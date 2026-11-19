"""Behavior of the tenement CE coverage tool (#11, #41).

Every fixture here is SYNTHETIC. The point coordinates, the run id and the pins are invented for the test only;
nothing here observes DayZ and none of it may ever be shipped under mission/. Offline tests never establish
engine behavior.
"""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from tools.package import ce_coverage as cc
from tools.package import economy, gameplay, snafu_optional, tactical_flava_optional
from tools.setup import interior_sampler

REPO = Path(__file__).resolve().parents[2]
RUN_ID = 'ab' * 16  # SYNTHETIC
PIN = hashlib.sha256(b'synthetic pin').hexdigest()


def group(name, lootmax='0', containers=('lootFloor', 'lootShelves', 'lootWeapons'), eol='\n'):
    lines = ['\t<group name="%s" lootmax="%s">' % (name, lootmax), '\t\t<usage name="Town" />']
    for c in containers:
        lines += ['\t\t<container name="%s" lootmax="0">' % c, '\t\t\t<category name="tools" />',
                  '\t\t\t<tag name="floor" />', '\t\t</container>']
    lines.append('\t</group>')
    return eol.join(lines) + eol


BARRACKS = ('\t<group name="Land_Mil_Barracks2" lootmax="10">\n\t\t<usage name="Military" />\n'
            '\t\t<container name="lootFloor" lootmax="10">\n\t\t\t<point pos="1.000000 0.100000 2.000000" range="1.5" height="2" flags="32" />\n'
            '\t\t</container>\n\t</group>\n')


def stock_proto(eol='\n', small=None, big=None):
    text = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<prototype>\n\t<defaults>\n\t\t<default lootmax="1" />\n'
            '\t</defaults>\n' + group('Land_Tenement_Small', eol='\n') + BARRACKS
            + group('Land_Tenement_Big', eol='\n') + '</prototype>\n')
    if small is not None:
        text = text.replace(group('Land_Tenement_Small'), small)
    if big is not None:
        text = text.replace(group('Land_Tenement_Big'), big)
    return text.replace('\n', eol).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def result_doc(stock=None, **overrides):
    stock = stock_proto() if stock is None else stock
    doc = {'schema': 1, 'kind': 'ce-coverage-sampler-result', 'native_run_id': RUN_ID, 'frame': 'stock',
           'pins': {'mapgroupproto_sha256': sha(stock), 'census_sha256': PIN, 'hook_sha256': PIN},
           'groups': {
               'Land_Tenement_Small': {'bounds': {'min': [-10.0, -1.0, -10.0], 'max': [10.0, 8.0, 10.0]},
                                       'containers': {'lootFloor': [[1.0, 0.1, 2.0], [-3.5, 0.1, 4.25], [2.0, 3.1, -1.0]]}},
               'Land_Tenement_Big': {'bounds': {'min': [-20.0, -1.0, -20.0], 'max': [20.0, 12.0, 20.0]},
                                     'containers': {'lootFloor': [[5.0, 0.1, 5.0]],
                                                    'lootShelves': [[6.0, 0.9, 5.0]]}}}}
    doc.update(overrides)
    return doc


def blob(doc):
    return json.dumps(doc).encode()


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='hc-cecov-'))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.mission = self.tmp / 'mission'
        self.mission.mkdir()
        self.stock = stock_proto()
        (self.mission / 'mapgroupproto.xml').write_bytes(self.stock)
        (self.mission / 'cfgeconomycore.xml').write_bytes(b'<economycore/>')

    def result_path(self, doc=None, name='result.json'):
        path = self.tmp / name
        path.write_bytes(blob(result_doc(self.stock) if doc is None else doc))
        return path

    def stage(self, doc=None, name='delta'):
        out = self.tmp / name
        cc.write_delta(out, cc.generate(self.result_path(doc).read_bytes(), self.mission))
        return out

    def proto(self):
        return (self.mission / 'mapgroupproto.xml').read_bytes()


class ContractTests(Fixture):
    def test_managed_folder_collides_with_no_other_installer(self):
        others = {economy.MANAGED, gameplay.MANAGED, snafu_optional.MANAGED, tactical_flava_optional.MANAGED}
        self.assertNotIn(cc.MANAGED, others)
        for other in others:  # also no nesting either way
            self.assertFalse(cc.MANAGED.startswith(other + '/') or other.startswith(cc.MANAGED + '/'))

    def test_sampler_already_samples_both_tenement_classes(self):
        classes = {name for name, _role in interior_sampler.SAMPLE_CLASSES}
        self.assertEqual(set(cc.TARGET_GROUPS), set(cc.TARGET_GROUPS) & classes)
        self.assertEqual(cc.TARGET_GROUPS, ('Land_Tenement_Small', 'Land_Tenement_Big'))

    def test_shipped_mission_carries_no_apartment_point_data(self):
        # HC-57 design inputs are permitted; they are not native sampler results or installed deltas.
        authored = {REPO / 'mission/hollow-country/ce-coverage' / name
                    for name in ('apartments.json', 'municipal-office.json')}
        for path in (REPO / 'mission').rglob('*'):
            if path.is_file() and path.suffix != '.md':
                if path in authored:
                    cc.parse_input(path.read_bytes())
                    continue
                self.assertNotIn(b'Land_Tenement', path.read_bytes(), path.name)


