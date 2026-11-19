"""Admin test kit: every Hollow Country feature has an admin trigger or inspector.

The authored Enforce bodies are executed through a small statement-level
EnScript-to-Python adapter. It only supplies syntax (types, braces, out
parameters, string concatenation) and explicit synthetic native collaborators;
it decides no gameplay policy of its own. Offline results never establish DayZ
behaviour, so runtime acceptance stays pending.
"""
import math
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "mods/HollowCountry/scripts"
ADMIN = SCRIPTS / "4_World/Admin"
LAYOUT = ROOT / "mods/HollowCountry/gui/layouts/hc_admin.layout"
MENU = SCRIPTS / "5_Mission/Admin/HCAdminMenu.c"
DOC = ROOT / "docs/ADMIN_TEST_KIT.md"
WEATHER = SCRIPTS / "4_World/Weather/HCWeatherDaysModule.c"
WEATHER_DAYS = SCRIPTS / "4_World/Weather/HCWeatherDays.c"

KEYWORDS = {"return", "else", "new", "delete", "break", "continue"}


class Cell:
    """Mutable cell standing in for an Enforce `out` parameter."""
    def __init__(self):
        self.value = None


def strip_comments(text):
    out, index, quoted = [], 0, False
    while index < len(text):
        char = text[index]
        if quoted:
            out.append(char)
            if char == "\\":
                out.append(text[index + 1])
                index += 1
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            out.append(char)
        elif text.startswith("//", index):
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        else:
            out.append(char)
        index += 1
    return "".join(out)


def block(text, start):
    depth, index, quoted = 1, start, False
    while depth:
        char = text[index]
        if quoted:
            if char == "\\":
                index += 1
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        else:
            depth += (char == "{") - (char == "}")
        index += 1
    return text[start:index - 1]


def class_text(path, name, modded):
    text = strip_comments(Path(path).read_text())
    prefix = r"\bmodded\s+class\s+" if modded else r"(?<!modded )\bclass\s+"
    match = re.search(prefix + name + r"\b[^{]*\{", text)
    if not match:
        raise AssertionError("Missing authored class %s in %s" % (name, Path(path).name))
    return block(text, match.end())


def authored_method(path, cls, name, modded=True):
    text = class_text(path, cls, modded)
    pattern = r"(?m)^    (?:(?:static|override|protected|private|ref)\s+)*[\w<>]+\s+" + name + r"\s*\(([^)]*)\)\s*\{"
    match = re.search(pattern, text)
    if not match:
        raise AssertionError("Missing authored method %s.%s in %s" % (cls, name, Path(path).name))
    return match.group(1), block(text, match.end())


def split_statements(body):
    out, current, depth, quoted, index = [], [], 0, False, 0
    while index < len(body):
        char = body[index]
        if quoted:
            current.append(char)
            if char == "\\":
                current.append(body[index + 1])
                index += 1
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            current.append(char)
        elif char in "([":
            depth += 1
            current.append(char)
        elif char in ")]":
            depth -= 1
            current.append(char)
        elif depth == 0 and char in "{};":
            token = "".join(current).strip()
            current = []
            if token:
                out.append(token)
            if char != ";":
                out.append(char)
        else:
            current.append(char)
        index += 1
    token = "".join(current).strip()
    if token:
        out.append(token)
    return out


def rewrite_tostring(text):
    while ".ToString()" in text:
        end = text.index(".ToString()")
        start = end
        while start > 0:
            char = text[start - 1]
            if char in ")]":
                close, depth = char, 0
                opener = "(" if char == ")" else "["
                while start > 0:
                    start -= 1
                    if text[start] == close:
                        depth += 1
                    elif text[start] == opener:
                        depth -= 1
                        if depth == 0:
                            break
            elif char.isalnum() or char in "_.":
                start -= 1
            else:
                break
        text = text[:start] + "str(" + text[start:end] + ")" + text[end + len(".ToString()"):]
    return text


def py_expr(text, members):
    parts = re.split(r'("(?:\\.|[^"\\])*")', text)
    for index in range(0, len(parts), 2):
        part = parts[index]
        part = re.sub(r"\bnew\s+(\w+)(?:<[^>]*>)?\s*\(", r"\1(", part)
        part = re.sub(r"\bnew\s+(\w+)(?:<[^>]*>)?", r"\1()", part)
        part = part.replace("&&", " and ").replace("||", " or ")
        part = re.sub(r"!(?!=)", " not ", part)
        for old, new in (("true", "True"), ("false", "False"), ("null", "None")):
            part = re.sub(r"\b" + old + r"\b", new, part)
        part = re.sub(r"(?<![\w.])m_", "self.m_", part)
        for name in members:
            part = re.sub(r"(?<![.\w])" + name + r"\(", "self." + name + "(", part)
        part = re.sub(r"(?<!/)/(?!/)", "//", part)
        parts[index] = part
    return rewrite_tostring("".join(parts))


