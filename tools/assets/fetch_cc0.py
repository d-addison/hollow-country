"""Pinned CC0 archive fetcher into a local cache that lives outside git.

Only archive downloads named by a pin manifest are fetched: https, an allowlisted
archive host, a .zip target, an exact byte count and a sha256. Website preview
thumbnails are refused (Poly Haven preview terms differ from its CC0 archives).
Archives are verified while streaming, written under a temporary name and
renamed into a content-addressed path, never extracted. Cached files are local
only and must never be committed; the cache directory is refused if it sits
inside a git work tree or a symlink.

Manifest (schema cc0-pins.v1): {"schema": "cc0-pins.v1", "pins": [
  {"id": "rock_01", "source": "polyhaven", "url": "https://...zip",
   "sha256": "<64 hex>", "bytes": 123, "licence_id": "CC0-1.0"}]}

Default mode is offline verification; pass --download to use the network.
Output names pins and cache-relative files only, never absolute paths.
"""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import parse_qs, urlsplit

from tools.assets.licence_gate import load_policy
from tools.assets.provenance import ROOT, Refusal, SHA256, load_json

SCHEMA = 'cc0-pins.v1'
SOURCES = ('polyhaven', 'ambientcg')
LICENCE = 'CC0-1.0'
AMBIENTCG_HOSTS = ('ambientcg.com',)
MAX_PINS = 64
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_REDIRECTS = 3
CHUNK = 64 * 1024
DEFAULT_SECONDS = 120.0
SOCKET_TIMEOUT = 15.0
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')
ARCHIVE_FILE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.zip\Z')


def _allowed_url(url, source, policy):
    """Return the validated url or raise; used for pins and every redirect."""
    if not isinstance(url, str) or not url or len(url) > 512 or any(c.isspace() or ord(c) < 33 or ord(c) > 126 for c in url):
        raise Refusal('fetch.url_invalid')
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise Refusal('fetch.url_invalid') from None
    if (parts.scheme != 'https' or parts.username or parts.password or port
            or parts.fragment or not parts.hostname):
        raise Refusal('fetch.url_invalid')
    host, path = parts.hostname.lower(), parts.path
    if source == 'polyhaven':
        ph = policy['poly_haven']
        # Substring and suffix both: a preview image path is never an archive.
        if (ph['preview_path'] in path or host not in ph['archive_hosts']
                or parts.query or not any(path.endswith(s) for s in ph['archive_suffixes'])
                or '..' in path.split('/') or '//' in path):
            raise Refusal('fetch.url_not_archive')
    elif source == 'ambientcg':
        query = parse_qs(parts.query, keep_blank_values=True, strict_parsing=False)
        names = query.get('file', [])
        if (host not in AMBIENTCG_HOSTS or path != '/get' or set(query) != {'file'}
                or len(names) != 1 or not ARCHIVE_FILE.fullmatch(names[0])):
            raise Refusal('fetch.url_not_archive')
    else:
        raise Refusal('fetch.source_invalid')
    return url


def load_pins(data, *, policy=None):
    """Validate a manifest document (bytes or text) into a list of pin dicts."""
    policy = policy or load_policy()
    document = load_json(data)
    if (not isinstance(document, dict) or set(document) != {'schema', 'pins'}
            or document['schema'] != SCHEMA or not isinstance(document['pins'], list)
            or not 1 <= len(document['pins']) <= MAX_PINS):
        raise Refusal('fetch.manifest_invalid')
    pins, ids, digests, total = [], set(), set(), 0
    for row in document['pins']:
        keys = {'id', 'source', 'url', 'sha256', 'bytes', 'licence_id'}
        if not isinstance(row, dict) or set(row) != keys:
            raise Refusal('fetch.pin_fields')
        if (not isinstance(row['id'], str) or not ID.fullmatch(row['id'])
                or row['source'] not in SOURCES or row['licence_id'] != LICENCE
                or not isinstance(row['sha256'], str) or not SHA256.fullmatch(row['sha256'])
                or type(row['bytes']) is not int or not 1 <= row['bytes'] <= MAX_ARCHIVE_BYTES):
            raise Refusal('fetch.pin_invalid')
        if row['id'] in ids or row['sha256'] in digests:
            raise Refusal('fetch.pin_duplicate')
        _allowed_url(row['url'], row['source'], policy)
        ids.add(row['id'])
        digests.add(row['sha256'])
        total += row['bytes']
        pins.append(dict(row))
    if total > MAX_TOTAL_BYTES:
        raise Refusal('fetch.total_limit')
    return pins


def default_cache():
    override = os.environ.get('HC_ASSET_CACHE')
    base = Path(override) if override else Path.home() / '.cache' / 'hollow-country' / 'asset-cache'
    return base


