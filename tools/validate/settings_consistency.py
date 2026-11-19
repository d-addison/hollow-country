"""Check the operator registry, compiled native mirror and shipped defaults.

Standard library only. This is source admission, never DayZ runtime evidence.
The JSON is the authoring registry; HCSettings consumes its checked compiled
mirror so startup does not depend on an extra mission file or file IO.
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / 'tools/validate/shared_settings.json'
NATIVE = ROOT / 'mods/HollowCountry/scripts/3_Game/HCSettings.c'
AI_NATIVE = ROOT / 'mods/HollowCountry/scripts/3_Game/World/HCAILimits.c'
PERF_NATIVE = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCPerfSlices.c'
PERF_REGISTRY = ROOT / 'mods/HollowCountry/scripts/3_Game/HCPerfSettingsRegistry.c'
HEARTH_NATIVE = ROOT / 'mods/HollowCountry/scripts/4_World/Atmosphere/HCHearthFires.c'
HEARTH_REGISTRY = ROOT / 'mods/HollowCountry/scripts/3_Game/Atmosphere/HCHearthSettingsRegistry.c'
SHIPPED = (ROOT / 'config/hollow-country-settings.json',
           ROOT / 'mission/hollow-country/operator/settings.json')


def load_registry(*, include_scoped=False):
    """Main settings consumers exclude optional profile-file scopes by default."""
    rows = json.loads(REGISTRY.read_text())
    return rows if include_scoped else [r for r in rows if not r['key'].startswith(('Performance.', 'HearthFires.'))]


def check_performance(rows, source, registry):
    """Optional performance.json has no shipped image; check its constructor."""
    errors = []
    source = re.sub(r'//[^\n]*', '', source)
    registry = re.sub(r'//[^\n]*', '', registry)
    dto = source.split('class HCPerfConfig\n', 1)[-1].split('class HCPerfSlices', 1)[0]
    fields = {key: (kind, json.loads(value)) for kind, key, value in re.findall(
        r'^    (bool|int|float) (\w+) = ([\w.]+);', dto, re.M)}
    rules = {r['key'].removeprefix('Performance.'): r for r in rows}
    if fields.keys() != rules.keys(): errors.append('Performance registry/native key set differs')
    compiled = re.findall(r'^        HCAdd\([^\n]+;', registry, re.M)
    expected = render_native_registry(rows).splitlines()
    if compiled != expected: errors.append('Performance compiled registry differs (key/type/default/range/owner)')
    for key, row in rules.items():
        if row['owner'] != 'HCPerfConfig' or fields.get(key) != (row['type'], row['default']):
            errors.append(f'Performance DTO default/type/owner differs for {key}')
        guard = f'HCJsonFields.Has(text, "{key}")'
        if row['type'] != 'bool':
            guard += f' && HCOperatorSettingsRegistry.HCValid("Performance.{key}", decoded.{key})'
        binding = f'if ({guard}) {{ {key} = decoded.{key}; }}'
        if binding not in dto: errors.append(f'Performance apply binding differs for {key}')
        if re.search(r'\b' + key + r'\s*[<>]=?\s*[\d.]', dto):
            errors.append(f'Performance literal range bypasses registry for {key}')
    return errors


def check_hearth(rows, source, registry):
    """Optional hearth-fires.json has no shipped image; check its constructor."""
    errors = []
    source = re.sub(r'//[^\n]*', '', source)
    registry = re.sub(r'//[^\n]*', '', registry)
    dto = source.split('class HCHearthConfig\n', 1)[-1].split('class HCHearthRecord', 1)[0]
    fields = {key: (kind, json.loads(value)) for kind, key, value in re.findall(
        r'^    (bool|int|float) (\w+) = ([\w.]+);', dto, re.M)}
    rules = {r['key'].removeprefix('HearthFires.'): r for r in rows}
    if fields.keys() != rules.keys(): errors.append('HearthFires registry/native key set differs')
    compiled = re.findall(r'^        HCAdd\([^\n]+;', registry, re.M)
    expected = render_native_registry(rows).splitlines()
    if compiled != expected: errors.append('HearthFires compiled registry differs (key/type/default/range/owner)')
    for key, row in rules.items():
        if row['owner'] != 'HCHearthConfig' or fields.get(key) != (row['type'], row['default']):
            errors.append(f'HearthFires DTO default/type/owner differs for {key}')
        guard = f'HCJsonFields.Has(text, "{key}")'
        if row['type'] != 'bool':
            guard += f' && HCOperatorSettingsRegistry.HCValid("HearthFires.{key}", decoded.{key})'
        binding = f'if ({guard}) {{ {key} = decoded.{key}; }}'
        if binding not in dto: errors.append(f'HearthFires apply binding differs for {key}')
        if re.search(r'\b' + key + r'\s*[<>]=?\s*[\d.]', dto):
            errors.append(f'HearthFires literal range bypasses registry for {key}')
    return errors


def flatten(value, prefix=''):
    result = {}
    for key, item in value.items():
        name = prefix + key
        result[name] = item
        if isinstance(item, dict):
            result.update(flatten(item, name + '.'))
    return result


def render_native_registry(rows):
    lines = []
    for row in rows:
        default = row['default']
        if row['type'] == 'object': default = 0
        if row['type'] == 'bool': default = int(default)
        lines.append('        HCAdd("{key}", "{type}", {default}, {low}, {high}, "{owner}");'.format(
            **{key: row[key] for key in ('key', 'type', 'owner')}, default=default,
            low=row['min'] or 0, high=row['max'] or 0))
    return '\n'.join(lines)


# Owner -> (source, registry key prefix, DTO accessor used in validation bindings).
EXTERNAL_OWNERS = {
    'HCW38SituationPolicy': ('mods/HollowCountry/scripts/4_World/Events/HCW38SituationPolicy.c', 'W38Situations', 'policy.'),
    'HCTheftConfig': ('mods/HollowCountry/scripts/4_World/Camps/HCCampTheft.c', 'CampTheft', 'config.'),
    'HCBaseRaidConfig': ('mods/HollowCountry/scripts/4_World/Camps/HCBaseRaid.c', 'BaseRaid', 'config.'),
    'HCConvoyPolicy': ('mods/HollowCountry/scripts/4_World/Events/HCConvoyPolicy.c', 'Convoys', 'policy.'),
}


def check_external_owner(rules, owner, path, prefix, var):
    """Defaults, registry bindings and literal fallback bounds of one external DTO."""
    errors = []
    source = path.read_text()
    dto = source.split('class ' + owner + '\n', 1)[-1]
    defaults = {key: (kind, json.loads(value)) for kind, key, value in re.findall(
        r'^    (int|float) (\w+) = ([\d.]+);', dto, re.M)}
    owned = {key.removeprefix(prefix + '.'): row for key, row in rules.items() if row['owner'] == owner}
    if set(defaults) != set(owned):
        errors.append(f'{prefix} registry/native key set differs')
    for key, row in owned.items():
        if defaults.get(key) != (row['type'], row['default']):
            errors.append(f'{prefix} default/type differs for {key}')
        binding = f'HCOperatorSettingsRegistry.HCValid("{prefix}.{key}", {var}{key})'
        if binding not in source:
            errors.append(f'{prefix} validation binding differs for {key}')
        if row['min'] == row['max']:
            bounds = [f"{var}{key} != {row['min']}"]
        else:
            bounds = [f"{var}{key} < {row['min']}", f"{var}{key} > {row['max']}"]
        if any(bound not in source for bound in bounds):
            errors.append(f'{prefix} fallback bounds differ for {key}')
    return errors



def check_consistency(*, registry=None, shipped=None, native=None, perf_native=None, perf_registry=None):
    """Optional inputs are explicit synthetic mutation seams for the same check."""
    rows = load_registry(include_scoped=True) if registry is None else registry
    source = NATIVE.read_text() if native is None else native
    errors, rules = [], {}
    for row in rows:
        if set(row) != {'key', 'type', 'default', 'min', 'max', 'owner'}:
            errors.append('Registry row must contain key/type/default/min/max/owner')
            continue
        key = row['key']
        if key in rules: errors.append(f'Duplicate registry key {key}')
        rules[key] = row
        if not row['owner']: errors.append(f'Missing owner {key}')
        kind = row['type']
        allowed = {'bool': (bool,), 'int': (int,), 'float': (int, float), 'object': (dict,)}
        if kind not in allowed or type(row['default']) not in allowed[kind]:
            errors.append(f'Registry default type differs for {key}')
        if kind != 'object':
            low, high = row['min'], row['max']
            if type(low) not in (int, float) or type(high) not in (int, float) or low > high:
                errors.append(f'Invalid registry range {key}')
            elif key != 'SearchDensityScale' and not low <= row['default'] <= high:
                errors.append(f'Registry default outside range {key}')
    if errors: return errors
    hearth_rows = [r for r in rows if r['key'].startswith('HearthFires.')]
    errors.extend(check_hearth(hearth_rows, HEARTH_NATIVE.read_text(), HEARTH_REGISTRY.read_text()))
    perf_rows = [r for r in rows if r['key'].startswith('Performance.')]
    errors.extend(check_performance(perf_rows,
        PERF_NATIVE.read_text() if perf_native is None else perf_native,
        PERF_REGISTRY.read_text() if perf_registry is None else perf_registry))
    rows = [r for r in rows if not r['key'].startswith(('Performance.', 'HearthFires.'))]
    rules = {r['key']: r for r in rows}
    images = [('<synthetic shipped settings>', shipped)] if shipped is not None else [
        (str(path.relative_to(ROOT)), json.loads(path.read_text())) for path in SHIPPED]
    shipped_rules = {k: row for k, row in rules.items()
                     if row['owner'] not in EXTERNAL_OWNERS and not k.startswith('WildlifeProviders.')}
    for label, image in images:
        values = flatten(image)
        for key in sorted(values.keys() - shipped_rules.keys()): errors.append(f'{label}: unregistered key {key}')
        for key in sorted(shipped_rules.keys() - values.keys()): errors.append(f'{label}: missing key {key}')
        for key in values.keys() & shipped_rules.keys():
            default = rules[key]['default']
            if values[key] != default or type(values[key]) is not type(default):
                errors.append(f'{label}: default differs for {key}')
    block = re.search(r'// BEGIN GENERATED SETTINGS REGISTRY\n(.*?)\n        // END GENERATED SETTINGS REGISTRY', source, re.S)
    if block is None or block[1] != render_native_registry(rows):
        errors.append('Compiled settings registry differs (key/type/default/range/owner)')
    dto = source.split('class HCSettings\n', 1)[-1]
    fields = {key: (kind, json.loads(value)) for kind, key, value in re.findall(
        r'^    (bool|int|float) (\w+) = ([\w.]+);', dto, re.M)}
    top_rules = {key: row for key, row in rules.items() if '.' not in key and row['type'] != 'object'}
    for key in fields.keys() - top_rules.keys(): errors.append(f'Unregistered native field {key}')
    for key, row in top_rules.items():
        if fields.get(key) != (row['type'], row['default']):
            errors.append(f'Native DTO default/type differs for {key}')
        if row['type'] in ('int', 'float'):
            binding = f'HCOperatorSettingsRegistry.HCValid("{key}", {key})'
            if binding not in dto: errors.append(f'Native validation binding differs for {key}')
            if re.search(r'\b' + key + r'\s*[<>]=?\s*[\d.]', dto):
                errors.append(f'Native literal range bypasses registry for {key}')
    # AILimits keeps its owner and key-specific native clamp policy. Check its
    # defaults/bounds against the same registry without editing that owner.
    ai = AI_NATIVE.read_text()
    ai_defaults = {k: int(v) for k,v in re.findall(r'^    int (\w+) = (\d+);', ai, re.M)}
    ai_ranges = {k: (int(a), int(b)) for k,a,b in re.findall(
        r'HCAILimits.Value\("(\w+)", \w+, (\d+), (\d+)\)', ai)}
    nested = {k.removeprefix('AILimits.'): v for k,v in rules.items() if k.startswith('AILimits.')}
    if set(nested) != set(ai_defaults) or set(nested) != set(ai_ranges):
        errors.append('AILimits registry/native key set differs')
    for key, row in nested.items():
        if ai_defaults.get(key) != row['default'] or ai_ranges.get(key) != (row['min'], row['max']):
            errors.append(f'AILimits default/range differs for {key}')
    # External owners use their own optional profile JSON, not HCSettings.
    for owner, (path, prefix, var) in EXTERNAL_OWNERS.items():
        errors.extend(check_external_owner(rules, owner, ROOT / path, prefix, var))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        errors = check_consistency()
    except (OSError, ValueError, TypeError) as exc:
        errors = [str(exc)]
    print(json.dumps({'status': 'fail' if errors else 'pass', 'errors': errors,
                      'scope': 'settings source consistency; runtime=PENDING'}, indent=2))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
