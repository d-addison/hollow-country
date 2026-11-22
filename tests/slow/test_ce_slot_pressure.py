"""Synthetic route eligibility, never engine spawn acceptance."""
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools.package import ce_slot_pressure as pressure, military_loot


class ModdedCoverage(unittest.TestCase):
    def test_usage_category_tag_tier_and_capacity_all_constrain_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'db').mkdir()
            (root / 'cfgeconomycore.xml').write_text('<economycore/>')
            (root / 'cfglimitsdefinition.xml').write_text('<lists><usageflags><usage name="Hunting"/>'
                '<usage name="Medic"/></usageflags><valueflags><value name="Tier1"/>'
                '<value name="Tier2"/></valueflags></lists>')
            (root / 'areaflags.map').write_bytes(struct.pack('<6I', 1, 1, 10, 10, 32, 0) + b'\x08\x00\x00\x00\x01')
            (root / 'mapgrouppos.xml').write_text('<map><group name="Stand" pos="5 0 5"/></map>')
            (root / 'mapgroupproto.xml').write_text('<map><group name="Stand"><usage name="Hunting"/>'
                '<container name="shelf" lootmax="1"><category name="weapons"/><tag name="shelves"/>'
                '<point/></container><container name="disabled" lootmax="0"><category name="tools"/>'
                '<point/></container></group></map>')
            def row(name, category='weapons', extra=''):
                return f'<type name="{name}"><nominal>1</nominal><category name="{category}"/>' \
                       f'<usage name="Hunting"/>{extra}</type>'
            rows = [row('Rifle'), row('FloorOnly', extra='<tag name="floor"/>'),
                    row('LateTier', extra='<value name="Tier2"/>'), row('Tool', 'tools')]
            (root / 'db/types.xml').write_text('<types>' + ''.join(rows) + '</types>')
            catalog = {name: {'datamined': True} for name in ('Rifle', 'FloorOnly', 'LateTier', 'Tool')}
            with patch.object(military_loot, 'catalog', return_value=catalog), patch.object(military_loot, 'SOURCES', ('synthetic',)):
                result = pressure.modded_coverage(root)
            self.assertEqual(result['classes_by_usage'], {'Hunting': 1, 'Medic': 0})
            self.assertEqual(result['positive_modded_classes'], len(rows))
            self.assertEqual(result['uncovered_containers'], [])
            self.assertEqual(set(result['unreachable_classes']), {'flooronly', 'latetier', 'tool'})


class JointCapacity(unittest.TestCase):
    def fixture(self, root, rows, container):
        (root/'db').mkdir()
        (root/'db/types.xml').write_text('<types>'+''.join(rows)+'</types>')
        (root/'cfgeconomycore.xml').write_text('<economycore/>')
        (root/'cfglimitsdefinition.xml').write_text('<lists><valueflags><value name="Tier1"/></valueflags></lists>')
        (root/'areaflags.map').write_bytes(struct.pack('<6I',1,1,10,10,32,0)+b'\0\0\0\0\1')
        (root/'mapgrouppos.xml').write_text('<map><group name="House" pos="5 0 5"/></map>')
        (root/'mapgroupproto.xml').write_text('<map><group name="House" lootmax="1"><usage name="Town"/>'+container+'</group></map>')

    def test_categories_compete_for_shared_group_capacity(self):
        rows = [f'<type name="{name}"><nominal>1</nominal><usage name="Town"/><category name="{name}"/></type>'
                for name in ('tools','clothes')]
        containers = ''.join(f'<container lootmax="1"><category name="{name}"/><point/></container>'
                             for name in ('tools','clothes'))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root, rows, containers)
            result = pressure.feasibility(root)
            self.assertEqual(set(result['categories']), {'tools','clothes'})
            self.assertEqual(result['demand'], len(rows))
            self.assertEqual(result['deficit'], len(rows)-1)
            self.assertEqual(result['unreachable_nominal'], 0)

    def test_tag_and_actual_tier_exclude_rows_even_with_spare_category_slots(self):
        rows = ['<type name="Tool"><nominal>1</nominal><usage name="Town"/><category name="tools"/>'
                '<tag name="floor"/></type>']
        container = '<container lootmax="1"><category name="tools"/><tag name="shelves"/><point/></container>'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root, rows, container)
            result = pressure.feasibility(root)
            self.assertEqual(result['unreachable_nominal'], result['demand'])
            (root/'db/types.xml').write_text('<types>'+rows[0].replace('floor','shelves')+'</types>')
            self.assertEqual(pressure.feasibility(root)['status'], 'pass')
            (root/'db/types.xml').write_text('<types>'+rows[0].replace('floor','shelves').replace('</type>', '<value name="Tier2"/></type>')+'</types>')
            self.assertEqual(pressure.feasibility(root)['status'], 'fail')
