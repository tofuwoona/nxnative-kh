#!/usr/bin/env python3
"""Run an isolated KH2 Mac host with bounded continuous save + NVN/Metal logs.

All existing DM_ROOT/ROMFS/SAVE/MSL paths must already be set by the caller.
This wrapper never selects or changes a save path. It keeps only two 4 GiB log
segments (8 GiB maximum), overwriting the older segment on each rollover. The trace contains
Vulkan-to-Metal render passes, not an Instruments GPU System Trace or screenshots.

Safety: DM_GAME/DM_SAVE presence is validated, but an env var can be stale from
an old shell. --confirm-save-path must independently repeat the exact resolved
DM_SAVE path as a command-line argument, so a caller who copy-pasted an old
command with a leftover DM_SAVE pointing at a real save gets a hard mismatch
error instead of silently tracing (or, with --rotate-bytes misuse, writing)
against it.
"""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys

LIMIT = 4 << 30


def run(argv: list[str], log_dir: Path, limit: int, confirm_save_path: str) -> int:
    if not argv or limit <= 0:
        raise ValueError("pass a command after -- and a positive rotation limit")
    if os.environ.get("DM_GAME", "").lower() != "010090c022978003":
        raise ValueError("DM_GAME must be the KH2 Program 3 ID 010090c022978003")
    save = os.environ.get("DM_SAVE")
    if not save:
        raise ValueError("DM_SAVE must explicitly point to an isolated save copy")
    if Path(confirm_save_path).resolve() != Path(save).resolve():
        raise ValueError(
            f"--confirm-save-path {confirm_save_path!r} does not match the resolved "
            f"DM_SAVE {save!r} -- refusing to run against a save the caller did not "
            "explicitly re-confirm (a stale DM_SAVE from an old shell is the likely cause)"
        )
    log_dir.mkdir(parents=True, exist_ok=True)
    active, previous = log_dir / "kh2-diag.log", log_dir / "kh2-diag.prev.log"
    if active.exists():
        active.replace(previous)
    env = dict(os.environ, DM_FS="1", DM_SAVE_TRACE="1", DM_KH24_DIAG="1", DM_KH_INPUT_TRACE="1")
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
    p.add_argument("--rotate-bytes", type=int, default=LIMIT, help="test override; normal limit is 4 GiB per segment")
    p.add_argument("--confirm-save-path", required=True,
                    help="must exactly equal the DM_SAVE path already set in the environment")
    p.add_argument("command", nargs=argparse.REMAINDER)
    a = p.parse_args()
    command = a.command[1:] if a.command[:1] == ["--"] else a.command
    try:
        return run(command, a.log_dir, a.rotate_bytes, a.confirm_save_path)
    except (OSError, ValueError) as e:
        print(f"kh2-diag: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
