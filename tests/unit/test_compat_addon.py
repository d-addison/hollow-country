"""Offline tooling checks for the compat addon generator; not DayZ behaviour."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
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
        config = self.root / 'mods/HollowCountryExpansionAI/config.cpp'
        config.parent.mkdir(parents=True)
        config.write_text('class CfgPatches\n{\n    class %s\n    {\n        requiredAddons[] = {"X"};\n'
                          '    };\n};\nclass CfgVehicles { class Other {}; };\n' % OWN)
        # Built offline and never shipped: must not widen the mandatory set.
        assets = self.root / 'mods/HollowCountryAssets/config.cpp'
        assets.parent.mkdir(parents=True)
        assets.write_text('class CfgPatches\n{\n    class AssetsPatch\n    {\n'
                          '        requiredAddons[] = {"AssetOnly"};\n    };\n};\n')
        self.strings = self.root / 'strings.json'
        self.strings.write_text(json.dumps({'schema': 1, 'strings': []}))
        self.vanilla = self.root / 'vanilla'
        self.vanilla.mkdir()

    @staticmethod
    def config_text(patch, sections):
        """Plain config text: sections is {section: [(class, parent or None)]}."""
        lines = ['class CfgPatches', '{', '    class %s' % patch, '    {',
                 '        requiredAddons[] = {};', '    };', '};']
        for section, rows in sections.items():
            lines += ['class %s' % section, '{']
            lines += ['    class %s: %s {};' % (name, parent) if parent else '    class %s {};' % name
                      for name, parent in rows]
            lines.append('};')
        return '\n'.join(lines) + '\n'

    def put_pbo(self, directory, name, patch, sections):
        directory.mkdir(parents=True, exist_ok=True)
        text = self.config_text(patch, sections).encode()
        (directory / name).write_bytes(pbo.pack({'config.cpp': text}, prefix='HollowCountryExpansionAI'))

    def upstream(self, rows, patch='X', skip=()):
        """Vanilla PBO defining every rule target with its own parent, and every parent as a root.

        The patch X is also the fixture's mandatory requiredAddons entry, so the parent lives in the chain."""
        sections = {}
        targets = {(r['section'], r['class'].casefold()) for r in rows}
        for r in rows:
            if r['class'] in skip:
                continue
            sections.setdefault(r['section'], []).append((r['class'], r['parent']))
        for r in rows:
            if (r['section'], r['parent'].casefold()) not in targets:
                known = {name.casefold() for name, _ in sections.setdefault(r['section'], [])}
                if r['parent'].casefold() not in known:
                    sections[r['section']].append((r['parent'], None))
        self.put_pbo(self.vanilla, 'x.pbo', patch, sections)

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

    def generate(self, upstream=True, **kw):
        rows = [*kw.get('own', ()), *kw.get('dependency', ())]
        if upstream:
            self.upstream(rows)
        return addon.generate([self.rules(**kw)], self.strings, self.root, vanilla=self.vanilla)

    def stack(self, declared=True, installed=True, provider_patch='DepAddon'):
        """Fixture Workshop root and stack manifest for the provider item."""
        item = '1234567'
        workshop = self.root / 'workshop'
        workshop.mkdir(exist_ok=True)
        if installed:
            (workshop / item).mkdir(exist_ok=True)
            if provider_patch:
                self.put_pbo(workshop / item / 'addons', 'dep.pbo', provider_patch, {})
        manifest = self.root / 'stack.json'
        manifest.write_text(json.dumps({'schema': 1, 'mods': (
            [{'id': item, 'publish': False}] if declared else [])}))
        return item, workshop, manifest

    def generate_providers(self, rows, declared=True, installed=True, provider_patch='DepAddon', upstream=True):
        item, workshop, manifest = self.stack(declared, installed, provider_patch)
        if upstream:
            self.upstream(rows)
        path = self.rules(dependency=rows, providers=[{'slot': 'a', 'item': item}])
        return addon.generate_all([path], self.strings, self.root, workshop, manifest, self.vanilla)

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
        self.upstream([self.rule(id='x', **{'class': 'Extra'})])
        _, files, _ = addon.generate([self.rules(), extra], self.strings, self.root, vanilla=self.vanilla)
        self.assertIn('class Extra: Base', files['config.cpp'].decode())
        with self.assertRaises(ValueError):
            addon.generate([self.rules(), self.rules(name='again.json')], self.strings, self.root,
                           vanilla=self.vanilla)

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
        shutil.rmtree(self.root / 'workshop/1234567')
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

    # ---- shipped-catalogue own set (P2-a)
    def test_own_set_follows_the_shipped_catalogue_not_every_config(self):
        self.assertEqual({OWN}, addon.own_patches(self.root))
        self.assertEqual({OWN.casefold(), 'x'}, addon.chain_addons(self.root))
        self.assertNotIn('assetonly', addon.mandatory_addons(self.root))
        self.assertNotIn('assetspatch', addon.mandatory_addons(self.root))
        with self.assertRaisesRegex(ValueError, 'optional addon'):
            addon.load_rules([self.rules(dependency=[self.rule(requires=['AssetOnly'])])], self.root)
        with self.assertRaises(ValueError):
            addon.load_rules([self.rules(required=['AssetsPatch'])], self.root)

    def test_release_injected_blocks_do_not_widen_the_mandatory_set(self):
        config = self.root / 'mods/HollowCountryExpansionAI/config.cpp'
        config.write_text(config.read_text().replace(
            'requiredAddons[] = {"X"};',
            'requiredAddons[] = {"X"/* BEGIN HC inventory dependencies */, "PackOnly"/* END HC inventory dependencies */};'))
        self.assertNotIn('packonly', addon.chain_addons(self.root))
        config.write_text(config.read_text().replace('"PackOnly"', '"Y"').replace(
            'requiredAddons[] = {"X"/*', 'requiredAddons[] = {"X", "Z"/*'))
        self.assertIn('z', addon.chain_addons(self.root))

    def test_vanilla_patches_resolve_as_vanilla_not_optional(self):
        row = self.rule(requires=['Vanilla_Gear'])
        addon.load_rules([self.rules(dependency=[row])], self.root, frozenset({'vanilla_gear'}))
        with self.assertRaisesRegex(ValueError, 'optional addon'):
            addon.load_rules([self.rules(dependency=[row])], self.root)
        item, _, _ = self.stack()
        providers = [{'slot': 'a', 'item': item}]
        # A vanilla parent never needs a provider slot.
        with self.assertRaisesRegex(ValueError, 'only mandatory addons'):
            addon.load_rules([self.rules(dependency=[dict(row, provider='a')], providers=providers)],
                             self.root, frozenset({'vanilla_gear'}))

    def test_vanilla_requires_end_to_end(self):
        row = self.rule(requires=['Vanilla_Gear'])
        self.put_pbo(self.vanilla, 'gear.pbo', 'Vanilla_Gear', {addon.SECTIONS[0]: [('Base', None)]})
        self.put_pbo(self.vanilla, 'x.pbo', 'X', {addon.SECTIONS[0]: [('Child', 'Base')]})
        _, files, receipt = addon.generate([self.rules(dependency=[row])], self.strings, self.root,
                                           vanilla=self.vanilla)
        self.assertIn('"Vanilla_Gear"', files['config.cpp'].decode())
        self.assertEqual([OWN, 'Vanilla_Gear'], receipt['requiredAddons'])

    # ---- upstream verification (P2-b, P2-c)
    def refused(self, code, rows=(), upstream=None, **kw):
        if upstream is not None:
            for stale in self.vanilla.glob('*.pbo'):
                stale.unlink()
            for name, patch, sections in upstream:
                self.put_pbo(self.vanilla, name, patch, sections)
        with self.assertRaisesRegex(ValueError, code):
            addon.generate([self.rules(dependency=list(rows), **kw)], self.strings, self.root,
                           vanilla=self.vanilla)

    def test_parent_must_match_the_installed_class(self):
        veh = addon.SECTIONS[0]
        self.refused('parent_mismatch', [self.rule()],
                     [('x.pbo', 'X', {veh: [('Base', None), ('Other2', None), ('Child', 'Other2')]})])
        self.refused('parent_ambiguous', [self.rule()],
                     [('x.pbo', 'X', {veh: [('Base', None), ('Other2', None), ('Child', 'Base')]}),
                      ('y.pbo', 'Y', {veh: [('Child', 'Other2')]})])
        self.refused('parent_unverified', [self.rule()],
                     [('x.pbo', 'X', {veh: [('Base', None), ('Child', None)]})])
        for stale in self.vanilla.glob('*.pbo'):
            stale.unlink()
        self.upstream([self.rule()])
        _, files, _ = addon.generate([self.rules(dependency=[self.rule(parent='BASE')])], self.strings,
                                     self.root, vanilla=self.vanilla)
        self.assertIn('class Child: BASE', files['config.cpp'].decode())

    def test_class_absent_upstream_needs_new_class_with_evidence(self):
        veh = addon.SECTIONS[0]
        absent = [('x.pbo', 'X', {veh: [('Base', None)]})]
        self.refused('class_absent_upstream', [self.rule()], absent)
        self.refused('class_absent_upstream', [self.rule(**{'class': 'Child', 'new_class': False})], absent)
        with self.assertRaisesRegex(ValueError, 'evidence'):
            addon.load_rules([self.rules(own=[self.rule(new_class=True, evidence='', requires=[])])], self.root)
        with self.assertRaisesRegex(ValueError, 'new_class'):
            addon.load_rules([self.rules(own=[self.rule(new_class='yes')])], self.root)
        _, files, _ = addon.generate([self.rules(dependency=[self.rule(new_class=True)])], self.strings,
                                     self.root, vanilla=self.vanilla)
        self.assertIn('class Child: Base', files['config.cpp'].decode())
        self.upstream([self.rule()])
        self.refused('new_class_exists', [self.rule(new_class=True)])

    def test_parent_must_exist_and_be_reachable(self):
        veh = addon.SECTIONS[0]
        self.refused('parent_missing', [self.rule()],
                     [('x.pbo', 'X', {veh: [('Child', 'Base')]})])
        outside = [('x.pbo', 'X', {veh: [('Child', 'Base')]}), ('z.pbo', 'Z', {veh: [('Base', None)]})]
        self.refused('parent_requires_missing', [self.rule()], outside)
        _, files, receipt = addon.generate([self.rules(dependency=[self.rule(requires=['X', 'Z'])])],
                                           self.strings, self.root, vanilla=self.vanilla)
        self.assertEqual([OWN, 'X', 'Z'], receipt['requiredAddons'])
        self.assertIn('class Child: Base', files['config.cpp'].decode())

    def test_provider_requires_must_come_from_the_installed_provider_item(self):
        rows = [self.provider_rule()]
        self.generate_providers(rows)
        with self.assertRaisesRegex(ValueError, 'provider_requires_missing'):
            self.generate_providers(rows, provider_patch='SomethingElse')
        with self.assertRaisesRegex(ValueError, 'provider_requires_missing'):
            self.generate_providers(rows, provider_patch=None)
        # The required patch exists, but in another declared item.
        item, workshop, manifest = self.stack(provider_patch='SomethingElse')
        other = workshop / '7654321'
        self.put_pbo(other / 'addons', 'other.pbo', 'DepAddon', {})
        manifest.write_text(json.dumps({'schema': 1, 'mods': [{'id': item, 'publish': False},
                                                              {'id': '7654321', 'publish': False}]}))
        self.upstream(rows)
        path = self.rules(dependency=rows, providers=[{'slot': 'a', 'item': item}])
        with self.assertRaisesRegex(ValueError, 'provider_requires_foreign'):
            addon.generate_all([path], self.strings, self.root, workshop, manifest, self.vanilla)

    def test_undeclared_provider_rules_are_not_verified(self):
        outputs, _ = self.generate_providers([self.provider_rule()], declared=False, provider_patch=None)
        self.assertEqual([addon.PBO_NAME], [name for name, _, _ in outputs])

    def test_unreadable_installed_config_refuses_with_a_fixed_reason(self):
        self.upstream([self.rule()])
        (self.vanilla / 'broken.pbo').write_bytes(b'not a pbo')
        with self.assertRaisesRegex(ValueError, 'unreadable installed config in broken.pbo'):
            addon.generate([self.rules(dependency=[self.rule()])], self.strings, self.root,
                           vanilla=self.vanilla)

    # ---- reserved words and receipt hashes (P3)
    def test_reserved_words_are_refused_as_names(self):
        for word in ('class', 'delete', 'import', 'Delete', 'ENUM', 'include'):
            for row in (self.rule(**{'class': word}), self.rule(parent=word), self.rule(requires=[word]),
                        self.rule(set={word: 1}), self.rule(set={word + '[]': [1]})):
                with self.subTest(word=word, row=row), self.assertRaises(ValueError):
                    addon.load_rules([self.rules(dependency=[row])], self.root)
        addon.load_rules([self.rules(dependency=[self.rule(**{'class': 'classy'}, set={'delete_me': 1})])],
                         self.root)

    def test_check_receipt_needs_64_hex_values(self):
        outputs, receipt = self.generate_providers([self.provider_rule()])
        base = addon.ADDONS_DIR + addon.PBO_NAME
        slot = addon.ADDONS_DIR + addon.slot_pbo('a')
        good = {base: receipt['sha256'], slot: receipt['optional'][0]['sha256']}
        self.assertEqual([], addon.check_receipt(receipt, good))
        self.assertEqual([], addon.check_receipt(receipt, {k: v.upper() for k, v in good.items()}))
        for bad in (None, '', 'abc', 'g' * 64, '0' * 63):
            with self.subTest(bad=bad):
                self.assertTrue(addon.check_receipt(receipt, dict(good, **{base: bad})))
        # None == None must not pass: a receipt without hashes is refused even when the shipped side has none.
        broken = json.loads(json.dumps(receipt))
        broken['sha256'] = None
        self.assertTrue(addon.check_receipt(broken, dict(good, **{base: None})))
        broken = json.loads(json.dumps(receipt))
        broken['optional'][0]['sha256'] = None
        self.assertTrue(addon.check_receipt(broken, dict(good, **{slot: None})))

    def test_check_hashes_compares_every_compat_pbo(self):
        outputs, receipt = self.generate_providers([self.provider_rule()])
        shas = {name: hashlib.sha256(blob).hexdigest() for name, blob, _ in outputs}
        self.assertEqual([], addon.check_hashes(receipt, shas))
        self.assertTrue(addon.check_hashes(receipt, {addon.PBO_NAME: shas[addon.PBO_NAME]}))
        self.assertTrue(addon.check_hashes(receipt, None))
        self.assertTrue(addon.check_hashes(receipt, dict(shas, **{addon.slot_pbo('a'): '1' * 64})))
        self.assertTrue(addon.check_hashes(receipt, dict(shas, **{addon.slot_pbo('b'): '1' * 64})))
        outputs, receipt = self.generate_providers([self.provider_rule()], declared=False)
        self.assertEqual([], addon.check_hashes(receipt, {addon.PBO_NAME: receipt['sha256']}))
        self.assertTrue(addon.check_hashes(receipt, {addon.PBO_NAME: receipt['sha256'],
                                                     addon.slot_pbo('a'): '1' * 64}))

    def test_declared_providers_lists_only_declared_slots_with_rules(self):
        item, workshop, manifest = self.stack()
        path = self.rules(dependency=[self.provider_rule()], providers=[{'slot': 'a', 'item': item}])
        self.assertEqual({'a': item}, addon.declared_providers([path], self.root, manifest))
        self.stack(declared=False)
        self.assertEqual({}, addon.declared_providers([path], self.root, manifest))
        self.assertEqual({}, addon.declared_providers([self.rules()], self.root, manifest))

    def test_strings_are_packed_when_present(self):
        self.strings.write_text(json.dumps({'schema': 1, 'strings': [{'key': 'STR_k', 'text': 'Own words'}]}))
        blob, files, receipt = self.generate()
        self.assertEqual({'config.cpp', 'stringtable.csv'}, set(files))
        self.assertEqual(1, receipt['strings'])
        self.assertEqual((addon.PREFIX, files), pbo.parse(blob, prefixes=(addon.PREFIX,)))

    def test_cli_writes_provider_pbos_and_source(self):
        item, workshop, manifest = self.stack()
        self.put_pbo(workshop / item / 'addons', 'dep.pbo', 'DepAddon', {addon.SECTIONS[0]: [('Base', None)]})
        # The CLI validates against the real repository, so use one of its own patches.
        path = self.rules(dependency=[self.provider_rule(new_class=True)], providers=[{'slot': 'a', 'item': item}],
                          required=sorted(addon.own_patches())[:1])
        out = self.root / 'out2'
        args = ['--out', str(out), '--rules', str(path), '--strings', str(self.strings),
                '--workshop', str(workshop), '--addons', str(self.vanilla), '--manifest', str(manifest),
                '--source']
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