def py_statement(token, members, outs):
    match = re.fullmatch(r"else if\s*\((.*)\)", token, re.S)
    if match:
        return "elif " + py_expr(match.group(1), members) + ":"
    if token == "else":
        return "else:"
    match = re.fullmatch(r"(if|while)\s*\((.*)\)", token, re.S)
    if match:
        return match.group(1) + " " + py_expr(match.group(2), members) + ":"
    match = re.fullmatch(r"for\s*\((?:int\s+)?(\w+)\s*=\s*(.+?);\s*\1\s*<\s*(.+?);\s*\1\+\+\)", token, re.S)
    if match:
        return "for %s in range(%s, %s):" % (match.group(1), py_expr(match.group(2), members), py_expr(match.group(3), members))
    if token == "return":
        return "return None"
    if token.startswith("return "):
        return "return " + py_expr(token[7:], members)
    if token in ("break", "continue"):
        return token
    match = re.fullmatch(r"([\w.\[\]]+)(\+\+|--)", token)
    if match:
        return match.group(1) + (" += 1" if match.group(2) == "++" else " -= 1")
    match = re.fullmatch(r"(?:ref\s+)?([A-Za-z_]\w*(?:<[^>]*>)?)\s+(\w+)(?:\s*=\s*(.+))?", token, re.S)
    if match and match.group(1) not in KEYWORDS:
        if match.group(3) is None:
            return match.group(2) + " = None"
        return match.group(2) + " = " + py_expr(match.group(3), members)
    match = re.fullmatch(r"(\w+)\s*=\s*(.+)", token, re.S)
    if match and match.group(1) in outs:
        return match.group(1) + ".value = " + py_expr(match.group(2), members)
    return py_expr(token, members)


def compile_authored(path, cls, name, scope, members=(), modded=True, fields=(), native_strings=None):
    params, text = authored_method(path, cls, name, modded)
    # Explicit public fields, like m_ members, belong to the synthetic receiver.
    # Do not rewrite string literals or fields already qualified by an object.
    parts = re.split(r'("(?:\\.|[^"\\])*")', text)
    for index in range(0, len(parts), 2):
        for field in fields:
            parts[index] = re.sub(r'(?<![.\w])' + re.escape(field) + r'\b', 'self.' + field, parts[index])
    text = ''.join(parts)
    namespace = dict(scope)
    if native_strings:
        # Give literal strings the same explicit synthetic native methods as
        # strings returned by a fake widget. This is language scaffolding only.
        def literal(match):
            key = '_native_literal_' + str(len(namespace))
            namespace[key] = native_strings(json.loads(match[0]))
            return key
        text = re.sub(r'"(?:\\.|[^"\\])*"', literal, text)
    # Older code writes brace-less one-line returns; the translator needs braces.
    text = re.sub(r"\bif\s*\(([^;{}]*)\)\s*return\s+([^;{}]*);", r"if (\1) { return \2; }", text)
    names, outs = [], set()
    for raw in [p for p in params.split(",") if p.strip()]:
        words = raw.replace("=", " ").split()
        words = [w for w in words if w not in ("out", "inout", "notnull", "ref")]
        names.append(words[1])
        if re.match(r"\s*out\b", raw):
            outs.add(words[1])
    lines, indent, pending = ["def run(self%s):" % "".join(", " + n for n in names)], 1, False
    tokens = split_statements(text)
    for position, token in enumerate(tokens):
        if token == "{":
            if not pending:
                raise AssertionError("Unexpected block in %s.%s" % (cls, name))
            indent += 1
            lines.append("    " * indent + "pass")
            pending = False
            continue
        if token == "}":
            indent -= 1
            continue
        line = py_statement(token, members, outs)
        if line.endswith(":") and not line.startswith("return"):
            if position + 1 >= len(tokens) or tokens[position + 1] != "{":
                raise AssertionError("Braces required after %r in %s.%s" % (token, cls, name))
            pending = True
        lines.append("    " * indent + line)
    exec(compile("\n".join(lines), "%s.%s [synthetic]" % (cls, name), "exec"), namespace)
    return namespace["run"]


def real_math():
    return NS(Min=min, Max=max, Round=lambda x: int(math.floor(x + 0.5)), Floor=math.floor,
              Clamp=lambda v, lo, hi: max(lo, min(hi, v)))


def vector_stub():
    return NS(DistanceSq=lambda a, b: sum((x - y) ** 2 for x, y in zip(a, b)))


