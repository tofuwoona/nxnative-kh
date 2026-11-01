# KH1/KH2 adversarial save fixes — handoff

## Scope and integration

- Branch: `fix/kh-save-adversarial-108`.
- Worktree: `/Users/tofu/.hermes/cache/scratch/kh-save-fix-108`.
- Exact base: `70eca8a8c1dfefe972ae91a5851fbe5aaa6a3205`.
- Verified common Git directory: `/Users/tofu/Documents/Workspace/nxnative-kh/.git`.
- Reviewed inputs were copied from `/Users/tofu/Documents/Workspace/kh2-save-review-108`; its report and findings were read in full. No original saves or phone were accessed. Tests use disposable synthetic trees only.
- Only production file changed: `dm/host/hle_fs.c`. Existing `t_fs.c` has one internal injection-call adaptation for transaction-scoped poison; its assertions are unchanged. New regression runner/harness/stubs and this evidence accompany the fix.
- The source worktree's uncommitted `dm/games/settings.tsv` coalescer launcher row was copied byte-for-byte into this isolated worktree and is deliberately **not part of the save commit**. The renderer/coalescer, lifecycle, iOS frontend and packaging sources are unchanged. Cherry-pick the save commit onto the parent's current source; retain the parent's existing launcher toggle.
- The baseline's disabled `kh2_save_migrate` implementation is byte-identical. No migration helper was added, ported, enabled or used by the new fixtures. No bundled environment or suspend/auto-commit policy changed. The existing KH2 normal suite still internally enables migration for its pre-existing legacy subtest; this is not a shipping configuration or an endorsement of migration.

## Repairs

| Finding | Repair and exercised behavior |
|---|---|
| SAVE-01 | Failed CreateFile open, truncate and name metadata stages poison the backing transaction before cleanup. Unexpected resource/I/O failure opening an existing replacement for writing also poisons it. Native error/refused commit preserves the prior generation even if the caller ignores the original failure and uses a null handle. EEXIST and ordinary missing-path probes remain benign. A bare null handle has no attributable mount: it fails but does not arbitrarily poison another save. |
| SAVE-02 | A save-mount identity bit survives read-only transaction-setup fallback. KH1/KH2's existing canonical mapping no longer depends on `commit[0]`; distinct flat aliases remain untouched and are not selected/migrated. |
| SAVE-03 | Opaque 64-bit file handles contain a non-reused open cookie plus the low-word host FD. Successful rollback marks only that backing work generation's handles stale; read/write/resize/get-size/flush reject stale handles. Descriptors stay owned until explicit matching close. An old cookie cannot write or close a fresh handle after numeric FD reuse. Failed rollback does not invalidate the still-linked work generation. Healthy commits retain existing open-handle behavior. |
| SAVE-04 | Clone/swap failure captures the original error for native notification and keeps staged bytes retryable. Both single and mount-list Commit, and mount fallback, release **both** mount and cleanup-guarded path locks before notifying. A test callback trylocks both and actually re-enters the FS. |
| SAVE-05 | WriteFile and SetFileSize use the existing path transaction lock for the entire mutation and failure/poison decision; Commit cannot snapshot the prefix of a subsequently failed in-flight write. The gated reproducer releases its writer independently, so a correct serialized Commit does not deadlock the test. No new close-before-commit restriction was imposed. |
| SAVE-06 | Recursive clean/delete poison the affected transaction on aggregate failure. Shared traversal preserves the first error, checks directory-read/close and path-length failures, and never reports successful partial cleanup. Directory-create I/O/name failures receive the same protection, excluding EEXIST. |

Poison is scoped to the backing transaction and shared by aliases. Mounting/committing an independent healthy save cannot clear or consume the failed save's poison. Diagnostic write counts/timing anchors remain global; they are not the transaction identity or persistence oracle.

## Actual RED → GREEN results

Full per-command output, exact compiler commands, working directories and exit status are in `kh2-save-fix-evidence/`. The commit stores the complete raw evidence in `kh2-save-fix-evidence.tar.gz` to avoid hundreds of generated-log files in the patch; `kh2-save-fix-evidence/summary.json` is also directly tracked. Extract beside this report with:

```sh
tar -xzf docs/agents/kh2-save-fix-evidence.tar.gz -C docs/agents
```

The isolated implementation worktree already has the expanded raw directories.

| Run | Commands | Outcome |
|---|---:|---|
| `red/` — original review fixtures before any production edits | 54 | 40 exit 0; 14 exit 1. All seven original red cases per profile reproduced. 32 adversarial invocations / 94 assertions, 22 assertions failed. |
| `red-extended/` — final expanded harness compiled against Git's exact original `hle_fs.c` | 62 | 22 exit 0; 40 exit 1. 56 adversarial invocations / 324 assertions, 108 assertions failed. Extra red outcomes include the cleanup-guard callback-lock gap; they do not all represent independent data-loss findings. |
| `green/` — final fixed source, both profiles | 78 | **78 exit 0**, no failed command. All **28 adversarial cases per profile**, **56 invocations / 324 assertions**, pass. |
| `sanitized/` — KH2 ASan + UBSan | 29 | Build and all 28 cases exit 0; no sanitizer finding. Leak detection was explicitly disabled (`ASAN_OPTIONS=detect_leaks=0`); UBSan was configured to halt on error. |

Unchanged normal-suite assertions on fixed source:

