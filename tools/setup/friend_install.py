"""Guided Hollow Country install for a friend's Windows dedicated server (standard library only).

Run it from the unzipped bundle (install-hollow-country.bat does exactly this):

    python -m tools.setup.friend_install [--server-root <DayZ server folder>] [--apply] [--check] [--repair]
    python -m tools.setup.friend_install --rollback <run>

It walks eleven steps in order. Each says what it found and what it would do, and each is skipped on its
own when it is already done:

  1 server folder                    7 optional Workshop weapon CE layers
  2 stopped-server check             8 profiles
  3 Workshop dependencies            9 serverDZ.cfg
  4 mod folders and keys            10 start-server.bat
  5 mission overlay                 11 final checklist
  6 map overlays

Infected placement uses the persisted profile season at install/upgrade time. Winter medics
follow the season of the last upgrade; a changed season repairs the receipted layer automatically.

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
* Self-healing: a dry run and --check list a "Repair preview" (missing or edited managed files, retired files
  left behind, a partial earlier install, operator db/globals.xml values to carry forward). --apply --repair
  does exactly those repairs, copies every replaced file to the backup folder first and ends with a "Repair
  receipt" (also stored in the install receipt under "repairs"). Files the installer does not manage and the
  world saves are never deleted. Operator db/globals.xml values survive an upgrade: the keys the operator
  changed are re-applied on top of the new loot boost; the file is only left alone (and the run refuses)
  when the receipt and backup cannot prove what the installer wrote.
  An operator-edited start-server.bat is merged, never replaced (also under --yes, recorded or not): the -mod=
  and -serverMod= lists become the bundle's folders in bundle order, then every operator entry the installer
  does not manage; retired folders are removed; a launcher that cannot be merged is a refusal with a reason.
  A hard exit inside a mission writer is journaled; --repair (or a typed y at "repair these (each backed up)?
  [y/N]", which allows that tree restore only and never turns on --repair) restores the whole mission tree from
  that run's backup after a complete copy of the cut-off tree is kept as hard-exit-partial-<run id>.
  --keep-stock-globals records db/globals.xml variables the operator put back at stock as an opt-out.
* --rollback <run> restores the files of one earlier run from its backup folder; it refuses files edited
  since that run, keeps run-created folders the server has written into, and finishes an interrupted
  rollback of that run without installing anything.
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

from tools.package import loot_boost, hc_events, map_overlay, infected_variety, snafu_optional, tactical_flava_optional
from tools.package import ce_slot_pressure, xml_text
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
STEPS = ('server', 'stopped', 'workshop', 'mods', 'overlay', 'overlays-map', 'weapons', 'profiles', 'cfg', 'launcher', 'checklist')
SKIPPABLE = ('workshop', 'mods', 'overlay', 'overlays-map', 'weapons', 'profiles', 'cfg', 'launcher')
TITLES = {
    'server': 'Check the server folder',
    'stopped': 'Check the server is stopped',
    'workshop': 'Workshop dependencies',
    'mods': 'Copy mod folders and keys',
    'overlay': 'Mission overlay (bundle-plan, then bundle-apply)',
    'weapons': 'Optional Workshop weapon CE layers',
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


def normalize_profile(data):
    """Only transport differences: retain whitespace and real operator edits."""
    return data.removeprefix(b'\xef\xbb\xbf').replace(b'\r\n', b'\n')


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


def live_mod_list(text):
    """The -mod= entries of a live launcher (whole tokens, comment lines skipped); [] when there are none or the
    line cannot be read."""
    delayed = delayed_expansion(text)
    for line in text.splitlines():
        if _launcher_comment(line):
            continue
        try:
            for name, start, end, _quoted in launcher_args(line, delayed):
                if name == 'mod':
                    return launcher_entries(line[start:end])
        except Unmergeable:
            return []
    return []


LAUNCHER_REL = 'start-server.bat'
LAUNCHER_FLAG = re.compile(r'(?i)(?<![\w-])-(mod|serverMod)=')
LAUNCHER_STOP = re.compile(r'[\s"]')


class Unmergeable(Exception):
    """The operator's launcher cannot be edited safely; the message says why."""


def _launcher_comment(line):
    word = line.strip().lower().lstrip('@').lstrip()
    return word.startswith('::') or word == 'rem' or word.startswith(('rem ', 'rem\t'))


DELAYED_EXPANSION = re.compile(r'(?i)\bsetlocal\b[^\r\n]*\benabledelayedexpansion\b')


def delayed_expansion(text):
    """True when the launcher turns batch delayed expansion on (setlocal EnableDelayedExpansion on a line that is not
    a comment); only then is ! in a value an expansion marker instead of a literal character."""
    return any(DELAYED_EXPANSION.search(line) for line in text.splitlines() if not _launcher_comment(line))


def launcher_args(line, delayed=False):
    """[(name lower, value start, value end, quoted)] for the -mod= and -serverMod= arguments of one launcher line.
    Whole tokens: a value inside quotes ("-mod=@A;@B C" or -mod="@A;@B C") runs to the closing quote and may hold
    spaces; an unquoted value runs to the next whitespace. delayed says the file enables delayed expansion, which
    makes ! in a value unreadable (without it ! is a literal character)."""
    found, pos = [], 0
    while True:
        match = LAUNCHER_FLAG.search(line, pos)
        if match is None:
            return found
        start = match.end()
        if line.startswith('"', start):
            quoted, start = True, start + 1
        else:
            quoted = line[:match.start()].endswith('"')
        if quoted:
            end = line.find('"', start)
            if end < 0:
                raise Unmergeable('has a -%s= value with no closing quote' % match.group(1))
        else:
            stop = LAUNCHER_STOP.search(line, start)
            end = stop.start() if stop else len(line)
        value = line[start:end]
        if '%' in value:
            raise Unmergeable('has a -%s= value built from a batch variable (%%...%%)' % match.group(1))
        if delayed and '!' in value:
            raise Unmergeable('has a -%s= value with ! in it (batch delayed expansion !...!)' % match.group(1))
        if '^' in value:
            raise Unmergeable('has a -%s= value with the batch escape character ^ in it' % match.group(1))
        found.append((match.group(1).lower(), start, end, quoted))
        pos = end


def launcher_entries(value):
    return [entry.strip() for entry in value.split(';') if entry.strip()]


def mod_leaf(entry):
    """The folder name of a -mod= entry: the last path component, whatever the slash, a leading .\\ or a drive."""
    text = entry.strip().replace('\\', '/').rstrip('/')
    return text.rsplit('/', 1)[-1].rsplit(':', 1)[-1]


def merge_values(operator, bundle, retired, managed=(), unowned=(), present=None):
    """The merged list: the bundle's folders in bundle order, then every operator entry this installer does not
    manage in the operator's own order. Entries are compared by their last path component, ignoring case and slash
    style: a path-form entry of a bundle folder (C:\\mods\\@CF, .\\@CF) is replaced by the bundle's own form.
    Dropped from the operator's list: retired folders the installer is removing (retired), and folders the bundle
    lists in the other argument (managed: all bundle folders of both lists; they move to their own list). A retired
    folder the installer did not install (unowned) stays as the operator's own entry and is reported. present, when
    given, is the set of casefolded folder names that exist in the server root or that this run installs: a path-form
    entry of a bundle folder outside it keeps the operator's own form in the bundle slot (the bundle's short form
    would name a folder the server does not have). Returns a dict: merged, added, removed, kept, moved, replaced
    (old, new) pairs, unowned."""
    retired_keys = {mod_leaf(name).casefold() for name in retired}
    unowned_keys = {mod_leaf(name).casefold() for name in unowned}
    bundle_keys = {mod_leaf(name).casefold() for name in bundle}
    other_keys = {mod_leaf(name).casefold() for name in managed} - bundle_keys
    slots = {}
    for entry in operator:
        key = mod_leaf(entry).casefold()
        if key in bundle_keys and entry != mod_leaf(entry) and present is not None and key not in present:
            slots.setdefault(key, entry)
    merged, seen = [], set()
    for name in bundle:
        entry = slots.get(mod_leaf(name).casefold(), name)
        if entry.casefold() not in seen:
            seen.add(entry.casefold())
            merged.append(entry)
    removed, kept, moved, replaced, warned = [], [], [], [], []
    for entry in operator:
        key = mod_leaf(entry).casefold()
        if key in bundle_keys:
            own = next(name for name in bundle if mod_leaf(name).casefold() == key)
            if entry != mod_leaf(entry) and key not in slots and (entry, own) not in replaced:
                replaced.append((entry, own))
        elif key in retired_keys:
            removed.append(entry)
        elif key in other_keys:
            moved.append(entry)
        elif entry.casefold() not in seen:
            seen.add(entry.casefold())
            merged.append(entry)
            (warned if key in unowned_keys else kept).append(entry)
    present = {entry.casefold() for entry in operator}
    added = [entry for entry in merged if entry.casefold() not in present]
    return {'merged': merged, 'added': added, 'removed': removed, 'kept': kept, 'moved': moved,
            'replaced': replaced, 'unowned': warned}


def _merge_launcher(current, bundle, retired, unowned=(), present=None):
    try:
        text, wanted_text = current.decode('utf-8'), bundle.decode('utf-8')
    except UnicodeDecodeError:
        raise Unmergeable('is not UTF-8 text')
    wanted = {}
    wanted_delayed, delayed = delayed_expansion(wanted_text), delayed_expansion(text)
    for line in wanted_text.splitlines():
        if not _launcher_comment(line):
            for name, start, end, _quoted in launcher_args(line, wanted_delayed):
                wanted.setdefault(name, launcher_entries(line[start:end]))
    if 'mod' not in wanted:
        raise Unmergeable('the bundle launcher has no -mod= argument')
    managed = [entry for entries in wanted.values() for entry in entries]
    seen, changes, out = set(), [], []
    for line in text.splitlines(keepends=True):
        if not _launcher_comment(line):
            for name, start, end, quoted in reversed(launcher_args(line, delayed)):
                seen.add(name)
                old = launcher_entries(line[start:end])
                result = merge_values(old, wanted.get(name, []), retired, managed, unowned, present)
                merged = result['merged']
                if merged == old:
                    continue
                value = ';'.join(merged)
                if not quoted and LAUNCHER_STOP.search(value):
                    raise Unmergeable('would need quotes around a -%s= value it did not write' % name)
                line = line[:start] + value + line[end:]
                changes.append({'arg': 'mod' if name == 'mod' else 'serverMod', 'added': result['added'],
                                'removed': result['removed'], 'kept': result['kept'], 'moved': result['moved'],
                                'replaced': result['replaced'], 'unowned': result['unowned'],
                                'reordered': not (result['added'] or result['removed'] or result['moved']
                                                  or result['replaced'])})
        out.append(line)
    if 'mod' not in seen:
        raise Unmergeable('has no -mod= argument to merge into')
    if wanted.get('servermod') and 'servermod' not in seen:
        for index, line in enumerate(out):
            if _launcher_comment(line):
                continue
            args = [arg for arg in launcher_args(line, delayed) if arg[0] == 'mod']
            if not args:
                continue
            _name, _start, end, quoted = args[0]
            value = ';'.join(wanted['servermod'])
            add = ' "-serverMod=%s"' % value if quoted else ' -serverMod=%s' % value
            at = end + (1 if quoted else 0)
            out[index] = line[:at] + add + line[at:]
            changes.append({'arg': 'serverMod', 'added': list(wanted['servermod']), 'removed': [], 'kept': [],
                            'moved': [], 'replaced': [], 'unowned': [], 'reordered': False})
            break
    merged = ''.join(out).encode('utf-8')
    return merged, ([] if merged == current else changes)


def merge_launcher(current, bundle, retired=(), unowned=(), present=None):
    """(merged bytes, changes) with the -mod= and -serverMod= lists merged: the bundle's folders in bundle order,
    then every operator entry this installer does not manage in its original order. retired names the retired folders
    to remove; unowned names retired folders the installer never installed, which stay as the operator's own entries.
    present limits the path-form replacement to folders that exist or are installed (see merge_values).
    Every other byte of the operator's file (port, -profiles, -cpuCount, other arguments, line endings) stays.
    None when the file cannot be merged safely (see launcher_problem)."""
    try:
        return _merge_launcher(current, bundle, retired, unowned, present)
    except Unmergeable:
        return None


def launcher_problem(current, bundle, retired=(), unowned=(), present=None):
    try:
        _merge_launcher(current, bundle, retired, unowned, present)
    except Unmergeable as error:
        return str(error)
    return None


def live_launcher_problem(text):
    """Why the -mod= entries of a live launcher cannot be read (an unclosed quote, a %variable%, ^ in a value, ! in a
    value when the file enables delayed expansion); None when they can."""
    delayed = delayed_expansion(text)
    for line in text.splitlines():
        if _launcher_comment(line):
            continue
        try:
            launcher_args(line, delayed)
        except Unmergeable as error:
            return str(error)
    return None


def retired_folders():
    return [m['folder'] for m in ws.load_manifest()['retired']]


