# Kingdom Hearts: build and source boundaries

This page describes the fork's direct-program inputs and existing packaging tools. It is **not a complete, validated clean-checkout build recipe**. Only KH1 and KH2 have been tested in this fork; inherited profiles do not establish compatibility for other games. See the [root README](../README.md) for current features, known issues and testing limits.

## Select the actual program

| Target | Program ID | Expected RomFS marker |
| --- | --- | --- |
| Collection launcher (not working game selection) | `010090C022978000` | Not a substitute for either direct program |
| KH1, Program 1 | `010090C022978001` | `kh1_second.pkg` |
| KH2, Program 3 | `010090C022978003` | `kh2_fifth.pkg` |

The direct profiles are nested under [direct-profiles](../dm/games/010090C022978000/direct-profiles), not automatically selected by the collection build. From the repository root, these **read-only** commands query the profile metadata; they do not build or access game assets:

```sh
export DM_GAMES_DIR="$PWD/dm/games/010090C022978000/direct-profiles"
export DM_GAMES_FIRST=1
python3 dm/games/game.py 010090C022978001 program_id
python3 dm/games/game.py 010090C022978003 program_id
python3 dm/games/game.py 010090C022978003 modules
python3 dm/games/game.py 010090C022978003 mem_used
```

For the registered base-game profiles, the KH2 module list is `main subsdk1 sdk` and its measured rewritten-module reservation is `0x4200000`. These values are not universal for other game builds. See the [KH1 profile](../dm/games/010090C022978000/direct-profiles/010090C022978001/game.tsv), [KH2 profile](../dm/games/010090C022978000/direct-profiles/010090C022978003/game.tsv) and [profile reader](../dm/games/game.py).

## Prerequisites and missing automation

- Use a Mac with Xcode and an iPhoneOS SDK providing Metal 4, plus XcodeGen. The iOS target is 26.0. Physical-device, BC-texture and iPad limitations still apply; a simulator build is not the validated target.
- Upstream's tool installation uses Homebrew packages `xcodegen`, `zstd`, `spirv-cross`, `glslang` and `dotnet-sdk`, and Python packages `lz4`, `capstone` and `fonttools` (plus `backports.zstd` on Python before 3.14). See [upstream setup](https://github.com/seedds/nxnative#pack-an-ipa); its multi-game compatibility claims do not apply to this fork.
- Supply your own lawfully obtained native Switch collection package and keys. Keep all proprietary inputs and outputs outside Git.
- Separately extract the chosen program, rewrite **its** modules, stage its RomFS and prepare its iOS Vulkan shader library. KH1 also needs the collection's shared `SettingMenu.hed` and `SettingMenu.pkg` data in the staged layout. The checked-in direct profiles do not automate this staging.
- The [inherited NSP pipeline](../scripts/build_ipa_from_nsp.py) targets the collection profile; it does **not** select Program 1/3 or reproduce the tested direct apps automatically. Generic pipeline success is not a KH gameplay test.
- KH2's opt-in [color-processing shader experiment](../dm/games/010090C022978000/build_color_experiment.py) is a separate, input-hash-gated step, not an automatic feature of the general [Vulkan shader compiler](../dm/gfx/tools/vk_shaders.py). Do not assume a fresh generic shader build includes the same optimization as a previously tested app.

## Existing direct KH2 packaging entry point

The [packaging script](../dm/ios/tools/build_ipa.sh) supports explicit staged paths. The following is a **template for already prepared inputs**, not an extraction, shader-generation or end-to-end build command. Replace every `/path/to/...` value with a new output location or your own prepared input outside the repository. Run it from the repository root only when you intend to generate a project:

