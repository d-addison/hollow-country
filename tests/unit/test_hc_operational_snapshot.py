"""HC-25 / consolidated Wave 2: explicit synthetic restricted-port fixtures.

Executes authored Enforce handlers; no DayZ/RPC/performance qualification.
Spec/plan input: .banso-writer/inputs/task.md HC-25. runtime=PENDING.

Actual TDD receipt (same command for RED and GREEN):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_operational_snapshot -v
RED: FAILED (failures=1), unauthorized Core row exposed: [] !=
     ['[HC Admin] module=Core enabled=0 active=0 budget=n/a'].
RED extension: FAILED (failures=1), ' state=off ' not found in disabled
     owner's state=unknown/source_state=off/freshness=stale row.
GREEN: Ran 1 test; OK (synthetic handlers, not engine acceptance).
Round 2 (same focused command above):
RED: Ran 7 tests; FAILED (failures=6): authorized status returned no owner rows;
Start retained prior-session owner; refresh became source_stale at t=73;
Stop retained state=ready; aggregate refusals 1 != 64; unloaded store closed.
GREEN: Ran 7 tests; OK. Explicit synthetic lifecycle/transport/store ports only.
Round 2 related-file/admin/compile/hygiene suites: Ran 500 tests;
OK (expected failures=1, pre-existing shared-work-budget case).
python3 -B -m tools.validate.enforce_lint --no-native:
pass findings=126 new=0 stale=0 native=no.

Round 1 related focused modules: 116 tests OK. Required checks plus formula complexity:
56 tests OK. Native compile, two-client RPC and performance remain PENDING.
"""
from pathlib import Path
from types import SimpleNamespace as N
import re
import unittest

from tests.unit.test_admin_test_kit import compile_authored, base_scope, authored_method
from tests.unit.test_hc_operational_status import authored_status
from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / 'mods/HollowCountry/scripts/4_World'


OPS = WORLD / 'Operations/HCOperationalContributors.c'
DEBUG = WORLD / 'Debug/HCDebugSnapshot.c'


class NativeMap(dict):
    def Get(self, key): return self.get(key)
    def Insert(self, key, value): self[key] = value
    def Clear(self): self.clear()
    def Count(self): return len(self)
    def GetKey(self, index): return list(self)[index]
    def GetElement(self, index): return list(self.values())[index]


class NativeString(str):
    def Length(self): return len(self.encode('utf-8'))
    def LengthUtf8(self): return len(self)
    def SubstringUtf8(self, start, count): return NativeString(self[start:start + count])
    # Concatenation keeps the synthetic native methods (Enforce strings always have them).
    def __add__(self, other): return NativeString(str.__add__(self, other))
    def __radd__(self, other): return NativeString(str.__add__(other, self))


def bind(obj, path, cls, names, scope, fields=(), members=(), modded=False, native_strings=None):
    for name in names:
        fn = compile_authored(path, cls, name, scope, members, modded=modded, fields=fields,
                              native_strings=native_strings)
        setattr(obj, name, lambda *args, fn=fn: fn(obj, *args))


