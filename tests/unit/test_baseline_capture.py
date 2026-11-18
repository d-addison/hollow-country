"""Single-client baseline capture: log markers, sampler CSV, benchmark row and manifest.

Every log excerpt and sampler row below is a SYNTHETIC, hand-written fixture that copies only the line
shapes of a real server run (including the unpadded millisecond field, where ".56" means 56 ms). None is a
measurement, and nothing here establishes DayZ runtime behaviour or accepts a budget.
"""
import csv
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

from tools.benchmark import compare
from tools.testing import baseline_capture as bc

ROOT = pathlib.Path(__file__).resolve().parents[2]
SAMPLER_SCRIPT = ROOT / 'tools/testing/sample-server-process.ps1'
TEMPLATE_HEADER = next(csv.reader((ROOT / 'metrics/benchmark-template.csv').open()))

RPT_HEADER = """\
=====================================================================
== C:\\synthetic\\runtime\\DayZServer_x64.exe
=====================================================================
Exe timestamp: 2026/01/02 03:04:05
Current time:  2026/03/04 21:07:38
Version 1.30.164289.70
=====================================================================

21:07:38.656 ENGINE       : PBO Load 'C:\\synthetic\\runtime\\dta\\bin'
21:07:38.656  ENGINE       : Loaded
21:07:40.91  ENGINE       : PBO Load 'C:\\synthetic\\runtime\\sakhal\\addons\\worlds_sakhal'
"""
RPT_BODY = """\
21:08:22.917  PROFILING    : Loading landscape took: 23211.770200 ms
21:08:23.347  SCRIPT       : Module: Mission; loaded 314x files; 628x classes; used 3664/33554 kB (10%) of static memory
21:08:24.56   SCRIPT       : [HollowCountry][SelfTest] Core settings PASS in native script VM
21:09:13.343  SCRIPT       : [HollowCountry] Perf sampler started, window seconds: 60
21:09:13.343  SCRIPT       : [HollowCountry] Server initialized; feature preferences default enabled; inspect each module's admission result
21:09:13.552 [CE][Hive] :: Initializing OFFLINE
"""
SCRIPT_HEADER = """\
---------------------------------------------
Log C:\\synthetic\\profiles\\script_2026-03-04_21-07-38.log started at 2026-03-04 21:07:48 (2026-03-05 02:07:48 UTC)

21:07:48.927 SCRIPT       : Module: GameLib; loaded 24x files; 29x classes
"""
SCRIPT_BODY = """\
21:08:23.347  SCRIPT       : Module: Mission; loaded 314x files; 628x classes
21:08:24.56   SCRIPT       : [HollowCountry][SelfTest] Core settings PASS in native script VM
21:09:13.343  SCRIPT       : [HollowCountry] Perf sampler started, window seconds: 60
21:09:13.343  SCRIPT       : [HollowCountry] Server initialized; feature preferences default enabled; inspect each module's admission result
"""


def perf_line(window, tick_p95, tick_p99, samples=60, players=1, clock='21:10:13.450'):
    return ('%s SCRIPT       : [HC Perf] window=%d samples=%d tick_p50=1000.00 tick_p95=%.2f tick_p99=%.2f '
            'tick_max=%.2f work_p50=0.50 work_p95=1.60 work_max=9.00 players_min=%d players_max=%d '
            'ticks_per_ms=10000.00\n' % (clock, window, samples, tick_p95, tick_p99, tick_p99 + 1, players, players))


PERF_WINDOWS = (perf_line(1, 1004.0, 26102.0, samples=35) + perf_line(2, 1000.0, 1011.0, clock='21:11:13.461')
                + perf_line(3, 1002.0, 1005.0, clock='21:12:13.461'))

SAMPLER_HEADER = 'timestamp_utc,process_alive,working_set_bytes,private_bytes,storage_bytes,storage_files,storage_last_write_utc'


def sampler_csv(rows):
    return SAMPLER_HEADER + '\n' + ''.join(row + '\n' for row in rows)


