"""Static CE capacity and CLI contracts; these do not prove native item fit."""
import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.package import ce_slot_pressure as pressure


class SlotPressure(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.mission = Path(self.scratch.name)
        (self.mission / 'db').mkdir()
        self.write('cfgeconomycore.xml', '<economycore/>')
        self.write('cfglimitsdefinition.xml', '<lists><valueflags>'
                   '<value name="Tier1"/><value name="Tier2"/></valueflags></lists>')
        (self.mission / 'areaflags.map').write_bytes(
            struct.pack('<6I', 1, 1, 10, 10, 32, 0) + b'\0\0\0\0\1')
        self.write('mapgrouppos.xml', '<map><group name="Cabin" pos="5 0 5"/></map>')
        self.types(self.row('Pants'))
        self.proto()

    def write(self, name, text):
        (self.mission / name).write_text(text, encoding='utf-8')

    def types(self, *rows):
        self.write('db/types.xml', '<types>' + ''.join(rows) + '</types>')

    @staticmethod
    def row(name, nominal=1, category='clothes', usage='Hunting', extra=''):
        return (f'<type name="{name}"><nominal>{nominal}</nominal>'
                f'<category name="{category}"/><usage name="{usage}"/>{extra}</type>')

    def proto(self, group_cap=1, containers=None):
        if containers is None:
            containers = ('<container lootmax="1"><category name="clothes"/>'
                          '<tag name="shelves"/><point/></container>')
        self.write('mapgroupproto.xml', f'<prototype><group name="Cabin" lootmax="{group_cap}">'
                   '<usage name="Hunting"/>' + containers + '</group></prototype>')

    def cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = pressure.main([str(self.mission), *args])
        return code, json.loads(output.getvalue())

    def test_feasibility_exit_status_tracks_capacity_deficit(self):
        for nominal in (1, 3):
            with self.subTest(nominal=nominal):
                self.types(self.row('Pants', nominal))
                code, report = self.cli('--feasibility')
                self.assertEqual(report['demand'], nominal)
                self.assertEqual(report['deficit'], max(0, nominal - 1))
                self.assertEqual(code, int(report['deficit'] > 0))

    def test_categories_share_group_capacity(self):
        rows = [self.row(category, category=category) for category in ('clothes', 'tools')]
        self.types(*rows)
        self.proto(containers=''.join(
            f'<container lootmax="1"><category name="{c}"/><point/></container>'
            for c in ('clothes', 'tools')))
        code, result = self.cli('--all-categories')
        self.assertEqual(result['demand'], len(rows))
        self.assertEqual(result['placeable_upper_bound'], 1)
        self.assertEqual(code, 1)
        self.assertEqual(result['unreachable_types'], [])

    def test_usage_tier_category_tag_and_disabled_caps_refuse_routes(self):
        cases = [dict(usage='Military'), dict(category='tools'),
                 dict(extra='<tag name="floor"/>'), dict(extra='<value name="Tier2"/>')]
        for fields in cases:
            with self.subTest(fields=fields):
                self.types(self.row('Unrouted', **fields))
                code, result = self.cli('--feasibility')
                self.assertEqual(code, 1)
                self.assertEqual(result['unreachable_nominal'], result['demand'])
                self.assertEqual([r['name'] for r in result['unreachable_types']], ['Unrouted'])
        self.types(self.row('Pants'))
        self.proto(group_cap=0)
        self.assertEqual(self.cli('--feasibility')[0], 1)

    def test_overlay_replaces_stock_row_case_insensitively(self):
        (self.mission / 'custom').mkdir()
        self.write('custom/types.xml', '<types>' + self.row('PANTS', nominal=2) + '</types>')
        self.write('cfgeconomycore.xml', '<economycore><ce folder="custom">'
                   '<file name="types.xml" type="types"/></ce></economycore>')
        _, result = self.cli('--feasibility')
        self.assertEqual(result['demand'], 2)
        self.assertEqual(result['deficit'], 1)

    def test_clothing_routes_can_use_native_hunting_shelves(self):
        source = Path(__file__).resolve().parents[2] / 'mission/hollow-country/ce/types.xml'
        authored = {r.get('name'): r for r in ET.parse(source).getroot()}
        for name in ('BDUPants', 'JungleBoots_Green', 'OKZKCap_Beige'):
            with self.subTest(name=name):
                row = authored[name]
                nominal = int(row.findtext('nominal'))
                self.assertGreaterEqual(int(row.findtext('min')), 1)
                self.assertGreaterEqual(nominal, int(row.findtext('min')))
                self.types(ET.tostring(row, encoding='unicode'))
                # Size this synthetic native-category receiver from the data's demand.
                self.proto(group_cap=nominal, containers=f'<container lootmax="{nominal}">'
                           '<category name="clothes"/><tag name="shelves"/>'
                           + '<point/>' * nominal + '</container>')
                code, result = self.cli('--feasibility')
                self.assertEqual(code, 0)
                self.assertEqual(result['placeable_upper_bound'], nominal)

    def test_military_headroom_is_enforced(self):
        self.types(self.row('Rifle', category='weapons', usage='Military'))
        self.write('mapgroupproto.xml', '<prototype><group name="Cabin" lootmax="1">'
                   '<usage name="Military"/><container lootmax="1">'
                   '<category name="weapons"/><point/></container></group></prototype>')
        code, result = self.cli('--military-weapons', '--limit', '0.5')
        self.assertEqual(code, 1)
        self.assertGreater(result['required_with_headroom'], result['reserved_placeable'])

    def test_bad_inputs_fail_closed_without_paths(self):
        for name, bad in [('db/types.xml', '<types>'), ('areaflags.map', b'bad')]:
            with self.subTest(name=name):
                path = self.mission / name
                before = path.read_bytes()
                path.write_bytes(bad.encode() if isinstance(bad, str) else bad)
                code, result = self.cli('--feasibility')
                self.assertEqual(code, 2)
                self.assertEqual(result['status'], 'error')
                self.assertNotIn(str(self.mission), json.dumps(result))
                path.write_bytes(before)
        (self.mission / 'db/types.xml').unlink()
        self.assertEqual(self.cli('--feasibility')[0], 2)

    def test_route_upper_bound_counts_placed_groups_once_and_shares_their_cap(self):
        self.types(self.row('Pants', nominal=2), self.row('Coat', nominal=2))
        self.proto(group_cap=1, containers='<container lootmax="4"><category name="clothes"/>'
                   '<tag name="shelves"/><point/><point/><point/><point/></container>')
        self.write('mapgrouppos.xml', '<map><group name="Cabin" pos="5 0 5"/>'
                   '<group name="Cabin" pos="5 0 5"/></map>')
        bucket = pressure.feasibility(self.mission, slack=True)['bucket_slack'][0]
        self.assertEqual(bucket['compatible_capacity'], 2)
        self.assertEqual(bucket['nominal'], 4)
        self.assertEqual(bucket['unassigned'], 2)

    def test_calibration_reports_missing_rows_and_elapsed_windows_without_paths(self):
        self.proto(containers='<container lootmax="1"><category name="clothes"/>'
                   '<tag name="shelves"/><point pos="0 0 0"/></container>')
        rpt = self.mission / 'private-input.RPT'
        rpt.write_text('12:00:00.000 boot\n'
                       '12:00:01.000 [CE][LootRespawner] hard to place, performance drops: "Pants"\n'
                       '12:03:00.000 [CE][LootRespawner] hard to place, performance drops: "Missing"\n'
                       '12:04:00.000 quiet\n')
        code, result = self.cli('--calibrate-rpt', str(rpt))
        self.assertEqual(code, 0)
        self.assertEqual(result['status'], 'unverified')
        self.assertNotIn(str(rpt), json.dumps(result))
        rows = {r['name']: r for r in result['classes']}
        self.assertEqual(rows['Pants']['prototype_shelf_points'], 1)
        self.assertEqual(rows['Pants']['placed_compatible_upper_bound'], 1)
        self.assertEqual(rows['Pants']['observations'][0]['later_count'], 0)
        self.assertEqual(rows['Missing']['observations'][0]['later_per_hour'], 30)
        self.assertIsNone(rows['Missing']['nominal'])

    def test_rpt_windows_include_quiet_time_and_midnight(self):
        rpt = self.mission / 'midnight.RPT'
        rpt.write_text('23:59:00.40 boot\n'
                       '23:59:00.100 later\n'
                       '00:01:00.40 [CE][LootRespawner] hard to place, performance drops: "Pants"\n'
                       '00:03:00.40 quiet\n')
        result = pressure.rpt_placement_counts(rpt)
        self.assertEqual(result['duration_seconds'], 240)
        self.assertEqual(result['later_counts'], {'Pants': 1})
        rpt.write_text('12:00:00 boot\n11:59:00 backwards\n')
        with self.assertRaises(ValueError):
            pressure.rpt_placement_counts(rpt)
        rpt.write_text('no timestamp\n')
        self.assertEqual(self.cli('--calibrate-rpt', str(rpt))[0], 2)

    def test_invalid_options_are_rejected(self):
        for args in [('--limit', 'nan'), ('--limit', '0'), ('--limit', '1.1'),
                     ('--top', '-1'), ('--all-categories', '--military-weapons')]:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    pressure.main([str(self.mission), *args])
                self.assertEqual(error.exception.code, 2)


if __name__ == '__main__':
    unittest.main()


class VillageItems(unittest.TestCase):
    def test_a_house_holds_its_slots_times_the_village_fill(self):
        """SYNTHETIC mission: 2 houses of 10 slots plus one 4-slot wreck shared with Industrial; fill = nominal / slots."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'db').mkdir()
            (root / 'cfgeconomycore.xml').write_text('<economycore/>')
            (root / 'db/types.xml').write_text('<types><type name="A"><nominal>11</nominal><usage name="Village"/></type></types>')
            points = ''.join('<point pos="0 0 0"/>' for _ in range(10))
            (root / 'mapgroupproto.xml').write_text(
                '<prototype><defaults><default name="container" lootmax="10"/></defaults>'
                f'<group name="Land_House_X" lootmax="10"><usage name="Village"/><container name="c">{points}</container></group>'
                '<group name="Land_Wreck_Y" lootmax="4"><usage name="Village"/><usage name="Industrial"/>'
                f'<container name="w">{points[:4 * 20]}</container></group></prototype>')
            (root / 'mapgrouppos.xml').write_text('<map><group name="Land_House_X" pos="0 0 0"/><group name="Land_House_X" pos="1 0 0"/>'
                                                  '<group name="Land_Wreck_Y" pos="2 0 0"/></map>')
            result = pressure.village_items(root)
        self.assertEqual((result['nominal'], result['slots']), (11, 22))
        self.assertEqual(result['fill'], 0.5)
        self.assertEqual(result['kinds']['house'], {'groups': 1, 'buildings': 2, 'median': 5.0, 'p90': 5.0})
        self.assertEqual(result['kinds']['wreck']['median'], 1.0)


class EngineCapReceipt(unittest.TestCase):
    def test_old_receipt_above_cap_fails_and_capped_reinstall_passes(self):
        from unittest import mock
        from tools.package import loot_boost as boost
        from tests.unit.test_loot_boost import EngineEvidenceCaps
        with tempfile.TemporaryDirectory() as tmp:
            mission = EngineEvidenceCaps().fixture(tmp)
            with mock.patch.object(boost, 'engine_caps', return_value={}):
                boost.install(mission, None, None, floor_policy=None)
            old = pressure.engine_cap_check(mission)
            self.assertEqual(old['status'], 'fail')
            self.assertIn('Pipe', {r['class'] for r in old['violations']})
            (mission / 'cfglimitsdefinition.xml').write_text('<lists><valueflags><value name="Tier1"/></valueflags></lists>')
            (mission / 'areaflags.map').write_bytes(struct.pack('<6I', 1, 1, 10, 10, 32, 0) + b'\0\0\0\0\1')
            gate = pressure.feasibility(mission, True)
            self.assertEqual(gate['engine_caps']['status'], 'fail')
            from tools.validate.mission_sources import ce_slots_main
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ce_slots_main(mission), 1)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(pressure.main([str(mission), '--engine-caps']), 1)
            boost.rollback(mission)
            boost.install(mission, None, None, floor_policy=None)
            self.assertEqual(pressure.engine_cap_check(mission), {'status': 'pass', 'violations': []})
            # A minimum-only violation is also rejected, even if nominal equals its cap.
            path = mission / 'db/types.xml'
            path.write_bytes(path.read_bytes().replace(b'<min>60</min>', b'<min>61</min>'))
            self.assertEqual(pressure.engine_cap_check(mission)['status'], 'fail')

    def test_missing_or_drifted_backup_is_not_a_pass(self):
        from tools.package import loot_boost as boost
        from tests.unit.test_loot_boost import EngineEvidenceCaps
        with tempfile.TemporaryDirectory() as tmp:
            mission = EngineEvidenceCaps().fixture(tmp)
            with self.assertRaises(ValueError):
                pressure.engine_cap_check(mission)
            receipt = boost.install(mission, None, None, floor_policy=None)
            row = next(r for r in receipt['files'] if r['name'] == 'db/types.xml')
            (mission / boost.MANAGED / row['backup']).write_bytes(b'<types/>')
            with self.assertRaisesRegex(ValueError, 'backup drifted'):
                pressure.engine_cap_check(mission)

    def test_unchanged_registered_layer_uses_receipted_source_cap(self):
        from tools.package import loot_boost as boost
        from tests.unit.test_loot_boost import EngineEvidenceCaps, type_row
        with tempfile.TemporaryDirectory() as tmp:
            mission = EngineEvidenceCaps().fixture(tmp)
            (mission / 'custom').mkdir()
            path = mission / 'custom/types.xml'
            path.write_text('<types>' + type_row('geb_SmallTackle', ['Coast'], 1, 0, 'weapons') + '</types>')
            (mission / 'cfgeconomycore.xml').write_text('<economycore><ce folder="custom">'
                '<file name="types.xml" type="types"/></ce></economycore>')
            receipt = boost.install(mission, None, None, floor_policy=None)
            self.assertNotIn('custom/types.xml', [r['name'] for r in receipt['files']])
            path.write_bytes(path.read_bytes().replace(b'<nominal>1</nominal>', b'<nominal>2</nominal>'))
            result = pressure.engine_cap_check(mission)
            self.assertEqual(result['status'], 'fail')
            self.assertIn({'class': 'geb_SmallTackle', 'field': 'nominal', 'actual': 2, 'cap': 1}, result['violations'])