def server_folder_names(ctx):
    """Casefolded names of the folders in the server root (NTFS is case-insensitive)."""
    try:
        return {path.name.casefold() for path in Path(ctx.server).iterdir() if path.is_dir()}
    except OSError:
        return set()


def launcher_present(ctx):
    """Casefolded folder names the server has or this run puts there: what a path-form launcher entry may be replaced
    by the bundle's short form for. A skipped step installs nothing."""
    names = server_folder_names(ctx)
    if 'mods' not in ctx.skip:
        names |= {name.casefold() for name in getattr(ctx, 'own_folders', None) or ()}
    if 'workshop' not in ctx.skip:
        names |= {item['folder'].casefold() for item in getattr(ctx, 'third_items', None) or ()}
    return names


def launcher_retired(ctx):
    """(retired folders the launcher merge removes, retired folders it keeps). Only a folder the Workshop receipt
    records as created by this installer, and that the Workshop step removes now or removed in an earlier run (the
    install receipt's retired_removed list), is removed from the launcher; a retired folder the operator brought
    themselves stays in their -mod= list. A retired_removed name counts only while its folder is absent from the
    server root: a folder the operator put back is theirs. ctx.retire_reasons says why a kept folder is kept
    (casefolded name -> 'skipped' when the Workshop step is skipped, 'returned' when the operator put the folder
    back, 'unowned' otherwise)."""
    if ctx.retire_cache is None:
        manifest = ws.load_manifest()
        names = [m['folder'] for m in manifest['retired']]
        tops = set()
        skipped = 'workshop' in ctx.skip
        if not skipped:
            try:
                receipt = ws.load_receipt(ctx.server, {m['folder'] for m in manifest['mods'] + manifest['retired']},
                                          [Path(ctx.bundle) / 'keys'], warn=lambda _text: None)
                rows, dirs, _kept = ws.split_retired_rows(receipt, manifest, ctx.server, [Path(ctx.bundle) / 'keys'])
            except ws.SyncError as error:
                raise Refused('workshop_receipt', str(error))
            tops |= {r['path'].split('/')[0].casefold() for r in rows}
            tops |= {d.split('/')[0].casefold() for d in dirs}
        done = ctx.receipt.get('retired_removed') if ctx.receipt else None
        back = set()
        if isinstance(done, list):
            present = server_folder_names(ctx)
            for name in done:
                if isinstance(name, str):
                    (back if name.casefold() in present else tops).add(name.casefold())
        ctx.retire_cache = ([n for n in names if n.casefold() in tops], [n for n in names if n.casefold() not in tops])
        ctx.retire_reasons = {n.casefold(): 'returned' if n.casefold() in back else 'skipped' if skipped else 'unowned'
                              for n in ctx.retire_cache[1]}
    return ctx.retire_cache


def prune_retired_removed(ctx, launcher_text):
    """Forget retired_removed names the launcher step no longer needs: those the live launcher does not list (the
    removal is done) or whose folder is back in the server root (the operator owns it now). The list is only a
    note for a launcher step that did not finish; it must not outlive that. True when the list changed."""
    done = ctx.receipt.get('retired_removed')
    if not isinstance(done, list):
        return False
    listed = {mod_leaf(entry).casefold() for line in launcher_text.splitlines() if not _launcher_comment(line)
              for _name, start, end, _quoted in launcher_args(line, delayed_expansion(launcher_text))
              for entry in launcher_entries(line[start:end])}
    present = server_folder_names(ctx)
    keep = [name for name in done if isinstance(name, str) and name.casefold() in listed
            and name.casefold() not in present]
    if keep:
        ctx.receipt['retired_removed'] = sorted(keep)
    else:
        ctx.receipt.pop('retired_removed', None)
    return ctx.receipt.get('retired_removed') != done


WARN_RETIRED = {
    'unowned': 'is a retired Hollow Country dependency this installer did not install; it stays in your launcher as '
               'one of your own mods',
    'skipped': 'is a retired Hollow Country dependency; the workshop step was skipped, so its folder is kept and it '
               'stays in your launcher',
    'returned': 'is a retired Hollow Country dependency this installer removed earlier; its folder is back in the '
                'server folder, so it stays in your launcher as one of your own mods',
}


def launcher_change_lines(changes, reasons=None):
    """One line per mod: added, removed (retired), moved (to the other argument), replaced (path form), kept (not
    managed by this installer) or WARN (a retired folder that stays; reasons maps the casefolded folder name to why:
    see launcher_retired)."""
    reasons = reasons or {}
    lines = []
    for change in changes:
        arg = '-' + change['arg']
        lines += ['added   %s %s' % (arg, name) for name in change['added']]
        lines += ['removed %s %s (retired by this bundle)' % (arg, name) for name in change['removed']]
        lines += ['moved   %s %s (the bundle lists it in the other argument)' % (arg, name)
                  for name in change.get('moved', [])]
        lines += ['replaced %s %s by %s (the bundle form)' % (arg, old, new) for old, new in change.get('replaced', [])]
        lines += ['kept    %s %s (not managed by this installer)' % (arg, name) for name in change['kept']]
        lines += ['WARN    %s %s %s' % (arg, name, WARN_RETIRED[reasons.get(mod_leaf(name).casefold(), 'unowned')])
                  for name in change.get('unowned', [])]
        if change.get('reordered'):
            lines.append('moved   %s: the bundle folders come first, in bundle order' % arg)
    return lines


def load_receipt(server):
    path = Path(server) / RECEIPT
    if not path.exists():
        return {'schema': SCHEMA, 'files': {}, 'overlay': None}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except OSError as error:
        # Locked, permission denied, a folder in its place: the content is unknown, so --repair must not replace it.
        raise Refused('receipt_unreadable', '%s cannot be opened (%s); stop whatever holds it or fix its permissions, '
                      'then run this again: --repair only rebuilds a receipt that is damaged, never one that cannot '
                      'be read at all' % (RECEIPT, error.__class__.__name__))
    except ValueError:  # includes UnicodeDecodeError: the bytes are there but are not a receipt
        raise Refused('receipt_invalid', '%s is damaged (not valid JSON text); run --apply --repair to start a fresh one (the old bytes '
                      'are kept in the backup folder), or move it away (files are then treated as existing ones and '
                      'backed up before they are replaced)' % RECEIPT)
    validate_receipt(data)
    return data


def validate_receipt(data):
    """Refuse a receipt of another layout, with invalid profile default hashes (receipt_invalid) or with a
    globals_optout that is not a list of names (receipt_optout_invalid, checked last: --repair rebuilds that one
    list, then validates everything else again)."""
    if not isinstance(data, dict) or data.get('schema') != SCHEMA or not isinstance(data.get('files'), dict):
        raise Refused('receipt_invalid', '%s has an unknown layout' % RECEIPT)
    profiles = data.get('profile_defaults', {})
    if (not isinstance(profiles, dict) or
            any(not isinstance(hashes, list) or
                any(not isinstance(h, str) or not re.fullmatch(r'[0-9a-f]{64}', h) for h in hashes)
                for hashes in profiles.values())):
        raise Refused('receipt_invalid', '%s has invalid profile default hashes' % RECEIPT)
    optout = data.get('globals_optout')
    if 'globals_optout' in data and (not isinstance(optout, list) or any(not isinstance(n, str) or not n for n in optout)):
        raise Refused('receipt_optout_invalid', '%s has an invalid globals_optout (it must be a list of variable names); '
                      'run --apply --repair: the list is rebuilt from the loot-boost state on disk and the rest of the '
                      'receipt is kept' % RECEIPT)


def clean_optout(value):
    """A globals_optout value as a sorted list of names, or None when it is not a list of non-empty strings."""
    if isinstance(value, list) and all(isinstance(name, str) and name for name in value):
        return sorted(set(value))
    return None


def salvage_optout(ctx, text):
    """The --keep-stock-globals opt-outs a receipt that is being rebuilt must not lose. From the old receipt when its
    text still holds a readable globals_optout (the whole file as JSON, else the array alone), otherwise from the
    loot-boost state on disk: the variables that are back at their stock value are exactly the ones an opt-out
    recorded."""
    if text:
        try:
            found = clean_optout(json.loads(text).get('globals_optout'))
        except (ValueError, AttributeError):
            found = None
            match = re.search(r'"globals_optout"\s*:\s*(\[[^\[\]]*\])', text)
            if match:
                try:
                    found = clean_optout(json.loads(match.group(1)))
                except ValueError:
                    found = None
        if found is not None:
            return found
    try:
        return clean_optout(sorted(globals_state(map_mission(ctx))['resets'])) or []
    except Exception:  # evidence unusable: nothing to carry; the next --keep-stock-globals run records it again
        return []


def load_run_receipt(ctx):
    """The receipt for this run. A receipt that cannot be read or parsed stops the run, except under --repair, which
    starts a fresh one (the unreadable file is copied to the backup folder when the new receipt replaces it; the
    globals_optout list is carried over, see salvage_optout). A receipt that parses but has another layout or schema
    is never replaced: it may belong to another installer. A receipt of this layout whose globals_optout is not a list
    of names keeps everything else under --repair and rebuilds that list the same way."""
    try:
        ctx.receipt = load_receipt(ctx.server)
    except Refused as error:
        if error.code not in ('receipt_invalid', 'receipt_optout_invalid') or not getattr(ctx.args, 'repair', False):
            raise
        try:
            text = (Path(ctx.server) / RECEIPT).read_text(encoding='utf-8')
        except UnicodeDecodeError:
            text = None
        except OSError as os_error:
            raise Refused('receipt_unreadable', '%s cannot be opened (%s); --repair does not replace it'
                          % (RECEIPT, os_error.__class__.__name__))
        if error.code == 'receipt_optout_invalid':
            data = json.loads(text)
            data['globals_optout'] = salvage_optout(ctx, None)
            validate_receipt(data)  # everything else the receipt holds is checked as on any other run
            ctx.receipt = data
            ctx.repair_extra = [row for row in ctx.repair_extra if row['kind'] != 'receipt']
            ctx.repair_extra.append(repair_row('receipt', RECEIPT, 'globals_optout was not a list of names; rebuilt '
                                               'from the loot-boost state on disk, the rest of the receipt is kept'))
            return
        if text is not None:
            try:
                json.loads(text)
            except ValueError:
                pass
            else:
                raise Refused('receipt_invalid', '%s has an unknown layout (written by another installer version?); '
                              '--repair does not replace it: use the installer that wrote it, or move it away (files '
                              'are then treated as existing ones and backed up before they are replaced)' % RECEIPT)
        ctx.receipt = {'schema': SCHEMA, 'files': {}, 'overlay': None}
        optout = salvage_optout(ctx, text)
        if optout:
            ctx.receipt['globals_optout'] = optout
        ctx.repair_extra = [row for row in ctx.repair_extra if row['kind'] != 'receipt']
        ctx.repair_extra.append(repair_row('receipt', RECEIPT, 'unreadable; replaced by a fresh receipt (old bytes '
                                           'kept in the backup folder)%s'
                                           % ('; globals_optout carried over' if optout else '')))


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
        self.repair_blocked = []  # repair rows --repair could fix but was not given (edited managed files)
        self.repair_extra = []   # repair rows that are not file classifications (receipt rebuild, recovered runs)
        self.retire_cache = None  # launcher_retired: (removed, kept) retired folders, fixed for the run
        self.retire_reasons = {}  # launcher_retired: why each kept retired folder is kept
        self.optout_new = False  # --keep-stock-globals recorded a new opt-out; a step must save the receipt
        self.force_tree = False  # a typed y at the hard-exit prompt: allows the whole-tree restore and nothing else
        self.replaced_plan = {}  # dry run: step name -> label of a layer step 5 would roll back for that step to replace
        self.replaced_done = {}  # apply: step name -> label of a layer step 5 rolled back; that step must install it again

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


# HC configuration adds missing keys only. Expansion owns the rest of AISettings
# and receives the HC-owned merge policy there; never replace an entire operator object.
MISSING_ONLY_PROFILES = {'profiles/HollowCountry/Groups/settings.json',
                         'profiles/HollowCountry/Infected/lod.json'}
MERGE_PROFILES = {'profiles/ExpansionMod/Settings/AISettings.json'} | MISSING_ONLY_PROFILES


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
    missing_only = any(target.as_posix().endswith('/' + rel) for rel in MISSING_ONLY_PROFILES)
    changed = [k for k, v in want.items() if k not in live or (not missing_only and not same_value(live[k], v))]
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
    normalized = sha256_bytes(normalize_profile((ctx.server / rel).read_bytes()))
    if current == recorded or current in known or normalized in known:
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
        self.retire_files = []   # receipt rows of retired dependencies still on the server
        self.retire_dirs = []    # their receipt folders
        self.receipt_repaired = []  # Workshop receipt key rows an earlier release orphaned (dropped, then persisted)
        self.retire_kept = []    # (key path, reason): retired mods' root keys that stay because something else needs them
        self.overlay = None
        self.repairs = []        # repair rows (see repair_row) found while classifying; --repair applies them
        self.launcher_blocked = None  # why start-server.bat cannot be merged (set when it is a refusal)


