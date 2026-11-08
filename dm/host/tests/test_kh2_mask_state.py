#!/usr/bin/env python3
"""Authentic producer entry/setup regression using asynchronous phone snapshots.

No game/GPU/device. Execute the original warm entry and setup callees through
2fc20/3026c/bfe0, stopping after the original descriptor call. Only 30a08
(alpha/depth helper) is a stub. Snapshot addresses are relocated explicitly.
"""
import hashlib
import os
from pathlib import Path
import struct
import unittest
from test_kh2_mask import mask, INPUT

SNAPSHOT_ENV = os.environ.get('KH2_MASK_SNAPSHOTS')
if not SNAPSHOT_ENV or not Path(SNAPSHOT_ENV).is_dir():
    raise unittest.SkipTest('set KH2_MASK_SNAPSHOTS to the private captured-state directory')
SNAPSHOTS = Path(SNAPSHOT_ENV)
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as r
NAMES = ('before-pause-01','before-pause-02','after-camera','in-pause',
         'after-close-01','after-close-02')
R, S = 0x94a7a0, 0x5525b0
SP, STOP = 0x800f000, 0x8001000


def setup_path(image, base, name, entry, bits):
    u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    u.mem_map(base, len(image)); u.mem_write(base, image)
    u.mem_map(0x8000000, 0x10000)
    p = SNAPSHOTS/name
    u.mem_write(base+S, (p/'state.bin').read_bytes())
    u.mem_write(base+R+0x2a4, (p/'raw-mask.bin').read_bytes())
    u.mem_write(base+0xa62b50, (p/'init-flags.bin').read_bytes())
    # GOT relocation used by original setters; actual functions unmodified.
    u.mem_write(base+0x54ad48, struct.pack('<Q', base+S))
    # Non-equal dimensions select the genuine 37760 producer setup path.
    u.mem_write(base+R+8, struct.pack('<2f', 1704, 786))
    u.mem_write(base+R+0x30, struct.pack('<2f', 512, 416))
    u.mem_write(base+mask.FLAG, struct.pack('<I', bits))
    u.mem_write(base+mask.TITLE_STATE, bytes(4))
    u.mem_write(base+mask.MEDIA_TASK, bytes(8))
    visited=[]
    def hook(uc, a, n, data):
        if a == base+0x30a08:
            uc.reg_write(r.UC_ARM64_REG_PC, uc.reg_read(r.UC_ARM64_REG_LR))
        if a in (base+0x2fc20, base+0x3026c, base+0xbfe0): visited.append(a-base)
        if a in (base+0x377f0, base+0x44294, STOP): uc.emu_stop()
    u.hook_add(UC_HOOK_CODE, hook)
    def call(pc, x0=0):
        u.reg_write(r.UC_ARM64_REG_SP, SP)
        u.reg_write(r.UC_ARM64_REG_LR, STOP)
        u.reg_write(r.UC_ARM64_REG_X0, x0)
        u.emu_start(base+pc, STOP, count=10000)
    raw=lambda:struct.unpack('<I',u.mem_read(base+R+0x2a4,4))[0]
    observed=raw()
    call(0x3026c,base+S)
    assert u.reg_read(r.UC_ARM64_REG_PC)==STOP
    assert raw()==observed, (name, observed, raw())
    visited.clear()
    call(entry)
    result=raw()
    u.reg_write(r.UC_ARM64_REG_X20,base+R)
    u.reg_write(r.UC_ARM64_REG_X29,SP)
    u.emu_start(base+0x1e738,base+0x1e794,count=100)
    return result,u.reg_read(r.UC_ARM64_REG_W8),visited


class ProducerStateTests(unittest.TestCase):
    def test_original_setup_side_effect_survives_feature_on(self):
        original=(INPUT/'main.patched.bin').read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(),mask.INPUT_SHA)
        image=mask.patch_image(original,cpu_aspect=True)
        count=0
        for name in NAMES:
            for base in (0x10000000,0x130004000):
                for entry in (0x37760,0x4422c):
                    baseline=setup_path(original,base,name,entry,0)
                    self.assertEqual(baseline[:2],(0,15))
                    for bits in range(4):
                        with self.subTest(snapshot=name,base=base,entry=entry,bits=bits):
                            actual=setup_path(image,base,name,entry,bits)
                            self.assertEqual(actual,baseline,
                                'whole-producer bypass loses authentic color-disable reset')
                            count+=1
        print(f'Authentic captured-state producer entry/setup comparisons: {count}')

if __name__=='__main__': unittest.main()
