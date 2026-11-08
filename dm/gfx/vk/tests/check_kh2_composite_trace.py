#!/usr/bin/env python3
"""KH2 final-copy state oracle; consumes complete Vulkan diagnostic frames.

Pipeline binds are state evidence, not pixel/draw-count proof. Pair this check
with passive movement captures. Exclude the last frame without its successor.
"""
import argparse
import json
import re
from pathlib import Path

PAIR = 'vs=4224d4542e2f8e20 fs=80a74ee192e6490b '

def check(path, first=0, last=None):
    current = None
    final_pass = None
    copies = []
    checked = 0
    failures = 0
    examples = []
    def finish():
        nonlocal checked, failures
        if current is None or current < first or (last is not None and current > last):
            return
        checked += 1
        reason = None
        if len(copies) != 1:
            reason = f'expected one final-copy bind, found {len(copies)}'
        elif copies[0][0] != final_pass:
            reason = 'copy bind was not in the final pass'
        elif copies[0][1] & 7 != 7:
            reason = f'final copy disables RGB channels (write={copies[0][1]})'
        if reason:
            failures += 1
            if len(examples) < 12:
                examples.append({'frame': current, 'reason': reason})
    with Path(path).open(errors='replace') as f:
        for line in f:
            if not line.endswith('\n') or '[vk-diag]' not in line:
                continue
            match = re.search(r'\bframe=(\d+)\b', line)
            if not match:
                continue
            frame = int(match[1])
            if current is None or frame != current:
                if current is not None and frame < current:
                    raise ValueError('non-monotonic diagnostic frame stream')
                finish()
                current, final_pass, copies = frame, None, []
            if '[vk-diag] pass ' in line:
                pass_match = re.search(r'\bpass=(\d+)', line)
                if pass_match is None:
                    raise ValueError('pass record lacks a pass identifier')
                final_pass = int(pass_match[1])
            if '[vk-diag] pipeline ' in line and PAIR in line:
                pass_match = re.search(r'\bpass=(\d+)', line)
                mask_match = re.search(r'\bwrite=(\d+)', line)
                if pass_match is None or mask_match is None:
                    raise ValueError('copy pipeline record lacks pass or write mask')
                copies.append((int(pass_match[1]), int(mask_match[1])))
    return {'complete_frames_checked': checked, 'bad_complete_frames': failures,
            'examples': examples, 'excluded_eof_frame': current,
            'pass': checked > 0 and failures == 0,
            'scope': 'final pipeline RGB-write state; not GPU pixel or campaign certification'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log')
    parser.add_argument('--start-frame', type=int, default=0)
    parser.add_argument('--end-frame', type=int)
    parser.add_argument('--json-out')
    args = parser.parse_args()
    result = check(args.log, args.start_frame, args.end_frame)
    text = json.dumps(result, indent=2) + '\n'
    if args.json_out:
        Path(args.json_out).write_text(text)
    print(text, end='')
    return 0 if result['pass'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
