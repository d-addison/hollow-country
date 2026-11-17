"""Offline interior sampler stager/hook tests; SYNTHETIC fixtures, never DayZ behavior.

Nothing here proves how the engine raycast, the building geometry or the navmesh behave.
The generated Enforce hook is checked against compile-shape rules already observed natively
and its floor/interior/reachability logic is executed line by line (reference transpiler from
test_ce_probe) against a mock scene whose planes and navmesh are REFERENCE models, not DayZ.
"""
import ast
import json
import math
from pathlib import Path
import re
import shutil
import unittest
from unittest import mock

from tests.unit import test_ce_probe as cep
from tests.unit import test_probe_runtime as tpr
from tools.setup import ce_probe as probe
from tools.setup import diagnostic_mission as dm
from tools.setup import interior_sampler as samp
from tools.setup import probe_runtime as rt

ROOT = Path(__file__).resolve().parents[2]
NATIVE_CACHE = Path.home() / ".cache/hollow-country/native-scripts/scripts-1.30.164289"
LAUNCHER = ROOT / "tools/setup/Start-CEProbeServer.ps1"
# The row the launcher owner adds for this kind (the launcher chooses plan/directory/output from it).
LAUNCHER_ROW = "'interior-sampler' = @{ Plan = 'interior-sampler-plan.json'; Directory = 'HCInteriorSampler'; Output = 'census.json' }"


class StrictS(cep.S):
    """Enforce string that, unlike the CE probe's S, refuses ANY non-string operand.

    The native compiler rejected a probe hook that concatenated a bare int ("Incompatible parameter");
    a number must be converted with ToString() or a formatting helper before it joins a string.
    """

    def __add__(self, other):
        if not isinstance(other, str):
            raise TypeError("bare %s concatenated to a string: %r" % (type(other).__name__, other))
        return StrictS(str(self) + other)

    def __radd__(self, other):
        if not isinstance(other, str):
            raise TypeError("bare %s concatenated to a string: %r" % (type(other).__name__, other))
        return StrictS(other + str(self))

    def Substring(self, start, length):
        return StrictS(self[start:start + length])

    def Replace(self, sample, replacement):
        return StrictS(str.replace(self, sample, replacement))


def mock_to_string(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("ToString is only modelled for int and float: %r" % (value,))
    return StrictS(str(value) if isinstance(value, int) else repr(float(value)))


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

    def GetType(self):
        return StrictS(self.type_name)

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


class Wall:
    """A vertical wall of the building, in model space: the plane ``axis == coord`` over the span
    [lo, hi) of the other horizontal axis and the heights [y0, y1). REFERENCE geometry only."""

    def __init__(self, owner, axis, coord, lo, hi, y0, y1):
        self.owner, self.axis, self.coord, self.lo, self.hi, self.y0, self.y1 = owner, axis, coord, lo, hi, y0, y1


class Scene:
    def __init__(self, building, planes, walls=()):
        self.building, self.planes, self.walls, self.calls = building, planes, list(walls), []

    def horizontal(self, lb, le, results):
        """First wall crossed by a level ray, or a miss; a sloped ray is refused as unmodelled."""
        if abs(lb[1] - le[1]) > 1e-6:
            raise AssertionError("the sampler must cast vertical or level rays only")
        best = None
        for wall in self.walls:
            a, b = (0, 2) if wall.axis == "x" else (2, 0)            # a: crossing axis, b: along the wall
            if (lb[a] - wall.coord) * (le[a] - wall.coord) > 0 or lb[a] == le[a]:
                continue
            t = (wall.coord - lb[a]) / (le[a] - lb[a])
            along = lb[b] + t * (le[b] - lb[b])
            if wall.lo <= along < wall.hi and wall.y0 <= lb[1] < wall.y1 and (best is None or t < best[0]):
                best = (t, wall)
        if best is None:
            return False, None, None
        t, wall = best
        point = [lb[0] + t * (le[0] - lb[0]), lb[1], lb[2] + t * (le[2] - lb[2])]
        results.Insert(wall.owner)
        return True, self.building.to_world(tuple(point)), (1.0, 0.0, 0.0)

    def ray(self, beg, end, results, intersect):
        self.calls.append((beg, end, intersect))
        lb, le = self.building.CoordToLocal(beg), self.building.CoordToLocal(end)
        if abs(lb[0] - le[0]) > 1e-6 or abs(lb[2] - le[2]) > 1e-6:
            return self.horizontal(lb, le, results)
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

    def __init__(self, building, zones, links=(), partial_gap=0.0, tolerance=1.5, snap=False, offset=(0.0, 0.0, 0.0),
                 box=None):
        self.building, self.zones, self.partial_gap, self.tolerance = building, zones, partial_gap, tolerance
        self.links = {frozenset(pair) for pair in links}
        self.snap, self.offset, self.box = snap, offset, box or building.clip
        self.samples = self.paths = 0

    def zone_at(self, world, radius):
        local = self.building.CoordToLocal(world)
        best = None
        for zone in self.zones:
            if zone.x0 <= local[0] < zone.x1 and zone.z0 <= local[2] < zone.z1 and abs(local[1] - zone.y) <= radius:
                if best is None or abs(local[1] - zone.y) < abs(local[1] - best.y):
                    best = zone
        return best

    def nearest(self, local, radius):
        """Snapping mesh: the closest point of any zone within ``radius`` (3D), like a nearest-poly query."""
        best = None
        for zone in self.zones:
            x = min(max(local[0], zone.x0 + 1e-6), zone.x1 - 1e-6)
            z = min(max(local[2], zone.z0 + 1e-6), zone.z1 - 1e-6)
            distance = math.dist((x, zone.y, z), local)
            if distance <= radius and (best is None or distance < best[0]):
                best = (distance, (x, zone.y, z))
        return None if best is None else best[1]

    def sample(self, position, radius):
        self.samples += 1
        local = self.building.CoordToLocal(position)
        if self.snap:
            point = self.nearest(local, radius)
        else:
            zone = self.zone_at(position, radius)
            point = None if zone is None else (local[0], zone.y, local[2])
        if point is None:
            return False, None
        inside = all(self.box[0][a] <= point[a] <= self.box[1][a] for a in range(3))
        if inside:
            point = tuple(point[a] + self.offset[a] for a in range(3))
        return True, self.building.to_world(point)

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
            "HCProbeReachSetup", "HCProbeReachHit", "HCProbeStep", "HCProbeFinish",
            "HCProbeInt", "HCProbeNum", "HCProbeOutsideBox", "HCProbeOpenSky", "HCProbeSeedOutside",
            "HCProbeTakePath", "HCProbeBlocked")
