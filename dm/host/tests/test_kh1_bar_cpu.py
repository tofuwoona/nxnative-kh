#!/usr/bin/env python3
"""AArch64 CPU equivalence for both KH1 owned-bar adapters."""
import os
from pathlib import Path
import random
import struct
import unittest
from test_kh1_bar import bar, INPUT
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as r

BASE=0x10000000
SCR=0x08000000
SP=SCR+0xf000
OUT=0x09000000
C1=OUT+0x100
C2=C1+0x100
X=[getattr(r,f'UC_ARM64_REG_X{i}') for i in range(31)]
Q=[getattr(r,f'UC_ARM64_REG_Q{i}') for i in range(32)]
STATE=X+Q+[r.UC_ARM64_REG_SP,r.UC_ARM64_REG_PC,r.UC_ARM64_REG_NZCV,r.UC_ARM64_REG_FPCR,r.UC_ARM64_REG_FPSR]


def run(image,site,bits,seed):
    mapped=(len(image)+0x3fff)&~0x3fff
    u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);u.mem_map(BASE,mapped);u.mem_write(BASE,image)
    u.mem_map(SCR,0x10000);u.mem_map(OUT,0x10000)
    rng=random.Random(seed);vals=[rng.getrandbits(64) for _ in X]+[rng.getrandbits(128) for _ in Q]
    for reg,val in zip(X+Q,vals):u.reg_write(reg,val)
    u.reg_write(r.UC_ARM64_REG_SP,SP);u.reg_write(r.UC_ARM64_REG_NZCV,(seed&15)<<28)
    u.reg_write(r.UC_ARM64_REG_FPCR,0x400000 if seed&1 else 0);u.reg_write(r.UC_ARM64_REG_FPSR,0x8000000 if seed&2 else 0)
    payload=bytes(rng.getrandbits(8) for _ in range(0x50));corners=struct.pack('<6f',*[rng.uniform(-4096,4096) for _ in range(6)])
    u.mem_write(OUT,payload);u.mem_write(C1,corners[:12]);u.mem_write(C2,corners[12:]);u.mem_write(BASE+bar.FLAG,struct.pack('<I',bits))
    u.reg_write(r.UC_ARM64_REG_X0,OUT);u.reg_write(r.UC_ARM64_REG_X1,0x80000000)
    u.reg_write(r.UC_ARM64_REG_X2,C1);u.reg_write(r.UC_ARM64_REG_X3,C2);u.reg_write(r.UC_ARM64_REG_X4,0)
    stop=BASE+site+4
    def hook(uc,address,size,data):
        if address==BASE+0x1bca0:uc.reg_write(r.UC_ARM64_REG_PC,uc.reg_read(r.UC_ARM64_REG_LR))
        elif address==stop:uc.emu_stop()
    u.hook_add(UC_HOOK_CODE,hook);u.emu_start(BASE+site,0,count=3000)
    return [u.reg_read(x) for x in STATE],bytes(u.mem_read(OUT,0x50))


class Kh1BarCpuTests(unittest.TestCase):
    def test_eight_calls_preserve_cpu_and_collapse_only_x(self):
        self.assertIsNotNone(bar)
        original=(INPUT/'main.patched.bin').read_bytes();patched=bar.patch_image(original)
        checks=0
        for site in bar.QUAD_CALLS:
            for seed in range(8):
                with self.subTest(site=hex(site),seed=seed):
                    original_state,original_out=run(original,site,0,seed)
                    off_state,off_out=run(patched,site,0,seed)
                    self.assertEqual(off_state,original_state);self.assertEqual(off_out,original_out)
                    on_state,on_out=run(patched,site,1,seed)
                    self.assertEqual(on_state,original_state)
                    expected=bytearray(original_out)
                    for off in (20,40,60):expected[off:off+4]=expected[:4]
                    self.assertEqual(on_out,bytes(expected));checks+=2
        print(f'KH1 AArch64 adapters: {checks} exact CPU/state/output comparisons')


if __name__=='__main__':unittest.main()
