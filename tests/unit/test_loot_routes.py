"""Behavior of the essential-route checker (T012 / AC-004: essentials have two credible routes).

Every fixture here is SYNTHETIC: classes, groups, placements and thresholds are invented for the test only. The
checker reads files; nothing here observes DayZ, and a route that is credible offline is not an observed spawn.
The committed-state tests read the operator's own stock mission when this machine has it (never modified).
"""
import csv
import io
import json
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[2]
STOCK = Path('/mnt/d/SteamLibrary/steamapps/common/DayZServer/mpmissions/dayzOffline.chernarusplus')

TYPES = b'''<?xml version="1.0" encoding="UTF-8"?>
<types>
  <type name="Spoon"><nominal>10</nominal><min>5</min><category name="tools"/>
    <usage name="Town"/><usage name="Village"/><tag name="shelves"/></type>
  <type name="Fork"><nominal>10</nominal><min>5</min><category name="tools"/><usage name="Village"/></type>
  <type name="Mug"><nominal>10</nominal><min>5</min><category name="tools"/></type>
  <type name="Glass"><nominal>10</nominal><min>5</min></type>
  <type name="Blade"><nominal>10</nominal><min>5</min><category name="tools"/>
    <usage name="Military"/><usage name="Town"/></type>
  <type name="Pan"><nominal>10</nominal><min>5</min><category name="tools"/>
    <usage name="Town"/><usage name="Village"/><tag name="floor"/></type>
</types>
'''
# The profile layer replaces rows by name, exactly like a later registered types file.
PROFILE_LAYER = b'''<?xml version="1.0" encoding="UTF-8"?>
<types>
  <type name="Fork"><nominal>10</nominal><min>5</min><category name="tools"/>
    <usage name="Village"/><usage name="Town"/></type>
</types>
'''
PROTO = b'''<?xml version="1.0" encoding="UTF-8"?>
<prototype>
  <defaults><default name="group" lootmax="6" /><default name="container" lootmax="4" /></defaults>
  <group name="House_A"><usage name="Town" /><usage name="Village" />
    <container name="lootShelves"><category name="tools" /><tag name="shelves" />
      <point pos="0 0 0" range="1" height="1" /><point pos="1 0 0" range="1" height="1" /></container></group>
  <group name="House_B"><usage name="Village" />
    <container name="lootFloor"><category name="tools" /><tag name="floor" /><point pos="0 0 0" range="1" height="1" /></container></group>
  <group name="Mil_A"><usage name="Military" />
    <container name="lootFloor"><category name="tools" /><point pos="0 0 0" range="1" height="1" /></container></group>
</prototype>
'''
POS = b'''<map>
  <group name="House_A" pos="1 0 1" rpy="0 0 0" a="0"/><group name="House_A" pos="2 0 2" rpy="0 0 0" a="0"/>
  <group name="House_B" pos="3 0 3" rpy="0 0 0" a="0"/>
  <group name="Mil_A" pos="4 0 4" rpy="0 0 0" a="0"/><group name="Mil_A" pos="5 0 5" rpy="0 0 0" a="0"/>
  <group name="Mil_A" pos="6 0 6" rpy="0 0 0" a="0"/>
</map>
'''
LIMITS = b'''<lists><usageflags><usage name="Military"/><usage name="Town"/><usage name="Village"/></usageflags></lists>'''
PRESETS = b'''<randompresets><cargo name="p1"><item name="Glass" chance="0.1"/><item name="Fork" chance="0.1"/></cargo>
  <cargo name="p2"><item name="Glass" chance="0.1"/></cargo></randompresets>'''
SPAWNABLE = b'''<spawnabletypes>
  <type name="Bag_1"><cargo preset="p1"/></type><type name="Bag_2"><cargo preset="p1"/></type>
  <type name="Bag_3"><cargo preset="p2"/></type><type name="Vest_1"><attachments chance="1"><item name="Fork" chance="1"/></attachments></type>
</spawnabletypes>'''
POLICY = {
    'schema': 1, 'kind': 'hollow-country-essential-routes', 'min_buildings': 2,
    'excluded_usages': ['Military'],
    'roles': [{'role': 'tools', 'items': [{'class': 'Spoon', 'required': True}, {'class': 'Fork', 'required': True},
                                          {'class': 'Mug', 'required': True}, {'class': 'Glass', 'required': True},
                                          {'class': 'Blade', 'required': True}, {'class': 'Ghost', 'required': True},
                                          {'class': 'Pan', 'required': False}]}]}


