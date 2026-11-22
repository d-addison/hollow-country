"""Build the HC compat config addon: inheritance-only config entries for gaps we do not own.

Run before signing/bundling (not wired into release, friendcycle or the compile gate yet):
  python3 -B -m tools.package.compat_addon --out <new-dir> [--source]

Output in the new staging directory: hollowcountry_compat.pbo and compat-addon.json
(receipt, no machine paths). With --source the plain config.cpp / stringtable.csv are also
written under source/ for inspection. Generated output is never committed.

Inputs: compat_rules.json (rules), compat_strings.json via compat_stringtable.py, and an
optional compat_vehicles.json in the same rule schema. Every emitted class is
"class <Name>: <Parent> { <scalar and array properties> };" under an allow-listed Cfg*
section, with the parents forward-declared. Nothing of any dependency is copied, patched
or repacked: no class bodies, assets, scripts or text. The addon requires our own
HollowCountryExpansionAI patch plus the addons each rule names, so it loads after them.

Rule schema (schema 1), file-level keys: schema, addon, own_rules, dependency_rules.
  addon: {patch, prefix, pbo, required_addons[]}  required_addons must be our own patches.
  rule:  {id, section, class, parent, requires[], set{}, evidence}
         id        unique [A-Za-z0-9_-]; printed as a comment only
         section   one of SECTIONS
         parent    the class that already exists upstream; the rule inherits from it
         requires  addons (CfgPatches names) that define the parent; mandatory in dependency_rules
         set       {name: scalar | list}; "name[]" keys take lists; bool/null/nested rejected
         evidence  short non-emitted note (RPT category, audit id); mandatory in dependency_rules
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

from tools.package import compat_stringtable, pbo

ROOT = Path(__file__).resolve().parents[2]
RULES = Path(__file__).with_name('compat_rules.json')
OPTIONAL_RULES = (Path(__file__).with_name('compat_vehicles.json'),)
SCHEMA = 1
PBO_NAME = 'hollowcountry_compat.pbo'
PREFIX = 'HollowCountryExpansionAI\\compat'
PATCH = 'HollowCountryCompat'
SECTIONS = ('CfgVehicles', 'CfgWeapons', 'CfgMagazines', 'CfgAmmo', 'CfgNonAIVehicles')
IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,127}')
PROP = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}(\[\])?')
RULE_ID = re.compile(r'[A-Za-z0-9_-]{1,64}')
MAX_RULES = 4096
MAX_ARRAY = 256
MAX_STRING = 256
RULE_KEYS = {'id', 'section', 'class', 'parent', 'requires', 'set', 'evidence'}
FILE_KEYS = {'schema', 'addon', 'own_rules', 'dependency_rules'}


def _ident(value, what):
    if not isinstance(value, str) or not IDENT.fullmatch(value):
        raise ValueError(f'compat rules: invalid {what}')
    return value


def _scalar(value, what):
    if isinstance(value, bool) or value is None:
        raise ValueError(f'compat rules: {what}: only numbers and strings are allowed')
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f'compat rules: {what}: non-finite number')
        return repr(value)
    if isinstance(value, str):
        if len(value) > MAX_STRING or not all(32 <= ord(c) < 127 and c != '"' for c in value):
            raise ValueError(f'compat rules: {what}: string must be printable ASCII without quotes')
        return '"' + value + '"'
    raise ValueError(f'compat rules: {what}: unsupported value type')


def _property(name, value, rule_id):
    if not isinstance(name, str) or not PROP.fullmatch(name):
        raise ValueError(f'compat rules: {rule_id}: invalid property name')
    what = f'{rule_id}.{name}'
    if name.endswith('[]'):
        if not isinstance(value, list) or len(value) > MAX_ARRAY:
            raise ValueError(f'compat rules: {what}: array property needs a bounded list')
        return f'{name} = {{' + ', '.join(_scalar(item, what) for item in value) + '};'
    if isinstance(value, list):
        raise ValueError(f'compat rules: {what}: list needs a "[]" property name')
    return f'{name} = {_scalar(value, what)};'


def own_patches(root=ROOT):
    """CfgPatches class names declared by this repo's own mods/*/config.cpp files."""
    names = set()
    for config in sorted((Path(root) / 'mods').glob('*/config.cpp')):
        text = config.read_text(encoding='utf-8', errors='replace')
        match = re.search(r'\bclass\s+CfgPatches\s*\{', text)
        if not match:
            continue
        depth, start = 1, match.end()
        for index in range(start, len(text)):
            if text[index] == '{':
                depth += 1
            elif text[index] == '}':
                depth -= 1
                if depth == 0:
                    block = text[start:index]
                    break
        else:
            continue
        depth = 0
        for token in re.finditer(r'[{}]|\bclass\s+([A-Za-z_]\w*)', block):
            if token.group(0) == '{':
                depth += 1
            elif token.group(0) == '}':
                depth -= 1
            elif depth == 0:
                names.add(token.group(1))
    return names


