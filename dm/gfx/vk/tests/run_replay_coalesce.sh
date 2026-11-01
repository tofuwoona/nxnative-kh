#!/bin/bash
# Standalone macOS Metal replay integration test. No game launch or save access.
set -euo pipefail
root="$(cd "$(dirname "$0")/../../../.." && pwd)"
work="$(mktemp -d "${BH_AGENT_WORKSPACE:-$HOME/.hermes/cache/scratch}/kh-ripple-test.XXXXXX")"
trap 'rm -rf "$work"' EXIT
ulimit -c 0
profile="${DM_GAMES_DIR:-$root/dm/games/010090C022978000/direct-profiles}"
DM_GAMES_DIR="$profile" DM_GAMES_FIRST=1 python3 "$root/dm/games/game.py" header 010090C022978003 "$work/game_profile.h"
clang -fobjc-arc -ffunction-sections -fdata-sections \
  -I "$root/dm/third_party/vulkan-headers/include" \
  -I "$root/dm/gfx/nvn/include" -I "$work" \
  -Wl,-dead_strip -Wl,-undefined,dynamic_lookup \
  "$root/dm/gfx/vk/tests/t_replay_coalesce.m" -o "$work/replay-test" \
  -framework Metal -framework Foundation -framework Cocoa -framework QuartzCore
if [[ "${1:-}" == --red ]]; then
  set +e
  DM_VK_COALESCE_PASSES=0 "$work/replay-test" > "$work/red.log" 2>&1
  result=$?
  set -e
  if [[ "$result" -eq 0 ]] || ! grep -q 'safe LOAD/STORE pair must merge' "$work/red.log"; then
    printf 'RED control did not fail at the intended replay merge assertion (exit %s):\n' "$result"
    cat "$work/red.log"
    exit 1
  fi
  printf 'EXPECTED RED: coalescing disabled, actual replay produced two encoders (exit %s)\n' "$result"
elif [[ "${1:-}" == --default ]]; then
  env -u DM_VK_COALESCE_PASSES "$work/replay-test"
else
  DM_VK_COALESCE_PASSES=1 "$work/replay-test"
fi
