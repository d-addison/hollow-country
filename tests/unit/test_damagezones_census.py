"""Synthetic rapified configs only; offline, never evidence of engine behaviour."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tests.unit.test_pbo_config import klass, pbo, rap
from tools.audit import damagezones_census as census


def zone(parent='', hp=None, **fields):
    if hp is not None:
        fields['Health'] = klass('', hitpoints=hp, transferToGlobalCoef=1.0)
    return klass(parent, **fields)


def zones(**named):
    return {'DamageSystem': klass('', DamageZones=klass('', **named))}


def config(**vehicles):
    return rap(klass('', CfgVehicles=klass('', **vehicles)))


# Vanilla-shaped: RightLeg inherits LeftLeg, a boss redeclares every leg with own hit points.
VANILLA = config(
    DayZInfected=klass('', scope=0),
    ZombieBase=klass('DayZInfected', scope=0, **zones(
        Head=zone(hp=30), LeftLeg=zone(hp=100), RightLeg=zone('LeftLeg'), Odd=zone(hp=5))),
    ZmbM_A=klass('ZombieBase', scope=2),
    ZmbM_B=klass('ZmbM_A', scope=2),
    ZmbM_Boss=klass('ZombieBase', scope=2, **zones(LeftLeg=zone('LeftLeg', hp=900), RightLeg=zone('RightLeg', hp=800))),
    ZmbM_Hidden=klass('ZombieBase', scope=1),
    SurvivorBase=klass('', scope=0, **zones(Head=zone(hp=33), LeftLeg=zone(hp=125), RightLeg=zone('LeftLeg'))),
    SurvivorM_A=klass('SurvivorBase', scope=2),
    PlainItem=klass('', scope=2),
)
# Later PBO patches: LeftLeg hit points on the shared base; HC posed variant; AI actor.
PATCH = config(
    ZombieBase=klass('DayZInfected', **zones(LeftLeg=zone(hp=50))),
    HC_ZmbM_Posed=klass('ZmbM_A', scope=2),
    eAI_Actor=klass('SurvivorM_A', scope=2),
)


class DamageZonesCensus(unittest.TestCase):
    def classes(self, *configs):
        with tempfile.TemporaryDirectory() as folder:
            for i, data in enumerate(configs):
                (Path(folder) / f'a{i}.pbo').write_bytes(pbo({'config.bin': data}))
            return census.scan([Path(folder)])

    def test_merge_patch_hitpoints_reach_inheriting_right_leg_but_not_redeclared(self):
        classes, stats = self.classes(VANILLA, PATCH)
        self.assertEqual(stats['pbos'], 2)
        self.assertEqual(stats['config_unreadable'], 0)
        self.assertEqual(census.zone_hp(classes, 'zmbm_b', 'leftleg'), 50)
        self.assertEqual(census.zone_hp(classes, 'zmbm_b', 'rightleg'), 50)
        self.assertEqual(census.zone_link(classes, 'zmbm_b', 'rightleg'), 'leftleg')
        self.assertEqual(census.zone_hp(classes, 'zmbm_boss', 'rightleg'), 800)
        self.assertIsNone(census.zone_link(classes, 'zmbm_boss', 'leftleg'))  # same-name override

    def test_family_counts_use_public_classes_only(self):
        families = census.census(self.classes(VANILLA, PATCH)[0])
        vanilla = families['infected_vanilla']
        self.assertEqual((vanilla['classes'], vanilla['public']), (5, 3))  # base, A, B, boss, hidden; base/hidden are not scope 2
        self.assertEqual(families['infected_hc']['public'], 1)
        self.assertEqual(families['eai_actor']['public'], 1)
        self.assertEqual(families['survivor_vanilla']['public'], 1)
        self.assertEqual(vanilla['own_zone_overrides'], 1)
        self.assertEqual(vanilla['zone_names_outside_vocabulary'], 1)
        leg = vanilla['right_leg']
        self.assertEqual(leg['present'], vanilla['public'])
        # The boss's same-name override keeps the inherited link while setting its own hit points.
        self.assertEqual(leg['inherits_left_leg'], vanilla['public'])
        self.assertEqual(leg['hitpoints_equal_left'], vanilla['public'] - 1)
        self.assertEqual(leg['hitpoints_differ_from_left'], 1)
        self.assertEqual(vanilla['zones']['LeftLeg']['hitpoints'], {'50': 2, '900': 1})

    def test_unresolved_hitpoints_and_cyclic_links_are_bounded(self):
        data = config(Base=klass('', scope=2, **zones(RightLeg=zone('LeftLeg'), LeftLeg=zone('RightLeg'))),
                      ZombieBase=klass('', scope=2, **zones(Head=zone())))
        classes, _ = self.classes(data)
        self.assertIsNone(census.zone_hp(classes, 'base', 'rightleg'))
        families = census.census(classes)
        self.assertEqual(families['infected_vanilla']['zones']['Head']['hitpoints'], {'unresolved': 1})

    def test_report_has_counts_and_vocabulary_only(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'v.pbo').write_bytes(pbo({'config.bin': VANILLA}))
            out = Path(folder) / 'out.json'
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = census.main(['--addons', folder, '--report', str(out)])
            text = out.read_text()
            self.assertEqual(code, 0)
            self.assertEqual({s['reason'] for s in json.loads(text)['skipped']},
                             {'HC_INFECTED_NOT_INSTALLED', 'EAI_ACTORS_NOT_INSTALLED'})
            for private in ('ZmbM_A', 'Boss', 'SurvivorM_A', 'Odd', folder):
                self.assertNotIn(private, text + output.getvalue())
            self.assertEqual(census.main(['--addons', folder, '--report', str(out), '--require-installed']), 1)

    def test_missing_folder_skips_and_strict_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'r.json'
            args = ['--addons', str(Path(folder) / 'absent'), '--report', str(out)]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(census.main(args), 0)
                self.assertEqual(census.main(args + ['--require-installed']), 1)
            self.assertEqual(json.loads(out.read_text())['skipped'], [{'reason': 'ADDONS_UNAVAILABLE'}])
            self.assertNotIn(folder, out.read_text())

    def test_unreadable_config_is_counted_and_never_echoed(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'bad.pbo').write_bytes(pbo({'config.bin': b'garbage-private'}))
            out = Path(folder) / 'r.json'
            with contextlib.redirect_stdout(io.StringIO()) as output:
                census.main(['--addons', folder, '--report', str(out)])
            self.assertEqual(json.loads(out.read_text())['sources']['config_unreadable'], 1)
            self.assertNotIn('garbage-private', out.read_text() + output.getvalue())


if __name__ == '__main__':
    unittest.main()