def load_rules(paths=None, root=ROOT):
    """Validate rule files; return (addon block, rules list of dicts with a 'source' key)."""
    paths = [Path(p) for p in paths] if paths else [RULES] + [p for p in OPTIONAL_RULES if p.is_file()]
    addon, rules, ids, targets = None, [], set(), set()
    for path in paths:
        data = json.loads(path.read_bytes())
        if not isinstance(data, dict) or data.get('schema') != SCHEMA:
            raise ValueError('compat rules: unsupported schema')
        if not set(data) <= FILE_KEYS | {'_doc'}:
            raise ValueError('compat rules: unknown top-level key')
        block = data.get('addon')
        if block is not None:
            if addon is not None:
                raise ValueError('compat rules: addon block defined twice')
            addon = block
        for source, key in (('own', 'own_rules'), ('dependency', 'dependency_rules')):
            rows = data.get(key, [])
            if not isinstance(rows, list):
                raise ValueError(f'compat rules: {key} must be a list')
            for row in rows:
                rule = _check_rule(row, source)
                if rule['id'] in ids:
                    raise ValueError('compat rules: duplicate id ' + rule['id'])
                target = (rule['section'], rule['class'])
                if target in targets:
                    raise ValueError('compat rules: duplicate target class ' + rule['class'])
                ids.add(rule['id'])
                targets.add(target)
                rules.append(rule)
    if len(rules) > MAX_RULES:
        raise ValueError('compat rules: too many rules')
    addon = _check_addon(addon, root)
    return addon, rules


def _check_addon(block, root):
    if not isinstance(block, dict) or set(block) != {'patch', 'prefix', 'pbo', 'required_addons'}:
        raise ValueError('compat rules: addon block needs patch, prefix, pbo, required_addons')
    if block['patch'] != PATCH or block['prefix'] != PREFIX or block['pbo'] != PBO_NAME:
        raise ValueError('compat rules: addon identity differs from the generator contract')
    if PREFIX not in pbo.PREFIXES:
        raise ValueError('compat prefix is not a registered PBO prefix')
    required = block['required_addons']
    if (not isinstance(required, list) or not required
            or any(not isinstance(a, str) for a in required) or len(set(required)) != len(required)):
        raise ValueError('compat rules: required_addons must be a non-empty unique list')
    own = own_patches(root)
    for name in required:
        if name not in own:
            raise ValueError('compat rules: required_addons entry is not one of our own patches')
    return block


def _check_rule(row, source):
    if not isinstance(row, dict) or not set(row) <= RULE_KEYS:
        raise ValueError('compat rules: rule has unknown keys')
    rule_id = row.get('id')
    if not isinstance(rule_id, str) or not RULE_ID.fullmatch(rule_id):
        raise ValueError('compat rules: invalid rule id')
    if row.get('section') not in SECTIONS:
        raise ValueError(f'compat rules: {rule_id}: section not allowed')
    name, parent = _ident(row.get('class'), 'class'), _ident(row.get('parent'), 'parent')
    if name == parent:
        raise ValueError(f'compat rules: {rule_id}: class cannot inherit from itself')
    requires = row.get('requires', [])
    if (not isinstance(requires, list) or len(set(requires)) != len(requires)
            or any(not isinstance(a, str) or not IDENT.fullmatch(a) for a in requires)):
        raise ValueError(f'compat rules: {rule_id}: invalid requires')
    evidence = row.get('evidence', '')
    if not isinstance(evidence, str) or len(evidence) > 300:
        raise ValueError(f'compat rules: {rule_id}: invalid evidence')
    if source == 'dependency' and (not requires or not evidence.strip()):
        raise ValueError(f'compat rules: {rule_id}: dependency rules need requires and evidence')
    props = row.get('set', {})
    if not isinstance(props, dict):
        raise ValueError(f'compat rules: {rule_id}: set must be an object')
    lines = [_property(key, props[key], rule_id) for key in sorted(props)]
    return {'id': rule_id, 'section': row['section'], 'class': name, 'parent': parent,
            'requires': list(requires), 'lines': lines, 'source': source}


