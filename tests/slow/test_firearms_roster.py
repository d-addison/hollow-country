"""Curated firearms roster: synthetic CE mission only. Offline tests never establish DayZ behaviour."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from tools.package import economy, firearms
from tools.setup import local_test_session

# Explicit synthetic parent budgets; installed config evidence is checked separately.
NEW_PARENTS = {
    'MakarovPB': 'MakarovIJ70', 'Mag_MakarovPB_8Rnd': 'Mag_IJ70_8Rnd',
    'Winchester70_Black': 'Winchester70', 'Winchester70_Green': 'Winchester70',
    'B95_Black': 'B95', 'B95_Green': 'B95', 'CZ527_Camo': 'CZ527',
    'CZ527_Green': 'CZ527', 'CZ527_desert': 'CZ527', 'CZ527_winter': 'CZ527'}

ROSTER_PATH = Path(__file__).resolve().parents[2] / 'tools/package/firearms_roster.json'
DATAMINED_WEAPONS = {'LeeEnfield', 'MP18', 'Luger', 'SKS_Black', 'SKS_Desert', 'SKS_Green', 'SKS_Winter',
                     'Mosin9130_Black', 'Mosin9130_Winter', 'SVD_Wooden'} | (set(NEW_PARENTS) - {'Mag_MakarovPB_8Rnd'})
DATAMINED_MAGAZINES = {'Mag_LeeEnfield_10Rnd', 'Mag_MP18_Drum32Rnd', 'Mag_Luger_8Rnd', 'Mag_MakarovPB_8Rnd'}
# Historical first proposal; unsplit curated families retain the owner's established shares.
V1_FIRST_PROPOSAL = {
    'Mosin9130': (12, 9), 'Mosin9130_Woodland': (5, 3), 'SKS': (6, 4), 'SKS_Woodland': (3, 2),
    'Izh18': (14, 11), 'Izh18Shotgun': (10, 8), 'Izh43Shotgun': (8, 6), 'Repeater': (8, 6),
    'Winchester70': (5, 4), 'CZ527': (8, 6), 'CZ527_Woodland': (5, 4), 'B95': (5, 4),
    'LeeEnfield': (6, 4), 'MP18': (2, 1), 'Luger': (3, 2), 'Mp133Shotgun': (4, 3), 'Magnum': (5, 4),
    'AKM': (2, 1), 'Colt1911': (8, 6), 'MakarovIJ70': (8, 6), 'P1': (6, 5), 'Glock19': (6, 5),
    'FNX45': (3, 2), 'CZ75': (4, 3), 'Ruger1022': (6, 4), 'M16A2': (2, 1), 'AK74': (3, 2),
    'MP5K': (3, 2), 'Saiga': (2, 1), 'SVD': (2, 1)}


# Explicit SYNTHETIC pre-round-2 native-budget policy, never an engine assertion.
NATIVE_BUDGETS = {
    'AK101': (4, 2),
    'AKS74U': (8, 5),
    'ASVAL': (3, 2),
    'AmmoBox_00buck_10rnd': (15, 11),
    'AmmoBox_12gaRubberSlug_10Rnd': (12, 10),
    'AmmoBox_12gaSlug_10Rnd': (15, 10),
    'AmmoBox_22_50Rnd': (29, 21),
    'AmmoBox_308WinTracer_20Rnd': (4, 2),
    'AmmoBox_308Win_20Rnd': (8, 5),
    'AmmoBox_357_20Rnd': (19, 14),
    'AmmoBox_380_35rnd': (15, 11),
    'AmmoBox_45ACP_25rnd': (15, 10),
    'AmmoBox_545x39Tracer_20Rnd': (4, 2),
    'AmmoBox_545x39_20Rnd': (6, 3),
    'AmmoBox_556x45Tracer_20Rnd': (4, 2),
    'AmmoBox_556x45_20Rnd': (9, 6),
    'AmmoBox_762x39Tracer_20Rnd': (4, 2),
    'AmmoBox_762x39_20Rnd': (9, 6),
    'AmmoBox_762x54Tracer_20Rnd': (4, 3),
    'AmmoBox_762x54_20Rnd': (8, 6),
    'AmmoBox_9x19_25rnd': (20, 14),
    'AmmoBox_9x39AP_20Rnd': (3, 1),
    'AmmoBox_9x39_20Rnd': (4, 2),
    'Ammo_12gaRubberSlug': (28, 24),
    'Ammo_308WinTracer': (12, 8),
    'Ammo_40mm_Chemgas': (5, 3),
    'Ammo_40mm_Explosive': (8, 5),
    'Ammo_40mm_Smoke_Black': (15, 8),
    'Ammo_40mm_Smoke_Green': (15, 8),
    'Ammo_40mm_Smoke_Red': (15, 8),
    'Ammo_40mm_Smoke_White': (15, 8),
    'Ammo_545x39Tracer': (9, 5),
    'Ammo_556x45Tracer': (11, 7),
    'Ammo_762x39Tracer': (20, 14),
    'Ammo_762x54Tracer': (13, 9),
    'Ammo_9x39': (9, 5),
    'Ammo_9x39AP': (6, 3),
    'Ammo_HuntingBolt': (25, 18),
    'Aug': (1, 1),
    'AugShort': (4, 3),
    'CZ550': (14, 12),
    'CZ61': (5, 4),
    'Crossbow_Autumn': (5, 3),
    'Crossbow_Black': (5, 3),
    'Crossbow_Wood': (3, 1),
    'Deagle': (21, 17),
    'Deagle_Gold': (4, 3),
    'Derringer_Grey': (20, 15),
    'FAL': (2, 1),
    'FAMAS': (8, 6),
    'LongHorn': (25, 20),
    'M14': (2, 1),
    'M4A1': (1, 1),
    'M79': (3, 1),
    'MKII': (30, 27),
    'Mag_AK101_30Rnd': (16, 13),
    'Mag_AK74_45Rnd': (4, 2),
    'Mag_AKM_Drum75Rnd': (1, 0),
    'Mag_AKM_Palm30Rnd': (3, 2),
    'Mag_Aug_30Rnd': (6, 4),
    'Mag_CMAG_10Rnd': (12, 10),
    'Mag_CMAG_20Rnd': (8, 5),
    'Mag_CMAG_30Rnd': (6, 4),
    'Mag_CMAG_40Rnd': (4, 2),
    'Mag_CZ550_10Rnd': (8, 5),
    'Mag_CZ61_20Rnd': (14, 10),
    'Mag_Deagle_9rnd': (30, 20),
    'Mag_FAL_20Rnd': (9, 6),
    'Mag_FAMAS_25Rnd': (12, 10),
    'Mag_M14_10Rnd': (4, 2),
    'Mag_M14_20Rnd': (4, 2),
    'Mag_MKII_10Rnd': (30, 20),
    'Mag_PM73_15Rnd': (12, 8),
    'Mag_PM73_25Rnd': (7, 5),
    'Mag_PP19_64Rnd': (12, 10),
    'Mag_Ruger1022_30Rnd': (30, 20),
    'Mag_SSG82_5rnd': (10, 7),
    'Mag_STANAG_60Rnd': (3, 1),
    'Mag_SV98_10Rnd': (4, 2),
    'Mag_Saiga_5Rnd': (10, 7),
    'Mag_Saiga_Drum20Rnd': (3, 1),
    'Mag_Scout_5Rnd': (8, 4),
    'Mag_UMP_25Rnd': (18, 15),
    'Mag_VAL_20Rnd': (4, 2),
    'Mag_VSS_10Rnd': (6, 4),
    'Mag_Vikhr_30Rnd': (3, 1),
    'PM73Rak': (5, 4),
    'PP19': (14, 11),
    'R12': (6, 5),
    'SSG82': (12, 10),
    'SV98': (2, 1),
    'Scout': (1, 1),
    'Scout_Chernarus': (5, 3),
    'UMP45': (12, 10),
    'VSS': (6, 4),
    'Vikhr': (4, 2)}


def entry(name, nominal, minimum, lifetime, restock, usage, value, extra=''):
    return f'''<type name="{name}"><nominal>{nominal}</nominal><lifetime>{lifetime}</lifetime><restock>{restock}</restock>
<min>{minimum}</min><quantmin>30</quantmin><quantmax>80</quantmax><cost>100</cost>
<flags count_in_cargo="0" count_in_hoarder="0" count_in_map="1" count_in_player="0" crafted="0" deloot="0"/>
<category name="weapons"/>{extra}{''.join(f'<usage name="{u}"/>' for u in usage)}{''.join(f'<value name="{v}"/>' for v in value)}</type>'''


def synthetic(root):
    (root / 'db').mkdir(parents=True)
    rows = [entry('Ammo_45ACP', 20, 10, 14400, 0, ['Military'], []),
            entry('SynthWoodRifle', 40, 30, 14400, 0, ['Town'], ['Tier2']),
            entry('SynthModernRifle', 8, 6, 7200, 3600, ['Military'], ['Tier4']),
            entry('SynthZeroRifle', 0, 0, 14400, 0, ['Hunting'], []),
            entry('SynthMag', 30, 25, 14400, 0, ['Military'], ['Tier2']),
            entry('SynthZeroMag', 0, 0, 14400, 0, ['Hunting'], []),
            entry('SynthBareRifle', 0, 0, 14400, 0, [], []),
            entry('SynthAmmo', 100, 70, 14400, 0, ['Town'], [], '<tag name="shelves"/>'),
            entry('Unrelated', 9, 7, 100, 0, ['Town'], [])]
    (root / 'db/types.xml').write_text('<types>' + ''.join(rows) + '</types>')
    (root / 'cfgeconomycore.xml').write_bytes(
        b'<?xml version="1.0"?><economycore><!--keep exactly--><defaults/></economycore>')
    (root / 'cfglimitsdefinition.xml').write_text(
        '<lists><usageflags><usage name="Town"/><usage name="Village"/><usage name="Military"/>'
        '<usage name="Farm"/><usage name="ContaminatedArea"/><usage name="Police"/><usage name="Hunting"/><usage name="Prison"/></usageflags><valueflags><value name="Tier1"/><value name="Tier2"/>'
        '<value name="Tier3"/><value name="Tier4"/></valueflags></lists>')
    (root / 'mapgroupproto.xml').write_text('<prototype><group name="G" lootmax="0"/></prototype>')
    (root / 'mapgrouppos.xml').write_text('<map><group name="G" pos="1 2 3"/></map>')
    # SYNTHETIC positive carrier references mirror the authored names, not engine evidence.
    carriers = ET.Element('spawnabletypes')
    for weapon in json.loads(ROSTER_PATH.read_bytes())['entries']:
        parts = [part for part in weapon.get('parts', []) if part['route'] == 'native-carrier']
        if parts:
            host = ET.SubElement(carriers, 'type', name=weapon['class'])
            group = ET.SubElement(host, 'attachments', chance='1.0')
            for part in parts:
                ET.SubElement(group, 'item', name=part['class'], chance='1.0')
    (root / 'cfgspawnabletypes.xml').write_bytes(ET.tostring(carriers))


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
                 'set': {'nominal': 5, 'min': 3}, 'ammo': ['SynthAmmo'], 'magazines': ['SynthZeroMag'],
                 'datamined': True, 'acceptance': 'pending-local',
                 'justification': 'stock nominal zero; enabled by roster'},
                {'class': 'SynthZeroMag', 'kind': 'magazine', 'role': 'support', 'tier': 'rare',
                 'set': {'nominal': 2, 'min': 1}, 'datamined': True, 'acceptance': 'pending-local',
                 'justification': 'magazine only the datamined rifle needs'},
                {'class': 'SynthMag', 'kind': 'magazine', 'role': 'support', 'tier': 'uncommon',
                 'set': {'nominal': 4, 'min': 2}, 'justification': 'matching magazine'},
                {'class': 'SynthAmmo', 'kind': 'ammo', 'role': 'support', 'tier': 'common',
                 'set': {'nominal': 30, 'min': 20}, 'justification': 'matching ammo'}],
            'deferred_datamined': [
                {'class': 'SynthOddRifle', 'status': 'requires-local-acceptance', 'note': 'not in types'}]}


def patch_roster(testcase, directory, data=None):
    """SYNTHETIC shipped roster file: exercise the real installer permission check."""
    path = Path(directory) / 'SYNTHETIC-shipped-roster.json'
    path.write_bytes(economy.encode(data or roster()))
    patcher = mock.patch.object(firearms, 'ROSTER_PATH', path)
    patcher.start()
    testcase.addCleanup(patcher.stop)
    return path


def children(element):
    return {n.tag: (n.text or '').strip() for n in element if n.tag not in {'usage', 'value'}}


class RosterGeneration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'source'
        self.root.mkdir()
        synthetic(self.root)
        self.stock = {t.get('name'): t for t in ET.parse(self.root / 'db/types.xml').getroot()}
        self.shipped_roster = patch_roster(self, self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_spawning_weapons_need_effective_nonzero_support(self):
        """SYNTHETIC overrides must win over positive stock support counts."""
        for name in ('SynthAmmo', 'SynthMag'):
            r = roster()
            next(e for e in r['entries'] if e['class'] == name)['set'] = {'nominal': 0, 'min': 0}
            with self.subTest(support=name), self.assertRaisesRegex(ValueError, 'spawning weapon|HC_MILITARY_LOOT_RETENTION'):
                firearms.generate(self.root, r)

    def test_zeroed_alternatives_and_weapons_require_allowlist(self):
        """SYNTHETIC zeroed alternatives and weapons fail the retention contract."""
        r = roster()
        modern = next(e for e in r['entries'] if e['class'] == 'SynthModernRifle')
        modern['magazines'].append('SynthZeroMag')
        support = next(e for e in r['entries'] if e['class'] == 'SynthZeroMag')
        support.pop('datamined')
        support.pop('acceptance')
        next(e for e in r['entries'] if e['class'] == 'SynthMag')['set'] = {'nominal': 0, 'min': 0}
        with self.assertRaisesRegex(ValueError, 'HC_MILITARY_LOOT_RETENTION'):
            firearms.generate(self.root, r)
        for e in r['entries']:
            e['set'] = {'nominal': 0, 'min': 0}
        with self.assertRaisesRegex(ValueError, 'HC_MILITARY_LOOT_RETENTION'):
            firearms.generate(self.root, r)

    def test_effective_family_checks_use_supplied_custom_policy(self):
        custom = roster()
        for e in custom['entries']:
            e.update(family=e['class'], disposition='curated-family-split')
            if e['kind'] == 'ammo':
                e['unit_rounds'] = 20
        generated = []
        for e in custom['entries']:
            item = copy.deepcopy(self.stock[e['class']])
            for field, value in e['set'].items():
                item.find(field).text = str(value)
            generated.append(item)
        # A custom --roster must work even when the shipped policy cannot be read.
        with mock.patch.object(firearms, 'ROSTER_PATH', self.root / 'not-the-custom-policy.json'):
            firearms.check_effective_support(self.root, self.stock, custom['entries'], generated)
            generated[0].find('nominal').text = '13'
            with self.assertRaisesRegex(ValueError, 'family budget'):
                firearms.check_effective_support(self.root, self.stock, custom['entries'], generated)
        generated[0].find('nominal').text = '12'
        carriers = ET.Element('spawnabletypes')
        custom['entries'][0]['parts'] = [{'class': 'SynthNativePart', 'route': 'native-carrier'}]
        (self.root / 'cfgspawnabletypes.xml').write_bytes(ET.tostring(carriers))
        with self.assertRaisesRegex(ValueError, 'HC21_PART_ROUTE_MISSING'):
            firearms.check_effective_support(self.root, self.stock, custom['entries'], generated)

    def test_only_selected_budget_fields_change_and_everything_else_is_stock(self):
        delta = firearms.generate(self.root, roster())
        out = {t.get('name'): t for t in ET.fromstring(delta['ce/types.xml'])}
        self.assertEqual(sorted(out), ['SynthAmmo', 'SynthMag', 'SynthModernRifle', 'SynthWoodRifle', 'SynthZeroMag', 'SynthZeroRifle'])
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

    def test_datamined_rows_spawn_by_default_and_carry_the_pending_local_marker(self):
        delta = firearms.generate(self.root, roster())
        out = {t.get('name'): t for t in ET.fromstring(delta['ce/types.xml'])}
        self.assertEqual((out['SynthZeroRifle'].findtext('nominal'), out['SynthZeroMag'].findtext('nominal')),
                         ('5', '2'))
        report = json.loads(delta['economy-report.json'])
        rows = {r['class']: r for r in report['entries']}
        self.assertEqual(rows['SynthZeroRifle']['acceptance'], 'pending-local')
        self.assertEqual(rows['SynthZeroMag']['acceptance'], 'pending-local')
        self.assertNotIn('acceptance', rows['SynthWoodRifle'])
        self.assertEqual(report['datamined'], {'enabled': True, 'classes': ['SynthZeroMag', 'SynthZeroRifle']})

    def test_one_switch_disables_every_datamined_row_and_nothing_else(self):
        delta = firearms.generate(self.root, roster(), include_datamined=False)
        out = {t.get('name') for t in ET.fromstring(delta['ce/types.xml'])}
        self.assertEqual(out, {'SynthAmmo', 'SynthMag', 'SynthModernRifle', 'SynthWoodRifle'})
        report = json.loads(delta['economy-report.json'])
        self.assertEqual(report['datamined'], {'enabled': False, 'classes': ['SynthZeroMag', 'SynthZeroRifle']})
        self.assertEqual({r['class'] for r in report['entries']}, out)
        self.assertEqual(report['totals']['weapon_nominal_candidate'], 14)

    def test_cli_no_datamined_switch_reaches_the_delta(self):
        stage = Path(self.tmp.name) / 'cli-delta'
        path = Path(self.tmp.name) / 'roster.json'
        path.write_text(json.dumps(roster()))
        firearms.main(['generate', '--source', str(self.root), '--roster', str(path), '--out', str(stage),
                       '--no-datamined'])
        self.assertNotIn(b'SynthZeroRifle', (stage / 'ce/types.xml').read_bytes())

    def test_datamined_marker_rules(self):
        def with_(fn):
            r = roster()
            fn(r)
            return r
        zero = lambda r: next(e for e in r['entries'] if e['class'] == 'SynthZeroRifle')
        wood = lambda r: next(e for e in r['entries'] if e['class'] == 'SynthWoodRifle')
        cases = {
            'datamined without acceptance': lambda r: zero(r).pop('acceptance'),
            'acceptance not pending-local': lambda r: zero(r).update({'acceptance': 'accepted'}),
            'acceptance without datamined': lambda r: wood(r).update({'acceptance': 'pending-local'}),
            'datamined false': lambda r: zero(r).update({'datamined': False}),
            'non-datamined weapon needs a datamined magazine':
                lambda r: wood(r).update({'magazines': ['SynthZeroMag']}),
        }
        for label, fn in cases.items():
            with self.subTest(label), self.assertRaises(ValueError):
                firearms.generate(self.root, with_(fn))

    def test_a_datamined_class_with_no_stock_usage_gets_the_declared_usage(self):
        r = roster()
        r['entries'].append({'class': 'SynthBareRifle', 'kind': 'weapon', 'role': 'wood', 'tier': 'rare',
                             'set': {'nominal': 2, 'min': 1}, 'add_usage': ['Hunting'],
                             'set_value': ['Tier2'], 'ammo': ['SynthAmmo'], 'magazines': [],
                             'datamined': True, 'acceptance': 'pending-local', 'justification': 'no stock usage'})
        out = {t.get('name'): t for t in ET.fromstring(firearms.generate(self.root, r)['ce/types.xml'])}
        bare = out['SynthBareRifle']
        self.assertEqual([u.get('name') for u in bare.findall('usage')], ['Hunting'])
        self.assertEqual([v.get('name') for v in bare.findall('value')], ['Tier2'])
        tags = [n.tag for n in bare]
        self.assertLess(tags.index('category'), tags.index('usage'))
        self.assertLess(tags.index('usage'), tags.index('value'))
        stage = Path(self.tmp.name) / 'bare'
        firearms.write_delta(stage, firearms.generate(self.root, r))
        target = Path(self.tmp.name) / 'bare-target'
        shutil.copytree(self.root, target)
        self.shipped_roster.write_bytes(economy.encode(r))
        firearms.install(stage, target)  # install guard accepts the added usage/value only
        firearms.rollback(target)

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

    def test_install_rechecks_effective_support_after_rehashed_stage_tampering(self):
        """SYNTHETIC staged override disables all compatible ammo after generation."""
        files = firearms.generate(self.root, roster())
        root = ET.fromstring(files['ce/types.xml'])
        ammo = root.find("type[@name='SynthAmmo']")
        ammo.find('nominal').text = ammo.find('min').text = '0'
        files['ce/types.xml'] = ET.tostring(root)
        manifest = json.loads(files['delta-manifest.json'])
        manifest['files']['ce/types.xml'] = economy.sha(files['ce/types.xml'])
        files['delta-manifest.json'] = economy.encode(manifest)
        stage = Path(self.tmp.name) / 'tampered-delta'
        firearms.write_delta(stage, files)
        before = economy.snapshot(self.root)
        with self.assertRaisesRegex(ValueError, 'spawning weapon|HC_MILITARY_LOOT_RETENTION'):
            firearms.install(stage, self.root)
        self.assertEqual(before, economy.snapshot(self.root))
        self.assertFalse((self.root / economy.MANAGED).exists())

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

    def installed(self):
        stage = Path(self.tmp.name) / 'delta'
        firearms.write_delta(stage, firearms.generate(self.root, roster()))
        target = Path(self.tmp.name) / 'private-copy'
        shutil.copytree(self.root, target)
        firearms.install(stage, target)
        outside = Path(self.tmp.name) / 'operator-file-outside-mission.txt'
        outside.write_bytes(b'operator data: preserve exactly\n')
        return target, target / economy.MANAGED, outside

    def assert_refused_and_untouched(self, target, managed, outside):
        core = (target / 'cfgeconomycore.xml').read_bytes()
        with self.assertRaises(ValueError):
            firearms.rollback(target)
        self.assertEqual(outside.read_bytes(), b'operator data: preserve exactly\n')
        self.assertEqual((target / 'cfgeconomycore.xml').read_bytes(), core)
        self.assertTrue(managed.is_dir())

    def test_rollback_refuses_a_hardlinked_staging_file_and_leaves_the_outside_file_alone(self):
        target, managed, outside = self.installed()
        os.link(outside, managed / 'core.next')
        self.assert_refused_and_untouched(target, managed, outside)

    def test_rollback_refuses_a_symlinked_or_non_regular_staging_file(self):
        target, managed, outside = self.installed()
        os.symlink(outside, managed / 'core.next')
        self.assert_refused_and_untouched(target, managed, outside)
        (managed / 'core.next').unlink()
        os.mkfifo(managed / 'core.next')
        self.assert_refused_and_untouched(target, managed, outside)

    def test_rollback_refuses_hardlinked_managed_evidence(self):
        target, managed, outside = self.installed()
        os.link(managed / 'core.backup', outside.parent / 'second-name-for-backup')
        self.assert_refused_and_untouched(target, managed, outside)

    def test_rollback_replaces_a_stale_regular_staging_file_without_writing_through_it(self):
        target, managed, outside = self.installed()
        (managed / 'core.next').write_bytes(b'stale partial write')
        before = economy.sha((managed / 'core.backup').read_bytes())
        firearms.rollback(target)
        self.assertEqual(economy.sha((target / 'cfgeconomycore.xml').read_bytes()), before)
        self.assertFalse(managed.exists())

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


class ReviewedNewTypes(unittest.TestCase):
    """SYNTHETIC stock parents with odd budgets and retained tags; no engine claims."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'mission'
        synthetic(self.root)
        self.roster = json.loads(ROSTER_PATH.read_bytes())
        self.stock = {}
        for roster_entry in self.roster['entries']:
            class_name = roster_entry['class']
            if class_name not in NEW_PARENTS:
                self.stock[class_name] = ET.fromstring(entry(
                    class_name, 0 if roster_entry.get('datamined') else 51,
                    0 if roster_entry.get('datamined') else 39, 28800, 0, ['Town'], ['Tier2'], '<tag name="shelves"/>'))
        stock_root = ET.Element('types')
        stock_root.extend(self.stock.values())
        (self.root / 'db/types.xml').write_bytes(ET.tostring(stock_root))
        self.before = economy.snapshot(self.root)

    def test_nine_variants_and_pb_magazine_are_reviewed_and_pending(self):
        enabled = {e['class']: e for e in self.roster['entries']}
        self.assertTrue(set(NEW_PARENTS) <= set(enabled))
        self.assertFalse(set(NEW_PARENTS) & {d['class'] for d in self.roster['deferred_datamined']})
        for class_name, parent in NEW_PARENTS.items():
            self.assertEqual(enabled[class_name]['new_type_parent'], parent)
            self.assertEqual(enabled[class_name]['runtime_acceptance'], 'pending')
            self.assertEqual(enabled[class_name]['status'], 'requires-local-acceptance')

    def test_generate_both_paths_install_and_rollback_preserve_exact_bytes(self):
        for combined in (False, True, 'local-session'):
            with self.subTest(combined=combined):
                if combined == 'local-session':
                    # SYNTHETIC mission covers firearms; unrelated non-weapon items are empty.
                    with mock.patch.object(economy.datamined_items, 'load_rows', return_value=[]):
                        files = local_test_session.economy_delta(
                            economy, self.root, ROSTER_PATH.parents[2],
                            {'profile': 'mission/hollow-country/economy-profiles/baseline.json',
                             'roster': 'tools/package/firearms_roster.json'})
                elif combined:
                    files = firearms.generate_combined(self.root, self.roster, include_items=False)
                else:
                    files = firearms.generate(self.root, self.roster)
                output = economy._unique(ET.fromstring(files['ce/types.xml']))
                self.assertTrue(set(NEW_PARENTS) <= set(output))
                self.assertEqual((output['CZ527_Camo'].findtext('nominal'),
                                  output['CZ527_Camo'].findtext('min')), tuple(str(next(e for e in firearms.selected_roster(self.roster)['entries'] if e['class'] == 'CZ527_Camo')['set'][field]) for field in ('nominal', 'min')))
                for class_name, parent in NEW_PARENTS.items():
                    expected = copy.deepcopy(self.stock[parent])
                    expected.set('name', class_name)
                    policy = next(e for e in firearms.selected_roster(self.roster)['entries'] if e['class'] == class_name)
                    expected.find('nominal').text = str(policy['set']['nominal'])
                    for field, value in policy['set'].items():
                        expected.find(field).text = str(value)
                    for tag, field in (('usage', 'set_usage'), ('value', 'set_value')):
                        for node in expected.findall(tag):
                            expected.remove(node)
                        for value in sorted(policy[field]):
                            ET.SubElement(expected, tag, name=value)
                    self.assertEqual(economy._full(output[class_name]), economy._full(expected))
                report = json.loads(files['economy-report.json'])
                report_rows = report.get('entries')
                if report_rows is None:
                    report_rows = report['firearms']['entries']
                for row in report_rows:
                    if row['class'] in NEW_PARENTS:
                        self.assertIsNone(row['stock'])
                        self.assertEqual(row['status'], 'requires-local-acceptance')
                        self.assertEqual(row['runtime_acceptance'], 'pending')
                self.assertEqual(set(json.loads(files['delta-manifest.json'])['new_type_classes']), set(NEW_PARENTS))
                stage = Path(self.tmp.name) / str(combined)
                economy.write_delta(stage, files)
                economy.install_delta(stage, self.root)
                self.assertEqual((self.root / 'db/types.xml').read_bytes(), self.before['db/types.xml'])
                economy.rollback(self.root)
                self.assertEqual(self.before, economy.snapshot(self.root))
                self.assertFalse((self.root / economy.MANAGED).exists())

    def test_missing_reviewed_roster_name_raises_value_error(self):
        custom = copy.deepcopy(self.roster)
        custom['entries'] = [e for e in custom['entries'] if e['class'] != 'CZ527_Camo']
        with self.assertRaisesRegex(ValueError, 'roster'):
            firearms.reviewed_type('CZ527_Camo', self.stock, custom)

    def test_direct_economy_requires_native_carriers(self):
        (self.root / 'cfgspawnabletypes.xml').write_text('<spawnabletypes/>')
        profile = {'schema': 1, 'name': 'synthetic', 'add_usage': {}, 'diagnostics': []}
        with self.assertRaisesRegex(ValueError, 'HC21_PART_ROUTE_MISSING'):
            economy.generate(self.root, profile, include_datamined=False,
                             roster=dict(self.roster, economy_profile='scarcity'))

    def test_switch_disables_new_rows_and_their_install_permissions(self):
        files = firearms.generate(self.root, self.roster, include_datamined=False)
        output = economy._unique(ET.fromstring(files['ce/types.xml']))
        self.assertFalse(set(NEW_PARENTS) & set(output))
        self.assertEqual(json.loads(files['delta-manifest.json'])['new_type_classes'], [])

    def test_existing_case_alias_is_reused_with_parent_fields_without_duplicate(self):
        stock_root = ET.parse(self.root / 'db/types.xml').getroot()
        stock_root.append(ET.fromstring(entry('CZ527_Desert', 0, 0, 14400, 0, [], [])))
        (self.root / 'db/types.xml').write_bytes(ET.tostring(stock_root))
        original = economy.snapshot(self.root)
        files = firearms.generate(self.root, self.roster)
        output = economy._unique(ET.fromstring(files['ce/types.xml']))
        self.assertNotIn('CZ527_desert', output)
        expected = next(e for e in firearms.selected_roster(self.roster)['entries'] if e['class'].lower() == 'cz527_desert')
        self.assertEqual(output['CZ527_Desert'].findtext('nominal'), str(expected['set']['nominal']))
        self.assertEqual(output['CZ527_Desert'].find('tag').get('name'), 'shelves')
        self.assertNotIn('CZ527_Desert', json.loads(files['delta-manifest.json'])['new_type_classes'])
        stage = Path(self.tmp.name) / 'case-alias'
        economy.write_delta(stage, files)
        economy.install_delta(stage, self.root)
        economy.rollback(self.root)
        self.assertEqual(original, economy.snapshot(self.root))

    def test_install_refuses_rehashed_new_type_mutations_before_writing(self):
        mutations = ('unknown class', 'nominal', 'min', 'reduced nominal', 'reduced min', 'flags', 'usage', 'value', 'tag', 'category', 'missing permission',
                     'case duplicate')
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                files = firearms.generate(self.root, self.roster)
                output = ET.fromstring(files['ce/types.xml'])
                candidate = output.find("type[@name='CZ527_Camo']")
                manifest = json.loads(files['delta-manifest.json'])
                if mutation == 'unknown class':
                    candidate.set('name', 'UnreviewedNewWeapon')
                    manifest['new_type_classes'].append('UnreviewedNewWeapon')
                    manifest['firearms_classes'].append('UnreviewedNewWeapon')
                elif mutation == 'missing permission':
                    manifest['new_type_classes'].remove('CZ527_Camo')
                elif mutation == 'case duplicate':
                    # CE class names are case-insensitive: a second spelling of a candidate row is a duplicate.
                    twin = ET.fromstring(ET.tostring(output.find("type[@name='AKM']")))
                    twin.set('name', 'akm')
                    output.append(twin)
                elif mutation in ('nominal', 'min'):
                    candidate.find(mutation).text = '26'
                elif mutation.startswith('reduced '):
                    # Stays below the family cap; exact reviewed shares must still refuse.
                    field = mutation.split()[1]
                    candidate.find(field).text = str(int(candidate.findtext(field)) - 1)
                else:
                    candidate.find(mutation).set('name', 'Invented')
                files['ce/types.xml'] = ET.tostring(output)
                manifest['files']['ce/types.xml'] = economy.sha(files['ce/types.xml'])
                files['delta-manifest.json'] = economy.encode(manifest)
                stage = Path(self.tmp.name) / mutation
                economy.write_delta(stage, files)
                with self.assertRaises(ValueError):
                    economy.install_delta(stage, self.root)
                self.assertEqual(self.before, economy.snapshot(self.root))
                self.assertFalse((self.root / economy.MANAGED).exists())


