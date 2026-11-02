"""CPU-only repair table contract. No module rewrite or game execution."""
import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[3]
BUILD = 'e1bced80ffd14436980f7490b1d3c3e7'

class RepairTable(unittest.TestCase):
    def test_common_entry_wrappers_are_build_keyed(self):
        path = ROOT / 'dm/games/010090C022978000/patches.py'
        spec = importlib.util.spec_from_file_location('kh2repair', path)
        assert spec and spec.loader
        p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
        self.assertTrue(hasattr(p,'WRAPS'), 'common original-function wrappers are missing')
        self.assertEqual({o for o, ident, word, why in p.WRAPS[BUILD]},
                         {0x2c040,0x2be80,0x2d360,0x2d460,0x2d5d0,0x2d250,0x2cd20,0x2da24,0x40ef0})
        self.assertEqual({ident for o, ident, word, why in p.WRAPS[BUILD]}, set(range(1,10)))

    def test_failure_unwind_uses_separate_png_status(self):
        path = ROOT / 'dm/games/010090C022978000/patches.py'
        self.assertTrue(path.exists(), 'production build-keyed repair is missing')
        spec = importlib.util.spec_from_file_location('kh2repair', path)
        assert spec and spec.loader
        p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
        cuts = {o: (bytes.fromhex(old), bytes.fromhex(new)) for o, old, new, why in p.CUTS[BUILD]}
        self.assertEqual(cuts[0x2dba4], (struct.pack('<I', 0x34000060), struct.pack('<I', 0x2a0003f7)))
        for off, svc in [(0x2dbcc, 0x7f00), (0x2dbd0, 0x7f01), (0x41044, 0x7f02)]:
            self.assertEqual(cuts[off][1], struct.pack('<I', 0xd4000001 | svc << 5))
        self.assertNotIn(0x2dba8, cuts)  # inverse receives original positive length
        self.assertNotIn(0x2dbb4, cuts)  # old failure branch is unreachable, retained as evidence
        self.assertEqual(set(p.CUTS), {BUILD, "badf2faf580b712464365c4d529d92c9"})

    def test_png_callback_capture_and_cleanup_sites_are_exact(self):
        spec = importlib.util.spec_from_file_location('kh2png', ROOT/'dm/games/010090C022978000/patches.py')
        assert spec and spec.loader
        p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
        cuts={o:(bytes.fromhex(old),bytes.fromhex(new)) for o,old,new,why in p.CUTS[BUILD]}
        for off,old,svc in [(0x40f30,0xaa0003f3,0x7f03),(0x40f40,0xaa1f03e2,0x7f04),
                            (0x40f4c,0xaa0003f5,0x7f05),(0x40f58,0xaa0003f6,0x7f06),
                            (0x41030,0x910063a0,0x7f07)]:
            self.assertEqual(cuts[off],(struct.pack('<I',old),struct.pack('<I',0xd4000001|svc<<5)))
        self.assertEqual(len(cuts),9)
        self.assertEqual(set(p.WRAPS),{BUILD, "badf2faf580b712464365c4d529d92c9"})

if __name__ == '__main__': unittest.main()
