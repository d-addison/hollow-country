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
from tools.audit import interior_points as pts
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

    def Contains(self, sample):
        return str(sample) in str(self)


class LooseS(cep.S):
    """The non-strict Enforce string plus Contains (EnString.c:286)."""

    def Contains(self, sample):
        return str(sample) in str(self)


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
    """A horizontal surface. ``owner`` None models ground (a hit with an empty result set). ``thick`` > 0
    models a closed volume below the surface: a downward ray that STARTS inside it reports the contact at its
    start (a pessimistic REFERENCE model of a start-inside re-hit, not observed DayZ behavior)."""

    def __init__(self, owner, y, x0, x1, z0, z1, kind, dir_y=1.0, thick=0.0):
        self.owner, self.y, self.x0, self.x1, self.z0, self.z1, self.kind, self.dir_y, self.thick = (
            owner, y, x0, x1, z0, z1, kind, dir_y, thick)

    def hit_y(self, start_y, end_y):
        """Height of the contact for a vertical ray from start_y to end_y, or None.

        A thick plane is a closed volume from ``y - thick`` to ``y``: a ray that starts inside re-reports its
        start, and an upward ray from below meets the underside first (REFERENCE model, not DayZ behavior)."""
        if end_y < start_y:
            if self.thick and self.y - self.thick < start_y <= self.y:
                return start_y
            return self.y if end_y <= self.y < start_y else None
        if self.thick:
            bottom = self.y - self.thick
            if bottom < start_y <= self.y:
                return start_y
            return bottom if start_y < bottom <= end_y else None
        return self.y if start_y < self.y <= end_y else None

    def covers(self, x, z):
        return self.x0 <= x < self.x1 and self.z0 <= z < self.z1


class SampBuilding(cep.MockObject):
    """REFERENCE door model with a REQUESTED phase apart from the ACTUAL phase (Building.c:33 versus :45/:51).

    ``state`` is the requested phase (IsDoorOpen: the wanted phase is above 0.5). ``phase`` is the actual phase
    (IsDoorOpened 1.0, IsDoorOpenedAjar 0.2, IsDoorClosed 0.0; anything else is mid-move). A request moves the
    actual phase after ``lag`` ticks (the hook driver calls ``tick``), unless the door is ``stuck`` for that
    request. A door is open and unlocked unless a test says otherwise, so a scenario that does not care about
    doors never triggers the open pass. ``ops`` logs every state change the hook asks for.
    """

    MOVING = 0.5

    def __init__(self, *args, doors=(), model="synthetic_model", selections=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.doors = list(doors)
        self.model, self.selections = model, dict(selections or {})
        self.state, self.locked, self.ops = {}, set(), []
        self.phase, self.pending, self.stuck, self.lag = {}, {}, {}, 2

    def actual(self, index):
        return self.phase.get(index, 1.0 if self.state.get(index, True) else 0.0)

    def IsDoorOpen(self, index):
        return self.state.get(index, True)

    def IsDoorOpened(self, index):
        return self.actual(index) == 1.0

    def IsDoorOpenedAjar(self, index):
        return self.actual(index) == 0.2

    def IsDoorClosed(self, index):
        return self.actual(index) == 0.0

    def IsDoorLocked(self, index):
        return index in self.locked

    def request(self, index, opening):
        self.ops.append(("open" if opening else "close", index))
        self.phase[index] = self.actual(index)          # the actual phase is pinned: a request does not move it by itself
        self.state[index] = opening
        if ("open" if opening else "close") in self.stuck.get(index, ()):
            return
        lag = self.lag[index] if isinstance(self.lag, dict) else self.lag
        if lag <= 0:
            self.phase[index] = 1.0 if opening else 0.0
            self.pending.pop(index, None)
            return
        self.phase[index] = self.MOVING
        self.pending[index] = [lag, 1.0 if opening else 0.0]

    def OpenDoor(self, index):
        self.request(index, True)

    def CloseDoor(self, index):
        self.request(index, False)

    def tick(self):
        for index in list(self.pending):
            self.pending[index][0] -= 1
            if self.pending[index][0] <= 0:
                self.phase[index] = self.pending.pop(index)[1]

    def GetType(self):
        return StrictS(self.type_name)

    def CoordToParent(self, local):
        return self.to_world(local)

    def GetOrientation(self):
        return (math.degrees(self.yaw), 0.0, 0.0)

    def GetDoorCount(self):
        return len(self.doors)

    def GetModelName(self):
        """Object.c:497 (the p3d name without the suffix)."""
        return LooseS(self.model)

    def GetSelectionList(self, out):
        """Object.c:382 (out TStringArray): the model's selection names in model order (REFERENCE data)."""
        out.extend(LooseS(name) for name in self.selections)

    def GetSelectionPositionMS(self, name):
        """Object.c:864: the selection's model-space position (REFERENCE data, not an observed frame)."""
        return self.selections[str(name)]

    def GetDoorSoundPos(self, index):
        return self.doors[index]

    def GetParent(self):
        return None


class SceneObject:
    """A non-building collision owner; ``parent`` models Object.GetParent() (IEntity, EnEntity.c:571)."""

    def __init__(self, name, parent=None):
        self.name, self.parent = name, parent

    def GetType(self):
        return StrictS(self.name)

    def GetParent(self):
        return self.parent


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
        x, z = lb[0], lb[2]
        best = None
        for plane in self.planes:
            height = plane.hit_y(lb[1], le[1]) if plane.covers(x, z) else None
            if height is not None and (best is None or abs(height - lb[1]) < abs(best[0] - lb[1])):
                best = (height, plane)
        if best is None:
            return False, None, None
        height, plane = best
        if plane.owner is not None:
            results.Insert(plane.owner)
        return True, self.building.to_world((x, height, z)), (0.0, plane.dir_y, 0.0)


class Zone:
    def __init__(self, comp, x0, x1, z0, z1, y):
        self.comp, self.x0, self.x1, self.z0, self.z1, self.y = comp, x0, x1, z0, z1, y


class NavMesh:
    """Reference navmesh: flat zones, links between components, optional truncated paths."""

    def __init__(self, building, zones, links=(), partial_gap=0.0, tolerance=1.5, snap=False, offset=(0.0, 0.0, 0.0),
                 box=None, single_waypoint=False, player_links=None, final_drop=0.0, player_only=None):
        self.building, self.zones, self.partial_gap, self.tolerance = building, zones, partial_gap, tolerance
        self.single_waypoint, self.final_drop = single_waypoint, final_drop
        self.links = {frozenset(pair) for pair in links}
        # Links only the player filter may use (stairs, ladders, jumps); strict never sees them.
        self.player_links = self.links | {frozenset(pair) for pair in (player_links or ())}
        if player_only is not None:             # the player filter may use exactly these links
            self.player_links = {frozenset(pair) for pair in player_only}
        self.snap, self.offset, self.box = snap, offset, box or building.clip
        self.samples = self.paths = 0
        self.filters = []                       # the filter object every sample/path call received

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

    def sample(self, position, radius, flt=None):
        self.samples += 1
        self.filters.append(flt)
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

    def path(self, start, end, waypoints, flt=None):
        self.paths += 1
        self.filters.append(flt)
        a, b = self.zone_at(start, self.tolerance), self.zone_at(end, self.tolerance)
        if a is None or b is None:
            return False
        links = self.player_links if flt is PLAYER_FILTER else self.links
        if a.comp != b.comp and frozenset((a.comp, b.comp)) not in links:
            return False
        stop = end
        if self.partial_gap:
            stop = (end[0] + self.partial_gap, end[1], end[2])
        if self.final_drop:
            stop = (stop[0], stop[1] + self.final_drop, stop[2])
        waypoints.Insert(start)
        if not self.single_waypoint:
            waypoints.Insert(stop)
        return True


class DoorGatedNav(NavMesh):
    """A reference mesh whose zone links exist only while door ``gate`` of the building is open (REFERENCE model)."""

    def __init__(self, building, zones, gate=0, **kwargs):
        super().__init__(building, zones, **kwargs)
        self.gate, self.open_links, self.open_player_links = gate, self.links, self.player_links

    def path(self, start, end, waypoints, flt=None):
        closed = not self.building.IsDoorOpened(self.gate)
        self.links = set() if closed else self.open_links
        self.player_links = set() if closed else self.open_player_links
        return super().path(start, end, waypoints, flt)


class MockFilter:
    """A PGFilter stand-in: only the three getters the census header reads."""

    def __init__(self, include, exclude, exclusive=0):
        self.include, self.exclude, self.exclusive = include, exclude, exclusive

    def GetIncludeFlags(self):
        return self.include

    def GetExcludeFlags(self):
        return self.exclude

    def GetExlusiveFlags(self):
        return self.exclusive


class MockPolyFlags:
    """PGPolyFlags with REFERENCE values (distinct powers of two); the native values are recorded by the census."""
    NAMES = ("NONE", "WALK", "DISABLED", "DOOR", "INSIDE", "SWIM", "SWIM_SEA", "LADDER", "JUMP_OVER", "JUMP_DOWN",
             "CLIMB", "CRAWL", "CROUCH", "UNREACHABLE", "ALL", "JUMP", "SPECIAL")


for _index, _name in enumerate(MockPolyFlags.NAMES):
    setattr(MockPolyFlags, _name, 0 if _name == "NONE" else 1 << (_index - 1))

STRICT_FILTER = MockFilter(MockPolyFlags.WALK | MockPolyFlags.DOOR | MockPolyFlags.INSIDE, 4096)
PLAYER_FILTER = MockFilter(MockPolyFlags.WALK | MockPolyFlags.DOOR | MockPolyFlags.INSIDE | MockPolyFlags.JUMP, 8192)


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
    def __init__(self, world, nav, ground_offset=0.0):
        super().__init__(world)
        self.nav, self.queue, self.clock = nav, MockQueue(), 0
        self.ground = (world[0].pos[1] if world else 0.0) + ground_offset
        self.surface_calls = []

    def SurfaceY(self, x, z):
        """Game.c:1176 SurfaceY(x, z): a flat REFERENCE terrain at the building's base."""
        self.surface_calls.append((x, z))
        return self.ground

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

    def Set(self, index, value):
        self[index] = value


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


_MODEL_TYPES = r"(?:int|float|bool|string|vector|Object|ItemBase|CargoBase|Building|FileHandle|PGFilter|array<[^>]+>)"

# Exact hook lines whose out-parameter calls cannot be modelled; each must match exactly once.
MODEL_REWRITES = (
    (r"^( +)set<Object> hitObjects = new set<Object>;$", r"\1array<Object> hitObjects = new array<Object>;"),
    (r"^( +)bool hit = DayZPhysics\.RaycastRV\(rayFrom, rayTo, contactPos, contactDir, contactComponent, hitObjects, "
     r"null, null, false, false, (ObjIntersect\w+)\);$",
     r"\1hit, contactPos, contactDir = HCMockRay(rayFrom, rayTo, hitObjects, '\2');"),
    (r"^( +)bool found = GetGame\(\)\.GetWorld\(\)\.GetAIWorld\(\)\.SampleNavmeshPosition\(position, radius, "
     r"(m_HCProbeFilter|meshFilter), sampled\);$", r"\1found, sampled = HCMockSample(position, radius, \2);"),
    (r"^( +)TVectorArray waypoints = new TVectorArray;$", r"\1array<vector> waypoints = new array<vector>;"),
    (r"^( +)bool found = GetGame\(\)\.GetWorld\(\)\.GetAIWorld\(\)\.FindPath\(startPos, endPos, "
     r"(m_HCProbeFilter|meshFilter), waypoints\);$", r"\1found = HCMockPath(startPos, endPos, waypoints, \2);"),
)

MODELLED = ("HCProbeKey", "HCProbeStr", "HCProbeBool", "HCProbeVector", "HCProbeBoxUsable", "HCProbeCount",
            "HCProbeRay", "HCProbeClearance", "HCProbeEmit", "HCProbeFlush", "HCProbeHeader",
            "HCProbeBeginBuilding", "HCProbeScanRow", "HCProbeScanColumn", "HCProbeRecordFloor",
            "HCProbeEndBuilding", "HCProbeMeshAvailable", "HCProbeSampleMesh", "HCProbePath",
            "HCProbeReachSetup", "HCProbeReachHit", "HCProbeStep", "HCProbeFinish",
            "HCProbeInt", "HCProbeNum", "HCProbeOutsideBox", "HCProbeOpenSky", "HCProbeSeedOutside",
            "HCProbeTakePath", "HCProbeBlocked", "HCProbeClassify", "HCProbeReachAttempt", "HCProbeReachNote",
            "HCProbeHitNote", "HCProbeTypeNote", "HCProbeTypesText", "HCProbeTraceEntry", "HCProbeDiagColumn",
            "HCProbeReachDoor", "HCProbeDiagReset", "HCProbeDiagSample", "HCProbeReasonName", "HCProbeReachDiagVariant",
            "HCProbeReachDiagText", "HCProbeControlDetail", "HCProbeColumnFlush", "HCProbeFilterText",
            "HCProbeFlagEntry", "HCProbeFlagsText", "HCProbeReachResult",
            "HCProbeVariantState", "HCProbeSetState", "HCProbeUseEntrance", "HCProbeSetEntrance",
            "HCProbeUseFilter", "HCProbeEnteredCheck", "HCProbeDoorsOpen", "HCProbeWait", "HCProbeDoorPhase", "HCProbeDoorsSettled",
            "HCProbeOpenControl", "HCProbeOpenFloors", "HCProbeDoorsClose", "HCProbeDoorsRestored",
            "HCProbeDoorRunText", "HCProbeEnteredText", "HCProbeFrameProbe", "HCProbeFrameCheck",
            "HCProbeDoorSelection", "HCProbeHouseText")
# Methods the reference transpiler deliberately does not execute: the loaders are literal data and
# HCProbeStart only touches the engine file system and the call queue.
UNMODELLED = frozenset({"HCProbeAdd", "HCProbeFrameAdd", "HCProbeStart"})
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
                 strict=False, ground_offset=0.0, frame_points=()):
        self.text = rewrite_for_model(hook_text)
        self.building, self.scene = building, Scene(building, planes, walls)
        self.nav = nav
        self.files = MockFiles()
        self.game = RunGame([building, *extra_world], nav if ai else None, ground_offset)
        self.prints = []
        text_type = StrictS if strict else LooseS
        namespace = {
            "S": text_type, "EArray": SampArray, "ItemBase": cep.MockItemBase, "Math": cep.MockMath,
            "vector": cep.MockVector, "Vector": lambda x, y, z: (x, y, z), "GetGame": lambda: self.game,
            "FLT_MAX": cep.FLT_MAX_VALUE, "Building": MockBuildingClass, "FileMode": MockFiles.Mode,
            "OpenFile": self.files.OpenFile, "FPrintln": self.files.FPrintln, "CloseFile": self.files.CloseFile,
            "FileExist": self.files.FileExist, "Print": self.prints.append, "CALL_CATEGORY_SYSTEM": 0,
            "HCProbeStep": None, "HCMockRay": self.scene.ray, "HCMockToString": mock_to_string,
            "HCMockSample": (nav.sample if nav else (lambda p, r, f=None: (False, None))),
            "HCMockPath": (nav.path if nav else (lambda a, b, w, f=None: False)),
            "PGPolyFlags": MockPolyFlags,
        }
        with mock.patch.object(cep, "_TYPE", _MODEL_TYPES):
            source = cep.enforce_to_python(self.text, MODELLED)
        exec(compile(source, "<generated-sampler>", "exec"), namespace)
        self.model = namespace["HookModel"]()
        for _type, name, value in _MEMBER.findall(self.text):
            setattr(self.model, name, eval(cep._enforce_expression(value), namespace) if value else None)
        self.model.m_HCProbeQuote = text_type('"')
        self.model.m_HCProbeFilter = STRICT_FILTER
        self.model.m_HCProbePlayerFilter = PLAYER_FILTER
        step = self.model.HCProbeStep

        def stepped():
            step()
            getattr(self.building, "tick", lambda: None)()
        self.model.HCProbeStep = stepped        # one hook tick is one game tick: the doors keep moving
        for name, value in (overrides or {}).items():
            setattr(self.model, name, value)
        self.model.m_HCProbeClasses.Insert(text_type(building.type_name))
        self.model.m_HCProbeRoles.Insert(text_type("tenement"))
        self.model.m_HCProbePositions.Insert(building.pos)
        for class_name, fx, fy, fz in frame_points:
            self.model.m_HCProbeFrameClasses.Insert(text_type(class_name))
            self.model.m_HCProbeFramePos.Insert((fx, fy, fz))

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


TERRAIN = None                      # ground: a contact with an empty result set
CRATE = SceneObject("Crate")
LAMP = SceneObject("StreetLamp")
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


class PartialNearTarget(NavMesh):
    """Every path to a point inside the building stops 0.4 m past it (a truncated-path reference model)."""

    def path(self, start, end, waypoints, flt=None):
        local = self.building.CoordToLocal(end)
        if local[0] > -5:
            self.paths += 1
            waypoints.Insert(start)
            waypoints.Insert(self.building.to_world((local[0] + 0.4, local[1], local[2])))
            return True
        return super().path(start, end, waypoints, flt)


def run_hidden_wall(hook_text):
    """A non-building object stands 0.1 m in front of the building wall on the snap ray (Sol P1)."""
    building = flat_building()
    walls = [Wall(building, "x", -0.2, -3.0, 2.0, 0.0, 3.0), Wall(CRATE, "x", -0.3, -3.0, 2.0, 0.0, 3.0)]
    return HookRun(hook_text, building, storey_planes(building), nav=snap_nav(building), walls=walls).run().row()


def run_small_snap(hook_text):
    """The mesh is 4 cm past a building wall: a snap far below the old 5 cm exemption (Sol P1)."""
    building = flat_building()
    return HookRun(hook_text, building, storey_planes(building), nav=snap_nav(building, east_from=-0.46),
                   walls=[Wall(building, "x", -0.48, -3.0, 2.0, 0.0, 3.0)]).run().row()


def run_final_gap_wall(hook_text):
    """The final waypoint is 0.4 m from the floor across a wall (Sol P2)."""
    building = flat_building()
    nav = PartialNearTarget(building, nav_for(building).zones, links=[("out", "g")])
    return HookRun(hook_text, building, storey_planes(building), nav=nav,
                   walls=[Wall(building, "x", -3.3, -3.0, 2.0, 0.0, 3.0)]).run().row()


def run_other_roof(hook_text):
    """Another object's roof covers the exterior seed (Sol P2): sheltered, not open sky."""
    building = flat_building()
    planes = storey_planes(building) + [Plane(CRATE, 2.0, -30, -5, -30, 30, "other-roof")]
    return HookRun(hook_text, building, planes, nav=nav_for(building)).run().row()


# A native-shaped building: the clipping box is symmetric about the origin and far larger than the
# building, the door sound position has an unreliable height, and every storey is cluttered with
# collision objects that are not the building (crates and the building's own proxy children).
NATIVE_BOX = ((-14.0, -10.0, -14.0), (14.0, 14.0, 14.0))
STOREY = 3.4


def native_building(yaw=0.0):
    building = SampBuilding("Land_Tenement_Big", (3000.0, 20.0, 5000.0), yaw=yaw, clip=NATIVE_BOX)
    building.doors = [building.to_world((-4.9, -6.35, -0.5))]
    return building


