"""Validate operator settings before native staging; never certify gameplay."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLAGS = {'EnableInteriors', 'EnableSearch', 'EnableCrafting', 'EnableInfected',
         'EnableHordes', 'EnableAlertChains', 'EnableGroups', 'EnableAtmosphere'}
# Bounds/default metadata come from the shared authoring registry. Native
# HCSettings reads the compiled mirror, checked by the same validate entry point.
from tools.validate.settings_consistency import load_registry, check_consistency
RULES = {row['key']: row for row in load_registry()}
V2_FLAGS = {key for key,row in RULES.items() if row['type'] == 'bool'} - FLAGS
LIMITS = {key: (row['min'], row['max']) for key,row in RULES.items()
          if row['type'] == 'int' and '.' not in key
          and key not in {'SchemaVersion', 'ClientPresentationMask', 'MaxFamiliarityRows'}}
OPTIONAL_LIMITS = {'MaxFamiliarityRows': (RULES['MaxFamiliarityRows']['min'], RULES['MaxFamiliarityRows']['max'])}


def validate_settings(value):
    if not isinstance(value, dict):
        return ['Settings must be a JSON object']
    expected = FLAGS | LIMITS.keys() | {'SchemaVersion'}
    errors = [f'Missing field {key}' for key in sorted(expected - value.keys())]
    errors += [f'Unknown field {key}' for key in sorted(value.keys() - expected - V2_FLAGS - {'AILimits', 'ClientPresentationMask'} - OPTIONAL_LIMITS.keys() - {'SearchDensityScale'})]
    if 'ClientPresentationMask' in value:
        mask = value['ClientPresentationMask']
        if type(mask) is not int or not RULES['ClientPresentationMask']['min'] <= mask <= RULES['ClientPresentationMask']['max']:
            errors.append('ClientPresentationMask must be an integer within 0..15')
    if type(value.get('SchemaVersion')) is not int or value.get('SchemaVersion') != RULES['SchemaVersion']['default']:
        errors.append('Unsupported SchemaVersion')
    for key in sorted(FLAGS):
        if type(value.get(key)) is not bool:
            errors.append(f'{key} must be boolean')
    for key in sorted(V2_FLAGS & value.keys()):
        if type(value[key]) is not bool:
            errors.append(f'{key} must be boolean')
    for key, (low, high) in LIMITS.items():
        if type(value.get(key)) is not int or not low <= value[key] <= high:
            errors.append(f'{key} must be an integer within {low}..{high}')
    if 'AILimits' in value:
        ai = value['AILimits']
        if not isinstance(ai, dict):
            errors.append('AILimits must be an object')
        else:
            # Match the runtime key-specific fallback policy. CLI validation
            # reports invalid input before staging; the server logs/defaults it.
            ai_ranges = {key.removeprefix('AILimits.'): (row['min'], row['max'])
                         for key,row in RULES.items() if key.startswith('AILimits.')}
            for key in ai.keys() - ai_ranges.keys():
                errors.append(f'Unknown field AILimits.{key}')
            for key, item in ai.items():
                if key in ai_ranges:
                    low, high = ai_ranges[key]
                    if type(item) is not int or not low <= item <= high:
                        errors.append(f'AILimits.{key} must be an integer within {low}..{high}')
            for kind in ('Occupation', 'Holdout', 'Party', 'Patrol', 'Camp'):
                low, high = ai.get(kind + 'Min'), ai.get(kind + 'Max')
                if type(low) is int and type(high) is int and low > high:
                    errors.append(f'AILimits.{kind}Min must not exceed {kind}Max')
    for key, (low, high) in OPTIONAL_LIMITS.items():
        if key in value and (type(value[key]) is not int or not low <= value[key] <= high):
            errors.append(f'{key} must be an integer within {low}..{high}')
    if 'SearchDensityScale' in value:
        scale = value['SearchDensityScale']
        rule = RULES['SearchDensityScale']
        if type(scale) not in (int, float) or not (scale == 0 or rule['min'] <= scale <= rule['max']):
            errors.append('SearchDensityScale must be 0 (1.0) or a number within 0.5..2.0; native fallback=0')
    for child, parent in [('EnableSearch', 'EnableInteriors'),
                          ('EnableHordes', 'EnableInfected'),
                          ('EnableAlertChains', 'EnableInfected')]:
        if value.get(child) is True and value.get(parent) is not True:
            errors.append(f'{child} requires {parent}')
    return errors

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('settings', type=Path, nargs='?', default=ROOT/'config/hollow-country-settings.json')
    args = parser.parse_args()
    try:
        errors = check_consistency() + validate_settings(json.loads(args.settings.read_text()))
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
    print(json.dumps({'status': 'fail' if errors else 'pass', 'errors': errors,
                      'scope': 'operator settings admission only'}, indent=2))
    return bool(errors)

if __name__ == '__main__':
    raise SystemExit(main())
