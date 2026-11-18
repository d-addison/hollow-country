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
Dabs Framework, Expansion Core, Animations, AI, the optional weapons packs, @HollowCountry, then
@HollowCountryExpansionAI). A ``-serverMod=`` line is omitted when no server-only items remain.
Offline checks establish nothing about DayZ behaviour: the join-time auto-subscribe, signature checks and the
mod set at runtime stay pending the owner's acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
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


def find_item(item_id, dirs):
    """(state, path, detail) with state present, incomplete or missing."""
    incomplete = None
    for directory in dirs:
        path = directory / item_id
        if path.is_dir() and not path.is_symlink():
            state, detail = inspect_item(path)
            if state == 'present':
                return 'present', path, ''
            incomplete = incomplete or (path, detail)
    if incomplete:
        return 'incomplete', incomplete[0], incomplete[1]
    return 'missing', None, ''


# ---------------------------------------------------------------- server process detection
def server_running():
    """True if a DayZ server process is running, False if not, None if the process list cannot be read."""
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
            results.append(SERVER_EXE.lower() in (done.stdout or '').lower() if done.returncode == 0 else None)
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
    state = server_running()
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


def copy_atomic(source, target):
    fd, temp = tempfile.mkstemp(dir=str(target.parent), prefix='.sync-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as handle, open(source, 'rb') as src:
            shutil.copyfileobj(src, handle, 1024 * 1024)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o644)
        os.replace(temp, target)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def write_json_atomic(path, data):
    fd, temp = tempfile.mkstemp(dir=str(path.parent), prefix='.receipt-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(json.dumps(data, indent=2, sort_keys=True) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o644)
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


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
def load_receipt(root, managed):
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
    by_path = {e['path']: e for e in data['files']}
    for entry in data['files']:
        path = entry['path']
        if path.startswith('@'):
            if path.split('/')[0] not in created:
                raise SyncError('receipt entry %s is in a folder install did not create; refusing to roll back' % path)
        else:
            # A server key is ours only if a created mod folder holds the same key we copied from it.
            name = path.split('/')[-1]
            if not any(by_path.get(top + '/keys/' + name, {}).get('sha256') == entry['sha256'] for top in created):
                raise SyncError('receipt key %s has no matching copy in a folder install created; '
                                'refusing to roll back' % path)
    return data


def receipt_data(files, dirs):
    return {'schema': SCHEMA, 'files': sorted(files.values(), key=lambda e: e['path']), 'dirs': sorted(dirs)}


# ---------------------------------------------------------------- commands
def resolve(args):
    manifest = load_manifest(args.manifest)
    groups = parse_groups(args.groups)
    items = select(manifest, groups, args.hollowcountry_id)
    dirs = content_dirs(args.workshop_content, args.steamcmd, getattr(args, 'install_dir', None))
    return groups, items, dirs


def managed_folders(args):
    return {m['folder'] for m in load_manifest(args.manifest)['mods']}


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


def plan_install(items, dirs, root, owned=()):
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
    conflicts = []
    for rel, (item, digest, source) in sorted(targets.items()):
        check_no_symlink_below(root, rel)
        target = root / rel
        if target.exists() or target.is_symlink():
            if not target.is_file():
                conflicts.append('%s exists and is not a regular file' % rel)
            elif sha256_of(target) != digest:
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


def cmd_install(args, say):
    require_stopped(args)
    root = check_root(args.server_root)
    groups, items, dirs = resolve(args)
    receipt = load_receipt(root, managed_folders(args))
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
            parent = ''
            for part in rel.split('/')[:-1]:
                parent = parent + '/' + part if parent else part
                if not (root / parent).exists():
                    (root / parent).mkdir()
                    made_dirs.add(parent)
                    changed = True
            copy_atomic(source, target)
            files[rel] = {'path': rel, 'sha256': digest, 'size': target.stat().st_size, 'item': item['id']}
            created.add(rel)
            changed = True
    finally:
        if changed or receipt is None:
            write_json_atomic(root / RECEIPT_NAME, receipt_data(files, made_dirs))
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
    receipt = load_receipt(root, managed_folders(args))
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
    install.set_defaults(install_dir=None)
    rollback = sub.add_parser('rollback', help='remove exactly what install added', allow_abbrev=False)
    common(rollback, groups=False)
    rollback.add_argument('--manifest', help='alternative workshop_mods.json')
    rollback.add_argument('--assume-stopped', action='store_true', help='skip the running-server check')
    return parser


def main(argv=None, out=None):
    out = out or sys.stdout
    args = build_parser().parse_args(argv)

    def say(text=''):
        print(text, file=out)

    commands = {'plan': cmd_plan, 'fetch': cmd_fetch, 'install': cmd_install, 'rollback': cmd_rollback}
    try:
        return commands[args.command](args, say)
    except SyncError as exc:
        print('error: %s' % exc, file=sys.stderr)
        return 1
    except OSError as exc:
        print('error: %s' % exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
