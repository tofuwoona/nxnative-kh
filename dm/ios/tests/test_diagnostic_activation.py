#!/usr/bin/env python3
"""CPU-only production boot/Play lifecycle and actual input publications."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_release_defaults import ROOT, GAME, PROFILES, TEMPLATE, clean_env, function


class DiagnosticActivation(unittest.TestCase):
    def test_play_activates_before_host_flags_and_only_one_rotation_thread(self):
        source = (ROOT / 'dm/ios/Sources/main.m').read_text()
        boot = function('dm/ios/Sources/main.m', 'boot_env')
        boot = boot.replace('NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES)[0]', 'test_doc')
        boot = boot.replace('NSBundle.mainBundle.resourcePath', 'test_res')
        match = re.search(r'^void front_ios_boot\(void\) \{.*?^\}', source, re.M | re.S)
        self.assertIsNotNone(match)
        assert match is not None
        play = match.group()
        play = play.replace('NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES)[0]', 'test_doc')
        # Existing source has inline activation; repaired source moves it to Play.
        activation = function('dm/ios/Sources/main.m', 'diag_activate') if 'static void diag_activate(' in source else ''
        harness = r'''#import <Foundation/Foundation.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <stdatomic.h>
static NSString *test_doc, *test_res;
static char *g_argv[4]; static int g_argc, g_boot_ok;
typedef struct { char *active, *previous; } diag_log_paths;
static int threads, owners, preloads, flags_fs, render_cached, configured, game_threads;
struct dm_flags { int thr, svc, fs, movie, dbg, imports, bootprof; } g_flag;
''' + function('dm/host/main.c', 'flags_init') + '\n' + function('dm/gfx/vk/hle_vk.m', 'vk_diag_on') + r'''
static void dm_host_preload_start(int argc, char **argv) { assert(argc == 2 && argv[0]); ++preloads; flags_init(); flags_fs = g_flag.fs; render_cached = !!vk_diag_on(); }
static void dm_input_trace_configure(void) { ++configured; }
static NSString *romfs_locate(void) { return test_res; }
static void *diag_log_rotate_thread(void *arg) { return arg; }
static void *boot_thread(void *arg) { return arg; }
static void front_ios_audio_session(void) {}
static void dm_log_rotate_assert_sole_owner(int fd) { assert(fd == fileno(stderr)); ++owners; }
static int record_thread(pthread_t *t, const pthread_attr_t *a, void *(*fn)(void *), void *arg) {
    *t = pthread_self(); (void)a;
    if (fn == boot_thread) { ++game_threads; return 0; }
    assert(fn == diag_log_rotate_thread);
    diag_log_paths *paths = arg; assert(paths->active && paths->previous);
    free(paths->active); free(paths->previous); free(paths); ++threads; return 0;
}
static int record_detach(pthread_t t) { (void)t; return 0; }
#define pthread_create record_thread
#define pthread_detach record_detach
''' + activation + '\n' + boot + '\n' + play + r'''
int main(int argc, char **argv) {
    assert(argc == 9);
    @autoreleasepool {
        test_doc = [NSString stringWithUTF8String:argv[1]]; test_res = [NSString stringWithUTF8String:argv[2]];
        g_boot_ok = boot_env(); assert(g_boot_ok);
        int kh2 = DM_GAME_PROGRAM_ID == 0x010090C022978003ull;
        assert(preloads == !kh2 && "KH2 preload must wait for Play/settings before flags_init");
        assert(threads == 0 && "no rotation before Play");
        // Same environment writes as LauncherModel.apply (tested separately in Swift).
        NSArray *keys = @[@"DM_SAVE_TRACE", @"DM_KH_INPUT_TRACE", @"DM_KH24_DIAG"];
        NSArray *locked = [[NSString stringWithUTF8String:getenv("DM_ENV_FILE_KEYS") ?: ""] componentsSeparatedByString:@" "];
        for (int i = 0; i < 3; ++i) if (kh2 && ![locked containsObject:keys[i]]) setenv([keys[i] UTF8String], argv[i + 3], 1);
        front_ios_boot(); front_ios_boot();
        assert(preloads == 1 && game_threads == 1);
        assert(threads == atoi(argv[6]) && owners == threads && "any independent trace requires one rotation thread");
        assert(flags_fs == atoi(argv[7]) && "FS flag must see selected save tracing before initialization");
        const char *render = getenv("DM_KH24_DIAG");
        assert(render_cached == (kh2 && render && *render && strcmp(render, "0")));
        assert(!strcmp(getenv("DM_SAVE_TRACE") ?: "absent", argv[8]));
        assert(configured == kh2 && "final input gate must be configured at Play");
        fprintf(stderr, "ordinary-log-sentinel\n"); fflush(stderr);
    }
}
'''
        with tempfile.TemporaryDirectory(prefix='kh2-activation-') as temporary:
            root = Path(temporary)
            src, exe = root / 'activation.m', root / 'activation'
            src.write_text(harness)
            for profile in (GAME, '010090C022978001'):
                header = root / (profile + '.h')
                subprocess.run([sys.executable, str(ROOT / 'dm/games/game.py'), 'header', profile, str(header)],
                               env=dict(clean_env(), DM_GAMES_DIR=str(PROFILES), DM_GAMES_FIRST='1'), check=True)
                self.assertIn('#define DM_GAME_ID "' + profile + '"', header.read_text())
                subprocess.run(['clang', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-Wno-incompatible-pointer-types', '-framework', 'Foundation',
                                '-include', str(header), str(src), '-o', str(exe)], check=True)
                cases = [
                    ('default off', ('0','0','0'), {}, None, None, 0, 0, '0'),
                    ('save alone', ('1','0','0'), {}, None, None, 1, 1, '1'),
                    ('input alone', ('0','1','0'), {}, None, None, 1, 0, '0'),
                    ('render alone', ('0','0','1'), {}, None, None, 1, 0, '0'),
                    ('save and input render off', ('1','1','0'), {}, None, None, 1, 1, '1'),
                    ('all on', ('1','1','1'), {}, None, None, 1, 1, '1'),
                    ('legacy bundle', ('0','0','0'), {}, None, 'DM_KH24_DIAG=1\n', 1, 1, '1'),
                    ('legacy process', ('0','0','0'), {'DM_KH24_DIAG':'1'}, None, None, 1, 1, '1'),
                    ('explicit save off legacy on', ('1','0','0'), {}, 'DM_SAVE_TRACE=0\n', TEMPLATE.read_text(), 1, 0, '0'),
                    ('documents wins', ('1','1','1'), {}, 'DM_SAVE_TRACE=0\nDM_KH_INPUT_TRACE=0\nDM_KH24_DIAG=0\n', TEMPLATE.read_text(), 0, 0, '0'),
                    ('process wins', ('1','1','1'), {'DM_SAVE_TRACE':'0','DM_KH_INPUT_TRACE':'0','DM_KH24_DIAG':'0'}, TEMPLATE.read_text(), TEMPLATE.read_text(), 0, 0, '0'),
                ]
                for label, choices, process, documents, bundled, rotate, fs, save in cases:
                    with self.subTest(profile=profile, case=label):
                        fixture = root / (profile + '-' + label.replace(' ', '-'))
                        doc, res = fixture / 'Documents', fixture / 'bundle'
                        doc.mkdir(parents=True); (res / 'dm').mkdir(parents=True)
                        (doc / 'log.txt').write_text('previous launch\n')
                        for path, text in ((doc / 'env.txt', documents), (res / 'dm/env.txt', bundled)):
                            if text is not None: path.write_text(text)
                        before = {p: p.read_bytes() for p in fixture.rglob('env.txt')}
                        kh2 = profile == GAME
                        if not kh2:
                            rotate = fs = 0
                            save = process.get('DM_SAVE_TRACE', '0' if documents and 'DM_SAVE_TRACE=0' in documents else 'absent')
                        run = subprocess.run([str(exe), str(doc), str(res), *choices, str(rotate), str(fs), save],
                                             env=dict(clean_env(), **process), capture_output=True, text=True)
                        log = (doc / 'log.txt').read_text()
                        self.assertEqual(run.returncode, 0, log + run.stderr)
                        self.assertIn('ordinary-log-sentinel', log)
                        self.assertEqual((doc / 'log.prev.txt').read_text(), 'previous launch\n')
                        self.assertEqual(before, {p: p.read_bytes() for p in fixture.rglob('env.txt')})

    def test_actual_input_setters_before_and_after_activation(self):
        source = (ROOT / 'dm/host/hle_hid.c').read_text()
        publications = source[source.index('static _Atomic uint64_t g_btn'):source.index('// DM_KEYS scripted input')]
        # Before the new API exists, exercise the old lazy gate and observe lost transitions.
        configure = 'dm_input_trace_configure();' if 'void dm_input_trace_configure(' in publications else ''
        harness = r'''#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <time.h>
#include <assert.h>
#include "dm_input.h"
static uint64_t guest_ns(void) { return clock_gettime_nsec_np(CLOCK_MONOTONIC); }
static int env_reads;
static char *counted_getenv(const char *key) { ++env_reads; return getenv(key); }
#define getenv counted_getenv
#define LOG(fmt, ...) fprintf(stderr, fmt "\n", ##__VA_ARGS__)
''' + publications + r'''
int main(int argc, char **argv) {
    assert(argc == 2);
    dm_input_set(1, 0, 0, 0, 0); dm_pad_set(2, 0, 0, 0, 0); // pre-Play controller publication
    assert(dm_input_last_event_ns() == 0);
    if (!strcmp(argv[1], "absent")) unsetenv("DM_KH_INPUT_TRACE");
    else setenv("DM_KH_INPUT_TRACE", argv[1], 1);
    ''' + configure + r'''
    int reads = env_reads;
    dm_input_set(1, -123, 234, -345, 456);
    uint64_t t = dm_input_last_event_ns();
    int on = DM_GAME_PROGRAM_ID == 0x010090C022978003ull && !strcmp(argv[1], "1");
    assert(!!t == on && "pre-Play OFF must not permanently cache input tracing OFF");
    dm_input_set(1, -123, 234, -345, 456); assert(dm_input_last_event_ns() == t);
    dm_input_set(0, 0, 0, 0, 0);
    if (on) assert(dm_input_last_event_ns() >= t);
    dm_pad_set(2, -1, 2, -3, 4); t = dm_input_last_event_ns();
    dm_pad_set(2, -1, 2, -3, 4); assert(dm_input_last_event_ns() == t);
    dm_pad_set(0, 0, 0, 0, 0);
    dm_pad_set_player(7, 4, -32767, 32767, 0, 0);
    dm_pad_set_player(7, 0, 0, 0, 0, 0);
    dm_pad_set_player(-1, 1, 0, 0, 0, 0); dm_pad_set_player(8, 1, 0, 0, 0, 0);
    assert(env_reads == reads && "no getenv per input publication after activation");
}
'''
        with tempfile.TemporaryDirectory(prefix='kh2-input-activation-') as temporary:
            src, exe = Path(temporary) / 'input.c', Path(temporary) / 'input'
            src.write_text(harness)
            for profile in (GAME, '010090C022978001'):
                header = Path(temporary) / (profile + '.h')
                subprocess.run([sys.executable, str(ROOT / 'dm/games/game.py'), 'header', profile, str(header)],
                               env=dict(clean_env(), DM_GAMES_DIR=str(PROFILES), DM_GAMES_FIRST='1'), check=True)
                self.assertIn('#define DM_GAME_ID "' + profile + '"', header.read_text())
                subprocess.run(['clang', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-fsanitize=address,undefined',
                                '-include', str(header), '-UTARGET_OS_IPHONE', '-DTARGET_OS_IPHONE=1',
                                '-I' + str(ROOT / 'dm/host'), str(src), '-o', str(exe)], check=True)
                for before in (None, '0', '1'):
                    for value in ('absent', '0', '1'):
                        with self.subTest(profile=profile, before=before, value=value):
                            env = clean_env()
                            if before is not None:
                                env['DM_KH_INPUT_TRACE'] = before
                            run = subprocess.run([str(exe), value], env=env, capture_output=True, text=True)
                            self.assertEqual(run.returncode, 0, run.stderr)
                            events = re.findall(r'^\[input-trace\] t_ns=(\d+) source=(-?\d+) buttons=(0x[0-9a-f]+|0) axes=(-?\d+),(-?\d+),(-?\d+),(-?\d+)$', run.stderr, re.M)
                            self.assertEqual(run.stderr.count('[input-trace]'), len(events), 'malformed trace line')
                            expected = [('-1','0x1','-123','234','-345','456'), ('-1','0','0','0','0','0'),
                                        ('0','0x2','-1','2','-3','4'), ('0','0','0','0','0','0'),
                                        ('7','0x4','-32767','32767','0','0'), ('7','0','0','0','0','0')]
                            self.assertEqual([e[1:] for e in events], expected if profile == GAME and value == '1' else [])
                            stamps = [int(e[0]) for e in events]
                            # CLOCK_MONOTONIC need not produce unique ticks for
                            # adjacent transitions; exact event counts prove both.
                            self.assertTrue(all(t > 0 for t in stamps))
                            self.assertEqual(stamps, sorted(stamps))


if __name__ == '__main__':
    unittest.main()
