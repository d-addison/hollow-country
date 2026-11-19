"""HC-28: one behavioral scenario; authored handlers, synthetic native ports.

No native inventory, engine generation, disk durability or DayZ qualification.
RED/GREEN receipts and unresolved acceptance are in docs/OPS_RECOVERY.md.
"""
import functools
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
RECOVERY = SCRIPTS / '4_World/Core/HCPersistenceDisposition.c'


def authored(path, kind, target, env, member=False):
    """Existing restricted translator, with syntax-only types/out bindings."""
    source = path.read_text()
    match = re.search(r'class ' + kind + r'\s*\{', source)
    source = body(source, match.end())
    names = re.findall(r'\b(?:static )?(?:bool|int|string|void|HC\w+) (\w+)\(', source)
    source = source.replace('FileHandle ', 'HCEventNativeFileHandle ')
    source = re.sub(r'\b(HC(?:Recovery\w+|Persistence\w+|GroupIO|GroupJson))\b', r'HCEvent\1', source)
    scope = {('HCEvent' + k if k.startswith('HC') else k): v for k, v in env.items()}
    # Native out parameters only: these fixtures supply bytes/DTOs, no policy.
    source = re.sub(r'HCEventHCGroupIO.HCReadRaw\(([^,]+), ([^,]+), (\w+)\)',
                    r'((\3 := raw_read(\1, \2)) != null)', source)
    source = re.sub(r'HCEventHCGroupJson<HCEvent(\w+)>\.Load\(([^,]+), ([^,]+), (\w+)\)',
                    r'((\4 := load_json(\2, \3, "\1")) != null)', source)
    if not member:
        source = re.sub(r'\bs_\w+\b', lambda m: 'HCEvent' + kind + '.' + m[0], source)
    for name in names:
        fn = translate(source, name, scope, 'HCEvent' + kind, member=member)
        setattr(target, name, functools.partial(fn, target) if member else fn)
    return target


class RecoveryBehavior(unittest.TestCase):
    def test_old_journal_new_native_quarantines_then_only_explicit_pair_opens(self):
        # Regression first: old Load accepted corrupt input as a clean world.
        logs = []
        disk = {'world': '{CORRUPT', 'world.bak': 'completed-history'}
        env = dict(Print=logs.append, FileExist=lambda p: p in disk,
                   HCWorldClock=N(UTC=lambda: 100),
                   HCWorldData=N(Fresh=lambda now: N(Meta=N(Epoch=now))),
                   HCPersistenceDisposition=N(HCAdmitStore=lambda *a: True,
                                             HCQuarantine=lambda *a: False),
                   HCRecoveryGate=N(HCReady=lambda: True))
        world = N(m_Path='world', m_Temp='world.tmp', m_Backup='world.bak',
                  m_Data=None, m_KeepBackup=False, m_Fresh=False, m_Fault=False,
                  Prepare=lambda: True, ReadCurrent=lambda: False)
        world.Preserve = lambda path: True  # Synthetic old copy seam.
        load = translate(STORE.read_text().replace('HCWorldData ', 'HCEventWorldData '),
                         'Load', env, 'HCWorldStore', member=True)
        self.assertFalse(load(world), 'corrupt world must refuse, never become fresh')
        self.assertIsNone(world.m_Data)
        self.assertEqual({'world': '{CORRUPT', 'world.bak': 'completed-history'}, disk)

        h = Harness(self)
        # EXPLICIT SYNTHETIC old HC generation 7, native inventory generation 8.
        h.native.Generation = 8
        self.assertFalse(h.recovery.HCLoad())
        self.assertEqual('generation_mismatch', h.gate.s_Reason)
        self.assertFalse(h.gate.HCAllowWrite(h.group_path))
        # Execute actual IO guards too: refused paths cannot touch native IO.
        self.assertFalse(h.io.Read(h.group_path, 1024, ''))
        self.assertFalse(h.io.WriteNew(h.group_path, 'replacement', 1024))
        self.assertEqual([], h.opened)
        self.assertNotIn(h.active, h.files)
        # Matching numbers alone never assert native consistency or restore.
        h.native.Generation = 7
        h.hc.PairedRestore = False
        self.assertFalse(h.recovery.HCLoad())
        self.assertEqual('paired_restore_required', h.gate.s_Reason)
        h.hc.PairedRestore = True
        h.native.StoppedPairAttested = False
        self.assertFalse(h.recovery.HCLoad())
        h.native.StoppedPairAttested = True
        for kind in ('HCRecoveryHCReceipt', 'HCRecoveryNativeReceipt'):
            h.corrupt_receipts.add(kind)
            self.assertFalse(h.recovery.HCLoad())
            h.corrupt_receipts.clear()
        for pending in (h.world_path + '.tmp', h.clock_path + '.tmp'):
            h.files[pending] = 'interrupted'
            self.assertFalse(h.recovery.HCLoad())
            self.assertEqual('interrupted_store_intent', h.gate.s_Reason)
            h.files.pop(pending)
        for missing in (h.world_path, h.clock_path, h.group_path):
            original = h.files.pop(missing)
            self.assertFalse(h.recovery.HCLoad())
            self.assertFalse(h.gate.HCReady())
            h.files[missing] = original
        original = h.files[h.world_path]
        h.files[h.world_path] = 'corrupt'
        self.assertFalse(h.recovery.HCLoad())
        h.files[h.world_path] = NativeText('x' * 1048577)
        self.assertFalse(h.recovery.HCLoad())
        h.files[h.world_path] = original
        # Explicit operator restore: three bounded images + matching native pair.
        self.assertTrue(h.recovery.HCLoad())
        self.assertEqual(7, h.gate.HCGeneration())
        self.assertIn(h.active, h.files)
        self.assertFalse(h.gate.s_GroupOpened)
        self.assertTrue(h.gate.HCReadImage(h.group_path, h.files[h.group_path]))
        self.assertTrue(h.gate.HCAllowWrite(h.group_path))
        self.assertEqual('transient', h.gate.HCDisposition('invitation'))
        self.assertEqual('native', h.gate.HCDisposition('native_inventory'))
        self.assertEqual('durable', h.gate.HCDisposition('world'))
        # A crash / ordinary restart cannot reuse the attestation after writes.
        self.assertFalse(h.recovery.HCLoad())
        self.assertEqual('unclosed_native_session', h.gate.s_Reason)
        before = dict(h.files)
        for _ in range(100):
            self.assertFalse(h.gate.HCAllowWrite(h.group_path))
        self.assertEqual(before, h.files)
        self.assertLessEqual(h.gate.s_Quarantine, 3)
        self.assertEqual('unclosed_native_session', h.gate.s_Reason)
        # A missing group must not write revision 1 without opening its pair.
        h.files.pop(h.active)
        self.assertTrue(h.recovery.HCLoad())
        self.assertFalse(h.io.WriteNew(h.group_path.replace('state_9', 'state_1'), 'empty', 1024))
        self.assertEqual('group_baseline_not_opened', h.gate.s_Reason)
        # A higher group revision cannot fall back to the attested old journal.
        h.files.pop(h.active)
        self.assertTrue(h.recovery.HCLoad())
        self.assertFalse(h.gate.HCReadImage(h.group_path.replace('state_9', 'state_10'), 'newer'))
        self.assertFalse(h.gate.HCReady())
        self.assertTrue(any('runtime=PENDING' in line and 'HC-28' in line for line in h.logs))


