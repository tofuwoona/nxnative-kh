# KINGDOM HEARTS - HD 1.5+2.5 ReMIX -

Switch base title `010090C022978000`, base package 1.0.0, SDK 20, Vulkan. The collection launcher is Program 0; KH1 is Program 1 (`010090C022978001`), and KH2 is Program 3 (`010090C022978003`). The registered root profile is **experimental**: the launcher was observed, but selecting a game hung; it is not evidence that the collection is playable or that the standard NSP build produces the direct apps below.

## Status and boundaries

| Target | Status | Limit |
|---|---|---|
| Collection launcher | Reached on Mac | Game selection was not fixed. |
| Direct KH1 | Built and installed on iPhone; user reported save/load and face-swap working | Black HUD bars and broader rendering/gameplay remain open. Shared Program 0 `SettingMenu` files were needed. |
| Direct KH2 | Built and installed on iPhone; user played; Mac direct build reached Twilight Town | Scene slowdowns remain. The later X/Y-fix IPA was packaged but **not installed or device-tested**. |

The tested direct profiles are under `direct-profiles/`, not selected by the collection builder automatically. They contain only derived metadata, not game assets. To query a direct profile from the repository root:

```sh
DM_GAMES_DIR="$PWD/dm/games/010090C022978000/direct-profiles" \
  python3 dm/games/game.py 010090C022978003 program_id
```

The KH2 profile's `mem_used 0x4200000` and KH1's `0x4a00000` reflect observed rewritten module sizes; the full memory range has not been independently characterized. The files under `direct-profiles/` do not implement automatic extraction of Programs 1 and 3 or their shared data. See [release handoff](../../../docs/agents/kh-release-handoff.md) for the local build, resource staging and save boundaries. Keep the user's NSPs, keys, extracted game data, shaders, saves, signed IPAs and provisioning files outside this repository.

## Changes used in the direct builds

The existing working tree contains the following changes; they need review and separation before committing:

- Vulkan replay: render-pass attachment clear/store behavior, resolve handling, dynamic blend constants and stencil reference. Generic semantics belong in `dm/gfx/vk/`, not in a KH-specific binary patch. Mid-pass clear still needs a focused correctness regression test, including untouched attachments and multisample behavior. The same file also contains opt-in, game-specific shader overrides and tracing that were **diagnostics only** and should not be shipped as fixes.
- The program-index `MountRom` overload uses `DM_ROMFS_<index>` for another program's shared RomFS, with a fallback to `DM_ROMFS`. KH1 needed Program 0's `SettingMenu` assets; test other multi-program games before treating the fallback as general semantics.
- An experimental movie decoder event-signaling change is present in the working tree; KH1 movie playback was not verified. Keep it separate from a release-ready patch until its semantics and regressions are tested.
- Optional SDL2 Mac controller fallback (`SDL2=1`, `DM_SDL_GAMEPAD=1`) and iOS face-button swap setting. The X/Y correction's host test covers the bit transformations; physical and touch behavior of the later IPA remains unverified.
- The KH2 release shader library retained original alpha discard. Diagnostic raw-texture and no-discard shaders changed visual or coverage behavior and must not be promoted as fixes.

## Experimental KH2 color-processing shader

The latest X/Y IPA contains a separately rebuilt fragment shader `80a74ee192e6490b` whose immutable color-vision tables were moved to Metal constant storage. This is **not integrated** into `dm/gfx/tools/vk_shaders.py`. `build_color_experiment.py` preserves the per-shader experiment in a fail-closed, opt-in wrapper: it refuses a generated MSL input different from the validated hash. Given the user's own captured KH2 SPIR-V directory and the normal compiler's dependencies, rebuild into new directories, for example:

```sh
python3 dm/games/010090C022978000/build_color_experiment.py \
  /path/to/kh2/vk_capture /path/to/output/mac --ios /path/to/output/ios
```

