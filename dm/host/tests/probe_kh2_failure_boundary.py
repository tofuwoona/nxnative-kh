#!/usr/bin/env python3
"""Read-only, arm64 macOS CPU probe of two pinned KH2 failure-boundary slices.

Requires the operator's original ELF (never checked in). Extracted assembly,
executables, and results go ONLY to --out outside the checkout. Calls to the
inverse transform / Commit are instrumented seams, NOT game/FS implementations.
The inverse seam executes the original signed-length guard; its positive body
is only a reachability counter. No guest transform, PNG or save is synthesized.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
from run_kh2_sync import command_ok

ELF_SHA = "53baff858787505aa5714a982f38611630403cf560be59f889ddeba8b5ee1484"
PATCHED_SHA = "fd307fc9be644d72e11a546401e0b808171793547d06ceb0b4ca7537b82efb2c"
FS_SHA = "32e36ff48977f8e96ef2e65a2174d6960e5a53626fcb521ead5db8e77c3d06f9"
# All decision/data words of the examined serializer tail, plus inverse guard
# and writer-close tail. Only BLs are redirected; commit's literal is unused.
WORDS = {
    0x2dba4: 0x34000060, 0x2dba8: 0xb9406e62, 0x2dbac: 0x14000003,
    0x2dbb0: 0x12800002, 0x2dbb4: 0xb9006e62, 0x2dbb8: 0xf9402261,
    0x2dbbc: 0xaa1303e0, 0x2dbc0: 0x94000114, 0x2dbc4: 0xd0001f40,
    0x2dbc8: 0x912a0c00, 0x2dbcc: 0x940f4979, 0x2dbd0: 0x3901a27f,
    0x2dbd4: 0xb9406e60, 0x2dbd8: 0xa9544ff4, 0x2dbdc: 0xa95357f6,
    0x2dbe0: 0xa9525ffc, 0x2dbe4: 0xa9517bfd, 0x2dbe8: 0x910543ff,
    0x2dbec: 0xd65f03c0, 0x2e010: 0x7100445f, 0x2e014: 0x5400082b,
    0x2e118: 0xd65f03c0, 0x4103c: 0xaa1303e0, 0x41040: 0x940ef820,
    0x41044: 0x394002e0,
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def elf_image(data):
    if sha(data) != ELF_SHA:
        raise ValueError("original ELF SHA mismatch: refusing native probe")
    h = struct.unpack_from("<16sHHIQQQIHHHHHH", data)
    if h[0][:6] != b"\x7fELF\x02\x01" or h[2] != 183:
        raise ValueError("requires little-endian AArch64 ELF64")
    segs = [struct.unpack_from("<IIQQQQQQ", data, h[5] + i*h[9])
            for i in range(h[10])]
    loads = [s for s in segs if s[0] == 1]
    image = bytearray(max(s[3] + s[5] for s in loads))
    for s in loads:
        image[s[3]:s[3]+s[5]] = data[s[2]:s[2]+s[5]]
    return image


def validate_words(image):
    for off, expected in WORDS.items():
        got = struct.unpack_from("<I", image, off)[0]
        if got != expected:
            raise ValueError(f"original word mismatch at {off:#x}: {got:#x} != {expected:#x}")


def assembly(image):
    def word(off):
        return f"    .long 0x{struct.unpack_from('<I', image, off)[0]:08x} // main+{off:x}\n"
    s = ".text\n.p2align 2\n.globl _probe_serializer_tail\n_probe_serializer_tail:\n"
    # The original serializer frame, preserving every callee-saved GPR it uses.
    for off in range(0x2da24, 0x2da3c, 4):
        s += word(off)
    s += "    mov x19, x0\n    mov w0, w1\n"
    for off in range(0x2dba4, 0x2dbf0, 4):
        if off == 0x2dbc0:
            s += "    bl Lprobe_inverse_entry // redirected original BL\n"
        elif off in (0x2dbc4, 0x2dbc8):
            s += "    nop // omitted unused Commit path literal; seam takes no args\n"
        elif off == 0x2dbcc:
            s += "    bl _probe_commit // result injected at original call boundary\n"
        else:
            s += word(off)
    s += """