def repair_row(kind, path, detail, status='repair'):
    return {'kind': kind, 'path': path, 'detail': detail, 'status': status}


def heal_action(ctx, a, rel, action):
    """Self-repair classification for a file this installer owns outright (our mod folders, keys, start-server.bat).

    A recorded file that is gone is simply written again. An edited file (drift) or one the receipt never
    recorded (confirm) is restored from the bundle only under --repair, with the current bytes backed up first;
    without --repair drift stays a refusal that names the flag. Profiles are operator files and never come here.
    """
    if action == 'new' and rel in ctx.receipt['files']:
        a.repairs.append(repair_row('missing', rel, 'recorded as installed but absent; written again'))
    elif action in ('drift', 'confirm'):
        kind = 'edited' if action == 'drift' else 'unrecorded'
        if getattr(ctx.args, 'repair', False):
            a.repairs.append(repair_row(kind, rel, 'replaced with the bundle file; current bytes are copied to the '
                                        'backup folder first'))
            return 'repair'
        if action == 'drift':
            a.repairs.append(repair_row(kind, rel, 'changed since this installer wrote it; run --apply --repair to '
                                        'restore it (backed up first)', status='blocked'))
        else:
            # An unrecorded file is replaced only after the typed yes or --yes; it is listed either way.
            a.repairs.append(repair_row(kind, rel, 'differs from the bundle file and was never written by this '
                                        'installer; replaced after confirmation (--yes or a typed yes), current bytes '
                                        'are copied to the backup folder first'))
    return action


def classify_launcher(ctx, rel, source):
    """classify_file for start-server.bat, with the operator's own launcher in mind: a file whose -mod= and
    -serverMod= lists already equal the merged result is 'same' whatever else it holds (port, -profiles, -cpuCount)."""
    action, sha = classify_file(ctx, rel, source)
    if action in ('new', 'same'):
        return action, sha
    if action == 'upgrade' and not ctx.receipt.get('launcher_merged'):
        return action, sha  # the unedited file an older bundle wrote: replaced as a whole, with a backup
    current = (ctx.server / rel).read_bytes()
    merged = merge_launcher(current, source.read_bytes(), *launcher_retired(ctx), present=launcher_present(ctx))
    if merged is not None and merged[0] == current:
        return 'same', sha
    return action, sha


def heal_launcher(ctx, a, rel, source, action):
    """heal_action for start-server.bat. An edited or unrecorded launcher is never replaced wholesale, not even
    under --repair or --yes: only its -mod= and -serverMod= lists are merged (bundle folders first, then every
    operator entry kept, retired folders removed), the old file is backed up first and the preview names each mod.
    A launcher that cannot be merged (no -mod= argument, not UTF-8, a batch variable or an unclosed quote) is a
    refusal with that reason."""
    if action not in ('drift', 'confirm'):
        return heal_action(ctx, a, rel, action)
    current = (ctx.server / rel).read_bytes()
    retired = launcher_retired(ctx)
    present = launcher_present(ctx)
    problem = launcher_problem(current, source.read_bytes(), *retired, present=present)
    if problem:
        a.launcher_blocked = ('%s %s; --repair and --yes never replace a launcher wholesale: fix it by hand or move '
                              'it away' % (rel, problem))
        a.repairs.append(repair_row('launcher', rel, 'cannot be merged (%s); never replaced wholesale: fix it by '
                                    'hand or move it away' % problem, status='blocked'))
        return 'drift'
    merged = merge_launcher(current, source.read_bytes(), *retired, present=present)
    lines = launcher_change_lines(merged[1], ctx.retire_reasons)
    if action == 'drift':
        if getattr(ctx.args, 'repair', False):
            row = repair_row('edited', rel, 'edited launcher kept; only the -mod=/-serverMod= lists are merged in '
                             '(current bytes are copied to the backup folder first)')
            row['lines'] = lines
            a.repairs.append(row)
            return 'repair'
        row = repair_row('edited', rel, 'changed since this installer wrote it; run --apply --repair to merge the '
                         '-mod=/-serverMod= lists into it (every other argument and your own mods kept, backed up '
                         'first)', status='blocked')
        row['lines'] = lines
        a.repairs.append(row)
        return 'drift'
    repairing = getattr(ctx.args, 'repair', False)
    row = repair_row('unrecorded', rel, 'existing launcher kept; only the -mod=/-serverMod= lists are merged in%s; '
                     'current bytes are copied to the backup folder first'
                     % ('' if repairing else ' after confirmation (--yes or a typed yes)'))
    row['lines'] = lines
    a.repairs.append(row)
    return 'repair' if repairing else 'confirm'


def analyze(ctx):
    a = Analysis()
    args = ctx.args
    manifest = ws.load_manifest()
    items = ws.select(manifest, list(ws.GROUPS))
    ctx.items = items
    own_folders = [i['folder'] for i in items if i['publish'] and bundle_walk(ctx.bundle, ctx.manifest, i['folder'])]
    ctx.own_folders = own_folders
    ctx.third_items = [i for i in items if i['id'] and not i['publish']]
    if not args.check and not args.assume_stopped:
        a.running = ws.server_running(ctx.server)
    # mod folders and keys
    if 'mods' not in ctx.skip:
        keys = {}
        for folder in own_folders:
            expected = set()
            for rel, source in bundle_walk(ctx.bundle, ctx.manifest, folder):
                action, sha = classify_file(ctx, rel, source)
                action = heal_action(ctx, a, rel, action)
                a.own.append((rel, source, action, sha))
                expected.add(rel.casefold())
            installed = ctx.server / folder / 'addons'
            if installed.is_dir() and not installed.is_symlink():
                for path in sorted(installed.iterdir()):
                    rel = '%s/addons/%s' % (folder, path.name)
                    # NTFS is case-insensitive: a case-only variant of an expected file is the file just written.
                    if path.is_file() and path.suffix.lower() in ('.pbo', '.bisign') and rel.casefold() not in expected:
                        a.stale.append(rel)
                        a.repairs.append(repair_row('retired', rel, 'old signed file moved to the backup folder'))
        for rel, source in bundle_walk(ctx.bundle, ctx.manifest, 'keys'):
            action, sha = classify_file(ctx, rel, source)
            action = heal_action(ctx, a, rel, action)
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
        action, sha = classify_launcher(ctx, LAUNCHER_REL, source)
        action = heal_launcher(ctx, a, LAUNCHER_REL, source, action)
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
        # A receipt an older release wrote still names the folders of items since retired.
        receipt = ws.load_receipt(ctx.server, {m['folder'] for m in manifest['mods'] + manifest['retired']},
                                  [Path(ctx.bundle) / 'keys'], warn=ctx.say, repaired=a.receipt_repaired)
        owned = set(receipt['dirs']) if receipt else set()
        a.retire_files, a.retire_dirs, a.retire_kept = ws.split_retired_rows(
            receipt, manifest, ctx.server, [Path(ctx.bundle) / 'keys'])
    except ws.SyncError as error:
        raise Refused('workshop_receipt', str(error))
    ctx.owned = owned
    for item in ctx.third_items:
        ctx.say('Checking Workshop dependency %s ...' % item['folder'])
        exists = ws.case_path(ctx.server, item['folder']).exists()
        resolved = ws.find_item(item['id'], dirs)
        a.third.append({'item': item, 'exists': exists, 'ours': item['folder'].casefold() in {d.casefold() for d in owned},
                        'content': resolved[0], 'resolved': resolved})
    a.dependencies = []
    for dep in a.third:
        item = dep['item']
        if dep['ours']:
            plan = ws.plan_refresh(item, dirs, ctx.server, receipt, [ctx.bundle / 'keys'], say=ctx.say, resolved=dep['resolved'])
            a.dependencies.append(plan)
            for kind in ('edited', 'unrecorded'):
                for rel in plan[kind]:
                    root_key = kind == 'unrecorded' and rel.casefold().startswith('keys/')
                    row = repair_row(kind, rel, 'Workshop source %s; %s' % (plan['source'],
                        'unowned root key blocks the whole folder; reconcile by hand' if root_key else
                        'run --apply --repair to restore it (current bytes backed up first)'),
                        status='repair' if args.repair and not root_key else 'blocked')
                    row['step'] = 'workshop'
                    a.repairs.append(row)
            if args.repair:
                for rel in plan['extras']:
                    row = repair_row('retired', rel, 'extra file moved to backup; Workshop source %s' % plan['source'])
                    row['step'] = 'workshop'
                    a.repairs.append(row)
        elif dep['exists']:
            state, source, detail = dep['resolved']
            if state == 'present':
                # Compare read-only, without ever claiming or touching this folder.
                fake = {'schema': 1, 'dirs': [item['folder']], 'files': []}
                plan = ws.plan_refresh(item, dirs, ctx.server, fake, say=ctx.say, resolved=dep['resolved'])
                dep['version'] = plan['state']
            else:
                dep['version'] = state
    a.workshop_receipt = receipt
    a.pending = [t for t in a.third if not t['exists'] and not t['ours'] and t['content'] != 'content-updating']
    a.left = [t for t in a.third if t['exists'] and not t['ours']]
    a.fetch = [t['item'] for t in a.pending if t['content'] != 'present']
    a.dependency_warnings = []
    for dep in a.third:
        state, source, detail = dep['resolved']
        folder = dep['item']['folder']
        if detail:
            a.dependency_warnings.append('%s: %s' % (folder, detail))
        if state != 'present':
            label = state if state == 'content-updating' else 'content-missing (' + state + ')'
            a.dependency_warnings.append('%s: %s; existing server copy kept' % (folder, label))
        copies = [d for d in dirs if (d / dep['item']['id']).is_dir()]
        steam_dir = ws.content_dirs((), ctx.steamcmd)
        if copies and all(d in steam_dir for d in copies) and not getattr(ctx, 'workshop_updated', False):
            a.dependency_warnings.append('%s: steamcmd copies are only refreshed with --update-workshop' % folder)
        if dep['exists'] and not dep['ours'] and dep.get('version') not in ('current', 'content-missing', 'missing'):
            a.dependency_warnings.append('%s: non-owned dependency differs from Workshop; update by hand' % folder)
    for plan in a.dependencies:
        for rel in plan['extras']:
            a.dependency_warnings.append('%s: untracked extra; kept unless --repair' % rel)
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


def read_journal(ctx, path):
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
    return data


def pending_runs(ctx):
    parent = ctx.server / BACKUP_DIR
    ws.check_no_symlink_below(ctx.server, BACKUP_DIR)
    runs = []
    if not parent.exists():
        return runs
    for path in sorted(parent.glob('*/' + JOURNAL), reverse=True):
        data = read_journal(ctx, path)
        if data['state'] in ('active', 'rolling-back', 'rollback_pending'):
            runs.append((path.parent, data))
    return runs


def record_written(ctx, rel, digest):
    """Publish expected bytes before a live write; retain earlier writes for interrupted upgrades."""
    track_target(ctx, rel)
    key = rel.casefold()
    for row in ctx.journal['entries']:
        path = row['path'].casefold()
        if key == path or (row['kind'] == 'tree' and key.startswith(path + '/')):
            name = '/'.join(rel.split('/')[len(row['path'].split('/')):])
            values = row['written'].setdefault(name, [])
            if digest not in values:
                values.append(digest)
                ws.write_json_atomic(journal_path(ctx.backup_root), ctx.journal)
            return


def journal_row(ctx, rel):
    """The journal row for a path, compared case-insensitively like track_target (Windows paths). A missing row is a
    refusal, never a StopIteration."""
    key = rel.casefold()
    for row in ctx.journal['entries']:
        if row['path'].casefold() == key:
            return row
    raise Refused('journal_invalid', 'the run journal has no row for %s; nothing was written there' % rel)


@contextlib.contextmanager
def tree_writer(ctx, mission):
    """Fingerprint helper results before returning, including partial/refused writes.

    A hard process exit before this snapshot leaves unknown bytes: recovery must
    refuse those bytes, never infer ownership from a backup alone.
    """
    rel = mission.relative_to(ctx.server).as_posix()
    track_target(ctx, rel, tree=True)
    before = tree_inventory(mission)
    # "tree writer in progress": published before the helper writes and cleared when its result is recorded. A
    # hard exit leaves it set, which is the only case --repair may restore the whole tree from the backup.
    row = journal_row(ctx, rel)
    row['writing'] = row.get('writing', 0) + 1
    ws.write_json_atomic(journal_path(ctx.backup_root), ctx.journal)
    try:
        yield
    finally:
        after = tree_inventory(mission)
        row = journal_row(ctx, rel)
        if row.get('writing', 0) > 1:
            row['writing'] -= 1
        else:
            row.pop('writing', None)
        for name in before.keys() | after.keys():
            if before.get(name) != after.get(name):
                values = row['written'].setdefault(name, [])
                if after.get(name) not in values:
                    values.append(after.get(name))
        ws.write_json_atomic(journal_path(ctx.backup_root), ctx.journal)


