# Clean KH1 save-hardening backport

## Source boundary

- Branch: `fix/kh1-save-hardening`; worktree: `/Users/tofu/.hermes/cache/scratch/kh1-save-hardening`.
- Exact parent: `e9ca69cd8fc153a5ea6848992ec11073a2cf2abe` (`fix/kh2-save-backslash-path`). Common Git directory: `/Users/tofu/Documents/Workspace/nxnative-kh/.git`.
- The integrated `c05f82bb20249917f561084e862e9208a9e90f15` source already has shared KH1/KH2 hardening. **The older clean branch needed this backport.** Neither original branch was moved. This source-only branch does not update an installed KH1 application.
- Reviewed source: `566afc34000535faa9dbb9d5e6730d9dd2e5f218` / production fixes `e191b99d1806682888557e415ab82c99f9185fb0` and `566afc3`, integrated as `a5c4b4b` / `6e52077`. The integration file `/Users/tofu/Documents/Workspace/kh2-ios-110/dm/host/hle_fs.c` was hash-checked, not copied wholesale.
- Reviewed `hle_fs.c` SHA-256: `32e36ff48977f8e96ef2e65a2174d6960e5a53626fcb521ead5db8e77c3d06f9`.
- Backport `hle_fs.c` SHA-256: `31b360fbc530e51febf9632b102800a17502f07fde13bbce9c19df2691099b46`.

**Only production file changed: `dm/host/hle_fs.c`.** The manual behavior backport adds no save tracing, input timing, migration helper, renderer/HUD/coalescer change, lifecycle change, suspend auto-commit or durability barrier. Inherited ordinary error/commit timing logs remain. `kh2_save_migrate`, its environment switch, `save_trace*`, `[save-timing]`, `dm_input_last_event_ns` and `g_txn_input_ns` remain absent from production. No app, IPA, dmhost/hostgame, GPU launch, device operation, original save access, push or publication was performed.

## RED before production edits

The imported tests were adapted and run on unchanged e9ca69c first, under both direct profiles. All failures below are real failed preservation/notification assertions, not compile failures or timeouts.

| KH1 test group | Cases / checks | Observed RED |
|---|---:|---|
| Original six findings (clone/swap separate) | 7 / 18 | All seven fail; 11 checks fail |
| Original R1 Create/Open lookup | 2 / 8 | Both fail; 6 checks fail |
| Expanded original regression matrix | 28 / 162 | 20 cases / 54 checks fail |
| Expanded R1 seams/probes/isolation | 97 / 774 | 83 cases / 415 checks fail |

KH2 control reproduced the same counts. Across both profiles, RED is **278 commands, 224 expected failed commands; 268 case invocations, 1,924 checks, 972 failed checks**. All ten profile/build commands passed; every failed command emitted its semantic RESULT line. The original KH1 observations included: ignored Create failure publishing a missing save; read-only backslash lookup selecting `STALEflat`; post-rollback handle accepting unpersisted bytes; missing clone/swap notifications; concurrent Commit publishing `NEWold`; partial recursive cleanup publication. Original R1 published a missing canonical file (Create), or six NUL bytes (Open), with successful Commit and no notification.

## Technical equivalence to reviewed source

`python3 dm/host/tests/check_kh_save_equivalence.py` passes. It reads the pinned reviewed Git blob, validates its SHA-256, removes only explicitly enumerated tracing/input/migration pieces, then compares **every remaining C token** with the clean backport, retaining quoted strings and ignoring only comments/whitespace. It is a read-only guard, not a source generator. This covers surrounding generic FS behavior too, rather than merely matching named functions or green tests.

Line references below are `dm/host/hle_fs.c` in this branch versus the reviewed file.

| Obligation | Clean branch | Reviewed source / retained semantics |
|---|---|---|
| Transaction identity / poison | 38–70, 94–107, 109–145 | 38–75, 111–120, 156–192: per-backing owner, first errno, alias sharing, independent mounts cannot consume/reset poison |
| Stable read-only save normalization | 113, 315–324 | 162, 344–353: `save=txn` persists when staging falls back read-only; existing KH1 **and** KH2 compile gate retained; canonical path only, no flat-file selection/migration |
| R1 early lookup / original errno | 200–237, 361–363 | 245–281, 392–394: errno cleared before each readdir, EOF distinct from failure, xattr error preserved across close, close errors propagated; exact guest-mount attribution before a physical path exists |
| Create / writable Open / directory mutation | 655–679, 766–787 | 695–720, 812–835: resource/I/O failures poison; create size/name cleanup preserves original errno; explicit write/append/read-write lookup predicate; read-only/missing/existing/type/invalid probes retain reviewed exemptions |
| Rollback generation / opaque handles | 49–58, 585–593, 669–676, 681–763 | 49–58, 617–624, 709–715, 722–809: cookie+FD ABI; successful rollback stales only affected work handles without closing; failed rollback leaves linked generation usable; explicit matching close owns FD; cookie prevents old-token reuse |
| Complete mutation / snapshot serialization | 721–755, 564–648 | 762–801, 595–686: full write/resize plus failure decision serialized with Commit by path lock; healthy handles remain valid across healthy publication |
| Snapshot/swap failure / callback locks | 597–598, 610–648, 143–144 | 633–634, 650–686, 189–190: original errno captured before cleanup, staged bytes retryable; mount/single/list callbacks after both locks release; cleanup guard nulled after explicit unlock |
| Recursive aggregation / rename endpoints | 788–819, 830–845 | 836–867, 878–892: first traversal/read/close/path-length failure retained and transaction refused; source-only failure poisons source; destination lookup/probe/syscall failures attribute both reached endpoints |

