"""Synthetic CE exports exercise preparation, never native eligibility."""
import hashlib
import unittest
import xml.etree.ElementTree as ET

from tools.package import coverage


STOCK = b'<prototype><group name="SyntheticApartment" lootmax="0"><usage name="Town"/><container name="loot" lootmax="0"><category name="tools"/></container></group><group name="Untouched" lootmax="2"/></prototype>'
EXPORT = b'<prototype><group name="SyntheticApartment" lootmax="1"><usage name="Town"/><container name="loot" lootmax="1"><category name="tools"/><point pos="1.25 0.5 -2" range="1.0" height="0.5"/></container></group><group name="Untouched" lootmax="2"/></prototype>'


def evidence():
    return {'schema': 1, 'world': 'chernarusplus', 'build': '1.30.164289',
            'source_sha256': hashlib.sha256(STOCK).hexdigest(),
            'export_sha256': hashlib.sha256(EXPORT).hexdigest(),
            'groups': ['SyntheticApartment'],
            'observations': [{'path': 'diag-export.log', 'sha256': hashlib.sha256(b'synthetic observation').hexdigest()}]}


class CoveragePatchTests(unittest.TestCase):
    def test_utf16_entity_declarations_cannot_bypass_xml_guard(self):
        # Keep a valid entity declaration and put its reference in a point.
        text = '<!DOCTYPE prototype [<!ENTITY coordinate "1.25 0.5 -2">]>' + EXPORT.decode().replace('1.25 0.5 -2', '&coordinate;')
        for encoding in ('utf-16', 'utf-16-le', 'utf-16-be', 'utf-32'):
            exported = text.encode(encoding)
            e = evidence()
            e['export_sha256'] = hashlib.sha256(exported).hexdigest()
            with self.subTest(encoding=encoding), self.assertRaises(ValueError):
                self.prepare(exported=exported, evidence=e)

    def prepare(self, **kw):
        args = dict(stock=STOCK, exported=EXPORT, evidence=evidence(),
                    artifacts={'diag-export.log': b'synthetic observation'})
        args.update(kw)
        return coverage.prepare(**args)

    def test_minimal_verified_export_changes_only_requested_group(self):
        result, report = self.prepare()
        root = ET.fromstring(result)
        self.assertEqual(root.find('group').get('lootmax'), '1')
        self.assertEqual(root.find('.//point').get('pos'), '1.25 0.5 -2')
        self.assertEqual(ET.tostring(root.findall('group')[1]), ET.tostring(ET.fromstring(STOCK).findall('group')[1]))
        self.assertEqual(report['changed_groups'], ['SyntheticApartment'])
        self.assertEqual(report['added_raw_points'], 1)
        self.assertFalse(report['engine_eligibility_verified'])
        self.assertEqual(self.prepare(), (result, report))

    def test_source_export_and_observation_pins_are_required(self):
        for field in ('source_sha256', 'export_sha256'):
            e = evidence()
            e[field] = '0' * 64
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.prepare(evidence=e)
        with self.assertRaises(ValueError):
            self.prepare(artifacts={'diag-export.log': b'tampered'})
        e = evidence()
        e['observations'] = []
        with self.assertRaises(ValueError):
            self.prepare(evidence=e)

    def test_unrequested_changes_unknown_groups_and_noops_rejected(self):
        for export in (EXPORT.replace(b'name="Untouched" lootmax="2"', b'name="Untouched" lootmax="4"'), STOCK):
            e = evidence()
            e['export_sha256'] = hashlib.sha256(export).hexdigest()
            with self.subTest(export=export), self.assertRaises(ValueError):
                self.prepare(exported=export, evidence=e)
        e = evidence()
        e['groups'] = ['Missing']
        with self.assertRaises(ValueError):
            self.prepare(evidence=e)

    def test_invalid_duplicate_or_nonfinite_points_rejected(self):
        for value in ('nan 0 0', 'inf 0 0', '1001 0 0', '1 2', '0 0 0 0'):
            export = EXPORT.replace(b'1.25 0.5 -2', value.encode())
            e = evidence()
            e['export_sha256'] = hashlib.sha256(export).hexdigest()
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.prepare(exported=export, evidence=e)
        point = b'<point pos="1.25 0.5 -2" range="1.0" height="0.5"/>'
        export = EXPORT.replace(point, point + point)
        e = evidence()
        e['export_sha256'] = hashlib.sha256(export).hexdigest()
        with self.assertRaises(ValueError):
            self.prepare(exported=export, evidence=e)

    def test_existing_points_and_categories_cannot_be_deleted(self):
        for export in (EXPORT.replace(b'<category name="tools"/>', b''),
                       EXPORT.replace(b'<usage name="Town"/>', b'<usage name="Military"/>')):
            e = evidence()
            e['export_sha256'] = hashlib.sha256(export).hexdigest()
            with self.assertRaises(ValueError):
                self.prepare(exported=export, evidence=e)

    def test_evidence_schema_and_unsafe_paths_rejected(self):
        for patch in ({'schema': True}, {'world': 'unknown'}, {'groups': []},
                      {'groups': ['SyntheticApartment', 'SyntheticApartment']}, {'accepted': True}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                self.prepare(evidence=dict(evidence(), **patch))
        e = evidence()
        e['observations'][0]['path'] = '../escape'
        with self.assertRaises(ValueError):
            self.prepare(evidence=e)

    def test_point_metadata_and_bounds_cannot_silently_change(self):
        for old, new in ((b'range="1.0"', b'range="-1"'),
                         (b'height="0.5"', b'height="nan"'),
                         (b'height="0.5"', b'flags="bad"'),
                         (b'height="0.5"', b'unknown="1"'),
                         (b'lootmax="1"', b'lootmax="99"')):
            export = EXPORT.replace(old, new)
            e = evidence()
            e['export_sha256'] = hashlib.sha256(export).hexdigest()
            with self.subTest(new=new), self.assertRaises(ValueError):
                self.prepare(exported=export, evidence=e)

    def test_external_entities_and_duplicate_groups_rejected(self):
        for export in (b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>' + EXPORT,
                       EXPORT.replace(b'</prototype>', b'<group name="Untouched"/></prototype>')):
            e = evidence()
            e['export_sha256'] = hashlib.sha256(export).hexdigest()
            with self.assertRaises(ValueError):
                self.prepare(exported=export, evidence=e)


if __name__ == '__main__':
    unittest.main()
