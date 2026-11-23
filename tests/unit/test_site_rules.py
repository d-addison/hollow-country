"""Hand-made pass/fail sites for rules R0-R8 of tools.validate.site_rules (synthetic world, no model data)."""
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.validate import site_rules as sr


def box(sx, sz):
    return {'geometry_min_m': [-sx / 2, 0, -sz / 2], 'geometry_max_m': [sx / 2, 1, sz / 2],
            'footprint_m': [sx, sz]}


def klass(kind, role):
    return {'kind': kind, 'role': role, 'footprint_reserve_m': [2, 2]}


CLASSES = {
    'T_Barrier': klass('prop', 'barrier'), 'T_Nest': klass('prop', 'nest'), 'T_Tent': klass('tent', 'tent'),
    'T_Fireplace': klass('prop', 'scene dressing'), 'T_Crate': klass('container', 'container'),
    'T_Litter': klass('prop', 'scene dressing'), 'T_Chair': klass('prop', 'furnishing'),
    'T_Wreck': klass('wreck', 'wreck'),
}
GEOMETRY = {'classes': {
    'T_Barrier': {'bounds': box(4, 1), 'symmetric': False, 'front_yaw_deg': 0},
    'T_Nest': {'bounds': box(2, 2), 'symmetric': False, 'front_yaw_deg': 0},
    'T_Tent': {'bounds': box(4, 4), 'symmetric': False, 'front_yaw_deg': 0},
    'T_Fireplace': {'bounds': box(1, 1), 'symmetric': True},
    'T_Crate': {'bounds': box(2, 6), 'symmetric': False, 'front_yaw_deg': 0},
    'T_Litter': {'bounds': box(0.5, 0.5), 'symmetric': True},
    'T_Chair': {'bounds': box(0.5, 0.5), 'symmetric': False, 'front_yaw_deg': 0},
    'T_Wreck': {'bounds': box(2, 5), 'symmetric': False, 'front_yaw_deg': 0},
}}


def part(pid, cls, op, **kw):
    row = {'id': pid, 'class': cls, 'op': op, 'loot': 'none', 'count': 1}
    row.update(kw)
    return row


ROADPOST = {
    'kind': 'hollow-country-site-archetype', 'id': 'roadpost', 'story': 'A post on the road.',
    'frame': {'kind': 'road', 'forward': 'road'},
    'location': {'road': {'surface': ['asphalt'], 'straight_m': 100, 'max_turn_deg': 10, 'max_grade_pct': 8},
                 'junction_m': [30, 5000], 'not_in': ['military', 'town_core'], 'slope_pct_max': 8},
    'parts': [
        part('barrier', 'T_Barrier', 'across_lane', anchor=True, loot='proto', gap_m=4.5),
        part('nest', 'T_Nest', 'shoulder', side='right', faces='forward', guard_post=True),
        part('tent', 'T_Tent', 'offroad', side='right', faces='of', of='fire'),
        part('fire', 'T_Fireplace', 'offroad', side='right'),
        part('crate', 'T_Crate', 'offroad', side='right'),
        part('litter', 'T_Litter', 'scatter', count=[0, 3], zone='camp', min_gap_m=2.0, optional=True),
    ],
    'density': {'max_per_map': 5, 'min_same_m': 400, 'min_any_m': 300},
}
CAMP = {
    'kind': 'hollow-country-site-archetype', 'id': 'camp', 'story': 'A camp off the road.',
    'frame': {'kind': 'approach', 'forward': 'road'}, 'location': {},
    'parts': [part('crate', 'T_Crate', 'offroad', anchor=True, loot='proto'),
              part('seats', 'T_Chair', 'row', count=3, faces='forward', spacing_m=1.5)],
    'density': {'max_per_map': 5, 'min_same_m': 400, 'min_any_m': 300},
}


def obj(site, pid, cls, x, z, yaw=0.0, loot='none', n=1, source='road'):
    return {'id': '%s-%s-%d' % (site, pid, n), 'class': cls, 'pos': [x, 0.0, z], 'yaw': yaw, 'loot': loot,
            'site': site, 'part': pid, 'customString': 'hcsite:%s:%s' % (site, pid), 'yaw_source': source}


