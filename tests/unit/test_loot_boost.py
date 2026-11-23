"""Physical CE capacity regressions; these do not prove engine spawning."""
import contextlib
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

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
    usages = ''.join(f'<usage name="{u}"/>' for u in group_usage.split(','))
    return (f'<prototype><defaults><default name="group" lootmax="2"/><default name="container" lootmax="1"/>'
            f'</defaults><group name="Barracks" lootmax="{group_limit}">{usages}{body}'
            '</group></prototype>').encode()


def limits_of(output):
    return {c.get('name'): int(c.get('lootmax')) for c in ET.fromstring(output).iter('container')}


class CapacityMap(unittest.TestCase):
    MILITARY = {'Military': 1.5, 'Police': 1.5, 'Prison': 1.5}

    def test_factor_one_is_a_no_op(self):
        data = military_proto()
        for capacity in ({}, {'Military': 1.0}):
            output, report = boost.scale_capacity_proto(data, capacity)
            self.assertEqual(output, data)
            self.assertEqual(report['groups'], 0)

    def test_military_group_and_containers_grow_within_points(self):
        output, report = boost.scale_capacity_proto(military_proto(), self.MILITARY, {'Barracks': 3})
        # weapons-only and zeroed containers keep their limits
        self.assertEqual(limits_of(output), {'Shelf': 6, 'Gun': 2, 'Empty': 0})
        group = ET.fromstring(output).find('group')
        self.assertEqual(int(group.get('lootmax')), 8)  # 1.5x of 6 is 9, capped at container capacity 8
        self.assertEqual((report['groups'], report['containers'], report['placed_groups']), (1, 1, 3))
        self.assertEqual((report['placed_lootmax_before'], report['placed_lootmax_after']), (18, 24))
        self.assertEqual(report['by_usage']['Military']['groups'], 1)
        ProtoCapacity().assert_capacity(output)

    def test_mixed_container_scales_and_weapon_only_containers_are_kept(self):
        data = military_proto(containers=[('Mixed', 'tools', 2, 6), ('Shelf', 'food', 2, 6),
                                          ('Gun', 'weapons', 2, 6), ('Boom', 'explosives', 2, 6)]).replace(
            b'<category name="tools"/>', b'<category name="tools"/><category name="weapons"/>')
        output, _ = boost.scale_capacity_proto(data, {'Military': 2.0})
        self.assertEqual(limits_of(output), {'Mixed': 4, 'Shelf': 4, 'Gun': 2, 'Boom': 2})

    def test_group_takes_the_largest_factor_over_its_usages(self):
        data = military_proto(group_usage='Farm,Police', group_limit=4, containers=[('Shelf', 'tools', 4, 16)])
        output, _ = boost.scale_capacity_proto(data, {'Farm': 1.25, 'Police': 2.0, 'Town': 3.0})
        self.assertEqual(limits_of(output), {'Shelf': 8})
        self.assertEqual(int(ET.fromstring(output).find('group').get('lootmax')), 8)
        output, _ = boost.scale_capacity_proto(data, {'Farm': 1.25, 'Town': 3.0})
        self.assertEqual(limits_of(output), {'Shelf': 5})  # ceil(4 x 1.25)

    def test_ceil_is_immune_to_float_noise(self):
        self.assertEqual(boost.ceil_scaled(10, 1.1), 11)
        self.assertEqual(boost.ceil_scaled(2, 1.25), 3)

    def test_group_limit_is_capped_at_80_and_a_larger_stock_limit_is_kept(self):
        data = military_proto(group_limit=60, containers=[('Shelf', 'tools', 100, 200)])
        output, _ = boost.scale_capacity_proto(data, {'Military': 2.0})
        self.assertEqual(int(ET.fromstring(output).find('group').get('lootmax')), 80)
        data = military_proto(group_limit=90, containers=[('Shelf', 'tools', 100, 200)])
        output, _ = boost.scale_capacity_proto(data, {'Military': 2.0})
        self.assertEqual(int(ET.fromstring(output).find('group').get('lootmax')), 90)

    def test_group_cannot_exceed_container_capacity(self):
        data = military_proto(group_limit=6, containers=[('Shelf', 'tools', 4, 4), ('Gun', 'weapons', 2, 2)])
        output, _ = boost.scale_capacity_proto(data, {'Military': 3.0})
        self.assertEqual(int(ET.fromstring(output).find('group').get('lootmax')), 6)

    def test_other_usages_are_untouched(self):
        for usage in ('Farm', 'Hunting', 'Town'):
            with self.subTest(usage=usage):
                data = military_proto(group_usage=usage)
                self.assertEqual(boost.scale_capacity_proto(data, self.MILITARY)[0], data)

    def test_single_factor_wrapper_still_scales_a_usage_set(self):
        output, report = boost.scale_military_proto(military_proto(), 1.5, frozenset({'Military'}))
        self.assertEqual(limits_of(output), {'Shelf': 6, 'Gun': 2, 'Empty': 0})
        self.assertEqual(report['factor'], 1.5)
        self.assertEqual(boost.scale_military_proto(military_proto(), 1.0, {'Military'})[0], military_proto())


