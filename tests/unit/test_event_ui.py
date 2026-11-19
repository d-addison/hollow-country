"""HC-38 retired quest UI; explicit synthetic native ports, no DayZ proof."""
import re
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET

from tests.unit import test_event_runtime as event_runtime
from tests.unit.test_event_transport import methods, Handle, ROOT


class EventClientTests(unittest.TestCase):
    def setUp(self):
        self.e = event_runtime.environment()
        self.sent = []
        self.player = Handle()
        # Any engine/listener/input/transport access is unexpected for the shell.
        self.e["GetGame"] = lambda: self.fail("retired client queried the engine")
        self.e["GetUApi"] = lambda: self.fail("retired client queried input")
        self.e["DayZGame"] = SimpleNamespace(Event_OnRPC=SimpleNamespace(
            Insert=lambda fn: self.fail("retired listener attached"),
            Remove=lambda fn: self.fail("retired listener detached")))
        test = self
        class NativeRPC:
            def __init__(self): test.fail("retired client created transport")
        self.e["HCEventSyntheticRPC"] = NativeRPC
        self.client = methods(ROOT / "5_Mission/Events/HCEventClient.c", self.e)()

    def frame(self):
        view = self.e["HCEventPublicView"]()
        view.Enabled = True
        row = self.e["HCEventPublicRow"]()
        row.EventId = 1
        row.Joined = True
        view.Rows.Insert(row)
        return view

    def test_compatibility_lifecycle_and_frames_do_no_native_work(self):
        for _ in range(5):
            self.client.Start()
            self.client.SetBrowsing(True)
            self.client.Transmit(self.e["HCEventWireRequest"]())
            self.client.Update()
            self.client.SetBrowsing(False)
            self.client.Reset()
            self.client.Stop()
        self.assertEqual([], self.sent)
        self.assertEqual({}, vars(self.client), "no client cache or pending intent")

    def test_all_legacy_operations_refused_and_public_state_empty(self):
        for op in range(4):
            for ident in (0, 1, 32, 1000000001):
                self.assertFalse(self.client.CanSend(op, ident))
                self.assertFalse(self.client.Send(op, ident))
                self.assertIsNone(self.client.Row(ident))
        self.assertFalse(self.client.Browse())
        self.assertFalse(self.client.Fresh())
        self.assertFalse(self.client.IsBusy())
        self.assertEqual("", self.client.GetNotice())
        self.assertIsNone(self.client.GetView())

    def test_old_or_malformed_snapshots_never_publish_or_deserialize(self):
        for view in (self.frame(), None, object()):
            self.assertFalse(self.client.ViewValid(view))
            self.assertFalse(self.client.Receive(view))
        context = SimpleNamespace(Read=lambda: self.fail("retired view deserialized"))
        for sender in (None, object()):
            for target in (self.player, None, object()):
                self.client.OnRPC(sender, target, 4853802, context)
        self.assertIsNone(self.client.GetView())
        self.assertEqual({}, vars(self.client))


def menu_source(path):
    source = path.read_text()
    for typ in ("Widget", "UIScriptedMenu"):
        source = re.sub(r"\b" + typ + r"\b", "HCEventNative" + typ, source)
    source = source.replace("super.", "native_super_")
    return SimpleNamespace(read_text=lambda: source, stem=path.stem)


class EventMenuTests(unittest.TestCase):
    def test_old_menu_cannot_build_layout_and_factory_preserves_native_dispatch(self):
        env = dict(GetGame=lambda: self.fail("retired menu created widgets"))
        menu = methods(menu_source(ROOT / "5_Mission/Events/HCEventMenu.c"), env)()
        self.assertIsNone(menu.Init())
        calls = []
        env["native_super_CreateScriptedMenu"] = lambda ident: calls.append(ident) or ("native", ident)
        env["HCEventMenu"] = lambda: self.fail("retired menu instantiated")
        env["HCEventWire"] = SimpleNamespace(MENU_EVENTS=48538)
        factory = methods(menu_source(ROOT / "5_Mission/Events/HCEventMenuFactory.c"), env)()
        self.assertIsNone(factory.CreateScriptedMenu(48538))
        self.assertEqual([], calls)
        for ident in (0, 42, 48537):
            self.assertEqual(("native", ident), factory.CreateScriptedMenu(ident))
        self.assertEqual([0, 42, 48537], calls)

    def test_retired_input_and_layout_removed_without_affecting_other_bindings(self):
        root = ROOT.parent
        document = ET.parse(root / "inputs.xml")
        actions = {item.attrib["name"] for item in document.findall("./inputs/actions/input")}
        bindings = {item.attrib["name"]: [btn.attrib["name"] for btn in item.findall("btn")]
                    for item in document.findall("./preset/input")}
        expected = {"UAHollowCountryGrade": ["kK"], "UAHollowCountryPingOK": ["kNumpad7"],
                    "UAHollowCountryPingHurt": ["kNumpad3"], "UAHollowCountryPingHelp": ["kNumpad9"],
                    "UAHollowCountryAdmin": ["kPause"]}
        self.assertEqual(set(expected), actions)
        self.assertEqual(expected, bindings)
        self.assertFalse((root / "gui/layouts/hc_events.layout").exists())


class EventInputLifecycleTests(unittest.TestCase):
    def test_native_mission_lifecycle_has_no_quest_overrides(self):
        source = (ROOT / "5_Mission/Events/HCEventGameplay.c").read_text()
        source = re.sub(r"//[^\n]*", "", source)
        self.assertRegex(source, r"^\s*modded class MissionGameplay\s*\{\s*\}\s*$")


if __name__ == "__main__":
    unittest.main()
