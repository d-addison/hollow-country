"""Generate CE candidates from vanilla furniture proxies and baked room surfaces.

Run as a module with --addons and --stock-proto. Assets stay external; only
hashes, transforms and candidate coordinates enter the overlay. This is static
support evidence, not native collision/clearance or CE acceptance. Optional
runtime furnishings never count as unconditional support.
"""
import argparse
from collections import Counter, deque
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import struct
import sys
import types
import xml.etree.ElementTree as ET

from tools.audit import pbo_config as pbo
from tools.package import loot_boost as loot

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'mission/hollow-country/loot-points/additions-interiors.json'
# Furniture whose horizontal faces have a useful scavenging context. Actual
# triangles, not the entire bounding box, must support each admitted point.
TOPS = {
    'almara', 'case_a', 'case_cans_b', 'case_d', 'dhangar_brownskrin',
    'dhangar_brownskrin_old', 'library_a', 'lobby_case', 'metalcase_01',
    'metalcrate', 'metalcrate_02', 'sarcophagus', 'skrin_bar', 'lekarnicka',
    'icebox', 'shelf', 'shelf_1side', 'class_case_a_closed',
    'class_case_b_closed', 'teacher_desk', 'conference_table_a',
    'kitchen_table_a', 'lobby_table', 'desk_office', 'office_table_a',
    'table_umakart', 'shelf_dz', 'workbench', 'workbench_dz',
    'case_bedroom_a', 'case_bedroom_b', 'metalcase_02', 'pult',
    'fridge', 'kitchen_unit_a_dz', 'table_drawer', 'table_dz',
    'case_wall_unit_part_c', 'case_wall_unit_part_d', 'case_sink_a',
    'airport_bench', 'hospital_bench', 'long_bench',
    'medical_table', 'lab_bench', 'lab_teacher_bench', 'student_desk',
    'lobby_counter', 'chest_dz', 'matress_white', 'foldingbed_matress',
    'kicthen_desk_a', 'kicthen_desk_a_cupboards',
    'kicthen_desk_a_nocupboards', 'kicthen_desk_b', 'kicthen_desk_c',
    'kicthen_desk_single_cupboard_closed',
    # Additional installed vanilla members, inspected read-only for this pass.
    # Seats and appliance tops still need the same horizontal mesh support,
    # clearance, room footprint and independently witnessed approach as shelves.
    'bar_shelves_dz', 'rack_dz', 'tools_racking_dz', 'pultskasou',
    'stul_kuch1', 'washing_machine', 'kitchenstove_elec',
    'piano', 'postel_panelak1', 'postel_panelak2', 'postel_manz_kov',
    'postel_manz_kov_rust', 'vojenska_palanda',
    'stretcher_green', 'stretcher_red',
    'brown_sofa_old', 'sofa_leather_new', 'sofa_leather_old',
    'sofa_sakhal_1', 'sofacorner', 'couch_dz', 'couch_beige84x213x75_dz',
    'church_chair', 'lobby_chair', 'vaulting_box_large', 'vaulting_box_small',
    'paperbox_01_small_closed', 'box_c', 'box_c_multi',
}
PROXY = re.compile(rb'\\dz\\[^\x00\r\n]{1,400}\x00', re.I)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Assets:
    def __init__(self, folder):
        self.members, self.classes = {}, {}
        for path in sorted(Path(folder).glob('structures*.pbo')):
            index = pbo.read_pbo_index(path)
            self.classes.update(pbo.read_configs(path, ['CfgVehicles'], index)['CfgVehicles'])
            for entry in index['entries']:
                if entry['name'].lower().endswith('.p3d'):
                    key = pbo.normalize_path(index['prefix'] + '\\' + entry['name'])
                    if key in self.members:
                        raise ValueError('ambiguous installed model: ' + key)
                    self.members[key] = (path, index, entry['name'])
        self.cache = {}

    def read(self, model):
        if model not in self.cache:
            path, index, member = self.members[model]
            self.cache[model] = pbo.read_member(path, index, member)
        return self.cache[model]


