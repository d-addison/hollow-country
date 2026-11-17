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
  opt-in steps    --interiors (tools/package/interiors_profile.py into <profiles>/HollowCountry),
                  --expansion-ai (stage @HollowCountryExpansionAI after Expansion's own Workshop folders, which
                  are only checked and never copied; then expansion_ai_config installs ai/sites.json and the
                  HollowCountry_* loadouts, the patrol override and the field merge into Expansion's existing
                  AISettings.json, with byte-exact backups) and
                  --markers all-local / NAME,... (names parsed from docs/LOCAL_ACCEPTANCE_V1.md at run time).
                  Apply order: mod, keys, cfg, gameplay, economy, interiors, expansion_ai, expansion_ai_config,
                  markers; rollback reverses.

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
import subprocess
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
AI_PBO_NAME = 'hollowcountryexpansionai.pbo'
AI_PREFIX = 'HollowCountryExpansionAI'
MAX_BYTES = 256 * 1024 * 1024
MAX_CFG = 1024 * 1024
MISSION_ROOT = 'mission/hollow-country'
GAMEPLAY_PROFILE = MISSION_ROOT + '/gameplay-profiles/hollow-country-v1.json'
GAMEPLAY_PRESET = MISSION_ROOT + '/gear/hardscrabble.json'
ECONOMY_PROFILES = MISSION_ROOT + '/economy-profiles/'
DEFAULT_ECONOMY_PROFILE = 'contextual-pilot'
FIREARMS_ROSTER = 'tools/package/firearms_roster.json'  # the 2x-scarcity firearms roster, in the economy delta by default
INTERIORS_PACK = MISSION_ROOT + '/interiors'
AI_MERGE = MISSION_ROOT + '/ai/AISettings.merge.json'
AI_SETTINGS_TARGET = 'ExpansionMod/Settings/AISettings.json'
AI_PATROL_OVERRIDE = MISSION_ROOT + '/ai/AIPatrolSettings.override.json'
AI_PATROL_TARGET = 'expansion/settings/AIPatrolSettings.json'
AI_POLICY_TARGET = 'HollowCountry/expansion-ai.json'
AI_SITES = MISSION_ROOT + '/ai/sites.json'
AI_SITES_TARGET = 'HollowCountry/expansion-ai-sites.json'
AI_LOADOUTS = MISSION_ROOT + '/ai/loadouts'
AI_LOADOUTS_TARGET = 'ExpansionMod/Loadouts'
AI_LOADOUT_NAME = re.compile(r'^HollowCountry_[A-Za-z0-9]+\.json$')
AI_MARKER = 'pve_patrols'
MARKER_DOC = 'docs/LOCAL_ACCEPTANCE_V1.md'
MARKER_ROW = re.compile(r'^\|\s*`\$profile:HollowCountry/acceptance/(?P<name>[A-Za-z0-9_-]+)\.enable`\s*\|')
# (label, Workshop id or None, accepted folder names after lowercasing and dropping '@' and punctuation)
# Optional-subset CE deltas, in install order (rollback is the reverse): (step, tool name, label).
OPTIONAL_DELTAS = (('snafu', 'snafu_optional', 'SNAFU'),
                   ('tactical_flava', 'tactical_flava_optional', 'Tactical Flava'))
STEP_TOOLS = {'tactical_flava': 'tactical_flava_optional', 'snafu': 'snafu_optional',
              'economy': 'economy', 'gameplay': 'gameplay'}
STACK_STEPS = ('tactical_flava', 'snafu', 'economy')  # each rolls back on top of the CE core the ones below patched

EXPANSION_DEPENDENCIES = (
    ('CF', '1559212036', ('cf', 'communityframework')),
    ('Dabs Framework', '2545327648', ('dabsframework', 'dabs')),
    ('Expansion-Animations', '2793893086', ('expansionanimations', 'dayzexpansionanimations')),
    ('Expansion-Core', '2291785308', ('expansioncore', 'dayzexpansioncore')),
    ('Expansion-AI', '2792982069', ('expansionai', 'dayzexpansionai')),
)
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
              'acceptance_markers': 'tools.audit.acceptance_markers',
              'interiors_profile': 'tools.package.interiors_profile',
              'snafu_optional': 'tools.package.snafu_optional',
              'tactical_flava_optional': 'tools.package.tactical_flava_optional'}[name]
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


def check_ai_pbo(blob):
    try:
        return structure_ai_pbo(blob)
    except ValueError as error:
        raise ValueError('Expansion AI addon: %s' % str(error).replace('the Expansion AI addon ', '')) from None


def structure_ai_pbo(blob):
    """Structural check of the Expansion AI addon PBO: checksum, Vers header, its own prefix, a config member that
    names the CfgPatches class. (tools.package.pbo.parse only accepts the HollowCountry prefix.)"""
    if not isinstance(blob, bytes) or not 63 <= len(blob) <= MAX_BYTES + 21:
        raise ValueError('invalid PBO length')
    body, trailer = blob[:-21], blob[-21:]
    if trailer != b'\0' + hashlib.sha1(body).digest():
        raise ValueError('PBO checksum mismatch')
    offset = 0

    def string():
        nonlocal offset
        end = body.find(b'\0', offset, min(offset + 1025, len(body)))
        if end < 0:
            raise ValueError('unterminated string')
        try:
            value = body[offset:end].decode('ascii')
        except UnicodeDecodeError:
            raise ValueError('non-ASCII PBO string') from None
        offset = end + 1
        return value

    def words():
        nonlocal offset
        if offset + pbo.WORDS.size > len(body):
            raise ValueError('truncated header')
        value = pbo.WORDS.unpack_from(body, offset)
        offset += pbo.WORDS.size
        return value

    if string() != '' or words() != (pbo.VERS, 0, 0, 0, 0):
        raise ValueError('expected a Vers header')
    props = {}
    while True:
        key = string()
        if not key:
            break
        if key in props:
            raise ValueError('duplicate property')
        props[key] = string()
    if props.get('prefix') != AI_PREFIX:
        raise ValueError('the Expansion AI addon PBO prefix must be %s, not %r' % (AI_PREFIX, props.get('prefix')))
    sizes = {}
    while True:
        name = string()
        meta = words()
        if not name:
            break
        if name.lower() in (n.lower() for n in sizes) or len(sizes) >= pbo.MAX_ENTRIES:
            raise ValueError('duplicate header or too many entries')
        sizes[name] = meta[4]
    if offset + sum(sizes.values()) != len(body):
        raise ValueError('data sizes do not match the archive')
    members, position = {}, offset
    for name, size in sizes.items():
        members[name.replace('\\', '/').lower()] = body[position:position + size]
        position += size
    config = members.get('config.cpp')
    if config is not None:
        found = re.search(rb'class\s+CfgPatches\s*\{\s*class\s+' + AI_PREFIX.encode() + rb'\b', config)
    else:
        config = members.get('config.bin')
        found = config is not None and b'CfgPatches' in config and AI_PREFIX.encode() in config
    if not found:
        raise ValueError('the Expansion AI addon config.cpp or config.bin must declare the CfgPatches class %s' % AI_PREFIX)


