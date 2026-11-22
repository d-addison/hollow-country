"""Floor-policy routing and physical capacity; native placement remains pending."""
import copy
import unittest
import xml.etree.ElementTree as ET

from tools.package import loot_boost as boost, loot_floor_policy as floor


class FloorPolicy(unittest.TestCase):
    def setUp(self):
        self.policy = floor.parse_policy(floor.shipped_policy())

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
        output, _ = floor.retag_types(data, self.policy)
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
        _, rows = floor.retag_types(types, policy)
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


if __name__ == '__main__':
    unittest.main()
