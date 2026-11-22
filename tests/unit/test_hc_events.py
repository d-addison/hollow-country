"""Offline CE anchor policy checks; these do not establish engine behaviour."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.package import hc_events as hc


class AnchorInvariantTests(unittest.TestCase):
    def positions(self):
        return ET.fromstring('<eventposdef><event name="StaticHCTest">'
                             '<pos x="100" z="200" y="12.5" a="0" />'
                             '</event></eventposdef>')

    def test_fixed_anchors_allow_no_zone_and_finite_zero_or_negative_height(self):
        for height in ('12.5', '0', '-2'):
            with self.subTest(height=height):
                positions = self.positions()
                positions[0][0].set('y', height)
                hc.check_anchor_invariants(positions)

    def test_every_anchor_requires_finite_numeric_height(self):
        for height in (None, '', 'unknown', 'nan', 'inf', '-inf'):
            with self.subTest(height=height):
                positions = self.positions()
                bad = ET.SubElement(positions[0], 'pos', x='300', z='400')
                if height is not None:
                    bad.set('y', height)
                with self.assertRaisesRegex(ValueError, 'anchor y: StaticHCTest:site002'):
                    hc.check_anchor_invariants(positions)

    def test_zero_zone_refused_including_numeric_spellings(self):
        for zero in ('0', '0.0', '-0', '0e0'):
            with self.subTest(zero=zero):
                positions = self.positions()
                ET.SubElement(positions[0], 'zone', **dict.fromkeys(
                    ('smin', 'smax', 'dmin', 'dmax', 'r'), zero))
                with self.assertRaisesRegex(ValueError, 'zero anchor zone: StaticHCTest'):
                    hc.check_anchor_invariants(positions)

    def test_nonzero_zone_allowed_but_malformed_zone_refused(self):
        positions = self.positions()
        zone = ET.SubElement(positions[0], 'zone', smin='0', smax='0', dmin='1', dmax='2', r='3')
        hc.check_anchor_invariants(positions)
        for value in ('', '-1', 'nan', 'inf', 'invalid', None):
            with self.subTest(value=value):
                if value is None:
                    zone.attrib.pop('r')
                else:
                    zone.set('r', value)
                with self.assertRaisesRegex(ValueError, 'invalid anchor zone: StaticHCTest'):
                    hc.check_anchor_invariants(positions)

    def test_committed_heights_match_native_authored_measurements(self):
        positions = ET.parse(hc.SOURCE / 'ce/hc-eventspawns.xml').getroot()
        rows = hc.measurement_rows(json.loads((hc.SOURCE / hc.MEASUREMENTS).read_bytes()))
        hc.check_anchor_invariants(positions)
        for event in positions:
            for index, pos in enumerate(event.findall('pos'), 1):
                ident = '%s:site%03d' % (event.get('name'), index)
                with self.subTest(anchor=ident):
                    for axis in ('x', 'z', 'y'):
                        self.assertAlmostEqual(float(pos.get(axis)), rows[ident][axis], places=6)

    def source_copy(self, root):
        relatives = ['ce/' + name for name in hc.DATA]
        relatives += ['events/' + name for name in hc.CACHE_DATA]
        relatives.append(hc.MEASUREMENTS)
        for relative in relatives:
            dest = root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((hc.SOURCE / relative).read_bytes())

    def test_validation_refuses_authored_regressions_before_measurement_repair(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.source_copy(root)
            path = root / 'ce/hc-eventspawns.xml'
            original = path.read_bytes()
            for defect in ('missing_y', 'zero_zone'):
                with self.subTest(defect=defect):
                    positions = ET.fromstring(original)
                    if defect == 'missing_y':
                        positions[0].find('pos').attrib.pop('y')
                    else:
                        ET.SubElement(positions[0], 'zone', smin='0', smax='0', dmin='0', dmax='0', r='0')
                    path.write_bytes(hc._serialized(positions))
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        result = hc.main(['check', '--source', str(root)])
                    self.assertEqual(result, 2)
                    self.assertIn('anchor', output.getvalue())
                    self.assertEqual(path.read_bytes(), hc._serialized(positions))

    def test_cache_events_must_be_created_empty_by_ce(self):
        # HC fills each CE-created case once at runtime; CE stock would double the fill.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.source_copy(root)
            path = root / 'events' / hc.CACHE_DATA[0]
            events = ET.fromstring(path.read_bytes())
            events[0].find('children/child').set('lootmax', '2')
            path.write_bytes(hc._serialized(events))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = hc.main(['check', '--source', str(root)])
            self.assertEqual(result, 2)
            self.assertIn('invalid cache stock lifecycle', output.getvalue())

    def test_offline_cli_without_mission_checks_generated_anchors_and_reports(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = hc.main(['check'])
        self.assertEqual(result, 0)
        report = json.loads(output.getvalue())
        self.assertTrue(report['valid'])
        self.assertEqual(report['runtime'], 'PENDING')
        _, (_, positions, _, _), _, expected = hc.validate()
        hc.check_anchor_invariants(positions)
        self.assertEqual(report['measured_relocated_anchors'], expected['measured_relocated_anchors'])
        self.assertEqual(report['measured_retired_anchors'], expected['measured_retired_anchors'])
        self.assertEqual(report['event_types'] + report['cache_event_types'], len(positions))


if __name__ == '__main__':
    unittest.main()
