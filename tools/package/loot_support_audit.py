"""Collision-only support/enclosure gate for HC CE points; native acceptance pending.

Installed PBOs and the hash-pinned ODOL reader are read-only inputs. No visual
triangles or optional runtime furniture can supply support, roofs or walls.
Run with --fix to prune failing points and align their source arrays. Never
moves a point: an uncertain surface is removed rather than guessed.
"""
import argparse
from collections import Counter
import copy
import io
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from tools.audit import pbo_config as pbo
from tools.package import interior_points_gen as gen, loot_boost as loot
from tools.package.loot_floor_policy import validate_collision_support as validate_policy
from tools.package.loot_reach_audit import (
    Scene, collision_triangles, cross, dot, intersection, lod_for, model_point, subtract,
)

proxy_table = gen.proxy_table

ROOT = Path(__file__).resolve().parents[2]
# ODOL resolution identifiers, compared tolerantly because stored as float32.
COLLISION = (('geometry', 1e13), ('roadway', 3e15), ('view-geometry', 6e15))
# View Geometry (6e15) is the AI visibility/occlusion LOD. Its tops coincide
# with authored solids (baked counters, building slabs), so it may still carry
# an item, but its boxes are coarse: in house_1w06 they sit 4-5 cm above every
# skrin_bar top and 31 cm above a kitchen counter. As a clearance blocker it
# refused every real top in that house as "collision above". Only Geometry and
# Roadway decide what is physically above a support.
CLEARANCE = ('geometry', 'roadway')
FOOTPRINT = ((0, 0), (.12, 0), (-.12, 0), (0, .12), (0, -.12),
             (.085, .085), (.085, -.085), (-.085, .085), (-.085, -.085))
METHOD = 'collision-support-v3: Geometry/Roadway/View-Geometry support; near-horizontal Geometry/Roadway slopes use local footprint heights, not whole-triangle height span; 0..0.08m below; 12cm footprint; 50cm vertical clearance against Geometry/Roadway only (View-Geometry occluder boxes never block); building roof and eight wall rays; stock proxy tables only; proxy marker faces excluded; no visual fallback'


class SupportScene(Scene):
    def __init__(self):
        super().__init__()
        self.sources = []
        # Eligibility depends only on the installed triangle, not the query.
        # Keep the full scene for clearance but index support faces once.
        self.support_cells = {}

    def add_source(self, values, source):
        before = len(self.triangles)
        self.add(values)
        self.sources.extend([source] * (len(self.triangles) - before))
        for index in range(before, len(self.triangles)):
            tri = self.triangles[index]
            normal = cross(subtract(tri[1], tri[0]), subtract(tri[2], tri[0]))
            length = math.sqrt(dot(normal, normal))
            # A tilted bus floor is a real solid even when a long triangle's
            # ends differ by 19cm. Geometry/Roadway support depends on its local
            # 12cm item footprint, checked below, not its whole-triangle span.
            # Retain the old flat-only restriction on visibility occluders.
            if (length and abs(normal[1]) / length >= .98
                    and (source['kind'] in CLEARANCE
                         or max(v[1] for v in tri) - min(v[1] for v in tri) <= .025)):
                for x in range(math.floor(min(v[0] for v in tri)), math.floor(max(v[0] for v in tri)) + 1):
                    for z in range(math.floor(min(v[2] for v in tri)), math.floor(max(v[2] for v in tri)) + 1):
                        self.support_cells.setdefault((x, z), []).append(index)

    def supports(self, x, z, low, high):
        result = []
        for index in self.support_cells.get((math.floor(x), math.floor(z)), ()):
            tri = self.triangles[index]
            y = gen.triangle_height(tri, x, z)
            if y is not None and low <= y <= high:
                result.append((y, self.sources[index]))
        return result


