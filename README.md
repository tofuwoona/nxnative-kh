# nxnative-kh — Kingdom Hearts–focused fork

**This is a Kingdom Hearts–specific fork of [seedds/nxnative](https://github.com/seedds/nxnative), not a general-purpose continuation of upstream.** Development revolves around **Kingdom Hearts 1 and Kingdom Hearts 2**: direct-program execution, save correctness and persistence, rendering and performance, controller/touch controls, and Apple-platform packaging.

This experimental fork adapts the native-execution runtime for separate KH1 and KH2 apps on Apple platforms: rewritten Switch code runs on Apple silicon, with graphics translated to Metal.

**Only KH1 and KH2 have been tested in this fork. Other games are untested here.** Inherited game profiles, tools and upstream compatibility reports are not a compatibility claim for this fork. This is work in progress, not a complete or generally supported port of the collection.

## Tested scope

| Target | What has been tested | What that does not establish |
| --- | --- | --- |
| KH1 — direct Program 1 | A separate app on a physical iPhone, including reported save/load and face-button swapping; adaptive edge-to-edge gameplay, title and in-engine cutscene checks on an Apple-silicon Mac | Complete gameplay coverage or physical-iOS gameplay acceptance of the adaptive build |
| KH2 — direct Program 3 | A separate app on a physical iPhone; direct-game testing on an Apple-silicon Mac | Every scene, save slot, controller, lifecycle transition or device |
| Collection launcher — Program 0 | Launcher startup | Working game selection: switching to another program is still unsupported |

Source changes, CPU tests, an app build and an installed app are different milestones. **A commit on a branch does not update an installed app.** The KH2 synchronous-save and PNG-error recovery changes have independent source/CPU review and bounded Mac gameplay evidence, not new iOS acceptance. KH1's separately mapped save and adaptive-aspect ports are implemented; actual-menu save/retry/cold-load and adaptive physical-iOS gameplay acceptance remain separate gates. See [save persistence and verification limits](docs/kh-save-persistence.md).

## Current features

- Separate KH1/KH2 program profiles, rather than relying on collection-menu switching.
- Vulkan-to-Metal rendering fixes and KH2 performance work. Render-pass coalescing has greatly reduced the KH2 **MISS-effect stutter**, but has **not eliminated it**: several overlapping effects can still struggle, and other slow scenes remain. In the updated source it is **on by default for KH2** and can be disabled with **MISS effect render fix** or `DM_VK_COALESCE_PASSES=0`. Saved user choices are retained; KH1 does not inherit this default.
- Touch controls and physical-controller support, with optional face-button swapping. KH2's touch layout places **X on the left and Y at the top**; this position change does not remap their functions.
- A pre-game settings screen with saved preferences and per-app `Documents/env.txt` overrides. Available settings depend on the selected program and source revision.
- Save-path and transaction hardening, including failure-injection and fresh-process persistence checks. These checks are limited evidence, **not power-loss certification** or a guarantee for every gameplay slot, suspend/resume sequence or interrupted write. Back up saves before changing builds.

## Known issues and work in progress

- **Collection switching:** `ExecuteProgram` is not implemented for the collection's game-selection path. Use the direct programs; the rest of the collection is not validated.
- **KH1 adaptive-aspect coverage:** the persistent 16:9 side bars are removed in the tested Mac gameplay route while the tutorial prompt and controls remain complete. This does not establish every HUD, menu, movie or physical-device state.
- **KH2 effects:** overlapping MISS effects and other effect-heavy scenes can still stutter. The coalescer is not a universal rendering or performance fix.
- **KH2 Twilight Town slowdown:** user-reported slowdown when facing certain directions. The affected room, exact directions and root cause remain unconfirmed; this is not assumed to be the MISS-effect issue.
- **Adaptive edge-to-edge:** exact KH1 Program 1 and KH2 Program 3 builds expose **Native display aspect**, selecting coherent render dimensions from the startup viewport for landscape ratios from 16:9 to 20:9. KH2 1.0.17 passed startup, save-load, sustained movement/camera and complete-HUD checks on an iPhone 15 Pro without the prior stale-frame regression; other KH2 ratios were tested in real Mac windows. KH1 passed an eight-minute Mac gameplay run with active movement and complete tutorial UI, but adaptive physical-iOS gameplay acceptance remains pending. At wider ratios, some menu/background UI elements can be slightly misaligned, awkwardly framed or expose plain side margins; these were visual-only in tested scenes, with gameplay and menu contents usable. The removed **Fill screen (crop)** setting is not part of the adaptive mode and must not be used to describe it.
- **KH1 current-install status:** 1.0.14 is installed on the iPhone 15 Pro and the existing save/settings were preserved byte-for-byte across the update. It has not yet received physical adaptive-gameplay acceptance; the Mac route above is the current visual/runtime evidence.
- **KH2 current-install status:** 1.0.17 is installed and physically gameplay-tested on the iPhone 15 Pro; the original save/settings were preserved. The 1.0.16 rollback build remains the earlier verified fallback. See the selected revision's [settings definitions](dm/games/settings.tsv).
- **Save persistence on iOS remains unaccepted:** the original guest cache can acknowledge a write before serializing it, leaving progress vulnerable to closing the app. The reviewed KH2 source repair synchronously uses the original serializer per complete record and handles publication/PNG errors; a bounded Mac failure/retry/cold-load trial supports that mechanism, not physical-iOS acceptance. Keep independent backups and verify the intended saved row after reopening. Whole-menu atomicity, sudden-power-loss durability, all-slot coverage and lifecycle acceptance are not established. See the [save guide](docs/kh-save-persistence.md) for exact build pairing and test limits.
- **iPad:** a reported BC3 texture-format rejection remains unresolved; iPad compatibility is unverified.
- **Simulator:** the tested simulator SDK lacked required Metal 4 declarations. Simulator gameplay is unverified and is not a substitute for physical-device testing.

## Normal logging, not continuous diagnostics

Normal builds do **not** bundle a `DM_ENV_FILE` override. KH2 Program 3's **Save traces**, **Record controller inputs** and **Detailed render logging** settings are separate and default OFF, applied at **Play**. Leave `DM_SAVE_TRACE`, `DM_KH_INPUT_TRACE`, `DM_KH24_DIAG` and verbose filesystem tracing unset/off in the environment and app override files, and check any saved launcher choices. Explicit overrides can keep diagnostics enabled. Ordinary operational/error logging still writes `Documents/log.txt`, retaining the previous launch as `log.prev.txt`; this is not a claim of zero logging.

The separate continuous-diagnostics template is **explicit opt-in only**. It enables verbose tracing and two rotating **4 GiB** segments (about **8 GiB** retained, with possible rotation overshoot), can affect performance, and is not the normal build configuration. See the [build guidance](docs/KINGDOM_HEARTS.md) before using or sharing diagnostics.

## Requirements and building

The current iOS path uses **iOS 26+, Metal 4 and BC-compressed textures**. Upstream's hardware baseline is A17 Pro–class iPhones or later and M1–class iPads or later, but this is **not** a guarantee for every such device, OS or SDK; the iPad issue above remains open. Development also requires a Mac with the appropriate Xcode SDK and build tools. Older Apple hardware is not a validated fallback.

See [Kingdom Hearts build and source boundaries](docs/KINGDOM_HEARTS.md) for program IDs, source-verified profile queries, prerequisites and the packaging entry point. **Direct KH builds still require separately staged program modules, shared data and shader libraries.** The inherited one-command collection builder does not automatically produce the tested direct apps. No clean-checkout, end-to-end direct build is claimed here.

## Source-only and legal boundaries

This fork is for source code and build metadata. **Bring your own lawfully obtained game dumps and keys.** No game package, key, decrypted executable, extracted RomFS, game-derived shader library, save or copyrighted game artwork is supplied by these instructions. Keep those inputs and all generated game-containing apps/IPAs outside the repository; do not upload them in issues, pull requests or releases. Do not publish signing identities, provisioning profiles or credentials.

The runtime's license does not grant rights to Nintendo, Disney, Square Enix or other third-party game content, nor permission to redistribute it. This project is not affiliated with or endorsed by those companies. Follow applicable law and the terms governing your own assets and development tools.

## Credits and license

This fork builds on **[nxnative by seedds](https://github.com/seedds/nxnative)**. Its broader game documentation describes upstream's work, not this fork's tested compatibility. The upstream MIT copyright and license are preserved in [LICENSE](LICENSE).

The upstream acknowledgements remain applicable:

- **[d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile)** (MIT) developed this native-execution approach for Diablo II: Resurrected. nxnative started from its generic NSO rewriter, Horizon host, NVN-on-Metal layer and iOS app shell.
- **Ryujinx** (MIT): shader translation through `Ryujinx.Graphics.Shader`, `Ryujinx.Common` and `Spv.Generator`; also a reference for kernel and service behavior. See the [vendored README](dm/third_party/ryujinx/README.md).
- **[Atmosphère](https://github.com/Atmosphere-NX/Atmosphere)**: mesosphère is a reference for Horizon synchronization semantics.
- **yuzu**: Maxwell instruction encodings and kernel-behavior cross-checks.
- **LibHac**: NSP reading and update layering; **hactool** supported early extractions.
- **[SPIRV-Cross](https://github.com/KhronosGroup/SPIRV-Cross)** and **[glslang](https://github.com/KhronosGroup/glslang)**: shader translation and compilation.
- **deko3d** (zlib): texture-layout sizing algorithm used in `dm/gfx/nvn/nvn_tex.c`.
- **libvpx**, **stb_vorbis**, **Vulkan headers** and **NVIDIA FLIP**: vendored dependencies with their own licenses.
- **Capstone**, **lz4**, **fontTools** and **XcodeGen**: build tooling.

Source is MIT unless otherwise noted. Third-party code retains its own license; see [dm/third_party](dm/third_party/README.md). Game content is not covered by the source license.
