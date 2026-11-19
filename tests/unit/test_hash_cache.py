"""#194 P3 hash cache: LRU eviction, unique temp names and tests that never touch the user cache.

Synthetic files in temp directories only; offline tests never establish DayZ behaviour.

RED (before the change): PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hash_cache -v
see the commit body for the recorded failing lines.
"""
import itertools
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from tools.package import hash_cache

ROOT = Path(__file__).resolve().parents[2]
UNIT = ROOT / 'tests' / 'unit'
# Test modules whose code paths reach hash_cache.cached_sha256 through snafu_optional's
# whole-PBO hashing (found by spying cached_sha256 with HC_HASH_CACHE_DIR unset, #194).
REACHING = ('test_hc_optional_gear', 'test_local_test_session', 'test_optional_ce_composition',
            'test_optional_gun_scale', 'test_optional_subset_pins', 'test_snafu_optional',
            'test_tactical_flava_optional')
ISOLATION_HELPER = 'hash_cache_isolation'


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
        # Each of these runs snafu_optional's whole-PBO hashing; without the shared helper
        # (or its own HC_HASH_CACHE_DIR) they would read and write the user's cache.
        for name in REACHING:
            text = (UNIT / (name + '.py')).read_text()
            self.assertTrue(ISOLATION_HELPER in text or 'HC_HASH_CACHE_DIR' in text, name)

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
