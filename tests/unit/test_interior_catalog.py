"""Explicitly synthetic surveys exercise the real tool; no engine fit evidence."""
import copy
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.package import interior_catalog as tool

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / 'mods/HollowCountry/scripts/4_World/Interiors'
SOURCE_NAMES = ('HCInteriorCatalog.c', 'HCInteriorRules.c', 'HCInteriorStore.c')
PILOT = (
    ('family-pantry-v1', 'family', 'StaticObj_Furniture_case_a', 'StaticObj_Furniture_kitchen_chair_a'),
    ('family-storage-v1', 'family', 'StaticObj_Furniture_case_bedroom_b', 'StaticObj_Furniture_PaperBox_01_small_closed'),
    ('ransacked-storage-v1', 'ransacked', 'StaticObj_Furniture_case_a_open', 'StaticObj_Furniture_PaperBox_01_small_ransacked'),
)


class ExpandedCatalogTests(unittest.TestCase):
    def test_reviewed_catalog_and_runtime_search_allowlist_agree(self):
        source = (SOURCE_ROOT / 'HCInteriorCatalog.c').read_text()
        body = re.search(r'static bool SearchType\(string type\)\s*\{([^}]+)\}', source)[1]
        searchable = set(re.findall(r'type == "([^"]+)"', body))
        self.assertEqual(set(tool.SEARCH_TYPES), searchable)
        self.assertTrue(searchable <= set(tool.PROPS))
        for name, prop in tool.PROPS.items():
            self.assertIn('CfgVehicles/' + name, prop['Evidence'])
            self.assertTrue(prop['Evidence'].startswith('installed:'))
            if name in searchable:
                self.assertEqual('container', prop['Role'])
        self.assertEqual(PILOT, tool.PILOT)  # The legacy measured adapter keeps its three layouts.


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, indent=2) + '\n').encode()


def fixture():
    sources = {name: (SOURCE_ROOT / name).read_bytes() for name in SOURCE_NAMES}
    artifacts = {kind + '.log': ('SYNTHETIC ONLY: ' + kind).encode() for kind in
                 ('native-build', 'asset-config', 'geometry', 'door-clearance', 'stairs-clearance')}
    observations = [{'Path': name, 'Sha256': sha(data), 'Kind': name[:-4]} for name, data in artifacts.items()]
    layouts = []
    rules = []
    for index, (identity, history, storage, clutter) in enumerate(PILOT):
        props = []
        measured = []
        for i, name in enumerate((storage, clutter)):
            x = i * 3 + 1.25  # Arbitrary SYNTHETIC geometry, never a real house survey.
            props.append({'Type': name, 'Position': [x, 0.5, 1.25], 'Orientation': [45, 0, 0],
                          'Searchable': i == 0, 'SearchPoint': [0, 0.8, 0] if i == 0 else [0, 0, 0]})
            measured.append({'Index': i, 'Room': 'storage',
                             'Bounds': {'Min': [x - .4, 0, .8], 'Max': [x + .4, 1.8, 1.7]},
                             'Observation': 'geometry.log'})
        layouts.append({'Id': identity, 'History': history, 'Props': props,
                        'Survey': {'Bounds': {'Min': [0, -1, 0], 'Max': [8, 4, 8]},
                                   'Props': measured, 'Stairs': 'absent',
                                   'DoorObservation': 'door-clearance.log',
                                   'StairObservation': 'stairs-clearance.log',
                                   'MinimumClearanceMetres': .25,
                                   'Keepouts': [{'Id': 'entry', 'Kind': 'door',
                                                 'Bounds': {'Min': [0, -1, 4], 'Max': [2, 3, 6]}}]}})
        rules.append({'LayoutId': identity, 'Room': 'storage', 'History': history,
                      'Risk': 'civilian-survey', 'ItemGroups': ['household'],
                      'EmptyAllowed': True, 'MaxItems': 1,
                      'Selection': 'unweighted-review-only', 'Condition': 'unmodified-native',
                      'Storage': 'added-searchable-prop', 'Observation': 'geometry.log',
                      'Rationale': 'Synthetic household storage policy for offline validation only.'})
    record = {'SchemaVersion': 1, 'Synthetic': True,
              'Context': {'World': 'chernarusplus', 'Build': '1.30.164289',
                          'NativeScriptsSha256': '09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a',
                          'SurveyId': 'synthetic-house-survey', 'BuildingPosition': [1234.5, 100, 2345.5],
                          'BuildingOrientation': [90, 0, 0],
                          'AssetPboSha256': {
                              'structures_residential': 'f47cbd5f46f3597cc83fef822ed405cbd69de0f160c414b6deb843cc3ff2106a',
                              'structures_furniture': 'e5add5e387d17df70e680e966f1705f55940ba267dcb05e7b76b8013e9d4b448'},
                          'Operator': 'synthetic-test-operator', 'MeasuredAt': '2026-11-16T12:00:00+00:00',
                          'Method': 'DayZDiag', 'CoordinateBasis': 'building-model-local-metres',
                          'BuildObservation': 'native-build.log', 'AssetObservation': 'asset-config.log'},
              'SourceSha256': {name: sha(data) for name, data in sources.items()},
              'BuildingType': 'Land_House_1W01', 'CatalogVersion': 1,
              'Layouts': layouts, 'Observations': observations,
              'Policy': {'ItemGroups': [{'Id': 'household', 'Items': ['Rag', 'Battery9V']}],
                         'Rules': rules, 'Limits': {'Slots': 12, 'Rag': 4, 'Battery9V': 2}}}
    return record, sources, artifacts