def plan_mod(source, destination, repo=ROOT, pbo_name=PBO_NAME, check=None):
    """Collect (relative name -> source path) for the new mod folder; verify the PBO structurally."""
    source = no_links(source, 'built mod')
    files, signed = {}, False
    if source.is_file():
        files['addons/' + pbo_name] = regular(source, 'built PBO')
    elif source.is_dir():
        addons = source / 'addons'
        files['addons/' + pbo_name] = regular(addons / pbo_name, 'built addons/' + pbo_name)
        signatures = sorted(p for p in addons.iterdir() if re.fullmatch(re.escape(pbo_name) + r'\.[A-Za-z0-9_-]+\.bisign', p.name))
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
        (check or pbo.parse)(blobs['addons/' + pbo_name])
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


def has_addons(path):
    """An addons folder, however the mod author cased it (the SNAFU Workshop folder is 'Addons')."""
    return any(child.name.lower() == 'addons' and child.is_dir() and not child.is_symlink() for child in path.iterdir())


def plan_tf(path, repo=ROOT):
    """Tactical Flava (@TacticalFlava or the Workshop 2646817942 dir): read-only; only its keys/*.bikey are read."""
    source = existing_dir(path, 'Tactical Flava directory', repo)
    if not has_addons(source):
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


def key_sources(mod_plan, tf, extra_mods=()):
    sources = []
    for plan in (mod_plan, *extra_mods):
        if not plan['signed']:
            continue
        for name in sorted(n for n in plan['blobs'] if n.startswith('keys/')):
            key = name.split('/', 1)[1]
            if not KEY_NAME.match(key):
                raise Refused('built public key has an unsafe file name: %s' % key)
            sources.append({'origin': 'hc', 'name': key, 'data': plan['blobs'][name]})
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
    if value in ('all', 'none', 'all-local'):
        return value, None
    names = [item.strip() for item in value.split(',')]
    if not names or any(not MARKER_NAME.match(name) for name in names):
        raise Refused('--markers must be all, none, all-local or a comma list of marker names')
    return 'names', sorted(set(names))


def local_marker_names(repo=ROOT):
    """Marker names in the local-acceptance marker table, in table order: rows of docs/LOCAL_ACCEPTANCE_V1.md that
    begin with a backticked `$profile:HollowCountry/acceptance/<name>.enable` literal (prose mentions and the
    checklist rows below the table are not part of it). Read at run time so the doc stays the single list."""
    try:
        text = read_bytes(repo / MARKER_DOC, MARKER_DOC, limit=4 * 1024 * 1024).decode('utf-8')
    except (Refused, UnicodeDecodeError):
        raise Refused('cannot read the marker table in %s' % MARKER_DOC) from None
    names = []
    for line in text.splitlines():
        match = MARKER_ROW.match(line)
        if match and match.group('name') not in names:
            names.append(match.group('name'))
    if not names:
        raise Refused('no marker rows found in the table of %s' % MARKER_DOC)
    return names


def resolve_markers(mode, only, repo):
    """(mode, names): all-local and named lists are checked against the acceptance table before any write."""
    if mode == 'all-local':
        return mode, local_marker_names(repo)
    if mode == 'names':
        listed = local_marker_names(repo)
        unlisted = sorted(set(only) - set(listed))
        if unlisted:
            raise Refused('marker(s) %s are not in the marker table of %s (allowed: %s)' %
                          (', '.join(unlisted), MARKER_DOC, ', '.join(listed)))
    return mode, only


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


def economy_delta(economy, mission, repo, spec):
    """Generate the economy delta for a planned spec: the profile plus the firearms roster unless --no-roster."""
    profile = json.loads(repo_file(repo, spec['profile']))
    if spec.get('roster'):
        return economy.generate(mission, profile, roster=json.loads(repo_file(repo, spec['roster'])))
    return economy.generate(mission, profile)


DIAG_QUERY = ("Get-CimInstance Win32_Process -Filter \"Name='DayZDiag_x64.exe'\" | "
              "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }")


def _csv_pids(stdout, image):
    pids = []
    for line in stdout.splitlines():
        cells = [cell.strip('"') for cell in line.split('","')]
        if len(cells) > 1 and cells[0].strip('"').lower() == image and cells[1].strip('"').isdigit():
            pids.append(int(cells[1].strip('"')))
    return pids


def windows_task_list():
    """PIDs of DayZServer_x64.exe and of DayZDiag_x64.exe started with -server, from the Windows side (WSL interop).

    tasklist shows no command line, so DayZDiag is asked through PowerShell; when that cannot be done every
    DayZDiag_x64.exe counts (fail closed). [] when Windows cannot be asked at all."""
    tool = shutil.which('tasklist.exe')
    if not tool:
        return []

    def tasklist(image):
        return _csv_pids(subprocess.run([tool, '/FI', 'IMAGENAME eq ' + image, '/NH', '/FO', 'CSV'],
                                        capture_output=True, text=True, timeout=15, check=False).stdout, image)
    try:
        pids = tasklist('dayzserver_x64.exe')
    except (OSError, subprocess.SubprocessError):
        return []
    try:
        shell = shutil.which('powershell.exe')
        if not shell:
            raise OSError('no powershell.exe')
        done = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-Command', DIAG_QUERY],
                              capture_output=True, text=True, timeout=30, check=False)
        if done.returncode != 0:
            raise OSError('command line query failed')
        for line in done.stdout.splitlines():
            pid, _, command = line.partition('\t')
            if pid.strip().isdigit() and not command.strip():
                raise OSError('command line unavailable for pid %s' % pid.strip())  # unknown: fall back, fail closed
            if pid.strip().isdigit() and re.search(r'(^|\s)"?-server"?(\s|$)', command, re.I):
                pids.append(int(pid.strip()))
    except (OSError, subprocess.SubprocessError):
        try:
            pids += tasklist('dayzdiag_x64.exe')
        except (OSError, subprocess.SubprocessError):
            pass
    return pids


def find_server_processes(proc_root=Path('/proc'), query=windows_task_list):
    """PIDs whose command line names DayZServer_x64 (Linux /proc and Wine), plus the Windows task list. Best effort:
    a server started some way neither can see is not detected, so stop it before apply or rollback regardless."""
    found = set(query())
    try:
        entries = list(Path(proc_root).iterdir())
    except OSError:
        entries = []
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / 'cmdline').read_bytes()[:4096].decode('utf-8', 'replace').lower()
        except OSError:
            continue
        words = command.split('\0')
        program = words[0].replace('\\', '/').rsplit('/', 1)[-1]
        if 'dayzserver_x64' in program or ('dayzdiag_x64' in program and any(w == '-server' for w in words[1:])):
            found.add(int(entry.name))
    return sorted(found)


def running_servers():
    return find_server_processes()


def refuse_if_running():
    pids = running_servers()
    if pids:
        raise Refused('the DayZ server is running (pid %s); stop it before apply or rollback' % ', '.join(map(str, pids)))


def _normal(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())


