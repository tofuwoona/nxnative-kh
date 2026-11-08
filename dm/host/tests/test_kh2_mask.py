#!/usr/bin/env python3
"""CPU execution of emitted AArch64; no game, GPU, Metal, or device."""
import importlib.util
import os
from pathlib import Path
import random
import struct
import unittest

ROOT = Path(__file__).resolve().parents[3]
INPUT_ENV = os.environ.get('KH2_MASK_INPUT')
if not INPUT_ENV or not (Path(INPUT_ENV)/'main.patched.bin').is_file():
    raise unittest.SkipTest('set KH2_MASK_INPUT to the private reconstructed-module directory')
INPUT = Path(INPUT_ENV)
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_MEM_WRITE
from unicorn import arm64_const as r
SPEC = importlib.util.spec_from_file_location('mask', ROOT/'dm/tools/kh2_mask_patch.py')
mask = None
if SPEC and Path(SPEC.origin).exists():
    mask = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(mask)

class MaskTests(unittest.TestCase):
    def test_reject_bad_input_and_branch_ranges(self):
        self.assertIsNotNone(mask)
        original=(INPUT/'main.patched.bin').read_bytes()
        bad=bytearray(original);bad[0x100]^=1
        for data in (b'',original[:-1],original+bytes(4),bytes(bad),mask.patch_image(original)):
            with self.assertRaises(ValueError):mask.patch_image(data)
        for pc,target in ((0,1),(0,1<<27),(1<<27,0-4),(2,4)):
            with self.assertRaises(ValueError):mask.branch(pc,target)

    def test_package_exact_inputs_and_preservation(self):
        self.assertTrue(hasattr(mask,'patch_directory'),'directory adapter missing')
        import tempfile
        import hashlib
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as td:
            dst=Path(td)/'out'
            mask.patch_directory(INPUT,dst)
            for file in INPUT.iterdir():
                if file.name!='main.patched.bin':self.assertEqual(file.read_bytes(),(dst/file.name).read_bytes())
            import json
            receipt=json.loads((dst/'mask-manifest.json').read_text())
            for name,item in receipt['outputs'].items():
                self.assertEqual(hashlib.sha256((dst/name).read_bytes()).hexdigest(),item['sha256'])
            with self.assertRaises(ValueError):mask.patch_directory(dst,Path(td)/'twice')
            self.assertFalse((Path(td)/'twice').exists())
            import shutil
            bad=Path(td)/'bad';shutil.copytree(INPUT,bad)
            (bad/'main.fixups.tsv').write_text('# KEY_PAGE_OFF\t0x0\n')
            with self.assertRaises(ValueError):mask.patch_directory(bad,Path(td)/'reject')
            self.assertFalse((Path(td)/'reject').exists())

    def test_cpu_both_entries_off_on(self):
        self.assertIsNotNone(mask, 'offline conditional mask adapter is not implemented')
        original = (INPUT/'main.patched.bin').read_bytes()
        image = mask.patch_image(original)
        self.assertEqual(image[0x2d30100:0x2d30104], bytes(4))
        # Only the eight owned BL words may differ; both producers are intact.
        restored = bytearray(image[:len(original)])
        for entry in mask.QUAD_CALLS: restored[entry:entry+4] = original[entry:entry+4]
        self.assertEqual(restored, original)
        for base in (0x10000000, 0x130004000):
            for entry in (0x37760, 0x4422c):
                for enabled in (0, 1):
                    for seed in range(8):
                        with self.subTest(base=base, entry=entry, enabled=enabled, seed=seed):
                            u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
                            u.mem_map(base, len(image)); u.mem_write(base, image)
                            stack = 0x8000000; u.mem_map(stack, 0x4000)
                            sp = stack+0x3000; ret = base+0x1000
                            rng = random.Random(seed)
                            regs = [getattr(r, f'UC_ARM64_REG_X{i}') for i in range(31)]
                            qs = [getattr(r, f'UC_ARM64_REG_Q{i}') for i in range(32)]
                            vals = [rng.getrandbits(64) for _ in regs]; vals[30] = ret
                            qvals = [rng.getrandbits(128) for _ in qs]
                            for reg,val in zip(regs+qs, vals+qvals): u.reg_write(reg,val)
                            nzcv = (seed*2+1)<<28
                            u.reg_write(r.UC_ARM64_REG_NZCV,nzcv)
                            u.reg_write(r.UC_ARM64_REG_FPCR,0x400000)
                            u.reg_write(r.UC_ARM64_REG_FPSR,0x8000000)
                            u.reg_write(r.UC_ARM64_REG_SP,sp)
                            u.mem_write(base+0x2d30100,struct.pack('<I',enabled))
                            writes=[]
                            u.hook_add(UC_HOOK_MEM_WRITE,lambda uc,access,a,size,value,data: writes.append((a,size)))
                            end=base+entry+4
                            u.emu_start(base+entry,end,count=32)
                            self.assertEqual(u.reg_read(r.UC_ARM64_REG_PC),end)
                            self.assertEqual([u.reg_read(x) for x in regs+qs],vals+qvals)
                            self.assertEqual(u.reg_read(r.UC_ARM64_REG_SP),sp-0xa0)
                            self.assertEqual(u.reg_read(r.UC_ARM64_REG_NZCV),nzcv)
                            self.assertEqual(u.reg_read(r.UC_ARM64_REG_FPCR),0x400000)
                            self.assertEqual(u.reg_read(r.UC_ARM64_REG_FPSR),0x8000000)
                            self.assertEqual(writes,[])
        print('AArch64: 64 entry/base/flag/register-state cases; original prologue always executes')

if __name__ == '__main__': unittest.main()