class Recorder:
    def __init__(self):
        self.calls = []


def base_scope(**extra):
    scope = dict(Math=real_math(), vector=vector_stub(), EArray=EArray)
    scope.update(extra)
    return scope


# ---------------------------------------------------------------- hooks

class InfectedMemoryHeatHook(unittest.TestCase):
    PATH = ADMIN / "HCAdminDirectors.c"

    def build(self, active=True, valid=True, cells=None, heat=0.5):
        self.recorded = []
        state = NS(Cells=EArray(cells or []))
        instance = NS(m_State=state, m_Dirty=False)
        instance.Find = lambda x, z: next((c for c in state.Cells if (c.X, c.Z) == (x, z)), None)
        scope = base_scope(
            s_Instance=instance,
            Active=lambda: active,
            Heat=lambda pos: heat,
            Record=lambda pos, loud: self.recorded.append((pos, loud)),
            HCInfectedStore=NS(ValidPosition=lambda pos: valid),
            GetGame=lambda: NS(IsServer=lambda: True),
            CohortSizeAtHeat=lambda h, n: 4,
            ResponseLimitAtHeat=lambda h: 8,
        )
        self.instance = instance
        self.fn = compile_authored(self.PATH, "HCInfectedMemory", "HCAdminHeat", scope)

    def test_inactive_memory_refuses_with_reason(self):
        self.build(active=False)
        reason = Cell()
        self.assertFalse(self.fn(None, (100, 0, 100), 2, reason))
        self.assertEqual("infected-memory-unavailable", reason.value)
        self.assertEqual([], self.recorded)

    def test_shot_count_is_bounded(self):
        self.build()
        reason = Cell()
        self.assertFalse(self.fn(None, (100, 0, 100), 4, reason))
        self.assertEqual("heat-shots-0-to-3", reason.value)
        self.assertFalse(self.fn(None, (100, 0, 100), -1, reason))
        self.assertEqual([], self.recorded)

    def test_shots_use_the_normal_record_path_at_full_loudness(self):
        self.build()
        reason = Cell()
        self.assertTrue(self.fn(None, (100, 0, 100), 2, reason))
        self.assertEqual([((100, 0, 100), 1)] * 2, self.recorded)
        self.assertIn("heat-recorded", reason.value)

    def test_zero_clears_only_this_cell(self):
        here = NS(X=0, Z=0, Value=0.7)
        other = NS(X=5, Z=5, Value=0.7)
        self.build(cells=[here, other])
        reason = Cell()
        self.assertTrue(self.fn(None, (100, 0, 100), 0, reason))
        self.assertEqual([other], list(self.instance.m_State.Cells))
        self.assertTrue(self.instance.m_Dirty)
        self.assertEqual("heat-cell-cleared", reason.value.split(";")[0])

    def test_zero_without_a_cell_is_refused_with_a_reason(self):
        self.build()
        reason = Cell()
        self.assertFalse(self.fn(None, (100, 0, 100), 0, reason))
        self.assertEqual("no-heat-in-this-cell", reason.value)

    def test_shots_that_record_nothing_are_not_reported_as_heat(self):
        # Record() drops samples past its per-second cap or without a clock.
        self.build(heat=0.0)
        reason = Cell()
        self.assertFalse(self.fn(None, (100, 0, 100), 2, reason))
        self.assertEqual("heat-record-refused-or-capped", reason.value)


class InfectedSitterClearHook(unittest.TestCase):
    PATH = ADMIN / "HCAdminDirectors.c"

    def test_clear_refuses_without_an_admin_sitter_and_removes_only_it(self):
        deleted = []
        scope = base_scope(GetGame=lambda: NS(ObjectDelete=deleted.append))
        fn = compile_authored(self.PATH, "HCInfectedModule", "HCAdminClearSitter", scope)
        service = NS(m_HCAdminSitter=None)
        reason = Cell()
        self.assertFalse(fn(service, reason))
        self.assertEqual("no-admin-sitter", reason.value)
        body = object()
        service.m_HCAdminSitter = body
        self.assertTrue(fn(service, reason))
        self.assertEqual([body], deleted)
        self.assertIsNone(service.m_HCAdminSitter)
        self.assertIn("other infected untouched", reason.value)


