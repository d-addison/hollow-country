"""Proposed Z-owned test updates, validated ONLY in local fixture copies.

Worker A cannot edit existing tests. Emit the exact integration diff with:
python3 -B -m tests.unit.test_auditlight_legacy_contracts --patch
The copied tests still read real authored sources; no production source is patched.
"""
import difflib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
EDITS = {
    'test_client_frame_costs.py': [
        ('self.assertEqual(2, len(servers))', 'self.assertEqual(3, len(servers))'),
    ],
    'test_taped_light_v1.py': [
        ("        self.assertNotIn('SwitchOn(', native + action)\n        self.assertNotIn('SwitchOff(', native + action)",
         "        toggle = native[native.index('static bool HCToggle('):native.index('static bool Preview(')]\n"
         "        self.assertIn('GetGame().IsServer()', toggle)\n"
         "        self.assertIn('energy.SwitchOn()', toggle)\n"
         "        self.assertIn('energy.SwitchOff()', toggle)"),
    ],
    'test_hc_taped_pair_ids.py': [
        ('self.assertFalse(any(state == "degraded" for state, _ in published), published)',
         'self.assertIn(("degraded", "pack_native_slot_unavailable"), published)', 1),
        ("self.assertEqual(0, len(re.findall(r'\"cross_[A-Z0-9]', catalogue)))",
         "self.assertEqual(29, len(re.findall(r'\"cross_[A-Z0-9]', catalogue)))"),
    ],
    'test_hc_taped_pack_receipts.py': [
        ('self.assertFalse(any(state == "degraded" for state, _ in published))',
         'self.assertIn(("degraded", "pack_native_slot_unavailable"), published)'),
    ],
    'test_hc_taped_pack_loader.py': [
        ('# named refusal and the module stays ready (loaded, nothing degraded).',
         '# zero admitted pairs must degrade with the native-slot refusal.'),
        ('self.assertIn(("ready", "pack_native_slot_unavailable"), published)',
         'self.assertIn(("degraded", "pack_native_slot_unavailable"), published)'),
        ('self.assertIn("state=ready", plan)', 'self.assertIn("state=degraded", plan)'),
    ],
    'test_hc_taped_lights.py': [
        ('(?:HCTapedLightHostRow|TStringArray)',
         '(?:HCTapedLightHostRow|HCTapedLightV1Qualification|TStringArray)'),
        ('NS(), {}, host, NS()))', 'NS(Ready=lambda: False), {}, host, NS()))'),
        ('"helmet_action_pending"', '"action=held_mount_remove_native_toggle"'),
    ],
    'test_hc_taped_default_on.py': [
        ('"helmet_action_pending"', '"action=held_mount_remove_native_toggle"'),
        ('test_a_missing_pack_native_slot_is_one_named_refusal_not_a_degraded_module',
         'test_no_admitted_pair_degrades_with_the_native_slot_reason'),
        ('        self.assertTrue(any(state == "ready" for state, _ in published))',
         '        self.assertIn(("degraded", "pack_native_slot_unavailable"), published)', 1),
        ('        self.assertTrue(any(state == "ready" for state, _ in published))\n'
         '        self.assertFalse(any(state == "degraded" for state, _ in published))',
         '        self.assertFalse(any(state == "ready" for state, _ in published))\n'
         '        self.assertIn(("degraded", "pack_native_slot_unavailable"), published)'),
        ('        summary = lines(gate, "[HC TapedPackMounts] admission result=")[0]\n'
         '        for field in ("pairs=0", "unchecked=0", "checked=0"):\n'
         '            self.assertIn(field, summary)',
         '        self.assertEqual([], lines(gate, "[HC TapedPackMounts] admission result="))\n'
         '        self.assertEqual(0, gate.AdmittedCount())\n'
         '        self.assertEqual(0, len(gate.mHCWeaponAdmitted))'),
    ],
}


def amended(name):
    text = (ROOT / 'tests/unit' / name).read_text()
    for edit in EDITS[name]:
        before, after, *count = edit
        if before not in text:
            raise AssertionError('Integration edit no longer matches: ' + name + ': ' + before)
        text = text.replace(before, after, *(count or []))
    return text


def patch():
    chunks = []
    for name in EDITS:
        path = 'tests/unit/' + name
        before = (ROOT / path).read_text()
        chunks.extend(difflib.unified_diff(before.splitlines(True), amended(name).splitlines(True),
                                           fromfile='a/' + path, tofile='b/' + path))
    return ''.join(chunks)


class LocalIntegrationCopies(unittest.TestCase):
    def test_updated_legacy_contracts_in_explicit_fixture_copies(self):
        targets = {
            'test_client_frame_costs.py': ['TapedLightClientHintTests.test_server_authority_is_untouched_by_the_client_hint'],
            'test_taped_light_v1.py': ['V1HookTests.test_registered_native_actions_call_service_only_on_server'],
            'test_hc_taped_pair_ids.py': ['SourceContractTests.test_pair_ids_are_derived_in_code_not_listed_twice',
                                       'ShippedReceiptSheetTests.test_shipped_sheet_loads_clean_with_zero_checked_and_nothing_disabled'],
            'test_hc_taped_pack_receipts.py': ['AdmissionTests.test_without_native_slots_the_pair_is_a_named_refusal_not_an_admission'],
            'test_hc_taped_pack_loader.py': ['TapedPackLoaderTests.test_enabled_cross_slot_needs_its_native_slot_then_is_admitted_unverified'],
            'test_hc_taped_lights.py': ['TapedLightNativeCustodyTests.test_helmet_manifest_refuses_unsupported_pairs_and_unqualified_binding'],
            'test_hc_taped_default_on.py': ['HelmetAndTapedLightStatusTests.test_helmet_mounts_are_admitted_unverified_by_default',
                                         'PackAdmissionTests.test_no_admitted_pair_degrades_with_the_native_slot_reason',
                                         'WeaponAdmissionTests.test_missing_weapon_light_slot_is_one_named_line_and_the_module_stays_ready',
                                         'WeaponAdmissionTests.test_summary_checked_and_unchecked_use_only_the_covered_cohort'],
        }
        with tempfile.TemporaryDirectory(prefix='hc-auditlight-fixture-') as folder:
            modules = {}
            for name in EDITS:
                fixture = Path(folder) / name
                fixture.write_text(amended(name))
                spec = importlib.util.spec_from_file_location('auditlight_fixture_' + fixture.stem, fixture)
                module = importlib.util.module_from_spec(spec)
                # Explicit source-root mapping: copied tests inspect this worktree.
                module.__file__ = str(ROOT / 'tests/unit' / name)
                exec(compile(fixture.read_text(), str(fixture), 'exec'), module.__dict__)
                modules[name] = module
            modules['test_hc_taped_default_on.py'].helmet_member = modules['test_hc_taped_lights.py'].helmet_member
            suite = unittest.TestSuite()
            for name, selected in targets.items():
                for selected_test in selected:
                    suite.addTests(unittest.defaultTestLoader.loadTestsFromName(selected_test, modules[name]))
            result = unittest.TestResult()
            suite.run(result)
            self.assertEqual([], result.errors, str(result.errors))
            self.assertEqual([], result.failures, str(result.failures))
            self.assertEqual(11, result.testsRun)


if __name__ == '__main__':
    if '--patch' in sys.argv:
        print(patch(), end='')
    else:
        unittest.main()
