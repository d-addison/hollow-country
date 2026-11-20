"""#177 spec/plan/task: native missing scalar fields must not retain initializers.

Explicit synthetic DTOs and source snippets; offline checks are not engine proof.
Plan: correct shared JSON ports, lint loaded DTOs transitively, audit migrations.
The assigned brief is the specification; HC-11 owns shared trace documents.

Wave-8 #177 RED (2026-11-19):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_zero_fill.ZeroFill.test_sentinel_guards_must_distinguish_absence_from_minus_one test_hc_zero_fill.ZeroFill.test_nonempty_string_defaults_need_typed_guards_and_keep_parser_parity test_hc_faction_outcomes -v
Actual: FAILED (failures=8), including
AssertionError: Lists differ: ['HCSynthetic.Remaining'] != []
AssertionError: Items in the first set but not the second: HCSynthetic.Label, HCSynthetic.Space
AssertionError: Missing authored method HCFieldsPresent
GREEN (same cases plus all affected readers/checks):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_zero_fill test_hc_faction_outcomes test_enforce_lint test_script_syntax test_enforce_locals test_script_identifiers test_hygiene test_enforce_source_parity test_hc_claim_round2 test_hc_locality_rotation test_taped_light_v1_evidence -v
Actual: Ran 130 tests in 25.504s; OK.
python3 -B -m tools.validate.enforce_lint --no-native
Actual: enforce_lint: pass findings=138 new=0 stale=0 native=no (HC-S005 total=17).
Four temporary infected baselines await parallel-owner reconciliation. Territory
raw-key rejection is authored/tested; HCFactionConflict load wiring belongs to
the lead. No offline check proves that runtime path or native JSON behavior.
"""
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace as N

from tests.legacy.test_group_persistence import StoreHarness
from tools.validate import enforce_lint as lint
from tools.validate import enforce_source as es


