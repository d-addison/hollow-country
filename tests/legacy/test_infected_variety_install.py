"""Synthetic mission bytes only: these tests establish no native CE behavior."""
import importlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / 'mission/hollow-country/infected/variants.json'
WORLD = ROOT / 'mods/HollowCountry/scripts/4_World/Infected'


class InfectedVarietyInstallTests(unittest.TestCase):
    def setUp(self):
        self.tool = importlib.import_module('tools.package.infected_variety')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mission = self.root / 'mission'
        (self.mission / 'db').mkdir(parents=True)
        self.events = self.mission / 'db/events.xml'
        # Deliberately small synthetic events, NOT copied vanilla configuration.
        self.policy = json.loads(POLICY.read_text())
        rows = []
        for name in dict.fromkeys(s['event'] for s in self.policy['substitutions']):
            donors = dict.fromkeys(s['from'] for s in self.policy['substitutions'] if s['event'] == name)
            # A donor may feed several rows; it keeps min 8 after giving all its shares.
            given = {d: sum(s['share'] for s in self.policy['substitutions'] if s['event'] == name and s['from'] == d) for d in donors}
            children = ''.join(f'\n      <child min="{8 + given[d]}" max="0" lootmin="0" lootmax="5" type="{d}" />' for d in donors)
            rows.append(f'  <event name="{name}"><nominal>42</nominal><active>1</active><children>{children}\n    </children></event>')
        self.original = ('<?xml version="1.0" encoding="UTF-8"?>\r\n<!-- synthetic comment retained -->\r\n<events>\r\n' + '\r\n'.join(rows) + '\r\n  <event name="Unrelated"><active>0</active></event>\r\n</events>\r\n').encode()
        self.events.write_bytes(self.original)
        self.stock = self.root / 'installed-stock-events.xml'
        self.stock.write_bytes(self.original)
        import hashlib
        self.policy['evidence']['stock_events_sha256'] = hashlib.sha256(self.original).hexdigest()
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
        for old, new in zip(before, after):
            self.assertEqual(old.attrib, new.attrib)
            self.assertEqual(sum(int(c.get('min')) for c in old.findall('./children/child')),
                             sum(int(c.get('min')) for c in new.findall('./children/child')))
            self.assertEqual([(c.tag, c.text, c.attrib) for c in old if c.tag != 'children'],
                             [(c.tag, c.text, c.attrib) for c in new if c.tag != 'children'])
        for row in self.policy['substitutions']:
            event = next(e for e in after if e.get('name') == row['event'])
            self.assertEqual(str(row['share']), event.find(f'./children/child[@type="{row["to"]}"]').get('min'))
            self.assertEqual('8', event.find(f'./children/child[@type="{row["from"]}"]').get('min'))
        self.assertIn(b'<!-- synthetic comment retained -->', self.events.read_bytes())
        self.assertFalse((ROOT / 'mission/hollow-country/infected/events.append.xml').exists())

    def test_non_stock_event_refuses_before_receipt_or_mutation(self):
        for old, new in ((b'<nominal>42', b'<nominal>43'), (b'min="', b'min="1'),
                         (b'name="InfectedCity"', b'name="MissingCity"')):
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
            self.assertEqual(self.original, self.events.read_bytes())
            self.assertFalse((self.mission / self.tool.MANAGED).exists())
        self.tool.install(self.mission, None, off=True)
        self.assertEqual(self.original, self.events.read_bytes())

    def test_receipt_binds_backup_and_installed_bytes(self):
        import base64
        import hashlib
        self.install()
        receipt = json.loads((self.mission / self.tool.MANAGED / 'receipt.json').read_bytes())
        row = receipt['files']['db/events.xml']
        self.assertEqual(self.original, base64.b64decode(row['before']))
        self.assertEqual(hashlib.sha256(self.original).hexdigest(), row['before_sha256'])
        self.assertEqual(hashlib.sha256(self.events.read_bytes()).hexdigest(), row['after'])
        self.assertEqual('PENDING', receipt['runtime_acceptance'])

    def test_double_quoted_declaration_and_byte_exact_original_restoration(self):
        data = self.original.replace(b'<?xml version="1.0" encoding="UTF-8"?>', b"<?xml version='1.0' encoding='utf-8'?>")
        self.events.write_bytes(data)
        self.install()
        self.assertTrue(self.events.read_bytes().startswith(b'<?xml version="1.0" encoding="UTF-8"?>'))
        self.tool.rollback(self.mission)
        self.assertEqual(data, self.events.read_bytes())

    def test_rollback_refuses_operator_drift_and_retains_receipt(self):
        self.install()
        data = self.events.read_bytes() + b'<!-- operator edit -->'
        self.events.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'drift'):
            self.tool.rollback(self.mission)
        self.assertEqual(data, self.events.read_bytes())
        self.assertTrue((self.mission / self.tool.MANAGED / 'receipt.json').exists())

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
        def fail_target(path, data, managed):
            if path == self.events:
                raise OSError('synthetic interruption before events switch')
            real_atomic(path, data, managed)
        with patch.object(self.tool, 'atomic', side_effect=fail_target):
            with self.assertRaises(OSError):
                self.install()
        self.tool.rollback(self.mission)
        self.assertEqual(self.original, self.events.read_bytes())