def locate_expansion(workshop):
    """(found rows, missing rows) for the Expansion dependencies inside an existing Workshop/mods directory.

    A dependency is a real folder with an addons directory whose name is the Workshop id or a known name
    (case, '@' and punctuation ignored). Nothing here copies, opens for writing or modifies those folders."""
    folders = []
    for entry in sorted(workshop.iterdir()):
        if entry.is_dir() and not entry.is_symlink() and has_addons(entry):
            folders.append(entry)
    found, missing = [], []
    for label, workshop_id, aliases in EXPANSION_DEPENDENCIES:
        wanted = set(aliases) | ({workshop_id} if workshop_id else set())
        match = next((f for f in folders if _normal(f.name) in wanted), None)
        (found if match else missing).append({'label': label, 'id': workshop_id, 'path': match})
    return found, missing


def plan_interiors(profiles, repo):
    pack = no_links(repo / INTERIORS_PACK, 'interiors data pack')
    if not pack.is_dir():
        raise Refused('--interiors: the data pack is not in this checkout: %s' % INTERIORS_PACK)
    tool = load_tool('interiors_profile')
    try:
        report = tool.validate(pack)
    except (ValueError, OSError, KeyError, TypeError) as error:
        raise Refused('--interiors: the data pack failed validation: %s' % error) from None
    if report['errors']:
        raise Refused('--interiors: the data pack failed validation: %s' % '; '.join(map(str, report['errors'][:3])))
    target = no_links(profiles / 'HollowCountry', 'profiles/HollowCountry')
    if target.exists() and not target.is_dir():
        raise Refused('--interiors: %s is not a directory' % target)
    if os.path.lexists(target / tool.MANAGED):
        raise Refused('--interiors: an interiors install already exists in %s; run its rollback first' % target)
    rehearse_interiors(tool, pack, target, report)
    return {'pack': pack, 'target': target, 'pending': [row['id'] for row in report.get('pending', [])]}


def rehearse_interiors(tool, pack, target, report):
    """Run the interiors installer's own conflict checks on a scratch copy of the profile paths it would touch, so a
    different operator-owned interiors.json, a journal or a non-directory in the way refuses at plan time."""
    names = set(report.get('files') or ())
    try:
        manifest = json.loads(read_bytes(pack / 'pack.json', 'interiors pack.json', 65536))
        names |= set(manifest['files']) if isinstance(manifest.get('files'), dict) else set()
        config = json.loads(read_bytes(pack / 'interiors.json', 'interiors.json', 65536))
        if isinstance(config, dict) and isinstance(config.get('Epoch'), int) and not isinstance(config['Epoch'], bool):
            names.add('interiors_s1_e%d' % config['Epoch'])
    except (ValueError, OSError, AttributeError, Refused):
        pass
    scratch = Path(tempfile.mkdtemp(prefix='hc-interiors-rehearsal-'))
    try:
        copy = scratch / target.name
        if target.exists():
            copy.mkdir()
            for name in sorted(names | {tool.MANAGED}):
                relative = Path(name)
                if relative.is_absolute() or '..' in relative.parts:
                    continue
                for number, part in enumerate(relative.parts):
                    live = target.joinpath(*relative.parts[:number + 1])
                    if not os.path.lexists(live):
                        break
                    no_links(live, 'profiles/HollowCountry/' + '/'.join(relative.parts[:number + 1]))
                    here = copy.joinpath(*relative.parts[:number + 1])
                    if live.is_dir():
                        here.mkdir(exist_ok=True)
                    elif number == len(relative.parts) - 1:
                        here.write_bytes(read_bytes(live, '/'.join(relative.parts), MAX_BYTES))
                    else:
                        (copy.joinpath(*relative.parts[:number + 1])).write_bytes(b'')  # a file where a directory is needed
        try:
            tool.install(pack, copy)
        except (ValueError, OSError, KeyError, TypeError) as error:
            raise Refused('--interiors: the profile cannot take the data pack (nothing was changed): %s' % error) from None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def inside_directory(path, directory):
    """True when path is the directory or below it, after resolving symlinks and '..' on both sides."""
    resolved, base = Path(os.path.realpath(path)), Path(os.path.realpath(directory))
    return resolved == base or base in resolved.parents


def plan_expansion_ai(args, mod_plan, repo):
    if not (args.workshop_dir and args.expansion_ai_mod and args.expansion_ai_dest):
        raise Refused('--expansion-ai needs --workshop-dir, --expansion-ai-mod and --expansion-ai-dest')
    workshop = existing_dir(args.workshop_dir, 'Workshop mods directory', repo)
    found, missing = locate_expansion(workshop)
    if missing:
        raise Refused('--expansion-ai: not present in %s: %s. Subscribe to them in the Steam Workshop; this tool never '
                      'copies or repacks Expansion.' % (workshop, ', '.join(
                          row['label'] + (' (%s)' % row['id'] if row['id'] else '') for row in missing)))
    if absolute(args.expansion_ai_dest) == mod_plan['dest']:
        raise Refused('--expansion-ai-dest must differ from --mod-dest')
    inside = [(what, path) for what, path in (('--expansion-ai-mod', args.expansion_ai_mod),
                                              ('--expansion-ai-dest', args.expansion_ai_dest),
                                              ('--mod-dest', args.mod_dest), ('--profiles', args.profiles),
                                              ('--mission', args.mission), ('--server-root', args.server_root))
              if inside_directory(path, workshop)]
    if inside:
        raise Refused('%s must not be inside the Workshop directory %s (compared after resolving symlinks); the '
                      'Workshop folders are never written, copied or repacked' % (inside[0][0], workshop))
    mod = plan_mod(args.expansion_ai_mod, args.expansion_ai_dest, repo, AI_PBO_NAME, check=check_ai_pbo)
    try:
        json.loads(repo_file(repo, AI_MERGE))
    except (ValueError, Refused) as error:
        raise Refused('--expansion-ai: %s is not readable JSON: %s' % (AI_MERGE, error)) from None
    try:
        json.loads(repo_file(repo, AI_PATROL_OVERRIDE))
    except (ValueError, Refused) as error:
        raise Refused('--expansion-ai: %s is not readable JSON: %s' % (AI_PATROL_OVERRIDE, error)) from None
    return {'workshop': workshop, 'dependencies': found, 'mod': mod, 'merge': AI_MERGE,
            'patrol_override': AI_PATROL_OVERRIDE}


def ai_json(data, what):
    try:
        value = json.loads(data)
    except ValueError as error:
        raise Refused('--expansion-ai: %s is not readable JSON: %s' % (what, error)) from None
    if not isinstance(value, dict):
        raise Refused('--expansion-ai: %s must be a JSON object' % what)
    return value


def ai_target(path, base, what, repo):
    """A target under base (profiles or mission): no links on any existing ancestor, outside every checkout."""
    path = no_links(path, what)
    if base not in path.parents:
        raise Refused('%s is outside %s' % (what, base))
    outside_checkouts(path, what, repo)
    return path


