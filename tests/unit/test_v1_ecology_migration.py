"""Execute authored ecology with explicit synthetic ports; no DayZ acceptance."""
import json
import re
import unittest
from types import SimpleNamespace as NS
from tests.unit.test_ecology_runtime import ROOT, environment, translated, EArray

POLICY = ROOT / '4_World/Ecology/HCEcologyMigrationRules.c'
SERVICE = ROOT / '4_World/Ecology/HCEcologyMigration.c'
STORE = ROOT / '4_World/Ecology/HCEcologyMigrationStore.c'


def setup():
    env = environment()
    env['HCEcologyPopulation'] = NS(ANIMAL=1, INFECTED=2)
    rules = NS(); env['HCEcologyMigrationRules'] = rules
    source = POLICY.read_text()
    for name in re.findall(r'static (?:bool|int|void|HCEcology\w+) (\w+)\(', source):
        setattr(rules, name, translated(source, name, env, 'HCEcologyMigrationRules'))
    return env


def row(env, key='route-a'):
    result = env['HCEcologyMigrationSchedule']()
    result.Id = key; result.PopulationKind = 2; result.IntervalSeconds = 300
    result.Sequence = 0; result.ReservedMembers = 0; result.LastOutcome = 0
    result.NextDueUtc = 1800000300
    return result


def journal(env):
    result = env['HCEcologyMigrationJournal']()
    result.Version = 1; result.WorldName = 'synthetic-world'
    result.Revision = 1; result.LastUtc = 1800000000
    result.Schedules.Insert(row(env))
    return result


class MigrationRulesBehavior(unittest.TestCase):
    def setUp(self):
        self.e = setup(); self.r = self.e['HCEcologyMigrationRules']
        self.state = journal(self.e); self.slot = self.state.Schedules[0]

    def test_due_uses_absolute_utc_no_catchup_and_no_rollback(self):
        self.assertFalse(self.r.Due(self.slot, 1800000299))
        self.assertTrue(self.r.Due(self.slot, 1800000300))
        self.assertTrue(self.r.Prepare(self.state, self.slot, 1800086400))
        self.assertEqual(1800086700, self.slot.NextDueUtc)
        self.assertEqual(1, self.slot.Sequence)
        self.assertTrue(self.slot.Pending)
        self.assertFalse(self.r.Due(self.slot, 1800999999))
        self.assertFalse(self.r.Prepare(self.state, self.slot, 1800000000))

    def test_ce_capacity_is_a_ceiling_never_a_census_or_spawn_budget(self):
        self.assertEqual(6, self.r.MemberLimit(1000, 6))
        self.assertEqual(2, self.r.MemberLimit(2, 6))
        for value in (-2147483648, -1, 0):
            self.assertEqual(0, self.r.MemberLimit(value, 6))
        for budget in (0, 7, -1):
            self.assertEqual(0, self.r.MemberLimit(1000, budget))

    def test_malformed_duplicate_overflow_and_foreign_state_are_rejected(self):
        self.assertTrue(self.r.JournalValid(self.state, 'synthetic-world'))
        for field, value in [('Version', 0), ('WorldName', 'other'), ('Revision', -1), ('LastUtc', -1)]:
            old = getattr(self.state, field); setattr(self.state, field, value)
            self.assertFalse(self.r.JournalValid(self.state, 'synthetic-world'))
            setattr(self.state, field, old)
        for field, value in [('IntervalSeconds', 59), ('IntervalSeconds', 86401),
                             ('Sequence', 1000000001), ('NextDueUtc', 2147483647), ('Id', '../x')]:
            old = getattr(self.slot, field); setattr(self.slot, field, value)
            self.assertFalse(self.r.ScheduleValid(self.slot))
            setattr(self.slot, field, old)
        self.state.Schedules.Insert(row(self.e))
        self.assertFalse(self.r.JournalValid(self.state, 'synthetic-world'))
        self.state.Schedules = EArray(row(self.e, str(n)) for n in range(9))
        self.assertFalse(self.r.JournalValid(self.state, 'synthetic-world'))

    def test_completion_requires_the_exact_prepared_sequence_and_does_not_claim_arrival(self):
        self.assertTrue(self.r.Prepare(self.state, self.slot, 1800000300))
        self.assertFalse(self.r.Complete(self.slot, 2, 2))
        self.assertTrue(self.slot.Pending)
        self.assertTrue(self.r.Complete(self.slot, 1, 2))
        self.assertEqual(2, self.slot.LastOutcome)  # command accepted, not arrival
        self.assertFalse(self.slot.Pending)
        self.assertFalse(self.r.Complete(self.slot, 1, 2))

    def test_foreign_slot_and_exhaustion_cannot_mutate_state(self):
        other = row(self.e, 'foreign')
        self.assertFalse(self.r.Prepare(self.state, other, 1800000300))
        self.slot.Sequence = 1000000000
        self.assertFalse(self.r.Prepare(self.state, self.slot, 1800000300))
        self.assertFalse(self.slot.Pending)


