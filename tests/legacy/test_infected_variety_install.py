"""Synthetic mission bytes only: these tests establish no native CE behavior."""
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from tests.legacy.infected_variety_fixtures import (
    synthetic_events, transfers, weight_deltas, write_mission,
)

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / 'mission/hollow-country/infected/variants.json'


class InfectedVarietyInstallTests(unittest.TestCase):
    def setUp(self):
        self.tool = importlib.import_module('tools.package.infected_variety')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mission = self.root / 'mission'
        self.events = self.mission / self.tool.TARGET
        self.policy = json.loads(POLICY.read_text())
        self.original = synthetic_events(self.policy)
        self.originals = write_mission(self.mission, self.policy, self.original)
        self.stock = self.root / 'installed-stock-events.xml'
        self.stock.write_bytes(self.original)
        self.policy_path = self.root / 'synthetic-policy.json'
        self.policy_path.write_text(json.dumps(self.policy))
        self.patch = patch.object(self.tool, 'POLICY', self.policy_path)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def install(self):
        return self.tool.install(self.mission, self.stock)

    def test_substitution_keeps_event_min_sums_and_unrelated_fields(self):
        before = ET.fromstring(self.original)
        self.install()
        after = ET.fromstring(self.events.read_bytes())
        self.assertEqual([e.get('name') for e in before], [e.get('name') for e in after])
        for old, new in zip(before, after):
            self.assertEqual(old.attrib, new.attrib)
            self.assertEqual(sum(int(c.get('min')) for c in old.findall('./children/child')),
                             sum(int(c.get('min')) for c in new.findall('./children/child')))
            self.assertEqual(sum(int(c.get('max')) for c in old.findall('./children/child')),
                             sum(int(c.get('max')) for c in new.findall('./children/child')))
            self.assertEqual([(c.tag, c.text, c.attrib) for c in old if c.tag != 'children'],
                             [(c.tag, c.text, c.attrib) for c in new if c.tag != 'children'])
        self.assertTrue(transfers(self.policy))
        deltas = weight_deltas(self.policy)
        for (name, child), delta in deltas.items():
            old_event = next(e for e in before if e.get('name') == name)
            new_event = next(e for e in after if e.get('name') == name)
            def weight(event):
                node = event.find(f'./children/child[@type="{child}"]')
                return int(node.get('min')) if node is not None else 0
            self.assertEqual(weight(old_event) + delta, weight(new_event))
        for row in transfers(self.policy):
            event = next(e for e in after if e.get('name') == row['event'])
            self.assertGreater(int(event.find(f'./children/child[@type="{row["from"]}"]').get('min')), 0)
        targets = {r['event'] for r in transfers(self.policy)}
        untouched = [(old, new) for old, new in zip(before, after) if old.get('name') not in targets]
        self.assertTrue(untouched)
        for old, new in untouched:
            self.assertEqual(ET.tostring(old), ET.tostring(new))
        self.assertIn(b'<!-- synthetic comment retained -->', self.events.read_bytes())

    def test_non_stock_event_refuses_before_receipt_or_mutation(self):
        for old, new in ((b'<nominal>42', b'<nominal>43'), (b'min="', b'min="1'),
                         (('name="' + self.policy['substitutions'][0]['event'] + '"').encode(), b'name="MissingSyntheticEvent"')):
            with self.subTest(change=new):
                data = self.original.replace(old, new, 1)
                self.events.write_bytes(data)
                with self.assertRaisesRegex(ValueError, 'stock|target'):
                    self.install()
                self.assertEqual(data, self.events.read_bytes())
                self.assertFalse((self.mission / self.tool.MANAGED).exists())

    def test_unpinned_stock_refuses(self):
        self.stock.write_bytes(self.original + b'\n')
        with self.assertRaisesRegex(ValueError, 'stock.*hash|stock.*pin'):
            self.install()
        self.assertEqual(self.original, self.events.read_bytes())

    def test_off_and_rollback_restore_original_bytes(self):
        for off in (False, True):
            self.install()
            if off:
                self.tool.install(self.mission, None, off=True)
            else:
                self.tool.rollback(self.mission)
            for name, data in self.originals.items():
                self.assertEqual(data, (self.mission / name).read_bytes())
            self.assertFalse((self.mission / self.tool.MANAGED).exists())
        self.tool.install(self.mission, None, off=True)
        self.assertEqual(self.original, self.events.read_bytes())

    def test_receipt_binds_backup_and_installed_bytes(self):
        import base64
        import hashlib
        self.install()
        receipt = json.loads((self.mission / self.tool.MANAGED / 'receipt.json').read_bytes())
        expected_files = set(self.originals) - {self.tool.PRESETS}
        self.assertEqual(expected_files, set(receipt['files']))
        for name, row in receipt['files'].items():
            original = self.originals[name]
            self.assertEqual(original, base64.b64decode(row['before']))
            self.assertEqual(hashlib.sha256(original).hexdigest(), row['before_sha256'])
            self.assertEqual(hashlib.sha256((self.mission / name).read_bytes()).hexdigest(), row['after'])
        self.assertEqual(self.policy['runtime_acceptance'], receipt['runtime_acceptance'])

    def test_double_quoted_declaration_and_byte_exact_original_restoration(self):
        data = self.original.replace(b'<?xml version="1.0" encoding="UTF-8"?>', b"<?xml version='1.0' encoding='utf-8'?>")
        self.events.write_bytes(data)
        self.install()
        self.assertTrue(self.events.read_bytes().startswith(self.tool.xml_text.DECLARATION.rstrip(b'\n')))
        self.tool.rollback(self.mission)
        self.assertEqual(data, self.events.read_bytes())

    def test_rollback_refuses_operator_drift_and_retains_receipt(self):
        for name in set(self.originals) - {self.tool.PRESETS}:
            with self.subTest(file=name):
                self.install()
                installed = {n: (self.mission / n).read_bytes() for n in self.originals}
                path = self.mission / name
                drift = installed[name] + b'<!-- operator edit -->'
                path.write_bytes(drift)
                with self.assertRaisesRegex(ValueError, 'drift'):
                    self.tool.rollback(self.mission)
                for n, data in installed.items():
                    self.assertEqual(drift if n == name else data, (self.mission / n).read_bytes())
                self.assertTrue((self.mission / self.tool.MANAGED / 'receipt.json').exists())
                path.write_bytes(installed[name])
                self.tool.rollback(self.mission)

    def test_missing_receipt_with_substituted_target_refuses(self):
        # Review P2-1: an operator-deleted receipt must not report success
        # while events.xml still carries the authored destinations.
        self.install()
        installed = self.events.read_bytes()
        (self.mission / self.tool.MANAGED / 'receipt.json').unlink()
        with self.assertRaisesRegex(ValueError, 'receipt missing'):
            self.tool.rollback(self.mission)
        self.assertEqual(installed, self.events.read_bytes())
        self.assertTrue((self.mission / self.tool.MANAGED).is_dir())

    def test_missing_receipt_before_switch_clears_managed_dir(self):
        (self.mission / self.tool.MANAGED).mkdir()
        self.assertEqual([], self.tool.rollback(self.mission))
        self.assertEqual(self.original, self.events.read_bytes())
        self.assertFalse((self.mission / self.tool.MANAGED).exists())

    def test_interrupted_switch_is_recoverable(self):
        real_atomic = self.tool.atomic
        for name in set(self.originals) - {self.tool.PRESETS}:
            with self.subTest(file=name):
                def fail_target(path, data, managed):
                    if path == self.mission / name:
                        raise OSError('synthetic interruption before file switch')
                    real_atomic(path, data, managed)
                with patch.object(self.tool, 'atomic', side_effect=fail_target):
                    with self.assertRaises(OSError):
                        self.install()
                self.tool.rollback(self.mission)
                for original_name, data in self.originals.items():
                    self.assertEqual(data, (self.mission / original_name).read_bytes())
