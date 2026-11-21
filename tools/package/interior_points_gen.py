"""Generate CE candidates from vanilla furniture proxies and baked room surfaces.

Run as a module with --addons and --stock-proto. Assets stay external; only
hashes, transforms and candidate coordinates enter the overlay. This is static
support evidence, not native collision/clearance or CE acceptance. Optional
runtime furnishings never count as unconditional support. Use --partition INDEX COUNT
with a separate --out for bounded scans; --merge-partitions joins a complete set.
--prior-overlay re-audits and adds compatible points from a previous layout.
"""
import argparse
from collections import Counter, deque
import copy
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
    'ch_mod_c', 'ch_mod_h', 'ch_office_b', 'kitchen_chair_a',
    'office_chair', 'student_chair', 'dkamna_bila', 'dkamna_uhli',
    'radar_panel_flat', 'radar_electronics', 'radar_rack', 'radar_rack_quad',
    'anvil', 'metal_cutting_saw', 'soustruh_proxy', 'basin_a', 'sink', 'lab_sink',
    'tent_table', 'tent_boxwooden', 'tent_stretcher', 'tent_chair',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Assets:
    def __init__(self, folder):
        self.members, self.classes = {}, {}
        folder = Path(folder)
        # Fire extinguishers are baked building blockers in gear_tools, not
        # furniture candidates. Include their installed model without importing
        # unrelated item/vehicle assets or changing building config precedence.
        paths = sorted(folder.glob('structures*.pbo')) + [folder / 'gear_tools.pbo']
        for path in paths:
            if not path.is_file():
                continue
            index = pbo.read_pbo_index(path)
            if path.name.startswith('structures'):
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


def proxy_table(data, model, lod):
    """Read only the bounded proxy table at this decoded LOD's start address.

    ODOL56: u32 count, NUL path, 12 float matrix, four u32 indices. This
    independently identifies installed proxies instead of scanning all bytes
    (which can confuse visual LODs and other strings with collision proxies).
    """
    start, end = model.lod_starts[lod.index], model.lod_ends[lod.index]
    count = struct.unpack_from('<I', data, start)[0]
    offset = start + 4
    if count > 10000:
        raise ValueError('proxy table count outside bound')
    for _ in range(count):
        stop = data.find(b'\0', offset, min(end, offset + 1024))
        if stop < 0 or stop + 65 > end:
            raise ValueError('truncated proxy table')
        path = pbo.normalize_path(data[offset:stop].decode('ascii'))
        if not path.endswith('.p3d'):
            path += '.p3d'
        matrix = struct.unpack_from('<12f', data, stop + 1)
        if not all(math.isfinite(v) and abs(v) < 1000 for v in matrix):
            raise ValueError('invalid proxy matrix')
        # Reject scaled/sheared/corrupt transforms, retain actual rigid tilts.
        axes = (matrix[:3], matrix[3:6], matrix[6:9])
        if any(abs(sum(x*y for x, y in zip(a, b)) - (i == j)) > .002
               for i, a in enumerate(axes) for j, b in enumerate(axes)):
            raise ValueError('non-rigid proxy matrix')
        yield path, matrix
        offset = stop + 65


def stock_proxies(data, model):
    """Unique actual proxy-table entries from visual and collision LODs.

    Selection names such as table.001 are not model members. Never guess a
    suffix alias or parse a matrix after an arbitrary embedded string.
    """
    seen = set()
    for lod in model.lods:
        if lod.resolution >= 1000 and not any(
                math.isclose(lod.resolution, resolution, rel_tol=1e-6)
                for resolution in (1e13, 3e15, 6e15)):
            continue
        for path, matrix in proxy_table(data, model, lod):
            key = (path, matrix)
            if key not in seen:
                seen.add(key)
                yield path, matrix


def surface_model(model):
    stem = model.rsplit('\\', 1)[-1].removesuffix('.p3d')
    if stem.startswith('locker_'):
        return 'locker', re.sub(r'locker_open', 'locker_closed', model)
    if stem in {'bed_stacked', 'foldingbed_open', 'hospital_transport_bed'}:
        return stem, model
    closed = stem.removesuffix('_open')
    if closed + '_closed' in TOPS:
        closed += '_closed'
    if closed in TOPS:
        return closed, model.replace(stem + '.p3d', closed + '.p3d')
    # Installed stock furniture need not be named in the contextual alias list.
    # The mesh, collision, enclosure and reach gates decide whether a top is
    # usable; names alone neither grant support nor exclude an evidenced top.
    if '\\furniture\\' in model:
        return stem, model
    # Installed composite interiors carry baked counters/tables outside the
    # furniture directory. Ruined furniture and workshop pallets likewise use
    # building-specific proxy directories. These are proposals only: all mesh,
    # collision, enclosure and independent approach gates remain mandatory.
    if (stem.endswith(('_int', '_interior', '_interier', '_interier_proxy', '_grnd_proxy', '_details_proxy'))
            or re.fullmatch(r'ruin_house\w+_proxy_0[1-9]', stem)
            or ('\\ruins\\proxy\\' in model and stem.startswith((
                'table_', 'shelfs_', 'racks_', 'wardrobe_', 'bed_',
                'classroom_case_', 'tools_racking')))
            or stem in {'misc_pallet', 'misc_pallets1', 'misc_pallets2', 'misc_pallets3',
                        'misc_boxwooden', 'misc_table_large', 'misc_woodtable_indoor',
                        'chapel_table_proxy', 'chapel_table_proxy2', 'table',
                        'shelfs_small', 'racks', 'tent_ltable', 'tent_pallets',
                        # Installed composite room/workshop members identified
                        # from actual building proxy tables, not guessed aliases.
                        'tb_lobby', 'school_details', 'showertent_furniture',
                        'houseb_tenement_dayz_proxy', 'barn_metal_lod1_proxy',
                        'ind_sawmill_saw', 'misc_woodencrate_5x',
                        'ruin_housesmall2_proxy'}
            or re.fullmatch(r'dieselpowerplant_building_accessories_[1-4]', stem)):
        return stem, model
    return None


