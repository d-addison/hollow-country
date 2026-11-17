"""Read-only review probes; all geometry below is synthetic, never engine evidence."""
import copy
import json
import sys
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.setup import interior_sampler as sampler, ce_probe
from tools.audit import interior_points as points
from tests.unit import test_interior_points as fixtures
from tests.unit import test_interior_sampler as model
from review_fixtures import room_without_filtered_mesh

cache = Path('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289')
types = ce_probe.native_type_names(cache)
hook = model.default_hook()
print('Native type names:', len(types))
print('Generated hook lint:', sampler.lint_sampler_hook(hook, native_types=types))

stock = Path('/mnt/d/HollowCountryLocal/vanilla-p0-001/stock-backup/mpmissions/dayzOffline.chernarusplus/mapgroupproto.xml').read_bytes()
root = ET.fromstring(stock)
for name in (*points.TENEMENT_CLASSES, *points.CALIBRATION_CLASSES):
    group = next(g for g in root.iter('group') if g.get('name') == name)
    print('Stock:', name, 'lootmax', group.get('lootmax'), 'containers',
          [(c.get('name'), c.get('lootmax'), len(c.findall('point'))) for c in group.findall('container')])
print('Stock point attribute sets:', Counter(tuple(sorted(p.attrib)) for p in root.iter('point')))
selection = {n: [{'x': 0.5, 'y': 0.0, 'z': 0.5}] for n in points.TENEMENT_CLASSES}
treatment = points.write_treatment(stock, selection)
print('Actual stock treatment parses:', ET.fromstring(treatment).tag)
print('Actual stock bytes outside tenements equal:', points._outside_groups(stock, selection) == points._outside_groups(treatment, selection))

document = fixtures.full_census()
_, report = points.build_treatment(fixtures.encode(document), fixtures.STOCK, 0.4)
print('Untested reachability treatment:', [(n, c['reachability_mode'], c['selected']) for n, c in report['classes'].items()])

document = fixtures.full_census()
for row in document['placements']:
    if row['class'] in points.CALIBRATION_CLASSES:
        for hit in row['hits']:
            hit[1] += 100
_, report = points.build_treatment(fixtures.encode(document), fixtures.STOCK, 0.4)
print('Calibration floors shifted +100m still pass:', report['calibration']['passed'],
      [(n, c['xz_coverage'], c['v3_coverage']) for n, c in report['calibration']['classes'].items()])
stock_with_extra_covered_point = fixtures.STOCK.replace(b'-4.5 0.0 3.5', b'-4.5 0.0 -3.5')
_, report = points.build_treatment(fixtures.encode(document), stock_with_extra_covered_point, 0.6)
print('Same vertical failure at default threshold 0.6:', report['calibration']['passed'],
      [(n, c['xz_coverage'], c['v3_coverage']) for n, c in report['calibration']['classes'].items()])

rows = fixtures.four_placements('Land_Tenement_Small')
for i, row in enumerate(rows):
    for hit in row['hits']:
        hit[5] = 1 if i == 0 else -1
candidates = fixtures.candidates_of(rows)
accepted = points.eligible(candidates['candidates'], candidates['reach_mode'], 0.75)
print('One reachable + three unknown placements:', len(accepted), 'eligible; first reach counts:', accepted[0]['reach'])

building, nav, floor, nearest = room_without_filtered_mesh()
run = model.HookRun(hook, building, model.storey_planes(building), nav=nav).run()
print('Disconnected room without snap reach code:', run.model.HCProbeReachHit(floor))
original_sample = nav.sample
def snapped_sample(position, radius):
    if position == floor:
        return True, nearest
    return original_sample(position, radius)
# The transpiled call resolves this global, matching the native out-parameter result.
run.model.HCProbeSampleMesh.__globals__['HCMockSample'] = snapped_sample
print('Same disconnected room snapped 1m across wall reach code:', run.model.HCProbeReachHit(floor))

wide = model.SampBuilding('Land_Tenement_Big', (3000.0, 20.0, 5000.0),
                          clip=((-20.0, -1.0, -20.0), (20.0, 5.0, 20.0)))
wide.doors = [wide.to_world((5.0, 0.0, 0.0))]
planes = [model.Plane(wide, 0, -20, 20, -20, 20, 'floor'),
          model.Plane(wide, 3, -20, 20, -20, 20, 'roof')]
isolated = model.NavMesh(wide, [model.Zone('isolated-interior', -20, 20, -20, 20, 0.0)])
interior_control = model.HookRun(hook, wide, planes, nav=isolated).run()
print('Interior-door control with NO exterior mesh:', interior_control.row()['reach'],
      'reach code', interior_control.model.HCProbeReachHit(wide.to_world((0.5, 0, 0.5))))

baseline = fixtures.candidates_of(fixtures.four_placements('Land_Tenement_Small'))
rows = fixtures.four_placements('Land_Tenement_Small')
for row in rows:
    row['hits'] += [[-0.5, y, -0.5, 2.8, 1, 1] for y in (0.5, 1, 1.5, 2, 2.5)]
bridged = fixtures.candidates_of(rows)
print('Storeys before/after staircase heights:', sorted({c['storey'] for c in baseline['candidates']}), sorted({c['storey'] for c in bridged['candidates']}))

zero = model.HookRun(model.default_hook(path_limit=0), building, model.storey_planes(building), nav=model.nav_for(building)).run()
print('path_limit=0 actual path calls:', zero.nav.paths)

# Both floor heights in this cell exist in both placements, but opposing clearance
# differences cause the reducer to choose a different physical level in each.
rows = []
for i in range(4):
    lower_clear, upper_clear = ((3.0, 2.8) if i % 2 == 0 else (2.8, 3.0))
    hits = fixtures.cells(0.0, fixtures.XS0, fixtures.ZS, clearance=lower_clear, reach=1)
    hits += fixtures.cells(3.0, fixtures.XS0, fixtures.ZS, clearance=upper_clear, reach=1)
    hits += [[-0.5, y, -0.5, 2.8, 1, 1] for y in (0.5, 1, 1.5, 2, 2.5)]
    rows.append(fixtures.placement('Land_Tenement_Small', hits, index=i))
merged = fixtures.candidates_of(rows)
accepted = points.eligible(merged['candidates'], merged['reach_mode'], 0.75)
print('Merged-storey eligible heights where only y=0 and y=3 floors exist:', sorted({c['y'] for c in accepted if c['x'] < -1.0}))
document = fixtures.census(rows + fixtures.four_placements('Land_Tenement_Big')
                          + fixtures.four_placements('Land_HouseBlock_2F1', role='calibration'))
_, report = points.build_treatment(fixtures.encode(document), fixtures.STOCK, 0.4)
print('End-to-end tenement treatment selects phantom heights:',
      sorted({p['y'] for p in report['classes']['Land_Tenement_Small']['points']}))
