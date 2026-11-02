#!/usr/bin/env python3
"""CPU-only input mechanism tests. No game, GPU, device, or save writes.

--capture validates private raw/plain/gzip logs ONLY (never replays them).
Only synthetic input fixtures are dispatched by this runner.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT / 'dm/host/tests'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True, help='NEW evidence directory outside the checkout')
    p.add_argument('--sanitize', action='store_true')
    p.add_argument('--repeats', type=int, default=5, help='synthetic replay repeats per fresh process (2..100)')
    p.add_argument('--check-baseline', help='git revision to reproduce the known parser/scheduler failures against')
    p.add_argument('--capture', type=Path, action='append', default=[], help='read-only validation; NEVER replayed')
    args = p.parse_args()
    out = args.out.resolve()
    if out == ROOT or ROOT in out.parents or not 2 <= args.repeats <= 100:
        p.error('output must be outside checkout; repeats must be 2..100')
    out.mkdir(parents=True, exist_ok=False)
    scratch = out / 'scratch'
    scratch.mkdir()
    env = dict(os.environ, TMPDIR=str(scratch), DM_KH_INPUT_TRACE='1', DM_GAMES_DIR=str(ROOT / 'dm/games/010090C022978000/direct-profiles'), DM_GAMES_FIRST='1')
    # Never inherit scripted inputs, live control endpoints, or save overrides.
    for key in ('DM_SAVE', 'DM_CTL', 'DM_KEYS', 'DM_KH_REPLAY_ALLOW', 'DM_KH_REPLAY_CONFIRM_SAVE'):
        env.pop(key, None)
    if args.sanitize:
        env.update(ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1')
    results = []

    def run(label, command, expected=0, must_contain=None):
        result = subprocess.run([str(x) for x in command], cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        (out / (label + '.stdout')).write_text(result.stdout)
        (out / (label + '.stderr')).write_text(result.stderr)
        ok = result.returncode == expected and (must_contain is None or must_contain in result.stdout + result.stderr)
        results.append(dict(label=label, command=[str(x) for x in command], exit_code=result.returncode, expected=expected, passed=ok))
        print(f'{label}: exit={result.returncode} expected={expected} {"PASS" if ok else "FAIL"}', flush=True)
        if not ok:
            raise RuntimeError(result.stdout + result.stderr)
        return result

    def build(label, source, profile=None, extra=()):
        flags = ['clang', '-O1', '-g', '-Wall', '-Wextra', '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-missing-field-initializers']
        if args.sanitize:
            flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
        if profile:
            flags += ['-I' + str(profile), '-I' + str(ROOT / 'dm/host')]
        exe = out / label
        run('build-' + label, flags + [source, *extra, '-o', exe])
        return exe

    try:
        profiles = {}
        for game, tag in [('010090C022978003', 'kh2'), ('010090C022978001', 'kh1')]:
            profile = out / tag
            profile.mkdir()
            run('profile-' + tag, [sys.executable, ROOT / 'dm/games/game.py', 'header', game, profile / 'game_profile.h'])
            profiles[tag] = profile
        for name in ('t_input_replay', 't_input_replay_invalid', 't_input_replay_validate'):
            exe = build(name, TESTS / (name + '.c'))
            if name != 't_input_replay_validate':
                run(name, [exe])
        adapter = build('t_input_replay_mac', TESTS / 't_input_replay_mac.c', profiles['kh2'])
        run('mac-adapter', [adapter], must_contain='exact press/release order and guard verified')
        reject = build('t_input_replay_reject', TESTS / 't_input_replay_reject.c', profiles['kh2'])
        run('scheduler-reject', [reject, scratch])
        sibling = build('t_input_replay_profile', TESTS / 't_input_replay_profile.c', profiles['kh1'])
        run('sibling-disabled', [sibling, scratch])
        run('extractor-cli-tests', [sys.executable, TESTS / 'test_extract_input_trace.py', '-v'])
        pipeline = build('t_input_replay_pipeline', TESTS / 't_input_replay_pipeline.c', profiles['kh2'], [ROOT / 'dm/host/hle_haptics.c'])
        capture = run('production-capture', [pipeline, 'capture'])
        raw = out / 'production-capture.stderr'
        compressed = out / 'production-capture.gz'
        compressed.write_bytes(gzip.compress(capture.stderr.encode()))
        for tag, source in [('plain', raw), ('gzip', compressed)]:
            extracted = out / ('synthetic-' + tag + '.log')
            run('extract-' + tag, [sys.executable, ROOT / 'scripts/extract_input_trace.py', source, extracted])
            run('parse-' + tag, [out / 't_input_replay_validate', extracted], must_contain='7 records; 0 failed')
            # Each invocation is a fresh process; each repeats the same capture.
            run('pipeline-' + tag, [pipeline, 'replay', extracted, scratch, args.repeats], must_contain='NO save writes; NOT KH2 menu/slot route')
        hid = build('t_hid', TESTS / 't_hid.c', profiles['kh2'], [ROOT / 'dm/host/hle_haptics.c'])
        run('existing-hid-suite', [hid], must_contain='0 failed')
        for i, source in enumerate(args.capture):
            extracted = out / f'private-validated-{i}.log'
            run(f'private-extract-{i}', [sys.executable, ROOT / 'scripts/extract_input_trace.py', source, extracted])
            run(f'private-parse-{i}', [out / 't_input_replay_validate', extracted])
        if args.check_baseline:
            baseline = out / 'baseline'
            (baseline / 'tests').mkdir(parents=True)
            for name in ('input_replay.h', 'input_replay_mac.c'):
                blob = subprocess.check_output(['git', 'show', args.check_baseline + ':dm/host/' + name], cwd=ROOT)
                (baseline / name).write_bytes(blob)
            for name, failure in [('t_input_replay_invalid', 'parser invalid records: 7 failed'), ('t_input_replay_reject', 'scheduler reject: 2 failed')]:
                source = baseline / 'tests' / (name + '.c')
                shutil.copyfile(TESTS / source.name, source)
                exe = build('baseline-' + name, source, profiles['kh2'])
                run('red-' + name, [exe] + ([scratch] if name.endswith('reject') else []), expected=1, must_contain=failure)
    finally:
        hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
            'dm/host/input_replay.h', 'dm/host/input_replay_mac.c', 'dm/host/hle_hid.c', 'dm/host/hle_fs.c', 'scripts/extract_input_trace.py')}
        report = dict(results=results, passed=sum(r['passed'] for r in results), commands=len(results), source_sha256=hashes,
                      scope='CPU input mechanism only. No save writes; not KH2 menu/slot route or game serialization.')
        (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(dict(commands=report['commands'], passed=report['passed'], evidence=str(out))))


if __name__ == '__main__':
    main()
