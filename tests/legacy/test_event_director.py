"""Synthetic execution of authored rules, not native/network/reward evidence."""
import copy
from pathlib import Path
import unittest
from tests.legacy.test_group_server import EArray


ROOT = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts"


def event_rules():
    from tests.legacy.test_event_runtime import environment
    env = environment()
    return dict(env, **vars(env["HCEventDirector"]))


class EventDirectorTests(unittest.TestCase):
    def test_dto_members_do_not_shadow_native_world_type(self):
        source = (ROOT / "3_Game/Events/HCEventData.c").read_text()
        self.assertNotRegex(source, r"\bstring\s+World\s*;")

    def setUp(self):
        self.e = event_rules()
        self.s = self.e["Initialize"]("synthetic_world", "run-a")
        self.c = self.e["HCEventContext"]()
        self.c.Server = True
        self.c.WorldName = "synthetic_world"
        self.c.Session = "run-a"
        self.c.Now = 100
        self.d = self.e["HCEventDefinition"]()
        self.d.Id = "recovery"
        self.d.WorldName = self.c.WorldName
        self.d.ObjectiveTag = "observed_delivery"
        self.code = self.e["HCEventCode"]
        self.op = self.e["HCEventOp"]

    def command(self, operation, participant=""):
        q = self.e["HCEventRequest"]()
        q.EventId = self.s.Records[0].Id
        q.ExpectedRevision = self.s.Records[0].Revision
        q.Op = operation
        q.ParticipantId = participant
        return self.e["Command"](self.s, self.c, q)

    def active(self):
        self.assertEqual(self.code.OK, self.e["Propose"](self.s, self.c, self.d))
        self.assertEqual(self.code.OK, self.command(self.op.ANNOUNCE))
        self.assertEqual(self.code.OK, self.command(self.op.JOIN, "alice"))
        self.assertEqual(self.code.OK, self.command(self.op.ACTIVATE))

    def observation(self):
        o = self.e["HCEventObservation"]()
        o.ServerObserved = True
        o.WorldName = self.c.WorldName
        o.Session = self.c.Session
        o.EventId = self.s.Records[0].Id
        o.ParticipantId = "alice"
        o.ObjectiveTag = self.d.ObjectiveTag
        o.Sequence = 1
        o.Units = 1
        return o

    def test_observed_completion_rejects_replay_and_double_completion(self):
        self.active()
        o = self.observation()
        self.assertEqual(self.code.OK, self.e["Observe"](self.s, self.c, o))
        before = copy.deepcopy(self.s)
        self.assertNotEqual(self.code.OK, self.e["Observe"](self.s, self.c, o))
        self.assertEqual(before, self.s)
        self.assertEqual(self.code.OK, self.command(self.op.COMPLETE))
        self.assertNotEqual(self.code.OK, self.command(self.op.COMPLETE))

    def test_rewards_remain_blocked_without_grant_adapter(self):
        self.d.RewardUnits = 1
        self.active()
        self.d.RewardUnits = 0  # Caller edits cannot bypass the frozen definition.
        self.assertEqual(self.code.OK,
                         self.e["Observe"](self.s, self.c, self.observation()))
        before = copy.deepcopy(self.s)
        self.assertEqual(self.code.BLOCKED, self.command(self.op.COMPLETE))
        self.assertEqual(before, self.s)

    def test_unobserved_or_unenrolled_progress_never_mutates_state(self):
        self.active()
        for field, value in (("ServerObserved", False),
                             ("ParticipantId", "outsider"),
                             ("WorldName", "other_world"),
                             ("Session", "old_session"),
                             ("ObjectiveTag", "invented"),
                             ("Units", 0), ("Units", 2), ("Sequence", 2)):
            with self.subTest(field=field, value=value):
                o = self.observation()
                setattr(o, field, value)
                before = copy.deepcopy(self.s)
                self.assertNotEqual(self.code.OK, self.e["Observe"](self.s, self.c, o))
                self.assertEqual(before, self.s)

    def test_opt_out_and_deadline_are_explicit_without_inventory_operations(self):
        self.d.LifetimeSeconds = 10
        self.active()
        self.assertEqual(["alice"], self.s.Records[0].Participants)
        self.assertEqual(self.code.OK, self.command(self.op.LEAVE, "alice"))
        self.assertNotEqual(self.code.OK,
                            self.e["Observe"](self.s, self.c, self.observation()))
        self.c.Now = 110
        before = copy.deepcopy(self.s)
        self.assertEqual(self.code.EXPIRED, self.command(self.op.JOIN, "bob"))
        self.assertEqual(before, self.s)
        self.assertEqual(self.code.OK, self.command(self.op.EXPIRE))
        self.assertEqual(self.e["HCEventStatus"].EXPIRED, self.s.Records[0].Status)

    def test_restart_cancels_live_records_and_rejects_session_reuse(self):
        self.active()
        old = self.observation()
        self.assertEqual(self.code.OK, self.e["Restart"](self.s, self.c, "run-b"))
        self.assertEqual(self.e["HCEventStatus"].CANCELLED, self.s.Records[0].Status)
        self.c.Session = self.s.Session
        before = copy.deepcopy(self.s)
        self.assertNotEqual(self.code.OK, self.e["Observe"](self.s, self.c, old))
        self.assertNotEqual(self.code.OK, self.e["Restart"](self.s, self.c, "run-a"))
        self.assertEqual(before, self.s)

    def test_server_authority_clock_and_stale_revision_fail_closed(self):
        self.active()
        for field, value in (("Server", False), ("WorldName", "other"),
                             ("Session", "other"), ("Now", 99)):
            previous = getattr(self.c, field)
            setattr(self.c, field, value)
            before = copy.deepcopy(self.s)
            self.assertNotEqual(self.code.OK, self.command(self.op.CANCEL))
            self.assertEqual(before, self.s)
            setattr(self.c, field, previous)
        q = self.e["HCEventRequest"]()
        q.EventId = self.s.Records[0].Id
        q.ExpectedRevision = 0
        q.Op = self.op.CANCEL
        before = copy.deepcopy(self.s)
        self.assertEqual(self.code.CONFLICT, self.e["Command"](self.s, self.c, q))
        self.assertEqual(before, self.s)

    def test_definition_is_snapshotted_and_duplicate_proposal_is_rejected(self):
        self.active()
        self.d.Goal = 500
        self.assertEqual(1, self.s.Records[0].Definition.Goal)
        before = copy.deepcopy(self.s)
        self.assertNotEqual(self.code.OK, self.e["Propose"](self.s, self.c, self.d))
        self.assertEqual(before, self.s)

    def test_finite_reservations_release_only_after_terminal_transition(self):
        self.d.ActorBudget = 64
        self.d.ItemBudget = 128
        self.active()
        self.d.Id = "second"
        self.d.ActorBudget = 1
        self.d.ItemBudget = 1
        before = copy.deepcopy(self.s)
        self.assertEqual(self.code.LIMIT, self.e["Propose"](self.s, self.c, self.d))
        self.assertEqual(before, self.s)
        self.assertEqual(self.code.OK, self.command(self.op.CANCEL))
        self.assertEqual(self.code.OK, self.e["Propose"](self.s, self.c, self.d))

    def test_partial_progress_requires_contiguous_observation_sequence(self):
        self.d.Goal = 3
        self.active()
        o = self.observation()
        self.assertEqual(self.code.OK, self.e["Observe"](self.s, self.c, o))
        before = copy.deepcopy(self.s)
        self.assertEqual(self.code.CONFLICT, self.e["Observe"](self.s, self.c, o))
        o.Sequence = 3
        self.assertEqual(self.code.CONFLICT, self.e["Observe"](self.s, self.c, o))
        self.assertEqual(before, self.s)
        o.Sequence = 2
        o.Units = 2
        self.assertEqual(self.code.OK, self.e["Observe"](self.s, self.c, o))
        self.assertEqual(self.code.OK, self.command(self.op.COMPLETE))
        self.assertTrue(self.e["StateValid"](self.s))

    def test_revision_exhaustion_reserves_a_terminal_transition(self):
        self.active()
        self.s.Records[0].Revision = 999999
        before = copy.deepcopy(self.s)
        self.assertEqual(self.code.LIMIT, self.command(self.op.JOIN, "bob"))
        self.assertEqual(before, self.s)
        self.assertEqual(self.code.OK, self.command(self.op.CANCEL))
        self.assertEqual(1000000, self.s.Records[0].Revision)
        self.assertTrue(self.e["StateValid"](self.s))

    def test_live_capacity_is_bounded_while_empty_session_history_is_compacted(self):
        for number in range(32):
            self.d.Id = "definition-" + str(number)
            self.assertEqual(self.code.OK, self.e["Propose"](self.s, self.c, self.d))
        self.d.Id = "overflow"
        before = copy.deepcopy(self.s)
        self.assertEqual(self.code.LIMIT, self.e["Propose"](self.s, self.c, self.d))
        self.assertEqual(before, self.s)
        for number in range(100):
            session = "run-" + str(number)
            self.assertEqual(self.code.OK, self.e["Restart"](self.s, self.c, session))
            self.c.Session = self.s.Session
            self.assertLessEqual(len(self.s.Sessions), 33)
        self.assertTrue(self.e["StateValid"](self.s))

    def test_pruned_floor_preserves_ids_and_old_context_cannot_replay(self):
        self.active()
        stale = copy.deepcopy(self.c)
        self.assertEqual(0, self.e["Restart"](self.s, self.c, "next"))
        self.c.Session = self.s.Session
        self.assertTrue(self.e["PruneFirst"](self.s))
        self.assertEqual(1, self.s.PrunedThrough)
        self.assertEqual(0, self.e["Propose"](self.s, self.c, self.d))
        self.assertEqual(2, self.s.Records[0].Id)
        before = copy.deepcopy(self.s)
        self.assertFalse(self.e["PruneFirst"](self.s))
        self.assertEqual(before, self.s)
        self.assertNotEqual(0, self.e["Propose"](self.s, stale, self.d))
        self.assertNotEqual(0, self.e["Propose"](self.s, self.c, self.d))
        for field, value in (("PrunedThrough", 0), ("NextId", 2), ("SessionGeneration", -1)):
            broken = copy.deepcopy(self.s); setattr(broken, field, value)
            self.assertFalse(self.e["StateValid"](broken), field)

    def test_malformed_state_is_rejected_without_traversing_oversized_arrays(self):
        self.active()
        baseline = copy.deepcopy(self.s)
        changes = (
            lambda s: setattr(s, "Version", 2),
            lambda s: setattr(s, "WorldName", ""),
            lambda s: setattr(s, "Session", ""),
            lambda s: setattr(s, "NextId", 0),
            lambda s: setattr(s, "LastNow", -1),
            lambda s: setattr(s, "Sessions", EArray(["run-a", "run-a"])),
            lambda s: setattr(s, "Records", EArray([None] * 33)),
            lambda s: setattr(s, "Records", EArray([None])),
            lambda s: setattr(s.Records[0].Definition, "Goal", 0),
            lambda s: setattr(s.Records[0], "Participants", EArray(["alice"] * 2)),
            lambda s: setattr(s.Records[0], "Participants", EArray([""])),
            lambda s: setattr(s.Records[0], "Revision", 1000000),
            lambda s: setattr(s.Records[0], "Status", 99),
            lambda s: setattr(s.Records[0], "Progress", 2),
            lambda s: setattr(s.Records[0], "Expires", -1),
        )
        for number, change in enumerate(changes):
            with self.subTest(case=number):
                self.s = copy.deepcopy(baseline)
                change(self.s)
                before = copy.deepcopy(self.s)
                self.assertFalse(self.e["StateValid"](self.s))
                q = self.e["HCEventRequest"]()
                q.EventId = 1
                q.ExpectedRevision = 1
                q.Op = self.op.CANCEL
                self.assertEqual(self.code.DENIED,
                                 self.e["Command"](self.s, self.c, q))
                self.assertEqual(before, self.s)

    def test_invalid_definition_fields_never_reserve_capacity(self):
        original = copy.deepcopy(self.d)
        changes = (("Version", 2), ("Id", ""), ("Id", "x" * 65),
                   ("WorldName", "other"), ("ObjectiveTag", "\t"),
                   ("Goal", 0), ("Goal", 1001),
                   ("MaxParticipants", 0), ("MaxParticipants", 7),
                   ("ActorBudget", -1), ("ActorBudget", 65),
                   ("ItemBudget", -1), ("ItemBudget", 129),
                   ("LifetimeSeconds", 0), ("LifetimeSeconds", 86401),
                   ("RewardUnits", -1), ("RewardUnits", 33))
        for field, value in changes:
            with self.subTest(field=field, value=value):
                self.d = copy.deepcopy(original)
                setattr(self.d, field, value)
                before = copy.deepcopy(self.s)
                self.assertEqual(self.code.INVALID,
                                 self.e["Propose"](self.s, self.c, self.d))
                self.assertEqual(before, self.s)

    def test_blank_identity_and_unsupported_initial_namespace_are_rejected(self):
        for world, session in (("", "run"), ("world", " "),
                               ("x" * 97, "run"), ("world", "\t")):
            self.assertIsNone(self.e["Initialize"](world, session))
        self.active()
        for participant in ("", "   ", "bob\n", "x" * 97):
            before = copy.deepcopy(self.s)
            self.assertEqual(self.code.INVALID,
                             self.command(self.op.JOIN, participant))
            o = self.observation()
            o.ParticipantId = participant
            self.assertEqual(self.code.INVALID,
                             self.e["Observe"](self.s, self.c, o))
            self.assertEqual(before, self.s)

    def test_discovery_does_not_enroll_players_or_skip_lifecycle(self):
        self.assertEqual(self.code.OK, self.e["Propose"](self.s, self.c, self.d))
        self.assertEqual([], self.s.Records[0].Participants)
        before = copy.deepcopy(self.s)
        for operation in (self.op.ACTIVATE, self.op.COMPLETE, self.op.JOIN):
            self.assertEqual(self.code.CONFLICT,
                             self.command(operation, "alice"))
            self.assertEqual(before, self.s)
        self.assertEqual(self.code.OK, self.command(self.op.ANNOUNCE))
        before = copy.deepcopy(self.s)
        self.assertEqual(self.code.CONFLICT, self.command(self.op.ACTIVATE))
        self.assertEqual(before, self.s)

    def test_deadline_must_fit_the_bounded_session_clock(self):
        self.c.Now = 1000000000
        before = copy.deepcopy(self.s)
        self.assertEqual(self.code.LIMIT, self.e["Propose"](self.s, self.c, self.d))
        self.assertEqual(before, self.s)

    def test_source_has_no_gameplay_hooks_or_native_grant_operations(self):
        source = (ROOT / "4_World/Events/HCEventDirector.c").read_text()
        self.assertNotRegex(source, r"\b(?:override|modded)\b")
        for forbidden in ("GetGame(", "ScriptRPC", "OpenFile(", "CreateObject",
                          "CallLater", "GetInventory(", "JsonFileLoader"):
            self.assertNotIn(forbidden, source)


def load_tests(loader, standard_tests, pattern):
    """Keep the fixed BDD binding while exercising the whole optional-event stack.

    Default full discovery loads these files itself. Only the precise bound
    event entry point expands here, preventing duplicate full-suite execution.
    """
    if pattern == "test_event_director.py":
        import importlib
        for name in ("test_event_runtime", "test_event_transport", "test_event_ui",
                     "test_event_integration", "test_v1_events_behavior"):
            module = importlib.import_module("tests.unit." + name)
            standard_tests.addTests(loader.loadTestsFromModule(module))
    return standard_tests
