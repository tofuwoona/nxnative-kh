#!/usr/bin/env python3
"""CPU-only save regressions. --baseline runs all adversarial cases on exact base source.
No phone, original save, shared build output or GPU access.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import hashlib
import shutil
import tempfile
from run_kh2_sync import command_ok

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '--baseline' in sys.argv[1:]
SANITIZE = '--sanitize' in sys.argv[1:]
OUT = Path(os.environ.get('DM_SAVE_TEST_OUT', ROOT / 'docs/agents/kh2-save-fix-evidence' / ('red-extended' if BASELINE else 'green'))).resolve()
OUT.mkdir(parents=True, exist_ok=True)
TMP = OUT / 'fixtures'
TMP.mkdir(parents=True, exist_ok=True)
ENV = dict(os.environ, TMPDIR=str(TMP), DM_SAVE_TRACE='1')
ENV.pop('DM_KH2_SAVE_FIX_MIGRATE', None)
for key in ['DM_TEST_FS_FAIL', 'DM_TEST_FS_FAILAT', 'DM_TEST_KILL_AT', 'DM_FSLOG']:
    ENV.pop(key, None)
if SANITIZE:
    ENV.update(ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1')
ENV.update(DM_GAMES_DIR=str(ROOT / 'dm/games/010090C022978000/direct-profiles'), DM_GAMES_FIRST='1')
results = []
CASES = ['create-failure', 'readonly-path', 'held-handle', 'clone-failure', 'swap-failure', 'concurrent-commit', 'short-io', 'resize-failure', 'crash-before-commit', 'crash-before-swap', 'crash-after-swap', 'normal-aliases', 'recursive-failure', 'log-rotation-save', 'legacy-only', 'overloads', 'create-open-failure', 'create-name-failure', 'write-open-failure', 'stale-edges', 'benign-exists', 'healthy-handle', 'directory-failure', 'directory-name-failure', 'recursive-delete-failure', 'poison-isolation']
baseline_flags = []
CASES += ['rollback-retry-handle', 'list-clone-failure']
if BASELINE:
    revision = '70eca8a8c1dfefe972ae91a5851fbe5aaa6a3205'
    source = subprocess.check_output(['git', 'show', revision + ':dm/host/hle_fs.c'], cwd=ROOT)
    baseline_path = TMP / 'baseline-hle_fs.c'
    baseline_path.write_bytes(source)
    baseline_flags = ['-DREVIEW_BASELINE=1', '-DHLE_FS_SOURCE="' + str(baseline_path) + '"']
    (OUT / 'baseline-source.json').write_text(json.dumps(dict(revision=revision, path='dm/host/hle_fs.c', sha256=hashlib.sha256(source).hexdigest()), indent=2) + '\n')

def run(label, cmd, cwd=ROOT):
    p = subprocess.run(cmd, cwd=cwd, env=ENV, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    (OUT / (label + '.log')).write_text(p.stdout)
    r = dict(label=label, command=cmd, cwd=str(cwd), exit_code=int(not command_ok(p.returncode,p.stdout)), process_exit=p.returncode, output=str(OUT / (label + '.log')))
    results.append(r)
    print(label, 'exit', p.returncode, p.stdout[-300:].strip(), flush=True)
    return r['exit_code']

for game, tag in [('010090C022978003', 'kh2'), ('010090C022978001', 'kh1')]:
    tests = ROOT / 'dm/host/tests'
    b = OUT / ('build-save-' + tag)
    b.mkdir(exist_ok=True)
    if run(tag + '-profile', [sys.executable, 'dm/games/game.py', 'header',
                             str(ROOT / 'dm/games/010090C022978000/direct-profiles' / game), str(b / 'game_profile.h')]):
        continue
    flags = ['clang', '-O1', '-g', '-Wno-unused-function', '-I..', '-I' + str(b)]
    if SANITIZE: flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    for name in ([] if BASELINE else ['t_fs', 't_fs_case', 't_fs_commit_list']):
        sources = [name + '.c', '../hle_bigstack.c']
        if name != 't_fs_case': sources.append('t_fs_stub.c')
        if name != 't_fs': sources.append('t_save_review_input_stub.c')
        # ASan pads separate globals, breaking this test's intentional contiguous
        # Mach-O swforce-section ABI walk. Keep address/UB instrumentation of
        # code/stack/heap; only this binary disables global redzone insertion.
        name_flags = flags + (['-mllvm', '-asan-globals=0'] if SANITIZE and name == 't_fs_commit_list' else [])
        rc = run(tag + '-build-' + name, name_flags + ['-o', str(b / name)] + sources, tests)
        if not rc:
            run(tag + '-' + name, [str(b / name)])
    if not BASELINE:
        run(tag + '-save-trace', [sys.executable, 'dm/host/tests/test_kh_save_trace.py', str(b / 't_fs')])
    adversarial = b / ('t_fs_save_adversarial_baseline' if BASELINE else 't_fs_save_adversarial')
    if not run(tag + '-build-adversarial', flags + baseline_flags + ['-o', str(adversarial), 't_fs_save_adversarial.c', 't_save_adversarial_stub.c', '../hle_bigstack.c'], tests):
        for case in CASES:
            run(tag + '-adversarial-' + case, [str(adversarial), case])

logexe = OUT / 'build-save-kh2/t_log_rotation'
if not BASELINE and not run('build-log-rotation', ['clang', '-O1', '-g', '-pthread', '-o', str(logexe), 'dm/ios/tests/t_log_rotation.c']):
    run('log-rotation', [str(logexe)])
# No original-save access: deterministic multi-megabyte synthetic byte transport,
# independently exec'd reader, with distinct flat alias preserved.
def manifest(path):
    return [dict(path=str(p.relative_to(path)), size=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(path.rglob('*')) if p.is_file()]

with tempfile.TemporaryDirectory(prefix='synthetic-copy-', dir=TMP) as td:
    dest = Path(td) / 'save'
    canonical = dest / 'KINGDOM HEARTS HD 1.5+2.5 ReMIX/KHIIFM.png'
    canonical.parent.mkdir(parents=True)
    canonical.write_bytes(bytes(range(256)) * 27629 + b'fixture!')
    (dest / '\\KINGDOM HEARTS HD 1.5+2.5 ReMIX\\KHIIFM.png').write_bytes(b'distinct flat alias')
    expected = Path(td) / 'expected.bin'
    expected.write_bytes(canonical.read_bytes())
    before = manifest(dest)
    exe = OUT / 'build-save-kh2' / ('t_fs_save_adversarial_baseline' if BASELINE else 't_fs_save_adversarial')
    run('synthetic-copy-roundtrip', [str(exe), 'real-roundtrip', str(dest), str(expected)])
    run('synthetic-copy-fresh-process-read', [str(exe), 'real-read', str(dest), str(expected)])
    after = manifest(dest)
    assert before == after, 'roundtrip modified bytes'
    (OUT / 'synthetic-manifests.json').write_text(json.dumps(dict(before=before, after=after), indent=2) + '\n')
(OUT / 'test-results.json').write_text(json.dumps(results, indent=2) + '\n')
failed = [r['label'] for r in results if r['exit_code']]
print('FAILED TEST COMMANDS:', json.dumps(failed))
sys.exit(bool(failed))