def plan_ai_config(profiles, mission, repo):
    """The shipped HC AI files and the two Expansion settings changes, decided before any write.

    create: the sites policy, the loadouts and (when Expansion has not written one yet) the patrol override, each
    a fresh file. replace: an existing AIPatrolSettings.json that differs from the override, and the field merge
    into Expansion's own AISettings.json, which must already exist; both keep a byte-exact backup. A target that
    already holds the same bytes is left alone and never removed by rollback."""
    sources = [(profiles / AI_SITES_TARGET, AI_SITES)]
    try:
        names = sorted(p.name for p in (repo / AI_LOADOUTS).iterdir())
    except OSError:
        raise Refused('--expansion-ai: %s is missing' % AI_LOADOUTS) from None
    loadouts = [n for n in names if AI_LOADOUT_NAME.match(n)]
    if not loadouts or len(loadouts) != len(names):
        raise Refused('--expansion-ai: %s must hold only HollowCountry_<Name>.json loadouts' % AI_LOADOUTS)
    sources += [(profiles / AI_LOADOUTS_TARGET / n, AI_LOADOUTS + '/' + n) for n in loadouts]
    create, present, replace = [], [], []
    for target, relative in sources:
        data = repo_file(repo, relative)
        ai_json(data, relative)
        target = ai_target(target, profiles, 'Expansion AI target ' + target.name, repo)
        if os.path.lexists(target):
            if read_bytes(target, target.name) != data:
                raise Refused('--expansion-ai: %s exists with different content; refusing to replace it (move it '
                              'away or make it identical to %s)' % (target, relative))
            present.append(target)
        else:
            create.append({'path': target, 'data': data})
    patrols = ai_target(mission / AI_PATROL_TARGET, mission, 'AIPatrolSettings.json', repo)
    override = repo_file(repo, AI_PATROL_OVERRIDE)
    ai_json(override, AI_PATROL_OVERRIDE)
    if not os.path.lexists(patrols):
        create.append({'path': patrols, 'data': override})
    else:
        before = read_bytes(patrols, patrols.name)
        if before == override:
            present.append(patrols)
        else:
            replace.append({'path': patrols, 'before': before, 'after': override})
    settings = ai_target(profiles / AI_SETTINGS_TARGET, profiles, 'AISettings.json', repo)
    if not os.path.lexists(settings):
        raise Refused('--expansion-ai: %s is missing; start the server once with Expansion AI loaded so Expansion '
                      'writes its own AISettings.json, then plan again (the merge never creates the file)' % settings)
    before = read_bytes(settings, settings.name)
    current = ai_json(before, str(settings))
    merged = dict(current)
    merged.update(ai_json(repo_file(repo, AI_MERGE), AI_MERGE))
    if merged == current:
        present.append(settings)
    else:
        replace.append({'path': settings, 'before': before,
                        'after': (json.dumps(merged, indent=4) + '\n').encode('utf-8')})
    return {'create': create, 'present': present, 'replace': replace}


def verify_optional(tool_name, label, install, vanilla_dir):
    """Read-only verification of an installed optional mod with the tool's own verify_install and allowlist.

    Fail closed: only a 'verified' report may ever be turned into a delta."""
    tool = load_tool(tool_name)
    try:
        allowlist = json.loads(read_bytes(Path(tool.ALLOWLIST_PATH), label + ' allowlist', MAX_BYTES))
        kwargs = {} if vanilla_dir is None else {'vanilla': tool.load_vanilla(vanilla_dir)}
        report = tool.verify_install(install, allowlist, **kwargs)
    except (ValueError, OSError, KeyError, TypeError) as error:
        raise Refused('%s verification failed (nothing was changed): %s' % (label, error)) from None
    if report.get('status') != 'verified':
        problems = list(report.get('install', {}).get('problems', [])) + list(report.get('vanilla', {}).get('problems', []))
        problems += ['%s: %s' % (name, ' '.join(row.get('reasons', []) or [row.get('status', '?')]))
                     for name, row in sorted(report.get('classes', {}).items()) if row.get('status') != 'verified']
        raise Refused('%s install is not verified by %s, so no CE delta can be generated (nothing was changed); '
                      'drop the flag or fix the install: %s' % (label, tool_name, '; '.join(problems[:10]) or 'unverified'))
    return {'install': install, 'allowlist': allowlist, 'report': report,
            'allowlist_sha256': report.get('allowlist_sha256'), 'vanilla': vanilla_dir}