def fixture():
    logs = []
    make_status, _ = authored_status(logs)
    cap = re.search(r'static const int HC_REGISTRY_CAP = (\d+);', DEBUG.read_text(encoding='utf-8'))
    debug = N(s_Contributors=None, s_RegistrationRefusals=0, HC_REGISTRY_CAP=int(cap.group(1)))
    service = N(s_Owners=EArray(), s_ByName=NativeMap(), s_Aggregate=None,
                s_Registered=False, s_RegistrationTried=False, s_Refused=0, MAX_SOURCE_AGE_SECONDS=60)
    scope = base_scope(array=EArray, HCOperationalContributors=service, HCDebugSnapshot=debug,
                       HCRecoveryGate=N(HCReady=lambda name:name != 'world',
                          HCDisposition=lambda name:'durable', HCGeneration=lambda:7,
                          HCQuarantined=lambda:1, HCReason=lambda:'synthetic_quarantine'),
                       Print=logs.append, HCAdminReply=lambda:N(Lines=EArray()))
    # Authored text policy, synthetic native UTF8 operations only.
    text_fn = compile_authored(DEBUG, 'HCDebugSnapshot', 'HCText', scope, modded=False)
    debug.HCText = lambda value, limit:text_fn(None, NativeString(value), limit)
    bind(debug, DEBUG, 'HCDebugSnapshot', ('HCRegister','HCUnregister','HCContributorCount'),
         scope, fields=('s_Contributors','s_RegistrationRefusals'))
    bind(debug, DEBUG, 'HCDebugSnapshot', ('HCResetRegistrationRefusals',), scope,
         fields=('s_RegistrationRefusals',))
    owner_fields = ('Name','Status','Requested','ObservedAt','CountersAt','Work','Cap','Refusals','Exception')
    owner_methods = ('HCObserve','HCCounters','HCStop','HCFreshness','HCLine')
    def owner():
        row = N(Name='', Status=make_status(), Requested=False, ObservedAt=-1, CountersAt=-1,
                Work=-1, Cap=-1, Refusals=-1, Exception='owner_counters_unobserved')
        bind(row, OPS, 'HCOperationalOwner', owner_methods, scope, fields=owner_fields,
             members=owner_methods)
        return row
    def budget():
        row = N(m_Limit=0, m_Used=0, m_Items=0)
        bind(row, WORLD / 'Core/HCUnitBudget.c', 'HCUnitBudget', ('HCReset','HCTake'), scope)
        return row
    def aggregate():
        row = N()
        bind(row, WORLD / 'Debug/HCDebugContributors.c', 'HCDebugOperationalContributor',
             ('HCDescribe',), scope)
        return row
    scope.update(HCOperationalOwner=owner, HCUnitBudget=budget, HCDebugOperationalContributor=aggregate,
                 GetGame=lambda:N(GetTickTime=lambda:125))
    methods = ('HCRegisterOwner','HCReset','HCCount','HCRefused','HCStoreLine',
               'HCRows','HCAppend','HCAdminRows','HCReport')
    bind(service, OPS, 'HCOperationalContributors', methods, scope,
         fields=('s_Owners','s_ByName','s_Aggregate','s_Registered','s_RegistrationTried','s_Refused'), members=methods)
    return service, debug, make_status, scope, logs


