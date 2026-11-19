"""#160/#177 wave 11 (w27-s005): retire HC-S005 baseline entries with real guards.

Native JsonFileLoader zero-fills a missing key and ignores the declared
initializer. Each case below loads an explicit synthetic fixture with the key
missing (json_loader_port decodes it zero-filled from the authored declarations)
and asserts the authored guard refuses it or restores the declared default.
Offline synthetic ports never establish DayZ behaviour; native runtime pending.

RED (2026-11-19, before the source edits):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_s005_wave11 -v
Ran 10 tests; FAILED (failures=8, errors=0), first line
AssertionError: True is not false : missing SchemaVersion must refuse before zero-fill
GREEN: same command after the edits, see the commit message.
"""
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit.json_loader_port import decode_json, json_fields_port
from tests.unit.test_event_runtime import translate as execute
from tests.unit.test_infected_admission import translate as member
from tests.unit import test_interior_catalog as measured_fixtures
from tests.unit.test_interior_measured_catalog import fixture as measured_fixture
from tools.validate import enforce_lint as lint
from tools.validate import enforce_source as es

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mods/HollowCountry/scripts'
XAI = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World'

RETIRED = {
    'HCEcologyMigrationSchedule.NextDueUtc', 'HCInfectedSnapshot.SchemaVersion',
    'HCInfectedLODConfig.HerdWorld', 'HCCellarSamplerClass.Disposition',
    'HCCellarSamplerClass.Reason', 'HCCellarSamplerData.Method',
    'HCInteriorCandidate.SlotId', 'HCSettlementState.Version',
    'HCXAILocalityCoverage.Refusal',
    # w28-s160: raw-key presence guard before the strict parse (tests.unit.test_hc_s160_final_burn).
    'HCInteriorMeasuredCatalogMeasuredProp.Index',
}


def text(relative):
    return (SCRIPTS / relative).read_text()