```sh
# Normal operation: no bundled diagnostic override or inherited verbose gates.
unset DM_ENV_FILE DM_KH24_DIAG DM_KH_INPUT_TRACE DM_SAVE_TRACE DM_FS
DM_GAMES_DIR="$PWD/dm/games/010090C022978000/direct-profiles" \
DM_GAMES_FIRST=1 \
GAME=010090C022978003 \
W="/path/to/kh2-work" \
PATCHED="/path/to/kh2-program3-patched" \
ROMFS="/path/to/kh2-staged-romfs" \
MSL_IOS="/path/to/kh2-ios-shaders" \
DM_ICON="/path/to/your-own-game-icon.png" \
DM_DISPLAY_NAME="KH2 Direct" \
DM_XCODE_PROJECT_DIR="/path/to/kh2-project" \
DM_XCODE_DERIVED_DATA="/path/to/kh2-derived-data" \
GFXAPI=vulkan AOC='' \
bash dm/ios/tools/build_ipa.sh --prepare-xcode
```

Required inputs include:

- `PATCHED`: each profile module's `.patched.bin` and rewriter tables. For the save repair, freshly rewrite **all three modules and metadata** and build the matching host from the same source; do not reuse an older rewritten main. The [KH2 packaging guard](../dm/ios/tools/check_kh2_direct_patch.py) checks the direct-main build ID, but does not replace the runtime's complete gate/module checks. See [exact build pairing](kh-save-persistence.md#exact-build-and-hostmodule-pairing). Do not bypass either guard.
- `ROMFS`: the staged game files, including `kh2_fifth.pkg`.
- `MSL_IOS`: the **parent** directory containing `vk/vk_shaders.metallib`, not the `vk` directory itself.
- Control metadata: a valid `control.nacp` beside the RomFS or at `$W/data/v0/control.nacp`, used for language discovery and app metadata. A missing/truncated file can silently remove language choices; setting a display name is not a replacement for valid language metadata.
- `DM_ICON`: an existing, locally supplied game icon; direct KH2 packaging refuses a missing icon. Do not add game artwork to Git.

`--prepare-xcode` generates a project and resources metadata; it does **not** compile an app, sign, install or prove playability. Subsequent Xcode builds use your own local signing configuration. Keep build products isolated as well: the [project template](../dm/ios/project.yml) uses `DM_XCODE_OUTPUT_ROOT`, so a custom Xcode invocation should set that to the same isolated output root as `-derivedDataPath`. Never include actual signing identities, provisioning profiles or credentials in shared instructions or commits.

Without `--prepare-xcode`, the packaging script builds and packs an unsigned IPA containing your staged game assets. That output is **not a source-only artifact and must not be publicly uploaded**. The same boundary applies to signed apps and IPAs.

## Settings, saves and verification scope

In the updated source, KH2's **MISS effect render fix** is on by default. The launcher retains an existing saved on/off choice; `DM_VK_COALESCE_PASSES=0` disables it and `1` enables it. `Documents/env.txt` overrides launcher preferences. Fully close and reopen the app after changing the file: the native coalescer gate is cached. This is KH2-specific, not a new KH1 default.

The temporary `DM_PRESERVE_FULL_HUD` option has been removed. Original fit/crop behavior is restored: `DM_ASPECT_FILL=0` fits the original 16:9 image with bars, and `1` fills by cropping, potentially cutting off HUD. Neither adds horizontal world view or relocates the HUD. See [settings definitions](../dm/games/settings.tsv) and the [shared aspect policy](../dm/host/aspect_fill.h).

These source changes do not alter existing installations. A new commit, successful CPU check or generated project is not evidence of a rebuilt, installed or gameplay-tested app. KH1's independently mapped cache/PNG repair is implemented and has independent source/CPU review; actual-menu save/retry/cold-load acceptance and physical-iOS validation remain separate, outstanding gates. No new KH1 app is certified here.

The original KH2 cached-write path can return success while progress remains only in guest RAM. The reviewed source repair invokes the original serializer synchronously for each complete record, preserves the original inverse transform and qualifies publication on actual success. Its recoverable PNG-error boundary has independent source/CPU review and bounded Mac menu failure/retry/cold-load evidence. **New physical-iOS acceptance is still outstanding.** This is per-record publication, not whole-menu atomicity or a sudden-power-loss guarantee. The [save-persistence guide](kh-save-persistence.md) documents exact profile/module pairing, portable CPU commands and the remaining delivery gates.

Back up saves before updating or reinstalling. Retain separate backups of `Documents/save` and `Documents/save.work` when present; use copies for fault tests, not live progress. Save hardening and fresh-process byte checks do not certify power-loss durability or every in-game slot and suspend/resume path. Reinstalling with a different identity or sideloading tool may change the data container.

## Normal operation and optional diagnostics

Normal packaging uses **no `DM_ENV_FILE` override** and leaves `DM_KH24_DIAG`, `DM_KH_INPUT_TRACE`, `DM_SAVE_TRACE` and verbose filesystem tracing unset/off. Also inspect saved launcher choices and any existing app `Documents/env.txt`: rebuilding without a bundled override does not erase a user's saved diagnostic overrides. Ordinary startup, operational and error logging remains in `Documents/log.txt`, with the previous launch retained as `log.prev.txt`.

Program 3 has three separate, **default-OFF** settings, applied at **Play** before native diagnostic gates are cached. Relaunch to change them; they are not live runtime switches:

| Launcher setting | Switch | Purpose |
| --- | --- | --- |
| **Save traces** | `DM_SAVE_TRACE` | Save operations and transaction timing |
| **Record controller inputs** | `DM_KH_INPUT_TRACE` | Changed published controller states for offline analysis/replay |
| **Detailed render logging** | `DM_KH24_DIAG` | High-volume Vulkan-to-Metal diagnostics |

For these diagnostic switches, explicit process values take priority over `Documents/env.txt`, then bundled `dm/env.txt`, then saved launcher choices or new-install defaults. Overridden rows are locked without rewriting their saved choice. Use canonical `0`/`1` values. A legacy process/file `DM_KH24_DIAG=1` defaults save tracing on unless `DM_SAVE_TRACE` is explicitly set (including `0`); selecting render logging in the launcher alone does not enable the other two settings. Input tracing is observation, not a save repair or a guarantee of deterministic replay. See the [game guide](../dm/games/010090C022978000/README.md#optional-diagnostics) for the isolated Mac wrapper.

The [continuous-diagnostics template](../dm/games/010090C022978000/kh2-24h-diagnostic.env) is for an explicitly requested diagnostic session only, not normal builds. It enables KH2 continuous save/render tracing and input tracing. Any enabled KH2 trace starts the diagnostic rotation path at Play: two 4 GiB segments, retaining about 8 GiB plus possible polling overshoot. Copy both logs before rotation/relaunch replaces them. This can affect performance; on-device rollover is not certified by the CPU rotation tests. Redact private paths and identifiers before sharing log excerpts; do not upload raw logs or game/save data by default.

## Verification gates before delivery

The intended delivery source must include the reviewed save-path, failed-transaction, complete-record serialization and PNG-recovery changes, not merely this documentation or an older baseline. Re-run relevant integrated-source CPU suites, including both profiles, exclusion/fail-closed gates, failure-injection/fresh-process persistence, launcher/default-isolation, fit/crop and diagnostic-off checks. The [save guide](kh-save-persistence.md#portable-cpu-tests) explains asset-free defaults and optional private-input probes. A KH1 port additionally needs its own profile-specific implementation validation and independent review; shared filesystem tests alone do not certify it.

Before calling a new app ready, require a matching host/module build, review and the relevant actual-menu normal-save, failure/retry, overwrite/relaunch and lifecycle tests on the target platform. Verify that normal generated resources contain no bundled diagnostic override and no trace-enabling app override or saved choice is active. Record which source revision was actually built and tested. CPU tests, local compilation and remote CI are distinct evidence; none alone is physical-device gameplay or power-loss certification.

This documentation change does not perform an app build, installation or gameplay test. Sharing source also remains subject to a separate privacy and asset audit; documentation is not clearance to publish the repository or its history.

## What may be shared

Share source changes, build-tool fixes and sanitized reproduction steps. Do **not** share NSP/XCI packages, keys, decrypted modules, RomFS, game-derived shader sources/libraries, game artwork, personal saves, game-containing apps/IPAs, signing material or unredacted private logs. The [MIT license](../LICENSE) covers the runtime source, not the game content. Third-party dependencies retain their [own licenses](../dm/third_party/README.md).