def native_planes(building, clutter=6):
    proxy = SceneObject("ProxyPart", parent=building)
    planes = [Plane(TERRAIN, -0.3, -50, 50, -50, 50, "terrain")]
    for storey in range(3):
        base = STOREY * storey
        planes.append(Plane(building, base, -4, 6, -3, 2, "floor"))
        planes.append(Plane(building, base + 2.9, -4, 6, -3, 2, "under"))
        for item in range(clutter):
            planes.append(Plane(proxy if item % 2 else CRATE, base + 0.4 + 0.3 * item, -4, 6, -3, 2, "other"))
    planes.append(Plane(building, 3 * STOREY - 0.3, -4, 6, -3, 2, "roof"))
    return planes


def native_nav(building):
    zones = [Zone("out", -45, -5, -45, 45, 0.0), Zone("g", -5, 7, -4, 3, 0.0)]
    return NavMesh(building, zones, links=[("out", "g")])


def run_native_shape(hook_text, clutter=6, **overrides):
    building = native_building()
    run = HookRun(hook_text, building, native_planes(building, clutter), nav=native_nav(building),
                  overrides=overrides).run()
    return run.row(), run


def storeys_with_clearance(row):
    return {round(h[1], 1) for h in row["hits"] if h[3] >= 1.9}


def tiny_building():
    return SampBuilding("Land_Tenement_Small", (3000.0, 20.0, 5000.0), clip=((-1.0, 0.0, -1.0), (1.0, 4.0, 1.0)))


def tiny_planes(building):
    """Per column from the top: owner underside 2.8, a proxy child 1.5, a crate 1.0, owner floor 0, ground -0.5."""
    proxy = SceneObject("ProxyPart", parent=building)
    return [Plane(building, 2.8, -5, 5, -5, 5, "under"), Plane(proxy, 1.5, -5, 5, -5, 5, "other"),
            Plane(CRATE, 1.0, -5, 5, -5, 5, "other"), Plane(building, 0.0, -5, 5, -5, 5, "floor"),
            Plane(TERRAIN, -0.5, -5, 5, -5, 5, "terrain")]


def run_tiny(hook_text, **overrides):
    building = tiny_building()
    return HookRun(hook_text, building, tiny_planes(building), ai=False, overrides=overrides).run().row()


def run_thick_clutter(hook_text, **overrides):
    """A 0.5 m thick crate over a floor: a downward ray restarted inside it re-reports it at its start."""
    building = tiny_building()
    planes = [Plane(building, 0.0, -5, 5, -5, 5, "floor"), Plane(building, 2.8, -5, 5, -5, 5, "under"),
              Plane(CRATE, 1.0, -5, 5, -5, 5, "other", thick=0.5)]
    return HookRun(hook_text, building, planes, ai=False, overrides=overrides).run().row()


def stage_of(row):
    return [attempt[2] for attempt in row["reach"]["attempts"]]


def run_no_seed_outside(hook_text):
    building = SampBuilding("Land_Tenement_Big", (3000.0, 20.0, 5000.0), clip=((-40.0, -1.0, -40.0), (40.0, 9.0, 40.0)))
    building.doors = [building.to_world((-4.9, 1.0, -0.5))]
    return HookRun(hook_text, building, [Plane(building, 0.0, -5, 5, -5, 5, "floor")], nav=native_nav(building)).run().row()


def run_sloped_ground(hook_text):
    """The ground at the entrance is 1 m below the building origin height (the door height is not used)."""
    building = flat_building()
    return HookRun(hook_text, building, storey_planes(building), nav=nav_for(building), ground_offset=-1.0).run().row()


def run_far_door_downhill(hook_text):
    """The terrain falls 2 m between the entrance and the far control door: the far sample must use SurfaceY there."""
    building = flat_building()
    zones = [Zone("near", -12, -5, -30, 30, 0.0), Zone("out", -30, -12, -30, 30, -2.0), Zone("g", -5, 7, -4, 3, 0.0)]
    nav = NavMesh(building, zones, links=[("near", "g"), ("near", "out")])
    run = HookRun(hook_text, building, storey_planes(building), nav=nav)
    base = run.game.ground
    run.game.SurfaceY = lambda x, z: base - 2.0 if building.CoordToLocal((x, base, z))[0] < -12.0 else base
    return run.run().row()


def run_far_unmeshed(hook_text):
    building = flat_building()
    zones = [Zone("out", -12, -5, -30, 30, 0.0), Zone("g", -5, 7, -4, 3, 0.0)]
    nav = NavMesh(building, zones, links=[("out", "g")])
    return HookRun(hook_text, building, storey_planes(building), nav=nav).run().row()


def run_single_waypoint(hook_text):
    building = flat_building()
    nav = nav_for(building, single_waypoint=True)
    return HookRun(hook_text, building, storey_planes(building), nav=nav).run().row()


def run_control_final_wall(hook_text):
    """The control path ends 0.4 m (inside the gap tolerance) from its far point, across a wall."""
    building = flat_building()
    nav = nav_for(building, partial_gap=0.4)
    walls = [Wall(building, "x", -16.64, -30.0, 30.0, 0.0, 3.0)]
    return HookRun(hook_text, building, storey_planes(building), nav=nav, walls=walls).run().row()


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
        return len(row["hits"]) == 96 and row["stats"]["floor_capped_columns"] == 16

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
        tested = [h for h in row["hits"] if h[3] >= 1.9 and h[5] in (0, 1)]
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
                and mesh_code(open_row, -0.5, 0.5) == 3 and mesh_code(loose, -0.5, 0.5) == 2)

    def snap_distance():
        far, near = run_snap_distance(hook_text)
        return mesh_code(far, -0.5, 0.5) == 2 and mesh_code(near, -0.5, 0.5) == 3

    def final_waypoint():
        short, trunc = run_final_waypoint(hook_text)
        far = storey_run(hook_text, nav=inside_nav(flat_building(), gap_x=0.85))
        return (short["reach"]["state"] == "tested" and mesh_code(short, -3.5, 0.5) == 3
                and trunc["reach"]["state"] == "tested" and mesh_code(trunc, -3.5, 0.5) == 3
                and far["reach"]["state"] == "tested" and mesh_code(far, -3.5, 0.5) == 0)

    def isolated_mesh():
        row, nav = run_isolated_mesh(hook_text)
        return row["reach"]["state"] != "tested" and {h[5] for h in row["hits"]} == {-1} and nav.paths == 0

    def seed_projection():
        row = run_seed_projection(hook_text)
        return row["reach"]["state"] != "tested" and {h[5] for h in row["hits"]} == {-1}

    def seed_standoff():
        row = run_seed_standoff(hook_text)
        entrances = row["reach"]["entrances"]
        return row["reach"]["state"] == "tested" and len(entrances) == 1 and entrances[0][0] < -6.0

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
        return (small["reach"]["state"] == "tested" and mesh_code(small, -3.5, 0.5) == 3
                and large["reach"]["state"] == "control-failed")

    def hidden_wall():
        row = run_hidden_wall(hook_text)
        return row["reach"]["state"] == "tested" and mesh_code(row, -0.5, 0.5) == 2

    def small_snap():
        row = run_small_snap(hook_text)
        return row["reach"]["state"] == "tested" and mesh_code(row, -0.5, 0.5) == 2

    def trivial_snap():
        building = flat_building()
        row = HookRun(hook_text, building, storey_planes(building), nav=snap_nav(building, east_from=-0.495)).run().row()
        return row["reach"]["state"] == "tested" and mesh_code(row, -0.5, 0.5) == 1

    def far_door_downhill():
        row = run_far_door_downhill(hook_text)
        return row["reach"]["state"] == "tested" and row["reach"]["player"]["state"] == "tested"

    def unknown_final_gap_ray():
        clear, _ = run_final_gap_with_ray(hook_text, 0)
        unknown, level = run_final_gap_with_ray(hook_text, -1)
        return level > 0 and mesh_code(clear, -3.5, 0.5) == 3 and mesh_code(unknown, -3.5, 0.5) == 0

    def blocked_fail_closed():
        clear, hit, run_capped, building_capped = blocked_answers(hook_text)
        return clear is False and hit is True and run_capped is True and building_capped is True

    def final_gap_wall():
        row = run_final_gap_wall(hook_text)
        building = flat_building()
        nav = PartialNearTarget(building, nav_for(building).zones, links=[("out", "g")])
        open_row = HookRun(hook_text, building, storey_planes(building), nav=nav).run().row()
        return (row["reach"]["state"] == "tested" and mesh_code(row, -3.5, 0.5) == 0
                and mesh_code(open_row, -3.5, 0.5) == 3)

    def other_roof():
        row = run_other_roof(hook_text)
        return (row["reach"]["state"] != "tested" and {h[5] for h in row["hits"]} == {-1}
                and stage_of(row) == [6])

    def native_shape():
        row, _run = run_native_shape(hook_text)
        stats = row["stats"]
        relations = stats["hit_relations"]
        return (storeys_with_clearance(row) == {0.0, STOREY, 2 * STOREY} and stats["step_capped_columns"] == 0
                and stats["floor_capped_columns"] == 0 and stats["clearance_capped"] == 0
                and relations["proxy"] > 0 and relations["other"] > 0 and relations["building"] > 0
                and row["reach"]["state"] == "tested" and row["reach"]["attempts"][0][1] == 11.0
                and mesh_code(row, -3.5, 0.5) == 3 and abs(row["reach"]["entrances"][0][1]) < 0.01
                and mesh_code(run_native_shape(hook_text, clutter=0)[0], -3.5, 0.5) == 1)

    def sloped_ground():
        row = run_sloped_ground(hook_text)
        return row["reach"]["state"] == "tested" and abs(row["reach"]["entrances"][0][1] + 1.0) < 0.01

    def clutter_floor_cap():
        row, _run = run_native_shape(hook_text, m_HCProbeHitLimit=8)
        return storeys_with_clearance(row) == {0.0, STOREY, 2 * STOREY} and row["stats"]["floor_capped_columns"] == 0

    def floor_cap():
        row = run_tiny(hook_text, m_HCProbeHitLimit=1)
        return row["stats"]["floor_capped_columns"] == 4 and row["hits"] == []

    def step_cap():
        row = run_tiny(hook_text, m_HCProbeStepLimit=3)
        return row["stats"]["step_capped_columns"] == 4 and row["stats"]["rays"] == 16

    def thick_clutter():
        row = run_thick_clutter(hook_text, m_HCProbeStepLimit=8)
        return (row["stats"]["step_capped_columns"] == 0 and row["stats"]["rehits"] == 12
                and {round(h[1], 1) for h in row["hits"]} == {0.0} and len(row["hits"]) == 4)

    def clearance_capped():
        building = tiny_building()
        proxy = SceneObject("ProxyPart", parent=building)
        planes = [Plane(building, 0.0, -5, 5, -5, 5, "floor"), Plane(building, 3.5, -5, 5, -5, 5, "under")]
        planes += [Plane(proxy, 0.3 + 0.15 * k, -5, 5, -5, 5, "other") for k in range(20)]
        row = HookRun(hook_text, building, planes, ai=False).run().row()
        return row["stats"]["clearance_capped"] == 4 and row["hits"] == []

    def waist_slot():
        row = run_waist_slot(hook_text)
        return row["reach"]["state"] == "tested" and mesh_code(row, -0.5, 0.5) == 3

    def final_gap_crate():
        building = flat_building()
        nav = PartialNearTarget(building, nav_for(building).zones, links=[("out", "g")])
        row = HookRun(hook_text, building, storey_planes(building), nav=nav,
                      walls=[Wall(CRATE, "x", -3.3, -3.0, 2.0, 0.0, 3.0)]).run().row()
        return row["reach"]["state"] == "tested" and mesh_code(row, -3.5, 0.5) == 0

    def obstruction():
        low = storey_run(hook_text, planes_extra=[Plane(CRATE, 1.2, -4, -3, 0, 1, "other")])
        solid = storey_run(hook_text, planes_extra=[Plane(CRATE, 2.4, -5, 7, -4, 3, "solid-block", thick=2.3)])
        return (mesh_code(low, -3.5, 0.5) == 3 and mesh_code(storey_run(hook_text), -3.5, 0.5) == 1
                and diag(low, "clearance_obstructed")["count"] > 0 and mesh_code(solid, -3.5, 0.5) == 3)

    def capped_unqualified():
        row = storey_run(hook_text, overrides={"m_HCProbeHitLimit": 2})
        capped = [h for h in candidates(row) if h[5] != -1]
        return len(capped) > 0 and {h[5] for h in capped} == {3} and diag(row, "column_capped")["count"] == len(capped)

    def owner_rehits():
        building = tiny_building()
        roof = Plane(building, 3.5, -5, 5, -5, 5, "owner-solid", thick=3.0)
        floor = Plane(building, 0.0, -5, 5, -5, 5, "floor")
        row = HookRun(hook_text, building, [roof, floor], ai=False).run().row()
        capped = HookRun(hook_text, building, [roof, floor], ai=False, overrides={"m_HCProbeStepLimit": 6}).run().row()
        return {round(h[1], 3) for h in row["hits"]} == {0.0} and len(row["hits"]) == 4 and capped["hits"] == []

    def player_variant():
        building = flat_building()
        row = storey_run(hook_text, nav=nav_for(building, player_links=[("out", "up")]))
        upstairs = [(h[5], row["player_codes"][i]) for i, h in enumerate(row["hits"])
                    if h[3] >= 1.9 and abs(h[1] - 3.0) < 0.1 and h[0] < 0.0]
        zones = [Zone("near", -12, -5, -30, 30, 0.0), Zone("far", -30, -12, -30, 30, 0.0), Zone("g", -5, 7, -4, 3, 0.0)]
        gate = HookRun(hook_text, building, storey_planes(building), nav=NavMesh(
            building, zones, links=[("near", "g")], player_links=[("near", "far")])).run().row()
        return (len(upstairs) > 4 and set(upstairs) == {(0, 1)} and gate["reach"]["state"] == "control-failed"
                and gate["reach"]["player"]["state"] == "tested" and 1 in gate["player_codes"])

    def variant_budget():
        row = storey_run(hook_text, overrides={"m_HCProbePathLimit": 3})
        return (row["stats"]["player_paths"] == 3 and row["stats"]["paths"] == 3
                and diag(row, "path_budget", "player")["count"] > 0)

    def vertical_allowance():
        small = storey_run(hook_text, nav=zoned(flat_building(), h=0.2))
        large = storey_run(hook_text, nav=zoned(flat_building(), h=0.4))
        low = storey_run(hook_text, nav=inside_nav(flat_building(), drop=0.2))
        high = storey_run(hook_text, nav=inside_nav(flat_building(), drop=0.4))
        return (diag(small, "reached")["count"] > 0 and diag(small, "snap_far")["count"] == 0
                and diag(large, "snap_far")["count"] > 0 and mesh_code(low, -3.5, 0.5) == 1
                and mesh_code(high, -3.5, 0.5) == 0)

    for name, function in (("floors", floors), ("rotation", rotation), ("grid", grid), ("reach", reach),
                           ("partial-path", partial_path), ("altitude", altitude), ("budgets", budgets),
                           ("run-budget", run_budget), ("hit-limit", hit_limit), ("reach-states", reach_states),
                           ("other-objects", other_objects), ("snap-wall", snap_wall),
                           ("snap-distance", snap_distance), ("final-waypoint", final_waypoint),
                           ("isolated-mesh", isolated_mesh), ("seed-projection", seed_projection),
                           ("seed-standoff", seed_standoff), ("overhang", overhang), ("sky-cap", sky_cap),
                           ("zero-paths", zero_paths), ("disconnected-control", disconnected_control),
                           ("end-tolerance", end_tolerance), ("hidden-wall", hidden_wall),
                           ("small-snap", small_snap), ("trivial-snap", trivial_snap), ("blocked-fail-closed", blocked_fail_closed),
                           ("unknown-final-gap-ray", unknown_final_gap_ray), ("far-door-downhill", far_door_downhill), ("final-gap-wall", final_gap_wall),
                           ("other-roof", other_roof), ("native-shape", native_shape),
                           ("sloped-ground", sloped_ground), ("clutter-floor-cap", clutter_floor_cap), ("floor-cap", floor_cap),
                           ("step-cap", step_cap), ("thick-clutter", thick_clutter),
                           ("clearance-capped", clearance_capped), ("waist-slot", waist_slot),
                           ("final-gap-crate", final_gap_crate), ("obstruction", obstruction),
                           ("capped-unqualified", capped_unqualified), ("owner-rehits", owner_rehits),
                           ("player-variant", player_variant), ("variant-budget", variant_budget),
                           ("vertical-allowance", vertical_allowance)):
        check(name, function)
    return failures


