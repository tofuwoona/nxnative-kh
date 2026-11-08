#!/usr/bin/env python3
"""Canonical host/payload pairing and explicit pre-media v1 rejection."""
import hashlib
import os
import struct
from pathlib import Path
import tempfile
import unittest
from test_kh2_mask import mask, INPUT, ROOT
import test_kh2_mask_host as host

# Exact former integrated payload (only generated adapter bytes, no private
# game bytes). The full reconstructed v1 SHA pins this regression fixture.
LEGACY_TAIL = bytes.fromhex(
    '4b48324d41534b2d4f46462d7631000079bd1d43b574173ff0823f74f95f515c5216a805528aeeb166fc913d83b3e66b'
    '00c0d502000000000000d602000000000001d3020000000060770300000000002c4204000000000080c0d50200000000'
    'c0c0d502000000000300000000000000381902000000000000c1d50200000000'
    'f047bfa9b0feff90100241b970000036f047c1a8c0035fd6f047c1a8ff8302d1b16d4b17'
    '00000000000000000000000000000000000000000000000000000000'
    'f047bfa9b0feff90100241b970000036f047c1a8c0035fd6f047c1a8ff8302d154a04b17'
    '00000000000000000000000000000000000000000000000000000000'
    'f047bfa9b0feff90100241b970000836f047c1a80a164b17f047c1a8480000350c164b1706164b17'
    '000000000000000000000000000000000000000000000000')


LEGACY_V2 = bytes.fromhex(
    '4b48324d41534b2d4f46462d7632000079bd1d43b574173ff0823f74f95f515c5216a805528aeeb166fc913d83b3e66b'
    '00c0d502000000000000d602000000000001d3020000000060770300000000002c4204000000000080c0d50200000000'
    'c0c0d502000000000300000000000000381902000000000000c1d50200000000'
    'f047bfa9b0feff90100241b950010036f0effed0101e43b910060051d000003490fbfe90102e41f9700000b5f047c1a8c0035fd6f047c1a8ff8302d1aa6d4b17'
    'f047bfa9b0feff90100241b950010036f0effed0101e43b910060051d000003490fbfe90102e41f9700000b5f047c1a8c0035fd6f047c1a8ff8302d14da04b17'
    'f047bfa9b0feff90100241b910010836f01340f951a1fed031b22391100211cad00000b4f047c1a805164b17f047c1a8c8ffff3507164b17f047c1a805164b17')


def legacy_image(original, tail):
    image=bytearray(original)+tail.ljust(0x4000,b'\0')
    for site,word in ((0x37760,0x14b49248),(0x4422c,0x14b45fa5),(0x21938,0x14b4e9f2)):
        struct.pack_into('<I',image,site,word)
    return image


class PairingTests(unittest.TestCase):
    def test_legacy_integrated_payload_is_rejected(self):
        original = (INPUT/'main.patched.bin').read_bytes()
        legacy = legacy_image(original, LEGACY_TAIL)
        self.assertEqual(len(LEGACY_TAIL), 320)
        legacy[mask.INPUT_SIZE:mask.INPUT_SIZE+320] = LEGACY_TAIL
        self.assertEqual(hashlib.sha256(legacy).hexdigest(),
                         '6d25a372ee975ca065fb66b37e2d831b84909c4d5f9d22bff6b6ec7c75141e90')
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as td:
            image = Path(td)/'legacy.bin'
            image.write_bytes(legacy)
            host.HostTests().run_cases([36], image, cpu_switch='1')

    def test_canonical_header_and_version(self):
        self.assertEqual(mask.appendix(True)[:16], b'KH2MASK-OFF-v3\0\0')
        self.assertTrue(hasattr(mask, 'payload_header'))
        self.assertEqual((ROOT/'dm/host/kh2_mask_payload.h').read_text(), mask.payload_header())

    def test_marker_and_each_instruction_must_pair(self):
        original = (INPUT/'main.patched.bin').read_bytes()
        image = bytearray(mask.patch_image(original, cpu_aspect=True))
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as td:
            file = Path(td)/'mutated.bin'
            # v3 marker cannot bless old thunks, or vice versa.
            for start, end in ((0, 16), (128, 320)):
                bad = image.copy()
                bad[mask.INPUT_SIZE+start:mask.INPUT_SIZE+end] = LEGACY_TAIL[start:end]
                file.write_bytes(bad)
                host.HostTests().run_cases([36], file, cpu_switch='1')

    def test_v2_installed_image_and_mixed_v3_payload_rejected(self):
        original=(INPUT/'main.patched.bin').read_bytes()
        legacy=legacy_image(original,LEGACY_V2)
        self.assertEqual(hashlib.sha256(legacy).hexdigest(),
                         'ec1eed8851b1552ccc6115a23fab99d52da50a5712a794c0dd2e1a8a4ded8d72')
        current=bytearray(mask.patch_image(original,cpu_aspect=True))
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as td:
            file=Path(td)/'mixed.bin'
            for data in (legacy,):
                file.write_bytes(data)
                host.HostTests().run_cases([36],file,cpu_switch='1')
            for lo,hi in ((0,16),(128,256),(0,320)):
                bad=current.copy()
                bad[mask.INPUT_SIZE+lo:mask.INPUT_SIZE+hi]=LEGACY_V2[lo:hi]
                file.write_bytes(bad)
                host.HostTests().run_cases([36],file,cpu_switch='1')

    def test_all_owned_calls_must_pair_with_original_producer_entries(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as td:
            file=Path(td)/'mutated.bin'
            original=(INPUT/'main.patched.bin').read_bytes()
            image=mask.patch_image(original,cpu_aspect=True)
            for site in mask.QUAD_CALLS:
                bad=bytearray(image)
                bad[site:site+4]=original[site:site+4]
                file.write_bytes(bad)
                host.HostTests().run_cases([36],file,cpu_switch='1')
            for site,word in ((0x37760,0x14b49248),(0x4422c,0x14b45fa5)):
                bad=bytearray(image)
                struct.pack_into('<I',bad,site,word)
                file.write_bytes(bad)
                host.HostTests().run_cases([36],file,cpu_switch='1')


if __name__ == '__main__': unittest.main()
