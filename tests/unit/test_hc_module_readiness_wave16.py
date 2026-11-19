"""Wave 16 (w32-status): honest per-module readiness and late readiness lines.

Executes the AUTHORED Core/HCModuleReadiness.c, Core/HCOperationalChanges.c, the authored
HCServer Start/Tick refresh and each module's authored HCGetOperationalStatus through the repo's
syntax-only translators over explicit SYNTHETIC flags. Offline policy evidence only: nothing here
observes DayZ; runtime=PENDING.
"""
from pathlib import Path
import re
import unittest
from types import SimpleNamespace as N

from tests.unit import test_core_lifecycle as core
from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
S = ROOT / 'mods/HollowCountry/scripts/4_World'
X = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World'
READINESS = S / 'Core/HCModuleReadiness.c'
CHANGES = S / 'Core/HCOperationalChanges.c'


def renamed(text):
    # The translator knows the HCEvent prefix as a return type; HCOperationalStatus is the same shape.
    return text.replace('HCOperationalStatus', 'HCEventOperationalStatus')


class FakeStatus:
    """Records the last HCPublish like the authored cached status does."""

    def __init__(self):
        self.state, self.reason, self.publishes = 'unknown', 'owner_state_unknown', 0

    def HCPublish(self, state, reason):
        self.state, self.reason = state, reason
        self.publishes += 1

    def HCState(self): return self.state
    def HCReason(self): return self.reason


READINESS_ENV = {'HCModuleReadiness': N(HC_OFF_REASON='not_started_or_disabled')}


def derive():
    return translate(READINESS.read_text(), 'HCDerive', dict(READINESS_ENV), None, False)


class HelperTests(unittest.TestCase):
    def test_derive_maps_started_refusal_degraded_and_off(self):
        fn = derive()
        cases = [
            ((True, '', '', 'files_loaded'), ('ready', 'files_loaded')),
            ((True, '', 'native_fault', 'files_loaded'), ('degraded', 'native_fault')),
            ((True, 'ignored_when_started', '', 'files_loaded'), ('ready', 'files_loaded')),
            ((False, 'store_refused', '', 'files_loaded'), ('refused', 'store_refused')),
            ((False, '', '', 'files_loaded'), ('off', 'not_started_or_disabled')),
        ]
        for args, expected in cases:
            with self.subTest(args=args):
                status = FakeStatus()
                fn(status, *args)
                self.assertEqual(expected, (status.state, status.reason))

    def test_derive_ignores_a_missing_status_object(self):
        derive()(None, True, '', '', 'ready')


def make_changes(env=None):
    text = CHANGES.read_text()
    cls = type('AuthoredChanges', (), {})
    for name in sorted(set(re.findall(r'\b(?:void|bool|int|string) (HC\w+)\(', text))):
        local = dict(env or {}, EArray=EArray, len=len, str=str,
                     HCOperationalChanges=N(HC_CAP=64))
        setattr(cls, name, translate(text, name, local, 'changes', True))
    obj = cls()
    obj.m_States = EArray()
    obj.m_Reasons = EArray()
    return obj