# Methods the reference transpiler deliberately does not execute: the loaders are literal data and
# HCProbeStart only touches the engine file system and the call queue.
UNMODELLED = frozenset({"HCProbeAdd", "HCProbeStart"})
_MEMBER = re.compile(r"^    protected (?:ref )?([\w<>]+) (m_HCProbe\w+)(?: = (.+))?;$", re.M)
_TO_STRING = re.compile(r"\b(\w+)\.ToString\(\)")


def rewrite_for_model(text):
    for pattern, replacement in MODEL_REWRITES:
        text, count = re.subn(pattern, replacement, text, flags=re.M)
        if count != 1:
            raise ValueError("model rewrite did not match exactly once: " + pattern[:60])
    text = _TO_STRING.sub(r"HCMockToString(\1)", text)
    if ".ToString(" in text:
        raise ValueError("ToString on an expression the reference model cannot rewrite")
    return text


class HookRun:
    """Drive the transpiled hook over one mock building and return the written census.

    ``strict`` runs the hook with an Enforce string type that refuses any bare number operand; the
    behavioural scenarios run with it off so a formatting slip is reported only by the dedicated test.
    """

    def __init__(self, hook_text, building, planes, nav=None, extra_world=(), ai=True, overrides=None, walls=(),
                 strict=False):
        self.text = rewrite_for_model(hook_text)
        self.building, self.scene = building, Scene(building, planes, walls)
        self.nav = nav
        self.files = MockFiles()
        self.game = RunGame([building, *extra_world], nav if ai else None)
        self.prints = []
        text_type = StrictS if strict else cep.S
        namespace = {
            "S": text_type, "EArray": SampArray, "ItemBase": cep.MockItemBase, "Math": cep.MockMath,
            "vector": cep.MockVector, "Vector": lambda x, y, z: (x, y, z), "GetGame": lambda: self.game,
            "FLT_MAX": cep.FLT_MAX_VALUE, "Building": MockBuildingClass, "FileMode": MockFiles.Mode,
            "OpenFile": self.files.OpenFile, "FPrintln": self.files.FPrintln, "CloseFile": self.files.CloseFile,
            "FileExist": self.files.FileExist, "Print": self.prints.append, "CALL_CATEGORY_SYSTEM": 0,
            "HCProbeStep": None, "HCMockRay": self.scene.ray, "HCMockToString": mock_to_string,
            "HCMockSample": (nav.sample if nav else (lambda p, r: (False, None))),
            "HCMockPath": (nav.path if nav else (lambda a, b, w: False)),
        }
        with mock.patch.object(cep, "_TYPE", _MODEL_TYPES):
            source = cep.enforce_to_python(self.text, MODELLED)
        exec(compile(source, "<generated-sampler>", "exec"), namespace)
        self.model = namespace["HookModel"]()
        for _type, name, value in _MEMBER.findall(self.text):
            setattr(self.model, name, eval(cep._enforce_expression(value), namespace) if value else None)
        self.model.m_HCProbeQuote = text_type('"')
        self.model.m_HCProbeFilter = object()
        for name, value in (overrides or {}).items():
            setattr(self.model, name, value)
        self.model.m_HCProbeClasses.Insert(text_type(building.type_name))
        self.model.m_HCProbeRoles.Insert(text_type("tenement"))
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


