"""Soak campaign orchestrator: stage a local test profile, run the scripted client, idle, audit, restore.

  python3 -B -m tools.testing.soak_campaign plan      # default: phases, counter map, what would be staged; writes nothing
  python3 -B -m tools.testing.soak_campaign stage     # build the test addon and stage the test profile (reversible)
  python3 -B -m tools.testing.soak_campaign run --yes # LEAD ONLY: stage, boot, drive, idle >= 125 min, audit, stop, restore
  python3 -B -m tools.testing.soak_campaign restore   # put every staged byte back; a no-op when nothing is staged
  python3 -B -m tools.testing.soak_campaign report    # works/broken table of the last run

Targeted runs (plan and run): --changed <git ref> maps the changed mods/**/*.c files to their counters through
the reach map's code: tokens; --modules A,B and --only-phases a,b select directly. Only the phases those counters
need (plus join, and every earlier phase that holds one of their steps or fixtures) are driven, and the idle lasts
max(10, the longest selected timer) minutes. A targeted run is never release evidence: its report says so and
marks the counters of phases it did not drive "not run". The full campaign stays the release-candidate run.

The campaign uses the dev-only test addon (mods/HollowCountryTest, never shipped) on the local server and the
owner's local client. Everything it adds is a COPY or a new file: the server runs from a copy of the profile
folders, a test copy of serverDZ.cfg and its own start file; only the mission's cfggameplay.json is edited in
place, with a byte backup in the receipt. BattlEye, signature checks and Steam are never bypassed. Counters are
never bumped by test code. Two-player and subjective items stay "owner check" / "friend playtest" rows.
Only the graceful CloseMainWindow path stops the server and the client. Nothing here prints a home path, a
Windows user folder, an id, a name or a config value.
"""
import argparse
import base64
import contextlib
import errno
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import sys
import time

from tools.release.host_lock import LockRefused
from tools.setup.winproc import InteropError

ROOT = Path(__file__).resolve().parents[2]
PHASES_FILE = Path(__file__).with_name('soak_phases.json')
EXPECTATIONS = ROOT / 'config/activity-expectations.json'
STATE = Path.home() / '.cache/hollow-country/soak-campaign'
PHASE_ORDER = ('join', 'group', 'walk_ai', 'walk_zone', 'walk_town', 'fixtures', 'actions', 'scene', 'forest', 'mission',
               'idle')
# Test-profile settings the staging writes (the shipped defaults stay untouched): the smoke fixtures, and a
# short Fortify breach window so one scripted barricade can be breached inside the run.
SOAK_SETTINGS = {'EnableSmokeFixtures': True, 'FortifyBreachSeconds': 20}
RESULTS = ('active', 'zero', 'owner check', 'friend playtest', 'not run')
MANUAL_KINDS = {'owner_check': 'owner check', 'friend_playtest': 'friend playtest'}
# Only the two-player and subjective items of the shared contract may be a manual row.
ALLOWED_MANUAL = frozenset({'TeamPing/ping_recipients', 'TeamPing/ping_delivered', 'Cellars/visual_applied'})
ALLOWED_LOOKS = {'lighting_look': 'owner_check', 'grade_look': 'owner_check', 'audio': 'owner_check',
                 'group_sharing': 'friend_playtest', 'team_ping_delivery': 'friend_playtest'}
# GetName() of a base class that no feature reports under.
SOURCE_IGNORED_MODULES = frozenset({'unnamed'})
TEST_MOD = '@HollowCountryTest'
SERVER_IMAGE = 'DayZServer_x64.exe'
CLIENT_IMAGE = 'DayZ_x64.exe'
LAUNCHER_IMAGE = 'DayZ_BE.exe'
PROCESS_IMAGES = (LAUNCHER_IMAGE, CLIENT_IMAGE, SERVER_IMAGE)
SERVER_ROOT_DEFAULT = 'E:\\HollowCountryLocal\\friend-local-1'
OWN_MODS = ('@HollowCountry', '@HollowCountryExpansionAI', TEST_MOD)
INSTANCE_ID = '99'
SOAK_TIME = '2026/07/15/08/00'  # forage season (June to November), daytime; run at 1x so it stays daytime
CFG_EDITS = (('instanceId', INSTANCE_ID), ('serverTime', '"' + SOAK_TIME + '"'),
             ('serverTimeAcceleration', '1'), ('serverTimePersistent', '0'))
GAMEPLAY = 'cfggameplay.json'
GEAR_REL = 'hollow-country-gameplay/gear/soak-test.json'
PROFILE_COPY = 'soak-profiles'
CFG_COPY = 'hc-soak.cfg'
BAT_COPY = 'start-server-soak.bat'
CLIENT_PROFILE = 'soak-client-profile'
STEP_REL = 'HollowCountry/acceptance/client_driver.json'
CELLAR_MARKER_REL = 'HollowCountry/measure-cellars'
# Receipt rows are only ever removed or restored for these names; a tampered receipt is refused.
CREATED_ALLOWED = {('server', PROFILE_COPY), ('server', TEST_MOD), ('server', CFG_COPY), ('server', BAT_COPY),
                   ('client', CLIENT_PROFILE), ('mission', GEAR_REL), ('mission', 'storage_' + INSTANCE_ID),
                   ('mission', 'storage_0')}
# The 2026-11-23 test boot (instance 99) also left an empty storage_0/communityframework folder; it is
# recorded (and removed by restore) only when it did not exist before staging.
STRAY_STORAGE = 'storage_0'
# A graceful stop saves the world first: the build 178 test server needed about 80 s after CloseMainWindow.
STOP_WAIT_SECONDS = 240
STOP_POLL_SECONDS = 5
LAUNCH_ATTEMPTS = 3
LAUNCH_TIMEOUT_SECONDS = 60
LAUNCH_SETTLE_SECONDS = 30
LAUNCH_POLL_SECONDS = 5
# Consecutive unreadable polls of a live log (Windows may hold it briefly) before the run gives up.
UNREADABLE_POLLS = 20
# The BattlEye launcher starts DayZ_x64 seconds after Start-Process returns (soak 178 attempt 5).
PROCESS_APPEAR_SECONDS = 180
APPEAR_POLL_SECONDS = 5
EDITED_ALLOWED = {('mission', GAMEPLAY)}
CONNECT_ENABLED = 'Player connect enabled'
# A script error before connect enabled means the soak can only fail; the shipped gate never compiles the test
# addon, so its compile errors first show here (2026-11-23 soak 178: Unknown operator '%' in the test addon,
# then an access violation). Stop at the first one and name it.
SCRIPT_ERROR = 'SCRIPT    (E)'
POLL_SECONDS = 30
SERVER_READY_MINUTES = 20
JOIN_MINUTES = 10
# Both peers must prove a join within six minutes of the BattlEye launch, including startup.
CLIENT_JOIN_SECONDS = 6 * 60
# CREATED -> CONNECTED precedes authentication and is also emitted for rejected clients. A joined
# client ends at "MISSION RECEIVED -> GAME LOADED" (soak 185b, 2026-11-24); "SELECTED -> PLAYER
# ASSIGNED" is the server's own __SERVER__ identity and never a client.
SERVER_PLAYER_CONNECTED = re.compile(
    r"Server: SetClientState dpid=\d+ id=\S+ name=(?!__SERVER__ )\S.* -> GAME LOADED\s*$")
# Only our fixed, non-identifying trace grammar may appear in a refusal.
CONNECT_TRACE = re.compile(
    r"\[HC Driver\] connect (?:initializ(?:e load=-?\d+ game=-?\d+ cli=(?:0|1|true|false)"
    r"|ed load=-?\d+ game=-?\d+)|entry load=-?\d+ game=-?\d+|returned load=-?\d+ game=-?\d+"
    r"|session (?:start|fail|end))\s*$")
# A targeted run idles this long unless a selected counter waits on a longer timer.
TARGETED_IDLE_MINUTES = 10
SELECTION_FILE = 'selection.json'


class Refused(ValueError):
    """The campaign cannot go on; the message names no private path or id."""


# ------------------------------------------------------------------ phase map

def norm(feature):
    return feature.replace('-', '_')


def load_phases(path=PHASES_FILE):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema_version') != 1:
        raise Refused('soak_phases.json schema_version must be 1')
    names = tuple(p['name'] for p in data['phases'])
    if names != PHASE_ORDER:
        raise Refused('soak_phases.json phases must be exactly ' + ','.join(PHASE_ORDER))
    if data['min_idle_minutes'] < 125:
        raise Refused('min_idle_minutes must be at least 125')
    for key in ('modules', 'features'):
        for name, phase in data[key].items():
            if phase not in PHASE_ORDER:
                raise Refused('unknown phase %r for %s' % (phase, name))
    return data


def expectation_rows(path=EXPECTATIONS):
    rows = json.loads(Path(path).read_text(encoding='utf-8'))['features']
    return [(r['module'], r['feature']) for r in rows]


def scan_source(root=ROOT):
    """(module, feature) literals and GetName() modules of the shipped Enforce sources.

    The release registry is built at runtime; this offline scan is a guard that a new module or a new literal
    counter cannot appear without a phase (it is not evidence about DayZ)."""
    from tools.package.gen_modules import strip_comments
    pair = re.compile(r'HC(?:RegisterUse|Use|UseGuarded|UseFixture)\(\s*"([^"]+)"\s*,\s*"([^"]+)"')
    name = re.compile(r'GetName\(\)\s*\{\s*return\s+"([^"]+)"')
    pairs, modules = set(), set()
    for path in sorted((Path(root) / 'mods').rglob('*.c')):
        if 'HollowCountryTest' in path.parts:
            continue
        text = strip_comments(path.read_text(encoding='utf-8', errors='replace'))
        pairs.update(pair.findall(text))
        modules.update(m for m in name.findall(text) if m not in SOURCE_IGNORED_MODULES)
    return pairs, modules