class RadioHook(unittest.TestCase):
    PATH = ADMIN / "HCAdminDirectors.c"

    def build(self, receiving, busy=False, save=True):
        channels = EArray([NS(Faction=f, Frequency=freq, LastSent=900, Sequence=3)
                           for f, freq in (("locals", 87.8), ("volunteers", 89.5), ("scavengers", 91.3),
                                           ("raiders", 94.6), ("travellers", 96.6))])
        saved = []
        store = NS(Data=NS(Channels=channels), Healthy=lambda: True, Save=lambda: saved.append(1) or save)
        service = NS(m_Store=store, m_Channel=channels[0] if busy else None, m_ChannelCursor=0)
        service.Receiving = lambda player, freq: freq == receiving
        self.saved, self.channels = saved, channels
        self.fn = compile_authored(self.PATH, "HCRadioChatter", "HCAdminRadio", base_scope(), ("Receiving",))
        return service

    def test_requires_a_receiving_radio_and_says_how(self):
        service = self.build(receiving=None)
        reason = Cell()
        self.assertFalse(self.fn(service, object(), reason))
        self.assertIn("no-receiving-radio", reason.value)
        self.assertEqual([], self.saved)

    def test_busy_channel_is_not_overwritten(self):
        service = self.build(receiving=91.3, busy=True)
        reason = Cell()
        self.assertFalse(self.fn(service, object(), reason))
        self.assertIn("radio-channel-busy", reason.value)

    def test_clears_only_the_tuned_channel_rate_limit_and_queues_it(self):
        service = self.build(receiving=91.3)
        reason = Cell()
        self.assertTrue(self.fn(service, object(), reason))
        self.assertEqual([900, 900, 0, 900, 900], [c.LastSent for c in self.channels])
        self.assertEqual(2, service.m_ChannelCursor)
        self.assertEqual([1], self.saved)
        self.assertIn("rate-limit-cleared", reason.value)

    def test_failed_save_reports_a_reason(self):
        service = self.build(receiving=87.8, save=False)
        reason = Cell()
        self.assertFalse(self.fn(service, object(), reason))
        self.assertEqual("radio-channel-save-refused", reason.value)


class DeadDropHook(unittest.TestCase):
    PATH = ADMIN / "HCAdminDirectors.c"

    def build(self, rows, ready=True, today=10, saved=True):
        service = NS(m_Ready=ready, m_State=NS(Rows=EArray(rows)), m_Next=0, m_Elapsed=0.0, m_Dirty=False)
        service.Count = lambda: len(service.m_State.Rows)
        service.SaveChanged = lambda: saved
        scope = base_scope(HCEscalationClock=NS(Day=lambda: today))
        self.fn = compile_authored(self.PATH, "HCDeadDrops", "HCAdminDeadDrop", scope, ("Count", "SaveChanged"))
        return service

    @staticmethod
    def row(name, x, deposits=0, next_day=99, quarantined=False):
        return NS(Id=name, Cache=NS(Position=(x, 0, 0), Phase=2), Deposits=deposits, NextDay=next_day, Quarantined=quarantined)

    def test_unavailable_module_is_refused(self):
        service = self.build([], ready=False)
        reason = Cell()
        self.assertFalse(self.fn(service, (0, 0, 0), reason))
        self.assertEqual("dead-drop-service-unavailable", reason.value)

    def test_nearest_spot_is_made_due_through_the_normal_tick(self):
        rows = [self.row("far", 5000), self.row("near", 100)]
        service = self.build(rows)
        reason = Cell()
        self.assertTrue(self.fn(service, (0, 0, 0), reason))
        self.assertEqual(10, rows[1].NextDay)
        self.assertEqual(99, rows[0].NextDay)
        self.assertEqual(1, service.m_Next)
        self.assertEqual(60, service.m_Elapsed)
        self.assertIn("near", reason.value)

    def test_quarantined_and_exhausted_spots_keep_their_caps(self):
        service = self.build([self.row("q", 1, quarantined=True)])
        reason = Cell()
        self.assertFalse(self.fn(service, (0, 0, 0), reason))
        self.assertIn("dead-drop-quarantined", reason.value)
        service = self.build([self.row("full", 1, deposits=4)])
        self.assertFalse(self.fn(service, (0, 0, 0), reason))
        self.assertIn("deposits-exhausted", reason.value)
        self.assertEqual(0, service.m_Elapsed)

    def test_save_refusal_is_reported(self):
        service = self.build([self.row("a", 1)], saved=False)
        reason = Cell()
        self.assertFalse(self.fn(service, (0, 0, 0), reason))
        self.assertEqual("dead-drop-persistence-refused", reason.value)


