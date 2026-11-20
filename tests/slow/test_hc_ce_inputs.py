"""HC-57 offline loader regression. All source/stock fixtures here are SYNTHETIC."""
import copy
import json
import unittest
import xml.etree.ElementTree as ET

from tests.slow.test_ce_coverage import Fixture, blob, result_doc
from tools.package import ce_coverage as ce


class AuthoredInputTests(Fixture):
    def test_named_subset_requires_exact_source_class_pins_and_floor_categories(self):
        raw = blob(result_doc(self.stock))
        source = json.loads(raw)
        policy = {
            'schema': 1, 'kind': 'hc-ce-coverage-input', 'work_package': 'HC-57',
            'state': 'candidate', 'runtime_acceptance': 'pending', 'production_enabled': False,
            'refusal': 'HC57_NATIVE_ACCEPTANCE_PENDING',
            'source': {'evidence_role': 'design_input', 'result_sha256': ce.sha(raw),
                       'native_run_id': source['native_run_id'], 'pins': source['pins']},
            'groups': {name: {
                'source_points': sum(len(p) for p in spec['containers'].values()),
                'stock_instances': 1, 'container': 'lootFloor', 'usage': ['Town'],
                'categories': ['tools'], 'tags': ['floor'],
                'candidates': [{'id': name + '_floor_a', 'position': spec['containers']['lootFloor'][0]}]
            } for name, spec in source['groups'].items()}}
        files = ce.generate(raw, self.mission, input_bytes=blob(policy))
        delta = json.loads(files['coverage-delta.json'])
        self.assertEqual({name: 1 for name in ce.TARGET_GROUPS},
                         {name: len(spec['containers']['lootFloor']['points'])
                          for name, spec in delta['groups'].items()})
        self.assertEqual('pending', delta['runtime_acceptance'])
        ce.write_delta(self.tmp / 'subset', files)
        ce.install(self.tmp / 'subset', self.mission)
        ce.rollback(self.mission)
        self.assertEqual(self.stock, self.proto())
        for label in ('source', 'pin', 'class', 'category', 'unobserved', 'duplicate', 'name'):
            bad = copy.deepcopy(policy)
            first = bad['groups']['Land_Tenement_Small']
            if label == 'source': bad['source']['result_sha256'] = '0' * 64
            if label == 'pin': bad['source']['pins']['hook_sha256'] = '0' * 64
            if label == 'class': bad['groups']['Land_Office_Municipal2'] = bad['groups'].pop('Land_Tenement_Small')
            if label == 'category': first['categories'] = ['weapons']
            if label == 'unobserved': first['candidates'][0]['position'] = [2, 2, 2]
            if label == 'duplicate': first['candidates'].append(copy.deepcopy(first['candidates'][0]))
            if label == 'name': first['candidates'][0]['id'] = ''
            with self.subTest(label=label), self.assertRaises(ValueError):
                ce.generate(raw, self.mission, input_bytes=blob(bad))
        pending = copy.deepcopy(policy)
        pending.update(state='pending_survey', source=None, refusal='HC57_OFFICE_SURVEY_PENDING')
        pending['groups'] = {'Land_Office_Municipal2': dict(
            next(iter(policy['groups'].values())), source_points=None, candidates=[])}
        with self.assertRaisesRegex(ValueError, 'HC57_OFFICE_SURVEY_PENDING'):
            ce.generate(raw, self.mission, input_bytes=blob(pending))
        authored_path = self.tmp / 'input.json'
        authored_path.write_bytes(blob(pending))
        self.assertEqual('HC57_OFFICE_SURVEY_PENDING', ce.validate(input_path=authored_path)['reason'])
        authored_path.write_bytes(blob(policy))
        report = ce.validate(self.result_path(), self.mission, input_path=authored_path)
        self.assertEqual('input-valid', report['status'])
        self.assertEqual(0, report['observed'])
        self.assertEqual(ce.sha(ce.apply_delta(self.stock, delta)), report['effective_pin'])

        # Exercise the existing restricted census port with its explicit synthetic fixture, too.
        from tests.slow.test_ce_coverage_census import Fixture as CensusFixture
        census = CensusFixture()
        census.setUp()
        try:
            full, summary = census.convert(min_calibration=0.4)
            full_doc = json.loads(full)
            census_policy = copy.deepcopy(policy)
            census_policy['source'].update(result_sha256=ce.sha(full), native_run_id=full_doc['native_run_id'],
                                           pins=full_doc['pins'])
            root = ET.fromstring(census.stock)
            for name in ce.TARGET_GROUPS:
                decision = census_policy['groups'][name]
                group = next(g for g in root.iter('group') if g.get('name') == name)
                floor = next(c for c in group.findall('container') if c.get('name') == 'lootFloor')
                decision.update(source_points=summary['points'][name],
                                usage=[e.get('name') for e in group.findall('usage')],
                                categories=[e.get('name') for e in floor.findall('category')])
                decision['candidates'][0]['position'] = full_doc['groups'][name]['containers']['lootFloor'][0]
            subset, selected_summary = census.convert(min_calibration=0.4, input_bytes=blob(census_policy))
            self.assertEqual(summary['points'], selected_summary['source_points'])
            self.assertEqual({name: 1 for name in ce.TARGET_GROUPS}, selected_summary['points'])
            self.assertEqual(ce.generate(full, census.mission, input_bytes=blob(census_policy)),
                             ce.generate(subset, census.mission))
        finally:
            census.doCleanups()


if __name__ == '__main__':
    unittest.main()
