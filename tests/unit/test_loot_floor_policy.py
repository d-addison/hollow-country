"""Floor-policy routing and physical capacity; native placement remains pending."""
import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest
import xml.etree.ElementTree as ET

from tools.package import loot_boost as boost, loot_floor_policy as floor


class FloorPolicy(unittest.TestCase):
    def setUp(self):
        self.policy = floor.parse_policy(floor.shipped_policy())
        self.fit = {'threshold': 0.30, 'classes': {name: {
            'reason': 'fits', 'fit_share': 0.45, 'candidate_points': 20, 'longest_m': 0.1}
            for name in ('SmallPart', 'Tool')}}

    def test_shipped_motorbike_wheels_keep_native_routes_and_quantities(self):
        data = (boost.REPO_ROOT / 'mission/hollow-country/ce/types.xml').read_bytes()
        output, rows = floor.retag_types(data, self.policy)
        old = {t.get('name'): t for t in ET.fromstring(data)}
        new = {t.get('name'): t for t in ET.fromstring(output)}
        wheels = [name for name in old if floor._shelf_exempt(
            name, {c.get('name') for c in old[name].findall('category')})]
        self.assertTrue(wheels)
        for name in wheels:
            self.assertEqual(ET.tostring(old[name]), ET.tostring(new[name]))
        self.assertTrue(all(before == after for name, _, before, after, _, _ in rows if name in wheels))

    def test_small_lootdispatch_still_retagged_and_wheel_tags_preserved(self):
        data = (b'<types><type name="SmallPart"><nominal>8</nominal><category name="lootdispatch"/>'
                b'<usage name="Industrial"/></type><type name="Motorbike_03_Wheel_1">'
                b'<nominal>8</nominal><min>4</min><category name="lootdispatch"/>'
                b'<tag name="garage"/><usage name="Industrial"/></type></types>')
        output, _ = floor.retag_types(data, self.policy, shelf_fit=self.fit)
        root = ET.fromstring(output)
        self.assertEqual(root.find('type/tag').get('name'), self.policy['shelf_tag'])
        self.assertEqual(root.findall('type')[1].find('tag').get('name'), 'garage')
        self.assertEqual(root.findall('type')[1].findtext('nominal'), '8')

    def fixture(self):
        policy = copy.deepcopy(self.policy)
        policy['receivers'] = {}
        policy['capacity']['enabled'] = False
        cname = policy['floor_container_names'][0]
        data = (f'<prototype><defaults><default name="container" lootmax="2"/></defaults>'
                f'<group name="TestGarage" lootmax="4"><usage name="Industrial"/>'
                f'<container name="{cname}" lootmax="2"><category name="tools"/>'
                '<point pos="0 0 0"/><point pos="1 0 0"/></container>'
                '<container name="shelf" lootmax="2"><category name="tools"/>'
                f'<tag name="{policy["shelf_tag"]}"/>'
                '<point pos="0 2 0"/><point pos="1 2 0"/></container></group></prototype>').encode()
        types = b'<types><type name="Tool"><nominal>8</nominal><category name="tools"/></type></types>'
        _, rows = floor.retag_types(types, policy, shelf_fit=self.fit)
        return data, rows, policy

    def test_floor_reduction_also_clamps_parent(self):
        data, rows, policy = self.fixture()
        output, report = floor.rebalance_proto(data, [rows], policy)
        root = ET.fromstring(output)
        boost._verify_proto_caps(root)
        limits = [int(c.get('lootmax')) for c in root.findall('group/container')]
        self.assertEqual(int(root.find('group').get('lootmax')), sum(limits))
        self.assertGreater(report['displaced'], 0)
        self.assertEqual(report['displaced'], report['transferred'] + report['unplaced'])

    def test_floor_verifier_rejects_overcapacity(self):
        data, rows, policy = self.fixture()
        output, report = floor.rebalance_proto(data, [rows], policy)
        root = ET.fromstring(output)
        root.find('group').set('lootmax', '999')
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            floor._verify_proto(data, ET.tostring(root), report, policy)

    def test_receiver_removal_clamps_source_and_parent(self):
        data, _, policy = self.fixture()
        root = ET.fromstring(data)
        source = root.find('group/container')
        point = source.findall('point')[0]
        receiver = ET.SubElement(root.find('group'), 'container', name=floor.SURFACE_RECEIVER, lootmax='1')
        receiver.append(copy.deepcopy(point))
        report = {'groups': {'TestGarage': {'relocations': [
            {'source': source.get('name'), 'pos': point.get('pos'), 'target': floor.SURFACE_RECEIVER}]}}}
        floor_report = {'floor_nonclothing_slots_after': 0}
        output = floor.finish_receivers(ET.tostring(root), report, policy, floor_report)
        boost._verify_proto_caps(ET.fromstring(output))
        self.assertEqual(ET.fromstring(output).find('group/container').get('lootmax'), '1')


    def test_shelf_admission_preserves_refused_rows_exactly(self):
        rows = [b'<type name="Pipe"><nominal>8</nominal><min>3</min><category name="tools"/></type>',
                b'<type name="LowFloor"><category name="tools"/><tag name="floor"/></type>',
                b'<type name="Missing"><nominal>5</nominal><usage name="Farm"/></type>',
                b'<type name="StockShelf"><category name="tools"/><tag name="floor"/><tag name="shelves"/></type>',
                b'<type name="SmallPart"><category name="tools"/></type>']
        evidence = copy.deepcopy(self.fit)
        evidence['classes']['Pipe'] = dict(reason='below_threshold', fit_share=.01, candidate_points=100, longest_m=2.0)
        evidence['classes']['LowFloor'] = dict(reason='below_threshold', fit_share=.1, candidate_points=100, longest_m=2.0)
        data = b'<types>\r\n' + b'\r\n'.join(rows) + b'\r\n</types>'
        output, result = floor.retag_types(data, self.policy, shelf_fit=evidence)
        for row in rows[:4]:
            self.assertIn(row, output)
        self.assertEqual(floor.kept_vanilla(result, self.policy, evidence), ['LowFloor', 'Missing', 'Pipe'])
        self.assertEqual(ET.fromstring(output).findall('type')[-1].find('tag').get('name'), 'shelves')

    def test_shelf_fit_validation_is_fail_closed(self):
        doc = dict(schema=1, kind=floor.SHELF_FIT_KIND, threshold=.30, classes=self.fit['classes'])
        self.assertEqual(floor.parse_shelf_fit(json.dumps(doc).encode())['threshold'], .30)
        for field, value in [('threshold', 0), ('threshold', True), ('threshold', float('nan')),
                             ('schema', 2), ('schema', True), ('kind', 'other'), ('classes', [])]:
            bad = dict(doc, **{field: value})
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                floor.parse_shelf_fit(json.dumps(bad).encode())
        for field, value in [('fit_share', -.1), ('fit_share', 1.1), ('fit_share', True),
                             ('fit_share', .299), ('candidate_points', 0), ('longest_m', None),
                             ('reason', 'typo')]:
            bad = copy.deepcopy(doc)
            bad['classes']['Tool'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                floor.parse_shelf_fit(json.dumps(bad).encode())
        bad = dict(doc, classes={'bad/name': self.fit['classes']['Tool']})
        with self.assertRaises(ValueError):
            floor.parse_shelf_fit(json.dumps(bad).encode())
        for raw in (b'{', b'\xff', b' ' * (floor.MAX_SHELF_FIT_BYTES + 1),
                    b'{"schema":1,"schema":1}'):
            with self.assertRaises(ValueError):
                floor.parse_shelf_fit(raw)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'requires readable'):
                floor.load_shelf_fit(tmp)
            path = Path(tmp) / floor.SHELF_FIT
            path.parent.mkdir(parents=True)
            path.write_bytes(b'{')
            with self.assertRaisesRegex(ValueError, 'invalid shelf-fit'):
                floor.load_shelf_fit(tmp)

    def test_enabled_plan_requires_fit_before_any_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            mission = Path(tmp)
            (mission / 'db').mkdir()
            policy = floor.shipped_policy()
            config = mission / 'config'
            config.mkdir()
            (config / 'military-loot.json').write_bytes((boost.REPO_ROOT / 'config/military-loot.json').read_bytes())
            roster = mission / 'tools/package/firearms_roster.json'
            roster.parent.mkdir(parents=True)
            roster.write_bytes((boost.REPO_ROOT / 'tools/package/firearms_roster.json').read_bytes())
            with self.assertRaisesRegex(ValueError, 'requires readable'):
                boost.plan(mission, multiplier=1, capacity={}, categories={}, knobs=boost.default_knobs(),
                           floor_policy=policy, root=mission)

    def test_disabled_policy_does_not_load_companion(self):
        policy = json.loads(floor.shipped_policy())
        policy['enabled'] = False
        parsed, _ = boost._floor_policy(json.dumps(policy).encode())
        self.assertIsNone(parsed)
        with patch.object(floor, 'load_shelf_fit', side_effect=AssertionError('must not load')):
            # A minimal mission reaches normal input validation, not shelf-fit loading.
            with tempfile.TemporaryDirectory() as tmp:
                mission = Path(tmp)
                (mission / 'db').mkdir()
                with self.assertRaises((ValueError, FileNotFoundError)):
                    boost.plan(mission, multiplier=1, capacity={}, categories={}, knobs=boost.default_knobs(),
                               floor_policy=json.dumps(policy).encode())


if __name__ == '__main__':
    unittest.main()
