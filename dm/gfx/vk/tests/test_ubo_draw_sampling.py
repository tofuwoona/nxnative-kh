#!/usr/bin/env python3
"""CPU-only execution of the real vk_trace_ubo body. Fake CPU buffer, no Metal.
Usage: test_ubo_draw_sampling.py SOURCE_ROOT OUT_DIR [--legacy]
--legacy proves the original sparse sampler's same-submit omission.
"""
import os,re,subprocess,sys
from pathlib import Path
root,out=map(Path,sys.argv[1:3]); out.mkdir(parents=True,exist_ok=True)
s=(root/'dm/gfx/vk/hle_vk.m').read_text()
start=s.index('static void vk_trace_ubo(rs_t *s,')
end=s.index('\nstatic void bind_res(',start)
body=s[start:end]
preamble=r'''
#import <Foundation/Foundation.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>
@interface CPUBuffer : NSObject { NSMutableData *_data; }
@property(readonly) void *contents;
@property(readonly) NSUInteger length;
@end
@implementation CPUBuffer
- (id)init { if ((self=[super init])) _data=[NSMutableData dataWithLength:1024]; return self; }
- (void *)contents { return _data.mutableBytes; }
- (NSUInteger)length { return _data.length; }
@end
static _Atomic uint64_t g_frames,g_n_pass,g_n_draw;
typedef uint64_t VkDeviceSize;
typedef struct { uint64_t v; } SQ;
typedef struct { SQ *sq; } rs_t;
typedef struct { const char *key; } shinfo;
typedef struct { char kind; uint8_t set,slot,count; uint16_t binding; } shres;
typedef struct { CPUBuffer *buf; VkDeviceSize off; } desc_t;
#define VLOG(...) do { printf(__VA_ARGS__); putchar('\n'); } while(0)
'''
main=r'''
int main(int argc,char **argv) { @autoreleasepool {
    unsetenv("DM_VK_UBOTRACE"); unsetenv("DM_VK_UBOTRACE_DRAWS");
    setenv("DM_VK_UBOTRACE_MIN_SUBMIT","10",1);
    if (strcmp(argv[1],"disabled")) setenv("DM_VK_UBOTRACE","1",1);
    if (!strcmp(argv[1],"on") || !strcmp(argv[1],"cap") || !strcmp(argv[1],"bounds")) setenv("DM_VK_UBOTRACE_DRAWS","1",1);
    if (!strcmp(argv[1],"off")) setenv("DM_VK_UBOTRACE_DRAWS","0",1);
    SQ q={10}; rs_t st={&q}; shinfo si={"d7a52a49f521f4f0"}; shres r={'u',0,0,1,3};
    desc_t e={[CPUBuffer new],0}; memset(e.buf.contents,0,1024);
    memset((char *)e.buf.contents+512,0x3f,448);
    g_frames=42; g_n_pass=7;
    int count=!strcmp(argv[1],"cap")?140:2;
    for(int i=0;i<count;i++) {
        g_n_draw=(uint64_t)i;
        uint64_t off=(i&1)?512:0;
        if(!strcmp(argv[1],"bounds")) off=900;
        vk_trace_ubo(&st,&si,&r,&e,off,0);
    }
    (void)argc; return 0;
} }
'''
source=out/'ubo_cpu.m'; source.write_text(preamble+body+main)
exe=out/'ubo_cpu'
cmd=['clang','-fobjc-arc','-fsanitize=address,undefined','-framework','Foundation',str(source),'-o',str(exe)]
c=subprocess.run(cmd,text=True,capture_output=True); (out/'compile.log').write_text(' '.join(cmd)+'\n'+c.stdout+c.stderr); c.check_returncode()
legacy='--legacy' in sys.argv
failures=[]
for mode in ('disabled','default','off','on','cap','bounds'):
    r=subprocess.run([str(exe),mode],text=True,capture_output=True)
    (out/(mode+'.log')).write_text(r.stdout+r.stderr)
    assert r.returncode==0 and not re.search('AddressSanitizer|runtime error:|UndefinedBehaviorSanitizer',r.stderr),(mode,r.stderr)
    decoded=r.stdout.count('[UBOTRACE]')
    raw=[l for l in r.stdout.splitlines() if '[UBOTRACE-DRAW]' in l]
    trunc=r.stdout.count('[UBOTRACE-DRAW-LIMIT]')
    expected=0 if mode in ('disabled','bounds') else 128 if mode=='cap' and not legacy else 2 if mode=='on' and not legacy else 1
    ok=decoded==expected
    if not legacy:
        ok &= len(raw)==(128 if mode=='cap' else 2 if mode=='on' else 0)
        ok &= trunc==(1 if mode=='cap' else 0)
        if mode=='on' and len(raw)==2:
            ok &= 'offset=0 ' in raw[0] and 'offset=512 ' in raw[1]
            ok &= 'draw_counter=0 ' in raw[0] and 'draw_counter=1 ' in raw[1]
            ok &= 'frame=42 submit=10 pass=7 ' in raw[0]
            ok &= raw[0].split('hex=')[-1]=='00'*448 and raw[1].split('hex=')[-1]=='3f'*448
    print(('PASS' if ok else 'FAIL'),mode,'decoded',decoded,'draw_prefixes',len(raw),'limit_records',trunc,'expected decoded',expected)
    if not ok: failures.append(mode)
assert not failures,failures
