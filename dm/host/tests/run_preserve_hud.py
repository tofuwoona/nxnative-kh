#!/usr/bin/env python3
"""CPU-only layout/policy tests. --red checks original coalescer HEAD fails."""
import argparse, os, pathlib, shutil, subprocess, tempfile
p=argparse.ArgumentParser(); p.add_argument('--red',action='store_true'); args=p.parse_args()
ROOT=pathlib.Path(__file__).resolve().parents[3]
with tempfile.TemporaryDirectory(prefix='kh2-hud-test-',dir=os.environ.get('TMPDIR',str(pathlib.Path.home()/'.hermes/cache/scratch'))) as d:
    work=pathlib.Path(d)
    if args.red:
        (work/'tests').mkdir()
        (work/'aspect_fill.h').write_bytes(subprocess.check_output(['git','show','70eca8a8c1dfefe972ae91a5851fbe5aaa6a3205:dm/host/aspect_fill.h'],cwd=ROOT))
        for name in ['t_preserve_hud.c','t_aspect_layout.c']:
            shutil.copyfile(ROOT/'dm/host/tests'/name,work/'tests'/name)
    for name,game in [('t_preserve_hud.c','0x010090C022978003ull'),('t_aspect_layout.c','0x010090C022978003ull')]+([] if args.red else [('t_preserve_hud.c','0x010090C022978001ull')]):
        src=(work/'tests'/name) if args.red else ROOT/'dm/host/tests'/name
        out=work/'test'
        subprocess.run(['clang','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-DDM_GAME_PROGRAM_ID='+game,str(src),'-o',str(out)],check=True)
        result=subprocess.run([str(out)])
        if args.red:
            assert result.returncode != 0, name+' unexpectedly passed on baseline'
            print('EXPECTED RED:',name,'exit',result.returncode,flush=True)
        else:
            assert result.returncode == 0, name+' failed'
    if not args.red:
        subprocess.run(['python3',str(ROOT/'dm/host/tests/test_preserve_hud_wiring.py')],check=True)
        subprocess.run(['python3',str(ROOT/'dm/host/tests/test_ios_image_origin.py')],check=True)
