#!/usr/bin/env python3
"""Black-box tests of the real plain/gzip CLI, never a parser reimplementation."""
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / 'scripts/extract_input_trace.py'

def event(t, source=-1, buttons='0x1', axes='0,0,0,0'):
    return f'[dm] [input-trace] t_ns={t} source={source} buttons={buttons} axes={axes}\n'

class CaptureCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='capture-cli-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_cli(self, text, *args, compressed=False, output=None):
        src = self.root / ('raw.gz' if compressed else 'raw.log')
        src.write_bytes(gzip.compress(text.encode()) if compressed else text.encode())
        output = output or self.root / 'capture.log'
        p = subprocess.run([sys.executable, str(CLI), str(src), str(output), *args], capture_output=True, text=True)
        return p, output

    def test_mixed_plain_and_gzip(self):
        text = 'ordinary log\n[dm] [save-trace] commit=1\n' + event(100) + 'more logs\n' + event(101, 7, '0', '-32768,32767,0,-1')
        for compressed in (False, True):
            with self.subTest(compressed=compressed):
                p, out = self.run_cli(text, compressed=compressed)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(out.read_text(), event(100) + event(101, 7, '0', '-32768,32767,0,-1'))
                meta = json.loads(p.stdout)
                self.assertEqual(meta['count'], 2)
                self.assertEqual((meta['first_t_ns'], meta['last_t_ns']), (100, 101))
                self.assertEqual(meta['sources'], {'-1': 1, '7': 1})
                self.assertEqual(meta['compression'], 'gzip' if compressed else 'plain')
                self.assertEqual(len(meta['source_sha256']), 64)
                self.assertEqual(out.stat().st_mode & 0o777, 0o600)
                out.unlink()

    def test_rejects_malformed_axes_trailing_order_and_empty(self):
        bad = [
            event(102, axes='32768,0,0,0'), event(102, axes='-32769,0,0,0'),
            event(102, axes='4294967296,0,0,0'), event(102, axes='0,0,0'),
            event(102, axes='0,0,0,0 trailingdata'), event(102, axes='0,0,nan,0'),
            event(99), event(102, source=8), event(102, source=-2),
            event(-1), event(0), event(18446744073709551616),
            event(102, buttons='-1'), event(102, buttons='0x10000000000000000'),
            event(102).replace('[dm] ', ''), event(102).replace('\n', '\x00\n'),
            event(102).replace('source=-1', 'source=4294967295'),
        ]
        for compressed in (False, True):
            for record in bad:
                with self.subTest(record=record, compressed=compressed):
                    # Good prefix/suffix must not publish a partial valid file.
                    p, out = self.run_cli(event(100) + record + event(103), compressed=compressed)
                    self.assertNotEqual(p.returncode, 0)
                    self.assertFalse(out.exists())
                    self.assertFalse(p.stdout)
        for text in ('', 'ordinary log\n', '[dm] [input-trace] truncated\n'):
            p, out = self.run_cli(text)
            self.assertNotEqual(p.returncode, 0)
            self.assertFalse(out.exists())

    def test_exact_inclusive_window_and_ties(self):
        text = event(100) + event(101) + event(101, 0) + event(102) + event(103)
        p, out = self.run_cli(text, '--start-ns', '101', '--end-ns', '102')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(out.read_text(), event(101) + event(101, 0) + event(102))
        meta = json.loads(p.stdout)
        self.assertEqual((meta['count'], meta['total_source_events']), (3, 5))
        out.unlink()
        p, out = self.run_cli(text, '--start-ns', '101', '--end-ns', '101')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(out.read_text(), event(101) + event(101, 0))

    def test_window_does_not_hide_invalid_source_records(self):
        for text in (event(100) + event(101) + event(102, axes='broken'),
                     event(100) + event(101) + event(99)):
            p, out = self.run_cli(text, '--start-ns', '100', '--end-ns', '101')
            self.assertNotEqual(p.returncode, 0)
            self.assertFalse(out.exists())

    def test_invalid_window_and_two_hour_limit(self):
        for args in (('--start-ns','102','--end-ns','100'), ('--start-ns','0'),
                     ('--end-ns','-1'), ('--start-ns','18446744073709551616'),
                     ('--start-ns','101'), ('--end-ns','101'), ('--start-ns','999')):
            p, out = self.run_cli(event(100) + event(102), *args)
            self.assertNotEqual(p.returncode, 0)
            self.assertFalse(out.exists())
        p, out = self.run_cli(event(1) + event(7200000000002))
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse(out.exists())
        p, out = self.run_cli(event(1) + event(7200000000001))
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_new_only_including_dangling_and_source_symlinks(self):
        out = self.root / 'existing'
        out.write_text('do not overwrite')
        p, _ = self.run_cli(event(100), output=out)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(out.read_text(), 'do not overwrite')
        link = self.root / 'link'
        missing = self.root / 'missing'
        link.symlink_to(missing)
        p, _ = self.run_cli(event(100), output=link)
        self.assertNotEqual(p.returncode, 0)
        self.assertTrue(link.is_symlink())
        self.assertFalse(missing.exists())
        p, _ = self.run_cli(event(100), output=self.root / 'raw.log')
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual((self.root / 'raw.log').read_text(), event(100))

    def test_gzip_magic_missing_newline_all_sources_and_metadata_hashes(self):
        import hashlib
        text = ''.join(event(100 + i, i - 1, '0xffffffffffffffff', '-32768,32767,-1,0') for i in range(9)).rstrip('\n')
        p, out = self.run_cli(text, compressed=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        meta = json.loads(p.stdout)
        self.assertEqual(meta['sources'], {str(i): 1 for i in range(-1, 8)})
        self.assertEqual(meta['source_bytes'], (self.root / 'raw.gz').stat().st_size)
        self.assertEqual(meta['source_sha256'], hashlib.sha256((self.root / 'raw.gz').read_bytes()).hexdigest())
        self.assertEqual(meta['output_sha256'], hashlib.sha256(out.read_bytes()).hexdigest())
        out.unlink()
        # Detection must follow bytes, not .gz suffix.
        (self.root / 'raw.log').write_bytes((self.root / 'raw.gz').read_bytes())
        p = subprocess.run([sys.executable, str(CLI), str(self.root / 'raw.log'), str(out)], capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_corrupt_gzip_and_oversized_lines_do_not_publish(self):
        for data in (gzip.compress(event(100).encode())[:-8], b'\x1f\x8bnot-gzip', b'x' * (1024*1024+1)):
            src, out = self.root / 'broken.log', self.root / 'capture.log'
            src.write_bytes(data)
            p = subprocess.run([sys.executable, str(CLI), str(src), str(out)], capture_output=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertFalse(out.exists())

if __name__ == '__main__':
    unittest.main()
