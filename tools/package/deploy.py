"""Private development ZIP installation with explicit crash recovery.

Only HollowCountryPackage and .hollow-country-deploy are managed. Server profiles
and missions are never edited. Stop the server and all other destination writers.
Run this trusted script alongside the trusted, existing pbo.py (Python >=3.10).
"""
import argparse
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import zipfile
import uuid

try:
    from . import pbo
except ImportError:  # Direct portable invocation; never import from the input ZIP.
    import pbo


ACTIVE = 'HollowCountryPackage'
CONTROL = '.hollow-country-deploy'
BOOTSTRAP = CONTROL + '.init'
OWNER = b'Hollow Country private deployment metadata v1\n'
MAX_METADATA = 2 * 1024 * 1024
MAX_TRANSACTIONS = 128
MAX_ARCHIVE = 2 * pbo.MAX_BYTES
ID = re.compile(r'[0-9a-f]{32}')
SHA = re.compile(r'[0-9a-f]{64}')


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _check_stat(info, directory=False):
    if getattr(info, 'st_file_attributes', 0) & 0x400:
        raise ValueError('Windows reparse point forbidden')
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(info.st_mode) or (not directory and info.st_nlink != 1):
        raise ValueError('symlink, hardlink or special file forbidden')


def _safe(path, directory=None, missing=False):
    """Check lexical components before resolving: resolution must not hide links."""
    path = Path(path)
    if '..' in path.parts or (os.name != 'nt' and '\\' in str(path)):
        raise ValueError('traversal/non-native path forbidden')
    path = path.absolute()
    if path.drive.startswith('\\\\') or str(path).startswith('//'):
        raise ValueError('network/UNC destination unsupported')
    for part in path.parts[1:]:
        # Existing Windows host components may use 8.3 names (RUNNER~1).
        # Keep archive member validation strict; only host paths admit tilde.
        pbo.safe_name(part.replace('~', '_'))
    for parent in reversed(path.parents):
        _check_stat(parent.lstat(), directory=True)
    try:
        info = path.lstat()
    except FileNotFoundError:
        if missing:
            return path
        raise ValueError(f'path does not exist: {path}') from None
    _check_stat(info, directory=stat.S_ISDIR(info.st_mode) if directory is None else directory)
    return path


def _read(path, limit=MAX_METADATA):
    path = _safe(path, directory=False)
    before = path.lstat()
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        current = os.fstat(stream.fileno())
        _check_stat(current)
        if (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino):
            raise ValueError('file replaced while opening')
        if current.st_size > limit:
            raise ValueError('bounded file size exceeded')
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError('bounded file size exceeded')
        return data


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _json(data):
    try:
        return json.loads(data, object_pairs_hook=_pairs)
    except (ValueError, UnicodeError) as error:
        raise ValueError('invalid or duplicate-key JSON') from error