class RouteChecker(unittest.TestCase):
    def setUp(self):
        from tools.package import economy
        self.economy = economy

    def report(self, layers=(('stock', TYPES),), overlay=None, policy=POLICY):
        return self.economy.route_report(list(layers), PROTO, POS, LIMITS, json.dumps(policy).encode(),
                                         overlay=overlay)

    def row(self, report, name):
        return next(r for r in report['rows'] if r['item'] == name)

    def test_verdicts_follow_distinct_credible_usage_routes(self):
        report = self.report()
        spoon = self.row(report, 'Spoon')
        self.assertEqual(spoon['verdict'], 'pass')
        self.assertEqual(spoon['routes'], 'Town:2;Village:2', 'tag shelves matches only House_A: 2 placements each')
        fork = self.row(report, 'Fork')
        self.assertEqual((fork['verdict'], fork['route_count']), ('fail-routes', 1))
        self.assertEqual(fork['routes'], 'Village:3')
        blade = self.row(report, 'Blade')
        self.assertEqual((blade['verdict'], blade['routes']), ('fail-routes', 'Town:2'), 'Military is not a civilian route')
        pan = self.row(report, 'Pan')
        self.assertEqual((pan['verdict'], pan['routes'], pan['weak_routes']), ('fail-routes', '', 'Village:1'),
                         'one floor building is below the threshold of 2')

    def test_empty_usage_means_every_usage_but_is_marked_as_an_assumption(self):
        mug = self.row(self.report(), 'Mug')
        self.assertEqual(mug['verdict'], 'pass')
        self.assertEqual(mug['usage_semantics'], 'empty-usage-any-assumed')
        self.assertEqual(self.row(self.report(), 'Spoon')['usage_semantics'], 'explicit')

    def test_item_without_category_has_no_building_route_and_absent_class_is_reported(self):
        report = self.report()
        self.assertEqual(self.row(report, 'Glass')['verdict'], 'no-building-route')
        self.assertEqual(self.row(report, 'Ghost')['verdict'], 'absent')
        self.assertEqual(report['failing'], ['Blade', 'Fork', 'Ghost', 'Glass'],
                         'required items that do not pass; the optional Pan is reported but never fails the check')

    def test_cargo_presets_are_listed_as_carried_evidence_and_never_count_as_a_route(self):
        report = self.economy.route_report([('stock', TYPES)], PROTO, POS, LIMITS, json.dumps(POLICY).encode(),
                                           spawnable_bytes=SPAWNABLE, presets_bytes=PRESETS)
        glass = self.row(report, 'Glass')
        self.assertEqual((glass['verdict'], glass['carried'], glass['route_count']), ('no-building-route', 'p1+p2:3', 0))
        fork = self.row(report, 'Fork')
        self.assertEqual((fork['carried'], fork['route_count'], fork['verdict']), ('p1:3', 1, 'fail-routes'),
                         'two preset holders plus one inline holder are evidence, not a second route')
        self.assertEqual(self.row(report, 'Spoon')['carried'], '')

    def test_a_later_layer_replaces_the_row_by_name_and_names_its_source(self):
        report = self.report(layers=[('stock', TYPES), ('contextual-pilot', PROFILE_LAYER)])
        fork = self.row(report, 'Fork')
        self.assertEqual((fork['verdict'], fork['row_source']), ('pass', 'contextual-pilot'))
        self.assertEqual(self.row(report, 'Spoon')['row_source'], 'stock')

    def test_loot_boost_containers_add_routes_for_matching_categories_and_tags_only(self):
        from tools.package import loot_boost
        selection = {'House_A': {'floor': [[0.0, 0.0, 1.0]], 'surface': []}}
        policy = {'schema': 1, 'kind': 'hollow-country-loot-families',
                  'families': [{'family': 'house', 'match': ['^House_A$'],
                                'floor': {'categories': ['tools'], 'tags': ['floor']}}]}
        overlay = json.loads(loot_boost.build_overlay(selection, PROTO, json.dumps(policy).encode(), {'synthetic': True}))
        before, after = self.report(), self.report(overlay=overlay)
        self.assertEqual(self.row(before, 'Pan')['verdict'], 'fail-routes')
        pan = self.row(after, 'Pan')
        self.assertEqual(pan['verdict'], 'pass', 'House_A gains a tools+floor container: Town and Village both reach 2')
        self.assertEqual(self.row(after, 'Spoon')['routes'], self.row(before, 'Spoon')['routes'])

    def test_csv_is_deterministic_and_carries_provenance_columns(self):
        report = self.report()
        first, second = self.economy.route_csv(report), self.economy.route_csv(self.report())
        self.assertEqual(first, second)
        rows = list(csv.DictReader(io.StringIO(first.decode())))
        self.assertEqual([r['item'] for r in rows], ['Spoon', 'Fork', 'Mug', 'Glass', 'Blade', 'Ghost', 'Pan'])
        self.assertEqual(set(rows[0]) >= {'role', 'item', 'required', 'verdict', 'routes', 'route_count',
                                         'row_source', 'usage_semantics', 'tag_rule', 'types_sha256',
                                         'proto_sha256', 'runtime_acceptance'}, True)
        self.assertEqual({r['runtime_acceptance'] for r in rows}, {'pending'})
        self.assertNotIn(b'\r', first)

    def test_policy_is_validated(self):
        for bad in ({**POLICY, 'min_buildings': 0}, {**POLICY, 'kind': 'x'}, {**POLICY, 'roles': []},
                    {**POLICY, 'excluded_usages': 'Military'},
                    {**POLICY, 'roles': [{'role': 'a', 'items': [{'class': 'Spoon', 'required': True},
                                                                 {'class': 'Spoon', 'required': True}]}]}):
            with self.assertRaises(ValueError):
                self.report(policy=bad)


