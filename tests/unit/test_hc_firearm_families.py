"""HC-21 authored CE policy, with explicitly SYNTHETIC mission rows; no DayZ evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.package import economy, firearms, loot_boost
from test_firearms_roster import entry, synthetic


class FirearmFamilies(unittest.TestCase):
    def test_whole_family_supply_cannot_bypass_caps_or_native_routes(self):
        roster = json.loads(firearms.ROSTER_PATH.read_bytes())
        entries = {e['class']: e for e in roster['entries']}
        survivors = set('AK101 AKS74U ASVAL Aug AugShort CZ550 CZ61 Crossbow_Autumn Crossbow_Black '
                        'Crossbow_Wood Deagle Deagle_Gold Derringer_Grey Engraved1911 FAL FAMAS '
                        'LongHorn M14 M4A1 M79 MKII Magnum_Gold PM73Rak PP19 R12 SSG82 SV98 Scout '
                        'Scout_Chernarus UMP45 VSS Vikhr'.split())
        self.assertFalse(survivors - entries.keys(), 'positive off-roster firearms bypass scarcity')
        self.assertEqual({n for n, e in entries.items() if e.get('disposition') in
                          ('keep-native-budget', 'review-native-budget') and e['kind'] == 'weapon'}, survivors)
        self.assertEqual(entries['SV98']['disposition'], 'review-native-budget')
        self.assertEqual(entries['SV98']['runtime_acceptance'], 'pending')
        document = (Path(__file__).resolve().parents[2] / 'docs/FIREARMS.md').read_text()
        self.assertIn(firearms.render_family_summary(roster), document)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'mission'
            source.mkdir()
            synthetic(source)
            # SYNTHETIC: every authored ordinary row exists, with exaggerated source budgets.
            stock = ET.Element('types')
            for e in roster['entries']:
                if 'new_type_parent' not in e:
                    item = ET.fromstring(entry(e['class'], 0 if e.get('datamined') else 100,
                                               0 if e.get('datamined') else 80, 28800, 0,
                                               ['Town'], ['Tier2'], '<tag name="shelves"/>'))
                    # SYNTHETIC support category is normally boostable: the roster exclusion must win.
                    if e['kind'] != 'weapon':
                        item.find('category').set('name', 'containers')
                    stock.append(item)
            (source / 'db/types.xml').write_bytes(ET.tostring(stock))
            # SYNTHETIC carrier declarations mirror policy names, not installed spawn evidence.
            carriers = ET.Element('spawnabletypes')
            for e in roster['entries']:
                if e['kind'] == 'weapon':
                    host = ET.SubElement(carriers, 'type', name=e['class'])
                    for part in e.get('parts', []):
                        if part['route'] == 'native-carrier':
                            group = ET.SubElement(host, 'attachments', chance='1.0')
                            ET.SubElement(group, 'item', name=part['class'], chance='1.0')
            (source / 'cfgspawnabletypes.xml').write_bytes(ET.tostring(carriers))
            first = firearms.generate(source, roster)
            output = {e.get('name').lower(): e for e in ET.fromstring(first['ce/types.xml'])}
            report = json.loads(first['economy-report.json'])
            self.assertEqual(report['totals']['boost'], 'excluded')
            self.assertIn('HC21_NATIVE_WORLD_CAP_UNOBSERVED', report['totals']['refusals'])
            self.assertIn('HC21_SV98_FUNCTION_PENDING', report['totals']['refusals'])
            self.assertEqual(report['runtime_acceptance'], 'pending')
            self.assertEqual(report['totals']['family_count'],
                             sum(f['kind'] == 'weapon' for f in roster['family_budgets']))
            for e in roster['entries']:
                row = output[e['class'].lower()]
                self.assertEqual(int(row.findtext('nominal')), e['set']['nominal'], e['class'])
                self.assertEqual(int(row.findtext('min')), e['set']['min'], e['class'])
                donor_name = e.get('new_type_parent', e['class'])
                donor = next(item for item in stock if item.get('name') == donor_name)
                self.assertEqual(ET.tostring(row.find('flags')), ET.tostring(donor.find('flags')))
                self.assertEqual(row.findtext('quantmax'), donor.findtext('quantmax'))
            # Real combined generator and real boost consume exactly the same authored policy.
            combined = firearms.generate_combined(source, roster, include_items=False)
            self.assertEqual(first['ce/types.xml'], combined['ce/types.xml'])
            tampered = ET.fromstring(first['ce/types.xml'])
            tampered.find("type[@name='CZ527_Camo']/nominal").text = '10000'
            with self.assertRaisesRegex(ValueError, 'family budget'):
                firearms.check_effective_support(source, {e.get('name'): e for e in stock},
                                                 roster['entries'], tampered)
            boosted, _ = loot_boost.scale_types(first['ce/types.xml'], 2, loot_boost._roster_names())
            self.assertEqual(ET.tostring(ET.fromstring(boosted)), ET.tostring(ET.fromstring(first['ce/types.xml'])))
            for class_name in ('CZ527_Camo', 'MakarovPB', 'AmmoBox_556x45_20Rnd', 'Ammo_556x45Tracer'):
                bypass = copy.deepcopy(roster)
                target = next(e for e in bypass['entries'] if e['class'] == class_name)
                target['set']['nominal'] += 10000
                with self.subTest(bypass=class_name), self.assertRaisesRegex(ValueError, 'family budget'):
                    firearms.generate(source, bypass)
            # Carrier-only parts stay attached; integral optics/cylinders never become loose loot.
            self.assertNotIn('AugOptic', entries)
            self.assertNotIn('Magnum_Cylinder', entries)
            (source / 'cfgspawnabletypes.xml').write_text('<spawnabletypes/>')
            with self.assertRaisesRegex(ValueError, 'HC21_PART_ROUTE_MISSING'):
                firearms.generate(source, roster)
            (source / 'cfgspawnabletypes.xml').write_bytes(ET.tostring(carriers))
            disabled = firearms.generate(source, roster, include_datamined=False)
            rows = {e.get('name').lower() for e in ET.fromstring(disabled['ce/types.xml'])}
            self.assertFalse({e['class'].lower() for e in roster['entries'] if e.get('datamined')} & rows)
            # Missing off-roster support refuses; no newly invented magazine is substituted.
            bad = copy.deepcopy(roster)
            next(e for e in bad['entries'] if e['class'] == 'Mag_AK101_30Rnd')['set'] = {'nominal': 0, 'min': 0}
            with self.assertRaisesRegex(ValueError, 'spawning weapon.*magazine'):
                firearms.generate(source, bad)
            # Future positive ammo rows cannot silently fall outside the reviewed policy.
            stock.append(ET.fromstring(entry('Ammo_FutureTracer', 5, 2, 100, 0, ['Town'], [])))
            (source / 'db/types.xml').write_bytes(ET.tostring(stock))
            with self.assertRaisesRegex(ValueError, 'HC21_UNACCOUNTED_SUPPORT'):
                firearms.generate(source, roster)
