"""Execute authored bounded relays with explicit synthetic entities/geometry.

No hearing range, audibility, perception or engine behavior is established here.
"""
from types import SimpleNamespace as NS
import unittest

if __package__:
    from .test_horde_stimulus import SOURCE, SyntheticClue, compile_method, method_body, policy_functions
else:
    from test_horde_stimulus import SOURCE, SyntheticClue, compile_method, method_body, policy_functions


class Array(list):
    def __bool__(self): return True  # Allocated empty arrays are non-null.
    def Count(self): return len(self)
    def Insert(self, item): self.append(item)
    def Remove(self, index): self.pop(index)
    def Find(self, item):
        return next((i for i, value in enumerate(self) if value is item), -1)


class SyntheticEntity:
    def __init__(self, position=(0, 0, 0), alive=True, mind=1):
        self.position, self.alive, self.mind = position, alive, mind
    def IsAlive(self): return self.alive
    def GetPosition(self): return self.position
    def GetMindStateSynced(self): return self.mind


def actor(position=(0, 0, 0)):
    return NS(InfectedEntity=SyntheticEntity(position), Heard=None, HeardRootId=0,
              HeardExternally=False, ClueLifetime=30, NextHearing=0,
              SearchAttempts=4, Clue=None)


def root(root_id=1, observed=100, expires=130):
    return NS(RootId=root_id, RootObserved=observed, RootExpires=expires,
              Recipients=Array(), Emitters=Array())


def chain(server=True, geometry=True):
    context = NS(m_Roots=Array(), m_Queue=Array(), m_NextRootId=1, m_RecipientCursor=0)
    context.geometry_calls = []
    def clear_geometry(*args):
        context.geometry_calls.append(args)
        return geometry
    context.ClearGeometry = clear_geometry
    scope = dict(HCInfectedPolicy=NS(**policy_functions()),
                 HCInfectedClue=SyntheticClue, HCAlertRoot=root,
                 HCAlertEmission=lambda: NS(Scanned=0),
                 GetGame=lambda: NS(IsServer=lambda: server),
                 DayZInfectedConstants=NS(MINDSTATE_CALM=0), Math=NS(Min=min),
                 HCInfectedStore=NS(ValidPosition=lambda point: all(abs(v) < 100000 for v in point)),
                 vector=NS(DistanceSq=lambda a, b: sum((x-y)**2 for x, y in zip(a, b))))
    for name, parameters in (("FindRoot", "id"), ("Expire", "now"),
                             ("NativeEmission", "actor, eventId, now, queueCap, trackedCount"),
                             ("ProcessPending", "actors, now, work")):
        function = compile_method("HCAlertChain.c", name + "(", parameters, scope,
                                  ("Expire", "FindRoot", "ClearGeometry"))
        setattr(context, name, lambda *args, f=function: f(context, *args))
    return context


