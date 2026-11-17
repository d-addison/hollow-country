"""Synthetic retained-target regressions; no lighting or native sight evidence."""
from types import SimpleNamespace as NS
import unittest

if __package__:
    from .test_infected_routes import SOURCE, authored_navigation
else:
    from test_infected_routes import SOURCE, authored_navigation


class SyntheticVector:
    """Only the clear, in-range, in-FOV geometry used by this counterexample."""
    def __add__(self, other): return self
    def __sub__(self, other): return self
    def Normalize(self): pass
    @staticmethod
    def DistanceSq(first, second): return 100
    @staticmethod
    def Dot(first, second): return .8


class InfectedPerceptionTests(unittest.TestCase):
    def sample(self, mind=2):
        calls = []
        point = SyntheticVector()
        candidate = NS(IsAlive=lambda: True, GetDefaultHitPosition=lambda: point)
        def coordinates(_):
            calls.append("hidden-coordinates")
            return point
        candidate.ModelToWorld = coordinates
        def retained_target():
            calls.append("retained-target")
            return candidate
        controller = NS(GetMindState=lambda: mind, GetTargetEntity=retained_target)
        infected = NS(IsAlive=lambda: True, GetInputController=lambda: controller,
                      GetPosition=lambda: point, GetDirection=lambda: point)
        def raycast(origin, target, contact, normal, component, hits, *args):
            calls.append("geometry")
            hits.Insert(candidate)
            return True
        source = (SOURCE / "HCInfectedNavigation.c").read_text()
        def provenance(native_controller):
            # Execute the actual fail-closed gate when present, without inventing
            # a lighting-aware native API or a runtime-qualified fixture.
            return authored_navigation("static bool VisualProvenanceEstablished(", NS(),
                                       controller=native_controller)
        old_visual = NS(Provenance=2, Origin="frozen-observed-cue", Observed=90, Expires=110)
        actor = NS(InfectedEntity=infected, Visual=old_visual, SearchAttempts=2, ClueLifetime=20)
        result = authored_navigation("static bool SampleVisual(", NS(), actor=actor, now=100,
            DayZInfectedConstants=NS(MINDSTATE_CHASE=2, MINDSTATE_FIGHT=3),
            HCInfectedObservation=NS(VisualProvenanceEstablished=provenance),
            vector=SyntheticVector, DayZPhysics=NS(RaycastRV=raycast),
            ObjIntersectView=1, ObjIntersectFire=2, HCInfectedClue=NS,
            HCInfectedStore=NS(ValidPosition=lambda value: True))
        return result, actor, old_visual, calls, source

    def test_retained_auditory_candidate_is_not_a_confirmed_visual_observation(self):
        result, actor, old_visual, calls, _ = self.sample()
        self.assertFalse(result, "Clear geometry and retained sound target do not prove native sight")
        self.assertIs(old_visual, actor.Visual)
        self.assertEqual(2, actor.SearchAttempts)

    def test_unknown_visual_provenance_does_not_acquire_hidden_coordinates(self):
        for mind in (2, 3):
            with self.subTest(mind=mind):
                result, actor, old_visual, calls, _ = self.sample(mind)
                self.assertEqual([], calls, "Deny unknown provenance before even sampling the target")
                self.assertIs(old_visual, actor.Visual)
                self.assertEqual((90, 110), (actor.Visual.Observed, actor.Visual.Expires))

    def test_native_pursuit_has_no_authored_override(self):
        observation = (SOURCE / "HCInfectedNavigation.c").read_text().split("class HCInfectedObservation", 1)[1]
        for mutation in ("SetTarget", "Override", "RemoveAgent(", "AddAgent(", "SetWaypoints("):
            self.assertNotIn(mutation, observation)


if __name__ == "__main__": unittest.main()