def rehearse_deltas(plan, repo):
    """Run economy, then the optional deltas, through the real installers on a scratch copy of the mission inputs.

    The optional deltas are generated from the economy-patched core, so they cannot be generated before the economy
    is installed; this is the only way to refuse a bad combination before apply writes anything."""
    economy = load_tool('economy')
    scratch = Path(tempfile.mkdtemp(prefix='hc-delta-rehearsal-'))
    try:
        copy = scratch / 'mission'
        copy.mkdir()
        for relative in getattr(economy, 'INPUTS', ()):
            (copy / relative).parent.mkdir(parents=True, exist_ok=True)
            (copy / relative).write_bytes(read_bytes(plan['mission'] / relative, relative, MAX_BYTES))
        try:
            economy.write_delta(scratch / 'economy', economy_delta(economy, copy, repo, plan['economy']))
            economy.install_delta(scratch / 'economy', copy)
        except (ValueError, OSError, KeyError, TypeError) as error:
            raise Refused('economy delta cannot be installed on a scratch copy of the mission: %s' % error) from None
        for step, tool_name, label in OPTIONAL_DELTAS:
            spec = plan[step + '_delta']
            if not spec:
                continue
            tool = load_tool(tool_name)
            try:
                tool.write_delta(scratch / step, tool.generate(copy, spec['allowlist'], spec['report']))
                tool.install(scratch / step, copy)
            except (ValueError, OSError, KeyError, TypeError) as error:
                raise Refused('%s delta cannot be generated for this mission (nothing was changed): %s' %
                              (label, error)) from None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def check_destinations(plan, mission, snafu, tf, ai, keys, plan_interiors_target=None):
    """Refuse when two planned write destinations, existing or not yet created, are equal or nested."""
    rows = [('session state', 0, plan['state']), ('mod destination', 1, plan['mod']['dest'])]
    if ai:
        rows.append(('Expansion AI destination', 2, ai['mod']['dest']))
    managed = []
    if plan['gameplay']:
        managed.append(('gameplay', 'gameplay'))
    if plan['economy']:
        managed.append(('economy', 'economy'))
    if snafu:
        managed.append(('SNAFU delta', 'snafu_optional'))
    if tf:
        managed.append(('Tactical Flava delta', 'tactical_flava_optional'))
    for label, tool_name in managed:
        rows.append((label + ' directory', 3, mission / load_tool(tool_name).MANAGED))
    if plan_interiors_target:
        rows.append(('interiors target', 4, plan_interiors_target))
    for key in keys:
        if key['state'] == 'missing':
            rows.append(('server key ' + key['name'], 5, key['path']))
    for first in range(len(rows)):
        for second in range(first + 1, len(rows)):
            (name_a, group_a, path_a), (name_b, group_b, path_b) = rows[first], rows[second]
            if group_a == group_b == 5:
                continue  # key files share the keys directory
            a, b = Path(os.path.realpath(path_a)), Path(os.path.realpath(path_b))
            if a == b or a in b.parents or b in a.parents:
                raise Refused('planned destinations collide: %s (%s) and %s (%s) are the same or nested; '
                              'choose another destination. Nothing was changed.' % (name_a, path_a, name_b, path_b))


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
        if not has_addons(snafu):
            raise Refused('SNAFU directory has no addons folder: %s' % snafu)
    tf = plan_tf(args.tactical_flava, repo) if args.tactical_flava else None
    wanted_ai = bool(getattr(args, 'expansion_ai', False))
    if not wanted_ai and any(getattr(args, name, None) for name in ('workshop_dir', 'expansion_ai_mod', 'expansion_ai_dest')):
        raise Refused('--workshop-dir, --expansion-ai-mod and --expansion-ai-dest only apply with --expansion-ai')
    ai = plan_expansion_ai(args, mod_plan, repo) if wanted_ai else None
    vanilla_flag = getattr(args, 'vanilla_addons', None)
    if vanilla_flag and not args.tactical_flava:
        raise Refused('--vanilla-addons only applies with --tactical-flava')
    keys = server_key_plan(server_root, key_sources(mod_plan, tf, [ai['mod']] if ai else ()))
    if args.install_key and not keys:
        raise Refused('--install-key needs a signed @HollowCountry with keys/ or a --tactical-flava with keys/')
    mode, only = resolve_markers(*parse_markers(args.markers), repo)
    plan = {'server_root': server_root, 'state': state, 'cfg_path': cfg_path, 'cfg_before': cfg_bytes,
            'cfg_after': new_text.encode('utf-8'), 'changes': changes, 'cfg_facts': cfg_facts(cfg_text),
            'mission': mission, 'profiles': profiles, 'mod': mod_plan, 'snafu': snafu, 'tf': tf, 'keys': keys,
            'time_accel': float(args.time_accel), 'night_accel': float(args.night_accel),
            'markers_mode': mode, 'markers_only': only, 'warnings': [], 'repo': repo,
            'install_key': bool(args.install_key), 'expansion_ai': ai,
            'interiors': plan_interiors(profiles, repo) if getattr(args, 'interiors', False) else None,
            'running': running_servers()}
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
        spec = {'profile': ECONOMY_PROFILES + name + '.json',
                'roster': None if getattr(args, 'no_roster', False) else FIREARMS_ROSTER}
        try:
            economy_delta(economy, mission, repo, spec)
        except (ValueError, OSError, KeyError, TypeError) as error:
            raise Refused('economy delta cannot be generated for this mission: %s' % error) from None
        plan['economy'] = spec
    plan['snafu_delta'] = plan['tactical_flava_delta'] = None
    check_destinations(plan, mission, snafu, tf, ai, keys if args.install_key else (),
                       plan_interiors_target=getattr(args, 'interiors', False) and profiles / 'HollowCountry')
    if snafu or tf:
        if not plan['economy']:
            raise Refused('--snafu and --tactical-flava install CE deltas on top of the economy delta; '
                          'do not combine them with --economy-profile none')
        for step, tool_name, label in OPTIONAL_DELTAS:
            if (snafu if step == 'snafu' else tf) is None:
                continue
            managed = load_tool(tool_name).MANAGED
            if os.path.lexists(mission / managed):
                raise Refused('%s delta: %s already exists in the mission (an earlier install or an operator-owned '
                              'path); remove it or run its rollback first. Nothing was changed.' %
                              (label, mission / managed))
        if snafu:
            plan['snafu_delta'] = verify_optional('snafu_optional', 'SNAFU', snafu, None)
        if tf:
            vanilla = Path(vanilla_flag) if vanilla_flag else server_root / 'addons'
            if not vanilla.is_dir():
                raise Refused('Tactical Flava verification needs the game\'s own Addons folder; %s is not a directory '
                              '(pass --vanilla-addons <DayZ server dir>/addons)' % vanilla)
            vanilla = existing_dir(vanilla, 'vanilla addons directory', repo)
            plan['tactical_flava_delta'] = verify_optional('tactical_flava_optional', 'Tactical Flava', tf['dir'], vanilla)
        rehearse_deltas(plan, repo)
    if ai:
        ai['config'] = plan_ai_config(profiles, mission, repo)
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

    ai = plan.get('expansion_ai')
    # -mod= (server and client): Expansion's own folders, SNAFU, Tactical Flava, HC. The HC Expansion AI addon
    # is server-only: -serverMod= on the server command, after HollowCountry; clients never load it.
    mods = [win(row['path']) for row in ai['dependencies']] if ai else []
    if plan['snafu']:
        mods.append(win(plan['snafu']))
    if plan['tf']:
        mods.append(win(plan['tf']['dir']))
    mods.append(win(plan['mod']['dest']))
    mod_argument = '-mod=' + ';'.join(mods)
    server_mod = ['-serverMod=' + win(ai['mod']['dest'])] if ai else []
    root = win(plan['server_root'])
    port, query = args.game_port, args.query_port
    server_arguments = ['-config=' + win(plan['cfg_path']), '-profiles=' + win(plan['profiles']), mod_argument,
                        *server_mod, '-mission=' + win(plan['mission']), '-ip=127.0.0.1', '-port=%d' % port,
                        '-doLogs', '-adminLog']
    server = ['Set-Location -LiteralPath ' + ps_quote(root),
              '& ' + ps_quote(root + '\\DayZServer_x64.exe') + ' ' + ' '.join(ps_quote(a) for a in server_arguments)]
    client_arguments = ['0', '1', '1', '-exe', 'DayZ_x64.exe', mod_argument,
                        '-connect=127.0.0.1:%d:%d' % (port, query), '-port=%d' % port]
    client = ['Start-Process -FilePath ' + ps_quote(args.client_root + '\\DayZ_BE.exe')
              + ' -WorkingDirectory ' + ps_quote(args.client_root)
              + ' -ArgumentList @(' + ', '.join(ps_arg(a) for a in client_arguments) + ')']
    return {'server': server, 'client': client, 'warnings': notes[:1], 'mod': mod_argument,
            'server_mod': server_mod[0] if server_mod else None}


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
    if plan.get('running'):
        rows.append('The DayZ server is running (pid %s); apply and rollback refuse until it is stopped.' %
                    ', '.join(map(str, plan['running'])))
    if facts.get('password_set'):
        rows.append('The server has a password; add -password=<yours> to the client command (it is not printed here).')
    return rows


# ---------------------------------------------------------------- reporting

