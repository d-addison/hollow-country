"""#177 spec/plan/task: native missing scalar fields must not retain initializers.

Explicit synthetic DTOs and source snippets; offline checks are not engine proof.
Plan: correct shared JSON ports, lint loaded DTOs transitively, audit migrations.
The assigned brief is the specification; HC-11 owns shared trace documents.
"""
import unittest
from types import SimpleNamespace as N

from tests.unit.test_group_persistence import StoreHarness
from tools.validate import enforce_lint as lint


class ZeroFill(unittest.TestCase):
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
        from tests.unit.json_loader_port import json_fields_port
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
        from tests.unit.test_event_runtime import translate
        root = Path(__file__).resolve().parents[2]
        cases = (
            ('Infected/HCInfectedMemory.c', 'HCInfectedMemory',
             '{"Cells":[{"X":0,"Z":0}]}', '{"Cells":[{"X":0}]}'),
            ('Weather/HCVisualSeasonStore.c', 'HCVisualSeasonIO',
             '{"ElapsedSeconds":0,"RemainderSeconds":0}', '{"ElapsedSeconds":0}'),
            ('World/HCSettlementDecay.c', 'HCSettlementDecayStore',
             '{"Towns":[{"LastDay":0,"Ransack":0,"Barricades":0,"Remains":0,"Notices":0}]}',
             '{"Towns":[{"LastDay":0}]}'),
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
