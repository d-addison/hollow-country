"""One synthetic scalar smoke; executes authored bodies, never DayZ evidence."""
import re
from pathlib import Path
from types import SimpleNamespace
import unittest

from tests.legacy.test_event_runtime import translate
from tests.legacy.test_c2_atmoscfg import defaults_env

SOURCE = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/3_Game/Atmosphere/HCLightingBlend.c'


class LightingSmoke(unittest.TestCase):
    def test_midnight_is_vanilla_and_storm_differs_from_clear(self):
        self.assertTrue(SOURCE.is_file(), 'HCLightingBlend source has not been implemented')
        policy = SimpleNamespace()
        source = SOURCE.read_text()
        for name in re.findall(r'static (?:bool|float|string) (\w+)\(', source):
            setattr(policy, name, translate(source, name, dict(defaults_env(), HCLightingBlend=policy)))
        # Explicit synthetic hours/weather, including a stale storm on entering night.
        for hour in (0, 4.99, 20, 23.99):
            for cloud, rain, fog in ((0, 0, 0), (1, 1, 1)):
                self.assertEqual(0, policy.Weight(hour, cloud, rain, fog))
                self.assertEqual('vanilla', policy.Name(hour, cloud, rain, fog))
            self.assertEqual(0, policy.Step(.7, .9, policy.Daylight(hour)))
        self.assertEqual('vanilla', policy.Name(12, .2, 0, 0))
        self.assertEqual('storm', policy.Name(12, .95, .85, .2))
        self.assertGreater(policy.Weight(12, .95, .85, .2), policy.Weight(12, .2, 0, 0))
        self.assertEqual('overcast', policy.Name(12, .9, 0, .1))
        self.assertEqual('dusk_warm', policy.Name(17, .2, 0, 0))
        self.assertEqual('dusk_cold', policy.Name(19, .2, 0, 0))


if __name__ == '__main__':
    unittest.main()
