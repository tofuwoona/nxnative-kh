"""Direct KH2 packaging must reject the collection launcher's patched main."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = Path('/Users/tofu/nxnative-local-work/Kingdom Hearts HD 1.5 plus 2.5 ReMIX/010090C022978000_build')
profile = ROOT / 'dm/games/010090C022978000/direct-profiles/010090C022978003/game.tsv'
checker = ROOT / 'dm/ios/tools/check_kh2_direct_patch.py'
for directory, expected in [('patched_v0', 1), ('program3_patched', 0)]:
    p = subprocess.run([sys.executable, str(checker), str(profile), 'v0', str(BASE / directory)],
                       capture_output=True, text=True)
    assert p.returncode == expected, (directory, p.returncode, p.stdout, p.stderr)
print('KH2 package guard: wrong collection main rejected; Program 3 main accepted')
