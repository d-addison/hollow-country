"""Curated firearms roster: synthetic CE mission only. Offline tests never establish DayZ behaviour."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.package import economy, firearms

ROSTER_PATH = Path(__file__).resolve().parents[2] / 'tools/package/firearms_roster.json'


def entry(name, nominal, minimum, lifetime, restock, usage, value, extra=''):
    return f'''<type name="{name}"><nominal>{nominal}</nominal><lifetime>{lifetime}</lifetime><restock>{restock}</restock>
<min>{minimum}</min><quantmin>30</quantmin><quantmax>80</quantmax><cost>100</cost>
<flags count_in_cargo="0" count_in_hoarder="0" count_in_map="1" count_in_player="0" crafted="0" deloot="0"/>
<category name="weapons"/>{extra}{''.join(f'<usage name="{u}"/>' for u in usage)}{''.join(f'<value name="{v}"/>' for v in value)}</type>'''


def synthetic(root):
    (root / 'db').mkdir(parents=True)
    rows = [entry('SynthWoodRifle', 40, 30, 14400, 0, ['Town'], ['Tier2']),
            entry('SynthModernRifle', 8, 6, 7200, 3600, ['Military'], ['Tier4']),
            entry('SynthZeroRifle', 0, 0, 14400, 0, ['Hunting'], []),
            entry('SynthMag', 30, 25, 14400, 0, ['Military'], ['Tier2']),
            entry('SynthAmmo', 100, 70, 14400, 0, ['Town'], [], '<tag name="shelves"/>'),
            entry('Unrelated', 9, 7, 100, 0, ['Town'], [])]
    (root / 'db/types.xml').write_text('<types>' + ''.join(rows) + '</types>')
    (root / 'cfgeconomycore.xml').write_bytes(
        b'<?xml version="1.0"?><economycore><!--keep exactly--><defaults/></economycore>')
    (root / 'cfglimitsdefinition.xml').write_text(
        '<lists><usageflags><usage name="Town"/><usage name="Village"/><usage name="Military"/>'
        '<usage name="Hunting"/></usageflags><valueflags><value name="Tier1"/><value name="Tier2"/>'
        '<value name="Tier3"/><value name="Tier4"/></valueflags></lists>')
    (root / 'mapgroupproto.xml').write_text('<prototype><group name="G" lootmax="0"/></prototype>')
    (root / 'mapgrouppos.xml').write_text('<map><group name="G" pos="1 2 3"/></map>')


def roster():
    return {'schema': 1, 'name': 'synthetic-roster', 'players': '3-6',
            'entries': [
                {'class': 'SynthWoodRifle', 'kind': 'weapon', 'role': 'wood', 'tier': 'common',
                 'set': {'nominal': 12, 'min': 9}, 'add_usage': ['Village'],
                 'ammo': ['SynthAmmo'], 'magazines': [], 'justification': 'wood stock'},
                {'class': 'SynthModernRifle', 'kind': 'weapon', 'role': 'modern', 'tier': 'rare',
                 'set': {'nominal': 2, 'min': 1, 'lifetime': 10800, 'restock': 7200},
                 'set_value': ['Tier3', 'Tier4'], 'ammo': ['SynthAmmo'], 'magazines': ['SynthMag'],
                 'justification': 'conventional'},
                {'class': 'SynthZeroRifle', 'kind': 'weapon', 'role': 'wood', 'tier': 'uncommon',
                 'set': {'nominal': 5, 'min': 3}, 'ammo': ['SynthAmmo'], 'magazines': [],
                 'justification': 'stock nominal zero; enabled by roster'},
                {'class': 'SynthMag', 'kind': 'magazine', 'role': 'support', 'tier': 'uncommon',
                 'set': {'nominal': 4, 'min': 2}, 'justification': 'matching magazine'},
                {'class': 'SynthAmmo', 'kind': 'ammo', 'role': 'support', 'tier': 'common',
                 'set': {'nominal': 30, 'min': 20}, 'justification': 'matching ammo'}],
            'deferred_datamined': [
                {'class': 'SynthOddRifle', 'status': 'requires-local-acceptance', 'note': 'not in types'}]}


def children(element):
    return {n.tag: (n.text or '').strip() for n in element if n.tag not in {'usage', 'value'}}


class RosterGeneration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'source'
        self.root.mkdir()
        synthetic(self.root)
        self.stock = {t.get('name'): t for t in ET.parse(self.root / 'db/types.xml').getroot()}

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_selected_budget_fields_change_and_everything_else_is_stock(self):
        delta = firearms.generate(self.root, roster())
        out = {t.get('name'): t for t in ET.fromstring(delta['ce/types.xml'])}
        self.assertEqual(sorted(out), ['SynthAmmo', 'SynthMag', 'SynthModernRifle', 'SynthWoodRifle', 'SynthZeroRifle'])
        wood = out['SynthWoodRifle']
        self.assertEqual(wood.findtext('nominal'), '12')
        self.assertEqual(wood.findtext('min'), '9')
        self.assertEqual(wood.findtext('lifetime'), '14400')
        self.assertEqual(wood.find('flags').attrib, self.stock['SynthWoodRifle'].find('flags').attrib)
        self.assertEqual([u.get('name') for u in wood.findall('usage')], ['Town', 'Village'])
        self.assertEqual([v.get('name') for v in wood.findall('value')], ['Tier2'])
        modern = out['SynthModernRifle']
        self.assertEqual((modern.findtext('lifetime'), modern.findtext('restock')), ('10800', '7200'))
        self.assertEqual([v.get('name') for v in modern.findall('value')], ['Tier3', 'Tier4'])
        self.assertEqual([u.get('name') for u in modern.findall('usage')], ['Military'])
        self.assertNotIn('Unrelated', out)
        self.assertEqual(out['SynthAmmo'].find('tag').attrib, {'name': 'shelves'})
        self.assertEqual(out['SynthZeroRifle'].findtext('quantmin'), '30')

    def test_unlisted_fields_keep_stock_text_and_stock_is_untouched(self):
        before = {p.name: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        delta = firearms.generate(self.root, roster())
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        out = {t.get('name'): t for t in ET.fromstring(delta['ce/types.xml'])}
        for name, item in out.items():
            stock = children(self.stock[name])
            changed = {k for k, v in children(item).items() if stock[k] != v}
            self.assertLessEqual(changed, {'nominal', 'min', 'lifetime', 'restock'}, name)
            self.assertEqual(list(stock), list(children(item)), name)

    def test_report_is_evidence_only_and_names_roles_and_deferred_items(self):
        delta = firearms.generate(self.root, roster())
        report = json.loads(delta['economy-report.json'])
        self.assertEqual(report['status'], 'offline-only-runtime-pending')
        self.assertEqual(report['kind'], 'firearms-roster')
        self.assertFalse(report['loot_fix_claim'])
        self.assertEqual(report['deferred_datamined'][0]['class'], 'SynthOddRifle')
        self.assertEqual(report['deferred_datamined'][0]['status'], 'requires-local-acceptance')
        rows = {r['class']: r for r in report['entries']}
        self.assertEqual(rows['SynthWoodRifle']['stock']['nominal'], 40)
        self.assertEqual(rows['SynthWoodRifle']['candidate']['nominal'], 12)
        self.assertEqual(rows['SynthWoodRifle']['role'], 'wood')
        self.assertEqual(report['totals']['weapon_nominal_stock'], 48)
        self.assertEqual(report['totals']['weapon_nominal_candidate'], 19)
        self.assertEqual(report['runtime_acceptance'], 'pending')
        self.assertEqual(delta, firearms.generate(self.root, roster()))

    def test_deferred_datamined_classes_never_reach_the_delta(self):
        delta = firearms.generate(self.root, roster())
        self.assertNotIn(b'SynthOddRifle', delta['ce/types.xml'])

    def test_refuses_invalid_roster_entries(self):
        base = roster()
        def mutate(fn):
            r = copy.deepcopy(base)
            fn(r)
            return r
        cases = {
            'unknown class': lambda r: r['entries'][0].update({'class': 'Nope'}),
            'duplicate class': lambda r: r['entries'].append(copy.deepcopy(r['entries'][0])),
            'min above nominal': lambda r: r['entries'][0].update({'set': {'nominal': 3, 'min': 9}}),
            'negative nominal': lambda r: r['entries'][0].update({'set': {'nominal': -1, 'min': 0}}),
            'float nominal': lambda r: r['entries'][0].update({'set': {'nominal': 2.5, 'min': 1}}),
            'bool nominal': lambda r: r['entries'][0].update({'set': {'nominal': True, 'min': 0}}),
            'unsupported field': lambda r: r['entries'][0]['set'].update({'cost': 5}),
            'unknown usage': lambda r: r['entries'][0].update({'add_usage': ['Invented']}),
            'unknown value': lambda r: r['entries'][1].update({'set_value': ['Tier9']}),
            'duplicate value': lambda r: r['entries'][1].update({'set_value': ['Tier3', 'Tier3']}),
            'bad role': lambda r: r['entries'][0].update({'role': 'futuristic'}),
            'bad kind': lambda r: r['entries'][0].update({'kind': 'tank'}),
            'missing justification': lambda r: r['entries'][0].pop('justification'),
            'extra top field': lambda r: r.update({'nominal_multiplier': 5}),
            'extra entry field': lambda r: r['entries'][0].update({'multiplier': 2}),
            'schema': lambda r: r.update({'schema': 2}),
            'unreferenced ammo': lambda r: r['entries'][0].update({'ammo': ['SynthMissingAmmo']}),
            'unreferenced magazine': lambda r: r['entries'][1].update({'magazines': ['SynthMissingMag']}),
            'deferred active': lambda r: r['deferred_datamined'][0].update({'status': 'accepted'}),
            'deferred overlaps entry': lambda r: r['deferred_datamined'].append(
                {'class': 'SynthWoodRifle', 'status': 'requires-local-acceptance', 'note': 'x'}),
        }
        for label, fn in cases.items():
            with self.subTest(label), self.assertRaises(ValueError):
                firearms.generate(self.root, mutate(fn))

    def test_refuses_existing_core_extensions_and_missing_usage(self):
        (self.root / 'cfgeconomycore.xml').write_text(
            '<economycore><ce folder="other"><file name="types.xml" type="types"/></ce></economycore>')
        with self.assertRaises(ValueError):
            firearms.generate(self.root, roster())

    def test_install_and_rollback_are_byte_exact_and_core_is_only_extended(self):
        stage = Path(self.tmp.name) / 'delta'
        firearms.write_delta(stage, firearms.generate(self.root, roster()))
        target = Path(self.tmp.name) / 'private-copy'
        shutil.copytree(self.root, target)
        before = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob('*') if p.is_file()}
        firearms.install(stage, target)
        core = (target / 'cfgeconomycore.xml').read_bytes()
        self.assertIn(b'<!--keep exactly-->', core)
        self.assertIn(b'folder="hollow-country/ce"', core)
        self.assertEqual((target / 'db/types.xml').read_bytes(), before['db/types.xml'])
        with self.assertRaises(ValueError):
            firearms.install(stage, target)
        firearms.rollback(target)
        after = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_install_refuses_the_steam_path_and_tampered_stage(self):
        stage = Path(self.tmp.name) / 'delta'
        firearms.write_delta(stage, firearms.generate(self.root, roster()))
        with self.assertRaises(ValueError):
            firearms.install(stage, Path('/mnt/g/SteamLibrary/steamapps/common/DayZServer/mpmissions/x'))
        (stage / 'ce/types.xml').write_text('<types/>')
        with self.assertRaises(ValueError):
            firearms.install(stage, self.root)


class EconomyMutableFields(unittest.TestCase):
    """Additive economy.install(mutable=...) used by the roster; default behaviour is unchanged."""

    def test_default_install_still_refuses_a_budget_change(self):
        with tempfile.TemporaryDirectory() as t:
            source = Path(t) / 'source'
            source.mkdir()
            synthetic(source)
            stage = Path(t) / 'delta'
            firearms.write_delta(stage, firearms.generate(source, roster()))
            target = Path(t) / 'copy'
            shutil.copytree(source, target)
            with self.assertRaises(ValueError):
                economy.install(stage, target)
            self.assertFalse((target / 'hollow-country').exists())
            economy.install(stage, target, mutable=firearms.MUTABLE)
            economy.rollback(target)

    def test_mutable_cannot_include_unsafe_tags(self):
        with tempfile.TemporaryDirectory() as t:
            source = Path(t) / 'source'
            source.mkdir()
            synthetic(source)
            stage = Path(t) / 'delta'
            firearms.write_delta(stage, firearms.generate(source, roster()))
            for bad in ({'flags'}, {'usage', 'cost'}, {'category'}, {'quantmax'}):
                with self.subTest(bad), self.assertRaises(ValueError):
                    economy.install(stage, source, mutable=bad)


class CommittedRoster(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(ROSTER_PATH.read_text())

    def test_schema_and_vocabulary(self):
        firearms.validate_roster(self.data)

    def test_counts_suit_three_to_six_players(self):
        weapons = [e for e in self.data['entries'] if e['kind'] == 'weapon']
        self.assertGreaterEqual(len(weapons), 20)
        for e in weapons:
            self.assertLessEqual(e['set']['nominal'], 16, e['class'])
        self.assertLessEqual(sum(e['set']['nominal'] for e in weapons), 200)
        for e in self.data['entries']:
            self.assertGreaterEqual(e['set']['nominal'], e['set']['min'])
            self.assertTrue(e['justification'].strip())

    def test_roles_wood_and_modern_are_both_present_and_nothing_futuristic(self):
        roles = {e['role'] for e in self.data['entries'] if e['kind'] == 'weapon'}
        self.assertEqual(roles, {'wood', 'modern'})
        banned = {'VSS', 'ASVAL', 'Vikhr', 'Groza', 'M249', 'SV98', 'DartGun', 'Shockpistol', 'M79', 'LAW',
                  'RPG7', 'Flaregun', 'PP19', 'Aug', 'AugShort'}
        names = {e['class'] for e in self.data['entries']}
        self.assertEqual(names & banned, set())

    def test_every_ammo_and_magazine_reference_is_in_the_roster(self):
        by_kind = {}
        for e in self.data['entries']:
            by_kind.setdefault(e['kind'], set()).add(e['class'])
        for e in self.data['entries']:
            if e['kind'] == 'weapon':
                self.assertTrue(set(e['ammo']) <= by_kind['ammo'], e['class'])
                self.assertTrue(set(e['magazines']) <= by_kind['magazine'], e['class'])

    def test_deferred_datamined_are_all_pending_local_acceptance(self):
        deferred = self.data['deferred_datamined']
        self.assertTrue(deferred)
        self.assertEqual({d['status'] for d in deferred}, {'requires-local-acceptance'})
        self.assertFalse({d['class'] for d in deferred} & {e['class'] for e in self.data['entries']})

    def test_roster_is_small_and_carries_no_vanilla_dump(self):
        self.assertLess(ROSTER_PATH.stat().st_size, 40_000)
        self.assertNotIn('<type ', ROSTER_PATH.read_text())


if __name__ == '__main__':
    unittest.main()
