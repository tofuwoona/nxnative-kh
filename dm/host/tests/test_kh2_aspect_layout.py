#!/usr/bin/env python3
"""Execute extracted production layout/touch/present expressions, CPU only.
UIKit/Metal types and the UI/guest callback boundary are plain test substitutes.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from kh2_mask_fixture import C as MASK_FIXTURE, write_image
from test_kh2_aspect import ROOT, function


class LayoutTests(unittest.TestCase):
    def test_layout_input_present(self):
        ios = (ROOT/'dm/ios/Sources/front_ios.m').read_text()
        pad = (ROOT/'dm/ios/Sources/DmGamepad.m').read_text()
        mac = (ROOT/'dm/host/front_mac.m').read_text()
        mtl = (ROOT/'dm/gfx/nvn/nvn_mtl.m').read_text()
        oe = (ROOT/'dm/host/hle_oe.c').read_text()
        gate = oe[oe.index('static _Atomic uint64_t g_kh2_aspect'):oe.index('// ---------- System notification')]
        layout = ios.split('CGRect b = self.view.bounds; if (!self.game) return;',1)[1].split('    if (self.fps)',1)[0].replace('self.game.frame =','return')
        ipre = pad.split('- (void)pushGame {',1)[1].split('    dm_touch t[16]',1)[0].replace('self.bounds','bounds').replace('return;','return (Point){0,0};')
        ipoint = pad.split('CGPoint p = [_game[i] locationInView:self];',1)[1].split('        t[n++]',1)[0]
        mpre = mac.split('- (void)mouseDragged:(NSEvent *)e {',1)[1].split('    dm_touch t =',1)[0]
        mpre = mpre[mpre.index('    double w = b.width'):].replace('return;','return (Point){0,0};')
        # Startup callback ordering is covered separately by test_kh2_adaptive_startup.
        present = function(mtl,'static MTLViewport present_fit(')
        harness = r'''
#include <math.h>
#include <stdio.h>
#include <assert.h>
#include <stdatomic.h>
#include "dm.h"
#include "kh2_aspect.h"
#include "aspect_fill.h"
module_t g_mod[MAX_MOD]; int g_nmod;
static int dm_kh1_bar_apply(int on) {(void)on;return 1;}
GATE
typedef double CGFloat;
typedef struct { double x,y; } Point;
typedef struct { double x,y,w,h; } Rect;
typedef struct { struct { double width,height; } size; } Bounds;
typedef Bounds CGRect;
typedef struct { double originX,originY,width,height,znear,zfar; } MTLViewport;
static Rect CGRectMake(double x,double y,double w,double h) {return (Rect){x,y,w,h};}
// Legacy constants keep old touch code executable for behavior RED.
enum { DM_KH2_ASPECT_WIDTH = 1704, DM_KH2_ASPECT_HEIGHT = 786 };
static Rect image(Bounds b) { LAYOUT }
static Point ios_touch(Bounds bounds,Point p) { IPRE IPOINT return (Point){nx,ny}; }
static Point mac_touch(double width,double height,Point p) {
    struct {double width,height;} b={width,height}; MPRE return (Point){nx,ny};
}
PRESENT
static int expect_wide;
static unsigned failures,cases;
static void same(double a,double b) {if(fabs(a-b)>1e-8) {if(failures<12) fprintf(stderr,"got %.12f expected %.12f\n",a,b); failures++;}}
int main(int argc, char **argv) {
 assert(argc==5);
 int vw=atoi(argv[1]),vh=atoi(argv[2]),rw=atoi(argv[3]),rh=atoi(argv[4]);
 test_mask_load(&g_mod[0]);
 const double sizes[][2]={{852,393},{2556,1179},{852.5,393.25},{393,852},{1920,1080},{1024,768}};
 const char *builds[]={"", "unknown", "e1bced80ffd14436980f7490b1d3c3e7", "badf2faf580b712464365c4d529d92c9"};
 for(unsigned build=0;build<4;build++) for(int wide=-1;wide<=1;wide++) for(int fill=-1;fill<=1;fill++) {
  if(wide<0) unsetenv("DM_KH2_ASPECT_EXPERIMENT"); else setenv("DM_KH2_ASPECT_EXPERIMENT",wide?"1":"0",1);
  if(fill<0) unsetenv("DM_ASPECT_FILL"); else setenv("DM_ASPECT_FILL",fill?"1":"0",1);
  g_nmod=1; snprintf(g_mod[0].name,sizeof g_mod[0].name,"main"); snprintf(g_mod[0].build_id,sizeof g_mod[0].build_id,"%s",builds[build]);
  dm_kh2_aspect_init(vw,vh);
  expect_wide=((DM_GAME_PROGRAM_ID==0x010090C022978003ull && build==2) ||
               (DM_GAME_PROGRAM_ID==0x010090C022978001ull && build==3)) && wide==1;
  same(dm_kh2_aspect_on(),expect_wide);
  // The crop preference is not rewritten by the experiment.
  same(!!dm_aspect_fill_on(),fill==1);
  for(unsigned i=0;i<sizeof sizes/sizeof *sizes;i++) {
   double w=sizes[i][0],h=sizes[i][1],fw=w,fh=h;
   if(!expect_wide && fill!=1) {if(w/h>16.0/9) fw=h*16.0/9; else fh=w*9.0/16;}
   Rect a=image((Bounds){{w,h}});
   same(a.x,floor((w-fw)/2));same(a.y,floor((h-fh)/2));same(a.w,fw);same(a.h,fh);
   double sw=expect_wide?rw:1920,sh=expect_wide?rh:1080;
   double cx=0,cy=0,cw=sw,ch=sh;
   MTLViewport v=present_fit(0,0,sw,sh,w,h,&cx,&cy,&cw,&ch);
   if(expect_wide) {double s=fmin(w/sw,h/sh);same(cx,0);same(cy,0);same(cw,sw);same(ch,sh);
    same(v.originX,(w-sw*s)/2);same(v.originY,(h-sh*s)/2);same(v.width,sw*s);same(v.height,sh*s);}
   else if(fill==1) {double s=fmax(w/sw,h/sh);same(v.originX,0);same(v.originY,0);same(v.width,w);same(v.height,h);same(cw,w/s);same(ch,h/s);}
   else {double s=fmin(w/sw,h/sh);double x=floor((w-sw*s)/2),y=floor((h-sh*s)/2),vw=round(sw*s),vh=round(sh*s);
    if(fabs((w/h)/(sw/sh)-1)<0.01) {x=y=0;vw=w;vh=h;} same(v.originX,x);same(v.originY,y);same(v.width,vw);same(v.height,vh);same(cw,sw);same(ch,sh);}
   double tx=(w-fw)/2,ty=(h-fh)/2,tw=fw,th=fh,ox=0,oy=0,fx=1,fy=1;
   if(expect_wide) {tx=v.originX;ty=v.originY;tw=v.width;th=v.height;}
   else if(fill==1) {fx=fmin(1,(w/h)/(16.0/9));fy=fmin(1,(16.0/9)/(w/h));ox=(1-fx)/2;oy=(1-fy)/2;}
   for(int k=0;k<7;k++) {double u=k==4?.5:k==5?-1:k==6?2:(k&1),vv=k==4?.5:k==5?-1:k==6?2:((k>>1)&1);
    Point p={tx+u*tw,ty+vv*th},it=ios_touch((Bounds){{w,h}},p),mt=mac_touch(w,h,(Point){p.x,h-p.y});
    double nx=ox+fmin(fmax(u,0),1)*fx,ny=oy+fmin(fmax(vv,0),1)*fy;
    same(it.x,nx);same(it.y,ny);same(mt.x,nx);same(mt.y,ny);
   }
   cases++;
  }

 }
 printf("production layout/present/input: %u cases, %u failures, profile %llx\n",cases,failures,(unsigned long long)DM_GAME_PROGRAM_ID);
 return failures?1:0;
}
'''
        for key,val in [('GATE',MASK_FIXTURE+gate),('LAYOUT',layout),('IPRE',ipre),('IPOINT',ipoint),('MPRE',mpre),('PRESENT',present)]: harness=harness.replace(key,val)
        # Baseline has no calls to UI stubs; allow unused-function for the RED build only.
        with tempfile.TemporaryDirectory(prefix='kh2-layout-',dir=os.environ['TMPDIR']) as tmp:
            tmp=Path(tmp); src=tmp/'t.c';src.write_text(harness)
            image=write_image(tmp)
            for program in ('010090C022978003','010090C022978001','010090C022978000'):
                env=dict(os.environ, DM_GAMES_DIR=str(ROOT/'dm/games/010090C022978000/direct-profiles'),DM_GAMES_FIRST='1')
                subprocess.run(['python3',str(ROOT/'dm/games/game.py'),'header',program,str(tmp/'game_profile.h')],env=env,check=True,capture_output=True)
                exe=tmp/'t'
                subprocess.run(['clang','-fblocks','-Wall','-Wextra','-Werror','-Wno-unused-function','-fsanitize=address,undefined','-I'+str(tmp),'-I'+str(ROOT/'dm/host'),str(src),'-o',str(exe)],check=True)
                if program == '010090C022978001':
                    viewports=[(2556,1179,1561,720),(1920,1080,1280,720),(2400,1080,1600,720),(2532,1170,1558,720),(2796,1290,1561,720)]
                else:
                    viewports=[(2556,1179,1704,786),(1920,1080,1920,1080),(2400,1080,1920,864),(2532,1170,1688,780),(2796,1290,1864,860)]
                for viewport in viewports:
                    with self.subTest(program=program,viewport=viewport):
                        p=subprocess.run([str(exe),*map(str,viewport)],env=dict(os.environ,KH2_MASK_IMAGE=image),capture_output=True,text=True)
                        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                        print(p.stdout.strip())


if __name__=='__main__': unittest.main()
