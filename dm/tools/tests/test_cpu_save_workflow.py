"""Portable, stdlib-only contract for game-free native save CI.

This checks orchestration, not native behavior: the macOS job executes the real
runners. Keep its header-mutating FS/path runners serial in one isolated checkout.
"""
from pathlib import Path
import re
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[3]
CHECKOUT = 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1'
PYTHON = 'actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0'
ARTIFACT = 'actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9'


class CpuSaveWorkflowTests(unittest.TestCase):
    def test_game_free_save_job_runs_all_modes_serially_with_external_outputs(self):
        workflow = (ROOT / '.github/workflows/tests.yml').read_text()
        jobs = dict(re.findall(
            r'^  ([\w-]+):\n(.*?)(?=^  [\w-]+:\n|\Z)',
            workflow.split('jobs:\n', 1)[1], re.M | re.S))
        self.assertIn('cpu-save-tests', jobs,
                      'missing game-free CPU save CI coverage')
        job = jobs['cpu-save-tests']
        self.assertRegex(job, r'runs-on: macos-26\b')
        self.assertIn('persist-credentials: false', job)
        for action in (CHECKOUT, PYTHON, ARTIFACT):
            self.assertIn(action, job)
        self.assertIn("python-version: '3.14'", job)
        self.assertRegex(job, r'python -m pip install lz4 capstone fonttools\b')
        self.assertIn("PYTHONDONTWRITEBYTECODE: '1'", job)
        self.assertNotRegex(job, r'\b(matrix|needs|continue-on-error)\s*:')

        blocks = re.findall(r'^        run: \|\n((?:^          .*\n|^\n)*)', job, re.M)
        self.assertEqual(len(blocks), 1, 'all native runners belong in one serial shell')
        shell = textwrap.dedent(blocks[0])
        self.assertIn('set -euo pipefail', shell)
        self.assertIn('out=$(mktemp -d "$RUNNER_TEMP/cpu-save-tests.XXXXXX")', shell)
        commands = [line.strip() for line in shell.splitlines()
                    if re.search(r'\bpython dm/host/tests/run_', line)]
        self.assertEqual(commands, [
            'python dm/host/tests/run_kh2_sync.py --out "$out/sync" 2>&1 | tee "$out/sync.log"',
            'DM_SAVE_TEST_OUT="$out/fs-plain" python dm/host/tests/run_save_review.py 2>&1 | tee "$out/fs-plain.log"',
            'DM_SAVE_TEST_OUT="$out/fs-asan-ubsan" python dm/host/tests/run_save_review.py --sanitize 2>&1 | tee "$out/fs-asan-ubsan.log"',
            'DM_SAVE_PATH_OUT="$out/path-plain" python dm/host/tests/run_save_path_resolution.py 2>&1 | tee "$out/path-plain.log"',
            'DM_SAVE_PATH_OUT="$out/path-asan-ubsan" python dm/host/tests/run_save_path_resolution.py --sanitize 2>&1 | tee "$out/path-asan-ubsan.log"',
        ])
        # No parallel make, historical baseline, proprietary inputs or GPU replay.
        self.assertNotRegex(shell, r'(?<![>\d])&(?![>&])')
        self.assertNotRegex(job, r'--baseline|--nso|--elf|git (?:show|fetch)|run_input_replay|dmhost|/Users/|make -C')
        self.assertIn('if: always()', job)
        for suffix in ('json', 'log'):
            self.assertIn('${{ runner.temp }}/cpu-save-tests.*/**/*.' + suffix, job)
        self.assertIn('retention-days: 7', job)

        # This new job supplements, rather than replaces, existing coverage.
        self.assertIn('permissions:\n  contents: read\n', workflow)
        for name in ('host-tests', 'tool-tests', 'build', 'ios-build'):
            self.assertIn(name, jobs)
        self.assertIn('tsan memory-tsan', jobs['host-tests'])
        self.assertIn('python -m unittest -v "$f"', jobs['tool-tests'])
        self.assertIn('010015100B514000 0100535012974000 010014E00DB56000', jobs['build'])
        self.assertIn('compile_check.py', jobs['build'])
        self.assertIn('build_smoke.py --output "$RUNNER_TEMP/ios-smoke"', jobs['ios-build'])


if __name__ == '__main__':
    unittest.main()
