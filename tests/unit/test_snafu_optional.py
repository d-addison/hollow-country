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
from unittest import mock
import xml.etree.ElementTree as ET

from tools.package import economy, firearms, snafu_optional

try:
    from .test_pbo_config import klass, pbo, rap
    from .test_firearms_roster import roster as vanilla_roster, synthetic as synthetic_mission, patch_roster
except ImportError:
    from test_pbo_config import klass, pbo, rap
    from test_firearms_roster import roster as vanilla_roster, synthetic as synthetic_mission, patch_roster

REPO = Path(__file__).resolve().parents[2]
ALLOWLIST = REPO / 'tools/package/snafu_allowlist.json'
TERMS = b'synthetic terms text'
MODEL = 'Synth\\Guns\\Data\\{}.p3d'


class Killed(BaseException):
    """A process kill: unlike OSError it is not handled by install's in-process cleanup."""


def killing_write(real, fail_name, partial=0):
    """fresh_write wrapper that is killed at fail_name (after writing `partial` bytes if asked)."""
    def write(root, name, data):
        if name == fail_name:
            if partial:
                real(root, name, data[:partial])
            raise Killed(fail_name)
        return real(root, name, data)
    return write


def killing_replace(real, staged_name):
    """os.replace wrapper that is killed when it would rename staged_name."""
    def replace(src, dst, *args, **kwargs):
        if Path(src).name == staged_name:
            raise Killed(staged_name)
        return real(src, dst, *args, **kwargs)
    return replace


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
        entry('SynPistol', role='modern', usage=['Military'], vanilla_ammo=['Ammo_45ACP'], magazines=['SynPistolMag']),
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
    def test_modern_picks_require_exact_military_usage_and_high_tiers(self):
        """SYNTHETIC policy mutations of the committed HK416_Gun pick."""
        base = json.loads(ALLOWLIST.read_text())
        for patch in ({'usage': ['Town']}, {'usage': ['Military', 'Town']},
                      {'value': ['Tier2']}, {'value': []}, {'value': ['Tier3', 'Tier1']}):
            a = copy.deepcopy(base)
            next(e for e in a['entries'] if e['class'] == 'HK416_Gun').update(patch)
            with self.subTest(patch=patch), self.assertRaisesRegex(ValueError, 'modern pick'):
                snafu_optional.validate_allowlist(a)
        for tiers in (['Tier3'], ['Tier4'], ['Tier3', 'Tier4']):
            a = copy.deepcopy(base)
            next(e for e in a['entries'] if e['class'] == 'HK416_Gun')['value'] = tiers
            snafu_optional.validate_allowlist(a)

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

    def test_spawning_weapons_need_effective_nonzero_support(self):
        """SYNTHETIC allowlist and stock budgets, independent of static config verification."""
        for name in ('SynAmmoA', 'SynPistolMag', 'vanilla'):
            a = copy.deepcopy(self.allow)
            if name == 'vanilla':
                # No Ammo_45ACP in this SYNTHETIC stock fixture.
                a['entries'][1]['vanilla_ammo'] = ['MissingSyntheticAmmo']
            else:
                next(e for e in a['entries'] if e['class'] == name)['set'].update(nominal=0, min=0)
            report = dict(self.report, allowlist_sha256=snafu_optional.allowlist_sha256(a))
            with self.subTest(support=name), self.assertRaisesRegex(ValueError, 'spawning weapon'):
                snafu_optional.generate(self.mission, a, report)

    def test_no_report_or_unverified_report_generates_nothing(self):
        for report in (None, {}, dict(self.report, status='unverified')):
            with self.subTest(status=(report or {}).get('status')), self.assertRaises(ValueError):
                snafu_optional.generate(self.mission, self.allow, report)

    def test_native_magazine_requirement_cannot_be_hidden_by_an_empty_policy_list(self):
        """SYNTHETIC verified config still requires SynPistolMag when the pick omits it."""
        a = copy.deepcopy(self.allow)
        next(e for e in a['entries'] if e['class'] == 'SynPistol')['magazines'] = []
        next(e for e in a['entries'] if e['class'] == 'SynPistolMag')['set'].update(nominal=0, min=0)
        report = snafu_optional.verify_install(self.install, a)
        with self.assertRaisesRegex(ValueError, 'spawning weapon.*magazine'):
            snafu_optional.generate(self.mission, a, report)

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
        patch_roster(self, self.tmp.name)
        self.source = t / 'source'
        self.source.mkdir()
        synthetic_mission(self.source)
        self.allow = allowlist(*GOOD)
        self.report = snafu_optional.verify_install(self.install, self.allow)

    def tearDown(self):
        self.tmp.cleanup()

    def files(self, target):
        return {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob('*') if p.is_file()}

    def test_install_rechecks_effective_support_after_rehashed_stage_tampering(self):
        """SYNTHETIC rehashed stage still cannot disable required support."""
        files = snafu_optional.generate(self.source, self.allow, self.report)
        root = ET.fromstring(files['ce/types.xml'])
        support = root.find("type[@name='SynAmmoA']")
        support.find('nominal').text = support.find('min').text = '0'
        files['ce/types.xml'] = ET.tostring(root)
        manifest = json.loads(files['delta-manifest.json'])
        manifest['files']['ce/types.xml'] = economy.sha(files['ce/types.xml'])
        files['delta-manifest.json'] = economy.encode(manifest)
        stage = Path(self.tmp.name) / 'tampered-support'
        snafu_optional.write_delta(stage, files)
        before = economy.snapshot(self.source)
        with self.assertRaisesRegex(ValueError, 'spawning weapon'):
            snafu_optional.install(stage, self.source)
        self.assertEqual(before, economy.snapshot(self.source))
        self.assertFalse((self.source / snafu_optional.MANAGED).exists())

    def test_failed_types_write_cleans_up_and_allows_byte_exact_retry(self):
        """SYNTHETIC disk failure, including a partially created managed file."""
        stage = Path(self.tmp.name) / 'failed-delta'
        snafu_optional.write_delta(stage, snafu_optional.generate(self.source, self.allow, self.report))
        before = {p.relative_to(self.source): p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        write = economy.fresh_write
        for partial in (False, True):
            def fail(root, name, data):
                if name == 'ce/types.xml':
                    if partial:
                        write(root, name, b'<types>')
                    raise OSError('SYNTHETIC disk full')
                return write(root, name, data)
            with self.subTest(partial=partial):
                with mock.patch.object(economy, 'fresh_write', side_effect=fail):
                    with self.assertRaisesRegex(OSError, 'SYNTHETIC disk full'):
                        snafu_optional.install(stage, self.source)
                self.assertFalse((self.source / snafu_optional.MANAGED).exists())
                snafu_optional.install(stage, self.source)
                snafu_optional.rollback(self.source)
                self.assertEqual(before, {p.relative_to(self.source): p.read_bytes()
                                          for p in self.source.rglob('*') if p.is_file()})

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

    def staged_copy(self):
        stage = Path(self.tmp.name) / 'delta'
        snafu_optional.write_delta(stage, snafu_optional.generate(self.source, self.allow, self.report))
        target = Path(self.tmp.name) / 'copy'
        shutil.copytree(self.source, target)
        return stage, target, self.files(target)

    def kill_install(self, stage, target, name, partial=0):
        with mock.patch.object(economy, 'fresh_write', killing_write(economy.fresh_write, name, partial)):
            with self.assertRaises(Killed):
                snafu_optional.install(stage, target)
        self.assertTrue((target / snafu_optional.MANAGED).is_dir())

    def test_kill_before_receipt_is_recovered_and_a_changed_core_is_refused(self):
        stage, target, before = self.staged_copy()
        self.kill_install(stage, target, 'receipt.json')
        self.assertFalse((target / snafu_optional.MANAGED / 'receipt.json').exists())
        (target / 'cfgeconomycore.xml').write_bytes(before['cfgeconomycore.xml'] + b'<!--operator edit-->')
        edited = self.files(target)
        with self.assertRaises(ValueError):
            snafu_optional.rollback(target)
        self.assertEqual(self.files(target), edited)
        (target / 'cfgeconomycore.xml').write_bytes(before['cfgeconomycore.xml'])
        self.assertEqual(snafu_optional.rollback(target), 'recovered_bootstrap')
        self.assertEqual(self.files(target), before)
        snafu_optional.install(stage, target)
        snafu_optional.rollback(target)
        self.assertEqual(self.files(target), before)

    def test_kill_after_the_receipt_rolls_back_a_partial_delta(self):
        stage, target, before = self.staged_copy()
        for name, partial in (('verification.json', 0), ('verification.json', 5), ('ce/types.xml', 0), ('ce/types.xml', 7)):
            with self.subTest(name=name, partial=partial):
                self.kill_install(stage, target, name, partial)
                self.assertEqual(snafu_optional.rollback(target), 'rolled_back')
                self.assertEqual(self.files(target), before)

    def test_null_receipt_is_refused_not_recovered(self):
        stage, target, before = self.staged_copy()
        self.kill_install(stage, target, 'receipt.json')
        managed = target / snafu_optional.MANAGED
        (managed / 'receipt.json').write_bytes(b'null')
        (target / 'cfgeconomycore.xml').write_bytes(before['cfgeconomycore.xml'] + b'<!--operator edit-->')
        edited = self.files(target)
        with self.assertRaises(ValueError):
            snafu_optional.rollback(target)
        self.assertEqual(self.files(target), edited)

    def test_missing_evidence_and_incomplete_receipts_are_refusals(self):
        stage, target, before = self.staged_copy()
        snafu_optional.install(stage, target)
        managed = target / snafu_optional.MANAGED
        installed = self.files(target)
        saved = (managed / 'verification.json').read_bytes()
        (managed / 'verification.json').unlink()
        with self.assertRaises(economy.MissingEvidence):
            snafu_optional.rollback(target)
        (managed / 'verification.json').write_bytes(saved)
        full = json.loads((managed / 'receipt.json').read_bytes())
        (managed / 'ce/types.xml').write_bytes(b'operator data')
        for broken in ({k: v for k, v in full.items() if k != 'verification_sha256'},
                       {'before': full['before'], 'after': 'f' * 64, 'sources': full['sources']},
                       {k: v for k, v in full.items() if k != 'schema'}):
            (managed / 'receipt.json').write_bytes(economy.encode(broken))
            with self.assertRaises(ValueError):
                snafu_optional.rollback(target)
            self.assertEqual((managed / 'ce/types.xml').read_bytes(), b'operator data')
        self.assertEqual(self.files(target)['cfgeconomycore.xml'], installed['cfgeconomycore.xml'])

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

    def installed(self):
        stage = Path(self.tmp.name) / 'delta'
        snafu_optional.write_delta(stage, snafu_optional.generate(self.source, self.allow, self.report))
        target = Path(self.tmp.name) / 'copy'
        shutil.copytree(self.source, target)
        snafu_optional.install(stage, target)
        outside = Path(self.tmp.name) / 'operator-file-outside-mission.txt'
        outside.write_bytes(b'operator data: preserve exactly\n')
        return target, target / snafu_optional.MANAGED, outside

    def assert_refused_and_untouched(self, target, managed, outside):
        core = (target / 'cfgeconomycore.xml').read_bytes()
        with self.assertRaises(ValueError):
            snafu_optional.rollback(target)
        self.assertEqual(outside.read_bytes(), b'operator data: preserve exactly\n')
        self.assertEqual((target / 'cfgeconomycore.xml').read_bytes(), core)
        self.assertTrue(managed.is_dir())

    def test_rollback_refuses_a_hardlinked_staging_file_and_leaves_the_outside_file_alone(self):
        target, managed, outside = self.installed()
        os.link(outside, managed / 'core.next')
        self.assert_refused_and_untouched(target, managed, outside)

    def test_rollback_refuses_symlinked_non_regular_or_hardlinked_managed_files(self):
        target, managed, outside = self.installed()
        os.symlink(outside, managed / 'core.next')
        self.assert_refused_and_untouched(target, managed, outside)
        (managed / 'core.next').unlink()
        os.mkfifo(managed / 'core.next')
        self.assert_refused_and_untouched(target, managed, outside)
        (managed / 'core.next').unlink()
        os.link(managed / 'verification.json', outside.parent / 'second-name-for-evidence')
        self.assert_refused_and_untouched(target, managed, outside)

    def test_rollback_refuses_changed_verification_evidence_before_touching_the_core(self):
        target, managed, outside = self.installed()
        (managed / 'verification.json').write_bytes(b'{"status":"unverified","operator_note":"preserve"}\n')
        self.assert_refused_and_untouched(target, managed, outside)
        self.assertIn(b'operator_note', (managed / 'verification.json').read_bytes())

    def test_rollback_replaces_a_stale_regular_staging_file(self):
        target, managed, outside = self.installed()
        (managed / 'core.next').write_bytes(b'stale partial write')
        backup = (managed / 'core.backup').read_bytes()
        snafu_optional.rollback(target)
        self.assertEqual((target / 'cfgeconomycore.xml').read_bytes(), backup)
        self.assertFalse(managed.exists())

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

    CONSERVATIVE_SEVEN = {'SNAFUMarlin1895', 'SNAFUSWM629', 'SN_M870', 'SN_USP', 'SNAFU_M48',
                          'SNAFU_Trenchgun', 'GCGN_M1Garand'}
    WW2_SMGS = {'SNAFUThompsonMk2', 'SNAFUPPSh', 'SNAFUSten'}
    MODERN_MILITARY = {'SNAFU_AK103A', 'HK416_Gun', 'SCAR_Gun', 'SNAFU_MPX_GUN', 'SNHK417_Gun'}

    def weapons(self):
        return {e['class']: e for e in self.data['entries'] if e['kind'] == 'weapon'}

    def test_subset_is_the_conservative_seven_plus_ww2_smgs_plus_a_handful_of_modern_military_arms(self):
        weapons = self.weapons()
        self.assertEqual(set(weapons), self.CONSERVATIVE_SEVEN | self.WW2_SMGS | self.MODERN_MILITARY)
        for name, e in weapons.items():
            self.assertLessEqual(e['set']['nominal'], 4, name)
        self.assertTrue(self.data['excluded'])
        banned = ('AA12', 'AX50', 'M82', 'M200', 'AS50', 'M249', 'Bren', 'M1918', 'MDAR', 'VECTOR', 'Vikhr', 'P90',
                  'Magnum500', 'Alligator', 'KH9', 'AUG', 'TAR21', 'RDB', 'Modular', 'Honey', 'ACR', 'U100', 'BR18')
        for e in self.data['entries']:
            self.assertFalse(any(b.lower() in e['class'].lower() for b in banned), e['class'])

    def test_the_new_picks_are_military_usage_tier3_to_tier4_only_and_rare(self):
        weapons = self.weapons()
        for name in self.WW2_SMGS | self.MODERN_MILITARY:
            e = weapons[name]
            self.assertEqual(e['usage'], ['Military'], name)
            self.assertTrue(e['value'] and set(e['value']) <= {'Tier3', 'Tier4'}, name)
            self.assertEqual(e['tier'], 'rare', name)
            self.assertLessEqual(e['set']['nominal'], 2, name)
        for name in self.MODERN_MILITARY:
            self.assertEqual(weapons[name]['role'], 'modern', name)
        for name in self.WW2_SMGS:
            self.assertEqual(weapons[name]['role'], 'wood', name)

    def test_the_new_picks_bring_their_magazines_and_ammunition_into_the_allowlist(self):
        by_class = {e['class']: e for e in self.data['entries']}
        expected = {'SNAFUThompsonMk2': (['SNAFUThompsonMk2_30rdMag'], [], ['Ammo_45ACP']),
                    'SNAFUPPSh': (['SNAFUPPSh_71rdMag'], ['SNAFU_Ammo_762x25'], []),
                    'SNAFUSten': (['SNAFUSten_32rdMag'], [], ['Ammo_9x19']),
                    'SNAFU_MPX_GUN': (['SNAFU_MPX_30rnd_Mag'], [], ['Ammo_9x19']),
                    'SNHK417_Gun': (['SNHK417_Mag'], [], ['Ammo_308Win'])}
        for name, (mags, ammo, vanilla) in expected.items():
            e = by_class[name]
            self.assertEqual((e['magazines'], e['snafu_ammo'], e['vanilla_ammo']), (mags, ammo, vanilla), name)
            for m in mags:
                self.assertEqual(by_class[m]['kind'], 'magazine')
            for a in ammo:
                self.assertEqual(by_class[a]['kind'], 'ammo')
        for name in ('SNAFU_AK103A', 'HK416_Gun', 'SCAR_Gun'):  # accept vanilla magazines and ammo only
            self.assertEqual(by_class[name]['magazines'], [])
            self.assertTrue(by_class[name]['vanilla_ammo'] and not by_class[name]['snafu_ammo'], name)

    def test_exclusion_groups_no_longer_name_a_selected_class(self):
        selected = {e['class'] for e in self.data['entries']}
        for group in self.data['excluded']:
            self.assertFalse(set(group.get('classes', [])) & selected, group['group'])

    def test_optics_are_a_documented_empty_extension_point(self):
        self.assertEqual(self.data['optics']['entries'], [])
        self.assertEqual(self.data['optics']['status'], 'deferred-pending-owner-decision')
        self.assertFalse([e for e in self.data['entries'] if 'scope' in e['class'].lower() or e['kind'] == 'optic'])
        for bad in ({'status': 'accepted', 'entries': []},
                    {'status': 'deferred-pending-owner-decision', 'entries': [{'class': 'SNAFU_Scope'}]},
                    {'status': 'deferred-pending-owner-decision', 'entries': [], 'extra': 1}):
            with self.subTest(bad), self.assertRaises(ValueError):
                mutated = copy.deepcopy(self.data)
                mutated['optics'] = bad
                snafu_optional.validate_allowlist(mutated)

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
