"""Guided Hollow Country install for a friend's Windows dedicated server (standard library only).

Run it from the unzipped bundle (install-hollow-country.bat does exactly this):

    python -m tools.setup.friend_install [--server-root <DayZ server folder>] [--apply] [--check]

It walks ten steps in order. Each says what it found and what it would do, and each is skipped on its
own when it is already done:

  1 check the server folder           6 map overlays (layers: map_overlay validate, then install)
  2 check the server is stopped       7 profiles (Hollow Country and Expansion AI settings)
  3 Workshop dependencies (steamcmd)  8 merge the Hollow Country lines into serverDZ.cfg (backup first)
  4 copy mod folders and keys         9 write start-server.bat
  5 mission overlay (bundle-plan, then bundle-apply)         10 final checklist

Safety rules:

* Dry run by default. Nothing changes until --apply (or a typed yes at the end of a terminal dry run).
* Every file that is replaced is copied to hollow-country-install-backups/<run>/ first, and a receipt
  (hollow-country-install-receipt.json) records what was installed. A stale signed
  PBO in our own mod folder is moved into the backup folder. Saves and storage_* are never touched.
* A second run changes nothing. A file this installer wrote and that was changed afterwards is drift: for mod
  files, keys and start-server.bat the run refuses; a profile file the server or Expansion rewrote is kept.
  Profile bytes matching any shipped/receipted default upgrade with a backup; unknown bytes are kept with
  a WARN, unless explicitly selected with --adopt-profile "profiles/<file>".
  An existing file that was not written by this installer and differs needs --yes (or a typed yes).
* The server must be stopped (read-only process check; nothing is ever stopped or killed here).
* The friend types their own Steam login name; steamcmd asks for the password and the Steam Guard code
  itself. This tool never reads, stores, passes on or echoes a password.
* Only files the bundle manifest lists are ever installed; a file that merely sits in the bundle folder is not.
* The map overlay layers change the mission's cfggameplay.json and mapgrouppos.xml (receipted, byte-exact
  rollback: py -3 tools/package/map_overlay.py rollback --target <mission folder>); the server must be stopped.
* serverDZ.cfg: only the Hollow Country keys and the mission template change; passwords, hostname and every
  other line stay byte-identical.

--check only verifies an existing install and changes nothing. It establishes nothing about DayZ behaviour.
"""
import argparse
import contextlib
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

from tools.package import map_overlay
from tools.package import optional_overlays as overlays
from tools.setup import workshop_sync as ws

RECEIPT = 'hollow-country-install-receipt.json'
BACKUP_DIR = 'hollow-country-install-backups'
REMEMBER_FILE = 'hollow-country-server-root.txt'
REMEMBER_STEAMCMD = 'hollow-country-steamcmd.txt'
MAP_SOURCE = 'config/map-overlays'
BUNDLE_MANIFEST = 'bundle-manifest.json'
SERVER_EXE = ws.SERVER_EXE
BUNDLE_ROOT = Path(__file__).resolve().parents[2]
STEPS = ('server', 'stopped', 'workshop', 'mods', 'overlay', 'overlays-map', 'profiles', 'cfg', 'launcher', 'checklist')
SKIPPABLE = ('workshop', 'mods', 'overlay', 'overlays-map', 'profiles', 'cfg', 'launcher')
TITLES = {
    'server': 'Check the server folder',
    'stopped': 'Check the server is stopped',
    'workshop': 'Workshop dependencies',
    'mods': 'Copy mod folders and keys',
    'overlay': 'Mission overlay (bundle-plan, then bundle-apply)',
    'overlays-map': 'Map overlays (layers)',
    'profiles': 'Profiles',
    'cfg': 'serverDZ.cfg settings',
    'launcher': 'start-server.bat',
    'checklist': 'Final checklist',
}
ALLOWED_CFG_KEYS = ('thirdPersonView', 'disable3rdPerson', 'serverTimeAcceleration',
                    'serverNightTimeAcceleration', 'enableCfgGameplayFile')
SCHEMA = 1


