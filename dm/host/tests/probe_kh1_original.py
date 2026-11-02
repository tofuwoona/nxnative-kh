#!/usr/bin/env python3
"""Optional arm64 macOS original-instruction probe; explicit private NSO inputs.
No game/host build or NSO rewrite. PNG API/FILE calls and inverse positive body
are bounded call seams, not a replacement encoder/transform or gameplay test.
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
import lz4.block
from run_kh2_sync import command_ok

ROOT=Path(__file__).resolve().parents[3]
NSOS={
    'main':('8f3a37500232da3ee4d564970c811f5738c78682f56cbe5bd4a28d177b3528d6','badf2faf580b712464365c4d529d92c9'),
    'sdk':('b0cb6992d78c64b724b2a330cc43a34dfc38d3f4ae4146f2cd06500262d2ad8c','bc204aae7319bab274894f1cc3f5da92'),
    'subsdk1':('4e4b97bc7b864ea91db88c808f654ce247a003a6139081fec546d4fc9f57382e','99e21f98a397434b534c1459fc38a2b8')}

def load_nso(path,name):
    data=path.read_bytes();digest,bid=NSOS[name]
    if hashlib.sha256(data).hexdigest()!=digest or data[:4]!=b'NSO0' or data[0x40:0x50].hex()!=bid:
        raise ValueError(name+' original NSO identity mismatch')
    flags=struct.unpack_from('<I',data,12)[0]
    segs=[struct.unpack_from('<III',data,0x10+i*16) for i in range(3)]
    sizes=struct.unpack_from('<III',data,0x60)
    image=bytearray(segs[2][1]+segs[2][2]+struct.unpack_from('<I',data,0x3c)[0])
    for i,(fo,mo,sz) in enumerate(segs):
        raw=data[fo:fo+sizes[i]]
        if flags>>i&1:raw=lz4.block.decompress(raw,uncompressed_size=sz)
        if len(raw)!=sz or hashlib.sha256(raw).digest()!=data[0xa0+i*32:0xc0+i*32]:
            raise ValueError(name+' segment digest mismatch')
        image[mo:mo+sz]=raw
    return image

def tail_assembly(image,repaired):
    def word(off):return f'    .long 0x{struct.unpack_from("<I",image,off)[0]:08x}\n'
    cs=capstone.Cs(capstone.CS_ARCH_ARM64,0)
    s='.text\n.p2align 2\n.globl _probe_serializer_tail\n_probe_serializer_tail:\n'
    for off in range(0x12af4,0x12b0c,4):s+=word(off)
    s+='    mov x19,x0\n    mov w0,w1\n'
    for ins in cs.disasm(image[0x12c74:0x12cc0],0x12c74):
        off=ins.address;s+=f'L{off:x}:\n'
        if off==0x12c90:s+='    bl Linverse\n'
        elif off in (0x12c94,0x12c98):s+='    nop // unused Commit literal at call seam\n'
        elif off==0x12c9c:s+='    bl '+('Lrepair_commit' if repaired else '_probe_commit')+'\n'
        elif off==0x12ca0 and repaired:s+='    bl Lrepair_finish\n'
        elif ins.mnemonic=='b':s+='    b L'+ins.op_str[1:].removeprefix('0x')+'\n'
        elif ins.mnemonic=='cbz':s+='    cbz w0,L12c80\n'
        else:s+=word(off)
    s+='''Linverse:
    stp x29,x30,[sp,#-32]!
    str w2,[sp,#16]
    mov w0,w2
    bl _probe_note_inverse
    ldr w2,[sp,#16]
'''
    s+=word(0x130e0)+'    b.lt Linverse_return\n    bl _probe_note_inverse_body_reached\nLinverse_return:\n    ldp x29,x30,[sp],#32\n'+word(0x131e8)
    s+='''.globl _probe_writer_close
_probe_writer_close:
    stp x29,x30,[sp,#-32]!
    stp x19,x23,[sp,#16]
    mov x19,x0
    mov x23,x1
'''
    s+=word(0x3e13c)+'    bl _probe_fclose\n'
    s+='    bl Lrepair_close\n' if repaired else word(0x3e144)
    s+='    ldp x19,x23,[sp,#16]\n    ldp x29,x30,[sp],#32\n    ret\n'
    if repaired:
        for name,reg in [('commit','x19'),('finish','x19'),('close','x23')]:
            s+=f'''Lrepair_{name}:
    stp x29,x30,[sp,#-16]!
    mov x1,{'x23' if name=='commit' else 'x0'}
    mov x0,{reg}
    bl _repair_{name}
    ldp x29,x30,[sp],#16
    ret
'''
    return s

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in NSOS:p.add_argument('--'+n+'-nso',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve()
    if out==ROOT or ROOT in out.parents:raise ValueError('private output outside checkout required')
    out.mkdir(parents=True,exist_ok=False)
    blobs={n:load_nso(getattr(a,n+'_nso'),n) for n in NSOS}
    # Exercise identity failure before any native execution.
    for n in NSOS:
        bad=out/(n+'.bad');bad.write_bytes(b'not an original NSO')
        try:load_nso(bad,n)
        except ValueError:pass
        else:raise AssertionError('wrong NSO accepted')
        bad.unlink()
    spec=importlib.util.spec_from_file_location('table',ROOT/'dm/games/010090C022978000/patches.py')
    assert spec and spec.loader
    table=importlib.util.module_from_spec(spec);spec.loader.exec_module(table)
    image=blobs['main'];checks=0
    for off,ident,old,why in table.WRAPS[table.kh1_build]:
        assert struct.unpack_from('<I',image,off)[0]==int(old,16);checks+=1
    for off,old,new,why in table.CUTS[table.kh1_build]:
        assert image[off:off+4]==bytes.fromhex(old);checks+=1
    for off,expected in {0x13354:0x7109651f,0x12500:0xb90002a0,0x130e0:0x7100445f,0x131e8:0xd65f03c0}.items():
        assert struct.unpack_from('<I',image,off)[0]==expected;checks+=1
    for n in ['main','sdk']:(out/(n+'.orig.bin')).write_bytes(blobs[n])
    env={**os.environ,'TMPDIR':str(out),'PYTHONDONTWRITEBYTECODE':'1','ASAN_OPTIONS':'detect_leaks=0','UBSAN_OPTIONS':'halt_on_error=1'}
    runs=[]
    def run(label,cmd,expected=0):
        cp=subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
        log=cp.stdout+cp.stderr;(out/(label+'.log')).write_text(log)
        ok=command_ok(cp.returncode,log,expected)
        runs.append(dict(label=label,command=list(map(str,cmd)),exit=cp.returncode,expected=expected,ok=ok));print(label,cp.returncode,ok,flush=True)
        return ok
    gid='010090C022978001'
    assert run('profile',[sys.executable,ROOT/'dm/games/game.py','header',ROOT/'dm/games/010090C022978000/direct-profiles'/gid,out/'game_profile.h'])
    run('original-png',[sys.executable,ROOT/'dm/host/tests/probe_kh2_png_boundary.py','--program','kh1','--main',out/'main.orig.bin','--sdk',out/'sdk.orig.bin','--out',out/'png'])
    for repaired in [False,True]:
        img=bytearray(image)
        if repaired:
            for off,old,new,why in table.CUTS[table.kh1_build]:img[off:off+4]=bytes.fromhex(new)
        asm=out/('repaired.S' if repaired else 'original.S');asm.write_text(tail_assembly(img,repaired))
        for mode,flags in [('plain',[]),('san',['-fsanitize=address,undefined','-fno-omit-frame-pointer'])]:
            tag=('repaired-' if repaired else 'original-')+mode;exe=out/tag
            fixture='t_kh2_repaired_boundary.c' if repaired else 't_kh2_failure_boundary.c'
            if run(tag+'-build',['clang','-O1','-g','-Wall','-Wextra','-Werror','-I'+str(out),*flags,ROOT/'dm/host/tests'/fixture,asm,'-o',exe]):
                if repaired:run(tag,[exe])
                else:
                    for case,expected in [('png-success',0),('commit-failure',0),('png-failure-observed',0),('require-png-recovery',1),('close-failure-observed',0),('require-close-error',1)]:run(tag+'-'+case,[exe,case],expected)
    (out/'results.json').write_text(json.dumps(dict(scope=__doc__,original_nsos=NSOS,word_checks=checks,runs=runs),indent=2)+'\n')
    return int(any(not r['ok'] for r in runs))
if __name__=='__main__':sys.exit(main())
