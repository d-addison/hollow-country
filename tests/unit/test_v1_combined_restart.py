"""#23 crash cuts against authored stores; explicit in-memory byte fixtures.

Each fixture starts with a valid committed image, then changes ONE owned file.
The three damage cuts are mid-document truncation, invalid JSON, and zero bytes.
Stale .tmp siblings are never adopted; stores may refuse or ignore them while
retaining depletion/reservations. Pending ecology markers always block startup.
These tests do not prove native parser behavior, disk durability or DayZ restart.
"""
import copy
import json
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch

from tests.unit import test_event_runtime as events
from tests.unit import test_group_persistence as groups
from tests.unit import test_search_economy_recovery as search
from tests.unit import test_search_economy_integration as interiors
from tests.unit import test_interiors_contract as pool
from tests.unit import test_infected_admission as infected
from tests.unit import test_ecology_runtime as ecology
from tests.unit import test_v1_ecology_migration as migration
from tests.unit.test_group_server import EArray
from tests.unit.test_search_economy import invoke as search_invoke
from tests.unit.build_identity_support import translate as build_identity

ROOT = events.ROOT


def encode(value): return json.dumps(value, default=vars, sort_keys=True)


def decode(text):
    """Explicit synthetic JSON object/managed-array adapter, no recovery policy."""
    def restore(value):
        if isinstance(value, dict): return N(**{k: restore(v) for k, v in value.items()})
        if isinstance(value, list): return EArray(restore(v) for v in value)
        return value
    try:
        value = json.loads(text)
        return restore(value) if isinstance(value, dict) else None
    except (ValueError, TypeError): return None


class EventFiles:
    def __init__(self):
        self.h = events.EventJournalTests(); self.h.setUp()
        self.files = self.h.io.files
        self.state = self.h.j.Load('synthetic_world')
        self.runtime_helper = events.EventRuntimeTests(); self.runtime_helper.setUp()
        self.runtime = self.runtime_helper.runtime()
        self.runtime_helper.ai.ready = True
        self.runtime_helper.mission.Family = 5
        self.runtime_helper.mission.ActorBudget = 2
        assert self.runtime.Announce(self.runtime_helper.mission, self.runtime_helper.ctx) == 0
        self.state = copy.deepcopy(self.runtime.m_State)
        self.state.Revision = 0
        # A valid completed transaction, followed by a second revision, proves
        # damage cannot cause fallback to an older revision.
        assert self.h.save(self.h.j, self.state)
        assert self.h.save(self.h.j, self.state)
        self.paths = ('image-2.json', 'intent-2.json', 'commit-2.json')

    def restart(self):
        loaded = self.h.open().Load('synthetic_world')
        if loaded:
            assert len(loaded.Runs) == 1
            assert loaded.Runs[0].Lease == self.state.Runs[0].Lease
            assert loaded.Director.NextId == self.state.Director.NextId
        return loaded is not None


class GroupFiles:
    def __init__(self):
        self.h = groups.StoreHarness()
        self.cfg = self.h.rules['HCGroupSettings']()
        self.s = self.h.store(self.cfg)
        ok, self.state = self.s.Open(self.cfg, None)
        assert ok
        q = self.h.rules['HCGroupRequest'](); q.Op = self.h.rules['HCGroupOp'].CREATE
        q.Name = 'Synthetic persisted group'
        assert self.h.rules['Apply'](self.state, self.cfg, q, 'alice', 2000000001) == 0
        self.state.Revision += 1
        assert self.s.Save(self.state)
        self.files = self.h.files
        self.paths = tuple(self.s.m_Root + '/' + prefix + '2.json'
                           for prefix in ('state_', 'intent_', 'commit_'))

    def restart(self):
        ok, state = self.h.store(self.cfg).Open(self.cfg, None)
        if ok:
            assert len(state.Groups) == 1
            assert state.Groups[0].Members == ['alice']
            assert state.Revision == 2
        return ok


