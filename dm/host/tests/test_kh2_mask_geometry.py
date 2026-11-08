#!/usr/bin/env python3
"""Execute all eight authentic BL sites/2126c/b080 and emitted adapters.

Compare complete returned CPU state and every output byte. Stack spills are
bounded; only three additional owned vertex-X stores are allowed. No GPU.
"""
import itertools
import random
import struct
import unittest
from test_kh2_mask import mask, INPUT
from unicorn import UC_HOOK_CODE
from unicorn import arm64_const as r
from test_kh2_mask_media import machine, STATE, REGS, QS, BASES, SP

SITES=(0x37908,0x37970,0x379c0,0x37a0c,0x44380,0x443e8,0x44438,0x44484)
OUT=0x8000200
CORNERS=0x8000100


class QuadFixture:
    def __init__(self, original, image, base):
        self.base=base
        self.pair=[machine(b,base) for b in (original,image)]
        self.stop=0
        for u,_ in self.pair:
            u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:
                uc.emu_stop() if a==self.stop else None)

    def compare(self, test, site, bits, title, task, seed, nzcv, corners=None):
        rng=random.Random(seed)
        initial=[rng.getrandbits(64) for _ in REGS]+[rng.getrandbits(128) for _ in QS]
        # Authentic owned calls use packed color 80000000 and ordering zero.
        initial[0:5]=[OUT,0x80000000,CORNERS,CORNERS+12,0]
        if corners is None:
            corners=struct.pack('<6f',*[rng.uniform(-8192,8192) for _ in range(6)])
        payload=bytes(rng.getrandbits(8) for _ in range(0x50))
        active=bool(bits&1 and title!=1 and task==0)
        self.stop=self.base+site+4
        result=[]
        for u,writes in self.pair:
            for reg,value in zip(REGS+QS,initial):u.reg_write(reg,value)
            u.reg_write(r.UC_ARM64_REG_SP,SP)
            u.reg_write(r.UC_ARM64_REG_NZCV,nzcv<<28)
            u.reg_write(r.UC_ARM64_REG_FPCR,0x400000 if seed&1 else 0)
            u.reg_write(r.UC_ARM64_REG_FPSR,0x8000000 if seed&2 else 0)
            u.mem_write(OUT,payload)
            u.mem_write(CORNERS,corners)
            u.mem_write(self.base+mask.FLAG,struct.pack('<I',bits))
            u.mem_write(self.base+mask.TITLE_STATE,struct.pack('<I',title))
            u.mem_write(self.base+mask.MEDIA_TASK,struct.pack('<Q',task))
            u.mem_write(self.base+0xa62b50,b'\1')
            # Invalid movie player must not be followed, including teardown.
            u.mem_write(self.base+0xa6b1e0,struct.pack('<Q',0xdeadbeefdeadbeef))
            u.mem_write(self.base+0xaa0fe8,struct.pack('<I',seed%6))
            writes.clear()
            u.emu_start(self.base+site,0,count=500)
            test.assertEqual(u.reg_read(r.UC_ARM64_REG_PC),self.stop)
            test.assertEqual(bytes(u.mem_read(CORNERS,24)),corners)
            test.assertTrue(all(SP-0x80<=a and a+n<=SP or OUT<=a and a+n<=OUT+0x50
                                for a,n in writes),writes)
            result.append(([u.reg_read(x) for x in STATE],bytes(u.mem_read(OUT,0x50)),
                           [(a,n) for a,n in writes if OUT<=a<OUT+0x50]))
        expected=bytearray(result[0][1])
        extra=[]
        if active:
            for off in (20,40,60):
                expected[off:off+4]=expected[:4]
                extra.append((OUT+off,4))
        test.assertEqual(result[1][0],result[0][0], 'all callee CPU outputs must survive')
        test.assertEqual(result[1][1],bytes(expected),'only owned vertex X may change')
        test.assertEqual(result[1][2],result[0][2]+extra,'original stores plus exactly three X stores')
        test.assertEqual(result[1][0][0],OUT+0x50)
        # Every possible indexed triangle from the four vertices has zero area
        # for finite XY. Independent of winding/triangle strip order.
        if active:
            xy=[struct.unpack_from('<2f',result[1][1],i*20) for i in range(4)]
            for a,b,c in itertools.combinations(xy,3):
                test.assertEqual((b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1]),0)