def counter_universe(root=ROOT):
    """Every counter the campaign must map: kind 'expect' (activity-expectations rows), 'use' (release registry)."""
    universe = {('expect', m, f) for m, f in expectation_rows(Path(root) / 'config/activity-expectations.json')}
    pairs, modules = scan_source(root)
    universe |= {('use', m, f) for m, f in pairs}
    return universe, modules


def phase_of(phases, module, feature):
    """('phase', name) | ('owner check'|'friend playtest', reason) | None for an unmapped counter."""
    key = module + '/' + norm(feature)
    manual = phases.get('manual', {}).get(key)
    if manual:
        return MANUAL_KINDS[manual['kind']], manual['reason']
    if key in phases['features']:
        return 'phase', phases['features'][key]
    if module in phases['modules']:
        return 'phase', phases['modules'][module]
    return None


def unmapped(phases, root=ROOT):
    universe, modules = counter_universe(root)
    missing = sorted('%s %s/%s' % row for row in universe if phase_of(phases, row[1], row[2]) is None)
    missing += sorted('module %s' % m for m in modules if m not in phases['modules'])
    return missing


def manual_problems(phases):
    """Rows the contract does not allow as owner check / friend playtest, or without a reason."""
    problems = []
    for key, row in sorted(phases.get('manual', {}).items()):
        if key not in ALLOWED_MANUAL:
            problems.append('manual row not allowed: ' + key)
        if row.get('kind') not in MANUAL_KINDS or not str(row.get('reason', '')).strip():
            problems.append('manual row needs kind and reason: ' + key)
    for look in phases.get('looks', []):
        if ALLOWED_LOOKS.get(look.get('id')) != look.get('kind') or not str(look.get('reason', '')).strip():
            problems.append('look row not allowed: ' + str(look.get('id')))
    return problems


# ------------------------------------------------------------------ reach map

REACH_CLASSES = ('required', 'diagnostic')
_TOKEN_NAME = re.compile(r'[A-Za-z0-9_.\-]+\Z')


def counter_keys(root=ROOT):
    """Every counter key (module/normalised feature) the campaign maps, kind-free."""
    universe, _ = counter_universe(root)
    return sorted({m + '/' + norm(f) for _, m, f in universe})


def _source_names(root):
    names = set()
    for path in (Path(root) / 'mods').rglob('*.c'):
        if 'HollowCountryTest' not in path.parts:
            names.add(path.name)
    return names


def _quoted_commands(root):
    """Quoted fx_ command words found in any Enforce source (shipped catalog rows and the test addon)."""
    found = set()
    word = re.compile(r'"(fx_[a-z0-9_]+)"')
    for path in (Path(root) / 'mods').rglob('*.c'):
        found.update(word.findall(path.read_text(encoding='utf-8', errors='replace')))
    return found


def reach_context(root=ROOT):
    return {'index': _step_index(), 'sources': _source_names(root),
            'commands': _quoted_commands(root)}


def reach_token_problem(token, phase, phases, context):
    """None when the token names something real that exists by `phase`, else the reason."""
    kind, _, value = token.partition(':')
    if not value and kind != 'boot':
        return 'token %r has no value' % token
    if kind == 'boot':
        return None if not value else 'boot takes no value'
    if kind == 'timer':
        match = re.fullmatch(r'(\d{1,3})m', value)
        if not match or not 1 <= int(match.group(1)) <= phases['min_idle_minutes']:
            return 'timer %r must be 1..%dm' % (value, phases['min_idle_minutes'])
        return None
    if kind in ('step', 'fixture'):
        wanted = value if kind == 'step' else 'fixture:' + value
        if kind == 'fixture' and value not in context['commands']:
            return 'fixture %s has no command in any source' % value
        limit = PHASE_ORDER.index(phase)
        for name in PHASE_ORDER[:limit + 1]:
            if wanted in context['index'].get(name, {}):
                return None
        return 'no %s step in phases up to %s' % (wanted, phase)
    if kind == 'setting':
        return None if value in SOAK_SETTINGS else 'setting %s is not staged by SOAK_SETTINGS' % value
    if kind == 'gear':
        return None if value in GEAR_CARRIED else 'gear %s is not in the soak gear preset' % value
    if kind == 'marker':
        return None if value == CELLAR_MARKER_REL.rsplit('/', 1)[-1] else 'unknown marker %s' % value
    if kind == 'pack':
        return None if _TOKEN_NAME.match(value) else 'bad pack name %r' % value
    if kind == 'code':
        return None if value in context['sources'] else 'no source file %s under mods' % value
    return 'unknown token kind %r' % kind


def reach_rows(phases, root=ROOT, context=None):
    """[(key, phase, how, problems)] for every counter key that needs a reach row (manual rows excluded)."""
    context = context or reach_context(root)
    reach = phases.get('reach', {})
    rows = []
    for key in counter_keys(root):
        module, _, feature = key.partition('/')
        target = phase_of(phases, module, feature)
        if target is None or target[0] != 'phase':
            continue
        row = reach.get(key)
        problems = []
        how = []
        phase = target[1]
        if not isinstance(row, dict):
            problems.append('no reach row')
        else:
            how = row.get('how')
            if row.get('phase') != phase:
                problems.append('reach phase %r differs from the counter phase %s' % (row.get('phase'), phase))
            if row.get('class', 'required') not in REACH_CLASSES:
                problems.append('class must be one of %s' % (REACH_CLASSES,))
            if not isinstance(how, list) or not how or not all(isinstance(t, str) for t in how):
                problems.append('how must be a non-empty list of tokens')
                how = []
            for token in how:
                reason = reach_token_problem(token, phase, phases, context)
                if reason:
                    problems.append(reason)
            if how and not any(t.startswith('code:') for t in how):
                problems.append('how needs a code: token naming the counter call site')
            if how and not any(t.split(':', 1)[0] in ('boot', 'timer', 'step', 'fixture', 'setting', 'marker')
                               for t in how):
                problems.append('how needs a trigger token (boot, timer, step, fixture, setting or marker)')
        rows.append((key, phase, how, problems))
    known = {key for key, _, _, _ in rows}
    for key in sorted(set(reach) - known):
        rows.append((key, str(reach[key].get('phase')), [], ['reach row for a counter that needs none']))
    return rows


def reach_lines(rows):
    """(lines, unreached) for the plan output; unreached counts rows with at least one problem."""
    bad = [r for r in rows if r[3]]
    lines = ['', 'reach map (counter -> phase and the traced mechanism):']
    for key, phase, how, problems in rows:
        lines.append('  %-9s %-62s %s' % (phase, key, ' '.join(how)))
        lines += ['            unreached: ' + problem for problem in problems]
    lines.append('rows=%d reached=%d' % (len(rows), len(rows) - len(bad)))
    return lines, len(bad)


# ------------------------------------------------------------------ targeted selection

def changed_files(ref, root=ROOT):
    """Repo paths changed since the merge base with `ref`, committed or not (never the ref's own later work)."""
    import subprocess
    if not ref or ref.startswith('-'):
        raise Refused('--changed needs a git ref')
    base = subprocess.run(['git', 'merge-base', ref, 'HEAD'], cwd=root, capture_output=True, text=True)
    if base.returncode:
        raise Refused('git merge-base with %s failed' % ref)
    diff = subprocess.run(['git', 'diff', '--name-only', base.stdout.strip(), '--'], cwd=root,
                          capture_output=True, text=True)
    if diff.returncode:
        raise Refused('git diff against %s failed' % ref)
    return sorted({line.strip() for line in diff.stdout.splitlines() if line.strip()})


def _step_index():
    try:
        from tools.testing import driver_script
    except ImportError:
        raise Refused('tools.testing.driver_script is not in this checkout') from None
    return _campaign_driver_plan(PHASE_ORDER)[1]


def timer_minutes(how):
    """The longest timer:<n>m token of a reach row, 0 without one."""
    return max([int(t[6:-1]) for t in how if re.fullmatch(r'timer:\d{1,3}m', t)] or [0])


# Script layer folders hold unrelated files side by side; only a feature subfolder groups one feature.
_LAYER_FOLDERS = frozenset({'3_Game', '4_World', '5_Mission'})
# The dev-only test addon drives every phase; a change there selects nothing by itself.
_HARNESS_PREFIX = 'mods/HollowCountryTest/'


def feature_folder(folder):
    """'<mod>/<feature subfolder>' of a repo folder, the same across script layers; None in a flat layer folder."""
    parts = folder.split('/')
    if len(parts) < 3 or parts[-1] in _LAYER_FOLDERS:
        return None
    return parts[1] + '/' + parts[-1]


def source_folders(root=ROOT):
    """{file name: {feature folder}} of every mods/**/*.c file in a feature subfolder."""
    folders = {}
    for path in sorted((Path(root) / 'mods').rglob('*.c')):
        key = feature_folder(path.parent.relative_to(root).as_posix())
        if key:
            folders.setdefault(path.name, set()).add(key)
    return folders


