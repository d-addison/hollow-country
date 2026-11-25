"""Read-only client compile evidence check; never launches a native executable."""
import argparse
from pathlib import Path
import re

MAX_BYTES = 64 * 1024 * 1024
MAX_LINE = 16384
FAILURE = re.compile(
    r"Can't compile|Cannot compile|Compile error|Multiple declaration of function|"
    r"SCRIPT\s*\(E\)|Script validation failed|Failed to load .*script|"
    r"script.*module.*(?:failed|failure)|(?:failed|unable|cannot) to load.*(?:script|module)", re.I)
# Step receipts originate in 5_Mission/HCClientDriverSteps.c:91; a Game-layer
# connection trace alone cannot establish that Mission compiled.
COMPLETE = re.compile(r'\bModule:\s*Mission;\s*loaded\s+[1-9]\d*x?\s+files\b|'
                      r'\[HC Driver\] step=[A-Za-z0-9_-]+\s+kind=', re.I)


def scan(rpt, script_logs=None):
    """Check a fresh client RPT and its script logs, failing closed without completion.

    Automatic discovery deliberately scans ALL sibling script logs. Callers must
    use a fresh isolated profile (or pass the exact session's script_logs).
    Only counts/reason codes escape this parser, never private log content.
    """
    result = dict(passed=False, reason='logs_unavailable', logs=0, errors=0, complete=False)
    try:
        rpt = Path(rpt)
        scripts = sorted(rpt.parent.glob('script_*.log')) if script_logs is None else list(script_logs)
        paths = list(dict.fromkeys([rpt, *(Path(p) for p in scripts)]))
        if len(paths) > 32:
            result['reason'] = 'too_many_logs'
            return result
        consumed = 0
        for path in paths:
            if not path.is_file() or path.stat().st_size > MAX_BYTES:
                result['reason'] = 'logs_unavailable_or_oversized'
                return result
            with path.open('rb') as stream:
                while True:
                    raw = stream.readline(MAX_LINE + 1)
                    if not raw:
                        break
                    consumed += len(raw)
                    if consumed > MAX_BYTES or len(raw) > MAX_LINE:
                        result['reason'] = 'logs_oversized'
                        return result
                    line = raw.decode('utf-8', errors='replace')
                    result['errors'] += bool(FAILURE.search(line))
                    result['complete'] |= bool(COMPLETE.search(line))
            result['logs'] += 1
    except (OSError, TypeError, ValueError):
        return result
    result['reason'] = ('compile_errors' if result['errors'] else
                        'clean' if result['complete'] else 'completion_missing')
    result['passed'] = result['reason'] == 'clean'
    return result


def verdict_line(result):
    return ('client_compile_check: %s reason=%s logs=%d errors=%d complete=%s' % (
        'PASS' if result['passed'] else 'FAIL', result['reason'], result['logs'],
        result['errors'], str(result['complete']).lower()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rpt', type=Path, required=True, help='fresh client RPT from the checked build')
    parser.add_argument('--script-log', type=Path, action='append',
                        help='same-session script log; repeat for every log (default: all sibling script_*.log)')
    args = parser.parse_args(argv)
    result = scan(args.rpt, args.script_log)
    print(verdict_line(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
