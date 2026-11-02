#!/usr/bin/env python3
"""CPU-only synchronous-save tests; all compiler/profile outputs outside checkout.
No game/host/app/GPU/device execution. Guest call bodies in policy tests are seams.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
TESTS=ROOT/'dm/host/tests'

def command_ok(code,log,expected=0):
    return code==expected and not any(s in log for s in [
        'runtime error:', 'ERROR: AddressSanitizer', 'ERROR: UndefinedBehaviorSanitizer',
        'UndefinedBehaviorSanitizer:', 'WARNING: ASan', 'AddressSanitizer:DEADLYSIGNAL'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();out=args.out.resolve()
    if out==ROOT or ROOT in out.parents:raise ValueError('outputs must stay outside checkout')
    out.mkdir(parents=True,exist_ok=False)
    env={**os.environ,'TMPDIR':str(out),'ASAN_OPTIONS':'detect_leaks=0','UBSAN_OPTIONS':'halt_on_error=1','PYTHONDONTWRITEBYTECODE':'1'}
    runs=[]
    def run(label,cmd,expected=0):
        cp=subprocess.run([str(x) for x in cmd],cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
        (out/(label+'.log')).write_text(cp.stdout)
        code=int(not command_ok(cp.returncode,cp.stdout,expected))
        runs.append(dict(label=label,command=list(map(str,cmd)),exit=code,process_exit=cp.returncode,expected=expected));print(label,code,cp.stdout[-200:].strip(),flush=True)
        return code
    for tag,gid in [('kh2','010090C022978003'),('kh1','010090C022978001')]:
        profile=out/tag;profile.mkdir()
        if run(tag+'-profile',[sys.executable,ROOT/'dm/games/game.py','header',ROOT/'dm/games/010090C022978000/direct-profiles'/gid,profile/'game_profile.h']):continue
        for mode,flags in [('plain',[]),('asan-ubsan',['-fsanitize=address,undefined','-fno-omit-frame-pointer'])]:
            names=['t_kh2_sync','t_kh2_guard','t_kh2_gates','t_kh2_dispatch','t_kh2_abi','t_kh2_png','t_kh_save_controls']
            if tag=='kh1':names+=['t_kh1_gates','t_kh1_alternate']
            for name in names:
                label=tag+'-'+mode+'-'+name;exe=out/label
                sources=[TESTS/(name+'.c')]
                if name=='t_kh2_abi':sources += [TESTS/'t_kh2_abi.S',ROOT/'dm/host/entry.S',ROOT/'dm/host/hle_bigstack.c']
                cmd=['clang','-O1','-g','-Wall','-Wextra','-Werror','-I'+str(profile),*flags,*sources,'-o',exe]
                if not run(label+'-build',cmd):run(label,[exe])
        if tag=='kh2':
            exe=out/'t_preempt'
            if not run('preempt-build',['clang','-O1','-g','-Wall','-Werror','-Wno-unused-function','-I'+str(profile),TESTS/'t_preempt.c',TESTS/'t_condvar_stub.c','-o',exe]):
                run('preempt',[exe]);run('preempt-all-peers',[exe,'--all-peers'])
    # Real launcher/Wonder headers, and an explicit Program2 compile-ID control.
    for tag,profile_path in [('program0',ROOT/'dm/games/010090C022978000'),
                             ('wonder',ROOT/'dm/games/010015100B514000'),('program2',None)]:
        profile=out/tag;profile.mkdir()
        if profile_path is None:
            text=(out/'kh1/game_profile.h').read_text().replace('0x010090C022978001','0x010090C022978002')
            assert text!=(out/'kh1/game_profile.h').read_text()
            (profile/'game_profile.h').write_text(text)
        elif run(tag+'-profile',[sys.executable,ROOT/'dm/games/game.py','header',profile_path,profile/'game_profile.h']):continue
        for mode,flags in [('plain',[]),('asan-ubsan',['-fsanitize=address,undefined','-fno-omit-frame-pointer'])]:
            label=tag+'-'+mode+'-controls';exe=out/label
            if not run(label+'-build',['clang','-O1','-g','-Wall','-Wextra','-Werror','-I'+str(profile),*flags,TESTS/'t_kh_save_controls.c','-o',exe]):run(label,[exe])
    for filename in ['test_kh2_sync_patches.py','test_kh1_sync_patches.py','test_kh_save_runner.py']:
        run(filename,[sys.executable,TESTS/filename])
    for filename in ['test_kh2_wrap.py','test_patches.py','test_nso_match.py']:
        run(filename,[sys.executable,ROOT/'dm/tools/tests'/filename])
    (out/'results.json').write_text(json.dumps(dict(scope='CPU mechanism/call-seam, not gameplay',runs=runs),indent=2)+'\n')
    return int(any(r['exit'] for r in runs))
if __name__=='__main__':sys.exit(main())