def sample_row(second, working_set=1000, private=2000, storage=0, files=3, last_write='2026-03-05T02:09:00.000Z',
               alive=1):
    stamp = '2026-03-05T02:10:%02d.250Z' % second
    return '%s,%d,%s,%s,%s,%s,%s' % (stamp, alive, working_set if alive else '', private if alive else '',
                                    storage, files, last_write)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = pathlib.Path(self.temp.name)

    def write(self, name, text):
        path = self.dir / name
        path.write_text(text, encoding='utf-8')
        return path

    def logs(self, rpt_body=RPT_BODY, script_body=SCRIPT_BODY + PERF_WINDOWS, rpt_header=RPT_HEADER):
        return (self.write('server.RPT', rpt_header + rpt_body),
                self.write('script.log', SCRIPT_HEADER + script_body))

    def capture(self, **overrides):
        rpt, script = self.logs()
        sampler = self.write('s.csv', sampler_csv([
            sample_row(0, working_set=3 * 1024 * 1024, storage=0),
            sample_row(30, working_set=5 * 1024 * 1024, storage=3000)]))
        args = dict(rpt=rpt, script_log=script, sampler_csv=sampler, label='cold', git_commit='abc1234',
                    run_id=None, scenario=None, seed=0, player_count=1, measured={}, skip_windows=0,
                    hardware=None, mission=None, warmup_seconds=None, sample_seconds=None)
        args.update(overrides)
        return bc.build_capture(**args)


class TimestampTests(unittest.TestCase):
    def test_milliseconds_are_an_integer_not_a_fraction(self):
        base = ((21 * 60 + 8) * 60 + 24) * 1000
        self.assertEqual(bc.parse_time_ms('21:08:24.56'), base + 56)
        self.assertEqual(bc.parse_time_ms('21:08:24.143'), base + 143)
        self.assertEqual(bc.parse_time_ms('21:08:24.5'), base + 5)

    def test_not_a_timestamp(self):
        self.assertIsNone(bc.parse_time_ms('=== Current time:'))
        self.assertIsNone(bc.parse_time_ms('Version 1.30'))


class StartupTests(Fixture):
    def test_startup_seconds_from_rpt_start_to_hc_ready(self):
        rpt, script = self.logs()
        startup = bc.read_startup(rpt, script)
        self.assertAlmostEqual(startup['startup_seconds'], 95.343, places=3)
        self.assertEqual(startup['server_start'], '2026-03-04T21:07:38')
        self.assertEqual(startup['hc_ready_marker'], '[HollowCountry] Server initialized;')
        self.assertEqual(startup['game_build'], '1.30.164289.70')

    def test_other_phases_are_reported_from_observed_lines(self):
        rpt, script = self.logs()
        startup = bc.read_startup(rpt, script)
        self.assertAlmostEqual(startup['phases']['mission_module_loaded_seconds'], 45.347, places=3)
        self.assertAlmostEqual(startup['phases']['ce_hive_initializing_seconds'], 95.552, places=3)
        self.assertAlmostEqual(startup['loading_landscape_ms'], 23211.7702, places=3)

    def test_rpt_ready_marker_is_used_when_script_log_lacks_it(self):
        rpt, script = self.logs(script_body=PERF_WINDOWS)
        startup = bc.read_startup(rpt, script)
        self.assertAlmostEqual(startup['startup_seconds'], 95.343, places=3)
        self.assertEqual(startup['ready_source'], 'rpt')

    def test_script_log_wins_when_both_have_the_marker(self):
        rpt, script = self.logs()
        self.assertEqual(bc.read_startup(rpt, script)['ready_source'], 'script_log')

    def test_midnight_rollover(self):
        header = RPT_HEADER.split('Current time:')[0] + 'Current time:  2026/03/04 23:59:50\nVersion 1.30.164289.70\n'
        body = ("23:59:55.000 ENGINE       : Loaded\n"
                "00:00:10.500  SCRIPT       : [HollowCountry] Server initialized; feature preferences default enabled\n")
        rpt, script = self.logs(rpt_body=body, script_body=PERF_WINDOWS, rpt_header=header)
        self.assertAlmostEqual(bc.read_startup(rpt, script)['startup_seconds'], 20.5, places=3)

    def test_first_ready_marker_wins(self):
        body = RPT_BODY + "21:20:00.000  SCRIPT       : [HollowCountry] Server initialized; again\n"
        rpt, script = self.logs(rpt_body=body)
        self.assertAlmostEqual(bc.read_startup(rpt, script)['startup_seconds'], 95.343, places=3)

    def test_decoy_lines_do_not_count_as_ready(self):
        body = ("21:08:00.000  SCRIPT       : [HC Events] Server initialized; not the module marker\n"
                "21:08:01.000  SCRIPT       : [HollowCountry] Requested module start; Server initialized\n")
        rpt, script = self.logs(rpt_body=body, script_body=PERF_WINDOWS)
        with self.assertRaises(bc.BaselineError) as caught:
            bc.read_startup(rpt, script)
        self.assertIn('ready marker', str(caught.exception))

    def test_missing_start_header_is_an_error(self):
        rpt, script = self.logs(rpt_header='21:07:38.656 ENGINE       : Loaded\n')
        with self.assertRaises(bc.BaselineError) as caught:
            bc.read_startup(rpt, script)
        self.assertIn('Current time', str(caught.exception))

    def test_implausibly_long_startup_is_an_error(self):
        # 20:00 is before the 21:07:38 start, so the clock can only have wrapped past midnight: 22 h 52 min.
        body = "20:00:00.000  SCRIPT       : [HollowCountry] Server initialized; early\n"
        rpt, script = self.logs(rpt_body=body, script_body=PERF_WINDOWS)
        with self.assertRaises(bc.BaselineError) as caught:
            bc.read_startup(rpt, script)
        self.assertIn('implausible', str(caught.exception))


