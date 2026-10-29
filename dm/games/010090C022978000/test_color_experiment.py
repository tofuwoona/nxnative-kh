#!/usr/bin/env python3
"""Synthetic tests for the KH2-only source-rewrite guard (no game assets)."""
import hashlib
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).with_name("build_color_experiment.py")
SPEC = importlib.util.spec_from_file_location("kh2_color", PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

SYNTHETIC = """\
spvUnsafeArray<float3x3, 11> _195 = { a };
spvUnsafeArray<float3x3, 11> _326 = { b };
spvUnsafeArray<float3x3, 11> _457 = { c };
spvUnsafeArray<spvUnsafeArray<float3x3, 11>, 3> _458 = { matrix };
spvUnsafeArray<float3x3, 3> _471 = { matrix };
fragment main0_out main0() { return _458[0] + _471[0]; }
"""


class ColorTransformTest(unittest.TestCase):
    def test_unknown_source_is_refused(self):
        with self.assertRaisesRegex(ValueError, "differs"):
            MODULE.transform(SYNTHETIC)

    def test_exact_source_is_transformed(self):
        previous = MODULE.EXPECTED_MSL
        setattr(MODULE, "EXPECTED_MSL", hashlib.sha256(SYNTHETIC.strip().encode()).hexdigest())
        try:
            result = MODULE.transform(SYNTHETIC)
        finally:
            setattr(MODULE, "EXPECTED_MSL", previous)
        self.assertNotIn("_195", result)
        self.assertNotIn("_326", result)
        self.assertNotIn("_457", result)
        self.assertIn("constant spvUnsafeArray<spvUnsafeArray<float3x3, 11>, 3> _458_global", result)
        self.assertIn("constant spvUnsafeArray<float3x3, 3> _471_global", result)
        self.assertIn("return _458_global[0] + _471_global[0]", result)

    def test_bad_structure_is_refused_even_with_matching_digest(self):
        source = SYNTHETIC.replace("fragment main0_out main0(", "fragment other(")
        previous = MODULE.EXPECTED_MSL
        setattr(MODULE, "EXPECTED_MSL", hashlib.sha256(source.strip().encode()).hexdigest())
        try:
            with self.assertRaisesRegex(ValueError, "fragment entry"):
                MODULE.transform(source)
        finally:
            setattr(MODULE, "EXPECTED_MSL", previous)


if __name__ == "__main__":
    unittest.main()
