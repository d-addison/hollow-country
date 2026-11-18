"""Batch A native wiring (A1 pathgraph, A17 noise intake pins, C4 voice pin).

Offline only. The authored Enforce statics are translated to Python with explicit
synthetic collaborators. That proves the authored decision logic, never DayZ
behaviour: no pathgraph rebuild, noise reduction unit, restock timing or native
noise delivery is established here. Native citations are checked against the
installed interface cache when it is present.
"""
import os
import re
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

try:
    from .test_alert_chain import Array
except ImportError:
    from test_alert_chain import Array

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "mods/HollowCountry/scripts/4_World"
CACHE = Path(os.environ.get(
    "HC_NATIVE_SCRIPTS",
    Path.home() / ".cache/hollow-country/native-scripts/scripts-1.30.164289"))
NEEDS_CACHE = unittest.skipUnless(CACHE.is_dir(), "installed native interface cache not present")


def code(path):
    return re.sub(r"//[^\n]*", "", Path(path).read_text())


def inner_block(text, open_index):
    depth = 0
    for index in range(open_index, len(text)):
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        if depth == 0:
            return text[open_index + 1:index]
    raise AssertionError("unbalanced braces")


def class_body(path, name):
    text = code(path)
    match = re.search(r"\bclass " + re.escape(name) + r"\b[^{;]*\{", text)
    if not match:
        raise AssertionError("missing class " + name + " in " + str(path))
    return inner_block(text, match.end() - 1)


def method_body(text, name):
    match = re.search(r"\b" + re.escape(name) + r"\s*\(([^)]*)\)\s*\{", text)
    if not match:
        raise AssertionError("missing method " + name)
    return match.group(1), inner_block(text, match.end() - 1)


def translate(path, class_name, scope, names, replacements=()):
    """Translate authored static methods of one class (restricted Enforce subset)."""
    body_text = class_body(path, class_name)
    for constant, value in re.findall(r"static const (?:int|float) (\w+) = ([^;]+);", body_text):
        scope[constant] = eval(value, {"__builtins__": {}})
    scope.setdefault("S", NS(s_Checked=False, s_OptIn=False))
    for name in names:
        parameters, body = method_body(body_text, name)
        args = [p.strip().split()[-1] for p in parameters.split(",") if p.strip()]
        body = re.sub(r"(?m)^(\s*)if \((.*)\) (return\b[^;]*;|continue;)\s*$", r"\1if (\2) {\3}", body)
        body = re.sub(r"(?m)^(\s*)if \((.*)\) (\w[\w.]* = [^;]*;)\s*$", r"\1if (\2) {\3}", body)
        body = re.sub(r"\b" + re.escape(class_name) + r"\.", "", body)
        body = re.sub(r"\bs_(\w+)", r"S.s_\1", body)
        body = re.sub(r"([\w.\[\]]+(?:\(\))?)\.ToString\(\)", r"str(\1)", body)
        for old, new in replacements:
            body = body.replace(old, new)
        lines, indent = ["def " + name + "(" + ",".join(args) + "):"], 1
        for token in re.split(r"([{};])", body):
            token = token.strip()
            if not token or token == ";":
                continue
            if token == "{":
                indent += 1
                continue
            if token == "}":
                indent -= 1
                continue
            token = re.sub(r"^(?:int|float|bool|vector|string|[A-Z]\w*(?:<[^>]*>)?)\s+(\w+)\s*(=|$)",
                           lambda m: m.group(1) + (" =" if m.group(2) else " = None"), token)
            token = re.sub(r"&&", " and ", token).replace("||", " or ")
            token = re.sub(r"!(?!=)", "not ", token)
            for old, new in (("true", "True"), ("false", "False"), ("null", "None")):
                token = re.sub(r"\b" + old + r"\b", new, token)
            if token.endswith("++"):
                token = token[:-2] + " += 1"
            if token.startswith("if ("):
                token = "if " + token[4:-1] + ":"
            elif token == "else":
                token = "else:"
            elif token.startswith("while ("):
                token = "while " + token[7:-1] + ":"
            lines.append("    " * indent + token)
        exec(compile("\n".join(lines), path.name + ":" + name + " [synthetic]", "exec"), scope)
    return scope


# --------------------------------------------------------------------------
# A1: pathgraph update after interior props
# --------------------------------------------------------------------------
PATHGRAPH = SCRIPTS / "Interiors/HCInteriorPathgraph.c"
MODULE = SCRIPTS / "Interiors/HCInteriorModule.c"


class FakeQueue:
    def __init__(self):
        self.calls = []

    def CallLater(self, function, delay, repeat, *params):
        self.calls.append((function, delay, repeat, params))


def pathgraph(server=True):
    queue, logs = FakeQueue(), []
    game = NS(IsServer=lambda: server, GetCallQueue=lambda category: queue if category == 1 else None,
              UpdatePathgraphRegionByObject="UpdatePathgraphRegionByObject")
    scope = {"GetGame": lambda: game, "CALL_CATEGORY_SYSTEM": 1, "Math": NS(Min=min),
             "Print": lambda text: logs.append(text)}
    scope["HCInteriorTemplatePlacement"] = NS(HCTimedPathgraph="HCTimedPathgraph")
    translate(PATHGRAPH, "HCInteriorPathgraph", scope, ["Schedule"])
    return scope["Schedule"], queue, logs


