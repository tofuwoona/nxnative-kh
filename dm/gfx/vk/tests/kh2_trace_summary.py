#!/usr/bin/env python3
"""Summarize bounded KH2 VPTRACE records; never infer a pass boundary from a hash.

Usage: python3 kh2_trace_summary.py <dmhost.log> <frame>
The existing VPTRACE logger deduplicates changed state and caps records at 256;
this report explicitly marks incomplete captures. A screenshot must be inspected
separately before interpreting a frame as gameplay.
"""
import collections
import json
import re
import sys
from pathlib import Path
from typing import Any

DRAW = re.compile(r'\[VPTRACE\] frame=(\d+) submit=(\d+) target=(\d+x\d+) .*?vs=([0-9a-f]+) fs=([0-9a-f]+) blend=(\d+) .*?mask=(\S+)')
ATT = re.compile(r'\[VPTRACE\]   dest_att0=(\S+)')
DEPTH = re.compile(r'\[VPTRACE\]   depth=(\S+) format=(\d+) .*?test=(\d+) .*?write=(\d+)')
TEX = re.compile(r'\[VPTRACE\]   fs_src_tex\[\d+\]=(\S+) size=(\d+x\d+)')
UBO = re.compile(r'\[UBOTRACE\] submit=(\d+) key=([0-9a-f]+) (.*)')


def summarize(lines, frame):
    draws: list[dict[str, Any]] = []
    ubo: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in lines:
        m = DRAW.search(line)
        if m:
            current = None
            if int(m[1]) == frame:
                current = dict(submit=int(m[2]), target=m[3], vs=m[4], fs=m[5], blend=int(m[6]), mask=m[7], textures=[])
                draws.append(current)
            continue
        if '[VPTRACE] frame=' in line:
            current = None
        if current is not None:
            if m := ATT.search(line): current['attachment'] = m[1]
            if m := DEPTH.search(line): current['depth'] = dict(attachment=m[1], format=int(m[2]), test=int(m[3]), write=int(m[4]))
            if m := TEX.search(line): current['textures'].append(dict(attachment=m[1], size=m[2]))
        if m := UBO.search(line): ubo.append(dict(submit=int(m[1]), key=m[2], values=m[3]))
    by_target = collections.Counter(d['target'] for d in draws)
    by_shader = collections.Counter(f"{d['vs']}/{d['fs']}" for d in draws)
    submit_range = [min((d['submit'] for d in draws), default=0), max((d['submit'] for d in draws), default=0)]
    window_records = sum(1 for line in lines if (m := DRAW.search(line)) and frame <= int(m[1]) <= frame + 2)
    return dict(frame=frame, records=len(draws), window_records=window_records, cap_reached=window_records >= 256,
                warning='VPTRACE is deduplicated and capped at 256 across the three-frame window; this is NOT a complete draw/pass inventory' if window_records >= 256 else 'VPTRACE is deduplicated: counts are changed-state records, not draws',
                submit_range=submit_range, target_counts=dict(by_target), shader_counts=dict(by_shader),
                selected_ubo=[r for r in ubo if submit_range[0] <= r['submit'] <= submit_range[1]],
                records_detail=draws)


def main():
    if len(sys.argv) != 3: raise SystemExit('usage: kh2_trace_summary.py LOG FRAME')
    print(json.dumps(summarize(Path(sys.argv[1]).read_text(errors='replace').splitlines(), int(sys.argv[2])), indent=2))


if __name__ == '__main__': main()
