#!/usr/bin/env python3
"""Refuse to embed the collection launcher in the KH2 direct app.

The common RomFS can be shared, but Program 0 and Program 3 have different
patched main images. The fixup table retains the extracted module's build ID;
compare it to the direct profile's declared build ID before generating Xcode.
"""
import sys
from pathlib import Path


def check(profile: Path, package: str, patched: Path) -> None:
    rows = [line.split('\t') for line in profile.read_text().splitlines()
            if line and not line.startswith('#')]
    fields = {row[0]: row[1:] for row in rows if len(row) > 1 and row[0] != 'build'}
    if fields.get('program_id', [''])[0].lower() != '010090c022978003':
        return
    builds = [r for r in rows if r[0] == 'build' and len(r) > 3 and r[1] == package]
    if len(builds) != 1:
        raise ValueError(f'KH2 direct profile has no unique build for {package}')
    expected = next((x.split('=', 1)[1] for x in builds[0][3:] if x.startswith('main=')), None)
    if not expected:
        raise ValueError('KH2 direct profile has no main build ID')
    fixups = patched / 'main.fixups.tsv'
    image = patched / 'main.patched.bin'
    if not fixups.is_file() or not image.is_file():
        raise ValueError(f'KH2 patched main or fixups missing in {patched}')
    actual = next((line.split('\t', 1)[1].strip() for line in fixups.read_text().splitlines()
                   if line.startswith('# BUILD_ID\t')), None)
    if actual != expected:
        raise ValueError(f'KH2 direct main build ID {expected} required; {patched} has {actual or "none"}. '
                         'This is likely the collection launcher (Program 0), not Program 3.')


if __name__ == '__main__':
    try:
        check(Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]))
    except (IndexError, OSError, ValueError) as exc:
        print(f'[RED] KH2 package input: {exc}', file=sys.stderr)
        raise SystemExit(1)