def type_row(name, usages, nominal=10, minimum=6, category='tools'):
    return (f'<type name="{name}"><nominal>{nominal}</nominal><min>{minimum}</min><lifetime>100</lifetime>'
            f'<category name="{category}"/>' + ''.join(f'<usage name="{u}"/>' for u in usages) + '</type>')


def rows_of(output):
    return {t.get('name'): (int(t.findtext('nominal')), int(t.findtext('min'))) for t in ET.fromstring(output)}


class TypesScaling(unittest.TestCase):
    USAGES = frozenset({'Military', 'Police', 'Prison'})

    def test_military_only_rows_scale_again_shared_rows_do_not(self):
        data = ('<types>' + type_row('MilTool', ['Military']) + type_row('SharedTool', ['Military', 'Town'])
                + '</types>').encode()
        stats = {}
        output, _ = boost.scale_types(data, 2, military=(self.USAGES, 1.5), stats=stats)
        rows = rows_of(output)
        self.assertEqual(rows['MilTool'], (30, 18))
        self.assertEqual(rows['SharedTool'], (20, 12))
        self.assertEqual(stats['military_rows'], 1)
        for nominal, minimum in rows.values():
            self.assertLessEqual(minimum, nominal)

    def test_category_target_raises_to_a_multiple_of_stock_only_where_below(self):
        data = ('<types>' + type_row('Can', ['Town'], 10, 6, 'food') + type_row('Pot', ['Town'], 10, 6, 'tools')
                + type_row('Bag', ['Town'], 10, 6, 'containers') + type_row('Gun', ['Town'], 10, 6, 'weapons')
                + type_row('MilFood', ['Military'], 10, 6, 'food') + '</types>').encode()
        stats = {}
        output, _ = boost.scale_types(data, 1.5, military=(self.USAGES, 2.0), stats=stats,
                                      targets={'food': 2.0, 'containers': 1.25})
        rows = rows_of(output)
        self.assertEqual(rows['Can'], (20, 12))   # target 2x beats the 1.5x boost
        self.assertEqual(rows['Pot'], (15, 9))    # no tools target
        self.assertEqual(rows['Bag'], (15, 9))    # the 1.5x boost already exceeds 1.25x
        self.assertEqual(rows['Gun'], (10, 6))    # kept category
        self.assertEqual(rows['MilFood'], (30, 18))  # military factor already above the target
        self.assertEqual((stats['target_rows'], stats['target_nominal']), (1, 5))

    def test_medical_rows_use_their_own_target_or_fall_back_to_tools(self):
        data = ('<types>' + type_row('Morphine', ['Medic'], 10, 6) + type_row('Hammer', ['Medic'], 10, 6)
                + '</types>').encode()
        rows = rows_of(boost.scale_types(data, 1.0, targets={'tools': 2.0, 'medical': 3.0})[0])
        self.assertEqual((rows['Morphine'], rows['Hammer']), ((30, 18), (20, 12)))
        rows = rows_of(boost.scale_types(data, 1.0, targets={'tools': 2.0})[0])
        self.assertEqual((rows['Morphine'], rows['Hammer']), ((20, 12), (20, 12)))
        rows = rows_of(boost.scale_types(data, 1.0, targets={'medical': 2.0})[0])
        self.assertEqual((rows['Morphine'], rows['Hammer']), ((20, 12), (10, 6)))

    def test_targets_never_touch_roster_rows_or_construction_kits(self):
        data = ('<types>' + type_row('RosterTool', ['Town'], 10, 6) + type_row('FenceKit', ['Town'], 10, 6)
                + '</types>').encode()
        output, _ = boost.scale_types(data, 1.0, roster=frozenset({'rostertool'}), targets={'tools': 2.0})
        self.assertEqual(rows_of(output)['RosterTool'], (10, 6))
        self.assertEqual(rows_of(output)['FenceKit'], (10, 6))