def flat_building(yaw=0.0, door=(-4.9, 1.0, -0.5)):
    """The standard box without rotation (so model and world axes agree) and one door."""
    b = SampBuilding("Land_Tenement_Small", (3000.0, 20.0, 5000.0), yaw=yaw, clip=BOX)
    b.doors = [b.to_world(door)]
    return b


def mesh_code(row, x, z, y=0.0):
    return {(round(h[0], 1), round(h[2], 1), round(h[1], 1)): h[5] for h in row["hits"]}.get((x, z, y))


def snap_nav(building, east_from=-0.1, **kwargs):
    """A snapping navmesh whose only interior zone starts at model x == east_from (outside is linked)."""
    zones = [Zone("out", -30, -5, -30, 30, 0.0), Zone("g", east_from, 7, -4, 3, 0.0)]
    return NavMesh(building, zones, links=[("out", "g")], snap=True, **kwargs)


def isolated_box_building():
    """40 m building with an INTERNAL door at x=5 and a mesh that exists only inside it."""
    b = SampBuilding("Land_Tenement_Big", (3000.0, 20.0, 5000.0), clip=((-20.0, -1.0, -20.0), (20.0, 5.0, 20.0)))
    b.doors = [b.to_world((5.0, 0.0, 0.0))]
    planes = [Plane(b, 0.0, -20, 20, -20, 20, "floor"), Plane(b, 3.0, -20, 20, -20, 20, "roof")]
    return b, planes, NavMesh(b, [Zone("isolated-interior", -20, 20, -20, 20, 0.0)])


def run_snap_wall(hook_text):
    """Mesh snapping 0.4 m across a wall: (wall owned by the building, no wall, wall owned by a crate)."""
    building = flat_building()
    planes = storey_planes(building)
    wall = [Wall(building, "x", -0.2, -3.0, 2.0, 0.0, 3.0)]
    crate = [Wall(CRATE, "x", -0.2, -3.0, 2.0, 0.0, 3.0)]
    return tuple(HookRun(hook_text, building, planes, nav=snap_nav(building), walls=walls).run().row()
                 for walls in (wall, (), crate))


def run_snap_distance(hook_text):
    """The nearest mesh is 1.4 m (far) or 0.4 m (near) from the measured floor, with no wall between."""
    building = flat_building()
    planes = storey_planes(building)
    return tuple(HookRun(hook_text, building, planes, nav=snap_nav(building, east_from=east)).run().row()
                 for east in (0.9, -0.1))


def run_final_waypoint(hook_text):
    """The mesh is 0.4 m off the floor; the second path also stops 0.45 m short of its destination."""
    building = flat_building()
    planes = storey_planes(building)
    return tuple(HookRun(hook_text, building, planes, nav=nav_for(building, offset=(0.4, 0.0, 0.0), **extra))
                 .run().row() for extra in ({}, {"partial_gap": 0.45}))


def run_isolated_mesh(hook_text):
    building, planes, nav = isolated_box_building()
    return HookRun(hook_text, building, planes, nav=nav).run().row(), nav


def run_seed_projection(hook_text):
    """The raw outside seed snaps back to an interior mesh edge; the real outside mesh is farther away."""
    building = flat_building(door=(-4.2, 0.5, -0.5))
    zones = [Zone("far", -30, -8, -30, 30, 0.0), Zone("g", -5, 7, -4, 3, 0.0)]
    nav = NavMesh(building, zones, links=[("far", "g")], snap=True)
    return HookRun(hook_text, building, storey_planes(building), nav=nav).run().row()


def run_seed_standoff(hook_text):
    """A door 1.4 m inside the box edge: the 2 m seed is only 0.6 m outside, so a farther seed must be used."""
    building = flat_building(door=(-3.6, 1.0, -0.5))
    return HookRun(hook_text, building, storey_planes(building), nav=nav_for(building)).run().row()


def run_overhang(hook_text):
    """A building roof overhangs the entrance seed: outside the box, but not open sky."""
    building = flat_building()
    planes = storey_planes(building) + [Plane(building, 2.6, -9, -5, -4, 3, "under")]
    return HookRun(hook_text, building, planes, nav=nav_for(building)).run().row()


def run_sky_cap(hook_text):
    """No ray budget at all: the open-sky test cannot be answered, so the seed is not validated."""
    building = flat_building()
    return HookRun(hook_text, building, storey_planes(building), nav=nav_for(building),
                   overrides={"m_HCProbeBuildingRayLimit": 0}).run().row()


def run_zero_paths(hook_text):
    building = flat_building()
    nav = nav_for(building)
    row = HookRun(hook_text, building, storey_planes(building), nav=nav, overrides={"m_HCProbePathLimit": 0}).run().row()
    return row, nav


