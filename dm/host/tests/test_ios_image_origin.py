#!/usr/bin/env python3
"""Run actual iOS image and iOS/Mac touch expressions against the old fit/crop oracle.
No app build, UIKit runtime, GPU, device or save access.
"""
import os
from pathlib import Path

import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
for folder in ('dm/host', 'dm/ios/Sources', 'dm/gfx'):
    for path in (ROOT / folder).rglob('*'):
        if 'tests' not in path.parts and path.suffix in ('.c', '.h', '.m', '.swift'):
            assert 'DM_PRESERVE_FULL_HUD' not in path.read_text(), str(path) + ': removed HUD runtime override returned'
ios = (ROOT / 'dm/ios/Sources/front_ios.m').read_text()
pad = (ROOT / 'dm/ios/Sources/DmGamepad.m').read_text()
mac = (ROOT / 'dm/host/front_mac.m').read_text()
layout = ios.split('CGRect b = self.view.bounds; if (!self.game) return;', 1)[1].split('    if (self.fps)', 1)[0]
layout = layout.replace('self.view.safeAreaInsets', 'safe').replace('self.game.frame =', 'return')
# Compile production touch geometry and point mapping, omitting only the input sink.
ipre = pad.split('- (void)pushGame {', 1)[1].split('    dm_touch t[16]', 1)[0]
ipre = ipre.replace('self.bounds', 'bounds').replace('self.safeAreaInsets', 'safe').replace('return;', 'return (Point){0,0};')
ipoint = pad.split('CGPoint p = [_game[i] locationInView:self];', 1)[1].split('        t[n++]', 1)[0]
mpre = mac.split('- (void)mouseDragged:(NSEvent *)e {', 1)[1].split('    dm_touch t =', 1)[0]
mpre = mpre[mpre.index('    double w = b.width'):].replace('return;', 'return (Point){0,0};')
harness = r'''
#include <math.h>
#include <stdio.h>
#include "aspect_fill.h"
typedef double CGFloat;
typedef struct { double x,y; } Point;
typedef struct { double x,y,w,h; } Rect;
typedef struct { struct { double width,height; } size; } Bounds;
typedef Bounds CGRect;
typedef struct { double left,top,right,bottom; } UIEdgeInsets;
static Rect CGRectMake(double x,double y,double w,double h) { return (Rect){x,y,w,h}; }
static Rect image(Bounds b, UIEdgeInsets safe) {
    (void)safe;
    LAYOUT
}
static Point ios_touch(Bounds bounds, UIEdgeInsets safe, Point p) {
    (void)safe;
    IPRE
    IPOINT
    return (Point){nx,ny};
}
static Point mac_touch(double width,double height,Point p) {
    struct {double width,height;} b = {width,height};
    MPRE
    return (Point){nx,ny};
}
static unsigned failed;
static void same(double a,double b) { if(fabs(a-b)>1e-8) { failed++; fprintf(stderr,"got %.12f expected %.12f\n",a,b); } }
int main(void) {
    const double sizes[][6] = {{852,393,59,0,0,21},{852,393,0,0,59,21},
        {393,852,0,59,0,34},{852.5,393.25,59.5,0.25,0,21.5},{1920,1080,0,0,0,0},{1024,768,0,0,0,0}};
    unsigned cases=0;
    for(int keep=-1;keep<=1;keep++) for(int fill=-1;fill<=1;fill++) {
        if(keep<0) unsetenv("DM_PRESERVE_FULL_HUD"); else setenv("DM_PRESERVE_FULL_HUD",keep?"1":"0",1);
        if(fill<0) unsetenv("DM_ASPECT_FILL"); else setenv("DM_ASPECT_FILL",fill?"1":"0",1);
        same(!!dm_aspect_fill_on(),fill==1);
        for(unsigned i=0;i<sizeof sizes/sizeof *sizes;i++) {
            const double *s=sizes[i]; double w=s[0],h=s[1],fw=w,fh=h;
            if(fill!=1) { double scale=fmin(w/16,h/9); fw=16*scale; fh=9*scale; }
            double x=(w-fw)/2,y=(h-fh)/2;
            Bounds b={{w,h}}; UIEdgeInsets safe={s[2],s[3],s[4],s[5]};
            Rect a=image(b,safe);
            same(a.x,floor(x)); same(a.y,floor(y)); same(a.w,fw); same(a.h,fh);
            double fx=fill==1?fmin(1,(w/h)/(16.0/9)):1,fy=fill==1?fmin(1,(16.0/9)/(w/h)):1;
            for(int point=0;point<7;point++) {
                double u=point==4?0.5:point==5?-1:point==6?2:(point&1);
                double v=point==4?0.5:point==5?-1:point==6?2:((point>>1)&1);
                Point p={x+u*fw,y+v*fh};
                Point it=ios_touch(b,safe,p),mt=mac_touch(w,h,(Point){p.x,h-p.y});
                double nx=(1-fx)/2+fmin(fmax(u,0),1)*fx,ny=(1-fy)/2+fmin(fmax(v,0),1)*fy;
                same(it.x,nx); same(it.y,ny); same(mt.x,nx); same(mt.y,ny);
            }
            cases++;
        }
    }
    printf("%s %u actual iOS frame + iOS/Mac input cases, %u failed comparisons (profile %llx)\n",failed?"FAIL":"PASS",cases,failed,(unsigned long long)DM_GAME_PROGRAM_ID);
    return failed?1:0;
}
'''
for token, value in [('LAYOUT', layout), ('IPRE', ipre), ('IPOINT', ipoint), ('MPRE', mpre)]:
    harness = harness.replace(token, value)
with tempfile.TemporaryDirectory(prefix='kh2-aspect-policy-', dir=os.environ['TMPDIR']) as tmp:
    src, exe = Path(tmp) / 'aspect.c', Path(tmp) / 'aspect'
    src.write_text(harness)
    failed = False
    for profile in ('0x010090C022978003ull', '0x010090C022978001ull'):
        subprocess.run(['clang', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                        '-I'+str(ROOT/'dm/host'), '-DDM_GAME_PROGRAM_ID='+profile,
                        str(src), '-o', str(exe)], check=True)
        failed |= subprocess.run([str(exe)]).returncode != 0
    raise SystemExit(1 if failed else 0)
