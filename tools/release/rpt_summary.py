"""Streaming privacy-filtered RPT verdict and module/performance summary.

python3 -B -m tools.release.rpt_summary server.RPT [--json]
Exit: 0 connect-enabled/no observed failure, 2 compile, 3 crash, 4 not-ready,
5 incomplete, 6 input error, 7 persistence corruption, 8 runtime script error. Historical evidence is not runtime acceptance.
"""
import argparse
import json
from pathlib import Path
import re
import sqlite3
import tempfile

from tools.setup.server_report import redact, DROPPED
from tools.validate.tick_cost_report import aggregate

DROP = re.compile(r'steam ?id|uid|name=|[0-9]{17}|Player "|id=|password|admin.?id', re.I)
HOME = re.compile(r'(?:/home/[^/\s"\'<>]+|/Users/[^/\s"\'<>]+|/root(?=/|\s|$)|[A-Z]:[\\/]+Users[\\/]+[^\\/\s"\'<>]+|/mnt/[a-z]/Users/[^/\s"\'<>]+)', re.I)
MISSION_LOADED = re.compile(r"\bModule:\s*Mission;\s*loaded\b", re.I)
SCRIPT_ERROR = re.compile(r'SCRIPT\s*\(E\)', re.I)
COMPILE_MARKER = re.compile(r"Can't compile|Cannot compile", re.I)
CORRUPTED = re.compile(r'Scripted variables corrupted upon\s+"([^"\r\n]+)"', re.I)
CASCADE = re.compile(r"Bad type|Can.t find (?:class|variable)|Unknown type|Wrong number of template|Error in parameters|Failed to load .*script", re.I)
CRASH = re.compile(r'NULL pointer|Unhandled exception|Access[_ ]violation|Exception code:|\bcrash(?:ed)?\b|\.mdmp\b|\.dmp\b|minidump|stack overflow', re.I)
HC = re.compile(r'\[HC(?:\s+([^\]]+))?\]')
READINESS = re.compile(r'ready|readiness|refus|unavailable|bind failed|degrad|missing|invalid|disabled|blocked|not available', re.I)
NOT_READY = re.compile(r'\bready\s*=\s*false\b', re.I)
READY = re.compile(r'\bready\s*=\s*true\b', re.I)
PERF = re.compile(r'\b(tick_max|work_max|slowest_module_max_ms)\s*=\s*([0-9]+(?:\.[0-9]+)?)', re.I)
TICKS = re.compile(r'\b([a-z_]*(?:ticks|tick_ms)[a-z_]*)\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)', re.I)


HIVE_FINISHED = '[CE][Hive] :: Init sequence finished'
RPT_CLOCK = re.compile(r'^\s*(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d+))?\b')
READY_FIELDS = re.compile(r'\[HC Ready\]\s+module=([A-Za-z0-9_.-]{1,96})\s+enabled=(true|false)\s+ready=(true|false)\b')


class ReadinessTiming:
    """Bounded same-boot R4 evidence; retain no raw RPT text or identities."""
    def __init__(self):
        self.clock = None
        self.previous = None
        self.hive_at = None
        self.modules = {}
        self.first_ready = {}
        self.invalid = False

    def observe(self, raw):
        stamp = RPT_CLOCK.match(raw)
        at = None
        if stamp:
            h, m, sec = map(int, stamp.group(1, 2, 3))
            if h < 24 and m < 60 and sec < 60:
                clock = h * 3600 + m * 60 + sec + float('0.' + (stamp[4] or '0'))
                if self.previous is None:
                    self.clock = clock
                    self.previous = clock
                else:
                    delta = clock - self.previous
                    if delta < -43200:
                        delta += 86400
                    if delta >= 0:
                        self.clock += delta
                        self.previous = clock
                at = self.clock
        if HIVE_FINISHED in raw:
            if self.hive_at is not None or at is None:
                self.invalid = True
            else:
                self.hive_at = at
        safe = filtered(raw)
        match = READY_FIELDS.search(safe) if safe else None
        if match:
            module, enabled, ready = match.groups()
            if module not in self.modules and len(self.modules) >= 256:
                self.invalid = True
                return
            self.modules[module] = enabled == 'true'
            if enabled == 'true' and ready == 'true':
                if at is None:
                    self.invalid = True
                elif module not in self.first_ready:
                    self.first_ready[module] = at

    def result(self, limit):
        enabled = sorted(m for m, on in self.modules.items() if on)
        pending = [m for m in enabled if m not in self.first_ready]
        late = [] if self.hive_at is None else [m for m in enabled if m in self.first_ready
                    and self.first_ready[m] - self.hive_at > limit]
        status = 'unavailable' if self.invalid or self.hive_at is None or not self.modules else (
            'failed' if pending or late else 'passed')
        before_hive = [] if self.hive_at is None else [m for m in enabled
                       if m in self.first_ready and self.first_ready[m] < self.hive_at]
        # Ready before Hive is already ready at the R4 baseline. Keep the
        # affected modules visible rather than emitting negative durations.
        elapsed = [max(0, self.first_ready[m] - self.hive_at) for m in enabled
                   if m in self.first_ready and self.hive_at is not None]
        return dict(status=status, max_after_hive_seconds=max(elapsed, default=None),
                    limit_seconds=limit, pending=pending, late=late, ready_before_hive=before_hive)