class SearchManifestFiles:
    def __init__(self):
        self.h = search.SearchStoreOpenTests(); self.h.setUp()
        store, ok = self.h.opened(); assert ok
        self.files = self.h.files
        self.paths = (store.m_Root + '/manifest.json',)

    def restart(self): return self.h.opened(initialize=False)[1]


class SearchRecordFiles:
    def __init__(self):
        self.h = search.SearchRecoveryTerminalTests(); self.h.setUp()
        self.files = self.h.files
        for kind, phase in (('claim', 1), ('attempt', 1), ('result', 2)):
            self.files[self.h.s.PathFor(0, kind)] = encode(self.h.record(phase))
        self.paths = tuple(self.files)
        self.h.s.LoadRecord = lambda i, k: decode(self.files.get(self.h.s.PathFor(i, k), ''))

    def restart(self):
        # Recovered 2 (spent) or 3 (held) is terminal. Verify the real economy
        # refuses output, not just that parsing returned a number.
        phase = self.h.recover()
        assert phase in (2, 3)
        service = N(m_Ready=True, m_Enabled=True, m_Busy=False, m_Manifest=self.h.m,
                    m_Phases=EArray([phase]), m_Store=N(Healthy=lambda: True),
                    m_Source=N(ReadyFor=lambda m: True, CanTransfer=lambda *a: True))
        env = dict(self.h.env, GetGame=lambda: N(IsServer=lambda: True))
        service.Index = lambda site: 0
        service.Live = lambda actor: True
        assert not search_invoke('HCSearchEconomy.c', 'CanGrant', env, service, 'site_a', object())
        return phase == 2


class InteriorFiles:
    def __init__(self):
        self.h = interiors.StoreBuildAliasTests(); self.h.setUp()
        self.files = {}
        self.manifest = self.h.manifest('1.30.164289')
        self.files[self.h.root + '/manifest.json'] = encode(self.manifest)
        self.files[self.h.root + '/manifest.backup.json'] = encode(self.manifest)
        self.files[self.h.root + '/journal-v2.json'] = encode(self.h.journal(self.manifest))
        self.paths = tuple(self.files)
        self.h.env['load_json'] = lambda p: decode(self.files.get(p, ''))
        self.h.env['HCInteriorRules'].JournalVersionAccepted = lambda *a: pool.authored('JournalVersionAccepted', *a)

    def restart(self):
        return interiors.invoke('Open', self.h.env, self.h.store,
            self.h.config('1.30.164289'), copy.deepcopy(self.manifest), path=interiors.STORE_SOURCE)


class InteriorRecordFiles:
    def __init__(self):
        self.files, self.logs = {}, []
        self.site = N(SlotId=0, Id='instance_storage_v1', Item='Rag', Phase=0)
        self.manifest = N(SchemaVersion=1, Assignments=EArray([
            N(SlotId=0, InstanceId='instance', Item='Rag')]))
        self.env = dict(Print=self.logs.append, str=str, FileExist=lambda p: p in self.files,
            load_json=lambda p: decode(self.files.get(p, '')),
            HCInteriorRules=N(RecoverJournal=lambda *a: pool.authored('RecoverJournal', *a)))
        for kind, phase in (('claim', 1), ('attempt', 1), ('result', 2)):
            self.files['synthetic/' + kind + '_0.json'] = encode(N(
                SchemaVersion=2, SiteId=self.site.Id, Item='Rag', PlayerId='alice', Phase=phase))
        self.paths = tuple(self.files)

    def restart(self):
        shared = pool.authored_pool(); assert shared.Open(self.manifest)
        store = N(m_Root='synthetic', m_Fault=False, m_Pool=shared)
        for name in ('ClaimPath', 'AttemptPath', 'ResultPath', 'HoldPath', 'IsHeld',
                     'MatchesClaim', 'Quarantine'):
            setattr(store, name, lambda *a, name=name: interiors.invoke(
                name, self.env, store, *a, path=interiors.STORE_SOURCE))
        source = interiors.STORE_SOURCE.read_text()
        source = re.sub(r'HCInteriorJson<HCInteriorClaim>.Load\(((?:ClaimPath|AttemptPath|ResultPath)\(site.SlotId\)), (\w+)\)',
                        r'((\2 := load_json(\1)) != null)', source)
        for name in ('ClaimPath', 'AttemptPath', 'ResultPath', 'HoldPath', 'IsHeld', 'MatchesClaim', 'Quarantine'):
            source = re.sub(r'(?<![\w.])' + name + r'\(', 'self.' + name + '(', source)
        # Declarations retain their actual names; only call sites are qualified.
        source = re.sub(r'(string|bool|int) self\.', r'\1 ', source)
        original = Path.read_text
        with patch.object(Path, 'read_text', lambda p, *a, **kw: source if p == interiors.STORE_SOURCE else original(p, *a, **kw)):
            phase = interiors.invoke('RecoverSite', self.env, store, self.site, path=interiors.STORE_SOURCE)
        assert phase in (2, 3)
        self.site.Phase = phase
        assert not shared.TryReserve(self.site)
        return phase == 2


