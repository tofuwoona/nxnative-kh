# KH2 Program 3 true-widescreen investigation (not an enabled mode)

## Status / evidence

This branch starts at `1b0476abd4329dbbb1469a4fa1895d72b09c6d41` of **nxnative-kh**, not upstream nxnative. The source under investigation is KH2 Program 3 (`010090C022978003`, profile main BUILD_ID `e1bced80ffd14436980f7490b1d3c3e7`); the Mac host launched `program3_patched/main.patched.bin`, not Program 0 or `patched_v0`. The game resources were read from the separately extracted Program 3 RomFS; an isolated copy of the existing Mac diagnostic save was used. Neither phone nor its save was touched.

- Actual host run (`/Users/tofu/.hermes/cache/scratch/kh2-wide-evidence/run.log`): Vulkan `vkCreateSwapchainKHR` creates three 1920x1080 images; at frame 0 / submit 13, `VPTRACE` sees the full-target draw `vs=d65da5b64d80bc07 fs=ba448af6ad311465` with a depth attachment and a later fullscreen `vs=4224d4542e2f8e20 fs=80a74ee192e6490b` sampling a 1920x1080 texture, without depth. `UBOTRACE` reports fullscreen `FillScale=1`. The shader table for this profile lists the fullscreen vertex shader's uniform binding `0.2`, while candidate geometry shader `4c1e2f47738ed1ba` has bindings `0.2/0.3/0.4`. **These early loading frames do not identify the gameplay camera projection or isolate the UI pass.** Frames 120/240 show black loading screens with small heart icons, not gameplay, HUD, menu, or a movie. This is no wider-FOV visual proof.
- `dm/gfx/vk/hle_vk.m`: `vkCmdSetViewport` and `vkCmdSetScissor` record Vulkan commands; `pre_draw` applies them at Metal draw time. `vkCreateGraphicsPipelines` handles both static and dynamic viewport state. The framebuffer/render-pass attachments are game-owned; changing a viewport in isolation changes raster coordinates, not the perspective projection or offscreen allocation. `vkQueuePresentKHR` passes the VI crop and swapchain image to `mtl_present_ext` in the shared NVN Metal path. `nvn_mtl.m:present_fit` only samples a source rectangle and determines the final screen viewport; `DM_ASPECT_FILL=1` discards top/bottom on a wider phone. None of this creates new world geometry.
- Existing `DM_VK_UBOTRACE`, `DM_VK_VPTRACE`, `DM_VK_VPTRACE_FRAME`, and per-pass `[vk-diag]` can narrow down candidate world, overlay, movie, and postprocess draws in a **matched gameplay frame**. The currently bounded UBO trace identifies possible `Projection2D`, `LocalProjection0`, `WorldView`, and movie uniforms but was previously written for other game observations; key presence in the shader table is not proof of the camera matrix layout or draw classification in KH2. Do not change those bytes blindly.

## Safe implemented slice

`dm/gfx/vk/kh2_wide_layout.h` computes, without touching rendering, the centered full-height 16:9 HUD-safe rectangle and two equal world-only side-strip widths for a wider target. It rejects invalid input and declines expansion for equal/narrower ratios. `tests/t_kh2_wide_layout.c` checks partitions without gaps, safe rect bounds, identity/fitted fallback and invalid sizes. The planner is **not called by the game**: this is a tested compositor geometry contract, not an opt-in widescreen toggle. The existing default fit and independent `DM_ASPECT_FILL` option remain untouched. No feature flag is exposed because an enabled flag that only scales/crops the original frame would misrepresent the result.

## Design to unlock after evidence (not implemented)

