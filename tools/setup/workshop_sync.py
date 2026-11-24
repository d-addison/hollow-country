"""Server-side Steam Workshop sync for the Hollow Country mod set (standard library only).

Subcommands: ``plan`` (read-only), ``fetch`` (steamcmd download), ``install`` (copy into the server
root) and ``rollback`` (remove exactly what install added). The mod set comes from
``tools/setup/workshop_mods.json``: Workshop ids, server folder names, load order, client or server side
and an optional group (base, snafu, tactical_flava, pve_patrols).

Safety rules:

* Credentials. ``fetch`` runs ``steamcmd +login <user> ...`` with the operator's own terminal. There is no
  password option; the operator types the password and the Steam Guard code into steamcmd, which this tool
  neither reads, captures, stores nor logs (it passes no stdin, stdout, stderr or environment overrides).
* ``install`` copies (never symlinks) each item into ``<server-root>/@<Folder>`` and its public .bikey files
  into ``<server-root>/keys``. It copies only addons/*.pbo and *.bisign, keys/*.bikey, mod.cpp and meta.cpp.
  Anything else in an item is skipped and listed; a private key, a symlink or an unexpected file inside
  addons/ or keys/ refuses the item. It refuses to overwrite a different file, checks everything before it
  writes anything, and is idempotent.
* It writes ``hollow-country-workshop-receipt.json`` in the server root. ``rollback`` removes only the files
  recorded there (and only if they still match the recorded SHA-256) and the now-empty folders it created.
* ``install`` and ``rollback`` refuse while a DayZ server process is running; ``--assume-stopped`` skips the
  check (also needed where the process list cannot be read).
* Our own mods are published as Unlisted Workshop items: @HollowCountry and the optional
  @HollowCountryExpansionAI. One with an id in the manifest is fetched and installed like a third-party item.
  One whose id is still null ("unpublished") is listed in the launch lines but never fetched or copied here;
  copy its signed folder into the server root yourself. @HollowCountryExpansionAI goes at the end of
  -mod after @HollowCountry on the server and every client; players subscribe to it when the server uses it.

The printed ``-mod=`` list is shared by server and clients and follows the documented load order (CF,
COT, Dabs Framework, Expansion Core, AI, Navigation, the weapons packs, RaG_Core,
RaG Immersive Vehicles, Ambient Animals, @HollowCountry, then
@HollowCountryExpansionAI). A ``-serverMod=`` line is omitted when no server-only items remain.
Offline checks establish nothing about DayZ behaviour: the join-time auto-subscribe, signature checks and the
mod set at runtime stay pending the owner's acceptance.
"""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import ntpath
import re
import shutil
import stat
import subprocess
import sys
import tempfile

SCHEMA = 1
APP_ID = '221100'
DEFAULT_MANIFEST = Path(__file__).with_name('workshop_mods.json')
RECEIPT_NAME = 'hollow-country-workshop-receipt.json'
SERVER_EXE = 'DayZServer_x64.exe'
GROUPS = ('base', 'snafu', 'tactical_flava', 'living_packs', 'pve_patrols')
SIDES = ('client', 'server')
BASE_FOLDER = '@HollowCountry'
ID = re.compile(r'^[1-9][0-9]{5,12}$')
FOLDER = re.compile(r'^@[A-Za-z0-9][A-Za-z0-9_.-]*$')
STEAM_USER = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$')
NAME = r'[A-Za-z0-9_@+-][A-Za-z0-9_.@+-]*'
ADDON = re.compile(r'^' + NAME + r'\.(?:pbo|bisign)$', re.IGNORECASE)
KEY = re.compile(r'^[A-Za-z0-9_-][A-Za-z0-9_.-]*\.bikey$', re.IGNORECASE)
TOP_FILES = re.compile(r'^(?:mod|meta)\.cpp$', re.IGNORECASE)
RECEIPT_FILE = re.compile(r'^(?:@[A-Za-z0-9][A-Za-z0-9_.-]*/(?:(?:addons|keys)/' + NAME + r'|(?:mod|meta)\.cpp)'
                          r'|keys/[A-Za-z0-9_-][A-Za-z0-9_.-]*\.bikey)$', re.IGNORECASE)
RECEIPT_DIR = re.compile(r'^(?:keys|@[A-Za-z0-9][A-Za-z0-9_.-]*(?:/(?:addons|keys))?)$')
SHA256 = re.compile(r'^[0-9a-f]{64}$')


class SyncError(ValueError):
    """A safety rule or precondition failed; nothing further was written."""


# ---------------------------------------------------------------- manifest and selection
def load_manifest(path=None):
    path = Path(path or DEFAULT_MANIFEST)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise SyncError('cannot read manifest %s: %s' % (path, exc))
    if not isinstance(data, dict) or data.get('schema') != SCHEMA or not isinstance(data.get('mods'), list):
        raise SyncError('manifest %s has an unknown schema' % path)
    seen_ids, seen_folders, seen_ranks = set(), set(), set()
    for mod in data['mods']:
        if not isinstance(mod, dict):
            raise SyncError('manifest entry is not an object')
        name = mod.get('name')
        if not isinstance(name, str) or not name:
            raise SyncError('manifest entry without a name')
        if mod.get('id') is not None and not (isinstance(mod['id'], str) and ID.match(mod['id'])):
            raise SyncError('%s: bad Workshop id %r' % (name, mod.get('id')))
        if not (isinstance(mod.get('folder'), str) and FOLDER.match(mod['folder'])):
            raise SyncError('%s: bad server folder %r (must look like @Name)' % (name, mod.get('folder')))
        if isinstance(mod.get('rank'), bool) or not isinstance(mod.get('rank'), int):
            raise SyncError('%s: rank must be an integer' % name)
        if mod.get('side') not in SIDES:
            raise SyncError('%s: side must be one of %s' % (name, ', '.join(SIDES)))
        if mod.get('group') not in GROUPS:
            raise SyncError('%s: group must be one of %s' % (name, ', '.join(GROUPS)))
        if not isinstance(mod.get('publish'), bool):
            raise SyncError('%s: publish must be true or false' % name)
        for seen, key in ((seen_folders, 'folder'), (seen_ranks, 'rank'), (seen_ids, 'id')):
            if mod.get(key) is None:
                continue
            if mod[key] in seen:
                raise SyncError('%s: duplicate %s %r' % (name, key, mod[key]))
            seen.add(mod[key])
    data['mods'] = sorted(data['mods'], key=lambda m: m['rank'])
    # Retired third-party items stay listed (id, folder, reason) so an install an older release made keeps
    # validating and rolling back; they are never selected, fetched or put on the -mod line.
    retired = data.get('retired', [])
    if not isinstance(retired, list):
        raise SyncError('manifest retired list is not a list')
    for mod in retired:
        if not (isinstance(mod, dict) and isinstance(mod.get('name'), str) and mod['name']
                and isinstance(mod.get('folder'), str) and FOLDER.match(mod['folder'])
                and isinstance(mod.get('id'), str) and ID.match(mod['id'])
                and isinstance(mod.get('reason'), str) and mod['reason']):
            raise SyncError('manifest retired entry needs name, id, folder and reason')
        if mod['folder'] in seen_folders or mod['id'] in seen_ids:
            raise SyncError('%s: retired item is still an active manifest entry' % mod['name'])
    data['retired'] = retired
    return data


