"""Read-only client compile evidence check; never launches a native executable.

Compile diagnostics fail the check; other SCRIPT (E) lines are reported separately
as runtime_errors and do not fail compile completion. Release verification still
requires zero runtime script errors and VMEs through activity_check/rpt_summary.
Missing or invalid completion evidence also exits nonzero.
"""
import argparse
from pathlib import Path
import re

MAX_BYTES = 64 * 1024 * 1024
MAX_LINE = 16384
FAILURE = re.compile(
    r"Can't compile|Cannot compile|Compile error|Multiple declaration of function|"
    r"Script validation failed|Failed to load .*script|"
    r"script.*module.*(?:failed|failure)|(?:failed|unable|cannot) to load.*(?:script|module)", re.I)
# Step receipts originate in 5_Mission/HCClientDriverSteps.c:91; a Game-layer
# connection trace alone cannot establish that Mission compiled.
COMPLETE = re.compile(r'\bModule:\s*Mission;\s*loaded\s+[1-9]\d*x?\s+files\b|'
                      r'\[HC Driver\] step=[A-Za-z0-9_-]+\s+kind=', re.I)


SCRIPT_ERROR = re.compile(r'SCRIPT\s*\(E\)', re.I)


def _counts(line):
    compile_error = bool(FAILURE.search(line))
    return (int(compile_error), int(not compile_error and bool(SCRIPT_ERROR.search(line))),
            bool(COMPLETE.search(line)))


def _combine(left, right):
    return (left[0] + right[0], left[1] + right[1], left[2] or right[2])


class Scanner:
    """Bounded append-only polling cache; stores counts/offsets, never log text.

    Unchanged (path, size, mtime) evidence is reused. Appends resume at the last
    complete line; truncation, replacement or same-size edits restart that file.
    Each scan retains at most the current 32 paths and enforces the total byte
    and line bounds, including bytes already scanned.
    """
    def __init__(self):
        self.files = {}

    def _file(self, path, stat):
        signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
        old = self.files.get(path)
        if old and old[0] == signature:
            return old[3]
        offset, counts = 0, (0, 0, False)
        if old and old[0][:2] == signature[:2] and stat.st_size > old[0][2]:
            offset, counts = old[1:3]
        # An unfinished line is counted provisionally, then reread on append so
        # split markers and UTF-8 characters cannot be lost or counted twice.
        total = counts
        with path.open('rb') as stream:
            stream.seek(offset)
            while stream.tell() < stat.st_size:
                raw = stream.readline(min(MAX_LINE + 1, stat.st_size - stream.tell()))
                if not raw:
                    raise OSError('log changed during scan')
                if len(raw) > MAX_LINE:
                    raise ValueError('logs_oversized')
                total = _combine(counts, _counts(raw.decode('utf-8', errors='replace')))
                if raw.endswith(b'\n'):
                    counts, offset = total, stream.tell()
        self.files[path] = (signature, offset, counts, total)
        return total

    def scan(self, rpt, script_logs=None):
        """Check a fresh client RPT and all same-session script logs.

        Automatic discovery scans ALL sibling script logs. Use a fresh isolated
        profile (or pass the exact session's script_logs). Only counts and reason
        codes escape this parser, never private log content. ``errors`` remains
        the compatibility name for the compile-class count.
        """
        result = dict(passed=False, reason='logs_unavailable', logs=0, errors=0,
                      compile_errors=0, runtime_errors=0, complete=False)
        try:
            rpt = Path(rpt)
            scripts = sorted(rpt.parent.glob('script_*.log')) if script_logs is None else list(script_logs)
            paths = list(dict.fromkeys([rpt, *(Path(p) for p in scripts)]))
            if len(paths) > 32:
                self.files.clear()
                result['reason'] = 'too_many_logs'
                return result
            self.files = {path: self.files[path] for path in paths if path in self.files}
            consumed = 0
            for path in paths:
                stat = path.stat()
                if not path.is_file() or stat.st_size > MAX_BYTES:
                    result['reason'] = 'logs_unavailable_or_oversized'
                    return result
                consumed += stat.st_size
                if consumed > MAX_BYTES:
                    result['reason'] = 'logs_oversized'
                    return result
                errors, runtime, complete = self._file(path, stat)
                result['errors'] += errors
                result['compile_errors'] += errors
                result['runtime_errors'] += runtime
                result['complete'] |= complete
                result['logs'] += 1
        except ValueError as error:
            if str(error) == 'logs_oversized':
                result['reason'] = 'logs_oversized'
            return result
        except (OSError, TypeError):
            return result
        result['reason'] = ('compile_errors' if result['compile_errors'] else
                            'clean' if result['complete'] else 'completion_missing')
        result['passed'] = result['reason'] == 'clean'
        return result


def scan(rpt, script_logs=None):
    """One-shot scan; use Scanner across driver polls to reuse bounded evidence."""
    return Scanner().scan(rpt, script_logs)


def verdict_line(result):
    return ('client_compile_check: %s reason=%s logs=%d errors=%d runtime_errors=%d complete=%s' % (
        'PASS' if result['passed'] else 'FAIL', result['reason'], result['logs'],
        result['errors'], result.get('runtime_errors', 0), str(result['complete']).lower()))


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
