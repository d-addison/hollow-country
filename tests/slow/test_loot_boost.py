"""Behavior of the loot boost installer (2x non-firearm loot plus contextual building points).

Every fixture here is SYNTHETIC: the types, prototype groups, census hits and point coordinates are invented for
the test only, nothing here observes DayZ, and none of it may ever be shipped under mission/. Offline tests never
establish engine behavior; CE spawning of the added points and the doubled rate stays pending native testing.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]

TYPES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<types>
    <!-- <type name="Commented"><nominal>9</nominal><min>9</min></type> -->
    <type name="Apple">
        <nominal>10</nominal>
        <lifetime>3600</lifetime>
        <restock>0</restock>
        <min>5</min>
        <category name="food"/>
        <usage name="Village"/>
    </type>
    <type name="Hammer">
        <nominal>3</nominal>
        <min>1</min>
        <category name="tools"/>
    </type>
    <type name="AKM">
        <nominal>4</nominal>
        <min>2</min>
        <category name="weapons"/>
    </type>
    <type name="Grenade">
        <nominal>2</nominal>
        <min>1</min>
        <category name="explosives"/>
    </type>
    <type name="Sedan_Door">
        <nominal>6</nominal>
        <min>3</min>
    </type>
</types>
'''

OVERRIDE = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<types>
\t<type name="Apple"><nominal>20</nominal><min>8</min><category name="food"/></type>
\t<type name="SyntheticRifle"><nominal>1</nominal><min>1</min><category name="tools"/></type>
</types>
'''

CORE = '''<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<economycore>
\t<classes><rootclass name="DefaultWeapon" /></classes>
<ce folder="hollow-country/ce"><file name="types.xml" type="types" /></ce>
</economycore>
'''

GLOBALS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<variables>
    <var name="InitialSpawn" type="0" value="100"/>
    <var name="RespawnLimit" type="0" value="20"/>
    <var name="RespawnTypes" type="0" value="12"/>
</variables>
'''

LIMITS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<lists>
    <categories><category name="tools"/><category name="containers"/><category name="clothes"/>
    <category name="food"/><category name="weapons"/><category name="books"/><category name="explosives"/></categories>
    <tags><tag name="floor"/><tag name="shelves"/><tag name="ground"/></tags>
    <usageflags><usage name="Village"/><usage name="Police"/></usageflags>
</lists>
'''

PROTO = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<prototype>
\t\t<defaults>
\t\t\t\t<default name="group" lootmax="6" />
\t\t\t\t<default name="container" lootmax="4" />
\t\t</defaults>
\t\t<group name="Land_House_Synthetic" lootmax="3">
\t\t\t\t<usage name="Village" />
\t\t\t\t<container name="lootFloor" lootmax="2">
\t\t\t\t\t\t<category name="tools" />
\t\t\t\t\t\t<tag name="floor" />
\t\t\t\t\t\t<point pos="1.000000 -1.000000 1.000000" range="0.5" height="1.4" flags="32" />
\t\t\t\t</container>
\t\t\t\t<container name="lootweapons">
\t\t\t\t\t\t<category name="weapons" />
\t\t\t\t\t\t<point pos="1.000000 -1.000000 1.000000" range="0.5" height="1.4" flags="32" />
\t\t\t\t</container>
\t\t</group>
\t\t<group name="Land_City_PoliceStation_Synthetic">
\t\t\t\t<usage name="Police" />
\t\t\t\t<container name="lootweapons" lootmax="2">
\t\t\t\t\t\t<category name="weapons" />
\t\t\t\t\t\t<point pos="0.000000 0.000000 0.000000" range="0.5" height="1.4" flags="32" />
\t\t\t\t</container>
\t\t</group>
</prototype>
'''

POLICY = {
    'schema': 1, 'kind': 'hollow-country-loot-families',
    'families': [
        {'family': 'police', 'match': ['PoliceStation'],
         'floor': {'categories': ['tools', 'clothes'], 'tags': ['floor']},
         'surface': {'categories': ['tools', 'books'], 'tags': ['shelves']}},
        {'family': 'residential', 'match': ['^Land_House'],
         'floor': {'categories': ['tools', 'containers', 'clothes'], 'tags': ['floor']},
         'surface': {'categories': ['food', 'tools'], 'tags': ['shelves']}},
    ]}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def mission(root):
    files = {'db/types.xml': TYPES, 'hollow-country/ce/types.xml': OVERRIDE, 'cfgeconomycore.xml': CORE,
             'db/globals.xml': GLOBALS, 'cfglimitsdefinition.xml': LIMITS, 'mapgroupproto.xml': PROTO}
    for name, text in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode())
    return {name: (Path(root) / name).read_bytes() for name in files}


def types_of(path):
    return {t.get('name'): (int(t.findtext('nominal')), int(t.findtext('min')))
            for t in ET.parse(path).getroot().findall('type')}


PLAIN_SETTINGS = {'schema': 1, 'kind': 'hollow-country-loot-boost-settings', 'Multiplier': 2.0,
                  'CapacityMultiplier': {'Farm': 1.25, 'Hunting': 1.5, 'Military': 1.5, 'Police': 2.0, 'Prison': 3.0,
                                         'School': 2.0},
                  'CategoryMultiplier': {'containers': 2.0, 'food': 2.0, 'medical': 2.0, 'tools': 2.0}}


def plain_settings(case):
    """These tests check the boost mechanism at 2x; the shipped supply targets (usage, tier, firearms, damage,
    refill) are unit-tested in tests/unit/test_loot_boost.py, so pin the settings file to the plain 2x layer."""
    target = Path(case.temp.name) / 'plain-settings.json'
    target.write_text(json.dumps(PLAIN_SETTINGS))
    patch = mock.patch.object(case.lb, 'SETTINGS', target)
    patch.start()
    case.addCleanup(patch.stop)


class LootBoostSmoke(unittest.TestCase):
    def setUp(self):
        from tools.package import loot_boost
        self.lb = loot_boost
        self.temp = tempfile.TemporaryDirectory()
        plain_settings(self)
        self.mission = Path(self.temp.name) / 'mission'
        self.before = mission(self.mission)
        # SYNTHETIC selection in the stock prototype frame: two floor points and one raised surface point.
        selection = {'Land_House_Synthetic': {'floor': [[-2.0, -1.0, 3.0], [2.5, -1.0, -3.0]],
                                              'surface': [[0.5, -0.2, 2.0]]},
                     'Land_City_PoliceStation_Synthetic': {'floor': [[3.0, 0.0, 3.0]], 'surface': []}}
        self.overlay = self.lb.build_overlay(selection, PROTO.encode(), json.dumps(POLICY).encode(),
                                             {'synthetic': True})

    def tearDown(self):
        self.temp.cleanup()

    def test_doubles_non_firearm_loot_adds_contextual_points_and_rolls_back_byte_exact(self):
        receipt = self.lb.install(self.mission, multiplier=2.0, points=self.overlay)
        self.assertEqual(receipt['multiplier'], 2.0)
        stock = types_of(self.mission / 'db/types.xml')
        self.assertEqual(stock['Apple'], (20, 10))
        self.assertEqual(stock['Hammer'], (6, 2))
        self.assertEqual(stock['AKM'], (4, 2), 'firearms keep their current scarcity')
        self.assertEqual(stock['Grenade'], (2, 1), 'explosives keep their current scarcity')
        self.assertEqual(stock['Sedan_Door'], (6, 3), 'uncategorised (vehicle part) rows are not building loot')
        self.assertIn(b'<!-- <type name="Commented"><nominal>9</nominal>', (self.mission / 'db/types.xml').read_bytes())
        overridden = types_of(self.mission / 'hollow-country/ce/types.xml')
        self.assertEqual(overridden['Apple'], (40, 16), 'every loaded types file is scaled, whichever wins')
        globals_root = ET.parse(self.mission / 'db/globals.xml').getroot()
        values = {v.get('name'): v.get('value') for v in globals_root.findall('var')}
        self.assertEqual(values['RespawnTypes'], '24')
        self.assertEqual(values['RespawnLimit'], '20')

        root = ET.parse(self.mission / 'mapgroupproto.xml').getroot()
        defaults = {d.get('name'): d.get('lootmax') for d in root.find('defaults')}
        self.assertEqual(defaults, {'group': '12', 'container': '8'})
        house = next(g for g in root.iter('group') if g.get('name') == 'Land_House_Synthetic')
        containers = {c.get('name'): c for c in house.findall('container')}
        # The fixture's stock containers have one point each. Since the physical-capacity clamp (229cd021) a
        # container never exceeds its points: lootFloor doubles to 4, is clamped to 1, and the floor policy then
        # moves that single displaced tool slot to the shelves (lootHCSurface), leaving 0. The weapons-only
        # container keeps its inherited default (4) unscaled and is only clamped to its one point; the unit test
        # ProtoCapacity.test_inherited_weapon_limit_and_group_are_bounded covers the unscaled default itself.
        self.assertEqual(containers['lootFloor'].get('lootmax'), '0')
        self.assertEqual(containers['lootweapons'].get('lootmax'), '1')
        floor, surface = containers['lootHCFloor'], containers['lootHCSurface']
        self.assertEqual([c.get('name') for c in floor.findall('category')], ['tools', 'containers', 'clothes'])
        self.assertEqual([t.get('name') for t in surface.findall('tag')], ['shelves'])
        self.assertEqual(len(floor.findall('point')), 2)
        self.assertEqual(surface.find('point').get('pos'), '0.500000 -0.200000 2.000000')
        added = int(floor.get('lootmax')) + int(surface.get('lootmax'))
        capacity = sum(int(c.get('lootmax')) for c in house.findall('container'))
        self.assertEqual(int(house.get('lootmax')), capacity, 'the group never exceeds its container capacity')
        self.assertEqual(added, 2)
        police = next(g for g in root.iter('group') if g.get('name') == 'Land_City_PoliceStation_Synthetic')
        pcont = {c.get('name'): c for c in police.findall('container')}
        # stock lootmax 2 on a single point: never above the physical capacity (229cd021), and never raised
        self.assertEqual(pcont['lootweapons'].get('lootmax'), '1', 'weapons lootmax is only clamped to its point')
        self.assertNotIn('weapons', [c.get('name') for c in pcont['lootHCFloor'].findall('category')])
        self.assertEqual(int(police.get('lootmax')), sum(int(c.get('lootmax')) for c in police.findall('container')),
                         'the group (inherited 6, doubled and military-scaled) is bounded by its container capacity')

        with self.assertRaises(ValueError):
            self.lb.install(self.mission, multiplier=2.0, points=self.overlay)  # never doubles twice
        self.lb.rollback(self.mission)
        for name, data in self.before.items():
            self.assertEqual((self.mission / name).read_bytes(), data, name)
        self.assertFalse((self.mission / self.lb.MANAGED).exists())

    def test_rollback_refuses_drift_and_keeps_recovery_data(self):
        self.lb.install(self.mission, multiplier=2.0, points=self.overlay)
        (self.mission / 'db/globals.xml').write_bytes(GLOBALS.encode() + b'<!-- operator edit -->\n')
        with self.assertRaises(ValueError):
            self.lb.rollback(self.mission)
        self.assertTrue((self.mission / self.lb.MANAGED / 'receipt.json').is_file())
        self.assertEqual(types_of(self.mission / 'db/types.xml')['Apple'], (20, 10), 'nothing restored on refusal')

    def test_friend_bundle_rollback_undoes_the_boost_first_byte_exact(self):
        from tools.package import optional_overlays as overlays
        self.lb.install(self.mission, multiplier=2.0, points=self.overlay)
        overlays.bundle_rollback(self.mission)
        for name, data in self.before.items():
            self.assertEqual((self.mission / name).read_bytes(), data, name)
        self.assertFalse((self.mission / self.lb.MANAGED).exists())

    def test_floor_selection_uses_reachable_wall_cells_away_from_stock_points_and_doors(self):
        # SYNTHETIC 5 x 4 m room at y=-1 on a 1 m grid in the sampler frame; one stock point, one door.
        hits, codes = [], []
        for ix in range(5):
            for iz in range(4):
                hits.append([float(ix), -1.0, float(iz), 2.5, 0.0, 1])
                codes.append(1)
        hits.append([2.0, -1.0, 9.0, 2.5, 0.0, 0])  # unreachable cell in another space
        codes.append(0)
        stock = [(0.0, -1.0, 0.0)]
        doors = [(4.0, -1.0, 3.0)]
        points = self.lb.floor_points(hits, codes, stock, doors, step=1.0)
        self.assertTrue(points)
        for x, y, z in points:
            self.assertEqual(y, -1.0)
            self.assertTrue(x in (0.0, 4.0) or z in (0.0, 3.0), 'only cells next to a wall or edge')
            self.assertGreater(abs(x - 0.0) + abs(z - 0.0), 1.0, 'never on the stock spot')
            self.assertFalse(abs(x - 4.0) <= 1.2 and abs(z - 3.0) <= 1.2, 'door swing kept clear')
            self.assertNotEqual(z, 9.0, 'unreachable cells are never used')
        for a in points:
            for b in points:
                if a is not b:
                    self.assertGreaterEqual(((a[0] - b[0]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5, 1.5 - 1e-9)


class FirearmScarcityStrict(unittest.TestCase):
    """Owner decision 2026-11-17: firearms keep their scarcity, so the boost adds no firearm spots."""

    def setUp(self):
        from tools.package import loot_boost
        self.lb = loot_boost
        self.temp = tempfile.TemporaryDirectory()
        plain_settings(self)
        self.mission = Path(self.temp.name) / 'mission'

    def tearDown(self):
        self.temp.cleanup()

    def test_policy_and_overlay_refuse_firearm_or_explosive_categories(self):
        for kept in ('weapons', 'explosives'):
            bad = json.loads(json.dumps(POLICY))
            bad['families'][0]['floor']['categories'].append(kept)
            with self.assertRaises(ValueError, msg=kept):
                self.lb.parse_policy(json.dumps(bad).encode())
        overlay = json.loads(self.lb.build_overlay({'Land_House_Synthetic': {'floor': [[-2.0, -1.0, 3.0]], 'surface': []}},
                                                   PROTO.encode(), json.dumps(POLICY).encode(), {'synthetic': True}))
        overlay['groups']['Land_House_Synthetic']['containers']['lootHCFloor']['categories'].append('weapons')
        with self.assertRaises(ValueError):
            self.lb.parse_overlay(json.dumps(overlay).encode())

    def test_committed_policy_and_overlay_add_no_firearm_spots(self):
        self.lb.parse_policy(self.lb.FAMILIES.read_bytes())
        doc = self.lb.parse_overlay(self.lb.ADDITIONS.read_bytes())
        for name, spec in doc['groups'].items():
            for cname, c in spec['containers'].items():
                self.assertFalse(set(c['categories']) & self.lb.KEPT_CATEGORIES, (name, cname))

    def test_mixed_container_listing_weapons_keeps_its_lootmax_and_respawn_types_never_drop(self):
        proto = PROTO.replace('\t\t\t\t<container name="lootweapons" lootmax="2">\n\t\t\t\t\t\t<category name="weapons" />',
                              '\t\t\t\t<container name="lootweapons" lootmax="2">\n\t\t\t\t\t\t<category name="tools" />'
                              '\n\t\t\t\t\t\t<category name="weapons" />')
        self.assertNotEqual(proto, PROTO)
        # Four points so that the stock limit 2 is below capacity: doubling would be visible (4); with one point
        # the physical-capacity clamp would hide it.
        marker = '<category name="weapons" />\n\t\t\t\t\t\t<point pos="0.000000 0.000000 0.000000" range="0.5" height="1.4" flags="32" />'
        self.assertIn(marker, proto)
        proto = proto.replace(marker, '<category name="weapons" />' + ''.join(
            f'\n\t\t\t\t\t\t<point pos="{i}.000000 0.000000 0.000000" range="0.5" height="1.4" flags="32" />'
            for i in range(4)))
        files = mission(self.mission)
        (self.mission / 'mapgroupproto.xml').write_bytes(proto.encode())
        (self.mission / 'db/globals.xml').write_bytes(GLOBALS.replace('value="12"', 'value="80"').encode())
        overlay = self.lb.build_overlay({'Land_House_Synthetic': {'floor': [[-2.0, -1.0, 3.0]], 'surface': []}},
                                        proto.encode(), json.dumps(POLICY).encode(), {'synthetic': True})
        self.lb.install(self.mission, multiplier=2.0, points=overlay)
        root = ET.parse(self.mission / 'mapgroupproto.xml').getroot()
        police = next(g for g in root.iter('group') if g.get('name') == 'Land_City_PoliceStation_Synthetic')
        pcont = {c.get('name'): c for c in police.findall('container')}
        # Owner 2026-11-22 (per-usage capacity): the plain settings give Police 2.0, so a mixed container that
        # also lists tools grows with it (4 = the physical capacity of its four points); Multiplier alone never
        # does, and weapons-only containers stay at their stock limit (unit tests: CapacityMap).
        self.assertEqual(pcont['lootweapons'].get('lootmax'), '4', 'a mixed container follows the Police capacity')
        values = {v.get('name'): v.get('value') for v in ET.parse(self.mission / 'db/globals.xml').getroot().findall('var')}
        self.assertEqual(values['RespawnTypes'], '80', 'a stock value above the cap is never lowered')
        self.assertTrue(files)


class InstallIsAtomicAndVerified(unittest.TestCase):
    """#141: a failed or raced install leaves the mission exactly as it was found, verified."""

    def setUp(self):
        from tools.package import loot_boost
        self.lb = loot_boost
        self.temp = tempfile.TemporaryDirectory()
        self.mission = Path(self.temp.name) / 'mission'
        self.before = mission(self.mission)
        selection = {'Land_House_Synthetic': {'floor': [[-2.0, -1.0, 3.0]], 'surface': []}}
        self.overlay = self.lb.build_overlay(selection, PROTO.encode(), json.dumps(POLICY).encode(),
                                             {'synthetic': True})

    def tearDown(self):
        self.temp.cleanup()

    def assert_untouched(self, except_names=()):
        for name, data in self.before.items():
            if name not in except_names:
                self.assertEqual((self.mission / name).read_bytes(), data, name)
        self.assertFalse((self.mission / self.lb.MANAGED).exists(), 'no managed leftovers')

    def test_failure_after_some_files_were_switched_restores_every_file_verified(self):
        real, calls = self.lb._switch, []

        def failing(mission, managed, name, data, staged_name, expected_sha):
            calls.append(name)
            if len(calls) == 3:
                raise OSError('injected failure after two files were switched')
            return real(mission, managed, name, data, staged_name, expected_sha)
        self.lb._switch = failing
        try:
            with self.assertRaises(OSError):
                self.lb.install(self.mission, multiplier=2.0, points=self.overlay)
        finally:
            self.lb._switch = real
        self.assertGreaterEqual(len(calls), 3, "the injected failure happened mid-install")
        self.assert_untouched()

        # HC-9: exercise failures inside the real staged swap as well as at its caller.
        # Each mission and injected edit is SYNTHETIC; this proves filesystem recovery only.
        scenarios = ('install_stage_drift', 'rollback_stage_drift', 'rollback_backup_drift',
                     'rollback_replace_failure', 'install_readback', 'rollback_readback')
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                root = Path(self.temp.name) / scenario
                original = mission(root)
                plan = self.lb.plan(root, multiplier=2.0, points=self.overlay)
                name, before, after = plan['files'][1]
                live = root / name
                managed = root / self.lb.MANAGED
                edited = before + b'<!-- synthetic concurrent operator edit -->\n'
                if scenario.startswith('rollback'):
                    self.lb.install(root, multiplier=2.0, points=self.overlay)
                real_sync, real_replace = self.lb._sync_file, self.lb.os.replace
                injected = []

                def during_stage(path):
                    if not injected:
                        if scenario.endswith('stage_drift') and Path(path).name == '01.next':
                            live.write_bytes(edited)
                            injected.append(True)
                        elif scenario == 'rollback_backup_drift' and Path(path).name == '00.next':
                            (managed / '01.backup').write_bytes(b'SYNTHETIC corrupt backup')
                            injected.append(True)
                    return real_sync(path)

                def during_replace(source, destination):
                    if Path(destination) == live and not injected:
                        if scenario == 'rollback_replace_failure':
                            injected.append(True)
                            raise OSError('injected rollback swap failure')
                        if scenario.endswith('readback'):
                            injected.append(True)
                            real_replace(source, destination)
                            live.write_bytes(edited)
                            return
                    return real_replace(source, destination)

                operation = self.lb.rollback if scenario.startswith('rollback') else self.lb.install
                kwargs = {} if scenario.startswith('rollback') else {'multiplier': 2.0, 'points': self.overlay}
                expected_error = OSError if scenario == 'rollback_replace_failure' else ValueError
                with mock.patch.object(self.lb, '_sync_file', side_effect=during_stage), \
                        mock.patch.object(self.lb.os, 'replace', side_effect=during_replace):
                    with self.assertRaises(expected_error):
                        operation(root, **kwargs)
                self.assertTrue(injected, 'the fault must occur inside the real swap')
                self.assertTrue((managed / 'receipt.json').is_file(), 'keep the recovery receipt')
                if scenario.endswith(('stage_drift', 'readback')):
                    self.assertEqual(live.read_bytes(), edited, 'never overwrite the concurrent edit')
                    # Explicit operator reconciliation, outside the failing transaction.
                    live.write_bytes(after if scenario.startswith('rollback') else before)
                if scenario == 'rollback_backup_drift':
                    self.assertEqual(live.read_bytes(), after, 'corrupt backup was never installed')
                    (managed / '01.backup').write_bytes(before)
                if scenario == 'rollback_replace_failure':
                    self.assertEqual(live.read_bytes(), after)
                    self.assertTrue((managed / '01.next').is_file(), 'retry a leftover staged restore')
                self.lb.rollback(root)
                for relative, data in original.items():
                    self.assertEqual((root / relative).read_bytes(), data, relative)
                self.assertFalse(managed.exists(), 'remove recovery data only after verified restore')

    def test_mission_file_changed_after_planning_is_refused_without_any_write(self):
        real_sync, state = self.lb._sync_dir, {'done': False}

        def racing(path):
            if not state['done']:
                state['done'] = True
                (self.mission / 'db/types.xml').write_bytes(TYPES.encode() + b'<!-- raced edit -->\n')
            return real_sync(path)
        self.lb._sync_dir = racing
        try:
            with self.assertRaises(ValueError) as caught:
                self.lb.install(self.mission, multiplier=2.0, points=self.overlay)
        finally:
            self.lb._sync_dir = real_sync
        self.assertIn('changed since planning', str(caught.exception))
        self.assertEqual((self.mission / 'db/types.xml').read_bytes(), TYPES.encode() + b'<!-- raced edit -->\n',
                         'the operator edit is never overwritten')
        self.assert_untouched(except_names=('db/types.xml',))

    def test_file_changed_between_two_swaps_undoes_the_swapped_files_and_keeps_the_edit(self):
        real, calls = self.lb._switch, []

        def racing(mission, managed, name, data, staged_name, expected_sha):
            calls.append(name)
            result = real(mission, managed, name, data, staged_name, expected_sha)
            if len(calls) == 1:
                (self.mission / 'db/globals.xml').write_bytes(GLOBALS.encode() + b'<!-- raced edit -->\n')
            return result
        self.lb._switch = racing
        try:
            with self.assertRaises(ValueError) as caught:
                self.lb.install(self.mission, multiplier=2.0, points=self.overlay)
        finally:
            self.lb._switch = real
        self.assertIn('changed since planning', str(caught.exception))
        self.assertEqual((self.mission / 'db/globals.xml').read_bytes(), GLOBALS.encode() + b'<!-- raced edit -->\n')
        self.assert_untouched(except_names=('db/globals.xml',))

    def test_combined_install_failure_after_the_boost_undoes_what_this_run_applied(self):
        from tools.package import optional_overlays as overlays
        applied = []

        def boost():
            self.lb.install(self.mission, multiplier=2.0, points=self.overlay)
            applied.append('boost')

        def failing_next_step():
            raise RuntimeError('injected failure after the real loot boost merge')
        with self.assertRaises(RuntimeError):
            overlays.apply_stack(self.mission, [boost, failing_next_step])
        self.assertEqual(applied, ['boost'])
        self.assert_untouched()

    def test_combined_install_reports_when_the_automatic_undo_itself_is_refused(self):
        from tools.package import optional_overlays as overlays

        def boost_then_operator_edit():
            self.lb.install(self.mission, multiplier=2.0, points=self.overlay)
            (self.mission / 'db/globals.xml').write_bytes(b'<variables/>')
            raise RuntimeError('injected')
        with self.assertRaises(ValueError) as caught:
            overlays.apply_stack(self.mission, [boost_then_operator_edit])
        self.assertIn('automatic undo failed', str(caught.exception))
        self.assertTrue((self.mission / self.lb.MANAGED / 'receipt.json').is_file(), 'recovery data kept')


