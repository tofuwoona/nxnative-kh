# KH2 adaptive display ingress (CPU-tested; runtime acceptance separate)

The launcher row `DM_KH2_ASPECT_EXPERIMENT` defaults ON for exact Program 3;
saved OFF remains honored. Native activation still requires the exact string
`1`, Program ID `010090C022978003`, loaded main build key
`e1bced80ffd14436980f7490b1d3c3e7`, and the complete accepted v3 payload capability.
Unset/invalid values, OFF, unknown builds and sibling profiles preserve legacy
behavior. The build key alone is not instruction-byte verification: existing
mask capability validation remains required and unchanged.

## Selection and publication

`dm_kh2_aspect_init(uint32_t viewport_w, uint32_t viewport_h)` is a startup-only
writer. `dm_kh2_aspect_size()` reads one atomically published width/height pair;
zero/zero means disabled. OE, Vulkan and both touch consumers use that pair.
Only the front end calls init, after host loading/final settings and viewport
creation, before guest allocation, CPU state initialization or graphics startup.
No frame-time UI/loader queries, environment rereads, or live guest resizing are
introduced. Reinitialization is only valid with the guest stopped (regression
fixtures also exercise warm flag clearing).

The selector reduces positive integer viewport dimensions by GCD and chooses the
largest integer multiple within **960..1920 by 540..1080**, preferring the largest
even multiple when it still meets both minimum axes. These are guest per-axis
limits, not a pixel-area budget: the authentic startup/resize code clamps BOTH
axes if either axis violates its bounds, and an internal backing resource remains
1920x1080. Never raise those caps or pass native pixels directly to the guest.

Supported landscape ratios are **16:9 through 20:9**, inclusive. No phone-model
whitelist is used. Zero, overflowing/over-16384 viewport axes, narrower/portrait/
tablet/extreme ratios, and exact ratios whose reduced units cannot meet the
budget and minimums fail closed: no adaptive dimensions or guest feature bits.
Floating-point viewport conversion rejects nonfinite/fractional pixels except
for tiny (1e-6 pixel) arithmetic representation error. There is no nearest-ratio
approximation, crop, or stretch used to make an unsupported ratio pass.

Examples (viewport pixels → guest render dimensions):

| Viewport | Render |
|---|---|
| 1920x1080 | 1920x1080 |
| 2556x1179 | **1704x786**, baseline compatibility |
| 2400x1080 | 1920x864 |
| 2532x1170 | 1688x780 |
| 2796x1290 | 1864x860 |
| 2436x1125 | 1624x750 |
| 2688x1242 | 1792x828 |
| 2340x1080 | 1898x876 |

These are dimension fixtures, not claims of testing those physical phones.
The accepted v3 CPU/mask emitter and payload headers are unchanged. Its original
physical-aspect branch already consumes runtime renderer dimensions; the media
caller exception, title/media mask periods, full producer state and geometry-only
collapse of the owned quads remain intact. Original shaders are unchanged.

## Front ends and controlled Mac tests

- **iOS:** snapshot the full root view bounds times its current screen's native
  scale on the main queue. Do not use the early, already-letterboxed game view.
  Validate/publish on the host thread, then complete main-queue relayout before
  guest entry. Direct calls already on the main thread avoid dispatch-sync deadlock.
- **Mac window:** create/show the real window, fit its actual Metal drawable, and
  initialize from that actual pixel size before creating the guest thread.
  Default content geometry remains 1280x720 points.
- **Mac diagnostic:** `DM_WINDOW=1 DM_KH2_VIEWPORT=1704x786` requests real content
  pixels, converting by the window backing scale before fitting/readback.
  Strict syntax is `WIDTHxHEIGHT`, bounded to 320..4096 by 180..4096; malformed
  explicit values abort startup. An even pixel pair allows integer point sizes
  on a 2x display. `2556x1179` may be rounded by AppKit; the actual drawable,
  not the request, controls selection. Check both the `front end: drawable` and
  `KH2 startup viewport: window drawable` logs and independent live drawable
  readback. A screenshot re-encoded with `DM_NVN_SHOT_OUT` is not viewport proof.
- **Headless:** `DM_KH2_VIEWPORT` is explicitly a diagnostic viewport. Without it,
  the logged fallback is 1920x1080 (16:9), never a pretend physical display.
- **Later resize/fullscreen/rotation:** only presentation fits the fixed startup
  source. This is not safe live guest-aspect reconfiguration; relaunch at the
  desired viewport. In particular asynchronous `DM_FULLSCREEN` transitions after
  startup do not select a new guest ratio. Controlled tests should use windowed
  startup geometry, not a subsequent resize as evidence of a new guest aspect.

Present still fits the actual full source without extra crop while active. Touch
uses the published render ratio. Off-path image-origin flooring and historical
fractional touch origins are unchanged. `DM_ASPECT_FILL` is not rewritten and
retains its legacy behavior when adaptive mode is disabled. Guest-requested VI
source crops are neither removed nor invented. Thermal mode changes do not
change the latched adaptive resolution.

## CPU regression commands

Run in an isolated source export with `TMPDIR` set to an owned scratch directory.
The mask fixtures require the real private reference modules via an explicit
`KH2_MASK_INPUT`; mask CPU execution additionally requires Unicorn. Tests that
need private modules or captured state skip cleanly when their corresponding
environment variable is absent. No game modules belong in the patch.

```sh
python3 -m unittest discover -s dm/host/tests -p 'test_kh2_adaptive*.py' -v
python3 -m unittest discover -s dm/host/tests -p 'test_kh2_aspect*.py' -v
python3 -m unittest discover -s dm/host/tests -p 'test_kh2_mask*.py' -v
python3 dm/host/tests/test_ios_image_origin.py
python3 dm/ios/tests/test_launcher_render_preferences.py
python3 dm/tools/tests/test_launcher_settings.py
```

Tests execute extracted production OE/gate/Vulkan extent bodies with real
profile headers and real payload validation, header policy against an independent
integer-search oracle, actual iOS/Mac touch/image and present-fit arithmetic,
main ordering, UIKit queue branches, and Mac window-size/readback/headless slices.
UI, loader/thread/guest boundaries are explicitly labeled seams; ASan/UBSan run
on native CPU harnesses. These are not AppKit/UIKit integration or GPU tests.

## Acceptance still required

Parent owns host/app builds, live Metal-window readback, actual field/camera and
culling behavior, backing/depth/resolve/postprocess checks, HUD/minimap/menus,
movie/title framing, sustained freeze regressions, touch and physical iPhone
15 Pro comparison. Passing CPU tests does not certify every in-bounds extent,
other physical phones, orientation changes, rendering performance, or gameplay.
