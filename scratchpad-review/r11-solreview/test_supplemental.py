"""Explicit synthetic r11 fixtures: report logic only, no runtime claims."""
import copy
import importlib.util
import itertools
import json
from pathlib import Path
import unittest

from tests.unit import test_taped_light_report as t
from tools.audit import taped_light_report as report

OUT = Path(__file__).resolve().parent


def fixture(entries, selection=False, refused=False, prereq=None, variant=None):
    raw = t.row('AK74', 'slot_host', t.gun_slots(selection),
                t.refusal_lights() if refused else t.good_gun_lights(),
                prereq=prereq, prereq_variant=variant, proxies=copy.deepcopy(list(entries)))
    return t.classification([t.host('AK74', 'slot_host')]), t.observations([raw])


def result(cls, obs, module=report):
    return module.build_report(cls, obs)['hosts'][0]


def pair(record):
    return record['lights']['UniversalLight']['verdict']


class SupplementalTests(unittest.TestCase):
    def test_conflicts_survive_all_sibling_orders_and_attach_routes(self):
        a = t.proxy()
        b = dict(copy.deepcopy(a), cfg_exists=False, model='', inventory_slots=[], slot_count=0)
        legacy = t.proxy('/dz/other/legacy', cfg_class='Proxy/dz/other/legacy', exists=False, res_selection='')
        missing_model = t.proxy('/dz/other/missing'); del missing_model['model']
        malformed_res = t.proxy('/dz/other/res'); malformed_res['res_lods'][0]['name'] = '2.000'
        siblings = [legacy, None, dict(t.proxy(), selection='bad'),
                    dict(t.proxy('/dz/other/class'), cfg_class='ProxyWrong'), missing_model, malformed_res]
        routes = [dict(), dict(selection=True), dict(refused=True),
                  dict(refused=True, prereq=[]),
                  dict(refused=True, prereq=t.prereq_obs(has='weaponHandguardAK')),
                  dict(refused=True, prereq=t.prereq_obs(has='weaponHandguardAK', rail=True)),
                  dict(refused=True, prereq=t.prereq_obs(has='weaponHandguardAK'),
                       variant=t.variant_obs('weaponHandguardAK', t.refusal_lights())),
                  dict(refused=True, prereq=t.prereq_obs(has='weaponHandguardAK'),
                       variant=t.variant_obs('weaponHandguardAK', t.good_gun_lights()))]
        count = 0
        for sibling, route in itertools.product(siblings, routes):
            for order in itertools.permutations([a, b, sibling]):
                cls, obs = fixture(order, **route)
                with self.subTest(sibling=sibling, route=route):
                    parsed = report._proxies(obs['hosts'][0])
                    self.assertEqual(frozenset({'weaponFlashlight'}), parsed[4]['slots'])
                    record = result(cls, obs)
                    self.assertEqual('pending', record['verdict'])
                    self.assertEqual('pending', pair(record))
                    self.assertIn('proxy_alias_conflict', record['reasons'])
                count += 1
        self.assertEqual(288, count)

    def test_full_coherent_spelling_product_qualifies_but_native_gaps_do_not(self):
        first = t.proxy()
        selections = [first['selection'], first['selection'].upper().replace('/', '\\'),
                      first['selection'].replace('proxy:/', 'proxy:')]
        models = [first['model'], t.LIGHT_PROXY_PATH.upper() + '.P3D',
                  t.LIGHT_PROXY_PATH[1:].replace('/', '//')]
        classes = [first['cfg_class'], first['cfg_class'].upper(), first['cfg_class'].lower()]
        for selection, model, klass, resolution in itertools.product(selections, models, classes, selections):
            second = copy.deepcopy(first)
            second.update(selection=selection, model=model, cfg_class=klass)
            second['res_lods'][0]['selection'] = resolution
            for order in ([first, second], [second, first]):
                cls, obs = fixture(order)
                self.assertEqual(1, len(report._proxies(obs['hosts'][0])[1]))
                self.assertEqual('server_qualified', pair(result(cls, obs)))
                # The new collapse never supplies a missing concrete native light read-back.
                obs['hosts'][0]['lights'] = [r for r in obs['hosts'][0]['lights'] if r['light'] != 'UniversalLight']
                self.assertEqual('pending', pair(result(cls, obs)))

    def test_substantive_resolution_differences_stay_conflicts_after_normalisation(self):
        first = t.proxy()
        for key, value in [('selection', 'proxy:' + t.LIGHT_PROXY_PATH.upper() + '.002'),
                           ('vertex', ['2', '3', '4']), ('vertex_ok', False)]:
            second = copy.deepcopy(first)
            second['model'] = t.LIGHT_PROXY_PATH.upper() + '.P3D'
            second['res_lods'][0][key] = value
            if key == 'vertex_ok': second['res_lods'][0]['vertex'] = []
            for order in ([first, second], [second, first]):
                cls, obs = fixture(order, selection=True)
                self.assertIsNotNone(report._proxies(obs['hosts'][0])[4])
                self.assertEqual('pending', pair(result(cls, obs)))

    def test_generic_malformed_does_not_override_an_independent_native_negative(self):
        evidence = []
        entries = [t.proxy(), dict(t.proxy('/dz/other/broken'), selection='not-a-proxy')]
        cases = [('native positive', dict(), 'pending'),
                 ('native positive with selection', dict(selection=True), 'pending'),
                 ('native refusal, no prerequisite owned', dict(refused=True), 'geometry_missing'),
                 ('native refusal, prerequisite evidence absent', dict(refused=True, prereq=[]), 'pending'),
                 ('native refusal, unmet prerequisite', dict(refused=True, prereq=t.prereq_obs(has='weaponHandguardAK')), 'pending'),
                 ('native refusal, satisfied prerequisite', dict(refused=True, prereq=t.prereq_obs(has='weaponHandguardAK', rail=True)), 'geometry_missing')]
        for label, kwargs, expected in cases:
            cls, obs = fixture(entries, **kwargs)
            parsed = report._proxies(obs['hosts'][0])
            self.assertEqual('malformed', parsed[0]); self.assertIsNone(parsed[4])
            record = result(cls, obs)
            self.assertEqual(expected, pair(record), label)
            self.assertNotEqual('server_qualified', record['verdict'], label)
            slot = record['lights']['UniversalLight']['slots']['weaponFlashlight']
            evidence.append(dict(case=label, host=record['verdict'], pair=pair(record),
                                 reason=slot['reason'], model_evidence=slot['evidence']['model_evidence']))
        (OUT/'generic-malformed.json').write_text(json.dumps(evidence, indent=2)+'\n')

    def test_differential_qualification_only_adds_coherent_alias_cases(self):
        spec = importlib.util.spec_from_file_location('r11_before', OUT/'committed_taped_light_report.py')
        old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
        first = t.proxy()
        model_alias = dict(copy.deepcopy(first), model=t.LIGHT_PROXY_PATH.upper()+'.P3D')
        res_alias = copy.deepcopy(first); res_alias['res_lods'][0]['selection'] = first['selection'].upper()
        absent = dict(copy.deepcopy(first), cfg_exists=False, model='', inventory_slots=[], slot_count=0)
        wrong = dict(copy.deepcopy(first), model='/dz/other/substantive.p3d')
        broken = dict(t.proxy('/dz/other/broken'), selection='bad')
        legacy = t.proxy('/dz/other/legacy', cfg_class='Proxy/dz/other/legacy', exists=False, res_selection='')
        choices = [first, model_alias, res_alias, absent, wrong, broken, legacy]
        promotions = []; checked = 0
        for size in (1, 2, 3):
            for entries in itertools.product(choices, repeat=size):
                for selection, refused in itertools.product((False, True), repeat=2):
                    cls, obs = fixture(entries, selection=selection, refused=refused)
                    before, after = result(cls, obs, old), result(cls, obs)
                    checked += 1
                    if pair(after) == 'server_qualified' and pair(before) != 'server_qualified':
                        parsed = report._proxies(obs['hosts'][0])
                        self.assertEqual('ok', parsed[0]); self.assertIsNone(parsed[4])
                        self.assertTrue(all(e in [first, model_alias, res_alias] for e in entries))
                        self.assertFalse(refused)
                        promotions.append(dict(rows=len(entries), selection=selection))
        self.assertEqual(1596, checked)
        self.assertTrue(promotions)
        (OUT/'differential.json').write_text(json.dumps(dict(cases=checked, promotions=len(promotions),
            every_promotion_is_coherent_alias_collapse=True), indent=2)+'\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
