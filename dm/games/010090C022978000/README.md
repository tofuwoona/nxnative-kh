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

- The reported screen ripple on transition from scripted fight camera to player control is **not confirmed to be depth of field**. The mission `miss` PAX is a plausible camera-cut effect; a playback trigger has not been implemented or runtime-verified.
- Fire effects in a later fight and the Seven Wonders bag encounter have user-reported slowdowns; they have not been isolated in matched captures.
- An in-game save overwrite reportedly succeeds but old progress appears after restart; the title and slot are unconfirmed. Preserve all committed and working saves; no cause or fix is established.
- iPad new-game startup failed because Metal rejected BC3 texture format 134; a compatibility fix is not verified.
- Simulator build was blocked by missing Metal 4 declarations in the tested simulator SDK; no simulator gameplay was demonstrated.
- Keep 16:9 until projection, render targets, HUD and movies can be tested together. Do not stretch or crop as a widescreen fix.
  - An opt-in `DM_ASPECT_FILL=1` toggle exists (dm/host/aspect_fill.h) that crops the rendered 16:9 picture to fill the screen with no black bars, instead of fitting it with letterbox/pillarbox bars (the default, unchanged). It does not stretch and does not touch the game's own rendering, camera or HUD -- it only crops which part of the already-rendered 16:9 frame is shown, so it is implementable without an engine/NSO patch. The trade-off this paragraph already warns about still applies: HUD elements positioned near whichever edge gets cropped (top/bottom on a screen wider than 16:9, e.g. iPhone; left/right on a screen narrower than 16:9) may be clipped. Verified end-to-end on the Mac host (title screen fills a 1600x700 window edge to edge with DM_ASPECT_FILL=1, vs. clear black pillarbox bars without it) and with a pure-math unit test (dm/host/tests/t_aspect_fill.c) for the shared touch-coordinate remapping (DmGamepad.m, front_mac.m) -- not yet verified against real gameplay HUD/movies at a cropped aspect, so still off by default.

Before updating from upstream, preserve the worktree and compare [the update checklist](../../../docs/agents/kh-upstream-update-reminder.md). Do not claim current work is rebased or compatible with upstream without checking it.
