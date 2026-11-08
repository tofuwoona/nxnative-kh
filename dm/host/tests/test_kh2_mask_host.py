#!/usr/bin/env python3
"""Actual aspect gate + data activation, mmap/mprotect; never execute guest."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_kh2_aspect import ROOT, function

C = r'''
#include <assert.h>
#include <stdatomic.h>
#include <sys/mman.h>
#include <unistd.h>
#include "dm.h"
#include "kh2_aspect.h"
module_t g_mod[MAX_MOD]; int g_nmod;
static int calls,fail;
static void *page;
static int protect(void *p,size_t n,int prot) {
 assert(p==page && n==0x4000 && !(prot&PROT_EXEC));
 assert(prot==(calls%2?PROT_READ:PROT_READ|PROT_WRITE));
 ++calls;
 if(calls==fail)return -1;
 return mprotect(p,n,prot);
}
#define mprotect protect
#if __has_include("kh2_mask.h")
#include "kh2_mask.h"
#endif
#undef mprotect
static int dm_kh1_bar_apply(int on) {
    (void)on;
    assert(!"KH1 bar activation is outside this KH2 fixture");
    return 0;
}
GATE
int main(int argc,char **argv) {
 assert(argc==3); int mode=atoi(argv[2]);
 assert(!dm_kh2_aspect_on());
 g_nmod=1; module_t *m=&g_mod[0]; strcpy(m->name,"main");
 strcpy(m->build_id,"e1bced80ffd14436980f7490b1d3c3e7");
 if(mode==0) {dm_kh2_aspect_init(2556,1179);assert(!dm_kh2_aspect_on());return 0;}
 FILE *f=fopen(argv[1],"rb");assert(f);fseek(f,0,SEEK_END);size_t size=ftell(f);rewind(f);
 // mmap guarantees a 16K-aligned address on the target Darwin arm64 host.
 m->base=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);
 assert(m->base!=MAP_FAILED && !((uintptr_t)m->base&0x3fff));
 assert(fread(m->base,1,size,f)==size);fclose(f);
 m->size=size;m->text_end=0x400d50;m->ro_off=0x401000;m->data_off=0x52f000;
 m->key_page_off=0x2d30000;m->key_page_size=0x4000;m->patch_off=0x2d40000;m->loaded=1;
 for(int i=0;i<4;i++)m->key_idx[i]=i;
 page=m->base+0x2d30000;uint32_t *flag=(uint32_t *)((char *)page+0x100);
 assert(*flag==0);
 if(mode==2)m->base[0x37760]^=1;
 if(mode==3)m->base[0x4422c]^=1;
 if(mode==4)m->base[0x2d5c080]^=1;
 if(mode==5)m->base[0x2d5c0c0]^=1;
 if(mode==6)m->base[0x2d5c000]^=1;
 if(mode==7)m->size--;
 if(mode==8)m->key_idx[3]=32;
 if(mode==9)m->patch_off++;
 if(mode==10)m->build_id[0]='f';
 if(mode==11)m->loaded=0;
 if(mode==12)m->key_page_off++;
 if(mode==13)m->text_end++;
 if(mode==14)m->fps_state_off=0x2d30100;
 if(mode==15)m->base[0x2d5ffff]=1;
 if(mode==16)*flag=2;
 if(mode==17)fail=1;
 if(mode==18)fail=2;
 if(mode==19)*flag=1; // warm process: OFF must clear a prior activation
 if(mode==20)m->key_page_size=0x8000;
 if(mode==21)m->ro_off++;
 if(mode==22)m->data_off++;
 if(mode==23)m->image_size=1;
 if(mode==24)m->file_image_len=1;
 if(mode==25)m->patch_len=1;
 if(mode==26)m->nro=1;
 if(mode==27){g_mod[1]=*m;g_nmod=2;}
 if(mode==30)m->base[0x21938]^=1;
 if(mode==31)m->base[0x2d5c100]^=1;
 if(mode==33){*flag=1;fail=1;}
 assert(!mprotect(page,0x4000,PROT_READ));
 if(mode==35) {
   dm_kh2_aspect_init(2556,1179);assert(dm_kh2_aspect_on() && *flag==1 && calls==2);
   setenv("DM_KH2_CPU_ASPECT_EXPERIMENT","1",1);
   dm_kh2_aspect_init(2556,1179);assert(!dm_kh2_aspect_on() && *flag==0 && calls==4);
   pid_t pid=fork();assert(pid>=0);if(!pid){*flag=1;_exit(0);}int st;assert(waitpid(pid,&st,0)==pid);assert(WIFSIGNALED(st));
   munmap(m->base,size);return 0;
 }
 dm_kh2_aspect_init(2556,1179);
 int want=(mode==1 || mode==28) && DM_GAME_PROGRAM_ID==0x010090C022978003ull;
 assert(dm_kh2_aspect_on()==want);
 assert(*flag==(mode==16?2:want?(mode==28?3:1):0));
 if(want){assert(calls==2);setenv("DM_KH2_ASPECT_EXPERIMENT","0",1);dm_kh2_aspect_init(2556,1179);assert(!dm_kh2_aspect_on() && *flag==0 && calls==4);}
 else if(mode==19 && DM_GAME_PROGRAM_ID==0x010090C022978003ull)assert(calls==2);
 else if(mode==17)assert(calls==1);
 else assert(calls==0);
 // Actual OS must reject a child write after successful activation/deactivation.
 if(calls==2 || calls==4) {
   pid_t pid=fork();assert(pid>=0);if(!pid){*flag=1;_exit(0);}int st;assert(waitpid(pid,&st,0)==pid);assert(WIFSIGNALED(st));
 }
 munmap(m->base,size);return 0;
}
'''

class HostTests(unittest.TestCase):
    def test_loader_zeros_reserved_flag_on_every_load(self):
        loader=(ROOT/'dm/host/loader.c').read_text()
        install=function(loader,'static void install_key_page(module_t *m)')
        c=r'''
#include <assert.h>
#include <sys/mman.h>
#include "dm.h"
enum {KEY_N=4};
static unsigned key_value(unsigned i){return i+1;}
static void install_fps_state(module_t *m){(void)m;assert(0);}
INSTALL
int main(void){
 module_t m={0};m.size=0x8000;m.key_page_off=0x4000;m.key_page_size=0x4000;
 m.base=mmap(NULL,m.size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);assert(m.base!=MAP_FAILED);
 for(unsigned i=0;i<4;i++)m.key_idx[i]=i;
 for(int load=0;load<3;load++){
  uint8_t *page=m.base+m.key_page_off;
  assert(!mprotect(page,0x4000,PROT_READ|PROT_WRITE));memset(page,0xff,0x4000);
  install_key_page(&m);
  for(unsigned i=0;i<4;i++)assert(((uint64_t*)page)[i]==(i+1)*8);
  for(unsigned i=32;i<0x4000;i++)assert(page[i]==0);
 }
 munmap(m.base,m.size);return 0;
}
'''.replace('INSTALL',install)
        import re
        keys=re.search(r'enum \{ KEY_K18,.*?\};',loader).group(0)
        c=c.replace('enum {KEY_N=4};',keys)
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as td:
            td=Path(td);src=td/'loader.c';src.write_text(c)
            env=dict(os.environ,DM_GAMES_DIR=str(ROOT/'dm/games/010090C022978000/direct-profiles'),DM_GAMES_FIRST='1')
            subprocess.run(['python3',str(ROOT/'dm/games/game.py'),'header','010090C022978003',str(td/'game_profile.h')],env=env,check=True,capture_output=True)
            subprocess.run(['clang','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(td),'-I'+str(ROOT/'dm/host'),str(src),'-o',str(td/'loader')],check=True)
            p=subprocess.run([str(td/'loader')],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertNotIn('Sanitizer',p.stderr)

    def test_loaded_layout_activation_and_readonly(self):
        from test_kh2_mask import mask, INPUT
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as td:
            image=Path(td)/'main.bin'
            image.write_bytes(mask.patch_image((INPUT/'main.patched.bin').read_bytes()))
            self.run_cases([*range(1,28),33],image)

    def test_cpu_capability_and_activation(self):
        from test_kh2_mask import mask, INPUT
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as td:
            image=Path(td)/'main.bin'
            original=(INPUT/'main.patched.bin').read_bytes()
            image.write_bytes(mask.patch_image(original,cpu_aspect=True))
            self.run_cases([1,28,29,30,31],image)
            for switch in (None,"1"):
                self.run_cases([28],image,cpu_switch=switch)
            self.run_cases([1],image,cpu_switch="0")
            for switch in ("true","2",""):
                self.run_cases([34],image,cpu_switch=switch)
            for profile in ("010090C022978001","010090C022978000"):
                self.run_cases([1,28,29],image,profile=profile)
            image.write_bytes(mask.patch_image(original))
            self.run_cases([32],image)
            self.run_cases([32],image,cpu_switch=None)
            self.run_cases([35],str(image),cpu_switch="0")

    def test_unpatched_input_cannot_enable_dimensions(self):
        self.run_cases([0])

    def run_cases(self,modes,image='unused',profile='010090C022978003',cpu_switch='auto'):
        oe=(ROOT/'dm/host/hle_oe.c').read_text()
        gate=oe[oe.index('static _Atomic uint64_t g_kh2_aspect'):oe.index('// ---------- System notification')]
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'],prefix='mask-host-') as td:
            td=Path(td);src=td/'test.c';src.write_text(C.replace('GATE',gate).replace('#include <unistd.h>','#include <unistd.h>\n#include <sys/wait.h>'))
            env=dict(os.environ,DM_GAMES_DIR=str(ROOT/'dm/games/010090C022978000/direct-profiles'),DM_GAMES_FIRST='1')
            subprocess.run(['python3',str(ROOT/'dm/games/game.py'),'header',profile,str(td/'game_profile.h')],env=env,check=True,capture_output=True)
            exe=td/'test'
            subprocess.run(['clang','-Wall','-Wextra','-Wno-unused-function','-I'+str(td),'-I'+str(ROOT/'dm/host'),str(src),'-o',str(exe)],check=True)
            for mode in modes:
                runenv=dict(env,DM_KH2_ASPECT_EXPERIMENT='0' if mode in (19,29,33) else '1')
                if cpu_switch == 'auto':runenv['DM_KH2_CPU_ASPECT_EXPERIMENT']='1' if mode in (28,29,30,31,32) else '0'
                elif cpu_switch is None:runenv.pop('DM_KH2_CPU_ASPECT_EXPERIMENT',None)
                else:runenv['DM_KH2_CPU_ASPECT_EXPERIMENT']=cpu_switch
                with self.subTest(mode=mode,profile=profile,cpu_switch=cpu_switch):
                    p=subprocess.run([str(exe),str(image),str(mode)],env=runenv,capture_output=True,text=True)
                    if mode in (18,33):
                        self.assertEqual(p.returncode,-6,p.stderr)
                        self.assertIn('restore read-only' if mode==18 else 'cannot reset',p.stderr)
                    else:self.assertEqual(p.returncode,0,p.stdout+p.stderr)

if __name__=='__main__':unittest.main()
