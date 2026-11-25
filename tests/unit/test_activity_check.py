"""Activity audit behavior with synthetic RPTs; no engine behavior is inferred."""
from contextlib import redirect_stdout
from io import StringIO
import json
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.release import activity_check as audit
from tools.release import acceptance_targets as policy

TARGETS = policy.load_targets()


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

    def test_persistence_healthy_reads_and_unobserved_faults(self):
        lines = []
        for module, store in [('World', 'world'), ('Materializer', 'custody'), ('LootRefresh', 'intent')]:
            lines += [ready(module), use(module, store + '_read_ok', 1),
                      use(module, store + '_read_recovered', 0),
                      use(module, store + '_save_read_pending', 0)]
        result = self.report(lines)
        self.assertEqual(result['count'], 0)
        for row in result['features']:
            self.assertEqual(row['status'], 'ACTIVE' if row['feature'].endswith('_read_ok') else 'NOT_APPLICABLE')

    def test_persistence_observed_fault_requires_real_recovery_and_refusal(self):
        for module, store in [('World', 'world'), ('Materializer', 'custody'), ('LootRefresh', 'intent')]:
            with self.subTest(store=store):
                lines = [ready(module), use(module, store + '_read_ok', 1),
                         use(module, store + '_read_recovered', 0),
                         use(module, store + '_save_read_pending', 0),
                         f'[HC Persistence] store={store} read_unavailable\n',
                         f'[HC Persistence] store={store} save_refused reason=read_pending count=1\n']
                rows = self.report(lines)['features']
                self.assertEqual(sum(row['status'] == 'INERT' for row in rows), 2)
                lines += [use(module, store + '_read_recovered', 1), use(module, store + '_save_read_pending', 1)]
                self.assertTrue(all(row['status'] == 'ACTIVE' for row in self.report(lines)['features']))

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

    def test_change_only_checkpoints_keep_cumulative_maxima(self):
        result = self.report(['[HC UseRegistry] registered=2\n', ready('World'),
                              use('World', 'active', 1), use('World', 'active', 5),
                              use('World', 'idle', 0)])
        self.assertEqual(result['registry_count'], 2)
        rows = {row['feature']: row for row in result['features']}
        self.assertEqual(rows['active']['count'], 5)
        self.assertEqual(rows['idle']['status'], 'INERT')

    def test_registry_digest_does_not_prove_activity(self):
        result = self.report(['[HC UseRegistry] registered=1\n', ready('World')])
        self.assertEqual(result['features'][0]['status'], 'INERT')
        for digest in ('[HC Use] registered=1', '[HC UseRegistry] registered=bad'):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                self.report([digest, ready('World')])

    def test_fixture_counts_merge_as_maxima_and_remain_active(self):
        module, feature = 'Materializer', 'actors_materialized'
        samples = [(3, 1), (4, 2), (4, 2)]
        result = self.report([ready(module)] + [
            use(module, feature, count).rstrip() + f' fixture={fixture}\n'
            for count, fixture in samples], [use(module, feature, 6)])
        row, = result['features']
        self.assertEqual(row['count'], 6)
        self.assertEqual(row['fixture'], max(f for _, f in samples))
        self.assertEqual(row['status'], 'ACTIVE')
        output = StringIO()
        with redirect_stdout(output):
            audit.print_result(result)
        self.assertIn(f"ACTIVE count={row['count']} fixture={row['fixture']}", output.getvalue())

    def test_invalid_fixture_suffix_fails_closed(self):
        for suffix in (' fixture=-1', ' fixture=bad', ' fixture=2'):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                self.report([ready('Materializer'), use('Materializer', 'actors_materialized', 1).rstrip() + suffix])

    def test_every_zero_registration_fails_without_player_waiting(self):
        module = 'Navigation'
        samples = [('map_open', 0), ('pin_drawn', 2), ('menu_open', 0)]
        result = self.report([ready(module)] + [use(module, f, c) for f, c in samples])
        expected = {f for f, c in samples if c == 0}
        self.assertEqual({r['feature'] for r in result['features'] if r['status'] == 'INERT'}, expected)
        self.assertEqual(result['count'], len(expected) if TARGETS['activity_requires_active_for_default_on'] else 0)

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

    def test_waivers_are_forbidden(self):
        with patch.dict(audit.RELEASE_WAIVERS, {('RareEvent', 'meteor_seen'): 'rare'}):
            with self.assertRaisesRegex(ValueError, 'waivers forbidden'):
                self.report([ready('RareEvent'), use('RareEvent', 'meteor_seen', 0)])

    def test_owner_checks_never_establish_a_pass(self):
        for count in (0, 1):
            result = self.report([ready('TeamPing'), use('TeamPing', 'ping_delivered', count)])
            row, = result['features']
            self.assertEqual(row['status'], 'OWNER-CHECK')
            self.assertEqual(row['owner_decision_date'], '2026-11-23')
            self.assertEqual(result['count'], 0)
            self.assertIn('TeamPing/ping_delivered', result['owner_checks'])

    def test_enabled_owner_without_registration_fails(self):
        result = self.report([ready('Missing')])
        row, = result['features']
        self.assertEqual((row['module'], row['status']), ('Missing', 'INERT'))
        self.assertGreater(result['count'], 0)

    def test_disabled_and_unknown_owner_counters_do_not_establish_admission(self):
        result = self.report([ready('Off', False), use('Off', 'spawned', 0), use('Unknown', 'spawned', 1)])
        self.assertEqual(result['features'], [])

    def test_active_requirement_uses_loaded_policy(self):
        samples = [ready('World'), use('World', 'step_done', 0)]
        for required in (False, True):
            with self.subTest(required=required), patch.object(audit, 'load_targets', return_value=dict(
                    TARGETS, activity_requires_active_for_default_on=required)):
                result = self.report(samples)
                self.assertEqual(bool(result['count']), required)
                self.assertEqual(result['features'][0]['status'], 'INERT')

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


