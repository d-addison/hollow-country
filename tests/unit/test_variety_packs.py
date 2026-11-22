"""Synthetic fixtures for the variety pack rules plus consistency checks of the committed data.

Nothing here establishes DayZ behaviour; the fixtures are explicit and the data checks derive their
expectations from the committed rules and outputs, never from counts or class names.
"""
import copy
import json
import math
from pathlib import Path
import unittest

from tools.package import optional_overlays, variety_optional, variety_packs as vp
from tools.package import generated_digests, regenerate_all
from tools.setup import workshop_sync

ROOT = Path(__file__).resolve().parents[2]
RULES = json.loads((ROOT / vp.RULES).read_bytes())
CE = json.loads((ROOT / vp.CE_OUT).read_bytes())
DISPOSITIONS = json.loads((ROOT / vp.DISPOSITIONS_OUT).read_bytes())
FLOOR = json.loads((ROOT / vp.FLOOR_POLICY).read_bytes())


def config_row(name, parent='', **fields):
    return {'root': 'CfgVehicles', 'name': name, 'parent': parent, 'fields': {'scope': 2, **fields},
            'nutrition': None, 'pbo': 'synthetic.pbo'}


def stock_row(name, nominal, **extra):
    row = {'name': name, 'nominal': nominal, 'min': 1, 'lifetime': 3888000, 'restock': 0, 'quantmin': -1,
           'quantmax': -1, 'cost': 100, 'flags': {'count_in_cargo': '0'}, 'category': 'food',
           'tags': ['shelves'], 'usage': ['Town'], 'value': []}
    row.update(extra)
    return row


def rule(identifier, disposition, **keys):
    out = {'id': identifier, 'disposition': disposition}
    if disposition == 'excluded':
        out['reason'] = 'synthetic_reason'
    if disposition == 'crafted':
        out.update(reason='synthetic_reason', evidence='derived')
    out.update(keys)
    return out


def document(packs):
    data = copy.deepcopy(RULES)
    data['packs'] = packs
    return data


def pack(rules, **extra):
    return {'id': '1', 'name': 'Synthetic', 'folder': '@Synthetic', 'licence': 'synthetic licence',
            'scope': 'synthetic scope', 'rules': rules, **extra}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.vanilla = {('CfgVehicles', n): r for n, r in {
            'Inventory_Base': config_row('Inventory_Base'),
            'Edible_Base': config_row('Edible_Base', 'Inventory_Base'),
            'PeerCan': config_row('PeerCan', 'Edible_Base'),
            'PeerJar': config_row('PeerJar', 'Edible_Base')}.items()}
        self.pack_rows = {('CfgVehicles', n): r for n, r in {
            'NewCan': config_row('NewCan', 'Edible_Base'),
            'NewCan_Opened': config_row('NewCan_Opened', 'Edible_Base'),
            'NewHidden': config_row('NewHidden', 'Edible_Base', scope=1)}.items()}
        self.stock = {'PeerCan': stock_row('PeerCan', 40), 'PeerJar': stock_row('PeerJar', 10)}
        self.index = vp.Index(self.vanilla, [self.pack_rows])

    def classify(self, rules, tokens=()):
        data = document([pack(rules)])
        parsed = vp.Rules(data)
        return vp.classify_pack(parsed.packs[0], parsed, self.index, self.pack_rows, self.stock, FLOOR, set(tokens)), parsed


