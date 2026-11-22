"""Stage/ingest a disposable native CE initial-fill experiment; never launch DayZ."""
import argparse
import csv
import contextlib
import datetime
import io
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
import re
import secrets
import tempfile
from types import SimpleNamespace

from tools.setup import probe_runtime as rt, ce_site_probe, friend_bundle, friend_install
from tools.package import (optional_overlays as overlays, loot_boost, travel, map_overlay,
                           infected_variety, hc_events, tactical_flava_optional as tf,
                           snafu_optional as sf, weapon_pack_guards, xml_text)

PLAN_NAME = 'ce-fill-probe-plan.json'
CATALOG_NAME = 'ce-fill-type-catalog.json'
FRIEND = Path('/mnt/e/HollowCountryLocal/friend-local-1')
HARD_CAP = 8
MAX_RPT_BYTES = 128 * 1024 * 1024
# t4 uses the friend's real installation order: optional/travel precede boost;
# map and weapons precede events. Earlier treatments omit those intervening layers.
TREATMENTS = {
    't0': (),
    't1': ('base',),
    't2': ('base', 'boost'),
    't3': ('base', 'boost', 'weapons'),
    't4': ('base', 'travel', 'optional', 'boost', 'variety', 'map', 'weapons', 'events'),
}


def installed_mods(friend=FRIEND):
    """The receipted launcher, not the subscription catalogue, is authoritative."""
    raw = rt._read_bounded(friend / 'start-server.bat', rt.MAX_CONFIG_BYTES)
    receipt_raw = rt._read_bounded(friend / friend_install.RECEIPT, rt.MAX_PLAN_BYTES)
    receipt = json.loads(receipt_raw)
    if receipt['files']['start-server.bat'] != rt.sha256(raw):
        raise ValueError('installed launcher differs from friend installer receipt')
    matches = re.findall(r'(?i)(-mod|-serverMod)=([^\s"\r\n]+)', raw.decode('utf-8-sig'))
    mods = {}
    for switch, names in matches:
        key = '-mod' if switch.lower() == '-mod' else '-serverMod'
        if key in mods:
            raise ValueError('ambiguous launcher mod switches')
        mods[key] = []
        for name in names.split(';'):
            if not re.fullmatch(r'@[A-Za-z0-9_-]+', name):
                raise ValueError('launcher mod folder must be relative to friend install')
            root = friend / name
            pbos = [dict(path=n, sha256=rt._hash_file(root / n)[0])
                    for n in sorted(rt.dm.walk_plain(root)) if n.lower().endswith('.pbo')]
            mods[key].append(dict(path='E:\\HollowCountryLocal\\friend-local-1\\' + name, pbos=pbos))
    rt.validate_mods(mods)
    return mods, dict(authority='friend-local-1/start-server.bat',
                      launcher_sha256=rt.sha256(raw), receipt_sha256=rt.sha256(receipt_raw))


def binding(plan):
    fields = {key: plan[key] for key in ('variant', 'layers', 'mods', 'mod_source',
              'stock_mission_sha256', 'run_id', 'hold_seconds', 'server_exe_sha256')}
    for key in ('authored_inputs_sha256', 'tool_sha256', 'variants', 'variant_receipts', 'type_catalog', 'census_version'):
        if key in plan:
            fields[key] = plan[key]
    return rt.sha256(json.dumps(fields, sort_keys=True, separators=(',', ':')).encode())


