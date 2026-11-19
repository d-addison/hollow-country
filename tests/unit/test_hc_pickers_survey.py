"""Wave 16 w32-pickers: the HC-34 picker route survey and provider source, executed behaviourally.

Spec -> plan -> task: HC-34 waited on `HC34_PROVIDER_SOURCE_MISSING_ROUTE_UNSURVEYED`. The route survey is
`mission/hollow-country/ai/picker-routes.json`, DERIVED here from the repo's own scavenger sites
(`ai/sites.json`: waypoints verbatim, locality from `HC43.Localities`, home = first waypoint, source = the
opposite waypoint, thresholds copied from the sites file). Nothing is invented and nothing here observes DayZ:
the authored Enforce bodies run over explicit SYNTHETIC fakes through the repo's syntax-only translators.

Round 1 TDD receipt (2026-11-19; same command for RED and GREEN):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_pickers_survey test_hc_scavenge -v
RED: Ran 23 tests; FAILED (failures=9, errors=8).
Actual failure lines include:
  AssertionError: Tuples differ: ('refused', 'HC34_JOURNAL_UNAVAILABLE') != ('ready', 'journal_and_survey_loaded')
  AttributeError: 'NoneType' object has no attribute 'Count'
  Rejected-start tuple comparison: + (None, None, None, None, '')
GREEN: Ran 23 tests; OK. Synthetic execution only; runtime acceptance pending.
"""
import copy
import json
import math
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit import test_debug_map_layers as layers
from tests.unit.test_admin_test_kit import base_scope
from tests.unit.test_hc_scavenge import bind
from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
PICKERS = ROOT / "mods/HollowCountry/scripts/4_World/World/HCPickers.c"
SURVEY = ROOT / "mission/hollow-country/ai/picker-routes.json"
SITES = ROOT / "mission/hollow-country/ai/sites.json"
TRANSFER_RANGE = 2.5  # HCScavengeDefaults.TransferRangeMeters, the native pickup envelope


