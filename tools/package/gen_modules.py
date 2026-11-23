"""Module manifests (modules/*.module.json): validate against the Enforce code, generate MODULE_STATUS rows.

check (default): schema, then every manifest fact against the scripts (class, GetName, layer, registered
uses, shared saves, settings keys and defaults, dependency classes, readiness reasons), then the pilot rows
of docs/MODULE_STATUS.md (section 'R1 registered use features') against the rows generated from the manifests.
write: rewrites drifted pilot rows in that table (appends a missing row); nothing else is touched.
No Generated/ Enforce file is produced: the pilot modules need none. The code still owns s_LegacyUses and
RequiresSharedSaves; the manifest records them until a later migration moves them.
"""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
MODULES = Path('modules')
SCHEMA = MODULES / 'module.schema.json'
STATUS_DOC = Path('docs/MODULE_STATUS.md')
STATUS_SECTION = '## R1 registered use features'
READINESS = Path('mods/HollowCountry/scripts/4_World/Core/HCModuleReadiness.c')
MODULE_BASE = Path('mods/HollowCountry/scripts/4_World/Core/HCModule.c')
LAYERS = {'HC_PHASE_CORE': 'core', 'HC_PHASE_PROVIDER': 'provider', 'HC_PHASE_FEATURE': 'feature',
          'HC_PHASE_ADDON': 'addon'}
ENABLE_FLAG = re.compile(r'^Enable[A-Za-z0-9]+$')


class ManifestError(ValueError):
    """Failed expectations; each problem names the module and the fact."""

    def __init__(self, problems):
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        super().__init__('; '.join(self.problems))


def schema_errors(value, schema, path='$'):
    """Small Draft 2020-12 subset (type, enum, const, pattern, items, required, properties, additionalProperties,
    minItems, uniqueItems): the standard library only, as the offline CI lane requires."""
    types = {'object': dict, 'array': list, 'string': str, 'boolean': bool, 'integer': int, 'number': (int, float)}
    errors = []
    wanted = schema.get('type')
    if wanted:
        ok = isinstance(value, types[wanted]) and not (wanted in ('integer', 'number') and isinstance(value, bool))
        if not ok:
            return [f'{path}: expected {wanted}']
    if 'const' in schema and (value != schema['const'] or isinstance(value, bool) != isinstance(schema['const'], bool)):
        errors.append(f'{path}: must be {schema["const"]!r}')
    if 'enum' in schema and value not in schema['enum']:
        errors.append(f'{path}: must be one of {schema["enum"]}')
    if isinstance(value, str) and 'pattern' in schema and not re.search(schema['pattern'], value):
        errors.append(f'{path}: does not match {schema["pattern"]}')
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0):
            errors.append(f'{path}: needs at least {schema["minItems"]} item(s)')
        if schema.get('uniqueItems') and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            errors.append(f'{path}: items must be unique')
        for index, item in enumerate(value):
            errors += schema_errors(item, schema.get('items', {}), f'{path}[{index}]')
    if isinstance(value, dict):
        properties = schema.get('properties', {})
        for key in schema.get('required', ()):
            if key not in value:
                errors.append(f'{path}: missing {key}')
        for key, item in value.items():
            if key in properties:
                errors += schema_errors(item, properties[key], f'{path}.{key}')
            elif schema.get('additionalProperties') is False:
                errors.append(f'{path}: unknown field {key}')
    return errors


def load_manifests(root=ROOT):
    """Return (manifests sorted by name, errors). Each manifest gains no fields; the file path is the key."""
    schema = json.loads((root / SCHEMA).read_bytes())
    found, errors = [], []
    for path in sorted((root / MODULES).glob('*.module.json')):
        try:
            data = json.loads(path.read_bytes())
        except ValueError as exc:
            errors.append(f'{path.name}: invalid JSON: {exc}')
            continue
        problems = schema_errors(data, schema)
        if not problems and path.name != data['name'] + '.module.json':
            problems = [f'$.name: file name must be {data["name"]}.module.json']
        errors += [f'{path.name}: {p}' for p in problems]
        if not problems:
            found.append(data)
    names = [m['name'] for m in found]
    errors += [f'duplicate manifest for {n}' for n in sorted(set(names)) if names.count(n) > 1]
    return found, errors


def strip_comments(text):
    """Blank // and /* */ comments while keeping string literals and offsets."""
    out, i, n = [], 0, len(text)
    while i < n:
        two = text[i:i + 2]
        if text[i] == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == '\\' else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif two == '//':
            j = text.find('\n', i)
            j = n if j < 0 else j
            out.append(' ' * (j - i))
            i = j
        elif two == '/*':
            j = text.find('*/', i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r'[^\n]', ' ', text[i:j]))
            i = j
        else:
            out.append(text[i])
            i += 1
    return ''.join(out)