def render_hook(token, hold_seconds):
    # Native declarations inspected in the pinned 1.30 scripts; read-only survey.
    return ('''\nclass HCDisposableDiagnosticMission : CustomMission
{
    protected int m_FillTile;
    protected int m_FillObjects;
    protected ref map<string, int> m_FillLoose = new map<string, int>;
    protected ref map<string, int> m_FillAttached = new map<string, int>;

    override void OnInit()
    {
        super.OnInit();
        Print("[HC FillProbe] begin binding=TOKEN");
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(FillStart, HOLD, false);
    }
    void FillStart()
    {
        CEApi fillEconomy = GetCEApi();
        if (fillEconomy)
            fillEconomy.EconomyLog(EconomyLogCategories.Economy);
        FillStep();
    }
    int FillAttachments(EntityAI fillRoot)
    {
        int fillTotal = 0;
        ref array<EntityAI> fillPending = new array<EntityAI>;
        fillPending.Insert(fillRoot);
        while (fillPending.Count() > 0)
        {
            EntityAI fillNode = fillPending[fillPending.Count() - 1];
            fillPending.Remove(fillPending.Count() - 1);
            GameInventory fillInventory = fillNode.GetInventory();
            if (!fillInventory)
                continue;
            for (int fillSlot = 0; fillSlot < fillInventory.AttachmentCount(); fillSlot++)
            {
                EntityAI fillChild = fillInventory.GetAttachmentFromIndex(fillSlot);
                if (!fillChild)
                    continue;
                if (ItemBase.Cast(fillChild))
                    fillTotal++;
                fillPending.Insert(fillChild);
            }
        }
        return fillTotal;
    }
    void FillStep()
    {
        // 60 x 60 half-open 256 m tiles cover the 15,360 m map.
        // One tile per callback; circles overlap, ownership squares do not.
        int fillTilesPerStep = 1;
        for (int fillBatch = 0; fillBatch < fillTilesPerStep && m_FillTile < 3600; fillBatch++)
        {
            int fillX = m_FillTile % 60;
            int fillZ = m_FillTile / 60;
            vector fillCenter = Vector(fillX * 256 + 128, 0, fillZ * 256 + 128);
            ref array<Object> fillObjects = new array<Object>;
            ref array<CargoBase> fillProxies = new array<CargoBase>;
            GetGame().GetObjectsAtPosition(fillCenter, 182, fillObjects, fillProxies);
            m_FillObjects += fillObjects.Count();
            foreach (Object fillObject : fillObjects)
            {
                ItemBase fillItem = ItemBase.Cast(fillObject);
                if (!fillItem || fillItem.GetHierarchyRoot() != fillItem)
                    continue;
                vector fillPosition = fillItem.GetPosition();
                if (fillPosition[0] < fillX * 256 || fillPosition[0] >= (fillX + 1) * 256)
                    continue;
                if (fillPosition[2] < fillZ * 256 || fillPosition[2] >= (fillZ + 1) * 256)
                    continue;
                string fillName = fillItem.GetType();
                m_FillLoose.Set(fillName, m_FillLoose.Get(fillName) + 1);
                m_FillAttached.Set(fillName, m_FillAttached.Get(fillName) + FillAttachments(fillItem));
            }
            m_FillTile++;
        }
        if (m_FillTile < 3600)
        {
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(FillStep, 10, false);
            return;
        }
        FillFinish();
    }
    void FillFinish()
    {
        if (!FileExist("$profile:HCCEFillProbe") && !MakeDirectory("$profile:HCCEFillProbe"))
            return;
        FileHandle fillCensus = OpenFile("$profile:HCCEFillProbe/census.txt", FileMode.WRITE);
        if (!fillCensus)
            return;
        FPrintln(fillCensus, "[HC FillProbe] census binding=TOKEN");
        foreach (string fillType, int fillLooseCount : m_FillLoose)
        {
            string fillRow = fillType + "\\t" + fillLooseCount.ToString();
            fillRow += "\\t" + m_FillAttached.Get(fillType).ToString();
            FPrintln(fillCensus, fillRow);
        }
        CloseFile(fillCensus);
        string fillMarker = "[HC FillProbe] census binding=TOKEN tiles=" + m_FillTile.ToString();
        fillMarker += " objects=" + m_FillObjects.ToString() + " types=" + m_FillLoose.Count().ToString();
        Print(fillMarker);
        Print("[HC FillProbe] done binding=TOKEN");
        FileHandle handle = OpenFile("$profile:HCCEFillProbe/complete.txt", FileMode.WRITE);
        if (!handle)
            return;
        FPrintln(handle, "TOKEN");
        CloseFile(handle);
    }
}
'''.replace('TOKEN', token).replace('HOLD', str(hold_seconds * 1000))).encode('ascii')


def prepare_bundle(stock, destination):
    """Reuse the friend bundle's authored-image and patch generators."""
    files, core, gameplay = friend_bundle.fresh_economy(stock)
    for name, data in friend_bundle.mission_images(files).items():
        target = destination / 'mission-overlay' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (destination / 'mission-patches.json').write_bytes(friend_bundle.mission_patches(files, core, gameplay))