def road_layer(site='c001', cz=100.0):
    entry = {'id': site, 'archetype': 'roadpost',
             'frame': {'kind': 'road', 'origin': [1000.0, 0.0, cz], 'forward_yaw_deg': 0.0},
             'protected_bearing_deg': 180.0, 'zones': {'camp': {'centre': [1032.0, cz + 12], 'radius_m': 6.0}},
             'guard_slots': [{'part': 'nest', 'pos': [1006.0, 0.0, cz - 0.5], 'facing_deg': 0.0}]}
    objects = [obj(site, 'barrier', 'T_Barrier', 997.0, cz, loot='proto'),
               obj(site, 'nest', 'T_Nest', 1006.0, cz),
               obj(site, 'tent', 'T_Tent', 1030.0, cz),
               obj(site, 'fire', 'T_Fireplace', 1030.0, cz + 8),
               obj(site, 'crate', 'T_Crate', 1040.0, cz - 10)]
    return {'kind': 'hollow-country-map-overlay', 'sites': [entry], 'objects': objects}


def survey_for(layer, extra=None):
    pieces = {o['id']: {'corners_y': [0.0, 0.05, 0.1, 0.0], 'center_y': 0.0, 'slope_pct': 2.0, 'water': False,
                        'collides': False}
              for o in layer['objects'] if o['class'] != 'T_Litter'}
    pieces.update(extra or {})
    return {'kind': 'hollow-country-site-survey', 'version': 1, 'road_samples': [[1000.0, 100.0, 'asphalt']],
            'cells': {'size_m': 8, 'samples': [[1000.0, 100.0, 2.0, 0]]}, 'pieces': pieces}


def road_graph():
    nodes = [(1000.0, 0.0, 20.0 * k) for k in range(21)] + [(1020.0, 0.0, 200.0), (1040.0, 0.0, 200.0)]
    links = [[] for _ in nodes]

    def link(a, b):
        links[a].append(b)
        links[b].append(a)
    for k in range(20):
        link(k, k + 1)
    link(10, 21)
    link(21, 22)
    return sr.RoadGraph(nodes, links)


def inputs(layer, survey=True, stock=(('T_House', 1600.0, 0.0, 1600.0, 0.0),), archetypes=None, **kw):
    arch = archetypes if archetypes is not None else {'roadpost': ROADPOST, 'camp': CAMP}
    surv = sr.Survey([survey_for(layer)]) if survey is True else survey
    classes = dict(CLASSES)
    return sr.Inputs(road_graph(), classes, sr.parse_geometry(GEOMETRY, classes), arch, surv,
                     list(stock) if stock is not None else None, **kw)


def rules(layer, **kw):
    inp = kw.pop('inp', None) or inputs(layer, **kw)
    out = sr.run(inp, sr.composed_sites(layer))
    got = {}
    for site, rule, text in out.rows:
        got.setdefault(rule, []).append((site, text))
    return got


def texts(got, rule):
    return ' | '.join(t for _s, t in got.get(rule, []))


class SiteCase(unittest.TestCase):
    def base(self):
        return copy.deepcopy(road_layer())

    def find(self, layer, objid):
        return next(o for o in layer['objects'] if o['id'] == objid)

    def assertFails(self, got, rule, fragment=''):
        self.assertIn(rule, got, 'expected %s to fail; got %s' % (rule, sorted(got)))
        self.assertIn(fragment, texts(got, rule))


class TestPassingSite(SiteCase):
    def test_baseline_is_clean(self):
        self.assertEqual({}, rules(self.base()))

    def test_camp_row_is_clean(self):
        layer = {'sites': [{'id': 'k1', 'archetype': 'camp', 'frame': {'kind': 'approach',
                                                                      'origin': [1050.0, 0.0, 100.0],
                                                                      'forward_yaw_deg': 0.0}}],
                 'objects': [obj('k1', 'crate', 'T_Crate', 1080.0, 100.0, loot='proto')] +
                            [obj('k1', 'seats', 'T_Chair', 1050.0 + 1.5 * k, 100.0, n=k) for k in range(3)]}
        got = rules(layer, survey=sr.Survey([survey_for(layer)]))
        self.assertEqual({}, got)