class OperationalSnapshot(unittest.TestCase):
    def lifecycle(self):
        from tests.unit import test_core_lifecycle as core
        service, debug, status, scope, logs = fixture()
        events = []
        report = status()
        report.HCPublish('ready', 'synthetic_ready')
        active = core.Module(NativeString('running'), events)
        active.HCGetOperationalStatus = lambda: report
        active.OnTick = lambda elapsed: None
        disabled = core.Module(NativeString('disabled'), events, enabled=False)
        state, _ = core.fixture(modules=[active, disabled], operational=service)
        return state, service, scope, logs

    def test_status_authorizes_before_describing_and_rechecks_delivery(self):
        service, _, _, scope, _ = fixture()
        service.HCRegisterOwner(NativeString('synthetic-status'))
        replies, described, refused = [], [], []
        sender = object()
        allowed = [True]
        describe = compile_authored(WORLD / 'Admin/HCAdminStatus.c', 'HCServer',
                                    'HCAdminDescribe', scope)
        def record(reply):
            describe(N(), reply)
            described.append(reply)
        scope.update(HCAdminReply=lambda:N(Authorized=False, Lines=EArray()),
                     HCServer=N(Get=lambda:N(HCAdminDescribe=record)))
        admin = N(HCAuthorized=lambda who:allowed[0] and who is sender,
                  HCRefused=lambda who:refused.append(who),
                  HCCommand=lambda *args:False)
        # The actual final sender gate is already exercised below; record its input here.
        admin.HCSend = lambda who, reply:replies.append(reply) if admin.HCAuthorized(who) else None
        bind(admin, WORLD / 'Admin/HCAdminModule.c', 'HCAdminModule',
             ('HCStatus', 'HCDispatch'), scope,
             members=('HCAuthorized','HCRefused','HCStatus','HCCommand','HCSend'))
        self.assertTrue(admin.HCDispatch(sender, 'status', 0, 1))
        self.assertTrue(any('owner=synthetic-status ' in line for line in replies[0].Lines),
                        'authorized status command returned no owner rows')
        allowed[0] = False
        self.assertFalse(admin.HCDispatch(sender, 'status', 0, 2))
        self.assertEqual(1, len(described))
        self.assertEqual(1, len(replies))
        self.assertEqual([sender], refused)
        admin.HCStatus(sender, 3)  # direct invocation still cannot expose cached rows
        self.assertEqual([], described[-1].Lines)
        self.assertEqual(1, len(replies))

    def test_start_registers_enabled_and_disabled_owners_and_reports(self):
        state, service, scope, logs = self.lifecycle()
        service.HCRegisterOwner(NativeString('prior-session'))
        state.Start()
        self.assertEqual(['running', 'disabled'], [row.Name for row in service.s_Owners])
        self.assertIn('state=ready', service.s_Owners[0].HCLine(12))
        self.assertIn('state=off', service.s_Owners[1].HCLine(12))
        self.assertTrue(any('[HC Plan] HC-25 contributors=1' in line for line in logs))

    def test_ticks_refresh_active_owner_past_source_ttl_with_bounded_work(self):
        from tests.unit import test_core_lifecycle as core
        state, service, scope, logs = self.lifecycle()
        state.Start()
        row = service.HCRegisterOwner(NativeString('running'))
        row.HCObserve(True, state.m_Active[0].HCGetOperationalStatus(), 12)
        clock = [12]
        tick_scope = dict(GetGame=lambda:N(IsServer=lambda:True, GetTickTime=lambda:clock[0]),
                          TickCount=lambda prior:0, Print=logs.append,
                          HCOperationalContributors=service)
        tick = core.actual_method('Tick', tick_scope)
        for now in range(13, 100):
            clock[0] = now
            tick(state)
            self.assertNotIn('source_stale', row.HCLine(now))
        self.assertGreaterEqual(row.ObservedAt, 87)
        # Deliberately oversized synthetic active array: publisher visits at most 64.
        reads = []
        for index in range(70):
            state.m_Active.Insert(N(GetName=lambda i=index:NativeString('extra-' + str(i)),
                                   OnTick=lambda elapsed:None,
                                   HCGetOperationalStatus=lambda i=index:reads.append(i)))
        attempts = []
        register = service.HCRegisterOwner
        service.HCRegisterOwner = lambda name:(attempts.append(name), register(name))[1]
        clock[0] = 115
        tick(state)
        self.assertEqual(64, len(attempts))
        self.assertEqual(62, len(reads))
        self.assertEqual(64, service.HCCount())

    def test_stop_marks_owner_before_callback_and_restart_discards_receipts(self):
        state, service, scope, logs = self.lifecycle()
        state.Start()
        row = service.HCRegisterOwner(NativeString('running'))
        row.HCObserve(True, state.m_Active[0].HCGetOperationalStatus(), 12)
        stopped = []
        state.m_Active[0].OnStop = lambda:stopped.append(row.HCLine(12))
        state.Stop()
        self.assertIn('state=off', stopped[0])
        self.assertFalse(row.Requested)
        self.assertIn('reason=server_stop_requested', row.HCLine(13))
        state.Start()
        self.assertIsNot(row, service.s_ByName.Get('running'))

    def test_full_contributor_registry_attempts_once_and_reset_clears_refusals(self):
        service, debug, _, _, _ = fixture()
        for _ in range(debug.HC_REGISTRY_CAP):
            self.assertTrue(debug.HCRegister(object()))
        for index in range(64):
            service.HCRegisterOwner(NativeString('owner-' + str(index)))
        self.assertEqual(1, debug.s_RegistrationRefusals,
                         'one saturated aggregate registration must not retry for every owner')
        service.HCReset()
        self.assertEqual(0, debug.s_RegistrationRefusals)
        self.assertFalse(service.s_RegistrationTried)
        service.HCRegisterOwner(NativeString('new-session'))
        self.assertEqual(1, debug.s_RegistrationRefusals)
        self.assertTrue(service.s_RegistrationTried)
        service.HCReset()
        debug.HCUnregister(debug.s_Contributors[0])
        service.HCRegisterOwner(NativeString('available-next-session'))
        self.assertTrue(service.s_Registered)
        self.assertEqual(0, debug.s_RegistrationRefusals)

    def test_not_loaded_store_receipt_is_pending_admission(self):
        service, _, _, scope, _ = fixture()
        scope['HCRecoveryGate'].HCReady = lambda name:False
        scope['HCRecoveryGate'].HCReason = lambda:'not_loaded'
        self.assertIn('recovery=pending_admission', service.HCStoreLine('world'))
        scope['HCRecoveryGate'].HCReason = lambda:'synthetic_quarantine'
        self.assertIn('recovery=closed_or_quarantined', service.HCStoreLine('world'))
        scope['HCRecoveryGate'].HCReady = lambda name:True
        self.assertIn('recovery=admitted', service.HCStoreLine('world'))

    def test_unauthorized_oversized_and_stale_cached_rows(self):
        # This first assertion is the actual preimplementation RED: original
        # HCAdminDescribe emitted a Core row without checking authorization.
        describe = compile_authored(WORLD / 'Admin/HCAdminStatus.c', 'HCServer',
                                    'HCAdminDescribe', base_scope())
        reply = N(Authorized=False, Lines=EArray())
        describe(N(m_Started=False, m_Registry=None), reply)
        self.assertEqual([], reply.Lines, 'unauthorized status must not expose even a Core row')

        service, debug, status, scope, logs = fixture()
        service.HCAdminRows(reply, False, 125)
        self.assertEqual([], reply.Lines)
        for index in range(70):
            service.HCRegisterOwner(NativeString('synthetic-' + str(index)))
        self.assertEqual(64, service.HCCount())
        self.assertEqual(6, service.HCRefused())
        self.assertEqual(1, debug.HCContributorCount())  # aggregate, not 53 callbacks
        self.assertIs(service.s_Owners[0], service.HCRegisterOwner(NativeString('synthetic-0')))
        self.assertIsNone(service.HCRegisterOwner(NativeString('x' * 65)))
        for index, state in enumerate(('off','requested','refused','ready','degraded')):
            reported = status()
            reported.HCPublish(state, 'synthetic_' + state)
            row = service.s_Owners[index]
            row.HCObserve(state != 'off', reported, 120)
            row.HCCounters(index, 32, 2, NativeString('no_work' if index == 0 else 'bounded'), 120)
            self.assertIn(' state=' + state + ' ', row.HCLine(125))
            self.assertIn('perf=unobserved qualification=PENDING runtime=PENDING', row.HCLine(125))
            # The authored HC-1 copy must resist later mutation.
            reported.HCPublish('off','synthetic_later')
            self.assertIn('source_state=' + state, row.HCLine(125))
        self.assertIn(' state=off ', service.s_Owners[0].HCLine(181),
                      'disabled owner has no tick publisher and must retain its observed off receipt')
        ready = service.s_Owners[3]
        self.assertIn('work=3 cap=32 refusals=2', ready.HCLine(125))
        self.assertIn('state=unknown source_state=ready freshness=stale', ready.HCLine(181))
        self.assertIn('work=unobserved', ready.HCLine(181))
        ready.HCObserve(True, status(), 181)
        self.assertIn('counters=stale', ready.HCLine(182))  # lifecycle cannot freshen old work
        self.assertIn('freshness=unobserved', ready.HCLine(100))  # clock rollback
        self.assertIn('state=unknown', service.s_Owners[63].HCLine(125))
        ready.HCStop(182)
        self.assertIn(' state=off ', ready.HCLine(183))
        self.assertIn('work=unobserved', ready.HCLine(183))

        authorized = N(Authorized=True, Lines=EArray())
        describe = compile_authored(WORLD / 'Admin/HCAdminStatus.c', 'HCServer',
                                    'HCAdminDescribe', scope)
        # No registry/module or world ports exist on this synthetic server.
        describe(N(), authorized)
        self.assertEqual(64, len(authorized.Lines))
        self.assertIn('rows=63 truncated=11', authorized.Lines[-1])
        self.assertIn('contributors=1', authorized.Lines[-1])
        service.HCReport()
        self.assertEqual(authorized.Lines[-1], logs[-1])
        self.assertIn('recovery=closed_or_quarantined', service.HCStoreLine('world'))
        self.assertIn('per_store_quarantine=unobserved', service.HCStoreLine('world'))
        self.assertIn('recovery=admitted generation=7', service.HCStoreLine('groups'))
        self.assertIn('paired_recovery=operator_attested', service.HCStoreLine('groups'))
        self.assertIn('quarantined_total=1', service.HCStoreLine('groups'))

        # Capture is detached text: later owner changes do not rewrite it.
        doc = N(operational=EArray(), operationalTruncated=0)
        capture = N(m_Describing=True, m_Document=doc, HCDocument=lambda:doc)
        add = compile_authored(DEBUG, 'HCDebugSnapshot', 'HCAddOperational', scope, ('HCText',), modded=False, fields=('m_Document',))
        capture.HCText = debug.HCText
        capture.HCAddOperational = lambda line:add(capture, NativeString(line))
        debug.HCText = scope['HCDebugSnapshot'].HCText
        service.s_Aggregate.HCDescribe(capture)
        self.assertEqual(64, len(doc.operational))
        self.assertEqual(10, doc.operationalTruncated)  # 4 overflow + 6 refused owners
        old = doc.operational[0]
        service.s_Owners[0].Name = 'mutated'
        self.assertEqual(old, doc.operational[0])
        clipped = debug.HCText('é' * 1000, 768)
        self.assertEqual(768, len(clipped.encode('utf-8')))
        capture.HCAddOperational('over-cap')
        self.assertEqual(11, doc.operationalTruncated)

        # Maximum authored capture envelope, synthetic native arrays only.
        wire_scope = dict(scope, str=NativeString, HCAdminReply=lambda:N(Lines=EArray(), Marks=EArray()),
                          HCAdminMark=lambda:N(), Vector=lambda x,y,z:(x,y,z),
                          HCAdminSnapshotWire=N(MAX_WIRE_LAYERS=24, NOTICE_BYTES=1024, NOTICE_UNPLACED_SHARE=4))
        wire = N()
        bind(wire, WORLD / 'Admin/HCAdminSnapshotWire.c', 'HCAdminSnapshotWire',
             ('HCMark','HCSlot','HCAllocate','HCFitted','HCFitEntries','HCBuild'), wire_scope,
             members=('HCMark','HCSlot','HCAllocate','HCFitted','HCFitEntries'), native_strings=NativeString)
        doc.layers = NativeMap({str(i):EArray([N(x=1,z=2,label='fixture',detail='fixture')
                                              for _ in range(32)]) for i in range(32)})
        doc.routes = EArray([N(layer='fixture', label='route',
                              points=EArray([EArray([1,2]) for _ in range(64)])) for _ in range(128)])
        doc.truncated = 2
        doc.layerStats = EArray()
        delivered = wire.HCBuild(capture, 19)
        self.assertEqual(19, delivered.Ticket)
        self.assertEqual(512, len(delivered.Marks))
        self.assertEqual(24, len({mark.Layer for mark in delivered.Marks}))  # MAX_WIRE_LAYERS
        self.assertEqual(64, len(delivered.Lines))
        self.assertIn('truncated=14', delivered.Lines[-1])  # 11 row + 2 registry + 1 wire
        self.assertIn('dropped=8704', delivered.Notice)
        self.assertTrue(all(len(line.encode('utf-8')) <= 768 for line in delivered.Lines))
        self.assertLessEqual(len(delivered.Notice), 1024)
        # Native RPC is a recorder here. Execute the actual final identity gate.
        sent = []
        allow = [False]
        rpc_scope = base_scope(ScriptRPC=lambda:N(Write=lambda reply:None,
                 Send=lambda *args:sent.append(args)), HCAdminWire=N(REPLY=7))
        sender = object()
        transport = N(HCAuthorized=lambda who:allow[0] and who is sender)
        send = compile_authored(WORLD / 'Admin/HCAdminModule.c', 'HCAdminModule',
                                'HCSend', rpc_scope, ('HCAuthorized',), modded=False)
        send(transport, sender, delivered)
        self.assertEqual([], sent)
        allow[0] = True
        send(transport, sender, delivered)
        self.assertEqual([(None,7,True,sender)], sent)
        allow[0] = False  # disconnect/revoked identity before delivery
        send(transport, sender, delivered)
        self.assertEqual(1, len(sent))

        # The named registry ceiling remains authoritative and refusal visible.
        cap = debug.HC_REGISTRY_CAP
        for _ in range(cap - 1): self.assertTrue(debug.HCRegister(object()))
        self.assertFalse(debug.HCRegister(object()))
        self.assertEqual(cap, debug.HCContributorCount())
        self.assertEqual(1, debug.s_RegistrationRefusals)
        service.HCReset()
        self.assertEqual(cap - 1, debug.HCContributorCount())
        self.assertEqual(0, service.HCCount())
        self.assertEqual(0, service.HCRefused())
        service.HCRegisterOwner(NativeString('restart'))
        self.assertEqual(cap, debug.HCContributorCount())
        service.HCReset()
        self.assertTrue(debug.HCRegister(object()))
        service.HCRegisterOwner(NativeString('full-registry'))
        self.assertFalse(service.s_Registered)
        bounded = N(Lines=EArray())
        service.HCAdminRows(bounded, True, 125)
        self.assertIn('state=refused reason=aggregate_contributor_not_registered', bounded.Lines[-1])
        for token in ('invitation=transient','native_inventory=native','unknown_store=unknown_refused'):
            self.assertTrue(any(token in line for line in bounded.Lines))

        # Optional addon reports only already cached HC admission, never Ready().
        xai = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXOperationalAdapters.c'
        fn = compile_authored(xai, 'HCXAIAdapter', 'HCGetOperationalStatus',
                              base_scope(HCOperationalStatus=status))
        for phase, armed, settled, expected in (
            ('wait',False,False,'requested'), ('off',False,True,'off'),
            ('refused',False,True,'refused'), ('run',True,True,'ready'),
            ('run',False,True,'degraded'), ('stopped',False,True,'off')):
            adapter = N(m_Sites=N(Phase=lambda:phase),
                        m_Encounters=N(Armed=lambda:armed, Settled=lambda:settled, State=lambda:'synthetic'))
            self.assertEqual(expected, fn(adapter).HCState())
        self.assertEqual('refused', fn(N(m_Sites=None, m_Encounters=None)).HCState())

        # Guard the request path against reintroducing a live owner rescan.
        _, body = authored_method(WORLD / 'Admin/HCAdminStatus.c', 'HCServer', 'HCAdminDescribe')
        self.assertNotIn('m_Registry', body)
        self.assertNotIn('HCAdminCounts', body)
        _, body = authored_method(WORLD / 'Debug/HCDebugContributors.c',
                                  'HCDebugOperationalContributor', 'HCDescribe', False)
        for forbidden in ('GetPlayers','GetPosition','Ready(','GetObjects','IsEnabled'):
            self.assertNotIn(forbidden, body)