def profiles(runtime, bundle):
    """Use the same source catalogue, normalization and writer as friend_install.

    No operator profiles, COT identities or runtime state are inherited.
    """
    rows = []
    for relative, source in friend_bundle.repo_profile_sources().items():
        path = bundle / 'profiles' / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        data = friend_bundle.profile_bytes(source)
        path.write_bytes(data)
        rows.append(('profiles/' + relative, path, 'new', rt.sha256(data)))
    ctx = friend_install.Ctx(SimpleNamespace(bundle=bundle, steam_user=''), io.StringIO(), None)
    ctx.server = runtime
    ctx.receipt = {'schema': 1, 'files': {}, 'profile_defaults': {}}
    friend_install.do_files(ctx, rows)


def apply_layers(mission, layers, bundle, workshop, mods, reports):
    loaded = {Path(workshop) / item['id'] for item in friend_install.ws.select(
        friend_install.ws.load_manifest(), list(friend_install.ws.GROUPS))
        if item['id'] and item['folder'] in {Path(r['path'].replace('\\', '/')).name
                                            for rows in mods.values() for r in rows}}
    packs = {writer.WORKSHOP_ID: {'install': FRIEND / folder, 'evidence': workshop / writer.WORKSHOP_ID}
             for writer, folder in ((sf, '@SnafuWeapons'), (tf, '@TacticalFlava'))}
    for layer in layers:
        if layer == 'base':
            continue  # Installed with common mission scripting before the CE stack.
        elif layer == 'boost':
            loot_boost.install(mission, loot_boost.default_multiplier(friend_bundle.lts.ROOT),
                               loot_boost.shipped_points(friend_bundle.lts.ROOT))
        elif layer == 'weapons':
            failures = tf.apply_weapon_packs(mission, packs, FRIEND / 'addons', reports, say=lambda _: None)
            if failures:
                raise ValueError('weapon installer refused: ' + ', '.join(failures))
        elif layer == 'travel':
            travel.install(friend_bundle.SOURCE, mission)
        elif layer == 'optional':
            candidate = overlays.plan(workshop, mission, loaded, friend_bundle.SOURCE / 'optional/overlay-policy.json')
            if overlays.unloaded_default_packs(candidate['diagnostics']):
                raise ValueError('default optional pack source missing or not loaded')
            overlays.install(candidate, mission)
        elif layer == 'variety':
            infected_variety.install(mission)
        elif layer == 'map':
            map_overlay.install(map_overlay.load_source(friend_bundle.lts.ROOT / 'config/map-overlays'), mission)
        elif layer == 'events':
            hc_events.install(friend_bundle.SOURCE, mission)
        else:
            raise ValueError('unknown treatment layer')



PACK_FILES = (sf.MANAGED + '/ce/types.xml', tf.MANAGED + '/ce/types.xml')


def parse_variants(values, treatment):
    """Normalize repeatable knobs before any runtime is built; duplicates refuse."""
    result = {}
    for item in values or ():
        name, sep, value = item.partition('=')
        if not sep or name in result:
            raise ValueError('variant must be a unique NAME=VALUE')
        if name == 'pack_tiers':
            if value != 'widen':
                raise ValueError('pack_tiers requires widen')
            result[name] = value
        elif name in ('weapons_capacity', 'pack_nominal'):
            try:
                factor = float(value)
            except ValueError as error:
                raise ValueError('variant factor must be numeric') from error
            if not math.isfinite(factor) or not (1 < factor <= 4 if name == 'weapons_capacity' else 0 < factor < 1):
                raise ValueError('variant factor outside diagnostic range')
            result[name] = factor
        else:
            raise ValueError('unknown variant name')
    if result and 'weapons' not in TREATMENTS[treatment]:
        raise ValueError('variants require the weapons layer')
    return dict(sorted(result.items()))


def type_catalog(mission):
    """Resolve effective rows from this mission's XML registrations, in load order."""
    result = {}
    for name in loot_boost.types_files(mission, include_optional=True):
        data = loot_boost.economy.read_plain(mission, name)
        for row in ET.fromstring(data).findall('type'):
            result[row.get('name').lower()] = dict(
                file=name, file_sha256=rt.sha256(data),
                nominal=int(row.findtext('nominal', '0')), min=int(row.findtext('min', '0')),
                category=sorted({n.get('name') for n in row.findall('category')}),
                usage=sorted({n.get('name') for n in row.findall('usage')}),
                tier=sorted({n.get('name') for n in row.findall('value')}))
    return result


