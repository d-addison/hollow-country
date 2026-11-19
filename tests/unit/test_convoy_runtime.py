"""#210 road branch: convoys borrow a qualified world car, drive bounded road
waypoints and dismount to walk.

Authored Enforce bodies run through the restricted translator against explicit
synthetic cars, members, groups, roads and budgets. Nothing here establishes
DayZ physics, seating, AI driving or replication: runtime stays PENDING.
"""
import json
import math
import re
import unittest
from pathlib import Path
from types import MethodType, SimpleNamespace as N

from tests.unit.test_group_server import EArray
from tests.unit.test_map_layers import EStr, methods, translate
from tools.setup import friend_bundle

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World'
POLICY = ROOT / 'mods/HollowCountry/scripts/4_World/Events/HCConvoyPolicy.c'
ROUTE = AI / 'HCXConvoyRoute.c'
RUNTIME = AI / 'HCXConvoyRuntime.c'

MATH = N(PI=math.pi, Clamp=lambda v, lo, hi: max(lo, min(hi, v)), AbsFloat=abs, Sqrt=math.sqrt)
SITUATIONS = 11


class Arr(EArray):
    def Set(self, index, value): self[index] = value


class Budget:
    def __init__(self, units=10 ** 9):
        self.units, self.calls = units, []

    def HCTakeFor(self, consumer, cost):
        self.calls.append((consumer, cost))
        if self.units < cost:
            return False
        self.units -= cost
        return True


def flat(a, b):
    return math.hypot(a[0] - b[0], a[2] - b[2])


def defaults():
    text = POLICY.read_text()
    text = text[text.index('class HCConvoyPolicy'):]
    found = {}
    for kind, name, value in re.findall(r'^    (int|float) (\w+) = ([-\d.]+);', text, re.M):
        found[name] = int(value) if kind == 'int' else float(value)
    return N(**found)


def bind(path, class_name, env, obj, skip=()):
    source = path.read_text()
    table, _ = methods(source, class_name)
    wanted = tuple(name for name in table if name not in skip)
    translate(source, class_name, env, only=wanted)
    for name in wanted:
        if not table[name][0]:
            setattr(obj, name, MethodType(env[name], obj))
    return obj


def rules():
    env = dict(Math=MATH)
    translate(POLICY.read_text(), 'HCConvoyRules', env)
    return N(HCVehicleProblem=env['HCVehicleProblem'], HCControl=env['HCControl'], HCStalled=env['HCStalled'])


def flat_port():
    env = dict(Math=MATH)
    translate(ROUTE.read_text(), 'HCXConvoyRoute', env, only=('HCFlat', 'HCFlatSq'))
    return N(HCFlat=env['HCFlat'], HCFlatSq=env['HCFlatSq'])


class Car:
    def __init__(self, x, z=0.0, seats=4):
        self.pos = [x, 0.0, z]
        self.destroyed = self.flipped = self.engine = False
        self.operational = True
        self.wheels = self.present = 4
        self.crew = [None] * seats
        self.cargo, self.speed, self.gear = 0, 0.0, 1
        self.calls = []

    def GetPosition(self): return self.pos
    def GetDirection(self): return [0.0, 0.0, 1.0]
    def IsDamageDestroyed(self): return self.destroyed
    def CheckOperationalState(self): return self.operational
    def WheelCount(self): return self.wheels
    def WheelCountPresent(self): return self.present
    def CrewSize(self): return len(self.crew)
    def CrewMember(self, seat): return self.crew[seat]
    def HasCrew(self): return any(self.crew)
    def IsFlipped(self): return self.flipped
    def GetInventory(self): return N(GetCargo=lambda: N(GetItemCount=lambda: self.cargo))
    def GetSpeedometerAbsolute(self): return self.speed
    def EngineIsOn(self): return self.engine
    def GetGear(self): return self.gear
    def EngineStart(self): self.calls.append('start'); self.engine = True
    def EngineStop(self): self.calls.append('stop'); self.engine = False
    def ShiftTo(self, gear): self.calls.append(('gear', gear)); self.gear = gear
    def SetSteering(self, value): self.calls.append(('steer', value))
    def SetThrottle(self, value): self.calls.append(('throttle', value))
    def SetBrake(self, value): self.calls.append(('brake', value))
    def SetHandbrake(self, value): self.calls.append(('handbrake', value))


