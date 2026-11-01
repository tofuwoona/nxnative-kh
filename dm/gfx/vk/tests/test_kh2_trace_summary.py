import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('kh2_trace_summary', Path(__file__).with_name('kh2_trace_summary.py'))
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class TraceSummaryTests(unittest.TestCase):
    def test_record_boundaries_and_attachments(self):
        lines = ['[dm] [vk] [VPTRACE] frame=3000 submit=4316 target=1920x1080 viewport=0,0 vs=abc fs=def blend=1 rgb=1/0/0 mask=0xf',
                 '[dm] [vk] [VPTRACE]   dest_att0=0xabc',
                 '[dm] [vk] [VPTRACE]   depth=0xd format=260 load=1 test=1 op=7 write=0',
                 '[dm] [vk] [VPTRACE]   fs_src_tex[0]=0x7 size=256x256 kind=t',
                 '[dm] [vk] [UBOTRACE] submit=4316 key=abc binding=3 matrix=2',
                 '[dm] [vk] [VPTRACE] frame=3001 submit=4317 target=256x256 viewport=0,0 vs=aaa fs=bbb blend=0 rgb=1/0/0 mask=0xf',
                 '[dm] [vk] [VPTRACE]   dest_att0=0xother']
        r = mod.summarize(lines, 3000)
        self.assertEqual(r['target_counts'], {'1920x1080': 1})
        self.assertEqual(r['records_detail'][0]['attachment'], '0xabc')
        self.assertEqual(r['records_detail'][0]['textures'], [{'attachment': '0x7', 'size': '256x256'}])
        self.assertEqual(r['selected_ubo'][0]['values'], 'binding=3 matrix=2')
        self.assertFalse(r['cap_reached'])

    def test_real_gameplay_capture_is_truncated(self):
        p = Path('/Users/tofu/.hermes/cache/scratch/kh2-wide-evidence/run220/run.log')
        if not p.exists(): self.skipTest('capture not available on this host')
        r = mod.summarize(p.read_text(errors='replace').splitlines(), 3000)
        self.assertTrue(r['cap_reached'])
        self.assertIn('1920x1080', r['target_counts'])
        self.assertIn('256x256', r['target_counts'])
        self.assertEqual(r['selected_ubo'], [])  # submit 3000, actual frame-3000 submit ~4316

if __name__ == '__main__': unittest.main()
