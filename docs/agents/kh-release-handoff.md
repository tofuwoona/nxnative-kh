# Kingdom Hearts direct apps: release and upstream handoff

## Scope and state

Local nxnative base: `c1b7eff61fb3ca2d182320f12a9c6c30dc3c520e` on `main`, with a mixed, **uncommitted** worktree. Public `main` was `a6171b80f94e7873135ac3eeba4bd64f32f49295` when checked; compatibility with it has not been tested. Do not commit the whole worktree or reset it: it contains game experiments, independently pre-existing changes and untracked save data. See the game [profile and status](../../dm/games/010090C022978000/README.md).

The target is the later **KH2 X/Y-fix release IPA**: Program 3, signed for iPhone, optimized `80a74ee192e6490b` shader, original `a552cfafcf3c0899` alpha testing, face-swap support and increased-memory entitlement. Its SHA-256 is `894a40d7d3a003433a9c404e5aa840732734ca1592eb855ebc2a5a58bb58579d`. The archive has 55 unique entries and valid CRC. The app extracted from that exact IPA passed `codesign --verify --deep --strict` and has the increased-memory entitlement. It has **not** been installed or tested on-device. The current local Xcode app executable differs from the packaged executable; do not use the current app directory as evidence for the IPA. The phone has the preceding clean KH2 release, whose SHA-256 is `88029dde1191c0653b1460dbfd6e185ebef7688318ffa35b4af8d2c855ffcf81`. Do not confuse package validation with gameplay validation.

KH1 was separately built as a release with tracing/logging disabled and installed. The user confirmed a save/load and initial face-swap behavior. KH1's HUD bars remain unexplained. Existing KH1/KH2 applications, all phone saves and the current local saves must be preserved; request a save and app closure before any future replace or restart. The isolated Mac save was derived from a copy and must never overwrite phone data. A later user report of save overwrite returning old progress remains unconfirmed and must not be described as fixed.

## What to commit and what to keep apart

1. **Game profiles and docs:** `dm/games/010090C022978000/` carries a provisional launcher profile, nested direct Program 1/3 profiles, the opt-in shader experiment and status/readme. Launcher selection still hangs; the profiles do not provide a complete direct-app builder. Their generated empty NVIDIA-oriented tables are placeholders, not a captured Vulkan shader collection.
2. **Generic Vulkan work:** `dm/gfx/vk/hle_vk.m` contains attachment clear/load/store, multisample resolve, blend constants and stencil reference changes. It also contains extensive KH-focused diagnostics, trace overrides and shader probes. Separate semantic fixes from diagnostics and add targeted render tests before staging. Do not ship the raw-texture or no-discard variants: they altered required output.
3. **Input:** `dm/ios/Sources/DmGamepad.m`, `face_swap.h`, `dm/ios/tests/t_face_swap.c` and `dm/host/tests/Makefile` implement the opt-in iOS face swap and its host tests. Latest X/Y fix pre-corrects physical position mapping while leaving touch X/Y labels at their original positions. All face-bit combinations passed the C tests; physical and virtual device behavior remains unverified. `dm/games/settings.tsv` also contains the user-facing toggle and unrelated diagnostic settings: stage only intended settings after review.
4. **Mac fallback:** `dm/host/front_mac.m`, `dm/host/Makefile`, `mac_sdl_input.h`, `t_mac_sdl_input.c`, host test Makefile and `docs/development.md` add opt-in SDL2 fallback. Test with both SDL and Apple GameController. The user confirmed operation before a later 10% radial deadzone adjustment, not after it.
5. **Earlier work:** `dm/host/hle_fs.c` has `MountRom` shared-program support and `dm/host/hle_movie.c` has event changes. They were already dirty when this wrap-up started. Keep their exact contents; split and review separately rather than treating them as clean KH-only patches. No claim of KH1 movie correctness or generalized filesystem semantics has been established.
6. **Do not commit:** `savkh1/`, game assets, SPIR-V and generated Metal shaders, captures/traces, extracted PAX data, local investigation projects, build products, icons copied from the game, signing material or IPA archives. The older `kh-native-iphone-handoff.md` is a detailed local investigation log with machine-local paths and is not a polished public document; sanitize before including it. No credentials belong in a patch.

