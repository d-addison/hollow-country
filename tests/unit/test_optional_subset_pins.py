"""HC-61 / #183: subset pins instead of whole-PBO pins; synthetic Workshop-shaped fixtures only.

A Workshop update that leaves the used subset's classes unchanged must still verify, a change in a pinned
class must report drift naming the class, and verify must not hash whole PBO files once the subset is pinned.
Nothing here reads a real Workshop item or establishes DayZ behaviour; runtime acceptance stays pending.

RED (before implementation), command:
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_optional_subset_pins -v
GREEN command and result are recorded in the commit message.
"""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.package import snafu_optional as sf, tactical_flava_optional as tf
from tests.unit import test_snafu_optional as sf_fixture
from tests.unit import test_tactical_flava_optional as tf_fixture
from tests.unit.test_pbo_config import klass, pbo, rap


def pinned(allow, report):
    """Pin the used subset the way an operator would after a first verify (synthetic policy)."""
    policy = {'schema': 1, 'members': [], 'family_budgets': [],
              'dependency_pins': [], 'class_pins': dict(report['subset_pins']),
              'aggregate_weapon_budget': {'nominal': 62, 'min': 31},
              'refusals': ['HC61_SUBSET_RUNTIME_PENDING']}
    for entry in allow['entries']:
        weight = 20 if entry['kind'] == 'ammo' else 1
        policy['members'].append({
            'class': entry['class'], 'family': entry['class'], 'unit_rounds': weight,
            'parts': [{'class': name, 'route': 'native-carrier'} for name in entry.get('optic_requires', [])]})
        policy['family_budgets'].append({
            'family': entry['class'], 'kind': entry['kind'] if entry['kind'] in sf.KINDS else 'magazine',
            **{field: entry['set'][field] * weight for field in ('nominal', 'min')}})
    out = copy.deepcopy(allow)
    out['hc61'] = policy
    return out


def sf_configs(extra=None, wood_ammo='SynAmmoA'):
    tree = sf_fixture.configs()
    weapons = {k: v for k, v in tree['CfgWeapons'].items() if k != '__parent__'}
    weapons['SynWood'] = klass('Rifle_Base', scope=2, model=sf_fixture.MODEL.format('wood'),
                               chamberableFrom=[wood_ammo])
    weapons.update(extra or {})
    tree['CfgWeapons'] = klass('', **weapons)
    return tree


def sf_rewrite(root, tree):
    members = {'Data/wood.p3d': b'x', 'Data/pistol.p3d': b'x', 'config.bin': rap(tree)}
    (root / 'Addons/Synth_Guns.pbo').write_bytes(pbo(members, prefix='Synth\\Guns'))