def apply_variants(mission, variants):
    """Only mutate disposable copies; receipt each edited file and aggregate counts."""
    receipts = {}
    for knob, factor in variants.items():
        report = dict(files=[], edited_rows=0)
        names = ['mapgroupproto.xml'] if knob == 'weapons_capacity' else PACK_FILES
        for name in names:
            before = loot_boost.economy.read_plain(mission, name)
            root = ET.fromstring(before)
            counts = dict(edited_rows=0)
            if knob == 'weapons_capacity':
                defaults = {n.get('name'): int(n.get('lootmax')) for n in root.findall('./defaults/default')
                            if n.get('lootmax') is not None}
                counts.update(containers=0, groups=0, capacity_before=0, capacity_after=0,
                              group_caps_before=0, group_caps_after=0)
                for group in root.findall('group'):
                    if int(group.get('lootmax', defaults.get('group', 12))) == 0:
                        continue
                    if not {n.get('name') for n in group.findall('usage')} & {'Military', 'Police'}:
                        continue
                    changed = False
                    for container in group.findall('container'):
                        if 'weapons' not in {n.get('name') for n in container.findall('category')}:
                            continue
                        old = int(container.get('lootmax', defaults.get('container', 8)))
                        new = math.ceil(old * factor)
                        counts['containers'] += 1
                        counts['capacity_before'] += old
                        counts['capacity_after'] += new
                        if new != old:
                            container.set('lootmax', str(new))
                            counts['edited_rows'] += 1
                            changed = True
                    if changed:
                        old = int(group.get('lootmax', defaults.get('group', 12)))
                        new = max(old, sum(int(c.get('lootmax', defaults.get('container', 8)))
                                           for c in group.findall('container')))
                        group.set('lootmax', str(new))
                        counts['groups'] += 1
                        counts['group_caps_before'] += old
                        counts['group_caps_after'] += new
            else:
                counts.update(nominal_before=0, nominal_after=0, min_before=0, min_after=0)
                for row in root.findall('type'):
                    if knob == 'pack_tiers':
                        usages = {n.get('name') for n in row.findall('usage')}
                        if (usages and usages <= {'Military', 'Police', 'Prison'}
                                and 'Tier2' not in {n.get('name') for n in row.findall('value')}):
                            ET.SubElement(row, 'value', name='Tier2')
                            counts['edited_rows'] += 1
                    else:
                        changed = False
                        for field in ('nominal', 'min'):
                            node = row.find(field)
                            old = int(node.text)
                            new = loot_boost.scaled(old, factor)
                            node.text = str(new)
                            counts[field + '_before'] += old
                            counts[field + '_after'] += new
                            changed |= new != old
                        counts['edited_rows'] += int(changed)
            after = xml_text.document(root) if counts['edited_rows'] else before
            (mission / name).write_bytes(after)
            report['files'].append(dict(path=name, before_sha256=rt.sha256(before),
                                        after_sha256=rt.sha256(after), **counts))
            report['edited_rows'] += counts['edited_rows']
        report['diagnostic_only'] = True
        if knob == 'pack_nominal':
            report['policy_warning'] = 'Never a shipped policy: owner fixed both packs at 2x.'
        receipts[knob] = report
    return receipts