class Audit:
    def __init__(self, addons, reader, stock_proto, repo=ROOT):
        self.repo = Path(repo)
        self.reader = gen.Reader(reader)
        self.assets = gen.Assets(addons)
        self.stock_bytes = Path(stock_proto).read_bytes()
        self.stock = {g.get('name'): g for g in ET.fromstring(self.stock_bytes).findall('group')}
        self.policy_bytes = (self.repo / loot.POINTS_DIR / 'floor-policy.json').read_bytes()
        self.policy = validate_policy(json.loads(self.policy_bytes)['collision_support'])
        self.props = {}
        self.context_cache = None
        self.stats = Counter()

    def decode(self, path):
        return self.reader.module.ODOL_File.read(io.BytesIO(self.assets.read(path)))

    def context(self, name, spec):
        if self.context_cache and self.context_cache[0] == name:
            return self.context_cache[1]
        stock = self.stock.get(name)
        if stock is None or loot.group_pin(stock) != spec['stock_sha256']:
            raise ValueError('stock group pin mismatch: ' + name)
        path = pbo.normalize_path(pbo.resolve_field(self.assets.classes, name, 'model') or '')
        if path not in self.assets.members:
            return None
        data = self.assets.read(path)
        model = self.decode(path)
        if spec.get('building_model_sha256', gen.sha(data)) != gen.sha(data):
            raise ValueError('building model pin mismatch: ' + name)
        model.bounding_center = (0., 0., 0.)  # raw building vertices = CE model origin
        support, building, clearance = SupportScene(), Scene(), Scene()
        lods = [(kind, lod_for(model, resolution)) for kind, resolution in COLLISION]
        if not any(lod is not None for _, lod in lods):
            return None
        if any(lod is None for _, lod in lods):
            self.stats['missing_collision_lods'] += sum(lod is None for _, lod in lods)
        for kind, lod in lods:
            if lod is None:
                continue
            source = {'model': path, 'sha256': gen.sha(data), 'lod': lod.index, 'kind': kind}
            support.add_source(collision_triangles(model, lod), source)
            building.add(collision_triangles(model, lod))
            if kind in CLEARANCE:
                clearance.add(collision_triangles(model, lod))
        # Stock visual proxy tables identify furniture actually in the model.
        # Only that furniture's collision LODs are eligible, never its visual LOD.
        seen = set()
        for lod in model.lods:
            if lod.resolution >= 1000 and not any(lod is l for _, l in lods):
                continue
            for proxy, matrix in proxy_table(data, model, lod):
                key = (proxy, matrix)
                if key in seen:
                    continue
                seen.add(key)
                if proxy not in self.assets.members:
                    self.stats['unresolved_stock_proxies'] += 1
                    continue
                if proxy not in self.props:
                    prop = self.decode(proxy)
                    prop.lods = [l for l in prop.lods if any(math.isclose(l.resolution, r, rel_tol=1e-6) for _, r in COLLISION)]
                    self.props[proxy] = prop
                prop = self.props[proxy]
                for prop_kind, resolution in COLLISION:
                    prop_lod = lod_for(prop, resolution)
                    if prop_lod is not None:
                        source = {'model': proxy, 'sha256': gen.sha(self.assets.read(proxy)),
                                  'lod': prop_lod.index, 'kind': prop_kind,
                                  'transform': list(matrix)}
                        support.add_source(collision_triangles(prop, prop_lod, matrix), source)
                        if prop_kind in CLEARANCE:
                            clearance.add(collision_triangles(prop, prop_lod, matrix))
                self.stats['stock_proxy_instances'] += 1
        points = [model_point([float(v) for v in p.get('pos').split()]) for p in stock.iter('point')]
        extent = max((math.sqrt(sum(v*v for v in p)) for tri in building.triangles for p in tri), default=0)
        context = (support, building, clearance, points, max(10., extent * 2 + 1), path, gen.sha(data))
        self.context_cache = (name, context)
        self.assets.cache.pop(path, None)
        self.stats['building_models'] += 1
        return context

    def check(self, name, point, context):
        if context is None:
            return 'missing_collision_model', None
        support, building, clearance, stock, distance, _, _ = context
        x, y, z = model_point(point)
        hits = support.supports(x, z, y - .080001, y + .000001)
        if not hits:
            return 'no_collision_support_within_8cm', None
        # Every sample must stay on the same supported plane, not bridge edges.
        candidate = next(((height, source) for height, source in sorted(hits, key=lambda h: -h[0])
                          if all(any(abs(other - height) <= .025
                                     for other, _ in support.supports(x+dx, z+dz, y-.080001, y+.000001))
                                 for dx, dz in FOOTPRINT)), None)
        if candidate is None:
            return 'collision_support_footprint_edge', None
        height, source = candidate
        # A slab's underside is not an exposed top: require the CE item's
        # 50cm box to be clear above every support sample as well.
        if any(not clearance.clear((x+dx, y+.002, z+dz), (x+dx, y+.502, z+dz))
               for dx, dz in FOOTPRINT):
            return 'collision_above_item_support', None
        open_structure = (name in self.policy['open_structure_classes']
                          or any(name.startswith(prefix) for prefix in self.policy['open_structure_prefixes']))
        if open_structure:
            # Open structures have no enclosing wall loop. Native loot witnesses
            # constrain their supported footprint/storey without admitting terrain.
            if not any(math.hypot(x-p[0], z-p[2]) <= 3 and abs(y-p[1]) <= .35 for p in stock):
                return 'open_structure_outside_native_loot_footprint', None
        else:
            for dx, dz in FOOTPRINT:
                if not any(gen.triangle_height(tri, x+dx, z+dz) is not None
                           and gen.triangle_height(tri, x+dx, z+dz) > y + .10
                           for tri in building.candidates((x+dx, y+.10, z+dz), (x+dx, y+distance, z+dz))):
                    return 'no_building_roof_over_footprint', None
            # Eight enclosing structural wall rays above the loot/floor. Sampling
            # two heights permits windows; a porch missing a side still fails.
            for angle in range(8):
                dx, dz = math.cos(angle * math.tau / 8), math.sin(angle * math.tau / 8)
                enclosed = False
                for rise in (.60, 1.20):
                    start = (x, y+rise, z)
                    end = (x+distance*dx, y+rise, z+distance*dz)
                    for tri in building.candidates(start, end):
                        normal = cross(subtract(tri[1], tri[0]), subtract(tri[2], tri[0]))
                        length = math.sqrt(dot(normal, normal))
                        if length and abs(normal[1]) / length < .3 and intersection(start, end, tri):
                            enclosed = True
                            break
                    if enclosed:
                        break
                if not enclosed:
                    return 'outside_enclosing_building_walls', None
        return None, {'support_height_m': round(height, 6), 'gap_m': round(y-height, 6),
                      'support': source, 'open_structure': open_structure}

    def filter(self, doc):
        """Shared generator gate; maintains pins, source alignment and honest caps."""
        doc = copy.deepcopy(doc)
        rows = []
        totals = Counter()
        before_groups = len(doc['groups'])
        for name, spec in list(doc['groups'].items()):
            # Full-file audits must not accumulate decoded proxies or raw P3Ds
            # across buildings; generation already uses this per-building bound.
            context = None
            self.context_cache = None
            self.props.clear()
            self.assets.cache.clear()
            print('collision ' + name, file=sys.stderr, flush=True)
            context = self.context(name, spec)
            before = sum(len(c['points']) for c in spec['containers'].values())
            reasons, witnesses = Counter(), {}
            point_refusals = []
            for cname, container in list(spec['containers'].items()):
                keep, sources, proofs = [], [], []
                source_key = 'surface_sources' if cname == 'lootHCSurface' else 'floor_sources'
                old_sources = spec.get(source_key)
                if old_sources is not None and len(old_sources) != len(container['points']):
                    raise ValueError(source_key.split('_')[0] + ' evidence length mismatch: ' + name)
                for index, point in enumerate(container['points']):
                    reason, proof = self.check(name, point, context)
                    if reason:
                        reasons[reason] += 1
                        point_refusals.append({'container': cname, 'index': index,
                                               'point': point, 'reason': reason})
                    else:
                        keep.append(point)
                        proofs.append(proof)
                        if old_sources is not None:
                            sources.append(old_sources[index])
                if keep:
                    container['points'] = keep
                    container['lootmax'] = loot.added_lootmax(len(keep), spec.get('interior_area_m2'))
                    witnesses[cname] = proofs
                    if old_sources is not None:
                        spec[source_key] = sources
                else:
                    del spec['containers'][cname]
                    spec.pop(source_key, None)
            after = sum(len(c['points']) for c in spec['containers'].values())
            print(f'collision result {name} before={before} after={after}', file=sys.stderr, flush=True)
            totals.update(reasons)
            rows.append({'group': name, 'before': before, 'after': after, 'dropped': before-after,
                         'reasons': dict(sorted(reasons.items())), 'point_refusals': point_refusals})
            if spec['containers']:
                spec['collision_support'] = witnesses
                spec['building_model'], spec['building_model_sha256'] = context[-2:]
            else:
                del doc['groups'][name]
        checked = sum(r['before'] for r in rows)
        refused = sum(r['dropped'] for r in rows)
        prior = doc['sources'].get('collision_support', {}).get('result')
        # Continue history only for an unexpanded prior result. A manually
        # edited/new selection must get its own honest before-counts and pin.
        if prior and {r['group']: r['after'] for r in prior['groups'] if r['after']} != {r['group']: r['before'] for r in rows}:
            prior = None
        if prior:
            previous = {r['group']: r for r in prior['groups']}
            current = {r['group']: r for r in rows}
            combined = []
            for name, old in previous.items():
                row = current.get(name, {'after': 0, 'reasons': {}})
                reasons = Counter(old['reasons']) + Counter(row['reasons'])
                combined.append({'group': name, 'before': old['before'], 'after': row['after'],
                                 'dropped': old['before']-row['after'], 'reasons': dict(sorted(reasons.items())),
                                 'point_refusals': old.get('point_refusals', []) + row.get('point_refusals', [])})
            rows = combined
            before_groups = prior['before_groups']
            totals = Counter(prior['failure_counts']) + totals
        result = {'checked_points': checked, 'refused_points': refused,
                  'before_groups': before_groups, 'after_groups': len(doc['groups']),
                  'before_points': sum(r['before'] for r in rows), 'after_points': sum(r['after'] for r in rows),
                  'failure_counts': dict(sorted(totals.items())), 'groups': rows}
        if prior and 'input_sha256' in prior:
            result['input_sha256'] = prior['input_sha256']
        doc['sources']['collision_support'] = {
            'method': METHOD, 'floor_policy_sha256': gen.sha(self.policy_bytes),
            'stock_proto_sha256': gen.sha(self.stock_bytes),
            'reader_revision': gen.READER_REVISION, 'reader_sha256': gen.READER_HASHES,
            'result': result, 'native_acceptance': 'pending'}
        # Refresh existing source pins; don't claim old census files were rerun.
        if 'floor_policy_sha256' in doc['sources']:
            doc['sources']['floor_policy_sha256'] = gen.sha(self.policy_bytes)
        loot.parse_overlay(json.dumps(doc).encode())
        return doc, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--addons', type=Path, required=True)
    parser.add_argument('--reader', type=Path, required=True)
    parser.add_argument('--stock-proto', type=Path, required=True)
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--fix', action='store_true')
    args = parser.parse_args()
    audit = Audit(args.addons, args.reader, args.stock_proto, args.repo)
    report = {'method': METHOD, 'native_acceptance': 'pending', 'files': {}}
    for path in sorted((args.repo / loot.POINTS_DIR).glob('additions*.json')):
        raw = path.read_bytes()
        filtered, result = audit.filter(loot.parse_overlay(raw))
        result.setdefault('input_sha256', gen.sha(raw))
        report['files'][path.name] = result
        if args.fix:
            path.write_text(json.dumps(filtered, sort_keys=True, indent=2)+'\n')
    report['scene_counts'] = dict(sorted(audit.stats.items()))
    if args.report:
        args.report.write_text(json.dumps(report, sort_keys=True, indent=2)+'\n')
    print(json.dumps(report, sort_keys=True))
    if not args.fix and any(r['refused_points'] for r in report['files'].values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