def hard_exit_rows(data):
    """Journal rows of a mission tree whose writer never recorded its result (the process exited inside it)."""
    return [row for row in data['entries'] if row['kind'] == 'tree' and row.get('writing')]


def rollback_changes(ctx, root, data, force=False):
    """Only undo known installer bytes. Validate every row before mutating anything.

    With force (--repair), a tree whose writer was cut off by a hard exit ("writing" marker) is restored as a whole
    from this run's verified backup: its live bytes were never recorded, so they cannot be matched one by one.
    """
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
            # A Workshop update may rename only the case. The journal owns that Windows path,
            # including on a case-sensitive test host; restore its original spelling and bytes.
            target = ws.case_path(ctx.server, rel)
            actual = target.relative_to(ctx.server).as_posix()
            current = ({'': sha256_file(target)} if target.is_file() else
                       {'': 'dir'} if target.is_dir() else {})
            if actual != rel and target.is_file():
                live = current['']
                if live != before.get('') and live not in row.get('written', {}).get('', []):
                    conflicts.append('%s (backup: %s)' % (actual, shown(backup)))
                    continue
                changes.append(('remove', actual, None))
                current = {}
        whole = force and row['kind'] == 'tree' and bool(row.get('writing'))
        written = row.get('written', {})
        row_changes = []
        for name in before.keys() | current.keys():
            baseline, live = before.get(name), current.get(name)
            if live == baseline:
                continue
            full_rel = rel + ('/' + name if name else '')
            if not whole and live not in written.get(name, []):
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
        hint = ''
        if hard_exit_rows(data):
            hint = ('; the mission step was cut off by a hard exit: with the server stopped, run --apply --repair '
                    '(or answer y when asked) to restore the mission folder from this run\'s backup')
        raise ValueError('changed after interrupted install; left untouched: ' + '; '.join(sorted(conflicts)) + hint)
    unique = {}
    for change in changes:
        unique.setdefault(change[:2], change)
    return keep_non_empty(ctx, list(unique.values()))


def keep_non_empty(ctx, changes):
    """A folder this run created may hold files the server wrote since (runtime data, logs). Leaving the folder
    is harmless; failing to remove it halfway through an undo is not. Decide before anything is changed."""
    gone = {rel for action, rel, _source in changes if action == 'remove'}
    planned = []
    for action, rel, source in changes:
        if action == 'rmdir':
            target = ctx.server / rel
            try:
                names = [child.name for child in target.iterdir()] if target.is_dir() else []
            except OSError:
                names = []
            if any(rel + '/' + name not in gone for name in names):
                planned.append(('keep', rel, None))
                continue
            gone.add(rel)
        planned.append((action, rel, source))
    return planned


def change_text(change):
    action, rel, _source = change
    return 'kept non-empty folder %s' % rel if action == 'keep' else '%s %s' % (action, rel)


def restore_change(ctx, change):
    action, rel, source = change
    ws.check_no_symlink_below(ctx.server, rel)
    target = ctx.server / rel
    if action == 'keep':
        ctx.say(change_text(change))
    elif action == 'remove':
        target.unlink()
    elif action == 'rmdir':
        # Only empty directories; never recursively remove a live tree. A runtime file that appeared after the
        # plan was made keeps the folder.
        if target.is_dir() and any(target.iterdir()):
            ctx.say(change_text(('keep', rel, None)))
        else:
            target.rmdir()
    elif action == 'mkdir':
        target.mkdir(parents=True, exist_ok=True)
    else:
        # A step that retired a folder (workshop_sync removes an emptied retired mod folder) does not journal the
        # removal, so the folder a file is restored into may be gone: make it again.
        target.parent.mkdir(parents=True, exist_ok=True)
        ws.copy_atomic(source, target)


def describe_pending(ctx, root, data):
    state = 'install_interrupted' if data['state'] == 'active' else 'rollback_pending'
    if data['state'] != 'active' and data.get('intent') == 'rollback':
        advice = ('rerun with --rollback %s --apply with the server stopped to finish this rollback (--apply alone '
                  'also finishes it, then installs)' % root.name)
    else:
        advice = 'rerun with --apply with the server stopped to recover before installing'
    lines = ['%s: %s; %s' % (state, shown(journal_path(root)), advice)]
    try:
        changes = rollback_changes(ctx, root, data)
        lines += ['  pending: %s' % change_text(change) for change in changes if change[0] != 'keep']
        if not changes:
            lines.append('  pending: finalize rollback journal')
    except (OSError, ValueError, ws.SyncError) as error:
        lines.append('  pending: inspect journal targets: ' + shown(error))
    return '\n'.join(lines)


STASH_PREFIX = 'hard-exit-partial-'
STASH_TEMP = 'hard-exit-stash-tmp'


def stash_cut_off_trees(ctx, root, data):
    """Before a hard-exit tree is restored from the backup, keep a copy of what is there now: one stash per attempt
    (named with the run id, numbered when an earlier attempt already left one). The copy is made under a temporary
    name and renamed into place only when complete, so an interrupted copy is never mistaken for a stash and a
    retry always keeps the operator's mission edits. Returns the stash folder, or None when there was nothing."""
    rows = [row for row in hard_exit_rows(data) if (ctx.server / row['path']).is_dir()]
    if not rows:
        return None
    for partial in root.glob(STASH_TEMP + '*'):
        shutil.rmtree(partial, ignore_errors=True)  # only ever our own unfinished copy
        if os.path.lexists(partial):
            raise Refused('stash_cleanup', 'an earlier unfinished copy of the cut-off mission folder (%s) could not be '
                          'removed (a file in it is locked or read-only?); close what uses it or delete it by hand, then '
                          'run this again: it is only a temporary copy' % shown(partial))
    number = 1
    while True:
        final = root / (STASH_PREFIX + root.name + ('' if number == 1 else '-%d' % number))
        if not os.path.lexists(final):
            break
        number += 1
    temp = root / (STASH_TEMP + '-' + root.name)
    for row in rows:
        target = temp / row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ctx.server / row['path'], target, ignore=ignore_persistence)
    os.rename(temp, final)
    ctx.say('Kept a copy of the cut-off mission folder before restoring it: %s' % shown(final))
    return final


def rollback_run(ctx, root, data, force=False):
    ws.write_json_atomic(journal_path(root), dict(data, state='rolling-back'))
    data['state'] = 'rolling-back'
    try:
        changes = rollback_changes(ctx, root, data, force)
        if force:
            stash_cut_off_trees(ctx, root, data)
        for change in changes:
            restore_change(ctx, change)  # Stop at the first failed undo; keep all backups.
    except (OSError, ValueError, ws.SyncError):
        data['state'] = 'rollback_pending'
        ws.write_json_atomic(journal_path(root), data)
        raise
    ws.write_json_atomic(journal_path(root), dict(data, state='rolled-back'))
    data['state'] = 'rolled-back'


def recover_runs(ctx, runs, force=False):
    require_stopped(ctx, False if ctx.args.assume_stopped else ws.server_running(ctx.server))
    for root, data in runs:
        try:
            rollback_run(ctx, root, data, force)
        except (OSError, ValueError, ws.SyncError):
            raise Refused('rollback_pending', describe_pending(ctx, root, data))
        ctx.say('Recovered interrupted install; ' + ROLLBACK_OK)


def rollback_named(ctx, name):
    """--rollback RUN: undo one completed run byte-exact from its journal. Every target is checked first: a file
    changed since that run (a later install, the operator, the server) is left untouched and listed. The same
    command resumes a rollback of that run that was interrupted (state rolling-back or rollback_pending).

    This is mostly a tool for right after an install, before the server has run: Expansion rewrites
    AISettings.json when the server boots, and anything the server changed since the run is a conflict that
    stops the rollback before it changes anything."""
    if not re.fullmatch(r'[0-9A-Za-z_.-]+', name) or name in ('.', '..'):
        raise Refused('rollback_run', '--rollback takes a run folder name from %s' % BACKUP_DIR)
    path = ctx.server / BACKUP_DIR / name / JOURNAL
    if not path.is_file():
        raise Refused('rollback_run', 'no run named %s in %s' % (name, BACKUP_DIR))
    data = read_journal(ctx, path)
    root = path.parent
    if data['state'] == 'rolled-back':
        ctx.say('Run %s was already rolled back; nothing to do.' % name)
        return 0
    resuming = data['state'] in ('rolling-back', 'rollback_pending')
    if data['state'] != 'complete' and not resuming:
        raise Refused('rollback_run', 'run %s is %s; rerun with --apply (without --rollback) to recover it' % (name, data['state']))
    force = bool(getattr(ctx.args, 'repair', False)) or ctx.force_tree
    try:
        changes = rollback_changes(ctx, root, data, force)
    except (OSError, ValueError, ws.SyncError) as error:
        raise Refused('rollback_conflict', shown(error))
    ctx.say('%s of run %s (%s):' % ('Resuming the rollback' if resuming else 'Rollback', name,
                                    'apply' if ctx.args.apply else 'dry run, nothing is changed'))
    for change in changes:
        ctx.say('  ' + change_text(change))
    if not changes:
        ctx.say('  nothing differs from the state before that run')
    if not ctx.args.apply:
        ctx.say('Run again with --apply (server stopped) to roll back.')
        return 0
    require_stopped(ctx, False if ctx.args.assume_stopped else ws.server_running(ctx.server))
    data['intent'] = 'rollback'
    try:
        rollback_run(ctx, root, data, force)
    except (OSError, ValueError, ws.SyncError):
        raise Refused('rollback_pending', describe_pending(ctx, root, data))
    ctx.say(ROLLBACK_OK)
    return 0


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
    if ctx.args.assume_stopped:
        return 'ok', ['process check skipped (--assume-stopped); operator asserts target is stopped'], None
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
    updates = [p for p in a.dependencies if dependency_todo(ctx, p)]
    for warning in a.dependency_warnings:
        lines.append('WARN: ' + warning)
    if getattr(ctx.args, 'update_workshop', False) and not getattr(ctx, 'workshop_updated', False):
        lines.append('--update-workshop: on apply, ask Steam for updates to every receipt-owned item before analysis')
    for plan in updates:
        lines.append('update %s from %s: %d file(s) to write, %d to remove' % (
            plan['item']['folder'], plan['source'], len(plan['writes']), len(plan['removes'])))
    blockers = [p for p in a.dependencies if p['state'] == 'downgrade' or
                ((p['edited'] or p['unrecorded']) and not ctx.args.repair) or
                any(r.casefold().startswith('keys/') for r in p['unrecorded'])]
    if blockers:
        return 'blocked', lines + ['%s: %s; %s' % (p['item']['folder'], p['state'],
            '; '.join(p['warnings']) if p['state'] == 'downgrade' else 'run --apply --repair; unowned root keys require reconciliation by hand')
            for p in blockers], None
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
    if a.retire_files or a.retire_dirs:
        folders = sorted({r['path'].split('/')[0] for r in a.retire_files if r['path'].startswith('@')}
                         | {d.split('/')[0] for d in a.retire_dirs})
        lines.append('retired dependencies this install put there are removed with their keys (unchanged files '
                     'only; the Workshop subscription stays harmless): %s' % ', '.join(folders))
    for path, reason in a.retire_kept:
        lines.append('kept shared key %s: %s' % (path, reason))
    if a.receipt_repaired:
        lines.append('the Workshop receipt records %d key row(s) an earlier release left orphaned; they are dropped '
                     'from it (the key files stay)' % len(a.receipt_repaired))
    if updates or a.pending or a.retire_files or a.retire_dirs or a.receipt_repaired:
        return 'planned', lines, lambda: do_workshop(ctx, a)
    lines.append('all %d dependencies are in the server folder; available receipt-owned copies are current' % len(third))
    return 'already-done', lines, None


def dependency_todo(ctx, plan):
    return (plan['state'] in ('current', 'stale', 'edited', 'unrecorded') and
            (plan['writes'] or plan['removes'] or plan.get('receipt_changed') or
             (ctx.args.repair and plan['extras'])))


