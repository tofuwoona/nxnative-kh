#!/usr/bin/env python3
"""Exact offline KH1 owned-bar adapter; no app, GPU, or device."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
INPUT_ENV = os.environ.get('KH1_BAR_INPUT')
if not INPUT_ENV or not (Path(INPUT_ENV)/'main.patched.bin').is_file():
    raise unittest.SkipTest('set KH1_BAR_INPUT to the private reconstructed-module directory')
INPUT = Path(INPUT_ENV)
SPEC = importlib.util.spec_from_file_location('bar', ROOT/'dm/tools/kh1_bar_patch.py')
bar = None
if SPEC and Path(SPEC.origin).exists():
    bar = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(bar)


class BarPatchTests(unittest.TestCase):
    def test_exact_patch_scope_and_default_off(self):
        self.assertIsNotNone(bar, 'KH1 offline bar adapter is not implemented')
        original=(INPUT/'main.patched.bin').read_bytes()
        image=bar.patch_image(original)
        self.assertEqual(bar.QUAD_CALLS, (0x3ef20,0x3ef88,0x3efd8,0x3f024,
                                         0x5eb30,0x5eb98,0x5ebe8,0x5ec34))
        self.assertEqual(len(image), bar.OUTPUT_SIZE)
        self.assertEqual(image[bar.FLAG:bar.FLAG+4], bytes(4))
        restored=bytearray(image[:len(original)])
        for site in bar.QUAD_CALLS:
            target=bar.ADAPTER if site in bar.QUAD_CALLS1 else bar.ADAPTER2
            self.assertEqual(struct.unpack_from('<I', image, site)[0], bar.bl(site, target))
            restored[site:site+4]=original[site:site+4]
        self.assertEqual(restored, original)
        self.assertEqual(image[len(original):], bar.appendix())
        self.assertEqual(hashlib.sha256(image[bar.ADAPTER:bar.ADAPTER+len(bar.adapter(bar.ADAPTER))]).hexdigest(),
                         'd5e4f81f9607efafeea8f88cbee39121b60dd4dffcdeeea4451d731fcd5b85ad')
        second=bar.adapter(bar.ADAPTER2,bar.QUAD_CONSTRUCTOR2)
        self.assertEqual(image[bar.ADAPTER2:bar.ADAPTER2+len(second)],second)

    def test_reject_bad_inputs_and_repatch(self):
        self.assertIsNotNone(bar)
        original=(INPUT/'main.patched.bin').read_bytes()
        bad=bytearray(original);bad[0x3edcc]^=1
        for data in (b'', original[:-1], original+bytes(4), bytes(bad), bar.patch_image(original)):
            with self.assertRaises(ValueError): bar.patch_image(data)
        for pc,target in ((0,1),(0,1<<27),(1<<27,-4),(2,4)):
            with self.assertRaises(ValueError): bar.bl(pc,target)

    def test_directory_preserves_all_non_main_inputs(self):
        self.assertIsNotNone(bar)
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as td:
            dst=Path(td)/'out'
            receipt=bar.patch_directory(INPUT,dst)
            for file in INPUT.iterdir():
                if file.name!='main.patched.bin': self.assertEqual(file.read_bytes(),(dst/file.name).read_bytes())
            self.assertEqual(receipt,json.loads((dst/'bar-manifest.json').read_text()))
            for name,item in receipt['outputs'].items():
                data=(dst/name).read_bytes()
                self.assertEqual(len(data),item['size'])
                self.assertEqual(hashlib.sha256(data).hexdigest(),item['sha256'])
            with self.assertRaises(ValueError):bar.patch_directory(dst,Path(td)/'twice')
            self.assertFalse((Path(td)/'twice').exists())


if __name__=='__main__': unittest.main()