def expansion_lines(ai, profiles, mission, markers=None, markers_mode='all', applied=False):
    mod = ai['mod']
    out = ['6. Expansion AI (optional addon): stage %s (%s) from %d file(s), loaded server-only with -serverMod= '
           'after HollowCountry (players do not need it):' %
           (mod['dest'], 'signed, with keys/' if mod['signed'] else 'unsigned', len(mod['blobs']))]
    out += ['     %s  sha256 %s' % (name, mod['hashes'][name][:16]) for name in sorted(mod['hashes'])]
    out.append('     Required Workshop subscriptions (found in %s; read-only, never copied, never repacked):' % ai['workshop'])
    for row in ai['dependencies']:
        out.append('       %s%s -> %s' % (row['label'], ' ' + row['id'] if row['id'] else '', row['path']))
    config = ai['config']
    verb = 'created' if applied else 'create'
    out.append('     Expansion AI settings, installed by this tool and undone by rollback (backups in the session state):')
    for item in config['create']:
        out.append('       %s %s' % (verb, item['path']))
    for item in config['replace']:
        what = 'field merge of %s' % ai['merge'] if item['path'].name == 'AISettings.json' else ai['patrol_override']
        out.append('       %s %s (%s; byte-exact backup)' % ('replaced' if applied else 'replace', item['path'], what))
    for path in config['present']:
        out.append('       already identical, left alone: %s' % path)
    out.append('       (%s turns off Expansion\'s own default patrols; %s keeps every other AISettings.json field)' %
               (ai['patrol_override'], ai['merge']))
    out.append('     MANUAL check: keep the Expansion admin unlimited-reload controls OFF; HC sites refuse to start otherwise.')
    found = [item for item in (markers or {}).get('files', []) if item.get('name') == AI_MARKER]
    if not found:
        out.append('     WARNING: the %s opt-in marker is not part of this session (--markers %s): HC sites stay off.' %
                   (AI_MARKER, markers_mode))
    elif found[0].get('action') == 'exists':
        out.append('     %s opt-in marker: already present' % AI_MARKER)
    else:
        out.append('     %s opt-in marker: %s' % (AI_MARKER, 'created' if applied else 'will be created'))
    out.append('     Lease policy: %s/%s (HC event leases) is written as a template on first start and is not' %
               (profiles, AI_POLICY_TARGET))
    out.append('       generated here; the shipped sites above do not depend on it.')
    return out


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
    out.append('     economy (CE delta, profile %s%s): %s' % (
        args.economy_profile, ', firearms roster' if plan['economy'] and plan['economy'].get('roster') else '',
        'install' if plan['economy'] else 'skipped'))
    out.append('4. Acceptance markers in %s: %s' % (plan['profiles'], plan['markers_mode'] if plan['markers_mode'] != 'names' else ','.join(plan['markers_only'])))
    for item in (plan['markers'] or {}).get('files', []):
        out.append('     %s.enable [%s]' % (item['name'], item['action']))
    if plan.get('interiors'):
        info = plan['interiors']
        out.append('5. Interiors data pack: install %s into %s with interiors_profile (receipt, byte-exact rollback)' %
                   (info['pack'], info['target']))
        if info['pending']:
            out.append('     pending components (not installed, need a native measurement): %s' % ', '.join(info['pending']))
    if plan.get('expansion_ai'):
        out += expansion_lines(plan['expansion_ai'], plan['profiles'], plan['mission'], plan['markers'],
                               plan['markers_mode'], applied)
    if plan['snafu']:
        out.append('   SNAFU (read-only, optional dependency): %s' % plan['snafu'])
    if plan.get('snafu_delta'):
        out.append('     SNAFU subset CE delta: snafu_optional verify (read-only install, status %s), generate, install '
                   'after the economy delta; only the generated delta files are written to the mission' %
                   plan['snafu_delta']['report']['status'])
    if plan['tf']:
        out.append('   Tactical Flava (read-only, optional dependency): %s' % plan['tf']['dir'])
    if plan.get('tactical_flava_delta'):
        out.append('     Tactical Flava subset CE delta: tactical_flava_optional verify (read-only install, vanilla '
                   'classes from %s, status %s), generate, install after the economy delta; only the generated delta '
                   'files are written to the mission' % (plan['tactical_flava_delta']['vanilla'],
                                                         plan['tactical_flava_delta']['report']['status']))
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


def optional_receipt(spec):
    if not spec:
        return None
    row = {'install': str(spec['install']), 'allowlist_sha256': spec['allowlist_sha256'],
           'verification': spec['report']['status']}
    if spec['vanilla'] is not None:
        row['vanilla_addons'] = str(spec['vanilla'])
    return row


def apply_plan(plan, args):
    """Write the session. Every creation is recorded in the receipt (fsynced) BEFORE it happens, so a run that
    is killed at any point leaves a receipt that names everything the run may have created."""
    repo, state = plan['repo'], plan['state']
    if plan.get('running'):  # a server seen while planning must stop apply before any write
        raise Refused('the DayZ server is running (pid %s); stop it before apply or rollback' %
                      ', '.join(map(str, plan['running'])))
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
                    'interiors': {'target': str(plan['interiors']['target']), 'pack': str(plan['interiors']['pack'])}
                    if plan['interiors'] else None,
                    'snafu_delta': optional_receipt(plan.get('snafu_delta')),
                    'tactical_flava_delta': optional_receipt(plan.get('tactical_flava_delta')),
                    'expansion_ai': {'dest': str(plan['expansion_ai']['mod']['dest']),
                                     'files': plan['expansion_ai']['mod']['hashes'],
                                     'sizes': {n: len(b) for n, b in plan['expansion_ai']['mod']['blobs'].items()},
                                     'signed': plan['expansion_ai']['mod']['signed'],
                                     'workshop': str(plan['expansion_ai']['workshop']),
                                     'dependencies': {r['label']: str(r['path']) for r in plan['expansion_ai']['dependencies']}}
                    if plan['expansion_ai'] else None,
                    'expansion_ai_config': {'created': [], 'replaced': [], 'dirs': []} if plan['expansion_ai'] else None,
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
        economy.write_delta(stage, economy_delta(economy, plan['mission'], repo, plan['economy']))
        economy.install_delta(stage, plan['mission'])
        receipt.step('economy', 'done')
    # 4b. optional-subset CE deltas through their own installers, on top of the economy-patched core (SNAFU first)
    for step, tool_name, label in OPTIONAL_DELTAS:
        spec = plan.get(step + '_delta')
        if spec:
            tool = load_tool(tool_name)
            receipt.step(step, 'started')
            stage = stage_directory(state, step)
            tool.write_delta(stage, tool.generate(plan['mission'], spec['allowlist'], spec['report']))
            tool.install(stage, plan['mission'])
            receipt.step(step, 'done')
    # 5. interiors data pack, through its own installer (own receipt, byte-exact rollback)
    if plan['interiors']:
        interiors = load_tool('interiors_profile')
        receipt.step('interiors', 'started')
        interiors.install(plan['interiors']['pack'], plan['interiors']['target'])
        receipt.step('interiors', 'done')
    # 6. the optional Expansion AI addon folder (Expansion's own Workshop folders are never touched)
    if plan['expansion_ai']:
        ai_mod = plan['expansion_ai']['mod']
        receipt.step('expansion_ai', 'started')
        try:
            ai_mod['dest'].mkdir()
        except FileExistsError:
            receipt.data['expansion_ai']['files'] = {}
            receipt.step('expansion_ai', 'refused')
            raise Refused('Expansion AI addon destination appeared after the plan was made: %s' % ai_mod['dest']) from None
        assemble_mod(ai_mod, stage=state)
        receipt.step('expansion_ai', 'done')
        apply_ai_config(plan['expansion_ai']['config'], receipt, state)
    # 7. markers
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


