# KINGDOM HEARTS - HD 1.5+2.5 ReMIX -

Experimental Vulkan profiles for the Switch base package 1.0.0 (SDK 20). Only KH1 and KH2 have been tested in this fork. The collection launcher is not a working game-selection route; use the separate direct profiles. See the [root README](../../../README.md) for fork scope, credits and known issues, and the [build guide](../../../docs/KINGDOM_HEARTS.md) for staged inputs and packaging limits.

## Programs and exact base-build identities

| Target | Program ID | `main` build key | Observed scope |
| --- | --- | --- | --- |
| Collection launcher, Program 0 | `010090C022978000` | See [collection profile](game.tsv) | Launcher reached; game selection unsupported |
| KH1, Program 1 | `010090C022978001` | `badf2faf580b712464365c4d529d92c9` | Separate iPhone app tested; reported save/load and face-button swapping, not complete gameplay coverage |
| KH2, Program 3 | `010090C022978003` | `e1bced80ffd14436980f7490b1d3c3e7` | Separate iPhone app and Apple-silicon Mac direct-game testing, not all-scene/device coverage |

The [KH1](direct-profiles/010090C022978001/game.tsv) and [KH2](direct-profiles/010090C022978003/game.tsv) profiles each require `main subsdk1 sdk`, with shared `sdk=bc204aae7319bab274894f1cc3f5da92` and `subsdk1=99e21f98a397434b534c1459fc38a2b8`. These identities are build-specific, not support for arbitrary updates. Their rewritten-module reservations are `0x4a00000` and `0x4200000` respectively; these are not total-memory measurements or guarantees for other builds.

From the repository root, query metadata without building or accessing game assets:

```sh
DM_GAMES_DIR="$PWD/dm/games/010090C022978000/direct-profiles" \
DM_GAMES_FIRST=1 \
  python3 dm/games/game.py 010090C022978003 program_id
```

The inherited collection builder does not automatically extract/select these direct programs or stage shared data. KH1 needs the collection's `SettingMenu.hed` and `SettingMenu.pkg` in its staged layout. Supply lawful inputs outside Git; the profiles contain metadata, not assets. A prepared Xcode project, source push or successful CPU suite is not an installed-app update.

## Save repair and evidence limits

The original cached-write path can acknowledge a complete record while leaving it only in guest RAM. Its background worker uses an approximately **601-second worker-baseline cadence**, not a fixed delay from menu confirmation. Host flushing alone cannot serialize that cache.

The reviewed KH2 repair synchronously invokes the **original serializer per complete record**, with shared cache/lifecycle exclusion, positive-length inverse restoration, actual Commit/close-error handling and recoverable PNG-error cleanup. It preserves the original format, direct-filesystem mode and worker cadence. Logical PNG failure uses the existing filesystem poison/rollback engine, not a replacement save writer.

Independent source/CPU review and a bounded real Mac menu failure → same-process retry → independent cold-load trial support the KH2 mechanism. KH1's separately mapped port is implemented and independently source/CPU-reviewed, but its actual-menu save/retry/cold-load acceptance remains outstanding. **Physical-iOS acceptance of both new repairs is outstanding.** Existing KH1 save/load reports and shared filesystem tests do not certify the newly built app.

A menu may publish **intermediate valid per-record generations**. Failure of a later record does not undo every earlier Commit. No whole-menu atomicity, sudden-power-loss durability, all-slot coverage or lifecycle guarantee is claimed. Back up `Documents/save` and `Documents/save.work` separately when present, and verify the intended saved row after reopening.

Read the [save-persistence guide](../../../docs/kh-save-persistence.md) for exact gate/module activation, matching newly built host plus freshly rewritten **all three modules and metadata**, portable CPU commands and optional private-input probes. Do not reuse an older gate set, mix build tables or bypass fail-closed guards. Historical `kh2` filenames/API names alone do not establish KH1 support.

## Rendering and controls

