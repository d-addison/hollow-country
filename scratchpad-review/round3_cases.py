"""Explicit synthetic report counterexamples. No DayZ execution or engine model."""
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parent / 'baseline'))
from tests.unit import test_weather_report as f
from tools.audit import weather_report as r


def with_current(xml, name='fog'):
    root = ET.fromstring(xml)
    node = root.find(name + '/current')
    node.set('actual', '0.75')
    node.set('time', '30')
    node.set('duration', '30')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


class NewRegressions(unittest.TestCase):
    def test_canceled_deadline_does_not_establish_a_later_cycle(self):
        def canceled(rows):
            for i, row in enumerate(rows[1:-1]):
                row['phenomena']['overcast'].update(
                    actual=.81 + .01 * i, forecast=.9, next_change=100 if i == 0 else 1000)
        candidate = f.evaluated(f.DISTINCT, 'candidate', mutate=canceled)
        result = r.compare(f.evaluated(f.STOCK, 'stock', .3), candidate)
        entry = result['phenomena']['overcast']
        print('canceled deadline:', json.dumps({k: entry[k] for k in
              ('evidence', 'boundary_crossed', 'cycle_observed')}), 'status=', result['status'], flush=True)
        self.assertFalse(entry['cycle_observed']['candidate'])
        self.assertEqual('pending', result['status'])

    def test_current_only_is_not_reported_as_no_treatment(self):
        xml = with_current(f.cfgweather(enable='1'))
        result = r.compare(f.evaluated(f.STOCK, 'stock', .3), f.evaluated(xml, 'candidate', .3))
        print('current only:', result['status'], 'treated=', result['treated'],
              'fog=', result['phenomena']['fog']['evidence'], 'issues=', result['issues'], flush=True)
        self.assertNotEqual('not_treated', result['phenomena']['fog']['evidence'])

    def test_current_only_target_is_not_hidden_in_a_mixed_treatment(self):
        xml = with_current(f.DISTINCT)
        result = r.compare(f.evaluated(f.STOCK, 'stock', .3), f.evaluated(xml, 'candidate', .9))
        print('mixed current + limits:', result['status'], 'treated=', result['treated'],
              'fog=', result['phenomena']['fog']['evidence'], 'issues=', result['issues'], flush=True)
        self.assertNotEqual('not_treated', result['phenomena']['fog']['evidence'])


class ReadbackQuantifiers(unittest.TestCase):
    def test_every_candidate_readback_must_match(self):
        def one_stale(rows):
            rows[1]['phenomena']['overcast'].update(limit_min=0, limit_max=1)
        result = r.compare(f.evaluated(f.STOCK, 'stock', .3), f.evaluated(f.DISTINCT, 'candidate', mutate=one_stale))
        print('mixed candidate readbacks:', result['phenomena']['overcast']['evidence'], flush=True)
        self.assertEqual('limits_not_observed_applied', result['phenomena']['overcast']['evidence'])

    def test_no_stock_readback_may_match_candidate(self):
        def one_match(rows):
            rows[1]['phenomena']['overcast'].update(limit_min=.8, limit_max=.95)
        result = r.compare(f.evaluated(f.STOCK, 'stock', .3, mutate=one_match), f.evaluated(f.DISTINCT, 'candidate'))
        print('mixed stock readbacks:', result['phenomena']['overcast']['evidence'], flush=True)
        self.assertEqual('limits_not_observed_applied', result['phenomena']['overcast']['evidence'])


class AmbiguityDiagnostics(unittest.TestCase):
    def test_one_early_mismatch_persists_after_five_matching_readbacks(self):
        def delayed(rows):
            rows[1]['phenomena']['overcast'].update(limit_min=0, limit_max=1)
        candidate = f.evaluated(f.DISTINCT, 'candidate', mutate=delayed)
        result = r.compare(f.evaluated(f.STOCK, 'stock', .3), candidate)
        entry = result['phenomena']['overcast']
        print('one early mismatch, then 5 matches:', result['status'], entry['evidence'],
              'counts=', candidate['phenomena']['overcast']['engine_limits']['limits'],
              'readback=', entry['live_readback'], flush=True)
        self.assertEqual('limits_not_observed_applied', entry['evidence'])
        self.assertEqual('complete', result['status'])
        self.assertEqual('pending', result['runtime_acceptance'])

    def test_wrong_readback_units_cannot_be_distinguished_from_mismatch(self):
        xml = f.cfgweather(enable='1', times={'overcast': (30, 60)})
        def milliseconds(rows):
            for row in rows[1:-1]:
                row['phenomena']['overcast'].update(time_min=30000, time_max=60000)
        result = r.compare(f.evaluated(f.STOCK, 'stock', .3), f.evaluated(xml, 'candidate', mutate=milliseconds))
        print('hypothetical readback milliseconds:', result['status'],
              result['phenomena']['overcast']['evidence'], 'issues=', result['issues'], flush=True)
        self.assertEqual('complete', result['status'])
        self.assertEqual('limits_not_observed_applied', result['phenomena']['overcast']['evidence'])

    def test_stock_without_cycle_is_accepted_only_as_descriptive_comparison(self):
        def stuck(rows):
            for row in rows[1:-1]:
                row['phenomena']['overcast'].update(next_change=1000, forecast=.3)
        result = r.compare(f.evaluated(f.STOCK, 'stock', .3, mutate=stuck), f.evaluated(f.DISTINCT, 'candidate'))
        entry = result['phenomena']['overcast']
        print('stock no cycle:', result['status'], entry['evidence'], entry['cycle_observed'], flush=True)
        self.assertEqual({'stock': False, 'candidate': True}, entry['cycle_observed'])
        self.assertEqual('pending', result['runtime_acceptance'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
