#!/usr/bin/env python3
"""Exact image CPU-only execution; no renderer, GPU, game or device.

Warm renderer fixtures use the actual b490/b5b0/b520 getters, not call mocks.
Compare full helper state against the authentic original chosen branch.
"""
import itertools
import random
import struct
import unittest
from test_kh2_mask import mask, INPUT
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn import arm64_const as r

REGS = [getattr(r, f'UC_ARM64_REG_X{i}') for i in range(31)]
QS = [getattr(r, f'UC_ARM64_REG_Q{i}') for i in range(32)]
STATE = REGS + QS + [r.UC_ARM64_REG_SP, r.UC_ARM64_REG_NZCV,
                     r.UC_ARM64_REG_FPCR, r.UC_ARM64_REG_FPSR]
BASES = (0x10000000, 0x130004000)
TITLE = 0xb5a31c
MEDIA = 0xccc258
MEDIA_LR = 0x1868ec
SP = 0x8003000


def machine(image, base, seed=0):
    u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    u.mem_map(base, len(image)); u.mem_write(base, image)
    u.mem_map(0x8000000, 0x4000)
    rng = random.Random(seed)
    for reg in REGS: u.reg_write(reg, rng.getrandbits(64))
    for reg in QS: u.reg_write(reg, rng.getrandbits(128))
    u.reg_write(r.UC_ARM64_REG_SP, SP)
    u.reg_write(r.UC_ARM64_REG_NZCV, (seed % 16) << 28)
    u.reg_write(r.UC_ARM64_REG_FPCR, 0)
    u.reg_write(r.UC_ARM64_REG_FPSR, 0)
    writes = []
    u.hook_add(UC_HOOK_MEM_WRITE,
               lambda uc, access, a, n, v, data: writes.append((a, n)))
    return u, writes


def helper(image, base, bits, original_global, caller, constructor=False):
    u, writes = machine(image, base, seed=7)
    u.mem_write(base + mask.FLAG, struct.pack('<I', bits))
    u.mem_write(base + 0xa62b50, b'\x01')  # actual getter guard: already initialized
    u.mem_write(base + 0xa62b58, bytes([original_global]))
    u.mem_write(base + 0x94a7b0, struct.pack('<2f', 1704, 786))
    u.mem_write(base + 0x94a7e0, struct.pack('<2f', 640, 480))
    u.mem_write(base + 0x94a7d0, struct.pack('<2f', 512, 416))
    u.reg_write(r.UC_ARM64_REG_LR, base + caller)
    if constructor:
        u.reg_write(r.UC_ARM64_REG_X23, base + 0xa6b1e0)
        u.mem_write(base + 0xa6b1e0, struct.pack('<Q', base + 0xccc300))
    start, stop = (0x1868e8, 0x186924) if constructor else (0x21910, caller)
    u.emu_start(base + start, base + stop, count=300)
    assert u.reg_read(r.UC_ARM64_REG_PC) == base + stop
    assert all(SP-0x50 <= a and a+n <= SP or
               constructor and base+0xccc390 <= a and a+n <= base+0xccc398
               for a,n in writes), writes
    return u


class MediaHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (INPUT/'main.patched.bin').read_bytes()
        cls.image = mask.patch_image(cls.original, cpu_aspect=True)

    def test_full_helper_media_caller_keeps_fixed_width(self):
        # This catches using current LR (2192c) instead of the caller LR saved
        # by the real prologue at SP+16 (SP+32 after the thunk's 16-byte spill).
        cases = 0
        for base, bits, global_bit, caller in itertools.product(
                BASES, range(4), (0, 1, 255), (MEDIA_LR, MEDIA_LR+4, 0x12340)):
            with self.subTest(base=base, bits=bits, global_bit=global_bit, caller=caller):
                selected = (0 if caller == MEDIA_LR else 1) if bits & 2 else global_bit
                expected = helper(self.original, base, 0, selected, caller)
                actual = helper(self.image, base, bits, global_bit, caller)
                self.assertEqual([actual.reg_read(x) for x in STATE],
                                 [expected.reg_read(x) for x in STATE])
                cases += 1
        print(f'Full original/emitted helper state comparisons: {cases}')

    def test_cpu_thunk_saved_caller_and_all_nzcv_preserved(self):
        cases = 0
        for base in BASES:
            u, writes = machine(self.image, base)
            initial = [u.reg_read(x) for x in REGS + QS]
            stops = (base+0x2193c, base+0x21950)
            u.hook_add(UC_HOOK_CODE, lambda uc, a, n, data:
                       uc.emu_stop() if a in stops else None)
            for bits, x8, caller, flags in itertools.product(
                    range(4), (0, 1, 0xffffffff, 0x100000000),
                    (MEDIA_LR, MEDIA_LR+4, MEDIA_LR+0x100000000), range(16)):
                with self.subTest(base=base, bits=bits, x8=x8, caller=caller, flags=flags):
                    before = initial.copy()
                    before[8] = x8
                    # A tempting live-LR compare must fail: invert its identity.
                    before[30] = base + (0x2192c if caller == MEDIA_LR else MEDIA_LR)
                    for reg, value in zip(REGS + QS, before): u.reg_write(reg, value)
                    u.reg_write(r.UC_ARM64_REG_SP, SP)
                    u.reg_write(r.UC_ARM64_REG_NZCV, flags << 28)
                    u.reg_write(r.UC_ARM64_REG_FPCR, 0x400000)
                    u.reg_write(r.UC_ARM64_REG_FPSR, 0x8000000)
                    u.mem_write(SP+16, struct.pack('<Q', base+caller))
                    u.mem_write(base+mask.FLAG, struct.pack('<I', bits))
                    physical = caller != MEDIA_LR if bits & 2 else bool(x8 & 0xffffffff)
                    end = base + (0x2193c if physical else 0x21950)
                    writes.clear()
                    u.emu_start(base+0x21938, 0, count=40)
                    self.assertEqual(u.reg_read(r.UC_ARM64_REG_PC), end)
                    self.assertEqual([u.reg_read(x) for x in REGS + QS], before)
                    self.assertEqual(u.reg_read(r.UC_ARM64_REG_SP), SP)
                    self.assertEqual(u.reg_read(r.UC_ARM64_REG_NZCV), flags << 28)
                    self.assertEqual(u.reg_read(r.UC_ARM64_REG_FPCR), 0x400000)
                    self.assertEqual(u.reg_read(r.UC_ARM64_REG_FPSR), 0x8000000)
                    self.assertEqual(bytes(u.mem_read(SP+16, 8)), struct.pack('<Q', base+caller))
                    self.assertTrue(all(SP-16 <= a and a+n <= SP for a,n in writes))
                    cases += 1
        print(f'CPU thunk saved/live caller, w8 and all-NZCV cases: {cases}')

    def test_real_movie_constructor_destination(self):
        cases = 0
        for base, bits, global_bit in itertools.product(BASES, range(4), (0, 1, 255)):
            with self.subTest(base=base, bits=bits, global_bit=global_bit):
                u = helper(self.image, base, bits, global_bit, MEDIA_LR, constructor=True)
                width, height = struct.unpack('<2I', u.mem_read(base+0xccc390, 8))
                self.assertEqual((width, height),
                                 (570 if bits & 2 or not global_bit else 694, 348))
                cases += 1
        print(f'Actual movie BL/helper/width-store cases: {cases}')


class PeriodMaskTests(unittest.TestCase):
    def test_title_and_media_owned_periods_preserve_original_masks(self):
        # Replacement for the former whole-function bypass oracle: compare the
        # actual constructor and exact geometry, not just a branch destination.
        from test_kh2_mask_geometry import QuadFixture, SITES
        original = (INPUT/'main.patched.bin').read_bytes()
        cases = 0
        for cpu, base in itertools.product((False, True), BASES):
            fixture = QuadFixture(original, mask.patch_image(original, cpu_aspect=cpu), base)
            for site, bits, title, task, flags in itertools.product(
                    SITES, range(4) if cpu else range(2), (0, 1, 2, 3, 0xffffffff),
                    (0, 1, 0x100000000, 0xffffffffffffffff), range(16)):
                with self.subTest(cpu=cpu, base=base, site=site, bits=bits,
                                  title=title, task=task, nzcv=flags):
                    fixture.compare(self, site, bits, title, task, cases, flags)
                    cases += 1
        print(f'Authentic quad title/media/flags/full-state cases: {cases}')


if __name__ == '__main__': unittest.main()