1. **Camera/world:** Trace a gameplay frame to distinguish 3D geometry shaders and their actual bound projection matrices from orthographic HUD vertices. Verify which constant is the camera's perspective x-scale using at least two camera poses and a window-space correspondence; preserve the vertical field of view, recompute horizontal field of view for the physical aspect and extend the render target, depth, resolve, postprocess intermediates and final swapchain consistently. Verify culling/frustum visibility; the guest may cull against the old aspect before the shader runs. A viewport-only change or final-image stretch is invalid. Require an image differential in which a stationary camera shows genuinely *new* scene objects at both outer edges, while the central 16:9 content remains geometrically comparable.
2. **HUD and menu:** Preserve original 16:9 coordinates in a separate transparent overlay and center that overlay in the planner's safe rectangle. Keep all dialogue, subtitles, pause/title/save menus, command panels and cursor highlights in that rectangle. If the game composites HUD before a postprocess or into the world color attachment, identify that boundary from pass/texture evidence; do not simply replay blended draws, because depth/stencil, temporal effects, clears and sampling feedback could differ. Composite with premultiplied-alpha-aware blending after the appropriate color treatment; clear side strips, render actual world there, and verify no transparent pixels/gaps at rectangle seams.
3. **Movies/cutscenes:** Detect pre-rendered videos via their concrete decoder texture/draw chain; letterbox or pillarbox entire 16:9 frames instead of widening pixels or displaying synthetic sides. In-engine cutscenes can widen only after camera/event framing and subtitle placement are checked; otherwise fall back to original full 16:9 fit for that entire frame. Title and pause screens default to fit until categorized and visually inspected. No guessing from a single shader hash.
4. **Touch:** For a full-screen world+safe-HUD composite, map touches in the centered safe rect to normalized original 16:9 coordinates, not through `dm_aspect_visible()`'s crop mapping. Reject or explicitly define touches in world-only strips; virtual controls outside the Metal view need their own view-relative handling. Movies and fallback fit must use the original fit mapping. Test corners, safe-rect boundaries, device rotation, and controller overlays.
5. **Gate/fallback:** A future `DM_KH2_TRUE_WIDE=1` must be KH2 Program-3 exact-build gated, default off, mutually exclusive with `DM_ASPECT_FILL`, and must fall back atomically to existing *fit* on unknown scene/pass classification, missing render targets, incomplete overlay, incompatible postprocess, movies or narrower screens. Never present a partially widened frame with missing pixels. No deployment until gameplay, pause/menu, movie and cutscene screenshots plus touch checks on Mac pass and the user authorizes phone testing.

## Follow-up Mac gameplay capture (isolated save; no true-wide feature)

A 230.92-second Mac Program-3 run used the isolated iPhone17 backup copied twice into a scratch-only save (literal backslash filename and canonical nested path); the original backup was not written. `DM_KEYS=f2200:Down,f2220:A,f2500:A` opened the LOAD menu and loaded the existing Merlin's House slot. The host exited gracefully, and no dmhost process remains. Evidence: `/Users/tofu/.hermes/cache/scratch/kh2-wide-evidence/run220/` (`invocation.txt`, `source-sha256.txt`, `run.log`, `result.txt`, frame screenshots 2100/2500/3000/4000/4500 and `trace-summary.json`). The frame-2500 screenshot displays the four-slot load menu; frame 3000 and 4500 show **actual 3D gameplay in Merlin's House**, with command panel, minimap and party HP/MP gauges all visible. Frame 3000 shows the bright save-point effect. These are 16:9-only screenshots, **not** visual wider-FOV proof.

In frame 3000, `VPTRACE` changed-state records show mixed full-target 1920x1080 rendering (97 records) and 256x256 intermediates (25 records). Geometry candidate `d7a52a49f521f4f0/a552cfafcf3c0899` occurs 52 times, and `5715f513ed87a8a9/8061129a84c22e46` 24 times; the final `4224d4542e2f8e20/80a74ee192e6490b` draw writes a 1920x1080 no-depth target while sampling a 1920x1080 texture. The 256x256 loop alternates clear, `cc4227.../a552...` and `5715.../a32c...`; it is not a world/HUD split. The 256-record cap is reached over frames 3000–3002, so the records are **not a complete pass/draw inventory**. The image confirms world and HUD coexist onscreen, but the trace has not identified a safely separable HUD attachment or a validated world projection matrix. No camera or compositor bytes were changed.

`DM_VK_UBOTRACE_MIN_SUBMIT=3000` was mistargeted: gameplay frame 3000 actually spans submissions 4316–4319; the printed UBOs near submit 3000 belong to earlier frames. They must not be correlated with this screenshot. The checked-in `dm/gfx/vk/tests/kh2_trace_summary.py` is an offline fixture that preserves attachment/source texture records and explicitly reports the cap and true submission range; its synthetic and real-capture tests pass. The next **short, externally coordinated** capture can target UBO submit 4316 and narrow VPTRACE to the relevant draw family (or raise the cap in a tightly bounded diagnostic build), with paired pre/post-UI attachment images. Do not run a second long host session while the separate Mac GPU profiling work is underway.

