"""Re-audit and preserve prior surface coordinates before adding a new layout.

Unlike a larger-layout-first merge, passing prior points cannot be crowded out
by new points or a smaller area cap. Every missing prior coordinate has an
explicit physical refusal in the output receipt. Installed assets stay external;
--refresh-models explicitly permits re-auditing a historical layout on new meshes.
Run partitions under agent-run --memory 3G; merge every partition exactly once.
This is static evidence only, never DayZ acceptance.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path

from tools.audit import pbo_config as pbo
from tools.package import interior_points_gen as gen, loot_boost as loot
from tools.package.loot_reach_audit import Audit as Reach, model_point
from tools.package.loot_support_audit import Audit as Support


def encode(doc):
    raw = (json.dumps(doc, sort_keys=True, indent=2) + '\n').encode()
    loot.parse_overlay(raw)
    return raw


def rebind(point, reach, context, proxies, templates):
    """Find an installed visual proxy supporting this exact unchanged coordinate.

    Current meshes can move baked furniture into proxy members. Requiring the
    historical root mesh to still contain those faces falsely calls the item
    floating. Derive fresh local coordinates and triangles from actual tables;
    all support, clearance, standing and approach checks still apply.
    """
    world = model_point(point)
    for member, matrix in sorted(proxies):
        if (max(abs(matrix[3+i] - (1 if i == 1 else 0)) for i in range(3)) > .001
                or any(abs(sum(v*v for v in axis)-1) > .001 for axis in (matrix[:3], matrix[6:9]))
                or abs(sum(matrix[i]*matrix[6+i] for i in range(3))) > .001):
            continue
        kind = gen.surface_model(member)
        support_member = (member if '_open' in member else kind[1]) if kind else member
        if support_member not in reach.assets.members:
            continue
        if support_member not in reach.meshes:
            reach.meshes[support_member] = gen.Mesh(reach.prop(support_member))
        mesh = reach.meshes[support_member]
        delta = [world[a] - matrix[9+a] for a in range(3)]
        local = [sum(delta[a]*matrix[3*i+a] for a in range(3)) for i in range(3)]
        for height, normal, face, triangle in mesh.hits(local[0], local[2]):
            if normal <= .85 or abs(height - (local[1]-.005)) > .025:
                continue
            source = {'model': member, 'support_model': support_member,
                      'surface': gen.role(kind[0] if kind else member.rsplit('\\', 1)[-1].removesuffix('.p3d')),
                      'local_point': [round(v, 8) for v in local],
                      'transform': list(matrix), 'lod': mesh.lod, 'face': face,
                      'model_center': list(mesh.center),
                      'support_triangle': [[round(v, 6) for v in vertex] for vertex in triangle]}
            failures, _ = reach.check(point, source, context, templates)
            if not failures:
                return source
    return None


def preserve(prior_path, candidate_path, addons, reader, stock, partition,
             refresh_models=False):
    prior_raw, candidate_raw = Path(prior_path).read_bytes(), Path(candidate_path).read_bytes()
    prior, candidate = loot.parse_overlay(prior_raw), loot.parse_overlay(candidate_raw)
    reach, collision = Reach(addons, reader, stock, gen.ROOT), Support(addons, reader, stock)
    stock_sha = gen.sha(Path(stock).read_bytes())
    if any(d['sources']['stock_proto_sha256'] != stock_sha for d in (prior, candidate)):
        raise ValueError('stock prototype pin mismatch')
    index, count = partition
    if not 0 <= index < count <= 32:
        raise ValueError('partition requires 0 <= index < count <= 32')
    doc = copy.deepcopy(candidate)
    doc['groups'] = {}
    doc['sources'].pop('collision_support', None)
    receipt = {'prior_sha256': gen.sha(prior_raw), 'candidate_sha256': gen.sha(candidate_raw),
               'refresh_models': refresh_models, 'partition': {'index': index, 'count': count},
               'method': 'preserve every passing prior coordinate; append passing new coordinates within spacing and cap; every prior removal requires a physical refusal',
               'native_acceptance': 'pending', 'groups': {}}
    for name in sorted(set(prior['groups']) | set(candidate['groups']))[index::count]:
        print('preserve ' + name, flush=True)
        context = support_context = None
        reach.props.clear()
        reach.meshes.clear()
        reach.lifts.clear()
        reach.assets.cache.clear()
        collision.props.clear()
        collision.assets.cache.clear()
        collision.context_cache = None
        old, new = prior['groups'].get(name), candidate['groups'].get(name)
        spec = copy.deepcopy(new or old)
        if old and new and any(old[k] != new[k] for k in ('family', 'stock_sha256')):
            raise ValueError('prior building family/stock mismatch: ' + name)
        path = pbo.normalize_path(pbo.resolve_field(reach.assets.classes, name, 'model') or '')
        pin = gen.sha(reach.assets.read(path))
        changed = {label: item['building_model_sha256'] for label, item in
                   (('prior', old), ('candidate', new)) if item and item['building_model_sha256'] != pin}
        if changed and not refresh_models:
            raise ValueError('building model pin mismatch (requires --refresh-models): ' + name)
        spec['building_model'], spec['building_model_sha256'] = path, pin
        context, support_context = reach.scene(name, spec), collision.context(name, spec)
        proxy_entries = list(gen.stock_proxies(reach.assets.read(path), context[1]))
        proxies = {(member, tuple(round(v, 4) for v in matrix)) for member, matrix in proxy_entries}
        selected, evidence, proofs = [], [], []
        row = {'prior_points': 0, 'candidate_points': 0, 'after_points': 0,
               'model_pin_changes': changed, 'prior_refusals': [], 'candidate_not_selected': [],
               'rebound_evidence': []}
        for label, item in (('prior', old), ('candidate', new)):
            if item is None:
                continue
            points = item['containers']['lootHCSurface']['points']
            if len(points) != len(item['surface_sources']):
                raise ValueError('surface evidence count mismatch: ' + name)
            row[label + '_points'] = len(points)
            for point, source in zip(points, item['surface_sources']):
                if point in selected:
                    continue
                reason, proof = collision.check(name, point, support_context)
                failures = [reason] if reason else []
                if not failures:
                    failures, _ = reach.check(point, source, context, reach.templates.get(name, []))
                if source['surface'] != 'baked-interior-ledge' and (
                        source['model'], tuple(round(v, 4) for v in source['transform'])) not in proxies:
                    failures.append('missing_installed_support_proxy')
                if not reason and failures:
                    replacement = rebind(point, reach, context, proxy_entries, reach.templates.get(name, []))
                    if replacement is not None:
                        row['rebound_evidence'].append({'point': point, 'layout': label,
                            'prior_model': source['model'], 'current_model': replacement['model'],
                            'false_refusals': sorted(set(failures))})
                        source, failures = replacement, []
                if failures:
                    row[label + ('_refusals' if label == 'prior' else '_not_selected')].append(
                        {'point': point, 'stage': 'collision' if reason else 'reach',
                         'reasons': sorted(set(failures))})
                    continue
                # Spacing/cap control additions, never erase a passing prior spot.
                if label == 'candidate' and (gen.near(point, selected) or len(selected) >=
                        gen.surface_cap(spec.get('interior_area_m2'))):
                    row['candidate_not_selected'].append({'point': point, 'stage': 'selection',
                        'reasons': ['spacing_against_preserved_point' if gen.near(point, selected)
                                    else 'surface_area_cap']})
                    continue
                selected.append(point)
                evidence.append(source)
                proofs.append(proof)
                if source['surface'] != 'baked-interior-ledge':
                    member = source.get('support_model', source['model'])
                    mesh = reach.meshes[member]
                    doc['sources']['model_surfaces'][member] = {
                        'sha256': gen.sha(reach.assets.read(member)), 'lod': mesh.lod,
                        'model_center': list(mesh.center)}
        if len(selected) > loot.MAX_SURFACE_POINTS:
            raise ValueError('preserved layout exceeds hard surface bound: ' + name)
        # Another source can re-evidence the same coordinate later in the pass.
        row['prior_refusals'] = [r for r in row['prior_refusals'] if r['point'] not in selected]
        row['after_points'] = len(selected)
        receipt['groups'][name] = row
        if not selected:
            continue
        container = spec['containers']['lootHCSurface']
        container['points'] = selected
        container['lootmax'] = loot.added_lootmax(len(selected), spec.get('interior_area_m2'))
        container['categories'] = gen.story_categories(name, reach.stock[name], spec['family'],
                                                      [e['surface'] for e in evidence])
        spec['surface_sources'] = evidence
        spec['collision_support'] = {'lootHCSurface': proofs}
        doc['groups'][name] = spec
    doc['sources']['point_preservation'] = receipt
    return doc


def merge(paths):
    parts = [loot.parse_overlay(Path(path).read_bytes()) for path in paths]
    infos = [p['sources']['point_preservation'] for p in parts]
    if (any(i['partition']['count'] != len(parts) for i in infos) or
            sorted(i['partition']['index'] for i in infos) != list(range(len(parts)))):
        raise ValueError('require every disjoint preservation partition exactly once')
    doc = copy.deepcopy(parts[0])
    doc['groups'] = {}
    receipt = doc['sources']['point_preservation']
    receipt['groups'] = {}
    receipt.pop('partition')
    receipt['partitions'] = len(parts)
    doc['sources']['model_surfaces'] = {}
    for part, info in zip(parts, infos):
        for key in ('prior_sha256', 'candidate_sha256', 'refresh_models', 'method'):
            if info[key] != receipt[key]:
                raise ValueError('preservation partition input mismatch: ' + key)
        if set(receipt['groups']) & set(info['groups']):
            raise ValueError('overlapping preservation partitions')
        receipt['groups'].update(info['groups'])
        doc['groups'].update(part['groups'])
        for spec in part['groups'].values():
            for source in spec['surface_sources']:
                if source['surface'] == 'baked-interior-ledge':
                    continue
                member = source.get('support_model', source['model'])
                pin = part['sources']['model_surfaces'][member]
                previous = doc['sources']['model_surfaces'].setdefault(member, pin)
                if previous != pin:
                    raise ValueError('preservation support pin mismatch: ' + member)
    counts = Counter(reason for r in receipt['groups'].values() for p in r['prior_refusals']
                     for reason in p['reasons'])
    receipt['prior_refusal_counts'] = dict(sorted(counts.items()))
    receipt['prior_refused_points'] = sum(len(r['prior_refusals']) for r in receipt['groups'].values())
    receipt['after_points'] = sum(r['after_points'] for r in receipt['groups'].values())
    for name in doc['groups']:
        doc['sources']['rejected_groups'].pop(name, None)
    doc['sources']['rejected_counts'] = dict(sorted(Counter(doc['sources']['rejected_groups'].values()).items()))
    return doc


def check(prior_path, candidate_path, doc):
    """Fail closed if even one removed coordinate has no recorded refusal."""
    prior_raw, candidate_raw = Path(prior_path).read_bytes(), Path(candidate_path).read_bytes()
    prior, candidate = loot.parse_overlay(prior_raw), loot.parse_overlay(candidate_raw)
    receipt = doc['sources']['point_preservation']
    if (gen.sha(prior_raw) != receipt['prior_sha256'] or
            gen.sha(candidate_raw) != receipt['candidate_sha256']):
        raise ValueError('preservation receipt input mismatch')
    counts = Counter()
    historical = receipt.get('historical_candidate_loss_audit')
    historical_points = {}
    if historical:
        if any(historical[k] != receipt[k] for k in ('prior_sha256', 'candidate_sha256')):
            raise ValueError('historical loss audit input mismatch')
        historical_points = {(r['group'], tuple(r['point'])): r for r in historical['points']}
    reviewed = set()
    for name, row in receipt['groups'].items():
        old = prior['groups'].get(name, {}).get('containers', {}).get('lootHCSurface', {}).get('points', [])
        new = candidate['groups'].get(name, {}).get('containers', {}).get('lootHCSurface', {}).get('points', [])
        after = doc['groups'].get(name, {}).get('containers', {}).get('lootHCSurface', {}).get('points', [])
        refused = {tuple(r['point']): r for r in row['prior_refusals']}
        skipped = {tuple(r['point']): r for r in row['candidate_not_selected']}
        if len(refused) != len(row['prior_refusals']) or len(skipped) != len(row['candidate_not_selected']):
            raise ValueError('duplicate point decision: ' + name)
        if set(refused) != {tuple(p) for p in old if p not in after}:
            raise ValueError('unreported prior loss or spurious refusal: ' + name)
        if set(skipped) != {tuple(p) for p in new if p not in after}:
            raise ValueError('unreported candidate loss or spurious refusal: ' + name)
        if any(not r['reasons'] or r['stage'] not in ('collision', 'reach')
               for r in refused.values()):
            raise ValueError('prior removal lacks a physical refusal: ' + name)
        omissions = []
        for point in old:
            if point in new:
                continue
            refusal = refused.get(tuple(point))
            historical_row = historical_points.get((name, tuple(point)))
            if historical and historical_row is None:
                raise ValueError('historical omission missing from loss audit: ' + name)
            if historical_row is not None:
                reviewed.add((name, tuple(point)))
                original = historical_row['support'] or (','.join(historical_row['reach']))
                reason = ('stripped_server_collision_refusal' if historical_row['support']
                          else 'stripped_server_visual_refusal' if historical_row['reach']
                          else 'selection_spacing' if historical_row['near_current']
                          else 'selection_area_cap' if historical_row['current'] >= historical_row['cap']
                          else 'selection_missing_prior')
                decision = {'point': point, 'stage': 'historical_review', 'reasons': [reason],
                            'original_rule': original or reason, 'restored': point in after}
            elif refusal:
                decision = dict(refusal)
            else:
                reason = ('selection_spacing' if gen.near(point, new) else 'selection_area_cap'
                          if len(new) >= gen.surface_cap(candidate['groups'].get(name, {}).get('interior_area_m2'))
                          else 'selection_missing_prior')
                decision = {'point': point, 'stage': 'selection', 'reasons': [reason]}
            omissions.append(decision)
            counts.update(decision['reasons'])
        row['candidate_omissions_vs_prior'] = omissions
    if historical and reviewed != set(historical_points):
        raise ValueError('historical audit contains non-omitted coordinates')
    expected = set(prior['groups']) | set(candidate['groups'])
    if set(receipt['groups']) != expected:
        raise ValueError('incomplete preservation receipt')
    receipt['candidate_omission_reason_counts'] = dict(sorted(counts.items()))
    return {'prior_points': sum(r['prior_points'] for r in receipt['groups'].values()),
            'prior_removed_with_physical_refusals': receipt['prior_refused_points'],
            'unreported_losses': 0, 'candidate_omission_reason_counts': dict(sorted(counts.items()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prior', type=Path)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--addons', type=Path)
    parser.add_argument('--reader', type=Path)
    parser.add_argument('--stock-proto', type=Path)
    parser.add_argument('--partition', nargs=2, type=int, default=(0, 1))
    parser.add_argument('--refresh-models', action='store_true')
    parser.add_argument('--merge', nargs='+', type=Path)
    parser.add_argument('--loss-audit', type=Path, help='hash-bound historical candidate omission audit for merge receipt')
    parser.add_argument('--check', action='store_true', help='check existing output against prior/candidate without writing')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.check:
        if not args.prior or not args.candidate:
            parser.error('check requires prior/candidate')
        print(json.dumps(check(args.prior, args.candidate, loot.parse_overlay(args.out.read_bytes())), sort_keys=True))
        return
    if args.merge:
        if not args.prior or not args.candidate:
            parser.error('merge requires prior/candidate for the complete point-loss check')
        doc = merge(args.merge)
        if args.loss_audit:
            doc['sources']['point_preservation']['historical_candidate_loss_audit'] = json.loads(args.loss_audit.read_bytes())
        print(json.dumps(check(args.prior, args.candidate, doc), sort_keys=True))
    else:
        if not all((args.prior, args.candidate, args.addons, args.reader, args.stock_proto)):
            parser.error('preservation requires prior, candidate, addons, reader and stock-proto')
        doc = preserve(args.prior, args.candidate, args.addons, args.reader, args.stock_proto,
                       args.partition, args.refresh_models)
    args.out.write_bytes(encode(doc))


if __name__ == '__main__':
    main()
