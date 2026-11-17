"""One-command local test session prep for a local DayZ server and one client; standard library only.

Never launches DayZ, Wine or a network connection. It prepares files, prints the exact PowerShell
launch commands, and can undo everything it did. It reuses the existing tooling and never
reimplements it:

  mod folder      tools/package/pbo.py (structural PBO check) plus a hash-recorded copy of the built
                  addons/ (and keys/ only when signed) into a fresh @HollowCountry folder
  serverDZ.cfg    byte-exact backup plus receipt, then only the keys listed in MANAGED_KEYS change
  mission deltas  tools/package/gameplay.py and tools/package/economy.py generate/install/rollback
  markers         tools/audit/acceptance_markers.py scan_tree/plan_profile/apply_plan
  optional mods   --snafu and --tactical-flava dirs are read-only (never copied); load order SNAFU, TF, HC

    python3 tools/setup/local_test_session.py plan  --server-root /mnt/d/HollowCountryLocal/runtime-001 \\
        --mission /mnt/d/HollowCountryLocal/candidate/mpmissions/dayzOffline.chernarusplus \\
        --profiles /mnt/d/HollowCountryLocal/profiles --mod /mnt/d/HollowCountryLocal/out/@HollowCountry \\
        --mod-dest /mnt/d/HollowCountryLocal/session/@HollowCountry
    ... same arguments with `apply`, then `rollback --server-root ...`

`plan` is the default and writes nothing. Never touched: BattlEye, signature verification, passwords
and every other serverDZ.cfg line (the edit is verified line by line before it is written). Credentials
are never printed. Destinations inside this repository or any git checkout are refused, as are symlinks
and hard-linked (st_nlink > 1) managed files. Files are created with O_EXCL or temp + os.replace, and
nothing is replaced without a backup and a receipt. Nothing here establishes DayZ behavior; runtime
acceptance stays pending the owner's local session (docs/LOCAL_ACCEPTANCE_V1.md).
"""
import argparse
import difflib
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
try:
    from tools.package import pbo
except ImportError:  # executed as a script from tools/setup
    sys.path.insert(0, str(ROOT))
    from tools.package import pbo

SCHEMA = 1
STATE_NAME = 'hollow-country-local-test'
RECEIPT_NAME = 'session-receipt.json'
BACKUP_NAME = 'serverDZ.cfg.backup'
CFG_NAME = 'serverDZ.cfg'
PBO_NAME = 'hollowcountry.pbo'
MAX_BYTES = 256 * 1024 * 1024
MAX_CFG = 1024 * 1024
MISSION_ROOT = 'mission/hollow-country'
GAMEPLAY_PROFILE = MISSION_ROOT + '/gameplay-profiles/hollow-country-v1.json'
GAMEPLAY_PRESET = MISSION_ROOT + '/gear/hardscrabble.json'
ECONOMY_PROFILES = MISSION_ROOT + '/economy-profiles/'
DEFAULT_ECONOMY_PROFILE = 'contextual-pilot'
DEFAULT_CLIENT_ROOT = r'D:\SteamLibrary\steamapps\common\DayZ'
DEFAULT_TIME_ACCELERATION = 4
DEFAULT_NIGHT_ACCELERATION = 8
ACCELERATION_RANGE = (0.1, 64.0)

THIRD_PERSON_CITATION = ('native ThirdPersonMode.VEHICLES_ONLY (first person on foot, third person in vehicles): '
                         '~/.cache/hollow-country/native-scripts/scripts-1.30.164289/3_Game/Global/World.c:301 '
                         'and 4_World/Entities/DayZPlayerImplement.c:2918')
TO_CONFIRM = 'value to confirm in session'
# The only serverDZ.cfg keys this tool may change (compared case-insensitively, like the engine).
MANAGED_KEYS = ('thirdPersonView', 'disable3rdPerson', 'serverTimeAcceleration',
                'serverNightTimeAcceleration', 'enableCfgGameplayFile')
# Keys that must come out byte-identical. Their values are never printed.
PROTECTED_KEYS = ('password', 'passwordAdmin', 'BattlEye', 'verifySignatures', 'forceSameBuild',
                  'hostname', 'steamQueryPort', 'allowFilePatching')
NIGHT_HOURS = 9  # the owner's target night length, in game hours, for the printed pace estimate
NOTES = {'thirdPersonView': TO_CONFIRM + '; ' + THIRD_PERSON_CITATION,
         'disable3rdPerson': 'legacy key forced to 0 so it does not override thirdPersonView',
         'serverTimeAcceleration': 'default 4, override with --time-accel',
         'serverNightTimeAcceleration': 'default 8, override with --night-accel; the BI server docs multiply it by '
                                        'serverTimeAcceleration, so the night pace is the product',
         'enableCfgGameplayFile': 'required for the native loader to read the mission cfggameplay.json'}

# One configuration statement, matched on the masked line (comments blanked, string contents replaced).
STATEMENT = re.compile(r'^(?P<lead>[^\S\r\n]*)(?P<key>[A-Za-z_][A-Za-z0-9_]*)(?P<eq>[^\S\r\n]*=[^\S\r\n]*)'
                       r'(?P<value>[^;\r\n]*?)(?P<semi>[^\S\r\n]*;)(?P<tail>.*)$', re.DOTALL)
MARKER_NAME = re.compile(r'^[A-Za-z0-9_-]+$')
KEY_NAME = re.compile(r'^[A-Za-z0-9_.-]+\.bikey$')
MOD_FILE = re.compile(r'^(?:(?:addons|keys)/[A-Za-z0-9_.@+-]+|mod\.cpp)$')
NEXT_NAME = 'serverDZ.cfg.next'
RESTORE_NAME = 'serverDZ.cfg.restore'
MAX_KEY = 1024 * 1024
DRIVE_PATH = re.compile(r'^/mnt/([A-Za-z])(?:/(.*))?$')


class Refused(ValueError):
    """A safety rule or precondition failed; nothing further was written."""


# ---------------------------------------------------------------- safe file primitives

def sha(data):
    return hashlib.sha256(data).hexdigest()


def absolute(path):
    return Path(os.path.abspath(os.fspath(path)))


def no_links(path, what):
    """Refuse any symlink among the path and its existing ancestors (checked before resolving)."""
    path = absolute(path)
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise Refused('%s: symlink in path is forbidden (%s)' % (what, candidate.name or str(candidate)))
        if candidate.exists() and getattr(candidate.lstat(), 'st_file_attributes', 0) & 0x400:
            raise Refused('%s: Windows reparse point forbidden' % what)
    return path


def outside_checkouts(path, what, repo=ROOT):
    """Refuse a path inside this repository or any git checkout (compared after resolving)."""
    resolved = Path(os.path.realpath(absolute(path)))
    try:
        resolved.relative_to(Path(os.path.realpath(repo)))
    except ValueError:
        pass
    else:
        raise Refused('%s is inside the repository: %s' % (what, resolved))
    for candidate in (resolved, *resolved.parents):
        if (candidate / '.git').exists():
            raise Refused('%s is inside a git checkout: %s' % (what, candidate))
    return resolved


