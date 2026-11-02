# Kingdom Hearts save persistence

This guide describes the reviewed **KH1 Program 1 and KH2 Program 3** source repairs, their exact build boundaries and the evidence needed before delivery. Both implementations have independent source/CPU-mechanism review. This does not announce an installed-app update: **physical-iOS acceptance remains outstanding**, and KH1's actual-menu save/retry/cold-load acceptance is not established by CPU review.

See also [build and source boundaries](KINGDOM_HEARTS.md), the [game profile guide](../dm/games/010090C022978000/README.md) and the [root README](../README.md).

## Why a successful menu action could lose progress

The original cached-write path copies a complete record into guest RAM, marks it dirty and returns the supplied length without serializing it. The background save worker checks dirty data on an approximately **601-second worker-baseline cadence**. This is not a promise to save exactly 601 seconds after menu confirmation: the baseline, cache mode and other serializer callers matter. Closing the process while progress exists only in that cache can leave the prior on-disk generation.

A host `fflush`, `FlushFile` or filesystem Commit cannot serialize data still only in the guest cache. Shortening the worker timer alone also does not address cache races, inverse-transform restoration or ignored publication errors. Separate canonical-path and failed-transaction problems are handled by the shared filesystem hardening; they are not a substitute for draining the guest cache.

The same cadence and related error-handling defects were independently identified in KH1's original build. KH1 has different addresses, globals and command state machines, so widening a KH2 title guard or copying its offsets is not a valid port.

## Reviewed KH2 mechanism

The [game patch table](../dm/games/010090C022978000/patches.py) and [host save boundary](../dm/host/hle_kh2_save.c) work together:

- After the original higher-level cached write finishes its final returned-length store, synchronously invoke the **original serializer** for that complete record. Preserve the original direct-filesystem mode and background-worker cadence.
- Use a common process-lifetime recursive mutex around cache initialization, mutation, deletion/compaction, reading/listing and serializer entry. A separate nested-flush guard prevents recursive transformation. Teardown marks the object closing and drains entrants, but does not hold the mutex while the original worker stops/joins.
- Preserve the positive serialized length through PNG failure so the original inverse transform restores the shared cache before recording an error. Retain dirty state on serialization or publication failure; do not equate a nonnegative length with a successful Commit.
- Qualify publication on PNG success and the actual original Commit result, including close/write errors. A narrow rejection adapter feeds logical PNG errors into the existing filesystem poison/rollback engine even when no host syscall has already poisoned it. It is not a new transaction engine or save writer.
- Keep the original PNG encoder, container and normal destroy/close tail. The error boundary uses a live **Darwin** `jmp_buf` in heap-owned context, captured original resources and same-thread ownership checks. On the reviewed write-error path, the callback runs after SDK `fwrite` has returned and unlocked; it returns to the live host wrapper, restores virtual guest thread-register state, cleans up captured resources once and returns failure to the original inverse/rejection flow. It does not reuse a guest/SDK jump buffer or jump over an active filesystem/HLE call.
- Hand resource ownership back before the original normal cleanup tail. Missing, stale, foreign-thread, mismatched or nested callback contexts fail closed rather than jumping through an invalid context.

The historical filename/API names containing `kh2` are not an assurance of KH1 support. Check the selected profile's implementation and tests, not its name alone.

## Per-record publication, not whole-menu atomicity

**The boundary is one complete record, not the whole save menu.** A menu operation can serialize multiple records and publish intermediate valid generations. If a later record fails, an earlier successful Commit can remain durable. Rejection rolls back the failed filesystem working generation; it does not undo every earlier Commit in that menu operation.

An explicit failure followed by a successful same-process menu retry and an independent cold load is the relevant bounded recovery check. Neither a zero-write startup Commit nor a live play-time display proves that the intended record was saved. Do not infer whole-menu atomicity, protection against sudden power loss, all-slot coverage or recovery of progress that was never serialized.

## Exact build and host/module pairing

These are the registered base-package profile build keys, not generic support for other revisions:

| Direct target | Program ID | `main` build key | Save-repair status |
| --- | --- | --- | --- |
| KH2, Program 3 | `010090C022978003` | `e1bced80ffd14436980f7490b1d3c3e7` | Reviewed source/CPU mechanism; bounded Mac recovery evidence |
| KH1, Program 1 | `010090C022978001` | `badf2faf580b712464365c4d529d92c9` | Reviewed source/CPU mechanism; actual-menu acceptance outstanding |

Both direct profiles declare `sdk=bc204aae7319bab274894f1cc3f5da92` and `subsdk1=99e21f98a397434b534c1459fc38a2b8`. See the [KH1](../dm/games/010090C022978000/direct-profiles/010090C022978001/game.tsv) and [KH2](../dm/games/010090C022978000/direct-profiles/010090C022978003/game.tsv) profiles for the complete source configuration.

KH2 activation requires the exact title/main and a unique matching `main`, `sdk` and `subsdk1` set, **nine wrappers, eight private SVC gates** and the positive-length inverse repair. Registration validates mandatory sites, emitted gate/trampoline bytes, branches and continuations before readiness. These are required identity/metadata checks, not a digest of every loaded byte.

Use a matching newly built host and a **fresh complete rewrite of all profile modules and their metadata** from the same source. Do not reuse an older rewritten main or mix module tables across revisions. Missing/duplicate modules, wrong SDK/subsdk identities, old or incomplete gate sets and malformed sites are rejected. Unsupported originals do not gain the repair; private repair metadata for an unsupported title/build is rejected. Do not bypass a guard to make mismatched inputs start. Packaging's direct-main build-ID check alone is not the full runtime gate validation.

