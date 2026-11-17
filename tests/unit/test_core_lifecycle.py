"""Execute authored lifecycle methods with explicit synthetic callbacks.

Restricted translation tests source control flow, not Enforce fault propagation.
"""
from pathlib import Path
import re
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts/4_World/Core/HCServer.c"


def method_body(name):
    source = SOURCE.read_text()
    match = re.search(r"void " + name + r"\(\)\s*\{", source)
    if not match:
        raise AssertionError("missing actual lifecycle method: " + name)
    start = end = match.end()
    depth = 1
    while depth:
        if source[end] == "{": depth += 1
        if source[end] == "}": depth -= 1
        end += 1
    return re.sub(r"//[^\n]*", "", source[start:end - 1])


def tokens(source):
    """Split statements/braces, retaining semicolons inside for headers."""
    chunk, depth, quoted = "", 0, False
    for char in source:
        if char == '"': quoted = not quoted
        if not quoted:
            if char == "(": depth += 1
            if char == ")": depth -= 1
            if char in "{};" and depth == 0:
                if chunk.strip(): yield chunk.strip()
                chunk = ""
                if char != ";": yield char
                continue
        chunk += char
    if chunk.strip(): raise AssertionError("unsupported unterminated statement")


def expression(text):
    text = re.sub(r"\bnew (HCModuleRegistry)\(\)", r"\1()", text)
    text = re.sub(r"\b(?:int|float|HCSettings|HCModule) (\w+) =", r"\1 =", text)
    text = re.sub(r"\bm_(\w+)\b", r"self.m_\1", text)
    text = re.sub(r"(?<!\.)\b(Stop|Tick)\b", r"self.\1", text)
    text = text.replace("&&", " and ").replace("||", " or ")
    text = re.sub(r"!(?!=)", "not ", text)
    for old, new in (("true", "True"), ("false", "False"), ("null", "None")):
        text = re.sub(r"\b" + old + r"\b", new, text)
    text = re.sub(r"(\b[\w.]+)\+\+", r"\1 += 1", text)
    return text


def actual_method(name, context):
    """Only if, foreach, reverse index for, calls and typed assignments."""
    lines, indent = [], 1
    for token in tokens(method_body(name)):
        if token == "{": indent += 1; continue
        if token == "}": indent -= 1; continue
        each = re.fullmatch(r"foreach \(HCModule (\w+) : (.*)\)", token, re.S)
        reverse = re.fullmatch(r"for \(int (\w+) = (.*); \1 >= 0; \1--\)(.*)", token, re.S)
        conditional = None
        if token.startswith("if ("):
            depth = 0
            for index in range(3, len(token)):
                if token[index] == "(": depth += 1
                if token[index] == ")": depth -= 1
                if depth == 0:
                    conditional = (token[4:index], token[index + 1:].strip())
                    break
        if each:
            line = "for " + each[1] + " in " + expression(each[2]) + ":"
        elif reverse:
            line = "for " + reverse[1] + " in range(" + expression(reverse[2]) + ", -1, -1): " + expression(reverse[3].strip())
        elif conditional:
            line = "if " + expression(conditional[0]) + ": " + expression(conditional[1])
        else:
            if re.search(r"\b(?:for|foreach|while|try|catch|throw|switch)\b", token):
                raise AssertionError("unsupported control flow: " + token)
            line = expression(token)
        lines.append("    " * indent + line.replace("\n", " "))
    namespace = dict(context)
    exec(compile("def actual(self):\n" + "\n".join(lines), "authored-HCServer:" + name, "exec"), namespace)
    return namespace["actual"]


class NativeArray(list):
    def Count(self): return len(self)
    def Insert(self, item): self.append(item)
    def Remove(self, index):
        # Installed native Remove swaps the last element into the removed slot.
        self[index] = self[-1]
        self.pop()
    def Clear(self): self.clear()


class AbortCallback(Exception):
    """Synthetic abort: not a claim about native script exception handling."""


class Module:
    def __init__(self, name, events, enabled=True, abort_start=False, abort_stop=False):
        self.name, self.events, self.enabled = name, events, enabled
        self.abort_start, self.abort_stop = abort_start, abort_stop

    def GetName(self): return self.name
    def IsEnabled(self, settings): return self.enabled
    def OnStart(self, settings):
        self.events.append("start:" + self.name)
        if self.abort_start: raise AbortCallback("start:" + self.name)
    def OnStop(self):
        self.events.append("stop:" + self.name)
        if self.abort_stop: raise AbortCallback("stop:" + self.name)


