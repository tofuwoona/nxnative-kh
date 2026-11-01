"""Source-level safety regression for the opt-in KH2 encoder coalescer.

Integration benchmarks (including pixels and GPU time) are separate gates;
this test prevents the specific blind spot found by Sonnet 5 from returning.
"""
from pathlib import Path
s=Path(__file__).resolve().parents[1].joinpath('hle_vk.m').read_text()
begin=s[s.index('static void begin_rp('):s.index('static void vk_trace_ubo(')]
assert 'vk_diag_pass(s, c, 1)' in begin.split('return;',1)[0], 'merged fast path skipped per-pass diagnostic records'
assert 'vk_diag_pass(s, c, 0)' in begin, 'normal path must share the exact logger'
assert 'vk_diag_encoder(s, "begin")' in begin, 'actual encoder creations must be counted, not modeled'
assert 'vk_coalesce_on()' in begin, 'feature gate must be cached and KH2-only'
assert 'vk_pass_can_coalesce(&s->pass_key, &next, pass_storage_safe(c))' in begin, 'reject alias-uncertain attachments'
pre=s[s.index('static int pre_draw('):s.index('static int vk_copy_trace(')]
assert 's->merged_pending = 0' not in pre, 'feedback check must remain armed for every draw in the merged pass'
assert 'pass_feedback_shader(s, s->pipe->vs)' in pre and 'pass_feedback_shader(s, s->pipe->fs)' in pre
assert 'vk_diag_encoder(s, "resume")' in s, 'resumed render encoder must also be counted'
print('source safety: per-Vulkan-pass logs, encoder counts and every-draw feedback guard present')
