# KH1/KH2 save R1 repair — implementation handoff

## Integration boundary

- Branch `fix/save-r1-path-resolution`; isolated worktree `/Users/tofu/.hermes/cache/scratch/kh-save-r1`.
- Exact parent `e191b99d1806682888557e415ab82c99f9185fb0`; common Git directory `/Users/tofu/Documents/Workspace/nxnative-kh/.git`.
- This commit is a small follow-up to the save implementation, not a replacement for it. Parent should independently review this delta, cherry-pick onto the integrated source, then rebuild iOS. **No installation approval is claimed. The old signed 1.0.9 candidate must not be deployed.**
- Only production change: `dm/host/hle_fs.c` (+33/-15 lines). HUD, rounding, X/Y, coalescer/settings, shaders, lifecycle and migration remain unchanged. The migration function was byte-compared with the parent. No migration, suspend commit or fsync protocol was added.
- No phone, original save, integration checkout, shared game output or GPU/game launch was used. Fixtures are disposable synthetic trees. Mac binary and generated headers belong to this worktree.

## Root cause and bounded repair

The independent report's four Create/Open cases were reproduced **before production edits**: both profiles returned successful Commit after an ignored `.work` parent `opendir(EIO)` failure; the old canonical save was missing (Create) or six zero bytes (Open). Four cases / 16 checks / 12 failed.

`HP`/`HP_EX` returned before the old syscall-level poison branches. A physical path cannot identify the transaction when resolution is incomplete. The repair:

1. Attribute unexpected failed mutations by **exact guest mount name** under the existing path lock. Shared backing aliases retain shared poison; independent saves do not. Missing/existing/type/invalid-name probes are excluded (`ENOENT`, `ENOTDIR`, `EEXIST`, `EISDIR`, `ENOTEMPTY`, `ENAMETOOLONG`, `EINVAL`). Read-only/nontransactional mounts are not poisoned.
2. Give the path macro an explicit mutating predicate. Use it for write/append/read-write OpenFile, CreateFile, DeleteFile, CreateDirectory, DeleteDirectory, both recursive mutations, and rename source. Rename destination-resolution, existence-probe and syscall I/O failures attribute both guest endpoints, preserving the original errno.
3. Preserve lookup errors through cleanup: distinguish `readdir` EOF from I/O failure, retain `getxattr` errno across `closedir`, and propagate directory-close errors. Otherwise an I/O failure could become benign ENOENT and still bypass poison.
4. Protect the corresponding DeleteDirectory syscall failure seam. Existing read-only OpenFile/GetEntryType/OpenDirectory/ReadFile errors do not poison otherwise healthy writes.

The tests for the directory/rename/error-preservation seams were run red before their production repair. No prior assertion source was changed. An early new fixture initially read its pre-alias physical filename after intentionally renaming that directory; the fixture's canonical physical target was corrected before the seam RED run used below. The fresh-process guest oracle was never weakened.

## Executed verification

Counts are parsed from retained result JSON/logs, not inferred from command exit alone.

| Run | Commands | Semantic result |
|---|---:|---|
| Original reviewer cases before edits | 8; 4 failed | Four red cases, 16 checks, 12 failed |
| Same original cases after first repair | 8; all pass | Four cases, 16 checks, none failed |
| Final expanded R1 harness against exact e191b99 (`--baseline`) | 204; 162 failed (expected exit 1) | 198 invocations, 1,564 checks, 804 failed |
| Final R1 harness, KH1 + KH2 | 204; all pass | 198 invocations, 1,564 checks, none failed |
| Same R1 harness, ASan + UBSan, both profiles | 204; all pass | 198 invocations, 1,564 checks, none failed; no sanitizer report |
| Prior full suites, both profiles | 78; all pass | 56 adversarial invocations / 324 checks; normal suites below; trace/logger/synthetic transport pass |
| Prior full suites with sanitizer configuration below | 78; all pass | Same assertions, none failed |
| Original independent six-finding tight fixtures + extra KH2 sanitized adversarial run | 45; all pass | Original 14 invocations / 36 checks; extra sanitized 28 invocations / 162 checks |

Normal suites retain their existing expectations: KH2 `t_fs` 74/74, KH1 64/64; `t_fs_case` 51/51 each; `t_fs_commit_list` 36/36 each. Both save-trace tests pass. Concurrent log rotation with 100 transactions/profile and the separate log/FD/sparse-4-GiB tests pass. The 7,073,032-byte deterministic container's manifests match after rewrite/Commit and independent exec readback, including the distinct flat alias.