class MissingKeyGuards(unittest.TestCase):
    def present(self, relative):
        return execute(text(relative), 'HCFieldsPresent', {'HCJsonFields': json_fields_port()})

    def test_infected_journal_without_schema_version_is_refused(self):
        present = self.present('4_World/Infected/HCInfectedState.c')
        group = '{"Living":1,"Reserved":1,"AdoptionStage":0}'
        self.assertTrue(present('{"SchemaVersion":2,"Reserved":1,"Groups":[' + group + ']}'))
        self.assertTrue(present('{"SchemaVersion":2,"Reserved":0,"Groups":[]}'))
        snapshot = decode_json('{"Reserved":0,"Groups":[]}', 'HCInfectedSnapshot')
        self.assertEqual(0, snapshot.SchemaVersion, 'synthetic native zero-fill, not the -1 initializer')
        self.assertFalse(present('{"Reserved":0,"Groups":[]}'),
                         'missing SchemaVersion must refuse before zero-fill')

    def test_settlement_state_without_version_is_refused(self):
        present = self.present('4_World/World/HCSettlementDecay.c')
        town = '{"LastDay":-1,"Ransack":0,"Barricades":0,"Remains":0,"Notices":0}'
        self.assertTrue(present('{"Version":1,"Towns":[' + town + ']}'))
        self.assertFalse(present('{"Towns":[' + town + ']}'), 'missing Version must refuse')
        self.assertFalse(present('{"Version":1,"Towns":[' + town + ',{"LastDay":0}]}'))

    def test_lod_config_without_herd_world_is_refused_with_a_reason(self):
        store = text('4_World/Infected/LOD/HCInfectedLODStore.c')
        present = execute(store, 'HCFieldsPresent', {'HCJsonFields': json_fields_port()})
        self.assertTrue(present('{"SchemaVersion":1,"HerdWorld":"chernarusplus"}'))
        self.assertTrue(present('{"SchemaVersion":1,"HerdWorld":""}'), 'explicit empty is an operator choice')
        config = decode_json('{"SchemaVersion":1}', 'HCInfectedLODConfig')
        self.assertEqual('', config.HerdWorld, 'native zero-fill silently disables every herd seed')
        self.assertFalse(present('{"SchemaVersion":1}'), 'missing HerdWorld must refuse')
        load = store.split('static HCInfectedLODConfig Load(out string reason)', 1)[1].split('\n    }\n', 1)[0]
        self.assertRegex(load, r'HCFieldsPresent\(content\)')
        self.assertIn('lod.json missing HerdWorld', load)

    def test_legacy_interior_pilot_candidates_need_an_explicit_slot(self):
        present = self.present('4_World/Interiors/HCInteriorModule.c')
        row = '{"SlotId":0,"Type":"Land_House_1W01"}'
        self.assertTrue(present('{"SchemaVersion":1,"Candidates":[' + row + ']}'))
        self.assertFalse(present('{"SchemaVersion":1,"Candidates":[{"Type":"Land_House_1W01"}]}'),
                         'missing SlotId would alias slot 0')
        self.assertFalse(present('{"Candidates":[' + row + ',{"Type":"Land_House_1W01"}]}'))
        self.assertFalse(present(''), 'an empty re-read must not pass')

    def test_pending_locality_row_without_refusal_restores_the_declared_reason(self):
        from tests.unit.test_expansion_ai_adapter import A, Authored, declarations
        env = dict(A=A, Print=lambda line: None)
        declarations(env)
        source = (XAI / 'HCXAISites.c').read_text()
        parsed = es.Source(XAI / 'HCXAISites.c', source)
        store = next(c for c in parsed.classes if c.name == 'HCXAILocalitySave')
        code = source[store.offset:store.body_end + 1].replace('array<string> ', 'HCXAIStrings ')
        for field in ('Data', 'Fault', 'HCDirty'):
            code = re.sub(r'(?<![.\w])' + field + r'\b', 'this.' + field, code)
        code = code.replace(
            'JsonFileLoader<HCXAILocalityRotation>.LoadData(HCWorldStore.Read(path), this.Data, error)',
            'synthetic_load(this, path)')
        files = {'rotation': json.dumps({
            'SchemaVersion': 1, 'WorldName': 'chernarusplus', 'NextId': 'b', 'SelectionSerial': 2,
            'Rows': [
                {'LocalityId': 'a', 'NextSite': 0, 'LastSelected': 1, 'LastObserved': 0,
                 'PendingSinceSerial': 1, 'RetryAt': 0, 'Pending': True},
                {'LocalityId': 'b', 'NextSite': 0, 'LastSelected': 2, 'LastObserved': 2,
                 'PendingSinceSerial': 0, 'RetryAt': 0, 'Pending': False, 'Refusal': ''},
                {'LocalityId': 'c', 'NextSite': 0, 'LastSelected': 2, 'LastObserved': 0,
                 'PendingSinceSerial': 2, 'RetryAt': 0, 'Pending': True,
                 'Refusal': 'island_access_route_unreviewed'}]})}

        def load(job, path):
            job.Data = decode_json(files[path], 'HCXAILocalityRotation', A)
            return True
        env.update(synthetic_load=load, FileExist=lambda path: path in files,
                   HCXAIRules=N(Token=lambda value: bool(value)),
                   HCXAISiteRules=N(HCMaxCatalogRows=lambda: 64),
                   HCWorldStore=N(Read=lambda path: files[path]))
        restored = N(Data=None, Fault=False)
        self.assertTrue(Authored(code, env).call('HCRestore', restored, 'rotation', 'chernarusplus'))
        rows = {row.LocalityId: row for row in restored.Data.Rows}
        self.assertEqual('route_not_reviewed', rows['a'].Refusal,
                         'a pending row missing its reason keeps the declared default')
        self.assertEqual('', rows['b'].Refusal, 'an observed row keeps its empty reason')
        self.assertEqual('island_access_route_unreviewed', rows['c'].Refusal)

    def test_cellar_seed_missing_method_and_disposition_get_declared_defaults(self):
        data = text('4_World/Interiors/HCCellarSamplerData.c')
        self.assertIn('HCRestoreDeclaredDefaults', data, 'declared-default restore missing')
        sampler = text('4_World/Interiors/HCCellarSampler.c')
        self.assertIn('.HCRestoreDeclaredDefaults()', sampler, 'HCStart must call the restore')
        self.assertIn('m_Data.HCRestoreDeclaredMethod()', sampler)
        seed = decode_json('{"SchemaVersion":1,"WorldName":"chernarusplus","Classes":[{"BuildingClass":"Land_X"}]}',
                           'HCCellarSamplerData')
        row = seed.Classes[0]
        self.assertEqual(('', '', ''), (seed.Method, row.Disposition, row.Reason), 'synthetic zero-fill')
        restore_row = member(str(SCRIPTS / '4_World/Interiors/HCCellarSamplerData.c'),
                             'void HCRestoreDeclaredDefaults(', (), fields=('Disposition', 'Reason'),
                             DEFAULT_DISPOSITION='pending', DEFAULT_REASON='native_survey_pending')
        restore_row(row)
        self.assertEqual(('pending', 'native_survey_pending'), (row.Disposition, row.Reason))
        self.assertRegex(data, r'DEFAULT_METHOD = "ground-floor-owner-rays-3x3-clearance-v1";')
        restore_data = member(str(SCRIPTS / '4_World/Interiors/HCCellarSamplerData.c'),
                              'void HCRestoreDeclaredMethod(', (), fields=('Method',),
                              DEFAULT_METHOD='ground-floor-owner-rays-3x3-clearance-v1')
        restore_data(seed)
        self.assertEqual('ground-floor-owner-rays-3x3-clearance-v1', seed.Method)
        seed.Method = 'operator-method'
        restore_data(seed)
        self.assertEqual('operator-method', seed.Method)
        # An explicit authored refusal is never overwritten.
        row.Disposition, row.Reason = 'refused', 'inconsistent_measured_boxes'
        restore_row(row)
        self.assertEqual(('refused', 'inconsistent_measured_boxes'), (row.Disposition, row.Reason))

    def test_migration_schedule_zero_fill_is_refused_by_the_utc_range(self):
        schedule = decode_json('{"Id":"a","PopulationKind":1,"IntervalSeconds":600}', 'HCEcologyMigrationSchedule')
        self.assertEqual(0, schedule.NextDueUtc)
        valid = execute((SCRIPTS / '4_World/Ecology/HCEcologyMigrationRules.c').read_text(), 'UtcValid', {})
        self.assertFalse(valid(schedule.NextDueUtc), 'a missing NextDueUtc must read as invalid')
        declared = next(f for c in es.Source(SCRIPTS / '3_Game/Ecology/HCEcologyRuntimeData.c',
                        text('3_Game/Ecology/HCEcologyRuntimeData.c')).classes
                        if c.name == 'HCEcologyMigrationSchedule' for f in c.fields if f.name == 'NextDueUtc')
        self.assertEqual('', declared.initializer, 'no sentinel the native loader would erase')

    def test_missing_measured_prop_index_is_refused_before_native_parse(self):
        e, raw, calls, house, objects, candidate, profile = measured_fixture()
        path = '$profile:HollowCountry/measured-interiors/measured-record.json'
        record = json.loads(raw[path])
        for layout in record['Layouts']:
            del layout['Survey']['Props'][0]['Index']
        edited = measured_fixtures.encode(record).decode()
        profile['ExpectedRecordText'] = edited
        raw[path] = edited
        raw['$profile:HollowCountry/interiors-measured-profile.json'] = json.dumps(profile)
        e['MeasuredEnsureLoaded']()
        self.assertIsNone(e['s_Binding'])
        self.assertEqual(1, calls['parse'], 'only the profile may reach LoadData; the record is refused first')


class LintRetirement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.symbols = {f.symbol for f in lint.lint(es.mod_sources(ROOT)) if f.rule == 'HC-S005'}

    def test_guarded_stores_no_longer_rely_on_the_json_initializer(self):
        self.assertEqual(set(), self.symbols & RETIRED)


if __name__ == '__main__':
    unittest.main()