- **MISS effect render fix** (`DM_VK_COALESCE_PASSES`) is **on by default only for exact KH2 Program 3**. It coalesces compatible render passes and reduces, but does not eliminate, effect-heavy stutter. Existing saved `0` and `1` choices are honored; no migration forces it on. `0` disables it, `1` enables it, and explicit env-file overrides take priority over saved preferences. Relaunch after changing an override because native gates are cached. KH1 does not inherit the KH2 default.
- **Fill screen (crop)** (`DM_ASPECT_FILL=1`) is opt-in; normal `0` fits the original 16:9 picture with bars. Cropping may clip HUD and adds no world view. The temporary **Preserve full HUD** option is removed; legacy `DM_PRESERVE_FULL_HUD` values are inert. True widescreen projection and HUD relocation remain unfinished.
- KH2 touch geometry places **X on the left, Y at the top**. Positioning does not remap their actions. **Swap face buttons** separately swaps A/B and X/Y for touch and physical controllers.
- The opt-in [color-processing experiment](build_color_experiment.py) is an input-hash-gated shader step, not an automatic part of the generic shader compiler or a general fix for slow scenes. Keep game-derived shader inputs and output outside Git; retain original alpha-discard semantics and revalidate any translator changes.

See [settings definitions](../settings.tsv) and [shared aspect policy](../../host/aspect_fill.h). Source defaults do not change an existing app installation.

## Optional diagnostics

Program 3 has three separate **default-OFF** launcher settings: **Save traces** (`DM_SAVE_TRACE`), **Record controller inputs** (`DM_KH_INPUT_TRACE`) and **Detailed render logging** (`DM_KH24_DIAG`). They apply at **Play**, before native gates cache values; relaunch to change them. The MISS rendering setting is independent.

Explicit process diagnostic values take priority over `Documents/env.txt`, then bundled `dm/env.txt`, then saved launcher choices or new-install defaults. Overridden rows are locked; startup does not rewrite their saved preferences or override files. Use `0`/`1`. Legacy process/file `DM_KH24_DIAG=1` defaults save tracing on unless `DM_SAVE_TRACE` is explicit, including `0`. Choosing render logging in the launcher alone does not enable either other toggle.

Normal packaging bundles no `DM_ENV_FILE` override. Check saved choices and existing override files as well as build settings. All three toggles OFF still retain ordinary operational/error logging in `Documents/log.txt` and previous-launch retention in `log.prev.txt`; this is **not zero logging**.

The [continuous-diagnostics template](kh2-24h-diagnostic.env) is explicit opt-in. Any enabled KH2 trace activates two rotating 4 GiB segments at Play, nominally 8 GiB retained plus polling overshoot. Copy both before rotation/relaunch replaces them. High-volume traces can affect performance; CPU rotation tests do not establish on-device rollover acceptance. See [diagnostic guidance](../../../docs/KINGDOM_HEARTS.md#normal-operation-and-optional-diagnostics).

Input records are host-published controller states, not raw touch positions, launcher actions or game randomness. They do not establish deterministic replay or repair saves. The [Mac diagnostic wrapper](../../../scripts/kh2_diag_mac.py) is separately opt-in and requires an explicit copied save path and matching confirmation. Use the existing in-game menu route with isolated copies, never live progress. Do not publish raw logs or personal saves.

## Remaining limits and source-only boundaries

KH1's black HUD bars remain unresolved. Overlapping KH2 effects and other scenes can still stutter; no general performance fix is claimed. iPad compatibility remains unverified after a reported BC3 rejection, and the tested simulator SDK lacked required Metal 4 declarations. Neither simulator nor CPU success replaces physical-device testing. Collection switching and the other collection programs remain unvalidated.

Keep game packages, keys, original/rewritten modules, RomFS, game-derived shaders, artwork, saves, game-containing apps/IPAs, signing material and private evidence outside Git. Share source, synthetic fixtures and sanitized reproduction steps only. The [MIT license](../../../LICENSE) covers runtime source, not third-party game content; dependencies retain their [own licenses](../../third_party/README.md). This documentation is not public-release clearance or certification that historical commits contain no private material.