def surface_model(model):
    stem = model.rsplit('\\', 1)[-1].removesuffix('.p3d')
    if stem.startswith('locker_'):
        return 'locker', re.sub(r'locker_open', 'locker_closed', model)
    if stem in {'bed_stacked', 'foldingbed_open', 'hospital_transport_bed'}:
        return stem, model
    closed = stem.removesuffix('_open')
    if closed in TOPS:
        return closed, model.replace(stem + '.p3d', closed + '.p3d')
    return None


def role(stem):
    if stem.startswith('kicthen_') or stem in {'kitchen_table_a', 'table_umakart', 'icebox', 'skrin_bar', 'shelf', 'shelf_1side', 'pult', 'pultskasou', 'fridge', 'kitchen_unit_a_dz', 'kitchenstove_elec'}:
        return 'kitchen-counter'
    if ('matress' in stem or stem.startswith(('postel_', 'stretcher_'))
            or stem in {'bed_stacked', 'foldingbed_open', 'hospital_transport_bed', 'vojenska_palanda'}):
        return 'bed-mattress'
    if ('sofa' in stem or 'couch' in stem or stem.endswith('_bench')
            or stem in {'church_chair', 'lobby_chair'}):
        return 'bench-seat'
    if stem in {'washing_machine', 'piano'}:
        return 'appliance-top'
    if stem == 'medical_table':
        return 'medical-tray'
    if stem == 'lekarnicka':
        return 'bathroom-cabinet'
    if 'workbench' in stem or 'crate' in stem:
        return 'repair-bench'
    if stem == 'locker':
        return 'locker-top'
    if stem in {'almara', 'case_a', 'dhangar_brownskrin', 'dhangar_brownskrin_old'}:
        return 'wardrobe-top'
    if 'desk' in stem or 'table' in stem:
        return 'desk-table'
    return 'cabinet-shelf'


READER_REVISION = 'e272780131dc10fe798bad321dca2c96894e993e'
READER_HASHES = {
    'data_p3d_odol.py': '275fb16b687d91920a5b024cbd96f6507c475b1d6a510efb55cb3293f9cd8252',
    'binary_handler.py': 'bb512f19fe61a951f798465a4966a2ea2c8a7cfc53d38b28aa2b0611cc8d0206',
    'compression.py': '1b518489b63246d8e6dbdb019d6450dcbd035a5cbb59134df4738541c3aa8a10',
}


def triangle_height(triangle, x, z):
    a, b, c = triangle
    det = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
    if abs(det) < 1e-9:
        return None
    u = ((b[2] - c[2]) * (x - c[0]) + (c[0] - b[0]) * (z - c[2])) / det
    v = ((c[2] - a[2]) * (x - c[0]) + (a[0] - c[0]) * (z - c[2])) / det
    if min(u, v, 1 - u - v) < -1e-6:
        return None
    return u * a[1] + v * b[1] + (1 - u - v) * c[1]


