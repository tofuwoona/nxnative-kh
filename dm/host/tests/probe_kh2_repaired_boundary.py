#!/usr/bin/env python3
"""Native CPU slices with actual production cuts/policy. No game/module rewrite.
The inverse positive body is a reachability counter, not a replacement transform.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import struct
import sys
import probe_kh2_failure_boundary as original
from run_kh2_sync import command_ok

ROOT=Path(__file__).resolve().parents[3]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--elf',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();out=args.out.resolve()
    if ROOT==out or ROOT in out.parents:raise ValueError('outputs must be outside checkout')
    out.mkdir(parents=True,exist_ok=False)
    image=original.elf_image(args.elf.read_bytes());original.validate_words(image)
    spec=importlib.util.spec_from_file_location('repair',ROOT/'dm/games/010090C022978000/patches.py')
    assert spec and spec.loader
    table=importlib.util.module_from_spec(spec);spec.loader.exec_module(table)
    for off,ident,word,why in table.WRAPS[table.build]:
        assert struct.unpack_from('<I',image,off)[0]==int(word,16),(hex(off),'original wrapper byte assertion')
    for off,old,new,why in table.CUTS[table.build]:
        old=bytes.fromhex(old);new=bytes.fromhex(new)
        assert image[off:off+len(old)]==old,hex(off)
        image[off:off+len(new)]=new
    asm=original.assembly(image)
    asm=asm.replace('    bl _probe_commit // result injected at original call boundary','    bl Lrepair_commit')
    for off,label in [(0x2dbd0,'finish'),(0x41044,'close')]:
        word=struct.unpack_from('<I',image,off)[0]
        asm=asm.replace(f'    .long 0x{word:08x} // main+{off:x}',f'    bl Lrepair_{label}')
    for name,reg in [('commit','x19'),('finish','x19'),('close','x23')]:
        asm+=f'''\nLrepair_{name}:
    stp x29, x30, [sp, #-16]!
    mov x1, {'x23' if name=='commit' else 'x0'}
    mov x0, {reg}
    bl _repair_{name}
    ldp x29, x30, [sp], #16
    ret
'''
    # All private SVCs have been redirected at the same bounded call seams.
    assert '.long 0xd40fe0' not in asm
    source=out/'repaired-slices.S';source.write_text(asm)
    env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0','UBSAN_OPTIONS':'halt_on_error=1'}
    subprocess.run([sys.executable,str(ROOT/'dm/games/game.py'),'header',
                    str(ROOT/'dm/games/010090C022978000/direct-profiles/010090C022978003'),str(out/'game_profile.h')],check=True,env=env)
    runs=[]
    for mode,flags in [('plain',[]),('asan-ubsan',['-fsanitize=address,undefined','-fno-omit-frame-pointer'])]:
        exe=out/mode
        subprocess.run(['clang','-O1','-g','-Wall','-Wextra','-Werror',*flags,'-I'+str(out),
                        str(Path(__file__).with_name('t_kh2_repaired_boundary.c')),str(source),'-o',str(exe)],check=True,env=env)
        cp=subprocess.run([str(exe)],text=True,capture_output=True,env=env)
        (out/(mode+'.log')).write_text(cp.stdout+cp.stderr);print(cp.stdout+cp.stderr,end='')
        runs.append(dict(mode=mode,exit=cp.returncode,ok=command_ok(cp.returncode,cp.stdout+cp.stderr)))
    (out/'manifest.json').write_text(json.dumps(dict(scope='CPU instruction-slice/call-seam only, not gameplay or full PNG encoder',runs=runs),indent=2)+'\n')
    return int(any(not r['ok'] for r in runs))
if __name__=='__main__':sys.exit(main())
