# Direct KH iOS icon packaging

Direct-program extractions may lack an adjacent icon even when the collection has one. Supply your own lawfully obtained artwork explicitly; keep it outside Git:

```sh
DM_ICON="/path/to/your-own-icon.png" \
  bash dm/ios/tools/build_ipa.sh --prepare-xcode
```

Combine this with the selected direct program's staged-input and isolated-output settings from [the build guide](KINGDOM_HEARTS.md). Do not reuse another program's generated project without checking its source links, embedded module identities and resource paths.

The packaging guard requires an icon for KH2 Program 3 (`010090C022978003`) and rejects any explicitly supplied nonexistent `DM_ICON`. Other profiles retain optional-icon behavior. The game-free regression is:

```sh
python3 dm/ios/tests/test_app_icon.py
```

## Verification before delivery

- Confirm the selected image was staged at `Gen/Assets.xcassets/AppIcon.appiconset/icon.png` and the generated configuration selects `DM_APPICON = AppIcon`.
- Require an actual asset-catalog compilation step and compiled `AppIcon*.png` plus `Assets.car` in the app.
- Read `CFBundleIcons.CFBundlePrimaryIcon.CFBundleIconName` and the corresponding iPad metadata from the built app; require `AppIcon`.
- Decode compiled PNGs before comparing pixels with the selected image or its documented resized reference. Inspect the resulting icon; metadata alone is not pixel verification.
- Verify the exact current source/module pairing, shader-library provenance and staged resource hashes separately. Rebuilding an icon neither updates a stale shader library nor proves a persistence repair.
- Run strict signature verification after staging all resources. Preserve the intended entitlements and verify the actual installed bundle/version after installation.
- Back up committed and work save trees before replacement and verify their hashes afterward. Installation and icon registration are not gameplay or save/reload acceptance.

Keep artwork, signed game-containing apps/IPAs, signing material, private paths and device evidence outside the source repository. A source change is not an announcement that an app was built or installed.
