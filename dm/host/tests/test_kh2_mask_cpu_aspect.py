#!/usr/bin/env python3
"""Separate experimental CPU-aspect branch, original w8/flags preserved."""
import random
import struct
import unittest
from test_kh2_mask import mask, INPUT
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as r

class CPUAspectTests(unittest.TestCase):
    def test_original_cbz_and_separate_flag(self):
        self.assertTrue(hasattr(mask,'CPU_ENTRY'),'separate CPU-aspect redirect missing')
        original=(INPUT/'main.patched.bin').read_bytes()
        image=mask.patch_image(original,cpu_aspect=True)
        plain=mask.patch_image(original)
        self.assertEqual(plain[0x21938:0x2193c],bytes.fromhex('c8000034'))
        restored=bytearray(image[:len(original)])
        for entry in (*mask.QUAD_CALLS,0x21938):restored[entry:entry+4]=original[entry:entry+4]
        self.assertEqual(restored,original)
        cases=0
        for base in (0x10000000,0x130004000):
            for bits in range(4):
                for x8 in (0,1,0xffffffff,0x100000000):
                    for entry in (0x37760,0x4422c,0x21938):
                        u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);u.mem_map(base,len(image));u.mem_write(base,image)
                        stack=0x8000000;u.mem_map(stack,0x4000);sp=stack+0x3000
                        regs=[getattr(r,f'UC_ARM64_REG_X{i}') for i in range(31)]
                        qs=[getattr(r,f'UC_ARM64_REG_Q{i}') for i in range(32)]
                        rng=random.Random(cases);vals=[rng.getrandbits(64) for _ in regs];qvals=[rng.getrandbits(128) for _ in qs]
                        vals[8]=x8;vals[30]=base+0x1000
                        for rr,v in zip(regs+qs,vals+qvals):u.reg_write(rr,v)
                        nzcv=(cases%16)<<28;u.reg_write(r.UC_ARM64_REG_NZCV,nzcv);u.reg_write(r.UC_ARM64_REG_SP,sp)
                        u.reg_write(r.UC_ARM64_REG_FPCR,0x400000);u.reg_write(r.UC_ARM64_REG_FPSR,0x8000000)
                        u.mem_write(base+0x2d30100,struct.pack('<I',bits))
                        cpu=entry==0x21938
                        end=base+(0x2193c if bits&2 or x8&0xffffffff else 0x21950) if cpu else base+entry+4
                        stops=(base+0x2193c,base+0x21950) if cpu else (vals[30],base+entry+4)
                        def stop(uc,addr,size,data):
                            if addr in stops:uc.emu_stop()
                        u.hook_add(UC_HOOK_CODE,stop)
                        try:u.emu_start(base+entry,0,count=40)
                        except Exception as exc:self.fail(f'entry={entry:x} bits={bits} x8={x8:x} pc={u.reg_read(r.UC_ARM64_REG_PC):x}: {exc}')
                        self.assertEqual(u.reg_read(r.UC_ARM64_REG_PC),end)
                        self.assertEqual([u.reg_read(rr) for rr in regs+qs],vals+qvals)
                        self.assertEqual(u.reg_read(r.UC_ARM64_REG_NZCV),nzcv)
                        self.assertEqual(u.reg_read(r.UC_ARM64_REG_FPCR),0x400000)
                        self.assertEqual(u.reg_read(r.UC_ARM64_REG_FPSR),0x8000000)
                        self.assertEqual(u.reg_read(r.UC_ARM64_REG_SP),sp if cpu else sp-0xa0)
                        cases+=1
        print(f'AArch64 CPU-aspect/mask isolation: {cases} cases')

if __name__=='__main__':unittest.main()