def matching_brace(text, start):
    """Index of the brace closing the one at text[start]; strings are skipped."""
    depth, i, n = 0, start, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == '\\' else 1
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ManifestError('unbalanced braces')


def class_body(code, class_name):
    match = re.search(r'^[ \t]*class\s+' + re.escape(class_name) + r'\s*(?::|extends)\s*HCModule\b[^{;]*\{', code, re.M)
    if not match:
        return None
    return code[match.end() - 1:matching_brace(code, match.end() - 1) + 1]


def method_body(body, signature):
    match = re.search(signature + r'\s*\{', body)
    if not match:
        return None
    return body[match.end() - 1:matching_brace(body, match.end() - 1) + 1]


class CodeFacts:
    """Facts read once from the scripts: registry rows, class names, legacy tables."""

    def __init__(self, root=ROOT):
        self.root = root
        self.sources = {}
        self.registry = {}
        self.classes = set()
        for path in sorted((root / 'mods').rglob('*.c')):
            code = strip_comments(path.read_text(errors='replace'))
            self.sources[path.relative_to(root)] = code
            self.classes.update(re.findall(r'^[ \t]*(?:modded\s+)?class\s+([A-Za-z_]\w*)', code, re.M))
            for key, kind, default in re.findall(r'HCAdd\(\s*"([^"]+)"\s*,\s*"(\w+)"\s*,\s*([^,]+),', code):
                self.registry.setdefault(key, (kind, default.strip()))
        self.legacy_uses = {}
        for name, features in re.findall(r's_LegacyUses\.Insert\(\s*"([^"]+)"\s*,\s*"([^"]*)"\s*\)',
                                         self.sources.get(READINESS, '')):
            self.legacy_uses[name] = [f for f in features.split(',') if f]
        owners = re.search(r's_HCLegacySaveOwners\s*=\s*\{([^}]*)\}', self.sources.get(MODULE_BASE, ''))
        self.legacy_save_owners = set(re.findall(r'"([^"]+)"', owners.group(1))) if owners else set()


def module_facts(manifest, facts):
    """Everything the code says about the manifest's module, or ManifestError when the class is unusable."""
    name = manifest['name']
    source = Path(manifest['source'])
    if source not in facts.sources:
        raise ManifestError(f'{name}: source {source} is not a script file')
    code = facts.sources[source]
    body = class_body(code, manifest['class'])
    if body is None:
        raise ManifestError(f'{name}: {source} does not define class {manifest["class"]} deriving from HCModule')
    result = {'code': code, 'body': body}
    got = re.search(r'string\s+GetName\s*\(\s*\)\s*\{\s*return\s+"([^"]*)"\s*;\s*\}', body)
    if not got:
        raise ManifestError(f'{name}: GetName() must return a string literal')
    result['name'] = got.group(1)
    phase = re.search(r'int\s+StartupPhase\s*\(\s*\)\s*\{\s*return\s+(HC_PHASE_\w+)\s*;', body)
    result['layer'] = LAYERS.get(phase.group(1)) if phase else 'feature'
    registration = re.compile(r'Register\(\s*new\s+' + re.escape(manifest['class']) + r'\s*\)')
    result['registered'] = any(registration.search(text) for text in facts.sources.values())
    uses = method_body(body, r'void\s+RegisterUses\s*\(\s*\)')
    if uses is None:
        result['uses_source'] = 'legacy_uses'
        result['uses'] = list(facts.legacy_uses.get(result['name'], []))
    else:
        result['uses_source'] = 'register_uses'
        calls = re.findall(r'HCRegisterUse\(\s*"([^"]*)"\s*,\s*"([^"]*)"', uses)
        result['uses'] = [feature for module, feature in calls if module == result['name']]
        result['foreign_uses'] = [m for m, _ in calls if m != result['name']]
        if 'super.RegisterUses' in uses:
            result['uses'] += facts.legacy_uses.get(result['name'], [])
    saves = method_body(body, r'bool\s+RequiresSharedSaves\s*\(\s*\)')
    if saves is not None:
        result['shared_saves'] = bool(re.search(r'return\s+true\s*;', saves))
    else:
        result['shared_saves'] = result['name'] in facts.legacy_save_owners
    return result