def stage(source_runtime, destination, *, treatment='t0', workshop=weapon_pack_guards.WORKSHOP,
          hold_seconds=240, wait_minutes=10, native_scripts=None, dry_run=False, variant=None):
    if len(TREATMENTS) > HARD_CAP or treatment not in TREATMENTS:
        raise ValueError('invalid treatment set or hard cap exceeded')
    variants = parse_variants(variant, treatment)
    if not 240 <= hold_seconds <= 3600 or not 5 <= wait_minutes <= 120 or wait_minutes*60 < hold_seconds+120:
        raise ValueError('hold needs at least 240 seconds and timeout needs 120 seconds headroom')
    # Even dry-run verifies all source bytes, mod hashes and installer composition.
    windows_root = rt.windows_runtime_root(destination)
    rt.fresh_destination(destination)
    mods, mod_source = installed_mods()
    source = rt.verify_source(source_runtime, rt.BATTLEYE_SHA256)
    stock_sha = ce_site_probe.stock_digest(source['records'])
    plan = rt.plan_header('ce-fill-probe', None, after={'variant': treatment})
    plan.update(census_version=1, variants=variants, layers=list(TREATMENTS[treatment]), mods=mods, mod_source=mod_source,
                stock_control='verified vanilla-p0-001; supplied bundle-src-005 is already HC-layered',
                stock_mission_sha256=stock_sha, run_id=secrets.token_hex(16),
                hold_seconds=hold_seconds, server_exe_sha256=rt.SERVER_EXE_SHA256)
    authored = {}
    for root in (friend_bundle.SOURCE, friend_bundle.lts.ROOT/'config',
                 friend_bundle.lts.ROOT/'mods/HollowCountryExpansionAI/data/defaults'):
        for path in sorted(root.rglob('*')):
            if path.is_file() and path.suffix in ('.json', '.xml'):
                authored[path.relative_to(friend_bundle.lts.ROOT).as_posix()] = rt._hash_file(path)[0]
    plan['authored_inputs_sha256'] = rt.sha256(json.dumps(authored, sort_keys=True).encode())
    plan['tool_sha256'] = {Path(module.__file__).name: rt._hash_file(Path(module.__file__))[0]
                          for module in (rt, friend_bundle, friend_install, overlays, loot_boost, travel,
                                         map_overlay, infected_variety, hc_events, tf, sf)}
    plan['tool_sha256']['ce_fill_probe.py'] = rt._hash_file(Path(__file__))[0]
    plan['binding'] = binding(plan)
    hook = render_hook(plan['binding'], hold_seconds)
    native = rt.native_type_names(native_scripts or Path.home()/'.cache/hollow-country/native-scripts/scripts-1.30.164289')
    found = rt.lint_hook(hook.decode(), native_types=native)
    if found:
        raise ValueError('hook lint: ' + '; '.join(found[:3]))
    with tempfile.TemporaryDirectory(prefix='hc-ce-fill-') as temporary:
        scratch = Path(temporary)
        context = dict(destination=scratch/'runtime' if dry_run else Path(destination), source=source,
                       source_runtime=Path(source_runtime), windows_root=windows_root, battleye_sha256=rt.BATTLEYE_SHA256)
        built = rt.build_runtime(context, hook, purpose='ce-probe')
        bundle = scratch/'bundle'
        bundle.mkdir()
        with contextlib.redirect_stdout(io.StringIO()):
            prepare_bundle(source['mission'], bundle)
            candidate = overlays.bundle_candidate(bundle, built['mission_dest'])
            if 'base' not in TREATMENTS[treatment]:
                # Select generator outputs; never reimplement their transformations.
                # t0 keeps the same HC JSON/gameplay support but stock CE XML/maps.
                candidate['files'] = {n: data for n, data in candidate['files'].items() if n.endswith('.json')}
                candidate['before'] = {n: candidate['before'][n] for n in candidate['files']}
            overlays.install(candidate, built['mission_dest'], managed_name=overlays.BUNDLE_MANAGED)
            apply_layers(built['mission_dest'], TREATMENTS[treatment], bundle, Path(workshop), mods, scratch/'reports')
            plan['variant_receipts'] = apply_variants(built['mission_dest'], variants)
            catalog_raw = json.dumps(type_catalog(built['mission_dest']), separators=(',', ':')).encode()
            (context['destination'] / CATALOG_NAME).write_bytes(catalog_raw)
            plan['type_catalog'] = dict(path=CATALOG_NAME, sha256=rt.sha256(catalog_raw))
            profiles(context['destination'], bundle)
        old_hook = hook
        plan['binding'] = binding(plan)
        hook = render_hook(plan['binding'], hold_seconds)
        found = rt.lint_hook(hook.decode(), native_types=native)
        if found:
            raise ValueError('hook lint: ' + '; '.join(found[:3]))
        init = built['mission_dest'] / 'init.c'
        data = init.read_bytes()
        if data.count(old_hook) != 1:
            raise ValueError('staged hook differs before final binding')
        init.write_bytes(data.replace(old_hook, hook))
        manifest = built['manifest']
        manifest['hook_sha256'] = rt.sha256(hook)
        manifest['files']['init.c'].update(staged_sha256=rt.sha256(init.read_bytes()),
                                           staged_bytes=init.stat().st_size)
        (built['mission_dest'] / rt.dm.MARKER_NAME).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        # write_plan re-verifies the complete mod inventory after installers finish.
        built['staged'] = [dict(path=n, sha256=rt._hash_file(context['destination']/n)[0],
                                bytes=size) for n, size in sorted(rt.dm.walk_plain(context['destination']).items())]
        hashes = {r['path']: r['sha256'] for r in built['staged']}
        prefix = 'mpmissions/' + rt.MISSION_NAME + '/'
        for row in built['mission_files']:
            row['sha256'] = hashes[prefix+row['path']]
            if row['sha256'] != row['source_sha256']:
                row['origin'] = 'treatment-or-instrumentation'
        plan.update(rt.plan_runtime_fields(context, built, mods=mods))
        plan.update(mission_files=built['mission_files'], staged_files=built['staged'],
                    probe=dict(hold_seconds=hold_seconds, wait_minutes=wait_minutes, hook_sha256=rt.sha256(hook)))
        rt.write_plan(context['destination'], PLAN_NAME, plan)
    if dry_run:
        return dict(kind=plan['kind'], status='inputs-validated-not-staged', variant=treatment,
                    variants=variants, variant_receipts=plan['variant_receipts'],
                    layers=plan['layers'], mod_directories=sum(map(len, mods.values())))
    return plan