class ZeroFill(unittest.TestCase):
    def test_sentinel_guards_must_distinguish_absence_from_minus_one(self):
        prefix = 'mods/HollowCountry/scripts/4_World/'
        dto = 'class HCSynthetic { int Remaining = -1; }'
        load = 'class HCReader { void Read(string text) { HCSynthetic row; string error; JsonFileLoader<HCSynthetic>.LoadData(text, row, error); } }'
        def findings(check, helper=False):
            if helper:
                guard = ('class HCGuard { static bool Valid(int count) { return ' + check + '; } '
                         'bool Row(HCSynthetic row) { return Valid(row.Remaining); } }')
            else:
                guard = 'class HCGuard { bool Valid(HCSynthetic row) { return ' + check + '; } }'
            return [f.symbol for f in lint.lint_texts(
                {prefix+'Data.c': dto, prefix+'Read.c': load, prefix+'Guard.c': guard})
                if f.rule == 'HC-S005']
        for check in ('row.Remaining > 0', 'row.Remaining >= 1', '0 < row.Remaining',
                      '1 <= row.Remaining', 'row.Remaining != 0', 'row.Remaining < 1',
                      'row.Remaining >= 0', 'row.Remaining < 0'):
            with self.subTest(check=check):
                self.assertEqual(['HCSynthetic.Remaining'], findings(check))
                self.assertEqual(['HCSynthetic.Remaining'], findings(check.replace('row.Remaining', 'count'), True))
        for check in ('row.Remaining == 0', 'row.Remaining != -1', 'row.Remaining == -1',
                      '0 == row.Remaining', '-1 != row.Remaining', '-1 == row.Remaining'):
            with self.subTest(check=check):
                self.assertEqual([], findings(check))
                self.assertEqual([], findings(check.replace('row.Remaining', 'count'), True))
        self.assertEqual([], findings('HCJsonFields.Every("synthetic", "Remaining", 3)'))

    def test_nonempty_string_defaults_need_typed_guards_and_keep_parser_parity(self):
        prefix = 'mods/HollowCountry/scripts/4_World/'
        # Synthetic escaped quotes, punctuation, comments and whitespace literals.
        dto = r'''class HCSynthetic {
            string Label = "default; } \\\" quote";
            string Blank = /* "comment is not an initializer" */ "";
            string Space = " "; // a nonempty initializer, too
            static const string Fixed = "constant";
        }'''
        load = 'class HCReader { void Read(string text) { HCSynthetic row; string error; JsonFileLoader<HCSynthetic>.LoadData(text, row, error); } }'
        files = {prefix+'Data.c': dto, prefix+'Read.c': load}
        parsed = es.Source(prefix+'Data.c', dto).classes[0].fields
        self.assertEqual(r'"default; } \\\" quote"', parsed[0].string_initializer)
        self.assertEqual('""', parsed[1].string_initializer)
        self.assertEqual('" "', parsed[2].string_initializer)
        self.assertEqual({'HCSynthetic.Label', 'HCSynthetic.Space'},
                         {f.symbol for f in lint.lint_texts(files) if f.rule == 'HC-S005'})
        for check in ('row.Label == ""', 'row.Label != ""', 'row.Label.Length() < 1',
                      'row.Label.Length() == 0', 'row.Label == "default"',
                      'HCJsonFields.Has(text, "Label")'):
            with self.subTest(check=check):
                guard = 'class HCGuard { bool Valid(HCSynthetic row, string text) { return ' + check + '; } }'
                self.assertEqual(['HCSynthetic.Space'], [f.symbol for f in lint.lint_texts(
                    dict(files, **{prefix+'Guard.c': guard})) if f.rule == 'HC-S005'])

        # Reparse every real authored file with only masked text available for
        # initializer recovery: the pre-change structural definitions must match.
        root = Path(__file__).resolve().parents[2]
        sources = es.mod_sources(root)
        self.assertTrue(sources)
        def definitions(source):
            return (source.code, source.directives, source.typedefs, source.enums, source.parse_issues,
                    [(c.name, c.base, c.modded, c.offset, c.body_start, c.body_end,
                      [(f.name, f.type, f.modifiers, f.initializer, f.offset) for f in c.fields]) for c in source.classes],
                    [(m.name, m.return_type, m.modifiers, m.params, m.offset, m.body_start, m.body_end)
                     for m in source.methods], source.signatures, source.enum_blocks)
        original_members = es.Source._members
        def masked_members(source, definition):
            with patch.object(source, 'text', source.code):
                original_members(source, definition)
        for source in sources:
            with self.subTest(path=source.rel), patch.object(es.Source, '_members', masked_members):
                before = es.Source(source.path, source.text, root, source.mod)
                self.assertEqual(definitions(before), definitions(source))

    def test_missing_scalars_are_zero_and_loaded_initializers_require_a_guard(self):
        port = StoreHarness()
        port.rules['Synthetic'] = lambda: N(Version=1, Scale=2.5, Enabled=True, Label='default')
        decoded = port.decode('{}', 'Synthetic')
        self.assertEqual(0, decoded.Version, 'missing native int must be zero, not initializer 1')
        self.assertEqual(0.0, decoded.Scale)
        self.assertIs(False, decoded.Enabled)
        self.assertEqual('', decoded.Label)
        explicit = port.decode('{"Version":3,"Scale":1.5,"Enabled":true,"Label":"operator"}', 'Synthetic')
        self.assertEqual((3, 1.5, True, 'operator'),
                         (explicit.Version, explicit.Scale, explicit.Enabled, explicit.Label))

        prefix = 'mods/HollowCountry/scripts/4_World/'
        dto = 'class HCSynthetic { int Version = 1; float Scale = 2.5; bool Enabled = true; }'
        load = 'class HCReader { bool Read(string text) { HCSynthetic value; string error; return JsonFileLoader<HCSynthetic>.LoadData(text, value, error); } }'
        findings = lint.lint_texts({prefix+'Data.c': dto, prefix+'Read.c': load})
        self.assertEqual({'HCSynthetic.Version', 'HCSynthetic.Scale', 'HCSynthetic.Enabled'},
                         {f.symbol for f in findings if f.rule == 'HC-S005'})
        guards = '''class HCGuard {
            bool Valid(HCSynthetic value) {
                if (value.Version == 0) { value.Version = 1; }
                if (value.Scale < 1) { return false; }
                if (!value.Enabled) { return false; }
                return true;
            }
        }'''
        self.assertEqual([], [f for f in lint.lint_texts(
            {prefix+'Data.c': dto, prefix+'Read.c': load, prefix+'Guard.c': guards})
            if f.rule == 'HC-S005'])
        # Unloaded classes, constants and native-zero initializers are irrelevant.
        self.assertEqual([], [f for f in lint.lint_texts({prefix+'Only.c': dto}) if f.rule == 'HC-S005'])
        nested = 'class HCEnvelope { ref HCSynthetic Child; } class HCR { bool Read(string path) { HCEnvelope row; return HCGroupJson<HCEnvelope>.Load(path, 100, row); } }'
        self.assertEqual(3, len([f for f in lint.lint_texts(
            {prefix+'Data.c': dto, prefix+'Nested.c': nested}) if f.rule == 'HC-S005']))

        array_load = 'class HCEnvelope { ref array<ref HCSynthetic> Rows; } class HCR { bool Read(string path) { HCEnvelope row; return HCGroupJson<HCEnvelope>.Load(path, 100, row); } }'
        self.assertEqual(3, len([f for f in lint.lint_texts(
            {prefix+'Data.c': dto, prefix+'Array.c': array_load}) if f.rule == 'HC-S005']))
        unrelated = 'class HCOther { int Version; bool Valid(HCOther value) { return value.Version == 1; } }'
        self.assertEqual(3, len([f for f in lint.lint_texts(
            {prefix+'Data.c': dto, prefix+'Read.c': load, prefix+'Other.c': unrelated}) if f.rule == 'HC-S005']))
        negative = 'class HCSynthetic { int Version = -1; bool Valid() { return Version >= 0; } }'
        self.assertEqual(1, len([f for f in lint.lint_texts(
            {prefix+'Data.c': negative, prefix+'Read.c': load}) if f.rule == 'HC-S005']))
        scalar_findings = [f for f in findings if f.rule == 'HC-S005']
        reviewed = lint.baseline_from(scalar_findings, 'explicit synthetic review')
        self.assertEqual(([], []), lint.compare(scalar_findings, reviewed, False))
        self.assertEqual(3, len(lint.compare([], reviewed, False)[1]))

        # Execute the shared presence scanner: a value/nested key cannot claim
        # an operator's top-level key; escaped JSON names must still count.
        from tests.legacy.json_loader_port import json_fields_port
        api = json_fields_port()
        self.assertTrue(api.Has('{"Enabled":false}', 'Enabled'))
        self.assertTrue(api.Has('{"\\u0045nabled":false}', 'Enabled'))
        self.assertFalse(api.Has('{"Nested":{"Enabled":true},"Value":"Enabled"}', 'Enabled'))
        self.assertTrue(api.Every('{"Rows":[{"Sequence":0},{"Sequence":1}]}', 'Sequence', 3))
        self.assertFalse(api.Every('{"Rows":[{"Sequence":0},{}]}', 'Sequence', 3))
        self.assertTrue(api.Every('{"Rows":[{"CreatorId":"a","Color":0},{"Visit":1}]}', 'Color', 3, 'CreatorId'))
        self.assertFalse(api.Every('{"Rows":[{"CreatorId":"a"}]}', 'Color', 3, 'CreatorId'))

        # Persisted zero is legitimate, but absent negative sentinels must not
        # silently become a new origin, spring clock or already-visited town.
        from pathlib import Path
        from tests.legacy.test_event_runtime import translate
        root = Path(__file__).resolve().parents[2]
        cases = (
            ('Infected/HCInfectedMemory.c', 'HCInfectedMemory',
             '{"Cells":[{"X":0,"Z":0}]}', '{"Cells":[{"X":0}]}'),
            ('Weather/HCVisualSeasonStore.c', 'HCVisualSeasonIO',
             '{"ElapsedSeconds":0,"RemainderSeconds":0}', '{"ElapsedSeconds":0}'),
            ('World/HCSettlementDecay.c', 'HCSettlementDecayStore',
             '{"Version":1,"Towns":[{"LastDay":0,"Ransack":0,"Barricades":0,"Remains":0,"Notices":0}]}',
             '{"Version":1,"Towns":[{"LastDay":0}]}'),
            ('Groups/HCGroupStore.c', 'HCGroupStore',
             '{"Groups":[{"Markers":[{"CreatorId":"a","Color":0}]}]}',
             '{"Groups":[{"Markers":[{"CreatorId":"a"}]}]}'),
            ('Vehicles/HCWreckSalvage.c', 'HCWreckSalvageModule',
             '{"Rows":[{"Budget":0,"Left":0}]}', '{"Rows":[{"Budget":0}]}'),
            ('Scenes/HCSceneChains.c', 'HCSceneChains',
             '{"Chains":[{"Stages":[{"DelaySeconds":0}]}]}',
             '{"Chains":[{"Stages":[{}]}]}'),
        )
        for path, kind, complete, missing in cases:
            with self.subTest(store=kind):
                source = (root / 'mods/HollowCountry/scripts/4_World' / path).read_text()
                self.assertIn('static bool HCFieldsPresent(string text)', source)
                valid = translate(source, 'HCFieldsPresent', {'HCJsonFields': api}, kind)
                self.assertTrue(valid(complete))
                self.assertFalse(valid(missing))


if __name__ == '__main__':
    unittest.main()
