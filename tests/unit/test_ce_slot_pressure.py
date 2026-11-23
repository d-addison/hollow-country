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