class TestR0Contract(SiteCase):
    def test_unknown_archetype_fails(self):
        layer = self.base()
        layer['sites'][0]['archetype'] = 'nope'
        self.assertFails(rules(layer), 'R0', 'nope')

    def test_bad_frame_fails(self):
        layer = self.base()
        layer['sites'][0]['frame'] = {'kind': 'sideways', 'origin': [1, 2]}
        got = rules(layer)
        self.assertFails(got, 'R0', 'frame.origin')
        self.assertIn('frame.kind', texts(got, 'R0'))

    def test_object_for_undeclared_site_fails(self):
        layer = self.base()
        layer['objects'].append(obj('ghost', 'nest', 'T_Nest', 5.0, 5.0))
        self.assertFails(rules(layer), 'R0', 'undeclared site')

    def test_missing_road_graph_fails_run(self):
        layer = self.base()
        inp = inputs(layer)
        inp.roads = None
        got = rules(layer, inp=inp)
        self.assertFails(got, 'R0', 'road graph')
        self.assertFails(got, 'R2', 'road graph')

    def test_missing_geometry_fails(self):
        layer = self.base()
        inp = inputs(layer)
        inp.geometry = None
        self.assertFails(rules(layer, inp=inp), 'R0', 'class geometry')


class TestR1Location(SiteCase):
    def with_loc(self, **loc):
        arch = copy.deepcopy(ROADPOST)
        arch['location'] = loc
        return rules(self.base(), archetypes={'roadpost': arch})

    def test_junction_too_close_fails(self):
        self.assertFails(self.with_loc(junction_m=[150, 5000]), 'R1', 'junction')

    def test_wrong_surface_fails(self):
        self.assertFails(self.with_loc(road={'surface': ['dirt']}), 'R1', 'surface')

    def test_missing_surface_survey_fails(self):
        layer = self.base()
        surv = survey_for(layer)
        surv['road_samples'] = []
        got = rules(layer, survey=sr.Survey([surv]), archetypes={'roadpost': ROADPOST})
        self.assertFails(got, 'R1', 'surface unknown')

    def test_bend_inside_window_fails(self):
        self.assertFails(self.with_loc(road={'straight_m': 500}), 'R1', 'straight run')

    def test_unsupported_predicate_fails(self):
        self.assertFails(self.with_loc(cliff_m=4), 'R1', 'unsupported')

    def test_settlement_predicate_needs_stock(self):
        arch = copy.deepcopy(ROADPOST)
        arch['location'] = {'not_in': ['town_core']}
        self.assertFails(rules(self.base(), stock=None, archetypes={'roadpost': arch}), 'R1', 'stock')

    def test_military_area_fails(self):
        layer = self.base()
        stock = (('Land_Mil_Barracks', 1010.0, 0.0, 100.0, 0.0),)
        self.assertFails(rules(layer, stock=stock), 'R1', 'military')

    def test_slope_fails(self):
        layer = self.base()
        surv = survey_for(layer)
        surv['cells']['samples'] = [[1000.0, 100.0, 14.0, 0]]
        self.assertFails(rules(layer, survey=sr.Survey([surv])), 'R1', 'slope')

    def test_legacy_site_has_no_intent(self):
        site = sr.Site('x', 'checkpoint', [0, 0, 0], 0.0, 'road', [], legacy=True)
        out = sr.Findings()
        sr.Checker(inputs(self.base())).r1(site, out)
        self.assertEqual('R1', out.rows[0][1])


