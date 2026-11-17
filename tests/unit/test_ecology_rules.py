"""Behavioral execution of the authored, unhooked ecology policy bodies.

The translator supplies only Enforce syntax/container scaffolding.  Authority,
freshness, eligibility, budgets, scheduling, and commit decisions remain in the
authored HCEcologyRules methods; no perception or navigation result is faked.
"""
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


def translated_rules():
    data = (ROOT / "3_Game/Ecology/HCEcologyData.c").read_text()
    source = (ROOT / "4_World/Ecology/HCEcologyRules.c").read_text()
    env = {"EArray": EArray, "len": len}

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
            lines.append("    " * indent + token)
        exec(compile("\n".join(lines), "authored-ecology:" + name, "exec"), env)
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
        return self.e["Commit"](self.state, self.policy, directives, accepted, now)

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

    def test_commit_rejection_is_atomic_and_success_applies_cooldown_hysteresis(self):
        self.batch.Actors.Insert(self.actor("a"))
        self.batch.Actors.Insert(self.actor("b"))
        self.batch.Zones.Insert(self.zone("x"))
        self.batch.Zones.Insert(self.zone("y"))
        directives = self.schedule()[1]
        before = (self.state.LastNowMs, self.state.NextActorIndex, self.state.NextZoneIndex, len(self.state.Assignments))
        self.assertEqual(self.code.NATIVE_REJECTED, self.commit(directives, accepted=EArray([True, False])))
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


if __name__ == "__main__":
    unittest.main()
