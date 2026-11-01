import pathlib
import os
import subprocess
import sys
import tempfile

script = pathlib.Path(__file__).parents[3] / "scripts/kh2_diag_mac.py"
with tempfile.TemporaryDirectory() as td:
    save = str(pathlib.Path(td) / "save")
    run = subprocess.run([sys.executable, str(script), "--log-dir", td, "--rotate-bytes", "128",
                          "--confirm-save-path", save, "--",
                          sys.executable, "-c", "import sys;sys.stdout.write('A'*260);sys.stdout.flush()"],
                         env=dict(os.environ, DM_GAME="010090c022978003", DM_SAVE=save),
                         text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    root = pathlib.Path(td)
    active = root / "kh2-diag.log"
    prev = root / "kh2-diag.prev.log"
    assert active.exists() and prev.exists()
    assert 0 < active.stat().st_size <= 128 and prev.stat().st_size == 128
    assert active.read_bytes() == b"A" * 4
    assert prev.read_bytes() == b"A" * 128

    # A mismatched --confirm-save-path (e.g. a stale DM_SAVE from an old shell)
    # must be refused, not silently traced.
    bad = subprocess.run([sys.executable, str(script), "--log-dir", td, "--rotate-bytes", "128",
                          "--confirm-save-path", str(pathlib.Path(td) / "wrong-save"), "--",
                          sys.executable, "-c", "pass"],
                         env=dict(os.environ, DM_GAME="010090c022978003", DM_SAVE=save),
                         text=True, capture_output=True)
    assert bad.returncode != 0 and "does not match" in bad.stderr, bad.stderr
print("Mac continuous log keeps two bounded segments, and a mismatched save-path confirmation is refused")
