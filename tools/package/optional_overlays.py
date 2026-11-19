"""LC-T105/T106/T204: subscription-only, install-time CE overlays (EXP-D1 FALLBACK).

Only authored policy ships. Read the operator's installed XML/README snippets in
memory; write generated data solely into an external mission, never a source or
bundle tree. No PBO is read, extracted, modified or redistributed. Uses stdlib.
Stop the server before apply/rollback. Offline checks establish no DayZ behavior.
"""
import argparse
import base64
import copy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import xml.etree.ElementTree as ET
try:
    from tools.package import xml_text
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.package import xml_text

from tools.package import rag_optional, travel

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / 'mission/hollow-country/optional/overlay-policy.json'
MANAGED = 'hollow-country-optional-packs'
BUNDLE_MANAGED = 'hollow-country-bundle'
CELLARS_MANAGED = 'hollow-country-cellars'
BICYCLE_ID = '2971190303'
ANIMALS_ID = '3114410963'
ANIMATIONS_ID = '2918418331'
DEFAULT_OVERLAY_IDS = (rag_optional.NAVIGATION_ID, rag_optional.RAG_CORE_ID,
                       rag_optional.RAG_VEHICLES_ID, ANIMALS_ID, ANIMATIONS_ID, BICYCLE_ID)
AMBIENT_SPECIES = ('otter', 'rabbit', 'rat', 'raven', 'seagull', 'squirrel')
MAX_BYTES = 16 * 1024 * 1024
BASE_TARGETS = {'cfgeconomycore.xml', 'cfgenvironment.xml', 'cfgeventspawns.xml', 'env/hen_territories.xml'}
GENERATED = {'events.xml', 'types.xml', 'spawnabletypes.xml'} | {
    species + '_territories.xml' for species in (*AMBIENT_SPECIES, 'snake')}



def _ce_relative(folder, name):
    """Mission-relative path of a cfgeconomycore <ce folder><file name> pair, always '/'-separated.

    Built with PurePosixPath so Windows never rewrites the tool's own forward slashes into the
    backslashes the guard refuses (#142); a real backslash, drive, absolute or '..' entry is refused.
    """
    if '\\' in folder or '\\' in name or ':' in folder or ':' in name:
        raise ValueError('unsafe existing CE declaration')
    relative = PurePosixPath(folder) / name
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('unsafe existing CE declaration')
    return relative.as_posix()

def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError('symlink forbidden: ' + part.name)
        if part.exists():
            info = part.lstat()
            if getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('reparse point forbidden')
    return path


