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

    def test_group_cap_knob_raises_the_ceiling_per_usage_and_is_clamped_to_container_capacity(self):
        data = military_proto(group_limit=60, containers=[('Shelf', 'tools', 100, 200)])
        for cap, want in ((None, 80), ({}, 80), ({'Default': 70}, 70), ({'Military': 150}, 120),
                          ({'Military': 400}, 120), ({'Police': 150}, 80), ({'Default': 1}, 60)):
            with self.subTest(cap=cap):
                output, _ = boost.scale_capacity_proto(data, {'Military': 2.0}, None, cap)
                self.assertEqual(int(ET.fromstring(output).find('group').get('lootmax')), want)  # ceil(60 x 2) = 120
        data = military_proto(group_usage='Farm,Military', group_limit=60, containers=[('Shelf', 'tools', 100, 200)])
        output, _ = boost.scale_capacity_proto(data, {'Military': 2.0}, None, {'Default': 70, 'Farm': 100})
        self.assertEqual(int(ET.fromstring(output).find('group').get('lootmax')), 100)  # largest cap over the usages
        data = military_proto(group_limit=6, containers=[('Shelf', 'tools', 4, 4), ('Gun', 'weapons', 2, 2)])
        output, _ = boost.scale_capacity_proto(data, {'Military': 3.0}, None, {'Military': 400})
        self.assertEqual(int(ET.fromstring(output).find('group').get('lootmax')), 6)  # container capacity wins

    def test_group_cap_validation(self):
        self.assertEqual(boost.knobs_of({})['group_cap'], {})
        self.assertEqual(boost.knobs_of({'GroupLootmaxCap': {'Town': 160, 'Default': 90}})['group_cap'],
                         {'Default': 90, 'Town': 160})
        for bad in ({'Nowhere': 90}, {'Town': 0}, {'Town': 8.1}, {'Town': 90.5}, {'Town': True}, {'Default': 'x'}, []):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                boost.knobs_of({'GroupLootmaxCap': bad})

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
        for bad in ({'Nowhere': 1.5}, {'Town': 0.9}, {'Town': 8.1}, {'Town': True}, {'Town': 'x'},
                    {'Town': float('nan')}, [], {1: 2}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                boost._capacity_map(bad)
        for bad in ({'weapons': 2.0}, {'food': 0.9}, {'food': boost.MAX_CATEGORY + 0.1}, {'food': True}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                boost._category_map(bad, 2.0)
        # a target may exceed Multiplier: the owner's food and medical totals are ~4-6x stock under Multiplier 2
        self.assertEqual(boost._category_map({'food': 4.2, 'medical': 5.7}, 2.0), {'food': 4.2, 'medical': 5.7})
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
            result = boost.plan(mission, 2.0, **PLAN, capacity={'Police': 2.0}, categories={'food': 3.0}, knobs={})
            plain = boost.plan(mission, 2.0, **PLAN, capacity={}, categories={}, knobs={})
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
            first = boost.plan(mission, 2.0, **PLAN, capacity={'Police': 2.0}, categories={'food': 3.0}, knobs={})
            other = boost.plan(mission, 2.0, **PLAN, capacity={'Town': 1.5}, categories={'tools': 2.0}, knobs={})
            again = boost.plan(mission, 2.0, **PLAN, capacity={'Town': 1.5}, categories={'tools': 2.0}, knobs={})
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


SUPPLY_A = (', "UsageMultiplier": {"Town": 3.0}, "MilitaryTierMultiplier": {"Tier4": 2.0},'
            ' "FirearmsMultiplier": {"weapon": 2.0}, "LootDamageMax": 0.6, "Refill": {"RestockMin": 5000}')
SUPPLY_B = ', "UsageMultiplier": {"Police": 2.5}'
SUPPLY_A = SUPPLY_A + ', "GroupLootmaxCap": {"Default": 90, "Town": 160}'


def supply_row(name, usages, nominal=10, minimum=6, category='tools', tiers=(), restock=300):
    return (f'<type name="{name}"><nominal>{nominal}</nominal><min>{minimum}</min><restock>{restock}</restock>'
            f'<category name="{category}"/>' + ''.join(f'<usage name="{u}"/>' for u in usages)
            + ''.join(f'<value name="{t}"/>' for t in tiers) + '</type>')


class SupplyKnobs(unittest.TestCase):
    def scale(self, rows, multiplier=2, **kw):
        return rows_of(boost.scale_types(('<types>' + ''.join(rows) + '</types>').encode(), multiplier, **kw)[0])

    def test_row_factor_is_the_largest_over_its_usages_and_unlisted_usages_count_as_multiplier(self):
        rows = self.scale([supply_row('Town1', ['Town']), supply_row('Mixed', ['Town', 'Farm']),
                           supply_row('Farm1', ['Farm']), supply_row('NoUsage', [])],
                          knobs={'usage': {'Town': 3.5}})
        self.assertEqual(rows['Town1'], (35, 21))
        self.assertEqual(rows['Mixed'], (35, 21))   # max(3.5, Multiplier for Farm)
        self.assertEqual(rows['Farm1'], (20, 12))   # no entry: Multiplier
        self.assertEqual(rows['NoUsage'], (20, 12))
        rows = self.scale([supply_row('Mixed', ['Town', 'Farm'])], knobs={'usage': {'Town': 1.0}})
        self.assertEqual(rows['Mixed'], (20, 12))   # an entry below Multiplier cannot lower a row that has a better usage

    def test_usage_map_replaces_the_legacy_military_step_for_its_usages(self):
        usages = frozenset({'Military', 'Police', 'Prison'})
        rows = self.scale([supply_row('Mil', ['Military']), supply_row('Pol', ['Police'])], military=(usages, 1.5),
                          knobs={'usage': {'Military': 3.0}})
        self.assertEqual(rows['Mil'], (30, 18))   # the usage factor, not 2 x 3.0 x 1.5
        self.assertEqual(rows['Pol'], (30, 18))   # the legacy step still covers a usage the map leaves out

    def test_tier_factor_is_the_mean_over_a_military_rows_tiers(self):
        tiers = {'Tier1': 1.0, 'Tier2': 1.0, 'Tier3': 1.5, 'Tier4': 1.5}
        rows = self.scale([supply_row('Low', ['Military'], tiers=['Tier1', 'Tier2']),
                           supply_row('All', ['Military'], tiers=['Tier1', 'Tier2', 'Tier3', 'Tier4']),
                           supply_row('High', ['Military'], tiers=['Tier3', 'Tier4']),
                           supply_row('Plain', ['Military']), supply_row('Town', ['Town'], tiers=['Tier4'])],
                          knobs={'tier': tiers})
        self.assertEqual([rows[k] for k in ('Low', 'All', 'High', 'Plain', 'Town')],
                         [(20, 12), (25, 15), (30, 18), (20, 12), (20, 12)])

    def test_roster_rows_scale_by_kind_only_with_a_kind_map_and_a_firearms_factor(self):
        data = [supply_row('Gun', ['Police'], category='weapons'), supply_row('Mag', ['Police'], category='weapons'),
                supply_row('Pot', ['Police'])]
        roster = {'gun': 'weapon', 'mag': 'magazine'}
        rows = self.scale(data, roster=roster, knobs={'firearms': {'weapon': 1.5}})
        self.assertEqual((rows['Gun'], rows['Mag'], rows['Pot']), ((15, 9), (10, 6), (20, 12)))
        rows = self.scale(data, roster=frozenset(roster), knobs={'firearms': {'weapon': 1.5}})
        self.assertEqual(rows['Gun'], (10, 6))     # a plain roster set keeps the old behaviour
        rows = self.scale(data, roster=roster)
        self.assertEqual(rows['Gun'], (10, 6))

    def test_restock_floor_raises_only_lower_restocks_and_is_verified(self):
        data = ('<types>' + supply_row('Low', ['Town'], restock=300) + supply_row('High', ['Town'], restock=90000)
                + '</types>').encode()
        stats = {}
        output, _ = boost.scale_types(data, 2, stats=stats, knobs={'refill': {'RestockMin': 3600}})
        found = {t.get('name'): int(t.findtext('restock')) for t in ET.fromstring(output)}
        self.assertEqual(found, {'Low': 3600, 'High': 90000})
        self.assertEqual(stats['restock_rows'], 1)
        output, _ = boost.scale_types(data, 2, knobs={})
        self.assertEqual({t.get('name'): int(t.findtext('restock')) for t in ET.fromstring(output)},
                         {'Low': 300, 'High': 90000})

    def test_settings_validation(self):
        for key, bad in (('UsageMultiplier', {'Nowhere': 2.0}), ('UsageMultiplier', {'Town': 0.5}),
                         ('UsageMultiplier', {'Town': 8.5}), ('MilitaryTierMultiplier', {'Tier9': 1.0}),
                         ('MilitaryTierMultiplier', {'Tier3': 5.0}), ('FirearmsMultiplier', {'grenade': 2.0}),
                         ('FirearmsMultiplier', {'weapon': 0.5}), ('LootDamageMax', 1.5), ('LootDamageMax', True),
                         ('Refill', {'RestockMin': -1}), ('Refill', {'RestockMin': 1.5}),
                         ('Refill', {'RespawnTypesFactor': 9.0}), ('Refill', {'Other': 1})):
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                boost.knobs_of({key: bad})
        self.assertEqual(boost.knobs_of({})['refill'], {'RestockMin': 0, 'RespawnTypesFactor': 1.0})
        self.assertIsNone(boost.knobs_of({})['loot_damage_max'])

    def test_shipped_supply_settings_meet_the_owner_targets(self):
        knobs = boost.default_knobs()
        self.assertEqual(knobs['loot_damage_max'], 0.6)
        self.assertGreater(knobs['tier']['Tier3'], knobs['tier']['Tier1'])
        self.assertGreater(knobs['tier']['Tier4'], knobs['tier']['Tier2'])
        self.assertGreater(boost.default_category_map()['medical'], boost.default_multiplier())  # exceeds Multiplier
        for usage in ('Village', 'Farm', 'Town', 'Military', 'Police', 'Prison', 'Hunting', 'Medic', 'Firefighter',
                      'Industrial', 'School'):
            self.assertIn(usage, knobs['usage'])
        self.assertEqual(knobs['refill'], {'RestockMin': 0, 'RespawnTypesFactor': 4 / 3})  # #343
        for usage in ('Town', 'Military', 'Police', 'Prison', 'Medic', 'School'):
            self.assertGreater(knobs['group_cap'][usage], boost.GROUP_CAPACITY_CAP)


class GlobalsKnobs(unittest.TestCase):
    STOCK = ('<variables><var name="LootDamageMax" type="1" value="0.82"/>'
             '<var name="RespawnTypes" type="0" value="12"/></variables>').encode()

    def values(self, data):
        return {v.get('name'): v.get('value') for v in ET.fromstring(data)}

    def test_loot_damage_max_is_lowered_never_raised(self):
        output, report = boost.scale_globals(self.STOCK, 2, 0.6)
        self.assertEqual(self.values(output), {'LootDamageMax': '0.6', 'RespawnTypes': '24'})
        self.assertEqual(report['LootDamageMax'], '0.82->0.6')
        output, report = boost.scale_globals(self.STOCK, 2, 0.9)
        self.assertEqual(self.values(output)['LootDamageMax'], '0.82')
        self.assertNotIn('->', report['LootDamageMax'])
        self.assertEqual(self.values(boost.scale_globals(self.STOCK, 2)[0])['LootDamageMax'], '0.82')

    def test_respawn_types_factor(self):
        self.assertEqual(self.values(boost.scale_globals(self.STOCK, 2, None, 0.5)[0])['RespawnTypes'], '12')
        self.assertEqual(self.values(boost.scale_globals(self.STOCK, 2, None, 4.0)[0])['RespawnTypes'], '64')

    def test_shipped_respawn_target_is_receipt_backed_and_capped(self):
        factor = boost.default_knobs()['refill']['RespawnTypesFactor']
        output, report = boost.scale_globals(self.STOCK, boost.default_multiplier(), None, factor)
        self.assertEqual(self.values(output)['RespawnTypes'], '32')
        self.assertEqual(report['RespawnTypes'], '12->32')
        self.assertEqual(boost.globals_from_report(self.STOCK, report), output)
        self.assertEqual(self.values(boost.scale_globals(self.STOCK, 4, None, factor)[0])['RespawnTypes'], '64')

    def test_the_receipt_report_rebuilds_the_written_bytes(self):
        output, report = boost.scale_globals(self.STOCK, 2, 0.6, 1.25)
        self.assertEqual(boost.globals_from_report(self.STOCK, report), output)


FITS = {'guna': {'scope', 'mag', 'ghost', 'zero'}, 'gunb': {'scope'}, 'shed': {'scope'}}


def fit_rows(**usage):
    return boost.type_rows([('<types>' + supply_row('GunA', ['Military'], category='weapons')
                             + supply_row('GunB', ['Town'], category='weapons')
                             + supply_row('Shed', ['Town'], category='tools')
                             + supply_row('Scope', usage.get('scope', ['Police']), category='weapons')
                             + supply_row('Mag', ['Military'], category='weapons')
                             + supply_row('Zero', ['Military'], nominal=0, minimum=0, category='weapons')
                             + '</types>').encode()])


class AttachmentCoverage(unittest.TestCase):
    def test_gaps_are_classified_and_non_guns_ignored(self):
        report = boost.attachment_coverage(fit_rows(), FITS)
        self.assertEqual((report['guns'], report['attachments'], report['ok']), (2, 4, 1))  # Shed is not a weapon
        self.assertEqual({k: v['kind'] for k, v in report['gaps'].items()},
                         {'ghost': 'norow', 'scope': 'usage', 'zero': 'nominal'})
        self.assertEqual(report['gaps']['scope']['usages'], ['Military', 'Town'])
        self.assertEqual(boost.attachment_coverage(fit_rows(scope=['Town']), FITS)['gaps'].keys(), {'ghost', 'zero'})

    def test_repair_raises_nominal_and_adds_the_gun_usages_only(self):
        data = ('<types>' + supply_row('Scope', ['Police'], category='weapons')
                + supply_row('Zero', [], nominal=0, minimum=0, category='weapons')
                + supply_row('Other', ['Town']) + '</types>').encode()
        gaps = {'scope': {'kind': 'usage', 'guns': 2, 'usages': ['Military', 'Town']},
                'zero': {'kind': 'nominal', 'guns': 1, 'usages': ['Military']},
                'ghost': {'kind': 'norow', 'guns': 1, 'usages': ['Town']}}
        output, fixed = boost.repair_attachments(data, gaps)
        self.assertEqual(fixed, ['scope', 'zero'])
        found = {t.get('name'): (int(t.findtext('nominal')), sorted(u.get('name') for u in t.findall('usage')))
                 for t in ET.fromstring(output)}
        self.assertEqual(found, {'Scope': (10, ['Military', 'Police', 'Town']), 'Zero': (1, ['Military']),
                                 'Other': (10, ['Town'])})
        self.assertEqual(boost.repair_attachments(output, {})[0], output)

    def test_plan_reports_and_repairs_from_the_missions_spawnabletypes(self):
        with tempfile.TemporaryDirectory() as tmp:
            mission = stock_mission(tmp)
            (mission / 'db/types.xml').write_text('<types>' + supply_row('Rifle', ['Police'], category='weapons')
                                                  + supply_row('Scope', ['Farm'], category='weapons') + '</types>')
            (mission / 'cfgspawnabletypes.xml').write_text(
                '<spawnabletypes><type name="Rifle"><attachments chance="1"><item name="Scope"/></attachments>'
                '</type></spawnabletypes>')
            result = boost.plan(mission, 2.0, **PLAN, knobs={})
            cover = result['counts']['attachments']
            self.assertEqual((cover['guns'], cover['gaps'], cover['repaired'], cover['unrepairable']),
                             (1, {'usage': 1}, 1, []))
            types = {name: after for name, _b, after in result['files']}['db/types.xml']
            self.assertIn('Police', {u.get('name') for t in ET.fromstring(types) if t.get('name') == 'Scope'
                                     for u in t.findall('usage')})
            self.assertTrue(any('attachment coverage' in l and 'repaired 1' in l for l in boost.describe(result)))
            self.assertEqual(boost.plan(mission, 2.0, **PLAN, knobs={}, fits={'rifle': ['scope']})['counts']['attachments'],
                             cover)


class PlanSupply(unittest.TestCase):
    def test_receipt_records_the_knobs_and_the_globals_change(self):
        with tempfile.TemporaryDirectory() as tmp, settings_file(SUPPLY_A):
            mission = stock_mission(tmp)
            (mission / 'db/globals.xml').write_text(GlobalsKnobs.STOCK.decode())
            boost.install(mission, None, None, floor_policy=None)
            receipt = json.loads((mission / boost.MANAGED / 'receipt.json').read_bytes())
            self.assertEqual(receipt['knobs']['usage'], {'Town': 3.0})
            self.assertEqual(receipt['knobs']['loot_damage_max'], 0.6)
            self.assertEqual(receipt['knobs']['refill']['RestockMin'], 5000)
            self.assertEqual(receipt['knobs']['group_cap'], {'Default': 90, 'Town': 160})
            self.assertEqual(receipt['counts']['globals']['LootDamageMax'], '0.82->0.6')
            installed = (mission / 'db/globals.xml').read_bytes()
            self.assertEqual(boost.globals_from_report(GlobalsKnobs.STOCK, receipt['counts']['globals']), installed)
            self.assertEqual(rows_of((mission / 'db/types.xml').read_bytes())['Hammer'], (30, 18))
            boost.rollback(mission)
            self.assertEqual((mission / 'db/globals.xml').read_bytes(), GlobalsKnobs.STOCK)

    def test_respawn_upgrade_restores_stock_reapplies_and_refuses_operator_drift(self):
        # Exercise the existing receipt rollback path used by friend_install. No receipt format change.
        with tempfile.TemporaryDirectory() as tmp:
            mission = stock_mission(tmp)
            original = (mission / 'db/globals.xml').read_bytes()
            with settings_file(SUPPLY_A):
                boost.install(mission, None, None, floor_policy=None)
            self.assertEqual(GlobalsKnobs().values((mission / 'db/globals.xml').read_bytes())['RespawnTypes'], '24')
            boost.rollback(mission)
            self.assertEqual((mission / 'db/globals.xml').read_bytes(), original)
            receipt = boost.install(mission, None, None, floor_policy=None)
            self.assertEqual(receipt['counts']['globals']['RespawnTypes'], '12->32')
            installed = (mission / 'db/globals.xml').read_bytes()
            boost.rollback(mission)
            boost.install(mission, None, None, floor_policy=None)
            self.assertEqual((mission / 'db/globals.xml').read_bytes(), installed)
            # Direct rollback refuses drift; friend_install handles operator carry-forward separately.
            edited = installed.replace(b'value="32"', b'value="40"')
            (mission / 'db/globals.xml').write_bytes(edited)
            with self.assertRaises(ValueError):
                boost.rollback(mission)
            self.assertEqual((mission / 'db/globals.xml').read_bytes(), edited)

    def test_supply_settings_b_does_not_depend_on_supply_settings_a(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as fresh:
            mission, clean = stock_mission(tmp), stock_mission(fresh)
            stock = mission_bytes(mission)
            with settings_file(SUPPLY_A):
                boost.install(mission, None, None, floor_policy=None)
            self.assertNotEqual(mission_bytes(mission), stock)
            boost.rollback(mission)
            self.assertEqual(mission_bytes(mission), stock)
            with settings_file(SUPPLY_B):
                boost.install(mission, None, None, floor_policy=None)
                boost.install(clean, None, None, floor_policy=None)
            self.assertEqual(mission_bytes(mission), mission_bytes(clean))
            self.assertEqual(rows_of(mission_bytes(mission)['db/types.xml'])['Hammer'], (25, 15))  # Police 2.5, not A's Town 3.0

    def test_a_receipt_without_knobs_still_rolls_back_and_a_malformed_one_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp, settings_file(SUPPLY_A):
            mission = stock_mission(tmp)
            stock = mission_bytes(mission)
            boost.install(mission, None, None, floor_policy=None)
            path = mission / boost.MANAGED / 'receipt.json'
            receipt = json.loads(path.read_bytes())
            receipt['knobs'] = 3
            path.write_bytes(json.dumps(receipt).encode())
            with self.assertRaises(ValueError):
                boost.rollback(mission)
            del receipt['knobs']
            path.write_bytes(json.dumps(receipt).encode())
            boost.rollback(mission)
            self.assertEqual(mission_bytes(mission), stock)

    def test_describe_lists_every_supply_knob(self):
        with tempfile.TemporaryDirectory() as tmp, settings_file(SUPPLY_A):
            mission = stock_mission(tmp)
            (mission / 'db/globals.xml').write_text(GlobalsKnobs.STOCK.decode())
            text = '\n'.join(boost.describe(boost.plan(mission, **PLAN)))
            for needle in ('usage targets {Town: 3.0}', 'military tiers {Tier4: 2.0}', 'firearms {weapon: 2.0}',
                           'refill: restock >= 5000s', 'group lootmax cap {Default: 90, Town: 160}', 'LootDamageMax=0.82->0.6', 'attachment coverage'):
                self.assertIn(needle, text)



def flag_row(name, category, hoarder='0', extra=''):
    return (f'<type name="{name}"><nominal>10</nominal><min>6</min><lifetime>100</lifetime>'
            f'<flags count_in_cargo="0" count_in_hoarder="{hoarder}" count_in_map="1" count_in_player="0" crafted="0" deloot="0"/>'
            f'<category name="{category}"/>{extra}</type>')


class HoarderFlags(unittest.TestCase):
    ROSTER = {'rostergun': 'weapon', 'rostermag': 'magazine', 'rosterammo': 'ammo', 'rosteroptic': 'attachment'}

    def data(self):
        return ('<types>' + flag_row('Plain', 'tools') + flag_row('RosterGun', 'weapons') + flag_row('RosterOptic', 'weapons')
                + flag_row('AK101_Black', 'weapons') + flag_row('Mag_Extra_10Rnd', 'tools') + flag_row('Ammo_Extra', 'weapons')
                + flag_row('AmmoBox_Extra_20Rnd', 'weapons') + flag_row('RosterMag', 'tools') + flag_row('RosterAmmo', 'tools')
                + flag_row('PoliceBaton', 'weapons') + flag_row('NVGoggles', 'weapons') + flag_row('GunCase_Black', 'weapons')
                + flag_row('Mosin_Compensator', 'weapons') + flag_row('Crossbow', 'weapons') + flag_row('Done', 'weapons', '1') + '<!-- ' + flag_row('Commented', 'weapons') + ' -->'
                + '</types>').encode()

    def flags(self, output):
        return {t.get('name'): t.find('flags').get('count_in_hoarder') for t in ET.fromstring(output)}

    def test_sets_count_in_hoarder_on_guns_mags_and_ammo_only(self):
        output, stats = boost.set_hoarder_flags(self.data(), self.ROSTER)
        self.assertEqual(stats, {'guns': 2, 'mags': 2, 'ammo': 3})
        self.assertEqual(self.flags(output), {
            'Plain': '0', 'RosterGun': '1', 'RosterOptic': '0', 'AK101_Black': '1', 'Mag_Extra_10Rnd': '1',
            'Ammo_Extra': '1', 'AmmoBox_Extra_20Rnd': '1', 'RosterMag': '1', 'RosterAmmo': '1', 'PoliceBaton': '0',
            'NVGoggles': '0', 'GunCase_Black': '0', 'Mosin_Compensator': '0', 'Crossbow': '0', 'Done': '1'})
        self.assertIn(b'<!--', output)
        self.assertIn(b'count_in_hoarder="0" count_in_map="1" count_in_player="0" crafted="0" deloot="0"/>'
                      b'<category name="weapons"/></type> -->', output)  # a commented-out row is never edited
        self.assertEqual(len(output) - len(self.data()), 0)  # same-width edit: nothing else moved
        again, stats = boost.set_hoarder_flags(output, self.ROSTER)
        self.assertEqual((again, sum(stats.values())), (output, 0))

    def test_verify_allows_exactly_that_flag_change_and_refuses_the_rest(self):
        before = self.data()
        after, _ = boost.set_hoarder_flags(before, self.ROSTER)
        boost._verify_types(before, after, {}, self.ROSTER)
        with self.assertRaisesRegex(ValueError, 'changed beyond'):
            boost._verify_types(before, after, {})  # the scaling steps still refuse any flag change
        wrong_row = after.replace(b'<type name="Plain"><nominal>10</nominal><min>6</min><lifetime>100</lifetime>'
                                  b'<flags count_in_cargo="0" count_in_hoarder="0"',
                                  b'<type name="Plain"><nominal>10</nominal><min>6</min><lifetime>100</lifetime>'
                                  b'<flags count_in_cargo="0" count_in_hoarder="1"')
        optic = after.replace(b'<type name="RosterOptic"><nominal>10</nominal><min>6</min><lifetime>100</lifetime>'
                              b'<flags count_in_cargo="0" count_in_hoarder="0"',
                              b'<type name="RosterOptic"><nominal>10</nominal><min>6</min><lifetime>100</lifetime>'
                              b'<flags count_in_cargo="0" count_in_hoarder="1"')
        other_flag = after.replace(b'<type name="RosterGun"><nominal>10</nominal><min>6</min><lifetime>100</lifetime>'
                                   b'<flags count_in_cargo="0"', b'<type name="RosterGun"><nominal>10</nominal><min>6</min>'
                                   b'<lifetime>100</lifetime><flags count_in_cargo="1"')
        for bad in (wrong_row, optic, other_flag, before):
            self.assertNotEqual(bad, after)
            with self.subTest(), self.assertRaisesRegex(ValueError, 'changed beyond|verification failed'):
                boost._verify_types(before, bad, {}, self.ROSTER)

    def test_plan_receipts_the_count_describes_it_and_rollback_restores_stock(self):
        with tempfile.TemporaryDirectory() as tmp:
            mission = stock_mission(tmp)
            types = mission / 'db/types.xml'
            types.write_text(types.read_text().replace('</types>', flag_row('SawedoffMagnum', 'weapons') + flag_row('Mag_Shotgun_8Rnd', 'weapons')
                                                       + flag_row('Ammo_Shotgun', 'weapons') + '</types>'))
            stock = mission_bytes(mission)
            result = boost.plan(mission, 2.0, **PLAN, knobs={})
            self.assertEqual((result['counts']['hoarder_flag_rows'], result['counts']['hoarder_flags']),
                             (3, {'guns': 1, 'mags': 1, 'ammo': 1}))
            self.assertIn('  hoarder flags: rows=3 (guns 1, mags 1, ammo 1)', boost.describe(result))
            boost.install(mission, 2.0, None, floor_policy=None)
            flags = {t.get('name'): t.find('flags').get('count_in_hoarder') for t in ET.fromstring(types.read_bytes())
                     if t.find('flags') is not None}
            self.assertEqual(flags, {'SawedoffMagnum': '1', 'Mag_Shotgun_8Rnd': '1', 'Ammo_Shotgun': '1'})
            self.assertEqual(json.loads((mission / boost.MANAGED / 'receipt.json').read_bytes())['counts']['hoarder_flag_rows'], 3)
            boost.rollback(mission)
            self.assertEqual(mission_bytes(mission), stock)


class BundleRoot(unittest.TestCase):
    """Install-path inputs come from the tree being applied (root), never from this module's own repo tree."""
    BODY = ('{"schema": 1, "kind": "%s", "Multiplier": 3.0, "CapacityMultiplier": {"Town": 1.5}, '
            '"UsageMultiplier": {"Town": 2.5}, "GroupLootmaxCap": {"Town": 123}, "LootDamageMax": 0.5}'
            % boost.SETTINGS_KIND)

    def bundle(self, tmp, settings=BODY, roster=True):
        root = Path(tmp) / 'bundle'
        target = root / boost.SETTINGS
        target.parent.mkdir(parents=True)
        target.write_text(settings)
        if roster:
            for rel in ('tools/package/firearms_roster.json', 'config/military-loot.json'):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_bytes((boost.REPO_ROOT / rel).read_bytes())
        return root

    def test_every_knob_comes_from_the_root_and_not_from_the_repo_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.bundle(tmp)
            mission = stock_mission(Path(tmp) / 'm')
            self.assertNotEqual(boost.default_knobs()['group_cap'], boost.default_knobs(root)['group_cap'])
            receipt = boost.install(mission, None, None, floor_policy=None, root=root)
            self.assertEqual(receipt['multiplier'], 3.0)  # the root's, not the repo's 2.0
            self.assertEqual(receipt['capacity_multiplier'], {'Town': 1.5})
            self.assertEqual(receipt['knobs']['usage'], {'Town': 2.5})
            self.assertEqual(receipt['knobs']['group_cap'], {'Town': 123})
            self.assertEqual(receipt['knobs']['loot_damage_max'], 0.5)
            self.assertEqual(receipt['category_multiplier'], {})  # the repo has category targets; the root has none
            boost.rollback(mission)

    def test_a_root_without_its_inputs_is_refused_and_never_falls_back_to_the_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            mission = stock_mission(Path(tmp) / 'm')
            stock = mission_bytes(mission)
            with self.assertRaises(OSError):
                boost.install(mission, 2.0, None, floor_policy=None, root=Path(tmp) / 'empty')
            root = self.bundle(Path(tmp) / 'r', roster=False)
            with self.assertRaises(ValueError):
                boost.install(mission, 2.0, None, floor_policy=None, root=root)
            self.assertEqual(mission_bytes(mission), stock)
            self.assertFalse((mission / boost.MANAGED).exists())

    def test_floor_policy_and_new_buildings_are_read_from_the_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.bundle(tmp)
            mission = stock_mission(Path(tmp) / 'm')
            repo_policy = boost._floor_policy(boost.SHIPPED)
            self.assertIsNotNone(repo_policy[0])
            self.assertEqual(boost._floor_policy(boost.SHIPPED, root), (None, None))  # the root carries no policy
            with mock.patch('tools.package.loot_floor_policy.shipped_policy', return_value=None) as shipped:
                boost._floor_policy(boost.SHIPPED, root)
            shipped.assert_called_once_with(root)
            self.assertEqual(boost._new_buildings(b'<prototype/>', b'<map/>', boost.SHIPPED, root)[2]['applied'], False)
            boost.plan(mission, root=root, points=None)


if __name__ == '__main__':
    unittest.main()


class EngineEvidenceCaps(unittest.TestCase):
    SOURCE = {'Pipe': (80, 60), 'CableReel': (80, 50), 'GardenLime': (50, 30),
              'Izh43Shotgun': (90, 78), 'geb_SmallTackle': (1, 0)}

    def fixture(self, tmp):
        mission = stock_mission(tmp)
        extra = ''.join(type_row(n, ['Town'], *values, 'weapons' if n == 'Izh43Shotgun' else 'tools')
                        for n, values in self.SOURCE.items())
        path = mission / 'db/types.xml'
        path.write_bytes(path.read_bytes().replace(b'</types>', extra.encode() + b'</types>'))
        return mission

    def test_post_balance_caps_change_only_selected_rows_and_do_not_reinvest(self):
        with tempfile.TemporaryDirectory() as tmp:
            mission = self.fixture(tmp)
            with mock.patch.object(boost, 'engine_caps', return_value={}):
                old = boost.plan(mission, **PLAN)
            new = boost.plan(mission, **PLAN)
            old_bytes = dict((n, a) for n, _, a in old['files'])['db/types.xml']
            new_bytes = dict((n, a) for n, _, a in new['files'])['db/types.xml']
            for name, values in self.SOURCE.items():
                self.assertEqual(rows_of(new_bytes)[name], values)
            # Remove precisely the selected XML rows; every remaining byte must match, including whitespace.
            import re
            def peers(data):
                return re.sub(rb'<type\b[^>]*name="(?:Pipe|CableReel|GardenLime|Izh43Shotgun|geb_SmallTackle)"[^>]*>.*?</type>',
                              b'', data, flags=re.S)
            self.assertEqual(peers(new_bytes), peers(old_bytes))
            self.assertEqual(old['counts']['balance'], new['counts']['balance'])
            cap = new['counts']['engine_caps']
            self.assertEqual(cap['reinvested_nominal'], 0)
            self.assertEqual(cap['freed_nominal'], sum(max(0, rows_of(old_bytes)[n][0] - v[0])
                                                      for n, v in self.SOURCE.items()))

    def test_friend_reinstall_restores_receipt_source_and_is_idempotent(self):
        # Exercise friend_install's actual upgrade orchestration. Only the bundle transport is replaced;
        # its loot receipt rollback/apply use the real installer on the synthetic mission.
        from types import SimpleNamespace
        from tools.setup import friend_install as friend
        with tempfile.TemporaryDirectory() as tmp:
            mission = self.fixture(tmp)
            # Seed a genuine receipt/backups with the measured old installed quantities.
            # The synthetic mission supplies all five source rows without committing game dumps.
            import re
            measured = {'Pipe': (280, 210), 'CableReel': (281, 176), 'GardenLime': (185, 111),
                        'Izh43Shotgun': (144, 125), 'geb_SmallTackle': (1, 0)}
            with mock.patch.object(boost, 'engine_caps', return_value={}):
                legacy = boost.plan(mission, **PLAN)
            files = []
            for filename, before, after in legacy['files']:
                if filename == 'db/types.xml':
                    for name, values in measured.items():
                        def measured_row(hit):
                            block = hit.group(0)
                            for field, value in zip(('nominal', 'min'), values):
                                block = re.sub(rb'<' + field.encode() + rb'>[0-9]+</' + field.encode() + rb'>',
                                               ('<%s>%d</%s>' % (field, value, field)).encode(), block)
                            return block
                        after = re.sub(rb'<type name="' + name.encode() + rb'">.*?</type>',
                                       measured_row, after, flags=re.S)
                files.append((filename, before, after))
            legacy['files'] = files
            with mock.patch.object(boost, 'plan', return_value=legacy):
                boost.install(mission, None, None, floor_policy=None)
            self.assertEqual({n: rows_of((mission / 'db/types.xml').read_bytes())[n] for n in measured}, measured)
            ctx = SimpleNamespace(replaced_done={}, receipt={}, args=SimpleNamespace(), server=Path(tmp),
                                  bundle=Path(tmp) / 'bundle')
            calls = []
            def transport(_ctx, argv):
                calls.append(argv[0])
                if argv[0] == 'bundle-rollback':
                    boost.rollback(mission)
                elif argv[0] == 'bundle-apply':
                    boost.install(mission, None, None, floor_policy=None)
                return 0, '', ''
            with contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.object(friend, 'replaced_layers', return_value=[]))
                stack.enter_context(mock.patch.object(friend.hc_events, 'rollback'))
                stack.enter_context(mock.patch.object(friend.tactical_flava_optional, 'rollback_weapon_packs'))
                stack.enter_context(mock.patch.object(friend.infected_variety, 'rollback'))
                stack.enter_context(mock.patch.object(friend.infected_variety, 'install'))
                stack.enter_context(mock.patch.object(friend.infected_variety, 'season_from_profile', return_value='autumn'))
                stack.enter_context(mock.patch.object(friend, 'overlay_pack_dir', return_value=(Path(tmp), [])))
                stack.enter_context(mock.patch.object(friend, 'save_receipt'))
                stack.enter_context(mock.patch.object(friend, 'run_overlay', side_effect=transport))
                friend._do_overlay_with_variety(ctx, None, mission, True, 'new')
                capped = mission_bytes(mission)
                receipt = json.loads((mission / boost.MANAGED / 'receipt.json').read_bytes())
                self.assertEqual(receipt['counts']['engine_caps']['reinvested_nominal'], 0)
                for name, values in self.SOURCE.items():
                    self.assertEqual(rows_of(capped['db/types.xml'])[name], values)
                friend._do_overlay_with_variety(ctx, None, mission, True, 'new')
                self.assertEqual(mission_bytes(mission), capped)
                self.assertEqual(calls, ['bundle-rollback', 'bundle-plan', 'bundle-apply'] * 2)

    def test_exact_minimum_restore_and_no_below_source_cut(self):
        # A cap restores source values even when balance lowered nominal, or min changed alone.
        before = ('<types>' + type_row('Pipe', ['Town'], 80, 0) + '</types>').encode()
        after = before.replace(b'<nominal>80', b'<nominal>60').replace(b'<min>0', b'<min>3')
        output, _ = boost.cap_engine_types(before, after, boost.engine_caps())
        self.assertEqual(output, before)
        output, _ = boost.cap_engine_types(before, output, boost.engine_caps())
        self.assertEqual(output, before)

    def test_threshold_and_bundle_source(self):
        rows = [dict(row, steady_per_hour=49 if row['class'] == 'Pipe' else 50)
                for row in boost.engine_caps().values()]
        body = ', "ce_engine_caps": ' + json.dumps({'steady_per_hour_threshold': 50, 'rows': rows})
        with settings_file(body):
            self.assertNotIn('pipe', boost.engine_caps())
            self.assertIn('cablereel', boost.engine_caps())
