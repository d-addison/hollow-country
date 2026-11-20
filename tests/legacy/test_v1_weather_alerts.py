"""Explicit synthetic #35 alert integration; no native hearing/audio evidence."""
from tests.legacy.test_c1_infectedcfg import tuning_fixture
from types import SimpleNamespace as NS
import unittest

from tests.legacy.test_alert_chain import Array, actor, chain
from tests.legacy.test_horde_stimulus import compile_method, policy_functions
from tests.legacy.test_v1_weather import WEATHER, authored, authored_policy


class V1WeatherAlertIntegrationTests(unittest.TestCase):
    def exercise(self, enabled, reduction):
        context = chain()
        emitter, near, far = actor(), actor((3., 0., 0.)), actor((5., 0., 0.))
        context.NativeEmission(emitter, 17, 100, 16, 3)
        root = context.m_Roots[0]
        emission = context.m_Queue[0]
        before = (root.RootId, root.RootObserved, root.RootExpires,
                  emission.Clue.Strength, emission.Clue.Hops, emission.Clue.EventId)
        # Live emitter moves; attenuation must still use this emission's origin.
        emitter.InfectedEntity.position = (100., 0., 0.)
        samples = []
        noise = NS(GetEnvironmentNoiseReduction=lambda position: samples.append(position) or reduction)
        relay_scope = {'GetGame': lambda: NS(GetNoiseSystem=lambda: noise),
                       'HCAtmosphereQualification': NS(Enabled=lambda: enabled),
                       'HCAtmospherePolicy': authored_policy()}
        relay = NS(RangeAtSource=lambda radius, position: authored(
            WEATHER / 'HCAtmosphereRelay.c', 'RangeAtSource', relay_scope, None, radius, position))
        # Compile the actual ProcessPending body with the newly required explicit
        # collaborator; the existing out-of-scope fixture supplies only old APIs.
        scope = {'HCInfectedTuning': tuning_fixture(), 'HCAtmosphereRelay': relay, 'HCInfectedPolicy': NS(**policy_functions()),
                 'GetGame': lambda: NS(IsServer=lambda: True),
                 'vector': NS(DistanceSq=lambda a, b: sum((x-y)**2 for x, y in zip(a, b)))}
        process = compile_method('HCAlertChain.c', 'ProcessPending(', 'actors, now, work', scope,
                                 ('Expire', 'FindRoot', 'ClearGeometry'))
        spent = process(context, Array([emitter, near, far]), 100, 3)
        self.assertEqual(3, spent)
        self.assertEqual(before, (root.RootId, root.RootObserved, root.RootExpires,
                                  emission.Clue.Strength, emission.Clue.Hops, emission.Clue.EventId))
        self.assertEqual(130, root.RootExpires)
        self.assertTrue(near.HeardExternally)
        return near, far, samples

    def test_enabled_weather_shrinks_only_relay_range_at_frozen_source(self):
        _, far, samples = self.exercise(True, 1.)
        self.assertIsNone(far.Heard)
        self.assertEqual([(0, 0, 0), (0, 0, 0)], samples)

    def test_disabled_weather_preserves_range_without_sampling_environment(self):
        _, far, samples = self.exercise(False, 1.)
        self.assertTrue(far.HeardExternally)
        self.assertEqual([], samples)


if __name__ == '__main__':
    unittest.main()
