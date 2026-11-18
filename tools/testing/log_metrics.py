"""Read-only W5 #50 log extraction; JSON on stdout, never an acceptance verdict.

Reuses perf_capture.parse_line for HCPerfSampler.c's calibrated [HC Perf] format.
Also retains [HollowCountry] perf/feature diagnostics. No engine API is called.
Work is linear in input bytes, bounded to 256 MiB/file and 10,000 samples/kind.
Error counts are matching lines per input, not deduplicated exception incidents.
"""
import argparse
import json
import math
from pathlib import Path
import re
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.testing import perf_capture

MAX_RECORDS = 10000
MAX_LINE = 65536
NUMBER = r'(\d+(?:\.\d+)?)(?![\w.])'
FPS = re.compile(r'\b(?:average\s+server\s+fps|server\s*fps|fps)\s*[:=]\s*' + NUMBER, re.I)
SERVER_FPS = re.compile(r'\b(?:average\s+server\s+fps|server\s*fps)\s*[:=]\s*' + NUMBER, re.I)
COUNTS = re.compile(r'\b(players|infected|zombies|animals|entities|ai_bodies|hordes|ai)\s*[:=]\s*(\d+)\b(?!\.)', re.I)
HC = re.compile(r'\[HollowCountry\]|\[HC(?:\s+[^\]]+)?\]')
ADMISSION = re.compile(r'(?:V2 admission|HCV2Admission)\b')
CLOCK = re.compile(r'\b\d{1,2}:\d{2}:\d{2}(?:\.\d+)?\b')


def redact(text):
    """Drop home-path tails (spaces included) and common Steam/account identifiers."""
    text = re.sub(r'(?i)(?:[a-z]:[\\/]users[\\/]|/(?:home|users)/|/root(?:/|\b)|'
                  r'/mnt/[a-z]/users/|~[\\/]|%userprofile%|'
                  + re.escape(str(Path.home())) + r').*', '[home-path-redacted]', text)
    text = re.sub(r'(?i)\bSTEAM_\d:[01]:\d+|\[U:\d+:\d+\]|(?<!\d)\d{17}(?!\d)|\b[a-f0-9]{32,64}\b',
                  '[id-redacted]', text)
    text = re.sub(r'(?i)\b(steam(?:id|id64)?|playerid|identity|uid|guid)\s*[:=]\s*\S+',
                  r'\1=[id-redacted]', text)
    return ''.join(char if char.isprintable() else ' ' for char in text)


def _append(report, key, record, limit=MAX_RECORDS):
    if len(report[key]) < limit:
        report[key].append(record)
    else:
        report['truncated'] = True


def collect(script_log, rpt):
    if Path(script_log).resolve() == Path(rpt).resolve():
        raise ValueError('script log and RPT must be different files')
    report = dict(schema=1, runtime_acceptance='pending', truncated=False,
                  fps_samples=[], perf_windows=[], entity_samples=[], module_max_ms={},
                  admissions=[], feature_summaries=[], filtered_animation_lines=0,
                  malformed_perf_lines=0, errors={'script_e': 0, 'vm_exception': 0}, sources={})
    for source, path in (('script', script_log), ('rpt', rpt)):
        if Path(path).stat().st_size > perf_capture.MAX_FILE_BYTES:
            raise ValueError('input exceeds 256 MiB limit')
        errors = {'script_e': 0, 'vm_exception': 0}
        report['sources'][source] = errors
        with Path(path).open(encoding='utf-8-sig', errors='replace') as stream:
            line_number = 0
            while True:
                raw = stream.readline(MAX_LINE + 1)
                if not raw:
                    break
                line_number += 1
                if len(raw) > MAX_LINE:
                    raise ValueError('input line exceeds 65536 characters')
                if 'TWO ANIMATION MODS' in raw.upper():
                    report['filtered_animation_lines'] += 1
                    continue
                if re.search(r'\bSCRIPT\s*\(E\)', raw, re.I):
                    errors['script_e'] += 1
                if re.search(r'\bVM\s+exception\b', raw, re.I):
                    errors['vm_exception'] += 1
                location = {'source': source, 'line': line_number}
                clock = CLOCK.search(raw)
                if clock:
                    location['time'] = clock.group()
                counts = {name.lower(): int(value) for name, value in COUNTS.findall(raw) if int(value) <= 1000000}
                if 'zombies' in counts:
                    counts['infected'] = counts.pop('zombies')
                fps = SERVER_FPS.search(raw)
                if fps is None and source == 'rpt' and not re.search(r'\bclient\s*fps\b', raw, re.I):
                    fps = FPS.search(raw)
                if fps and math.isfinite(float(fps[1])) and float(fps[1]) <= 1000000:
                    sample = dict(location, fps=float(fps[1]))
                    if 'players' in counts:
                        sample['players'] = counts['players']
                    _append(report, 'fps_samples', sample)
                if counts:
                    scope = 'feature'
                    if fps and source == 'rpt' and not HC.search(raw):
                        scope = 'monitor'
                    _append(report, 'entity_samples', dict(location, counts=counts, scope=scope))
                # Redaction before parse also prevents arbitrary mod_max names leaking IDs.
                safe = redact(raw)
                try:
                    window = perf_capture.parse_line(safe)
                except ValueError:
                    report['malformed_perf_lines'] += 1
                    window = None
                if window is not None:
                    _append(report, 'perf_windows', dict(location, **window))
                    for name, value in window.get('mod_max', {}).items():
                        report['module_max_ms'][name] = max(report['module_max_ms'].get(name, 0), value)
                marker = HC.search(safe)
                if marker and window is None:
                    record = dict(location, text=safe[marker.start():][:2000])
                    if ADMISSION.search(safe):
                        _append(report, 'admissions', record, 1024)
                    else:
                        _append(report, 'feature_summaries', record, 512)
        for key, count in errors.items():
            report['errors'][key] += count
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script-log', required=True, type=Path)
    parser.add_argument('--rpt', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = collect(args.script_log, args.rpt)
    except (OSError, ValueError, OverflowError):
        print('log_metrics: unreadable or invalid input; check both local files and size limits', file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