class RequestTests(Fixture):
    def test_request_names_both_classes_pins_and_the_native_sampler_command(self):
        data = cc.request(self.mission)
        doc = json.loads(data)
        self.assertEqual(doc['kind'], 'ce-coverage-request')
        self.assertEqual([c['class'] for c in doc['classes']], list(cc.TARGET_GROUPS))
        self.assertEqual(doc['sources']['mapgroupproto.xml'], sha(self.stock))
        self.assertEqual(doc['sampler']['tool'], 'tools/setup/interior_sampler.py')
        self.assertIn('--destination', doc['sampler']['command'])
        self.assertEqual(doc['runtime_acceptance'], 'pending')
        self.assertEqual(doc['result_contract']['frame'], 'stock')
        self.assertEqual(data, cc.request(self.mission))  # deterministic

    def test_request_refuses_a_group_that_is_not_an_empty_shell(self):
        (self.mission / 'mapgroupproto.xml').write_bytes(stock_proto(small=group('Land_Tenement_Small', lootmax='3')))
        with self.assertRaisesRegex(ValueError, 'empty'):
            cc.request(self.mission)

    def test_request_file_is_fresh_and_never_inside_the_shipped_mission(self):
        out = self.tmp / 'request.json'
        cc.write_request(out, cc.request(self.mission))
        with self.assertRaises(ValueError):
            cc.write_request(out, cc.request(self.mission))
        with self.assertRaisesRegex(ValueError, 'shipped mission'):
            cc.write_request(REPO / 'mission' / 'hollow-country' / 'request.json', b'{}')
        self.assertFalse((REPO / 'mission' / 'hollow-country' / 'request.json').exists())


