"""Export a self-contained Hollow Country server bundle for a friend's dedicated server.

Input is the local server that was set up with local_test_session.py apply: its applied mission
folder, its profiles folder, the signed @HollowCountry session mod (and optionally
@HollowCountryExpansionAI, loaded after it with -mod on server and clients) and its serverDZ.cfg.
Output is a new folder the owner can zip and hand
over: authored mission overlays and minimal merge patches, the Hollow Country profile configuration, the signed mods, their public
keys, a start-server.bat, a serverDZ.cfg snippet and a README with the Workshop download commands.

What it never copies: CE storage (storage_*), rollback backups and receipts, logs, any runtime
state under the profile (event/group state, journals, leases, hordes, ecology state, audits),
private signing keys (any .biprivatekey refuses the whole export), symlinks (refused), or a
password value from serverDZ.cfg. Third-party Workshop mods are named by id only; the friend
downloads them with their own steamcmd login.

Coverage is excluded from exported files; qualify it separately against the friend stock.
Sampler results and census inputs stay outside the checkout and are never bundled.

This tool establishes nothing about DayZ behaviour. Usage:

  python3 -m tools.setup.friend_bundle build --mission <server>/mpmissions/dayzOffline.chernarusplus \
      --profiles <profiles> --mod <session>/@HollowCountry [--addon <session>/@HollowCountryExpansionAI] \
      --server-cfg <server>/serverDZ.cfg --out <new folder>
"""
import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile

from tools.package import ce_coverage
from tools.setup import local_test_session as lts
from tools.setup import workshop_sync as ws
from tools.package import optional_overlays as overlays, travel, pbo
from tools.package import snafu_optional, tactical_flava_optional
from tools.package import loot_boost, map_overlay
import xml.etree.ElementTree as ET

SOURCE = lts.ROOT / 'mission/hollow-country'
SETUP_TOOLS = ('friend_install.py', 'server_report.py', 'workshop_sync.py', 'workshop_mods.json')
SETUP_BATS = ('install-hollow-country.bat', 'server-report.bat')
BUNDLE_TOOLS = ('xml_text.py', 'optional_overlays.py', 'rag_optional.py', 'travel.py', 'economy.py', 'ce_extensions.py',
                'datamined_items.py', 'datamined_items.json', 'loot_boost.py', 'firearms_roster.json',
                'map_overlay.py')
# The map overlay layer set the friend's installer validates and installs (map_overlay.py reads it from here).
MAP_OVERLAY_CONFIG = 'config/map-overlays'

# Mission files that are local state or tool rollback data, never configuration.
MISSION_EXCLUDE_DIRS = ('storage_*',)
MISSION_EXCLUDE_FILES = ('*.backup', '*.next', 'receipt.json', 'verification.json', '*.log', '*.rpt',
                         '*.adm', '*.mdmp', 'hollow-country-*receipt*.json')
# Profile files that are configuration (everything else under the profile is state or logs). No acceptance
# marker ships: the V1/V2 features are on by default, an operator's own .disable opt-outs stay local, and the
# xai_diagnostic_spawn.enable diagnostic must never reach a friend's server.
PROFILE_INCLUDE = (
    'HollowCountry/settings.json',
    'HollowCountry/stamina.json',
    'HollowCountry/interiors.json',
    'HollowCountry/interiors-measured-profile.json',
    'HollowCountry/measured-interiors/**',
    'HollowCountry/templates/**',
    'HollowCountry/expansion-ai.json',
    'HollowCountry/expansion-ai-sites.json',
    'HollowCountry/expansion-ai-localities.json',
    'HollowCountry/Ecology/settings.json',
    'HollowCountry/Events/settings.json',
    'HollowCountry/Groups/settings.json',
    'HollowCountry/Groups/places.json',
    'HollowCountry/Infected/config.json',
    'HollowCountry/Infected/production-rooms.json',
    'HollowCountry/Infected/measured-rooms.json',
    'ExpansionMod/Settings/AISettings.json',
    'ExpansionMod/Loadouts/HollowCountry_*.json',
)
PORTS = '2302-2305 UDP (game) and 27016 UDP (Steam query)'
MISSION_TEMPLATE = re.compile(r'\btemplate\s*=\s*"([^"\r\n]+)"\s*;')