class TestR2Road(SiteCase):
    def test_origin_off_road_fails(self):
        layer = self.base()
        layer['sites'][0]['frame']['origin'][0] = 1008.0
        self.assertFails(rules(layer), 'R2', 'centreline')

    def test_axis_off_tangent_fails(self):
        layer = self.base()
        layer['sites'][0]['frame']['forward_yaw_deg'] = 35.0
        self.assertFails(rules(layer), 'R2', 'off the road tangent')

    def test_blocked_lane_fails_unless_blocking(self):
        layer = self.base()
        layer['objects'].append(obj('c001', 'barrier', 'T_Barrier', 1001.0, 100.0, n=2))
        self.assertFails(rules(layer), 'R2', 'passable lane')
        arch = copy.deepcopy(ROADPOST)
        arch['blocking'] = True
        self.assertNotIn('passable lane', texts(rules(layer, archetypes={'roadpost': arch}), 'R2'))

    def test_nest_too_far_for_shoulder_fails(self):
        layer = self.base()
        self.find(layer, 'c001-nest-1')['pos'][0] = 1016.0
        self.assertFails(rules(layer), 'R2', 'beyond the road edge')

    def test_nest_on_wrong_side_fails(self):
        layer = self.base()
        self.find(layer, 'c001-nest-1')['pos'][0] = 994.0
        self.assertFails(rules(layer), 'R2', 'not on the right')

    def test_tent_near_road_fails(self):
        layer = self.base()
        self.find(layer, 'c001-tent-1')['pos'][0] = 1006.0
        self.assertFails(rules(layer), 'R2', 'offroad needs')

    def test_non_road_site_hard_piece_clear_of_road(self):
        for x, expect in ((1040.0, False), (1004.0, True)):
            layer = {'sites': [{'id': 'k1', 'archetype': 'camp', 'frame': {'kind': 'approach',
                                                                          'origin': [x, 0.0, 100.0],
                                                                          'forward_yaw_deg': 0.0}}],
                     'objects': [obj('k1', 'crate', 'T_Crate', x, 100.0, loot='proto')] +
                                [obj('k1', 'seats', 'T_Chair', x + 20 + 1.5 * k, 100.0, n=k) for k in range(3)]}
            got = rules(layer, survey=sr.Survey([survey_for(layer)]))
            self.assertEqual(expect, 'R2' in got, texts(got, 'R2'))


class TestR3Facing(SiteCase):
    def test_nest_off_target_fails(self):
        layer = self.base()
        self.find(layer, 'c001-nest-1')['yaw'] = 40.0
        self.assertFails(rules(layer), 'R3', 'off its forward target')

    def test_nest_within_defensive_tolerance_passes(self):
        layer = self.base()
        self.find(layer, 'c001-nest-1')['yaw'] = 18.0
        self.assertNotIn('R3', rules(layer))

    def test_tent_social_tolerance_is_tighter(self):
        layer = self.base()
        self.find(layer, 'c001-tent-1')['yaw'] = 18.0
        self.assertFails(rules(layer), 'R3', 'c001-tent-1')

    def test_defensive_piece_facing_protected_side_fails(self):
        layer = self.base()
        layer['sites'][0]['protected_bearing_deg'] = 0.0
        self.assertFails(rules(layer), 'R3', 'protected side')

    def test_barrier_not_across_road_fails(self):
        layer = self.base()
        self.find(layer, 'c001-barrier-1')['yaw'] = 40.0
        self.assertFails(rules(layer), 'R3', 'perpendicular')

    def test_row_spacing_and_yaw(self):
        def camp(mut):
            layer = {'sites': [{'id': 'k1', 'archetype': 'camp', 'frame': {'kind': 'approach',
                                                                          'origin': [1050.0, 0.0, 100.0],
                                                                          'forward_yaw_deg': 0.0}}],
                     'objects': [obj('k1', 'crate', 'T_Crate', 1080.0, 100.0, loot='proto')] +
                                [obj('k1', 'seats', 'T_Chair', 1050.0 + 1.5 * k, 100.0, n=k) for k in range(3)]}
            mut(layer)
            return rules(layer, survey=sr.Survey([survey_for(layer)]))
        self.assertFails(camp(lambda l: l['objects'][2]['pos'].__setitem__(0, 1052.3)), 'R3', 'spacing')
        self.assertFails(camp(lambda l: l['objects'][2].__setitem__('yaw', 25.0)), 'R3', 'yaws differ')

    def test_pending_front_fails_directional_class(self):
        layer = self.base()
        inp = inputs(layer)
        inp.geometry['T_Nest'].front = None
        self.assertFails(rules(layer, inp=inp), 'R3', 'front_yaw_deg')


