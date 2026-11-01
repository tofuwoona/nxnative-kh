# KH2 ripple encoder-coalescing experiment (isolated branch)

Branch `fix/kh2-ripple-review-v2` starts from the KH diagnostic checkout, not upstream `nxnative`. Do not merge or enable on the phone based on unit tests alone.

## Observed problem

The prior iPhone log has five >1,000-pass clusters; sampled frames have 1,475–1,482 Vulkan passes, with 1,408 uses of `vs=99eb434865f915a8 fs=8061129a84c22e46`. The same attachment texture/depth IDs recur across a 1,431-pass adjacent run in frame 6328, but the old log has no renderpass/framebuffer handles or actual Metal encoder IDs. There is no measured before/after GPU timing.

## Change (opt-in only)

`DM_VK_COALESCE_PASSES=1` is KH2-program-ID gated. Adjacent same-renderpass/framebuffer/area LOAD+STORE passes without resolves can reuse a Metal encoder. Buffer-backed and heap-placed render targets fail closed; every draw of a merged pass remains guarded for a shader texture feedback alias, and buffer resources cannot alias an accepted standalone private attachment. Query/blit/submit/clear boundaries still cut. Default is unchanged. One `[vk-diag] pass`, color/depth/stencil record per Vulkan pass survives a merge, with `rp`, `fb`, `merged`, `encoder`, mip/layer fields and actual encoder-start records. The earlier rejected upstream candidate did not provide these safeguards.

## Verification to date

- `bash dm/gfx/vk/tests/run_replay_coalesce.sh --red`: expected failure when coalescing disabled, at the actual replay-path encoder-count assertion.
- `bash dm/gfx/vk/tests/run_replay_coalesce.sh`: production `h_vkCmd*` recording/replay on real Mac Metal; 2 compatible LOAD+STORE passes -> 1 encoder; late texture feedback -> cut/resume; buffer-backed and heap-backed attachments -> no merge; final red pixel readback on first two; color, depth and stencil readback on a second merged fixture.
- Same fixture under `MTL_DEBUG_LAYER=1 MTL_SHADER_VALIDATION=1` emitted “Metal API Validation Enabled” and “Metal GPU Validation Enabled” and passed after initializing the test's default depth-stencil state.
- Predicate and source-safety checks passed; `check_pass_trace.py` streamed a synthetic merged fixture and two real 15-second Mac KH2 title-screen smoke logs. Baseline title-screen: 1,438 Vulkan passes / 2,157 actual encoder starts / 0 merges. Opt-in title-screen: 1,466 / 2,199 / **0 merges**. This validates log parity at title screen but **does not exercise the real ripple workload**.
- KH2 Mac host and signed iOS Release app 1.0.6 built; optimized metallib hash retained. 1.0.6 installed with bundled diagnostics and input trace, but no `DM_VK_COALESCE_PASSES` flag: **coalescing remains off**. Device was locked so the automatic launch was denied; the user must unlock/tap Play. Existing save container was not modified by these tests.

## Remaining release gates

1. Capture matched visible ripple scenes with coalescing off/on using isolated save state, same shader library/aspect/log settings. Report per-frame Vulkan pass count, merge hit/reject reasons, **actual encoder starts**, and separate submit counts. The opt-in test should not be enabled without baseline evidence and an explicit validation run.
2. Compare color/depth/stencil outputs on the real KH2 scene, not only the small synthetic fixture. Take short complete Metal GPU traces and compare GPU intervals and frame pacing separately. Run one opt-in safety capture with Metal API/Shader validation enabled before a non-validation performance run.
3. If GPU time does not improve or image output differs, leave the option disabled and investigate the game's repeated full-resolution draw workload rather than claiming the modeled encoder floor is a fix. The opt-in implementation has **no proven ripple FPS improvement**.