def parse_groups(text):
    groups = [g.strip() for g in (text or '').split(',') if g.strip()]
    if not groups:
        raise SyncError('--groups is empty; choose from %s' % ', '.join(GROUPS))
    for group in groups:
        if group not in GROUPS:
            raise SyncError('unknown group %r; choose from %s' % (group, ', '.join(GROUPS)))
    return groups


def select(manifest, groups, hollowcountry_id=None):
    """Items in the chosen groups in load order. ``hollowcountry_id`` fills the base mod's id if it has none."""
    chosen = []
    for mod in manifest['mods']:
        if mod['group'] not in groups:
            continue
        item = dict(mod)
        if item['id'] is None and item['folder'] == BASE_FOLDER and hollowcountry_id:
            item['id'] = str(hollowcountry_id)
        chosen.append(item)
    return chosen


def launch_lines(items):
    """Shared server/client -mod list, plus -serverMod only for server-only manifest entries."""
    client = [i['folder'] for i in items if i['side'] == 'client']
    server = [i['folder'] for i in items if i['side'] == 'server']
    lines = []
    if client:
        lines.append('-mod=' + ';'.join(client))
    if server:
        lines.append('-serverMod=' + ';'.join(server))
    return lines


# ---------------------------------------------------------------- locating Workshop content
def content_dirs(workshop_content=(), steamcmd=None, install_dir=None):
    """Where downloaded items may be: explicit dirs, the --install-dir tree and the steamcmd folder's tree."""
    dirs = [Path(p) for p in workshop_content or ()]
    tail = Path('steamapps') / 'workshop' / 'content' / APP_ID
    if install_dir:
        dirs.append(Path(install_dir) / tail)
    if steamcmd:
        located = Path(steamcmd)
        if located.parent != Path('.'):
            dirs.append(located.parent / tail)
    unique = []
    for path in dirs:
        if path not in unique:
            unique.append(path)
    return unique


def inspect_item(path):
    """('present' | 'incomplete', detail) for one Workshop item directory."""
    missing = []
    addons, keys = path / 'addons', path / 'keys'
    if not addons.is_dir() or not any(p.suffix.lower() == '.pbo' for p in addons.iterdir()):
        missing.append('addons/ (no .pbo)')
    if not keys.is_dir() or not any(p.suffix.lower() == '.bikey' for p in keys.iterdir()):
        missing.append('keys/ (no .bikey)')
    return ('incomplete', 'missing ' + ', '.join(missing)) if missing else ('present', '')


def item_timestamp(path):
    """Steam's meta.cpp timestamp (observed in installed Workshop metadata), or zero if absent."""
    meta = case_path(Path(path), 'meta.cpp')
    if not meta.is_file() or meta.is_symlink():
        return 0
    match = re.search(r'\btimestamp\s*=\s*(\d+)\s*;', meta.read_text(encoding='utf-8', errors='replace'))
    return int(match.group(1)) if match else 0


def case_path(root, rel):
    """Resolve Windows-style keys on either host; ambiguous case variants are a refusal."""
    current = Path(root)
    for part in Path(rel).parts:
        if current.is_symlink():
            raise SyncError('%s is a symlink' % current)
        matches = [p for p in current.iterdir() if p.name.casefold() == part.casefold()] if current.is_dir() else []
        if len(matches) > 1:
            raise SyncError('ambiguous case variants at %s/%s' % (current, part))
        current = matches[0] if matches else current / part
    return current


def find_item(item_id, dirs):
    """Newest complete copy by meta.cpp timestamp. Never use content Steam is downloading."""
    present, incomplete, updating = [], None, None
    for directory in dirs:
        directory = Path(directory)
        path = directory / item_id
        downloading = directory.parent.parent / 'downloads' / APP_ID / item_id
        if downloading.exists():
            updating = updating or path
            continue
        if path.is_dir() and not path.is_symlink():
            state, detail = inspect_item(path)
            if state == 'present':
                present.append((item_timestamp(path), path))
            else:
                incomplete = incomplete or (path, detail)
    # Even another complete copy might be older than the in-flight update: defer the whole item.
    if updating is not None:
        return 'content-updating', updating, 'Steam download in progress; folder skipped'
    if present:
        newest = max(present, key=lambda row: row[0])
        detail = ''
        disagree = len({stamp for stamp, _path in present}) > 1
        if len(present) > 1 and not disagree:
            # Equal metadata timestamps do not establish equal bytes. Compare allowlisted files,
            # checking sizes before hashes, just as the server comparison does.
            template = {'id': item_id, 'folder': '@source'}
            base_files, _skip = item_files(template, newest[1])
            baseline = {rel.casefold(): src for rel, src in base_files}
            for _stamp, candidate in present:
                if candidate == newest[1]:
                    continue
                files, _skip = item_files(template, candidate)
                other = {rel.casefold(): src for rel, src in files}
                if other.keys() != baseline.keys() or any(
                        baseline[rel].stat().st_size != src.stat().st_size or
                        sha256_of(baseline[rel]) != sha256_of(src) for rel, src in other.items()):
                    disagree = True
                    break
        if disagree:
            detail = 'WARN: Workshop sources disagree: ' + ', '.join('%s (timestamp %s)' % (p, t) for t, p in present)
        return 'present', newest[1], detail
    if incomplete:
        return 'incomplete', incomplete[0], incomplete[1]
    return 'missing', None, ''


# ---------------------------------------------------------------- server process detection
def _windows_server_running(server_root, executable='powershell'):
    """Scope readable image paths; inaccessible images remain unknown (fail closed)."""
    script = ("$ErrorActionPreference='Stop'; $p=@(Get-CimInstance Win32_Process "
              "-Filter \"Name='DayZServer_x64.exe'\" | Select-Object ExecutablePath); "
              "ConvertTo-Json -InputObject $p -Compress")
    try:
        done = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-Command', script],
                              capture_output=True, text=True, timeout=30)
        rows = json.loads(done.stdout.lstrip('\ufeff')) if done.returncode == 0 else None
        if not isinstance(rows, list):
            raise ValueError('process paths unavailable')
        root_text = str(server_root)
        # WSL's conventional drive mounts name the same Windows install.
        drive = re.match(r'^/mnt/([a-zA-Z])/(.*)$', root_text)
        if drive:
            root_text = drive.group(1) + ':\\' + drive.group(2).replace('/', '\\')
        elif not ntpath.isabs(root_text):
            root_text = os.path.abspath(root_text)
        wanted = ntpath.normcase(ntpath.normpath(root_text))
        unknown = False
        for row in rows:
            image = row.get('ExecutablePath') if isinstance(row, dict) else None
            if not isinstance(image, str) or not image:
                unknown = True
            elif ntpath.normcase(ntpath.dirname(ntpath.normpath(image))) == wanted:
                return True
        return None if unknown else False
    except (OSError, subprocess.SubprocessError, ValueError):
        # tasklist cannot establish a process's install folder. A hit is unknown,
        # rather than claiming an unrelated server belongs to this target.
        try:
            tasklist = 'tasklist.exe' if executable.endswith('.exe') else 'tasklist'
            done = subprocess.run([tasklist, '/V', '/FI', 'IMAGENAME eq ' + SERVER_EXE, '/NH'],
                                  capture_output=True, text=True, timeout=30)
            if done.returncode == 0 and SERVER_EXE.lower() not in (done.stdout or '').lower():
                return False
        except (OSError, subprocess.SubprocessError):
            pass
        return None


