"""Actual authored reservation-policy execution; synthetic crash boundaries only."""
import unittest
from types import SimpleNamespace as NS
if __package__:
    from tests.legacy.test_infected_contract import SOURCE, policy_functions
    from tests.legacy.test_infected_admission import UnqualifiedPathsPerformNoMutation as Admission
else:
    from tests.legacy.test_infected_contract import SOURCE, policy_functions
    from tests.legacy.test_infected_admission import UnqualifiedPathsPerformNoMutation as Admission


class InfectedPersistenceTests(unittest.TestCase):
    def test_retiring_a_horde_refunds_capacity_for_a_third_admission(self):
        from tests.legacy.test_infected_admission import Array, admission, module_call, translate
        # Explicit synthetic journal: two committed three-member hordes; the
        # first has three confirmed deaths. No native engine is simulated.
        records = Array(NS(Id=i, State=1, Reserved=3, Living=3, CreatedUtc=100,
            LastSignalUtc=100, BudgetReleased=False, RetiredUtc=0, HasRoute=False, Anchor=0)
            for i in (1, 2))
        sweeps = Array(NS(Living=n, ConfirmedDead=3-n, Accounted=3,
            Ambiguous=False, Stimulus=None, Engaged=False, Sum=0) for n in (0, 3))
        records[0].State = 5  # Retirement/wipe has been recorded by the lifecycle.
        ctx = NS(m_State=NS(Groups=records, Reserved=6), m_Sweeps=sweeps,
            m_Packs=Array([None, None]), m_Actors=Array(), m_Dirty=False,
            m_GroupCap=2, m_Admission=admission(CEAdoption=True), m_Now=10,
            SnapshotRoute=lambda *a: None, ResetSweep=lambda: None)
        policy = NS(**policy_functions())
        logs = []
        namespace = dict(HCInfectedPolicy=policy, Print=logs.append,
            vector=NS(DistanceSq=lambda *a: 0))
        # Bind only an authored lifecycle helper if present; no harness changes.
        if "protected void RefundRetired(" in (SOURCE / "HCInfectedModule.c").read_text():
            refund = translate("HCInfectedModule.c", "protected void RefundRetired(", (), **namespace)
            namespace["RefundRetired"] = lambda record, utc: refund(ctx, record, utc)
            ctx.RefundRetired = namespace["RefundRetired"]
        module_call("protected void FinishSweep(", ctx, 110, **namespace)
        self.assertEqual(3, ctx.m_State.Reserved, "retirement must refund the horde ledger")
        active = sum(record.State != 5 for record in records)
        self.assertTrue(policy.CanReserve(active, 2, ctx.m_State.Reserved, 6, 3))

    def test_prepared_reservation_can_only_commit_once_with_exact_ledger(self):
        p = policy_functions()["CommitAdoptionRecord"]
        valid = [1, 1, 6, 6, 6, 6, 6, 0, 100, 100, 1, 2]
        self.assertTrue(p(*valid))
        for index, value in ((1, 2), (3, 5), (5, 7), (5, 5), (6, 0),
                             (7, 3), (9, 101), (10, 2), (11, 1), (11, 3)):
            args = valid.copy(); args[index] = value
            self.assertFalse(p(*args), args)

    def test_adoption_stages_reject_replay_and_abort_reactivation(self):
        p = policy_functions()["ValidAdoptionStagePair"]
        for old, new in ((1, 1), (1, 2), (1, 3), (2, 2), (3, 3)):
            self.assertTrue(p(old, new), (old, new))
        for old, new in ((0, 1), (2, 1), (2, 3), (3, 1), (3, 2), (-1, 1)):
            self.assertFalse(p(old, new), (old, new))

    def test_record_stage_requires_unresolved_preparation_and_conflicted_abort(self):
        p = policy_functions()["ValidAdoptionRecord"]
        for args in ((1, 6, False), (2, 0, False), (2, 6, True), (3, 6, True), (3, 5, True)):
            self.assertTrue(p(*args), args)
        for args in ((-1, 0, False), (1, 0, False), (1, 6, True), (3, 6, False), (3, 0, True)):
            self.assertFalse(p(*args), args)

    def test_actual_transfer_outcome_fails_closed_on_readback_or_partial_release(self):
        p = policy_functions()["AdoptionOutcome"]
        # 0=no transfer authorized; 2=committed; 3=abort and retain reservation.
        self.assertEqual(0, p(False, False, False, False))
        self.assertEqual(0, p(False, True, True, False))
        self.assertEqual(2, p(True, False, False, False))
        self.assertEqual(2, p(True, True, True, False))
        self.assertEqual(3, p(True, True, False, False))
        self.assertEqual(3, p(True, True, True, True))

    def test_restart_never_replays_prepared_transfer(self):
        p = policy_functions()["AdoptionAfterRestart"]
        self.assertEqual(3, p(1))
        self.assertEqual(2, p(2))
        self.assertEqual(3, p(3))
        self.assertEqual(-1, p(-1))
        # Given crash after preparation, restart retains phase 3, state 6 and
        # the same reservation; no transition can turn that phase into commit.
        self.assertFalse(policy_functions()["ValidAdoptionStagePair"](p(1), 2))

    def test_snapshot_schema_rejects_pre_intent_state(self):
        p = policy_functions()["ValidSnapshotHeader"]
        self.assertFalse(p(1, True, 1, 1, 6, 24, 100, 101))
        self.assertTrue(p(2, True, 1, 1, 6, 24, 100, 101))

    def test_actual_orchestration_persists_before_native_transfer_and_after_result(self):
        module = (SOURCE / "HCInfectedModule.c").read_text()
        adopt = module.split("protected void TryAdopt", 1)[1].split("protected void TryInvestigate", 1)[0]
        before = adopt.index('SaveAdoptionBoundary("prepare")')
        transfer = adopt.index("pack.Start(")
        after = adopt.index('SaveAdoptionBoundary("outcome")')
        self.assertLess(before, transfer)
        self.assertLess(transfer, after)
        self.assertIn("if (!SaveAdoptionBoundary", adopt)
        self.assertIn("record.AdoptionStage = 1", adopt)
        self.assertIn("AdoptionOutcome", adopt)
        self.assertNotIn("m_State.Reserved -=", adopt)
        boundary = module.split("protected bool SaveAdoptionBoundary", 1)[1].split("protected void TryAdopt", 1)[0]
        self.assertIn("HCInfectedStore.Save", boundary)
        self.assertIn("Quarantine", boundary)

    def test_unqualified_adoption_writes_no_prepare_intent_and_reserves_nothing(self):
        # Requested-but-unadmitted CE adoption must not create a durable reservation:
        # a prepare record would pin finite escrow for a transfer that never runs.
        probe = Admission("test_ce_adoption_requested_but_unadmitted_does_not_reserve_save_capture_or_transfer")
        probe.setUpClass()
        probe.test_ce_adoption_requested_but_unadmitted_does_not_reserve_save_capture_or_transfer()
        module = (SOURCE / "HCInfectedModule.c").read_text()
        adopt = module.split("protected void TryAdopt", 1)[1].split("protected void TryInvestigate", 1)[0]
        self.assertLess(adopt.index("m_Admission.CEAdoption"), adopt.index('SaveAdoptionBoundary("prepare")'))
        self.assertLess(adopt.index("m_Admission.CEAdoption"), adopt.index("m_State.Groups.Insert(record)"))

    def test_restart_validates_generations_and_latches_aborted_preparation(self):
        state = (SOURCE / "HCInfectedState.c").read_text()
        self.assertIn("ValidAdoptionStagePair", state)
        self.assertIn("CommitAdoptionRecord", state)
        self.assertIn("ValidAdoptionRecord", state)
        self.assertIn("AdoptionAfterRestart", state)
        self.assertIn("group.RecoveryConflicted = true", state)
        self.assertIn("snapshot.SchemaVersion = 2", state)


if __name__ == "__main__": unittest.main()
