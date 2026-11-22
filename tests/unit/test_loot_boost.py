"""Physical CE capacity regressions; these do not prove engine spawning."""
import unittest
import xml.etree.ElementTree as ET

from tools.package import loot_boost as boost


def prototype(group_limit=8, container_limit=4, points=3, category='weapons'):
    return (f'<prototype><defaults><default name="group" lootmax="{group_limit}"/>'
            f'<default name="container" lootmax="{container_limit}"/></defaults>'
            '<group name="StaticTrain"><container name="SupplyBox">'
            f'<category name="{category}"/>'
            + ''.join(f'<point pos="{i} 0 0"/>' for i in range(points))
            + '</container></group></prototype>').encode()


class ProtoCapacity(unittest.TestCase):
    def assert_capacity(self, output):
        root = ET.fromstring(output)
        defaults = {d.get('name'): int(d.get('lootmax')) for d in root.iter('default')}
        for group in root.findall('group'):
            total = 0
            for container in group.findall('container'):
                limit = int(container.get('lootmax', str(defaults.get('container', 0))))
                self.assertLessEqual(limit, len(container.findall('point')))
                total += limit
            self.assertLessEqual(int(group.get('lootmax', str(defaults.get('group', 0)))), total)

    def test_inherited_weapon_limit_and_group_are_bounded(self):
        for category in boost.KEPT_CATEGORIES:
            with self.subTest(category=category):
                data = prototype(category=category, container_limit=2, points=5)
                output, _ = boost.scale_proto(data, 2)
                self.assert_capacity(output)
                container = ET.fromstring(output).find('group/container')
                self.assertEqual(int(container.get('lootmax')), 2)

    def test_scaled_container_cannot_exceed_points(self):
        for multiplier in (1, 2, 4):
            for points in (0, 1, 3, 10):
                with self.subTest(multiplier=multiplier, points=points):
                    output, _ = boost.scale_proto(prototype(points=points, category='tools'), multiplier)
                    self.assert_capacity(output)
                    root = ET.fromstring(output)
                    self.assertEqual(len(root.findall('group/container/point')), points)

    def test_explicit_mixed_limits_and_empty_elements(self):
        data = (b'<prototype><defaults><default name="container" lootmax="4"/></defaults>'
                b'<group name="StaticAirplaneCrate" lootmax="8">'
                b'<container name="weapons" lootmax="1"><category name="weapons"/>'
                b'<point pos="0 0 0"/><point pos="1 0 0"/></container>'
                b'<container name="tools" lootmax="2"><category name="tools"/>'
                b'<point pos="2 0 0"/><point pos="3 0 0"/></container>'
                b'<container name="empty"/></group><group name="empty" lootmax="7"/></prototype>')
        output, _ = boost.scale_proto(data, 2)
        self.assert_capacity(output)
        self.assertEqual(ET.fromstring(output).find('group/container').get('lootmax'), '1')
        self.assertEqual(boost._clamp_proto(output), output)

    def test_added_overlay_capacity_is_also_bounded(self):
        data = (b'<prototype><group name="Test" lootmax="4">\n'
                b'<container name="weapon" lootmax="1"><category name="weapons"/>'
                b'<point pos="0 0 0"/></container>\n</group></prototype>')
        group = ET.fromstring(data).find('group')
        points = [[1, 0, 0], [2, 0, 0]]
        overlay = {'groups': {'Test': {'stock_sha256': boost.group_pin(group), 'family': 'test',
                   'containers': {boost.CONTAINERS['floor']: {
                       'lootmax': len(points) + 1, 'categories': ['clothes'], 'tags': ['floor'],
                       'points': points}}}}}
        output, report = boost.scale_proto(data, 2, overlay)
        self.assert_capacity(output)
        added = ET.fromstring(output).findall('group/container')[1]
        self.assertEqual(int(added.get('lootmax')), len(points))
        self.assertEqual(report['points_added'], len(points))

    def test_verifier_rejects_group_or_container_overcapacity(self):
        data = prototype()
        valid, _ = boost.scale_proto(data, 2)
        for target in ('group', 'group/container'):
            root = ET.fromstring(valid)
            element = root.find(target)
            element.set('lootmax', str(len(root.findall('.//point')) + 1))
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'exceeds'):
                boost._verify_proto(data, ET.tostring(root), {})


if __name__ == '__main__':
    unittest.main()
