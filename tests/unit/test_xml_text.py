import unittest
import xml.etree.ElementTree as ET

from tools.package import xml_text


def _wide_types(count):
    root = ET.Element('types')
    for index in range(count):
        item = ET.SubElement(root, 'type', {'name': f'Item_{index}'})
        ET.SubElement(item, 'nominal').text = '1'
        ET.SubElement(item, 'flags', {'count_in_map': '1', 'deloot': '0'})
        ET.SubElement(item, 'category', {'name': 'weapons'})
    return root


class DocumentTest(unittest.TestCase):
    def test_short_documents_keep_their_bytes(self):
        root = _wide_types(2)
        expected = xml_text.DECLARATION + ET.tostring(root, encoding='utf-8')
        self.assertLessEqual(xml_text.longest_line(expected), xml_text.MAX_LINE)
        self.assertEqual(xml_text.document(root), expected)

    def test_generated_lines_stay_within_the_bound(self):
        # Enough fresh elements that a single-line serialisation exceeds the bound.
        count = 1
        while xml_text.longest_line(ET.tostring(_wide_types(count), encoding='utf-8')) <= xml_text.MAX_LINE:
            count *= 2
        root = _wide_types(count)
        before = ET.tostring(root, encoding='utf-8')
        data = xml_text.document(root)
        self.assertLessEqual(xml_text.longest_line(data), xml_text.MAX_LINE)
        self.assertTrue(data.startswith(xml_text.DECLARATION))
        self.assertEqual(ET.tostring(root, encoding='utf-8'), before)
        parsed = ET.fromstring(data[len(xml_text.DECLARATION):])
        self.assertEqual([t.get('name') for t in parsed], [t.get('name') for t in root])

    def test_unbreakable_line_raises(self):
        root = ET.Element('types', {'name': 'x' * (xml_text.MAX_LINE + 1)})
        with self.assertRaises(ValueError):
            xml_text.document(root)


if __name__ == '__main__':
    unittest.main()