def role(stem):
    if stem.startswith('kicthen_') or stem in {'kitchen_table_a', 'table_umakart', 'icebox', 'skrin_bar', 'shelf', 'shelf_1side', 'pult', 'pultskasou', 'fridge', 'kitchen_unit_a_dz', 'kitchenstove_elec'}:
        return 'kitchen-counter'
    if ('matress' in stem or stem.startswith(('postel_', 'stretcher_'))
            or stem in {'bed_stacked', 'foldingbed_open', 'hospital_transport_bed', 'vojenska_palanda'}):
        return 'bed-mattress'
    if ('sofa' in stem or 'couch' in stem or stem.endswith('_bench')
            or 'chair' in stem or stem.startswith('ch_')
            or stem in {'church_chair', 'lobby_chair'}):
        return 'bench-seat'
    if stem in {'washing_machine', 'piano', 'dkamna_bila', 'dkamna_uhli'}:
        return 'appliance-top'
    if stem in {'medical_table', 'lab_sink'}:
        return 'medical-tray'
    if stem in {'lekarnicka', 'basin_a', 'sink'}:
        return 'bathroom-cabinet'
    if ('workbench' in stem or 'crate' in stem
            or stem in {'anvil', 'metal_cutting_saw', 'soustruh_proxy'}):
        return 'repair-bench'
    if stem == 'locker':
        return 'locker-top'
    if stem in {'almara', 'case_a', 'dhangar_brownskrin', 'dhangar_brownskrin_old'}:
        return 'wardrobe-top'
    if 'desk' in stem or 'table' in stem:
        return 'desk-table'
    if stem not in TOPS:
        return 'static-proxy-surface'
    return 'cabinet-shelf'


# Loot tells the story of the furniture it sits on (owner, 2026-11-20). Each
# admitted top votes for the vanilla CE categories of its room: vanilla puts
# medical supplies, paper and hand tools in "tools" and canteens in "food".
# The building keeps its stock <usage> (Town, Medic, Military...), which the
# CE applies on top, so a farmhouse kitchen and a hospital cabinet differ.
ROLE_CATEGORIES = {
    'kitchen-counter': ('food', 'tools'),
    'appliance-top': ('food', 'tools'),
    'bed-mattress': ('clothes', 'containers'),
    'wardrobe-top': ('clothes', 'containers'),
    'locker-top': ('clothes', 'tools'),
    'bench-seat': ('clothes', 'books'),
    'desk-table': ('books', 'tools'),
    'cabinet-shelf': ('books', 'tools', 'containers'),
    'bathroom-cabinet': ('tools',),
    'medical-tray': ('tools',),
    'repair-bench': ('tools', 'containers'),
    'static-proxy-surface': ('tools', 'containers'),
    'baked-interior-ledge': ('tools', 'food'),
}


def story_categories(name, group, family_name, roles):
    """Surface categories from the admitted furniture roles plus the building's identity."""
    weight = Counter()
    for item in roles:
        for rank, category in enumerate(ROLE_CATEGORIES.get(item, ('tools',))):
            weight[category] += 1 / (rank + 1)
    categories = [c for c, _ in sorted(weight.items(), key=lambda kv: (-kv[1], kv[0]))]
    usages = {u.get('name') for u in group.findall('usage')} if group is not None else set()
    armed = []
    if 'Mil_' in name or 'Tisy_' in name or family_name == 'military':
        armed = ['weapons', 'explosives']
    elif re.search(r'Police|Prison|Guardhouse', name) or 'Hunting' in usages:
        armed = ['weapons']
    if family_name == 'kitchen' and 'food' not in categories:
        categories.insert(0, 'food')
    if family_name in ('medical', 'fire') and 'tools' not in categories:
        categories.insert(0, 'tools')
    return armed + [c for c in categories if c not in armed] or ['tools']


def surface_cap(area_m2):
    """Surface spawn spots by reached interior floor: one per 3 m2, 4..32."""
    if area_m2 is None:
        return loot.MAX_SURFACE_POINTS
    return max(4, min(loot.MAX_SURFACE_POINTS, math.ceil(area_m2 / 3)))


def interior_area(name, group, context, templates):
    """Reached walkable floor area (m2) of one building, or None without anchors."""
    slots = [slot for _, t in templates for slot in t.get('PropSlots', [])]
    _, cells, _ = floor_cells(name, group, context, slots)
    return round(cells[2] * FLOOR_STEP * FLOOR_STEP, 2) if cells else None


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
        markers = {index for selection in lod.named_selections
                   if selection.name.lower().startswith('proxy:')
                   for index in selection.faces}
        for face_index, face in enumerate(lod.faces):
            if face_index in markers:
                continue
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

    def tops(self, accept=None, measured_box=None, height_accept=None):
        seen = set()
        for triangle, normal_y, face in self.triangles:
            if normal_y < .85 or max(v[1] for v in triangle) - min(v[1] for v in triangle) > .025:
                continue
            if height_accept is not None and not height_accept(
                    min(v[1] for v in triangle) + .005,
                    max(v[1] for v in triangle) + .005):
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
            # A finer proposal lattice recovers supported strips missed between
            # the old columns. Admission footprints and .60m output spacing do
            # not change; more samples are never evidence by themselves.
            step = .10
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


# Furniture collision tops are authored a little above their visual tops:
# measured +0.4..1.3 cm on skrin_bar, +1.9 cm Geometry / +3.2 cm Roadway on
# lobby_table. A point 5 mm above the visual top then sits inside the
# furniture's own collision slab, and the collision audit refuses it as
# "collision above item support". Lift a visual candidate onto the highest
# Geometry/Roadway horizontal plane of the same prop at most this far above
# its visual top. Larger offsets stay refused: that is a different surface.
COLLISION_LIFT = .05
COLLISION_LODS = (1e13, 3e15)  # Geometry, Roadway


