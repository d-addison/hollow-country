"""Soak campaign orchestrator: stage a local test profile, run the scripted client, idle, audit, restore.

  python3 -B -m tools.testing.soak_campaign plan      # default: phases, counter map, what would be staged; writes nothing
  python3 -B -m tools.testing.soak_campaign stage     # build the test addon and stage the test profile (reversible)
  python3 -B -m tools.testing.soak_campaign run --yes # LEAD ONLY: stage, boot, drive, idle >= 125 min, audit, stop, restore
  python3 -B -m tools.testing.soak_campaign restore   # put every staged byte back; a no-op when nothing is staged
  python3 -B -m tools.testing.soak_campaign report    # works/broken table of the last run

The campaign uses the dev-only test addon (mods/HollowCountryTest, never shipped) on the local server and the
owner's local client. Everything it adds is a COPY or a new file: the server runs from a copy of the profile
folders, a test copy of serverDZ.cfg and its own start file; only the mission's cfggameplay.json is edited in
place, with a byte backup in the receipt. BattlEye, signature checks and Steam are never bypassed. Counters are
never bumped by test code. Two-player and subjective items stay "owner check" / "friend playtest" rows.
Only the graceful CloseMainWindow path stops the server and the client. Nothing here prints a home path, a
Windows user folder, an id, a name or a config value.
"""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
PHASES_FILE = Path(__file__).with_name('soak_phases.json')
EXPECTATIONS = ROOT / 'config/activity-expectations.json'
STATE = Path.home() / '.cache/hollow-country/soak-campaign'
PHASE_ORDER = ('join', 'group', 'walk_ai', 'walk_zone', 'walk_town', 'fixtures', 'actions', 'idle')
RESULTS = ('active', 'zero', 'owner check', 'friend playtest')
MANUAL_KINDS = {'owner_check': 'owner check', 'friend_playtest': 'friend playtest'}
# Only the two-player and subjective items of the shared contract may be a manual row.
ALLOWED_MANUAL = frozenset({'TeamPing/ping_recipients', 'TeamPing/ping_delivered'})
ALLOWED_LOOKS = {'lighting_look': 'owner_check', 'grade_look': 'owner_check', 'audio': 'owner_check',
                 'group_sharing': 'friend_playtest', 'team_ping_delivery': 'friend_playtest'}
# GetName() of a base class that no feature reports under.
SOURCE_IGNORED_MODULES = frozenset({'unnamed'})
TEST_MOD = '@HollowCountryTest'
SERVER_IMAGE = 'DayZServer_x64.exe'
CLIENT_IMAGE = 'DayZ_x64.exe'
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
                   ('client', CLIENT_PROFILE), ('mission', GEAR_REL), ('mission', 'storage_' + INSTANCE_ID)}
EDITED_ALLOWED = {('mission', GAMEPLAY)}
CONNECT_ENABLED = 'Player connect enabled'
POLL_SECONDS = 30
SERVER_READY_MINUTES = 20
JOIN_MINUTES = 10


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


# ------------------------------------------------------------------ staged content (pure)

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
    carried = ['KitchenKnife', 'CamoNet', 'PersonalRadio', 'Battery9V', 'Mich2001Helmet', 'UniversalLight',
               'Battery9V', 'Flashlight', 'Battery9V', 'DuctTape', 'Crowbar', 'Wrench', 'Pliers', 'Rag',
               'LeatherJacket_Beige', 'Mag_AKM_30Rnd', 'Ammo_762x39']
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
    data['EnableSmokeFixtures'] = True
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


def ps_quote(value):
    return "'" + value.replace("'", "''") + "'"


def ps_arg(value):
    return ps_quote('"%s"' % value if re.search(r'\s', value) else value)


def client_arguments(mod_paths, profile_win, game_port=2302, query_port=27016):
    """DayZ_BE.exe arguments: the normal BattlEye launcher path with -connect to the local server."""
    return ['0', '1', '1', '-exe', 'DayZ_x64.exe', '-connect=127.0.0.1:%d:%d' % (game_port, query_port),
            '-port=%d' % game_port, '-mod=' + ';'.join(mod_paths), '-profiles=' + profile_win, '-doLogs']


# ------------------------------------------------------------------ host (Windows) boundary

