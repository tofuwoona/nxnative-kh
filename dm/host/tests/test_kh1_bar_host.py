#!/usr/bin/env python3
"""KH1 exact loaded-layout activation and read-only flag; no guest/GPU."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_kh2_aspect import ROOT

C=r'''
#include <assert.h>
#include <stdatomic.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>
#include "dm.h"
#include "kh2_aspect.h"
module_t g_mod[MAX_MOD]; int g_nmod;
static int calls,fail;
static void *page;
static int protect(void *p,size_t n,int prot) {
 assert(p==page && n==0x4000 && !(prot&PROT_EXEC));
 assert(prot==(calls%2?PROT_READ:PROT_READ|PROT_WRITE));
 ++calls;if(calls==fail)return -1;return mprotect(p,n,prot);
}
#define mprotect protect
#if __has_include("kh1_bar.h")
#include "kh1_bar.h"
#endif
#undef mprotect
static int dm_kh2_mask_apply(int on){(void)on;return 0;}
GATE
int main(int argc,char **argv) {
 assert(argc==3);int mode=atoi(argv[2]);
 g_nmod=1;module_t *m=&g_mod[0];strcpy(m->name,"main");
 strcpy(m->build_id,"badf2faf580b712464365c4d529d92c9");
 if(mode==0){dm_kh2_aspect_init(2556,1179);assert(!dm_kh2_aspect_on());return 0;}
 FILE *f=fopen(argv[1],"rb");assert(f);fseek(f,0,SEEK_END);size_t size=ftell(f);rewind(f);
 m->base=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);
 assert(m->base!=MAP_FAILED && !((uintptr_t)m->base&0x3fff));
 assert(fread(m->base,1,size,f)==size);fclose(f);
 m->size=size;m->text_end=0x2f0c00;m->ro_off=0x2f1000;m->data_off=0x3cb000;
 m->key_page_off=0x31c8000;m->key_page_size=0x4000;m->patch_off=0x31d0000;m->loaded=1;
 for(int i=0;i<4;i++)m->key_idx[i]=i;
 page=m->base+0x31c8000;uint32_t *flag=(uint32_t *)((char *)page+0x100);assert(!*flag);
 if(mode==2)m->base[0x3edcc]^=1;
 if(mode==3)m->base[0x31e8080]^=1;
 if(mode==4)m->base[0x3ef20]^=1;
 if(mode==5)m->size--;
 if(mode==6)m->build_id[0]='f';
 if(mode==7)m->patch_off++;
 if(mode==8)*flag=2;
 if(mode==9)fail=1;
 if(mode==10)fail=2;
 if(mode==11)*flag=1;
 if(mode==12){g_mod[1]=*m;g_nmod=2;}
 if(mode==13)m->base[0x5e940]^=1;
 if(mode==14)m->base[0x5eb30]^=1;
 if(mode==15)m->base[0x31e8100]^=1;
 assert(!mprotect(page,0x4000,PROT_READ));
 dm_kh2_aspect_init(2556,1179);
 int want=mode==1;
 assert(dm_kh2_aspect_on()==want);
 assert(*flag==(mode==8?2:want?1:0));
 if(want){
  assert(calls==2);setenv("DM_KH2_ASPECT_EXPERIMENT","0",1);dm_kh2_aspect_init(2556,1179);
  assert(!dm_kh2_aspect_on() && !*flag && calls==4);
 }
 else if(mode==11)assert(calls==2 && !*flag);
 else if(mode==9)assert(calls==1);
 else assert(calls==0);
 if(calls==2 || calls==4){pid_t p=fork();assert(p>=0);if(!p){*flag=1;_exit(0);}int st;assert(waitpid(p,&st,0)==p);assert(WIFSIGNALED(st));}
 munmap(m->base,size);return 0;
}
'''


class Kh1BarHostTests(unittest.TestCase):
    def test_exact_activation_rejections_and_readonly(self):
        from test_kh1_bar import bar, INPUT
        self.assertIsNotNone(bar)
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'],prefix='kh1-bar-host-') as td:
            td=Path(td);image=td/'main.bin';image.write_bytes(bar.patch_image((INPUT/'main.patched.bin').read_bytes()))
            oe=(ROOT/'dm/host/hle_oe.c').read_text()
            gate=oe[oe.index('static _Atomic uint64_t g_kh2_aspect'):oe.index('// ---------- System notification')]
            src=td/'test.c';src.write_text(C.replace('GATE',gate))
            env=dict(os.environ,DM_GAMES_DIR=str(ROOT/'dm/games/010090C022978000/direct-profiles'),DM_GAMES_FIRST='1')
            subprocess.run(['python3',str(ROOT/'dm/games/game.py'),'header','010090C022978001',str(td/'game_profile.h')],env=env,check=True,capture_output=True)
            exe=td/'test';subprocess.run(['clang','-Wall','-Wextra','-Werror','-Wno-unused-function','-I'+str(td),'-I'+str(ROOT/'dm/host'),str(src),'-o',str(exe)],check=True)
            for mode in range(16):
                runenv=dict(env,DM_KH2_ASPECT_EXPERIMENT='0' if mode==11 else '1')
                with self.subTest(mode=mode):
                    p=subprocess.run([str(exe),str(image),str(mode)],env=runenv,capture_output=True,text=True)
                    if mode==10:
                        self.assertEqual(p.returncode,-6,p.stderr);self.assertIn('restore read-only',p.stderr)
                    else:self.assertEqual(p.returncode,0,p.stdout+p.stderr)


if __name__=='__main__':unittest.main()
