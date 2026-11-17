"""Explicit synthetic review cases; these do not model or prove native execution."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent / 'baseline'))
from tests.unit import test_weather_report as f
from tools.audit import weather_report as r

class NewCases(unittest.TestCase):
    def test_crossed_boundary_does_not_override_conflicting_live_limits(self):
        def conflicting(rows):
            for i, row in enumerate(rows[1:-1]):
                row['phenomena']['overcast'].update(actual=.86+i*.01, limit_min=0.0, limit_max=1.0, forecast=0.3)
        stock = f.evaluated(f.STOCK, 'stock', .3)
        candidate = f.evaluated(f.DISTINCT, 'candidate', .9, mutate=conflicting)
        result = r.compare(stock, candidate)
        print('boundary crossed + live limits 0..1 + forecast .3:', result['status'], result['phenomena']['overcast']['evidence'],
              'live=', candidate['phenomena']['overcast']['engine_limits']['limits'],
              'forecast_outside=', candidate['phenomena']['overcast']['forecast_outside_limits'])
        self.assertNotEqual('observed_limit_compliance', result['phenomena']['overcast']['evidence'])

    def test_constant_future_deadline_is_not_observed_forecast_recomputation(self):
        def interp(rows):
            for i, row in enumerate(rows[1:-1]):
                row['phenomena']['overcast'].update(actual=.81+i*.01, forecast=.9, next_change=100)
        candidate = f.evaluated(f.DISTINCT, 'candidate', mutate=interp)
        result = r.compare(f.evaluated(f.STOCK, 'stock', .3), candidate)
        print('unchanged deadline, interpolation only:', result['status'], result['phenomena']['overcast']['evidence'],
              'boundary=', candidate['phenomena']['overcast']['boundary_crossed'])
        self.assertNotEqual('observed_limit_compliance', result['phenomena']['overcast']['evidence'])

    def test_unchanged_zero_snowfall_does_not_block_targeted_overcast_result(self):
        def inert(rows):
            for row in rows[1:-1]:
                row['phenomena']['snowfall'].update(actual=0, forecast=0, next_change=0)
        result = r.compare(f.evaluated(f.STOCK, 'stock', .3, mutate=inert),
                           f.evaluated(f.DISTINCT, 'candidate', mutate=inert))
        print('inert unchanged snowfall:', result['status'], 'overcast=', result['phenomena']['overcast']['evidence'],
              'snowfall=', result['phenomena']['snowfall']['evidence'], result['issues'])
        self.assertEqual('complete', result['status'])

    def test_plausible_24_minute_fog_and_wind_schedules(self):
        # Invented trace deadlines reflecting visible native durations, not recorded native observations.
        def schedules(rows):
            for row in rows[1:-1]:
                row['phenomena']['fog']['next_change'] = 1805
                row['phenomena']['windDirection']['next_change'] = 2205
        def run(xml, variant, overcast):
            rows = [f.header(289, interval_ms=5000, cap_ms=1475000)]
            for i in range(289):
                row = f.sample(i, {'overcast': overcast})
                row['game_ms'] = 30000 + 5000*i
                row['weather_time'] = 30+5*i
                for value in row['phenomena'].values():
                    value['next_change'] = 100 * ((30+5*i)//100+1)
                rows.append(row)
            rows.append(f.end(289))
            schedules(rows)
            plan = f.plan_for(xml, variant, samples=289, interval_s=5)
            return r.evaluate(f.lines(rows), xml, plan=plan)
        result = r.compare(run(f.STOCK, 'stock', .3), run(f.DISTINCT, 'candidate', .9))
        print('24 minute observation window:', result['status'], result['issues'])
        self.assertEqual('complete', result['status'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
