# KH2 MISS render default and temporary HUD-mode removal

Source-only follow-up to `c05f82bb20249917f561084e862e9208a9e90f15`.
No app/IPA/dmhost build, game launch, install, device/save access or external push.

## Current behavior

- KH2 Program 3 (`010090C022978003`) offers **MISS effect render fix**.
  The note says: “Reduces slowdown from pirate ‘MISS’ effects by coalescing
  compatible render passes. On by default; disable if you see rendering problems.”
  This is a slowdown reduction, not a promise to remove all effect-heavy stalls.
- New launcher preferences default to `1`. Existing saved values, including `0`,
  remain respected; `Launcher.swift` is unchanged and no migration is introduced.
  Env-file settings still win over saved values.
- The native cached gate defaults on when `DM_VK_COALESCE_PASSES` is **absent**.
  Explicit `0` disables and `1` enables it. Existing fail-closed handling of other
  explicit strings is retained. All non-Program-3 profiles return off regardless
  of the environment. Renderer eligibility and feedback guards are unchanged.
- **Preserve full HUD** and its runtime override are removed, not merely hidden.
  Old `DM_PRESERVE_FULL_HUD` environment values and saved launcher keys cannot
  override crop. There is no replacement HUD mode or true-widescreen claim.
- `DM_ASPECT_FILL` remains off by default. The original pre-HUD-mode image layout,
  iOS touch mapping and Mac mouse mapping from `70eca8a` are restored. The iOS
  image retains floored origins; touch origins retain their original fractions.
  Ordinary control safe-area placement is not removed.
- The five-line KH2 X/Y geometry change remains. Save implementation SHA-256:
  `32e36ff48977f8e96ef2e65a2174d6960e5a53626fcb521ead5db8e77c3d06f9`.
  The integrated icon implementation and other save changes are untouched.

Historical coalescer/default-off notes and old HUD captures describe their own
revisions, not these current settings.

## Focused RED → GREEN evidence

Before the relevant production edits:

- The new `settings.build()` regression failed for KH2's `default=0` versus `1`.
- The extracted actual `vk_coalesce_on()` regression failed for KH2 with no env
  variable. Explicit overrides and other profiles already matched the policy.
- The removed-row regression failed because the HUD setting was still emitted.
- The rewritten actual front-end expression test failed 134 comparisons for
  KH2 with the legacy HUD value set; the KH1 sibling baseline passed.

All now pass. The obsolete preserve-mode-only tests were removed; the actual
image-origin test now also executes production iOS and Mac touch expressions,
checking the independent old fit/crop oracle with legacy env unset/0/1 and crop
unset/0/1, six viewport/inset shapes, corners, center and out-of-bounds points.
It reports 54 cases per profile (KH2 and KH1), with zero failed comparisons.

## Reproduction commands and results

From the repository root:

```sh
python3 dm/tools/tests/test_launcher_settings.py
python3 dm/gfx/vk/tests/test_coalesce_defaults.py
python3 dm/host/tests/test_ios_image_origin.py
python3 dm/ios/tests/test_launcher_render_preferences.py
python3 dm/ios/tests/test_touch_face_positions.py
make -C dm/host/tests ios_face_swap
python3 dm/ios/tests/test_app_icon.py
python3 dm/gfx/vk/tests/test_coalesce_source.py
python3 dm/gfx/vk/tests/check_pass_trace.py dm/gfx/vk/tests/merged_trace_fixture.log
```

PASS: four settings tests; the native gate matrix (fresh executable processes,
three profiles × six env values, plus cache stability); actual frame/input
expressions; actual Swift launcher init/apply using disposable UserDefaults;
production geometry/labels/hits/publish/physical input for five profiles and
both swap preferences; face-swap test; four icon tests; source safety guard;
trace fixture (two Vulkan passes, one encoder, one merged pass).

Standalone C tests (write executables under `$TMPDIR`, not the source tree):

```sh
clang -Wall -Wextra -Werror -fsanitize=address,undefined \
  dm/host/tests/t_aspect_fill.c -o "$TMPDIR/kh2-aspect-test"
"$TMPDIR/kh2-aspect-test"
clang -Wall -Wextra -Werror -fsanitize=address,undefined \
  -Idm/third_party/vulkan-headers/include \
  dm/gfx/vk/tests/t_pass_coalesce.c -o "$TMPDIR/kh2-coalesce-test"
"$TMPDIR/kh2-coalesce-test"
```

PASS: five aspect checks and eleven coalescing-eligibility checks, ASan/UBSan.

Standalone real-Metal replay only, without a game/host/device/save:

```sh
bash dm/gfx/vk/tests/run_replay_coalesce.sh --red
bash dm/gfx/vk/tests/run_replay_coalesce.sh
bash dm/gfx/vk/tests/run_replay_coalesce.sh --default
MTL_DEBUG_LAYER=1 MTL_SHADER_VALIDATION=1 \
  bash dm/gfx/vk/tests/run_replay_coalesce.sh --default
```

The disabled control fails at the intended merge assertion (exit 134, two
encoders). Explicit-on and native-unset runs each pass all five checks: drawn
LOAD/STORE merge with red-pixel readback, feedback cut/resume, buffer-backed
attachment rejection, heap-backed attachment rejection, and color/depth/stencil
GPU readback. Metal API and GPU Validation explicitly report enabled in the
last run. No gameplay FPS, physical iOS touch/rotation, or installed-build
behavior is established by these source/replay checks.