def do_workshop(ctx, a):
    updates = [p for p in a.dependencies if dependency_todo(ctx, p)]
    if a.receipt_repaired and not updates:
        # Written first and journaled like every other receipt write, so the warning does not come back each run.
        manifest = ws.load_manifest()
        ws.persist_repaired_receipt(
            ctx.server, ws.load_receipt(ctx.server, {m['folder'] for m in manifest['mods'] + manifest['retired']},
                                        [Path(ctx.bundle) / 'keys'], warn=lambda _text: None),
            before_write=lambda rel, digest: record_written(ctx, rel, digest))
    if a.fetch:
        do_fetch(ctx, a)
    updates = [p for p in a.dependencies if dependency_todo(ctx, p)]
    if updates:
        # Reclassify after any fetch and immediately before applying; never use an obsolete source plan.
        receipt = ws.load_receipt(ctx.server, {i['folder'] for i in ws.load_manifest()['mods'] + ws.load_manifest()['retired']},
                                  [ctx.bundle / 'keys'], warn=ctx.say)
        plans = [ws.plan_refresh(p['item'], ctx.dirs, ctx.server, receipt, [ctx.bundle / 'keys'], say=ctx.say)
                 for p in updates]
        for p in plans:
            if p['state'] in ('content-updating', 'content-missing'):
                ctx.say('  %s: %s; folder skipped' % (p['item']['folder'], p['state']))
        plans = [p for p in plans if p['state'] not in ('content-updating', 'content-missing')]
        if plans:
            ws.apply_refresh(ctx.server, receipt, plans, lambda rel, digest: record_written(ctx, rel, digest), ctx.args.repair)
        for p in plans:
            ctx.say('  updated %s from %s: %d file(s) written, %d removed' % (
                p['item']['folder'], p['source'], len(p['writes']), len(p['removes'])))
    if a.pending:
        install_dependencies(ctx, a)
    if a.retire_files or a.retire_dirs:
        retire_dependencies(ctx, a)
    return 'done'


def retire_dependencies(ctx, a=None):
    manifest = ws.load_manifest()
    receipt = ws.load_receipt(ctx.server, {m['folder'] for m in manifest['mods'] + manifest['retired']},
                              [Path(ctx.bundle) / 'keys'], warn=ctx.say)
    removed, left = ws.retire_items(ctx.server, receipt, manifest,
                                    before_write=lambda rel, digest: record_written(ctx, rel, digest),
                                    extra_key_dirs=[Path(ctx.bundle) / 'keys'])
    ctx.owned = ctx.owned - {d for d in ctx.owned if d.split('/')[0] in {m['folder'] for m in manifest['retired']}}
    if a is not None:
        # Written down now: the receipt no longer names these folders, and the launcher step (which may run in a later
        # attempt) removes only retired folders this installer removed.
        tops = {r['path'].split('/')[0] for r in a.retire_files} | {d.split('/')[0] for d in a.retire_dirs}
        folders = {name for name in retired_folders() if name.casefold() in {top.casefold() for top in tops}}
        done = ctx.receipt.get('retired_removed')
        done = [n for n in done if isinstance(n, str)] if isinstance(done, list) else []
        ctx.receipt['retired_removed'] = sorted(set(done) | folders)
        save_receipt(ctx)
    for rel in removed:
        ctx.say('  removed retired file: ' + rel)
    for rel in left:
        ctx.say('  left in place (changed since install; remove by hand if wanted): ' + rel)


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
    todo = [r for r in a.own if r[2] in ('new', 'upgrade', 'confirm', 'repair')]
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
                '--assume-stopped', '--bundle-keys', str(Path(ctx.bundle) / 'keys')]
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


# Everything that decides the mission bytes the bundle apply writes: the overlay, the patches, the infected variants,
# the authored CE layer the loot boost scales (ce/), the optional pack CE rows (optional/), the loot-points data and settings (settings.json, families,
# additions, floor policy, new buildings), the firearms roster and the military rules the boost reads. A release that
# changes only one of these must not look "already applied": the fingerprint changes, the earlier overlay is rolled
# back (receipt-verified) and the stack is applied again from stock bytes.
OVERLAY_INPUT_PREFIXES = ('mission-overlay/', 'mission/hollow-country/loot-points/', 'mission/hollow-country/ce/',
                          'mission/hollow-country/optional/')
OVERLAY_INPUT_FILES = ('mission-patches.json', 'mission/hollow-country/infected/variants.json',
                       'tools/package/firearms_roster.json', 'tools/package/loot_families.json', 'config/military-loot.json',
                       # read by the loot boost balance: the slack table, the military route rules and the pack
                       # estimates (R4 counts the pack guns)
                       'tools/package/loot_slack.json', 'tools/package/military_loot_allowlist.json',
                       'tools/package/snafu_allowlist.json', 'tools/package/tactical_flava_allowlist.json',
                       # the code that computes the boosted bytes: a logic change reapplies even when nobody bumps
                       # LOOT_BOOST_VERSION
                       'tools/package/loot_boost.py', 'tools/package/loot_balance.py', 'tools/package/military_loot.py',
                       'tools/package/loot_slack.py', 'tools/package/ce_slot_pressure.py', 'tools/package/infected_variety.py')


def overlay_fingerprint(ctx):
    rows = [(r['path'], r['sha256']) for r in ctx.manifest['files']
            if r['path'].startswith(OVERLAY_INPUT_PREFIXES) or r['path'] in OVERLAY_INPUT_FILES]
    # LOOT_BOOST_VERSION and the infected variety GENERATOR_VERSION cover logic changes that alter the applied bytes
    # for unchanged inputs
    return sha256_bytes(json.dumps({'files': sorted(rows), 'loot_boost': loot_boost.LOOT_BOOST_VERSION,
                                    'infected_variety': infected_variety.GENERATOR_VERSION},
                                   sort_keys=True).encode())


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


GLOBALS_REL = loot_boost.GLOBALS


def _globals_vars(data):
    """(text, {var name: {span, tag}}) for db/globals.xml bytes; comments are masked, duplicates refuse."""
    loot_boost.economy.xml(data, 'variables')
    text = data.decode('utf-8-sig')
    masked = loot_boost._mask(text)
    rows = {}
    for match in re.finditer(r'<var\b[^>]*>', masked):
        name = loot_boost._attr(match.group(0), 'name')
        if name is None:
            continue
        if name in rows:
            raise ValueError('db/globals.xml sets %s more than once' % name)
        rows[name] = {'span': (match.start(), match.end()), 'tag': text[match.start():match.end()]}
    return text, rows


def _globals_norm(tag):
    return ' '.join(tag.split())


def _globals_value(tag):
    return loot_boost._attr(tag, 'value')


def globals_installed_bytes(before, row, receipt):
    """The exact bytes the loot boost wrote (verified against the receipt hash), or None."""
    candidates = []
    try:
        candidates.append(loot_boost.scale_globals(before, receipt['multiplier'])[0])
    except (ValueError, KeyError, TypeError, ArithmeticError):
        pass
    try:
        new = receipt['counts']['globals']['RespawnTypes'].split('->')[1]
        text, rows = _globals_vars(before)
        start, end = rows['RespawnTypes']['span']
        tag = re.sub(r'\bvalue="\d+"', 'value="%d"' % int(new), rows['RespawnTypes']['tag'], count=1)
        candidates.append(loot_boost._encode(loot_boost._apply(text, [(start, end, tag)]), before))
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
        pass
    try:  # every old->new change the receipt records (RespawnTypes, LootDamageMax), without the knobs behind them
        candidates.append(loot_boost.globals_from_report(before, receipt['counts']['globals']))
    except (ValueError, KeyError, TypeError, AttributeError):
        pass
    candidates.append(before)
    for data in candidates:
        if sha256_bytes(data) == row['after']:
            return data
    return None


def globals_overrides(installed, current, stock=None, optout=()):
    """({var: current tag} for values the operator changed or added, [vars the operator removed], [vars reset]).

    A loot-boosted variable whose current value equals the pre-boost (stock) value is a reset, not operator
    tuning: the boost value is applied again instead of keeping the stock one. That holds for one variable and for
    a whole file put back to stock alike (every boosted variable is then a reset). A variable in optout (the
    operator asked to keep stock values: --keep-stock-globals, recorded in the install receipt) is never a reset;
    its stock value is kept like any other operator value."""
    _text, old = _globals_vars(installed)
    _text, now = _globals_vars(current)
    overrides = {name: row['tag'] for name, row in now.items()
                 if name not in old or _globals_norm(old[name]['tag']) != _globals_norm(row['tag'])}
    resets = []
    if stock is not None:
        _text, before = _globals_vars(stock)
        for name in sorted(overrides):
            if (name not in optout and name in old and name in before and
                    _globals_value(old[name]['tag']) != _globals_value(before[name]['tag']) and
                    _globals_value(overrides[name]) == _globals_value(before[name]['tag'])):
                resets.append(name)
                del overrides[name]
    return overrides, sorted(name for name in old if name not in now), resets


def globals_with_overrides(data, overrides):
    """data with the operator's var tags put back (existing vars replaced in place, new ones appended)."""
    text, rows = _globals_vars(data)
    edits = [(rows[name]['span'][0], rows[name]['span'][1], tag) for name, tag in overrides.items() if name in rows]
    added = [tag for name, tag in overrides.items() if name not in rows]
    text = loot_boost._apply(text, edits)
    if added:
        end = loot_boost._mask(text).rfind('</variables>')
        if end < 0:
            raise ValueError('db/globals.xml has no closing variables tag')
        newline = '\r\n' if '\r\n' in text else '\n'
        text = text[:end] + ''.join('\t' + tag + newline for tag in added) + text[end:]
    return loot_boost._encode(text, data)


def globals_state(mission, optout=()):
    """Classify receipt-owned db/globals.xml without writing.

    none (no loot boost), clean (receipted bytes), tuned (operator values on top: carried forward on
    upgrade), missing (file absent: restored from the receipt) or blocked (evidence unusable).
    """
    state = {'state': 'none', 'prev': None, 'overrides': {}, 'removed': [], 'resets': [], 'problem': None,
             'changes': [], 'optout': []}
    managed = mission / loot_boost.MANAGED
    if not managed.exists():
        return state

    def blocked(problem):
        state.update(state='blocked', problem=problem)
        return state
    try:
        loot_boost._preflight(managed)
        receipt = loot_boost._receipt(managed)
        if receipt is None:
            return blocked('loot boost receipt unreadable')
        rows = [row for row in receipt['files'] if row['name'] == GLOBALS_REL]
        if not rows:
            return state
        row = rows[0]
        backup = loot_boost.economy.read_plain(managed, row['backup'])
        if sha256_bytes(backup) != row['before']:
            return blocked('loot boost backup of db/globals.xml is missing or changed')
        prev = globals_installed_bytes(backup, row, receipt)
        if prev is None:
            return blocked('db/globals.xml loot boost bytes cannot be reproduced from the receipt')
        state['prev'] = prev
        if not os.path.lexists(mission / GLOBALS_REL):
            state['state'] = 'missing'
            return state
        current = loot_boost.economy.read_plain(mission, GLOBALS_REL)
        if sha256_bytes(current) == row['after']:
            state['state'] = 'clean'
            return state
        # Not the bytes the boost wrote. That includes the stock file put back whole (row['before']): it is read
        # like any other reset, so one stock variable and the whole file behave the same.
        overrides, removed, resets = globals_overrides(prev, current, backup, optout)
        _text, old = _globals_vars(prev)
        state.update(state='tuned', overrides=overrides, removed=removed, resets=resets, current=sha256_bytes(current),
                     optout=sorted(name for name in optout if name in overrides))
        state['changes'] = ['%s %s -> %s' % (name, _globals_value(old[name]['tag']) if name in old else 'absent',
                                            _globals_value(tag)) for name, tag in overrides.items()]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        return blocked('loot boost globals evidence unreadable (%s)' % shown(error))
    return state


def ctx_globals(ctx, mission):
    """globals_state with this server's recorded opt-outs. --keep-stock-globals records every variable that is
    currently reset to stock as an opt-out in the install receipt (saved by the step that writes the receipt), so
    later runs keep the stock value instead of applying the loot boost again."""
    optout = set(ctx.receipt.get('globals_optout') or [])
    state = globals_state(mission, optout)
    if getattr(ctx.args, 'keep_stock_globals', False) and state['resets']:
        optout |= set(state['resets'])
        ctx.receipt['globals_optout'] = sorted(optout)
        ctx.optout_new = True
        state = globals_state(mission, optout)
    return state


def globals_upgrade_problem(mission):
    """Why receipt-owned globals cannot be carried through an upgrade; None when they can (including operator
    tuning, which globals_state keeps and the overlay step re-applies)."""
    return globals_state(mission)['problem']


def globals_digest(state):
    return sha256_bytes(json.dumps([state['state'], state['overrides'], state['removed'], state.get('resets', []),
                                    state.get('current')], sort_keys=True).encode())


def globals_lines(state, replacing):
    if state['state'] == 'tuned':
        lines = []
        if state['changes'] or not state.get('resets'):
            names = ', '.join(state['changes']) or 'formatting only'
            lines.append('db/globals.xml carries operator values (%s)' % names)
            lines.append('they are carried forward onto the new loot boost values; the file is backed up first'
                         if replacing else 'they are kept as they are')
        for name in state['removed']:
            lines.append('WARN  globals  %s was removed by the operator; the stock variable returns on upgrade' % name)
        for name in state.get('resets', ()):
            lines.append('WARN  globals  %s is back at its stock value (a reset, not operator tuning); the loot boost '
                         'value is applied again (--keep-stock-globals keeps the stock value and records that choice)'
                         % name)
        for name in state.get('optout', ()):
            lines.append('globals  %s stays at its stock value: you opted out of the loot boost for it '
                         '(--keep-stock-globals, recorded in the install receipt)' % name)
        return lines
    if state['state'] == 'missing':
        return ['db/globals.xml is missing; it is restored from the loot boost receipt (nothing else changes)']
    return []


