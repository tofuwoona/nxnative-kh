#!/usr/bin/env python3
"""CPU host-entry ordering with real main/gate, synthetic loader/thread/UI boundaries."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from kh2_mask_fixture import C as MASK_FIXTURE, write_image
from test_kh2_aspect import ROOT, function


class StartupTests(unittest.TestCase):
    def test_header_dependency(self):
        make = (ROOT/'dm/host/Makefile').read_text()
        target = next(line for line in make.splitlines() if line.startswith('dmhost: $(SRC)'))
        self.assertIn('kh2_aspect.h', target.split())

    def test_loading_before_front_and_viewport_before_guest(self):
        text = (ROOT/'dm/host/main.c').read_text()
        main = function(text,'int main(int argc, char **argv)').replace('int main(', 'int host_entry(')
        # Signature-only RED bridge: preserve the old (incorrect) call position.
        main = main.replace('void dm_kh2_aspect_init(void); dm_kh2_aspect_init();', 'dm_kh2_aspect_init(2556,1179);')
        oe = (ROOT/'dm/host/hle_oe.c').read_text()
        gate = oe[oe.index('static _Atomic uint64_t g_kh2_aspect'):oe.index('// ---------- System notification')]
        harness = r'''
#include <assert.h>
#include <stdatomic.h>
#include "dm.h"
#include "kh2_aspect.h"
module_t g_mod[MAX_MOD]; int g_nmod;
static int dm_kh1_bar_apply(int on) {(void)on;return 1;}
GATE
static struct {int argc;char **argv;pthread_t th;_Atomic int started;} g_pre;
static int sequence,expected;
static const char *build;
// Only the loader/OS/guest boundaries are replaced; execute production main.
static void host_preload(int argc,char **argv) {
 assert(argc==2 && argv && sequence==0 && !dm_kh2_aspect_on());
 snprintf(g_mod[0].name,sizeof g_mod[0].name,"main");
 snprintf(g_mod[0].build_id,sizeof g_mod[0].build_id,"%s",build);
 test_mask_load(&g_mod[0]);
 g_nmod=1;sequence=1;
}
static void dm_host_preload_start(int argc,char **argv) {
 g_pre.started=1;g_pre.argc=argc;g_pre.argv=argv;
 host_preload(argc,argv);
}
static int test_join(pthread_t th,void **result) {(void)th;(void)result;assert(sequence==1);return 0;}
#define pthread_join test_join
void crash_thread_init(void) {assert(sequence==1);}
void dm_fps_state_apply(void) {assert(sequence==1 && !dm_kh2_aspect_on());sequence=2;}
static void guest_main(void) {assert(sequence==3);sequence=4;}
static void front_run(void (*guest)(void)) {
 assert(sequence==2 && !dm_kh2_aspect_on()); // viewport exists only now
 dm_kh2_aspect_init(2400,1080);
 assert(dm_kh2_aspect_on()==expected);
 dm_kh2_extent size=dm_kh2_aspect_size();
 int kh1=DM_GAME_PROGRAM_ID==0x010090C022978001ull;
 assert(size.width==(expected?(kh1?1600:1920):0) && size.height==(expected?(kh1?720:864):0));
 sequence=3;guest();
}
MAIN
int main(int argc,char **argv) {
 assert(argc==3);build=argv[1];expected=atoi(argv[2]);
 char *args[]={"test","unused",NULL};
 assert(!dm_kh2_aspect_on());
 assert(host_entry(2,args)==0 && sequence==4);
 return 0;
}
'''.replace('GATE',MASK_FIXTURE + gate).replace('MAIN',main)
        with tempfile.TemporaryDirectory(prefix='kh2-startup-',dir=os.environ['TMPDIR']) as tmp:
            tmp=Path(tmp); src=tmp/'t.c';src.write_text(harness)
            image=write_image(tmp)
            for program in ('010090C022978003','010090C022978001'):
                env=dict(os.environ,DM_GAMES_DIR=str(ROOT/'dm/games/010090C022978000/direct-profiles'),DM_GAMES_FIRST='1')
                subprocess.run(['python3',str(ROOT/'dm/games/game.py'),'header',program,str(tmp/'game_profile.h')],env=env,check=True,capture_output=True)
                exe=tmp/'t'
                subprocess.run(['clang','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(tmp),'-I'+str(ROOT/'dm/host'),str(src),'-o',str(exe)],check=True)
                for preload in (None,'1'):
                    for build in ('','unknown','e1bced80ffd14436980f7490b1d3c3e7','badf2faf580b712464365c4d529d92c9'):
                        for switch in (None,'0','1'):
                            env=dict(os.environ,KH2_MASK_IMAGE=image)
                            for name,value in [('DM_PRELOAD',preload),('DM_KH2_ASPECT_EXPERIMENT',switch)]:
                                env.pop(name,None)
                                if value is not None:env[name]=value
                            expected=((program=='010090C022978003' and build=='e1bced80ffd14436980f7490b1d3c3e7') or (program=='010090C022978001' and build=='badf2faf580b712464365c4d529d92c9')) and switch=='1'
                            with self.subTest(program=program,preload=preload,build=build,switch=switch):
                                p=subprocess.run([str(exe),build,str(int(expected))],env=env,capture_output=True,text=True)
                                self.assertEqual(p.returncode,0,p.stdout+p.stderr)


if __name__=='__main__':unittest.main()
