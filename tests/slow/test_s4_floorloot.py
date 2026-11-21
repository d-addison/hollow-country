"""Floor loot policy (#179/#199): floor-height points take clothing and trash only, the rest moves to shelves.

Every fixture is SYNTHETIC: invented classes, nominals and points. The CE category/tag matching in ``accepts`` is a
test-local MODEL of the documented rule, not an observation of DayZ. Whether the CE honours the rewritten tags, and
the resulting density on shelves versus floors, stay pending a native server session (runtime=PENDING).
"""
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]

TYPES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<types>
    <type name="Hammer"><nominal>6</nominal><min>2</min><category name="tools"/></type>
    <type name="Broom"><nominal>2</nominal><min>1</min><category name="tools"/><tag name="floor"/></type>
    <type name="TShirt"><nominal>4</nominal><min>2</min><category name="clothes"/></type>
    <type name="Apple"><nominal>10</nominal><min>5</min><category name="food"/><tag name="floor"/><tag name="shelves"/></type>
    <type name="SyntheticBag"><nominal>3</nominal><min>1</min><category name="containers"/></type>
    <type name="AKM"><nominal>4</nominal><min>2</min><category name="weapons"/></type>
    <type name="Sedan_Door"><nominal>6</nominal><min>3</min></type>
</types>
'''

CORE = '''<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<economycore><classes><rootclass name="DefaultWeapon" /></classes></economycore>
'''

GLOBALS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<variables><var name="RespawnTypes" type="0" value="12"/></variables>
'''

LIMITS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<lists>
    <categories><category name="tools"/><category name="containers"/><category name="clothes"/>
    <category name="food"/><category name="weapons"/><category name="books"/><category name="explosives"/></categories>
    <tags><tag name="floor"/><tag name="shelves"/><tag name="ground"/></tags>
    <usageflags><usage name="Village"/></usageflags>
</lists>
'''


def point(y, x=0.0):
    return '<point pos="%f %f 1.000000" range="0.5" height="1.4" flags="32" />' % (x, y)


PROTO = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<prototype>
    <defaults>
        <default name="group" lootmax="6" />
        <default name="container" lootmax="4" />
    </defaults>
    <group name="Land_House_S4" lootmax="3">
        <usage name="Village" />
        <container name="lootFloor" lootmax="6">
            <category name="tools" /><category name="clothes" /><category name="food" />
            <tag name="floor" />
            %(floors)s
        </container>
        <container name="lootshelves" lootmax="1">
            <category name="tools" /><category name="food" /><category name="books" />
            <tag name="shelves" />
            %(shelf)s
        </container>
        <container name="lootweapons" lootmax="2">
            <category name="weapons" />
            %(floor)s
        </container>
    </group>
    <group name="Land_Mixed_S4" lootmax="3">
        <container name="loot" lootmax="2">
            <category name="tools" /><category name="food" />
            <tag name="floor" /><tag name="shelves" />
            %(low)s
        </container>
        <container name="loot" lootmax="2">
            <category name="tools" /><category name="food" />
            <tag name="floor" /><tag name="shelves" />
            %(high)s
        </container>
    </group>
</prototype>
''' % {'floor': point(-1.0), 'floors': ''.join(point(-1.0, float(n)) for n in range(6)), 'shelf': ''.join(point(0.6, x) for x in range(8)),
       'low': point(-1.0) + point(-0.9, 1.0), 'high': ''.join(point(1.2 + 0.01 * n, float(n)) for n in range(6))}

POLICY = {
    'schema': 1, 'kind': 'hollow-country-loot-floor-policy', 'enabled': True,
    'floor_categories': ['clothes'],
    'floor_classes': ['Broom'], 'floor_class_patterns': [],
    'shelf_categories': ['tools', 'containers', 'food', 'books'],
    'floor_tag': 'floor', 'shelf_tag': 'shelves',
    'floor_container_tags': ['floor', 'ground'],
    'floor_container_names': ['lootFloor', 'lootGround', 'lootHCFloor'],
    'height_checked_container_names': ['loot'], 'extra_floor_container_names': ['lootHCFloor'], 'floor_band_m': 0.75,
    'capacity': {'enabled': True, 'max_container_lootmax': 12, 'preserve_tolerance': 0.1},
}