class FloorBound(unittest.TestCase):
    """#141: points far below their building's own stock floor are refused (offline guard, in-game check pending)."""

    def setUp(self):
        from tools.package import loot_boost
        self.lb = loot_boost

    def test_generation_drops_and_install_refuses_a_point_far_below_the_stock_floor(self):
        below = [0.0, -1.0 - self.lb.MAX_BELOW_STOCK_FLOOR - 0.5, 0.0]  # SYNTHETIC outlier
        selection = {'Land_House_Synthetic': {'floor': [[-2.0, -1.0, 3.0], below], 'surface': []}}
        data = self.lb.build_overlay(selection, PROTO.encode(), json.dumps(POLICY).encode(), {'synthetic': True})
        doc = json.loads(data)
        points = doc['groups']['Land_House_Synthetic']['containers']['lootHCFloor']['points']
        self.assertEqual(points, [[-2.0, -1.0, 3.0]], 'the outlier is dropped at generation')
        forged = json.loads(data)
        forged['groups']['Land_House_Synthetic']['containers']['lootHCFloor']['points'].append(below)
        with self.assertRaises(ValueError) as caught:
            self.lb.scale_proto(PROTO.encode(), 2.0, self.lb.parse_overlay(json.dumps(forged).encode()),
                                ({'tools', 'containers', 'clothes'}, {'floor'}))
        self.assertIn('below', str(caught.exception))

    def test_a_basement_within_the_bound_is_accepted(self):
        deep = [0.0, -1.0 - self.lb.MAX_BELOW_STOCK_FLOOR + 0.5, 0.0]
        selection = {'Land_House_Synthetic': {'floor': [deep], 'surface': []}}
        data = self.lb.build_overlay(selection, PROTO.encode(), json.dumps(POLICY).encode(), {'synthetic': True})
        self.lb.scale_proto(PROTO.encode(), 2.0, self.lb.parse_overlay(data), ({'tools', 'containers', 'clothes'}, {'floor'}))

    def test_committed_overlay_has_no_point_below_the_stock_floor_when_the_stock_mission_is_present(self):
        stock = Path('/mnt/d/SteamLibrary/steamapps/common/DayZServer/mpmissions/dayzOffline.chernarusplus/mapgroupproto.xml')
        if not stock.is_file():
            self.skipTest('stock mission not on this machine')
        floors = {}
        for group in ET.parse(stock).getroot().iter('group'):
            ys = [float(p.get('pos').split()[1]) for p in group.iter('point')]
            if ys:
                floors[group.get('name')] = min(ys)
        doc = self.lb.parse_overlay(self.lb.ADDITIONS.read_bytes())
        for name, spec in doc['groups'].items():
            for cname, c in spec['containers'].items():
                for p in c['points']:
                    self.assertGreaterEqual(p[1], floors[name] - self.lb.MAX_BELOW_STOCK_FLOOR, (name, cname, p))