class LootRefreshHook(unittest.TestCase):
    PATH = ADMIN / "HCAdminDirectors.c"

    def build(self, rows, active=True, pending=None, now=1000000, last=900000, saved=True):
        service = NS(m_State=NS(Rows=EArray(rows), LastUtc=last), m_Pending=len(rows) if pending is None else pending,
                     m_Minute=0.0, m_Store=NS(Save=lambda state: saved))
        service.Active = lambda: active
        scope = base_scope(HCGroupClock=NS(Utc=lambda: now), MAX_RECORDS=4096,
                           HCSearchRefreshPolicy=NS(Interval=lambda site: 172800),
                           HCSearchRefreshModule=NS(MAX_RECORDS=4096))
        self.fn = compile_authored(self.PATH, "HCSearchRefreshModule", "HCAdminDue", scope, ("Active",))
        return service

    @staticmethod
    def row(searched, ready=False):
        return NS(Scope="w/p", SiteId="s%d" % searched, SearchedUtc=searched, Ready=ready)

    def test_inactive_and_empty_are_refused_with_reasons(self):
        reason = Cell()
        service = self.build([], active=False)
        self.assertFalse(self.fn(service, reason))
        self.assertEqual("loot-refresh-service-unavailable", reason.value)
        service = self.build([self.row(5, ready=True)], pending=0)
        self.assertFalse(self.fn(service, reason))
        self.assertIn("no-pending-refresh-timer", reason.value)

    def test_ages_only_the_oldest_pending_timer_and_requests_a_tick(self):
        rows = [self.row(500000), self.row(300000), self.row(100000, ready=True)]
        service = self.build(rows)
        reason = Cell()
        self.assertTrue(self.fn(service, reason))
        self.assertEqual(1000000 - 172800, rows[1].SearchedUtc)
        self.assertEqual(500000, rows[0].SearchedUtc)
        self.assertEqual(100000, rows[2].SearchedUtc)
        self.assertEqual(1000000, service.m_State.LastUtc)
        self.assertEqual(60.0, service.m_Minute)
        self.assertIn("no loot created", reason.value)

    def test_save_refusal_is_reported(self):
        service = self.build([self.row(300000)], saved=False)
        reason = Cell()
        self.assertFalse(self.fn(service, reason))
        self.assertEqual("refresh-timer-save-refused", reason.value)


class ForageHook(unittest.TestCase):
    PATH = ADMIN / "HCAdminDirectors.c"

    def build(self, nodes, month=7, healthy=True, position=(450, 0, 450)):
        service = NS(m_Healthy=healthy, m_Nodes=EArray(nodes), m_Elapsed=0.0, m_Dirty=False)
        # GetDate has native out parameters, so the month comes from the
        # protected HCAdminMonth helper; the synthetic service fixes it here.
        service.HCAdminMonth = lambda: month
        self.fn = compile_authored(self.PATH, "HCForageModule", "HCAdminForage", base_scope(), ("HCAdminMonth",))
        self.month = month
        self.player = NS(GetPosition=lambda: position)
        return service

    @staticmethod
    def node(cell_x, cell_z, ready=5000, item=None, live=False):
        return NS(Spot=NS(CellX=cell_x, CellZ=cell_z, NodeSlot=0, ReadyUtc=ready), Item=item, WasLive=live)

    def test_out_of_season_is_refused_with_the_month(self):
        service = self.build([self.node(2, 2)], month=3)
        reason = Cell()
        self.assertFalse(self.fn(service, self.player, reason))
        self.assertIn("forage-out-of-season", reason.value)
        self.assertIn("month=3", reason.value)
        self.assertEqual(5000, service.m_Nodes[0].Spot.ReadyUtc)

    def test_clears_only_idle_cooldowns_in_the_players_cell(self):
        nodes = [self.node(2, 2), self.node(2, 2, item=object()), self.node(2, 2, live=True), self.node(9, 9)]
        service = self.build(nodes, month=7)
        reason = Cell()
        self.assertTrue(self.fn(service, self.player, reason))
        self.assertEqual([0, 5000, 5000, 5000], [n.Spot.ReadyUtc for n in service.m_Nodes])
        self.assertEqual(10, service.m_Elapsed)
        self.assertTrue(service.m_Dirty)
        self.assertIn("cleared=1", reason.value)

    def test_unhealthy_module_is_refused(self):
        service = self.build([], healthy=False)
        reason = Cell()
        self.assertFalse(self.fn(service, self.player, reason))
        self.assertEqual("forage-service-unavailable", reason.value)


