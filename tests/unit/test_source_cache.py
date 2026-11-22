"""The shared parsed-source cache: hits, disk reuse, invalidation and identical parse results."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.validate import enforce_rules_readiness as readiness, enforce_source as es, source_cache

TEXT = 'class HCThing\n{\n    int m_Value = 3;\n    void Run()\n    {\n    }\n}\n'


def build_counter(path, text, **kwargs):
    calls = []

    def build():
        calls.append(1)
        return es.Source(path, text, **kwargs)
    return build, calls


class MemoryCache(unittest.TestCase):
    def test_equal_inputs_share_one_parse_and_changed_text_reparses(self):
        cache = source_cache.SourceCache()
        build, calls = build_counter('a/x.c', TEXT)
        first = cache.get(build, 'a/x.c', TEXT)
        self.assertIs(first, cache.get(build, 'a/x.c', TEXT))
        self.assertEqual(1, len(calls))
        changed = TEXT.replace('3', '4')
        build, calls = build_counter('a/x.c', changed)
        self.assertIsNot(first, cache.get(build, 'a/x.c', changed))
        self.assertEqual(1, len(calls))
        self.assertEqual(dict(memory=1, disk=0, parsed=2, stored=0), cache.stats)

    def test_path_root_and_mod_are_part_of_the_key(self):
        cache = source_cache.SourceCache()
        keys = [dict(), dict(root='a'), dict(mod='m')]
        sources = [cache.get(build_counter('a/x.c', TEXT, **k)[0], 'a/x.c', TEXT, **k) for k in keys]
        self.assertEqual(3, len({id(s) for s in sources}))
        self.assertEqual('m', sources[2].mod)

    def test_memory_budget_evicts_oldest_and_skips_oversized_text(self):
        cache = source_cache.SourceCache(memory_text_bytes=len(TEXT) * 2)
        for name in ('a', 'b', 'c'):
            cache.get(build_counter(name + '.c', TEXT)[0], name + '.c', TEXT)
        self.assertEqual(2, len(cache.entries))
        self.assertLessEqual(cache.text_bytes, len(TEXT) * 2)
        big = TEXT * 4
        cache.get(build_counter('big.c', big)[0], 'big.c', big)
        self.assertNotIn('big.c', [key[0] for key in cache.entries])


class DiskCache(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'cache'

    def fetch(self, text=TEXT, stat=(len(TEXT), 7), path='a/x.c'):
        cache = source_cache.SourceCache(self.directory)
        build, calls = build_counter(path, text)
        return cache.get(build, path, text, stat=stat, persist=True), calls, cache

    def test_second_process_loads_from_disk_without_parsing(self):
        first, calls, cache = self.fetch()
        self.assertEqual(([1], 1), (calls, cache.stats['stored']))
        second, calls, cache = self.fetch()
        self.assertEqual([], calls)
        self.assertEqual(1, cache.stats['disk'])
        self.assertEqual((first.rel, first.text, first.code), (second.rel, second.text, second.code))
        self.assertEqual([c.name for c in first.classes], [c.name for c in second.classes])
        self.assertEqual(['HCThing.Run'], [m.owner.name + '.' + m.name for m in second.methods])

    def test_stat_or_text_change_misses_and_replaces_the_entry(self):
        self.fetch()
        for kwargs in (dict(stat=(len(TEXT), 8)), dict(text=TEXT.replace('3', '4'), stat=(len(TEXT), 7))):
            with self.subTest(kwargs=kwargs):
                _, calls, _ = self.fetch(**kwargs)
                self.assertEqual([1], calls)
        _, calls, _ = self.fetch(text=TEXT.replace('3', '4'), stat=(len(TEXT), 7))
        self.assertEqual([], calls)
        self.assertEqual(1, len(list(next(self.directory.iterdir()).glob('*.pkl'))))

    def test_damaged_entry_falls_back_to_a_parse(self):
        self.fetch()
        for entry in next(self.directory.iterdir()).glob('*.pkl'):
            entry.write_bytes(b'not a pickle')
        source, calls, _ = self.fetch()
        self.assertEqual([1], calls)
        self.assertEqual('HCThing', source.classes[0].name)

    def test_text_only_inputs_never_touch_the_disk(self):
        cache = source_cache.SourceCache(self.directory)
        cache.get(build_counter('a/x.c', TEXT)[0], 'a/x.c', TEXT, persist=True)
        self.assertEqual(0, cache.stats['stored'])

    def test_older_fingerprint_directories_are_removed(self):
        old = self.directory / 'v0123456789abcdef'
        keep = self.directory / 'other'
        old.mkdir(parents=True)
        keep.mkdir()
        self.fetch()
        self.assertFalse(old.exists())
        self.assertTrue(keep.exists())

    def test_unusable_directory_is_only_a_slower_run(self):
        blocked = Path(self.temp.name) / 'file'
        blocked.write_text('x')
        cache = source_cache.SourceCache(blocked / 'cache')
        source = cache.get(build_counter('a/x.c', TEXT)[0], 'a/x.c', TEXT, stat=(1, 1), persist=True)
        self.assertEqual('HCThing', source.classes[0].name)


class EnforceSourceIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        scripts = self.root / 'mods' / 'HollowCountry' / 'scripts' / '4_World'
        scripts.mkdir(parents=True)
        (scripts / 'a.c').write_bytes(TEXT.replace('\n', '\r\n').encode())
        (scripts / 'b.c').write_text(TEXT.replace('HCThing', 'HCOther'))
        self.addCleanup(source_cache.configure, None)
        source_cache.configure(self.root / 'cache')

    def test_mod_sources_match_the_uncached_parse_and_are_reused(self):
        cached = es.mod_sources(self.root)
        self.assertEqual(['HCThing', 'HCOther'], [s.classes[0].name for s in cached])
        for source in cached:
            plain = es.Source(source.path, source.path.read_text(encoding='utf-8', errors='replace'),
                              self.root, 'HollowCountry')
            self.assertEqual((plain.rel, plain.text, plain.code, plain.layer), (source.rel, source.text, source.code, source.layer))
            self.assertEqual([(c.name, c.offset, [f.name for f in c.fields], [m.name for m in c.methods])
                              for c in plain.classes],
                             [(c.name, c.offset, [f.name for f in c.fields], [m.name for m in c.methods])
                              for c in source.classes])
        self.assertNotIn('\r', cached[0].text)
        again = es.mod_sources(self.root)
        self.assertTrue(all(a is b for a, b in zip(cached, again)))

    def test_a_new_process_view_reads_from_disk_and_an_edit_reparses(self):
        es.mod_sources(self.root)
        cache = source_cache.configure(self.root / 'cache')
        with patch.object(es.Source, '_parse', side_effect=AssertionError('parsed again')):
            es.mod_sources(self.root)
        self.assertEqual(dict(memory=0, disk=2, parsed=0, stored=0), cache.stats)
        path = self.root / 'mods' / 'HollowCountry' / 'scripts' / '4_World' / 'b.c'
        path.write_text(TEXT.replace('HCThing', 'HCEdited'))
        self.assertEqual(['HCThing', 'HCEdited'], [s.classes[0].name for s in es.mod_sources(self.root)])

    def test_read_source_passes_a_parsed_source_through(self):
        source = es.mod_sources(self.root)[0]
        self.assertIs(source, es.read_source(source))

    def test_readiness_reuses_parsed_sources_and_matches_text_input(self):
        text = 'class HCModule {}\nclass HCUnnamed : HCModule {}\nclass HCServer { void Go() { Register(new HCUnnamed()); } }\n'
        by_text = readiness.module_readiness({'a.c': text})
        self.assertEqual(['HCUnnamed'], [row.symbol for row in by_text])
        with patch.object(es.Source, '_parse', side_effect=AssertionError('parsed again')):
            self.assertEqual(by_text, readiness.module_readiness({'a.c': es.parse(Path('a.c'), text)}))
        text = 'class HCThing { int Queue; }\n'
        source = es.parse(Path('b.c'), text)
        self.assertEqual(readiness.engine_type_names(text, 'b.c'), readiness.engine_type_names(source, 'b.c'))
        self.assertEqual(1, len(readiness.engine_type_names(source, 'b.c')))


if __name__ == '__main__':
    unittest.main()