class Member:
    def __init__(self, x, group=None):
        self.pos = [x, 0.0, 0.0]
        self.alive, self.parent, self.group = True, None, group
        self.exits, self.boarded, self.idle = [], [], True
        self.command = N(GetOutVehicle=lambda: self.exits.append('out'))

    def GetPosition(self): return self.pos
    def IsAlive(self): return self.alive
    def GetParent(self): return self.parent
    def IsInTransport(self): return self.parent is not None
    def GetGroup(self): return self.group
    def Notify_Transport(self, car, seat): self.boarded.append((car, seat))
    def Expansion_IsAnimationIdle(self): return self.idle
    def GetCommand_Vehicle(self):
        return self.command if self.parent is not None else None


class Group:
    def __init__(self, size=2, route=([0.0, 0.0, 0.0], [600.0, 0.0, 0.0])):
        self.members = [Member(0.0, self) for _ in range(size)]
        self.points = Arr(list(route))
        self.behaviour, self.combat, self.formation = 7, False, 1
        self.calls = []

    def GetFormationLeader(self): return self.members[0]
    def GetMember(self, index): return self.members[index]
    def Count(self): return len(self.members)
    def GetWaypoints(self): return Arr(list(self.points))
    def GetWaypointBehaviour(self): return self.behaviour
    def IsInCombat(self): return self.combat
    def GetFormationState(self): return self.formation
    def ClearWaypoints(self): self.points = Arr(); self.calls.append('clear')
    def AddWaypoint(self, point): self.points.Insert(point)
    def SetWaypointBehaviour(self, behaviour): self.behaviour = behaviour; self.calls.append(('behaviour', behaviour))


class FakeRoute:
    def __init__(self, path, ready=True):
        self.mHCPath = Arr(path)
        self.mHCPhase, self.mHCReason = EStr('idle'), EStr('')
        self.ready, self.plans = ready, []

    def HCPlan(self, origin, destination, policy):
        self.plans.append((origin, destination))
        self.mHCPhase = EStr('scan')
        return True

    def HCStep(self):
        if self.ready:
            self.mHCPhase = EStr('ready')


class RunWorld:
    def __init__(self, cars=(), players=(), path=None, ready=True):
        self.policy = defaults()
        self.clock = [0]
        self.printed = []
        self.cars = list(cars)
        self.players = list(players)
        self.budget = Budget()
        self.angle = [0.0]
        self.group = Group()
        self.route = FakeRoute(path or [[50.0, 0.0, 0.0], [300.0, 0.0, 0.0], [480.0, 0.0, 0.0]], ready)
        game = N(GetTime=lambda: self.clock[0], GetObjectsAtPosition3D=self.query)
        director = N(NearestPlayer=lambda pos: min([flat(pos, p) for p in self.players] or [100000.0]))
        env = dict(Math=MATH, Math3D=N(AngleFromPosition=lambda origin, facing, target: self.angle[0]),
                   Vector=lambda x, y, z: [x, y, z], Print=self.printed.append, GetGame=lambda: game,
                   CarScript=N(Cast=lambda o: o if isinstance(o, Car) else None), eAIBase=N(Cast=lambda o: o),
                   DayZPlayerImplement=N(Cast=lambda o: o if isinstance(o, Member) else None),
                   HCXAISiteDirector=N(Active=lambda: director), HCConvoyRules=rules(), HCXConvoyRoute=flat_port(),
                   HCServer=N(HCTickWork=lambda: self.budget), HCUnitBudget=N(HC_WORK_SITUATIONS=SITUATIONS),
                   eAIWaypointBehavior=N(HALT=3), eAIGroupFormationState=N(IN=1), CarGear=N(FIRST=2))
        self.run = N(mHCId=EStr(''), mHCPhase=EStr('seek'), mHCReason=EStr(''), mHCNote=EStr(''),
                     mHCGroup=None, mHCLeader=None, mHCCar=None, mHCPolicy=None, mHCWalk=Arr(),
                     mHCRoute=self.route, mHCControl=N(Steering=0.0, Throttle=0.0, Brake=0.0),
                     mHCBehaviour=0, mHCIndex=0, mHCPhaseAt=0, mHCScanAt=0, mHCScans=0, mHCProgressAt=0,
                     mHCProgressPos=[0.0, 0.0, 0.0], mHCDoor=[0.0, 0.0, 0.0], mHCDrove=False, mHCReleased=False,
                     mHCForeign=False, mHCExitTries=0)
        bind(RUNTIME, 'HCXConvoyRun', env, self.run, skip=('HCDoor',))
        # CrewEntryWS has native out parameters; the door port is synthetic.
        self.run.HCDoor = lambda car: [car.pos[0] - 1.0, 0.0, car.pos[2]]

    def query(self, pos, radius, found, proxies):
        found.extend(c for c in self.cars if flat(pos, c.pos) <= radius)

    def open(self):
        return self.run.HCOpen(EStr('situation-1'), self.group, self.policy, self.clock[0])

    def step(self, at):
        self.clock[0] = at
        self.run.HCStep(at)

    def seat(self, car):
        for seat, member in enumerate(self.group.members):
            member.parent = car
            car.crew[seat] = member