WARNING = re.compile(r'\[CE\]\[LootRespawner\].*?Item \[\d+\] is hard to place, performance drops: "([A-Za-z0-9_]+)"')
STAMP = re.compile(r'^\s*(\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)\s+')


def timestamp(line):
    match = STAMP.match(line)
    if not match:
        raise ValueError('missing RPT timestamp')
    h, m, s = map(float, match.groups())
    if h >= 24 or m >= 60 or s >= 60:
        raise ValueError('invalid RPT timestamp')
    return h*3600+m*60+s


def parse_census(raw, token):
    """Strict, bound tab-separated census; case-insensitive class uniqueness."""
    lines = raw.decode('utf-8').splitlines()
    if not lines or lines[0] != '[HC FillProbe] census binding=' + token:
        raise ValueError('missing or mismatched census binding header')
    rows = {}
    for line in lines[1:]:
        fields = line.split('\t')
        if (len(fields) != 3 or not re.fullmatch(r'[A-Za-z0-9_]+', fields[0])
                or any(not re.fullmatch(r'[0-9]+', value) for value in fields[1:])):
            raise ValueError('malformed census row')
        name = fields[0].lower()
        if name in rows:
            raise ValueError('duplicate census type')
        rows[name] = dict(loose=int(fields[1]), attached=int(fields[2]))
    return rows


def fill_ratios(rows, catalog):
    """Include every staged definition, even classes absent from the census."""
    files, signatures, classes = {}, {}, {}
    for name, definition in sorted(catalog.items()):
        measured = rows.get(name, dict(loose=0, attached=0))
        classes[name] = dict(**measured, definition=definition)
        signature = json.dumps([definition[k] for k in ('category', 'usage', 'tier')], separators=(',', ':'))
        for groups, key in ((files, definition['file']), (signatures, signature)):
            group = groups.setdefault(key, dict(nominal=0, min=0, loose=0, attached=0))
            for field in ('nominal', 'min'):
                group[field] += definition[field]
            for field in ('loose', 'attached'):
                group[field] += measured[field]
    for groups in (files, signatures):
        for group in groups.values():
            group['fill_ratio'] = group['loose'] / group['nominal'] if group['nominal'] else None
    return dict(per_defining_file=files, per_signature=signatures, types=classes,
                below_min=[n for n, r in classes.items() if r['loose'] < r['definition']['min']],
                zero_with_nominal=[n for n, r in classes.items() if not r['loose'] and r['definition']['nominal'] > 0],
                unattributed={n: r for n, r in rows.items() if n not in catalog})


def read_census(runtime, token, catalog, required=False):
    path = runtime / 'profiles/HCCEFillProbe/census.txt'
    if not path.exists() and not required:
        return dict(present=False)
    raw = rt._read_bounded(path, MAX_RPT_BYTES)
    rows = parse_census(raw, token)
    if not catalog or any('nominal' not in r or 'min' not in r for r in catalog.values()):
        raise ValueError('census requires staged nominal/min catalog')
    return dict(present=True, sha256=rt.sha256(raw), observed_types=len(rows), **fill_ratios(rows, catalog))


def economy_logs(runtime):
    """Optional DIAG export: absence is evidence too; never depend on it."""
    records = []
    directory = runtime / 'storage/log'
    for path in sorted(directory.glob('*.csv')):
        raw = rt._read_bounded(path, MAX_RPT_BYTES)
        records.append(dict(file=path.name, sha256=rt.sha256(raw),
                            rows=sum(1 for _ in csv.reader(io.StringIO(raw.decode('utf-8-sig'))))))
    return dict(present=bool(records), files=records, row_count_includes_header=True)


