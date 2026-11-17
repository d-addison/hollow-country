"""Synthetic firearm census fixtures. Every class and number here is invented.

Offline classification is static-file evidence only; it never establishes in-game spawning.
"""
import json
from pathlib import Path
import tempfile
import unittest

from tools.audit import firearm_census as census


def cls(parent, scope=None, **extra):
    row = {'parent': parent, 'scope': scope}
    row.update(extra)
    return row


WEAPONS = {
    'Weapon_Base': cls(None, 0),
    'Rifle_Base': cls('Weapon_Base', 0),
    'Pistol_Base': cls('Weapon_Base', 0),
    'Shotgun_Base': cls('Weapon_Base', 0),
    'Spawny': cls('Rifle_Base', 2, model='\\dz\\w\\spawny.p3d', magazines=['Mag_Ok'],
                  handAnim=['Idle', 'dz\\w\\anim\\spawny.rtm']),
    'Spawny_Black': cls('Spawny'),          # inherits scope 2
    'ZeroNom': cls('Rifle_Base', 2, model='\\dz\\w\\zero.p3d', magazines=['Mag_Ok']),
    'NotInTypes': cls('Rifle_Base', 2, model='\\dz\\w\\nit.p3d', magazines=['Mag_Ok']),
    'CrateOnly': cls('Pistol_Base', 2, model='\\dz\\w\\crate.p3d', magazines=['Mag_Ok']),
    'ZombiePocket': cls('Pistol_Base', 2, model='\\dz\\w\\zp.p3d', magazines=['Mag_Ok']),
    'Protected': cls('Rifle_Base', 1, model='\\dz\\w\\p.p3d'),
    'Mystery': cls('MissingParent'),
    'Unfinished': cls('Shotgun_Base', 2, model='\\dz\\w\\gone.p3d',
                      magazines=['Mag_Missing', 'Mag_Hidden'],
                      handAnim=['Idle', 'dz\\w\\anim\\gone.rtm']),
    'NoUsage': cls('Rifle_Base', 2, model='\\dz\\w\\nu.p3d', magazines=['Mag_Ok']),
}
MAGAZINES = {
    'Mag_Ok': cls(None, 2, ammo='Bullet_Ok'),
    'Mag_Hidden': cls(None, 0, ammo='Bullet_Ok'),
}
AMMO = {'Bullet_Ok': cls(None, 2)}
MODELS = {'dz\\w\\spawny.p3d', 'dz\\w\\zero.p3d', 'dz\\w\\nit.p3d', 'dz\\w\\crate.p3d',
          'dz\\w\\zp.p3d', 'dz\\w\\p.p3d', 'dz\\w\\nu.p3d'}
ANIMS = {'dz\\w\\anim\\spawny.rtm'}


def item(name, nominal, usage=('Military',), value=('Tier3',), **flags):
    usage_xml = ''.join(f'<usage name="{u}"/>' for u in usage)
    value_xml = ''.join(f'<value name="{v}"/>' for v in value)
    return (f'<type name="{name}"><nominal>{nominal}</nominal><lifetime>3600</lifetime>'
            f'<restock>0</restock><min>{max(0, nominal - 1)}</min><quantmin>-1</quantmin>'
            f'<quantmax>-1</quantmax><cost>100</cost><category name="weapons"/>'
            f'{usage_xml}{value_xml}</type>')


MISSION = {
    'db/types.xml': ('<types>' + item('Spawny', 6) + item('Spawny_Black', 0, usage=(), value=())
                     + item('ZeroNom', 0) + item('CrateOnly', 0) + item('ZombiePocket', 0)
                     + item('Unfinished', 2) + item('NoUsage', 3, usage=(), value=())
                     + item('Mag_Ok', 20) + item('Protected', 5)
                     + '</types>').encode(),
    'cfgspawnabletypes.xml': b'''<spawnabletypes>
        <type name="Wreck_Test"><cargo chance="0.5"><item name="CrateOnly" chance="0.2"/></cargo></type>
        <type name="ZmbF_Test"><attachments preset="pocketGuns" chance="0.3"/></type>
        <type name="Hoarder_Test"><hoarder/></type></spawnabletypes>''',
    'cfgrandompresets.xml': b'''<randompresets>
        <cargo name="pocketGuns" chance="0.1"><item name="ZombiePocket" chance="0.1"/></cargo>
        <attachments name="unused" chance="0.1"><item name="ZeroNom" chance="0.1"/></attachments>
        </randompresets>''',
    'cfgeventgroups.xml': b'''<eventgroupdef><group name="G"><child type="Wreck_Test" x="0" z="0"/></group></eventgroupdef>''',
    'db/events.xml': b'''<events><event name="StaticTest"><nominal>3</nominal><active>1</active>
        <children><child type="Wreck_Test" min="1" max="1" lootmin="1" lootmax="2"/></children></event></events>''',
    'cfgeventspawns.xml': b'''<eventposdef><event name="StaticTest"><pos x="1" z="2" a="3"/></event></eventposdef>''',
}