def _sync(directory):
    # Windows stdlib has no portable directory FlushFileBuffers. See runbook.
    if os.name != 'nt':
        fd = os.open(_safe(directory, directory=True), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _new(path, data):
    path = _safe(path, missing=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    flags |= getattr(os, 'O_BINARY', 0)
    with os.fdopen(os.open(path, flags, 0o600), 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    _sync(path.parent)


def _atomic(path, value):
    data = pbo.json_bytes(value)
    if len(data) > MAX_METADATA:
        raise ValueError('metadata budget exceeded')
    path = _safe(path, missing=True)
    temporary = path.with_name('.' + path.name + '.next')
    _new(temporary, data)
    _safe(path, missing=True)
    os.replace(temporary, path)
    _sync(path.parent)


def _mkdir(path):
    path = _safe(path, missing=True)
    path.mkdir(mode=0o700)
    _sync(path.parent)


def _move(source, target):
    source = _safe(source)
    target = _safe(target, missing=True)
    if target.exists():
        raise ValueError('rename target already exists; refusing overwrite')
    os.rename(source, target)
    _sync(source.parent)
    if source.parent != target.parent:
        _sync(target.parent)


def _names(directory):
    directory = _safe(directory, directory=True)
    result = {}
    for path in directory.iterdir():
        if len(result) >= pbo.MAX_ENTRIES:
            raise ValueError('directory entry budget exceeded')
        pbo.safe_name(path.name)
        folded = path.name.casefold()
        if folded in result:
            raise ValueError('case-colliding directory entries')
        result[folded] = path
    return result


def _root(destination):
    root = _safe(destination, directory=True)
    source = Path(__file__).absolute().parents[2]
    if root == Path(root.anchor) or (source / 'AGENTS.md').exists() and (
            root == source or source in root.parents or root in source.parents):
        raise ValueError('destination must be outside source/root directories')
    for part in (root, *root.parents):
        if (part.name.casefold() in {'steam', 'steamapps', 'steamlibrary'}
                or (part / 'steamapps').exists() or (part / '.git').exists()):
            raise ValueError('destination must be outside Steam and source checkouts')
    names = _names(root)
    for expected in (ACTIVE, CONTROL, BOOTSTRAP):
        actual = names.get(expected.casefold())
        if actual is not None and actual.name != expected:
            raise ValueError('managed path has a case alias')
    return root


def _file_map(data):
    return {name: {'bytes': len(value), 'sha256': _sha(value)} for name, value in sorted(data.items())}


def _spec(value):
    if value is None:
        return
    if (not isinstance(value, dict) or set(value) != {'archive_sha256', 'files'}
            or not isinstance(value['archive_sha256'], str) or not SHA.fullmatch(value['archive_sha256'])
            or not isinstance(value['files'], dict) or not 2 <= len(value['files']) <= pbo.MAX_ENTRIES):
        raise ValueError('invalid managed tree manifest')
    pbo._names(value['files'])
    total = 0
    for record in value['files'].values():
        if (not isinstance(record, dict) or set(record) != {'bytes', 'sha256'}
                or type(record['bytes']) is not int or not 0 <= record['bytes'] <= pbo.MAX_BYTES
                or not isinstance(record['sha256'], str) or not SHA.fullmatch(record['sha256'])):
            raise ValueError('invalid file manifest')
        total += record['bytes']
    if total > pbo.MAX_BYTES + MAX_METADATA or 'manifest.json' not in value['files']:
        raise ValueError('invalid tree size/manifest')


def _zip_member(source, info, limit):
    """Bound decompression independently of ZIP metadata and legacy verification."""
    if not 0 <= info.file_size <= limit:
        raise ValueError('ZIP member exceeds uncompressed byte budget')
    chunks, length = [], 0
    with source.open(info, 'r') as stream:
        while length <= info.file_size:
            chunk = stream.read(min(64 * 1024, info.file_size + 1 - length))
            if not chunk:
                break
            length += len(chunk)
            if length > info.file_size or length > limit:
                raise ValueError('ZIP stream exceeds declared size or byte budget')
            chunks.append(chunk)
    if length != info.file_size:
        raise ValueError('ZIP stream differs from declared size')
    return b''.join(chunks)


def _bundle(archive):
    blob = _read(archive, MAX_ARCHIVE)
    # Reject duplicate-key or non-object metadata before the legacy verifier
    # interprets it. Never execute a helper supplied inside an input archive.
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as source:
            entries = source.infolist()
            if not 1 <= len(entries) <= pbo.MAX_ENTRIES:
                raise ValueError('ZIP entry count exceeds budget')
            names = [info.filename for info in entries]
            pbo._names(names)
            if len(names) != len(set(names)):
                raise ValueError('duplicate ZIP members forbidden')
            total = 0
            for info in entries:
                if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise ValueError('only stored/deflated ZIP members are supported')
                kind = stat.S_IFMT(info.external_attr >> 16)
                if (info.is_dir() or kind not in (0, stat.S_IFREG)
                        or info.create_system == 0 and info.external_attr & 0x400):
                    raise ValueError('nonregular/reparse ZIP member forbidden')
                limit = MAX_METADATA if info.filename == 'manifest.json' else pbo.MAX_BYTES
                if not 0 <= info.file_size <= limit:
                    raise ValueError('ZIP member exceeds uncompressed byte budget')
                total += info.file_size
                if total > pbo.MAX_BYTES:
                    raise ValueError('ZIP aggregate uncompressed byte budget exceeded')
            if 'manifest.json' not in names:
                raise ValueError('ZIP manifest required')
            # Every declared size is admitted before opening even the manifest.
            # Bound actual stream reads too, including a one-byte overrun probe.
            data = {info.filename: _zip_member(
                source, info, MAX_METADATA if info.filename == 'manifest.json' else pbo.MAX_BYTES)
                for info in entries}
            strict = _json(data['manifest.json'])
            if not isinstance(strict, dict) or not isinstance(strict.get('files'), dict):
                raise ValueError('handoff manifest object required')
            for item in strict['files'].values():
                if not isinstance(item, dict) or type(item.get('bytes')) is not int:
                    raise ValueError('exact integer payload size required')
    except (KeyError, zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise ValueError('invalid development ZIP') from error
    # Existing verifier is authoritative for the handoff container and PBO map.
    manifest = pbo.verify_handoff(blob)
    if strict != manifest or strict.get('distribution') != 'private-only':
        raise ValueError('private distribution manifest required')
    if strict.get('runtime_acceptance') != 'pending' or type(strict.get('schema')) is not int:
        raise ValueError('development runtime/schema contract required')
    _, scripts = pbo.parse(data['@HollowCountry/addons/hollowcountry.pbo'])
    for name, value in scripts.items():
        if name != 'config.cpp' and not re.fullmatch(r'scripts/(3_Game|4_World|5_Mission)/[A-Za-z0-9_/.-]+\.c', name):
            raise ValueError('PBO must contain original config/script source only')
        pbo._text(value)
    if 'config.cpp' not in scripts:
        raise ValueError('PBO config.cpp required')
    spec = {'archive_sha256': _sha(blob), 'files': _file_map(data)}
    _spec(spec)
    return spec, data


def _directories(spec):
    result = set()
    if spec:
        for name in spec['files']:
            result.update(p.as_posix() for p in Path(name).parents if p.as_posix() != '.')
    return result


def _tree(path, spec, partial=False):
    """Hash every file and reject added empty directories as well as added files."""
    if spec is None:
        if path.exists() or path.is_symlink():
            raise ValueError('unexpected managed tree')
        return {}
    _safe(path, directory=True)
    files, directories, total = {}, set(), 0
    pending = [path]
    allowed = _directories(spec)
    while pending:
        directory = pending.pop()
        for entry in _names(directory).values():
            name = entry.relative_to(path).as_posix()
            info = entry.lstat()
            if stat.S_ISDIR(info.st_mode):
                _check_stat(info, directory=True)
                if name not in allowed:
                    raise ValueError('managed directory drift')
                directories.add(name)
                pending.append(entry)
            else:
                _check_stat(info)
                if name not in spec['files']:
                    raise ValueError('managed file set drift')
                value = _read(entry, pbo.MAX_BYTES)
                total += len(value)
                if total > pbo.MAX_BYTES + MAX_METADATA:
                    raise ValueError('managed tree budget exceeded')
                if _file_map({name: value})[name] != spec['files'][name]:
                    raise ValueError('managed file content drift')
                files[name] = value
    if not partial and (set(files) != set(spec['files']) or directories != allowed):
        raise ValueError('missing managed files/directories')
    return files


def _empty_state():
    return {'schema': 1, 'revision': 0, 'active': None, 'stack': [], 'last': None}


def _identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError('invalid transaction ID')
    return value


def _state(value):
    if (not isinstance(value, dict) or set(value) != {'schema', 'revision', 'active', 'stack', 'last'}
            or type(value['schema']) is not int or value['schema'] != 1
            or type(value['revision']) is not int or not 0 <= value['revision'] <= MAX_TRANSACTIONS
            or not isinstance(value['stack'], list) or len(value['stack']) > MAX_TRANSACTIONS):
        raise ValueError('invalid deployment state')
    for item in value['stack']:
        _identifier(item)
    if len(set(value['stack'])) != len(value['stack']):
        raise ValueError('duplicate transaction in state stack')
    if value['last'] is not None:
        _identifier(value['last'])
    _spec(value['active'])
    if bool(value['active']) != bool(value['stack']) or (value['revision'] == 0) != (value['last'] is None):
        raise ValueError('inconsistent deployment state')
    return value


def _intent(value):
    if not isinstance(value, dict) or set(value) != {'schema', 'transaction', 'operation', 'target', 'before', 'after'}:
        raise ValueError('invalid transaction journal')
    _identifier(value['transaction'])
    before, after = _state(value['before']), _state(value['after'])
    if type(value['schema']) is not int or value['schema'] != 1 or value['operation'] not in {'install', 'upgrade', 'migrate', 'rollback'}:
        raise ValueError('unsupported transaction')
    if after['last'] != value['transaction'] or after['revision'] != before['revision'] + 1:
        raise ValueError('inconsistent transaction revisions')
    if value['operation'] == 'rollback':
        _identifier(value['target'])
        if not before['stack'] or before['stack'][-1] != value['target'] or after['stack'] != before['stack'][:-1]:
            raise ValueError('inconsistent rollback stack')
    elif value['target'] is not None or after['stack'] != before['stack'] + [value['transaction']]:
        raise ValueError('inconsistent forward transaction')
    if value['operation'] == 'install' and before['active'] is not None:
        raise ValueError('install over owned deployment forbidden')
    if value['operation'] in {'upgrade', 'migrate'} and before['active'] is None:
        raise ValueError('upgrade requires existing deployment')
    return value


def _initialize(root):
    control, bootstrap = root / CONTROL, root / BOOTSTRAP
    if control.exists():
        return control
    if bootstrap.exists():
        raise ValueError('interrupted metadata initialization; use explicit recover')
    if (root / ACTIVE).exists():
        raise ValueError('unowned active path; refusing overwrite')
    _mkdir(bootstrap)
    _new(bootstrap / 'owner', OWNER)
    _new(bootstrap / 'lock', b'0')
    _mkdir(bootstrap / 'transactions')
    _mkdir(bootstrap / 'quarantine')
    _atomic(bootstrap / 'state.json', _empty_state())
    _move(bootstrap, control)
    return control


@contextmanager
def _locked(control):
    descriptor = os.open(_safe(control / 'lock', directory=False), os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0))
    try:
        _check_stat(os.fstat(descriptor))
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError('deployment is locked by another process') from error
        yield
    finally:
        os.close(descriptor)  # OS releases lock after process death; no stale PID override.


def _metadata(control):
    names = {p.name for p in _names(control).values()}
    required = {'owner', 'lock', 'state.json', 'transactions', 'quarantine'}
    allowed = required | {'pending.json', '.pending.json.next', '.state.json.next'}
    if not required <= names or not names <= allowed or _read(control / 'owner') != OWNER:
        raise ValueError('unowned or changed deployment metadata')
    # Windows locks prohibit reading the locked byte through another handle,
    # including a second handle in this process. Only its shape matters: the
    # byte is a synchronization region, not an authoritative state record.
    if _safe(control / 'lock', directory=False).stat().st_size != 1:
        raise ValueError('deployment lock shape drift')
    transactions = _names(control / 'transactions')
    if len(transactions) > MAX_TRANSACTIONS:
        raise ValueError('transaction retention limit exceeded')
    for path in transactions.values():
        _identifier(path.name)
        child_names = {p.name for p in _names(path).values()}
        if not child_names <= {'journal.json', 'result.json', 'decision.json', 'before', 'stage', 'discarded',
                              'work.tmp', '.journal.json.next', '.result.json.next', '.decision.json.next'}:
            raise ValueError('unexpected transaction data; refusing mutation')
        for child in _names(path).values():
            _safe(child)
    for path in _names(control / 'quarantine').values():
        if not re.fullmatch(r'[0-9a-f]{32}\.bin', path.name):
            raise ValueError('unexpected quarantine entry')
        _read(path, MAX_METADATA)
    state = _state(_json(_read(control / 'state.json')))
    pending_path = control / 'pending.json'
    pending = _intent(_json(_read(pending_path))) if pending_path.exists() else None
    pending_id = pending['transaction'] if pending else None
    for path in transactions.values():
        journal_path = path / 'journal.json'
        if not journal_path.exists():
            if path.name != pending_id:
                raise ValueError('orphan transaction without a journal')
            continue
        intent = _journal(control, path.name)
        result_path = path / 'result.json'
        if result_path.exists():
            result = _json(_read(result_path))
            if result not in (_receipt(intent, 'committed'), _receipt(intent, 'aborted')):
                raise ValueError('journal/receipt drift')
            if path.name == pending_id:
                if result == _receipt(intent, 'committed') and state != intent['after']:
                    raise ValueError('committed receipt without committed state')
                if result == _receipt(intent, 'aborted') and state != intent['before']:
                    raise ValueError('aborted receipt without original state')
        elif path.name != pending_id:
            raise ValueError('missing completed transaction receipt')
    for transaction in set(state['stack']) | ({state['last']} if state['last'] else set()):
        transaction_path = _safe(control / 'transactions' / transaction, directory=True)
        receipt = transaction_path / 'result.json'
        if receipt.exists() and _json(_read(receipt)) != _receipt(_journal(control, transaction), 'committed'):
            raise ValueError('installed state references an uncommitted transaction')
    if state['last'] and _journal(control, state['last'])['after'] != state:
        raise ValueError('state does not match its committed journal')
    for index, identifier in enumerate(state['stack']):
        journal = _journal(control, identifier)
        if journal['operation'] == 'rollback' or journal['before']['stack'] != state['stack'][:index]:
            raise ValueError('deployment history chain drift')
    if state['stack'] and _journal(control, state['stack'][-1])['after']['active'] != state['active']:
        raise ValueError('active manifest does not match installed history')
    return state


def _load(root, pending_ok=False):
    if (root / BOOTSTRAP).exists():
        raise ValueError('metadata bootstrap remains; inspect/recover first')
    control = root / CONTROL
    if not control.exists():
        _tree(root / ACTIVE, None)
        return _empty_state()
    state = _metadata(control)
    if not pending_ok and ((control / 'pending.json').exists()
                           or any((control / name).exists() for name in ['.pending.json.next', '.state.json.next'])):
        raise ValueError('interrupted transaction; explicit recover required')
    if not pending_ok:
        _tree(root / ACTIVE, state['active'])
    return state


def _journal(control, identifier):
    value = _intent(_json(_read(control / 'transactions' / _identifier(identifier) / 'journal.json')))
    if value['transaction'] != identifier:
        raise ValueError('journal transaction identity drift')
    return value


def _report(intent, status, idempotent=False):
    return {'transaction': intent['transaction'], 'operation': intent['operation'], 'status': status,
            'idempotent': idempotent, 'distribution': 'private-only', 'runtime_acceptance': 'pending'}


def _receipt(intent, status):
    return {'schema': 1, 'status': status, 'journal_sha256': _sha(pbo.json_bytes(intent))}


def _record(control, intent, status):
    path = control / 'transactions' / intent['transaction'] / 'result.json'
    expected = _receipt(intent, status)
    if path.exists():
        if _json(_read(path)) != expected:
            raise ValueError('transaction receipt drift')
    else:
        _atomic(path, expected)


def _clear(control):
    _safe(control / 'pending.json', directory=False).unlink()
    _sync(control)


def _stage(transaction, spec, data, checkpoint):
    if spec is None:
        return
    stage = transaction / 'stage'
    _mkdir(stage)
    for name, value in sorted(data.items()):
        path = stage / name
        for directory in reversed(path.parent.relative_to(stage).parents):
            if directory.as_posix() != '.' and not (stage / directory).exists():
                _mkdir(stage / directory)
        if not path.parent.exists():
            _mkdir(path.parent)
        _new(transaction / 'work.tmp', value)
        _move(transaction / 'work.tmp', path)
        checkpoint('stage-file')
    _tree(stage, spec)


def _forward(root, intent, checkpoint):
    control, active = root / CONTROL, root / ACTIVE
    transaction = control / 'transactions' / intent['transaction']
    before, after = intent['before']['active'], intent['after']['active']
    backup, stage = transaction / 'before', transaction / 'stage'
    if before is not None and not backup.exists():
        _tree(active, before)
        _move(active, backup)
    checkpoint('backed-up')
    if after is not None and stage.exists():
        _tree(stage, after)
        _tree(active, None)
        _move(stage, active)
    _tree(active, after)
    checkpoint('activated')
    _atomic(control / 'state.json', intent['after'])  # Commit point.
    checkpoint('committed')
    _record(control, intent, 'committed')
    checkpoint('recorded')
    _clear(control)
    return _report(intent, 'committed')


def _execute(root, state, spec, data, operation, target, checkpoint):
    control = root / CONTROL
    if state['revision'] >= MAX_TRANSACTIONS or len(_names(control / 'transactions')) >= MAX_TRANSACTIONS:
        raise ValueError('transaction retention limit; preserve/archive metadata before further changes')
    identifier = uuid.uuid4().hex
    after = {'schema': 1, 'revision': state['revision'] + 1, 'active': spec,
             'stack': state['stack'][:-1] if operation == 'rollback' else state['stack'] + [identifier],
             'last': identifier}
    intent = _intent({'schema': 1, 'transaction': identifier, 'operation': operation,
                      'target': target, 'before': state, 'after': after})
    _atomic(control / 'pending.json', intent)
    checkpoint('journaled')
    transaction = control / 'transactions' / identifier
    _mkdir(transaction)
    _atomic(transaction / 'journal.json', intent)
    _stage(transaction, spec, data, checkpoint)
    checkpoint('staged')
    _tree(root / ACTIVE, state['active'])
    return _forward(root, intent, checkpoint)


def plan(archive, destination):
    spec, _ = _bundle(archive)
    root = _root(destination)
    state = _load(root)
    return {'operation': 'upgrade' if state['active'] else 'install', 'destination': str(root),
            'archive_sha256': spec['archive_sha256'], 'files': len(spec['files']),
            'idempotent': spec == state['active'], 'runtime_acceptance': 'pending',
            'profile_migration': 'none; external runtime profiles preserved'}


def _stopped(value):
    if value is not True:
        raise ValueError('stop server and destination writers; --server-stopped acknowledgement required')


def install(archive, destination, operation='install', server_stopped=False, checkpoint=lambda event: None):
    _stopped(server_stopped)
    if operation not in {'install', 'upgrade', 'migrate'}:
        raise ValueError('invalid install operation')
    spec, data = _bundle(archive)
    root = _root(destination)
    state = _load(root)
    if state['active'] is None and operation != 'install':
        raise ValueError('upgrade/migrate requires owned installation')
    if state['active'] is not None and spec != state['active'] and operation == 'install':
        raise ValueError('use explicit upgrade or migrate for an installed destination')
    control = _initialize(root)
    with _locked(control):
        state = _load(root)
        if spec == state['active']:
            return _report(_journal(control, state['last']), 'committed', idempotent=True)
        return _execute(root, state, spec, data, operation, None, checkpoint)


def rollback(destination, transaction, server_stopped=False, checkpoint=lambda event: None):
    _stopped(server_stopped)
    _identifier(transaction)
    root = _root(destination)
    _load(root)
    with _locked(root / CONTROL):
        state = _load(root)
        last = _journal(root / CONTROL, state['last']) if state['last'] else None
        if last and last['operation'] == 'rollback' and last['target'] == transaction:
            return _report(last, 'committed', idempotent=True)
        if not state['stack'] or state['stack'][-1] != transaction:
            raise ValueError('rollback target is not the current installation/upgrade')
        original = _journal(root / CONTROL, transaction)
        desired = original['before']['active']
        backup = root / CONTROL / 'transactions' / transaction / 'before'
        data = _tree(backup, desired)
        return _execute(root, state, desired, data, 'rollback', transaction, checkpoint)


def _quarantine_temps(control):
    candidates = [control / '.pending.json.next', control / '.state.json.next']
    for transaction in _names(control / 'transactions').values():
        candidates.extend(transaction / ('.' + name + '.next')
                          for name in ['journal.json', 'result.json', 'decision.json'])
    for path in candidates:
        if path.exists():
            _read(path)
            _move(path, control / 'quarantine' / (uuid.uuid4().hex + '.bin'))


def _slots(root, intent):
    """Refuse all unexpected combinations before recovering any directory."""
    transaction = root / CONTROL / 'transactions' / intent['transaction']
    active, backup, stage = root / ACTIVE, transaction / 'before', transaction / 'stage'
    before, after = intent['before']['active'], intent['after']['active']
    discarded = transaction / 'discarded'
    if backup.exists():
        _tree(backup, before)
    if stage.exists():
        _tree(stage, after, partial=True)
    if discarded.exists():
        _tree(discarded, after)
    if (transaction / 'work.tmp').exists():
        _read(transaction / 'work.tmp', pbo.MAX_BYTES)
    if active.exists():
        if backup.exists() or before is None:
            _tree(active, after)
            if stage.exists() or discarded.exists():
                raise ValueError('ambiguous active/staging transaction slots')
        else:
            _tree(active, before)
    elif before is not None and not backup.exists():
        raise ValueError('missing original package and backup')
    return transaction


def recover(destination, action='abort', server_stopped=False, checkpoint=lambda event: None):
    _stopped(server_stopped)
    if action not in {'abort', 'resume'}:
        raise ValueError('explicit recovery action must be abort or resume')
    root = _root(destination)
    bootstrap, control = root / BOOTSTRAP, root / CONTROL
    if bootstrap.exists():
        if control.exists() or (root / ACTIVE).exists():
            raise ValueError('ambiguous metadata bootstrap; preserve and inspect')
        if _metadata(bootstrap) != _empty_state() or (bootstrap / 'pending.json').exists():
            raise ValueError('invalid bootstrap; preserve and inspect')
        _move(bootstrap, control)
    if not control.exists():
        _tree(root / ACTIVE, None)
        return {'status': 'no-pending-transaction', 'idempotent': True}
    with _locked(control):
        state = _metadata(control)
        # Validate the authoritative journal before moving transient metadata.
        pending = control / 'pending.json'
        intent = _intent(_json(_read(pending))) if pending.exists() else None
        if intent is None:
            _tree(root / ACTIVE, state['active'])
            _quarantine_temps(control)
            return {'status': 'no-pending-transaction', 'idempotent': True}
        if state not in (intent['before'], intent['after']):
            raise ValueError('state/journal drift')
        transaction = control / 'transactions' / intent['transaction']
        if transaction.exists() and (transaction / 'journal.json').exists():
            if _journal(control, intent['transaction']) != intent:
                raise ValueError('pending/archived journal drift')
        _slots(root, intent)
        if state == intent['after']:
            _tree(root / ACTIVE, state['active'])
            _quarantine_temps(control)
            _record(control, intent, 'committed')
            _clear(control)
            return _report(intent, 'committed', idempotent=True)
        decision = transaction / 'decision.json'
        if decision.exists():
            stored = _json(_read(decision))
            if stored not in ({'action': 'abort'}, {'action': 'resume'}):
                raise ValueError('recovery decision drift')
            action = stored['action']
        if action == 'resume':
            after = intent['after']['active']
            stage = transaction / 'stage'
            if stage.exists():
                _tree(stage, after)
            elif after is not None:
                _tree(root / ACTIVE, after)
        _quarantine_temps(control)
        if not transaction.exists():
            _mkdir(transaction)
        if not (transaction / 'journal.json').exists():
            _atomic(transaction / 'journal.json', intent)
        if not decision.exists():
            _atomic(decision, {'action': action})
        if action == 'resume':
            return _forward(root, intent, checkpoint)
        active, backup, discarded = root / ACTIVE, transaction / 'before', transaction / 'discarded'
        if active.exists() and (backup.exists() or intent['before']['active'] is None):
            _tree(active, intent['after']['active'])
            _move(active, discarded)
            checkpoint('abort-deactivated')
        if backup.exists():
            _tree(active, None)
            _move(backup, active)
            checkpoint('abort-restored')
        _tree(active, intent['before']['active'])
        _record(control, intent, 'aborted')
        checkpoint('abort-recorded')
        _clear(control)
        return _report(intent, 'aborted')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ['plan', 'install', 'upgrade', 'migrate', 'rollback', 'recover']:
        entry = sub.add_parser(command)
        entry.add_argument('--destination', type=Path, required=True)
        if command in {'plan', 'install', 'upgrade', 'migrate'}:
            entry.add_argument('--zip', type=Path, required=True)
        if command == 'rollback':
            entry.add_argument('--transaction', required=True)
        if command == 'recover':
            entry.add_argument('--action', choices=['abort', 'resume'], required=True)
        if command != 'plan':
            entry.add_argument('--server-stopped', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'plan':
            result = plan(args.zip, args.destination)
        elif args.command == 'rollback':
            result = rollback(args.destination, args.transaction, server_stopped=args.server_stopped)
        elif args.command == 'recover':
            result = recover(args.destination, args.action, server_stopped=args.server_stopped)
        else:
            result = install(args.zip, args.destination, args.command, server_stopped=args.server_stopped)
        print(json.dumps(result, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        parser.exit(1, f'Deployment refused: {error}\n')


if __name__ == '__main__':
    main()