class Mesh:
    def __init__(self, model, restore_center=True):
        visual = [lod for lod in model.lods if lod.resolution < 1000]
        if not visual:
            raise ValueError('no readable visual LOD')
        lod = min(visual, key=lambda item: (item.resolution, item.index))
        self.lod = lod.index
        # Stock building vertices already use the CE model origin. Furniture
        # vertices instead need their own local bounding centre restored.
        self.center = model.bounding_center if restore_center else (0.0, 0.0, 0.0)
        vertices = [tuple(v[a] + self.center[a] for a in range(3)) for v in lod.vertices]
        self.triangles, self.cells = [], {}
        for face_index, face in enumerate(lod.faces):
            for i in range(1, len(face) - 1):
                indices = [face[0], face[i], face[i + 1]]
                triangle = [vertices[k] for k in indices]
                normal_y = sum(lod.normals[k][1] for k in indices) / 3
                tri_id = len(self.triangles)
                self.triangles.append((triangle, normal_y, face_index))
                # Spatial index for vertical rays. No external mesh dependencies.
                for x in range(math.floor(min(v[0] for v in triangle) / .65),
                               math.floor(max(v[0] for v in triangle) / .65) + 1):
                    for z in range(math.floor(min(v[2] for v in triangle) / .65),
                                   math.floor(max(v[2] for v in triangle) / .65) + 1):
                        self.cells.setdefault((x, z), []).append(tri_id)

    def hits(self, x, z):
        hits = []
        for index in self.cells.get((math.floor(x / .65), math.floor(z / .65)), ()):
            triangle, normal_y, face = self.triangles[index]
            y = triangle_height(triangle, x, z)
            if y is not None:
                hits.append((y, normal_y, face, triangle))
        return hits

    def tops(self, accept=None, measured_box=None):
        seen = set()
        for triangle, normal_y, face in self.triangles:
            if normal_y < .85 or max(v[1] for v in triangle) - min(v[1] for v in triangle) > .025:
                continue
            positions = [(sum(v[0] for v in triangle) / 3, sum(v[2] for v in triangle) / 3)]
            # A narrow rectangular shelf can fall entirely between global grid
            # columns; its two triangle centroids can both be too near an edge.
            # The face-bounds centre recovers its genuinely supported middle.
            positions.append(((min(v[0] for v in triangle) + max(v[0] for v in triangle)) / 2,
                              (min(v[2] for v in triangle) + max(v[2] for v in triangle)) / 2))
            if measured_box is not None:
                # Measured native prop boxes seed the centre of a top, but the
                # actual visual mesh still supplies height and all support rays.
                positions.append(((measured_box['Min'][0] + measured_box['Max'][0]) / 2,
                                  (measured_box['Min'][2] + measured_box['Max'][2]) / 2))
            # Sample narrowly spaced alternatives before spacing the final set.
            # This lets the reach check find the accessible edge of a long top.
            step = .15
            for x in range(math.ceil(min(v[0] for v in triangle) / step),
                           math.floor(max(v[0] for v in triangle) / step) + 1):
                for z in range(math.ceil(min(v[2] for v in triangle) / step),
                               math.floor(max(v[2] for v in triangle) / step) + 1):
                    positions.append((x * step, z * step))
            # Follow the midline of narrow sills/tops even when no global grid
            # column falls on their supportable width. Heights still snap to an
            # actual triangle and the same five footprint rays must pass.
            xmin, xmax = min(v[0] for v in triangle), max(v[0] for v in triangle)
            zmin, zmax = min(v[2] for v in triangle), max(v[2] for v in triangle)
            for x in (xmin + .125, (xmin + xmax) / 2, xmax - .125):
                for z in range(math.ceil(zmin / step), math.floor(zmax / step) + 1):
                    positions.append((x, z * step))
            for z in (zmin + .125, (zmin + zmax) / 2, zmax - .125):
                for x in range(math.ceil(xmin / step), math.floor(xmax / step) + 1):
                    positions.append((x * step, z))
            for x, z in positions:
                y = triangle_height(triangle, x, z)
                if y is None:
                    continue
                if accept is not None and not accept(x, y + .005, z):
                    continue
                key = tuple(round(v, 4) for v in (x, y, z))
                if key in seen:
                    continue
                seen.add(key)
                # A 12cm footprint must stay on this horizontal support plane.
                if any(not any(abs(hit[0] - y) < .025 and hit[1] > .85
                               for hit in self.hits(x + dx, z + dz))
                       for dx, dz in ((.12, 0), (-.12, 0), (0, .12), (0, -.12))):
                    continue
                yield [x, y + .005, z], {'lod': self.lod, 'face': face,
                    'support_triangle': [[round(v, 6) for v in p] for p in triangle],
                    'model_center': [round(v, 8) for v in self.center]}