class ConvoyPolicyAndRules(unittest.TestCase):
    def test_policy_defaults_validate_and_unbounded_overrides_are_refused(self):
        rows = {r['key']: r for r in json.loads((ROOT / 'tools/validate/shared_settings.json').read_text())
                if r['key'].startswith('Convoys.')}
        checked = []

        def registry_valid(key, value):
            checked.append(key)
            row = rows.get(key)
            return row is not None and row['min'] <= value <= row['max']

        env = dict(HCOperatorSettingsRegistry=N(HCValid=registry_valid))
        translate(POLICY.read_text(), 'HCConvoyPolicy', env, only=('HCValid', 'HCNumbers', 'HCRegistryValid'))
        policy = defaults()
        self.assertEqual({'Convoys.' + key for key in vars(policy)}, set(rows))
        self.assertTrue(env['HCValid'](policy))
        self.assertEqual(set(rows), set(checked), 'every policy field is bound to its registry row')
        for key, row in rows.items():
            self.assertEqual(row['default'], getattr(policy, key.split('.', 1)[1]), key)
        self.assertIn(('ExitAttempts', 3), vars(policy).items())
        for field, value in [('Version', 2), ('MaxConvoys', 2), ('MaxConvoys', 0), ('SeekObjects', 0),
                             ('MaxRouteNodes', 1), ('MaxPlanNodes', 100001), ('RoadNodesPerTick', 0),
                             ('RoadNodesPerWorkUnit', 0), ('SeekMeters', float('nan')), ('CruiseKmh', 61.0),
                             ('Throttle', 1.5), ('MaxDriveMeters', 50.0), ('StallSeconds', 0.0),
                             ('PlayerClaimMeters', 10.0), ('MaxDriveSeconds', 0.0)]:
            bad = N(**vars(policy)); setattr(bad, field, value)
            self.assertFalse(env['HCValid'](bad), field)

    def test_world_vehicle_must_be_intact_unclaimed_empty_and_seat_the_party(self):
        policy, rule = defaults(), rules()
        good = dict(destroyed=False, operational=True, wheels=4, present=4, crewed=False, flipped=False,
                    seats=4, members=3, cargo=0, nearest=500.0)

        def problem(**changes):
            row = dict(good); row.update(changes)
            return rule.HCVehicleProblem(policy, *row.values())

        self.assertEqual('', problem())
        for changes, reason in [(dict(destroyed=True), 'CONVOY_VEHICLE_DESTROYED'),
                                (dict(crewed=True), 'CONVOY_VEHICLE_CREWED'),
                                (dict(nearest=policy.PlayerClaimMeters - 1), 'CONVOY_VEHICLE_PLAYER_NEAR'),
                                (dict(cargo=1), 'CONVOY_VEHICLE_HAS_CARGO'),
                                (dict(operational=False), 'CONVOY_VEHICLE_NOT_OPERATIONAL'),
                                (dict(present=3), 'CONVOY_VEHICLE_WHEELS_MISSING'),
                                (dict(wheels=0, present=0), 'CONVOY_VEHICLE_WHEELS_MISSING'),
                                (dict(flipped=True), 'CONVOY_VEHICLE_FLIPPED'),
                                (dict(seats=2), 'CONVOY_VEHICLE_SEATS')]:
            self.assertEqual(reason, problem(**changes), changes)

    def test_control_is_bounded_slows_for_turns_and_arrival_and_brakes_when_stopping(self):
        policy, rule = defaults(), rules()
        c = N(Steering=9.0, Throttle=9.0, Brake=9.0)
        rule.HCControl(policy, 0.3, 30.0, 500.0, True, c)
        self.assertEqual((0, 0, 1), (c.Steering, c.Throttle, c.Brake))
        rule.HCControl(policy, 0.0, 0.0, 500.0, False, c)
        self.assertEqual((0, policy.Throttle, 0), (c.Steering, c.Throttle, c.Brake))
        rule.HCControl(policy, math.pi, policy.TurnKmh + 1, 500.0, False, c)
        self.assertEqual((1, 0, 0), (c.Steering, c.Throttle, c.Brake))
        rule.HCControl(policy, -math.pi, policy.TurnKmh + policy.SpeedBandKmh + 1, 500.0, False, c)
        self.assertEqual((-1, 0, policy.BrakeStrength), (c.Steering, c.Throttle, c.Brake))
        rule.HCControl(policy, 0.0, policy.CruiseKmh - 1, policy.ArriveMeters, False, c)
        self.assertEqual(policy.BrakeStrength, c.Brake)
        for angle in (-10.0, -0.1, 0.1, 10.0):
            rule.HCControl(policy, angle, 5.0, 500.0, False, c)
            self.assertTrue(-1 <= c.Steering <= 1 and 0 <= c.Throttle <= 1 and 0 <= c.Brake <= 1)

    def test_stall_needs_both_no_progress_and_the_named_window(self):
        policy, rule = defaults(), rules()
        window = int(policy.StallSeconds * 1000)
        self.assertTrue(rule.HCStalled(policy, policy.StallMeters - 1, window))
        self.assertFalse(rule.HCStalled(policy, policy.StallMeters - 1, window - 1))
        self.assertFalse(rule.HCStalled(policy, policy.StallMeters, window * 10))


