"""#23/W1.9: authored core and admission decisions; synthetic engine ports.

Trace: RUNTIME_IMPLEMENTATION_CONTRACT HCSettings/lifecycle/budgets; #23 v1.
All feature combinations are operator preferences, not native qualification.
Events/ecology have separate enabled synthetic configs; atmosphere is an owner,
not a registry slot. No engine, two-client, late-join or timing proof is claimed.

Trace: T023 / AC-011, FR-012, NFR-003/004; current #23 scope supersedes
the older plan's two-client and late-join acceptance cases for this writer.
TDD record (2026-11-17): unmarked combined workload failed 36 <= 32;
unmarked Stop regression failed with two pathgraph callbacks still queued.
Both remain expected failures; no product implementation is changed.
Green: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_v1_combined_flags
"""
import itertools
import json
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit import test_core_lifecycle as core
from tests.unit import test_event_runtime as event
from tests.unit import test_event_integration as event_integration
from tests.unit import test_search_economy_integration as search
from tests.unit import test_v1_weather as weather
from tests.unit import test_infected_admission as infected
from tests.unit import test_ecology_module as ecology
from tests.unit.test_group_server import EArray
from tools.validate.runtime import V2_FLAGS

ROOT = event.ROOT
SETTINGS = ROOT / '3_Game/HCSettings.c'
DEFAULTS = json.loads((ROOT.parents[2] / 'config/hollow-country-settings.json').read_text())
# V2 preferences (LC-T001) gate no module yet; the 256-combination product stays
# over the v1 module flags, while reload preservation covers every flag.
ALL_FLAGS = tuple(k for k in DEFAULTS if k.startswith('Enable'))
FLAGS = tuple(k for k in ALL_FLAGS if k not in V2_FLAGS)
MODULE_PATHS = {
    'Groups': 'Groups/HCGroupModule.c', 'Events': 'Events/HCEventModule.c',
    'Interiors': 'Interiors/HCInteriorModule.c', 'Infected': 'Infected/HCInfectedModule.c',
    'Crafting': 'Crafting/HCCraftingModule.c', 'Ecology': 'Ecology/HCEcologyRuntimeModule.c',
    # Registered by HCInteriorModule.c before Interiors (da17531); real IsEnabled executes.
    'SearchBinding': 'Loot/HCSearchBinding.c',
}


class Profile:
    """Explicit synthetic JSON/out-parameter seam; actual profile policy executes."""
    def __init__(self, values):
        self.text = json.dumps(values)
        self.logs = []
        self.writes = []
        self.source = SETTINGS.read_text().replace('HCSettings', 'HCEventSettings')
        self.source = re.sub(r'else if \(([^\n]*)\)', r'elif (\1):', self.source)
        self.source = self.source.replace('LoadBounded(path, settings, error)',
            '((settings := load_settings(path)) != null)')
        self.source = self.source.replace('JsonFileLoader<HCEventSettings>.SaveFile(path, settings, error)',
                                          'save_settings(path, settings)')
        self.env = dict(Print=self.logs.append, FileExist=lambda p: True,
                        MakeDirectory=lambda p: True, load_settings=self.decode,
                        save_settings=lambda *a: self.writes.append(a) or True)
        from tests.unit.ai_limits_fixture import install
        install(self.env)
        self.env['HCAILimits'].Use = lambda limits: None
        self.env['HCEventSettings'] = self.make
        self.load = event.translate(self.source, 'LoadFromProfile', self.env, 'HCEventSettings')

    def make(self):
        value = N(**DEFAULTS)
        self.ai(value, DEFAULTS["AILimits"])
        source = self.source
        for field in DEFAULTS:
            source = re.sub(r'\b' + field + r'\b', 'self.' + field, source)
        value.Validate = lambda error: event.translate(source, 'Validate', self.env,
                                                       'HCEventSettings', True)(value, error)
        return value

    def ai(self, value, fields):
        from tests.unit.test_ai_limits import authored
        limits, api, env, logs = authored()
        vars(limits).update(fields)
        limits.Validate = lambda: env["Validate"](limits)
        value.AILimits = limits

    def decode(self, path):
        fields = json.loads(self.text)
        value = self.make()
        vars(value).update(fields)
        self.ai(value, fields.get("AILimits", DEFAULTS["AILimits"]))
        return value