## Correctly-targeted capture and a real camera-rotation disproof

Two isolated-save re-runs (never the phone/original backup; the iPhone17 backup was only read,
copied fresh into scratch-only `run400`/`run401`/`run402` save dirs) resolved the stale-target bug
and produced a conclusive, not merely a mistargeted, result.

**UBOTRACE targeting was the actual bug, VPTRACE was not.** Rereading `run220/run.log` shows
`DM_VK_VPTRACE_FRAME=3000` (frame-counter mode) had already correctly logged the real gameplay
submits for that screenshot (`frame=3000 submit=4316…4325`, 256 total records capped only after
frames 3000 **and** 3001 were each fully enumerated — 122 complete changed-state records apiece;
only frame 3002 was truncated). The actual mismatch was `DM_VK_UBOTRACE_MIN_SUBMIT=3000`, a
*submit*-indexed window that landed on early loading-screen submits near literal value 3000, far
from the real submits 4316+. `run400` reproduced frame 3000 with `DM_VK_UBOTRACE_MIN_SUBMIT=4300`
(discovered from run220's own VPTRACE output) and got real, submit-matched UBO lines — but frame
3000 turned out to be a **camera-locked** moment: the loaded save spawns Sora standing in the save
crystal's interaction beam with the `X Save / Attack / Magic / Items / Drive` panel already up, and
the scene is pixel-identical from frame 2990 through frame 4500 regardless of stick input (confirmed
by screenshots and by `VPdiag`/`WorldViewdiag` never changing). That is not evidence those fields are
camera-driven; it is evidence the camera itself was locked, so it is an invalid test.

`run401` (discovery) and `run402` (full capture, identical deterministic save+keys) fixed that: a
left-stick hold (`f2520:LDown~2.5`) plus a right-stick turn (`f2900:RRight~0.6`) produced a
**confirmed real ~90° camera rotation** at frames 2910/2911 — screenshots `run401/frame-2890.png`
(facing the bookshelf/desk wall) through `run401/frame-3200.png` and `run402/frame-2911.png` (facing
a completely different wall, with a computer console/workbench) show the background change entirely
while Sora stays by the save point. `run401`'s own VPTRACE log (frame-keyed, no guessing needed)
gave the real submit numbers for that moment; `run402` re-ran the identical save/keys with
`DM_VK_UBOTRACE_MIN_SUBMIT` set from that real number (not a frame-number guess) and a wide-enough
margin that it kept matching even though submit numbering drifted by about a dozen when UBOTRACE's
own logging overhead was added (confirmed empirically: frame 2910 was submits 3954-3957 in run401,
3966-3969 in run402 — **submit windows must include margin, an exact single guessed value is not
reliable even run-to-run with identical `DM_KEYS`, because `f`-prefixed key timings pin the *frame*
counter, not the *submit* counter**). Both runs captured **complete, uncapped-for-that-frame**
changed-state inventories: frame 2910 and 2911 each logged 128 records with zero truncation (256
total split exactly across the two target frames), confirmed against `kh2_trace_summary.py`'s own
`submit_range` computation (`tests/test_kh2_trace_summary.py::test_correctly_targeted_capture_matches_real_submits`).
The 256-record cap was not raised; narrowing the window to the two frames that actually matter was
sufficient this time. (If a future target frame alone exceeds ~256 distinct changed-state draws, the
per-process `vp_logged` cap in `hle_vk.m` would need raising for a diagnostic build, or the capture
would need splitting into single-frame windows via separate runs — not done here because it wasn't
needed.)

**Result: the prior "VPdiag"/"WorldViewdiag" hypothesis is disproved, not confirmed.** Across the
whole genuine-rotation window (submits 3954-3985), for the three world-geometry vertex shaders
(`4c1e2f47738ed1ba`, `d7a52a49f521f4f0`, `8cca46c2723c962d` — the only shaders with all three of
bindings `0.2`/`0.3`/`0.4` per `vk_shaders.tsv`), binding `0.2`'s decoded `VPdiag` (bytes 80-143 of
its 144-byte UBO, the diagonal of a hypothetical 4x4 float matrix) and binding `0.4`'s
`WorldViewdiag` (bytes 0-63, same diagonal convention) are **both frozen at `1,1,1,1` on every single
logged submit**, before, during and after the confirmed camera turn. Binding `0.3`'s
`LocalProjection0diag` does vary, but in a pattern tied to *which specific mesh is being drawn*
(exact value triples like `246.001,266.502,0.554801` and `-1242.56,1664.89,0.775122` recur
byte-identically across different frames/camera angles, consistent with a fixed per-object/local
transform, not a per-frame camera one; its slowly-incrementing 4th component, e.g. `2013→2020→2026`,
looks like an animation/time value on the save-crystal effect object, unrelated to camera facing).
The `4224d4542e2f8e20` fullscreen-quad shader (the only resource it declares is `u:0.2`, a 64-byte
UBO with only `FillScale` in range) stayed `FillScale=1` on every sample through the same rotation —
this part of the prior hypothesis holds up under real evidence: that shader is structurally and
empirically camera-independent, a genuine 2D/HUD-postprocess pass. The `5715f513ed87a8a9` "movieVS"
shader's own `VPdiag`-labeled bytes are not camera-related either — they repeat byte-identically
across different camera angles for the same recurring UI/text draw (e.g. `231727,186248,1,0`) and
differ only between distinct UI elements, matching a text/sprite-atlas position field, not a matrix.

