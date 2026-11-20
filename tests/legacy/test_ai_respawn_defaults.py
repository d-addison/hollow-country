"""Respawn2 spec/plan/tasks: provenance, backed-up schema adoption, shared path.
Explicit in-memory files; no native filesystem or DayZ acceptance evidence.
"""
import json
import re
from pathlib import Path
from types import SimpleNamespace as N
import unittest
from tests.legacy.test_expansion_ai_adapter import Authored, A
from tests.legacy.test_map_layers import EStr

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIRespawnDefaults.c'

class DefaultAdoptionTests(unittest.TestCase):
    def fixture(self, profile=None, origin=None, shipped='{"SchemaVersion":1,"NewTimer":900,"Sites":[]}', fail_copy_suffix=None):
        files = {'pbo/sites.json': shipped}
        target = '$profile:HollowCountry/sites.json'
        if profile is not None: files[target] = profile
        if origin is not None: files[target + '.hcdefault.origin'] = origin
        logs = []
        def write(path, text):
            files[path] = text
            return True
        def copy(source, destination):
            if fail_copy_suffix and destination.endswith(fail_copy_suffix): return False
            if source not in files: return False
            files[destination] = files[source]
            return True
        env = dict(A=A, FileExist=lambda path: path in files, CopyFile=copy,
                   DeleteFile=lambda path: files.pop(path, None), Print=logs.append,
                   HCProfileDefaults=N(Valid=lambda name: name == 'sites.json',
                       ReadText=lambda path: EStr(files.get(path, '')),
                       WriteText=write, PrepareParents=lambda name: True),
                   HCJsonFields=N(Has=lambda text, key: key in json.loads(text)))
        env['HCXAIReadSchema'] = lambda text: N(SchemaVersion=json.loads(text).get('SchemaVersion', 0))
        source = SOURCE.read_text().replace(
            'if (!JsonFileLoader<HCXAIRespawnSchema>.LoadData(text, schema, error) || !schema)',
            'schema = HCXAIReadSchema(text); if (!schema)')
        authored = Authored(re.sub(r'array<string> (\w+)', r'HCXAIKeyList \1', source), env)
        api = N()
        env['HCXAIRespawnDefaults'] = api
        for method in ('HCKeys', 'HCVersion', 'HCOlderSchema', 'HCEnsure'):
            setattr(api, method, lambda *args, name=method: authored.call(name, None, *args))
        return api, files, target, logs

    def test_legacy_missing_keys_is_backed_up_and_adopted(self):
        old = '{"SchemaVersion":1}'
        api, files, target, logs = self.fixture(old)
        self.assertTrue(api.HCEnsure('sites.json', 'pbo/sites.json'))
        self.assertEqual(old, files[target + '.legacy.bak'])
        self.assertEqual(files['pbo/sites.json'], files[target])
        self.assertEqual(files[target], files[target + '.hcdefault.origin'])
        self.assertEqual(1, sum('adopted' in line for line in logs))
        api.HCEnsure('sites.json', 'pbo/sites.json')
        self.assertEqual(1, sum('adopted' in line for line in logs))

    def test_untouched_provenance_upgrades_but_operator_edits_survive(self):
        old = '{"SchemaVersion":1,"NewTimer":600}'
        for edited in (False, True):
            profile = old.replace('600', '120') if edited else old
            api, files, target, logs = self.fixture(profile, old)
            self.assertTrue(api.HCEnsure('sites.json', 'pbo/sites.json'))
            self.assertEqual(profile if edited else files['pbo/sites.json'], files[target])
            self.assertEqual(not edited, target + '.bak' in files)

    def test_unknown_newer_keys_and_same_schema_legacy_are_kept(self):
        for profile in ('{"SchemaVersion":2}',
                        '{"SchemaVersion":1,"OperatorNewKey":42}',
                        '{"SchemaVersion":1,"Sites":[{"OperatorRowKey":42}]}',
                        '{"SchemaVersion":1,"NewTimer":120,"Sites":[]}'):
            api, files, target, logs = self.fixture(profile)
            api.HCEnsure('sites.json', 'pbo/sites.json')
            self.assertEqual(profile, files[target])
            self.assertNotIn(target + '.hcdefault.origin', files)

    def test_fresh_copy_and_failed_backup_do_not_lose_profile(self):
        api, files, target, logs = self.fixture()
        self.assertTrue(api.HCEnsure('sites.json', 'pbo/sites.json'))
        self.assertEqual(files[target], files[target + '.hcdefault.origin'])
        old = '{"SchemaVersion":1}'
        api, files, target, logs = self.fixture(old)
        files[target + '.legacy.bak'] = 'previous recovery image'
        self.assertFalse(api.HCEnsure('sites.json', 'pbo/sites.json'))
        self.assertEqual(old, files[target])


    def test_failed_backup_or_promotion_preserves_original_bytes_and_provenance(self):
        old = '{"SchemaVersion":1,"NewTimer":600}'
        for destination in ('.bak', '/sites.json'):
            api, files, target, logs = self.fixture(old, old, fail_copy_suffix=destination)
            self.assertFalse(api.HCEnsure('sites.json', 'pbo/sites.json'))
            self.assertEqual(old, files[target])
            self.assertEqual(old, files[target + '.hcdefault.origin'])
            self.assertFalse(any('adopted' in line for line in logs))
