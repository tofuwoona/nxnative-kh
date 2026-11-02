#!/usr/bin/env python3
"""R1 CPU-only regression runner; all builds/fixtures/logs stay in own output.
--baseline compiles unchanged e191b99 production; expected to fail.
--sanitize enables ASan + UBSan for both direct KH profiles.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from run_kh2_sync import command_ok

ROOT = Path(__file__).resolve().parents[3]
BASE = 'e191b99d1806682888557e415ab82c99f9185fb0'
baseline = '--baseline' in sys.argv
sanitize = '--sanitize' in sys.argv
mode = 'red' if baseline else ('sanitized' if sanitize else 'green')
OUT = Path(os.environ.get('DM_SAVE_PATH_OUT', ROOT / 'dm/host/tests/build-path-resolution' / mode)).resolve()
OUT.mkdir(parents=True, exist_ok=True)
fixtures = OUT / 'fixtures'
fixtures.mkdir(exist_ok=True)
env = dict(os.environ, TMPDIR=str(fixtures), ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1')
for key in ['DM_KH2_SAVE_FIX_MIGRATE', 'DM_TEST_FS_FAILAT', 'DM_TEST_FS_FAIL', 'DM_TEST_KILL_AT', 'DM_FSLOG']:
    env.pop(key, None)
env.update(DM_GAMES_DIR=str(ROOT / 'dm/games/010090C022978000/direct-profiles'), DM_GAMES_FIRST='1')
flags = []
source = ROOT / 'dm/host/hle_fs.c'
if baseline:
    source = OUT / 'baseline-hle_fs.c'
    source.write_bytes(subprocess.check_output(['git', 'show', BASE + ':dm/host/hle_fs.c'], cwd=ROOT))
    flags += ['-DHLE_FS_SOURCE="' + str(source) + '"']
if sanitize:
    flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
results = []

def run(label, cmd, cwd=ROOT):
    p = subprocess.run(cmd, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    log = OUT / (label + '.log')
    log.write_text(p.stdout)
    code=int(not command_ok(p.returncode,p.stdout))
    results.append(dict(label=label, command=cmd, cwd=str(cwd), exit_code=code, process_exit=p.returncode, log=str(log)))
    print(label, 'exit', p.returncode, p.stdout[-500:].strip(), flush=True)
    return code

CASES = ['create', 'open']
OPS = ['create', 'open', 'append', 'readwrite', 'delete', 'mkdir', 'rmdir', 'clean', 'recursive', 'rename-file-src', 'rename-file-dst', 'rename-dir-src', 'rename-dir-dst', 'read', 'stat', 'read-dir']
SEAMS = [['seam', op, fault] for op in OPS for fault in ['opendir', 'opendir2', 'readdir', 'closedir', 'getxattr']]
SEAMS += [['seam', op, 'lstat'] for op in ['create', 'mkdir', 'rename-file-dst', 'rename-dir-dst']]
SEAMS += [['seam', op, fault] for op, fault in [('rename-file-dst', 'access'), ('rename-dir-dst', 'access'), ('rename-file-src', 'rename'), ('rename-dir-src', 'rename'), ('rmdir', 'rmdir'), ('open', 'fstat'), ('append', 'fstat'), ('readwrite', 'fstat'), ('read', 'fstat')]]
SEAMS += [[case] for case in ['probes', 'isolation', 'alias', 'readonly-read']]
for tag, game in [('kh2', '010090C022978003'), ('kh1', '010090C022978001')]:
    profile = OUT / tag
    profile.mkdir(exist_ok=True)
    if run(tag + '-profile', [sys.executable, 'dm/games/game.py', 'header',
                             str(ROOT / 'dm/games/010090C022978000/direct-profiles' / game), str(profile / 'game_profile.h')]):
        continue
    exe = OUT / ('t_path_resolution_' + tag)
    cmd = ['clang', '-O1', '-g', '-Wno-unused-function', '-I..', '-I' + str(profile)] + flags + ['-o', str(exe), 't_fs_path_resolution.c', 't_save_adversarial_stub.c', '../hle_bigstack.c']
    if run(tag + '-build', cmd, ROOT / 'dm/host/tests'):
        continue
    for case in CASES:
        run(tag + '-' + case, [str(exe), case])
    seam_exe = OUT / ('t_path_seams_' + tag)
    cmd = ['clang', '-O1', '-g', '-Wno-unused-function', '-I..', '-I' + str(profile)] + flags + ['-o', str(seam_exe), 't_fs_path_seams.c', 't_save_adversarial_stub.c', '../hle_bigstack.c']
    if not run(tag + '-seams-build', cmd, ROOT / 'dm/host/tests'):
        for args in SEAMS:
            run(tag + '-' + '-'.join(args), [str(seam_exe)] + args)
(OUT / 'results.json').write_text(json.dumps(dict(production_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), baseline=BASE if baseline else None, sanitized=sanitize, results=results), indent=2) + '\n')
sys.exit(int(any(r['exit_code'] for r in results)))
