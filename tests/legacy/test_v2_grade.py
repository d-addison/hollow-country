"""LC-T101..103: synthetic policy smoke only; no DayZ/PPE acceptance.

Reuses the existing authored-method adapter without extending it. Inputs are
explicit synthetic hours/weather, and the output is a caller-owned native DTO.
"""
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

from tests.legacy.test_v1_weather import authored


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / 'mods/HollowCountry/scripts/3_Game/Atmosphere/HCGradePolicy.c'


class GradeSmokeTests(unittest.TestCase):
    def test_night_and_zero_are_identity_and_day_scales(self):
        self.assertTrue(POLICY.is_file(), 'missing HCGradePolicy implementation')
        identity = dict(Desaturation=0., TintRed=1., TintGreen=1., TintBlue=1.,
                        Contrast=1., Vignette=0., Exposure=1.)
        math_api = NS(Clamp=lambda x, lo, hi: max(lo, min(hi, x)))

        def evaluate(hour, overcast, fog, rain, intensity):
            result = NS(**{key: -99. for key in identity})
            authored(POLICY, 'Evaluate', {'Math': math_api}, None,
                     hour, overcast, fog, rain, intensity, result)
            return vars(result)

        for hour in (0., 4., 6., 8., 18., 20., 22., 24.):
            self.assertEqual(identity, evaluate(hour, 1., 1., 1., 1.))
        for hour in (0., 9., 12., 15., 23.):
            self.assertEqual(identity, evaluate(hour, 1., 1., 1., 0.))
        full = evaluate(12., 1., 1., 1., 1.)
        half = evaluate(12., 1., 1., 1., .5)
        self.assertGreater(full['Desaturation'], evaluate(12., 0., 0., 0., 1.)['Desaturation'])
        self.assertGreater(full['Vignette'], 0.)
        self.assertLess(full['TintRed'], full['TintGreen'])
        for key, baseline in identity.items():
            self.assertAlmostEqual((full[key] + baseline) / 2., half[key])
        self.assertEqual(1., full['Exposure'])


if __name__ == '__main__':
    unittest.main()