class MigrationProviderBehavior(unittest.TestCase):
    def setUp(self):
        self.e = setup(); self.trace = []; self.enabled = True; self.authority = True
        self.state = journal(self.e); self.slot = self.state.Schedules[0]
        self.service = NS(m_State=self.state, m_Fault=False, m_World='synthetic-world')
        self.service.Persist = lambda: self.trace.append(('save', self.slot.Pending, self.slot.NextDueUtc)) or True
        self.clue = NS(Origin=[1., 0., 2.]); self.pack = NS(); self.members = EArray([NS()])
        self.owns = True; self.ce = 1000; self.result = 2
        self.e['HCEcologyMigrationQualification'] = NS(Admitted=lambda: self.enabled)
        self.e['HCEcologyNative'] = NS(Authority=lambda: self.authority)
        self.e['HCEcologyMigrationNative'] = NS(
            CurrentWorld=lambda: 'synthetic-world', Ceiling=lambda kind: self.ce,
            Owns=lambda pack, members: self.owns,
            Choose=lambda members, now, visual, heard: self.clue,
            Move=lambda pack, clue, now: self.trace.append(('move', clue.Origin[:])) or self.result)
        source = SERVICE.read_text().replace('HCNativeInfectedPack ', 'HCEcologyPack ').replace('HCInfectedClue ', 'HCEcologyClue ')
        self.submit = translated(source, 'SubmitOwned', self.e, 'HCEcologyMigration', True)

    def submit_now(self):
        return self.submit(self.service, 'route-a', self.pack, self.members, 1800000300, 30., True, True)

    def test_enrollment_preserves_cadence_and_rejects_unavailable_animal_destination(self):
        text = SERVICE.read_text()
        enroll = translated(text, 'EnrollOwned', self.e, 'HCEcologyMigration', True)
        self.e['HCEcologyMigrationNative'].AnimalDestinationSupported = lambda:False
        self.assertTrue(enroll(self.service,'route-a',2,300,1800000400))
        self.assertEqual(1800000300,self.slot.NextDueUtc)
        self.assertEqual([],self.trace)
        self.assertFalse(enroll(self.service,'animal-route',1,300,1800000400))
        self.assertEqual([],self.trace)
        self.assertEqual(1,len(self.state.Schedules))
        self.assertTrue(enroll(self.service,'route-b',2,600,1800000400))
        self.assertEqual(1800001000,self.state.Schedules[1].NextDueUtc)
        self.assertFalse(enroll(self.service,'route-b',2,300,1800000400))

    def test_write_ahead_of_native_move_and_terminal_receipt(self):
        self.assertEqual(2, self.submit_now())
        self.assertEqual([('save', True, 1800000600), ('move', [1., 0., 2.]),
                          ('save', False, 1800000600)], self.trace)
        self.assertEqual(1, self.slot.Sequence)
        self.assertEqual(0, self.submit_now())
        self.assertEqual(3, len(self.trace))

    def test_other_persisted_cohort_reservations_share_the_ce_ceiling(self):
        other = row(self.e, 'route-b')
        other.ReservedMembers = 2
        self.state.Schedules.Insert(other)
        self.ce = 2
        self.assertEqual(0, self.submit_now())
        self.assertEqual([], self.trace)
        self.ce = 3
        self.assertEqual(2, self.submit_now())
        self.assertEqual(1, self.slot.ReservedMembers)

    def test_rejected_geometry_still_consumes_persisted_schedule(self):
        self.result = 1
        self.assertEqual(1, self.submit_now())
        self.assertEqual(3, self.slot.LastOutcome)
        self.assertEqual(1800000600, self.slot.NextDueUtc)
        self.assertEqual(0, self.submit_now())

    def test_qualification_ownership_ce_or_missing_clue_vetoes_before_writes(self):
        for field, value in [('enabled', False), ('authority', False), ('owns', False), ('ce', 0), ('clue', None)]:
            old = getattr(self, field); setattr(self, field, value)
            self.assertEqual(0, self.submit_now(), field)
            self.assertEqual([], self.trace)
            setattr(self, field, old)
        self.members.extend([NS()] * 6)
        self.assertEqual(0, self.submit_now())
        self.assertEqual([], self.trace)

    def test_write_failures_latch_fault_and_never_replay_ambiguous_movement(self):
        self.service.Persist = lambda: False
        self.assertEqual(0, self.submit_now())
        self.assertTrue(self.service.m_Fault)
        self.assertEqual([], self.trace)
        self.assertTrue(self.slot.Pending)
        self.service.Persist = lambda: True
        self.assertEqual(0, self.submit_now())

    def test_terminal_failure_blocks_after_exactly_one_move(self):
        writes = []
        def save():
            writes.append(self.slot.Pending)
            return len(writes) == 1
        self.service.Persist = save
        self.assertEqual(1, self.submit_now())
        self.assertEqual([True, False], writes)
        self.assertTrue(self.service.m_Fault)
        self.assertEqual(0, self.submit_now())
        self.assertEqual([('move', [1., 0., 2.])], self.trace)