def run_disconnected_control(hook_text):
    """The far control point sits on a mesh island that is not linked to the entrance."""
    building = flat_building()
    zones = [Zone("near", -12, -5, -30, 30, 0.0), Zone("far", -30, -12, -30, 30, 0.0), Zone("g", -5, 7, -4, 3, 0.0)]
    nav = NavMesh(building, zones, links=[("near", "g")])
    return HookRun(hook_text, building, storey_planes(building), nav=nav).run().row()


def run_end_tolerance(hook_text):
    building = flat_building()
    planes = storey_planes(building)
    return tuple(HookRun(hook_text, building, planes, nav=nav_for(building, partial_gap=gap)).run().row()
                 for gap in (0.3, 0.8))


def battery(hook_text, first_failure=False):
    """Names of failed reference scenarios; an exception in the model counts as a failure.

    With ``first_failure`` the run stops at the first mismatch (enough to detect a mutation)."""
    failures = []

    def check(name, function):
        if first_failure and failures:
            return
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

    def snap_wall():
        blocked, open_row, loose = run_snap_wall(hook_text)
        return (blocked["reach"]["state"] == "tested" and mesh_code(blocked, -0.5, 0.5) == 2
                and mesh_code(open_row, -0.5, 0.5) == 1 and mesh_code(loose, -0.5, 0.5) == 1)

    def snap_distance():
        far, near = run_snap_distance(hook_text)
        return mesh_code(far, -0.5, 0.5) == 2 and mesh_code(near, -0.5, 0.5) == 1

    def final_waypoint():
        short, trunc = run_final_waypoint(hook_text)
        return (short["reach"]["state"] == "tested" and mesh_code(short, -3.5, 0.5) == 1
                and trunc["reach"]["state"] == "tested" and mesh_code(trunc, -3.5, 0.5) == 0)

    def isolated_mesh():
        row, nav = run_isolated_mesh(hook_text)
        return row["reach"]["state"] != "tested" and {h[5] for h in row["hits"]} == {-1} and nav.paths == 0

    def seed_projection():
        row = run_seed_projection(hook_text)
        return row["reach"]["state"] != "tested" and {h[5] for h in row["hits"]} == {-1}

    def seed_standoff():
        row = run_seed_standoff(hook_text)
        entrances = row["reach"]["entrances"]
        return row["reach"]["state"] == "tested" and len(entrances) == 1 and entrances[0][0] < -7.0

    def overhang():
        row = run_overhang(hook_text)
        return row["reach"]["state"] != "tested" and {h[5] for h in row["hits"]} == {-1}

    def sky_cap():
        return run_sky_cap(hook_text)["reach"]["state"] != "tested"

    def zero_paths():
        row, nav = run_zero_paths(hook_text)
        return (nav.paths == 0 and nav.samples == 0 and row["reach"]["state"] == "path-budget"
                and {h[5] for h in row["hits"]} == {-1} and row["stats"]["paths"] == 0)

    def disconnected_control():
        row = run_disconnected_control(hook_text)
        return row["reach"]["state"] == "control-failed" and {h[5] for h in row["hits"]} == {-1}

    def end_tolerance():
        small, large = run_end_tolerance(hook_text)
        return (small["reach"]["state"] == "tested" and mesh_code(small, -3.5, 0.5) == 1
                and large["reach"]["state"] == "control-failed")

    for name, function in (("floors", floors), ("rotation", rotation), ("grid", grid), ("reach", reach),
                           ("partial-path", partial_path), ("altitude", altitude), ("budgets", budgets),
                           ("run-budget", run_budget), ("hit-limit", hit_limit), ("reach-states", reach_states),
                           ("other-objects", other_objects), ("snap-wall", snap_wall),
                           ("snap-distance", snap_distance), ("final-waypoint", final_waypoint),
                           ("isolated-mesh", isolated_mesh), ("seed-projection", seed_projection),
                           ("seed-standoff", seed_standoff), ("overhang", overhang), ("sky-cap", sky_cap),
                           ("zero-paths", zero_paths), ("disconnected-control", disconnected_control),
                           ("end-tolerance", end_tolerance)):
        check(name, function)
    return failures


