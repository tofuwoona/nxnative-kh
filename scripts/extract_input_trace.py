#!/usr/bin/env python3
"""Extract replay transitions only; does not launch a host or inject input.

Output is private (0600), NEW only. All input records, including records outside
an optional inclusive exact-t_ns window, must validate before output is created.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

MAX_U64 = (1 << 64) - 1
PATTERN = re.compile(rb'\[dm\] \[input-trace\] t_ns=([0-9]+) source=(-1|[0-7]) buttons=((?:0[xX])?[0-9a-fA-F]+) axes=(-?[0-9]+),(-?[0-9]+),(-?[0-9]+),(-?[0-9]+)\n?')


def extract(source, output, start=None, end=None):
    if os.path.lexists(output):
        raise ValueError('output already exists (files and symlinks are never overwritten)')
    if start is not None and end is not None and start > end:
        raise ValueError('start t_ns exceeds end t_ns')
    count = total = 0
    first = last = prev = None
    sources = Counter()
    bounds = set()
    digest = hashlib.sha256()
    source_digest = hashlib.sha256()
    # Spool to disk when necessary, but never publish a partially validated log.
    with open(source, 'rb') as raw, tempfile.SpooledTemporaryFile(max_size=1024*1024) as spool:
        before = os.fstat(raw.fileno())
        for chunk in iter(lambda: raw.read(1024*1024), b''):
            source_digest.update(chunk)
        raw.seek(0)
        compressed = raw.read(2) == b'\x1f\x8b'
        raw.seek(0)
        stream = gzip.GzipFile(fileobj=raw) if compressed else raw
        try:
            line_no = 0
            while True:
                line = stream.readline(1024*1024 + 1)
                if not line:
                    break
                line_no += 1
                if len(line) > 1024*1024:
                    raise ValueError(f'line {line_no}: exceeds 1 MiB line limit')
                if b'[input-trace]' not in line:
                    continue
                m = PATTERN.fullmatch(line)
                if not m or len(line) > 4095:
                    raise ValueError(f'line {line_no}: malformed input-trace record')
                try:
                    t, src, buttons, *axes = m.groups()
                    t, src, buttons = int(t), int(src), int(buttons, 16)
                    axes = [int(a) for a in axes]
                except ValueError as exc:
                    raise ValueError(f'line {line_no}: invalid integer') from exc
                if not 0 < t <= MAX_U64 or not 0 <= buttons <= MAX_U64 or any(not -32768 <= a <= 32767 for a in axes):
                    raise ValueError(f'line {line_no}: integer out of range')
                if prev is not None and t < prev:
                    raise ValueError(f'line {line_no}: out-of-order t_ns')
                prev = t
                total += 1
                if t == start or t == end:
                    bounds.add(t)
                if (start is not None and t < start) or (end is not None and t > end):
                    continue
                if first is None:
                    first = t
                last = t
                if last - first > 7200 * 1000000000:
                    raise ValueError('selected capture exceeds replay scheduler 2h limit')
                count += 1
                sources[str(src)] += 1
                canonical = line.rstrip(b'\n') + b'\n'
                spool.write(canonical)
                digest.update(canonical)
        finally:
            if compressed:
                stream.close()
        if not count:
            raise ValueError('empty input capture/window')
        if any(bound is not None and bound not in bounds for bound in (start, end)):
            raise ValueError('window boundary must match an exact recorded t_ns')
        after = os.fstat(raw.fileno())
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('source changed during extraction')
        spool.seek(0)
        # O_EXCL also refuses dangling symlinks and closes the exists-check race.
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'wb') as dest:
                shutil.copyfileobj(spool, dest)
                dest.flush()
                os.fsync(dest.fileno())
        except BaseException:
            os.unlink(output)
            raise
    assert first is not None and last is not None
    return dict(count=count, total_source_events=total, first_t_ns=first, last_t_ns=last,
                duration_ns=last-first, sources=dict(sorted(sources.items())),
                source=str(source), source_bytes=before.st_size, source_sha256=source_digest.hexdigest(),
                compression='gzip' if compressed else 'plain', output=str(output), output_sha256=digest.hexdigest())


def timestamp(value):
    if not re.fullmatch(r'[0-9]+', value) or not 0 < int(value) <= MAX_U64:
        raise argparse.ArgumentTypeError('t_ns must be a positive uint64 decimal integer')
    return int(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='raw plain/gzip log (gzip detected by magic, not suffix)')
    parser.add_argument('output', type=Path, help='NEW extracted transition log; parent directory must exist')
    parser.add_argument('--start-ns', type=timestamp, help='inclusive exact recorded t_ns')
    parser.add_argument('--end-ns', type=timestamp, help='inclusive exact recorded t_ns')
    args = parser.parse_args()
    try:
        meta = extract(args.source, args.output, args.start_ns, args.end_ns)
    except (OSError, EOFError, ValueError) as exc:
        parser.exit(1, f'error: {exc}\n')
    print(json.dumps(meta, sort_keys=True))


if __name__ == '__main__':
    main()