MUTATIONS = (
    ("hits on other objects accepted as the building", "if (found.Find(m_HCProbeBuilding) != -1)", "if (true)"),
    ("miss treated as a hit", "        if (!hit)\n            return 0;", "        if (hit)\n            return 0;"),
    ("same-slab spacing removed", "if (previousY - hitY >= 0.25)", "if (previousY - hitY >= -1.0)"),
    ("restart goes above the hit", "startY = hitY - offset;", "startY = hitY + offset;"),
    ("exterior hits kept", "if (clearance >= 0.0)", "if (true)"),
    ("clearance measured from the box", "return hitY - surfacePos[1];", "return hitY;"),
    ("upward ray starts below the surface", "float startY = surfacePos[1] + 0.05;", "float startY = surfacePos[1] - 0.05;"),
    ("upward range widened", "float endY = surfacePos[1] + 6.0;", "float endY = surfacePos[1] + 60.0;"),
    ("upward non-building hit ends the search", "if (result == 1)\n                return hitY - surfacePos[1];",
     "if (true)\n                return hitY - surfacePos[1];"),
    ("other-object hits become floors",
     "            if (rel == 1 && drop >= 0.02)\n            {\n                previousY = lastY;",
     "            if (drop >= 0.02)\n            {\n                previousY = lastY;"),
    ("grid step doubled", "edge = edge + m_HCProbeGridStep;", "edge = edge + 2.0;"),
    ("grid origin moved to the edge", "float edge = low + 0.5;", "float edge = low;"),
    ("hit limit removed", "if (floors >= m_HCProbeHitLimit)", "if (floors >= 99)"),
    ("step limit removed", "step < m_HCProbeStepLimit", "step < 99999"),
    ("floor cap counted for every hit", "            action = 0;\n            if (rel == 1)",
     "            action = 0;\n            floors = floors + 1;\n            if (rel == 1)"),
    ("re-hit offset never widens", "offset = usedOffset * 2.0;", "offset = 0.05;"),
    ("re-hit never detected", "if (drop < 0.02)", "if (drop < -1.0)"),
    ("clearance attempts cut short", "for (attempt = 0; attempt < 16; attempt++)", "for (attempt = 0; attempt < 2; attempt++)"),
    ("clearance restart does not advance", "startY = hitY + offset;", "startY = hitY;"),
    ("proxy children classified as the building", "if (found.Get(index).GetParent() == m_HCProbeBuilding)", "if (false)"),
    ("building ray cap removed", "m_HCProbeBuildingRays >= m_HCProbeBuildingRayLimit ||",
     "m_HCProbeBuildingRays >= 99999999 ||"),
    ("run ray cap removed", "|| m_HCProbeRunRays >= m_HCProbeRunRayLimit", "|| m_HCProbeRunRays >= 99999999"),
    ("model coordinates dropped",
     "vector modelPos = m_HCProbeBuilding.CoordToLocal(floorPos);",
     "vector modelPos = floorPos;"),
    ("path end gap widened",
     "if (m_HCProbeDiagHGap > m_HCProbeEndTolerance)",
     "if (m_HCProbeDiagHGap > 200.0)"),
    ("final waypoint not compared with the floor",
     "m_HCProbeDiagHGap = Math.Sqrt(gapX * gapX + gapZ * gapZ);",
     "m_HCProbeDiagHGap = 0.0;"),
    ("final gap level ray skipped",
     "if (m_HCProbeDiagHGap > m_HCProbeTrivialShift)",
     "if (false)"),
    ("final gap level ray never blocks", "if (HCProbeBlocked(Vector(finalPoint[0], waistY, finalPoint[2])",
     "if (false && HCProbeBlocked(Vector(finalPoint[0], waistY, finalPoint[2])"),
    ("reach computed without control",
     "if (state != \"tested\")\n            return -1;",
     "if (false)\n            return -1;"),
    ("control failure ignored",
     "if (stage != 5 && stage != 6)\n        {\n            HCProbeControlDetail(7 + stage, farSampled);",
     "if (false)\n        {\n            HCProbeControlDetail(7 + stage, farSampled);"),
    ("control path to its own start",
     "int stage = HCProbePath(entranceSampled, farSampled, farSampled, meshFilter);",
     "int stage = HCProbePath(entranceSampled, entranceSampled, entranceSampled, meshFilter);"),
    ("path budget removed", "if (m_HCProbeBuildingPaths >= m_HCProbePathLimit)", "if (false)"),
    ("comma separation removed", "if (m_HCProbeHitsEmitted > 0)", "if (false)"),
    ("outside point inside the building", "doorPos[0] + unitX * standoff", "doorPos[0] - unitX * standoff"),
    ("seed margin removed", "if (HCProbeOutsideBox(m_HCProbeSeed, m_HCProbeSeedMargin))", "if (true)"),
    ("seed ladder steps too far", "standoff = standoff + 1.0;", "standoff = standoff + 5.0;"),
    ("seed height from the door", "float ground = GetGame().SurfaceY(seedWorld[0], seedWorld[2]);", "float ground = seedWorld[1];"),
    ("projected seed may land inside", "if (!HCProbeOutsideBox(m_HCProbeSampledModel, m_HCProbeProjectedMargin))", "if (false)"),
    ("open sky not required", "if (!HCProbeOpenSky(entranceSampled))", "if (false)"),
    ("open-sky ignores other objects roofs", "if (m_HCProbeSkyResult == 0)\n            return true;",
     "if (m_HCProbeSkyResult != 1)\n            return true;"),
    ("snap displacement unbounded",
     "if (m_HCProbeDiagHSnap > m_HCProbeSnapLimit)",
     "if (m_HCProbeDiagHSnap > 99.0)"),
    ("waist wall ray skipped",
     "            if (snapRay != 0)\n                return HCProbeReachResult(variant, 2, floorPos);",
     "            if (false)\n                return HCProbeReachResult(variant, 2, floorPos);"),
    ("waist wall ray never blocks", "        if (result == 0)\n            return false;\n        return true;\n    }",
     "        if (result == 0)\n            return false;\n        return false;\n    }"),
    ("only building collisions block",
     "        if (result == 0)\n            return false;\n        return true;\n    }",
     "        if (result != 1)\n            return false;\n        return true;\n    }"),
    ("small snap shifts skip the wall ray",
     "if (m_HCProbeDiagHSnap > m_HCProbeTrivialShift)",
     "if (m_HCProbeDiagHSnap > 0.05)"),
    ("far control door uses the seed height", "float farGround = GetGame().SurfaceY(farWorld[0], farWorld[2]);",
     "float farGround = farWorld[1];"),
    ("unknown ray counts as clear", "        if (result == 0)\n            return false;\n        return true;\n    }\n\n    void HCProbeHitNote",
     "        if (result <= 0)\n            return false;\n        return true;\n    }\n\n    void HCProbeHitNote"),
    ("trivial snap threshold removed",
     "if (m_HCProbeDiagHSnap > m_HCProbeTrivialShift)",
     "if (m_HCProbeDiagHSnap > 0.0)"),
    ("owner re-hits become floors",
     "            if (rel == 1 && drop >= 0.02)\n            {\n                previousY = lastY;",
     "            if (rel == 1)\n            {\n                previousY = lastY;"),
    ("vertical gap ignored",
     "if (m_HCProbeDiagVGap > m_HCProbeVerticalAllowance)",
     "if (m_HCProbeDiagVGap > 99.0)"),
    ("vertical snap ignored",
     "if (m_HCProbeDiagVSnap > m_HCProbeVerticalAllowance)",
     "if (m_HCProbeDiagVSnap > 99.0)"),
    ("nontrivial snap authorizes reached",
     "return HCProbeReachResult(variant, 8, floorPos);",
     "return HCProbeReachResult(variant, 7, floorPos);"),
    ("nontrivial gap authorizes reached",
     "        if (stage == 6)\n            return HCProbeReachResult(variant, 9, floorPos);",
     "        if (stage == 6)\n            return HCProbeReachResult(variant, 7, floorPos);"),
    ("clear snap ray treated as blocked",
     "            if (snapRay != 0)\n                return HCProbeReachResult(variant, 2, floorPos);",
     "            if (true)\n                return HCProbeReachResult(variant, 2, floorPos);"),
    ("foreign obstruction not checked",
     "if (freeClear < m_HCProbeClearRequired)",
     "if (false)"),
    ("capped columns qualify",
     "        if (capKind > 0)\n            return HCProbeReachResult(variant, 11, floorPos);",
     "        if (false)\n            return HCProbeReachResult(variant, 11, floorPos);"),
    ("player variant uses the strict filter",
     "        if (variant == 1 || variant == 3)\n            m_HCProbeUsedFilter = m_HCProbePlayerFilter;",
     "        if (variant == 3)\n            m_HCProbeUsedFilter = m_HCProbePlayerFilter;"),
    ("player path budget removed",
     "if (m_HCProbePlayerPaths >= m_HCProbePathLimit)",
     "if (false)"),
)


class RenderTests(unittest.TestCase):
    def test_every_target_and_limit_is_inlined_as_literal_data(self):
        targets = sampler_targets()
        text = samp.render_hook(targets, sample_delay_s=75, run_ray_limit=123456, building_ray_limit=23456,
                                hit_limit=7, step_limit=11).decode()
        for target in targets:
            self.assertIn('HCProbeAdd("%s", "%s", %.6f, %.6f, %.6f);' % (target["class"], target["role"], *target["pos"]),
                          text)
        for needle in ("= 123456;", "= 23456;", "= 7;", "= 11;", "CallLater(HCProbeStart, 75000, false)"):
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
        self.assertNotEqual([], samp.lint_sampler_hook(base.replace("            return 1;\n        return 2;\n    }", "            return 1;\n        else\n            return 2;\n    }", 1)))
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

    def test_the_plus_count_is_taken_per_cleaned_statement_whatever_the_layout(self):
        base = default_hook()
        nine = '"x" + "y" + "z" + "x" + "y" + "z" + "x" + "y" + "z" + "x"'
        eight = '"x" + "y" + "z" + "x" + "y" + "z" + "x" + "y" + "z"'
        layouts = ("        string a = %s;", "        { string a = %s; }", "string a = %s;",
                   "        string a =\n            %s;", "        if (true) { string a = %s; }",
                   "        string a = %s; // + + +", "        /* + + + */ string a = %s;",
                   "        string a = \"+ + + + + + + + + +\" + %s;")
        for layout in layouts:
            with self.subTest(layout=layout):
                bad = base + "\n    void Bad()\n    {\n" + (layout % nine) + "\n    }\n"
                self.assertTrue(any("'+'" in issue for issue in samp.lint_sampler_hook(bad)), layout)
                inline = base + "\n    void Bad() { " + (layout % nine).replace("\n", " ") + " }\n"
                self.assertTrue(any("'+'" in issue for issue in samp.lint_sampler_hook(inline)), layout)
        for layout in layouts[:5]:
            with self.subTest(good=layout):
                good = base + "\n    void Ok()\n    {\n" + (layout % eight) + "\n    }\n"
                self.assertEqual([], samp.lint_sampler_hook(good), layout)

    def test_the_public_plus_counter_reports_the_largest_statement_of_the_generated_hook(self):
        text = default_hook()
        counts = samp.statement_plus_counts(text)
        self.assertTrue(counts)
        self.assertLessEqual(max(count for _line, count in counts), samp.MAX_PLUS_PER_STATEMENT)
        self.assertEqual([(3, 3)], samp.statement_plus_counts("a;\n\nx = 1 + 2 + 3 + 4;")[-1:])
        self.assertEqual(3, max(count for _line, count in samp.statement_plus_counts('x = a + b + c + d;')))
        self.assertEqual(0, max(count for _line, count in samp.statement_plus_counts('x = "+ + +"; // + + +\ny++;')))

    def test_functions_are_scanned_for_joined_numbers_and_undeclared_out_arguments_in_any_brace_layout(self):
        base = default_hook()
        shapes = {
            "inline": '\n    void Bad() { int c = 1; string a = "n" + c; }\n',
            "k-and-r": '\n    void Bad() {\n        int c = 1;\n        string a = "n" + c;\n    }\n',
            "two-space": '\n  void Bad()\n  {\n    int c = 1;\n    string a = "n" + c;\n  }\n',
            "tab": '\n\tvoid Bad()\n\t{\n\t\tint c = 1;\n\t\tstring a = "n" + c;\n\t}\n',
            "multi-line": '\n    void Bad()\n    {\n        int c = 1;\n        string a = "n"\n            + c;\n    }\n',
            "inside-the-class": None,
        }
        for name, shape in shapes.items():
            with self.subTest(name):
                if shape is None:
                    text = base.replace("    void HCProbeEmit(string text)",
                                        '    void Bad() { int c = 1; string a = "n" + c; }\n\n    void HCProbeEmit(string text)', 1)
                    self.assertNotEqual(base, text)
                else:
                    text = base + shape
                self.assertTrue(any("number" in issue for issue in samp.lint_sampler_hook(text)), name)
        out = ('\n    void Bad() { vector p; bool f = GetGame().GetWorld().GetAIWorld().SampleNavmeshPosition('
               'p, 1.0, m_HCProbeFilter, undeclared); }\n')
        self.assertTrue(any("out argument" in issue for issue in samp.lint_sampler_hook(base + out)))
        member = base.replace("    protected int m_HCProbeCursor = 0;", "  protected   int m_HCProbeCursor = 0;", 1)
        self.assertNotEqual(base, member)
        self.assertTrue(any("number" in issue for issue in samp.lint_sampler_hook(
            member + '\n    void Bad() { string a = "[" + m_HCProbeCursor + "]"; }\n')))
        self.assertEqual([], samp.lint_sampler_hook(base + '\n    void Ok() { int c = 1; string a = "n" + HCProbeInt(c); }\n'))

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
        frame_text = samp.render_hook(sampler_targets(), frame_points=[("Land_HouseBlock_2F1", 1.0, 0.1, 2.0)]).decode()
        names |= {m.group(1) for m in map(cep._SIGNATURE.match, frame_text.splitlines()) if m}
        loaders |= {n for n in names if re.fullmatch(r"HCProbeLoadFrame\d+", n)}
        self.assertTrue(loaders)
        self.assertEqual(set(), names - set(MODELLED) - UNMODELLED - loaders)
        self.assertEqual(set(), set(MODELLED) - names)

    def test_hook_only_observes_the_world(self):
        text = default_hook()
        for forbidden in (r"\bSetPosition\b", r"\bCreateObject", r"\bSpawn", r"\bDelete\b", r"\bSetOrientation\b",
                          r"\bTeleport", r"\bSetHealth\b", r"\bLockDoor", r"\bUnlockDoor", r"\bGetCEApi\b", r"\bExport"):
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
                       {"path_limit": -1}, {"output_limit": 10}, {"step_limit": 3}, {"step_limit": 513}):
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
        counts = {reason: diag(row, reason)["count"] for reason in REASONS}
        spent = sum(counts[r] for r in REASONS if r not in ("clearance_obstructed", "column_capped", "path_budget"))
        self.assertEqual(5, spent)                                        # limit 6 minus the control path
        self.assertGreater(counts["path_budget"], 10)
        self.assertEqual(counts["path_budget"], len([h for h in roofed if h[5] == -1]))
        self.assertEqual(6, row["stats"]["paths"])
        self.assertTrue(all(h[5] == -1 for h in row["hits"] if h[3] < 1.9))

    def test_mesh_snapping_across_a_wall_is_not_reachability(self):
        blocked, open_row, loose = run_snap_wall(self.hook)
        self.assertEqual("tested", blocked["reach"]["state"])
        self.assertEqual(3, mesh_code(open_row, -0.5, 0.5))      # same mesh, no wall, but a nontrivial snap: unqualified
        self.assertEqual(2, mesh_code(blocked, -0.5, 0.5))       # the snapped point is behind a building wall
        self.assertEqual(2, mesh_code(loose, -0.5, 0.5))         # any collision between the points blocks

    def test_the_snap_displacement_from_the_measured_floor_is_bounded(self):
        far, near = run_snap_distance(self.hook)
        self.assertEqual(3, mesh_code(near, -0.5, 0.5))          # 0.4 m: nontrivial snap, unqualified (round 3)
        self.assertEqual(2, mesh_code(far, -0.5, 0.5))           # 1.4 m: a different surface

    def test_the_final_waypoint_must_end_at_the_measured_floor_not_within_two_metres(self):
        short, trunc = run_final_waypoint(self.hook)
        self.assertEqual(3, mesh_code(short, -3.5, 0.5))         # 0.4 m mesh offset: unqualified (round 3)
        self.assertEqual("tested", trunc["reach"]["state"])      # the 0.45 m stop is inside the control tolerance
        self.assertEqual(3, mesh_code(trunc, -3.5, 0.5))         # the 0.4 m mesh offset is unqualified before any path
        far = storey_run(self.hook, nav=inside_nav(flat_building(), gap_x=0.85))
        self.assertEqual(0, mesh_code(far, -3.5, 0.5))           # a path that stops 0.85 m from the floor itself

    def test_the_path_end_tolerance_is_tight_enough_to_fail_a_truncated_control_path(self):
        small, large = run_end_tolerance(self.hook)
        self.assertEqual("tested", small["reach"]["state"])      # 0.3 m short is a complete path
        self.assertEqual(3, mesh_code(small, -3.5, 0.5))         # a 0.3 m final gap is unqualified, not reached
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
        self.assertLess(row["reach"]["entrances"][0][0], BOX[0][0] - 1.0)

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


class SafetyRegressionTests(unittest.TestCase):
    """Sol's re-review (hc-interior-review-002) of 68dd22f: four refusals that must hold."""

    def setUp(self):
        self.hook = default_hook()

    def test_a_wall_hidden_behind_a_nearer_non_building_object_does_not_allow_a_snap(self):
        row = run_hidden_wall(self.hook)
        self.assertEqual("tested", row["reach"]["state"])
        self.assertEqual(2, mesh_code(row, -0.5, 0.5))

    def test_a_snap_of_a_few_centimetres_still_has_its_wall_validated(self):
        row = run_small_snap(self.hook)
        self.assertEqual("tested", row["reach"]["state"])
        self.assertEqual(2, mesh_code(row, -0.5, 0.5))

    def test_the_far_control_door_is_sampled_at_the_terrain_height_there_not_at_the_seed_height(self):
        row = run_far_door_downhill(self.hook)
        self.assertEqual("tested", row["reach"]["state"])
        self.assertEqual("tested", row["reach"]["player"]["state"])

    def test_a_sub_centimetre_snap_is_trivial_and_does_not_need_a_waist_ray(self):
        building = flat_building()
        row = HookRun(self.hook, building, storey_planes(building), nav=snap_nav(building, east_from=-0.495)).run().row()
        self.assertEqual("tested", row["reach"]["state"])
        self.assertEqual(1, mesh_code(row, -0.5, 0.5))          # 5 mm of mesh quantisation is below the 1 cm trivial shift
        self.assertLess(sample_at(row, "reached", -0.5, 0.5)[2], 0.01)

    def test_a_final_waypoint_near_the_floor_but_across_a_wall_is_not_reached(self):
        row = run_final_gap_wall(self.hook)
        self.assertEqual("tested", row["reach"]["state"])
        self.assertEqual(0, mesh_code(row, -3.5, 0.5))

    def test_a_final_waypoint_near_the_floor_without_a_wall_still_counts(self):
        building = flat_building()
        nav = PartialNearTarget(building, nav_for(building).zones, links=[("out", "g")])
        row = HookRun(self.hook, building, storey_planes(building), nav=nav).run().row()
        self.assertEqual(3, mesh_code(row, -3.5, 0.5))          # clear, but a nontrivial final gap is unqualified

    def test_an_exterior_seed_under_another_objects_roof_is_not_open_sky(self):
        row = run_other_roof(self.hook)
        self.assertNotEqual("tested", row["reach"]["state"])
        self.assertEqual({-1}, {h[5] for h in row["hits"]})
        self.assertEqual([6], stage_of(row))

    def test_a_point_already_on_the_mesh_is_reached_without_any_level_wall_ray(self):
        building = flat_building()
        run = HookRun(self.hook, building, storey_planes(building), nav=nav_for(building),
                      walls=[Wall(building, "x", -0.2, -3.0, 2.0, 0.0, 3.0)]).run()
        self.assertEqual(1, mesh_code(run.row(), -3.5, 0.5))
        level = [call for call in run.scene.calls if abs(call[0][1] - call[1][1]) < 1e-9]
        self.assertEqual([], level)


