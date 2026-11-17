"""Performance capture: parser/report behaviour on SYNTHETIC lines plus static checks of HCPerfSampler.c.

Every RPT line below is a SYNTHETIC fixture written for this test. None is a measurement of a real server,
and nothing here establishes DayZ runtime behaviour or accepts a budget.
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

from tools.testing import perf_capture as pc

ROOT = pathlib.Path(__file__).resolve().parents[2]
SAMPLER = ROOT / 'mods/HollowCountry/scripts/4_World/Core/HCPerfSampler.c'


def line(window=1, samples=60, players=4, tick_p50=1000.0, tick_p95=1004.0, tick_p99=1010.0, tick_max=1020.0,
         work_p50=0.5, work_p95=2.0, work_max=8.0, ticks_per_ms=1000.0, calibration_invalid=False,
         prefix='12:00:00.000 ', players_max=None):
    # players_max=None writes the old single `players=` form; otherwise `players` is the window minimum.
    if players_max is None:
        players_text = 'players=%d' % players
    else:
        players_text = 'players_min=%d players_max=%d' % (players, players_max)
    head = '%s[HC Perf] window=%d samples=%d tick_p50=%s tick_p95=%s tick_p99=%s tick_max=%s' % (
        prefix, window, samples, tick_p50, tick_p95, tick_p99, tick_max)
    if calibration_invalid:
        return head + ' %s calibration=invalid' % players_text
    return head + ' work_p50=%s work_p95=%s work_max=%s %s ticks_per_ms=%s' % (
        work_p50, work_p95, work_max, players_text, ticks_per_ms)


# Exact lines captured from a real server RPT. The Print(report) form wrapped them in a variable declaration;
# the second one also lost its closing quote.
REAL_WINDOW_2 = ("12:42:50.951 SCRIPT       : string report = '[HC Perf] window=2 samples=60 tick_p50=1000.00 "
                 "tick_p95=1000.00 tick_p99=1005.00 tick_max=1005.00 work_p50=0.31 work_p95=12.54 work_max=17.89 "
                 "players=0 ticks_per_ms=9999.97'")
REAL_WINDOW_1 = ("12:41:50.945 SCRIPT       : string report = '[HC Perf] window=1 samples=22 tick_p50=1000.00 "
                 "tick_p95=1320.00 tick_p99=39645.00 tick_max=39645.00 work_p50=0.31 work_p95=11.78 "
                 "work_max=289.00 players=0 ticks_per_ms=9999.94")


def write(directory, name, lines):
    path = pathlib.Path(directory) / name
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


class ParseLine(unittest.TestCase):
    def test_parses_a_timestamped_rpt_line(self):
        record = pc.parse_line(line(window=3, players=5, work_p95=1.25))
        self.assertEqual(3, record['window'])
        self.assertEqual(5, record['players'])
        self.assertEqual(1.25, record['work_p95'])
        self.assertEqual(60, record['samples'])

    def test_calibration_invalid_line_parses_without_work_values(self):
        record = pc.parse_line(line(window=2, players=4, calibration_invalid=True))
        self.assertFalse(record['calibration_valid'])
        self.assertNotIn('work_max', record)
        self.assertEqual(1004.0, record['tick_p95'])

    def test_calibrated_line_carries_ticks_per_ms(self):
        record = pc.parse_line(line(ticks_per_ms=9999.5))
        self.assertTrue(record['calibration_valid'])
        self.assertEqual(9999.5, record['ticks_per_ms'])

    def test_real_rpt_lines_with_the_string_report_wrapper_parse(self):
        two = pc.parse_line(REAL_WINDOW_2)
        self.assertEqual(2, two['window'])
        self.assertEqual(60, two['samples'])
        self.assertEqual(17.89, two['work_max'])
        self.assertEqual(9999.97, two['ticks_per_ms'])
        self.assertEqual((0, 0), (two['players_min'], two['players_max']))
        one = pc.parse_line(REAL_WINDOW_1)
        self.assertEqual(1, one['window'])
        self.assertEqual(39645.0, one['tick_max'])
        self.assertEqual(9999.94, one['ticks_per_ms'])

    def test_plain_line_and_wrapper_without_quote_agree(self):
        plain = '[HC Perf]' + REAL_WINDOW_2.split('[HC Perf]')[1].rstrip("'")
        self.assertEqual(pc.parse_line(REAL_WINDOW_2), pc.parse_line(plain))
        self.assertEqual(pc.parse_line(REAL_WINDOW_2), pc.parse_line(REAL_WINDOW_2.rstrip("'")))

    def test_stray_quote_on_a_plain_line_is_malformed(self):
        with self.assertRaises(ValueError):
            pc.parse_line(line() + "'")

    def test_players_min_max_form_parses_and_old_form_means_min_equals_max(self):
        record = pc.parse_line(line(players=2, players_max=5))
        self.assertEqual((2, 5), (record['players_min'], record['players_max']))
        self.assertNotIn('players', record)
        old = pc.parse_line(line(players=4))
        self.assertEqual((4, 4), (old['players_min'], old['players_max']))
        self.assertEqual(4, old['players'])
        invalid = pc.parse_line(line(players=3, players_max=3, calibration_invalid=True))
        self.assertEqual((3, 3), (invalid['players_min'], invalid['players_max']))

    def test_impossible_records_are_malformed(self):
        bad = [
            line(samples=0),
            line(window=0),
            line(tick_p50=1010.0, tick_p95=1004.0),
            line(tick_p95=1011.0, tick_p99=1010.0),
            line(tick_p99=1021.0, tick_max=1020.0),
            line(work_p50=3.0, work_p95=2.0),
            line(work_p95=9.0, work_max=8.0),
            line(players=5, players_max=2),
            line().replace('players=4', 'players_min=4'),
            line().replace('players=4', 'players_max=4'),
            line().replace('players=4', 'players=4 players_min=4 players_max=4'),
            line(players=4, players_max=5).replace('players_min=4', 'players_min=-1'),
            line(samples=0, calibration_invalid=True),
            line(tick_p50=1010.0, tick_p95=1004.0, calibration_invalid=True),
        ]
        for text in bad:
            with self.assertRaises(ValueError, msg=text):
                pc.parse_line(text)

    def test_equal_percentiles_are_possible_and_valid(self):
        record = pc.parse_line(line(tick_p50=1000.0, tick_p95=1000.0, tick_p99=1000.0, tick_max=1000.0,
                                    work_p50=0.0, work_p95=0.0, work_max=0.0, samples=1))
        self.assertEqual(1, record['samples'])

    def test_non_perf_lines_are_ignored_not_malformed(self):
        self.assertIsNone(pc.parse_line('12:00:00.000 [HollowCountry] Server initialized'))

    def test_malformed_perf_lines_raise_value_error(self):
        bad = [
            '[HC Perf] window=1 samples=3',
            line().replace('players=4', 'players=four'),
            line().replace('work_max=8.0', 'work_max=nan'),
            line().replace('work_max=8.0', 'work_max=-1.0'),
            line().replace('work_max=8.0', 'work_max=inf'),
            line() + ' players=5',
            line().replace(' ticks_per_ms=1000.0', ''),
            line().replace('ticks_per_ms=1000.0', 'ticks_per_ms=0'),
            line().replace('ticks_per_ms=1000.0', 'ticks_per_ms=nan'),
            line().replace('ticks_per_ms=1000.0', 'ticks_per_ms=-3.0'),
            line() + ' calibration=invalid',
            line(calibration_invalid=True) + ' work_max=1.0',
            line(calibration_invalid=True).replace('calibration=invalid', 'calibration=ok'),
        ]
        for text in bad:
            with self.assertRaises(ValueError, msg=text):
                pc.parse_line(text)


class Report(unittest.TestCase):
    def build(self, lines_by_file, budgets=None):
        with tempfile.TemporaryDirectory() as directory:
            paths = [write(directory, name, lines) for name, lines in lines_by_file.items()]
            return pc.build_report(paths, budgets or dict(pc.DEFAULT_BUDGETS))

    def test_report_always_says_runtime_acceptance_pending_and_budgets_provisional(self):
        report = self.build({'a.rpt': [line()]})
        self.assertEqual('pending', report['runtime_acceptance'])
        self.assertTrue(report['budgets_provisional'])
        self.assertIn('PROVISIONAL', pc.render_text(report))
        self.assertIn('runtime_acceptance: pending', pc.render_text(report))

    def test_default_budgets_are_the_documented_provisional_values(self):
        self.assertEqual(5.0, pc.DEFAULT_BUDGETS['work_p95_ms'])
        self.assertEqual(20.0, pc.DEFAULT_BUDGETS['work_max_ms'])

    def test_within_target_load_and_budget_is_only_within_provisional_budget(self):
        report = self.build({'a.rpt': [line(players=3), line(window=2, players=6)]})
        self.assertEqual('within_provisional_budget', report['verdict'])
        self.assertNotIn('accepted', json.dumps(report).replace('runtime_acceptance', ''))

    def test_over_budget_at_target_load_fails(self):
        report = self.build({'a.rpt': [line(players=4, work_p95=6.5)]})
        self.assertEqual('over_budget', report['verdict'])
        group = report['by_players']['4']
        self.assertEqual('over_budget', group['verdict'])
        self.assertIn('work_p95_ms', group['violations'])
        report = self.build({'a.rpt': [line(players=4, work_max=21.0)]})
        self.assertIn('work_max_ms', report['by_players']['4']['violations'])

    def test_fewer_than_three_players_is_insufficient_load_even_when_fast(self):
        for players in (0, 1, 2):
            report = self.build({'a.rpt': [line(players=players, work_p50=0.05, work_p95=0.1, work_max=0.2)]})
            self.assertEqual('insufficient_load', report['verdict'])
            self.assertEqual('insufficient_load', report['by_players'][str(players)]['verdict'])

    def test_insufficient_load_never_masks_a_target_load_violation(self):
        report = self.build({'a.rpt': [line(players=1), line(window=2, players=5, work_max=40.0)]})
        self.assertEqual('over_budget', report['verdict'])

    def test_above_target_load_is_reported_but_not_counted_as_acceptance_evidence(self):
        report = self.build({'a.rpt': [line(players=9)]})
        self.assertEqual('above_target_load', report['by_players']['9']['verdict'])
        self.assertEqual('insufficient_load', report['verdict'])

    def test_calibration_invalid_windows_are_separate_and_never_within_budget(self):
        report = self.build({'a.rpt': [line(players=4, calibration_invalid=True)]})
        self.assertEqual('calibration_invalid', report['verdict'])
        self.assertEqual('calibration_invalid', report['by_players']['4']['verdict'])
        self.assertEqual(1, report['calibration_invalid_windows'])
        self.assertEqual(1, report['by_players']['4']['calibration_invalid_windows'])
        self.assertEqual(1, report['runs'][0]['calibration_invalid_windows'])
        self.assertIsNone(report['by_players']['4']['worst']['work_max'])
        self.assertIn('calibration_invalid', pc.render_text(report))

    def test_one_invalid_window_prevents_within_budget_but_not_over_budget(self):
        mixed = self.build({'a.rpt': [line(players=4), line(window=2, players=4, calibration_invalid=True)]})
        self.assertEqual('calibration_invalid', mixed['verdict'])
        self.assertEqual(1, mixed['by_players']['4']['windows'] - mixed['by_players']['4']['calibration_invalid_windows'])
        over = self.build({'a.rpt': [line(players=4, work_max=50.0),
                                     line(window=2, players=4, calibration_invalid=True)]})
        self.assertEqual('over_budget', over['verdict'])

    def test_invalid_calibration_below_target_load_stays_insufficient_load(self):
        report = self.build({'a.rpt': [line(players=2, calibration_invalid=True)]})
        self.assertEqual('insufficient_load', report['verdict'])
        self.assertEqual(1, report['by_players']['2']['calibration_invalid_windows'])

    def test_valid_windows_report_the_observed_ticks_per_ms_range(self):
        report = self.build({'a.rpt': [line(ticks_per_ms=900.0), line(window=2, ticks_per_ms=1100.0),
                                       line(window=3, calibration_invalid=True)]})
        self.assertEqual({'min': 900.0, 'max': 1100.0}, report['runs'][0]['ticks_per_ms'])

    def test_groups_by_player_count_and_keeps_worst_values(self):
        report = self.build({'a.rpt': [
            line(window=1, players=3, work_p95=1.0, work_max=4.0, tick_p99=1010.0),
            line(window=2, players=3, work_p95=3.0, work_max=9.0, tick_p99=1100.0, tick_max=1200.0),
            line(window=3, players=5, work_p95=2.0, work_max=5.0),
        ]})
        three = report['by_players']['3']
        self.assertEqual(2, three['windows'])
        self.assertEqual(3.0, three['worst']['work_p95'])
        self.assertEqual(9.0, three['worst']['work_max'])
        self.assertEqual(1100.0, three['worst']['tick_p99'])
        self.assertEqual(9.0, report['overall']['worst']['work_max'])
        self.assertEqual(3, report['overall']['windows'])

    def test_multiple_runs_are_summarised_separately_and_overall(self):
        report = self.build({
            'one.rpt': [line(players=4, work_max=3.0)],
            'two.rpt': [line(players=4, work_max=12.0), line(window=2, players=4, work_max=2.0)],
        })
        self.assertEqual(2, len(report['runs']))
        by_name = {r['file']: r for r in report['runs']}
        self.assertEqual(1, by_name['one.rpt']['windows'])
        self.assertEqual(12.0, by_name['two.rpt']['worst']['work_max'])
        self.assertEqual(12.0, report['overall']['worst']['work_max'])

    def test_malformed_lines_are_counted_and_reported_not_fatal(self):
        report = self.build({'a.rpt': [line(), '[HC Perf] window=2 garbage',
                                       line(window=3).replace('samples=60', 'samples=x')]})
        run = report['runs'][0]
        self.assertEqual(1, run['windows'])
        self.assertEqual(2, run['malformed_lines'])
        self.assertEqual(2, report['malformed_lines'])
        self.assertEqual(2, len(run['malformed_examples']))
        self.assertIn('malformed', pc.render_text(report))

    def test_any_malformed_line_makes_the_report_non_passing(self):
        for extra in ('[HC Perf] window=2 garbage', line(window=2, samples=0)):
            report = self.build({'a.rpt': [line(players=4), extra]})
            self.assertEqual('malformed_input', report['verdict'])
            self.assertIn('malformed_input', pc.render_text(report))
            self.assertEqual('pending', report['runtime_acceptance'])
        report = self.build({'a.rpt': [line(players=1), '[HC Perf] bad']})
        self.assertEqual('malformed_input', report['verdict'])
        report = self.build({'a.rpt': ['[HC Perf] bad']})
        self.assertEqual('malformed_input', report['verdict'])
        report = self.build({'a.rpt': [line(players=4, work_max=50.0), '[HC Perf] bad']})
        self.assertEqual('over_budget', report['verdict'])

    def test_window_player_range_decides_the_load_group(self):
        report = self.build({'a.rpt': [line(players=2, players_max=4)]})
        self.assertEqual('insufficient_load', report['by_players']['2-4']['verdict'])
        self.assertEqual('insufficient_load', report['verdict'])
        report = self.build({'a.rpt': [line(players=3, players_max=6)]})
        self.assertEqual('within_provisional_budget', report['by_players']['3-6']['verdict'])
        self.assertEqual('within_provisional_budget', report['verdict'])
        report = self.build({'a.rpt': [line(players=4, players_max=9)]})
        self.assertEqual('above_target_load', report['by_players']['4-9']['verdict'])
        report = self.build({'a.rpt': [line(players=4, players_max=4)]})
        self.assertIn('4', report['by_players'])
        report = self.build({'a.rpt': [line(players=0, players_max=5, work_max=90.0)]})
        self.assertEqual('insufficient_load', report['verdict'])
        self.assertEqual(['0-5'], report['runs'][0]['players_seen'])

    def test_real_wrapped_lines_in_a_file_are_two_clean_windows(self):
        report = self.build({'a.rpt': ['noise', REAL_WINDOW_1, REAL_WINDOW_2]})
        self.assertEqual(0, report['malformed_lines'])
        self.assertEqual(2, report['overall']['windows'])
        self.assertEqual('insufficient_load', report['verdict'])
        self.assertEqual(289.0, report['overall']['worst']['work_max'])

    def test_a_file_with_no_perf_lines_yields_no_data_verdict(self):
        report = self.build({'a.rpt': ['nothing here']})
        self.assertEqual('no_data', report['verdict'])
        self.assertEqual('pending', report['runtime_acceptance'])

    def test_custom_budgets_change_the_verdict(self):
        budgets = dict(pc.DEFAULT_BUDGETS)
        budgets['work_p95_ms'] = 1.0
        report = self.build({'a.rpt': [line(players=4, work_p95=2.0)]}, budgets)
        self.assertEqual('over_budget', report['verdict'])

    def test_tick_p95_budget_is_optional_and_off_by_default(self):
        report = self.build({'a.rpt': [line(players=4, tick_p95=5000.0, tick_p99=5100.0, tick_max=5200.0)]})
        self.assertEqual('within_provisional_budget', report['verdict'])
        budgets = dict(pc.DEFAULT_BUDGETS)
        budgets['tick_p95_ms'] = 1100.0
        report = self.build({'a.rpt': [line(players=4, tick_p95=5000.0, tick_p99=5100.0, tick_max=5200.0)]}, budgets)
        self.assertEqual('over_budget', report['verdict'])


class Budgets(unittest.TestCase):
    def test_json_budget_file_overrides_defaults_and_cli_flags_override_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'budgets.json'
            path.write_text(json.dumps({'work_p95_ms': 2.5, 'work_max_ms': 10}), encoding='utf-8')
            budgets = pc.load_budgets(str(path), {'work_max_ms': 7.0})
            self.assertEqual(2.5, budgets['work_p95_ms'])
            self.assertEqual(7.0, budgets['work_max_ms'])

    def test_bad_budget_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for body in ('[]', '{"work_p95_ms": -1}', '{"work_p95_ms": "x"}', '{"unknown": 1}', 'not json'):
                path = pathlib.Path(directory) / 'b.json'
                path.write_text(body, encoding='utf-8')
                with self.assertRaises(ValueError, msg=body):
                    pc.load_budgets(str(path), {})


class CommandLine(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-B', '-m', 'tools.testing.perf_capture', *args], cwd=ROOT,
                              capture_output=True, text=True,
                              env={'PYTHONDONTWRITEBYTECODE': '1', 'PATH': '/usr/bin:/bin'})

    def test_cli_writes_json_and_text_and_exit_code_tracks_verdict(self):
        with tempfile.TemporaryDirectory() as directory:
            ok = write(directory, 'ok.rpt', [line(players=4)])
            bad = write(directory, 'bad.rpt', [line(players=4, work_max=99.0)])
            out = pathlib.Path(directory) / 'report.json'
            text = pathlib.Path(directory) / 'summary.txt'
            result = self.run_cli(str(ok), '--json-out', str(out), '--text-out', str(text))
            self.assertEqual(0, result.returncode, result.stderr)
            report = json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual('pending', report['runtime_acceptance'])
            self.assertIn('runtime_acceptance: pending', text.read_text(encoding='utf-8'))
            self.assertIn('runtime_acceptance: pending', result.stdout)
            result = self.run_cli(str(bad), '--max-work-max-ms', '20')
            self.assertEqual(1, result.returncode)
            result = self.run_cli(str(bad), '--max-work-max-ms', '100')
            self.assertEqual(0, result.returncode)

    def test_cli_exits_non_zero_for_any_malformed_perf_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write(directory, 'm.rpt', [line(players=4), '[HC Perf] window=2 garbage'])
            result = self.run_cli(str(path))
            self.assertEqual(1, result.returncode, result.stdout)
            self.assertIn('malformed_input', result.stdout)
            wrapped = write(directory, 'w.rpt', [REAL_WINDOW_1, REAL_WINDOW_2])
            self.assertEqual(0, self.run_cli(str(wrapped)).returncode)

    def test_cli_missing_file_is_a_clean_error(self):
        result = self.run_cli('/nonexistent/none.rpt')
        self.assertEqual(2, result.returncode)
        self.assertNotIn('Traceback', result.stderr)


def code_of(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return '\n'.join(re.sub(r'//.*$', '', row) for row in text.splitlines())


class SamplerSource(unittest.TestCase):
    """Static checks only: they say nothing about how the engine runs the class."""

    @classmethod
    def setUpClass(cls):
        cls.text = SAMPLER.read_text(encoding='utf-8')
        cls.code = code_of(cls.text)

    def test_log_format_literal_and_fields_are_present_in_order(self):
        fields = ['window', 'samples', 'tick_p50', 'tick_p95', 'tick_p99', 'tick_max', 'work_p50', 'work_p95',
                  'work_max', 'players_min', 'players_max']
        self.assertIn('[HC Perf] window=', self.text)
        positions = [self.text.index(' ' + name + '=') for name in fields[1:]]
        self.assertEqual(sorted(positions), positions)

    def test_exactly_one_print_call_emits_the_window_line(self):
        # Print(variable) makes the engine print the declaration (`string report = '...'`); an expression prints plain.
        self.assertEqual(1, len(re.findall(r'\bPrint\("" \+ report\);', self.code)))
        self.assertEqual(0, len(re.findall(r'\bPrint\(report\)', self.code)))
        self.assertEqual(1, self.code.count('[HC Perf]'))

    def test_sample_cap_is_a_named_constant_and_enforced(self):
        self.assertRegex(self.code, r'const int HC_PERF_MAX_SAMPLES\s*=\s*512;')
        self.assertIn('HC_PERF_MAX_SAMPLES', self.code.split('void Sample(')[1])

    def test_server_only_guard(self):
        start = self.code.split('void Start(')[1].split('void Sample(')[0]
        self.assertIn('GetGame().IsServer()', start)
        sample = self.code.split('void Sample(')[1]
        self.assertIn('m_Active', sample)

    def test_self_calibrates_from_a_delta_and_clamps_the_window(self):
        self.assertRegex(self.code, r'const int HC_PERF_MAX_WINDOW_SECONDS\s*=\s*120;')
        self.assertIn('m_WindowTick0 = TickCount(0);', self.code)
        self.assertIn('m_WindowTime0 = GetGame().GetTickTime();', self.code)
        self.assertIn('TickCount(m_WindowTick0)', self.code)
        self.assertIn('GetTickTime() - m_WindowTime0', self.code)
        self.assertIn('" ticks_per_ms="', self.code)
        self.assertIn('" calibration=invalid"', self.code)

    def test_calibration_rejects_negative_and_implausible_deltas(self):
        self.assertRegex(self.code, r'const float HC_PERF_MAX_TICKS_PER_MS\s*=\s*\d+(?:\.\d+)?;')
        emit = self.code.split('void EmitWindow()')[1]
        self.assertRegex(emit, r'ticksDelta\s*>\s*0')
        self.assertIn('HC_PERF_MAX_TICKS_PER_MS', emit)
        self.assertIn('HC_PERF_MIN_TICKS_PER_MS', emit)
        self.assertIn('HC_PERF_MAX_WINDOW_SECONDS', emit)
        self.assertIn('ticksPerMs <= HC_PERF_MAX_TICKS_PER_MS', emit)

    def test_players_are_tracked_per_sample_as_min_and_max(self):
        sample = self.code.split('void Sample(')[1].split('void Stop()')[0]
        self.assertIn('CountPlayers()', sample)
        self.assertIn('m_PlayersMin', sample)
        self.assertIn('m_PlayersMax', sample)
        emit = self.code.split('void EmitWindow()')[1]
        self.assertNotIn('CountPlayers()', emit)
        reset = self.code.split('void ResetWindow()')[1].split('protected')[0]
        self.assertIn('m_PlayersMin', reset)
        self.assertIn('m_PlayersMax', reset)

    def test_invalid_calibration_skips_work_values(self):
        emit = self.code.split('void EmitWindow()')[1]
        self.assertLess(emit.index('if (calibrated)'), emit.index('" work_p50="'))
        self.assertLess(emit.index('" work_max="'), emit.index('" players_min="'))
        self.assertLess(emit.index('" players_max="'), emit.index('" ticks_per_ms="'))
        self.assertLess(emit.index('" players_min="'), emit.index('" players_max="'))
        self.assertNotIn('" players="', self.code)

    def test_not_a_module_and_no_file_io(self):
        self.assertNotRegex(self.code, r'extends\s+HCModule')
        for banned in ('FileHandle', 'OpenFile', 'FPrint', 'JsonFileLoader', 'MakeDirectory', '$profile'):
            self.assertNotIn(banned, self.code)

    def test_public_api_is_start_sample_stop(self):
        self.assertRegex(self.code, r'void Start\(int windowSeconds\)')
        self.assertRegex(self.code, r'void Sample\(float elapsedSeconds, int workTicks\)')
        self.assertRegex(self.code, r'void Stop\(\)')

    def test_enforce_rules(self):
        self.assertNotIn('?', self.code)
        self.assertEqual([], [r for r in self.code.splitlines() if re.match(r'^\s*(\|\||&&)', r)])
        self.assertIsNone(re.search(r'\b\d+(?:\.\d+)?[eE][+-]?\d+\b', self.code))

    def test_no_duplicate_locals_per_function_and_no_engine_type_identifiers(self):
        engine_types = {'array', 'Man', 'Math', 'string', 'float', 'int', 'bool', 'vector', 'Object', 'Entity',
                        'World', 'Weather', 'Param', 'Class', 'Managed', 'map', 'set', 'ref', 'auto', 'typename'}
        bodies = re.findall(r'\n    (?:protected |static )*(?:void|bool|int|float|string)\s+\w+\([^)]*\)\s*\n    \{(.*?)\n    \}',
                            self.code, re.S)
        self.assertGreaterEqual(len(bodies), 5)
        for body in bodies:
            names = re.findall(r'\b(?:int|float|string|bool|Man)\s+([A-Za-z_]\w*)\s*[=;]', body)
            self.assertEqual(len(names), len(set(names)), names)
        declared = re.findall(r'\b(?:int|float|string|bool)\s+([A-Za-z_]\w*)\s*[=;,)]', self.code)
        self.assertEqual(set(), set(declared) & engine_types)

    def test_integer_concatenation_uses_explicit_to_string(self):
        self.assertIsNone(re.search(r'"\s*\+\s*(?:m_\w+|count|index)\s*[;+]', self.code))


if __name__ == '__main__':
    unittest.main()