class InteriorCatalogTests(unittest.TestCase):
    def prepare(self, record=None, sources=None, artifacts=None):
        r, s, a = fixture()
        return tool.prepare(encode(r if record is None else record),
                            s if sources is None else sources, a if artifacts is None else artifacts)

    def rejects(self, edit):
        record, sources, artifacts = fixture()
        edit(record)
        with self.assertRaises(ValueError):
            self.prepare(record, sources, artifacts)

    def test_measured_candidate_preserves_values_and_original_bytes(self):
        record, sources, artifacts = fixture()
        raw = encode(record)
        before = copy.deepcopy((record, sources, artifacts))
        files, report = tool.prepare(raw, sources, artifacts)
        self.assertEqual(files['measured-record.json'], raw)
        candidate = json.loads(files['interior-layouts.candidate.json'])
        self.assertEqual(candidate['Layouts'], [{k: v for k, v in layout.items() if k != 'Survey'} for layout in record['Layouts']])
        self.assertEqual(json.loads(files['context-policy.candidate.json']), record['Policy'])
        self.assertEqual(report['status'], 'synthetic-candidate-only')
        self.assertFalse(report['runtime_loader_wired'])
        self.assertFalse(report['production_accepted'])
        self.assertEqual(report['record_sha256'], sha(raw))
        self.assertEqual((record, sources, artifacts), before)
        self.assertEqual(tool.prepare(raw, sources, artifacts), (files, report))

    def test_caller_measurement_is_never_runtime_acceptance(self):
        record, _, _ = fixture()
        record['Synthetic'] = False
        _, report = self.prepare(record)
        self.assertEqual(report['status'], 'candidate-native-validation-required')
        self.assertFalse(report['production_accepted'])
        self.assertFalse(report['runtime_loader_wired'])

    def test_context_and_provenance_cannot_be_omitted_or_rebound(self):
        edits = [lambda r: r['Context'].update(World='enoch'),
                 lambda r: r['Context'].update(Build='1.29.000000'),
                 lambda r: r['Context'].update(NativeScriptsSha256='0' * 64),
                 lambda r: r['Context'].update(MeasuredAt='yesterday'),
                 lambda r: r['Context'].update(Operator=''),
                 lambda r: r['Context'].update(Method='guessed'),
                 lambda r: r['SourceSha256'].update({'HCInteriorCatalog.c': '0' * 64}),
                 lambda r: r.update(Observations=[]),
                 lambda r: r['Observations'][0].update(Sha256='0' * 64),
                 lambda r: r['Layouts'][0]['Survey'].update(DoorObservation='geometry.log')]
        for edit in edits:
            with self.subTest(edit=edit):
                self.rejects(edit)
        _, sources, artifacts = fixture()
        artifacts['geometry.log'] = b'tampered'
        with self.assertRaises(ValueError):
            self.prepare(artifacts=artifacts)
        sources['HCInteriorCatalog.c'] = sources['HCInteriorCatalog.c'].replace(b'family-pantry-v1', b'unknown-layout')
        record, _, _ = fixture()
        record['SourceSha256'] = {n: sha(v) for n, v in sources.items()}
        with self.assertRaises(ValueError):
            self.prepare(record, sources)

    def test_only_existing_pilot_assets_layouts_and_fields_are_allowed(self):
        for edit in (lambda r: r.update(BuildingType='OtherHouse'),
                     lambda r: r.update(CatalogVersion=2),
                     lambda r: r['Layouts'][0].update(Id='another-layout'),
                     lambda r: r['Layouts'][0]['Props'][0].update(Type='M4A1'),
                     lambda r: r['Layouts'][0]['Props'][0].update(Searchable=False),
                     lambda r: r['Layouts'][0]['Props'][0].update(Spawn=True),
                     lambda r: r.update(InitializeNewEpoch=True),
                     lambda r: r['Layouts'][0].update(History='military'),
                     lambda r: r['Layouts'].pop()):
            with self.subTest(edit=edit):
                self.rejects(edit)

    def test_finite_transforms_real_bounds_and_nonoverlap(self):
        for value in (float('nan'), float('inf'), -float('inf'), 101, True, '1'):
            with self.subTest(value=value):
                self.rejects(lambda r: r['Layouts'][0]['Props'][0]['Position'].__setitem__(0, value))
        for edit in (lambda r: r['Layouts'][0]['Props'][0].update(Position=[1, 2]),
                     lambda r: r['Layouts'][0]['Props'][0].update(Orientation=[361, 0, 0]),
                     lambda r: r['Layouts'][0]['Props'][0].update(SearchPoint=[0, 4, 0]),
                     lambda r: r['Layouts'][0]['Survey']['Props'][0]['Bounds'].update(Max=[-1, 1, 1]),
                     lambda r: r['Layouts'][0]['Survey']['Props'][0]['Bounds'].update(Max=[20, 20, 20]),
                     lambda r: r['Layouts'][0]['Props'][0].update(Position=[7, 0, 7]),
                     lambda r: r['Layouts'][0]['Survey']['Props'][1].update(Bounds=copy.deepcopy(r['Layouts'][0]['Survey']['Props'][0]['Bounds']))):
            with self.subTest(edit=edit):
                self.rejects(edit)

    def test_door_stair_observations_and_measured_clearance_required(self):
        for edit in (lambda r: r['Layouts'][0]['Survey'].update(Keepouts=[]),
                     lambda r: r['Layouts'][0]['Survey'].update(Stairs='unknown'),
                     lambda r: r['Layouts'][0]['Survey'].update(Stairs='present'),
                     lambda r: r['Layouts'][0]['Survey'].update(StairObservation='missing.log'),
                     lambda r: r['Layouts'][0]['Survey'].update(MinimumClearanceMetres=0),
                     lambda r: r['Layouts'][0]['Survey'].update(MinimumClearanceMetres=5),
                     lambda r: r['Layouts'][0]['Survey']['Keepouts'][0].update(Bounds={'Min': [0, -1, 0], 'Max': [2, 3, 2]})):
            with self.subTest(edit=edit):
                self.rejects(edit)
        record, _, _ = fixture()
        for layout in record['Layouts']:
            layout['Survey']['Stairs'] = 'present'
            layout['Survey']['Keepouts'].append({'Id': 'stairs', 'Kind': 'stairs', 'Bounds': {'Min': [5, -1, 4], 'Max': [7, 3, 7]}})
        self.prepare(record)

    def test_policy_links_measured_room_history_risk_and_groups_without_weights(self):
        for patch in ({'Room': 'kitchen'}, {'History': 'ransacked'}, {'Risk': ''},
                      {'Rationale': 'TODO'}, {'ItemGroups': ['missing']}, {'Weight': 10},
                      {'EmptyAllowed': False}, {'MaxItems': 2}, {'Selection': 'weighted'},
                      {'Condition': 'pristine'}, {'Storage': 'client-inventory'}, {'LayoutId': 'unknown'}):
            with self.subTest(patch=patch):
                self.rejects(lambda r: r['Policy']['Rules'][0].update(patch))
        for edit in (lambda r: r['Policy']['ItemGroups'][0].update(Items=['M4A1']),
                     lambda r: r['Policy']['Limits'].update(Rag=5),
                     lambda r: r['Policy']['Limits'].update(Slots=13),
                     lambda r: r['Policy']['Rules'].pop(),
                     lambda r: r['Policy']['Rules'].append(copy.deepcopy(r['Policy']['Rules'][0])),
                     lambda r: r['Policy']['ItemGroups'].append({'Id': 'unused', 'Items': ['Rag']})):
            with self.subTest(edit=edit):
                self.rejects(edit)

    def test_strict_json_bytes_collections_and_portable_paths(self):
        record, sources, artifacts = fixture()
        for raw in (b'{}' * 20000, b'{"x":1,"x":2}', b'[' * 2000, b'null', b'\xff'):
            with self.subTest(raw=raw[:20]), self.assertRaises(ValueError):
                tool.prepare(raw, sources, artifacts)
        for path in ('../escape', '/absolute', 'sub/../../escape', 'C:/escape', 'x\\escape', 'CON.log', 'a//b'):
            self.rejects(lambda r: r['Observations'][0].update(Path=path))
        self.rejects(lambda r: r['Observations'].extend(copy.deepcopy(r['Observations']) * 4))
        self.rejects(lambda r: r['Layouts'][0]['Survey']['Keepouts'].extend(copy.deepcopy(r['Layouts'][0]['Survey']['Keepouts']) * 40))
        with self.assertRaises(ValueError):
            self.prepare(artifacts=dict(artifacts, extra=b'unrelated'))
        with self.assertRaises(ValueError):
            self.prepare(artifacts=dict(artifacts, **{'geometry.log': b'x' * (1024 * 1024 + 1)}))

    def test_changed_native_allowlists_and_pilot_caps_fail_closed(self):
        for name, before, after in (
                ('HCInteriorCatalog.c', b'type == "Battery9V"', b'type == "M4A1"'),
                ('HCInteriorCatalog.c', b'type == "StaticObj_Furniture_case_a"', b'type == "OtherCase"'),
                ('HCInteriorRules.c', b'rags <= 4', b'rags <= 1')):
            record, sources, artifacts = fixture()
            self.assertIn(before, sources[name])
            sources[name] = sources[name].replace(before, after)
            record['SourceSha256'][name] = sha(sources[name])
            with self.subTest(name=name, after=after), self.assertRaises(ValueError):
                self.prepare(record, sources, artifacts)

    def test_actual_instance_context_and_assets_are_required(self):
        for patch in ({'SurveyId': ''}, {'BuildingPosition': [float('nan'), 0, 0]},
                      {'BuildingPosition': [40000, 0, 0]}, {'BuildingOrientation': [0, 999, 0]},
                      {'AssetPboSha256': {}}, {'AssetPboSha256': {'structures_furniture': '0' * 64}}):
            with self.subTest(patch=patch):
                self.rejects(lambda r: r['Context'].update(patch))

    def test_malformed_unhashable_fields_are_clean_validation_errors(self):
        for edit in (lambda r: r['Observations'][0].update(Kind=[]),
                     lambda r: r['Layouts'][0]['Survey']['Keepouts'][0].update(Kind={}),
                     lambda r: r['Layouts'][0]['Survey']['Props'][0].update(Room=[]),
                     lambda r: r['Context'].update(MeasuredAt={}),
                     lambda r: r['Layouts'][0]['Props'][0].update(Type=[])):
            with self.subTest(edit=edit):
                self.rejects(edit)

    def cli(self, root, *extra):
        return subprocess.run([sys.executable, '-B', '-m', 'tools.package.interior_catalog',
                               '--record', str(root / 'record.json'), '--sources', str(root / 'sources'),
                               '--artifacts', str(root / 'artifacts'), '--out', str(root / 'review'), *extra],
                              cwd=ROOT, capture_output=True, text=True, timeout=20,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))

    def staged(self, root):
        record, sources, artifacts = fixture()
        (root / 'sources').mkdir()
        (root / 'artifacts').mkdir()
        (root / 'record.json').write_bytes(encode(record))
        for name, data in sources.items():
            (root / 'sources' / name).write_bytes(data)
        for name, data in artifacts.items():
            (root / 'artifacts' / name).write_bytes(data)

    def test_cli_exports_fresh_review_only_and_preserves_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.staged(root)
            raw = (root / 'record.json').read_bytes()
            result = self.cli(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / 'review/measured-record.json').read_bytes(), raw)
            self.assertEqual(json.loads(result.stdout)['status'], 'synthetic-candidate-only')
            before = {p.name: p.read_bytes() for p in (root / 'review').iterdir()}
            self.assertNotEqual(self.cli(root).returncode, 0)
            self.assertEqual(before, {p.name: p.read_bytes() for p in (root / 'review').iterdir()})
            self.assertEqual((root / 'record.json').read_bytes(), raw)

    def test_cli_rejects_symlink_inputs_ancestors_and_output(self):
        for target in ('record.json', 'sources/HCInteriorCatalog.c', 'artifacts/geometry.log', 'sources', 'artifacts', 'review'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.staged(root)
                path = root / target
                saved = root / 'saved'
                if path.exists():
                    path.rename(saved)
                else:
                    saved.mkdir()
                try:
                    path.symlink_to(saved, target_is_directory=saved.is_dir())
                except OSError as exc:
                    self.skipTest(f'symlinks unavailable: {exc}')
                self.assertNotEqual(self.cli(root).returncode, 0)
                self.assertFalse((saved / 'measured-record.json').exists())

    def test_cli_oversized_input_and_unsafe_output_do_not_create_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.staged(root)
            (root / 'record.json').write_bytes(b' ' * 32768)
            self.assertNotEqual(self.cli(root).returncode, 0)
            self.assertFalse((root / 'review').exists())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.staged(root)
            result = self.cli(root, '--out', str(root / 'artifacts/new'))
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / 'artifacts/new').exists())


if __name__ == '__main__':
    unittest.main()
