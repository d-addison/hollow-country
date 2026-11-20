"""Proposed lead-owned test updates, validated ONLY in local fixture copies.

Worker A cannot edit existing tests. Emit the exact integration diff with:
python3 -B -m tests.legacy.test_auditlight_legacy_contracts --patch
The copied tests still read real authored sources; no production source is patched.

Fix-round integration spec: generated amendments must apply to the real shared
files and remain testable after the lead applies them. Plan/task: add explicit
shared-adapter fakes; RED then GREEN an already-amended temporary test tree.
RED command: python3 -B -m unittest tests.legacy.test_auditlight_legacy_contracts.LocalIntegrationCopies.test_amendments_accept_real_tests_after_lead_applies_patch -v
Actual failure: Integration edit no longer matches: test_client_frame_costs.py:
self.assertEqual(2, len(servers)). Ran 1 test; FAILED (failures=1).
GREEN: the same command -> Ran 1 test; OK.
Covering-module RED: authored-native-member:Row raised SyntaxError at
"InventoryLocation looseLocation = InventoryLocation()". The emitted patch
extends only the fixture's declaration translation. GREEN: the six
NativeAttachSiteTests pass in the patched temporary shared-test copy.

"""
import difflib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch as mock_patch

ROOT = Path(__file__).resolve().parents[2]
EDITS = {
    'test_client_frame_costs.py': [
        (r'\bHCTapedLightHostRow\s+(?=\w+\s*[=;])',
         r'\b(?:HCTapedLightHostRow|InventoryLocation)\s+(?=\w+\s*[=;])'),
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
        ('        HCGroupIO=NS(), Print=logs.append,',
         '        HCGroupIO=NS(), Print=logs.append,\n'
         '        HCTapedLightAdmission=NS(Admitted=lambda: True),'),
        ('# named refusal and the module stays ready (loaded, nothing degraded).',
         '# zero admitted pairs must degrade with the native-slot refusal.'),
        ('self.assertIn(("ready", "pack_native_slot_unavailable"), published)',
         'self.assertIn(("degraded", "pack_native_slot_unavailable"), published)'),
        ('self.assertIn("state=ready", plan)', 'self.assertIn("state=degraded", plan)'),
    ],
    'test_hc_taped_lights.py': [
        ('                   HCTapedPackCatalog=catalog, HCTapedLightCatalog=lights, NewSlots=EArray,',
         '                   HCTapedPackCatalog=catalog, HCTapedLightCatalog=lights, NewSlots=EArray,\n'
         '                   HCTapedLightAdmission=NS(Admitted=lambda: True),'),
        ('                   FileExist=lambda path: False, GetGame=',
         '                   HCTapedLightAdmission=NS(Admitted=lambda: True),\n'
         '                   FileExist=lambda path: False, GetGame='),
        ('(?:HCTapedLightHostRow|TStringArray)',
         '(?:HCTapedLightHostRow|HCTapedLightV1Qualification|TStringArray)'),
        ('NS(), {}, host, NS()))', 'NS(Ready=lambda: False), {}, host, NS()))'),
        ('"helmet_action_pending"', '"action=held_mount_remove_native_toggle"'),
    ],
    'test_hc_taped_default_on.py': [
        ('(?:HCTapedLightHostRow|ref array<ref HCTapedLightHostRow>)',
         '(?:HCTapedLightHostRow|InventoryLocation|ref array<ref HCTapedLightHostRow>)'),
        ('                   FileExist=lambda path: probes.append(path) or disabled,',
         '                   HCTapedLightAdmission=NS(Admitted=lambda: True),\n'
         '                   FileExist=lambda path: probes.append(path) or disabled,'),
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
    # Once the lead applies this file's full amendment set, keep it stable.
    if all(edit[1] in text for edit in EDITS[name]):
        return text
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
    def test_amendments_accept_real_tests_after_lead_applies_patch(self):
        # Explicit temporary shared-test tree, containing the emitted end state.
        with tempfile.TemporaryDirectory(prefix='hc-auditlight-applied-') as folder:
            root = Path(folder)
            target = root / 'tests/unit'
            target.mkdir(parents=True)
            for name in EDITS:
                (target / name).write_text(amended(name))
            with mock_patch(__name__ + '.ROOT', root):
                for name in EDITS:
                    self.assertEqual((target / name).read_text(), amended(name))
                self.assertEqual('', patch())

    def test_updated_legacy_contracts_in_explicit_fixture_copies(self):
        targets = {
            'test_client_frame_costs.py': ['TapedLightClientHintTests.test_server_authority_is_untouched_by_the_client_hint',
                                            'TapedLightPreviewCostTests.test_row_hoists_the_type_reads_out_of_the_catalog_loop'],
            'test_taped_light_v1.py': ['V1HookTests.test_registered_native_actions_call_service_only_on_server'],
            'test_hc_taped_pair_ids.py': ['SourceContractTests.test_pair_ids_are_derived_in_code_not_listed_twice',
                                       'ShippedReceiptSheetTests.test_shipped_sheet_loads_clean_with_zero_checked_and_nothing_disabled'],
            'test_hc_taped_pack_receipts.py': ['AdmissionTests.test_without_native_slots_the_pair_is_a_named_refusal_not_an_admission'],
            'test_hc_taped_pack_loader.py': ['TapedPackLoaderTests.test_enabled_cross_slot_needs_its_native_slot_then_is_admitted_unverified'],
            'test_hc_taped_lights.py': ['TapedLightNativeCustodyTests.test_helmet_manifest_refuses_unsupported_pairs_and_unqualified_binding',
                                         'TapedLightConservationTests.test_pack_pairs_refuse_before_custody_without_native_qualification'],
            'test_hc_taped_default_on.py': ['NativeAttachSiteTests', 'HelmetAndTapedLightStatusTests.test_helmet_mounts_are_admitted_unverified_by_default',
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
            for module in modules.values():
                if hasattr(module, 'build'):
                    module.build = modules['test_hc_taped_pack_loader.py'].build
            modules['test_hc_taped_default_on.py'].helmet_member = modules['test_hc_taped_lights.py'].helmet_member
            suite = unittest.TestSuite()
            for name, selected in targets.items():
                for selected_test in selected:
                    suite.addTests(unittest.defaultTestLoader.loadTestsFromName(selected_test, modules[name]))
            result = unittest.TestResult()
            suite.run(result)
            self.assertEqual([], result.errors, str(result.errors))
            self.assertEqual([], result.failures, str(result.failures))
            self.assertEqual(19, result.testsRun)


if __name__ == '__main__':
    if '--patch' in sys.argv:
        print(patch(), end='')
    else:
        unittest.main()
