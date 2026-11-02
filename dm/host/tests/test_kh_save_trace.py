"""The KH2 diagnostic stream must contain each save operation, not just commits."""
import os
import pathlib
import subprocess
import sys

exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).parent / "build/t_fs"
markers = ("[save-trace] create ", "[save-trace] write ", "[save-trace] delete ", "[save-trace] commit ")
for value in (None, '0', '1'):
    env = dict(os.environ)
    for key in ('DM_SAVE_TRACE', 'DM_KH24_DIAG', 'DM_KH_INPUT_TRACE', 'DM_FS'):
        env.pop(key, None)
    if value is not None:
        env['DM_SAVE_TRACE'] = value
    run = subprocess.run([str(exe.resolve())], env=env, text=True, capture_output=True)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    if value == '1':
        for marker in markers:
            assert marker in run.stderr, f"missing {marker}; stderr tail:\n{run.stderr[-2000:]}"
    else:
        assert '[save-trace]' not in run.stderr, f'trace unexpectedly enabled with DM_SAVE_TRACE={value!r}'
print("save trace absent/0: off; explicit 1: create, write, delete and commit present")