class ScopedShelfLimit(unittest.TestCase):
    POLICY = {'floor_categories': {'clothes'}, '_classes': set()}

    def test_a_row_is_held_only_when_all_its_usages_are_pressured(self):
        self.assertTrue(boost.shelf_held({'Coast'}, None))  # no usage scope: the old global hold
        self.assertTrue(boost.shelf_held({'Coast'}, frozenset({'Coast', 'Farm'})))
        self.assertTrue(boost.shelf_held({'Coast', 'Farm'}, frozenset({'Coast', 'Farm'})))
        self.assertFalse(boost.shelf_held({'Coast', 'Town'}, frozenset({'Coast'})))
        self.assertFalse(boost.shelf_held(set(), frozenset({'Coast'})))
        self.assertTrue(boost.shelf_held(set(), frozenset({'*'})))

    def test_scale_types_holds_only_all_pressured_shelf_rows(self):
        data = ('<types>' + type_row('CoastRod', ['Coast']) + type_row('MixedRod', ['Coast', 'Town'])
                + type_row('TownPot', ['Town']) + type_row('Shirt', ['Coast'], category='clothes')
                + type_row('Anywhere', []) + '</types>').encode()
        rows = rows_of(boost.scale_types(data, 2, floor_only=self.POLICY, held=frozenset({'Coast'}))[0])
        self.assertEqual(rows['CoastRod'], (10, 6))   # held at its native quantity
        self.assertEqual(rows['MixedRod'], (20, 12))  # a usage with slack keeps the boost
        self.assertEqual(rows['TownPot'], (20, 12))
        self.assertEqual(rows['Shirt'], (20, 12))     # floor-eligible rows are never held
        self.assertEqual(rows['Anywhere'], (20, 12))  # the shared bucket is not pressured
        rows = rows_of(boost.scale_types(data, 2, floor_only=self.POLICY)[0])  # no scope: every shelf row held
        self.assertEqual([rows[n] for n in ('CoastRod', 'MixedRod', 'TownPot', 'Anywhere')], [(10, 6)] * 4)
        self.assertEqual(rows['Shirt'], (20, 12))

    def test_held_rows_are_not_raised_by_a_category_target(self):
        data = ('<types>' + type_row('CoastRod', ['Coast']) + type_row('TownPot', ['Town']) + '</types>').encode()
        rows = rows_of(boost.scale_types(data, 1.0, floor_only=self.POLICY, held=frozenset({'Coast'}),
                                         targets={'tools': 2.0})[0])
        self.assertEqual((rows['CoastRod'], rows['TownPot']), ((10, 6), (20, 12)))


