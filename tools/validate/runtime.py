"""Validate operator settings before native staging; never certify gameplay."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLAGS = {'EnableInteriors', 'EnableSearch', 'EnableCrafting', 'EnableInfected',
         'EnableHordes', 'EnableAlertChains', 'EnableGroups', 'EnableAtmosphere'}
# V2 preferences are optional so an existing V1 settings file stays valid; when present they must be booleans.
V2_FLAGS = {'EnableGrade', 'EnableAmbientLife', 'EnableSignsOfLife', 'EnableTravel', 'EnableWorld', 'EnableLeads',
            'EnableCamps', 'EnableEncounters',
            'EnableInfectedVariety', 'EnableDebugSnapshot', 'EnableAdminMap', 'EnableCampRespawn', 'EnableTeamPing', 'EnableVehicleFlip', 'EnableMealBuffs', 'EnableForage', 'EnableProgression', 'EnableGroupScaling'}
LIMITS = {'TickIntervalMs': (500, 10000), 'MaxTickWorkItems': (1, 256),
          'MaxActiveHordes': (1, 8), 'MaxActiveHordeMembers': (1, 64),
          'MaxActiveInteriors': (1, 32), 'MaxPropsPerInterior': (1, 20),
          'MaxFurnishedProps': (0, 2000), 'MaxBoundSearchSites': (1, 1024),
          'InfectedBindRadius': (5, 60), 'MaxBindQueriesPerTick': (1, 8)}

OPTIONAL_LIMITS = {'MaxFamiliarityRows': (0, 128)}

def validate_settings(value):
    if not isinstance(value, dict):
        return ['Settings must be a JSON object']
    expected = FLAGS | LIMITS.keys() | {'SchemaVersion'}
    errors = [f'Missing field {key}' for key in sorted(expected - value.keys())]
    errors += [f'Unknown field {key}' for key in sorted(value.keys() - expected - V2_FLAGS - {'AILimits', 'ClientPresentationMask'} - OPTIONAL_LIMITS.keys())]
    if 'ClientPresentationMask' in value:
        mask = value['ClientPresentationMask']
        if type(mask) is not int or not 0 <= mask <= 15:
            errors.append('ClientPresentationMask must be an integer within 0..15')
    if type(value.get('SchemaVersion')) is not int or value.get('SchemaVersion') != 1:
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
            ai_ranges = {
                'MaxLiveGroups': (1, 24),
                'MaxLiveAI': (1, 128),
                'OccupationMin': (1, 12),
                'OccupationMax': (1, 12),
                'HoldoutMin': (1, 12),
                'HoldoutMax': (1, 12),
                'PartyMin': (1, 12),
                'PartyMax': (1, 12),
                'PatrolMin': (1, 12),
                'PatrolMax': (1, 12),
                'CampMin': (1, 12),
                'CampMax': (1, 12),
                'MaxOccupiedPlaces': (1, 64),
                'MaxParties': (1, 128),
                'MaxMaterialized': (1, 24),
                'FactionStrengthMax': (1, 128),
                'MaxActiveSites': (1, 24),
                'MaxActiveAI': (1, 128),
                'MaxEncounters': (1, 24),
                'MaxObservedAI': (1, 8192),
                'MaxHoldouts': (24, 128),
                'MaxCamps': (1, 128),
                'MaxCampItems': (1, 128),
                'WorldSeed': (0, 1000003),
            }
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
        errors = validate_settings(json.loads(args.settings.read_text()))
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
    print(json.dumps({'status': 'fail' if errors else 'pass', 'errors': errors,
                      'scope': 'operator settings admission only'}, indent=2))
    return bool(errors)

if __name__ == '__main__':
    raise SystemExit(main())