class GeometryTests(unittest.TestCase):
    def test_eight_owned_constructor_sites_and_random_exact_cpu_state(self):
        original=(INPUT/'main.patched.bin').read_bytes()
        # Exact original producer geometry for outer 640x480, inner 512x416,
        # viewport factors 1,1,1. Captured by executing original 37800/442a4
        # through all four constructors; only caf0 allocation is substituted.
        known=[(1792.5,1856.5,0,1856.5,2336.5,0),
               (2368.5,1856.5,0,2432.5,2336.5,0),
               (1856.5,1856.5,0,2368.5,1952.5,0),
               (1856.5,2240.5,0,2368.5,2336.5,0),
               (2048.5,2048.5,0,2112.5,2528.5,0),
               (2624.5,2048.5,0,2688.5,2528.5,0),
               (2112.5,2048.5,0,2624.5,2144.5,0),
               (2112.5,2432.5,0,2624.5,2528.5,0)]
        count=0
        for cpu,base in itertools.product((False,True),BASES):
            image=mask.patch_image(original,cpu_aspect=cpu)
            fixture=QuadFixture(original,image,base)
            for site,bits,seed in itertools.product(SITES,range(4) if cpu else range(2),range(16)):
                with self.subTest(cpu=cpu,base=base,site=hex(site),bits=bits,seed=seed):
                    corners=struct.pack('<6f',*known[seed]) if seed<8 else None
                    fixture.compare(self,site,bits,0,0,seed,seed,corners)
                    count+=1
        print(f'Authentic constructor/site/CPU-state/random+known-corner comparisons: {count}')

    def test_post_constructor_all_nzcv_and_return_state(self):
        original=(INPUT/'main.patched.bin').read_bytes()
        image=mask.patch_image(original,cpu_aspect=True)
        count=0
        for base in BASES:
            u,writes=machine(image,base,seed=23)
            end=base+0x3790c
            u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:uc.emu_stop() if a==end else None)
            before=[u.reg_read(x) for x in STATE]
            before[0]=OUT+0x50;before[30]=end
            before[STATE.index(r.UC_ARM64_REG_SP)]=SP
            for bits,title,task,nzcv in itertools.product(range(4),(0,1,0xffffffff),
                                                         (0,1,0x100000000),range(16)):
                with self.subTest(base=base,bits=bits,title=title,task=task,nzcv=nzcv):
                    before[STATE.index(r.UC_ARM64_REG_NZCV)]=nzcv<<28
                    for reg,value in zip(STATE,before):u.reg_write(reg,value)
                    # State immediately after authentic constructor returns to
                    # wrapper: its saved outer LR/x29 are at SP-16.
                    u.reg_write(r.UC_ARM64_REG_SP,SP-16)
                    u.reg_write(r.UC_ARM64_REG_LR,base+mask.INPUT_SIZE+136)
                    u.mem_write(SP-16,struct.pack('<2Q',before[29],end))
                    u.mem_write(base+mask.FLAG,struct.pack('<I',bits))
                    u.mem_write(base+mask.TITLE_STATE,struct.pack('<I',title))
                    u.mem_write(base+mask.MEDIA_TASK,struct.pack('<Q',task))
                    u.mem_write(OUT,bytes(range(80)))
                    writes.clear()
                    u.emu_start(base+mask.INPUT_SIZE+136,0,count=100)
                    self.assertEqual(u.reg_read(r.UC_ARM64_REG_PC),end)
                    self.assertEqual([u.reg_read(x) for x in STATE],before)
                    extra=[(OUT+x,4) for x in (20,40,60)] if bits&1 and title!=1 and not task else []
                    self.assertEqual([(a,n) for a,n in writes if OUT<=a<OUT+80],extra)
                    self.assertTrue(all(SP-16<=a and a+n<=SP or OUT<=a and a+n<=OUT+80 for a,n in writes))
                    count+=1
        print(f'Post-constructor all-NZCV/full-return-state comparisons: {count}')

if __name__=='__main__': unittest.main()
