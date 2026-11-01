#!/usr/bin/env python3
"""Compare clean FS C tokens with reviewed 566afc3 minus explicit exclusions.

This is a read-only equivalence guard, NOT a source generator. It drops only
reviewed tracing/input timing and opt-in legacy migration. All remaining C
(non-comment/non-whitespace) tokens must match, including generic FS paths.
"""
import difflib
import hashlib
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
REVIEW = '566afc34000535faa9dbb9d5e6730d9dd2e5f218'
REVIEW_SHA256 = '32e36ff48977f8e96ef2e65a2174d6960e5a53626fcb521ead5db8e77c3d06f9'
raw = subprocess.check_output(['git', 'show', REVIEW + ':dm/host/hle_fs.c'], cwd=ROOT)
assert hashlib.sha256(raw).hexdigest() == REVIEW_SHA256, 'reviewed source hash mismatch'
expected = raw.decode()


def replace(old, new='', count=1):
    global expected
    assert expected.count(old) == count, ('exclusion must be exact', old, expected.count(old))
    expected = expected.replace(old, new)


def remove_range(start, end):
    global expected
    assert expected.count(start) == 1 and expected.count(end) == 1
    a, b = expected.index(start), expected.index(end)
    assert a < b
    expected = expected[:a] + expected[b:]


# Diagnostic-only declarations/functions. Keep the inherited FSLOG and ordinary
# commit timing/counter behavior already present on e9ca69c.
replace('static _Atomic uint64_t g_txn_input_ns;     // preceding input transition at the FIRST write, not a later stick movement during the save\n')
replace('// t_fs has no HID implementation; the weak reference is zero there, and the real host links hle_hid.c.\n')
replace('extern uint64_t dm_input_last_event_ns(void) __attribute__((weak));\n')
replace('static int save_trace_on(void) { const char *e = getenv("DM_SAVE_TRACE"); return e && *e && strcmp(e, "0"); }\n')
remove_range('static void save_trace_file(', 'static void fslog_init(')
# This forbidden helper and its only caller are absent on the clean base.
remove_range('// KH2\'s exported save can contain a legacy flat filename with literal Windows\n', 'static Result mount_ex(')
replace('        else if (!strcmp(name, "save") && kh2_save_migrate(work)) why = "staging the legacy KH2 save in the work directory failed";\n')
replace('    uint64_t ti = atomic_exchange(&g_txn_input_ns, 0);\n')
replace('        if (save_trace_on()) LOG("[save-trace] commit %s refused errno=%d writes=%d", g_mnt[i].commit, perr, atomic_load(&g_save_writes));\n')
start = expected.index('    if (save_trace_on()) {\n')
end = expected.index('    return r;\n}', start)
replace(expected[start:end])
replace('(g_fslog || (g_fsave[fd] && save_trace_on()))', 'g_fslog')
replace('    if (g_fsave[fd] && save_trace_on()) LOG("[save-trace] open %s mode=%d fd=%d", path, mode, fd);\n')
replace('''        { uint64_t last_input = dm_input_last_event_ns ? dm_input_last_event_ns() : 0;
          uint64_t z = 0, t = clock_gettime_nsec_np(CLOCK_MONOTONIC);
          if (atomic_compare_exchange_strong(&g_txn_first_ns, &z, t))
              atomic_store(&g_txn_input_ns, last_input); }''', '''        { uint64_t z = 0; atomic_compare_exchange_strong(&g_txn_first_ns, &z, clock_gettime_nsec_np(CLOCK_MONOTONIC)); }''')
for call in [
    ' save_trace_file(h, "write", off, sz, fail_e);',
    ' save_trace_file(h, "write", off, sz, e);',
    ' save_trace_file(h, "write", off, sz, ENOSPC);',
    '    save_trace_file(h, "write", off, sz, 0);\n',
    '    save_trace_file(h, "resize", 0, (size_t)sz, e);\n',
]:
    replace(call)
replace('if (!ftruncate((int)h, sz)) { save_trace_file(h, "resize", 0, (size_t)sz, 0); return RES_OK; }', 'if (!ftruncate((int)h, sz)) return RES_OK;')
replace('    if (in_txn_dir(hp) && save_trace_on()) LOG("[save-trace] create %s size=%lld %s errno=%d", path, (long long)sz, rc ? "failed" : "ok", rc ? e : 0);\n')
replace(' if (save_trace_on()) LOG("[save-trace] delete %s failed errno=%d", path, e);')
replace('    if (in_txn_dir(hp) && save_trace_on()) LOG("[save-trace] delete %s ok", path);\n')

# Preserve quoted strings/characters before removing comments, so path literals,
# errno/result values, ABI names and every control-flow token stay significant.
lexer = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/|\w+|[^\s]')


def tokens(text):
    return [m.group() for m in lexer.finditer(text) if not m.group().startswith(('//', '/*'))]


actual_bytes = (ROOT / 'dm/host/hle_fs.c').read_bytes()
a, b = tokens(expected), tokens(actual_bytes.decode())
if a != b:
    print(''.join(difflib.unified_diff([t + '\n' for t in a], [t + '\n' for t in b], fromfile='reviewed-minus-explicit-exclusions', tofile='clean-backport')))
    raise SystemExit('FAIL: unexpected C token difference')
print('PASS: all FS C tokens equal reviewed source minus explicit trace/input/migration exclusions')
print('reviewed_sha256=' + REVIEW_SHA256)
print('backport_sha256=' + hashlib.sha256(actual_bytes).hexdigest())
