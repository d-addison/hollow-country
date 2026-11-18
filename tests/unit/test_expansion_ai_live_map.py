"""Every live eAI unit on the HC admin map and in the debug snapshot (owner request, GitHub #162).

Spec: admins must see all live Expansion AI, including Expansion's own patrols that the HC site
director does not own, as layer "ai-units" (<=128 units per capture, a cursor across captures),
each with faction, group id/size, source (expansion or hc-site), state (patrol/combat) and the
weapon in hands, plus a rate-limited RPT line "[HC XAI] live groups=N units=M expansion=a hc=b".
Plan/tasks: new addon file HCXAILiveMap.c registering two page contributors through the existing
HCDebugSnapshot.HCRegister seam, no new RPC; this test runs the authored Enforce bodies through the
syntax adapter with explicit synthetic eAI scaffolding. Nothing here establishes DayZ behavior;
native compile, a real Expansion patrol and the two-client map check stay pending.
RED: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_expansion_ai_live_map -v
GREEN: same command, recorded in the work report.
"""
from pathlib import Path
from types import SimpleNamespace as N
import re
import unittest

from tests.unit.test_expansion_ai_adapter import A, Authored

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "mods/HollowCountryExpansionAI/scripts/4_World/HCXAILiveMap.c"
LIVE_CLASS = re.compile(r"class HCXAILive\n\{.*?\n\}\n", re.S)


class Id(int):
    def ToString(self): return str(int(self))


class Faction:
    def __init__(self, name): self.name = name
    def Type(self): return N(ToString=lambda: "eAIFaction" + self.name)


class Group:
    def __init__(self, gid, name, faction="Raiders", combat=False):
        self.gid, self.name, self.faction, self.combat, self.members = gid, name, Faction(faction), combat, []
    def GetID(self): return Id(self.gid)
    def GetName(self): return self.name
    def GetFaction(self): return self.faction
    def IsInCombat(self): return self.combat
    def Count(self): return len(self.members)
    def GetMember(self, i): return self.members[i]
    def GetIndex(self, ai): return self.members.index(ai) if ai in self.members else -1


class Unit:
    def __init__(self, group, pos, weapon="", alive=True, npc=False):
        self.group, self.pos, self.weapon, self.alive, self.npc = group, pos, weapon, alive, npc
        if group is not None: group.members.append(self)
    def IsAlive(self): return self.alive
    def GetGroup(self): return self.group
    def GetPosition(self): return self.pos
    def GetEntityInHands(self): return N(GetType=lambda: self.weapon) if self.weapon else None


class Snapshot:
    """Stands in for HCDebugSnapshot.AddPoint; the real per-contributor cap is 64."""
    def __init__(self): self.rows = []
    def AddPoint(self, layer, id, pos, label, detail):
        if len([r for r in self.rows if r.page == self.page]) >= 64: return
        self.rows.append(N(layer=layer, id=id, pos=pos, label=label, detail=detail, page=self.page))
    page = 0