Do not write generated libraries or game-derived shader sources into this repository. A Mac Metal differential test checked 440 gamma/color-vision combinations (1,802,240 RGBA comparisons, zero reported differences) with gamma, color and alpha negative controls; that finite test is not a proof across all inputs, formats or iPhone GPUs. A similar-scene Mac comparison improved from 39.02 FPS / 28.29 ms GPU HUD to 60.00 FPS / 7.57 ms, with slight camera differences; the user reported the optimized build performed well on iPhone. Other scenes still slowed down. Any translator change must preserve and revalidate this experiment; do not generalize the regex rewrite to other shaders.

## Open issues

- The reported screen ripple on transition from scripted fight camera to player control is **not confirmed to be depth of field**. Static analysis shows the `main+0x1eec50` event handler's case 0 calls `main+0x1ad190` with `(event_id, 1, 3, 0x9c41, 0)`. A new isolated run installed probes at the event-case dispatch (`main+0x1eec94`) and case-0 call site (`main+0x1eecb8`); neither was reached through the title/tutorial, so no ripple was observed. The Mac host now has an opt-in, exact-build-gated debug command: launch with `DM_PAX_FORCE=1`, then append `pax 0` or `pax 1` to `DM_CTL`. It queues a one-shot case-0/effect-ID override at the next validated PAX event, on the guest event thread without writing event memory. Later isolated Mac runs dispatched IDs 0 and 1 on validated case-0 events; neither dispatch by itself establishes that the screen-wide ripple was captured. A requested Metal pass/texture dump produced only acknowledgement lines, no `[pass]` records or target files, so no renderer root cause is established. Use isolated saves only; this does not establish a cause or fix.
- A temporary Mac-only `DM_KH_HID_TRACE` trace in HLE `fill()` observed KH2's returned Npad input state; the instrumentation has since been removed and the normal host rebuilt. In isolated runs, `DM_CTL` full-scale stick input reached the guest in both console (`No1`) and handheld (`Handheld`) modes with the expected axes and direction bits; B advanced the tutorial prompt, but Roxas did not move on tested stick/D-pad directions. This does not establish whether the game-side movement path or scene state is responsible.
- Fire effects in a later fight and the Seven Wonders bag encounter have user-reported slowdowns; they have not been isolated in matched captures.
- An in-game KH2 save overwrite reportedly succeeds but old progress appears after restart. The isolated Mac run that the user played (`kh2-save-repro-15`) logged two startup commits with zero writes, no later save commit, and no `config1525.dat`; it cannot verify the user's iPhone overwrite. A separate older `mac-dof-investigation/save` fixture has a 7 MB `KHIIFM.png` with an `sqEX` save-data chunk in both a literal-backslash filename and a nested slash path. In that earlier run, the nested file changed after 24 save writes and commit #3 while the flat file remained byte-identical to its source; startup separately opened the flat backslash path. This is a concrete stale-path divergence. In the KH2-specific host fix, a legacy flat file is cloned into the canonical nested path in the *working* save tree if that path does not already exist, and KH2 save paths using backslashes resolve to the canonical path. The flat original remains intact. A RED→GREEN FS test demonstrated that both spellings read the same slot after overwrite and remount; 67 FS checks and the full host suite pass. On an isolated flat-only copy of the real PNG, the rebuilt Mac host staged the canonical file, opened the save through the backslash guest path, created `config1525.dat` in the nested directory, and committed one write. The title-screen Load item was still grey, so a playable save/overwrite/relaunch test and the reported iPhone symptom remain **unverified**. Separately, the host now refuses a save Commit and notifies the front end after a failed DeleteFile instead of silently publishing stale content. No iPhone build has been installed; all baseline/device saves remain untouched.
- iPad new-game startup failed because Metal rejected BC3 texture format 134; a compatibility fix is not verified.
- Simulator build was blocked by missing Metal 4 declarations in the tested simulator SDK; no simulator gameplay was demonstrated.
- Keep 16:9 until projection, render targets, HUD and movies can be tested together. Do not stretch or crop as a widescreen fix.
  - An opt-in `DM_ASPECT_FILL=1` toggle exists (dm/host/aspect_fill.h) that crops the rendered 16:9 picture to fill the screen with no black bars, instead of fitting it with letterbox/pillarbox bars (the default, unchanged). It does not stretch and does not touch the game's own rendering, camera or HUD -- it only crops which part of the already-rendered 16:9 frame is shown, so it is implementable without an engine/NSO patch. The trade-off this paragraph already warns about still applies: HUD elements positioned near whichever edge gets cropped (top/bottom on a screen wider than 16:9, e.g. iPhone; left/right on a screen narrower than 16:9) may be clipped. Verified end-to-end on the Mac host (title screen fills a 1600x700 window edge to edge with DM_ASPECT_FILL=1, vs. clear black pillarbox bars without it) and with a pure-math unit test (dm/host/tests/t_aspect_fill.c) for the shared touch-coordinate remapping (DmGamepad.m, front_mac.m) -- not yet verified against real gameplay HUD/movies at a cropped aspect, so still off by default.