class SettlementDecayHook(unittest.TestCase):
    PATH = ADMIN / "HCAdminDirectors.c"

    def build(self, ready=True, pending=False, fault=False):
        places = EArray([NS(Id="a", Position=(0, 0, 0)), NS(Id="b", Position=(5000, 0, 5000))])
        towns = EArray([NS(Id="a", Ransack=1, Barricades=0, Remains=1, Notices=1), NS(Id="b", Ransack=0, Barricades=0, Remains=0, Notices=0)])
        service = NS(m_Fault=fault, m_State=NS(Towns=towns) if ready else None, m_Catalog=NS(Places=places),
                     m_HistoryPending=pending, m_Cursor=1, m_Elapsed=0.0)
        self.fn = compile_authored(self.PATH, "HCSettlementDecay", "HCAdminTown", base_scope())
        return service

    def test_queues_the_nearest_town_for_the_normal_step(self):
        service = self.build()
        reason = Cell()
        self.assertTrue(self.fn(service, (100, 0, 100), reason))
        self.assertEqual(0, service.m_Cursor)
        self.assertEqual(10, service.m_Elapsed)
        self.assertIn("town-queued id=a", reason.value)

    def test_refusals_carry_reasons(self):
        reason = Cell()
        cold = self.build(ready=False)
        self.assertFalse(self.fn(cold, (0, 0, 0), reason))
        self.assertIn("decay-not-initialised", reason.value)
        warm = self.build()
        self.assertFalse(self.fn(warm, (3000, 0, 3000), reason))
        self.assertEqual("no-town-within-1000m", reason.value)
        service = self.build(pending=True)
        self.assertFalse(self.fn(service, (0, 0, 0), reason))
        self.assertIn("history-scan-in-progress", reason.value)
        self.assertEqual(1, service.m_Cursor)


