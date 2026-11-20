"""Tactical Flava optional dependency: synthetic install only (plus one guarded real-install check).

The synthetic tests build a tiny layout of invented PBOs and class names. They never read or copy the real
Workshop item and never establish DayZ behaviour. Static file evidence is not runtime proof.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from tools.audit import pbo_config
from tools.package import economy, firearms, snafu_optional, tactical_flava_optional as tfo

try:
    from tests.unit.test_pbo_config import klass, pbo, rap
    from tests.slow.test_firearms_roster import roster as vanilla_roster, synthetic as synthetic_mission, entry as stock_entry
    from . import test_snafu_optional as snafu_fixture
except ImportError:
    from tests.unit.test_pbo_config import klass, pbo, rap
    from tests.slow.test_firearms_roster import roster as vanilla_roster, synthetic as synthetic_mission, entry as stock_entry
    import test_snafu_optional as snafu_fixture

REPO = Path(__file__).resolve().parents[2]
ALLOWLIST = REPO / 'tools/package/tactical_flava_allowlist.json'
FIREARMS_DOC = REPO / 'docs/FIREARMS.md'
REAL = Path('/mnt/g/SteamLibrary/steamapps/workshop/content/221100/2646817942')
VANILLA_ADDONS = Path('/mnt/g/SteamLibrary/steamapps/common/DayZ/Addons')
TERMS = b'synthetic vendor readme'
TEXT_A = '''// synthetic derapped-style config (invented class names)
#define SYN_LONG_MACRO(a) \\
    class Ignored##a {};
class CfgPatches { class syn_a { units[] = {}; weapons[] = {"SynRifle"}; }; };
class CfgWeapons
{
	class Rifle_Base;
	/* class Fake: Rifle_Base { scope = 2; }; */
	class SynRifle: Rifle_Base
	{
		scope = 2;
		model = "syn_a\\w\\rifle.p3d";
		displayName = "Quote ""inside"" ; { text";
		magazines[] = {"SynMagA","SynMagWrongBullet"};
		chamberableFrom[] = {"Ammo_545x39","Ammo_545x39Tracer"};
		attachments[] = {"weaponOptics","suppressorImpro"};
		class Inner { scope = 0; magazines[] = {"NotMine"}; };
	};
	class SynRifle_Black: SynRifle {};
	class SynDMR: Rifle_Base
	{
		scope = public;
		model = "syn_a\\w\\dmr.p3d";
		magazines[] = {"SynMagB"};
		chamberableFrom[] = {"Ammo_308Win"};
		attachments[] = {"weaponDMRAdapter","weaponOptics"};
	};
	class SynHunter: Rifle_Base
	{
		scope = 2;
		model = "syn_a\\w\\hunter.p3d";
		magazines[] = {"SynMagB"};
		chamberableFrom[] = {"Ammo_308Win"};
		attachments[] = {"weaponOptics"};
	};
	class SynNoOptic: Rifle_Base
	{
		scope = 2;
		model = "syn_a\\w\\rifle.p3d";
		magazines[] = {"SynMagA"};
		chamberableFrom[] = {"Ammo_545x39"};
		attachments[] = {"suppressorImpro"};
	};
	class SynHidden: Rifle_Base { scope = 0; model = "syn_a\\w\\rifle.p3d"; };
	class SynNoModel: Rifle_Base { scope = 2; model = "syn_a\\w\\gone.p3d"; chamberableFrom[] = {"Ammo_545x39"}; };
	class SynWrongAmmo: Rifle_Base
	{
		scope = 2; model = "syn_a\\w\\rifle.p3d"; magazines[] = {"SynMagA"}; chamberableFrom[] = {"Ammo_9x19"};
	};
	class SynAppended: Rifle_Base
	{
		scope = 2; model = "syn_a\\w\\rifle.p3d"; magazines[] += {"SynMagA"}; chamberableFrom[] = {"Ammo_545x39"};
	};
};
class cfgMagazines
{
	class SynMagA { scope = 2; ammo = "Bullet_545x39"; count = 30; model = "syn_a\\w\\mag.p3d"; };
	class SynMagB { scope = 2; ammo = "Bullet_308Win"; count = 20; };
	class SynMagWrongBullet { scope = 2; ammo = "Bullet_9x19"; count = 10; };
	class SynMagNoBullet { scope = 2; ammo = "Bullet_Gone"; count = 10; };
};
class CfgVehicles
{
	class Inventory_Base;
	class SynAdapter: Inventory_Base
	{
		scope = 2; model = "syn_a\\w\\adapter.p3d"; inventorySlot[] = {"weaponDMRAdapter"};
	};
};
'''
TEXT_TWICE = 'class CfgWeapons { class SynTwice { scope = 2; model = "syn_a\\w\\rifle.p3d"; }; };\n'
VANILLA = {'CfgMagazines': {'Ammo_545x39': {'parent': None, 'ammo': 'Bullet_545x39'},
                            'Ammo_545x39Tracer': {'parent': None, 'ammo': 'Bullet_545x39Tracer'},
                            'Ammo_308Win': {'parent': None, 'ammo': 'Bullet_308Win'},
                            'Ammo_9x19': {'parent': None, 'ammo': 'Bullet_9x19'}},
           'CfgAmmo': {k: {'parent': None} for k in ('Bullet_545x39', 'Bullet_545x39Tracer', 'Bullet_308Win',
                                                      'Bullet_9x19')}}


def rap_c():
    return rap(klass(
        '', CfgWeapons=klass('', SynBolt=klass('Rifle_Base', scope=2, model='syn_c\\w\\bolt.p3d', magazines=[],
                                               chamberableFrom=['Ammo_308Win'], attachments=['weaponOptics'])),
        CfgVehicles=klass('', SynOptic_Base=klass('ItemOptics_Base', scope=0, model='syn_c\\o\\optic.p3d',
                                                  inventorySlot=['weaponOptics']),
                          SynOptic_Black=klass('SynOptic_Base', scope=2),
                          SynOptic_WrongSlot=klass('ItemOptics_Base', scope=2, model='syn_c\\o\\optic.p3d',
                                                   inventorySlot=['suppressorImpro']))))


def build_install(root, publishedid=2646817942, terms=TERMS, addons='addons', extra_pbos=None, text=TEXT_A,
                  extra_dir='extra files', terms_name='readme.txt'):
    root.mkdir(parents=True)
    (root / 'meta.cpp').write_text(f'protocol = 1;\npublishedid = {publishedid};\nname = "Synthetic";\n')
    (root / addons).mkdir()
    members_a = {'config.cpp': text.encode(), 'w/rifle.p3d': b'x', 'w/dmr.p3d': b'x', 'w/hunter.p3d': b'x',
                 'w/adapter.p3d': b'x', 'w/mag.p3d': b'x', 'sub/config.cpp': TEXT_TWICE.encode()}
    (root / addons / 'syn_a.pbo').write_bytes(pbo(members_a, prefix='syn_a'))
    (root / addons / 'syn_c.pbo').write_bytes(pbo({'config.bin': rap_c(), 'w/bolt.p3d': b'x', 'o/optic.p3d': b'x'},
                                                  prefix='syn_c'))
    for name, data in (extra_pbos or {}).items():
        (root / addons / name).write_bytes(data)
    if terms is not None:
        (root / extra_dir).mkdir()
        (root / extra_dir / terms_name).write_bytes(terms)


def entry(cls, kind='weapon', role='modern', nominal=2, minimum=1, usage=('Military',), **extra):
    weaponish = kind != 'magazine'
    row = {'class': cls, 'kind': kind, 'role': role, 'tier': 'rare',
           'set': {'nominal': nominal, 'min': minimum, 'lifetime': 7200 if weaponish else 14400,
                   'restock': 1800 if weaponish else 0},
           'usage': list(usage), 'value': ['Tier3'], 'justification': 'synthetic'}
    if kind == 'weapon':
        row.update({'vanilla_ammo': [], 'magazines': [], 'optic_requires': []})
    if kind in {'optic', 'attachment'}:
        row.update({'slot': 'weaponOptics', 'fits': []})
    row.update(extra)
    return row


def allowlist(*rows, **top):
    data = {'schema': 1, 'name': 'synthetic-tf', 'workshop_id': '2646817942', 'status': 'unverified',
            'rights': {'license': 'none-recorded', 'redistribution': 'none', 'dependency_use': 'unstated',
                       'review': 'pending', 'terms_file': 'extra files/readme.txt',
                       'terms_sha256': hashlib.sha256(TERMS).hexdigest(),
                       'urls': ['https://example.invalid/page'], 'notes': ['synthetic']},
            'entries': list(rows), 'excluded': [{'group': 'synthetic-gimmick', 'reason': 'tone',
                                                 'classes': ['SynGatling']}]}
    data.update(top)
    return data


def good():
    return (
        entry('SynRifle', nominal=4, minimum=2, usage=['Military'], vanilla_ammo=['Ammo_545x39'],
              magazines=['SynMagA']),
        entry('SynHunter', role='civilian', usage=['Village', 'Hunting'], vanilla_ammo=['Ammo_308Win'],
              magazines=['SynMagB']),
        entry('SynDMR', usage=['Military'], vanilla_ammo=['Ammo_308Win'], magazines=['SynMagB'],
              optic_requires=['SynAdapter']),
        entry('SynBolt', usage=['Military'], vanilla_ammo=['Ammo_308Win'], magazines=[]),
        entry('SynMagA', kind='magazine', role='support', nominal=8, minimum=4, usage=['Military']),
        entry('SynMagB', kind='magazine', role='support', nominal=6, minimum=3, usage=['Military', 'Hunting']),
        entry('SynOptic_Black', kind='optic', usage=['Military'], slot='weaponOptics',
              fits=['SynRifle', 'SynDMR', 'SynBolt']),
        entry('SynAdapter', kind='attachment', role='support', nominal=0, minimum=0, usage=['Military'],
              slot='weaponDMRAdapter', fits=['SynDMR']))


def replace(rows, cls, **changes):
    out = []
    for row in rows:
        if row['class'] == cls:
            row = copy.deepcopy(row)
            changes = dict(changes)
            for key, field in (('nominal', 'nominal'), ('minimum', 'min')):
                if key in changes:
                    row['set'][field] = changes.pop(key)
            row.update(changes)
        out.append(row)
    return out


def statuses(report):
    return {k: v['status'] for k, v in report['classes'].items()}


try:
    from tests.unit import hash_cache_isolation
except ImportError:  # run as a script from tests/unit
    import hash_cache_isolation


def setUpModule():
    # #194: the whole-PBO hashing path reads/writes the hash cache; never the user's.
    hash_cache_isolation.enter()


def tearDownModule():
    hash_cache_isolation.leave()


class TextConfigParser(unittest.TestCase):
    ROOTS = ('CfgWeapons', 'CfgMagazines', 'CfgAmmo', 'CfgVehicles')

    @classmethod
    def setUpClass(cls):
        cls.parsed = pbo_config.parse_text_config(TEXT_A, cls.ROOTS)

    def test_rows_have_the_same_shape_as_the_rapified_reader(self):
        row = self.parsed['CfgWeapons']['SynRifle']
        self.assertEqual(row['parent'], 'Rifle_Base')
        self.assertEqual(row['scope'], 2)
        self.assertEqual(row['model'], 'syn_a\\w\\rifle.p3d')
        self.assertEqual(row['magazines'], ['SynMagA', 'SynMagWrongBullet'])
        self.assertEqual(row['chamberableFrom'], ['Ammo_545x39', 'Ammo_545x39Tracer'])
        self.assertEqual(row['attachments'], ['weaponOptics', 'suppressorImpro'])
        self.assertEqual(self.parsed['CfgMagazines']['SynMagA']['ammo'], 'Bullet_545x39')
        self.assertEqual(self.parsed['CfgMagazines']['SynMagA']['count'], 30)
        self.assertEqual(self.parsed['CfgVehicles']['SynAdapter']['inventorySlot'], ['weaponDMRAdapter'])

    def test_inheritance_nested_classes_forward_declarations_and_comments(self):
        weapons = self.parsed['CfgWeapons']
        self.assertEqual(weapons['SynRifle_Black'], {'parent': 'SynRifle', 'scope': None})
        self.assertNotIn('Inner', weapons)
        self.assertNotIn('Rifle_Base', weapons)  # forward declaration is not a definition
        self.assertNotIn('Fake', weapons)  # inside a block comment
        self.assertEqual(weapons['SynRifle']['magazines'], ['SynMagA', 'SynMagWrongBullet'])  # Inner did not leak
        self.assertEqual(weapons['SynDMR']['scope'], 2)  # the engine's public keyword

    def test_strings_with_doubled_quotes_and_roots_are_case_insensitive(self):
        self.assertIn('SynMagB', self.parsed['CfgMagazines'])  # declared as "cfgMagazines"
        self.assertEqual(self.parsed['CfgWeapons']['SynHidden']['model'], 'syn_a\\w\\rifle.p3d')
        self.assertEqual(self.parsed['CfgWeapons']['SynHunter']['magazines'], ['SynMagB'])  # after a quoted ';'

    def test_array_append_is_recorded(self):
        row = self.parsed['CfgWeapons']['SynAppended']
        self.assertEqual(row['magazines'], ['SynMagA'])
        self.assertEqual(row['appended'], ['magazines'])
        self.assertNotIn('appended', self.parsed['CfgWeapons']['SynRifle'])

    def test_budgets_and_malformed_input_are_refused(self):
        with self.assertRaises(ValueError):
            pbo_config.parse_text_config(TEXT_A, self.ROOTS, max_bytes=100)
        with self.assertRaises(ValueError):
            pbo_config.parse_text_config('class CfgWeapons { class A { scope = 2; };', self.ROOTS)  # unbalanced
        with self.assertRaises(ValueError):
            pbo_config.parse_text_config('class CfgWeapons { class A { ' + 'class B {' * 40 + '}; ' * 40 + '}; };',
                                         self.ROOTS)
        with self.assertRaises(ValueError):
            pbo_config.parse_text_config(TEXT_A, self.ROOTS, max_tokens=50)
        with self.assertRaises(ValueError):
            pbo_config.parse_text_config('class CfgWeapons { /* never closed', self.ROOTS)

    def test_rap_reader_exposes_attachments_inventory_slot_and_append(self):
        parsed = pbo_config.parse_rap(rap_c(), ('CfgWeapons', 'CfgVehicles'))
        self.assertEqual(parsed['CfgWeapons']['SynBolt']['attachments'], ['weaponOptics'])
        self.assertEqual(parsed['CfgVehicles']['SynOptic_Base']['inventorySlot'], ['weaponOptics'])
        tree = rap(klass('', CfgWeapons=klass('', Only=klass('P', magazines=['a']))))
        patched = tree.replace(b'\x02magazines\0', b'\x05\0\0\0\0magazines\0')
        self.assertEqual(len(patched), len(tree) + 4)
        row = pbo_config.parse_rap(patched, ('CfgWeapons',))['CfgWeapons']['Only']
        self.assertEqual(row['magazines'], ['a'])
        self.assertEqual(row['appended'], ['magazines'])

    def test_config_members_cover_binary_and_text_members(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / 'syn_a.pbo'
            path.write_bytes(pbo({'config.cpp': TEXT_A.encode(), 'sub/config.cpp': TEXT_TWICE.encode(),
                                  'readme.txt': b'x'}, prefix='syn_a'))
            members = dict(pbo_config.read_config_members(path, self.ROOTS))
            self.assertEqual(sorted(members), ['config.cpp', 'sub/config.cpp'])
            self.assertIn('SynTwice', members['sub/config.cpp']['CfgWeapons'])


class Verifier(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.install = Path(self.tmp.name) / 'mod'
        build_install(self.install)

    def tearDown(self):
        self.tmp.cleanup()

    def verify(self, *rows, **kw):
        kw.setdefault('vanilla', VANILLA)
        return tfo.verify_install(self.install, allowlist(*rows), **kw)

    def rebuild(self, **kw):
        shutil.rmtree(self.install)
        build_install(self.install, **kw)

    def snapshot(self):
        return {p.relative_to(self.install).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.install.rglob('*') if p.is_file()}

    def test_good_entries_verify(self):
        report = self.verify(*good())
        self.assertEqual(report['kind'], 'tactical-flava-verification')
        self.assertEqual(report['status'], 'verified', report['install']['problems'])
        for name, row in report['classes'].items():
            self.assertEqual(row['status'], 'verified', (name, row))
        self.assertEqual(report['counts'], {'verified': 8, 'missing': 0, 'unverified': 0})
        self.assertEqual(report['install']['publishedid'], '2646817942')
        self.assertTrue(report['terms']['matches_reviewed'])
        self.assertTrue(report['vanilla']['checked'])
        self.assertEqual(report['runtime_acceptance'], 'pending')
        self.assertIn('model-unresolved', report['classes']['SynMagB']['notes'])  # magazine models are a note

    def test_verification_is_read_only(self):
        before = self.snapshot()
        self.verify(*good())
        self.assertEqual(before, self.snapshot())

    def test_capitalised_addon_and_extra_folder_names_are_found(self):
        self.rebuild(addons='Addons', extra_dir='Extra Files', terms_name='README.TXT')
        self.assertEqual(self.verify(*good())['status'], 'verified')

    def test_missing_class_is_reported_missing(self):
        report = self.verify(*good(), entry('SynGhost', usage=['Military'], vanilla_ammo=['Ammo_545x39'],
                                            magazines=['SynMagA']))
        self.assertEqual(report['classes']['SynGhost']['status'], 'missing')
        self.assertEqual(report['status'], 'unverified')

    def test_wrong_ammo_is_unverified(self):
        rows = replace(good(), 'SynRifle', vanilla_ammo=['Ammo_9x19'])
        report = self.verify(*rows)
        self.assertEqual(report['classes']['SynRifle']['status'], 'unverified')
        self.assertIn('ammo-not-chamberable:Ammo_9x19', report['classes']['SynRifle']['reasons'])
        self.assertEqual(report['status'], 'unverified')

    def test_ammo_missing_from_vanilla_is_unverified(self):
        vanilla = copy.deepcopy(VANILLA)
        del vanilla['CfgMagazines']['Ammo_545x39']
        report = self.verify(*good(), vanilla=vanilla)
        self.assertIn('ammo-not-in-vanilla:Ammo_545x39', report['classes']['SynRifle']['reasons'])

    def test_magazine_with_another_bullet_than_the_loose_ammo_is_unverified(self):
        rows = replace(good(), 'SynRifle', magazines=['SynMagA', 'SynMagWrongBullet'])
        rows.append(entry('SynMagWrongBullet', kind='magazine', role='support', usage=['Military']))
        report = self.verify(*rows)
        self.assertIn('magazine-bullet-mismatch:SynMagWrongBullet', report['classes']['SynRifle']['reasons'])

    def test_magazine_not_accepted_by_the_weapon_and_bullet_class_missing(self):
        rows = replace(good(), 'SynRifle', magazines=['SynMagA', 'SynMagB'])
        report = self.verify(*rows)
        self.assertIn('magazine-not-accepted:SynMagB', report['classes']['SynRifle']['reasons'])
        rows = replace(good(), 'SynRifle', magazines=['SynMagA', 'SynMagNoBullet'])
        rows.append(entry('SynMagNoBullet', kind='magazine', role='support', usage=['Military']))
        report = self.verify(*rows)
        self.assertIn('bullet-class-missing', ' '.join(report['classes']['SynMagNoBullet']['reasons']))
        self.assertIn('magazine-unverified:SynMagNoBullet', report['classes']['SynRifle']['reasons'])

    def test_hidden_scope_and_missing_model_are_unverified(self):
        rows = [entry('SynHidden', nominal=0, minimum=0), entry('SynNoModel', nominal=0, minimum=0)]
        report = self.verify(*rows)
        self.assertIn('scope-0-not-public', report['classes']['SynHidden']['reasons'])
        self.assertIn('model-missing-from-pbos', report['classes']['SynNoModel']['reasons'])

    def test_optic_on_a_weapon_without_the_slot_is_unverified(self):
        rows = replace(good(), 'SynOptic_Black', fits=['SynRifle', 'SynNoOptic'])
        rows.append(entry('SynNoOptic', usage=['Military'], vanilla_ammo=['Ammo_545x39'], magazines=['SynMagA']))
        report = self.verify(*rows)
        self.assertIn('weapon-lacks-slot:SynNoOptic:weaponOptics', report['classes']['SynOptic_Black']['reasons'])
        self.assertEqual(report['classes']['SynRifle']['status'], 'verified')

    def test_optic_for_another_slot_is_unverified(self):
        rows = replace(good(), 'SynOptic_Black', slot='suppressorImpro')
        report = self.verify(*rows)
        self.assertIn('slot-mismatch:suppressorImpro', report['classes']['SynOptic_Black']['reasons'])
        rows = [r for r in good() if r['class'] != 'SynOptic_Black']
        rows.append(entry('SynOptic_WrongSlot', kind='optic', slot='weaponOptics', fits=['SynRifle']))
        report = self.verify(*rows)
        self.assertIn('slot-mismatch:weaponOptics', report['classes']['SynOptic_WrongSlot']['reasons'])

    def test_required_attachment_must_verify_for_the_weapon(self):
        text = TEXT_A.replace('attachments[] = {"weaponDMRAdapter","weaponOptics"};',
                              'attachments[] = {"weaponOptics"};')
        self.rebuild(text=text)
        report = self.verify(*good())
        self.assertIn('weapon-lacks-slot:SynDMR:weaponDMRAdapter', report['classes']['SynAdapter']['reasons'])
        self.assertIn('optic-requires-unverified:SynAdapter', report['classes']['SynDMR']['reasons'])

    def test_class_defined_twice_is_not_trusted(self):
        dup = pbo({'config.cpp': TEXT_TWICE.encode(), 'w/rifle.p3d': b'x'}, prefix='syn_a')
        self.rebuild(extra_pbos={'syn_dup.pbo': dup})
        rows = [entry('SynTwice', nominal=0, minimum=0)]
        report = self.verify(*rows)
        self.assertIn('multiple-definitions', report['classes']['SynTwice']['reasons'])  # also twice inside syn_a

    def test_class_defined_in_two_pbos_is_not_trusted(self):
        text = 'class CfgWeapons { class SynRifle { scope = 2; model = "syn_a\\w\\rifle.p3d"; }; };'
        dup = pbo({'config.cpp': text.encode()}, prefix='syn_dup')
        self.rebuild(extra_pbos={'syn_dup.pbo': dup})
        report = self.verify(*good())
        self.assertIn('multiple-definitions', report['classes']['SynRifle']['reasons'])
        self.assertEqual(report['status'], 'unverified')

    def test_array_append_is_never_treated_as_a_full_array(self):
        rows = [entry('SynAppended', nominal=0, minimum=0, vanilla_ammo=['Ammo_545x39'], magazines=['SynMagA'])]
        rows.append(entry('SynMagA', kind='magazine', role='support', usage=['Military'], nominal=0, minimum=0))
        report = self.verify(*rows)
        self.assertEqual(report['classes']['SynAppended']['status'], 'verified')
        rows = [entry('SynAppended', nominal=0, minimum=0, vanilla_ammo=['Ammo_545x39'], magazines=['SynMagB']),
                entry('SynMagB', kind='magazine', role='support', usage=['Military'], nominal=0, minimum=0)]
        report = self.verify(*rows)
        self.assertIn('array-append-unresolved:magazines', report['classes']['SynAppended']['reasons'])

    def test_vanilla_table_is_required(self):
        report = self.verify(*good(), vanilla=None)
        self.assertEqual(report['status'], 'unverified')
        self.assertIn('vanilla-not-provided', report['install']['problems'])
        self.assertFalse(report['vanilla']['checked'])

    def test_identity_and_terms_are_checked(self):
        self.rebuild(publishedid=1)
        self.assertIn('publishedid-mismatch', self.verify(*good())['install']['problems'])
        self.rebuild(terms=b'changed vendor readme')
        report = self.verify(*good())
        self.assertIn('terms-changed-since-review', report['install']['problems'])
        self.assertFalse(report['terms']['matches_reviewed'])
        self.assertEqual(report['status'], 'unverified')
        self.rebuild(terms=None)
        self.assertIn('terms-file-missing', self.verify(*good())['install']['problems'])
        shutil.rmtree(self.install)
        self.install.mkdir()
        report = self.verify(*good())
        self.assertIn('meta-missing', report['install']['problems'])
        self.assertIn('no-addon-pbos', report['install']['problems'])

    def test_symlinked_install_and_pbo_budget_are_refused_and_corrupt_pbo_is_reported(self):
        link = Path(self.tmp.name) / 'link'
        link.symlink_to(self.install)
        with self.assertRaises(ValueError):
            tfo.verify_install(link, allowlist(*good()), vanilla=VANILLA)
        with self.assertRaises(ValueError):
            self.verify(*good(), max_pbos=1)
        (self.install / 'addons/zzz_corrupt.pbo').write_bytes(b'not a pbo')
        report = self.verify(*good())
        self.assertTrue(any('zzz_corrupt.pbo' in p for p in report['install']['problems']))
        self.assertEqual(report['status'], 'unverified')

    def test_vanilla_loader_reads_magazines_and_ammo_from_binary_pbos(self):
        folder = Path(self.tmp.name) / 'vanilla'
        folder.mkdir()
        tree = klass('', CfgMagazines=klass('', Ammo_545x39=klass('', scope=2, ammo='Bullet_545x39', count=30)),
                     CfgAmmo=klass('', Bullet_545x39=klass('', scope=1)))
        (folder / 'syn_vanilla.pbo').write_bytes(pbo({'config.bin': rap(tree)}, prefix='dz\\syn'))
        (folder / 'broken.pbo').write_bytes(b'junk')
        table = tfo.load_vanilla(folder)
        self.assertEqual(table['CfgMagazines']['Ammo_545x39']['ammo'], 'Bullet_545x39')
        self.assertIn('Bullet_545x39', table['CfgAmmo'])
        self.assertEqual([p.split(':')[0] for p in table['problems']], ['broken.pbo'])
        with self.assertRaises(ValueError):
            tfo.load_vanilla(folder, max_pbos=1)


class AllowlistValidation(unittest.TestCase):
    def check(self, *rows, **top):
        tfo.validate_allowlist(allowlist(*rows, **top))

    def refuses(self, *rows, **top):
        with self.assertRaises(ValueError):
            self.check(*rows, **top)

    def test_good_allowlist_is_valid(self):
        self.check(*good())

    def test_modern_pick_with_town_usage_is_refused(self):
        self.refuses(*replace(good(), 'SynRifle', usage=['Military', 'Town']))
        self.refuses(*replace(good(), 'SynRifle', usage=['Town']))
        self.refuses(*replace(good(), 'SynOptic_Black', usage=['Military', 'Village']))

    def test_modern_pick_without_military_is_refused(self):
        self.refuses(*replace(good(), 'SynRifle', usage=['Police']))
        self.refuses(*replace(good(), 'SynOptic_Black', usage=['Police']))

    def test_civilian_pick_may_not_use_military_or_police(self):
        self.refuses(*replace(good(), 'SynHunter', usage=['Village', 'Military']))
        self.refuses(*replace(good(), 'SynHunter', usage=['Hunting', 'Police']))

    def test_spawning_weapon_needs_ammo_and_nonzero_magazines(self):
        rows = replace(good(), 'SynMagA', nominal=0, minimum=0)  # zero-count magazine for a spawning weapon
        self.refuses(*rows)
        self.refuses(*replace(good(), 'SynRifle', vanilla_ammo=[]))
        # a weapon that does not spawn may have zero-count companions
        rows = replace(replace(good(), 'SynRifle', nominal=0, minimum=0), 'SynMagA', nominal=0, minimum=0)
        self.check(*rows)

    def test_magazine_usage_must_come_from_its_weapons(self):
        self.refuses(*replace(good(), 'SynMagA', usage=['Military', 'Hunting']))  # SynRifle is Military only
        self.refuses(*replace(good(), 'SynMagA', usage=['Hunting']))

    def test_orphan_and_all_modern_magazines(self):
        rows = list(good()) + [entry('SynOrphan', kind='magazine', role='support', usage=['Military'])]
        self.refuses(*rows)

    def test_weapon_needs_a_magazine_usable_where_it_spawns(self):
        rows = replace(replace(good(), 'SynHunter', usage=['Village']), 'SynMagB', usage=['Military'])
        self.refuses(*rows)  # SynMagB only spawns in Military, where SynHunter never does

    def test_optic_and_attachment_references(self):
        self.refuses(*replace(good(), 'SynOptic_Black', fits=['SynGhost']))
        self.refuses(*replace(good(), 'SynOptic_Black', fits=[]))
        self.refuses(*replace(good(), 'SynDMR', optic_requires=['SynGhost']))
        self.refuses(*replace(good(), 'SynRifle', optic_requires=['SynAdapter']))  # adapter does not fit SynRifle
        self.refuses(*replace(good(), 'SynOptic_Black', slot='bad slot'))

    def test_shape_rights_and_exclusion_errors(self):
        self.refuses(*good(), workshop_id='1')
        self.refuses(*good(), status='verified')
        self.refuses(*good(), schema=2)
        self.refuses(*good(), extra='x')
        for patch in ({'terms_sha256': 'abc'}, {'redistribution': 'allowed'}, {'review': 'done'},
                      {'license': 'MIT'}, {'urls': ['http://x']}, {'dependency_use': 'allowed'},
                      {'terms_file': '../etc/passwd'}):
            bad = allowlist(*good())
            bad['rights'] = dict(bad['rights'], **patch)
            with self.assertRaises(ValueError, msg=patch):
                tfo.validate_allowlist(bad)
        self.refuses(*good(), excluded=[{'group': 'g'}])
        self.refuses(*good(), excluded=[{'group': 'g', 'reason': 'r', 'classes': ['SynRifle']}])
        self.refuses(*list(good()) + [good()[0]])
        self.refuses(*replace(good(), 'SynRifle', set={'nominal': 1, 'min': 2, 'lifetime': 1, 'restock': 0}))
        self.refuses(*replace(good(), 'SynRifle', justification=' '))
        self.refuses(*replace(good(), 'SynRifle', tier='epic'))
        self.refuses(*replace(good(), 'SynRifle', role='wood'))
        self.refuses(*[dict(r, kind='ammo') if r['class'] == 'SynMagA' else r for r in good()])
        self.refuses(*[entry('Syn%d' % i, nominal=0, minimum=0) for i in range(tfo.MAX_ENTRIES + 1)])


def mission(root):
    synthetic_mission(root)
    (root / 'cfglimitsdefinition.xml').write_text(
        '<lists><usageflags><usage name="Town"/><usage name="Village"/><usage name="Military"/>'
        '<usage name="Hunting"/><usage name="Police"/><usage name="Farm"/></usageflags><valueflags>'
        '<value name="Tier1"/><value name="Tier2"/><value name="Tier3"/><value name="Tier4"/></valueflags></lists>')
    types = (root / 'db/types.xml').read_text()
    extra = ''.join(stock_entry(n, 50, 30, 14400, 0, ['Military'], ['Tier3']) for n in ('Ammo_545x39', 'Ammo_308Win'))
    (root / 'db/types.xml').write_text(types.replace('</types>', extra + '</types>'))


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


def files_of(target):
    return {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob('*') if p.is_file()}


class FailClosedGeneration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        snafu_fixture.patch_roster(self, self.tmp.name)
        self.install = t / 'mod'
        build_install(self.install)
        self.mission = t / 'mission'
        self.mission.mkdir()
        mission(self.mission)
        self.allow = allowlist(*good())
        self.report = tfo.verify_install(self.install, self.allow, vanilla=VANILLA)
        self.assertEqual(self.report['status'], 'verified')

    def tearDown(self):
        self.tmp.cleanup()

    def test_one_live_compatible_ammo_or_magazine_is_sufficient(self):
        """SYNTHETIC alternatives may be disabled if another compatible source spawns."""
        a = copy.deepcopy(self.allow)
        rifle = a['entries'][0]
        rifle['vanilla_ammo'].append('MissingSyntheticAmmo')
        a['entries'].append(entry('SynDisabledMag', kind='magazine', role='support', nominal=0, minimum=0))
        rifle['magazines'].append('SynDisabledMag')
        report = copy.deepcopy(self.report)
        report['allowlist_sha256'] = tfo.allowlist_sha256(a)
        report['classes']['SynDisabledMag'] = {'status': 'verified'}
        tfo.generate(self.mission, a, report)

    def test_managed_ammo_override_wins_over_positive_stock_nominal(self):
        """SYNTHETIC existing roster override disables otherwise positive loose ammo."""
        managed = self.mission / economy.MANAGED / 'ce'
        managed.mkdir(parents=True)
        (managed / 'types.xml').write_text('<types><type name="Ammo_308Win"><nominal>0</nominal></type></types>')
        with self.assertRaisesRegex(ValueError, 'spawning weapon'):
            tfo.generate(self.mission, self.allow, self.report)

    def test_no_report_or_unverified_report_generates_nothing(self):
        for report in (None, {}, dict(self.report, status='unverified')):
            with self.assertRaises(ValueError):
                tfo.generate(self.mission, self.allow, report)

    def test_native_magazine_requirement_cannot_be_hidden_by_an_empty_policy_list(self):
        """SYNTHETIC config requires a detachable magazine even if policy omits it."""
        a = copy.deepcopy(self.allow)
        next(e for e in a['entries'] if e['class'] == 'SynRifle')['magazines'] = []
        a['entries'] = [e for e in a['entries'] if e['class'] != 'SynMagA']
        report = tfo.verify_install(self.install, a, vanilla=VANILLA)
        with self.assertRaisesRegex(ValueError, 'spawning weapon.*magazine'):
            tfo.generate(self.mission, a, report)

    def test_report_must_match_allowlist_vanilla_terms_and_every_class(self):
        odd = copy.deepcopy(self.allow)
        odd['entries'][0]['set']['nominal'] = 3
        with self.assertRaises(ValueError):
            tfo.generate(self.mission, odd, self.report)
        for edit in (lambda r: r['classes'].pop('SynRifle'),
                     lambda r: r['classes']['SynRifle'].update(status='unverified'),
                     lambda r: r['terms'].update(matches_reviewed=False),
                     lambda r: r['vanilla'].update(checked=False),
                     lambda r: r['install'].update(problems=['x'])):
            report = copy.deepcopy(self.report)
            edit(report)
            with self.assertRaises(ValueError):
                tfo.generate(self.mission, self.allow, report)

    def test_committed_allowlist_with_no_report_yields_no_spawns(self):
        with self.assertRaises(ValueError):
            tfo.generate(self.mission, json.loads(ALLOWLIST.read_text()), None)

    def test_required_adapter_is_preattached_in_the_managed_spawnable_delta(self):
        """SYNTHETIC DMR mirrors the allowlisted TF M14 adapter requirement."""
        files = tfo.generate(self.mission, self.allow, self.report)
        self.assertIn('ce/cfgspawnabletypes.xml', files)
        spawnable = ET.fromstring(files['ce/cfgspawnabletypes.xml'])
        self.assertEqual(spawnable.tag, 'spawnabletypes')
        self.assertEqual([n.attrib for n in spawnable], [{'name': 'SynDMR'}])
        attachments = spawnable[0].find('attachments')
        self.assertEqual(attachments.attrib, {'chance': '1.00'})
        self.assertEqual([n.attrib for n in attachments], [{'name': 'SynAdapter', 'chance': '1.00'}])
        fragment = ET.fromstring(files['cfgeconomycore.append.xml'])
        self.assertIn({'name': 'cfgspawnabletypes.xml', 'type': 'spawnabletypes'},
                      [n.attrib for n in fragment[0]])
        manifest = json.loads(files['delta-manifest.json'])
        self.assertEqual(manifest['files']['ce/cfgspawnabletypes.xml'], economy.sha(files['ce/cfgspawnabletypes.xml']))
        # The adapter's independent CE nominal remains zero.
        self.assertEqual(ET.fromstring(files['ce/types.xml']).find("type[@name='SynAdapter']/nominal").text, '0')
        a = copy.deepcopy(self.allow)
        next(e for e in a['entries'] if e['class'] == 'SynDMR')['set'].update(nominal=0, min=0)
        report = dict(self.report, allowlist_sha256=tfo.allowlist_sha256(a))
        self.assertEqual(len(ET.fromstring(tfo.generate(self.mission, a, report)['ce/cfgspawnabletypes.xml'])), 0)

    def test_verified_report_generates_complete_new_type_entries(self):
        files = tfo.generate(self.mission, self.allow, self.report)
        types = ET.fromstring(files['ce/types.xml'])
        by = {t.get('name'): t for t in types.findall('type')}
        self.assertEqual(set(by), {r['class'] for r in good()})
        rifle, mag, optic = by['SynRifle'], by['SynMagA'], by['SynOptic_Black']
        self.assertEqual((rifle.findtext('nominal'), rifle.findtext('min'), rifle.findtext('lifetime'),
                          rifle.findtext('restock')), ('4', '2', '7200', '1800'))
        self.assertEqual((mag.findtext('quantmin'), mag.findtext('quantmax'), mag.findtext('lifetime'),
                          mag.findtext('restock')), ('30', '70', '14400', '0'))
        self.assertEqual((rifle.findtext('quantmin'), optic.findtext('quantmax')), ('-1', '-1'))
        self.assertEqual(rifle.find('category').get('name'), 'weapons')
        self.assertEqual([u.get('name') for u in by['SynHunter'].findall('usage')], ['Village', 'Hunting'])
        self.assertEqual(by['SynAdapter'].findtext('nominal'), '0')
        self.assertIn(b'hollow-country-tactical-flava/ce', files['cfgeconomycore.append.xml'])
        meta = json.loads(files['economy-report.json'])
        self.assertEqual(meta['kind'], 'tactical-flava-optional')
        self.assertEqual(meta['runtime_acceptance'], 'pending')
        self.assertFalse(meta['loot_fix_claim'])
        self.assertIn('optional', meta['dependency'])
        self.assertEqual(json.loads(files['delta-manifest.json'])['kind'], 'tactical-flava-optional')

    def test_refuses_stock_collisions_unknown_tags_and_unspawnable_ammo(self):
        stock = self.allow['entries'] + [entry('SynthMag', nominal=0, minimum=0)]
        odd = dict(self.allow, entries=stock)
        report = dict(self.report, allowlist_sha256=tfo.allowlist_sha256(odd))
        report['classes'] = dict(report['classes'], SynthMag={'status': 'verified', 'reasons': [], 'notes': []})
        with self.assertRaises(ValueError):
            tfo.generate(self.mission, odd, report)
        odd = copy.deepcopy(self.allow)
        odd['entries'][1]['usage'] = ['Village', 'Hunting', 'Coast']
        report = dict(self.report, allowlist_sha256=tfo.allowlist_sha256(odd))
        with self.assertRaises(ValueError):
            tfo.generate(self.mission, odd, report)
        broken = Path(self.tmp.name) / 'no-ammo'
        shutil.copytree(self.mission, broken)
        text = (broken / 'db/types.xml').read_text().replace('<type name="Ammo_308Win"><nominal>50</nominal>',
                                                             '<type name="Ammo_308Win"><nominal>0</nominal>')
        (broken / 'db/types.xml').write_text(text)
        with self.assertRaises(ValueError):
            tfo.generate(broken, self.allow, self.report)
        (broken / 'db/types.xml').write_text(text.replace('Ammo_308Win', 'Ammo_Other'))
        with self.assertRaises(ValueError):
            tfo.generate(broken, self.allow, self.report)

    def test_refuses_classes_the_roster_or_snafu_already_manage(self):
        target = Path(self.tmp.name) / 'copy'
        shutil.copytree(self.mission, target)
        firearms.write_delta(Path(self.tmp.name) / 'roster', firearms.generate(target, vanilla_roster()))
        firearms.install(Path(self.tmp.name) / 'roster', target)
        for taken in ('SynthModernRifle', 'SynWood'):
            odd = dict(self.allow, entries=self.allow['entries'] + [entry(taken, nominal=0, minimum=0)])
            report = copy.deepcopy(self.report)
            report['allowlist_sha256'] = tfo.allowlist_sha256(odd)
            report['classes'][taken] = {'status': 'verified', 'reasons': [], 'notes': []}
            if taken == 'SynWood':
                snafu_install = Path(self.tmp.name) / 'snafu-mod'
                snafu_fixture.build_install(snafu_install)
                snafu_allow = snafu_fixture.allowlist(*snafu_fixture.GOOD)
                snafu_report = snafu_optional.verify_install(snafu_install, snafu_allow)
                snafu_optional.write_delta(Path(self.tmp.name) / 'snafu',
                                           snafu_optional.generate(target, snafu_allow, snafu_report))
                snafu_optional.install(Path(self.tmp.name) / 'snafu', target)
            with self.assertRaises(ValueError, msg=taken):
                tfo.generate(target, odd, report)


class InstallRollback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        snafu_fixture.patch_roster(self, self.tmp.name)
        self.install = t / 'mod'
        build_install(self.install)
        self.source = t / 'source'
        self.source.mkdir()
        mission(self.source)
        self.allow = allowlist(*good())
        self.report = tfo.verify_install(self.install, self.allow, vanilla=VANILLA)

    def tearDown(self):
        self.tmp.cleanup()

    def stage(self, source=None, name='delta'):
        stage = Path(self.tmp.name) / name
        tfo.write_delta(stage, tfo.generate(source or self.source, self.allow, self.report))
        return stage

    def installed(self):
        stage = self.stage()
        target = Path(self.tmp.name) / 'copy'
        shutil.copytree(self.source, target)
        tfo.install(stage, target)
        outside = Path(self.tmp.name) / 'operator-file-outside-mission.txt'
        outside.write_bytes(b'operator data: preserve exactly\n')
        return target, target / tfo.MANAGED, outside

    def assert_refused_and_untouched(self, target, managed, outside):
        core = (target / 'cfgeconomycore.xml').read_bytes()
        with self.assertRaises(ValueError):
            tfo.rollback(target)
        self.assertEqual(outside.read_bytes(), b'operator data: preserve exactly\n')
        self.assertEqual((target / 'cfgeconomycore.xml').read_bytes(), core)
        self.assertTrue(managed.is_dir())

    def test_install_rechecks_effective_support_after_rehashed_stage_tampering(self):
        """SYNTHETIC rehashed stage still cannot disable required support."""
        files = tfo.generate(self.source, self.allow, self.report)
        root = ET.fromstring(files['ce/types.xml'])
        support = root.find("type[@name='SynMagA']")
        support.find('nominal').text = support.find('min').text = '0'
        files['ce/types.xml'] = ET.tostring(root)
        manifest = json.loads(files['delta-manifest.json'])
        manifest['files']['ce/types.xml'] = economy.sha(files['ce/types.xml'])
        files['delta-manifest.json'] = economy.encode(manifest)
        stage = Path(self.tmp.name) / 'tampered-support'
        tfo.write_delta(stage, files)
        before = economy.snapshot(self.source)
        with self.assertRaisesRegex(ValueError, 'spawning weapon'):
            tfo.install(stage, self.source)
        self.assertEqual(before, economy.snapshot(self.source))
        self.assertFalse((self.source / tfo.MANAGED).exists())

    def test_failed_types_write_cleans_up_and_allows_byte_exact_retry(self):
        """SYNTHETIC disk failure, including a partially created managed file."""
        stage = Path(self.tmp.name) / 'failed-delta'
        tfo.write_delta(stage, tfo.generate(self.source, self.allow, self.report))
        before = {p.relative_to(self.source): p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        write = economy.fresh_write
        for failing_name in ('ce/types.xml', 'ce/cfgspawnabletypes.xml'):
            for partial in (False, True):
                def fail(root, name, data):
                    if name == failing_name:
                        if partial:
                            write(root, name, b'<types>')
                        raise OSError('SYNTHETIC disk full')
                    return write(root, name, data)
                with self.subTest(file=failing_name, partial=partial):
                    with mock.patch.object(economy, 'fresh_write', side_effect=fail):
                        with self.assertRaisesRegex(OSError, 'SYNTHETIC disk full'):
                            tfo.install(stage, self.source)
                    self.assertFalse((self.source / tfo.MANAGED).exists())
                    tfo.install(stage, self.source)
                    tfo.rollback(self.source)
                    self.assertEqual(before, {p.relative_to(self.source): p.read_bytes()
                                              for p in self.source.rglob('*') if p.is_file()})

    def test_adapter_delta_installs_and_rolls_back_without_touching_operator_spawnables(self):
        """SYNTHETIC operator file remains byte exact; the TF delta owns its own file."""
        original = b'<spawnabletypes><!--SYNTHETIC operator bytes--></spawnabletypes>\r\n'
        operator = self.source / 'cfgspawnabletypes.xml'
        operator.write_bytes(original)
        stage = self.stage()
        before = files_of(self.source)
        tfo.install(stage, self.source)
        installed = self.source / tfo.MANAGED / 'ce/cfgspawnabletypes.xml'
        self.assertTrue(installed.is_file())
        installed.write_bytes(installed.read_bytes() + b'<!--SYNTHETIC drift-->')
        with self.assertRaisesRegex(ValueError, 'spawnable.*drift'):
            tfo.rollback(self.source)
        installed.write_bytes((stage / 'ce/cfgspawnabletypes.xml').read_bytes())
        tfo.rollback(self.source)
        self.assertEqual(before, files_of(self.source))
        self.assertEqual(operator.read_bytes(), original)

    def test_rollback_accepts_a_legacy_receipt_without_a_spawnable_delta(self):
        """SYNTHETIC prior-version install: no managed spawnable file or hash."""
        stage = self.stage()
        before = files_of(self.source)
        tfo.install(stage, self.source)
        managed = self.source / tfo.MANAGED
        core = self.source / 'cfgeconomycore.xml'
        tree = ET.fromstring(core.read_bytes())
        ce = tree.find("ce[@folder='hollow-country-tactical-flava/ce']")
        ce.remove(ce.find("file[@type='spawnabletypes']"))
        legacy_core = ET.tostring(tree)
        core.write_bytes(legacy_core)
        (managed / 'ce/cfgspawnabletypes.xml').unlink()
        receipt = json.loads((managed / 'receipt.json').read_bytes())
        receipt.pop('spawnable_sha256')
        receipt['after'] = economy.sha(legacy_core)
        (managed / 'receipt.json').write_bytes(economy.encode(receipt))
        tfo.rollback(self.source)
        self.assertEqual(before, files_of(self.source))

    def staged_copy(self):
        stage = self.stage()
        target = Path(self.tmp.name) / 'copy'
        shutil.copytree(self.source, target)
        return stage, target, files_of(target)

    def kill_install(self, stage, target, name, partial=0):
        with mock.patch.object(economy, 'fresh_write', killing_write(economy.fresh_write, name, partial)):
            with self.assertRaises(Killed):
                tfo.install(stage, target)
        self.assertTrue((target / tfo.MANAGED).is_dir())

    def test_kill_before_receipt_is_recovered_and_a_changed_core_is_refused(self):
        stage, target, before = self.staged_copy()
        self.kill_install(stage, target, 'receipt.json')
        (target / 'cfgeconomycore.xml').write_bytes(before['cfgeconomycore.xml'] + b'<!--operator edit-->')
        edited = files_of(target)
        with self.assertRaises(ValueError):
            tfo.rollback(target)
        self.assertEqual(files_of(target), edited)
        (target / 'cfgeconomycore.xml').write_bytes(before['cfgeconomycore.xml'])
        self.assertEqual(tfo.rollback(target), 'recovered_bootstrap')
        self.assertEqual(files_of(target), before)
        tfo.install(stage, target)
        tfo.rollback(target)
        self.assertEqual(files_of(target), before)

    def test_kill_after_the_receipt_rolls_back_a_partial_delta_including_the_spawnable_file(self):
        stage, target, before = self.staged_copy()
        for name in ('verification.json', 'ce/types.xml', 'ce/cfgspawnabletypes.xml'):
            for partial in (0, 6):
                with self.subTest(name=name, partial=partial):
                    self.kill_install(stage, target, name, partial)
                    self.assertEqual(tfo.rollback(target), 'rolled_back')
                    self.assertEqual(files_of(target), before)

    def test_null_receipt_is_refused_not_recovered(self):
        stage, target, before = self.staged_copy()
        self.kill_install(stage, target, 'receipt.json')
        (target / tfo.MANAGED / 'receipt.json').write_bytes(b'null')
        (target / 'cfgeconomycore.xml').write_bytes(before['cfgeconomycore.xml'] + b'<!--operator edit-->')
        edited = files_of(target)
        with self.assertRaises(ValueError):
            tfo.rollback(target)
        self.assertEqual(files_of(target), edited)

    def test_an_install_in_the_shape_af885df_wrote_still_rolls_back(self):
        """The managed layout and receipt are unchanged: no staging leftovers, spawnable digest recognised."""
        stage, target, before = self.staged_copy()
        tfo.install(stage, target)
        managed = target / tfo.MANAGED
        names = {p.relative_to(managed).as_posix() for p in managed.rglob('*') if p.is_file()}
        self.assertEqual(names, {'core.backup', 'receipt.json', 'verification.json', 'ce/types.xml',
                                 'ce/cfgspawnabletypes.xml'})
        receipt = json.loads((managed / 'receipt.json').read_bytes())
        self.assertIn('spawnable_sha256', receipt)
        installed = files_of(target)
        (managed / 'ce/cfgspawnabletypes.xml').write_bytes(b'<spawnabletypes/>')
        with self.assertRaisesRegex(ValueError, 'spawnable.*drift'):
            tfo.rollback(target)
        (managed / 'ce/cfgspawnabletypes.xml').write_bytes((stage / 'ce/cfgspawnabletypes.xml').read_bytes())
        self.assertEqual(files_of(target), installed)
        self.assertEqual(tfo.rollback(target), 'rolled_back')
        self.assertEqual(files_of(target), before)

    def test_an_install_from_before_the_spawnable_file_still_rolls_back(self):
        stage, target, before = self.staged_copy()
        tfo.install(stage, target)
        managed = target / tfo.MANAGED
        receipt = json.loads((managed / 'receipt.json').read_bytes())
        del receipt['spawnable_sha256']
        (managed / 'receipt.json').write_bytes(economy.encode(receipt))
        (managed / 'ce/cfgspawnabletypes.xml').unlink()
        self.assertEqual(tfo.rollback(target), 'rolled_back')
        self.assertEqual(files_of(target), before)

    def test_missing_evidence_and_incomplete_receipts_are_refusals(self):
        stage, target, before = self.staged_copy()
        tfo.install(stage, target)
        managed = target / tfo.MANAGED
        for name in ('verification.json', 'ce/cfgspawnabletypes.xml'):
            saved = (managed / name).read_bytes()
            (managed / name).unlink()
            with self.assertRaises(economy.MissingEvidence):
                tfo.rollback(target)
            (managed / name).write_bytes(saved)
        full = json.loads((managed / 'receipt.json').read_bytes())
        (managed / 'ce/types.xml').write_bytes(b'operator data')
        for broken in ({k: v for k, v in full.items() if k != 'verification_sha256'},
                       {'before': full['before'], 'after': 'f' * 64, 'sources': full['sources']},
                       dict(full, spawnable_sha256='nothex'),
                       {k: v for k, v in full.items() if k != 'schema'}):
            (managed / 'receipt.json').write_bytes(economy.encode(broken))
            with self.assertRaises(ValueError):
                tfo.rollback(target)
            self.assertEqual((managed / 'ce/types.xml').read_bytes(), b'operator data')

    def test_install_and_rollback_are_byte_exact(self):
        stage = self.stage()
        target = Path(self.tmp.name) / 'copy'
        shutil.copytree(self.source, target)
        before = files_of(target)
        tfo.install(stage, target)
        core = (target / 'cfgeconomycore.xml').read_bytes()
        self.assertIn(b'<!--keep exactly-->', core)
        self.assertIn(b'hollow-country-tactical-flava/ce', core)
        self.assertTrue((target / 'hollow-country-tactical-flava/verification.json').is_file())
        self.assertEqual((target / 'db/types.xml').read_bytes(), before['db/types.xml'])
        with self.assertRaises(ValueError):
            tfo.install(stage, target)
        tfo.rollback(target)
        self.assertEqual(before, files_of(target))

    def test_composes_with_the_roster_and_snafu_and_requires_last_in_first_out_rollback(self):
        target = Path(self.tmp.name) / 'copy'
        shutil.copytree(self.source, target)
        before = files_of(target)
        firearms.write_delta(Path(self.tmp.name) / 'roster', firearms.generate(target, vanilla_roster()))
        firearms.install(Path(self.tmp.name) / 'roster', target)
        snafu_install = Path(self.tmp.name) / 'snafu-mod'
        snafu_fixture.build_install(snafu_install)
        snafu_allow = snafu_fixture.allowlist(*snafu_fixture.GOOD)
        snafu_report = snafu_optional.verify_install(snafu_install, snafu_allow)
        snafu_optional.write_delta(Path(self.tmp.name) / 'snafu', snafu_optional.generate(target, snafu_allow,
                                                                                        snafu_report))
        snafu_optional.install(Path(self.tmp.name) / 'snafu', target)
        tfo.write_delta(Path(self.tmp.name) / 'tf', tfo.generate(target, self.allow, self.report))
        tfo.install(Path(self.tmp.name) / 'tf', target)
        core = (target / 'cfgeconomycore.xml').read_bytes()
        for folder in (b'hollow-country/ce', b'hollow-country-snafu/ce', b'hollow-country-tactical-flava/ce'):
            self.assertIn(folder, core)
        with self.assertRaises(ValueError):
            snafu_optional.rollback(target)
        with self.assertRaises(ValueError):
            firearms.rollback(target)
        tfo.rollback(target)
        with self.assertRaises(ValueError):
            firearms.rollback(target)
        snafu_optional.rollback(target)
        firearms.rollback(target)
        self.assertEqual(before, files_of(target))

    def test_installs_on_the_roster_alone_but_refuses_unknown_ce_extensions(self):
        target = Path(self.tmp.name) / 'copy'
        shutil.copytree(self.source, target)
        firearms.write_delta(Path(self.tmp.name) / 'roster', firearms.generate(target, vanilla_roster()))
        firearms.install(Path(self.tmp.name) / 'roster', target)
        stage = self.stage(source=target, name='tf')
        core = (target / 'cfgeconomycore.xml').read_bytes()
        (target / 'cfgeconomycore.xml').write_bytes(core.replace(
            b'</economycore>', b'<ce folder="someone-else/ce"><file name="types.xml" type="types"/></ce></economycore>'))
        with self.assertRaises(ValueError):
            tfo.install(stage, target)
        (target / 'cfgeconomycore.xml').write_bytes(core)
        tfo.install(stage, target)
        tfo.rollback(target)
        self.assertEqual((target / 'cfgeconomycore.xml').read_bytes(), core)

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
        tfo.rollback(target)
        self.assertEqual((target / 'cfgeconomycore.xml').read_bytes(), backup)
        self.assertFalse(managed.exists())

    def test_refuses_steam_path_tamper_stock_drift_symlinks_and_wrong_delta_kind(self):
        stage = self.stage()
        with self.assertRaises(ValueError):
            tfo.install(stage, Path('/mnt/g/SteamLibrary/steamapps/common/DayZServer/mpmissions/x'))
        target = Path(self.tmp.name) / 'copy'
        shutil.copytree(self.source, target)
        (target / 'db/types.xml').write_text('<types/>')
        with self.assertRaises(ValueError):
            tfo.install(stage, target)
        link = Path(self.tmp.name) / 'linked'
        link.symlink_to(self.source)
        with self.assertRaises(ValueError):
            tfo.install(stage, link)
        snafu_stage = Path(self.tmp.name) / 'snafu'
        snafu_install = Path(self.tmp.name) / 'snafu-mod'
        snafu_fixture.build_install(snafu_install)
        snafu_allow = snafu_fixture.allowlist(*snafu_fixture.GOOD)
        snafu_optional.write_delta(snafu_stage, snafu_optional.generate(
            self.source, snafu_allow, snafu_optional.verify_install(snafu_install, snafu_allow)))
        fresh = Path(self.tmp.name) / 'fresh'
        shutil.copytree(self.source, fresh)
        with self.assertRaises(ValueError):
            tfo.install(snafu_stage, fresh)

    def test_install_refuses_a_delta_that_redefines_stock_types(self):
        stage = self.stage()
        target = Path(self.tmp.name) / 'copy'
        shutil.copytree(self.source, target)
        types = (stage / 'ce/types.xml').read_text().replace('SynRifle', 'SynthMag')
        (stage / 'ce/types.xml').write_text(types)
        manifest = json.loads((stage / 'delta-manifest.json').read_text())
        manifest['files']['ce/types.xml'] = economy.sha(types.encode())
        (stage / 'delta-manifest.json').write_bytes(economy.encode(manifest))
        with self.assertRaises(ValueError):
            tfo.install(stage, target)


class CommittedAllowlist(unittest.TestCase):
    KEEP = {
        'TF_AK74M': (4, 2), 'TF_M1A_Black': (5, 2), 'TF_M14_STD': (3, 1), 'TF_VPO190': (8, 4),
        'TF_MP443': (8, 4), 'TF_M24': (2, 1), 'TF_ElcanSpecterDROptic_Black': (3, 1),
        'TF_ElcanSpecterDROptic_FDE': (2, 1), 'TF_ElcanSpecterDR_6xOptic_Black': (2, 1),
        'TF_ElcanSpecterDR_6xOptic_FDE': (1, 0), 'TF_Mag_M14_10Rnd': (12, 6), 'TF_Mag_M14_20Rnd': (6, 3),
        'TF_Mag_VPO190_4Rnd': (10, 5), 'TF_Mag_MP443_18Rnd': (8, 4), 'TF_Mag_AK74_Bakelit30Rnd': (8, 4),
        'TF_M14_Adapter': (0, 0)}

    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(ALLOWLIST.read_text())
        cls.rows = {e['class']: e for e in cls.data['entries']}

    def test_valid_and_declared_unverified(self):
        tfo.validate_allowlist(self.data)
        self.assertEqual(self.data['status'], 'unverified')
        self.assertEqual(self.data['workshop_id'], '2646817942')

    def test_rights_inventory_records_the_unresolved_terms(self):
        rights = self.data['rights']
        self.assertEqual((rights['license'], rights['redistribution'], rights['dependency_use'], rights['review']),
                         ('none-recorded', 'none', 'unstated', 'pending'))
        self.assertTrue(all(u.startswith('https://') for u in rights['urls']))
        self.assertRegex(rights['terms_sha256'], r'^[0-9a-f]{64}$')
        self.assertEqual(rights['terms_file'], 'extra files/readme.txt')
        self.assertTrue(any('licence file' in n or 'license file' in n for n in rights['notes']))

    def test_expanded_pack_meets_owner_test_abundance(self):
        weapons = [e for e in self.rows.values() if e['kind'] == 'weapon']
        self.assertGreaterEqual(len(weapons), 50)
        self.assertGreaterEqual(sum(e['set']['nominal'] for e in weapons), 250)
        for e in weapons:
            self.assertEqual(e['set']['min'], e['set']['nominal'] // 2)
        self.assertEqual(self.data['test_abundance_multiplier'], 1.0)

    def test_snafu_lifetime_and_restock_convention(self):
        for name, e in self.rows.items():
            expected = (14400, 0) if e['kind'] != 'weapon' else (7200, 1800)
            self.assertEqual((e['set']['lifetime'], e['set']['restock']), expected, name)

    def test_modern_rifles_and_civilian_picks_use_owner_tiers(self):
        for name, e in self.rows.items():
            if e['kind'] != 'weapon':
                continue
            if e['role'] == 'modern':
                self.assertEqual(e['usage'], ['Military'], name)
                self.assertEqual(e['value'], ['Tier3', 'Tier4'], name)
            elif e['role'] == 'civilian':
                self.assertIn('Town', e['usage'], name)
                self.assertIn('Village', e['usage'], name)
            else:
                self.assertEqual(set(e['usage']), {'Military', 'Police'}, name)
                self.assertEqual(e['value'], ['Tier2', 'Tier3'], name)

    def test_every_spawning_weapon_has_ammo_and_spawning_magazines(self):
        for name, e in self.rows.items():
            if e['kind'] == 'weapon' and e['set']['nominal']:
                self.assertTrue(e['vanilla_ammo'], name)
                for m in e['magazines']:
                    self.assertGreater(self.rows[m]['set']['nominal'], 0, (name, m))

    def test_m14_keeps_verified_native_optic_adapter(self):
        self.assertEqual(self.rows['TF_M14_STD']['optic_requires'], ['TF_M14_Adapter'])
        adapter = self.rows['TF_M14_Adapter']
        self.assertEqual((adapter['kind'], adapter['slot']), ('attachment', 'weaponDMRAdapter'))
        self.assertIn('TF_M14_STD', adapter['fits'])
        for name in ('TF_ElcanSpecterDROptic_Black', 'TF_ElcanSpecterDR_6xOptic_FDE'):
            self.assertNotIn('TF_M24', self.rows[name]['fits'])
            self.assertEqual(self.rows[name]['slot'], 'weaponOptics')

    def test_excluded_definitions_remain_traceable_and_unselected(self):
        listed = {x['group'] for x in self.data['excluded']}
        self.assertFalse(listed & set(self.rows))
        self.assertTrue(all(x['reason'].strip() for x in self.data['excluded']))
        self.assertIn('M4A1', listed)  # native patch, not a new pack firearm
        self.assertIn('TF_Mag_AK74_60Rnd', listed)  # duplicate config definitions

    def test_no_overlap_with_the_roster_or_snafu_subsets(self):
        snafu = {e['class'] for e in json.loads((REPO / 'tools/package/snafu_allowlist.json').read_text())['entries']}
        self.assertFalse(snafu & set(self.rows))
        roster = json.loads((REPO / 'tools/package/firearms_roster.json').read_text()) \
            if (REPO / 'tools/package/firearms_roster.json').exists() else {'entries': []}
        self.assertFalse({e['class'] for e in roster['entries']} & set(self.rows))


class FirearmsDocument(unittest.TestCase):
    def test_section_records_terms_script_risks_collisions_and_local_checks(self):
        text = FIREARMS_DOC.read_text()
        self.assertIn('Tactical Flava (optional)', text)
        section = text[text.index('Tactical Flava (optional)'):]
        for needle in ('2646817942', 'rights review pending', 'no licence file', 'M4A1', 'BUIS', 'carry handle',
                       'Mosin', 'UAToggleBipod', 'EEKilled', 'RegisterActions', 'weaponDMRAdapter', 'TF_M14_Adapter',
                       'verification.json', 'MDF_PHOSPHORUS', 'NTF_TFPOISONED', 'rolls back', 'never repack'):
            self.assertIn(needle, section, needle)


@unittest.skipIf(bool(os.environ.get('GITHUB_ACTIONS')), 'CI runners carry no Workshop item or game install')
@unittest.skipUnless(REAL.is_dir() and VANILLA_ADDONS.is_dir(), 'Tactical Flava or vanilla DayZ not installed')
class RealInstall(unittest.TestCase):
    """Static evidence only: this reads the operator's installed copy and never proves runtime behaviour."""

    def test_committed_allowlist_verifies_against_the_installed_copy(self):
        data = json.loads(ALLOWLIST.read_text())
        vanilla = tfo.load_vanilla(VANILLA_ADDONS)
        report = tfo.verify_install(REAL, data, vanilla=vanilla)
        bad = {k: v['reasons'] for k, v in report['classes'].items() if v['status'] != 'verified'}
        self.assertEqual(bad, {})
        self.assertEqual(report['install']['problems'], [])
        self.assertEqual(report['status'], 'verified')
        self.assertEqual(len(report['classes']), len(data['entries']))
        # SYNTHETIC mission budgets; only the allowlisted compatibility evidence is real/read-only.
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'mission'
            source.mkdir()
            mission(source)
            stock = ET.parse(source / 'db/types.xml').getroot()
            existing = {n.get('name') for n in stock}
            ammo = {a for e in data['entries'] if e['kind'] == 'weapon' for a in e['vanilla_ammo']}
            ammo |= {m for row in report['classes'].values() for m in row.get('compatible_magazines', [])}
            for name in sorted(ammo - existing - {e['class'] for e in data['entries']}):
                stock.append(ET.fromstring(stock_entry(name, 50, 30, 14400, 0, ['Military'], ['Tier3'])))
            (source / 'db/types.xml').write_bytes(ET.tostring(stock))
            files = tfo.generate(source, data, report)
            spawnable = ET.fromstring(files['ce/cfgspawnabletypes.xml'])
            adapter = spawnable.find("type[@name='TF_M14_STD']/attachments/item")
            self.assertIsNotNone(adapter)
            self.assertEqual(adapter.attrib, {'name': 'TF_M14_Adapter', 'chance': '1.00'})