def filtered(line):
    """Strict audit drop policy, then existing report redaction and home masking.

    Player-quoted lines are dropped under the strict rule, rather than exposing
    any part of a player event. Other callers can replace names before filtering.
    """
    if DROP.search(line):
        return None
    safe = redact(HOME.sub('~', line.rstrip()))
    return None if safe == DROPPED else HOME.sub('~', safe)


def lines(path):
    """Bound memory even for malformed RPTs with multi-megabyte lines."""
    with Path(path).open(encoding='utf-8', errors='replace') as stream:
        while True:
            line = stream.readline(16385)
            if not line:
                break
            if len(line) > 16384:
                while line and not line.endswith('\n'):
                    line = stream.readline(16385)
                continue
            yield line


def module_line(line):
    marker = HC.search(line)
    if not marker or not READINESS.search(line[marker.start():]):
        return None
    module = marker.group(1) or 'Core'
    if module in ('Ready', 'Reached'):
        field = re.search(r'\b(?:module|feature)=([^\s;]+)', line)
        module = field.group(1) if field else module
    return module, line[marker.start():]


def failure(line, mission_loaded=False):
    """Inspect raw text so privacy filtering cannot hide a failing verdict."""
    lowered = line.lower()
    if COMPILE_MARKER.search(line):
        return 'compile_failed'
    if CORRUPTED.search(line):
        return 'persistence_corrupted'
    if SCRIPT_ERROR.search(line):
        return 'script_error' if mission_loaded else 'compile_failed'
    if any(token in lowered for token in ('null pointer', 'unhandled exception', 'access violation',
                                          'access_violation', 'exception code:', 'crash', '.mdmp',
                                          '.dmp', 'minidump', 'stack overflow')) and CRASH.search(line):
        return 'crashed'
    # Only the per-module [HC Ready] line decides; internal phase lines such as
    # "[HC Expansion AI] readiness (server start) ... Ready=false" are progress.
    if '[HC Ready]' in line and NOT_READY.search(line) and not re.search(r'\benabled\s*=\s*false\b', line, re.I):
        return 'not_ready'
    return None


