"""Behavioral execution of the authored, unhooked ecology policy bodies.

The translator supplies only Enforce syntax/container scaffolding.  Authority,
freshness, eligibility, budgets, scheduling, and commit decisions remain in the
authored HCEcologyRules methods; no perception or navigation result is faked.
"""
import ast
from pathlib import Path
import re
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts"


class EArray(list):
    def __bool__(self):
        return True

    def Insert(self, item):
        self.append(item)

    def Count(self):
        return len(self)

    def Get(self, index):
        if index < 0 or index >= len(self):
            raise IndexError("native array index")
        return self[index]

    def Find(self, item):
        return self.index(item) if item in self else -1

    def Clear(self):
        self.clear()


def block(source, start):
    depth = 1
    end = start
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end - 1]


def native_int(value):
    return (value + 2**31) % 2**32 - 2**31


def native_remainder(left, right):
    return left % right if left >= 0 else -((-left) % right)


class NativeIntArithmetic(ast.NodeTransformer):
    def visit_BinOp(self, node):
        node = self.generic_visit(node)
        if isinstance(node.op, ast.Mod):
            call = ast.Call(ast.Name("native_remainder", ast.Load()),
                            [node.left, node.right], [])
        elif isinstance(node.op, (ast.Add, ast.Sub)):
            call = ast.Call(ast.Name("native_int", ast.Load()), [node], [])
        else:
            return node
        return ast.copy_location(call, node)


def translated_rules():
    data = (ROOT / "3_Game/Ecology/HCEcologyData.c").read_text()
    source = (ROOT / "4_World/Ecology/HCEcologyRules.c").read_text()
    env = {"EArray": EArray, "len": len, "native_int": native_int,
           "native_remainder": native_remainder}

    for match in re.finditer(r"class (\w+)\s*\{", data):
        name = match[1]
        fields = block(data, match.end())
        constants = re.findall(r"static const int (\w+)\s*=\s*(-?\d+);", fields)
        declarations = re.findall(
            r"^\s*(?:ref )?([\w<> ]+?)\s+(\w+)(?:\s*=\s*([^;]+))?;",
            fields,
            re.M,
        )

        def make(declarations=declarations):
            value = SimpleNamespace()
            for typ, field, default in declarations:
                typ = typ.strip()
                if typ.startswith("array<"):
                    result = EArray()
                elif default is None or not default.strip():
                    result = {"bool": False, "int": 0, "string": ""}.get(typ)
                elif default.strip() in ("true", "false"):
                    result = default.strip() == "true"
                elif re.fullmatch(r"-?\d+", default.strip()):
                    result = int(default)
                else:
                    result = ""
                setattr(value, field, result)
            return value

        for constant, number in constants:
            setattr(make, constant, int(number))
        env[name] = make

    source = re.sub(r"//[^\n]*", "", source)
    for match in re.finditer(r"static [\w<>]+\s+(\w+)\(([^)]*)\)\s*\{", source):
        name = match[1]
        parameters = [
            item.strip().split()[-1]
            for item in match[2].split(",")
            if item.strip()
        ]
        lines = [f'def {name}({", ".join(parameters)}):']
        indent = 1
        for token in re.split(r"([{};])", block(source, match.end())):
            token = token.strip()
            if not token or token == ";":
                continue
            if token == "{":
                indent += 1
                continue
            if token == "}":
                indent -= 1
                continue
            token = re.sub(r"new array<[^>]+>\(\)", "EArray()", token)
            token = re.sub(r"new (HCEcology\w+)\(\)", r"\1()", token)
            token = token.replace("HCEcologyRules.", "")
            token = token.replace("&&", " and ").replace("||", " or ")
            token = re.sub(r"!(?!=)", "not ", token)
            token = re.sub(r"\btrue\b", "True", token)
            token = re.sub(r"\bfalse\b", "False", token)
            token = re.sub(r"\bnull\b", "None", token)
            bare = re.fullmatch(
                r"(?:ref )?(?:array<[^>]+>|bool|int|string|HCEcology\w+)\s+(\w+)",
                token,
            )
            if bare:
                token = bare[1] + " = None"
            token = re.sub(
                r"\b(?:ref )?(?:array<[^>]+>|bool|int|string|HCEcology\w+)\s+(?=\w+\s*=)",
                "",
                token,
            )
            if token.startswith("if ("):
                token = "if " + token[4:-1] + ":"
            elif token.startswith("else if ("):
                token = "elif " + token[9:-1] + ":"
            elif token == "else":
                token = "else:"
            elif token.startswith("while ("):
                token = "while " + token[7:-1] + ":"
            token = re.sub(r"([\w.]+)\+\+$", r"\1 += 1", token)
            token = re.sub(r"(\b[\w.]+)\.Length\(\)", r"len(\1)", token)
            lines.append("    " * indent + token)
        tree = ast.parse("\n".join(lines))
        tree = ast.fix_missing_locations(NativeIntArithmetic().visit(tree))
        exec(compile(tree, "authored-ecology:" + name, "exec"), env)
    return env


