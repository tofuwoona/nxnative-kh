"""Game-free tests of the direct KH2 packaging *metadata* guard.

The real checker compares profile and fixup build IDs and requires an image
file to exist. These explicitly SYNTHETIC fixtures are not NSOs, game modules,
serializer output, image-encoder validation, or proof of runtime save gates.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
PROFILE = ROOT / 'dm/games/010090C022978000/direct-profiles/010090C022978003/game.tsv'
COLLECTION_PROFILE = ROOT / 'dm/games/010090C022978000/game.tsv'
CHECKER = ROOT / 'dm/ios/tools/check_kh2_direct_patch.py'


def main_build_id(profile):
    rows = [line.split('\t') for line in profile.read_text().splitlines()
            if line and not line.startswith('#')]
    builds = [row for row in rows if row[0] == 'build' and row[1] == 'v0']
    if len(builds) != 1:
        raise AssertionError('fixture requires exactly one real v0 build')
    return next(field.split('=', 1)[1] for field in builds[0][3:]
                if field.startswith('main='))


class DirectKh2PackagingMetadataTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='kh2-packaging-metadata-')
        self.addCleanup(temporary.cleanup)
        self.scratch = Path(temporary.name).resolve()
        self.patched = self.scratch / 'synthetic-patched'
        self.patched.mkdir()
        self.direct_id = main_build_id(PROFILE)
        self.collection_id = main_build_id(COLLECTION_PROFILE)
        self.assertNotEqual(self.direct_id, self.collection_id)
        self.fixups = self.patched / 'main.fixups.tsv'
        self.image = self.patched / 'main.patched.bin'
        self.fixups.write_text('# SYNTHETIC packaging metadata only\n'
                               '# BUILD_ID\t' + self.direct_id + '\n')
        # The checker only tests file presence, NOT binary contents.
        self.image.write_bytes(b'SYNTHETIC PLACEHOLDER - NOT A GAME MODULE\n')

    def check(self, *, profile=PROFILE, package='v0', expected=0, message=None):
        result = subprocess.run(
            [sys.executable, '-B', str(CHECKER), str(profile), package, str(self.patched)],
            cwd=self.scratch, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        if message is not None:
            self.assertIn(message, result.stderr)
        return result

    def test_matching_direct_build_metadata_is_accepted(self):
        self.check()

    def test_collection_build_metadata_is_rejected(self):
        self.fixups.write_text('# SYNTHETIC collection metadata only\n'
                               '# BUILD_ID\t' + self.collection_id + '\n')
        result = self.check(expected=1, message='not Program 3')
        self.assertIn(self.direct_id, result.stderr)
        self.assertIn(self.collection_id, result.stderr)

    def test_wrong_build_metadata_is_rejected(self):
        self.fixups.write_text('# BUILD_ID\tsynthetic-wrong-build-id\n')
        self.check(expected=1, message='direct main build ID')

    def test_missing_image_is_rejected(self):
        self.image.unlink()
        self.check(expected=1, message='patched main or fixups missing')

    def test_missing_fixups_are_rejected(self):
        self.fixups.unlink()
        self.check(expected=1, message='patched main or fixups missing')

    def test_missing_build_id_is_rejected(self):
        self.fixups.write_text('# SYNTHETIC metadata without a build ID\n')
        self.check(expected=1, message='has none')

    def test_missing_patched_directory_is_rejected(self):
        self.patched = self.scratch / 'absent'
        self.check(expected=1, message='patched main or fixups missing')

    def test_unknown_package_is_rejected(self):
        self.check(package='synthetic-missing-package', expected=1, message='no unique build')

    def test_ambiguous_profile_build_is_rejected(self):
        text = PROFILE.read_text()
        build = next(line for line in text.splitlines() if line.startswith('build\tv0\t'))
        profile = self.scratch / 'synthetic-ambiguous-profile.tsv'
        profile.write_text(text + '\n' + build + '\n')
        self.check(profile=profile, expected=1, message='no unique build')

    def test_missing_profile_main_id_is_rejected(self):
        # Malformed metadata is generated only in this disposable fixture.
        lines = PROFILE.read_text().splitlines()
        profile = self.scratch / 'synthetic-no-main-profile.tsv'
        profile.write_text('\n'.join(
            '\t'.join(field for field in line.split('\t') if not field.startswith('main='))
            if line.startswith('build\tv0\t') else line for line in lines) + '\n')
        self.check(profile=profile, expected=1, message='no main build ID')


if __name__ == '__main__':
    unittest.main()
