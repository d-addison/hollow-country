"""HC-47 / #121: one synthetic stale/wall/unsupported/off behavior matrix.

Executes authored Enforce handlers through existing restricted ports. Fixtures
are synthetic; this proves neither geometry receipts nor DayZ behavior.
Spec/plan/task trace and native acceptance are lead-owned (HC-11 / HC-63).
RED: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_threat_matrix -v
     FAILED (failures=1): stale native target was damaged (damage list nonempty).
GREEN: same command -> Ran 1 test, OK. Offline only; runtime=PENDING.
"""
import math
import re
import tempfile
from pathlib import Path
from types import MethodType, SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import translate as scalar
from tests.unit.test_infected_admission import Array, translate
from tests.unit.test_infected_reach import policy
from tests.unit.test_v1_native_noise_vision import VisionWorld, Player, f32

WORLD = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/4_World'
NATIVE = WORLD / 'Infected/Reach/HCInfectedReachNative.c'
POLICY = WORLD / 'Infected/Reach/HCInfectedReachPolicy.c'
ROOMS = WORLD / 'Infected/HCInfectedRooms.c'
MINDS = N(MINDSTATE_CHASE=3, MINDSTATE_FIGHT=4)


class Vec(list):
    def __add__(self, other):
        if isinstance(other, str): other = [float(v) for v in other.split()]
        return Vec(a + b for a, b in zip(self, other))
    def __sub__(self, other): return Vec(a - b for a, b in zip(self, other))


class SyntheticSet(Array):
    def Get(self, index): return self[index]


class SyntheticContact:
    """Synthetic native targeting, ray output and damage recording ports."""
    METHODS = ('HCReachHitLegs', 'HCReachCurrentTarget', 'HCReachContactLine',
               'HCReachReleaseSteering', 'HCReachMove', 'GetPosition', 'IsAlive',
               'IsCrawling', 'IsBeingBackstabbed', 'GetInputController',
               'CanAttackToPosition', 'GetDayZInfectedType', 'StartCommand_Vault')

    def __init__(self):
        self.target = N(IsAlive=lambda: True, GetMeleeTargetType=lambda: 0,
                        GetCommand_Vehicle=lambda: None, GetMeleeFightLogic=lambda: None,
                        GetPosition=lambda: Vec([0., 1., 1.]))
        self.current = self.target
        self.mind = MINDS.MINDSTATE_FIGHT
        self.native_reach = True
        self.wall = False
        self.damage = []
        self.rays = []
        self.steering = []
        self.started = []
        self.controller = N(GetTargetEntity=lambda: self.current,
                            GetMindState=lambda: self.mind,
                            OverrideMovementSpeed=lambda *a: self.steering.append(a),
                            OverrideHeading=lambda *a: self.steering.append(a))
        self.z = N(m_ActualTarget=self.target, m_HCReachPlayer=self.target,
                   m_HCReachAttack=N(m_Distance=1.7, m_AmmoType='SyntheticMelee'),
                   m_HCReachSteering=False, m_DamageHitToProcess=False,
                   GetPosition=lambda: Vec([0., 0., 0.]),
                   IsAlive=lambda: True, IsCrawling=lambda: False,
                   IsBeingBackstabbed=lambda: False,
                   GetInputController=lambda: self.controller,
                   CanAttackToPosition=lambda aim: self.native_reach,
                   GetDayZInfectedType=lambda: N(ChooseAttack=lambda *a: None),
                   StartCommand_Vault=lambda *a: self.started.append(a))
        self.p = policy()
        for name, value in re.findall(r'static const vector (HC_CONTACT_\w+) = "([^"]+)";', POLICY.read_text()):
            setattr(self.p, name, Vec(float(v) for v in value.split()))
        self.p.HCThreatTakeContact = lambda: True  # explicit synthetic admitted budget
        def ray(origin, finish, contact, normal, component, hits, *args):
            self.rays.append((origin, finish))
            # A wall even arbitrarily close to the shin cannot mean hitTarget.
            hits.Insert(N(GetHierarchyRoot=lambda: None) if self.wall else self.target)
            return True
        self.reach = N(LineCheck=lambda *a: True, CountStrike=lambda *a: None,
                       Landed=lambda *a: None, StateFor=lambda *a: None)
        env = dict(this=self.z, PlayerBase=N(Cast=lambda value: value),
                   EntityAI=N(Cast=lambda value: value if hasattr(value, 'GetHierarchyRoot') else None),
                   DayZInfectedConstants=MINDS, HCInfectedReachPolicy=self.p,
                   DayZPhysics=N(RaycastRV=ray), SyntheticSet=SyntheticSet, ObjIntersectFire=0,
                   EMeleeTargetType=N(NONALIGNABLE=-1), GetGame=lambda: N(GetTickTime=lambda: 10.),
                   vector=N(Distance=lambda a, b: math.dist(a, b)),
                   DamageSystem=N(CloseCombatDamageName=lambda *a: self.damage.append(a)))
        source = NATIVE.read_text()
        # The existing port needs a named declaration for the synthetic native
        # set's Count/Get/Insert surface. Only the type spelling changes.
        with tempfile.TemporaryDirectory() as temporary:
            port_source = Path(temporary) / 'HCThreatPort.c'
            port_source.write_text(source.replace('set<Object>', 'SyntheticSet'))
            for name in self.METHODS:
                if name.startswith('HCReach') and name + '(' in source:
                    signature = ('protected bool ' if name in ('HCReachCurrentTarget', 'HCReachContactLine', 'HCReachMove')
                                 else 'protected void ') + name + '('
                    fn = translate(str(port_source), signature, self.METHODS, **env)
                    fn.__globals__['Math'].Sqrt = math.sqrt
                    fn.__globals__['Math'].RandomInt = lambda low, high: low
                    setattr(self.z, name, MethodType(fn, self.z))
        # Existing handler uses this slot only when it actually applies damage.
        self.z.m_HCReachSlot = 0