class Refused(Exception):
    """A rule or precondition failed; run-owned changes must be undone."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


STEAM64_SHOWN = re.compile(r'(?<![0-9])[0-9]{17}(?![0-9])')


def shown(value):
    """Text for the screen with the home folder written as ~ and Steam64 ids redacted.

    Journal rows keep exact paths (COT PermissionsFramework/Players/<id>.json); every
    screen line, recovery listing and error goes through here, so ids never print.
    """
    text = str(value)
    home = str(Path.home())
    if home and home not in ('/', '\\'):
        text = text.replace(home, '~')
    return STEAM64_SHOWN.sub('<id>', text)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------------------------------------
# serverDZ.cfg: parsing and merging (Enforce-free, standard library)

def _mask(text):
    """The text with comments blanked (same length, newlines kept) and the brace depth at each character."""
    out = list(text)
    depth = []
    level = 0
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            depth.append(level)
            i += 1
            while i < n and text[i] not in '"\r\n':
                depth.append(level)
                i += 1
            if i < n and text[i] == '"':
                depth.append(level)
                i += 1
            continue
        if text.startswith('//', i):
            while i < n and text[i] not in '\r\n':
                out[i] = ' '
                depth.append(level)
                i += 1
            continue
        if text.startswith('/*', i):
            end = text.find('*/', i + 2)
            end = n if end < 0 else end + 2
            for j in range(i, end):
                if text[j] not in '\r\n':
                    out[j] = ' '
                depth.append(level)
            i = end
            continue
        if ch == '{':
            depth.append(level)
            level += 1
        elif ch == '}':
            level = max(0, level - 1)
            depth.append(level)
        else:
            depth.append(level)
        i += 1
    return ''.join(out), depth


def _same_value(old, new):
    old, new = old.strip().strip('"'), new.strip().strip('"')
    if old == new:
        return True
    try:
        return float(old) == float(new)
    except ValueError:
        return False


def cfg_values(text, keys):
    """{key: value} for top-level 'key = value;' lines (case-insensitive key match)."""
    masked, depth = _mask(text)
    found = {}
    for key in keys:
        for match in re.finditer(r'(?im)^[ \t]*(%s)[ \t]*=[ \t]*([^;\r\n]*?)[ \t]*;' % re.escape(key), masked):
            if depth[match.start(1)] == 0:
                found[key] = match.group(2)
    return found


def merge_cfg(text, want, template):
    """Return (new text, changes). Only the wanted keys and the mission template can change."""
    masked, depth = _mask(text)
    eol = '\r\n' if '\r\n' in text else '\n'
    edits = []
    changes = []
    missing = []
    for key, value in want.items():
        pattern = re.compile(r'(?i)(?<![\w])(%s)([ \t]*=[ \t]*)([^;\r\n]*?)([ \t]*;)' % re.escape(key))
        hits = [m for m in pattern.finditer(masked) if depth[m.start(1)] == 0]
        if len(hits) > 1:
            raise Refused('cfg_duplicate', 'serverDZ.cfg sets %s more than once; fix it by hand first' % key)
        if not hits:
            missing.append((key, value))
            continue
        hit = hits[0]
        line_start = masked.rfind('\n', 0, hit.start()) + 1
        line_end = masked.find('\n', hit.end())
        line_end = len(masked) if line_end < 0 else line_end
        if masked[line_start:hit.start()].strip() or masked[hit.end():line_end].strip():
            raise Refused('cfg_multiple', 'serverDZ.cfg has %s on a line with another statement; put it on its own '
                          'line first' % key)
        if _same_value(hit.group(3), value):
            changes.append({'key': key, 'action': 'unchanged', 'old': hit.group(3), 'new': value})
        else:
            edits.append((hit.start(3), hit.end(3), value))
            changes.append({'key': key, 'action': 'replaced', 'old': hit.group(3), 'new': value})
    tpl = [m for m in re.finditer(r'(\btemplate[ \t]*=[ \t]*")([^"\r\n]*)(")', masked) if depth[m.start(1)] >= 1]
    if not tpl:
        raise Refused('cfg_template_missing', 'serverDZ.cfg has no class Missions { class DayZ { template = "..."; }; } '
                      'block; add the stock one first')
    if len(tpl) > 1:
        raise Refused('cfg_duplicate', 'serverDZ.cfg has more than one mission template line; fix it by hand first')
    if tpl[0].group(2) == template:
        changes.append({'key': 'template', 'action': 'unchanged', 'old': tpl[0].group(2), 'new': template})
    else:
        edits.append((tpl[0].start(2), tpl[0].end(2), template))
        changes.append({'key': 'template', 'action': 'replaced', 'old': tpl[0].group(2), 'new': template})
    if missing:
        first_class = next((m for m in re.finditer(r'(?m)^[ \t]*class\b', masked) if depth[m.start()] == 0), None)
        position = first_class.start() if first_class else len(text)
        prefix = ''
        if first_class is None and text and not text.endswith(('\n', '\r')):
            prefix = eol
        block = prefix + ''.join('%s = %s;%s' % (key, value, eol) for key, value in missing)
        edits.append((position, position, block))
        changes += [{'key': key, 'action': 'inserted', 'old': None, 'new': value} for key, value in missing]
    new = text
    for start, end, replacement in sorted(edits, key=lambda e: e[0], reverse=True):
        new = new[:start] + replacement + new[end:]
    return new, changes


def parse_snippet(text):
    """(keys, template) from serverDZ-hollow-country.txt; only the Hollow Country keys are allowed."""
    keys, template = {}, None
    for raw in text.splitlines():
        line = raw.split('//', 1)[0].strip()
        match = re.match(r'^([A-Za-z_]\w*)\s*=\s*(.*?)\s*;$', line)
        if not match:
            continue
        key, value = match.group(1), match.group(2)
        if key == 'template':
            template = value.strip('"')
        elif key in ALLOWED_CFG_KEYS:
            keys[key] = value
        else:
            raise Refused('cfg_key_not_allowed', 'the bundle snippet sets %s; only %s may change'
                          % (key, ', '.join(ALLOWED_CFG_KEYS)))
    if not template:
        raise Refused('cfg_template_missing', 'the bundle snippet has no template line')
    return keys, template


# ---------------------------------------------------------------------------------------------------------
# Bundle and server inspection

def load_bundle(bundle):
    bundle = Path(bundle)
    path = bundle / BUNDLE_MANIFEST
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise Refused('bundle_missing', 'cannot read %s in the bundle folder (%s); run this from the unzipped bundle'
                      % (BUNDLE_MANIFEST, error.__class__.__name__))
    rows = data.get('files') if isinstance(data, dict) else None
    if not isinstance(rows, list) or not isinstance(data.get('mission'), str):
        raise Refused('bundle_missing', '%s has an unknown layout' % BUNDLE_MANIFEST)
    bad = []
    for row in rows:
        rel = row.get('path') if isinstance(row, dict) else None
        if not isinstance(rel, str) or rel.startswith('/') or '\\' in rel or '..' in rel.split('/') or ':' in rel:
            bad.append(str(rel))
            continue
        target = bundle / rel
        if target.is_symlink() or not target.is_file() or sha256_file(target) != row.get('sha256'):
            bad.append(rel)
    if bad:
        raise Refused('bundle_tampered', 'these bundle files are missing or changed since the bundle was built: %s%s; '
                      'unzip the bundle again' % (', '.join(bad[:8]), ' and %d more' % (len(bad) - 8) if len(bad) > 8 else ''))
    listed = {row['path'] for row in rows}
    folded = {}
    for rel in sorted(listed):
        folded.setdefault(rel.casefold(), []).append(rel)
    clashes = [' / '.join(names) for names in folded.values() if len(names) > 1]
    if clashes:
        raise Refused('bundle_tampered', 'these bundle paths differ only by case and would overwrite each other on '
                      'Windows: %s; unzip the bundle again' % ', '.join(clashes[:8]))
    absent = [rel for rel in ('start-server.bat', 'serverDZ-hollow-country.txt') if rel not in listed]
    if absent:
        raise Refused('bundle_tampered', '%s is not listed in %s; unzip the bundle again' % (', '.join(absent), BUNDLE_MANIFEST))
    defaults = data.get('profile_defaults', {})  # Older bundles have only their current file hashes.
    profiles = {row['path']: row['sha256'] for row in rows if row['path'].startswith('profiles/')}
    if not isinstance(defaults, dict) or (defaults and set(defaults) != set(profiles)):
        raise Refused('bundle_tampered', 'profile_defaults must describe only and all shipped profile files')
    for rel, entry in defaults.items():
        hashes = entry.get('shipped_sha256') if isinstance(entry, dict) else None
        if (not isinstance(hashes, list) or not hashes or
                any(not isinstance(h, str) or not re.fullmatch(r'[0-9a-f]{64}', h) for h in hashes) or
                entry.get('sha256') != profiles[rel] or profiles[rel] not in hashes):
            raise Refused('bundle_tampered', 'invalid shipped profile hashes for ' + rel)
    data['_sha'] = sha256_file(path)
    return data


def sha256_file(path):
    return ws.sha256_of(path)


def bundle_walk(bundle, manifest, prefix):
    """The files under prefix that the bundle manifest lists (load_bundle verified each one). A file that only
    sits in the bundle folder, planted or left over, is never listed here and so never installed."""
    rows = []
    for row in sorted(manifest['files'], key=lambda r: r['path']):
        if row['path'].startswith(prefix.rstrip('/') + '/'):
            rows.append((row['path'], Path(bundle) / row['path']))
    return rows


def parse_mod_list(bat_text):
    match = re.search(r'-mod=([^"\s]+)', bat_text)
    return match.group(1).split(';') if match else []


def load_receipt(server):
    path = Path(server) / RECEIPT
    if not path.exists():
        return {'schema': SCHEMA, 'files': {}, 'overlay': None}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise Refused('receipt_invalid', '%s cannot be read; move it away to start fresh (files are then treated as '
                      'existing ones and backed up before they are replaced)' % RECEIPT)
    if not isinstance(data, dict) or data.get('schema') != SCHEMA or not isinstance(data.get('files'), dict):
        raise Refused('receipt_invalid', '%s has an unknown layout' % RECEIPT)
    profiles = data.get('profile_defaults', {})
    if (not isinstance(profiles, dict) or
            any(not isinstance(hashes, list) or
                any(not isinstance(h, str) or not re.fullmatch(r'[0-9a-f]{64}', h) for h in hashes)
                for hashes in profiles.values())):
        raise Refused('receipt_invalid', '%s has invalid profile default hashes' % RECEIPT)
    return data


def steamcmd_exe(typed):
    """The steamcmd program for a typed path: the file itself, or the folder that holds it. None if neither."""
    path = Path(str(typed).strip().strip('"')).expanduser()
    if path.is_dir():
        for name in ('steamcmd.exe', 'steamcmd.sh', 'steamcmd'):
            if (path / name).is_file():
                return path / name
        return None
    return path if path.is_file() else None


def find_steamcmd(ctx):
    """--steamcmd, then the path remembered from an earlier run, then PATH. Never asks. Sets ctx.steamcmd (a Path
    or None) and ctx.steamcmd_from ('option', 'remembered', 'path'); an explicit option that points nowhere is
    reported when a download needs it, never replaced by a different steamcmd."""
    ctx.steamcmd, ctx.steamcmd_from, ctx.steamcmd_bad = None, None, None
    if ctx.args.steamcmd:
        found = steamcmd_exe(ctx.args.steamcmd)
        if found is None:
            ctx.steamcmd_bad = str(ctx.args.steamcmd)
        else:
            ctx.steamcmd, ctx.steamcmd_from = found, 'option'
        return
    try:
        remembered = (ctx.bundle / REMEMBER_STEAMCMD).read_text(encoding='utf-8').strip()
    except OSError:
        remembered = ''
    found = steamcmd_exe(remembered) if remembered else None
    source = 'remembered'
    if found is None:
        which = shutil.which('steamcmd')
        found = steamcmd_exe(which) if which else None
        source = 'path'
    if found is not None:
        ctx.steamcmd, ctx.steamcmd_from = found, source


def content_dirs(ctx, server):
    """Where downloaded items may be: --workshop-content, the steamcmd folder's own tree, the usual places beside
    the server folder."""
    args = ctx.args
    dirs = ws.content_dirs(args.workshop_content, ctx.steamcmd)
    tail = Path('steamapps') / 'workshop' / 'content' / ws.APP_ID
    for parent in [server.parent, *list(server.parents)[1:3]]:
        for candidate in (parent / tail, parent / 'workshop' / 'content' / ws.APP_ID):
            if candidate.is_dir() and candidate not in dirs:
                dirs.append(candidate)
    return dirs


# ---------------------------------------------------------------------------------------------------------
# Context and analysis

class Ctx:
    def __init__(self, args, out, input_fn):
        self.args = args
        self.out = out
        self.input_fn = input_fn
        self.server = None
        self.bundle = Path(args.bundle)
        self.manifest = None
        self.skip = set()
        self.receipt = None
        self.backup_root = None
        self.journal = None
        self.steam_user = args.steam_user
        self.notes = []
        self.steamcmd = None
        self.steamcmd_from = None
        self.steamcmd_bad = None
        self.statuses = {}

    def say(self, text=''):
        print(shown(text), file=self.out)

    def ask(self, prompt):
        if self.input_fn is None:
            return None
        try:
            return self.input_fn(prompt)
        except (EOFError, StopIteration):
            return ''


def classify_file(ctx, rel, source):
    """new / same / upgrade / confirm / drift for one file this installer would write."""
    ws.check_no_symlink_below(ctx.server, rel)
    target = ctx.server / rel
    want = sha256_file(source)
    if not target.exists() and not target.is_symlink():
        return 'new', want
    if not target.is_file():
        raise Refused('conflict', '%s exists and is not a regular file' % rel)
    current = sha256_file(target)
    if current == want:
        return 'same', want
    recorded = ctx.receipt['files'].get(rel)
    if recorded is None:
        return 'confirm', want
    return ('upgrade' if current == recorded else 'drift'), want


# Shipped as a partial key set: Expansion owns the rest of the file and rewrites a partial file with its
# own upgrade defaults, so an existing file gets these keys merged in (other fields kept) instead of replaced.
MERGE_PROFILES = {'profiles/ExpansionMod/Settings/AISettings.json'}


def merge_value(live, want):
    """The wanted value in the live file's own form (Expansion writes bools as 0/1)."""
    if isinstance(want, bool) and type(live) is int:
        return int(want)
    return want


def same_value(live, want):
    if isinstance(want, bool) or isinstance(live, bool):
        return type(live) in (bool, int) and bool(live) == bool(want)
    if isinstance(want, (int, float)) and isinstance(live, (int, float)):
        return abs(float(live) - float(want)) <= 1e-4 * max(1.0, abs(float(want)))
    return live == want


