"""Stage/ingest a disposable native CE initial-fill experiment; never launch DayZ."""
import argparse
import contextlib
import datetime
import io
import json
from pathlib import Path
import re
import secrets
import tempfile
from types import SimpleNamespace

from tools.setup import probe_runtime as rt, ce_site_probe, friend_bundle, friend_install
from tools.package import (optional_overlays as overlays, loot_boost, travel, map_overlay,
                           infected_variety, hc_events, tactical_flava_optional as tf,
                           snafu_optional as sf, weapon_pack_guards)

PLAN_NAME = 'ce-fill-probe-plan.json'
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
    for key in ('authored_inputs_sha256', 'tool_sha256'):
        if key in plan:
            fields[key] = plan[key]
    return rt.sha256(json.dumps(fields, sort_keys=True, separators=(',', ':')).encode())


def render_hook(token, hold_seconds):
    # Same native OnInit/CallLater/file APIs as ce_site_probe; no CE/gameplay mutation.
    return ('''\nclass HCDisposableDiagnosticMission : CustomMission
{
    override void OnInit()
    {
        super.OnInit();
        Print("[HC FillProbe] begin binding=TOKEN");
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(FillFinish, HOLD, false);
    }
    void FillFinish()
    {
        Print("[HC FillProbe] done binding=TOKEN");
        if (!MakeDirectory("$profile:HCCEFillProbe"))
            return;
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


def stage(source_runtime, destination, *, treatment='t0', workshop=weapon_pack_guards.WORKSHOP,
          hold_seconds=240, wait_minutes=10, native_scripts=None, dry_run=False):
    if len(TREATMENTS) > HARD_CAP or treatment not in TREATMENTS:
        raise ValueError('invalid treatment set or hard cap exceeded')
    if not 240 <= hold_seconds <= 3600 or not 5 <= wait_minutes <= 120 or wait_minutes*60 < hold_seconds+120:
        raise ValueError('hold needs at least 240 seconds and timeout needs 120 seconds headroom')
    # Even dry-run verifies all source bytes, mod hashes and installer composition.
    windows_root = rt.windows_runtime_root(destination)
    if Path(destination).exists() or Path(destination).is_symlink():
        raise ValueError('fresh destination required')
    mods, mod_source = installed_mods()
    source = rt.verify_source(source_runtime, rt.BATTLEYE_SHA256)
    stock_sha = ce_site_probe.stock_digest(source['records'])
    plan = rt.plan_header('ce-fill-probe', None, after={'variant': treatment})
    plan.update(layers=list(TREATMENTS[treatment]), mods=mods, mod_source=mod_source,
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
            profiles(context['destination'], bundle)
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
    result = dict(schema=1, status='observed-not-accepted', treatment=plan['variant'],
                  total=sum(r['count'] for r in counts.values()), first_timestamp=first, last_timestamp=last,
                  types=dict(sorted(counts.items())), ce_init_summaries=summaries, mission_hold_seconds=elapsed,
                  provenance=dict(plan_sha256=rt.sha256(plan_raw), rpt_sha256=rt.sha256(raw),
                    binding=plan['binding'], stock_mission_sha256=plan['stock_mission_sha256'],
                    server_exe_sha256=plan['server_exe_sha256'], mods=plan['mods'], mod_source=plan['mod_source'],
                    authored_inputs_sha256=plan.get('authored_inputs_sha256'), tool_sha256=plan.get('tool_sha256'),
                    staged_utc=plan['staged_utc'], ingested_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    rt.new_file(out, (json.dumps(result, indent=2)+'\n').encode())
    return result


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
    st.add_argument('--dry-run', action='store_true')
    ing = sub.add_parser('ingest')
    ing.add_argument('--rpt', type=Path, required=True)
    ing.add_argument('--out', type=Path, required=True)
    ing.add_argument('--plan', type=Path)
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    try:
        result = stage(**args) if command == 'stage' else ingest(args['rpt'], args['out'], args['plan'])
        print(json.dumps({k: result[k] for k in ('status', 'variant', 'total') if k in result}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, friend_install.Refused, friend_bundle.Refused) as error:
        # Native logs and operator paths are never echoed into public output.
        reason = re.sub(r'(?:[A-Za-z]:)?[/\\][^\s;]*', '<path>', str(error)) if isinstance(error, ValueError) else type(error).__name__
        print('ce_fill_probe refused: ' + reason)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