def write_globals(ctx, mission, data):
    rel = (mission / GLOBALS_REL).relative_to(ctx.server).as_posix()
    record_written(ctx, rel, sha256_bytes(data))
    (mission / GLOBALS_REL).parent.mkdir(parents=True, exist_ok=True)
    ws.write_bytes_atomic(mission / GLOBALS_REL, data)


def globals_heal(ctx, mission):
    """Restore a missing db/globals.xml to the receipted bytes, or put the loot boost value back on variables that
    were reset to stock (the operator's own values stay on top). Idempotent."""
    state = ctx_globals(ctx, mission)
    if state['state'] == 'missing':
        write_globals(ctx, mission, state['prev'])
        return True
    if state['state'] == 'tuned' and state['resets']:
        write_globals(ctx, mission, globals_with_overrides(state['prev'], state['overrides']))
        return True
    return False


def globals_recovery(mission):
    """Executable PowerShell recovery on an absent copy; original tuning stays backed up."""
    quote = lambda path: "'" + str(path).replace("'", "''") + "'"
    copy = mission.with_name(mission.name + '.hc-recovery')
    lines = ['Stop only the target server. Save the desired db/globals.xml values; recovery restores originals.',
             'Run these PowerShell commands from this bundle; recovery destination must not exist:',
             '$MISSION = ' + quote(mission), '$RECOVERY = ' + quote(copy),
             "if (Test-Path -LiteralPath $RECOVERY) { throw 'Recovery destination already exists' }",
             'Copy-Item -Recurse -LiteralPath $MISSION -Destination $RECOVERY -ErrorAction Stop']
    for writer, module, option in (
            (hc_events, 'hc_events', '--mission'),
            (tactical_flava_optional, 'tactical_flava_optional', '--target'),
            (snafu_optional, 'snafu_optional', '--target'),
            (map_overlay, 'map_overlay', '--target'),
            (infected_variety, 'infected_variety', '--mission')):
        if (mission / writer.MANAGED).exists():
            lines.append('py -3 -m tools.package.%s rollback %s "$RECOVERY"' % (module, option))
            lines.append("if ($LASTEXITCODE -ne 0) { throw 'Rollback refused; keep both copies' }")
    lines += ['py -3 -m tools.package.optional_overlays restore-originals --mission "$RECOVERY"',
              "if ($LASTEXITCODE -ne 0) { throw 'Recovery refused; keep both copies' }",
              'After success, move the original mission aside, put the recovery copy at the original path,',
              'rerun --plan-only, --apply --yes and --check; reapply reviewed globals tuning afterwards.',
              'Keep the original mission as the backup. Never delete receipts to bypass drift.']
    return lines


def replaced_layers(ctx, a, mission, installed):
    """The installed layers that step 5 rolls back when it replaces the mission overlay, as (label, folder, step,
    reason). They sit on top of it and patch the same files, so the mission overlay cannot be rolled back without
    them. reason is '' when the named later step of this run installs the layer again, else why it cannot: a run
    never leaves fewer installed layers than it started with."""
    rows = []
    fetching = {i['id'] for i in a.fetch} if 'workshop' not in ctx.skip else set()
    if installed and os.path.lexists(mission / map_overlay.MANAGED):
        reason = 'step 6 (map overlays) is skipped' if 'overlays-map' in ctx.skip else ''
        rows.append(('map overlay', map_overlay.MANAGED, 'overlays-map', reason))
    sources = weapon_pack_sources(ctx)
    for label, writer in (('SNAFU weapon pack', snafu_optional), ('Tactical Flava weapon pack', tactical_flava_optional)):
        if os.path.lexists(mission / writer.MANAGED):
            reason = ''
            if 'weapons' in ctx.skip:
                reason = 'step 7 (weapons) is skipped'
            elif writer.WORKSHOP_ID not in sources and writer.WORKSHOP_ID not in fetching:
                reason = 'its Workshop pack %s is not on the server or in the downloads' % writer.WORKSHOP_ID
            rows.append((label, writer.MANAGED, 'weapons', reason))
    return rows


def stack_lines(rows):
    """Plan lines saying which layers go, which are replaced and which stay."""
    lines = []
    for label, folder, step, reason in rows:
        if reason:
            lines.append('%s (%s): cannot be kept: %s' % (label, folder, reason))
        else:
            lines.append('%s (%s): rolled back here, installed again by the %s step of this run' % (label, folder, step))
    return lines


def stack_problem(rows):
    bad = [row for row in rows if row[3]]
    if not bad:
        return ''
    return ('refused before anything is changed: replacing the mission overlay rolls back the layers on top of it '
            '(they patch the same files), and this run would not install %s again: %s. Run again without that skip '
            'or with the pack available; the installed layers stay as they are until then'
            % ('it' if len(bad) == 1 else 'them', '; '.join('%s: %s' % (row[0], row[3]) for row in bad)))


def layers_stay_lines(mission):
    """One plan line when layers installed on top of the mission overlay are left exactly as they are."""
    found = [folder for folder in (map_overlay.MANAGED, snafu_optional.MANAGED, tactical_flava_optional.MANAGED)
             if os.path.lexists(mission / folder)]
    return ['layers on top of it stay installed, byte for byte: %s' % ', '.join(found)] if found else []


def plan_overlay(ctx, a):
    status, lines, action = plan_overlay_step(ctx, a)
    if ctx.optout_new and status != 'blocked':
        # The opt-out lives in the install receipt: whatever else this step does, the receipt is saved with it.
        lines.append('--keep-stock-globals: the stock values above are recorded as your choice and never boosted again')

        def record():
            result = action() if action else 'done'
            save_receipt(ctx)
            return result
        return ('planned' if status == 'already-done' else status), lines, record
    return status, lines, action


def plan_overlay_step(ctx, a):
    if 'overlay' in ctx.skip:
        return 'skipped', ['you asked to skip this step'], None
    mission = ctx.server / 'mpmissions' / ctx.manifest['mission']
    if not mission.is_dir():
        return 'blocked', ['mission folder %s was not found; start the server once with the stock mission or '
                           'check the folder' % shown(mission)], None
    lines = ['mission: %s' % shown(mission)]
    state = ctx_globals(ctx, mission)
    if state['state'] == 'blocked':
        return 'blocked', lines + [state['problem']] + globals_recovery(mission), None
    installed = (mission / overlays.BUNDLE_MANAGED).exists()
    want = overlay_fingerprint(ctx)
    replacing = not (installed and ctx.receipt.get('overlay') == want)
    lines += globals_lines(state, installed and replacing)
    ctx.globals_planned = globals_digest(state)
    if not replacing:
        lines.append('the bundle overlay is already applied (same bundle)')
        lines += layers_stay_lines(mission)
        variety = mission / infected_variety.MANAGED
        if getattr(ctx.args, 'infected_variety_off', False):
            if variety.exists():
                return 'planned', lines + ['restore infected variety backup (off)'], lambda: do_variety(ctx, mission)
        else:
            if not variety.exists():
                return 'planned', lines + ['apply infected variety after the existing mission overlay'], lambda: do_variety(ctx, mission)
            receipt = infected_variety.check(mission)
            season = infected_variety.season_from_profile(ctx.server / 'profiles')
            if receipt.get('season') != season:
                return 'planned', lines + ['refresh infected variety for the current season'], lambda: do_variety(ctx, mission)
        if state['state'] == 'missing' or (state['state'] == 'tuned' and state['resets']):
            return 'planned', lines, lambda: do_variety(ctx, mission, variety=False)
        return 'already-done', lines, None
    pack_dir, missing = overlay_pack_dir(ctx)
    fetching = {i['id'] for i in a.fetch} if 'workshop' not in ctx.skip else set()
    missing = [m for m in missing if m not in fetching]
    if missing:
        return 'blocked', lines + ['these default Workshop packs are not downloaded: %s' % ', '.join(missing)], None
    stack = replaced_layers(ctx, a, mission, installed)
    ctx.replaced_plan = {row[2]: row[0] for row in stack}
    if installed:
        lines.append('an overlay from an earlier bundle is applied; it is rolled back first (rollback restores the '
                     'files it changed), then the new bundle is planned and applied')
    lines += stack_lines(stack)
    stuck = stack_problem(stack)
    if stuck:
        return 'blocked', lines + [stuck], None
    if not installed:
        code, text, err = run_overlay(ctx, ['bundle-plan', '--bundle', str(ctx.bundle), '--mission', str(mission)])
        if code != 0:
            return 'blocked', lines + ['bundle-plan refused: %s' % err.strip()], None
        shown_lines = [line for line in text.splitlines() if line.strip()]
        lines += shown_lines[:12]
        if len(shown_lines) > 12:
            lines.append('... and %d more overlay files' % (len(shown_lines) - 12))
        ctx.overlay_planned = True
    return 'planned', lines, lambda: do_overlay(ctx, a, mission, installed, want)


def do_variety(ctx, mission, variety=True):
    with tree_writer(ctx, mission):
        globals_heal(ctx, mission)
        if variety:
            infected_variety.install(mission, off=getattr(ctx.args, 'infected_variety_off', False),
                                     season=infected_variety.season_from_profile(ctx.server / 'profiles'))
    return 'done'


def do_overlay(ctx, a, mission, installed, want):
    with tree_writer(ctx, mission):
        return _do_overlay_with_variety(ctx, a, mission, installed, want)


def _do_overlay_with_variety(ctx, a, mission, installed, want):
    for label, folder, step, reason in replaced_layers(ctx, a, mission, installed):
        if reason:
            # pre_apply and the plan refuse first; this keeps the rule even if a caller skipped them
            raise Refused('overlay_layers', stack_problem([(label, folder, step, reason)]))
        ctx.replaced_done[step] = label
    # Encounters snapshot CE geometry above the map and weapon layers.
    hc_events.rollback(mission)
    # Weapon layers are installed after the base overlay and must be removed first.
    tactical_flava_optional.rollback_weapon_packs(mission)
    # Infected variety is the last events.xml layer: undo it before habitat rollback.
    infected_variety.rollback(mission)
    if installed and os.path.lexists(mission / map_overlay.MANAGED):
        # the map overlay patched the same cfggameplay.json; the mission rollback refuses while it is in place
        code, text, err = run_map(ctx, ['rollback', '--target', str(mission)])
        if code != 0:
            raise Refused('overlay', 'the map overlay must be rolled back before the mission overlay is replaced, and '
                          'its rollback was refused: %s' % err.strip())
    state = ctx_globals(ctx, mission)
    if state['state'] == 'blocked':
        raise Refused('globals_drift', '\n'.join([state['problem']] + globals_recovery(mission)))
    planned = getattr(ctx, 'globals_planned', None)
    if planned is not None and planned != globals_digest(state):
        raise Refused('drift', 'db/globals.xml changed while this run was waiting; nothing was written to it. Run the '
                      'installer again so it carries the file as it is now')
    carry = {}
    if installed and state['state'] in ('tuned', 'missing'):
        # The loot boost rollback only restores bytes it wrote: put its receipted bytes back first (journaled and
        # backed up), then re-apply the operator's values on top of the new loot boost output below.
        carry = dict(state['overrides'])
        write_globals(ctx, mission, state['prev'])
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
    infected_variety.install(mission, off=getattr(ctx.args, 'infected_variety_off', False),
                             season=infected_variety.season_from_profile(ctx.server / 'profiles'))
    if carry:
        fresh = loot_boost.economy.read_plain(mission, GLOBALS_REL)
        merged = globals_with_overrides(fresh, carry)
        if merged != fresh:
            write_globals(ctx, mission, merged)
    ctx.receipt['overlay'] = want
    save_receipt(ctx)
    return 'done'


def weapon_pack_sources(ctx):
    """Verify loaded server PBOs; read omitted terms/vendor XML from Workshop."""
    packs = {}
    for writer in (snafu_optional, tactical_flava_optional):
        item = next((item for item in ctx.items if item['id'] == writer.WORKSHOP_ID), None)
        if item is None:
            continue
        downloaded = next((directory / writer.WORKSHOP_ID for directory in ctx.dirs
                           if (directory / writer.WORKSHOP_ID).is_dir()), None)
        loaded = ctx.server / item['folder']
        if loaded.is_dir():
            packs[writer.WORKSHOP_ID] = {'install': loaded, 'evidence': downloaded or loaded}
        elif downloaded is not None:
            packs[writer.WORKSHOP_ID] = downloaded
    return packs


