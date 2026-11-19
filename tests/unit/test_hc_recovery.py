"""HC-28 authored recovery/lifecycle handlers; explicit SYNTHETIC native IO.

No native inventory, filesystem durability, engine compile or DayZ acceptance.
The test ports provide bytes, DTO decoding, UTC and scheduler callbacks only.
"""
import functools
import fnmatch
import json
import re
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import body

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mods/HollowCountry/scripts'
IO = SCRIPTS / '3_Game/Groups/HCGroupIO.c'
STORE = SCRIPTS / '4_World/World/HCWorldStore.c'
CLOCK = SCRIPTS / '4_World/World/HCEscalationClock.c'
RECOVERY = SCRIPTS / '4_World/Core/HCPersistenceDisposition.c'


def authored(path, kind, target, env, member=False, only=None, modded=False):
    """Existing restricted translator with syntax/out-parameter adapters only."""
    source = path.read_text()
    match = re.search(('modded class ' if modded else r'class ') + kind + r'(?:\s*(?::|extends)\s*\w+)?\s*\{', source)
    source = body(source, match.end())
    names = re.findall(r'\b(?:static )?(?:bool|int|string|void|HC\w+) (\w+)\(', source)
    source = re.sub(r'\bFileHandle ', 'HCEventNativeFileHandle ', source)
    source = re.sub(r'FindFileHandle handle = FindFile\((.+?), filename, attr, (.+?)\)',
                    r'handle, filename, attr = find_first(\1, \2)', source)
    source = source.replace('found = FindNextFile(handle, filename, attr)',
                            'found, filename, attr = find_next(handle)')
    source = source.replace('FileAttr attr', 'int attr')
    source = re.sub(r'\b(HCRecovery\w+|HCPersistence\w+|HCGroupIO|HCGroupJson|HCWorldData|HCWorldClock|HCGroupClock|HCSaveJob|HCSaveScheduler|HCEscalation\w+|HCOperationalStatus|HCV2\w+)\b', r'HCEvent\1', source)
    scope = {('HCEvent' + k if k.startswith('HC') else k): v for k, v in env.items()}
    source = re.sub(r'HCEventHCGroupIO.HCReadRaw\(([^,]+), ([^,]+), (\w+)\)',
                    r'((\3 := raw_read(\1, \2)) != null)', source)
    source = re.sub(r'HCEventHCGroupJson<HCEvent(\w+)>\.Load\(([^,]+), ([^,]+), (\w+)\)',
                    r'((\4 := load_json(\2, \3, "\1")) != null)', source)
    source = source.replace('HCEventHCV2ThreatStore<HCEventHCEscalationState>', 'HCEventHCV2ThreatStore')
    source = source.replace('HCEventHCV2ThreatStore.Load(PATH, 2048, m_State)', 'clock_load(PATH, 2048)')
    source = re.sub(r'([\w.]+)\+\+;', r'\1 += 1;', source)
    source = re.sub(r'([\w.]+\([^()]*\))\.ToString\(\)', r'str(\1)', source)
    source = re.sub(r'foreach \(([^()\n]+)\) ([^{\n][^;\n]*);', r'foreach (\1) { \2; }', source)
    source = re.sub(r'\bs_\w+\b', lambda m: 'HCEvent' + kind + '.' + m[0], source)
    for name in names:
        if only is not None and name not in only:
            continue
        fn = translate(source, name, scope, 'HCEvent' + kind, member=member)
        params = re.search(r'\b' + name + r'\(([^)]*)\)', source)[1]
        fn.__defaults__ = tuple(json.loads(p.split('=')[1].strip()) for p in params.split(',') if '=' in p)
        setattr(target, name, functools.partial(fn, target) if member else fn)
    return target


class NativeText(str):
    def Hash(self):
        # Explicit synthetic checksum, NOT native Hash or cryptography.
        return sum((i + 1) * ord(c) for i, c in enumerate(self))


