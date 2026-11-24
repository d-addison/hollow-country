"""Streaming activity audit; readiness and runtime acceptance remain separate.

python3 -B -m tools.release.activity_check server.RPT [--client-rpt client.RPT] [--json]
Exit 0: ACTIVE/WAITING only (legacy), ACTIVE/WAIVED (release); 8: activity findings; 6: input error.
--release audits registered cumulative [HC Use] counters after the scenario window.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re

from tools.release.acceptance_targets import load_targets, TargetsError
from tools.release.rpt_summary import filtered, lines, HC
from tools.setup.server_report import _EVENT, _PLAYER_ENABLED

DEFAULT_EXPECTATIONS = Path(__file__).resolve().parents[2] / 'config/activity-expectations.json'
STATUSES = ('ACTIVE', 'INERT', 'SILENT', 'NO_SIGNAL', 'WAITING', 'NOT_APPLICABLE')
SCOPES = ('runtime', 'transport', 'client', 'diagnostic')
TOKEN = re.compile(r'[A-Za-z0-9_.-]{1,96}\Z')
CLOCK = re.compile(r'^\s*(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d+))?\b')
READY_MODULE = re.compile(r'\[HC Ready\]\s+module=([A-Za-z0-9_.-]+)\s+enabled=(true|false)\b')
# Only runtime counts: never configuration budgets such as [HC Config] players=16.
PLAYER_COUNT = re.compile(r'\[HC InfectedLOD\] stats .*\bplayers=(\d+)\b|\[HC Expansion AI\] group scale players=(\d+)\b')
PLAYER_EVENT = re.compile(r'\bplayer\b', re.I)
LEAVE = re.compile(r'\bdisconnected\b|\bkicked\b|\bbanned\b|\bhas left\b', re.I)
JOIN = re.compile(r'\bconnected\b|\bhas joined\b', re.I)


# Waivers are deliberately explicit and empty until an owner accepts a reason.
# Key: (module, feature); value: reason why the scenario cannot exercise it.
# A waiver remains visible as WAIVED and never counts as ACTIVE.
RELEASE_WAIVERS = {}
USE_LINE = re.compile(r'\[HC Use\] module=([A-Za-z0-9_.-]{1,64}) '
                      r'feature=([A-Za-z0-9_.-]{1,64}) count=([0-9]{1,10})(?=\s|$)')
FIXTURE_SUFFIX = re.compile(r' fixture=([0-9]{1,10})(?=\s|$)')
RELEASE_STATUSES = ('ACTIVE', 'INERT', 'WAIVED', 'NOT_APPLICABLE')
# World P1.3 navigation aggregates (HCModuleReadiness HCNav*): NavInf/NavXai have no
# [HC Ready] marker of their own, so each row is admitted through the owner modules that
# produce its member counters. Key: (aggregate module, feature); value: owner modules.
NAV_AGGREGATE_OWNERS = {
    ('NavInf', 'route_advance'): ('HordeMigration',),
    ('NavInf', 'pathgraph_refresh'): ('Interiors', 'Shelters'),
    ('NavInf', 'door_action'): ('InfectedDoors',),
    ('NavInf', 'vault_started'): ('InfectedReach',),
    ('NavXai', 'routes'): ('optional-expansion-human-ai',),
    ('NavXai', 'stuck_recovery'): ('optional-expansion-human-ai',),
}
NAV_AGGREGATE_MODULES = frozenset(module for module, _ in NAV_AGGREGATE_OWNERS)


class UseActivity:
    """Cumulative maxima from change-only checkpoints; zero lines register features.

    Readiness determines enabled modules on the server only. Registration and
    first use may precede readiness. Delta emission suppresses unchanged lines,
    but count remains cumulative: checkpoints must never be summed.
    The caller runs this audit at the end of the release scenario window.
    """
    def __init__(self, *, targets=None, entries=None):
        self.targets = load_targets() if targets is None else targets
        entries = load_expectations() if entries is None else entries
        self.client_smoke = {(entry['module'], entry['feature']) for entry in entries
                             if entry.get('release_smoke')}
        self.required_when = {(entry['module'], entry['feature']): entry['required_when']
                              for entry in entries if entry.get('conditional') == 'upgrade-only'}
        self.observed_conditions = set()
        self.modules = {}
        self.counts = {}
        self.fixtures = {}
        self.registry_count = None

    def observe(self, raw, *, client=False):
        safe = filtered(raw)
        if not safe:
            return
        if not client:
            for key, marker in self.required_when.items():
                if safe.strip().endswith(marker):
                    self.observed_conditions.add(key)
        ready = READY_MODULE.search(safe)
        if ready and not client:
            if ready[1] not in self.modules and len(self.modules) >= 256:
                raise ValueError('module limit')
            self.modules[ready[1]] = ready[2] == 'true'
        if '[HC UseRegistry]' in safe:
            match = re.search(r'\[HC UseRegistry\] registered=([0-9]{1,3})\s*$', safe)
            if not match or int(match[1]) > 512:
                raise ValueError('invalid use registry')
            if not client:
                self.registry_count = int(match[1])
            return
        if '[HC Use]' not in safe:
            return
        match = USE_LINE.search(safe)
        if not match:
            raise ValueError('invalid use counter')
        module, feature, value = match.groups()
        count = int(value)
        if count > 2147483647:
            raise ValueError('use counter overflow')
        suffix = safe[match.end():]
        fixture_match = FIXTURE_SUFFIX.search(suffix)
        fixture = int(fixture_match[1]) if fixture_match else 0
        if ' fixture=' in suffix and not fixture_match:
            raise ValueError('invalid fixture counter')
        if fixture > count:
            raise ValueError('fixture counter exceeds use count')
        key = (module, feature)
        if key not in self.counts and len(self.counts) >= 512:
            raise ValueError('feature limit')
        if key in self.client_smoke:
            # Server zero lines declare the feature; only play on the observed
            # client can satisfy it. These smoke counters have no fixture source.
            count = count if client and not fixture else 0
            fixture = 0
        self.counts[key] = max(self.counts.get(key, 0), count)
        self.fixtures[key] = max(self.fixtures.get(key, 0), fixture)

    def result(self):
        if not self.modules:
            raise ValueError('no readiness markers')
        features = []
        for (module, feature), count in sorted(self.counts.items()):
            # Server registration declares ClientUI, which has no HCModule slot.
            # Other unknown/disabled module counters cannot establish admission.
            if module in NAV_AGGREGATE_MODULES:
                owners = NAV_AGGREGATE_OWNERS.get((module, feature), ())
                if not any(self.modules.get(owner) for owner in owners):
                    continue
            elif not self.modules.get(module, module == 'ClientUI'):
                continue
            reason = RELEASE_WAIVERS.get((module, feature)) if count == 0 else None
            conditional_idle = ((module, feature) in self.required_when
                                and (module, feature) not in self.observed_conditions)
            status = ('ACTIVE' if count else 'NOT_APPLICABLE' if conditional_idle
                      else 'WAIVED' if reason else 'INERT')
            if conditional_idle and not count:
                reason = 'upgrade-only: no persisted retirement candidate observed'
            features.append(dict(module=module, feature=feature, count=count,
                                 status=status, reason=reason, fixture=self.fixtures.get((module, feature), 0)))
        registered = {row['module'] for row in features}
        # An aggregate row stands in for its owner modules' registration only when
        # the owner itself has a registered counter; it never hides an unregistered one.
        registered -= NAV_AGGREGATE_MODULES
        # An enabled owner with no registration must fail closed, even if an
        # older addon emits readiness but has not yet adopted the use API.
        for module, enabled in sorted(self.modules.items()):
            if enabled and module not in registered:
                features.append(dict(module=module, feature='unregistered', count=0,
                                     status='INERT', reason='no registered use counters'))
        features.sort(key=lambda row: (row['module'], row['feature']))
        totals = {status: 0 for status in RELEASE_STATUSES}
        totals.update(Counter(row['status'] for row in features))
        failures = totals['INERT'] if self.targets['activity_requires_active_for_default_on'] else 0
        return dict(features=features, totals=totals, count=failures,
                    activity='inert' if failures else 'waived' if totals['WAIVED'] else 'ok',
                    release=True, readiness_observed=True, registry_count=self.registry_count)


def scan_release(path, *, client_rpt=None, targets=None, entries=None):
    audit = UseActivity(targets=targets, entries=entries)
    for raw in lines(path):
        audit.observe(raw)
    if client_rpt is not None:
        for raw in lines(client_rpt):
            audit.observe(raw, client=True)
    result = audit.result()
    result['client_rpt_observed'] = client_rpt is not None
    return result


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def load_expectations(path=DEFAULT_EXPECTATIONS):
    return parse_expectations(Path(path).read_text(encoding='utf-8'))


def parse_expectations(text):
    """Validate before scanning; configuration is trusted local regex, never RPT code."""
    data = json.loads(text)
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
        if 'release_smoke' in entry and (entry['release_smoke'] is not True or entry.get('scope') != 'client'):
            raise ValueError('expectations release smoke scope')
        if 'conditional' in entry:
            if entry['conditional'] != 'upgrade-only':
                raise ValueError('expectations conditional')
            marker = entry.get('required_when')
            if (not isinstance(marker, str) or not marker.startswith('[HC ')
                    or len(marker) > 128 or not filtered(marker) or '\n' in marker):
                raise ValueError('expectations conditional marker')
        elif 'required_when' in entry:
            raise ValueError('expectations conditional marker without condition')
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
    def __init__(self, expectations=DEFAULT_EXPECTATIONS, *, client=False, entries=None):
        self.client = client
        self.entries = load_expectations(expectations) if entries is None else entries
        self.states = []
        self.by_tag = {}
        for entry in self.entries:
            state = dict(entry=entry, samples=0, value=None, condition_observed=False)
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
        if not self.client:
            for state in self.states:
                marker = state['entry'].get('required_when')
                if marker and safe.strip().endswith(marker):
                    state['condition_observed'] = True
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
            client_ui = entry['module'] == 'ClientUI' and entry.get('release_smoke')
            if not client_ui and not self.modules.get(entry['module'], False):
                continue
            elapsed = self.elapsed(entry)
            status = 'WAITING'
            if entry['signal'] is None:
                status = 'NO_SIGNAL'
            elif (entry.get('conditional') == 'upgrade-only' and not state['condition_observed']
                  and not state['value']):
                status = 'NOT_APPLICABLE'
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


def scan(path, expectations=DEFAULT_EXPECTATIONS, *, client_rpt=None, entries=None):
    activity = Activity(expectations, entries=entries)
    for raw in lines(path):
        activity.observe(raw)
    result = activity.result()
    if not result['readiness_observed']:
        raise ValueError('no readiness markers')
    if client_rpt is not None:
        client = Activity(client=True, entries=activity.entries)
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
    if result.get('release'):
        for row in result['features']:
            reason = f" reason={row['reason']}" if row['reason'] else ''
            fixture = f" fixture={row['fixture']}" if row.get('fixture') else ''
            print(f"{row['module']}/{row['feature']} {row['status']} count={row['count']}{fixture}{reason}")
        print('totals ' + ' '.join(f'{s}={result["totals"][s]}' for s in RELEASE_STATUSES))
        print(summary_line(result))
        return
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


def main(argv=None, *, targets=None, entries=None):
    parser = InputParser(description=__doc__)
    parser.add_argument('rpt', type=Path)
    parser.add_argument('--client-rpt', type=Path)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--release', action='store_true')
    parser.add_argument('--expectations', type=Path, default=DEFAULT_EXPECTATIONS)
    args = parser.parse_args(argv)
    try:
        if args.release:
            result = scan_release(args.rpt, client_rpt=args.client_rpt, targets=targets, entries=entries)
        else:
            result = scan(args.rpt, args.expectations, client_rpt=args.client_rpt, entries=entries)
    except TargetsError as error:
        print(json.dumps(dict(error=str(error))) if args.json else str(error))
        return 6
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
