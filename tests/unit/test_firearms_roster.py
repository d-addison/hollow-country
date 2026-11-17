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

ROSTER_PATH = Path(__file__).resolve().parents[2] / 'tools/package/firearms_roster.json'
DATAMINED_WEAPONS = {'LeeEnfield', 'MP18', 'Luger', 'SKS_Black', 'SKS_Desert', 'SKS_Green', 'SKS_Winter',
                     'Mosin9130_Black', 'Mosin9130_Winter', 'SVD_Wooden'}
DATAMINED_MAGAZINES = {'Mag_LeeEnfield_10Rnd', 'Mag_MP18_Drum32Rnd', 'Mag_Luger_8Rnd'}
# The first v1 proposal (nominal, min) per original weapon, before the owner's 2x decision.
V1_FIRST_PROPOSAL = {
    'Mosin9130': (12, 9), 'Mosin9130_Woodland': (5, 3), 'SKS': (6, 4), 'SKS_Woodland': (3, 2),
    'Izh18': (14, 11), 'Izh18Shotgun': (10, 8), 'Izh43Shotgun': (8, 6), 'Repeater': (8, 6),
    'Winchester70': (5, 4), 'CZ527': (8, 6), 'CZ527_Woodland': (5, 4), 'B95': (5, 4),
    'LeeEnfield': (6, 4), 'MP18': (2, 1), 'Luger': (3, 2), 'Mp133Shotgun': (4, 3), 'Magnum': (5, 4),
    'AKM': (2, 1), 'Colt1911': (8, 6), 'MakarovIJ70': (8, 6), 'P1': (6, 5), 'Glock19': (6, 5),
    'FNX45': (3, 2), 'CZ75': (4, 3), 'Ruger1022': (6, 4), 'M16A2': (2, 1), 'AK74': (3, 2),
    'MP5K': (3, 2), 'Saiga': (2, 1), 'SVD': (2, 1)}


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
            with self.subTest(support=name), self.assertRaisesRegex(ValueError, 'spawning weapon'):
                firearms.generate(self.root, r)

    def test_one_live_alternative_is_sufficient_and_disabled_weapons_need_no_support(self):
        """SYNTHETIC compatible alternatives and disabled-only roster."""
        r = roster()
        modern = next(e for e in r['entries'] if e['class'] == 'SynthModernRifle')
        modern['magazines'].append('SynthZeroMag')
        support = next(e for e in r['entries'] if e['class'] == 'SynthZeroMag')
        support.pop('datamined')
        support.pop('acceptance')
        next(e for e in r['entries'] if e['class'] == 'SynthMag')['set'] = {'nominal': 0, 'min': 0}
        firearms.generate(self.root, r)
        for e in r['entries']:
            e['set'] = {'nominal': 0, 'min': 0}
        firearms.generate(self.root, r)

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
        with self.assertRaisesRegex(ValueError, 'spawning weapon'):
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


class CommittedRoster(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(ROSTER_PATH.read_text())

    def test_schema_and_vocabulary(self):
        firearms.validate_roster(self.data)

    def test_counts_are_the_owner_chosen_double_generous_scale(self):
        weapons = [e for e in self.data['entries'] if e['kind'] == 'weapon']
        self.assertGreaterEqual(len(weapons), 30)
        for e in weapons:
            self.assertLessEqual(e['set']['nominal'], 28, e['class'])
        total = sum(e['set']['nominal'] for e in weapons)
        self.assertTrue(328 <= total <= 360, total)
        # Owner decision 2026-11-17: 2x the first proposal (164 -> 328) with min/nominal ratios kept.
        by_class = {e['class']: e['set'] for e in weapons}
        for name, (nominal, minimum) in V1_FIRST_PROPOSAL.items():
            self.assertEqual((by_class[name]['nominal'], by_class[name]['min']), (2 * nominal, 2 * minimum), name)
        self.assertEqual(sum(n for n, _ in V1_FIRST_PROPOSAL.values()), 164)
        for e in self.data['entries']:
            self.assertGreaterEqual(e['set']['nominal'], e['set']['min'])
            self.assertTrue(e['justification'].strip())

    def test_datamined_rows_are_marked_pending_local_and_stay_rare(self):
        marked = {e['class']: e for e in self.data['entries'] if e.get('datamined')}
        self.assertEqual({c for c, e in marked.items() if e['kind'] == 'weapon'}, DATAMINED_WEAPONS)
        self.assertEqual({c for c, e in marked.items() if e['kind'] == 'magazine'}, DATAMINED_MAGAZINES)
        for name, e in marked.items():
            self.assertEqual(e['acceptance'], 'pending-local', name)
            self.assertTrue(e['justification'].strip(), name)
        for name in DATAMINED_WEAPONS - {'LeeEnfield', 'MP18', 'Luger'}:
            self.assertLessEqual(marked[name]['set']['nominal'], 2, name)
        self.assertEqual({e['class'] for e in self.data['entries'] if 'acceptance' in e}, set(marked))

    def test_the_single_switch_removes_exactly_the_datamined_rows_from_a_generated_delta(self):
        names = {e['class'] for e in self.data['entries']}
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / 'mission'
            synthetic(root)
            rows = ''.join(entry(n, 0, 0, 14400, 0, ['Town'], []) for n in sorted(names))
            (root / 'db/types.xml').write_text('<types>' + rows + '</types>')
            usages = {u for e in self.data['entries'] for u in e.get('add_usage', [])} | {'Town'}
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

    def test_optics_are_a_documented_empty_extension_point(self):
        self.assertEqual(self.data['optics'], {'status': 'deferred-pending-owner-decision', 'entries': []})
        for bad in ({'status': 'accepted', 'entries': []},
                    {'status': 'deferred-pending-owner-decision', 'entries': [{'class': 'PSO1Optic'}]}):
            with self.subTest(bad), self.assertRaises(ValueError):
                mutated = copy.deepcopy(self.data)
                mutated['optics'] = bad
                firearms.validate_roster(mutated)

    def test_roster_is_small_and_carries_no_vanilla_dump(self):
        self.assertLess(ROSTER_PATH.stat().st_size, 60_000)
        self.assertNotIn('<type ', ROSTER_PATH.read_text())


if __name__ == '__main__':
    unittest.main()
