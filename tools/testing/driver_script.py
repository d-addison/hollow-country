"""Build and validate the step file for the dev-only scripted client driver (mods/HollowCountryTest).

The client driver reads `$profile:HollowCountry/acceptance/client_driver.json` and runs the steps
strictly in order. This module is the only writer of that file: it picks waypoints from repo data
(ai/sites.json, ai/zones.json, travel/route-surveys.json), builds the default campaign route and
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
PHASES = ("join", "group", "walk_ai", "walk_zone", "walk_town", "fixtures", "actions", "scene", "forest",
          "mission", "idle")
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
# Forest phase: an existing authored barn of travel/route-surveys.json set in woodland (forage
# habitats and the forest wind loop need a wooded surface under the player).
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
FIXTURES = ("fx_car_side", "fx_camp_setup", "fx_wreck", "fx_holdout_due", "fx_conflict",
            "fx_materialize", "fx_incident", "fx_tactic", "fx_trade", "fx_convoy_stuck",
            "fx_animal", "fx_food", "fx_cooking", "fx_kit_place", "fx_kit_refuse", "fx_barricade",
            "fx_melee", "fx_shoot")
# Server commands the player's own admin RPC runs on the real module path (HCAdminModule.HCExtra and
# the command list): they ask a module to do its normal bounded work now, they never spawn a counter.
ADMIN_STEPS = ("status", "snapshot", "scene", "radio", "deaddrop", "loot", "forage", "decay")

GAITS = ("walk", "jog", "sprint")
MENUS = ("map", "inventory", "pause", "admin")
GROUP_OPS = ("create_solo",)
KINDS = ("wait", "walk", "stand", "sprint", "menu", "admin", "group", "ping", "action", "enter", "route",
         "combat", "loot")
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
    "combat": {"range_m", "timeout_s"},
    "loot": {"range_m", "max_items", "timeout_s"},
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


def resolve_waypoint(source):
    """`site:<id>` first waypoint of an ai/sites.json site, `zone:<id>` centre of an ai/zones.json
    zone, `shelter:<id or name>` position of a travel/route-surveys.json shelter, `scene:<chain id>`
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
    if kind == "shelter":
        surveys = _load("travel/route-surveys.json")
        rows = list(surveys.get("existing_shelters", [])) + list(surveys.get("regional_candidates", []))
        for row in rows:
            if ident in (row.get("id"), row.get("name")):
                return _xz(row.get("position"), source)
        raise ScriptError("no shelter %s" % ident)
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
    def __init__(self):
        self.steps = []
        self.notes = {}
        self.position = None

    def add(self, kind, note="", **fields):
        step = {"id": "s%02d" % (len(self.steps) + 1), "kind": kind}
        step.update(fields)
        self.steps.append(step)
        if note:
            self.notes[step["id"]] = note
        return step

    def walk(self, source, gait="jog", arrive=5):
        x, z = resolve_waypoint(source)
        if self.position is None:
            distance = 6000.0
        else:
            distance = math.hypot(x - self.position[0], z - self.position[1])
        self.position = (x, z)
        self.add("walk", note=source, to=[x, z], gait=gait, arrive_m=arrive,
                 timeout_s=_timeout_for(distance, gait))

    def route(self, source, gait="jog", arrive=5):
        points = resolve_route(source)
        distance = 0.0
        last = self.position or points[0]
        for point in points:
            distance += math.hypot(point[0] - last[0], point[1] - last[1])
            last = point
        self.position = points[-1]
        flat = [value for point in points for value in point]
        # Each ladder climb costs up to about 14 s (8 s stuck + a 2 s move or a 6 s door scan).
        self.add("route", note=source, points=flat, gait=gait, arrive_m=arrive,
                 timeout_s=min(3600, _timeout_for(distance, gait) + 30 * len(points)))

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


def _phase_walk_zone(b):
    b.walk(ZONE, arrive=20)
    b.add("stand", seconds=30)


def _phase_walk_town(b):
    b.walk(TOWN)
    # Then the scavenger site's own street line through the town, with the stuck ladder.
    b.route(TOWN)
    b.add("stand", seconds=60)
    # Town streets carry infected: raise, aim and reload at the nearest visible one.
    b.add("combat", range_m=60, timeout_s=180)
    # Then whatever the streets offer: rifle magazines, food, drink, bandages, a map.
    b.add("loot", range_m=40, max_items=4, timeout_s=300)


# Seconds the player keeps standing after a fixture, so the real code it starts can run.
FIXTURE_STAND = {"fx_barricade": 60, "fx_melee": 15, "fx_cooking": 20, "fx_shoot": 8, "fx_kit_place": 8}


def _phase_fixtures(b):
    for cmd in FIXTURES:
        b.admin(cmd, FIXTURE_STAND.get(cmd, 3))


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


def _phase_idle(b):
    b.add("stand", seconds=60)


_PHASE_BUILDERS = {
    "join": _phase_join, "group": _phase_group, "walk_ai": _phase_walk_ai,
    "walk_zone": _phase_walk_zone, "walk_town": _phase_walk_town, "fixtures": _phase_fixtures,
    "actions": _phase_actions, "scene": _phase_scene, "forest": _phase_forest, "mission": _phase_mission,
    "idle": _phase_idle,
}


def build_plan(phases):
    """(script dict, {step id: waypoint source}) for the named phases, in the order given."""
    if not isinstance(phases, (list, tuple)) or not phases:
        raise ScriptError("phases must be a non-empty list")
    builder = _Builder()
    for phase in phases:
        if phase not in _PHASE_BUILDERS:
            raise ScriptError("unknown phase %r (known: %s)" % (phase, ", ".join(PHASES)))
        _PHASE_BUILDERS[phase](builder)
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
    index = {}
    for phase in PHASES:
        start = len(builder.steps)
        _PHASE_BUILDERS[phase](builder)
        tokens = index.setdefault(phase, {})
        for step in builder.steps[start:]:
            tokens.setdefault(step_token(step, builder.notes), []).append(step["id"])
            if step["kind"] == "admin" and step["cmd"] in FIXTURES:
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
    elif kind == "combat":
        _number(step.get("range_m"), COMBAT_RANGE[0], COMBAT_RANGE[1], label + " range_m")
        _number(step.get("timeout_s"), 10, 1800, label + " timeout_s")
    elif kind == "loot":
        _number(step.get("range_m"), LOOT_RANGE[0], LOOT_RANGE[1], label + " range_m")
        max_items = step.get("max_items")
        if isinstance(max_items, bool) or not isinstance(max_items, int) or not 1 <= max_items <= LOOT_MAX_ITEMS:
            raise ScriptError("%s max_items must be an integer 1..%d" % (label, LOOT_MAX_ITEMS))
        _number(step.get("timeout_s"), 10, 1800, label + " timeout_s")
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
    elif kind == "combat":
        detail = "range_m=%s timeout_s=%s (fire=unsupported)" % (step["range_m"], step["timeout_s"])
    elif kind == "loot":
        detail = "range_m=%s max_items=%s timeout_s=%s" % (step["range_m"], step["max_items"], step["timeout_s"])
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
            script, notes = build_plan(args.phases)
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
