"""Build and execute retained filesystem Make recipes without game/private inputs."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
GAME = '010015100B514000'  # The retained host CI's Wonder profile.


@unittest.skipUnless(sys.platform == 'darwin', 'host filesystem fixtures require macOS')
class HostFsMakeLinkageTests(unittest.TestCase):
    def test_retained_fs_recipes_link_and_execute(self):
        with tempfile.TemporaryDirectory(prefix='host-fs-make-') as temporary:
            scratch = Path(temporary).resolve()
            env = dict(os.environ, TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE='1')
            # Select only the repository profile and synthetic test fixtures.
            for key in list(env):
                if key.startswith(('DM_', 'MAKE')) or key in ('MFLAGS', 'GNUMAKEFLAGS'):
                    env.pop(key)
            profile = scratch / 'game_profile.h'
            generated = subprocess.run(
                [sys.executable, '-B', str(ROOT / 'dm/games/game.py'),
                 'header', GAME, str(profile)], cwd=scratch, env=env,
                text=True, capture_output=True, timeout=60)
            self.assertEqual(generated.returncode, 0, generated.stdout + generated.stderr)
            build = scratch / 'build'
            for name in ('t_fs_commit_list', 't_fs_case'):
                with self.subTest(target=name):
                    executable = build / name
                    self.assertFalse(executable.exists(), 'must exercise a fresh link')
                    compiled = subprocess.run(
                        ['make', '-C', str(ROOT / 'dm/host/tests'), 'GAME=' + GAME,
                         'GAME_H=' + str(profile), 'GINC=-I' + str(scratch),
                         'B=' + str(build), str(executable)], cwd=scratch, env=env,
                        text=True, capture_output=True, timeout=120)
                    self.assertEqual(compiled.returncode, 0,
                                     compiled.stdout + compiled.stderr)
                    self.assertTrue(executable.is_file())
                    executed = subprocess.run(
                        [str(executable)], cwd=scratch, env=env,
                        text=True, capture_output=True, timeout=120)
                    self.assertEqual(executed.returncode, 0,
                                     executed.stdout + executed.stderr)


if __name__ == '__main__':
    unittest.main()