def prepare_cache(path, *, repo_root=ROOT):
    """Create/validate the cache root: absolute, no symlinks, outside any git tree."""
    path = Path(path)
    if not path.is_absolute() or '\x00' in str(path):
        raise Refusal('cache.not_absolute')
    # Reject a symlinked component before resolving would hide it.
    probe = path
    while True:
        if probe.is_symlink():
            raise Refusal('cache.symlink')
        if probe.parent == probe:
            break
        probe = probe.parent
    resolved = path.resolve()
    root = Path(repo_root).resolve()
    if resolved == root or root in resolved.parents:
        raise Refusal('cache.inside_repository')
    for ancestor in (resolved, *resolved.parents):
        if (ancestor / '.git').exists():
            raise Refusal('cache.inside_repository')
    target = resolved / 'cc0'
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    if target.is_symlink() or not target.is_dir():
        raise Refusal('cache.symlink')
    return target


def cached_name(pin):
    return pin['sha256'] + '.zip'


def _hash_file(path, limit):
    if path.is_symlink() or not path.is_file():
        raise Refusal('cache.not_regular')
    digest, size = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while True:
            block = stream.read(CHUNK)
            if not block:
                break
            size += len(block)
            if size > limit:
                raise Refusal('cache.oversize')
            digest.update(block)
    return digest.hexdigest(), size


def verify_cached(pin, directory):
    """True when the cached archive exists and matches its pin; False if absent."""
    path = directory / cached_name(pin)
    if not (path.exists() or path.is_symlink()):
        return False
    try:
        digest, size = _hash_file(path, pin['bytes'])
    except (Refusal, OSError):
        return False
    return digest == pin['sha256'] and size == pin['bytes']


def urllib_opener(policy, source):
    """Default network opener: redirects are revalidated, never followed blindly."""
    import urllib.error
    import urllib.request

    class Guard(urllib.request.HTTPRedirectHandler):
        max_redirections = MAX_REDIRECTS

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            _allowed_url(newurl, source, policy)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(Guard)

    def open_url(url, timeout):
        request = urllib.request.Request(url, headers={'User-Agent': 'hollow-country-asset-fetch'})
        return opener.open(request, timeout=timeout)
    return open_url


def download(pin, directory, *, opener, policy, deadline):
    """Stream a pinned archive to a temp file, verify, then rename into place."""
    final = directory / cached_name(pin)
    temp = directory / ('.partial-' + pin['sha256'] + '.' + str(os.getpid()))
    digest, size = hashlib.sha256(), 0
    try:
        with opener(pin['url'], SOCKET_TIMEOUT) as response:
            _allowed_url(response.geturl(), pin['source'], policy)
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            with os.fdopen(fd, 'wb') as out:
                while True:
                    if time.monotonic() > deadline:
                        raise Refusal('fetch.time_limit')
                    block = response.read(CHUNK)
                    if not block:
                        break
                    size += len(block)
                    if size > pin['bytes']:
                        raise Refusal('fetch.byte_limit')
                    digest.update(block)
                    out.write(block)
        if size != pin['bytes']:
            raise Refusal('fetch.size_mismatch')
        if digest.hexdigest() != pin['sha256']:
            raise Refusal('fetch.sha256_mismatch')
        if final.is_symlink():
            raise Refusal('cache.symlink')
        os.replace(temp, final)
    except (OSError, http.client.HTTPException) as exc:
        raise Refusal('fetch.network_or_io') from exc
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
    return final


def fetch(pins, cache, *, download_enabled=False, opener=None, max_seconds=DEFAULT_SECONDS,
          policy=None, repo_root=ROOT):
    """Return {id: {'state': ..., 'file': 'cc0/<sha>.zip'}}; state ok|downloaded|missing|failed.

    Without download_enabled no network is touched. A corrupt cache entry is
    removed and re-fetched when downloading, so interrupted runs self-repair.
    """
    policy = policy or load_policy()
    directory = prepare_cache(cache, repo_root=repo_root)
    deadline = time.monotonic() + max_seconds
    result = {}
    for pin in pins:
        entry = {'state': 'ok', 'file': 'cc0/' + cached_name(pin)}
        result[pin['id']] = entry
        if verify_cached(pin, directory):
            continue
        if not download_enabled:
            entry['state'] = 'missing'
            continue
        stale = directory / cached_name(pin)
        if stale.exists() or stale.is_symlink():
            stale.unlink()
        try:
            download(pin, directory,
                     opener=opener or urllib_opener(policy, pin['source']),
                     policy=policy, deadline=deadline)
            entry['state'] = 'downloaded'
        except Refusal as exc:
            entry['state'] = 'failed'
            entry['reason'] = str(exc)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--cache', type=Path, default=None)
    parser.add_argument('--download', action='store_true',
                        help='use the network; default only verifies the local cache')
    parser.add_argument('--max-seconds', type=float, default=DEFAULT_SECONDS)
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.max_seconds <= 1800:
            raise Refusal('fetch.time_invalid')
        pins = load_pins(args.manifest.read_bytes())
        report = fetch(pins, args.cache or default_cache(), download_enabled=args.download,
                       max_seconds=args.max_seconds)
    except (Refusal, OSError) as exc:
        print(json.dumps({'valid': False, 'reason': str(exc) if isinstance(exc, Refusal) else 'fetch.io'}))
        return 1
    valid = all(v['state'] in ('ok', 'downloaded') for v in report.values())
    print(json.dumps({'valid': valid, 'pins': report}, sort_keys=True))
    return 0 if valid else 1


if __name__ == '__main__':
    sys.exit(main())