class NativeText(str):
    def Hash(self):
        # Explicit synthetic checksum; not native Hash and not cryptography.
        return sum((i + 1) * ord(c) for i, c in enumerate(self))


class Harness:
    world_path = '$profile:HollowCountry/world.json'
    clock_path = '$profile:HollowCountry/escalation.json'
    group_path = '$profile:HollowCountry/Groups/state/state_9.json'
    active = '$profile:HollowCountry/recovery-active.intent'

    def __init__(self, case):
        case.assertTrue(RECOVERY.is_file(), 'missing HC-28 shared recovery disposition')
        self.files = {self.world_path: NativeText('synthetic completed world'),
                      self.clock_path: NativeText('synthetic clock'),
                      self.group_path: NativeText('synthetic revision 9')}
        self.logs = []
        self.opened = []
        self.corrupt_receipts = set()
        self.hc = N(Version=1, Generation=7, WorldName='synthetic', PairedRestore=True,
                    NativeBackupId='synthetic-pair-7', GroupRevision=9,
                    WorldLength=len(self.files[self.world_path]), WorldHash=self.files[self.world_path].Hash(),
                    EscalationLength=len(self.files[self.clock_path]), EscalationHash=self.files[self.clock_path].Hash(),
                    GroupLength=len(self.files[self.group_path]), GroupHash=self.files[self.group_path].Hash())
        self.native = N(Version=1, Generation=7, WorldName='synthetic',
                        StoppedPairAttested=True, NativeBackupId='synthetic-pair-7')
        self.files['$profile:HollowCountry/recovery-hc.json'] = 'synthetic DTO'
        self.files['$profile:HollowCountry/recovery-native.json'] = 'synthetic DTO'
        self.gate = N(s_Admitted=False, s_Generation=0, s_Quarantine=0,
                      s_Reason='not_loaded', s_GroupPath='', s_GroupLength=0,
                      s_GroupHash=0, s_GroupOpened=False)
        self.recovery = N()
        self.io = N()
        env = dict(HCRecoveryGate=self.gate, HCPersistenceDisposition=self.recovery,
                   Print=self.logs.append, str=str, FileExist=lambda p: p in self.files,
                   GetGame=lambda: N(IsServer=lambda: True, GetWorldName=lambda: 'synthetic'),
                   raw_read=lambda path, limit: self.files.get(path) if 0 < len(self.files.get(path, '')) <= limit else None,
                   load_json=lambda path, limit, kind: None if kind in self.corrupt_receipts else (self.hc if kind == 'HCRecoveryHCReceipt' else self.native),
                   OpenFile=lambda *args: self.opened.append(args),
                   FileMode=N(READ=0, WRITE=1), HCGroupIO=self.io)
        authored(IO, 'HCRecoveryGate', self.gate, env)
        authored(IO, 'HCGroupIO', self.io, env)
        # Successful bounded IO is a native fixture port. Refused-path calls
        # above execute the actual authored Read/WriteNew guards.
        env['HCGroupIO'] = N(WriteNew=self.write)
        authored(RECOVERY, 'HCPersistenceDisposition', self.recovery, env)

    def write(self, path, text, limit):
        if path in self.files or not 0 < len(text) <= limit:
            return False
        self.files[path] = NativeText(text)
        return True


if __name__ == '__main__':
    unittest.main()
