"""Sequential Workbench/native calibration on historical compile fixes (lead only)."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

from tools.release import wb_compile as wb

REPO = Path(__file__).resolve().parents[2]
# Reasons condensed from each fix's git subject; never inferred from offline tests.
CORPUS = (
    ('47f27ad5', 'Compile the M-map admin view natively'),
    ('386809e1', 'Fix native compile errors in fortification and Interiors'),
    ('1c48658f', 'Rename the interiors variable using a native keyword'),
    ('f56f40bf', 'Split the camp visitor readiness comparison'),
    ('755a572f', 'Rename the HC-43 Queue field'),
    ('25a7dc25', 'Own fallback refusal results in strong locals'),
    ('630467f1', 'Split HCWorldData.Valid formula-too-complex cap check'),
    ('acab865c', 'Rename HCXGrudge.Slot to avoid the native Slot type'),
    ('6daeb18a', 'Declare infected hook, move group IO and strongly own cellar sampler'),
    ('5fed8436', 'Rename salvage Ray colliding with a loaded dependency'),
    ('3cd74237', 'Rename template File members colliding with a dependency type'),
    ('d776707b', 'Qualify stimulus enum members'),
    ('d790c437', 'Move taped light hooks off EntityAI to compile World'),
)
WB_STATUSES = {'passed', 'compile_failed', 'unverified', 'timeout', 'incomplete_logs',
               'tool_failed', 'blocked', 'controller_failed', 'cleanup_unconfirmed', 'unavailable'}


class Refusal(ValueError):
    """A fixed, public diagnostic safe to print."""


def git(*arguments):
    result = subprocess.run(['git', *arguments], cwd=REPO, capture_output=True,
                            text=True, check=False, timeout=120)
    if result.returncode:
        raise Refusal('corpus revision missing or parent is not an ancestor of main')
    return result.stdout.strip()


def validate_corpus():
    """Resolve every entry before any compiler starts; read-only git operations."""
    entries = []
    for sha, reason in CORPUS:
        fix = git('rev-parse', '--verify', sha + '^{commit}')
        parent = git('rev-parse', '--verify', sha + '^')
        git('merge-base', '--is-ancestor', parent, 'main')
        entries.append({'fix': sha, 'fix_commit': fix, 'parent_commit': parent, 'reason': reason})
    return entries


def location(errors):
    """Retain only a source location, never raw diagnostics or absolute folders."""
    for error in errors:
        name, line = error.get('file'), error.get('line')
        if not isinstance(name, str) or type(line) is not int or line < 1:
            continue
        name = wb.mask(name).replace('\\', '/')
        # Keep known source roots only. Unknown paths retain a safe basename.
        match = re.search(r'(?:HollowCountry(?:ExpansionAI)?/)?scripts/[^\s]+\.c$', name, re.I)
        name = match[0] if match else name.rsplit('/', 1)[-1]
        if not re.fullmatch(r'[A-Za-z0-9_./-]+\.c', name) or '..' in name:
            continue
        return {'file': name, 'line': line}
    return None


def output_tail(text):
    """Bound both line count and bytes; redact before persisting any tool output."""
    return '\n'.join(wb.private(line.replace('\\\\', '\\'))[:2000] for line in text.splitlines()[-200:]) + '\n'


def native_verdict(text, code):
    """Parse compile_gate's terminal verdict, never a launcher exit alone."""
    verdicts = re.findall(r'^compile_gate: (PASS|FAIL) status=([a-z0-9-]+)$', text, re.M)
    if len(verdicts) != 1:
        return 'unverified', 'missing_or_ambiguous_terminal_verdict'
    outcome, status = verdicts[0]
    if outcome == 'PASS' and code == 0 and status in {
            'initialized', 'timeout', 'mission-loaded-runtime-json'} and (
            'compile_gate: Mission loaded with zero compile errors; runtime acceptance pending' in text):
        return 'passed', 'mission_loaded'
    # compiler-error is also used by the probe for runtime/self-test failures.
    # Require the gate's emitted script source diagnostic or compile-failure line.
    source_error = re.search(r'^compile_gate: script_error: .*SCRIPT\s*\(E\).*\.c[,(:]\d+', text, re.M)
    compile_error = any(wb.compile_gate.COMPILE_FAILURE.search(line) for line in text.splitlines()
                        if line.startswith('compile_gate: '))
    if outcome == 'FAIL' and code == 1 and status == 'compiler-error' and (source_error or compile_error):
        return 'compile_failed', 'compiler_error'
    return 'unverified', 'gate_' + outcome.lower() + '_' + status