class Harness:
    world_path = '$profile:HollowCountry/world.json'
    clock_path = '$profile:HollowCountry/escalation.json'
    group_path = '$profile:HollowCountry/Groups/state/state_9.json'
    active = '$profile:HollowCountry/recovery-active.intent'
    hc_path = '$profile:HollowCountry/recovery-hc.json'
    native_path = '$profile:HollowCountry/recovery-native.json'

    def __init__(self):
        self.files, self.logs, self.opened = {}, [], []
        self.searches, self.search_steps, self.closed_searches = [], 0, 0
        self.now = 100
        self.gate = N(s_Admitted=False, s_Generation=0, s_Quarantine=0,
                      s_Reason='not_loaded', s_GroupPath='', s_GroupLength=0,
                      s_GroupHash=0, s_GroupOpened=False)
        self.recovery = N(s_Loaded=False, s_LoadOK=False, s_WorldStarted=False,
                          s_EscalationStarted=False, s_GroupsStarted=False)
        self.io = N()
        self.jobs = []
        self.env = dict(HCRecoveryGate=self.gate, HCPersistenceDisposition=self.recovery,
                        HCGroupIO=self.io, HCWorldClock=N(UTC=lambda: self.now),
                        HCGroupClock=N(Utc=lambda: self.now),
                        Print=self.logs.append, str=str,
                        FileExist=lambda p: p in self.files,
                        GetGame=lambda: N(IsServer=lambda: True, GetWorldName=lambda: 'synthetic'),
                        clock_load=self.clock_load, PATH=self.clock_path, MakeDirectory=lambda p: True, CopyFile=self.copy, DeleteFile=self.delete,
                        raw_read=self.read, load_json=self.load,
                        find_first=self.find_first, find_next=self.find_next,
                        CloseFindFile=self.close_find, FileAttr=N(DIRECTORY=0, INVALID=3),
                        FindFileFlags=N(DIRECTORIES=0), native_int=self.native_int,
                        OpenFile=lambda *args: self.opened.append(args), FileMode=N(READ=0, WRITE=1),
                        HCWorldData=N(Fresh=lambda now: N(Meta=N(Epoch=now)), Valid=lambda data: True),
                        HCSaveJob=N(STEP_MORE=0, STEP_DONE=1, STEP_FAILED=-1),
                        HCSaveScheduler=N(HCRegister=self.jobs.append, HCUnregister=lambda job: None,
                                          HCFlush=lambda job: job and job.HCDirty and job.Owner.HCFlushRoutine()),
                        HCV2Admission=N(Line=lambda *args: 'synthetic admission'),
                        HCV2ThreatStore=N(CanOpen=lambda path: not (path + '.tmp' in self.files or
                            path not in self.files and path + '.bak' in self.files),
                            Load=lambda *args: False, Save=self.clock_save),
                        HCEscalationState=lambda: N(Version=0, WorldName='', EpochUtc=0, SavedUtc=0),
                        HCEscalationSaveJob=lambda: N(HCDirty=False))
        authored(IO, 'HCRecoveryGate', self.gate, self.env)
        authored(IO, 'HCGroupIO', self.io, self.env)
        self.env['HCGroupIO'] = N(WriteNew=self.write, HCReadRaw=self.read)
        authored(RECOVERY, 'HCPersistenceDisposition', self.recovery, self.env)
        self.world = N(m_Path=self.world_path, m_Temp=self.world_path + '.tmp',
                       m_Backup=self.world_path + '.bak', m_Data=None, m_KeepBackup=False,
                       m_Fresh=False, m_Fault=False, m_SaveStage=0, m_VerifiedText='',
                       m_PendText='', m_PendPrior='', Prepare=lambda: True,
                       Read=lambda p: self.files.get(p, ''), Write=self.world_write,
                       Decode=self.decode_world, Encode=lambda data: NativeText('{"epoch":100}'))
        authored(STORE, 'HCWorldStore', self.world, self.env, member=True,
                 only=('Load', 'ReadCurrent', 'Fault', 'SaveFailed', 'SaveStep', 'Save'))
        self.clock = N(m_Healthy=False, m_State=None, m_NowUtc=0, m_SaveJob=None,
                       m_Operational=N(HCPublish=lambda *args: None),
                       IsEnabled=lambda settings: settings.EnableWorld, Report=lambda: None,
                       s_Instance=None)
        self.env['HCEscalationClock'] = self.clock
        authored(CLOCK, 'HCEscalationClock', self.clock, self.env, member=True,
                 only=('OnStart', 'OnTick', 'OnStop', 'Fail', 'Valid', 'HCFlushRoutine'))

    def read(self, path, limit):
        text = self.files.get(path)
        return text if text and len(text) <= limit else None

    @staticmethod
    def native_int(value):
        # Explicit synthetic integer parse; no native overflow claim.
        match = re.match(r'^[+-]?\d+', value)
        return int(match[0]) if match else 0

    def find_first(self, pattern, flags):
        # Explicit synthetic, nonrecursive directory enumeration in insertion order.
        self.searches.append(pattern)
        parent, glob = pattern.rsplit('/', 1)
        entries = iter(p.rsplit('/', 1)[1] for p in self.files
                       if p.rsplit('/', 1)[0] == parent
                       and fnmatch.fnmatchcase(p.rsplit('/', 1)[1], glob))
        _, filename, attr = self.find_next(entries)
        return entries, filename, attr

    def find_next(self, handle):
        self.search_steps += 1
        filename = next(handle, '')
        return bool(filename), filename, 2  # Synthetic regular read-only file.

    def close_find(self, handle):
        self.closed_searches += 1

    def load(self, path, limit, kind):
        text = self.read(path, limit)
        from tests.unit.json_loader_port import decode_json
        return decode_json(text or '', kind)

    def write(self, path, text, limit):
        if path in self.files or not 0 < len(text) <= limit:
            return False
        self.files[path] = NativeText(text)
        return True

    def copy(self, src, dst):
        if src not in self.files or dst in self.files:
            return False
        self.files[dst] = self.files[src]
        return True

    def delete(self, path):
        return self.files.pop(path, None) is not None

    def world_write(self, path, text):
        if not self.gate.HCAllowWrite(path):
            return False
        return self.write(path, text, 1048576)

    def decode_world(self, text):
        try:
            value = json.loads(text)
            return N(Meta=N(Epoch=value['epoch'], LastTick=value.get('tick', value['epoch'])))
        except (ValueError, TypeError, KeyError):
            return None

    def clock_load(self, path, limit):
        self.clock.m_State = self.load(path, limit, 'HCEscalationState')
        return self.clock.m_State is not None

    def clock_save(self, path, state, limit):
        if not self.gate.HCAllowWrite(path):
            return False
        self.files[path] = NativeText(json.dumps(vars(state)))
        return True

    def restore_pair(self, groups=9):
        self.files[self.world_path] = NativeText('{"epoch":90}')
        self.files[self.clock_path] = NativeText('{"synthetic":"clock"}')
        if groups:
            self.files[self.group_path] = NativeText('{"synthetic":"group revision 9"}')
        hc = dict(Version=1, Generation=7, WorldName='synthetic', PairedRestore=True,
                  NativeBackupId='synthetic-pair-7', GroupRevision=groups,
                  WorldLength=len(self.files[self.world_path]), WorldHash=self.files[self.world_path].Hash(),
                  EscalationLength=len(self.files[self.clock_path]), EscalationHash=self.files[self.clock_path].Hash(),
                  GroupLength=len(self.files.get(self.group_path, '')),
                  GroupHash=NativeText(self.files.get(self.group_path, '')).Hash())
        native = dict(Version=1, Generation=7, WorldName='synthetic',
                      StoppedPairAttested=True, NativeBackupId='synthetic-pair-7')
        self.files[self.hc_path] = NativeText(json.dumps(hc))
        self.files[self.native_path] = NativeText(json.dumps(native))


