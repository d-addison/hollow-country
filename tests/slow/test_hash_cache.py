"""#194 P3 hash cache: LRU eviction, unique temp names and tests that never touch the user cache.

Synthetic files in temp directories only; offline tests never establish DayZ behaviour.

RED (before the change): PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.slow.test_hash_cache -v
see the commit body for the recorded failing lines.
"""
import ast
import hashlib
import itertools
import os
from pathlib import Path
import re
import tempfile
import time
import unittest
from unittest import mock

from tools.package import hash_cache

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / 'tests'
# #195: the modules that must isolate the cache are discovered, not listed. A unit test module
# reaches hash_cache.cached_sha256 (through snafu_optional's whole-PBO hashing) when its source
# names one of these entry points: verify_install runs the whole-PBO hash of every addon,
# subset_pins and _pbo_sha256 hash a PBO directly, _load_addons hashes while listing addons.
HASHING_HELPERS = ('verify_install', 'subset_pins', '_pbo_sha256', '_load_addons', 'cached_sha256')
ISOLATION_HELPER = 'hash_cache_isolation'
# Sources that name the helpers without being callers: this file and the helper itself.
NOT_CALLERS = ('test_hash_cache', 'hash_cache_isolation')


def _calls_helper(tree):
    """True when the module calls a hashing helper by name, attribute or import alias, or defines a stand-in
    of one that the code under test calls (test_local_test_session's stub installers) (#197)."""
    aliases = set(HASHING_HELPERS)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            aliases.update(a.asname for a in node.names if a.name in HASHING_HELPERS and a.asname)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in HASHING_HELPERS:
            return True
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            if name in aliases:
                return True
    return False