class MigrationStoreBehavior(unittest.TestCase):
    def setUp(self):
        self.e = setup(); self.files = {}; self.trace = []; self.failure_mode = ''
        self.state = journal(self.e)
        self.store = NS(m_Root='owned', m_World='synthetic-world', m_Revision=0, m_Fault=False)
        def encode(state):
            return json.dumps(vars(state), default=lambda obj: vars(obj), sort_keys=True)
        def decode(text):
            try:
                values = json.loads(text)
                result = self.e['HCEcologyMigrationJournal']()
                for key, value in values.items():
                    if key == 'Schedules':
                        rows = EArray()
                        for fields in value:
                            slot = self.e['HCEcologyMigrationSchedule']()
                            for field, datum in fields.items(): setattr(slot, field, datum)
                            rows.Insert(slot)
                        value = rows
                    setattr(result, key, value)
                return result
            except (ValueError, TypeError, AttributeError):
                return None
        def write(path, text, limit):
            self.trace.append(('write', path))
            if self.failure_mode == 'image':
                self.files[path] = 'torn'; return False
            self.files[path] = text; return True
        def new(path, text, limit):
            self.trace.append(('new', path))
            if path in self.files or self.failure_mode == 'intent': return False
            self.files[path] = text; return True
        def read(path, limit):
            self.trace.append(('read', path))
            text = self.files.get(path, '')
            if self.failure_mode == 'readback': return 'torn'
            return text if len(text) <= limit else ''
        def delete(path):
            self.trace.append(('delete', path))
            if self.failure_mode == 'clear': return False
            del self.files[path]; return True
        self.encode = encode
        self.e['HCEcologyMigrationIO'] = NS(Encode=encode, Decode=decode)
        self.e['HCEcologyRuntimeIO'] = NS(Write=write, WriteNew=new, Read=read)
        self.e['FileExist'] = lambda p: p in self.files or p in ('owned', '$profile:HollowCountry')
        self.e['MakeDirectory'] = lambda p: True
        self.e['DeleteFile'] = delete
        text = STORE.read_text()
        self.save = translated(text, 'Save', self.e, 'HCEcologyMigrationStore', True)
        self.open = translated(text, 'Open', self.e, 'HCEcologyMigrationStore', True)
        self.store.Save = lambda state: self.save(self.store, state)

    def test_write_order_and_readback_before_clear(self):
        self.assertTrue(self.save(self.store, self.state))
        self.assertEqual(['new', 'write', 'read', 'delete'], [op for op, path in self.trace])
        self.assertEqual(1, self.store.m_Revision)
        self.assertFalse(self.store.m_Fault)

    def test_each_failure_poisoned_and_preserves_ambiguous_files(self):
        for mode in ('intent', 'image', 'readback', 'clear'):
            self.setUp(); self.failure_mode = mode
            self.assertFalse(self.save(self.store, self.state), mode)
            self.assertTrue(self.store.m_Fault)
            before = list(self.trace); self.failure_mode = ''
            self.assertFalse(self.save(self.store, self.state))
            self.assertEqual(before, self.trace)
            if mode != 'intent': self.assertIn('owned/migration-pending-synthetic-world.json', self.files)

    def test_restart_retains_due_sequence_and_ambiguous_attempt_without_replay(self):
        self.e['HCEcologyMigrationRules'].Prepare(self.state, self.state.Schedules[0], 1800000300)
        self.files['owned/migration-state-synthetic-world.json'] = self.encode(self.state)
        reopened = self.open(self.store, 'synthetic-world', 1800000400)
        self.assertIsNotNone(reopened)
        slot = reopened.Schedules[0]
        self.assertTrue(slot.Pending)
        self.assertEqual((1, 1800000600), (slot.Sequence, slot.NextDueUtc))
        self.assertFalse(self.e['HCEcologyMigrationRules'].Due(slot, 1800000900))
        self.assertEqual([], [op for op, path in self.trace if op != 'read'])

    def test_pending_corrupt_world_clock_or_oversize_never_reinitializes(self):
        for mode in ('pending', 'corrupt', 'world', 'clock', 'oversize'):
            self.setUp()
            state = self.state
            if mode == 'world': state.WorldName = 'other'
            text = self.encode(state)
            if mode == 'corrupt': text = 'torn'
            if mode == 'oversize': text = ' ' * 16385
            self.files['owned/migration-state-synthetic-world.json'] = text
            if mode == 'pending': self.files['owned/migration-pending-synthetic-world.json'] = 'interrupted'
            before = dict(self.files)
            now = 1799999999 if mode == 'clock' else 1800000400
            self.assertIsNone(self.open(self.store, 'synthetic-world', now), mode)
            self.assertEqual(before, self.files)
            self.assertTrue(self.store.m_Fault)

    def test_missing_schedule_counters_cannot_reset_attempts_or_reserved_capacity(self):
        for field in ('Sequence', 'ReservedMembers', 'LastOutcome'):
            self.setUp()
            values = json.loads(self.encode(self.state))
            del values['Schedules'][0][field]
            self.files['owned/migration-state-synthetic-world.json'] = json.dumps(values)
            before = dict(self.files)
            self.assertIsNone(self.open(self.store,'synthetic-world',1800000400),field)
            self.assertEqual(before,self.files)

    def test_foreign_world_and_replayed_revision_have_no_writes(self):
        self.state.WorldName = 'other'
        self.assertFalse(self.save(self.store, self.state))
        self.state.WorldName = 'synthetic-world'; self.state.Revision = 2
        self.assertFalse(self.save(self.store, self.state))
        self.assertEqual([], self.trace)


