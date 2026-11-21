"""Activity audit behavior with synthetic RPTs; no engine behavior is inferred."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.release import activity_check as audit


def ready(module, enabled=True):
    return f'[HC Ready] module={module} enabled={str(enabled).lower()} ready=true reason=started runtime=PENDING\n'


def use(module, feature, count):
    return f'[HC Use] module={module} feature={feature} count={count}\n'


class UseActivityTests(unittest.TestCase):
    def report(self, server, client=()):
        activity = audit.UseActivity()
        for line in server:
            activity.observe(line)
        for line in client:
            activity.observe(line, client=True)
        return activity.result()

    def test_registration_first_use_and_repeated_summaries_reduce_to_max(self):
        module, feature = 'Workshop', 'recipe_done'
        result = self.report([use(module, feature, 0), ready(module),
                              use(module, feature, 1), use(module, feature, 7),
                              use(module, feature, 7), use(module, feature, 0)])
        row, = result['features']
        self.assertEqual((row['module'], row['feature']), (module, feature))
        self.assertEqual(row['count'], 7)
        self.assertEqual(row['status'], 'ACTIVE')
        self.assertEqual(result['count'], 0)

    def test_every_zero_registration_fails_without_player_waiting(self):
        module = 'Navigation'
        samples = [('map_open', 0), ('pin_drawn', 2), ('menu_open', 0)]
        result = self.report([ready(module)] + [use(module, f, c) for f, c in samples])
        expected = {f for f, c in samples if c == 0}
        self.assertEqual({r['feature'] for r in result['features'] if r['status'] == 'INERT'}, expected)
        self.assertEqual(result['count'], len(expected))

    def test_server_and_client_merge_independent_cumulative_counters(self):
        module, feature = 'Navigation', 'map_open'
        result = self.report([ready(module), use(module, feature, 0)],
                             [use(module, feature, 1), use(module, feature, 3)])
        row, = result['features']
        self.assertEqual(row['count'], 3)
        self.assertEqual(result['count'], 0)

    def test_missing_client_leaves_registered_ui_at_zero(self):
        features = ['map_open', 'inventory_open']
        result = self.report([ready('World')] + [use('ClientUI', f, 0) for f in features]
                             + [use('World', 'step_done', 1)])
        self.assertEqual({r['feature'] for r in result['features'] if r['status'] == 'INERT'}, set(features))

    def test_client_readiness_cannot_enable_or_disable_server_modules(self):
        result = self.report([ready('Enabled'), ready('Disabled', False),
                              use('Enabled', 'open', 0), use('Disabled', 'open', 0)],
                             [ready('Enabled', False), ready('Disabled'), use('Enabled', 'open', 1)])
        row, = result['features']
        self.assertEqual(row['module'], 'Enabled')
        self.assertEqual(row['status'], 'ACTIVE')

    def test_waiver_is_visible_and_not_active(self):
        module, feature, reason = 'RareEvent', 'meteor_seen', 'Requires a rare world event outside the scenario.'
        with patch.dict(audit.RELEASE_WAIVERS, {(module, feature): reason}):
            result = self.report([ready(module), use(module, feature, 0)])
            row, = result['features']
            self.assertEqual((row['status'], row['reason']), ('WAIVED', reason))
            self.assertEqual(result['activity'], 'waived')
            self.assertEqual(result['totals']['ACTIVE'], 0)
            self.assertEqual(result['count'], 0)
            active = self.report([ready(module), use(module, feature, 1)])
            self.assertEqual(active['features'][0]['status'], 'ACTIVE')

    def test_enabled_owner_without_registration_fails(self):
        result = self.report([ready('Missing')])
        row, = result['features']
        self.assertEqual((row['module'], row['status']), ('Missing', 'INERT'))
        self.assertGreater(result['count'], 0)

    def test_disabled_and_unknown_owner_counters_do_not_establish_admission(self):
        result = self.report([ready('Off', False), use('Off', 'spawned', 0), use('Unknown', 'spawned', 1)])
        self.assertEqual(result['features'], [])

    def test_missing_readiness_is_input_error(self):
        with self.assertRaises(ValueError):
            self.report([use('World', 'step_done', 1)])

    def test_malformed_counts_fail_closed(self):
        for count in ('-1', '1.5', 'NaN', '2147483648', '1garbage'):
            with self.subTest(count=count), self.assertRaises(ValueError):
                self.report([ready('World'), use('World', 'step_done', count)])

    def test_bounded_counter_storage(self):
        activity = audit.UseActivity()
        index = 0
        with self.assertRaises(ValueError):
            while index <= 1024:
                activity.observe(use('World', f'feature_{index}', 0))
                index += 1
        self.assertLessEqual(len(activity.counts), index)

    def test_privacy_filtered_lines_cannot_supply_activity(self):
        result = self.report([ready('World'), use('World', 'step_done', 0),
                              use('World', 'step_done', 3).rstrip() + ' password=private\n'])
        self.assertEqual(result['features'][0]['status'], 'INERT')

    def test_tokens_and_same_feature_in_distinct_modules(self):
        modules = ['World.A', 'World-B']
        result = self.report([ready(m) for m in modules] + [use(m, 'shared_feature', i) for i, m in enumerate(modules)])
        self.assertEqual({r['module'] for r in result['features']}, set(modules))
        self.assertEqual({r['module'] for r in result['features'] if r['status'] == 'INERT'}, set(modules[:1]))


class ActivityCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def cli(self, server, client=None, *options):
        path = self.root / 'server.RPT'
        path.write_text(''.join(server))
        argv = [str(path), *options]
        if client is not None:
            path = self.root / 'client.RPT'
            path.write_text(''.join(client))
            argv += ['--client-rpt', str(path)]
        output = StringIO()
        with redirect_stdout(output):
            code = audit.main(argv)
        return code, output.getvalue()

    def test_release_cli_lists_all_failed_features_and_exit_eight(self):
        module, features = 'Navigation', ['map_open', 'menu_open']
        code, output = self.cli([ready(module)] + [use(module, f, 0) for f in features], None, '--release')
        self.assertEqual(code, 8)
        for feature in features:
            self.assertIn(f'{module}/{feature} INERT count=0', output)

    def test_release_json_and_optional_client_need_no_legacy_timestamps(self):
        module, feature = 'Navigation', 'map_open'
        code, output = self.cli([ready(module), use(module, feature, 0)],
                                [use(module, feature, 1)], '--release', '--json')
        self.assertEqual(code, 0)
        result = json.loads(output)
        self.assertTrue(result['client_rpt_observed'])
        self.assertEqual(result['features'][0]['feature'], feature)
        self.assertEqual(result['features'][0]['status'], 'ACTIVE')

    def test_release_waiver_text_is_explicit(self):
        key = ('RareEvent', 'event_seen')
        with patch.dict(audit.RELEASE_WAIVERS, {key: 'rare event outside scenario'}):
            code, output = self.cli([ready(key[0]), use(*key, 0)], None, '--release')
        self.assertEqual(code, 0)
        self.assertIn('WAIVED count=0 reason=rare event outside scenario', output)
        self.assertIn('activity=waived', output)

    def test_bad_input_uses_existing_exit_six_without_echoing_path(self):
        output = StringIO()
        with redirect_stdout(output):
            code = audit.main([str(self.root / 'not-present.RPT'), '--release'])
        self.assertEqual(code, 6)
        self.assertNotIn('not-present', output.getvalue())

    def test_legacy_mode_and_exit_codes_are_preserved(self):
        module, feature = 'Synthetic', 'processed'
        expectations = self.root / 'expectations.json'
        expectations.write_text(json.dumps(dict(schema_version=1, features=[dict(
            module=module, feature=feature, floor=1, window_minutes=1,
            comparison='max', needs_player=False, scope='runtime',
            signal=dict(tag='[HC Synthetic]', regex=r'done=(?P<done>\d+)', fields=['done']))])))
        samples = [f'12:00:00 {ready(module)}', '12:02:00 [HC Synthetic] done=0\n']
        code, output = self.cli(samples, None, '--expectations', str(expectations), '--json')
        self.assertEqual(code, 8)
        self.assertFalse(json.loads(output).get('release', False))
        samples[-1] = '12:00:30 [HC Synthetic] done=1\n'
        code, output = self.cli(samples, None, '--expectations', str(expectations), '--json')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)['features'][0]['feature'], feature)


if __name__ == '__main__':
    unittest.main()