def server_running(server_root=None):
    """True if a DayZ server process is running, False if not, None if the process list cannot be read."""
    if server_root is not None and os.name == 'nt':
        return _windows_server_running(server_root)
    results = []
    if os.name == 'nt':
        commands = [['tasklist', '/FI', 'IMAGENAME eq ' + SERVER_EXE, '/NH']]
    else:
        commands = [['pgrep', '-f', r'(^|/)DayZServer_x64\.exe( |$)']]
        if shutil.which('tasklist.exe'):  # WSL can see Windows processes
            commands.append(['tasklist.exe', '/FI', 'IMAGENAME eq ' + SERVER_EXE, '/NH'])
    for command in commands:
        try:
            done = subprocess.run(command, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            results.append(None)
            continue
        if command[0].lower().startswith('tasklist'):
            results.append(_windows_server_running(server_root, 'powershell.exe') if server_root is not None else
                           SERVER_EXE.lower() in (done.stdout or '').lower() if done.returncode == 0 else None)
        else:
            if done.returncode == 0 and server_root is not None:
                # Resolve Linux/Wine image paths through procfs where available.
                states = []
                for pid in (done.stdout or '').split():
                    try:
                        image = Path('/proc') / pid / 'exe'
                        resolved = image.resolve(strict=True)
                        states.append(resolved.parent == Path(server_root).resolve()
                                      if resolved.name.casefold() == SERVER_EXE.casefold() else None)
                    except OSError:
                        states.append(None)
                results.append(True if True in states else None if not states or None in states else False)
            else:
                results.append(True if done.returncode == 0 else False if done.returncode == 1 else None)
    # Every probe must succeed and say "not running"; a probe that failed means unknown, never stopped.
    if any(r is True for r in results):
        return True
    if any(r is None for r in results):
        return None
    return False


def require_stopped(args):
    if getattr(args, 'assume_stopped', False):
        return
    state = server_running(getattr(args, 'server_root', None))
    if state:
        raise SyncError('a DayZ server process is running; stop it before changing mod files')
    if state is None:
        raise SyncError('cannot tell whether a DayZ server is running; stop it and pass --assume-stopped')


# ---------------------------------------------------------------- file helpers
def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def fsync_parent(path):
    """Persist the rename where directory fsync is supported (best effort on Windows)."""
    fd = None
    try:
        fd = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        os.fsync(fd)
    except OSError as error:
        if os.name != 'nt' and error.errno not in (errno.EINVAL, errno.ENOTSUP):
            raise
    finally:
        if fd is not None:
            os.close(fd)


def _write_atomic(path, writer, prefix, expected=None):
    fd, temp = tempfile.mkstemp(dir=str(path.parent), prefix=prefix, suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as handle:
            writer(handle)
            handle.flush()
            os.fsync(handle.fileno())
        if expected is not None and sha256_of(Path(temp)) != expected:
            raise SyncError("Workshop source changed during copy: %s" % path)
        os.chmod(temp, 0o644)
        os.replace(temp, path)
        fsync_parent(path)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def copy_atomic(source, target, expected=None):
    def copy(handle):
        with open(source, 'rb') as src:
            shutil.copyfileobj(src, handle, 1024 * 1024)
    _write_atomic(target, copy, '.sync-', expected)


def write_bytes_atomic(path, data):
    _write_atomic(path, lambda handle: handle.write(data), '.sync-')


def json_bytes(data):
    return (json.dumps(data, indent=2, sort_keys=True) + '\n').encode('utf-8')


def write_json_atomic(path, data):
    _write_atomic(path, lambda handle: handle.write(json_bytes(data)), '.receipt-')


def check_root(root):
    root = Path(root)
    if not root.is_dir():
        raise SyncError('server root %s is not a directory' % root)
    return root


def check_no_symlink_below(root, rel):
    current = root
    for part in rel.split('/'):
        current = current / part
        if current.is_symlink():
            raise SyncError('%s is a symlink; refusing to write or remove through it' % current)


# ---------------------------------------------------------------- what an item contributes
def item_files(item, source):
    """Allowlisted files of one Workshop item: ([(relative path, source path)], [skipped names])."""
    files, skipped = [], []
    pbos = keys = 0
    for entry in sorted(source.iterdir(), key=lambda p: p.name):
        name = entry.name
        if name.lower().endswith('.biprivatekey'):
            raise SyncError('%s contains a private key (%s); refusing the item' % (item['folder'], name))
        if name.lower() in ('addons', 'keys'):
            if entry.is_symlink() or not entry.is_dir():
                raise SyncError('%s/%s is a symlink or not a directory' % (item['id'], name))
            folder = name.lower()
            for child in sorted(entry.iterdir(), key=lambda p: p.name):
                rel = '%s/%s' % (folder, child.name)
                if child.is_symlink():
                    raise SyncError('%s/%s is a symlink; symlinks are never copied' % (item['id'], rel))
                if child.name.lower().endswith('.biprivatekey'):
                    raise SyncError('%s contains a private key (%s); refusing the item' % (item['folder'], rel))
                if not child.is_file():
                    raise SyncError('%s/%s is not a regular file' % (item['id'], rel))
                pattern = ADDON if folder == 'addons' else KEY
                if not pattern.match(child.name):
                    raise SyncError('%s/%s is not an allowed file (only %s)' % (
                        item['id'], rel, 'addons/*.pbo and *.bisign' if folder == 'addons' else 'keys/*.bikey'))
                pbos += child.name.lower().endswith('.pbo')
                keys += folder == 'keys'
                files.append((rel, child))
        elif TOP_FILES.match(name) and entry.is_file() and not entry.is_symlink():
            files.append((name, entry))
        else:
            skipped.append(name)
    if not pbos or not keys:
        raise SyncError('%s (%s) is incomplete: needs addons/*.pbo and keys/*.bikey' % (item['folder'], item['id']))
    return files, skipped


# ---------------------------------------------------------------- receipt
def bundle_key_dirs(args=None):
    """The bundle's keys folder as the standalone commands see it: --bundle-keys, else the keys folder next to
    tools/ in the unzipped bundle (this file is <bundle>/tools/setup/workshop_sync.py there). A folder that does not
    exist provides nothing."""
    given = getattr(args, 'bundle_keys', None)
    return [Path(given) if given else Path(__file__).resolve().parents[2] / 'keys']


def load_receipt(root, managed, extra_key_dirs=(), warn=None, repaired=None):
    """The validated receipt, or None. A root keys/*.bikey row ownership is checked against the receipt's own mod
    folders (exact name and bytes). A row an earlier release orphaned (retire_items kept the key because another mod
    or the bundle provides it, but left the row) is repaired here, never refused: the row is dropped, the file stays,
    and warn(text) says so. The repaired receipt is what callers see; repaired (a list), when given, receives the
    dropped paths so the caller can persist it (persist_repaired_receipt): a receipt nothing else rewrites would
    otherwise warn on every run."""
    path = root / RECEIPT_NAME
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise SyncError('%s is not a regular file' % path)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise SyncError('cannot read receipt %s: %s' % (path, exc))
    if not isinstance(data, dict) or data.get('schema') != SCHEMA or not isinstance(data.get('files'), list) \
            or not isinstance(data.get('dirs'), list):
        raise SyncError('receipt %s has an unknown schema' % path)
    for entry in data['files']:
        if not isinstance(entry, dict) or not isinstance(entry.get('path'), str) \
                or not RECEIPT_FILE.match(entry['path']) or not SHA256.match(str(entry.get('sha256'))):
            raise SyncError('receipt entry %r is not a file this tool installs; refusing to roll back'
                            % (entry.get('path') if isinstance(entry, dict) else entry))
    for rel in data['dirs']:
        if not isinstance(rel, str) or not RECEIPT_DIR.match(rel):
            raise SyncError('receipt folder %r is not one this tool creates; refusing to roll back' % (rel,))
        if rel.startswith('@') and rel.split('/')[0] not in managed:
            raise SyncError('receipt folder %r is not a mod folder in the manifest; refusing to roll back' % (rel,))
    created = {rel for rel in data['dirs'] if rel.startswith('@') and '/' not in rel}
    by_path = {e['path'].casefold(): e for e in data['files']}
    orphans = []
    for entry in data['files']:
        path = entry['path']
        if path.startswith('@'):
            if path.split('/')[0].casefold() not in {d.casefold() for d in created}:
                raise SyncError('receipt entry %s is in a folder install did not create; refusing to roll back' % path)
        else:
            # A server key is ours only if a created mod folder holds the same key we copied from it.
            name = path.split('/')[-1]
            if not any(by_path.get((top + '/keys/' + name).casefold(), {}).get('sha256') == entry['sha256'] for top in created):
                orphans.append(entry)
    if orphans:
        live = live_key_files(root, set(), extra_key_dirs)
        dropped = []
        for entry in orphans:
            name = entry['path'].split('/')[-1].casefold()
            provider = next((label for label, key_name, key_sha in live if key_name == name
                             or key_sha == entry['sha256']), None)
            if provider is None:
                raise SyncError('receipt key %s has no matching copy in a folder install created; '
                                'refusing to roll back' % entry['path'])
            dropped.append(entry)
            if repaired is not None:
                repaired.append(entry['path'])
            text = ('WARN: receipt key %s has no copy in a folder this install created (an earlier release kept it '
                    'when a retired mod was removed); %s provides it, so the key stays on the server and is no longer '
                    'recorded as installed by this tool' % (entry['path'], provider))
            if warn is not None:
                warn(text)
            else:
                print(text, file=sys.stderr)
        gone = {e['path'] for e in dropped}
        data['files'] = [e for e in data['files'] if e['path'] not in gone]
    return data


def live_key_files(root, retired_keys, extra_dirs=()):
    """{casefolded name: (label, sha)} for every key file an active mod folder or the bundle provides now: each live
    @*/keys folder (not only the ones the receipt names) and the extra directories (the bundle's keys folder)."""
    found = []
    if root is not None and Path(root).is_dir():
        for folder in sorted(Path(root).iterdir()):
            if not folder.name.startswith('@') or folder.name.casefold() in retired_keys or not folder.is_dir():
                continue
            for sub in folder.iterdir():
                if sub.name.casefold() == 'keys' and sub.is_dir():
                    found += [(folder.name + '/keys/' + key.name, key) for key in sorted(sub.iterdir())]
    for extra in extra_dirs:
        if Path(extra).is_dir():
            found += [('the bundle keys/' + key.name, key) for key in sorted(Path(extra).iterdir())]
    return [(label, key.name.casefold(), sha256_of(key)) for label, key in found if key.is_file()]


def _split(receipt, manifest, root=None, extra_key_dirs=()):
    """(file rows to delete, folder names, [(path, reason)] for root keys that are kept, paths to disown).

    A root key that is kept stays on the server. Its receipt row stays only when a folder the receipt keeps carries
    the exact-name copy (load_receipt validates exactly that); otherwise the row is disowned: retire_items drops it, so
    the receipt never names a key nothing in it backs and rollback never deletes a key another mod needs."""
    if not receipt:
        return [], [], [], set()
    retired = {m['folder'].casefold() for m in manifest['retired']}

    def key_copies(keep):
        return {(e['path'].split('/')[-1].casefold(), e['sha256']) for e in receipt['files']
                if e['path'].startswith('@') and '/keys/' in e['path'].casefold() and keep(e['path'].split('/')[0].casefold())}

    retired_keys = key_copies(lambda top: top in retired)
    active_keys = key_copies(lambda top: top not in retired)
    active_exact = {(e['path'].split('/')[-1], e['sha256']) for e in receipt['files']
                    if e['path'].startswith('@') and e['path'].count('/') == 2 and '/keys/' in e['path'].casefold()
                    and e['path'].split('/')[0].casefold() not in retired}
    live = None
    rows, kept, disown = [], [], set()
    for entry in receipt['files']:
        path = entry['path']
        if path.startswith('@'):
            if path.split('/')[0].casefold() in retired:
                rows.append(entry)
            continue
        key = (path.split('/')[-1].casefold(), entry['sha256'])
        if key not in retired_keys:
            continue
        if key in active_keys:
            kept.append((path, 'an active mod folder in the receipt carries the same key'))
            if (path.split('/')[-1], entry['sha256']) not in active_exact:
                disown.add(path)
            continue
        if live is None:
            live = live_key_files(root, retired, extra_key_dirs)
        shared = next((label for label, name, sha in live if name == key[0] or sha == entry['sha256']), None)
        if shared is not None:
            kept.append((path, 'also provided by %s' % shared))
            disown.add(path)
        else:
            rows.append(entry)
    dirs = sorted(rel for rel in receipt['dirs'] if rel.split('/')[0].casefold() in retired)
    return rows, dirs, kept, disown


def split_retired_rows(receipt, manifest, root=None, extra_key_dirs=()):
    """(file rows to delete, folder names, [(path, reason)] for root keys that are kept).

    A server key counts when a retired folder holds the same key bytes and no active folder does. An author key
    several mods share is never deleted: before a root keys/*.bikey goes, every live @*/keys folder (not only the
    receipt rows) and the bundle's keys folder are searched for the same name (case-insensitive) or the same bytes.
    """
    rows, dirs, kept, _disown = _split(receipt, manifest, root, extra_key_dirs)
    return rows, dirs, kept


def retired_receipt_rows(receipt, manifest, root=None, extra_key_dirs=()):
    """Receipt files and folders that belong to retired manifest items: (file rows, folder names). See
    split_retired_rows for the shared-key rules."""
    rows, dirs, _kept = split_retired_rows(receipt, manifest, root, extra_key_dirs)
    return rows, dirs


def retire_items(root, receipt, manifest, before_write=None, extra_key_dirs=()):
    """Remove what an earlier install recorded for retired items, keys included, then rewrite the receipt.

    Only files whose bytes still match the receipt are deleted; a changed file is left and reported, and
    its folder stays. Both are dropped from the receipt either way, so a second run finds nothing to do.
    Returns (removed paths, left paths).
    """
    rows, dirs, _kept, disown = _split(receipt, manifest, root, extra_key_dirs)
    if not rows and not dirs and not disown:
        return [], []
    for entry in rows:
        check_no_symlink_below(root, entry['path'])
    for rel in dirs:
        check_no_symlink_below(root, rel)
    removed, left = [], []
    for entry in rows:
        target = root / entry['path']
        if not target.exists() and not target.is_symlink():
            continue
        if not target.is_file() or sha256_of(target) != entry['sha256']:
            left.append(entry['path'])
            continue
        if before_write is not None:
            before_write(entry['path'], None)
        target.unlink()
        fsync_parent(target)
        removed.append(entry['path'])
    for rel in sorted(dirs, key=lambda r: r.count('/'), reverse=True):
        folder = root / rel
        if folder.is_dir() and not folder.is_symlink() and not any(folder.iterdir()):
            folder.rmdir()
    gone = {e['path'] for e in rows} | disown
    data = receipt_data({e['path']: e for e in receipt['files'] if e['path'] not in gone},
                        set(receipt['dirs']) - set(dirs))
    if before_write is not None:
        before_write(RECEIPT_NAME, hashlib.sha256(json_bytes(data)).hexdigest())
    write_json_atomic(root / RECEIPT_NAME, data)
    return removed, left


def receipt_data(files, dirs):
    return {'schema': SCHEMA, 'files': sorted(files.values(), key=lambda e: e['path']), 'dirs': sorted(dirs)}


def persist_repaired_receipt(root, receipt, before_write=None):
    """Write a receipt load_receipt repaired. before_write(RECEIPT_NAME, sha256) runs first, like every other
    receipt write, so a caller that journals its writes records this one."""
    data = receipt_data({e['path']: e for e in receipt['files']}, set(receipt['dirs']))
    if before_write is not None:
        before_write(RECEIPT_NAME, hashlib.sha256(json_bytes(data)).hexdigest())
    write_json_atomic(root / RECEIPT_NAME, data)


# ---------------------------------------------------------------- commands
def resolve(args):
    manifest = load_manifest(args.manifest)
    groups = parse_groups(args.groups)
    items = select(manifest, groups, args.hollowcountry_id)
    dirs = content_dirs(args.workshop_content, args.steamcmd, getattr(args, 'install_dir', None))
    return groups, items, dirs


def managed_folders(args):
    # A filtered --manifest (the friend installer passes only the pending mods) must not orphan folders an
    # earlier install created from the shipped manifest; those stay ours for receipt validation and rollback.
    # Retired items count too: a receipt an older release wrote can still name their folders.
    folders = set()
    for path in ([args.manifest, None] if args.manifest else [None]):
        manifest = load_manifest(path)
        folders |= {m['folder'] for m in manifest['mods'] + manifest['retired']}
    return folders


def classify(item, root):
    if item['id']:
        return 'workshop'
    return 'unpublished' if item['publish'] else 'local'


def cmd_plan(args, say):
    groups, items, dirs = resolve(args)
    root = Path(args.server_root)
    say('Server root: %s' % root)
    say('Groups: %s' % ', '.join(groups))
    say('Workshop content searched: %s' % (', '.join(str(d) for d in dirs) or '(none given)'))
    if 'pve_patrols' in groups and 'base' not in groups:
        say('  warning: pve_patrols is selected without base; the patrol mod needs @HollowCountry')
    say('Items in load order:')
    fetch_needed = 0
    for item in items:
        label = '%s (%s)' % (item['folder'], item['name'])
        kind = classify(item, root)
        if kind == 'workshop':
            state, path, detail = find_item(item['id'], dirs)
            if state == 'present':
                say('  %s %s present at %s' % (label, item['id'], path))
                files, skipped = item_files(item, path)
                say('    copy %s -> %s' % (path, root / item['folder']))
                for rel, _ in files:
                    if rel.lower().endswith('.bikey'):
                        say('    key %s -> %s' % (Path(rel).name, root / 'keys' / Path(rel).name))
                if skipped:
                    say('    not copied: %s' % ', '.join(skipped))
            elif state == 'incomplete':
                say('  %s %s incomplete at %s (%s)' % (label, item['id'], path, detail))
                fetch_needed += 1
            else:
                say('  %s %s missing; run fetch' % (label, item['id']))
                fetch_needed += 1
        elif kind == 'unpublished':
            here = (root / item['folder']).is_dir()
            say('  %s has no Workshop id yet (unpublished); %s' % (
                label, 'already in the server root' if here else
                'copy the signed folder into the server root, or pass --hollowcountry-id once published'))
        else:
            here = (root / item['folder']).is_dir()
            say('  %s is a local build, never published; %s' % (
                label, 'already in the server root' if here else 'build it and copy it into the server root'))
    if fetch_needed:
        say('%d item(s) still to fetch.' % fetch_needed)
    say('Launch lines (load order):')
    for line in launch_lines(items):
        say(line)
    return 0


def check_user(user):
    if not isinstance(user, str) or not STEAM_USER.match(user):
        raise SyncError('--steam-user %r is not a plausible Steam login name' % (user,))
    return user


def cmd_fetch(args, say):
    groups, items, dirs = resolve(args)
    wanted = [i for i in items if i['id']]
    for item in items:
        if not item['id']:
            say('skipping %s: no Workshop id (%s)' % (item['folder'], 'never published' if not item['publish']
                                                       else 'own mod, not published yet'))
    if not wanted:
        say('nothing to fetch')
        return 0
    user = check_user(args.steam_user)
    if not dirs:
        raise SyncError('no download location known: give --install-dir, --steamcmd <path> or --workshop-content')
    command = [args.steamcmd or 'steamcmd']
    if args.install_dir:
        command += ['+force_install_dir', str(args.install_dir)]
    command += ['+login', user]
    for item in wanted:
        command += ['+workshop_download_item', APP_ID, item['id'], 'validate']
    command.append('+quit')
    say('Running: %s' % ' '.join(command))
    say('steamcmd will ask for your password and Steam Guard code itself; type them there.')
    try:
        done = subprocess.run(command, check=False)
    except FileNotFoundError:
        raise SyncError('steamcmd not found (%s); install it or pass --steamcmd <path>' % command[0])
    if done.returncode != 0:
        raise SyncError('steamcmd exited with status %s' % done.returncode)
    problems = []
    for item in wanted:
        state, path, detail = find_item(item['id'], dirs)
        if state == 'present':
            say('  %s %s verified at %s' % (item['folder'], item['id'], path))
        elif state == 'incomplete':
            problems.append('%s %s incomplete at %s: %s' % (item['folder'], item['id'], path, detail))
        else:
            problems.append('%s %s not found after the download (searched: %s)' % (
                item['folder'], item['id'], ', '.join(str(d) for d in dirs)))
    if problems:
        raise SyncError('; '.join(problems))
    say('verified %d item(s)' % len(wanted))
    return 0


def plan_install(items, dirs, root, owned=(), compare=True):
    """Resolve every file to write before writing anything. Returns (work, skipped, manual)."""
    missing, work, skipped, manual = [], [], {}, []
    for item in items:
        if not item['id']:
            manual.append(item)
            continue
        state, path, detail = find_item(item['id'], dirs)
        if state != 'present':
            missing.append('%s %s (%s)' % (item['folder'], item['id'], state + (': ' + detail if detail else '')))
            continue
        files, skip = item_files(item, path)
        skipped[item['folder']] = skip
        for rel, source in files:
            work.append((item, '%s/%s' % (item['folder'], rel), source))
            if rel.lower().endswith('.bikey'):
                work.append((item, 'keys/%s' % Path(rel).name, source))
    if missing:
        raise SyncError('cannot install, fetch these first: ' + '; '.join(missing))
    targets = {}
    for item, rel, source in work:
        digest = sha256_of(source)
        if rel in targets and targets[rel][1] != digest:
            raise SyncError('%s and %s both supply a different %s' % (targets[rel][0]['folder'], item['folder'], rel))
        targets.setdefault(rel, (item, digest, source))
    if not compare:
        return targets, skipped, manual
    conflicts = []
    for rel, (item, digest, source) in sorted(targets.items()):
        check_no_symlink_below(root, rel)
        target = root / rel
        if target.exists() or target.is_symlink():
            if not target.is_file():
                conflicts.append('%s exists and is not a regular file' % rel)
            elif not matches_file(target, digest, source.stat().st_size):
                conflicts.append('%s exists and differs' % rel)
        top = rel.split('/')[0]
        folder = root / top
        if folder.exists() and not folder.is_dir():
            conflicts.append('%s exists and is not a directory' % folder.name)
        elif top.startswith('@') and folder.is_dir() and top not in owned:
            conflicts.append('%s exists but was not created by an earlier install' % top)
    if conflicts:
        raise SyncError('refusing to overwrite: ' + '; '.join(conflicts)
                        + '. Run rollback first if these came from an earlier install, or move them away.')
    return targets, skipped, manual


def matches_file(path, digest, size=None):
    """Avoid hashing gigabytes when size already proves a difference."""
    return (path.is_file() and not path.is_symlink()
            and (size is None or path.stat().st_size == size) and sha256_of(path) == digest)


def file_state(path, candidate_sizes):
    """Hash only if some candidate's size permits equality; otherwise retain a stat precondition."""
    if not path.exists():
        return None, None, None
    if not path.is_file() or path.is_symlink():
        raise SyncError('not a regular file: %s' % path)
    info = path.stat()
    snapshot = (info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_ino)
    digest = sha256_of(path) if info.st_size in candidate_sizes or None in candidate_sizes else None
    return digest, info.st_size, digest if digest is not None else snapshot


def plan_refresh(item, dirs, root, receipt, extra_key_dirs=(), say=lambda _text: None, resolved=None):
    """Classify one receipt-owned item, including root keys, using casefolded paths.

    Workshop equality wins (and adopts missing rows); otherwise receipt equality permits an update.
    A file differing from both is edited; a differing file without a row is unrecorded.
    The caller must reject the whole item before applying any blocked file.
    """
    folder = item['folder']
    plan = dict(item=item, state='current', source=None, warnings=[], writes={}, removes={},
                rows={}, edited=[], unrecorded=[], extras=[], expected={}, drop=set(), extra_key_dirs=extra_key_dirs)
    if receipt is None or folder.casefold() not in {d.casefold() for d in receipt['dirs']}:
        raise SyncError('cannot refresh unowned folder %s' % folder)
    if resolved is None:
        say('Checking Workshop dependency %s ...' % folder)
    state, source, detail = resolved or find_item(item['id'], dirs)
    plan['source'] = source
    if detail:
        plan['warnings'].append(detail)
    if state != 'present':
        plan['state'] = 'content-updating' if state == 'content-updating' else 'content-missing'
        return plan
    if item_timestamp(source) < item_timestamp(case_path(root, folder)):
        plan['state'] = 'downgrade'
        plan['warnings'].append('refusing downgrade: source timestamp %s < server timestamp %s' % (
            item_timestamp(source), item_timestamp(case_path(root, folder))))
        return plan
    # Use plan_install's target construction and digest rules, without its new-install conflict rule.
    targets, _skip, _manual = plan_install([item], [source.parent], root, compare=False)
    targets = {(case_path(root, str(Path(rel).parent)) / Path(rel).name).relative_to(root).as_posix(): value
               for rel, value in targets.items()}
    old = {e['path'].casefold(): e for e in receipt['files']}
    desired = {rel.casefold(): rel for rel in targets}
    if len(desired) != len(targets):
        raise SyncError('Workshop item has duplicate casefolded targets: %s' % folder)
    # Reuse retirement's shared-root-key protection, excluding only the item being refreshed.
    retired = {'retired': [item]}
    obsolete, _dirs, kept, disown = _split(receipt, retired, root, extra_key_dirs)
    candidates = [e for e in obsolete if e['path'].casefold() not in desired]
    plan['drop'] |= {e['path'].casefold() for e in receipt['files']
                     if e['path'].casefold().startswith(folder.casefold() + '/')}
    plan['drop'] |= {p.casefold() for p, _reason in kept if p.casefold() not in desired and
                     (p in disown or not any(e['path'].startswith('@') and
                         e['path'].split('/')[0].casefold() != folder.casefold() and
                         e['path'].endswith('/keys/' + p.split('/')[-1]) and
                         e['sha256'] == old[p.casefold()]['sha256'] for e in receipt['files']))}
    for entry in candidates:
        rel = entry['path']
        target = case_path(root, rel)
        check_no_symlink_below(root, target.relative_to(root).as_posix())
        plan['drop'].add(rel.casefold())
        if target.exists():
            if not target.is_file():
                raise SyncError('not a regular file: %s' % target)
            actual = target.relative_to(root).as_posix()
            digest, _size, snapshot = file_state(target, [entry.get('size')])
            plan['expected'][actual] = snapshot
            if digest != entry['sha256']:
                plan['edited'].append(actual)
            plan['removes'][actual] = entry
    for rel, (mod, digest, src) in targets.items():
        target = case_path(root, rel)
        actual = target.relative_to(root).as_posix()
        # Several items can share one root key with differently cased names. Keep its live
        # spelling so those items do not take turns renaming the same Windows path.
        if rel.casefold().startswith('keys/') and target.exists():
            rel = actual
        check_no_symlink_below(root, actual)
        entry = old.get(rel.casefold())
        size = src.stat().st_size
        sizes = [size] + ([entry.get('size')] if entry else [])
        current, current_size, snapshot = file_state(target, sizes)
        present = current_size is not None
        same = present and current_size == size and current == digest
        plan['expected'][actual] = snapshot
        if present and not same:
            if entry is None:
                plan['unrecorded'].append(actual)
            elif current != entry['sha256']:
                plan['edited'].append(actual)
        if not same or (present and actual != rel):
            if present and actual != rel:
                plan['removes'][actual] = entry
            plan['writes'][rel] = (mod, digest, src)
        row_item = (entry.get('item', mod['id']) if rel.casefold().startswith('keys/') and entry
                    and entry['sha256'] == digest else mod['id'])
        plan['rows'][rel] = dict(path=rel, item=row_item, sha256=digest, size=size)
    folder_path = case_path(root, folder)
    if folder_path.is_dir():
        for path in sorted(folder_path.rglob('*')):
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                raise SyncError('symlink in dependency: %s' % rel)
            if path.is_file() and rel.casefold() not in old and rel.casefold() not in desired:
                plan['extras'].append(rel)
                plan['expected'][rel] = file_state(path, [])[2]
    plan['receipt_changed'] = any(old.get(rel.casefold()) != row for rel, row in plan['rows'].items()) or any(
        key not in desired for key in plan['drop'])
    plan['state'] = ('unrecorded' if plan['unrecorded'] else 'edited' if plan['edited'] else
                     'stale' if plan['writes'] or plan['removes'] else 'current')
    return plan


def apply_refresh(root, receipt, plans, before_write, repair=False):
    """Apply preflighted items; caller supplies the durable backup/journal and rolls back on failure.

    Deletions precede writes (including case renames). Folder and root key rows commit once together.
    """
    writes, removes, expected = {}, {}, {}
    for plan in plans:
        if plan['state'] not in ('current', 'stale', 'edited', 'unrecorded'):
            raise SyncError('%s: %s' % (plan['item']['folder'], plan['state']))
        # Root keys without ownership are never repairable by overwriting.
        if any(p.casefold().startswith('keys/') for p in plan['unrecorded']):
            raise SyncError('unowned root key blocks %s' % plan['item']['folder'])
        if (plan['edited'] or plan['unrecorded']) and not repair:
            raise SyncError('%s: %s; run --apply --repair' % (plan['item']['folder'], plan['state']))
        for rel, value in plan['writes'].items():
            collision = next((v for p, v in writes.items() if p.casefold() == rel.casefold()), None)
            if collision and collision[1] != value[1]:
                raise SyncError('items supply different root key: %s' % rel)
            if collision is None:
                writes[rel] = value
        removes.update(plan['removes'])
        expected.update(plan['expected'])
        if repair:
            removes.update({rel: None for rel in plan['extras']})
    # Check every live precondition before the first mutation, even under --repair.
    for rel, snapshot in expected.items():
        target = root / rel
        check_no_symlink_below(root, rel)
        _digest, _size, current = file_state(target, [] if isinstance(snapshot, tuple) else [None])
        if current != snapshot:
            raise SyncError('dependency changed after planning: %s' % rel)
    backup_bytes = sum((root / rel).stat().st_size for rel in set(removes) | set(writes) if (root / rel).is_file())
    backup_bytes += (root / RECEIPT_NAME).stat().st_size if (root / RECEIPT_NAME).is_file() else 0
    files = {e['path']: e for e in receipt['files']}
    dirs = set(receipt['dirs'])
    for plan in plans:
        files = {p: row for p, row in files.items() if p.casefold() not in plan['drop']}
        for rel, row in plan['rows'].items():
            if rel.casefold().startswith('keys/'):
                live_path = case_path(root, rel)
                canonical = (live_path.relative_to(root).as_posix() if live_path.is_file() else
                             next((p for p in files if p.casefold() == rel.casefold()), rel))
                rel, row = canonical, dict(row, path=canonical)
            files = {p: e for p, e in files.items() if p.casefold() != rel.casefold()}
            files[rel] = row
    # A retained shared key may no longer be backed by an owned folder. Keep bytes but disown the row.
    backed = {(p.split('/')[-1].casefold(), row['sha256']) for p, row in files.items() if p.startswith('@') and '/keys/' in p.casefold()}
    files = {p: row for p, row in files.items() if p.startswith('@') or (p.split('/')[-1].casefold(), row['sha256']) in backed}
    data = receipt_data(files, dirs)
    largest = max([src.stat().st_size for _item, _digest, src in writes.values()] + [len(json_bytes(data))])
    if shutil.disk_usage(root).free < backup_bytes + largest:
        raise SyncError('not enough free space for dependency backups plus the largest new file')
    updating = {p['item']['folder'].casefold() for p in plans}
    live = live_key_files(root, updating)
    for plan in plans:
        live += live_key_files(None, set(), plan.get('extra_key_dirs', ()))
    for rel, (_item, digest, _src) in writes.items():
        if rel.casefold().startswith('keys/'):
            provider = next((label for label, name, sha in live if name == Path(rel).name.casefold() and sha != digest), None)
            if provider:
                raise SyncError('root key %s conflicts with active provider %s; folder update blocked' % (rel, provider))
    if not writes and not removes and data == receipt:
        return False
    for rel in sorted(removes):
        before_write(rel, None)
        (root / rel).unlink()
        fsync_parent(root / rel)
    for rel, (_item, digest, source) in sorted(writes.items()):
        before_write(rel, digest)
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        parent = Path(rel).parent.as_posix()
        dirs.add(next((d for d in dirs if d.casefold() == parent.casefold()), parent))
        copy_atomic(source, root / rel, expected=digest)
        row_path = next(p for p in files if p.casefold() == rel.casefold())
        files[row_path]['size'] = (root / rel).stat().st_size
    data = receipt_data(files, dirs)
    before_write(RECEIPT_NAME, hashlib.sha256(json_bytes(data)).hexdigest())
    write_json_atomic(root / RECEIPT_NAME, data)
    return True


def cmd_install(args, say, before_write=None):
    require_stopped(args)
    root = check_root(args.server_root)
    groups, items, dirs = resolve(args)
    repaired = []
    receipt = load_receipt(root, managed_folders(args), bundle_key_dirs(args), warn=say, repaired=repaired)
    targets, skipped, manual = plan_install(items, dirs, root, set(receipt['dirs']) if receipt else set())
    files = {e['path']: e for e in receipt['files']} if receipt else {}
    made_dirs = set(receipt['dirs']) if receipt else set()
    created = set()
    changed = False
    try:
        for rel, (item, digest, source) in sorted(targets.items()):
            target = root / rel
            if target.is_file():
                continue
            if before_write is not None:
                before_write(rel, digest)
            parent = ''
            for part in rel.split('/')[:-1]:
                parent = parent + '/' + part if parent else part
                if not (root / parent).exists():
                    (root / parent).mkdir()
                    made_dirs.add(parent)
                    changed = True
            copy_atomic(source, target, expected=digest)
            files[rel] = {'path': rel, 'sha256': digest, 'size': target.stat().st_size, 'item': item['id']}
            created.add(rel)
            changed = True
    finally:
        if changed or receipt is None or repaired:
            data = receipt_data(files, made_dirs)
            if before_write is not None:
                before_write(RECEIPT_NAME, hashlib.sha256(json_bytes(data)).hexdigest())
            write_json_atomic(root / RECEIPT_NAME, data)
    for item in items:
        if item['id']:
            fresh = [r for r in created if r.startswith(item['folder'] + '/')]
            say('  %s %s: %s' % (item['folder'], item['id'],
                                'installed %d file(s)' % len(fresh) if fresh else 'already installed'))
            if skipped.get(item['folder']):
                say('    skipped (not copied): %s' % ', '.join(skipped[item['folder']]))
    for item in manual:
        here = (root / item['folder']).is_dir()
        if item['publish']:
            say('  %s: no Workshop id, %s' % (item['folder'], 'found in the server root' if here else
                                              'warning: not in the server root; copy the signed folder there yourself'))
        else:
            say('  %s: local build, never published; %s' % (item['folder'], 'found in the server root' if here else
                                                          'warning: not in the server root; build it and copy it there'))
    if not changed:
        say('already installed: nothing to change')
    say('Add these to the server start command (load order):')
    for line in launch_lines(items):
        say(line)
    return 0


def cmd_rollback(args, say):
    require_stopped(args)
    root = check_root(args.server_root)
    receipt = load_receipt(root, managed_folders(args), bundle_key_dirs(args), warn=say)
    if receipt is None:
        raise SyncError('no receipt (%s) in %s; nothing this tool installed can be rolled back' % (RECEIPT_NAME, root))
    for entry in receipt['files']:
        check_no_symlink_below(root, entry['path'])
    for rel in receipt['dirs']:
        check_no_symlink_below(root, rel)
    removed, left = 0, []
    for entry in receipt['files']:
        target = root / entry['path']
        if not target.exists() and not target.is_symlink():
            continue
        if not target.is_file() or sha256_of(target) != entry['sha256']:
            left.append(entry['path'])
            continue
        target.unlink()
        removed += 1
    for rel in sorted(receipt['dirs'], key=lambda r: r.count('/'), reverse=True):
        folder = root / rel
        if folder.is_dir() and not folder.is_symlink() and not any(folder.iterdir()):
            folder.rmdir()
    (root / RECEIPT_NAME).unlink()
    say('removed %d file(s)' % removed)
    if left:
        say('left in place (modified or not a regular file; remove by hand if wanted):')
        for rel in left:
            say('  %s' % rel)
    return 0


# ---------------------------------------------------------------- command line
def _positive_id(value):
    if not ID.match(value):
        raise argparse.ArgumentTypeError('%r is not a Workshop id' % value)
    return value


CREDENTIAL_WORDS = ('pass', 'token', 'secret', 'pwd', 'credential', 'guard')


class QuietParser(argparse.ArgumentParser):
    """Never echoes argument values: credential-like options and unknown arguments are refused unseen."""

    def parse_args(self, args=None, namespace=None):
        for token in (sys.argv[1:] if args is None else args):
            name = token.split('=', 1)[0].lower() if token.startswith('-') else ''
            if name and (name == '-p' or (not name.startswith('--') and name.startswith('-p'))
                         or any(word in name for word in CREDENTIAL_WORDS)):
                self.error('credential options are not supported; the password and Steam Guard code are typed '
                           'into steamcmd itself (the offending argument is not shown)')
        return super().parse_args(args, namespace)

    def error(self, message):
        if message.startswith('unrecognized arguments'):
            message = 'unrecognized arguments (values are not shown)'
        super().error(message)


def build_parser():
    parser = QuietParser(description=__doc__.split('\n')[0], allow_abbrev=False)
    sub = parser.add_subparsers(dest='command', required=True)

    def common(p, groups=True, root_required=True):
        p.add_argument('--server-root', required=root_required, help='the DayZ server folder')
        if groups:
            p.add_argument('--groups', required=True, help='comma list of: ' + ', '.join(GROUPS))
            p.add_argument('--workshop-content', action='append', default=[],
                           help='a steamapps/workshop/content/221100 folder (repeatable)')
            p.add_argument('--steamcmd', help='path to steamcmd (its folder is searched for downloads)')
            p.add_argument('--manifest', help='alternative workshop_mods.json')
            p.add_argument('--hollowcountry-id', type=_positive_id,
                           help='Workshop id of @HollowCountry, used only if the manifest has none')

    plan = sub.add_parser('plan', help='show what is needed, present and will be copied', allow_abbrev=False)
    common(plan)
    plan.add_argument('--install-dir', help='steamcmd force_install_dir whose content folder is searched')
    fetch = sub.add_parser('fetch', help='download the Workshop items with steamcmd', allow_abbrev=False)
    common(fetch, root_required=False)
    fetch.add_argument('--steam-user', required=True, help='your Steam login name (the password is typed into steamcmd)')
    fetch.add_argument('--install-dir', help='steamcmd force_install_dir for the download')
    install = sub.add_parser('install', help='copy items and keys into the server root', allow_abbrev=False)
    common(install)
    install.add_argument('--assume-stopped', action='store_true', help='skip the running-server check')
    install.add_argument('--bundle-keys', help='the bundle keys folder (default: keys/ next to tools/ in the bundle)')
    install.set_defaults(install_dir=None)
    rollback = sub.add_parser('rollback', help='remove exactly what install added', allow_abbrev=False)
    common(rollback, groups=False)
    rollback.add_argument('--manifest', help='alternative workshop_mods.json')
    rollback.add_argument('--bundle-keys', help='the bundle keys folder (default: keys/ next to tools/ in the bundle)')
    rollback.add_argument('--assume-stopped', action='store_true', help='skip the running-server check')
    return parser


def main(argv=None, out=None, before_write=None):
    out = out or sys.stdout
    args = build_parser().parse_args(argv)

    def say(text=''):
        print(text, file=out)

    commands = {'plan': cmd_plan, 'fetch': cmd_fetch, 'install': cmd_install, 'rollback': cmd_rollback}
    try:
        if args.command == 'install':
            return cmd_install(args, say, before_write=before_write)
        return commands[args.command](args, say)
    except SyncError as exc:
        print('error: %s' % exc, file=sys.stderr)
        return 1
    except OSError as exc:
        print('error: %s' % exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