class TestR4Clearance(SiteCase):
    def test_overlap_fails(self):
        layer = self.base()
        self.find(layer, 'c001-nest-1')['pos'][:3:2] = [998.0, 100.0]
        self.assertFails(rules(layer), 'R4', 'apart')

    def test_hard_pieces_need_one_metre_apron(self):
        layer = self.base()
        layer['objects'].append(obj('c001', 'barrier', 'T_Barrier', 1006.0, 101.9, n=9))
        self.assertFails(rules(layer), 'R4', 'c001-barrier-9')

    def test_stock_building_clearance(self):
        layer = self.base()
        stock = (('Land_Unmeasured', 1030.0, 0.0, 110.0, 0.0),)
        self.assertFails(rules(layer, stock=stock), 'R4', 'Land_Unmeasured')

    def test_measured_stock_building_needs_four_metres(self):
        layer = self.base()
        inp = inputs(layer, stock=(('T_Shed', 1030.0, 0.0, 111.0, 0.0),))
        inp.geometry['T_Shed'] = sr.Geo(0, 0, 6, 6)
        self.assertFails(rules(layer, inp=inp), 'R4', 'T_Shed')

    def test_door_apron_blocked_fails(self):
        layer = self.base()
        crate = self.find(layer, 'c001-crate-1')
        layer['objects'].append(obj('c001', 'litter', 'T_Litter', crate['pos'][0], crate['pos'][2] + 4.0, n=1))
        got = rules(layer)
        self.assertFails(got, 'R4', 'door apron')

    def test_fire_too_near_canvas_fails(self):
        layer = self.base()
        self.find(layer, 'c001-fire-1')['pos'][2] = 104.0
        self.assertFails(rules(layer), 'R4', 'canvas')

    def test_unmeasured_class_fails(self):
        layer = self.base()
        inp = inputs(layer)
        del inp.geometry['T_Nest']
        self.assertFails(rules(layer, inp=inp), 'R4', 'no measured geometry')

    def test_survey_collision_fails(self):
        layer = self.base()
        surv = survey_for(layer)
        surv['pieces']['c001-tent-1']['collides'] = True
        self.assertFails(rules(layer, survey=sr.Survey([surv])), 'R4', 'collision')

    def test_litter_zone_and_gap(self):
        layer = self.base()
        layer['objects'] += [obj('c001', 'litter', 'T_Litter', 1032.0, 112.0, n=1),
                             obj('c001', 'litter', 'T_Litter', 1032.5, 112.0, n=2),
                             obj('c001', 'litter', 'T_Litter', 1090.0, 112.0, n=3)]
        got = rules(layer)
        self.assertFails(got, 'R4', 'closer than')
        self.assertIn('outside zone', texts(got, 'R4'))


class TestR5Ground(SiteCase):
    def spread(self, objid, spread, **extra):
        layer = self.base()
        surv = survey_for(layer)
        surv['pieces'][objid]['corners_y'] = [0.0, spread, 0.0, 0.0]
        surv['pieces'][objid].update(extra)
        return rules(layer, survey=sr.Survey([surv]))

    def test_tent_spread_limit_is_tight(self):
        self.assertFails(self.spread('c001-tent-1', 0.5), 'R5', 'spread')
        self.assertNotIn('R5', self.spread('c001-tent-1', 0.3))

    def test_nest_spread_limit_is_loose(self):
        self.assertNotIn('R5', self.spread('c001-nest-1', 0.5))
        self.assertFails(self.spread('c001-nest-1', 0.7), 'R5', 'spread')

    def test_water_fails(self):
        self.assertFails(self.spread('c001-tent-1', 0.1, water=True), 'R5', 'water')

    def test_tent_slope_cap_fails(self):
        self.assertFails(self.spread('c001-tent-1', 0.1, slope_pct=7.5), 'R5', 'slope')

    def test_missing_piece_entry_fails(self):
        layer = self.base()
        surv = survey_for(layer)
        del surv['pieces']['c001-crate-1']
        self.assertFails(rules(layer, survey=sr.Survey([surv])), 'R5', 'no survey entry')

    def test_missing_survey_fails_never_skipped(self):
        self.assertFails(rules(self.base(), survey=None), 'R5', 'survey missing')