class Reader:
    def __init__(self, folder):
        folder = Path(folder)
        for filename, digest in READER_HASHES.items():
            if sha((folder / filename).read_bytes()) != digest:
                raise ValueError('ODOL reader source pin mismatch: ' + filename)
        package = types.ModuleType('_hc_interior_odol')
        package.__path__ = [str(folder.absolute())]
        sys.modules[package.__name__] = package
        spec = importlib.util.spec_from_file_location(package.__name__ + '.data_p3d_odol', folder / 'data_p3d_odol.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def mesh(self, data, restore_center=True):
        return Mesh(self.module.ODOL_File.read(io.BytesIO(data)), restore_center)


def stock_point(transform, point):
    v = [transform[9 + a] + sum(point[i] * transform[3 * i + a] for i in range(3)) for a in range(3)]
    return [round(v[2], 6), round(v[1], 6), round(-v[0], 6)]


def near(point, others):
    return any(abs(point[1] - q[1]) < .30 and math.hypot(point[0] - q[0], point[2] - q[2]) < .60
               for q in others)


def generate(addons, stock_proto, reader_folder, map_pos=None):
    # Reuse the independent audit without relaxing any of its limits. Evaluate
    # before spacing/capping so refused candidates do not crowd out good tops.
    from tools.package.loot_reach_audit import Audit
    auditor = Audit(addons, reader_folder, stock_proto, ROOT)
    reader, assets = auditor.reader, auditor.assets
    measured = {name.removeprefix('StaticObj_Furniture_').lower(): box
                for name, box in auditor.boxes.items()}
    audit_refusals = Counter()
    audit_checked = 0
    furniture_meshes = {}
    furniture_tops = {}
    stock_bytes = Path(stock_proto).read_bytes()
    stock = ET.fromstring(stock_bytes)
    placements = Counter()
    if map_pos is not None:
        placements.update(g.get('name') for g in ET.fromstring(Path(map_pos).read_bytes()).findall('group'))
    policy = loot.parse_policy((ROOT / loot.FAMILIES).read_bytes())
    templates = {}
    for path in sorted((ROOT / 'mission/hollow-country/interiors/templates').glob('t-*.json')):
        doc = json.loads(path.read_bytes())
        templates.setdefault(doc['BuildingClass'], {'file': path.relative_to(ROOT).as_posix(),
                             'sha256': sha(path.read_bytes()), 'box': doc['Box']})
    groups, surfaces, rejected, refused = {}, {}, Counter(), {}
    for group in sorted(stock.findall('group'), key=lambda g: g.get('name', '')):
        name = group.get('name', '')
        # Do not inflate building coverage with car wrecks, wells or containers.
        if not name.startswith('Land_') or re.search(r'Wreck|wreck|Container_|Train_|Boat_Small|Misc_Well', name):
            continue
        model = pbo.resolve_field(assets.classes, name, 'model')
        if not model:
            rejected['missing-model'] += 1
            refused[name] = 'missing-model'
            continue
        model = pbo.normalize_path(model)
        if model not in assets.members:
            rejected['missing-member'] += 1
            refused[name] = 'missing-member'
            continue
        print('generate ' + name, file=sys.stderr, flush=True)
        data = assets.read(model)
        existing = [[float(v) for v in p.get('pos').split()] for p in group.iter('point')]
        floor = loot.stock_floor(group)
        candidates, seen = [], set()
        for match in PROXY.finditer(data):
            proxy_model = pbo.normalize_path(match.group()[:-1].decode('ascii'))
            if not proxy_model.endswith('.p3d'):
                proxy_model += '.p3d'
            kind = surface_model(proxy_model)
            if kind is None or proxy_model not in assets.members:
                continue
            stem, closed = kind
            if closed not in assets.members:
                continue
            end = match.end()
            if end + 48 > len(data):
                continue
            transform = struct.unpack_from('<12f', data, end)
            if not all(math.isfinite(v) and abs(v) < 1000 for v in transform):
                continue
            # Unit upright orthogonal proxy basis only; ignore wrecked/tilted furniture.
            x, y, z = transform[:3], transform[3:6], transform[6:9]
            if (max(abs(y[i] - (1 if i == 1 else 0)) for i in range(3)) > .001
                    or any(abs(sum(v * v for v in axis) - 1) > .001 for axis in (x, z))
                    or abs(sum(x[i] * z[i] for i in range(3))) > .001):
                continue
            identity = (proxy_model, tuple(round(v, 4) for v in transform))
            if identity in seen:
                continue
            seen.add(identity)
            mesh_key = proxy_model if '_open' in proxy_model else closed
            if mesh_key not in furniture_meshes:
                furniture_meshes[mesh_key] = reader.mesh(assets.read(mesh_key))
                prop_stem = mesh_key.rsplit('\\', 1)[-1].removesuffix('.p3d')
                furniture_tops[mesh_key] = list(
                    furniture_meshes[mesh_key].tops(measured_box=measured.get(prop_stem)))
            mesh = furniture_meshes[mesh_key]
            surfaces[mesh_key] = {'sha256': sha(assets.read(mesh_key)), 'lod': mesh.lod,
                                'model_center': list(mesh.center)}
            for local, support in furniture_tops[mesh_key]:
                above = [hit[0] for hit in mesh.hits(local[0], local[2]) if hit[0] > local[1] + .025]
                open_shelf = '_open' in proxy_model or stem in {'shelf', 'shelf_1side', 'shelf_dz', 'library_a', 'case_cans_b', 'bed_stacked', 'bar_shelves_dz', 'rack_dz', 'tools_racking_dz', 'vojenska_palanda'}
                # Closed cabinets admit only the exposed top. Open shelves may
                # use a lower tier only with clearance for the loader's .5m box.
                if above and (not open_shelf or min(above) - local[1] < .55):
                    continue
                point = stock_point(transform, local)
                if floor is None or point[1] < floor + .30 or near(point, existing):
                    continue
                candidates.append((point, {'model': proxy_model, 'support_model': mesh_key,
                    'proxy_offset': match.start(), 'surface': role(stem),
                    'local_point': [round(v, 8) for v in local],
                    'transform': [round(v, 8) for v in transform], **support}))
        try:
            baked = reader.mesh(data, restore_center=False)
        except (ValueError, reader.module.ODOL_Error):
            rejected['baked-mesh-unreadable'] += 1
        else:
            floors = [[float(v) for v in point.get('pos').split()]
                      for container in group.findall('container')
                      if 'floor' in container.get('name', '').lower()
                      for point in container.findall('point')]
            def in_room(x, y, z):
                return (any(.35 <= y - q[1] <= 2.20
                            and math.hypot(z - q[0], -x - q[2]) <= 6 for q in floors)
                        and not any(abs(y - q[1]) < .20 for q in floors))

            for local, support in baked.tops(in_room):
                point = [round(local[2], 6), round(local[1], 6), round(-local[0], 6)]
                # Native floor points locate an occupied room/storey. Reject
                # structural floors themselves, roofs and uncovered exterior ledges.
                if near(point, existing):
                    continue
                ceilings = [hit[0] for hit in baked.hits(local[0], local[2])
                            if hit[0] > local[1] + .10]
                if not ceilings or not .55 <= min(ceilings) - local[1] <= 3.5:
                    continue
                candidates.append((point, {'model': model, 'surface': 'baked-interior-ledge',
                    'local_point': [round(v, 8) for v in local], **support}))
        context = auditor.scene(name, {'stock_sha256': loot.group_pin(group),
                                      'building_model_sha256': sha(data)}) if candidates else None
        # Spread admission over furniture roles and heights before filling the cap.
        by_role = {}
        for point, evidence in candidates:
            by_role.setdefault(evidence['surface'], deque()).append((point, evidence))
        chosen, evidence = [], []
        while any(by_role.values()) and len(chosen) < loot.MAX_SURFACE_POINTS:
            for key in sorted(by_role):
                if not by_role[key] or len(chosen) >= loot.MAX_SURFACE_POINTS:
                    continue
                point, source = by_role[key].popleft()
                if near(point, chosen):
                    continue
                failures, _ = auditor.check(point, source, context, auditor.templates.get(name, []),
                                            stop_on_refusal=True)
                audit_checked += 1
                if failures:
                    audit_refusals.update(failures)
                    continue
                chosen.append(point)
                evidence.append(source)
        total = sum(len(s['surface_sources']) for s in groups.values()) + len(chosen)
        print(f'admitted {name} points={len(chosen)} total={total}', file=sys.stderr, flush=True)
        if not chosen:
            rejected['no-admissible-top'] += 1
            refused[name] = 'no-admissible-top'
            continue
        family = loot.family_of(name, policy)
        family_name = family['family'] if family else 'civic'
        categories = list(family['surface']['categories']) if family else ['books', 'tools']
        if family_name == 'residential':
            categories = ['food', 'tools', 'books', 'clothes', 'containers']
        if 'Hunting' in {u.get('name') for u in group.findall('usage')}:
            categories = ['weapons', 'tools', 'food', 'clothes']
        if re.search(r'Mil_|Tisy_|Guardhouse|Police|Prison', name):
            categories = ['weapons', 'explosives', 'tools', 'clothes'] if 'Mil_' in name or 'Tisy_' in name else ['weapons', 'tools', 'books']
        groups[name] = {'family': family_name, 'stock_sha256': loot.group_pin(group),
            'building_model': model, 'building_model_sha256': sha(data),
            'containers': {'lootHCSurface': {'lootmax': loot.added_lootmax(len(chosen)),
                'categories': categories, 'tags': ['shelves'], 'points': chosen}},
            'surface_sources': evidence}
        if map_pos is not None:
            groups[name]['map_instances'] = placements[name]
        if name in templates:
            groups[name]['interior_template'] = templates[name]
    doc = {'schema': 1, 'kind': loot.OVERLAY_KIND, 'runtime_acceptance': loot.PENDING,
        'frame': 'stock-mapgroupproto', 'caps': {'surface_per_group': loot.MAX_SURFACE_POINTS,
        'added_container_lootmax': loot.MAX_ADDED_LOOTMAX, 'total_points': loot.MAX_TOTAL_POINTS},
        'sources': {'stock_proto_sha256': sha(stock_bytes),
        'method': 'ODOL56 visual horizontal face support with 12cm footprint; raw building frame, restored furniture centres; 0.15m candidate lattice and measured prop centres snapped to mesh tops; 5mm lift; .60m separation; reach audit before cap including optional-prop corridor and eye obstruction; optional props never support',
        'prop_boxes_sha256': sha(auditor.boxes_bytes),
        'reach_generation': {'checked_candidates': audit_checked,
            'refusal_counting': 'stop after the first failed support/room/clearance stage; final read-only audit collects all reasons',
            'refusal_counts': dict(sorted(audit_refusals.items()))},
        'reader_repository': 'https://github.com/SXDIST/DayZObjectBuilder',
        'reader_revision': READER_REVISION, 'reader_sha256': READER_HASHES,
        'eligible_stock_groups': len(groups) + len(refused),
        'eligible_placed_groups': sum(placements[n] > 0 for n in groups.keys() | refused.keys()),
        'eligible_map_instances': sum(placements[n] for n in groups.keys() | refused.keys()),
        'model_surfaces': surfaces, 'rejected_counts': dict(sorted(rejected.items())),
        'rejected_groups': dict(sorted(refused.items()))}, 'groups': groups}
    if map_pos is not None:
        doc['sources']['map_pos_sha256'] = sha(Path(map_pos).read_bytes())
    raw = (json.dumps(doc, sort_keys=True, indent=2) + '\n').encode()
    loot.parse_overlay(raw)
    return raw


def report(raw):
    doc = loot.parse_overlay(raw)
    counts = {}
    for group in doc['groups'].values():
        row = counts.setdefault(group['family'], [0, 0])
        row[0] += 1
        row[1] += len(group['containers']['lootHCSurface']['points'])
    for family, (groups, points) in sorted(counts.items()):
        print(f'{family}: groups={groups} points={points}')
    print('TOTAL groups=%d points=%d sha256=%s' % (
        sum(c[0] for c in counts.values()), sum(c[1] for c in counts.values()), sha(raw)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--addons', type=Path, required=True)
    parser.add_argument('--stock-proto', type=Path, required=True)
    parser.add_argument('--reader', type=Path, required=True, help='external pinned ODOL reader directory (see docs/LOOT_POINTS.md)')
    parser.add_argument('--map-pos', type=Path, help='stock mapgrouppos.xml for instance counts')
    parser.add_argument('--out', type=Path, default=OUTPUT)
    args = parser.parse_args()
    raw = generate(args.addons, args.stock_proto, args.reader, args.map_pos)
    args.out.write_bytes(raw)
    report(raw)


if __name__ == '__main__':
    main()