class DescentTests(unittest.TestCase):
    """The descent must reach lower floors through clutter that is not the building (native evidence)."""

    def setUp(self):
        self.hook = default_hook()

    def test_every_storey_is_reached_through_native_shaped_clutter_within_the_default_budget(self):
        row, _run = run_native_shape(self.hook)
        self.assertEqual({0.0, STOREY, 2 * STOREY}, storeys_with_clearance(row))
        stats = row["stats"]
        self.assertEqual(0, stats["step_capped_columns"])
        self.assertEqual(0, stats["floor_capped_columns"])
        self.assertFalse(stats["ray_capped"])
        self.assertLess(stats["rays"], 150000)

    def test_clutter_that_is_not_the_building_does_not_count_against_the_floor_cap(self):
        row, _run = run_native_shape(self.hook, m_HCProbeHitLimit=8)
        self.assertEqual({0.0, STOREY, 2 * STOREY}, storeys_with_clearance(row))
        self.assertEqual(0, row["stats"]["floor_capped_columns"])

    def test_the_floor_cap_counts_only_the_buildings_own_surfaces_and_is_reported_separately(self):
        row = run_tiny(self.hook, m_HCProbeHitLimit=1)
        self.assertEqual(4, row["stats"]["floor_capped_columns"])
        self.assertEqual(0, row["stats"]["step_capped_columns"])
        self.assertEqual([], row["hits"])             # the one candidate it spent was the exterior 2.8 slab

    def test_the_step_cap_bounds_every_column_and_is_reported_separately(self):
        row = run_tiny(self.hook, m_HCProbeStepLimit=3)
        self.assertEqual(4, row["stats"]["step_capped_columns"])
        self.assertEqual(0, row["stats"]["floor_capped_columns"])
        self.assertEqual(16, row["stats"]["rays"])    # three descent rays and one clearance ray per column

    def test_an_uncapped_column_reports_neither_cap(self):
        row = run_tiny(self.hook)
        self.assertEqual((0, 0), (row["stats"]["step_capped_columns"], row["stats"]["floor_capped_columns"]))
        self.assertEqual({0.0}, {round(h[1], 1) for h in row["hits"]})
        self.assertEqual(4, len(row["hits"]))

    def test_restarting_inside_a_thick_object_widens_the_restart_offset_until_the_floor_is_reached(self):
        row = run_thick_clutter(self.hook, m_HCProbeStepLimit=8)
        self.assertEqual(0, row["stats"]["step_capped_columns"])
        self.assertEqual({0.0}, {round(h[1], 1) for h in row["hits"]})
        self.assertEqual(4, len(row["hits"]))
        self.assertEqual(12, row["stats"]["rehits"])       # three start-inside re-hits per column

    def test_a_restart_that_makes_progress_keeps_the_small_offset(self):
        row = run_tiny(self.hook)
        self.assertEqual(0, row["stats"]["rehits"])

    def test_clearance_is_found_through_clutter_that_is_not_the_building(self):
        row, _run = run_native_shape(self.hook)
        ground = [h for h in row["hits"] if round(h[1], 1) == 0.0 and round(h[0], 1) == -3.5 and round(h[2], 1) == 0.5]
        self.assertEqual(1, len(ground))
        self.assertAlmostEqual(2.9, ground[0][3], places=3)
        self.assertEqual(0, row["stats"]["clearance_capped"])

    def test_a_clearance_search_that_runs_out_of_attempts_is_counted_not_hidden(self):
        building = tiny_building()
        proxy = SceneObject("ProxyPart", parent=building)
        planes = [Plane(building, 0.0, -5, 5, -5, 5, "floor"), Plane(building, 3.5, -5, 5, -5, 5, "under")]
        planes += [Plane(proxy, 0.3 + 0.15 * k, -5, 5, -5, 5, "other") for k in range(20)]
        row = HookRun(self.hook, building, planes, ai=False).run().row()
        self.assertEqual(4, row["stats"]["clearance_capped"])
        self.assertEqual([], row["hits"])


class DiagnosticsTests(unittest.TestCase):
    """Bounded hook diagnostics that answer why the native descent exhausted its cap."""

    def setUp(self):
        self.hook = default_hook()

    def test_hit_relations_split_the_building_its_proxy_children_other_objects_and_ground(self):
        row = run_tiny(self.hook)
        stats = row["stats"]
        self.assertEqual({"none": 4, "building": 8, "proxy": 4, "other": 4}, stats["hit_relations"])
        self.assertEqual(12, stats["other_hits"])          # every descent hit that is not the building
        self.assertEqual([["ProxyPart", 4], ["Crate", 4]], stats["other_types"])
        self.assertEqual((4, 4), (stats["interior_hits"], stats["exterior_hits"]))

    def test_the_types_histogram_is_bounded_to_sixteen_distinct_types(self):
        building = tiny_building()
        planes = [Plane(building, 0.0, -5, 5, -5, 5, "floor")]
        planes += [Plane(SceneObject("Thing%d" % k), 0.5 + 0.1 * k, -5, 5, -5, 5, "other") for k in range(20)]
        row = HookRun(self.hook, building, planes, ai=False).run().row()
        names = [entry[0] for entry in row["stats"]["other_types"]]
        self.assertEqual(16, len(names))
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(entry[1] == 4 for entry in row["stats"]["other_types"]))
        self.assertEqual(80, row["stats"]["other_hits"])

    def test_a_capped_column_carries_its_hit_sequence_with_type_owner_relation_height_and_restart_distance(self):
        row = run_tiny(self.hook, m_HCProbeStepLimit=3)
        columns = row["diag"]["columns"]
        self.assertEqual(3, len(columns))
        first = columns[0]
        self.assertEqual((-0.5, -0.5, 3, 1, "step"), (first["x"], first["z"], first["steps"], first["floors"], first["cap"]))
        sequence = first["seq"]
        self.assertEqual([1, 2, 3], [entry[0] for entry in sequence])
        self.assertEqual([1, 2, 3], [entry[1] for entry in sequence])        # building, proxy child, other
        self.assertEqual([1, 1, 1], [entry[2] for entry in sequence])        # objects in the result set
        for entry, height, drop, offset in zip(sequence, (2.8, 1.5, 1.0), (1.7, 1.25, 0.45), (0.0, 0.05, 0.05)):
            self.assertAlmostEqual(height, entry[3], places=3)
            self.assertAlmostEqual(drop, entry[4], places=3)
            self.assertAlmostEqual(offset, entry[5], places=6)
            self.assertAlmostEqual(1.0, entry[6], places=6)                  # raw dirY
        self.assertEqual([3, 0, 0], [entry[7] for entry in sequence])        # exterior floor, other, other
        self.assertEqual(["Land_Tenement_Small", "ProxyPart", "Crate"], [entry[8] for entry in sequence])

    def test_only_the_first_three_heavy_columns_are_traced_and_a_light_column_is_not(self):
        light = run_tiny(self.hook)
        self.assertEqual([], light["diag"]["columns"])
        row = run_tiny(self.hook, m_HCProbeStepLimit=2)
        self.assertEqual(3, len(row["diag"]["columns"]))
        self.assertEqual({"step"}, {column["cap"] for column in row["diag"]["columns"]})

    def test_a_floor_capped_column_says_so_and_a_busy_uncapped_column_is_traced_too(self):
        row = run_tiny(self.hook, m_HCProbeHitLimit=1)
        self.assertEqual({"floor"}, {column["cap"] for column in row["diag"]["columns"]})
        busy, _run = run_native_shape(self.hook)
        columns = busy["diag"]["columns"]
        self.assertEqual(3, len(columns))
        self.assertEqual({"none"}, {column["cap"] for column in columns})
        self.assertTrue(all(column["steps"] >= 12 for column in columns))

    def test_the_trace_is_bounded_to_thirty_two_entries_per_column(self):
        building = tiny_building()
        planes = [Plane(building, 0.0, -5, 5, -5, 5, "floor")]
        planes += [Plane(CRATE, 0.5 + 0.1 * k, -5, 5, -5, 5, "other") for k in range(40)]
        row = HookRun(self.hook, building, planes, ai=False).run().row()
        self.assertEqual(3, len(row["diag"]["columns"]))
        self.assertTrue(all(len(c["seq"]) == 32 and c["steps"] > 32 for c in row["diag"]["columns"]))

    def test_a_start_inside_object_shows_as_a_zero_drop_re_hit_with_a_growing_restart_offset(self):
        row = run_thick_clutter(self.hook, m_HCProbeStepLimit=5)
        sequence = row["diag"]["columns"][0]["seq"]
        self.assertAlmostEqual(0.0, sequence[2][4], places=3)
        self.assertEqual([0.0, 0.05, 0.05, 0.1, 0.2], [round(entry[5], 6) for entry in sequence])

    def test_reach_attempts_record_stage_seed_sample_and_raw_values_for_a_passing_control(self):
        row, run = run_native_shape(self.hook)
        attempts = row["reach"]["attempts"]
        self.assertEqual(1, len(attempts))
        door, standoff, stage, seed, sampled, waypoints, gap = attempts[0]
        self.assertEqual((0, 11.0, 12), (door, standoff, stage))
        self.assertLess(seed[0], NATIVE_BOX[0][0] - 1.0)
        self.assertAlmostEqual(0.0, seed[1], places=3)                       # model height of the SurfaceY ground
        self.assertAlmostEqual(0.0, sampled[1], places=3)
        self.assertEqual(2.0, waypoints)
        self.assertAlmostEqual(0.0, gap, places=3)
        self.assertEqual("tested", row["reach"]["state"])
        self.assertGreater(len(run.game.surface_calls), 0)

    def test_each_control_failure_names_its_stage_and_the_raw_values(self):
        building = flat_building()
        planes = storey_planes(building)

        def attempt(row):
            return row["reach"]["attempts"][0]

        self.assertEqual([2], stage_of(run_no_seed_outside(self.hook)))
        zero, _nav = run_zero_paths(self.hook)
        self.assertEqual([3], stage_of(zero))
        isolated, _nav = run_isolated_mesh(self.hook)
        self.assertEqual([4], stage_of(isolated))
        projected = run_seed_projection(self.hook)
        self.assertEqual([5], stage_of(projected))
        self.assertGreater(attempt(projected)[6], 0.0)                       # how far the sample moved
        overhang = run_overhang(self.hook)
        self.assertEqual([6], stage_of(overhang))
        self.assertEqual(1.0, attempt(overhang)[5])                          # the sky ray's result: the building
        self.assertAlmostEqual(2.6, attempt(overhang)[6], places=3)          # and where it hit (model height)
        capped = run_sky_cap(self.hook)
        self.assertEqual([6], stage_of(capped))
        self.assertEqual(-1.0, attempt(capped)[5])
        self.assertEqual([7], stage_of(run_far_unmeshed(self.hook)))
        self.assertEqual([8], stage_of(run_disconnected_control(self.hook)))
        self.assertEqual([9], stage_of(run_single_waypoint(self.hook)))
        partial = HookRun(self.hook, building, planes, nav=nav_for(building, partial_gap=3.0)).run().row()
        self.assertEqual([10], stage_of(partial))
        self.assertEqual(2.0, attempt(partial)[5])
        self.assertAlmostEqual(3.0, attempt(partial)[6], places=3)
        self.assertEqual([11], stage_of(run_control_final_wall(self.hook)))
        for row in (partial, projected, overhang):
            self.assertEqual("control-failed", row["reach"]["state"])
            self.assertEqual({-1}, {h[5] for h in row["hits"]})
        self.assertEqual("control-failed", capped["reach"]["state"])
        self.assertEqual([], capped["hits"])                                 # no ray budget: nothing was scanned either

    def test_a_door_without_a_direction_is_recorded_as_stage_one(self):
        building = SampBuilding("Land_Tenement_Small", (3000.0, 20.0, 5000.0), clip=BOX)
        building.doors = [building.to_world((1.0, 1.0, -0.5))]                # exactly at the box centre
        row = HookRun(self.hook, building, storey_planes(building), nav=nav_for(building)).run().row()
        self.assertEqual([1], stage_of(row))
        self.assertEqual("control-failed", row["reach"]["state"])


class ControlSeedTests(unittest.TestCase):
    def setUp(self):
        self.hook = default_hook()

    def test_a_valid_exterior_seed_passes_for_a_symmetric_box_much_larger_than_the_building(self):
        row, _run = run_native_shape(self.hook)
        self.assertEqual("tested", row["reach"]["state"])
        codes = {(round(h[0], 1), round(h[2], 1), round(h[1], 1)): h[5] for h in row["hits"]}
        self.assertEqual(3, codes[(-3.5, 0.5, 0.0)])                         # crate/proxy clutter within 1.9 m
        self.assertEqual(3, codes[(-3.5, 0.5, STOREY)])                      # clutter there too (obstruction is checked first)
        clear, _run = run_native_shape(self.hook, clutter=0)
        self.assertEqual(1, mesh_code(clear, -3.5, 0.5))
        self.assertEqual(2, mesh_code(clear, -3.5, 0.5, STOREY))             # no navmesh under the upper floor
        self.assertLess(row["reach"]["entrances"][0][0], NATIVE_BOX[0][0] - 1.0)

    def test_the_seed_height_comes_from_the_ground_not_from_the_unreliable_door_height(self):
        row, _run = run_native_shape(self.hook)
        self.assertEqual("tested", row["reach"]["state"])
        self.assertEqual(-6.35, round(row["reach"]["doors"][0][1], 2))
        self.assertAlmostEqual(0.0, row["reach"]["entrances"][0][1], places=3)

    def test_the_seed_is_the_nearest_one_metre_standoff_outside_the_box_margin(self):
        row, _run = run_native_shape(self.hook)
        self.assertEqual(11.0, row["reach"]["attempts"][0][1])
        near = run_seed_standoff(self.hook)
        self.assertEqual(3.0, near["reach"]["attempts"][0][1])
        self.assertLess(near["reach"]["entrances"][0][0], BOX[0][0] - 1.0)

    def test_a_failed_seed_is_not_retried_farther_out_so_it_cannot_drift_onto_an_exterior_island(self):
        row = run_seed_projection(self.hook)
        self.assertEqual(1, len(row["reach"]["attempts"]))
        self.assertEqual("control-failed", row["reach"]["state"])

    def test_every_door_gets_one_attempt_record_until_a_control_passes(self):
        building = flat_building()
        building.doors = [building.to_world((-4.9, 1.0, -0.5)), building.to_world((0.0, 1.0, 2.9))]
        row = HookRun(self.hook, building, storey_planes(building), nav=nav_for(building)).run().row()
        self.assertEqual("tested", row["reach"]["state"])
        self.assertEqual([12], stage_of(row))                               # the second door is not needed
        self.assertEqual(2, len(row["reach"]["doors"]))
        failing = flat_building()
        failing.doors = [failing.to_world((-4.9, 1.0, -0.5)), failing.to_world((-4.9, 1.0, 0.5))]
        row = HookRun(self.hook, failing, storey_planes(failing), nav=nav_for(failing, partial_gap=3.0)).run().row()
        self.assertEqual([10, 10], stage_of(row))
        self.assertEqual("control-failed", row["reach"]["state"])


# ---------------------------------------------------------------------------
# Round 3: per-hit failure detail, the player filter variant, split snap/gap, control detail and the
# Sol hc-interior-review-003 addendum (obstruction, unqualified snap/gap, owner re-hits).
# Every scenario is explicit synthetic geometry; none of it establishes DayZ behavior.
# ---------------------------------------------------------------------------

REASONS = ("sample_failed", "snap_far", "snap_blocked", "path_not_found", "path_too_short", "gap_far",
           "gap_blocked", "reached", "snap_unqualified", "gap_unqualified", "clearance_obstructed",
           "column_capped", "path_budget")
CODE_OF_REASON = {"reached": 1, "sample_failed": 2, "snap_far": 2, "snap_blocked": 2, "path_not_found": 0,
                  "path_too_short": 0, "gap_far": 0, "gap_blocked": 0, "snap_unqualified": 3,
                  "gap_unqualified": 3, "clearance_obstructed": 3, "column_capped": 3, "path_budget": -1}
PLAYER_FLAGS = ("WALK", "DOOR", "INSIDE", "JUMP", "CLIMB", "CROUCH", "LADDER")
PLAYER_EXCLUDED = ("DISABLED", "UNREACHABLE", "SWIM", "SWIM_SEA")


