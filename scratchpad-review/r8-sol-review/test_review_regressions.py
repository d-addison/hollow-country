"""Synthetic behavioral expectations from owner rules; source is unchanged."""
import copy
import unittest
from tests.unit import test_taped_light_report as t
from tools.audit import taped_light_report as report


class OwnerRuleRegressions(unittest.TestCase):
    def build(self, proxies, lights=None):
        rows = [t.row('AK74', 'slot_host', t.gun_slots(False), lights or t.good_gun_lights(), proxies=proxies)]
        return report.build_report(t.classification([t.host('AK74', 'slot_host')]), t.observations(rows))

    def test_conflicting_light_aliases_outrank_an_attach_refusal(self):
        first = t.proxy()
        second = dict(copy.deepcopy(first), selection=first['selection'].replace('proxy:/', 'proxy:'),
                      cfg_exists=False, model='', inventory_slots=[], slot_count=0)
        for aliases in ([first, second], [second, first]):
            built = self.build(aliases, t.refusal_lights())
            self.assertEqual('pending', built['hosts'][0]['verdict'])
            self.assertEqual('pending', built['hosts'][0]['lights']['UniversalLight']['verdict'])

    def test_unrelated_alias_conflict_keeps_independent_light_evidence(self):
        first = t.proxy('/dz/weapons/attachments/magazine/mag_stanag', slots=('magazine',))
        second = dict(copy.deepcopy(first), selection=first['selection'].replace('proxy:/', 'proxy:'),
                      model='\\dz\\other.p3d')
        built = self.build([t.proxy(), first, second])
        self.assertEqual('pending', built['hosts'][0]['verdict'])
        self.assertEqual('server_qualified', built['hosts'][0]['lights']['UniversalLight']['verdict'])

    def test_slot_name_matching_is_exact(self):
        built = self.build([t.proxy(slots=('weaponflashlight',))])
        self.assertNotEqual('server_qualified', built['hosts'][0]['lights']['UniversalLight']['verdict'])

    def test_malformed_diagnostic_scalar_does_not_abort_the_report(self):
        observations = t.observations([t.row('AK74', 'slot_host', t.gun_slots(False), t.good_gun_lights(),
                                           proxies=[t.proxy()])])
        observations['spawn_control'] = None
        built = report.build_report(t.classification([t.host('AK74', 'slot_host')]), observations)
        self.assertEqual({'status': 'malformed'}, built['spawn_control'])
        self.assertEqual('server_qualified', built['hosts'][0]['verdict'])

    def test_coherent_aliases_collapse_without_inventing_an_extra_row(self):
        first = t.proxy()
        second = dict(copy.deepcopy(first), selection=first['selection'].replace('proxy:/', 'proxy:'))
        row = t.row('AK74', 'slot_host', t.gun_slots(False), t.good_gun_lights(), proxies=[first, second])
        parsed = report._proxies(row)
        self.assertEqual('ok', parsed[0])
        self.assertEqual(1, len(parsed[1]))

    def test_concrete_variants_never_take_the_parent_verdict(self):
        names = ['FNX45', 'FNX45_arrow', 'SCARH_Black', 'Glock19_Tan']
        cls = t.classification([t.host(name, 'slot_host') for name in names])
        for entry in cls['hosts'][1:]:
            entry['ancestors'] = ['FNX45']
        obs = t.observations([t.row('FNX45', 'slot_host', t.gun_slots(), t.good_gun_lights())])
        built = report.build_report(cls, obs)
        self.assertEqual('server_qualified', t.by_class(built, 'FNX45')['verdict'])
        for name in names[1:]:
            self.assertEqual(('pending', ['no_probe_row']),
                             (t.by_class(built, name)['verdict'], t.by_class(built, name)['reasons']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
