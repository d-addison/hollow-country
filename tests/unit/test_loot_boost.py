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


def military_proto(group_usage='Military', group_limit=6, containers=None):
    containers = containers or [('Shelf', 'tools', 4, 6), ('Gun', 'weapons', 2, 4), ('Empty', 'tools', 0, 4)]
    body = ''.join(
        f'<container name="{n}" lootmax="{m}"><category name="{c}"/>'
        + ''.join(f'<point pos="{i} 0 0"/>' for i in range(p)) + '</container>'
        for n, c, m, p in containers)
    return (f'<prototype><defaults><default name="group" lootmax="2"/><default name="container" lootmax="1"/>'
            f'</defaults><group name="Barracks" lootmax="{group_limit}"><usage name="{group_usage}"/>{body}'
            '</group></prototype>').encode()


class MilitaryCapacity(unittest.TestCase):
    USAGES = frozenset({'Military', 'Police', 'Prison'})

    def test_factor_one_is_a_no_op(self):
        data = military_proto()
        output, report = boost.scale_military_proto(data, 1.0, self.USAGES)
        self.assertEqual(output, data)
        self.assertEqual(report['groups'], 0)

    def test_military_group_and_containers_grow_within_points(self):
        output, report = boost.scale_military_proto(military_proto(), 1.5, self.USAGES, {'Barracks': 3})
        root = ET.fromstring(output)
        limits = {c.get('name'): int(c.get('lootmax')) for c in root.iter('container')}
        self.assertEqual(limits, {'Shelf': 6, 'Gun': 2, 'Empty': 0})  # weapons and zeroed containers keep limits
        group = root.find('group')
        self.assertEqual(int(group.get('lootmax')), 8)  # 1.5x of 6 is 9, capped at container capacity 8
        self.assertLessEqual(int(group.get('lootmax')), sum(limits.values()))
        self.assertEqual((report['groups'], report['containers'], report['placed_groups']), (1, 1, 3))
        self.assertEqual((report['placed_lootmax_before'], report['placed_lootmax_after']), (18, 24))
        ProtoCapacity().assert_capacity(output)

    def test_group_cannot_exceed_container_capacity(self):
        data = military_proto(group_limit=6, containers=[('Shelf', 'tools', 4, 4), ('Gun', 'weapons', 2, 2)])
        output, _ = boost.scale_military_proto(data, 3.0, self.USAGES)
        self.assertEqual(int(ET.fromstring(output).find('group').get('lootmax')), 6)

    def test_other_usages_are_untouched(self):
        for usage in ('Farm', 'Hunting', 'Town'):
            with self.subTest(usage=usage):
                data = military_proto(group_usage=usage)
                self.assertEqual(boost.scale_military_proto(data, 2.0, self.USAGES)[0], data)

    def test_military_only_rows_scale_again_shared_rows_do_not(self):
        def row(name, usages):
            return (f'<type name="{name}"><nominal>10</nominal><min>6</min><lifetime>100</lifetime>'
                    '<category name="tools"/>' + ''.join(f'<usage name="{u}"/>' for u in usages) + '</type>')
        data = ('<types>' + row('MilTool', ['Military']) + row('SharedTool', ['Military', 'Town'])
                + '</types>').encode()
        stats = {}
        output, _ = boost.scale_types(data, 2, military=(self.USAGES, 1.5), stats=stats)
        rows = {t.get('name'): (int(t.findtext('nominal')), int(t.findtext('min')))
                for t in ET.fromstring(output)}
        self.assertEqual(rows['MilTool'], (30, 18))
        self.assertEqual(rows['SharedTool'], (20, 12))
        self.assertEqual(stats['military_rows'], 1)
        for nominal, minimum in rows.values():
            self.assertLessEqual(minimum, nominal)


class MilitarySetting(unittest.TestCase):
    def test_shipped_default_and_range(self):
        self.assertEqual(boost.default_military_multiplier(), 1.5)
        self.assertEqual(boost._military_multiplier(1), 1.0)
        for bad in (0.9, 3.1, True, 'x', float('nan')):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                boost._military_multiplier(bad)

    def test_older_settings_file_means_no_change(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / boost.SETTINGS
            target.parent.mkdir(parents=True)
            target.write_text('{"Multiplier": 2.0, "kind": "%s", "schema": 1}' % boost.SETTINGS_KIND)
            self.assertEqual(boost.default_military_multiplier(tmp), 1.0)


if __name__ == '__main__':
    unittest.main()