MUTATIONS = (
    ("hits on other objects accepted as the building", "if (hitObjects.Find(m_HCProbeBuilding) == -1)", "if (false)"),
    ("miss treated as a hit", "        if (!hit)\n            return 0;", "        if (hit)\n            return 0;"),
    ("same-slab spacing removed", "if (lastY - hitY < 0.25)", "if (lastY - hitY < -1.0)"),
    ("restart goes above the hit", "startY = hitY - 0.05;", "startY = hitY + 0.05;"),
    ("exterior hits kept", "if (clearance < 0.0)", "if (false)"),
    ("clearance measured from the box", "return hitY - surfacePos[1];", "return hitY;"),
    ("upward ray starts below the surface", "surfacePos[1] + 0.05", "surfacePos[1] - 0.05"),
    ("upward range widened", "surfacePos[1] + 6.0", "surfacePos[1] + 60.0"),
    ("upward non-building hit ends the search", "if (result == 1)\n                return hitY - surfacePos[1];",
     "if (true)\n                return hitY - surfacePos[1];"),
    ("other-object hits become floors", "            if (result == 2)\n            {\n                m_HCProbeStatOther",
     "            if (result == 99)\n            {\n                m_HCProbeStatOther"),
    ("grid step doubled", "edge = edge + m_HCProbeGridStep;", "edge = edge + 2.0;"),
    ("grid origin moved to the edge", "float edge = low + 0.5;", "float edge = low;"),
    ("hit limit removed", "step < m_HCProbeHitLimit", "step < 99"),
    ("building ray cap removed", "m_HCProbeBuildingRays >= m_HCProbeBuildingRayLimit ||",
     "m_HCProbeBuildingRays >= 99999999 ||"),
    ("run ray cap removed", "|| m_HCProbeRunRays >= m_HCProbeRunRayLimit", "|| m_HCProbeRunRays >= 99999999"),
    ("model coordinates dropped", "m_HCProbeBuilding.CoordToLocal(floorPos)", "floorPos"),
    ("path end gap widened", "gap <= m_HCProbeEndTolerance", "gap <= 200.0"),
    ("final waypoint not compared with the floor", "float gap = vector.Distance(finalPoint, goalPos);",
     "float gap = 0.0;"),
    ("reach computed without control", 'if (m_HCProbeReachState != "tested")', "if (false)"),
    ("control failure ignored", "if (HCProbePath(entranceSampled, farSampled, farSampled) < 1)", "if (false)"),
    ("control path to its own start", "HCProbePath(entranceSampled, farSampled, farSampled)",
     "HCProbePath(entranceSampled, entranceSampled, entranceSampled)"),
    ("path budget removed", "if (m_HCProbeBuildingPaths >= m_HCProbePathLimit)", "if (false)"),
    ("comma separation removed", "if (m_HCProbeHitsEmitted > 0)", "if (false)"),
    ("outside point inside the building", "doorPos[0] + unitX * standoff", "doorPos[0] - unitX * standoff"),
    ("seed margin removed", "if (HCProbeOutsideBox(m_HCProbeSeed, m_HCProbeSeedMargin))", "if (true)"),
    ("projected seed may land inside", "HCProbeOutsideBox(m_HCProbeBuilding.CoordToLocal(entranceSampled), m_HCProbeProjectedMargin)",
     "true"),
    ("open sky not required", "if (!HCProbeOpenSky(entranceSampled))", "if (false)"),
    ("open-sky building hit ignored", "            if (result != 2)\n                return false;", "            if (false)\n                return false;"),
    ("snap displacement unbounded", "vector.Distance(candidate, floorPos) > m_HCProbeSnapLimit",
     "vector.Distance(candidate, floorPos) > 99.0"),
    ("waist wall ray skipped", "if (HCProbeBlocked(Vector(floorPos[0], waistY", "if (false && HCProbeBlocked(Vector(floorPos[0], waistY"),
    ("waist wall ray never blocks", "            return false;\n        return true;\n    }\n\n    void HCProbeEmit",
     "            return false;\n        return false;\n    }\n\n    void HCProbeEmit"),
    ("small snap shifts skip the wall ray", "shiftZ * shiftZ > 0.0025", "shiftZ * shiftZ > 100.0"),
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
            self.assertEqual([], samp.lint_sampler_hook(text, native_types=rt.native_type_names(NATIVE_CACHE)))

    def test_extra_lint_rejects_else_unseeded_out_arguments_and_leading_operators(self):
        base = default_hook()
        self.assertNotEqual([], samp.lint_sampler_hook(base.replace("        vector contactPos;\n", "", 1)))
        self.assertNotEqual([], samp.lint_sampler_hook(base.replace("        int contactComponent;\n", "", 1)))
        self.assertNotEqual([], samp.lint_sampler_hook(base.replace("return 2;\n        return 1;", "return 2;\n        else\n            return 1;", 1)))
        self.assertNotEqual([], samp.lint_sampler_hook(base + "\n    void Bad()\n    {\n        int a = true ? 1 : 2;\n    }\n"))

    def test_the_lint_rejects_a_statement_with_more_than_eight_binary_plus_operators(self):
        base = default_hook()
        nine = 'string a = "x" + "y" + "z" + "x" + "y" + "z" + "x" + "y" + "z" + "x";'
        eight = 'string a = "x" + "y" + "z" + "x" + "y" + "z" + "x" + "y" + "z";'
        bad = base + "\n    void Bad()\n    {\n        %s\n    }\n"
        self.assertTrue(any("'+'" in issue for issue in samp.lint_sampler_hook(bad % nine)))
        self.assertEqual([], samp.lint_sampler_hook(bad % eight))
        # '++' and '+=' are not binary additions, and string literal contents are ignored
        loop = ('\n    void Ok()\n    {\n        int i = 0;\n        int n = 0;\n        for (i = 0; i < 3; i++)\n'
                '            n += 1;\n        string t = "+ + + + + + + + + +";\n    }\n')
        self.assertEqual([], samp.lint_sampler_hook(base + loop))

    def test_the_lint_rejects_a_bare_number_joined_to_a_string(self):
        base = default_hook()
        wrap = base + "\n    void Bad()\n    {\n        int count = 1;\n        float size = 1.0;\n        string a = %s;\n    }\n"
        for bad in ('"n=" + count', '"s=" + size', 'count + "n"', '"[" + m_HCProbeCursor + "]"',
                    '"v=" + m_HCProbeRoles.Count()', 'HCProbeKey("a") + count'):
            with self.subTest(bad=bad):
                self.assertTrue(any("number" in issue for issue in samp.lint_sampler_hook(wrap % bad)), bad)
        for good in ('"n=" + count.ToString()', '"s=" + HCProbeNum(size)', '"n=" + HCProbeInt(count)',
                     '"x" + HCProbeBool(true)', 'HCProbeKey("a") + HCProbeStr("b")'):
            with self.subTest(good=good):
                self.assertEqual([], samp.lint_sampler_hook(wrap % good), good)

    def test_the_generated_hook_has_at_most_eight_pluses_per_statement_and_converts_every_number(self):
        text = default_hook()
        blank = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
        plus = re.compile(r"(?<!\+)\+(?![+=])")
        self.assertLessEqual(max(len(plus.findall(statement)) for statement in re.split(r"[;{}]", blank)), 8)
        self.assertLessEqual(max(len(plus.findall(line)) for line in blank.splitlines()), 8)
        self.assertEqual([], samp.lint_sampler_hook(text))
        self.assertIn("string HCProbeInt(int value)", text)
        self.assertIn("string HCProbeNum(float value)", text)
        self.assertEqual(2, text.count(".ToString()"))          # only inside the two helpers

    def test_every_number_in_the_census_is_converted_explicitly_when_the_hook_runs_with_strict_strings(self):
        building = storey_building()
        run = HookRun(default_hook(), building, storey_planes(building), nav=nav_for(building), strict=True).run()
        row = run.row()
        self.assertGreater(len(row["hits"]), 40)
        self.assertEqual("tested", row["reach"]["state"])
        self.assertEqual(["rows=1 found=1"], run.sentinel())
        self.assertTrue(run.census()["summary"]["complete"])

    def test_the_strict_string_model_rejects_a_hook_that_concatenates_a_bare_number(self):
        good = default_hook()
        self.assertEqual(1, good.count("HCProbeInt(m_HCProbeCursor)"))
        text = good.replace("HCProbeInt(m_HCProbeCursor)", "m_HCProbeCursor", 1)
        building = storey_building()
        with self.assertRaises(TypeError):
            HookRun(text, building, storey_planes(building), ai=False, strict=True).run()

    def test_every_hook_method_is_executed_by_the_reference_model_except_the_loaders_and_start(self):
        text = default_hook()
        names = {m.group(1) for m in map(cep._SIGNATURE.match, text.splitlines()) if m}
        loaders = {n for n in names if re.fullmatch(r"HCProbeLoadTargets\d+", n)}
        self.assertTrue(loaders)
        self.assertEqual(set(), names - set(MODELLED) - UNMODELLED - loaders)
        self.assertEqual(set(), set(MODELLED) - names)

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
        self.assertIn('"$profile:HCInteriorSampler/census.json"', text)
        self.assertIn('"$profile:HCInteriorSampler/complete.txt"', text)
        self.assertIn('"$profile:HCInteriorSampler"', text)
        self.assertNotIn("HCCEProbe", text)

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
                self.assertNotEqual([], battery(self.hook.replace(old, new, 1), first_failure=True))

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

    def test_mesh_snapping_across_a_wall_is_not_reachability(self):
        blocked, open_row, loose = run_snap_wall(self.hook)
        self.assertEqual("tested", blocked["reach"]["state"])
        self.assertEqual(1, mesh_code(open_row, -0.5, 0.5))      # same mesh, no wall: reachable
        self.assertEqual(2, mesh_code(blocked, -0.5, 0.5))       # the snapped point is behind a building wall
        self.assertEqual(1, mesh_code(loose, -0.5, 0.5))         # a non-building object is not a wall

    def test_the_snap_displacement_from_the_measured_floor_is_bounded(self):
        far, near = run_snap_distance(self.hook)
        self.assertEqual(1, mesh_code(near, -0.5, 0.5))          # 0.4 m: the cell is on that mesh
        self.assertEqual(2, mesh_code(far, -0.5, 0.5))           # 1.4 m: a different surface

    def test_the_final_waypoint_must_end_at_the_measured_floor_not_within_two_metres(self):
        short, trunc = run_final_waypoint(self.hook)
        self.assertEqual(1, mesh_code(short, -3.5, 0.5))         # 0.4 m mesh offset
        self.assertEqual("tested", trunc["reach"]["state"])      # the 0.45 m stop is inside the control tolerance
        self.assertEqual(0, mesh_code(trunc, -3.5, 0.5))         # but 0.85 m from the floor itself

    def test_the_path_end_tolerance_is_tight_enough_to_fail_a_truncated_control_path(self):
        small, large = run_end_tolerance(self.hook)
        self.assertEqual("tested", small["reach"]["state"])      # 0.3 m short is a complete path
        self.assertEqual(1, mesh_code(small, -3.5, 0.5))
        self.assertEqual("control-failed", large["reach"]["state"])    # 0.8 m short is truncated, not 2 m

    def test_a_door_inside_the_box_on_an_isolated_interior_mesh_cannot_validate_the_exterior_control(self):
        row, nav = run_isolated_mesh(self.hook)
        self.assertNotEqual("tested", row["reach"]["state"])
        self.assertEqual({-1}, {h[5] for h in row["hits"]})
        self.assertEqual([], row["reach"]["entrances"])
        self.assertEqual(0, nav.paths)

    def test_an_exterior_seed_that_snaps_back_inside_the_building_is_refused(self):
        row = run_seed_projection(self.hook)
        self.assertNotEqual("tested", row["reach"]["state"])
        self.assertEqual({-1}, {h[5] for h in row["hits"]})

    def test_a_door_near_the_box_edge_gets_a_seed_with_a_real_standoff(self):
        row = run_seed_standoff(self.hook)
        self.assertEqual("tested", row["reach"]["state"])
        self.assertLess(row["reach"]["entrances"][0][0], BOX[0][0] - 2.0)

    def test_an_exterior_seed_under_a_building_overhang_is_not_open_sky(self):
        row = run_overhang(self.hook)
        self.assertNotEqual("tested", row["reach"]["state"])
        self.assertEqual({-1}, {h[5] for h in row["hits"]})

    def test_an_unanswerable_open_sky_test_does_not_validate_the_seed(self):
        self.assertNotEqual("tested", run_sky_cap(self.hook)["reach"]["state"])

    def test_a_zero_path_budget_runs_no_setup_or_control_queries(self):
        row, nav = run_zero_paths(self.hook)
        self.assertEqual((0, 0), (nav.paths, nav.samples))
        self.assertEqual("path-budget", row["reach"]["state"])
        self.assertEqual(0, row["stats"]["paths"])
        self.assertEqual({-1}, {h[5] for h in row["hits"]})
        building = storey_building()
        nav = nav_for(building)
        HookRun(default_hook(path_limit=0), building, storey_planes(building), nav=nav).run()
        self.assertEqual(0, nav.paths)

    def test_a_control_path_to_an_unlinked_far_point_fails_the_control(self):
        row = run_disconnected_control(self.hook)
        self.assertEqual("control-failed", row["reach"]["state"])
        self.assertEqual({-1}, {h[5] for h in row["hits"]})

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
        # probe_runtime lists the launcher's per-kind rows; the sampler's row is added by its owner.
        patcher = mock.patch.dict(rt.LAUNCHER_PROBES, {samp.KIND: samp.LAUNCHER_ROW})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.source = cep.make_source_runtime(self.root / "vanilla-s", counts=sampler_counts())

    def launcher_problems(self, plan, plan_name):
        """The launcher's plan checks on the staged files without the plan file itself (the launcher
        adds the plan path to its own allowed set)."""
        view = self.root / "launcher-view"
        shutil.copytree(self.dest, view, ignore=shutil.ignore_patterns(plan_name))
        return rt.launcher_problems(plan, view, plan_name)

    def stage(self, **extra):
        return samp.stage(self.source, self.dest, **self.kw(**extra))


class StagerTests(SamplerWorkspace):
    MISSION = "mpmissions/dayzOffline.chernarusplus/"

    def test_stage_builds_the_runtime_with_k_placements_per_class_and_a_launcher_compatible_plan(self):
        plan = self.stage()
        self.assertEqual("interior-sampler", plan["kind"])
        self.assertEqual("staged-only-not-launched", plan["status"])
        self.assertEqual("sampler", plan["variant"])             # the launcher reads $plan.variant for every kind
        self.assertEqual(16, plan["probe"]["target_count"])
        self.assertEqual({name: 4 for name, _role in samp.SAMPLE_CLASSES},
                         {entry["class"]: entry["sampled"] for entry in plan["target_classes"]})
        self.assertEqual("profiles/HCInteriorSampler/census.json", plan["probe"]["census_relative_path"])
        self.assertEqual("profiles/HCInteriorSampler/complete.txt", plan["probe"]["sentinel_relative_path"])
        self.assertEqual("interior-sampler", plan["probe"]["tool"])
        self.assertEqual({"grid_step": 1.0, "per_class": 4, "intersect": "geom"},
                         {k: plan["sampler"][k] for k in ("grid_step", "per_class", "intersect")})
        self.assertEqual(plan, json.loads((self.dest / "interior-sampler-plan.json").read_text()))
        self.assertFalse((self.dest / "ce-probe-plan.json").exists())
        self.assertEqual([], self.launcher_problems(plan, "interior-sampler-plan.json"))
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

    def test_the_plan_is_refused_while_the_launcher_has_no_row_for_the_kind(self):
        rt.LAUNCHER_PROBES.pop(samp.KIND)                      # restored by the workspace's patch.dict
        with self.assertRaises(ValueError) as caught:
            self.stage()
        self.assertIn("launcher", str(caught.exception))
        self.assertFalse((self.dest / "interior-sampler-plan.json").exists())

    def test_the_plan_names_only_the_sampler_directory_and_files(self):
        plan = self.stage()
        text = json.dumps(plan)
        self.assertNotIn("HCCEProbe", text)
        self.assertEqual(samp.LAUNCHER_ROW, ("interior-sampler-plan.json", "HCInteriorSampler", "census.json"))
        self.assertEqual("complete.txt", samp.SENTINEL_NAME)

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
        with mock.patch.object(rt, "WSL_PARENT", self.root), mock.patch("sys.stdout") as out:
            self.assertEqual(0, samp.main(argv))
        self.assertIn("interior-sampler-plan.json", "".join(call.args[0] for call in out.write.call_args_list))
        plan = json.loads((self.dest / "interior-sampler-plan.json").read_text())
        self.assertEqual(8, plan["probe"]["target_count"])
        self.assertEqual("view", plan["sampler"]["intersect"])
        with mock.patch.object(rt, "WSL_PARENT", self.root), mock.patch("sys.stderr") as err:
            self.assertEqual(1, samp.main(argv))
        self.assertIn("interior_sampler:", "".join(call.args[0] for call in err.write.call_args_list))


def launcher_with_row():
    """The launcher text as it will be once its owner adds the sampler row (idempotent)."""
    script = LAUNCHER.read_text()
    if "'interior-sampler'" not in script:
        script = script.replace("[ValidateSet('ce-probe', 'taped-light-probe')]",
                                "[ValidateSet('ce-probe', 'taped-light-probe', 'interior-sampler')]", 1)
        script = re.sub(r"(\$probes = @\{\n(?:    '.*\n)+)", lambda m: m.group(1) + "    " + LAUNCHER_ROW + "\n", script, count=1)
    return script


def launcher_probe_table(script):
    block = re.search(r"\$probes = @\{\n((?:    '.*\n)+)\}", script)
    table = {}
    for kind, plan, directory, output in re.findall(
            r"'([\w-]+)' = @\{ Plan = '([^']+)'; Directory = '([^']+)'; Output = '([^']+)' \}", block.group(1)):
        table[kind] = (plan, directory, output)
    return table


class LauncherCompatibilityTests(SamplerWorkspace):
    def test_plan_satisfies_every_field_the_kind_derived_launcher_checks(self):
        plan = self.stage()
        script = launcher_with_row()
        self.assertIn("'interior-sampler'", re.search(r"\[ValidateSet\([^)]*\)\]", script).group(0))
        table = launcher_probe_table(script)
        self.assertEqual(samp.LAUNCHER_ROW, table["interior-sampler"])
        self.assertEqual(plan["kind"], "interior-sampler")
        self.assertEqual(table["interior-sampler"][0], "interior-sampler-plan.json")
        for field in re.findall(r"\$plan\.(\w+)", script):
            self.assertIn(field, plan, field)
        self.assertEqual(plan["arguments"][:2], ["-ip=127.0.0.1", "-port=2302"])
        self.assertIn("wait_minutes", plan["probe"])
        self.assertIn("'profiles\\' + $probe.Directory + '\\complete.txt'", script)
        self.assertIn("'profiles\\' + $probe.Directory + '\\' + $probe.Output", script)
        self.assertEqual(plan["probe"]["census_relative_path"],
                         "profiles/%s/%s" % (table["interior-sampler"][1], table["interior-sampler"][2]))
        self.assertEqual(plan["probe"]["sentinel_relative_path"], "profiles/%s/complete.txt" % table["interior-sampler"][1])
        self.assertEqual([], self.launcher_problems(plan, table["interior-sampler"][0]))

    def test_the_hook_writes_where_the_launcher_looks_for_the_sentinel_and_output(self):
        table = launcher_probe_table(launcher_with_row())
        _plan, directory, output = table["interior-sampler"]
        text = default_hook()
        self.assertIn('"$profile:%s/%s"' % (directory, output), text)
        self.assertIn('"$profile:%s/complete.txt"' % directory, text)

    def test_the_existing_launcher_rows_are_untouched_by_the_test_copy(self):
        table = launcher_probe_table(launcher_with_row())
        for kind, row in rt.LAUNCHER_PROBES.items():
            if kind != "interior-sampler":
                self.assertEqual(tuple(row), table[kind])


if __name__ == "__main__":
    unittest.main()