def invoke(tool, commit):
    """Retry only the driver's unknown prelaunch state query; never rerun a launch."""
    tails = []
    for attempt in range(3):
        result = subprocess.run([sys.executable, '-B', '-m', 'tools.release.' + tool,
                                 '--tree', str(REPO), '--commit', commit], cwd=REPO,
                                capture_output=True, text=True, errors='replace', check=False)
        text = result.stdout + '\n' + result.stderr
        tails.append('attempt=' + str(attempt + 1) + '\n' + output_tail(text))
        if tool != 'wb_compile':
            status, reason = native_verdict(text, result.returncode)
            receipt = {'status': status, 'reason': reason,
                       'first_error': location(wb.diagnostics(text))}
            break
        try:
            report = json.loads(result.stdout)
            status = report['status']
            if status not in WB_STATUSES:
                raise ValueError('unknown verdict')
            expected_code = 0 if status == 'passed' else 1 if status == 'compile_failed' else None
            if expected_code is not None and result.returncode != expected_code:
                raise ValueError('inconsistent verdict')
            first = location(report.get('errors', []))
        except (ValueError, KeyError, TypeError, AttributeError):
            receipt = {'status': 'invalid_report', 'reason': 'invalid_or_inconsistent_report', 'first_error': None}
            break
        receipt = {'status': status, 'first_error': first}
        reason = report.get('reason')
        if isinstance(reason, str):
            receipt['reason'] = wb.private(reason)[:2000]
        build = report.get('workbench_build', '')
        if isinstance(build, str) and re.fullmatch(r'[0-9a-f]{16,64}', build):
            receipt['workbench_build'] = build
        if status != 'blocked' or reason != 'Workbench process state: unknown' or attempt == 2:
            break
        time.sleep(0.5)
    if tool == 'wb_compile':
        receipt['state_query_retries'] = attempt
    receipt['output_tail'] = output_tail(''.join(tails))
    return receipt


def agreement(row, gate):
    parent, fix = row.get('wb_parent', {}), row.get('wb_fix', {})
    if not parent or not fix or (gate and 'native_parent' not in row):
        return 'incomplete'
    if parent['status'] not in {'passed', 'compile_failed'} or fix['status'] not in {'passed', 'compile_failed'}:
        return 'inconclusive'
    if gate and row['native_parent']['status'] not in {'passed', 'compile_failed'}:
        return 'inconclusive'
    if parent['status'] != 'compile_failed':
        return 'disagree'
    # Corpus fixes are chained: a fix commit may still fail on the next corpus
    # error. It agrees when the parent's first error is gone, never when it stays.
    if fix['status'] == 'compile_failed':
        if not fix.get('first_error') or not parent.get('first_error'):
            return 'inconclusive'
        if same_error(fix['first_error'], parent['first_error']):
            return 'disagree'
    if gate:
        native = row['native_parent']
        if native['status'] != parent['status']:
            return 'disagree'
        if native.get('first_error') and parent.get('first_error') and (
                native['first_error'].get('file', '').lower() != parent['first_error'].get('file', '').lower()):
            return 'disagree'
    return 'agree' if gate else 'expected_only'


def same_error(left, right):
    return (left.get('file', '').lower(), left.get('line')) == (right.get('file', '').lower(), right.get('line'))