## What has and has not been verified

| Evidence | What it supports | Limits |
| --- | --- | --- |
| Independent KH2 source review and CPU fixtures | Policy, exclusion/lifecycle, exact registry/gate checks, original inverse/Commit error handling, PNG cleanup/retry, thread-register restoration and real gate/big-stack nonlocal return | Guest bodies and selected APIs use explicit seams; not a full game or complete encoder execution |
| Original-instruction boundary probes with separately supplied inputs | Pinned original writer/error/locked-stdio slices and expected negative controls | Not the full original PNG encoder/destructor or arbitrary binaries |
| Matching rewritten KH2 modules and Mac host, isolated real save-menu trial | Actual PNG write failure becomes explicit storage failure without the former abort; same-process menu retry and independent cold load agree with the saved row; preserved originals remain unchanged | Bounded Mac trial, not all routes/slots, final integrated-source regression or physical iOS acceptance |
| KH1 independent original-build mapping and implementation review | Exact profile-specific cache/serializer/PNG gates, original-instruction probes, alternate-handler failure publication, and plain/sanitized CPU mechanisms | Not a real KH1 menu save/retry/cold-load result or installed-app delivery |

Independent CPU review included plain and ASan/UBSan executions and adversarial cleanup/context controls. Assembly is not sanitizer-instrumented; macOS leak detection was disabled for those runs. Do not claim exhaustive register-bit coverage, TSan coverage, exhaustive leak checking or device validation from them.

Existing installed applications retain their prior code. A source push, successful compile or unsigned/signed artifact does not update a phone. Physical iOS overwrite/relaunch, failure/retry, lifecycle and relevant normal-save regressions remain delivery gates. Back up saves and check the intended saved row after reopening before trusting a new build.

## Portable CPU tests

Run from the repository root on an Apple-silicon macOS development machine with Python 3, Clang, Make and the profile-reader dependencies. These compile **CPU test harnesses**, not a game host or app, and use synthetic fixtures rather than personal saves. Default-mode runs do not need game assets, private evidence directories or historical Git objects.

Use new, disposable absolute output directories **outside the checkout**; replace `/path/to/...` below. Filesystem and path runners generate profile headers in those explicit owned output directories, not in the checkout. Run the modes serially as shown.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 dm/host/tests/run_kh2_sync.py \
  --out /path/to/new-cpu-sync

DM_SAVE_TEST_OUT=/path/to/new-save-review \
  PYTHONDONTWRITEBYTECODE=1 python3 dm/host/tests/run_save_review.py
DM_SAVE_TEST_OUT=/path/to/new-save-review-sanitized \
  PYTHONDONTWRITEBYTECODE=1 python3 dm/host/tests/run_save_review.py --sanitize

DM_SAVE_PATH_OUT=/path/to/new-save-paths \
  PYTHONDONTWRITEBYTECODE=1 python3 dm/host/tests/run_save_path_resolution.py
DM_SAVE_PATH_OUT=/path/to/new-save-paths-sanitized \
  PYTHONDONTWRITEBYTECODE=1 python3 dm/host/tests/run_save_path_resolution.py --sanitize
```

`run_kh2_sync.py` covers the active KH1 and KH2 CPU mechanisms in plain/sanitized modes, including KH1's gate and alternate-handler fixtures, and emits `results.json`. This is not actual-menu or physical-iOS acceptance. The filesystem suites cover both direct profiles; `run_save_review.py` emits `test-results.json`, and the path suite emits `results.json`. Set the output variables explicitly: their built-in fallback locations are inside the checkout, not the recommended source-only workflow. Check process exit status and every recorded result; a manifest's existence alone is not a pass.

The filesystem runners' optional `--baseline` modes retrieve private historical source revisions with Git. Those objects may not exist in a source-only checkout and are **not default/CI prerequisites**. Do not fetch private evidence history merely to run the ordinary tests.

### Optional original-instruction probes

These probes are **private, local analysis**, not asset-free default CI. Supply your own lawful, exactly matching original inputs; the probes reject unsupported identities. `--main` and `--sdk` refer to the expected original flat images, not arbitrary NSOs or rewritten output. `--elf` requires the expected original ELF representation. Keep inputs and generated slices/results outside Git.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 dm/host/tests/probe_kh2_png_boundary.py \
  --main /path/to/original-main.bin --sdk /path/to/original-sdk.bin \
  --out /path/to/new-original-png-probe
PYTHONDONTWRITEBYTECODE=1 python3 dm/host/tests/probe_kh2_repaired_boundary.py \
  --elf /path/to/original-main.elf --out /path/to/new-repaired-boundary-probe
```

The [original failure-boundary probe](../dm/host/tests/probe_kh2_failure_boundary.py) also accepts explicit `--elf`, optional `--patched` and `--out` inputs. Its negative controls characterize original defects; expected failures are not repaired-game acceptance. No proprietary module, save or game-derived probe output is required in the repository.

## Save handling and source-only boundaries

Back up `Documents/save` and `Documents/save.work` separately when present, before updating or reinstalling. Use isolated copies for fault tests; never run destructive experiments against live progress. Changing app identity or sideloading tools can change the data container. Keep the preserved originals separate from working copies.

Share only source, synthetic fixtures and sanitized reproduction steps. Do not commit saves, raw logs, private paths/identifiers, keys, original or rewritten game modules, extracted game data, game-derived shaders, signing material or game-containing apps/IPAs. These docs neither authorize redistribution nor certify that the repository's entire history has been sanitized. The repository remains private; source-only curation is not a public-release clearance.