class Summary:
    """Disk-backed distinct diagnostics: every filtered line, bounded RAM.

    The temporary database contains only filtered HC lines and is removed on
    close. JSON/text are streamed too; as_dict intentionally not provided.
    """
    def __init__(self, path):
        self.path = Path(path)
        self.temp = tempfile.TemporaryDirectory(prefix='hc-rpt-')
        self.db = sqlite3.connect(str(Path(self.temp.name) / 'summary.sqlite'))
        self.db.execute('PRAGMA cache_size=-1024')
        self.db.execute('CREATE TABLE diagnostics(module TEXT, line TEXT, n INTEGER, PRIMARY KEY(module,line))')
        self.errors = []
        self.script_errors = []
        self.mission_loaded = False
        self.cascades = []
        self.compile_markers = []
        self.crashes = []
        self.db.execute('CREATE TABLE corruptions(type TEXT PRIMARY KEY, n INTEGER)')
        self.connected = False
        self.readiness_timing = ReadinessTiming()
        self.failures = set()
        # Last [HC Ready] verdict per enabled module: a boot-time loading state that
        # later prints ready=true (late readiness on the 15 s refresh) is not a failure.
        self.ready_last = {}
        self.worst = {}
        self.saves = {}
        self.readiness_count = 0
        self.tick_rows = {}
        self.tick_rejected = 0
        # Lazy import avoids a cycle: activity_check reuses this module's privacy
        # filter and bounded line reader. Activity findings never alter outcome.
        from tools.release.activity_check import Activity
        try:
            self.activity_checker = Activity()
        except (OSError, ValueError, TypeError, KeyError, re.error):
            self.activity_checker = None
        self.activity_error = self.activity_checker is None

    def close(self):
        self.db.close()
        self.temp.cleanup()

    def scan(self):
        for raw in lines(self.path):
            self.readiness_timing.observe(raw)
            if self.activity_checker is not None and not self.activity_error:
                try:
                    self.activity_checker.observe(raw)
                except (ValueError, TypeError):
                    self.activity_error = True
            self.mission_loaded = self.mission_loaded or bool(MISSION_LOADED.search(raw))
            verdict = failure(raw, self.mission_loaded)
            corrupted = CORRUPTED.search(raw)
            if corrupted:
                # Retain only a filtered type, never an entity/player identifier.
                entity_type = filtered(corrupted.group(1))
                if entity_type:
                    self.db.execute('INSERT INTO corruptions VALUES(?,1) ON CONFLICT(type) DO UPDATE SET n=n+1',
                                    (entity_type,))
            if verdict == 'not_ready' or ('[HC Ready]' in raw and READY.search(raw)):
                field = re.search(r'\bmodule=([^\s;]+)', raw)
                if field and (field.group(1) in self.ready_last or len(self.ready_last) < 256):
                    self.ready_last[field.group(1)] = verdict != 'not_ready'
            elif verdict:
                self.failures.add(verdict)
            if 'Player connect enabled' in raw:
                self.connected = True
            # Only retain the first root/cascade/compiler/crash examples.
            # Runtime error storms can contain a million SCRIPT (E) lines.
            needs_error = False
            if verdict == 'compile_failed' and SCRIPT_ERROR.search(raw):
                needs_error = len(self.cascades if CASCADE.search(raw) else self.errors) < 8
            needs_error = needs_error or (verdict == 'script_error' and len(self.script_errors) < 8)
            needs_marker = COMPILE_MARKER.search(raw) and len(self.compile_markers) < 8
            needs_crash = len(self.crashes) < 8 and verdict in ('compile_failed', 'crashed') and CRASH.search(raw)
            if not ('[HC' in raw or needs_error or needs_marker or needs_crash):
                continue
            line = filtered(raw)
            if not line:
                continue
            if COMPILE_MARKER.search(line):
                if len(self.compile_markers) < 8:
                    self.compile_markers.append(line)
            elif verdict == 'script_error' and len(self.script_errors) < 8:
                self.script_errors.append(line)
            elif verdict == 'compile_failed' and SCRIPT_ERROR.search(line):
                target = self.cascades if CASCADE.search(line) else self.errors
                if len(target) < 8:
                    target.append(line)
            if CRASH.search(line) and len(self.crashes) < 8:
                self.crashes.append(line)
            item = module_line(line)
            if item:
                self.readiness_count += 1
                self.db.execute('INSERT INTO diagnostics VALUES(?,?,1) ON CONFLICT(module,line) DO UPDATE SET n=n+1', item)
            metrics = list(PERF.findall(line)) if '[HC Perf]' in line else [
                (field, value) for field, value in TICKS.findall(line)
                if field in ('worst_tick_ticks', 'heaviest_item_ticks', 'max_stage_ticks', 'ticks_max')]
            for field, value in metrics:
                if len(self.worst) < 16 or field in self.worst:
                    rows = self.worst.setdefault(field, [])
                    rows.append((float(value), line))
                    rows[:] = sorted(rows, reverse=True)[:10]
            if '[HC Save]' in line:
                job = re.search(r'\bjob=([^\s;]+)', line)
                key = job.group(1) if job else 'unknown'
                if key in self.saves or len(self.saves) < 256:
                    entry = self.saves.setdefault(key, {})
                    for field, value in TICKS.findall(line):
                        value = float(value)
                        if value >= entry.get(field, (float('-inf'), ''))[0]:
                            entry[field] = (value, line)
        self.db.commit()
        self.tick_rows, self.tick_rejected = aggregate(self.path)
        return self

    @property
    def outcome(self):
        for value in ('compile_failed', 'crashed', 'persistence_corrupted', 'script_error'):
            if value in self.failures:
                return value
        if not all(self.ready_last.values()):
            return 'not_ready'
        return 'connect_enabled' if self.connected else 'incomplete'

    def diagnostics(self):
        return self.db.execute('SELECT module,line,n FROM diagnostics ORDER BY module,line')

    @property
    def activity(self):
        if self.activity_error or not self.activity_checker.modules:
            return dict(activity='unavailable', count=0, error='activity expectations or readiness unavailable or invalid')
        return self.activity_checker.result()

    def header(self):
        from tools.release.acceptance_targets import load_targets
        timing = self.readiness_timing.result(load_targets()['readiness_max_after_hive_seconds'])
        return dict(outcome=self.outcome, connected=self.connected, activity=self.activity,
                    readiness_timing=timing,
                    compile_result='compile_failed' if 'compile_failed' in self.failures else 'no_compile_error_observed',
                    # Root errors precede cascades and the generic module failure.
                    compile_errors=self.errors + self.compile_markers + self.cascades,
                    script_errors=self.script_errors,
                    crash_indicators=self.crashes, readiness_lines=self.readiness_count,
                    persistence_corruption_counts=dict(self.db.execute('SELECT type,n FROM corruptions ORDER BY type')),
                    worst_ticks=self.worst, save_peaks=self.saves,
                    tick_cost={k: {a: sorted(b) if isinstance(b, set) else b for a, b in v.items()}
                               for k, v in self.tick_rows.items()},
                    tick_cost_rejected=self.tick_rejected)

    def print(self, as_json=False):
        if as_json:
            # Do not materialize all module diagnostics in memory.
            prefix = json.dumps(self.header())
            print(prefix[:-1] + ', "modules": [', end='')
            separator = ''
            for module, line, count in self.diagnostics():
                print(separator + json.dumps(dict(module=module, line=line, count=count)), end='')
                separator = ','
            print(']}')
            return
        print('outcome=' + self.outcome)
        print('R4 ' + json.dumps(self.header()['readiness_timing'], sort_keys=True))
        for entity_type, count in self.db.execute('SELECT type,n FROM corruptions ORDER BY type'):
            print(f'persistence_corrupted type={entity_type} count={count}')
        for line in self.errors + self.compile_markers + self.cascades + self.script_errors:
            print(line)
        for line in self.crashes:
            print(line)
        for module, line, count in self.diagnostics():
            print(f'{module} ({count}x): {line}')
        print('Worst ticks (Perf maxima in ms, *_ticks in raw engine units; no target-load acceptance):')
        for field, rows in self.worst.items():
            for peak, line in rows:
                print(f'{field}={peak:g}: {line}')
        print('[HC Save] peaks:')
        for job, fields in self.saves.items():
            for field, (peak, line) in fields.items():
                print(f'{job} {field}={peak:g}: {line}')
        print('[HC TickCost] totals: consumer windows used starved ticks_sum ticks_max')
        for name, row in self.tick_rows.items():
            print(f"{name} {row['windows']} {row['used']:g} {row['starved']:g} {row['ticks']:g} {row['ticks_max']:g}")
        if not self.tick_rows:
            print('no_data')
        print(f'readiness_lines={self.readiness_count}; absent readiness markers do not establish readiness')
        print('[HC Activity] runtime signals (separate from boot verdict):')
        if 'error' in self.activity:
            print('activity=unavailable count=0')
        else:
            from tools.release.activity_check import print_result
            print_result(self.activity)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rpt', type=Path)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    summary = Summary(args.rpt)
    try:
        summary.scan().print(args.json)
        return dict(connect_enabled=0, compile_failed=2, crashed=3, not_ready=4,
                    incomplete=5, persistence_corrupted=7, script_error=8)[summary.outcome]
    except (OSError, sqlite3.Error, ValueError):
        print('RPT summary input/storage unavailable')
        return 6
    finally:
        summary.close()


if __name__ == '__main__':
    raise SystemExit(main())
