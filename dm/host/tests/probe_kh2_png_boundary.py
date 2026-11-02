#!/usr/bin/env python3
"""Pinned original writer/error/fwrite CPU slices, NOT a PNG encoder/game run.
Original mapped writer instructions execute; only PNG APIs, FILE creation/close,
SDK stream lock/write callbacks and PC-relative data addresses are call seams.
No NSO rewrite: generated assembly stays in caller-owned private output.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import capstone
from run_kh2_sync import command_ok
ROOT=Path(__file__).resolve().parents[3]
HASHES={'main':'c052aeef9f049e842fb68b69d14cef50c3290a063bd7ad1200cf263f2dcdd8c3',
        'sdk':'91dc388bd85060c4a07f4c6e494c4f6e10a707436ff49d768725c79bdc8cb702'}

def assembly(main,sdk,program='kh2'):
    cs=capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_ARM)
    data={0x40f08:'adrp x23,_slice_flag@PAGE',0x40f10:'add x23,x23,_slice_flag@PAGEOFF',
          0x40f20:'adrp x1,_slice_string@PAGE',0x40f24:'add x1,x1,_slice_string@PAGEOFF',
          0x40f34:'adrp x0,_slice_string@PAGE',0x40f38:'add x0,x0,_slice_string@PAGEOFF',
          0x40fc4:'adrp x8,_slice_string@PAGE',0x40fc8:'add x8,x8,_slice_string@PAGEOFF',
          0x40fcc:'adrp x9,_slice_string@PAGE',0x40fd0:'add x9,x9,_slice_string@PAGEOFF',
          0x350f6c:'adrp x1,_slice_string@PAGE',0x350f70:'add x1,x1,_slice_string@PAGEOFF'}
    calls={0x3ff0b0:'_slice_open',0x351690:'_slice_create',0x343ff0:'_slice_info',
           0x3444e0:'_slice_init_io',0x3514f0:'_slice_write_end',0x351d40:'_slice_destroy',
           0x3ff0c0:'_slice_close',0x400210:'_slice_sdk_fwrite',0x345900:'_slice_png_error',
           0x345940:'_slice_default_error',0x56dfe0:'_slice_lock',0x56e010:'_slice_unlock',
           0x595e20:'_slice_unexpected',0x644ef0:'_memcpy'}
    # The remaining original writer PNG API calls are explicit no-encoder seams.
    for target in [0x34f750,0x34fc30,0x3502a0,0x34ff10,0x3511d0,0x352910,0x351bc0]:calls[target]='_slice_noop'
    cap={0x40f30:'file',0x40f40:'error',0x40f4c:'png',0x40f58:'info',0x41030:'handoff'}
    text=['.text','.p2align 2']
    spans=[('writer',main,0x40ef0,0x41060),('default_write',main,0x350f30,0x350f7c),
           ('png_error',main,0x345900,0x345938),('sdk_fwrite',sdk,0x597e20,0x597fb4)]
    close_site=0x41044
    continuation=0x40ef4
    if program=='kh1':
        # Independent Program1 map. Shared SDK span is digest-verified below.
        data={0x3e008:'adrp x23,_slice_flag@PAGE',0x3e010:'add x23,x23,_slice_flag@PAGEOFF',
              0x3e020:'adrp x1,_slice_string@PAGE',0x3e024:'add x1,x1,_slice_string@PAGEOFF',
              0x3e034:'adrp x0,_slice_string@PAGE',0x3e038:'add x0,x0,_slice_string@PAGEOFF',
              0x3e0c4:'adrp x8,_slice_string@PAGE',0x3e0c8:'add x8,x8,_slice_string@PAGEOFF',
              0x3e0cc:'adrp x9,_slice_string@PAGE',0x3e0d0:'add x9,x9,_slice_string@PAGEOFF',
              0x2e0afc:'adrp x1,_slice_string@PAGE',0x2e0b00:'add x1,x1,_slice_string@PAGEOFF'}
        calls={0x2f0060:'_slice_open',0x2e1220:'_slice_create',0x2d3b80:'_slice_info',
               0x2d4070:'_slice_init_io',0x2e1080:'_slice_write_end',0x2e18d0:'_slice_destroy',
               0x2f00a0:'_slice_close',0x2f0070:'_slice_sdk_fwrite',0x2d5490:'_slice_png_error',
               0x2d54d0:'_slice_default_error',0x56dfe0:'_slice_lock',0x56e010:'_slice_unlock',
               0x595e20:'_slice_unexpected',0x644ef0:'_memcpy'}
        for target in [0x2df2e0,0x2df7c0,0x2dfe30,0x2dfaa0,0x2e0d60,0x2e24a0,0x2e1750]:calls[target]='_slice_noop'
        cap={0x3e030:'file',0x3e040:'error',0x3e04c:'png',0x3e058:'info',0x3e130:'handoff'}
        spans=[('writer',main,0x3dff0,0x3e160),('default_write',main,0x2e0ac0,0x2e0b0c),
               ('png_error',main,0x2d5490,0x2d54c8),('sdk_fwrite',sdk,0x597e20,0x597fb4)]
        close_site=0x3e144
        continuation=0x3dff4
    for name,image,lo,hi in spans:
        text += [f'.globl _slice_{name}',f'_slice_{name}:']
        for ins in cs.disasm(image[lo:hi],lo):
            off=ins.address;text += [f'L{off:x}:']
            if off in cap:line='b Lcapture_'+cap[off]
            elif off==close_site:line='bl _slice_close_status' # existing repaired close seam
            elif off in data:line=data[off]
            elif ins.mnemonic=='bl':line='bl '+calls[int(ins.op_str[1:],16)]
            elif ins.mnemonic in ['b','b.eq','b.ne','b.hs','b.lo','b.ge','b.lt','b.hi','b.le']:
                line=ins.mnemonic+' L'+ins.op_str[1:].removeprefix('0x')
            elif ins.mnemonic in ['cbz','cbnz','tbz','tbnz']:
                left,target=ins.op_str.rsplit(', #',1);line=ins.mnemonic+' '+left+', L'+target.removeprefix('0x')
            else:line=f'.long 0x{struct.unpack("<I",ins.bytes)[0]:08x}'
            text += ['    '+line+f' // original {off:x}']
    def gate(name,after):
        return [f'{name}:','    stp x29,x30,[sp,#-16]!',
                '    adrp x30,_dm_gate@PAGE','    add x30,x30,_dm_gate@PAGEOFF',
                '    nop','    nop','    nop','    nop','    blr x30',
                f'.globl _slice_ret_{name}',f'_slice_ret_{name}:','    ldp x29,x30,[sp],#16',after]
    text += ['.globl _slice_wrapped',*gate('_slice_wrapped','    ret')]
    # This body is the actual displaced original first instruction + continuation.
    text += ['.globl _slice_body','_slice_body:','    sub sp,sp,#0x90',f'    b L{continuation:x}']
    for off,name in cap.items():text += gate('Lcapture_'+name,f'    b L{off+4:x}')
    return '\n'.join(text)+'\n'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--main',type=Path,required=True)
    p.add_argument('--sdk',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--program',choices=['kh1','kh2'],default='kh2')
    a=p.parse_args();out=a.out.resolve()
    if out==ROOT or ROOT in out.parents:raise ValueError('private output required')
    out.mkdir(parents=True,exist_ok=False)
    hashes=dict(HASHES)
    if a.program=='kh1':hashes['main']='ea087b91d8227ea29442fc311a7345d0ba89fb43e0b228c2c35c91f2939e20aa'
    blobs={n:getattr(a,n).read_bytes() for n in hashes}
    for n,h in hashes.items():assert hashlib.sha256(blobs[n]).hexdigest()==h,n+' artifact digest mismatch'
    spec=importlib.util.spec_from_file_location('pngpatch',ROOT/'dm/games/010090C022978000/patches.py')
    assert spec and spec.loader
    table=importlib.util.module_from_spec(spec);spec.loader.exec_module(table)
    build=table.kh1_build if a.program=='kh1' else table.build
    for off,ident,word,why in table.WRAPS[build]:assert struct.unpack_from('<I',blobs['main'],off)[0]==int(word,16),hex(off)
    for off,old,new,why in table.CUTS[build]:assert blobs['main'][off:off+len(bytes.fromhex(old))]==bytes.fromhex(old),hex(off)
    source=out/'slices.S';source.write_text(assembly(blobs['main'],blobs['sdk'],a.program))
    env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0','UBSAN_OPTIONS':'halt_on_error=1','PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(out)}
    runs=[]
    def run(label,cmd,expected=0):
        cp=subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
        log=cp.stdout+cp.stderr;(out/(label+'.log')).write_text(log)
        ok=command_ok(cp.returncode,log,expected)
        runs.append(dict(label=label,command=list(map(str,cmd)),exit=cp.returncode,expected=expected,ok=ok));print(label,cp.returncode,log[-500:],flush=True)
        return ok
    gid='010090C022978001' if a.program=='kh1' else '010090C022978003'
    assert run('profile',[sys.executable,ROOT/'dm/games/game.py','header',ROOT/'dm/games/010090C022978000/direct-profiles'/gid,out/'game_profile.h'])
    for tag,flags in [('plain',[]),('san',['-fsanitize=address,undefined','-fno-omit-frame-pointer'])]:
        exe=out/tag
        cmd=['clang','-O1','-g','-Wall','-Wextra','-Werror','-I'+str(out),*flags,ROOT/'dm/host/tests/t_kh2_png_slices.c',source,ROOT/'dm/host/entry.S',ROOT/'dm/host/hle_bigstack.c','-o',exe]
        if run(tag+'-build',cmd):
            run(tag,[exe]);run(tag+'-default-negative',[exe,'--default-negative'],expected=-6)
    (out/'results.json').write_text(json.dumps(dict(scope=__doc__,program=a.program,hashes=hashes,runs=runs),indent=2)+'\n')
    return int(any(not r['ok'] for r in runs))
if __name__=='__main__':sys.exit(main())
