"""S3 car repair: AI mechanics repair real cars with real parts.

Authored static policy methods run through the same small Enforce-to-Python
syntax adapter the other Expansion AI tests use (Authored). Only syntax is
adapted; every decision (selection, coverage, claim, attach order) stays in the
authored C. Cars, parts, inventories and groups are explicit synthetic
fixtures. Offline tests never establish DayZ behavior.
"""
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.legacy.test_expansion_ai_adapter import Authored

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "mods/HollowCountryExpansionAI/scripts/4_World"
POLICY = SCRIPTS / "HCXAICarRepairPolicy.c"
REPAIR = SCRIPTS / "HCXAICarRepair.c"
CONFIG = ROOT / "mission/hollow-country/ai/car-repair.json"


class A(list):
    def __bool__(self): return True
    def Count(self): return len(self)
    def Insert(self, x): self.append(x); return len(self) - 1
    def Get(self, i): return self[i]
    def Find(self, x): return self.index(x) if x in self else -1


def consts(source):
    return {m[2]: int(m[3]) if re.fullmatch(r"-?\d+", m[3]) else float(m[3])
            for m in re.finditer(r"static const (int|float) (\w+)\s*=\s*([-\d.]+);", source)}


def adapt_types(source):
    # Syntax adaptation: native class names the adapter does not know are
    # declared as EntityAI locals; no behavior is changed.
    return re.sub(r"\b(?:InventoryLocation|CarScript|ItemBase)\s+(\w+)\s*=", r"EntityAI \1 =", source)


class FakeWorld:
    def __init__(self):
        self.created = []   # any spawn would land here; must stay empty
        self.deleted = []
        self.moves = []


class FakeLocation:
    def __init__(self): self.slot = -1
    def GetSlot(self): return self.slot


class FakeInventory:
    def __init__(self, owner, world):
        self.owner, self.world = owner, world
        self.free_slot = 7          # slot the car offers; None means full
        self.fail_take = False
        self.fail_drop = False
    def FindFreeLocationFor(self, item, flags, loc):
        if self.free_slot is None: return False
        loc.slot = self.free_slot
        return True
    def TakeEntityAsTargetAttachmentEx(self, mode, target, item, slot):
        if self.fail_take: return False
        item.parent = target
        target.attached[slot] = item
        self.world.moves.append(("attach", item.name, slot, mode))
        return True
    def DropEntity(self, mode, owner, item):
        if self.fail_drop: return False
        for key, value in list(owner.attached.items()):
            if value is item: del owner.attached[key]
        item.parent = None
        self.free_slot = 7
        self.world.moves.append(("drop", item.name, mode))
        return True


class FakeEntity:
    def __init__(self, name, world, parent=None):
        self.name, self.parent, self.attached = name, parent, {}
        self.inv = FakeInventory(self, world)
    def GetInventory(self): return self.inv
    def GetHierarchyParent(self): return self.parent


class Fixture(unittest.TestCase):
    def setUp(self):
        self.policy_source = POLICY.read_text()
        self.consts = consts(self.policy_source)
        self.world = FakeWorld()
        self.env = {
            "A": A,
            "vector": N(DistanceSq=lambda a, b: sum((x - y) ** 2 for x, y in zip(a, b))),
            "Math": N(Max=max, Min=min),
            "GameConstants": N(STATE_RUINED=4, STATE_BADLY_DAMAGED=3, STATE_DAMAGED=2, STATE_WORN=1,
                               STATE_PRISTINE=0, DAMAGE_DAMAGED_VALUE=0.5,
                               DAMAGE_BADLY_DAMAGED_VALUE=0.3, DAMAGE_RUINED_VALUE=0.0),
            "InventoryMode": N(SERVER="SERVER"),
            "FindInventoryLocationType": N(ATTACHMENT="ATTACHMENT"),
            "InventoryLocation": FakeLocation,
        }
        self.env["EntityAI"] = FakeEntity
        self.authored = Authored(adapt_types(self.policy_source), self.env)
        outer = self

        class Policy:
            def __getattr__(self, name):
                return lambda *args: outer.authored.call(name, None, *args)
        self.env["HCXAICarRepairPolicy"] = Policy()
        for key, value in self.consts.items():
            setattr(self.env["HCXAICarRepairPolicy"].__class__, key, value)
        self.P = self.env["HCXAICarRepairPolicy"]

    def car(self, pos=(100.0, 0.0, 0.0), wheels=0, mask=0, engine=0, unrepairable=False,
            claim=0, until=0, attempts=0, next_at=0):
        return N(Pos=pos, WheelNeed=wheels, PartMask=mask, EngineSteps=engine,
                 Unrepairable=unrepairable, ClaimGroup=claim, ClaimUntil=until,
                 Attempts=attempts, NextAt=next_at)


