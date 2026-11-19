"""HC-8: authored door handlers on explicit synthetic engine ports.

Restricted translations execute the shipped watcher, pressure and shared
budgets. No Python gameplay policy, DayZ compile, AI/audio or replication proof.

HC-8 / #121 / #151 TDD receipt (spec/plan/task integration owned by HC-11):
RED: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_infected_doors -v
     FAILED (failures=3, errors=2), including the actual behavioral failure:
     AssertionError: ('open', 34) not found in [] : door index 34 was never serviced in the large building
     Protected attachment refusal also failed: AssertionError: 2 != 1.
     NPC-target refusal also failed: AssertionError: 0 != 2.
RED after adding four protected doors ahead of index 34: same command,
     FAILED (failures=1), same index-34 assertion (hot-priority starvation).
GREEN: same command -> Ran 5 tests, OK.
Native APIs cited in HCInfectedDoors.c; runtime acceptance pending.
"""
from tests.unit.test_c1_infectedcfg import tuning_fixture
from pathlib import Path
import re
from types import MethodType, SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import translate as scalar
from tests.unit.test_infected_admission import Array, translate
from tests.unit.test_infected_doors import constants, MINDS

WORLD = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts/4_World"
DOORS = WORLD / "Infected/Doors"


class Vec(list):
    def __sub__(self, other): return Vec(a - b for a, b in zip(self, other))


class SyntheticBuilding:
    """Synthetic ordinary building: only index 34 is closed and locked."""
    def __init__(self, count=70, protected=False):
        self.count = count
        self.closed = {34}
        self.locked = True
        self.protected = protected
        self.deleted = False
        self.reads = []
        self.actions = []
        self.allow_open = True
        self.info = N(m_LockCompatibilityBitMask=2, m_RelatedInventorySlotNames=None)
        self.holder = N(GetSingleDoorInfo=lambda index: self.info)
        self.attachments = {}
    def GetDoorCount(self): return self.count
    def IsPendingDeletion(self): return self.deleted
    def IsDoorClosed(self, index):
        assert 0 <= index < self.count, "out-of-range native door index"
        self.reads.append(index)
        return index in self.closed
    def GetDoorSoundPos(self, index): return Vec([0., 0., 0.])
    def IsDoorLocked(self, index): return self.locked
    def GetDoorInfoHolder(self): return self.holder
    def FindAttachmentBySlotName(self, name): return self.attachments.get(name)
    def CanDoorBeOpened(self, request):
        self.actions.append(("check", request.m_DoorIndex, request.m_CheckIfLocked))
        return self.allow_open  # explicit synthetic native/modded opening verdict
    def UnlockDoor(self, index, animate):
        self.actions.append(("unlock", index, animate))
        self.locked = False
    def OpenDoor(self, index):
        self.actions.append(("open", index))
        self.closed.discard(index)
    def PlayDoorSound(self, index): self.actions.append(("sound", index))
    def GetType(self): return "SyntheticTenement"


def shared_budget(path, owner, fields, methods, game):
    obj = N(**fields)
    env = dict(GetGame=lambda: game, Print=lambda text: None)
    for name in methods:
        fn = scalar(path.read_text(), name, env, owner, True)
        if owner == "HCWorkBudget" and name == "HCReset":
            fn.__defaults__ = (4,)  # translator omits the authored optional milliseconds argument
        setattr(obj, name, MethodType(fn, obj))
    return obj