class WindowsHost:
    """Process and path access; tests replace it. Stops are the graceful CloseMainWindow path only."""

    def __init__(self):
        from tools.setup import winproc
        self.winproc = winproc

    def state(self, image):
        return self.winproc.process_state(image)

    def stop(self, image):
        name = image[:-4]
        script = ("$p=@(Get-Process -Name %s -ErrorAction SilentlyContinue); "
                  "if ($p.Count -eq 0) { Write-Output 'HC stopped'; exit 0 }; "
                  "if ($p.Count -ne 1) { Write-Output 'HC stop ambiguous'; exit 2 }; "
                  "if (-not $p[0].CloseMainWindow()) { Write-Output 'HC close refused'; exit 2 }; "
                  "if (-not $p[0].WaitForExit(60000)) { Write-Output 'HC close timeout'; exit 2 }; "
                  "Write-Output 'HC stopped'" % name)
        result = self.winproc.run('powershell', [script], attempts=1, timeout=75)
        if result.returncode or self.state(image) != 'gone':
            raise Refused('graceful stop of %s failed; stop it by hand, then run restore' % image)

    def launch_server(self, server_root_win):
        script = ("$ErrorActionPreference='Stop'; Start-Process -FilePath " + ps_quote(server_root_win + '\\' + BAT_COPY)
                  + ' -WorkingDirectory ' + ps_quote(server_root_win)
                  + " -ArgumentList '/min' -WindowStyle Hidden; Write-Output 'HC launch acknowledged'")
        if self.winproc.run('powershell', [script], attempts=1).returncode:
            raise Refused('server start failed')

    def launch_client(self, client_root_win, arguments):
        script = ("$ErrorActionPreference='Stop'; Start-Process -FilePath " + ps_quote(client_root_win + '\\DayZ_BE.exe')
                  + ' -WorkingDirectory ' + ps_quote(client_root_win)
                  + ' -ArgumentList ' + ','.join(ps_arg(a) for a in arguments) + '; Write-Output \'HC launch acknowledged\'')
        if self.winproc.run('powershell', [script], attempts=1).returncode:
            raise Refused('client start failed')


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
        if existed and (root, rel) != ('mission', 'storage_' + INSTANCE_ID):
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
        # client side
        client = self._created('client', CLIENT_PROFILE, True)
        step = client / STEP_REL
        step.parent.mkdir(parents=True)
        step.write_text(json.dumps(step_script, indent=1) + '\n', encoding='utf-8')
        return self.summary()

    def summary(self):
        rows = [('server', 'profile folders copied to ' + PROFILE_COPY + ' (EnableSmokeFixtures=true, cellar marker)'),
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

def tail_lines(path, offset):
    """New complete lines of a growing log since offset; returns (lines, new_offset)."""
    with Path(path).open('rb') as stream:
        stream.seek(offset)
        data = stream.read()
    end = data.rfind(b'\n')
    if end < 0:
        return [], offset
    return data[:end].decode('utf-8', errors='replace').replace('\r', '').split('\n'), offset + end + 1


class Campaign:
    """The lead's run. Every process and clock interaction goes through host/clock so tests never start DayZ."""

    def __init__(self, stager, host, phases, *, addon_build, step_script, sleep=time.sleep, now=time.monotonic,
                 log=print, win=default_win):
        self.stager, self.host, self.phases = stager, host, phases
        self.addon_build, self.step_script = addon_build, step_script
        self.sleep, self.now, self.log, self.win = sleep, now, log, win

    def preflight(self):
        for image in (SERVER_IMAGE, CLIENT_IMAGE):
            state = self.host.state(image)
            if state != 'gone':
                raise Refused('refused: %s state=%s (no server or client may run, so no player is connected)' % (image, state))
        if self.stager.load() is not None:
            raise Refused('a staged test profile exists; run restore first')
        if manual_problems(self.phases) or unmapped(self.phases):
            raise Refused('the phase map is incomplete; run plan')

    def wait_for(self, what, minutes, check, image):
        end = self.now() + minutes * 60
        while True:
            result = check()
            if result:
                return result
            if self.host.state(image) != 'running':
                raise Refused('%s stopped while waiting for %s' % (image, what))
            if self.now() >= end:
                raise Refused('timed out waiting for ' + what)
            self.sleep(POLL_SECONDS)

    def newest(self, folder, pattern):
        found = sorted(Path(folder).glob(pattern), key=lambda p: p.stat().st_mtime)
        return found[-1] if found else None

    def run(self):
        self.preflight()
        stager = self.stager
        idle_minutes = self.phases['min_idle_minutes']
        total = sum(p['minutes'] for p in self.phases['phases'] if p['name'] != 'idle')
        started = {'server': False, 'client': False}
        failure = None
        try:
            addon = self.addon_build()
            self.log('run: test addon built and signed')
            stager.stage(addon, self.step_script)
            self.log('run: test profile staged')
            server_win = self.win(stager.server)
            started['server'] = True
            self.host.launch_server(server_win)
            server_profile = stager.server / PROFILE_COPY
            server_follow = {'path': None, 'offset': 0}

            def server_ready():
                path = self.newest(server_profile, 'DayZServer_x64_*.RPT')
                if path is None:
                    return False
                if server_follow['path'] != path:
                    server_follow.update(path=path, offset=0)
                lines, server_follow['offset'] = tail_lines(path, server_follow['offset'])
                return any(CONNECT_ENABLED in line for line in lines)

            self.wait_for('server connect enabled', SERVER_READY_MINUTES, server_ready, SERVER_IMAGE)
            self.log('run: server is accepting connections')
            mods = client_mods(server_mods((stager.server / 'start-server.bat').read_bytes()) + [TEST_MOD],
                               stager.server, stager.client_root / '!Workshop', self.win)
            args = client_arguments(mods, self.win(stager.client_parent / CLIENT_PROFILE))
            started['client'] = True
            self.host.launch_client(self.win(stager.client_root), args)
            self.log('run: client launched through the BattlEye launcher')
            client_dir = stager.client_parent / CLIENT_PROFILE
            follow = {'path': None, 'offset': 0, 'done': False, 'inert': False, 'steps': 0}

            def driver_progress():
                path = self.newest(client_dir, '*.RPT')
                if path is None:
                    return False
                if follow['path'] != path:
                    follow.update(path=path, offset=0)
                lines, follow['offset'] = tail_lines(path, follow['offset'])
                for line in lines:
                    if '[HC Driver] inert' in line:
                        follow['inert'] = True
                    elif '[HC Driver] step=' in line:
                        follow['steps'] += 1
                    elif '[HC Driver] done' in line:
                        follow['done'] = True
                return follow['done'] or follow['inert']

            budget = int(total * 1.5) + JOIN_MINUTES
            try:
                self.wait_for('the driver to finish', budget, driver_progress, CLIENT_IMAGE)
            except Refused as error:
                if str(error).startswith('timed out'):
                    self.log('run: driver did not finish in its budget; idling anyway (the report shows how far it got)')
                else:
                    raise
            if follow['inert']:
                raise Refused('the client driver found no step file (inert); nothing was driven')
            self.log('run: driver steps seen=%d done=%s' % (follow['steps'], follow['done']))
            end = self.now() + idle_minutes * 60
            while self.now() < end:
                for image in (SERVER_IMAGE, CLIENT_IMAGE):
                    if self.host.state(image) != 'running':
                        raise Refused('%s stopped during the idle phase' % image)
                self.sleep(min(POLL_SECONDS * 4, max(1, end - self.now())))
            self.log('run: idle window of %d minutes complete' % idle_minutes)
        except BaseException as error:  # restore must always run; the error is re-raised below
            failure = error
        finally:
            failure = self.shutdown(started, failure)
        if failure is not None:
            raise failure
        return True

    def shutdown(self, started, failure):
        """Graceful stops (client first), then restore. Returns the first failure, if any."""
        for key, image in (('client', CLIENT_IMAGE), ('server', SERVER_IMAGE)):
            if not started[key]:
                continue
            try:
                self.host.stop(image)
            except Refused as error:
                failure = failure or error
        if failure is None or not isinstance(failure, Refused) or 'by hand' not in str(failure):
            try:
                self.stager.restore(log=self.log)
            except Refused as error:
                failure = failure or error
        else:
            self.log('run: left staged; stop the process by hand, then run restore')
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


def report_rows(phases, legacy, release, errors=()):
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
                result = 'active' if row['status'] == 'ACTIVE' else 'zero'
                rows.append((kind, counter, mapped[1], result, seen))
            else:
                rows.append((kind, counter, mapped[0], mapped[0], mapped[1] + ' (observed: ' + seen + ')'))
    for look in phases.get('looks', []):
        rows.append(('look', look['id'], 'manual', MANUAL_KINDS[look['kind']], look['reason']))
    for error in errors:
        rows.append(('audit', 'activity_check', 'idle', 'zero', error))
    return rows


def render_report(rows, drivers, release_summary):
    totals = {r: sum(1 for row in rows if row[3] == r) for r in RESULTS}
    lines = ['# Soak campaign report', '',
             'works=%d broken=%d owner_check=%d friend_playtest=%d' % (
                 totals['active'], totals['zero'], totals['owner check'], totals['friend playtest']), '']
    if release_summary:
        lines += ['activity_check --release: `%s`' % release_summary, '']
    lines += ['| source | counter | phase | result | evidence |', '| --- | --- | --- | --- | --- |']
    order = {'zero': 0, 'active': 1, 'owner check': 2, 'friend playtest': 3}
    for kind, counter, phase, result, evidence in sorted(rows, key=lambda r: (order[r[3]], r[1], r[0])):
        lines.append('| %s | %s | %s | %s | %s |' % (kind, counter, phase, result, evidence.replace('|', '/')))
    lines += ['', '## Driver', '']
    lines += ['    ' + line for line in drivers] or ['    (no [HC Driver] lines in the client RPT)']
    return '\n'.join(lines) + '\n', totals


def build_report(phases, server_rpt, client_rpt):
    legacy, release, errors = activity_results(server_rpt, client_rpt)
    rows = report_rows(phases, legacy, release, errors)
    drivers = driver_lines(client_rpt) if client_rpt else []
    summary = None
    if release:
        summary = 'activity=%s count=%d' % (release['activity'], release['count'])
    return render_report(rows, drivers, summary)


def last_run_logs(state=STATE):
    keep = Path(state) / 'last-run'
    server = sorted((keep / 'server').glob('*.RPT')) if (keep / 'server').is_dir() else []
    client = sorted((keep / 'client').glob('*.RPT')) if (keep / 'client').is_dir() else []
    return (server[-1] if server else None), (client[-1] if client else None)


def command_report(phases, state, out):
    server, client = last_run_logs(state)
    if server is None or client is None:
        raise Refused('no last run to report (both a server and a client RPT are needed)')
    text, totals = build_report(phases, server, client)
    (Path(state) / 'last-run' / 'report.md').write_text(text, encoding='utf-8')
    out.write(text)
    return 8 if totals['zero'] else 0


# ------------------------------------------------------------------ plan

def step_script():
    try:
        from tools.testing import driver_script
    except ImportError:
        raise Refused('tools.testing.driver_script is not in this checkout (the drv brief adds it)') from None
    if tuple(driver_script.PHASES) != PHASE_ORDER:
        raise Refused('driver_script phases differ from the campaign phases')
    try:
        return driver_script.build_route(list(PHASE_ORDER))
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
    out = out or sys.stdout
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mode', nargs='?', default='plan', choices=('plan', 'stage', 'run', 'restore', 'report'))
    parser.add_argument('--server-root', default=SERVER_ROOT_DEFAULT, help='Windows path of the local server install')
    parser.add_argument('--client-root', default=None, help='WSL path of the DayZ client install (default: discover)')
    parser.add_argument('--state-dir', type=Path, default=STATE)
    parser.add_argument('--phases', type=Path, default=PHASES_FILE)
    parser.add_argument('--yes', action='store_true', help='run only: the lead confirms the owner is not playing')
    args = parser.parse_args(argv)
    try:
        phases = load_phases(args.phases)
        if args.mode == 'plan':
            lines, problems = plan_text(phases)
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
            for image in (SERVER_IMAGE, CLIENT_IMAGE):
                if host.state(image) != 'gone':
                    raise Refused('restore refused: %s is not stopped' % image)
            stager.restore(log=lambda text: print(text, file=out))
            return 0
        if client is None:
            raise Refused('the DayZ client install was not found; pass --client-root')
        from tools.testing import test_addon
        script = step_script()
        if args.mode == 'stage':
            addon = Path(test_addon.build()['path'])
            for line in stager.stage(addon, script):
                print('staged [%s] %s' % line, file=out)
            return 0
        if not args.yes:
            raise Refused('run is lead-only and idles at least %d minutes; pass --yes' % phases['min_idle_minutes'])
        from tools.release.host_lock import host_lock, LockRefused
        try:
            with host_lock('soak_campaign'):
                campaign = Campaign(stager, host, phases, step_script=script,
                                    addon_build=lambda: Path(test_addon.build()['path']),
                                    log=lambda text: print(text, file=out, flush=True))
                campaign.run()
        except LockRefused as error:
            raise Refused(str(error)) from None
        return command_report(phases, args.state_dir, out)
    except (Refused, OSError, ValueError, KeyError) as error:
        if not isinstance(error, Refused):
            error = Refused('%s (details withheld: may hold a private path)' % type(error).__name__)
        print('soak_campaign: ' + str(error), file=out)
        return 2


if __name__ == '__main__':
    sys.exit(main())