class SubsetPins(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_snafu_unrelated_update_passes_and_changed_class_names_the_drift(self):
        install = self.root / 'sf'
        sf_fixture.build_install(install)
        allow = sf_fixture.allowlist(*sf_fixture.GOOD)
        first = sf.verify_install(install, allow)
        self.assertEqual(first['status'], 'verified')
        self.assertEqual(set(first['subset_pins']), {e['class'] for e in allow['entries']})
        allow = pinned(allow, first)
        sf.validate_allowlist(allow)
        # Workshop update: a new unrelated class and different bytes, subset classes unchanged.
        sf_rewrite(install, sf_configs(extra={'SynUnrelated': klass('Rifle_Base', scope=2)}))
        update = sf.verify_install(install, allow)
        self.assertEqual(update['install']['problems'], [])
        self.assertEqual(update['status'], 'verified')
        # A pinned class changes: drift names exactly that class and verification is not trusted.
        sf_rewrite(install, sf_configs(wood_ammo='SynAmmoB'))
        drift = sf.verify_install(install, allow)
        self.assertEqual(drift['status'], 'unverified')
        self.assertIn('HC61_SUBSET_PIN_DRIFT:SynWood', drift['install']['problems'])
        self.assertEqual([p for p in drift['install']['problems'] if p.startswith('HC61_SUBSET_PIN_DRIFT')],
                         ['HC61_SUBSET_PIN_DRIFT:SynWood'])

    def test_snafu_subset_pins_skip_whole_pbo_hashing_and_generate_rechecks_pins(self):
        install = self.root / 'sf'
        sf_fixture.build_install(install)
        allow = sf_fixture.allowlist(*sf_fixture.GOOD)
        allow = pinned(allow, sf.verify_install(install, allow))
        with mock.patch.object(sf, '_pbo_sha256', side_effect=AssertionError('whole-PBO hash')):
            report = sf.verify_install(install, allow)
        self.assertEqual(report['status'], 'verified')
        self.assertTrue(all('sha256' not in row for row in report['install']['pbos']))
        stale = copy.deepcopy(report)
        stale['subset_pins']['SynWood'] = '0' * 64
        mission = self.root / 'mission'
        mission.mkdir()
        sf_fixture.patch_roster(self, self.root)
        tf_fixture.mission(mission)
        with self.assertRaisesRegex(ValueError, 'HC61_SUBSET_PIN_DRIFT:SynWood'):
            sf.generate(mission, allow, stale)

    def test_legacy_pbo_pins_still_pin_the_whole_file(self):
        install = self.root / 'sf'
        sf_fixture.build_install(install)
        allow = sf_fixture.allowlist(*sf_fixture.GOOD)
        report = sf.verify_install(install, allow)
        allow = pinned(allow, report)
        del allow['hc61']['class_pins']
        allow['hc61']['dependency_pins'] = [{k: row[k] for k in ('name', 'size', 'sha256')}
                                            for row in report['install']['pbos']]
        sf_rewrite(install, sf_configs(extra={'SynUnrelated': klass('Rifle_Base', scope=2)}))
        self.assertIn('HC61_DEPENDENCY_PIN_MISMATCH', sf.verify_install(install, allow)['install']['problems'])

    def test_tactical_flava_subset_pins_pass_unrelated_text_update_and_name_changes(self):
        install = self.root / 'tf'
        tf_fixture.build_install(install)
        allow = tf_fixture.allowlist(*tf_fixture.good())
        first = tf.verify_install(install, allow, vanilla=tf_fixture.VANILLA)
        self.assertEqual(first['status'], 'verified', first['install']['problems'])
        allow = pinned(allow, first)
        tf.validate_allowlist(allow)
        update = tf_fixture.TEXT_A.replace('class SynHidden: Rifle_Base { scope = 0;',
                                           'class SynHidden: Rifle_Base { scope = 0; ignored = 1;')
        self.assertNotEqual(update, tf_fixture.TEXT_A)
        (install / 'addons/syn_a.pbo').unlink()
        tf_fixture.build_install(self.root / 'tf2', text=update)
        os.replace(self.root / 'tf2/addons/syn_a.pbo', install / 'addons/syn_a.pbo')
        with mock.patch.object(sf, '_pbo_sha256', side_effect=AssertionError('whole-PBO hash')):
            ok = tf.verify_install(install, allow, vanilla=tf_fixture.VANILLA)
        self.assertEqual(ok['status'], 'verified', ok['install']['problems'])
        changed = tf_fixture.TEXT_A.replace('chamberableFrom[] = {"Ammo_545x39","Ammo_545x39Tracer"};',
                                            'chamberableFrom[] = {"Ammo_545x39"};')
        self.assertNotEqual(changed, tf_fixture.TEXT_A)
        tf_fixture.build_install(self.root / 'tf3', text=changed)
        os.replace(self.root / 'tf3/addons/syn_a.pbo', install / 'addons/syn_a.pbo')
        drift = tf.verify_install(install, allow, vanilla=tf_fixture.VANILLA)
        self.assertEqual(drift['status'], 'unverified')
        names = [p for p in drift['install']['problems'] if p.startswith('HC61_SUBSET_PIN_DRIFT')]
        self.assertIn('HC61_SUBSET_PIN_DRIFT:SynRifle', names)


if __name__ == '__main__':
    unittest.main()