def plan_weapons(ctx, a):
    mission = ctx.server / 'mpmissions' / ctx.manifest['mission']
    if 'weapons' in ctx.skip or 'overlay' in ctx.skip:
        lines = ['you asked to skip mission/weapon installation']
        for label, writer in (('SNAFU', snafu_optional), ('Tactical Flava', tactical_flava_optional)):
            if os.path.lexists(mission / writer.MANAGED):
                lines.append('the installed %s weapon pack (%s) stays as it is, byte for byte' % (label, writer.MANAGED))
        return 'skipped', lines, None
    if not mission.is_dir():
        return 'blocked', ['stock mission is missing'], None
    packs = weapon_pack_sources(ctx)
    lines = []
    for label, writer in (('SNAFU', snafu_optional), ('TF', tactical_flava_optional)):
        present = writer.WORKSHOP_ID in packs
        lines.append('optional weapons %s: %s' % (label,
                     'verify -> generate -> install (default on)' if present else 'absent; skip cleanly'))
    # Run after Workshop fetch/copy too: a missing pack at planning time may appear there.
    return 'planned', lines, lambda: do_weapons(ctx, mission)


def do_weapons(ctx, mission):
    with tree_writer(ctx, mission):
        # Rehearse on scratch before changing the mission; verify report files are
        # outside Git even when the operator runs this installer from a checkout.
        with tempfile.TemporaryDirectory(prefix='hc-weapon-packs-') as temporary:
            root = Path(temporary)
            scratch = root / 'mission'
            shutil.copytree(mission, scratch, ignore=shutil.ignore_patterns('storage_*'))
            packs = weapon_pack_sources(ctx)
            hc_events.rollback(scratch)
            tactical_flava_optional.rollback_weapon_packs(scratch)
            failures = tactical_flava_optional.apply_weapon_packs(
                scratch, packs, ctx.server / 'addons', root / 'rehearsal', ctx.say)
            if failures:
                raise Refused('weapons', 'weapon pack rehearsal refused: ' + ', '.join(failures))
            hc_events.install(ctx.bundle / 'mission/hollow-country', scratch)
            # If every generated byte matches, preserve the existing receipts and backups.
            def images(target):
                names = ['cfgeconomycore.xml', *sorted(hc_events.TARGETS),
                         hc_events.MANAGED + '/receipt.json']
                for writer in (snafu_optional, tactical_flava_optional):
                    managed = target / writer.MANAGED
                    names += [path.relative_to(target).as_posix() for path in managed.rglob('*') if path.is_file()]
                return {name: (target / name).read_bytes() if (target / name).exists() else None
                        for name in names}
            if images(scratch) == images(mission):
                ctx.say('optional weapons: already installed; verified bytes match')
                return 'already-done'
            hc_events.rollback(mission)
            tactical_flava_optional.rollback_weapon_packs(mission)
            failures = tactical_flava_optional.apply_weapon_packs(
                mission, packs, ctx.server / 'addons', root / 'install', ctx.say)
            if failures:
                raise Refused('weapons', 'weapon pack install refused: ' + ', '.join(failures))
            hc_events.install(ctx.bundle / 'mission/hollow-country', mission)
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
        lines = ['you asked to skip this step']
        if os.path.lexists(map_mission(ctx) / map_overlay.MANAGED):
            lines.append('the installed map overlay (%s) stays as it is, byte for byte' % map_overlay.MANAGED)
        return 'skipped', lines, None
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
    # A dry run does not apply step 5, so it must say what step 5 will do to the installed map overlay.
    popped = ctx.statuses.get('overlay') == 'planned' and 'overlays-map' in ctx.replaced_plan and state != 'none'
    if popped:
        state = 'different'
        lines.append('step 5 rolls the installed map overlay back first (the mission overlay it sits on is replaced); '
                     'this step installs the bundle layers again')
    if state == 'same':
        lines.append('the map overlay is installed and intact (same layer set); it stays as it is')
        return 'already-done', lines, None
    present = all((mission / name).is_file() for name in map_overlay.INPUTS + ('mapgroupproto.xml',))
    waiting = ctx.statuses.get('overlay') == 'planned' and not present
    if state == 'different' and not popped:
        lines.append('a map overlay from a different layer set is installed; it is replaced: rolled back first '
                     '(byte-exact restore of cfggameplay.json and mapgrouppos.xml), then the new layers are installed')
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
    # Every mission write here (hc_events and weapon-pack rollbacks, hc_events install)
    # must be fingerprinted, or recovery refuses those bytes as unknown.
    with tree_writer(ctx, mission):
        hc_events.rollback(mission)
        # Weapon receipts snapshot map inputs; remove them before replacing those bytes.
        tactical_flava_optional.rollback_weapon_packs(mission)
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
        hc_events.install(ctx.bundle / 'mission/hollow-country', mission)
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
            lines.append('merge the Hollow Country keys into %s (operator fields kept for HC settings, backup first)' % rel)
        elif action == 'same' and rel in MERGE_PROFILES:
            lines.append('%s: baseline keys present; operator fields kept' % rel)
        elif action == 'new' and rel in MERGE_PROFILES - MISSING_ONLY_PROFILES:
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
        target = ctx.server / rel
        if target.is_file() and sha256_file(target) != sha:
            # The operator's own launcher with the right -mod= values: kept as it is.
            ctx.receipt['files'].setdefault(rel, sha256_file(target))
            ctx.receipt['launcher_merged'] = True
            lines.append('your own launcher is kept: its -mod=/-serverMod= values already match the bundle')
            keep = {mod_leaf(name).casefold() for name in launcher_retired(ctx)[1]}
            warned = [name for name in live_mod_list(target.read_text(encoding='utf-8', errors='replace'))
                      if mod_leaf(name).casefold() in keep]
            lines += launcher_change_lines([{'arg': 'mod', 'added': [], 'removed': [], 'kept': [], 'unowned': warned}],
                                           ctx.retire_reasons)
            pruned = prune_retired_removed(ctx, target.read_text(encoding='utf-8', errors='replace'))
        else:
            ctx.receipt['files'].setdefault(rel, sha)
            pruned = prune_retired_removed(ctx, target.read_text(encoding='utf-8', errors='replace')
                                           if target.is_file() else '')
        if pruned and ctx.args.apply:
            save_receipt(ctx)
        return 'already-done', lines, None
    return 'planned', lines, lambda: do_launcher(ctx, a)


def do_launcher(ctx, a):
    """Write start-server.bat: the bundle file when none is there (or an unedited older bundle's), otherwise only
    the -mod=/-serverMod= lists merged into the operator's file. The old bytes are journaled and backed up first.
    An edited or unrecorded launcher that cannot be merged is never replaced."""
    rel, source, action, sha = a.launcher
    target = ctx.server / rel
    if action != 'new' and target.is_file():
        current = target.read_bytes()
        pristine = action == 'upgrade' and not ctx.receipt.get('launcher_merged')
        if not pristine:
            retired = launcher_retired(ctx)
            present = launcher_present(ctx)
            problem = launcher_problem(current, source.read_bytes(), *retired, present=present)
            if problem:
                raise Refused('launcher', '%s %s; it is never replaced wholesale: fix it by hand or move it away'
                              % (rel, problem))
            data = merge_launcher(current, source.read_bytes(), *retired, present=present)[0]
            record_written(ctx, rel, sha256_bytes(data))
            ws.write_bytes_atomic(target, data)
            ctx.receipt['files'][rel] = sha256_bytes(data)
            ctx.receipt['launcher_merged'] = True
            prune_retired_removed(ctx, data.decode('utf-8'))
            save_receipt(ctx)
            return 'done'
    ctx.receipt.pop('launcher_merged', None)
    prune_retired_removed(ctx, source.read_bytes().decode('utf-8', errors='replace'))
    return do_files(ctx, [a.launcher])


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


