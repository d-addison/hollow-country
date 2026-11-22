"""Export a self-contained Hollow Country server bundle for a friend's dedicated server.

HC-authored mission overlays, profile JSON and Expansion settings come exclusively from this
checkout's build commit or generators using its inputs. --mission supplies only stock vanilla
mission files which the overlay patches (cfgeconomycore.xml, cfggameplay.json, economy inputs);
installed HC deltas are rolled back on scratch copies to recover that baseline. --profiles is
inspected for excluded local data, never used as an authored configuration source. Neither
argument supplies release templates or operator edits. Output includes the signed --mod and
optional --addon, public keys, portable installers and server launch instructions.

--build-manifest PATH embeds the release BUILD_MANIFEST.json and requires its commit to match
HEAD and its PBO catalogue to exactly match --mod/--addon paths and SHA-256 hashes. The manifest
uses {"commit": "<full git sha>", "pbos": [{"path": "@Mod/addons/file.pbo", "sha256": "..."}]}.
A path-to-SHA256 object is also accepted for pbos. Omit this option only for legacy artifacts
without a release manifest; that build cannot establish PBO provenance.

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
import subprocess
import sys
import tempfile

from tools.package import ce_coverage, compat_addon
from tools.setup import local_test_session as lts
from tools.setup import workshop_sync as ws
from tools.setup.friend_install import normalize_profile, globals_upgrade_problem, globals_recovery
from tools.package import optional_overlays as overlays, travel, pbo
from tools.package import snafu_optional, tactical_flava_optional
from tools.package import economy, gameplay, loot_boost, map_overlay, hc_events
import xml.etree.ElementTree as ET

SOURCE = lts.ROOT / 'mission/hollow-country'
SETUP_TOOLS = ('friend_install.py', 'server_report.py', 'workshop_sync.py', 'workshop_mods.json')
SETUP_BATS = ('install-hollow-country.bat', 'server-report.bat')
BUNDLE_TOOLS = ('snafu_optional.py', 'tactical_flava_optional.py', 'snafu_allowlist.json',
                'tactical_flava_allowlist.json', 'firearms.py', 'hash_cache.py', 'xml_text.py', 'optional_overlays.py', 'rag_optional.py', 'travel.py', 'economy.py', 'ce_extensions.py', 'overlay_stack.py',
                'datamined_items.py', 'datamined_items.json', 'overlay_remove.py', 'loot_boost.py', 'new_buildings.py', 'loot_floor_policy.py', 'firearms_roster.json',
                'hc_events.py', 'map_overlay.py', 'infected_variety.py', 'HCWildlife_habitats.py',
                'military_loot.py', 'military_loot_allowlist.json', 'pbo.py', 'ce_coverage.py', 'interior_templates.py',
                'interior_catalog.py', 'search_context.py', 'essential_routes.json', 'interior_prop_boxes.json',
                'loot_reach_audit.py', 'interior_points_gen.py', 'loot_support_audit.py', 'ce_slot_pressure.py')
# Other repo files the shipped tools import or read at install time (wiring audit W010 bundle closure).
BUNDLE_EXTRA_FILES = ('tools/audit/interior_points.py', 'tools/setup/interior_sampler.py', 'tools/setup/ce_probe.py',
                      'tools/setup/diagnostic_mission.py', 'tools/setup/probe_runtime.py',
                      'tools/setup/probe_core.py', 'tools/release/host_lock.py',
                      'config/loot-dispositions.json', 'config/military-loot.json')
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
    'HollowCountry/Groups/settings.json',
    'HollowCountry/Infected/lod.json',
    'HollowCountry/settings.json',
    'HollowCountry/stamina.json',
    'HollowCountry/interiors-measured-profile.json',
    'HollowCountry/measured-interiors/**',
    'HollowCountry/templates/**',
    'HollowCountry/expansion-ai-sites.json',
    'HollowCountry/expansion-ai-localities.json',
    'HollowCountry/expansion-ai-formations.json',
    'HollowCountry/expansion-ai-tactics.json',
    'HollowCountry/Ecology/settings.json',
    'HollowCountry/Events/settings.json',
    'HollowCountry/Groups/settings.json',
    'HollowCountry/Groups/places.json',
    'HollowCountry/Infected/config.json',
    'HollowCountry/Infected/production-rooms.json',
    'HollowCountry/Infected/measured-rooms.json',
    'HollowCountry/camp-theft-config.json',
    'HollowCountry/base-raid-config.json',
    'HollowCountry/convoys.json',
    'HollowCountry/forage-config.json',
    'HollowCountry/vehicle-flip.json',
    'HollowCountry/wreck-salvage-config.json',
    'HollowCountry/fuel-siphon.json',
    'HollowCountry/signals.json',
    'HollowCountry/progression-config.json',
    'HollowCountry/radio.json',
    'HollowCountry/incidents.json',
    'HollowCountry/ai-incident-response.json',
    'HollowCountry/hearth-fires.json',
    'HollowCountry/role-activities.json',
    'HollowCountry/admin-teleport.json',
    'HollowCountry/atmosphere-presentation.json',
    'HollowCountry/building-claims-config.json',
    'HollowCountry/performance.json',
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
            if name.lower().endswith('.biprivatekey') or name.lower() == 'hits_privkey.txt':
                raise Refused('private signing key found: %s; never bundle it' % rel)
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


# The retired interiors.json pilot is never shipped; an installed copy is left alone and the server ignores it.


# No runtime state is deliberately carried between servers. Additions require an exact path
# and a comment explaining why carrying that state is safe; logs/receipts stay excluded.
RUNTIME_STATE_ALLOWLIST = ()


# These authored defaults mirror HCGroupSettings (3_Game/Groups/HCGroupData.c)
# and HCInfectedLODConfig (4_World/Infected/LOD/HCInfectedLODStore.c).
# No group state, herd journal or installed profile bytes enter this catalogue.
BASELINE_PROFILES = {
    'HollowCountry/Groups/settings.json': {
        'SchemaVersion': 2, 'Enabled': True, 'HCTeamPingEnabled': False,
        'WorldIcons': True, 'MapIcons': True, 'RequireGPS': False,
        'RequireLOS': False, 'RequireRadio': False, 'NavigationLayer': True,
        'DiscoveryLayer': True, 'MissionLayer': True, 'ShareDiscovery': True,
        'MaxLOSRaysPerTick': 56, 'MaxDiscoveries': 64, 'MaxExplorers': 256,
        'DiscoveryIntervalSeconds': 5.0, 'IconScale': 1.0, 'LabelScale': 1.0,
        'MaxGroups': 32, 'MaxMembers': 8, 'MaxMarkers': 64, 'MaxInvites': 64,
        'MaxRequestsPerSecond': 4, 'MaxStoreBytes': 262144, 'KeepRevisions': 8,
        'InviteSeconds': 120, 'MarkerRetentionSeconds': 604800,
        'PositionIntervalSeconds': 2.0, 'PositionStaleSeconds': 10.0,
        'MaxIconDistance': 1000.0,
    },
    'HollowCountry/Infected/lod.json': {
        'SchemaVersion': 3, 'EnableLOD': True, 'EnableVirtualHerds': True,
        'FullRange': 300, 'IdleRange': 1000, 'MinSpawnDistance': 120,
        'MaterializeRange': 900, 'FoldRange': 1000, 'VisibilityRange': 1500,
        'ClassifyPerTick': 12, 'MaxMaterialized': 12, 'MaxPerHerd': 6,
        'MaxObservers': 6, 'RegrowSeconds': 1800, 'PosedBudget': 12,
        'PosedFullBudget': 12, 'PosedIdleBudget': 12,
        'VarietyNonCalmHoldSeconds': 600, 'HerdWorld': 'chernarusplus',
        'MemberTypes': [],
        'Herds': [dict(Id=name, X=x, Z=z, Radius=60, HeadCount=12) for name, x, z in (
            ('bor-farm', 3100.955811, 4238.387207),
            ('sosnovka-woods', 3560.896484, 7004.783203),
            ('pulkovo-fields', 5271.449219, 5515.677246),
            ('dolina-ridge', 9710.349609, 6487.099121),
            ('polana-farm', 10677.808594, 7923.848633),
            ('sinystok-woods', 1987.282837, 12965.870117),
            ('kamensk-woods', 7428.081543, 12732.728516),
            ('northeast-woods', 12818.673828, 13117.182617))
        ],
    },
}


def profile_bytes(source):
    return normalize_profile(source if isinstance(source, bytes) else source.read_bytes())


def repo_profile_sources():
    """Complete release profile catalogue; installed profile presence never selects defaults."""
    sources = {
        'HollowCountry/settings.json': lts.ROOT / 'config/hollow-country-settings.json',
        'HollowCountry/stamina.json': lts.ROOT / 'config/hollow-country-stamina.json',
        'HollowCountry/expansion-ai-sites.json': SOURCE / 'ai/sites.json',
        # Runtime AI localities come from the addon default, which is kept byte-identical to the
        # mission's 523-row HC-18 catalogue (all 528 sites). Story sites live in events/story-sites.json.
        'ExpansionMod/Settings/AISettings.json': SOURCE / 'ai/AISettings.merge.json',
    }
    defaults = lts.ROOT / 'mods/HollowCountryExpansionAI/data/defaults'
    for name in ('localities', 'formations', 'tactics'):
        rel = 'expansion-ai-' + name + '.json'
        sources['HollowCountry/' + rel] = defaults / rel
    for path in sorted((SOURCE / 'ai/loadouts').glob('HollowCountry_*.json')):
        sources['ExpansionMod/Loadouts/' + path.name] = path
    for path in sorted((SOURCE / 'interiors/templates').rglob('*.json')):
        sources['HollowCountry/templates/' + path.relative_to(SOURCE / 'interiors/templates').as_posix()] = path
    sources.update({rel: (json.dumps(data, indent=4) + '\n').encode('utf-8')
                    for rel, data in BASELINE_PROFILES.items()})
    return sources


def profile_files(profiles):
    sources = repo_profile_sources()
    installed = _walk(profiles)  # Preserve the symlink/private-key refusal without inheriting bytes.
    keep = sorted(sources.items())
    for rel, path in installed:
        if rel in RUNTIME_STATE_ALLOWLIST:
            if _profile_allowed(rel):
                raise Refused('runtime state conflicts with authored profile: ' + rel)
            keep.append((rel, path))
    dropped = sum(rel not in sources and rel not in RUNTIME_STATE_ALLOWLIST for rel, _ in installed)
    return keep, dropped


# Exact authored source paths, never a basename search through unrelated JSON.
# Generated/measured profile images have no checked-in byte history: their earlier
# installed hashes can only be recognized from the destination install receipt.
PROFILE_SOURCES = {
    'HollowCountry/settings.json': ('config/hollow-country-settings.json',),
    'HollowCountry/stamina.json': ('config/hollow-country-stamina.json',),
    'HollowCountry/expansion-ai-sites.json': (
        'mission/hollow-country/ai/sites.json',
        'mods/HollowCountryExpansionAI/data/defaults/expansion-ai-sites.json'),
    'HollowCountry/expansion-ai-localities.json': (
        'mods/HollowCountryExpansionAI/data/defaults/expansion-ai-localities.json',
        'mission/hollow-country/ai/localities.json'),
    'HollowCountry/expansion-ai-tactics.json': (
        'mods/HollowCountryExpansionAI/data/defaults/expansion-ai-tactics.json',),
}


def profile_history(source):
    """Hash every authored revision, following renames. Git metadata is read-only.

    Fail closed if tracked history is unavailable rather than silently issuing an
    incomplete upgrade catalogue: a shallow clone (missing older revisions), a missing
    git binary and a failing git call all raise Refused. Never include git stderr
    (paths/identities).
    """
    def git(*args):
        try:
            result = subprocess.run(['git', *args], cwd=lts.ROOT, capture_output=True, check=False)
        except OSError:
            raise Refused('profile_history_unavailable: git binary not found or not runnable; '
                          'install git or build from a full clone (' + source + ')') from None
        if result.returncode:
            raise Refused('profile_history_unavailable: cannot read tracked default history for ' + source)
        return result.stdout

    if git('rev-parse', '--is-shallow-repository').strip() == b'true':
        raise Refused('profile_history_unavailable: shallow clone has no full default history; '
                      'run git fetch --unshallow (' + source + ')')
    history = git('log', '--follow', '--diff-filter=AMR', '--format=%H', '--name-only', 'HEAD', '--', source)
    revision = None
    hashes = set()
    for line in history.decode('utf-8').splitlines():
        if re.fullmatch(r'[0-9a-f]{40,64}', line):
            revision = line
        elif line and revision:
            hashes.add(hashlib.sha256(normalize_profile(git('show', revision + ':' + line))).hexdigest())
    if not hashes:
        raise Refused('profile_history_unavailable: no tracked revisions for ' + source)
    return hashes


def _source_match(rel, data, sources):
    """Compare authored text after transport-only BOM/CRLF normalization."""
    current = next((profile_bytes(lts.ROOT / source) for source in sources
                    if (lts.ROOT / source).is_file()), None)
    if current is None:
        return 'none'
    if current == normalize_profile(data):
        return 'exact'
    return 'content'


def profile_defaults(rows):
    """Current bundle bytes plus known earlier authored defaults, per shipped file."""
    defaults = {}
    source_map = repo_profile_sources()
    for rel, path in rows:
        source = source_map.get(rel)
        sources = PROFILE_SOURCES.get(rel, (source.relative_to(lts.ROOT).as_posix(),)
                                      if isinstance(source, Path) else ())
        if rel.startswith('ExpansionMod/Loadouts/HollowCountry_'):
            name = PurePosixPath(rel).name
            candidates = ('mods/HollowCountryExpansionAI/data/defaults/loadouts/' + name,
                          'mission/hollow-country/ai/loadouts/' + name)
            sources = tuple(source for source in candidates if (lts.ROOT / source).is_file())
        data = profile_bytes(path)
        current = hashlib.sha256(data).hexdigest()
        hashes = {current}
        match = _source_match(rel, data, sources) if sources else 'none'
        for source in sources:
            hashes.update(profile_history(source))
        history = 'receipt-only'
        if sources:
            history = 'git-log'
            if match == 'content':
                history = 'git-log-best-effort'
                print('profile history for %s is best-effort: shipped bytes differ from repo source %s'
                      % (rel, sources[0]))
        defaults['profiles/' + rel] = {
            'sha256': current, 'shipped_sha256': sorted(hashes),
            'history': history, 'sources': list(sources)}
    return defaults


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
             'rem start-server.bat /min starts the server minimized without taking focus.',
             'set "HC_WINDOW="',
             'if /i "%~1"=="/min" set "HC_WINDOW=/min"',
             'start "" %%HC_WINDOW%% DayZServer_x64.exe -config=serverDZ.cfg -profiles=profiles -port=2302 %s '
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
        '  Ambient Animals Pack is a default subscription. Survivor Animations and DayZ-Bicycle are retired; an existing subscription is harmless and is not loaded.',
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
        'Stopped-server overlay removal (run from this bundle folder; keep a backup):',
        '  python3 -B -m tools.package.overlay_remove --mission /path/to/private-mission --overlays loot vehicles --dry-run',
        '  python3 -B -m tools.package.overlay_remove --mission /path/to/private-mission --overlays loot vehicles --server-stopped',
        '  Stop the server first. Loot rollback runs before vehicle rollback, with a scratch rehearsal.',
        '  Removal is resumable, not atomic across installers; drift refuses and retains recovery data.',
        '  Inventory overrides require a reviewed addon rebuild and redistribution; mission rollback cannot remove them.',
        '  Omitting --overlays requests inventory too and refuses. Runtime acceptance remains pending.',
        '',
        'bundle-manifest.json lists the SHA-256 of every file in this bundle.',
        'Its profile_defaults catalogue includes current bytes and earlier authored defaults from git log.',
        'All authored profiles come from the build checkout; installed operator edits are never exported.',
        'Profiles without tracked JSON history are marked receipt-only; older installed',
        'bytes are recognized from the server installer receipt. Unknown bytes are always kept with a WARN.',
        'To adopt one kept default with a backup: install-hollow-country.bat --apply --adopt-profile "profiles/<file>"',
        '',
    ]
    return '\r\n'.join(lines)


def fresh_economy(mission, scratch_root=None):
    """Regenerate the release delta on a rolled-back scratch mission, never the source."""
    try:
        profile = json.loads(overlays.read(SOURCE / 'economy-profiles/contextual-pilot.json'))
        roster = json.loads(overlays.read(lts.ROOT / lts.FIREARMS_ROSTER))
        with tempfile.TemporaryDirectory(prefix='hc-bundle-economy-', dir=scratch_root) as directory:
            scratch = Path(directory) / 'mission'
            shutil.copytree(mission, scratch, ignore=shutil.ignore_patterns('storage_*'))
            # Reverse the local CE stack. Each existing installer validates its
            # receipts/backups; missing or drifted evidence refuses the export.
            for writer in (hc_events, map_overlay, loot_boost, overlays, ce_coverage, travel,
                           tactical_flava_optional, snafu_optional, economy, gameplay):
                if (scratch / writer.MANAGED).exists():
                    writer.rollback(scratch)
            baseline = overlays.read(scratch / 'cfgeconomycore.xml')
            if any(node.get('folder', '').lower().startswith('hollow-country')
                   for node in overlays.xml(baseline, 'economycore').findall('ce')):
                raise Refused('recovered vanilla core still registers an HC overlay; no repo provenance')
            files = economy.generate(scratch, profile, include_datamined=True, roster=roster,
                                     include_roster_datamined=True,
                                     authored_types=overlays.read(SOURCE / 'ce/types.xml'))
            delta = Path(directory) / 'delta'
            economy.write_delta(delta, files)
            return ({name: overlays.read(delta / name) for name in files}, baseline,
                    overlays.read(scratch / 'cfggameplay.json'))
    except (OSError, ValueError, KeyError, TypeError) as error:
        recovery = '\n' + '\n'.join(globals_recovery(Path(mission))) if globals_upgrade_problem(Path(mission)) else ''
        raise Refused('HC-22 economy regeneration failed: %s%s' % (error, recovery)) from error


def repo_revision():
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=lts.ROOT, capture_output=True)
    if result.returncode:
        raise Refused('build commit unavailable')
    return result.stdout.decode().strip()


def check_repo_inputs():
    """Data and generator bytes must be tracked and unchanged at the build commit.

    The dispatcher may edit this bundle tool without changing release data. Do not require
    a clean worktree globally: other workers own unrelated files in this audit.
    """
    roots = ['mission/hollow-country', 'config', 'tools/package',
             'mods/HollowCountryExpansionAI/data/defaults']
    git_env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
    result = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', *roots], cwd=lts.ROOT,
                            capture_output=True, env=git_env)
    if result.returncode:
        raise Refused('repo data or generators differ from build commit; build from committed inputs')
    inputs = [path.relative_to(lts.ROOT).as_posix() for root in roots
              for path in (lts.ROOT / root).rglob('*')
              if path.is_file() and path.suffix in ('.json', '.xml', '.py', '.md')]
    result = subprocess.run(['git', 'ls-files', '--error-unmatch', '--', *inputs], cwd=lts.ROOT,
                            capture_output=True, env=git_env)
    if result.returncode:
        raise Refused('untracked repo data or generators cannot be bundled')


def validate_build_manifest(path, plan):
    """Read public build metadata only; exact PBO set comparison fails closed."""
    raw = overlays.read(Path(path))
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or manifest.get('commit') != repo_revision():
        raise Refused('BUILD_MANIFEST commit differs from this checkout build commit')
    pbos = manifest.get('pbos')
    if isinstance(pbos, dict):
        pbos = [{'path': name, 'sha256': digest} for name, digest in pbos.items()]
    if not isinstance(pbos, list) or not pbos:
        raise Refused('BUILD_MANIFEST needs a nonempty pbos path/sha256 catalogue')
    expected = {}
    for row in pbos:
        name = row.get('path') if isinstance(row, dict) else None
        digest = row.get('sha256') if isinstance(row, dict) else None
        if (not isinstance(name, str) or not name.endswith('.pbo') or name in expected
                or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)):
            raise Refused('BUILD_MANIFEST has an invalid or duplicate PBO entry')
        expected[name] = digest
    actual = {dest: hashlib.sha256(source if isinstance(source, bytes) else overlays.read(source)).hexdigest()
              for dest, source in plan if dest.lower().endswith('.pbo')}
    if actual != expected:
        bad = sorted(name for name in actual.keys() | expected.keys() if actual.get(name) != expected.get(name))
        raise Refused('BUILD_MANIFEST PBO paths/hashes differ: ' + ', '.join(bad))
    return raw


def mission_images(economy_files):
    images = {'hollow-country/' + path.relative_to(SOURCE).as_posix(): overlays.read(path)
              for path in sorted(SOURCE.rglob('*.json'))}
    images['hollow-country/ecology/events.append.xml'] = overlays.read(SOURCE / 'ecology/events.append.xml')
    images[lts.AI_PATROL_TARGET] = overlays.read(lts.ROOT / lts.AI_PATROL_OVERRIDE)
    images[gameplay.GEAR_PATH] = gameplay.encode(gameplay.parse(overlays.read(lts.ROOT / lts.GAMEPLAY_PRESET)))
    images.update({'hollow-country/' + rel: data for rel, data in economy_files.items()
                   if rel not in ('delta-manifest.json', 'economy-report.json')})
    return images


def freshness_report(stage, mission):
    """Compare staged bytes and complete path sets against repo or regenerated images."""
    expected = {}
    expected.update({'mission/' + path.relative_to(lts.ROOT / 'mission').as_posix(): overlays.read(path)
                     for path in SOURCE.rglob('*') if path.is_file()})
    expected.update({'profiles/' + rel: profile_bytes(path) for rel, path in repo_profile_sources().items()})
    regenerated, baseline, vanilla_gameplay = fresh_economy(mission, stage.parent)
    expected.update({'mission-overlay/' + rel: data for rel, data in mission_images(regenerated).items()})
    expected['mission-patches.json'] = mission_patches(regenerated, baseline, vanilla_gameplay, stage.parent)
    expected.update({path.relative_to(lts.ROOT).as_posix(): overlays.read(path)
                     for path in (lts.ROOT / MAP_OVERLAY_CONFIG).rglob('*.json')})
    expected.update({rel: overlays.read(lts.ROOT / rel) for rel in BUNDLE_EXTRA_FILES if rel.startswith('config/')})
    actual = {path.relative_to(stage).as_posix() for root in ('mission', 'mission-overlay', 'profiles', 'config')
              for path in (stage / root).rglob('*') if path.is_file()}
    actual.add('mission-patches.json')
    if actual != expected.keys():
        raise Refused('freshness file catalogue mismatch: ' + ', '.join(sorted(actual ^ expected.keys())))
    families = {}
    for rel, data in sorted(expected.items()):
        if hashlib.sha256(overlays.read(stage / rel)).digest() != hashlib.sha256(data).digest():
            raise Refused('freshness SHA-256 mismatch: ' + rel)
        parts = PurePosixPath(rel).parts
        family = '/'.join(parts[:3]) if len(parts) > 3 else '/'.join(parts[:-1]) or 'patches'
        counts = families.setdefault(family, {'files': 0})
        counts['files'] += 1
        if '/templates/t-' in rel:
            counts['templates'] = counts.get('templates', 0) + 1
        if rel.endswith('.json'):
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                for key in ('Sites', 'Localities', 'Templates'):
                    if isinstance(parsed.get(key), list):
                        counts[key.lower()] = counts.get(key.lower(), 0) + len(parsed[key])
        if rel.endswith('/ce/types.xml'):
            counts['types'] = len(ET.fromstring(data).findall('type'))
    for family, counts in sorted(families.items()):
        print('freshness %s: %s sha256=match' %
              (family, ' '.join('%s=%d' % item for item in counts.items())))


def mission_patches(economy_files, economy_core, baseline, scratch_root=None):
    """Repo policy applied to recovered vanilla inputs, with no installed HC policy."""
    # Build the HC core patch from fresh generation, never installed HC registrations.
    core = overlays.xml(economy_core, 'economycore')
    core.extend(overlays.xml(economy_files['cfgeconomycore.append.xml'], 'economycore'))
    core_defaults = {n.get('name'): n for n in core.findall('defaults/default')}
    for name, patch in json.loads(economy_files['core-defaults.patch.json']).items():
        if name not in core_defaults:
            raise Refused('HC-22 economy default missing in export core: ' + name)
        core_defaults[name].set('value', patch['after'])
    changes = []
    for node in core.findall('ce'):
        folder = node.get('folder', '')
        if folder.startswith('hollow-country') and not folder.startswith((travel.MANAGED, overlays.MANAGED, ce_coverage.MANAGED,
                                                                                   snafu_optional.MANAGED, tactical_flava_optional.MANAGED)):
            node.tail = None
            changes.append({'before': None, 'after': ET.tostring(node, encoding='unicode').strip()})
    if economy_core:
        old_core = overlays.xml(economy_core, 'economycore')
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
    # Recover stock gameplay on scratch, then derive every owned leaf from repo policy.
    with tempfile.TemporaryDirectory(prefix='hc-bundle-gameplay-', dir=scratch_root) as directory:
        scratch = Path(directory)
        (scratch / 'cfggameplay.json').write_bytes(baseline)
        generated = gameplay.generate(scratch, gameplay.parse(overlays.read(lts.ROOT / lts.GAMEPLAY_PROFILE)),
                                      gameplay.parse(overlays.read(lts.ROOT / lts.GAMEPLAY_PRESET)))
    before = gameplay.parse(baseline)
    after = gameplay.parse(generated['cfggameplay.merged.json'])
    gameplay_patch = []

    def changed_leaves(old, new, path):
        if isinstance(new, dict):
            for key, value in new.items():
                changed_leaves(old.get(key) if isinstance(old, dict) else None, value, path + [key])
        elif old != new:
            gameplay_patch.append({'path': path, 'before': old, 'after': new})

    changed_leaves(before, after, [])
    return json.dumps({'schema': 1, 'core': changes, 'gameplay': gameplay_patch}, indent=2).encode()


def build(args):
    out = Path(args.out)
    if out.exists() or out.is_symlink():
        raise Refused('output %s already exists; choose a new folder' % out)
    check_repo_inputs()
    out.parent.mkdir(parents=True, exist_ok=True)
    mission = Path(args.mission)
    plan = []  # (destination relative path, source path or bytes)
    try:
        travel.validate(SOURCE)
        hc_events.validate(SOURCE)
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
        for rel in BUNDLE_EXTRA_FILES:
            overlays.read(lts.ROOT / rel)
    except (OSError, ValueError) as error:
        raise Refused('optional overlay source missing or invalid: %s' % error) from error
    m_keep, m_drop = mission_files(mission)
    # Installed HC files are never candidates for copying. Even unknown authored files in
    # the snapshot cannot leak through: this catalogue is built wholly from repo inputs.
    economy_files, economy_core, vanilla_gameplay = fresh_economy(mission, out.parent)
    authored = mission_images(economy_files)
    plan += [('mission-overlay/' + rel, data) for rel, data in sorted(authored.items())]
    m_drop += len(m_keep) - len(authored.keys() & {rel for rel, _ in m_keep})
    plan.append(('mission-patches.json', mission_patches(economy_files, economy_core, vanilla_gameplay, out.parent)))
    if args.ce_coverage_result or (mission / ce_coverage.MANAGED).exists():
        print('left out CE building coverage: PENDING; rerun the native sampler against the friend stock mission')
    else:
        print('left out CE building coverage: PENDING (no native sampler result is shipped)')
    # Portable stdlib installers; no source addon, stock mission or dependency bytes.
    for name in BUNDLE_TOOLS:
        path = lts.ROOT / 'tools/package' / name
        plan.append(('tools/package/' + name, overlays.read(path)))
    plan.append(('tools/audit/pbo_config.py', overlays.read(lts.ROOT / 'tools/audit/pbo_config.py')))
    for rel in BUNDLE_EXTRA_FILES:
        plan.append((rel, overlays.read(lts.ROOT / rel)))
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
    defaults = profile_defaults(p_keep)
    plan += [('profiles/' + rel, profile_bytes(path)) for rel, path in p_keep]
    mods = [(Path(args.mod), True)] + ([(Path(args.addon), False)] if args.addon else [])
    keys = {}
    for mod, need_key in mods:
        rows, mod_keys = mod_files(mod, need_key)
        plan += [('%s/%s' % (mod.name, rel), path) for rel, path in rows]
        for rel, path in mod_keys:
            keys.setdefault(PurePosixPath(rel).name, path)
    plan += [('keys/' + name, path) for name, path in sorted(keys.items())]
    if getattr(args, 'build_manifest', None):
        release = validate_build_manifest(args.build_manifest, plan)
        # Signed compatibility addons travel in the ordinary HCX file plan. Keep
        # the release receipt tied to those exact bytes without rebuilding here.
        guard = json.loads(release).get('weapon_pack_guards')
        if guard is not None:
            if not isinstance(guard, dict):
                raise Refused('invalid weapon-pack guard receipt')
            guard_path = '@HollowCountryExpansionAI/addons/hollowcountry_weapon_pack_guards.pbo'
            guard_files = [source for dest, source in plan if dest == guard_path]
            if (guard.get('status') not in ('generated', 'absent')
                    or bool(guard_files) != (guard.get('status') == 'generated')):
                raise Refused('weapon-pack guard receipt differs from addon plan')
            if guard_files and hashlib.sha256(overlays.read(guard_files[0])).hexdigest() != guard.get('sha256'):
                raise Refused('weapon-pack guard receipt hash differs from addon plan')
        compat = json.loads(release).get('compat_addon')
        if compat is not None:
            # The compat PBO(s) are built at bundle time; the receipt must match the addon plan.
            present = {dest: hashlib.sha256(source if isinstance(source, bytes) else overlays.read(source)).hexdigest()
                       for dest, source in plan if dest.lower().endswith('.pbo')}
            if compat_addon.check_receipt(compat, present):
                raise Refused('compat addon receipt differs from addon plan')
        plan.append(('BUILD_MANIFEST.json', release))
    else:
        print('build manifest: legacy input; PBO build provenance unverified')
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
        freshness_report(stage, mission)
        check_repo_inputs()
        if getattr(args, 'build_manifest', None):
            staged = [(dest, stage / dest) for dest, _ in plan]
            if validate_build_manifest(stage / 'BUILD_MANIFEST.json', staged) != release:
                raise Refused('BUILD_MANIFEST changed during staging')
        data = {'schema': 1, 'mission': mission.name, 'files': sorted(rows, key=lambda r: r['path']),
                'profile_defaults': defaults,
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
    b.add_argument('--build-manifest', type=Path, help='release BUILD_MANIFEST.json; verify commit and every selected PBO hash')
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
