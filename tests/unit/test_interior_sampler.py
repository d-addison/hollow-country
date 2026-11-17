"""Offline interior sampler stager/hook tests; SYNTHETIC fixtures, never DayZ behavior.

Nothing here proves how the engine raycast, the building geometry or the navmesh behave.
The generated Enforce hook is checked against compile-shape rules already observed natively
and its floor/interior/reachability logic is executed line by line (reference transpiler from
test_ce_probe) against a mock scene whose planes and navmesh are REFERENCE models, not DayZ.
"""
import json
import math
from pathlib import Path
import re
import unittest
from unittest import mock

from tests.unit import test_ce_probe as cep
from tools.setup import ce_probe as probe
from tools.setup import diagnostic_mission as dm
from tools.setup import interior_sampler as samp

ROOT = Path(__file__).resolve().parents[2]
NATIVE_CACHE = Path.home() / ".cache/hollow-country/native-scripts/scripts-1.30.164289"


def sampler_counts(extra=12):
    counts = {name: extra for name, _role in samp.SAMPLE_CLASSES}
    counts["Land_Unrelated_Shed"] = 20
    counts["Land_Mil_Barracks1"] = 9
    return counts


def sampler_targets(per_class=4, counts=None):
    placements = probe.parse_placements(cep.pos_xml(counts or sampler_counts()))
    return probe.build_targets(placements, classes=samp.SAMPLE_CLASSES, per_class=per_class)


# ---------------------------------------------------------------------------
# Reference scene. All planes are expressed in the building's model space; the mock raycast converts
# the (always vertical) world rays into that space. Plane kinds exist only for the independent
# expectation; the hook never sees them.
# ---------------------------------------------------------------------------


class Plane:
    def __init__(self, owner, y, x0, x1, z0, z1, kind, dir_y=1.0):
        self.owner, self.y, self.x0, self.x1, self.z0, self.z1, self.kind, self.dir_y = (
            owner, y, x0, x1, z0, z1, kind, dir_y)

    def covers(self, x, z):
        return self.x0 <= x < self.x1 and self.z0 <= z < self.z1


