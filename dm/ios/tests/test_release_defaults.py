#!/usr/bin/env python3
"""Release-default contract, using disposable inputs and production source.

Runs the complete build_ipa.sh --prepare-xcode path, not an app/IPA build.
Only host/module generation, font generation and xcodegen are stand-ins;
profile selection, input checks, launcher generation, env copying/cleanup,
icon conversion and resource-path generation run their actual tools.
Native gates and iOS boot log/env setup are extracted verbatim and executed
without UIKit, a game host, GPU or device. Requires macOS, clang and sips.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
GAME = '010090C022978003'
PROFILES = ROOT / 'dm/games/010090C022978000/direct-profiles'
TEMPLATE = ROOT / 'dm/games/010090C022978000/kh2-24h-diagnostic.env'
KEYS = ('DM_ENV_FILE', 'DM_KH24_DIAG', 'DM_KH_INPUT_TRACE', 'DM_SAVE_TRACE',
        'DM_FS', 'DM_VK_COALESCE_PASSES', 'DM_GAMES_DIR', 'DM_GAMES_FIRST')


def clean_env():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for key in KEYS:
        env.pop(key, None)
    return env


def function(path, name):
    source = (ROOT / path).read_text()
    # Check one-line functions first, so they cannot swallow a later body.
    matches = re.findall(r'^static int ' + name + r'\(void\) \{[^\n]*\}', source, re.M)
    if not matches:
        matches = re.findall(r'^static (?:int|void) ' + name + r'\([^\n]*\) \{.*?^\}', source, re.S | re.M)
    if len(matches) != 1:
        raise AssertionError(f'expected one production {name}, got {len(matches)}')
    return matches[0]


class PreparationDefaultsTests(unittest.TestCase):
    def test_regular_optin_then_regular_does_not_reuse_generated_env(self):
        with tempfile.TemporaryDirectory(prefix='dm-release-prep-') as temporary:
            root = Path(temporary)
            dm, ios = root / 'repo/dm', root / 'repo/dm/ios'
            tools = ios / 'tools'
            tools.mkdir(parents=True)
            (ios / 'Sources').mkdir()
            (dm / 'host').mkdir()
            (dm / 'gfx/nvn').mkdir(parents=True)
            (dm / 'tools').mkdir()
            (dm / 'games').symlink_to(ROOT / 'dm/games', target_is_directory=True)
            for name in ('build_ipa.sh', 'check_kh2_direct_patch.py', 'gen_resources.py'):
                shutil.copyfile(ROOT / 'dm/ios/tools' / name, tools / name)
            shutil.copyfile(ROOT / 'dm/ios/project.yml', ios / 'project.yml')
            shutil.copyfile(ROOT / 'dm/gfx/nvn/dmsh_chain.h', dm / 'gfx/nvn/dmsh_chain.h')
            shutil.copyfile(ROOT / 'dm/tools/nacp.py', dm / 'tools/nacp.py')
            (tools / 'gen_build.py').write_text('print("// fixture: no host build")\n')
            (tools / 'gen_embed.py').write_text('print("")\n')
            (dm / 'tools/make_ext_font.py').write_text(
                'import pathlib, sys\npathlib.Path(sys.argv[1]).write_bytes(b"fixture font")\n')
            binaries = root / 'bin'
            binaries.mkdir()
            (binaries / 'python3').symlink_to(sys.executable)
            (binaries / 'xcodegen').write_text('#!/bin/sh\nmkdir -p DmIOS.xcodeproj\n')
            for name in ('xcodebuild', 'make', 'codesign'):
                (binaries / name).write_text('#!/bin/sh\necho "forbidden build tool" >&2\nexit 97\n')
            for executable in binaries.iterdir():
                if not executable.is_symlink():
                    executable.chmod(0o755)
            patched, romfs, shaders = (root / name for name in ('patched', 'romfs', 'shaders'))
            for folder in (patched, romfs, shaders / 'vk'):
                folder.mkdir(parents=True)
            # Tiny synthetic module/table fixtures satisfy the real profile checks;
            # no game bytes or proprietary shader libraries are used.
            rows = [line.split('\t') for line in (PROFILES / GAME / 'game.tsv').read_text().splitlines()
                    if line and not line.startswith('#')]
            fields = {row[0]: row[1] for row in rows if len(row) > 1}
            build = next(row for row in rows if row[0] == 'build' and row[1] == fields['package'])
            main_id = next(value.split('=', 1)[1] for value in build[3:] if value.startswith('main='))
            for module in fields['modules'].split():
                (patched / f'{module}.patched.bin').write_bytes(b'fixture module')
                for table in ('fixups', 'gates', 'cuts', 'obs'):
                    (patched / f'{module}.{table}.tsv').write_text('# BUILD_ID\t' + main_id + '\n')
            marker = romfs / fields['romfs_marker']
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch()
            (shaders / 'vk/vk_shaders.metallib').write_bytes(b'fixture shader')
            font, icon = root / 'font.ttf', root / 'icon.ppm'
            font.write_bytes(b'fixture font')
            icon.write_bytes(b'P6\n1 1\n255\n\x12\x34\x56')
            project = root / 'project'
            env = dict(clean_env(), PATH=str(binaries) + os.pathsep + os.environ['PATH'],
                       GAME=GAME, DM_GAMES_DIR=str(PROFILES), DM_GAMES_FIRST='1',
                       W=str(root / 'work'), PATCHED=str(patched), ROMFS=str(romfs),
                       MSL_IOS=str(shaders), GFXAPI='vulkan', AOC='', STD_FONT=str(font),
                       FONT_PY=sys.executable, DM_ICON=str(icon), DM_DISPLAY_NAME='Fixture',
                       DM_APP_VERSION='1.0', DM_XCODE_PROJECT_DIR=str(project),
                       DM_XCODE_DERIVED_DATA=str(root / 'derived-data'))
            generated = project / 'Gen/dm/env.txt'
            # Both a clean prep and reuse of a diagnostic-prepared project matter.
            for label, optin in (('clean release', None), ('explicit diagnostic', TEMPLATE),
                                 ('release after diagnostic', None), ('empty optin', '')):
                with self.subTest(preparation=label):
                    run_env = dict(env)
                    if optin is not None:
                        run_env['DM_ENV_FILE'] = str(optin)
                    result = subprocess.run(['bash', str(tools / 'build_ipa.sh'), '--prepare-xcode'],
                                            env=run_env, capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('ready: select your Team', result.stdout)
                    if optin:
                        self.assertEqual(generated.read_bytes(), TEMPLATE.read_bytes())
                    else:
                        self.assertFalse(generated.exists(), 'release bundled a diagnostic env')
                    settings = json.loads((project / 'Gen/dm/launcher.json').read_text())['settings']
                    defaults = {item['env']: item['default'] for item in settings}
                    self.assertEqual(defaults['DM_VK_COALESCE_PASSES'], '1')
                    self.assertNotIn('DM_KH24_DIAG', defaults)
                    self.assertNotIn('DM_KH_INPUT_TRACE', defaults)
                    self.assertTrue((project / 'Gen/resources.env').is_file())
                    self.assertFalse(list(root.rglob('*.app')))
                    self.assertFalse(list(root.rglob('*.ipa')))


class NativeDefaultsTests(unittest.TestCase):
    def test_actual_fs_vulkan_input_gates_and_independent_miss_default(self):
        gates = '\n'.join((function('dm/gfx/vk/hle_vk.m', 'vk_diag_on'),
                            function('dm/gfx/vk/hle_vk.m', 'vk_coalesce_on'),
                            function('dm/host/hle_fs.c', 'save_trace_on'),
                            function('dm/host/hle_hid.c', 'kh_input_trace')))
        harness = '''#include <stdatomic.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <pthread.h>
#include <time.h>
#define DM_PLAYERS 8
static _Atomic uint64_t g_input_last_ns;
static int input_lines;
#define LOG(...) (++input_lines)
''' + gates + '''
int main(int argc, char **argv) {
    if (argc != 5) return 2;
    kh_input_trace(-1, 1, 0, 0, 0, 0);
    (void)atomic_load(&g_input_last_ns);
    return (!!vk_diag_on() != atoi(argv[1]) ||
            !!save_trace_on() != atoi(argv[2]) ||
            !!input_lines != atoi(argv[3]) ||
            !!vk_coalesce_on() != atoi(argv[4]));
}
'''
        with tempfile.TemporaryDirectory(prefix='dm-release-gates-') as temporary:
            src, exe = Path(temporary) / 'gate.c', Path(temporary) / 'gate'
            src.write_text(harness)
            for profile in (GAME, '010090C022978001', '01007EF00011E000'):
                subprocess.run(['clang', '-Wall', '-Wextra', '-Werror', '-pthread',
                                '-fsanitize=address,undefined', '-DDM_GAME_PROGRAM_ID=0x' + profile + 'ull',
                                str(src), '-o', str(exe)], check=True)
                for value in (None, '', '0', '1'):
                    for coalesce in (None, '0', '1'):
                        with self.subTest(profile=profile, diagnostics=value, miss=coalesce):
                            env = clean_env()
                            if value is not None:
                                env.update({key: value for key in ('DM_KH24_DIAG', 'DM_SAVE_TRACE', 'DM_KH_INPUT_TRACE')})
                            if coalesce is not None:
                                env['DM_VK_COALESCE_PASSES'] = coalesce
                            kh2, on = profile == GAME, value == '1'
                            expected = [kh2 and on, on, kh2 and on, kh2 and coalesce != '0']
                            result = subprocess.run([str(exe)] + [str(int(x)) for x in expected], env=env)
                            self.assertEqual(result.returncode, 0, 'production trace/MISS gate mismatch')


class BootDefaultsTests(unittest.TestCase):
    def test_boot_env_precedence_rotation_optin_and_ordinary_log(self):
        source = (ROOT / 'dm/ios/Sources/main.m').read_text()
        # Keep the real ordinary-log setup, env parser and entire diagnostic
        # activation block. Supply only Documents/bundle roots; do not run UIKit
        # or the rest of game startup. Record thread requests without spawning it.
        block = source[source.index('    // Log: the host only writes'):source.index('    if (getenv("DM_METAL_HUD")')]
        harness = '''#import <Foundation/Foundation.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
typedef struct { char *active, *previous; } diag_log_paths;
static int threads, owners;
static void *diag_log_rotate_thread(void *arg) { return arg; }
static void dm_log_rotate_assert_sole_owner(int fd) { assert(fd == fileno(stderr)); ++owners; }
static int record_thread(pthread_t *thread, const pthread_attr_t *attr, void *(*fn)(void *), void *arg) {
    *thread = pthread_self(); (void)attr;
    assert(fn == diag_log_rotate_thread);
    diag_log_paths *paths = arg;
    assert(paths->active && paths->previous);
    free(paths->active); free(paths->previous); free(paths);
    ++threads; return 0;
}
static int record_detach(pthread_t thread) { (void)thread; return 0; }
#define pthread_create record_thread
#define pthread_detach record_detach
int main(int argc, char **argv) {
    if (argc != 6) return 2;
    @autoreleasepool {
        NSFileManager *fm = NSFileManager.defaultManager;
        NSString *doc = [NSString stringWithUTF8String:argv[1]];
        NSString *res = [NSString stringWithUTF8String:argv[2]];
''' + block + '''
        fprintf(stderr, "ordinary-log-sentinel\\n"); fflush(stderr);
        int expected = atoi(argv[3]);
        if (threads != expected || owners != expected) return 3;
        const char *fs = getenv("DM_FS"), *save = getenv("DM_SAVE_TRACE");
        if (!!fs != expected || !!save != expected) return 4;
        if (expected && (strcmp(fs, "1") || strcmp(save, "1"))) return 5;
        if (strcmp(getenv("DM_KH24_DIAG") ?: "absent", argv[4])) return 6;
        if (strcmp(getenv("DM_KH_INPUT_TRACE") ?: "absent", argv[5])) return 7;
        return 0;
    }
}
'''
        with tempfile.TemporaryDirectory(prefix='dm-release-boot-') as temporary:
            root = Path(temporary)
            src, exe = root / 'boot.m', root / 'boot'
            src.write_text(harness)
            for profile in (GAME, '010090C022978001'):
                subprocess.run(['clang', '-Wall', '-Wextra', '-Werror', '-framework', 'Foundation',
                                '-DDM_GAME_ID="' + profile.lower() + '"', str(src), '-o', str(exe)],
                               check=True, capture_output=True)
                cases = [
                    ('release', None, None, None, 'absent', 'absent'),
                    ('process off', '0', None, None, '0', 'absent'),
                    ('process on', '1', None, None, '1', 'absent'),
                    ('bundle off', None, None, 'DM_KH24_DIAG=0\n', '0', 'absent'),
                    ('bundle template', None, None, TEMPLATE.read_text(), '1', '1'),
                    ('Documents optin', None, TEMPLATE.read_text(), None, '1', '1'),
                    ('Documents wins', None, 'DM_KH24_DIAG=0\nDM_KH_INPUT_TRACE=0\n', TEMPLATE.read_text(), '0', '0'),
                    ('process wins', '0', TEMPLATE.read_text(), TEMPLATE.read_text(), '0', '1'),
                ]
                for label, process, documents, bundled, diag, input_trace in cases:
                    with self.subTest(profile=profile, case=label):
                        fixture = root / (profile + '-' + label.replace(' ', '-'))
                        doc, res = fixture / 'Documents', fixture / 'bundle'
                        doc.mkdir(parents=True)
                        (res / 'dm').mkdir(parents=True)
                        (doc / 'log.txt').write_text('previous launch\n')
                        (doc / 'log.prev.txt').write_text('older launch\n')
                        for path, text in ((doc / 'env.txt', documents), (res / 'dm/env.txt', bundled)):
                            if text is not None:
                                path.write_text(text)
                        before = {p: p.read_bytes() for p in fixture.rglob('env.txt')}
                        env = clean_env()
                        if process is not None:
                            env['DM_KH24_DIAG'] = process
                        expected = profile == GAME and diag == '1'
                        result = subprocess.run([str(exe), str(doc), str(res), str(int(expected)), diag, input_trace], env=env)
                        self.assertEqual(result.returncode, 0, 'boot logging/env/rotation mismatch')
                        self.assertEqual((doc / 'log.prev.txt').read_text(), 'previous launch\n')
                        log = (doc / 'log.txt').read_text()
                        self.assertIn('ordinary-log-sentinel', log)
                        self.assertEqual('[kh2-diag] continuous' in log, expected)
                        self.assertEqual(before, {p: p.read_bytes() for p in fixture.rglob('env.txt')}, 'boot changed user overrides')


if __name__ == '__main__':
    unittest.main()
