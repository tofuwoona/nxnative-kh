"""Game-free packaging metadata and native input fixture portability regressions.

Native adapter coverage requires macOS, but packaging coverage is stdlib-only.
All generated headers, executables, traces and evidence stay in temporary roots.
"""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
PACKAGING_TEST = ROOT / 'dm/ios/tests/test_kh2_direct_patch.py'


def isolated_env(scratch):
    env = dict(os.environ, TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE='1')
    for key in ('DM_SAVE', 'DM_CTL', 'DM_KEYS', 'DM_KH_REPLAY_ALLOW',
                'DM_KH_REPLAY_CONFIRM_SAVE'):
        env.pop(key, None)
    env.update(DM_GAMES_DIR=str(ROOT / 'dm/games/010090C022978000/direct-profiles'),
               DM_GAMES_FIRST='1')
    return env


class FixturePortabilityTests(unittest.TestCase):
    def test_direct_packaging_has_no_private_absolute_path(self):
        tree = ast.parse(PACKAGING_TEST.read_text())
        absolute = [node.args[0].value for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'Path' and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                    and Path(node.args[0].value).is_absolute()]
        self.assertEqual(absolute, [], 'packaging tests must not require private game paths')

    def test_direct_packaging_import_is_inert(self):
        with tempfile.TemporaryDirectory(prefix='kh-packaging-import-') as temporary:
            scratch = Path(temporary).resolve()
            code = '''import runpy
import sys
from unittest.mock import patch
with patch('subprocess.run', side_effect=AssertionError('import must not execute packaging checks')):
    runpy.run_path(sys.argv[1], run_name='portable_packaging_import')
'''
            result = subprocess.run([sys.executable, '-B', '-c', code, str(PACKAGING_TEST)],
                                    cwd=scratch, env=isolated_env(scratch),
                                    text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(sys.platform == 'darwin', 'CPU input runner requires macOS')
    def test_default_input_runner_executes_mac_adapter(self):
        with tempfile.TemporaryDirectory(prefix='kh-input-runner-portability-') as temporary:
            scratch = Path(temporary).resolve()
            out = scratch / 'results'
            result = subprocess.run(
                [sys.executable, '-B', str(ROOT / 'dm/host/tests/run_input_replay.py'),
                 '--out', str(out)], cwd=scratch, env=isolated_env(scratch),
                text=True, capture_output=True, timeout=180)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((out / 'results.json').read_text())
            labels = {entry['label'] for entry in report['results'] if entry['passed']}
            self.assertTrue({'build-t_input_replay_mac', 'mac-adapter'} <= labels,
                            'default CPU runner must compile and execute the real Mac adapter fixture')
            self.assertIn('exact press/release order and guard verified',
                          (out / 'mac-adapter.stdout').read_text())
            self.assertEqual(list((out / 'scratch').glob('kh-input-replay.*')), [])

    @unittest.skipUnless(sys.platform == 'darwin', 'actual Mac adapter requires macOS')
    def test_mac_adapter_uses_explicit_tmpdir(self):
        with tempfile.TemporaryDirectory(prefix='kh-fixture-portability-') as temporary:
            scratch = Path(temporary).resolve()
            env = isolated_env(scratch)
            profile = scratch / 'game_profile.h'
            generated = subprocess.run(
                [sys.executable, '-B', str(ROOT / 'dm/games/game.py'), 'header',
                 '010090C022978003', str(profile)], cwd=scratch, env=env,
                text=True, capture_output=True, timeout=60)
            self.assertEqual(generated.returncode, 0, generated.stdout + generated.stderr)
            # Include stdlib before interposing, so its declaration is unchanged;
            # checked_mkdtemp calls libc only after checking the actual template.
            wrapper = scratch / 'adapter_tmpdir.c'
            wrapper.write_text('''#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static char *checked_mkdtemp(char *pattern) {
    const char *root = getenv("TMPDIR");
    assert(root && *root);
    size_t n = strlen(root);
    assert(strncmp(pattern, root, n) == 0 &&
           strncmp(pattern + n, "/kh-input-replay.", 17) == 0 &&
           "Mac fixture must create its trace under explicit TMPDIR");
    return mkdtemp(pattern);
}
#define mkdtemp checked_mkdtemp
#include ''' + json.dumps(str(ROOT / 'dm/host/tests/t_input_replay_mac.c')) + '\n')
            executable = scratch / 'adapter_tmpdir'
            built = subprocess.run(
                ['clang', '-O1', '-g', '-Wall', '-Wextra', '-Wno-unused-function',
                 '-Wno-unused-parameter', '-I' + str(scratch),
                 '-I' + str(ROOT / 'dm/host'), str(wrapper), '-o', str(executable)],
                cwd=scratch, env=env, text=True, capture_output=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            result = subprocess.run([str(executable)], cwd=scratch, env=env,
                                    text=True, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('exact press/release order and guard verified', result.stdout)
            self.assertEqual(list(scratch.glob('kh-input-replay.*')), [],
                             'adapter must remove its synthetic trace directory')


if __name__ == '__main__':
    unittest.main()