def _isolates(tree):
    """Imports the shared helper, or names HC_HASH_CACHE_DIR in code (not in a comment)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.split('.')[-1] == ISOLATION_HELPER for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and (
                (node.module or '').split('.')[-1] == ISOLATION_HELPER
                or any(a.name == ISOLATION_HELPER for a in node.names)):
            return True
        if isinstance(node, ast.Constant) and node.value == 'HC_HASH_CACHE_DIR':
            return True
    return False


def _tree(path):
    return ast.parse(Path(path).read_text(encoding='utf-8'))


def hashing_modules(unit_dir):
    """Names of the test modules under unit_dir that call a whole-PBO hashing helper (AST, #197)."""
    found = []
    for path in sorted(Path(unit_dir).rglob('test_*.py')):
        if path.stem in NOT_CALLERS:
            continue
        if _calls_helper(_tree(path)):
            found.append(path.relative_to(unit_dir).with_suffix('').as_posix())
    return found


def unisolated(unit_dir):
    """The discovered hashing modules that neither use the shared helper nor set their own cache dir."""
    return [name for name in hashing_modules(unit_dir) if not _isolates(_tree(Path(unit_dir) / (name + '.py')))]


class FakeHome:
    """Replaces Path.home() with a temp dir and reports whether anything was created under it."""

    def __init__(self, testcase):
        self.tmp = tempfile.TemporaryDirectory()
        testcase.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / 'home'
        self.home.mkdir()
        patcher = mock.patch.object(Path, 'home', classmethod(lambda cls: self.home))
        patcher.start()
        testcase.addCleanup(patcher.stop)

    def touched(self):
        return sorted(p.relative_to(self.home).as_posix() for p in self.home.rglob('*'))


class CacheCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.cache = self.root / 'cache'
        self.fake_home = FakeHome(self)
        env = mock.patch.dict(os.environ, {'HC_HASH_CACHE_DIR': str(self.cache)})
        env.start()
        self.addCleanup(env.stop)
        self.clock = itertools.count(10 ** 15, 10 ** 10)  # explicit synthetic clock, 10 s per use
        clock = mock.patch.object(hash_cache, '_now_ns', lambda: next(self.clock))
        clock.start()
        self.addCleanup(clock.stop)

    def old_file(self, name, data):
        path = self.root / name
        path.write_bytes(data)
        os.utime(path, ns=(10 ** 9, 10 ** 9))  # outside the racy-write window
        return path

    def entries(self):
        return hash_cache._load(self.cache)


class LeastRecentlyUsedEviction(CacheCase):
    def test_eviction_drops_the_least_recently_used_entry_not_the_oldest_inserted(self):
        first = self.old_file('a.pbo', b'a')
        second = self.old_file('b.pbo', b'b')
        third = self.old_file('c.pbo', b'c')
        with mock.patch.object(hash_cache, 'MAX_ENTRIES', 2), mock.patch.object(hash_cache, 'USE_REFRESH_NS', 0):
            hash_cache.cached_sha256(first)   # inserted first
            hash_cache.cached_sha256(second)
            hash_cache.cached_sha256(first)   # ... but used again after the second
            hash_cache.cached_sha256(third)   # over the cap: the least recently used goes
        self.assertEqual({str(first.absolute()), str(third.absolute())}, set(self.entries()))
        self.assertEqual([], [p for p in self.fake_home.touched()], 'the user cache must stay untouched')

    def test_a_hit_inside_the_refresh_interval_does_not_rewrite_the_cache(self):
        path = self.old_file('a.pbo', b'a')
        hash_cache.cached_sha256(path)
        stamp = (self.cache / hash_cache.CACHE_FILE).stat().st_mtime_ns
        with mock.patch.object(hash_cache, 'USE_REFRESH_NS', 10 ** 18):
            for _ in range(3):
                hash_cache.cached_sha256(path)
        self.assertEqual(stamp, (self.cache / hash_cache.CACHE_FILE).stat().st_mtime_ns)

    def test_the_cap_is_kept_for_legacy_rows_without_a_use_stamp(self):
        files = [self.old_file('f%d.pbo' % i, bytes([i])) for i in range(4)]
        legacy = {str(p.absolute()): {'size': 1, 'mtime_ns': 1, 'sha256': '0' * 64} for p in files[:3]}
        hash_cache._store(self.cache, legacy)
        with mock.patch.object(hash_cache, 'MAX_ENTRIES', 3):
            hash_cache.cached_sha256(files[3])
        kept = set(self.entries())
        self.assertEqual(3, len(kept))
        self.assertIn(str(files[3].absolute()), kept)  # the fresh use survives; legacy rows go first


class FutureUseStamp(CacheCase):
    def test_a_future_use_stamp_is_clamped_to_now_so_the_row_can_age_out(self):
        path = self.old_file('a.pbo', b'a')
        digest = hashlib.sha256(b'a').hexdigest()
        st = path.stat()
        row = {'size': st.st_size, 'mtime_ns': st.st_mtime_ns, 'sha256': digest, 'used': 10 ** 21}
        hash_cache._store(self.cache, {str(path.absolute()): row})
        loaded = self.entries()[str(path.absolute())]
        self.assertLessEqual(loaded['used'], 10 ** 16)  # clamped on read; the synthetic clock is ~1e15
        with mock.patch.object(hash_cache, 'USE_REFRESH_NS', 1):
            self.assertEqual(digest, hash_cache.cached_sha256(path))
        self.assertLessEqual(self.entries()[str(path.absolute())]['used'], 10 ** 16)

    def test_a_future_stamp_does_not_outlive_fresh_rows_at_the_cap(self):
        files = [self.old_file('g%d.pbo' % i, bytes([i])) for i in range(3)]
        legacy = {str(files[0].absolute()): {'size': 1, 'mtime_ns': 1, 'sha256': '0' * 64, 'used': 10 ** 21}}
        hash_cache._store(self.cache, legacy)
        with mock.patch.object(hash_cache, 'MAX_ENTRIES', 2):
            hash_cache.cached_sha256(files[1])
            hash_cache.cached_sha256(files[2])
        self.assertNotIn(str(files[0].absolute()), set(self.entries()))


class OrphanTempSweep(CacheCase):
    def temp(self, name, mtime_ns):
        self.cache.mkdir(parents=True, exist_ok=True)
        path = self.cache / name
        path.write_text('{}')
        os.utime(path, ns=(mtime_ns, mtime_ns))
        return path

    def test_a_write_removes_old_orphan_temp_files_and_keeps_young_ones(self):
        now = 10 ** 15
        old = self.temp('%s.4242.%s.tmp' % (hash_cache.CACHE_FILE, 'a' * 16), now - hash_cache.ORPHAN_TEMP_AGE_NS - 10 ** 12)
        young = self.temp('%s.4243.%s.tmp' % (hash_cache.CACHE_FILE, 'b' * 16), now - 10 ** 9)
        other = self.temp('notes.tmp', 1)  # not a cache temp name: never touched
        cache_like = self.temp('other-cache.json.1.%s.tmp' % ('c' * 16), 1)
        hash_cache._store(self.cache, {})
        names = sorted(p.name for p in self.cache.iterdir())
        self.assertNotIn(old.name, names)
        self.assertIn(young.name, names)
        self.assertIn(other.name, names)
        self.assertIn(cache_like.name, names)
        self.assertIn(hash_cache.CACHE_FILE, names)

    def test_the_age_is_a_named_one_hour_constant(self):
        self.assertEqual(3600 * 10 ** 9, hash_cache.ORPHAN_TEMP_AGE_NS)

    def test_a_directory_with_a_temp_name_does_not_break_the_write(self):
        self.cache.mkdir(parents=True, exist_ok=True)
        (self.cache / ('%s.1.%s.tmp' % (hash_cache.CACHE_FILE, 'd' * 16))).mkdir()
        hash_cache._store(self.cache, {})
        self.assertTrue((self.cache / hash_cache.CACHE_FILE).is_file())


class ConcurrentWritersMerge(CacheCase):
    """#196: before the atomic replace the writer re-reads the file and merges, so two builds that each
    added a different key both survive under the OS-held merge lock."""

    row = staticmethod(lambda ch, used=1: {'size': 1, 'mtime_ns': 1, 'sha256': ch * 64, 'used': used})

    def test_two_writers_that_each_add_a_different_key_both_survive(self):
        first = self.entries()  # both writers loaded the same (empty) state
        second = self.entries()
        first['/a'] = self.row('a')
        second['/b'] = self.row('b')
        hash_cache._store(self.cache, first)
        hash_cache._store(self.cache, second)
        self.assertEqual({'/a', '/b'}, set(self.entries()))
        self.assertEqual([hash_cache.CACHE_FILE, hash_cache.LOCK_FILE], sorted(p.name for p in self.cache.iterdir()))

    def test_the_newer_use_stamp_wins_per_key_whichever_writer_holds_it(self):
        hash_cache._store(self.cache, {'/k': self.row('a', used=500)})
        hash_cache._store(self.cache, {'/k': self.row('b', used=100)})  # an older stale copy must not win
        self.assertEqual('a' * 64, self.entries()['/k']['sha256'])
        hash_cache._store(self.cache, {'/k': self.row('c', used=900)})
        self.assertEqual('c' * 64, self.entries()['/k']['sha256'])
        hash_cache._store(self.cache, {'/k': self.row('d', used=900)})  # a tie goes to the writer in hand
        self.assertEqual('d' * 64, self.entries()['/k']['sha256'])

    def test_the_cap_is_kept_over_the_merged_rows_least_recently_used_first(self):
        hash_cache._store(self.cache, {'/old': self.row('a', used=10), '/mid': self.row('b', used=20)})
        with mock.patch.object(hash_cache, 'MAX_ENTRIES', 2):
            hash_cache._store(self.cache, {'/new': self.row('c', used=30)})
        self.assertEqual({'/mid', '/new'}, set(self.entries()))

    def test_a_corrupt_file_on_disk_does_not_stop_the_write(self):
        self.cache.mkdir()
        (self.cache / hash_cache.CACHE_FILE).write_text('{not json', encoding='utf-8')
        hash_cache._store(self.cache, {'/a': self.row('a')})
        self.assertEqual({'/a'}, set(self.entries()))

    def test_the_module_says_merge_not_last_writer_wins(self):
        self.assertNotIn('last writer wins', hash_cache.__doc__.lower())
        self.assertIn('merge', hash_cache.__doc__.lower())


class FutureStampIsPersistedClamped(CacheCase):
    def test_the_next_write_persists_a_clamped_future_stamp_for_a_row_it_did_not_touch(self):
        import json
        self.cache.mkdir()
        future = {'size': 1, 'mtime_ns': 1, 'sha256': 'e' * 64, 'used': 10 ** 21}
        (self.cache / hash_cache.CACHE_FILE).write_text(
            json.dumps({'schema': hash_cache.CACHE_SCHEMA, 'entries': {'/future': future}}), encoding='utf-8')
        path = self.old_file('a.pbo', b'a')
        hash_cache.cached_sha256(path)  # a different key; this write must persist the clamp
        raw = json.loads((self.cache / hash_cache.CACHE_FILE).read_text(encoding='utf-8'))
        self.assertLessEqual(raw['entries']['/future']['used'], 10 ** 16)  # on disk, not just in memory


CTIME_RETRIES = 50  # bounded: 50 rewrites, 10 ms apart, is half a second at most
CTIME_PAUSE_SECONDS = 0.01


def rewrite_until_ctime_moves(path, rewrite, retries=CTIME_RETRIES, pause=CTIME_PAUSE_SECONDS):
    """Run `rewrite()` until `path` reports a different st_ctime_ns, retrying a bounded number of times.

    Returns the number of rewrites it took. Raises unittest.SkipTest, naming the reason, when the
    filesystem never advances ctime (a coarse-timestamp filesystem), because then the same-stat
    rewrite scenario cannot be produced and the test would prove nothing."""
    before = path.stat().st_ctime_ns
    for attempt in range(1, retries + 1):
        rewrite()
        if path.stat().st_ctime_ns != before:
            return attempt
        time.sleep(pause)
    raise unittest.SkipTest('filesystem_ctime_not_advancing: st_ctime_ns unchanged after %d rewrites' % retries)


class CtimeRetryHelper(unittest.TestCase):
    class Stat:
        def __init__(self, ticks):
            self.ticks, self.calls, self.writes = ticks, 0, 0

        def stat(self):
            self.calls += 1
            return type('S', (), {'st_ctime_ns': self.ticks.get(self.writes, 0)})()

        def write(self):
            self.writes += 1

    def test_it_returns_once_ctime_moves_even_when_the_first_rewrite_lands_in_the_same_tick(self):
        fake = self.Stat({3: 1})  # the ctime only advances on the third rewrite
        self.assertEqual(3, rewrite_until_ctime_moves(fake, fake.write, pause=0))
        self.assertEqual(3, fake.writes)

    def test_it_skips_with_a_named_reason_when_ctime_never_advances(self):
        fake = self.Stat({})
        with self.assertRaises(unittest.SkipTest) as caught:
            rewrite_until_ctime_moves(fake, fake.write, retries=4, pause=0)
        self.assertIn('filesystem_ctime_not_advancing', str(caught.exception))
        self.assertEqual(4, fake.writes)  # bounded


class RewrittenFileKeepsItsStamp(CacheCase):
    def test_a_rewrite_with_the_same_size_and_restored_mtime_is_not_served_from_cache(self):
        path = self.old_file('a.pbo', b'aaaa')
        first = hash_cache.cached_sha256(path)
        self.assertEqual(hashlib.sha256(b'aaaa').hexdigest(), first)
        self.assertIn(str(path.absolute()), self.entries())  # it was cached (outside the racy window)
        def rewrite():
            path.write_bytes(b'bbbb')
            os.utime(path, ns=(10 ** 9, 10 ** 9))  # same size, same mtime_ns as before
        rewrite_until_ctime_moves(path, rewrite)  # skips, named, if this filesystem has coarse ctime
        self.assertEqual(hashlib.sha256(b'bbbb').hexdigest(), hash_cache.cached_sha256(path))

    def test_a_replaced_file_with_the_same_size_and_mtime_is_rehashed(self):
        path = self.old_file('a.pbo', b'aaaa')
        hash_cache.cached_sha256(path)
        time.sleep(0.05)
        other = self.root / 'new.pbo'
        other.write_bytes(b'cccc')
        os.utime(other, ns=(10 ** 9, 10 ** 9))
        os.replace(other, path)  # a new inode behind the same path
        self.assertEqual(hashlib.sha256(b'cccc').hexdigest(), hash_cache.cached_sha256(path))

    def test_the_row_records_inode_and_ctime_where_the_platform_gives_them(self):
        path = self.old_file('a.pbo', b'aaaa')
        hash_cache.cached_sha256(path)
        row = self.entries()[str(path.absolute())]
        st = path.stat()
        self.assertEqual(st.st_ino, row['ino'])
        self.assertEqual(st.st_ctime_ns, row['ctime_ns'])

    def test_a_row_without_the_new_fields_is_rehashed_once_then_cached_with_them(self):
        path = self.old_file('a.pbo', b'aaaa')
        st = path.stat()
        old = {'size': st.st_size, 'mtime_ns': st.st_mtime_ns, 'sha256': 'f' * 64, 'used': 1}
        hash_cache._store(self.cache, {str(path.absolute()): old})
        self.assertEqual(hashlib.sha256(b'aaaa').hexdigest(), hash_cache.cached_sha256(path))
        self.assertIn('ino', self.entries()[str(path.absolute())])


class UniqueTempFile(CacheCase):
    def test_every_write_uses_its_own_temp_name_and_leaves_none_behind(self):
        names = []
        real_replace = os.replace

        def spy(source, target):
            names.append(Path(source).name)
            return real_replace(source, target)
        with mock.patch.object(os, 'replace', spy):
            hash_cache._store(self.cache, {})
            hash_cache._store(self.cache, {})
        self.assertEqual(2, len(set(names)), names)
        for name in names:
            self.assertRegex(name, r'^%s\.%d\.[0-9a-f]{8,}\.tmp$' % (re.escape(hash_cache.CACHE_FILE), os.getpid()))
        self.assertEqual([hash_cache.CACHE_FILE, hash_cache.LOCK_FILE], sorted(p.name for p in self.cache.iterdir()))

    def test_a_failed_replace_cleans_its_temp_file_and_is_not_fatal(self):
        with mock.patch.object(os, 'replace', side_effect=OSError('synthetic')):
            hash_cache._store(self.cache, {})
        self.assertEqual([hash_cache.LOCK_FILE], sorted(p.name for p in self.cache.iterdir()))

    def test_two_writers_never_share_a_temp_path(self):
        seen = []
        real_write = Path.write_text

        def spy(path, *args, **kwargs):
            seen.append(path.name)
            return real_write(path, *args, **kwargs)
        with mock.patch.object(Path, 'write_text', spy):
            hash_cache._store(self.cache, {})
            hash_cache._store(self.cache, {})
        self.assertEqual(len(seen), len(set(seen)))


class UserCacheIsolation(unittest.TestCase):
    def test_a_default_directory_lookup_lands_under_home_and_the_guard_sees_it(self):
        fake = FakeHome(self)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('HC_HASH_CACHE_DIR', None)
            path = Path(tempfile.mkdtemp()) / 'a.pbo'
            self.addCleanup(lambda: path.unlink(missing_ok=True))
            path.write_bytes(b'x')
            os.utime(path, ns=(10 ** 9, 10 ** 9))
            hash_cache.cached_sha256(path)
        self.assertIn('.cache/hollow-country/pbo-hash/' + hash_cache.CACHE_FILE, fake.touched())

    def test_with_the_override_set_the_user_cache_is_not_touched(self):
        fake = FakeHome(self)
        with tempfile.TemporaryDirectory() as t:
            cache = Path(t) / 'cache'
            path = Path(t) / 'a.pbo'
            path.write_bytes(b'x')
            os.utime(path, ns=(10 ** 9, 10 ** 9))
            with mock.patch.dict(os.environ, {'HC_HASH_CACHE_DIR': str(cache)}):
                hash_cache.cached_sha256(path)
            self.assertTrue((cache / hash_cache.CACHE_FILE).is_file())
        self.assertEqual([], fake.touched())

    def test_every_module_that_reaches_the_cache_isolates_it(self):
        # Discovered (#195): every module that names a whole-PBO hashing helper must use the shared
        # helper (or its own HC_HASH_CACHE_DIR), else it reads and writes the user's cache.
        found = hashing_modules(TESTS)
        self.assertTrue(found, 'discover callers across the current test groups')
        self.assertEqual([], unisolated(TESTS))

    def test_a_new_unisolated_caller_is_found_and_fails_the_check(self):
        with tempfile.TemporaryDirectory() as t:
            unit = Path(t)
            (unit / 'test_new_caller.py').write_text('from tools.package import snafu_optional\n'
                                                     'snafu_optional.verify_install(1, 2)\n')
            (unit / 'test_isolated_caller.py').write_text('import hash_cache_isolation\nverify_install()\n')
            (unit / 'test_own_dir.py').write_text("os.environ['HC_HASH_CACHE_DIR'] = 'x'\n_pbo_sha256(p)\n")
            (unit / 'test_unrelated.py').write_text('import unittest\n')
            self.assertEqual(['test_isolated_caller', 'test_new_caller', 'test_own_dir'], hashing_modules(unit))
            self.assertEqual(['test_new_caller'], unisolated(unit))

    def test_the_isolation_helper_redirects_the_cache_and_restores_the_environment(self):
        from tests.unit import hash_cache_isolation
        before = os.environ.get('HC_HASH_CACHE_DIR')
        hash_cache_isolation.enter()
        try:
            override = os.environ['HC_HASH_CACHE_DIR']
            self.assertTrue(Path(override).is_dir())
            self.assertNotEqual(Path.home() / '.cache' / 'hollow-country' / 'pbo-hash', Path(override))
        finally:
            hash_cache_isolation.leave()
        self.assertEqual(before, os.environ.get('HC_HASH_CACHE_DIR'))
        self.assertFalse(Path(override).exists())


# #197: a child process that widens the gap between the merge re-read and the replace, so an unserialized
# write would almost always drop another writer's rows.
CHILD = """
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from tools.package import hash_cache
real = hash_cache._merge
def slow(directory, entries):
    merged = real(directory, entries)
    time.sleep(0.03)
    return merged
hash_cache._merge = slow
for i in range(int(sys.argv[4])):
    key = '/synthetic/%s/%d.pbo' % (sys.argv[3], i)
    row = {'size': 1, 'mtime_ns': 1, 'ino': 0, 'ctime_ns': 0, 'sha256': '0' * 64, 'used': 10 ** 9 + i}
    hash_cache._store(Path(sys.argv[2]), {key: row})
"""


class SerializedMerge(unittest.TestCase):
    def test_concurrent_writers_keep_every_row(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as t:
            cache = Path(t) / 'cache'
            procs = [subprocess.Popen([sys.executable, '-B', '-c', CHILD, str(ROOT), str(cache), 'w%d' % n, '5'])
                     for n in range(4)]
            for proc in procs:
                self.assertEqual(0, proc.wait(timeout=60))
            rows = hash_cache._load(cache)
            self.assertEqual(20, len(rows), 'every writer keeps its rows under contention')
            descriptor = hash_cache._acquire(cache)
            self.assertIsNotNone(descriptor, 'all writers released ownership')
            os.close(descriptor)

    def holder(self, cache):
        import subprocess
        import sys
        from concurrent.futures import ThreadPoolExecutor
        code = """
import sys
from pathlib import Path
from tools.package import hash_cache
fd = hash_cache._acquire(Path(sys.argv[1]))
assert fd is not None
print('locked', flush=True)
sys.stdin.read()
"""
        proc = subprocess.Popen([sys.executable, '-B', '-c', code, str(cache)],
                                cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        def cleanup():
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=10)
            proc.stdin.close()
            proc.stdout.close()
        self.addCleanup(cleanup)
        with ThreadPoolExecutor() as pool:
            ready = pool.submit(proc.stdout.readline)
            try:
                self.assertEqual('locked\n', ready.result(timeout=10))
            except BaseException:
                proc.kill()
                raise
        return proc

    def test_a_foreign_os_lock_skips_the_store_without_failing(self):
        with tempfile.TemporaryDirectory() as t:
            cache = Path(t)
            proc = self.holder(cache)
            lock = cache / hash_cache.LOCK_FILE
            # Even an old timestamp never permits stealing live ownership.
            os.utime(lock, ns=(1, 1))
            inode = lock.stat().st_ino
            with mock.patch.object(hash_cache, 'LOCK_WAIT_NS', 50 * 10 ** 6):
                hash_cache._store(cache, {'k': {'sha256': '0' * 64, 'used': 1}})
            self.assertEqual({}, hash_cache._load(cache))
            self.assertIsNone(proc.poll(), 'the other build is still alive')
            self.assertEqual(inode, lock.stat().st_ino, 'contenders must keep the same lock inode')
            proc.stdin.close()
            self.assertEqual(0, proc.wait(timeout=10))
            hash_cache._store(cache, {'k': {'sha256': '0' * 64, 'used': 1}})
            self.assertIn('k', hash_cache._load(cache), 'normal exit releases ownership')

    def test_a_killed_build_releases_ownership_without_unlinking(self):
        with tempfile.TemporaryDirectory() as t:
            cache = Path(t)
            proc = self.holder(cache)
            lock = cache / hash_cache.LOCK_FILE
            inode = lock.stat().st_ino
            proc.kill()
            proc.wait(timeout=10)
            hash_cache._store(cache, {'k': {'sha256': '0' * 64, 'used': 1}})
            self.assertIn('k', hash_cache._load(cache))
            self.assertEqual(inode, lock.stat().st_ino)


class CallerDiscovery(unittest.TestCase):
    def test_aliased_and_attribute_calls_are_callers_but_mentions_are_not(self):
        with tempfile.TemporaryDirectory() as t:
            unit = Path(t)
            (unit / 'test_alias.py').write_text('from tools.package.snafu_optional import verify_install as vi\nvi(1)\n')
            (unit / 'test_module_alias.py').write_text('import tools.package.hash_cache as hc\nhc.cached_sha256(p)\n')
            (unit / 'test_string_only.py').write_text("NAME = 'verify_install'\n# _pbo_sha256 is not called here\n")
            (unit / 'test_patch_only.py').write_text("mock.patch.object(x, 'subset_pins')\n")
            (unit / 'test_stub.py').write_text('class Fake:\n    def verify_install(self, install):\n        pass\n')
            self.assertEqual(['test_alias', 'test_module_alias', 'test_stub'], hashing_modules(unit))
            self.assertEqual(['test_alias', 'test_module_alias', 'test_stub'], unisolated(unit))
            (unit / 'test_comment_isolation.py').write_text('# hash_cache_isolation\nverify_install()\n')
            self.assertIn('test_comment_isolation', unisolated(unit), 'a comment is not isolation')


if __name__ == '__main__':
    unittest.main()