class BaseAddonStaysIndependent(unittest.TestCase):
    def test_base_addon_and_default_mission_never_mention_the_optional_item(self):
        names = [e['class'].lower().encode() for e in json.loads(ALLOWLIST.read_text())['entries']]
        hits = []
        for folder in ('mods', 'mission', 'config'):
            for path in (REPO / folder).rglob('*'):
                if path.is_file() and path.suffix.lower() in {'.cpp', '.c', '.hpp', '.xml', '.json', '.md', '.txt'} \
                        and path.stat().st_size < 4_000_000:
                    data = path.read_bytes().lower()
                    if b'tactical' in data and b'flava' in data or b'2646817942' in data \
                            or any(n in data for n in names):
                        hits.append(path.relative_to(REPO).as_posix())
        self.assertEqual(hits, [])

    def test_core_tooling_does_not_import_the_optional_module(self):
        for name in ('economy.py', 'firearms.py', 'pbo.py', 'snafu_optional.py'):
            path = REPO / 'tools/package' / name
            if path.exists():
                self.assertNotIn('tactical_flava', path.read_text().lower(), name)

    def test_no_workshop_assets_are_in_the_repo(self):
        bad = []
        for folder in ('tools', 'docs', 'mods', 'mission', 'tests', 'config'):
            for path in (REPO / folder).rglob('*'):
                name = path.name.lower()
                if path.is_file() and (any(name.endswith(s) for s in ('.p3d', '.paa', '.rvmat', '.bisign', '.pbo'))
                                       or ('tactical' in name and name.endswith(('.xml', '.rar', '.pdf', '.bikey')))):
                    bad.append(path.relative_to(REPO).as_posix())
        self.assertEqual(bad, [])


if __name__ == '__main__':
    unittest.main()
