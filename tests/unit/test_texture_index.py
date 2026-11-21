"""Small generated PBO tables; no installed assets or tools required."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.package.pbo import WORDS, VERS, PREFIX
from tools.validate import texture_index as index


def archive(entries, prefix='dz\\ui', compressed=False):
    properties = b'' if prefix is None else b'\0' + WORDS.pack(VERS, 0, 0, 0, 0) + b'prefix\0' + prefix.encode() + b'\0\0'
    table = b''.join(name.encode() + b'\0' + WORDS.pack(0x43707273 if compressed else 0, len(data), 0, 0, len(data))
                     for name, data in entries)
    return properties + table + b'\0' + WORDS.pack(0, 0, 0, 0, 0) + b''.join(data for _, data in entries)


class TextureIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cache_root = patch.object(index, 'DEFAULT_CACHE', self.root / 'cache/index.json')
        self.cache_root.start()
        self.addCleanup(self.cache_root.stop)

    def test_names_only_and_compressed_entries(self):
        path = self.root / 'ui.pbo'
        entry = ('Data/Icon.PAA', b'private-content')
        path.write_bytes(archive([entry], compressed=True))
        names, fallback = index.pbo_names(path)
        self.assertEqual({index.canonical('dz/ui/' + entry[0])}, names)
        self.assertFalse(fallback)

    def test_no_prefix_fallback_is_explicit(self):
        path = self.root / 'legacy.pbo'
        path.write_bytes(archive([('x.paa', b'')], prefix=None))
        self.assertEqual(({'legacy/x.paa'}, True), index.pbo_names(path))

    def test_truncation_and_traversal_are_rejected(self):
        path = self.root / 'bad.pbo'
        for blob in (b'x', b'\0', archive([('../x.paa', b'')]), archive([('x.paa', b'123')])[:-2]):
            path.write_bytes(blob)
            with self.assertRaises(ValueError):
                index.pbo_names(path)

    def test_cache_roundtrip_never_contains_payload_or_install_path(self):
        addons = self.root / 'addons'
        addons.mkdir()
        payload = b'do-not-store-asset-data'
        (addons / 'ui.pbo').write_bytes(archive([('icon.paa', payload)]))
        cache = self.root / 'cache/index.json'
        data = index.build_index([addons], cache)
        self.assertEqual(set(data['names']), index.load_index(cache))
        text = cache.read_text()
        self.assertNotIn(payload.decode(), text)
        self.assertNotIn(str(addons), text)
        self.assertEqual(1, len(data['sources']))
        (addons / 'ui.pbo').write_bytes(archive([('replacement.paa', b'')]))
        data = index.build_index([addons], cache)
        self.assertEqual({'dz/ui/replacement.paa'}, index.load_index(cache))

    def test_invalid_cache_and_empty_input(self):
        cache = self.root / 'index.json'
        for data in ({}, {'schema': index.SCHEMA, 'sources': [1], 'names': [12]}):
            cache.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                index.load_index(cache)
        with self.assertRaises(ValueError):
            index.build_index([self.root], cache)

    def test_local_prefix_and_shipping_rules_reuse_packer(self):
        addon = self.root / 'mods/Anything'
        (addon / 'gui/layouts').mkdir(parents=True)
        (addon / '$PBOPREFIX$').write_text(PREFIX)
        (addon / 'gui/layouts/test.layout').write_text('')
        (addon / 'icon.paa').write_bytes(b'')
        files = index.local_files(self.root)
        self.assertTrue(files[index.canonical(PREFIX + '/gui/layouts/test.layout')])
        self.assertFalse(files[index.canonical(PREFIX + '/icon.paa')])

    def test_slash_case_and_enforce_escaping(self):
        self.assertEqual('dz/ui/icon.paa', index.canonical(r'\\DZ\\UI\\icon.PAA'))


    def manifest(self):
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps({'mods': [
            {'id': 'dependency', 'folder': '@Dependency', 'publish': False},
            {'id': 'owned', 'folder': '@Owned', 'publish': True}]}))
        return manifest

    def test_declared_dependencies_and_our_built_archives_are_required(self):
        manifest = self.manifest()
        addons = self.root / 'vanilla'
        workshop = self.root / 'workshop'
        for directory in (addons, workshop / 'dependency/Addons', workshop / 'owned/addons'):
            directory.mkdir(parents=True)
            (directory / 'test.pbo').write_bytes(archive([('icon.paa', b'')], prefix=directory.parent.name))
        directories, coverage = index.declared_directories(addons, workshop, manifest)
        self.assertEqual({addons, workshop / 'dependency/Addons', workshop / 'owned/addons'}, set(directories))
        self.assertEqual(sorted(['vanilla', '@Dependency', '@Owned']), coverage)
        data = index.build_index(directories, cache=None, coverage=coverage, manifest=manifest)
        self.assertTrue(data['names'])
        cache = self.root / 'cache/index.json'
        index.build_index(directories, cache, coverage, manifest)
        self.assertEqual(set(data['names']), index.load_index(cache, True, manifest))
        manifest.write_text(json.dumps({'mods': []}))
        with self.assertRaises(ValueError):
            index.load_index(cache, True, manifest)
        manifest = self.manifest()
        (workshop / 'dependency/Addons/test.pbo').unlink()
        with self.assertRaisesRegex(ValueError, '@Dependency'):
            index.declared_directories(addons, workshop, manifest)

    def test_incomplete_cache_cannot_pass_and_local_build_override(self):
        manifest = self.manifest()
        addons = self.root / 'vanilla'
        workshop = self.root / 'workshop'
        built = self.root / 'built'
        for directory in (addons, workshop / 'dependency/addons', built):
            directory.mkdir(parents=True)
            (directory / 'test.pbo').write_bytes(archive([('icon.paa', b'')]))
        directories, coverage = index.declared_directories(addons, workshop, manifest, [built])
        self.assertIn(built, directories)
        self.assertIn('@Owned', coverage)
        with self.assertRaisesRegex(ValueError, 'built PBO prefix missing'):
            index.build_index(directories, cache=None, coverage=coverage, manifest=manifest)
        cache = self.root / 'cache/index.json'
        index.build_index(directories, cache)
        with self.assertRaises(ValueError):
            index.load_index(cache, True, manifest)
