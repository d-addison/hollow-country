"""HC-10: execute authored custody decisions through synthetic stdlib ports.

No engine/provider/inventory simulation or native acceptance. The existing
restricted syntax adapter executes the Enforce methods; DTOs and file IO are
explicit synthetic fixtures.

RED: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_ai_custody -v
AssertionError: missing authored method HCCustodyAllows; FAILED (failures=1).
Restart-cap RED (same command): missing authored method HCCustodyDebt; FAILED (failures=1).
GREEN: same command; Ran 1 test; OK. Runtime acceptance pending.

Review fix-round spec/plan/task evidence (synthetic source tests only):
Actual RED (before each corresponding implementation):

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_ai_custody.CustodyLifecycleRegression tests.unit.test_ai_limits.SharedSpawnPaths.test_surveyed_adapter_uses_configured_stable_size_without_inventing_positions -v
Ran 8 tests; FAILED (failures=11)
# Refusal retained FINISHED row; claim 65: unexpectedly None : 64;
# startup custody debt: AssertionError: 0 != 4;
# fold-back failures retained active lease; save latch: True is not false;
# long identity could not claim; short survey: False is not true.

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_ai_limits.ReviewAdmissionRegression -v
Ran 1 test; FAILED (failures=1)
AssertionError: 1 != 50

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_ai_custody.CustodyLifecycleRegression.test_module_stop_start_does_not_assume_process_body_absence -v
Ran 1 test; FAILED (failures=1)
# A same-process off/on incorrectly admitted lease:2 alongside an unresolved claim.

Additional late typed-callback RED:

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_ai_custody.CustodyLifecycleRegression.test_late_typed_result_after_finished_eviction_releases_only_old_budget -v
Ran 1 test; FAILED (failures=1)
AssertionError: Tuples differ: (1, 4) != (2, 8)

GREEN focused command (also covers canonical legacy migration, corrupt/intent/
backup-only restore, bounded eviction preserving live/quarantined rows, and actual
materializer + site Spawn + adapter combined admission):

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_ai_custody tests.unit.test_ai_limits -v
Ran 28 tests; OK

Round 2 spec/plan/tasks: release unclaimed leases on stop; finish process-restart
quarantines unknown (normalize observations, release budget, bounded per-row log,
evict history); keep FINISHED terminal; latch first start only after load/migrate.
Tests execute authored methods through explicit synthetic ports, then implement
those four custody changes. No native runtime or production acceptance claimed.

Actual pre-implementation RED, combined seven-test run (full command and output
retained in .banso-writer/round2-report.md and round2-red.log):
  stop: AssertionError: Tuples differ: (0, 0) != (1, 4)
  restart quarantine: AssertionError: Tuples differ: (0, 0) != (256, 1024)
  late finished mismatch: AssertionError: Tuples differ: (0, 0) != (1, 4)
  repaired first load / failed migration: AssertionError: True is not false
  Ran 7 tests; FAILED (failures=56), including limits/site subtests.
GREEN: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_ai_custody tests.unit.test_ai_limits -v
Ran 37 tests; OK. Engine/PBO/server validation remains pending.

"""
import copy
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_expansion_ai_adapter import A, Authored

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = ROOT / 'mods/HollowCountry/scripts/3_Game/World/HCAIPartyIdentity.c'
MATERIALIZER = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCWorldMaterializer.c'
BRIDGE = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXMaterializerBridge.c'


def adapted(source, env):
    # Syntax only: let the existing restricted port strip our new DTO local
    # declarations. Class references, calls and all decisions remain authored.
    source = re.sub(r'\b(?:HCAIParty\w*|HCWorld\w+)\b(?=\s+\w+\s*[=;:)])',
                    'HCXAIValue', source)
    return Authored(source, env)


