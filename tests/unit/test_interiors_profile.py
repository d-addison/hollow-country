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