class AlertChainTests(unittest.TestCase):
    def seed(self, context=None, now=100, cap=16, count=24):
        context = context or chain()
        emitter = actor()
        context.NativeEmission(emitter, 17, now, cap, count)
        return context, emitter

    def test_native_adapter_explicitly_labels_seed_and_relay_as_heard(self):
        # Do not silently inherit the DTO default when source adapters are added.
        body = method_body("HCAlertChain.c", "void NativeEmission(")
        self.assertIn("actor.Heard.Provenance = 1;", body)
        self.assertIn("emission.Clue.Provenance = 1;", body)
        context, emitter = self.seed()
        self.assertEqual(1, emitter.Heard.Provenance)
        self.assertEqual(1, context.m_Queue[0].Clue.Provenance)
        self.assertFalse(emitter.HeardExternally)

    def test_queue_hard_cap_16_root_cap_8_and_root_id_exhaustion(self):
        for queue_cap in (16, 17, 32, 100):
            context = chain()
            # Explicit live unrelated queue entries and seven retained roots.
            context.m_Roots = Array(root(i) for i in range(1, 8))
            context.m_NextRootId = 8
            context.m_Queue = Array(NS(Clue=SyntheticClue(observed=100, expires=130)) for _ in range(15))
            context.NativeEmission(actor(), 1, 100, queue_cap, 24)
            self.assertEqual(16, len(context.m_Queue))
            # A fresh inherited emitter avoids confusing the queue cap with
            # the independently full root cap.
            inherited = actor()
            inherited.Heard = SyntheticClue(observed=100, expires=130)
            inherited.HeardRootId = 1
            context.NativeEmission(inherited, 2, 100, queue_cap, 24)
            self.assertEqual(16, len(context.m_Queue))
            self.assertEqual(8, len(context.m_Roots))
        for queue_cap in (1, 2, 8):
            context = chain()
            for _ in range(queue_cap + 1):
                context.NativeEmission(actor(), 1, 100, queue_cap, 24)
            self.assertEqual(queue_cap, len(context.m_Queue))
        for queue_cap in (0, -1):
            context, _ = self.seed(cap=queue_cap)
            self.assertEqual([], context.m_Queue)
        context = chain()
        context.m_Roots = Array(root(i) for i in range(8))
        context.NativeEmission(actor(), 1, 100, 16, 24)
        self.assertEqual([], context.m_Queue)
        context = chain()
        context.m_NextRootId = 2000000000
        context.NativeEmission(actor(), 1, 100, 16, 24)
        self.assertEqual([], context.m_Queue)

    def test_server_alive_noncalm_and_tracked_limit_are_required(self):
        for count in (-1, 0, 25):
            context, _ = self.seed(count=count)
            self.assertEqual([], context.m_Queue)
        for entity in (None, SyntheticEntity(alive=False), SyntheticEntity(mind=0)):
            context, emitter = chain(), actor()
            emitter.InfectedEntity = entity
            context.NativeEmission(emitter, 1, 100, 16, 24)
            self.assertEqual([], context.m_Queue)
        context, _ = self.seed(chain(server=False))
        self.assertEqual([], context.m_Queue)

    def test_root_ttl_30_queue_window_2_and_no_lifetime_refresh(self):
        context, emitter = self.seed()
        self.assertEqual((100, 130), (context.m_Roots[0].RootObserved, context.m_Roots[0].RootExpires))
        self.assertEqual((100, .5, 130),
                         (context.m_Queue[0].Clue.Observed, context.m_Queue[0].Clue.Strength, context.m_Queue[0].Clue.Expires))
        context.Expire(102)
        self.assertEqual(1, len(context.m_Queue))
        context.Expire(102.001)
        self.assertEqual([], context.m_Queue)
        context.Expire(129.999)
        self.assertEqual(1, len(context.m_Roots))
        context.Expire(130)
        self.assertEqual([], context.m_Roots)
        for lifetime, expected in ((10, 110), (100, 130)):
            context, emitter = chain(), actor()
            emitter.ClueLifetime = lifetime
            context.NativeEmission(emitter, 1, 100, 16, 24)
            self.assertEqual(expected, context.m_Roots[0].RootExpires)

    def test_hops_attenuation_emitter_and_recipient_dedupe_inherit_root(self):
        context, emitter = self.seed()
        recipient, third = actor((1, 0, 0)), actor((2, 0, 0))
        actors = Array([emitter, recipient, third])
        self.assertEqual(3, context.ProcessPending(actors, 100, 3))
        self.assertEqual(1, recipient.Heard.Hops)
        self.assertEqual(.5, recipient.Heard.Strength)
        self.assertTrue(recipient.HeardExternally)
        self.assertEqual(110, recipient.NextHearing)
        self.assertEqual(0, recipient.SearchAttempts)
        context.NativeEmission(recipient, 18, 101, 16, 3)
        relay = context.m_Queue[-1]
        self.assertEqual((1, 100, 130), (relay.Root.RootId, relay.Root.RootObserved, relay.Root.RootExpires))
        self.assertEqual((2, .25, 130), (relay.Clue.Hops, relay.Clue.Strength, relay.Clue.Expires))
        size = len(context.m_Queue)
        context.NativeEmission(recipient, 19, 101, 16, 3)
        context.NativeEmission(emitter, 20, 101, 16, 3)
        self.assertEqual(size, len(context.m_Queue))
        # A synthetic recipient already holding second-hop evidence cannot relay.
        third.Heard, third.HeardRootId = relay.Clue, 1
        context.NativeEmission(third, 21, 101, 16, 3)
        self.assertEqual(size, len(context.m_Queue))
        before = list(relay.Root.Recipients)
        context.ProcessPending(actors, 101, 16)
        self.assertEqual(before, relay.Root.Recipients)

    def test_missing_inherited_root_cannot_seed_fresh_root(self):
        context, emitter = chain(), actor()
        emitter.Heard = SyntheticClue(observed=100, expires=130)
        emitter.HeardRootId = 123
        context.NativeEmission(emitter, 1, 100, 16, 24)
        self.assertEqual([], context.m_Roots)
        self.assertEqual([], context.m_Queue)

    def test_recipient_cap_12_work_limit_and_scan_limit_24(self):
        context, emitter = self.seed()
        actors = Array([emitter] + [actor((1, 0, 0)) for _ in range(23)])
        self.assertEqual(0, context.ProcessPending(actors, 100, 0))
        self.assertEqual(0, context.ProcessPending(actors, 100, -1))
        self.assertEqual(1, context.ProcessPending(actors, 100, 1))
        self.assertEqual(0, len(context.geometry_calls))  # seed scan charged
        self.assertEqual(2, context.ProcessPending(actors, 100, 2))
        self.assertEqual(2, len(context.geometry_calls))
        context.ProcessPending(actors, 100, 100)
        self.assertEqual(12, len(context.m_Roots[0].Recipients))
        self.assertEqual(11, len(context.geometry_calls))
        self.assertEqual([], context.m_Queue)
        # No recipient passes cooldown: every scan is still charged and finite.
        context, emitter = self.seed()
        for candidate in actors:
            candidate.NextHearing = 200
        self.assertEqual(25, context.ProcessPending(actors, 100, 100))
        self.assertEqual([], context.m_Queue)
        self.assertEqual([], context.geometry_calls)
        for invalid in (None, Array(), Array(actor() for _ in range(25))):
            context, _ = self.seed()
            self.assertEqual(0, context.ProcessPending(invalid, 100, 4))
            self.assertEqual(1, len(context.m_Queue))

    def test_radius_strength_cooldown_geometry_and_dead_recipients_fail_closed(self):
        for distance, next_hearing, alive, geometry, accepted in (
            (7.5, 100, True, True, True), (7.501, 0, True, True, False),
            (1, 101, True, True, False), (1, 0, False, True, False),
            (1, 0, True, False, False), (0, 0, True, True, False),
        ):
            with self.subTest(distance=distance, cooldown=next_hearing, geometry=geometry):
                context, emitter = self.seed(chain(geometry=geometry))
                recipient = actor((distance, 0, 0))
                recipient.NextHearing, recipient.InfectedEntity.alive = next_hearing, alive
                self.assertEqual(2, context.ProcessPending(Array([emitter, recipient]), 100, 2))
                self.assertEqual(accepted, recipient.HeardExternally)

    def test_recipient_rotation_and_two_bounded_geometry_tests_remain(self):
        context = chain()
        starts = []
        for _ in range(8):
            context.NativeEmission(actor(), 1, 100, 16, 24)
            starts.append(context.m_Queue[-1].StartCursor)
        self.assertEqual(list(range(8)), starts)
        body = method_body("HCAlertChain.c", "protected bool ClearGeometry(")
        self.assertEqual(2, body.count("DayZPhysics.RaycastRV("))
        self.assertIn("ObjIntersectView", body)
        self.assertIn("ObjIntersectFire", body)
        source = (SOURCE / "HCAlertChain.c").read_text()
        for forbidden in ("AddNoise(", "OnSoundVoiceEvent(", "GetTargetEntity(", "SetPosition("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