class Classification(Fixture):
    def test_only_scope_two_classes_not_reopened_from_vanilla_are_in_scope(self):
        self.pack_rows[('CfgVehicles', 'PeerCan')] = config_row('PeerCan', 'Edible_Base')
        index = vp.Index(self.vanilla, [self.pack_rows])
        names = [key[1] for key in vp.scope_two_classes(self.pack_rows, set(self.vanilla), index)]
        self.assertEqual(names, ['NewCan', 'NewCan_Opened'])

    def test_unclassified_class_fails_naming_it(self):
        with self.assertRaises(ValueError) as caught:
            self.classify([rule('opened', 'excluded', name='.*_Opened')])
        self.assertIn('NewCan', str(caught.exception))
        self.assertNotIn('NewCan_Opened', str(caught.exception))

    def test_first_matching_rule_wins_and_every_entry_names_its_rule(self):
        (entries, _), _ = self.classify([rule('opened', 'excluded', name='.*_Opened'),
                                         rule('all', 'spawn', name='New.*', peers=['PeerCan'])])
        by_name = {e['name']: e for e in entries}
        self.assertEqual(by_name['NewCan_Opened']['rule'], 'opened')
        self.assertEqual(by_name['NewCan']['rule'], 'all')
        self.assertTrue(all(e['rule'] for e in entries))

    def test_spawn_budget_is_the_peer_nominal_at_the_scarcity_divisor(self):
        (entries, _), parsed = self.classify([rule('opened', 'excluded', name='.*_Opened'),
                                              rule('all', 'spawn', name='New.*', peers=['PeerCan', 'PeerJar'])])
        spawn = [e for e in entries if e['disposition'] == 'spawn']
        peer_total = sum(self.stock[n]['nominal'] for n in ('PeerCan', 'PeerJar'))
        self.assertEqual(sum(e['nominal'] for e in spawn), max(len(spawn), math.ceil(peer_total / parsed.divisor)))

    def test_spawn_without_peers_on_a_generic_anchor_is_refused(self):
        self.assertIn('Edible_Base', self.index.chain(('CfgVehicles', 'NewCan')))
        data = document([pack([rule('all', 'spawn', name='New.*')])])
        parsed = vp.Rules(data)
        parsed.generic = {'Edible_Base'}
        with self.assertRaises(ValueError):
            vp.classify_pack(parsed.packs[0], parsed, self.index, self.pack_rows, self.stock, FLOOR, set())

    def test_peers_without_a_stock_row_are_refused(self):
        with self.assertRaises(ValueError):
            self.classify([rule('all', 'spawn', name='New.*', peers=['NoSuchPeer'])])

    def test_script_evidence_is_required_for_a_crafted_class(self):
        rules = [rule('c', 'crafted', name='New.*', evidence='script')]
        with self.assertRaises(ValueError):
            self.classify(rules)
        (entries, _), _ = self.classify(rules, tokens={'NewCan', 'NewCan_Opened'})
        self.assertEqual({e['disposition'] for e in entries}, {'crafted'})

    def test_crafted_rows_never_spawn_and_carry_the_crafted_flag(self):
        (entries, _), parsed = self.classify([rule('c', 'crafted', name='New.*')])
        for entry in entries:
            out = vp._type_row(entry, parsed, self.stock, FLOOR['shelf_tag'], set(FLOOR['floor_categories']))
            self.assertEqual((out['nominal'], out['min'], out['flags']['crafted']), (0, 0, '1'))
            self.assertEqual(out['lifetime'], parsed.crafted_lifetime)

    def test_nutrition_outlier_becomes_an_explicit_exclusion_with_a_reason(self):
        self.vanilla[('CfgVehicles', 'PeerCan')]['nutrition'] = {'energy': 100, 'water': 100}
        self.pack_rows[('CfgVehicles', 'NewCan')]['nutrition'] = {
            'energy': 100 * (RULES['nutrition']['exclude_ratio'] + 1), 'water': 100}
        self.index = vp.Index(self.vanilla, [self.pack_rows])
        (entries, _), _ = self.classify([rule('opened', 'excluded', name='.*_Opened'),
                                         rule('all', 'spawn', name='New.*', peers=['PeerCan'])])
        entry = next(e for e in entries if e['name'] == 'NewCan')
        self.assertEqual(entry['disposition'], 'excluded')
        self.assertTrue(entry['reason'])
        self.assertNotIn('nominal', entry)