def chain(count=11, spacing=50.0, isolated=None):
    nodes = Arr()
    for index in range(count):
        links = [i for i in (index - 1, index + 1) if 0 <= i < count]
        nodes.Insert(N(Position=[index * spacing, 0.0, 0.0], Links=Arr(links), Parent=-2))
    if isolated:
        nodes.Insert(N(Position=isolated, Links=Arr(), Parent=-2))
    return N(Nodes=nodes, Phase=EStr('idle'))


class ConvoyRoutePlanning(unittest.TestCase):
    def route(self, roads, budget=None, **policy_changes):
        policy = defaults()
        for key, value in policy_changes.items():
            setattr(policy, key, value)
        self.budget = budget or Budget()
        env = dict(Math=MATH, HCXAICaravanRoads=N(HCGet=lambda: roads),
                   HCServer=N(HCTickWork=lambda: self.budget), HCUnitBudget=N(HC_WORK_SITUATIONS=SITUATIONS))
        route = N(mHCParent=Arr(), mHCFrontier=Arr(), mHCPath=Arr(), mHCPhase=EStr('idle'), mHCReason=EStr(''))
        bind(ROUTE, 'HCXConvoyRoute', env, route)
        return route, policy

    def plan(self, roads, origin, destination, ticks=400, **changes):
        route, policy = self.route(roads, **changes)
        self.assertTrue(route.HCPlan(origin, destination, policy))
        for _ in range(ticks):
            route.HCStep()
            if route.mHCPhase in ('ready', 'failed'):
                break
        return route

    def test_plans_car_to_destination_on_own_parents_and_stops_short_of_target(self):
        roads = chain()
        route = self.plan(roads, [-20.0, 0.0, 5.0], [520.0, 0.0, 0.0])
        self.assertEqual(('ready', ''), (route.mHCPhase, route.mHCReason))
        self.assertEqual([[x * 50.0, 0.0, 0.0] for x in range(9)], list(route.mHCPath))
        self.assertTrue(all(node.Parent == -2 for node in roads.Nodes), 'caravan parents untouched')
        self.assertTrue(self.budget.calls and all(c == SITUATIONS for c, _ in self.budget.calls))

    def test_every_refusal_has_a_named_reason(self):
        for origin, destination, changes, reason in [
                ([0.0, 0.0, -500.0], [520.0, 0.0, 0.0], {}, 'CONVOY_ROAD_APPROACH_TOO_FAR'),
                ([0.0, 0.0, 5.0], [0.0, 0.0, 330.0], {}, 'CONVOY_ROAD_DISCONNECTED'),
                ([-20.0, 0.0, 5.0], [520.0, 0.0, 0.0], dict(MaxPlanNodes=3), 'CONVOY_ROAD_SEARCH_CAP'),
                ([-20.0, 0.0, 5.0], [520.0, 0.0, 0.0], dict(MaxRouteNodes=3), 'CONVOY_ROUTE_NODE_CAP'),
                ([-20.0, 0.0, 5.0], [520.0, 0.0, 0.0], dict(MaxDriveMeters=200.0), 'CONVOY_ROUTE_LENGTH_CAP'),
                ([0.0, 0.0, 5.0], [120.0, 0.0, 0.0], {}, 'CONVOY_ROUTE_TOO_SHORT')]:
            route = self.plan(chain(isolated=[0.0, 0.0, 330.0]), origin, destination, **changes)
            self.assertEqual(('failed', reason), (route.mHCPhase, route.mHCReason), reason)

    def test_work_is_bounded_per_tick_and_refused_budget_makes_no_progress(self):
        route, policy = self.route(chain(), budget=Budget(units=0), RoadNodesPerTick=4)
        route.HCPlan([0.0, 0.0, 0.0], [500.0, 0.0, 0.0], policy)
        route.HCStep()
        self.assertEqual(('scan', 0), (route.mHCPhase, len(route.mHCParent)))
        self.budget.units = 10 ** 6
        route.HCStep()
        self.assertEqual(4, len(route.mHCParent))

    def test_closed_or_reloaded_network_fails_closed(self):
        roads = chain()
        route, policy = self.route(roads)
        route.HCPlan([0.0, 0.0, 0.0], [500.0, 0.0, 0.0], policy)
        roads.Nodes.Insert(N(Position=[0.0, 0.0, 0.0], Links=Arr(), Parent=-2))
        route.HCStep()
        self.assertEqual(('failed', 'CONVOY_ROAD_NETWORK_CHANGED'), (route.mHCPhase, route.mHCReason))


