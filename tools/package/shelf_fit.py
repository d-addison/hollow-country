"""Host-only shelf admission calibration from pristine CE files and installed models.

No engine fit rule is claimed. Reuses loot_boost.types_files, _new_buildings,
shipped_points/scale_proto and loot_floor_policy._scan/_matches for installed
point composition and category/tag/usage matching (also used by ce_slot_pressure).
Game files are read in place; output contains no model paths or geometry.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from tools.audit import odol56, pbo_config as pbo
from tools.package import loot_boost as loot, loot_floor_policy as floor, variety_packs
from tools.package.regenerate_all import WORKSHOP
from tools.release.ship_inputs import ADDONS

ROOT = loot.REPO_ROOT
THRESHOLD = 0.30
RULE = 'Add shelves only when at least 30% of candidate shelf points fit; otherwise keep vanilla tags.'
FIT = 'First visual LOD longest bounding-box dimension <= point range; category and usage match; unweighted prototype points.'


def encode(doc):
    raw = (json.dumps(doc, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    floor.parse_shelf_fit(raw)
    return raw


def archives(addons, workshop, repo):
    """Vanilla, manifest dependency order, then installed optional packs; names only in receipts."""
    paths = sorted(addons.glob('*.pbo'))
    manifest = json.loads((repo / 'tools/setup/workshop_mods.json').read_bytes())
    directories = []
    for mod in sorted(manifest['mods'], key=lambda m: m['rank']):
        if mod.get('id') and not mod.get('publish'):
            directory = variety_packs.addons_dir(workshop / mod['id'])
            if directory is not None:
                directories.append(directory)
    directories.extend(d for d in variety_packs.pack_directories(workshop, repo).values() if d is not None)
    for directory in directories:
        paths.extend(sorted(directory.glob('*.pbo')))
    return list(dict.fromkeys(paths))


class Models:
    def __init__(self, paths):
        self.classes, self.members, self.cache = {}, {}, {}
        roots = ('CfgVehicles', 'CfgWeapons', 'CfgMagazines')
        for path in paths:
            index = pbo.read_pbo_index(path)
            # Config patches often redeclare a stock class with only scope or
            # another field. Preserve its earlier model and parent declaration.
            for _, configs in pbo.read_config_members(path, roots, index):
                for root in roots:
                    for name, fields in configs[root].items():
                        key = name.lower()
                        previous = self.classes.setdefault(key, {})
                        previous.update({k: (v.lower() if k == 'parent' and v else v)
                                         for k, v in fields.items() if v is not None
                                         and not (k == 'parent' and v.lower() == key)})
            for entry in index['entries']:
                if entry['name'].lower().endswith('.p3d'):
                    key = pbo.normalize_path(index['prefix'] + '/' + entry['name'])
                    self.members[key] = (path, index, entry['name'])

    def longest(self, name):
        path = pbo.normalize_path(pbo.resolve_field(self.classes, name.lower(), 'model') or '')
        if path and not path.endswith('.p3d'):
            path += '.p3d'
        if path in self.cache:
            return self.cache[path]
        result = None
        if path in self.members:
            archive, index, member = self.members[path]
            try:
                data = pbo.read_member(archive, index, member)
                model = odol56.read_header(data)
                # read_header exposes addresses, not bbox_min/bbox_max. Read the
                # exact bounded read_lod prefix, avoiding its full geometry decode.
                visual = [i for i, r in enumerate(model.resolutions) if 0 <= r < 1000]
                if visual:
                    i = min(visual, key=lambda i: (model.resolutions[i], i))
                    cur = odol56.Cursor(data, model.lod_starts[i], model.lod_ends[i])
                    odol56._read_proxies(cur)
                    odol56._read_bone_tables(cur)
                    cur.count()
                    cur.take(12)
                    bbox_min, bbox_max = cur.floats(3), cur.floats(3)
                    dims = [b - a for a, b in zip(bbox_min, bbox_max)]
                    if all(math.isfinite(v) and v >= 0 for v in dims) and max(dims) > 0:
                        result = max(dims)
            except (ValueError, OSError):
                pass  # Unknown is a refused admission, never a guessed fit.
        self.cache[path] = result
        return result


def classify(longest, ranges):
    count = len(ranges)
    share = sum(longest <= r for r in ranges) / count if count and longest is not None else 0
    reason = ('no_shelf_points' if not count else 'bounds_unknown' if longest is None
              else 'fits' if share >= THRESHOLD else 'below_threshold')
    # Conservative quantization prevents a 0.2996 ratio rounding into admission.
    return {'candidate_points': count, 'fit_share': math.floor(share * 1000) / 1000,
            'longest_m': round(longest, 2) if longest is not None else None, 'reason': reason}


def generate(source, addons, workshop, repo=ROOT):
    policy_raw = floor.shipped_policy(repo)
    policy = floor.parse_policy(policy_raw)
    inputs = {}

    def read(name):
        raw = loot.economy.read_plain(source, name)
        inputs[name] = hashlib.sha256(raw).hexdigest()
        return raw

    read(loot.CORE)
    table = {}
    for name in loot.types_files(source, include_optional=True):
        for row in loot.economy.xml(read(name), 'types').findall('type'):
            classname = row.get('name')
            cats = tuple(c.get('name') for c in row.findall('category'))
            tags = tuple(c.get('name') for c in row.findall('tag'))
            nominal = int(row.findtext('nominal', '0'))
            usages = frozenset(c.get('name') for c in row.findall('usage'))
            table[classname] = (frozenset(cats), frozenset(tags), frozenset([policy['shelf_tag']]), nominal, usages)
    # Use authored categories/usages/nominals for their candidate points, even
    # after a refused shelf tag has been removed. This makes generation stable
    # across the tag-only authored-row regeneration.
    authored_path = repo / 'mission/hollow-country/ce/types.xml'
    authored = loot.economy.xml(authored_path.read_bytes(), 'types').findall('type')
    authored_names = {row.get('name') for row in authored}
    for row in authored:
        name = row.get('name')
        table[name] = (frozenset(c.get('name') for c in row.findall('category')),
                       frozenset(c.get('name') for c in row.findall('tag')),
                       frozenset([policy['shelf_tag']]), int(row.findtext('nominal', '0')),
                       frozenset(c.get('name') for c in row.findall('usage')))
    proto, positions = read(loot.PROTO), read('mapgrouppos.xml')
    proto, _, _ = loot._new_buildings(proto, positions, loot.SHIPPED, repo)
    overlay_raw = loot.shipped_points(repo)
    overlay = loot.parse_overlay(overlay_raw) if overlay_raw else None
    read('cfglimitsdefinition.xml')
    proto, _ = loot.scale_proto(proto, 1.0, overlay, loot._limits(source))
    text = proto.decode('utf-8-sig')
    containers = [c for _, _, cs in floor._scan(text, loot._mask(text), floor._default(loot.economy.xml(proto, 'prototype')))
                  for c in cs if policy['shelf_tag'] in c['tags']]
    paths = archives(addons, workshop, repo)
    if not paths:
        raise ValueError('installed PBO inputs unavailable')
    models = Models(paths)
    classes, totals, nominals = {}, Counter(), Counter()
    for name, row in sorted(table.items()):
        cats, tags, _, nominal, usages = row
        if name not in authored_names and not floor.would_gain_shelf(name, cats, tags, nominal, policy):
            continue
        # _matches includes positive nominal; zero-quantity classes still need a
        # usable geometric route if an operator later raises their quantity.
        matching = (cats, tags, row[2], max(1, nominal), usages)
        ranges = []
        for container in containers:
            if floor._matches(matching, container, 'after'):
                start, end = container['body']
                for point in loot.economy.xml(('<container>' + text[start:end] + '</container>').encode(), 'container').findall('point'):
                    value = float(point.get('range', '0'))
                    if not math.isfinite(value) or value < 0:
                        raise ValueError('invalid candidate point range')
                    ranges.append(value)
        entry = classify(models.longest(name), ranges)
        classes[name] = entry
        totals[entry['reason']] += 1
        nominals[entry['reason']] += nominal
    repo_inputs = [repo / floor.FLOOR_POLICY, repo / 'tools/setup/workshop_mods.json',
                   repo / variety_packs.RULES, repo / 'mission/hollow-country/loot-points/new-buildings.json']
    repo_inputs += sorted((repo / loot.POINTS_DIR).glob('additions*.json'))
    doc = {'schema': 1, 'kind': floor.SHELF_FIT_KIND, 'threshold': THRESHOLD,
           'rule': RULE, 'fit_definition': FIT, 'input_digests': {
               'mission': dict(sorted(inputs.items())),
               'repo': {p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in repo_inputs},
               'pbo_names_sizes_sha256': hashlib.sha256(json.dumps(sorted(
                   (p.name, p.stat().st_size) for p in paths), separators=(',', ':')).encode()).hexdigest()},
           'authored_candidates_sha256': hashlib.sha256(json.dumps(sorted(
               (name, sorted(row[0]), row[3], sorted(row[4])) for name, row in table.items()
               if name in authored_names), separators=(',', ':')).encode()).hexdigest(),
           'classes': classes}
    report = {'classes_by_reason': dict(sorted(totals.items())), 'nominal_by_reason': dict(sorted(nominals.items()))}
    unknown = [(name, table[name][3]) for name, r in classes.items()
               if r['reason'] == 'bounds_unknown' and table[name][3] > 0]
    if len(unknown) > 60:
        report['largest_unknown_nominal'] = sorted(unknown, key=lambda r: (-r[1], r[0]))[:20]
    return encode(doc), report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('generate', 'check'))
    parser.add_argument('--addons', type=Path, default=ADDONS)
    parser.add_argument('--workshop', type=Path, default=WORKSHOP)
    parser.add_argument('--source', type=Path, help='pristine mission; defaults to sibling of Addons, as regenerate_all')
    parser.add_argument('--repo', type=Path, default=ROOT)
    args = parser.parse_args()
    source = args.source or args.addons.parent / 'mpmissions/dayzOffline.chernarusplus'
    raw, report = generate(source, args.addons, args.workshop, args.repo)
    output = args.repo / floor.SHELF_FIT
    print(json.dumps(report, sort_keys=True))
    if args.mode == 'check':
        if not output.is_file() or output.read_bytes() != raw:
            raise SystemExit('shelf-fit bytes differ; regenerate on the dev host')
    else:
        output.write_bytes(raw)


if __name__ == '__main__':
    main()