def write_reports(out, report):
    """Checkpoint serial invocations with separately stored, redacted output tails."""
    out.mkdir(parents=True, exist_ok=True)
    for name in ('agreement.json', 'agreement.md'):
        if (out / name).is_symlink():
            raise Refusal('report files must not be symlinks')
    report['summary'] = {key: 0 for key in ('agree', 'disagree', 'inconclusive', 'incomplete', 'expected_only')}
    for row in report['entries']:
        report['summary'][agreement(row, report['gate'])] += 1
    rows = ['| Fix | Reason | WB parent | First error | WB fix | Native parent | Agreement |',
            '| --- | --- | --- | --- | --- | --- | --- |']
    for row in report['entries']:
        first = row.get('wb_parent', {}).get('first_error')
        error = '%s:%s' % (first['file'], first['line']) if first else 'unavailable'
        values = [row['fix'], row['reason'], row.get('wb_parent', {}).get('status', 'pending'), error,
                  row.get('wb_fix', {}).get('status', 'pending'),
                  row.get('native_parent', {}).get('status', 'pending' if report['gate'] else 'not run'),
                  agreement(row, report['gate'])]
        rows.append('| ' + ' | '.join(values) + ' |')
    (out / 'agreement.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    (out / 'agreement.md').write_text('# Workbench calibration\n\n' + '\n'.join(rows) + '\n\n'
                                    'Expected-only results do not establish native agreement. '
                                    'No boot, gameplay or multiplayer acceptance.\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', nargs='+', action='extend', metavar='SHA', help='select corpus fix SHAs')
    parser.add_argument('--stop-on-inconclusive', action='store_true', help='stop after the first inconclusive tool outcome')
    parser.add_argument('--gate', action='store_true', help='also run the native gate on each parent')
    parser.add_argument('--out', type=Path, help='output directory outside the repository (default: job TEMP)')
    args = parser.parse_args(argv)
    try:
        if args.only and set(args.only) - {sha for sha, _ in CORPUS}:
            raise Refusal('--only requires a listed corpus fix SHA')
        entries = validate_corpus()
        if not (wb.WORKBENCH / 'WorkbenchApp.exe').is_file():
            raise Refusal('Workbench install missing; calibration refused')
        out = args.out.expanduser().resolve() if args.out else None
        if out is None:
            root = Path(os.environ.get('TEMP') or tempfile.gettempdir()).resolve()
            if root.is_relative_to(REPO):
                raise Refusal('job TEMP must be outside the repository')
            out = Path(tempfile.mkdtemp(prefix='hc-wb-calibrate-', dir=root))
        if out.is_relative_to(REPO):
            raise Refusal('--out must be outside the repository')
        report = {'gate': args.gate, 'entries': [entry for entry in entries
                  if not args.only or entry['fix'] in args.only], 'status': 'running'}
        write_reports(out, report)
        for row in report['entries']:
            jobs = [('wb_parent', 'wb_compile', row['fix'] + '^'),
                    ('wb_fix', 'wb_compile', row['fix'])]
            if args.gate:
                jobs.append(('native_parent', 'compile_gate', row['fix'] + '^'))
            for key, tool, commit in jobs:
                name = row['fix'] + '-' + key + '.log'
                if (out / name).is_symlink():
                    raise Refusal('output tails must not be symlinks')
                try:
                    receipt = dict(invoke(tool, commit))
                except (OSError, ValueError, subprocess.SubprocessError):
                    receipt = {'status': 'tool_failed', 'reason': 'invocation_failed', 'first_error': None}
                tail = receipt.pop('output_tail', 'tool output unavailable\n')
                (out / name).write_text(output_tail(tail))
                receipt['output_log'] = name
                row[key] = receipt
                write_reports(out, report)
                print('wb_calibrate: ' + row['fix'] + ' ' + key + '=' + row[key]['status'], flush=True)
                if args.stop_on_inconclusive and row[key]['status'] not in {'passed', 'compile_failed'}:
                    report['status'] = 'incomplete'
                    write_reports(out, report)
                    return 2
        success = all(agreement(row, args.gate) in {'agree', 'expected_only'} for row in report['entries'])
        inconclusive = any(agreement(row, args.gate) in {'inconclusive', 'incomplete'} for row in report['entries'])
        report['status'] = 'incomplete' if inconclusive else (('agree' if args.gate else 'expected_only') if success else 'disagree')
        write_reports(out, report)
        print('wb_calibrate: ' + report['status'] + '; summary=' + json.dumps(report['summary'], sort_keys=True)
              + '; wrote agreement.json and agreement.md')
        return 2 if inconclusive else 0 if success else 1
    except Refusal as error:
        print('wb_calibrate: refused; ' + str(error), file=sys.stderr)
        return 2
    except (OSError, ValueError, subprocess.SubprocessError):
        # Exception messages can embed home directories, account names or raw tool output.
        print('wb_calibrate: refused; verify corpus/main, Workbench install and external output directory',
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
