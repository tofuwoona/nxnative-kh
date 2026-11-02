#!/usr/bin/env python3
"""Execute production LauncherModel init/apply with a disposable defaults suite.
Only SwiftUI publication/binding are omitted; no app build or real prefs writes.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('launcher_settings', ROOT / 'dm/games/settings.py')
assert spec is not None and spec.loader is not None
settings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settings)


class LauncherRenderPreferences(unittest.TestCase):
    def test_diagnostic_rows_are_separate_default_off_program3_only(self):
        labels = {'DM_SAVE_TRACE': 'Save traces',
                  'DM_KH_INPUT_TRACE': 'Record controller inputs',
                  'DM_KH24_DIAG': 'Detailed render logging'}
        profiles = ROOT / 'dm/games/010090C022978000/direct-profiles'
        with tempfile.TemporaryDirectory(prefix='kh2-launcher-rows-') as tmp:
            with patch.object(settings.nacp, 'languages', return_value=['en-US']), patch.dict(os.environ, {'DM_GAMES_DIR': str(profiles), 'DM_GAMES_FIRST': '1', 'GFXAPI': 'vulkan'}):
                for profile in ('010090C022978003', '010090C022978001'):
                    rows = settings.build(profile, tmp, Path(tmp) / 'control.nacp')['settings']
                    for key, label in labels.items():
                        matches = [row for row in rows if row['env'] == key]
                        self.assertEqual(len(matches), int(profile.endswith('003')), key)
                        if matches:
                            self.assertEqual((matches[0]['kind'], matches[0]['default'], matches[0]['label']), ('toggle', '0', label))

    def test_real_model_preserves_explicit_values_and_ignores_removed_saved_key(self):
        source = (ROOT / 'dm/ios/Sources/Launcher.swift').read_text()
        structs = source[source.index('private struct Setting:'):source.index('private func info(')]
        model = source[source.index('private final class LauncherModel:'):source.index('private struct SettingRow:')]
        model = model.replace(': ObservableObject', '').replace('@Published ', '')
        model = '\n'.join(line for line in model.splitlines() if 'func binding(' not in line)
        test = r'''
let suite = "kh2-render-test." + UUID().uuidString
let defaults = UserDefaults(suiteName: suite)!
defer { defaults.removePersistentDomain(forName: suite) }
private let file = try JSONDecoder().decode(SettingsFile.self, from: Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1])))
let key = "DM_VK_COALESCE_PASSES", legacy = "DM_PRESERVE_FULL_HUD"
assert(!file.settings.contains { $0.env == legacy })
for saved in [nil, "0", "1"] as [String?] {
    defaults.removePersistentDomain(forName: suite)
    if let value = saved { defaults.set(value, forKey: "launcher." + key) }
    defaults.set("1", forKey: "launcher." + legacy)
    unsetenv(legacy); unsetenv(key); unsetenv("DM_ENV_FILE_KEYS")
    let model = LauncherModel(file.settings)
    assert(model.values[key] == (saved ?? "1"))
    model.apply()
    assert(String(cString: getenv(key)!) == (saved ?? "1"))
    assert(defaults.string(forKey: "launcher." + key) == (saved ?? "1"))
    assert(getenv(legacy) == nil, "removed saved option must not become an env override")
}
for value in ["0", "1"] {
    defaults.set(value == "0" ? "1" : "0", forKey: "launcher." + key)
    setenv("DM_ENV_FILE_KEYS", key, 1); setenv(key, value, 1)
    let model = LauncherModel(file.settings)
    assert(model.values[key] == value)
    model.apply()
    assert(String(cString: getenv(key)!) == value)
    assert(defaults.string(forKey: "launcher." + key) != value, "env-file choice must not rewrite saved value")
}
print("PASS actual LauncherModel: new default=1, saved 0/1 retained, env-file 0/1 wins, removed HUD saved key inert")
let diagnostics = ["DM_SAVE_TRACE", "DM_KH_INPUT_TRACE", "DM_KH24_DIAG"]
for key in diagnostics {
    for saved in [nil, "0", "1"] as [String?] {
        defaults.removePersistentDomain(forName: suite)
        for k in diagnostics { unsetenv(k) }
        unsetenv("DM_ENV_FILE_KEYS")
        if let value = saved { defaults.set(value, forKey: "launcher." + key) }
        let model = LauncherModel(file.settings)
        assert(model.values[key] == (saved ?? "0"))
        model.apply()
        assert(String(cString: getenv(key)!) == (saved ?? "0"))
        assert(defaults.string(forKey: "launcher." + key) == (saved ?? "0"))
        for other in diagnostics where other != key { assert(String(cString: getenv(other)!) == "0") }
    }
    for explicit in ["0", "1"] {
        defaults.set(explicit == "0" ? "1" : "0", forKey: "launcher." + key)
        setenv("DM_ENV_FILE_KEYS", key, 1); setenv(key, explicit, 1)
        let model = LauncherModel(file.settings)
        assert(model.values[key] == explicit)
        model.apply()
        assert(String(cString: getenv(key)!) == explicit)
        assert(defaults.string(forKey: "launcher." + key) != explicit)
    }
}
print("PASS actual LauncherModel: all three diagnostics default OFF, saved 0/1 retained independently, explicit 0/1 wins without rewriting preferences")
'''
        profiles = ROOT / 'dm/games/010090C022978000/direct-profiles'
        with tempfile.TemporaryDirectory(prefix='kh2-launcher-model-', dir=os.environ['TMPDIR']) as tmp:
            with patch.object(settings.nacp, 'languages', return_value=['en-US']), patch.dict(os.environ, {'DM_GAMES_DIR': str(profiles), 'DM_GAMES_FIRST': '1', 'GFXAPI': 'vulkan'}):
                data = settings.build('010090C022978003', tmp, Path(tmp) / 'control.nacp')
            path = Path(tmp)
            (path / 'launcher.json').write_text(json.dumps(data))
            (path / 'model.swift').write_text('import Foundation\n' + structs + model + test)
            subprocess.run(['swift', str(path / 'model.swift'), str(path / 'launcher.json')], check=True)


if __name__ == '__main__':
    unittest.main()