class RuleValidation(unittest.TestCase):
    def bad(self, change):
        data = copy.deepcopy(RULES)
        change(data['packs'][0])
        with self.assertRaises(ValueError):
            vp.Rules(data)

    def test_committed_rules_load(self):
        self.assertTrue(vp.Rules(copy.deepcopy(RULES)).packs)

    def test_spawn_rule_with_a_reason_and_non_spawn_rule_without_one_are_refused(self):
        spawn = lambda p: next(r for r in p['rules'] if r['disposition'] == 'spawn')
        other = lambda p: next(r for r in p['rules'] if r['disposition'] != 'spawn')
        self.bad(lambda p: spawn(p).update(reason='because'))
        self.bad(lambda p: other(p).pop('reason'))

    def test_crafted_rule_needs_evidence_and_others_must_not_have_it(self):
        crafted = next(r for p in RULES['packs'] for r in p['rules'] if r['disposition'] == 'crafted')
        pack_index = next(i for i, p in enumerate(RULES['packs']) if crafted in p['rules'])
        data = copy.deepcopy(RULES)
        next(r for r in data['packs'][pack_index]['rules'] if r['id'] == crafted['id']).pop('evidence')
        with self.assertRaises(ValueError):
            vp.Rules(data)

    def test_rule_matching_nothing_and_duplicate_ids_are_refused(self):
        self.bad(lambda p: p['rules'].append({'id': 'x', 'disposition': 'excluded', 'reason': 'r'}))
        self.bad(lambda p: p['rules'].append(dict(p['rules'][0])))

    def test_every_non_spawn_rule_names_its_reason(self):
        for entry in RULES['packs']:
            for item in entry['rules']:
                self.assertEqual(bool(item.get('reason')), item['disposition'] != 'spawn', item['id'])


class SettingsFiles(unittest.TestCase):
    ENTRY = {'id': 's', 'root': 'profile', 'target': 'Dir/Sub/file.json', 'tokens': ['file'],
             'reason': 'because', 'json': {'Outer': {'Inner': 1}, 'List': [{'Leaf': 0}]}}

    def with_entry(self, **change):
        entry = {**self.ENTRY, **change}
        return pack([rule('r', 'excluded', name='.*')], settings_files=[entry])

    def test_json_keys_are_collected_through_objects_and_lists(self):
        self.assertEqual(vp.json_keys(self.ENTRY['json']), {'Outer', 'Inner', 'List', 'Leaf'})

    def test_every_key_and_token_must_appear_in_the_pack_scripts(self):
        spec = self.with_entry()
        everything = vp.json_keys(self.ENTRY['json']) | set(self.ENTRY['tokens'])
        rows = vp.settings_rows(spec, everything)
        self.assertEqual([r['target'] for r in rows], [self.ENTRY['target']])
        for drop in sorted(everything):
            with self.assertRaises(ValueError) as caught:
                vp.settings_rows(spec, everything - {drop})
            self.assertIn(drop, str(caught.exception))

    def test_invalid_entries_are_refused(self):
        for change in ({'root': 'elsewhere'}, {'target': '../escape/x.json'}, {'target': 'plain.json'},
                       {'target': '/abs/x.json'}, {'target': 'a\\b/x.json'}, {'reason': ''}, {'json': {}},
                       {'extra': 1}):
            with self.assertRaises(ValueError, msg=str(change)):
                vp.Rules(document([self.with_entry(**change)]))
        vp.Rules(document([self.with_entry()]))

    def test_committed_settings_are_listed_in_the_dispositions_with_their_reason(self):
        for entry in RULES['packs']:
            listed = {s['id']: s for p in DISPOSITIONS['packs'] if p['id'] == entry['id'] for s in p['settings']}
            self.assertEqual(set(listed), {s['id'] for s in entry.get('settings_files', ())})
            for item in entry.get('settings_files', ()):
                self.assertEqual(listed[item['id']]['reason'], item['reason'])