class ThreatMatrix(unittest.TestCase):
    def test_current_target_wall_native_refusal_and_off_matrix(self):
        s = SyntheticContact()
        s.current = object()  # native retarget between start and WasHit
        s.z.HCReachHitLegs(s.reach)
        self.assertEqual([], s.damage, 'stale native target was damaged')
        self.assertEqual([], s.rays, 'stale target must refuse before native geometry work')
        s.current = s.target
        s.wall = True
        s.z.HCReachHitLegs(s.reach)
        self.assertEqual([], s.damage, 'near-target wall was accepted as a floor/reach receipt')
        s.wall = False
        s.native_reach = False
        s.z.HCReachHitLegs(s.reach)
        self.assertEqual([], s.damage, 'native reach refusal was bypassed')
        s.native_reach = True
        s.mind = 0
        s.z.HCReachHitLegs(s.reach)
        self.assertEqual([], s.damage, 'disengaged infected applied a stale hit')
        s.mind = MINDS.MINDSTATE_FIGHT
        s.z.HCReachHitLegs(s.reach)
        self.assertEqual(1, len(s.damage), 'current native-reachable unoccluded contact should remain supported')
        s.z.HCReachHitLegs(None)
        self.assertEqual(1, len(s.damage), 'off service must not apply damage')

        self.assertFalse(s.p.HCExtendedReachSupported())
        self.assertFalse(s.p.HCForcedMovementSupported())
        state = N(Target=s.target, Phase=1, VaultType=1, NextStrike=100.)
        s.z.HCReachMove(s.reach, state)
        self.assertEqual([], s.steering, 'unsupported geometry must preserve native movement')
        self.assertEqual([], s.started, 'a room/floor ray is not a vault landing receipt')
        self.assertFalse(scalar(ROOMS.read_text(), 'HCThreatRoomReachSupported', {})())

        # Execute the shared unit budget, with a synthetic monotonic server clock.
        now = [10.]
        budget_source = (WORLD / 'Core/HCUnitBudget.c').read_text()
        budget = N()
        for name in ('HCReset', 'HCTake'):
            setattr(budget, name, MethodType(scalar(budget_source, name, {}, 'HCUnitBudget', True), budget))
        s.p.s_HCThreatBudget = budget
        s.p.s_HCThreatBudgetAfter = 0.
        take = translate(str(POLICY), 'static bool HCThreatTakeContact(', (),
                         statics=('s_HCThreatBudget', 's_HCThreatBudgetAfter'), STATICS=s.p,
                         HCUnitBudget=lambda: budget,
                         GetGame=lambda: N(IsServer=lambda: True, GetTickTime=lambda: now[0]))
        self.assertEqual(16, sum(take(None) for _ in range(30)))
        now[0] += 1.
        self.assertTrue(take(None))
        s.p.HCThreatTakeContact = lambda: take(None)
        s.wall = True
        now[0] += 1.
        before = len(s.rays)
        self.assertFalse(any(s.z.HCReachContactLine(s.target) for _ in range(30)))
        self.assertEqual(16, len(s.rays) - before, 'closed door/wall refusal must also bound ray work')
        reset = translate(str(POLICY), 'static void HCThreatResetBudget(', (),
                          statics=('s_HCThreatBudget', 's_HCThreatBudgetAfter'), STATICS=s.p)
        reset(None)
        self.assertIsNone(s.p.s_HCThreatBudget)
        self.assertTrue(take(None), 'restart must allocate/reset the contact budget')
        s.z.m_HCReachSteering = True
        s.z.HCReachReleaseSteering()
        s.z.HCReachReleaseSteering()
        self.assertEqual([(False, 0), (False, 0)], s.steering, 'release clears both overrides once')

        world = VisionWorld()
        gate = world.ns['HCInfectedVisionQualification']
        gate.HCThreatReset(False)
        self.assertEqual('off', gate.HCThreatState())
        self.assertEqual(f32(.9), world.callbacks(Player()).GetMaxVisionRangeModifier(object()))
        self.assertEqual(1, len(world.log), 'off vision must not probe markers or read player factors')
        gate.HCThreatReset(True)
        self.assertEqual('pending', gate.HCThreatState())
        world.callbacks(Player()).GetMaxVisionRangeModifier(object())
        self.assertEqual('on', gate.HCThreatState())
        summary = scalar(POLICY.read_text(), 'HCThreatSummary',
                         dict(HCInfectedReachPolicy=s.p, HCInfectedVisionQualification=gate,
                              HCInfectedRoomCatalog=N(HCThreatRoomReason=lambda: 'room_path_receipts_pending')),
                         'HCInfectedReachPolicy')
        self.assertIn('[HC Plan] HC-47 reach=refused vision=on refusals=3', summary(True))
        self.assertIn('reach=off', summary(False))
        self.assertIn('runtime=PENDING', summary(True))


if __name__ == '__main__': unittest.main()