if __name__ == '__main__':
    unittest.main()


class DebugRegistryCapacity(unittest.TestCase):
    """w28 #193 review P1: the built-ins plus every module/addon registrant fit the cap."""

    MODS = ROOT / 'mods'
    SNAPSHOT = MODS / 'HollowCountry/scripts/4_World/Debug/HCDebugSnapshot.c'
    MODULE = MODS / 'HollowCountry/scripts/4_World/Debug/HCDebugSnapshotModule.c'

    def cap(self):
        text = self.SNAPSHOT.read_text(encoding='utf-8')
        match = re.search(r'static const int HC_REGISTRY_CAP = (\d+);', text)
        self.assertIsNotNone(match, 'registry cap must be a named constant')
        self.assertIn('s_Contributors.Count() >= HCDebugSnapshot.HC_REGISTRY_CAP', text)
        return int(match.group(1))

    def test_lead_ledger_and_scenes_layers_are_registered_builtins(self):
        text = self.MODULE.read_text(encoding='utf-8')
        for name in ('HCDebugLeadLedgerContributor', 'HCDebugScenesContributor', 'HCDebugPickersContributor',
                     'HCDebugGroupPinsContributor', 'HCDebugProposalsContributor'):
            self.assertIn('HCKeep(new %s);' % name, text)

    def test_every_static_registrant_fits_under_the_cap(self):
        builtins = len(re.findall(r'^\s*HCKeep\(', self.MODULE.read_text(encoding='utf-8'), re.M))
        others = 0
        for path in self.MODS.rglob('*.c'):
            if path == self.MODULE:
                continue
            text = path.read_text(encoding='utf-8', errors='replace')
            others += len(re.findall(r'HCDebugSnapshot\.HCRegister\(', text))
        live = (self.MODS / 'HollowCountryExpansionAI/scripts/4_World/HCXAILiveMap.c').read_text(encoding='utf-8')
        # HCXAILiveMap registers its two pages through one loop call site.
        self.assertIn('HCDebugSnapshot.HCRegister(contributor);', live)
        total = builtins + others + 1
        self.assertGreaterEqual(builtins, 12)
        self.assertGreaterEqual(self.cap(), 24)
        self.assertLessEqual(total, self.cap(), 'registrants %d exceed the debug registry cap' % total)