class InfectedFiles:
    """Actual slot selection/validation/restart; JSON/out params are synthetic."""
    def __init__(self):
        self.files, self.logs = {}, []
        self.path = ROOT / '4_World/Infected/HCInfectedState.c'
        self.source = self.path.read_text()
        self.policies = N(**infected.policy_functions())
        self.owner = N()
        self.env = dict(HCBuildIdentity=build_identity(), HCInfectedPolicy=self.policies,
            HCHordeRecovery=N(ValidateRoster=lambda record: self.roster(record),
                              SameRoster=lambda a, b: self.same_roster(a, b)),
            HCInfectedSnapshot=lambda: N(), DIRECTORY='synthetic/infected',
            FileExist=lambda p: p in self.files, Print=self.logs.append,
            read=lambda p: self.files.get(p, ''), decode=decode)
        for name in ('ValidPosition', 'Validate', 'LoadSlot', 'LoadVerbatim', 'ApplyRestart'):
            setattr(self.owner, name, lambda *a, name=name: self.call(name, *a))
            self.env[name] = getattr(self.owner, name)
        def load_slot(path, *args):
            ok, snapshot = self.owner.LoadSlot(path, None, *args)
            return snapshot if ok else None
        self.env['load_slot'] = load_slot
        for generation, slot in ((1, 'a'), (2, 'b')):
            state = N(SchemaVersion=2, Build='1.30.164289', WorldName='synthetic_world',
                Epoch=1, Generation=generation, Reserved=3, SavedUtc=100,
                Groups=infected.Array([infected.prepared_record(record_id=1)]))
            self.files['synthetic/infected/hordes-' + slot + '.json'] = encode(state)
        self.paths = tuple(self.files)

    def roster(self, record):
        return infected.translate('HCHordeRecovery.c', 'static bool ValidateRoster(', ())(None, record)

    def same_roster(self, a, b):
        return infected.translate('HCHordeRecovery.c', 'static bool SameRoster(', (),
                                  ValidateRoster=self.roster)(None, a, b)

    def call(self, name, *args):
        source = self.source
        source = source.replace('string content, error;', 'string content; string error;')
        source = source.replace('HCInfectedSnapshot a, b;', 'HCInfectedSnapshot a; HCInfectedSnapshot b;')
        source = source.replace('ReadBounded(path, content)',
            '((content := read(path)) != "" && content.Length() <= 65536)')
        source = source.replace('JsonFileLoader<HCInfectedSnapshot>.LoadData(content, snapshot, error)',
            '((snapshot := decode(content)) != null)')
        source = source.replace('content.Length()', 'len(content)')
        for slot in ('A', 'B'):
            source = source.replace('LoadSlot(path' + slot + ', ' + slot.lower() + ', world, memberCap, groupCap, now)',
                '((' + slot.lower() + ' := load_slot(path' + slot + ', world, memberCap, groupCap, now)) != null)')
        # Adapt out-snapshot to a tuple at just these two boundaries.
        if name in ('LoadSlot', 'LoadVerbatim'):
            match = re.search(r'static bool ' + name + r'\([^)]*\)\s*\{', source)
            start = match.end(); content = events.body(source, start)
            content = re.sub(r'return ([^;]+);', r'return (\1), snapshot;', content)
            source = source[:start] + content + source[start + len(events.body(source, start)):]
        # The established infected translator supplies syntax, never policy.
        original = Path.read_text
        def read(path, *a, **kw): return source if path == self.path else original(path, *a, **kw)
        with patch.object(Path, 'read_text', read):
            fn = infected.translate('HCInfectedState.c', 'static ' +
                ('void ' if name == 'ApplyRestart' else 'bool ') + name + '(',
                tuple(), **self.env)
        return fn(None, *args)

    def restart(self):
        ok, state = self.owner.LoadVerbatim(None, 'synthetic_world', 24, 2, 101)
        if ok:
            assert state.Reserved == 3 and state.Generation == 2
            self.owner.ApplyRestart(state)
            assert state.Reserved == 3
            assert state.Groups[0].AdoptionStage == 3
            assert state.Groups[0].RecoveryConflicted
            assert not state.Groups[0].HasRoute
        return ok