def derive(sites):
    """The ONLY derivation rule: one route per scavenger site, copied from the sites file."""
    locality = {}
    for row in sites["HC43"]["Localities"]:
        for site in row["SiteIds"]:
            locality[site] = row["Id"]
    routes = []
    for site in sites["Sites"]:
        if site["Kind"] != "scavenger":
            continue
        points = [{"X": p[0], "Y": p[1], "Z": p[2]} for p in site["Waypoints"]]
        routes.append({"RouteId": "route:" + site["Id"], "SiteId": site["Id"],
                       "LocalityId": locality[site["Id"]], "HomeIndex": 0,
                       "SourceIndex": len(points) // 2, "Waypoints": points})
    return routes


def loop_legs(points):
    return [math.dist((a["X"], a["Z"]), (b["X"], b["Z"])) for a, b in zip(points, points[1:] + points[:1])]


SURVEY_FIELDS = ("Version", "MaxLegMeters", "MapExtentMeters", "ArrivalRangeMeters", "MaxRoutes", "MaxWaypoints",
                 "MaxScannedObjects", "MaxCargoScan", "Routes")


def to_ns(value):
    if isinstance(value, dict):
        return N(**{k: to_ns(v) for k, v in value.items()})
    if isinstance(value, list):
        return EArray([to_ns(v) for v in value])
    return value


def scope(**extra):
    defaults = N(TransferRangeMeters=TRANSFER_RANGE)
    return base_scope(HCScavengeDefaults=lambda: defaults, Vector=lambda x, y, z: (x, y, z),
                      HCWorldLimits=N(Token=lambda text: 0 < len(text) <= 96), **extra)


def method(cls, name, members=(), fields=(), **extra):
    return layers.compile_authored(PICKERS, cls, name, scope(array=lambda: EArray(), **extra), members=members,
                                   fields=fields, modded=False)


class SurveyFile(unittest.TestCase):
    def setUp(self):
        self.survey = json.loads(SURVEY.read_text())
        self.sites = json.loads(SITES.read_text())

    def test_routes_are_exactly_the_derived_scavenger_site_routes(self):
        self.assertEqual(derive(self.sites), self.survey["Routes"])
        self.assertEqual(5, len(self.survey["Routes"]))

    def test_thresholds_are_copied_from_the_sites_file_and_the_pickup_envelope(self):
        self.assertEqual(self.sites["MaxLegLength"], self.survey["MaxLegMeters"])
        self.assertEqual(self.sites["WorldName"], self.survey["WorldName"])
        self.assertEqual("ai/sites.json", self.survey["DerivedFrom"])
        self.assertEqual(TRANSFER_RANGE, self.survey["ArrivalRangeMeters"])
        for route in self.survey["Routes"]:
            self.assertTrue(all(leg <= self.survey["MaxLegMeters"] for leg in loop_legs(route["Waypoints"])), route)

    def test_every_numeric_limit_is_a_named_field_and_the_file_is_small(self):
        for key in ("MaxRoutes", "MaxWaypoints", "MaxScannedObjects", "MaxCargoScan", "MapExtentMeters"):
            self.assertGreater(self.survey[key], 0, key)
        self.assertLessEqual(len(self.survey["Routes"]), self.survey["MaxRoutes"])
        self.assertLess(len(SURVEY.read_text()), 16384)

    def test_the_file_carries_no_forbidden_strings_or_home_paths(self):
        text = SURVEY.read_text().lower()
        for banned in ("snafu", "2646817942", "2291785308", "2792982069", "/home/"):
            self.assertNotIn(banned, text)


class SurveyValidation(unittest.TestCase):
    """HCPickerSurvey.HCRefusal names the first thing wrong; the shipped file has nothing wrong."""

    def survey(self, mutate=None):
        data = json.loads(SURVEY.read_text())
        if mutate:
            mutate(data)
        node = to_ns(data)
        node.HCRefusal = lambda: refusal(node)
        return node

    def setUp(self):
        global refusal
        run = method("HCPickerSurvey", "HCRefusal", fields=SURVEY_FIELDS)
        refusal = run

    def test_the_shipped_survey_has_no_refusal(self):
        self.assertEqual("", self.survey().HCRefusal())

    def test_each_named_defect_is_refused_once_with_its_own_reason(self):
        cases = (
            ("PICKER_SURVEY_VERSION", lambda d: d.update(Version=2)),
            ("PICKER_SURVEY_LIMITS", lambda d: d.update(MaxLegMeters=0.0)),
            ("PICKER_SURVEY_LIMITS", lambda d: d.update(ArrivalRangeMeters=TRANSFER_RANGE + 0.5)),
            ("PICKER_SURVEY_LIMITS", lambda d: d.update(MaxScannedObjects=0)),
            ("PICKER_SURVEY_EMPTY", lambda d: d.update(Routes=[])),
            ("PICKER_SURVEY_ROUTE_CAP", lambda d: d.update(MaxRoutes=2)),
            ("PICKER_ROUTE_ID_INVALID", lambda d: d["Routes"][0].update(RouteId="")),
            ("PICKER_ROUTE_ID_DUPLICATE", lambda d: d["Routes"][1].update(RouteId=d["Routes"][0]["RouteId"])),
            ("PICKER_ROUTE_WAYPOINTS", lambda d: d["Routes"][0].update(Waypoints=d["Routes"][0]["Waypoints"][:1])),
            ("PICKER_ROUTE_WAYPOINTS", lambda d: d.update(MaxWaypoints=3)),
            ("PICKER_ROUTE_ANCHORS", lambda d: d["Routes"][0].update(HomeIndex=9)),
            ("PICKER_ROUTE_ANCHORS", lambda d: d["Routes"][0].update(SourceIndex=0)),
            ("PICKER_ROUTE_LEG_TOO_LONG", lambda d: d["Routes"][2]["Waypoints"][1].update(X=9999.0)),
            ("PICKER_ROUTE_POINT_INVALID", lambda d: d["Routes"][0]["Waypoints"][1].update(X=-1.0)),
        )
        for reason, mutate in cases:
            self.assertEqual(reason, self.survey(mutate).HCRefusal(), reason)


    def test_missing_or_null_collections_and_elements_are_named_refusals(self):
        # Explicit synthetic JSON zero-fill: absent ref fields become null in Enforce.
        for missing in (False, True):
            for target, expected in (("routes", "PICKER_SURVEY_EMPTY"),
                                     ("route", "PICKER_ROUTE_ID_INVALID"),
                                     ("waypoints", "PICKER_ROUTE_WAYPOINTS"),
                                     ("point", "PICKER_ROUTE_POINT_INVALID"),
                                     ("following", "PICKER_ROUTE_POINT_INVALID")):
                with self.subTest(target=target, missing=missing):
                    data = json.loads(SURVEY.read_text())
                    owner, key = data, "Routes"
                    if target == "route":
                        data["Routes"][0] = None
                    elif target in ("point", "following"):
                        data["Routes"][0]["Waypoints"][int(target == "following")] = None
                    else:
                        if target == "waypoints":
                            owner, key = data["Routes"][0], "Waypoints"
                        if missing:
                            owner.pop(key)
                        else:
                            owner[key] = None
                        # Model native missing-field zero-fill, not Python attribute errors.
                        owner.setdefault(key, None)
                    self.assertEqual(expected, refusal(to_ns(data)))


class SurveyLookupAndLegs(unittest.TestCase):
    def setUp(self):
        self.data = to_ns(json.loads(SURVEY.read_text()))
        find = method("HCPickerSurvey", "HCFind", fields=("Routes",))
        self.find = lambda route_id: find(self.data, route_id)

    def test_find_matches_only_the_exact_route_id(self):
        self.assertEqual("scav-vybor", self.find("route:scav-vybor").SiteId)
        for wrong in ("", "route:", "route:scav-vybo", "scav-vybor", "ROUTE:scav-vybor", "route:scav-vybor "):
            self.assertIsNone(self.find(wrong), wrong)

    def test_outbound_and_return_legs_walk_the_loop_forward_and_close_on_the_other_anchor(self):
        legs = method("HCPickerRoute", "HCLegPoints", fields=("Waypoints", "HomeIndex", "SourceIndex"))
        route = self.data.Routes[0]
        for point in route.Waypoints:
            point.HCPosition = (lambda p: lambda: (p.X, p.Y, p.Z))(point)
        out, back = EArray(), EArray()
        legs(route, False, out)
        legs(route, True, back)
        raw = [(p.X, p.Y, p.Z) for p in route.Waypoints]
        self.assertEqual([raw[1], raw[2]], list(out))   # home 0 -> source 2, the loop's own order
        self.assertEqual([raw[3], raw[0]], list(back))  # source 2 -> home 0, still forward on the loop
        self.assertEqual(raw[route.SourceIndex], out[-1])
        self.assertEqual(raw[route.HomeIndex], back[-1])


class RouteReadyAndBinding(unittest.TestCase):
    """HCScavengeInventory consumes the survey; a route the survey does not list is never ready."""

    def setUp(self):
        self.data = to_ns(json.loads(SURVEY.read_text()))
        self.data.HCFind = lambda route_id: next((r for r in self.data.Routes if r.RouteId == route_id), None)
        self.ready = method("HCScavengeInventory", "HCRouteReady", fields=("Survey",), HCAIPartyIdentity=N(HCValid=lambda i: i is not None))

    def identity(self, route_id):
        return N(HCRouteId=lambda: route_id)

    def test_a_surveyed_route_with_a_lease_is_ready(self):
        io = N(Survey=self.data)
        self.assertTrue(self.ready(io, self.identity("route:scav-berezino"), "lease-1"))

    def test_no_survey_unknown_route_or_empty_lease_is_not_ready(self):
        self.assertFalse(self.ready(N(Survey=None), self.identity("route:scav-berezino"), "lease-1"))
        io = N(Survey=self.data)
        self.assertFalse(self.ready(io, self.identity("route:police-chernogorsk"), "lease-1"))
        self.assertFalse(self.ready(io, self.identity("route:scav-berezino"), ""))
        self.assertFalse(self.ready(io, None, "lease-1"))


class BindSurveyed(unittest.TestCase):
    """HCBindSurveyed finds the two real crates at the surveyed anchors and one takeable item; else binds nothing."""

    def crate(self, name, position, items=(), locked=False):
        item = lambda n, takeable=True, ruined=False: N(Name=n, IsTakeable=lambda: takeable, IsRuined=lambda: ruined)
        entries = [item(n, t, r) for n, t, r in items]
        cargo = N(GetItemCount=lambda: len(entries), GetItem=lambda i: entries[i])
        return N(Name=name, Position=position, locked=locked, entries=entries, IsKindOf=lambda kind: kind == "WoodenCrate",
                 GetInventory=lambda: N(GetCargo=lambda: cargo))

    def setUp(self):
        self.data = to_ns(json.loads(SURVEY.read_text()))
        route = self.data.Routes[0]
        for point in route.Waypoints:
            point.HCPosition = (lambda p: lambda: (p.X, p.Y, p.Z))(point)
        route.HCHomePoint = lambda: route.Waypoints[route.HomeIndex].HCPosition()
        route.HCSourcePoint = lambda: route.Waypoints[route.SourceIndex].HCPosition()
        self.route = route
        self.home = self.crate("home", route.HCHomePoint())
        self.source = self.crate("source", route.HCSourcePoint(), (("junk", False, False), ("rag", True, False)))
        self.world = [self.home, self.source]
        self.scans = []

    def run_bind(self, world=None, accessible=lambda crate: True, scan_cap=None):
        world = self.world if world is None else world
        if scan_cap is not None:
            self.data.MaxScannedObjects = scan_cap

        def objects_at(position, radius, objects, cargos):
            self.scans.append((position, radius))
            objects.extend(o for o in world if o.Position == position)

        game = N(GetObjectsAtPosition3D=objects_at)
        crates = {"home": self.home, "source": self.source}
        io = N(Survey=self.data, Actor=None, Source=None, Home=None, Item=None, LeaseId="",
               HCAccessible=accessible, HCClear=lambda: None)
        io.HCClear = lambda: [setattr(io, k, None) for k in ("Actor", "Source", "Home", "Item")]
        scope_extra = dict(GetGame=lambda: game, ItemBase=N(Cast=lambda o: o),
                           HCSearchSupplyRegistry=N(PersistentId=lambda e: "id-" + e.Name))
        fields = ("Survey", "Actor", "Source", "Home", "Item", "LeaseId")
        for name in ("HCFindCrate", "HCFirstItem"):
            runner = method("HCScavengeInventory", name, members=("HCAccessible",), fields=fields, **scope_extra)
            setattr(io, name, (lambda r: lambda *a: r(io, *a))(runner))
        bind = method("HCScavengeInventory", "HCBindSurveyed", members=("HCClear", "HCFindCrate", "HCFirstItem"),
                      fields=fields, **scope_extra)
        actor = N(Name="actor")
        return io, bind(io, actor, self.route, "lease-1")

    def test_binds_the_actor_the_two_crates_and_the_first_takeable_item(self):
        io, bound = self.run_bind()
        self.assertTrue(bound)
        self.assertEqual(("home", "source", "rag"), (io.Home.Name, io.Source.Name, io.Item.Name))
        self.assertEqual("lease-1", io.LeaseId)
        self.assertEqual(2, len(self.scans))
        self.assertTrue(all(radius == self.data.ArrivalRangeMeters for _, radius in self.scans))

    def test_a_missing_crate_an_inaccessible_crate_or_no_takeable_item_binds_nothing(self):
        for world in ([self.source], [self.home]):
            io, bound = self.run_bind(world=world)
            self.assertFalse(bound)
            self.assertIsNone(io.Actor)
        io, bound = self.run_bind(accessible=lambda crate: crate.Name != "source")
        self.assertFalse(bound)
        self.source.entries.clear()
        io, bound = self.run_bind()
        self.assertFalse(bound)
        self.assertIsNone(io.Source)

    def test_the_object_scan_cap_refuses_a_crowded_anchor_instead_of_guessing(self):
        io, bound = self.run_bind(scan_cap=1, world=[self.home, self.source, self.crate("extra", self.route.HCHomePoint())])
        self.assertFalse(bound)


class PickersModuleReadiness(unittest.TestCase):
    """Readiness is derived from the journal and the survey, never hard-coded; the old refusal is gone."""

    def setUp(self):
        self.source = PICKERS.read_text()

    def test_the_old_refusal_reason_is_gone_from_the_module(self):
        for stale in ("HC34_PROVIDER_SOURCE_MISSING_ROUTE_UNSURVEYED", "PROVIDER_SOURCE_MISSING_ROUTE_UNSURVEYED"):
            self.assertNotIn(stale, self.source)

    def readiness(self, trip_ready, survey, refusal="PICKER_SURVEY_UNAVAILABLE"):
        published = []
        status = N(HCPublish=lambda state, reason: published.append((state, reason)),
                   HCState=lambda: published[-1][0] if published else "unknown",
                   HCReason=lambda: published[-1][1] if published else "owner_state_unknown")
        run = method("HCPickers", "HCPublishReadiness")
        receiver = N(m_Trip=N(m_Ready=trip_ready) if trip_ready is not None else None, m_Survey=survey,
                     m_SurveyRefusal=refusal, m_Status=status)
        run(receiver)
        return published

    def test_ready_needs_the_journal_and_a_loaded_valid_survey(self):
        self.assertEqual([("ready", "journal_and_survey_loaded")], self.readiness(True, object()))
        self.assertEqual([("refused", "HC34_JOURNAL_UNAVAILABLE")], self.readiness(False, object()))
        self.assertEqual([("refused", "HC34_JOURNAL_UNAVAILABLE")], self.readiness(None, object()))
        self.assertEqual([("degraded", "PICKER_SURVEY_VERSION")], self.readiness(True, None, "PICKER_SURVEY_VERSION"))

    def test_the_survey_is_loaded_once_from_the_mission_file_with_the_zero_fill_guards(self):
        self.assertIn('"$mission:hollow-country/ai/picker-routes.json"', self.source)
        self.assertEqual(1, self.source.count("class HCPickerSurvey"))
        for guard in ('HCJsonFields.Has(text, "Version")', 'HCJsonFields.Every(text, "HomeIndex", 3, "Waypoints")',
                      'HCJsonFields.Every(text, "SourceIndex", 3, "Waypoints")', 'HCJsonFields.Every(text, "X", 5)',
                      "JsonFileLoader<HCPickerSurvey>.LoadData"):
            self.assertIn(guard, self.source)

    def test_the_missing_provider_part_is_one_named_line_derived_from_the_bound_port(self):
        self.assertEqual(1, self.source.count("[HC Pickers] provider walk=unbound"))
        self.assertIn("HCWalkRefusal", self.source)
        self.assertNotIn('HCPublish("ready"', self.source.replace("m_Status.HCPublish(\"ready\", \"journal_and_survey_loaded\")", ""))


class PickerOperationRegressions(unittest.TestCase):
    """Authored module and trip methods over synthetic ports/journals; no DayZ evidence."""

    def fixture(self):
        publications, effects = [], []
        status = N(HCPublish=lambda state, reason: publications.append((state, reason)),
                   HCState=lambda: publications[-1][0] if publications else "unknown",
                   HCReason=lambda: publications[-1][1] if publications else "owner_state_unknown")
        port = N(Actor=object(), Source=object(), Home=object(), Item=object(), LeaseId="active-lease", HCWalkRefusal=lambda: "")
        def clear():
            effects.append("clear")
            for key in ("Actor", "Source", "Home", "Item"):
                setattr(port, key, None)
            port.LeaseId = ""
        def bind_port(*args):
            clear()
            effects.append("bind")
            return False
        port.HCClear, port.HCBindSurveyed = clear, bind_port
        trip = N(m_IO=port, m_Ready=True, m_Busy=False,
                 m_State=N(Phase="idle", LeaseId="active-lease", CargoOwner="source", Refusal=""),
                 m_Store=N(Save=lambda row: False), HCLog=lambda: None)
        bind(PICKERS.read_text(), "HCScavengeTrip", trip, ("HCCheckpoint",), {})
        budget = N(HCReset=lambda cap: effects.append("budget"), HCTake=lambda cost: True,
                   HCContinue=lambda: True)
        module = N(m_Trip=trip, m_Survey=N(HCFind=lambda route: object()), m_SurveyRefusal="",
                   m_RunsOn=False, m_Danger=None, m_Houses=None,
                   m_Status=status, m_Units=budget, m_WorkBudget=budget)
        for name in ("HCPublishReadiness", "HCBeginSurveyed", "OnTick"):
            run = method("HCPickers", name, members=("HCPublishReadiness",),
                         HCAIPartyIdentity=N(HCValid=lambda identity: True),
                         HCSearchSupplyRegistry=N(PersistentId=lambda entity: "id"))
            setattr(module, name, (lambda r: lambda *args: r(module, *args))(run))
        return module, publications, effects

    def test_rejected_start_preserves_all_handles_and_leases_without_binding(self):
        for phase, busy in (("leaving", False), ("returning", False), ("idle", True),
                            ("acquiring", True), ("returned", False), (None, False)):
            with self.subTest(phase=phase, busy=busy):
                module, published, effects = self.fixture()
                trip, port = module.m_Trip, module.m_Trip.m_IO
                trip.m_Busy = busy
                trip.m_State.Phase = phase
                if phase is None:
                    trip.m_State = None
                before = tuple(getattr(port, key) for key in ("Actor", "Source", "Home", "Item", "LeaseId"))
                state_before = copy.deepcopy(trip.m_State)
                result = module.HCBeginSurveyed(N(HCRouteId=lambda: "route"), "replacement-lease", object())
                self.assertNotEqual("", result)
                self.assertEqual(before, tuple(getattr(port, key) for key in ("Actor", "Source", "Home", "Item", "LeaseId")))
                self.assertEqual(state_before, trip.m_State)
                self.assertEqual([], effects, "rejected start must do no binding or budget work")

    def test_tick_checkpoint_failure_refreshes_status_before_later_early_returns(self):
        module, published, effects = self.fixture()
        module.HCPublishReadiness()
        module.m_Trip.m_State.Phase = "leaving"
        module.m_Trip.HCStep = module.m_Trip.HCCheckpoint
        module.OnTick(1.0)
        self.assertFalse(module.m_Trip.m_Ready)
        self.assertEqual([("ready", "journal_and_survey_loaded"),
                          ("refused", "HC34_JOURNAL_UNAVAILABLE")], published)
        module.OnTick(1.0)
        module.HCPublishReadiness()
        self.assertEqual(2, len(published), "unchanged status must not be republished")

    def test_tick_refreshes_a_failure_observed_before_its_early_return(self):
        module, published, effects = self.fixture()
        module.HCPublishReadiness()
        module.m_Trip.HCCheckpoint()
        module.OnTick(1.0)
        self.assertEqual(("refused", "HC34_JOURNAL_UNAVAILABLE"), published[-1])
        self.assertEqual([], effects)

    def test_begin_checkpoint_failure_refreshes_status(self):
        module, published, effects = self.fixture()
        module.HCPublishReadiness()
        module.m_Trip.m_IO.HCBindSurveyed = lambda *args: True
        module.m_Trip.HCLeave = lambda *args: module.m_Trip.HCCheckpoint()
        self.assertEqual("PICKER_LEAVE_REFUSED", module.HCBeginSurveyed(
            N(HCRouteId=lambda: "route"), "lease", object()))
        self.assertEqual(("refused", "HC34_JOURNAL_UNAVAILABLE"), published[-1])


class ShippedSurveyFieldPresence(unittest.TestCase):
    """Authored HCPickerSurvey.HCFieldsPresent over the authored HCJsonFields and the shipped survey text.

    Native boot 076 (03d4aa7): [HC Pickers] degraded reason=PICKER_SURVEY_FIELDS_MISSING after the
    #205 CacheLoot rows were added at the same depth as the route objects.
    """

    @staticmethod
    def present():
        from tests.unit.json_loader_port import json_fields_port
        from tests.unit.test_event_runtime import translate
        source = (ROOT / "mods/HollowCountry/scripts/4_World/World/HCPickers.c").read_text()
        env = {"HCJsonFields": json_fields_port()}
        # #144: HCFieldsPresent delegates the run limits to HCRunFieldsPresent (same authored class).
        env["HCPickerSurvey"] = N(HCRunFieldsPresent=translate(source, "HCRunFieldsPresent", dict(env)))
        return translate(source, "HCFieldsPresent", env)

    def test_the_shipped_survey_with_cache_loot_rows_has_every_field(self):
        self.assertTrue(self.present()(SURVEY.read_text()))

    def test_a_route_without_its_route_id_is_still_refused(self):
        data = json.loads(SURVEY.read_text())
        del data["Routes"][1]["RouteId"]
        self.assertFalse(self.present()(json.dumps(data, indent=2)))


if __name__ == "__main__":
    unittest.main()