class Settings(unittest.TestCase):
    def write(self, tmp, body):
        target = Path(tmp) / boost.SETTINGS
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('{"Multiplier": 2.0, "kind": "%s", "schema": 1%s}' % (boost.SETTINGS_KIND, body))
        return tmp

    def test_shipped_settings_are_valid_and_one_source_of_truth(self):
        capacity, targets = boost.default_capacity_map(), boost.default_category_map()
        self.assertTrue(capacity and targets)
        self.assertEqual(boost.default_military_multiplier(), capacity.get('Military', 1.0))
        self.assertNotIn(boost.MILITARY_KEY, boost._settings(boost.REPO_ROOT))

    def test_legacy_key_maps_to_military_police_prison(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, ', "MilitaryCapacityMultiplier": 1.5')
            self.assertEqual(boost.default_capacity_map(tmp), {'Military': 1.5, 'Police': 1.5, 'Prison': 1.5})
            self.assertEqual(boost.default_military_multiplier(tmp), 1.5)

    def test_new_key_and_older_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, ', "CapacityMultiplier": {"Town": 2, "Military": 1.5}, "CategoryMultiplier": {"food": 3}')
            self.assertEqual(boost.default_capacity_map(tmp), {'Military': 1.5, 'Town': 2.0})
            self.assertEqual(boost.default_category_map(tmp), {'food': 3.0})
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, '')
            self.assertEqual(boost.default_capacity_map(tmp), {})
            self.assertEqual(boost.default_category_map(tmp), {})
            self.assertEqual(boost.default_military_multiplier(tmp), 1.0)

    def test_both_capacity_keys_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, ', "MilitaryCapacityMultiplier": 1.5, "CapacityMultiplier": {"Town": 2}')
            with self.assertRaisesRegex(ValueError, 'mutually exclusive'):
                boost.default_capacity_map(tmp)

    def test_bad_values_are_refused(self):
        for bad in ({'Nowhere': 1.5}, {'Town': 0.9}, {'Town': 3.1}, {'Town': True}, {'Town': 'x'},
                    {'Town': float('nan')}, [], {1: 2}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                boost._capacity_map(bad)
        for bad in ({'weapons': 2.0}, {'food': 0.9}, {'food': 3.1}, {'food': True}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                boost._category_map(bad, 2.0)
        self.assertEqual(boost._category_map({'food': 3.0}, 2.0), {'food': 3.0})
        for bad in (0.9, 3.1, True, 'x', float('nan')):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                boost._military_multiplier(bad)


STOCK_FILES = {
    'cfgeconomycore.xml': '<economycore/>',
    'db/globals.xml': '<variables><var name="RespawnTypes" type="0" value="12"/></variables>',
    'db/types.xml': '<types>' + type_row('Hammer', ['Town', 'Police'], 10, 6) + type_row('Can', ['Town'], 10, 6, 'food')
                    + type_row('Rifle', ['Police'], 10, 6, 'weapons') + '</types>',
    'mapgroupproto.xml': '<prototype><defaults><default name="group" lootmax="2"/>'
                         '<default name="container" lootmax="1"/></defaults>'
                         '<group name="Station" lootmax="4"><usage name="Police"/>'
                         '<container name="Mixed" lootmax="2"><category name="tools"/><category name="weapons"/>'
                         + ''.join('<point pos="%d 0 0"/>' % i for i in range(8)) + '</container>'
                         '<container name="Gun" lootmax="2"><category name="weapons"/>'
                         + ''.join('<point pos="%d 1 0"/>' % i for i in range(4)) + '</container></group>'
                         '<group name="House" lootmax="3"><usage name="Town"/>'
                         '<container name="Shelf" lootmax="3"><category name="food"/>'
                         + ''.join('<point pos="%d 2 0"/>' % i for i in range(6)) + '</container></group></prototype>',
    'mapgrouppos.xml': '<map><group name="Station" pos="1 0 1"/><group name="Station" pos="5 0 5"/>'
                       '<group name="House" pos="9 0 9"/></map>',
}


def stock_mission(tmp):
    root = Path(tmp) / 'mission'
    for name, text in STOCK_FILES.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return root


def mission_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob('*')) if p.is_file()
            and not p.relative_to(root).parts[0] == boost.MANAGED}


PLAN = dict(points=None, floor_policy=None, buildings=None)