def fixture(modules=(), active=(), started=False, self_test=True, loaded=True, game_present=True, server=True):
    calls = []
    queue = SimpleNamespace(Remove=lambda fn: calls.append("remove-tick"),
                            CallLater=lambda *args: calls.append("schedule-tick"))
    game = SimpleNamespace(IsServer=lambda: server, GetTickTime=lambda: 12,
                           GetCallQueue=lambda category: queue)
    settings = SimpleNamespace(TickIntervalMs=1000)
    registry = SimpleNamespace(RegisterModules=lambda: calls.append("register"), GetModules=lambda: modules)
    context = {"GetGame": lambda: game if game_present else None,
               "HCNativeSelfTests": SimpleNamespace(Run=lambda: self_test),
               "HCSettings": SimpleNamespace(LoadFromProfile=lambda: settings if loaded else None),
               "HCModuleRegistry": lambda: registry, "Print": lambda text: None,
               "CALL_CATEGORY_SYSTEM": 0, "TickCount": lambda prior: 0}
    state = SimpleNamespace(m_Started=started, m_Active=NativeArray(active), m_Settings=settings,
                            m_Registry=None, m_LastTick=0, Tick=lambda: None,
                            # The perf sampler is a passive observer; its own tests live in test_perf_capture.
                            m_Perf=SimpleNamespace(Start=lambda seconds: None, Stop=lambda: None,
                                                   Sample=lambda elapsed, ticks: None,
                                                   RegisterModule=lambda name: None,
                                                   SampleModule=lambda index, ticks: None))
    state.Stop = lambda: actual_method("Stop", context)(state)
    state.Start = lambda: actual_method("Start", context)(state)
    return state, calls


