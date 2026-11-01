# KH2 direct iOS icon packaging

The Program 3 split extraction uses `program3_v0/RomFS` but has no adjacent
`icon.jpg`. The old packaging fallback silently generated an empty catalog and
left `DM_APPICON` unset, so version 1.0.9 had no primary-icon metadata or compiled
icons. No runtime, renderer, save, input, HUD or settings change is needed.

For this local 1.0.10 rebuild, pass this existing artwork explicitly during
`dm/ios/tools/build_ipa.sh --prepare-xcode` (keep the PNG outside Git):

```sh
export DM_ICON='/Users/tofu/nxnative-local-work/Kingdom Hearts HD 1.5 plus 2.5 ReMIX/010090C022978000_build/program3_ios_project/Gen/Assets.xcassets/AppIcon.appiconset/icon.png'
```

It is the existing 1024×1024 collection logo with the gold **II FINAL MIX**
badge, not new artwork. Use an isolated Xcode project and derived-data path;
keep all 1.0.9 profile/resource/environment inputs and signing entitlements.

The packaging guard now refuses a missing icon for `010090C022978003`, or any
explicit `DM_ICON` path that does not exist. Other titles retain optional-icon
behavior. Run `/usr/bin/python3 dm/ios/tests/test_app_icon.py`; it exercises the
actual shell staging block with a synthetic image, requiring no game assets.

Before installation, assert all of:

- `Gen/Assets.xcassets/AppIcon.appiconset/icon.png` exists and decoded pixels
  match the selected existing image; `Gen/dm.xcconfig` sets `DM_APPICON = AppIcon`.
- Xcode's build log actually runs the asset-catalog compiler.
- The built `Info.plist` has `CFBundleIcons.CFBundlePrimaryIcon.CFBundleIconName`
  equal to `AppIcon` (and the equivalent iPad primary icon), and compiled
  `AppIcon*.png` plus `Assets.car` exist.
- Decode a compiled icon, compare it with a resized reference, and inspect it.
- Strict signature verification, Program 3 package guard, exact reviewed FS
  hash and shader/resource hashes, entitlements and launcher/environment
  equality with 1.0.9 all pass.
- Back up both save trees, install over the same bundle ID, read back installed
  version/primary-icon metadata and rehash every save file without launching.

Local build commands, external icon path, resource checks, previews, backup
and device readback evidence belong in `kh2-ios-110-evidence` alongside the
source checkout, not in Git. Never commit game art, game assets or signing keys.