class CustodyBehavior(unittest.TestCase):
    def test_duplicate_lease_result_and_refilled_return_are_refused(self):
        source = MATERIALIZER.read_text()
        env = dict(A=A, len=len, str=str, HCAIPartyCustody=N(MAX_ROWS=64))
        from tests.unit.ai_limits_fixture import install
        install(env, MaxLiveAI=8, MaxMaterialized=2)
        runtime = N(m_CustodyReady=True, m_Custody=N(Rows=A()),
                    m_DuplicateRefused=0)
        # This executes the authored reservation decision (initial RED seam).
        runtime.HCCustodyAllows = lambda identity: adapted(source, env).call(
            'HCCustodyAllows', runtime, identity)
        synthetic_identity = N(HCPartyId=lambda: 'party:synthetic-caravan',
                               HCCargoId=lambda: 'cargo:synthetic-caravan')
        self.assertTrue(runtime.HCCustodyAllows(synthetic_identity))
        runtime.m_Custody.Rows.Insert(N(PartyId='party:synthetic-caravan',
                                       CargoId='cargo:synthetic-caravan', Outcome='CLAIMED'))
        self.assertFalse(runtime.HCCustodyAllows(synthetic_identity))
        self.assertEqual(1, runtime.m_DuplicateRefused)

        data_source = IDENTITY.read_text()
        policy = adapted(data_source, env)
        env['HCWorldLimits'] = N(Token=lambda value: bool(value) and len(value) <= 96)
        identity_api = N()
        env['HCAIPartyIdentity'] = identity_api
        identity_api.HCValid = lambda identity: policy.call('HCValid', None, identity)
        # Explicit immutable synthetic identity values; getter bodies are authored.
        identity = N(m_PartyId='party:synthetic-caravan', m_CampId='camp:synthetic',
                     m_HomeId='synthetic-home', m_RouteId='route:synthetic-caravan',
                     m_CargoId='cargo:synthetic-caravan', m_Generation=42)
        for name in ('HCPartyId', 'HCCampId', 'HCHomeId', 'HCRouteId',
                     'HCCargoId', 'HCGeneration'):
            setattr(identity, name, lambda name=name: policy.call(name, identity))
        self.assertTrue(identity_api.HCValid(identity))
        identity.m_Generation = 0
        self.assertFalse(identity_api.HCValid(identity))
        identity.m_Generation = 42
        env['HCAIPartyCustodyRow'] = lambda: N(Outcome='CLAIMED', Materialized=False,
                                              Survivors=0)
        row = policy.call('HCReservation', None, identity, 'lease:synthetic', 4)
        self.assertEqual('camp:synthetic', row.CampId)
        self.assertEqual('synthetic-home', row.HomeId)
        self.assertEqual('route:synthetic-caravan', row.RouteId)
        self.assertEqual(42, row.Generation)
        self.assertEqual(1, policy.call('HCFinish', None, row, True, 2))
        first = copy.deepcopy(vars(row))
        self.assertEqual(2, policy.call('HCFinish', None, row, True, 2))
        self.assertEqual(first, vars(row))  # duplicate death/retirement callback
        self.assertEqual(2, policy.call('HCFinish', None, row, True, 4))
        self.assertEqual('FINISHED', row.Outcome)  # late callbacks cannot undo absence
        self.assertEqual(2, row.Survivors)  # never overwrite first observation
        self.assertEqual(first, vars(row))
        row = policy.call('HCReservation', None, identity, 'lease:quarantined', 4)
        self.assertEqual(0, policy.call('HCFinish', None, row, True, 5))
        self.assertEqual('QUARANTINED', row.Outcome)  # invalid first result still latches
        self.assertEqual(0, policy.call('HCFinish', None, row, True, 2))
        runtime.m_Custody.Rows = A([row])
        restarted = copy.deepcopy(runtime.m_Custody)  # synthetic durable readback
        runtime.m_Custody = restarted
        self.assertFalse(runtime.HCCustodyAllows(identity))
        identity.m_Generation = 43  # a reset epoch cannot refill the same party
        self.assertFalse(runtime.HCCustodyAllows(identity))
        identity.m_PartyId = 'party:synthetic-other'
        self.assertFalse(runtime.HCCustodyAllows(identity))  # cargo alias refused
        # Exercise the actual claim + result handlers against explicit synthetic
        # durable/world ports. A saved intent must precede any provider claim;
        # duplicated callbacks cannot repeat either world mutation.
        env['HCAIPartyCustody'].HCReservation = lambda *args: policy.call(
            'HCReservation', None, *args)
        env['HCAIPartyCustody'].HCFinish = lambda *args: policy.call(
            'HCFinish', None, *args)
        facts, debits, saves = [], [], []
        world = N(GetFaction=lambda faction: True,
                  AddFact=lambda *args: facts.append(args) or True,
                  AdjustStrength=lambda *args: debits.append(args) or True)
        env['HCWorldModule'] = N(Get=lambda: world)
        methods = adapted(source, env)
        api = N(MAX_ACTORS=8, MAX_PROPOSALS=2, MAX_PER_PROPOSAL=4,
                PROVIDER_TIMEOUT=120)
        env['HCWorldMaterializer'] = api
        api.FoldBack = lambda *args: methods.call('FoldBack', None, *args)
        api.NoProvider = lambda *args: methods.call('NoProvider', None, *args)
        identity.m_PartyId = 'party:synthetic-caravan'
        identity.m_Generation = 42
        lease = N(Proposal=N(Id='lease:synthetic', Identity=identity,
                            ActorCap=4, FactionId='synthetic-faction',
                            PlaceId='synthetic-home', Kind='CARAVAN'),
                  Claimed=False, Finished=False, OutcomeApplied=False,
                  Materialized=False, Survivors=0, Created=0, RowIndex=-1)
        runtime.m_Custody.Rows.Clear()
        runtime.m_Active = A([lease])
        runtime.m_Clock = 0
        runtime.m_Materialized = runtime.m_Traces = 0
        runtime.m_Cooldowns = A()
        runtime.HCSaveCustody = lambda: saves.append(copy.deepcopy(
            runtime.m_Custody)) or True
        runtime.HCCustodyDebt = lambda *args: methods.call('HCCustodyDebt', runtime, *args)
        runtime.HCClaimFits = lambda: methods.call('HCClaimFits', runtime)
        env['MAX_ACTORS'] = 8
        env['MAX_PROPOSALS'] = 2
        runtime.HCRecordResult = lambda *args: methods.call('HCRecordResult', runtime, *args)
        runtime.Expire = lambda: methods.call('Expire', runtime)
        runtime.Resolve = lambda *args: methods.call('Resolve', runtime, *args)
        self.assertTrue(methods.call('HCClaim', runtime, lease))
        self.assertTrue(lease.Claimed)
        self.assertEqual(1, len(saves))
        self.assertFalse(methods.call('HCClaim', runtime, lease))
        methods.call('HCRecordResult', runtime, 'unknown-lease', True, 0)
        self.assertEqual(1, len(saves))
        result = N(HCIdentity=lambda: identity, HCLeaseId=lambda: 'lease:synthetic',
                   HCMaterialized=lambda: True, HCSurvivors=lambda: 2)
        methods.call('HCRecordTypedResult', runtime, result)
        methods.call('HCRecordTypedResult', runtime, result)
        self.assertEqual(1, len(facts))
        self.assertEqual([('synthetic-faction', -2)], debits)
        self.assertEqual(2, len(saves))
        self.assertEqual([], runtime.m_Active)
        result.HCSurvivors = lambda: 4
        methods.call('HCRecordTypedResult', runtime, result)
        methods.call('HCRecordTypedResult', runtime, result)
        self.assertEqual(2, len(saves))  # finished callbacks never rewrite history
        self.assertEqual('FINISHED', runtime.m_Custody.Rows[0].Outcome)
        self.assertEqual(1, len(debits))
        self.assertTrue(runtime.HCCustodyAllows(identity))
        self.assertEqual(0, methods.call('HCCustodyDebt', runtime, True))
        self.assertEqual(0, methods.call('HCCustodyDebt', runtime, False))
        # A restart/off transition must reserve unknown surviving actors against
        # the same 8/2 global cap; a new identity cannot bypass the old lease.
        runtime.m_Custody.Rows[0].Outcome = 'CLAIMED'
        runtime.m_Custody.Rows[0].Materialized = False
        runtime.m_Custody.Rows[0].Survivors = 0
        self.assertEqual(4, methods.call('HCCustodyDebt', runtime, True))
        runtime.m_Active.Insert(N(Proposal=N(Id='synthetic-second', ActorCap=4)))
        self.assertTrue(runtime.HCClaimFits())
        runtime.m_Active.Insert(N(Proposal=N(Id='synthetic-third', ActorCap=1)))
        self.assertFalse(runtime.HCClaimFits())
        runtime.m_Active.Clear()
        runtime.m_Active.Insert(lease)
        self.assertEqual(0, methods.call('HCCustodyDebt', runtime, True))
        runtime.m_Active.Clear()
        # Synthetic failed claim barrier: never hands the provider a lease.
        runtime.m_Custody.Rows.Clear()
        lease.Claimed = lease.Finished = False
        runtime.HCSaveCustody = lambda: False
        self.assertFalse(methods.call('HCClaim', runtime, lease))
        self.assertFalse(lease.Claimed)
        self.assertFalse(runtime.HCCustodyAllows(identity))
        runtime.m_CustodyReady = False
        runtime.m_Custody.Rows.Clear()
        self.assertFalse(runtime.HCCustodyAllows(identity))
        # Explicit synthetic legacy/typed callback ports: distinguish callbacks
        # with unknown identity from unique, attributable provider spawns.
        bridge_runtime = N(m_Running=True, m_Spawned=0,
                           m_UnattributedSpawnCallbacks=0, m_Started=A())
        env['s_Instance'] = bridge_runtime
        api.HCIdentity = lambda lease_id: identity if lease_id == 'lease:synthetic' else None
        bridge = adapted(BRIDGE.read_text(), env)
        bridge.call('SiteSpawned', None)
        self.assertEqual(0, bridge_runtime.m_Spawned)
        self.assertEqual(1, bridge_runtime.m_UnattributedSpawnCallbacks)
        bridge.call('SiteSpawned', None, 'unknown-lease')
        bridge.call('SiteSpawned', None, 'lease:synthetic')
        bridge.call('SiteSpawned', None, 'lease:synthetic')
        self.assertEqual(1, bridge_runtime.m_Spawned)


