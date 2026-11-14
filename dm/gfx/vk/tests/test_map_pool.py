#!/usr/bin/env python3
"""Actual map-handler ownership tests. CPU fake backing by default; --metal opts in.

No game, private module, save, credentials or Metal device is needed by CPU tests.
Apple SDK/frameworks are required. Unused host integration symbols are dead-stripped;
this is not a complete game-host link or device/driver-residency test.
"""
import argparse
import contextlib
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[3]
METAL = False
OUT = os.environ.get('DM_MAP_TEST_OUT')
SANITIZER_ERRORS = ('ERROR: AddressSanitizer', 'runtime error:', 'SUMMARY: UndefinedBehaviorSanitizer')

@unittest.skipUnless(platform.system() == 'Darwin', 'Apple Objective-C SDK required')
class MapPool(unittest.TestCase):
    def run_matrix(self, metal):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('DM_', 'ASAN_', 'UBSAN_', 'MTL_'))}
        env.update(ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        if metal:
            env['MTL_DEBUG_LAYER'] = '1'
        def call(cmd, out, name):
            result = subprocess.run(cmd, env=env, cwd=SOURCE, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            (out / (name + '.log')).write_text(result.stdout)
            self.assertEqual(result.returncode, 0, result.stdout[-10000:])
            for error in SANITIZER_ERRORS:
                self.assertNotIn(error, result.stdout)
            return result.stdout
        if OUT:
            Path(OUT).mkdir(parents=True, exist_ok=True)
        workspace = (contextlib.nullcontext(tempfile.mkdtemp(prefix='vk-map-pool-', dir=OUT))
                     if OUT else tempfile.TemporaryDirectory(prefix='vk-map-pool-'))
        with workspace as tmp:
            out = Path(tmp)
            for profile in ('010090C022978003', '010090C022978001'):
                pd = out / profile
                pd.mkdir()
                penv = dict(env, DM_GAMES_DIR=str(SOURCE / 'dm/games/010090C022978000/direct-profiles'), DM_GAMES_FIRST='1')
                result = subprocess.run(['python3', str(SOURCE / 'dm/games/game.py'), 'header', profile,
                                         str(pd / 'game_profile.h')], env=penv, text=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout)
                for opt in (0, 2):
                    for sanitize in (False, True):
                        with self.subTest(profile=profile, opt=opt, sanitize=sanitize, metal=metal):
                            name = '{}-O{}-{}-{}'.format(profile, opt, int(sanitize), 'metal' if metal else 'cpu')
                            binary = out / name
                            fixture = HERE / ('t_map_pool_metal.m' if metal else 't_map_pool_cpu.m')
                            cmd = ['xcrun', 'clang', '-O' + str(opt), '-g', '-fobjc-arc',
                                   '-ffunction-sections', '-fdata-sections', '-I', str(pd),
                                   '-I', str(SOURCE / 'dm/third_party/vulkan-headers/include'),
                                   '-DHLE_VK_SOURCE="' + str(SOURCE / 'dm/gfx/vk/hle_vk.m') + '"',
                                   str(fixture), '-Wl,-dead_strip', '-Wl,-undefined,dynamic_lookup',
                                   '-framework', 'Foundation', '-framework', 'Metal',
                                   '-framework', 'QuartzCore', '-o', str(binary)]
                            if sanitize:
                                cmd[2:2] = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
                            call(cmd, out, name + '-build')
                            text = call([str(binary)], out, name)
                            self.assertRegex(text, r'checks=\d+ failed=0')
                            print(name + ': ' + next(l for l in text.splitlines() if 'checks=' in l), flush=True)

    def test_cpu_ownership(self):
        self.run_matrix(False)

    def test_metal_ownership(self):
        if not METAL:
            self.skipTest('explicit --metal opt-in required')
        self.run_matrix(True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--metal', action='store_true')
    parser.add_argument('--source-root', type=Path, default=SOURCE,
                        help='Explicit alternate production source for regression/baseline checks')
    args, rest = parser.parse_known_args()
    SOURCE = args.source_root.resolve()
    METAL = args.metal
    unittest.main(argv=[__file__] + rest)