@contextlib.contextmanager
def settings_file(body):
    """Point loot_boost at a temporary settings.json (an absolute SETTINGS wins over the repo join)."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / 'settings.json'
        target.write_text('{"Multiplier": 2.0, "kind": "%s", "schema": 1%s}' % (boost.SETTINGS_KIND, body))
        with mock.patch.object(boost, 'SETTINGS', target):
            yield


SETTINGS_A = ', "CapacityMultiplier": {"Police": 2.0}, "CategoryMultiplier": {"food": 3.0}'
SETTINGS_B = ', "CapacityMultiplier": {"Town": 1.5}, "CategoryMultiplier": {"tools": 2.0}'


class PlanFromStock(unittest.TestCase):
    def test_plan_applies_the_capacity_map_and_category_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            mission = stock_mission(tmp)
            result = boost.plan(mission, 2.0, **PLAN, capacity={'Police': 2.0}, categories={'food': 3.0})
            plain = boost.plan(mission, 2.0, **PLAN, capacity={}, categories={})
            self.assertEqual((result['capacity_multiplier'], result['category_multiplier']),
                             ({'Police': 2.0}, {'food': 3.0}))
            files = {name: after for name, _before, after in result['files']}
            base = {name: after for name, _before, after in plain['files']}
            self.assertEqual(rows_of(base['db/types.xml'])['Can'], (20, 12))
            self.assertEqual(rows_of(files['db/types.xml'])['Can'], (30, 18))
            self.assertEqual(rows_of(files['db/types.xml'])['Hammer'], rows_of(base['db/types.xml'])['Hammer'])
            grown, plain_limits = limits_of(files['mapgroupproto.xml']), limits_of(base['mapgroupproto.xml'])
            self.assertGreater(grown['Mixed'], plain_limits['Mixed'])
            self.assertEqual((grown['Gun'], grown['Shelf']), (plain_limits['Gun'], plain_limits['Shelf']))
            lines = boost.describe(result)
            self.assertTrue(any('capacity map' in l and 'Police: 2.0' in l for l in lines), lines)
            self.assertTrue(any('category targets' in l and 'food: 3.0' in l for l in lines), lines)

    def test_settings_b_does_not_depend_on_settings_a(self):
        """Plan and install A, roll back, then B: B is what a fresh install of B on the stock bytes gives."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as fresh:
            mission, clean = stock_mission(tmp), stock_mission(fresh)
            stock = mission_bytes(mission)
            with settings_file(SETTINGS_A):
                plan_a = boost.plan(mission, **PLAN)
                boost.install(mission, None, None, floor_policy=None)
            self.assertNotEqual(mission_bytes(mission), stock)
            boost.rollback(mission)
            self.assertEqual(mission_bytes(mission), stock)
            with settings_file(SETTINGS_B):
                boost.install(mission, None, None, floor_policy=None)
                with self.assertRaisesRegex(ValueError, 'already installed'):
                    boost.install(mission, None, None, floor_policy=None)  # never applied twice
                boost.install(clean, None, None, floor_policy=None)
            self.assertEqual(mission_bytes(mission), mission_bytes(clean))
            self.assertNotEqual(plan_a['capacity_multiplier'], {'Town': 1.5})
            self.assertEqual(rows_of(mission_bytes(mission)['db/types.xml'])['Can'], (20, 12))  # A's 3x food target is gone

    def test_plan_is_a_pure_function_of_the_bytes_and_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            mission = stock_mission(tmp)
            first = boost.plan(mission, 2.0, **PLAN, capacity={'Police': 2.0}, categories={'food': 3.0})
            other = boost.plan(mission, 2.0, **PLAN, capacity={'Town': 1.5}, categories={'tools': 2.0})
            again = boost.plan(mission, 2.0, **PLAN, capacity={'Town': 1.5}, categories={'tools': 2.0})
            self.assertEqual(other['files'], again['files'])
            self.assertNotEqual(first['files'], other['files'])
            self.assertEqual(mission_bytes(mission), {n: t.encode() for n, t in STOCK_FILES.items()})

    def test_receipt_records_both_maps_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp, settings_file(SETTINGS_A):
            mission = stock_mission(tmp)
            stock = mission_bytes(mission)
            boost.install(mission, None, None, floor_policy=None)
            receipt = json.loads((mission / boost.MANAGED / 'receipt.json').read_bytes())
            self.assertEqual((receipt['capacity_multiplier'], receipt['category_multiplier']),
                             ({'Police': 2.0}, {'food': 3.0}))
            self.assertNotIn('military_multiplier', receipt)
            self.assertEqual(boost.rollback(mission)['restored'], len(receipt['files']) - sum(
                1 for r in receipt['files'] if r['before'] == r['after']))
            self.assertEqual(mission_bytes(mission), stock)
            self.assertFalse((mission / boost.MANAGED).exists())

    def test_rollback_reads_an_older_receipt_carrying_military_multiplier(self):
        with tempfile.TemporaryDirectory() as tmp, settings_file(SETTINGS_A):
            mission = stock_mission(tmp)
            stock = mission_bytes(mission)
            boost.install(mission, None, None, floor_policy=None)
            path = mission / boost.MANAGED / 'receipt.json'
            receipt = json.loads(path.read_bytes())
            del receipt['capacity_multiplier'], receipt['category_multiplier']
            receipt['military_multiplier'] = 1.5
            path.write_bytes(json.dumps(receipt).encode())
            boost.rollback(mission)
            self.assertEqual(mission_bytes(mission), stock)

    def test_a_malformed_new_receipt_key_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp, settings_file(SETTINGS_A):
            mission = stock_mission(tmp)
            boost.install(mission, None, None, floor_policy=None)
            path = mission / boost.MANAGED / 'receipt.json'
            receipt = json.loads(path.read_bytes())
            receipt['capacity_multiplier'] = 1.5
            path.write_bytes(json.dumps(receipt).encode())
            with self.assertRaises(ValueError):
                boost.rollback(mission)


if __name__ == '__main__':
    unittest.main()