def existing_dir(path, what, repo=ROOT):
    path = no_links(path, what)
    if not path.is_dir():
        raise Refused('%s must be an existing directory: %s' % (what, path))
    outside_checkouts(path, what, repo)
    return path


def regular(path, what, links=1):
    """A plain file with exactly `links` links (one by default): symlinks, stray hard links and special files are refused."""
    path = no_links(path, what)
    try:
        info = path.lstat()
    except OSError:
        raise Refused('%s does not exist: %s' % (what, path)) from None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != links:
        raise Refused('%s must be a regular file without hard links: %s' % (what, path.name))
    return path


def read_bytes(path, what, limit=MAX_BYTES, links=1):
    path = regular(path, what, links)
    before = path.lstat()
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        current = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino) or current.st_nlink != links:
            raise Refused('%s changed while opening' % what)
        if current.st_size > limit:
            raise Refused('%s exceeds the %d byte bound' % (what, limit))
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise Refused('%s exceeds the %d byte bound' % (what, limit))
    return data


def stage_path(stage, path):
    """The staging name for a final path: derived from the path, so rollback can find a link a killed apply left."""
    return absolute(stage) / ('.stage-' + hashlib.sha256(str(absolute(path)).encode()).hexdigest()[:24])


def write_new(path, data, mode=0o600, stage=None):
    """Create a fresh file exclusively; an existing path of any kind is never opened for writing.

    With `stage` (a directory of ours) the bytes are written and fsynced there first and then hard-linked
    into place: the link fails if the final path exists and is atomic, so a partial file never appears at the
    final path. Where the filesystem cannot link (another device, no hard links), it falls back to an exclusive
    create at the final path; rollback then still deletes nothing it cannot prove by hash."""
    path = no_links(path.parent, 'directory of ' + path.name) / path.name
    if stage is not None:
        staged = stage_path(stage, path)
        if os.path.lexists(staged):  # a leftover of a killed run inside our own state directory
            if staged.is_symlink() or not staged.is_file():
                raise Refused('refusing to reuse an existing staging path: %s' % staged)
            staged.unlink()
        write_new(staged, data, mode)
        try:
            os.link(staged, path)
        except FileExistsError:
            staged.unlink()
            raise Refused('refusing to overwrite an existing path: %s' % path) from None
        except OSError:
            staged.unlink()
            return write_new(path, data, mode)
        staged.unlink()
        fsync_dir(path.parent)
        return path
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
    try:
        fd = os.open(path, flags, mode)
    except FileExistsError:
        raise Refused('refusing to overwrite an existing path: %s' % path) from None
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    fsync_dir(path.parent)
    return path