class Refused(Exception):
    pass


def _walk(root):
    """Every regular file under root as (relative posix path, path). Symlinks and specials refuse."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise Refused('%s is not a real folder (symlink or missing)' % root.name)
    rows = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in sorted(dirnames + filenames):
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                raise Refused('symlink refused: %s' % rel)
            if name.lower().endswith('.biprivatekey'):
                raise Refused('private signing key (.biprivatekey) found: %s; never bundle it' % rel)
            if name in filenames:
                if not path.is_file():
                    raise Refused('not a regular file: %s' % rel)
                rows.append((rel, path))
        dirnames.sort()
    return sorted(rows)


def _matches(name, patterns):
    return any(fnmatch.fnmatch(name.lower(), p.lower()) for p in patterns)


def mission_files(mission):
    keep, dropped = [], 0
    for rel, path in _walk(mission):
        parts = PurePosixPath(rel).parts
        if _matches(parts[0], MISSION_EXCLUDE_DIRS) and len(parts) > 1:
            dropped += 1
        elif _matches(parts[-1], MISSION_EXCLUDE_FILES):
            dropped += 1
        else:
            keep.append((rel, path))
    return keep, dropped


def coverage_report(result_path, mission=None):
    """An unvalidated optional result is left out; an installed delta must still restore safely."""
    try:
        return ce_coverage.validate(result_path, mission)
    except (ValueError, OSError, KeyError, TypeError) as error:
        return {'status': 'invalid', 'reason': lts.redact_home(error)}


def coverage_files(mission, rows, result_path):
    """Apply or remove coverage on scratch bytes only; never export sampler inputs or recovery data."""
    if result_path is not None:
        lts.outside_checkouts(result_path, 'CE coverage sampler result')
        lts.no_links(result_path, 'CE coverage sampler result')
    report = coverage_report(result_path)
    accepted = report['status'] == 'result-valid'
    managed = Path(mission) / ce_coverage.MANAGED
    keep = [(rel, path) for rel, path in rows if PurePosixPath(rel).parts[0] != ce_coverage.MANAGED]
    if not accepted and not managed.exists():
        print('left out CE building coverage: %s (%s)' % (report['status'].upper(), report['reason']))
        return keep
    with tempfile.TemporaryDirectory(prefix='hc-bundle-coverage-') as temp:
        scratch = Path(temp) / 'mission'
        scratch.mkdir()
        source = Path(mission) / ce_coverage.PROTO
        (scratch / ce_coverage.PROTO).write_bytes(source.read_bytes())
        # The existing installer checks pinning receipts when restoring an already installed delta.
        for folder in (*ce_coverage.PINNING_FOLDERS, ce_coverage.MANAGED):
            source_dir = Path(mission) / folder
            if source_dir.exists():
                shutil.copytree(source_dir, scratch / folder)
        if managed.exists():
            ce_coverage.rollback(scratch)
        if accepted:
            report = coverage_report(result_path, scratch)
            accepted = report['status'] == 'result-valid'
        if accepted:
            result_file = result_path
            if result_file is None:
                result_file = ce_coverage.REPO_ROOT / ce_coverage.SHIPPED_RESULT
            delta = Path(temp) / 'delta'
            ce_coverage.write_delta(delta, ce_coverage.generate(Path(result_file).read_bytes(), scratch))
            ce_coverage.install(delta, scratch)
        proto = (scratch / ce_coverage.PROTO).read_bytes()
    if not accepted:
        print('left out CE building coverage: %s (%s)' % (report['status'].upper(), report['reason']))
    return [(rel, proto) for rel, _ in keep if rel == ce_coverage.PROTO] + [
        (rel, path) for rel, path in keep if rel != ce_coverage.PROTO]


def _profile_allowed(rel):
    for pattern in PROFILE_INCLUDE:
        if pattern.endswith('/**'):
            if rel.startswith(pattern[:-2]):
                return True
        elif fnmatch.fnmatchcase(rel, pattern) and '/' not in rel[len(pattern.rsplit('/', 1)[0]) + 1:]:
            return True
    return False


# The template pack refuses to load (rooms_conflict) while either legacy room owner sits beside it.
LEGACY_ROOM_OWNERS = ('HollowCountry/interiors.json', 'HollowCountry/Infected/production-rooms.json')
TEMPLATE_INDEX = 'HollowCountry/templates/index.json'


def profile_files(profiles):
    keep, dropped = [], 0
    for rel, path in _walk(profiles):
        if _profile_allowed(rel):
            keep.append((rel, path))
        else:
            dropped += 1
    if any(rel == TEMPLATE_INDEX for rel, _ in keep):
        legacy = [rel for rel, _ in keep if rel in LEGACY_ROOM_OWNERS]
        if legacy:
            keep = [(rel, path) for rel, path in keep if rel not in LEGACY_ROOM_OWNERS]
            dropped += len(legacy)
            print('left out %s: the interior template pack refuses to load (rooms_conflict) beside them'
                  % ', '.join(legacy))
    return keep, dropped


def mod_files(mod, need_key):
    rows = _walk(mod)
    names = {rel for rel, _ in rows}
    pbos = [rel for rel in names if rel.startswith('addons/') and rel.lower().endswith('.pbo')]
    if not pbos:
        raise Refused('%s has no addons/*.pbo' % Path(mod).name)
    for pbo in pbos:
        if not any(r.startswith(pbo + '.') and r.lower().endswith('.bisign') for r in names):
            raise Refused('%s is not signed (no %s.*.bisign); build and sign it first' % (pbo, pbo))
    keys = [(rel, path) for rel, path in rows if rel.lower().endswith('.bikey')]
    if need_key and not keys:
        raise Refused('%s has no keys/*.bikey' % Path(mod).name)
    return rows, keys


def server_settings(cfg_text, mission_name):
    values = {}
    for statement in lts._statements(lts.split_bom(cfg_text)[1]):
        for key in lts.MANAGED_KEYS:
            if statement['key'].lower() == key.lower():
                values[key] = statement['value'].strip()
    match = MISSION_TEMPLATE.search(cfg_text)
    template = match.group(1) if match else mission_name
    lines = ['// Hollow Country settings for serverDZ.cfg. Set each key below in your own serverDZ.cfg',
             '// (replace the existing line). Keep your own hostname, passwords and other settings.']
    for key in lts.MANAGED_KEYS:
        if key in values:
            lines.append('%s = %s;' % (key, values[key]))
    lines += ['', '// and in class Missions { class DayZ { ... }; }:', 'template = "%s";' % template, '']
    return '\n'.join(lines), template


def crlf(data):
    """Windows batch files must use CRLF line endings."""
    return data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')


def launcher(items):
    args = ' '.join('"%s"' % line for line in ws.launch_lines(items))
    lines = ['@echo off', 'rem Hollow Country dedicated server. Run from the DayZServer folder.',
             'cd /d "%~dp0"',
             'start "" DayZServer_x64.exe -config=serverDZ.cfg -profiles=profiles -port=2302 %s '
             '-dologs -adminlog -netlog -freezecheck' % args, '']
    return '\r\n'.join(lines)


def readme(items, template, addon):
    third = [i for i in items if i['id'] and not i['publish']]
    lines = [
        'Hollow Country - friend server bundle',
        '=====================================',
        '',
        'Easiest way: double-click install-hollow-country.bat (or run it from a terminal). It walks the steps',
        'below one by one, shows what it will change first, makes backups, never deletes saves, and can be run',
        'again safely. It asks for the Steam login name you want steamcmd to use; steamcmd asks for the password',
        'itself, nothing here sees it. Check an existing install any time with: install-hollow-country.bat --check',
        'After a play session, run server-report.bat and upload the file it writes (see the end of this file).',
        '',
        'The manual steps, if you prefer them:',
        '',
        '1. Install DayZ Server (Steam app 223350) with steamcmd, and stop it if it is running.',
        '2. Download the Workshop mods with your own steamcmd login (type your password yourself):',
        '     steamcmd +login <your steam name>',
    ]
    for item in third:
        lines.append('     workshop_download_item 221100 %s   (%s -> copy to %s)' % (item['id'], item['name'], item['folder']))
    lines += [
        '     quit',
        '   Copy each downloaded folder from steamapps/workshop/content/221100/<id> into the server folder',
        '   under the name shown, and copy every .bikey from their keys/ folders into the server keys/ folder.',
        '   Hollow Country itself is in this bundle (@HollowCountry); players subscribe to its Workshop item.',
    ]
    if addon:
        lines.append('   Players subscribe to @HollowCountryExpansionAI when this server uses it; load it after @HollowCountry.')
    lines += [
        '',
        'Default dependencies are subscribed from the Workshop, never repacked or included as third-party files.',
        '  @HollowCountryExpansionAI uses Community Framework (CF), COT, Dabs Framework, Expansion-Core, Expansion-AI and Expansion Navigation (GPS).',
        '  RaG_Core and RaG Immersive Vehicles are default subscribed dependencies after the weapons packs.',
        '  COT permissions stay in the server profile; see docs/COT_PERMISSIONS.md. Admin ids are never written to git.',
        '  Ambient Animals Pack, Survivor Animations and DayZ-Bicycle are default subscriptions.',
        '  Load the listed dependencies before @HollowCountry, then @HollowCountryExpansionAI on every peer.',
        '  Review current Workshop terms and the optional-overlay instructions below before installing.',
        '',
    ]
    lines += [
        '3. Copy from this bundle into the server folder:',
        '     @HollowCountry/' + ('  and  @HollowCountryExpansionAI/' if addon else ''),
        '     keys/*.bikey            -> keys/',
        '     Keep your own stock mpmissions/%s/; apply the overlay using the commands below.' % template,
        '     profiles/               -> profiles/ (the -profiles folder)',
        '     start-server.bat',
        '4. Edit serverDZ.cfg as shown in serverDZ-hollow-country.txt. Keep verifySignatures = 2 and BattlEye on.',
        '5. Forward ports %s to the server PC.' % PORTS,
        '6. Run start-server.bat. Players launch DayZ with the same -mod list (the DayZ launcher does this',
        '   when they join from the server browser after subscribing to the mods).',
        '   Server and every client use this exact list:',
    ]
    lines += ['     ' + line for line in ws.launch_lines(items) if line.startswith('-mod=')]
    lines += [
        '',
        'After a play session: run server-report.bat. It writes hollow-country-report-<date-time>.md (a redacted',
        'summary of the server log: no player names, ids, IP addresses, passwords or home folders; at most 512 KB).',
        'Read it once, then upload that file only: open a new issue titled "Server report <date>" on the',
        'Hollow Country GitHub repository with the "Server report" template and drag the file in, or add it under',
        'reports/friend-server/ in a pull request. Never upload the raw .RPT, .ADM or .mdmp files.',
        '',
        'bundle-manifest.json lists the SHA-256 of every file in this bundle.',
        '',
    ]
    return '\r\n'.join(lines)


def build(args):
    out = Path(args.out)
    if out.exists() or out.is_symlink():
        raise Refused('output %s already exists; choose a new folder' % out)
    mission = Path(args.mission)
    plan = []  # (destination relative path, source path or bytes)
    try:
        travel.validate(SOURCE)
        overlays.read(Path(travel.__file__))
    except (OSError, ValueError) as error:
        raise Refused('travel CE source missing or invalid: %s' % error) from error
    try:
        policy = json.loads(overlays.read(SOURCE / 'optional/overlay-policy.json'))
        if not isinstance(policy, dict) or policy.get('schema') != 1:
            raise ValueError('unknown optional overlay policy')
        for name in BUNDLE_TOOLS:
            overlays.read(lts.ROOT / 'tools/package' / name)
        for name in SETUP_TOOLS + SETUP_BATS:
            overlays.read(lts.ROOT / 'tools/setup' / name)
    except (OSError, ValueError) as error:
        raise Refused('optional overlay source missing or invalid: %s' % error) from error
    m_keep, m_drop = mission_files(mission)
    # Remove dependency-derived bytes before selecting our authored overlay.
    prefix = 'mpmissions/' + mission.name + '/'
    clean = overlays.friend_bundle_plan(mission, [(prefix + rel, path) for rel, path in m_keep])
    clean = {rel[len(prefix):]: data if isinstance(data, bytes) else data.read_bytes()
             for rel, data in clean if rel.startswith(prefix)}
    authored = {}
    for rel, data in clean.items():
        top = PurePosixPath(rel).parts[0]
        # Weapon-pack deltas are generated from the installed third-party Workshop items: never export them.
        # The owner's own map overlay install (hollow-country-overlays) is local state: the friend installs the layers.
        own = top.startswith('hollow-country') and top not in (travel.MANAGED, ce_coverage.MANAGED, loot_boost.MANAGED,
                                                                snafu_optional.MANAGED, tactical_flava_optional.MANAGED,
                                                                map_overlay.MANAGED)
        if own or rel == 'expansion/settings/AIPatrolSettings.json':
            if PurePosixPath(rel).name not in ('delta-manifest.json', 'economy-report.json', 'gameplay-report.json'):
                authored[rel] = data
    # The friend's own bundle-apply boosts loot once on their stock mission: export the pre-boost bytes of
    # every file a local loot boost holds (for example the economy types), never the doubled ones.
    try:
        unboosted = loot_boost.installed_before(mission)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise Refused('local loot boost cannot be undone in the export: %s' % error) from error
    for rel, data in unboosted.items():
        if rel in authored:
            authored[rel] = data
    # Every authored V2 JSON is copied at its runtime mission path. Never infer
    # the catalog from a hard-coded list that silently misses the next module.
    for path in sorted(SOURCE.rglob('*.json')):
        rel = path.relative_to(SOURCE).as_posix()
        authored['hollow-country/' + rel] = overlays.read(path)
    plan += [('mission-overlay/' + rel, data) for rel, data in sorted(authored.items())]
    m_drop += len(m_keep) - len(authored.keys() & clean.keys())
    core = overlays.xml(clean['cfgeconomycore.xml'], 'economycore')
    changes = []
    for node in core.findall('ce'):
        folder = node.get('folder', '')
        if folder.startswith('hollow-country') and not folder.startswith((travel.MANAGED, overlays.MANAGED, ce_coverage.MANAGED,
                                                                                   snafu_optional.MANAGED, tactical_flava_optional.MANAGED)):
            node.tail = None
            changes.append({'before': None, 'after': ET.tostring(node, encoding='unicode').strip()})
    backup = mission / 'hollow-country/core.backup'
    if backup.exists():
        old_core = overlays.xml(overlays.read(backup), 'economycore')
        for node in core.findall('defaults/*'):
            old = next((n for n in old_core.findall('defaults/*')
                        if n.tag == node.tag and n.get('name') == node.get('name')), None)
            node.tail = None
            if old is not None:
                old.tail = None
            after = ET.tostring(node, encoding='unicode').strip()
            before = None if old is None else ET.tostring(old, encoding='unicode').strip()
            if before != after:
                changes.append({'before': before, 'after': after})
    gameplay_patch = []
    gameplay_backup = mission / 'hollow-country-gameplay/cfggameplay.backup'
    if gameplay_backup.exists():
        before = json.loads(overlays.read(gameplay_backup))
        after = json.loads(clean['cfggameplay.json'])
        arr = after.get('WorldsData', {}).get('objectSpawnersArr') if isinstance(after, dict) else None
        if isinstance(arr, list):
            arr[:] = [p for p in arr if not (isinstance(p, str) and p.startswith(map_overlay.MANAGED + '/'))]

        def changed_leaves(old, new, path):
            if isinstance(new, dict):
                for key, value in new.items():
                    changed_leaves(old.get(key) if isinstance(old, dict) else None, value, path + [key])
            elif old != new:
                gameplay_patch.append({'path': path, 'before': old, 'after': new})

        changed_leaves(before, after, [])
    plan.append(('mission-patches.json', json.dumps({'schema': 1, 'core': changes, 'gameplay': gameplay_patch}, indent=2).encode()))
    if args.ce_coverage_result or (mission / ce_coverage.MANAGED).exists():
        print('left out CE building coverage: PENDING; rerun the native sampler against the friend stock mission')
    else:
        print('left out CE building coverage: PENDING (no native sampler result is shipped)')
    # Portable stdlib installers; no source addon, stock mission or dependency bytes.
    for name in BUNDLE_TOOLS:
        path = lts.ROOT / 'tools/package' / name
        plan.append(('tools/package/' + name, overlays.read(path)))
    config_root = lts.ROOT / MAP_OVERLAY_CONFIG
    try:
        config_files = sorted(p for p in config_root.rglob('*.json') if p.is_file())
        if not config_files:
            raise OSError('no layer files')
        for path in config_files:
            plan.append((path.relative_to(lts.ROOT).as_posix(), overlays.read(path)))
        map_overlay.load_source(config_root)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise Refused('map overlay layer set missing or invalid: %s' % error) from error
    for name in SETUP_TOOLS:
        plan.append(('tools/setup/' + name, overlays.read(lts.ROOT / 'tools/setup' / name)))
    for name in SETUP_BATS:
        plan.append((name, crlf(overlays.read(lts.ROOT / 'tools/setup' / name))))
    plan.append(('docs/COT_PERMISSIONS.md', overlays.read(lts.ROOT / 'docs/COT_PERMISSIONS.md')))
    for path in sorted(SOURCE.rglob('*')):
        if path.is_file():
            rel = path.relative_to(SOURCE).as_posix()
            if rel not in pbo.MISSION_FILES:
                raise Refused('unreviewed mission source: ' + rel)
            plan.append(('mission/hollow-country/' + rel, overlays.read(path)))
    p_keep, p_drop = profile_files(args.profiles)
    plan += [('profiles/' + rel, path) for rel, path in p_keep]
    mods = [(Path(args.mod), True)] + ([(Path(args.addon), False)] if args.addon else [])
    keys = {}
    for mod, need_key in mods:
        rows, mod_keys = mod_files(mod, need_key)
        plan += [('%s/%s' % (mod.name, rel), path) for rel, path in rows]
        for rel, path in mod_keys:
            keys.setdefault(PurePosixPath(rel).name, path)
    plan += [('keys/' + name, path) for name, path in sorted(keys.items())]
    cfg_text = Path(args.server_cfg).read_text(encoding='utf-8-sig')
    snippet, template = server_settings(cfg_text, mission.name)
    manifest = ws.load_manifest()
    groups = list(ws.GROUPS)
    items = ws.select(manifest, groups)
    if not args.addon:
        items = [i for i in items if i['folder'] != '@HollowCountryExpansionAI']
    plan += [('serverDZ-hollow-country.txt', snippet.encode()),
             ('start-server.bat', launcher(items).encode()),
             ('README.txt', readme(items, template, bool(args.addon)).encode())]
    plan = [(dest, data + overlays.friend_notes().encode() if dest == 'README.txt' else data)
            for dest, data in plan]
    seen = set()
    for dest, _ in plan:
        if dest.lower() in seen:
            raise Refused('two inputs map to %s' % dest)
        seen.add(dest.lower())

    stage = out.with_name(out.name + '.partial')
    if stage.exists():
        raise Refused('%s exists from an earlier run; remove it first' % stage)
    stage.mkdir(parents=True)
    try:
        rows = []
        for dest, source in plan:
            target = stage / dest
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(source, bytes):
                target.write_bytes(source)
            else:
                shutil.copyfile(source, target)
            rows.append({'path': dest, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
        data = {'schema': 1, 'mission': mission.name, 'files': sorted(rows, key=lambda r: r['path']),
                'excluded': {'mission': m_drop, 'profiles': p_drop}}
        (stage / 'bundle-manifest.json').write_text(json.dumps(data, indent=2) + '\n')
        os.replace(stage, out)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return len(plan), m_drop, p_drop


def main(argv=None):
    parser = argparse.ArgumentParser(prog='friend_bundle', description=__doc__.split('\n\n')[0])
    sub = parser.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build', help='write a new bundle folder')
    b.add_argument('--mission', required=True)
    b.add_argument('--profiles', required=True)
    b.add_argument('--ce-coverage-result', type=Path,
                   help='external validated sampler result; apply coverage to the local stock (coverage is not exported), or leave it out '
                   'with one PENDING line when no result exists')
    b.add_argument('--mod', required=True)
    b.add_argument('--addon')
    b.add_argument('--server-cfg', required=True)
    b.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    try:
        count, m_drop, p_drop = build(args)
    except (Refused, ws.SyncError, lts.Refused, ValueError, OSError, KeyError, TypeError) as exc:
        print('refused: %s' % lts.redact_home(exc), file=sys.stderr)
        return 2
    print('bundle written: %d files (left out %d mission and %d profile files that are state, logs or '
          'rollback data). Nothing here was observed in DayZ.' % (count, m_drop, p_drop))
    return 0


if __name__ == '__main__':
    sys.exit(main())