def select_targets(phases, *, changed=None, modules=(), only_phases=(), index=None, folders=None):
    """The targeted selection, or None for the full campaign.

    changed: repo paths. A changed mods/**/*.c file selects the counters whose reach row names it in a code:
    token; failing that, the counters of the code: files in a same-named feature subfolder of the same mod
    in any script layer (never a flat layer folder). Files that reach no counter are listed, and refused only when nothing else is selected.
    modules and only_phases select directly. A counter brings its own phase, every earlier phase holding
    one of its step or fixture tokens, and its timer. join and idle are always driven.
    """
    if changed is None and not modules and not only_phases:
        return None
    reach = phases.get('reach', {})
    counters, unmapped_files, sources, harness = set(), [], [], []
    by_folder = None
    for path in changed or ():
        if not (path.startswith('mods/') and path.endswith('.c')):
            continue
        if path.startswith(_HARNESS_PREFIX):
            harness.append(path)
            continue
        sources.append(path)
        folder, _, name = path.rpartition('/')
        hits = {key for key, row in reach.items() if 'code:' + name in row.get('how', [])}
        group = feature_folder(folder)
        if not hits and group:
            if by_folder is None:
                by_folder = source_folders() if folders is None else folders
            hits = {key for key, row in reach.items()
                    if any(t.startswith('code:') and group in by_folder.get(t[5:], ()) for t in row.get('how', []))}
        counters |= hits
        if not hits:
            unmapped_files.append(path)
    for module in modules:
        hits = {key for key in reach if key.partition('/')[0] == module}
        if not hits:
            raise Refused('module %s has no reach row' % module)
        counters |= hits
    for phase in only_phases:
        if phase not in PHASE_ORDER:
            raise Refused('unknown phase %s (known: %s)' % (phase, ', '.join(PHASE_ORDER)))
    if not counters and not only_phases:
        named = unmapped_files + harness
        raise Refused('nothing to run: no changed mods/**/*.c file reaches a counter; pass --modules or '
                      '--only-phases' + (': ' + ', '.join(named) if named else ''))
    index = _step_index() if index is None else index
    wanted = {'join', 'idle'} | set(only_phases)
    timers = [0]
    for key in counters:
        row = reach[key]
        wanted.add(row['phase'])
        timers.append(timer_minutes(row['how']))
        limit = PHASE_ORDER.index(row['phase'])
        for token in row['how']:
            kind, _, value = token.partition(':')
            if kind not in ('step', 'fixture'):
                continue
            needle = value if kind == 'step' else token
            wanted |= {name for name in PHASE_ORDER[:limit + 1] if needle in index.get(name, {})}
    ordered = [name for name in PHASE_ORDER if name in wanted]
    driven = sum(p['minutes'] for p in phases['phases'] if p['name'] in wanted and p['name'] != 'idle')
    idle = max(TARGETED_IDLE_MINUTES, *timers)
    return {'targeted': True, 'phases': ordered, 'counters': sorted(counters), 'idle_minutes': idle,
            'window_minutes': driven + idle, 'sources': sources, 'unmapped_sources': unmapped_files,
            'harness_sources': harness,
            'modules': list(modules), 'only_phases': list(only_phases)}


def judged(selection, phases, key, phase):
    """Whether a counter of `phase` could fire in this run; always true for the full campaign."""
    if not selection:
        return True
    if phase not in selection['phases']:
        return False
    row = phases.get('reach', {}).get(key, {})
    return timer_minutes(row.get('how', [])) <= selection['window_minutes']


def selection_lines(selection, phases):
    driven = [p for p in phases['phases'] if p['name'] in selection['phases'] and p['name'] != 'idle']
    out = ['Targeted soak selection (not release evidence; the full campaign stays the release-candidate run)', '']
    out.append('phases: ' + ', '.join(selection['phases']))
    out.append('minutes: driven %d (driver budget %d) + idle %d' % (
        sum(p['minutes'] for p in driven), int(sum(p['minutes'] for p in driven) * 1.5) + JOIN_MINUTES,
        selection['idle_minutes']))
    if selection['sources']:
        out.append('changed sources: %d (%d reach no counter)' % (len(selection['sources']),
                                                                  len(selection['unmapped_sources'])))
        out += ['  no counter: ' + path for path in selection['unmapped_sources']]
    if selection['harness_sources']:
        out.append('test addon changes (they select nothing; add --only-phases for the steps they change): %d'
                   % len(selection['harness_sources']))
    if selection['modules']:
        out.append('modules: ' + ', '.join(selection['modules']))
    out.append('selected counters (%d):' % len(selection['counters']))
    out += ['  ' + key for key in selection['counters']]
    return out


# ------------------------------------------------------------------ staged content (pure)

# What the actions need, one entry per item: craft (CamoNet + KitchenKnife), the radio (PersonalRadio and a
# battery), two light mounts (a UniversalLight and DuctTape each, onto Mich2001Helmet and TortillaBag), salvage
# (Pliers), flip (Crowbar), the note actions (Paper, Pen_Black), a spare Rag and clothing.
GEAR_CARRIED = ('KitchenKnife', 'CamoNet', 'PersonalRadio', 'Battery9V', 'Mich2001Helmet', 'TortillaBag',
                'UniversalLight', 'UniversalLight', 'Battery9V', 'Flashlight', 'Battery9V', 'DuctTape', 'DuctTape',
                'Crowbar', 'Wrench', 'Pliers', 'Rag', 'Paper', 'Pen_Black', 'LeatherJacket_Beige',
                'Mag_AKM_30Rnd', 'Ammo_762x39')


def gear_preset():
    """One native spawn-gear preset: worn clothes, a bag, a rifle with a magazine, and the items the actions need."""
    def attributes(health=(0.6, 0.69), quantity=(0.0, 0.0)):
        return {'healthMax': health[1], 'healthMin': health[0], 'quantityMax': quantity[1], 'quantityMin': quantity[0]}

    def slot(name, item):
        return {'slotName': name, 'discreteItemSets': [{
            'attributes': attributes(), 'complexChildrenTypes': [], 'itemType': item, 'quickBarSlot': -1,
            'simpleChildrenTypes': [], 'simpleChildrenUseDefaultAttributes': True, 'spawnWeight': 1}]}

    rifle = slot('shoulderL', 'AKM')
    rifle['discreteItemSets'][0]['complexChildrenTypes'] = [{
        'itemType': 'Mag_AKM_30Rnd', 'quickBarSlot': -1, 'attributes': attributes((1.0, 1.0), (1.0, 1.0)),
        'complexChildrenTypes': [], 'simpleChildrenTypes': [], 'simpleChildrenUseDefaultAttributes': True}]
    carried = list(GEAR_CARRIED)
    return {'name': 'SoakTest', 'spawnWeight': 1,
            'characterTypes': ['SurvivorM_Mirek', 'SurvivorF_Eva'],
            'attachmentSlotItemSets': [slot('Body', 'TShirt_Black'), slot('Legs', 'Jeans_Black'),
                                       slot('Feet', 'Sneakers_Black'), slot('Back', 'AliceBag_Camo'), rifle],
            'discreteUnsortedItemSets': [{'name': 'soak-kit', 'spawnWeight': 1,
                                          'simpleChildrenTypes': carried, 'simpleChildrenUseDefaultAttributes': True}]}


def gameplay_with_preset(raw):
    data = json.loads(raw.decode('utf-8'))
    player = data.get('PlayerData')
    if not isinstance(player, dict):
        raise Refused('mission cfggameplay.json has no PlayerData')
    player['spawnGearPresetFiles'] = [GEAR_REL]
    return (json.dumps(data, indent=2) + '\n').encode('utf-8')


def settings_with_fixtures(raw):
    data = json.loads(raw.decode('utf-8'))
    if not isinstance(data, dict):
        raise Refused('profile settings.json is not an object')
    data.update(SOAK_SETTINGS)
    return (json.dumps(data, indent=2) + '\n').encode('utf-8')


def test_cfg(raw):
    """A copy of the server config with the soak keys set; every other byte (passwords included) is untouched."""
    text = raw.decode('utf-8')
    for key, value in CFG_EDITS:
        pattern = re.compile(r'^([ \t]*%s[ \t]*=[ \t]*)[^;\r\n]*(;)' % re.escape(key), re.I | re.M)
        found = pattern.findall(text)
        if len(found) > 1:
            raise Refused('serverDZ.cfg sets %s more than once; resolve it by hand first' % key)
        if found:
            text = pattern.sub(lambda m: m.group(1) + value + m.group(2), text, count=1)
        else:
            text = text.rstrip('\r\n') + '\n%s = %s;\n' % (key, value)
    return text.encode('utf-8')


def server_mods(bat):
    """The server's exact -mod list, in order, from its own start file."""
    found = re.findall(r'"-mod=([^"]*)"(?=\s|$)', bat.decode('utf-8', errors='replace'))
    if len(found) != 1:
        raise Refused('start-server.bat must hold exactly one -mod list')
    mods = [m for m in found[0].split(';') if m]
    if not mods or any(not re.fullmatch(r'@[A-Za-z0-9_. -]+', m) for m in mods):
        raise Refused('start-server.bat -mod list is not a plain @folder list')
    return mods