class CommittedData(unittest.TestCase):
    def test_every_pack_in_the_rules_has_one_disposition_per_class_and_one_ce_entry(self):
        self.assertEqual([p['id'] for p in RULES['packs']], [p['id'] for p in DISPOSITIONS['packs']])
        self.assertEqual({p['id'] for p in RULES['packs']}, set(CE['packs']))
        for entry in DISPOSITIONS['packs']:
            names = [c['name'] for c in entry['classes']]
            self.assertEqual(len(names), len(set(names)), entry['id'])
            self.assertEqual(entry['total'], len(names))
            self.assertEqual(sum(entry['counts'].values()), len(names))

    def test_no_class_is_silently_zeroed(self):
        for entry in DISPOSITIONS['packs']:
            for item in entry['classes']:
                self.assertIn(item['disposition'], vp.DISPOSITIONS)
                if item['disposition'] == 'spawn':
                    self.assertGreaterEqual(item['nominal'], 1, item['name'])
                    self.assertNotIn('reason', item)
                else:
                    self.assertTrue(item['reason'], item['name'])
                    self.assertNotIn('nominal', item)

    def test_ce_rows_are_exactly_the_spawn_and_crafted_classes(self):
        for entry in DISPOSITIONS['packs']:
            wanted = {c['name'] for c in entry['classes'] if c['disposition'] != 'excluded'}
            rows = {r['name'] for r in CE['packs'][entry['id']]['types']}
            self.assertEqual(rows, wanted)

    def test_crafted_rows_have_no_budget_and_spawn_rows_follow_the_disposition_nominal(self):
        for entry in DISPOSITIONS['packs']:
            kinds = {c['name']: c for c in entry['classes']}
            for row in CE['packs'][entry['id']]['types']:
                source = kinds[row['name']]
                if source['disposition'] == 'crafted':
                    self.assertEqual((row['nominal'], row['min'], row['flags']['crafted']), (0, 0, '1'))
                else:
                    self.assertEqual(row['nominal'], source['nominal'])
                    self.assertTrue(row['usage'], row['name'])

    def test_no_pack_row_is_floor_loot_outside_the_floor_policy(self):
        floor = set(FLOOR['floor_categories'])
        for entry in CE['packs'].values():
            for row in entry['types']:
                if row['nominal'] and row['category'] not in floor:
                    self.assertEqual(row['tags'], [FLOOR['shelf_tag']], row['name'])

    def test_ce_document_is_what_the_runtime_parser_accepts(self):
        packs = variety_optional.parse((ROOT / vp.CE_OUT).read_bytes())
        self.assertEqual(set(packs), set(CE['packs']))
        for ident, entry in packs.items():
            self.assertLessEqual(len(entry['types']), variety_optional.MAX_ROWS, ident)

    def test_the_committed_outputs_are_the_generator_outputs_list(self):
        self.assertEqual(set(vp.OUTPUTS), {vp.CE_OUT, vp.DISPOSITIONS_OUT})
        for rel in vp.OUTPUTS:
            self.assertTrue((ROOT / rel).is_file(), rel)


class Wiring(unittest.TestCase):
    def test_every_pack_is_a_manifest_dependency_with_a_known_group_and_folder(self):
        manifest = json.loads((ROOT / 'tools/setup/workshop_mods.json').read_bytes())
        rows = manifest['mods'] if isinstance(manifest, dict) else manifest
        by_id = {str(r['id']): r for r in rows}
        for entry in RULES['packs']:
            row = by_id[entry['id']]
            self.assertIn(row['group'], workshop_sync.GROUPS)
            self.assertEqual(row['folder'], entry['folder'])
            self.assertFalse(row['publish'])

    def test_every_pack_in_the_shipped_document_is_a_default_overlay_pack(self):
        ids = set(variety_optional.pack_ids(ROOT / vp.CE_OUT))
        self.assertTrue(ids)
        self.assertLessEqual(ids, set(optional_overlays.DEFAULT_OVERLAY_IDS))

    def test_the_generator_is_checked_and_its_digest_contract_exists(self):
        generator = next(g for g in regenerate_all.GENERATORS if g.name == 'variety_packs')
        self.assertIn('--check', generator.arguments)
        self.assertIn('variety_packs', generator.inputs)
        names = {c.name for c in generated_digests.contracts()}
        self.assertIn('variety_packs', names)
        contract = next(c for c in generated_digests.contracts() if c.name == 'variety_packs')
        self.assertEqual(set(contract.outputs), set(vp.OUTPUTS))

    def test_the_runtime_helper_and_document_ship_in_the_bundle_and_the_mission_pbo(self):
        from tools.package import pbo
        from tools.setup import friend_bundle
        self.assertIn('variety_optional.py', friend_bundle.BUNDLE_TOOLS)
        self.assertIn('optional/' + variety_optional.RELATIVE, pbo.MISSION_FILES)


if __name__ == '__main__':
    unittest.main()