class Module:
    """Actual IsEnabled; start/tick/stop are explicit synthetic collaborator ports."""
    def __init__(self, name, fixture):
        self.name, self.f = name, fixture
        self.m_Config = None
        self.m_Settings = None
        self.live = False
        source = (ROOT / '4_World' / MODULE_PATHS[name]).read_text()
        source = source.replace('HCSettings', 'HCEventSettings')
        source = source.replace('HCEcology', 'HCEventEcology')
        source = source.replace('HCGroupSettings', 'HCEventGroupSettings')
        self.gate = event.translate(source, 'IsEnabled', fixture.env, None, True)

    def GetName(self): return self.name
    def IsEnabled(self, settings): return self.gate(self, settings)
    def HCGetOperationalStatus(self): return None
    def OnStart(self, settings):
        self.live = True
        self.f.starts.append(self.name)
    def OnTick(self, elapsed): self.f.work.append(self.name)
    def OnStop(self):
        self.live = False
        self.f.stops.append(self.name)


class CoreFixture:
    def __init__(self, values=DEFAULTS):
        self.profile = Profile(values)
        self.starts, self.stops, self.work, self.queued = [], [], [], []
        self.now = 100.
        self.game = N(IsServer=lambda: True, GetTickTime=lambda: self.now)
        self.game.GetCallQueue = lambda category: N(CallLater=self.schedule, Remove=self.remove)
        self.env = dict(GetGame=lambda: self.game, Print=self.profile.logs.append,
                        HCEventConfiguration=lambda: N(Load=lambda: N(Enabled=True)),
                        HCGroupStore=N(LoadSettings=lambda: N(Enabled=True)),
                        HCEventEcologyRuntimeIO=N(Settings=lambda: N(Enabled=True)),
                        HCEventEcologyRuntime=N(CloseCollection=lambda: None),
                        # SYNTHETIC: log-only once-per-process disposition report (da17531).
                        HCEventEcologyDisposition=N(Report=lambda: None))
        self.modules = {name: Module(name, self) for name in MODULE_PATHS}
        # Execute core registration and each authored modded extension in a
        # synthetic deterministic load order; native linker ordering is unproved.
        self.registry = N(m_Modules=EArray())
        env = dict(self.env, EArray=EArray)
        for name, path in MODULE_PATHS.items():
            text = (ROOT / '4_World' / path).read_text()
            cls = re.search(r'class (\w+) (?:extends|:) HCModule', text)[1]
            env[cls] = lambda name=name: self.modules[name]
        source = (ROOT / '4_World/Core/HCModule.c').read_text().replace('HCModule', 'HCEventBase')
        # Only local/parameter HCModule types need renaming; constructor names
        # in RegisterModules remain the product's class names.
        for method in ('Register', 'RegisterModules', 'GetModules'):
            fn = event.translate(source, method, env, 'HCEventBaseRegistry', True)
            setattr(self.registry, method, lambda *a, fn=fn: fn(self.registry, *a))
        base = self.registry.RegisterModules
        for path in MODULE_PATHS.values():
            text = (ROOT / '4_World' / path).read_text()
            if 'modded class HCModuleRegistry' not in text: continue
            text = text[text.index('modded class HCModuleRegistry'):]
            text = text.replace('super.RegisterModules()', 'prior_register()')
            text = re.sub(r'(?<![\w.])Register\(', 'self.Register(', text)
            fn = event.translate(text, 'RegisterModules', dict(env, prior_register=base),
                                 'HCModuleRegistry', True)
            base = lambda fn=fn: fn(self.registry)
        self.registry.RegisterModules = base
        self.state = N(m_Started=False, m_Active=core.NativeArray(), m_Settings=None,
                       m_LastTick=0, m_Registry=None,
                       m_Operational=N(HCReset=lambda: None, HCStopAll=lambda: None,
                                       HCCapture=lambda name, requested, reported: None),
                       m_Perf=N(Start=lambda seconds: None, Stop=lambda: None,
                                Sample=lambda elapsed, ticks: None,
                                RegisterModule=lambda name: None, SampleModule=lambda index,ticks: None))
        context = dict(GetGame=lambda: self.game, Print=self.profile.logs.append,
                       HCNativeSelfTests=N(Run=lambda: True),
                       HCSettings=N(LoadFromProfile=self.profile.load),
                       HCModuleRegistry=lambda: self.registry, CALL_CATEGORY_SYSTEM=0,
                       TickCount=lambda prior:0,
                       HCV2Admission=N(Summary=lambda settings: '[HollowCountry] V2 preferences',
                                       OperationalSummary=lambda status: '[HC Plan] HC-1 status',
                                       NonModuleSummary=lambda: '[HC Plan] HC-1 non_modules'))
        for name in ('Start', 'Tick', 'Stop'):
            if name == 'Tick':
                source = core.SOURCE.read_text().replace(
                    'foreach (HCModule module : m_Active) module.OnTick(elapsed);',
                    'foreach (HCModule module : m_Active) { module.OnTick(elapsed); }')
                source = source.replace('HCModule', 'HCEventBase')
                source = re.sub(r'(\b[\w.]+)\+\+;',r'\1 += 1;',source)
                fn = event.translate(source, name, dict(context), 'HCServer', True)
            else:
                fn = core.actual_method(name, context)
            setattr(self.state, name, lambda fn=fn: fn(self.state))

    def schedule(self, fn, *args): self.queued.append((fn, args))
    def remove(self, fn): self.queued[:] = [entry for entry in self.queued if entry[0] != fn]


