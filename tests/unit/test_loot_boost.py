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


class LootBoostSmoke(unittest.TestCase):
    def setUp(self):
        from tools.package import loot_boost
        self.lb = loot_boost
        self.temp = tempfile.TemporaryDirectory()
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
        self.assertEqual(containers['lootFloor'].get('lootmax'), '4')
        self.assertEqual(containers['lootweapons'].get('lootmax'), '4',
                         'a weapons-only container keeps the stock default it inherited, written explicitly')
        floor, surface = containers['lootHCFloor'], containers['lootHCSurface']
        self.assertEqual([c.get('name') for c in floor.findall('category')], ['tools', 'containers', 'clothes'])
        self.assertEqual([t.get('name') for t in surface.findall('tag')], ['shelves'])
        self.assertEqual(len(floor.findall('point')), 2)
        self.assertEqual(surface.find('point').get('pos'), '0.500000 -0.200000 2.000000')
        added = int(floor.get('lootmax')) + int(surface.get('lootmax'))
        self.assertEqual(int(house.get('lootmax')), 3 * 2 + added)
        police = next(g for g in root.iter('group') if g.get('name') == 'Land_City_PoliceStation_Synthetic')
        pcont = {c.get('name'): c for c in police.findall('container')}
        self.assertEqual(pcont['lootweapons'].get('lootmax'), '2', 'explicit weapons lootmax unchanged')
        self.assertNotIn('weapons', [c.get('name') for c in pcont['lootHCFloor'].findall('category')])
        self.assertEqual(int(police.get('lootmax')), 6 * 2 + int(pcont['lootHCFloor'].get('lootmax')))

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
        files = mission(self.mission)
        (self.mission / 'mapgroupproto.xml').write_bytes(proto.encode())
        (self.mission / 'db/globals.xml').write_bytes(GLOBALS.replace('value="12"', 'value="80"').encode())
        overlay = self.lb.build_overlay({'Land_House_Synthetic': {'floor': [[-2.0, -1.0, 3.0]], 'surface': []}},
                                        proto.encode(), json.dumps(POLICY).encode(), {'synthetic': True})
        self.lb.install(self.mission, multiplier=2.0, points=overlay)
        root = ET.parse(self.mission / 'mapgroupproto.xml').getroot()
        police = next(g for g in root.iter('group') if g.get('name') == 'Land_City_PoliceStation_Synthetic')
        pcont = {c.get('name'): c for c in police.findall('container')}
        self.assertEqual(pcont['lootweapons'].get('lootmax'), '2', 'a mixed container that lists weapons is not doubled')
        values = {v.get('name'): v.get('value') for v in ET.parse(self.mission / 'db/globals.xml').getroot().findall('var')}
        self.assertEqual(values['RespawnTypes'], '80', 'a stock value above the cap is never lowered')
        self.assertTrue(files)


if __name__ == '__main__':
    unittest.main()