def apply_ai_config(config, receipt, state):
    """6b. The shipped HC AI files and the two Expansion settings changes. Every directory, backup and file is in
    the receipt before it is created; a replaced file is re-read and must still be what the plan saw."""
    record = receipt.data['expansion_ai_config']
    receipt.step('expansion_ai_config', 'started')
    for item in config['create']:
        missing, directory = [], item['path'].parent
        while not os.path.lexists(directory):
            missing.append(directory)
            directory = directory.parent
        for directory in reversed(missing):
            record['dirs'].append(str(directory))
            receipt.save()
            directory.mkdir()
    for index, item in enumerate(config['replace']):
        backup = state / ('expansion-ai-backup-%d' % index)
        write_new(backup, item['before'], mode_of(item['path']))
        entry = {'path': str(item['path']), 'before_sha256': sha(item['before']),
                 'after_sha256': sha(item['after']), 'backup': backup.name, 'state': 'intent'}
        record['replaced'].append(entry)
        receipt.save()  # intent first: a run killed after this line may or may not have switched the file
        if read_bytes(item['path'], item['path'].name) != item['before']:
            # Never switched: whatever is there now (even the very bytes we would write) is the operator's.
            entry['state'] = 'skipped'
            receipt.save()
            raise Refused('%s changed since the plan was made; run rollback, then plan again' % item['path'])
        replace_with(item['path'], item['after'], mode_of(item['path']), temp=state / ('expansion-ai-next-%d' % index))
        entry['state'] = 'replaced'
        receipt.save()
    for item in config['create']:
        entry = {'path': str(item['path']), 'sha256': sha(item['data']), 'state': 'intent'}
        record['created'].append(entry)
        receipt.save()  # intent first: the file may or may not exist when this run is killed
        try:
            write_new(item['path'], item['data'], 0o644, stage=state)
        except Refused:
            entry['state'] = 'skipped'  # an exclusive create refused: the file is not ours
            receipt.save()
            raise
        entry['state'] = 'created'
        receipt.save()
    receipt.step('expansion_ai_config', 'done')


def ai_config_rollback(record, state, profiles, mission):
    """(step, description, action) undoing 6b; every refusal is decided here, before any step runs."""
    settings, patrols = profiles / AI_SETTINGS_TARGET, mission / AI_PATROL_TARGET
    places = (profiles / 'HollowCountry', profiles / AI_LOADOUTS_TARGET, patrols.parent)
    restores, files, notes, staged = [], [], [], []
    for item in record['replaced']:
        path = absolute(item['path'])
        if path not in (settings, patrols):
            raise Refused('receipt lists an Expansion AI settings file outside its known place')
        if item.get('state') == 'skipped':
            continue  # apply refused before the switch: the file was never ours to restore
        current = sha(read_bytes(path, path.name))
        if current == item['before_sha256']:
            continue  # never replaced, or an earlier rollback already restored it
        if current != item['after_sha256']:
            raise Refused('Expansion AI settings drift: %s no longer matches what apply wrote; nothing was changed '
                          'and the backup %s is kept in the session state. Reconcile it by hand, then run rollback '
                          'again.' % (path, item['backup']))
        backup = read_bytes(state / item['backup'], 'backup of ' + path.name)
        if sha(backup) != item['before_sha256']:
            raise Refused('the backup of %s does not match its receipt' % path.name)
        restores.append((path, backup, item['backup']))
    for item in record['created']:
        path = absolute(item['path'])
        if path.parent not in places:
            raise Refused('receipt lists an Expansion AI file outside its known places')
        if item.get('state', 'created') in ('intent', 'created'):
            owned, note, links = owned_file(path, item['sha256'], 'Expansion AI file ' + path.name, state)
            staged.extend(links)
            if owned:
                files.append(owned)
            if note:
                notes.append(note)
    directories = [absolute(text) for text in record['dirs']]
    if any(profiles not in d.parents and mission not in d.parents for d in directories):
        raise Refused('receipt lists an Expansion AI directory outside the profiles and mission directories')
    directories.sort(key=lambda d: len(d.parts), reverse=True)

    def run():
        for path, backup, name in restores:
            replace_with(path, backup, mode_of(path), temp=state / (name + '.restore'))
        _remove_files(files, directories, staged)()
    return ('expansion_ai_config', '; '.join(['Expansion AI settings: remove %d file(s), restore %d from backup' %
                                             (len(files), len(restores))] + notes), run)


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


def trial_rollback(name, tool, mission, started, above=(), inputs=()):
    """Run the existing installer's real rollback on a scratch copy of what it reads: 'run' or 'noop'.

    The installers validate everything before they change anything, but they cannot be asked in advance
    without changing something (economy has no dry run), so the same code runs on a copy first.
    `above` are the (name, tool) pairs whose real rollback runs before this one (the CE deltas installed after
    it); they are rolled back on the copy first, because each later install patched the core this one reads."""
    chain = list(above) + [(name, tool)]
    for label, member in chain:
        managed = mission / member.MANAGED
        for path in (managed, *sorted(managed.rglob('*'))):
            no_links(path, label + ' managed path')
            if path.is_file():
                regular(path, label + ' managed file ' + path.name)
    scratch = Path(tempfile.mkdtemp(prefix='hc-rollback-trial-'))
    try:
        copy = scratch / 'mission'
        copy.mkdir()
        for label, member in chain:
            shutil.copytree(mission / member.MANAGED, copy / member.MANAGED, symlinks=True)
        for relative in (getattr(tool, 'INPUTS', None) or inputs):
            source = mission / relative
            if os.path.lexists(source):
                (copy / relative).parent.mkdir(parents=True, exist_ok=True)
                (copy / relative).write_bytes(read_bytes(source, relative, MAX_BYTES))
        for label, member in above:
            try:
                member.rollback(copy)
            except (ValueError, OSError, KeyError, TypeError) as error:
                raise Refused('%s rollback would be refused (nothing was changed; the receipt is kept): %s' %
                              (label, error)) from None
        try:
            tool.rollback(copy)
        except (ValueError, OSError, KeyError, TypeError) as error:
            # An install that never wrote its own receipt has nothing to undo; anything else refuses now.
            if started and ('nothing to roll back' in str(error)):
                return 'noop'
            raise Refused('%s rollback would be refused (nothing was changed; the receipt is kept): %s' %
                          (name, error)) from None
        return 'run'
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def trial_interiors_rollback(tool, target, started, markers):
    """The interiors installer's real rollback on a scratch copy of <profiles>/HollowCountry: 'run' or 'noop'.

    The markers this session created are removed from the copy first, because the real rollback runs after the
    marker step has removed them; anything else found in the directory (the operator's files) refuses now."""
    managed = target / tool.MANAGED
    for path in (managed, *sorted(managed.rglob('*'))):
        no_links(path, 'interiors managed path')
        if path.is_file():
            regular(path, 'interiors managed file ' + path.name)
    # The scratch copy below loses link counts, so every live file in the profile is checked first, where it is:
    # a hard-linked, special or symlinked file refuses now, so the dry run and the real run agree and nothing moves.
    for path in sorted(target.rglob('*')):
        no_links(path, 'interiors profile path')
        if path.is_file():
            regular(path, 'interiors profile file ' + path.relative_to(target).as_posix())
        elif not path.is_dir():
            raise Refused('interiors profile path %s is not a regular file or directory' % path.relative_to(target))
    scratch = Path(tempfile.mkdtemp(prefix='hc-rollback-trial-'))
    try:
        copy = scratch / target.name
        shutil.copytree(target, copy, symlinks=True)
        for text in markers['created']:
            path = copy / absolute(text).relative_to(target) if target in absolute(text).parents else None
            if path is not None and os.path.lexists(path):
                path.unlink()
        for text in sorted(markers.get('dirs', []), key=len, reverse=True):
            path = absolute(text)
            if path != target and target in path.parents and (copy / path.relative_to(target)).is_dir():
                try:
                    (copy / path.relative_to(target)).rmdir()
                except OSError:
                    pass
        try:
            tool.rollback(copy)
        except (ValueError, OSError, KeyError, TypeError) as error:
            if started and ('nothing to roll back' in str(error)):
                return 'noop'
            raise Refused('interiors rollback would be refused (nothing was changed; the receipt is kept): %s' %
                          error) from None
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