class NativeAdmissionTests(unittest.TestCase):
    def test_manifest_counts_and_selected_inspection_calls_agree(self):
        manifest = json.loads(POLICY.read_text())
        source = (WORLD / 'HCNativeVariantAdmission.c').read_text()
        selected = [r for r in manifest['entries'] if r['selected']]
        unresolved = [r for r in manifest['aliases'] if r['kind'] == 'unresolved_spelling']
        self.assertEqual(len(selected), int(re.search(r'int Authored = (\d+);', source)[1]))
        self.assertEqual(len(unresolved), int(re.search(r'int Unresolved = (\d+);', source)[1]))
        self.assertEqual({r['class'] for r in selected}, set(re.findall(r'HCInspectCandidate\("([^"]+)"', source)))
        self.assertEqual(len(selected), len(re.findall(r'HCInspectCandidate\("', source)))
        self.assertEqual(len(selected), manifest['counts']['selected_authored'])
        self.assertEqual(len(unresolved), manifest['counts']['unresolved_spelling_groups'])

    def test_admission_cached_once_before_healthy_and_cleared_on_stop(self):
        source = (WORLD / 'HCInfectedModule.c').read_text()
        self.assertIn('protected ref HCNativeVariantAdmission m_NativeVariants;', source)
        startup = source.split('override void OnStart(', 1)[1].split('protected void Quarantine', 1)[0]
        call = 'm_NativeVariants = HCNativeVariantAdmission.Check(settings.EnableInfectedVariety);'
        self.assertEqual(1, startup.count(call))
        self.assertLess(startup.index(call), startup.index('m_Healthy = true;'))
        from types import SimpleNamespace
        from tests.legacy.test_infected_admission import translate
        cached = object()
        getter = translate('HCInfectedModule.c', 'HCNativeVariantAdmission NativeVariants(', ())
        self.assertIs(cached, getter(SimpleNamespace(m_NativeVariants=cached)))
        self.assertIn('m_NativeVariants = null;', source.split('override void OnStop()', 1)[1])

    def test_native_model_normalization_executes_authored_helper(self):
        # Restricted existing Enforce port; synthetic strings, no native config claims.
        from tests.legacy.test_infected_admission import translate
        class NativeString:
            def __init__(self, value): self.value = value
            def Length(self): return len(self.value)
            # Existing port masks Enforce string literals without unescaping
            # them; represent the native separator the same way for comparison.
            def Get(self, i): return self.value[i].replace('\\', '\\\\')
            def Substring(self, start, count): return NativeString(self.value[start:start+count])
            def ToLower(self): self.value = self.value.lower()
        normalize = translate('HCNativeVariantAdmission.c', 'static string HCNormalizeModel(', ())
        for path in ('', '\\', '\\DZ\\Characters\\Zombies\\A.p3d', 'dz\\characters\\zombies\\a.p3d'):
            self.assertEqual(path.lower().lstrip('\\'), normalize(None, NativeString(path)).value)
        source = (WORLD / 'HCNativeVariantAdmission.c').read_text()
        self.assertIn('HCNormalizeModel(model) != HCNormalizeModel(expectedModel)', source)