class EcologyFiles:
    def __init__(self):
        self.h = ecology.EcologyStoreRestartBehaviorTests(); self.h.setUp()
        self.files = self.h.files
        self.image = 'owned/state-synthetic-world.json'
        self.pending = 'owned/pending-synthetic-world.json'
        self.files[self.image] = encode(self.h.prior)
        self.paths = (self.image,)

    def restart(self):
        state = self.h.open(self.h.store, 'synthetic-world', 'session-b')
        if state:
            assert (state.Samples, state.PathQueries) == (12, 5)
            assert set(vars(state)) == set(self.h.prior)  # no entity handles restored
        return state is not None


class MigrationFiles:
    def __init__(self):
        self.h = migration.MigrationStoreBehavior(); self.h.setUp()
        self.files = self.h.files
        self.image = 'owned/migration-state-synthetic-world.json'
        self.pending = 'owned/migration-pending-synthetic-world.json'
        assert self.h.e['HCEcologyMigrationRules'].Prepare(self.h.state, self.h.slot
            if hasattr(self.h, 'slot') else self.h.state.Schedules[0], 1800000300)
        # da17531: Open rewrites a journal that still holds a pending attempt. The committed
        # fixture is the already-recovered image so a clean reopen performs no writes.
        assert self.h.e['HCEcologyMigrationRules'].RecoverPending(self.h.state) == 1
        self.files[self.image] = self.h.encode(self.h.state)
        self.paths = (self.image,)

    def restart(self):
        state = self.h.open(self.h.store, 'synthetic-world', 1800000400)
        if state:
            slot = state.Schedules[0]
            # da17531: Open durably resolves an ambiguous pending attempt (LastOutcome 4,
            # not replayed) instead of surfacing Pending; sequence and next-due are kept.
            assert (slot.Pending, slot.Sequence, slot.NextDueUtc, slot.LastOutcome) == (
                False, 1, 1800000600, 4)
            # No replay: the recovered attempt is not due again before its original next-due.
            assert not self.h.e['HCEcologyMigrationRules'].Due(slot, 1800000599)
            assert self.h.e['HCEcologyMigrationRules'].Due(slot, 1800000900)
        return state is not None


FACTORIES = dict(events=EventFiles, groups=GroupFiles, search_epoch=SearchManifestFiles,
    search_records=SearchRecordFiles, interior_epoch=InteriorFiles,
    interior_records=InteriorRecordFiles, infected=InfectedFiles,
    ecology=EcologyFiles, migration=MigrationFiles)