class InsideNav(NavMesh):
    """Only paths that END inside the building (model x > -5) are altered: a lateral end gap, a height drop
    on the final waypoint, or a single-waypoint path. The exterior control path is never touched."""

    def __init__(self, *args, gap_x=0.0, drop=0.0, single=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.gap_x, self.drop, self.single = gap_x, drop, single

    def path(self, start, end, waypoints, flt=None):
        found = super().path(start, end, waypoints, flt)
        if not found or self.building.CoordToLocal(end)[0] <= -5:
            return found
        last = self.building.CoordToLocal(waypoints.Get(waypoints.Count() - 1))
        waypoints.Set(waypoints.Count() - 1, self.building.to_world((last[0] + self.gap_x, last[1] + self.drop, last[2])))
        if self.single:
            waypoints.Clear()
            waypoints.Insert(start)
        return True


def diag(row, reason, variant="strict"):
    return row["reach_diag"][variant].get(reason, {"count": 0, "samples": []})


def sample_at(row, reason, x, z, variant="strict"):
    for sample in diag(row, reason, variant)["samples"]:
        if abs(sample[0][0] - x) < 0.06 and abs(sample[0][2] - z) < 0.06:
            return sample
    raise AssertionError("no %s sample at %s,%s: %s" % (reason, x, z, diag(row, reason, variant)))


def candidates(row):
    return [h for h in row["hits"] if h[3] >= 1.9]


def zoned(building, h=0.0, **kwargs):
    zones = [Zone("out", -30, -5, -30, 30, 0.0), Zone("deck", -5, 7, -4, 3, h)]
    return NavMesh(building, zones, links=[("out", "deck")], **kwargs)


def inside_nav(building, **kwargs):
    return InsideNav(building, nav_for(building).zones, links=[("out", "g")], **kwargs)


def run_waist_slot(hook_text):
    """A closed room: a 0.2 m slot at waist height in the wall lets a zero-radius level ray through, but no
    player fits; the mesh is 0.4 m away on the other side (Sol P1-1)."""
    building = flat_building()
    walls = [Wall(building, "x", -0.2, -3, 2, 0, 0.9), Wall(building, "x", -0.2, -3, 2, 1.1, 3),
             Wall(building, "x", -1, -3, 2, 0, 3), Wall(building, "z", -3, -1, -0.2, 0, 3),
             Wall(building, "z", 2, -1, -0.2, 0, 3)]
    return HookRun(hook_text, building, storey_planes(building), nav=snap_nav(building), walls=walls).run().row()


def storey_run(hook_text, nav=None, planes_extra=(), **kwargs):
    building = flat_building()
    return HookRun(hook_text, building, storey_planes(building) + list(planes_extra),
                   nav=nav if nav is not None else nav_for(building), **kwargs).run().row()


class Round3DiagTests(unittest.TestCase):
    def setUp(self):
        self.hook = default_hook()

    def test_hit_rows_keep_six_fields_and_attempts_keep_seven(self):
        row = storey_run(self.hook)
        self.assertTrue(all(len(h) == 6 for h in row["hits"]))
        self.assertTrue(all(len(a) == 7 for a in row["reach"]["attempts"]))
        self.assertEqual(len(row["reach"]["attempts"]), len(row["reach"]["detail"]))
        self.assertEqual(len(row["hits"]), len(row["player_codes"]))

    def test_every_candidate_gets_exactly_one_exact_reason_and_the_code_follows_the_reason(self):
        row = storey_run(self.hook)
        self.assertEqual("tested", row["reach"]["state"])
        for reason in row["reach_diag"]["strict"]:
            self.assertIn(reason, REASONS)
        counts = {reason: diag(row, reason)["count"] for reason in REASONS}
        self.assertEqual(len(candidates(row)), sum(counts.values()))
        for code in (0, 1, 2, 3, -1):
            expected = sum(counts[r] for r in REASONS if CODE_OF_REASON[r] == code)
            self.assertEqual(expected, len([h for h in candidates(row) if h[5] == code]), code)
        for reason in ("reached", "path_not_found", "sample_failed", "clearance_obstructed"):
            self.assertGreater(counts[reason], 0, reason)

    def test_samples_are_bounded_to_eight_per_reason_while_the_count_keeps_going(self):
        row = storey_run(self.hook)
        reached = diag(row, "reached")
        self.assertGreater(reached["count"], 8)
        self.assertEqual(8, len(reached["samples"]))
        for variant in ("strict", "player"):
            for entry in row["reach_diag"][variant].values():
                self.assertLessEqual(len(entry["samples"]), 8)
                self.assertEqual(min(8, entry["count"]), len(entry["samples"]))

    def test_a_reached_sample_carries_floor_sampled_snap_waypoints_final_gap_and_blocker_fields(self):
        row = storey_run(self.hook)
        sample = sample_at(row, "reached", -3.5, 0.5)
        floor, sampled, h_snap, v_snap, waypoints, final, h_gap, v_gap, rel, kind = sample
        self.assertEqual(10, len(sample))
        self.assertEqual(0.0, round(floor[1], 2))
        self.assertAlmostEqual(0.0, h_snap, places=3)
        self.assertAlmostEqual(0.0, v_snap, places=3)
        self.assertEqual(2, waypoints)
        self.assertAlmostEqual(0.0, h_gap, places=3)
        self.assertAlmostEqual(0.0, v_gap, places=3)
        for point in (floor, sampled, final):
            self.assertEqual(3, len(point))
        self.assertEqual(0, rel)
        self.assertEqual("", kind)

    def test_a_failed_sample_reports_that_no_snap_was_measured(self):
        row = storey_run(self.hook)
        sample = sample_at(row, "sample_failed", 5.5, -2.5)
        self.assertEqual(-1.0, sample[2])
        self.assertEqual(-1.0, sample[3])
        self.assertEqual(0, sample[4])

    def test_the_horizontal_snap_and_the_vertical_snap_are_measured_separately(self):
        building = flat_building()
        far = HookRun(self.hook, building, storey_planes(building), nav=snap_nav(building, east_from=0.9)).run().row()
        sample = sample_at(far, "snap_far", -0.5, 0.5)
        self.assertAlmostEqual(1.4, sample[2], places=2)
        self.assertAlmostEqual(0.0, sample[3], places=3)
        row = storey_run(self.hook, nav=zoned(flat_building(), h=0.4))
        sample = diag(row, "snap_far")["samples"][0]
        self.assertAlmostEqual(0.0, sample[2], places=3)
        self.assertAlmostEqual(0.4, sample[3], places=2)
        self.assertEqual(2, mesh_code(row, sample[0][0], sample[0][2]))

    def test_a_small_vertical_offset_is_an_explicit_provisional_allowance_that_stays_reached(self):
        row = storey_run(self.hook, nav=zoned(flat_building(), h=0.2))
        self.assertEqual("tested", row["reach"]["state"])
        sample = diag(row, "reached")["samples"][0]
        self.assertAlmostEqual(0.2, sample[3], places=2)
        self.assertEqual(1, mesh_code(row, sample[0][0], sample[0][2]))
        self.assertRegex(self.hook, r"m_HCProbeVerticalAllowance = 0\.25;")
        self.assertRegex(self.hook, r"m_HCProbeTrivialShift = 0\.01;")

    def test_the_final_gap_is_split_and_a_vertical_gap_beyond_the_allowance_is_not_reached(self):
        reached = storey_run(self.hook, nav=inside_nav(flat_building(), drop=0.2))
        sample = sample_at(reached, "reached", -3.5, 0.5)
        self.assertAlmostEqual(0.0, sample[6], places=3)
        self.assertAlmostEqual(0.2, sample[7], places=2)
        far = storey_run(self.hook, nav=inside_nav(flat_building(), drop=0.4))
        sample = sample_at(far, "gap_far", -3.5, 0.5)
        self.assertAlmostEqual(0.4, sample[7], places=2)
        self.assertEqual(0, mesh_code(far, -3.5, 0.5))
        self.assertEqual("tested", far["reach"]["state"])

    def test_a_clear_lateral_final_gap_with_a_height_difference_casts_a_level_waist_ray_and_stays_unqualified(self):
        building = flat_building()
        run = HookRun(self.hook, building, storey_planes(building), nav=inside_nav(building, drop=0.2, gap_x=0.3)).run()
        row = run.row()
        self.assertEqual(3, mesh_code(row, -3.5, 0.5))
        sample = sample_at(row, "gap_unqualified", -3.5, 0.5)
        self.assertAlmostEqual(0.3, sample[6], places=2)
        level = [c for c in run.scene.calls if abs(c[0][1] - c[1][1]) < 1e-9
                 and abs(building.CoordToLocal(c[0])[1] - 1.0) < 1e-6]
        self.assertGreater(len(level), 0)

    def test_a_blocked_snap_records_which_object_stopped_the_waist_ray(self):
        blocked, _open_row, loose = run_snap_wall(self.hook)
        sample = sample_at(blocked, "snap_blocked", -0.5, 0.5)
        self.assertEqual(1, sample[8])
        self.assertEqual("Land_Tenement_Small", sample[9])
        sample = sample_at(loose, "snap_blocked", -0.5, 0.5)
        self.assertEqual(3, sample[8])
        self.assertEqual("Crate", sample[9])
        self.assertAlmostEqual(0.4, sample[2], places=2)

    def test_a_blocked_final_gap_and_a_far_final_gap_record_their_own_reasons(self):
        row = run_final_gap_wall(self.hook)
        sample = sample_at(row, "gap_blocked", -3.5, 0.5)
        self.assertEqual(1, sample[8])
        self.assertAlmostEqual(0.4, sample[6], places=2)
        far = storey_run(self.hook, nav=inside_nav(flat_building(), gap_x=0.85))
        sample = sample_at(far, "gap_far", -3.5, 0.5)
        self.assertAlmostEqual(0.85, sample[6], places=2)
        self.assertAlmostEqual(0.0, sample[2], places=3)

    def test_a_single_waypoint_path_is_path_too_short_and_a_locked_room_is_path_not_found(self):
        row = storey_run(self.hook, nav=inside_nav(flat_building(), single=True))
        self.assertGreater(diag(row, "path_too_short")["count"], 0)
        self.assertEqual(0, mesh_code(row, -3.5, 0.5))
        self.assertGreater(diag(storey_run(self.hook), "path_not_found")["count"], 0)

    def test_the_path_budget_and_capped_columns_are_reasons_not_silence(self):
        row = storey_run(self.hook, overrides={"m_HCProbePathLimit": 3})
        self.assertGreater(diag(row, "path_budget")["count"], 0)
        self.assertEqual(-1, candidates(row)[-1][5])
        capped = storey_run(self.hook, overrides={"m_HCProbeStepLimit": 3})
        tested = [h for h in candidates(capped) if h[5] != -1]
        self.assertGreater(len(tested), 0)
        self.assertEqual({3}, {h[5] for h in tested})
        self.assertEqual(len(tested), diag(capped, "column_capped")["count"])
        self.assertGreater(capped["stats"]["step_capped_columns"], 0)

    def test_the_diagnostics_are_bounded_for_sixteen_targets(self):
        row, _run = run_native_shape(self.hook)
        text = json.dumps(row["reach_diag"], separators=(",", ":"))
        self.assertLess(len(text), 30000)
        self.assertLess(len(json.dumps(row, separators=(",", ":"))) * 16, samp.DEFAULT_OUTPUT_LIMIT)
        self.assertLessEqual(max(len(e["samples"]) for v in row["reach_diag"].values() for e in v.values()), 8)


class Round3PlayerTests(unittest.TestCase):
    def setUp(self):
        self.hook = default_hook()

    def test_the_two_filters_are_distinct_objects_and_every_navmesh_call_receives_one(self):
        building = flat_building()
        nav = nav_for(building)
        HookRun(self.hook, building, storey_planes(building), nav=nav).run()
        self.assertEqual({id(STRICT_FILTER), id(PLAYER_FILTER)}, {id(f) for f in nav.filters})
        self.assertNotEqual(id(STRICT_FILTER), id(PLAYER_FILTER))

    def test_the_player_filter_may_use_a_link_that_the_strict_filter_cannot(self):
        building = flat_building()
        row = storey_run(self.hook, nav=nav_for(building, player_links=[("out", "up")]))
        upstairs = [(h, row["player_codes"][i]) for i, h in enumerate(row["hits"])
                    if h[3] >= 1.9 and abs(h[1] - 3.0) < 0.1 and h[0] < 0.0]
        self.assertGreater(len(upstairs), 4)
        self.assertEqual({(0, 1)}, {(h[5], code) for h, code in upstairs})
        ground = [(h[5], row["player_codes"][i]) for i, h in enumerate(row["hits"]) if abs(h[1]) < 0.1]
        self.assertTrue(all(strict == player for strict, player in ground))
        self.assertGreater(diag(row, "reached", "player")["count"], diag(row, "reached")["count"])
        self.assertEqual("tested", row["reach"]["player"]["state"])

    def test_the_gate_stays_strict_and_a_failing_strict_control_does_not_fail_the_player_control(self):
        building = flat_building()
        zones = [Zone("near", -12, -5, -30, 30, 0.0), Zone("far", -30, -12, -30, 30, 0.0), Zone("g", -5, 7, -4, 3, 0.0)]
        nav = NavMesh(building, zones, links=[("near", "g")], player_links=[("near", "far")])
        row = HookRun(self.hook, building, storey_planes(building), nav=nav).run().row()
        self.assertEqual("control-failed", row["reach"]["state"])
        self.assertEqual({-1}, {h[5] for h in row["hits"]})
        self.assertEqual("tested", row["reach"]["player"]["state"])
        self.assertIn(1, row["player_codes"])
        self.assertEqual({}, row["reach_diag"]["strict"])
        self.assertGreater(diag(row, "reached", "player")["count"], 0)

    def test_a_failing_player_control_leaves_the_player_codes_unknown_while_strict_is_tested(self):
        building = flat_building()
        zones = [Zone("near", -12, -5, -30, 30, 0.0), Zone("far", -30, -12, -30, 30, 0.0), Zone("g", -5, 7, -4, 3, 0.0)]
        nav = NavMesh(building, zones, links=[("near", "g"), ("near", "far")], player_only=[("near", "g")])
        row = HookRun(self.hook, building, storey_planes(building), nav=nav).run().row()
        self.assertEqual("tested", row["reach"]["state"])
        self.assertIn(1, {h[5] for h in row["hits"]})
        self.assertEqual("control-failed", row["reach"]["player"]["state"])
        self.assertEqual({-1}, set(row["player_codes"]))

    def test_each_filter_variant_has_its_own_path_budget(self):
        row = storey_run(self.hook, overrides={"m_HCProbePathLimit": 3})
        self.assertEqual(3, row["stats"]["paths"])
        self.assertEqual(3, row["stats"]["player_paths"])
        free = ("clearance_obstructed", "column_capped", "path_budget")
        for variant in ("strict", "player"):
            spent = sum(diag(row, r, variant)["count"] for r in REASONS if r not in free)
            self.assertEqual(2, spent, variant)
            self.assertGreater(diag(row, "path_budget", variant)["count"], 0, variant)

    def test_the_census_header_records_the_flag_constants_and_both_filters(self):
        building = flat_building()
        census = HookRun(self.hook, building, storey_planes(building), nav=nav_for(building)).run().census()
        filters = census["filters"]
        self.assertEqual({name: getattr(MockPolyFlags, name) for name in MockPolyFlags.NAMES}, filters["flags"])
        self.assertEqual({"include": STRICT_FILTER.include, "exclude": STRICT_FILTER.exclude, "exclusive": 0}, filters["strict"])
        self.assertEqual({"include": PLAYER_FILTER.include, "exclude": PLAYER_FILTER.exclude, "exclusive": 0}, filters["player"])

    def test_the_strict_filter_line_is_unchanged_and_the_player_filter_matches_the_brief(self):
        strict = re.search(r"m_HCProbeFilter\.SetFlags\(([^;]+)\);", self.hook)
        self.assertIsNotNone(strict)
        self.assertTrue(strict.group(1).startswith("PGPolyFlags.WALK | PGPolyFlags.DOOR | PGPolyFlags.INSIDE, "))
        player = re.search(r"m_HCProbePlayerFilter\.SetFlags\(([^;]+)\);", self.hook)
        self.assertIsNotNone(player)
        include, exclude, exclusive = (re.findall(r"PGPolyFlags\.(\w+)", part) for part in player.group(1).split(", "))
        self.assertEqual(set(PLAYER_FLAGS), set(include))
        self.assertEqual(7, len(include))
        self.assertEqual(set(PLAYER_EXCLUDED), set(exclude))
        self.assertEqual(["NONE"], exclusive)
        self.assertIn("m_HCProbePlayerFilter.SetCost(PGAreaType.DOOR_CLOSED, 1000);", self.hook)
        self.assertIn("m_HCProbeFilter.SetCost(PGAreaType.DOOR_CLOSED, 1000);", self.hook)

    @unittest.skipUnless(NATIVE_CACHE.is_dir(), "native script cache not extracted")
    def test_every_filter_flag_exists_in_the_native_pgpolyflags_enum(self):
        text = (NATIVE_CACHE / "3_Game/AI/AIWorld.c").read_text(errors="replace")
        enum = re.search(r"enum PGPolyFlags\s*\{(.*?)\}", text, re.S).group(1)
        names = re.findall(r"^\s*([A-Z_]+)\s*,?", enum, re.M)
        for flag in PLAYER_FLAGS + PLAYER_EXCLUDED + tuple(re.findall(r"PGPolyFlags\.(\w+)", self.hook)):
            self.assertIn(flag, names)
        self.assertIn("DOOR_CLOSED", re.search(r"enum PGAreaType\s*\{(.*?)\}", text, re.S).group(1))
        self.assertRegex(text, r"proto native void SetFlags\(int includeFlags, int excludeFlags, int exclusiveFlags\);")


class Round3ControlDetailTests(unittest.TestCase):
    def setUp(self):
        self.hook = default_hook()

    def test_a_stage_four_control_failure_reports_what_the_seed_sat_on(self):
        nav = NavMesh(flat_building(), [Zone("g", -5, 7, -4, 3, 0.0)])
        row = storey_run(self.hook, nav=nav, planes_extra=[Plane(CRATE, -0.2, -30, -5, -30, 30, "other")])
        self.assertEqual([4], stage_of(row))
        detail = row["reach"]["detail"][0]
        self.assertEqual(3, detail["rel"])
        self.assertEqual("Crate", detail["type"])
        self.assertAlmostEqual(-0.2, detail["hit_y"], places=2)
        self.assertEqual(3, len(detail["seed"]))
        plain = storey_run(self.hook, nav=nav)
        self.assertEqual(0, plain["reach"]["detail"][0]["rel"])
        self.assertEqual("", plain["reach"]["detail"][0]["type"])

    def test_a_stage_ten_control_failure_reports_the_sample_the_final_waypoint_and_the_hit_object(self):
        nav = nav_for(flat_building(), partial_gap=0.8)
        row = storey_run(self.hook, nav=nav, planes_extra=[Plane(CRATE, -0.2, -30, -5, -30, 30, "other")])
        self.assertEqual([10], stage_of(row))
        detail = row["reach"]["detail"][0]
        self.assertAlmostEqual(0.8, detail["h_gap"], places=2)
        self.assertAlmostEqual(0.0, detail["v_gap"], places=3)
        self.assertEqual(2, detail["waypoints"])
        self.assertAlmostEqual(0.8, detail["final"][0] - detail["sample"][0], places=2)
        self.assertEqual(3, detail["rel"])
        self.assertEqual("Crate", detail["type"])

    def test_other_stages_carry_an_empty_detail_object(self):
        row = storey_run(self.hook)
        self.assertEqual([{}], row["reach"]["detail"])
        self.assertEqual([{}], row["reach"]["player"]["detail"])

    def test_the_player_variant_has_its_own_attempts_and_detail(self):
        row = storey_run(self.hook, nav=nav_for(flat_building(), partial_gap=0.8))
        player = row["reach"]["player"]
        self.assertEqual("control-failed", player["state"])
        self.assertEqual([10], [a[2] for a in player["attempts"]])
        self.assertEqual(1, len(player["detail"]))
        self.assertAlmostEqual(0.8, player["detail"][0]["h_gap"], places=2)


class Round3AddendumTests(unittest.TestCase):
    """Sol hc-interior-review-003 of 9816612: P1-1 waist slot, P1-2 foreign obstruction, P2-3 owner re-hits."""

    def setUp(self):
        self.hook = default_hook()

    def slot_row(self):
        return run_waist_slot(self.hook)

    def assert_reached_is_trivial(self, row):
        for variant in ("strict", "player"):
            for sample in diag(row, "reached", variant)["samples"]:
                self.assertLessEqual(sample[2], 0.01)
                self.assertLessEqual(sample[6], 0.01)
                self.assertLessEqual(sample[3], 0.25)
                self.assertLessEqual(sample[7], 0.25)

    def test_a_clear_zero_radius_line_through_a_waist_slot_never_authorizes_a_snapped_point(self):
        row = self.slot_row()
        self.assertEqual("tested", row["reach"]["state"])
        self.assertEqual(3, mesh_code(row, -0.5, 0.5))
        sample = sample_at(row, "snap_unqualified", -0.5, 0.5)
        self.assertAlmostEqual(0.4, sample[2], places=2)
        index = [i for i, h in enumerate(row["hits"]) if (round(h[0], 1), round(h[2], 1), round(h[1], 1)) == (-0.5, 0.5, 0.0)][0]
        self.assertEqual(3, row["player_codes"][index])

    def test_a_nontrivial_snap_or_gap_is_never_reached_for_any_clear_geometry(self):
        for row in (self.slot_row(), storey_run(self.hook, nav=snap_nav(flat_building())), run_final_gap_wall(self.hook),
                    run_final_waypoint(self.hook)[0], storey_run(self.hook, nav=inside_nav(flat_building(), gap_x=0.3))):
            self.assert_reached_is_trivial(row)
            self.assertEqual(diag(row, "reached")["count"], len([h for h in candidates(row) if h[5] == 1]))
        row = storey_run(self.hook, nav=snap_nav(flat_building()))
        self.assertGreater(diag(row, "snap_unqualified")["count"], 0)
        for sample in diag(row, "snap_unqualified")["samples"]:
            self.assertEqual(3, mesh_code(row, round(sample[0][0], 1), round(sample[0][2], 1)))

    def test_a_point_under_a_low_foreign_object_is_obstructed_even_when_the_owner_ceiling_is_high(self):
        row = storey_run(self.hook, planes_extra=[Plane(CRATE, 1.2, -4, -3, 0, 1, "other")])
        self.assertEqual(3, mesh_code(row, -3.5, 0.5))
        hit = [h for h in row["hits"] if (round(h[0], 1), round(h[2], 1), round(h[1], 1)) == (-3.5, 0.5, 0.0)][0]
        self.assertGreaterEqual(hit[3], 1.9)                                   # the owner-ceiling field keeps its meaning
        sample = sample_at(row, "clearance_obstructed", -3.5, 0.5)
        self.assertEqual(0, sample[4])                                         # rejected before any path was asked
        self.assertEqual(1, mesh_code(storey_run(self.hook), -3.5, 0.5))      # the same cell without the object

    def test_a_solid_foreign_block_over_the_floor_is_not_free_player_clearance(self):
        solid = Plane(CRATE, 2.4, -5, 7, -4, 3, "solid-block", thick=2.3)
        row = storey_run(self.hook, planes_extra=[solid])
        self.assertEqual(3, mesh_code(row, -3.5, 0.5))
        self.assertGreater(diag(row, "clearance_obstructed")["count"], 10)
        self.assertEqual(0, len([h for h in candidates(row) if h[5] == 1 and abs(h[1]) < 0.1]))

    def test_owner_volume_rehits_never_become_floors_and_only_advance_the_descent(self):
        building = tiny_building()
        roof = Plane(building, 3.5, -5, 5, -5, 5, "owner-solid", thick=3.0)
        floor = Plane(building, 0.0, -5, 5, -5, 5, "floor")
        row = HookRun(self.hook, building, [roof, floor], ai=False).run().row()
        self.assertEqual({0.0}, {round(h[1], 3) for h in row["hits"]})
        self.assertEqual(4, len(row["hits"]))
        self.assertGreater(row["stats"]["rehits"], 0)
        capped = HookRun(self.hook, building, [roof, floor], ai=False, overrides={"m_HCProbeStepLimit": 6}).run().row()
        self.assertEqual([], capped["hits"])
        self.assertEqual(4, capped["stats"]["step_capped_columns"])
        actions = {entry[7] for column in capped["diag"]["columns"] for entry in column["seq"]}
        self.assertIn(5, actions)                                              # ignored re-hits are traced, not emitted

    def test_a_capped_column_keeps_its_floors_but_never_qualifies_them(self):
        row = storey_run(self.hook, overrides={"m_HCProbeHitLimit": 2})
        capped = [h for h in candidates(row) if h[5] != -1]
        self.assertGreater(row["stats"]["floor_capped_columns"], 0)
        self.assertGreater(len(capped), 0)
        self.assertEqual({3}, {h[5] for h in capped})
        self.assertEqual(len(capped), diag(row, "column_capped")["count"])


def run_final_gap_with_ray(hook_text, horizontal_result):
    """The final waypoint is 0.4 m short of the floor with no wall; every level (waist) ray answers ``horizontal_result``.

    Only the final-gap ray is level here (no snap, and the sky/descent/clearance rays are vertical), so this
    drives the HCProbeBlocked call site of the final gap with a chosen ray answer, including the unknown -1.
    """
    building = flat_building()
    nav = PartialNearTarget(building, nav_for(building).zones, links=[("out", "g")])
    run = HookRun(hook_text, building, storey_planes(building), nav=nav)
    original = run.model.HCProbeRay
    state = {"level_rays": 0}

    def ray(ray_from, ray_to):
        if abs(ray_from[1] - ray_to[1]) < 1e-6 and (abs(ray_from[0] - ray_to[0]) > 1e-6 or abs(ray_from[2] - ray_to[2]) > 1e-6):
            state["level_rays"] += 1
            run.model.m_HCProbeHitCount = 0
            run.model.m_HCProbeHitRel = 0
            run.model.m_HCProbeHitType = cep.S("")
            return horizontal_result
        return original(ray_from, ray_to)

    run.model.HCProbeRay = ray
    row = run.run().row()
    return row, state["level_rays"]


class Round5UnknownFinalGapRayTests(unittest.TestCase):
    """Round 5: an unknown (-1) answer on the final-gap level ray fails closed at the call site, not only in HCProbeBlocked."""

    def setUp(self):
        self.hook = default_hook()

    def test_a_clear_level_ray_leaves_a_nontrivial_final_gap_unqualified(self):
        row, level = run_final_gap_with_ray(self.hook, 0)
        self.assertGreater(level, 0)
        self.assertEqual(3, mesh_code(row, -3.5, 0.5))
        self.assertGreater(diag(row, "gap_unqualified")["count"], 0)

    def test_an_unknown_level_ray_blocks_the_final_gap_instead_of_leaving_it_unqualified(self):
        row, level = run_final_gap_with_ray(self.hook, -1)
        self.assertGreater(level, 0)
        self.assertEqual(0, mesh_code(row, -3.5, 0.5))
        self.assertGreater(diag(row, "gap_blocked")["count"], 0)
        self.assertEqual(0, diag(row, "gap_unqualified")["count"])


def blocked_answers(hook_text):
    """HCProbeBlocked called directly: a clear line, a line that hits something, and a ray the budget refuses."""
    building = flat_building()

    def ask(overrides, start, end):
        run = HookRun(hook_text, building, storey_planes(building), overrides=overrides)
        run.model.m_HCProbeBuilding = building
        return run.model.HCProbeBlocked(building.to_world(start), building.to_world(end))

    return (ask(None, (0.0, 50.0, 0.0), (1.0, 50.0, 0.0)),
            ask(None, (0.0, 50.0, 0.0), (0.0, -50.0, 0.0)),
            ask({"m_HCProbeRunRayLimit": 0}, (0.0, 50.0, 0.0), (1.0, 50.0, 0.0)),
            ask({"m_HCProbeBuildingRayLimit": 0}, (0.0, 50.0, 0.0), (1.0, 50.0, 0.0)))


class Round4BlockedTests(unittest.TestCase):
    """Round 4: an unknown ray (-1, budget refused) is blocked, never clear (survivor unknown-ray-clear)."""

    def setUp(self):
        self.hook = default_hook()

    def test_an_unknown_ray_counts_as_blocked_and_only_a_real_miss_is_clear(self):
        clear, hit, run_capped, building_capped = blocked_answers(self.hook)
        self.assertFalse(clear)                         # result 0: a real miss
        self.assertTrue(hit)                            # result 1 or 2: something is in the way
        self.assertTrue(run_capped)                     # result -1: the run ray budget refused the ray
        self.assertTrue(building_capped)                # result -1: the per-building ray budget refused it

    def test_a_refused_ray_is_reported_as_capped_not_as_a_miss(self):
        building = flat_building()
        run = HookRun(self.hook, building, storey_planes(building), overrides={"m_HCProbeRunRayLimit": 0})
        self.assertEqual(-1, run.model.HCProbeRay(building.to_world((0.0, 50.0, 0.0)), building.to_world((1.0, 50.0, 0.0))))
        self.assertTrue(run.model.m_HCProbeRayCapped)


class SamplerWorkspace(cep.Workspace):
    def setUp(self):
        super().setUp()
        proto = mock.patch.object(cep, "SYNTH_PROTO", SAMPLER_PROTO)
        proto.start()
        self.addCleanup(proto.stop)
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
        self.assertEqual({"grid_step": 1.0, "per_class": 4, "intersect": "geom", "step_limit": 64},
                         {k: plan["sampler"][k] for k in ("grid_step", "per_class", "intersect", "step_limit")})
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


SAMPLER_PROTO = (
    b'<prototype>'
    b'<group name="Land_Tenement_Small" lootmax="0" />'
    b'<group name="Land_HouseBlock_2F1" lootmax="6"><container name="lootFloor" lootmax="3">'
    b'<point pos="1.5 0.1 3.0" range="1.0" height="1.5" /><point pos="-1.0 0.1 -3.5" range="1.0" height="1.5" />'
    b'<point pos="0.0 0.1 0.0" range="1.0" height="1.5" /></container>'
    b'<container name="shelves" lootmax="2"><point pos="9.0 1.0 9.0" range="1.0" height="1.5" /></container></group>'
    b'<group name="Land_Mil_Barracks2" lootmax="6"><container name="lootFloor" lootmax="3">'
    b'<point pos="2.0 0.1 1.0" range="1.0" height="1.5" /></container></group>'
    b'</prototype>\n')


def gated_run(hook_text, building=None, overrides=None, planes=None):
    """One door gating the only zone link: with it closed nothing inside the building is reachable."""
    building = building or flat_building()
    building.state[0] = False
    nav = DoorGatedNav(building, nav_for(building).zones, links=[("out", "g")])
    run = HookRun(hook_text, building, planes or storey_planes(building), nav=nav, overrides=overrides)
    return run.run(), building


def ones(codes):
    return sum(1 for code in codes if code == 1)


class Round5FrameCheckTests(unittest.TestCase):
    """Vertical raycasts at each stock lootFloor point under the as-is and the rotate +90 transforms."""

    POINTS = [("Land_Tenement_Small", 1.5, 0.1, 3.0), ("Land_Tenement_Small", -1.0, 0.1, -3.5),
              ("Land_Tenement_Small", 0.0, 0.1, 0.0), ("Land_Tenement_Small", 5.0, 0.1, 0.0)]

    def frame_row(self, points=POINTS, hook=None):
        building = flat_building()
        run = HookRun(hook or samp.render_hook(sampler_targets(), frame_points=points).decode(), building,
                      storey_planes(building), nav=nav_for(building), frame_points=points)
        return run.run().row()

    def test_each_record_holds_the_stock_point_and_the_two_vertical_ray_answers(self):
        row = self.frame_row()
        self.assertEqual(4, len(row["frame"]))
        for record in row["frame"]:
            self.assertEqual(7, len(record))
        by_point = {(r[0], r[2]): r for r in row["frame"]}
        rot_only, as_is_only, both = by_point[(1.5, 3.0)], by_point[(5.0, 0.0)], by_point[(0.0, 0.0)]
        self.assertEqual((0, 1), (rot_only[3], rot_only[5]))        # sampler = (-z, y, x) = (-3.0, 0.1, 1.5)
        self.assertEqual((1, 0), (as_is_only[3], as_is_only[5]))
        self.assertEqual((1, 1), (both[3], both[5]))
        self.assertAlmostEqual(0.0, both[4], places=3)               # the contact height in the building frame
        self.assertEqual((0, 1), (by_point[(-1.0, -3.5)][3], by_point[(-1.0, -3.5)][5]))

    def test_the_check_uses_two_rays_per_point_from_the_building_ray_budget(self):
        building = flat_building()
        plain = HookRun(default_hook(), building, storey_planes(building), nav=nav_for(building)).run().row()
        row = self.frame_row()
        self.assertEqual(plain["stats"]["rays"] + 2 * len(self.POINTS), row["stats"]["rays"])

    def test_a_class_without_frame_points_carries_no_frame_records_and_no_extra_rays(self):
        building = flat_building()
        plain = HookRun(default_hook(), building, storey_planes(building), nav=nav_for(building)).run().row()
        self.assertNotIn("frame", plain)
        row = self.frame_row(points=[("Land_Mil_Barracks2", 1.0, 0.1, 1.0)])
        self.assertEqual([], row.get("frame", []))
        self.assertEqual(plain["stats"]["rays"], row["stats"]["rays"])

    def test_the_default_hook_inlines_no_frame_points_and_a_staged_one_inlines_them_as_literals(self):
        self.assertNotIn('HCProbeFrameAdd("', default_hook())
        text = samp.render_hook(sampler_targets(), frame_points=[("Land_HouseBlock_2F1", 1.5, 0.1, 3.0)]).decode()
        self.assertIn('HCProbeFrameAdd("Land_HouseBlock_2F1", 1.500000, 0.100000, 3.000000);', text)
        self.assertEqual([], samp.lint_sampler_hook(text))

    def test_frame_points_are_validated(self):
        for bad in ([("Not A Class", 0.0, 0.0, 0.0)], [("Land_HouseBlock_2F1", float("nan"), 0.0, 0.0)],
                    [("Land_HouseBlock_2F1", 1e7, 0.0, 0.0)], [("Land_HouseBlock_2F1", 1.0, 2.0)],
                    [("Land_HouseBlock_2F1", 0.0, 0.0, 0.0)] * (samp.MAX_FRAME_POINTS + 1)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                samp.render_hook(sampler_targets(), frame_points=bad)


class Round5DoorRunTests(unittest.TestCase):
    def setUp(self):
        self.hook = default_hook()

    def test_the_hook_opens_unlocked_doors_and_restores_them_and_never_locks_or_moves_anything(self):
        for needle in ("OpenDoor(", "CloseDoor(", "IsDoorClosed(", "IsDoorLocked(", "m_HCProbeDoorDelayTicks"):
            self.assertIn(needle, self.hook)
        self.assertEqual(1, self.hook.count(".OpenDoor("))
        self.assertEqual(1, self.hook.count(".CloseDoor("))
        for forbidden in (r"\bLockDoor", r"\bUnlockDoor", r"\bSetPosition\b", r"\bDelete\b"):
            self.assertIsNone(re.search(forbidden, self.hook), forbidden)

    def test_every_door_is_recorded_beyond_the_old_four_door_cap_with_its_locked_and_open_state(self):
        building = flat_building()
        building.doors = [building.to_world((-4.9 + 0.1 * i, 1.0, -0.5)) for i in range(6)]
        building.locked = {2}
        building.state = {3: True, 4: True, 5: True}
        row = HookRun(self.hook, building, storey_planes(building), nav=nav_for(building)).run().row()
        run = row["door_run"]
        self.assertEqual(6, run["count"])
        self.assertEqual(1, run["locked"])
        self.assertEqual(6, run["open_at_start"])
        self.assertEqual(6, len(run["doors"]))
        self.assertEqual(6, len(row["reach"]["doors"]))
        self.assertEqual([0, 0, 1, 0, 0, 0], [d[3] for d in run["doors"]])
        self.assertEqual([1, 1, 1, 1, 1, 1], [d[4] for d in run["doors"]])
        self.assertAlmostEqual(-4.8, run["doors"][1][0], places=3)

    def test_a_building_whose_doors_are_all_open_or_locked_is_not_touched_and_copies_its_codes(self):
        for locked, state in ((set(), {}), ({0}, {0: False})):
            building = flat_building()
            building.locked, building.state = locked, dict(state)
            row = HookRun(self.hook, building, storey_planes(building), nav=nav_for(building)).run().row()
            with self.subTest(locked=sorted(locked)):
                self.assertEqual([], building.ops)
                self.assertEqual("no-change", row["door_run"]["state"])
                self.assertEqual(0, row["door_run"]["opened"])
                self.assertEqual([h[5] for h in row["hits"]], row["open_codes"])
                self.assertEqual(row["player_codes"], row["open_player_codes"])
                self.assertEqual(row["entered"]["strict"]["closed"], row["entered"]["strict"]["open"])

    def test_a_building_without_doors_copies_the_codes_and_says_so(self):
        building = flat_building()
        building.doors = []
        row = HookRun(self.hook, building, storey_planes(building), nav=nav_for(building)).run().row()
        self.assertEqual("no-door", row["door_run"]["state"])
        self.assertEqual(0, row["door_run"]["count"])
        self.assertEqual([h[5] for h in row["hits"]], row["open_codes"])
        self.assertEqual("untested", row["entered"]["strict"]["open"])

    def test_closed_doors_are_opened_the_codes_are_recorded_again_and_the_doors_are_closed_again(self):
        run, building = gated_run(self.hook)
        row = run.row()
        self.assertEqual([("open", 0), ("close", 0)], building.ops)
        self.assertTrue(building.IsDoorClosed(0))
        door_run = row["door_run"]
        self.assertEqual((1, 1, 1, "done"), (door_run["opened"], door_run["observed_open"], door_run["restored"], door_run["state"]))
        self.assertEqual(0, door_run["open_at_start"])
        self.assertEqual(len(row["hits"]), len(row["open_codes"]))
        self.assertEqual(len(row["hits"]), len(row["open_player_codes"]))
        self.assertEqual(len(row["hits"]), len(row["player_codes"]))
        self.assertEqual(0, ones([h[5] for h in row["hits"]]))
        self.assertGreater(ones(row["open_codes"]), 0)
        self.assertGreater(ones(row["open_player_codes"]), 0)
        self.assertEqual(0, ones(row["player_codes"]))

    def test_the_control_through_a_closed_door_does_not_enter_and_through_the_open_door_it_does(self):
        row = gated_run(self.hook)[0].row()
        self.assertEqual("tested", row["reach"]["state"])
        self.assertEqual({"closed": "not-entered", "open": "entered"}, row["entered"]["strict"])
        self.assertEqual({"closed": "not-entered", "open": "entered"}, row["entered"]["player"])

    def test_a_door_that_does_not_gate_anything_gives_equal_codes_and_an_entered_control_in_both_runs(self):
        building = flat_building()
        building.state[0] = False
        row = HookRun(self.hook, building, storey_planes(building), nav=nav_for(building)).run().row()
        self.assertEqual([("open", 0), ("close", 0)], building.ops)
        self.assertEqual([h[5] for h in row["hits"]], row["open_codes"])
        self.assertEqual({"closed": "entered", "open": "entered"}, row["entered"]["strict"])

    def test_the_open_control_tries_later_doors_until_one_enters(self):
        building = flat_building()
        building.doors = [building.to_world((-4.9, 1.0, 20.0)), building.to_world((-4.9, 1.0, -0.5))]
        building.state = {0: False, 1: False}
        nav = DoorGatedNav(building, nav_for(building).zones, gate=1, links=[("out", "g")])
        row = HookRun(self.hook, building, storey_planes(building), nav=nav).run().row()
        self.assertEqual("entered", row["entered"]["strict"]["open"])
        self.assertGreater(ones(row["open_codes"]), 0)

    def test_the_delay_between_opening_and_closing_is_the_bounded_tick_count(self):
        for ticks in (3, 11):
            building = flat_building()
            building.state[0] = False
            nav = DoorGatedNav(building, nav_for(building).zones, links=[("out", "g")])
            run = HookRun(self.hook, building, storey_planes(building), nav=nav, overrides={"m_HCProbeDoorDelayTicks": ticks})
            run.model.HCProbeHeader(cep.S("chernarusplus"), cep.S("1.30.test"))
            steps, seen = 0, {}
            while run.sentinel() is None and steps < 100000:
                run.model.HCProbeStep()
                steps += 1
                for index, op in enumerate(building.ops):
                    seen.setdefault(op, steps)
            with self.subTest(ticks=ticks):
                self.assertGreaterEqual(seen[("open", 0)], 1)
                self.assertGreaterEqual(seen[("close", 0)] - seen[("open", 0)], ticks)
                self.assertTrue(run.census()["placements"][0]["door_run"]["delay_ticks"] == ticks)

    def test_a_capped_building_is_not_opened_and_its_doors_are_left_as_found(self):
        building = flat_building()
        building.state[0] = False
        nav = DoorGatedNav(building, nav_for(building).zones, links=[("out", "g")])
        row = HookRun(self.hook, building, storey_planes(building), nav=nav,
                      overrides={"m_HCProbeBuildingRayLimit": 120}).run().row()
        self.assertEqual([], building.ops)
        self.assertEqual("skipped-capped", row["door_run"]["state"])
        self.assertEqual(len(row["hits"]), len(row["open_codes"]))
        self.assertTrue(row["stats"]["ray_capped"])

    def test_open_pass_paths_are_counted_apart_so_the_closed_counters_do_not_change(self):
        run, _building = gated_run(self.hook)
        stats = run.row()["stats"]
        self.assertGreater(stats["open_paths"], 0)
        self.assertGreater(stats["open_player_paths"], 0)
        building = flat_building()
        plain = HookRun(self.hook, building, storey_planes(building), nav=nav_for(building)).run().row()["stats"]
        self.assertEqual(0, plain["open_paths"])

    @staticmethod
    def player_gain(hook):
        building = flat_building()
        building.state[0] = False
        nav = DoorGatedNav(building, nav_for(building).zones, links=[("out", "g")], player_links=[("out", "up")])
        row = HookRun(hook, building, storey_planes(building), nav=nav).run().row()
        return ones(row["open_player_codes"]) - ones(row["open_codes"])

    def test_the_open_player_run_uses_the_player_filter_and_the_open_strict_run_does_not(self):
        self.assertGreater(self.player_gain(self.hook), 0)
        old = "        if (variant == 1 || variant == 3)\n            m_HCProbeUsedFilter = m_HCProbePlayerFilter;"
        self.assertEqual(1, self.hook.count(old))
        mutant = self.hook.replace(old, "        if (variant == 1)\n            m_HCProbeUsedFilter = m_HCProbePlayerFilter;")
        self.assertEqual(0, self.player_gain(mutant))

    def test_reach_diag_names_the_open_runs(self):
        row = gated_run(self.hook)[0].row()
        self.assertEqual({"strict", "player", "strict_open", "player_open"}, set(row["reach_diag"]))
        self.assertIn("reached", row["reach_diag"]["strict_open"])
        self.assertNotIn("reached", row["reach_diag"]["strict"])


class Round6DoorPhaseTests(unittest.TestCase):
    """Sol r5 P2: IsDoorOpen(int) is the REQUESTED phase (Building.c:33). The actual state is IsDoorOpened /
    IsDoorOpenedAjar / IsDoorClosed (:45/:51); the run waits for it with a bounded settle and says so when it stalls."""

    def setUp(self):
        self.hook = default_hook()

    def gated(self, lag=2, stuck=None, overrides=None, extra_doors=0, setup=None):
        return self.gated_with(self.hook, lag, stuck, overrides, extra_doors, setup)

    @staticmethod
    def gated_with(hook, lag=2, stuck=None, overrides=None, extra_doors=0, setup=None):
        building = flat_building()
        building.doors = [building.doors[0]] + [building.to_world((-4.9 + 0.1 * (i + 1), 1.0, -0.5))
                                                 for i in range(extra_doors)]
        building.state[0] = False
        building.lag = lag
        building.stuck = dict(stuck or {})
        if setup:
            setup(building)
        nav = DoorGatedNav(building, nav_for(building).zones, links=[("out", "g")])
        run = HookRun(hook, building, storey_planes(building), nav=nav, overrides=overrides)
        return run.run(), building

    def test_the_hook_reads_the_actual_door_phase_and_never_the_requested_one(self):
        self.assertIsNone(re.search(r"\bIsDoorOpen\(", self.hook))
        for needle in ("IsDoorOpened(", "IsDoorClosed(", "IsDoorOpenedAjar(", "m_HCProbeDoorSettleTicks"):
            self.assertIn(needle, self.hook)

    def test_a_door_that_moves_slower_than_the_fixed_delay_is_waited_for_with_a_bounded_settle(self):
        run, building = self.gated(lag=6, overrides={"m_HCProbeDoorDelayTicks": 1})
        row = run.row()
        door_run = row["door_run"]
        self.assertEqual("done", door_run["state"])
        self.assertEqual((1, 1, 1), (door_run["opened"], door_run["observed_open"], door_run["restored"]))
        self.assertGreater(ones(row["open_codes"]), 0, "the open pass ran before the door actually opened")
        self.assertEqual({"closed": "not-entered", "open": "entered"}, row["entered"]["strict"])
        self.assertGreater(door_run["open_settle_ticks"], 0)
        self.assertGreater(door_run["close_settle_ticks"], 0)
        self.assertTrue(building.IsDoorClosed(0))

    def test_a_fast_door_needs_no_settle_ticks(self):
        door_run = self.gated(lag=1)[0].row()["door_run"]
        self.assertEqual((0, 0), (door_run["open_settle_ticks"], door_run["close_settle_ticks"]))

    def test_the_settle_is_bounded_and_a_close_that_never_completes_fails_explicitly(self):
        run, building = self.gated(stuck={0: {"close"}})
        row = run.row()
        door_run = row["door_run"]
        self.assertEqual("not-restored", door_run["state"])
        self.assertEqual((1, 1, 0), (door_run["opened"], door_run["observed_open"], door_run["restored"]))
        self.assertLessEqual(door_run["close_settle_ticks"], samp.DOOR_SETTLE_TICKS)
        self.assertTrue(any("not-restored" in str(line) for line in run.prints), run.prints)
        self.assertTrue(building.IsDoorOpened(0))

    def test_an_open_that_never_completes_skips_the_open_pass_and_still_closes(self):
        run, building = self.gated(stuck={0: {"open"}})
        row = run.row()
        door_run = row["door_run"]
        self.assertEqual("open-stalled", door_run["state"])
        self.assertEqual((1, 0, 1), (door_run["opened"], door_run["observed_open"], door_run["restored"]))
        self.assertLessEqual(door_run["open_settle_ticks"], samp.DOOR_SETTLE_TICKS)
        self.assertEqual([("open", 0), ("close", 0)], building.ops)
        self.assertEqual([h[5] for h in row["hits"]], row["open_codes"])
        self.assertEqual("untested", row["entered"]["strict"]["open"])
        self.assertEqual("untested", row["entered"]["player"]["open"])
        self.assertEqual(0, row["stats"]["open_paths"])

    def test_one_door_of_two_that_does_not_open_is_still_an_open_stall(self):
        run, _building = self.gated(stuck={1: {"open"}}, extra_doors=1,
                                    setup=lambda b: b.state.__setitem__(1, False))
        door_run = run.row()["door_run"]
        self.assertEqual("open-stalled", door_run["state"])
        self.assertEqual((2, 1), (door_run["opened"], door_run["observed_open"]))

    def test_a_door_slower_than_delay_plus_settle_is_a_stall_not_a_wait_forever(self):
        slow = samp.DOOR_DELAY_TICKS + samp.DOOR_SETTLE_TICKS + 40
        door_run = self.gated(lag=slow)[0].row()["door_run"]
        self.assertEqual("not-restored", door_run["state"])
        self.assertEqual(0, door_run["observed_open"])

    def test_a_door_inside_the_delay_plus_settle_budget_completes(self):
        door_run = self.gated(lag=samp.DOOR_DELAY_TICKS + 5)[0].row()["door_run"]
        self.assertEqual("done", door_run["state"])
        self.assertGreater(door_run["open_settle_ticks"], 0)

    def test_a_door_requested_open_but_actually_closed_is_opened_and_restored(self):
        def stale(building):
            building.state[0], building.phase[0] = True, 0.0
        run, building = self.gated(setup=stale)
        door_run = run.row()["door_run"]
        self.assertEqual([("open", 0), ("close", 0)], building.ops)
        self.assertEqual("done", door_run["state"])
        self.assertEqual(0, door_run["open_at_start"])

    def test_doors_found_ajar_open_or_moving_are_left_alone_and_counted(self):
        def mixed(building):
            building.phase.update({1: 0.2, 2: 1.0, 3: SampBuilding.MOVING})
            building.state.update({1: True, 2: True, 3: True})
        run, building = self.gated(extra_doors=3, setup=mixed)
        door_run = run.row()["door_run"]
        self.assertEqual([("open", 0), ("close", 0)], building.ops)
        self.assertEqual((4, 1, 1, 1), (door_run["count"], door_run["opened"], door_run["observed_open"], door_run["restored"]))
        self.assertEqual((1, 1, 1), (door_run["open_at_start"], door_run["ajar_at_start"], door_run["moving_at_start"]))
        self.assertEqual([0, 2, 1, 3], [door[5] for door in door_run["doors"]])
        self.assertEqual((0.2, 1.0), (building.phase[1], building.phase[2]))
        self.assertEqual("done", door_run["state"])

    def test_a_building_whose_only_doors_are_ajar_or_open_is_no_change_and_records_why(self):
        for phase, label in ((0.2, "ajar"), (1.0, "open")):
            with self.subTest(phase=label):
                building = flat_building()
                building.phase[0], building.state[0] = phase, True
                row = HookRun(self.hook, building, storey_planes(building), nav=nav_for(building)).run().row()
                self.assertEqual([], building.ops)
                self.assertEqual("no-change", row["door_run"]["state"])
                self.assertEqual(1, row["door_run"]["ajar_at_start"] + row["door_run"]["open_at_start"])

    def test_a_locked_door_is_never_opened_even_when_actually_closed(self):
        building = flat_building()
        building.locked, building.phase[0], building.state[0] = {0}, 0.0, False
        row = HookRun(self.hook, building, storey_planes(building), nav=nav_for(building)).run().row()
        self.assertEqual([], building.ops)
        self.assertEqual(1, row["door_run"]["locked"])

    def test_the_settle_check_is_what_makes_the_slow_door_work(self):
        old = "if (!HCProbeDoorsSettled() && m_HCProbeSettleUsed < m_HCProbeDoorSettleTicks)"
        self.assertEqual(1, self.hook.count(old))
        mutant = self.hook.replace(old, "if (false)")
        building = flat_building()
        building.state[0], building.lag = False, 6
        nav = DoorGatedNav(building, nav_for(building).zones, links=[("out", "g")])
        row = HookRun(mutant, building, storey_planes(building), nav=nav,
                      overrides={"m_HCProbeDoorDelayTicks": 1}).run().row()
        self.assertEqual(0, ones(row["open_codes"]))


class Round7ActualPhaseContractTests(unittest.TestCase):
    """Sol r6 P2: the census says which door-evidence contract it was written under, and every door run reconciles."""

    def setUp(self):
        self.hook = default_hook()

    def test_the_census_header_carries_the_actual_phase_contract_version(self):
        census = gated_run(self.hook)[0].census()
        self.assertEqual(samp.DOOR_PHASE_CONTRACT, census["door_phase_contract"])
        self.assertEqual(2, samp.DOOR_PHASE_CONTRACT)
        self.assertEqual(pts.DOOR_PHASE_CONTRACT, samp.DOOR_PHASE_CONTRACT)

    def test_a_finished_run_lists_the_door_indices_it_opened(self):
        run, _building = gated_run(self.hook)
        self.assertEqual([0], run.row()["door_run"]["opened_doors"])

    def test_a_mixed_building_lists_only_the_unlocked_closed_door_it_opened(self):
        building = flat_building()
        building.doors = [building.doors[0]] + [building.to_world((-4.9 + 0.1 * (i + 1), 1.0, -0.5)) for i in range(4)]
        building.state[0] = False
        building.phase.update({1: 0.2, 2: 1.0, 3: SampBuilding.MOVING})
        building.state.update({1: True, 2: True, 3: True, 4: False})
        building.locked = {4}
        nav = DoorGatedNav(building, nav_for(building).zones, links=[("out", "g")])
        row = HookRun(self.hook, building, storey_planes(building), nav=nav).run().row()
        door_run = row["door_run"]
        self.assertEqual([0], door_run["opened_doors"])
        self.assertEqual((5, 1, 1, 1, 1), (door_run["count"], door_run["locked"], door_run["open_at_start"],
                                           door_run["ajar_at_start"], door_run["moving_at_start"]))

    def test_a_run_that_changed_nothing_lists_no_opened_doors(self):
        building = flat_building()
        building.locked = {0}
        row = HookRun(self.hook, building, storey_planes(building), nav=nav_for(building)).run().row()
        self.assertEqual([], row["door_run"]["opened_doors"])

    def test_the_door_runs_the_hook_writes_satisfy_the_builder_validation(self):
        for label, kwargs in (("fast", {"lag": 1}), ("slow", {"lag": 6, "overrides": {"m_HCProbeDoorDelayTicks": 1}}),
                              ("two-doors", {"extra_doors": 1, "setup": lambda b: b.state.__setitem__(1, False)})):
            with self.subTest(label=label):
                run, _building = Round6DoorPhaseTests().gated_with(self.hook, **kwargs)
                door_run = run.row()["door_run"]
                self.assertEqual("done", door_run["state"])
                self.assertIsNone(pts._door_run_problem(door_run))

    def test_a_stalled_run_is_recorded_and_refused_by_the_builder(self):
        run, _building = Round6DoorPhaseTests().gated_with(self.hook, stuck={0: {"close"}})
        door_run = run.row()["door_run"]
        self.assertEqual("not-restored", door_run["state"])
        self.assertIsNotNone(pts._door_run_problem(door_run))


class Round7StagerContractTests(SamplerWorkspace):
    def setUp(self):
        patcher = mock.patch.object(cep, "SYNTH_PROTO", SAMPLER_PROTO)
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()

    def test_the_plan_names_the_door_evidence_contract_the_census_will_carry(self):
        plan = self.stage()
        self.assertEqual(samp.DOOR_PHASE_CONTRACT, plan["door_run"]["phase_contract"])
        text = (self.dest / "mpmissions/dayzOffline.chernarusplus/init.c").read_text()
        self.assertIn('HCProbeKey("door_phase_contract") + "2,"', text)


class Round5StagerFrameTests(SamplerWorkspace):
    def setUp(self):
        patcher = mock.patch.object(cep, "SYNTH_PROTO", SAMPLER_PROTO)
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()

    def plan_hook(self):
        return (self.dest / "mpmissions/dayzOffline.chernarusplus/init.c").read_text()

    def test_stage_inlines_the_stock_lootfloor_points_of_both_calibration_classes_and_reports_them(self):
        plan = self.stage()
        text = self.plan_hook()
        self.assertIn('HCProbeFrameAdd("Land_HouseBlock_2F1", 1.500000, 0.100000, 3.000000);', text)
        self.assertIn('HCProbeFrameAdd("Land_Mil_Barracks2", 2.000000, 0.100000, 1.000000);', text)
        self.assertNotIn("9.000000, 1.000000, 9.000000", text)            # shelves are not frame points
        self.assertEqual({"Land_HouseBlock_2F1": 3, "Land_Mil_Barracks2": 1}, plan["frame_check"]["points"])
        self.assertEqual(["as-is", "rot90"], plan["frame_check"]["transforms"])
        self.assertEqual("lootFloor", plan["frame_check"]["container"])

    def test_stage_refuses_when_a_calibration_class_has_no_lootfloor_points(self):
        bare = b'<prototype><group name="Land_HouseBlock_2F1" lootmax="6"><container name="lootFloor">' \
               b'<point pos="1 0.1 1" range="1" height="1" /></container></group></prototype>\n'
        shutil.rmtree(self.source)
        with mock.patch.object(cep, "SYNTH_PROTO", bare):
            self.source = cep.make_source_runtime(self.root / "vanilla-s", counts=sampler_counts())
        with self.assertRaisesRegex(ValueError, "Land_Mil_Barracks2"):
            self.stage()
        self.assertFalse(self.dest.exists())

    def test_the_frame_points_are_bounded_per_class(self):
        many = b'<prototype><group name="Land_HouseBlock_2F1"><container name="lootFloor">%s</container></group>' \
               b'<group name="Land_Mil_Barracks2"><container name="lootFloor"><point pos="1 0 1" /></container></group></prototype>' \
               % b"".join(b'<point pos="%d 0.1 0" />' % i for i in range(100))
        shutil.rmtree(self.source)
        with mock.patch.object(cep, "SYNTH_PROTO", many):
            self.source = cep.make_source_runtime(self.root / "vanilla-s", counts=sampler_counts())
        plan = self.stage()
        self.assertEqual(samp.MAX_FRAME_POINTS_PER_CLASS, plan["frame_check"]["points"]["Land_HouseBlock_2F1"])


class Round8NativeRunIdTests(SamplerWorkspace):
    """The census must name its native run: the id is chosen when the plan is staged and echoed by the hook."""
    RUN = "00112233445566778899aabbccddeeff"  # SYNTHETIC

    def setUp(self):
        patcher = mock.patch.object(cep, "SYNTH_PROTO", SAMPLER_PROTO)
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()

    def test_the_census_header_echoes_the_run_id_the_hook_was_rendered_with(self):
        hook = samp.render_hook(sampler_targets(), native_run_id=self.RUN).decode()
        census = gated_run(hook)[0].census()
        self.assertEqual(self.RUN, census["native_run_id"])

    def test_a_malformed_run_id_is_refused_when_rendering(self):
        for bad in ("", "ABCDEF0123456789ABCDEF0123456789", "abc", "0" * 31 + "g", 5, '0" + "'):
            with self.subTest(run_id=bad), self.assertRaises(ValueError):
                samp.render_hook(sampler_targets(), native_run_id=bad)

    def test_the_plan_records_the_run_id_and_the_staged_hook_embeds_that_same_id(self):
        plan = self.stage()
        run_id = plan["probe"]["native_run_id"]
        self.assertRegex(run_id, r"^[0-9a-f]{32}$")
        text = (self.dest / "mpmissions/dayzOffline.chernarusplus/init.c").read_text()
        self.assertIn(run_id, text)

    def test_every_stage_gets_a_fresh_run_id(self):
        first = self.stage()["probe"]["native_run_id"]
        shutil.rmtree(self.dest)
        self.assertNotEqual(first, self.stage()["probe"]["native_run_id"])

    def test_the_hook_text_without_an_explicit_id_still_lints_clean(self):
        self.assertEqual([], samp.lint_sampler_hook(samp.render_hook(sampler_targets()).decode()))


# ---------------------------------------------------------------------------
# T1: all-class batch plans, the House config census and door rows. Synthetic fixtures only; none of this
# observes the engine, and the in-game census stays pending a native run.
# ---------------------------------------------------------------------------

def house_names(count, prefix="Land_House_Syn"):
    return ["%s%04d" % (prefix, index) for index in range(count)]


def house_placements(names, per_name=1):
    return {name: [(1000.0 + 10 * index + 3 * copy, 100.0, 2000.0 + index) for copy in range(per_name)]
            for index, name in enumerate(names)}


def house_census_document(rows, run_id="ab" * 16):
    """A minimal SYNTHETIC census shaped like the hook output (rows are placement dicts)."""
    return {"schema": 1, "kind": "interior-sampler-census", "door_phase_contract": samp.DOOR_PHASE_CONTRACT,
            "native_run_id": run_id, "world": "chernarusplus", "version": "1.30.test",
            "placements": rows, "summary": {"complete": True}}


def house_row(name, doors=((1.0, 0.5, 2.0),), selections=(("door1", 1.0, 0.5, 2.0),), found=True, door_count=None):
    return {"i": 0, "class": name, "role": "house", "found": found, "actual": [1.0, 2.0, 3.0], "distance": 0.1,
            "orientation": [0.0, 0.0, 0.0], "box_source": "clipping", "box_min": [-5.0, -1.0, -4.0],
            "box_max": [7.0, 9.0, 3.0], "hits": [], "grid": {"step": 1.0, "rows": 12, "cols": 7},
            "house": {"model": "model_" + name, "door_count": len(doors) if door_count is None else door_count,
                      "doors": [list(d) for d in doors], "selection_total": len(selections) + 2,
                      "door_selections": [[n, x, y, z] for n, x, y, z in selections]}}


def write_census_dir(root, name, rows, run_id="ab" * 16, sentinel=True):
    directory = Path(root) / name / "profiles" / "HCInteriorSampler"
    directory.mkdir(parents=True)
    (directory / "census.json").write_text(json.dumps(house_census_document(rows, run_id)))
    if sentinel:
        (directory / "complete.txt").write_text("done\n")
    return Path(root) / name


class BatchPlanTests(unittest.TestCase):
    def plan(self, count, **kwargs):
        names = house_names(count)
        return samp.plan_batches(names, house_placements(names), **kwargs), names

    def test_run_boundaries_at_63_64_65_and_300_classes_never_exceed_64_targets(self):
        for count, sizes in ((63, [63]), (64, [64]), (65, [64, 1]), (300, [64, 64, 64, 64, 44])):
            with self.subTest(count=count):
                plan, names = self.plan(count)
                self.assertEqual(sizes, [len(run["targets"]) for run in plan["runs"]])
                self.assertEqual(sorted(names), sorted(c for run in plan["runs"] for c in run["classes"]))
                self.assertEqual(list(range(len(sizes))), [run["index"] for run in plan["runs"]])
                self.assertEqual([], plan["unplaced"])

    def test_a_class_with_several_targets_is_never_split_across_runs(self):
        names = house_names(40)
        plan = samp.plan_batches(names, house_placements(names, per_name=3), per_class=2)
        self.assertEqual([64, 16], [len(run["targets"]) for run in plan["runs"]])
        for run in plan["runs"]:
            self.assertEqual(2 * len(run["classes"]), len(run["targets"]))
            for number, target in enumerate(run["targets"]):
                self.assertEqual(number, target["index"])
                self.assertRegex(target["role"], r"^[a-z]{1,16}$")

    def test_run_ids_are_32_hex_deterministic_and_independent_of_the_input_order(self):
        names = house_names(150)
        placements = house_placements(names)
        first = samp.plan_batches(names, placements)
        again = samp.plan_batches(list(reversed(names)), placements)
        self.assertEqual(first, again)
        ids = [run["native_run_id"] for run in first["runs"]]
        self.assertEqual(3, len(set(ids)))
        for run_id in ids:
            self.assertRegex(run_id, r"^[0-9a-f]{32}$")
        changed = samp.plan_batches(names[:-1], placements)
        self.assertNotEqual(ids[-1], changed["runs"][-1]["native_run_id"])
        self.assertEqual(ids[:-1], [run["native_run_id"] for run in changed["runs"][:-1]])
        moved = dict(placements, **{names[0]: [(5.0, 6.0, 7.0)]})
        self.assertNotEqual(ids[0], samp.plan_batches(names, moved)["runs"][0]["native_run_id"])

    def test_a_class_without_a_stock_placement_is_reported_not_planned(self):
        names = house_names(5)
        placements = house_placements(names)
        placements.pop(names[2])
        plan = samp.plan_batches(names, placements)
        self.assertEqual([{"class": names[2], "reason": "not_in_mapgrouppos"}], plan["unplaced"])
        self.assertNotIn(names[2], [c for run in plan["runs"] for c in run["classes"]])

    def test_the_plan_refuses_bad_inputs(self):
        names = house_names(3)
        placements = house_placements(names)
        cases = (
            ("duplicate", dict(classes=names + [names[0]])),
            ("empty", dict(classes=[])),
            ("bad identifier", dict(classes=names + ["Land Bad;Class"])),
            ("non string", dict(classes=names + [5])),
            ("too many", dict(classes=house_names(samp.MAX_BATCH_CLASSES + 1))),
            ("run size 65", dict(classes=names, run_size=65)),
            ("run size 0", dict(classes=names, run_size=0)),
            ("per class 0", dict(classes=names, per_class=0)),
            ("per class 17", dict(classes=names, per_class=17)),
            ("bool run size", dict(classes=names, run_size=True)),
        )
        for label, kwargs in cases:
            classes = kwargs.pop("classes")
            with self.subTest(label), self.assertRaises(ValueError):
                samp.plan_batches(classes, placements, **kwargs)


class ClassListTests(unittest.TestCase):
    def test_a_json_list_a_text_list_and_a_census_all_enumerate_the_same_classes(self):
        names = house_names(4)
        as_json = json.dumps(names).encode()
        as_text = ("# House classes\n" + "\n".join(names) + "\n").encode()
        as_census = json.dumps(house_census_document([house_row(n) for n in names] + [house_row(names[0])])).encode()
        self.assertEqual(sorted(names), sorted(samp.parse_class_list(as_json)))
        self.assertEqual(sorted(names), sorted(samp.parse_class_list(as_text)))
        self.assertEqual(sorted(names), sorted(samp.parse_class_list(as_census)))

    def test_a_class_list_refuses_duplicates_malformed_rows_and_oversize(self):
        names = house_names(3)
        for label, data in (
                ("duplicate json", json.dumps(names + [names[0]]).encode()),
                ("duplicate text", "\n".join(names + [names[1]]).encode()),
                ("bad identifier", b"Land_House_1\nLand/House\n"),
                ("empty", b"\n# nothing\n"),
                ("not bytes", "Land_House_1"),
                ("non string json", json.dumps(["Land_House_1", 4]).encode()),
                ("census row without class", json.dumps(house_census_document([{"found": True}])).encode()),
                ("census class not a string", json.dumps(house_census_document([{"class": 7}])).encode()),
                ("too many", "\n".join(house_names(samp.MAX_BATCH_CLASSES + 1)).encode()),
                ("too large", b"Land_X\n" * 3000000)):
            with self.subTest(label), self.assertRaises(ValueError):
                samp.parse_class_list(data)


class ResumeTests(unittest.TestCase):
    def setUp(self):
        temp = __import__("tempfile").TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_classes_measured_in_a_prior_output_are_skipped_and_the_rest_keep_their_run_index(self):
        names = house_names(130)
        placements = house_placements(names)
        full = samp.plan_batches(names, placements)
        done = sorted(names)[:64] + sorted(names)[64:70]              # run 0 entirely, run 1 partly
        first = write_census_dir(self.root, "prior-a", [house_row(n) for n in done[:64]], run_id="11" * 16)
        second = write_census_dir(self.root, "prior-b", [house_row(n) for n in done[64:]], run_id="22" * 16)
        measured = samp.measured_classes([first, second])
        self.assertEqual(sorted(done), measured["measured"])
        self.assertEqual(2, len(measured["censuses"]))
        resumed = samp.plan_batches(names, placements, measured=measured["measured"])
        self.assertEqual([1, 2], [run["index"] for run in resumed["runs"]])
        self.assertEqual([58, 2], [len(run["targets"]) for run in resumed["runs"]])
        self.assertEqual(sorted(done), resumed["measured"])
        self.assertEqual(full["runs"][2]["native_run_id"], resumed["runs"][1]["native_run_id"])
        self.assertNotEqual(full["runs"][1]["native_run_id"], resumed["runs"][0]["native_run_id"])
        again = samp.plan_batches(names, placements, measured=list(reversed(measured["measured"])))
        self.assertEqual(resumed, again)

    def test_everything_measured_leaves_no_runs(self):
        names = house_names(5)
        prior = write_census_dir(self.root, "prior", [house_row(n) for n in names])
        plan = samp.plan_batches(names, house_placements(names), measured=samp.measured_classes([prior])["measured"])
        self.assertEqual([], plan["runs"])

    def test_an_unfinished_census_and_a_row_without_house_evidence_do_not_count_as_measured(self):
        unfinished = write_census_dir(self.root, "crashed", [house_row("Land_House_A")], run_id="cd" * 16,
                                      sentinel=False)
        bare = house_row("Land_House_B")
        bare.pop("house")
        lost = house_row("Land_House_C", found=False)
        complete = write_census_dir(self.root, "done", [bare, lost, house_row("Land_House_D")], run_id="ef" * 16)
        result = samp.measured_classes([unfinished, complete])
        self.assertEqual(["Land_House_D"], result["measured"])
        self.assertEqual(1, len(result["ignored"]))

    def test_a_malformed_finished_census_is_refused_not_skipped(self):
        bad = write_census_dir(self.root, "bad", [house_row("Land_House_A")])
        (bad / "profiles/HCInteriorSampler/census.json").write_text('{"kind": "wrong"}')
        with self.assertRaises(ValueError):
            samp.measured_classes([bad])
        broken = write_census_dir(self.root, "broken", [house_row("Land_House_A", doors=[(1, 2)])])
        with self.assertRaises(ValueError):
            samp.measured_classes([broken])

    def test_output_paths_with_dotdot_and_missing_directories_are_refused(self):
        for bad in (self.root / ".." / "elsewhere", str(self.root) + "/a/../b", "prior/../../x"):
            with self.subTest(bad=str(bad)), self.assertRaises(ValueError):
                samp.measured_classes([bad])
            with self.subTest(write=str(bad)), self.assertRaises(ValueError):
                samp.write_batch_plan({"runs": []}, bad)
        with self.assertRaises(ValueError):
            samp.measured_classes([self.root / "missing"])

    def test_write_batch_plan_writes_one_new_file_and_refuses_to_overwrite(self):
        names = house_names(70)
        plan = samp.plan_batches(names, house_placements(names))
        path = samp.write_batch_plan(plan, self.root / "plan-out")
        self.assertEqual(samp.BATCH_PLAN_NAME, Path(path).name)
        self.assertEqual(plan, json.loads(Path(path).read_text()))
        with self.assertRaises(ValueError):
            samp.write_batch_plan(plan, self.root / "plan-out")


class HouseCensusHookTests(unittest.TestCase):
    DOORS = [(-4.9, 1.0, -0.5), (2.0, 1.0, 3.0), (6.5, 1.0, 0.0)]
    SELECTIONS = {"door1": (-4.9, 1.0, -0.5), "wall_a": (0.0, 1.0, 0.0), "Door_2": (2.0, 1.0, 3.0),
                  "windowfront": (3.0, 1.0, 3.0), "DOOR3": (6.5, 1.0, 0.0)}

    def house_building(self, yaw=0.6, doors=None):
        b = SampBuilding("Land_Tenement_Small", (3000.0, 20.0, 5000.0), yaw=yaw, clip=BOX,
                         model="tenement_small", selections=self.SELECTIONS)
        b.doors = [b.to_world(d) for d in (self.DOORS if doors is None else doors)]
        return b

    def run_house(self, building, strict=False):
        building.state[0] = True
        hook = default_hook()
        return HookRun(hook, building, storey_planes(building), nav=nav_for(building), strict=strict).run().row()

    def test_the_census_row_carries_the_house_config_with_door_positions_in_the_model_frame(self):
        building = self.house_building()
        house = self.run_house(building)["house"]
        self.assertEqual("tenement_small", house["model"])
        self.assertEqual(3, house["door_count"])
        self.assertEqual(3, len(house["doors"]))
        for recorded_door, wanted in zip(house["doors"], self.DOORS):
            self.assertEqual(3, len(recorded_door))
            for got, expected in zip(recorded_door, wanted):
                self.assertAlmostEqual(expected, got, places=4)

    def test_only_door_named_selections_are_recorded_with_model_space_positions_and_the_total_is_kept(self):
        house = self.run_house(self.house_building())["house"]
        self.assertEqual(["door1", "Door_2", "DOOR3"], [entry[0] for entry in house["door_selections"]])
        self.assertEqual([-4.9, 1.0, -0.5], house["door_selections"][0][1:])
        self.assertEqual(5, house["selection_total"])

    def test_doors_and_selections_are_bounded_while_the_true_count_is_kept(self):
        many = {"door%d" % index: (float(index), 1.0, 0.0) for index in range(70)}
        building = SampBuilding("Land_Tenement_Small", (3000.0, 20.0, 5000.0), yaw=0.0, clip=BOX,
                                model="big", selections=many)
        building.doors = [building.to_world((index * 0.1, 1.0, 0.0)) for index in range(70)]
        house = self.run_house(building)["house"]
        self.assertEqual(70, house["door_count"])
        self.assertEqual(samp.MAX_HOUSE_DOORS, len(house["doors"]))
        self.assertEqual(samp.MAX_HOUSE_SELECTIONS, len(house["door_selections"]))
        self.assertEqual(70, house["selection_total"])

    def test_a_house_without_doors_still_records_its_model_and_an_empty_door_list(self):
        house = self.run_house(self.house_building(doors=[]))["house"]
        self.assertEqual(0, house["door_count"])
        self.assertEqual([], house["doors"])

    def test_the_house_block_is_valid_json_under_strict_strings_and_passes_the_census_parser(self):
        row = self.run_house(self.house_building(), strict=True)
        self.assertIn("house", row)
        hook = default_hook()
        run = HookRun(hook, self.house_building(), storey_planes(self.house_building()), strict=True)
        census = run.run().census()
        pts.parse_census(json.dumps(census).encode())               # the builder's own strict parser accepts it
        rows = samp.house_rows(census)
        self.assertEqual("Land_Tenement_Small", rows[0]["class"])

    def test_the_rendered_hook_lints_clean_with_the_house_census(self):
        self.assertEqual([], samp.lint_sampler_hook(default_hook()))


class HouseRowsTests(unittest.TestCase):
    def test_canonical_rows_carry_class_model_box_and_indexed_door_rows(self):
        doc = house_census_document([house_row("Land_House_A", doors=[(1.0, 0.5, 2.0), (-3.0, 0.5, 1.0)],
                                              selections=[("door1", 1.0, 0.5, 2.0)]),
                                     house_row("Land_House_B", found=False)])
        rows = samp.house_rows(doc)
        self.assertEqual(1, len(rows))                                   # a class that was not found is not a row
        row = rows[0]
        self.assertEqual({"class", "model", "box_min", "box_max", "door_count", "doors", "door_selections",
                          "selection_total", "native_run_id"}, set(row))
        self.assertEqual("Land_House_A", row["class"])
        self.assertEqual("model_Land_House_A", row["model"])
        self.assertEqual([-5.0, -1.0, -4.0], row["box_min"])
        self.assertEqual([{"index": 0, "position": [1.0, 0.5, 2.0]}, {"index": 1, "position": [-3.0, 0.5, 1.0]}],
                         row["doors"])
        self.assertEqual([{"name": "door1", "position": [1.0, 0.5, 2.0]}], row["door_selections"])
        self.assertEqual("ab" * 16, row["native_run_id"])

    def test_malformed_house_blocks_are_refused(self):
        def mutated(change):
            row = house_row("Land_House_A", doors=[(1.0, 0.5, 2.0), (2.0, 0.5, 1.0)])
            change(row["house"])
            return house_census_document([row])
        bad = {
            "door not three numbers": lambda h: h["doors"].__setitem__(0, [1.0, 2.0]),
            "door nan": lambda h: h["doors"].__setitem__(0, [1.0, float("nan"), 2.0]),
            "door huge": lambda h: h["doors"].__setitem__(0, [1.0, 1e9, 2.0]),
            "door bool": lambda h: h["doors"].__setitem__(0, [True, 1.0, 2.0]),
            "count below rows": lambda h: h.__setitem__("door_count", 1),
            "count negative": lambda h: h.__setitem__("door_count", -1),
            "rows missing": lambda h: h.__setitem__("doors", h["doors"][:1]),
            "too many doors": lambda h: (h.__setitem__("door_count", 65),
                                         h.__setitem__("doors", [[0.0, 0.0, 0.0]] * 65)),
            "model not text": lambda h: h.__setitem__("model", 4),
            "model empty": lambda h: h.__setitem__("model", ""),
            "selection bad": lambda h: h["door_selections"].append(["x", 1.0]),
            "selection name": lambda h: h["door_selections"].append([3, 1.0, 1.0, 1.0]),
            "selection total small": lambda h: h.__setitem__("selection_total", 0),
            "missing key": lambda h: h.pop("doors"),
            "extra key": lambda h: h.__setitem__("extra", 1),
        }
        for label, change in bad.items():
            with self.subTest(label), self.assertRaises(ValueError):
                samp.house_rows(mutated(change))

    def test_a_found_row_without_a_house_block_or_a_box_is_refused_and_a_wrong_kind_too(self):
        row = house_row("Land_House_A")
        row.pop("house")
        with self.assertRaises(ValueError):
            samp.house_rows(house_census_document([row]))
        with self.assertRaises(ValueError):
            samp.house_rows({"kind": "other"})
        boxless = house_row("Land_House_A")
        boxless["box_source"] = "none"
        with self.assertRaises(ValueError):
            samp.house_rows(house_census_document([boxless]))


class BatchStageTests(SamplerWorkspace):
    def setUp(self):
        patcher = mock.patch.object(cep, "SYNTH_PROTO", SAMPLER_PROTO)
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()
        counts = {"Land_Syn_A": 3, "Land_Syn_B": 2, "Land_HouseBlock_2F1": 2, "Land_Mil_Barracks2": 2}
        self.source = cep.make_source_runtime(self.root / "vanilla-b", counts=counts)
        xml = (self.source / "stock-backup/mpmissions/dayzOffline.chernarusplus/mapgrouppos.xml").read_bytes()
        self.placements = probe.parse_placements(xml)
        self.plan = samp.plan_batches(sorted(counts), self.placements)

    def test_a_run_stages_with_its_own_deterministic_native_run_id(self):
        run = self.plan["runs"][0]
        staged = samp.stage(self.source, self.dest, run=run, **self.kw())
        self.assertEqual(run["native_run_id"], staged["probe"]["native_run_id"])
        self.assertEqual(len(run["targets"]), staged["probe"]["target_count"])
        text = (self.dest / "mpmissions/dayzOffline.chernarusplus/init.c").read_text()
        self.assertIn(run["native_run_id"], text)
        self.assertIn('HCProbeAdd("Land_Syn_A"', text)
        self.assertEqual({"index": 0, "classes": len(run["classes"])}, staged["batch"])
        self.assertEqual([], self.launcher_problems(staged, "interior-sampler-plan.json"))
        self.assertEqual({"Land_HouseBlock_2F1": 3, "Land_Mil_Barracks2": 1}, staged["frame_check"]["points"])

    def test_a_tampered_or_unplaced_run_is_refused_before_anything_is_created(self):
        run = json.loads(json.dumps(self.plan["runs"][0]))
        forged = dict(run, native_run_id="0" * 32)
        moved = json.loads(json.dumps(run))
        moved["targets"][0]["pos"][0] += 1.0
        moved["native_run_id"] = samp.run_id_for(moved["targets"])
        toomany = dict(run, targets=run["targets"] * 20)
        for label, bad in (("forged id", forged), ("position not in mapgrouppos", moved), ("too many", toomany)):
            with self.subTest(label), self.assertRaises(ValueError):
                samp.stage(self.source, self.dest, run=bad, **self.kw())
            self.assertFalse(self.dest.exists())

    def test_the_cli_plans_all_classes_and_stages_one_run_from_the_plan_file(self):
        mission = self.source / "stock-backup/mpmissions/dayzOffline.chernarusplus"
        classes = self.root / "classes.txt"
        classes.write_text("\n".join(sorted(self.placements)) + "\n")
        out = self.root / "plan-out"
        argv = ["plan", "--classes", str(classes), "--mapgrouppos", str(mission / "mapgrouppos.xml"),
                "--output", str(out)]
        with mock.patch("sys.stdout"):
            self.assertEqual(0, samp.main(argv))
        written = json.loads((out / samp.BATCH_PLAN_NAME).read_text())
        self.assertEqual(self.plan, written)
        with mock.patch("sys.stderr") as err:
            self.assertEqual(1, samp.main(argv))                    # the plan already exists
            self.assertEqual(1, samp.main(["plan", "--classes", str(classes), "--mapgrouppos",
                                           str(mission / "mapgrouppos.xml"), "--output", "x/../y"]))
        self.assertIn("interior_sampler:", "".join(call.args[0] for call in err.write.call_args_list))
        stage_argv = ["--source-runtime", str(self.source), "--destination", str(self.dest),
                      "--battleye-sha256", cep.SYNTH_BE_SHA, "--batch-plan", str(out / samp.BATCH_PLAN_NAME),
                      "--run", "0"]
        with mock.patch.object(rt, "WSL_PARENT", self.root), mock.patch("sys.stdout"):
            self.assertEqual(0, samp.main(stage_argv))
        staged = json.loads((self.dest / "interior-sampler-plan.json").read_text())
        self.assertEqual(self.plan["runs"][0]["native_run_id"], staged["probe"]["native_run_id"])


if __name__ == "__main__":
    unittest.main()
