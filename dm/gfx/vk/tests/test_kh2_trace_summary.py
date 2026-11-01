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

    def test_correctly_targeted_capture_matches_real_submits(self):
        # run402: DM_VK_UBOTRACE_MIN_SUBMIT was set from a real VPTRACE-discovered submit number
        # (not a stale/guessed frame-number value), so selected_ubo must be non-empty and must
        # include the world-geometry shader's three UBOs at the frame's own submit range.
        p = Path('/Users/tofu/.hermes/cache/scratch/kh2-wide-evidence/run402/run.log')
        if not p.exists(): self.skipTest('capture not available on this host')
        lines = p.read_text(errors='replace').splitlines()
        r = mod.summarize(lines, 2910)
        self.assertFalse(r['selected_ubo'] == [])
        keys_bindings = {(u['key'], u['values'].split()[0]) for u in r['selected_ubo']}
        self.assertIn(('d7a52a49f521f4f0', 'binding=2'), keys_bindings)
        self.assertIn(('d7a52a49f521f4f0', 'binding=3'), keys_bindings)
        self.assertIn(('d7a52a49f521f4f0', 'binding=4'), keys_bindings)

    def test_world_shader_binding2_binding4_are_camera_invariant_in_real_capture(self):
        # Across a confirmed ~90deg real camera turn (run402, frames 2910/2911, screenshots show
        # the view rotating from the bookshelf/desk wall to the computer-console wall while Sora's
        # position stays at the save point), the previously-hypothesized camera-matrix fields
        # (binding=2 "VPdiag", binding=4 "WorldViewdiag") never move off identity. This is a
        # disproof, not a confirmation: those bytes are not the camera's view/projection matrix.
        p = Path('/Users/tofu/.hermes/cache/scratch/kh2-wide-evidence/run402/run.log')
        if not p.exists(): self.skipTest('capture not available on this host')
        lines = p.read_text(errors='replace').splitlines()
        ubo = mod.summarize(lines, 2910)['selected_ubo'] + mod.summarize(lines, 2911)['selected_ubo']
        world = [u for u in ubo if u['key'] == 'd7a52a49f521f4f0']
        self.assertTrue(world)
        for u in world:
            if u['values'].startswith('binding=2'):
                self.assertIn('VPdiag=1,1,1,1', u['values'])
            if u['values'].startswith('binding=4'):
                self.assertIn('WorldViewdiag=1,1,1,1', u['values'])

if __name__ == '__main__': unittest.main()