def build(**override):
    mission = dict(MISSION, **override)
    return census.build_census(WEAPONS, MAGAZINES, AMMO, MODELS, ANIMS, mission)


class Classification(unittest.TestCase):
    def setUp(self):
        self.result = build()
        self.by = self.result['weapons']

    def test_every_documented_class_is_assigned_with_evidence(self):
        got = {name: row['classification'] for name, row in self.by.items()}
        self.assertEqual(got, {
            'Spawny': 'spawning',
            'Spawny_Black': 'nominal-zero',
            'ZeroNom': 'nominal-zero',
            'NotInTypes': 'missing-from-types',
            'CrateOnly': 'event-only',
            'ZombiePocket': 'spawning',
            'Protected': 'scope-not-public',
            'Mystery': 'unknown',
            'Unfinished': 'spawning',
            'NoUsage': 'unknown',
        })
        self.assertTrue(all(row['evidence'] for row in self.by.values()))

    def test_abstract_scope_zero_bases_are_counted_not_reported(self):
        for base in ('Weapon_Base', 'Rifle_Base', 'Pistol_Base', 'Shotgun_Base'):
            self.assertNotIn(base, self.by)
        self.assertEqual(self.result['summary']['abstract_bases'], 4)
        self.assertEqual(self.by['Spawny_Black']['scope'], 2)  # inherited scope is resolved

    def test_types_budget_and_reference_sources_are_recorded(self):
        spawny = self.by['Spawny']
        self.assertEqual(spawny['types'], {'nominal': 6, 'min': 5, 'lifetime': 3600, 'restock': 0,
                                           'usage': ['Military'], 'value': ['Tier3']})
        self.assertEqual(self.by['CrateOnly']['references']['event_carriers'], ['Wreck_Test'])
        self.assertEqual(self.by['ZombiePocket']['references']['world_carriers'], ['ZmbF_Test'])
        self.assertEqual(self.by['ZombiePocket']['references']['presets'], ['pocketGuns'])
        self.assertEqual(self.by['ZeroNom']['references']['presets'], ['unused'])
        self.assertEqual(self.by['ZeroNom']['references']['world_carriers'], [])
        self.assertIsNone(self.by['NotInTypes']['types'])

    def test_incomplete_asset_flags_are_explicit_not_silent(self):
        flags = self.by['Unfinished']['completeness']
        self.assertFalse(flags['model_present'])
        self.assertEqual(flags['anim_missing'], ['dz\\w\\anim\\gone.rtm'])
        self.assertEqual(flags['magazines_missing'], ['Mag_Missing'])
        self.assertEqual(flags['magazines_not_public'], ['Mag_Hidden'])
        self.assertTrue(flags['suspect_unfinished'])
        self.assertFalse(self.by['Spawny']['completeness']['suspect_unfinished'])
        self.assertTrue(self.by['Spawny']['completeness']['model_present'])

    def test_magazines_record_types_and_ammo_presence(self):
        mags = {m['class']: m for m in self.by['Spawny']['magazines']}
        self.assertEqual(mags['Mag_Ok'], {'class': 'Mag_Ok', 'scope': 2, 'in_types': True,
                                           'ammo': 'Bullet_Ok', 'ammo_present': True})

    def test_summary_counts_and_limits_text(self):
        summary = self.result['summary']
        self.assertEqual(summary['by_classification']['spawning'], 3)
        self.assertEqual(summary['weapon_classes'], 10)
        self.assertIn('static file evidence', self.result['limitations'][0].lower())

    def test_families_follow_ancestry(self):
        self.assertEqual(self.by['Spawny']['family'], 'rifle')
        self.assertEqual(self.by['CrateOnly']['family'], 'pistol')
        self.assertEqual(self.by['Unfinished']['family'], 'shotgun')

    def test_event_only_is_not_assigned_when_world_carrier_exists(self):
        mission = dict(MISSION)
        mission['cfgspawnabletypes.xml'] = MISSION['cfgspawnabletypes.xml'].replace(
            b'<hoarder/>', b'<cargo><item name="CrateOnly"/></cargo>')
        result = census.build_census(WEAPONS, MAGAZINES, AMMO, MODELS, ANIMS, mission)
        self.assertEqual(result['weapons']['CrateOnly']['classification'], 'spawning')

    def test_deterministic(self):
        self.assertEqual(json.dumps(build(), sort_keys=True), json.dumps(build(), sort_keys=True))