def test_bat(raw):
    """A copy of start-server.bat that uses the test config, the profile copy and the test addon."""
    text = raw.decode('utf-8')
    mods = server_mods(raw)
    if TEST_MOD in mods:
        raise Refused('start-server.bat already lists the test addon')
    for token in ('-config=serverDZ.cfg', '-profiles=profiles '):
        if text.count(token) != 1:
            raise Refused('start-server.bat has an unexpected launch line')
    text = text.replace('-config=serverDZ.cfg', '-config=' + CFG_COPY)
    text = text.replace('-profiles=profiles ', '-profiles=' + PROFILE_COPY + ' ')
    before = '"-mod=' + ';'.join(mods) + '"'
    if text.count(before) != 1:
        raise Refused('start-server.bat -mod list is not a single quoted option')
    text = text.replace(before, '"-mod=' + ';'.join(mods + [TEST_MOD]) + '"')
    return text.encode('utf-8')


def meta_id(folder):
    meta = Path(folder) / 'meta.cpp'
    if not meta.is_file():
        return None
    match = re.search(r'^\s*publishedid\s*=\s*(\d+)\s*;', meta.read_text(encoding='utf-8', errors='replace'), re.M)
    return match.group(1) if match else None


def client_mods(mods, server_root, workshop, win):
    """Client -mod paths: own mods from the server root (same bytes as the server), the rest by Workshop id."""
    by_id = {}
    for folder in sorted(Path(workshop).glob('@*')):
        ident = meta_id(folder)
        if ident:
            by_id.setdefault(ident, folder)
    paths = []
    for mod in mods:
        if mod in OWN_MODS:
            paths.append(win(Path(server_root) / mod))
            continue
        ident = meta_id(Path(server_root) / mod)
        if ident is None or ident not in by_id:
            raise Refused('the client has no Workshop copy of ' + mod)
        paths.append(win(by_id[ident]))
    return paths


def dependency_parity(mods, server_root, client_paths):
    """Read only PBOs in the resolved shared mod list; return (folder, differing PBO count) rows."""
    def inventory(folder):
        files = {}
        for path in sorted(Path(folder).rglob('*')):
            if path.is_file() and path.suffix.casefold() == '.pbo':
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
                key = path.relative_to(folder).as_posix().casefold()
                files.setdefault(key, []).append((path.stat().st_size, digest.hexdigest()))
        return files

    rows = []
    for mod, client in zip(mods, client_paths, strict=True):
        server = Path(server_root) / mod
        if server.resolve() == Path(client).resolve():
            continue  # Our own addons use the server's files, including the test addon before staging.
        left, right = inventory(server), inventory(client)
        rows.append((mod, sum(left.get(key) != right.get(key) for key in left.keys() | right.keys())))
    return rows


def require_dependency_parity(mods, server_root, client_paths, log=print):
    rows = dependency_parity(mods, server_root, client_paths)
    for folder, count in rows:
        if count:
            raise Refused('dependency mismatch: %s (%d pbo differ; players get kick 146; '
                          'rerun friend_install --apply)' % (folder, count))
    log('dependency parity: %d folders ok' % len(rows))


def kick_refusal(line):
    """Extract only the reason, never the player/identity prefix of a server kick line."""
    match = re.search(r'kicked from server:\s*(\d+)\s*\((.*)\)\s*$', line, re.I)
    if not match:
        return None
    reason = match[2]
    reason = re.sub(r'"[^"\n]*"', '[redacted]', reason)
    reason = re.sub(r"'[^']*'", '[redacted]', reason)
    reason = re.sub(r'\b(?:id|uid|steamid|guid|plainid)\s*[=:]\s*[^\s()]+',
                    '[id removed]', reason, flags=re.I)
    reason = re.sub(r'\b(?:\d{6,}|[0-9a-fA-F]{16,}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})\b',
                    '[id removed]', reason)
    if re.search(r'[A-Za-z]:\\|/home/|/mnt/', reason):
        reason = 'reason withheld: host path'
    return 'client never joined: kicked %s (%s)' % (match[1], reason)


def ps_quote(value):
    return "'" + value.replace("'", "''") + "'"


def ps_arg(value):
    return ps_quote('"%s"' % value if re.search(r'\s', value) else value)


def client_arguments(mod_paths, profile_win, game_port=2302, query_port=27016):
    """DayZ_BE.exe arguments: the normal BattlEye launcher path with -connect to the local server."""
    return ['0', '1', '1', '-exe', 'DayZ_x64.exe', '-connect=127.0.0.1:%d:%d' % (game_port, query_port),
            '-port=%d' % game_port, '-mod=' + ';'.join(mod_paths), '-profiles=' + profile_win, '-doLogs']


# ------------------------------------------------------------------ host (Windows) boundary

# A failed script compile leaves the engine's modal "Compile error" box (Abort/Retry/Ignore), which ignores
# CloseMainWindow (2026-11-23 soak 178 boot 3). Ignore (IDIGNORE=5) is posted to that one dialog of that one
# process, as tools/release/wb_compile.py does for assertion boxes; Abort would end the process abruptly.
# The console window then takes the ordinary graceful close.
DIALOG_TYPE = r"""Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices; using System.Text;
public static class HcSoakDialog {
    public delegate bool EnumProc(IntPtr hwnd, IntPtr data);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc proc, IntPtr data);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int size);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr hwnd, StringBuilder text, int size);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr hwnd, uint msg, IntPtr w, IntPtr l);
    public static bool IgnoreCompileError(uint owner) {
        bool answered = false;
        EnumWindows((hwnd, data) => {
            uint pid;
            GetWindowThreadProcessId(hwnd, out pid);
            if (pid != owner || !IsWindowVisible(hwnd)) return true;
            var title = new StringBuilder(256); GetWindowText(hwnd, title, title.Capacity);
            var kind = new StringBuilder(256); GetClassName(hwnd, kind, kind.Capacity);
            if (title.ToString() == "Compile error" && kind.ToString() == "#32770")
                answered |= PostMessage(hwnd, 0x0111, (IntPtr)5, IntPtr.Zero);
            return true;
        }, IntPtr.Zero);
        return answered;
    }
}
'@
"""


def ps_encoded(script):
    """One -Command argument with no quotes for the Windows command line to mangle."""
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    return "iex ([Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('%s')))" % encoded


class WindowsHost:
    """Process and path access; tests replace it. Stops are the graceful CloseMainWindow path only."""

    def __init__(self):
        from tools.setup import winproc
        self.winproc = winproc
        self.sleep = time.sleep
        self.clock = time.monotonic

    def state(self, image):
        return self.winproc.process_state(image)

    def stop(self, image):
        name = image[:-4]
        script = (DIALOG_TYPE + "$p=@(Get-Process -Name %s -ErrorAction SilentlyContinue); "
                  "if ($p.Count -eq 0) { Write-Output 'HC stopped'; exit 0 }; "
                  "if ($p.Count -ne 1) { Write-Output 'HC stop ambiguous'; exit 2 }; "
                  "if ([HcSoakDialog]::IgnoreCompileError([uint32]$p[0].Id)) { "
                  "Write-Output 'HC compile error dialog answered Ignore'; Start-Sleep -Seconds 5; $p[0].Refresh() }; "
                  "if (-not $p[0].CloseMainWindow()) { Write-Output 'HC close refused'; exit 2 }; "
                  "if (-not $p[0].WaitForExit(%d)) { Write-Output 'HC close timeout'; exit 2 }; "
                  "Write-Output 'HC stopped'" % (name, STOP_WAIT_SECONDS * 1000))
        result = self.winproc.run('powershell', [ps_encoded(script)], attempts=1, timeout=STOP_WAIT_SECONDS + 60)
        if result.returncode:
            raise Refused('graceful close request for %s failed' % image)

    def launch_server(self, server_root_win):
        script = ("$ErrorActionPreference='Stop'; Start-Process -FilePath " + ps_quote(server_root_win + '\\' + BAT_COPY)
                  + ' -WorkingDirectory ' + ps_quote(server_root_win)
                  + " -ArgumentList '/min' -WindowStyle Hidden; Write-Output 'HC launch acknowledged'")
        self.launch(script, (SERVER_IMAGE,), 'server')

    def launch_client(self, client_root_win, arguments):
        script = ("$ErrorActionPreference='Stop'; Start-Process -FilePath " + ps_quote(client_root_win + '\\DayZ_BE.exe')
                  + ' -WorkingDirectory ' + ps_quote(client_root_win)
                  + ' -ArgumentList ' + ','.join(ps_arg(a) for a in arguments) + "; Write-Output 'HC launch acknowledged'")
        self.launch(script, (LAUNCHER_IMAGE, CLIENT_IMAGE), 'client')

    def launch(self, script, images, what):
        """Start once. A lost interop reply (soak 178 attempt 4: the server was up, the client launch got no answer)
        may hide a start that happened, so a retry only follows a check that none of the images is running."""
        for attempt in range(LAUNCH_ATTEMPTS):
            if attempt and self.started(images, what):
                return
            try:
                result = self.winproc.run('powershell', [ps_encoded(script)], attempts=1, timeout=LAUNCH_TIMEOUT_SECONDS)
            except self.winproc.InteropError:
                continue
            if result.returncode or 'HC launch acknowledged' not in result.stdout:
                raise Refused('%s start failed' % what)
            return
        if not self.started(images, what):
            raise Refused('%s start failed: Windows interop gave no answer %d times' % (what, LAUNCH_ATTEMPTS))

    def started(self, images, what):
        """True once any image runs; False only when every image reads gone for the whole settle window."""
        deadline = self.clock() + LAUNCH_SETTLE_SECONDS
        while True:
            states = [self.state(image) for image in images]
            if 'running' in states:
                return True
            if self.clock() >= deadline:
                if all(state == 'gone' for state in states):
                    return False
                raise Refused('cannot tell whether the %s started (process state unknown); '
                              'check it by hand, then run restore' % what)
            self.sleep(LAUNCH_POLL_SECONDS)


