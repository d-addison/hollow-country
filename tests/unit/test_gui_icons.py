"""Focused icon provenance and PBO checks; synthetic converter, no engine claims."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from tools.package import gui_icons as icons, pbo


class GuiIconsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tool = self.root / 'ImageToPAA.exe'
        self.tool.write_bytes(b'synthetic converter')

    def fake_convert(self, tool, source, target):
        target.write_bytes(b'\x05\xff' + bytes.fromhex(icons.sha(source.read_bytes())))

    def build(self):
        icons.build(self.root, self.tool, self.fake_convert)

    def test_png_pixels_have_alpha_and_unique_shapes(self):
        images = [icons.render_png(name) for name in icons.ICONS]
        self.assertEqual(len(set(images)), len(icons.ICONS))
        for png in images:
            self.assertEqual(struct.unpack('>II', png[16:24]), (icons.SIZE, icons.SIZE))
            offset, compressed = 8, b''
            while offset < len(png):
                length = struct.unpack('>I', png[offset:offset+4])[0]
                kind, data = png[offset+4:offset+8], png[offset+8:offset+8+length]
                crc = struct.unpack('>I', png[offset+8+length:offset+12+length])[0]
                self.assertEqual(crc, zlib.crc32(kind+data))
                if kind == b'IDAT':
                    compressed += data
                offset += length + 12
            rows = zlib.decompress(compressed)
            alpha = [rows[y*(1+icons.SIZE*4)+1+x*4+3]
                     for y in range(icons.SIZE) for x in range(icons.SIZE)]
            self.assertIn(0, alpha)
            self.assertIn(255, alpha)
            self.assertTrue(any(0 < a < 255 for a in alpha))

    def test_build_and_offline_check(self):
        self.build()
        self.assertEqual(icons.check(self.root), len(icons.ICONS))
        manifest = json.loads((self.root / icons.MANIFEST).read_text())
        self.assertEqual(manifest['converter_sha256'], icons.sha(self.tool.read_bytes()))
        self.assertNotIn(str(self.root), json.dumps(manifest))

    def test_mutations_and_missing_pairs_fail(self):
        self.build()
        for directory, extension in ((icons.SOURCE, '.png'), (icons.OUTPUT, '.paa')):
            path = self.root / directory / (next(iter(icons.ICONS)) + extension)
            original = path.read_bytes()
            path.write_bytes(original + b'changed')
            with self.assertRaises(ValueError):
                icons.check(self.root)
            path.unlink()
            with self.assertRaises(ValueError):
                icons.check(self.root)
            path.write_bytes(original)
        (self.root / icons.OUTPUT / 'unexpected.paa').write_bytes(b'extra')
        with self.assertRaises(ValueError):
            icons.check(self.root)

    def test_manifest_cannot_redirect_paths_or_omit_categories(self):
        self.build()
        path = self.root / icons.MANIFEST
        manifest = json.loads(path.read_text())
        name = next(iter(icons.ICONS))
        manifest['icons'][name]['source'] = '../elsewhere.png'
        path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            icons.check(self.root)
        del manifest['icons'][name]
        path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            icons.check(self.root)

    def test_failed_converter_keeps_previous_manifest_and_outputs(self):
        self.build()
        manifest = (self.root / icons.MANIFEST).read_bytes()
        output = {p.name: p.read_bytes() for p in (self.root / icons.OUTPUT).glob('*.paa')}
        def fail(tool, source, target):
            raise ValueError('synthetic failure')
        with self.assertRaises(ValueError):
            icons.build(self.root, self.tool, fail)
        self.assertEqual((self.root / icons.MANIFEST).read_bytes(), manifest)
        self.assertEqual({p.name: p.read_bytes() for p in (self.root / icons.OUTPUT).glob('*.paa')}, output)

    def test_missing_tool_still_renders_sources_without_fake_paa(self):
        self.tool.unlink()
        with self.assertRaises(ValueError):
            icons.build(self.root, self.tool, self.fake_convert)
        self.assertEqual(len(list((self.root / icons.SOURCE).glob('*.png'))), len(icons.ICONS))
        self.assertFalse((self.root / icons.MANIFEST).exists())

    def test_packer_roundtrip_preserves_icons_and_prefix(self):
        self.build()
        addon = self.root / 'mods/HollowCountry'
        (addon / 'config.cpp').write_text('class CfgPatches {};')
        (addon / 'gui/icons/map/.gitignore').write_text('!*.paa\n')
        files = pbo.collect_addon(addon)
        self.assertNotIn('gui/icons/map/.gitignore', files)
        prefix, unpacked = pbo.parse(pbo.pack(files))
        self.assertEqual(prefix, 'HollowCountry')
        self.assertEqual(unpacked, files)
        for name in icons.ICONS:
            self.assertIn('gui/icons/map/' + name + '.paa', files)

    def test_packer_binary_exception_is_narrow(self):
        addon = self.root / 'addon'
        addon.mkdir()
        (addon / 'config.cpp').write_text('class CfgPatches {};')
        for rel in ('gui/other.paa', 'gui/icons/map/player.png', 'scripts/4_World/binary.c',
                    'gui/icons/map/player.paa'):
            path = addon / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'invalid\0binary')
            with self.assertRaises(ValueError):
                pbo.collect_addon(addon)
            path.unlink()

    def test_committed_provenance(self):
        self.assertEqual(icons.check(icons.ROOT), len(icons.ICONS))


if __name__ == '__main__':
    unittest.main()