class CarSelectionTests(Fixture):
    def test_nearest_damaged_car_within_radius_is_chosen(self):
        near, far, fine = self.car(pos=(50.0, 0.0, 0.0), wheels=1), self.car(pos=(300.0, 0.0, 0.0), mask=2), self.car(pos=(10.0, 0.0, 0.0))
        picked = self.P.HCPickCar(A([far, fine, near]), (0.0, 0.0, 0.0), 400.0, 5, 1000, 3)
        self.assertIs(picked, near)

    def test_car_beyond_config_radius_is_not_known_work(self):
        self.assertIsNone(self.P.HCPickCar(A([self.car(pos=(900.0, 0.0, 0.0), wheels=2)]), (0.0, 0.0, 0.0), 400.0, 5, 1000, 3))

    def test_other_groups_live_claim_excludes_car_but_expired_claim_does_not(self):
        held = self.car(wheels=1, claim=9, until=2000)
        self.assertIsNone(self.P.HCPickCar(A([held]), (0.0, 0.0, 0.0), 400.0, 5, 1000, 3))
        self.assertIs(self.P.HCPickCar(A([held]), (0.0, 0.0, 0.0), 400.0, 5, 2000, 3), held)
        self.assertIs(self.P.HCPickCar(A([held]), (0.0, 0.0, 0.0), 400.0, 9, 1000, 3), held)

    def test_unrepairable_exhausted_and_cooling_cars_are_skipped(self):
        cars = A([self.car(wheels=1, unrepairable=True), self.car(wheels=1, attempts=3), self.car(wheels=1, next_at=5000)])
        self.assertIsNone(self.P.HCPickCar(cars, (0.0, 0.0, 0.0), 400.0, 5, 1000, 3))

    def test_need_count_adds_wheels_parts_and_engine_steps(self):
        e = self.car(wheels=2, mask=self.consts["PART_SPARK"] | self.consts["PART_BATTERY"], engine=1)
        self.assertEqual(self.P.HCNeedCount(e), 5)
        self.assertEqual(self.P.HCNeedCount(self.car()), 0)


class PartCoverageTests(Fixture):
    def test_repair_is_refused_when_members_and_stash_lack_a_wheel(self):
        self.assertEqual(self.P.HCCoverage(2, 0, 0, 1, 0, False), "carfix_no_wheels")

    def test_repair_is_refused_without_the_missing_spark_plug(self):
        mask = self.consts["PART_SPARK"] | self.consts["PART_BATTERY"]
        self.assertEqual(self.P.HCCoverage(0, mask, 0, 0, self.consts["PART_BATTERY"], False), "carfix_no_parts")

    def test_engine_steps_need_a_working_torch_and_full_coverage_is_empty_reason(self):
        self.assertEqual(self.P.HCCoverage(0, 0, 2, 0, 0, False), "carfix_no_tool")
        self.assertEqual(self.P.HCCoverage(1, 4, 2, 3, 4, True), "")

    def test_engine_repair_mirrors_native_one_level_band(self):
        # ActionRepairVehiclePartBase.c:48-62: level-1 clamped at WORN, then band base + jitter.
        self.assertEqual(self.P.HCEngineNextLevel(3), 2)
        self.assertEqual(self.P.HCEngineNextLevel(1), 1)
        self.assertAlmostEqual(self.P.HCEngineHealth(100.0, 3, 7.0), 7.0)
        self.assertAlmostEqual(self.P.HCEngineHealth(100.0, 2, 7.0), 37.0)
        self.assertAlmostEqual(self.P.HCEngineHealth(100.0, 1, 7.0), 57.0)


