"""Explicit synthetic report fixtures; no DayZ runtime claims."""
import copy
import itertools
import json
import unittest
from pathlib import Path
from tests.unit import test_taped_light_report as t
from tools.audit import taped_light_report as report

OUT = Path(__file__).resolve().parent


def build(entries, selection=False, lights=None):
    observed = t.row('AK74', 'slot_host', t.gun_slots(selection),
                     t.good_gun_lights() if lights is None else lights, proxies=entries)
    result = report.build_report(t.classification([t.host('AK74', 'slot_host')]), t.observations([observed]))
    return observed, result


def aliases():
    first = t.proxy()
    second = dict(copy.deepcopy(first), selection=first['selection'].replace('proxy:/', 'proxy:'),
                  cfg_exists=False, model='', inventory_slots=[], slot_count=0)
    return first, second


def legacy_other():
    path = '/dz/other/legacy_proxy'
    return t.proxy(path, exists=False, cfg_class='Proxy' + path, res_selection='')


class AdversarialTests(unittest.TestCase):
    def test_conflict_survives_unrelated_legacy_name_mismatch_in_every_order(self):
        for entries in itertools.permutations([*aliases(), legacy_other()]):
            with self.subTest(order=[e['selection'] for e in entries]):
                raw, result = build(list(entries), selection=True)
                record = result['hosts'][0]
                self.assertEqual([], result['integrity']['issues'])
                self.assertEqual('pending', record['lights']['UniversalLight']['verdict'])
                self.assertIn('proxy_alias_conflict', record['reasons'])

    def test_conflict_survives_an_unreadable_sibling_in_every_order(self):
        broken = dict(t.proxy('/dz/other/broken'), selection='not-a-proxy')
        for entries in itertools.permutations([*aliases(), broken]):
            with self.subTest(order=[e['selection'] for e in entries]):
                raw, result = build(list(entries), lights=t.refusal_lights())
                self.assertEqual('pending', result['hosts'][0]['verdict'])
                self.assertIn('proxy_alias_conflict', result['hosts'][0]['reasons'])

    def test_coherent_model_path_spellings_collapse(self):
        first = t.proxy()
        second = dict(copy.deepcopy(first), selection=first['selection'].replace('proxy:/', 'proxy:'),
                      model=t.LIGHT_PROXY_PATH.upper() + '.P3D', cfg_class=first['cfg_class'].upper())
        for entry in (first, second):
            self.assertEqual('server_qualified', build([entry])[1]['hosts'][0]['verdict'])
        for entries in ([first, second], [second, first]):
            with self.subTest(first_model=entries[0]['model']):
                raw, result = build(entries)
                parsed = report._proxies(raw)
                self.assertEqual('ok', parsed[0])
                self.assertIsNone(parsed[4])
                self.assertEqual(1, len(parsed[1]))
                self.assertEqual('server_qualified', result['hosts'][0]['verdict'])

    def test_resolution_proxy_spelling_alone_collapses(self):
        first = t.proxy()
        second = copy.deepcopy(first)
        second['res_lods'][0]['selection'] = first['res_lods'][0]['selection'].upper().replace('/', chr(92))
        for entry in (first, second):
            self.assertEqual('server_qualified', build([entry])[1]['hosts'][0]['verdict'])
        for entries in ([first, second], [second, first]):
            with self.subTest(first_selection=entries[0]['res_lods'][0]['selection']):
                raw, result = build(entries)
                self.assertIsNone(report._proxies(raw)[4])
                self.assertEqual(1, len(report._proxies(raw)[1]))
                self.assertEqual('server_qualified', result['hosts'][0]['verdict'])

    def test_class_spelling_alone_collapses(self):
        first = t.proxy()
        second = dict(copy.deepcopy(first), cfg_class=first['cfg_class'].upper())
        raw, result = build([first, second])
        self.assertEqual(1, len(report._proxies(raw)[1]))
        self.assertIsNone(report._proxies(raw)[4])
        self.assertEqual('server_qualified', result['hosts'][0]['verdict'])

    def test_three_readings_union_slots_and_truncation_in_every_order(self):
        path = '/dz/other/magazine'
        a = t.proxy(path, slots=('magazine',))
        b = t.proxy(path, number='002', slots=('weaponFlashlight',))
        c = t.proxy(path, number='003', slots=tuple('extra%d' % n for n in range(8)), slot_count=9)
        for order in itertools.permutations([a,b,c]):
            raw, result = build([t.proxy(), *order])
            parsed = report._proxies(raw)
            self.assertTrue(parsed[4]['all'])
            self.assertIn('weaponFlashlight', parsed[4]['slots'])
            self.assertEqual('pending', result['hosts'][0]['lights']['UniversalLight']['verdict'])

    def test_unknown_case_slots_do_not_implicate_native_slot(self):
        path = '/dz/other/magazine'
        a = t.proxy(path, slots=('weaponflashlight',))
        b = dict(copy.deepcopy(a), model='/dz/other/mismatch.p3d')
        for order in ([a,b], [b,a]):
            raw, result = build([t.proxy(), *order])
            self.assertEqual('pending', result['hosts'][0]['verdict'])
            self.assertEqual('server_qualified', result['hosts'][0]['lights']['UniversalLight']['verdict'])

    def test_missing_native_rows_and_concrete_variants_remain_pending(self):
        names = ['FNX45', 'FNX45_arrow', 'SCARH_Black', 'Glock19_Tan']
        cls = t.classification([t.host(name,'slot_host') for name in names])
        for entry in cls['hosts'][1:]:
            entry['ancestors'] = ['FNX45']
            entry['model'] = 'shared.p3d'
        obs = t.observations([t.row('FNX45','slot_host',t.gun_slots(False),t.good_gun_lights(),proxies=[t.proxy()])])
        result = report.build_report(cls,obs)
        self.assertEqual('PENDING', result['acceptance'])
        self.assertEqual('server_qualified',t.by_class(result,'FNX45')['verdict'])
        for name in names[1:]:
            record = t.by_class(result,name)
            self.assertEqual(('pending',['no_probe_row']), (record['verdict'],record['reasons']))
        result = report.build_report(cls,t.observations([]))
        self.assertTrue(all(r['verdict']=='pending' for r in result['hosts']))
        self.assertTrue(all(v=='pending' for v in result['unobserved_axes'].values()))


if __name__ == '__main__':
    examples=[]
    for label, entries, selection, lights in [
        ('conflict alone', list(aliases()), True, None),
        ('same conflict plus legacy sibling', [*aliases(),legacy_other()], True, None),
        ('same conflict plus unreadable sibling and native refusal', [*aliases(),dict(t.proxy('/dz/other/broken'),selection='not-a-proxy')],False,t.refusal_lights()),
    ]:
        raw, result=build(entries,selection,lights)
        record=result['hosts'][0]
        examples.append(dict(case=label,parsed=report._proxies(raw)[0],host=record['verdict'],reasons=record['reasons'],
                             pair=record['lights']['UniversalLight']['verdict'],integrity=result['integrity']['issues'],acceptance=result['acceptance']))
    (OUT/'counterexamples.json').write_text(json.dumps(examples,indent=2)+'\n')
    unittest.main(verbosity=2)
