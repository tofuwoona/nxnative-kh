"""Exact KH1 Program 1 / KH2 Program 3 v0 original save repair tables.

Host activation additionally requires the exact title and complete gate metadata.
0x7f00..07 are private repair SVCs, never general Horizon SVC replacements.
"""
build = 'e1bced80ffd14436980f7490b1d3c3e7'
# Integer-register-only AAPCS64 functions, <=8 arguments. Each entry thunk calls
# the host and returns to its original caller. The saved entry instruction plus
# a branch to entry+4 form a callable ORIGINAL body at gate returnpoint+8.
WRAPS = {build: [
    (0x2c040, 1, 'a9ba7bfd', 'Initialize cache lifecycle under process-lifetime exclusion'),
    (0x2be80, 2, 'a9be7bfd', 'Closing/drain; original worker join runs without exclusion held'),
    (0x2d360, 3, 'd10103ff', 'Synchronous per-complete-record original flush after final length store'),
    (0x2d460, 4, 'a9ba7bfd', 'Exclude original record mutation before first memory access'),
    (0x2d5d0, 5, 'a9ba7bfd', 'Exclude original deletion/compaction'),
    (0x2d250, 6, 'a9bb7bfd', 'Exclude cached reader during in-place transform'),
    (0x2cd20, 7, 'd10283ff', 'Exclude cached listing during in-place transform'),
    (0x2da24, 8, 'd10543ff', 'Guard every original serializer entrant, including Save worker'),
    (0x40ef0, 9, 'd10243ff', 'Recoverable error boundary around ORIGINAL PNG writer during guarded save'),
]}
CUTS = {build: [
    (0x2dba4, '60000034', 'f703002a', 'Preserve PNG status in saved w23; always inverse with original length'),
    (0x2dbcc, '79490f94', '01e00fd4', 'Private 7f00: PNG-qualified original Commit / transaction rejection'),
    (0x2dbd0, '7fa20139', '21e00fd4', 'Private 7f01: retain dirty and payload error on publication failure'),
    (0x41044, 'e0024039', '41e00fd4', 'Private 7f02: fclose error clears PNG flag before original load'),
    (0x40f30, 'f30300aa', '61e00fd4', 'Private 7f03: capture original FILE; emulate mov x19,x0'),
    (0x40f40, 'e2031faa', '81e00fd4', 'Private 7f04: owned host PNG error callback, original zero outside flush'),
    (0x40f4c, 'f50300aa', 'a1e00fd4', 'Private 7f05: capture original PNG; emulate mov x21,x0'),
    (0x40f58, 'f60300aa', 'c1e00fd4', 'Private 7f06: capture original INFO; emulate mov x22,x0'),
    (0x41030, 'a0630091', 'e1e00fd4', 'Private 7f07: hand cleanup ownership to original destroy/fclose; emulate add x0,x29,#0x18'),
]}

# Program1 was mapped independently; do not relocate Program3's table by a delta.
kh1_build = 'badf2faf580b712464365c4d529d92c9'
WRAPS[kh1_build] = [
    (0x11110, 1, 'a9ba7bfd', 'Initialize cache lifecycle under common exclusion'),
    (0x10f50, 2, 'a9be7bfd', 'Drain; original stop/join runs without exclusion held'),
    (0x12430, 3, 'd10103ff', 'Flush original complete record after final operation-status store'),
    (0x12530, 4, 'a9ba7bfd', 'Exclude original cached writer'),
    (0x126a0, 5, 'a9ba7bfd', 'Exclude original deletion/compaction'),
    (0x12320, 6, 'a9bb7bfd', 'Exclude original cached reader'),
    (0x11df0, 7, 'd10283ff', 'Exclude original listing'),
    (0x12af4, 8, 'd10543ff', 'Guard all original serializer entrants'),
    (0x3dff0, 9, 'd10243ff', 'Recoverable boundary around original PNG writer'),
    (0x12cd0, 10, 'a9bd7bfd', 'Guard alternate state step; publish explicit-flush failure after its final store'),
]
CUTS[kh1_build] = [
    (0x12c74, '60000034', 'f703002a', 'Keep PNG status in saved w23; inverse always gets original positive length'),
    (0x12c9c, 'e9710b94', '01e00fd4', 'Private 7f00: qualified original Commit or FS rejection'),
    (0x12ca0, '7fa20139', '21e00fd4', 'Private 7f01: dirty/error publication after inverse'),
    (0x3e144, 'e0024039', '41e00fd4', 'Private 7f02: propagate fclose failure into PNG status'),
    (0x3e030, 'f30300aa', '61e00fd4', 'Private 7f03: FILE capture / original mov x19,x0'),
    (0x3e040, 'e2031faa', '81e00fd4', 'Private 7f04: owned callback / original zero outside flush'),
    (0x3e04c, 'f50300aa', 'a1e00fd4', 'Private 7f05: PNG capture / original mov x21,x0'),
    (0x3e058, 'f60300aa', 'c1e00fd4', 'Private 7f06: INFO capture / original mov x22,x0'),
    (0x3e130, 'a0630091', 'e1e00fd4', 'Private 7f07: disarm and hand resources to original cleanup'),
]