def default_win(path):
    from tools.setup import probe_core
    return probe_core.windows_path(path)


def default_linux(text):
    from tools.setup import probe_core
    return probe_core.linux_path(text)


def discover_client_root():
    for pattern in ('/mnt/*/SteamLibrary/steamapps/common/DayZ', '/mnt/*/Steam/steamapps/common/DayZ',
                    '/mnt/*/Program Files (x86)/Steam/steamapps/common/DayZ'):
        for path in sorted(Path('/').glob(pattern.lstrip('/'))):
            if (path / 'DayZ_BE.exe').is_file() and (path / 'DayZ_x64.exe').is_file():
                return path
    return None


# ------------------------------------------------------------------ staging with receipt

def sha(data):
    return hashlib.sha256(data).hexdigest()


class Stager:
    """Stage and restore the test profile. Receipt and byte backups live in the state folder."""

    def __init__(self, server_root, client_root, state=STATE, *, win=default_win, linux=default_linux):
        self.server = Path(server_root)
        self.mission = None
        self.client_parent = self.server.parent
        self.state = Path(state)
        self.win = win
        self.linux = linux
        self.client_root = Path(client_root) if client_root else None
        self.receipt = None

    # -- receipt
    @property
    def receipt_path(self):
        return self.state / 'receipt.json'

    def load(self):
        if not self.receipt_path.is_file():
            return None
        return json.loads(self.receipt_path.read_text(encoding='utf-8'))

    def save(self):
        self.state.mkdir(parents=True, exist_ok=True)
        tmp = self.receipt_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.receipt, indent=1, sort_keys=True), encoding='utf-8')
        tmp.replace(self.receipt_path)

    def roots(self):
        return {'server': self.server, 'mission': self.mission, 'client': self.client_parent}

    def mission_dir(self):
        found = sorted(p for p in (self.server / 'mpmissions').glob('*') if (p / GAMEPLAY).is_file())
        if len(found) != 1:
            names = [p.name for p in found]
            preferred = [p for p in found if p.name == 'dayzOffline.chernarusplus']
            if len(preferred) != 1:
                raise Refused('cannot pick the mission folder (%d candidates: %s)' % (len(found), ','.join(names)))
            found = preferred
        return found[0]

    # -- primitive steps
    def _created(self, root, rel, is_dir):
        if (root, rel) not in CREATED_ALLOWED:
            raise Refused('internal: unexpected staged path')
        target = self.roots()[root] / rel
        existed = target.exists()
        if existed and (root, rel) in {('mission', 'storage_' + INSTANCE_ID), ('mission', STRAY_STORAGE)}:
            return target
        if existed:
            raise Refused('%s/%s already exists; run restore (or remove it) first' % (root, rel))
        if not existed:
            self.receipt['created'].append({'root': root, 'rel': rel, 'dir': is_dir})
            self.save()
        return target

    def _write_new(self, root, rel, data):
        target = self._created(root, rel, False)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def _edit(self, root, rel, transform):
        if (root, rel) not in EDITED_ALLOWED:
            raise Refused('internal: unexpected edited path')
        target = self.roots()[root] / rel
        before = target.read_bytes()
        after = transform(before)
        backup = 'edit-%d.bak' % len(self.receipt['edited'])
        (self.state / backup).write_bytes(before)
        self.receipt['edited'].append({'root': root, 'rel': rel, 'backup': backup,
                                       'sha_before': sha(before), 'sha_after': sha(after)})
        self.save()
        target.write_bytes(after)

    # -- stage
    def stage(self, addon_dir, step_script):
        """addon_dir: built scratch @HollowCountryTest; step_script: the driver step file (dict)."""
        if self.load() is not None:
            raise Refused('a staged test profile exists; run restore first')
        self.mission = self.mission_dir()
        profiles = self.server / 'profiles'
        hc = profiles / 'HollowCountry'
        for needed in (self.server / 'serverDZ.cfg', self.server / 'start-server.bat', hc / 'settings.json',
                       hc / 'admins.json', addon_dir):
            if not Path(needed).exists():
                raise Refused('missing input: ' + Path(needed).name)
        admins = json.loads((hc / 'admins.json').read_text(encoding='utf-8'))
        if not isinstance(admins, dict) or not admins.get('PlainIds'):
            raise Refused('the local admin allowlist is empty; add the local client there first (ids are never printed)')
        bat = (self.server / 'start-server.bat').read_bytes()
        server_mods(bat)
        text_cfg = test_cfg((self.server / 'serverDZ.cfg').read_bytes())
        self.state.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(self.state / 'last-run', ignore_errors=True)
        self.receipt = {'schema': 1, 'staged_at': time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()),
                        'roots': {k: str(v) for k, v in self.roots().items()}, 'created': [], 'edited': []}
        self.save()
        # server side
        copy = self._created('server', PROFILE_COPY, True)
        copy.mkdir()
        for folder in sorted(p for p in profiles.iterdir() if p.is_dir()):
            shutil.copytree(folder, copy / folder.name, symlinks=True)
        settings = copy / 'HollowCountry/settings.json'
        settings.write_bytes(settings_with_fixtures(settings.read_bytes()))
        (copy / CELLAR_MARKER_REL).write_bytes(b'')
        self._write_new('mission', GEAR_REL, (json.dumps(gear_preset(), indent=2) + '\n').encode('utf-8'))
        self._edit('mission', GAMEPLAY, gameplay_with_preset)
        self._write_new('server', CFG_COPY, text_cfg)
        self._write_new('server', BAT_COPY, test_bat(bat))
        shutil.copytree(addon_dir, self._created('server', TEST_MOD, True))
        if (self.mission / ('storage_' + INSTANCE_ID)).exists():
            raise Refused('the test storage folder already exists; remove it or run restore')
        self._created('mission', 'storage_' + INSTANCE_ID, True)  # recorded now; the server creates it
        self._created('mission', STRAY_STORAGE, True)  # recorded only when absent; see STRAY_STORAGE
        # client side
        client = self._created('client', CLIENT_PROFILE, True)
        step = client / STEP_REL
        step.parent.mkdir(parents=True)
        step.write_text(json.dumps(step_script, indent=1) + '\n', encoding='utf-8')
        return self.summary()

    def summary(self):
        rows = [('server', 'profile folders copied to ' + PROFILE_COPY + ' (EnableSmokeFixtures=true, FortifyBreachSeconds=20, cellar marker)'),
                ('server', 'test config ' + CFG_COPY + ' (forage-season date, daytime, own storage instance)'),
                ('server', 'start file ' + BAT_COPY + ' (test config, profile copy, ' + TEST_MOD + ')'),
                ('server', TEST_MOD + ' (built and signed test addon)'),
                ('mission', GEAR_REL + ' (test spawn gear)'),
                ('mission', GAMEPLAY + ' edited in place (spawnGearPresetFiles), byte backup in the receipt'),
                ('client', CLIENT_PROFILE + ' with the driver step file')]
        return rows

    # -- restore
    def restore(self, *, log=print):
        receipt = self.load()
        if receipt is None:
            log('restore: nothing staged')
            return False
        self.receipt = receipt
        self.mission = Path(receipt['roots']['mission'])
        self.server = Path(receipt['roots']['server'])
        self.client_parent = Path(receipt['roots']['client'])
        roots = self.roots()
        self._keep_logs()
        for row in reversed(receipt['edited']):
            if (row['root'], row['rel']) not in EDITED_ALLOWED:
                raise Refused('receipt names a path restore does not own; refused')
            target = roots[row['root']] / row['rel']
            original = (self.state / row['backup']).read_bytes()
            if sha(original) != row['sha_before']:
                raise Refused('byte backup does not match its receipt; refused')
            if target.is_file() and sha(target.read_bytes()) != row['sha_after']:
                log('restore: %s changed since it was staged; restoring the original bytes anyway' % row['rel'])
            target.write_bytes(original)
            if sha(target.read_bytes()) != row['sha_before']:
                raise Refused('restored bytes do not verify')
        for row in reversed(receipt['created']):
            if (row['root'], row['rel']) not in CREATED_ALLOWED:
                raise Refused('receipt names a path restore does not own; refused')
            target = roots[row['root']] / row['rel']
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            elif target.exists() or target.is_symlink():
                target.unlink()
        folder = self.mission / 'hollow-country-gameplay/gear'  # only an empty folder staging made
        with contextlib.suppress(OSError):
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
        for row in receipt['edited']:
            (self.state / row['backup']).unlink(missing_ok=True)
        self.receipt_path.unlink()
        log('restore: every staged file removed and every edited file back to its original bytes')
        return True

    def _keep_logs(self):
        """Copy the run's RPT/ADM files out of the folders restore removes, so report can read them later."""
        roots = self.roots()
        keep = self.state / 'last-run'
        for kind, rel in (('server', PROFILE_COPY), ('client', CLIENT_PROFILE)):
            source = roots[kind] / rel
            if not source.is_dir():
                continue
            (keep / kind).mkdir(parents=True, exist_ok=True)
            for path in sorted(source.glob('*')):
                if path.is_file() and path.suffix.lower() in ('.rpt', '.adm', '.log'):
                    shutil.copyfile(path, keep / kind / path.name)


