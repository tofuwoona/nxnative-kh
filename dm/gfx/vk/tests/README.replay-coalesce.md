# KH2 replay/Metal coalescing fixture

Run on macOS with Metal and the KH2 direct profile:

```sh
bash dm/gfx/vk/tests/run_replay_coalesce.sh --red
bash dm/gfx/vk/tests/run_replay_coalesce.sh
```

`DM_GAMES_DIR` may override the default direct-profiles directory (the script
creates a temporary `game_profile.h` and executable, then removes them).
The fixture compiles the **actual** `hle_vk.m` into its executable, records
commands with the production `h_vkCmd*` functions and calls production
`replay()`, `begin_rp()`, `pre_draw()` and `end_rp()` with a real Metal device.
Dead-stripping and dynamic lookup leave unrelated host entry points unlinked;
no host/device/game process is started. The first control deliberately disables
coalescing and verifies that the merge assertion fails (two encoders).

Green asserts Metal command-buffer completion and the actual encoder/pass
counters for: two compatible drawn LOAD/STORE passes sharing one encoder;
a later draw whose bound texture aliases the color attachment forcing an
encoder cut and resume; and a buffer-backed color target failing merge
eligibility. GPU blit readback checks the final red RGBA pixel for the drawn
merge and feedback paths, and a separate full color/depth/stencil fixture
compares GPU readback after two merged passes. A real heap-backed attachment
also fails closed. `MTL_DEBUG_LAYER=1 MTL_SHADER_VALIDATION=1` passed the same
fixture with Metal API and GPU Validation explicitly reporting enabled. The
fixture does not reproduce actual KH2 ripple frames or GPU timing. Its feedback
fragment metadata names the bound color texture, but the minimal fixture's
fragment function emits a constant color rather than fetching it; the
production feedback detector and encoder transition are exercised, not the
shader's sampling result. It does not establish device safety or performance.