class RealPartAttachTests(Fixture):
    def attach(self, car, item, occupant=None):
        return self.P.HCAttach(car, item, occupant)

    def test_attach_moves_the_carried_item_into_the_slot_without_spawning(self):
        car, wheel = FakeEntity("car", self.world), FakeEntity("wheel", self.world, parent="member")
        self.assertEqual(self.attach(car, wheel), 0)
        self.assertIs(wheel.parent, car)
        self.assertIs(car.attached[7], wheel)
        self.assertEqual((self.world.created, self.world.deleted), ([], []))
        self.assertEqual(self.world.moves, [("attach", "wheel", 7, "SERVER")])

    def test_ruined_occupant_is_dropped_never_deleted_before_replacement(self):
        car = FakeEntity("car", self.world)
        ruined = FakeEntity("ruined", self.world, parent=car)
        car.attached[3] = ruined
        plug = FakeEntity("plug", self.world, parent="member")
        self.assertEqual(self.attach(car, plug, ruined), 0)
        self.assertEqual([m[0] for m in self.world.moves], ["drop", "attach"])
        self.assertIsNone(ruined.parent)
        self.assertEqual(self.world.deleted, [])

    def test_failed_drop_or_full_car_or_refused_take_leaves_the_part_with_its_carrier(self):
        for field, code, occupant_needed in (("fail_drop", 2, True), ("free_slot", 3, False), ("fail_take", 4, False)):
            world = FakeWorld()
            car, item = FakeEntity("car", world), FakeEntity("part", world, parent="member")
            occupant = FakeEntity("old", world, parent=car) if occupant_needed else None
            if field == "free_slot": car.inv.free_slot = None
            elif field == "fail_drop": car.inv.fail_drop = True
            else: car.inv.fail_take = True
            self.assertEqual(self.attach(car, item, occupant), code, field)
            self.assertEqual(item.parent, "member")
            self.assertEqual((world.created, world.deleted), ([], []))

    def test_readback_catches_a_take_that_reports_success_but_did_not_move(self):
        car, item = FakeEntity("car", self.world), FakeEntity("part", self.world, parent="member")
        car.inv.TakeEntityAsTargetAttachmentEx = lambda mode, target, it, slot: True
        self.assertEqual(self.attach(car, item), 5)


class ClaimAndCooldownTests(Fixture):
    def test_offer_refusal_order_and_reasons(self):
        r = self.P.HCOfferRefusal
        self.assertEqual(r(False, 0, 2, 100, 0, True), "carfix_disabled")
        self.assertEqual(r(True, 0, 2, 100, 0, False), "carfix_no_mechanic")
        self.assertEqual(r(True, 0, 2, 100, 200, True), "carfix_cooldown")
        self.assertEqual(r(True, 2, 2, 100, 0, True), "carfix_cap")
        self.assertEqual(r(True, 1, 2, 100, 100, True), "")

    def test_claim_is_free_for_owner_or_after_expiry_only(self):
        c = self.P.HCClaimFree
        self.assertTrue(c(0, 0, 5, 10))
        self.assertTrue(c(5, 99, 5, 10))
        self.assertFalse(c(6, 99, 5, 10))
        self.assertTrue(c(6, 10, 5, 10))

    def test_walk_budget_scales_with_distance_and_has_slack_never_a_teleport(self):
        self.assertEqual(self.P.HCWalkSeconds(200.0, 2.0, 60), 160)

    def test_registry_dedupes_and_enforces_cap(self):
        registry = A()
        self.assertTrue(self.P.HCRegistryAdd(registry, "car1", 2))
        self.assertTrue(self.P.HCRegistryAdd(registry, "car1", 2))
        self.assertEqual(len(registry), 1)
        self.assertTrue(self.P.HCRegistryAdd(registry, "car2", 2))
        self.assertFalse(self.P.HCRegistryAdd(registry, "car3", 2))
        self.assertEqual(len(registry), 2)


