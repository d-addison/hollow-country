"""Offline tooling checks for the compat addon generator; not DayZ behaviour."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.package import compat_addon as addon
from tools.package import pbo

OWN = 'OwnPatch'


class CompatAddonTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        config = self.root / 'mods/Own/config.cpp'
        config.parent.mkdir(parents=True)
        config.write_text('class CfgPatches\n{\n    class %s\n    {\n        requiredAddons[] = {"X"};\n'
                          '    };\n};\nclass CfgVehicles { class Other {}; };\n' % OWN)
        self.strings = self.root / 'strings.json'
        self.strings.write_text(json.dumps({'schema': 1, 'strings': []}))

    def rules(self, own=(), dependency=(), required=(OWN,), name='rules.json'):
        path = self.root / name
        path.write_text(json.dumps({
            'schema': addon.SCHEMA,
            'addon': {'patch': addon.PATCH, 'prefix': addon.PREFIX, 'pbo': addon.PBO_NAME,
                      'required_addons': list(required)},
            'own_rules': list(own), 'dependency_rules': list(dependency)}))
        return path

    def rule(self, **over):
        row = {'id': 'r1', 'section': addon.SECTIONS[0], 'class': 'Child', 'parent': 'Base',
               'requires': ['DepAddon'], 'set': {'scope': 2}, 'evidence': 'rpt category 1'}
        row.update(over)
        return row

    def generate(self, **kw):
        return addon.generate([self.rules(**kw)], self.strings, self.root)

    def test_committed_rules_validate_against_repo(self):
        block, rules = addon.load_rules()
        self.assertLessEqual(set(block['required_addons']), addon.own_patches())
        self.assertTrue(all(r['source'] in {'own', 'dependency'} for r in rules))
        blob, files, receipt = addon.generate()
        self.assertEqual((addon.PREFIX, files), pbo.parse(blob, prefixes=(addon.PREFIX,)))
        self.assertEqual(len(rules), receipt['rules']['own'] + receipt['rules']['dependency'])
        self.assertIn(addon.PREFIX, pbo.PREFIXES)

    def test_own_patches_reads_only_cfgpatches_children(self):
        self.assertEqual({OWN}, addon.own_patches(self.root))

    def test_empty_rules_make_a_config_only_addon(self):
        blob, files, receipt = self.generate()
        self.assertEqual({'config.cpp'}, set(files))
        text = files['config.cpp'].decode()
        self.assertIn(f'class {addon.PATCH}', text)
        self.assertIn(f'requiredAddons[] = {{"{OWN}"}};', text)
        self.assertNotIn('Cfg' + 'Vehicles', text)
        self.assertEqual('generated', receipt['status'])
        self.assertEqual('PENDING', receipt['runtime'])

    def test_rule_emits_inheritance_only_class_and_requires(self):
        _, files, receipt = self.generate(dependency=[self.rule(set={'scope': 2, 'tags[]': ['a', 'b'],
                                                                      'weight': 1.5, 'name': 'x y'})])
        text = files['config.cpp'].decode()
        self.assertIn('class Base;', text)
        self.assertIn('class Child: Base', text)
        for line in ('scope = 2;', 'tags[] = {"a", "b"};', 'weight = 1.5;', 'name = "x y";'):
            self.assertIn(line, text)
        self.assertEqual([OWN, 'DepAddon'], receipt['requiredAddons'])
        self.assertEqual({'own': 0, 'dependency': 1}, receipt['rules'])
        self.assertNotIn('rpt category', text)

    def test_empty_set_and_parent_ordering_are_deterministic(self):
        rows = [self.rule(id='b', **{'class': 'Leaf', 'parent': 'Mid', 'set': {}}),
                self.rule(id='a', **{'class': 'Mid', 'parent': 'Root'})]
        first = self.generate(dependency=rows)
        second = self.generate(dependency=list(reversed(rows)))
        self.assertEqual(first[0], second[0])
        text = first[1]['config.cpp'].decode()
        self.assertLess(text.index('class Mid: Root'), text.index('class Leaf: Mid'))
        self.assertIn('class Leaf: Mid {};', text)
        self.assertEqual(1, text.count('class Root;'))
        self.assertNotIn('class Mid;', text)

    def test_invalid_rules_are_refused(self):
        bad = [
            self.rule(section='CfgPatches'),
            self.rule(parent='Child'),
            self.rule(**{'class': 'bad name'}),
            self.rule(set={'x': True}),
            self.rule(set={'x': None}),
            self.rule(set={'x': {'nested': 1}}),
            self.rule(set={'x': [1]}),
            self.rule(set={'x[]': 1}),
            self.rule(set={'x': 'quo"te'}),
            self.rule(set={'x': float('inf')}),
            self.rule(set={'bad name': 1}),
            self.rule(requires=[]),
            self.rule(evidence=''),
            self.rule(id='bad id!'),
            self.rule(unexpected=1),
        ]
        for row in bad:
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.generate(dependency=[row])

    def test_own_rules_need_no_requires_or_evidence(self):
        _, files, _ = self.generate(own=[self.rule(requires=[], evidence='')])
        self.assertIn('class Child: Base', files['config.cpp'].decode())

    def test_duplicates_and_cycles_are_refused(self):
        with self.assertRaises(ValueError):
            self.generate(dependency=[self.rule(), self.rule(**{'class': 'Other'})])
        with self.assertRaises(ValueError):
            self.generate(dependency=[self.rule(), self.rule(id='r2')])
        with self.assertRaises(ValueError):
            self.generate(dependency=[self.rule(id='a', **{'class': 'A', 'parent': 'B'}),
                                      self.rule(id='b', **{'class': 'B', 'parent': 'A'})])

    def test_required_addons_must_be_our_own(self):
        with self.assertRaises(ValueError):
            self.generate(required=['NotOurs'])
        with self.assertRaises(ValueError):
            self.generate(required=[])

    def test_multiple_rule_files_share_one_addon_block(self):
        extra = self.root / 'extra.json'
        extra.write_text(json.dumps({'schema': 1, 'dependency_rules': [self.rule(id='x', **{'class': 'Extra'})]}))
        _, files, _ = addon.generate([self.rules(), extra], self.strings, self.root)
        self.assertIn('class Extra: Base', files['config.cpp'].decode())
        with self.assertRaises(ValueError):
            addon.generate([self.rules(), self.rules(name='again.json')], self.strings, self.root)

    def test_strings_are_packed_when_present(self):
        self.strings.write_text(json.dumps({'schema': 1, 'strings': [{'key': 'STR_k', 'text': 'Own words'}]}))
        blob, files, receipt = self.generate()
        self.assertEqual({'config.cpp', 'stringtable.csv'}, set(files))
        self.assertEqual(1, receipt['strings'])
        self.assertEqual((addon.PREFIX, files), pbo.parse(blob, prefixes=(addon.PREFIX,)))

    def test_cli_writes_fresh_output_and_refuses_existing(self):
        out = self.root / 'out'
        real = sorted(addon.own_patches())[:1]
        args = ['--out', str(out), '--rules', str(self.rules(required=real)), '--strings', str(self.strings), '--source']
        text = io.StringIO()
        with contextlib.redirect_stdout(text):
            self.assertEqual(0, addon.main(args))
        self.assertTrue((out / addon.PBO_NAME).is_file())
        self.assertTrue((out / 'source/config.cpp').is_file())
        receipt = json.loads((out / 'compat-addon.json').read_text())
        self.assertEqual(receipt['sha256'], hashlib.sha256((out / addon.PBO_NAME).read_bytes()).hexdigest())
        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stderr(io.StringIO()):
            addon.main(args)
        self.assertEqual(1, raised.exception.code)


if __name__ == '__main__':
    unittest.main()
