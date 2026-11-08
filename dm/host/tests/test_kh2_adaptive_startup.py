#!/usr/bin/env python3
"""Execute production front-end startup slices with labeled UI/thread seams.
No UIKit/AppKit/Metal device, app, host executable, or guest is run.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_kh2_aspect import ROOT, function


def run_c(source, args=(), env=None):
    with tempfile.TemporaryDirectory(prefix='adaptive-front-',dir=os.environ['TMPDIR']) as t:
        t=Path(t);(t/'t.c').write_text(source)
        subprocess.run(['clang','-fblocks','-Wall','-Wextra','-Werror','-Wno-unused-function','-fsanitize=address,undefined','-I'+str(ROOT/'dm/host'),str(t/'t.c'),'-o',str(t/'t')],check=True)
        return subprocess.run([str(t/'t'),*args],env=env,capture_output=True,text=True)


class FrontTests(unittest.TestCase):
    def test_ios_full_root_before_guest_and_main_queue_safe(self):
        text=(ROOT/'dm/ios/Sources/front_ios.m').read_text()
        front=function(text,'void front_run(void (*guest)(void))')
        # Substitute only UI access/dispatch; execute the real front_run body.
        replacements={
            '[NSThread isMainThread]':'on_main',
            'g_root.view.bounds.size':'root_bounds',
            'g_root.view.window.screen ?: UIScreen.mainScreen':'test_screen',
            'UIScreen *screen':'Screen *screen',
            '[g_root.view setNeedsLayout]':'mark_layout()',
            '[g_root.view layoutIfNeeded]':'apply_layout()',
            'screen.nativeScale':'screen->nativeScale',
        }
        for a,b in replacements.items(): front=front.replace(a,b)
        c=r'''
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include "kh2_aspect.h"
typedef struct {double width,height;} CGSize;
typedef struct {double nativeScale;} Screen;
static Screen screen_value={3}, *test_screen=&screen_value;
static CGSize root_bounds;
static int on_main,init_count,marks,layouts,dispatches,entered;
static dm_kh2_extent published;
// Loader/payload validation is exercised by the independent real-gate suite.
// Here the init seam proves full-root pixels arrive before layout/guest.
void dm_kh2_aspect_init(uint32_t w,uint32_t h) {
 assert(!entered && !marks && !layouts);init_count++;
 assert(w==(unsigned)(root_bounds.width*3) && h==(unsigned)(root_bounds.height*3));
 published=dm_kh2_aspect_choose(w,h);
}
int dm_kh2_aspect_on(void) {return published.width!=0;}
static int dispatch_get_main_queue(void) {return 1;}
static void dispatch_sync(int queue,void (^block)(void)) {
 assert(!on_main && queue==1);dispatches++;on_main=1;block();on_main=0;
}
static void mark_layout(void) {assert(on_main && init_count==1);marks++;}
static void apply_layout(void) {assert(on_main && marks==1);layouts++;}
static void guest(void) {assert(init_count==1 && marks==1 && layouts==1);entered++;}
FRONT
int main(void) {
 const CGSize cases[]={{852,393},{800,360},{844,390},{932,430}};
 (void)test_screen;
 for(unsigned i=0;i<sizeof cases/sizeof *cases;i++) for(int main=0;main<2;main++) {
  root_bounds=cases[i];on_main=main;published=(dm_kh2_extent){0,0};
  init_count=marks=layouts=dispatches=entered=0;
  front_run(guest);
  assert(entered==1 && dispatches==(main?0:2));
 }
 return 0;
}
'''.replace('FRONT',front)
        p=run_c(c);self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def test_mac_request_controls_actual_window_before_guest(self):
        text=(ROOT/'dm/host/front_mac.m').read_text()
        # Baseline evaluates its actual default content rect; the requested
        # diagnostic viewport must change that geometry, not screenshot output.
        if 'static dm_kh2_extent kh2_viewport_request(void)' in text:
            helper=function(text,'static dm_kh2_extent kh2_viewport_request(void)')
        else:
            rect=next(x.strip() for x in text.splitlines() if 'NSRect r = NSMakeRect' in x)
            helper='static dm_kh2_extent kh2_viewport_request(void) {'+rect+'return (dm_kh2_extent){r.w*2,r.h*2};}'
        c=r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include "kh2_aspect.h"
typedef struct {unsigned w,h;} NSRect;
#define NSMakeRect(x,y,w,h) ((NSRect){w,h})
static void die(const char *fmt,...) {(void)fmt;exit(9);}
HELPER
int main(int argc,char **argv) {
 assert(argc==3);dm_kh2_extent v=kh2_viewport_request();
 assert(v.width==(unsigned)atoi(argv[1]) && v.height==(unsigned)atoi(argv[2]));return 0;
}
'''.replace('HELPER',helper)
        for value in [None,'2556x1179','2400x1080','1920x1080','2532x1170']:
            env=dict(os.environ);env.pop('DM_KH2_VIEWPORT',None)
            if value is not None:env['DM_KH2_VIEWPORT']=value
            dims=value.split('x') if value else ['0','0']
            with self.subTest(value=value):
                p=run_c(c,dims,env);self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        for value in ['', '0x1080','-1920x1080','1920x1080junk','8192x8192','999999999999999999999x1080','1920X1080',' 1920x1080','319x180','320x179']:
            with self.subTest(invalid=value):
                p=run_c(c,['0','0'],dict(os.environ,DM_KH2_VIEWPORT=value));self.assertEqual(p.returncode,9,p.stdout+p.stderr)

    def test_mac_actual_drawable_and_headless_ingress(self):
        text=(ROOT/'dm/host/front_mac.m').read_text()
        front=function(text,'void front_run(void (*guest)(void))')
        block=front[front.index('[win makeKeyAndOrderFront:nil];'):front.index('        g_screen_fps')]
        # UI setter/getter seam only. Arithmetic and ordering remain production.
        block=block.replace('[win makeKeyAndOrderFront:nil]','show_window()').replace('win.backingScaleFactor','backing_scale')
        block=block.replace('[win setContentSize:NSMakeSize(requested.width / scale, requested.height / scale)]','set_content_size(NSMakeSize(requested.width / scale, requested.height / scale))')
        block=block.replace('[(DmGameView *)v fitDrawable]','fit_drawable()')
        helper=function(text,'static dm_kh2_extent kh2_viewport_request(void)')
        headless=function(front,'if (!getenv("DM_WINDOW"))')
        c=r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "kh2_aspect.h"
#define LOG(...) ((void)0)
#define NSMakeSize(w,h) ((Size){w,h})
typedef struct {double width,height;} Size;
static struct {Size drawableSize;} g_layer;
static Size content;
static double backing_scale;
static int shown,fit,init_count,guest_count,rounding;
static dm_kh2_extent input;
static void die(const char *s) {(void)s;abort();}
static void show_window(void) {shown++;}
static void set_content_size(Size s) {assert(shown && !init_count);content=s;}
static void fit_drawable(void) {
 assert(shown && !init_count);fit++;
 g_layer.drawableSize=(Size){content.width*backing_scale+rounding,content.height*backing_scale};
}
void dm_kh2_aspect_init(uint32_t w,uint32_t h) {
 assert(!guest_count && !init_count);init_count++;
 input=(dm_kh2_extent){w,h};
}
static void guest(void) {assert(init_count==1);guest_count++;}
HELPER
static void window(dm_kh2_extent requested) {BLOCK guest();}
static void no_window(void (*guest)(void)) {
 dm_kh2_extent requested=kh2_viewport_request(); HEADLESS
 assert(0);
}
int main(void) {
 const dm_kh2_extent cases[]={{2556,1179},{1920,1080},{2400,1080},{2532,1170}};
 for(unsigned i=0;i<sizeof cases/sizeof *cases;i++) for(int scale=1;scale<=2;scale++) for(int round=0;round<=1;round++) {
  shown=fit=init_count=guest_count=0;rounding=round;backing_scale=scale;content=(Size){1280,720};
  window(cases[i]);
  assert(shown==1 && fit==1 && guest_count==1);
  assert(input.width==cases[i].width+(unsigned)round && input.height==cases[i].height);
 }
 unsetenv("DM_WINDOW");unsetenv("DM_KH2_VIEWPORT");init_count=guest_count=0;
 no_window(guest);assert(input.width==1920 && input.height==1080 && guest_count==1);
 setenv("DM_KH2_VIEWPORT","2556x1179",1);init_count=guest_count=0;
 no_window(guest);assert(input.width==2556 && input.height==1179 && guest_count==1);
 return 0;
}
'''
        for key,value in [('HELPER',helper),('BLOCK',block),('HEADLESS',headless)]:c=c.replace(key,value)
        p=run_c(c);self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def test_mac_init_callsite_is_before_guest_thread(self):
        text=(ROOT/'dm/host/front_mac.m').read_text()
        front=function(text,'void front_run(void (*guest)(void))')
        # Ordering guard complements execution of the exact CPU startup slice.
        self.assertIn('dm_kh2_aspect_init',front)
        self.assertLess(front.index('fitDrawable]'),front.rindex('dm_kh2_aspect_init'))
        self.assertLess(front.rindex('dm_kh2_aspect_init'),front.index('pthread_create(&th'))
        self.assertNotIn('DM_NVN_SHOT_OUT',front)


if __name__=='__main__':unittest.main()