def read(path, limit=MAX_BYTES):
    path = safe(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('regular single-link file required: ' + path.name)
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('input exceeds byte budget: ' + path.name)
    return data


def mission_target(mission):
    mission = safe(mission)
    if not mission.is_dir() or 'steamapps' in (p.lower() for p in mission.parts):
        raise ValueError('mission must be an isolated existing copy outside Steam')
    if any((p / '.git').exists() for p in (mission, *mission.parents)):
        raise ValueError('generated dependency data must never enter a repository')
    return mission


def xml(data, tag):
    text = data.decode('utf-8-sig')
    if '\x00' in text or re.search(r'<!\s*(DOCTYPE|ENTITY)', text, re.I):
        raise ValueError('unsupported XML declaration')
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise ValueError('malformed XML; expected ' + tag) from error
    if root.tag != tag:
        raise ValueError('expected XML root ' + tag)
    return root


def serialized(root):
    return xml_text.document(root) + b'\n'


def fragments(data, tag):
    # Installed READMEs are prose containing complete XML snippets, not XML documents.
    text = data.decode('utf-8-sig')
    if '\x00' in text or re.search(r'<!\s*(DOCTYPE|ENTITY)', text, re.I):
        raise ValueError('unsupported README declaration')
    result = []
    for opening in re.finditer(r'<' + tag + r'\s[^>]*>', text):
        end = opening.end()
        if not opening.group().endswith('/>'):
            closing = re.search(r'</' + tag + r'\s*>', text[end:])
            if not closing:
                continue
            end += closing.end()
        try:
            result.append(ET.fromstring(text[opening.start():end]))
        except ET.ParseError:
            # README prose quotes opening tags as insertion landmarks, then
            # supplies a separate complete snippet. Only that snippet is data.
            continue
    return result


def unique_append(parent, node, attribute='name'):
    key = node.get(attribute)
    if not key or any(n.get(attribute, '').casefold() == key.casefold() for n in parent if n.tag == node.tag):
        raise ValueError('duplicate or missing overlay entry: ' + str(key))
    parent.append(copy.deepcopy(node))


def find_file(folder, relative):
    """Case-insensitive resolution for upstream's mixed Chernarus/filename casing."""
    current = safe(folder)
    for component in Path(relative).parts:
        matches = [p for p in current.iterdir() if p.name.casefold() == component.casefold()]
        if len(matches) != 1:
            raise ValueError('installed dependency file missing or ambiguous: ' + relative)
        current = safe(matches[0])
    return current


def positions(mission, fragments_wanted):
    path = mission / 'mapgrouppos.xml'
    if not path.exists():
        return []
    groups = xml(read(path), 'map')
    result = []
    for group in groups.iter('group'):
        if any(term in group.get('name', '').lower() for term in fragments_wanted):
            values = [float(v) for v in group.get('pos', '').split()]
            if len(values) != 3 or not all(math.isfinite(v) for v in values):
                raise ValueError('invalid mission group position')
            result.append((values[0], values[2]))
    return result


def near(x, z, points, radius):
    return any((x - px) ** 2 + (z - pz) ** 2 <= radius ** 2 for px, pz in points)


def loaded_paths(loaded_mods):
    if isinstance(loaded_mods, str):
        loaded_mods = loaded_mods.removeprefix('-mod=').strip('"').split(';')
    return {Path(p).absolute() for p in loaded_mods if str(p)}


def ambient_caps(options):
    """Installed schema: six independent ambient maxima and a separate snake CE
    event. Reserve snakes first, then share the remainder; there is no native
    aggregate field. These are authored ceilings, never observed occupancy.
    """
    cap, total, snake = (options[k] for k in ('per_species_cap', 'total_cap', 'snake_cap'))
    if (any(type(n) is not int for n in (cap, total, snake)) or not 1 <= cap <= 8
            or not 0 <= snake <= 2 or not snake <= total <= 48
            or options.get('total_cap_includes_snakes', True) is not True):
        raise ValueError('ambient policy exceeds provisional aggregate caps')
    share, remainder = divmod(min(total - snake, cap * len(AMBIENT_SPECIES)), len(AMBIENT_SPECIES))
    return {**{name: share + (index < remainder) for index, name in enumerate(AMBIENT_SPECIES)},
            'snake': snake}


def plan(workshop, mission, loaded_mods, policy_path=POLICY):
    """Read-only in-memory candidate; an absent/unloaded pack makes no changes.

    loaded_mods is the actual server -mod list, not the subscription list. The
    caller owns loading Survivor Animations before Bicycle on both clients/server.
    """
    mission = mission_target(mission)
    workshop = safe(workshop) if workshop else None
    if workshop and (mission.is_relative_to(workshop) or workshop.is_relative_to(mission)):
        raise ValueError('mission and read-only Workshop sources must be disjoint')
    loaded = loaded_paths(loaded_mods)
    candidate = {'files': {}, 'before': {}, 'diagnostics': [], 'sources': {}, 'mission': str(mission)}
    packs = {}
    for name, item in (('AmbientAnimals', ANIMALS_ID), ('Bicycles', BICYCLE_ID), *rag_optional.OVERLAY_PACKS):
        path = workshop / item if workshop else None
        present = bool(path and safe(path).is_dir())
        active = present and path.absolute() in loaded
        candidate['diagnostics'].append('[HollowCountry] V2 optional pack %s loaded=%d' % (name, active))
        if active:
            packs[name] = path
    if not packs:
        return candidate
    policy = json.loads(read(policy_path))
    if policy.get('schema') != 1:
        raise ValueError('unknown optional overlay policy')
    if (mission / MANAGED).exists():
        raise ValueError('optional overlay already installed; rollback first')

    def source(path):
        data = read(path)
        candidate['sources'][str(path)] = sha(data)
        return data

    def put(relative, data):
        path = safe(mission / relative)
        candidate['before'][relative] = read(path) if path.exists() else None
        candidate['files'][relative] = data

    if (mission / 'mapgrouppos.xml').exists():
        source(mission / 'mapgrouppos.xml')
    # Separate CE registration preserves stock db/types.xml and other installers' pins.
    events, types, spawnable = ET.Element('events'), ET.Element('types'), ET.Element('spawnabletypes')
    vehicle_events = []  # HC-32 owns only the bicycle events, never ambient ones.
    eventspawns = ET.Element('eventposdef')
    if 'Bicycles' in packs or 'AmbientAnimals' in packs:
        eventspawns = xml(source(mission / 'cfgeventspawns.xml'), 'eventposdef')
    rag_optional.append_types(packs, workshop, loaded, types, source, sys.modules[__name__])
    if 'Bicycles' in packs:
        bicycle = packs['Bicycles']
        options = policy['bicycle']
        multiplier = options['count_multiplier']
        if not 1 <= multiplier <= 4 or not 1 <= options['nominal_cap'] <= 160:
            raise ValueError('bicycle count policy outside provisional bounds')
        bike_events = xml(source(find_file(bicycle, 'events.xml')), 'events')
        bike_points = xml(source(find_file(bicycle, 'cfgeventspawns_Chernarus.xml')), 'events')
        preferred = positions(mission, options['preferred_group_fragments'])
        budget = options['nominal_cap']
        for event in bike_events:
            nominal = event.find('nominal')
            nominal.text = str(min(budget, int(int(nominal.text) * multiplier)))
            budget -= int(nominal.text)
            for tag in ('min', 'max'):
                node = event.find(tag)
                node.text = str(min(options['nominal_cap'], int(int(node.text) * multiplier)))
            event.find('min').text = str(min(int(event.findtext('min')), int(nominal.text)))
            for child in event.findall('children/child'):
                for attribute in ('min', 'max'):
                    child.set(attribute, str(min(options['nominal_cap'], int(int(child.get(attribute)) * multiplier))))
            unique_append(events, event)
            vehicle_events.append(event)
            points = bike_points.findall("event[@name='%s']" % event.get('name'))
            if len(points) != 1 or not list(points[0]):
                raise ValueError('bicycle event has no unique installed placement list')
            placements = list(points[0])
            favoured = [p for p in placements if near(float(p.get('x')), float(p.get('z')),
                                                    preferred, options['placement_radius'])]
            # Retain only dependency-authored points; no invented doorway/shed coordinates.
            if favoured:
                required = max(int(nominal.text), math.ceil(len(favoured) / options['preferred_fraction']))
                points[0][:] = favoured + [p for p in placements if p not in favoured][:max(0, required - len(favoured))]
            unique_append(eventspawns, points[0])
        for entry in xml(source(find_file(bicycle, 'types.xml')), 'types'):
            unique_append(types, entry)
        spawnable = xml(source(find_file(bicycle, 'spawnabletypes.xml')), 'spawnabletypes')
        travel.validate_repairs(spawnable)
        vehicle_names = set(travel.vehicle_owners(events))
        for tag, rows in (('type', types), ('repair template', spawnable)):
            available = [n.get('name', '').casefold() for n in rows.findall('type')]
            if len(available) != len(set(available)) or not vehicle_names <= set(available):
                raise ValueError('HC-32 bicycle missing or duplicate ' + tag)
        put(MANAGED + '/spawnabletypes.xml', serialized(spawnable))

    if 'AmbientAnimals' in packs:
        animals = packs['AmbientAnimals']
        options = policy['ambient']
        caps = ambient_caps(options)
        environment = xml(source(mission / 'cfgenvironment.xml'), 'env')
        territories = environment.find('territories')
        if territories is None:
            raise ValueError('mission lacks native environment territories')
        for species in (*AMBIENT_SPECIES, 'snake'):
            directory = animals / (species + '_territories')
            if species == 'snake':
                instructions = find_file(directory, 'Snake_TypesEvents.txt')
            else:
                matches = [p for p in directory.iterdir() if p.name.lower().endswith('_readme.txt')]
                if len(matches) != 1:
                    raise ValueError('missing or ambiguous installed species README: ' + species)
                instructions = matches[0]
            data = source(instructions)
            territory_nodes = fragments(data, 'territory')
            event_nodes = fragments(data, 'event')
            type_nodes = fragments(data, 'type')
            if len(territory_nodes) != 1 or not event_nodes or not type_nodes:
                raise ValueError('incomplete installed species instructions: ' + species)
            territory = territory_nodes[0]
            # Upstream raven README names seagull; otter usable names rat. Resolve
            # against that species' actual installed file, never another species.
            usable = species + '_territories'
            territory.find('file').set('usable', usable)
            limit = caps[species]
            maxima = territory.findall("item[@name='globalCountMax']")
            if species != 'snake' and len(maxima) != 1:
                raise ValueError('ambient cap schema missing or ambiguous: ' + species)
            for item in maxima:
                item.set('val', str(min(int(item.get('val')), limit)))
            unique_append(territories, territory)
            territory_file = find_file(directory, 'chernarus/' + usable + '.xml')
            territory_data = source(territory_file)
            xml(territory_data, 'territory-type')
            put(MANAGED + '/' + usable + '.xml', territory_data)
            ET.SubElement(territories, 'file', {'path': MANAGED + '/' + usable + '.xml'})
            for animal_event in event_nodes:
                if animal_event.find('nominal') is None:
                    unique_append(eventspawns, animal_event)
                    continue
                for tag in ('nominal', 'min', 'max'):
                    animal_event.find(tag).text = str(min(int(animal_event.findtext(tag)), limit))
                for animal_child in animal_event.findall('children/child'):
                    for attribute in ('min', 'max'):
                        animal_child.set(attribute, str(min(int(animal_child.get(attribute)), limit)))
                unique_append(events, animal_event)
            for animal_type in type_nodes:
                unique_append(types, animal_type)
        put('cfgenvironment.xml', serialized(environment))
        native_ambient_delta(mission, options, source, put)

    # Refuse existing declarations of the same types/events across stock and CE
    # extensions. No duplicate loot or reliance on unobserved replacement order.
    core = xml(source(mission / 'cfgeconomycore.xml'), 'economycore')
    owners = travel.vehicle_owners(vehicle_events)
    travel.validate_vehicle_budgets(types, set(owners))
    # An optional event with a new name can still duplicate a native/managed
    # vehicle. Compare child classes against every effective source, too.
    event_files = ['db/events.xml']
    for ce in core.findall('ce'):
        for entry in ce.findall("file[@type='events']"):
            event_files.append(_ce_relative(ce.get('folder', ''), entry.get('name', '')))
    effective_events = {}
    for relative in event_files:
        # Types-only plans do not need a stock events file; synthetic/stripped
        # missions may omit it. A declared CE file is always required.
        if relative == 'db/events.xml' and not (mission / relative).exists() and not owners:
            continue
        existing = xml(source(mission / relative), 'events')
        for event in existing:
            if set(owners) & {n.get('type', '').casefold() for n in event.findall('children/child')}:
                raise ValueError('HC-32 vehicle has another event owner: ' + event.get('name', ''))
            effective_events[event.get('name', '').casefold()] = event
    existing_vehicles = {n.get('type', '').casefold() for event in effective_events.values()
                         for n in event.findall('children/child')}
    travel.validate_vehicle_budgets(types, existing_vehicles | set(owners))
    for kind, additions, stock in (('events', events, 'db/events.xml'), ('types', types, 'db/types.xml'),
                                   ('spawnabletypes', spawnable, 'cfgspawnabletypes.xml')):
        if not len(additions):
            continue
        names = {node.get('name').casefold() for node in additions if node.get('name')}
        if len(names) != len([node for node in additions if node.get('name')]):
            raise ValueError('duplicate installed optional entries: ' + kind)
        existing_files = [stock]
        for ce in core.findall('ce'):
            for entry in ce.findall('file'):
                if entry.get('type') == kind:
                    existing_files.append(_ce_relative(ce.get('folder', ''), entry.get('name', '')))
        for relative in existing_files:
            existing = xml(source(mission / relative), kind)
            if names & {node.get('name', '').casefold() for node in existing}:
                raise ValueError('existing optional CE entries require reconciliation: ' + kind)
    registration = ET.SubElement(core, 'ce', {'folder': MANAGED})
    for name, content in (('events.xml', events), ('types.xml', types)):
        if len(content):
            put(MANAGED + '/' + name, serialized(content))
    for relative in sorted(candidate['files']):
        if relative in {MANAGED + '/' + n for n in ('events.xml', 'types.xml', 'spawnabletypes.xml')}:
            name = Path(relative).name
            ET.SubElement(registration, 'file', {'name': name, 'type': name[:-4]})
    put('cfgeconomycore.xml', serialized(core))
    if 'Bicycles' in packs or 'AmbientAnimals' in packs:
        put('cfgeventspawns.xml', serialized(eventspawns))
    native_count = len(set(effective_events) & {n.casefold() for n in travel.NATIVE_FAMILIES})
    candidate['diagnostics'].append(
        '[HC Plan] HC-32 vehicle_families=%d optional=%d refused=runtime_pending state=authored runtime=PENDING'
        % (native_count, len(vehicle_events)))
    return candidate


def native_ambient_delta(mission, options, source, put):
    """Bounded edit of existing hen habitat near native water/farm metadata.

    Never raises a native global cap, creates a new coordinate, or edits herd /
    infected populations. Density/zone budgets are provisional until EXP-A4.
    """
    path = mission / 'env/hen_territories.xml'
    if not path.exists():
        return
    habitat = xml(source(path), 'territory-type')
    landmarks = positions(mission, ('farm', 'barn', 'cowshed'))
    water_path = mission / 'env/red_deer_territories.xml'
    if water_path.exists():
        for zone in xml(source(water_path), 'territory-type').iter('zone'):
            if zone.get('name') == 'Water':
                landmarks.append((float(zone.get('x')), float(zone.get('z'))))
    changed = 0
    for zone in habitat.iter('zone'):
        if changed >= min(12, options['native_zone_limit']):
            break
        if near(float(zone.get('x')), float(zone.get('z')), landmarks, options['near_water_or_farm_radius']):
            original = int(zone.get('dmax'))
            density = min(3, options['native_density_cap'], math.ceil(original * options['native_density_multiplier']))
            if original < density:
                zone.set('dmax', str(density))
                changed += 1
    if changed:
        put('env/hen_territories.xml', serialized(habitat))


def allowed(relative, managed_name=MANAGED):
    if managed_name == CELLARS_MANAGED:
        return relative == 'cfgundergroundtriggers.json'
    if managed_name == BUNDLE_MANAGED:
        path = Path(relative)
        clean = not path.is_absolute() and '..' not in path.parts and '\\' not in relative and ':' not in relative
        authored = path.parts and path.parts[0].startswith('hollow-country')
        if path.parts and path.parts[0] in (BUNDLE_MANAGED, MANAGED, CELLARS_MANAGED):
            return False
        return clean and (relative in ('cfgeconomycore.xml', 'cfggameplay.json', 'cfgenvironment.xml', 'db/events.xml') or authored or relative == 'expansion/settings/AIPatrolSettings.json')
    if managed_name != MANAGED:
        return False
    return relative in BASE_TARGETS or relative in {MANAGED + '/' + name for name in GENERATED}


def atomic(path, data, managed):
    """Exclusive temp + fsync + atomic rename; receipt exists before target writes."""
    safe(path)
    temporary = managed / '.next'
    if temporary.exists():
        read(temporary)
        temporary.unlink()
    with temporary.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def install(candidate, mission, managed_name=MANAGED):
    mission = mission_target(mission)
    if not candidate['files'] and managed_name == MANAGED:
        return
    if str(mission) != candidate['mission']:
        raise ValueError('candidate belongs to another mission')
    managed = safe(mission / managed_name)
    if managed.exists():
        raise ValueError('optional overlay already installed; rollback first')
    for name, data in candidate['files'].items():
        if not allowed(name, managed_name):
            raise ValueError('unexpected overlay target')
        path = safe(mission / name)
        current = read(path) if path.exists() else None
        if current != candidate['before'][name]:
            raise ValueError('mission drift since planning: ' + name)
    for name, digest in candidate['sources'].items():
        if sha(read(name)) != digest:
            raise ValueError('source drift since planning: ' + Path(name).name)
    receipt = {'schema': 1, 'files': {name: {
        'before': None if candidate['before'][name] is None else base64.b64encode(candidate['before'][name]).decode(),
        'before_sha256': None if candidate['before'][name] is None else sha(candidate['before'][name]),
        'after': sha(data)} for name, data in candidate['files'].items()}}
    # One self-contained receipt includes byte-exact backups. A pre-receipt
    # interruption cannot have changed any target; an empty bootstrap is removable.
    managed.mkdir()
    atomic(managed / 'receipt.json', (json.dumps(receipt, sort_keys=True) + '\n').encode(), managed)
    for name, data in candidate['files'].items():
        (mission / name).parent.mkdir(parents=True, exist_ok=True)
        atomic(mission / name, data, managed)


def installed_before(mission, managed_name=MANAGED):
    managed = safe(mission / managed_name)
    if not managed.exists():
        return None
    if not (managed / 'receipt.json').exists():
        if set(p.name for p in managed.iterdir()) <= {'.next'}:
            return {}
        raise ValueError('optional overlay receipt missing; reconcile manually')
    receipt = json.loads(read(managed / 'receipt.json', 128 * 1024 * 1024))
    if receipt.get('schema') != 1 or not isinstance(receipt.get('files'), dict):
        raise ValueError('invalid optional overlay receipt')
    before = {}
    expected = {'receipt.json', '.next'}
    for name, row in receipt['files'].items():
        if not allowed(name, managed_name) or not re.fullmatch('[0-9a-f]{64}', row['after']):
            raise ValueError('invalid optional overlay target in receipt')
        old = None if row['before'] is None else base64.b64decode(row['before'], validate=True)
        if row['before_sha256'] != (None if old is None else sha(old)):
            raise ValueError('optional overlay backup drift: ' + name)
        path = safe(mission / name)
        current = read(path) if path.exists() else None
        if current != old and (current is None or sha(current) != row['after']):
            raise ValueError('optional overlay drift: ' + name)
        before[name] = old
        if name.startswith(managed_name + '/'):
            expected.add(name.split('/', 1)[1])
    for path in managed.iterdir():
        if path.name not in expected:
            raise ValueError('unexpected optional overlay file; reconcile manually')
        read(path, 128 * 1024 * 1024)
    return before


def rollback(mission, dry_run=False, managed_name=MANAGED):
    mission = mission_target(mission)
    before = installed_before(mission, managed_name)
    if before is None:
        return []
    if not dry_run:
        managed = mission / managed_name
        for name, data in before.items():
            if data is not None:
                (mission / name).parent.mkdir(parents=True, exist_ok=True)
                atomic(mission / name, data, managed)
            elif (mission / name).exists():
                (mission / name).unlink()
        shutil.rmtree(managed)
    return sorted(before)


def bundle_candidate(bundle, mission):
    """Merge only authored files and explicit patches into the friend's own stock.

    This uses install/rollback's byte-exact backup receipt, including first installs.
    No stock mission is transported. Unknown edits to patched values refuse.
    """
    bundle, mission = safe(bundle), mission_target(mission)
    # Inspect the preference before requiring any habitat-only source/stock.
    habitat_root = bundle / 'mission-overlay/hollow-country/ecology'
    habitat = json.loads(read(habitat_root / 'habitat-overrides.json'))
    if type(habitat.get('Enabled')) is not bool:
        raise ValueError('habitat Enabled preference missing')
    habitat_stock = {}
    if habitat['Enabled']:
        for name in ('cfgenvironment.xml', 'db/events.xml'):
            try:
                habitat_stock[name] = read(mission / name)
            except FileNotFoundError as error:
                raise ValueError('HC149_HABITAT_STOCK_MISSING: ' + name) from error
    patch = json.loads(read(bundle / 'mission-patches.json'))
    candidate = {'mission': str(mission), 'files': {}, 'before': {}, 'sources': {}}

    def put_file(name, data):
        if not allowed(name, BUNDLE_MANAGED):
            raise ValueError('unexpected bundle mission target: ' + name)
        target = safe(mission / name)
        old = read(target) if target.exists() else None
        candidate['before'][name] = old
        candidate['files'][name] = data

    for path in sorted((bundle / 'mission-overlay').rglob('*')):
        safe(path)
        if path.is_file():
            name = path.relative_to(bundle / 'mission-overlay').as_posix()
            if not habitat['Enabled'] and name in (
                    'hollow-country/ecology/habitat-overrides.json',
                    'hollow-country/ecology/events.append.xml'):
                continue
            data = read(path)
            target = safe(mission / name)
            if target.exists() and read(target) != data:
                raise ValueError('bundle overlay would replace existing file: ' + name)
            put_file(name, data)
    core = xml(read(mission / 'cfgeconomycore.xml'), 'economycore')
    for entry in patch['core']:
        node = ET.fromstring(entry['after'])
        parent = core
        if node.tag != 'ce':
            parent = core.find('defaults')
            if parent is None:
                parent = ET.SubElement(core, 'defaults')
        key = 'folder' if node.tag == 'ce' else 'name'
        existing = [n for n in parent if n.tag == node.tag and n.get(key) == node.get(key)]
        if len(existing) > 1:
            raise ValueError('ambiguous mission core merge')
        if existing:
            old = ET.tostring(existing[0], encoding='unicode').strip()
            if old != entry['before'] and old != entry['after']:
                raise ValueError('mission core merge conflict: ' + str(node.get(key)))
            parent.remove(existing[0])
        elif entry['before'] is not None:
            raise ValueError('mission core merge baseline missing')
        parent.append(node)
    if patch['core']:
        put_file('cfgeconomycore.xml', serialized(core))
    if patch['gameplay']:
        gameplay = json.loads(read(mission / 'cfggameplay.json'))
        for row in patch['gameplay']:
            parent = gameplay
            for part in row['path'][:-1]:
                parent = parent.setdefault(part, {})
            key = row['path'][-1]
            if parent.get(key) not in (row['before'], row['after']):
                raise ValueError('mission gameplay merge conflict: ' + '.'.join(row['path']))
            parent[key] = row['after']
        put_file('cfggameplay.json', (json.dumps(gameplay, indent=2) + '\n').encode())
    # #149: replace one stock event, never add another CE event owner. These
    # class names are from the inspected stock 1.30 configuration inventory;
    # this candidate is not evidence of class loading or mixed-herd behavior.
    if habitat['Enabled']:
        from tools.package import HCWildlife_habitats
        habitat_files = HCWildlife_habitats.build(
            habitat, read(habitat_root / 'events.append.xml'),
            habitat_stock['cfgenvironment.xml'], habitat_stock['db/events.xml'],
            HCWildlife_habitats.REQUIRED_CLASSES)
        for relative, data in habitat_files.items():
            put_file(relative, data)
    return candidate


PACK_DIAGNOSTIC = '[HollowCountry] V2 optional pack '


def unloaded_default_packs(diagnostics):
    """Names of default packs plan() reported unloaded. Other plan() lines (the HC-32
    receipt) are not pack verdicts; no pack line at all is itself a refusal."""
    packs = [line[len(PACK_DIAGNOSTIC):] for line in diagnostics if line.startswith(PACK_DIAGNOSTIC)]
    if not packs:
        return ['<none reported>']
    return [row.rsplit(' loaded=', 1)[0] for row in packs if not row.endswith(' loaded=1')]


def bundle_apply(bundle, mission, workshop, loaded):
    """Rehearse on local scratch bytes, then reuse the receipt installers in order."""
    mission = mission_target(mission)
    for path in mission.rglob('*'):
        safe(path)
    if (Path(mission) / BUNDLE_MANAGED).exists():
        raise ValueError('bundle install exists; rollback before installing again')
    candidate = bundle_candidate(bundle, mission)
    from tools.package import loot_boost, travel
    source = Path(bundle) / 'mission/hollow-country'
    travel.validate(source)
    if (Path(mission) / loot_boost.MANAGED).exists():
        raise ValueError('loot boost already installed; bundle-rollback before installing again')
    # The loot boost is generated from the friend's own installed bytes and goes last, on top of every layer.
    multiplier, points = loot_boost.default_multiplier(Path(bundle)), loot_boost.shipped_points(Path(bundle))
    with tempfile.TemporaryDirectory(prefix='hc-bundle-preflight-') as directory:
        scratch = Path(directory) / 'mission'
        shutil.copytree(mission, scratch, ignore=shutil.ignore_patterns('storage_*'))
        rehearsal = bundle_candidate(bundle, scratch)
        install(rehearsal, scratch, managed_name=BUNDLE_MANAGED)
        travel.install(source, scratch)
        optional = plan(workshop, scratch, loaded, source / 'optional/overlay-policy.json')
        unloaded = unloaded_default_packs(optional['diagnostics'])
        if unloaded:
            raise ValueError('bundle requires all default optional overlays to be loaded: ' + ', '.join(unloaded))
        install(optional, scratch)
        loot_boost.install(scratch, multiplier, points)
    apply_stack(mission, [
        lambda: install(candidate, mission, managed_name=BUNDLE_MANAGED),
        lambda: travel.install(source, mission),
        lambda: install(plan(workshop, mission, loaded, source / 'optional/overlay-policy.json'), mission),
        lambda: loot_boost.install(mission, multiplier, points)])


def _undo_layers(target):
    """Roll back every layer present, newest first; each rollback verifies its own files before restoring."""
    from tools.package import loot_boost, travel
    if os.path.lexists(target / loot_boost.MANAGED):
        loot_boost.rollback(target)  # installed last, so it is undone first
    rollback(target)
    if (target / travel.MANAGED).exists():
        travel.rollback(target)
    rollback(target, managed_name=BUNDLE_MANAGED)


def apply_stack(mission, steps):
    """Run install steps in order; when one fails, undo what this run applied (verified) and re-raise the failure.

    A refused undo (an operator edit in the way) keeps all recovery data and says so, so bundle-rollback can finish.
    """
    mission = mission_target(mission)
    try:
        for step in steps:
            step()
    except Exception as error:
        try:
            _undo_layers(mission)
            from tools.package import loot_boost, travel
            left = [n for n in (loot_boost.MANAGED, MANAGED, travel.MANAGED, BUNDLE_MANAGED)
                    if os.path.lexists(mission / n)]
            if left:
                raise ValueError('managed folders remain after undo: ' + ', '.join(left))
        except (OSError, ValueError) as undo_error:
            raise ValueError('install failed (%s) and the automatic undo failed (%s); recovery data is kept, '
                             'run bundle-rollback after reconciling' % (error, undo_error)) from error
        raise


def bundle_rollback(mission):
    from tools.package import loot_boost, travel
    mission = mission_target(mission)
    for path in mission.rglob('*'):
        safe(path)
    # Validate all rollback layers on scratch before changing any live byte.
    with tempfile.TemporaryDirectory(prefix='hc-bundle-rollback-') as directory:
        scratch = Path(directory) / 'mission'
        shutil.copytree(mission, scratch, ignore=shutil.ignore_patterns('storage_*'))
        for target in (scratch, Path(mission)):
            _undo_layers(target)


def friend_bundle_plan(mission, rows):
    """Strip all generated dependency data and undo its edits in export bytes only."""
    before = installed_before(safe(mission))
    cellar_before = installed_before(safe(mission), CELLARS_MANAGED)
    if cellar_before:
        before = dict(before or {}, **cellar_before)
    prefix = 'mpmissions/' + Path(mission).name + '/'
    result = []
    for relative, content in rows:
        if relative.startswith(prefix):
            name = relative[len(prefix):]
            if name.startswith(MANAGED + '/') or name.startswith(CELLARS_MANAGED + '/'):
                continue
            if before and name in before:
                content = before[name]
                if content is None:
                    continue
        result.append((relative, content))
    result += [('tools/package/optional_overlays.py', read(Path(__file__))),
               ('tools/package/rag_optional.py', read(Path(rag_optional.__file__))),
               ('mission/hollow-country/optional/overlay-policy.json', read(POLICY))]
    return result


def friend_notes():
    return '\r\n'.join([
        '', 'Default subscriptions: COT, Expansion Navigation (GPS), RaG_Core, RaG Immersive Vehicles, Ambient Animals Pack, Survivor Animations and DayZ-Bicycle.',
        'Never repack or redistribute them. Download their original Workshop folders on the friend server.',
        'Expansion-Animations is intentionally not loaded: it conflicts with Survivor Animations, which DayZ-Bicycle requires; Expansion-AI brings its own AI animations.',
        'Keep the original numeric Workshop folders for the installer, alongside the @ copies used to launch.',
        'Install Python 3.10+. From this bundle folder, with the server stopped, run:',
        '  python -m tools.package.optional_overlays bundle-plan --mission <friend-mission>',
        '  python -m tools.package.optional_overlays bundle-apply --mission <friend-mission> --workshop-dir <content/221100>',
        'The installer rehearses merges on scratch bytes, then backs up every changed file in a receipt.',
        'Our mission overlay, travel CE and Bicycle/Ambient/RaG/GPS overlays apply to your own stock mission.',
        'RaG shipped types are generated locally from the installed item, never exported in this bundle.',
        'ExpansionGPS uses nominal 4 with Military/Police usage; do not add another CE owner for these types.',
        'No stock mission ships. Use an isolated dayzOffline.chernarusplus copy outside Steam and this bundle.',
        'To undo (stop server first): python -m tools.package.optional_overlays bundle-rollback --mission <friend-mission>',
        'The loot boost goes last: non-firearm building loot x2 (settings in mission/hollow-country/loot-points/settings.json),',
        '  RespawnTypes x2 and model-derived kitchen/garage/police/medical loot points; firearms, ammo and explosives keep their scarcity.',
        'Rollback order: loot boost, optional packs, travel, bundle merge. Drift refuses rather than overwriting edits.',
        'Keep all receipts and backups on the friend server. No hive wipe; persisted entities are not deleted.',
        'CE building coverage is excluded; qualify it separately against the friend stock mission.',
        'Native compile, normal PBO/server and two-client synchronization remain pending.', '',
    ])


def launcher_run(args, repo, out, launcher):
    """Small launcher entry point; its existing installers retain their ordering."""
    if args.command == 'rollback':
        return launcher_rollback(args, repo, out, launcher)
    if not 1024 <= args.game_port <= 65533 or not 1024 <= args.query_port <= 65535:
        raise ValueError('ports out of range')
    workshop = args.workshop_dir
    requested_key_install = args.install_key
    # --workshop-dir can now be used for optional packs without the AI addon.
    if not args.expansion_ai:
        args.workshop_dir = None
    if workshop:
        args.install_key = False  # include the optional public keys before validating this request
    try:
        session = launcher.build_plan(args, repo)
    finally:
        args.workshop_dir = workshop
        args.install_key = requested_key_install
    commands = launcher.launch_commands(session, args)
    additions = []
    if workshop:
        workshop = launcher.existing_dir(workshop, 'optional Workshop directory', repo)
        for destination in (session['mission'], session['profiles'], session['mod']['dest'], session['server_root']):
            if Path(destination).is_relative_to(workshop):
                raise ValueError('Workshop sources must remain read only; destination overlaps Workshop directory')
        for item in (rag_optional.RAG_CORE_ID, rag_optional.RAG_VEHICLES_ID, ANIMALS_ID, ANIMATIONS_ID, BICYCLE_ID):
            path = workshop / item
            if path.is_dir():
                if not launcher.has_addons(path):
                    raise ValueError('optional Workshop pack has no Addons: ' + item)
                if item == BICYCLE_ID and not (workshop / ANIMATIONS_ID).is_dir():
                    raise ValueError('DayZ-Bicycle requires subscribed Survivor Animations ' + ANIMATIONS_ID)
                additions.append(path)
        if not args.expansion_ai:
            # Retain the base launcher's input gate unless a numeric CE source
            # is actually supplied. Alias-only framework folders are not overlays.
            has_overlay_source = any(path.name in (ANIMALS_ID, BICYCLE_ID, rag_optional.RAG_VEHICLES_ID)
                                     for path in additions)
            has_overlay_source = has_overlay_source or (workshop / rag_optional.NAVIGATION_ID).is_dir()
            if not has_overlay_source:
                raise ValueError('--workshop-dir without optional packs only applies with --expansion-ai')
            dependencies, _ = launcher.locate_expansion(workshop)
            additions = [row['path'] for row in dependencies] + additions
    previous = commands['mod']
    suffix = ';'.join(launcher.to_windows(p)[0] for p in additions)
    if suffix:
        # Insert immediately before HC, retaining Expansion/weapon order.
        base_path = launcher.to_windows(session['mod']['dest'])[0]
        parts = previous.removeprefix('-mod=').split(';')
        extra_parts = suffix.split(';')
        # Dependencies precede both weapon packs, RaG/living packs follow them.
        if not args.expansion_ai:
            prefix_count = len(dependencies)
            parts[0:0] = extra_parts[:prefix_count]
            extra_parts = extra_parts[prefix_count:]
        parts[parts.index(base_path):parts.index(base_path)] = extra_parts
        commands['mod'] = '-mod=' + ';'.join(parts)
        for key in ('server', 'client'):
            commands[key] = [line.replace(previous, commands['mod']) for line in commands[key]]
        public_keys = list(session['keys'])
        for dependency in additions:
            for keys_directory in dependency.iterdir():
                if keys_directory.name.lower() != 'keys' or not keys_directory.is_dir():
                    continue
                safe(keys_directory)
                for key_file in keys_directory.iterdir():
                    if key_file.suffix.lower() == '.bikey':
                        if not launcher.KEY_NAME.fullmatch(key_file.name):
                            raise ValueError('unsafe optional public key name')
                        public_keys.append({'origin': 'optional-pack', 'name': key_file.name,
                                            'data': read(key_file, launcher.MAX_KEY)})
        session['keys'] = launcher.server_key_plan(session['server_root'], public_keys)
    session['install_key'] = requested_key_install
    if requested_key_install and not session['keys']:
        raise ValueError('--install-key needs a signed mod public key or an optional pack public key')
    settings_path = session['profiles'] / 'HollowCountry/settings.json'
    enabled = True
    if settings_path.exists():
        enabled = json.loads(read(settings_path)).get('EnableAmbientLife', True)
        if type(enabled) is not bool:
            raise ValueError('EnableAmbientLife must be boolean')
    loaded = list(additions)
    if session.get('expansion_ai'):
        loaded += [row['path'] for row in session['expansion_ai']['dependencies']]
    if not enabled:
        loaded = [path for path in loaded if path.name not in (ANIMALS_ID, BICYCLE_ID)]
    candidate = plan(workshop, session['mission'], loaded,
                     Path(repo) / 'mission/hollow-country/optional/overlay-policy.json')
    # Source core may change when existing economy installers run. Replan after
    # apply; the preflight above rejects missing/malformed dependency inputs first.
    if args.command == 'apply':
        launcher.apply_plan(session, args)
        _, _, receipt = launcher.load_receipt(session['server_root'], repo)
        receipt.step('optional_packs', 'started')
        candidate = plan(workshop, session['mission'], loaded,
                         Path(repo) / 'mission/hollow-country/optional/overlay-policy.json')
        install(candidate, session['mission'])
        receipt.step('optional_packs', 'done')
    print(launcher.render_plan(session, args, commands, applied=args.command == 'apply'), file=out)
    for line in candidate['diagnostics']:
        print(line, file=out)
    if candidate['files']:
        print('Optional overlays: %d mission files; subscription-only; runtime acceptance pending' % len(candidate['files']), file=out)
    return 0


def launcher_rollback(args, repo, out, launcher):
    # Preserve the base launcher's own missing-session errors and test seams.
    if not (Path(args.server_root) / launcher.STATE_NAME / launcher.RECEIPT_NAME).exists():
        descriptions = launcher.rollback(args.server_root, repo, args.dry_run)
        for line in descriptions:
            print(('would ' if args.dry_run else 'done: ') + line, file=out)
        print('Rollback %s.' % ('previewed' if args.dry_run else 'complete'), file=out)
        return 0
    _, _, receipt = launcher.load_receipt(args.server_root, repo)
    mission = Path(receipt.data['mission'])
    if (mission / MANAGED).exists():
        rollback(mission, dry_run=True)
        # Preflight the underlying session against an in-memory-receipt view of
        # a scratch mission with our overlay removed. Never change live mission
        # bytes during preview, and refuse all session drift before actual undo.
        with tempfile.TemporaryDirectory(prefix='hc-optional-rollback-') as temporary:
            scratch = Path(temporary) / 'mission'
            shutil.copytree(mission, scratch, ignore=shutil.ignore_patterns('storage_*'), symlinks=True)
            rollback(scratch)
            original_loader = launcher.load_receipt

            def scratch_receipt(server_root, repo_arg):
                server, state, original = original_loader(server_root, repo_arg)
                # AI mission config records also contain absolute mission paths.
                # Profiles/mod destinations keep their real paths for validation.
                def remap(value):
                    if isinstance(value, dict):
                        return {key: remap(item) for key, item in value.items()}
                    if isinstance(value, list):
                        return [remap(item) for item in value]
                    if isinstance(value, str) and (value == str(mission) or value.startswith(str(mission) + os.sep)):
                        return str(scratch) + value[len(str(mission)):]
                    return value
                original.data = remap(original.data)
                return server, state, original

            launcher.load_receipt = scratch_receipt
            try:
                descriptions = launcher.rollback(args.server_root, repo, dry_run=True)
            finally:
                launcher.load_receipt = original_loader
        descriptions = ['optional packs: restore external mission from receipt'] + [
            line.replace(str(scratch), str(mission)) for line in descriptions]
        if not args.dry_run:
            rollback(mission)
            descriptions = descriptions[:1] + launcher.rollback(args.server_root, repo, dry_run=False)
    else:
        descriptions = launcher.rollback(args.server_root, repo, args.dry_run)
    for line in descriptions:
        print(('would ' if args.dry_run else 'done: ') + line, file=out)
    print('Rollback %s.' % ('previewed' if args.dry_run else 'complete'), file=out)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('command', choices=('plan', 'apply', 'rollback', 'bundle-plan', 'bundle-apply', 'bundle-rollback'))
    parser.add_argument('--bundle', type=Path, default=ROOT)
    parser.add_argument('--mission', required=True, type=Path)
    parser.add_argument('--workshop-dir', type=Path)
    parser.add_argument('--loaded-mods', default='')
    args = parser.parse_args(argv)
    try:
        if args.command.startswith('bundle-'):
            if args.command == 'bundle-rollback':
                bundle_rollback(args.mission)
            elif args.command == 'bundle-plan':
                candidate = bundle_candidate(args.bundle, args.mission)
                for name in sorted(candidate['files']):
                    print('bundle overlay: ' + name)
            else:
                if args.workshop_dir is None:
                    raise ValueError('bundle apply requires --workshop-dir with the subscribed default packs')
                loaded = args.loaded_mods or ';'.join(str(args.workshop_dir / ident) for ident in
                                                   DEFAULT_OVERLAY_IDS)
                if not all((args.workshop_dir / ident).is_dir() for ident in DEFAULT_OVERLAY_IDS):
                    raise ValueError('default bundle needs Navigation, RaG_Core, RaG Immersive Vehicles, Ambient Animals, Survivor Animations and DayZ-Bicycle')
                bundle_apply(args.bundle, args.mission, args.workshop_dir, loaded)
            print('HC bundle ' + args.command + ' complete; runtime acceptance pending')
        elif args.command == 'rollback':
            rollback(args.mission)
        else:
            candidate = plan(args.workshop_dir, args.mission, args.loaded_mods)
            for line in candidate['diagnostics']:
                print(line)
            for name in sorted(candidate['files']):
                print('overlay: ' + name)
            if args.command == 'apply':
                install(candidate, args.mission)
        return 0
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError) as error:
        print('refused: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