class VillageHouseTarget(unittest.TestCase):
    """The owner's 5-6 items per Village house (economy interview 2026-11-22), as the offline fill model sees it."""
    STOCK = Path('/mnt/d/SteamLibrary/steamapps/common/DayZServer/mpmissions/dayzOffline.chernarusplus')

    def test_staged_pipeline_keeps_the_median_village_house_at_5_to_6_items_and_its_tail_bounded(self):
        if not self.STOCK.is_dir():
            self.skipTest('stock mission not on this machine')
        from tools.package import ce_slot_pressure, loot_slack
        with tempfile.TemporaryDirectory() as tmp:
            result = ce_slot_pressure.village_items(loot_slack.stage(self.STOCK, tmp))
        house = result['kinds']['house']
        # Offline fill model, never DayZ: the capacity layer must not push a house past 6 or stretch its tail.
        self.assertGreaterEqual(house['median'], 5.0, result)
        self.assertLessEqual(house['median'], 6.0, result)
        self.assertLessEqual(house['p90'], 10.5, result)
        self.assertGreater(result['nominal'], 15000, result)


class FinalShelfCapacity(unittest.TestCase):
    """Synthetic final supply cuts must survive balance and preserve installed floors."""

    def test_final_cap_shares_buckets_respects_stock_min_and_never_reinvests(self):
        from tools.package import loot_boost as lb
        stock = b'''<types>
          <type name="Pipe"><nominal>4</nominal><min>3</min><category name="tools"/><usage name="Industrial"/><tag name="shelves"/></type>
          <type name="Hammer"><nominal>2</nominal><min>2</min><category name="tools"/><usage name="Industrial"/><tag name="shelves"/></type>
          <type name="SyntheticRifle"><nominal>1</nominal><min>1</min><category name="weapons"/><usage name="Industrial"/><tag name="shelves"/></type>
        </types>'''
        boosted, _ = lb.set_nominals(stock, {'pipe': 12, 'hammer': 8, 'syntheticrifle': 3})
        proto = b'''<prototype><group name="Synthetic" lootmax="9"><usage name="Industrial"/>
          <container name="shelf" lootmax="9"><tag name="shelves"/>''' + b'<point/>' * 9 + b'</container></group></prototype>'
        positions = b'<map><group name="Synthetic"/></map>'
        gap = {'nominal': 12, 'requested_slots': 4, 'unplaced_slots': 2,
               'compatible_shelf_points': 20}
        floor = {'supply_gaps': {'Pipe': gap}}
        outputs, budget, report = lb._cap_shelf_supply(
            [('db/types.xml', stock, boosted)], floor, proto, positions,
            {'type_files': {'db/types.xml'}, 'shelf_tag': 'shelves'}, {'syntheticrifle': 'weapon'})
        rows = {n.get('name'): (int(n.findtext('nominal')), int(n.findtext('min')))
                for n in ET.fromstring(outputs[0][2])}
        self.assertLessEqual(sum(n for n, m in rows.values()), 9)
        self.assertGreaterEqual(rows['Pipe'][0], 4)
        self.assertGreaterEqual(rows['Pipe'][1], 3)
        self.assertGreaterEqual(rows['Hammer'][1], 2)
        self.assertEqual(rows['SyntheticRifle'], (3, 3))
        self.assertLessEqual(rows['Pipe'][0], 6)
        self.assertEqual(gap['nominal'], rows['Pipe'][0])
        self.assertFalse(budget['remaining_pressure'])
        self.assertEqual(report['unreinvested_nominal'], 23 - sum(n for n, m in rows.values()))

    def test_stock_and_firearm_excess_is_reported_and_missing_inputs_never_pass(self):
        from tools.package import loot_boost as lb
        stock = b'''<types><type name="Pipe"><nominal>8</nominal><min>6</min>
          <category name="tools"/><tag name="shelves"/></type></types>'''
        boosted, _ = lb.set_nominals(stock, {'pipe': 16})
        floor = {'supply_gaps': {'Pipe': {'nominal': 16, 'requested_slots': 4,
                 'unplaced_slots': 4, 'compatible_shelf_points': 1}}}
        outputs, budget, report = lb._cap_shelf_supply(
            [('db/types.xml', stock, boosted)], floor, b'<prototype/>', b'<map/>',
            {'type_files': {'db/types.xml'}, 'shelf_tag': 'shelves'}, {})
        row = ET.fromstring(outputs[0][2]).find('type')
        self.assertEqual((row.findtext('nominal'), row.findtext('min')), ('8', '6'))
        self.assertEqual(budget['remaining_pressure'], ['*/shelves'])
        self.assertEqual(report['stock_or_protected_gaps']['Pipe']['above_capacity'], 8)
        self.assertEqual(lb.capacity_check(None), 2)

    def test_upgrade_rollback_uses_verified_preboost_bytes_then_replans(self):
        from tools.package import loot_boost as lb
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'mission'
            original = mission(target)
            with mock.patch.object(lb, 'default_knobs', return_value=dict(lb.default_knobs(), balance=None, usage={}, tier={}, firearms={})), \
                    mock.patch.object(lb, 'default_category_map', return_value={}), \
                    mock.patch.object(lb, 'default_capacity_map', return_value={}):
                lb.install(target, multiplier=2, points=None, floor_policy=None)
                self.assertEqual(lb.installed_before(target)['db/types.xml'], original['db/types.xml'])
                lb.rollback(target)
                for name, data in original.items():
                    self.assertEqual((target / name).read_bytes(), data)
                # A changed generator/setting is applied to the original 3, never to the boosted 6.
                lb.install(target, multiplier=3, points=None, floor_policy=None)
                self.assertEqual(types_of(target / 'db/types.xml')['Hammer'], (9, 3))

    def test_reinvest_headroom_rebases_demand_and_preserves_firearm_weights(self):
        from tools.package import loot_boost as lb
        rows = {'kit': {'category': 'containers', 'nominal': 80},
                'rifle': {'category': 'weapons', 'nominal': 10}}
        slack = {'class': {'kit': 'medic', 'rifle': 'weapon'}, 'bucket': {'medic': 97, 'weapon': 97}}
        first = lb._reinvest_slack(rows, slack, {'medic': 130, 'weapon': 10})
        slack['bucket']['medic'] = 98
        second = lb._reinvest_slack(rows, slack, {'medic': 129, 'weapon': 10})
        self.assertEqual(first, second)
        self.assertEqual(first['bucket'], {'medic': 147, 'weapon': 97})
        self.assertEqual(slack['bucket']['medic'], 98)

    def test_plan_caps_the_emitted_layers_and_reports_their_actual_budget(self):
        from tools.package import loot_boost as lb, economy
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'mission'
            mission(target)
            (target / 'mapgrouppos.xml').write_bytes(b'<map><group name="Land_House_Synthetic"/></map>')
            knobs = dict(lb.default_knobs(), balance=None, usage={}, tier={}, firearms={})
            result = lb.plan(target, multiplier=2, points=None, buildings=None,
                             capacity={}, categories={}, knobs=knobs)
            layers = []
            for name in lb.types_files(target, include_optional=True):
                layers.append(next((a for n, b, a in result['files'] if n == name),
                                   (target / name).read_bytes()))
            proto = next((a for n, b, a in result['files'] if n == lb.PROTO),
                         (target / lb.PROTO).read_bytes())
            budget = economy.placement_budget(layers, proto, (target / 'mapgrouppos.xml').read_bytes())
            self.assertEqual(result['counts']['placement_budget']['by_usage_tag'], budget['by_usage_tag'])
            self.assertIn('supply_cap', result['counts'])


if __name__ == '__main__':
    unittest.main()
