#!/usr/bin/env python3
"""Execute the exact native cached gate, without Metal or a game launch."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]


class CoalesceDefaultsTests(unittest.TestCase):
    def test_native_default_profile_and_explicit_environment(self):
        source = (ROOT / 'dm/gfx/vk/hle_vk.m').read_text()
        gate, = re.findall(r'static int vk_coalesce_on\(void\) \{.*?\n\}', source, re.S)
        harness = '''#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
''' + gate + '''
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    int expected = atoi(argv[1]);
    if (vk_coalesce_on() != expected) return 1;
    // The result remains cached after startup, as in production.
    setenv("DM_VK_COALESCE_PASSES", expected ? "0" : "1", 1);
    return vk_coalesce_on() == expected ? 0 : 3;
}
'''
        with tempfile.TemporaryDirectory(prefix='kh2-coalesce-gate-', dir=os.environ['TMPDIR']) as tmp:
            src, exe = Path(tmp) / 'gate.c', Path(tmp) / 'gate'
            src.write_text(harness)
            for profile in ('0x010090C022978003ull', '0x010090C022978001ull', '0x01007EF00011E000ull'):
                subprocess.run(['clang', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                                '-DDM_GAME_PROGRAM_ID=' + profile, str(src), '-o', str(exe)], check=True)
                for value in (None, '0', '1', '', 'true', '2'):
                    with self.subTest(profile=profile, env=value):
                        env = dict(os.environ)
                        env.pop('DM_VK_COALESCE_PASSES', None)
                        if value is not None:
                            env['DM_VK_COALESCE_PASSES'] = value
                        expected = profile == '0x010090C022978003ull' and value in (None, '1')
                        result = subprocess.run([str(exe), str(int(expected))], env=env)
                        self.assertEqual(result.returncode, 0, 'native default/override/cache mismatch')


if __name__ == '__main__':
    unittest.main()
