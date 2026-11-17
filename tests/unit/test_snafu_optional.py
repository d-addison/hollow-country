"""SNAFU Weapons optional dependency: synthetic install only.

These tests build a tiny synthetic mod layout (synthetic PBOs, class names and types list). They never
read or copy the real Workshop item and never establish DayZ behaviour.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.package import economy, firearms, snafu_optional

try:
    from .test_pbo_config import klass, pbo, rap
    from .test_firearms_roster import roster as vanilla_roster, synthetic as synthetic_mission
except ImportError:
    from test_pbo_config import klass, pbo, rap
    from test_firearms_roster import roster as vanilla_roster, synthetic as synthetic_mission

REPO = Path(__file__).resolve().parents[2]
ALLOWLIST = REPO / 'tools/package/snafu_allowlist.json'
TERMS = b'synthetic terms text'
MODEL = 'Synth\\Guns\\Data\\{}.p3d'


def configs():
    weapons = {
        'Rifle_Base': klass('', scope=0),
        'SynWood': klass('Rifle_Base', scope=2, model=MODEL.format('wood'), chamberableFrom=['SynAmmoA']),
        'SynPistol': klass('Rifle_Base', scope=2, model=MODEL.format('pistol'),
                           magazines=['SynPistolMag'], chamberableFrom=['Ammo_45ACP']),
        'SynEmptyMag': klass('Rifle_Base', scope=2, model=MODEL.format('wood'), magazines=[''],
                             chamberableFrom=['SynAmmoA']),
        'SynHidden': klass('Rifle_Base', scope=0, model=MODEL.format('wood')),
        'SynNoModel': klass('Rifle_Base', scope=2, model=MODEL.format('gone'), chamberableFrom=['SynAmmoA']),
        'SynNoTypes': klass('Rifle_Base', scope=2, model=MODEL.format('wood'), chamberableFrom=['SynAmmoA']),
        'SynBadMag': klass('Rifle_Base', scope=2, model=MODEL.format('wood'), magazines=['AbsentMag'],
                           chamberableFrom=['SynAmmoA']),
        'SynWrongAmmo': klass('Rifle_Base', scope=2, model=MODEL.format('wood'), chamberableFrom=['SynAmmoB']),
        'SynBaseModel': klass('SynWood'),
    }
    mags = {'SynPistolMag': klass('', scope=2, ammo='Bullet_45ACP', count=7),
            'SynAmmoA': klass('', scope=2, ammo='SynBulletA', count=20),
            'SynAmmoB': klass('', scope=2, ammo='SynBulletMissing', count=20)}
    return klass('', CfgWeapons=klass('', **weapons), CfgMagazines=klass('', **mags),
                 CfgAmmo=klass('', SynBulletA=klass('', scope=1)))


def build_install(root, publishedid=2443122116, vendor=None, terms=TERMS, extra_addons=None):
    root.mkdir(parents=True)
    (root / 'meta.cpp').write_text(f'protocol = 1;\npublishedid = {publishedid};\nname = "SNAFU Weapons";\n')
    (root / 'Addons').mkdir()
    members = {'Data/wood.p3d': b'x', 'Data/pistol.p3d': b'x', 'config.bin': rap(configs())}
    (root / 'Addons/Synth_Guns.pbo').write_bytes(pbo(members, prefix='Synth\\Guns'))
    for name, data in (extra_addons or {}).items():
        (root / 'Addons' / name).write_bytes(data)
    (root / 'XML_and_Clasnames').mkdir()
    names = vendor if vendor is not None else ['SynWood', 'SynPistol', 'SynEmptyMag', 'SynHidden', 'SynNoModel',
                                                'SynBadMag', 'SynWrongAmmo', 'SynBaseModel', 'SynPistolMag', 'SynAmmoA']
    (root / 'XML_and_Clasnames/SNAFU_types.xml').write_text(
        '<types>' + ''.join(f'<type name="{n}"><nominal>1</nominal></type>' for n in names) + '</types>')
    if terms is not None:
        (root / 'Readme_Terms').mkdir()
        (root / 'Readme_Terms/Mod_Terms_Of _Use_DPL_ND.pdf').write_bytes(terms)


def entry(cls, kind='weapon', role='wood', nominal=2, minimum=1, **extra):
    row = {'class': cls, 'kind': kind, 'role': role, 'tier': 'rare',
           'set': {'nominal': nominal, 'min': minimum, 'lifetime': 14400, 'restock': 0},
           'usage': ['Town'], 'value': ['Tier3'], 'justification': 'synthetic'}
    if kind == 'weapon':
        row.update({'vanilla_ammo': [], 'snafu_ammo': [], 'magazines': []})
    row.update(extra)
    return row


def allowlist(*rows):
    return {'schema': 1, 'name': 'synthetic-snafu', 'workshop_id': '2443122116', 'status': 'unverified',
            'rights': {'license': 'DPL-ND', 'terms_file': 'Readme_Terms/Mod_Terms_Of _Use_DPL_ND.pdf',
                       'terms_sha256': hashlib.sha256(TERMS).hexdigest(),
                       'urls': ['https://example.invalid/terms'], 'redistribution': 'none'},
            'entries': list(rows), 'excluded': [{'group': 'synthetic-futuristic', 'reason': 'tone'}]}


GOOD = (entry('SynWood', snafu_ammo=['SynAmmoA']),
        entry('SynPistol', role='modern', vanilla_ammo=['Ammo_45ACP'], magazines=['SynPistolMag']),
        entry('SynEmptyMag', snafu_ammo=['SynAmmoA']),
        entry('SynPistolMag', kind='magazine', role='support'),
        entry('SynAmmoA', kind='ammo', role='support', nominal=10, minimum=6))


class Verifier(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.install = Path(self.tmp.name) / 'mod'
        build_install(self.install)

    def tearDown(self):
        self.tmp.cleanup()

    def snapshot(self):
        return {p.relative_to(self.install).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.install.rglob('*') if p.is_file()}

    def test_good_entries_verify_and_empty_magazine_is_a_note_not_a_failure(self):
        report = snafu_optional.verify_install(self.install, allowlist(*GOOD))
        self.assertEqual(report['status'], 'verified')
        for row in report['classes'].values():
            self.assertEqual(row['status'], 'verified', row)
        self.assertIn('empty-magazine-entry-ignored', report['classes']['SynEmptyMag']['notes'])
        self.assertEqual(report['install']['publishedid'], '2443122116')
        self.assertTrue(report['terms']['matches_reviewed'])
        self.assertEqual(report['counts'], {'verified': 5, 'missing': 0, 'unverified': 0})

    def test_each_failure_mode_is_missing_or_unverified_with_a_reason(self):
        rows = [entry('SynGhost'), entry('SynHidden'), entry('SynNoModel', snafu_ammo=['SynAmmoA']),
                entry('SynNoTypes', snafu_ammo=['SynAmmoA']), entry('SynBadMag', magazines=['AbsentMag'],
                                                                    snafu_ammo=['SynAmmoA']),
                entry('SynWrongAmmo', snafu_ammo=['SynAmmoB']),
                entry('SynWood', vanilla_ammo=['Ammo_Wrong']),
                entry('SynAmmoA', kind='ammo', role='support'),
                entry('SynAmmoB', kind='ammo', role='support'), entry('AbsentMag', kind='magazine', role='support')]
        # SynNoTypes is absent from the vendor list; SynAmmoB has a bullet class that is not defined.
        shutil.rmtree(self.install)
        names = ['SynWood', 'SynPistol', 'SynHidden', 'SynNoModel', 'SynBadMag', 'SynWrongAmmo', 'SynAmmoA',
                 'SynAmmoB']
        build_install(self.install, vendor=names)
        report = snafu_optional.verify_install(self.install, allowlist(*rows))
        expected = {'SynGhost': 'missing', 'SynHidden': 'unverified', 'SynNoModel': 'unverified',
                    'SynNoTypes': 'unverified', 'SynBadMag': 'unverified', 'SynWrongAmmo': 'unverified',
                    'SynWood': 'unverified', 'SynAmmoA': 'verified', 'SynAmmoB': 'unverified',
                    'AbsentMag': 'missing'}
        self.assertEqual({k: v['status'] for k, v in report['classes'].items()}, expected)
        self.assertEqual(report['status'], 'unverified')
        for name, row in report['classes'].items():
            if row['status'] != 'verified':
                self.assertTrue(row['reasons'], name)

    def test_verification_is_read_only(self):
        before = self.snapshot()
        snafu_optional.verify_install(self.install, allowlist(*GOOD))
        self.assertEqual(before, self.snapshot())

    def test_install_identity_and_layout_are_checked(self):
        for label, kwargs in {'wrong id': {'publishedid': 1}}.items():
            with tempfile.TemporaryDirectory() as t, self.subTest(label):
                other = Path(t) / 'mod'
                build_install(other, **kwargs)
                report = snafu_optional.verify_install(other, allowlist(*GOOD))
                self.assertEqual(report['status'], 'unverified')
                self.assertIn('publishedid-mismatch', report['install']['problems'])
        with tempfile.TemporaryDirectory() as t:
            empty = Path(t) / 'mod'
            empty.mkdir()
            report = snafu_optional.verify_install(empty, allowlist(*GOOD))
            self.assertEqual(report['status'], 'unverified')
            self.assertIn('no-addon-pbos', report['install']['problems'])
        with self.assertRaises(ValueError):
            snafu_optional.verify_install(Path(self.tmp.name) / 'nope', allowlist(*GOOD))

    def test_changed_terms_file_fails_closed(self):
        shutil.rmtree(self.install)
        build_install(self.install, terms=b'amended terms')
        report = snafu_optional.verify_install(self.install, allowlist(*GOOD))
        self.assertEqual(report['status'], 'unverified')
        self.assertFalse(report['terms']['matches_reviewed'])
        shutil.rmtree(self.install)
        build_install(self.install, terms=None)
        report = snafu_optional.verify_install(self.install, allowlist(*GOOD))
        self.assertEqual(report['status'], 'unverified')
        self.assertFalse(report['terms']['present'])

    def test_symlinked_install_and_pbo_budget_are_refused(self):
        link = Path(self.tmp.name) / 'link'
        os.symlink(self.install, link)
        with self.assertRaises(ValueError):
            snafu_optional.verify_install(link, allowlist(*GOOD))
        with self.assertRaises(ValueError):
            snafu_optional.verify_install(self.install, allowlist(*GOOD), max_pbos=0)

    def test_corrupt_pbo_is_reported_not_trusted(self):
        (self.install / 'Addons/Broken.pbo').write_bytes(b'not a pbo at all')
        report = snafu_optional.verify_install(self.install, allowlist(*GOOD))
        self.assertEqual(report['status'], 'unverified')
        self.assertIn('Broken.pbo', ' '.join(report['install']['problems']))

    def test_class_defined_in_two_pbos_is_not_trusted(self):
        shadow = rap(klass('', CfgWeapons=klass('', SynWood=klass('', scope=0))))
        (self.install / 'Addons/Zzz_Shadow.pbo').write_bytes(pbo({'config.bin': shadow}, prefix='Shadow'))
        report = snafu_optional.verify_install(self.install, allowlist(*GOOD))
        self.assertEqual(report['classes']['SynWood']['status'], 'unverified')
        self.assertIn('multiple-definitions', report['classes']['SynWood']['reasons'])
        self.assertEqual(report['status'], 'unverified')


class AllowlistValidation(unittest.TestCase):
    def test_valid_and_invalid_shapes(self):
        snafu_optional.validate_allowlist(allowlist(*GOOD))
        base = allowlist(*GOOD)
        cases = {
            'verified status in file': lambda a: a.update({'status': 'verified'}),
            'wrong workshop id': lambda a: a.update({'workshop_id': '1'}),
            'extra top': lambda a: a.update({'multiplier': 2}),
            'no rights': lambda a: a.pop('rights'),
            'rights license': lambda a: a['rights'].update({'license': 'MIT'}),
            'redistribution': lambda a: a['rights'].update({'redistribution': 'bundled'}),
            'no urls': lambda a: a['rights'].update({'urls': []}),
            'http url': lambda a: a['rights'].update({'urls': ['http://x']}),
            'bad hash': lambda a: a['rights'].update({'terms_sha256': 'abc'}),
            'duplicate': lambda a: a['entries'].append(copy.deepcopy(a['entries'][0])),
            'bad usage type': lambda a: a['entries'][0].update({'usage': 'Town'}),
            'empty usage': lambda a: a['entries'][0].update({'usage': []}),
            'min above nominal': lambda a: a['entries'][0].update({'set': {'nominal': 1, 'min': 2}}),
            'bool nominal': lambda a: a['entries'][0].update({'set': {'nominal': True, 'min': 0}}),
            'no justification': lambda a: a['entries'][0].pop('justification'),
            'ammo not listed': lambda a: a['entries'][0].update({'snafu_ammo': ['NotListed']}),
            'magazine not listed': lambda a: a['entries'][1].update({'magazines': ['NotListed']}),
            'weapon missing lists': lambda a: a['entries'][0].pop('snafu_ammo'),
            'no excluded reasons': lambda a: a['excluded'][0].pop('reason'),
            'bad role': lambda a: a['entries'][0].update({'role': 'futuristic'}),
            'bad class chars': lambda a: a['entries'][0].update({'class': 'Bad Name'}),
        }
        for label, fn in cases.items():
            with self.subTest(label), self.assertRaises(ValueError):
                bad = copy.deepcopy(base)
                fn(bad)
                snafu_optional.validate_allowlist(bad)


class FailClosedGeneration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.install = t / 'mod'
        build_install(self.install)
        self.mission = t / 'mission'
        self.mission.mkdir()
        synthetic_mission(self.mission)
        self.allow = allowlist(*GOOD)
        self.report = snafu_optional.verify_install(self.install, self.allow)

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_report_or_unverified_report_generates_nothing(self):
        for report in (None, {}, dict(self.report, status='unverified')):
            with self.subTest(status=(report or {}).get('status')), self.assertRaises(ValueError):
                snafu_optional.generate(self.mission, self.allow, report)

    def test_report_must_match_the_allowlist_and_every_class(self):
        changed = copy.deepcopy(self.allow)
        changed['entries'][0]['set']['nominal'] = 9
        with self.assertRaises(ValueError):
            snafu_optional.generate(self.mission, changed, self.report)
        forged = copy.deepcopy(self.report)
        forged['classes']['SynWood']['status'] = 'unverified'
        with self.assertRaises(ValueError):
            snafu_optional.generate(self.mission, self.allow, forged)
        dropped = copy.deepcopy(self.report)
        del dropped['classes']['SynAmmoA']
        with self.assertRaises(ValueError):
            snafu_optional.generate(self.mission, self.allow, dropped)

    def test_committed_allowlist_with_no_report_yields_no_spawns(self):
        data = json.loads(ALLOWLIST.read_text())
        self.assertEqual(data['status'], 'unverified')
        with self.assertRaises(ValueError):
            snafu_optional.generate(self.mission, data, None)

    def test_verified_report_generates_complete_new_type_entries(self):
        delta = snafu_optional.generate(self.mission, self.allow, self.report)
        types = {t.get('name'): t for t in ET.fromstring(delta['ce/types.xml'])}
        self.assertEqual(sorted(types), sorted(e['class'] for e in GOOD))
        wood = types['SynWood']
        self.assertEqual(wood.findtext('nominal'), '2')
        self.assertEqual(wood.findtext('lifetime'), '14400')
        self.assertEqual([u.get('name') for u in wood.findall('usage')], ['Town'])
        self.assertEqual(wood.find('category').get('name'), 'weapons')
        self.assertEqual(wood.find('flags').get('count_in_map'), '1')
        self.assertIn(b'folder="hollow-country-snafu/ce"', delta['cfgeconomycore.append.xml'])
        meta = json.loads(delta['economy-report.json'])
        self.assertEqual(meta['kind'], 'snafu-optional')
        self.assertEqual(meta['runtime_acceptance'], 'pending')
        self.assertEqual(meta['verification']['status'], 'verified')
        self.assertEqual(delta, snafu_optional.generate(self.mission, self.allow, self.report))

    def test_refuses_classes_already_in_stock_and_unknown_usage(self):
        clash = allowlist(*GOOD, entry('Unrelated'))
        report = dict(self.report, classes=dict(self.report['classes'], Unrelated={'status': 'verified'}),
                      allowlist_sha256=snafu_optional.allowlist_sha256(clash))
        with self.assertRaises(ValueError):
            snafu_optional.generate(self.mission, clash, report)
        odd = copy.deepcopy(self.allow)
        odd['entries'][0]['usage'] = ['Invented']
        report = dict(self.report, allowlist_sha256=snafu_optional.allowlist_sha256(odd))
        with self.assertRaises(ValueError):
            snafu_optional.generate(self.mission, odd, report)


class InstallRollback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.install = t / 'mod'
        build_install(self.install)
        self.source = t / 'source'
        self.source.mkdir()
        synthetic_mission(self.source)
        self.allow = allowlist(*GOOD)
        self.report = snafu_optional.verify_install(self.install, self.allow)

    def tearDown(self):
        self.tmp.cleanup()

    def files(self, target):
        return {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob('*') if p.is_file()}

    def test_install_and_rollback_are_byte_exact(self):
        stage = Path(self.tmp.name) / 'delta'
        snafu_optional.write_delta(stage, snafu_optional.generate(self.source, self.allow, self.report))
        target = Path(self.tmp.name) / 'copy'
        shutil.copytree(self.source, target)
        before = self.files(target)
        snafu_optional.install(stage, target)
        core = (target / 'cfgeconomycore.xml').read_bytes()
        self.assertIn(b'<!--keep exactly-->', core)
        self.assertIn(b'hollow-country-snafu/ce', core)
        self.assertTrue((target / 'hollow-country-snafu/verification.json').is_file())
        self.assertEqual((target / 'db/types.xml').read_bytes(), before['db/types.xml'])
        with self.assertRaises(ValueError):
            snafu_optional.install(stage, target)
        snafu_optional.rollback(target)
        self.assertEqual(before, self.files(target))

    def test_coexists_with_the_roster_and_requires_last_in_first_out_rollback(self):
        target = Path(self.tmp.name) / 'copy'
        shutil.copytree(self.source, target)
        before = self.files(target)
        roster_stage = Path(self.tmp.name) / 'roster'
        firearms.write_delta(roster_stage, firearms.generate(target, vanilla_roster()))
        firearms.install(roster_stage, target)
        stage = Path(self.tmp.name) / 'snafu'
        snafu_optional.write_delta(stage, snafu_optional.generate(target, self.allow, self.report))
        snafu_optional.install(stage, target)
        core = (target / 'cfgeconomycore.xml').read_bytes()
        self.assertIn(b'hollow-country/ce', core)
        self.assertIn(b'hollow-country-snafu/ce', core)
        with self.assertRaises(ValueError):
            firearms.rollback(target)
        snafu_optional.rollback(target)
        firearms.rollback(target)
        self.assertEqual(before, self.files(target))

    def test_refuses_steam_path_tamper_stock_drift_and_symlinks(self):
        stage = Path(self.tmp.name) / 'delta'
        snafu_optional.write_delta(stage, snafu_optional.generate(self.source, self.allow, self.report))
        with self.assertRaises(ValueError):
            snafu_optional.install(stage, Path('/mnt/g/SteamLibrary/steamapps/common/DayZServer/mpmissions/x'))
        target = Path(self.tmp.name) / 'copy'
        shutil.copytree(self.source, target)
        (target / 'db/types.xml').write_text('<types/>')
        with self.assertRaises(ValueError):
            snafu_optional.install(stage, target)
        (stage / 'ce/types.xml').write_text('<types/>')
        with self.assertRaises(ValueError):
            snafu_optional.install(stage, self.source)
        link = Path(self.tmp.name) / 'linked'
        os.symlink(self.source, link)
        with self.assertRaises(ValueError):
            snafu_optional.install(stage, link)

    def test_install_refuses_a_delta_that_redefines_stock_types(self):
        stage = Path(self.tmp.name) / 'delta'
        files = snafu_optional.generate(self.source, self.allow, self.report)
        data = files['ce/types.xml'].replace(b'name="SynWood"', b'name="Unrelated"')
        files['ce/types.xml'] = data
        manifest = json.loads(files['delta-manifest.json'])
        manifest['files']['ce/types.xml'] = economy.sha(data)
        files['delta-manifest.json'] = economy.encode(manifest)
        snafu_optional.write_delta(stage, files)
        target = Path(self.tmp.name) / 'copy'
        shutil.copytree(self.source, target)
        with self.assertRaises(ValueError):
            snafu_optional.install(stage, target)
        self.assertFalse((target / 'hollow-country-snafu').exists())


class CommittedAllowlist(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(ALLOWLIST.read_text())

    def test_valid_and_declared_unverified(self):
        snafu_optional.validate_allowlist(self.data)
        self.assertEqual(self.data['status'], 'unverified')

    def test_rights_inventory_is_recorded(self):
        rights = self.data['rights']
        self.assertEqual(rights['license'], 'DPL-ND')
        self.assertEqual(rights['redistribution'], 'none')
        self.assertTrue(rights['urls'])
        self.assertTrue(all(u.startswith('https://') for u in rights['urls']))
        self.assertRegex(rights['terms_sha256'], r'^[0-9a-f]{64}$')

    def test_subset_is_small_wood_or_conventional_and_not_ww2_or_exotic(self):
        weapons = [e for e in self.data['entries'] if e['kind'] == 'weapon']
        self.assertTrue(4 <= len(weapons) <= 12)
        for e in weapons:
            self.assertLessEqual(e['set']['nominal'], 4, e['class'])
            self.assertNotIn('WW2', e['class'])
        self.assertTrue(self.data['excluded'])
        banned = ('AA12', 'AX50', 'M82', 'M200', 'AS50', 'M249', 'Bren', 'M1918', 'MDAR', 'VECTOR', 'Vikhr', 'P90',
                  'Magnum500', 'Alligator', 'KH9', 'PPSh')
        for e in self.data['entries']:
            self.assertFalse(any(b.lower() in e['class'].lower() for b in banned), e['class'])

    def test_no_overlap_with_the_vanilla_roster(self):
        roster = json.loads((REPO / 'tools/package/firearms_roster.json').read_text())
        self.assertFalse({e['class'] for e in self.data['entries']} & {e['class'] for e in roster['entries']})


class BaseAddonStaysIndependent(unittest.TestCase):
    def test_base_addon_and_default_mission_never_mention_snafu(self):
        hits = []
        for folder in ('mods', 'mission', 'config'):
            for path in (REPO / folder).rglob('*'):
                if path.is_file() and path.suffix.lower() in {'.cpp', '.c', '.hpp', '.xml', '.json', '.md', '.txt'} \
                        and path.stat().st_size < 4_000_000:
                    if b'snafu' in path.read_bytes().lower():
                        hits.append(path.relative_to(REPO).as_posix())
        self.assertEqual(hits, [])

    def test_core_tooling_does_not_import_the_optional_module(self):
        for name in ('economy.py', 'firearms.py', 'pbo.py'):
            path = REPO / 'tools/package' / name
            if path.exists():
                self.assertNotIn('snafu', path.read_text().lower(), name)

    def test_no_snafu_or_workshop_assets_are_in_the_repo(self):
        bad = []
        for folder in ('tools', 'docs', 'mods', 'mission', 'tests', 'config'):
            for path in (REPO / folder).rglob('*'):
                name = path.name.lower()
                if path.is_file() and (any(name.endswith(s) for s in ('.p3d', '.paa', '.rvmat', '.bisign', '.pbo'))
                                       or ('snafu' in name and name.endswith(('.xml', '.rar', '.pdf', '.bikey')))):
                    bad.append(path.relative_to(REPO).as_posix())
        self.assertEqual(bad, [])


if __name__ == '__main__':
    unittest.main()