def ingest(rpt, out, plan_path=None):
    rpt = Path(rpt)
    plan_path = Path(plan_path) if plan_path else rpt.parent.parent/PLAN_NAME
    plan_raw = rt._read_bounded(plan_path, rt.MAX_PLAN_BYTES)
    plan = json.loads(plan_raw)
    if (plan.get('kind') != 'ce-fill-probe' or plan.get('variant') not in TREATMENTS
            or plan.get('layers') != list(TREATMENTS[plan['variant']])
            or plan.get('binding') != binding(plan) or plan['server_exe_sha256'] != rt.SERVER_EXE_SHA256
            or not 240 <= plan['hold_seconds'] <= 3600):
        raise ValueError('invalid fill probe plan or binding')
    normalized = parse_variants([f'{k}={v}' for k, v in plan.get('variants', {}).items()], plan['variant'])
    if normalized != plan.get('variants', {}):
        raise ValueError('invalid variants')
    rt.validate_mods(plan['mods'])
    if plan['arguments'] != rt.server_arguments(plan['runtime_root'], plan['mods']):
        raise ValueError('invalid fill probe arguments')
    raw = rt._read_bounded(rpt, MAX_RPT_BYTES)
    text = raw.decode('utf-8', errors='replace')
    markers = re.findall(r'\[HC FillProbe\] (begin|done) binding=([a-f0-9]{64})', text)
    if markers != [('begin', plan['binding']), ('done', plan['binding'])]:
        raise ValueError('incomplete probe or mismatched run binding')
    lines = text.splitlines()
    begin = next(i for i, line in enumerate(lines) if '[HC FillProbe] begin' in line)
    done = next(i for i, line in enumerate(lines) if '[HC FillProbe] done' in line)
    elapsed = (timestamp(lines[done])-timestamp(lines[begin])) % 86400
    if not plan['hold_seconds']-1 <= elapsed <= plan.get('probe', {}).get('wait_minutes', 120)*60:
        raise ValueError('incomplete mission hold')
    summaries, counts, first, last = [], {}, None, None
    for index, line in enumerate(lines):
        match = WARNING.search(line)
        if 'is hard to place, performance drops:' in line and not match:
            raise ValueError('malformed hard-to-place warning')
        if match:
            if index > done:
                raise ValueError('warning after completion; extend the hold before comparing treatments')
            stamp = timestamp(line)
            row = counts.setdefault(match[1], dict(count=0, first_timestamp=stamp, last_timestamp=stamp))
            row['count'] += 1
            row['last_timestamp'] = stamp
            first = stamp if first is None else first
            last = stamp
        if '[CE]' in line and any(term in line.lower() for term in ('init', 'nominal:', 'total in map:', 'economy loaded')):
            # Only CE summary content, never the RPT header/command line or identities.
            summaries.append(dict(timestamp=timestamp(line), text=line[line.index('[CE]'):]))
    if not summaries:
        raise ValueError('missing CE init summary')
    catalog = {}
    if 'type_catalog' in plan:
        pin = plan['type_catalog']
        if pin.get('path') != CATALOG_NAME:
            raise ValueError('invalid type catalog path')
        catalog_raw = rt._read_bounded(plan_path.parent / CATALOG_NAME, MAX_RPT_BYTES)
        if rt.sha256(catalog_raw) != pin['sha256']:
            raise ValueError('type catalog hash drift')
        catalog = json.loads(catalog_raw)
    census = read_census(plan_path.parent, plan['binding'], catalog, required=bool(plan.get('census_version')))
    if census['present']:
        census_markers = re.findall(r'\[HC FillProbe\] census binding=([a-f0-9]{64}) tiles=(\d+) objects=(\d+) types=(\d+)', text)
        if (len(census_markers) != 1 or census_markers[0][0] != plan['binding']
                or int(census_markers[0][1]) != 3600
                or int(census_markers[0][3]) != census['observed_types']
                or not text.index('[HC FillProbe] begin') < text.index('[HC FillProbe] census') < text.index('[HC FillProbe] done')):
            raise ValueError('missing or invalid census completion marker')
        census['tiles'], census['objects'], census['observed_types'] = map(int, census_markers[0][1:])
    for name, row in counts.items():
        row['definition'] = catalog.get(name.lower())
    result = dict(schema=2, census=census, economy_log=economy_logs(plan_path.parent), variants=plan.get('variants', {}),
                  variant_receipts=plan.get('variant_receipts', {}), status='observed-not-accepted', treatment=plan['variant'],
                  total=sum(r['count'] for r in counts.values()), first_timestamp=first, last_timestamp=last,
                  types=dict(sorted(counts.items())), ce_init_summaries=summaries, mission_hold_seconds=elapsed,
                  provenance=dict(plan_sha256=rt.sha256(plan_raw), rpt_sha256=rt.sha256(raw),
                    binding=plan['binding'], stock_mission_sha256=plan['stock_mission_sha256'],
                    server_exe_sha256=plan['server_exe_sha256'], mods=plan['mods'], mod_source=plan['mod_source'],
                    authored_inputs_sha256=plan.get('authored_inputs_sha256'), tool_sha256=plan.get('tool_sha256'),
                    staged_utc=plan['staged_utc'], ingested_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    rt.new_file(out, (json.dumps(result, indent=2)+'\n').encode())
    return result


def compare(paths):
    """Compare every run against the first; refuse incompatible native controls."""
    if len(paths) < 2:
        raise ValueError('compare requires at least two summaries')
    runs = [json.loads(rt._read_bounded(Path(p), MAX_RPT_BYTES)) for p in paths]
    controls = ('server_exe_sha256', 'stock_mission_sha256')
    expected = tuple(runs[0]['provenance'].get(k) for k in controls)
    if not all(expected):
        raise ValueError('missing compare control hashes')
    output = []
    base = runs[0]['types']
    for run in runs:
        if tuple(run['provenance'].get(k) for k in controls) != expected:
            raise ValueError('compare server executable or stock mission mismatch')
        files, signatures = {}, {}
        for row in run['types'].values():
            definition = row.get('definition')
            if not definition:
                raise ValueError('compare requires staged runtime type attribution; re-ingest with a new plan')
            file = definition['file']
            signature = json.dumps([definition[k] for k in ('category', 'usage', 'tier')], separators=(',', ':'))
            files[file] = files.get(file, 0) + row['count']
            signatures[signature] = signatures.get(signature, 0) + row['count']
        if run['total'] != sum(row['count'] for row in run['types'].values()):
            raise ValueError('summary total differs from type counts')
        names = set(base) | set(run['types'])
        deltas = {n: (base.get(n, {}).get('count', 0), run['types'].get(n, {}).get('count', 0)) for n in names}
        output.append(dict(census=run.get('census', dict(present=False)),
                           economy_log=run.get('economy_log', dict(present=False)), treatment=run['treatment'], variants=run.get('variants', {}), total=run['total'],
                           per_defining_file=dict(sorted(files.items())), per_signature=dict(sorted(signatures.items())),
                           went_to_zero=sorted(n for n, (a, b) in deltas.items() if a > 0 and b == 0),
                           rose={n: dict(before=a, after=b) for n, (a, b) in sorted(deltas.items()) if b > a}))
    return dict(status='compared-not-accepted', baseline='first summary', runs=output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    st = sub.add_parser('stage')
    st.add_argument('--destination', type=Path, required=True)
    st.add_argument('--source-runtime', type=Path, default=Path(rt.DEFAULT_SOURCE_RUNTIME))
    st.add_argument('--treatment', choices=TREATMENTS, default='t0')
    st.add_argument('--workshop', type=Path, default=weapon_pack_guards.WORKSHOP)
    st.add_argument('--native-scripts', type=Path)
    st.add_argument('--hold-seconds', type=int, default=240)
    st.add_argument('--wait-minutes', type=int, default=10)
    st.add_argument('--variant', action='append', default=[])
    st.add_argument('--dry-run', action='store_true')
    ing = sub.add_parser('ingest')
    ing.add_argument('--rpt', type=Path, required=True)
    ing.add_argument('--out', type=Path, required=True)
    ing.add_argument('--plan', type=Path)
    cmp = sub.add_parser('compare')
    cmp.add_argument('summaries', type=Path, nargs='+')
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    try:
        if command == 'compare':
            result = compare(args['summaries'])
        elif command == 'stage':
            result = stage(**args)
        else:
            result = ingest(args['rpt'], args['out'], args['plan'])
        print(json.dumps(result if command == 'compare' else {k: result[k] for k in
              ('status', 'variant', 'variants', 'variant_receipts', 'total') if k in result}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, friend_install.Refused, friend_bundle.Refused) as error:
        # Native logs and operator paths are never echoed into public output.
        reason = re.sub(r'(?:[A-Za-z]:)?[/\\][^\s;]*', '<path>', str(error)) if isinstance(error, ValueError) else type(error).__name__
        print('ce_fill_probe refused: ' + reason)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