def write_mission(root, policy=POLICY):
    files = {'db/types.xml': TYPES, 'cfgeconomycore.xml': CORE, 'db/globals.xml': GLOBALS,
             'cfglimitsdefinition.xml': LIMITS, 'mapgroupproto.xml': PROTO}
    for name, text in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode())
    return {name: (Path(root) / name).read_bytes() for name in files}


def policy_bytes(**changes):
    doc = json.loads(json.dumps(POLICY))
    doc.update(changes)
    return json.dumps(doc).encode()


def accepts(container, row):
    """MODEL of CE matching: the row category must be listed; a tagged row needs a shared container tag."""
    cats = {c.get('name') for c in container.findall('category')}
    tags = {t.get('name') for t in container.findall('tag')}
    row_cat = row.find('category')
    row_tags = {t.get('name') for t in row.findall('tag')}
    if row_cat is None or row_cat.get('name') not in cats:
        return False
    return not row_tags or bool(row_tags & tags)


def rows_of(path):
    return {t.get('name'): t for t in ET.parse(path).getroot().findall('type')}


def containers_of(path, group):
    root = ET.parse(path).getroot()
    found = next(g for g in root.iter('group') if g.get('name') == group)
    return found.findall('container')


class FloorPolicyAdmission(unittest.TestCase):
    def setUp(self):
        from tools.package import loot_boost
        self.lb = loot_boost
        self.temp = tempfile.TemporaryDirectory()
        self.mission = Path(self.temp.name) / 'mission'
        self.before = write_mission(self.mission)

    def tearDown(self):
        self.temp.cleanup()

    def install(self, **kw):
        return self.lb.install(self.mission, multiplier=1.0, points=None, floor_policy=policy_bytes(**kw))

    def test_a_non_clothing_class_is_not_admitted_on_a_floor_point_but_clothes_and_trash_are(self):
        self.install()
        rows = rows_of(self.mission / 'db/types.xml')
        floor = containers_of(self.mission / 'mapgroupproto.xml', 'Land_House_S4')[0]
        self.assertEqual(floor.get('name'), 'lootFloor')
        self.assertFalse(accepts(floor, rows['Hammer']), 'a tool must not land on a floor point')
        self.assertFalse(accepts(floor, rows['Apple']), 'food must not land on a floor point')
        self.assertTrue(accepts(floor, rows['TShirt']), 'clothing may lie on the floor')
        self.assertTrue(accepts(floor, rows['Broom']), 'listed trash may lie on the floor')
        shelf = containers_of(self.mission / 'mapgroupproto.xml', 'Land_House_S4')[1]
        self.assertTrue(accepts(shelf, rows['Hammer']) and accepts(shelf, rows['Apple']),
                        'displaced classes stay spawnable on shelves')

    def test_unavailable_shelves_report_unplaced_demand_without_floor_fallback(self):
        path = self.mission / 'mapgroupproto.xml'
        path.write_text('<prototype><group name="OnlyFloor" lootmax="1">'
                        '<container name="lootFloor" lootmax="1"><category name="tools"/>'
                        '<tag name="floor"/>' + point(0) + '</container></group></prototype>')
        receipt = self.install()
        row = rows_of(self.mission / 'db/types.xml')['Hammer']
        floor = containers_of(path, 'OnlyFloor')[0]
        self.assertFalse(accepts(floor, row), 'equipment must not regain floor eligibility')
        self.assertEqual(receipt['counts']['floor_policy']['unplaced'], 1)
        self.assertIn('Hammer', receipt['counts']['floor_policy']['supply_gaps'])
        self.assertEqual(receipt['counts']['floor_policy']['kept_without_shelf_room'], 0)

    def test_newly_admitted_broom_demand_does_not_cancel_displaced_hammer(self):
        from tools.package import loot_floor_policy as policy
        doc = policy.parse_policy(policy_bytes())
        # Synthetic review fixture: the floor initially admits only the nominal-1 Hammer.
        types = (b'<types><type name="Hammer"><nominal>1</nominal><category name="tools"/></type>'
                 b'<type name="Broom"><nominal>10</nominal><category name="tools"/>'
                 b'<tag name="floor"/></type></types>')
        rewritten_types, rows = policy.retag_types(types, doc)
        proto = ('<prototype><group name="G" lootmax="1">'
                 '<container name="lootFloor" lootmax="1"><category name="tools"/>'
                 '<tag name="shelves"/>' + point(0) + '</container>'
                 '<container name="shelf" lootmax="0"><category name="tools"/>'
                 '<tag name="shelves"/>' + point(1) + '</container></group></prototype>').encode()
        output, counts = policy.rebalance_proto(proto, [rows], doc)
        floor, shelf = ET.fromstring(output).find('group').findall('container')
        rewritten_rows = {t.get('name'): t for t in ET.fromstring(rewritten_types)}
        self.assertEqual((counts['displaced'], counts['transferred'], counts['unplaced']), (1, 1, 0))
        self.assertEqual((floor.get('lootmax'), shelf.get('lootmax')), ('0', '1'))
        self.assertTrue(accepts(floor, rewritten_rows['Broom']))
        self.assertFalse(accepts(floor, rewritten_rows['Hammer']))
        self.assertTrue(accepts(shelf, rewritten_rows['Hammer']))
        self.assertEqual((counts['slots_before'], counts['slots_after']), (1, 1))

    def test_rounding_a_rare_displacement_to_zero_still_reports_missing_receiver(self):
        path = self.mission / 'mapgroupproto.xml'
        path.write_text('<prototype><group name="Rare" lootmax="1">'
                        '<container name="lootFloor" lootmax="1"><category name="tools"/>'
                        '<category name="clothes"/><tag name="floor"/>' + point(0) +
                        '</container></group></prototype>')
        (self.mission / 'db/types.xml').write_text(
            '<types><type name="Hammer"><nominal>1</nominal><category name="tools"/></type>'
            '<type name="TShirt"><nominal>100</nominal><category name="clothes"/></type></types>')
        receipt = self.install()
        self.assertFalse(accepts(containers_of(path, 'Rare')[0],
                                rows_of(self.mission / 'db/types.xml')['Hammer']),
                        'rounding must not restore equipment to floors')
        gap = receipt['counts']['floor_policy']['supply_gaps']['Hammer']
        self.assertEqual(gap['requested_slots'], 0)
        self.assertEqual(gap['groups_without_receiver'], ['Rare'])

    def test_relocated_receivers_and_extra_clothing_floors_keep_positive_capacity(self):
        from tools.package import loot_floor_policy as policy
        doc = policy.parse_policy(policy_bytes(receivers={'G': {
            'evidence': 'Synthetic raised point; no native placement claim.',
            'sources': {'lootFloor': ['1.000000 1.000000 1.000000']},
            'widen': [], 'floor_exception': None}}))
        # No displaced equipment demand can rescue an inert receiver. Explicit
        # zero and inherited native capacities must still leave it spawnable.
        _types, rows = policy.retag_types(
            b'<types><type name="TShirt"><nominal>4</nominal><category name="clothes"/></type></types>', doc)
        for capacity in ('', ' lootmax="0"', ' lootmax="2"'):
            with self.subTest(source_capacity=capacity):
                proto = ('<prototype><defaults><default name="container" lootmax="2"/></defaults>'
                         '<group name="G" lootmax="3"><container name="lootFloor"' + capacity + '>'
                         '<category name="clothes"/><tag name="floor"/>' + point(0) + point(1, 1) +
                         '</container><container name="lootHCFloor" lootmax="1">'
                         '<category name="clothes"/><tag name="floor"/>' + point(0, 2) +
                         '</container></group></prototype>').encode()
                staged, receivers = policy.provision_receivers(proto, doc)
                balanced, counts = policy.rebalance_proto(staged, [rows], doc)
                final = policy.finish_receivers(balanced, receivers, doc, counts)
                containers = ET.fromstring(final).find('group').findall('container')
                receiver = next(c for c in containers if c.get('name') == policy.SURFACE_RECEIVER)
                floor = next(c for c in containers if c.get('name') == 'lootHCFloor')
                self.assertEqual(int(receiver.get('lootmax')), 1)
                self.assertGreater(int(floor.get('lootmax')), 0)
                self.assertEqual(counts['displaced'], 0)
                positions = [p.get('pos') for c in containers for p in c.findall('point')]
                self.assertEqual(len(positions), len(set(positions)))
                self.assertEqual(len(positions), 3, 'relocation conserves physical points')
                self.assertEqual(receivers['zero_capacity_containers_after'], 0)

    def test_incompatible_shelves_do_not_count_as_replacement_capacity(self):
        for mismatch in ('category', 'tag', 'usage'):
            with self.subTest(mismatch=mismatch):
                mission = Path(self.temp.name) / mismatch
                write_mission(mission)
                (mission / 'db/types.xml').write_text(
                    '<types><type name="Hammer"><nominal>6</nominal><category name="tools"/>'
                    '<tag name="floor"/><usage name="Village"/></type></types>')
                category = 'books' if mismatch == 'category' else 'tools'
                tags = '<tag name="shelves"/>' + ('<tag name="floor"/>' if mismatch == 'tag' else '')
                usage = 'Industrial' if mismatch == 'usage' else 'Village'
                # A receiver without the resulting shelf tag cannot replace this floor.
                if mismatch == 'tag':
                    tags = '<tag name="ground"/>'
                proto = ('<prototype><group name="Mismatch" lootmax="1">'
                         '<container name="lootFloor" lootmax="1"><category name="tools"/>'
                         '<tag name="floor"/><usage name="Village"/>' + point(0) + '</container>'
                         '<container name="shelf" lootmax="0"><category name="' + category + '"/>'
                         + tags + '<usage name="' + usage + '"/>' + point(1) + '</container></group></prototype>')
                (mission / 'mapgroupproto.xml').write_text(proto)
                receipt = self.lb.install(mission, multiplier=1.0, points=None, floor_policy=policy_bytes())
                counts = receipt['counts']['floor_policy']
                self.assertEqual(counts['transferred'], 0, mismatch + ' cannot receive Hammer')
                self.assertFalse(accepts(containers_of(mission / 'mapgroupproto.xml', 'Mismatch')[0],
                                        rows_of(mission / 'db/types.xml')['Hammer']))
                self.assertEqual(counts['kept_without_shelf_room'], 0)
                self.assertEqual((counts['displaced'], counts['transferred'], counts['unplaced']), (1, 0, 1),
                                 'unmatched demand must be reported, never assigned to an incompatible shelf')

    def test_bags_firearms_and_uncategorized_parts_require_shelves(self):
        self.install()
        rows = rows_of(self.mission / 'db/types.xml')
        for name in ('SyntheticBag', 'AKM', 'Sedan_Door'):
            self.assertEqual([t.get('name') for t in rows[name].findall('tag')], ['shelves'], name)

    def test_displaced_capacity_uses_compatible_shelves_and_reports_unplaced_remainder(self):
        receipt = self.install()
        floor, shelf, _weapons = containers_of(self.mission / 'mapgroupproto.xml', 'Land_House_S4')
        counts = receipt['counts']['floor_policy']
        self.assertEqual((counts['displaced'], counts['transferred'], counts['unplaced']), (6, 2, 4))
        self.assertEqual((counts['slots_before'], counts['slots_after']), (6, 3),
                         'reported usable capacity must respect group limits')
        self.assertEqual(floor.get('lootmax'), '4', 'transferred slots leave the floor budget')
        self.assertEqual(shelf.get('lootmax'), '3', 'group limit bounds estimated displacement')
        def usable(data):
            root = ET.fromstring(data)
            return sum(min(int(g.get('lootmax')), sum(min(int(c.get('lootmax')), len(c.findall('point')))
                       for c in g.findall('container'))) for g in root.findall('group'))
        self.assertEqual(usable(self.before['mapgroupproto.xml']), counts['slots_before'])
        self.assertEqual(usable((self.mission / 'mapgroupproto.xml').read_bytes()), counts['slots_after'])
        self.assertEqual(sum(row['unplaced_slots'] for row in counts['supply_gaps'].values()), counts['unplaced'])
        rows = rows_of(self.mission / 'db/types.xml')
        group = ET.parse(self.mission / 'mapgroupproto.xml').getroot().find('group')
        hammer_capacity = min(int(group.get('lootmax')), sum(
            min(int(c.get('lootmax')), len(c.findall('point'))) for c in group.findall('container')
            if accepts(c, rows['Hammer'])))
        self.assertEqual(hammer_capacity, 3, 'usable tool capacity survives the group limit')

    def test_repeat_generation_is_deterministic_and_policy_is_idempotent(self):
        from tools.package import loot_floor_policy as policy
        first = self.lb.plan(self.mission, multiplier=1.0, points=None, floor_policy=policy_bytes())
        second = self.lb.plan(self.mission, multiplier=1.0, points=None, floor_policy=policy_bytes())
        self.assertEqual(first, second)
        self.install()
        output = {name: (self.mission / name).read_bytes() for name in self.before}
        with self.assertRaisesRegex(ValueError, 'never applied twice'):
            self.install()
        self.assertEqual(output, {name: (self.mission / name).read_bytes() for name in self.before})
        types, rows = policy.retag_types(output['db/types.xml'], policy.parse_policy(policy_bytes()))
        proto, _ = policy.rebalance_proto(output['mapgroupproto.xml'], [rows],
                                          policy.parse_policy(policy_bytes()))
        self.assertEqual(types, output['db/types.xml'])
        self.assertEqual(proto, output['mapgroupproto.xml'])
        self.lb.rollback(self.mission)
        self.install()
        self.assertEqual(output, {name: (self.mission / name).read_bytes() for name in self.before})

    def test_transfer_is_capped_by_the_shelf_points_and_the_unplaced_remainder_is_reported(self):
        receipt = self.install(capacity={'enabled': True, 'max_container_lootmax': 3, 'preserve_tolerance': 0.5})
        shelf = containers_of(self.mission / 'mapgroupproto.xml', 'Land_House_S4')[1]
        self.assertEqual(shelf.get('lootmax'), '3', 'never above the named cap')
        counts = receipt['counts']['floor_policy']
        self.assertEqual((counts['transferred'], counts['unplaced']), (2, 4))

    def test_mixed_floor_shelf_tags_require_evidenced_receivers_even_at_height(self):
        self.install()
        low, high = containers_of(self.mission / 'mapgroupproto.xml', 'Land_Mixed_S4')
        self.assertEqual([t.get('name') for t in low.findall('tag')], ['floor'], 'floor-height points are floor only')
        self.assertEqual([t.get('name') for t in high.findall('tag')], ['floor'],
                         'height alone does not establish a shelf surface')

    def test_self_closing_groups_in_a_prototype_are_skipped_not_refused(self):
        path = self.mission / 'mapgroupproto.xml'
        path.write_bytes(path.read_bytes().replace(b'<prototype>', b'<prototype>\n    <group name="Land_Empty_S4" lootmax="1" />', 1))
        self.install()
        floor = containers_of(path, 'Land_House_S4')[0]
        self.assertEqual(floor.get('name'), 'lootFloor')

    def test_opt_out_and_missing_policy_leave_every_byte_to_the_plain_boost(self):
        plain = Path(self.temp.name) / 'plain'
        write_mission(plain)
        self.lb.install(plain, multiplier=1.0, points=None, floor_policy=None)
        self.lb.rollback(plain)
        self.install(enabled=False)
        for name in ('db/types.xml', 'mapgroupproto.xml'):
            self.assertEqual((self.mission / name).read_bytes(), self.before[name], name)
        report = json.loads((self.mission / self.lb.MANAGED / 'receipt.json').read_bytes())
        self.assertFalse(report['counts']['floor_policy']['enabled'])

    def test_rollback_restores_every_file_byte_exact(self):
        self.install()
        self.assertNotEqual((self.mission / 'db/types.xml').read_bytes(), self.before['db/types.xml'])
        self.lb.rollback(self.mission)
        for name, data in self.before.items():
            self.assertEqual((self.mission / name).read_bytes(), data, name)

    def test_policy_validation_refuses_unbounded_or_unnamed_values(self):
        from tools.package import loot_floor_policy as policy
        for bad in ({'floor_band_m': 50.0}, {'floor_class_patterns': ['(']}, {'floor_categories': ['weapons']},
                    {'capacity': {'enabled': True, 'max_container_lootmax': 0, 'preserve_tolerance': 0.1}},
                    {'kind': 'other'}, {'enabled': 'yes'}):
            with self.assertRaises(ValueError, msg=str(bad)):
                policy.parse_policy(policy_bytes(**bad))


