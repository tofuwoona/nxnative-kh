#!/usr/bin/env python3
"""Execute the actual UIKit frame RHS as C; no UIKit runtime/device required."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
source = (ROOT / 'dm/ios/Sources/front_ios.m').read_text()
# Fail closed if layout stops using these assignments. Compile their RHS verbatim,
# rather than testing symbol presence or a handwritten copy of the image policy.
frame_rhs, = re.findall(r'self\.game\.frame\s*=\s*([^;]+);', source)
layout_rhs, = re.findall(r'dm_aspect_rect f\s*=\s*([^;]+);', source)
harness = r'''
#include <math.h>
#include <stdio.h>
#include "aspect_fill.h"
static dm_aspect_rect CGRectMake(double x, double y, double w, double h) {
    return (dm_aspect_rect){x,y,w,h};
}
static dm_aspect_rect image(double w, double h, double l, double t, double r, double bot) {
    struct { struct { double width, height; } size; } b = {{w,h}};
    struct { double left, top, right, bottom; } a = {l,t,r,bot};
    dm_aspect_rect f = LAYOUT_RHS;
    return FRAME_RHS;
}
static int same(double actual, double expected, const char *field, int keep, int fill) {
    if (fabs(actual-expected) < 1e-8) return 1;
    fprintf(stderr, "FAIL %s preserve=%d fill=%d: got %.12f expected %.12f\n",
            field, keep, fill, actual, expected);
    return 0;
}
int main(void) {
    const double sizes[][6] = {
        {852,393,59,0,0,21}, {852,393,0,0,59,21},
        {393,852,0,59,0,34}, {852.5,393.25,59.5,0.25,0,21.5},
        {1920,1080,0,0,0,0}
    };
    unsigned cases=0, failed=0;
    for (int keep=-1; keep<=1; keep++) for (int fill=0; fill<=1; fill++) {
        if (keep<0) unsetenv("DM_PRESERVE_FULL_HUD");
        else setenv("DM_PRESERVE_FULL_HUD",keep?"1":"0",1);
        setenv("DM_ASPECT_FILL",fill?"1":"0",1);
        // Independent profile oracle, not dm_preserve_full_hud_on().
        int preserve = keep==1 && DM_GAME_PROGRAM_ID==0x010090C022978003ull;
        for (unsigned i=0; i<sizeof sizes/sizeof *sizes; i++) {
            const double *s=sizes[i];
            double x=preserve?s[2]:0, y=preserve?s[3]:0;
            double aw=s[0]-(preserve?s[2]+s[4]:0);
            double ah=s[1]-(preserve?s[3]+s[5]:0);
            double w=aw, h=ah;
            if (preserve || !fill) {
                double scale=fmin(aw/16,ah/9); w=16*scale; h=9*scale;
                x+=(aw-w)/2; y+=(ah-h)/2;
            }
            dm_aspect_rect actual=image(s[0],s[1],s[2],s[3],s[4],s[5]);
            // Original image placement floors origins only; input was fractional.
            failed+=!same(actual.x,preserve?x:floor(x),"image.x",keep,fill);
            failed+=!same(actual.y,preserve?y:floor(y),"image.y",keep,fill);
            failed+=!same(actual.w,w,"image.w",keep,fill);
            failed+=!same(actual.h,h,"image.h",keep,fill);
            dm_aspect_rect touch=dm_aspect_frame(s[0],s[1],s[2],s[3],s[4],s[5]);
            failed+=!same(touch.x,x,"fractional touch.x",keep,fill);
            failed+=!same(touch.y,y,"fractional touch.y",keep,fill);
            for (int corner=0; corner<5; corner++) {
                double u=corner==4?0.5:(corner&1), v=corner==4?0.5:((corner>>1)&1);
                double nx,ny,ox=0,oy=0,fx=1,fy=1;
                if (!preserve && fill) {
                    fx=fmin(1,(w/h)/(16.0/9)); fy=fmin(1,(16.0/9)/(w/h));
                    ox=(1-fx)/2; oy=(1-fy)/2;
                }
                // Preserve uses the *actual image* corners, proving image/input agree.
                double px=preserve?actual.x:x, py=preserve?actual.y:y;
                dm_aspect_touch(touch,px+u*w,py+v*h,&nx,&ny);
                failed+=!same(nx,ox+u*fx,"touch.nx",keep,fill);
                failed+=!same(ny,oy+v*fy,"touch.ny",keep,fill);
            }
            cases++;
        }
    }
    printf("%s %u actual iOS frame cases, %u failed comparisons (profile %llx)\n",
           failed?"FAIL":"PASS",cases,failed,(unsigned long long)DM_GAME_PROGRAM_ID);
    return failed?1:0;
}
'''.replace('LAYOUT_RHS', layout_rhs).replace('FRAME_RHS', frame_rhs)
with tempfile.TemporaryDirectory(prefix='kh2-ios-frame-', dir=os.environ.get('TMPDIR', str(Path.home()/'.hermes/cache/scratch'))) as d:
    src = Path(d)/'frame.c'
    src.write_text(harness)
    failed = False
    for profile in ('0x010090C022978003ull', '0x010090C022978001ull'):
        exe = Path(d)/'frame'
        subprocess.run(['clang', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                        '-I'+str(ROOT/'dm/host'), '-DDM_GAME_PROGRAM_ID='+profile,
                        str(src), '-o', str(exe)], check=True)
        failed |= subprocess.run([str(exe)]).returncode != 0
    raise SystemExit(1 if failed else 0)