class MigrationNativeBehavior(unittest.TestCase):
    def test_animal_provider_reports_unsupported_without_native_side_effects(self):
        env = setup()
        text = (ROOT / '4_World/Ecology/HCEcologyMigrationNative.c').read_text()
        fn = translated(text, 'AnimalDestinationSupported', env, 'HCEcologyMigrationNative')
        self.assertFalse(fn())

    def test_native_clue_selection_requires_owner_admission_and_freezes_evidence(self):
        env = setup(); frozen = []
        env['HCInfectedQualification'] = NS(InvestigationQualified=lambda:True, SupplementaryChainsQualified=lambda:True)
        env['HCInfectedObservation'] = NS(VisualSamplingAvailable=lambda:True)
        env['HCHordeStimulus'] = NS(PreferClue=lambda a,b,now:a is not None and b is None,
            FreezeClue=lambda clue: frozen.append(clue) or NS(**vars(clue)))
        text = (ROOT / '4_World/Ecology/HCEcologyMigrationNative.c').read_text()
        text = text.replace('HCInfectedClue ', 'HCEcologyClue ').replace('HCInfectedActor ', 'HCEcologyActor ')
        choose = translated(text, 'Choose', env, 'HCEcologyMigrationNative')
        visual = NS(Provenance=2, IsLive=lambda now: now == 30., Origin=[1.,0.,2.])
        actor = NS(Visual=visual, Heard=None, HeardExternally=False)
        members = EArray([actor])
        self.assertIsNone(choose(members,30.,False,False))
        self.assertEqual([], frozen)
        result = choose(members,30.,True,False)
        self.assertIsNot(result,visual); self.assertEqual(visual.Origin,result.Origin)
        self.assertIsNone(choose(members,31.,True,False))
        actor.Visual=None
        actor.Heard=NS(Provenance=1, IsLive=lambda now:True, Origin=[3.,0.,4.])
        self.assertIsNone(choose(members,30.,False,True))
        actor.HeardExternally=True
        self.assertIsNone(choose(members,30.,False,False))
        self.assertIsNotNone(choose(members,30.,False,True))
        env['HCInfectedQualification'].SupplementaryChainsQualified=lambda:False
        self.assertIsNone(choose(members,30.,False,True))

    def test_native_clock_reuses_consistent_shared_utc_reader(self):
        env = setup(); values = iter([1800000000, -1])
        env['HCGroupClock'] = NS(Utc=lambda: next(values))
        text = (ROOT / '4_World/Ecology/HCEcologyMigrationNative.c').read_text()
        utc = translated(text, 'Utc', env, 'HCEcologyMigrationNative')
        self.assertEqual(1800000000, utc())
        self.assertEqual(-1, utc())

    def test_gate_probes_marker_once_and_does_not_promote_qualification(self):
        env = setup(); calls = []; logs = []; present = [False]
        source = (ROOT / '4_World/Ecology/HCEcologyMigrationNative.c').read_text()
        gate = NS(s_Checked=False, s_OptIn=False)
        # Mechanical static storage adaptation; no policy duplicated.
        fragment = source[:source.index('class HCEcologyMigrationNative')]
        fragment = re.sub(r'\bs_(Checked|OptIn)\b', r'HCEcologyMigrationQualification.s_\1', fragment)
        env['HCEcologyMigrationQualification'] = gate
        env['FileExist'] = lambda path: calls.append(path) or present[0]
        env['Print'] = logs.append
        for name in ('Qualified', 'LocalAcceptanceOptIn', 'Admitted'):
            setattr(gate, name, translated(fragment, name, env, 'HCEcologyMigrationQualification'))
        self.assertFalse(gate.Qualified()); self.assertFalse(gate.Admitted())
        present[0] = True
        self.assertFalse(gate.Admitted()); self.assertEqual(1, len(calls))
        gate.s_Checked = False
        self.assertTrue(gate.Admitted()); self.assertTrue(any('EXPERIMENTAL' in log for log in logs))
        self.assertFalse(gate.Qualified())


if __name__ == '__main__':
    unittest.main()
