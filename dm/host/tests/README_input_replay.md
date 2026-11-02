# Input capture/extraction and CPU replay checks

These tests verify the input mechanism only. **They do not prove a KH2 menu,
slot-selection route, game serialization, saving, or reload persistence.** No
filesystem writer/fixture is attached to replayed buttons. The runner never
builds or starts a game host/app and never uses a device or GPU.

## Extract a private capture (no input injection)

```sh
python3 scripts/extract_input_trace.py /private/raw.log.gz /private/NEW-route.log
python3 scripts/extract_input_trace.py /private/raw.log /private/NEW-window.log \
  --start-ns 1000000000 --end-ns 2000000000
```

Substitute actual **recorded** `t_ns` values, not elapsed seconds. Bounds are
inclusive and must match existing event timestamps exactly; tied timestamps are
all included. Gzip is detected by magic rather than filename. Ordinary log lines
are discarded, but any line containing `[input-trace]` must match the full
recorder grammar and numeric ranges. All records, even outside a selected
window, must be valid and nondecreasing. Empty captures/windows, invalid bounds,
malformed axes/sources/buttons, overflow, trailing data, damaged gzip, oversized
lines and selected spans over the scheduler's two-hour limit are rejected.

Validation finishes before creating the output. Output uses exclusive creation
and mode 0600; existing files, directories, and dangling symlinks are never
replaced. Failure does not publish a partial validated capture. JSON stdout
contains selected count, total source-event count, first/last/duration `t_ns`,
per-source counts, compression, raw source size/SHA-256, and output SHA-256.
The script does not validate a game/scene association or identify a save-confirm
button automatically. A window does not invent an initial controller snapshot
or append a post-save waiting period. Keep captures/metadata outside Git.

## Repeatable CPU checks

On macOS with clang and Python 3:

```sh
python3 dm/host/tests/run_input_replay.py \
  --out /absolute/NEW-input-replay-evidence --sanitize --repeats 5 \
  --check-baseline 074f1addc7dfb33fbba5ad5b16ab7105eea2ec82
```

Output must be a **new directory outside the checkout**. Profiles are generated
inside it, not into shared `dm/host/gen`. Each command has separate stdout/stderr
and an exit-status record in `results.json`, with hashes of the production
parser, scheduler, HID, FS, and extractor. The baseline option uses disposable
copies from the specified Git revision; it never replaces working source.

Optional private captures are **extracted and parsed read-only, never replayed**:

```sh
python3 dm/host/tests/run_input_replay.py \
  --out /absolute/NEW-private-validation --sanitize \
  --capture /private/input-only.log --capture /private/another.log.gz
```

Checks execute:

- The production recorder through real `dm_input_set`/`dm_pad_set_player`:
  changed-state capture, identical-poll suppression, source -1 and pad 0/7,
  full axes, button releases and a final intentionally held button.
- The actual plain/gzip extraction CLI, then the production C parser.
- The unmodified scheduling algorithm in `input_replay_mac.c` through its
  public start API: relative monotonic delays, order, repeated runs in the same
  process, two fresh-process runs, overlap refusal, absolute-save/matching-path/
  explicit-allow guards, and final input release.
- Real production setters, stored button/axis state **and production HID state
  assembly** at dispatch. No setter or scheduler is replaced by a test stub.
  Existing `t_hid.c` supplies only unrelated host/GPU link stubs; its full
  original suite is run separately. Only logging is observed to assert states.
- Malformed-axis/trailing-data aborts (no later press), timestamp-order and
  two-hour-limit aborts, cleanup, and sibling-profile replay refusal.
- Eight black-box CLI test methods, including malformed captures after valid
  prefixes, invalid records outside windows, all sources, numeric extrema,
  new-only output, gzip corruption, mixed ordinary logs, hashes and permissions.

The CPU harness dispatches **only its own seven-event synthetic controller
capture**. It performs **no save reads/writes**. The absolute disposable directory
passed as `DM_SAVE` satisfies the existing replay guard, not a save test. Timing
checks establish non-collapsed relative scheduling with a 1 ms measurement
allowance, not real-time precision or a game's response to every press.

## Demonstrated safety bugs and RED/GREEN

Against the pinned publication above, the numeric parser regression reports
`parser invalid records: 7 failed`: scanf accepted negative unsigned fields and
wrapped overflowing timestamps, button masks, source indices and axes into
apparently valid values. Bounded token accumulation now rejects them before
narrowing; failed parses leave the output event unchanged.

The scheduler regression reports `scheduler reject: 2 failed` on that publication:
a malformed release (axes or trailing data) was silently skipped and a subsequent
A press still executed. The minimal scheduler change aborts on malformed trace
records, preserves ordinary-log skipping, and follows existing release cleanup.
Order/time-limit checks and guards are otherwise unchanged. The scheduler is
still streaming: a bad later record may be discovered after a valid prefix was
already dispatched. **Use the fully validated extraction output**, not raw logs,
for a real route. A successful start/completion message is not gameplay proof.
The baseline runner requires these exact failing assertions and exit 1; build
failures or unrelated crashes are not accepted as expected RED.

## Real repeated saves: existing game workflow only

This remains an integration task, not a CPU harness claim:

1. Preserve the original committed/work save and logs privately. Prepare a new
   isolated **copied committed save** for each trial, with a manifest; never
   point replay at a primary save or the live phone. Use unchanged `hle_fs.c`.
2. Identify the actual captured save-menu sequence and its exact start/end
   transitions. Do not replay an entire gameplay log just because it parses.
   Select a window beginning from a known released state; include the actual
   final release. Other input sources must also be neutral.
3. Open the same game/build, loaded save, scene and menu position on the Mac.
   Preserve the existing menu navigation/slot-selection/save-confirm sequence;
   do not translate a button into a new host-side FS operation. Reset to the
   same starting snapshot/scene for each repeat. Loading speed and game random
   state can make iPhone-to-Mac wall-clock replay diverge.
4. Before starting that isolated Mac host, set all existing guards:

   ```sh
   export DM_SAVE=/absolute/copied-trial-save
   export DM_KH_REPLAY_CONFIRM_SAVE="$DM_SAVE"
   export DM_KH_REPLAY_ALLOW=1
   export DM_CTL=/absolute/private-trial-control.txt
   ```

   `DM_CTL` is an append-only command file polled by the existing host, not a
   FIFO. Once the starting scene is verified, append one complete line
   `replay /absolute/validated-route.log` using existing control tooling. Do not
   mix manual/controller/DM_KEYS input into that trial. No live-phone replay.
5. Verify the real menu/slot route visually and correlate existing save/FS
   operation records with the confirmation event; wait for the game's normal
   completion indication before closing. A replay completion only means the
   input file ended, not that saving completed. Reopen in a fresh game process
   and verify the intended slot's actual progress marker, not only byte hashes.
   Retain each trial's capture hash, start-state manifest, trace, route outcome,
   save result and reopened marker. Report divergences separately.

The reported slots 10/11/12 progress loss (expected roughly 46 minutes versus
roughly 28 shown) remains unresolved until that real save/close/reopen workflow
passes. Parser and CPU input checks cannot resolve it.