class SamplerTests(Fixture):
    def test_header_matches_the_powershell_sampler(self):
        script = SAMPLER_SCRIPT.read_text(encoding='utf-8')
        self.assertIn(SAMPLER_HEADER, script)
        self.assertEqual(','.join(bc.SAMPLER_COLUMNS), SAMPLER_HEADER)

    def test_peak_memory_and_exact_linear_slope(self):
        rows = [sample_row(0, working_set=900, private=2500, storage=1000),
                sample_row(10, working_set=1500, private=2400, storage=2000),
                sample_row(20, working_set=1200, private=2600, storage=3000),
                sample_row(30, working_set=1100, private=2300, storage=4000)]
        summary = bc.read_sampler(self.write('s.csv', sampler_csv(rows)))
        self.assertEqual(summary['peak_working_set_bytes'], 1500)
        self.assertEqual(summary['peak_private_bytes'], 2600)
        # 1000 bytes per 10 s is 6000 bytes per minute.
        self.assertAlmostEqual(summary['storage_write_slope_bytes_per_min'], 6000.0, places=6)
        self.assertEqual(summary['samples'], 4)
        self.assertAlmostEqual(summary['span_seconds'], 30.0, places=6)

    def test_slope_is_a_least_squares_fit_not_endpoints(self):
        # Sizes 0, 60, 60, 60 at 0..3 minutes: the least-squares slope is 18 bytes/min; first-to-last
        # endpoints would give 20 and last-step differences 0, so only a fit passes.
        rows = ['2026-03-05T02:10:00.000Z,1,1,1,0,1,',
                '2026-03-05T02:11:00.000Z,1,1,1,60,1,',
                '2026-03-05T02:12:00.000Z,1,1,1,60,1,',
                '2026-03-05T02:13:00.000Z,1,1,1,60,1,']
        summary = bc.read_sampler(self.write('s.csv', sampler_csv(rows)))
        self.assertAlmostEqual(summary['storage_write_slope_bytes_per_min'], 18.0, places=6)

    def test_flat_storage_has_zero_slope(self):
        rows = [sample_row(0, storage=500), sample_row(10, storage=500), sample_row(20, storage=500)]
        summary = bc.read_sampler(self.write('s.csv', sampler_csv(rows)))
        self.assertEqual(summary['storage_write_slope_bytes_per_min'], 0.0)

    def test_single_sample_gives_no_slope(self):
        summary = bc.read_sampler(self.write('s.csv', sampler_csv([sample_row(0)])))
        self.assertIsNone(summary['storage_write_slope_bytes_per_min'])
        self.assertEqual(summary['peak_working_set_bytes'], 1000)

    def test_write_events_count_last_write_changes(self):
        rows = [sample_row(0, last_write='2026-03-05T02:09:00.000Z'),
                sample_row(10, last_write='2026-03-05T02:09:00.000Z'),
                sample_row(20, last_write='2026-03-05T02:10:15.000Z'),
                sample_row(30, last_write='2026-03-05T02:10:25.000Z')]
        summary = bc.read_sampler(self.write('s.csv', sampler_csv(rows)))
        self.assertEqual(summary['storage_write_events'], 2)

    def test_dead_process_rows_do_not_feed_the_peak(self):
        rows = [sample_row(0, working_set=1000), sample_row(10, working_set=9999, alive=0)]
        summary = bc.read_sampler(self.write('s.csv', sampler_csv(rows)))
        self.assertEqual(summary['peak_working_set_bytes'], 1000)
        self.assertEqual(summary['samples_without_process'], 1)

    def test_no_live_sample_is_an_error(self):
        with self.assertRaises(bc.BaselineError):
            bc.read_sampler(self.write('s.csv', sampler_csv([sample_row(0, alive=0)])))

    def test_wrong_header_is_an_error(self):
        with self.assertRaises(bc.BaselineError) as caught:
            bc.read_sampler(self.write('s.csv', 'a,b\n1,2\n'))
        self.assertIn('header', str(caught.exception))

    def test_non_increasing_timestamps_are_an_error(self):
        rows = [sample_row(10), sample_row(10)]
        with self.assertRaises(bc.BaselineError):
            bc.read_sampler(self.write('s.csv', sampler_csv(rows)))

    def test_bad_numbers_are_errors(self):
        for bad in ('x', '-5', '1.5'):
            with self.subTest(bad=bad):
                rows = [sample_row(0, working_set=bad)]
                with self.assertRaises(bc.BaselineError):
                    bc.read_sampler(self.write('s.csv', sampler_csv(rows)))

    def test_utf8_bom_is_tolerated(self):
        path = self.dir / 'bom.csv'
        path.write_bytes(b'\xef\xbb\xbf' + sampler_csv([sample_row(0)]).encode())
        self.assertEqual(bc.read_sampler(path)['samples'], 1)

    def test_seven_digit_fractional_seconds_parse(self):
        rows = ['2026-03-05T02:10:00.1234567Z,1,5,6,100,1,2026-03-05T02:09:00.0000000Z',
                '2026-03-05T02:11:00.1234567Z,1,5,6,160,1,2026-03-05T02:09:00.0000000Z']
        summary = bc.read_sampler(self.write('s.csv', sampler_csv(rows)))
        self.assertAlmostEqual(summary['storage_write_slope_bytes_per_min'], 60.0, places=6)


