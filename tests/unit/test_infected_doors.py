"""#136 offline smoke: authored infected door-pressure policy on explicit synthetic inputs.

Executes restricted translations of the shipped scalar policy and per-door
state machine. It is not an Enforce compile and establishes nothing about
DayZ AI, door replication, door sounds or native noise perception.

A separate module because the concurrent infected capability worker owns
test_infected_variants.py / admission tests.
"""
from pathlib import Path
from types import SimpleNamespace as N
import math
import re
import unittest

from tests.unit.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2]
DOORS = ROOT / 'mods/HollowCountry/scripts/4_World/Infected/Doors'
POLICY = DOORS / 'HCInfectedDoorPolicy.c'
# Synthetic stand-in for the native enum order at 3_Game/Entities/DayZInfected.c:13-18.
MINDS = N(MINDSTATE_CALM=0, MINDSTATE_DISTURBED=1, MINDSTATE_ALERTED=2,
          MINDSTATE_CHASE=3, MINDSTATE_FIGHT=4, MINDSTATE_COWER=5)


def constants(text):
    values = {}
    for name, value in re.findall(r'static const (?:int|float) (\w+) = ([\d.]+);', text):
        values[name] = float(value) if '.' in value else int(value)
    return N(**values)


class InfectedDoorSmoke(unittest.TestCase):
    def test_w6_variant_door_pressure_opens_bashes_and_refuses(self):
        self.assertTrue(POLICY.is_file(), 'missing authored #136 HCInfectedDoorPolicy.c')
        text = POLICY.read_text()
        policy = constants(text)
        env = dict(HCInfectedDoorPolicy=policy, DayZInfectedConstants=MINDS,
                   Math=N(Min=min, Max=max, AbsFloat=abs, Floor=math.floor))
        for name in ('HeavyClass', 'Kind', 'Pursuing', 'PlayerQualifies', 'Expired'):
            setattr(policy, name, translate(text, name, env, 'HCInfectedDoorPolicy'))
        advance = translate(text, 'HCAdvance', env, 'HCInfectedDoorPressure', member=True)
        NONE, HIT, OPEN, BREAK = policy.ACTION_NONE, policy.ACTION_HIT, policy.ACTION_OPEN, policy.ACTION_BREAK
        WEAK, COMMON, HEAVY = policy.KIND_NONE, policy.KIND_COMMON, policy.KIND_HEAVY

        # Variant mapping: crawlers/dead cannot; soldiers and big workers bash.
        self.assertEqual(WEAK, policy.Kind(True, True, False, 'ZmbM_CitizenASkinny_Brown'))
        self.assertEqual(WEAK, policy.Kind(False, False, True, 'ZmbM_SoldierNormal'))
        self.assertEqual(COMMON, policy.Kind(True, False, False, 'ZmbF_CitizenANormal_Blue'))
        self.assertEqual(HEAVY, policy.Kind(True, False, True, 'ZmbM_PatrolNormal_Autumn'))
        for heavy in ('ZmbM_FirefighterNormal', 'ZmbM_HeavyIndustryWorker',
                      'ZmbM_ConstrWorkerNormal_Beige', 'ZmbM_PolicemanSpecForce'):
            self.assertEqual(HEAVY, policy.Kind(True, False, False, heavy), heavy)
        self.assertEqual(WEAK, policy.Kind(True, True, False, 'ZmbM_FirefighterNormal'))

        # Not omniscient: only alerted/chasing/fighting minds count.
        self.assertEqual([False, False, True, True, True, False],
                         [policy.Pursuing(mind) for mind in range(6)])
        # Player must be near the door, or within 8 m on the far side.
        self.assertFalse(policy.PlayerQualifies(100.0, -1.0))
        self.assertFalse(policy.PlayerQualifies(16.0, 0.5))
        self.assertTrue(policy.PlayerQualifies(16.0, -0.5))
        self.assertTrue(policy.PlayerQualifies(4.0, 1.0))

        def door(open_needed=8, hits_needed=5):
            return N(m_LastHot=-1000.0, m_Pressure=0.0, m_Hits=0, m_NextHit=0.0,
                     m_OpenNeeded=open_needed, m_HitsNeeded=hits_needed, m_CooldownUntil=0.0)

        def run(state, kind, lock, times):
            return [advance(state, kind, lock, float(t)) for t in times]

        # Common: sustained pressure opens an unlocked door after its roll, once.
        common = door(open_needed=8)
        actions = run(common, COMMON, 0, range(0, 9))
        self.assertEqual([NONE] * 8 + [OPEN], actions)
        cooldown = common.m_CooldownUntil
        self.assertGreaterEqual(cooldown - 8, 30)
        self.assertEqual([NONE] * 5, run(common, COMMON, 0, range(9, 14)))
        # A gap longer than the grace resets pressure (sustained, not cumulative).
        gap = door(open_needed=6)
        run(gap, COMMON, 0, (0, 1, 2, 3))
        run(gap, WEAK, 0, (4, 5, 6, 7, 8))
        self.assertEqual([NONE] * 6 + [OPEN], run(gap, COMMON, 0, range(9, 16)))
        # Common never opens a locked door; weak never acts.
        self.assertEqual([NONE] * 20, run(door(), COMMON, 1, range(20)))
        self.assertEqual([NONE] * 20, run(door(), WEAK, 0, range(20)))

        # Heavy: paced hits, final hit breaks a lockpick-class lock.
        heavy = door(hits_needed=5)
        actions = run(heavy, HEAVY, 1, range(0, 9))
        self.assertEqual([HIT, NONE, HIT, NONE, HIT, NONE, HIT, NONE, BREAK], actions)
        self.assertEqual([NONE] * 3, run(heavy, HEAVY, 1, (9, 10, 11)))
        unlocked = door(hits_needed=4)
        self.assertEqual(OPEN, run(unlocked, HEAVY, 0, range(0, 7))[-1])
        # Heavy cannot defeat a non-lockpick lock (containers, code locks).
        self.assertEqual([NONE] * 12, run(door(), HEAVY, 2, range(12)))

        # Bounded table expiry: watched or cooling entries remain.
        self.assertFalse(policy.Expired(10.0, 12.0, 0.0))
        self.assertFalse(policy.Expired(10.0, 5.0, 40.0))
        self.assertTrue(policy.Expired(10.0, 5.0, 9.0))
        self.assertEqual(64, policy.MAX_DOORS)
        self.assertLessEqual(policy.DOORS_PER_TICK, 4)
        self.assertLessEqual(policy.PLAYERS_PER_TICK, 2)


if __name__ == '__main__':
    unittest.main()