class CombinedRestartTests(unittest.TestCase):
    def test_corrupt_event_store_denies_runtime_start_without_new_ai_or_writes(self):
        f = EventFiles()
        f.files['image-2.json'] = ''
        before = copy.deepcopy(f.files)
        starts = list(f.runtime_helper.ai.starts)
        context = copy.deepcopy(f.runtime_helper.ctx); context.Session = 'synthetic-restart'
        self.assertFalse(f.runtime.Start(f.runtime_helper.cfg, context, f.h.open(),
                                        f.runtime_helper.observer, f.runtime_helper.ai))
        self.assertEqual(starts, f.runtime_helper.ai.starts)
        self.assertEqual(before, f.files)


def damage_case(factory, mode):
    def test(self):
        pristine = factory()
        self.assertTrue(pristine.restart(), 'valid fixture must reopen before injection')
        for path in pristine.paths:
            with self.subTest(path=path, mode=mode):
                f = factory()
                text = f.files[path]
                f.files[path] = text[:len(text)//2] if mode == 'truncate' else ('{broken-json' if mode == 'corrupt' else '')
                before = copy.deepcopy(f.files)
                ok = f.restart()
                # The backup is not authoritative and is never adopted; the
                # intact manifest/journal can still reopen with a torn backup.
                if path.endswith('/manifest.backup.json'): self.assertTrue(ok)
                else: self.assertFalse(ok)
                self.assertEqual(before, f.files, 'restart must preserve original bytes')
    return test


def temporary_case(factory):
    def test(self):
        pristine = factory(); self.assertTrue(pristine.restart())
        for path in pristine.paths:
            with self.subTest(path=path):
                f = factory()
                f.files[path + '.tmp'] = '{stale synthetic temp'
                before = copy.deepcopy(f.files)
                f.restart()  # exact-name stores ignore; enumerating stores refuse
                self.assertEqual(before, f.files)
    return test


for _name, _factory in FACTORIES.items():
    for _mode in ('truncate', 'corrupt', 'zero'):
        setattr(CombinedRestartTests, 'test_' + _name + '_' + _mode, damage_case(_factory, _mode))
    setattr(CombinedRestartTests, 'test_' + _name + '_stale_temp', temporary_case(_factory))


def pending_case(factory, mode):
    def test(self):
        f = factory()
        text = f.files[f.image]
        f.files[f.pending] = {'truncate': text[:len(text)//2], 'corrupt': '{broken', 'zero': '',
                              'stale_temp': text}[mode]
        if mode == 'stale_temp': f.files[f.pending + '.tmp'] = '{stale'
        before = copy.deepcopy(f.files)
        self.assertFalse(f.restart())
        self.assertEqual(before, f.files)
    return test


for _name, _factory in (('ecology', EcologyFiles), ('migration', MigrationFiles)):
    for _mode in ('truncate', 'corrupt', 'zero', 'stale_temp'):
        setattr(CombinedRestartTests, 'test_' + _name + '_pending_' + _mode, pending_case(_factory, _mode))


def hold_case(mode):
    def test(self):
        f = InteriorRecordFiles()
        path = 'synthetic/hold_0.json'
        text = encode(N(SchemaVersion=2, SiteId=f.site.Id, Item='Rag', PlayerId='SERVER_HOLD:synthetic', Phase=3))
        f.files[path] = {'truncate': text[:len(text)//2], 'corrupt': '{broken', 'zero': '',
                         'stale_temp': text}[mode]
        if mode == 'stale_temp': f.files[path + '.tmp'] = '{stale'
        before = copy.deepcopy(f.files)
        self.assertFalse(f.restart())  # marker presence retains quarantine, no JSON replay
        self.assertEqual(before, f.files)
    return test


for _mode in ('truncate', 'corrupt', 'zero', 'stale_temp'):
    setattr(CombinedRestartTests, 'test_interior_hold_' + _mode, hold_case(_mode))


if __name__ == '__main__': unittest.main()
