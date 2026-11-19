"""#194 P3 hash cache: LRU eviction, unique temp names and tests that never touch the user cache.

Synthetic files in temp directories only; offline tests never establish DayZ behaviour.

RED (before the change): PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hash_cache -v
see the commit body for the recorded failing lines.
"""
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
UNIT = ROOT / 'tests' / 'unit'
# #195: the modules that must isolate the cache are discovered, not listed. A unit test module
# reaches hash_cache.cached_sha256 (through snafu_optional's whole-PBO hashing) when its source
# names one of these entry points: verify_install runs the whole-PBO hash of every addon,
# subset_pins and _pbo_sha256 hash a PBO directly, _load_addons hashes while listing addons.
HASHING_HELPERS = ('verify_install', 'subset_pins', '_pbo_sha256', '_load_addons', 'cached_sha256')
HELPER_PATTERN = re.compile(r'\b(?:%s)\b' % '|'.join(HASHING_HELPERS))
ISOLATION_HELPER = 'hash_cache_isolation'
# Sources that name the helpers without being callers: this file and the helper itself.
NOT_CALLERS = ('test_hash_cache', 'hash_cache_isolation')


def hashing_modules(unit_dir):
    """Names of the test modules under unit_dir whose source names a whole-PBO hashing helper."""
    found = []
    for path in sorted(Path(unit_dir).glob('*.py')):
        if path.stem in NOT_CALLERS:
            continue
        if HELPER_PATTERN.search(path.read_text(encoding='utf-8')):
            found.append(path.stem)
    return found


def unisolated(unit_dir):
    """The discovered hashing modules that neither use the shared helper nor set their own cache dir."""
    bad = []
    for name in hashing_modules(unit_dir):
        text = (Path(unit_dir) / (name + '.py')).read_text(encoding='utf-8')
        if ISOLATION_HELPER not in text and 'HC_HASH_CACHE_DIR' not in text:
            bad.append(name)
    return bad


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


class LastWriterWins(CacheCase):
    def test_interleaved_writers_leave_one_valid_file_and_the_last_write_wins(self):
        self.assertIn('last writer wins', hash_cache.__doc__.lower())
        row = lambda ch: {'size': 1, 'mtime_ns': 1, 'sha256': ch * 64, 'used': 1}
        first = self.entries()  # both writers loaded the same (empty) state
        second = self.entries()
        first['/a'] = row('a')
        second['/b'] = row('b')
        hash_cache._store(self.cache, first)
        hash_cache._store(self.cache, second)
        self.assertEqual({'/b'}, set(self.entries()))  # the first writer's row is lost, never corrupted
        self.assertEqual([hash_cache.CACHE_FILE], sorted(p.name for p in self.cache.iterdir()))


class RewrittenFileKeepsItsStamp(CacheCase):
    def test_a_rewrite_with_the_same_size_and_restored_mtime_is_not_served_from_cache(self):
        path = self.old_file('a.pbo', b'aaaa')
        first = hash_cache.cached_sha256(path)
        self.assertEqual(hashlib.sha256(b'aaaa').hexdigest(), first)
        self.assertIn(str(path.absolute()), self.entries())  # it was cached (outside the racy window)
        time.sleep(0.05)  # ctime ticks are coarse; the rewrite must land in a later one
        path.write_bytes(b'bbbb')
        os.utime(path, ns=(10 ** 9, 10 ** 9))  # same size, same mtime_ns as before
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
        self.assertEqual([hash_cache.CACHE_FILE], sorted(p.name for p in self.cache.iterdir()))

    def test_a_failed_replace_cleans_its_temp_file_and_is_not_fatal(self):
        with mock.patch.object(os, 'replace', side_effect=OSError('synthetic')):
            hash_cache._store(self.cache, {})
        self.assertEqual([], sorted(p.name for p in self.cache.iterdir()))

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
        found = hashing_modules(UNIT)
        # The scan is not vacuous: the modules found by spying cached_sha256 in #194 are still found.
        for known in ('test_snafu_optional', 'test_tactical_flava_optional', 'test_local_test_session',
                      'test_optional_subset_pins'):
            self.assertIn(known, found)
        self.assertEqual([], unisolated(UNIT))

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


if __name__ == '__main__':
    unittest.main()