class InputRefusal(unittest.TestCase):
    def test_hostile_or_malformed_xml_is_refused(self):
        for key, bad in (('db/types.xml', b'<!DOCTYPE x><types/>'), ('db/types.xml', b'<types>'),
                         ('cfgspawnabletypes.xml', b'<wrong/>')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                build(**{key: bad})

    def test_missing_types_is_refused(self):
        mission = {k: v for k, v in MISSION.items() if k != 'db/types.xml'}
        with self.assertRaises(ValueError):
            census.build_census(WEAPONS, MAGAZINES, AMMO, MODELS, ANIMS, mission)


class OutputPlacement(unittest.TestCase):
    def test_output_inside_a_git_checkout_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t) / 'repo'
            (repo / '.git').mkdir(parents=True)
            with self.assertRaises(ValueError):
                census.check_output_dir(repo / 'out')
            with self.assertRaises(ValueError):
                census.check_output_dir(repo / 'a' / 'b' / 'out')
            census.check_output_dir(Path(t) / 'elsewhere')  # no repo above: allowed

    def test_existing_output_is_not_overwritten_and_files_are_written(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / 'census'
            census.write_census(out, build())
            self.assertEqual(sorted(p.name for p in out.iterdir()),
                             ['census.json', 'summary.txt'])
            with self.assertRaises(ValueError):
                census.write_census(out, build())


class ResolvedFromPboConfigs(unittest.TestCase):
    def test_ancestry_scope_and_family_helpers(self):
        self.assertEqual(census.family(['A', 'Pistol_Base', 'Weapon_Base']), 'pistol')
        self.assertEqual(census.family(['A', 'Archery_Base', 'Weapon_Base']), 'archery')
        self.assertEqual(census.family(['A', 'Weapon_Base']), 'other')
        self.assertEqual(census.family(['A', 'Shotgun_Base', 'Weapon_Base']), 'shotgun')
        self.assertEqual(census.family(['A', 'Launcher_Base', 'Weapon_Base']), 'launcher')
        self.assertEqual(census.family(['A', 'Rifle_Base', 'Weapon_Base']), 'rifle')
        self.assertEqual(census.family(['A', 'NonlethalCore', 'Weapon_Base']), 'nonlethal')


class WorkbookCrossCheck(unittest.TestCase):
    def test_native_hidden_rows_are_compared_without_overriding_the_config_read(self):
        workbook = {'classes': [
            {'root': 'CfgWeapons', 'name': 'Protected', 'review_status': 'retain'},
            {'root': 'CfgWeapons', 'name': 'Spawny', 'review_status': 'retain'},
            {'root': 'CfgWeapons', 'name': 'Hidden', 'review_status': 'excluded-definition'},
            {'root': 'CfgWeapons', 'name': 'NativeOnly', 'review_status': 'retain'},
            {'root': 'CfgVehicles', 'name': 'Ignored', 'review_status': 'retain'}]}
        check = census.cross_check_workbook(build(), workbook)
        self.assertEqual(check['native_weapon_rows'], 4)
        self.assertEqual(check['native_only'], ['NativeOnly'])
        self.assertEqual(check['native_hidden_not_in_census'], ['Hidden'])
        self.assertEqual(check['native_retained_but_file_scope_not_public'], ['Protected'])
        self.assertEqual(check['status'], 'file-read-authoritative-native-is-cross-check')


class LoadingAddons(unittest.TestCase):
    def test_pbo_configs_models_and_anims_are_merged_first_seen(self):
        try:
            from .test_pbo_config import rap, pbo, klass
        except ImportError:
            from test_pbo_config import rap, pbo, klass
        weapons = klass('', CfgWeapons=klass('', Weapon_Base=klass('', scope=0),
                                              Hunter=klass('Weapon_Base', scope=2,
                                                           model='\\dz\\w\\hunter.p3d')),
                        CfgMagazines=klass('', M=klass('', scope=2, ammo='B')),
                        CfgAmmo=klass('', B=klass('', scope=2)))
        dup = klass('', CfgWeapons=klass('', Hunter=klass('Other', scope=1),
                                          Late=klass('Weapon_Base', scope=2)))
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / 'a_weapons.pbo').write_bytes(pbo({'config.bin': rap(weapons), 'hunter.p3d': b'M',
                                                      'anim\\x.rtm': b'1'}, prefix='dz\\w'))
            (root / 'b_weapons.pbo').write_bytes(pbo({'config.bin': rap(dup)}, prefix='dz\\v'))
            (root / 'notes.txt').write_text('ignored')
            (root / 'sounds.ebo').write_bytes(b'encrypted, never parsed')
            data = census.load_addons([('server', root)])
        self.assertEqual(data['weapons']['Hunter']['scope'], 2)
        self.assertEqual(data['weapons']['Hunter']['parent'], 'Weapon_Base')
        self.assertIn('Late', data['weapons'])
        self.assertEqual(data['magazines']['M']['ammo'], 'B')
        self.assertIn('B', data['ammo'])
        self.assertIn('dz\\w\\hunter.p3d', data['models'])
        self.assertIn('dz\\w\\anim\\x.rtm', data['anims'])
        self.assertEqual(data['sources'][0]['pbo_count'], 2)
        self.assertEqual(data['sources'][0]['skipped'], ['sounds.ebo'])


if __name__ == '__main__':
    unittest.main()
