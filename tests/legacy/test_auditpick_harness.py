"""#144/#150 audit-pick: shared synthetic harness for the authored HCPick* classes.

The authored Enforce bodies in World/auditpick_*.c run through the repo's syntax-only
translator over explicit SYNTHETIC fakes. Nothing here observes DayZ; runtime
acceptance of every behaviour is PENDING.
"""
import re
import json
import unittest
from pathlib import Path
from types import MethodType, SimpleNamespace as N

from tests.legacy.test_group_server import EArray
from tests.legacy.test_map_layers import EStr, translate

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / 'mods/HollowCountry/scripts/4_World/World'
POLICY = WORLD / 'auditpick_Policy.c'
DANGER = WORLD / 'auditpick_Danger.c'
HOUSES = WORLD / 'auditpick_Houses.c'
SURVEY = ROOT / 'mission/hollow-country/ai/picker-routes.json'
PICKERS = WORLD / 'HCPickers.c'


def to_ns(value):
    if isinstance(value, dict):
        return N(**{k: to_ns(v) for k, v in value.items()})
    if isinstance(value, list):
        return EArray([to_ns(v) for v in value])
    return value


def shipped_survey(**changes):
    """The shipped survey as a synthetic namespace; routes get a HCPosition per point."""
    data = json.loads(SURVEY.read_text())
    data.update(changes)
    node = to_ns(data)
    for route in node.Routes:
        for point in route.Waypoints:
            point.HCPosition = (lambda p: lambda: [p.X, p.Y, p.Z])(point)
    return node


class Native:
    """Explicit native adapters: file system, clock, weather owner, infected memory."""

    def __init__(self):
        self.opted_out = False
        self.season = 0
        self.weather = True
        self.weather_calls = []
        self.heat = {}
        self.prints = []
        self.tick = 100.0
        self.utc = 1000
        self.budget = True

    def env(self):
        weather = N(HCSeasonPhaseCode=lambda: (self.weather_calls.append('phase'), self.season)[1])
        server = N(HCAdminModuleNamed=lambda name: weather if self.weather and name == 'WeatherDays' else None)
        return dict(
            FileExist=lambda path: self.opted_out and str(path).endswith('scavenge_runs.disable'),
            HCServer=N(Get=lambda: server, HCTickWork=lambda: N(HCTake=lambda n: self.budget)),
            HCWeatherDaysModule=N(Cast=lambda module: module),
            HCInfectedMemory=N(Heat=lambda pos: self.heat.get(tuple(pos), 0.0)),
            Math=N(Max=max, Min=min, Round=round),
            Print=lambda text: self.prints.append(str(text)),
            GetGame=lambda: N(GetTickTime=lambda: self.tick),
            HCWorldClock=N(UTC=lambda: self.utc),
            vector=N(DistanceSq=lambda a, b: sum((x - y) ** 2 for x, y in zip(a, b))),
        )


def _bind(source, owner, target, names, env):
    import re
    source = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', source)
    translate(source, owner, env, only=names)
    for name in names:
        setattr(target, name, MethodType(env[name], target))


def policy(native=None):
    """HCPickPolicy statics as a namespace plus the class constants."""
    native = native or Native()
    env = native.env()
    env['IDiv'] = lambda a, b: a // b
    # Enforce int/int is integer division; the Python adapter would give a float.
    source = re.sub(r'\((survey\.\w+ \* [^()]*(?:\([^()]*\))?)\) / 100', r'IDiv(\1, 100)', POLICY.read_text())
    consts = N(OPT_OUT=EStr('$profile:HollowCountry/acceptance/scavenge_runs.disable'),
               NEED_REFUSAL=EStr('PICKER_NO_SUPPLY_NEED'), DANGER_REFUSAL=EStr('PICKER_ROUTE_DANGER'))
    env['HCPickPolicy'] = consts
    translate(source, 'HCPickPolicy', env)
    names = ('Enabled', 'SeasonPhase', 'NeedPercent', 'NeedTarget', 'NeedsSupplies', 'PartyRefusal',
             'ActiveTrip', 'CapRefusal', 'RouteDanger', 'Deferred', 'RunRefusal')
    for name in names:
        setattr(consts, name, env[name])
    # Callers hand plain Python strings; the authored body uses native string methods.
    deferred = env['Deferred']
    consts.Deferred = lambda refusal: deferred(EStr(refusal))
    return consts


def danger():
    target = N(Routes=EArray(), Kinds=EArray(), Times=EArray())
    # The adapter only recognises capitalised member types; the members are the same.
    source = re.sub(r'^    ref array<', '    ref Array<', DANGER.read_text(), flags=re.M)
    _bind(source, 'HCPickDanger', target, ('HCPrune', 'HCNote', 'HCFresh', 'HCCount'), {})
    return target


class HarnessSmoke(unittest.TestCase):
    def test_policy_translates(self):
        self.assertEqual('', policy().RunRefusal(shipped_survey()))