PLANNERS = {'weapons': plan_weapons, 'server': plan_server, 'stopped': plan_stopped, 'workshop': plan_workshop, 'mods': plan_mods,
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
    try:
        analysis = analyze(ctx)
        say_repairs(ctx, repair_rows(ctx, analysis), False)
        failures = ['%s: %s; %s' % (p['item']['folder'], p['state'],
                    '--apply' if p['state'] == 'stale' else '--apply --repair' if p['state'] in ('edited', 'unrecorded')
                    else 'use a newer Workshop source; downgrade refused')
                    for p in analysis.dependencies if p['state'] in ('stale', 'edited', 'unrecorded', 'downgrade')]
        result('dependency_versions', failures, 'every available receipt-owned dependency is current')
        for warning in analysis.dependency_warnings:
            say('WARN  dependency_versions  ' + warning)
    except (Refused, ws.SyncError, OSError, ValueError) as error:
        result('dependency_versions', ['analysis unavailable: %s' % shown(error)], '')
        say('WARN  repair_preview  unavailable: %s' % shown(error))
    if 'overlay' not in ctx.skip:
        mission = map_mission(ctx)
        problem = globals_upgrade_problem(mission)
        result('globals_upgrade', [problem] if problem else [], 'receipt-owned globals have no drift')
        if problem:
            for line in globals_recovery(mission):
                say(line)
    missing = []
    for folder in expected:
        addons = server / folder / 'addons'
        if not addons.is_dir() or not any(p.suffix.lower() == '.pbo' for p in addons.iterdir()):
            missing.append('missing_mod_folder: %s' % folder)
    result('mod_folders', missing, '%d mod folders present with signed PBOs' % len(expected))
    # Our own folders must be this bundle's bytes: a rolled-back or older install
    # still has signed PBOs, so presence alone cannot prove which build will load.
    problems = []
    own_count = 0
    for folder in ('@HollowCountry', '@HollowCountryExpansionAI'):
        rows = bundle_walk(ctx.bundle, ctx.manifest, folder)
        own_count += len(rows)
        for rel, source in rows:
            target = server / rel
            if not target.is_file():
                problems.append('own_file_missing: ' + rel)
            elif sha256_file(target) != sha256_file(source):
                problems.append('own_file_differs: ' + rel)
        listed = {rel.casefold() for rel, _ in rows}
        addons = server / folder / 'addons'
        if rows and addons.is_dir():
            for path in sorted(addons.iterdir()):
                rel = folder + '/addons/' + path.name
                if path.is_file() and path.suffix.lower() == '.pbo' and rel.casefold() not in listed:
                    problems.append('own_pbo_not_in_bundle: ' + rel)
    result('own_mod_bytes', problems, '%d own mod files match this bundle' % own_count)
    # The signed guard is an ordinary HCX addon: analyze() copies it and moves its
    # old PBO/signatures to backup when a later bundle no longer ships the pack.
    guard_rel = '@HollowCountryExpansionAI/addons/hollowcountry_weapon_pack_guards.pbo'
    guard_rows = [(rel, source) for rel, source in bundle_walk(ctx.bundle, ctx.manifest,
                  '@HollowCountryExpansionAI') if rel.casefold() == guard_rel.casefold()
                  or rel.casefold().startswith(guard_rel.casefold() + '.')]
    problems = []
    for rel, source in guard_rows:
        target = server / rel
        if not target.is_file() or sha256_file(target) != sha256_file(source):
            problems.append('guard_missing_or_changed: ' + rel)
    guard_addons = server / '@HollowCountryExpansionAI/addons'
    wanted = {rel.casefold() for rel, _ in guard_rows}
    if guard_addons.is_dir():
        for path in guard_addons.iterdir():
            rel = '@HollowCountryExpansionAI/addons/' + path.name
            if (path.is_file() and (rel.casefold() == guard_rel.casefold()
                    or rel.casefold().startswith(guard_rel.casefold() + '.'))
                    and rel.casefold() not in wanted):
                problems.append('stale_guard: ' + rel)
    result('weapon_pack_guard', problems, 'signed guard matches bundle' if guard_rows else 'guard absent')
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
        launcher_text = live.read_text(encoding='utf-8', errors='replace')
        problem = live_launcher_problem(launcher_text)
        actual = live_mod_list(launcher_text)
        if problem:
            result('mod_order', ['launcher_problem: start-server.bat %s' % problem], '')
        elif actual[:len(expected)] != expected:
            diff = next((i for i, (x, y) in enumerate(zip(actual, expected)) if x != y), min(len(actual), len(expected)))
            result('mod_order', ['wrong_mod_order: differs from the bundle at position %d' % (diff + 1)], '')
        else:
            extras = len(actual) - len(expected)
            result('mod_order', [], '-mod order matches the bundle (%d mods%s)' % (
                len(expected), ', then %d of your own' % extras if extras else ''))
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
    mission = map_mission(ctx)
    variety_problems = []
    if getattr(ctx.args, 'infected_variety_off', False):
        if (mission / infected_variety.MANAGED).exists():
            variety_problems.append('infected variety receipt remains; run --apply with --infected-variety-off')
        variety_good = 'off; no variety receipt'
    else:
        try:
            infected_variety.check(mission)
        except (OSError, ValueError, KeyError, TypeError):
            variety_problems.append('missing, outdated or damaged variety receipt; reconcile or run the installer')
        variety_good = 'receipt and events.xml intact; policy matches; runtime=PENDING'
    result('infected_variety', variety_problems, variety_good)
    ctx.dirs = content_dirs(ctx, ctx.server)
    try:
        weapon_layers = tactical_flava_optional.check_weapon_packs(mission, weapon_pack_sources(ctx))
        result('optional_weapons', [], 'verified receipts and rollback: ' + ', '.join(weapon_layers) + '; runtime=PENDING')
    except (OSError, ValueError, KeyError, TypeError):
        result('optional_weapons', ['missing, outdated or damaged weapon layer; run the installer'], '')
    # CF_XML reads mission XML with native FGets; a 217,826-character line crashed build 150 at boot.
    wide = []
    for path in sorted(mission.rglob('*.xml')) if mission.is_dir() else ():
        with path.open('rb') as handle:
            width = max((len(line.rstrip(b'\r\n')) for line in handle), default=0)
        if width > xml_text.MAX_LINE:
            wide.append('%s: %d-byte line' % (path.relative_to(mission).as_posix(), width))
    result('xml_line_bound', wide, 'every mission XML line is at most %d bytes' % xml_text.MAX_LINE)
    try:
        if not all((mission / name).is_file() for name in ce_slot_pressure.INPUTS):
            raise FileNotFoundError('proxy map')
        pressure = ce_slot_pressure.problems(mission)
        result('ce_slot_pressure', pressure, 'weapon nominal fits proxy slots (limit %.2f, offline estimate)'
               % ce_slot_pressure.LIMIT)
    except FileNotFoundError:
        result('ce_slot_pressure', [], 'skipped: mission has no proxy map files to estimate')
    except (OSError, ValueError, KeyError, TypeError, SyntaxError, ce_slot_pressure.struct.error):
        result('ce_slot_pressure', ['mission CE files unreadable for the slot estimate'], '')
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
    if args.assume_stopped:
        return
    if running:
        raise Refused('server_running', 'a DayZ server process is running; stop it yourself first (this tool never '
                      'stops anything)')
    if running is None and not args.assume_stopped:
        answer = ctx.ask('The process list cannot be read. Type yes only if the DayZ server is stopped: ')
        if (answer or '').strip().lower() != 'yes':
            raise Refused('server_state_unknown', 'cannot tell whether the DayZ server is running; stop it and pass '
                          '--assume-stopped')


def prepare_workshop_fetch(ctx):
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


def pre_apply(ctx, a):
    """Every refusal that can be known before the first write."""
    args = ctx.args
    require_stopped(ctx, a.running)
    if 'workshop' not in ctx.skip:
        status, lines, _action = plan_workshop(ctx, a)
        if status == 'blocked':
            raise Refused('workshop', '; '.join(lines))
    if 'overlay' not in ctx.skip:
        mission = map_mission(ctx)
        problem = globals_upgrade_problem(mission)
        if problem:
            raise Refused('globals_drift', '\n'.join([problem] + globals_recovery(mission)))
    if 'workshop' not in ctx.skip and a.fetch:
        prepare_workshop_fetch(ctx)
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
    if a.launcher_blocked:
        raise Refused('launcher', a.launcher_blocked)
    if drift:
        raise Refused('drift', 'changed since this installer wrote them: %s; run again with --repair to restore them '
                      '(each is copied to %s first; an edited start-server.bat only has its -mod=/-serverMod= lists '
                      'merged), or restore or move them away yourself' % (', '.join(drift[:8]), BACKUP_DIR))
    confirm = [r[0] for r in a.own + a.profiles if r[2] == 'confirm']
    if a.launcher and a.launcher[2] == 'confirm':
        confirm.append(a.launcher[0])
    if 'overlay' not in ctx.skip:
        mission = ctx.server / 'mpmissions' / ctx.manifest['mission']
        if mission.is_dir() and (mission / overlays.BUNDLE_MANAGED).exists() and \
                ctx.receipt.get('overlay') != overlay_fingerprint(ctx):
            confirm.append('mission overlay from an earlier bundle (rolled back first)')
            stuck = stack_problem(replaced_layers(ctx, a, mission, True))
            if stuck:
                raise Refused('overlay_layers', stuck)
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


REPAIR_KEEP = 10


def repair_rows(ctx, a):
    """Everything --apply (with --repair for blocked rows) heals, from one place: the dry run, --check and the
    receipt print exactly these rows."""
    rows = list(getattr(ctx, 'repair_extra', [])) + list(a.repairs)
    if 'overlay' not in ctx.skip:
        mission = map_mission(ctx)
        if mission.is_dir():
            state = ctx_globals(ctx, mission)
            installed = (mission / overlays.BUNDLE_MANAGED).exists()
            replacing = installed and ctx.receipt.get('overlay') != overlay_fingerprint(ctx)
            if state['state'] == 'missing':
                rows.append(repair_row('globals', GLOBALS_REL, 'missing; restored from the loot boost receipt'))
            elif state['state'] == 'tuned' and (replacing or state['resets']):
                detail = []
                if replacing and (state['changes'] or not state['resets']):
                    detail.append('operator values carried forward: %s' % ('; '.join(state['changes']) or 'formatting only'))
                if state['resets']:
                    detail.append('reset to stock, loot boost value applied again: %s' % ', '.join(state['resets']))
                rows.append(repair_row('globals', GLOBALS_REL, '; '.join(detail)))
            elif state['state'] == 'blocked':
                rows.append(repair_row('globals', GLOBALS_REL, state['problem'], status='blocked'))
    return rows


def repair_step(row):
    if row.get('step') == 'workshop':
        return 'workshop'
    if row['path'] == LAUNCHER_REL:
        return 'launcher'
    if row['kind'] == 'globals':
        return 'overlay'
    if row['kind'] in ('missing', 'edited', 'unrecorded', 'retired'):
        return 'mods'
    return None


def say_repairs(ctx, rows, done):
    if not rows:
        ctx.say('Repair receipt: nothing to repair' if done else 'Repair preview: nothing to repair')
        return
    ctx.say('Repair receipt (what this run repaired):' if done else
            'Repair preview (what --apply%s would change):' % (' --repair' if getattr(ctx.args, 'repair', False) else ''))
    for row in rows:
        label = {'repair': 'repaired' if done else 'would repair', 'blocked': 'blocked'}[row['status']]
        ctx.say('  %s  %s  %s: %s' % (label, row['kind'], row['path'], row['detail']))
        for line in row.get('lines', ()):
            ctx.say('      ' + line)
    ctx.say()


def run_steps(ctx, apply):
    ctx.retire_cache, ctx.retire_reasons = None, {}  # a dry run's answer must not outlive it
    if apply and getattr(ctx.args, 'update_workshop', False) and 'workshop' not in ctx.skip and not getattr(ctx, 'workshop_updated', False):
        require_stopped(ctx, False if ctx.args.assume_stopped else ws.server_running(ctx.server))
        find_steamcmd(ctx)
        ctx.dirs = content_dirs(ctx, ctx.server)
        manifest = ws.load_manifest()
        receipt = ws.load_receipt(ctx.server, {m['folder'] for m in manifest['mods'] + manifest['retired']},
                                  [ctx.bundle / 'keys'], warn=ctx.say)
        owned = {d.casefold() for d in receipt['dirs']} if receipt else set()
        fetch = [i for i in manifest['mods'] if i['id'] and i['folder'].casefold() in owned]
        if fetch:
            prepare_workshop_fetch(ctx)
            request = Analysis()
            request.fetch = fetch
            do_fetch(ctx, request)
        ctx.workshop_updated = True
    a = analyze(ctx)
    ctx.say('Mode: %s' % ('apply (changes are backed up and recorded)' if apply else 'dry-run (nothing is changed)'))
    ctx.say('Server: %s' % shown(ctx.server))
    ctx.say('Bundle: %s' % shown(ctx.bundle))
    ctx.say()
    repairs = repair_rows(ctx, a)
    ctx.repair_blocked = [row for row in repairs if row['status'] == 'blocked']
    if not apply:
        say_repairs(ctx, repairs, False)
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
                if name in ('workshop', 'mods'):
                    # The later launcher step must know these folders will not be installed this run.
                    ctx.skip.add(name)
                    ctx.retire_cache, ctx.retire_reasons = None, {}
        if (stopped or status == 'skipped') and apply and name in ctx.replaced_done:
            # Step 5 already rolled this layer back for this step to install it again: the run is not left half-way.
            raise Refused('overlay_layers', 'step 5 rolled back the installed %s so the mission overlay could be '
                          'replaced, and this step would not install it again; the run is undone so the server keeps '
                          'its layers' % ctx.replaced_done[name])
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
        done = [row for row in repairs if row['status'] == 'repair' and
                ctx.statuses.get(repair_step(row), 'done') == 'done']
        if done:
            ensure_journal(ctx)  # the run folder names this entry; it exists before the first write of the run
            log = ctx.receipt.setdefault('repairs', [])
            log.append({'run': ctx.backup_root.name, 'rows': done})
            del log[:-REPAIR_KEEP]
            save_receipt(ctx)
        say_repairs(ctx, done, True)
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
    parser.add_argument('--infected-variety-off', action='store_true',
                        help='restore the infected variety backup before restart; leave the stock infected mix')
    parser.add_argument('--repair', action='store_true',
                        help='with --apply: restore edited or unrecorded files this installer owns (our mod folders, '
                             'keys, start-server.bat, Workshop dependencies) from their source, each backed up first; profiles are never '
                             'overwritten and saves are never touched')
    parser.add_argument('--keep-stock-globals', action='store_true',
                        help='db/globals.xml variables put back to their stock values stay at stock instead of '
                             'getting the loot boost again; the choice is recorded in the install receipt and kept '
                             'on every later run')
    parser.add_argument('--rollback', metavar='RUN', help='undo one completed run from hollow-country-install-backups '
                        '(dry run unless --apply; refuses when files changed since that run)')
    parser.add_argument('--check', action='store_true', help='only verify an existing install; changes nothing')
    parser.add_argument('--plan-only', action='store_true', help='dry run without offering to apply')
    parser.add_argument('--skip', default='', help='comma list of steps to skip: ' + ', '.join(SKIPPABLE))
    parser.add_argument('--adopt-profile', action='append', default=[], metavar='profiles/<file>',
                        help='adopt this exact shipped default even when hand-edited (backup first; repeatable)')
    parser.add_argument('--assume-stopped', action='store_true', help='skip the running-server check')
    parser.add_argument('--workshop-content', action='append', default=[],
                        help='a steamapps/workshop/content/221100 folder (repeatable)')
    parser.add_argument('--update-workshop', action='store_true', help='with --apply, fetch every receipt-owned Workshop item first (Steam asks for your password)')
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
            resumable = [root for root, data in runs if args.rollback == root.name
                         and data['state'] in ('rolling-back', 'rollback_pending')]
            if args.check:
                for root, data in runs:
                    ctx.say(describe_pending(ctx, root, data))
                ctx.say('check result: fail')
                return 1
            if resumable:
                # An interrupted --rollback of that run: finish it, on that run only, and install nothing.
                return rollback_named(ctx, args.rollback)
            if args.apply and not args.rollback:
                force = bool(args.repair)
                if not force and ctx.input_fn is not None and any(hard_exit_rows(data) for _root, data in runs):
                    # A typed y allows the whole-tree restore only (ctx.force_tree); it never turns on --repair, so
                    # edited mod files, keys and the launcher are still refused or kept as they are.
                    ctx.say('A mission step of an interrupted run was cut off by a hard exit; its bytes cannot be '
                            'matched one by one. The mission folder can be restored from that run\'s backup (what is '
                            'there now is kept in the run backup first).')
                    answer = ctx.ask('repair these (each backed up)? [y/N]: ')
                    if (answer or '').strip().lower() in ('y', 'yes'):
                        force = ctx.force_tree = True
                recover_runs(ctx, runs, force)
                for root, _data in runs:
                    ctx.repair_extra.append(repair_row('interrupted', root.name, 'unfinished run rolled back to its '
                                                       'backup before installing'))
            else:
                raise Refused('install_interrupted', '\n'.join(describe_pending(ctx, root, data)
                                                           for root, data in runs))
        if args.rollback:
            return rollback_named(ctx, args.rollback)
        load_run_receipt(ctx)
        if args.check:
            analyze_items(ctx)
            return run_check(ctx)
        apply = args.apply
        blocked = run_steps(ctx, apply)
        if not apply:
            ctx.say('This was a dry run: nothing was changed. Run again with --apply to install.')
            if not blocked and not args.plan_only and ctx.input_fn is not None:
                stuck = [row for row in ctx.repair_blocked if row['kind'] == 'edited'] if not args.repair else []
                if stuck:
                    # Edited managed files stop a plain --apply; --repair merges or restores them, each backed up.
                    answer = ctx.ask('repair these (each backed up)? [y/N]: ')
                    if (answer or '').strip().lower() in ('y', 'yes'):
                        args.repair = True
                        load_run_receipt(ctx)
                        run_steps(ctx, True)
                        ctx.say('Install finished. Nothing here was observed in DayZ; run --check any time.')
                    else:
                        ctx.say('Nothing was repaired or installed. Run again with --apply --repair when you are ready.')
                    return 0
                answer = ctx.ask('Apply these changes now? [y/N]: ')
                if (answer or '').strip().lower() in ('y', 'yes'):
                    load_run_receipt(ctx)
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