R1 matrix covers first/second parent `opendir` (EIO/EMFILE), `readdir`, `closedir`, aliased-name `getxattr` with cleanup errno clobbering, create/destination `lstat`, rename destination `access`, rename/rmdir syscalls and writable-open `fstat`. Every row checks actual injection, guest error, scoped poison/original errno, Commit outcome, canonical bytes, notification/unlocked callback, and **fresh exec** normalized readback. Additional cases cover benign missing-parent/EEXIST/directory/invalid/oversized/unmounted probes, read-only lookup/data-I/O, ENOMEM attribution through backslash spelling and mount alias, and independent prefix-sharing `save2` publication.

### Sanitizer caveat (preserved failure evidence)

The first attempt to sanitize *all* prior suites failed in both `t_fs_commit_list` binaries before filesystem behavior: ASan inserts redzones between registration globals, invalidating that test's intentional contiguous Mach-O `swforce` section walk (`list_hook`, line 45). Logs remain in `prior-sanitized/` in the archive. The runner now passes `-mllvm -asan-globals=0` **only for that binary**; stack/heap/code address instrumentation and UBSan remain. All other normal/adversarial/R1 binaries retain global instrumentation. No test assertion or production registration macro was changed. Leak detection is disabled (`ASAN_OPTIONS=detect_leaks=0`); UBSan halts on error. The independent logger binary remains its normal unsanitized compile, as in the inherited runner.

## Reproduce in the isolated worktree

```sh
cd /Users/tofu/.hermes/cache/scratch/kh-save-r1
E=/Users/tofu/.hermes/cache/scratch/kh-save-r1-retest
DM_SAVE_PATH_OUT="$E/path-red" python3 dm/host/tests/run_save_path_resolution.py --baseline # expected exit 1
DM_SAVE_PATH_OUT="$E/path-green" python3 dm/host/tests/run_save_path_resolution.py
DM_SAVE_PATH_OUT="$E/path-sanitized" python3 dm/host/tests/run_save_path_resolution.py --sanitize
DM_SAVE_TEST_OUT="$E/prior" python3 dm/host/tests/run_save_review.py
DM_SAVE_TEST_OUT="$E/prior-sanitized" python3 dm/host/tests/run_save_review.py --sanitize
make -C dm/host -j4 GAME=010090C022978003 \
  DM_GAMES_DIR="$PWD/dm/games/010090C022978000/direct-profiles" DM_GAMES_FIRST=1
```

Both runners isolate binaries, logs and fixtures under their chosen output. They generate profile headers **only in this worktree**. Prior runner output isolation was repaired because its previous output variable did not relocate hardcoded binaries/fixtures. Fault configuration inherited from the caller is cleared. Exact per-command argv/cwd/status/log paths are retained in result JSON.

## Built artifact and durable evidence

- Exact Program 3 Mac build above: exit 0; `dm/host/dmhost`, Mach-O arm64, 2,449,064 bytes.
- Binary SHA-256: `b858a0a22d6664ebecc7e927cefa26fa54bc70cd5dd4c9940e61f65f72f3e823`.
- Production `hle_fs.c` SHA-256: `32e36ff48977f8e96ef2e65a2174d6960e5a53626fcb521ead5db8e77c3d06f9`.
- Own `gen/game.stamp`: `010090C022978003`; header contract: `kh2_fifth.pkg`, `mem_used=0x4200000`, main BUILD_ID `e1bced80ffd14436980f7490b1d3c3e7`.
- Build emitted 45 warnings in untouched files; none in `hle_fs.c`. Full compile/link log retained. No binary was launched.
- Raw evidence: `/Users/tofu/.hermes/cache/scratch/kh-save-r1-evidence`; committed `kh2-save-r1-summary.json` and `kh2-save-r1-evidence.tar.gz` preserve logs/JSON/reviewer adaptations/source snapshots, excluding binaries and fixture trees. Extract with `tar -xzf docs/agents/kh2-save-r1-evidence.tar.gz -C <own-evidence-dir>`.
- Evidence archive SHA-256: `ff92b054eda38341264bfe0a72a4d278741c8fae63fdd2d4ec226912084d6a89`.

## Remaining owner/gates

Parent owns independent review of the exact new revision and integrated production hash, iOS rebuild/signature/resource verification, backup-protected installation and gameplay slot save/reload tests. CPU tests do not prove historical UI-completed/zero-write causation, game serialization/slot identity, iOS alerts/suspend timing, real volume exhaustion, arbitrary crash safety or power-loss durability. Flush remains a page-cache no-op; no power-loss barriers were added. Do not reuse the previous signed 1.0.9 binary as evidence for this source.
