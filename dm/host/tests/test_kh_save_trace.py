"""The KH2 diagnostic stream must contain each save operation, not just commits."""
import os
import pathlib
import subprocess
import sys

exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).parent / "build/t_fs"
env = dict(os.environ, DM_SAVE_TRACE="1")
run = subprocess.run([str(exe.resolve())], env=env, text=True, capture_output=True)
assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
for marker in ("[save-trace] create ", "[save-trace] write ", "[save-trace] delete ", "[save-trace] commit "):
    assert marker in run.stderr, f"missing {marker}; stderr tail:\n{run.stderr[-2000:]}"
print("save trace includes create, write, delete and commit")