class WeatherOverrideHook(unittest.TestCase):
    def build(self, active=True, utc=1_760_000_000, suspended=False, mission=False, frozen=False):
        service = NS(m_HCWeatherDaysActive=active, m_HCWeatherAdminDay=-1, m_HCWeatherAdminUntil=0.0,
                     m_HCWeatherCalm=0.0, m_HCWeatherWasWet=True, m_HCWeatherDaysSuspended=suspended,
                     m_Weather=NS(GetMissionWeather=lambda: mission, GetWeatherUpdateFrozen=lambda: frozen))
        seed_fn = compile_authored(WEATHER_DAYS, "HCWeatherDays", "Seed", base_scope(), modded=False)
        self.seed = lambda day: seed_fn(None, day)
        scope = base_scope(
            GetGame=lambda: NS(IsServer=lambda: True, GetTickTime=lambda: 1000.0),
            HCGroupClock=NS(Utc=lambda: utc),
            HCWeatherDays=NS(Seed=self.seed),
        )
        self.fn = compile_authored(WEATHER, "ChernarusPlusData", "HCAdminWeather", scope)
        self.utc = utc
        return service

    def test_codes_outside_zero_to_four_are_refused(self):
        service = self.build()
        reason = Cell()
        self.assertFalse(self.fn(service, 9, reason))
        self.assertIn("weather-code-0-clear", reason.value)

    def test_inactive_weather_days_refuse_with_a_reason(self):
        service = self.build(active=False)
        reason = Cell()
        self.assertFalse(self.fn(service, 4, reason))
        self.assertIn("weather-days-inactive", reason.value)

    def test_each_profile_picks_a_day_whose_seed_draws_it(self):
        for code, buckets in ((4, (0,)), (3, (1, 2)), (1, (3, 4)), (2, (3, 4))):
            service = self.build()
            reason = Cell()
            self.assertTrue(self.fn(service, code, reason), (code, reason.value))
            chosen = service.m_HCWeatherAdminDay
            self.assertGreaterEqual(chosen, self.utc // 86400)
            self.assertLess(chosen, self.utc // 86400 + 64)
            self.assertIn(self.seed(chosen) % 5, buckets)
            self.assertEqual(2800.0, service.m_HCWeatherAdminUntil)

    def test_calm_sets_the_normal_calm_window_and_others_clear_it(self):
        service = self.build()
        self.assertTrue(self.fn(service, 2, Cell()))
        self.assertEqual(3, service.m_HCWeatherCalm)
        self.assertTrue(self.fn(service, 4, Cell()))
        self.assertEqual(0, service.m_HCWeatherCalm)

    def test_zero_clears_the_override(self):
        service = self.build()
        self.fn(service, 4, Cell())
        reason = Cell()
        self.assertTrue(self.fn(service, 0, reason))
        self.assertEqual(-1, service.m_HCWeatherAdminDay)
        self.assertIn("override-cleared", reason.value)

    def test_a_foreign_weather_controller_refuses_instead_of_claiming_success(self):
        for kwargs in ({"suspended": True}, {"mission": True}, {"frozen": True}):
            service = self.build(**kwargs)
            reason = Cell()
            self.assertFalse(self.fn(service, 4, reason), kwargs)
            self.assertEqual("foreign-weather-controller-active", reason.value)
            self.assertEqual(-1, service.m_HCWeatherAdminDay)

    def test_clearing_ends_the_calm_the_override_started(self):
        service = self.build()
        self.assertTrue(self.fn(service, 2, Cell()))
        self.assertTrue(self.fn(service, 0, Cell()))
        self.assertEqual(0, service.m_HCWeatherCalm)

    def test_expiry_also_ends_the_override_calm(self):
        text = strip_comments(WEATHER.read_text())
        expiry = re.search(r"else\s*\{([^}]*admin override expired[^}]*)\}", text)
        assert expiry is not None, "override expiry branch missing"
        self.assertRegex(expiry.group(1), r"m_HCWeatherCalm\s*=\s*0")

    def test_the_tick_reads_the_override_only_while_it_lasts(self):
        text = strip_comments(WEATHER.read_text())
        self.assertRegex(text, r"m_HCWeatherAdminDay\s*>=\s*0")
        self.assertRegex(text, r"GetTickTime\(\)\s*<\s*m_HCWeatherAdminUntil")


# ---------------------------------------------------------------- routing

NEW_COMMANDS = ("camptier", "campvisit", "campraid", "kit", "list", "clear", "memory", "radio", "deaddrop", "loot", "forage", "decay", "weather")
OLD_COMMANDS = ("status", "snapshot", "sitter", "dormant", "horde", "scene", "event", "camp", "holdout", "day")


class KnownCommands(unittest.TestCase):
    def setUp(self):
        # Catalog-derived synthetic metadata; HCKnown still executes the authored
        # server body. Catalog/dispatch equality is independently checked in UI tests.
        catalog = (SCRIPTS / '3_Game/Admin/HCAdminCatalog.c').read_text()
        ids = set(re.findall(r'HCAdd\("(\w+)"', strip_comments(catalog)))
        scope = base_scope(HCAdminCatalog=NS(HCKnown=lambda command: command in ids))
        self.known = compile_authored(ADMIN / "HCAdminModule.c", "HCAdminModule", "HCKnown", scope, modded=False)

    def test_every_old_and_new_command_is_on_the_allowlist(self):
        for command in OLD_COMMANDS + NEW_COMMANDS:
            self.assertTrue(self.known(None, command), command)

    def test_unknown_commands_stay_refused(self):
        for command in ("", "teleport", "spawn", "give", "KIT", "ban"):
            self.assertFalse(self.known(None, command), command)


class ExtraRouting(unittest.TestCase):
    """HCExtra routes each new command to exactly one module hook and its reason."""

    def build(self, present=True):
        self.calls = []
        record = self.calls

        def hook(name, result=True, reason_text="r"):
            def call(*args):
                record.append((name, args[:-1]))
                args[-1].value = reason_text
                return result
            return call

        module = NS(HCAdminClearSitter=hook("clear"), HCAdminRadio=hook("radio"), HCAdminDeadDrop=hook("deaddrop"),
                    HCAdminDue=hook("loot"), HCAdminForage=hook("forage"), HCAdminTown=hook("decay"),
                    HCAdminWeather=hook("weather"))
        named = NS(HCAdminModuleNamed=lambda name: module if present else None)
        scope = base_scope(
            HCInfectedModule=NS(Instance=module if present else None, Cast=lambda m: m),
            HCInfectedMemory=NS(HCAdminHeat=hook("memory")),
            HCRadioChatter=NS(Get=lambda: module if present else None),
            HCDeadDrops=NS(Get=lambda: module if present else None),
            HCSearchRefreshModule=NS(Cast=lambda m: m),
            HCForageModule=NS(Cast=lambda m: m),
            HCSettlementDecay=NS(Cast=lambda m: m),
            HCWeatherDaysModule=NS(Cast=lambda m: m),
            HCServer=NS(Get=lambda: named),
        )
        self.owner = NS(HCNamed=named.HCAdminModuleNamed)
        self.fn = compile_authored(ADMIN / "HCAdminModule.c", "HCAdminModule", "HCExtra", scope, ("HCNamed",), modded=False)

    def run_command(self, command, value=0):
        reason = Cell()
        ok = self.fn(self.owner, "PLAYER", (1, 2, 3), command, value, reason)
        return ok, reason.value

    def test_each_command_reaches_its_module_hook(self):
        self.build()
        expected = {"clear": "clear", "memory": "memory", "radio": "radio", "deaddrop": "deaddrop",
                    "loot": "loot", "forage": "forage", "decay": "decay", "weather": "weather"}
        for command, hook in expected.items():
            self.calls.clear()
            ok, reason = self.run_command(command, 2)
            self.assertTrue(ok, command)
            self.assertEqual("r", reason)
            self.assertEqual(1, len(self.calls), command)
            self.assertEqual(hook, self.calls[0][0])

    def test_value_and_position_reach_the_hooks_that_use_them(self):
        self.build()
        self.run_command("memory", 3)
        self.assertEqual(("memory", ((1, 2, 3), 3)), self.calls[-1])
        self.run_command("weather", 4)
        self.assertEqual(("weather", (4,)), self.calls[-1])
        self.run_command("deaddrop")
        self.assertEqual(("deaddrop", ((1, 2, 3),)), self.calls[-1])

    def test_missing_modules_refuse_with_a_specific_reason(self):
        self.build(present=False)
        for command in ("clear", "radio", "deaddrop", "loot", "forage", "decay", "weather"):
            ok, reason = self.run_command(command)
            self.assertFalse(ok, command)
            self.assertEqual("module-unavailable", reason, command)


class KitListing(unittest.TestCase):
    def build(self, active=("AdminMap", "Infected", "Scenes", "Radio"), sitter_class=True):
        lines = []
        reply = NS(Lines=EArray())
        scope = base_scope(GetGame=lambda: NS(ConfigIsExisting=lambda name: sitter_class))
        service = NS()
        service.HCAdminModuleNamed = lambda name: name if name in active else None
        fn = compile_authored(ADMIN / "HCAdminStatus.c", "HCServer", "HCAdminKit", scope,
                              ("HCAdminKitLine", "HCAdminModuleNamed"))
        line_fn = compile_authored(ADMIN / "HCAdminStatus.c", "HCServer", "HCAdminKitLine", scope,
                                   ("HCAdminModuleNamed",))
        service.HCAdminKitLine = lambda *args: line_fn(service, *args)
        fn(service, reply)
        return reply.Lines

    def commands_listed(self, lines):
        return [re.search(r"cmd=(\w+)", line).group(1) for line in lines]

    def test_every_known_command_appears_exactly_once(self):
        lines = self.build()
        self.assertEqual(sorted(OLD_COMMANDS + NEW_COMMANDS), sorted(self.commands_listed(lines)))

    def test_availability_follows_the_active_modules(self):
        lines = self.build()
        by_command = {re.search(r"cmd=(\w+)", l).group(1): l for l in lines}
        self.assertIn("available=1", by_command["horde"])
        self.assertIn("available=1", by_command["radio"])
        self.assertIn("available=0", by_command["deaddrop"])
        self.assertIn("reason=module-inactive", by_command["deaddrop"])
        self.assertIn("available=1", by_command["kit"])
        for line in lines:
            self.assertTrue(line.startswith("[HC Admin] kit "), line)
            self.assertIn("input=", line)

    def test_sitter_needs_its_addon_class(self):
        lines = self.build(sitter_class=False)
        sitter = [l for l in lines if "cmd=sitter" in l][0]
        self.assertIn("available=0", sitter)
        self.assertIn("class-missing-HC_ZmbM_Sitter", sitter)

    def test_dormant_is_listed_as_refused_by_design(self):
        lines = self.build(active=("AdminMap", "Infected"))
        dormant = [l for l in lines if "cmd=dormant" in l][0]
        self.assertIn("available=0", dormant)
        self.assertIn("refused-by-design", dormant)

    def test_the_listing_fits_the_reply_line_cap(self):
        self.assertLessEqual(len(self.build()), 64)


# ---------------------------------------------------------------- menu + docs

class MenuAndDocs(unittest.TestCase):
    def test_menu_builds_cards_for_every_catalog_command(self):
        menu = MENU.read_text()
        catalog = (SCRIPTS / '3_Game/Admin/HCAdminCatalog.c').read_text()
        for command in NEW_COMMANDS:
            self.assertIn('HCAdd("%s"' % command, catalog, command)
        self.assertIn('HCAdminCatalog.Commands()', menu)
        self.assertIn('card.Entry.Id', menu)
        self.assertTrue(LAYOUT.is_file())

    def test_value_commands_validate_digits_before_sending(self):
        menu = MENU.read_text()
        self.assertRegex(menu, r"HCAdminValue")
        self.assertIn("ToInt()", menu)

    def test_doc_documents_every_command_with_its_rpt_line(self):
        text = DOC.read_text()
        for command in OLD_COMMANDS + NEW_COMMANDS:
            self.assertIn("`%s`" % command, text, command)
            self.assertIn("cmd=%s" % command, text, command)
        for heading in ("COT", "Expansion", "checklist"):
            self.assertIn(heading, text, heading)
        for banned in ("snafu", "2646817942", "2291785308", "2792982069"):
            self.assertNotIn(banned, text.lower())

    def test_doc_is_linked_from_the_handbook_index(self):
        self.assertIn("ADMIN_TEST_KIT.md", (ROOT / "docs/README.md").read_text())


if __name__ == "__main__":
    unittest.main()