class PathgraphTests(unittest.TestCase):
    def test_each_placed_prop_gets_one_short_vanilla_style_deferred_update(self):
        schedule, queue, logs = pathgraph()
        props = Array(["a", "b", "c"])
        self.assertEqual(3, schedule(props))
        # HC-owned target: stopping the module must not cancel vanilla's own queued updates.
        self.assertEqual([("HCTimedPathgraph", 100, False, (prop,)) for prop in props], queue.calls)
        self.assertEqual(1, len(logs))
        self.assertIn("pathgraph", logs[0])

    def test_batch_is_bounded_skips_null_and_requires_server(self):
        schedule, queue, _ = pathgraph()
        self.assertEqual(8, schedule(Array(str(i) for i in range(50))))
        self.assertEqual(8, len(queue.calls))
        schedule, queue, _ = pathgraph()
        self.assertEqual(2, schedule(Array(["a", None, "b"])))
        for invalid in (None, Array()):
            schedule, queue, _ = pathgraph()
            self.assertEqual(0, schedule(invalid))
            self.assertEqual([], queue.calls)
        schedule, queue, _ = pathgraph(server=False)
        self.assertEqual(0, schedule(Array(["a"])))
        self.assertEqual([], queue.calls)

    def test_source_uses_only_the_vanilla_call_later_form_with_no_retained_queue(self):
        text = code(PATHGRAPH)
        self.assertIn("GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCInteriorTemplatePlacement.HCTimedPathgraph, DELAY_MS, false, placedObject);", text)
        module = code(MODULE)
        self.assertNotIn("Remove(GetGame().UpdatePathgraphRegionByObject)", module)
        self.assertIn("Remove(HCInteriorTemplatePlacement.HCTimedPathgraph)", module)
        for forbidden in ("ProcessMarkedObjectsForPathgraphUpdate", "MarkObjectForPathgraphUpdate", "foreach", "for (", "ref array", "static ref"):
            self.assertNotIn(forbidden, text)
        self.assertEqual(1, text.count("while ("))

    def test_place_candidate_updates_only_created_props_after_the_whole_batch(self):
        text = code(MODULE)
        start = text.index("void PlaceCandidate(")
        body = inner_block(text, text.index("{", start))
        call = "HCInteriorPathgraph.Schedule(created);"
        self.assertEqual(1, body.count(call))
        # After the rollback return and after orientation/ownership bookkeeping.
        self.assertGreater(body.index(call), body.index("partial layout rolled back"))
        self.assertGreater(body.index(call), body.index("object.SetOrientation(orientation);"))
        self.assertGreater(body.index(call), body.index("foreach (Object ownedObject : created) m_Objects.Insert(ownedObject);"))
        self.assertEqual(1, text.count("HCInteriorPathgraph.Schedule("))

    @NEEDS_CACHE
    def test_native_precedent_is_present_in_the_installed_cache(self):
        game = (CACHE / "3_Game/Global/Game.c").read_text()
        self.assertIn("void UpdatePathgraphRegionByObject(Object object)", game)
        for relative in ("4_World/Entities/ItemBase/TentBase.c", "4_World/Entities/ItemBase/BaseBuildingBase.c",
                         "4_World/Entities/ItemBase/FireplaceBase.c"):
            self.assertIn("CallLater(g_Game.UpdatePathgraphRegionByObject, 100, false, this)",
                          re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", (CACHE / relative).read_text())))


# --------------------------------------------------------------------------
# A17: no legitimate native noise-target intake; HC never labels noise as seen
# --------------------------------------------------------------------------
INFECTED = SCRIPTS / "Infected"


class NoiseIntakeTests(unittest.TestCase):
    def test_visual_provenance_is_assigned_in_exactly_one_gated_place(self):
        found = []
        for path in sorted(INFECTED.glob("*.c")):
            for match in re.finditer(r"\.Provenance\s*=\s*(\d+)\s*;", code(path)):
                found.append((path.name, match.group(1)))
        self.assertEqual(1, len([f for f in found if f[1] == "2"]), found)
        self.assertIn(("HCInfectedNavigation.c", "2"), found)
        text = code(INFECTED / "HCInfectedNavigation.c")
        self.assertRegex(text, r"static bool VisualProvenanceEstablished\([^)]*\)\s*\{\s*return false;\s*\}")
        self.assertRegex(text, r"static bool VisualSamplingAvailable\(\)\s*\{\s*return false;\s*\}")
        # Mind state or a retained target alone never establishes sight.
        self.assertLess(text.index("VisualProvenanceEstablished(controller)"), text.index("controller.GetTargetEntity()"))

    def test_hc_never_creates_noise_targets_and_emits_noise_only_from_search(self):
        # The only sanctioned emitter is the search-noise hook: one native
        # NoiseSystem.AddNoisePos on a committed search, using the vanilla
        # SurvivorBase action-noise config. HC never invents noise targets
        # or intercepts AI noise intake.
        emitters = []
        for path in (ROOT / "mods").rglob("*.c"):
            text = code(path)
            for forbidden in ("AddNoiseTarget", "OnNoise(", "AINoiseInfo"):
                self.assertNotIn(forbidden, text, str(path.relative_to(ROOT)))
            emitters.extend([path.name] * text.count("AddNoisePos"))
        self.assertEqual(["HCSearchNoise.c"], emitters)
        noise = code(SCRIPTS / "Loot" / "HCSearchNoise.c")
        self.assertIn('"CfgVehicles SurvivorBase NoiseActionDefault"', noise)

    @NEEDS_CACHE
    def test_native_cache_exposes_no_script_noise_intake_for_infected(self):
        behaviour = (CACHE / "3_Game/AIBehaviour.c").read_text()
        self.assertIn("//void OnNoise(AINoiseInfo noise, EntityAI source){}", behaviour)
        for relative in ("3_Game/Entities/DayZInfected.c", "3_Game/DayZCreatureAI.c", "3_Game/AI/AIAgent.c",
                         "3_Game/Entities/DayZInfectedInputController.c"):
            self.assertNotRegex((CACHE / relative).read_text(), r"(?i)noise", relative)
        zombie = (CACHE / "4_World/Entities/Creatures/Infected/ZombieBase.c").read_text()
        self.assertEqual(["AddNoise"], sorted(set(re.findall(r"\bAdd(?:Noise\w*)\b", zombie))))
        for relative in ("4_World/Entities/ItemBase/Gear/Tools/AlarmClock.c", "4_World/Entities/ItemBase/Gear/Tools/KitchenTimer.c",
                         "4_World/Entities/Vehicles/Components/VehicleHornComponent.c", "4_World/Entities/ItemBase/TrapSpawnBase.c"):
            self.assertIn("AddNoiseTarget(", (CACHE / relative).read_text(), relative)


# --------------------------------------------------------------------------
# C4: the voice override keeps native voice-to-AI-noise
# --------------------------------------------------------------------------
NATIVE = INFECTED / "HCInfectedNative.c"
SUPER_CALL = "super.ProcessSoundVoiceEvent(sound_event, aw);"


def voice_override_calls_super_first(text):
    declaration = re.search(r"override protected void ProcessSoundVoiceEvent\(AnimSoundVoiceEvent sound_event, out AbstractWave aw\)\s*\{", text)
    if not declaration:
        return False
    body = inner_block(text, declaration.end() - 1)
    statements = [s.strip() for s in body.split(";") if s.strip()]
    return bool(statements) and statements[0] + ";" == SUPER_CALL and body.count("super.ProcessSoundVoiceEvent(") == 1 \
        and "return" not in body.split("super.ProcessSoundVoiceEvent(")[0]


class VoiceNoiseTests(unittest.TestCase):
    def test_override_calls_super_unconditionally_as_its_first_statement(self):
        self.assertTrue(voice_override_calls_super_first(code(NATIVE)))

    def test_checker_rejects_every_way_of_losing_the_native_noise_path(self):
        text = code(NATIVE)
        for mutation in (
            text.replace(SUPER_CALL, ""),
            text.replace(SUPER_CALL, "if (!GetGame().IsServer()) return;\n        " + SUPER_CALL),
            text.replace(SUPER_CALL, "if (GetGame().IsServer()) { " + SUPER_CALL + " }"),
            text.replace(SUPER_CALL, "HCInfectedModule.Instance.NativeVoice(this, sound_event);\n        " + SUPER_CALL, 1),
            text.replace("out AbstractWave aw", "out AbstractWave wave"),
        ):
            self.assertFalse(voice_override_calls_super_first(mutation))

    def test_native_voice_adapter_runs_after_super_and_emits_no_second_noise(self):
        body = inner_block(code(NATIVE), re.search(r"override protected void ProcessSoundVoiceEvent\([^)]*\)\s*\{", code(NATIVE)).end() - 1)
        self.assertLess(body.index("super.ProcessSoundVoiceEvent"), body.index("NativeVoice("))
        self.assertNotIn("AddNoise", body)

    @NEEDS_CACHE
    def test_native_voice_path_in_cache_still_adds_server_noise(self):
        zombie = (CACHE / "4_World/Entities/Creatures/Infected/ZombieBase.c").read_text()
        self.assertIn("protected void ProcessSoundVoiceEvent(AnimSoundVoiceEvent sound_event, out AbstractWave aw)", zombie)
        self.assertRegex(zombie, r"if \(g_Game\.IsServer\(\)\)\s*\{\s*if \(sound_event\.m_NoiseParams != NULL\)\s*GetGame\(\)\.GetNoiseSystem\(\)\.AddNoise\(this, sound_event\.m_NoiseParams\);")


if __name__ == "__main__":
    unittest.main()
