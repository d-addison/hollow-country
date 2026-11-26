"""Validate the V2 experiment register; a verdict needs a build, date, evidence and artifacts.

The register records what native sessions observed. It never runs an
experiment and never certifies gameplay: a GO or FALLBACK verdict is accepted
only when the entry names the game build, the observation date, the observed
evidence and at least one artifact (a local log or capture, named and hashed,
kept outside Git). Features read `qualified()`; anything else stays gated.
"""
import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.validate import dayz_build

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / 'docs/experiments/v2-experiments.json'
IDS = (
    'EXP-P1', 'EXP-P2', 'EXP-D1',
    'EXP-A1', 'EXP-A2', 'EXP-A3', 'EXP-A4', 'EXP-A5',
    'EXP-T1', 'EXP-T2', 'EXP-T3', 'EXP-T4', 'EXP-T5',
    'EXP-S1', 'EXP-S2', 'EXP-S3', 'EXP-S4',
    'EXP-L1', 'EXP-L2', 'EXP-L3', 'EXP-L4', 'EXP-L5', 'EXP-L6', 'EXP-L7', 'EXP-L8', 'EXP-L9',
    'EXP-POL-1', 'EXP-POL-2',
)
VERDICTS = ('PENDING', 'GO', 'FALLBACK', 'NO-GO')
QUALIFYING = ('GO', 'FALLBACK')
TEXT_FIELDS = ('Question', 'Method', 'Required', 'Fallback')
RECORD_FIELDS = ('Build', 'Date', 'Evidence', 'Artifacts')
FIELDS = {'Id', 'Verdict', *TEXT_FIELDS, *RECORD_FIELDS}
BUILD = re.compile(r'\d+\.\d+\.\d+(\.\d+)?')
DATE = re.compile(r'\d{4}-\d{2}-\d{2}')
MAX_BYTES = 256 * 1024


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _entry_errors(entry):
    if not isinstance(entry, dict):
        return ['experiment entry must be an object']
    name = entry.get('Id') if isinstance(entry.get('Id'), str) else '?'
    errors = [f'{name}: unknown field {key}' for key in sorted(entry.keys() - FIELDS)]
    errors += [f'{name}: missing field {key}' for key in sorted(FIELDS - entry.keys())]
    if name not in IDS:
        errors.append(f'{name}: unknown experiment id')
    for key in TEXT_FIELDS:
        if key in entry and not _text(entry[key]):
            errors.append(f'{name}: {key} must be non-empty text')
    verdict = entry.get('Verdict')
    if verdict not in VERDICTS:
        errors.append(f'{name}: Verdict must be one of {"/".join(VERDICTS)}')
        return errors
    artifacts = entry.get('Artifacts')
    if not isinstance(artifacts, list) or not all(_text(a) for a in artifacts):
        errors.append(f'{name}: Artifacts must be a list of non-empty text')
        artifacts = []
    if verdict == 'PENDING':
        recorded = [k for k in ('Build', 'Date', 'Evidence') if entry.get(k) != ''] + (['Artifacts'] if artifacts else [])
        if recorded:
            errors.append(f'{name}: PENDING entry records {", ".join(recorded)}; record a verdict or clear them')
        return errors
    if not isinstance(entry.get('Build'), str) or not BUILD.fullmatch(entry['Build']):
        errors.append(f'{name}: a {verdict} verdict needs the game Build (for example {dayz_build.pinned()})')
    if not isinstance(entry.get('Date'), str) or not DATE.fullmatch(entry['Date']):
        errors.append(f'{name}: a {verdict} verdict needs the observation Date (YYYY-MM-DD)')
    if not _text(entry.get('Evidence')):
        errors.append(f'{name}: a {verdict} verdict needs the observed Evidence')
    if not artifacts:
        errors.append(f'{name}: a {verdict} verdict needs at least one Artifacts entry')
    return errors


def validate(data):
    if not isinstance(data, dict):
        return ['register must be a JSON object']
    errors = [f'unknown register field {key}' for key in sorted(data.keys() - {'SchemaVersion', 'Experiments'})]
    if type(data.get('SchemaVersion')) is not int or data.get('SchemaVersion') != 1:
        errors.append('Unsupported SchemaVersion')
    entries = data.get('Experiments')
    if not isinstance(entries, list):
        return errors + ['Experiments must be a list']
    seen = []
    for entry in entries:
        errors += _entry_errors(entry)
        if isinstance(entry, dict):
            seen.append(entry.get('Id'))
    errors += [f'{i}: duplicate experiment id' for i in sorted({i for i in seen if seen.count(i) > 1}, key=str)]
    errors += [f'{i}: missing experiment' for i in IDS if i not in seen]
    return errors


def qualified(data, experiment_id):
    """True only for a GO or accepted FALLBACK verdict in a valid register."""
    if experiment_id not in IDS:
        raise KeyError(experiment_id)
    if validate(data):
        return False
    entry = next(e for e in data['Experiments'] if e['Id'] == experiment_id)
    return entry['Verdict'] in QUALIFYING


def load(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('register exceeds %d bytes' % MAX_BYTES)
    return json.loads(path.read_text(encoding='utf-8'))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Validate the V2 experiment register.')
    parser.add_argument('--register', type=Path, default=REGISTER)
    args = parser.parse_args(argv)
    try:
        data = load(args.register)
    except (OSError, ValueError) as error:
        print('experiment register refused: ' + type(error).__name__, file=sys.stderr)
        return 1
    errors = validate(data)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    counts = {v: sum(e['Verdict'] == v for e in data['Experiments']) for v in VERDICTS}
    print('experiments=%d pending=%d go=%d fallback=%d no-go=%d; the register records native verdicts, it never runs them'
          % (len(data['Experiments']), counts['PENDING'], counts['GO'], counts['FALLBACK'], counts['NO-GO']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
