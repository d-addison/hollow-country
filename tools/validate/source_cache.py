"""Shared parsed-source cache for the Enforce validators (standard library only).

``enforce_source.Source`` lexes and parses a whole file; lint, perf and the readiness/JSON rules all
build the same Source objects, so each process re-derived them several times. ``SourceCache`` keeps a
parsed Source in memory per process and, when a directory is configured, on disk so a second process
(preland runs each check as its own subprocess) loads it instead of parsing it again.

Key: path, root, mod, size, mtime_ns and a content hash. A text-only caller has no stat, so size is the
text length and mtime is absent; the content hash still decides every hit, and a hit also requires the
stored text to equal the requested text, so a stale or damaged entry only costs a re-parse.

The on-disk directory is ``$HC_SOURCE_CACHE_DIR`` (preland points it at the git-ignored ``build/``
tree). Entries are pickles written by this tool into a private directory (mode 0700) and are versioned
by a fingerprint of enforce_source.py, this file and the interpreter; a changed parser therefore never
reads an old entry, and directories of older fingerprints are removed on first use. It is only a
speed-up: any read or write failure falls back to parsing, and findings are identical with or without it.
"""
import atexit
import hashlib
import os
from pathlib import Path
import pickle
import re
import shutil
import sys
import tempfile

ENV = 'HC_SOURCE_CACHE_DIR'
STATS_ENV = 'HC_SOURCE_CACHE_STATS'
MEMORY_TEXT_BYTES = 96 * 1024 * 1024
_FINGERPRINT_DIR = re.compile(r'v[0-9a-f]{16}')


def _fingerprint():
    here = Path(__file__).resolve().parent
    digest = hashlib.blake2b(digest_size=8)
    for name in ('enforce_source.py', 'source_cache.py'):
        digest.update((here / name).read_bytes())
    digest.update(repr((sys.version_info[:3], pickle.HIGHEST_PROTOCOL)).encode())
    return 'v' + digest.hexdigest()


def _digest(text):
    return hashlib.blake2b(text.encode('utf-8', 'surrogatepass'), digest_size=16).hexdigest()


class SourceCache:
    def __init__(self, directory=None, memory_text_bytes=MEMORY_TEXT_BYTES):
        self.directory = Path(directory) if directory else None
        self.memory_text_bytes = memory_text_bytes
        self.entries = {}          # insertion-ordered: oldest first
        self.text_bytes = 0
        self.stats = dict(memory=0, disk=0, parsed=0, stored=0)
        self._disk_ready = None

    # -- disk ---------------------------------------------------------------
    def _disk(self):
        """The versioned directory, or None when no usable cache directory is configured."""
        if self._disk_ready is None:
            self._disk_ready = False
            if self.directory is not None:
                try:
                    current = self.directory / _fingerprint()
                    current.mkdir(mode=0o700, parents=True, exist_ok=True)
                    for sibling in self.directory.iterdir():
                        if sibling != current and sibling.is_dir() and _FINGERPRINT_DIR.fullmatch(sibling.name):
                            shutil.rmtree(sibling, ignore_errors=True)
                    self._disk_ready = current
                except OSError:
                    self._disk_ready = False
        return self._disk_ready or None

    @staticmethod
    def _file_name(path, root, mod):
        name = '%s\0%s\0%s' % (path, root or '', mod or '')
        return hashlib.blake2b(name.encode('utf-8', 'surrogatepass'), digest_size=16).hexdigest() + '.pkl'

    def _load(self, path, root, mod, meta, text):
        directory = self._disk()
        if directory is None:
            return None
        try:
            stored_meta, source = pickle.loads((directory / self._file_name(path, root, mod)).read_bytes())
        except Exception:      # absent, truncated or from a different build: just parse again
            return None
        if stored_meta != meta or getattr(source, 'text', None) != text:
            return None
        return source

    def _store(self, path, root, mod, meta, source):
        directory = self._disk()
        if directory is None:
            return
        try:
            data = pickle.dumps((meta, source), protocol=pickle.HIGHEST_PROTOCOL)
            handle, temporary = tempfile.mkstemp(dir=directory, suffix='.tmp')
            try:
                with os.fdopen(handle, 'wb') as out:
                    out.write(data)
                os.replace(temporary, directory / self._file_name(path, root, mod))
            except BaseException:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
                raise
            self.stats['stored'] += 1
        except (OSError, pickle.PickleError, RecursionError):
            pass

    # -- memory -------------------------------------------------------------
    def _remember(self, key, source, size):
        if size > self.memory_text_bytes:
            return
        self.entries[key] = (source, size)
        self.text_bytes += size
        while self.text_bytes > self.memory_text_bytes and len(self.entries) > 1:
            oldest = next(iter(self.entries))
            self.text_bytes -= self.entries.pop(oldest)[1]

    def get(self, build, path, text, root=None, mod=None, stat=None, persist=False):
        """Return the parsed Source for this input, calling build() only on a miss.

        ``stat`` is (size, mtime_ns) of the file the text was read from, when there is one. ``persist``
        also uses the on-disk cache; callers set it for files of the repository's own tree only.
        """
        path, root = os.fspath(path), os.fspath(root) if root is not None else None
        size, mtime = stat if stat else (len(text), None)
        digest = _digest(text)
        key = (path, root, mod, size, mtime, digest)
        found = self.entries.get(key)
        if found is not None and found[0].text == text:
            self.stats['memory'] += 1
            return found[0]
        source = None
        if persist and stat:
            source = self._load(path, root, mod, (size, mtime, digest), text)
            if source is not None:
                self.stats['disk'] += 1
        if source is None:
            source = build()
            self.stats['parsed'] += 1
            if persist and stat:
                self._store(path, root, mod, (size, mtime, digest), source)
        self._remember(key, source, len(text))
        return source

    def clear(self):
        self.entries.clear()
        self.text_bytes = 0


_shared = None


def shared():
    """The process-wide cache; its directory comes from $HC_SOURCE_CACHE_DIR at first use."""
    global _shared
    if _shared is None:
        _shared = SourceCache(os.environ.get(ENV) or None)
        if os.environ.get(STATS_ENV):
            atexit.register(lambda: print('source_cache: %s' % ' '.join(
                '%s=%d' % item for item in sorted(_shared.stats.items())), file=sys.stderr))
    return _shared


def configure(directory=None, memory_text_bytes=MEMORY_TEXT_BYTES):
    """Replace the process-wide cache (used by preland-style callers and tests)."""
    global _shared
    _shared = SourceCache(directory, memory_text_bytes)
    return _shared
