#!/usr/bin/env python3
"""Guard shared layout wiring and launcher exposure; runtime C tests do geometry."""
import pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'dm/games'))
import settings
rows={c[0]:c for _,c in settings.rows()}
assert 'DM_PRESERVE_FULL_HUD' in rows, 'Missing functional launcher option'
r=rows['DM_PRESERVE_FULL_HUD']
assert r[3]=='0' and r[4]=='game:010090C022978003'
assert 'temporary' in r[6].lower() and 'not true widescreen' in r[6].lower()
for f in ['dm/host/front_mac.m','dm/ios/Sources/front_ios.m','dm/ios/Sources/DmGamepad.m']:
    text=(ROOT/f).read_text()
    assert 'dm_aspect_frame(' in text, f+' must use shared picture rectangle'
    if 'Gamepad' in f or 'front_mac' in f:
        assert 'dm_aspect_touch(' in text, f+' must use matching input mapping'
assert 'safeAreaInsets' in (ROOT/'dm/ios/Sources/front_ios.m').read_text()
assert 'safeAreaInsets' in (ROOT/'dm/ios/Sources/DmGamepad.m').read_text()
assert 'DM_VK_COALESCE_PASSES' in rows, 'Existing coalescing toggle lost'
print('PASS launcher default/profile gate, explicit temporary label, shared layout/input wiring, coalescing toggle retained')