def merged_profile(target, source):
    """(merged bytes, changed keys) for a MERGE_PROFILES file, or None when either side is not a JSON object."""
    try:
        live = json.loads(target.read_text(encoding='utf-8-sig'))
        want = json.loads(source.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return None
    if not isinstance(live, dict) or not isinstance(want, dict):
        return None
    changed = [k for k, v in want.items() if k not in live or not same_value(live[k], v)]
    for key in changed:
        live[key] = merge_value(live.get(key), want[key])
    return (json.dumps(live, indent=4) + '\n').encode('utf-8'), changed


def classify_profile(ctx, rel, source, adopt=False):
    target = ctx.server / rel
    if rel in MERGE_PROFILES and target.is_file() and not target.is_symlink():
        ws.check_no_symlink_below(ctx.server, rel)
        merged = merged_profile(target, source)
        if merged is None:
            return 'drift', sha256_file(target)
        data, changed = merged
        return ('merge' if changed else 'same'), (sha256_bytes(data) if changed else sha256_file(target))
    action, want = classify_file(ctx, rel, source)
    if action in ('new', 'same'):
        return action, want
    current = sha256_file(ctx.server / rel)
    known = set(ctx.manifest.get('profile_defaults', {}).get(rel, {}).get('shipped_sha256', []))
    known.update(ctx.receipt.get('profile_defaults', {}).get(rel, []))
    recorded = ctx.receipt['files'].get(rel)
    if current == recorded or current in known:
        return 'upgrade', want
    if adopt:
        return 'confirm', want
    return 'drift', want


def profile_warning(rel):
    return ('kept %s (hand-edited or unknown profile bytes; not overwritten); '
            'to adopt with a backup, stop the server and run: '
            'install-hollow-country.bat --apply --adopt-profile "%s"' % (rel, rel))


class Analysis:
    def __init__(self):
        self.running = False
        self.own = []            # (rel, source, action, sha) for mod folders and keys
        self.stale = []          # relative paths of old signed files in our own mod folders
        self.profiles = []
        self.holdouts_state = None
        self.holdouts_moves = []
        self.cot = ([], 0)       # (COT admin record rows, count kept untouched); see cot_admin_records
        self.launcher = None
        self.cfg = None          # dict(path, raw, new, changes)
        self.third = []          # dict(item, folder_exists, ours)
        self.fetch = []          # items to download
        self.overlay = None


def analyze(ctx):
    a = Analysis()
    args = ctx.args
    manifest = ws.load_manifest()
    items = ws.select(manifest, list(ws.GROUPS))
    ctx.items = items
    own_folders = [i['folder'] for i in items if i['publish'] and bundle_walk(ctx.bundle, ctx.manifest, i['folder'])]
    ctx.own_folders = own_folders
    ctx.third_items = [i for i in items if i['id'] and not i['publish']]
    if not args.check:
        a.running = ws.server_running()
    # mod folders and keys
    if 'mods' not in ctx.skip:
        keys = {}
        for folder in own_folders:
            expected = set()
            for rel, source in bundle_walk(ctx.bundle, ctx.manifest, folder):
                action, sha = classify_file(ctx, rel, source)
                a.own.append((rel, source, action, sha))
                expected.add(rel.casefold())
            installed = ctx.server / folder / 'addons'
            if installed.is_dir() and not installed.is_symlink():
                for path in sorted(installed.iterdir()):
                    rel = '%s/addons/%s' % (folder, path.name)
                    # NTFS is case-insensitive: a case-only variant of an expected file is the file just written.
                    if path.is_file() and path.suffix.lower() in ('.pbo', '.bisign') and rel.casefold() not in expected:
                        a.stale.append(rel)
        for rel, source in bundle_walk(ctx.bundle, ctx.manifest, 'keys'):
            action, sha = classify_file(ctx, rel, source)
            a.own.append((rel, source, action, sha))
            keys[rel] = source
    if 'profiles' not in ctx.skip:
        shipped = {rel for rel, _ in bundle_walk(ctx.bundle, ctx.manifest, 'profiles')}
        unknown = set(args.adopt_profile) - shipped
        if unknown:
            raise Refused('profile_not_shipped', '--adopt-profile requires an exact shipped profile path')
        for rel, source in bundle_walk(ctx.bundle, ctx.manifest, 'profiles'):
            action, sha = classify_profile(ctx, rel, source, adopt=rel in args.adopt_profile)
            a.profiles.append((rel, source, action, sha))
        a.holdouts_state, a.holdouts_moves = inspect_holdouts(ctx)
        a.cot = cot_admin_records(ctx)
    if 'launcher' not in ctx.skip:
        source = ctx.bundle / 'start-server.bat'
        action, sha = classify_file(ctx, 'start-server.bat', source)
        a.launcher = ('start-server.bat', source, action, sha)
    if 'cfg' not in ctx.skip:
        keys_wanted, template = parse_snippet((ctx.bundle / 'serverDZ-hollow-country.txt').read_text(encoding='utf-8'))
        path = ctx.server / 'serverDZ.cfg'
        if not path.is_file():
            a.cfg = {'path': path, 'error': 'serverDZ.cfg was not found in the server folder'}
        else:
            raw = path.read_bytes()
            try:
                text = raw.decode('utf-8')
            except UnicodeDecodeError:
                raise Refused('cfg_unreadable', 'serverDZ.cfg is not UTF-8 text; save it as UTF-8 first')
            new, changes = merge_cfg(text, keys_wanted, template)
            a.cfg = {'path': path, 'raw': raw, 'new': new, 'changes': changes,
                     'todo': [c for c in changes if c['action'] != 'unchanged']}
    # Workshop dependencies
    find_steamcmd(ctx)
    dirs = content_dirs(ctx, ctx.server)
    ctx.dirs = dirs
    owned = set()
    try:
        receipt = ws.load_receipt(ctx.server, {m['folder'] for m in manifest['mods']})
        owned = set(receipt['dirs']) if receipt else set()
    except ws.SyncError as error:
        raise Refused('workshop_receipt', str(error))
    ctx.owned = owned
    for item in ctx.third_items:
        exists = (ctx.server / item['folder']).exists()
        state = ws.find_item(item['id'], dirs)[0]
        a.third.append({'item': item, 'exists': exists, 'ours': item['folder'] in owned, 'content': state})
    a.pending = [t for t in a.third if not t['exists']]
    a.left = [t for t in a.third if t['exists'] and not t['ours']]
    a.fetch = [t['item'] for t in a.pending if t['content'] != 'present']
    return a


# ---------------------------------------------------------------------------------------------------------
# Backups and writes

def stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')


# A write-ahead journal owns only this run's targets. Backups are published before
# the journal entry, and the entry is atomically published before the live write.
JOURNAL = 'run-journal.json'
ROLLBACK_OK = 'rolled back: the server is as it was before this run'


def journal_path(root):
    return root / JOURNAL


def safe_relative(rel):
    path = Path(rel)
    if (not rel or path.is_absolute() or path.as_posix() != rel or '\\' in rel
            or any(p in ('.', '..') or ':' in p or reserved_component(p) for p in path.parts)):
        raise ValueError('unsafe install journal target')
    return path


def reserved_component(name):
    return name.casefold().startswith('storage_') or name.casefold() == BACKUP_DIR.casefold()


def ignore_persistence(_directory, names):
    return [name for name in names if reserved_component(name)]


def tree_inventory(root):
    """Local backup inventory, excluding persistence at every depth; never follow links."""
    rows = {}
    def visit(path, rel):
        if path.is_symlink():
            raise ValueError('linked rollback target: ' + rel)
        if path.is_dir():
            rows[rel] = 'dir'
            for child in sorted(path.iterdir()):
                if not reserved_component(child.name):
                    visit(child, child.name if not rel else rel + '/' + child.name)
        elif path.is_file():
            rows[rel] = sha256_file(path)
        elif path.exists():
            raise ValueError('non-regular rollback target: ' + rel)
    visit(root, '')
    return rows


def inventory_digest(rows):
    return sha256_bytes(json.dumps(rows, sort_keys=True).encode())


def ensure_journal(ctx):
    if ctx.journal is not None:
        return
    ws.check_no_symlink_below(ctx.server, BACKUP_DIR)
    parent = ctx.server / BACKUP_DIR
    parent.mkdir(exist_ok=True)
    ctx.backup_root = Path(tempfile.mkdtemp(prefix=stamp() + '-', dir=parent))
    data = {'schema': 1, 'state': 'active', 'entries': [], 'temporaries': {}, 'unchanged': []}
    ws.write_json_atomic(journal_path(ctx.backup_root), data)
    ctx.journal = data


def scratch_names(directory):
    return sorted(p.name for pattern in ('.sync-*.tmp', '.receipt-*.tmp')
                  for p in directory.glob(pattern))


def track_target(ctx, rel, tree=False):
    """Capture once per run, including absent parents, immediately before a writer."""
    safe_relative(rel)
    ws.check_no_symlink_below(ctx.server, rel)
    ensure_journal(ctx)
    key = rel.casefold()
    for row in ctx.journal['entries']:
        path = row['path'].casefold()
        if key == path or (row['kind'] == 'tree' and key.startswith(path + '/')):
            return
    target = ctx.server / rel
    parent = Path(rel).parent
    if parent != Path('.') and not (ctx.server / parent).exists():
        track_target(ctx, parent.as_posix())
        record_written(ctx, parent.as_posix(), 'dir')
    backup = ctx.backup_root / rel
    row = {'path': rel, 'kind': 'absent', 'written': {}}
    if target.is_dir() and tree:
        before = tree_inventory(target)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(target, backup, ignore=ignore_persistence)
        if tree_inventory(backup) != before:
            raise ValueError('mission changed during backup')
        row.update(kind='tree', sha256=inventory_digest(before))
    elif target.is_file():
        backup.parent.mkdir(parents=True, exist_ok=True)
        ws.copy_atomic(target, backup)
        row.update(kind='file', sha256=sha256_file(backup))
    elif target.exists():
        raise ValueError('non-file install target: ' + rel)
    temporaries = dict(ctx.journal['temporaries'])
    parent_rel = Path(rel).parent.as_posix()
    if parent_rel == '.':
        parent_rel = ''
    temporaries.setdefault(parent_rel, scratch_names(target.parent))
    data = dict(ctx.journal, entries=ctx.journal['entries'] + [row], temporaries=temporaries)
    ws.write_json_atomic(journal_path(ctx.backup_root), data)
    ctx.journal = data


def pending_runs(ctx):
    parent = ctx.server / BACKUP_DIR
    ws.check_no_symlink_below(ctx.server, BACKUP_DIR)
    runs = []
    if not parent.exists():
        return runs
    for path in sorted(parent.glob('*/' + JOURNAL), reverse=True):
        ws.check_no_symlink_below(ctx.server, path.relative_to(ctx.server).as_posix())
        data = json.loads(path.read_text(encoding='utf-8'))
        if (not isinstance(data, dict) or data.get('schema') != 1
                or data.get('state') not in ('active', 'rolling-back', 'rollback_pending', 'complete', 'rolled-back')
                or not isinstance(data.get('entries'), list)
                or not isinstance(data.get('temporaries'), dict)):
            raise Refused('journal_invalid', 'cannot recover ' + shown(path))
        for rel, names in data['temporaries'].items():
            if rel:
                safe_relative(rel)
            if not isinstance(names, list) or not all(isinstance(n, str) and Path(n).name == n for n in names):
                raise Refused('journal_invalid', 'unknown temporary entry in ' + shown(path))
        for row in data['entries']:
            if (not isinstance(row, dict) or not isinstance(row.get('path'), str)
                    or row.get('kind') not in ('file', 'tree', 'absent')):
                raise Refused('journal_invalid', 'unknown entry in ' + shown(path))
            safe_relative(row['path'])
        if data['state'] in ('active', 'rolling-back', 'rollback_pending'):
            runs.append((path.parent, data))
    return runs


def record_written(ctx, rel, digest):
    """Publish expected bytes before a live write; retain earlier writes for interrupted upgrades."""
    track_target(ctx, rel)
    for row in ctx.journal['entries']:
        if rel == row['path'] or (row['kind'] == 'tree' and rel.startswith(row['path'] + '/')):
            name = rel[len(row['path']):].lstrip('/')
            values = row['written'].setdefault(name, [])
            if digest not in values:
                values.append(digest)
                ws.write_json_atomic(journal_path(ctx.backup_root), ctx.journal)
            return


@contextlib.contextmanager
def tree_writer(ctx, mission):
    """Fingerprint helper results before returning, including partial/refused writes.

    A hard process exit before this snapshot leaves unknown bytes: recovery must
    refuse those bytes, never infer ownership from a backup alone.
    """
    rel = mission.relative_to(ctx.server).as_posix()
    track_target(ctx, rel, tree=True)
    before = tree_inventory(mission)
    try:
        yield
    finally:
        after = tree_inventory(mission)
        row = next(row for row in ctx.journal['entries'] if row['path'] == rel)
        for name in before.keys() | after.keys():
            if before.get(name) != after.get(name):
                values = row['written'].setdefault(name, [])
                if after.get(name) not in values:
                    values.append(after.get(name))
        ws.write_json_atomic(journal_path(ctx.backup_root), ctx.journal)


def rollback_changes(ctx, root, data):
    """Only undo known installer bytes. Validate every row before mutating anything."""
    changes, conflicts = [], []
    for rel, before_names in data['temporaries'].items():
        if rel:
            ws.check_no_symlink_below(ctx.server, rel)
        for name in scratch_names(ctx.server / rel):
            if name not in before_names:
                changes.append(('remove', rel + '/' + name if rel else name, None))
    for row in reversed(data['entries']):
        rel = row['path']
        ws.check_no_symlink_below(ctx.server, rel)
        ws.check_no_symlink_below(root, rel)
        backup, target = root / rel, ctx.server / rel
        if row['kind'] == 'tree':
            before = tree_inventory(backup)
            if inventory_digest(before) != row.get('sha256'):
                raise ValueError('backup missing or changed: ' + rel)
            current = tree_inventory(target)
        else:
            if row['kind'] == 'file':
                if not backup.is_file() or sha256_file(backup) != row.get('sha256'):
                    raise ValueError('backup missing or changed: ' + rel)
                before = {'': row['sha256']}
            else:
                before = {}
            current = ({'': sha256_file(target)} if target.is_file() else
                       {'': 'dir'} if target.is_dir() else {})
        written = row.get('written', {})
        row_changes = []
        for name in before.keys() | current.keys():
            baseline, live = before.get(name), current.get(name)
            if live == baseline:
                continue
            full_rel = rel + ('/' + name if name else '')
            if live not in written.get(name, []):
                conflicts.append('%s (backup: %s)' % (full_rel, shown(backup / name)))
                continue
            if live is not None and (baseline is None or baseline == 'dir' or live == 'dir'):
                row_changes.append(('rmdir' if live == 'dir' else 'remove', full_rel, None))
            if baseline is not None:
                row_changes.append(('mkdir' if baseline == 'dir' else 'restore', full_rel, backup / name))
        # Keep reverse journal order; within a tree remove children before parents.
        changes.extend(sorted((c for c in row_changes if c[0] in ('remove', 'rmdir')),
                              key=lambda c: (c[1].count('/'), c[1]), reverse=True))
        changes.extend(sorted((c for c in row_changes if c[0] not in ('remove', 'rmdir')),
                              key=lambda c: (c[1].count('/'), c[1])))
    if conflicts:
        raise ValueError('changed after interrupted install; left untouched: ' + '; '.join(sorted(conflicts)))
    unique = {}
    for change in changes:
        unique.setdefault(change[:2], change)
    return list(unique.values())


def restore_change(ctx, change):
    action, rel, source = change
    ws.check_no_symlink_below(ctx.server, rel)
    target = ctx.server / rel
    if action == 'remove':
        target.unlink()
    elif action == 'rmdir':
        target.rmdir()  # Only empty directories; never recursively remove a live tree.
    elif action == 'mkdir':
        target.mkdir()
    else:
        ws.copy_atomic(source, target)


def describe_pending(ctx, root, data):
    state = 'install_interrupted' if data['state'] == 'active' else 'rollback_pending'
    lines = ['%s: %s; rerun with --apply with the server stopped to recover before installing'
             % (state, shown(journal_path(root)))]
    try:
        changes = rollback_changes(ctx, root, data)
        lines += ['  pending: %s %s' % (action, rel) for action, rel, _source in changes]
        if not changes:
            lines.append('  pending: finalize rollback journal')
    except (OSError, ValueError, ws.SyncError) as error:
        lines.append('  pending: inspect journal targets: ' + shown(error))
    return '\n'.join(lines)


def rollback_run(ctx, root, data):
    ws.write_json_atomic(journal_path(root), dict(data, state='rolling-back'))
    data['state'] = 'rolling-back'
    try:
        for change in rollback_changes(ctx, root, data):
            restore_change(ctx, change)  # Stop at the first failed undo; keep all backups.
    except (OSError, ValueError, ws.SyncError):
        data['state'] = 'rollback_pending'
        ws.write_json_atomic(journal_path(root), data)
        raise
    ws.write_json_atomic(journal_path(root), dict(data, state='rolled-back'))
    data['state'] = 'rolled-back'


def recover_runs(ctx, runs):
    require_stopped(ctx, ws.server_running())
    for root, data in runs:
        try:
            rollback_run(ctx, root, data)
        except (OSError, ValueError, ws.SyncError):
            raise Refused('rollback_pending', describe_pending(ctx, root, data))
        ctx.say('Recovered interrupted install; ' + ROLLBACK_OK)


def write_file(ctx, rel, source, action):
    target = ctx.server / rel
    record_written(ctx, rel, sha256_file(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    ws.copy_atomic(source, target)


def save_receipt(ctx):
    record_written(ctx, RECEIPT, sha256_bytes(ws.json_bytes(ctx.receipt)))
    ws.write_json_atomic(ctx.server / RECEIPT, ctx.receipt)


# ---------------------------------------------------------------------------------------------------------
# Steps. Each planner returns (status, lines, action) where action is None or a function run on --apply.

def plan_server(ctx, a):
    return 'ok', ['server folder: %s' % shown(ctx.server), '%s found' % SERVER_EXE], None


def plan_stopped(ctx, a):
    if a.running:
        return 'blocked', ['a DayZ server process is running; stop it yourself before --apply (this tool never '
                           'stops anything)'], None
    if a.running is None:
        return 'unknown', ['cannot read the process list; --apply needs the server stopped: pass --assume-stopped '
                           'only if you are sure it is'], None
    return 'ok', ['no %s process is running' % SERVER_EXE], None


def plan_workshop(ctx, a):
    third = ctx.third_items
    lines = []
    if 'workshop' in ctx.skip:
        return 'skipped', ['you asked to skip this step'], None
    present = [t for t in a.pending if t['content'] == 'present']
    if a.left:
        lines.append('already in the server folder and left as they are: %s' % ', '.join(t['item']['folder'] for t in a.left))
    if a.fetch:
        lines.append('to download with steamcmd (your own login; steamcmd asks for the password itself): %s'
                     % ', '.join('%s %s' % (i['folder'], i['id']) for i in a.fetch))
        if ctx.steamcmd is not None:
            lines.append('steamcmd: %s (downloads go to its own folder, %s)' % (shown(ctx.steamcmd), shown(ctx.steamcmd.parent)))
        else:
            lines.append('steamcmd was not found on PATH or in an earlier run; you are asked for its path when you apply '
                         '(or pass --steamcmd <path to steamcmd.exe>)')
    if present:
        lines.append('already downloaded, nothing to fetch: %s' % ', '.join(t['item']['folder'] for t in present))
    if a.pending:
        lines.append('then copied into the server folder with their keys: %s'
                     % ', '.join(t['item']['folder'] for t in a.pending))
        return 'planned', lines, lambda: do_workshop(ctx, a)
    if not a.pending:
        lines.append('all %d dependencies are in the server folder' % len(third))
        return 'already-done', lines, None
    return 'already-done', lines, None


def do_workshop(ctx, a):
    if a.fetch:
        do_fetch(ctx, a)
    install_dependencies(ctx, a)
    return 'done'


def do_fetch(ctx, a):
    with tempfile.TemporaryDirectory(prefix='hc-friend-fetch-') as temp:
        manifest = ws.load_manifest()
        wanted = {i['folder'] for i in a.fetch}
        manifest['mods'] = [m for m in manifest['mods'] if m['folder'] in wanted]
        path = Path(temp) / 'workshop_mods.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        # steamcmd without +force_install_dir downloads into whatever folder it was started from; always name both
        # the program and the folder, so the content lands where the install step looks for it.
        argv = ['fetch', '--groups', ','.join(ws.GROUPS), '--manifest', str(path), '--steam-user', ctx.steam_user,
                '--steamcmd', str(ctx.steamcmd), '--install-dir', str(ctx.steamcmd.parent)]
        for directory in ctx.dirs:
            argv += ['--workshop-content', str(directory)]
        code = fetch_workshop(argv, ctx.say)
    if code != 0:
        raise Refused('workshop_fetch', 'steamcmd did not finish cleanly; fix what it printed and run this again '
                      '(nothing else was changed by this step)')
    return 'done'


def fetch_workshop(argv, say):
    """Run workshop_sync fetch; steamcmd keeps the terminal so the friend types the password into it."""
    buffer = io.StringIO()
    with contextlib.redirect_stderr(sys.stderr):
        code = ws.main(argv, out=buffer)
    for line in buffer.getvalue().splitlines():
        say(line)
    return code


def count_actions(rows):
    counts = {}
    for _rel, _source, action, _sha in rows:
        counts[action] = counts.get(action, 0) + 1
    return counts


def describe(counts):
    parts = ['%d %s' % (n, name) for name, n in sorted(counts.items())]
    return ', '.join(parts) if parts else 'nothing'


def plan_mods(ctx, a):
    if 'mods' in ctx.skip:
        return 'skipped', ['you asked to skip this step'], None
    lines = []
    counts = count_actions(a.own)
    lines.append('own mod folders and keys from the bundle (%s): %s' % (', '.join(ctx.own_folders), describe(counts)))
    for rel in a.stale:
        lines.append('old signed file would move to the backup folder: %s' % rel)
    todo = [r for r in a.own if r[2] in ('new', 'upgrade', 'confirm')]
    if not todo and not a.stale:
        return 'already-done', lines, None
    return 'planned', lines, lambda: do_mods(ctx, a)


def do_mods(ctx, a):
    for rel, source, action, sha in a.own:
        if action == 'same':
            ctx.receipt['files'][rel] = sha
            continue
        write_file(ctx, rel, source, action)
        ctx.receipt['files'][rel] = sha
    for rel in a.stale:
        target = ctx.server / rel
        ws.check_no_symlink_below(ctx.server, rel)
        record_written(ctx, rel, None)
        target.unlink()
        ws.fsync_parent(target)
        ctx.receipt['files'].pop(rel, None)
    save_receipt(ctx)
    return 'done'


def install_dependencies(ctx, a):
    missing = []
    for dep in a.pending:
        state = ws.find_item(dep['item']['id'], ctx.dirs)[0]
        if state != 'present':
            missing.append('%s %s' % (dep['item']['folder'], dep['item']['id']))
    if missing:
        raise Refused('workshop_missing', 'these dependencies are not downloaded yet: %s; run step 3 (do not skip it) '
                      'or point --workshop-content at the steamapps/workshop/content/221100 folder' % ', '.join(missing))
    items = [t['item'] for t in a.pending]
    targets, _skipped, _manual = ws.plan_install(items, ctx.dirs, ctx.server, ctx.owned)
    ensure_journal(ctx)
    for rel, (_item, digest, _source) in sorted(targets.items()):
        target = ctx.server / rel
        if target.is_file() and sha256_file(target) == digest:
            ctx.journal['unchanged'].append(rel)
            ctx.say('  unchanged: ' + rel)
    ws.write_json_atomic(journal_path(ctx.backup_root), ctx.journal)
    with tempfile.TemporaryDirectory(prefix='hc-friend-install-') as temp:
        manifest = ws.load_manifest()
        wanted = {t['item']['folder'] for t in a.pending}
        manifest['mods'] = [m for m in manifest['mods'] if m['folder'] in wanted]
        path = Path(temp) / 'workshop_mods.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        argv = ['install', '--server-root', str(ctx.server), '--groups', ','.join(ws.GROUPS), '--manifest', str(path),
                '--assume-stopped']
        for directory in ctx.dirs:
            argv += ['--workshop-content', str(directory)]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err):
            code = ws.main(argv, out=out, before_write=lambda rel, digest: record_written(ctx, rel, digest))
    if code != 0:
        raise Refused('mods', 'the dependency copy was refused: %s' % err.getvalue().strip())
    for line in out.getvalue().splitlines():
        if line.strip().startswith(('@', 'skipped')):
            ctx.say('  ' + line.strip())


def overlay_fingerprint(ctx):
    rows = [(r['path'], r['sha256']) for r in ctx.manifest['files']
            if r['path'].startswith('mission-overlay/') or r['path'] == 'mission-patches.json']
    return sha256_bytes(json.dumps(sorted(rows)).encode())


def overlay_pack_dir(ctx):
    needed = overlays.DEFAULT_OVERLAY_IDS
    best = None
    for directory in ctx.dirs:
        have = [i for i in needed if (directory / i).is_dir()]
        if len(have) == len(needed):
            return directory, []
        if best is None or len(have) > len(best[1]):
            best = (directory, have)
    missing = [i for i in needed if best is None or i not in best[1]]
    return None, missing


def run_overlay(ctx, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        if argv[0] in ('bundle-apply', 'bundle-rollback'):
            with tree_writer(ctx, Path(argv[argv.index('--mission') + 1])):
                code = overlays.main(argv)
        else:
            code = overlays.main(argv)
    return code, out.getvalue(), err.getvalue()


def plan_overlay(ctx, a):
    if 'overlay' in ctx.skip:
        return 'skipped', ['you asked to skip this step'], None
    mission = ctx.server / 'mpmissions' / ctx.manifest['mission']
    if not mission.is_dir():
        return 'blocked', ['mission folder %s was not found; start the server once with the stock mission or '
                           'check the folder' % shown(mission)], None
    lines = ['mission: %s' % shown(mission)]
    installed = (mission / overlays.BUNDLE_MANAGED).exists()
    want = overlay_fingerprint(ctx)
    if installed and ctx.receipt.get('overlay') == want:
        lines.append('the bundle overlay is already applied (same bundle)')
        return 'already-done', lines, None
    pack_dir, missing = overlay_pack_dir(ctx)
    fetching = {i['id'] for i in a.fetch} if 'workshop' not in ctx.skip else set()
    missing = [m for m in missing if m not in fetching]
    if missing:
        return 'blocked', lines + ['these default Workshop packs are not downloaded: %s' % ', '.join(missing)], None
    if installed:
        lines.append('an overlay from an earlier bundle is applied; it is rolled back first (rollback restores the '
                     'files it changed), then the new bundle is planned and applied')
    else:
        code, text, err = run_overlay(ctx, ['bundle-plan', '--bundle', str(ctx.bundle), '--mission', str(mission)])
        if code != 0:
            return 'blocked', lines + ['bundle-plan refused: %s' % err.strip()], None
        shown_lines = [line for line in text.splitlines() if line.strip()]
        lines += shown_lines[:12]
        if len(shown_lines) > 12:
            lines.append('... and %d more overlay files' % (len(shown_lines) - 12))
        ctx.overlay_planned = True
    return 'planned', lines, lambda: do_overlay(ctx, a, mission, installed, want)


def do_overlay(ctx, a, mission, installed, want):
    track_target(ctx, mission.relative_to(ctx.server).as_posix(), tree=True)
    if installed and os.path.lexists(mission / map_overlay.MANAGED):
        # the map overlay patched the same cfggameplay.json; the mission rollback refuses while it is in place
        code, text, err = run_map(ctx, ['rollback', '--target', str(mission)])
        if code != 0:
            raise Refused('overlay', 'the map overlay must be rolled back before the mission overlay is replaced, and '
                          'its rollback was refused: %s' % err.strip())
    if installed:
        code, text, err = run_overlay(ctx, ['bundle-rollback', '--mission', str(mission)])
        if code != 0:
            raise Refused('overlay', 'bundle-rollback was refused: %s' % err.strip())
    pack_dir, missing = overlay_pack_dir(ctx)
    if pack_dir is None:
        raise Refused('overlay_packs_missing', 'these default Workshop packs are not downloaded: %s; run step 3 or '
                      'pass --workshop-content' % ', '.join(missing))
    if installed or not getattr(ctx, 'overlay_planned', False):
        code, text, err = run_overlay(ctx, ['bundle-plan', '--bundle', str(ctx.bundle), '--mission', str(mission)])
        if code != 0:
            raise Refused('overlay', 'bundle-plan refused: %s' % err.strip())
    code, text, err = run_overlay(ctx, ['bundle-apply', '--bundle', str(ctx.bundle), '--mission', str(mission),
                                        '--workshop-dir', str(pack_dir)])
    if code != 0:
        raise Refused('overlay', 'bundle-apply refused: %s' % err.strip())
    ctx.receipt['overlay'] = want
    save_receipt(ctx)
    return 'done'


def run_map(ctx, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        if argv[0] in ('install', 'rollback'):
            with tree_writer(ctx, Path(argv[argv.index('--target') + 1])):
                code = map_overlay.main(argv)
        else:
            code = map_overlay.main(argv)
    return code, out.getvalue(), err.getvalue()


def map_mission(ctx):
    return ctx.server / 'mpmissions' / ctx.manifest['mission']


def map_source(ctx):
    """The bundle's layer folder, or (None, reason). Every file in it must be one the manifest lists."""
    root = ctx.bundle / MAP_SOURCE
    listed = {rel for rel, _path in bundle_walk(ctx.bundle, ctx.manifest, MAP_SOURCE)}
    if 'config/map-overlays/profile.json' not in listed:
        return None, 'this bundle carries no map overlay layers; rebuild or download the bundle again'
    if not root.is_dir():
        return None, '%s is missing from the bundle folder' % MAP_SOURCE
    extra = sorted(p.relative_to(ctx.bundle).as_posix() for p in root.rglob('*')
                   if p.is_file() and p.relative_to(ctx.bundle).as_posix() not in listed)
    if extra:
        return None, 'files in %s are not listed in the bundle manifest: %s' % (MAP_SOURCE, ', '.join(extra[:4]))
    return root, ''


def map_state(ctx, mission, source):
    """('none' | 'same' | 'different' | 'damaged', detail) for the map overlay already in the mission folder.
    'same' means the receipt is intact and its outputs equal what the bundle's layer set composes to."""
    managed = mission / map_overlay.MANAGED
    if not os.path.lexists(managed):
        return 'none', ''
    try:
        if managed.is_symlink() or not managed.is_dir():
            raise ValueError('%s is not a plain folder' % map_overlay.MANAGED)
        receipt = json.loads((managed / 'receipt.json').read_text(encoding='utf-8'))
        if not isinstance(receipt, dict) or receipt.get('schema') != 1 or not isinstance(receipt.get('outputs'), dict):
            raise ValueError('receipt.json has an unknown layout')
        for key, name, backup in (('gameplay', 'cfggameplay.json', 'gameplay.backup'),
                                  ('mapgrouppos', 'mapgrouppos.xml', 'mapgrouppos.backup')):
            row = receipt.get(key)
            if not isinstance(row, dict) or not all(isinstance(row.get(k), str) for k in ('before', 'after')):
                raise ValueError('receipt.json has an unknown layout')
            if sha256_file(mission / name) != row['after']:
                raise ValueError('%s no longer matches the overlay receipt (edited by hand or by a later installer)' % name)
            if sha256_file(managed / backup) != row['before']:
                raise ValueError('%s in %s does not match the receipt' % (backup, map_overlay.MANAGED))
        for name, digest in receipt['outputs'].items():
            rel = Path(str(name))
            if rel.is_absolute() or '..' in rel.parts or sha256_file(managed / rel) != digest:
                raise ValueError('%s in %s does not match the receipt' % (name, map_overlay.MANAGED))
    except (OSError, ValueError, KeyError, TypeError) as error:
        return 'damaged', str(error) if isinstance(error, ValueError) else \
            'a file of the overlay cannot be read (%s)' % error.__class__.__name__
    try:
        wanted = {name: sha256_bytes(data) for name, data in map_overlay.compose(map_overlay.load_source(source)).items()}
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise Refused('overlays-map', 'the bundle layer set is not valid: %s' % shown(error))
    return ('same' if wanted == receipt['outputs'] else 'different'), ''


ROLLBACK_HINT = 'to remove the map overlay by hand: py -3 tools/package/map_overlay.py rollback --target %s'


def map_validate_args(ctx, source, mission, with_mission):
    argv = ['validate', '--source', str(source), '--server-root', str(ctx.server)]
    if with_mission:
        argv += ['--mission', str(mission)]
    return argv


def plan_overlays_map(ctx, a):
    if 'overlays-map' in ctx.skip:
        return 'skipped', ['you asked to skip this step'], None
    mission = map_mission(ctx)
    if not mission.is_dir():
        return 'blocked', ['mission folder %s was not found; the map overlays go into it' % shown(mission)], None
    source, reason = map_source(ctx)
    if source is None:
        return 'blocked', [reason], None
    lines = ['mission: %s' % shown(mission)]
    state, detail = map_state(ctx, mission, source)
    if state == 'damaged':
        return 'blocked', lines + ['the installed map overlay is damaged: %s' % detail, ROLLBACK_HINT % shown(mission),
                                   'nothing is installed or rolled back until that is sorted out'], None
    try:
        ids = [layer['id'] for layer in map_overlay.enabled_layers(map_overlay.load_source(source))]
    except (OSError, ValueError, KeyError, TypeError) as error:
        return 'blocked', lines + ['the bundle layer set is not valid: %s' % shown(error)], None
    lines.append('layers: %s' % ', '.join(ids))
    if state == 'same':
        lines.append('the map overlay is installed and intact (same layer set)')
        return 'already-done', lines, None
    present = all((mission / name).is_file() for name in map_overlay.INPUTS + ('mapgroupproto.xml',))
    waiting = ctx.statuses.get('overlay') == 'planned' and not present
    if state == 'different':
        lines.append('a map overlay from a different layer set is installed; it is rolled back first (byte-exact '
                     'restore of cfggameplay.json and mapgrouppos.xml), then the new layers are installed')
    lines.append('the server must be stopped; this changes cfggameplay.json and mapgrouppos.xml in the mission '
                 '(receipted; runtime acceptance stays pending)')
    # With an overlay in place the vanilla rows are not what is in the file; it is checked again after the rollback.
    code, text, err = run_map(ctx, map_validate_args(ctx, source, mission, present and state == 'none'))
    if code != 0:
        return 'blocked', lines + ['validate refused: %s' % err.strip()], None
    if waiting:
        lines.append('cfggameplay.json and mapgrouppos.xml appear after the mission overlay step is applied; the '
                     'layers are checked against them then')
    lines.append(ROLLBACK_HINT % shown(mission))
    return 'planned', lines, lambda: do_overlays_map(ctx, mission, source, state)


def do_overlays_map(ctx, mission, source, state):
    track_target(ctx, mission.relative_to(ctx.server).as_posix(), tree=True)
    if state == 'different':
        code, text, err = run_map(ctx, ['rollback', '--target', str(mission)])
        if code != 0:
            raise Refused('overlays-map', 'rollback of the earlier map overlay was refused: %s' % err.strip())
    present = all((mission / name).is_file() for name in map_overlay.INPUTS + ('mapgroupproto.xml',))
    if state == 'different':
        code, text, err = run_map(ctx, map_validate_args(ctx, source, mission, present))
        if code != 0:
            raise Refused('overlays-map', 'validate refused the new layers (the earlier overlay is already rolled '
                          'back): %s' % err.strip())
    code, text, err = run_map(ctx, ['install', '--source', str(source), '--target', str(mission)])
    if code != 0:
        raise Refused('overlays-map', 'map_overlay install refused: %s' % err.strip())
    ctx.say('  ' + text.strip().splitlines()[-1] if text.strip() else '  map overlay installed')
    return 'done'


# HCHoldoutState.Version and OnStart's Version check in
# mods/HollowCountry/scripts/4_World/World/HCHoldouts.c (159, 261).
# HCAICampLifecycle.c in that directory defines schema 2's finite funding pool.
# Keep this in the installer: exported bundles contain PBOs, not script sources.
FUNDED_HOLDOUT_VERSION = 3
# Schema 1 had free occupants; schema 2 had the finite founding pool without the
# HC-16 reserve refund/regeneration fields, which schema 3 refuses (STATE_INVALID).
LEGACY_HOLDOUT_SCHEMAS = {1: 'legacy schema 1 (unfunded)', 2: 'legacy schema 2 (funded, before camp reserves)'}
HOLDOUT_PATH = 'profiles/HollowCountry/holdouts.json'


def inspect_holdouts(ctx):
    """Classify the schema only; native canonical-image and resource checks remain pending."""
    ws.check_no_symlink_below(ctx.server, HOLDOUT_PATH)
    target = ctx.server / HOLDOUT_PATH
    if not target.exists():
        return 'absent', []
    if not target.is_file():
        raise Refused('holdouts_conflict', '%s is not a regular file' % HOLDOUT_PATH)
    try:
        data = json.loads(target.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError):
        state = 'invalid JSON'
    else:
        version = data.get('Version') if isinstance(data, dict) else None
        if type(version) is int and version == FUNDED_HOLDOUT_VERSION:
            # HCHoldouts treats an image without CampPolicy as unfunded legacy state.
            if not isinstance(data.get('CampPolicy'), dict):
                return 'unsupported holdouts schema', []
            return 'funded', []
        if type(version) is not int or version not in LEGACY_HOLDOUT_SCHEMAS:
            return 'unsupported holdouts schema', []
        state = LEGACY_HOLDOUT_SCHEMAS[version]
    moves = []
    for suffix in ('', '.bak', '.tmp'):
        rel = HOLDOUT_PATH + suffix
        ws.check_no_symlink_below(ctx.server, rel)
        path = ctx.server / rel
        if path.exists():
            if not path.is_file():
                raise Refused('holdouts_conflict', '%s is not a regular file' % rel)
            moves.append(rel)
    return state, moves


HC_ADMINS_PATH = 'profiles/HollowCountry/admins.json'
COT_PLAYERS_DIR = 'profiles/PermissionsFramework/Players'
COT_EXAMPLE = COT_PLAYERS_DIR + '/Your_Steam64_ID.json'
STEAM64 = re.compile(r'[0-9]{17}')


def _read_json_object(ctx, rel):
    """The parsed JSON object at a server-relative path, None when absent, False when unreadable or not an object."""
    ws.check_no_symlink_below(ctx.server, rel)
    path = ctx.server / rel
    if not path.is_file():
        return None if not path.exists() else False
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return False
    return data if isinstance(data, dict) else False


def cot_admin_records(ctx):
    """(rows, kept): one (rel, bytes or None, action) per valid HC admin id, plus the count left untouched.

    The ids come only from the server's live admins.json and are never shown. An existing COT player file keeps
    every other field and role; a new one follows COT's own Your_Steam64_ID.json example when it is there.
    """
    try:
        admins = _read_json_object(ctx, HC_ADMINS_PATH)
        ids = admins.get('PlainIds') if admins else None
        if not isinstance(ids, list):
            return [], 0
        example = _read_json_object(ctx, COT_EXAMPLE)
    except (Refused, ws.SyncError, OSError):
        return [], 0
    wanted = []
    for value in ids:
        if isinstance(value, str) and STEAM64.fullmatch(value.strip()) and value.strip() not in wanted:
            wanted.append(value.strip())
    rows, kept = [], 0
    for steam in wanted:
        rel = '%s/%s.json' % (COT_PLAYERS_DIR, steam)
        try:
            record = _read_json_object(ctx, rel)
        except (Refused, ws.SyncError, OSError):
            kept += 1
            continue
        if record is False or (record is not None and not isinstance(record.get('Roles', []), list)):
            kept += 1  # unreadable or unexpected shape: never overwrite it
            continue
        if record is None:
            record = dict(example) if example else {}
            record['Roles'] = ['admin']
            action = 'created'
        elif 'admin' in record.get('Roles', []):
            rows.append((rel, None, 'same'))
            continue
        else:
            record['Roles'] = list(record.get('Roles', [])) + ['admin']
            action = 'updated'
        rows.append((rel, (json.dumps(record, indent=4) + '\n').encode('utf-8'), action))
    return rows, kept


def cot_lines(a):
    rows, kept = a.cot
    if not rows and not kept:
        return []
    counts = {}
    for _rel, _data, action in rows:
        counts[action] = counts.get(action, 0) + 1
    parts = ['%d %s' % (counts[k], k) for k in ('created', 'updated', 'same') if k in counts]
    if kept:
        parts.append('%d kept (unreadable or unexpected COT record; not overwritten)' % kept)
    total = len(rows) + kept
    return ['COT admin record for %d HC admin%s (%s)' % (total, '' if total == 1 else 's',
                                                       ', '.join(p.replace(' same', ' already admin') for p in parts))]


def do_cot_admins(ctx):
    # Recompute so a confirmation prompt that waited never writes over an edit made meanwhile.
    for rel, data, _action in cot_admin_records(ctx)[0]:
        if data is None:
            continue
        target = ctx.server / rel
        record_written(ctx, rel, sha256_bytes(data))
        target.parent.mkdir(parents=True, exist_ok=True)
        ws.write_bytes_atomic(target, data)


def plan_profiles(ctx, a):
    if 'profiles' in ctx.skip:
        return 'skipped', ['you asked to skip this step'], None
    counts = count_actions(a.profiles)
    kept = [r for r in a.profiles if r[2] == 'drift']
    lines = ['profile files from the bundle: %s' % describe({k: v for k, v in counts.items() if k != 'drift'})]
    for rel, _s, _a, _h in kept:
        lines.append('WARN  profile_defaults  ' + profile_warning(rel))
    if a.holdouts_moves:
        lines.append('holdouts: %s; preserve the old image so the mod can start fresh' % a.holdouts_state)
        for rel in a.holdouts_moves:
            lines.append('move to the backup folder: ' + rel)
    elif a.holdouts_state == 'unsupported holdouts schema':
        lines.append('unsupported holdouts schema; kept %s; inspect before starting the server' % HOLDOUT_PATH)
    for rel, _s, action, _h in a.profiles:
        if action == 'merge':
            lines.append('merge the Hollow Country keys into %s (other Expansion fields kept, backup first)' % rel)
        elif action == 'new' and rel in MERGE_PROFILES:
            lines.append('WARN  profile_defaults  %s is partial; start the server once so Expansion writes the full '
                         'file, stop it, then run --apply again to merge the keys' % rel)
    lines += cot_lines(a)
    todo = [r for r in a.profiles if r[2] in ('new', 'upgrade', 'confirm', 'merge')]
    if not todo and not a.holdouts_moves and not any(r[1] is not None for r in a.cot[0]):
        return 'already-done', lines, None
    return 'planned', lines, lambda: do_profiles(ctx, a)


def do_profiles(ctx, a):
    for rel in a.holdouts_moves:
        target = ctx.server / rel
        # Existing write-ahead mechanism copies exact bytes into this run's
        # backup and journals the absent live target before removing it.
        record_written(ctx, rel, None)
        target.unlink()
        ws.fsync_parent(target)
        moved = ctx.receipt.setdefault('holdouts_moved', [])
        if rel not in moved:
            moved.append(rel)
        ctx.receipt['files'].pop(rel, None)
    do_cot_admins(ctx)
    return do_files(ctx, a.profiles)


def do_files(ctx, rows):
    for rel, source, action, sha in rows:
        if action == 'drift':
            continue
        if action == 'merge':
            target = ctx.server / rel
            data, _changed = merged_profile(target, source)
            sha = sha256_bytes(data)
            record_written(ctx, rel, sha)
            ws.write_bytes_atomic(target, data)
        elif action != 'same':
            write_file(ctx, rel, source, action)
        if rel.startswith('profiles/'):
            hashes = ctx.receipt.setdefault('profile_defaults', {}).setdefault(rel, [])
            previous = ctx.receipt['files'].get(rel)
            if previous and previous not in hashes:
                hashes.append(previous)
            if sha not in hashes:
                hashes.append(sha)
        ctx.receipt['files'][rel] = sha
    save_receipt(ctx)
    return 'done'


def plan_cfg(ctx, a):
    if 'cfg' in ctx.skip:
        return 'skipped', ['you asked to skip this step'], None
    if 'error' in a.cfg:
        return 'blocked', [a.cfg['error']], None
    lines = []
    for change in a.cfg['changes']:
        if change['action'] == 'unchanged':
            lines.append('%s already %s' % (change['key'], change['new']))
        elif change['action'] == 'replaced':
            lines.append('%s: %s -> %s' % (change['key'], change['old'], change['new']))
        else:
            lines.append('%s: add %s' % (change['key'], change['new']))
    lines.append('everything else in serverDZ.cfg (passwords, hostname, BattlEye, signatures) is left byte-identical')
    if not a.cfg['todo']:
        return 'already-done', lines, None
    return 'planned', lines, lambda: do_cfg(ctx, a)


def do_cfg(ctx, a):
    cfg = a.cfg
    # The prompt before this step can wait for minutes; never write over an edit made meanwhile.
    try:
        current = cfg['path'].read_bytes()
    except OSError:
        current = None
    if current != cfg['raw']:
        raise Refused('drift', 'serverDZ.cfg changed while this run was waiting; nothing was written to it. Run the '
                      'installer again so it merges into the file as it is now')
    data = cfg['new'].encode('utf-8')
    record_written(ctx, 'serverDZ.cfg', sha256_bytes(data))
    ws.write_bytes_atomic(cfg['path'], data)
    return 'done'


def plan_launcher(ctx, a):
    if 'launcher' in ctx.skip:
        return 'skipped', ['you asked to skip this step'], None
    rel, source, action, sha = a.launcher
    lines = ['start-server.bat from the bundle: %s' % action]
    lines += ['  ' + line for line in ws.launch_lines(ctx.items) if line.startswith('-mod=')]
    if action == 'same':
        ctx.receipt['files'].setdefault(rel, sha)
        return 'already-done', lines, None
    return 'planned', lines, lambda: do_files(ctx, [a.launcher])


CHECKLIST = (
    'Start the server with start-server.bat. Your own serverDZ.cfg stays yours: keep verifySignatures = 2 and BattlEye on.',
    'Forward ports 2302-2305 UDP (game) and 27016 UDP (Steam query) to this PC.',
    'Players subscribe to the Hollow Country Workshop item (and the Expansion AI add-on if this server uses it) and '
    'join from the server browser.',
    'Admin tools (COT) permissions live in the server profile; see docs/COT_PERMISSIONS.md in the bundle.',
    'Verify any time: install-hollow-country.bat --check (read only).',
    'After a play session: run server-report.bat and upload the file it writes (see the README in the bundle).',
)


def plan_checklist(ctx, a):
    return 'ok', ['%d. %s' % (n, text) for n, text in enumerate(CHECKLIST, 1)], None


PLANNERS = {'server': plan_server, 'stopped': plan_stopped, 'workshop': plan_workshop, 'mods': plan_mods,
            'overlay': plan_overlay, 'overlays-map': plan_overlays_map, 'profiles': plan_profiles, 'cfg': plan_cfg, 'launcher': plan_launcher,
            'checklist': plan_checklist}


# ---------------------------------------------------------------------------------------------------------
# Server folder, check mode, main flow

def resolve_server(ctx):
    args = ctx.args
    raw = args.server_root
    if not raw:
        remembered = ''
        try:
            remembered = (ctx.bundle / REMEMBER_FILE).read_text(encoding='utf-8').strip()
        except OSError:
            pass
        typed = ctx.ask('DayZ server folder (the one holding %s)%s: ' % (
            SERVER_EXE, ' [%s]' % shown(remembered) if remembered else ''))
        if typed is None:
            if remembered:
                raw = remembered
            else:
                raise Refused('server_root', 'no server folder given; pass --server-root <folder holding %s>' % SERVER_EXE)
        else:
            raw = typed.strip().strip('"') or remembered
            if not raw:
                raise Refused('server_root', 'no server folder given')
    server = Path(raw).expanduser()
    if not server.is_dir():
        raise Refused('server_root', '%s is not a folder' % shown(server))
    if not (server / SERVER_EXE).is_file():
        raise Refused('server_root', '%s does not contain %s; point at the folder that does' % (shown(server), SERVER_EXE))
    if server.resolve() == ctx.bundle.resolve() or (server / BUNDLE_MANIFEST).exists():
        raise Refused('server_root', '%s is the bundle folder, not the DayZ server folder' % shown(server))
    return server


def remember_text(path, text):
    try:
        if path.exists() and path.read_text(encoding='utf-8') == text:
            return
        path.write_text(text, encoding='utf-8')
    except OSError:
        pass


def remember(ctx):
    remember_text(ctx.bundle / REMEMBER_FILE, str(ctx.server) + '\n')
    if ctx.steamcmd is not None and ctx.steamcmd_from in ('option', 'typed'):
        remember_text(ctx.bundle / REMEMBER_STEAMCMD, str(ctx.steamcmd) + '\n')


def run_check(ctx):
    server = ctx.server
    say = ctx.say
    bat = (ctx.bundle / 'start-server.bat').read_text(encoding='utf-8', errors='replace')
    expected = parse_mod_list(bat)
    manifest = ws.load_manifest()
    by_folder = {m['folder']: m for m in manifest['mods']}
    results = []

    def result(name, problems, good):
        results.append(not problems)
        say('%s  %s  %s' % ('FAIL' if problems else 'PASS', name, '; '.join(problems) if problems else good))

    say('Check of %s against the bundle (read only)' % shown(server))
    missing = []
    for folder in expected:
        addons = server / folder / 'addons'
        if not addons.is_dir() or not any(p.suffix.lower() == '.pbo' for p in addons.iterdir()):
            missing.append('missing_mod_folder: %s' % folder)
    result('mod_folders', missing, '%d mod folders present with signed PBOs' % len(expected))
    names = set(p.name for p in (ctx.bundle / 'keys').glob('*.bikey')) if (ctx.bundle / 'keys').is_dir() else set()
    for folder in expected:
        keys = server / folder / 'keys'
        if keys.is_dir():
            names |= {p.name for p in keys.glob('*.bikey')}
    absent = sorted(n for n in names if not (server / 'keys' / n).is_file())
    result('bikeys', ['missing_bikey: %s' % n for n in absent], '%d keys present in keys/' % len(names))
    problems = []
    for folder in expected:
        item = by_folder.get(folder)
        if not item or not item['id'] or not (server / folder).is_dir():
            continue
        meta = server / folder / 'meta.cpp'
        if not meta.is_file():
            problems.append('missing_meta_cpp: %s' % folder)
            continue
        found = re.search(r'publishedid\s*=\s*(\d+)', meta.read_text(encoding='utf-8', errors='replace'))
        if not found or found.group(1) != item['id']:
            problems.append('wrong_publishedid: %s' % folder)
    result('meta_ids', problems, 'meta.cpp publishedid matches for every Workshop mod')
    live = server / 'start-server.bat'
    if not live.is_file():
        result('mod_order', ['missing_start_server: start-server.bat not found'], '')
    else:
        actual = parse_mod_list(live.read_text(encoding='utf-8', errors='replace'))
        if actual != expected:
            diff = next((i for i, (x, y) in enumerate(zip(actual, expected)) if x != y), min(len(actual), len(expected)))
            result('mod_order', ['wrong_mod_order: differs from the bundle at position %d' % (diff + 1)], '')
        else:
            result('mod_order', [], '-mod order matches the bundle (%d mods)' % len(expected))
    cfg = server / 'serverDZ.cfg'
    if not cfg.is_file():
        result('verify_signatures', ['missing_server_cfg: serverDZ.cfg not found'], '')
    else:
        value = cfg_values(cfg.read_text(encoding='utf-8', errors='replace'), ['verifySignatures']).get('verifySignatures')
        result('verify_signatures', [] if value is not None and value.strip() == '2' else
               ['verify_signatures_off: verifySignatures should be 2'], 'verifySignatures = 2')
    holdouts_state, _moves = inspect_holdouts(ctx)
    result('holdouts', [] if holdouts_state in ('absent', 'funded') else
           ['%s: %s; run the profiles step for legacy/invalid JSON, inspect other schemas by hand'
            % (holdouts_state, HOLDOUT_PATH)],
           'absent (fresh state allowed)' if holdouts_state == 'absent' else
           'funded schema %d present; runtime acceptance pending' % FUNDED_HOLDOUT_VERSION)
    if 'profiles' not in ctx.skip:
        profile_problems = []
        for rel, source in bundle_walk(ctx.bundle, ctx.manifest, 'profiles'):
            action, _digest = classify_profile(ctx, rel, source)
            if action == 'drift':
                say('WARN  profile_defaults  ' + profile_warning(rel))
            elif action != 'same':
                profile_problems.append('%s: run the profiles step to install the current default' % rel)
        result('profile_defaults', profile_problems, 'shipped defaults checked; kept custom files are listed as WARN')
    if 'overlays-map' not in ctx.skip:
        mission = map_mission(ctx)
        source, reason = map_source(ctx)
        if not mission.is_dir():
            result('map_overlays', ['missing_mission: %s was not found' % shown(mission)], '')
        elif source is None:
            result('map_overlays', ['missing_map_source: %s' % reason], '')
        else:
            state, detail = map_state(ctx, mission, source)
            if state == 'none':
                result('map_overlays', ['missing_map_overlay: no receipt in %s; run the installer' % map_overlay.MANAGED], '')
            elif state == 'damaged':
                result('map_overlays', ['damaged_map_overlay: %s' % detail], '')
            elif state == 'different':
                result('map_overlays', ['outdated_map_overlay: installed layers differ from this bundle; run the installer'], '')
            else:
                result('map_overlays', [], 'overlay receipt present and intact, layers match this bundle')
    say('check result: %s' % ('pass' if all(results) else 'fail'))
    return 0 if all(results) else 1


def resolve_steamcmd(ctx):
    """A download needs a steamcmd program: from the option, the last run, PATH, or typed here. Raises if none."""
    if ctx.steamcmd_bad:
        raise Refused('steamcmd_required', '--steamcmd %s is not a steamcmd program or a folder holding steamcmd.exe'
                      % shown(ctx.steamcmd_bad))
    if ctx.steamcmd is None:
        typed = ctx.ask('Path to steamcmd (steamcmd.exe, or the folder that holds it): ')
        if typed is None:
            raise Refused('steamcmd_required', 'steamcmd was not found on PATH; install it and pass --steamcmd '
                          '<path to steamcmd.exe>')
        found = steamcmd_exe(typed) if typed.strip() else None
        if found is None:
            raise Refused('steamcmd_required', 'that is not a steamcmd program or a folder holding steamcmd.exe; '
                          'install steamcmd first (https://developer.valvesoftware.com/wiki/SteamCMD)')
        ctx.steamcmd, ctx.steamcmd_from = found, 'typed'
    ctx.dirs = content_dirs(ctx, ctx.server)


def require_stopped(ctx, running):
    args = ctx.args
    if running:
        raise Refused('server_running', 'a DayZ server process is running; stop it yourself first (this tool never '
                      'stops anything)')
    if running is None and not args.assume_stopped:
        answer = ctx.ask('The process list cannot be read. Type yes only if the DayZ server is stopped: ')
        if (answer or '').strip().lower() != 'yes':
            raise Refused('server_state_unknown', 'cannot tell whether the DayZ server is running; stop it and pass '
                          '--assume-stopped')


def pre_apply(ctx, a):
    """Every refusal that can be known before the first write."""
    args = ctx.args
    require_stopped(ctx, a.running)
    if 'workshop' not in ctx.skip and a.fetch:
        resolve_steamcmd(ctx)
        if not ctx.steam_user:
            typed = ctx.ask('Steam login name to download with (type your login name only; steamcmd asks for the '
                            'password itself, never type it here): ')
            if typed is None or not typed.strip():
                raise Refused('steam_user_required', 'the Workshop download needs your Steam login name: pass '
                              '--steam-user <name> (steamcmd then asks for the password itself)')
            ctx.steam_user = typed.strip()
        if not ws.STEAM_USER.match(ctx.steam_user):
            raise Refused('steam_user_invalid', 'that is not a Steam login name (type your login name only: no spaces; '
                          'steamcmd asks for the password itself). What you typed is not shown or kept')
    if 'workshop' not in ctx.skip:
        fetching = {i['id'] for i in a.fetch}
        missing = ['%s %s' % (t['item']['folder'], t['item']['id']) for t in a.pending
                   if t['content'] != 'present' and t['item']['id'] not in fetching]
        if missing:
            raise Refused('workshop_missing', 'these dependencies are not downloaded: %s; run step 3 (do not skip it) '
                          'or pass --workshop-content <steamapps/workshop/content/221100>' % ', '.join(missing))
    drift = [r[0] for r in a.own if r[2] == 'drift']
    if a.launcher and a.launcher[2] == 'drift':
        drift.append(a.launcher[0])
    if drift:
        raise Refused('drift', 'changed since this installer wrote them: %s; restore or move them away, then run again'
                      % ', '.join(drift[:8]))
    confirm = [r[0] for r in a.own + a.profiles if r[2] == 'confirm']
    if a.launcher and a.launcher[2] == 'confirm':
        confirm.append(a.launcher[0])
    if 'overlay' not in ctx.skip:
        mission = ctx.server / 'mpmissions' / ctx.manifest['mission']
        if mission.is_dir() and (mission / overlays.BUNDLE_MANAGED).exists() and \
                ctx.receipt.get('overlay') != overlay_fingerprint(ctx):
            confirm.append('mission overlay from an earlier bundle (rolled back first)')
            if os.path.lexists(mission / map_overlay.MANAGED):
                confirm.append('map overlay (rolled back first, because the mission overlay it sits on is replaced)')
    if 'overlays-map' not in ctx.skip and not any(c.startswith('map overlay') for c in confirm):
        mission = map_mission(ctx)
        source = map_source(ctx)[0]
        if mission.is_dir() and source is not None and map_state(ctx, mission, source)[0] == 'different':
            confirm.append('map overlay from a different layer set (rolled back first)')
    if confirm and not args.yes:
        answer = ctx.ask('%d existing file(s) differ from the bundle and are backed up first: %s. Replace them? [y/N]: '
                         % (len(confirm), ', '.join(confirm[:6])))
        if (answer or '').strip().lower() not in ('y', 'yes'):
            raise Refused('confirmation_required', 'existing files differ from the bundle: %s; read the list and pass '
                          '--yes to replace them (each is copied to %s first)' % (', '.join(confirm[:8]), BACKUP_DIR))


def run_steps(ctx, apply):
    a = analyze(ctx)
    ctx.say('Mode: %s' % ('apply (changes are backed up and recorded)' if apply else 'dry-run (nothing is changed)'))
    ctx.say('Server: %s' % shown(ctx.server))
    ctx.say('Bundle: %s' % shown(ctx.bundle))
    ctx.say()
    if apply:
        pre_apply(ctx, a)
    blocked = False
    stopped = False
    ctx.statuses = {}
    for number, name in enumerate(STEPS, 1):
        ctx.say('Step %d of %d: %s' % (number, len(STEPS), TITLES[name]))
        status, lines, action = PLANNERS[name](ctx, a)
        if name == 'stopped' and status in ('blocked', 'unknown'):
            blocked = True
        if status == 'blocked' and apply:
            raise Refused(name, '; '.join(lines))
        if status == 'blocked':
            blocked = True
        if apply and action is not None and status == 'planned' and not ctx.args.yes and ctx.input_fn is not None:
            answer = (ctx.ask('%s: do this step? [y]es / [s]kip / [q]uit: ' % TITLES[name]) or 'y').strip().lower()
            if answer.startswith('q'):
                stopped = True
            elif answer.startswith('s'):
                status, action = 'skipped', None
                lines = lines + ['skipped at your request']
        if stopped:
            ctx.say('  status: stopped (you quit; later steps were not run)')
            break
        if apply and action is not None and status == 'planned':
            result = action()
            status = result or 'done'
        ctx.statuses[name] = status
        ctx.say('  status: %s' % status)
        for line in lines:
            ctx.say('  ' + line)
        ctx.say()
    if apply:
        if ctx.journal is not None:
            data = dict(ctx.journal, state='complete')
            ws.write_json_atomic(journal_path(ctx.backup_root), data)
            ctx.journal = data
        remember(ctx)
    return blocked


def build_parser():
    parser = ws.QuietParser(prog='friend_install', description=__doc__.split('\n\n')[0], allow_abbrev=False)
    parser.add_argument('--server-root', help='the DayZ server folder (holds DayZServer_x64.exe)')
    parser.add_argument('--bundle', default=str(BUNDLE_ROOT), help='the unzipped bundle (default: where this runs)')
    parser.add_argument('--apply', action='store_true', help='make the changes (default is a dry run)')
    parser.add_argument('--yes', action='store_true', help='do not ask before replacing existing files (each is backed up)')
    parser.add_argument('--check', action='store_true', help='only verify an existing install; changes nothing')
    parser.add_argument('--plan-only', action='store_true', help='dry run without offering to apply')
    parser.add_argument('--skip', default='', help='comma list of steps to skip: ' + ', '.join(SKIPPABLE))
    parser.add_argument('--adopt-profile', action='append', default=[], metavar='profiles/<file>',
                        help='adopt this exact shipped default even when hand-edited (backup first; repeatable)')
    parser.add_argument('--assume-stopped', action='store_true', help='skip the running-server check')
    parser.add_argument('--workshop-content', action='append', default=[],
                        help='a steamapps/workshop/content/221100 folder (repeatable)')
    parser.add_argument('--steamcmd', help='path to steamcmd (its folder is searched for downloads)')
    parser.add_argument('--steam-user', help='your Steam login name (steamcmd asks for the password itself)')
    return parser


def main(argv=None, out=None, input_fn=None):
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    if input_fn is None and sys.stdin is not None and sys.stdin.isatty() and argv is None:
        input_fn = input
    ctx = Ctx(args, out, input_fn)
    try:
        skip = {s.strip() for s in args.skip.split(',') if s.strip()}
        unknown = sorted(skip - set(SKIPPABLE))
        if unknown:
            raise Refused('bad_skip', 'unknown step name(s): %s; choose from %s' % (', '.join(unknown), ', '.join(SKIPPABLE)))
        ctx.skip = skip
        ctx.manifest = load_bundle(ctx.bundle)
        ctx.server = resolve_server(ctx)
        runs = pending_runs(ctx)
        if runs:
            if args.check:
                for root, data in runs:
                    ctx.say(describe_pending(ctx, root, data))
                ctx.say('check result: fail')
                return 1
            if args.apply:
                recover_runs(ctx, runs)
            else:
                raise Refused('install_interrupted', '\n'.join(describe_pending(ctx, root, data)
                                                           for root, data in runs))
        ctx.receipt = load_receipt(ctx.server)
        if args.check:
            analyze_items(ctx)
            return run_check(ctx)
        apply = args.apply
        blocked = run_steps(ctx, apply)
        if not apply:
            ctx.say('This was a dry run: nothing was changed. Run again with --apply to install.')
            if not blocked and not args.plan_only and ctx.input_fn is not None:
                answer = ctx.ask('Apply these changes now? [y/N]: ')
                if (answer or '').strip().lower() in ('y', 'yes'):
                    ctx.receipt = load_receipt(ctx.server)
                    run_steps(ctx, True)
                    ctx.say('Install finished. Nothing here was observed in DayZ; run --check any time.')
        else:
            ctx.say('Install finished. Nothing here was observed in DayZ; run --check any time.')
        return 0
    except (Refused, ws.SyncError, OSError, ValueError) as error:
        print('refused: %s: %s' % (getattr(error, 'code', 'error'), shown(error)), file=sys.stderr)
        if ctx.journal is not None and ctx.journal['state'] in ('active', 'rolling-back'):
            try:
                rollback_run(ctx, ctx.backup_root, ctx.journal)
            except (OSError, ValueError, ws.SyncError) as undo_error:
                print('rollback stopped: %s\n%s' %
                      (shown(undo_error), describe_pending(ctx, ctx.backup_root, ctx.journal)), file=sys.stderr)
            else:
                print(ROLLBACK_OK, file=sys.stderr)
        return 2


def analyze_items(ctx):
    manifest = ws.load_manifest()
    ctx.items = ws.select(manifest, list(ws.GROUPS))


if __name__ == '__main__':
    sys.exit(main())
