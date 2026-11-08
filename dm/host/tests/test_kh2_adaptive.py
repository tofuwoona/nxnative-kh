#!/usr/bin/env python3
"""CPU-only dimension ingress: production gate/OE/VK, real guarded payload.
The viewport/loader are explicit seams; no physical display or GPU is exercised.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from kh2_mask_fixture import C as MASK_FIXTURE, write_image
from test_kh2_aspect import ROOT, function


class AdaptiveTests(unittest.TestCase):
    def test_launcher_description_is_viewport_based(self):
        row=next(line for line in (ROOT/'dm/games/settings.tsv').read_text().splitlines() if line.startswith('DM_KH2_ASPECT_EXPERIMENT\t')).split('\t')
        self.assertEqual(row[3:5],['1','game:010090C022978001,010090C022978003'])
        self.assertNotIn('15 Pro',row[-1])
        self.assertIn('Relaunch',row[-1])
        self.assertIn('display',row[-1])

    def test_header_policy_against_integer_search_oracle(self):
        from test_kh2_adaptive_startup import run_c
        c=r'''
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include "kh2_aspect.h"
static dm_kh2_extent oracle(uint32_t w,uint32_t h) {
 dm_kh2_extent best={0,0},even={0,0};
 if(!w || !h || w>16384 || h>16384 || (uint64_t)w*9<(uint64_t)h*16 || (uint64_t)w*9>(uint64_t)h*20) return best;
 for(unsigned y=540;y<=1080;y++) {
  uint64_t n=(uint64_t)w*y;
  if(n%h)continue;
  unsigned x=(unsigned)(n/h);
  if(x<960 || x>1920)continue;
  best=(dm_kh2_extent){x,y};
  if(!(x&1) && !(y&1))even=best;
 }
 return even.width?even:best;
}
int main(void) {
 unsigned count=0;
 for(uint32_t w=0;w<=5000;w+=17) for(uint32_t h=0;h<=2500;h+=13) {
  dm_kh2_extent a=dm_kh2_aspect_choose(w,h), b=oracle(w,h);
  assert(a.width==b.width && a.height==b.height);count++;
 }
 const uint32_t v[][2]={{2556,1179},{2622,1206},{2340,1080},{1801,901},{1001,501},{UINT32_MAX,UINT32_MAX},{16384,8192},{16385,8192}};
 for(unsigned i=0;i<sizeof v/sizeof *v;i++) {
  dm_kh2_extent a=dm_kh2_aspect_choose(v[i][0],v[i][1]),b=oracle(v[i][0],v[i][1]);
  assert(a.width==b.width && a.height==b.height);
 }
 dm_kh2_extent a=dm_kh2_aspect_pixels(2556+1e-7,1179-1e-7);assert(a.width==2556 && a.height==1179);
 const double bad[]={0,-1,NAN,INFINITY,1e30,16385,1179.25};
 for(unsigned i=0;i<sizeof bad/sizeof *bad;i++) {
  a=dm_kh2_aspect_pixels(bad[i],1080);assert(!a.width && !a.height);
  a=dm_kh2_aspect_pixels(1920,bad[i]);assert(!a.width && !a.height);
 }
 a=(dm_kh2_extent){1,2};assert(!dm_kh2_aspect_parse_viewport(NULL,&a));assert(a.width==1 && a.height==2);
 assert(!dm_kh2_aspect_parse_viewport("1920x1080",NULL));
 assert(!dm_kh2_aspect_parse_viewport("1920",&a));assert(a.width==1 && a.height==2);
 assert(dm_kh2_aspect_parse_viewport("320x180",&a));assert(a.width==320 && a.height==180);
 const uint32_t kh1[][4]={{1920,1080,1280,720},{2556,1179,1561,720},{2400,1080,1600,720},{2280,1080,1520,720}};
 for(unsigned i=0;i<sizeof kh1/sizeof *kh1;i++) {
  a=dm_kh1_aspect_choose(kh1[i][0],kh1[i][1]);
  assert(a.width==kh1[i][2] && a.height==kh1[i][3]);
 }
 printf("header policy: %u integer-search comparisons plus explicit boundaries\n",count);
 return 0;
}
'''
        p=run_c(c);self.assertEqual(p.returncode,0,p.stdout+p.stderr);print(p.stdout.strip())

    def test_atomic_pair_readers_and_invalid_warm_reset(self):
        oe=(ROOT/'dm/host/hle_oe.c').read_text()
        gate=oe[oe.index('static _Atomic uint64_t g_kh2_aspect'):oe.index('// ---------- System notification')]
        c=r'''
#include <assert.h>
#include <stdatomic.h>
#include <sched.h>
#include "dm.h"
#include "kh2_aspect.h"
module_t g_mod[MAX_MOD]; int g_nmod;
static int dm_kh1_bar_apply(int on) {(void)on;return 1;}
GATE
static _Atomic int done,ready;
static unsigned reads;
static void *reader(void *unused) {
 (void)unused;atomic_store(&ready,1);
 do {
  dm_kh2_extent s=dm_kh2_aspect_size();
  assert((s.width==1704 && s.height==786) || (s.width==1920 && s.height==864));
  reads++;
 } while(!atomic_load(&done));
 return NULL;
}
int main(void) {
 setenv("DM_KH2_ASPECT_EXPERIMENT","1",1);unsetenv("DM_KH2_CPU_ASPECT_EXPERIMENT");
 g_nmod=1;snprintf(g_mod[0].name,sizeof g_mod[0].name,"main");
 snprintf(g_mod[0].build_id,sizeof g_mod[0].build_id,"e1bced80ffd14436980f7490b1d3c3e7");
 test_mask_load(&g_mod[0]);dm_kh2_aspect_init(2556,1179);
 uint32_t *flag=(uint32_t *)(g_mod[0].base+g_mod[0].key_page_off+0x100);
 assert(*flag==3);
 pthread_t th;assert(!pthread_create(&th,NULL,reader,NULL));
 while(!atomic_load(&ready))sched_yield();
 // Stopped-guest reinit only: UI readers continue, no guest/resources run.
 for(int i=0;i<64;i++) {dm_kh2_aspect_init(2400,1080);dm_kh2_aspect_init(2556,1179);}
 atomic_store(&done,1);assert(!pthread_join(th,NULL));assert(reads>0);
 dm_kh2_aspect_init(1001,501);assert(!dm_kh2_aspect_on() && *flag==0);
 dm_kh2_extent s=dm_kh2_aspect_size();assert(!s.width && !s.height);
 printf("atomic pair: %u coherent reader snapshots; invalid warm reset cleared payload flags\n",reads);
 return 0;
}
'''.replace('GATE',MASK_FIXTURE+gate)
        with tempfile.TemporaryDirectory(prefix='adaptive-pair-',dir=os.environ['TMPDIR']) as t:
            t=Path(t);(t/'t.c').write_text(c);image=write_image(t)
            env=dict(os.environ,DM_GAMES_DIR=str(ROOT/'dm/games/010090C022978000/direct-profiles'),DM_GAMES_FIRST='1')
            subprocess.run(['python3',str(ROOT/'dm/games/game.py'),'header','010090C022978003',str(t/'game_profile.h')],env=env,check=True,capture_output=True)
            subprocess.run(['clang','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(t),'-I'+str(ROOT/'dm/host'),str(t/'t.c'),'-o',str(t/'t')],check=True)
            p=subprocess.run([str(t/'t')],env=dict(os.environ,KH2_MASK_IMAGE=image),capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertNotIn('runtime error:',p.stderr);print(p.stdout.strip())

    def test_viewport_reaches_oe_and_vk(self):
        oe = (ROOT/'dm/host/hle_oe.c').read_text()
        header = (ROOT/'dm/host/kh2_aspect.h').read_text()
        gate = oe[oe.index('static _Atomic'):oe.index('// ---------- System notification')]
        gate = gate[gate.index('static _Atomic', gate.index('// Publish')):] if '// Publish' in gate else gate
        res = function(oe, 'HLE_FORCE("_ZN2nn2oe27GetDefaultDisplayResolutionEPiS1_"')
        res = res[res.index('{'):]
        surface = function((ROOT/'dm/gfx/vk/hle_vk.m').read_text(),'static VkExtent2D surf_ext(void)')
        # Baseline executes its real no-argument gate: RED is wrong dimensions,
        # never a missing declaration or compilation failure.
        init = 'dm_kh2_aspect_init(vw,vh)' if 'uint32_t viewport_w' in header else 'dm_kh2_aspect_init()'
        harness = r'''
#include <assert.h>
#include <stdatomic.h>
#include "dm.h"
#include "kh2_aspect.h"
module_t g_mod[MAX_MOD]; int g_nmod;
static int dm_kh1_bar_apply(int on) {(void)on;return 1;}
static int mode;
int dm_opmode(void) { return mode; }
static int opmode(void) { return mode; }
GATE
static void resolution(int *w,int *h) RES
typedef struct { unsigned width,height; } VkExtent2D;
SURFACE
int main(int argc,char **argv) {
 assert(argc==8);
 unsigned vw=(unsigned)strtoul(argv[1],0,10), vh=(unsigned)strtoul(argv[2],0,10);
 (void)vw;(void)vh;
 int ew=atoi(argv[3]),eh=atoi(argv[4]); mode=atoi(argv[5]);
 g_nmod=1;snprintf(g_mod[0].name,sizeof g_mod[0].name,"main");
 snprintf(g_mod[0].build_id,sizeof g_mod[0].build_id,"%s",argv[6]);
 assert(!dm_kh2_aspect_on()); test_mask_load(&g_mod[0]);
 INIT;
 assert(dm_kh2_aspect_on()==atoi(argv[7]));
 int w=0,h=0;resolution(&w,&h);VkExtent2D s=surf_ext();
 if(w!=ew || h!=eh || s.width!=(unsigned)ew || s.height!=(unsigned)eh) {
  fprintf(stderr,"viewport %ux%u: OE %dx%d VK %ux%u expected %dx%d\n",vw,vh,w,h,s.width,s.height,ew,eh);return 1;
 }
 resolution(NULL,NULL);resolution(&w,NULL);resolution(NULL,&h);
 assert(w==ew && h==eh);
 setenv("DM_KH2_ASPECT_EXPERIMENT","0",1);g_nmod=0;
 resolution(&w,&h);s=surf_ext();assert(w==ew && h==eh && s.width==(unsigned)ew && s.height==(unsigned)eh);
 return 0;
}
'''
        for key,val in [('GATE',MASK_FIXTURE+gate),('RES',res),('SURFACE',surface),('INIT',init)]: harness=harness.replace(key,val)
        with tempfile.TemporaryDirectory(prefix='adaptive-',dir=os.environ['TMPDIR']) as tmp:
            tmp=Path(tmp); (tmp/'t.c').write_text(harness); image=write_image(tmp)
            env=dict(os.environ,DM_GAMES_DIR=str(ROOT/'dm/games/010090C022978000/direct-profiles'),DM_GAMES_FIRST='1')
            valid=[(1920,1080,1920,1080),(2556,1179,1704,786),(2400,1080,1920,864),(2532,1170,1688,780),(2796,1290,1864,860),(2436,1125,1624,750),(2688,1242,1792,828),(2340,1080,1898,876),(2280,1080,1900,900),(2000,1000,1920,960)]
            invalid=[(0,1080),(1920,0),(0,0),(1,1),(1024,768),(393,852),(3000,1000),(4294967295,2147483647),(20000,10000),(2557,1179),(2001,1000),(1001,501)]
            count=0
            for program in ['010090C022978003','010090C022978001','010090C022978000']:
                subprocess.run(['python3',str(ROOT/'dm/games/game.py'),'header',program,str(tmp/'game_profile.h')],env=env,check=True,capture_output=True)
                subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(tmp),'-I'+str(ROOT/'dm/host'),str(tmp/'t.c'),'-o',str(tmp/'t')],check=True)
                for vw,vh,rw,rh,valid_input in [(*v,1) for v in valid]+[(w,h,0,0,0) for w,h in invalid]:
                    for mode in (0,1):
                        for build in ('e1bced80ffd14436980f7490b1d3c3e7','badf2faf580b712464365c4d529d92c9','unknown'):
                            for switch in ('0','1'):
                                exact=(program=='010090C022978003' and build=='e1bced80ffd14436980f7490b1d3c3e7') or (program=='010090C022978001' and build=='badf2faf580b712464365c4d529d92c9')
                                on=int(exact and switch=='1' and valid_input)
                                if on and program=='010090C022978001': ew,eh=round(vw*720/vh),720
                                else: ew,eh=(rw,rh) if on else ((1920,1080) if mode else (1280,720))
                                with self.subTest(program=program,viewport=(vw,vh),mode=mode,build=build,switch=switch):
                                    p=subprocess.run([str(tmp/'t'),str(vw),str(vh),str(ew),str(eh),str(mode),build,str(on)],env=dict(os.environ,KH2_MASK_IMAGE=image,DM_KH2_ASPECT_EXPERIMENT=switch),capture_output=True,text=True)
                                    self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                                    self.assertNotIn('runtime error:',p.stderr)
                                count+=1
            print(f'adaptive production gate/OE/VK: {count} process cases')


if __name__=='__main__':unittest.main()