# ------------------------------------------------------------------ run

_CRASH_FRAME = re.compile(r'^[A-Za-z0-9_./ -]+\.c:\d+ Function \w+$')


def crash_summary(folder):
    """'<innermost script frame>' of the newest engine crash log in folder, or None.

    Only script stack frames (mod-relative .c paths) are returned, never the program path or other text.
    """
    try:
        logs = sorted(Path(folder).glob('crash_*.log'), key=lambda p: p.stat().st_mtime)
    except OSError:
        return None
    if not logs:
        return None
    try:
        text = logs[-1].read_text(encoding='utf-8', errors='replace')
    except OSError:
        return 'crash log unreadable'
    for line in text.splitlines():
        line = line.strip()
        if _CRASH_FRAME.match(line):
            return line
    return 'native crash without a script frame'


def os_reason(error):
    """errno name of an OSError, never its path."""
    return errno.errorcode.get(getattr(error, 'errno', None) or 0, type(error).__name__)


def describe_failure(error):
    """A failure without private paths: the Refused text, or type, errno and the innermost repo frame."""
    if isinstance(error, Refused):
        return str(error)
    text = type(error).__name__
    if isinstance(error, OSError):
        text += ' ' + os_reason(error)
    frames = []
    trace = error.__traceback__
    while trace is not None:
        code = trace.tb_frame.f_code
        try:
            rel = Path(code.co_filename).resolve().relative_to(Path(__file__).resolve().parents[2])
            frames.append('%s:%d %s' % (rel.as_posix(), trace.tb_lineno, code.co_name))
        except ValueError:
            pass
        trace = trace.tb_next
    if frames:
        text += ' at ' + frames[-1]
    return text


def script_error_text(line):
    """The message after the SCRIPT (E) marker: a PBO-relative file and line, never a host path."""
    text = line.split(SCRIPT_ERROR, 1)[1].lstrip(': ').strip()
    if re.search(r'[A-Za-z]:\\|/home/|/mnt/', text):
        return '(message withheld: it names a host path)'
    return text[:240]


def tail_lines(path, offset):
    """New complete lines of a growing log since offset; returns (lines, new_offset)."""
    with Path(path).open('rb') as stream:
        stream.seek(offset)
        data = stream.read()
    end = data.rfind(b'\n')
    if end < 0:
        return [], offset
    return data[:end].decode('utf-8', errors='replace').replace('\r', '').split('\n'), offset + end + 1


def require_processes_stopped(host, action):
    for image in PROCESS_IMAGES:
        state = host.state(image)
        if state != 'gone':
            raise Refused('%s refused: %s is not stopped (state=%s)' % (action, image, state))


class Campaign:
    """The lead's run. Every process and clock interaction goes through host/clock so tests never start DayZ."""

    def __init__(self, stager, host, phases, *, addon_build, step_script, sleep=time.sleep, now=time.monotonic,
                 log=print, win=default_win, selection=None):
        self.stager, self.host, self.phases, self.selection = stager, host, phases, selection
        self.addon_build, self.step_script = addon_build, step_script
        self.sleep, self.now, self.log, self.win = sleep, now, log, win

    def preflight(self):
        require_processes_stopped(self.host, 'run')
        if self.stager.load() is not None:
            raise Refused('a staged test profile exists; run restore first')
        if manual_problems(self.phases) or unmapped(self.phases):
            raise Refused('the phase map is incomplete; run plan')

    def wait_for(self, what, minutes, check, images):
        """Poll check() until it returns a truthy result; every image in images must stay alive meanwhile."""
        images = (images,) if isinstance(images, str) else tuple(images)
        end = self.now() + minutes * 60
        unreadable = 0
        unknown = dict.fromkeys(images, 0)
        while True:
            try:
                result = check()
                unreadable = 0
            except OSError as error:  # a live log Windows holds for a moment; never a reason to abandon the run
                unreadable += 1
                if unreadable >= UNREADABLE_POLLS:
                    raise Refused('%s: log unreadable %d polls in a row (%s)' % (what, unreadable, os_reason(error)))
                result = None
            if result:
                return result
            for image in images:
                unknown[image] = self.still_running(image, unknown[image], 'stopped while waiting for ' + what)
            if self.now() >= end:
                raise Refused('timed out waiting for ' + what)
            self.sleep(POLL_SECONDS)

    def still_running(self, image, unknown, stopped):
        """Only 'gone' is a stop. 'unknown' is a lost interop reply, refused once it repeats UNREADABLE_POLLS times."""
        state = self.host.state(image)
        if state == 'running':
            return 0
        if state == 'gone':
            crash = crash_summary(Path(self.stager.server) / PROFILE_COPY) if image == SERVER_IMAGE else None
            if crash:
                raise Refused('%s crashed %s: %s' % (image, stopped.replace('stopped ', '', 1), crash))
            raise Refused('%s %s' % (image, stopped))
        unknown += 1
        if unknown >= UNREADABLE_POLLS:
            raise Refused('%s: process state unknown %d polls in a row' % (image, unknown))
        return unknown

    def appear(self, image, what):
        """Wait for a launched image to run before any liveness check reads its absence as a stop."""
        end = self.now() + PROCESS_APPEAR_SECONDS
        while self.host.state(image) != 'running':
            if self.now() >= end:
                raise Refused('%s did not start within %d s of the %s launch' % (image, PROCESS_APPEAR_SECONDS, what))
            self.sleep(APPEAR_POLL_SECONDS)

    def record_selection(self):
        """The report of this run reads it: a targeted run is marked, a full run removes any earlier mark."""
        path = Path(self.stager.state) / 'last-run' / SELECTION_FILE
        if self.selection:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.selection, indent=1, sort_keys=True) + '\n', encoding='utf-8')
            self.log('run: targeted (%s; idle %d min); not release evidence' % (
                ', '.join(self.selection['phases']), self.selection['idle_minutes']))
        else:
            path.unlink(missing_ok=True)

    def newest(self, folder, pattern):
        found = sorted(Path(folder).glob(pattern), key=lambda p: p.stat().st_mtime)
        return found[-1] if found else None

    def run(self):
        self.preflight()
        stager = self.stager
        driven = self.selection['phases'] if self.selection else PHASE_ORDER
        idle_minutes = self.selection['idle_minutes'] if self.selection else self.phases['min_idle_minutes']
        total = sum(p['minutes'] for p in self.phases['phases'] if p['name'] != 'idle' and p['name'] in driven)
        started = {'server': False, 'client': False}
        failure = None
        try:
            mod_names = server_mods((stager.server / 'start-server.bat').read_bytes()) + [TEST_MOD]
            mod_paths = client_mods(mod_names, stager.server, stager.client_root / '!Workshop', Path)
            require_dependency_parity(mod_names, stager.server, mod_paths, self.log)
            addon = self.addon_build()
            self.log('run: test addon built and signed')
            stager.stage(addon, self.step_script)
            self.log('run: test profile staged')
            self.record_selection()  # after staging, which clears last-run
            server_win = self.win(stager.server)
            started['server'] = True
            self.host.launch_server(server_win)
            self.appear(SERVER_IMAGE, 'server')
            server_profile = stager.server / PROFILE_COPY
            server_follow = {'path': None, 'offset': 0}

            script_follow = {'path': None, 'offset': 0}

            def server_ready():
                script = self.newest(server_profile, 'script_*.log')
                if script is not None:
                    if script_follow['path'] != script:
                        script_follow.update(path=script, offset=0)
                    lines, script_follow['offset'] = tail_lines(script, script_follow['offset'])
                    for line in lines:
                        if SCRIPT_ERROR in line:
                            raise Refused('the server logged a script error before connect enabled: '
                                          + script_error_text(line))
                path = self.newest(server_profile, 'DayZServer_x64_*.RPT')
                if path is None:
                    return False
                if server_follow['path'] != path:
                    server_follow.update(path=path, offset=0)
                lines, server_follow['offset'] = tail_lines(path, server_follow['offset'])
                return any(CONNECT_ENABLED in line for line in lines)

            self.wait_for('server connect enabled', SERVER_READY_MINUTES, server_ready, SERVER_IMAGE)
            self.log('run: server is accepting connections')
            mods = [self.win(path) for path in mod_paths]
            args = client_arguments(mods, self.win(stager.client_parent / CLIENT_PROFILE))
            started['client'] = True
            join_deadline = self.now() + CLIENT_JOIN_SECONDS
            self.host.launch_client(self.win(stager.client_root), args)
            self.appear(CLIENT_IMAGE, 'client')
            self.log('run: client launched through the BattlEye launcher')
            client_dir = stager.client_parent / CLIENT_PROFILE
            follow = {'path': None, 'offset': 0, 'done': False, 'inert': False, 'steps': 0,
                      'session': False, 'last_connect': 'no connect line', 'player': False}

            def driver_progress():
                path = self.newest(client_dir, '*.RPT')
                if path is None:
                    return False
                if follow['path'] != path:
                    follow.update(path=path, offset=0)
                lines, follow['offset'] = tail_lines(path, follow['offset'])
                for line in lines:
                    trace = CONNECT_TRACE.search(line)
                    if trace:
                        follow['last_connect'] = trace.group(0).strip()
                        if follow['last_connect'] == '[HC Driver] connect session start':
                            follow['session'] = True
                    if '[HC Driver] inert' in line:
                        follow['inert'] = True
                    elif '[HC Driver] step=' in line:
                        follow['steps'] += 1
                    elif '[HC Driver] done' in line:
                        follow['done'] = True
                return follow['done'] or follow['inert']

            def joined():
                driver_progress()  # Keep driver completion/step evidence read during the join wait.
                path = self.newest(server_profile, 'DayZServer_x64_*.RPT')
                if path is not None:
                    if server_follow['path'] != path:
                        server_follow.update(path=path, offset=0)
                    lines, server_follow['offset'] = tail_lines(path, server_follow['offset'])
                    for line in lines:
                        refusal = kick_refusal(line)
                        if refusal:
                            raise Refused(refusal)
                        if SERVER_PLAYER_CONNECTED.search(line):
                            follow['player'] = True
                return follow['session'] and follow['player']

            try:
                remaining_minutes = max(0, join_deadline - self.now()) / 60
                self.wait_for('client join', remaining_minutes, joined, (SERVER_IMAGE, CLIENT_IMAGE))
            except Refused as error:
                if str(error).startswith('timed out'):
                    raise Refused('client never joined: ' + follow['last_connect']) from None
                raise
            self.log('run: client session started and server player connect confirmed')
            budget = int(total * 1.5) + JOIN_MINUTES
            try:
                # The server too: a server crash mid-drive must end the run now, not after the whole budget
                # (2026-11-23 soak 178: the server died 3 minutes in and the run waited an hour on the client).
                self.wait_for('the driver to finish', budget, driver_progress, (SERVER_IMAGE, CLIENT_IMAGE))
            except Refused as error:
                if str(error).startswith('timed out'):
                    self.log('run: driver did not finish in its budget; idling anyway (the report shows how far it got)')
                else:
                    raise
            if follow['inert']:
                raise Refused('the client driver found no step file (inert); nothing was driven')
            self.log('run: driver steps seen=%d done=%s' % (follow['steps'], follow['done']))
            end = self.now() + idle_minutes * 60
            unknown = {SERVER_IMAGE: 0, CLIENT_IMAGE: 0}
            while self.now() < end:
                for image in (SERVER_IMAGE, CLIENT_IMAGE):
                    unknown[image] = self.still_running(image, unknown[image], 'stopped during the idle phase')
                self.sleep(min(POLL_SECONDS * 4, max(1, end - self.now())))
            self.log('run: idle window of %d minutes complete' % idle_minutes)
        except BaseException as error:  # restore must always run; the error is re-raised below
            failure = error
        finally:
            failure = self.shutdown(started, failure)
        if failure is not None:
            raise failure
        return True

    def shutdown_states(self):
        """Allow time for a close with a lost reply to finish before checking the staged files."""
        deadline = self.now() + STOP_WAIT_SECONDS
        while True:
            states = {}
            # Check the launcher first so it cannot start the client after we check for the client.
            for image in PROCESS_IMAGES:
                try:
                    states[image] = self.host.state(image)
                except (OSError, InteropError):
                    states[image] = 'unknown'
            remaining = deadline - self.now()
            if all(state == 'gone' for state in states.values()) or remaining <= 0:
                return states
            self.sleep(min(STOP_POLL_SECONDS, remaining))

    def shutdown(self, started, failure):
        """Graceful stops (client first), then restore. Returns the first failure, if any.

        Restore runs only when every started process is confirmed stopped: restoring under a running server
        fails on its open files and would hide the original failure (2026-11-23 soak 178).
        """
        if failure is not None and not isinstance(failure, Refused):
            self.log('run: failed: ' + describe_failure(failure))
        close_errors = {}
        for key, image in (('client', CLIENT_IMAGE), ('server', SERVER_IMAGE)):
            if not started[key]:
                continue
            try:
                self.host.stop(image)
            except (Refused, OSError, InteropError) as error:
                close_errors[image] = error
        stopped = True
        for image, state in self.shutdown_states().items():
            error = close_errors.get(image)
            if error is not None:
                if state == 'gone' and isinstance(error, (OSError, InteropError)):
                    self.log('run: stop %s reported %s. Independently confirmed gone' %
                             (image, describe_failure(error)))
                else:
                    self.log('run: stop %s failed: %s' % (image, describe_failure(error)))
                    if state == 'gone':
                        failure = failure or error
            if state != 'gone':
                stopped = False
                reason = '%s state=%s after shutdown' % (image, state)
                self.log('run: ' + reason)
                failure = failure or Refused(reason + '. Stop DayZ by hand, then run restore')
        if not stopped:
            self.log('run: left staged. Stop DayZ by hand, then run restore')
            return failure
        try:
            self.stager.restore(log=self.log)
        except (Refused, OSError) as error:
            self.log('run: restore failed: %s; run restore by hand' % describe_failure(error))
            failure = failure or error
        return failure


