"""Host calibration helpers; synthetic metadata is never engine placement evidence."""
import unittest
from unittest.mock import patch

from tools.package import shelf_fit


class ShelfFit(unittest.TestCase):
    def test_threshold_and_unknowns(self):
        self.assertEqual(shelf_fit.classify(2, [.2] * 100)['reason'], 'below_threshold')
        self.assertEqual(shelf_fit.classify(.2, [.1] * 7 + [.2] * 3)['reason'], 'fits')
        self.assertEqual(shelf_fit.classify(.2, [.1] * 7004 + [.2] * 2996)['fit_share'], .299)
        self.assertEqual(shelf_fit.classify(None, [.2])['reason'], 'bounds_unknown')
        self.assertEqual(shelf_fit.classify(.1, [])['reason'], 'no_shelf_points')

    def test_unreadable_or_no_lod_model_is_unknown(self):
        models = shelf_fit.Models([])
        models.classes['tool'] = {'model': 'tool.p3d'}
        models.members['tool.p3d'] = (None, None, 'tool.p3d')
        for raw in (b'unreadable', b'ODOL' + b'8\0\0\0' + b'\0' * 20):
            models.cache.clear()
            with patch.object(shelf_fit.pbo, 'read_member', return_value=raw):
                self.assertIsNone(models.longest('Tool'))

    def test_authored_tags_restore_only_native_tags(self):
        import xml.etree.ElementTree as ET
        from tools.package import economy
        rows = ET.fromstring('<types>' + ''.join(
            '<type name="%s"><nominal>8</nominal><min>3</min><category name="tools"/>'
            '<tag name="shelves"/><usage name="Farm"/></type>' % name
            for name in ('Absent', 'Floor', 'NativeShelf', 'Fits', 'Missing')) + '</types>')
        stock = economy._unique(ET.fromstring('<types><type name="Floor"><tag name="floor"/></type>'
            '<type name="NativeShelf"><tag name="shelves"/></type></types>'))
        before = {r.get('name'): economy._retained(r, {'tag'}) for r in rows}
        evidence = {'classes': {'Absent': shelf_fit.classify(2, [.2]),
                               'Fits': shelf_fit.classify(.1, [.2])}}
        self.assertEqual(economy.authored_shelf_tags(rows, stock, evidence), ['Absent', 'Floor', 'Missing'])
        self.assertEqual([[n.get('name') for n in r.findall('tag')] for r in rows],
                         [[], ['floor'], ['shelves'], ['shelves'], []])
        self.assertEqual(before, {r.get('name'): economy._retained(r, {'tag'}) for r in rows})
        self.assertEqual(economy.authored_shelf_tags(rows, stock, evidence), [])

    def test_encoding_is_deterministic(self):
        doc = dict(schema=1, kind=shelf_fit.floor.SHELF_FIT_KIND, threshold=.3,
                   classes={'Tool': shelf_fit.classify(.1, [.2])})
        self.assertEqual(shelf_fit.encode(doc), shelf_fit.encode(dict(reversed(list(doc.items())))))


if __name__ == '__main__':
    unittest.main()