class CommittedRoster(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(ROSTER_PATH.read_text())

    def test_schema_and_vocabulary(self):
        firearms.validate_roster(self.data)

    def test_counts_are_the_owner_chosen_family_scarcity_scale(self):
        # Historical assertions exercise the retained scarcity selector.
        historical = firearms.selected_roster(dict(self.data, economy_profile='scarcity'))
        weapons = [e for e in historical['entries'] if e['kind'] == 'weapon']
        self.assertGreaterEqual(len(weapons), 30)
        self.assertEqual(max(e['set']['nominal'] for e in weapons), 28)
        for e in weapons:
            cap = next(b['nominal'] for b in historical['family_budgets'] if b['family'] == e['family'])
            self.assertLessEqual(e['set']['nominal'], cap, e['class'])
        total = sum(e['set']['nominal'] for e in weapons)
        self.assertEqual(total, 444)
        self.assertEqual(sum(e['set']['nominal'] for e in weapons if not e.get('datamined')), 394)
        # Unsplit curated classes keep established shares; skins now divide one family ceiling.
        by_class = {e['class']: e['set'] for e in weapons}
        split_families = {'Mosin9130', 'SKS', 'Winchester70', 'CZ527', 'B95', 'Magnum',
                          'Colt1911', 'Makarov'}
        for name, (nominal, minimum) in V1_FIRST_PROPOSAL.items():
            policy = next(e for e in weapons if e['class'] == name)
            if policy['family'] not in split_families:
                self.assertEqual((by_class[name]['nominal'], by_class[name]['min']),
                                 (2 * nominal, 2 * minimum), name)
        caps = {b['family']: b for b in historical['family_budgets'] if b['kind'] == 'weapon'}
        for family, cap in caps.items():
            for field in ('nominal', 'min'):
                self.assertEqual(sum(e['set'][field] for e in weapons if e['family'] == family), cap[field])
        self.assertEqual(by_class['MKII'], {'nominal': 15, 'min': 13})
        split_shares = {
            'Mosin9130': (22, 16), 'Mosin9130_Woodland': (8, 6),
            'Mosin9130_Black': (2, 1), 'Mosin9130_Winter': (2, 1),
            'SKS': (8, 4), 'SKS_Woodland': (6, 4), 'SKS_Black': (1, 1),
            'SKS_Desert': (1, 1), 'SKS_Green': (1, 1), 'SKS_Winter': (1, 1),
            'Winchester70': (6, 4), 'Winchester70_Black': (2, 1), 'Winchester70_Green': (2, 1),
            'CZ527': (10, 8), 'CZ527_Woodland': (8, 6), 'CZ527_Camo': (2, 1),
            'CZ527_Green': (2, 1), 'CZ527_desert': (2, 1), 'CZ527_winter': (2, 1),
            'B95': (6, 4), 'B95_Black': (2, 1), 'B95_Green': (2, 1),
            'Magnum': (9, 7), 'Magnum_Gold': (1, 1),
            'Colt1911': (12, 9), 'Engraved1911': (4, 3),
            'MakarovIJ70': (14, 11), 'MakarovPB': (2, 1)}
        self.assertEqual({e['class'] for e in weapons if e['family'] in split_families}, set(split_shares))
        for name, (nominal, minimum) in split_shares.items():
            self.assertEqual(by_class[name], {'nominal': nominal, 'min': minimum}, name)
        self.assertEqual(sum(n for n, _ in V1_FIRST_PROPOSAL.values()), 164)
        for e in historical['entries']:
            self.assertGreaterEqual(e['set']['nominal'], e['set']['min'])
            self.assertTrue(e['justification'].strip())

    def test_datamined_rows_are_marked_pending_local_and_stay_rare(self):
        # Historical assertions exercise the retained scarcity selector.
        historical = firearms.selected_roster(dict(self.data, economy_profile='scarcity'))
        marked = {e['class']: e for e in historical['entries'] if e.get('datamined')}
        self.assertEqual({c for c, e in marked.items() if e['kind'] == 'weapon'}, DATAMINED_WEAPONS)
        self.assertEqual({c for c, e in marked.items() if e['kind'] == 'magazine'}, DATAMINED_MAGAZINES)
        for name, e in marked.items():
            self.assertEqual(e['acceptance'], 'pending-local', name)
            self.assertTrue(e['justification'].strip(), name)
        for name in DATAMINED_WEAPONS - {'LeeEnfield', 'MP18', 'Luger'} - set(NEW_PARENTS):
            self.assertLessEqual(marked[name]['set']['nominal'], 2, name)
        self.assertEqual({e['class'] for e in historical['entries'] if 'acceptance' in e}, set(marked))

    def test_the_single_switch_removes_exactly_the_datamined_rows_from_a_generated_delta(self):
        names = {e['class'] for e in self.data['entries']}
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / 'mission'
            synthetic(root)
            rows = ''.join(entry(e['class'], 0 if e.get('datamined') else 51,
                                 0 if e.get('datamined') else 39, 14400, 0, ['Town'], [])
                           for e in self.data['entries'] if e['class'] not in NEW_PARENTS)
            (root / 'db/types.xml').write_text('<types>' + rows + '</types>')
            usages = {u for e in self.data['entries'] for u in e.get('set_usage', e.get('add_usage', []))} | {'Town'}
            values = {v for e in self.data['entries'] for v in e.get('set_value', [])} | {'Tier1'}
            (root / 'cfglimitsdefinition.xml').write_text(
                '<lists><usageflags>' + ''.join(f'<usage name="{u}"/>' for u in sorted(usages))
                + '</usageflags><valueflags>' + ''.join(f'<value name="{v}"/>' for v in sorted(values))
                + '</valueflags></lists>')
            on = {x.get('name') for x in ET.fromstring(firearms.generate(root, self.data)['ce/types.xml'])}
            off = {x.get('name') for x in ET.fromstring(
                firearms.generate(root, self.data, include_datamined=False)['ce/types.xml'])}
        self.assertEqual(on - off, DATAMINED_WEAPONS | DATAMINED_MAGAZINES)
        self.assertEqual(off, names - DATAMINED_WEAPONS - DATAMINED_MAGAZINES)

    def test_roles_wood_and_modern_are_both_present_and_nothing_futuristic(self):
        roles = {e['role'] for e in self.data['entries'] if e['kind'] == 'weapon'}
        self.assertEqual(roles, {'wood', 'modern'})
        banned = {'Groza', 'M249', 'DartGun', 'Shockpistol', 'LAW', 'RPG7', 'Flaregun'}
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
        self.assertEqual(deferred, [])
        self.assertFalse({d['class'] for d in deferred} & {e['class'] for e in self.data['entries']})

    def test_optics_placeholder_is_superseded_by_the_optional_pack(self):
        self.assertEqual(self.data['optics'], {'status': 'superseded', 'entries': []})
        for bad in ({'status': 'accepted', 'entries': []},
                    {'status': 'deferred-pending-owner-decision', 'entries': [{'class': 'PSO1Optic'}]}):
            with self.subTest(bad), self.assertRaises(ValueError):
                mutated = copy.deepcopy(self.data)
                mutated['optics'] = bad
                firearms.validate_roster(mutated)

    def test_native_budgets_and_cartridge_ceilings_use_halved_shares(self):
        # Historical assertions exercise the retained scarcity selector.
        historical = firearms.selected_roster(dict(self.data, economy_profile='scarcity'))
        by_class = {e['class']: e for e in historical['entries']}
        for name, (native_nominal, native_min) in NATIVE_BUDGETS.items():
            with self.subTest(name=name):
                self.assertEqual(by_class[name]['set'], {
                    'nominal': max(1, native_nominal // 2),
                    'min': max(1, native_min // 2) if native_min else 0})
        for budget in historical['family_budgets']:
            if budget['kind'] == 'ammo':
                members = [e for e in historical['entries'] if e['family'] == budget['family']]
                for field in ('nominal', 'min'):
                    self.assertEqual(budget[field], sum(e['set'][field] * e['unit_rounds'] for e in members))

    def test_every_magazine_has_a_weapon_reference_and_orphans_are_rejected(self):
        referenced = {m for e in self.data['entries'] if e['kind'] == 'weapon' for m in e['magazines']}
        magazines = {e['class'] for e in self.data['entries'] if e['kind'] == 'magazine'}
        self.assertEqual(magazines - referenced, set())
        custom = roster()
        custom['entries'][1]['magazines'] = []
        with self.assertRaisesRegex(ValueError, 'unreferenced magazine'):
            firearms.validate_roster(custom)

    def test_summary_derives_the_native_class_count(self):
        custom = copy.deepcopy(self.data)
        next(e for e in custom['entries'] if e['class'] == 'AK101')['disposition'] = 'curated-family-split'
        self.assertIn('All 31 are retained explicitly.', firearms.render_family_summary(custom))

    def test_roster_is_small_and_carries_no_vanilla_dump(self):
        self.assertLess(ROSTER_PATH.stat().st_size, 300_000)
        self.assertNotIn('<type ', ROSTER_PATH.read_text())


class MilitaryLootBudget(unittest.TestCase):
    """Offline generation properties, never observed CE population or magazine fill."""

    def test_all_sources_share_each_tier_ceiling_and_keep_support(self):
        from tools.package import military_loot as military
        rules = military.load_rules()
        rows, counts, remaining = military.allocation()
        self.assertTrue(all(n >= 0 for n in remaining.values()))
        for tier in rules['firearms']:
            total = sum(counts[name] for name, row in rows.items() if row['kind'] == 'weapon'
                        and 'Military' in row['usage'] and tier in row['value'])
            self.assertLessEqual(total, sum(rules['firearms'][tier].values()))
        tier4 = sum(counts[name] for name, row in rows.items() if row['kind'] == 'weapon'
                    and 'Military' in row['usage'] and 'Tier4' in row['value'])
        # Shared civilian sidearms keep their original pools outside this ceiling.
        self.assertEqual(tier4, rules['firearms']['Tier4']['primary'])
        effective = {row['class']: row for row in military.apply(list(rows.values()))}
        for row in effective.values():
            for field in ('ammo', 'vanilla_ammo', 'snafu_ammo'):
                row.setdefault(field, [])
        firearms.check_support(list(effective.values()), lambda name: effective.get(name, {}).get('set', {}).get('nominal', 0),
                               ammo_fields=('ammo', 'vanilla_ammo', 'snafu_ammo'))

    def test_projection_is_deterministic_and_preserves_civilian_only_rows(self):
        from tools.package import military_loot as military
        entries = list(military.catalog().values())
        first = military.apply(entries)
        self.assertEqual(first, military.apply(entries))
        for before, after in zip(entries, first):
            if not military.budgeted(before):
                self.assertEqual(before, after)
            elif after['set']['nominal']:
                self.assertGreater(after['set']['min'], 0)

    def test_configuration_change_reallocates_the_shared_pool(self):
        from tools.package import military_loot as military
        rules = military.load_rules()
        rules['firearms']['Tier4'] = {'primary': 12, 'secondary': 12}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rules.json'
            path.write_text(json.dumps(rules))
            with mock.patch.object(military, 'RULES', path):
                rows, counts, _ = military.allocation()
                self.assertEqual(sum(counts[name] for name, row in rows.items() if row['kind'] == 'weapon'
                                     and military.budgeted(row) and 'Tier4' in row['value']), 12)

    def test_every_generated_modded_magazine_uses_partial_fill_range(self):
        from tools.package import military_loot as military, snafu_optional, tactical_flava_optional
        for writer in (snafu_optional, tactical_flava_optional):
            data = json.loads(writer.ALLOWLIST_PATH.read_bytes())
            for row in data['entries']:
                if row['kind'] == 'magazine':
                    node = writer._new_type(row)
                    self.assertEqual((int(node.findtext('quantmin')), int(node.findtext('quantmax'))),
                                     military.magazine_quantity())


if __name__ == '__main__':
    unittest.main()