class PerfWindowTests(Fixture):
    def test_tick_percentiles_use_worst_window_as_upper_bound(self):
        _, script = self.logs()
        perf = bc.read_perf(script)
        self.assertEqual(perf['windows'], 3)
        self.assertEqual(perf['tick_p95_ms_worst_window'], 1004.0)
        self.assertEqual(perf['tick_p99_ms_worst_window'], 26102.0)
        self.assertEqual(perf['players_max_seen'], 1)

    def test_skip_windows_drops_the_leading_windows(self):
        _, script = self.logs()
        perf = bc.read_perf(script, skip_windows=1)
        self.assertEqual(perf['windows'], 2)
        self.assertEqual(perf['tick_p99_ms_worst_window'], 1011.0)

    def test_no_windows_is_an_error(self):
        _, script = self.logs(script_body=SCRIPT_BODY)
        with self.assertRaises(bc.BaselineError):
            bc.read_perf(script)

    def test_malformed_window_is_counted(self):
        bad = '21:10:13.450 SCRIPT       : [HC Perf] window=1 samples=oops\n'
        _, script = self.logs(script_body=SCRIPT_BODY + PERF_WINDOWS + bad)
        self.assertEqual(bc.read_perf(script)['malformed_lines'], 1)


class RowTests(Fixture):
    def test_row_has_exactly_the_template_columns_in_order(self):
        self.assertEqual(list(bc.ROW_FIELDS), TEMPLATE_HEADER)
        self.assertEqual(list(self.capture()['row']), TEMPLATE_HEADER)

    def test_row_values(self):
        row = self.capture()['row']
        self.assertEqual(row['scenario'], 'single-client-baseline-cold')
        self.assertEqual(row['run_id'], 'single-client-baseline-cold-20260304T210738')
        self.assertEqual(row['game_build'], '1.30.164289.70')
        self.assertEqual(row['git_commit'], 'abc1234')
        self.assertEqual(row['player_count'], 1)
        self.assertEqual(row['peak_ram_mb'], 5.0)
        self.assertEqual(row['errors'], 0)

    def test_hc_tick_intervals_never_fill_the_engine_frame_time_columns(self):
        # Review P1: the HC module timer interval is not an engine frame time; compare.py must not read it as one.
        capture = self.capture()
        row = capture['row']
        self.assertEqual(row['p95_server_frame_ms'], '')
        self.assertEqual(row['p99_server_frame_ms'], '')
        self.assertIn('p95_server_frame_ms', capture['unmeasured'])
        self.assertIn('p99_server_frame_ms', capture['unmeasured'])
        self.assertIn('hc_tick_p95_ms_worst_window=1004.0', row['notes'])
        self.assertIn('hc_tick_p99_ms_worst_window=26102.0', row['notes'])
        self.assertEqual(capture['entry']['perf']['tick_p95_ms_worst_window'], 1004.0)
        self.assertNotIn('p95_server_frame_ms', capture['entry']['units'])

    def test_unmeasured_fields_are_declared_not_invented(self):
        capture = self.capture()
        self.assertIn('client_1pct_low_fps', capture['unmeasured'])
        self.assertIn('avg_server_fps', capture['unmeasured'])
        self.assertIn('unmeasured=', capture['row']['notes'])
        self.assertIn('provisional', capture['row']['notes'])
        self.assertEqual(capture['row']['client_1pct_low_fps'], '')
        self.assertEqual(capture['row']['active_infected'], '')

    def test_unmeasured_row_is_rejected_loudly_by_compare(self):
        path = self.dir / 'row.csv'
        bc.write_outputs(path, self.capture())
        with self.assertRaises(compare.EvidenceError):
            compare._read_csv(path)

    def test_fully_supplied_row_is_accepted_by_compare(self):
        measured = {name: 7 for name in bc.OPERATOR_FIELDS}
        capture = self.capture(measured=measured)
        self.assertEqual(capture['unmeasured'], [])
        path = self.dir / 'row.csv'
        bc.write_outputs(path, capture)
        rows = compare._read_csv(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['peak_ram_mb'], 5.0)

    def test_label_must_be_warm_or_cold(self):
        with self.assertRaises(bc.BaselineError):
            self.capture(label='lukewarm')

    def test_p95_above_p99_never_reaches_a_row(self):
        # compare.py rejects such a row; the capture must not manufacture one.
        measured = {name: 7 for name in bc.OPERATOR_FIELDS}
        measured['p95_server_frame_ms'] = 9
        with self.assertRaises(bc.BaselineError):
            self.capture(measured=measured)

    def test_output_inside_shipped_source_trees_is_refused_before_writing(self):
        repo = pathlib.Path(bc.__file__).resolve().parents[2]
        for tree in ('mods', 'mission', 'config'):
            target = repo / tree / 'baseline-review-probe.csv'
            with self.subTest(tree=tree):
                with self.assertRaises(bc.BaselineError):
                    bc.write_outputs(target, self.capture())
                self.assertFalse(target.exists())

    def test_summary_names_only_the_output_file(self):
        out = self.dir / 'nested' / 'baseline.csv'
        text = bc.render_text(self.capture(), out)
        self.assertIn('wrote: baseline.csv and baseline.csv.manifest.json', text)
        self.assertNotIn(str(self.dir), text)


