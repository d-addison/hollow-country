"""Synthetic PBO/rapified-config fixtures. Offline: these never establish DayZ behaviour."""
from pathlib import Path
import struct
import tempfile
import unittest

from tools.audit import pbo_config


def cint(n):
    if n < 128:
        return bytes([n])
    return bytes([(n % 128) | 0x80, n // 128 + 1])


def rap(tree):
    """Encode a nested dict as a minimal rapified config (class body = dict with __parent__)."""
    out = bytearray(b'\0raP' + struct.pack('<III', 0, 8, 0))
    patches = []

    def write_body(parent, fields):
        out.extend(parent.encode() + b'\0' + cint(len(fields)))
        for name, value in fields:
            if isinstance(value, dict):
                out.extend(b'\x00' + name.encode() + b'\0')
                patches.append((len(out), value))
                out.extend(b'\0\0\0\0')
            elif isinstance(value, list):
                out.extend(b'\x02' + name.encode() + b'\0' + cint(len(value)))
                for v in value:
                    if isinstance(v, str):
                        out.extend(b'\x00' + v.encode() + b'\0')
                    elif isinstance(v, float):
                        out.extend(b'\x01' + struct.pack('<f', v))
                    else:
                        out.extend(b'\x02' + struct.pack('<i', v))
            elif isinstance(value, str):
                out.extend(b'\x01\x00' + name.encode() + b'\0' + value.encode() + b'\0')
            elif isinstance(value, float):
                out.extend(b'\x01\x01' + name.encode() + b'\0' + struct.pack('<f', value))
            elif value is None:
                out.extend(b'\x03' + name.encode() + b'\0')
            else:
                out.extend(b'\x01\x02' + name.encode() + b'\0' + struct.pack('<i', value))

    def emit(node):
        write_body(node['__parent__'], [(k, v) for k, v in node.items() if k != '__parent__'])

    emit(tree)
    while patches:
        pos, child = patches.pop(0)
        out[pos:pos + 4] = struct.pack('<I', len(out))
        emit(child)
    return bytes(out)


def pbo(entries, prefix='dz\\weapons\\test'):
    """Uncompressed PBO with a Vers header entry and a trailer."""
    header = bytearray()
    header += b'\0' + struct.pack('<IIIII', 0x56657273, 0, 0, 0, 0)
    header += b'prefix\0' + prefix.encode() + b'\0\0'
    for name, data in entries.items():
        header += name.encode() + b'\0' + struct.pack('<IIIII', 0, len(data), 0, 0, len(data))
    header += b'\0' + struct.pack('<IIIII', 0, 0, 0, 0, 0)
    return bytes(header) + b''.join(entries.values()) + b'\0' + b'\x11' * 20


def klass(parent='', **fields):
    return dict(__parent__=parent, **fields)


SAMPLE = klass(
    '', CfgWeapons=klass(
        '', Weapon_Base=klass('', scope=0),
        Rifle_Base=klass('Weapon_Base', scope=1, magazines=['Mag_A', 'Mag_B']),
        Hunter=klass('Rifle_Base', scope=2, model='\\dz\\weapons\\test\\hunter.p3d',
                     displayName='Hunter', magazines=['Mag_A'],
                     chamberableFrom=['Bullet_A', 'Bullet_B'], handAnim=['Idle', 'dz\\w\\a.rtm']),
        Hunter_Black=klass('Hunter'),
        Hidden=klass('Rifle_Base', scope=0),
        Orphan=klass('NotThere'),
        Ext=None),
    cfgMagazines=klass('', Mag_A=klass('', scope=2, ammo='Bullet_A', count=10.0)),
)


class TextHardening(unittest.TestCase):
    def test_unresolved_conditionals_are_refused(self):
        """SYNTHETIC inactive classes must never become verification evidence."""
        for directive in ('#ifdef OMIT', '#ifndef OMIT', '#if 0', '#else', '#endif', '#elif 1', '# if 0',
                          '/*SYNTHETIC prefix*/ #if 0', '#/**/if 0'):
            config = directive + '\nclass CfgWeapons { class SynHidden { scope=2; }; };'
            with self.subTest(directive=directive), self.assertRaisesRegex(ValueError, 'conditional'):
                pbo_config.parse_text_config(config, ['CfgWeapons'])
        pbo_config.parse_text_config('// #if 0\n/* #endif */\nclass CfgWeapons { class Syn {model="#else";};};',
                                     ['CfgWeapons'])

    def test_local_array_assignment_and_appends_accumulate(self):
        """SYNTHETIC complete local arrays stay complete; inherited appends stay unresolved."""
        config = '''class CfgWeapons {
            class Syn {magazines[]={"A"}; magazines[]+={"B"}; magazines[]+={"C"};};
            class SynInherited: Unknown {magazines[]+={"B"}; magazines[]+={"C"};};
            class SynReset: Unknown {magazines[]+={"B"}; magazines[]={"A"}; magazines[]+={"C"};};
        };'''
        rows = pbo_config.parse_text_config(config, ['CfgWeapons'])['CfgWeapons']
        self.assertEqual(rows['Syn']['magazines'], ['A', 'B', 'C'])
        self.assertNotIn('magazines', rows['Syn'].get('appended', []))
        self.assertEqual(rows['SynInherited']['magazines'], ['B', 'C'])
        self.assertIn('magazines', rows['SynInherited']['appended'])
        self.assertEqual(rows['SynReset']['magazines'], ['A', 'C'])
        self.assertNotIn('magazines', rows['SynReset'].get('appended', []))


class RapParsing(unittest.TestCase):
    def test_reads_classes_scope_and_selected_fields_only(self):
        roots = pbo_config.parse_rap(rap(SAMPLE), roots=('CfgWeapons', 'CfgMagazines'))
        weapons = roots['CfgWeapons']
        self.assertEqual(weapons['Hunter']['parent'], 'Rifle_Base')
        self.assertEqual(weapons['Hunter']['scope'], 2)
        self.assertEqual(weapons['Hunter']['model'], '\\dz\\weapons\\test\\hunter.p3d')
        self.assertEqual(weapons['Hunter']['magazines'], ['Mag_A'])
        self.assertEqual(weapons['Hunter']['chamberableFrom'], ['Bullet_A', 'Bullet_B'])
        self.assertEqual(weapons['Hunter']['handAnim'], ['Idle', 'dz\\w\\a.rtm'])
        self.assertNotIn('displayName', weapons['Hunter'])
        self.assertIsNone(weapons['Hunter_Black']['scope'])  # inherited, not own
        self.assertEqual(roots['CfgMagazines']['Mag_A']['ammo'], 'Bullet_A')
        self.assertEqual(roots['CfgMagazines']['Mag_A']['count'], 10)

    def test_rejects_bad_magic_truncation_and_unknown_entry(self):
        for bad in (b'', b'notraP' * 4, rap(SAMPLE)[:30]):
            with self.subTest(size=len(bad)), self.assertRaises(ValueError):
                pbo_config.parse_rap(bad, roots=('CfgWeapons',))
        data = bytearray(rap(SAMPLE))
        data[16 + 2] = 9  # corrupt the first root entry type
        with self.assertRaises(ValueError):
            pbo_config.parse_rap(bytes(data), roots=('CfgWeapons',))

    def test_oversized_input_is_refused(self):
        with self.assertRaises(ValueError):
            pbo_config.parse_rap(rap(SAMPLE), roots=('CfgWeapons',), max_bytes=20)


class ScopeResolution(unittest.TestCase):
    def setUp(self):
        self.classes = pbo_config.parse_rap(rap(SAMPLE), roots=('CfgWeapons',))['CfgWeapons']

    def test_scope_walks_parents_and_reports_unresolved(self):
        self.assertEqual(pbo_config.resolve_scope(self.classes, 'Hunter_Black'), 2)
        self.assertEqual(pbo_config.resolve_scope(self.classes, 'Rifle_Base'), 1)
        self.assertEqual(pbo_config.resolve_scope(self.classes, 'Hidden'), 0)
        self.assertIsNone(pbo_config.resolve_scope(self.classes, 'Orphan'))
        self.assertIsNone(pbo_config.resolve_scope(self.classes, 'Missing'))

    def test_field_resolution_walks_parents(self):
        self.assertEqual(pbo_config.resolve_field(self.classes, 'Hunter_Black', 'magazines'), ['Mag_A'])
        self.assertEqual(pbo_config.resolve_field(self.classes, 'Hidden', 'magazines'), ['Mag_A', 'Mag_B'])
        self.assertIsNone(pbo_config.resolve_field(self.classes, 'Orphan', 'magazines'))

    def test_ancestry_is_bounded_and_cycle_safe(self):
        cyc = {'A': {'parent': 'B', 'scope': None}, 'B': {'parent': 'A', 'scope': None}}
        self.assertIsNone(pbo_config.resolve_scope(cyc, 'A'))
        self.assertEqual(pbo_config.ancestry(cyc, 'A'), ['A', 'B'])
        self.assertEqual(pbo_config.ancestry(self.classes, 'Hunter_Black'),
                         ['Hunter_Black', 'Hunter', 'Rifle_Base', 'Weapon_Base'])


class PboReading(unittest.TestCase):
    def test_index_and_member_reading_are_bounded_and_streamed(self):
        raw = pbo({'config.bin': rap(SAMPLE), 'hunter.p3d': b'MLOD', 'sub\\x.rtm': b'1'})
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / 'weapons_test.pbo'
            path.write_bytes(raw)
            index = pbo_config.read_pbo_index(path)
            self.assertEqual(index['prefix'], 'dz\\weapons\\test')
            self.assertEqual([e['name'] for e in index['entries']],
                             ['config.bin', 'hunter.p3d', 'sub\\x.rtm'])
            self.assertEqual(pbo_config.read_member(path, index, 'config.bin'), rap(SAMPLE))
            self.assertIsNone(pbo_config.read_member(path, index, 'nothing.bin'))
            with self.assertRaises(ValueError):
                pbo_config.read_member(path, index, 'config.bin', max_bytes=10)
            self.assertIn('dz\\weapons\\test\\hunter.p3d', pbo_config.model_paths(index))

    def test_nested_config_members_are_found_and_merged(self):
        other = klass('', CfgWeapons=klass('', Second=klass('Hunter', scope=2)))
        raw = pbo({'config.bin': rap(SAMPLE), 'AK74\\config.bin': rap(other), 'x.paa': b'1'})
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / 'w.pbo'
            path.write_bytes(raw)
            index = pbo_config.read_pbo_index(path)
            self.assertEqual(pbo_config.config_member_names(index), ['config.bin', 'AK74\\config.bin'])
            merged = pbo_config.read_configs(path, ('CfgWeapons',))
            self.assertIn('Hunter', merged['CfgWeapons'])
            self.assertEqual(merged['CfgWeapons']['Second']['parent'], 'Hunter')

    def test_compressed_member_and_truncated_header_are_refused(self):
        raw = bytearray(pbo({'config.bin': b'abcd'}))
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / 'x.pbo'
            path.write_bytes(bytes(raw[:25]))
            with self.assertRaises(ValueError):
                pbo_config.read_pbo_index(path)
            marker = raw.index(b'config.bin\0') + len(b'config.bin\0')
            raw[marker:marker + 4] = struct.pack('<I', 0x43707273)
            path.write_bytes(bytes(raw))
            index = pbo_config.read_pbo_index(path)
            with self.assertRaises(ValueError):
                pbo_config.read_member(path, index, 'config.bin')

    def test_header_entry_count_budget(self):
        raw = pbo({f'f{i}.bin': b'x' for i in range(5)})
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / 'x.pbo'
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                pbo_config.read_pbo_index(path, max_entries=3)


if __name__ == '__main__':
    unittest.main()