class ChangeTests(unittest.TestCase):
    def status(self, state, reason):
        row = FakeStatus()
        row.HCPublish(state, reason)
        return row

    def test_late_ready_prints_once_and_unchanged_polls_are_silent(self):
        changes = make_changes()
        changes.HCBaseline(self.status('degraded', 'template_pack_loading'))
        changes.HCBaseline(self.status('ready', 'ok'))
        self.assertEqual('', changes.HCChange(0, 'Interiors', self.status('degraded', 'template_pack_loading')))
        self.assertEqual('', changes.HCChange(1, 'Other', self.status('ready', 'ok')))
        self.assertEqual('[HC Interiors] ready (late)',
                         changes.HCChange(0, 'Interiors', self.status('ready', 'templates_loaded')))
        self.assertEqual('', changes.HCChange(0, 'Interiors', self.status('ready', 'templates_loaded')))
        # A reason-only change while ready is not a state change.
        self.assertEqual('', changes.HCChange(0, 'Interiors', self.status('ready', 'other_ready_reason')))

    def test_state_or_reason_change_away_from_ready_prints_the_state_and_reason(self):
        changes = make_changes()
        changes.HCBaseline(self.status('ready', 'ok'))
        self.assertEqual('[HC Groups] degraded reason=store_fault',
                         changes.HCChange(0, 'Groups', self.status('degraded', 'store_fault')))
        self.assertEqual('', changes.HCChange(0, 'Groups', self.status('degraded', 'store_fault')))
        self.assertEqual('[HC Groups] degraded reason=clock_fault',
                         changes.HCChange(0, 'Groups', self.status('degraded', 'clock_fault')))
        self.assertEqual('[HC Groups] refused reason=gone',
                         changes.HCChange(0, 'Groups', self.status('refused', 'gone')))
        self.assertEqual('[HC Groups] ready (late)', changes.HCChange(0, 'Groups', self.status('ready', 'ok')))

    def test_missing_status_unknown_index_reset_and_cap(self):
        changes = make_changes()
        changes.HCBaseline(None)
        self.assertEqual('', changes.HCChange(0, 'Legacy', None))
        self.assertEqual('', changes.HCChange(5, 'Beyond', self.status('ready', 'x')))
        self.assertEqual('', changes.HCChange(-1, 'Negative', self.status('ready', 'x')))
        for _ in range(80):
            changes.HCBaseline(self.status('ready', 'x'))
        self.assertEqual(64, len(changes.m_States))
        changes.HCReset()
        self.assertEqual(0, len(changes.m_States))
        self.assertEqual(0, len(changes.m_Reasons))


def server_fixture(modules, changes):
    logs = []
    owner = N(HCObserve=lambda requested, reported, now: None, HCStop=lambda now: None)
    operational = N(HCReset=lambda: None, HCRegisterOwner=lambda name: owner, HCReport=lambda: None)
    clock = [12]
    state, _ = core.fixture(modules=modules, operational=operational,
                            ports={'Print': logs.append})
    state.m_Changes = changes
    state.m_OperationalRefreshAt = 0
    ctx = dict(GetGame=lambda: N(IsServer=lambda: True, GetTickTime=lambda: clock[0],
                                 GetCallQueue=lambda c: N(Remove=lambda fn: None, CallLater=lambda *a: None)),
               TickCount=lambda prior: 0, Print=logs.append, HCOperationalContributors=operational)
    state.Tick = lambda: core.actual_method('Tick', ctx)(state)
    return state, logs, clock


class ServerRefreshTests(unittest.TestCase):
    def module(self, name, status):
        return N(GetName=lambda: name, IsEnabled=lambda settings: True, OnStart=lambda settings: None,
                 OnStop=lambda: None, OnTick=lambda elapsed: None, HCGetOperationalStatus=lambda: status)

    def test_refresh_prints_one_late_ready_line_when_a_module_changes_after_boot(self):
        late = FakeStatus()
        late.HCPublish('degraded', 'template_pack_loading')
        steady = FakeStatus()
        steady.HCPublish('ready', 'ok')
        modules = [self.module('Interiors', late), self.module('Steady', steady)]
        state, logs, clock = server_fixture(modules, make_changes())
        state.Start()
        boot = [line for line in logs if line.startswith('[HC Interiors]') or line.startswith('[HC Steady]')]
        self.assertEqual(['[HC Interiors] degraded reason=template_pack_loading', '[HC Steady] ready'], boot)
        clock[0] = 20  # before the 15 s refresh
        state.Tick()
        clock[0] = 30
        state.Tick()
        self.assertEqual([], [line for line in logs if '(late)' in line])
        late.HCPublish('ready', 'templates_loaded')
        clock[0] = 50
        state.Tick()
        clock[0] = 70
        state.Tick()
        clock[0] = 90
        state.Tick()
        self.assertEqual(['[HC Interiors] ready (late)'], [line for line in logs if '(late)' in line])
        late.HCPublish('degraded', 'store_fault')
        clock[0] = 110
        state.Tick()
        self.assertIn('[HC Interiors] degraded reason=store_fault', logs)

    def test_stop_and_restart_reset_the_change_baseline(self):
        status = FakeStatus()
        status.HCPublish('ready', 'ok')
        changes = make_changes()
        state, logs, clock = server_fixture([self.module('A', status)], changes)
        state.Start()
        self.assertEqual(1, len(changes.m_States))
        state.Stop()
        self.assertEqual(0, len(changes.m_States))
        state.Start()
        self.assertEqual(1, len(changes.m_States))

    def test_disabled_modules_get_no_baseline_so_indexes_follow_the_active_array(self):
        off = FakeStatus()
        off.HCPublish('off', 'not_started_or_disabled')
        live = FakeStatus()
        live.HCPublish('degraded', 'warming')
        disabled = self.module('Disabled', off)
        disabled.IsEnabled = lambda settings: False
        state, logs, clock = server_fixture([disabled, self.module('Live', live)], make_changes())
        state.Start()
        live.HCPublish('ready', 'warm')
        clock[0] = 40
        state.Tick()
        self.assertEqual(['[HC Live] ready (late)'], [line for line in logs if '(late)' in line])