class CommittedEssentials(unittest.TestCase):
    """The shipped essential list and the committed economy profile, checked against the stock mission when present."""

    def setUp(self):
        from tools.package import economy
        self.economy = economy

    def test_committed_policy_lists_the_spec_essential_roles(self):
        policy = json.loads((REPO / 'tools/package/essential_routes.json').read_bytes())
        roles = {r['role'] for r in policy['roles']}
        self.assertTrue({'water', 'food', 'cutting_and_opening', 'medical', 'fire', 'clothing', 'utility'} <= roles)
        names = [i['class'] for r in policy['roles'] for i in r['items']]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn('Military', policy['excluded_usages'])

    def test_every_required_essential_has_two_credible_routes_with_the_committed_profile(self):
        if not STOCK.is_dir():
            self.skipTest('stock mission not on this machine')
        report = self.economy.routes_for_mission(STOCK, REPO)
        required_unresolved = [r['item'] for r in report['rows'] if r['item'] in report['failing']]
        self.assertEqual(required_unresolved, [r for r in required_unresolved if r in report['unresolved']],
                         'only items whose building route cannot be derived offline may remain, each named below')
        self.assertEqual(report['unresolved'], ['WaterBottle'], 'WaterBottle has no category in stock: needs a world count')

    def test_committed_csv_matches_a_fresh_generation_from_the_stock_mission(self):
        if not STOCK.is_dir():
            self.skipTest('stock mission not on this machine')
        fresh = self.economy.route_csv(self.economy.routes_for_mission(STOCK, REPO))
        self.assertEqual((REPO / 'metrics/loot_routes.csv').read_bytes(), fresh)

    def test_pilot_changes_are_usage_flags_for_existing_stock_classes_only(self):
        pilot = json.loads((REPO / 'mission/hollow-country/economy-profiles/contextual-pilot.json').read_bytes())
        firearm_like = ('Mag_', 'Ammo_', 'Grenade', 'Plastic', 'AK', 'M4', 'Mosin', 'SKS')
        for name, usages in pilot['add_usage'].items():
            self.assertFalse(name.startswith(firearm_like), name)
            self.assertTrue(usages and all(isinstance(u, str) for u in usages), name)


if __name__ == '__main__':
    unittest.main()