def verify_manifest(manifest, facts):
    name = manifest['name']
    errors = []
    try:
        seen = module_facts(manifest, facts)
    except ManifestError as exc:
        return [str(exc)]
    if seen['name'] != name:
        errors.append(f'{name}: GetName() returns {seen["name"]}')
    if not seen['registered']:
        errors.append(f'{name}: no Register(new {manifest["class"]}) in the scripts')
    if seen['layer'] != manifest['layer']:
        errors.append(f'{name}: layer is {seen["layer"]} in code, {manifest["layer"]} in manifest')
    if seen['uses_source'] != manifest['uses_source']:
        errors.append(f'{name}: uses_source is {seen["uses_source"]} in code, {manifest["uses_source"]} in manifest')
    if seen.get('foreign_uses'):
        errors.append(f'{name}: RegisterUses registers another module: {sorted(set(seen["foreign_uses"]))}')
    if sorted(seen['uses']) != sorted(manifest['uses']):
        errors.append(f'{name}: [HC Use] features are {seen["uses"]} in code, {manifest["uses"]} in manifest')
    if seen['shared_saves'] != manifest['requires_shared_saves']:
        errors.append(f'{name}: requires_shared_saves is {seen["shared_saves"]} in code')
    flags = []
    for key in manifest['settings']:
        row = facts.registry.get(key)
        if row is None:
            errors.append(f'{name}: settings key {key} is not in the settings registry')
            continue
        if ENABLE_FLAG.match(key):
            flags.append(key)
            if row[0] != 'bool':
                errors.append(f'{name}: {key} is not a bool registry key')
        if not re.search(r'\.' + re.escape(key) + r'\b|"' + re.escape(key) + '"', seen['code']):
            errors.append(f'{name}: settings key {key} is not read in {manifest["source"]}')
    expect_on = all(facts.registry.get(k, ('', '0'))[1] not in ('0', 'false') for k in flags)
    if manifest['default_on'] != expect_on:
        errors.append(f'{name}: default_on is {manifest["default_on"]} but the Enable flags default {expect_on}')
    for dependency in manifest['dependencies']:
        if dependency not in facts.classes:
            errors.append(f'{name}: dependency class {dependency} is not defined in the scripts')
    for reason in manifest['readiness_reasons']:
        if '"' + reason + '"' not in seen['code']:
            errors.append(f'{name}: readiness reason {reason} is not a string literal in {manifest["source"]}')
    return errors


def status_row(manifest):
    cell = ', '.join('`' + feature + '`' for feature in manifest['uses'])
    note = manifest.get('status_note', '')
    if note:
        cell += ' ' + note
    return '| ' + manifest['name'] + ' | ' + cell + ' |'


def table_span(lines):
    """(first, last) row indexes of the R1 use-feature table, or None."""
    try:
        head = lines.index(STATUS_SECTION)
    except ValueError:
        return None
    first = next((i for i in range(head, len(lines)) if lines[i].startswith('| Module | Feature names |')), None)
    if first is None:
        return None
    last = first
    while last + 1 < len(lines) and lines[last + 1].startswith('|'):
        last += 1
    return first, last


def render_status(text, manifests):
    """Return (new text, drifted module names). Rows are replaced in place; a missing row is appended."""
    lines = text.split('\n')
    span = table_span(lines)
    if span is None:
        raise ManifestError(f'{STATUS_DOC}: section "{STATUS_SECTION}" with its table not found')
    drift = []
    for manifest in manifests:
        row = status_row(manifest)
        first, last = table_span(lines)
        prefix = '| ' + manifest['name'] + ' | '
        index = next((i for i in range(first + 2, last + 1) if lines[i].startswith(prefix)), None)
        if index is None:
            lines.insert(last + 1, row)
            drift.append(manifest['name'])
        elif lines[index] != row:
            lines[index] = row
            drift.append(manifest['name'])
    return '\n'.join(lines), drift


def verified_manifests(root=ROOT):
    manifests, errors = load_manifests(root)
    if not manifests and not errors:
        errors.append('no module manifests found')
    if not errors:
        facts = CodeFacts(root)
        for manifest in manifests:
            errors += verify_manifest(manifest, facts)
    if errors:
        raise ManifestError(errors)
    return manifests


def check(root=ROOT):
    """Raise ManifestError (every problem listed) unless manifests, code and docs agree."""
    manifests = verified_manifests(root)
    _, drift = render_status((root / STATUS_DOC).read_text(), manifests)
    if drift:
        raise ManifestError([f'{STATUS_DOC}: row for {n} differs from the manifest (run gen_modules --write)'
                             for n in drift])
    return manifests


def write(root=ROOT):
    manifests = verified_manifests(root)
    path = root / STATUS_DOC
    text, drift = render_status(path.read_text(), manifests)
    if drift:
        path.write_text(text)
    return drift


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--check', action='store_true', help='validate manifests and rows (the default)')
    parser.add_argument('--write', action='store_true', help='rewrite drifted pilot rows in docs/MODULE_STATUS.md')
    args = parser.parse_args(argv)
    try:
        if args.write:
            drift = write()
            print('gen_modules: rewrote rows ' + (', '.join(drift) if drift else '(none: already current)'))
            return 0
        manifests = check()
    except ManifestError as exc:
        for problem in exc.problems:
            print('FAIL gen_modules ' + problem)
        return 1
    print(f'gen_modules: pass modules={len(manifests)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