class CoreLifecycleTests(unittest.TestCase):
    def test_tick_times_each_module_in_registration_order(self):
        events = []
        modules = [Module("Ecology",events),Module("Crafting",events)]
        state,_ = fixture(modules=modules)
        registered = []
        state.m_Perf.RegisterModule = registered.append
        state.Start()
        self.assertEqual(["Ecology","Crafting"],registered)
        ticks = [100,110,117,120,139,145]
        observations = []
        state.m_Perf.SampleModule = lambda index,work: observations.append((index,work))
        state.m_Perf.Sample = lambda elapsed,work: observations.append(("total",work))
        for module in modules: module.OnTick = lambda elapsed: events.append("tick")
        context = dict(GetGame=lambda:SimpleNamespace(IsServer=lambda:True,GetTickTime=lambda:13.),
                       TickCount=lambda prior:ticks.pop(0)-prior,Print=lambda text:None)
        actual_method("Tick",context)(state)
        self.assertEqual([(0,7),(1,19),("total",45)],observations)
        self.assertEqual(2,events.count("tick"))

    def test_stop_unwinds_initial_partial_start_in_reverse_order(self):
        events = []
        modules = [Module("a", events), Module("b", events)]
        state, calls = fixture(active=modules)
        state.Stop()
        self.assertEqual(events, ["stop:b", "stop:a"])
        self.assertEqual(state.m_Active, [])
        self.assertFalse(state.m_Started)
        self.assertEqual(calls, ["remove-tick"])
        state.Stop()
        self.assertEqual(events, ["stop:b", "stop:a"])

    def test_start_abort_tracks_current_module_for_cleanup(self):
        events = []
        modules = [Module("a", events), Module("b", events, abort_start=True), Module("c", events)]
        state, calls = fixture(modules=modules)
        with self.assertRaises(AbortCallback): state.Start()
        self.assertEqual(state.m_Active, modules[:2])
        self.assertFalse(state.m_Started)
        self.assertNotIn("schedule-tick", calls)
        state.Stop()
        self.assertEqual(events, ["start:a", "start:b", "stop:b", "stop:a"])
        self.assertEqual(state.m_Active, [])

    def test_stop_abort_removes_callback_before_call_and_next_stop_finishes(self):
        events = []
        modules = [Module("a", events), Module("b", events, abort_stop=True)]
        state, calls = fixture(active=modules, started=True)
        with self.assertRaises(AbortCallback): state.Stop()
        self.assertFalse(state.m_Started)
        self.assertEqual(state.m_Active, modules[:1])
        state.Stop()
        state.Stop()
        self.assertEqual(events, ["stop:b", "stop:a"])
        self.assertEqual(state.m_Active, [])

    def test_retry_cleans_stale_modules_before_any_new_start(self):
        events = []
        stale = [Module("old-a", events), Module("old-b", events)]
        fresh = [Module("new-a", events), Module("disabled", events, enabled=False), Module("new-b", events)]
        state, calls = fixture(modules=fresh, active=stale)
        state.Start()
        self.assertEqual(events, ["stop:old-b", "stop:old-a", "start:new-a", "start:new-b"])
        self.assertEqual(state.m_Active, [fresh[0], fresh[2]])
        self.assertTrue(state.m_Started)
        self.assertEqual(calls, ["remove-tick", "register", "schedule-tick"])
        state.Start()
        self.assertEqual(len(events), 4)

    def test_retry_cleanup_abort_does_not_admit_new_modules(self):
        events = []
        stale = [Module("old-a", events), Module("old-b", events, abort_stop=True)]
        fresh = [Module("new", events)]
        state, calls = fixture(modules=fresh, active=stale)
        with self.assertRaises(AbortCallback): state.Start()
        self.assertEqual(state.m_Active, stale[:1])
        self.assertEqual(events, ["stop:old-b"])
        self.assertNotIn("register", calls)
        state.Start()
        self.assertEqual(events, ["stop:old-b", "stop:old-a", "start:new"])
        self.assertEqual(state.m_Active, fresh)

    def test_failed_start_retry_unwinds_before_selftest_or_config_rejection(self):
        for options in ({"self_test": False}, {"loaded": False}):
            with self.subTest(options=options):
                events = []
                state, calls = fixture(active=[Module("stale", events)], **options)
                state.Start()
                self.assertEqual(events, ["stop:stale"])
                self.assertEqual(state.m_Active, [])
                self.assertFalse(state.m_Started)
                self.assertNotIn("schedule-tick", calls)

    def test_normal_order_enabled_filter_and_reverse_shutdown_are_preserved(self):
        events = []
        modules = [Module("a", events), Module("off", events, enabled=False), Module("b", events)]
        state, calls = fixture(modules=modules)
        state.Start()
        state.Stop()
        state.Stop()
        self.assertEqual(events, ["start:a", "start:b", "stop:b", "stop:a"])
        self.assertEqual(calls.count("schedule-tick"), 1)
        self.assertEqual(calls.count("remove-tick"), 1)
        self.assertEqual(state.m_LastTick, 12)

    def test_empty_stop_and_nonserver_start_remain_noops(self):
        state, calls = fixture()
        state.Stop()
        self.assertEqual(calls, [])
        for options in ({"game_present": False}, {"server": False}):
            with self.subTest(options=options):
                state, calls = fixture(**options)
                state.Start()
                self.assertEqual(calls, [])
                self.assertFalse(state.m_Started)

    def test_partial_stop_without_game_still_cleans_callbacks(self):
        events = []
        state, calls = fixture(active=[Module("a", events)], game_present=False)
        state.Stop()
        self.assertEqual(events, ["stop:a"])
        self.assertEqual(state.m_Active, [])
        self.assertEqual(calls, [])


class ModuleRegistryCapTests(unittest.TestCase):
    """Authored HCModuleRegistry.Register; synthetic modules only (no Enforce runtime)."""
    def registry(self):
        from tests.unit import test_event_runtime as runtime_tests
        from tests.unit.test_group_server import EArray
        source = (SOURCE.parent / "HCModule.c").read_text().replace("HCModule", "HCEventModule")
        self.lines = []
        env = {"Print": self.lines.append, "EArray": EArray}
        cls = type("AuthoredRegistry", (), {})
        for name in ("Register", "GetModules"):
            setattr(cls, name, runtime_tests.translate(source, name, env, "HCEventModuleRegistry", True))
        registry = cls()
        registry.m_Modules = EArray()
        return registry

    def test_cap_matches_perf_sampler_and_refusal_is_logged(self):
        registry = self.registry()
        for index in range(16):
            registry.Register(SimpleNamespace(GetName=lambda i=index: "module-" + str(i)))
        self.assertEqual(16, len(registry.GetModules()))
        self.assertEqual([], self.lines)
        registry.Register(SimpleNamespace(GetName=lambda: "module-16"))
        self.assertEqual(16, len(registry.GetModules()))
        self.assertTrue(any("module-16" in line and "cap 16" in line for line in self.lines), self.lines)


if __name__ == "__main__":
    unittest.main()
