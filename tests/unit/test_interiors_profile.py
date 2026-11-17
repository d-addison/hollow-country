"""Interior data pack generator, validator and profile installer.

The shipped pack carries ONE natively observed house (run 060 pose) and marks every
other component pending-measurement. Room/measured-record fixtures below are explicitly
SYNTHETIC, exist only to exercise validation/installation control flow in temporary
directories, and never prove DayZ behaviour, fit, rooms or native acceptance.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest import mock

from tests.unit import test_interior_catalog as measured_fixtures
from tools.package import interiors_profile as ip

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / 'mission/hollow-country/interiors'
HOUSE = {'position': [1598.0286865234375, 304.5144348144531, 8970.615234375],
         'orientation': [15.041482925415039, 0.0, 0.0]}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def snapshot(root):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root).as_posix()
        result[rel] = None if path.is_dir() else path.read_bytes()
    return result


class TempCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hc-synthetic-interiors-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def pack(self, name='pack'):
        target = self.root / name
        serial = 1
        while target.exists():
            serial += 1
            target = self.root / f'{name}-{serial}'
        shutil.copytree(PACK, target)
        return target

    def profile(self, name='profiles'):
        target = self.root / name / 'HollowCountry'
        target.mkdir(parents=True)
        return target


class RuleMirrorTests(unittest.TestCase):
    def test_quantize_yaw_and_transform_key_follow_the_float32_enforce_rules(self):
        self.assertEqual(ip.quantize(1598.0286865234375), 159803)
        self.assertEqual(ip.quantize(-0.004), 0)
        self.assertEqual(ip.yaw(15.041482925415039), 1504)
        self.assertEqual(ip.yaw(-38.2499), 32175)
        self.assertEqual(ip.transform_key(HOUSE['position'], HOUSE['orientation']), '159803_30451_897062_1504_0_0')

    def test_layout_index_is_the_enforce_integer_mix(self):
        # (159803 % 1009)*31 + (30451 % 1009)*17 + (897062 % 1009)*13 + 1504 + seed, mod 3
        mixed = (159803 % 1009) * 31 + (30451 % 1009) * 17 + (897062 % 1009) * 13 + 1504 + 7
        self.assertEqual(ip.layout_index(159803, 30451, 897062, 1504, 7), mixed % 3)

    def test_instance_and_storage_identities_are_derived_not_invented(self):
        cand = {'SlotId': 0, 'Type': 'Land_House_1W01', 'Position': HOUSE['position'], 'Orientation': HOUSE['orientation']}
        self.assertEqual(ip.instance_id(cand, 3), 'chernarusplus_130164289_s1_e3_Land_House_1W01_159803_30451_897062_1504_0_0_d0')
        self.assertTrue(ip.instance_id(cand, 3) + '_storage_v1')

    def test_number_text_is_float32_exact_and_native_parser_safe(self):
        for value in (1598.0286865234375, -4.994536399841309, 0.0, -0.0, 15.041482925415039, 0.25, 8970.615234375):
            text = ip.number_text(value)
            self.assertEqual(f32(float(text)), f32(value))
            self.assertLessEqual(len(text), 32)
            self.assertNotIn('e', text.lower())
            self.assertIn('.', text)
        self.assertEqual(ip.number_text(-0.0), '0.0')


class ShippedPackTests(TempCase):
    def test_shipped_pack_validates_and_reports_exactly_the_pending_components(self):
        report = ip.validate(PACK)
        self.assertEqual(report['errors'], [])
        self.assertEqual({p['id']: p['state'] for p in report['pending']},
                         {'measured-interiors': 'pending-measurement',
                          'infected-production-rooms': 'pending-measurement'})
        for row in report['pending']:
            self.assertTrue(row['needs'])

    def test_interiors_json_matches_the_enforce_config_schema(self):
        data = json.loads((PACK / 'interiors.json').read_text())
        self.assertEqual(list(data), ['SchemaVersion', 'MapName', 'Build', 'Epoch', 'Seed', 'InitializeNewEpoch',
                                      'MigrateLegacyJournal', 'DiagnosticPlacementTrial', 'DiagnosticSearchTrial',
                                      'Candidates'])
        self.assertEqual((data['SchemaVersion'], data['MapName'], data['Build']), (1, 'chernarusplus', '1.30.164289'))
        self.assertTrue(1 <= data['Epoch'] <= 899999 and 1 <= data['Seed'] <= 1000000)
        self.assertIs(data['DiagnosticPlacementTrial'], False)
        self.assertIs(data['DiagnosticSearchTrial'], False)
        self.assertIs(data['MigrateLegacyJournal'], False)
        self.assertEqual(len(data['Candidates']), 1)
        cand = data['Candidates'][0]
        self.assertEqual(list(cand), ['SlotId', 'Type', 'Position', 'Orientation'])
        self.assertEqual((cand['SlotId'], cand['Type']), (0, 'Land_House_1W01'))

    def test_candidate_pose_is_the_float32_exact_native_observation(self):
        cand = json.loads((PACK / 'interiors.json').read_text())['Candidates'][0]
        self.assertEqual([f32(v) for v in cand['Position']], [f32(v) for v in HOUSE['position']])
        self.assertEqual([f32(v) for v in cand['Orientation']], [f32(v) for v in HOUSE['orientation']])
        self.assertEqual(cand['Orientation'][1:], [0.0, 0.0])

    def test_pack_manifest_derives_identities_and_pins_every_file(self):
        manifest = json.loads((PACK / 'pack.json').read_text())
        data = json.loads((PACK / 'interiors.json').read_text())
        self.assertEqual(manifest['files'], {'interiors.json': sha((PACK / 'interiors.json').read_bytes())})
        (row,) = manifest['instances']
        iid = ip.instance_id(data['Candidates'][0], data['Epoch'])
        self.assertEqual(row['instance_id'], iid)
        self.assertEqual(row['storage_site_id'], iid + '_storage_v1')
        self.assertIn(row['layout_id'], {'family-pantry-v1', 'family-storage-v1', 'ransacked-storage-v1'})
        self.assertEqual(manifest['runtime_acceptance'], 'pending')

    def test_regeneration_is_byte_identical(self):
        pack = self.pack()
        before = snapshot(pack)
        ip.generate(pack)
        self.assertEqual(snapshot(pack), before)

    def test_evidence_is_a_small_derived_record_without_paths(self):
        raw = (PACK / 'evidence/house-candidates.json').read_bytes()
        self.assertLess(len(raw), 4096)
        for name in ('pack.json', 'pack-profile.json', 'interiors.json', 'evidence/house-candidates.json'):
            text = (PACK / name).read_text()
            for marker in ('/home/', '/mnt/', 'C:\\', 'D:\\', '\\\\'):
                self.assertNotIn(marker, text)


class ConfigValidationTests(TempCase):
    def mutate(self, edit, name='interiors.json'):
        pack = self.pack()
        data = json.loads((pack / name).read_text())
        edit(data)
        (pack / name).write_text(json.dumps(data, indent=2) + '\n')
        return pack

    def rejects(self, edit, name='interiors.json'):
        report = ip.validate(self.mutate(edit, name))
        self.assertTrue(report['errors'], 'mutation was accepted')
        return report

    def test_hash_pin_catches_any_edit(self):
        report = self.rejects(lambda d: d.update(Seed=d['Seed'] + 1))
        self.assertTrue(any('sha256' in e for e in report['errors']))

    def test_schema_rejections(self):
        edits = (lambda d: d.update(SchemaVersion=2), lambda d: d.update(MapName='enoch'),
                 lambda d: d.update(Build='1.29.0'), lambda d: d.update(Epoch=0), lambda d: d.update(Epoch=900000),
                 lambda d: d.update(Seed=0), lambda d: d.update(Seed=1000001),
                 lambda d: d.update(DiagnosticPlacementTrial=True), lambda d: d.update(DiagnosticSearchTrial=True),
                 lambda d: d.update(MigrateLegacyJournal=True), lambda d: d.update(Candidates=[]),
                 lambda d: d.update(Surplus=1), lambda d: d.pop('Seed'))
        for edit in edits:
            with self.subTest(edit=edit):
                self.rejects(edit)

    def test_candidate_rejections(self):
        edits = (lambda d: d['Candidates'][0].update(Type='Land_House_2W01'),
                 lambda d: d['Candidates'][0].update(SlotId=12), lambda d: d['Candidates'][0].update(SlotId=-1),
                 lambda d: d['Candidates'][0].update(Orientation=[15.0, 1.0, 0.0]),
                 lambda d: d['Candidates'][0].update(Orientation=[15.0, 0.0, 2.0]),
                 lambda d: d['Candidates'][0].update(Orientation=[361.0, 0.0, 0.0]),
                 lambda d: d['Candidates'][0].update(Position=[20001.0, 0.0, 0.0]),
                 lambda d: d['Candidates'][0].update(Position=[1.0, 2.0]),
                 lambda d: d['Candidates'][0].update(Extra=True))
        for edit in edits:
            with self.subTest(edit=edit):
                self.rejects(edit)

    def test_candidate_must_match_native_evidence_exactly(self):
        report = self.rejects(lambda d: d['Candidates'][0].update(Position=[1598.5, 304.5144348144531, 8970.615234375]))
        self.assertTrue(any('evidence' in e for e in report['errors']))

    def test_duplicate_slot_and_duplicate_quantised_pose_are_rejected(self):
        def dup(d):
            d['Candidates'].append(dict(d['Candidates'][0]))
        self.rejects(dup)

        def twin(d):
            twin = dict(d['Candidates'][0], SlotId=1)
            d['Candidates'].append(twin)
        self.rejects(twin)

    def test_unlisted_and_unsafe_pack_members_are_rejected(self):
        pack = self.pack()
        (pack / 'extra.json').write_text('{}')
        self.assertTrue(ip.validate(pack)['errors'])
        pack = self.pack('pack2')
        (pack / 'evidence/vanilla-dump.txt').write_text('x')
        self.assertTrue(ip.validate(pack)['errors'])
        pack = self.pack('pack3')
        os.symlink('interiors.json', pack / 'link.json')
        self.assertTrue(ip.validate(pack)['errors'])

    def test_manifest_cross_references_are_checked(self):
        for edit in (lambda m: m['instances'][0].update(storage_site_id='x_storage_v1'),
                     lambda m: m['instances'][0].update(layout_id='family-storage-v1' if m['instances'][0]['layout_id'] != 'family-storage-v1' else 'family-pantry-v1'),
                     lambda m: m['instances'][0].update(instance_id='other'),
                     lambda m: m.update(runtime_acceptance='accepted'),
                     lambda m: m['components'][0].update(state='pending-measurement')):
            with self.subTest(edit=edit):
                self.rejects(edit, 'pack.json')

    def test_evidence_that_is_synthetic_or_unbound_is_rejected(self):
        for edit in (lambda e: e['houses'][0].update(building_class='Land_House_2W01'),
                     lambda e: e['source'].update(result_sha256='0' * 64),
                     lambda e: e['source'].update(run_id='synthetic-run'),
                     lambda e: e.update(houses=[]),
                     lambda e: e['houses'][0].update(position=[1598.0, 0.0, 8970.0, 1.0])):
            with self.subTest(edit=edit):
                self.rejects(edit, 'evidence/house-candidates.json')


def repin(pack):
    """Recompute pack.json sha pins so a semantic edit is judged on its merits, not on the pin mismatch."""
    pack = Path(pack)
    manifest = json.loads((pack / 'pack.json').read_text())
    for section in ('files', 'sources'):
        for name in manifest[section]:
            manifest[section][name] = sha((pack / name).read_bytes())
    (pack / 'pack.json').write_text(json.dumps(manifest, indent=2) + '\n')


class RepinnedSemanticTests(TempCase):
    def edited(self, name, edit):
        pack = self.pack()
        data = json.loads((pack / name).read_text())
        edit(data)
        (pack / name).write_text(json.dumps(data, indent=2) + '\n')
        repin(pack)
        return ip.validate(pack)

    def test_pin_repaired_schema_edits_still_fail_on_their_merits(self):
        edits = (lambda d: d.update(Epoch=0), lambda d: d.update(Seed=0), lambda d: d.update(DiagnosticSearchTrial=True),
                 lambda d: d.update(MapName='enoch'), lambda d: d['Candidates'][0].update(Type='Land_House_2W01'),
                 lambda d: d['Candidates'][0].update(Orientation=[15.0, 1.0, 0.0]),
                 lambda d: d['Candidates'][0].update(Position=[1598.5, 304.5144348144531, 8970.615234375]))
        for edit in edits:
            with self.subTest(edit=edit):
                report = self.edited('interiors.json', edit)
                self.assertTrue(report['errors'])
                self.assertFalse(all('sha256 pin' in e for e in report['errors']))

    def test_pin_repaired_evidence_and_profile_edits_are_rejected(self):
        for name, edit in (('evidence/house-candidates.json', lambda e: e['source'].update(run_id='synthetic-run')),
                           ('evidence/house-candidates.json', lambda e: e['houses'][0].update(position=[1.0, 2.0, 3.0])),
                           ('pack-profile.json', lambda p: p.update(epoch=2)),
                           ('pack-profile.json', lambda p: p['slots'][0].update(house='house-999'))):
            with self.subTest(name=name):
                self.assertTrue(self.edited(name, edit)['errors'])

    def test_epoch_change_must_regenerate_identities(self):
        report = self.edited('pack-profile.json', lambda p: p.update(epoch=2))
        self.assertTrue(any('differs' in e for e in report['errors']))


def synthetic_rooms(count=2):
    """Fabricated rooms bound to the real pose; SYNTHETIC test input only."""
    rooms = [{'id': i + 1, 'local_position': [i * 3.0, 0.0, 0.0],
              'local_min': [i * 3.0 - 1.0, -1.0, -1.0], 'local_max': [i * 3.0 + 1.0, 1.0, 1.0]}
             for i in range(count)]
    survey = {'schema': 1, 'kind': 'native-room-survey-input', 'world': 'chernarusplus', 'build': '1.30.164289',
              'source_run_id': 'native-boundary-001', 'source_sha256': 'a' * 64,
              'buildings': [{'house': 'house-663', 'building_class': 'Land_House_1W01',
                             'position': HOUSE['position'], 'orientation': HOUSE['orientation'],
                             'box_min': [-8.0, -6.0, -8.0], 'box_max': [8.0, 6.0, 8.0], 'rooms': rooms}]}
    classes = {'schema': 1, 'kind': 'native-house-class-census', 'world': 'chernarusplus', 'build': '1.30.164289',
               'source_run_id': 'native-boundary-002', 'source_sha256': 'b' * 64,
               'house_classes': ['Land_House_1W01', 'Land_House_2W01', 'Land_Shed_W1'],
               'dispositions': {'Land_House_2W01': 'unmeasured', 'Land_Shed_W1': 'not_enterable'}}
    return survey, classes


def enc(value):
    return json.dumps(value).encode()


class InfectedRoomTests(TempCase):
    def generated(self, edit_survey=None, edit_classes=None):
        survey, classes = synthetic_rooms()
        if edit_survey:
            edit_survey(survey)
        if edit_classes:
            edit_classes(classes)
        pack = self.pack()
        ip.generate(pack, rooms_input=enc(survey), classes_input=enc(classes))
        return pack

    def test_room_records_land_in_the_exact_loader_path_and_format(self):
        pack = self.generated()
        doc = json.loads((pack / 'Infected/production-rooms.json').read_text())
        self.assertEqual(list(doc), ['SchemaVersion', 'Build', 'WorldName', 'Classes', 'Buildings'])
        self.assertEqual((doc['SchemaVersion'], doc['Build'], doc['WorldName']), (1, '1.30.164289', 'chernarusplus'))
        self.assertEqual({c['BuildingClass']: c['Disposition'] for c in doc['Classes']},
                         {'Land_House_1W01': 'covered', 'Land_House_2W01': 'unmeasured', 'Land_Shed_W1': 'not_enterable'})
        (house,) = doc['Buildings']
        self.assertEqual(list(house), ['BuildingClass', 'Position', 'Orientation', 'BoxMin', 'BoxMax', 'Anchors'])
        self.assertEqual(list(house['Anchors'][0]), ['Id', 'LocalPosition', 'LocalMin', 'LocalMax', 'SourceRunId',
                                                     'SourceSha256', 'EvidenceKind'])
        self.assertEqual(house['Anchors'][0]['EvidenceKind'], 'native-room-survey-v1')
        report = ip.validate(pack)
        self.assertEqual(report['errors'], [])
        self.assertEqual([p['id'] for p in report['pending']], ['measured-interiors'])
        manifest = json.loads((pack / 'pack.json').read_text())
        self.assertIn('Infected/production-rooms.json', manifest['files'])
        self.assertEqual(set(manifest['sources']), {'evidence/house-candidates.json', 'pack-profile.json',
                                                    'evidence/room-survey.json', 'evidence/house-classes.json'})

    def test_rooms_for_a_house_without_native_pose_evidence_are_refused(self):
        survey, classes = synthetic_rooms()
        survey['buildings'][0]['position'] = [1599.0, 304.5, 8970.6]
        with self.assertRaises(ValueError):
            ip.generate(self.pack(), rooms_input=enc(survey), classes_input=enc(classes))

    def test_generation_refuses_rooms_without_the_class_census(self):
        survey, _ = synthetic_rooms()
        with self.assertRaises(ValueError):
            ip.generate(self.pack(), rooms_input=enc(survey))

    def test_enforce_room_admission_rules_are_mirrored(self):
        edits = (lambda s: s['buildings'][0]['rooms'][0].update(id=0),
                 lambda s: s['buildings'][0]['rooms'][0].update(id=65),
                 lambda s: s['buildings'][0]['rooms'][1].update(id=1),
                 lambda s: s['buildings'][0]['rooms'][0].update(local_min=[5.0, -1.0, -1.0], local_max=[6.0, 1.0, 1.0]),
                 lambda s: s['buildings'][0]['rooms'][0].update(local_position=[9.0, 0.0, 0.0]),
                 lambda s: s['buildings'][0]['rooms'][1].update(local_position=[0.5, 0.0, 0.0],
                                                                 local_min=[0.0, -1.0, -1.0], local_max=[1.0, 1.0, 1.0]),
                 lambda s: s['buildings'][0].update(box_min=[-1.0, -1.0, -1.0], box_max=[1.0, 1.0, 1.0]),
                 lambda s: s['buildings'][0].update(box_min=[-600.0, -6.0, -8.0]),
                 lambda s: s['buildings'][0].update(rooms=[]),
                 lambda s: s['buildings'][0].update(rooms=s['buildings'][0]['rooms'] * 9),
                 lambda s: s.update(source_run_id='synthetic-run-001'),
                 lambda s: s.update(source_run_id='run-without-native-prefix'),
                 lambda s: s.update(source_run_id='native-fixture-001'),
                 lambda s: s.update(source_sha256='0' * 64),
                 lambda s: s.update(source_sha256='A' * 64),
                 lambda s: s.update(build='1.29.0'), lambda s: s.update(world='enoch'))
        for edit in edits:
            with self.subTest(edit=edit):
                survey, classes = synthetic_rooms()
                edit(survey)
                with self.assertRaises(ValueError):
                    ip.generate(self.pack(), rooms_input=enc(survey), classes_input=enc(classes))

    def test_class_denominator_must_be_complete_and_consistent(self):
        edits = (lambda c: c['house_classes'].remove('Land_House_1W01'),
                 lambda c: c['dispositions'].update(Land_House_1W01='unmeasured'),
                 lambda c: c['dispositions'].update(Land_House_2W01='covered'),
                 lambda c: c['dispositions'].update(Land_House_2W01='bogus'),
                 lambda c: c['dispositions'].update(Unknown_Class='unmeasured'),
                 lambda c: c['house_classes'].append('Land_Shed_W1'),
                 lambda c: c['house_classes'].append('bad name'),
                 lambda c: c.update(source_run_id='native-selftest-3'))
        for edit in edits:
            with self.subTest(edit=edit):
                survey, classes = synthetic_rooms()
                edit(classes)
                with self.assertRaises(ValueError):
                    ip.generate(self.pack(), rooms_input=enc(survey), classes_input=enc(classes))

    def test_tampering_with_generated_rooms_is_detected_by_regeneration(self):
        pack = self.generated()
        path = pack / 'Infected/production-rooms.json'
        doc = json.loads(path.read_text())
        doc['Buildings'][0]['Anchors'][0]['LocalPosition'] = [0.1, 0.0, 0.0]
        path.write_text(json.dumps(doc))
        self.assertTrue(ip.validate(pack)['errors'])

    def test_native_json_budget_limits(self):
        pack = self.generated()
        self.assertLess((pack / 'Infected/production-rooms.json').stat().st_size, 1048576)


def measured_inputs():
    """SYNTHETIC measured record (flag cleared only to exercise the pack path), bound to the real pose."""
    record, sources, artifacts = measured_fixtures.fixture()
    record['Synthetic'] = False
    record['Context']['BuildingPosition'] = list(HOUSE['position'])
    record['Context']['BuildingOrientation'] = list(HOUSE['orientation'])
    return record, sources, artifacts


class MeasuredCatalogTests(TempCase):
    def run_generate(self, record=None, **overrides):
        base, sources, artifacts = measured_inputs()
        record = base if record is None else record
        pack = self.pack()
        spec = dict(record=measured_fixtures.encode(record), sources=sources, artifacts=artifacts,
                    trusted_addon_sha256='c' * 64)
        spec.update(overrides)
        ip.generate(pack, measured=spec)
        return pack

    def test_measured_set_and_profile_are_generated_and_cross_checked(self):
        pack = self.run_generate()
        names = {'measured-record.json', 'interior-layouts.candidate.json', 'context-policy.candidate.json',
                 'interior-report.json'}
        self.assertEqual({p.name for p in (pack / 'measured-interiors').iterdir()}, names)
        profile = json.loads((pack / 'interiors-measured-profile.json').read_text())
        for key, name in (('ExpectedRecordText', 'measured-record.json'),
                          ('ExpectedCandidateText', 'interior-layouts.candidate.json'),
                          ('ExpectedPolicyText', 'context-policy.candidate.json'),
                          ('ExpectedReportText', 'interior-report.json')):
            self.assertEqual(profile[key].encode(), (pack / 'measured-interiors' / name).read_bytes())
        self.assertEqual((profile['SchemaVersion'], profile['WorldName'], profile['Build']), (1, 'chernarusplus', '1.30.164289'))
        self.assertEqual(profile['TrustedAddonSha256'], 'c' * 64)
        self.assertEqual(profile['TrustedValidatorSha256'], sha((ROOT / 'tools/package/interior_catalog.py').read_bytes()))
        self.assertEqual(profile['SourceSha256'], json.loads((pack / 'measured-interiors/measured-record.json').read_text())['SourceSha256'])
        report = ip.validate(pack)
        self.assertEqual(report['errors'], [])
        self.assertEqual([p['id'] for p in report['pending']], ['infected-production-rooms'])
        manifest = json.loads((pack / 'pack.json').read_text())
        self.assertEqual(set(manifest['files']), {'interiors.json', 'interiors-measured-profile.json',
                                                  'measured-interiors/measured-record.json',
                                                  'measured-interiors/interior-layouts.candidate.json',
                                                  'measured-interiors/context-policy.candidate.json',
                                                  'measured-interiors/interior-report.json'})

    def test_synthetic_record_is_refused_for_the_shipped_pack(self):
        record, sources, artifacts = measured_inputs()
        record['Synthetic'] = True
        with self.assertRaises(ValueError):
            self.run_generate(record)

    def test_record_for_a_house_without_a_config_candidate_is_refused(self):
        record, _, _ = measured_inputs()
        record['Context']['BuildingPosition'] = [1234.5, 100.0, 2345.5]
        with self.assertRaises(ValueError):
            self.run_generate(record)

    def test_bad_trusted_hash_is_refused(self):
        for bad in ('', 'g' * 64, '0' * 64, 'C' * 64, 'c' * 63):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.run_generate(trusted_addon_sha256=bad)

    def test_layout_assignment_and_manifest_use_the_measured_layout_ids(self):
        pack = self.run_generate()
        manifest = json.loads((pack / 'pack.json').read_text())
        (component,) = [c for c in manifest['components'] if c['id'] == 'measured-interiors']
        self.assertEqual(component['state'], 'present-pending-native-acceptance')

    def test_tampered_measured_file_is_rejected(self):
        pack = self.run_generate()
        path = pack / 'measured-interiors/interior-report.json'
        path.write_bytes(path.read_bytes() + b' ')
        self.assertTrue(ip.validate(pack)['errors'])
        pack = self.run_generate()
        path = pack / 'interiors-measured-profile.json'
        data = json.loads(path.read_text())
        data['ExpectedPolicyText'] += ' '
        path.write_text(json.dumps(data))
        self.assertTrue(ip.validate(pack)['errors'])


class InstallTests(TempCase):
    def test_install_places_pack_files_with_an_intent_receipt_and_rolls_back_to_nothing(self):
        target = self.profile()
        before = snapshot(target)
        receipt = ip.install(PACK, target)
        self.assertEqual((target / 'interiors.json').read_bytes(), (PACK / 'interiors.json').read_bytes())
        self.assertEqual(receipt['status'], 'installed')
        stored = json.loads((target / ip.MANAGED / 'receipt.json').read_text())
        self.assertEqual(stored, receipt)
        self.assertEqual(stored['files'][0]['action'], 'create')
        self.assertEqual(stored['pack_sha256'], sha((PACK / 'pack.json').read_bytes()))
        ip.rollback(target)
        self.assertEqual(snapshot(target), before)

    def test_install_into_a_missing_profile_directory_and_removes_created_directories(self):
        parent = self.root / 'profiles'
        parent.mkdir()
        target = parent / 'HollowCountry'
        ip.install(PACK, target)
        self.assertTrue((target / 'interiors.json').is_file())
        ip.rollback(target)
        self.assertFalse(target.exists())
        self.assertEqual(list(parent.iterdir()), [])

    def test_subdirectories_for_optional_files_are_created_and_removed(self):
        survey, classes = synthetic_rooms()
        pack = self.pack()
        ip.generate(pack, rooms_input=enc(survey), classes_input=enc(classes))
        target = self.profile()
        before = snapshot(target)
        ip.install(pack, target)
        self.assertTrue((target / 'Infected/production-rooms.json').is_file())
        ip.rollback(target)
        self.assertEqual(snapshot(target), before)

    def test_existing_different_file_requires_replace_and_rollback_is_byte_exact(self):
        target = self.profile()
        (target / 'interiors.json').write_bytes(b'{"operator":"edited"}\r\n\x00')
        (target / 'settings.json').write_bytes(b'keep')
        before = snapshot(target)
        with self.assertRaises(ValueError):
            ip.install(PACK, target)
        self.assertEqual(snapshot(target), before)
        ip.install(PACK, target, replace=True)
        self.assertEqual((target / 'interiors.json').read_bytes(), (PACK / 'interiors.json').read_bytes())
        ip.rollback(target)
        self.assertEqual(snapshot(target), before)

    def test_identical_existing_file_is_kept_and_survives_rollback(self):
        target = self.profile()
        (target / 'interiors.json').write_bytes((PACK / 'interiors.json').read_bytes())
        before = snapshot(target)
        receipt = ip.install(PACK, target)
        self.assertEqual(receipt['files'][0]['action'], 'keep')
        ip.rollback(target)
        self.assertEqual(snapshot(target), before)

    def test_hard_linked_and_symlinked_targets_are_refused_without_touching_outside(self):
        target = self.profile()
        outside = self.root / 'outside.json'
        outside.write_bytes(b'outside')
        os.link(outside, target / 'interiors.json')
        with self.assertRaises(ValueError):
            ip.install(PACK, target, replace=True)
        self.assertEqual(outside.read_bytes(), b'outside')
        (target / 'interiors.json').unlink()
        os.symlink(outside, target / 'interiors.json')
        with self.assertRaises(ValueError):
            ip.install(PACK, target, replace=True)
        self.assertEqual(outside.read_bytes(), b'outside')
        self.assertFalse((target / ip.MANAGED).exists())

    def test_symlinked_profile_directory_is_refused(self):
        real = self.root / 'real'
        real.mkdir()
        link = self.root / 'HollowCountry'
        os.symlink(real, link)
        with self.assertRaises(ValueError):
            ip.install(PACK, link)
        self.assertEqual(list(real.iterdir()), [])

    def test_wrong_directory_name_and_invalid_pack_are_refused(self):
        wrong = self.root / 'elsewhere'
        wrong.mkdir()
        with self.assertRaises(ValueError):
            ip.install(PACK, wrong)
        pack = self.pack()
        data = json.loads((pack / 'interiors.json').read_text())
        data['Seed'] += 1
        (pack / 'interiors.json').write_text(json.dumps(data))
        target = self.profile()
        with self.assertRaises(ValueError):
            ip.install(pack, target)
        self.assertEqual(snapshot(target), {})

    def test_second_install_and_existing_journal_are_refused(self):
        target = self.profile()
        ip.install(PACK, target)
        with self.assertRaises(ValueError):
            ip.install(PACK, target)
        ip.rollback(target)
        (target / 'interiors.json').write_bytes(b'{}')
        (target / f'interiors_s1_e{json.loads((PACK / "interiors.json").read_text())["Epoch"]}').mkdir()
        with self.assertRaises(ValueError):
            ip.install(PACK, target, replace=True)

    def test_interrupted_install_rolls_back(self):
        target = self.profile()
        (target / 'interiors.json').write_bytes(b'old')
        before = snapshot(target)
        real = os.replace
        calls = []

        def failing(src, dst, *a, **k):
            calls.append(dst)
            if len(calls) == 1:
                raise OSError('simulated crash while placing')
            return real(src, dst, *a, **k)
        original = os.replace
        os.replace = failing
        try:
            with self.assertRaises(OSError):
                ip.install(PACK, target, replace=True)
        finally:
            os.replace = original
        ip.rollback(target)
        self.assertEqual(snapshot(target), before)

    def test_rollback_refuses_drift_and_unknown_managed_files(self):
        target = self.profile()
        ip.install(PACK, target)
        (target / 'interiors.json').write_bytes(b'operator edit')
        with self.assertRaises(ValueError):
            ip.rollback(target)
        self.assertEqual((target / 'interiors.json').read_bytes(), b'operator edit')
        (target / 'interiors.json').write_bytes((PACK / 'interiors.json').read_bytes())
        (target / ip.MANAGED / 'surprise.txt').write_bytes(b'x')
        with self.assertRaises(ValueError):
            ip.rollback(target)
        self.assertTrue((target / 'interiors.json').exists())

    def failing(self, fail_name, partial=0):
        real = ip.fresh_write

        def write(root, name, data):
            if name == fail_name:
                if partial:
                    real(root, name, data[:partial])
                raise OSError('injected write failure before ' + fail_name)
            return real(root, name, data)
        return mock.patch.object(ip, 'fresh_write', write)

    def test_forged_replacement_evidence_never_deletes_the_only_operator_backup(self):
        """Regression (P1): a replace row whose original digest equals its installed digest is impossible evidence."""
        target = self.profile()
        original = b'operator config\r\n'
        (target / 'interiors.json').write_bytes(original)
        with self.failing('receipt.next'):
            with self.assertRaises(OSError):
                ip.install(PACK, target, replace=True)
        receipt_path = target / ip.MANAGED / 'receipt.json'
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt['status'], 'intent')
        row = receipt['files'][0]
        self.assertEqual(row['action'], 'replace')
        backup = target / ip.MANAGED / 'backup/0.bak'
        self.assertEqual(backup.read_bytes(), original)
        row['original_sha256'] = row['sha256']
        receipt_path.write_bytes(ip.encode(receipt))
        before = snapshot(target)
        with self.assertRaises(ValueError):
            ip.rollback(target)
        self.assertEqual(snapshot(target), before)
        self.assertEqual(backup.read_bytes(), original)

    def test_a_replacement_row_without_a_valid_original_digest_is_refused(self):
        target = self.profile()
        (target / 'interiors.json').write_bytes(b'operator config')
        with self.failing('receipt.next'):
            with self.assertRaises(OSError):
                ip.install(PACK, target, replace=True)
        receipt_path = target / ip.MANAGED / 'receipt.json'
        receipt = json.loads(receipt_path.read_text())
        for bad in ('nothex', None):
            with self.subTest(bad=bad):
                forged = json.loads(json.dumps(receipt))
                forged['files'][0]['original_sha256'] = bad
                receipt_path.write_bytes(ip.encode(forged))
                before = snapshot(target)
                with self.assertRaises(ValueError):
                    ip.rollback(target)
                self.assertEqual(snapshot(target), before)

    def test_kill_before_receipt_with_an_operator_config_is_recovered_by_rollback(self):
        target = self.profile()
        (target / 'interiors.json').write_bytes(b'operator config\r\n')
        before = snapshot(target)
        with self.failing('receipt.json'):
            with self.assertRaises(OSError):
                ip.install(PACK, target, replace=True)
        with self.assertRaises(ValueError):
            ip.install(PACK, target, replace=True)
        self.assertEqual(ip.rollback(target), 'recovered_bootstrap')
        self.assertEqual(snapshot(target), before)
        ip.install(PACK, target, replace=True)
        ip.rollback(target)
        self.assertEqual(snapshot(target), before)

    def test_kill_in_the_middle_of_the_receipt_or_a_backup_is_recovered(self):
        for fail, partial in (('receipt.json', 12), ('backup/0.bak', 4)):
            target = self.profile(name='profiles-' + fail.replace('/', '-'))
            (target / 'interiors.json').write_bytes(b'operator config\r\n')
            before = snapshot(target)
            with self.failing(fail, partial):
                with self.assertRaises(OSError):
                    ip.install(PACK, target, replace=True)
            self.assertIn(ip.rollback(target), ('recovered_bootstrap', 'rolled_back'))
            self.assertEqual(snapshot(target), before)
            self.assertFalse((target / ip.MANAGED).exists())

    def test_stranded_backup_without_a_receipt_is_recovered_only_while_the_operator_file_matches(self):
        target = self.profile()
        (target / 'interiors.json').write_bytes(b'operator config\r\n')
        managed = target / ip.MANAGED
        (managed / 'backup').mkdir(parents=True)
        (managed / 'backup/0.bak').write_bytes(b'operator config\r\n')
        (target / 'interiors.json').write_bytes(b'operator changed it later\r\n')
        before = snapshot(target)
        with self.assertRaises(ValueError):
            ip.rollback(target)
        self.assertEqual(snapshot(target), before)
        (target / 'interiors.json').write_bytes(b'operator config\r\n')
        self.assertEqual(ip.rollback(target), 'recovered_bootstrap')
        self.assertEqual(snapshot(target), {'interiors.json': b'operator config\r\n'})

    def test_receipt_less_managed_directory_with_unknown_files_is_refused(self):
        target = self.profile()
        managed = target / ip.MANAGED
        managed.mkdir()
        (managed / 'surprise.txt').write_bytes(b'x')
        before = snapshot(target)
        with self.assertRaises(ValueError):
            ip.rollback(target)
        self.assertEqual(snapshot(target), before)

    def test_a_null_or_non_object_receipt_is_refused_not_recovered(self):
        target = self.profile()
        managed = target / ip.MANAGED
        managed.mkdir()
        for text in (b'null', b'[]', b'7'):
            (managed / 'receipt.json').write_bytes(text)
            before = snapshot(target)
            with self.assertRaises(ValueError):
                ip.rollback(target)
            self.assertEqual(snapshot(target), before)

    def test_rollback_without_install_is_refused(self):
        target = self.profile()
        with self.assertRaises(ValueError):
            ip.rollback(target)


class CommandLineTests(TempCase):
    def run_cli(self, *args):
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                ip.main(list(args))
                code = 0
            except SystemExit as exit_:
                code = exit_.code or 0
        return code, out.getvalue() + err.getvalue()

    def test_validate_reports_pending_and_strict_fails_on_it(self):
        code, text = self.run_cli('validate', '--pack', str(PACK))
        self.assertEqual(code, 0)
        self.assertIn('pending-measurement', text)
        self.assertIn('measured-interiors', text)
        self.assertIn('infected-production-rooms', text)
        code, _ = self.run_cli('validate', '--pack', str(PACK), '--strict')
        self.assertNotEqual(code, 0)

    def test_install_and_rollback_commands(self):
        target = self.profile()
        code, text = self.run_cli('install', '--pack', str(PACK), '--target', str(target))
        self.assertEqual(code, 0, text)
        self.assertTrue((target / 'interiors.json').exists())
        code, text = self.run_cli('rollback', '--target', str(target))
        self.assertEqual(code, 0, text)
        self.assertFalse((target / 'interiors.json').exists())

    def test_output_never_prints_home_paths(self):
        _, text = self.run_cli('validate', '--pack', str(PACK))
        self.assertNotIn(str(Path.home()), text)
        code, text = self.run_cli('validate', '--pack', str(self.root / 'missing'))
        self.assertNotEqual(code, 0)
        self.assertNotIn(str(Path.home()), text)


if __name__ == '__main__':
    unittest.main()


class TemplatesPackTests(TempCase):
    """Explicit SYNTHETIC build/report inputs, never native evidence."""

    def build_input(self, **kwargs):
        from tests.unit.test_interior_templates import standard
        built = standard(types_bytes=None, **kwargs)
        source = self.root / 't2'
        source.mkdir()
        for name, data in built.files.items():
            (source / name).write_bytes(data)
        manifest = copy.deepcopy(built.manifest)
        for name in ('types', 'cfgspawnabletypes', 'cfglimitsdefinition'):
            manifest['Sources'][name] = sha(('synthetic-' + name).encode())
        manifest['Sources']['search-generator'] = sha(b'synthetic-search')
        (source / 'build-manifest.json').write_text(json.dumps(manifest))
        return source

    def assemble(self, search=None):
        source = self.build_input()
        out = self.root / 'assembled'
        ip.templates_assemble(source, out, search)
        return out

    def repin(self, pack, name, document):
        path = pack / 'templates' / name
        path.write_bytes(json.dumps(document, separators=(',', ':')).encode('ascii'))
        index_path = pack / 'templates/index.json'
        index = json.loads(index_path.read_bytes())
        for field in ('ClassFiles', 'TemplateFiles', 'FurnishFiles', 'GroupFiles'):
            for row in index[field]:
                if row['File'] == name:
                    row['Sha256'] = sha(path.read_bytes())
        index_path.write_bytes(json.dumps(index).encode('ascii'))

    def site_pack(self):
        pack = self.assemble()
        name = 'search-groups-000.json'
        raw = ip._compact({'SchemaVersion': 2, 'Chunk': 0, 'Groups': [
            {'Id': 'g-test', 'Usages': [], 'Container': 'loot', 'Categories': ['tools'],
             'Tags': [], 'Items': ['Hammer']}]})
        (pack / 'templates' / name).write_bytes(raw)
        index_path = pack / 'templates/index.json'
        index = json.loads(index_path.read_bytes())
        index['GroupFiles'] = [{'File': name, 'Sha256': sha(raw)}]
        index_path.write_bytes(ip._compact(index))
        t = json.loads((pack / 'templates/t-0000.json').read_bytes())
        t['SearchSites'] = [{'Id': 1, 'Room': 1, 'Center': [0, 1, 0], 'Radius': 1,
                             'Source': 'loot', 'Points': [0], 'Groups': ['g-test']}]
        self.repin(pack, 't-0000.json', t)
        ip.templates_validate(pack)
        return pack

    def test_templates_validate_cli_refuses_site_center_outside_box(self):
        import contextlib
        import io
        pack = self.site_pack()
        t = json.loads((pack / 'templates/t-0000.json').read_bytes())
        t['SearchSites'][0]['Center'][0] = t['Box']['Max'][0] + 1
        self.repin(pack, 't-0000.json', t)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as refused:
            ip.main(['templates', 'validate', str(pack)])
        self.assertEqual(refused.exception.code, 1)
        with self.assertRaises(ValueError):
            ip.templates_install(pack, self.root / 'refused-install', server_stopped=True)
        self.assertFalse((self.root / 'refused-install').exists())

    def test_reader_template_rules_are_enforced_even_when_file_hashes_match(self):
        pack = self.site_pack()
        original = json.loads((pack / 'templates/t-0000.json').read_bytes())
        changes = {
            'unknown field': lambda t: t.update(Extra=1),
            'template id': lambda t: t.update(TemplateId='bad text'),
            'evidence pin': lambda t: t['Evidence'][0].update(Sha256='b' * 64),
            'duplicate evidence': lambda t: t['Evidence'].append(copy.deepcopy(t['Evidence'][0])),
            'room containment': lambda t: t['Rooms'][0]['Min'].__setitem__(0, -500),
            'room anchor': lambda t: t['Rooms'][0].update(Anchor=[500, 0, 0]),
            'floor': lambda t: t['Rooms'][0].update(FloorY=500),
            'cells': lambda t: t['Rooms'][0].update(Cells=0),
            'integer token': lambda t: t['Rooms'][0].update(Id=1.0),
            'integer overflow': lambda t: t['Rooms'][0].update(Cells=2147483648),
            'anchors spacing': lambda t: t['Rooms'].append(dict(t['Rooms'][0], Id=2)),
            'keepout containment': lambda t: t['KeepOuts'][0]['Min'].__setitem__(0, -500),
            'keepout identity': lambda t: t['KeepOuts'].append(copy.deepcopy(t['KeepOuts'][0])),
            'prop type': lambda t: t['PropSlots'][0].update(Type='Unknown'),
            'prop orientation': lambda t: t['PropSlots'][0].update(Orientation=[0, 1, 0]),
            'prop position': lambda t: t['PropSlots'][0].update(Position=[500, 0, 0]),
            'prop keepout': lambda t: t['KeepOuts'].append(dict(t['PropSlots'][0]['Bounds'], Kind='door', Index=999)),
            'history': lambda t: t['PropSlots'][0].update(History=['family', 'family']),
            'site room': lambda t: t['SearchSites'][0].update(Room=999),
            'site radius': lambda t: t['SearchSites'][0].update(Radius=8.1),
            'site points': lambda t: t['SearchSites'][0].update(Points=[0, 0]),
            'site id': lambda t: t['SearchSites'][0].update(Id=0),
        }
        for label, change in changes.items():
            t = copy.deepcopy(original)
            change(t)
            self.repin(pack, 't-0000.json', t)
            with self.subTest(rule=label), self.assertRaises(ValueError):
                ip.templates_validate(pack)

    def test_assemble_requires_exact_search_group_item_cap(self):
        from tools.package import search_context as sc
        from tests.unit import test_interior_templates as f
        source = self.build_input()
        search = self.root / 'search'
        chunks, report = sc.build_search_groups(f.PROTO, f.TYPES)
        # Pins are explicit synthetic inputs shared with build_input.
        manifest = json.loads((source / 'build-manifest.json').read_bytes())
        report['Sources'] = {k: manifest['Sources'][k] for k in report['Sources']}
        for value in (None, 128, 1024.0, True):
            report['MaxItemsPerGroup'] = value
            if search.exists():
                shutil.rmtree(search)
            sc.write_pack(search, chunks, report)
            with self.subTest(cap=value), self.assertRaisesRegex(ValueError, 'MaxItemsPerGroup'):
                ip.templates_assemble(source, self.root / 'refused', search)
        self.assertFalse((self.root / 'refused').exists())

    def test_interrupted_bootstrap_removes_empty_templates_directory(self):
        pack = self.assemble()
        target = self.root / 'HollowCountry'
        target.mkdir()
        with mock.patch.object(ip, 'fresh_write', side_effect=OSError('interrupted receipt')):
            with self.assertRaises(OSError):
                ip.templates_install(pack, target, server_stopped=True)
        self.assertEqual(ip.templates_rollback(target, server_stopped=True), ip.RECOVERED_BOOTSTRAP)
        self.assertFalse((target / 'templates').exists())

    def test_runtime_rows_exclude_proto_classes_without_house_observations(self):
        from tests.unit import test_interior_templates as f
        raw = f.encode(f.census(f.house_rows() + f.calibration_rows(), f.CLASSES))
        built = ip.templates_build([raw], f.PROTO, f.POS, f.TYPES)
        rows = [r for n, data in built.files.items() if n.startswith('classes-')
                for r in json.loads(data)['Rows']]
        self.assertEqual({r['BuildingClass'] for r in rows}, set(f.CLASSES))
        expected = [{'BuildingClass': 'Land_Other_Farm', 'Reason': 'not_observed_as_house'}]
        self.assertEqual(built.manifest['ExcludedProtoClasses'], expected)
        self.assertEqual(built.summary['excluded_proto_classes'], expected)

    def test_furnish_duplicates_use_native_float32_quantization(self):
        pack = self.assemble()
        name = 'furnish-000.json'
        doc = json.loads((pack / 'templates' / name).read_bytes())
        row = doc['Rows'][0]
        doc['Rows'] = [dict(row, Slot=0, Position=[10000.0049, 100, 100], Yaw=0),
                       dict(row, Slot=1, Position=[10000.006, 100, 100], Yaw=90)]
        self.repin(pack, name, doc)
        with self.assertRaisesRegex(ValueError, 'duplicate furnished instance'):
            ip.templates_validate(pack)

    def test_strict_reader_tokens_refuse_before_semantic_validation(self):
        from tests.unit.test_interior_templates import standard
        raw = standard().files['t-0000.json']
        changes = [raw.replace(b'"Id":1', b'"Id":1.0', 1),
                   raw.replace(b'"Id":1', b'"Id":-2147483648', 1),
                   raw.replace(b'"FloorY":0.0', b'"FloorY":0e0000000000000000000000000000000000', 1),
                   raw.replace(b'"Cells"', b'"\\u0043ells"', 1)]
        for changed in changes:
            self.assertNotEqual(changed, raw)
            with self.subTest(raw=changed[:60]), self.assertRaises(ValueError):
                ip._template_json(changed, 't-0000.json')

    def test_assemble_pins_exact_contract_index_and_copies_bytes(self):
        pack = self.assemble()
        index = ip.templates_validate(pack)['index']
        self.assertEqual(set(index), set('SchemaVersion Kind WorldName Build PackId SourcePin Frame Provisional Sources ClassFiles TemplateFiles FurnishFiles GroupFiles'.split()))
        self.assertEqual(index['SchemaVersion'], 2)
        self.assertEqual(index['WorldName'], 'chernarusplus')
        self.assertIs(index['Provisional'], True)
        self.assertEqual(index['SourcePin'], sha(json.dumps(index['Sources'], sort_keys=True, separators=(',', ':')).encode('ascii')))
        for row in index['TemplateFiles']:
            self.assertEqual(row['BuildingClass'], json.loads((pack / 'templates' / row['File']).read_bytes())['BuildingClass'])
        for path in (self.root / 't2').glob('*.json'):
            if path.name != 'build-manifest.json':
                self.assertEqual(path.read_bytes(), (pack / 'templates' / path.name).read_bytes())

    def test_empty_optional_chunks_have_no_index_bindings_or_files(self):
        from tests.unit import test_interior_templates as f
        from tests.unit import test_interior_templates_runtime as runtime
        source = self.build_input(max_furnished=0)
        pack = self.root / 'empty-optionals'
        ip.templates_assemble(source, pack)
        docs = {p.name: json.loads(p.read_bytes()) for p in (pack / 'templates').iterdir()}
        self.assertEqual(docs['index.json']['FurnishFiles'], [])
        self.assertEqual(docs['index.json']['GroupFiles'], [])
        self.assertFalse(any(n.startswith(('furnish-', 'search-groups-')) for n in docs))
        env, _, _, logs, _, _ = runtime.fixture(docs)
        env['EngineHouse'] = lambda cls: cls in f.CLASSES
        env['HCInteriorCatalog'].SearchType = lambda typ: typ in f.tpl.PROP_TYPES
        env['EnsureLoaded'](None)
        self.assertTrue(env['Loaded'](), logs)

    def test_search_report_and_chunk_pins_are_merged_and_source_conflicts_refuse(self):
        search = self.root / 't5'
        search.mkdir()
        chunk = json.dumps({'SchemaVersion': 2, 'Chunk': 0, 'Groups': [
            {'Id': 'g-0000', 'Usages': ['Town'], 'Container': 'loot',
             'Categories': ['tools'], 'Tags': [], 'Items': ['Hammer']}]}).encode('ascii')
        (search / 'search-groups-000.json').write_bytes(chunk)
        source = self.build_input()
        manifest = json.loads((source / 'build-manifest.json').read_bytes())
        report = {'SchemaVersion': 2, 'Kind': 'hc-search-context-report', 'MaxItemsPerGroup': 1024,
                  'Sources': {'mapgroupproto': manifest['Sources']['mapgroupproto'],
                              'types': manifest['Sources']['types'], 'search-generator': sha(b'synthetic-search')},
                  'Chunks': [{'File': 'search-groups-000.json', 'Bytes': len(chunk), 'Sha256': sha(chunk)}]}
        (search / 'search-context-report.json').write_text(json.dumps(report))
        out = self.root / 'assembled'
        ip.templates_assemble(source, out, search)
        self.assertEqual(ip.templates_validate(out)['index']['GroupFiles'][0]['Sha256'], sha(chunk))
        report['Sources']['mapgroupproto'] = sha(b'conflict')
        (search / 'search-context-report.json').write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'source'):
            ip.templates_assemble(source, self.root / 'refused', search)
        self.assertFalse((self.root / 'refused').exists())

    def test_unknown_names_gaps_pins_provisional_and_class_binding_refuse(self):
        pack = self.assemble()
        before = snapshot(pack)
        def restore():
            shutil.rmtree(pack)
            pack.mkdir()
            for name, data in before.items():
                path = pack / name
                if data is None:
                    path.mkdir(exist_ok=True)
                else:
                    path.write_bytes(data)
        changes = [lambda: (pack / 'templates/extra.json').write_bytes(b'{}'),
                   lambda: (pack / 'templates/classes-000.json').rename(pack / 'templates/classes-001.json'),
                   lambda: (pack / 'templates/t-0000.json').write_bytes(b'{}')]
        for change in changes:
            change()
            with self.assertRaises(ValueError):
                ip.templates_validate(pack)
            restore()
        for key, value in (('Provisional', False), ('SourcePin', sha(b'bad')), ('Extra', 1)):
            path = pack / 'templates/index.json'
            index = json.loads(path.read_bytes())
            index[key] = value
            path.write_text(json.dumps(index))
            with self.assertRaises(ValueError):
                ip.templates_validate(pack)
            restore()
        path = pack / 'templates/t-0000.json'
        doc = json.loads(path.read_bytes())
        doc['BuildingClass'] = 'Land_Wrong'
        self.repin(pack, path.name, doc)
        with self.assertRaisesRegex(ValueError, 'BuildingClass'):
            ip.templates_validate(pack)

    def test_ascii_size_row_and_prop_caps_refuse_even_when_repinned(self):
        pack = self.assemble()
        path = pack / 'templates/classes-000.json'
        original = path.read_bytes()
        for raw in (b' ' * 32768, '{"x":"é"}'.encode('utf-8'), b'{"x":1,"x":2}'):
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                ip.templates_validate(pack)
        path.write_bytes(original)
        doc = json.loads(original)
        doc['Rows'] = doc['Rows'][:1] * 161
        self.repin(pack, path.name, doc)
        with self.assertRaises(ValueError):
            ip.templates_validate(pack)
        self.repin(pack, path.name, json.loads(original))
        furnish = json.loads((pack / 'templates/furnish-000.json').read_bytes())
        furnish['Rows'] = furnish['Rows'][:1] * 129
        self.repin(pack, 'furnish-000.json', furnish)
        with self.assertRaises(ValueError):
            ip.templates_validate(pack)

    def test_install_and_rollback_preserve_legacy_and_runtime_state(self):
        pack = self.assemble()
        target = self.root / 'profiles/HollowCountry'
        (target / 'templates/state').mkdir(parents=True)
        (target / 'templates/state/journal').write_bytes(b'runtime\r\n')
        (target / 'interiors.json').write_bytes(b'legacy\r\n')
        before = snapshot(target)
        receipt = ip.templates_install(pack, target, server_stopped=True)
        self.assertTrue(all(row['path'].startswith('templates/') for row in receipt['files']))
        self.assertEqual(ip.templates_rollback(target, server_stopped=True), ip.ROLLED_BACK)
        self.assertEqual(snapshot(target), before)

    def test_stopped_ack_replacement_backups_and_drift_refusal(self):
        pack = self.assemble()
        target = self.root / 'profiles/HollowCountry'
        (target / 'templates').mkdir(parents=True)
        path = target / 'templates/index.json'
        original = b'operator bytes\r\n'
        path.write_bytes(original)
        for kwargs in ({}, {'server_stopped': True}):
            with self.assertRaises(ValueError):
                ip.templates_install(pack, target, **kwargs)
        ip.templates_install(pack, target, replace=True, server_stopped=True)
        path.write_bytes(b'drift')
        before = snapshot(target)
        with self.assertRaises(ValueError):
            ip.templates_rollback(target, server_stopped=True)
        self.assertEqual(before, snapshot(target))
        path.write_bytes((pack / 'templates/index.json').read_bytes())
        ip.templates_rollback(target, server_stopped=True)
        self.assertEqual(path.read_bytes(), original)

    def test_symlink_and_hardlink_targets_refuse_before_writes(self):
        pack = self.assemble()
        for hard in (False, True):
            target = self.root / ('hard' if hard else 'sym') / 'HollowCountry'
            (target / 'templates').mkdir(parents=True)
            outside = target.parent / 'outside'
            outside.write_bytes(b'keep')
            dest = target / 'templates/index.json'
            if hard:
                os.link(outside, dest)
            else:
                dest.symlink_to(outside)
            with self.assertRaises(ValueError):
                ip.templates_install(pack, target, replace=True, server_stopped=True)
            self.assertEqual(outside.read_bytes(), b'keep')
            self.assertFalse((target / 'templates' / ip.MANAGED).exists())

    def test_pack_id_is_stable_when_manifest_source_order_changes(self):
        source = self.build_input()
        first = ip.templates_assemble(source, self.root / 'first')['index']
        path = source / 'build-manifest.json'
        manifest = json.loads(path.read_bytes())
        manifest['Sources'] = dict(reversed(list(manifest['Sources'].items())))
        path.write_text(json.dumps(manifest))
        second = ip.templates_assemble(source, self.root / 'second')['index']
        self.assertEqual(first['PackId'], second['PackId'])

    def test_created_container_directories_are_removed_only_if_empty(self):
        pack = self.assemble()
        target = self.root / 'profiles/HollowCountry'
        target.mkdir(parents=True)
        ip.templates_install(pack, target, server_stopped=True)
        ip.templates_rollback(target, server_stopped=True)
        self.assertEqual(snapshot(target), {})
        ip.templates_install(pack, target, server_stopped=True)
        (target / 'templates/state').mkdir()
        (target / 'templates/state/live').write_bytes(b'new runtime state')
        ip.templates_rollback(target, server_stopped=True)
        self.assertEqual((target / 'templates/state/live').read_bytes(), b'new runtime state')

    def test_interrupted_template_install_is_recoverable_and_forged_paths_refuse(self):
        pack = self.assemble()
        target = self.root / 'profiles/HollowCountry'
        (target / 'templates/state').mkdir(parents=True)
        (target / 'templates/state/live').write_bytes(b'runtime')
        original = b'original\r\n'
        (target / 'templates/index.json').write_bytes(original)
        before = snapshot(target)
        real = ip.fresh_write
        def fail(root, name, data):
            if name == 'receipt.next':
                raise OSError('synthetic crash after placement')
            return real(root, name, data)
        with mock.patch.object(ip, 'fresh_write', fail), self.assertRaises(OSError):
            ip.templates_install(pack, target, replace=True, server_stopped=True)
        receipt_path = target / ip.TEMPLATE_MANAGED / 'receipt.json'
        receipt_raw = receipt_path.read_bytes()
        receipt = json.loads(receipt_raw)
        receipt['files'][0]['path'] = 'templates/state/live'
        receipt_path.write_text(json.dumps(receipt))
        interrupted = snapshot(target)
        with self.assertRaises(ValueError):
            ip.templates_rollback(target, server_stopped=True)
        self.assertEqual(snapshot(target), interrupted)
        receipt_path.write_bytes(receipt_raw)
        ip.templates_rollback(target, server_stopped=True)
        self.assertEqual(snapshot(target), before)

    def test_prop_total_1500_is_allowed_and_1501_is_refused(self):
        pack = self.assemble()
        path = pack / 'templates/t-0000.json'
        template = json.loads(path.read_bytes())
        template['PropSlots'] = [dict(copy.deepcopy(template['PropSlots'][0]), Id=i, History=['family'])
                                 for i in range(1, 6)]
        self.repin(pack, path.name, template)
        original = json.loads((pack / 'templates/furnish-000.json').read_bytes())['Rows'][0]
        def populate(count):
            rows = [dict(original, Slot=i, Position=[1000.0+i, 100.0, 2000.0],
                         Props=list(range(1, min(5, count-i*5)+1)), History='family')
                    for i in range((count+4)//5)]
            index_path = pack / 'templates/index.json'
            index = json.loads(index_path.read_bytes())
            index['FurnishFiles'] = []
            for number, offset in enumerate(range(0, len(rows), 100)):
                name = 'furnish-%03d.json' % number
                raw = json.dumps({'SchemaVersion': 2, 'Chunk': number, 'Rows': rows[offset:offset+100]}, separators=(',', ':')).encode('ascii')
                (pack / 'templates' / name).write_bytes(raw)
                index['FurnishFiles'].append({'File': name, 'Sha256': sha(raw)})
            index_path.write_text(json.dumps(index))
        populate(1500)
        self.assertEqual(ip.templates_validate(pack)['summary']['furnish_props'], 1500)
        populate(1501)
        with self.assertRaisesRegex(ValueError, '1500'):
            ip.templates_validate(pack)

    def test_all_chunk_list_caps_are_enforced(self):
        pack = self.assemble()
        path = pack / 'templates/index.json'
        original = path.read_bytes()
        for field, count in (('ClassFiles', 17), ('FurnishFiles', 17), ('TemplateFiles', 513), ('GroupFiles', 65)):
            doc = json.loads(original)
            doc[field] = [{'File': 'fake', 'Sha256': sha(b'synthetic')}] * count
            path.write_text(json.dumps(doc))
            with self.subTest(field=field), self.assertRaises(ValueError):
                ip.templates_validate(pack)
        path.write_bytes(original)

    def test_scoped_build_records_unobserved_stock_classes_without_runtime_rows(self):
        from tests.unit import test_interior_templates as fixtures
        built = ip.templates_build([], fixtures.PROTO, fixtures.POS)
        classes = [row for name, raw in built.files.items() if name.startswith('classes-')
                   for row in json.loads(raw)['Rows']]
        self.assertEqual(classes, [])
        self.assertEqual({r['BuildingClass'] for r in built.manifest['ExcludedProtoClasses']},
                         set(fixtures.tpl.parse_proto(fixtures.PROTO)))
        self.assertEqual(built.summary['templates'], 0)
        self.assertFalse(any(key.startswith('census-') for key in built.manifest['Sources']))
        self.assertIsNone(built.manifest['Frame'])

    def test_scoped_build_checks_cross_run_conflicts_before_t2(self):
        from tests.unit import test_interior_templates as fixtures
        adapter = fixtures.CensusAdapterTests()
        first = adapter.native()
        second = adapter.native(run='b' * 32)
        second['placements'][0]['house']['model'] = 'conflict'
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            ip.templates_build([fixtures.encode(first), fixtures.encode(second)], fixtures.PROTO, fixtures.POS)

    def test_build_wrapper_retains_measured_templates_and_audits_excluded_stock_classes(self):
        from tests.unit import test_interior_templates as fixtures
        doc = fixtures.census(fixtures.house_rows() + fixtures.calibration_rows(), fixtures.CLASSES)
        proto = fixtures.proto_xml([fixtures.HOUSE_GROUP, fixtures.OTHER_GROUP,
                                   fixtures.group('Land_Unmeasured', [fixtures.container('loot', [fixtures.point('0 0 0')])])])
        built = ip.templates_build([fixtures.encode(doc)], proto, fixtures.POS)
        self.assertEqual(built.summary['rooms']['covered'], 1)
        self.assertEqual(built.summary['rooms']['excluded']['path_pending'], 2)
        self.assertEqual(len(built.manifest['ExcludedProtoClasses']), 2)
        self.assertTrue(any(name.startswith('t-') for name in built.files))
        self.assertEqual(built.manifest['Sources']['census-' + fixtures.RUN], sha(fixtures.encode(doc)))

    def test_templates_cli_build_assemble_validate_install_and_rollback(self):
        import contextlib
        import io
        from tests.unit import test_interior_templates as fixtures
        from tools.package import search_context as sc
        stock = self.root / 'stock'
        (stock / 'db').mkdir(parents=True)
        (stock / 'mapgroupproto.xml').write_bytes(fixtures.PROTO)
        (stock / 'mapgrouppos.xml').write_bytes(fixtures.POS)
        for relative in ('db/types.xml', 'cfgspawnabletypes.xml', 'cfglimitsdefinition.xml'):
            (stock / relative).write_bytes(b'<synthetic/>')
        (stock / 'db/types.xml').write_bytes(fixtures.TYPES)
        census = self.root / 'census.json'
        census.write_bytes(fixtures.encode(fixtures.census(
            fixtures.house_rows() + fixtures.calibration_rows(), fixtures.CLASSES)))
        build, pack = self.root / 'build', self.root / 'cli-pack'
        search = self.root / 'search'
        target = self.root / 'profiles/HollowCountry'
        target.parent.mkdir()
        with contextlib.redirect_stdout(io.StringIO()):
            ip.main(['templates', 'build', '--proto', str(stock / 'mapgroupproto.xml'),
                     '--pos', str(stock / 'mapgrouppos.xml'), '--census', str(census), '--out', str(build)])
            self.assertEqual(sc.main(['--mapgroupproto', str(stock / 'mapgroupproto.xml'),
                                      '--types', str(stock / 'db/types.xml'), '--output-dir', str(search)]), 0)
            ip.main(['templates', 'assemble', '--build', str(build), '--out', str(pack),
                     '--stock', str(stock), '--search-groups', str(search)])
            ip.main(['templates', 'validate', str(pack)])
            ip.main(['templates', 'install', '--pack', str(pack), '--target', str(target), '--server-stopped'])
            self.assertTrue((target / 'templates/index.json').exists())
            ip.main(['templates', 'rollback', '--target', str(target), '--server-stopped'])
        self.assertFalse(target.exists())

    def test_search_groups_refuse_containers_outside_reader_allowlist(self):
        pack = self.assemble()
        raw = json.dumps({'SchemaVersion': 2, 'Chunk': 0, 'Groups': [
            {'Id': 'g-0000', 'Usages': ['Town'], 'Container': 'lootFactory',
             'Categories': ['tools'], 'Tags': [], 'Items': ['Hammer']}]}).encode('ascii')
        (pack / 'templates/search-groups-000.json').write_bytes(raw)
        path = pack / 'templates/index.json'
        index = json.loads(path.read_bytes())
        index['GroupFiles'] = [{'File': 'search-groups-000.json', 'Sha256': sha(raw)}]
        index['Sources']['search-generator'] = sha(b'synthetic generator')
        index['SourcePin'] = ip._source_pin(index['Sources'])
        path.write_text(json.dumps(index))
        with self.assertRaisesRegex(ValueError, 'container'):
            ip.templates_validate(pack)

    def test_real_cli_pack_obeys_runtime_reader_admission_rules(self):
        import contextlib
        import io
        from tests.unit import test_interior_templates as f
        from tests.unit import test_interior_templates_runtime as runtime
        from tools.package import search_context as sc
        stock = self.root / 'e2e-stock'
        (stock / 'db').mkdir(parents=True)
        # Synthetic empty/unsupported keys sort before the emitted groups and used to shift IDs.
        pr = f.proto_xml([f.group(f.HOUSE, [
            f.container('loot', [f.point('0 0 0')], ()),
            f.container('loot', [f.point('0 0 0')], ('absent',)),
            f.container('lootFactory', [f.point('0 0 0')]),
            f.container('lootFloor', [f.point('0 0 0')]),
            f.container('lootshelves', [f.point('1 1 1')], ('books',))])])
        for name, raw in {'mapgroupproto.xml': pr, 'mapgrouppos.xml': f.POS,
                          'db/types.xml': f.TYPES, 'cfgspawnabletypes.xml': b'<spawnabletypes/>',
                          'cfglimitsdefinition.xml': b'<lists/>'}.items():
            (stock / name).write_bytes(raw)
        census = self.root / 'e2e-census.json'
        census.write_bytes(f.encode(f.census(f.house_rows() + f.calibration_rows(), f.CLASSES)))
        build, search, pack = [self.root / ('e2e-' + n) for n in ('build', 'search', 'pack')]
        with contextlib.redirect_stdout(io.StringIO()):
            ip.main(['templates', 'build', '--census', str(census), '--proto', str(stock / 'mapgroupproto.xml'),
                     '--pos', str(stock / 'mapgrouppos.xml'), '--types', str(stock / 'db/types.xml'), '--out', str(build)])
            self.assertEqual(sc.main(['--mapgroupproto', str(stock / 'mapgroupproto.xml'),
                                      '--types', str(stock / 'db/types.xml'), '--output-dir', str(search)]), 0)
            ip.main(['templates', 'assemble', '--build', str(build), '--search-groups', str(search),
                     '--stock', str(stock), '--out', str(pack)])
        docs = {p.name: json.loads(p.read_bytes()) for p in (pack / 'templates').iterdir()}
        index = docs['index.json']
        self.assertEqual(index['Frame'], 'rot90')
        required = {'mapgroupproto', 'mapgrouppos', 'types', 'cfgspawnabletypes',
                    'cfglimitsdefinition', 'generator', 'search-generator'}
        self.assertTrue(required <= set(index['Sources']))
        self.assertTrue(8 <= len(index['Sources']) <= 520)
        for pin in index['Sources'].values():
            self.assertRegex(pin, r'^[0-9a-f]{64}$')
        for field, key, cap in [('ClassFiles', 'Rows', 160), ('FurnishFiles', 'Rows', 128),
                                 ('GroupFiles', 'Groups', 512)]:
            self.assertTrue(index[field], field)
            for number, entry in enumerate(index[field]):
                chunk = docs[entry['File']]
                self.assertEqual(chunk['Chunk'], number)
                self.assertTrue(1 <= len(chunk[key]) <= cap)
        groups = {g['Id']: g for entry in index['GroupFiles'] for g in docs[entry['File']]['Groups']}
        allowed = {'lootshelves', 'loot', 'lootFloor', 'lootweapons'}
        for g in groups.values():
            self.assertIn(g['Container'], allowed)
            self.assertGreaterEqual(len(g['Categories']), 1)
            self.assertTrue(1 <= len(g['Items']) <= 1024)
            self.assertEqual(len(g['Items']), len(set(g['Items'])))
        for entry in index['TemplateFiles']:
            self.assertTrue(docs[entry['File']]['SearchSites'])
            for site in docs[entry['File']]['SearchSites']:
                self.assertIn(site['Source'], allowed)
                for gid in site['Groups']:
                    self.assertIn(gid, groups)
                    self.assertEqual(groups[gid]['Container'], site['Source'])
        # Execute the authored reader control flow, with explicit synthetic engine boundaries.
        env, _, _, logs, _, _ = runtime.fixture(docs)
        env['EngineHouse'] = lambda cls: cls in f.CLASSES
        env['HCInteriorCatalog'].SearchType = lambda typ: typ in f.tpl.PROP_TYPES
        env['EnsureLoaded'](None)
        self.assertTrue(env['Loaded'](), logs)

    def test_search_only_class_passes_assemble_validation_and_the_reader(self):
        import contextlib
        import io
        from tests.unit import test_interior_templates as f
        from tests.unit import test_interior_templates_runtime as runtime
        from tools.package import search_context as sc
        pending = 'Land_Pending_Path'
        stock = self.root / 'so-stock'
        (stock / 'db').mkdir(parents=True)
        pr = f.proto_xml([f.HOUSE_GROUP, f.group(pending, [f.container('lootFloor', [f.point('2.0 0.0 3.0')])])])
        for name, raw in {'mapgroupproto.xml': pr, 'mapgrouppos.xml': f.POS,
                          'db/types.xml': f.TYPES, 'cfgspawnabletypes.xml': b'<spawnabletypes/>',
                          'cfglimitsdefinition.xml': b'<lists/>'}.items():
            (stock / name).write_bytes(raw)
        classes = f.CLASSES + (pending,)
        rows = f.house_rows() + f.calibration_rows() + f.house_rows(pending, state='control-failed')
        census = self.root / 'so-census.json'
        census.write_bytes(f.encode(f.census(rows, classes)))
        build, search, pack = [self.root / ('so-' + n) for n in ('build', 'search', 'pack')]
        with contextlib.redirect_stdout(io.StringIO()):
            ip.main(['templates', 'build', '--census', str(census), '--proto', str(stock / 'mapgroupproto.xml'),
                     '--pos', str(stock / 'mapgrouppos.xml'), '--types', str(stock / 'db/types.xml'), '--out', str(build)])
            self.assertEqual(sc.main(['--mapgroupproto', str(stock / 'mapgroupproto.xml'),
                                      '--types', str(stock / 'db/types.xml'), '--output-dir', str(search)]), 0)
            ip.main(['templates', 'assemble', '--build', str(build), '--search-groups', str(search),
                     '--stock', str(stock), '--out', str(pack)])
            ip.main(['templates', 'validate', str(pack)])
        docs = {p.name: json.loads(p.read_bytes()) for p in (pack / 'templates').iterdir()}
        rows = {r['BuildingClass']: r for n, d in docs.items() if n.startswith('classes-') for r in d['Rows']}
        self.assertEqual(rows[pending], {'BuildingClass': pending, 'Rooms': 'path_pending',
                                         'Furniture': 'path_pending', 'Search': 'covered'})
        env, _, _, logs, _, _ = runtime.fixture(docs)
        env['EngineHouse'] = lambda cls: cls in classes
        env['HCInteriorCatalog'].SearchType = lambda typ: typ in f.tpl.PROP_TYPES
        env['EnsureLoaded'](None)
        self.assertTrue(env['Loaded'](), logs)
        layout = env['Template'](pending)
        self.assertEqual(len(layout.Rooms), 0)
        self.assertTrue(all(site.Room == 0 for site in layout.SearchSites))