| Suite | KH2 `010090C022978003` | KH1 `010090C022978001` |
|---|---:|---:|
| `t_fs` | 74 checks, 0 failed | 64 checks, 0 failed |
| `t_fs_case` | 51 checks, 0 failed | 51 checks, 0 failed |
| `t_fs_commit_list` | 36 checks, 0 failed | 36 checks, 0 failed |
| `test_kh_save_trace.py` | pass | pass |

The case/list tests link the copied test-only zero-input stub for the baseline's optional HID symbol; no production input implementation changed. Independent logger rotation tests also pass, including the real LOG primitive, FD-leak checks and sparse 4-GiB boundary. Each profile additionally passes 100 serial save transactions during concurrent stderr rotation.

Every expanded adversarial invocation execs a new reader process and checks the expected committed canonical bytes through the normalized guest path; recursive failures additionally read the entry that partial cleanup would remove. The runner separately rewrites a deterministic **7,073,032-byte synthetic container**, then execs an independent reader and compares entire manifests, preserving a distinct flat alias. No gameplay save or original backup was read for this task.

Representative final behavior:

```text
create-failure: create=0x2a2 open=0x202 write=0x2a2 commit=0x2a2 alerts=1 cold=OLDold
readonly-path: slash=OLDold; backslash=OLDold
held-handle: reused-handle write=0x2a2 flush=0x2a2 commit=0 alerts=1 cold=OLDold
clone-failure: commit=0x2a2 alerts=1 errno=28 committed=OLDold; retry passes
swap-failure: commit=0x2a2 alerts=1 errno=5 committed=OLDold; retry passes
concurrent-commit: commit=0x2a2 writer=0x2a2 snapshot=OLDold poison=0
recursive-failure: clean=0x2a2 commit=0x2a2; old-remove survives fresh exec
```

Additional edge cases cover create-open/name faults, writable-open resource failure, benign EEXIST/missing probes, null mutations, stale read/resize/flush/get-size, numeric FD reuse, full rewrites after refusal, failed/successful rollback retry, healthy handles across successful Commit, both recursive APIs, directory-create/name faults, transaction isolation and alias rollback, list-Commit notification, short/EINTR writes, sampled process death, overloads, no-migration legacy-only behavior and concurrent logger interference. Test invocations are bounded by alarms/timeouts.

## Reproduce

From this worktree:

```sh
python3 dm/host/tests/run_save_review.py --baseline  # intentionally exits 1
python3 dm/host/tests/run_save_review.py             # exits 0
# The runner forces its own direct-profile directory and scratch fixture root.

TMPDIR=/Users/tofu/.hermes/cache/scratch/kh-save-fix-fixtures \
  dm/host/tests/build-save-kh2/t_fs_save_adversarial create-failure
# Other case names/commands appear in green/test-results.json.

make -C dm/host -j4 GAME=010090C022978003 \
  DM_GAMES_DIR="$PWD/dm/games/010090C022978000/direct-profiles" \
  DM_GAMES_FIRST=1
```

`DM_SAVE_TEST_OUT` selects a different evidence directory. Default output is `kh2-save-fix-evidence/green` or `red-extended`. Baseline mode obtains only the pinned old production source with `git show`; it does not reverse/edit the working production file. The original RED run used the original review tests; the expanded RED run adds edge cases against that same old source.

## Exact Mac host artifact

- Final build command above completed with **exit 0**, after final source changes.
- Own binary: `/Users/tofu/.hermes/cache/scratch/kh-save-fix-108/dm/host/dmhost` (Mach-O arm64).
- SHA-256: `cdc30bc549a86da31647ea97add67752f883b561ef27f78f038c0c630555f38b`.
- Size: `2450616` bytes.
- Own generated profile/stamp: `010090C022978003`, Program 3 `kh2_fifth.pkg`, `DM_GAME_MEM_USED=0x4200000`, main BUILD_ID contract `e1bced80ffd14436980f7490b1d3c3e7`.
- `mac-build-final.log` contains the full link command and 45 warnings in untouched host/renderer files, none in `hle_fs.c`. No GPU/game launch or shared output/derived-data directory was used. This is a rebuilt Mac host, **not an iOS package or an installed/gameplay-validated artifact**.

## Remaining limitations / next owner

- Parent should independently review/cherry-pick the commit, build/package iOS in its own output, then perform the authorized device test. This child did not install, deploy, launch on a phone, access original saves or share the HUD agent's binary/GPU.
- SAVE-03/SAVE-05 remain conditional caller scenarios; the fixtures do not establish that current KH2 gameplay reuses a refused-commit handle or overlaps write/Commit. Recursive APIs are shared-host coverage, not proven active KH2 imports.
- The historical UI-completed / zero-poststartup-write event is still unexplained. Host tests do not establish correct game serialization, slot identity, UI completion timing or successful gameplay slot reload.
- FlushFile remains a validated page-cache no-op; no fsync/F_FULLFSYNC/parent-directory durability or suspend auto-commit was added. Fresh-process persistence and sampled process-death outcomes do **not** prove power-loss/kernel-crash durability or actual iOS suspend/force-close behavior.
- Faults are narrow syscall/scheduling injections, not actual volume exhaustion or exhaustive arbitrary-instruction crashes. No claim is made that every possible filesystem failure path was audited or fixed.
- Concurrent close/read of the same handle remains invalid SDK usage; a read already started before rollback may complete from its prior snapshot. Mutations and newly started stale-handle operations are checked/serialized as described.
- Stale descriptors are released on matching CloseFile, not proactively during rollback. A caller that never closes its stale handles can retain FDs, as it could already retain ordinary open handles. Open-cookie exhaustion fails closed rather than recycling a cookie.