class ResultValidationTests(Fixture):
    def refuse(self, doc, pattern):
        with self.assertRaisesRegex(ValueError, pattern):
            cc.generate(blob(doc), self.mission)

    def test_refuses_a_result_without_a_native_run_id(self):
        doc = result_doc(self.stock)
        del doc['native_run_id']
        self.refuse(doc, 'native_run_id|keys')
        for bad in ('', 'native', 'AB' * 16, 'ab' * 15, 7, None, 'ab' * 16 + '0'):
            with self.subTest(bad=bad):
                self.refuse(result_doc(self.stock, native_run_id=bad), 'native run id')

    def test_refuses_missing_or_malformed_pins(self):
        for pin in ('mapgroupproto_sha256', 'census_sha256', 'hook_sha256'):
            doc = result_doc(self.stock)
            del doc['pins'][pin]
            with self.subTest(missing=pin):
                self.refuse(doc, 'pins')
            doc = result_doc(self.stock)
            doc['pins'][pin] = 'xyz'
            with self.subTest(bad=pin):
                self.refuse(doc, 'SHA-256')

    def test_refuses_a_result_pinned_to_other_mapgroupproto_bytes(self):
        doc = result_doc(self.stock)
        doc['pins']['mapgroupproto_sha256'] = sha(b'another file')
        self.refuse(doc, 'mapgroupproto')

    def test_refuses_the_wrong_frame_and_unknown_keys(self):
        self.refuse(result_doc(self.stock, frame='sampler'), 'frame')
        self.refuse(result_doc(self.stock, extra=1), 'keys')
        doc = result_doc(self.stock)
        doc['groups']['Land_Tenement_Small']['note'] = 'x'
        self.refuse(doc, 'keys')

    def test_only_the_two_tenement_groups_can_be_treated(self):
        doc = result_doc(self.stock)
        doc['groups']['Land_Mil_Barracks2'] = copy.deepcopy(doc['groups']['Land_Tenement_Small'])
        self.refuse(doc, 'tenement')
        doc = result_doc(self.stock)
        doc['groups'] = {}
        self.refuse(doc, 'at least one')

    def test_refuses_points_outside_the_prototype_bounds(self):
        for axis in range(3):
            for value in (-10.5, 12.0):
                doc = result_doc(self.stock)
                point = [0.0, 0.0, 0.0]
                point[axis] = value
                doc['groups']['Land_Tenement_Small']['containers']['lootFloor'].append(point)
                with self.subTest(axis=axis, value=value):
                    self.refuse(doc, 'outside')

    def test_refuses_duplicate_points_in_and_across_containers(self):
        doc = result_doc(self.stock)
        doc['groups']['Land_Tenement_Small']['containers']['lootFloor'].append([1.0, 0.1, 2.0])
        self.refuse(doc, 'duplicate')
        doc = result_doc(self.stock)
        doc['groups']['Land_Tenement_Big']['containers']['lootShelves'].append([5.0000004, 0.1, 5.0])
        self.refuse(doc, 'duplicate')

    def test_refuses_more_points_than_the_reviewed_cap(self):
        doc = result_doc(self.stock)
        doc['groups']['Land_Tenement_Small']['containers']['lootFloor'] = [
            [float(i) * 0.5 - 5.0, 0.1, 1.0] for i in range(cc.MAX_POINTS_PER_CONTAINER + 1)]
        self.refuse(doc, 'cap')
        doc['groups']['Land_Tenement_Small']['containers']['lootFloor'].pop()
        cc.generate(blob(doc), self.mission)  # exactly the cap is fine

    def test_refuses_bad_numbers_and_empty_containers(self):
        for bad in (float('nan'), float('inf'), True, '1', None, 1e9):
            doc = result_doc(self.stock)
            doc['groups']['Land_Tenement_Small']['containers']['lootFloor'][0][0] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                cc.generate(json.dumps(doc).encode(), self.mission)
        doc = result_doc(self.stock)
        doc['groups']['Land_Tenement_Small']['containers']['lootFloor'] = []
        self.refuse(doc, 'at least one point')
        doc = result_doc(self.stock)
        doc['groups']['Land_Tenement_Small']['containers']['lootFloor'][0] = [1.0, 2.0]
        self.refuse(doc, 'three')

    def test_refuses_degenerate_bounds_and_invalid_json(self):
        doc = result_doc(self.stock)
        doc['groups']['Land_Tenement_Small']['bounds']['max'] = [-20.0, 8.0, 10.0]
        self.refuse(doc, 'bounds')
        for data in (b'', b'[]', b'{"a": NaN}', b'\xff\xfe'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                cc.generate(data, self.mission)

    def test_refuses_a_container_the_stock_group_does_not_have(self):
        doc = result_doc(self.stock)
        doc['groups']['Land_Tenement_Small']['containers'] = {'lootNowhere': [[1.0, 0.1, 2.0]]}
        self.refuse(doc, 'container')

    def test_refuses_stock_that_is_not_an_empty_shell(self):
        for stock in (stock_proto(small=group('Land_Tenement_Small', lootmax='2')),
                      stock_proto(small=group('Land_Tenement_Small').replace(
                          '\t\t\t<tag name="floor" />', '\t\t\t<point pos="1 1 1" />', 1))):
            (self.mission / 'mapgroupproto.xml').write_bytes(stock)
            with self.subTest(), self.assertRaisesRegex(ValueError, 'empty|authored'):
                cc.generate(blob(result_doc(stock)), self.mission)


class GenerateTests(Fixture):
    def test_delta_is_deterministic_regardless_of_point_order(self):
        doc = result_doc(self.stock)
        first = cc.generate(blob(doc), self.mission)
        shuffled = copy.deepcopy(doc)
        shuffled['groups'] = dict(reversed(list(shuffled['groups'].items())))
        shuffled['groups']['Land_Tenement_Small']['containers']['lootFloor'].reverse()
        self.assertEqual(first, cc.generate(blob(shuffled), self.mission))
        self.assertEqual(first, cc.generate(blob(doc), self.mission))

    def test_lootmax_is_conservative_and_capped(self):
        files = cc.generate(blob(result_doc(self.stock)), self.mission)
        delta = json.loads(files['coverage-delta.json'])
        small = delta['groups']['Land_Tenement_Small']
        self.assertEqual(small['containers']['lootFloor']['lootmax'], 1)  # 3 points * 0.25 rounded up
        self.assertEqual(small['lootmax'], 1)
        doc = result_doc(self.stock)
        small_doc = doc['groups']['Land_Tenement_Small']
        small_doc['containers'] = {name: [[x * 0.5 - 4.0 + k, 0.1, 1.0 + k * 0.01] for x in range(cc.MAX_POINTS_PER_CONTAINER)]
                                   for k, name in enumerate(('lootFloor', 'lootShelves', 'lootWeapons'))}
        delta = json.loads(cc.generate(blob(doc), self.mission)['coverage-delta.json'])
        small = delta['groups']['Land_Tenement_Small']
        for container in small['containers'].values():
            self.assertLessEqual(container['lootmax'], cc.MAX_CONTAINER_LOOTMAX)
        self.assertLessEqual(small['lootmax'], cc.MAX_GROUP_LOOTMAX)

    def test_delta_is_pinned_pending_and_records_the_native_run(self):
        files = cc.generate(blob(result_doc(self.stock)), self.mission)
        manifest = json.loads(files['delta-manifest.json'])
        self.assertEqual(manifest['runtime_acceptance'], 'pending')
        self.assertEqual(manifest['sources'], {'mapgroupproto.xml': sha(self.stock)})
        self.assertEqual(manifest['files'], {'coverage-delta.json': sha(files['coverage-delta.json'])})
        self.assertEqual(json.loads(files['coverage-delta.json'])['native_run_id'], RUN_ID)

    def test_stage_directory_is_fresh_and_never_inside_the_shipped_mission(self):
        out = self.stage()
        self.assertEqual({p.name for p in out.iterdir()}, {'coverage-delta.json', 'delta-manifest.json'})
        with self.assertRaises(ValueError):
            cc.write_delta(out, cc.generate(self.result_path().read_bytes(), self.mission))
        with self.assertRaisesRegex(ValueError, 'shipped mission'):
            cc.write_delta(REPO / 'mission' / 'hollow-country' / 'ce-coverage-stage', {})
        self.assertFalse((REPO / 'mission' / 'hollow-country' / 'ce-coverage-stage').exists())


class ApplyTests(Fixture):
    def apply(self, stock=None):
        stock = self.stock if stock is None else stock
        (self.mission / 'mapgroupproto.xml').write_bytes(stock)
        delta = json.loads(cc.generate(blob(result_doc(stock)), self.mission)['coverage-delta.json'])
        return cc.apply_delta(stock, delta)

    def test_only_the_two_tenement_groups_change_and_points_land_in_existing_containers(self):
        patched = self.apply()
        before, after = ET.fromstring(self.stock), ET.fromstring(patched)
        groups_before = {g.get('name'): g for g in before.iter('group')}
        groups_after = {g.get('name'): g for g in after.iter('group')}
        self.assertEqual(list(groups_before), list(groups_after))
        self.assertEqual(ET.tostring(groups_before['Land_Mil_Barracks2']), ET.tostring(groups_after['Land_Mil_Barracks2']))
        small = groups_after['Land_Tenement_Small']
        self.assertEqual(small.get('lootmax'), '1')
        floor = [c for c in small.findall('container') if c.get('name') == 'lootFloor'][0]
        self.assertEqual([p.get('pos') for p in floor.findall('point')],
                         ['-3.500000 0.100000 4.250000', '1.000000 0.100000 2.000000', '2.000000 3.100000 -1.000000'])
        self.assertEqual(floor.get('lootmax'), '1')
        for other in small.findall('container'):
            if other.get('name') != 'lootFloor':
                self.assertEqual((other.get('lootmax'), other.findall('point')), ('0', []))
        big = groups_after['Land_Tenement_Big']
        self.assertEqual({c.get('name'): len(c.findall('point')) for c in big.findall('container')},
                         {'lootFloor': 1, 'lootShelves': 1, 'lootWeapons': 0})
        # structure (usage/container/category/tag) is untouched
        skeleton = lambda g: [(e.tag, e.get('name')) for e in g.iter() if e.tag in ('usage', 'container', 'category', 'tag')]
        self.assertEqual(skeleton(groups_before['Land_Tenement_Big']), skeleton(big))

    def test_bytes_outside_the_edited_groups_are_identical(self):
        patched = self.apply().decode()
        stock = self.stock.decode()
        head = stock.index('<group name="Land_Tenement_Small"') - 1
        self.assertTrue(patched.startswith(stock[:head]))
        barracks = stock[stock.index(BARRACKS):stock.index(BARRACKS) + len(BARRACKS)]
        self.assertIn(barracks, patched)
        self.assertTrue(patched.endswith('</prototype>\n'))

    def test_crlf_files_keep_their_line_endings(self):
        stock = stock_proto(eol='\r\n')
        patched = self.apply(stock)
        self.assertEqual(patched.count(b'\n'), patched.count(b'\r\n'))
        self.assertIn(b'<point pos="1.000000 0.100000 2.000000"', patched)

    def test_a_bom_is_preserved(self):
        stock = b'\xef\xbb\xbf' + self.stock
        self.assertTrue(self.apply(stock).startswith(b'\xef\xbb\xbf'))

    def test_group_or_container_that_is_not_unique_or_open_is_refused(self):
        twice = self.stock.replace(b'</prototype>', group('Land_Tenement_Small').encode() + b'</prototype>')
        (self.mission / 'mapgroupproto.xml').write_bytes(twice)
        with self.assertRaises(ValueError):
            cc.generate(blob(result_doc(twice)), self.mission)
        selfclosed = stock_proto(small=group('Land_Tenement_Small').replace(
            '\t\t<container name="lootFloor" lootmax="0">\n\t\t\t<category name="tools" />\n\t\t\t<tag name="floor" />\n\t\t</container>',
            '\t\t<container name="lootFloor" lootmax="0" />'))
        (self.mission / 'mapgroupproto.xml').write_bytes(selfclosed)
        with self.assertRaises(ValueError):
            cc.generate(blob(result_doc(selfclosed)), self.mission)

    def test_dtd_and_non_utf8_proto_is_refused(self):
        for data in (b'<!DOCTYPE x [<!ENTITY a "b">]>' + self.stock, b'\xff\xfe' + self.stock):
            (self.mission / 'mapgroupproto.xml').write_bytes(data)
            with self.subTest(), self.assertRaises(ValueError):
                cc.request(self.mission)


class InstallRollbackTests(Fixture):
    def test_install_patches_in_place_and_rollback_is_byte_exact(self):
        stage = self.stage()
        receipt = cc.install(stage, self.mission)
        self.assertEqual(receipt['before'], sha(self.stock))
        self.assertNotEqual(self.proto(), self.stock)
        self.assertEqual(sha(self.proto()), receipt['after'])
        managed = self.mission / cc.MANAGED
        self.assertEqual({p.name for p in managed.iterdir()},
                         {'receipt.json', 'mapgroupproto.backup', 'coverage-delta.json'})
        self.assertEqual((managed / 'mapgroupproto.backup').read_bytes(), self.stock)
        cc.rollback(self.mission)
        self.assertEqual(self.proto(), self.stock)
        self.assertFalse(managed.exists())

    def test_install_preserves_file_mode(self):
        path = self.mission / 'mapgroupproto.xml'
        os.chmod(path, 0o640)
        cc.install(self.stage(), self.mission)
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o640)

    def test_a_second_install_is_refused(self):
        stage = self.stage()
        cc.install(stage, self.mission)
        with self.assertRaisesRegex(ValueError, 'already installed'):
            cc.install(stage, self.mission)

    def test_install_refuses_a_mission_that_differs_from_the_pinned_source(self):
        stage = self.stage()
        (self.mission / 'mapgroupproto.xml').write_bytes(self.stock + b'<!-- drift -->\n')
        with self.assertRaisesRegex(ValueError, 'source'):
            cc.install(stage, self.mission)
        self.assertFalse((self.mission / cc.MANAGED).exists())

    def test_install_refuses_a_tampered_or_incomplete_stage(self):
        stage = self.stage()
        delta = stage / 'coverage-delta.json'
        doc = json.loads(delta.read_bytes())
        doc['groups']['Land_Tenement_Small']['lootmax'] = 11
        delta.write_bytes(json.dumps(doc, sort_keys=True, indent=2).encode() + b'\n')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            cc.install(stage, self.mission)
        # a re-hashed but inconsistent delta is refused on content, not only on checksum
        manifest = json.loads((stage / 'delta-manifest.json').read_bytes())
        manifest['files']['coverage-delta.json'] = sha(delta.read_bytes())
        (stage / 'delta-manifest.json').write_bytes(json.dumps(manifest, sort_keys=True, indent=2).encode() + b'\n')
        with self.assertRaises(ValueError):
            cc.install(stage, self.mission)
        (stage / 'extra.txt').write_bytes(b'x')
        with self.assertRaisesRegex(ValueError, 'stage files'):
            cc.install(stage, self.mission)
        self.assertEqual(self.proto(), self.stock)

    def test_receipt_and_backup_exist_before_the_switch_and_an_interrupted_install_rolls_back(self):
        stage = self.stage()
        with mock.patch.object(cc.os, 'replace', side_effect=OSError('killed')):
            with self.assertRaises(OSError):
                cc.install(stage, self.mission)
        managed = self.mission / cc.MANAGED
        self.assertTrue((managed / 'receipt.json').is_file())
        self.assertEqual((managed / 'mapgroupproto.backup').read_bytes(), self.stock)
        self.assertEqual(self.proto(), self.stock)  # the switch never happened
        with self.assertRaisesRegex(ValueError, 'interrupted|already installed'):
            cc.install(stage, self.mission)
        cc.rollback(self.mission)
        self.assertEqual(self.proto(), self.stock)
        self.assertFalse(managed.exists())
        cc.install(stage, self.mission)  # and a clean install works again afterwards
        cc.rollback(self.mission)
        self.assertEqual(self.proto(), self.stock)

    def test_an_install_killed_after_the_switch_rolls_back_from_the_backup(self):
        stage = self.stage()
        receipt = cc.install(stage, self.mission)
        managed = self.mission / cc.MANAGED
        (managed / 'mapgroupproto.next').write_bytes(b'stale partial file')  # leftover staging
        cc.rollback(self.mission)
        self.assertEqual(self.proto(), self.stock)
        self.assertFalse(managed.exists())
        self.assertEqual(receipt['before'], sha(self.stock))

    def test_installs_killed_before_the_receipt_or_mid_receipt_leave_the_mission_untouched(self):
        managed = self.mission / cc.MANAGED
        managed.mkdir()
        cc.rollback(self.mission)  # empty managed folder: nothing was changed
        self.assertFalse(managed.exists())
        managed.mkdir()
        (managed / 'receipt.json').write_bytes(b'{"schema": 1, "bef')  # killed mid-receipt, no backup yet
        cc.rollback(self.mission)
        self.assertFalse(managed.exists())
        self.assertEqual(self.proto(), self.stock)
        managed.mkdir()
        (managed / 'receipt.json').write_bytes(b'{"schema": 1, "bef')
        (managed / 'mapgroupproto.backup').write_bytes(self.stock)  # a backup next to a corrupt receipt is not a safe state
        with self.assertRaises(ValueError):
            cc.rollback(self.mission)
        self.assertTrue(managed.exists())

    def test_rollback_refuses_drift_and_leaves_everything_in_place(self):
        cc.install(self.stage(), self.mission)
        patched = self.proto()
        (self.mission / 'mapgroupproto.xml').write_bytes(patched + b'<!-- hand edit -->\n')
        with self.assertRaisesRegex(ValueError, 'drift'):
            cc.rollback(self.mission)
        self.assertTrue((self.mission / cc.MANAGED).exists())
        (self.mission / 'mapgroupproto.xml').write_bytes(patched)
        (self.mission / cc.MANAGED / 'mapgroupproto.backup').write_bytes(self.stock + b'x')
        with self.assertRaisesRegex(ValueError, 'backup'):
            cc.rollback(self.mission)
        self.assertEqual(self.proto(), patched)
        (self.mission / cc.MANAGED / 'mapgroupproto.backup').write_bytes(self.stock)
        (self.mission / cc.MANAGED / 'coverage-delta.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'delta'):
            cc.rollback(self.mission)
        self.assertEqual(self.proto(), patched)

    def test_rollback_refuses_unexpected_managed_content(self):
        cc.install(self.stage(), self.mission)
        managed = self.mission / cc.MANAGED
        (managed / 'notes.txt').write_bytes(b'mine')
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            cc.rollback(self.mission)
        (managed / 'notes.txt').unlink()
        (managed / 'ce').mkdir()
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            cc.rollback(self.mission)
        self.assertTrue(managed.exists())
        self.assertNotEqual(self.proto(), self.stock)

    def test_symlinked_mapgroupproto_is_refused(self):
        real = self.tmp / 'elsewhere.xml'
        real.write_bytes(self.stock)
        path = self.mission / 'mapgroupproto.xml'
        path.unlink()
        path.symlink_to(real)
        stage = self.tmp / 'delta'
        cc.write_delta(stage, cc.generate(blob(result_doc(self.stock)), self.mission))  # reads are fine, writes are not
        with self.assertRaisesRegex(ValueError, 'symlink|hard link|regular'):
            cc.install(stage, self.mission)
        self.assertEqual(real.read_bytes(), self.stock)
        self.assertFalse((self.mission / cc.MANAGED).exists())

    def test_hard_linked_mapgroupproto_is_refused_so_nothing_outside_the_mission_changes(self):
        stage = self.stage()
        outside = self.tmp / 'outside.xml'
        os.link(self.mission / 'mapgroupproto.xml', outside)
        with self.assertRaisesRegex(ValueError, 'hard link|symlink|regular'):
            cc.install(stage, self.mission)
        self.assertEqual(outside.read_bytes(), self.stock)
        self.assertEqual(self.proto(), self.stock)

    def test_hard_linking_after_install_makes_rollback_refuse(self):
        cc.install(self.stage(), self.mission)
        outside = self.tmp / 'outside.xml'
        os.link(self.mission / 'mapgroupproto.xml', outside)
        patched = outside.read_bytes()
        with self.assertRaisesRegex(ValueError, 'hard link|symlink|regular'):
            cc.rollback(self.mission)
        self.assertEqual(outside.read_bytes(), patched)

    def test_symlinked_managed_folder_and_managed_files_are_refused(self):
        stage = self.stage()
        elsewhere = self.tmp / 'elsewhere'
        elsewhere.mkdir()
        (self.mission / cc.MANAGED).symlink_to(elsewhere)
        with self.assertRaises(ValueError):
            cc.install(stage, self.mission)
        with self.assertRaises(ValueError):
            cc.rollback(self.mission)
        self.assertEqual(list(elsewhere.iterdir()), [])
        (self.mission / cc.MANAGED).unlink()
        cc.install(stage, self.mission)
        backup = self.mission / cc.MANAGED / 'mapgroupproto.backup'
        backup.unlink()
        backup.symlink_to(self.tmp / 'elsewhere.xml')
        (self.tmp / 'elsewhere.xml').write_bytes(self.stock)
        with self.assertRaises(ValueError):
            cc.rollback(self.mission)

    def test_install_refuses_a_steam_installation_path(self):
        steam = self.tmp / 'SteamApps' / 'mission'
        steam.mkdir(parents=True)
        (steam / 'mapgroupproto.xml').write_bytes(self.stock)
        with self.assertRaisesRegex(ValueError, 'Steam|isolated'):
            cc.install(self.stage(), steam)

    def test_coexists_with_the_other_managed_folders_without_touching_them(self):
        for name in (economy.MANAGED, gameplay.MANAGED, snafu_optional.MANAGED, tactical_flava_optional.MANAGED):
            (self.mission / name).mkdir()
            (self.mission / name / 'marker.txt').write_bytes(b'theirs')
            (self.mission / name / 'receipt.json').write_bytes(
                json.dumps({'sources': {'mapgroupproto.xml': sha(self.stock)}}).encode())
        before = (self.mission / 'cfgeconomycore.xml').read_bytes()
        cc.install(self.stage(), self.mission)
        cc.rollback(self.mission)
        self.assertEqual((self.mission / 'cfgeconomycore.xml').read_bytes(), before)
        for name in (economy.MANAGED, gameplay.MANAGED, snafu_optional.MANAGED, tactical_flava_optional.MANAGED):
            self.assertEqual((self.mission / name / 'marker.txt').read_bytes(), b'theirs')


class RecoveryHardeningTests(Fixture):
    def pin_folder(self, name, pinned):
        folder = self.mission / name
        folder.mkdir()
        # the shape economy.py, snafu_optional.py and tactical_flava_optional.py write: sources pin every INPUT
        (folder / 'receipt.json').write_bytes(json.dumps({'schema': 1, 'sources': {'mapgroupproto.xml': pinned}}).encode())
        return folder

    def test_a_backup_without_a_receipt_is_never_cleaned_up(self):
        cc.install(self.stage(), self.mission)
        managed = self.mission / cc.MANAGED
        patched = self.proto()
        (managed / 'receipt.json').unlink()
        with self.assertRaisesRegex(ValueError, 'manual recovery needed'):
            cc.rollback(self.mission)
        self.assertEqual(self.proto(), patched)
        self.assertEqual((managed / 'mapgroupproto.backup').read_bytes(), self.stock)

    def test_economy_installed_on_top_of_coverage_blocks_the_coverage_rollback(self):
        receipt = cc.install(self.stage(), self.mission)
        self.pin_folder(economy.MANAGED, receipt['after'])  # economy generated against the patched file
        patched = self.proto()
        with self.assertRaisesRegex(ValueError, 'installed on top of the coverage'):
            cc.rollback(self.mission)
        self.assertEqual(self.proto(), patched)
        self.assertTrue((self.mission / cc.MANAGED / 'mapgroupproto.backup').is_file())
        shutil.rmtree(self.mission / economy.MANAGED)  # economy rolled back first: now coverage can roll back
        cc.rollback(self.mission)
        self.assertEqual(self.proto(), self.stock)

    def test_every_optional_installer_folder_is_checked_the_same_way(self):
        receipt = cc.install(self.stage(), self.mission)
        for name in (snafu_optional.MANAGED, tactical_flava_optional.MANAGED):
            folder = self.pin_folder(name, receipt['after'])
            with self.subTest(name), self.assertRaisesRegex(ValueError, 'installed on top of the coverage'):
                cc.rollback(self.mission)
            shutil.rmtree(folder)
        self.assertEqual(sha(self.proto()), receipt['after'])

    def test_an_unreadable_economy_receipt_blocks_the_coverage_rollback(self):
        cc.install(self.stage(), self.mission)
        folder = self.mission / economy.MANAGED
        folder.mkdir()
        patched = self.proto()
        with self.assertRaisesRegex(ValueError, 'manual recovery needed'):
            cc.rollback(self.mission)
        self.assertEqual(self.proto(), patched)
        self.assertTrue((self.mission / cc.MANAGED).exists())

    def test_economy_first_then_coverage_installs_and_rolls_back_cleanly(self):
        folder = self.pin_folder(economy.MANAGED, sha(self.stock))
        cc.install(self.stage(), self.mission)
        cc.rollback(self.mission)
        self.assertEqual(self.proto(), self.stock)
        self.assertEqual(json.loads((folder / 'receipt.json').read_bytes())['sources']['mapgroupproto.xml'], sha(self.stock))

    def test_install_refuses_when_an_existing_economy_install_pins_other_proto_bytes(self):
        stage = self.stage()
        self.pin_folder(economy.MANAGED, sha(b'a different mapgroupproto'))
        with self.assertRaisesRegex(ValueError, 'installed on top of the coverage|different mapgroupproto'):
            cc.install(stage, self.mission)
        self.assertEqual(self.proto(), self.stock)
        self.assertFalse((self.mission / cc.MANAGED).exists())

    def test_recovery_files_and_directories_are_synced_before_the_atomic_switch(self):
        events = []
        real_fsync, real_replace = os.fsync, os.replace

        def fsync(fd):
            events.append(('fsync', os.fstat(fd).st_ino))
            return real_fsync(fd)

        def replace(src, dst):
            events.append(('replace', None))
            return real_replace(src, dst)

        stage = self.stage()
        with mock.patch.object(cc.os, 'fsync', fsync), mock.patch.object(cc.os, 'replace', replace):
            cc.install(stage, self.mission)
        managed = self.mission / cc.MANAGED
        before = {ino for kind, ino in events[:events.index(('replace', None))] if kind == 'fsync'}
        for name in ('receipt.json', 'mapgroupproto.backup', 'coverage-delta.json', 'mapgroupproto.next'):
            path = managed / name if name != 'mapgroupproto.next' else None
            if path is not None:
                self.assertIn(os.stat(path).st_ino, before, name)
        self.assertIn(os.stat(managed).st_ino, before)
        self.assertIn(os.stat(self.mission).st_ino, before)
        self.assertEqual(events[-1][0], 'fsync')  # the switch itself is followed by a directory sync

    def test_directory_sync_is_skipped_without_failing_on_windows(self):
        with mock.patch.object(cc.os, 'name', 'nt'):
            cc._sync_dir(self.mission)  # must not raise or open the directory


class ValidateTests(Fixture):
    def test_validate_is_pending_when_no_sampler_result_is_shipped(self):
        report = cc.validate(result_path=self.tmp / 'absent.json')
        self.assertEqual(report['status'], 'pending')
        self.assertIn('no native sampler result', report['reason'])
        self.assertEqual(report['runtime_acceptance'], 'pending')

    def test_validate_checks_a_shipped_result_but_never_claims_acceptance(self):
        report = cc.validate(result_path=self.result_path(), mission=self.mission)
        self.assertEqual(report['status'], 'result-valid')
        self.assertEqual(report['native_run_id'], RUN_ID)
        self.assertEqual(report['runtime_acceptance'], 'pending')
        self.assertEqual(report['points'], {'Land_Tenement_Small': 3, 'Land_Tenement_Big': 2})

    def test_validate_refuses_an_invalid_shipped_result(self):
        doc = result_doc(self.stock)
        del doc['native_run_id']
        with self.assertRaises(ValueError):
            cc.validate(result_path=self.result_path(doc))

    def test_default_shipped_location_is_inside_the_mission_delta_folder(self):
        self.assertEqual(cc.SHIPPED_RESULT, Path('mission/hollow-country/ce-coverage/sampler-result.json'))


class CliTests(Fixture):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cc.main(list(argv))
            except SystemExit as exit_:
                code = exit_.code
        return code, out.getvalue(), err.getvalue()

    def test_request_generate_install_rollback_round_trip(self):
        code, out, _ = self.run_cli('request', '--mission', str(self.mission), '--out', str(self.tmp / 'req.json'))
        self.assertEqual(code, 0)
        self.assertIn('interior_sampler.py', out)
        self.assertEqual(json.loads((self.tmp / 'req.json').read_bytes())['kind'], 'ce-coverage-request')
        result = self.result_path()
        code, out, _ = self.run_cli('generate', '--sampler-result', str(result), '--mission', str(self.mission),
                                    '--out', str(self.tmp / 'stage'))
        self.assertEqual(code, 0)
        self.assertIn('pending', out)
        self.assertEqual(self.run_cli('install', '--delta', str(self.tmp / 'stage'), '--mission', str(self.mission))[0], 0)
        self.assertNotEqual(self.proto(), self.stock)
        self.assertEqual(self.run_cli('rollback', '--mission', str(self.mission))[0], 0)
        self.assertEqual(self.proto(), self.stock)

    def test_cli_refusals_exit_nonzero_without_a_traceback(self):
        doc = result_doc(self.stock)
        del doc['native_run_id']
        code, _out, err = self.run_cli('generate', '--sampler-result', str(self.result_path(doc)),
                                       '--mission', str(self.mission), '--out', str(self.tmp / 'stage'))
        self.assertEqual(code, 1)
        self.assertNotIn('Traceback', err)
        self.assertFalse((self.tmp / 'stage').exists())

    def test_validate_cli_reports_pending_and_exits_zero_when_nothing_is_shipped(self):
        code, out, _ = self.run_cli('validate', '--sampler-result', str(self.tmp / 'absent.json'))
        self.assertEqual(code, 0)
        self.assertIn('PENDING', out)
        self.assertNotIn('accepted', out.lower().replace('acceptance', ''))


if __name__ == '__main__':
    unittest.main()