# ------------------------------------------------------------------ report

def driver_lines(path):
    from tools.release import rpt_summary
    out = []
    for raw in rpt_summary.lines(path):
        if '[HC Driver]' in raw:
            safe = rpt_summary.filtered(raw)
            if safe:
                out.append(safe[safe.index('[HC Driver]'):])
    return out


def activity_results(server_rpt, client_rpt):
    """(legacy, release, errors): each audit is independent, so one failing never hides the other."""
    from tools.release import activity_check
    legacy = release = None
    errors = []
    try:
        legacy = activity_check.scan(server_rpt, client_rpt=client_rpt)
    except (OSError, ValueError, TypeError, KeyError, re.error) as error:
        errors.append('activity_check (expectations) unavailable: %s' % type(error).__name__)
    try:
        release = activity_check.scan_release(server_rpt, client_rpt=client_rpt)
    except (OSError, ValueError, TypeError, KeyError, re.error) as error:
        errors.append('activity_check --release unavailable: %s' % type(error).__name__)
    return legacy, release, errors


def evidence_of(kind, row):
    if kind == 'expect':
        value = 'none' if row['value'] is None else '%g' % row['value']
        return '%s value=%s samples=%d window=%sm elapsed=%sm' % (row['status'], value, row['samples'],
                                                                  row['window_minutes'], row['elapsed_minutes'])
    extra = ' fixture=%d' % row['fixture'] if row.get('fixture') else ''
    return '%s count=%d%s' % (row['status'], row['count'], extra)


def report_rows(phases, legacy, release, errors=(), selection=None):
    rows = []
    sources = (('expect', legacy['features'] if legacy else None), ('use', release['features'] if release else None))
    for kind, features in sources:
        if features is None:
            continue
        for row in features:
            mapped = phase_of(phases, row['module'], row['feature']) or ('phase', 'unmapped')
            counter = '%s/%s' % (row['module'], row['feature'])
            seen = evidence_of(kind, row)
            if mapped[0] == 'phase':
                key = row['module'] + '/' + norm(row['feature'])
                if row['status'] == 'ACTIVE':
                    result = 'active'
                elif row['status'] == 'NOT_APPLICABLE':
                    # Upgrade-only feature without a persisted candidate. Keep
                    # this visibly unexercised, never active or waived.
                    result = 'not run'
                elif judged(selection, phases, key, mapped[1]):
                    result = 'zero'
                else:
                    result, seen = 'not run', 'targeted run did not reach it (observed: ' + seen + ')'
                rows.append((kind, counter, mapped[1], result, seen))
            else:
                rows.append((kind, counter, mapped[0], mapped[0], mapped[1] + ' (observed: ' + seen + ')'))
    for look in phases.get('looks', []):
        rows.append(('look', look['id'], 'manual', MANUAL_KINDS[look['kind']], look['reason']))
    for error in errors:
        rows.append(('audit', 'activity_check', 'idle', 'zero', error))
    return rows


def render_report(rows, drivers, release_summary, selection=None):
    totals = {r: sum(1 for row in rows if row[3] == r) for r in RESULTS}
    lines = ['# Soak campaign report', '']
    if selection:
        lines += ['**Targeted run: not release evidence.** Phases %s; idle %d min. Counters of phases it did not '
                  'drive (or whose timer is longer than the run) are "not run".' % (
                      ', '.join(selection['phases']), selection['idle_minutes']), '']
        if selection.get('unmapped_sources'):
            lines += ['Changed sources this run did not reach (no counter names them): '
                      + ', '.join('`%s`' % path for path in selection['unmapped_sources']), '']
    lines += ['works=%d broken=%d owner_check=%d friend_playtest=%d not_run=%d' % (
                 totals['active'], totals['zero'], totals['owner check'], totals['friend playtest'],
                 totals['not run']), '']
    if release_summary:
        lines += ['activity_check --release: `%s`' % release_summary, '']
    lines += ['| source | counter | phase | result | evidence |', '| --- | --- | --- | --- | --- |']
    order = {'zero': 0, 'active': 1, 'owner check': 2, 'friend playtest': 3, 'not run': 4}
    for kind, counter, phase, result, evidence in sorted(rows, key=lambda r: (order[r[3]], r[1], r[0])):
        lines.append('| %s | %s | %s | %s | %s |' % (kind, counter, phase, result, evidence.replace('|', '/')))
    lines += ['', '## Driver', '']
    lines += ['    ' + line for line in drivers] or ['    (no [HC Driver] lines in the client RPT)']
    return '\n'.join(lines) + '\n', totals