class RecoveryBehavior(unittest.TestCase):
    def assert_normal_lone_boot(self, h):
        self.assertTrue(h.recovery.HCLoad(), 'lone receipt must not refuse healthy stores')
        self.assertEqual(0, h.gate.HCGeneration(), 'lone receipt must never apply a restore')
        for name in ('world', 'escalation', 'groups'):
            self.assertTrue(h.gate.HCReady(name))
        self.assertTrue(h.world.Load())
        h.clock.OnStart(N(EnableWorld=True))
        self.assertTrue(h.clock.m_Healthy)
        self.assertTrue(h.world_write(h.group_path, NativeText('synthetic healthy group flush')))
        self.assertEqual(0, h.gate.HCQuarantined())

    def test_lone_consumed_receipt_is_removed_without_reapplying_restore(self):
        for receipt in (Harness.hc_path, Harness.native_path):
            with self.subTest(receipt=receipt):
                h = Harness()
                # Deliberately non-JSON bytes: already-consumed identity is raw,
                # not a new DTO or a request to validate old image hashes.
                h.files[receipt] = NativeText('synthetic previously consumed bytes\n')
                h.files[receipt + '.consumed-99'] = h.files[receipt]
                self.assert_normal_lone_boot(h)
                self.assertNotIn(receipt, h.files)
                self.assertEqual('synthetic previously consumed bytes\n',
                                 h.files[receipt + '.consumed-99'])
                lines = [line for line in h.logs if 'recovery=consumed_receipt_cleanup' in line]
                self.assertEqual(1, len(lines))
                self.assertIn('runtime=PENDING', lines[0])
                self.assertEqual([receipt + '.consumed-*'], h.searches)
                self.assertEqual(1, h.closed_searches)
                h.recovery.HCStop()
                self.assertTrue(h.recovery.HCLoad())
                self.assertEqual(1, len(h.searches), 'normal boots must not scan archives')

    def test_unmatched_lone_receipt_refuses_only_restore_and_preserves_bytes(self):
        for receipt in (Harness.hc_path, Harness.native_path):
            for archive_suffix in (None, '.consumed-99', '.consumed-99.extra',
                                   '.consumed-0', '.consumed-099', '.stale-99'):
                with self.subTest(receipt=receipt, archive=archive_suffix):
                    h = Harness()
                    h.files[receipt] = NativeText('synthetic lone receipt')
                    if archive_suffix:
                        h.files[receipt + archive_suffix] = NativeText(
                            'different bytes' if archive_suffix == '.consumed-99'
                            else h.files[receipt])
                    other = h.native_path if receipt == h.hc_path else h.hc_path
                    h.files[other + '.consumed-99'] = h.files[receipt]
                    before = dict(h.files)
                    self.assert_normal_lone_boot(h)
                    self.assertTrue(all(h.files[p] == value for p, value in before.items()))
                    refusals = [line for line in h.logs if 'recovery=attestation_refused' in line]
                    self.assertEqual(1, len(refusals))
                    self.assertIn('reason=partial_restore_attestation', refusals[0])

    def test_lone_archive_scan_is_bounded_and_closes_handle(self):
        h = Harness()
        h.files[h.hc_path] = NativeText('synthetic lone receipt')
        for stamp in range(1, 66):
            h.files[h.hc_path + '.consumed-' + str(stamp)] = NativeText('different')
        h.files[h.hc_path + '.consumed-66'] = h.files[h.hc_path]
        self.assert_normal_lone_boot(h)
        self.assertIn(h.hc_path, h.files, 'beyond-cap match must not authorize cleanup')
        self.assertLessEqual(h.search_steps, 64)
        self.assertEqual(1, h.closed_searches)

    def test_lone_cleanup_failure_preserves_evidence_and_healthy_boot(self):
        h = Harness()
        h.files[h.native_path] = NativeText('synthetic consumed receipt')
        h.files[h.native_path + '.consumed-99'] = h.files[h.native_path]
        h.env['DeleteFile'] = lambda path: False
        authored(RECOVERY, 'HCPersistenceDisposition', h.recovery, h.env)
        before = dict(h.files)
        self.assert_normal_lone_boot(h)
        self.assertTrue(all(h.files[p] == value for p, value in before.items()))
        self.assertTrue(any('reason=stale_receipt_cleanup_failed' in line for line in h.logs))

    def test_two_inconsistent_receipts_still_refuse_without_removing_evidence(self):
        h = Harness()
        h.restore_pair()
        native = json.loads(h.files[h.native_path])
        native['Generation'] += 1
        h.files[h.native_path] = NativeText(json.dumps(native))
        before = dict(h.files)
        self.assertFalse(h.recovery.HCLoad())
        self.assertEqual(before, h.files)
        self.assertFalse(h.gate.HCReady('world'))
        self.assertEqual([], h.searches, 'pair validation must not search consumed archives')

    def test_first_boot_no_files_admits_fresh_stores(self):
        h = Harness()
        self.assertTrue(h.recovery.HCLoad(), 'first boot must not require restore receipts')
        self.assertTrue(h.world.Load())
        self.assertTrue(h.world.m_Fresh)
        h.clock.OnStart(N(EnableWorld=True))
        self.assertTrue(h.clock.m_Healthy)
        self.assertEqual(100, h.clock.m_State.EpochUtc)
        self.assertTrue(h.gate.HCAllowWrite(h.group_path.replace('state_9', 'state_1')))
        self.assertEqual(0, h.gate.HCQuarantined())

    def test_clean_stop_restart_admits_changed_images_without_receipts(self):
        h = Harness()
        self.assertTrue(h.recovery.HCLoad(), 'normal boot must not require restore receipts')
        self.assertTrue(h.world.Load())
        self.assertTrue(h.world.Save(h.world.m_Data))
        h.clock.OnStart(N(EnableWorld=True))
        h.now += 1
        h.clock.OnStop()
        h.recovery.HCStop()
        self.assertNotIn(h.active, h.files)
        self.assertTrue(h.recovery.HCLoad())
        self.assertTrue(h.world.Load())
        self.assertEqual(0, h.gate.HCQuarantined())

    def test_restore_attestation_consumed_once_and_revision_zero_valid(self):
        for revision in (0, 9):
            with self.subTest(revision=revision):
                h = Harness()
                h.restore_pair(revision)
                self.assertTrue(h.recovery.HCLoad())
                self.assertNotIn(h.hc_path, h.files, 'restore attestation must be consumed')
                self.assertNotIn(h.native_path, h.files)
                self.assertIn(h.hc_path + '.consumed-100', h.files)
                self.assertIn(h.native_path + '.consumed-100', h.files)
                h.files[h.world_path] = NativeText('{"epoch":100}')
                h.recovery.HCStop()
                self.assertTrue(h.recovery.HCLoad(), 'consumed hashes cannot pin subsequent saves')
                self.assertEqual(0, h.gate.HCQuarantined())

    def test_corrupt_world_quarantines_only_world_healthy_stores_flush_on_stop(self):
        h = Harness()
        h.files[h.world_path] = NativeText('{CORRUPT')
        before = dict(h.files)
        self.assertTrue(h.recovery.HCLoad(), 'one damaged store cannot refuse all admission')
        self.assertFalse(h.world.Load())
        self.assertIsNone(h.world.m_Data)
        self.assertFalse(h.gate.HCAllowWrite(h.world_path))
        h.recovery.HCStartStore('groups')
        h.clock.OnStart(N(EnableWorld=True))
        self.assertTrue(h.clock.m_Healthy)
        h.now += 5
        h.clock.OnTick(1)
        self.assertTrue(h.clock.m_Healthy, 'world fault must not latch escalation tick')
        h.clock.OnStop()
        self.assertIn(h.clock_path, h.files, 'healthy clock must flush on Stop')
        self.assertTrue(h.world_write(h.group_path, NativeText('synthetic healthy group flush')))
        h.recovery.HCStop()
        self.assertEqual(before[h.world_path], h.files[h.world_path])
        self.assertFalse(h.world.Save(N()))
        self.assertEqual(1, h.gate.HCQuarantined())

    def test_crash_intent_warns_and_validates_healthy_files(self):
        h = Harness()
        h.files[h.world_path] = NativeText('{"epoch":90}')
        h.files[h.active] = NativeText('synthetic unclosed intent')
        self.assertTrue(h.recovery.HCLoad(), 'unclosed intent is a warning, not damage')
        self.assertTrue(h.world.Load())
        self.assertEqual(0, h.gate.HCQuarantined())
        self.assertTrue(any('warning=unclosed_native_session' in line for line in h.logs))
        self.assertTrue(any('HC-28' in line and 'runtime=PENDING' in line for line in h.logs))

    def test_partial_backup_and_regression_preserve_evidence_per_store(self):
        for image, backup, temporary in (
            ('{"epoch":90}', '{broken', None),
            ('{"epoch":90,"tick":95}', '{"epoch":90,"tick":99}', None),
            (None, '{"epoch":90}', None),
            ('{"epoch":90}', None, 'partial intent'),
        ):
            with self.subTest(image=image, backup=backup, temporary=temporary):
                h = Harness()
                for path, value in ((h.world_path, image), (h.world_path + '.bak', backup),
                                    (h.world_path + '.tmp', temporary)):
                    if value is not None:
                        h.files[path] = NativeText(value)
                before = dict(h.files)
                self.assertTrue(h.recovery.HCLoad())
                self.assertFalse(h.world.Load(), 'damaged pair or revision regression must refuse world')
                self.assertEqual(before, {p: v for p, v in h.files.items() if p != h.active})
                self.assertFalse(h.gate.HCAllowWrite(h.world_path))
                self.assertTrue(h.gate.HCAllowWrite(h.clock_path))
                self.assertTrue(h.gate.HCAllowWrite(h.group_path))

    def test_escalation_damage_is_local_and_world_off_needs_no_clock(self):
        for current, backup in (('{broken', None),
                                ('{"Version":1,"WorldName":"synthetic","EpochUtc":80,"SavedUtc":90}', '{broken'),
                                ('{"Version":1,"WorldName":"synthetic","EpochUtc":80,"SavedUtc":90}',
                                 '{"Version":1,"WorldName":"synthetic","EpochUtc":80,"SavedUtc":95}')):
            with self.subTest(current=current, backup=backup):
                h = Harness()
                h.files[h.clock_path] = NativeText(current)
                if backup:
                    h.files[h.clock_path + '.bak'] = NativeText(backup)
                self.assertTrue(h.recovery.HCLoad())
                h.clock.OnStart(N(EnableWorld=True))
                self.assertFalse(h.clock.m_Healthy, 'corrupt clock pair or watermark regression must refuse')
                self.assertFalse(h.gate.HCAllowWrite(h.clock_path))
                self.assertTrue(h.world.Load())
                self.assertTrue(h.world.Save(h.world.m_Data))
                self.assertTrue(h.gate.HCAllowWrite(h.group_path))
        h = Harness()
        # Synthetic persisted admin-day adjustment legitimately changes epoch;
        # only a regressing saved watermark proves a backwards primary here.
        h.files[h.clock_path] = NativeText('{"Version":1,"WorldName":"synthetic","EpochUtc":90,"SavedUtc":100}')
        h.files[h.clock_path + '.bak'] = NativeText('{"Version":1,"WorldName":"synthetic","EpochUtc":80,"SavedUtc":95}')
        self.assertTrue(h.recovery.HCLoad())
        h.clock.OnStart(N(EnableWorld=True))
        self.assertTrue(h.clock.m_Healthy, 'persisted admin epoch change must remain valid')
        h = Harness()
        h.files[h.clock_path + '.tmp'] = NativeText('synthetic abandoned clock intent')
        self.assertTrue(h.recovery.HCLoad(False))
        h.clock.OnStart(N(EnableWorld=False))
        self.assertFalse(h.clock.m_Healthy)
        self.assertTrue(h.gate.HCAllowWrite(h.group_path))
        self.assertEqual(0, h.gate.HCQuarantined())

    def test_group_empty_directory_is_fresh_and_partial_revision_still_refused(self):
        from tests.unit.test_group_persistence import StoreHarness
        h = StoreHarness()
        config = h.rules['HCGroupSettings']()
        store = h.store(config)
        h.directories.add(store.m_Root)
        ok, state = store.Open(config, None)
        self.assertTrue(ok)
        self.assertEqual(1, state.Revision)
        h.files[store.PathFor('intent_', 2)] = NativeText('partial')
        reopened = h.store(config)
        self.assertFalse(reopened.Open(config, None)[0])

    def test_module_stops_flush_healthy_stores_before_last_intent_cleanup(self):
        from tests.unit.test_group_server import EArray
        h = Harness()
        self.assertTrue(h.recovery.HCLoad())
        for name in ('world', 'groups', 'escalation'):
            h.recovery.HCStartStore(name)
        # Explicit synthetic pending discovery batch. The authored service Stop
        # chooses to flush; native journal/DTO work is the fixture port here.
        service = N(m_Healthy=True, m_PendingVisits=EArray([object()]), m_Peers=EArray(),
                    FlushBatch=lambda: h.world_write(h.group_path, NativeText('synthetic batch')))
        service.s_Instance = service
        env = dict(h.env, HCGroupService=service)
        service_path = SCRIPTS / '4_World/Groups/HCGroupService.c'
        authored(service_path, 'HCGroupService', service, env, member=True, only=('Stop',))
        base_stop = service.Stop
        env['super'] = N(Stop=base_stop)
        module_path = SCRIPTS / '4_World/Groups/HCGroupModule.c'
        authored(module_path, 'HCGroupService', service, env, member=True, only=('Stop',), modded=True)
        module = N(m_Service=service)
        service.OnRPC = lambda *args: None
        env['DayZGame'] = N(Event_OnRPC=N(Remove=lambda *args: None))
        authored(module_path, 'HCGroupModule', module, env, member=True, only=('OnStop',))
        env['super'] = N(OnStop=module.OnStop)
        authored(module_path, 'HCGroupModule', module, env, member=True, only=('OnStop',), modded=True)
        # A different store has already closed. Healthy groups and escalation
        # must still flush, and the marker must survive until their final Stop.
        h.files[h.world_path] = NativeText('{broken')
        self.assertFalse(h.world.Load())
        h.recovery.HCStopStore('world')
        h.clock.OnStart(N(EnableWorld=True))
        h.now += 1
        module.OnStop()
        self.assertIn(h.group_path, h.files)
        self.assertFalse(h.gate.HCAllowWrite(h.group_path))
        self.assertIn(h.active, h.files)
        h.clock.OnStop()
        self.assertIn(h.clock_path, h.files)
        self.assertNotIn(h.active, h.files)


    def test_admission_call_sites_and_closed_world_tick(self):
        h = Harness()
        module_path = SCRIPTS / '4_World/World/HCWorldModule.c'
        world = N(m_Running=True)
        authored(module_path, 'HCWorldModule', world, h.env, member=True, only=('OnTick',))
        h.gate.HCReset()
        # No other tick fields exist: a closed world must return immediately.
        world.OnTick(60)
        # Execute the group recovery wrapper around a synthetic base lifecycle;
        # the actual base stop/service flush is exercised in the stop scenario.
        calls = []
        group = N(m_Service=object())
        env = dict(h.env, super=N(OnStart=lambda settings: calls.append(
            h.gate.HCAllowWrite(h.group_path))))
        authored(SCRIPTS / '4_World/Groups/HCGroupModule.c', 'HCGroupModule', group,
                 env, member=True, only=('OnStart',), modded=True)
        group.OnStart(N(EnableWorld=False))
        self.assertEqual([True], calls, 'HCLoad must precede group service admission')
        # Call the real world admission path through its observed UTC refusal;
        # it must have loaded recovery before attempting any store/DTO work.
        h = Harness()
        h.env['HCWorldClock'] = N(UTC=lambda: 0)
        h.env['HCV2Gates'] = N(Qualified=lambda *args: False)
        world = N(m_Running=False, m_AdmissionPrinted=False, IsEnabled=lambda settings: True)
        authored(module_path, 'HCWorldModule', world, h.env, member=True, only=('OnStart',))
        world.OnStart(N(EnableWorld=True))
        self.assertTrue(h.recovery.s_LoadOK)
        self.assertFalse(h.gate.HCReady('world'))
        self.assertTrue(h.gate.HCReady('groups'))
        self.assertTrue(h.gate.HCReady('escalation'))



if __name__ == '__main__':
    unittest.main()
