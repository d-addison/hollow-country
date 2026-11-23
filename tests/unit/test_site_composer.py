"""tools.package.site_composer on a hand-made repo (synthetic world, importer-schema survey, no model data)."""
import copy
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.package import map_overlay
from tools.package import site_composer as sc
from tools.validate import site_rules as sr

ROOT = Path(__file__).resolve().parents[2]


def box(sx, sz):
    return {'geometry_min_m': [-sx / 2, 0, -sz / 2], 'geometry_max_m': [sx / 2, 1, sz / 2],
            'footprint_m': [sx, sz], 'size_m': [sx, 1, sz]}


def klass(kind, role):
    return {'kind': kind, 'role': role, 'footprint_reserve_m': [2, 2]}


CLASSES = {
    'T_Barrier': klass('prop', 'barrier'), 'T_Nest': klass('prop', 'nest'), 'T_Tent': klass('tent', 'tent'),
    'T_Fireplace': klass('prop', 'scene dressing'), 'T_Crate': klass('container', 'container'),
    'T_Litter': klass('prop', 'scene dressing'), 'T_Chair': klass('prop', 'furnishing'),
}
GEOMETRY = {'classes': {
    'T_Barrier': {'bounds': box(2, 1), 'symmetric': False, 'front_yaw_deg': 0, 'front_source': 'authored'},
    'T_Nest': {'bounds': box(2, 2), 'symmetric': False, 'front_yaw_deg': 0, 'front_source': 'authored'},
    'T_Tent': {'bounds': box(4, 4), 'symmetric': False, 'front_yaw_deg': 0, 'front_source': 'authored'},
    'T_Fireplace': {'bounds': box(1, 1), 'symmetric': True},
    'T_Crate': {'bounds': box(2, 6), 'symmetric': False, 'front_yaw_deg': 0, 'front_source': 'authored'},
    'T_Litter': {'bounds': box(0.5, 0.5), 'symmetric': True},
    'T_Chair': {'bounds': box(0.5, 0.5), 'symmetric': False, 'front_yaw_deg': 0, 'front_source': 'authored'},
}}


def part(pid, cls, op, **kw):
    row = {'id': pid, 'class': cls, 'op': op, 'loot': 'none', 'count': 1}
    row.update(kw)
    return row


def arch(ident, kind, forward, parts, location=None, zones=None, density=None, **kw):
    doc = {'kind': 'hollow-country-site-archetype', 'id': ident, 'story': 'A %s.' % ident,
           'frame': {'kind': kind, 'forward': forward}, 'location': location or {}, 'parts': parts,
           'density': density or {'max_per_map': 20, 'min_same_m': 400, 'min_any_m': 300}}
    if zones:
        doc['zones'] = zones
    doc.update(kw)
    return doc


ROAD_LOC = {'road': {'surface': ['asphalt'], 'straight_m': 100, 'max_turn_deg': 10, 'max_grade_pct': 8},
            'settlement_edge_m': [300, 5000], 'not_in': ['military', 'town_core'], 'slope_pct_max': 8}
POST_PARTS = [
    part('barrier', 'T_Barrier', 'across_lane', anchor=True, loot='proto', count=2, gap_m=3.5, s=8.0,
         faces='-forward'),
    part('nest', 'T_Nest', 'shoulder', side='right', s=0.0, offset_m=3.0, faces='forward', guard_post=True),
    part('rear', 'T_Nest', 'shoulder', side='left', s=-6.0, offset_m=3.0, faces='forward', guard_post=True),
    part('fire', 'T_Fireplace', 'offroad', side='right', s=2.0, offset_m=14.0),
    part('tent', 'T_Tent', 'offroad', side='right', s=-4.0, offset_m=20.0, faces='of', of='fire'),
    part('litter', 'T_Litter', 'scatter', count=[1, 3], zone='yard', min_gap_m=2.0),
]
POST = arch('roadpost', 'road', 'toward_settlement', POST_PARTS, ROAD_LOC,
            zones=[{'id': 'yard', 'of': 'fire', 'shape': 'disc', 'r_m': 6}], zone_role='outpost')
CAMP = arch('camp', 'approach', 'toward_road_access',
            [part('crate', 'T_Crate', 'offroad', anchor=True, loot='proto', side='right', s=0.0, offset_m=6.0,
                  align='road'),
             part('seats', 'T_Chair', 'row', count=3, faces='forward', spacing_m=1.5, side='left', s=0.0,
                  offset_m=4.0, run='lateral')],
            {'settlement_edge_m': [300, 5000], 'slope_pct_max': 8, 'not_in': ['military', 'town_core']})

