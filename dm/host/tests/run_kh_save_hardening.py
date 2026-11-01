#!/usr/bin/env python3
"""CPU-only clean-branch save regressions (no hostgame/app build or devices).

--baseline tests pinned e9ca69c production, expected RED; --sanitize uses
ASan/UBSan. Output, synthetic fixtures and binaries live under --out.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
BASE = 'e9ca69cd8fc153a5ea6848992ec11073a2cf2abe'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline', action='store_true')
parser.add_argument('--sanitize', action='store_true')
parser.add_argument('--profile', choices=['kh1', 'kh2', 'both'], default='both')
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
OUT = args.out.resolve()
OUT.mkdir(parents=True, exist_ok=True)
fixtures = OUT / 'fixtures'
fixtures.mkdir(exist_ok=True)
env = dict(os.environ, TMPDIR=str(fixtures), ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1')
for key in ['DM_KH2_SAVE_FIX_MIGRATE', 'DM_SAVE_TRACE', 'DM_TEST_FS_FAILAT', 'DM_TEST_FS_FAIL', 'DM_TEST_KILL_AT', 'DM_FSLOG', 'DM_FSLOG_HASH']:
    env.pop(key, None)
env.update(DM_GAMES_DIR=str(ROOT / 'dm/games/010090C022978000/direct-profiles'), DM_GAMES_FIRST='1')
source = ROOT / 'dm/host/hle_fs.c'
flags = []
if args.baseline:
    source = OUT / 'baseline-hle_fs.c'
    source.write_bytes(subprocess.check_output(['git', 'show', BASE + ':dm/host/hle_fs.c'], cwd=ROOT))
    flags += ['-DREVIEW_BASELINE=1', '-DHLE_FS_SOURCE="' + str(source) + '"']
if args.sanitize:
    flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
rows = []


def run(label, cmd, cwd=ROOT):
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        output, status = p.stdout, p.returncode
    except subprocess.TimeoutExpired as e:
        output = (e.stdout or b'').decode() if isinstance(e.stdout, bytes) else (e.stdout or '')
        output += '\nTIMEOUT after 120 seconds\n'
        status = 124
    log = OUT / (label + '.log')
    log.write_text(output)
    results = [dict(checks=int(n), failed=int(f)) for n, f in re.findall(r'RESULT [^\n]*?: (\d+) checks, (\d+) failed', output)]
    ordinary = [dict(checks=int(n), failed=int(f)) for n, f in re.findall(r'(?:== (?:case: )?|list Commit: )(\d+) checks, (\d+) failed', output)]
    rows.append(dict(label=label, command=cmd, cwd=str(cwd), exit_code=status, log=str(log), cases=results, ordinary=ordinary))
    # Persist each command so a later failure cannot erase earlier RED evidence.
    (OUT / 'results.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), baseline=BASE if args.baseline else None, sanitized=args.sanitize, results=rows), indent=2) + '\n')
    print(label, 'exit', status, output[-180:].strip(), flush=True)
    return status


original = ['create-failure', 'readonly-path', 'held-handle', 'clone-failure', 'swap-failure', 'concurrent-commit', 'recursive-failure']
adversarial = original + ['short-io', 'resize-failure', 'crash-before-commit', 'crash-before-swap', 'crash-after-swap', 'normal-aliases', 'log-rotation-save', 'legacy-only', 'overloads', 'create-open-failure', 'create-name-failure', 'write-open-failure', 'stale-edges', 'benign-exists', 'healthy-handle', 'directory-failure', 'directory-name-failure', 'recursive-delete-failure', 'poison-isolation', 'rollback-retry-handle', 'list-clone-failure']
ops = ['create', 'open', 'append', 'readwrite', 'delete', 'mkdir', 'rmdir', 'clean', 'recursive', 'rename-file-src', 'rename-file-dst', 'rename-dir-src', 'rename-dir-dst', 'read', 'stat', 'read-dir']
seams = [['seam', op, fault] for op in ops for fault in ['opendir', 'opendir2', 'readdir', 'closedir', 'getxattr']]
seams += [['seam', op, 'lstat'] for op in ['create', 'mkdir', 'rename-file-dst', 'rename-dir-dst']]
seams += [['seam', op, fault] for op, fault in [('rename-file-dst', 'access'), ('rename-dir-dst', 'access'), ('rename-file-src', 'rename'), ('rename-dir-src', 'rename'), ('rmdir', 'rmdir'), ('open', 'fstat'), ('append', 'fstat'), ('readwrite', 'fstat'), ('read', 'fstat')]]
seams += [[case] for case in ['probes', 'isolation', 'alias', 'readonly-read']]
edges = ['cross-dst-lookup', 'cross-access', 'cross-rename', 'cross-src-lookup', 'nontransactional', 'readonly'] + ['benign-' + str(i) for i in range(7)]

if not args.baseline:
    run('source-equivalence', [sys.executable, 'dm/host/tests/check_kh_save_equivalence.py'])

for tag, game in [('kh1', '010090C022978001'), ('kh2', '010090C022978003')]:
    if args.profile not in ('both', tag):
        continue
    if run(tag + '-profile', ['make', '-C', 'dm/host', 'game_profile', 'GAME=' + game]):
        continue
    header = ROOT / ('dm/host/gen/' + game + '/game_profile.h')
    (OUT / (tag + '-profile.h')).write_bytes(header.read_bytes())
    b = OUT / ('build-' + tag)
    b.mkdir(exist_ok=True)
    cc = ['clang', '-O1', '-g', '-Wno-unused-function', '-I..', '-I../gen/' + game] + flags
    tests = ROOT / 'dm/host/tests'
    if not args.baseline:
        for name in ['t_fs', 't_fs_case', 't_fs_commit_list']:
            sources = [name + '.c', '../hle_bigstack.c']
            if name != 't_fs_case':
                sources.append('t_fs_stub.c')
            # ASan global padding breaks this test's contiguous Mach-O swforce
            # section ABI walk; retain code/heap/stack ASan and all UBSan.
            specific = ['-mllvm', '-asan-globals=0'] if args.sanitize and name == 't_fs_commit_list' else []
            exe = b / name
            if not run(tag + '-build-' + name, cc + specific + ['-o', str(exe)] + sources, tests):
                run(tag + '-' + name, [str(exe)])
    matrices = [
        ('original', 't_save_original_repros.c', 't_fs_stub.c', [[c] for c in original]),
        ('adversarial', 't_fs_save_adversarial.c', 't_save_adversarial_stub.c', [[c] for c in adversarial]),
        ('r1', 't_fs_path_resolution.c', 't_save_adversarial_stub.c', [['create'], ['open']]),
        ('seams', 't_fs_path_seams.c', 't_save_adversarial_stub.c', seams),
    ]
    if not args.baseline:
        matrices += [('edges', 't_save_independent_r1_edges.c', 't_save_adversarial_stub.c', [[c] for c in edges])]
    for label, src, stub, cases in matrices:
        exe = b / label
        if not run(tag + '-build-' + label, cc + ['-o', str(exe), src, stub, '../hle_bigstack.c'], tests):
            for case in cases:
                run(tag + '-' + label + '-' + '-'.join(case), [str(exe)] + case)
    # Deterministic, multi-megabyte synthetic transport; never original saves.
    if not args.baseline:
        with tempfile.TemporaryDirectory(prefix=tag + '-synthetic-', dir=fixtures) as td:
            td = Path(td)
            dest = td / 'save'
            filename = 'KHFM.png' if tag == 'kh1' else 'KHIIFM.png'
            canonical = dest / 'KINGDOM HEARTS HD 1.5+2.5 ReMIX' / filename
            canonical.parent.mkdir(parents=True)
            canonical.write_bytes(bytes(range(256)) * 27629 + b'fixture!')
            (dest / ('\\KINGDOM HEARTS HD 1.5+2.5 ReMIX\\' + filename)).write_bytes(b'distinct flat alias')
            expected = td / 'expected.bin'
            expected.write_bytes(canonical.read_bytes())

            def manifest():
                return [dict(path=str(p.relative_to(dest)), size=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(dest.rglob('*')) if p.is_file()]

            before = manifest()
            exe = b / 'adversarial'
            run(tag + '-transport-rewrite', [str(exe), 'real-roundtrip', str(dest), str(expected)])
            run(tag + '-transport-exec-read', [str(exe), 'real-read', str(dest), str(expected)])
            after = manifest()
            (OUT / (tag + '-manifests.json')).write_text(json.dumps(dict(before=before, after=after), indent=2) + '\n')
            assert before == after, 'synthetic byte/alias preservation failed'
failed = [r['label'] for r in rows if r['exit_code']]
print('FAILED TEST COMMANDS:', json.dumps(failed))
raise SystemExit(bool(failed))