class ManifestTests(Fixture):
    def make(self, **overrides):
        return self.capture(**overrides)

    def setUp(self):
        super().setUp()
        self.out = self.dir / 'baseline.csv'

    def test_manifest_is_readable_by_compare_with_known_context_only(self):
        capture = self.make(hardware='synthetic-host', mission='synthetic-mission', warmup_seconds=60,
                            sample_seconds=300, measured={name: 7 for name in bc.OPERATOR_FIELDS})
        bc.write_outputs(self.out, capture)
        rows = compare._read_csv(self.out)
        reasons = []
        contexts, _ = compare._read_manifest(self.out, None, rows, reasons)
        run_id = rows[0]['run_id']
        self.assertEqual(contexts[run_id]['hardware'], 'synthetic-host')
        self.assertEqual(contexts[run_id]['sample_seconds'], 300)
        self.assertEqual(reasons, [])

    def test_manifest_records_inputs_with_sha256_and_basenames_only(self):
        capture = self.make(label='warm')
        bc.write_outputs(self.out, capture)
        manifest = json.loads(pathlib.Path(str(self.out) + '.manifest.json').read_text())
        entry = manifest['captures'][capture['row']['run_id']]
        self.assertEqual(entry['label'], 'warm')
        roles = {item['role']: item for item in entry['inputs']}
        self.assertEqual(set(roles), {'server_rpt', 'script_log', 'sampler_csv'})
        rpt_bytes = (self.dir / 'server.RPT').read_bytes()
        self.assertEqual(roles['server_rpt']['sha256'], hashlib.sha256(rpt_bytes).hexdigest())
        self.assertEqual(roles['server_rpt']['name'], 'server.RPT')
        self.assertEqual(roles['server_rpt']['bytes'], len(rpt_bytes))
        self.assertIn('python', entry['tool_versions'])
        self.assertIn('baseline_capture_sha256', entry['tool_versions'])

    def test_manifest_marks_budgets_provisional_with_no_verdict(self):
        capture = self.make()
        bc.write_outputs(self.out, capture)
        manifest = json.loads(pathlib.Path(str(self.out) + '.manifest.json').read_text())
        entry = manifest['captures'][capture['row']['run_id']]
        self.assertEqual(entry['budgets'], {'status': 'provisional', 'verdict': 'unassessed'})
        self.assertEqual(entry['runtime_acceptance'], 'pending')
        self.assertEqual(entry['startup']['startup_seconds'], 95.343)

    def test_outputs_leak_no_home_or_steam_identifiers(self):
        capture = self.make()
        bc.write_outputs(self.out, capture)
        text = self.out.read_text() + pathlib.Path(str(self.out) + '.manifest.json').read_text()
        for forbidden in ('/home/', 'C:\\\\', 'C:\\', '/mnt/', 'steamapps', '7656119'):
            self.assertNotIn(forbidden, text)

    def test_appending_a_second_run_merges_row_and_manifest(self):
        bc.write_outputs(self.out, self.make(label='cold'))
        bc.write_outputs(self.out, self.make(label='warm'))
        with self.out.open(newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([r['scenario'] for r in rows],
                         ['single-client-baseline-cold', 'single-client-baseline-warm'])
        manifest = json.loads(pathlib.Path(str(self.out) + '.manifest.json').read_text())
        self.assertEqual(len(manifest['captures']), 2)
        self.assertEqual(len(manifest['runs']), 2)

    def test_duplicate_run_id_is_rejected(self):
        bc.write_outputs(self.out, self.make(label='cold'))
        with self.assertRaises(bc.BaselineError):
            bc.write_outputs(self.out, self.make(label='cold'))

    def test_mixed_git_commit_is_rejected_because_compare_needs_one_revision(self):
        bc.write_outputs(self.out, self.make(label='cold'))
        with self.assertRaises(bc.BaselineError):
            bc.write_outputs(self.out, self.make(label='warm', git_commit='def5678'))


class CliTests(Fixture):
    def run_cli(self, *extra):
        rpt, script = self.logs()
        sampler = self.write('s.csv', sampler_csv([
            sample_row(0, working_set=4096, storage=0), sample_row(30, working_set=8192, storage=3000)]))
        out = self.dir / 'out.csv'
        command = [sys.executable, '-I', str(ROOT / 'tools/testing/baseline_capture.py'),
                   '--rpt', str(rpt), '--script-log', str(script), '--sampler-csv', str(sampler),
                   '--label', 'warm', '--git-commit', 'abc1234', '--out-csv', str(out), *extra]
        done = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
        return done, out

    def test_cli_writes_row_and_manifest_and_prints_provisional_summary(self):
        done, out = self.run_cli()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(out.exists())
        self.assertTrue(pathlib.Path(str(out) + '.manifest.json').exists())
        self.assertIn('provisional', done.stdout)
        self.assertIn('startup_seconds', done.stdout)
        self.assertNotIn('within_provisional_budget', done.stdout)
        self.assertRegex(done.stdout, r'unmeasured:.*client_1pct_low_fps')

    def test_cli_accepts_operator_measured_values(self):
        done, out = self.run_cli('--client-1pct-low-fps', '31.5', '--client-avg-fps', '60',
                                 '--avg-server-fps', '40', '--p01-server-fps', '20')
        self.assertEqual(done.returncode, 0, done.stderr)
        with out.open(newline='') as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(float(row['client_1pct_low_fps']), 31.5)
        self.assertNotIn('client_1pct_low_fps', row['notes'])

    def test_cli_rejects_a_negative_operator_value(self):
        done, _ = self.run_cli('--network-kbps', '-1')
        self.assertNotEqual(done.returncode, 0)

    def test_cli_missing_ready_marker_exits_nonzero_and_writes_nothing(self):
        rpt, script = self.logs(rpt_body='', script_body=PERF_WINDOWS)
        sampler = self.write('s.csv', sampler_csv([sample_row(0)]))
        out = self.dir / 'none.csv'
        done = subprocess.run([sys.executable, '-I', str(ROOT / 'tools/testing/baseline_capture.py'),
                               '--rpt', str(rpt), '--script-log', str(script), '--sampler-csv', str(sampler),
                               '--label', 'cold', '--git-commit', 'abc1234', '--out-csv', str(out)],
                              capture_output=True, text=True, cwd=ROOT)
        self.assertNotEqual(done.returncode, 0)
        self.assertFalse(out.exists())
        self.assertIn('ready marker', done.stderr)


class PowerShellSamplerTests(unittest.TestCase):
    def setUp(self):
        self.text = SAMPLER_SCRIPT.read_text(encoding='utf-8')
        self.code = '\n'.join(line for line in self.text.splitlines() if not line.lstrip().startswith('#'))

    def test_targets_windows_powershell_5_1_without_policy_changes(self):
        self.assertTrue(self.text.startswith('#requires -Version 5.1'))
        self.assertNotRegex(self.text, r'(?i)executionpolicy')
        self.assertNotIn('?.', self.code)
        self.assertNotRegex(self.code, r'\?\?')

    def test_samples_the_documented_process_and_storage_properties(self):
        for token in ('WorkingSet64', 'PrivateMemorySize64', 'LastWriteTimeUtc', 'Get-Process',
                      'Get-ChildItem', 'IntervalSeconds', 'Samples', 'StoragePath', 'OutputCsv'):
            self.assertIn(token, self.code)

    def test_is_read_only_toward_the_server_and_storage(self):
        for verb in ('Stop-Process', 'Kill(', 'Remove-Item', 'Set-ExecutionPolicy', 'Invoke-Expression',
                     'Start-Process', 'Move-Item', 'Rename-Item', 'New-Item', 'Copy-Item', 'Clear-Content',
                     'Invoke-WebRequest', 'Invoke-RestMethod', 'Add-Type'):
            self.assertNotIn(verb, self.code)

    def test_refuses_to_overwrite_and_does_not_record_paths(self):
        self.assertIn('Test-Path', self.code)
        header_line = next(line for line in self.code.splitlines() if 'timestamp_utc' in line)
        self.assertNotRegex(header_line, r'(?i)path|dir')

    def test_timestamps_are_fixed_width_utc(self):
        self.assertRegex(self.code, re.escape("yyyy-MM-ddTHH:mm:ss.fff'Z'"))


if __name__ == '__main__':
    unittest.main()