class CombinedFlagsTests(unittest.TestCase):
    def test_all_256_combinations_reject_dependencies_or_start_exact_registry(self):
        self.assertEqual(8, len(FLAGS))  # a new flag must not silently multiply the product
        for bits in itertools.product((False, True), repeat=len(FLAGS)):
            values = dict(DEFAULTS, **dict(zip(FLAGS, bits)))
            valid = (not values['EnableSearch'] or values['EnableInteriors']) and (
                values['EnableInfected'] or not (values['EnableHordes'] or values['EnableAlertChains']))
            with self.subTest(flags=dict(zip(FLAGS, bits))):
                f = CoreFixture(values)
                f.state.Start()
                expected = {'Events', 'Ecology'} if valid else set()
                if valid:
                    expected.update(name for name in ('Interiors', 'Infected', 'Crafting', 'Groups')
                                    if values['Enable' + name])
                    if values['EnableInteriors'] and values['EnableSearch']:
                        expected.add('SearchBinding')
                self.assertEqual(expected, set(f.starts))
                self.assertEqual(len(expected), len(f.starts))
                self.assertEqual(valid, f.state.m_Started)
                self.assertEqual(int(valid), len(f.queued))
                self.assertEqual([], f.profile.writes)

    def test_start_stop_start_has_one_module_instance_and_one_tick_callback(self):
        f = CoreFixture()
        for cycle in range(3):
            f.state.Start(); f.state.Start()
            self.assertEqual(set(MODULE_PATHS), {m.GetName() for m in f.state.m_Active})
            self.assertEqual(7, len(f.state.m_Active))
            self.assertEqual(1, len(f.queued))
            f.state.Stop(); f.state.Stop()
            self.assertEqual([], f.queued)
            self.assertTrue(all(not m.live for m in f.modules.values()))
        self.assertEqual(21, len(f.starts))
        self.assertEqual(21, len(f.stops))

    def test_atmosphere_owner_obeys_preference_after_core_start(self):
        for enabled in (False, True):
            f = CoreFixture(dict(DEFAULTS, EnableAtmosphere=enabled))
            f.state.Start()
            gate = N(s_Reported=False, SupportedWorld=lambda: True, Qualified=lambda: False,
                     LocalOptIn=lambda: True, DelegatedWeather=lambda: True)
            env = dict(GetGame=lambda: f.game, HCServer=N(Get=lambda: N(
                IsStarted=lambda: f.state.m_Started, GetSettings=lambda: f.state.m_Settings)),
                HCAtmosphereQualification=gate, Print=f.profile.logs.append)
            env['s_Reported'] = False
            self.assertEqual(enabled, weather.authored(weather.GATE, 'Enabled', env, gate))
            self.assertNotIn('Atmosphere', f.starts)

    def test_search_gate_obeys_all_interior_search_dependency_combinations(self):
        for interiors, enabled in itertools.product((False, True), repeat=2):
            h = search.SearchIntegrationTests(); h.setUp()
            h.settings.EnableInteriors = interiors; h.settings.EnableSearch = enabled
            self.assertEqual(interiors and enabled, bool(h.call('SearchGate', h.actor, h.site)))

    def test_horde_and_chain_preferences_reach_infected_start_independently(self):
        for hordes, chains in itertools.product((False, True), repeat=2):
            h = infected.StartedModule(flags=infected.NO_ADMISSION, hordes=hordes)
            h.settings.EnableAlertChains = chains
            h.start()
            self.assertTrue(h.ctx.m_Healthy)
            self.assertEqual(hordes, h.ctx.m_Hordes)
            self.assertEqual(chains, h.ctx.m_Chains)
            h.stop()


