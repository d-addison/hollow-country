"""Execute authored Release with injected native failures; no engine proof."""
from types import SimpleNamespace as NS
import unittest

if __package__:
    from tests.legacy.test_infected_routes import NativeArray, authored_navigation
else:
    from tests.legacy.test_infected_routes import NativeArray, authored_navigation


class NativeMap(dict):
    def Get(self, key): return self.get(key)
    def Set(self, key, value): self[key] = value
    def Remove(self, key): self.pop(key, None)
    def Clear(self): self.clear()


class SyntheticAgent:
    def __init__(self, owner): self.owner = owner
    def GetGroup(self): return self.owner


class SyntheticMember:
    def __init__(self, agent): self.agent = agent
    def GetAIAgent(self): return self.agent


class SyntheticGroup:
    def __init__(self, accepts=True, removes=True):
        self.accepts, self.removes = accepts, removes
        self.adds, self.removals, self.routes = [], [], []
    def AddAgent(self, agent):
        self.adds.append(agent)
        if self.accepts: agent.owner = self
    def RemoveAgent(self, agent):
        self.removals.append(agent)
        if self.removes: agent.owner = None
    def GetBehaviour(self): return self
    def SetWaypoints(self, *args): self.routes.append(args)


class InfectedPackOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.now = 100
        self.old = SyntheticGroup()
        self.fallback = SyntheticGroup(accepts=False)
        self.agent = SyntheticAgent(self.old)
        self.member = SyntheticMember(self.agent)
        self.allocations = 0
        self.allocation_fails = False
        self.pending = NativeArray()
        self.context = NS(Group=self.old, RouteResult=1, m_Releasing=False,
            m_LastPosition="synthetic-position", m_Members=NativeArray([self.member]),
            m_ReleaseFallbacks=NativeMap(), m_ReleaseQuarantined=False,
            m_ReleaseAttempts=0, m_NextReleaseUtc=0,
            GetAIWorld=lambda: NS(CreateDefaultGroup=self.allocate))

    def allocate(self):
        self.allocations += 1
        return None if self.allocation_fails else self.fallback

    def release(self):
        return authored_navigation("bool Release()", self.context,
            s_PendingRelease=self.pending, HCInfectedClock=NS(UtcSeconds=lambda: self.now),
            BehaviourGroupInfectedPack=NS(Cast=lambda value: value),
            BehaviourGroupInfectedPackWaypointParams=lambda *args: NS())

    def test_release_does_not_forget_member_after_failed_fallback_add(self):
        self.assertFalse(self.release())
        self.assertIsNone(self.agent.owner)
        self.assertEqual([self.member], self.context.m_Members)
        self.assertFalse(self.release(), "No old owner is not proof of fallback ownership")
        self.assertIn(self.context, self.pending)
        self.assertEqual([self.member], self.context.m_Members)

    def test_ungrouped_retry_confirms_the_same_expected_fallback(self):
        self.assertFalse(self.release())
        self.now = 105
        self.fallback.accepts = True
        self.assertTrue(self.release())
        self.assertIs(self.fallback, self.agent.owner)
        self.assertEqual(1, self.allocations)
        self.assertEqual(2, len(self.fallback.adds))
        self.assertEqual([], self.pending)
        self.assertEqual({}, self.context.m_ReleaseFallbacks)
        self.assertEqual(1, len(self.old.routes))

    def test_retry_budget_quarantines_unresolved_members_without_more_mutations(self):
        for instant in (100, 104, 105, 109, 110, 115, 120):
            self.now = instant
            self.assertFalse(self.release())
        self.assertEqual(3, self.context.m_ReleaseAttempts)
        self.assertEqual(3, len(self.fallback.adds))
        self.assertTrue(self.context.m_ReleaseQuarantined)
        self.assertEqual([self.member], self.context.m_Members)
        self.assertIn(self.context, self.pending)

    def test_late_verified_fallback_ownership_can_complete_after_budget(self):
        for self.now in (100, 105, 110, 115):
            self.release()
        self.agent.owner = self.fallback  # explicit delayed native observation
        self.assertTrue(self.release())
        self.assertEqual([], self.pending)
        self.assertEqual(3, len(self.fallback.adds))

    def test_failed_remove_does_not_add_an_agent_still_owned_elsewhere(self):
        self.old.removes = False
        self.assertFalse(self.release())
        self.assertIs(self.old, self.agent.owner)
        self.assertEqual([], self.fallback.adds)

    def test_unexpected_third_owner_is_not_confirmation_or_permission_to_steal(self):
        self.assertFalse(self.release())
        third = SyntheticGroup()
        self.agent.owner = third
        self.now = 105
        self.assertFalse(self.release())
        self.assertIs(third, self.agent.owner)
        self.assertEqual([], third.removals)
        self.assertEqual(1, len(self.fallback.adds))

    def test_missing_agent_is_unresolved_rather_than_a_successful_rehome(self):
        self.member.agent = None
        self.assertFalse(self.release())
        self.assertIn(self.context, self.pending)
        self.assertEqual([self.member], self.context.m_Members)

    def test_allocation_failure_preserves_owner_and_retries_within_budget(self):
        self.allocation_fails = True
        self.assertFalse(self.release())
        self.assertIs(self.old, self.agent.owner)
        self.assertEqual([], self.old.removals)
        self.allocation_fails = False
        self.fallback.accepts = True
        self.now = 105
        self.assertTrue(self.release())
        self.assertIs(self.fallback, self.agent.owner)

    def test_partial_start_ungrouped_member_is_rehomed_even_without_old_group(self):
        self.context.Group = None
        self.agent.owner = None
        self.fallback.accepts = True
        self.assertTrue(self.release())
        self.assertIs(self.fallback, self.agent.owner)
        self.assertEqual(1, len(self.fallback.adds))

    def test_only_verified_members_are_removed_from_a_partial_release(self):
        second_agent = SyntheticAgent(self.old)
        second = SyntheticMember(second_agent)
        self.context.m_Members.Insert(second)
        self.assertFalse(self.release())
        second_agent.owner = self.fallback
        self.assertFalse(self.release())
        self.assertEqual([self.member], self.context.m_Members)
        self.assertIn(self.context, self.pending)


if __name__ == "__main__": unittest.main()
