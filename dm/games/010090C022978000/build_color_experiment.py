#!/usr/bin/env python3
"""Rebuild the KH2 experimental color shader, outside the normal pipeline.

Requires the exact captured SPIR-V and generated MSL used in the local build.
This is a reproducibility aid, not a generally safe shader transformation.
Usage: python3 build_color_experiment.py <spirv-dir> <mac-out> [--ios <ios-out>]
"""
import hashlib
import importlib.util
from pathlib import Path
import re
import sys

KEY = "80a74ee192e6490b"
EXPECTED_MSL = "0e92d38e7f8fae07f56a8fedb0ce4b2393ef208f6e9e908b576100cb7d1f8b25"
ROOT = Path(__file__).resolve().parents[3]


def transform(shader):
    """Apply only to the exact original generated source, failing closed."""
    if hashlib.sha256(shader.strip().encode()).hexdigest() != EXPECTED_MSL:
        raise ValueError("generated MSL differs from the validated KH2 input")
    for name in ("_195", "_326", "_457"):
        pattern = rf"\s*spvUnsafeArray<float3x3, 11> {name}\s*=\s*.*?;\n"
        shader, count = re.subn(pattern, "", shader, flags=re.DOTALL)
        if count != 1:
            raise ValueError(f"expected exactly one {name} declaration")
    patterns = {
        "_458": r"spvUnsafeArray<spvUnsafeArray<float3x3, 11>, 3> _458\s*=\s*(.*?);\n",
        "_471": r"spvUnsafeArray<float3x3, 3> _471\s*=\s*(.*?);\n",
    }
    values = {}
    for name, pattern in patterns.items():
        matches = list(re.finditer(pattern, shader, flags=re.DOTALL))
        if len(matches) != 1:
            raise ValueError(f"expected exactly one {name} declaration")
        values[name] = matches[0].group(1)
        shader = re.sub(pattern, "", shader, count=1, flags=re.DOTALL)
    declarations = f"""
constant spvUnsafeArray<spvUnsafeArray<float3x3, 11>, 3> _458_global = {values['_458']};
constant spvUnsafeArray<float3x3, 3> _471_global = {values['_471']};
"""
    shader, count = re.subn(r"fragment main0_out main0\(", declarations + "\nfragment main0_out main0(", shader)
    if count != 1:
        raise ValueError("fragment entry not found or not unique")
    shader = shader.replace("_458[", "_458_global[").replace("_471[", "_471_global[")
    return shader.strip()


def main():
    if len(sys.argv) not in (3, 5) or (len(sys.argv) == 5 and sys.argv[3] != "--ios"):
        raise SystemExit(__doc__)
    compiler = ROOT / "dm/gfx/tools/vk_shaders.py"
    spec = importlib.util.spec_from_file_location("vk_shaders", compiler)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load shader compiler: {compiler}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    original = getattr(mod, "one")
    hits = []

    def wrap(*args, **kwargs):
        result = original(*args, **kwargs)
        if isinstance(result, tuple) and result and result[0] == KEY:
            msl = Path(result[3][0])
            shader = msl.read_text()
            symbol = f"vk_{KEY}"
            if symbol not in shader:
                raise ValueError("target function symbol not found")
            transformed = transform(shader.replace(symbol, "main0"))
            msl.write_text(transformed.replace("main0", symbol))
            hits.append(KEY)
        return result

    setattr(mod, "one", wrap)
    sys.argv = [str(compiler), *sys.argv[1:]]
    mod.main()
    if hits != [KEY]:
        raise SystemExit(f"expected one transformed shader, found {len(hits)}")
    print(f"KH2 experimental transform applied once: {KEY}")


if __name__ == "__main__":
    main()