class CombinedWorkTests(unittest.TestCase):
    def test_combined_real_module_stops_detach_rpc_and_core_callbacks_then_restart(self):
        f = CoreFixture()
        e = event_integration.EventIntegrationTests(); e.setUp()
        i = search.SearchIntegrationTests(); i.setUp(); i.startup_ports()
        h = infected.StartedModule(flags=infected.NO_ADMISSION, hordes=False)
        eco = ecology.EcologyModuleBehavior(); eco.setUp()
        rpc_callbacks = e.callbacks
        group_callbacks = []  # owner buckets for one synthetic native invoker
        # Native group service is a synthetic collaborator; its MODULE's real
        # OnStart/OnStop owns the callback insertion/removal being checked.
        service = N(Start=lambda cfg: True, Stop=lambda: None, Tick=lambda dt: None,
                    OnRPC=lambda *args: None)
        group = N(m_Config=N(Enabled=True), m_Service=None)
        env = dict(HCEventGroupService=lambda: service, Print=lambda text: None,
            DayZGame=N(Event_OnRPC=N(Insert=group_callbacks.append, Remove=group_callbacks.remove)))
        source = (ROOT / '4_World/Groups/HCGroupModule.c').read_text().replace('HCGroup', 'HCEventGroup')
        group_start = event.translate(source, 'OnStart', env, 'HCEventGroupModule', True)
        group_stop = event.translate(source, 'OnStop', env, 'HCEventGroupModule', True)
        craft = N(Started=False, Validated=False, Crafted=0)
        craft_source = (ROOT / '4_World/Crafting/HCCraftingModule.c').read_text()
        craft_source = re.sub(r'else[ \t]*\n([^\n]+)', r'else { \1 }', craft_source)
        for old, new in (('m_Started', 'Started'), ('m_Validated', 'Validated'), ('m_Crafted', 'Crafted')):
            craft_source = craft_source.replace(old, new)
        craft_env = dict(HCCraftingGate=craft, HCCraftingNativeChecks=N(Run=lambda: True),
                         GetGame=lambda: f.game, Print=lambda text: None)
        craft_state = N(IsEnabled=lambda settings: settings.EnableCrafting)
        craft_start = event.translate(craft_source, 'OnStart', craft_env, 'HCCraftingModule', True)
        craft_stop = event.translate(craft_source, 'OnStop', craft_env, 'HCCraftingModule', True)
        delegates = {
            'Events': (lambda: e.module.OnStart(f.state.m_Settings), e.module.OnStop),
            'Groups': (lambda: group_start(group, f.state.m_Settings), lambda: group_stop(group)),
            'Interiors': (lambda: i.call('OnStart', i.settings), lambda: i.call('OnStop')),
            'Infected': (h.start, h.stop),
            'Ecology': (lambda: eco.method('OnStart')(eco.module, f.state.m_Settings),
                        lambda: eco.method('OnStop')(eco.module)),
            'Crafting': (lambda: craft_start(craft_state, f.state.m_Settings), lambda: craft_stop(craft_state)),
        }
        for name, (start, stop) in delegates.items():
            f.modules[name].OnStart = lambda settings, start=start: start()
            f.modules[name].OnStop = stop
        for cycle in range(2):
            f.state.Start(); f.state.Start()
            self.assertEqual(7, len(f.state.m_Active))
            self.assertEqual(2, len(rpc_callbacks) + len(group_callbacks))
            self.assertEqual(1, len(f.queued))
            self.assertTrue(craft.Started)
            # One explicit already-started atmosphere owner, sharing the real
            # core queue. Execute its authored server Stop extension as well.
            atmosphere = N(m_HCAtmosphereStarted=True, m_HCNightLimited=True)
            night_callback = lambda force=False: None
            f.schedule(night_callback, 10000, True, False)
            atmosphere_env = dict(GetGame=lambda: f.game, CALL_CATEGORY_SYSTEM=0,
                                  HCApplyNightLimits=night_callback)
            atmosphere.HCStopAtmosphere = lambda: weather.authored(
                weather.WORLD, 'HCStopAtmosphere', atmosphere_env, atmosphere)
            f.game.GetMission = lambda: N(GetWorldData=lambda: atmosphere)
            stop_env = dict(GetGame=lambda: f.game, ChernarusPlusData=N(Cast=lambda data: data),
                            base=N(Stop=f.state.Stop))
            lifecycle = weather.WEATHER / 'HCAtmosphereLifecycle.c'
            weather.authored(lifecycle, 'Stop', stop_env, None)
            weather.authored(lifecycle, 'Stop', stop_env, None)
            self.assertFalse(atmosphere.m_HCAtmosphereStarted)
            self.assertEqual([], rpc_callbacks)
            self.assertEqual([], group_callbacks)
            self.assertEqual([], f.queued)
            self.assertFalse(craft.Started)

    # DESIGN QUESTION (reviewed: MaxTickWorkItems is per module; no shared-budget requirement) mods/HollowCountry/scripts/4_World/Core/HCServer.c:61:
    # independent module loops receive no shared remaining
    # allowance. Input: MaxTickWorkItems=32, 12 interior sites + 24 actors = 36.
    @unittest.expectedFailure
    def test_all_modules_tick_within_shared_work_budget(self):
        f = CoreFixture()
        f.state.Start()
        processed = []
        # Explicit admitted synthetic workload: 24 registered infected actors,
        # 12 live interior sites. Actual module loops choose what gets processed.
        h = infected.StartedModule(flags=infected.NO_ADMISSION, hordes=False).start()
        h.ctx.m_Actors = infected.Array(object() for _ in range(24))
        h.ctx.SampleActor = lambda actor: processed.append('infected')
        h.ctx.FinishSweep = lambda now: None
        f.modules['Infected'].OnTick = lambda dt: h.tick(10001)
        interior = search.SearchIntegrationTests(); interior.setUp()
        class Site:
            Deadline = 1000.
            @property
            def Owner(self):
                processed.append('interior')
                return object()
        interior.t.m_Sites = EArray(Site() for _ in range(12))
        interior.t.IsEnabled = lambda settings: settings.EnableInteriors
        f.modules['Interiors'].OnTick = lambda dt: interior.call('OnTick', dt)
        f.now += 1
        f.state.Tick()
        self.assertLessEqual(len(processed), f.state.m_Settings.MaxTickWorkItems,
                             'shared budget exceeded by actual infected/interior loops: ' + repr(processed))

    def test_stop_removes_queued_interior_updates_as_well_as_core_tick(self):
        f = CoreFixture()
        interior = search.SearchIntegrationTests(); interior.setUp()
        interior.env['GetGame'] = lambda: f.game
        f.game.ObjectDelete = lambda obj: None
        f.game.UpdatePathgraphRegionByObject = lambda obj: None
        interior.t.m_Objects = EArray([object(), object()])
        f.modules['Interiors'].OnStop = lambda: interior.call('OnStop')
        f.state.Start()
        source = (ROOT / '4_World/Interiors/HCInteriorPathgraph.c').read_text()
        source = re.sub(r'\b(\w+)\+\+;', r'\1 += 1;', source).replace(
            'placed.Count().ToString()', 'str(placed.Count())')
        env = dict(GetGame=lambda: f.game, Math=N(Min=min), Print=lambda text: None,
                   CALL_CATEGORY_SYSTEM=0, str=str,
                   HCInteriorTemplatePlacement=interior.env['HCInteriorTemplatePlacement'])
        env.update({k: int(v) for k, v in re.findall(r'static const int (\w+) = (\d+);', source)})
        schedule = event.translate(source, 'Schedule', env)
        self.assertEqual(2, schedule(interior.t.m_Objects))
        self.assertEqual(3, len(f.queued))
        f.state.Stop()
        self.assertEqual([], f.queued)


def reload_case(flag):
    def test(self):
        values = dict(DEFAULTS, **{flag: False})
        # A disabled dependency needs its dependants explicitly disabled too.
        if flag == 'EnableInteriors': values['EnableSearch'] = False
        if flag == 'EnableInfected': values.update(EnableHordes=False, EnableAlertChains=False)
        f = CoreFixture(values)
        original = f.profile.text
        f.state.Start(); self.assertFalse(getattr(f.state.m_Settings, flag))
        f.state.Stop(); f.state.Start()
        self.assertFalse(getattr(f.state.m_Settings, flag))
        self.assertEqual(original, f.profile.text)
        self.assertEqual([], f.profile.writes)
    return test


for _flag in ALL_FLAGS:
    setattr(CombinedFlagsTests, 'test_reload_preserves_' + _flag, reload_case(_flag))


if __name__ == '__main__': unittest.main()
