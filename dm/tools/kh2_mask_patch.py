#!/usr/bin/env python3
"""Exact release-reconstructed rewritten KH2 image, NOT an original NSO.
Offline owned-quad call replacement only; append RX stubs. The loader-zeroed key-page
word +0x100 is reserved for pre-guest host activation, default OFF.
"""
import hashlib
import struct

INPUT_SHA = '79bd1d43b574173ff0823f74f95f515c5216a805528aeeb166fc913d83b3e66b'
INPUT_SIZE = 0x2d5c000
OUTPUT_SIZE = INPUT_SIZE + 0x4000
KEY_PAGE = 0x2d30000
FLAG = KEY_PAGE + 0x100
ENTRIES = (0x37760, 0x4422c)
CPU_ENTRY = 0x21938
PROLOGUE = bytes.fromhex('ff8302d1')
FUNCTIONS = ((0x37760,0x37a54,'86ac22d4acc9ebddc8cae3370250a02cd616bb308addd786c697389a08feb414'),
             (0x4422c,0x444c4,'e31171a53fd6ecfe16781e216e58fe4af107d0252244dd96452698ddbf3e682d'))

def branch(pc, target):
    delta = target-pc
    if pc % 4 or target % 4 or not -(1<<27) <= delta < (1<<27):
        raise ValueError('unaligned/out-of-range AArch64 B')
    return 0x14000000 | ((delta//4) & 0x3ffffff)

TITLE_STATE = 0xb5a31c  # u32: active title descriptor lifecycle == 1
MEDIA_TASK = 0xccc258   # u64: decoded-movie task owns load/play/teardown
MEDIA_CALLER_LR = 0x1868ec
PAYLOAD_SIZE = 320


QUAD_CONSTRUCTOR = 0x2126c
QUAD_CALLS = (0x37908, 0x37970, 0x379c0, 0x37a0c,
              0x44380, 0x443e8, 0x44438, 0x44484)


def quad_stub(pc):
    # Always execute the complete authentic constructor with unchanged args.
    # Restore its caller LR, then preserve its returned x16/x17 while gating.
    # The constructor emits four 20-byte vertices and returns output+0x50.
    # Collapse only X of vertices 1..3: no caller corner/state data is changed.
    # No instruction after BL changes NZCV, SIMD, FPCR/FPSR or callee outputs.
    words = [0xa9bf7bfd,                            # stp x29,x30,[sp,#-16]!
             branch(pc+4, QUAD_CONSTRUCTOR) | 0x80000000,
             0xa8c17bfd,                            # ldp x29,x30,[sp],#16
             0xa9bf47f0,                            # stp x16,x17,[sp,#-16]!
             adrp(pc+16, FLAG, 16),
             0xb9400210 | ((FLAG & 0xfff)//4) << 10,
             0x36000010 | (19-6) << 5,              # tbz w16,#0,restore
             adrp(pc+28, TITLE_STATE, 16),
             0xb9400210 | ((TITLE_STATE & 0xfff)//4) << 10,
             0x51000610,                            # sub w16,w16,#1 (not SUBS)
             0x34000010 | (19-10) << 5,             # cbz w16,restore
             adrp(pc+44, MEDIA_TASK, 16),
             0xf9400210 | ((MEDIA_TASK & 0xfff)//8) << 10,
             0xb5000010 | (19-13) << 5,             # cbnz x16,restore
             0xd1014011,                            # sub x17,x0,#0x50
             0xb9400230,                            # ldr w16,[x17]
             0xb9000230 | (20//4) << 10,
             0xb9000230 | (40//4) << 10,
             0xb9000230 | (60//4) << 10,
             0xa8c147f0, 0xd65f03c0]               # restore, return
    return struct.pack('<21I', *words)

def adrp(pc, target, reg):
    delta = (target >> 12) - (pc >> 12)
    if not -(1 << 20) <= delta < (1 << 20):
        raise ValueError('ADRP out of range')
    return 0x90000000 | reg | ((delta & 3) << 29) | (((delta >> 2) & 0x7ffff) << 5)


def cpu_stub(pc):
    # Real helper 21910 saves caller LR at SP+16, then calls two getters.
    # At 21938 live LR is 2192c, NOT the media caller. Spill adds 16 bytes:
    # read [SP+32], compare the full relocated address without changing NZCV.
    # CPU bit 1 OFF must replay original CBZ w8 (not x8), even for media.
    media_lr = MEDIA_CALLER_LR
    words = [0xa9bf47f0, adrp(pc+4, FLAG, 16),
             0xb9400210 | ((FLAG & 0xfff)//4) << 10,
             0x36080110,                         # tbz w16,#1,+32 (OFF)
             0xf94013f0,                         # ldr x16,[sp,#32]
             adrp(pc+20, media_lr, 17),
             0x91000231 | (media_lr & 0xfff) << 10, # add x17,x17,#lo12
             0xca110210,                         # eor x16,x16,x17
             0xb40000d0,                         # cbz x16,+24 (fixed)
             0xa8c147f0, branch(pc+40, CPU_ENTRY+4),
             0xa8c147f0,                         # OFF restores scratch
             0x35ffffc8,                         # cbnz w8,-8 (physical)
             branch(pc+52, 0x21950),
             0xa8c147f0, branch(pc+60, 0x21950)]
    return struct.pack('<16I', *words)

def appendix(cpu_aspect=False):
    meta = b'KH2MASK-OFF-v3\0\0' + bytes.fromhex(INPUT_SHA)
    meta += struct.pack('<8Q',INPUT_SIZE,OUTPUT_SIZE,FLAG,ENTRIES[0],ENTRIES[1],
                        INPUT_SIZE+128,QUAD_CONSTRUCTOR,3 if cpu_aspect else 1)
    meta += struct.pack('<2Q',CPU_ENTRY if cpu_aspect else 0,INPUT_SIZE+256 if cpu_aspect else 0)
    assert len(meta) == 128
    return (meta + quad_stub(INPUT_SIZE+128).ljust(128,b'\0') +
            (cpu_stub(INPUT_SIZE+256) if cpu_aspect else b'')).ljust(0x4000,b'\0')

def payload_header():
    """One canonical emitter for offline module bytes and host pairing bytes."""
    lines = ['// Generated by dm/tools/kh2_mask_patch.py --emit-header; do not edit.',
             '#pragma once',
             f'static const unsigned char kh2_mask_tail[2][{PAYLOAD_SIZE}] = {{']
    for cpu in (False, True):
        data = appendix(cpu)
        assert not any(data[PAYLOAD_SIZE:])
        lines.append('  {')
        for offset in range(0, PAYLOAD_SIZE, 16):
            lines.append('    ' + ', '.join(f'0x{x:02x}' for x in data[offset:offset+16]) + ',')
        lines.append('  },')
    lines.append('};')
    lines.append('static const unsigned int kh2_mask_quad_calls[8][2] = {')
    for site in QUAD_CALLS:
        lines.append(f'  {{ 0x{site:08x}, 0x{branch(site, INPUT_SIZE+128) | 0x80000000:08x} }},')
    lines.append('};')
    return '\n'.join(lines) + '\n'


def patch_image(original, cpu_aspect=False):
    if len(original) != INPUT_SIZE or hashlib.sha256(original).hexdigest() != INPUT_SHA:
        raise ValueError('requires exact release-reconstructed input SHA/size (no repatching)')
    for start,end,sha in FUNCTIONS:
        if original[start:start+4] != PROLOGUE or hashlib.sha256(original[start:end]).hexdigest()!=sha:
            raise ValueError('mask producer bytes mismatch')
    if any(original[KEY_PAGE:KEY_PAGE+0x4000]): raise ValueError('key page must be zero in file')
    out = bytearray(original)
    # Preserve both complete original producers, including their state setup.
    for site in QUAD_CALLS:
        expected = branch(site, QUAD_CONSTRUCTOR) | 0x80000000
        if struct.unpack_from('<I', original, site)[0] != expected:
            raise ValueError('owned quad BL mismatch')
        struct.pack_into('<I', out, site, branch(site, INPUT_SIZE+128) | 0x80000000)
    if cpu_aspect:
        if original[CPU_ENTRY:CPU_ENTRY+4] != bytes.fromhex('c8000034') or hashlib.sha256(original[0x21910:0x219a0]).hexdigest() != 'ead58dcc51ce3c21dea8249a6dd76643bd56d0997d617e6c72b959b0bdb907cf':
            raise ValueError('CPU aspect helper byte mismatch')
        struct.pack_into('<I',out,CPU_ENTRY,branch(CPU_ENTRY,INPUT_SIZE+256))
    return bytes(out)+appendix(cpu_aspect)

# Exact complete reconstructed release set; private artifacts are not checked in.
INPUT_FILES = {'main.cuts.tsv': 'f8b3af0eb13b762d5464c41447bb428696fab24ff8a83675e5fadfd6da4a8401', 'main.fixups.tsv': '80289ad11a309bc100bfd2f87a61e50cea6696d5dceb5fd8abf911ab93beb300', 'main.gates.tsv': '4d4bed186cf3ee85e9ed8b68acb9f2cbec7dd6b82d36cd48162cc5437db94ece', 'main.obs.tsv': '882ab2aa6100e70ed42ca97b425a3ec3c0ce64d38112cda2aa2813297953eb67', 'main.patched.bin': '79bd1d43b574173ff0823f74f95f515c5216a805528aeeb166fc913d83b3e66b', 'reconstruction.json': '0f021914e3caf0bdcf337e375554a77a411987f5a1beebd6c9670647865e212f', 'sdk.cuts.tsv': '3f1d4d685b7b5b44304c713c45f9017b5178a3b1e9985410ac85173115a41189', 'sdk.fixups.tsv': '1d2c29e5a8b59df38736572c93f99afa0b5f6dddaddfcd7f6772d63ec47911dc', 'sdk.gates.tsv': '4ef94ee60dc39f70bd18ec17c8e4c7afcd7a13ead7a5eade9e7662f180dc756b', 'sdk.obs.tsv': '3f1d4d685b7b5b44304c713c45f9017b5178a3b1e9985410ac85173115a41189', 'sdk.patched.bin': 'abaed505cfcdf65e7feb6e80d09cdc038ac2052850169bd30d064e9664d6c900', 'subsdk1.cuts.tsv': '1658361df3d5bea98384fd6bb06aee5dfeafe8cc49feda073466be963035f8ab', 'subsdk1.fixups.tsv': 'bf30dd79b28967109cd40f6d67e86136fc983e672e6292cb7bf52a470ed37f8e', 'subsdk1.gates.tsv': 'd9e5fda3bb02ca004e87c2395a0aa4ddbab160f5f31f7c38e9d497aadff3bc0b', 'subsdk1.obs.tsv': '1658361df3d5bea98384fd6bb06aee5dfeafe8cc49feda073466be963035f8ab', 'subsdk1.patched.bin': '34be9d2f39b613a5fa5717b2d478e9a42eb441983c0ea1eeeb739e5b5d6f67cc'}

def patch_directory(source, destination, cpu_aspect=False):
    from pathlib import Path
    import json
    import shutil
    source, destination = Path(source), Path(destination)
    if destination.exists(): raise ValueError('destination must not exist')
    blobs = {}
    for name, sha in INPUT_FILES.items():
        try: data = (source/name).read_bytes()
        except OSError as e: raise ValueError(f'missing input {name}') from e
        if hashlib.sha256(data).hexdigest() != sha: raise ValueError(f'exact input mismatch: {name}')
        blobs[name] = data
    blobs['main.patched.bin'] = patch_image(blobs['main.patched.bin'],cpu_aspect)
    manifest = {'provenance':'release-reconstructed rewritten modules; NOT original NSO',
                'input_sha256': INPUT_FILES, 'default_flag':0, 'flag_offset':hex(FLAG),
                'entry_offsets':[hex(x) for x in (*QUAD_CALLS,CPU_ENTRY)] if cpu_aspect else [hex(x) for x in QUAD_CALLS],
                'cpu_aspect_capability':bool(cpu_aspect),
                'payload_version':3,
                'preserved_producer_entries':[hex(x) for x in ENTRIES],
                'geometry_policy':'authentic constructor then equalize vertex 1/2/3 X to vertex 0 X',
                'original_mask_periods':{'title_u32_equals_1':hex(TITLE_STATE),
                                         'media_task_u64_nonzero':hex(MEDIA_TASK)},
                'fixed_cpu_media_caller_lr':hex(MEDIA_CALLER_LR) if cpu_aspect else None,
                'outputs':{name:{'size':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in blobs.items()}}
    destination.mkdir(parents=True)
    try:
        for name,data in blobs.items(): (destination/name).write_bytes(data)
        (destination/'mask-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    except BaseException:
        shutil.rmtree(destination)
        raise
    return manifest

if __name__ == '__main__':
    import argparse
    import json
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', nargs='?'); p.add_argument('destination', nargs='?')
    p.add_argument('--emit-header', action='store_true', help='print canonical host pairing header only')
    p.add_argument('--cpu-aspect',action='store_true',help='append separately gated CPU-aspect redirect (still default OFF)')
    a = p.parse_args()
    if a.emit_header:
        if a.source or a.destination or a.cpu_aspect: p.error('--emit-header takes no other arguments')
        print(payload_header(), end='')
    else:
        if not a.source or not a.destination: p.error('source and destination are required')
        try: print(json.dumps(patch_directory(a.source,a.destination,a.cpu_aspect),indent=2))
        except ValueError as e: p.error(str(e))