def build_report(phases, server_rpt, client_rpt, selection=None):
    legacy, release, errors = activity_results(server_rpt, client_rpt)
    rows = report_rows(phases, legacy, release, errors, selection)
    drivers = driver_lines(client_rpt) if client_rpt else []
    summary = None
    if release:
        summary = 'activity=%s count=%d' % (release['activity'], release['count'])
    return render_report(rows, drivers, summary, selection)


def last_run_logs(state=STATE):
    keep = Path(state) / 'last-run'
    server = sorted((keep / 'server').glob('*.RPT')) if (keep / 'server').is_dir() else []
    client = sorted((keep / 'client').glob('*.RPT')) if (keep / 'client').is_dir() else []
    return (server[-1] if server else None), (client[-1] if client else None)


def command_report(phases, state, out):
    server, client = last_run_logs(state)
    if server is None or client is None:
        raise Refused('no last run to report (both a server and a client RPT are needed)')
    marker = Path(state) / 'last-run' / SELECTION_FILE
    selection = json.loads(marker.read_text(encoding='utf-8')) if marker.is_file() else None
    text, totals = build_report(phases, server, client, selection)
    (Path(state) / 'last-run' / 'report.md').write_text(text, encoding='utf-8')
    out.write(text)
    return 8 if totals['zero'] else 0


# ------------------------------------------------------------------ plan

def _campaign_driver_plan(route):
    """Keep campaign-only kill plumbing and the audited step index in the same builder."""
    from tools.testing import driver_script
    original, notes = driver_script.build_plan(list(route))
    steps, index, offset = [], {}, 0
    for phase in route:
        # Preserve the full route's distance-based walk timeouts and waypoint notes.
        length = len(driver_script.build_route([phase])['steps'])
        phase_steps = original['steps'][offset:offset + length]
        offset += length
        if phase == 'walk_ai':
            phase_steps += [dict(kind='admin', cmd='fx_site_patrol_kill', value=''),
                            dict(kind='stand', seconds=20)]
        tokens = index.setdefault(phase, {})
        for step in phase_steps:
            token = driver_script.step_token(step, notes)
            step['id'] = 's%02d' % (len(steps) + 1)
            steps.append(step)
            tokens.setdefault(token, []).append(step['id'])
            if step['kind'] == 'admin' and step['cmd'].startswith('fx_'):
                tokens.setdefault('fixture:' + step['cmd'], []).append(step['id'])
    digest = hashlib.sha256(json.dumps(steps, sort_keys=True).encode('utf-8')).hexdigest()
    result = dict(version=driver_script.VERSION, run_id='r' + digest[:10], steps=steps)
    driver_script.validate_script(result)
    return result, index


def step_script(route=PHASE_ORDER):
    try:
        from tools.testing import driver_script
    except ImportError:
        raise Refused('tools.testing.driver_script is not in this checkout') from None
    if tuple(driver_script.PHASES) != PHASE_ORDER:
        raise Refused('driver_script phases differ from the campaign phases')
    try:
        return _campaign_driver_plan(route)[0]
    except ValueError as error:
        raise Refused('driver_script refused the route: ' + str(error)) from None


def plan_text(phases, root=ROOT):
    """(lines, problems). Pure: reads the repo, writes nothing."""
    out, problems = [], []
    out.append('Soak campaign plan (writes nothing)')
    out.append('')
    out.append('phases (driver order; idle lasts at least %d minutes; DebugSnapshot fires every %d s):' % (
        phases['min_idle_minutes'], phases['debug_snapshot_seconds']))
    for index, phase in enumerate(phases['phases'], 1):
        out.append('  %d. %-9s %4d min  %s' % (index, phase['name'], phase['minutes'], phase['what']))
    universe, modules = counter_universe(root)
    mapped = {name: [] for name in PHASE_ORDER}
    manual = []
    for kind, module, feature in sorted(universe):
        target = phase_of(phases, module, feature)
        if target is None:
            continue
        label = '%s:%s/%s' % (kind, module, feature)
        (mapped[target[1]] if target[0] == 'phase' else manual).append(label if target[0] == 'phase' else
                                                                        '%s [%s]' % (label, target[0]))
    out += ['', 'counter map (expect: activity-expectations row, use: [HC Use] registry literal):']
    for name in PHASE_ORDER:
        out.append('  %s (%d)' % (name, len(mapped[name])))
        for label in mapped[name]:
            out.append('    ' + label)
    out.append('  owner check / friend playtest (%d)' % len(manual))
    out += ['    ' + label for label in manual]
    out.append('  non-counter rows: ' + ', '.join('%s [%s]' % (x['id'], x['kind']) for x in phases.get('looks', [])))
    missing = unmapped(phases, root)
    bad = manual_problems(phases)
    out += ['', 'counters=%d unmapped counters: %d' % (len(universe), len(missing))]
    out += ['  unmapped: ' + item for item in missing] + ['  problem: ' + item for item in bad]
    problems += missing + bad
    try:
        lines, unreached = reach_lines(reach_rows(phases, root))
    except ImportError:
        lines, unreached = ['', 'reach map unavailable: tools.testing.driver_script is missing', 'unreached=1'], 1
    out += lines
    out.append('unreached=%d' % unreached)
    problems += ['unreached counters: %d' % unreached] if unreached else []
    out += ['', 'would stage (copies and new files; the real profile folders are never edited):']
    out += ['  [%s] %s' % row for row in Stager('x', None).summary()]
    out.append('  receipt with byte backups; restore puts every byte back and is a no-op when nothing is staged')
    return out, problems


def plan_checks(root=ROOT):
    """Extra reasons the campaign cannot run in this checkout."""
    reasons = []
    try:
        from tools.testing import test_addon
        test_addon.plan(root)
    except Exception as error:  # ValueError family; never echo a path
        reasons.append('test addon unavailable: ' + str(error).splitlines()[0][:160])
    try:
        step_script()
    except Refused as error:
        reasons.append('step file unavailable: ' + str(error))
    return reasons


# ------------------------------------------------------------------ cli

def local_roots(args):
    server = default_linux(args.server_root)
    if not server.is_dir():
        raise Refused('the local server folder is not available')
    client = Path(args.client_root) if args.client_root else discover_client_root()
    return server, client


def main(argv=None, *, host=None, out=None):
    from tools.release.host_lock import host_lock

    out = out or sys.stdout
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mode', nargs='?', default='plan', choices=('plan', 'stage', 'run', 'restore', 'report'))
    parser.add_argument('--server-root', default=SERVER_ROOT_DEFAULT, help='Windows path of the local server install')
    parser.add_argument('--client-root', default=None, help='WSL path of the DayZ client install (default: discover)')
    parser.add_argument('--state-dir', type=Path, default=STATE)
    parser.add_argument('--phases', type=Path, default=PHASES_FILE)
    parser.add_argument('--yes', action='store_true', help='run only: the lead confirms the owner is not playing')
    parser.add_argument('--changed', metavar='REF', help='targeted: counters of the mods/**/*.c files changed since REF')
    parser.add_argument('--modules', default='', help='targeted: comma-separated modules to drive')
    parser.add_argument('--only-phases', default='', help='targeted: comma-separated phases to drive')
    args = parser.parse_args(argv)
    try:
        phases = load_phases(args.phases)
        listed = lambda text: [x.strip() for x in text.split(',') if x.strip()]
        selection = select_targets(phases, changed=changed_files(args.changed) if args.changed else None,
                                   modules=listed(args.modules), only_phases=listed(args.only_phases))
        if args.mode == 'plan':
            lines, problems = plan_text(phases)
            if selection:
                lines = selection_lines(selection, phases) + ['', 'phase map problems: %d' % len(problems)]
                lines += ['  ' + problem for problem in problems]
            else:
                lines += ['', 'phase map problems: %d' % len(problems)]
            reasons = plan_checks()
            for line in lines:
                print(line, file=out)
            for reason in reasons:
                print('plan FAILED: ' + reason, file=out)
            return 2 if (problems or reasons) else 0
        if args.mode == 'report':
            return command_report(phases, args.state_dir, out)
        server, client = local_roots(args)
        stager = Stager(server, client, args.state_dir)
        host = host or WindowsHost()
        if args.mode == 'restore':
            with host_lock('soak_campaign'):
                require_processes_stopped(host, 'restore')
                stager.restore(log=lambda text: print(text, file=out))
            return 0
        if client is None:
            raise Refused('the DayZ client install was not found; pass --client-root')
        from tools.testing import test_addon
        script = step_script(selection['phases'] if selection else PHASE_ORDER)
        if args.mode == 'stage':
            with host_lock('soak_campaign'):
                require_processes_stopped(host, 'stage')
                addon = Path(test_addon.build()['path'])
                for line in stager.stage(addon, script):
                    print('staged [%s] %s' % line, file=out)
            return 0
        if not args.yes:
            raise Refused('run is lead-only and idles at least %d minutes; pass --yes' % (
                selection['idle_minutes'] if selection else phases['min_idle_minutes']))
        with host_lock('soak_campaign'):
            campaign = Campaign(stager, host, phases, step_script=script, selection=selection,
                                addon_build=lambda: Path(test_addon.build()['path']),
                                log=lambda text: print(text, file=out, flush=True))
            campaign.run()
            return command_report(phases, args.state_dir, out)
    except (OSError, ValueError, KeyError, InteropError) as error:
        if not isinstance(error, (Refused, LockRefused)):
            error = Refused('%s (path withheld)' % describe_failure(error))
        print('soak_campaign: ' + str(error), file=out)
        return 2


if __name__ == '__main__':
    sys.exit(main())
