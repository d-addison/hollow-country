"""Streaming activity audit; readiness and runtime acceptance remain separate.

python3 -B -m tools.release.activity_check server.RPT [--client-rpt client.RPT] [--json]
Exit 0: ACTIVE/WAITING only; 8: activity findings; 6: input error.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re

from tools.release.rpt_summary import filtered, lines, HC
from tools.setup.server_report import _EVENT, _PLAYER_ENABLED

DEFAULT_EXPECTATIONS = Path(__file__).resolve().parents[2] / 'config/activity-expectations.json'
STATUSES = ('ACTIVE', 'INERT', 'SILENT', 'NO_SIGNAL', 'WAITING')
SCOPES = ('runtime', 'transport', 'client', 'diagnostic')
TOKEN = re.compile(r'[A-Za-z0-9_.-]{1,96}\Z')
CLOCK = re.compile(r'^\s*(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d+))?\b')
READY_MODULE = re.compile(r'\[HC Ready\]\s+module=([A-Za-z0-9_.-]+)\s+enabled=(true|false)\b')
# Only runtime counts: never configuration budgets such as [HC Config] players=16.
PLAYER_COUNT = re.compile(r'\[HC InfectedLOD\] stats .*\bplayers=(\d+)\b|\[HC Expansion AI\] group scale players=(\d+)\b')
PLAYER_EVENT = re.compile(r'\bplayer\b', re.I)
LEAVE = re.compile(r'\bdisconnected\b|\bkicked\b|\bbanned\b|\bhas left\b', re.I)
JOIN = re.compile(r'\bconnected\b|\bhas joined\b', re.I)


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def load_expectations(path=DEFAULT_EXPECTATIONS):
    """Validate before scanning; configuration is trusted local regex, never RPT code."""
    with Path(path).open(encoding='utf-8') as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('expectations schema')
    entries = data.get('features')
    if not isinstance(entries, list) or not entries or len(entries) > 512:
        raise ValueError('expectations features')
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('expectations entry')
        for key in ('module', 'feature'):
            if not isinstance(entry.get(key), str) or not TOKEN.fullmatch(entry[key]) or not filtered(entry[key]):
                raise ValueError('expectations token')
        identity = (entry['module'], entry['feature'])
        if identity in seen:
            raise ValueError('duplicate feature')
        seen.add(identity)
        if not number(entry.get('floor')) or entry['floor'] <= 0 or not number(entry.get('window_minutes')):
            raise ValueError('expectations limits')
        if entry.get('comparison') not in ('sum', 'max', 'last', 'present') or type(entry.get('needs_player')) is not bool:
            raise ValueError('expectations comparison/player')
        if entry['comparison'] == 'present' and entry['floor'] != 1:
            raise ValueError('presence floor must be 1')
        if entry.get('scope', 'runtime') not in SCOPES:
            raise ValueError('expectations scope')
        if 'signal' not in entry:
            raise ValueError('missing signal')
        signal = entry['signal']
        if signal is None:
            continue
        if not isinstance(signal, dict) or not isinstance(signal.get('tag'), str) or not filtered(signal['tag']):
            raise ValueError('signal tag')
        if not isinstance(signal.get('regex'), str) or len(signal['regex']) > 2048:
            raise ValueError('signal regex')
        pattern = re.compile(signal['regex'])
        fields = signal.get('fields')
        if not isinstance(fields, list) or not fields or len(fields) > 16 or len(set(fields)) != len(fields):
            raise ValueError('signal fields')
        if any(not isinstance(f, str) or f not in pattern.groupindex for f in fields):
            raise ValueError('signal named fields')
    return entries


class Activity:
    """Bounded counters only: raw player markers and identities are never retained."""
    def __init__(self, expectations=DEFAULT_EXPECTATIONS, *, client=False):
        self.client = client
        self.entries = load_expectations(expectations)
        self.states = []
        self.by_tag = {}
        for entry in self.entries:
            state = dict(entry=entry, samples=0, value=None)
            self.states.append(state)
            if entry['signal'] is not None and (entry.get('scope') == 'client') == client:
                signal = entry['signal']
                state['pattern'] = re.compile(signal['regex'])
                self.by_tag.setdefault(signal['tag'], []).append(state)
        self.modules = {}
        self.previous_clock = None
        self.now = 0.0
        # Companion clients need no server readiness or player-connect markers.
        # Their independent exposure starts at their first timestamp.
        self.first_ready = 0.0 if client else None
        self.player_seconds = 0.0
        self.players = 0
        self.presence_observations = 0
        self.clock_lines = 0

    def observe(self, raw):
        stamp = CLOCK.match(raw)
        if stamp:
            h, m, s = map(int, stamp.group(1, 2, 3))
            if h > 23 or m > 59 or s > 59:
                return
            clock = h * 3600 + m * 60 + s + float('0.' + (stamp[4] or '0'))
            if self.previous_clock is not None:
                delta = clock - self.previous_clock
                if delta < -43200:
                    delta += 86400
                # Small backward timestamps occur in interleaved engine log lines.
                if delta >= 0:
                    self.now += delta
                    if self.first_ready is not None and self.players > 0:
                        self.player_seconds += delta
                    self.previous_clock = clock
            else:
                self.previous_clock = clock
            self.clock_lines += 1
        # Privacy exception: reduce existing native connect events to counts only.
        # Never feed raw names, IDs, or event text into the result or error output.
        if not self.client and not _PLAYER_ENABLED.search(raw) and PLAYER_EVENT.search(raw) and _EVENT.search(raw):
            if LEAVE.search(raw):
                self.players = max(0, self.players - 1)
                self.presence_observations += 1
            elif JOIN.search(raw):
                self.players = min(256, self.players + 1)
                self.presence_observations += 1
        safe = filtered(raw)
        if not safe:
            return
        count = PLAYER_COUNT.search(safe)
        if count and not self.client:
            self.players = min(256, int(count[1] or count[2]))
            self.presence_observations += 1
        ready = READY_MODULE.search(safe)
        if ready and not self.client:
            module, enabled = ready.groups()
            if module not in self.modules and len(self.modules) >= 256:
                raise ValueError('module limit')
            self.modules[module] = enabled == 'true'
            if self.first_ready is None:
                self.first_ready = self.now
        tag = HC.search(safe) or re.search(r'\[HCX[^\]]*\]', safe)
        candidates = self.by_tag.get(tag[0], ()) if tag else ()
        if '[HollowCountry]' in safe:
            candidates = self.by_tag.get('[HollowCountry]', ())
        for state in candidates:
            entry = state['entry']
            # HCServer finishes OnStart before readiness is printed. Retain
            # startup receipts, but start observation windows at readiness.
            elapsed = 0.0
            if self.first_ready is not None:
                elapsed = self.elapsed(entry)
            match = state['pattern'].search(safe)
            if not match:
                continue
            try:
                values = [float(match[f]) for f in entry['signal']['fields']]
            except (ValueError, TypeError, OverflowError):
                continue
            if not all(number(v) for v in values):
                continue
            # Marker values (e.g. first_s=0) prove presence, not a count.
            # Otherwise sum fields and reduce samples as declared; cumulative
            # counters should use max, never sum.
            sample = 1.0 if entry['comparison'] == 'present' else sum(values)
            if not math.isfinite(sample):
                continue
            state['samples'] += 1
            if elapsed > entry['window_minutes'] * 60:
                continue
            if entry['comparison'] == 'sum':
                state['value'] = (state['value'] or 0) + sample
            elif entry['comparison'] in ('max', 'present'):
                state['value'] = max(state['value'] or 0, sample)
            else:
                state['value'] = sample
            if not math.isfinite(state['value']):
                raise ValueError('counter overflow')

    def elapsed(self, entry):
        if self.client:
            return self.now
        return self.player_seconds if entry['needs_player'] else self.now - self.first_ready

    def result(self):
        features = []
        declared = {e['module'] for e in self.entries}
        for state in self.states:
            entry = state['entry']
            if not self.modules.get(entry['module'], False):
                continue
            elapsed = self.elapsed(entry)
            status = 'WAITING'
            if entry['signal'] is None:
                status = 'NO_SIGNAL'
            elif state['value'] is not None and state['value'] >= entry['floor']:
                status = 'ACTIVE'
            elif elapsed >= entry['window_minutes'] * 60 and self.clock_lines > 1:
                status = 'INERT' if state['samples'] else 'SILENT'
            features.append(dict(module=entry['module'], feature=entry['feature'], status=status,
                                 value=state['value'], samples=state['samples'], floor=entry['floor'],
                                 window_minutes=entry['window_minutes'], elapsed_minutes=round(elapsed / 60, 3),
                                 needs_player=entry['needs_player'], scope=entry.get('scope', 'runtime')))
        for module, enabled in self.modules.items():
            if enabled and module not in declared:
                features.append(dict(module=module, feature='undeclared', status='NO_SIGNAL',
                                     value=None, samples=0, floor=None, window_minutes=None,
                                     elapsed_minutes=None, needs_player=False, scope='runtime'))
        features.sort(key=lambda row: (row['module'], row['feature']))
        totals = {status: 0 for status in STATUSES}
        totals.update(Counter(row['status'] for row in features))
        count = sum(totals[s] for s in ('INERT', 'SILENT', 'NO_SIGNAL'))
        return dict(features=features, totals=totals, activity='inert' if count else 'ok', count=count,
                    readiness_observed=bool(self.modules), clock_observed=self.clock_lines > 1,
                    player_presence_observations=self.presence_observations,
                    player_minutes=round(self.player_seconds / 60, 3), client_rpt_observed=False)


def scan(path, expectations=DEFAULT_EXPECTATIONS, *, client_rpt=None):
    activity = Activity(expectations)
    for raw in lines(path):
        activity.observe(raw)
    result = activity.result()
    if not result['readiness_observed']:
        raise ValueError('no readiness markers')
    if client_rpt is not None:
        client = Activity(expectations, client=True)
        # Only the server determines enabled modules. Client readiness, server
        # counters and player events cannot alter the authoritative audit.
        client.modules = dict(activity.modules)
        for raw in lines(client_rpt):
            client.observe(raw)
        if client.clock_lines < 2:
            raise ValueError('insufficient client timestamps')
        client_rows = {(row['module'], row['feature']): row
                       for row in client.result()['features'] if row['scope'] == 'client'}
        result['features'] = [client_rows.get((row['module'], row['feature']), row)
                              for row in result['features']]
        result['totals'] = {status: 0 for status in STATUSES}
        result['totals'].update(Counter(row['status'] for row in result['features']))
        result['count'] = sum(result['totals'][s] for s in ('INERT', 'SILENT', 'NO_SIGNAL'))
        result['activity'] = 'inert' if result['count'] else 'ok'
        result['client_minutes'] = round(client.now / 60, 3)
    result['client_rpt_observed'] = client_rpt is not None
    return result


def summary_line(result):
    return f"activity={result['activity']} count={result['count']}"


def print_result(result):
    for row in result['features']:
        value = 'none' if row['value'] is None else f"{row['value']:g}"
        print(f"{row['module']}/{row['feature']} {row['status']} value={value} samples={row['samples']} "
              f"floor={row['floor']} elapsed_minutes={row['elapsed_minutes']} window_minutes={row['window_minutes']} "
              f"needs_player={str(row['needs_player']).lower()} scope={row['scope']}")
    print('totals ' + ' '.join(f'{s}={result["totals"][s]}' for s in STATUSES))
    print(summary_line(result))


class InputParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default echoes arbitrary arguments, which may be private.
        self.exit(6, 'activity arguments unavailable or invalid\n')


def main(argv=None):
    parser = InputParser(description=__doc__)
    parser.add_argument('rpt', type=Path)
    parser.add_argument('--client-rpt', type=Path)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--expectations', type=Path, default=DEFAULT_EXPECTATIONS)
    args = parser.parse_args(argv)
    try:
        result = scan(args.rpt, args.expectations, client_rpt=args.client_rpt)
    except (OSError, ValueError, TypeError, KeyError, re.error):
        # Never echo a private filename, malformed RPT text or regex exception.
        if args.json:
            print(json.dumps(dict(error='activity input unavailable or invalid')))
        else:
            print('activity input unavailable or invalid')
        return 6
    print(json.dumps(result, allow_nan=False)) if args.json else print_result(result)
    return 8 if result['count'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
