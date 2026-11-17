"""Local standard-library mutation harness; mutations run only on throwaway copies."""
import ast
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'scratchpad-review/wp3-r3'
SOURCE = Path('tools/setup/infected_competence_probe.py')
MODULE = 'tests.unit.test_infected_competence'
TARGETS = {
    'H05': 'HookTests.test_r3_observe_budget_stops_at_extra_1000_ms',
    'H07': 'HookTests.test_r3_unchanged_leg_health_is_inconclusive',
    'H17': 'HookTests.test_r3_geometry_ray_height_and_offsets',
    'H18': 'HookTests.test_r3_no_target_sample_returns_false',
    'V13': 'StagingAndReceiptTests.test_r3_one_sample_completed_row_refused',
    'V14': 'StagingAndReceiptTests.test_r3_version_cannot_embed_pinned_version_in_other_build',
    'S03': 'StagingAndReceiptTests.test_r3_survey_classes_sorted_before_limit',
    'S04': 'StagingAndReceiptTests.test_r3_survey_offset_range',
    'S05': 'StagingAndReceiptTests.test_r3_survey_ambiguous_rpy_refused',
    'S11': 'StagingAndReceiptTests.test_r3_stock_trials_without_provenance_refused_before_write',
    'S13': 'HookTests.test_r3_start_delay_lower_boundary',
}


def run(cwd, tests, output):
    command = ['python3', '-m', 'unittest', *tests, '-v']
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=300)
    output.write_text('PYTHONDONTWRITEBYTECODE=1 ' + ' '.join(command) + '\n'
                      + result.stdout + result.stderr + f'\nexit_code={result.returncode}\n')
    return result


def main():
    mode = sys.argv[1]
    if mode == 'baseline':
        tests = [
            'test_r3_initial_position_boundaries_and_later_movement',
            'test_r3_surface_height_bounds_for_completed_and_inconclusive',
            'test_r3_report_height_deltas_and_surveyed_fixture_warning',
            'test_r3_completed_clock_slack_boundaries',
            'test_r3_reasons_enumerated_per_status',
            'test_r3_footprint_reason_requires_hit_before_spawn',
            'test_r3_time_budget_reason_requires_observe_timeout',
            'test_r3_structure_reason_requires_pre_spawn_evidence',
            'test_survey_read_only_even_placements_yaw_provenance_and_stage',
        ]
        for name in tests:
            result = run(ROOT, [MODULE + '.StagingAndReceiptTests.' + name], OUT / ('RED-' + name + '.txt'))
            print(name, 'RED' if result.returncode else 'UNEXPECTED GREEN', flush=True)
        return
    tree = ast.parse((ROOT / 'scratchpad-review/wp3-r2-sonnet-review/mutate.py').read_text())
    mutants = ast.literal_eval(next(node.value for node in tree.body if isinstance(node, ast.Assign)
                                   and any(isinstance(t, ast.Name) and t.id == 'M' for t in node.targets)))
    original = (ROOT / SOURCE).read_text()
    results = []
    for name, old, new in mutants:
        code = name.split()[0]
        if code not in TARGETS:
            continue
        if old not in original:
            raise RuntimeError('Mutation no longer matches: ' + name)
        with tempfile.TemporaryDirectory(prefix='wp3-r3-mutant-') as directory:
            work = Path(directory)
            for folder in ('tools', 'tests'):
                shutil.copytree(ROOT / folder, work / folder, ignore=shutil.ignore_patterns('__pycache__'))
            (work / SOURCE).write_text(original.replace(old, new, 1))
            tests = [MODULE + '.' + TARGETS[code]] if mode == 'red' else [MODULE]
            log = OUT / (('RED-' if mode == 'red' else 'mutation-') + code + '.txt')
            result = run(work, tests, log)
            failures = re.findall(r'^(?:FAIL|ERROR): (\S+)', result.stderr, re.M)
            killed = result.returncode != 0 and ('FAIL: ' + TARGETS[code].split('.')[-1]) in result.stderr
            status = 'KILLED' if killed else 'SURVIVED' if result.returncode == 0 else 'UNEXPECTED FAILURE'
            line = f'{name}: {status}; ' + ', '.join(failures)
            results.append(line)
            print(line, flush=True)
    (OUT / ('red_mutation_results.txt' if mode == 'red' else 'mutation_results.txt')).write_text('\n'.join(results) + '\n')


if __name__ == '__main__':
    main()