class ConvoyRun(unittest.TestCase):
    def test_seek_picks_nearest_qualified_world_car_and_walks_to_its_door(self):
        cargo, destroyed, good, far = Car(10.0), Car(20.0), Car(30.0), Car(100.0)
        cargo.cargo = 1
        destroyed.destroyed = True
        world = RunWorld(cars=[cargo, destroyed, good, far])
        self.assertTrue(world.open())
        world.step(0)
        self.assertEqual('approach', world.run.mHCPhase)
        self.assertIs(good, world.run.mHCCar)
        self.assertEqual([([30.0, 0.0, 0.0], [600.0, 0.0, 0.0])], world.route.plans)
        self.assertEqual([[29.0, 0.0, 0.0]], list(world.group.points))
        self.assertEqual(3, world.group.behaviour)
        self.assertTrue(any('CONVOY_VEHICLE_HAS_CARGO' in line for line in world.printed))
        self.assertEqual([], good.calls, 'nothing is moved, started or created while seeking')

    def test_claimed_or_missing_vehicle_keeps_the_walking_caravan_after_bounded_scans(self):
        world = RunWorld(cars=[Car(30.0)], players=[[30.0, 0.0, 100.0]])
        world.open()
        policy = world.policy
        world.step(0)
        world.step(1000)
        self.assertEqual(1, world.run.mHCScans, 'no rescan before SeekSeconds')
        at = 0
        for _ in range(policy.MaxSeekScans + 1):
            at += int(policy.SeekSeconds * 1000)
            world.step(at)
        self.assertEqual(('walk', 'CONVOY_NO_QUALIFIED_WORLD_VEHICLE'), (world.run.mHCPhase, world.run.mHCReason))
        self.assertEqual([[0.0, 0.0, 0.0], [600.0, 0.0, 0.0]], list(world.group.points))
        self.assertEqual(7, world.group.behaviour)
        self.assertTrue(any('CONVOY_VEHICLE_PLAYER_NEAR' in line for line in world.printed))
        self.assertLessEqual(world.run.mHCScans, policy.MaxSeekScans)

    def drive(self, world, car):
        world.open()
        world.step(0)
        leader = world.group.members[0]
        leader.pos = [car.pos[0] - 1.0, 0.0, 0.0]
        world.step(1000)
        self.assertEqual('board', world.run.mHCPhase)
        self.assertEqual([(car, 0)], leader.boarded)
        world.seat(car)
        world.step(2000)
        self.assertEqual('drive', world.run.mHCPhase)
        return leader

    def test_full_journey_drives_stops_dismounts_and_walks_only_the_remainder(self):
        car = Car(30.0)
        world = RunWorld(cars=[car])
        leader = self.drive(world, car)
        world.run.HCInput()
        self.assertIn('start', car.calls)
        self.assertIn(('gear', 2), car.calls)
        self.assertIn(('throttle', world.policy.Throttle), car.calls)
        self.assertIn(('handbrake', 0), car.calls)
        car.calls.clear(); car.pos = [480.0, 0.0, 5.0]; car.speed = 20.0
        world.run.mHCIndex = 2
        world.step(3000)
        self.assertEqual(('stop', 'CONVOY_ARRIVED'), (world.run.mHCPhase, world.run.mHCReason))
        world.run.HCInput()
        self.assertEqual([('steer', 0), ('throttle', 0), ('brake', 1)], car.calls[-3:])
        car.speed = 0.0
        world.run.HCInput()
        self.assertEqual(('handbrake', 1), car.calls[-1])
        world.step(4000)
        self.assertEqual('exit', world.run.mHCPhase)
        self.assertIn('stop', car.calls)
        self.assertEqual(['out'], leader.exits)
        self.assertEqual(['out'], world.group.members[1].exits, 'every seated member is asked to leave')
        world.step(5000)
        self.assertEqual('exit', world.run.mHCPhase, 'waits while still seated')
        for member in world.group.members:
            member.parent = None
        world.step(6000)
        self.assertEqual(('walk', 'CONVOY_ARRIVED'), (world.run.mHCPhase, world.run.mHCReason))
        self.assertEqual([[600.0, 0.0, 0.0]], list(world.group.points))
        self.assertEqual(7, world.group.behaviour)

    def test_contact_stall_foreign_crew_and_timeout_stop_then_dismount(self):
        for name, mutate, reason, at in [
                ('contact', lambda w, c: setattr(w.group, 'combat', True), 'CONVOY_CONTACT', 3000),
                ('stall', lambda w, c: None, 'CONVOY_STALLED', 2000 + 15000),
                ('player', lambda w, c: c.crew.__setitem__(3, Member(0.0)), 'CONVOY_FOREIGN_CREW', 3000),
                ('flip', lambda w, c: setattr(c, 'flipped', True), 'CONVOY_VEHICLE_FLIPPED', 3000),
                ('driver', lambda w, c: c.crew.__setitem__(0, None), 'CONVOY_DRIVER_LOST', 3000)]:
            car = Car(30.0)
            world = RunWorld(cars=[car])
            leader = self.drive(world, car)
            mutate(world, car)
            world.step(at)
            self.assertEqual(('stop', reason), (world.run.mHCPhase, world.run.mHCReason), name)
            world.step(at + int(world.policy.StopSeconds * 1000) + 1)
            self.assertEqual('exit', world.run.mHCPhase, name)
            self.assertEqual(['out'], leader.exits, name)

    def test_board_timeout_dismounts_and_restores_the_whole_walking_route(self):
        car = Car(30.0)
        world = RunWorld(cars=[car])
        world.open()
        world.step(0)
        leader = world.group.members[0]
        leader.pos = [29.0, 0.0, 0.0]
        world.step(1000)
        leader.parent = car; car.crew[0] = leader
        world.step(1000 + int(world.policy.BoardSeconds * 1000) + 1)
        self.assertEqual(('stop', 'CONVOY_BOARD_TIMEOUT'), (world.run.mHCPhase, world.run.mHCReason))
        world.step(100000)
        leader.parent = None
        world.step(100001)
        self.assertEqual('walk', world.run.mHCPhase)
        self.assertEqual([[0.0, 0.0, 0.0], [600.0, 0.0, 0.0]], list(world.group.points))

    def test_boarding_waits_for_door_route_and_formation(self):
        car = Car(30.0)
        world = RunWorld(cars=[car], ready=False)
        world.open()
        world.step(0)
        leader = world.group.members[0]
        world.step(500)
        self.assertEqual([], leader.boarded, 'far from the door')
        leader.pos = [29.0, 0.0, 0.0]
        world.step(1000)
        self.assertEqual([], leader.boarded, 'route not ready')
        world.route.ready = True
        world.group.formation = 0
        world.step(1500)
        self.assertEqual(('walk', 'CONVOY_FORMATION_NOT_IN'), (world.run.mHCPhase, world.run.mHCReason))
        self.assertEqual([], leader.boarded)

    def test_release_while_driving_dismounts_without_rewriting_waypoints(self):
        car = Car(30.0)
        world = RunWorld(cars=[car])
        leader = self.drive(world, car)
        world.group.calls.clear()
        world.run.HCRelease(2500)
        self.assertEqual('exit', world.run.mHCPhase)
        self.assertEqual(['out'], leader.exits)
        for member in world.group.members:
            member.parent = None
        world.step(3000)
        self.assertEqual('done', world.run.mHCPhase)
        self.assertEqual([], world.group.calls)

    def assert_released_to_player(self, world, car, player):
        self.assertEqual([], car.calls, 'no brake, handbrake or engine write once a player drives')
        self.assertEqual('CONVOY_FOREIGN_DRIVER', world.run.mHCReason)
        self.assertEqual(1, sum('CONVOY_FOREIGN_DRIVER' in line for line in world.printed))
        self.assertTrue(car.engine, 'the player keeps the running engine')

    def test_player_taking_the_driver_seat_while_boarding_gets_the_car_at_once(self):
        for detect in ('input', 'step'):
            car = Car(30.0)
            world = RunWorld(cars=[car])
            world.open()
            world.step(0)
            leader = world.group.members[0]
            leader.pos = [29.0, 0.0, 0.0]
            world.step(1000)
            self.assertEqual('board', world.run.mHCPhase, detect)
            player = Member(29.0)
            car.crew[0] = player; car.engine = True; car.calls.clear()
            if detect == 'input':
                world.run.HCInput()
            else:
                world.step(1500)
            world.run.HCInput()
            world.run.HCInput()
            self.assert_released_to_player(world, car, player)
            world.step(2000)
            self.assertEqual(('walk', 'CONVOY_FOREIGN_DRIVER'), (world.run.mHCPhase, world.run.mHCReason), detect)
            self.assertEqual([[0.0, 0.0, 0.0], [600.0, 0.0, 0.0]], list(world.group.points), detect)
            world.run.HCRelease(2500)
            self.assert_released_to_player(world, car, player)

    def test_player_taking_the_driver_seat_while_driving_gets_the_car_and_the_crew_leaves(self):
        for detect in ('input', 'step'):
            car = Car(30.0)
            world = RunWorld(cars=[car])
            leader = self.drive(world, car)
            world.run.HCInput()
            follower = world.group.members[1]
            player = Member(30.0)
            leader.parent = None; car.crew[0] = player; car.calls.clear()
            if detect == 'input':
                world.run.HCInput()
            else:
                world.step(3000)
            world.run.HCInput()
            self.assert_released_to_player(world, car, player)
            self.assertEqual('exit', world.run.mHCPhase, detect)
            self.assertEqual(['out'], follower.exits, detect)
            self.assertEqual([], leader.exits, detect)
            world.step(4000)
            self.assertEqual('exit', world.run.mHCPhase, 'held while our follower is still seated')
            follower.parent = None
            world.step(5000)
            self.assertEqual(('walk', 'CONVOY_FOREIGN_DRIVER'), (world.run.mHCPhase, world.run.mHCReason), detect)
            self.assertEqual([[600.0, 0.0, 0.0]], list(world.group.points), detect)
            self.assert_released_to_player(world, car, player)

    def test_dismount_holds_for_every_member_then_gives_up_after_the_bounded_window(self):
        car = Car(30.0)
        world = RunWorld(cars=[car])
        leader = self.drive(world, car)
        follower = world.group.members[1]
        world.group.combat = True
        world.step(3000)
        world.step(3001)
        self.assertEqual('exit', world.run.mHCPhase)
        self.assertEqual((['out'], ['out']), (leader.exits, follower.exits))
        leader.parent = None; car.crew[0] = None
        window = int(world.policy.ExitSeconds * 1000)
        world.step(3001 + window - 1)
        self.assertEqual('exit', world.run.mHCPhase, 'a seated follower holds the run')
        at = 3001
        for attempt in range(1, world.policy.ExitAttempts):
            at += window + 1
            world.step(at)
            self.assertEqual('exit', world.run.mHCPhase, attempt)
            self.assertEqual(['out'] * (attempt + 1), follower.exits, attempt)
        self.assertEqual(['out'], leader.exits, 'only still-seated members are asked again')
        at += window + 1
        world.step(at)
        self.assertEqual(('walk', 'CONVOY_DISMOUNT_TIMEOUT'), (world.run.mHCPhase, world.run.mHCReason))
        self.assertTrue(any('CONVOY_DISMOUNT_TIMEOUT' in line for line in world.printed))

    def test_input_only_drives_in_drive_and_holds_brake_otherwise(self):
        car = Car(30.0)
        world = RunWorld(cars=[car])
        world.open()
        world.run.HCInput()
        world.step(0)
        world.run.HCInput()
        self.assertEqual([], car.calls, 'seek/approach never touch the car')


