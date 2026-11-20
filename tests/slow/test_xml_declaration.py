"""#168: generated mission XML must use the double-quoted declaration.

CF's XML reader refused ElementTree's `<?xml version='1.0' encoding='utf-8'?>`
on a friend server ("No root tag economycore" for cfgeconomycore.xml). Every
generator in tools/package writes through one shared serializer instead.
"""
import pathlib
import unittest
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOUBLE = b'<?xml version="1.0" encoding="UTF-8"?>\n'


class XmlDeclarationTests(unittest.TestCase):
    def test_shared_serializer_writes_double_quoted_declaration(self):
        from tools.package.xml_text import DECLARATION, document
        root = ET.fromstring('<economycore><ce folder="hc"/></economycore>')
        data = document(root)
        self.assertEqual(DECLARATION, DOUBLE)
        self.assertTrue(data.startswith(DOUBLE), data[:60])
        self.assertEqual(data.count(b'<?xml'), 1)
        self.assertNotIn(b"version='1.0'", data)
        self.assertEqual(ET.fromstring(data).find('ce').get('folder'), 'hc')

    def test_optional_overlay_serializer_uses_double_quotes(self):
        from tools.package import optional_overlays
        data = optional_overlays.serialized(ET.fromstring('<types><type name="A"/></types>'))
        self.assertTrue(data.startswith(DOUBLE), data[:60])

    def test_atmosphere_script_prefix_uses_double_quotes(self):
        from tools.package.atmosphere import SCRIPT_XML_PREFIX
        self.assertTrue(SCRIPT_XML_PREFIX.startswith(DOUBLE), SCRIPT_XML_PREFIX)

    def test_no_generator_writes_elementtree_declaration(self):
        offenders = []
        for path in sorted((ROOT / 'tools').rglob('*.py')):
            text = path.read_text(encoding='utf-8')
            if 'xml_declaration=True' in text:
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])


if __name__ == '__main__':
    unittest.main()