class BoundedBuildingDoors(unittest.TestCase):
    def setUp(self):
        self.policy = constants((DOORS / "HCInfectedDoorPolicy.c").read_text())
        self.player = N(IsAlive=lambda: True, GetIdentity=lambda: object(),
                        GetPosition=lambda: Vec([0., 0., 1.]))
        self.players = Array([self.player])
        self.target = self.player
        self.infected = N(IsAlive=lambda: True, IsCrawling=lambda: False,
                          IsZombieMilitary=lambda: True, GetType=lambda: "SyntheticMilitary",
                          GetPosition=lambda: Vec([0., 0., -1.]),
                          GetInputController=lambda: N(GetMindState=lambda: MINDS.MINDSTATE_CHASE,
                                                       GetTargetEntity=lambda: self.target))
        self.buildings = Array([SyntheticBuilding()])
        self.noises = []
        self.logs = []
        self.queries = []
        def query(position, radius, objects, proxies):
            self.queries.append(radius)
            objects.extend(self.buildings if radius == tuning_fixture().Get().Doors.WatchRadius else [self.infected])
        self.game = N(IsServer=lambda: True, GetTickTime=lambda: 0., GetObjectsAtPosition3D=query)
        policy_text = (DOORS / "HCInfectedDoorPolicy.c").read_text()
        scalar_env = dict(HCInfectedTuning=tuning_fixture(), HCInfectedDoorPolicy=self.policy, DayZInfectedConstants=MINDS,
                          Math=N(Min=min, Max=max))
        for name in ("HeavyClass", "Kind", "Pursuing", "PlayerQualifies", "Expired"):
            setattr(self.policy, name, scalar(policy_text, name, scalar_env, "HCInfectedDoorPolicy"))
        advance = scalar(policy_text, "HCAdvance", scalar_env, "HCInfectedDoorPressure", True)
        def pressure():
            obj = N(m_Building=None, m_Index=0, m_Player=None, m_WatchUntil=0.,
                    m_LastHot=-1000., m_Pressure=0., m_Hits=0, m_NextHit=0.,
                    m_OpenNeeded=8, m_HitsNeeded=5, m_CooldownUntil=0., m_VisitedAt=-1.)
            obj.HCAdvance = MethodType(advance, obj)
            return obj
        env = dict(HCInfectedTuning=tuning_fixture(), HCInfectedDoorPolicy=self.policy, GetGame=lambda: self.game,
                   HCPerfPlayers=N(HCGet=lambda: self.players),
                   Building=N(Cast=lambda value: value if isinstance(value, SyntheticBuilding) else None),
                   Bunker=N(Cast=lambda value: value if value.protected else None),
                   ContainerLockedBase=N(Cast=lambda value: None),
                   PlayerBase=N(Cast=lambda value: value if value is self.player else None),
                   ZombieBase=N(Cast=lambda value: value if value is self.infected else None),
                   ItemBase=N(Cast=lambda value: value), EBuildingLockType=N(LOCKPICK=1),
                   HCInfectedDoorPressure=pressure,
                   HCInfectedDoorScan=lambda: N(m_Building=None, m_NextIndex=0, m_WatchUntil=0.),
                   DoorManipulationParams=lambda: N(), Print=self.logs.append,
                   HCV2Admission=N(Line=lambda *args: "synthetic admission"),
                   HCSearchNoise=N(EmitAt=lambda *args: self.noises.append(args)),
                   vector=N(DistanceSq=lambda a, b: sum((x-y)**2 for x, y in zip(a, b)),
                            Dot=lambda a, b: sum(x*y for x, y in zip(a, b))))
        env["HCWorkBudget"] = lambda: shared_budget(WORLD / "World/HCWorkBudget.c", "HCWorkBudget",
            dict(m_LogAfter=0.), ("HCReset", "HCMayContinue", "HCContinue", "HCDeferred"), self.game)
        env["HCUnitBudget"] = lambda: shared_budget(WORLD / "Core/HCUnitBudget.c", "HCUnitBudget",
            {}, ("HCReset", "HCTake", "HCUsed"), self.game)
        self.module = N(m_Running=False, m_Printed=False, m_PlayerCursor=0, m_DoorCursor=0,
                        m_Hits=0, m_Opened=0, m_Broken=0, m_Refused=0, m_Full=0)
        source = (DOORS / "HCInfectedDoors.c").read_text().split("modded class HCModuleRegistry", 1)[0]
        methods = re.findall(r"^\s*(?:(?:protected|override)\s+)*(\w+ (\w+)\([^\n]*\))", source, re.M)
        names = tuple(name for _, name in methods)
        for signature, name in methods:
            fn = translate(str(DOORS / "HCInfectedDoors.c"), signature, names, **env)
            fn.__globals__["Math"].RandomIntInclusive = lambda low, high: low
            setattr(self.module, name, MethodType(fn, self.module))
        self.module.OnStart(N(EnableInfected=True))

    def test_index_34_is_serviced_and_cooldown_survives_cursor_wrap(self):
        b = self.buildings[0]
        b.closed.update(range(4))
        protected = N(m_LockCompatibilityBitMask=0, m_RelatedInventorySlotNames=None)
        b.holder.GetSingleDoorInfo = lambda index: protected if index < 4 else b.info
        retained = None
        for _ in range(45):
            self.module.OnTick(1.)
            if retained is None:
                retained = next((row for row in self.module.m_Doors if row.m_Index == 34), None)
        self.assertIn(("open", 34), self.buildings[0].actions,
                      "door index 34 was never serviced in the large building")
        self.assertEqual(1, self.module.m_Broken, "cursor wrap must retain the per-door cooldown")
        self.assertIs(retained, next(row for row in self.module.m_Doors if row.m_Index == 34))
        self.assertGreater(retained.m_CooldownUntil, self.module.m_Clock)
        self.assertIn(("unlock", 34, False), self.buildings[0].actions)
        self.assertIn(("check", 34, False), self.buildings[0].actions)
        self.assertTrue(self.noises, "reuse the real-noise port")

    def test_index_budget_yields_without_restarting_and_count_changes_are_safe(self):
        b = self.buildings[0]
        self.module.m_IndexBudget.HCReset(1)
        self.module.WatchAround(self.player)
        self.assertEqual([0], b.reads)
        self.module.m_IndexBudget.HCReset(1)
        self.module.WatchAround(self.player)
        self.assertEqual([0, 1], b.reads)
        b.count = 1
        self.module.m_IndexBudget.HCReset(1)
        self.module.WatchAround(self.player)
        self.assertEqual([0, 1, 0], b.reads)
        # Whole-tick cap across two player visits and four large buildings.
        self.buildings = Array(SyntheticBuilding() for _ in range(4))
        self.players.append(self.player)
        self.module.OnTick(1.)
        self.assertEqual(64, sum(len(x.reads) for x in self.buildings))
        self.assertLessEqual(sum(len(x.reads) for x in self.buildings), self.policy.MAX_DOOR_INDICES_PER_TICK)
        # An absent/deleted building leaves neither pressure nor scan state.
        self.buildings[0].deleted = True
        self.buildings.clear()
        for _ in range(12): self.module.OnTick(1.)
        self.assertEqual([], self.module.m_Scans)

    def test_heavy_native_lock_is_vulnerable_but_protected_locks_refuse(self):
        b = self.buildings[0]
        self.assertEqual(self.policy.LOCK_BREAKABLE, self.module.LockState(b, 34))
        b.info.m_LockCompatibilityBitMask = 0
        self.assertEqual(self.policy.LOCK_PROTECTED, self.module.LockState(b, 34))
        b.info.m_LockCompatibilityBitMask = 2
        b.info.m_RelatedInventorySlotNames = Array(["SyntheticCodeLock"])
        b.attachments["SyntheticCodeLock"] = N(IsExternalLockType=lambda: True)
        self.assertEqual(self.policy.LOCK_PROTECTED, self.module.LockState(b, 34))
        b.info.m_RelatedInventorySlotNames = Array(["unknown"] * 100)
        self.assertEqual(self.policy.LOCK_PROTECTED, self.module.LockState(b, 34))
        b.holder = None
        self.assertEqual(self.policy.LOCK_PROTECTED, self.module.LockState(b, 34))
        b.protected = True
        self.assertFalse(self.module.Eligible(b), "bunkers never enter pressure scanning")

    def test_crawling_dead_and_unproven_human_ai_targets_refuse(self):
        entry = N(m_Player=self.player)
        pos = Vec([0., 0., 0.])
        self.assertEqual(self.policy.KIND_HEAVY, self.module.Qualify(self.infected, entry, pos))
        self.infected.IsCrawling = lambda: True
        self.assertEqual(self.policy.KIND_NONE, self.module.Qualify(self.infected, entry, pos))
        self.infected.IsCrawling = lambda: False
        self.infected.IsAlive = lambda: False
        self.assertEqual(self.policy.KIND_NONE, self.module.Qualify(self.infected, entry, pos))
        self.infected.IsAlive = lambda: True
        self.player.GetIdentity = lambda: None  # synthetic PlayerBase subclass NPC
        self.assertEqual(self.policy.KIND_NONE, self.module.Qualify(self.infected, entry, pos))

    def test_stop_off_and_restart_drop_all_transient_work(self):
        self.module.OnTick(1.)
        self.module.OnStop()
        self.assertIsNone(self.module.m_Scans)
        self.assertIsNone(self.module.m_IndexBudget)
        before = len(self.queries)
        self.module.OnTick(1.)
        self.module.OnStart(N(EnableInfected=False))
        self.module.OnTick(1.)
        self.assertEqual(before, len(self.queries))
        self.module.OnStart(N(EnableInfected=True))
        self.assertEqual([], self.module.m_Scans)
        self.assertEqual(0, self.module.m_PlayerCursor)
        self.assertEqual(0, self.module.m_DoorCursor)
        self.assertTrue(any("[HC Plan] HC-8 door_cursor=bounded max_indices=" in line
                            and "state=on" in line and "runtime=PENDING" in line for line in self.logs))


if __name__ == "__main__":
    unittest.main()
