"""SHA-256 cache for large Workshop PBOs, keyed by (absolute path, size, mtime_ns, inode, ctime_ns).

Stored under ~/.cache/hollow-country/pbo-hash/ (override: HC_HASH_CACHE_DIR), never in the repo. An entry
is used only when size, mtime_ns, inode and ctime_ns all match (inode and ctime catch a file rewritten
with the same size and a restored mtime, #195; where a platform reports no inode it is 0 on both sides);
any other state re-hashes, including a row stored before those two fields existed. A missing, corrupt or
wrong-shaped cache file is ignored, and a cache that cannot be written is ignored too: the cache is only
ever an optimisation, never a source of truth or a failure. Files modified within RACY_WINDOW_NS of now are
hashed but not stored, because a rewrite inside one filesystem timestamp tick would keep the same
(size, mtime_ns) key (#183).

Every row carries `used`, the time (ns) of its last use. Over MAX_ENTRIES the least recently used rows are
evicted (#194), not the oldest inserted. A hit refreshes `used` only when it is older than USE_REFRESH_NS, so
a run of hits stays read-only. Each write goes through its own temp file (pid + random suffix) and an atomic
replace, so two concurrent builds never share a temp path.

Concurrent builds are last writer wins: each loads the file, adds its rows and replaces it, so a row
another build added in between is lost (never corrupted) and is simply re-hashed next time. A `used`
stamp in the future (clock change) is clamped to now when the file is read, so the row can age out and
be evicted. A write first removes `sha256-cache.json.*.tmp` files older than ORPHAN_TEMP_AGE_NS, the
leftovers of a build that was killed between writing and replacing.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import time

CACHE_FILE = 'sha256-cache.json'
CACHE_SCHEMA = 1
MAX_ENTRIES = 512
RACY_WINDOW_NS = 2 * 10 ** 9
# A hit rewrites the cache only to refresh a `used` stamp older than this (one hour).
USE_REFRESH_NS = 3600 * 10 ** 9
# A leftover temp file older than this (one hour) is removed by the next write.
ORPHAN_TEMP_AGE_NS = 3600 * 10 ** 9
BLOCK_BYTES = 1024 * 1024
_DIGEST = re.compile(r'[0-9a-f]{64}')


def cache_dir():
    override = os.environ.get('HC_HASH_CACHE_DIR')
    if override:
        return Path(override)
    return Path.home() / '.cache' / 'hollow-country' / 'pbo-hash'


def _hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(BLOCK_BYTES), b''):
            digest.update(block)
    return digest.hexdigest()


def _load(directory):
    try:
        data = json.loads((directory / CACHE_FILE).read_text(encoding='utf-8'))
    except (OSError, ValueError):  # includes UnicodeDecodeError and JSONDecodeError
        return {}
    entries = data.get('entries') if isinstance(data, dict) and data.get('schema') == CACHE_SCHEMA else None
    if not isinstance(entries, dict):
        return {}
    rows = {key: row for key, row in entries.items() if isinstance(row, dict)}
    now = _now_ns()
    for row in rows.values():
        if _used(row) > now:
            row['used'] = now  # a stamp from the future could never age out
    return rows


def _now_ns():
    return time.time_ns()


def _used(row):
    value = row.get('used')
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _stamp(info):
    """The identity of a file's contents as far as stat can tell: (size, mtime_ns, inode, ctime_ns)."""
    return (info.st_size, info.st_mtime_ns, getattr(info, 'st_ino', 0), getattr(info, 'st_ctime_ns', 0))


def _sweep_orphans(directory):
    """Remove `sha256-cache.json.*.tmp` files older than ORPHAN_TEMP_AGE_NS (killed writers' leftovers)."""
    now = _now_ns()
    try:
        names = [name for name in os.listdir(directory) if name.startswith(CACHE_FILE + '.') and name.endswith('.tmp')]
    except OSError:
        return
    for name in names:
        path = directory / name
        try:
            info = path.lstat()
            if stat.S_ISREG(info.st_mode) and now - info.st_mtime_ns > ORPHAN_TEMP_AGE_NS:
                path.unlink()
        except OSError:
            pass


def _row_stamp(row):
    return (row.get('size'), row.get('mtime_ns'), row.get('ino'), row.get('ctime_ns'))


def _store(directory, entries):
    temp = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        _sweep_orphans(directory)
        if len(entries) > MAX_ENTRIES:
            # Stable sort: rows with an equal (or missing) `used` keep their loaded order (keys are stored sorted).
            ranked = sorted(entries.items(), key=lambda item: _used(item[1]))
            entries = dict(ranked[-MAX_ENTRIES:])
        temp = directory / ('%s.%d.%s.tmp' % (CACHE_FILE, os.getpid(), secrets.token_hex(8)))
        temp.write_text(json.dumps({'schema': CACHE_SCHEMA, 'entries': entries}, sort_keys=True), encoding='utf-8')
        os.replace(temp, directory / CACHE_FILE)
    except OSError:
        if temp is not None:
            try:
                temp.unlink()
            except OSError:
                pass


def cached_sha256(path, directory=None):
    path = Path(path).absolute()
    directory = Path(directory) if directory is not None else cache_dir()
    before = path.stat()
    key = str(path)
    entries = _load(directory)
    row = entries.get(key)
    if (row is not None and _row_stamp(row) == _stamp(before)
            and isinstance(row.get('sha256'), str) and _DIGEST.fullmatch(row['sha256'])):
        now = _now_ns()
        if now - _used(row) > USE_REFRESH_NS:
            row['used'] = now
            _store(directory, entries)
        return row['sha256']
    digest = _hash_file(path)
    after = path.stat()
    stable = _stamp(after) == _stamp(before)
    if stable and time.time_ns() - after.st_mtime_ns > RACY_WINDOW_NS:
        entries.pop(key, None)
        size, mtime_ns, ino, ctime_ns = _stamp(after)
        entries[key] = {'size': size, 'mtime_ns': mtime_ns, 'ino': ino, 'ctime_ns': ctime_ns, 'sha256': digest,
                        'used': _now_ns()}
        _store(directory, entries)
    return digest
