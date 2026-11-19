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
    from tests.unit.build_identity_support import translate as build_identity
    env['HCBuildIdentity'] = build_identity()
    base_journal = env['HCEcologyMigrationJournal']
    def migration_journal():
        value = base_journal(); value.Build = ''
        return value
    env['HCEcologyMigrationJournal'] = migration_journal
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
    result.Build = env['HCBuildIdentity'].Canonical()
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

    def test_world_case_and_journal_build_are_checked_by_shared_identity(self):
        self.assertTrue(self.r.JournalValid(self.state, 'SYNTHETIC-World'))
        self.state.WorldName = 'SYNTHETIC-WORLD'
        self.assertTrue(self.r.JournalValid(self.state, 'synthetic-world'))
        for value in ('1.30.164289', '1.30.164289.70'):
            self.state.Build = value
            self.assertTrue(self.r.JournalValid(self.state, 'synthetic-world'))
        for value in ('', '1.30.164289.700', '1.30.1642890', '1.30.164289.71'):
            self.state.Build = value
            self.assertFalse(self.r.JournalValid(self.state, 'synthetic-world'))

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
        self.hidden = True; self.build_ok = True
        self.owns = True; self.ce = 1000; self.result = 2
        self.e['HCEcologyMigrationQualification'] = NS(Admitted=lambda: self.enabled)
        self.e['HCEcologyNative'] = NS(Authority=lambda: self.authority)
        self.e['HCEcologyMigrationNative'] = NS(
            CurrentWorld=lambda: 'synthetic-world', BuildSupported=lambda: self.build_ok,
            Unobserved=lambda members, clue: self.hidden, Ceiling=lambda kind: self.ce,
            Owns=lambda pack, members: self.owns,
            Choose=lambda members, now, visual, heard: self.clue,
            Move=lambda pack, clue, members, now: self.trace.append(('move', clue.Origin[:])) or self.result)
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
        for field, value in [('enabled', False), ('authority', False), ('owns', False), ('ce', 0), ('clue', None), ('hidden', False), ('build_ok', False)]:
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


class MigrationCohortWiringBehavior(unittest.TestCase):
    def test_only_exact_bounded_owned_group_is_enrolled_and_submitted(self):
        env = setup(); trace = []; enabled = [True]
        facade = NS(Enroll=lambda key, kind, interval: trace.append(('enroll', key, kind, interval)) or True,
                    Submit=lambda key, pack, members, now, visual, heard:
                        trace.append(('submit', key, list(members), now, visual, heard)) or 2)
        env['HCEcologyMigration'] = facade
        env['HCEcologyMigrationQualification'] = NS(Admitted=lambda: enabled[0])
        env['HCEcologyMigrationNative'] = NS(Owns=lambda pack, members: True)
        source = SERVICE.read_text().replace('HCNativeInfectedPack ', 'HCEcologyPack ').replace('HCInfectedActor ', 'HCEcologyActor ')
        submit = translated(source, 'SubmitCohort', env, 'HCEcologyMigration')
        actor = NS(GroupId=2, InfectedEntity=NS(IsAlive=lambda: True))
        other = NS(GroupId=3, InfectedEntity=NS(IsAlive=lambda: True))
        roster = EArray([actor, other]); pack = NS()
        self.assertEqual(2, submit(2, pack, roster, 1, 30., True, False))
        self.assertEqual([('enroll', 'infected-2', 2, 300),
                          ('submit', 'infected-2', [actor], 30., True, False)], trace)
        trace.clear()
        for roster_value, expected in ((roster,2),(EArray([actor]*25),1),(None,1)):
            self.assertEqual(0, submit(2,pack,roster_value,expected,30.,True,False))
            self.assertEqual([],trace)
        enabled[0] = False
        self.assertEqual(0, submit(2, pack, roster, 1, 30., True, False))
        self.assertEqual([], trace)