**So the discriminator that *is* evidence-backed today is structural, not byte-offset-based**: the
three world-geometry vertex shaders bind three separate UBOs (`0.2`+`0.3`+`0.4`); the fullscreen and
UI/movie passes bind only one (`0.2`). That alone cleanly separates the shader families in the
shader table and matches the observed camera-(in)dependence. It is **not** sufficient to safely
recompute a horizontal FOV, because the actual camera view/projection matrix has not been located.

**Next blocker (precise):** the real per-frame camera view/projection matrix is not among the
currently-decoded bytes of `d7a52a49f521f4f0`'s three UBOs at the previously-assumed diagonal
offsets, and this shader declares no other resources (no push constant, no additional binding) per
`vk_shaders.tsv`, so if a camera uniform exists at all for this shader it must be in an
**undecoded byte range** of the same three buffers (144/448/64 bytes; `vk_trace_ubo` currently only
samples specific named fields, not a full hex dump). The next step is a small, diagnostic-only
`DM_VK_UBODUMP`-style full-buffer hex dump (gated the same way, off by default) for exactly this one
shader key across a confirmed camera-rotation window like `run402`'s, to find which bytes actually
move with camera angle — or, if none do, treat that as evidence the perspective transform is applied
to vertices before upload (CPU-side, common in ported PS2-era renderers) rather than via a per-frame
camera uniform, which would need a different investigation path (vertex buffer content, not UBOs).
No such dump was implemented in this pass; it is unverified and intentionally not claimed. **No
wider-FOV change was made or should be made from this evidence.**

Evidence: `/Users/tofu/.hermes/cache/scratch/kh2-wide-evidence/run400/` (locked-camera control, shows
the bug in isolation), `run401/` (discovery run + screenshots proving the real ~90° turn), `run402/`
(full VPTRACE+UBOTRACE capture at the correct submits, `invocation.txt`, `run.log`, screenshots
`frame-2890.png`..`frame-3200.png`). `dm/gfx/vk/tests/test_kh2_trace_summary.py` gained three tests
against `run402`'s real log (skipped, not failed, on hosts without the scratch evidence).

## Next discriminating experiment

For a later short, GPU-coordinated experiment, use an isolated gameplay save and a matched frame. `DM_VK_VPTRACE_FRAME=<gameplay frame>` records changed states only and caps at 256 across three frames; `DM_VK_UBOTRACE_MIN_SUBMIT` needs the **submission number** measured in the first trace, not the frame number. Compare targeted pass/attachment and source-texture captures before and after HUD composition, then inspect actual Program-3 shader reflection and UBO matrix bytes at two camera poses. Correlate camera motion with projection and culling before changing a guest NSO byte or shader. The earlier 35-second run (frames 120/240) was only loading; the new gameplay run above resolves that screenshot blocker but not the true-wide renderer boundary.
