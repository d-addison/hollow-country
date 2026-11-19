"""Wave 16 W32: infected posture, variety and horde migration readiness.

Synthetic ports only; offline tests never establish DayZ behaviour. The route
nodes are derived from patrol waypoints already shipped in
mission/hollow-country/ai/sites.json (offline derivation, not a native survey).

Actual RED, before implementation (2026-11-19):
python3 -B -m unittest tests.unit.test_w32_infected -v
AssertionError: False is not true : shipped route manifest admits no route
AssertionError: ... : loaded routes did not report ready
GREEN: same command, Ran 6 tests; OK.
"""
import json
import math
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit.test_event_runtime import EArray
from tests.unit.test_hc_horde_routes import MIGRATION, Vec, authored, bind

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'mission/hollow-country/infected/route-surveys.json'
SITES = ROOT / 'mission/hollow-country/ai/sites.json'


def routes_port(manifest):
    cfg = N(**manifest['Defaults'])
    env = dict(Math=N(Min=min, Max=max), Vector=lambda x, y, z: Vec([x, y, z]),
               vector=N(DistanceSq=lambda a, b: sum((x - y) ** 2 for x, y in zip(a, b))),
               HCHordeRouteDefaults=lambda: N(**manifest['Defaults']),
               HCInfectedStore=N(ValidPosition=lambda p: len(p) == 3 and all(abs(v) < 1e6 for v in p)),
               HCHordeMigration=N(Active=lambda: True), Print=lambda text: None)
    routes = N(m_static_Document=None, m_static_Reason='not loaded')
    env['HCHordeRoutes'] = routes
    bind(routes, MIGRATION, 'HCHordeRoutes',
         ('Defaults', 'ValidDefaults', 'ValidSurvey', 'HCBind', 'Select', 'Reason', 'HCClear'), env)
    return routes, cfg


class ShippedRouteSurvey(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text())

    def test_shipped_manifest_admits_routes_through_the_authored_binder(self):
        routes, cfg = routes_port(self.manifest)
        rows = EArray(N(**{**r, 'Nodes': EArray(Vec(n) for n in r['Nodes'])}) for r in self.manifest['Routes'])
        document = N(SchemaVersion=1, WorldName='chernarusplus', Enabled=True, Defaults=cfg, Routes=rows)
        self.assertTrue(routes.HCBind(document, 'chernarusplus'), 'shipped route manifest admits no route')
        self.assertEqual('SURVEY_SOURCE_READY_NATIVE_PENDING', routes.Reason())

    def test_every_node_is_a_shipped_patrol_waypoint_within_segment_limit(self):
        sites = {s['Id']: s for s in json.loads(SITES.read_text())['Sites']}
        limit = self.manifest['Defaults']['NativeSegmentMetres']
        self.assertTrue(1 <= len(self.manifest['Routes']) <= 8)
        ids = [r['Id'] for r in self.manifest['Routes']]
        self.assertEqual(len(ids), len(set(ids)))
        for route in self.manifest['Routes']:
            self.assertTrue(route['Surveyed'], route['Id'])
            self.assertTrue(0 < len(route['Evidence']) <= 128, route['Id'])
            self.assertIn('offline', route['Evidence'])
            self.assertTrue(2 <= len(route['Nodes']) <= 8, route['Id'])
            site_id = route['Evidence'].split(':')[1]
            waypoints = [tuple(w) for w in sites[site_id]['Waypoints']]
            for node in route['Nodes']:
                self.assertIn(tuple(node), waypoints, route['Id'])
            for a, b in zip(route['Nodes'], route['Nodes'][1:]):
                self.assertTrue(0 < math.dist(a, b) <= limit, route['Id'])

    def test_each_route_endpoint_pair_binds_in_both_directions(self):
        routes, cfg = routes_port(self.manifest)
        rows = EArray(N(**{**r, 'Nodes': EArray(Vec(n) for n in r['Nodes'])}) for r in self.manifest['Routes'])
        document = N(SchemaVersion=1, WorldName='chernarusplus', Enabled=True, Defaults=cfg, Routes=rows)
        self.assertTrue(routes.HCBind(document, 'chernarusplus'))
        for row in rows:
            clue = N(Origin=row.Nodes[-1])
            self.assertIs(row, routes.Select(row.Nodes[0], clue), row.Id)
            self.assertIs(row, routes.Select(row.Nodes[-1], N(Origin=row.Nodes[0])), row.Id)


class MigrationReadiness(unittest.TestCase):
    def start(self, loaded, reason):
        logs, statuses = [], []
        status = N(HCPublish=lambda *a: statuses.append(a),
                   HCState=lambda: statuses[-1][0], HCReason=lambda: statuses[-1][1])
        routes = N(HCLoad=lambda world: loaded, Reason=lambda: reason)
        env = dict(Print=logs.append, GetGame=lambda: N(GetWorldName=lambda: 'chernarusplus'),
                   HCV2Admission=N(Line=lambda *a: 'admission'), HCV2Gates=N(Qualified=lambda g: False),
                   HCHordeRoutes=routes)
        ctx = N(m_WaitingPrinted=True, m_Status=status, m_static_Active=False)
        bind(ctx, MIGRATION, 'HCHordeMigration', ('OnStart',), env)
        ctx.OnStart(N())
        return statuses, logs

    def test_loaded_routes_report_ready_not_degraded(self):
        statuses, logs = self.start(True, 'SURVEY_SOURCE_READY_NATIVE_PENDING')
        self.assertEqual('ready', statuses[-1][0], 'loaded routes did not report ready')
        self.assertIn('runtime_pending', statuses[-1][1])

    def test_operator_off_and_missing_data_stay_honest(self):
        self.assertEqual('off', self.start(False, 'ROUTE_OPERATOR_OFF')[0][-1][0])
        self.assertEqual('refused', self.start(False, 'ROUTE_SURVEY_PENDING')[0][-1][0])


if __name__ == '__main__':
    unittest.main()