class Status:
    def __init__(self): self.published = []
    def HCPublish(self, state, reason): self.published.append((state, reason))


class ConvoyService(unittest.TestCase):
    def service(self, disabled=False, roads=None):
        self.printed = []
        self.admissions = []
        self.created = []

        def make_run():
            run = N(mHCPhase=EStr('seek'), mHCId=EStr(''), mHCReason=EStr(''), steps=[], inputs=[], mHCCar=None)
            run.HCOpen = lambda id, group, policy, now: (setattr(run, 'mHCId', id), True)[1]
            run.HCStep = lambda now: run.steps.append(now)
            run.HCInput = lambda: run.inputs.append(1)
            run.HCRelease = lambda now: setattr(run, 'mHCPhase', EStr('done'))
            self.created.append(run)
            return run

        def line(feature, preference, gate, qualified):
            self.admissions.append((feature, preference, gate, qualified))
            return EStr('admission')

        self.roads = roads
        game = N(GetTime=lambda: 0)
        env = dict(FileExist=lambda path: disabled and path.endswith('acceptance/convoys.disable'),
                   Print=self.printed.append, HCV2Admission=N(Line=line), GetGame=lambda: game,
                   HCConvoyPolicy=N(HCGet=defaults), HCXConvoyRun=make_run,
                   HCXAICaravanRoads=N(HCGet=lambda: self.roads))
        service = N(mHCRun=None, mHCStatus=Status(), mHCPolicy=None, mHCDisabled=False,
                    mHCRefused=EStr(''), mHCLogged=EStr(''))
        bind(RUNTIME, 'HCXConvoyService', env, service)
        service.HCAdmit()
        return service

    def test_operator_opt_out_is_off_logged_once_and_never_offers(self):
        service = self.service(disabled=True, roads=chain())
        self.assertEqual([('Convoys', False, 'convoys', False)], self.admissions)
        self.assertEqual(('off', 'operator_disabled'), service.mHCStatus.published[-1])
        self.assertFalse(service.HCOffer(EStr('s'), EStr('raid'), Group()))
        service.HCStep()
        self.assertEqual([], self.created)

    def test_admitted_unverified_and_status_follows_road_network(self):
        service = self.service(roads=None)
        self.assertEqual([('Convoys', True, 'convoys', False)], self.admissions)
        self.assertTrue(any('admission' in line and 'runtime=PENDING' in line for line in self.printed))
        self.assertEqual(('degraded', 'CONVOY_ROAD_NETWORK_NOT_OPENED'), service.mHCStatus.published[-1])
        self.assertFalse(service.HCOffer(EStr('s'), EStr('raid'), Group()))
        self.assertFalse(service.HCOffer(EStr('s'), EStr('raid'), Group()))
        self.assertEqual(1, sum('CONVOY_ROAD_NETWORK_NOT_OPENED road_branch' in line for line in self.printed))
        self.roads = N(Nodes=Arr(), Phase=EStr('loading'))
        service.HCStep()
        self.assertEqual(('requested', 'CONVOY_ROAD_NETWORK_LOADING'), service.mHCStatus.published[-1])
        self.roads = chain()
        service.HCStep()
        self.assertEqual('ready', service.mHCStatus.published[-1][0])

    def test_offers_only_raid_or_column_one_at_a_time_and_frees_the_slot_on_walk(self):
        service = self.service(roads=chain())
        self.assertFalse(service.HCOffer(EStr('a'), EStr('survivor'), Group()))
        self.assertTrue(service.HCOffer(EStr('b'), EStr('raid'), Group()))
        self.assertFalse(service.HCOffer(EStr('c'), EStr('column'), Group()))
        self.assertTrue(any('CONVOY_CAP' in line for line in self.printed))
        run = self.created[0]
        service.HCStep()
        self.assertEqual([0], run.steps)
        car, other = Car(1.0), Car(2.0)
        run.mHCCar = car
        service.HCInput(other)
        service.HCInput(car)
        self.assertEqual([1], run.inputs)
        service.HCRelease(EStr('other'))
        self.assertIs(run, service.mHCRun)
        run.mHCPhase = EStr('walk')
        service.HCStep()
        self.assertIsNone(service.mHCRun)
        self.assertTrue(service.HCOffer(EStr('d'), EStr('column'), Group()))