class EcologyRulesTests(unittest.TestCase):
    def setUp(self):
        self.e = translated_rules()
        self.policy = self.e["HCEcologyPolicy"]()
        self.policy.SchemaVersion = 1
        self.policy.Enabled = True
        self.policy.WorldName = "chernarusplus"
        self.policy.SessionId = "session-a"
        self.policy.MaxObservationAgeMs = 100
        self.policy.MaxZones = 4
        self.policy.MaxActors = 4
        self.policy.MaxDirectives = 2
        self.policy.CooldownMs = 20
        self.policy.HysteresisMs = 10
        self.batch = self.e["HCEcologyObservationBatch"]()
        self.batch.WorldName = "chernarusplus"
        self.batch.SessionId = "session-a"
        self.batch.ObservedAtMs = 1000
        self.state = self.e["HCEcologyState"]()
        self.state.WorldName = "chernarusplus"
        self.state.SessionId = "session-a"
        self.cap = self.e["HCEcologyCapabilities"]()
        self.cap.IsServerAuthority = True
        self.cap.ProviderAvailable = True
        self.cap.SupportsAnimalNavigation = True
        self.cap.SupportsInfectedNavigation = True
        self.code = self.e["HCEcologyCode"]
        self.population = self.e["HCEcologyPopulation"]
        self.resource = self.e["HCEcologyResource"]

    def actor(self, identity, population=None, species="deer", observed=1000):
        value = self.e["HCEcologyActorObservation"]()
        value.Id = identity
        value.PopulationKind = population or self.population.ANIMAL
        value.Species = species
        value.ObservedAtMs = observed
        value.Alive = True
        value.NativeNavigationAvailable = True
        value.EligibleResources.Insert(self.resource.FOOD)
        value.EligibleResources.Insert(self.resource.WATER)
        return value

    def zone(self, identity, population=None, resource=None, species="deer", observed=1000):
        value = self.e["HCEcologyZoneObservation"]()
        value.Id = identity
        value.PopulationKind = population or self.population.ANIMAL
        value.ResourceKind = resource or self.resource.FOOD
        value.ObservedAtMs = observed
        value.ExpiresAtMs = 1200
        value.ReachabilityKnown = True
        value.NativeReachable = True
        value.EligibleSpecies.Insert(species)
        return value

    def schedule(self, now=1000):
        output = EArray()
        code = self.e["Schedule"](self.state, self.policy, self.batch, self.cap, now, output)
        return code, output

    def commit(self, directives, now=1000, accepted=None):
        if accepted is None:
            accepted = EArray([True] * len(directives))
        receipts = EArray([
            self.e["MakeReceipt"](
                directives[i] if i < len(directives) else None, flag)
            for i, flag in enumerate(accepted)])
        return self.e["Commit"](
            self.state, self.policy, directives, receipts, now, self.cap)

    def test_server_authority_and_native_provider_capability_are_required(self):
        self.batch.Actors.Insert(self.actor("a"))
        self.batch.Zones.Insert(self.zone("z"))
        for field in ("IsServerAuthority", "ProviderAvailable", "SupportsAnimalNavigation"):
            setattr(self.cap, field, False)
            code, directives = self.schedule()
            self.assertEqual(self.code.OK, code)
            self.assertEqual([], directives)
            setattr(self.cap, field, True)

    def test_infected_require_their_native_navigation_capability(self):
        actor = self.actor("infected-a", population=self.population.INFECTED, species="infected")
        self.batch.Actors.Insert(actor)
        self.batch.Zones.Insert(self.zone(
            "infected-water",
            population=self.population.INFECTED,
            resource=self.resource.WATER,
            species="infected",
        ))
        self.cap.SupportsInfectedNavigation = False
        self.assertEqual([], self.schedule()[1])
        self.cap.SupportsInfectedNavigation = True
        self.assertEqual(["infected-water"], [item.ZoneId for item in self.schedule()[1]])

    def test_stale_unknown_depleted_expired_and_unreachable_observations_are_excluded(self):
        self.policy.MaxZones = 5
        self.batch.Actors.Insert(self.actor("a"))
        cases = [
            ("stale", {"ObservedAtMs": 899}),
            ("unknown", {"ReachabilityKnown": False}),
            ("depleted", {"Depleted": True}),
            ("expired", {"ExpiresAtMs": 1000}),
            ("unreachable", {"NativeReachable": False}),
        ]
        for identity, fields in cases:
            zone = self.zone(identity)
            for field, value in fields.items():
                setattr(zone, field, value)
            self.batch.Zones.Insert(zone)
        code, directives = self.schedule()
        self.assertEqual(self.code.OK, code)
        self.assertEqual([], directives)

    def test_invalid_identity_time_budget_and_duplicate_data_roll_back(self):
        self.batch.Actors.Insert(self.actor("a"))
        self.batch.Zones.Insert(self.zone("z"))
        before = (self.state.LastNowMs, self.state.NextActorIndex, len(self.state.Assignments))
        self.batch.Zones.Insert(self.zone("z"))
        code, directives = self.schedule()
        self.assertEqual(self.code.INVALID, code)
        self.assertEqual([], directives)
        self.assertEqual(before, (self.state.LastNowMs, self.state.NextActorIndex, len(self.state.Assignments)))
        self.batch.Zones.pop()
        self.policy.MaxDirectives = 5
        self.assertEqual(self.code.INVALID, self.schedule()[0])
        self.policy.MaxDirectives = 2
        self.assertEqual(self.code.INVALID, self.schedule(now=999)[0])

    def test_world_session_and_observation_clock_cannot_regress(self):
        self.batch.Actors.Insert(self.actor("a"))
        self.batch.Zones.Insert(self.zone("z"))
        directives = self.schedule()[1]
        self.assertEqual(self.code.OK, self.commit(directives))
        self.batch.ObservedAtMs = 999
        self.batch.Actors[0].ObservedAtMs = 1001
        self.batch.Zones[0].ObservedAtMs = 1001
        self.batch.Zones[0].ExpiresAtMs = 1201
        self.assertEqual(self.code.INVALID, self.schedule(now=1001)[0])
        self.batch.ObservedAtMs = 1001
        self.batch.SessionId = "other-session"
        self.assertEqual(self.code.INVALID, self.schedule(now=1001)[0])

    def test_species_resource_and_population_eligibility_are_enforced(self):
        actor = self.actor("a")
        actor.EligibleResources = EArray([self.resource.WATER])
        self.batch.Actors.Insert(actor)
        self.batch.Zones.Insert(self.zone("food"))
        self.batch.Zones.Insert(self.zone("wolf-water", resource=self.resource.WATER, species="wolf"))
        self.batch.Zones.Insert(self.zone("infected", population=self.population.INFECTED, resource=self.resource.WATER))
        self.assertEqual([], self.schedule()[1])
        self.batch.Zones.Insert(self.zone("water", resource=self.resource.WATER))
        self.assertEqual(["water"], [item.ZoneId for item in self.schedule()[1]])

    def test_hints_never_create_observations_and_only_annotate_matching_observed_zone(self):
        hint = self.e["HCEcologyRouteHint"]()
        hint.Id = "autumn-west"
        hint.ZoneId = "z"
        hint.PopulationKind = self.population.ANIMAL
        hint.ResourceKind = self.resource.FOOD
        hint.Species = "deer"
        hint.StartsAtMs = 900
        hint.EndsAtMs = 1100
        self.policy.RouteHints.Insert(hint)
        self.batch.Actors.Insert(self.actor("a"))
        self.assertEqual([], self.schedule()[1])
        self.batch.Zones.Insert(self.zone("other"))
        self.assertEqual("", self.schedule()[1][0].RouteHintId)
        self.batch.Zones = EArray([self.zone("z")])
        self.assertEqual("autumn-west", self.schedule()[1][0].RouteHintId)

    def test_directive_budget_no_duplication_and_exhaustion(self):
        for identity in ("a", "b", "c"):
            self.batch.Actors.Insert(self.actor(identity))
        for identity in ("x", "y", "z"):
            self.batch.Zones.Insert(self.zone(identity))
        code, directives = self.schedule()
        self.assertEqual(self.code.OK, code)
        self.assertEqual(2, len(directives))
        self.assertEqual(2, len({item.ActorId for item in directives}))
        self.assertEqual(2, len({item.ZoneId for item in directives}))
        self.assertEqual(self.code.OK, self.commit(directives))
        remaining = self.schedule(now=1001)[1]
        self.assertEqual([("c", "z")], [(item.ActorId, item.ZoneId) for item in remaining])
        self.assertEqual(self.code.OK, self.commit(remaining, now=1001))
        self.assertEqual([], self.schedule(now=1002)[1])

    def test_all_rejected_is_atomic_and_success_applies_cooldown_hysteresis(self):
        self.batch.Actors.Insert(self.actor("a"))
        self.batch.Actors.Insert(self.actor("b"))
        self.batch.Zones.Insert(self.zone("x"))
        self.batch.Zones.Insert(self.zone("y"))
        directives = self.schedule()[1]
        before = (self.state.LastNowMs, self.state.NextActorIndex, self.state.NextZoneIndex, len(self.state.Assignments))
        self.assertEqual(self.code.NATIVE_REJECTED, self.commit(directives, accepted=EArray([False, False])))
        self.assertEqual(before, (self.state.LastNowMs, self.state.NextActorIndex, self.state.NextZoneIndex, len(self.state.Assignments)))
        self.assertEqual(self.code.OK, self.commit(directives))
        self.assertEqual(2, len(self.state.Assignments))
        self.assertEqual(1010, self.state.Assignments[0].HoldUntilMs)
        self.assertEqual(1030, self.state.Assignments[0].CooldownUntilMs)

    def test_round_robin_fairness_across_actor_and_zone_budgets(self):
        self.policy.MaxDirectives = 1
        for identity in ("a", "b", "c"):
            self.batch.Actors.Insert(self.actor(identity))
        for identity in ("x", "y", "z"):
            self.batch.Zones.Insert(self.zone(identity))
        pairs = []
        for now in (1000, 1031, 1062):
            self.batch.ObservedAtMs = now
            for actor in self.batch.Actors:
                actor.ObservedAtMs = now
            for zone in self.batch.Zones:
                zone.ObservedAtMs = now
                zone.ExpiresAtMs = now + 100
            code, directives = self.schedule(now)
            self.assertEqual(self.code.OK, code)
            self.assertEqual(1, len(directives))
            pairs.append((directives[0].ActorId, directives[0].ZoneId))
            self.assertEqual(self.code.OK, self.commit(directives, now))
        self.assertEqual([("a", "x"), ("b", "y"), ("c", "z")], pairs)

    def test_source_has_no_engine_mutation_or_production_hook(self):
        source = (ROOT / "4_World/Ecology/HCEcologyRules.c").read_text()
        for forbidden in ("CreateObject", "Delete()", "SetPosition", "StartCommand_", "modded class", "HCModuleRegistry"):
            self.assertNotIn(forbidden, source)


    def test_operator_limits_have_hard_ceilings(self):
        for field, value in (("MaxActors", 33), ("MaxZones", 33),
                             ("MaxDirectives", 9)):
            with self.subTest(field=field):
                self.setUp()
                self.policy.MaxActors = self.policy.MaxZones = 32
                setattr(self.policy, field, value)
                self.assertFalse(self.e["PolicyValid"](self.policy))

    def test_nested_lists_and_identifiers_are_bounded(self):
        actor, zone = self.actor("a"), self.zone("z")
        actor.EligibleResources = EArray([self.resource.FOOD] * 3)
        self.assertFalse(self.e["ActorDataValid"](actor, 1000))
        actor.EligibleResources = EArray([self.resource.FOOD])
        zone.EligibleSpecies = EArray(["deer"] * 17)
        self.assertFalse(self.e["ZoneDataValid"](zone, 1000))
        zone.EligibleSpecies = EArray(["deer"])
        cases = (
            (self.policy, ("WorldName", "SessionId"),
             lambda: self.e["PolicyValid"](self.policy)),
            (actor, ("Id", "Species"),
             lambda: self.e["ActorDataValid"](actor, 1000)),
            (zone, ("Id",), lambda: self.e["ZoneDataValid"](zone, 1000)),
        )
        for obj, fields, check in cases:
            for field in fields:
                with self.subTest(field=field):
                    old = getattr(obj, field)
                    setattr(obj, field, "x" * 129)
                    self.assertFalse(check())
                    setattr(obj, field, old)
        zone.EligibleSpecies = EArray(["x" * 129])
        self.assertFalse(self.e["ZoneDataValid"](zone, 1000))

    def test_int32_cursor_normalized_before_addition(self):
        self.assertEqual(-2147483648, native_int(2147483647 + 1))
        self.assertEqual(-2, native_remainder(-2147483648, 3))
        self.state.NextActorIndex = self.state.NextZoneIndex = 2147483647
        for name in ("a", "b", "c"):
            self.batch.Actors.Insert(self.actor(name))
        for name in ("x", "y", "z"):
            self.batch.Zones.Insert(self.zone(name))
        code, directives = self.schedule()
        self.assertEqual(self.code.OK, code)
        self.assertEqual([("b", "y"), ("c", "z")],
                         [(d.ActorId, d.ZoneId) for d in directives])


    def test_null_future_entries_reject_without_mutation(self):
        names = ("Actors", "Zones", "Assignments", "RouteHints", "Directives")
        for collection in names:
            with self.subTest(collection=collection):
                self.setUp()
                self.batch.Actors.Insert(self.actor("a"))
                self.batch.Zones.Insert(self.zone("z"))
                directives = self.schedule()[1]
                if collection == "Directives":
                    directives.Insert(None)
                elif collection == "Assignments":
                    value = self.e["HCEcologyAssignment"]()
                    value.ActorId, value.ZoneId = "a", "z"
                    self.state.Assignments = EArray([value, None])
                elif collection == "RouteHints":
                    value = self.e["HCEcologyRouteHint"]()
                    value.Id, value.ZoneId, value.Species = "h", "z", "deer"
                    value.PopulationKind = self.population.ANIMAL
                    value.ResourceKind = self.resource.FOOD
                    value.StartsAtMs, value.EndsAtMs = 900, 1100
                    self.policy.RouteHints = EArray([value, None])
                else:
                    getattr(self.batch, collection).Insert(None)
                before = repr(self.state)
                if collection == "Directives":
                    code = self.commit(directives)
                else:
                    code = self.schedule()[0]
                self.assertEqual(self.code.INVALID, code)
                self.assertEqual(before, repr(self.state))

    def test_wrapped_deadlines_cannot_commit(self):
        self.batch.Actors.Insert(self.actor("a"))
        self.batch.Zones.Insert(self.zone("z"))
        directives = self.schedule()[1]
        directive = directives[0]
        directive.ObservationAtMs = directive.IssuedAtMs = 2147483647
        directive.HoldUntilMs = native_int(
            directive.IssuedAtMs + self.policy.HysteresisMs)
        directive.CooldownUntilMs = native_int(
            directive.HoldUntilMs + self.policy.CooldownMs)
        before = repr(self.state)
        code = self.commit(directives, now=directive.IssuedAtMs)
        self.assertEqual(self.code.INVALID, code)
        self.assertEqual(before, repr(self.state))

    def test_replayed_commit_does_not_mutate_state(self):
        self.batch.Actors.Insert(self.actor("a"))
        self.batch.Zones.Insert(self.zone("z"))
        directives = self.schedule()[1]
        self.assertEqual(self.code.OK, self.commit(directives))
        before = repr(self.state)
        self.assertEqual(self.code.INVALID, self.commit(directives))
        self.assertEqual(before, repr(self.state))

    def test_commit_requires_current_authority_and_capability(self):
        fields = ("IsServerAuthority", "ProviderAvailable",
                  "SupportsAnimalNavigation")
        for field in fields:
            with self.subTest(field=field):
                self.setUp()
                self.batch.Actors.Insert(self.actor("a"))
                self.batch.Zones.Insert(self.zone("z"))
                directives = self.schedule()[1]
                setattr(self.cap, field, False)
                before = repr(self.state)
                self.assertEqual(self.code.INVALID, self.commit(directives))
                self.assertEqual(before, repr(self.state))


    def test_partial_receipt_retains_confirmed_assignment_and_cursor(self):
        for name in ("a", "b"):
            self.batch.Actors.Insert(self.actor(name))
        for name in ("x", "y"):
            self.batch.Zones.Insert(self.zone(name))
        directives = self.schedule()[1]
        self.assertEqual(self.code.NATIVE_REJECTED,
                         self.commit(directives, accepted=EArray([True, False])))
        self.assertEqual(["a"], [a.ActorId for a in self.state.Assignments])
        self.assertEqual(
            (directives[0].NextActorIndex, directives[0].NextZoneIndex),
            (self.state.NextActorIndex, self.state.NextZoneIndex))
        self.assertEqual(["b"], [d.ActorId for d in self.schedule(1001)[1]])

    def test_old_context_directive_cannot_commit_into_new_context(self):
        self.batch.Actors.Insert(self.actor("a"))
        self.batch.Zones.Insert(self.zone("z"))
        directives = self.schedule()[1]
        self.policy.WorldName = self.state.WorldName = "another-world"
        self.policy.SessionId = self.state.SessionId = "session-b"
        before = repr(self.state)
        self.assertEqual(self.code.INVALID, self.commit(directives))
        self.assertEqual(before, repr(self.state))

    def test_zero_duration_cannot_propose_same_actor_twice_at_same_tick(self):
        self.policy.HysteresisMs = self.policy.CooldownMs = 0
        self.batch.Actors.Insert(self.actor("a"))
        self.batch.Zones.Insert(self.zone("z"))
        self.assertEqual(self.code.OK, self.commit(self.schedule()[1]))
        self.assertEqual([], self.schedule()[1])

    def test_full_assignment_table_requires_confirmed_retirement(self):
        self.policy.MaxActors = 2
        for name in ("a", "b"):
            self.batch.Actors.Insert(self.actor(name))
        for name in ("x", "y"):
            self.batch.Zones.Insert(self.zone(name))
        self.assertEqual(self.code.OK, self.commit(self.schedule()[1]))
        self.batch.Actors = EArray(
            [self.actor(n, observed=1031) for n in ("c", "d")])
        self.batch.ObservedAtMs = 1031
        for zone in self.batch.Zones:
            zone.ObservedAtMs = 1031
            zone.ExpiresAtMs = 1200
        self.assertEqual([], self.schedule(1031)[1])
        receipts = EArray()
        for assignment in self.state.Assignments:
            receipt = self.e["HCEcologyRetirementReceipt"]()
            receipt.WorldName = self.policy.WorldName
            receipt.SessionId = self.policy.SessionId
            receipt.ActorId = assignment.ActorId
            receipt.ZoneId = assignment.ZoneId
            receipt.AssignmentIssuedAtMs = assignment.IssuedAtMs
            receipt.ObservedAtMs = 1031
            receipt.NativeDirectiveEnded = True
            receipts.Insert(receipt)
        self.assertEqual(self.code.OK, self.e["Reconcile"](
            self.state, self.policy, receipts, 1031, self.cap))
        directives = self.schedule(1031)[1]
        self.assertEqual(["c", "d"], [d.ActorId for d in directives])
        self.assertEqual(self.code.OK, self.commit(directives, 1031))


    def native_receipts(self, directives, flags=None):
        if flags is None:
            flags = [True] * len(directives)
        return EArray([self.e["MakeReceipt"](d, flag)
                       for d, flag in zip(directives, flags)])

    def raw_commit(self, directives, receipts, now=1000):
        return self.e["Commit"](
            self.state, self.policy, directives, receipts, now, self.cap)

    def retirement(self, assignment, observed=1031):
        receipt = self.e["HCEcologyRetirementReceipt"]()
        receipt.WorldName = self.policy.WorldName
        receipt.SessionId = self.policy.SessionId
        receipt.ActorId = assignment.ActorId
        receipt.ZoneId = assignment.ZoneId
        receipt.AssignmentIssuedAtMs = assignment.IssuedAtMs
        receipt.ObservedAtMs = observed
        receipt.NativeDirectiveEnded = True
        return receipt

    def reconcile(self, receipts, now=1031):
        return self.e["Reconcile"](
            self.state, self.policy, receipts, now, self.cap)

    def test_receipt_is_detached_and_every_identity_field_is_bound(self):
        fields = ("WorldName", "SessionId", "ActorId", "ZoneId",
                  "PopulationKind", "ResourceKind", "RouteHintId",
                  "ObservationAtMs", "IssuedAtMs", "HoldUntilMs",
                  "CooldownUntilMs", "NextActorIndex", "NextZoneIndex")
        for field in fields:
            with self.subTest(field=field):
                self.setUp()
                self.batch.Actors.Insert(self.actor("a"))
                self.batch.Zones.Insert(self.zone("z"))
                directives = self.schedule()[1]
                receipts = self.native_receipts(directives)
                value = getattr(receipts[0], field)
                setattr(receipts[0], field,
                        value + "-altered" if isinstance(value, str)
                        else value + 1)
                before = repr(self.state)
                self.assertEqual(self.code.INVALID,
                                 self.raw_commit(directives, receipts))
                self.assertEqual(before, repr(self.state))
        self.setUp()
        self.batch.Actors.Insert(self.actor("a"))
        self.batch.Zones.Insert(self.zone("z"))
        directives = self.schedule()[1]
        receipts = self.native_receipts(directives)
        directives[0].ZoneId = "different-zone"
        self.assertEqual("z", receipts[0].ZoneId)
        self.assertEqual(self.code.INVALID,
                         self.raw_commit(directives, receipts))

    def test_swapped_or_bad_late_receipt_is_atomic_even_when_earlier_accepted(self):
        for name in ("a", "b"):
            self.batch.Actors.Insert(self.actor(name))
        for name in ("x", "y"):
            self.batch.Zones.Insert(self.zone(name))
        directives = self.schedule()[1]
        receipts = self.native_receipts(directives)
        before = repr(self.state)
        self.assertEqual(self.code.INVALID,
                         self.raw_commit(directives, EArray(reversed(receipts))))
        receipts[1].SessionId = "old-session"
        receipts[1].Accepted = False
        self.assertEqual(self.code.INVALID,
                         self.raw_commit(directives, receipts))
        self.assertEqual(before, repr(self.state))

    def test_receipt_arrays_and_null_entries_fail_closed(self):
        self.batch.Actors.Insert(self.actor("a"))
        self.batch.Zones.Insert(self.zone("z"))
        directives = self.schedule()[1]
        receipt = self.native_receipts(directives)[0]
        for receipts in (None, EArray(), EArray([None]),
                         EArray([receipt, receipt])):
            with self.subTest(receipts=receipts):
                before = repr(self.state)
                self.assertEqual(self.code.INVALID,
                                 self.raw_commit(directives, receipts))
                self.assertEqual(before, repr(self.state))

    def test_partial_second_confirmation_retains_its_cursor_and_rejects_replay(self):
        for name in ("a", "b"):
            self.batch.Actors.Insert(self.actor(name))
        for name in ("x", "y"):
            self.batch.Zones.Insert(self.zone(name))
        directives = self.schedule()[1]
        receipts = self.native_receipts(directives, [False, True])
        self.assertEqual(self.code.NATIVE_REJECTED,
                         self.raw_commit(directives, receipts))
        self.assertEqual(["b"], [a.ActorId for a in self.state.Assignments])
        self.assertEqual(
            (directives[1].NextActorIndex, directives[1].NextZoneIndex),
            (self.state.NextActorIndex, self.state.NextZoneIndex))
        before = repr(self.state)
        self.assertEqual(self.code.INVALID,
                         self.raw_commit(directives, receipts))
        self.assertEqual(before, repr(self.state))
        self.assertEqual(["a"], [d.ActorId for d in self.schedule(1001)[1]])

    def test_new_proposals_reserve_remaining_assignment_slots_within_batch(self):
        self.policy.MaxActors = 2
        self.batch.Actors.Insert(self.actor("a"))
        for name in ("x", "y"):
            self.batch.Zones.Insert(self.zone(name))
        self.assertEqual(self.code.OK, self.commit(self.schedule()[1]))
        self.batch.Actors = EArray([self.actor("c"), self.actor("d")])
        directives = self.schedule(1001)[1]
        self.assertEqual(["c"], [d.ActorId for d in directives])
        self.assertEqual(self.code.OK, self.commit(directives, 1001))
        self.assertEqual([], self.schedule(1002)[1])

    def test_retirement_rejects_wrong_generation_context_stale_or_unconfirmed(self):
        cases = (("WorldName", "other"), ("SessionId", "other"),
                 ("ActorId", "other"), ("ZoneId", "other"),
                 ("AssignmentIssuedAtMs", 999), ("ObservedAtMs", 900),
                 ("ObservedAtMs", 1032), ("NativeDirectiveEnded", False))
        for field, value in cases:
            with self.subTest(field=field):
                self.setUp()
                self.batch.Actors.Insert(self.actor("a"))
                self.batch.Zones.Insert(self.zone("z"))
                self.assertEqual(self.code.OK, self.commit(self.schedule()[1]))
                receipt = self.retirement(self.state.Assignments[0])
                setattr(receipt, field, value)
                before = repr(self.state)
                self.assertEqual(self.code.INVALID,
                                 self.reconcile(EArray([receipt])))
                self.assertEqual(before, repr(self.state))

    def test_retirement_is_atomic_bounded_and_requires_authoritative_provider(self):
        for name in ("a", "b"):
            self.batch.Actors.Insert(self.actor(name))
        for name in ("x", "y"):
            self.batch.Zones.Insert(self.zone(name))
        self.assertEqual(self.code.OK, self.commit(self.schedule()[1]))
        receipts = EArray([self.retirement(a) for a in self.state.Assignments])
        before = repr(self.state)
        for invalid in (None, EArray([None]), EArray([receipts[0], None]),
                        EArray([receipts[0], receipts[0]]),
                        EArray([receipts[0]] * (self.policy.MaxActors + 1))):
            self.assertEqual(self.code.INVALID, self.reconcile(invalid))
            self.assertEqual(before, repr(self.state))
        for field in ("IsServerAuthority", "ProviderAvailable"):
            setattr(self.cap, field, False)
            self.assertEqual(self.code.INVALID, self.reconcile(receipts))
            self.assertEqual(before, repr(self.state))
            setattr(self.cap, field, True)
        self.assertEqual(self.code.OK, self.reconcile(EArray([receipts[0]])))
        self.assertEqual(["b"], [a.ActorId for a in self.state.Assignments])
        self.assertEqual(self.code.INVALID, self.reconcile(EArray([receipts[0]])))
        self.assertEqual(["b"], [a.ActorId for a in self.state.Assignments])

    def test_retirement_never_bypasses_cooldown_or_zero_duration_tick_guard(self):
        self.batch.Actors.Insert(self.actor("a"))
        self.batch.Zones.Insert(self.zone("z"))
        self.assertEqual(self.code.OK, self.commit(self.schedule()[1]))
        receipt = self.retirement(self.state.Assignments[0], observed=1010)
        before = repr(self.state)
        self.assertEqual(self.code.INVALID,
                         self.reconcile(EArray([receipt]), now=1010))
        self.assertEqual(before, repr(self.state))
        self.setUp()
        self.policy.HysteresisMs = self.policy.CooldownMs = 0
        self.batch.Actors.Insert(self.actor("a"))
        self.batch.Zones.Insert(self.zone("z"))
        self.assertEqual(self.code.OK, self.commit(self.schedule()[1]))
        receipt = self.retirement(self.state.Assignments[0], observed=1000)
        before = repr(self.state)
        self.assertEqual(self.code.INVALID,
                         self.reconcile(EArray([receipt]), now=1000))
        self.assertEqual(before, repr(self.state))

    def test_retirement_generation_replay_and_clock_rollback_fail_closed(self):
        self.batch.Actors.Insert(self.actor("a"))
        self.batch.Zones.Insert(self.zone("z"))
        self.assertEqual(self.code.OK, self.commit(self.schedule()[1]))
        old = self.retirement(self.state.Assignments[0])
        self.assertEqual(self.code.OK, self.reconcile(EArray([old])))
        self.assertEqual(self.code.OK, self.commit(self.schedule(1031)[1], 1031))
        before = repr(self.state)
        self.assertEqual(self.code.INVALID,
                         self.reconcile(EArray([old]), now=1062))
        self.assertEqual(self.code.INVALID,
                         self.reconcile(EArray(), now=1030))
        self.assertEqual(before, repr(self.state))

    def test_retirement_cannot_free_slots_by_absence_or_elapsed_time_alone(self):
        self.batch.Actors.Insert(self.actor("a"))
        self.batch.Zones.Insert(self.zone("z"))
        self.assertEqual(self.code.OK, self.commit(self.schedule()[1]))
        self.batch.Actors = EArray()
        self.assertEqual([], self.schedule(1031)[1])
        before = repr(self.state)
        self.assertEqual(self.code.OK, self.reconcile(EArray()))
        self.assertEqual(before, repr(self.state))
        self.assertEqual(["a"], [a.ActorId for a in self.state.Assignments])

    def test_zone_uniqueness_is_batch_local_not_native_occupancy(self):
        for name in ("a", "b"):
            self.batch.Actors.Insert(self.actor(name))
        self.batch.Zones.Insert(self.zone("z"))
        first = self.schedule()[1]
        self.assertEqual(["a"], [d.ActorId for d in first])
        self.assertEqual(self.code.OK, self.commit(first))
        second = self.schedule(1001)[1]
        self.assertEqual([("b", "z")],
                         [(d.ActorId, d.ZoneId) for d in second])


def load_tests(loader, tests, pattern):
    # Keep the public BDD binding stable while executing the v1 ecology cases.
    # Normal whole-suite discovery already finds these files independently.
    if pattern == "test_ecology_rules.py":
        tests.addTests(loader.discover(str(ROOT.parents[2] / "tests/unit"),
                                     pattern="test_v1_ecology*.py"))
    return tests


if __name__ == "__main__":
    unittest.main()