class CollisionTops:
    """Horizontal Geometry/Roadway faces of one prop in its restored local frame."""
    def __init__(self, model):
        from tools.package.loot_reach_audit import collision_triangles, lod_for
        self.triangles, self.cells = [], {}
        for resolution in COLLISION_LODS:
            lod = lod_for(model, resolution)
            if lod is None:
                continue
            for tri in collision_triangles(model, lod):
                ax, ay, az = (tri[1][a] - tri[0][a] for a in range(3))
                bx, by, bz = (tri[2][a] - tri[0][a] for a in range(3))
                normal = (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)
                length = math.sqrt(sum(v * v for v in normal))
                if (not length or abs(normal[1]) / length < .98
                        or max(v[1] for v in tri) - min(v[1] for v in tri) > .025):
                    continue
                index = len(self.triangles)
                self.triangles.append(tri)
                for x in range(math.floor(min(v[0] for v in tri) / .65),
                               math.floor(max(v[0] for v in tri) / .65) + 1):
                    for z in range(math.floor(min(v[2] for v in tri) / .65),
                                   math.floor(max(v[2] for v in tri) / .65) + 1):
                        self.cells.setdefault((x, z), []).append(index)

    def heights(self, x, z):
        found = []
        for index in self.cells.get((math.floor(x / .65), math.floor(z / .65)), ()):
            y = triangle_height(self.triangles[index], x, z)
            if y is not None:
                found.append(y)
        return found

    def lift(self, local):
        """Metres to raise a 5 mm-lifted visual top onto its own collision top."""
        visual = local[1] - .005
        above = [y for y in self.heights(local[0], local[2])
                 if visual < y <= visual + COLLISION_LIFT]
        return max(above) - visual if above else 0.0


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