class NavAggregateTests(unittest.TestCase):
    SOURCE = Path(audit.__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/4_World/Core/HCModuleReadiness.c'
    report = UseActivityTests.report

    def c_members(self):
        """(aggregate module, feature) -> member module tokens, read from the C aggregate block."""
        text = self.SOURCE.read_text(encoding='utf-8')
        constants = dict(re.findall(r'static const string (HC_NAV_\w+) = "(\w+)";', text))
        body = text[text.index('string HCNavMembers('):text.index('int HCNavSum(')]
        found = {}
        module = None
        for line in body.splitlines():
            head = re.search(r'module == (HC_NAV_\w+)\)', line)
            if head:
                module = constants[head[1]]
            row = re.search(r'feature == "(\w+)"\) \{ return "([^"]+)"', line)
            if row and module:
                found[(module, row[1])] = {part.split('/')[0] for part in row[2].split('+')}
        return found

    def test_aggregate_table_matches_c_members(self):
        members = self.c_members()
        self.assertEqual(set(members), set(audit.NAV_AGGREGATE_OWNERS))
        for key, owners in audit.NAV_AGGREGATE_OWNERS.items():
            self.assertTrue(set(owners) <= members[key], key)

    def test_aggregate_admitted_through_owner_and_inert_at_zero(self):
        result = self.report([ready('HordeMigration'), ready('InfectedDoors'),
                              use('NavInf', 'route_advance', 4), use('NavInf', 'door_action', 0)])
        rows = {(row['module'], row['feature']): row for row in result['features']}
        self.assertEqual(rows[('NavInf', 'route_advance')]['status'], 'ACTIVE')
        self.assertEqual(rows[('NavInf', 'door_action')]['status'], 'INERT')

    def test_aggregate_ignored_without_enabled_owner(self):
        result = self.report([ready('HordeMigration', False), ready('World'),
                              use('World', 'row', 1), use('NavInf', 'route_advance', 0),
                              use('NavXai', 'routes', 9), use('NavInf', 'unknown_feature', 3)])
        self.assertEqual([row['module'] for row in result['features']], ['World'])

    def test_aggregate_does_not_register_its_owner(self):
        result = self.report([ready('InfectedReach'), use('NavInf', 'vault_started', 2)])
        rows = {(row['module'], row['feature']): row for row in result['features']}
        self.assertEqual(rows[('InfectedReach', 'unregistered')]['status'], 'INERT')

    def test_catalogue_rows_name_real_aggregates(self):
        data = json.loads(audit.DEFAULT_EXPECTATIONS.read_text(encoding='utf-8'))
        audit.load_expectations()
        rows = [row for row in data['features'] if row['feature'].startswith('nav-')]
        self.assertTrue(rows)
        for row in rows:
            match = re.search(r'module=([\w.-]+) feature=([\w.-]+) ', row['signal']['regex'])
            key = (match[1], match[2])
            if key in audit.NAV_AGGREGATE_OWNERS:
                self.assertIn(row['module'], audit.NAV_AGGREGATE_OWNERS[key])
            else:
                self.assertEqual(row['module'], match[1])
                self.assertIn(key, audit.registered_counters())


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

    def test_release_owner_check_text_is_explicit(self):
        code, output = self.cli([ready('TeamPing'), use('TeamPing', 'ping_delivered', 0)], None, '--release')
        self.assertEqual(code, 0)
        self.assertIn('OWNER-CHECK count=0', output)
        self.assertIn('owner_checks=TeamPing/ping_delivered', output)

    def test_bad_input_uses_existing_exit_six_without_echoing_path(self):
        output = StringIO()
        with redirect_stdout(output):
            code = audit.main([str(self.root / 'not-present.RPT'), '--release'])
        self.assertEqual(code, 6)
        self.assertNotIn('not-present', output.getvalue())

    def test_missing_policy_is_release_input_error(self):
        with patch.object(policy, 'DEFAULT_TARGETS', self.root / 'missing-targets.json'):
            code, output = self.cli([ready('World'), use('World', 'step_done', 1)], None, '--release')
        self.assertEqual(code, 6)
        self.assertIn('acceptance targets', output)
        self.assertNotIn('missing-targets.json', output)

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