Before updating from upstream, preserve the worktree and compare [the update checklist](../../../docs/agents/kh-upstream-update-reminder.md). Do not claim current work is rebased or compatible with upstream without checking it.

## Continuous diagnostic build (not a release build)

Opt-in, KH2-only instrumentation (branch `diag/kh2-continuous-save-metal-logging`) adds rolling save/filesystem and Vulkan-to-Metal pass tracing, gated by `DM_KH24_DIAG=1` (zero cost when unset):

- `dm/host/hle_fs.c`: `[save-trace]` lines for open/create/write/resize/delete/commit on the save mount only (`DM_SAVE_TRACE=1`).
- `dm/gfx/vk/hle_vk.m`: `[vk-diag]` lines for each render pass's attachments/formats/load-store state, pass end/resume, and bound pipeline/shader keys (`vk_diag_on()`, program ID gated to KH2 Program 3).
- `dm/ios/Sources/log_rotation.h` + `main.m`: a background thread calls `dm_log_rotate_file` on `stderr` every 250 ms; at 1 GiB it `rename`s the active file to `log.prev.txt` and opens a fresh `log.txt` via `dup2`, so the stream and its fd never change under the writer. Exactly two segments exist at any time (max 2 GiB), each overwritten on its next rollover. A unit test (`dm/ios/tests/t_log_rotation.c`) exercises two rollovers.
- `scripts/kh2_diag_mac.py`: Mac-only equivalent — wraps `dmhost`, requires `DM_GAME=010090c022978003` and an explicit `DM_SAVE`, never selects a save path itself, and enforces the same two-segment 1 GiB rotation on the host's stdout+stderr.
- `dm/games/010090C022978000/kh2-24h-diagnostic.env`: the `DM_ENV_FILE` used to bundle `DM_KH24_DIAG=1` into an iOS build via `build_ipa.sh`.

Verified: `dm/host/tests/test_kh_save_trace.py`, `dm/host/tests/test_kh_diag_mac.py`, `dm/host/tests/test_kh_vk_trace.py` pass; `t_fs` is 67/67. An isolated Mac run (`kh2-diag-smoke/`) produced thousands of real `[vk-diag] pass` entries at the title screen alone, and `[save-trace] open/create/resize/commit` entries from mounting a legacy flat save fixture. A `--prepare-xcode` + `xcodebuild` Release build succeeded unsigned; its binary contains the `[vk-diag] pass`/`[save-trace] commit`/`[kh2-diag] log rotated` strings and the bundled `dm/env.txt`, but `[save-trace] write` was not found as a literal string (likely inlined/deduplicated by the optimizer; not independently confirmed present at runtime). This has **not been installed on the iPhone or run on device**: the unsigned IPA (`KH2-continuous-diagnostics-unsigned.ipa`) still needs install, launch, and a sustained on-device run to confirm log rotation and trace volume over real play. Do not treat this instrumented build as release-quality; it is a debug build with extra logging only, not a save/camera fix.
