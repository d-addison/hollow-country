"""SHA-256 cache for large Workshop PBOs, keyed by (absolute path, size, mtime_ns).

Stored under ~/.cache/hollow-country/pbo-hash/ (override: HC_HASH_CACHE_DIR), never in the repo. An entry
is used only when size and mtime_ns both match; any other state re-hashes. A missing, corrupt or
wrong-shaped cache file is ignored, and a cache that cannot be written is ignored too: the cache is only
ever an optimisation, never a source of truth or a failure. Files modified within RACY_WINDOW_NS of now are
hashed but not stored, because a rewrite inside one filesystem timestamp tick would keep the same
(size, mtime_ns) key (#183).

Every row carries `used`, the time (ns) of its last use. Over MAX_ENTRIES the least recently used rows are
evicted (#194), not the oldest inserted. A hit refreshes `used` only when it is older than USE_REFRESH_NS, so
a run of hits stays read-only. Each write goes through its own temp file (pid + random suffix) and an atomic
replace, so two concurrent builds never share a temp path.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time

CACHE_FILE = 'sha256-cache.json'
CACHE_SCHEMA = 1
MAX_ENTRIES = 512
RACY_WINDOW_NS = 2 * 10 ** 9
# A hit rewrites the cache only to refresh a `used` stamp older than this (one hour).
USE_REFRESH_NS = 3600 * 10 ** 9
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
    return {key: row for key, row in entries.items() if isinstance(row, dict)}


def _now_ns():
    return time.time_ns()


def _used(row):
    value = row.get('used')
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _store(directory, entries):
    temp = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
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
    if (row is not None and row.get('size') == before.st_size and row.get('mtime_ns') == before.st_mtime_ns
            and isinstance(row.get('sha256'), str) and _DIGEST.fullmatch(row['sha256'])):
        now = _now_ns()
        if now - _used(row) > USE_REFRESH_NS:
            row['used'] = now
            _store(directory, entries)
        return row['sha256']
    digest = _hash_file(path)
    after = path.stat()
    stable = (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    if stable and time.time_ns() - after.st_mtime_ns > RACY_WINDOW_NS:
        entries.pop(key, None)
        entries[key] = {'size': after.st_size, 'mtime_ns': after.st_mtime_ns, 'sha256': digest, 'used': _now_ns()}
        _store(directory, entries)
    return digest
