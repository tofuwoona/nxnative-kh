# KH release-default regressions

Run from the repository root on macOS:

```sh
python3 dm/ios/tests/test_release_defaults.py -v
python3 dm/ios/tests/test_xcode_workflow.py -v
python3 dm/gfx/vk/tests/test_coalesce_defaults.py -v
python3 dm/ios/tests/test_launcher_render_preferences.py -v
python3 dm/tools/tests/test_launcher_settings.py -v
```

## Contract

- KH2 Program 3's **MISS render fix** (`DM_VK_COALESCE_PASSES`) defaults to
  `1` in both generated launcher settings and the native renderer. Explicit
  `0` disables it; explicit `1` enables it. Existing saved launcher choices
  remain choices, not forced migrations. This setting does **not** enable
  diagnostic logging. Other profiles do not gain this renderer default.
- With diagnostic variables absent or explicitly `0`, continuous
  Vulkan/input tracing and detailed save-operation tracing are off. The iOS
  4 GiB diagnostic rotation thread starts only for KH2 Program 3 with
  `DM_KH24_DIAG=1`. That boot path also enables `DM_FS` and `DM_SAVE_TRACE`.
  Input tracing has its own `DM_KH_INPUT_TRACE=1` opt-in; the supplied
  diagnostic template explicitly sets both KH2 diagnostic switches.
- Regular NSP preparation does not select an environment template.
  `--env-file` (NSP script), a deliberately configured `DM_ENV_FILE` in that
  script, or an explicit shell `DM_ENV_FILE` assignment is an opt-in.
  `build_ipa.sh` stages `Gen/dm/env.txt` only when that input is nonempty.
  Re-preparing the same project without it deletes the previously generated
  environment file along with the rest of `Gen`.
- **Ordinary logging remains enabled.** Boot redirects stderr to
  `Documents/log.txt`, keeping the previous launch as `Documents/log.prev.txt`.
  Default-off diagnostics does not mean a silent app, nor does it impose the
  diagnostic 4 GiB rollover limit on the ordinary log.
- Existing `Documents/env.txt` overrides survive preparation and app startup.
  Process variables take precedence over Documents switches, which take
  precedence over bundled `dm/env.txt`. A previously explicit on-device
  diagnostic opt-in can therefore remain active with a regular bundle.
  These tests never access or remove real user overrides or device data.
  Use the documented `0`/`1` values; the independent legacy gates do not all
  parse arbitrary strings identically.

## What is exercised

`test_release_defaults.py` runs the **entire production
`build_ipa.sh --prepare-xcode` script** using synthetic module, font, shader
and icon fixtures in temporary directories. Host/module generation, font
creation and xcodegen have stand-ins; profile selection, KH2 build-ID checks,
launcher generation, environment staging/cleanup, icon conversion and
resource-path generation use the real preparation code. Clean release,
explicit diagnostic, release-after-diagnostic and empty-input preparations
must all succeed. Build/sign tools are guarded against accidental invocation.
No app, IPA or game host is built.

The same test compiles and executes the actual native Vulkan, save-trace and
input gates under ASan/UBSan for KH2, KH1 and an unrelated profile, in fresh
processes. It also executes the production iOS boot log/env/diagnostic block
with Foundation, supplying temporary Documents/bundle roots. Thread creation
is recorded rather than started; UIKit and game startup are not run. This
checks absent/off/on behavior, file precedence, preserved overrides, ordinary
log output and launch-time log retention, independently of the MISS setting.

`test_xcode_workflow.py` exercises the real NSP CLI with extraction/build
steps mocked, checking both ordinary preparation's absent `DM_ENV_FILE` and
explicit `--env-file` forwarding. The renderer/launcher tests check the cached
native gate, generated settings and actual launcher model, including saved
`0`/`1` and environment-file precedence.

For the shared save repair and real save-operation trace output, run the
CPU-only suites with outputs directed to a disposable directory:

```sh
DM_SAVE_PATH_OUT="$TMPDIR/kh-save-path" python3 dm/host/tests/run_save_path_resolution.py --sanitize
DM_SAVE_TEST_OUT="$TMPDIR/kh-save-review" python3 dm/host/tests/run_save_review.py --sanitize
```

These compile filesystem test harnesses, not a game host, app or IPA. The
save-trace check executes actual create/write/delete/commit operations with
`DM_SAVE_TRACE` absent, `0` and `1`; the first two must emit no `[save-trace]`
records. The review suite also exercises the real rotation primitive,
including its sparse 4 GiB boundary. Source/fixture checks are not physical
device, game performance, or installed-app validation.
