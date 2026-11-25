"""Synthetic RPT/RAP evidence only; no DayZ behaviour or real log content."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.audit import rpt_config_audit as audit
from tests.unit.test_pbo_config import klass, pbo, rap


SAMPLE_LINES = {
    1: "Warning Message: No entry 'CfgVehicles.Synthetic.missing'",
    2: '[CE][LootRespawner] Item [1] is hard to place',
    3: 'Trying to access error value',
    5: '[CE][Point] Removing 1, 2 from synthetic proxy',
    6: '[CE][VehicleRespawner] Synthetic - Failed to spawn',
    8: '[CE][SpawnRandomLoot] lootmax != containermaxsum',
    10: 'Convex component selection faces are less then 3',
    13: 'Placement slopelandcontact failed on model synthetic.p3d',
    14: "Graph Snake/anims/animgraph/snake.agr doesn't have variable synthetic",
    4: "Warning Message: Size: '/' not an array",
    7: 'Warning Message: Cannot load synthetic/clip.anm',
    9: 'Warning Message: Wrong inventory shape="synthetic/case.p3d"',
    11: "Warning Message: Unknown object class 'SyntheticPond'",
    12: 'Warning Message: String STR_SYNTHETIC not found in localization table',
    15: 'Warning Message: UAGestureSlot inputs inserted twice',
}


class ConfigAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rpt = self.root / 'synthetic.RPT'
        self.vanilla = self.root / 'baseline.RPT'
        self.rpt.write_text('', encoding='utf-8')
        self.vanilla.write_text('', encoding='utf-8')

    def logs(self, observed, baseline=''):
        self.rpt.write_text(observed, encoding='utf-8')
        self.vanilla.write_text(baseline, encoding='utf-8')

    def addon(self, name, owner_class, **fields):
        path = self.root / (name + '.pbo')
        config = klass('', CfgVehicles=klass('', **{owner_class: klass('', **fields)}))
        path.write_bytes(pbo({'config.bin': rap(config), 'clip.anm': b'SYNTHETIC'}, prefix=name))
        return path

    def test_all_categories_have_specific_precedence_and_unknowns(self):
        samples = SAMPLE_LINES
        rules = audit.category_rules()
        for category, line in samples.items():
            with self.subTest(category=category):
                self.assertEqual(audit.classify(line, rules), category)
                self.assertEqual(audit.classify('Warning Message: ' + line, rules), category)
        self.assertEqual(audit.classify('ZSUSkeleton missing bone SyntheticBone', rules), 15)
        self.assertEqual(audit.classify('Unknown synthetic warning', rules), 0)
        self.assertEqual(audit.classify('Server ready', rules), audit.ENGINE_NOISE)
        unknown = 'Unknown synthetic warning\n'
        self.logs('\n'.join(samples.values()) + '\n' + unknown)
        result = audit.audit(self.rpt, self.vanilla)
        self.assertEqual({row['category'] for row in result['diagnostics']}, set(samples) | {0})
        self.assertTrue(result['taxonomy_complete'])
        self.assertEqual(set(samples), set(audit.RULES))
        self.assertEqual(result['unclassified_count'], len(unknown.splitlines()))
        self.assertTrue(all(row['matcher_available'] == (row['category'] in rules)
                            for row in result['categories']))

    def test_baseline_counts_do_not_hide_excess_or_unrelated_warnings(self):
        common = "Warning Message: No entry 'CfgVehicles/Synthetic/missing'\n"
        self.logs('12:34:56 ' + common + '12:34:57 ' + common +
                  "Unknown object class 'SyntheticOther'\n", '00:00:01 ' + common)
        result = audit.audit(self.rpt, self.vanilla)
        no_entry = next(row for row in result['diagnostics'] if row['category'] == 1)
        self.assertEqual(no_entry['count'], 2)
        self.assertEqual(no_entry['vanilla_matches'], 1)
        self.assertEqual(no_entry['excess_count'], 1)
        other = next(row for row in result['diagnostics'] if row['category'] == 11)
        self.assertEqual(other['vanilla_matches'], 0)
        self.assertEqual(other['attribution'], 'unresolved')

    def test_rap_candidates_reopenings_nested_types_and_resources(self):
        ours = self.addon('synthetic_hc', 'SyntheticShared', inventorySlot=['SyntheticSlot'],
                          AnimationSources=klass('', syntheticField=1))
        dep = self.addon('synthetic_dep', 'SyntheticShared', displayName='$STR_SYNTHETIC')
        vanilla = self.addon('synthetic_stock', 'SyntheticStock')
        self.logs("No entry 'CfgVehicles/SyntheticShared/AnimationSources/syntheticField'\n"
                  "No entry 'CfgVehicles/SyntheticStock/missing'\n"
                  'Cannot load synthetic_dep/clip.anm\n'
                  'String STR_SYNTHETIC not found in localization table\n')
        result = audit.audit(self.rpt, self.vanilla,
                             {'ours': [ours], 'dependency': [dep], 'vanilla': [vanilla]})
        shared = next(row for row in result['diagnostics'] if row['declared_field_types'])
        self.assertEqual(shared['origin_candidates'], ['dependency', 'ours'])
        self.assertEqual(shared['attribution'], 'ambiguous')
        self.assertEqual(shared['declared_field_types'], ['scalar'])
        stock = next(row for row in result['diagnostics'] if row['origin_candidates'] == ['vanilla'])
        self.assertEqual(stock['attribution'], 'candidate')
        for row in result['diagnostics']:
            if row['category'] in (7, 12):
                self.assertEqual(row['origin_candidates'], ['dependency'])
        self.assertEqual(result['pbo_counts'], result['config_counts'])
        self.assertNotIn('SyntheticShared', json.dumps(result))

    def test_complete_local_taxonomy_is_possible_without_serializing_patterns(self):
        rules = audit.category_rules()
        missing = set(rules)
        patterns = [f'{key}=synthetic_category_{key}\\b' for key in sorted(missing)]
        self.logs('\n'.join(f'synthetic_category_{key}' for key in missing))
        result = audit.audit(self.rpt, self.vanilla, overrides=patterns)
        self.assertTrue(result['taxonomy_complete'])
        self.assertEqual({row['category'] for row in result['diagnostics']}, missing)
        self.assertNotIn('synthetic_category', json.dumps(result))
        for invalid in ('0=x', '16=x', 'missing=x', '2=', '2=['):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                audit.category_rules([invalid])

    def invoke(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = audit.main(args)
        return status, stdout.getvalue() + stderr.getvalue()

    def test_cli_emits_no_input_strings_even_on_argument_and_storage_errors(self):
        # Synthetic identity canaries are assembled to avoid resembling private
        # material in this public test source. No player identity is ever emitted.
        canary = 'Synthetic' + 'IdentityCanary'
        private_home = '/' + 'home' + '/' + canary + '/secret.RPT'
        private_windows = 'C:' + '\\' + 'Users' + '\\' + canary + '\\secret.RPT'
        steam_like = '7' * 17
        self.logs(f'No entry "{private_home}" player="{canary}" id={steam_like}\n'
                  f'Warning Message: {private_windows}\n')
        output = self.root / 'compat_audit.json'
        status, messages = self.invoke([str(self.rpt), '--vanilla-rpt', str(self.vanilla),
                                        '--output', str(output)])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.read_text())['evidence'], 'offline_only')
        serialized = messages + output.read_text()
        for private in (canary, private_home, private_windows, steam_like, str(self.root)):
            self.assertNotIn(private, serialized)
        for args in ([private_home], [private_home, '--vanilla-rpt', private_windows],
                     [str(self.rpt), '--vanilla-rpt', str(self.vanilla), '--secret=' + canary],
                     [str(self.rpt), '--vanilla-rpt', str(self.vanilla),
                      '--category-pattern', '2=[' + canary],
                     [str(self.rpt), '--vanilla-rpt', str(self.vanilla), '--output', private_home]):
            status, messages = self.invoke(args)
            self.assertEqual(status, 2)
            self.assertEqual(messages, 'compat_audit: input_or_storage_error\n')

    def test_input_aliases_conflicting_owners_and_corrupt_rap_fail_closed(self):
        original = 'Warning Message: synthetic\n'
        self.logs(original)
        status, _ = self.invoke([str(self.rpt), '--vanilla-rpt', str(self.vanilla),
                                 '--output', str(self.rpt)])
        self.assertEqual(status, 2)
        self.assertEqual(self.rpt.read_text(), original)
        addon = self.addon('synthetic_dep', 'Synthetic')
        with self.assertRaises(audit.InputError):
            audit.audit(self.rpt, self.vanilla, {'ours': [addon], 'dependency': [addon]})
        addon.write_bytes(pbo({'config.bin': b'not RAP'}))
        output = self.root / 'compat_audit.json'
        status, messages = self.invoke([str(self.rpt), '--vanilla-rpt', str(self.vanilla),
                                        '--dependency-pbo', str(addon), '--output', str(output)])
        self.assertEqual(status, 2)
        self.assertFalse(output.exists())
        self.assertEqual(messages, 'compat_audit: input_or_storage_error\n')

    def test_directory_discovery_and_absent_config_are_visible(self):
        addon = self.root / 'synthetic.PBO'
        addon.write_bytes(pbo({'clip.anm': b'SYNTHETIC'}, prefix='synthetic'))
        result = audit.audit(self.rpt, self.vanilla, {'dependency': [self.root]})
        self.assertEqual(result['pbo_counts']['dependency'], 1)
        self.assertEqual(result['config_counts']['dependency'], 0)
        with self.assertRaises(audit.InputError):
            audit.pbo_files([self.root / 'nonexistent'])

    def test_oversized_lines_are_counted_and_next_warning_survives(self):
        self.logs('x' * (audit.MAX_LINE * 2) + '\nNo entry synthetic\n')
        result = audit.audit(self.rpt, self.vanilla)
        self.assertEqual(result['oversized_lines'], 1)
        self.assertEqual(sum(row['count'] for row in result['diagnostics']), 1)

    def test_totals_keep_all_occurrences_when_detailed_diagnostics_overflow(self):
        self.logs('No entry CensusCanaryAlpha\nNo entry CensusCanaryBeta\nNo entry CensusCanaryAlpha\nUnknown warning\n' +
                  'x' * (audit.MAX_LINE * 2) + '\nWarning Message: UAGestureSlot inserts twice\n',
                  'No entry CensusCanaryAlpha\n')
        output = self.root / 'totals.json'
        with patch.object(audit, 'MAX_DIAGNOSTICS', 1):
            with self.assertRaisesRegex(audit.InputError, 'diagnostic_budget'):
                audit.audit(self.rpt, self.vanilla)
            status, _ = self.invoke([str(self.rpt), '--vanilla-rpt', str(self.vanilla), '--totals-only',
                                     '--output', str(output)])
        self.assertEqual(status, 0)
        result = json.loads(output.read_text())
        rows = {row['category']: row for row in result['categories']}
        self.assertEqual((rows[1]['count'], rows[1]['vanilla_count']), (3, 1))
        self.assertEqual(rows[15]['count'], 1)
        self.assertEqual(result['unclassified_count'], 1)
        self.assertEqual(result['oversized_lines'], 1)
        self.assertNotIn('censuscanary', output.read_text().lower())

    def test_rap_cycles_are_rejected(self):
        import struct
        data = bytearray(rap(klass('', CfgVehicles=klass(''))))
        offset_start = 16 + len(b'\0\x01\x00CfgVehicles\0')
        data[offset_start:offset_start + 4] = struct.pack('<I', 16)
        addon = self.root / 'cycle.pbo'
        addon.write_bytes(pbo({'config.bin': bytes(data)}))
        with self.assertRaises(audit.InputError):
            audit.audit(self.rpt, self.vanilla, {'dependency': [addon]})


if __name__ == '__main__':
    unittest.main()