Removed behavior is intentionally bounded: optional diagnostic traces and input anchors, plus the forbidden opt-in KH2 legacy migration helper/call. In particular, generic error predicates, rename attribution, read-only behavior, handle locking and callback order were not redesigned.

## Final executed CPU results

The exact final source hash above was rebuilt into standalone test executables for direct KH1 `010090C022978001` and KH2 `010090C022978003`, using this worktree's profile generation only. No hostgame target was built.

| Group | KH1 | KH2 control |
|---|---:|---:|
| Inherited ordinary FS | 63/63 | 63/63 |
| Inherited case / listing | 51/51 | 51/51 |
| Inherited CommitList | 36/36 | 36/36 |
| Original six-finding tight fixture | 7 cases / 18 checks | 7 / 18 |
| Expanded six-finding matrix | 28 / 162 | 28 / 162 |
| Original R1 lookup | 2 / 8 | 2 / 8 |
| Expanded R1 matrix + benign/isolation/read-only | 97 / 774 | 97 / 774 |
| Independent R1 endpoint/benign/nontransactional edges | 13 / 72 | 13 / 72 |
| Synthetic rewrite + separate exec read | 2 / 3 | 2 / 3 |

All checks pass. Normal and sanitizer runs each contain **323 commands / zero failed**, **298 RESULT case invocations / 2,074 checks / zero failed**, plus the ordinary-suite checks listed separately above. Counts are parsed from this branch's own logs, not inherited from the reviewed handoff. Ordinary counts differ from the diagnostic branch because its delete/trace/input/migration additions to `t_fs.c` were not imported; all clean-base expectations remain intact (only internal `save_poison` call arity changed).

Expanded adversarial and R1 cases perform fresh-exec normalized readback. Original tight six-finding fixtures retain their original remount oracles, supplemented by the expanded fresh-exec checks. FD coverage includes stale ownership, unrelated descriptor survival, forced numeric FD reuse, old-cookie write/close rejection, rollback-retry and healthy-handle continuity. Lock checks try both locks and actually re-enter the FS in callbacks; concurrency uses an independently released writer, not a schedule that deadlocks a correct fix. There are 100 transactions/profile during concurrent test-only stderr rotation. Synthetic transport rewrites and independently exec-reads **7,073,032 bytes/profile** with identical complete manifests and a distinct flat alias preserved.

ASan + UBSan passes the same full two-profile matrix with no diagnostic. Leak detection disabled; UBSan halts on error. Only `t_fs_commit_list` disables ASan **global redzones** (`-mllvm -asan-globals=0`) because its inherited contiguous Mach-O swforce section walk is incompatible with padding; its code/heap/stack ASan and UBSan remain enabled. No other FS binary disables global instrumentation. No compile warnings were observed.

## Test adaptations / retained evidence

- Imported reviewed adversarial, R1 and independent fixtures retain **all original EXPECT assertion lines byte-for-byte**. Source/include roots became local; poison inspection supports scalar baseline versus indexed fixed source. KH1 fixtures use `KHFM.png`, KH2 `KHIIFM.png`, consistently in physical/guest/alias/cold-reader paths. No no-loss oracle or fault injection was weakened. Removed unused diagnostic HID test stubs; no missing-symbol workaround is needed on this clean source.
- `save_test_log_rotation.h` is a test-directory-only copy used by the inherited concurrent-save fixture. No production logging header, implementation or frontend integration was added. Save-trace tests are deliberately inapplicable, not silently claimed as passing.
- Raw commands, statuses, logs, generated profile snapshots, binaries and synthetic manifests: `/Users/tofu/.hermes/cache/scratch/kh1-save-hardening-evidence/`. Initial pre-edit failures are in `red/`; final accepted runs are `accepted-green/` and `accepted-sanitized/`. Earlier successful intermediate runs remain separately labelled. No binary/fixture/debug archive is committed.
- Committed `kh1-save-hardening-results.json` contains parsed results, source/profile/result-file hashes and complete synthetic manifests. Each raw `results.json` records exact compiler/run argv and cwd. The original pre-edit RED evidence remains unchanged.

Reproduce from this worktree (choose a fresh scratch output path):

```sh
E=/Users/tofu/.hermes/cache/scratch/kh1-save-hardening-retest
python3 dm/host/tests/check_kh_save_equivalence.py
python3 dm/host/tests/run_kh_save_hardening.py --baseline --out "$E/red" # expected exit 1
python3 dm/host/tests/run_kh_save_hardening.py --out "$E/green"
python3 dm/host/tests/run_kh_save_hardening.py --sanitize --out "$E/sanitized"
```

## Remaining owner / limits

Parent independent review and source synchronization follow; do not push/publish yet. This is CPU-only source verification, not installed-KH1, gameplay serialization/slot identity, iOS notification/suspend timing, real-volume exhaustion, arbitrary crash or power-loss certification. Flush remains a validated page-cache no-op and WriteOption remains ignored. No fsync/F_FULLFSYNC/parent-directory durability or suspend auto-commit protocol was added. Fresh-process readback and sampled process-death tests do not prove power-loss durability.
