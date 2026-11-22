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

    def rules(self, own=(), dependency=(), required=(OWN,), name='rules.json', providers=None):
        path = self.root / name
        data = {
            'schema': addon.SCHEMA,
            'addon': {'patch': addon.PATCH, 'prefix': addon.PREFIX, 'pbo': addon.PBO_NAME,
                      'required_addons': list(required)},
            'own_rules': list(own), 'dependency_rules': list(dependency)}
        if providers is not None:
            data['providers'] = providers
        path.write_text(json.dumps(data))
        return path

    def rule(self, **over):
        # 'X' is required by the fixture's own config, so it is a mandatory addon here.
        row = {'id': 'r1', 'section': addon.SECTIONS[0], 'class': 'Child', 'parent': 'Base',
               'requires': ['X'], 'set': {'scope': 2}, 'evidence': 'rpt category 1'}
        row.update(over)
        return row

    def provider_rule(self, **over):
        return self.rule(provider='a', requires=['DepAddon'], **over)

    def generate(self, **kw):
        return addon.generate([self.rules(**kw)], self.strings, self.root)

    def stack(self, declared=True, installed=True):
        """Fixture Workshop root and stack manifest for the provider item."""
        item = '1234567'
        workshop = self.root / 'workshop'
        workshop.mkdir(exist_ok=True)
        if installed:
            (workshop / item).mkdir(exist_ok=True)
        manifest = self.root / 'stack.json'
        manifest.write_text(json.dumps({'schema': 1, 'mods': (
            [{'id': item, 'publish': False}] if declared else [])}))
        return item, workshop, manifest

    def generate_providers(self, rows, declared=True, installed=True):
        item, workshop, manifest = self.stack(declared, installed)
        path = self.rules(dependency=rows, providers=[{'slot': 'a', 'item': item}])
        return addon.generate_all([path], self.strings, self.root, workshop, manifest)

    def test_committed_rules_validate_against_repo(self):
        block, rules, providers = addon.load_rules()
        self.assertLessEqual(set(block['required_addons']), addon.own_patches())
        self.assertTrue(all(r['source'] in {'own', 'dependency'} for r in rules))
        self.assertLessEqual({r['provider'] for r in rules} - {None}, set(providers))
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
        self.assertEqual([OWN, 'X'], receipt['requiredAddons'])
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

    def test_casefold_collisions_are_refused(self):
        bad = [
            [self.rule(**{'class': 'CHILD', 'parent': 'child'})],
            [self.rule(), self.rule(id='R1', **{'class': 'Other'})],
            [self.rule(), self.rule(id='r2', **{'class': 'cHILD'})],
            [self.rule(requires=['X', 'x'])],
            [self.rule(set={'Scope': 1, 'scope': 2})],
            [self.rule(set={'tags': 'a', 'TAGS[]': ['b']})],
            [self.rule(id='a', **{'class': 'A', 'parent': 'b'}),
             self.rule(id='b', **{'class': 'B', 'parent': 'a'})],
        ]
        for rows in bad:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.generate(dependency=rows)

    def test_casefold_parent_ordering_and_forward_declaration(self):
        rows = [self.rule(id='b', **{'class': 'Leaf', 'parent': 'mid'}),
                self.rule(id='a', **{'class': 'Mid', 'parent': 'Root'}),
                self.rule(id='c', **{'class': 'Side', 'parent': 'ROOT'})]
        text = self.generate(dependency=rows)[1]['config.cpp'].decode()
        self.assertLess(text.index('class Mid: Root'), text.index('class Leaf: mid'))
        self.assertEqual(1, sum(1 for line in text.splitlines() if line.strip().casefold() == 'class root;'))

    def test_scalar_bounds_and_string_markers_are_refused(self):
        low, high = addon.INT32
        for value in (high + 1, low - 1, 1e30, 1e-7, 2.0 ** 40, '//x', 'a/*b', 'a*/b', '#define'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.generate(dependency=[self.rule(set={'x': value})])
        _, files, _ = self.generate(dependency=[self.rule(set={'hi': high, 'lo': low})])
        text = files['config.cpp'].decode()
        self.assertIn(f'hi = {high};', text)
        self.assertIn(f'lo = {low};', text)

    def test_optional_requires_need_a_provider_slot(self):
        with self.assertRaisesRegex(ValueError, 'optional addon'):
            self.generate(dependency=[self.rule(requires=['DepAddon'])])
        with self.assertRaisesRegex(ValueError, 'not declared'):
            self.generate(dependency=[self.provider_rule()])
        item, _, _ = self.stack()
        providers = [{'slot': 'a', 'item': item}]
        # A provider rule that requires only mandatory addons gains nothing from a provider PBO.
        with self.assertRaises(ValueError):
            addon.load_rules([self.rules(dependency=[self.rule(provider='a')], providers=providers)],
                             self.root)
        for bad in ([{'slot': 'zz', 'item': item}], [{'slot': 'a', 'item': 'x'}],
                    [{'slot': 'a', 'item': item}, {'slot': 'a', 'item': '7654321'}],
                    [{'slot': 'a', 'item': item}, {'slot': 'b', 'item': item}],
                    [{'slot': 'a'}]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                addon.load_rules([self.rules(providers=bad)], self.root)

    def test_provider_pbo_is_built_only_for_a_declared_installed_item(self):
        rows = [self.provider_rule(), self.rule(id='r2', **{'class': 'Plain'})]
        outputs, receipt = self.generate_providers(rows)
        names = [name for name, _, _ in outputs]
        self.assertEqual([addon.PBO_NAME, addon.slot_pbo('a')], names)
        self.assertEqual(names, receipt['pbos'])
        base_text = outputs[0][2]['config.cpp'].decode()
        slot_text = outputs[1][2]['config.cpp'].decode()
        self.assertIn('class Plain: Base', base_text)
        self.assertNotIn('class Child', base_text)
        self.assertNotIn('DepAddon', base_text)
        self.assertIn('class Child: Base', slot_text)
        self.assertIn('"DepAddon"', slot_text)
        self.assertIn(addon.PATCH, slot_text)
        self.assertNotIn(addon.slot_patch('a'), base_text)
        entry = receipt['optional'][0]
        self.assertEqual('generated', entry['status'])
        self.assertEqual(hashlib.sha256(outputs[1][1]).hexdigest(), entry['sha256'])
        self.assertEqual((addon.slot_prefix('a'), outputs[1][2]),
                         pbo.parse(outputs[1][1], prefixes=(addon.slot_prefix('a'),)))
        self.assertNotEqual(addon.slot_prefix('a'), addon.PREFIX)
        self.assertNotIn('1234567', json.dumps(receipt))

    def test_undeclared_provider_emits_no_pbo_and_missing_install_refuses(self):
        outputs, receipt = self.generate_providers([self.provider_rule()], declared=False)
        self.assertEqual([addon.PBO_NAME], [name for name, _, _ in outputs])
        self.assertEqual([addon.PBO_NAME], receipt['pbos'])
        self.assertEqual('absent', receipt['optional'][0]['status'])
        (self.root / 'workshop/1234567').rmdir()
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.generate_providers([self.provider_rule()], installed=False)

    def test_parent_in_another_provider_pbo_is_refused(self):
        item, _, _ = self.stack()
        providers = [{'slot': 'a', 'item': item}, {'slot': 'b', 'item': '7654321'}]
        second = self.provider_rule(id='r2', **{'class': 'Other', 'parent': 'Child'})
        second['provider'] = 'b'
        rows = [self.provider_rule(), second]
        with self.assertRaisesRegex(ValueError, 'another compat PBO'):
            addon.load_rules([self.rules(dependency=rows, providers=providers)], self.root)

    def test_banned_provider_tokens_in_output_are_refused(self):
        with self.assertRaises(ValueError):
            self.generate(dependency=[self.rule(**{'class': 'Snafu' + '_Child'})])

    def test_receipt_check_matches_shipped_pbos(self):
        outputs, receipt = self.generate_providers([self.provider_rule()])
        present = {addon.ADDONS_DIR + name: hashlib.sha256(blob).hexdigest()
                   for name, blob, _ in outputs}
        self.assertEqual([], addon.check_receipt(receipt, present))
        changed = dict(present, **{addon.ADDONS_DIR + addon.PBO_NAME: '0' * 64})
        self.assertTrue(addon.check_receipt(receipt, changed))
        self.assertTrue(addon.check_receipt(receipt, {k: v for k, v in present.items()
                                                      if not k.endswith(addon.slot_pbo('a'))}))
        self.assertTrue(addon.check_receipt(None, present))
        outputs, receipt = self.generate_providers([self.provider_rule()], declared=False)
        absent = {addon.ADDONS_DIR + addon.PBO_NAME: receipt['sha256']}
        self.assertEqual([], addon.check_receipt(receipt, absent))
        stray = dict(absent, **{addon.ADDONS_DIR + addon.slot_pbo('a'): '0' * 64})
        self.assertTrue(addon.check_receipt(receipt, stray))

    def test_strings_are_packed_when_present(self):
        self.strings.write_text(json.dumps({'schema': 1, 'strings': [{'key': 'STR_k', 'text': 'Own words'}]}))
        blob, files, receipt = self.generate()
        self.assertEqual({'config.cpp', 'stringtable.csv'}, set(files))
        self.assertEqual(1, receipt['strings'])
        self.assertEqual((addon.PREFIX, files), pbo.parse(blob, prefixes=(addon.PREFIX,)))

    def test_cli_writes_provider_pbos_and_source(self):
        item, workshop, manifest = self.stack()
        # The CLI validates against the real repository, so use one of its own patches.
        path = self.rules(dependency=[self.provider_rule()], providers=[{'slot': 'a', 'item': item}],
                          required=sorted(addon.own_patches())[:1])
        out = self.root / 'out2'
        args = ['--out', str(out), '--rules', str(path), '--strings', str(self.strings),
                '--workshop', str(workshop), '--manifest', str(manifest), '--source']
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, addon.main(args))
        receipt = json.loads((out / 'compat-addon.json').read_text())
        for name in receipt['pbos']:
            self.assertTrue((out / name).is_file())
        self.assertTrue((out / 'source/a/config.cpp').is_file())

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
