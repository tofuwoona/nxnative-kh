# Reminder: update Kingdom Hearts patches against nxnative upstream

- [ ] Review the latest changes in the [nxnative GitHub repository](https://github.com/seedds/nxnative) and reconcile the local Kingdom Hearts patches with upstream before the next update or rebuild. The local checkout was based on `c1b7eff61fb3ca2d182320f12a9c6c30dc3c520e` when this reminder was written; this is not a claim about the current upstream HEAD.
- [ ] Preserve and review all uncommitted work and game saves before pulling, rebasing, or replacing builds. Compare upstream changes against the KH game profile, Vulkan/Metal clear handling, iOS face-button mapping, Mac controller support, and packaging changes; retain unrelated local changes rather than overwriting them.
- [ ] Review the experimental KH2 constant-table shader optimization separately: it was built into the KH2 iOS shader library but was not integrated into the general shader-generation pipeline. Confirm compatibility with any upstream shader-pipeline changes and preserve gamma, alpha, and color-vision behavior.
- [ ] Rebuild affected projects after changes and run relevant tests; verify signing, saved data, rendering, and gameplay on the target device before treating an updated IPA as ready. Save and obtain permission before restarting or replacing an active game.

## Known issue: save overwrite may not persist

The user reports that an in-game save overwrite says it succeeded, but after restarting only the old progress appears. The affected KH title and exact save slot are not yet confirmed. Preserve existing committed and working save data; this report has not been reproduced or traced, and no cause or fix has been established.

## Known issue: KH2 camera-transition ripple

The user described a screen-wide wave when a scripted fight camera returns control; it is not confirmed to be depth of field. The mission `miss` PAX is a plausible lead but is not visually identified. No safe force-trigger, effect-specific trace, cause or fix has been established. Do not treat shader bypasses or disabled effects as correctness-preserving fixes.

## Known issue: Seven wonders of twilight Town Wonders
Fire effects

Bag you have to hop on, arena might have several reaction scripts running causing fps spikes down to 30fps.




For prior evidence, build paths, release status, and diagnostic limitations, see [the KH iPhone handoff](kh-native-iphone-handoff.md).
