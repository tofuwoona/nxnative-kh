#!/usr/bin/env python3
"""Run an isolated KH2 Mac host with bounded continuous save + NVN/Metal logs.

All existing DM_ROOT/ROMFS/SAVE/MSL paths must already be set by the caller.
This wrapper never selects or changes a save path. It keeps only two 1 GiB log
segments, overwriting the older segment on each rollover. The trace contains
Vulkan-to-Metal render passes, not an Instruments GPU System Trace or screenshots.
"""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys

LIMIT = 1 << 30


def run(argv: list[str], log_dir: Path, limit: int) -> int:
    if not argv or limit <= 0:
        raise ValueError("pass a command after -- and a positive rotation limit")
    if os.environ.get("DM_GAME", "").lower() != "010090c022978003":
        raise ValueError("DM_GAME must be the KH2 Program 3 ID 010090c022978003")
    if not os.environ.get("DM_SAVE"):
        raise ValueError("DM_SAVE must explicitly point to an isolated save copy")
    log_dir.mkdir(parents=True, exist_ok=True)
    active, previous = log_dir / "kh2-diag.log", log_dir / "kh2-diag.prev.log"
    if active.exists():
        active.replace(previous)
    env = dict(os.environ, DM_FS="1", DM_SAVE_TRACE="1", DM_KH24_DIAG="1")
    child = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
    assert child.stdout
    old_handlers = {}

    def stop(signum, _frame):
        if child.poll() is None:
            child.send_signal(signum)

    for sig in (signal.SIGINT, signal.SIGTERM):
        old_handlers[sig] = signal.signal(sig, stop)
    size = 0
    out = active.open("wb", buffering=0)
    try:
        while data := os.read(child.stdout.fileno(), 65536):
            view = memoryview(data)
            while view:
                if size == limit:
                    out.close()
                    active.replace(previous)
                    out = active.open("wb", buffering=0)
                    size = 0
                part = view[:limit - size]
                out.write(part)
                size += len(part)
                view = view[len(part):]
        return child.wait()
    finally:
        out.close()
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        if child.poll() is None:
            child.terminate()
            child.wait()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log-dir", required=True, type=Path)
    p.add_argument("--rotate-bytes", type=int, default=LIMIT, help="test override; normal limit is 1 GiB")
    p.add_argument("command", nargs=argparse.REMAINDER)
    a = p.parse_args()
    command = a.command[1:] if a.command[:1] == ["--"] else a.command
    try:
        return run(command, a.log_dir, a.rotate_bytes)
    except (OSError, ValueError) as e:
        print(f"kh2-diag: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
