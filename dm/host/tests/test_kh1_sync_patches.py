"""Independent Program1 word/table fixture; no original game bytes required."""
import importlib.util
from pathlib import Path
import struct
import unittest
ROOT=Path(__file__).resolve().parents[3]
BUILD='badf2faf580b712464365c4d529d92c9'
class Program1Table(unittest.TestCase):
    def test_exact_independent_wrappers_and_private_sites(self):
        s=importlib.util.spec_from_file_location('p',ROOT/'dm/games/010090C022978000/patches.py')
        p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
        self.assertIn(BUILD,p.WRAPS,'Program1 production wrappers missing')
        wrappers={i:(o,int(w,16)) for o,i,w,_ in p.WRAPS[BUILD]}
        self.assertEqual(wrappers,{1:(0x11110,0xa9ba7bfd),2:(0x10f50,0xa9be7bfd),3:(0x12430,0xd10103ff),4:(0x12530,0xa9ba7bfd),5:(0x126a0,0xa9ba7bfd),6:(0x12320,0xa9bb7bfd),7:(0x11df0,0xd10283ff),8:(0x12af4,0xd10543ff),9:(0x3dff0,0xd10243ff),10:(0x12cd0,0xa9bd7bfd)})
        cuts={o:(bytes.fromhex(a),bytes.fromhex(b)) for o,a,b,_ in p.CUTS[BUILD]}
        expected={0x12c74:(0x34000060,0x2a0003f7)}
        for i,(o,w) in enumerate([(0x12c9c,0x940b71e9),(0x12ca0,0x3901a27f),(0x3e144,0x394002e0),(0x3e030,0xaa0003f3),(0x3e040,0xaa1f03e2),(0x3e04c,0xaa0003f5),(0x3e058,0xaa0003f6),(0x3e130,0x910063a0)]):expected[o]=(w,0xd4000001|((0x7f00+i)<<5))
        self.assertEqual(cuts,{o:tuple(struct.pack('<I',w) for w in pair) for o,pair in expected.items()})
        self.assertEqual(set(p.WRAPS),{BUILD,'e1bced80ffd14436980f7490b1d3c3e7'})
        self.assertEqual(set(p.CUTS),set(p.WRAPS))
if __name__=='__main__':unittest.main()