# every operator in one archetype: in_lane, across_lane, shoulder, offroad, row, ring, facing, beside, behind, scatter
FULL = arch('full', 'road', 'toward_settlement', [
    part('barrier', 'T_Barrier', 'across_lane', anchor=True, loot='proto', count=2, gap_m=3.5, s=8.0, faces='-forward'),
    part('nest', 'T_Nest', 'shoulder', side='right', s=0.0, offset_m=3.0, faces='forward', guard_post=True),
    part('rear', 'T_Nest', 'shoulder', side='left', s=-6.0, offset_m=3.0, faces='forward', guard_post=True),
    part('fire', 'T_Fireplace', 'offroad', side='right', s=2.0, offset_m=16.0),
    part('tent', 'T_Tent', 'offroad', side='right', s=-4.0, offset_m=24.0, faces='of', of='fire'),
    part('seats', 'T_Chair', 'ring', of='fire', r_m=2.5, count=3, arc_deg=180, centre_on='forward', faces='of'),
    part('bags', 'T_Barrier', 'ring', of='tent', r_m=6.0, count=3, arc_deg=120, centre_on='back', faces='outward'),
    part('stool', 'T_Chair', 'facing', of='fire', dist_m=1.5, **{'from': 'front'}),
    part('crate', 'T_Crate', 'beside', of='tent', dist_m=8.0, side='right', loot='proto'),
    part('post', 'T_Barrier', 'behind', of='tent', dist_m=13.0),
    part('seat2', 'T_Chair', 'in_lane', s=-14.0, lane='left', angle_deg=20, jitter_deg=4),
    part('hedge', 'T_Barrier', 'row', side='left', s=10.0, offset_m=14.0, count=3, spacing_m=3.0, run='forward', faces='axis'),
    part('litter', 'T_Litter', 'scatter', count=[1, 3], zone='yard', min_gap_m=2.0),
  ], ROAD_LOC, zones=[{'id': 'yard', 'of': 'fire', 'shape': 'disc', 'r_m': 6}])

CAND_Z = (500.0, 1500.0, 2500.0, 3500.0, 4500.0)
ROAD_X = 1000.0
HOUSES = [('Land_House_1', 1700.0 + 12.0 * k, 0.0, 2500.0 + 3.0 * k, 0.0) for k in range(8)]
MILITARY = [('Land_Mil_Barracks1', 3000.0, 0.0, 800.0, 0.0)]


def graph_doc():
    nodes = [(ROAD_X, 0.0, 50.0 * k) for k in range(121)] + [(ROAD_X + 50.0, 0.0, 3000.0),
                                                              (ROAD_X + 100.0, 0.0, 3000.0)]
    edges = [[] for _ in nodes]

    def link(a, b):
        edges[a].append(b)
        edges[b].append(a)
    for k in range(120):
        link(k, k + 1)
    link(60, 121)
    link(121, 122)
    flat, offsets, adj = [], [0], []
    for n in nodes:
        flat += list(n)
    for e in edges:
        adj += e
        offsets.append(len(adj))
    return {'NodeCount': len(nodes), 'Positions': flat, 'Offsets': offsets, 'Edges': adj}


def survey_docs(cands=CAND_Z, road_x=ROAD_X):
    roads = [[road_x, 20.0 * k, 'asphalt'] for k in range(301)]
    cells = []
    for z in cands:
        for i in range(-6, 7):
            for j in range(-6, 7):
                cells.append([road_x + 8.0 * i, z + 8.0 * j, 2.0, 0])
    return ({'kind': 'hollow-country-site-survey', 'version': 1, 'road_samples': roads},
            {'kind': 'hollow-country-site-survey', 'version': 1, 'cells': {'size_m': 8, 'samples': cells}})


