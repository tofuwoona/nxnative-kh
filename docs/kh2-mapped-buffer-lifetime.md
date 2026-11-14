# Mapped Metal-buffer lifetime and KH2 RAM growth

## Mechanism and repair

Metal declares `-[MTLBuffer contents]` with `NS_RETURNS_INNER_POINTER`.
ARC therefore inserts a retain/autorelease of the receiver when the Vulkan
`vkMapMemory` handler obtains its CPU pointer. Without a map-local pool, that
extra retain can survive `vkFreeMemory` until an enclosing pool drains.
Vulkan wrapper counts can balance while the actual Metal buffers remain alive.

The repair brackets only map materialization, the existing failure check,
`contents`, and return in `@autoreleasepool`. `VkDeviceMemory_T.buf` remains a
strong owner after the pool pops, so valid callers retain usable mapped storage
until the applicable Vulkan lifetime ends. Existing descriptor, texture-alias
and movie-cache owners are not cleared. This is a generic ownership correction,
not a title/size-specific allocation policy or a new synchronization barrier.
It does not make concurrent free or use-after-free valid, force driver residency
reclamation, or change the existing offset/range policy.

## Measured scope

A bounded physical iPhone 17 differential used the same diagnostic binary,
byte-identical disposable saves and the same 1748×804 rendering dimensions,
with only the experimental map-pool gate changed. DVT process-footprint
checkpoints after repeated Bamboo Grove load → return-to-title cycles were:

- OFF: approximately **884 → 1155 → 1389 MiB**, two cycles.
- ON: approximately **701 → 758 → 783 → 784 → 797 MiB**, four cycles.

The intervention substantially reduced this route's growth. The sequential runs
have unequal timing and cycle counts, sample delivery is irregular, and the
first OFF return has only one nearby sample. These measurements do not establish
exact memory savings, all-area stability, a plateau under indefinite use, or a
new movie-replay result. Earlier same-run labeled Metal events also observed
prompt destruction of all 44 selected early 4-MiB mapped buffers with the pool
requested ON; that capture ended before return-to-title and is not full-cycle
proof. Keep process footprint, Metal object lifetime, driver allocation size
and device-wide graphics counters separate.

The permanent unconditional-pool source is independently reviewed; signed iOS
1.0.26 build and full renderer aggregate checks passed. That rebuilt release was
then installed on the personal iPhone 17 and completed four isolated-save
Bamboo Grove load → title cycles without the experimental map-pool variable:
**700.71 → 759.16 → 783.86 → 797.72 → 798.72 MiB**, then **797.75 MiB** at the
additional idle checkpoint. These are medians of DVT footprint receipts within
[-8,+4] seconds of host checkpoint markers, not exact device-time measurements.
The original twelve save/work/preferences/env files remained path/hash-identical.
The test process was intentionally stopped, not observed to crash.

The installed compact app uses separately staged `Documents/romfs`; all 30 game
data files passed exact path/size/full SHA-256 readback before installation, and
the runtime log confirmed that resource root. The immutable full app remains a
separate packaging variant, not a separately physically tested installation.
Repeated full-app delivery failed; the streaming installer independently
reported a single-file >4-GiB constraint. Compact installation succeeded, but this
does not establish the cause of every earlier CoreDevice interruption.

The retained actual-handler ownership tests pass with generated KH1 Program 1
and KH2 Program 3 profiles at O0/O2, with and without ASan+UBSan, including
explicit opt-in real-Metal checks. The KH1 iPhoneOS ARM64 O2 renderer also
compiles. These are mechanism/build checks, not KH1 gameplay or measured
footprint acceptance.

Private device captures and delivery/preservation receipts are not distributed
in this repository. The device figures above validate the repair on the bounded
KH2 route, not a general RAM-creep cure, indefinite plateau, other-area soak,
movie replay, or KH1 gameplay acceptance. Later unscored attract-movie activity
is not movie-replay acceptance.

## KH1 applicability

The exact KH1 Program 1 (`010090C022978001`, main build-ID prefix
`badf2faf580b712464365c4d529d92c9`) directly imports `vkMapMemory`. An audit of
the authentic original modules and retained rewritten main verified the map
jump relocation, PLT thunk and seven static call sites. The selected SDK modules
do not define a competing map implementation; the host resolves that import to
the same registered big-stack map handler repaired here. This establishes a
concrete guest-to-host path, not merely a shared-source or profile-name match.

The pool is generic and keeps `VkDeviceMemory`'s strong buffer owner intact.
It does not enable the existing KH2-only movie staging cache or pass-coalescer
policy for KH1. Both profiles pass the retained ownership regressions, but a
KH1 RAM reduction or gameplay improvement has **not** been measured and no new
KH1 app was deployed for this verification. Static call-site counts are not
observed runtime call counts; the conclusion is limited to the identified build.

## Retained regression tests

On macOS with the Apple SDK:

```sh
# CPU fake Metal objects with real, freed heap backing; no Metal device.
make -C dm/gfx/tests GAME=010090C022978003 check_vk_map_pool_cpu
# Explicit bounded real-Metal microtests, not game/device/driver-residency proof.
make -C dm/gfx/tests GAME=010090C022978003 check_vk_map_pool_metal
# Existing graphics aggregate includes the CPU regression.
DM_GAMES_DIR="$PWD/dm/games/010090C022978000/direct-profiles" DM_GAMES_FIRST=1 \
  make -C dm/gfx/tests GAME=010090C022978003 run
```

The runner regenerates production KH1/KH2 headers in disposable output, compiles
the actual handlers at O0/O2 with normal and ASan+UBSan configurations, and
rejects sanitizer diagnostic text independently of exit code. `DM_MAP_TEST_OUT`
optionally retains logs and binaries under an explicit output directory. The
CPU fixture covers map/bind order, offsets, remap identity, heap-pointer use
after pool pop, failure/retry, descriptor copy/overwrite/free/reset,
map-before-linear-image and texel-descriptor ownership, and existing cache reuse.
Its linear-image constructor metadata and fake alias objects are explicit seams.
The real-Metal fixture covers mapping and ownership but does not submit GPU
commands. The existing full descriptor fixture separately submits/completes a
Metal command. Reduced map-only fixture links dead-strip unused host symbols;
they are not complete game-host links or complete iOS stack-chain proofs.

The same retained assertions compile and fail at the expected prompt-release
checks against the unmodified source. Test-only alternate source selection is
explicit via `test_map_pool.py --source-root <checkout>`; no private game files,
saves, historical Git objects or machine-specific paths are default inputs.