# (file, class, module name, module-owned started flag that OnStart raises / OnStop drops (or None),
#  [(expected state, expected reason or None, instance attrs, s_Instance is this, env overrides)])
# All values are explicit SYNTHETIC flags; they prove the authored getter's mapping only.
OFF = 'not_started_or_disabled'
GATE_OPEN = {'HCRecoveryGate': N(HCReady=lambda name: True)}
GATE_SHUT = {'HCRecoveryGate': N(HCReady=lambda name: False)}
MODULES = [
    (X / 'HCXDefence.c', 'HCXDefenceModule', 'AISelfDefence', None, [
        ('ready', None, {}, False, {'HCXDefence': N(Running=lambda: True)}),
        ('off', OFF, {}, False, {'HCXDefence': N(Running=lambda: False)})]),
    (S / 'Crafting/HCCraftingModule.c', 'HCCraftingModule', 'Crafting', None, [
        ('ready', None, {'m_Refusal': ''}, False, {'HCCraftingGate_started': True}),
        ('refused', 'native_definition_checks_failed', {'m_Refusal': 'native_definition_checks_failed'}, False,
         {'HCCraftingGate_started': False}),
        ('off', OFF, {'m_Refusal': ''}, False, {'HCCraftingGate_started': False})]),
    (S / 'World/HCDeadDrops.c', 'HCDeadDrops', 'DeadDrops', None, [
        ('ready', None, {'m_Ready': True, 'm_Refusal': ''}, False, {}),
        ('refused', 'dead_drop_state_invalid_or_save_failed',
         {'m_Ready': False, 'm_Refusal': 'dead_drop_state_invalid_or_save_failed'}, False, {}),
        ('off', OFF, {'m_Ready': False, 'm_Refusal': ''}, False, {})]),
    (S / 'Debug/HCDebugSnapshotModule.c', 'HCDebugSnapshotModule', 'DebugSnapshot', None, [
        ('ready', None, {'m_Running': True, 'm_Refusal': ''}, False, {}),
        ('refused', 'world_date_or_store_fault', {'m_Running': False, 'm_Refusal': 'world_date_or_store_fault'}, False, {}),
        ('off', OFF, {'m_Running': False, 'm_Refusal': ''}, False, {})]),
    (S / 'Atmosphere/HCGradeModule.c', 'HCGradeModule', 'Grade', 'm_Started', [
        ('ready', None, {'m_Started': True}, False, {}), ('off', OFF, {'m_Started': False}, False, {})]),
    (S / 'Groups/HCGroupModule.c', 'HCGroupModule', 'Groups', None, [
        ('ready', None, {'m_Service': object(), 'm_Refusal': ''}, False, GATE_OPEN),
        ('degraded', 'recovery_gate_closed', {'m_Service': object(), 'm_Refusal': ''}, False, GATE_SHUT),
        ('refused', 'recovery_gate_refused_groups_store', {'m_Service': None, 'm_Refusal': 'recovery_gate_refused_groups_store'},
         False, GATE_SHUT),
        ('off', OFF, {'m_Service': None, 'm_Refusal': ''}, False, GATE_SHUT)]),
    (S / 'Infected/Doors/HCInfectedDoors.c', 'HCInfectedDoorsModule', 'InfectedDoors', None, [
        ('ready', None, {'m_Running': True}, False, {}), ('off', OFF, {'m_Running': False}, False, {})]),
    (S / 'Infected/LOD/HCInfectedLOD.c', 'HCInfectedLODModule', 'InfectedLOD', None, [
        ('ready', None, {'m_Running': True, 'm_Herds': True, 'm_Refusal': '', 'm_Store': N(Healthy=lambda: True)}, False, {}),
        ('degraded', 'herd_store_unhealthy',
         {'m_Running': True, 'm_Herds': True, 'm_Refusal': '', 'm_Store': N(Healthy=lambda: False)}, False, {}),
        ('refused', 'lod_config_unavailable',
         {'m_Running': False, 'm_Herds': False, 'm_Refusal': 'lod_config_unavailable', 'm_Store': None}, False, {}),
        ('off', OFF, {'m_Running': False, 'm_Herds': False, 'm_Refusal': '', 'm_Store': None}, False, {})]),
    (S / 'Infected/HCInfectedMemory.c', 'HCInfectedMemoryModule', 'InfectedMemory', None, [
        ('ready', None, {'m_Memory': object()}, False, {'HCInfectedMemory': N(Active=lambda: True)}),
        ('degraded', 'memory_state_unhealthy', {'m_Memory': object()}, False, {'HCInfectedMemory': N(Active=lambda: False)}),
        ('off', OFF, {'m_Memory': None}, False, {'HCInfectedMemory': N(Active=lambda: False)})]),
    (S / 'Infected/Reach/HCInfectedReachModule.c', 'HCInfectedReachModule', 'InfectedReach', None, [
        ('ready', None, {'m_Running': True}, False, {}), ('off', OFF, {'m_Running': False}, False, {})]),
    (S / 'Atmosphere/HCLightingModule.c', 'HCLightingModule', 'Lighting', 'm_Started', [
        ('ready', None, {'m_Started': True}, False, {}), ('off', OFF, {'m_Started': False}, False, {})]),
    (S / 'Loot/HCSearchRefresh.c', 'HCSearchRefreshModule', 'LootRefresh', None, [
        ('ready', None, {'m_Refusal': '', 'm_Store': N(Healthy=lambda: True)}, True, {}),
        ('degraded', 'refresh_store_fault', {'m_Refusal': '', 'm_Store': N(Healthy=lambda: False)}, True, {}),
        ('refused', 'refresh_state_invalid', {'m_Refusal': 'refresh_state_invalid', 'm_Store': None}, False, {}),
        ('off', OFF, {'m_Refusal': '', 'm_Store': None}, False, {})]),
    (S / 'Groups/HCGroupPins.c', 'HCGroupPins', 'MapPins', None, [
        ('ready', None, {}, True, {}), ('off', OFF, {}, False, {})]),
    (X / 'HCXMaterializerBridge.c', 'HCXMaterializerBridge', 'MaterializerBridge', None, [
        ('ready', None, {'m_Running': True}, False, {}), ('off', OFF, {'m_Running': False}, False, {})]),
    (S / 'World/HCWorldMaterializer.c', 'HCWorldMaterializer', 'Materializer', None, [
        ('ready', None, {'m_Running': True, 'm_CustodyReady': True}, False, {}),
        ('degraded', 'custody_unreadable_ai_budget_blocked', {'m_Running': True, 'm_CustodyReady': False}, False, {}),
        ('off', OFF, {'m_Running': False, 'm_CustodyReady': False}, False, {})]),
    (S / 'Atmosphere/HCOptionalPacksModule.c', 'HCOptionalPacksModule', 'OptionalPacks', 'm_Started', [
        ('ready', None, {'m_Started': True}, False, {}), ('off', OFF, {'m_Started': False}, False, {})]),
    (S / 'Polish/HCPolishModule.c', 'HCPolishModule', 'Polish', 'm_Started', [
        ('ready', None, {'m_Started': True}, False, {}), ('off', OFF, {'m_Started': False}, False, {})]),
    (S / 'Scenes/HCScenesModule.c', 'HCScenesModule', 'Scenes', None, [
        ('ready', None, {'m_Running': True, 'm_Refusal': ''}, False, {}),
        ('refused', 'store_unavailable', {'m_Running': False, 'm_Refusal': 'store_unavailable'}, False, {}),
        ('off', OFF, {'m_Running': False, 'm_Refusal': ''}, False, {})]),
    (S / 'Loot/HCSearchBinding.c', 'HCSearchBinding', 'SearchBinding', None, [
        ('ready', None, {'m_Started': True, 'm_Stopped': False, 'm_Refusal': '', 'm_Fault': ''}, False, {}),
        ('degraded', 'measured_binding_refused',
         {'m_Started': True, 'm_Stopped': False, 'm_Refusal': '', 'm_Fault': 'measured_binding_refused'}, False, {}),
        ('refused', 'search_admission_marker_absent',
         {'m_Started': False, 'm_Stopped': False, 'm_Refusal': 'search_admission_marker_absent', 'm_Fault': ''}, False, {}),
        ('off', OFF, {'m_Started': True, 'm_Stopped': True, 'm_Refusal': '', 'm_Fault': ''}, False, {})]),
    (S / 'World/HCSettlementDecay.c', 'HCSettlementDecay', 'SettlementDecay', 'm_Started', [
        ('ready', None, {'m_Started': True, 'm_Fault': False}, False, {}),
        ('degraded', 'persistence_clock_or_schema_fault', {'m_Started': True, 'm_Fault': True}, False, {}),
        ('off', OFF, {'m_Started': False, 'm_Fault': False}, False, {})]),
    (S / 'Travel/HCShelterModule.c', 'HCShelterModule', 'Shelters', None, [
        ('ready', None, {'m_Started': True, 'm_Placed': 3}, False, {}),
        ('degraded', 'no_shelter_placed', {'m_Started': True, 'm_Placed': 0}, False, {}),
        ('off', OFF, {'m_Started': False, 'm_Placed': 0}, False, {})]),
    (S / 'Atmosphere/HCSignsOfLife.c', 'HCSignsOfLife', 'SignsOfLife', 'm_Started', [
        ('ready', None, {'m_Started': True}, False, {}), ('off', OFF, {'m_Started': False}, False, {})]),
    (S / 'Survival/HCMealBuffs.c', 'HCSurvivalAlignmentModule', 'SurvivalAlignment', 'm_Started', [
        ('ready', None, {'m_Started': True}, False, {}), ('off', OFF, {'m_Started': False}, False, {})]),
    (S / 'Vehicles/HCVehicleFlip.c', 'HCVehicleFlipModule', 'VehicleFlip', None, [
        ('ready', None, {}, True, {}), ('off', OFF, {}, False, {})]),
    (S / 'World/HCWorkBudget.c', 'HCSaveScheduler', 'WorldSaves', 'm_Started', [
        ('ready', None, {'m_Started': True, 'm_Fault': ''}, False, {}),
        ('degraded', 'save_job_write_faulted', {'m_Started': True, 'm_Fault': 'save_job_write_faulted'}, False, {}),
        ('off', OFF, {'m_Started': False, 'm_Fault': ''}, False, {})]),
    (S / 'World/HCWorldModule.c', 'HCWorldModule', 'World', None, [
        ('ready', None, {'m_Running': True, 'm_Refusal': ''}, False, GATE_OPEN),
        ('degraded', 'recovery_gate_closed', {'m_Running': True, 'm_Refusal': ''}, False, GATE_SHUT),
        ('refused', 'utc_clock_unsupported', {'m_Running': False, 'm_Refusal': 'utc_clock_unsupported'}, False, GATE_SHUT),
        ('off', OFF, {'m_Running': False, 'm_Refusal': ''}, False, GATE_SHUT)]),
    (X / 'HCXAILiveMap.c', 'HCXAILiveModule', 'hcxai-live-map', None, [
        ('ready', None, {'m_Live': object()}, False, {}), ('off', OFF, {'m_Live': None}, False, {})]),
    (X / 'HCXStance.c', 'HCXLivingModule', 'v2-expansion-living-world', 'm_Started', [
        ('ready', None, {'m_Started': True, 'm_Refusal': ''}, False, {}),
        ('degraded', 'actor finite-ammo/fairness/looting NONE assertion',
         {'m_Started': True, 'm_Refusal': 'actor finite-ammo/fairness/looting NONE assertion'}, False, {}),
        ('off', OFF, {'m_Started': False, 'm_Refusal': ''}, False, {})]),
]


