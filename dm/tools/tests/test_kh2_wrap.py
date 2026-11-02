"""Exercise production offline wrapper emitter, not a game/module rewrite."""
import ast
from pathlib import Path
import sys
import struct
import unittest
from typing import Any
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'dm/tools'))
from nso_asm import B, STP_PRE, LDP_POST, BLR, MRS_TPIDRRO, LDRX, ADDR, ADRP

class WrapEmitter(unittest.TestCase):
    def test_callable_original_body_and_return_layout(self):
        tree=ast.parse((ROOT/'dm/tools/patch_nso.py').read_text())
        f=next((n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='site_wrap'),None)
        self.assertIsNotNone(f,'production offline callable-body wrapper emitter missing')
        assert f is not None
        words=[];gates=[];patch=bytearray()
        def here(): return 0x10000+4*len(words)
        def emit(w,kind=None): words.append(w);patch.extend(struct.pack('<I',w))
        env: dict[str, Any] = dict(here=here,emit=emit,patch=patch, B=B,STP_PRE=STP_PRE,LDP_POST=LDP_POST,BLR=BLR,gates=gates,
                 MRS_TPIDRRO=MRS_TPIDRRO,LDRX=LDRX,ADDR=ADDR,ADRP=ADRP,fix=[],KEY_INDEX={'KGATE':3},KEY_PAGE_OFF=0x8000)
        names={'emit_key_addr','emit_slot_addr','emit_gate_call','site_wrap'}
        nodes: list[ast.stmt] = [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'production-site-wrap','exec'),env)
        start=env['site_wrap'](0x200,8,0xd10543ff)
        ret=gates[0][0]
        self.assertEqual(start,0x10000)
        self.assertEqual(ret,start+32) # runtime validator and CPU ABI adapter's exact layout
        self.assertEqual(gates,[(ret,'kh2wrap',8,0x200)])
        self.assertEqual(words[(ret-0x10000)//4:], [0xa8c17bfd,0xd65f03c0,0xd10543ff,B(ret+12,0x204)])
        # Original body must never branch back through the wrapped entry.
        self.assertNotEqual(words[-1],B(ret+12,0x200))

if __name__=='__main__':unittest.main()
