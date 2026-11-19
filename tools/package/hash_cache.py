"""SHA-256 cache for large Workshop PBOs, keyed by (absolute path, size, mtime_ns).

Stored under ~/.cache/hollow-country/pbo-hash/ (override: HC_HASH_CACHE_DIR), never in the repo. An entry
is used only when size and mtime_ns both match; any other state re-hashes. A missing, corrupt or
wrong-shaped cache file is ignored, and a cache that cannot be written is ignored too: the cache is only
ever an optimisation, never a source of truth or a failure. Files modified within RACY_WINDOW_NS of now are
hashed but not stored, because a rewrite inside one filesystem timestamp tick would keep the same
(size, mtime_ns) key (#183).
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time

CACHE_FILE = 'sha256-cache.json'
CACHE_SCHEMA = 1
MAX_ENTRIES = 512
RACY_WINDOW_NS = 2 * 10 ** 9
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


def _store(directory, entries):
    try:
        directory.mkdir(parents=True, exist_ok=True)
        if len(entries) > MAX_ENTRIES:
            entries = dict(list(entries.items())[-MAX_ENTRIES:])
        temp = directory / (CACHE_FILE + '.tmp')
        temp.write_text(json.dumps({'schema': CACHE_SCHEMA, 'entries': entries}, sort_keys=True), encoding='utf-8')
        os.replace(temp, directory / CACHE_FILE)
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
        return row['sha256']
    digest = _hash_file(path)
    after = path.stat()
    stable = (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    if stable and time.time_ns() - after.st_mtime_ns > RACY_WINDOW_NS:
        entries.pop(key, None)
        entries[key] = {'size': after.st_size, 'mtime_ns': after.st_mtime_ns, 'sha256': digest}
        _store(directory, entries)
    return digest
