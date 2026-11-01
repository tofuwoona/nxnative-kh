"""The launcher offers frame buffering only for the graphics API selected by the packer."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('launcher_settings', ROOT / 'dm/games/settings.py')
settings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settings)


class LauncherSettingsTests(unittest.TestCase):
    def test_kh_aspect_fill_is_opt_in_and_game_scoped(self):
        profiles = ROOT / 'dm/games/010090C022978000/direct-profiles'
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings.nacp, 'languages', return_value=['en-US']):
            with patch.dict(os.environ, {'DM_GAMES_DIR': str(profiles), 'DM_GAMES_FIRST': '1', 'GFXAPI': 'vulkan'}):
                for gid, expected in [('010090C022978001', 1), ('010090C022978003', 1), ('01007EF00011E000', 0)]:
                    with self.subTest(gid=gid):
                        rows = settings.build(gid, tmp, Path(tmp) / 'control.nacp')['settings']
                        found = [s for s in rows if s['env'] == 'DM_ASPECT_FILL']
                        self.assertEqual(len(found), expected)
                        if found:
                            self.assertEqual(found[0]['kind'], 'toggle')
                            self.assertEqual(found[0]['default'], '0')
                            self.assertIn('crop', found[0]['note'].lower())

    def test_kh2_miss_fix_defaults_on_only_for_program3(self):
        profiles = ROOT / 'dm/games/010090C022978000/direct-profiles'
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings.nacp, 'languages', return_value=['en-US']):
            with patch.dict(os.environ, {'DM_GAMES_DIR': str(profiles), 'DM_GAMES_FIRST': '1', 'GFXAPI': 'vulkan'}):
                for gid in ('010090C022978003', '010090C022978001', '01007EF00011E000'):
                    with self.subTest(gid=gid):
                        rows = settings.build(gid, tmp, Path(tmp) / 'control.nacp')['settings']
                        found = [s for s in rows if s['env'] == 'DM_VK_COALESCE_PASSES']
                        self.assertEqual(len(found), int(gid == '010090C022978003'))
                        if found:
                            self.assertEqual(found[0]['kind'], 'toggle')
                            self.assertEqual(found[0]['default'], '1')
                            self.assertIn('MISS', found[0]['label'])
                            self.assertIn('slowdown', found[0]['note'])
                            self.assertIn('disable', found[0]['note'])

    def test_removed_hud_option_is_not_emitted(self):
        profiles = ROOT / 'dm/games/010090C022978000/direct-profiles'
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings.nacp, 'languages', return_value=['en-US']):
            with patch.dict(os.environ, {'DM_GAMES_DIR': str(profiles), 'DM_GAMES_FIRST': '1'}):
                for gid in ('010090C022978003', '010090C022978001'):
                    rows = settings.build(gid, tmp, Path(tmp) / 'control.nacp')['settings']
                    self.assertNotIn('DM_PRESERVE_FULL_HUD', [s['env'] for s in rows])

    def test_frame_buffering_by_graphics_api(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings.nacp, 'languages', return_value=['en-US']):
            for api, gid in [('nvn', '01007EF00011E000'), ('vulkan', '0100535012974000'), ('gl', '010014E00DB56000'), ('', '01007EF00011E000')]:
                with self.subTest(api=api), patch.dict(os.environ, {'GFXAPI': api}):
                    rows = settings.build(gid, tmp, Path(tmp) / 'control.nacp')['settings']
                    found = [s for s in rows if s['env'] == 'DM_PRESENT_SNAP']
                    self.assertEqual(len(found), int(api == 'nvn'))
                    if found:
                        self.assertEqual(found[0]['kind'], 'toggle')
                        self.assertEqual(found[0]['default'], '0')
                        self.assertIn('latency', found[0]['note'])


if __name__ == '__main__':
    unittest.main()