def generate(addons, stock_proto, reader_folder, map_pos=None, partition=None):
    # Reuse the independent audit without relaxing any of its limits. Evaluate
    # before spacing/capping so refused candidates do not crowd out good tops.
    from tools.package.loot_reach_audit import Audit
    from tools.package.loot_support_audit import Audit as SupportAudit
    auditor = Audit(addons, reader_folder, stock_proto, ROOT)
    support_auditor = SupportAudit(addons, reader_folder, stock_proto)
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
    ordered = sorted(stock.findall('group'), key=lambda g: g.get('name', ''))
    if partition is not None:
        index, count = partition
        if not 0 <= index < count <= 32:
            raise ValueError('partition requires 0 <= index < count <= 32')
        ordered = ordered[index::count]
    for group in ordered:
        # Bound decoded prop/scene caches to one building instead of retaining
        # every visited model for the whole map scan. Output retains only pins,
        # coordinates and small witnesses, independent of these caches.
        context = support_context = decoded = baked = mesh = None
        furniture_meshes.clear()
        furniture_tops.clear()
        auditor.props.clear()
        auditor.meshes.clear()
        auditor.lifts.clear()
        assets.cache.clear()
        support_auditor.props.clear()
        support_auditor.assets.cache.clear()
        support_auditor.context_cache = None
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
        memory_anchors = None
        if not existing:
            # No native point at all (stock lootmax 0): the model's own loot
            # memory points on its collision floors locate rooms instead.
            anchor_context = auditor.scene(name, {'stock_sha256': loot.group_pin(group),
                                                  'building_model_sha256': sha(data)})
            memory_anchors = [[a[2], a[1], -a[0]] for a in anchor_context[5]]
            floor = min((a[1] for a in memory_anchors), default=None)
        candidates, seen = [], set()
        decoded = reader.module.ODOL_File.read(io.BytesIO(data))
        for proxy_model, transform in stock_proxies(data, decoded):
            kind = surface_model(proxy_model)
            if kind is None or proxy_model not in assets.members:
                continue
            stem, closed = kind
            if closed not in assets.members:
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
                lifts = CollisionTops(reader.module.ODOL_File.read(io.BytesIO(assets.read(mesh_key))))
                tops = []
                for local, support in furniture_meshes[mesh_key].tops(measured_box=measured.get(prop_stem)):
                    lift = lifts.lift(local)
                    if lift > 0:
                        local = [local[0], local[1] + lift, local[2]]
                        support = dict(support, collision_lift_m=round(lift, 6))
                    tops.append((local, support))
                furniture_tops[mesh_key] = tops
            mesh = furniture_meshes[mesh_key]
            surfaces[mesh_key] = {'sha256': sha(assets.read(mesh_key)), 'lod': mesh.lod,
                                'model_center': list(mesh.center)}
            for local, support in furniture_tops[mesh_key]:
                above = [hit[0] for hit in mesh.hits(local[0], local[2]) if hit[0] > local[1] + .025]
                # Every shelf tier needs actual empty volume and an independent
                # standing/approach witness. A cabinet name is not evidence that
                # the mesh is closed (several stock cases have exposed tiers).
                if above and min(above) - local[1] < .55:
                    continue
                point = stock_point(transform, local)
                if floor is None or point[1] < floor + .30 or near(point, existing):
                    continue
                candidates.append((point, {'model': proxy_model, 'support_model': mesh_key,
                    'surface': role(stem),
                    'local_point': [round(v, 8) for v in local],
                    'transform': [round(v, 8) for v in transform], **support}))
        try:
            baked = Mesh(decoded, restore_center=False)
        except (ValueError, reader.module.ODOL_Error):
            rejected['baked-mesh-unreadable'] += 1
        else:
            floors = [[float(v) for v in point.get('pos').split()]
                      for container in group.findall('container')
                      if 'floor' in container.get('name', '').lower()
                      for point in container.findall('point')]
            if memory_anchors is not None:
                floors = memory_anchors
            def in_room(x, y, z):
                return (any(.35 <= y - q[1] <= 2.20
                            and math.hypot(z - q[0], -x - q[2]) <= 6 for q in floors)
                        and not any(abs(y - q[1]) < .20 for q in floors))

            def room_height(low, high):
                # Reject only planes wholly outside the room-height bands.
                # A sloped face straddling a boundary still gets sampled.
                return (any(high >= q[1] + .35 and low <= q[1] + 2.20 for q in floors)
                        and not any(q[1] - .20 < low <= high < q[1] + .20 for q in floors))

            for local, support in baked.tops(in_room, height_accept=room_height):
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
        support_context = support_auditor.context(name, {
            'stock_sha256': loot.group_pin(group),
            'building_model_sha256': sha(data)}) if candidates else None
        area = interior_area(name, group, context, auditor.templates.get(name, [])) if context else None
        cap = surface_cap(area)
        # Spread admission over furniture roles and heights before filling the cap.
        by_role = {}
        for point, evidence in candidates:
            by_role.setdefault(evidence['surface'], []).append((point, evidence))
        # Pack from one edge of each support plane instead of privileging face
        # centroids. A centre-first choice can consume both usable ends of a
        # table under the unchanged .60m separation rule. Every sampled edge
        # still has the same visual footprint, collision and reach requirements.
        by_role = {key: deque(sorted(rows, key=lambda row: (
                       round(row[0][1], 2), row[0][2], row[0][0], row[0][1])))
                   for key, rows in by_role.items()}
        chosen, evidence = [], []
        while any(by_role.values()) and len(chosen) < cap:
            for key in sorted(by_role):
                if not by_role[key] or len(chosen) >= cap:
                    continue
                point, source = by_role[key].popleft()
                if near(point, chosen):
                    continue
                audit_checked += 1
                # Failed collision candidates must not consume spacing or cap
                # slots: a nearby visually similar top may have real support.
                reason, _ = support_auditor.check(name, point, support_context)
                if reason:
                    audit_refusals[reason] += 1
                    continue
                failures, _ = auditor.check(point, source, context, auditor.templates.get(name, []),
                                            stop_on_refusal=True)
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
        categories = story_categories(name, group, family_name, [e['surface'] for e in evidence])
        groups[name] = {'family': family_name, 'stock_sha256': loot.group_pin(group),
            'building_model': model, 'building_model_sha256': sha(data),
            'containers': {'lootHCSurface': {'lootmax': loot.added_lootmax(len(chosen), area),
                'categories': categories, 'tags': ['shelves'], 'points': chosen}},
            'surface_sources': evidence}
        if area is not None:
            groups[name]['interior_area_m2'] = area
        if map_pos is not None:
            groups[name]['map_instances'] = placements[name]
        if name in templates:
            groups[name]['interior_template'] = templates[name]
    doc = {'schema': 1, 'kind': loot.OVERLAY_KIND, 'runtime_acceptance': loot.PENDING,
        'frame': 'stock-mapgroupproto', 'caps': {'surface_per_group': loot.MAX_SURFACE_POINTS,
        'added_container_lootmax': loot.MAX_ADDED_LOOTMAX, 'total_points': loot.MAX_TOTAL_POINTS},
        'sources': {'stock_proto_sha256': sha(stock_bytes),
        'method': 'ODOL56 visual horizontal face support with 12cm footprint; bounded decoded visual/collision proxy tables, composite interior and exposed cabinet tiers; proxy marker faces excluded; raw building frame, restored furniture centres; 0.10m candidate lattice and measured prop centres snapped to mesh tops; 5mm lift; Z-edge-first plane ordering with .60m separation; collision and reach audits before spacing/cap including full optional-prop item/body volumes, swept corridor and eye obstruction; optional props never support',
        'prop_boxes_sha256': sha(auditor.boxes_bytes),
        'reach_generation': {'checked_candidates': audit_checked,
            'refusal_counting': 'collision support/enclosure, then visual/room/clearance/reach; stop on refusal; all checks before spacing/cap; final read-only audit collects all reach reasons',
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
    # Visual meshes only propose candidates. Collision support and building
    # enclosure are mandatory final admission, including stock proxy furniture.
    doc, _ = SupportAudit(addons, reader_folder, stock_proto).filter(doc)
    doc['sources']['method'] += '; final collision-only support/enclosure gate (see collision_support)'
    if partition is not None:
        doc['sources']['generation_partition'] = {'index': partition[0], 'count': partition[1]}
    raw = (json.dumps(doc, sort_keys=True, indent=2) + '\n').encode()
    loot.parse_overlay(raw)
    return raw


def merge_partitions(paths, addons, stock_proto, reader_folder, prior_overlay=None):
    """Join a complete disjoint scan and re-audit complementary prior points.

    A larger valid point set gets first choice, followed by compatible points
    from the other set. Caps and spacing are unchanged. Old coordinates never
    reserve space before passing the current collision and reach gates.
    """
    from tools.package.loot_reach_audit import Audit
    from tools.package.loot_support_audit import Audit as SupportAudit
    if not 1 <= len(paths) <= 32:
        raise ValueError('require 1..32 generation partitions')
    inputs = [(Path(path).read_bytes(), path) for path in paths]
    parts = [loot.parse_overlay(raw) for raw, _ in inputs]
    if not parts:
        raise ValueError('no generation partitions')
    partitions = [part['sources'].get('generation_partition', {}) for part in parts]
    if (any(p.get('count') != len(parts) for p in partitions)
            or sorted(p.get('index', -1) for p in partitions) != list(range(len(parts)))):
        raise ValueError('require every disjoint generation partition exactly once')
    doc = copy.deepcopy(parts[0])
    sources = doc['sources']
    sources.pop('generation_partition')
    sources.pop('collision_support')
    doc['groups'] = {}
    sources['model_surfaces'] = {}
    sources['rejected_groups'] = {}
    rejected, refusals = Counter(), Counter()
    for key in ('eligible_stock_groups', 'eligible_placed_groups', 'eligible_map_instances'):
        sources[key] = sum(part['sources'][key] for part in parts)
    for part in parts:
        for key in ('stock_proto_sha256', 'map_pos_sha256', 'prop_boxes_sha256',
                    'reader_revision', 'reader_sha256', 'method'):
            if part['sources'].get(key) != sources.get(key):
                raise ValueError('partition source mismatch: ' + key)
        if set(doc['groups']) & set(part['groups']):
            raise ValueError('overlapping generation partitions')
        doc['groups'].update(part['groups'])
        sources['model_surfaces'].update(part['sources']['model_surfaces'])
        sources['rejected_groups'].update(part['sources']['rejected_groups'])
        rejected.update(part['sources']['rejected_counts'])
        refusals.update(part['sources']['reach_generation']['refusal_counts'])
    sources['rejected_counts'] = dict(sorted(rejected.items()))
    sources['reach_generation']['checked_candidates'] = sum(
        p['sources']['reach_generation']['checked_candidates'] for p in parts)
    sources['reach_generation']['refusal_counts'] = dict(sorted(refusals.items()))
    sources['generation_partitions'] = {'count': len(parts),
        'method': 'complete disjoint sorted stock-group round robin; full original stock pin in every partition',
        'input_sha256': [sha(raw) for raw, _ in inputs]}
    if sources['stock_proto_sha256'] != sha(Path(stock_proto).read_bytes()):
        raise ValueError('partition stock prototype pin mismatch')
    if prior_overlay is not None:
        raw = Path(prior_overlay).read_bytes()
        prior = loot.parse_overlay(raw)
        if prior['sources']['stock_proto_sha256'] != sources['stock_proto_sha256']:
            raise ValueError('prior stock prototype pin mismatch')
        for model, pin in prior['sources']['model_surfaces'].items():
            if model in sources['model_surfaces'] and sources['model_surfaces'][model] != pin:
                raise ValueError('prior model pin mismatch: ' + model)
            sources['model_surfaces'][model] = pin
        auditor = Audit(addons, reader_folder, stock_proto, ROOT)
        collision = SupportAudit(addons, reader_folder, stock_proto)
        refused = Counter()
        added = 0
        for name, old in prior['groups'].items():
            context = support_context = None
            auditor.props.clear()
            auditor.meshes.clear()
            auditor.lifts.clear()
            auditor.assets.cache.clear()
            collision.props.clear()
            collision.assets.cache.clear()
            collision.context_cache = None
            print('merge ' + name, file=sys.stderr, flush=True)
            current = doc['groups'].get(name)
            if current and any(current[key] != old[key] for key in (
                    'family', 'stock_sha256', 'building_model_sha256')):
                raise ValueError('prior building pin/family mismatch: ' + name)
            if current and (current['containers']['lootHCSurface']['tags']
                            != old['containers']['lootHCSurface']['tags']):
                raise ValueError('prior tag mismatch: ' + name)
            context = auditor.scene(name, old)
            support_context = collision.context(name, old)
            sets = []
            for spec in (current, old):
                valid = []
                if spec:
                    for point, evidence in zip(spec['containers']['lootHCSurface']['points'],
                                               spec['surface_sources']):
                        reason, _ = collision.check(name, point, support_context)
                        failures, _ = auditor.check(point, evidence, context,
                            auditor.templates.get(name, []), stop_on_refusal=True) if not reason else ([], None)
                        if reason or failures:
                            refused.update([reason] if reason else failures)
                        else:
                            valid.append((point, evidence))
                sets.append(valid)
            chosen = []
            area = (current or {}).get('interior_area_m2')
            if area is None:
                area = interior_area(name, auditor.stock.get(name), context, auditor.templates.get(name, []))
            cap = surface_cap(area)
            layouts = sorted(sets, key=len, reverse=True)
            for point, evidence in layouts[0] + layouts[1]:
                if len(chosen) < cap and not near(point, [p for p, _ in chosen]):
                    chosen.append((point, evidence))
            if not chosen:
                doc['groups'].pop(name, None)
                continue
            added += len(chosen) - (len(current['surface_sources']) if current else 0)
            spec = copy.deepcopy(current or old)
            spec['containers']['lootHCSurface']['points'] = [p for p, _ in chosen]
            spec['containers']['lootHCSurface']['lootmax'] = loot.added_lootmax(len(chosen), area)
            spec['containers']['lootHCSurface']['categories'] = story_categories(
                name, auditor.stock.get(name), spec['family'], [e['surface'] for _, e in chosen])
            spec['surface_sources'] = [e for _, e in chosen]
            if area is not None:
                spec['interior_area_m2'] = area
            spec.pop('collision_support', None)
            doc['groups'][name] = spec
        sources['prior_overlay_selection'] = {'sha256': sha(raw), 'net_added_points': added,
            'prior_method': prior['sources']['method'],
            'prior_reach_generation': prior['sources']['reach_generation'],
            'net_points_vs_prior': sum(len(g['surface_sources']) for g in doc['groups'].values())
                                   - sum(len(g['surface_sources']) for g in prior['groups'].values()),
            'method': 're-audit both sets; prefer larger passing layout then append compatible points; same spacing; area cap and story categories from the final layout',
            'refusal_counts': dict(sorted(refused.items()))}
    for name in doc['groups']:
        reason = sources['rejected_groups'].pop(name, None)
        if reason is not None:
            rejected[reason] -= 1
    sources['rejected_counts'] = {key: value for key, value in sorted(rejected.items()) if value}
    doc, _ = SupportAudit(addons, reader_folder, stock_proto).filter(doc)
    encoded = (json.dumps(doc, sort_keys=True, indent=2) + '\n').encode()
    loot.parse_overlay(encoded)
    return encoded


FLOOR_OUTPUT = ROOT / loot.ADDITIONS
FLOOR_STEP = .50      # walk lattice; one HC floor point per CELLS_PER_POINT m2 reached
FLOOR_LIFT = .005     # same lift as surface points above their collision plane
FLOOR_RANGE = float(loot.POINT_SHAPE['floor'][0])
FLOOR_METHOD = ('hc-floor-v2: native stock points on building Geometry/Roadway floors seed a '
                '0.50m walk lattice; every cell needs a clear standing body (0.22m radius, 1.8m) '
                'and a swept same-storey corridor with sampled floor from a reached neighbour '
                '(closed doors block); points avoid stock spawn discs (stock range + 0.5m), '
                '1.0m of door leaves and stair steps (highest collision plane at each neighbour, '
                'never slab undersides); floor item base clears the highest Geometry/Roadway '
                'footprint sample by 5mm (local height span <=25mm); wall-side cells first, '
                'farthest-point spacing 1.5m, '
                'one point per 8m2 reached (2..12); collision support/enclosure gate before admission; '
                'optional props block bodies and points')


def floor_story(group, fallback):
    """Floor categories the stock group itself authors for its floor spots, minus firearms.

    Bohemia's own floor containers tell each place's story (a wreck carries food,
    a deer stand tools and clothes, a barracks tools and containers), so HC floor
    points follow them. Any modded item the economy files under those categories
    spawns there too; nothing is limited to a vanilla item list.
    """
    story = []
    for container in group.findall('container'):
        tags = {t.get('name') for t in container.findall('tag')}
        if 'floor' not in container.get('name', '').lower() and 'floor' not in tags and tags:
            continue
        for category in container.findall('category'):
            value = category.get('name')
            if value and value.lower() not in loot.KEPT_CATEGORIES and value not in story:
                story.append(value)
    return story or list(fallback)


def floor_cells(name, group, context, slots, diagnostics=None):
    """Reached floor cells in model frame; optional Counter records first refusals."""
    from tools.package.loot_reach_audit import (
        approach_clear, body_clear, model_point, volume_hit, RADIUS, HEIGHT)
    diagnostics = diagnostics if diagnostics is not None else Counter()
    _, model, _, scene, bounds, _, footprint = context
    if bounds is None:
        return 'no-building-bounds', None, None
    stock = [(model_point([float(v) for v in p.get('pos').split()]), float(p.get('range') or 0))
             for p in group.iter('point')]
    # A native point resting on the building's own floor (not furniture) is
    # the evidence that a storey is occupied and reachable.
    anchors = []
    for p, _ in stock:
        found = footprint.floors(p[0], p[2], p[1] - .12, p[1] + .05)
        if found:
            anchors.append((p[0], found[0], p[2]))
    if not stock:
        anchors = [tuple(a) for a in context[5]]  # memory loot anchors (stock lootmax 0)
    diagnostics['native_floor_anchors'] = len(anchors)
    if not anchors:
        return 'no-native-floor-anchor', None, None
    storeys = sorted({round(a[1], 2) for a in anchors})
    doors = []
    from tools.package.loot_reach_audit import lod_for
    geometry = lod_for(model, 1e13)
    for selection in geometry.named_selections:
        if selection.name.lower().startswith('door'):
            doors.extend(tuple(geometry.vertices[i]) for i in selection.vertices)
    cache = {}

    def cell(ix, iz, level):
        key = (ix, iz, level)
        if key not in cache:
            x, z = ix * FLOOR_STEP, iz * FLOOR_STEP
            found = [y for y in footprint.floors(x, z, level - .20, level + .20)]
            y = found[0] if found else None
            ok = (y is not None and body_clear(scene, (x, y, z))
                  and not any(volume_hit((x, y, z), RADIUS, .06, HEIGHT, s['Bounds']) for s in slots))
            cache[key] = (x, y, z) if ok else None
        return cache[key]

    lo = [math.floor(bounds['Min'][a] / FLOOR_STEP) for a in (0, 2)]
    hi = [math.ceil(bounds['Max'][a] / FLOOR_STEP) for a in (0, 2)]
    reached = {}
    for level in storeys:
        queue = deque()
        for a in anchors:
            if abs(a[1] - level) > .005:
                continue
            for ix in range(math.floor((a[0] - 1) / FLOOR_STEP), math.ceil((a[0] + 1) / FLOOR_STEP) + 1):
                for iz in range(math.floor((a[2] - 1) / FLOOR_STEP), math.ceil((a[2] + 1) / FLOOR_STEP) + 1):
                    c = cell(ix, iz, level)
                    key = (ix, iz, level)
                    if (c and key not in reached and math.hypot(c[0] - a[0], c[2] - a[2]) <= 1.0
                            and approach_clear(scene, a, c, slots)):
                        reached[key] = c
                        queue.append(key)
        while queue:
            ix, iz, _ = queue.popleft()
            here = reached[(ix, iz, level)]
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, nz = ix + dx, iz + dz
                key = (nx, nz, level)
                if key in reached or not (lo[0] <= nx <= hi[0] and lo[1] <= nz <= hi[1]):
                    continue
                c = cell(nx, nz, level)
                if c and approach_clear(scene, here, c, slots):
                    reached[key] = c
                    queue.append(key)
    diagnostics['reached_cells'] = len(reached)
    if not reached:
        return 'no-reachable-floor-cell', None, None
    wall, inner = [], []
    for (ix, iz, level), c in reached.items():
        if any(math.hypot(c[0] - p[0], c[2] - p[2]) < r + FLOOR_RANGE and abs(c[1] - p[1]) <= loot.STOCK_BAND
               for p, r in stock):
            diagnostics['stock_spawn_disc'] += 1
            continue
        if any(math.hypot(c[0] - d[0], c[2] - d[2]) <= loot.DOOR_CLEAR and -.5 <= d[1] - c[1] <= 2.5
               for d in doors):
            diagnostics['door_leaf_clearance'] += 1
            continue
        # Stair treads are walkable but steps make poor loot spots. A slab
        # has a top AND an underside: only its highest neighbouring collision
        # plane can be a walking step. Counting every plane falsely labels an
        # entire flat room as stairs when its slab is 5cm..1.2m thick. Keep
        # the uppermost-plane check conservative around actual raised treads.
        if any(.05 < abs(y - c[1]) <= loot.STAIR_RISE
               for dx, dz in ((.25, 0), (-.25, 0), (0, .25), (0, -.25))
               for y in footprint.floors(c[0] + dx, c[2] + dz, c[1] - loot.STAIR_RISE, c[1] + loot.STAIR_RISE)[:1]):
            diagnostics['stair_neighbour'] += 1
            continue
        side = any((ix + dx, iz + dz, level) not in reached for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        (wall if side else inner).append(c)
    diagnostics['candidate_cells'] = len(wall) + len(inner)
    return None, (sorted(wall), sorted(inner), len(reached)), [p for p, _ in stock]


def floor_candidate(position, support_context):
    """CE frame point just above a locally evidenced collision floor footprint."""
    from tools.package.loot_support_audit import FOOTPRINT, CLEARANCE
    x, y, z = position
    height = y
    if support_context is not None:
        support = support_context[0]
        samples = []
        for dx, dz in FOOTPRINT:
            hits = [h for h, source in support.supports(x+dx, z+dz, y-.025001, y+.025001)
                    if source['kind'] in CLEARANCE]
            if not hits:
                break
            samples.append(max(hits))
        # Tilted Geometry/Roadway floors need the item's horizontal base above
        # their highest footprint sample. Derive that height from real collision
        # only; never offset by a guessed slope or a visual mesh. The 25mm local
        # plane tolerance stays the same as the independent support gate's.
        if len(samples) == len(FOOTPRINT) and max(samples)-min(samples) <= .025:
            height = max(y, max(samples))
    return [round(z, 6), round(height + FLOOR_LIFT, 6), round(-x, 6)]


def generate_floors(addons, stock_proto, reader_folder, map_pos=None, base=None,
                    surfaces=None, partition=None):
    """Floor points for lootable stock groups with no HC floor or surface points yet.

    Existing floor groups in ``base`` are kept as they are and re-audited by the
    shared collision gate. Only stock groups with a native lootmax take part.
    """
    from tools.package.loot_reach_audit import Audit, model_point
    from tools.package.loot_support_audit import Audit as SupportAudit
    auditor = Audit(addons, reader_folder, stock_proto, ROOT)
    support = SupportAudit(addons, reader_folder, stock_proto)
    assets = auditor.assets
    stock_bytes = Path(stock_proto).read_bytes()
    stock = ET.fromstring(stock_bytes)
    placements = Counter()
    if map_pos is not None:
        placements.update(g.get('name') for g in ET.fromstring(Path(map_pos).read_bytes()).findall('group'))
    policy = loot.parse_policy((ROOT / loot.FAMILIES).read_bytes())
    doc = loot.parse_overlay(Path(base).read_bytes()) if base else {
        'schema': 1, 'kind': loot.OVERLAY_KIND, 'frame': 'stock-mapgroupproto',
        'runtime_acceptance': loot.PENDING, 'sources': {}, 'groups': {}}
    covered = set(loot.parse_overlay(Path(surfaces).read_bytes())['groups']) if surfaces else set()
    existing = set(doc['groups'])
    added, refused, refusals, refreshed = {}, {}, Counter(), []
    group_diagnostics = {}
    ordered = sorted(stock.findall('group'), key=lambda g: g.get('name', ''))
    if partition is not None:
        index, count = partition
        if not 0 <= index < count <= 32:
            raise ValueError('partition requires 0 <= index < count <= 32')
        ordered = ordered[index::count]
    for group in ordered:
        name = group.get('name', '')
        auditor.props.clear()
        auditor.meshes.clear()
        auditor.lifts.clear()
        assets.cache.clear()
        support.props.clear()
        support.assets.cache.clear()
        support.context_cache = None
        if name in covered and name not in existing:
            continue
        if map_pos is not None and not placements[name] and name not in existing:
            continue
        # Every lootable place takes part (owner, 2026-11-20): a building outside
        # the families policy takes its floor story from its own stock containers.
        family = loot.family_of(name, policy) or {
            'family': 'stock_story', 'floor': {'categories': ['clothes', 'tools'], 'tags': ['floor']}}
        model = pbo.normalize_path(pbo.resolve_field(assets.classes, name, 'model') or '')
        if model not in assets.members:
            refused[name] = 'missing-model'
            continue
        print('floor ' + name, file=sys.stderr, flush=True)
        spec = {'stock_sha256': loot.group_pin(group), 'building_model_sha256': sha(assets.read(model))}
        try:
            context = auditor.scene(name, spec)
        except ValueError as error:
            refused[name] = 'no-building-geometry' if 'geometry' in str(error) else 'scene-error'
            continue
        slots = [slot for _, t in auditor.templates.get(name, []) for slot in t.get('PropSlots', [])]
        detail = Counter()
        reason, cells, stock_points = floor_cells(name, group, context, slots, detail)
        group_diagnostics[name] = {'floor_cells': detail, 'support_refusals': Counter()}
        if name in existing:
            # Kept floor groups get the same size-realistic lootmax (owner,
            # 2026-11-20: loot numbers follow the building size everywhere).
            kept = doc['groups'][name]
            if cells:
                kept['interior_area_m2'] = round(cells[2] * FLOOR_STEP * FLOOR_STEP, 2)
            if 'lootHCFloor' in kept['containers']:
                kept['containers']['lootHCFloor']['categories'] = floor_story(group, family['floor']['categories'])
            refreshed.append(name)
            continue
        if reason:
            refused[name] = reason
            continue
        wall, inner, area_cells = cells
        if not wall and not inner:
            refused[name] = 'no-spare-floor-cell'
            continue
        support_context = support.context(name, spec)
        area = round(area_cells * FLOOR_STEP * FLOOR_STEP, 2)
        limit = min(loot.MAX_FLOOR_POINTS,
                    max(2, int(area_cells * FLOOR_STEP * FLOOR_STEP) // loot.CELLS_PER_POINT))
        chosen, witnesses, points = [], [], []
        for wall_side, pool in ((True, wall), (False, inner)):
            def spread(c):
                return min((math.hypot(c[0] - q[0], c[2] - q[2]) + 2 * abs(c[1] - q[1])
                            for q in chosen + stock_points), default=1e9)
            def rank(c):
                return spread(c), tuple(-v for v in c)
            # Refusal does not change chosen or any remaining score. Re-sort
            # only after admission, avoiding quadratic ranking over large
            # roofless floors while retaining the same deterministic choices.
            ranked = sorted(pool, key=rank)
            while ranked and len(chosen) < limit:
                best = ranked.pop()
                if any(math.hypot(best[0] - q[0], best[2] - q[2]) < loot.FLOOR_SPACING
                       and abs(best[1] - q[1]) <= loot.STOCK_BAND for q in chosen):
                    continue
                x, y, z = best
                point = floor_candidate(best, support_context)
                why, proof = support.check(name, point, support_context)
                if why:
                    refusals[why] += 1
                    group_diagnostics[name]['support_refusals'][why] += 1
                    continue
                chosen.append(best)
                points.append(point)
                ranked.sort(key=rank)
                witnesses.append({'floor_model': [round(v, 5) for v in best],
                                  'reached_cells': area_cells, 'wall_side': wall_side,
                                  'collision_lift_m': round(point[1] - y - FLOOR_LIFT, 6)})
            if len(chosen) >= 2:
                break
        if not chosen:
            refused[name] = 'no-supported-floor-point'
            continue
        floor = family['floor']
        added[name] = {'family': family['family'], 'stock_sha256': spec['stock_sha256'],
                       'building_model': model, 'building_model_sha256': spec['building_model_sha256'],
                       'containers': {'lootHCFloor': {'lootmax': loot.added_lootmax(len(points), area),
                           'categories': floor_story(group, floor['categories']), 'tags': list(floor['tags']),
                           'points': points}},
                       'floor_sources': witnesses, 'interior_area_m2': area}
        if map_pos is not None:
            added[name]['map_instances'] = placements[name]
        print(f'floor admitted {name} points={len(points)}', file=sys.stderr, flush=True)
    doc['groups'].update(added)
    doc['sources']['hc_floor_generation'] = {
        'method': FLOOR_METHOD, 'stock_proto_sha256': sha(stock_bytes),
        'reader_revision': READER_REVISION, 'reader_sha256': READER_HASHES,
        'kept_groups': len(existing), 'added_groups': len(added), 'area_refreshed_groups': sorted(refreshed),
        'added_points': sum(len(g['containers']['lootHCFloor']['points']) for g in added.values()),
        'skipped_surface_groups': sum(g.get('name', '') in covered - existing for g in ordered),
        'refusal_counts': dict(sorted(refusals.items())),
        'group_diagnostics': group_diagnostics,
        'rejected_groups': dict(sorted(refused.items())),
        'native_acceptance': 'pending'}
    if map_pos is not None:
        doc['sources']['hc_floor_generation']['map_pos_sha256'] = sha(Path(map_pos).read_bytes())
    if partition is not None:
        doc['sources']['hc_floor_generation']['partition'] = {'index': partition[0], 'count': partition[1]}
    doc, _ = SupportAudit(addons, reader_folder, stock_proto).filter(doc)
    raw = (json.dumps(doc, sort_keys=True, indent=2) + '\n').encode()
    loot.parse_overlay(raw)
    return raw


def merge_floor_partitions(paths, base):
    """Join disjoint floor partitions generated from the same base overlay."""
    parts = [loot.parse_overlay(Path(p).read_bytes()) for p in paths]
    infos = [p['sources']['hc_floor_generation'].get('partition', {}) for p in parts]
    if (any(i.get('count') != len(parts) for i in infos)
            or sorted(i.get('index', -1) for i in infos) != list(range(len(parts)))):
        raise ValueError('require every disjoint floor partition exactly once')
    doc = copy.deepcopy(parts[0])
    kept = set(loot.parse_overlay(Path(base).read_bytes())['groups']) if base else set()
    gen_info = doc['sources']['hc_floor_generation']
    gen_info.pop('partition')
    refusals, rejected, diagnostics = Counter(), {}, {}
    doc['groups'] = {}
    for part in parts:
        info = part['sources']['hc_floor_generation']
        for key in ('method', 'stock_proto_sha256', 'map_pos_sha256', 'reader_revision'):
            if info.get(key) != gen_info.get(key):
                raise ValueError('floor partition source mismatch: ' + key)
        owned = set(info.get('area_refreshed_groups', []))
        for name, spec in part['groups'].items():
            if name in doc['groups'] and name not in kept:
                raise ValueError('overlapping floor partitions: ' + name)
            if name in owned:
                doc['groups'][name] = spec
            else:
                doc['groups'].setdefault(name, spec)
        refusals.update(info['refusal_counts'])
        rejected.update(info['rejected_groups'])
        diagnostics.update(info.get('group_diagnostics', {}))
    gen_info['added_groups'] = len(set(doc['groups']) - kept)
    gen_info['added_points'] = sum(len(s['containers']['lootHCFloor']['points'])
                                   for n, s in doc['groups'].items() if n not in kept)
    gen_info['skipped_surface_groups'] = sum(p['sources']['hc_floor_generation']['skipped_surface_groups']
                                             for p in parts)
    gen_info['refusal_counts'] = dict(sorted(refusals.items()))
    gen_info['group_diagnostics'] = dict(sorted(diagnostics.items()))
    gen_info['rejected_groups'] = dict(sorted(rejected.items()))
    gen_info['area_refreshed_groups'] = sorted(n for p in parts for n in
                                               p['sources']['hc_floor_generation'].get('area_refreshed_groups', []))
    gen_info['partitions'] = {'count': len(parts),
                              'input_sha256': [sha(Path(p).read_bytes()) for p in paths]}
    doc['sources'].pop('collision_support', None)
    return doc


def report(raw):
    doc = loot.parse_overlay(raw)
    counts = {}
    for group in doc['groups'].values():
        row = counts.setdefault(group['family'], [0, 0])
        row[0] += 1
        row[1] += sum(len(c['points']) for c in group['containers'].values())
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
    parser.add_argument('--partition', nargs=2, type=int, metavar=('INDEX', 'COUNT'),
                        help='scan disjoint sorted stock-group partition (0-based index; count <= 32)')
    parser.add_argument('--merge-partitions', nargs='+', type=Path, help='join every partition from one complete scan')
    parser.add_argument('--prior-overlay', type=Path, help='re-audit and combine complementary prior points when merging')
    parser.add_argument('--out', type=Path, default=OUTPUT)
    parser.add_argument('--floors', action='store_true',
                        help='floor pass: supported floor points for stock groups without HC points (writes additions.json)')
    parser.add_argument('--base', type=Path, help='floor pass: existing floor overlay to keep and re-audit')
    parser.add_argument('--surface-overlay', type=Path, help='floor pass: surface overlay whose groups are skipped')
    args = parser.parse_args()
    if args.floors:
        out = args.out if args.out != OUTPUT else FLOOR_OUTPUT
        if args.prior_overlay:
            parser.error('--prior-overlay is a surface-pass option')
        if args.partition is not None and out.resolve() == FLOOR_OUTPUT.resolve():
            parser.error('--partition requires a separate --out; never replace the shipped overlay with one partition')
        if args.merge_partitions:
            doc = merge_floor_partitions(args.merge_partitions, args.base)
            from tools.package.loot_support_audit import Audit as SupportAudit
            doc, _ = SupportAudit(args.addons, args.reader, args.stock_proto).filter(doc)
            raw = (json.dumps(doc, sort_keys=True, indent=2) + '\n').encode()
            loot.parse_overlay(raw)
        else:
            raw = generate_floors(args.addons, args.stock_proto, args.reader, args.map_pos, args.base,
                                  args.surface_overlay, args.partition)
        out.write_bytes(raw)
        report(raw)
        return
    if args.base or args.surface_overlay:
        parser.error('--base and --surface-overlay require --floors')
    if args.partition is not None and args.out.resolve() == OUTPUT.resolve():
        parser.error('--partition requires a separate --out; never replace the shipped overlay with one partition')
    if args.merge_partitions and args.partition:
        parser.error('--merge-partitions and --partition are mutually exclusive')
    if args.prior_overlay and not args.merge_partitions:
        parser.error('--prior-overlay requires --merge-partitions')
    raw = (merge_partitions(args.merge_partitions, args.addons, args.stock_proto, args.reader, args.prior_overlay)
           if args.merge_partitions else generate(args.addons, args.stock_proto, args.reader, args.map_pos, args.partition))
    args.out.write_bytes(raw)
    report(raw)


if __name__ == '__main__':
    main()
