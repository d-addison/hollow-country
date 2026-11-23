"""gen_modules: schema subset, code facts, MODULE_STATUS rows, drift detection (synthetic trees plus the real pilot)."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.package import gen_modules as gm

MODULE_C = '''class HCSampleModule : HCModule
{
    override string GetName() { return "Sample"; }
    override int StartupPhase() { return HC_PHASE_FEATURE; }
    // HCRegisterUse("Other", "ignored_in_comment");
    override void RegisterUses() { HCModuleReadiness.HCRegisterUse("Sample", "thing_done"); }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableSample; }
    override HCOperationalStatus HCGetOperationalStatus()
    {
        m_Operational.HCPublish("refused", "sample_refused");
        return m_Operational;
    }
}

class HCSampleBridge { }

modded class HCModuleRegistry
{
    override void RegisterModules() { super.RegisterModules(); Register(new HCSampleModule); }
}
'''
LEGACY_C = '''class HCModuleReadiness
{
    static void HCRegisterModuleUses(string module)
    {
        s_LegacyUses.Insert("Plain", "one,two");
    }
}
'''
PLAIN_C = '''class HCPlainModule extends HCModule
{
    override string GetName() { return "Plain"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnablePlain; }
    override bool RequiresSharedSaves() { return true; }
}
modded class HCModuleRegistry { override void RegisterModules() { Register(new HCPlainModule); } }
'''
SETTINGS_C = '''modded class HCOperatorSettingsRegistry
{
    static void HCInit()
    {
        HCAdd("EnableSample", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnablePlain", "bool", 0, 0, 1, "HCSettings");
        HCAdd("Sample.Limit", "int", 3, 1, 3, "HCSampleConfig");
    }
}
'''
STATUS = '''# Doc

## R1 registered use features

| Module | Feature names |
| --- | --- |
| Alpha | `a` |
| Plain | `one`, `two` |
| Sample | `thing_done` |
| Zed | `z` |

Prose after the table.
'''


def manifest(**over):
    value = {'schema': 1, 'name': 'Sample', 'mod': 'HollowCountry', 'layer': 'feature', 'class': 'HCSampleModule',
             'source': 'mods/M/scripts/4_World/HCSample.c', 'default_on': True, 'settings': ['EnableSample'],
             'uses': ['thing_done'], 'uses_source': 'register_uses', 'requires_shared_saves': False,
             'dependencies': ['HCSampleBridge'], 'readiness_reasons': ['sample_refused']}
    value.update(over)
    return value


def plain(**over):
    value = manifest(name='Plain', **{'class': 'HCPlainModule'}, source='mods/M/scripts/4_World/HCPlain.c',
                     settings=['EnablePlain'], uses=['one', 'two'], uses_source='legacy_uses',
                     requires_shared_saves=True, dependencies=[], readiness_reasons=[], default_on=False)
    value.update(over)
    return value


class Tree:
    def __init__(self, test):
        self.dir = tempfile.TemporaryDirectory()
        test.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        for rel, text in (('mods/M/scripts/4_World/HCSample.c', MODULE_C), ('mods/M/scripts/4_World/HCPlain.c', PLAIN_C),
                          ('mods/M/scripts/3_Game/HCSettings.c', SETTINGS_C),
                          (str(gm.READINESS), LEGACY_C), (str(gm.MODULE_BASE), 'class HCModule { }\n'),
                          (str(gm.STATUS_DOC), STATUS)):
            self.put(rel, text)
        (self.root / gm.MODULES).mkdir()
        (self.root / gm.SCHEMA).write_bytes((gm.ROOT / gm.SCHEMA).read_bytes())

    def put(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def manifest(self, value):
        self.put(f'modules/{value["name"]}.module.json', json.dumps(value))

    def errors(self):
        try:
            gm.check(self.root)
        except gm.ManifestError as exc:
            return exc.problems
        return []


class SchemaTest(unittest.TestCase):
    def test_real_schema_accepts_a_good_manifest_and_names_each_defect(self):
        schema = json.loads((gm.ROOT / gm.SCHEMA).read_bytes())
        self.assertEqual([], gm.schema_errors(manifest(), schema))
        bad = manifest(layer='middle', uses=[], extra=1)
        bad.pop('class')
        text = ' '.join(gm.schema_errors(bad, schema))
        for needle in ('layer', 'uses', 'extra', 'class'):
            self.assertIn(needle, text)
        self.assertTrue(gm.schema_errors(manifest(uses=['a', 'a']), schema))
        self.assertTrue(gm.schema_errors(manifest(schema=True), schema))
        self.assertTrue(gm.schema_errors(manifest(source='scripts/HCSample.c'), schema))


class ParserTest(unittest.TestCase):
    def test_comments_are_blanked_and_strings_kept(self):
        source = 'a("//x"); // bb\n/* cc\n dd */ e'
        code = gm.strip_comments(source)
        self.assertIn('"//x"', code)
        self.assertNotIn('bb', code)
        self.assertNotIn('cc', code)
        self.assertNotIn('dd', code)
        self.assertEqual(len(source), len(code))
        self.assertEqual(source.count('\n'), code.count('\n'))

    def test_class_and_method_bodies(self):
        body = gm.class_body(MODULE_C, 'HCSampleModule')
        self.assertTrue(body.startswith('{') and body.endswith('}'))
        self.assertNotIn('HCSampleBridge', body)
        self.assertIsNone(gm.class_body(MODULE_C, 'HCSampleBridge'))
        self.assertIn('thing_done', gm.method_body(body, r'void\s+RegisterUses\s*\(\s*\)'))


class CheckTest(unittest.TestCase):
    def test_consistent_tree_passes_and_comment_registrations_do_not_count(self):
        tree = Tree(self)
        tree.manifest(manifest())
        tree.manifest(plain())
        self.assertEqual([], tree.errors())
        facts = gm.CodeFacts(tree.root)
        seen = gm.module_facts(manifest(), facts)
        self.assertEqual(['thing_done'], seen['uses'])
        self.assertEqual([], seen['foreign_uses'])

    def test_every_code_fact_is_compared(self):
        cases = (
            (dict(layer='core'), 'layer'),
            (dict(uses=['other']), '[HC Use]'),
            (dict(uses=['thing_done'], uses_source='legacy_uses'), 'uses_source'),
            (dict(requires_shared_saves=True), 'requires_shared_saves'),
            (dict(settings=['EnableSample', 'Missing.Key']), 'not in the settings registry'),
            (dict(settings=['EnableSample', 'Sample.Limit']), 'is not read'),
            (dict(default_on=False), 'default_on'),
            (dict(dependencies=['HCNoSuchBridge']), 'dependency class'),
            (dict(readiness_reasons=['made_up']), 'readiness reason'),
            (dict(**{'class': 'HCPlainModule'}), 'does not define class'),
            (dict(source='mods/M/scripts/4_World/Nope.c'), 'not a script file'),
        )
        for change, needle in cases:
            with self.subTest(needle=needle):
                tree = Tree(self)
                tree.manifest(manifest(**change))
                self.assertTrue(any(needle in e for e in tree.errors()), tree.errors())

    def test_name_mismatch_unregistered_and_filename(self):
        tree = Tree(self)
        tree.manifest(manifest(name='Renamed'))
        self.assertTrue(any('GetName() returns Sample' in e for e in tree.errors()))
        tree = Tree(self)
        tree.put('mods/M/scripts/4_World/HCSample.c', MODULE_C.replace('Register(new HCSampleModule)', ''))
        tree.manifest(manifest())
        self.assertTrue(any('no Register' in e for e in tree.errors()))
        tree = Tree(self)
        tree.put('modules/Wrong.module.json', json.dumps(manifest()))
        self.assertTrue(any('file name must be' in e for e in tree.errors()))
        self.assertTrue(any('no module manifests' in e for e in Tree(self).errors()))

    def test_changed_legacy_row_is_drift(self):
        tree = Tree(self)
        tree.manifest(plain())
        tree.put(str(gm.READINESS), LEGACY_C.replace('one,two', 'one,two,three'))
        self.assertTrue(any('[HC Use]' in e for e in tree.errors()))


class StatusRowTest(unittest.TestCase):
    def test_row_text_and_note(self):
        self.assertEqual('| Sample | `thing_done` |', gm.status_row(manifest()))
        self.assertEqual('| Plain | `one`, `two` (extra text) |', gm.status_row(plain(status_note='(extra text)')))

    def test_drift_fails_check_and_write_repairs_only_that_row(self):
        tree = Tree(self)
        tree.manifest(manifest())
        tree.manifest(plain(status_note='(extra text)'))
        self.assertTrue(any('row for Plain differs' in e for e in tree.errors()))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(['Plain'], gm.write(tree.root))
            self.assertEqual([], gm.write(tree.root))
        text = (tree.root / gm.STATUS_DOC).read_text()
        self.assertEqual(STATUS.replace('| Plain | `one`, `two` |', '| Plain | `one`, `two` (extra text) |'), text)
        self.assertEqual([], tree.errors())

    def test_missing_row_is_appended_to_the_table_end(self):
        tree = Tree(self)
        tree.manifest(manifest())
        tree.put(str(gm.STATUS_DOC), STATUS.replace('| Sample | `thing_done` |\n', ''))
        self.assertTrue(any('row for Sample differs' in e for e in tree.errors()))
        gm.write(tree.root)
        lines = (tree.root / gm.STATUS_DOC).read_text().split('\n')
        self.assertEqual('| Sample | `thing_done` |', lines[lines.index('| Zed | `z` |') + 1])

    def test_missing_section_is_an_error(self):
        tree = Tree(self)
        tree.manifest(manifest())
        tree.put(str(gm.STATUS_DOC), '# Doc\n')
        self.assertTrue(any('section' in e for e in tree.errors()))


class PilotTest(unittest.TestCase):
    def test_committed_manifests_match_code_and_the_committed_rows_byte_for_byte(self):
        manifests = gm.check()
        self.assertEqual(10, len(manifests))
        lines = (gm.ROOT / gm.STATUS_DOC).read_text().split('\n')
        for item in manifests:
            self.assertIn(gm.status_row(item), lines)

    def test_cli_exit_codes(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(0, gm.main(['--check']))
        self.assertIn('pass modules=10', out.getvalue())


if __name__ == '__main__':
    unittest.main()