class ConfigAndSourceTests(Fixture):
    def cfg(self, **over):
        data = json.loads(CONFIG.read_text())
        data.update(over)
        data["MechanicToolClasses"] = A(data["MechanicToolClasses"])
        return N(**data)

    def test_shipped_config_is_on_by_default_and_valid(self):
        data = json.loads(CONFIG.read_text())
        self.assertTrue(data["Enabled"])
        config = self.cfg()
        self.assertTrue(self.authored.call("HCValid", config))

    def test_out_of_range_tunables_are_refused(self):
        for key, bad in (("SearchRadiusMeters", 5.0), ("MaxActiveGroups", 0), ("CooldownSeconds", 1),
                         ("WorkSecondsPerStep", 0), ("MaxKnownCars", 100000), ("MaxAttemptsPerCar", 0),
                         ("MaxRouteNodes", 1), ("MechanicToolClasses", [])):
            self.assertFalse(self.authored.call("HCValid", self.cfg(**{key: bad})), key)

    def test_source_never_spawns_deletes_or_teleports_and_uses_shared_core(self):
        text = POLICY.read_text() + REPAIR.read_text()
        for banned in ("CreateInInventory", "CreateObject", "SetPosition(", "SetOrigin(", "SetTransform(", ".Delete()", "ObjectDelete"):
            self.assertNotIn(banned, text, banned)
        for needed in ("HCServer.HCTickWork()", "HCV2Admission.Line(", "HCOperationalStatus", "acceptance/ai_car_repair.disable",
                       "static bool HCOffer(eAIGroup group, vector home)", "HCReadyCar(eAIGroup group)",
                       "ClearWaypoints", "TakeEntityAsTargetAttachmentEx"):
            self.assertIn(needed, text, needed)
        self.assertNotIn("GetPlayer", text.replace("HCPerfPlayers", ""))

    def test_policy_has_no_unproven_engine_api(self):
        for name in ("TeleportTo", "SetPos(", "GetClosestPlayer"):
            self.assertNotIn(name, POLICY.read_text() + REPAIR.read_text())


class CommitProximityAndCustodyTests(Fixture):
    def gate(self, member, worker, carrier, reach=16.0):
        return self.P.HCCommitGate(member, worker, carrier, reach)

    def test_commit_gate_allows_a_member_carrier_and_worker_in_range(self):
        self.assertEqual(self.gate(True, 4.0, 9.0), "")

    def test_a_carrier_outside_the_group_is_refused_even_next_to_the_car(self):
        self.assertEqual(self.gate(False, 1.0, 1.0), "carfix_carrier_not_member")

    def test_worker_who_walked_off_pauses_the_job_instead_of_committing(self):
        self.assertEqual(self.gate(True, 400.0, 1.0), "carfix_pause_worker")

    def test_distant_part_carrier_aborts_instead_of_pulling_the_part_across_the_map(self):
        self.assertEqual(self.gate(True, 1.0, 900.0), "carfix_carrier_far")

    def test_membership_is_judged_before_distance(self):
        self.assertEqual(self.gate(False, 900.0, 900.0), "carfix_carrier_not_member")


class SourceStructureTests(unittest.TestCase):
    def setUp(self):
        self.text = REPAIR.read_text()

    def test_static_methods_qualify_kind_constants(self):
        body = re.sub(r"static const int KIND_\w+ = \d+;", "", self.text)
        self.assertEqual([], re.findall(r"(?<![\w.])KIND_\w+", body))

    def test_foreach_iterates_only_plain_locals(self):
        for source in (self.text, POLICY.read_text()):
            for expr in re.findall(r"foreach\s*\([^:)]+:\s*([^)]+)\)", source):
                self.assertRegex(expr.strip(), r"^[a-z]\w*$", expr)

    def test_commits_revalidate_proximity_and_custody_through_the_policy_gate(self):
        for method in ("HCCommit", "HCEngineStep"):
            start = self.text.index("static string %s(" % method)
            self.assertIn("HCCarrierGate(", self.text[start:start + 2500], method)
        start = self.text.index("static string HCCarrierGate(")
        self.assertIn("HCCommitGate(", self.text[start:start + 1200])
        self.assertIn("GetGroup() == job.Group", self.text[start:start + 1200])
        self.assertNotIn("!step.Item.GetHierarchyRootPlayer()", self.text)

    def test_work_budget_uses_the_allocated_carfix_consumer(self):
        self.assertNotIn("HCTakeFor(16,", self.text)
        self.assertIn("HCTakeFor(HCUnitBudget.HC_WORK_CARFIX,", self.text)
        self.assertIn("HCUnitBudget.HC_WORK_CARFIX", self.text)
        self.assertNotIn(".HCTake(", self.text)


if __name__ == "__main__":
    unittest.main()