def fsync_dir(path):
    """Best effort: make a created or renamed directory entry durable (not available on every platform)."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def replace_with(path, data, mode=0o600, temp=None):
    """temp file (O_EXCL), then os.replace; the caller already holds backup + receipt.

    The temp file defaults to the same directory. Pass a temp inside the session state directory to keep
    a killed run from leaving stray files next to a managed file (the state directory is ours alone)."""
    path = absolute(path)
    temporary = absolute(temp) if temp else path.with_name('.%s.hc-tmp-%d' % (path.name, os.getpid()))
    if os.path.lexists(temporary):  # a leftover of a killed run inside our own state directory
        if temp is None or temporary.is_symlink() or not temporary.is_file():
            raise Refused('refusing to reuse an existing temp path: %s' % temporary)
        temporary.unlink()
    write_new(temporary, data, mode)
    try:
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise
    fsync_dir(path.parent)


def mode_of(path):
    return stat.S_IMODE(Path(path).lstat().st_mode)


def load_tool(name):
    """Existing tooling, imported lazily so a missing sibling is a clear refusal (tests replace this)."""
    module = {'gameplay': 'tools.package.gameplay', 'economy': 'tools.package.economy',
              'acceptance_markers': 'tools.audit.acceptance_markers'}[name]
    try:
        return importlib.import_module(module)
    except ImportError as error:
        raise Refused('required existing tool is not in this checkout: %s (%s)' % (module, error)) from None


# ---------------------------------------------------------------- Windows path rendering

def to_windows(path):
    """/mnt/d/x/y -> D:\\x\\y. Other paths come back unchanged; the caller warns about them."""
    text = os.fspath(path)
    match = DRIVE_PATH.match(text)
    if not match:
        return text, False
    rest = (match.group(2) or '').replace('/', '\\')
    return '%s:\\%s' % (match.group(1).upper(), rest), True


def ps_quote(value):
    return "'" + value.replace("'", "''") + "'"


def ps_arg(value):
    # Start-Process -ArgumentList joins elements with spaces on Windows PowerShell 5.1.
    return ps_quote('"%s"' % value if re.search(r'\s', value) else value)


# ---------------------------------------------------------------- serverDZ.cfg edit

def _number(text):
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def format_number(value):
    return '%g' % value


def desired_values(time_acceleration, night_acceleration):
    for name, value in (('--time-accel', time_acceleration), ('--night-accel', night_acceleration)):
        if not math.isfinite(value) or not ACCELERATION_RANGE[0] <= value <= ACCELERATION_RANGE[1]:
            raise Refused('%s must be within %g..%g' % (name, *ACCELERATION_RANGE))
    return {'thirdPersonView': '2', 'disable3rdPerson': '0',
            'serverTimeAcceleration': format_number(time_acceleration),
            'serverNightTimeAcceleration': format_number(night_acceleration),
            'enableCfgGameplayFile': '1'}


BOM = '\ufeff'


class Statement:
    """One top-level `key = value;` statement; every part is a slice of the original line."""

    def __init__(self, index, line, match, multiple):
        self.index, self.line, self.multiple = index, line, multiple
        self.parts = {name: line[match.start(name):match.end(name)] for name in
                      ('lead', 'key', 'eq', 'value', 'semi')}
        self.parts['tail'] = line[match.end('semi'):]

    def __getitem__(self, name):
        return self.parts[name]


def _mask(line, block):
    """Same-length copy of `line` with comments blanked and string contents replaced, plus the carried comment state.

    Strings never span lines (an unterminated one ends at the line end); `//` and `/*` inside a string are text."""
    out, position, in_string = [], 0, False
    while position < len(line):
        char = line[position]
        if block:
            if line.startswith('*/', position):
                out.append('  ')
                position, block = position + 2, False
            else:
                out.append(char if char in '\r\n' else ' ')
                position += 1
        elif in_string:
            if char == '"':
                in_string = False
                out.append(char)
            else:
                out.append(char if char in '\r\n' else 'x')
                in_string = in_string and char not in '\r\n'
            position += 1
        elif line.startswith('//', position):
            out.append(''.join(c if c in '\r\n' else ' ' for c in line[position:]))
            position = len(line)
        elif line.startswith('/*', position):
            out.append('  ')
            position, block = position + 2, True
        else:
            in_string = char == '"'
            out.append(char)
            position += 1
    return ''.join(out), block


def scan_cfg(text):
    """Return one row per line: (line, masked, depth at line start, Statement or None).

    Only statements at brace depth 0 count; braces, `;` and comment markers inside quotes, and anything inside
    comments, are not syntax. `text` must not start with a byte order mark (see split_bom)."""
    rows, depth, block = [], 0, False
    for index, line in enumerate(text.splitlines(keepends=True)):
        masked, block_after = _mask(line, block)
        statement = None
        if depth == 0 and not masked.lstrip().startswith('class'):
            match = STATEMENT.match(masked)
            if match:
                statement = Statement(index, line, match, bool(masked[match.end('semi'):].strip()))
        rows.append((line, masked, depth, statement))
        depth += masked.count('{') - masked.count('}')
        block = block_after
    return rows


def split_bom(text):
    return (BOM, text[1:]) if text.startswith(BOM) else ('', text)


def _statements(text):
    return [row[3] for row in scan_cfg(text) if row[3]]


def edit_cfg(text, values):
    """Return (new_text, changes). Only the keys in `values` change; others are byte-identical."""
    bom, body = split_bom(text)
    rows = scan_cfg(body)
    if len(rows) > 20000:
        raise Refused('serverDZ.cfg has an implausible line count')
    lines = [row[0] for row in rows]
    eol = '\r\n' if lines and lines[0].endswith('\r\n') else '\n'
    wanted = {key.lower(): (key, value) for key, value in values.items()}
    found = {}
    for row in rows:
        statement = row[3]
        if statement and statement['key'].lower() in wanted:
            if statement.multiple:
                raise Refused('serverDZ.cfg line %d holds several statements; split it by hand first' % (statement.index + 1))
            key = statement['key'].lower()
            if key in found:
                raise Refused('serverDZ.cfg sets %s more than once; resolve it by hand first' % statement['key'])
            found[key] = statement
    changes, additions = [], []
    for key, (name, value) in wanted.items():
        if key in found:
            statement = found[key]
            old = statement['value'].strip()
            same = (old == value) or (_number(old) is not None and _number(old) == _number(value))
            changes.append({'key': statement['key'], 'before': old, 'after': old if same else value,
                            'action': 'unchanged' if same else 'replace', 'note': NOTES[name]})
            if not same:
                line = lines[statement.index]
                lines[statement.index] = (statement['lead'] + statement['key'] + statement['eq'] + value
                                          + statement['semi'] + statement['tail'])
                if not lines[statement.index].endswith(('\n', '\r')) and line.endswith(('\n', '\r')):
                    lines[statement.index] += eol
        else:
            changes.append({'key': name, 'before': None, 'after': value, 'action': 'insert', 'note': NOTES[name]})
            additions.append('%s = %s;%s' % (name, value, eol))
    if additions:
        position = len(lines)
        for index, (_, masked, depth, _) in enumerate(rows):  # before the first top-level class block
            if depth == 0 and masked.lstrip().startswith('class'):
                position = index
                break
        if position == len(lines) and lines and not lines[-1].endswith(('\n', '\r')):
            lines[-1] += eol
        lines[position:position] = additions
    new = bom + ''.join(lines)
    check_only_managed(text, new)
    return new, changes


def _row_keys(text):
    return [(row[0], row[3]['key'].lower() if row[3] else None) for row in scan_cfg(text)]


def check_only_managed(before, after):
    """Defensive: every differing line, old or new, must be a managed key; protected lines are identical."""
    managed = {key.lower() for key in MANAGED_KEYS}
    (old_bom, old_body), (new_bom, new_body) = split_bom(before), split_bom(after)
    if old_bom != new_bom:
        raise Refused('serverDZ.cfg edit would change the byte order mark')
    old, new = _row_keys(old_body), _row_keys(new_body)
    for tag, a1, a2, b1, b2 in difflib.SequenceMatcher(None, [r[0] for r in old], [r[0] for r in new],
                                                       autojunk=False).get_opcodes():
        if tag == 'equal':
            continue
        for _, key in old[a1:a2] + new[b1:b2]:
            if key not in managed:
                raise Refused('serverDZ.cfg edit would change a line outside the managed keys')
    for key in PROTECTED_KEYS:
        lowered = key.lower()
        a = [line for line, name in old if name == lowered]
        b = [line for line, name in new if name == lowered]
        if a != b:
            raise Refused('serverDZ.cfg edit would change protected key %s' % key)


def cfg_facts(text):
    """Credential-free facts for warnings (never a value of a password key)."""
    facts = {}
    for statement in _statements(split_bom(text)[1]):
        key, value = statement['key'].lower(), statement['value'].strip()
        if key == 'password':
            facts['password_set'] = value.strip('"') != ''
        elif key == 'verifysignatures':
            facts['verifySignatures'] = value
        elif key == 'battleye':
            facts['BattlEye'] = value
    return facts



# ---------------------------------------------------------------- mod folder

def _optional(path, what):
    try:
        path.lstat()
    except FileNotFoundError:
        return None
    return regular(path, what)


def plan_mod(source, destination, repo=ROOT):
    """Collect (relative name -> source path) for the new mod folder; verify the PBO structurally."""
    source = no_links(source, 'built mod')
    files, signed = {}, False
    if source.is_file():
        files['addons/' + PBO_NAME] = regular(source, 'built PBO')
    elif source.is_dir():
        addons = source / 'addons'
        files['addons/' + PBO_NAME] = regular(addons / PBO_NAME, 'built addons/' + PBO_NAME)
        signatures = sorted(p for p in addons.iterdir() if re.fullmatch(re.escape(PBO_NAME) + r'\.[A-Za-z0-9_-]+\.bisign', p.name))
        keys = sorted(p for p in (source / 'keys').iterdir() if p.suffix == '.bikey') if (source / 'keys').is_dir() else []
        for path in signatures:
            files['addons/' + path.name] = regular(path, 'signature ' + path.name)
        for path in keys:
            files['keys/' + path.name] = regular(path, 'public key ' + path.name)
        signed = bool(signatures) and bool(keys)
        if not signed:  # an unsigned artifact must not carry half a signature set
            for name in [n for n in files if n.endswith(('.bisign', '.bikey'))]:
                del files[name]
        meta = _optional(source / 'mod.cpp', 'mod.cpp')
        if meta:
            files['mod.cpp'] = meta
    else:
        raise Refused('built mod must be a .pbo file or an @HollowCountry directory: %s' % source)
    blobs = {name: read_bytes(path, name) for name, path in files.items()}
    try:
        pbo.parse(blobs['addons/' + PBO_NAME])
    except ValueError as error:
        raise Refused('built PBO failed the existing structural check: %s' % error) from None
    destination = absolute(destination)
    if destination.name.lower() in ('', '.', '..'):
        raise Refused('mod destination needs a folder name such as @HollowCountry')
    no_links(destination.parent, 'mod destination parent')
    if not destination.parent.is_dir():
        raise Refused('mod destination parent must exist: %s' % destination.parent)
    if os.path.lexists(destination):
        raise Refused('mod destination already exists (choose a fresh folder): %s' % destination)
    outside_checkouts(destination.parent, 'mod destination', repo)
    return {'dest': destination, 'signed': signed, 'blobs': blobs, 'hashes': {n: sha(b) for n, b in blobs.items()}}


def assemble_mod(plan, stage=None):
    destination = plan['dest']
    destination.mkdir(exist_ok=True)  # apply_plan creates it first, under a receipt intent
    for name, data in sorted(plan['blobs'].items()):
        target = destination / name
        if '/' in name:
            target.parent.mkdir(exist_ok=True)
        write_new(target, data, 0o644, stage=stage)
    return plan['hashes']


def plan_tf(path, repo=ROOT):
    """Tactical Flava (@TacticalFlava or the Workshop 2646817942 dir): read-only; only its keys/*.bikey are read."""
    source = existing_dir(path, 'Tactical Flava directory', repo)
    if not (source / 'addons').is_dir():
        raise Refused('Tactical Flava directory has no addons folder: %s' % source)
    keys = []
    directory = source / 'keys'
    if os.path.lexists(directory):
        no_links(directory, 'Tactical Flava keys directory')
        if directory.is_dir():
            for key in sorted(directory.iterdir()):
                if key.suffix.lower() == '.bikey':
                    if not KEY_NAME.match(key.name):
                        raise Refused('Tactical Flava key has an unsafe file name: %s' % key.name)
                    keys.append({'origin': 'tf', 'name': key.name,
                                 'data': read_bytes(key, 'Tactical Flava key ' + key.name, MAX_KEY)})
    return {'dir': source, 'keys': keys}


def key_sources(mod_plan, tf):
    sources = []
    if mod_plan['signed']:
        for name in sorted(n for n in mod_plan['blobs'] if n.startswith('keys/')):
            key = name.split('/', 1)[1]
            if not KEY_NAME.match(key):
                raise Refused('built public key has an unsafe file name: %s' % key)
            sources.append({'origin': 'hc', 'name': key, 'data': mod_plan['blobs'][name]})
    return sources + (tf['keys'] if tf else [])


def server_key_plan(server_root, sources):
    rows, seen = [], {}
    for source in sources:
        name, data = source['name'], source['data']
        if name in seen:
            if seen[name]['data'] != data:
                raise Refused('key %s is in both %s and %s with different content; refusing' %
                              (name, seen[name]['origin'], source['origin']))
            continue
        seen[name] = source
        target = server_root / 'keys' / name
        present = os.path.lexists(target)
        same = present and read_bytes(target, 'server key', MAX_KEY) == data
        if present and not same:
            raise Refused('server keys/%s exists with different content; refusing to replace it' % name)
        rows.append({'name': name, 'path': target, 'state': 'present' if same else 'missing', 'origin': source['origin'],
                     'sha256': sha(data), 'size': len(data), 'data': data})
    return rows


# ---------------------------------------------------------------- session plan

def parse_markers(value):
    if value in ('all', 'none'):
        return value, None
    names = [item.strip() for item in value.split(',')]
    if not names or any(not MARKER_NAME.match(name) for name in names):
        raise Refused('--markers must be all, none or a comma list of marker names')
    return 'names', sorted(set(names))


def marker_paths(plan, profiles, repo):
    """Validate every marker path before any write; return the paths that would be created.

    The acceptance_markers tool resolves only the destination, not what sits under it, so a symlinked
    HollowCountry or acceptance directory (or marker) would carry the writes elsewhere. Every ancestor up from
    the filesystem root is checked for links, the directories must be real directories, and the directory
    must not lie inside the repository or any git checkout."""
    profiles = no_links(profiles, 'profiles directory')
    base = profiles / 'HollowCountry' / 'acceptance'
    for directory in (profiles / 'HollowCountry', base):
        no_links(directory, 'marker directory')
        if os.path.lexists(directory) and not directory.is_dir():
            raise Refused('marker directory is not a directory: %s' % directory)
    outside_checkouts(base, 'marker directory', repo)
    creates = []
    for item in plan['files']:
        path = absolute(item['path'])
        if path.parent != base or path.name[-7:] != '.enable' or not MARKER_NAME.match(path.name[:-7]):
            raise Refused('marker path is outside the acceptance directory: %s' % path)
        no_links(path, 'marker ' + path.name)
        if item['action'] == 'create':
            if os.path.lexists(path):
                raise Refused('marker appeared after the plan was made: %s' % path.name)
            creates.append(path)
    return creates


def repo_file(repo, relative):
    return read_bytes(repo / relative, relative, limit=4 * 1024 * 1024)


def build_plan(args, repo=ROOT):
    server_root = existing_dir(args.server_root, 'server root', repo)
    state = server_root / STATE_NAME
    if os.path.lexists(state):
        raise Refused('a session already exists at %s; run rollback first' % state)
    cfg_path = regular(server_root / CFG_NAME, CFG_NAME)
    cfg_bytes = read_bytes(cfg_path, CFG_NAME, MAX_CFG)
    try:
        cfg_text = cfg_bytes.decode('utf-8')
    except UnicodeDecodeError:
        raise Refused('serverDZ.cfg is not valid UTF-8; refusing to edit it') from None
    new_text, changes = edit_cfg(cfg_text, desired_values(args.time_accel, args.night_accel))
    mission = existing_dir(args.mission, 'mission directory', repo)
    if 'steamapps' in (part.lower() for part in mission.parts):
        raise Refused('mission must be an isolated private copy outside steamapps')
    profiles = existing_dir(args.profiles, 'profiles directory', repo)
    no_links(profiles / 'HollowCountry', 'profiles/HollowCountry')
    no_links(profiles / 'HollowCountry' / 'acceptance', 'profiles/HollowCountry/acceptance')
    mod_plan = plan_mod(args.mod, args.mod_dest, repo)
    snafu = None
    if args.snafu:
        snafu = existing_dir(args.snafu, 'SNAFU Weapons Workshop directory', repo)
        if not (snafu / 'addons').is_dir():
            raise Refused('SNAFU directory has no addons folder: %s' % snafu)
    tf = plan_tf(args.tactical_flava, repo) if args.tactical_flava else None
    keys = server_key_plan(server_root, key_sources(mod_plan, tf))
    if args.install_key and not keys:
        raise Refused('--install-key needs a signed @HollowCountry with keys/ or a --tactical-flava with keys/')
    mode, only = parse_markers(args.markers)
    plan = {'server_root': server_root, 'state': state, 'cfg_path': cfg_path, 'cfg_before': cfg_bytes,
            'cfg_after': new_text.encode('utf-8'), 'changes': changes, 'cfg_facts': cfg_facts(cfg_text),
            'mission': mission, 'profiles': profiles, 'mod': mod_plan, 'snafu': snafu, 'tf': tf, 'keys': keys,
            'time_accel': float(args.time_accel), 'night_accel': float(args.night_accel),
            'markers_mode': mode, 'markers_only': only, 'warnings': [], 'repo': repo,
            'install_key': bool(args.install_key)}
    for row in changes:
        if row['key'].lower() == 'thirdpersonview':
            row['to_confirm'] = TO_CONFIRM
    # Mission deltas: generate in memory with the existing generators; this validates the mission.
    plan['gameplay'] = None
    if not args.no_gameplay:
        gameplay = load_tool('gameplay')
        regular(mission / 'cfggameplay.json', 'mission cfggameplay.json')
        if os.path.lexists(mission / gameplay.MANAGED):
            raise Refused('gameplay delta already installed in this mission; run rollback first')
        profile = gameplay.parse(repo_file(repo, GAMEPLAY_PROFILE))
        preset = gameplay.parse(repo_file(repo, GAMEPLAY_PRESET))
        try:
            gameplay.generate(mission, profile, preset)
        except (ValueError, OSError, KeyError, TypeError) as error:
            raise Refused('gameplay delta cannot be generated for this mission: %s' % error) from None
        plan['gameplay'] = {'profile': GAMEPLAY_PROFILE, 'preset': GAMEPLAY_PRESET}
    plan['economy'] = None
    if args.economy_profile != 'none':
        economy = load_tool('economy')
        name = args.economy_profile
        if not MARKER_NAME.match(name):
            raise Refused('--economy-profile must be a profile name or none')
        regular(mission / 'cfgeconomycore.xml', 'mission cfgeconomycore.xml')
        if os.path.lexists(mission / economy.MANAGED):
            raise Refused('economy delta already installed in this mission; run rollback first')
        profile_path = ECONOMY_PROFILES + name + '.json'
        try:
            economy.generate(mission, json.loads(repo_file(repo, profile_path)))
        except (ValueError, OSError, KeyError, TypeError) as error:
            raise Refused('economy delta cannot be generated for this mission: %s' % error) from None
        plan['economy'] = {'profile': profile_path}
    plan['markers'] = None
    if mode != 'none':
        markers = load_tool('acceptance_markers')
        try:
            plan['markers'] = markers.plan_profile(markers.scan_tree(repo), profiles, repo, only)
        except markers.RefusedDestination as error:
            raise Refused('markers: %s' % error) from None
        marker_paths(plan['markers'], profiles, repo)
    return plan


# ---------------------------------------------------------------- launch commands

def launch_commands(plan, args):
    notes = []

    def win(path):
        text, mapped = to_windows(path)
        if not mapped and os.name != 'nt':
            notes.append('some paths are not under /mnt/<drive>, so the printed commands are not valid Windows '
                         'paths (for example %s); pass /mnt/<drive>/... paths' % path)
        return text

    mods = [win(plan['snafu'])] if plan['snafu'] else []  # dependency order: SNAFU, Tactical Flava, then HC
    if plan['tf']:
        mods.append(win(plan['tf']['dir']))
    mods.append(win(plan['mod']['dest']))
    mod_argument = '-mod=' + ';'.join(mods)
    root = win(plan['server_root'])
    port, query = args.game_port, args.query_port
    server_arguments = ['-config=' + win(plan['cfg_path']), '-profiles=' + win(plan['profiles']), mod_argument,
                        '-mission=' + win(plan['mission']), '-ip=127.0.0.1', '-port=%d' % port,
                        '-doLogs', '-adminLog']
    server = ['Set-Location -LiteralPath ' + ps_quote(root),
              '& ' + ps_quote(root + '\\DayZServer_x64.exe') + ' ' + ' '.join(ps_quote(a) for a in server_arguments)]
    client_arguments = ['0', '1', '1', '-exe', 'DayZ_x64.exe', mod_argument,
                        '-connect=127.0.0.1:%d:%d' % (port, query), '-port=%d' % port]
    client = ['Start-Process -FilePath ' + ps_quote(args.client_root + '\\DayZ_BE.exe')
              + ' -WorkingDirectory ' + ps_quote(args.client_root)
              + ' -ArgumentList @(' + ', '.join(ps_arg(a) for a in client_arguments) + ')']
    return {'server': server, 'client': client, 'warnings': notes[:1]}


def advisories(plan):
    facts, rows = plan['cfg_facts'], []
    if not plan['mod']['signed']:
        rows.append('Unsigned mod: the server and the client need signature verification relaxed by you; '
                    'this tool does not change verifySignatures (currently %s).' % facts.get('verifySignatures', 'not set'))
    else:
        missing = [k['name'] for k in plan['keys'] if k['state'] == 'missing' and k['origin'] == 'hc']
        if missing and not plan['install_key']:
            rows.append('Public key(s) %s are not in <server root>\\keys. Copy them there or add --install-key '
                        '(only the public .bikey belongs on the server).' % ', '.join(missing))
    if plan['tf']:
        missing = [k['name'] for k in plan['keys'] if k['state'] == 'missing' and k['origin'] == 'tf']
        if not any(k['origin'] == 'tf' for k in plan['keys']):
            rows.append('Tactical Flava: no keys/*.bikey found in %s; signature checks for it only pass if its key '
                        'is already on the server.' % plan['tf']['dir'])
        elif missing and not plan['install_key']:
            rows.append('Tactical Flava key(s) %s are not in <server root>\\keys; signature checks need %s on the server. '
                        'Copy it there or add --install-key (only the public .bikey belongs on the server).' %
                        (', '.join(missing), 'it' if len(missing) == 1 else 'them'))
    if facts.get('password_set'):
        rows.append('The server has a password; add -password=<yours> to the client command (it is not printed here).')
    return rows


# ---------------------------------------------------------------- reporting

def render_plan(plan, args, commands, applied=False):
    out = ['Local test session %s (nothing is launched; runtime acceptance stays pending)' %
           ('APPLIED' if applied else 'PLAN, no changes written')]
    mod = plan['mod']
    out.append('')
    out.append('1. Mod folder %s (%s) from %d file(s):' % (mod['dest'], 'signed, with keys/' if mod['signed'] else 'unsigned', len(mod['blobs'])))
    out += ['     %s  sha256 %s' % (name, mod['hashes'][name][:16]) for name in sorted(mod['hashes'])]
    out.append('2. %s: backup to %s, receipt %s, then only these keys:' % (CFG_NAME, plan['state'] / BACKUP_NAME, plan['state'] / RECEIPT_NAME))
    for row in plan['changes']:
        before = '(absent)' if row['before'] is None else row['before']
        label = '"%s"' % TO_CONFIRM if row.get('to_confirm') else ''
        out.append('     %s: %s -> %s [%s] %s' % (row['key'], before, row['after'], row['action'], label))
        if row.get('to_confirm'):
            out.append('       ' + THIRD_PERSON_CITATION)
    product = plan['time_accel'] * plan['night_accel']
    out.append('     night pace: x%g at night (serverTimeAcceleration * serverNightTimeAcceleration, %g * %g; BI server '
               'docs), about %.0f real minutes for a %d h night' %
               (product, plan['time_accel'], plan['night_accel'], NIGHT_HOURS * 60 / product, NIGHT_HOURS))
    out.append('     BattlEye, signature verification and passwords: untouched and never printed.')
    out.append('3. Mission deltas in %s:' % plan['mission'])
    out.append('     gameplay (cfggameplay.json + spawn kit): %s' % ('install' if plan['gameplay'] else 'skipped'))
    out.append('     economy (CE delta, profile %s): %s' % (args.economy_profile, 'install' if plan['economy'] else 'skipped'))
    out.append('4. Acceptance markers in %s: %s' % (plan['profiles'], plan['markers_mode'] if plan['markers_mode'] != 'names' else ','.join(plan['markers_only'])))
    for item in (plan['markers'] or {}).get('files', []):
        out.append('     %s.enable [%s]' % (item['name'], item['action']))
    if plan['snafu']:
        out.append('   SNAFU (read-only, optional dependency): %s' % plan['snafu'])
    if plan['tf']:
        out.append('   Tactical Flava (read-only, optional dependency): %s' % plan['tf']['dir'])
    if plan['keys']:
        out.append('   Server keys (%s): %s' % ('copied with --install-key' if plan['install_key'] else
                                                 'not copied; add --install-key to copy them',
                                                 ', '.join('%s [%s, %s]' % (k['name'], k['origin'], k['state']) for k in plan['keys'])))
    out.append('')
    out.append('Server (PowerShell):')
    out += ['  ' + row for row in commands['server']]
    out.append('Client (PowerShell, after the server is up):')
    out += ['  ' + row for row in commands['client']]
    for row in advisories(plan) + commands['warnings']:
        out.append('NOTE: ' + row)
    if not applied:
        out.append('Run the same arguments with `apply` to write these changes; `rollback` undoes them.')
    return '\n'.join(out)


# ---------------------------------------------------------------- receipt + apply + rollback

def _jsonify(value):
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, default=_jsonify) + '\n').encode()


class Receipt:
    def __init__(self, path, data=None):
        self.path, self.data = path, data

    def create(self, data):
        self.data = data
        write_new(self.path, encode(data))

    def save(self):
        replace_with(self.path, encode(self.data))

    def step(self, name, state):
        self.data['steps'][name] = state
        self.save()


def stage_directory(state, name):
    stage = state / 'deltas' / name
    stage.parent.mkdir(exist_ok=True)
    return stage


def apply_plan(plan, args):
    """Write the session. Every creation is recorded in the receipt (fsynced) BEFORE it happens, so a run that
    is killed at any point leaves a receipt that names everything the run may have created."""
    repo, state = plan['repo'], plan['state']
    state.mkdir()
    receipt = Receipt(state / RECEIPT_NAME)
    receipt.create({'schema': SCHEMA, 'status': 'in-progress', 'server_root': str(plan['server_root']),
                    'steps': {}, 'runtime_acceptance': 'pending',
                    'cfg': {'path': str(plan['cfg_path']), 'before_sha256': sha(plan['cfg_before']),
                            'after_sha256': sha(plan['cfg_after']),
                            'changes': [{k: v for k, v in row.items()} for row in plan['changes']]},
                    'mod': {'dest': str(plan['mod']['dest']), 'files': plan['mod']['hashes'],
                            'sizes': {n: len(b) for n, b in plan['mod']['blobs'].items()},
                            'signed': plan['mod']['signed']},
                    'server_keys': [], 'server_keys_dir': None, 'mission': str(plan['mission']),
                    'profiles': str(plan['profiles']), 'markers': {'created': [], 'dirs': []},
                    'rollback': {'steps': {}}})
    # 1. mod folder (the intent: the dest folder and the listed files, all in the receipt already)
    receipt.step('mod', 'started')
    try:
        plan['mod']['dest'].mkdir()
    except FileExistsError:
        receipt.data['mod']['files'] = {}
        receipt.step('mod', 'refused')
        raise Refused('mod destination appeared after the plan was made: %s' % plan['mod']['dest']) from None
    assemble_mod(plan['mod'], stage=state)
    receipt.step('mod', 'done')
    if plan['install_key']:
        receipt.step('server_keys', 'started')
        keys_dir = plan['server_root'] / 'keys'
        for item in plan['keys']:
            if item['state'] != 'missing':
                continue
            if not os.path.lexists(keys_dir):
                receipt.data['server_keys_dir'] = str(keys_dir)
                receipt.save()
                try:
                    keys_dir.mkdir()
                except FileExistsError:
                    receipt.data['server_keys_dir'] = None
                    receipt.save()
            entry = {'path': str(item['path']), 'sha256': item['sha256'], 'size': item['size'], 'state': 'intent'}
            receipt.data['server_keys'].append(entry)
            receipt.save()  # intent first: the key may or may not exist when this run is killed
            try:
                write_new(item['path'], item['data'], 0o644, stage=state)
            except Refused:
                entry['state'] = 'skipped'  # an exclusive create refused: the file is not ours
                receipt.save()
                raise
            entry['state'] = 'created'
            receipt.save()
        receipt.step('server_keys', 'done')
    # 2. serverDZ.cfg: byte-exact backup and receipt exist before the atomic switch. The temp file lives in the
    # state directory, so a kill never leaves a stray file next to the server configuration.
    receipt.step('cfg', 'started')
    write_new(state / BACKUP_NAME, plan['cfg_before'], mode_of(plan['cfg_path']))
    if read_bytes(plan['cfg_path'], CFG_NAME, MAX_CFG) != plan['cfg_before']:
        raise Refused('serverDZ.cfg changed since the plan was made; run again')
    replace_with(plan['cfg_path'], plan['cfg_after'], mode_of(plan['cfg_path']), temp=state / NEXT_NAME)
    receipt.step('cfg', 'done')
    # 3 and 4. mission deltas through the existing installers (their own receipts and rollback)
    if plan['gameplay']:
        gameplay = load_tool('gameplay')
        receipt.step('gameplay', 'started')
        profile = gameplay.parse(repo_file(repo, GAMEPLAY_PROFILE))
        preset = gameplay.parse(repo_file(repo, GAMEPLAY_PRESET))
        stage = stage_directory(state, 'gameplay')
        gameplay.write_delta(stage, gameplay.generate(plan['mission'], profile, preset))
        gameplay.install(stage, plan['mission'])
        receipt.step('gameplay', 'done')
    if plan['economy']:
        economy = load_tool('economy')
        receipt.step('economy', 'started')
        stage = stage_directory(state, 'economy')
        economy.write_delta(stage, economy.generate(plan['mission'], json.loads(repo_file(repo, plan['economy']['profile']))))
        economy.install_delta(stage, plan['mission'])
        receipt.step('economy', 'done')
    # 5. markers
    if plan['markers']:
        markers = load_tool('acceptance_markers')
        receipt.step('markers', 'started')
        fresh = markers.plan_profile(markers.scan_tree(repo), plan['profiles'], repo, plan['markers_only'])
        creates = marker_paths(fresh, plan['profiles'], repo)  # refuses links and checkouts before any write
        base = plan['profiles'] / 'HollowCountry'
        for directory in (base, base / 'acceptance'):
            if not os.path.lexists(directory):
                receipt.data['markers']['dirs'].append(str(directory))
        receipt.data['markers']['created'] += [str(path) for path in creates]
        receipt.save()  # intent first, for every directory and file apply_plan may create
        marker_paths(fresh, plan['profiles'], repo)  # and once more immediately before the writes
        markers.apply_plan(fresh)
        receipt.step('markers', 'done')
    receipt.data['status'] = 'applied'
    receipt.save()
    return receipt


def load_receipt(server_root, repo=ROOT):
    server_root = existing_dir(server_root, 'server root', repo)
    state = no_links(server_root / STATE_NAME, 'session state')
    data = json.loads(read_bytes(state / RECEIPT_NAME, 'session receipt', 4 * 1024 * 1024))
    if not isinstance(data, dict) or data.get('schema') != SCHEMA or data.get('server_root') != str(server_root):
        raise Refused('receipt is not a session receipt for this server root')
    return server_root, state, Receipt(state / RECEIPT_NAME, data)


def owned_file(path, digest, what, stage=None):
    """(path, note, staged links) for one file this session recorded creating.

    (path, None, ...) when it is byte-for-byte what the receipt recorded; (None, None, ...) when absent;
    (None, note, ...) when something else is there. Only an exact hash match proves ownership: a shorter file, a
    true prefix, a symlink, a hard link or other content could be the operator's and is never deleted.

    A killed apply can leave our own staging link next to the file (hard-linked into place, not yet unlinked).
    That link is reconciled first: it must be a regular file in the state directory, the very same file as the
    final path (exactly two links) and carry the recorded hash. Anything else raises Refused, so the recovery
    state is kept and rollback does not report completion while a file we created may survive."""
    staged = stage_path(stage, path) if stage is not None else None
    stale = []
    if staged is not None and os.path.lexists(staged):
        if staged.is_symlink() or not staged.is_file():
            raise Refused('staging path for %s is not a regular file; keeping the recovery state' % what)
        if not os.path.lexists(path):
            return None, None, [staged]  # never linked into place: a leftover temp in our own state directory
        before, after = os.lstat(staged), os.lstat(path)
        if stat.S_ISLNK(after.st_mode) or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino) or before.st_nlink != 2:
            raise Refused('staging link for %s is not the same file as the one in place; keeping the recovery state' % what)
        if sha(read_bytes(staged, 'staging link for ' + what, links=2)) != digest:
            raise Refused('staging link for %s does not carry the recorded content; keeping the recovery state' % what)
        stale.append(staged)
        links = 2
    else:
        links = 1
    if not os.path.lexists(path):
        return None, None, stale
    try:
        data = read_bytes(path, what, links=links)
    except Refused:
        data = None
    if data is not None and sha(data) == digest:
        return path, None, stale
    return None, 'left in place: not provably ours (%s)' % path, stale


def trial_rollback(name, tool, mission, started):
    """Run the existing installer's real rollback on a scratch copy of what it reads: 'run' or 'noop'.

    The installers validate everything before they change anything, but they cannot be asked in advance
    without changing something (economy has no dry run), so the same code runs on a copy first."""
    managed = mission / tool.MANAGED
    for path in (managed, *sorted(managed.rglob('*'))):
        no_links(path, name + ' managed path')
        if path.is_file():
            regular(path, name + ' managed file ' + path.name)
    scratch = Path(tempfile.mkdtemp(prefix='hc-rollback-trial-'))
    try:
        copy = scratch / 'mission'
        copy.mkdir()
        shutil.copytree(managed, copy / tool.MANAGED, symlinks=True)
        for relative in getattr(tool, 'INPUTS', ()):
            source = mission / relative
            if os.path.lexists(source):
                (copy / relative).parent.mkdir(parents=True, exist_ok=True)
                (copy / relative).write_bytes(read_bytes(source, relative, MAX_BYTES))
        try:
            tool.rollback(copy)
        except (ValueError, OSError, KeyError, TypeError) as error:
            # An install that never wrote its own receipt has nothing to undo; anything else refuses now.
            if started and ('nothing to roll back' in str(error) or isinstance(error, FileNotFoundError)):
                return 'noop'
            raise Refused('%s rollback would be refused (nothing was changed; the receipt is kept): %s' %
                          (name, error)) from None
        return 'run'
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def run_installer_rollback(name, tool, mission):
    try:
        tool.rollback(mission)
    except (ValueError, OSError, KeyError, TypeError) as error:
        raise Refused('%s rollback refused (receipt and progress kept; run rollback again after fixing it): %s' %
                      (name, error)) from None


def noop():
    return None


def _remove_files(paths, directories=(), staged=()):
    def run():
        for link in staged:  # our own staging links first, so the file in place is back to one link
            if os.path.lexists(link):
                link.unlink()
        for path in paths:
            path.unlink()
        for directory in directories:  # only directories this session recorded creating, and only while empty
            try:
                if not directory.is_symlink():
                    directory.rmdir()
            except OSError:
                pass
    return run


def _restore_cfg(cfg_path, backup, state):
    def run():
        replace_with(cfg_path, backup, mode_of(cfg_path), temp=state / RESTORE_NAME)
    return run


def plan_rollback(server_root, repo=ROOT):
    """Everything that can refuse is decided here, before the first change; returns (receipt, state, todo)."""
    server_root, state, receipt = load_receipt(server_root, repo)
    data, steps = receipt.data, receipt.data['steps']
    progress = data.setdefault('rollback', {'steps': {}})['steps']
    mission = no_links(Path(data['mission']), 'mission')
    profiles = absolute(data['profiles'])
    cfg_path = server_root / CFG_NAME
    if data['cfg']['path'] != str(cfg_path):
        raise Refused('receipt names a different serverDZ.cfg')
    todo = []  # (step, description, action), in undo order; steps an earlier attempt finished are skipped

    if progress.get('markers') != 'done':
        base = profiles / 'HollowCountry' / 'acceptance'
        files = []
        for text in data['markers']['created']:
            path = absolute(text)
            if path.name[-7:] != '.enable' or not MARKER_NAME.match(path.name[:-7]) or path.parent != base:
                raise Refused('receipt lists a marker outside the acceptance directory')
            if os.path.lexists(path):
                regular(path, 'marker ' + path.name)
                if path.stat().st_size:
                    raise Refused('marker %s is no longer empty; leaving it for you to inspect' % path.name)
                files.append(path)
        directories = []
        for text in data['markers'].get('dirs', []):
            directory = absolute(text)
            if directory not in (base, base.parent):
                raise Refused('receipt lists a marker directory outside the profiles directory')
            directories.append(directory)
        directories.sort(key=lambda d: len(d.parts), reverse=True)
        todo.append(('markers', 'markers: remove %d empty file(s)' % len(files), _remove_files(files, directories)))

    for name in ('economy', 'gameplay'):
        if not steps.get(name) or progress.get(name) == 'done':
            continue
        tool = load_tool(name)
        managed = mission / tool.MANAGED
        if not os.path.lexists(managed):
            # Gone because an interrupted rollback already ran the installer, or the install never got that far;
            # for a finished install anything else means someone moved it away.
            if progress.get(name) != 'started' and steps[name] == 'done':
                raise Refused('%s: the installer directory %s is missing; reconcile by hand' % (name, managed))
            todo.append((name, '%s: installer already rolled back, nothing to undo' % name, noop))
        elif trial_rollback(name, tool, mission, steps[name] == 'started') == 'noop':
            todo.append((name, '%s: installer wrote no receipt, nothing to undo' % name, noop))
        else:
            todo.append((name, '%s: existing installer rollback on %s' % (name, mission),
                         lambda name=name, tool=tool: run_installer_rollback(name, tool, mission)))

    if steps.get('cfg') in ('started', 'done') and progress.get('cfg') != 'done':
        before, after = data['cfg']['before_sha256'], data['cfg']['after_sha256']
        current = sha(read_bytes(cfg_path, CFG_NAME, MAX_CFG))
        if current == before:
            todo.append(('cfg', 'serverDZ.cfg: already original, nothing to restore', noop))
        elif current == after:
            backup = read_bytes(state / BACKUP_NAME, 'serverDZ.cfg backup', MAX_CFG)
            if sha(backup) != before:
                raise Refused('serverDZ.cfg backup does not match its receipt')
            todo.append(('cfg', 'serverDZ.cfg: restore the backup (%s)' % before[:16], _restore_cfg(cfg_path, backup, state)))
        else:
            raise Refused('serverDZ.cfg drifted since apply; reconcile by hand (backup kept)')

    if progress.get('server_keys') != 'done':
        keys_dir = server_root / 'keys'
        files, notes, staged = [], [], []
        for item in data['server_keys']:
            path = absolute(item['path'])
            if path.parent != keys_dir:
                raise Refused('receipt lists a key outside the server keys directory')
            if item.get('state', 'created') in ('intent', 'created'):
                owned, note, links = owned_file(path, item['sha256'], 'server key ' + path.name, state)
                staged.extend(links)
                if owned:
                    files.append(owned)
                if note:
                    notes.append(note)
        created_dir = data.get('server_keys_dir')
        if created_dir is not None and absolute(created_dir) != keys_dir:
            raise Refused('receipt lists a keys directory outside the server root')
        todo.append(('server_keys', '; '.join(['server keys: remove %d' % len(files)] + notes),
                     _remove_files(files, [keys_dir] if created_dir else [], staged)))

    if steps.get('mod') in ('started', 'done') and progress.get('mod') != 'done':
        mod = data['mod']
        mod_dest = no_links(mod['dest'], 'mod folder')
        files, notes, staged = [], [], []
        for name, digest in sorted(mod['files'].items()):
            if not MOD_FILE.match(name):
                raise Refused('receipt lists a mod file outside the mod folder')
            owned, note, links = owned_file(mod_dest / name, digest, 'mod file ' + name, state)
            staged.extend(links)
            if owned:
                files.append(owned)
            if note:
                notes.append(note)
        todo.append(('mod', '; '.join(['mod folder: remove %d file(s) from %s' % (len(files), mod_dest)] + notes),
                     _remove_files(files, [mod_dest / 'addons', mod_dest / 'keys', mod_dest], staged)))
    return receipt, state, todo


def rollback(server_root, repo=ROOT, dry_run=False):
    receipt, state, todo = plan_rollback(server_root, repo)
    descriptions = [description for _, description, _ in todo]
    if dry_run:
        return descriptions
    progress = receipt.data['rollback']['steps']
    receipt.data['status'] = 'rolling-back'
    receipt.save()
    for name, description, action in todo:  # progress is saved step by step, so a retry resumes after the last finished one
        progress[name] = 'started'
        receipt.save()
        action()
        progress[name] = 'done'
        if 'left in place' in description:  # done, with a note: files that are not provably ours stay untouched
            receipt.data['rollback'].setdefault('notes', {})[name] = description
        receipt.save()
    # Everything undone: drop the state directory we created (backup holds the old cfg, so it goes last).
    leftovers = sorted(state.rglob('*'), key=lambda p: len(p.parts), reverse=True)
    for path in leftovers:
        if path.name == RECEIPT_NAME and path.parent == state:
            continue
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    (state / RECEIPT_NAME).unlink()
    state.rmdir()
    return descriptions


# ---------------------------------------------------------------- command line

def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = parser.add_subparsers(dest='command')
    for name in ('plan', 'apply'):
        p = sub.add_parser(name, help='dry run (default, writes nothing)' if name == 'plan' else 'write the changes')
        p.add_argument('--server-root', required=True, type=Path, help='server install/runtime dir holding serverDZ.cfg')
        p.add_argument('--mission', required=True, type=Path, help='private mission copy (outside steamapps)')
        p.add_argument('--profiles', required=True, type=Path, help='server -profiles directory (must exist)')
        p.add_argument('--mod', required=True, type=Path, help='built signed @HollowCountry dir, or a .pbo')
        p.add_argument('--mod-dest', required=True, type=Path, help='fresh @HollowCountry folder to create')
        p.add_argument('--snafu', type=Path, help='optional SNAFU Weapons Workshop dir (read-only)')
        p.add_argument('--tactical-flava', type=Path, help='optional @TacticalFlava or Workshop 2646817942 dir '
                       '(read-only; loaded before HC; its keys/*.bikey is installed only with --install-key)')
        p.add_argument('--markers', default='all', help='all, none or comma-separated marker names')
        p.add_argument('--time-accel', type=float, default=DEFAULT_TIME_ACCELERATION)
        p.add_argument('--night-accel', type=float, default=DEFAULT_NIGHT_ACCELERATION)
        p.add_argument('--economy-profile', default=DEFAULT_ECONOMY_PROFILE, help='economy profile name or none')
        p.add_argument('--no-gameplay', action='store_true', help='skip the cfggameplay delta')
        p.add_argument('--install-key', action='store_true',
                       help='copy the public .bikey of HC and of --tactical-flava into <server root>\\keys')
        p.add_argument('--client-root', default=DEFAULT_CLIENT_ROOT, help='Windows DayZ client install dir for the printed command')
        p.add_argument('--game-port', type=int, default=2302)
        p.add_argument('--query-port', type=int, default=27016)
    p = sub.add_parser('rollback', help='undo a session using its receipt')
    p.add_argument('--server-root', required=True, type=Path)
    p.add_argument('--dry-run', action='store_true')
    return parser


def main(argv=None, repo=ROOT, out=None):
    out = out or sys.stdout
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ('plan', 'apply', 'rollback', '-h', '--help'):
        argv.insert(0, 'plan')
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == 'rollback':
            for line in rollback(args.server_root, repo, args.dry_run):
                print(('would ' if args.dry_run else 'done: ') + line, file=out)
            print('Rollback %s.' % ('previewed' if args.dry_run else 'complete'), file=out)
            return 0
        if not 1024 <= args.game_port <= 65533 or not 1024 <= args.query_port <= 65535:
            raise Refused('ports out of range')
        plan = build_plan(args, repo)
        commands = launch_commands(plan, args)
        if args.command == 'apply':
            apply_plan(plan, args)
        print(render_plan(plan, args, commands, applied=args.command == 'apply'), file=out)
        return 0
    except (Refused, ValueError, OSError, KeyError, TypeError) as error:
        print('refused: %s' % error, file=sys.stderr)
        if args.command == 'apply':
            print('Partial work is recorded in the session receipt; run `rollback --server-root` to undo it.',
                  file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