def _remove_empty(directory):
    def run():
        try:
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

    if steps.get('expansion_ai_config') and progress.get('expansion_ai_config') != 'done' and data.get('expansion_ai_config'):
        todo.append(ai_config_rollback(data['expansion_ai_config'], state, profiles, mission))

    if steps.get('expansion_ai') in ('started', 'done') and progress.get('expansion_ai') != 'done' and data.get('expansion_ai'):
        todo.append(mod_removal('expansion_ai', 'Expansion AI addon folder', data['expansion_ai'], state,
                                strict=steps['expansion_ai'] == 'done'))

    # Files later steps created under <profiles>/HollowCountry are gone by the time the interiors rollback runs.
    ai_config = data.get('expansion_ai_config') or {'created': [], 'dirs': []}
    session_files = {'created': list(data['markers']['created']) + [row['path'] for row in ai_config['created']],
                     'dirs': list(data['markers'].get('dirs', [])) + list(ai_config['dirs'])}
    if steps.get('interiors') and progress.get('interiors') != 'done' and data.get('interiors'):
        target = absolute(data['interiors']['target'])
        if target != profiles / 'HollowCountry':
            raise Refused('receipt names an interiors target outside the profiles directory')
        no_links(target, 'interiors target')
        tool = load_tool('interiors_profile')
        managed = target / tool.MANAGED
        if not os.path.lexists(managed):
            if progress.get('interiors') != 'started' and steps['interiors'] == 'done':
                raise Refused('interiors: the installer directory %s is missing; reconcile by hand' % managed)
            todo.append(('interiors', 'interiors: installer already rolled back, nothing to undo', noop))
        elif trial_interiors_rollback(tool, target, steps['interiors'] == 'started', session_files) == 'noop':
            todo.append(('interiors', 'interiors: installer wrote no receipt, nothing to undo', _remove_empty(managed)))
        else:
            todo.append(('interiors', 'interiors: existing installer rollback on %s' % target,
                         lambda tool=tool, target=target: run_installer_rollback('interiors', tool, target)))

    above = []  # CE-stack installers that roll back before the next one (their trial runs on top of them)
    for name in ('tactical_flava', 'snafu', 'economy', 'gameplay'):
        if not steps.get(name) or progress.get(name) == 'done':
            continue
        tool = load_tool(STEP_TOOLS[name])
        managed = mission / tool.MANAGED
        if not os.path.lexists(managed):
            # Gone because an interrupted rollback already ran the installer, or the install never got that far;
            # for a finished install anything else means someone moved it away.
            if progress.get(name) != 'started' and steps[name] == 'done':
                raise Refused('%s: the installer directory %s is missing; reconcile by hand' % (name, managed))
            todo.append((name, '%s: installer already rolled back, nothing to undo' % name, noop))
        elif trial_rollback(name, tool, mission, steps[name] == 'started',
                            above if name in STACK_STEPS else (),
                            getattr(load_tool('economy'), 'INPUTS', ()) if name in STACK_STEPS else ()) == 'noop':
            todo.append((name, '%s: installer wrote no receipt, nothing to undo' % name, _remove_empty(managed)))
        else:
            todo.append((name, '%s: existing installer rollback on %s' % (name, mission),
                         lambda name=name, tool=tool: run_installer_rollback(name, tool, mission)))
            if name in STACK_STEPS:
                above.append((name, tool))

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
        todo.append(mod_removal('mod', 'mod folder', data['mod'], state))
    return receipt, state, todo


def mod_removal(step, label, mod, state, strict=False):
    """(step, description, action) removing the files a session recorded creating in one mod folder.

    strict (a finished install): a recorded file that is no longer byte-for-byte what the receipt says refuses the
    whole rollback now, before any step runs; otherwise such a file is left in place with a note."""
    mod_dest = no_links(mod['dest'], label)
    files, notes, staged = [], [], []
    for name, digest in sorted(mod['files'].items()):
        if not MOD_FILE.match(name):
            raise Refused('receipt lists a mod file outside the mod folder')
        owned, note, links = owned_file(mod_dest / name, digest, 'mod file ' + name, state)
        staged.extend(links)
        if owned:
            files.append(owned)
        if note:
            if strict:
                raise Refused('%s drift: %s no longer matches the receipt (%s); nothing was changed and the receipt is '
                              'kept. Restore the file or remove it yourself, then run rollback again.' % (label, name, note))
            notes.append(note)
    return (step, '; '.join(['%s: remove %d file(s) from %s' % (label, len(files), mod_dest)] + notes),
            _remove_files(files, [mod_dest / 'addons', mod_dest / 'keys', mod_dest], staged))


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
        p.add_argument('--vanilla-addons', type=Path, help='the game\'s own Addons folder, read-only, used to verify '
                       '--tactical-flava (default: <server root>/addons)')
        p.add_argument('--markers', default='all', help='all (every marker the code scan finds), none, all-local '
                       '(every marker in the docs/LOCAL_ACCEPTANCE_V1.md table) or comma-separated names from that table')
        p.add_argument('--interiors', action='store_true',
                       help='install the interiors data pack into <profiles>/HollowCountry (interiors_profile)')
        p.add_argument('--expansion-ai', action='store_true',
                       help='stage the optional @HollowCountryExpansionAI addon after the Expansion Workshop mods '
                       '(needs --workshop-dir, --expansion-ai-mod, --expansion-ai-dest)')
        p.add_argument('--workshop-dir', type=Path, help='directory holding the subscribed Workshop mod folders '
                       '(CF, Dabs Framework, Expansion-Animations, Expansion-Core, Expansion-AI); read-only')
        p.add_argument('--expansion-ai-mod', type=Path, help='built @HollowCountryExpansionAI dir (addons/%s) or a .pbo' % AI_PBO_NAME)
        p.add_argument('--expansion-ai-dest', type=Path, help='fresh @HollowCountryExpansionAI folder to create')
        p.add_argument('--time-accel', type=float, default=DEFAULT_TIME_ACCELERATION)
        p.add_argument('--night-accel', type=float, default=DEFAULT_NIGHT_ACCELERATION)
        p.add_argument('--economy-profile', default=DEFAULT_ECONOMY_PROFILE, help='economy profile name or none')
        p.add_argument('--no-roster', action='store_true',
                       help='leave the firearms roster (%s) out of the economy delta' % FIREARMS_ROSTER)
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
        if args.command == 'apply' or (args.command == 'rollback' and not args.dry_run):
            refuse_if_running()
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