def class_text(text, cls):
    match = re.search(r'^(?:modded )?class ' + cls + r'\b[^\n]*\n', text, re.M)
    if not match:
        raise AssertionError('missing class ' + cls)
    following = re.search(r'^(?:modded )?class \w+', text[match.end():], re.M)
    end = match.end() + following.start() if following else len(text)
    return text[match.start():end]


class ModuleStatusTests(unittest.TestCase):
    def test_every_listed_module_derives_its_status_from_live_state(self):
        helper = N(HCDerive=derive())
        for path, cls, name, flag, cases in MODULES:
            body = class_text(path.read_text(), cls)
            with self.subTest(module=name):
                self.assertRegex(body, r'override string GetName\(\)\s*\{?\s*return "' + re.escape(name) + '";',
                                 'module name mapping differs from the brief')
                self.assertIn('override HCOperationalStatus HCGetOperationalStatus()', body)
                self.assertIn('protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;', body)
                self.assertIn('HCModuleReadiness.HCDerive(m_Operational', body)
                # The offline translator prefixes every m_ token with self., so a static
                # HCCraftingGate.m_Started read is renamed to a plain env name first.
                text = renamed(body).replace('HCCraftingGate.m_Started', 'HCCraftingGate_started')
                fn = translate(text, 'HCGetOperationalStatus', {}, None, True)
                for state, reason, attrs, is_this, env in cases:
                    with self.subTest(module=name, state=state, reason=reason):
                        status = FakeStatus()
                        owner = N(m_Operational=status, **attrs)
                        fn.__globals__.update(env)
                        fn.__globals__['HCModuleReadiness'] = helper
                        fn.__globals__['s_Instance'] = owner if is_this else None
                        result = fn(owner)
                        self.assertIs(status, result)
                        self.assertEqual(state, status.state)
                        if reason is not None:
                            self.assertEqual(reason, status.reason)
                        self.assertNotEqual('', status.reason)
                if flag:
                    # A module-owned started flag is raised once in OnStart and dropped in OnStop.
                    self.assertRegex(body, r'm_Started\s*=\s*true;')
                    self.assertRegex(body, r'm_Started\s*=\s*false;')

    def test_the_brief_lists_29_names_and_reach_is_a_log_label_not_a_module(self):
        # 29 names in the task; "Reach" is only the print prefix of InfectedReach, not a registered module.
        self.assertEqual(29 - 1, len(MODULES))
        self.assertEqual(len(MODULES), len({row[2] for row in MODULES}))
        reach = (S / 'Infected/Reach/HCInfectedReachModule.c').read_text()
        self.assertEqual(1, len(re.findall(r'override string GetName\(\)', reach)))
        self.assertIn('"[HC Reach] started', reach)

    def test_no_listed_module_hard_codes_ready(self):
        for path, cls, name, flag, cases in MODULES:
            body = class_text(path.read_text(), cls)
            getter = body[body.index('override HCOperationalStatus HCGetOperationalStatus()'):]
            getter = getter[:getter.index('return m_Operational;')]
            with self.subTest(module=name):
                self.assertNotIn('HCPublish("ready"', getter)
                self.assertIn('HCModuleReadiness.HCDerive(', getter)


if __name__ == '__main__':
    unittest.main()
