"""One synthetic policy smoke; executes authored methods, never DayZ evidence."""
import math
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import translate
from tests.unit.test_c2_atmoscfg import defaults_env
from tests.unit.test_v1_weather import authored_policy

SOURCE = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/4_World/Weather/HCWeatherDays.c'


class WeatherDaysSmoke(unittest.TestCase):
    def test_seeded_days_morning_lift_and_observed_storm_calm(self):
        self.assertTrue(SOURCE.is_file(), 'missing authored HCWeatherDays.c')
        text = SOURCE.read_text()
        policy = N()
        env = dict(HCWeatherDays=policy, HCAtmospherePolicy=authored_policy(), Math=N(Floor=math.floor))
        env.update(defaults_env())
        for name in re.findall(r'static (?:int|float|bool|string) (\w+)\(', text):
            setattr(policy, name, translate(text, name, env, 'HCWeatherDays'))
        profiles = [policy.Profile(day, 7., 0.) for day in range(20700, 20800)]
        self.assertEqual(profiles, [policy.Profile(day, 7., 0.) for day in range(20700, 20800)])
        self.assertTrue(14 <= profiles.count('bad') <= 26, profiles.count('bad'))
        self.assertTrue(15 <= profiles.count('fog') <= 45)
        for day in range(20700, 20800):
            for hour in (0., 4.99, 9., 12., 20., 23.99):
                self.assertNotEqual('fog', policy.Profile(day, hour, 0.))
                self.assertEqual(.04, policy.FogTarget(day, hour, 0.))
        fog_day = next(day for day in range(20700, 20800) if policy.Profile(day, 7., 0.) == 'fog')
        self.assertGreater(policy.FogTarget(fog_day, 6., 0.), .5)
        self.assertGreater(policy.FogTarget(fog_day, 7., 0.), policy.FogTarget(fog_day, 8., 0.))
        self.assertEqual(0., policy.CalmRemaining(0., .1, True, .4, .95))
        remaining = policy.CalmRemaining(0., .1, True, 0., .8)
        self.assertEqual(3., remaining)
        self.assertEqual('calm', policy.Profile(fog_day, 7., remaining))
        self.assertEqual(0., policy.RainTarget('calm', .95, 12.))
        self.assertEqual(2., policy.WindTarget('calm', .95, 12.))
        self.assertEqual(0., policy.CalmRemaining(remaining, 3., False, 0., .25))
        self.assertGreater(policy.CloudTarget('bad', 2000., 12.), policy.CloudTarget('plain', 2000., 12.))
        self.assertLessEqual(policy.CloudTarget('bad', 4000., 23.), .550001)
        self.assertEqual(0., policy.RainTarget('bad', .95, 23.))


if __name__ == '__main__':
    unittest.main()