class MigrationStoreBehavior(unittest.TestCase):
    def setUp(self):
        self.e = setup(); self.files = {}; self.trace = []; self.failure_mode = ''
        self.state = journal(self.e)
        self.store = NS(m_Root='owned', m_World='synthetic-world', m_Revision=0, m_Fault=False)
        def encode(state):
            return json.dumps(vars(state), default=lambda obj: vars(obj), sort_keys=True)
        def native_decode(text):
            from tests.unit.json_loader_port import decode_json
            return decode_json(text, 'HCEcologyMigrationJournal', EArray)
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
        from tests.unit.json_loader_port import json_fields_port
        self.e.update(HCJsonFields=json_fields_port(), native_decode=native_decode)
        decode_source = STORE.read_text().replace(
            'JsonFileLoader<HCEcologyMigrationJournal>.LoadData(text, state, error)',
            '((state := native_decode(text)) != null)')
        decode = translated(decode_source, 'Decode', self.e, 'HCEcologyMigrationIO')
        self.e['HCEcologyMigrationIO'] = NS(Encode=encode, Decode=decode)
        self.e['HCEcologyRuntimeIO'] = NS(Write=write, WriteNew=new, Read=read)
        self.e['FileExist'] = lambda p: p in self.files or p in ('owned', '$profile:HollowCountry')
        self.e['MakeDirectory'] = lambda p: True
        self.e['DeleteFile'] = delete
        self.e['HCEcologyMigrationNative'] = NS(BuildSupported=lambda: True)
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

    def test_restart_resolves_ambiguous_attempt_durably_without_replay(self):
        self.e['HCEcologyMigrationRules'].Prepare(self.state, self.state.Schedules[0], 1800000300)
        self.files['owned/migration-state-synthetic-world.json'] = self.encode(self.state)
        reopened = self.open(self.store, 'synthetic-world', 1800000400)
        self.assertIsNotNone(reopened)
        slot = reopened.Schedules[0]
        self.assertFalse(slot.Pending)
        self.assertEqual((1, 1800000600, 4, 0),
                         (slot.Sequence, slot.NextDueUtc, slot.LastOutcome, slot.ReservedMembers))
        self.assertEqual(2, reopened.Revision)
        self.assertFalse(self.e['HCEcologyMigrationRules'].Due(slot, 1800000599))
        self.assertTrue(self.e['HCEcologyMigrationRules'].Due(slot, 1800000900))
        self.trace.clear()
        again = self.open(self.store, 'synthetic-world', 1800000500)
        self.assertEqual(2, again.Revision)
        self.assertEqual([], [op for op, path in self.trace if op != 'read'])

    def test_fresh_journal_uses_lowercase_paths_and_canonical_build(self):
        opened = self.open(self.store, 'SYNTHETIC-World', 1800000400)
        self.assertIsNotNone(opened)
        self.assertEqual(('synthetic-world', self.e['HCBuildIdentity'].Canonical(), 1),
                         (opened.WorldName, opened.Build, opened.Revision))
        self.assertEqual([], opened.Schedules)
        self.assertIn('owned/migration-state-synthetic-world.json', self.files)
        self.assertFalse(self.store.m_Fault)

    def test_wrong_or_missing_journal_build_and_live_build_refuse_without_writes(self):
        for build in ('', '1.30.164289.700', None):
            self.setUp()
            data = json.loads(self.encode(self.state))
            if build is None: del data['Build']
            else: data['Build'] = build
            self.files['owned/migration-state-synthetic-world.json'] = json.dumps(data)
            before = dict(self.files)
            self.assertIsNone(self.open(self.store, 'synthetic-world', 1800000400))
            self.assertEqual(before, self.files)
        self.setUp()
        self.e['HCEcologyMigrationNative'].BuildSupported = lambda: False
        self.assertIsNone(self.open(self.store, 'synthetic-world', 1800000400))
        self.assertEqual({}, self.files)

    def test_recovery_preserves_capacity_and_failed_write_quarantines(self):
        self.e['HCEcologyMigrationRules'].Prepare(self.state, self.state.Schedules[0], 1800000300)
        self.state.Schedules[0].ReservedMembers = 4
        self.files['owned/migration-state-synthetic-world.json'] = self.encode(self.state)
        self.failure_mode = 'intent'
        self.assertIsNone(self.open(self.store, 'synthetic-world', 1800000400))
        self.assertTrue(self.store.m_Fault)
        self.failure_mode = ''
        self.store.m_Fault = False
        opened = self.open(self.store, 'synthetic-world', 1800000400)
        self.assertEqual((4, 1, 4), (opened.Schedules[0].ReservedMembers,
                                  opened.Schedules[0].Sequence, opened.Schedules[0].LastOutcome))

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
        env['HCInfectedQualification'] = NS(InvestigationAdmitted=lambda:True, SupplementaryChainsAdmitted=lambda:True)
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
        env['HCInfectedQualification'].SupplementaryChainsAdmitted=lambda:False
        self.assertIsNone(choose(members,30.,False,True))

    def test_move_rechecks_marker_build_ownership_and_sight_after_write_ahead(self):
        env = setup(); moves = []; enabled = [True]; build = [True]; hidden = [True]; owned = [True]
        env['HCEcologyNative'] = NS(Authority=lambda: True)
        env['HCEcologyMigrationQualification'] = NS(Admitted=lambda: enabled[0])
        env['HCInfectedQualification'] = NS(NativePackRoutesAdmitted=lambda: True,
                                           HordeStimulusRoutesAdmitted=lambda: True)
        env['HCEcologyMigrationNative'] = NS(BuildSupported=lambda: build[0],
            Owns=lambda pack, members: owned[0], Unobserved=lambda members, clue: hidden[0])
        source = (ROOT / '4_World/Ecology/HCEcologyMigrationNative.c').read_text()
        source = source.replace('HCNativeInfectedPack ', 'HCEcologyPack ').replace('HCInfectedClue ', 'HCEcologyClue ')
        move = translated(source, 'Move', env, 'HCEcologyMigrationNative')
        pack = NS(Retarget=lambda clue, now: moves.append(now) or 2)
        for gate in (enabled, build, hidden, owned):
            gate[0] = False
            self.assertEqual(0, move(pack, NS(), EArray([NS()]), 30.))
            self.assertEqual([], moves)
            gate[0] = True
        self.assertEqual(2, move(pack, NS(), EArray([NS()]), 30.))
        self.assertEqual([30.], moves)

    def test_decode_bounds_before_native_json_and_canonicalizes_world(self):
        env = setup(); calls = []
        class Codec:
            def LoadData(self, text, state, error):
                calls.append(text)
                state.WorldName = 'SYNTHETIC-WORLD'
                state.Build = '1.30.164289.70'
                return True
        # Native out DTO syntax becomes an explicit mutable synthetic DTO.
        source = STORE.read_text().replace('HCEcologyMigrationJournal state;',
            'HCEcologyMigrationJournal state = new HCEcologyMigrationJournal;')
        source = source.replace('JsonFileLoader<HCEcologyMigrationJournal>', 'Codec')
        env['Codec'] = Codec()
        decode = translated(source, 'Decode', env, 'HCEcologyMigrationIO')
        for text in ('', ' ' * 16385): self.assertIsNone(decode(text))
        self.assertEqual([], calls)
        from tests.unit.json_loader_port import json_fields_port
        # Explicit synthetic required fields; native parse call remains a stub.
        env['HCJsonFields'] = json_fields_port()
        decode = translated(source, 'Decode', env, 'HCEcologyMigrationIO')
        payload = '{"LastUtc":1800000000,"Schedules":[]}'
        result = decode(payload + ' ' * (16384 - len(payload)))
        self.assertEqual('synthetic-world', result.WorldName)
        self.assertEqual(env['HCBuildIdentity'].Canonical(), result.Build)
        self.assertEqual(1, len(calls))

    def test_native_clock_reuses_consistent_shared_utc_reader(self):
        env = setup(); values = iter([1800000000, -1])
        env['HCGroupClock'] = NS(Utc=lambda: next(values))
        text = (ROOT / '4_World/Ecology/HCEcologyMigrationNative.c').read_text()
        utc = translated(text, 'Utc', env, 'HCEcologyMigrationNative')
        self.assertEqual(1800000000, utc())
        self.assertEqual(-1, utc())

    def test_gate_is_open_by_default_probes_disable_marker_once_and_does_not_promote_qualification(self):
        env = setup(); calls = []; logs = []; disabled = [False]
        source = (ROOT / '4_World/Ecology/HCEcologyMigrationNative.c').read_text()
        gate = NS(s_Checked=False, s_OptIn=False)
        # Mechanical static storage adaptation; no policy duplicated.
        fragment = source[:source.index('class HCEcologyMigrationNative')]
        fragment = re.sub(r'\bs_(Checked|OptIn)\b', r'HCEcologyMigrationQualification.s_\1', fragment)
        env['HCEcologyMigrationQualification'] = gate
        env['FileExist'] = lambda path: calls.append(path) or disabled[0]   # True = a .disable file exists
        env['Print'] = logs.append
        admission = (ROOT / '4_World/Core/HCV1Admission.c').read_text()
        env['HCV1Admission'] = NS(Line=translated(admission, 'Line', env, 'HCV1Admission'))
        for name in ('Qualified', 'LocalAcceptanceOptIn', 'Admitted'):
            setattr(gate, name, translated(fragment, name, env, 'HCEcologyMigrationQualification'))
        self.assertFalse(gate.Qualified())
        self.assertTrue(gate.Admitted())            # default with no marker is open
        self.assertEqual(['[HollowCountry] V1 admission feature=EcologyMigration preference=on gate=ecology_migration '
                          'qualified=0 result=admitted unverified: ecology_migration has no recorded native verdict; '
                          'opt out with acceptance/ecology_migration.disable'], logs)
        disabled[0] = True
        self.assertTrue(gate.Admitted()); self.assertEqual(1, len(calls))   # probed once
        self.assertTrue(calls[0].endswith('/acceptance/ecology_migration.disable') or calls[0].endswith('.disable'), calls[0])
        gate.s_Checked = False                       # simulated restart sees the opt-out
        self.assertFalse(gate.Admitted())
        self.assertIn('preference=off gate=ecology_migration qualified=0 result=off: operator opt-out', logs[-1])
        self.assertFalse(gate.Qualified())

if __name__ == '__main__':
    unittest.main()
