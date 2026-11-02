"""A real UBSan diagnostic must fail even with the expected abort exit."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent

class ResultPolicy(unittest.TestCase):
    def test_expected_abort_does_not_hide_ubsan(self):
        spec=importlib.util.spec_from_file_location('runner',HERE/'run_kh2_sync.py')
        assert spec and spec.loader
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            source=out/'bad.c';exe=out/'bad'
            source.write_text('#include <stdlib.h>\nint main(void){ volatile int n=32; volatile int x=1<<n; (void)x; abort(); }\n')
            subprocess.run(['clang','-O1','-fsanitize=undefined',str(source),'-o',str(exe)],check=True)
            cp=subprocess.run([str(exe)],text=True,capture_output=True,
                              env={**os.environ,'UBSAN_OPTIONS':'halt_on_error=0'})
            self.assertEqual(cp.returncode,-6)
            self.assertIn('runtime error:',cp.stderr)
            self.assertFalse(runner.command_ok(cp.returncode,cp.stdout+cp.stderr,expected=-6))
            self.assertTrue(runner.command_ok(-6,'ordinary expected fail-closed abort',expected=-6))

if __name__=='__main__':unittest.main()
