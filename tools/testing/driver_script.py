"""Build and validate the step file for the dev-only scripted client driver (mods/HollowCountryTest).

The client driver reads `$profile:HollowCountry/acceptance/client_driver.json` and runs the steps
strictly in order. This module is the only writer of that file: it picks waypoints from repo data
(ai/sites.json, ai/zones.json; live shelter points come from the server RPT), builds the default campaign route and
rejects any step the driver does not implement (unknown kind, unknown field, a teleport command).

  python3 -B -m tools.testing.driver_script plan --route default [--phases join,group,...]
  python3 -B -m tools.testing.driver_script write <path> [--route default|r3] [--phases ...]
  python3 -B -m tools.testing.driver_script validate <path>

Offline output only. It never starts DayZ and never establishes game behaviour.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
MISSION = ROOT / "mission" / "hollow-country"
VERSION = 1
PHASES = ("join", "group", "walk_ai", "walk_town", "combat", "loot", "fixtures", "actions",
          "vehicle", "walk_zone", "scene", "forest", "survive", "mission", "ai_clear", "idle")
# A phase that needs a place walks there first unless the route already stands within this of it, so
# every phase also runs alone (a targeted soak drives join, the phase and idle).
SPAWN_XZ = (6500.0, 2500.0)
# Source of truth: mods/HollowCountryTest/scripts/5_Mission/HCDriverInitialSpawn.c.
INITIAL_SPAWN_CANDIDATES_XZ = (
    (5500.0, 2800.0), (5400.0, 2800.0), (5300.0, 2800.0), (5200.0, 2800.0),
    (5500.0, 3000.0), (5400.0, 3000.0), (5300.0, 3000.0), (5200.0, 3000.0),
    (5500.0, 3200.0), (5400.0, 3200.0), (5300.0, 3200.0), (5200.0, 3200.0),
)
NEAR_M = 400.0
DEFAULT_PHASES = list(PHASES)
MAX_STEPS = 400
WORLD_SIZE = 15360.0

# Waypoint choices of the default route (all resolved from repo data, see resolve_waypoint).
AI_SITE = "site:police-chernogorsk"
ZONE = "zone:balota-cf3bbed7"
ZONE_CENTER = (3900.0, 2330.0)
TOWN = "site:scav-chernogorsk"
# Scene phase: the first stage source of one scene chain in events/scene-chains.json, reached on
# foot like every other waypoint. This `scene:` source is the one addition to the site/zone/shelter
# sources; it reads repo data only.
SCENE = "scene:scene-kamenka"
# Forest phase: retain the retired Bor barn point as a woodland waypoint.
# Retain the phase-map compatibility alias; it denotes woodland, never a live shelter.
FOREST = "shelter:Bor South Rest"
# Radius entry (enter kind). The server counts an entry only after it sampled the player outside and
# then inside the same radius (HCReleaseRadius.c); the driver walks in, out and in again until the
# server's own RPC_ENTRY confirms it. Site candidates: patrol sites of ai/sites.json at their first
# waypoint (HCSiteAnchor), radius = the repo-default activation radius: HCXAISites EncounterRadius
# max(600, ActivationRadius) at ActivationRadiusScale 1, clamped up to the default perception ring
# HCSpawnMax (HCPerceptionRing.HCClampActivation), about 1500 m. A server whose radius differs is
# covered by the driver's widening in/out margins, never by a closer guess here.
ENTER_ZONES = ("site", "mission")
SITE_RADIUS_FLOOR = 1500.0
SITE_CELL_METERS = 2000.0
MAX_SITE_CANDIDATES = 64

# Setup fixtures in the order the fixture block calls them (fxsetup brief plus the existing ones).
FIXTURES = ("fx_car_side", "fx_car_zeds", "fx_camp_setup", "fx_wreck", "fx_holdout_due", "fx_conflict_journal", "fx_conflict",
            "fx_materialize", "fx_incident", "fx_tactic", "fx_trade", "fx_convoy_stuck",
            "fx_animal", "fx_food", "fx_cooking", "fx_kit_place", "fx_kit_refuse", "fx_barricade",
            "fx_melee", "fx_shoot_held", "fx_door_press", "fx_hearth",
            "fx_site_patrol_kill", "fx_die")
# Server commands the player's own admin RPC runs on the real module path (HCAdminModule.HCExtra and
# the command list): they ask a module to do its normal bounded work now, they never spawn a counter.
ADMIN_STEPS = ("status", "snapshot", "scene", "radio", "deaddrop", "loot", "forage", "decay")

GAITS = ("walk", "jog", "sprint")
MENUS = ("map", "inventory", "pause", "admin")
GROUP_OPS = ("create_solo",)
KINDS = ("wait", "walk", "stand", "sprint", "menu", "admin", "group", "ping", "action", "enter", "route",
         "combat", "loot", "survive", "vehicle", "climb", "cellar", "search_site", "take_lead", "raise", "hold_ring", "respawn")
# route: 2..MAX_ROUTE_POINTS waypoints as a flat [x, z, ...] list (HCDriverRoute walks them with the
# stuck ladder side-right, side-left, back-up, door, skip once, then refused stuck:<rung>).
MAX_ROUTE_POINTS = 64
# combat: raise, aim (aim overrides) and the vanilla quick reload against the nearest visible infected
# or server AI within range_m; never fires (no retail client entry), at most 3 targets of 20 s each,
# retreats on foot when bleeding or the health tendency falls (HCDriverCombat).
COMBAT_RANGE = (10, 150)
# loot: walk to loose ground items in priority order (magazine the rifle takes, ammunition, food, drink,
# medical, map) and take each with the vanilla take action; full pockets drop one junk item (never
# the test kit) with the inventory drop request (HCDriverLoot).
LOOT_RANGE = (5, 80)
LOOT_MAX_ITEMS = 10
# survive: bandage when bleeding, then drink and eat with the item's own vanilla continuous action;
# mode need acts only on a falling or warning HUD water/energy level, always drinks and eats whatever
# it carries (HCDriverSurvive). Missing items are listed (missing=no-food,...), never faked.
SURVIVE_MODES = ("need", "always")
# vehicle: walk to the driver door of the nearest free intact car within range_m, look at it and get in
# with the vanilla get-in action, start the engine with the vanilla start action (the car's own parts
# decide), hold throttle for `seconds` through the modded CarScript.OnInput, brake, stop the engine
# and get out with the vanilla actions (HCDriverVehicle). A car that will not start is reported
# (engine=0 note=engine-did-not-start), never repaired or refuelled.
VEHICLE_RANGE = (5, 80)
VEHICLE_SECONDS = (2, 60)
VEHICLE_THROTTLE = (0.1, 1.0)

# action kind -> (required args, optional args). Every arg value is a string.
ACTION_ARGS = {
    "craft": (("item1", "item2"), ()),
    "search": ((), ()),
    "take": (("type",), ()),
    "mount": (("item", "target"), ()),
    "close_door": ((), ()),
    "open_door": ((), ()),
    "salvage": ((), ("item",)),
    "melee": ((), ()),
    "fire": ((), ()),
    "flip": ((), ("item",)),
    "radio": (("freq",), ()),
    "pickup_forage": ((), ()),
    "earplugs": ((), ()),
    "read": ((), ()),
    "write": ((), ("use",)),
}
# Kinds the retail client cannot start through a native entry point; the driver logs
# result=unsupported for them (UAInput.SyncedOverride is only compiled under INPUT_OVERRIDE).
UNSUPPORTED_ACTIONS = ("melee", "fire")

# Default arguments of the action block. The items come from the test profile setup (camp brief);
# a missing item makes the step log result=refused detail=item-missing, never a fake pass.
DEFAULT_ACTION_ARGS = {
    "craft": {"item1": "CamoNet", "item2": "KitchenKnife"},
    "take": {"type": "Paper"},
    "mount": {"item": "UniversalLight", "target": "Mich2001Helmet"},
    "write": {"use": "gear"},
    "salvage": {"item": "Pliers"},
    "flip": {"item": "Crowbar"},
    "radio": {"freq": "87.8"},
}

_STEP_ID = re.compile(r"s\d{2,3}\Z")
_RUN_ID = re.compile(r"[a-z0-9-]{1,24}\Z")
_CMD = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")
_TYPE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")
_FREQ = re.compile(r"\d{2,3}(\.\d{1,2})?\Z")
_FORBIDDEN_CMDS = ("tp", "teleport", "tpto", "goto")

_COMMON = {"id", "kind"}
_STEP_FIELDS = {
    "wait": {"seconds"},
    "walk": {"to", "gait", "arrive_m", "timeout_s"},
    "stand": {"seconds"},
    "sprint": {"seconds"},
    "menu": {"name", "seconds"},
    "admin": {"cmd", "value"},
    "group": {"op"},
    "ping": set(),
    "action": {"name", "args", "timeout_s"},
    "enter": {"zone", "sites", "gait", "hold_s", "timeout_s"},
    "route": {"points", "gait", "arrive_m", "timeout_s"},
    "climb": {"range_m", "hold_s", "timeout_s"},
    "cellar": {"classes_from", "range_m", "hold_s", "timeout_s"},
    "combat": {"range_m", "timeout_s"},
    "loot": {"range_m", "max_items", "timeout_s"},
    "survive": {"mode", "timeout_s"},
    "vehicle": {"range_m", "seconds", "throttle", "timeout_s"},
    "search_site": {"site", "timeout_s"},
    "take_lead": {"timeout_s"},
    "raise": {"range_min_m", "range_max_m", "seconds", "timeout_s"},
    "hold_ring": {"to", "hold_s", "timeout_s"},
    "respawn": {"timeout_s"},
}
_TOP_FIELDS = {"version", "run_id", "steps"}


class ScriptError(ValueError):
    """A step file or route request the driver would not accept."""


def _load(relative):
    path = MISSION / relative
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        raise ScriptError("cannot read %s: %s" % (relative, exc))


def _xz(point, label):
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        raise ScriptError("%s has no position" % label)
    x = float(point[0])
    z = float(point[-1]) if len(point) == 2 else float(point[2])
    if not (0.0 <= x <= WORLD_SIZE and 0.0 <= z <= WORLD_SIZE):
        raise ScriptError("%s position outside the world" % label)
    return round(x, 2), round(z, 2)


def shelter_points_from_rpt(rpt):
    """Read actual completed placements. Never predict the native string hash."""
    points = {}
    number = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
    point_pattern = re.compile(r"\bpoint=(" + number + r") (" + number + r") (" + number + r")(?:\s|$)")
    with Path(rpt).open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            regional = re.search(r"\[HC Shelters\] regional_placed=(\S+)", line)
            legacy = re.search(r"\[HollowCountry\] V2 shelter placed name=(.*?) alternate=", line)
            match = point_pattern.search(line)
            if match and (regional or legacy):
                ident = (regional or legacy).group(1)
                point = [float(v) for v in match.groups()]
                if not all(math.isfinite(v) for v in point):
                    raise ScriptError("nonfinite placed shelter point")
                points[ident] = _xz(point, "placed shelter")
    return points


def resolve_waypoint(source, server_rpt=None):
    """`site:<id>` first waypoint of an ai/sites.json site, `zone:<id>` centre of an ai/zones.json
    zone, `shelter:<id or name>` completed position from server_rpt, `scene:<chain id>`
    first-stage source of an events/scene-chains.json chain. Returns (x, z)."""
    if not isinstance(source, str) or ":" not in source:
        raise ScriptError("waypoint source must be kind:id, got %r" % (source,))
    kind, _, ident = source.partition(":")
    if kind == "site":
        for site in _load("ai/sites.json").get("Sites", []):
            if site.get("Id") == ident:
                points = site.get("Waypoints") or []
                if not points:
                    raise ScriptError("site %s has no waypoints" % ident)
                return _xz(points[0], source)
        raise ScriptError("no ai site %s" % ident)
    if kind == "zone":
        for zone in _load("ai/zones.json").get("zones", []):
            if zone.get("id") == ident:
                return _xz(zone.get("center"), source)
        raise ScriptError("no ai zone %s" % ident)
    # Retired alias retained by the soak phase map: fixed woodland, not discovery.
    if kind in ("woodland", "shelter") and ident == "Bor South Rest":
        return (3100.955811, 4238.387207)
    if kind == "shelter":
        if server_rpt is None:
            raise ScriptError("shelter waypoint requires the current boot server RPT")
        points = shelter_points_from_rpt(server_rpt)
        if ident in points:
            return points[ident]
        for scene in _load("travel/auditshelter_scenes.json").get("Scenes", []) + _load("travel/auditshelter_scenes.json").get("AdditionalScenes", []):
            if ident == scene['Name'] and scene['Id'] in points:
                return points[scene['Id']]
        raise ScriptError("no completed shelter placement in RPT for %s" % ident)
    if kind == "scene":
        for chain in _load("events/scene-chains.json").get("Chains", []):
            if chain.get("Id") == ident:
                stages = chain.get("Stages") or []
                if not stages:
                    raise ScriptError("scene chain %s has no stages" % ident)
                return _xz((stages[0].get("Objective") or {}).get("Source"), source)
        raise ScriptError("no scene chain %s" % ident)
    raise ScriptError("unknown waypoint source kind %r" % kind)


def resolve_route(source):
    """`site:<id>`: every waypoint of an ai/sites.json site in order (the AI's own patrol line, so it
    stays on ground the site author walked). Returns [(x, z), ...]."""
    kind, _, ident = str(source).partition(":")
    if kind != "site":
        raise ScriptError("route source must be site:<id>, got %r" % (source,))
    for site in _load("ai/sites.json").get("Sites", []):
        if site.get("Id") == ident:
            points = [_xz(point, source) for point in site.get("Waypoints") or []]
            if not 2 <= len(points) <= MAX_ROUTE_POINTS:
                raise ScriptError("site %s needs 2..%d waypoints for a route" % (ident, MAX_ROUTE_POINTS))
            return points
    raise ScriptError("no ai site %s" % ident)


def _timeout_for(distance, gait):
    speed = {"walk": 1.3, "jog": 2.8, "sprint": 5.0}[gait]
    return int(min(3600, max(120, distance / speed * 2 + 120)))


class _Builder:
    def __init__(self, server_rpt=None):
        self.server_rpt = server_rpt
        self.steps = []
        self.notes = {}
        self.position = SPAWN_XZ
        self.at_initial_spawn = True
        self.done = set()
        self.uncertain = False
        self.last_walk_target = SPAWN_XZ

    def add(self, kind, note="", **fields):
        step = {"id": "s%02d" % (len(self.steps) + 1), "kind": kind}
        step.update(fields)
        self.steps.append(step)
        if kind in ("walk", "route", "hold_ring"):
            self.at_initial_spawn = False
        if kind == "group":
            self.done.add("group")
        if kind in ("menu", "enter", "combat", "loot", "vehicle", "climb", "cellar", "respawn", "raise", "search_site", "take_lead") or (kind == "admin" and fields.get("cmd", "").startswith("fx_")):
            self.uncertain = True
        if kind == "action":
            self.done.add("action:" + fields.get("name", ""))
        if note:
            self.notes[step["id"]] = note
        return step

    def distance_to(self, point):
        origin = self.last_walk_target if self.uncertain else self.position
        # Keep the fallback origin for offline target selection; only the initial travel
        # budget must cover every possible result of the server's spawn search.
        origins = (*INITIAL_SPAWN_CANDIDATES_XZ, SPAWN_XZ) if self.at_initial_spawn else (origin,)
        return max(math.dist(start, point) for start in origins) + (150.0 if self.uncertain else 0.0)

    def walk(self, source, gait="jog", arrive=5):
        x, z = resolve_waypoint(source, self.server_rpt)
        distance = self.distance_to((x, z))
        self.position = self.last_walk_target = (x, z)
        self.uncertain = False
        self.add("walk", note=source, to=[x, z], gait=gait, arrive_m=arrive,
                 timeout_s=_timeout_for(distance, gait))

    def route(self, source, gait="jog", arrive=5):
        points = resolve_route(source)
        distance = self.distance_to(points[0])
        last = points[0]
        for point in points:
            distance += math.hypot(point[0] - last[0], point[1] - last[1])
            last = point
        self.position = points[-1]
        self.uncertain = False
        flat = [value for point in points for value in point]
        # Each ladder climb costs up to about 14 s (8 s stuck + a 2 s move or a 6 s door scan).
        self.add("route", note=source, points=flat, gait=gait, arrive_m=arrive,
                 timeout_s=min(3600, _timeout_for(distance, gait) + 30 * len(points)))

    def near(self, source, gait="jog"):
        """Walk to source unless the route already stands within NEAR_M of it."""
        x, z = resolve_waypoint(source, self.server_rpt)
        if self.position == SPAWN_XZ or math.hypot(x - self.position[0], z - self.position[1]) > NEAR_M:
            self.walk(source, gait=gait)

    def action(self, name, **overrides):
        args = dict(DEFAULT_ACTION_ARGS.get(name, {}))
        args.update(overrides)
        self.add("action", name=name, args=args, timeout_s=120)

    def admin(self, cmd, pause=3):
        self.add("admin", cmd=cmd, value="")
        self.add("stand", seconds=pause)


def _phase_join(b):
    b.add("wait", seconds=30)
    b.add("stand", seconds=5)
    b.add("sprint", seconds=10)
    for name in MENUS:
        b.add("menu", name=name, seconds=4)
    b.add("admin", cmd="status", value="")
    b.admin("snapshot")
    b.action("earplugs")


def _phase_group(b):
    b.add("group", op="create_solo")
    b.add("ping")


def _phase_walk_ai(b):
    b.walk(AI_SITE)
    b.add("stand", seconds=30)
    b.add("raise", range_min_m=45, range_max_m=75, seconds=3, timeout_s=180)


def _phase_walk_zone(b):
    b.walk(ZONE, arrive=20)
    b.add("stand", seconds=30)


def _phase_walk_town(b):
    b.walk(TOWN)
    # Then the scavenger site's own street line through the town, with the stuck ladder.
    b.route(TOWN)
    b.add("stand", seconds=60)
    b.add("search_site", site=TOWN.split(":", 1)[1], timeout_s=240)
    b.add("combat", range_m=60, timeout_s=180)
    b.add("admin", cmd="fx_shoot_held", value="")
    b.add("climb", range_m=100, hold_s=90, timeout_s=360)
    b.add("cellar", classes_from=cellar_classes(), range_m=100, hold_s=20, timeout_s=240)


def cellar_classes():
    """Embed the survey candidates; the client cannot read the mission JSON."""
    data = json.loads((MISSION / "cellars" / "classes.json").read_text(encoding="utf-8"))
    classes = [row["BuildingClass"] for row in data["Classes"]]
    _validate_cellar_classes(classes)
    return classes


def _validate_cellar_classes(classes):
    if (not isinstance(classes, list) or not 1 <= len(classes) <= 64
            or any(not isinstance(value, str) or not _TYPE.fullmatch(value) for value in classes)):
        raise ScriptError("cellar classes_from must be a list of 1..64 class names")
    if len(set(classes)) != len(classes):
        raise ScriptError("cellar classes_from must be unique")


def _phase_combat(b):
    # Town streets carry infected: raise, aim and reload at the nearest visible one (never fires).
    b.near(TOWN)
    b.add("combat", range_m=60, timeout_s=180)


def _phase_loot(b):
    # Whatever the town street offers: rifle magazines and ammunition first, then food, drink,
    # bandages and a map, each with the vanilla take action.
    b.near(TOWN)
    b.add("loot", range_m=40, max_items=4, timeout_s=300)


# Seconds the player keeps standing after a fixture, so the real code it starts can run.
FIXTURE_STAND = {"fx_conflict_journal": 60, "fx_barricade": 60, "fx_melee": 15, "fx_cooking": 20, "fx_kit_place": 8}


def _phase_fixtures(b):
    if "group" not in b.done:
        _phase_group(b)
    for cmd in FIXTURES:
        if cmd == "fx_site_patrol_kill":
            b.admin(cmd)
            b.walk(AI_SITE)
            b.admin(cmd)  # One retry after approaching the authored patrol site.
        elif cmd == "fx_die":
            if "ai_clear" in getattr(b, "requested", set()):
                continue  # Reserve the account's one respawn for the final driven phase.
            b.add("admin", cmd=cmd, value="")
            b.add("respawn", timeout_s=180)
        else:
            b.admin(cmd, FIXTURE_STAND.get(cmd, 3))
        if cmd == "fx_materialize":
            # Ledger rows move at runtime (HCWorldMaterializer.MaterializerRow). This fixed
            # mission-derived point is 1300 m west of the police site, not live-row evidence.
            anchor = resolve_waypoint(AI_SITE)
            point = [round(anchor[0] - 1300, 2), anchor[1]]
            timeout = min(3600, _timeout_for(b.distance_to(point), "jog") + 120)
            b.add("hold_ring", to=point, hold_s=120, timeout_s=timeout)
            b.position = b.last_walk_target = tuple(point)
            b.uncertain = False



def _phase_actions(b):
    # open_door reopens the door close_door shut, from where the player stands (in reach).
    for name in ("craft", "search", "close_door", "open_door"):
        b.action(name)
    b.action("mount")
    b.action("mount", target="TortillaBag")
    for name in ("salvage", "flip", "radio"):
        b.action(name)
    for cmd in ("radio", "loot", "decay", "deaddrop"):
        b.admin(cmd)


def _phase_scene(b):
    b.walk(SCENE)
    b.add("stand", seconds=20)
    b.admin("scene", 20)
    b.add("take_lead", timeout_s=180)
    b.action("take")
    b.action("read")
    b.action("write", use="taken")
    b.action("write", use="gear")


def _phase_forest(b):
    b.walk(FOREST)
    b.admin("forage", 20)
    b.action("pickup_forage")
    b.add("stand", seconds=60)


def site_candidates():
    """Flat [x, z, radius, ...] of patrol site anchors, one per 2 km cell (first by Id), at most 64."""
    cells = {}
    for site in sorted(_load("ai/sites.json").get("Sites", []), key=lambda row: str(row.get("Id"))):
        points = site.get("Waypoints") or []
        if site.get("Kind") != "patrol" or not points:
            continue
        x, z = _xz(points[0], "site:%s" % site.get("Id"))
        cell = (int(x // SITE_CELL_METERS), int(z // SITE_CELL_METERS))
        if cell in cells:
            continue
        radius = max(float(site.get("ActivationRadius") or 0.0), 600.0, SITE_RADIUS_FLOOR)
        cells[cell] = [x, z, round(min(radius, 7500.0), 1)]
    flat = []
    for cell in sorted(cells)[:MAX_SITE_CANDIDATES]:
        flat += cells[cell]
    if not flat:
        raise ScriptError("no patrol site with a waypoint in ai/sites.json")
    return flat


def _phase_mission(b):
    # A published mission zone (the client's own beacon rows); refused no-published-mission when the
    # server publishes none inside the timeout.
    b.add("enter", zone="mission", gait="jog", hold_s=60, timeout_s=1800)
    b.add("stand", seconds=20)


def _phase_vehicle(b):
    # Drive the car the actions phase flipped back onto its wheels (fx_car_side), the vanilla way. Run
    # alone, it places and rights that car first (the same setup-only fixture and the real flip).
    if "action:flip" not in b.done:
        b.admin("fx_car_side", FIXTURE_STAND.get("fx_car_side", 3))
        b.admin("fx_car_zeds")
        b.action("flip")
    b.add("vehicle", range_m=40, seconds=8, throttle=0.5, timeout_s=180)


def _phase_survive(b):
    # Eat and drink what the town loot and the forage gave; bandage if the town fight left a wound.
    b.add("survive", mode="always", timeout_s=120)


def ai_clear_targets(origin):
    """Offline reach preflight: held guard slots first, then police; bounded foot travel.

    Authored ground slots are candidates, never claims of live actors or navmesh reachability.
    The existing walk's arrival/stuck result is the native reach evidence.
    """
    candidates = []
    for zone in _load("ai/zones.json").get("zones", []):
        slots = zone.get("guard_slots") or []
        if zone.get("default_state") != "held" or not slots:
            continue
        point = _xz(slots[0], "guard-slot")
        distance = math.dist(origin, point)
        if distance <= 1800:
            candidates.append((0, distance, "zone:" + zone["id"], point))
    point = resolve_waypoint(AI_SITE)
    if math.dist(origin, point) <= 1800:
        candidates.append((1, math.dist(origin, point), AI_SITE, point))
    candidates.sort()
    if not candidates:
        return []
    first = candidates[0]
    # A second distinct authored site must be within the same short on-foot reach envelope.
    second = sorted((math.dist(first[3], row[3]), row) for row in candidates[1:]
                    if math.dist(first[3], row[3]) <= 500)
    return [first] + ([second[0][1]] if second else [])


def _phase_ai_clear(b):
    origin = b.last_walk_target if b.uncertain else b.position
    targets = ai_clear_targets(origin)
    if not targets:
        # No position writes and no speculative cross-map route. Retain a visible preflight note.
        b.add("stand", seconds=1, note="ai_clear:skip:no-authored-site-within-1800m")
        return
    for mode, (_, distance, source, point) in enumerate(targets):
        # Use the authored guard slot rather than a potentially remote zone centre.
        leg = b.distance_to(point)
        b.add("walk", to=list(point), gait="jog", arrive_m=50,
              timeout_s=_timeout_for(leg, "jog"),
              note="ai_clear:target=" + source + ":reason=held-guard-slot-or-police;reach=bounded-foot")
        b.position = b.last_walk_target = point
        b.uncertain = False
        b.add("stand", seconds=20)
        if mode == 0:
            b.admin("fx_incident")
            b.admin("fx_tactic")
        b.add("admin", cmd="fx_site_clear", value=str(mode))
        # Existing stand has no server-line predicate; the full 200 s covers the 180 s fixture cap.
        b.add("stand", seconds=200)
        b.add("stand", seconds=120)
    if len(targets) == 1:
        # A clear removes the live first site. Let the fixture select another live patrol nearby;
        # otherwise it reports no-patrol without damage. Both modes are always requested.
        b.add("admin", cmd="fx_site_clear", value="1")
        b.add("stand", seconds=200)
        b.add("stand", seconds=120)
    b.add("admin", cmd="fx_die", value="")
    b.add("respawn", timeout_s=180)
    # No existing step can target the runtime death position: no return walk is fabricated.


def _phase_idle(b):
    b.add("stand", seconds=60)


_PHASE_BUILDERS = {
    "join": _phase_join, "group": _phase_group, "walk_ai": _phase_walk_ai,
    "walk_zone": _phase_walk_zone, "walk_town": _phase_walk_town, "combat": _phase_combat,
    "loot": _phase_loot, "fixtures": _phase_fixtures, "actions": _phase_actions, "vehicle": _phase_vehicle,
    "scene": _phase_scene, "forest": _phase_forest, "survive": _phase_survive, "mission": _phase_mission,
    "ai_clear": _phase_ai_clear, "idle": _phase_idle,
}


def build_plan(phases, *, phase_ranges=None, server_rpt=None):
    """(script dict, {step id: waypoint source}) for the named phases, in the order given."""
    if not isinstance(phases, (list, tuple)) or not phases:
        raise ScriptError("phases must be a non-empty list")
    builder = _Builder(server_rpt)
    builder.requested = set(phases)
    for phase in phases:
        if phase not in _PHASE_BUILDERS:
            raise ScriptError("unknown phase %r (known: %s)" % (phase, ", ".join(PHASES)))
        start = len(builder.steps)
        _PHASE_BUILDERS[phase](builder)
        if phase_ranges is not None:
            phase_ranges[phase] = (start, len(builder.steps))
    digest = hashlib.sha256(json.dumps(builder.steps, sort_keys=True).encode("utf-8")).hexdigest()
    script = {"version": VERSION, "run_id": "r" + digest[:10], "steps": builder.steps}
    validate_script(script)
    return script, builder.notes


def step_token(step, notes):
    """The reach-map token of a step: wait|stand|sprint|ping, menu:<name>, admin:<cmd>, group:<op>,
    action:<name>, enter:<zone>, walk:<waypoint source> or route:<route source>. A fixture is also reachable as fixture:<cmd>."""
    kind = step["kind"]
    if kind == "enter":
        return "enter:" + step["zone"]
    if kind == "menu":
        return "menu:" + step["name"]
    if kind == "admin":
        return "admin:" + step["cmd"]
    if kind == "group":
        return "group:" + step["op"]
    if kind == "action":
        return "action:" + step["name"]
    if kind == "walk":
        return "walk:" + notes.get(step["id"], "")
    if kind == "route":
        return "route:" + notes.get(step["id"], "")
    return kind


def phase_index():
    """{phase: {token: [step ids]}} of the default route, the ids the written step file will carry."""
    builder = _Builder()
    builder.requested = set(PHASES)
    index = {}
    for phase in PHASES:
        start = len(builder.steps)
        _PHASE_BUILDERS[phase](builder)
        tokens = index.setdefault(phase, {})
        for step in builder.steps[start:]:
            tokens.setdefault(step_token(step, builder.notes), []).append(step["id"])
            if step["kind"] == "admin" and step["cmd"].startswith("fx_"):
                tokens.setdefault("fixture:" + step["cmd"], []).append(step["id"])
    return index


def build_route(phases):
    """The step file for the phases, in the order given. Raises ScriptError on a bad request."""
    return build_plan(phases)[0]


def build_r3():
    """(script, notes) of the no-human R3 client smoke (release_gate --client-mode scripted): the six
    categories map, inventory, groups (the M map's group frame), admin, ai (site radius) and event
    (mission radius), each through the same real client path a tester would use."""
    builder = _Builder()
    builder.add("wait", seconds=30)
    builder.add("stand", seconds=5)
    for name in ("map", "inventory", "admin"):
        builder.add("menu", name=name, seconds=4)
    builder.add("enter", zone="site", sites=site_candidates(), gait="jog", hold_s=120, timeout_s=1800)
    builder.add("enter", zone="mission", gait="jog", hold_s=60, timeout_s=1500)
    builder.add("stand", seconds=30)
    digest = hashlib.sha256(json.dumps(builder.steps, sort_keys=True).encode("utf-8")).hexdigest()
    script = {"version": VERSION, "run_id": "r3" + digest[:10], "steps": builder.steps}
    validate_script(script)
    return script, builder.notes


def _number(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ScriptError("%s must be a finite number" % label)
    if not low <= value <= high:
        raise ScriptError("%s outside %s..%s" % (label, low, high))


def _string(value, label, limit=64):
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ScriptError("%s must be a short printable string" % label)


def _validate_args(name, args, label):
    if not isinstance(args, dict):
        raise ScriptError("%s args must be an object" % label)
    required, optional = ACTION_ARGS[name]
    allowed = set(required) | set(optional)
    unknown = set(args) - allowed
    if unknown:
        raise ScriptError("%s unknown args %s" % (label, sorted(unknown)))
    for key in required:
        if key not in args:
            raise ScriptError("%s missing arg %s" % (label, key))
    for key, value in args.items():
        if key == "freq":
            if not isinstance(value, str) or not _FREQ.match(value):
                raise ScriptError("%s freq must be a string like 87.8" % label)
        elif not isinstance(value, str) or not _TYPE.match(value):
            raise ScriptError("%s arg %s must be a class name string" % (label, key))


def validate_step(step, label="step"):
    if not isinstance(step, dict):
        raise ScriptError("%s must be an object" % label)
    kind = step.get("kind")
    if kind not in KINDS:
        raise ScriptError("%s unknown kind %r" % (label, kind))
    unknown = set(step) - _COMMON - _STEP_FIELDS[kind]
    if unknown:
        raise ScriptError("%s unknown fields %s" % (label, sorted(unknown)))
    if not isinstance(step.get("id"), str) or not _STEP_ID.match(step["id"]):
        raise ScriptError("%s id must look like s01" % label)
    if kind in ("wait", "stand", "sprint"):
        _number(step.get("seconds"), 0, 3600, label + " seconds")
    elif kind == "menu":
        if step.get("name") not in MENUS:
            raise ScriptError("%s menu name must be one of %s" % (label, MENUS))
        _number(step.get("seconds"), 0, 60, label + " seconds")
    elif kind == "walk":
        target = step.get("to")
        if not isinstance(target, list) or len(target) != 2:
            raise ScriptError("%s to must be [x, z]" % label)
        _number(target[0], 0, WORLD_SIZE, label + " to.x")
        _number(target[1], 0, WORLD_SIZE, label + " to.z")
        if step.get("gait") not in GAITS:
            raise ScriptError("%s gait must be one of %s" % (label, GAITS))
        _number(step.get("arrive_m"), 1, 50, label + " arrive_m")
        _number(step.get("timeout_s"), 1, 3600, label + " timeout_s")
    elif kind == "admin":
        command = step.get("cmd")
        if not isinstance(command, str) or not _CMD.match(command):
            raise ScriptError("%s cmd must be a lower-case command word" % label)
        if command in _FORBIDDEN_CMDS or command.startswith("tp"):
            raise ScriptError("%s command %s would teleport a player" % (label, command))
        _string(step.get("value"), label + " value")
        if not re.fullmatch(r"(0|[1-9][0-9]{0,8})?", step["value"]):
            raise ScriptError(label + " value must be empty or digits")
    elif kind == "group":
        if step.get("op") not in GROUP_OPS:
            raise ScriptError("%s group op must be one of %s" % (label, GROUP_OPS))
    elif kind == "enter":
        zone = step.get("zone")
        if zone not in ENTER_ZONES:
            raise ScriptError("%s enter zone must be one of %s" % (label, ENTER_ZONES))
        sites = step.get("sites")
        if zone == "site":
            if not isinstance(sites, list) or not 3 <= len(sites) <= 3 * MAX_SITE_CANDIDATES or len(sites) % 3:
                raise ScriptError("%s sites must be a flat [x, z, radius, ...] list of 1..%d sites"
                                  % (label, MAX_SITE_CANDIDATES))
            for index in range(0, len(sites), 3):
                _number(sites[index], 0, WORLD_SIZE, label + " sites.x")
                _number(sites[index + 1], 0, WORLD_SIZE, label + " sites.z")
                _number(sites[index + 2], 50, 7500, label + " sites.radius")
        elif sites is not None:
            raise ScriptError("%s sites only belong to zone site" % label)
        if step.get("gait") not in GAITS:
            raise ScriptError("%s gait must be one of %s" % (label, GAITS))
        _number(step.get("hold_s"), 10, 540, label + " hold_s")
        _number(step.get("timeout_s"), 30, 3600, label + " timeout_s")
    elif kind == "route":
        points = step.get("points")
        if (not isinstance(points, list) or len(points) % 2
                or not 4 <= len(points) <= 2 * MAX_ROUTE_POINTS):
            raise ScriptError("%s points must be a flat [x, z, ...] list of 2..%d waypoints"
                              % (label, MAX_ROUTE_POINTS))
        for index in range(0, len(points), 2):
            _number(points[index], 0, WORLD_SIZE, label + " points.x")
            _number(points[index + 1], 0, WORLD_SIZE, label + " points.z")
        if step.get("gait") not in GAITS:
            raise ScriptError("%s gait must be one of %s" % (label, GAITS))
        _number(step.get("arrive_m"), 2, 50, label + " arrive_m")
        _number(step.get("timeout_s"), 10, 3600, label + " timeout_s")
    elif kind in ("climb", "cellar"):
        if kind == "cellar":
            _validate_cellar_classes(step.get("classes_from"))
        _number(step.get("range_m"), 5, 150, label + " range_m")
        _number(step.get("hold_s"), 1, 600, label + " hold_s")
        _number(step.get("timeout_s"), 10, 1800, label + " timeout_s")
        if step["timeout_s"] <= step["hold_s"]:
            raise ScriptError(label + " timeout_s must exceed hold_s")
    elif kind == "combat":
        _number(step.get("range_m"), COMBAT_RANGE[0], COMBAT_RANGE[1], label + " range_m")
        _number(step.get("timeout_s"), 10, 1800, label + " timeout_s")
    elif kind == "loot":
        _number(step.get("range_m"), LOOT_RANGE[0], LOOT_RANGE[1], label + " range_m")
        max_items = step.get("max_items")
        if isinstance(max_items, bool) or not isinstance(max_items, int) or not 1 <= max_items <= LOOT_MAX_ITEMS:
            raise ScriptError("%s max_items must be an integer 1..%d" % (label, LOOT_MAX_ITEMS))
        _number(step.get("timeout_s"), 10, 1800, label + " timeout_s")
    elif kind == "survive":
        if step.get("mode") not in SURVIVE_MODES:
            raise ScriptError("%s survive mode must be one of %s" % (label, SURVIVE_MODES))
        _number(step.get("timeout_s"), 10, 600, label + " timeout_s")
    elif kind == "vehicle":
        _number(step.get("range_m"), VEHICLE_RANGE[0], VEHICLE_RANGE[1], label + " range_m")
        _number(step.get("seconds"), VEHICLE_SECONDS[0], VEHICLE_SECONDS[1], label + " seconds")
        _number(step.get("throttle"), VEHICLE_THROTTLE[0], VEHICLE_THROTTLE[1], label + " throttle")
        _number(step.get("timeout_s"), 30, 600, label + " timeout_s")
    elif kind in ("search_site", "take_lead", "raise", "hold_ring", "respawn"):
        _number(step.get("timeout_s"), 10, 3600, label + " timeout_s")
        if kind == "search_site":
            site = step.get("site")
            if not isinstance(site, str) or not re.fullmatch(r"[a-z0-9-]{1,64}", site):
                raise ScriptError(label + " site must be an authored site id")
            resolve_waypoint("site:" + site)
        elif kind == "raise":
            _number(step.get("range_min_m"), 40.1, 79, label + " range_min_m")
            _number(step.get("range_max_m"), 41, 80, label + " range_max_m")
            if step["range_min_m"] >= step["range_max_m"]:
                raise ScriptError(label + " raise ranges must be increasing")
            _number(step.get("seconds"), 1, 30, label + " seconds")
            if step["timeout_s"] <= step["seconds"]:
                raise ScriptError(label + " timeout must exceed raise duration")
        elif kind == "hold_ring":
            point = step.get("to")
            if not isinstance(point, list) or len(point) != 2:
                raise ScriptError(label + " to must be [x, z]")
            for value in point:
                _number(value, 0, WORLD_SIZE, label + " to")
            _number(step.get("hold_s"), 10, 600, label + " hold_s")
            if step["timeout_s"] <= step["hold_s"]:
                raise ScriptError(label + " timeout must exceed hold duration")
    elif kind == "action":
        name = step.get("name")
        if name not in ACTION_ARGS:
            raise ScriptError("%s unknown action kind %r" % (label, name))
        _validate_args(name, step.get("args"), label)
        _number(step.get("timeout_s"), 1, 3600, label + " timeout_s")


def validate_script(script):
    if not isinstance(script, dict):
        raise ScriptError("step file must be an object")
    unknown = set(script) - _TOP_FIELDS
    if unknown:
        raise ScriptError("unknown top-level fields %s" % sorted(unknown))
    if script.get("version") != VERSION or isinstance(script.get("version"), bool):
        raise ScriptError("version must be %d" % VERSION)
    if not isinstance(script.get("run_id"), str) or not _RUN_ID.match(script["run_id"]):
        raise ScriptError("run_id must be a short id")
    steps = script.get("steps")
    if not isinstance(steps, list) or not steps or len(steps) > MAX_STEPS:
        raise ScriptError("steps must be a list of 1..%d" % MAX_STEPS)
    seen = set()
    for index, step in enumerate(steps):
        validate_step(step, "steps[%d]" % index)
        if step["id"] in seen:
            raise ScriptError("steps[%d] duplicate id %s" % (index, step["id"]))
        seen.add(step["id"])


def describe(step, notes):
    kind = step["kind"]
    if kind == "walk":
        detail = "to=%s,%s gait=%s arrive_m=%s timeout_s=%s" % (
            step["to"][0], step["to"][1], step["gait"], step["arrive_m"], step["timeout_s"])
        if step["id"] in notes:
            detail += " source=" + notes[step["id"]]
    elif kind in ("wait", "stand", "sprint"):
        detail = "seconds=%s" % step["seconds"]
    elif kind == "menu":
        detail = "name=%s seconds=%s" % (step["name"], step["seconds"])
    elif kind == "admin":
        detail = "cmd=%s value=%s" % (step["cmd"], step["value"])
    elif kind == "group":
        detail = "op=%s" % step["op"]
    elif kind == "enter":
        detail = "zone=%s gait=%s hold_s=%s timeout_s=%s" % (
            step["zone"], step["gait"], step["hold_s"], step["timeout_s"])
        if "sites" in step:
            detail += " candidates=%d" % (len(step["sites"]) // 3)
    elif kind == "route":
        detail = "waypoints=%d gait=%s arrive_m=%s timeout_s=%s" % (
            len(step["points"]) // 2, step["gait"], step["arrive_m"], step["timeout_s"])
        if step["id"] in notes:
            detail += " source=" + notes[step["id"]]
    elif kind in ("climb", "cellar"):
        detail = "range_m=%s hold_s=%s timeout_s=%s" % (step["range_m"], step["hold_s"], step["timeout_s"])
        if kind == "cellar":
            detail += " classes=%d" % len(step["classes_from"])
    elif kind == "combat":
        detail = "range_m=%s timeout_s=%s (fire=unsupported)" % (step["range_m"], step["timeout_s"])
    elif kind == "loot":
        detail = "range_m=%s max_items=%s timeout_s=%s" % (step["range_m"], step["max_items"], step["timeout_s"])
    elif kind == "survive":
        detail = "mode=%s timeout_s=%s" % (step["mode"], step["timeout_s"])
    elif kind == "vehicle":
        detail = "range_m=%s seconds=%s throttle=%s timeout_s=%s" % (
            step["range_m"], step["seconds"], step["throttle"], step["timeout_s"])
    elif kind in ("search_site", "take_lead", "raise", "hold_ring", "respawn"):
        detail = " ".join("%s=%s" % (key, value) for key, value in step.items() if key not in _COMMON)
    elif kind == "action":
        detail = "name=%s args=%s timeout_s=%s" % (
            step["name"], json.dumps(step["args"], sort_keys=True), step["timeout_s"])
        if step["name"] in UNSUPPORTED_ACTIONS:
            detail += " (expected result=unsupported)"
    else:
        detail = ""
    return "%s %-6s %s" % (step["id"], kind, detail)


def _phases_arg(text):
    return [part for part in text.split(",") if part]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "write"):
        child = sub.add_parser(name)
        if name == "write":
            child.add_argument("path", type=Path)
        child.add_argument("--server-rpt", type=Path, help="current boot RPT for shelter waypoints")
        child.add_argument("--route", default="default", choices=("default", "r3"),
                           help="r3: the no-human R3 client smoke (ignores --phases)")
        child.add_argument("--phases", type=_phases_arg, default=DEFAULT_PHASES,
                           help="comma list of: " + ",".join(PHASES))
    check = sub.add_parser("validate")
    check.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            validate_script(json.loads(args.path.read_text(encoding="utf-8")))
            print("valid: true")
            return 0
        if args.route == "r3":
            script, notes = build_r3()
        else:
            script, notes = build_plan(args.phases, server_rpt=args.server_rpt)
        if args.command == "plan":
            print("run_id=%s steps=%d" % (script["run_id"], len(script["steps"])))
            for step in script["steps"]:
                print(describe(step, notes))
            return 0
        args.path.parent.mkdir(parents=True, exist_ok=True)
        args.path.write_text(json.dumps(script, indent=1) + "\n", encoding="utf-8")
        print("wrote run_id=%s steps=%d" % (script["run_id"], len(script["steps"])))
        return 0
    except (ScriptError, OSError, ValueError) as exc:
        print("driver_script: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