class TestR6Density(SiteCase):
    def two(self, dx, dz):
        a, b = road_layer('c001', 100.0), road_layer('c002', 100.0)
        b['sites'][0]['frame']['origin'][0] += dx
        b['sites'][0]['frame']['origin'][2] += dz
        return {'sites': a['sites'] + b['sites'], 'objects': a['objects'] + b['objects']}

    def test_close_sites_fail(self):
        layer = self.two(0.0, 120.0)
        self.assertFails(rules(layer, survey=None), 'R6', 'sites need')

    def test_same_archetype_spacing_uses_declared_minimum(self):
        got = rules(self.two(0.0, 350.0), survey=None)
        self.assertIn('same', texts(got, 'R6'))

    def test_one_per_km_cell_fails(self):
        got = rules(self.two(0.0, 450.0), survey=None)
        self.assertIn('1 km cell', texts(got, 'R6'))

    def test_far_sites_pass_density(self):
        self.assertNotIn('R6', rules(self.two(0.0, 1500.0), survey=None))

    def test_totals_are_capped(self):
        layer = self.two(0.0, 1500.0)
        for name, value in (('MAX_SITES', 1), ('MAX_OBJECTS', 3), ('MAX_ROWS', 1)):
            with mock.patch.object(sr, name, value):
                self.assertFails(rules(layer, survey=None), 'R6', 'exceed the cap')

    def test_max_per_map_fails(self):
        arch = copy.deepcopy(ROADPOST)
        arch['density']['max_per_map'] = 1
        self.assertFails(rules(self.two(0.0, 1500.0), survey=None, archetypes={'roadpost': arch}), 'R6',
                         'allows 1')


class TestR7Story(SiteCase):
    def test_loot_on_non_anchor_fails(self):
        layer = self.base()
        self.find(layer, 'c001-nest-1')['loot'] = 'proto'
        self.assertFails(rules(layer), 'R7', 'neither anchor')

    def test_proto_rows_bounded(self):
        layer = self.base()
        self.find(layer, 'c001-barrier-1')['loot'] = 'none'
        self.assertFails(rules(layer), 'R7', '0 proto loot rows')
        layer = self.base()
        for pid in ('nest', 'tent', 'fire', 'crate'):
            self.find(layer, 'c001-%s-1' % pid)['loot'] = 'proto'
        self.assertFails(rules(layer), 'R7', '5 proto loot rows')

    def test_missing_part_fails(self):
        layer = self.base()
        layer['objects'] = [o for o in layer['objects'] if o['part'] != 'tent']
        self.assertFails(rules(layer), 'R7', 'part tent has 0')

    def test_undeclared_part_and_class_fail(self):
        layer = self.base()
        self.find(layer, 'c001-nest-1')['class'] = 'T_Wreck'
        layer['objects'].append(obj('c001', 'mystery', 'T_Litter', 1032.0, 112.0))
        got = rules(layer)
        self.assertIn('not allowed for part nest', texts(got, 'R7'))
        self.assertIn('does not declare', texts(got, 'R7'))

    def test_forbidden_role_fails(self):
        arch = copy.deepcopy(ROADPOST)
        arch['forbidden_roles'] = ['tent']
        self.assertFails(rules(self.base(), archetypes={'roadpost': arch}), 'R7', "role 'tent'")

    def test_scatter_may_not_be_hard(self):
        layer = self.base()
        arch = copy.deepcopy(ROADPOST)
        arch['parts'][-1]['class'] = 'T_Wreck'
        layer['objects'].append(obj('c001', 'litter', 'T_Wreck', 1032.0, 112.0))
        self.assertFails(rules(layer, archetypes={'roadpost': arch}), 'R7', 'scatter litter')

    def test_guard_slot_missing_fails(self):
        layer = self.base()
        layer['sites'][0]['guard_slots'] = []
        self.assertFails(rules(layer), 'R7', 'no guard slot')

    def test_guard_slot_must_face_target_and_sit_behind_front(self):
        layer = self.base()
        layer['sites'][0]['guard_slots'][0]['facing_deg'] = 90.0
        self.assertFails(rules(layer), 'R7', 'off its target')
        layer = self.base()
        layer['sites'][0]['guard_slots'][0]['pos'][2] += 1.4
        self.assertFails(rules(layer), 'R7', 'from the front face')

    def test_archetype_lint(self):
        arch = copy.deepcopy(ROADPOST)
        arch['parts'].append(part('bad', 'T_Nest', 'teleport'))
        arch['parts'].append(part('ghost', 'Not_In_Classes', 'offroad'))
        arch['story'] = ''
        out = sr.Findings()
        sr.check_archetypes(inputs(self.base(), archetypes={'roadpost': arch}), out)
        text = ' | '.join(t for _s, _r, t in out.rows)
        self.assertIn('closed set', text)
        self.assertIn('not in classes.json', text)
        self.assertIn('missing story', text)


