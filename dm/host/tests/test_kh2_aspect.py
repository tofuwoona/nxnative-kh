#!/usr/bin/env python3
"""CPU-only production resolution/gate tests; no loader, app, GPU or guest execution."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from kh2_mask_fixture import C as MASK_FIXTURE, write_image

ROOT = Path(__file__).resolve().parents[3]


def function(text, marker):
    start = text.index(marker)
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


class AspectTests(unittest.TestCase):
    def test_resolution_contract(self):
        oe = (ROOT / 'dm/host/hle_oe.c').read_text()
        vk = (ROOT / 'dm/gfx/vk/hle_vk.m').read_text()
        gate = ''
        if 'static _Atomic uint64_t g_kh2_aspect' in oe:
            gate = oe[oe.index('static _Atomic uint64_t g_kh2_aspect'):oe.index('// ---------- System notification')]
        res = function(oe, 'HLE_FORCE("_ZN2nn2oe27GetDefaultDisplayResolutionEPiS1_"')
        res = res[res.index('{'):]
        surface = function(vk, 'static VkExtent2D surf_ext(void)')
        harness = r'''
#include <assert.h>
#include <stdatomic.h>
#include <stdio.h>
#include "dm.h"
#if __has_include("kh2_aspect.h")
#include "kh2_aspect.h"
#endif
module_t g_mod[MAX_MOD]; int g_nmod;
static int dm_kh1_bar_apply(int on) {(void)on;return 1;}
static int mode;
int dm_opmode(void) { return mode; }
static int opmode(void) { return mode; }
GATE
static void resolution(int *w, int *h) RES
 typedef struct { unsigned width,height; } VkExtent2D;
SURFACE
int main(int argc, char **argv) {
    assert(argc == 4);
    mode = atoi(argv[1]);
    int wanted = atoi(argv[3]);
    // Before loading, UI policy must stay off without touching loader state.
#if __has_include("kh2_aspect.h")
    assert(!dm_kh2_aspect_on());
#endif
    g_nmod=1; snprintf(g_mod[0].name,sizeof g_mod[0].name,"main");
    snprintf(g_mod[0].build_id,sizeof g_mod[0].build_id,"%s",argv[2]);
    test_mask_load(&g_mod[0]);
#if __has_include("kh2_aspect.h")
    dm_kh2_aspect_init(2556,1179);
    assert(dm_kh2_aspect_on()==wanted);
#endif
    int w=-1,h=-1; resolution(&w,&h); VkExtent2D s=surf_ext();
    int kh1=DM_GAME_PROGRAM_ID==0x010090C022978001ull;
    int ew=wanted?(kh1?1561:1704):(mode==1?1920:1280), eh=wanted?(kh1?720:786):(mode==1?1080:720);
    if(w!=ew || h!=eh) { fprintf(stderr,"oe got %dx%d expected %dx%d\n",w,h,ew,eh); return 1; }
    assert(s.width==(unsigned)(wanted?(kh1?1561:1704):(mode?1920:1280)));
    assert(s.height==(unsigned)(wanted?(kh1?720:786):(mode?1080:720)));
    resolution(NULL,NULL); resolution(&w,NULL); resolution(NULL,&h);
    if(wanted) { assert(w>=960 && h>=540 && w<=1920 && h<=1080); if(!kh1) assert(w*1179==h*2556); }
    // Published mode is immutable to front-end reads after init (no env re-read).
    setenv("DM_KH2_ASPECT_EXPERIMENT","0",1);
#if __has_include("kh2_aspect.h")
    assert(dm_kh2_aspect_on()==wanted);
#endif
    return 0;
}
'''.replace('GATE',MASK_FIXTURE + gate).replace('RES',res).replace('SURFACE',surface)
        with tempfile.TemporaryDirectory(prefix='kh2-dim-', dir=os.environ['TMPDIR']) as tmp:
            tmp = Path(tmp)
            image = write_image(tmp)
            src = tmp / 't.c'; src.write_text(harness)
            env = dict(os.environ, DM_GAMES_DIR=str(ROOT/'dm/games/010090C022978000/direct-profiles'), DM_GAMES_FIRST='1')
            cases = 0
            for program in ('010090C022978003', '010090C022978001', '010090C022978000'):
                header = tmp / 'game_profile.h'
                subprocess.run(['python3',str(ROOT/'dm/games/game.py'),'header',program,str(header)],env=env,check=True,capture_output=True)
                exe = tmp / 't'
                subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(tmp),'-I'+str(ROOT/'dm/host'),str(src),'-o',str(exe)],check=True)
                for build in ('e1bced80ffd14436980f7490b1d3c3e7', 'badf2faf580b712464365c4d529d92c9', '', 'unknown', 'e1bced80ffd14436980f7490b1d3c3e8'):
                    for switch in ('1',None,'0','','true','2'):
                        for mode in (0,1,2):
                            runenv = dict(os.environ, KH2_MASK_IMAGE=image)
                            runenv.pop('DM_KH2_ASPECT_EXPERIMENT',None)
                            if switch is not None: runenv['DM_KH2_ASPECT_EXPERIMENT']=switch
                            exact = (program=='010090C022978003' and build=='e1bced80ffd14436980f7490b1d3c3e7') or (program=='010090C022978001' and build=='badf2faf580b712464365c4d529d92c9')
                            expected = exact and switch=='1'
                            with self.subTest(program=program,build=build,switch=switch,mode=mode):
                                p=subprocess.run([str(exe),str(mode),build,str(int(expected))],env=runenv,capture_output=True,text=True)
                                self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                            cases+=1
            print(f'production oe/surf/gate: {cases} process cases')


if __name__ == '__main__': unittest.main()
