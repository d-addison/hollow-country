"""Explicit synthetic counterexamples and malformed native-file copies in memory; no engine execution."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent/'baseline'))
from tests.unit import test_weather_report as f
from tools.audit import weather_report as r


class NewFindings(unittest.TestCase):
    def test_excursion_after_convergence_into_limits_is_not_excused_with_current_read_back(self):
        # Explicit synthetic excursion after first entering .7..8, prior to reaching .75.
        actual=[.3,.4,.72,.1]+[.75]*10
        points=list(zip(actual,[.75]*14,[360-30*i for i in range(12)]+[0,40]))
        candidate=f.fog_current_run(f.FOG_CURRENT_LIMITS,'candidate',points)
        result=r.compare(f.evaluated(f.STOCK,'stock',count=14),candidate)
        entry=result['phenomena']['fog']
        print('current also read back:',result['status'],entry['attribute_evidence'],entry['candidate_status'],
              entry['initial_transition'],flush=True)
        self.assertEqual('candidate_values_outside_limits',entry['evidence'])

    def test_excursion_after_entering_limits_is_not_initial_transition(self):
        points=list(zip([.81,.4,.6,.75,.9,.9,.9,.9],[.9]*8,[100,70,40,10]*2))
        candidate=f.evaluated(f.DISTINCT,'candidate',count=8,mutate=f.series('overcast',points))
        result=r.compare(f.evaluated(f.STOCK,'stock',.3,count=8),candidate)
        entry=result['phenomena']['overcast']
        print('inside then excursion:',json.dumps({k:entry[k] for k in
              ('evidence','candidate_status','values_in_range','initial_transition','candidate_actual_range')}),flush=True)
        self.assertEqual('violates_candidate',entry['candidate_status'])

    def test_forecast_outside_is_reported_even_without_a_cycle(self):
        points=[(.9,.99,900-30*i) for i in range(6)]
        result=r.compare(f.evaluated(f.STOCK,'stock',.3),
                         f.evaluated(f.DISTINCT,'candidate',mutate=f.series('overcast',points)))
        entry=result['phenomena']['overcast']
        print('out-of-range forecast without cycle:',entry['evidence'],entry['candidate_forecast_outside_limits'],flush=True)
        self.assertEqual('candidate_values_outside_limits',entry['evidence'])

    def test_values_in_range_describes_the_raw_samples(self):
        points=list(zip([.3,.45,.6,.75,.9,.9,.9,.9],[.9]*8,[100,70,40,10]*2))
        result=r.compare(f.evaluated(f.STOCK,'stock',.3,count=8),
                         f.evaluated(f.DISTINCT,'candidate',count=8,mutate=f.series('overcast',points)))
        entry=result['phenomena']['overcast']
        print('raw values outside:',entry['values_in_range'],entry['candidate_actual_range'],entry['initial_transition'],flush=True)
        self.assertFalse(entry['values_in_range'])


class RequestedGuards(unittest.TestCase):
    def test_nonending_window_is_not_excused(self):
        entry=f.evaluated(f.DISTINCT,'candidate',mutate=f.series('overcast',[(.3,.9,900-30*i) for i in range(6)]))['phenomena']['overcast']
        print('nonending window:',entry['status'],entry['actual_violations'],entry['initial_transition'],flush=True)
        self.assertEqual(6,entry['actual_violations'])

    def test_scheduled_change_ends_window_and_counts_same_sample(self):
        points=list(zip([.3]*6,[.9,.9,.9,.85,.85,.85],[100,70,40,10,100,70]))
        entry=f.evaluated(f.DISTINCT,'candidate',mutate=f.series('overcast',points))['phenomena']['overcast']
        print('scheduled window end:',entry['initial_transition'],entry['violating_samples'],flush=True)
        self.assertEqual([3,4,5],entry['violating_samples'])

    def test_native_exponents_and_bad_samples(self):
        root=Path('/mnt/d/HollowCountryLocal/weather-probe-001-candidate')
        text=(root/'profiles/HCWeatherProbe/observations.json').read_text()
        xml=(root/'mpmissions/dayzOffline.chernarusplus/cfgweather.xml').read_bytes()
        plan=json.loads((root/'weather-probe-plan.json').read_text())
        lines=text.splitlines()
        cases={'clean':text,'duplicate_sample':'\n'.join(lines[:2]+[lines[1]]+lines[2:]),
               'duplicate_json_key':text.replace('"actual":"0.2877"','"actual":"0.1","actual":"0.2877"',1),
               'nonfinite':text.replace('"actual":"0.2877"','"actual":"1e9999"',1),
               'null_sample':text.replace(lines[1],'null',1),
               'non_object_phenomenon':text.replace('"overcast":{','"overcast":null,"bogus":{',1)}
        for name,observations in cases.items():
            with self.subTest(name=name):
                result=r.evaluate(observations,xml,plan=plan)
                print('native copy',name, result['status'],result['issues'][:2],flush=True)
                self.assertEqual('complete' if name=='clean' else 'pending',result['status'])
        for text,wanted in [('5.51835e-05',.0000551835),('-1.2E+2',-120),('0e0',0)]:
            self.assertEqual(wanted,r._number(text))


if __name__=='__main__':
    unittest.main(verbosity=2)