class CommittedPolicy(unittest.TestCase):
    def setUp(self):
        from tools.package import loot_floor_policy as policy
        self.policy = policy
        self.doc = policy.parse_policy((REPO / policy.FLOOR_POLICY).read_bytes())

    def test_authored_admission_is_derived_from_policy_for_every_ledger_row(self):
        ledger = json.loads((REPO / 'config/loot-dispositions.json').read_bytes())
        categories = set(self.doc['floor_categories'])
        explicit = set(self.doc['floor_classes'])
        # Category and exact-name membership are the policy's data contract.
        # Invented out-of-policy category prevents assumptions about class ancestry.
        for row in ledger['entries']:
            name = row['class']
            for category in categories | {'synthetic_unlisted_category'}:
                with self.subTest(name=name, category=category):
                    self.assertEqual(self.policy.floor_eligible(name, category, self.doc),
                                     category in categories or name in explicit)
        for name in explicit:
            self.assertTrue(self.policy.floor_eligible(name, 'synthetic_unlisted_category', self.doc))

    def test_retagging_authored_admission_preserves_supply_and_row_identity(self):
        ledger = json.loads((REPO / 'config/loot-dispositions.json').read_bytes())
        root = ET.Element('types')
        for index, row in enumerate(ledger['entries'], 1):
            node = ET.SubElement(root, 'type', name=row['class'])
            ET.SubElement(node, 'nominal').text = str(index)
            ET.SubElement(node, 'min').text = str(index // 2)
            ET.SubElement(node, 'category', name='synthetic_unlisted_category')
        original = ET.tostring(root)
        rewritten, _ = self.policy.retag_types(original, self.doc)
        def supply(data):
            return {n.get('name'): (n.findtext('nominal'), n.findtext('min'))
                    for n in ET.fromstring(data)}
        self.assertEqual(supply(original), supply(rewritten))
        again, _ = self.policy.retag_types(rewritten, self.doc)
        self.assertEqual(rewritten, again)

    def test_listed_classes_are_plain_names_and_patterns_are_refused(self):
        for name in self.doc['floor_classes']:
            self.assertRegex(name, r'^[A-Za-z0-9_]{1,80}$')
        self.assertEqual(self.doc['floor_class_patterns'], [])
        with self.assertRaisesRegex(ValueError, 'exact class names'):
            self.policy.parse_policy(policy_bytes(floor_class_patterns=['Bag$']))


if __name__ == '__main__':
    unittest.main()