class CustodyLifecycleRegression(unittest.TestCase):
    def setUp(self):
        from tests.unit.custody_fixture import CustodyFixture
        self.f = CustodyFixture()
        self.r, self.b = self.f.runtime, self.f.budget

    def test_stop_releases_unclaimed_reservation_before_same_process_start(self):
        self.r.OnStart(N(EnableEncounters=True))
        self.r.InterestRing()  # reserve only; the provider has not claimed it
        self.assertEqual(1, len(self.r.m_Active))
        self.assertFalse(self.r.m_Active[0].Claimed)
        self.assertEqual([], self.r.m_Custody.Rows)
        self.assertEqual((1, 4), (self.b.Groups(), self.b.Actors()))
        self.r.OnStop()
        self.r.OnStart(N(EnableEncounters=True))
        self.assertEqual((0, 0), (self.b.Groups(), self.b.Actors()))
        self.f.limits.MaxLiveGroups = 2
        self.f.limits.MaxLiveAI = 8
        self.assertTrue(self.b.TryReserve('synthetic-site', 4))
        self.assertTrue(self.b.TryReserve('synthetic-adapter', 4))

    def test_restart_releases_quarantines_and_full_history_stays_evictable(self):
        cap = self.f.env['HCAIPartyCustody'].MAX_ROWS
        for index in range(cap):
            row = self.f.data_policy.call('HCReservation', None,
                self.f.identity(str(index)), 'quarantine:' + str(index), 4)
            row.Outcome, row.Materialized, row.Survivors = 'QUARANTINED', True, 2
            self.r.m_Custody.Rows.Insert(row)
            self.b.Restore(row.LeaseId, row.ActorCap)
        self.assertTrue(self.r.HCSaveCustody())
        self.r = self.f.runtime = self.f.new_runtime()  # synthetic process restart
        self.r.OnStart(N(EnableEncounters=True))
        self.assertEqual((0, 0), (self.b.Groups(), self.b.Actors()))
        self.assertEqual(0, self.r.HCCustodyDebt(True))
        self.assertTrue(self.r.m_CustodyReady)
        self.assertTrue(all(row.Outcome == 'FINISHED_UNKNOWN' and not row.Materialized
                            and row.Survivors == 0 for row in self.r.m_Custody.Rows))
        row_logs = [line for line in self.f.logs if 'custody restore lease=' in line]
        self.assertEqual(cap, len(row_logs))
        self.assertTrue(all(sum('lease=quarantine:' + str(i) + ' ' in line
                                for line in row_logs) == 1 for i in range(cap)))
        self.assertIsNotNone(self.f.offer())  # full history allows bounded eviction
        self.assertEqual(cap, len(self.r.m_Custody.Rows))
        self.assertEqual([], self.f.facts)
        self.assertEqual([], self.f.debits)
        self.r = self.f.runtime = self.f.new_runtime()
        self.r.OnStart(N(EnableEncounters=True))
        self.assertTrue(self.r.m_CustodyReady)  # converted rows are valid on disk
        self.assertEqual(cap + 1, sum('custody restore lease=' in line for line in self.f.logs))

    def test_finished_callbacks_never_restore_budget_or_unfinish_history(self):
        for callback in ('duplicate', 'different-count', 'invalid-count', 'identity'):
            with self.subTest(callback=callback):
                self.setUp()
                lease = self.f.offer()
                self.r.HCRecordResult(lease.Proposal.Id, True, 2)
                row = self.r.m_Custody.Rows[0]
                before = copy.deepcopy(vars(row))
                for _ in range(2):
                    if callback == 'identity':
                        result = N(HCIdentity=lambda: self.f.identity('mismatch'),
                                   HCLeaseId=lambda: lease.Proposal.Id,
                                   HCMaterialized=lambda: True, HCSurvivors=lambda: 2)
                        self.r.HCRecordTypedResult(result)
                    else:
                        survivors = dict(duplicate=2, **{'different-count': 4, 'invalid-count': -1})[callback]
                        self.r.HCRecordResult(lease.Proposal.Id, True, survivors)
                self.assertEqual((0, 0), (self.b.Groups(), self.b.Actors()))
                self.assertEqual(before, vars(row))
                self.assertEqual(0, self.r.HCCustodyDebt(True))
                self.assertEqual([('synthetic-faction', -2)], self.f.debits)

    def test_failed_first_load_then_repaired_legacy_file_still_migrates(self):
        path = self.r.m_CustodyPath
        self.f.disk[path] = '{'
        self.r.OnStart(N(EnableEncounters=True))
        self.assertFalse(self.r.m_CustodyReady)
        self.assertFalse(self.r.m_StartedOnce)
        self.r.OnStop()
        row = self.f.data_policy.call('HCReservation', None,
            self.f.identity(), 'legacy:synthetic', 4)
        self.f.disk[path] = self.f.encode(N(SchemaVersion=1, Rows=A([row])))
        self.r.OnStart(N(EnableEncounters=True))
        self.assertTrue(self.r.m_CustodyReady)
        self.assertTrue(self.r.m_StartedOnce)
        self.assertEqual(2, self.f.decode(self.f.disk[path]).SchemaVersion)
        self.assertEqual('FINISHED_UNKNOWN', self.r.m_Custody.Rows[0].Outcome)

    def test_failed_first_migration_does_not_mark_start_successful(self):
        path = self.r.m_CustodyPath
        legacy = self.f.encode(N(SchemaVersion=1, Rows=A()))
        self.f.disk[path] = legacy
        self.f.fail_write = True
        self.r.OnStart(N(EnableEncounters=True))
        self.assertFalse(self.r.m_CustodyReady)
        self.assertFalse(self.r.m_StartedOnce)
        self.r.OnStop()
        self.f.fail_write = False
        self.f.disk[path] = legacy  # explicit operator repair of canonical files
        self.r.OnStart(N(EnableEncounters=True))
        self.assertTrue(self.r.m_StartedOnce)
        self.assertEqual(2, self.f.decode(self.f.disk[path]).SchemaVersion)

    def test_refusal_releases_claim_and_reoffers_only_after_cooldown(self):
        first = self.f.offer()
        self.assertIsNotNone(first)
        self.r.HCRecordResult(first.Proposal.Id, False, 0)
        self.assertEqual([], self.r.m_Custody.Rows)
        self.assertEqual((0, 0), (self.b.Groups(), self.b.Actors()))
        self.assertIsNone(self.f.offer())
        self.r.m_Clock += 21600
        second = self.f.offer()
        self.assertIsNotNone(second)
        self.assertNotEqual(first.Proposal.Id, second.Proposal.Id)
        self.r.HCRecordResult(first.Proposal.Id, True, 4)  # stale refusal callback
        self.assertEqual(1, self.b.Groups())
        self.assertEqual(1, len(self.r.m_Active))

    def test_finished_outcome_cools_then_recycles_without_two_live_copies(self):
        first = self.f.offer()
        self.r.m_Clock = 21600
        self.assertIsNone(self.f.offer())  # no second live identity
        self.assertEqual(1, len(self.r.m_Active))
        self.r.HCRecordResult(first.Proposal.Id, True, 3)
        self.assertIsNone(self.f.offer())  # cooldown begins at outcome
        self.r.m_Clock += 21600
        second = self.f.offer()
        self.assertIsNotNone(second)
        self.assertNotEqual(first.Proposal.Id, second.Proposal.Id)
        self.r.HCRecordResult(first.Proposal.Id, True, 0)
        self.assertEqual((1, 4), (self.b.Groups(), self.b.Actors()))
        self.assertEqual([('synthetic-faction', -1)], self.f.debits)

    def test_more_than_64_claims_and_bounded_finished_eviction(self):
        for index in range(300):
            self.f.world.MaterializerRow = lambda row, i=index: self.f.proposal(str(i)) if row == 0 else None
            lease = self.f.offer()
            self.assertIsNotNone(lease, index)
            self.r.HCRecordResult(lease.Proposal.Id, True, 4)
            self.r.m_Clock += 21600
        self.assertLessEqual(len(self.r.m_Custody.Rows), self.f.env['HCAIPartyCustody'].MAX_ROWS)
        self.assertGreaterEqual(self.f.env['HCAIPartyCustody'].MAX_ROWS,
                                self.f.limits.MaxHoldouts + self.f.limits.MaxParties)

    def test_on_start_load_resolves_claims_and_late_result_releases_budget(self):
        first = self.f.offer()
        path = self.r.m_CustodyPath
        self.assertIn(path, self.f.disk)  # real authored save path ran
        self.r = self.f.runtime = self.f.new_runtime()
        self.r.OnStart(N(EnableEncounters=True))  # real authored load/restore path
        self.assertTrue(self.r.m_CustodyReady)
        self.assertEqual(0, self.r.HCCustodyDebt(True))
        self.assertEqual((0, 0), (self.b.Groups(), self.b.Actors()))
        self.assertEqual('FINISHED_UNKNOWN', self.r.m_Custody.Rows[0].Outcome)
        self.assertTrue(self.b.TryReserve('site:after-restart', 4))
        self.assertTrue(self.b.TryReserve('adapter:after-restart', 4))
        self.assertEqual(1, sum('custody restore finished_unknown=1' in line for line in self.f.logs))
        self.b.Restore(first.Proposal.Id, 4)  # explicit stray pre-restore budget row
        self.r.HCRecordResult(first.Proposal.Id, True, 2)
        self.assertEqual((2, 8), (self.b.Groups(), self.b.Actors()))
        self.assertEqual([], self.f.debits)  # no invented restart casualties/cargo
        second = self.f.offer()
        self.assertIsNotNone(second)
        self.assertNotEqual(first.Proposal.Id, second.Proposal.Id)
        self.assertEqual(1, len(self.r.m_Active))
        self.r.HCRecordResult(first.Proposal.Id, False, 0)
        self.assertEqual(1, len(self.r.m_Active))

    def test_save_failure_latches_budget_and_logs_once(self):
        self.assertTrue(self.b.TryReserve('existing-site', 1))
        self.f.fail_write = True
        self.assertFalse(self.r.HCSaveCustody())
        self.assertFalse(self.r.m_CustodyReady)
        self.assertFalse(self.b.TryReserve('site:must-fail-closed', 1))
        self.assertFalse(self.b.TryReserve('existing-site', 1))
        self.assertFalse(self.r.HCSaveCustody())
        self.assertEqual(1, sum('CUSTODY SAVE FAILED' in line for line in self.f.logs))

    def test_each_foldback_failure_releases_finished_lease_once(self):
        for failure in ('world', 'faction', 'fact', 'strength'):
            with self.subTest(failure=failure):
                self.setUp()
                lease = self.f.offer()
                if failure == 'world': self.f.world = None
                if failure == 'faction': self.f.world.GetFaction = lambda key: None
                if failure == 'fact': self.f.world.AddFact = lambda *args: False
                if failure == 'strength': self.f.world.AdjustStrength = lambda *args: False
                self.r.HCRecordResult(lease.Proposal.Id, True, 2)
                self.assertEqual([], self.r.m_Active)
                self.assertEqual((0, 0), (self.b.Groups(), self.b.Actors()))
                self.r.HCRecordResult(lease.Proposal.Id, True, 2)
                self.assertLessEqual(len(self.f.debits), 1)

    def test_long_party_id_has_bounded_distinct_leases(self):
        self.f.world.MaterializerRow = lambda index: self.f.proposal('x' * 90) if index == 0 else None
        first = self.f.offer()
        self.assertIsNotNone(first)
        self.assertLessEqual(len(first.Proposal.Id), 96)

    def test_module_stop_start_does_not_assume_process_body_absence(self):
        first = self.f.offer()
        self.r.m_StartedOnce = True
        self.r.OnStop()
        self.r.OnStart(N(EnableEncounters=True))
        self.assertIsNone(self.f.offer())
        self.assertEqual((1, 4), (self.b.Groups(), self.b.Actors()))
        self.r.HCRecordResult(first.Proposal.Id, True, 4)
        self.assertEqual((0, 0), (self.b.Groups(), self.b.Actors()))

    def test_legacy_canonical_image_migrates_without_replaying_cargo_or_casualties(self):
        first = self.f.offer()
        data = copy.deepcopy(self.r.m_Custody)
        data.SchemaVersion = 1
        del data.NextLease
        data.Rows[0].LeaseId = 'lease:party:synthetic-party:42'
        self.f.disk[self.r.m_CustodyPath] = self.f.encode(data)
        self.b.Release(first.Proposal.Id)
        self.r = self.f.runtime = self.f.new_runtime()
        self.r.OnStart(N(EnableEncounters=True))
        self.assertTrue(self.r.m_CustodyReady)
        self.assertEqual((2, 1), (self.r.m_Custody.SchemaVersion, self.r.m_Custody.NextLease))
        self.assertEqual('FINISHED_UNKNOWN', self.r.m_Custody.Rows[0].Outcome)
        self.assertEqual('cargo:synthetic-party', self.r.m_Custody.Rows[0].CargoId)
        saved = self.f.decode(self.f.disk[self.r.m_CustodyPath])
        self.assertEqual(2, saved.SchemaVersion)
        self.assertEqual([], self.f.debits)
        self.assertEqual([], self.f.facts)
        self.assertIsNotNone(self.f.offer())

    def test_unreadable_or_interrupted_restore_blocks_all_spawn_owners(self):
        for state in ('corrupt', 'intent', 'backup-only', 'noncanonical'):
            with self.subTest(state=state):
                self.setUp()
                path = self.r.m_CustodyPath
                if state == 'corrupt': self.f.disk[path] = '{'
                if state == 'intent': self.f.disk[path + '.tmp'] = 'interrupted'
                if state == 'backup-only': self.f.disk[path + '.bak'] = 'backup'
                if state == 'noncanonical': self.f.disk[path] = self.f.encode(self.r.m_Custody) + '\n'
                self.r.OnStart(N(EnableEncounters=True))
                self.assertFalse(self.r.m_CustodyReady)
                self.assertFalse(self.b.TryReserve('site:blocked', 1))
                self.assertFalse(self.b.TryReserve('adapter:blocked', 1))

    def test_late_claim_result_with_no_active_lease_releases_budget(self):
        first = self.f.offer()
        self.r.m_Active.Clear()  # explicit in-process detached provider result
        self.r.HCRecordResult(first.Proposal.Id, True, 2)
        self.assertEqual((0, 0), (self.b.Groups(), self.b.Actors()))
        self.assertEqual([], self.f.debits)  # no reconstructed world proposal

    def test_no_finished_eviction_can_remove_live_or_quarantined_identity(self):
        first = self.f.offer()
        first_row = self.r.m_Custody.Rows[0]
        second = self.f.data_policy.call('HCReservation', None, self.f.identity('quarantine'), 'quarantine', 4)
        second.Outcome = 'QUARANTINED'
        self.r.m_Custody.Rows.Insert(second)
        cap = self.f.env['HCAIPartyCustody'].MAX_ROWS
        for index in range(cap - 2):
            finished = self.f.data_policy.call('HCReservation', None, self.f.identity(str(index)), 'history:' + str(index), 4)
            finished.Outcome = 'FINISHED_UNKNOWN'
            self.r.m_Custody.Rows.Insert(finished)
        self.assertFalse(self.r.HCCustodyAllows(first.Proposal.Identity))
        self.assertFalse(self.r.HCCustodyAllows(self.f.identity('quarantine')))
        self.f.world.MaterializerRow = lambda index: self.f.proposal('next') if index == 0 else None
        self.r.m_Cooldowns[0] = 0
        self.assertIsNotNone(self.f.offer())
        self.assertIn(first_row, self.r.m_Custody.Rows)
        self.assertIn(second, self.r.m_Custody.Rows)
        self.assertEqual(cap, len(self.r.m_Custody.Rows))

    def test_late_typed_result_after_finished_eviction_releases_only_old_budget(self):
        first = self.f.offer()
        self.r.HCRecordResult(first.Proposal.Id, True, 4)
        self.r.m_Clock += 21600
        second = self.f.offer()
        self.assertIsNotNone(second)
        self.b.Restore(first.Proposal.Id, 4)
        result = N(HCIdentity=lambda: first.Proposal.Identity,
                   HCLeaseId=lambda: first.Proposal.Id,
                   HCMaterialized=lambda: True, HCSurvivors=lambda: 4)
        self.r.HCRecordTypedResult(result)
        self.assertEqual((1, 4), (self.b.Groups(), self.b.Actors()))
        self.assertEqual([second], self.r.m_Active)
        self.assertEqual(1, len(self.f.debits))


if __name__ == '__main__':
    unittest.main()
