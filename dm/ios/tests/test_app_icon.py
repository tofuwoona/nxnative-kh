#!/usr/bin/env python3
"""Exercise the real packaging icon block without game assets or Xcode."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'


class AppIconTest(unittest.TestCase):
    def run_icon(self, game, explicit=None, image=False):
        source = (TOOLS / 'build_ipa.sh').read_text()
        block = source[source.index('ICON=${DM_ICON:'):source.index('# A prepared Xcode project')]
        with tempfile.TemporaryDirectory(prefix='dm-icon-') as folder:
            root = Path(folder)
            (root / 'Gen').mkdir()
            env = dict(os.environ, GAME=game, ROMFS=str(root / 'RomFS'))
            env.pop('DM_ICON', None)
            if explicit is not None:
                env['DM_ICON'] = str(root / explicit)
            if image:
                # Public-domain synthetic PPM, not copyrighted game art.
                (root / 'test.ppm').write_bytes(b'P6\n1 1\n255\n\x12\x34\x56')
                subprocess.run(['sips', '-s', 'format', 'png', str(root / 'test.ppm'),
                                '--out', str(root / 'test.png')], check=True, capture_output=True)
            result = subprocess.run(['bash', '-uc', 't() { printf "%s\\n" "$*"; }; die() { t "FAIL: $*"; exit 1; };\n' + block],
                                    cwd=root, env=env, capture_output=True, text=True)
            staged = (root / 'Gen/Assets.xcassets/AppIcon.appiconset/icon.png').exists()
            config = (root / 'Gen/dm.xcconfig').read_text() if (root / 'Gen/dm.xcconfig').exists() else ''
            return result, staged, config

    def test_direct_kh2_missing_icon_is_fatal(self):
        result, _, _ = self.run_icon('010090C022978003')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('DM_ICON', result.stdout)

    def test_explicit_missing_icon_is_fatal(self):
        result, _, _ = self.run_icon('0100000000000000', 'missing.png')
        self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_other_titles_keep_optional_icon_behavior(self):
        result, staged, _ = self.run_icon('0100000000000000')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(staged)

    def test_explicit_image_stages_appicon(self):
        result, staged, config = self.run_icon('010090C022978003', 'test.png', image=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(staged)
        self.assertIn('DM_APPICON = AppIcon', config)


if __name__ == '__main__':
    unittest.main()
