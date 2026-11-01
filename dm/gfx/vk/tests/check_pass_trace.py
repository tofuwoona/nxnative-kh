#!/usr/bin/env python3
"""Stream and check per-Vulkan-pass telemetry in logs up to 4 GiB.

A merged pass MUST still have its own pass/color records even when it reuses
one Metal encoder. Counts are actual encoder-creation records, not models.
"""
import re
import sys
from pathlib import Path

passes=encoders=merged=0
last_pass=last_encoder=0
saw_color=False
with Path(sys.argv[1]).open(errors='replace') as f:
    for line in f:
        if '[vk-diag] pass frame=' in line:
            m=re.search(r'pass=(\d+).*merged=(\d+) encoder=(\d+)',line)
            assert m,line
            p,is_merged,encoder=map(int,m.groups())
            if passes: assert saw_color, f'pass {last_pass} lacks a color attachment'
            assert not passes or p==last_pass+1, f'gap or duplicate pass {last_pass}->{p}'
            assert encoder and encoder<=last_encoder, f'pass {p} references unrecorded Metal encoder {encoder}'
            passes+=1;merged+=is_merged;last_pass=p;saw_color=False
        elif '[vk-diag] color frame=' in line:
            m=re.search(r'pass=(\d+)',line)
            if m and int(m.group(1))==last_pass: saw_color=True
        elif '[vk-diag] encoder frame=' in line:
            m=re.search(r'encoder=(\d+)',line)
            assert m,line
            n=int(m.group(1))
            assert not encoders or n==last_encoder+1, f'encoder gap {last_encoder}->{n}'
            last_encoder=n;encoders+=1
assert passes and encoders and saw_color,'missing pass, encoder or final color record'
print(f'pass trace: {passes} Vulkan passes, {encoders} actual encoder starts, {merged} merged passes; all colored passes recorded')