def _ordered(rules):
    """Rules of one section, parents defined by other rules first; reject cycles."""
    by_name = {rule['class']: rule for rule in rules}
    done, order, active = set(), [], set()

    def visit(rule):
        if rule['class'] in done:
            return
        if rule['class'] in active:
            raise ValueError('compat rules: inheritance cycle at ' + rule['class'])
        active.add(rule['class'])
        if rule['parent'] in by_name:
            visit(by_name[rule['parent']])
        active.discard(rule['class'])
        done.add(rule['class'])
        order.append(rule)

    for rule in sorted(rules, key=lambda r: (r['class'].casefold(), r['class'])):
        visit(rule)
    return order


def render_config(addon, rules):
    required = list(addon['required_addons'])
    for rule in rules:
        for name in rule['requires']:
            if name not in required:
                required.append(name)
    out = ['// Generated by tools/package/compat_addon.py; do not edit.',
           'class CfgPatches', '{', f'    class {PATCH}', '    {',
           '        units[] = {};', '        weapons[] = {};', '        requiredVersion = 0.1;',
           '        requiredAddons[] = {' + ', '.join(f'"{name}"' for name in required) + '};',
           '    };', '};']
    for section in SECTIONS:
        members = _ordered([rule for rule in rules if rule['section'] == section])
        if not members:
            continue
        defined = {rule['class'] for rule in members}
        out += [f'class {section}', '{']
        for parent in sorted({r['parent'] for r in members} - defined, key=str.casefold):
            out.append(f'    class {parent};')
        for rule in members:
            out.append(f'    // rule {rule["id"]}')
            if rule['lines']:
                out.append(f'    class {rule["class"]}: {rule["parent"]}')
                out.append('    {')
                out += ['        ' + line for line in rule['lines']]
                out.append('    };')
            else:
                out.append(f'    class {rule["class"]}: {rule["parent"]} {{}};')
        out.append('};')
    return ('\n'.join(out) + '\n').encode('ascii'), required


def generate(rule_paths=None, strings=compat_stringtable.STRINGS, root=ROOT):
    """Return (PBO bytes, source files dict, receipt)."""
    addon, rules = load_rules(rule_paths, root)
    config, required = render_config(addon, rules)
    table, keys = compat_stringtable.build(strings)
    files = {'config.cpp': config}
    if table is not None:
        files['stringtable.csv'] = table
    blob = pbo.pack(files, prefix=PREFIX)
    if pbo.parse(blob, prefixes=(PREFIX,)) != (PREFIX, files):
        raise ValueError('compat PBO roundtrip differs')
    receipt = {
        'status': 'generated', 'runtime': 'PENDING', 'pbo': PBO_NAME, 'prefix': PREFIX,
        'sha256': hashlib.sha256(blob).hexdigest(),
        'config_sha256': hashlib.sha256(config).hexdigest(),
        'requiredAddons': required,
        'rules': {'own': sum(r['source'] == 'own' for r in rules),
                  'dependency': sum(r['source'] == 'dependency' for r in rules)},
        'strings': len(keys),
        'native_compile': 'PENDING', 'one_server_one_client': 'PENDING',
    }
    return blob, files, receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--out', type=Path, required=True,
                        help='new staging directory; existing output is refused')
    parser.add_argument('--rules', type=Path, action='append',
                        help='rule file (repeatable); default compat_rules.json + compat_vehicles.json if present')
    parser.add_argument('--strings', type=Path, default=compat_stringtable.STRINGS)
    parser.add_argument('--source', action='store_true', help='also write plain config/stringtable under source/')
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.exit(1, 'compat_addon: output already exists; use fresh staging\n')
    try:
        blob, files, receipt = generate(args.rules, args.strings)
    except (OSError, ValueError) as error:
        # OSError text can carry account paths; never echo it.
        reason = str(error) if isinstance(error, ValueError) else 'input read failed'
        parser.exit(1, 'compat_addon: ' + reason + '\n')
    args.out.mkdir(parents=True)
    (args.out / PBO_NAME).write_bytes(blob)
    (args.out / 'compat-addon.json').write_text(json.dumps(receipt, indent=2) + '\n')
    if args.source:
        (args.out / 'source').mkdir()
        for name, data in files.items():
            (args.out / 'source' / name).write_bytes(data)
    print('compat_addon: generated rules={own}+{dependency} strings={strings} runtime=PENDING'.format(
        strings=receipt['strings'], **receipt['rules']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