class ConvoySourceGuards(unittest.TestCase):
    def test_convoy_sources_never_move_create_or_delete_world_objects(self):
        for path in (POLICY, ROUTE, RUNTIME):
            text = re.sub(r'//[^\n]*', '', path.read_text())
            for banned in ('SetPosition', 'SetOrientation', 'SetDirection', 'CreateObject', 'Delete(',
                           'SpawnEntity', 'FixEntity', 'Fill(', 'SetHealth'):
                self.assertNotIn(banned, text, (path.name, banned))

    def test_car_input_hook_runs_after_the_native_and_expansion_input(self):
        text = RUNTIME.read_text()
        hook = text[text.index('modded class CarScript'):]
        self.assertLess(hook.index('super.OnInput(dt);'), hook.index('HCXConvoyRuntime.HCInput(this);'))
        self.assertIn('acceptance/convoys.disable', text)

    def test_policy_has_no_pending_registry_print_and_ships_in_the_friend_bundle(self):
        self.assertNotIn('CONVOY_SETTINGS_REGISTRY_PENDING', POLICY.read_text())
        self.assertIn('HollowCountry/convoys.json', friend_bundle.PROFILE_INCLUDE)

    def test_situations_offer_on_begin_release_before_restore_and_drop_the_missing_port_line(self):
        text = (AI / 'HCW38SituationRuntime.c').read_text()
        self.assertNotIn('SITUATION_VEHICLE_DRIVING_PORT_MISSING', text)
        begin = text[text.index('static bool HCBegin('):text.index('static string HCObserve(')]
        self.assertLess(begin.index('s_Active = binding;'), begin.index('HCXConvoyRuntime.HCOffer(binding);'))
        end = text[text.index('static void HCEnd('):]
        self.assertLess(end.index('HCXConvoyRuntime.HCRelease(s_Active.Id);'), end.index('HCRestore(s_Active);'))
