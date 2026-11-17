"""Explicit synthetic review checks; no assertion about native engine behavior."""
import itertools
import json
from pathlib import Path
import random
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'baseline'))
from tests.unit import test_weather_report as f
from tools.audit import weather_report as r

POSITIVE = {'candidate_live_limits_read_back', 'candidate_current_read_back'}


def independent_end(points, low=.8, high=.95):
    # Explicit numerical bands for this synthetic .8..95 XML, independent of report helpers.
    target = points[0][1]
    for i, (actual, forecast, left) in enumerate(points):
        if abs(actual - target) <= .001 or low - .001 <= actual <= high + .001:
            return i
        if i and (abs(forecast - target) > .001 or left > points[i-1][2] + .05
                  or left <= 0 < points[i-1][2]):
            return i
    return 0


class AdditionalChecks(unittest.TestCase):
    def test_synthetic_positive_label_invariant(self):
        stock = f.evaluated(f.STOCK, 'stock', .3)
        rng = random.Random(35)
        cases = [(list(actual), [.9]*6, [100,70,40,10,100,70])
                 for actual in itertools.product((.3,.85,.9,.99), repeat=6)]
        countdowns = [[100,70,40,10,100,70], [900,870,840,810,780,750],
                      [100,70,40,10,0,0], [100]*6, [0]*6, [100,70,900,870,840,810]]
        for _ in range(1200):
            cases.append(([rng.choice((.3,.85,.9,.99)) for _ in range(6)],
                          [rng.choice((.85,.9,.99)) for _ in range(6)], rng.choice(countdowns)))
        positives = 0
        for actual, forecast, countdown in cases:
            points = list(zip(actual, forecast, countdown))
            candidate = f.evaluated(f.DISTINCT, 'candidate', mutate=f.series('overcast', points))
            entry = r.compare(stock, candidate)['phenomena']['overcast']
            end = independent_end(points)
            self.assertEqual(end, entry['initial_transition']['samples'])
            bad_actual = any(not .799 <= value <= .951 for value in actual[end:])
            bad_forecast = any(not .799 <= value <= .951 for value in forecast)
            labels = {entry['evidence'], entry['supported_attribute_evidence']}
            labels.update((entry['attribute_evidence'] or {}).values())
            if labels & POSITIVE:
                positives += 1
                self.assertFalse(bad_actual or bad_forecast, (points, entry))
            self.assertEqual(not any(not .799 <= value <= .951 for value in actual), entry['values_in_range'])
            if bad_actual or bad_forecast:
                self.assertEqual('candidate_values_outside_limits', entry['evidence'])
        print(f'invariant: traces={len(cases)}, positives={positives}, false_positives=0', flush=True)

    def test_current_only_and_mixed_treatments_reject_every_position_of_a_violation(self):
        checked = 0
        for xml in (f.FOG_CURRENT, f.FOG_CURRENT_LIMITS):
            stock = f.evaluated(f.STOCK, 'stock', count=14)
            for kind in ('actual', 'forecast'):
                for position in range(14):
                    # Starts at target: no exempt prefix, so every position is assessed.
                    actual, forecast = [.75]*14, [.75]*14
                    (actual if kind == 'actual' else forecast)[position] = 1.2
                    points = list(zip(actual, forecast, [360-30*i for i in range(12)]+[0,40]))
                    entry = r.compare(stock, f.fog_current_run(xml, 'candidate', points))['phenomena']['fog']
                    if kind == 'actual' and position == 0:
                        # Only this placement is an initial prefix, rather than an assessed excursion.
                        self.assertIn(entry['evidence'], POSITIVE)
                        self.assertEqual(1, entry['initial_transition']['samples'])
                        self.assertFalse(entry['values_in_range'])
                    else:
                        self.assertEqual('candidate_values_outside_limits', entry['evidence'], (kind, position, entry))
                        self.assertIsNone(entry['attribute_evidence'])
                    checked += 1
        print(f'current-only/mixed: {checked} placements checked, 54 assessed violations rejected, 2 initial prefixes explicitly excused', flush=True)

    def test_changed_preexisting_fixtures_keep_pending_intent(self):
        def fog(rows, original=False):
            for row in rows[1:7]:
                row['phenomena']['fog']['next_change'] = 1000
                if not original:
                    row['phenomena']['fog'].update(actual=.75, forecast=.75)
        def conflict(rows, original=False):
            for row in rows[1:7]:
                row['phenomena']['overcast'].update(limit_min=0., limit_max=1.,
                                                   forecast=.3 if original else .9, next_change=1000)
        for name, xml, phenomenon, mutation in (
                ('one_pending_treated_phenomenon', f.XML_TREATING_OVERCAST_AND_FOG, 'fog', fog),
                ('conflicting_live_limits_without_boundary', f.DISTINCT, 'overcast', conflict)):
            for original in (True, False):
                candidate = f.evaluated(xml, 'candidate', mutate=lambda rows: mutation(rows, original))
                result = r.compare(f.evaluated(f.STOCK, 'stock', .3), candidate)
                entry = result['phenomena'][phenomenon]
                expected = 'candidate_values_outside_limits' if original else 'pending'
                self.assertEqual(expected, entry['evidence'])
                self.assertFalse(entry['boundary_crossed']['candidate'])
                self.assertFalse(entry['cycle_observed']['candidate'])
                print(name, 'old' if original else 'new', json.dumps({
                    'status': result['status'], 'evidence': entry['evidence'], 'reason': entry['reason'],
                    'actual_outside': entry['raw_actual_outside_limits'],
                    'forecast_outside': entry['candidate_forecast_outside_limits'],
                    'boundary': entry['boundary_crossed']['candidate'],
                    'cycle': entry['cycle_observed']['candidate']}), flush=True)

    def test_emitted_transition_prose_matches_first_entry_rule(self):
        # Review expectation: emitted single/pair prose must describe all three endpoints.
        note = next(note for note in r.NON_CLAIMS if 'initial transition' in note)
        print('emitted transition non-claim:', note, flush=True)
        self.assertIn('enters', note)
        self.assertIn('whichever', note)

    def test_short_clean_run_does_not_claim_post_transition_actuals_outside(self):
        candidate = f.evaluated(f.DISTINCT, 'candidate', .9, count=3)
        entry = r.compare(f.evaluated(f.STOCK, 'stock', .3, count=3), candidate)['phenomena']['overcast']
        print('short clean run:', json.dumps({key: entry[key] for key in (
            'candidate_status', 'evidence', 'values_in_range', 'values_in_range_after_initial_transition',
            'raw_actual_outside_limits', 'initial_transition', 'candidate_actual_range')}), flush=True)
        self.assertEqual('pending', entry['evidence'])
        self.assertEqual(0, candidate['phenomena']['overcast']['actual_violations'])
        self.assertTrue(entry['values_in_range_after_initial_transition'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