class TestR8Determinism(SiteCase):
    def test_sweep_yaw_fails(self):
        layer = self.base()
        self.find(layer, 'c001-nest-1')['yaw_source'] = 'sweep-15'
        self.assertFails(rules(layer), 'R8', 'sweep')

    def test_missing_yaw_source_fails(self):
        layer = self.base()
        del self.find(layer, 'c001-nest-1')['yaw_source']
        self.assertFails(rules(layer), 'R8', 'no yaw_source')

    def test_rebuild_must_match_committed_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rel = 'config/map-overlays/layers/composed-x.json'
            (root / rel).parent.mkdir(parents=True)
            (root / rel).write_bytes(b'{"a": 1}\n')
            inp = sr.Inputs(composed_files=[root / rel])
            for hook, ok in ((lambda r: {rel: b'{"a": 1}\n'}, True), (lambda r: {rel: b'{"a": 2}\n'}, False),
                             (lambda r: {}, False), (None, False)):
                inp.rebuild = hook
                out = sr.Findings()
                sr.check_rebuild(inp, root, out)
                self.assertEqual(ok, not out.rows, out.rows)

    def test_legacy_sweep_heading_fails(self):
        out = sr.Findings()
        for heading, fails in ((60.0, True), (61.0, False)):
            site = sr.Site('x', 'checkpoint', [0, 0, 0], heading, 'road', [], legacy=True)
            site.extra['heading'] = heading
            before = len(out.rows)
            sr.Checker(inputs(self.base())).r8(site, out)
            self.assertEqual(fails, len(out.rows) > before)


class TestRunModes(SiteCase):
    def make_root(self, tmp, enabled):
        root = Path(tmp)
        (root / 'config/map-overlays/layers').mkdir(parents=True)
        (root / 'config/map-overlays/classes.json').write_text(json.dumps({'classes': CLASSES}))
        (root / 'config/map-overlays/profile.json').write_text(json.dumps({'enabled': enabled}))
        road = root / 'mission/hollow-country/ai'
        road.mkdir(parents=True)
        (road / 'road-graph.compact.json').write_text(json.dumps(
            {'NodeCount': 2, 'Positions': [0, 0, 0, 0, 0, 10], 'Offsets': [0, 1, 2], 'Edges': [1, 0]}))
        return root

    def test_no_composed_layers_passes_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = io.StringIO()
            self.assertEqual(0, sr.gate(self.make_root(tmp, []), Path(tmp), 3, stream))
            self.assertIn('composed_layers=0', stream.getvalue())

    def test_profile_enabled_layer_without_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = io.StringIO()
            self.assertEqual(1, sr.gate(self.make_root(tmp, ['composed-sites']), Path(tmp), 3, stream))
            self.assertIn('composed-sites', stream.getvalue())

    def test_findings_are_summarised(self):
        layer = self.base()
        self.find(layer, 'c001-nest-1')['yaw'] = 40.0
        inp = inputs(layer)
        out = sr.run(inp, sr.composed_sites(layer))
        lines = sr.format_findings(out, 3)
        self.assertTrue(any(l.startswith('FAIL c001 R3 ') for l in lines))
        self.assertIn('failing=1', sr.summary_line(out, sr.composed_sites(layer), 'x'))


if __name__ == '__main__':
    unittest.main()