def dump(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n')


def make_repo(tmp, archetypes=None, cands=CAND_Z, stock=None, survey=True, profile_extra=None):
    root = Path(tmp)
    dump(root / 'mission/hollow-country/ai/road-graph.compact.json', graph_doc())
    dump(root / 'config/map-overlays/classes.json', {'kind': 'hollow-country-overlay-classes',
                                                      'provenance': {'source': 'fixture'}, 'classes': CLASSES})
    profile = {'kind': 'hollow-country-overlay-profile', 'enabled': [], 'limits': {'max_objects_total': 50}}
    profile.update(profile_extra or {})
    dump(root / 'config/map-overlays/profile.json', profile)
    (root / 'config/map-overlays/layers').mkdir(parents=True, exist_ok=True)
    dump(root / 'config/sites/class-geometry.json', GEOMETRY)
    for a in (archetypes if archetypes is not None else [POST, CAMP]):
        dump(root / 'config/sites/archetypes' / (a['id'] + '.json'), a)
    dump(root / 'config/sites/survey/candidates.json',
         {'schema': 1, 'kinds': ['junction', 'dead_end', 'straight', 'extra'], 'road_spacing_m': 50,
          'source': 'fixture', 'rows': [[ROAD_X + 1.5, z, 2, 0.0] for z in cands]})
    if survey:
        roads, cells = survey_docs(cands)
        dump(root / 'config/sites/survey/roads.json', roads)
        dump(root / 'config/sites/survey/cells.json', cells)
    rows = stock if stock is not None else HOUSES + MILITARY
    xml = '<map>%s</map>' % ''.join('<group name="%s" pos="%.1f %.1f %.1f" a="%.1f"/>' % r for r in rows)
    (root / 'mission').mkdir(parents=True, exist_ok=True)
    (root / 'mission/mapgrouppos.xml').write_text(xml)
    return root


def good_piece(**kw):
    piece = {'corners_y': [0.0, 0.05, 0.1, 0.0], 'center_y': 0.0, 'slope_pct': 2.0, 'water': False,
             'collides': False}
    piece.update(kw)
    return piece


def add_pieces(root, plan, **bad):
    """The second survey pass: a probe entry for every pending box (bad = {id fragment: overrides})."""
    pieces = {}
    for row in sc.pieces_request(plan):
        extra = next((v for k, v in bad.items() if k in row['id']), {})
        pieces[row['id']] = good_piece(**extra)
    path = Path(root) / 'config/sites/survey/pieces.json'
    old = json.loads(path.read_text())['pieces'] if path.is_file() else {}
    old.update(pieces)
    dump(path, {'kind': 'hollow-country-site-survey', 'version': 1, 'pieces': old})


class Repo(unittest.TestCase):
    """Builds a fixture repo and a finished plan (both survey passes) per test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = mock.patch.dict(os.environ, {'HC_CE_MISSION': str(Path(self.tmp.name) / 'mission')})
        self.env.start()
        self.addCleanup(self.env.stop)

    def repo(self, **kw):
        return make_repo(self.tmp.name, **kw)

    def world(self, root):
        return sc.load_world(root)

    def two_pass(self, root, accept=(), **bad):
        plan = sc.compose(self.world(root), accept)
        add_pieces(root, plan, **bad)
        return sc.compose(self.world(root), accept)

    def binding(self, plan):
        return [r.get('binding') for r in plan.rows]


class TestComposeAndGate(Repo):
    def test_places_every_candidate_and_site_rules_pass(self):
        root = self.repo()
        plan = self.two_pass(root)
        self.assertEqual(len(CAND_Z), len(plan.results), self.binding(plan))
        self.assertEqual([], plan.pending)
        sc.write_plan(root, plan)
        inp = sr.load_inputs(root, root / 'mission')
        sites = sr.load_composed_sites(inp)
        out = sr.run(inp, sites, with_archetypes=False)
        sr.check_rebuild(inp, root, out)
        real = [r for r in out.rows if not (r[1] == 'R3' and 'but no object of part' in r[2])]
        self.assertEqual([], real)
        self.assertEqual(2, len(inp.composed_files))
        archetypes = {r.site['archetype'] for r in plan.results}
        self.assertEqual({'roadpost', 'camp'}, archetypes)

    def test_layer_rows_carry_custom_string_ypr_and_yaw_source(self):
        root = self.repo()
        plan = self.two_pass(root)
        docs = sc.layer_docs(plan)
        self.assertEqual({'config/map-overlays/layers/composed-camp.json',
                          'config/map-overlays/layers/composed-roadpost.json'}, set(docs))
        tag = re.compile(map_overlay.SITE_TAG)
        for doc in docs.values():
            for o in doc['objects']:
                self.assertRegex(o['customString'], tag)
                self.assertEqual('hcsite:%s:%s' % (o['site'], o['part']), o['customString'])
                self.assertEqual([o['yaw'], 0.0, 0.0], o['ypr'])
                self.assertNotRegex(o['yaw_source'], r'^(sweep|first_fit)')
                self.assertEqual(round(o['pos'][0], 1), o['pos'][0])

    def test_site_ids_and_object_ids_are_valid(self):
        plan = self.two_pass(self.repo())
        for r in plan.results:
            self.assertRegex(r.site['id'], map_overlay.SITE_ID)
            for o in r.objects:
                self.assertRegex(o['id'], map_overlay.OBJECT_ID)

    def test_layers_validate_in_map_overlay(self):
        root = self.repo()
        plan = self.two_pass(root)
        sc.write_plan(root, plan)
        source = map_overlay.load_source(root / 'config/map-overlays')
        errors = [e for e in map_overlay.validate(source)]
        self.assertEqual([], errors)


class TestEveryOperator(Repo):
    def test_all_operators_place_and_pass_site_rules(self):
        root = self.repo(archetypes=[FULL])
        plan = self.two_pass(root)
        self.assertEqual(len(CAND_Z), len(plan.results), [r.get('text') for r in plan.rows])
        ops = {p['op'] for p in FULL['parts']}
        self.assertEqual({'in_lane', 'across_lane', 'shoulder', 'offroad', 'row', 'ring', 'facing', 'beside',
                          'behind', 'scatter'}, ops)
        parts = {o['part'] for r in plan.results for o in r.objects}
        self.assertEqual({p['id'] for p in FULL['parts']}, parts)
        sc.write_plan(root, plan)
        inp = sr.load_inputs(root, root / 'mission')
        out = sr.run(inp, sr.load_composed_sites(inp), with_archetypes=False)
        sr.check_rebuild(inp, root, out)
        left = [r for r in out.rows if not (r[1] == 'R3' and "faces 'axis'" in r[2])]
        self.assertEqual([], left)
        # the validator cannot resolve `faces: axis`; the composer says so in its report instead of hiding it
        self.assertEqual(len(CAND_Z) * 3, plan.gaps['faces:axis'])
        self.assertIn('faces:axis=15', '\n'.join(sc.report_lines(plan)))


class TestDeterminism(Repo):
    def test_r8_identical_bytes_on_rebuild(self):
        root = self.repo()
        plan = self.two_pass(root)
        first = sc.layer_bytes(plan)
        second = sc.layer_bytes(self.two_pass(root))
        self.assertEqual(first, second)
        sc.write_plan(root, plan)
        self.assertEqual(first, sc.rebuild_bytes(root))
        for path, data in first.items():
            self.assertEqual(data, (root / path).read_bytes())

    def test_rebuild_bytes_refuses_while_pieces_pending(self):
        root = self.repo()
        with self.assertRaises(sc.Refusal) as ctx:
            sc.rebuild_bytes(root)
        self.assertIn('pending', str(ctx.exception))

    def test_candidate_order_does_not_change_the_result(self):
        root = self.repo()
        plan = self.two_pass(root)
        path = root / 'config/sites/survey/candidates.json'
        doc = json.loads(path.read_text())
        doc['rows'].reverse()
        dump(path, doc)
        self.assertEqual(sc.layer_bytes(plan), sc.layer_bytes(self.two_pass(root)))


class TestRefusals(Repo):
    def refusal(self, root, **kw):
        with self.assertRaises(sc.Refusal) as ctx:
            sc.load_world(root, **kw)
        return ' | '.join(ctx.exception.reasons)

    def test_missing_survey_refuses_with_reason(self):
        text = self.refusal(self.repo(survey=False))
        self.assertIn('survey road samples missing', text)
        self.assertIn('survey cells missing', text)

    def test_missing_cells_refuses(self):
        root = self.repo()
        (root / 'config/sites/survey/cells.json').unlink()
        self.assertIn('survey cells missing', self.refusal(root))

    def test_missing_candidates_refuses(self):
        root = self.repo()
        (root / 'config/sites/survey/candidates.json').unlink()
        self.assertIn('candidates missing', self.refusal(root))

    def test_missing_stock_refuses(self):
        root = self.repo()
        (root / 'mission/mapgrouppos.xml').unlink()
        with mock.patch.object(sr, 'MISSION_DEFAULT', None):
            self.assertIn('mapgrouppos.xml not found', self.refusal(root, mission=root / 'nowhere'))

    def test_missing_road_graph_and_geometry_refuse(self):
        root = self.repo()
        (root / 'mission/hollow-country/ai/road-graph.compact.json').unlink()
        (root / 'config/sites/class-geometry.json').unlink()
        text = self.refusal(root)
        self.assertIn('road graph missing', text)
        self.assertIn('class geometry missing', text)

    def test_cli_refuses_with_exit_2_and_never_writes(self):
        root = self.repo(survey=False)
        with mock.patch('builtins.print') as shown:
            code = sc.main(['write', '--repo', str(root)])
        self.assertEqual(2, code)
        self.assertTrue(any('REFUSED' in str(c.args[0]) for c in shown.call_args_list))
        self.assertEqual([], list((root / 'config/map-overlays/layers').glob('*.json')))

    def test_write_refuses_while_pieces_pending(self):
        root = self.repo()
        plan = sc.compose(self.world(root))
        self.assertTrue(plan.pending)
        with self.assertRaises(sc.Refusal):
            sc.write_plan(root, plan)

    def test_never_bypassable_key_is_refused_by_the_cli(self):
        root = self.repo()
        with mock.patch('builtins.print'):
            self.assertEqual(2, sc.main(['plan', '--repo', str(root), '--accept-unmeasured', 'frame_view']))


class TestPendingPieces(Repo):
    def test_pieces_request_lists_exactly_the_hard_boxes(self):
        root = self.repo()
        plan = sc.compose(self.world(root))
        rows = sc.pieces_request(plan)
        hard = [o for r in plan.results for o in r.objects if map_overlay_hard(o['class'])]
        self.assertEqual(sorted(o['id'] for o in hard), sorted(r['id'] for r in rows))
        for row in rows:
            self.assertRegex(row['id'], r'^[A-Za-z0-9_.:\-]{1,64}$')
            self.assertTrue(0 < row['hx'] <= 60 and 0 < row['hz'] <= 60 and 0 < row['h'] <= 30)
            self.assertEqual(sorted(('id', 'x', 'z', 'yaw', 'hx', 'hz', 'h')), sorted(row))

    def test_pieces_cli_writes_the_request(self):
        root = self.repo()
        out = Path(self.tmp.name) / 'req.json'
        with mock.patch('builtins.print'):
            self.assertEqual(0, sc.main(['pieces', '--repo', str(root), '--out', str(out)]))
        self.assertTrue(json.loads(out.read_text()))


def map_overlay_hard(cls):
    return CLASSES[cls]['role'] not in sr.SOFT_ROLES


class TestRuleBindings(Repo):
    """For each of R1-R7 (and R6/MO): a site that passes and a site the composer rejects on that rule."""

    def only(self, a, **kw):
        root = self.repo(archetypes=[a], **kw)
        return root, self.two_pass(root)

    def test_r1_pass_and_fail(self):
        _root, plan = self.only(POST)
        self.assertEqual(len(CAND_Z), len(plan.results))
        tight = copy.deepcopy(POST)
        tight['location']['settlement_edge_m'] = [10, 100]
        _root, plan = self.only(tight)
        self.assertEqual([], plan.results)
        self.assertEqual({'R1'}, set(self.binding(plan)))

    def test_r1_own_predicate_no_vanilla_within(self):
        fuel = copy.deepcopy(POST)
        fuel['location']['no_vanilla_within_m'] = {'fuel_station': 300}
        stock = HOUSES + MILITARY + [('Land_FuelStation_Feed', 1040.0, 0.0, 480.0, 0.0)]
        _root, plan = self.only(fuel, stock=stock)
        self.assertEqual(len(CAND_Z) - 1, len(plan.results))
        bound = [r for r in plan.rows if r['binding']]
        self.assertEqual('R1', bound[0]['binding'])
        self.assertIn('vanilla fuel_station', bound[0]['text'])

    def test_r2_pass_and_fail(self):
        _root, plan = self.only(POST)
        self.assertEqual(len(CAND_Z), len(plan.results))
        narrow = copy.deepcopy(POST)
        narrow['parts'][0]['gap_m'] = 2.0
        _root, plan = self.only(narrow)
        self.assertEqual([], plan.results)
        self.assertEqual({'R2'}, set(self.binding(plan)))

    def test_r3_pass_and_fail(self):
        _root, plan = self.only(POST)
        self.assertEqual(len(CAND_Z), len(plan.results))
        blind = copy.deepcopy(POST)
        blind['parts'][4].pop('faces')
        blind['parts'][4].pop('of')
        _root, plan = self.only(blind)
        self.assertEqual([], plan.results)
        self.assertEqual({'R3'}, set(self.binding(plan)))

    def test_r4_pass_and_fail(self):
        _root, plan = self.only(POST)
        self.assertEqual(len(CAND_Z), len(plan.results))
        clash = copy.deepcopy(POST)
        clash['parts'][4].update(s=2.0, offset_m=14.0, faces='of')
        clash['parts'][4]['of'] = 'fire'
        _root, plan = self.only(clash)
        self.assertEqual([], plan.results)
        self.assertEqual({'R4'}, set(self.binding(plan)))

    def test_r4_scatter_zone_too_small(self):
        crowded = copy.deepcopy(POST)
        crowded['parts'][5].update(count=[14, 14], min_gap_m=4.0)
        _root, plan = self.only(crowded)
        self.assertEqual([], plan.results)
        self.assertEqual({'R4'}, set(self.binding(plan)))

    def test_r5_pass_and_fail(self):
        root = self.repo(archetypes=[POST])
        plan = self.two_pass(root)
        self.assertEqual(len(CAND_Z), len(plan.results))
        root2 = Path(tempfile.mkdtemp(dir=self.tmp.name))
        root2 = make_repo(root2, archetypes=[POST])
        plan = self.two_pass(root2, **{'tent': {'water': True}})
        self.assertEqual([], plan.results)
        self.assertEqual({'R5'}, set(self.binding(plan)))

    def test_r5_slope_and_spread(self):
        root = self.repo(archetypes=[POST])
        plan = self.two_pass(root, **{'tent': {'slope_pct': 7.5}})
        self.assertEqual([], plan.results)
        root = make_repo(Path(tempfile.mkdtemp(dir=self.tmp.name)), archetypes=[POST])
        plan = self.two_pass(root, **{'tent': {'corners_y': [0.0, 0.0, 0.0, 0.6]}})
        self.assertEqual({'R5'}, set(self.binding(plan)))

    def test_r6_spacing_cell_and_cap(self):
        root = self.repo(archetypes=[POST], cands=(500.0, 600.0, 1500.0, 1700.0))
        plan = self.two_pass(root)
        placed = sorted(round(r['z']) for r in plan.rows if r['placed'])
        self.assertEqual(2, len(placed))
        self.assertIn(placed[0], (500, 600))
        self.assertIn(placed[1], (1500, 1700))
        self.assertEqual({'R6'}, {r['binding'] for r in plan.rows if r['binding']})
        capped = copy.deepcopy(POST)
        capped['density']['max_per_map'] = 2
        _root, plan = self.only(capped)
        self.assertEqual(2, len(plan.results))
        self.assertEqual({'R6'}, {r['binding'] for r in plan.rows if r['binding']})
        self.assertEqual(3, plan.cap_blocked['roadpost'])

    def test_r6_min_same_m_binds_before_300(self):
        wide = copy.deepcopy(POST)
        wide['density']['min_same_m'] = 1200
        root = make_repo(Path(tempfile.mkdtemp(dir=self.tmp.name)), archetypes=[wide], cands=(500.0, 1500.0, 2500.0))
        plan = self.two_pass(root)
        self.assertEqual(2, len(plan.results))

    def test_r7_pass_and_fail(self):
        _root, plan = self.only(POST)
        self.assertEqual(len(CAND_Z), len(plan.results))
        for r in plan.results:
            proto = sum(1 for o in r.objects if o['loot'] == 'proto')
            self.assertTrue(1 <= proto <= sr.PROTO_ROWS[1], proto)
        lootless = copy.deepcopy(POST)
        lootless['parts'][0]['loot'] = 'none'
        _root, plan = self.only(lootless)
        self.assertEqual([], plan.results)
        self.assertEqual({'R7'}, set(self.binding(plan)))

    def test_mo_clearance_to_vanilla_rows(self):
        # a measured stock piece 9.5 m from a barrier: R4 (4 m for measured stock) passes, map_overlay (10 m) binds
        stock = HOUSES + MILITARY + [('T_Crate', 1013.0, 0.0, 508.0, 0.0)]
        _root, plan = self.only(POST, stock=stock, cands=(500.0,))
        self.assertEqual(['MO'], self.binding(plan))
        self.assertIn('map_overlay needs 10 m', plan.rows[0]['text'])

    def test_r8_no_sweep_or_first_fit_sources(self):
        _root, plan = self.only(POST)
        sources = {o['yaw_source'] for r in plan.results for o in r.objects}
        self.assertTrue(sources)
        self.assertFalse([s for s in sources if str(s).startswith(('sweep', 'first_fit'))])


class TestStaticBlocks(Repo):
    def test_calibration_pending_is_reported_not_skipped(self):
        root = self.repo(archetypes=[POST])
        geo = json.loads((root / 'config/sites/class-geometry.json').read_text())
        for name in ('T_Barrier', 'T_Nest'):
            geo['classes'][name].update(front_yaw_deg=None, front_source='calibration_pending')
        dump(root / 'config/sites/class-geometry.json', geo)
        plan = sc.compose(self.world(root))
        self.assertEqual([], plan.results)
        kind, why = plan.statics['roadpost'].blocked
        self.assertEqual('calibration_pending', kind)
        self.assertIn('T_Barrier', why)
        self.assertEqual({'calibration_pending'}, set(self.binding(plan)))
        lines = '\n'.join(sc.report_lines(plan))
        self.assertIn('not placeable: calibration_pending', lines)

    def test_unmeasured_key_blocks_unless_accepted(self):
        cover = copy.deepcopy(POST)
        cover['location']['cover_within_m'] = 30
        root = self.repo(archetypes=[cover])
        plan = sc.compose(self.world(root))
        self.assertEqual('unmeasured', plan.statics['roadpost'].blocked[0])
        self.assertEqual([], plan.results)
        plan = sc.compose(self.world(root), ['cover_within_m'])
        self.assertIsNone(plan.statics['roadpost'].blocked)
        self.assertTrue(plan.results)

    def test_view_and_fall_line_frames_are_never_placed(self):
        view = arch('watch', 'view', 'view_sector', [part('a', 'T_Nest', 'offroad', anchor=True, loot='proto',
                                                           side='center', s=0.0, offset_m=0.0)])
        plan = sc.compose(self.world(self.repo(archetypes=[view])))
        self.assertEqual('unmeasured', plan.statics['watch'].blocked[0])
        self.assertEqual([], plan.results)


class TestCountReport(Repo):
    def test_count_and_binding_rule_per_rejected_candidate(self):
        root = self.repo(archetypes=[POST], cands=(500.0, 600.0, 1500.0, 2500.0, 3500.0))
        plan = self.two_pass(root)
        lines = sc.report_lines(plan)
        self.assertIn('candidates=5 placed=4 rejected=1 pending_pieces=0', lines[0])
        self.assertIn('placed by archetype: roadpost=4', lines[1])
        self.assertIn('binding rule per rejected candidate: R6=1', lines[2])
        rejected = [r for r in plan.rows if not r['placed']]
        self.assertEqual(1, len(rejected))
        self.assertEqual('R6', rejected[0]['binding'])
        self.assertIn('spacing', rejected[0]['text'])

    def test_full_report_json_is_canonical(self):
        root = self.repo()
        plan = self.two_pass(root)
        report = sc.full_report(plan)
        self.assertEqual(len(CAND_Z), len(report['candidates']))
        self.assertEqual(sc.canon(report), sc.canon(sc.full_report(self.two_pass(root))))

    def test_plan_cli_prints_the_count_and_writes_the_report(self):
        root = self.repo()
        out = Path(self.tmp.name) / 'report.json'
        with mock.patch('builtins.print') as shown:
            self.assertEqual(0, sc.main(['plan', '--repo', str(root), '--report', str(out)]))
        first = str(shown.call_args_list[0].args[0])
        self.assertIn('candidates=5', first)
        self.assertEqual(5, len(json.loads(out.read_text())['candidates']))

    def test_report_never_prints_a_home_path(self):
        plan = self.two_pass(self.repo())
        text = '\n'.join(sc.report_lines(plan))
        self.assertNotIn('/home/', text)
        self.assertNotIn(self.tmp.name, text)


class TestZoneRetention(Repo):
    def test_old_zone_id_moves_to_the_nearest_new_site_and_others_retire(self):
        root = self.repo(archetypes=[POST], cands=(500.0, 2500.0))
        world = self.world(root)
        world.legacy = sc.Legacy(zones=[{'id': 'zone-a', 'role': 'outpost', 'pos': [ROAD_X + 100.0, 520.0]},
                                        {'id': 'zone-far', 'role': 'outpost', 'pos': [9000.0, 9000.0]}])
        plan = sc.compose(world)
        add_pieces(root, plan)
        world = self.world(root)
        world.legacy = sc.Legacy(zones=[{'id': 'zone-a', 'role': 'outpost', 'pos': [ROAD_X + 100.0, 520.0]},
                                        {'id': 'zone-far', 'role': 'outpost', 'pos': [9000.0, 9000.0]}])
        plan = sc.compose(world)
        kept = {z: s for z, s, _d in plan.kept}
        self.assertEqual(['zone-a'], list(kept))
        site = next(r.site for r in plan.results if r.site['id'] == kept['zone-a'])
        self.assertEqual('zone-a', site['zone_id'])
        self.assertEqual('outpost', site['zone_role'])
        self.assertLess(abs(site['frame']['origin'][2] - 520.0), 100.0)
        self.assertEqual(['zone-far'], [z['id'] for z in plan.retired])
        self.assertIn('retired=1', '\n'.join(sc.report_lines(plan)))
        self.assertIn('zone-far', '\n'.join(sc.report_lines(plan)))

    def test_zone_beyond_400_m_is_retired(self):
        root = self.repo(archetypes=[POST], cands=(500.0,))
        world = self.world(root)
        plan = sc.compose(world)
        add_pieces(root, plan)
        world = self.world(root)
        world.legacy = sc.Legacy(zones=[{'id': 'zone-b', 'role': 'outpost', 'pos': [ROAD_X, 500.0 + 450.0]}])
        plan = sc.compose(world)
        self.assertEqual([], plan.kept)
        self.assertEqual(['zone-b'], [z['id'] for z in plan.retired])


class TestMapOverlayEmission(unittest.TestCase):
    def layer(self):
        return {'kind': map_overlay.LAYER_KIND, 'id': 'composed-x', 'version': 1, 'status': 'runtime-unverified',
                'purpose': 'x', 'sites': [{'id': 's1', 'archetype': 'roadpost',
                                           'frame': {'kind': 'road', 'origin': [10.0, 0.0, 10.0],
                                                     'forward_yaw_deg': 0.0},
                                           'guard_slots': [{'part': 'nest', 'pos': [1.0, 0.0, 2.0],
                                                            'facing_deg': 0.0}] * 2}],
                'objects': [{'id': 's1-nest-1', 'class': 'T_Nest', 'pos': [10.0, 0.0, 10.0], 'yaw': 30.0,
                             'loot': 'none', 'site': 's1', 'part': 'nest', 'customString': 'hcsite:s1:nest',
                             'ypr': [30.0, 0.0, 0.0]}]}

    def errors(self, item):
        errs = []
        source = map_overlay.Source({'limits': {}}, {'classes': CLASSES}, [], None, None)
        map_overlay._validate_object('L', item, source, map_overlay.limits_of(source.profile), errs)
        return errs

    def test_custom_string_must_match_the_site_tag(self):
        item = self.layer()['objects'][0]
        self.assertEqual([], [e for e in self.errors(item) if 'customString' in e])
        item['customString'] = 'whatever'
        self.assertTrue([e for e in self.errors(item) if 'customString' in e])

    def test_ypr_needs_three_finite_numbers(self):
        item = self.layer()['objects'][0]
        item['ypr'] = [1.0, 2.0]
        self.assertTrue([e for e in self.errors(item) if 'ypr' in e])
        item['ypr'] = [1.0, 2.0, float('nan')]
        self.assertTrue([e for e in self.errors(item) if 'ypr' in e])

    def test_composed_site_is_recognised_and_positioned(self):
        site = self.layer()['sites'][0]
        self.assertTrue(map_overlay.is_composed(site))
        self.assertEqual([10.0, 0.0, 10.0], map_overlay.site_pos(site))
        self.assertEqual(2, len(map_overlay.site_slots(site)))
        self.assertFalse(map_overlay.is_composed({'id': 'x', 'composition': 'a', 'pos': [0, 0, 0]}))
        self.assertEqual([0, 0, 0], map_overlay.site_pos({'id': 'x', 'composition': 'a', 'pos': [0, 0, 0]}))

    def test_composed_site_frame_errors(self):
        errs = []
        site = self.layer()['sites'][0]
        site['frame']['kind'] = 'nowhere'
        map_overlay._validate_composed_site('w', site, errs)
        self.assertTrue(errs)

    def test_spawner_emits_ypr_and_custom_string_and_legacy_defaults(self):
        rows = json.loads(map_overlay._spawner([
            {'id': 'a', 'class': 'T_Nest', 'pos': [1.0, 0.0, 2.0], 'yaw': 400.0, 'customString': 'hcsite:s1:nest',
             'ypr': [40.0, 0.0, 0.0]},
            {'id': 'b', 'class': 'T_Nest', 'pos': [1.0, 0.0, 2.0], 'yaw': 370.0}]))['Objects']
        self.assertEqual('hcsite:s1:nest', rows[0]['customString'])
        self.assertEqual([40.0, 0.0, 0.0], rows[0]['ypr'])
        self.assertEqual('', rows[1]['customString'])
        self.assertEqual([10.0, 0.0, 0.0], rows[1]['ypr'])


class TestRealArchetypes(unittest.TestCase):
    def test_part_ids_are_valid_site_tag_parts(self):
        tag = re.compile(r'^[a-z][a-z0-9_]{0,31}$')
        for path in sorted((ROOT / 'config/sites/archetypes').glob('*.json')):
            if path.name == 'schema.json':
                continue
            doc = json.loads(path.read_text())
            self.assertRegex(path.stem[:1], r'[a-z]')
            for p in doc['parts']:
                self.assertRegex(p['id'], tag, '%s part %s' % (path.name, p['id']))

    def test_site_ids_fit_the_tag_for_every_archetype(self):
        class S:
            pass
        for path in sorted((ROOT / 'config/sites/archetypes').glob('*.json')):
            if path.name == 'schema.json':
                continue
            st = S()
            st.id = path.stem
            ident = sc.site_id_for(st, (1234.5, 6789.0))
            self.assertRegex(ident, map_overlay.SITE_ID)
            self.assertRegex('hcsite:%s:nest' % ident, map_overlay.SITE_TAG)


if __name__ == '__main__':
    unittest.main()