class SampBuilding(cep.MockObject):
    def __init__(self, *args, doors=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.doors = list(doors)

    def CoordToParent(self, local):
        return self.to_world(local)

    def GetOrientation(self):
        return (math.degrees(self.yaw), 0.0, 0.0)

    def GetDoorCount(self):
        return len(self.doors)

    def GetDoorSoundPos(self, index):
        return self.doors[index]


class MockBuildingClass:
    @staticmethod
    def Cast(value):
        return value if isinstance(value, SampBuilding) else None


class Scene:
    def __init__(self, building, planes):
        self.building, self.planes, self.calls = building, planes, []

    def ray(self, beg, end, results, intersect):
        self.calls.append((beg, end, intersect))
        lb, le = self.building.CoordToLocal(beg), self.building.CoordToLocal(end)
        if abs(lb[0] - le[0]) > 1e-6 or abs(lb[2] - le[2]) > 1e-6:
            raise AssertionError("the sampler must cast vertical rays only")
        x, z, down = lb[0], lb[2], le[1] < lb[1]
        best = None
        for plane in self.planes:
            if not plane.covers(x, z):
                continue
            crossed = (le[1] <= plane.y < lb[1]) if down else (lb[1] < plane.y <= le[1])
            if crossed and (best is None or abs(plane.y - lb[1]) < abs(best.y - lb[1])):
                best = plane
        if best is None:
            return False, None, None
        results.Insert(best.owner)
        return True, self.building.to_world((x, best.y, z)), (0.0, best.dir_y, 0.0)


class Zone:
    def __init__(self, comp, x0, x1, z0, z1, y):
        self.comp, self.x0, self.x1, self.z0, self.z1, self.y = comp, x0, x1, z0, z1, y


class NavMesh:
    """Reference navmesh: flat zones, links between components, optional truncated paths."""

    def __init__(self, building, zones, links=(), partial_gap=0.0, tolerance=1.5):
        self.building, self.zones, self.partial_gap, self.tolerance = building, zones, partial_gap, tolerance
        self.links = {frozenset(pair) for pair in links}
        self.samples = self.paths = 0

    def zone_at(self, world, radius):
        local = self.building.CoordToLocal(world)
        best = None
        for zone in self.zones:
            if zone.x0 <= local[0] < zone.x1 and zone.z0 <= local[2] < zone.z1 and abs(local[1] - zone.y) <= radius:
                if best is None or abs(local[1] - zone.y) < abs(local[1] - best.y):
                    best = zone
        return best

    def sample(self, position, radius):
        self.samples += 1
        zone = self.zone_at(position, radius)
        if zone is None:
            return False, None
        local = self.building.CoordToLocal(position)
        return True, self.building.to_world((local[0], zone.y, local[2]))

    def path(self, start, end, waypoints):
        self.paths += 1
        a, b = self.zone_at(start, self.tolerance), self.zone_at(end, self.tolerance)
        if a is None or b is None:
            return False
        if a.comp != b.comp and frozenset((a.comp, b.comp)) not in self.links:
            return False
        stop = end
        if self.partial_gap:
            stop = (end[0] + self.partial_gap, end[1], end[2])
        waypoints.Insert(start)
        waypoints.Insert(stop)
        return True


class MockWorld:
    def __init__(self, nav):
        self.nav = nav

    def GetAIWorld(self):
        return self.nav


class MockQueue:
    def __init__(self):
        self.calls = []

    def CallLater(self, function, delay, repeat):
        self.calls.append((function, delay, repeat))


class RunGame(cep.MockGame):
    def __init__(self, world, nav):
        super().__init__(world)
        self.nav, self.queue, self.clock = nav, MockQueue(), 0

    def GetWorld(self):
        return MockWorld(self.nav)

    def GetTime(self):
        self.clock += 7
        return self.clock

    def GetCallQueue(self, _category):
        return self.queue


class Handle:
    def __init__(self, lines):
        self.lines = lines

    def __bool__(self):
        return True


class SampArray(cep.EArray):
    def Clear(self):
        del self[:]


class MockFiles:
    """In-memory profile files; the hook only ever appends lines and creates a sentinel."""

    class Mode:
        WRITE, APPEND = "write", "append"

    def __init__(self):
        self.files, self.opens = {}, []

    def OpenFile(self, path, mode):
        self.opens.append((path, mode))
        if mode == self.Mode.WRITE:
            self.files[path] = []
        else:
            self.files.setdefault(path, [])
        return Handle(self.files[path])

    @staticmethod
    def FPrintln(handle, line):
        handle.lines.append(str(line))

    @staticmethod
    def CloseFile(_handle):
        return None

    def FileExist(self, path):
        return path in self.files


_MODEL_TYPES = r"(?:int|float|bool|string|vector|Object|ItemBase|CargoBase|Building|FileHandle|array<[^>]+>)"

# Exact hook lines whose out-parameter calls cannot be modelled; each must match exactly once.
MODEL_REWRITES = (
    (r"^( +)set<Object> hitObjects = new set<Object>;$", r"\1array<Object> hitObjects = new array<Object>;"),
    (r"^( +)bool hit = DayZPhysics\.RaycastRV\(rayFrom, rayTo, contactPos, contactDir, contactComponent, hitObjects, "
     r"null, null, false, false, (ObjIntersect\w+)\);$",
     r"\1hit, contactPos, contactDir = HCMockRay(rayFrom, rayTo, hitObjects, '\2');"),
    (r"^( +)bool found = GetGame\(\)\.GetWorld\(\)\.GetAIWorld\(\)\.SampleNavmeshPosition\(position, radius, "
     r"m_HCProbeFilter, sampled\);$", r"\1found, sampled = HCMockSample(position, radius);"),
    (r"^( +)TVectorArray waypoints = new TVectorArray;$", r"\1array<vector> waypoints = new array<vector>;"),
    (r"^( +)bool found = GetGame\(\)\.GetWorld\(\)\.GetAIWorld\(\)\.FindPath\(startPos, endPos, m_HCProbeFilter, "
     r"waypoints\);$", r"\1found = HCMockPath(startPos, endPos, waypoints);"),
)

MODELLED = ("HCProbeKey", "HCProbeStr", "HCProbeBool", "HCProbeVector", "HCProbeBoxUsable", "HCProbeCount",
            "HCProbeRay", "HCProbeClearance", "HCProbeEmit", "HCProbeFlush", "HCProbeHeader",
            "HCProbeBeginBuilding", "HCProbeScanRow", "HCProbeScanColumn", "HCProbeRecordFloor",
            "HCProbeEndBuilding", "HCProbeMeshAvailable", "HCProbeSampleMesh", "HCProbePath",
            "HCProbeReachSetup", "HCProbeReachHit", "HCProbeStep", "HCProbeFinish")
_MEMBER = re.compile(r"^    protected (?:ref )?([\w<>]+) (m_HCProbe\w+)(?: = (.+))?;$", re.M)


def rewrite_for_model(text):
    for pattern, replacement in MODEL_REWRITES:
        text, count = re.subn(pattern, replacement, text, flags=re.M)
        if count != 1:
            raise ValueError("model rewrite did not match exactly once: " + pattern[:60])
    return text


class HookRun:
    """Drive the transpiled hook over one mock building and return the written census."""

    def __init__(self, hook_text, building, planes, nav=None, extra_world=(), ai=True, overrides=None):
        self.text = rewrite_for_model(hook_text)
        self.building, self.scene = building, Scene(building, planes)
        self.nav = nav
        self.files = MockFiles()
        self.game = RunGame([building, *extra_world], nav if ai else None)
        self.prints = []
        namespace = {
            "S": cep.S, "EArray": SampArray, "ItemBase": cep.MockItemBase, "Math": cep.MockMath,
            "vector": cep.MockVector, "Vector": lambda x, y, z: (x, y, z), "GetGame": lambda: self.game,
            "FLT_MAX": cep.FLT_MAX_VALUE, "Building": MockBuildingClass, "FileMode": MockFiles.Mode,
            "OpenFile": self.files.OpenFile, "FPrintln": self.files.FPrintln, "CloseFile": self.files.CloseFile,
            "FileExist": self.files.FileExist, "Print": self.prints.append, "CALL_CATEGORY_SYSTEM": 0,
            "HCProbeStep": None, "HCMockRay": self.scene.ray,
            "HCMockSample": (nav.sample if nav else (lambda p, r: (False, None))),
            "HCMockPath": (nav.path if nav else (lambda a, b, w: False)),
        }
        with mock.patch.object(cep, "_TYPE", _MODEL_TYPES):
            source = cep.enforce_to_python(self.text, MODELLED)
        exec(compile(source, "<generated-sampler>", "exec"), namespace)
        self.model = namespace["HookModel"]()
        for _type, name, value in _MEMBER.findall(self.text):
            setattr(self.model, name, eval(cep._enforce_expression(value), namespace) if value else None)
        self.model.m_HCProbeQuote = cep.S('"')
        self.model.m_HCProbeFilter = object()
        for name, value in (overrides or {}).items():
            setattr(self.model, name, value)
        self.model.m_HCProbeClasses.Insert(cep.S(building.type_name))
        self.model.m_HCProbeRoles.Insert(cep.S("tenement"))
        self.model.m_HCProbePositions.Insert(building.pos)

    def run(self, limit=200000):
        self.model.HCProbeHeader(cep.S("chernarusplus"), cep.S("1.30.test"))
        for _ in range(limit):
            self.model.HCProbeStep()
            if self.sentinel() is not None:
                return self
        raise AssertionError("sampler model did not finish")

    def census_path(self):
        return str(self.model.m_HCProbePath)

    def sentinel(self):
        return next((lines for path, lines in self.files.files.items() if path.endswith("complete.txt")), None)

    def census(self):
        return json.loads("\n".join(self.files.files[self.census_path()]))

    def row(self):
        return self.census()["placements"][0]


TERRAIN = object()
CRATE = object()
LAMP = object()
BOX = ((-5.0, -1.0, -4.0), (7.0, 9.0, 3.0))


def storey_building(yaw=0.6, doors=True):
    b = SampBuilding("Land_Tenement_Small", (3000.0, 20.0, 5000.0), yaw=yaw, clip=BOX)
    if doors:
        b.doors = [b.to_world((-4.9, 1.0, -0.5))]
    return b


def storey_planes(building):
    """Two storeys in region A, one storey in B1/B2, a low ceiling in C, an 8 m hall in D."""
    def plane(owner, y, x0, x1, z0, z1, kind, dir_y=1.0):
        return Plane(owner, y, x0, x1, z0, z1, kind, dir_y)
    b = building
    return [
        plane(TERRAIN, -0.5, -50, 50, -50, 50, "terrain"),
        plane(b, 0.0, -4, 6, -3, 2, "floor"), plane(b, -0.1, -4, 6, -3, 2, "under"),
        plane(b, 3.0, -4, 0, -3, 2, "floor"), plane(b, 2.8, -4, 0, -3, 2, "under"),
        plane(b, 5.8, -4, 0, -3, 2, "under"), plane(b, 6.0, -4, 0, -3, 2, "roof"),
        plane(b, 2.5, 0, 2, -3, 2, "under"), plane(b, 2.7, 0, 2, -3, 2, "roof"),
        plane(b, 2.5, 4, 6, -3, 2, "under"), plane(b, 2.7, 4, 6, -3, 2, "roof"),
        plane(b, 1.5, 4, 5, -3, -2, "floor"),
        plane(b, 8.0, 2, 4, -3, 2, "under"), plane(b, 8.2, 2, 4, -3, 2, "roof"),
        plane(CRATE, 1.0, -2, -1, -1, 0, "other"), plane(LAMP, 2.0, 1, 2, 0, 1, "other"),
    ]


def grid_centres(low, high):
    values, edge = [], low + 0.5
    while edge < high:
        values.append(edge)
        edge += 1.0
    return values


def expected_floor_records(building, planes, box=BOX):
    """Independent derivation from plane kinds: floors with a building plane 0.05..6.0 m above."""
    owned = [p for p in planes if p.owner is building]
    expected = set()
    for x in grid_centres(box[0][0], box[1][0]):
        for z in grid_centres(box[0][2], box[1][2]):
            column = [p for p in owned if p.covers(x, z)]
            for floor in (p for p in column if p.kind == "floor"):
                above = [p.y - floor.y for p in column if floor.y + 0.05 < p.y <= floor.y + 6.0 + 1e-9]
                if above:
                    expected.add((round(x, 2), round(z, 2), round(floor.y, 2), round(min(above), 2)))
    return expected


def recorded(row):
    return {(round(h[0], 2), round(h[2], 2), round(h[1], 2), round(h[3], 2)) for h in row["hits"]}


def default_hook(**kwargs):
    return samp.render_hook(sampler_targets(), **kwargs).decode()


def nav_for(building, **kwargs):
    zones = [
        Zone("out", -30, -5, -30, 30, 0.0),
        Zone("locked", -4, -2, 1, 2, 0.0), Zone("g", -5, 5, -4, 3, 0.0), Zone("g", 5, 7, -2, 3, 0.0),
        Zone("up", -4, 0, -3, 2, 3.0),
    ]
    return NavMesh(building, zones, links=[("out", "g")], **kwargs)


def battery(hook_text):
    """Names of failed reference scenarios; an exception in the model counts as a failure."""
    failures = []

    def check(name, function):
        try:
            if not function():
                failures.append(name)
        except Exception as error:  # noqa: BLE001 - a model failure is a detected mismatch
            failures.append("%s:%s" % (name, type(error).__name__))

    def floors():
        building = storey_building()
        planes = storey_planes(building)
        row = HookRun(hook_text, building, planes, ai=False).run().row()
        return recorded(row) == expected_floor_records(building, planes) and len(row["hits"]) == len(recorded(row))

    def rotation():
        results = []
        for yaw in (0.0, 1.9):
            building = storey_building(yaw=yaw)
            results.append(recorded(HookRun(hook_text, building, storey_planes(building), ai=False).run().row()))
        return results[0] == results[1] and bool(results[0])

    def grid():
        building = storey_building()
        row = HookRun(hook_text, building, storey_planes(building), ai=False).run().row()
        odd = SampBuilding("Land_Tenement_Small", (3000.0, 20.0, 5000.0), clip=((-5.0, -0.5, -4.0), (6.4, 7.0, 3.0)))
        odd_row = HookRun(hook_text, odd, [], ai=False).run().row()
        return (row["grid"] == {"step": 1.0, "rows": 12, "cols": 7}
                and row["stats"]["columns"] == 84 and all(round(h[0] + 4.5, 6) % 1.0 == 0 for h in row["hits"])
                and odd_row["grid"] == {"step": 1.0, "rows": 11, "cols": 7})

    def reach():
        building = storey_building()
        planes = storey_planes(building)
        nav = nav_for(building)
        row = HookRun(hook_text, building, planes, nav=nav).run().row()
        codes = {(round(h[0], 1), round(h[2], 1), round(h[1], 1)): h[5] for h in row["hits"]}
        want = {(-3.5, 1.5, 0.0): 0, (-2.5, 1.5, 0.0): 0, (-3.5, 0.5, 0.0): 1, (0.5, -2.5, 0.0): 1,
                (5.5, -2.5, 0.0): 2, (-3.5, -2.5, 3.0): 0, (-3.5, -2.5, 0.0): 1}
        entrances = row["reach"]["entrances"]
        return (row["reach"]["state"] == "tested" and len(entrances) == 1 and entrances[0][0] < -5.0
                and all(codes.get(k) == v for k, v in want.items()))

    def partial_path():
        building = storey_building()
        nav = nav_for(building, partial_gap=3.0)
        row = HookRun(hook_text, building, storey_planes(building), nav=nav).run().row()
        return row["reach"]["state"] == "control-failed" and all(h[5] == -1 for h in row["hits"])

    def altitude():
        building = storey_building()
        planes = storey_planes(building)
        zones = [Zone("out", -30, -5, -30, 30, 0.0), Zone("deck", -5, 7, -4, 3, 1.2)]
        nav = NavMesh(building, zones, links=[("out", "deck")])      # mesh 1.2 m above the sampled floor
        row = HookRun(hook_text, building, planes, nav=nav).run().row()
        codes = {(round(h[0], 1), round(h[2], 1), round(h[1], 1)): h[5] for h in row["hits"]}
        return codes.get((0.5, 0.5, 0.0)) == 2 and row["reach"]["state"] == "tested"

    def budgets():
        building = storey_building()
        planes = storey_planes(building)
        run = HookRun(hook_text, building, planes, ai=False, overrides={"m_HCProbeBuildingRayLimit": 300}).run()
        row = run.row()
        return row["stats"]["ray_capped"] is True and row["stats"]["rays"] <= 300 and len(run.scene.calls) <= 300

    def run_budget():
        building = storey_building()
        run = HookRun(hook_text, building, storey_planes(building), ai=False, overrides={"m_HCProbeRunRayLimit": 200}).run()
        return run.row()["stats"]["rays"] <= 200 and run.row()["stats"]["ray_capped"] is True

    def hit_limit():
        building = SampBuilding("Land_Tenement_Big", (10.0, 5.0, 10.0), clip=((-2.0, 0.0, -2.0), (2.0, 40.0, 2.0)))
        planes = [Plane(building, 3.0 * k, -5, 5, -5, 5, "floor") for k in range(14)]
        planes += [Plane(building, 3.0 * k + 2.8, -5, 5, -5, 5, "under") for k in range(14)]
        row = HookRun(hook_text, building, planes, ai=False, overrides={"m_HCProbeHitLimit": 6}).run().row()
        return len(row["hits"]) == 48 and row["stats"]["hit_capped_columns"] == 16

    def reach_states():
        building = storey_building()
        planes = storey_planes(building)
        if HookRun(hook_text, building, planes, nav=nav_for(building), ai=False).run().row()["reach"]["state"] != "unavailable":
            return False
        bare = storey_building(doors=False)
        if HookRun(hook_text, bare, storey_planes(bare), nav=nav_for(bare)).run().row()["reach"]["state"] != "no-door":
            return False
        row = HookRun(hook_text, building, planes, nav=nav_for(building),
                      overrides={"m_HCProbePathLimit": 3}).run().row()
        tested = [h for h in row["hits"] if h[3] >= 1.9 and h[5] != -1]
        return (row["reach"]["state"] == "tested" and len(tested) == 2 and row["stats"]["paths"] == 3
                and all(h[5] == -1 for h in row["hits"] if h[3] < 1.9))

    def other_objects():
        building = storey_building()
        planes = storey_planes(building)
        row = HookRun(hook_text, building, planes, ai=False).run().row()
        by = {(round(h[0], 1), round(h[2], 1), round(h[1], 1)): h for h in row["hits"]}
        return (-1.5, -0.5, 0.0) in by and (-1.5, -0.5, 1.0) not in by and by[(1.5, 0.5, 0.0)][3] == 2.5

    for name, function in (("floors", floors), ("rotation", rotation), ("grid", grid), ("reach", reach),
                           ("partial-path", partial_path), ("altitude", altitude), ("budgets", budgets),
                           ("run-budget", run_budget), ("hit-limit", hit_limit), ("reach-states", reach_states),
                           ("other-objects", other_objects)):
        check(name, function)
    return failures


MUTATIONS = (
    ("hits on other objects accepted as the building", "if (hitObjects.Find(m_HCProbeBuilding) == -1)", "if (false)"),
    ("miss treated as a hit", "        if (!hit)\n            return 0;", "        if (hit)\n            return 0;"),
    ("same-slab spacing removed", "if (lastY - hitY < 0.25)", "if (lastY - hitY < -1.0)"),
    ("restart goes above the hit", "hitY - 0.05", "hitY + 0.05"),
    ("exterior hits kept", "if (clearance < 0.0)", "if (false)"),
    ("clearance measured from the box", "return hitY - surfacePos[1];", "return hitY;"),
    ("upward ray starts below the surface", "surfacePos[1] + 0.05", "surfacePos[1] - 0.05"),
    ("upward range widened", "surfacePos[1] + 6.0", "surfacePos[1] + 60.0"),
    ("upward non-building hit ends the search", "if (result == 1)\n                return hitY - surfacePos[1];",
     "if (true)\n                return hitY - surfacePos[1];"),
    ("other-object hits become floors", "if (result == 2)", "if (result == 99)"),
    ("grid step doubled", "edge = edge + m_HCProbeGridStep;", "edge = edge + 2.0;"),
    ("grid origin moved to the edge", "float edge = low + 0.5;", "float edge = low;"),
    ("hit limit removed", "step < m_HCProbeHitLimit", "step < 99"),
    ("building ray cap removed", "m_HCProbeBuildingRays >= m_HCProbeBuildingRayLimit ||",
     "m_HCProbeBuildingRays >= 99999999 ||"),
    ("run ray cap removed", "|| m_HCProbeRunRays >= m_HCProbeRunRayLimit", "|| m_HCProbeRunRays >= 99999999"),
    ("model coordinates dropped", "m_HCProbeBuilding.CoordToLocal(floorPos)", "floorPos"),
    ("path end gap widened", "gap <= 2.0", "gap <= 200.0"),
    ("mesh altitude check widened", "> 0.75)", "> 75.0)"),
    ("reach computed without control", 'if (m_HCProbeReachState != "tested")', "if (false)"),
    ("control failure ignored", "if (HCProbePath(entranceSampled, m_HCProbeSampled) < 1)", "if (false)"),
    ("path budget removed", "if (m_HCProbeBuildingPaths >= m_HCProbePathLimit)", "if (false)"),
    ("comma separation removed", "if (m_HCProbeHitsEmitted > 0)", "if (false)"),
    ("outside point inside the building", "doorPos[0] + unitX * 2.0", "doorPos[0] - unitX * 2.0"),
)


class RenderTests(unittest.TestCase):
    def test_every_target_and_limit_is_inlined_as_literal_data(self):
        targets = sampler_targets()
        text = samp.render_hook(targets, sample_delay_s=75, run_ray_limit=123456, building_ray_limit=23456,
                                hit_limit=7).decode()
        for target in targets:
            self.assertIn('HCProbeAdd("%s", "%s", %.6f, %.6f, %.6f);' % (target["class"], target["role"], *target["pos"]),
                          text)
        for needle in ("= 123456;", "= 23456;", "= 7;", "CallLater(HCProbeStart, 75000, false)"):
            self.assertIn(needle, text)
        self.assertNotIn("@@", text)

    def test_hook_is_ascii_bounded_and_overrides_only_oninit_of_the_disposable_mission(self):
        raw = samp.render_hook(sampler_targets())
        self.assertTrue(raw.isascii())
        self.assertLess(len(raw), dm.MAX_HOOK_BYTES)
        text = raw.decode()
        self.assertEqual(1, text.count("class HCDisposableDiagnosticMission : CustomMission"))
        self.assertEqual(1, len(re.findall(r"\boverride\b", text)))
        self.assertIn("override void OnInit()", text)
        self.assertIn("super.OnInit();", text)

    def test_hook_passes_the_observed_compile_shape_rules_and_the_sampler_extras(self):
        text = default_hook()
        self.assertEqual([], samp.lint_sampler_hook(text))
        if NATIVE_CACHE.is_dir():
            self.assertEqual([], samp.lint_sampler_hook(text, native_types=probe.native_type_names(NATIVE_CACHE)))

    def test_extra_lint_rejects_else_unseeded_out_arguments_and_leading_operators(self):
        base = default_hook()
        self.assertNotEqual([], samp.lint_sampler_hook(base.replace("        vector contactPos;\n", "", 1)))
        self.assertNotEqual([], samp.lint_sampler_hook(base.replace("        int contactComponent;\n", "", 1)))
        self.assertNotEqual([], samp.lint_sampler_hook(base.replace("return 2;\n        return 1;", "return 2;\n        else\n            return 1;", 1)))
        self.assertNotEqual([], samp.lint_sampler_hook(base + "\n    void Bad()\n    {\n        int a = true ? 1 : 2;\n    }\n"))

    def test_hook_only_observes_the_world(self):
        text = default_hook()
        for forbidden in (r"\bSetPosition\b", r"\bCreateObject", r"\bSpawn", r"\bDelete\b", r"\bSetOrientation\b",
                          r"\bTeleport", r"\bSetHealth\b", r"\bOpenDoor", r"\bGetCEApi\b", r"\bExport"):
            self.assertIsNone(re.search(forbidden, text), forbidden)

    def test_native_calls_match_the_observed_prototypes_in_the_installed_scripts(self):
        text = default_hook()
        self.assertEqual(1, text.count("DayZPhysics.RaycastRV("))
        self.assertIn("null, null, false, false, ObjIntersectGeom);", text)
        for call in ("GetGame().GetWorld().GetAIWorld().SampleNavmeshPosition(", "GetGame().GetWorld().GetAIWorld().FindPath(",
                     "m_HCProbeBuilding.GetDoorSoundPos(door)", "m_HCProbeBuilding.GetDoorCount()", "m_HCProbeBuilding.ClippingInfo(clip)",
                     "m_HCProbeBuilding.CoordToParent(", "m_HCProbeBuilding.CoordToLocal(", "m_HCProbeFilter.SetFlags(PGPolyFlags.WALK | PGPolyFlags.DOOR | PGPolyFlags.INSIDE"):
            self.assertIn(call, text)
        self.assertIn("$profile:HCCEProbe/census.json", text)
        self.assertIn("$profile:HCCEProbe/complete.txt", text)

    def test_intersect_type_is_selectable_and_validated(self):
        for name, constant in (("geom", "ObjIntersectGeom"), ("view", "ObjIntersectView"), ("fire", "ObjIntersectFire"),
                               ("ifire", "ObjIntersectIFire")):
            self.assertIn("null, null, false, false, %s);" % constant, default_hook(intersect=name))
        with self.assertRaises(ValueError):
            default_hook(intersect="none")

    def test_bad_inputs_are_refused(self):
        good = sampler_targets()
        for kwargs in ({"sample_delay_s": 1}, {"sample_delay_s": 99999}, {"hit_limit": 0}, {"hit_limit": 65},
                       {"building_ray_limit": 10}, {"building_ray_limit": 10 ** 8}, {"run_ray_limit": 10},
                       {"path_limit": -1}, {"output_limit": 10}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                samp.render_hook(good, **kwargs)
        for targets in ([], [dict(good[0], **{"class": "Bad Name"})], [dict(good[0], role="UPPER")],
                        [dict(good[0], pos=[float("nan"), 0.0, 0.0])], good * 20):
            with self.subTest(targets=str(targets)[:40]), self.assertRaises(ValueError):
                samp.render_hook(targets)

    def test_classes_are_the_two_tenements_plus_the_two_calibration_buildings(self):
        self.assertEqual({"Land_Tenement_Small": "tenement", "Land_Tenement_Big": "tenement",
                          "Land_HouseBlock_2F1": "calibration", "Land_Mil_Barracks2": "calibration"},
                         dict(samp.SAMPLE_CLASSES))
        self.assertEqual(4, samp.DEFAULT_PER_CLASS)
        self.assertEqual(16, len(sampler_targets()))
        self.assertEqual(1.0, samp.GRID_STEP)


class ModelBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.hook = default_hook()

    def test_generated_logic_matches_the_independent_reference_scenarios(self):
        self.assertEqual([], battery(self.hook))

    def test_every_mutated_condition_is_detected(self):
        for label, old, new in MUTATIONS:
            with self.subTest(label):
                self.assertEqual(1, self.hook.count(old), "mutation anchor must be unique")
                self.assertNotEqual([], battery(self.hook.replace(old, new, 1)))

    def test_only_interior_floor_surfaces_of_the_building_itself_are_recorded(self):
        building = storey_building()
        planes = storey_planes(building)
        row = HookRun(self.hook, building, planes, ai=False).run().row()
        self.assertEqual(expected_floor_records(building, planes), recorded(row))
        self.assertGreater(len(row["hits"]), 40)
        storeys = {round(h[1], 1) for h in row["hits"]}
        self.assertEqual({0.0, 1.5, 3.0}, storeys)
        stats = row["stats"]
        self.assertGreater(stats["exterior_hits"], 0)
        self.assertGreater(stats["other_hits"], 0)
        self.assertEqual(len(row["hits"]), stats["interior_hits"])

    def test_clearance_is_the_free_height_to_the_first_building_surface_above(self):
        building = storey_building()
        row = HookRun(self.hook, building, storey_planes(building), ai=False).run().row()
        clearance = {(round(h[0], 1), round(h[2], 1), round(h[1], 1)): h[3] for h in row["hits"]}
        self.assertAlmostEqual(2.8, clearance[(-3.5, 0.5, 0.0)], places=3)
        self.assertAlmostEqual(2.8, clearance[(-3.5, 0.5, 3.0)], places=3)
        self.assertAlmostEqual(2.5, clearance[(0.5, 0.5, 0.0)], places=3)
        self.assertAlmostEqual(1.5, clearance[(4.5, -2.5, 0.0)], places=3)
        self.assertNotIn((2.5, 0.5, 0.0), clearance)       # 8 m hall: no building surface within 6 m

    def test_a_hanging_object_above_the_floor_does_not_end_the_clearance_search(self):
        building = storey_building()
        row = HookRun(self.hook, building, storey_planes(building), ai=False).run().row()
        by = {(round(h[0], 1), round(h[2], 1), round(h[1], 1)): h for h in row["hits"]}
        self.assertAlmostEqual(2.5, by[(1.5, 0.5, 0.0)][3], places=3)

    def test_a_thick_slab_underside_is_recorded_with_its_small_clearance(self):
        building = SampBuilding("Land_Tenement_Big", (10.0, 5.0, 10.0), clip=((-2.0, -1.0, -2.0), (2.0, 8.0, 2.0)))
        planes = [Plane(building, 0.0, -5, 5, -5, 5, "floor"), Plane(building, 2.6, -5, 5, -5, 5, "under"),
                  Plane(building, 3.0, -5, 5, -5, 5, "floor"), Plane(building, 6.0, -5, 5, -5, 5, "under")]
        row = HookRun(self.hook, building, planes, ai=False).run().row()
        column = sorted((round(h[1], 2), round(h[3], 2)) for h in row["hits"] if round(h[0], 1) == -1.5
                        and round(h[2], 1) == -1.5)
        self.assertEqual([(0.0, 2.6), (2.6, 0.4), (3.0, 3.0)], column)

    def test_the_grid_is_one_metre_in_model_space_and_rotation_does_not_change_it(self):
        records = []
        for yaw in (0.0, 0.6, 2.4):
            building = storey_building(yaw=yaw)
            row = HookRun(self.hook, building, storey_planes(building), ai=False).run().row()
            self.assertEqual({"step": 1.0, "rows": 12, "cols": 7}, row["grid"])
            self.assertEqual(84, row["stats"]["columns"])
            records.append(recorded(row))
        self.assertEqual(records[0], records[1])
        self.assertEqual(records[0], records[2])

    def test_rays_are_vertical_and_use_the_selected_intersect_type(self):
        for name, constant in (("geom", "ObjIntersectGeom"), ("view", "ObjIntersectView")):
            building = storey_building()
            run = HookRun(default_hook(intersect=name), building, storey_planes(building), ai=False).run()
            self.assertGreater(len(run.scene.calls), 100)
            self.assertEqual({constant}, {call[2] for call in run.scene.calls})

    def test_raw_engine_direction_y_is_recorded_without_being_interpreted(self):
        building = storey_building()
        planes = storey_planes(building)
        for plane in planes:
            plane.dir_y = 0.37
        row = HookRun(self.hook, building, planes, ai=False).run().row()
        self.assertEqual({0.37}, {round(h[4], 2) for h in row["hits"]})

    def test_budgets_cap_work_flag_the_row_and_keep_the_json_valid(self):
        building = storey_building()
        run = HookRun(self.hook, building, storey_planes(building), ai=False,
                      overrides={"m_HCProbeBuildingRayLimit": 300}).run()
        stats = run.row()["stats"]
        self.assertTrue(stats["ray_capped"])
        self.assertLessEqual(stats["rays"], 300)
        self.assertLessEqual(len(run.scene.calls), 300)
        self.assertTrue(run.census()["summary"]["complete"])

    def test_output_cap_drops_hits_flags_the_row_and_the_file_stays_valid_json(self):
        building = storey_building()
        run = HookRun(self.hook, building, storey_planes(building), ai=False,
                      overrides={"m_HCProbeOutputLimit": 1500}).run()
        row = run.row()
        self.assertTrue(row["stats"]["output_capped"])
        self.assertLess(len(row["hits"]), len(expected_floor_records(building, storey_planes(building))))
        self.assertTrue(run.census()["summary"]["complete"])

    def test_reachability_is_tested_from_outside_the_door_with_a_working_control(self):
        building = storey_building()
        planes = storey_planes(building)
        nav = nav_for(building)
        row = HookRun(self.hook, building, planes, nav=nav).run().row()
        self.assertEqual("tested", row["reach"]["state"])
        self.assertEqual(1, len(row["reach"]["entrances"]))
        self.assertLess(row["reach"]["entrances"][0][0], BOX[0][0])      # outside the box, model space
        codes = {(round(h[0], 1), round(h[2], 1), round(h[1], 1)): h[5] for h in row["hits"]}
        self.assertEqual(1, codes[(-3.5, 0.5, 0.0)])         # connected ground floor
        self.assertEqual(0, codes[(-3.5, 1.5, 0.0)])         # walled-off room
        self.assertEqual(0, codes[(-3.5, -2.5, 3.0)])        # upstairs, no stairs in the navmesh
        self.assertEqual(2, codes[(5.5, -2.5, 0.0)])         # no navmesh under the point
        self.assertGreater(nav.paths, 0)

    def test_a_failing_control_path_or_missing_door_or_missing_navmesh_leaves_reachability_unknown(self):
        building = storey_building()
        planes = storey_planes(building)
        cases = (("control-failed", nav_for(building, partial_gap=3.0), building, True),
                 ("unavailable", nav_for(building), building, False))
        for state, nav, target, ai in cases:
            with self.subTest(state):
                row = HookRun(self.hook, target, planes, nav=nav, ai=ai).run().row()
                self.assertEqual(state, row["reach"]["state"])
                self.assertEqual({-1}, {h[5] for h in row["hits"]})
        bare = storey_building(doors=False)
        row = HookRun(self.hook, bare, storey_planes(bare), nav=nav_for(bare)).run().row()
        self.assertEqual("no-door", row["reach"]["state"])
        self.assertEqual({-1}, {h[5] for h in row["hits"]})

    def test_path_budget_marks_the_remaining_candidates_untested(self):
        building = storey_building()
        row = HookRun(self.hook, building, storey_planes(building), nav=nav_for(building),
                      overrides={"m_HCProbePathLimit": 6}).run().row()
        roofed = [h for h in row["hits"] if h[3] >= 1.9]
        self.assertEqual(5, len([h for h in roofed if h[5] != -1]))       # limit 6 minus the control path
        self.assertGreater(len([h for h in roofed if h[5] == -1]), 10)
        self.assertEqual(6, row["stats"]["paths"])
        self.assertTrue(all(h[5] == -1 for h in row["hits"] if h[3] < 1.9))

    def test_door_positions_are_recorded_in_model_space_for_validation(self):
        building = storey_building()
        row = HookRun(self.hook, building, storey_planes(building), nav=nav_for(building)).run().row()
        door = row["reach"]["doors"][0]
        self.assertAlmostEqual(-4.9, door[0], places=3)
        self.assertAlmostEqual(-0.5, door[2], places=3)

    def test_missing_building_and_unusable_box_rows_are_explicit_not_silent(self):
        building = storey_building()
        far = cep.MockObject("Land_Other", (3000.0, 20.0, 5000.0))
        run = HookRun(self.hook, far, [], ai=False)
        run.model.m_HCProbeClasses[0] = cep.S("Land_Tenement_Small")
        row = run.run().row()
        self.assertFalse(row["found"])
        self.assertEqual([], row["hits"])
        flat = SampBuilding("Land_Tenement_Small", (3000.0, 20.0, 5000.0), clip=((0, 0, 0), (0, 0, 0)))
        row = HookRun(self.hook, flat, [], ai=False).run().row()
        self.assertTrue(row["found"])
        self.assertEqual("none", row["box_source"])
        self.assertEqual([], row["hits"])
        self.assertEqual(building.type_name, "Land_Tenement_Small")

    def test_nearest_building_of_the_expected_class_is_sampled(self):
        near = storey_building()
        wrong = SampBuilding("Land_Other", (3000.0, 20.0, 5000.2), clip=BOX)
        farther = SampBuilding("Land_Tenement_Small", (3000.0, 20.0, 5003.0), clip=BOX)
        run = HookRun(self.hook, near, storey_planes(near), ai=False, extra_world=[wrong, farther])
        row = run.run().row()
        self.assertEqual([3000.0, 20.0, 5000.0], row["actual"])
        self.assertAlmostEqual(0.0, row["distance"], places=6)

    def test_census_is_one_valid_json_document_with_a_sentinel_after_the_final_write(self):
        building = storey_building()
        run = HookRun(self.hook, building, storey_planes(building), ai=False).run()
        census = run.census()
        self.assertEqual("interior-sampler-census", census["kind"])
        self.assertEqual(1, census["summary"]["targets"])
        self.assertEqual(1, census["summary"]["found"])
        self.assertTrue(census["summary"]["complete"])
        self.assertEqual(["rows=1 found=1"], run.sentinel())
        self.assertGreater(census["summary"]["run_rays"], 0)
        modes = [mode for _path, mode in run.files.opens if _path == run.census_path()]
        self.assertEqual("append", modes[-1])

    def test_work_is_split_into_row_sized_steps_that_reschedule_themselves(self):
        building = storey_building()
        run = HookRun(self.hook, building, storey_planes(building), ai=False)
        run.model.HCProbeHeader(cep.S("w"), cep.S("v"))
        run.model.HCProbeStep()                 # begin building
        self.assertEqual(0, run.model.m_HCProbeRunRays)
        run.model.HCProbeStep()                 # first grid row only
        first_row_rays = run.model.m_HCProbeRunRays
        self.assertEqual(1, run.model.m_HCProbeRow)
        self.assertGreater(first_row_rays, 0)
        self.assertLess(first_row_rays, 200)
        self.assertEqual(2, len(run.game.queue.calls))
        self.assertEqual({100}, {call[1] for call in run.game.queue.calls})


class SamplerWorkspace(cep.Workspace):
    def setUp(self):
        super().setUp()
        self.source = cep.make_source_runtime(self.root / "vanilla-s", counts=sampler_counts())

    def stage(self, **extra):
        return samp.stage(self.source, self.dest, **self.kw(**extra))


class StagerTests(SamplerWorkspace):
    MISSION = "mpmissions/dayzOffline.chernarusplus/"

    def test_stage_builds_the_runtime_with_k_placements_per_class_and_a_launcher_compatible_plan(self):
        plan = self.stage()
        self.assertEqual("ce-probe", plan["kind"])
        self.assertEqual("staged-only-not-launched", plan["status"])
        self.assertEqual("control", plan["variant"])
        self.assertEqual(16, plan["probe"]["target_count"])
        self.assertEqual({name: 4 for name, _role in samp.SAMPLE_CLASSES},
                         {entry["class"]: entry["sampled"] for entry in plan["target_classes"]})
        self.assertEqual("profiles/HCCEProbe/census.json", plan["probe"]["census_relative_path"])
        self.assertEqual("profiles/HCCEProbe/complete.txt", plan["probe"]["sentinel_relative_path"])
        self.assertEqual("interior-sampler", plan["probe"]["tool"])
        self.assertEqual({"grid_step": 1.0, "per_class": 4, "intersect": "geom"},
                         {k: plan["sampler"][k] for k in ("grid_step", "per_class", "intersect")})
        self.assertEqual(plan, json.loads((self.dest / "ce-probe-plan.json").read_text()))
        for name in ("storage", "profiles"):
            self.assertEqual([], list((self.dest / name).iterdir()))
        expected = probe.select_placements(probe.parse_placements(
            (self.source / "stock-backup/mpmissions/dayzOffline.chernarusplus/mapgrouppos.xml").read_bytes(),
            wanted={"Land_Tenement_Small"})["Land_Tenement_Small"], 4)
        staged = [tuple(t["pos"]) for t in plan["targets"] if t["class"] == "Land_Tenement_Small"]
        self.assertEqual(sorted(expected), sorted(staged))

    def test_only_init_c_differs_from_the_stock_mission_and_the_hook_hash_is_recorded(self):
        plan = self.stage()
        stock = self.source / "stock-backup/mpmissions/dayzOffline.chernarusplus"
        staged = self.dest / "mpmissions/dayzOffline.chernarusplus"
        for relative in ("mapgroupproto.xml", "mapgrouppos.xml", "db/types.xml", "db/messages.xml"):
            self.assertEqual((stock / relative).read_bytes(), (staged / relative).read_bytes(), relative)
        init = (staged / "init.c").read_bytes()
        self.assertIn(b"return new HCDisposableDiagnosticMission();", init)
        tail = init[init.index(b"\n\n// Hollow Country DISPOSABLE"):]
        self.assertEqual(plan["probe"]["hook_sha256"], cep.sha(tail))
        self.assertEqual(plan["probe"]["hook_bytes"], len(tail))
        self.assertIn(b"interior floor sampler", tail)
        for entry in plan["staged_files"]:
            data = (self.dest / entry["path"]).read_bytes()
            self.assertEqual((cep.sha(data), len(data)), (entry["sha256"], entry["bytes"]), entry["path"])

    def test_the_confinement_and_allowlist_checks_of_the_probe_stager_apply(self):
        for bad in (self.root / "elsewhere" / "ce-probe-test", self.source / "child"):
            with self.subTest(bad=str(bad)), self.assertRaises(ValueError):
                samp.stage(self.source, bad, **self.kw())
        with self.assertRaises(ValueError):
            samp.stage(self.source, self.root / "vanilla-p0-001", **self.kw())
        self.stage()
        with self.assertRaises(ValueError):
            self.stage()                                    # destination now exists
        (self.source / "stock-backup/mpmissions/dayzOffline.chernarusplus/db/server.cfg").write_bytes(b"x")
        self.dest = self.root / "ce-probe-second"
        with self.assertRaises(ValueError):
            self.stage()
        self.assertFalse(self.dest.exists())

    def test_a_hook_that_violates_the_compile_rules_is_refused_before_anything_is_created(self):
        real = samp.render_hook

        def bad(targets, **kwargs):
            return real(targets, **kwargs) + b"\n    void Bad()\n    {\n        int a = true ? 1 : 2;\n    }\n"
        with mock.patch.object(samp, "render_hook", bad), self.assertRaises(ValueError):
            self.stage()
        self.assertFalse(self.dest.exists())

    def test_option_ranges_are_enforced(self):
        for kwargs in ({"per_class": 0}, {"per_class": 17}, {"wait_minutes": 1}, {"wait_minutes": 500},
                       {"intersect": "bogus"}, {"sample_delay_s": 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.stage(**kwargs)
            self.assertFalse(self.dest.exists())

    def test_missing_placements_for_a_sample_class_is_refused(self):
        counts = sampler_counts()
        counts["Land_Tenement_Big"] = 0
        self.source = cep.make_source_runtime(self.root / "vanilla-2", counts=counts)
        with self.assertRaises(ValueError):
            samp.stage(self.source, self.dest, **self.kw())
        self.assertFalse(self.dest.exists())

    def test_staging_never_launches_anything_or_touches_the_network(self):
        with mock.patch("subprocess.Popen", side_effect=AssertionError("launch")), \
                mock.patch("socket.socket", side_effect=AssertionError("network")):
            self.stage()

    def test_cli_stages_and_reports_errors_without_a_traceback(self):
        argv = ["--source-runtime", str(self.source), "--destination", str(self.dest),
                "--battleye-sha256", cep.SYNTH_BE_SHA, "--per-class", "2", "--intersect", "view"]
        with mock.patch.object(probe, "WSL_PARENT", self.root), mock.patch("sys.stdout") as out:
            self.assertEqual(0, samp.main(argv))
        self.assertIn("ce-probe-plan.json", "".join(call.args[0] for call in out.write.call_args_list))
        plan = json.loads((self.dest / "ce-probe-plan.json").read_text())
        self.assertEqual(8, plan["probe"]["target_count"])
        self.assertEqual("view", plan["sampler"]["intersect"])
        with mock.patch.object(probe, "WSL_PARENT", self.root), mock.patch("sys.stderr") as err:
            self.assertEqual(1, samp.main(argv))
        self.assertIn("interior_sampler:", "".join(call.args[0] for call in err.write.call_args_list))


class LauncherCompatibilityTests(SamplerWorkspace):
    def test_plan_satisfies_every_field_the_unchanged_launcher_checks(self):
        plan = self.stage()
        script = (ROOT / "tools/setup/Start-CEProbeServer.ps1").read_text()
        for field in re.findall(r"\$plan\.(\w+)", script):
            self.assertIn(field, plan, field)
        self.assertEqual(plan["arguments"][:2], ["-ip=127.0.0.1", "-port=2302"])
        self.assertIn("wait_minutes", plan["probe"])
        self.assertIn(r"profiles\HCCEProbe\complete.txt", script)
        self.assertIn(r"profiles\HCCEProbe\census.json", script)


if __name__ == "__main__":
    unittest.main()