// This is NOT the original inverse transform. Observe its argument, then execute
// its exact signed-length guard. The positive body only records reachability.
Lprobe_inverse_entry:
    stp x29, x30, [sp, #-32]!
    mov x29, sp
    str w2, [sp, #16]
    mov w0, w2
    bl _probe_note_inverse
    ldr w2, [sp, #16]
"""
    s += word(0x2e010)
    s += "    b.lt Lprobe_inverse_return // relocated original main+2e014 target 2e118\n"
    s += "    bl _probe_note_inverse_body_reached\nLprobe_inverse_return:\n"
    s += "    ldp x29, x30, [sp], #32\n" + word(0x2e118)
    s += """
.p2align 2
.globl _probe_writer_close
_probe_writer_close:
    stp x29, x30, [sp, #-32]!
    stp x19, x23, [sp, #16]
    mov x29, sp
    mov x19, x0
    mov x23, x1
"""
    s += word(0x4103c)
    s += "    bl _probe_fclose // records the result of real host fclose\n"
    s += word(0x41044)
    s += "    ldp x19, x23, [sp, #16]\n    ldp x29, x30, [sp], #32\n    ret\n"
    return s


def run(args):
    repo = Path(__file__).resolve().parents[3]
    out = args.out.resolve()
    if out == repo or repo in out.parents:
        raise ValueError("--out must be outside the checkout")
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("native instruction probe requires arm64 macOS")
    image = elf_image(args.elf.read_bytes())
    validate_words(image)
    fs = repo / "dm/host/hle_fs.c"
    fs_bytes = fs.read_bytes()
    # The parent explicitly permitted one logical-error adapter. Continue to
    # assert every pre-existing filesystem byte, excluding only its delimited
    # additive export; the original failure slices themselves are unchanged.
    reviewed = fs_bytes
    marker = b'// Narrow logical-encoder rejection adapter.'
    if marker in reviewed:
        start = reviewed.index(marker)
        end = reviewed.index(b'// A mount list is atomic only', start)
        reviewed = reviewed[:start] + reviewed[end:]
    if sha(reviewed) != FS_SHA:
        raise ValueError("reviewed filesystem bytes outside narrow adapter mismatch")
    patched_verified = False
    if args.patched:
        patched = args.patched.read_bytes()
        if sha(patched) != PATCHED_SHA:
            raise ValueError("baseline patched image SHA mismatch")
        validate_words(patched)
        patched_verified = True
    # Fail-closed controls on the actual validation functions, no native execution.
    corrupted = bytearray(args.elf.read_bytes())
    corrupted[-1] ^= 1
    try:
        elf_image(corrupted)
    except ValueError:
        pass
    else:
        raise AssertionError("wrong-artifact digest was accepted")
    corrupted = bytearray(image)
    corrupted[0x2dbb4] ^= 1
    try:
        validate_words(corrupted)
    except ValueError:
        pass
    else:
        raise AssertionError("wrong original word was accepted")
    out.mkdir(parents=True, exist_ok=False)
    asm = out / "original-boundary-slices.S"
    asm.write_text(assembly(image))
    fixture = Path(__file__).with_name("t_kh2_failure_boundary.c")
    cases = [("png-success", 0), ("commit-failure", 0),
             ("png-failure-observed", 0), ("require-png-recovery", 1),
             ("close-failure-observed", 0), ("require-close-error", 1)]
    manifest = {"kind": "CPU mechanism evidence; NOT gameplay or a repair",
                "original_elf_sha256": ELF_SHA, "reviewed_fs_sha256": FS_SHA,
                "current_fs_sha256": sha(fs_bytes),
                "preexisting_fs_bytes_verified": True,
                "baseline_patched_sha256": PATCHED_SHA if patched_verified else None,
                "validated_original_words": len(WORDS),
                "negative_controls": ["wrong ELF digest rejected", "wrong instruction rejected"],
                "runs": []}
    for mode, flags in [("plain", []), ("asan-ubsan", ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"])]:
        exe = out / mode
        cmd = ["clang", "-Wall", "-Wextra", "-Werror", "-g", "-O1", *flags,
               str(fixture), str(asm), "-o", str(exe)]
        build = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (out / f"{mode}-build.log").write_text(build.stdout)
        if build.returncode:
            raise RuntimeError(build.stdout)
        for case, expected in cases:
            cp = subprocess.run([str(exe), case], text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0", "UBSAN_OPTIONS": "halt_on_error=1"})
            (out / f"{mode}-{case}.log").write_text(cp.stdout)
            print(f"{mode}/{case}: actual={cp.returncode} expected={expected}\n{cp.stdout}", end="")
            manifest["runs"].append({"mode": mode, "case": case, "expected_exit": expected,
                                     "actual_exit": cp.returncode, "output": cp.stdout})
    manifest["outcomes_match"] = all(command_ok(r["actual_exit"], r["output"], r["expected_exit"]) for r in manifest["runs"])
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if not manifest["outcomes_match"]:
        return 1
    print("PROBE VERIFIED: expected RED retained; no production repair implemented")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--patched", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    try:
        return run(parser.parse_args())
    except (ValueError, RuntimeError) as e:
        print(f"PROBE ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
