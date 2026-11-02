"""Assert the KH2 diagnostic run logged actual Vulkan/Metal passes, not NVN startup."""
from pathlib import Path
import re
import sys

log = Path(sys.argv[1]).read_text(errors="replace")
frames = [int(m.group(1)) for m in re.finditer(r"\[vk-diag\] pass frame=(\d+)", log)]
assert frames and max(frames) > 0, "no real Vulkan render-pass frames captured"
assert "[vk-diag] pipeline" in log, "no Metal pipeline/shader trace captured"
assert "[save-trace] write " in log and "[save-trace] commit " in log, "save write/commit missing"
print("VK/Metal pass, shader and save traces verified")