## Shader provenance and rebuild

The release shader was generated outside the regular pipeline. The opt-in `dm/games/010090C022978000/build_color_experiment.py` requires the user's own captured SPIR-V, invokes the normal shader compiler, and transforms only the exact validated generated MSL source. It refuses changed source. Example:

```sh
python3 dm/games/010090C022978000/build_color_experiment.py \
  /path/to/program3/vk_capture /path/to/output/mac --ios /path/to/output/ios
```

The reconstructed wrapper was run against the original 46 captured shaders. Its generated Mac and iOS tables matched the earlier experiment byte-for-byte, and the rebuilt iOS metallib SHA-256 `e074b29c94b7d281446053958c2fe2a99683adcfdbe72afb8d6cedfbc4df726e` matched the metallib read from the X/Y IPA. This establishes the library's provenance, not complete reproducibility of the signed IPA or iPhone rendering equivalence. The capture and generated binary are not included in Git.

Earlier synthetic Mac GPU testing compared 440 gamma/color-vision combinations and 1,802,240 RGBA components (zero differences), with deliberate negative controls. Alpha-test shader `a552cfafcf3c0899` was investigated separately: removing discard sped a synthetic test but produced incorrect coverage/depth, while an equivalent single-discard rewrite gave no consistent speedup. The release keeps the original shader. Further tests must include real-device scenes, alpha, depth, blending and stencil; no universal shader equivalence is established.

## Direct build and packaging provenance

Program 1 required Program 0's `SettingMenu.hed` and `SettingMenu.pkg`; Program 3 used its own modules and staged data. Both direct Xcode projects and their proprietary assets live outside the repository. Build/package automation was local, not a reproducible clean-checkout workflow: the final X/Y IPA was made by cloning the earlier IPA and replacing changed files from a rebuilt, signed app. The final archive's unique names and CRC were checked. Before public release, create and validate a documented clean extraction, asset staging, build, archive/signing and installation process; do not publish the private IPA or claim it is reproducible from these profiles alone.

A prior device Release build used `xcodebuild` on the generated Program 3 project, the direct KH2 scheme, `-configuration Release -sdk iphoneos -destination 'generic/platform=iOS'` and `OTHER_CFLAGS=$(inherited) -mcpu=apple-a17`; it verified the signed app and embedded shader. These steps depend on local signing and staged resources. Do not include signing identifiers or credentials in public instructions.

## Verification in this wrap-up

- Mac host rebuilt for direct Program 3 with SDL2; the host test suite, `ios_face_swap` and `sdl_input` passed. The build emitted Metal API type warnings; a successful build is not device gameplay verification.
- The generated Program 3 Xcode project built successfully for generic iPhoneOS Release with signing disabled in a separate derived-data directory. It is a new unsigned build, not the signed IPA.
- The shader wrapper's three synthetic guard tests passed, and its real-input rebuild matched the release library as described above. Both direct profiles were resolved through `game.py`; `git diff --check` passed for tracked changes. The earlier filesystem/movie diffs were checked unchanged.

## Next verification

- Review upstream changes without resetting this checkout; use the [update checklist](kh-upstream-update-reminder.md).
- Split diagnostics from generic fixes and add rendering, multi-program filesystem and input regression coverage. Check title resources, save compatibility and both Mac input backends.
- With user permission and after a save, install the later X/Y IPA and verify physical and virtual controls and gameplay. Verify archive and app signatures on the artifact actually installed.
- Reproduce save overwrite safely with isolated copies, logs and explicit slot identification. Investigate iPad BC3 format rejection and the Simulator Metal 4 SDK issue separately.
- Capture the camera-transition ripple and fire slowdown in matched scenes. The `miss` PAX is a plausible lead, not a visually confirmed match; its mission-owned runtime context, safe thread and valid arguments are unknown. No force-trigger was implemented.