class LiveMapTests(unittest.TestCase):
    def setUp(self):
        source = SOURCE_PATH.read_text()
        self.assertTrue(LIVE_CLASS.search(source), "HCXAILive class missing")
        self.units = A()
        env = dict(A=A, Print=lambda *a: None)
        eai = N(eAI_GetAll=lambda: self.units, Get=lambda i: self.units[i] if 0 <= i < len(self.units) else None,
                Cast=lambda o: o if isinstance(o, Unit) else None)
        env["eAIBase"] = eai
        env["eAINPCBase"] = N(Cast=lambda o: o if o is not None and o.npc else None)
        env["HCXFactions"] = N(Id=lambda f: "")
        from tests.unit.ai_limits_fixture import install
        self.limits = install(env)
        authored = Authored(LIVE_CLASS.search(source).group(0), env)
        live = N(PAGE_POINTS=64, PAGES=2)
        for name in re.findall(r"static \w+ (\w+)\(", LIVE_CLASS.search(source).group(0)):
            setattr(live, name, lambda *a, n=name: authored.call(n, None, *a))
        env["HCXAILive"] = live
        self.authored = authored
        self.live = live

    def owner(self):
        return N(m_Cursor=0, m_Base=0, m_Elapsed=0.0, m_Due=60)

    def capture(self, owner):
        snapshot = Snapshot()
        for page in (0, 1):
            snapshot.page = page
            self.authored.call("Describe", owner, snapshot, page)
        return snapshot.rows

    def test_every_live_unit_has_faction_size_state_source_and_weapon(self):
        site = Group(7, "HC:camp-a", "Locals")
        Unit(site, (100.0, 0.0, 200.0), "M4A1")
        Unit(site, (101.0, 0.0, 201.0), "")
        wild = Group(9, "Patrol_Balota", "Raiders", combat=True)
        Unit(wild, (300.0, 0.0, 400.0), "AKM")
        Unit(wild, (303.0, 0.0, 400.0), "AKM", alive=False)
        Unit(None, (1.0, 0.0, 1.0), "AKM")
        self.units.extend(u for g in (site, wild) for u in g.members)
        rows = self.capture(self.owner())
        by_id = {r.id: r for r in rows}
        self.assertEqual({"ai-units"}, {r.layer for r in rows})
        self.assertEqual(3, len(rows), "dead and ungrouped units are not listed")
        first = by_id["g7:0"]
        self.assertIn("source=hc-site", first.detail)
        self.assertIn("faction=Locals", first.detail)
        self.assertIn("size=2", first.detail)
        self.assertIn("state=patrol", first.detail)
        self.assertIn("weapon=M4A1", first.detail)
        self.assertIn("group=7", first.detail)
        self.assertIn("weapon=none", by_id["g7:1"].detail)
        expansion = by_id["g9:0"]
        self.assertIn("source=expansion", expansion.detail)
        self.assertIn("state=combat", expansion.detail)
        self.assertIn("[expansion]", expansion.label)
        self.assertEqual((300.0, 0.0, 400.0), expansion.pos)

    def test_unknown_faction_type_is_stripped_without_the_provider_helper(self):
        group = Group(3, "Quest", "Passive")
        Unit(group, (5.0, 0.0, 5.0), "")
        self.units.append(group.members[0])
        self.assertIn("faction=Passive", self.capture(self.owner())[0].detail)

    def test_capture_is_capped_at_128_and_a_cursor_reaches_every_unit(self):
        group = Group(1, "Big")
        for index in range(300):
            self.units.append(Unit(group, (float(index), 0.0, 1.0), ""))
        owner = self.owner()
        seen, sizes = set(), []
        for _ in range(4):
            rows = self.capture(owner)
            sizes.append(len(rows))
            self.assertLessEqual(len([r for r in rows if r.page == 0]), 64)
            self.assertLessEqual(len([r for r in rows if r.page == 1]), 64)
            seen.update(r.id for r in rows)
        self.assertEqual([128] * 4, sizes)
        self.assertEqual(300, len(seen), "three captures cover 300 units; the fourth wraps")

    def test_observation_cap_is_independent_of_live_admission_budget(self):
        self.limits.MaxObservedAI = 20
        self.limits.MaxLiveAI = 10
        group = Group(1, "Synthetic-over-budget")
        for index in range(30):
            self.units.append(Unit(group, (float(index), 0.0, 1.0), ""))
        self.assertEqual(20, len(self.capture(self.owner())))

    def test_a_small_population_is_listed_once_per_capture_and_empty_is_quiet(self):
        group = Group(2, "Small")
        for index in range(70):
            self.units.append(Unit(group, (float(index), 0.0, 1.0), ""))
        rows = self.capture(self.owner())
        self.assertEqual(70, len(rows))
        self.assertEqual(70, len({r.id for r in rows}))
        self.units.clear()
        self.assertEqual([], self.capture(self.owner()))

    def test_report_counts_groups_and_units_by_source_and_is_rate_limited(self):
        site = Group(7, "HC:camp-a", "Locals")
        wild = Group(9, "Patrol_Balota")
        for g in (site, wild):
            Unit(g, (1.0, 0.0, 1.0)); Unit(g, (2.0, 0.0, 2.0))
        Unit(wild, (3.0, 0.0, 3.0), alive=False)
        self.units.extend(u for g in (site, wild) for u in g.members)
        owner = self.owner()
        self.assertEqual("", self.authored.call("Report", owner, 30.0))
        self.assertEqual("[HC XAI] live groups=2 units=4 expansion=1 hc=1",
                         self.authored.call("Report", owner, 30.0))
        self.assertEqual("", self.authored.call("Report", owner, 299.0))
        self.assertTrue(self.authored.call("Report", owner, 1.0).startswith("[HC XAI] live groups=2"))

    def test_report_prints_zero_when_no_ai_is_alive(self):
        self.assertEqual("[HC XAI] live groups=0 units=0 expansion=0 hc=0",
                         self.authored.call("Report", self.owner(), 61.0))


class LiveMapSourceTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE_PATH.read_text()

    def test_contributors_register_only_with_the_snapshot_preference_and_unregister(self):
        start = self.source.split("override void OnStart", 1)[1].split("override void OnTick", 1)[0]
        self.assertIn("EnableDebugSnapshot", start)
        self.assertLess(start.index("EnableDebugSnapshot"), start.index("HCRegister"))
        self.assertIn("HCDebugSnapshot.HCUnregister", self.source)
        self.assertIn("Register(new HCXAILiveModule())", self.source)
        self.assertIn('IsEnabled(HCSettings settings) { return true; }', self.source)

    def test_layer_is_distinct_from_the_hc_site_layer_and_no_rpc_is_added(self):
        self.assertIn('AddPoint("ai-units"', self.source)
        patrol = (SOURCE_PATH.parent / "HCXAIPatrolDebug.c").read_text()
        self.assertIn('AddPoint("ai"', patrol)
        self.assertNotRegex(self.source, r"ScriptRPC|RPC\(")


if __name__ == "__main__":
    unittest.main()
