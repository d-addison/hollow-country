"""Build the HC compat config addon: inheritance-only config entries for gaps we do not own.

Run before signing/bundling (release.py, compile_gate.py and friendcycle run it for you):
  python3 -B -m tools.package.compat_addon --out <new-dir> [--workshop <221100>] [--source]

Output in the new staging directory: hollowcountry_compat.pbo (the base PBO), one
hollowcountry_compat_<slot>.pbo per declared optional provider that has rules, and
compat-addon.json (receipt, no machine paths). With --source the plain config.cpp /
stringtable.csv are also written under source/ (providers under source/<slot>/) for
inspection. Generated output is never committed: the PBOs are built at bundle time.

Inputs: compat_rules.json (rules), compat_strings.json via compat_stringtable.py, and an
optional compat_vehicles.json in the same rule schema. Every emitted class is
"class <Name>: <Parent> { <scalar and array properties> };" under an allow-listed Cfg*
section, with the parents forward-declared. Nothing of any dependency is copied, patched
or repacked: no class bodies, assets, scripts or text. The addon requires our own
HollowCountryExpansionAI patch plus the addons each rule names, so it loads after them.

Optional dependencies. A `requires` entry that names a patch our own mods do not already
require (an optional pack) would stop the server booting where that pack is absent. So the
base PBO may require mandatory addons only (our own patches and what they require, minus the
release-injected inventory block). A rule needing an optional addon names a `provider` slot;
each slot becomes its own PBO and nested prefix, built only when the provider's Workshop item
is declared in tools/setup/workshop_mods.json (weapon_pack_guards.declared_item) and present
under --workshop. An undeclared provider emits no PBO (receipt status absent); a declared but
missing one refuses generation. Provider PBOs also require the base compat patch, so a parent
class may live in the base PBO but never in another provider's PBO.

Rule schema (schema 1), file-level keys: schema, addon, providers, own_rules, dependency_rules.
  addon: {patch, prefix, pbo, required_addons[]}  required_addons must be our own patches.
  providers: [{slot, item}]  slot is one of pbo.COMPAT_SLOTS, item the Workshop id
  rule:  {id, section, class, parent, requires[], provider, set{}, evidence}
         id        unique (case-insensitive) [A-Za-z0-9_-]; printed as a comment only
         section   one of SECTIONS
         class     unique per section, case-insensitive (the engine ignores class-name case)
         parent    the UPSTREAM base class: it must be the class the target already inherits
                   from where it is defined (or an upstream class the target may legally
                   re-parent to); a wrong parent makes the engine refuse the reopening. It is
                   never one of our own classes unless the rule is an own rule.
         requires  addons (CfgPatches names) that define the parent; mandatory in dependency_rules
         provider  optional slot for rules whose requires names a non-mandatory addon
         set       {name: scalar | list}; "name[]" keys take lists; names are unique
                   case-insensitively; ints are int32; floats carry no exponent; strings are
                   printable ASCII without quotes, // , /* , */ or #; bool/null/nested rejected
         evidence  short non-emitted note (RPT category, audit id); mandatory in dependency_rules
Every rendered file (config, stringtable, receipt) is run through inventory_sources.safe_text.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

from tools.package import compat_stringtable, inventory_sources, pbo, weapon_pack_guards

ROOT = Path(__file__).resolve().parents[2]
RULES = Path(__file__).with_name('compat_rules.json')
OPTIONAL_RULES = (Path(__file__).with_name('compat_vehicles.json'),)
SCHEMA = 1
PBO_NAME = 'hollowcountry_compat.pbo'
PREFIX = pbo.COMPAT_PREFIX
PATCH = 'HollowCountryCompat'
SECTIONS = ('CfgVehicles', 'CfgWeapons', 'CfgMagazines', 'CfgAmmo', 'CfgNonAIVehicles')
IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,127}')
PROP = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}(\[\])?')
RULE_ID = re.compile(r'[A-Za-z0-9_-]{1,64}')
ITEM_ID = re.compile(r'[0-9]{6,12}')
MAX_RULES = 4096
MAX_ARRAY = 256
MAX_STRING = 256
INT32 = (-2 ** 31, 2 ** 31 - 1)
STRING_BANNED = ('//', '/*', '*/', '#')
RULE_KEYS = {'id', 'section', 'class', 'parent', 'requires', 'provider', 'set', 'evidence'}
FILE_KEYS = {'schema', 'addon', 'providers', 'own_rules', 'dependency_rules'}
ADDONS_DIR = '@HollowCountryExpansionAI/addons/'
# Release-time injections are optional-pack dependencies: never part of the mandatory set.
INJECTED = (re.compile(r'/\* BEGIN HC inventory dependencies \*/.*?/\* END HC inventory dependencies \*/', re.S),
            re.compile(r'// BEGIN HC attachment scale.*?// END HC attachment scale[^\n]*', re.S))


def slot_pbo(slot):
    return f'hollowcountry_compat_{slot}.pbo'


def slot_prefix(slot):
    return f'{PREFIX}-{slot}'


def slot_patch(slot):
    return f'{PATCH}_{slot}'


def _ident(value, what):
    if not isinstance(value, str) or not IDENT.fullmatch(value):
        raise ValueError(f'compat rules: invalid {what}')
    return value


def _scalar(value, what):
    if isinstance(value, bool) or value is None:
        raise ValueError(f'compat rules: {what}: only numbers and strings are allowed')
    if isinstance(value, int):
        if not INT32[0] <= value <= INT32[1]:
            raise ValueError(f'compat rules: {what}: integer outside int32')
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f'compat rules: {what}: non-finite number')
        text = repr(value)
        if 'e' in text.lower() or abs(value) > INT32[1]:
            raise ValueError(f'compat rules: {what}: float must be plain decimal within int32 range')
        return text
    if isinstance(value, str):
        if len(value) > MAX_STRING or not all(32 <= ord(c) < 127 and c != '"' for c in value):
            raise ValueError(f'compat rules: {what}: string must be printable ASCII without quotes')
        if any(token in value for token in STRING_BANNED):
            raise ValueError(f'compat rules: {what}: string must not contain comment or directive markers')
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




def mandatory_addons(root=ROOT):
    """Patches every install already has: our own plus what our own configs require.

    The release-injected optional-pack blocks are stripped first, so an optional pack never
    becomes mandatory through them. Names are returned case-folded."""
    names = {name.casefold() for name in own_patches(root)}
    for config in sorted((Path(root) / 'mods').glob('*/config.cpp')):
        text = config.read_text(encoding='utf-8', errors='replace')
        for pattern in INJECTED:
            text = pattern.sub('', text)
        text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
        for array in re.findall(r'\brequiredAddons\s*\[\s*\]\s*=\s*\{([^{}]*)\}\s*;', text):
            names.update(name.casefold() for name in re.findall(r'"([^"\n]+)"', array))
    return names


def _check_providers(rows, known):
    if rows is None:
        return {}
    if not isinstance(rows, list):
        raise ValueError('compat rules: providers must be a list')
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'slot', 'item'}:
            raise ValueError('compat rules: provider needs exactly slot and item')
        slot, item = row['slot'], row['item']
        if slot not in pbo.COMPAT_SLOTS or slot in known:
            raise ValueError('compat rules: provider slot invalid or duplicated')
        if not isinstance(item, str) or not ITEM_ID.fullmatch(item) or item in known.values():
            raise ValueError('compat rules: provider item invalid or duplicated')
        known[slot] = item
    return known


def load_rules(paths=None, root=ROOT):
    """Validate rule files; return (addon block, rules list of dicts with a 'source' key, providers).

    providers maps slot -> Workshop item id. Rules are checked against the mandatory-addon set:
    a rule without a provider may require only mandatory addons."""
    paths = [Path(p) for p in paths] if paths else [RULES] + [p for p in OPTIONAL_RULES if p.is_file()]
    addon, rules, ids, targets, providers = None, [], set(), set(), {}
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
        _check_providers(data.get('providers'), providers)
        for source, key in (('own', 'own_rules'), ('dependency', 'dependency_rules')):
            rows = data.get(key, [])
            if not isinstance(rows, list):
                raise ValueError(f'compat rules: {key} must be a list')
            for row in rows:
                rule = _check_rule(row, source)
                if rule['id'].casefold() in ids:
                    raise ValueError('compat rules: duplicate id ' + rule['id'])
                target = (rule['section'], rule['class'].casefold())
                if target in targets:
                    raise ValueError('compat rules: duplicate target class ' + rule['class'])
                ids.add(rule['id'].casefold())
                targets.add(target)
                rules.append(rule)
    if len(rules) > MAX_RULES:
        raise ValueError('compat rules: too many rules')
    addon = _check_addon(addon, root)
    _check_requires(rules, providers, mandatory_addons(root))
    _check_parents(rules)
    return addon, rules, providers


def _check_requires(rules, providers, mandatory):
    for rule in rules:
        optional = [name for name in rule['requires'] if name.casefold() not in mandatory]
        slot = rule['provider']
        if slot is None:
            if optional:
                raise ValueError(f'compat rules: {rule["id"]}: requires an optional addon; '
                                 'give the rule a provider slot')
            continue
        if slot not in providers:
            raise ValueError(f'compat rules: {rule["id"]}: provider slot is not declared')
        if not optional:
            raise ValueError(f'compat rules: {rule["id"]}: provider rule requires only mandatory addons')


def _check_parents(rules):
    """A parent defined by another rule must sit in the same PBO or in the base PBO."""
    owner = {(r['section'], r['class'].casefold()): r['provider'] for r in rules}
    for rule in rules:
        parent_owner = owner.get((rule['section'], rule['parent'].casefold()), rule['provider'])
        if parent_owner != rule['provider'] and not (parent_owner is None and rule['provider'] is not None):
            raise ValueError(f'compat rules: {rule["id"]}: parent is defined in another compat PBO')


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
    if name.casefold() == parent.casefold():
        raise ValueError(f'compat rules: {rule_id}: class cannot inherit from itself')
    requires = row.get('requires', [])
    if (not isinstance(requires, list) or len({a.casefold() for a in requires if isinstance(a, str)}) != len(requires)
            or any(not isinstance(a, str) or not IDENT.fullmatch(a) for a in requires)):
        raise ValueError(f'compat rules: {rule_id}: invalid requires')
    provider = row.get('provider')
    if provider is not None and provider not in pbo.COMPAT_SLOTS:
        raise ValueError(f'compat rules: {rule_id}: invalid provider slot')
    evidence = row.get('evidence', '')
    if not isinstance(evidence, str) or len(evidence) > 300:
        raise ValueError(f'compat rules: {rule_id}: invalid evidence')
    if (source == 'dependency' or provider is not None) and (not requires or not evidence.strip()):
        raise ValueError(f'compat rules: {rule_id}: dependency and provider rules need requires and evidence')
    props = row.get('set', {})
    if not isinstance(props, dict):
        raise ValueError(f'compat rules: {rule_id}: set must be an object')
    lines, seen = [], set()
    for key in sorted(props):
        line = _property(key, props[key], rule_id)
        # Engine property names ignore case, and "x" and "x[]" are one name.
        folded = key.removesuffix('[]').casefold()
        if folded in seen:
            raise ValueError(f'compat rules: {rule_id}: duplicate property {key}')
        seen.add(folded)
        lines.append(line)
    return {'id': rule_id, 'section': row['section'], 'class': name, 'parent': parent,
            'requires': list(requires), 'provider': provider, 'lines': lines, 'source': source}


def _ordered(rules):
    """Rules of one section, parents defined by other rules first; reject cycles (case-insensitive)."""
    by_name = {rule['class'].casefold(): rule for rule in rules}
    done, order, active = set(), [], set()

    def visit(rule):
        key = rule['class'].casefold()
        if key in done:
            return
        if key in active:
            raise ValueError('compat rules: inheritance cycle at ' + rule['class'])
        active.add(key)
        parent = by_name.get(rule['parent'].casefold())
        if parent is not None:
            visit(parent)
        active.discard(key)
        done.add(key)
        order.append(rule)

    for rule in sorted(rules, key=lambda r: (r['class'].casefold(), r['class'])):
        visit(rule)
    return order


def render_config(addon, rules, slot=None):
    """Config text and requiredAddons for the base PBO (slot None) or one provider slot."""
    patch = PATCH if slot is None else slot_patch(slot)
    required = list(addon['required_addons'])
    if slot is not None:
        required.append(PATCH)
    for rule in rules:
        for name in rule['requires']:
            if name.casefold() not in {a.casefold() for a in required}:
                required.append(name)
    out = ['// Generated by tools/package/compat_addon.py; do not edit.',
           'class CfgPatches', '{', f'    class {patch}', '    {',
           '        units[] = {};', '        weapons[] = {};', '        requiredVersion = 0.1;',
           '        requiredAddons[] = {' + ', '.join(f'"{name}"' for name in required) + '};',
           '    };', '};']
    for section in SECTIONS:
        members = _ordered([rule for rule in rules if rule['section'] == section])
        if not members:
            continue
        defined = {rule['class'].casefold() for rule in members}
        forward = {}
        for rule in members:
            if rule['parent'].casefold() not in defined:
                forward.setdefault(rule['parent'].casefold(), rule['parent'])
        out += [f'class {section}', '{']
        for parent in sorted(forward.values(), key=str.casefold):
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


def _build(prefix, files):
    blob = pbo.pack(files, prefix=prefix)
    if pbo.parse(blob, prefixes=(prefix,)) != (prefix, files):
        raise ValueError('compat PBO roundtrip differs')
    return blob


def _summary(rules):
    return {'own': sum(r['source'] == 'own' for r in rules),
            'dependency': sum(r['source'] == 'dependency' for r in rules)}


def generate_all(rule_paths=None, strings=compat_stringtable.STRINGS, root=ROOT, workshop=None, manifest=None):
    """Return (outputs, receipt): outputs is [(pbo name, blob, files)], base first.

    Optional-provider PBOs are gated like weapon_pack_guards: not declared in the stack manifest
    means no PBO (receipt status absent); declared but not installed under workshop refuses."""
    addon, rules, providers = load_rules(rule_paths, root)
    table, keys = compat_stringtable.build(strings)
    base_rules = [r for r in rules if r['provider'] is None]
    config, required = render_config(addon, base_rules)
    files = {'config.cpp': config}
    if table is not None:
        files['stringtable.csv'] = table
    outputs = [(PBO_NAME, _build(PREFIX, files), files)]
    receipt = {
        'status': 'generated', 'runtime': 'PENDING', 'pbo': PBO_NAME, 'prefix': PREFIX,
        'sha256': hashlib.sha256(outputs[0][1]).hexdigest(),
        'config_sha256': hashlib.sha256(config).hexdigest(),
        'requiredAddons': required,
        'rules': _summary(rules),
        'strings': len(keys),
        'native_compile': 'PENDING', 'one_server_one_client': 'PENDING',
        'pbos': [PBO_NAME], 'optional': [],
    }
    for slot in sorted({r['provider'] for r in rules if r['provider'] is not None}):
        members = [r for r in rules if r['provider'] == slot]
        entry = {'slot': slot, 'rules': _summary(members), 'runtime': 'PENDING'}
        receipt['optional'].append(entry)
        if not weapon_pack_guards.declared_item(providers[slot], manifest):
            entry.update(status='absent', reason='provider not declared')
            continue
        if workshop is None or not Path(workshop).is_dir():
            raise ValueError('Workshop content root is missing; absence is not verified')
        if not (Path(workshop) / providers[slot]).exists():
            raise ValueError('declared compat provider is missing; generation required')
        slot_config, slot_required = render_config(addon, members, slot)
        slot_files = {'config.cpp': slot_config}
        blob = _build(slot_prefix(slot), slot_files)
        outputs.append((slot_pbo(slot), blob, slot_files))
        entry.update(status='generated', pbo=slot_pbo(slot), prefix=slot_prefix(slot),
                     sha256=hashlib.sha256(blob).hexdigest(),
                     config_sha256=hashlib.sha256(slot_config).hexdigest(),
                     requiredAddons=slot_required, native_compile='PENDING')
        receipt['pbos'].append(slot_pbo(slot))
    # Public-safe output: no PBO content or receipt may carry a banned provider token.
    texts = [data for _, _, shipped in outputs for data in shipped.values()]
    texts.append(json.dumps(receipt).encode())
    if not all(inventory_sources.safe_text(data.decode('utf-8')) for data in texts):
        raise ValueError('compat output contains a banned provider token')
    return outputs, receipt


def generate(rule_paths=None, strings=compat_stringtable.STRINGS, root=ROOT, workshop=None, manifest=None):
    """Return (base PBO bytes, base source files dict, full receipt)."""
    outputs, receipt = generate_all(rule_paths, strings, root, workshop, manifest)
    return outputs[0][1], outputs[0][2], receipt


def check_receipt(receipt, present):
    """Problems (fixed text) between a compat receipt and the shipped PBO hashes.

    present maps '@HollowCountryExpansionAI/addons/<name>.pbo' -> sha256 for every shipped PBO;
    used by friendcycle and friend_bundle so both reject a bundle that drifted from the build."""
    if (not isinstance(receipt, dict) or receipt.get('status') != 'generated'
            or receipt.get('pbo') != PBO_NAME or not isinstance(receipt.get('optional'), list)):
        return ['compat receipt missing or not generated']
    wanted, absent = {ADDONS_DIR + PBO_NAME: receipt.get('sha256')}, set()
    for entry in receipt['optional']:
        slot = entry.get('slot') if isinstance(entry, dict) else None
        if slot not in pbo.COMPAT_SLOTS:
            return ['compat receipt has an invalid optional entry']
        if entry.get('status') == 'generated' and entry.get('pbo') == slot_pbo(slot):
            wanted[ADDONS_DIR + slot_pbo(slot)] = entry.get('sha256')
        elif entry.get('status') == 'absent':
            absent.add((ADDONS_DIR + slot_pbo(slot)).casefold())
        else:
            return ['compat receipt has an invalid optional entry']
    problems = []
    folded = {path.casefold(): sha for path, sha in present.items()}
    for path, sha in wanted.items():
        if folded.get(path.casefold()) != sha:
            problems.append('compat PBO missing or changed: ' + path.rsplit('/', 1)[1])
    for path in folded:
        name = path.rsplit('/', 1)[-1]
        if path.startswith(ADDONS_DIR.casefold()) and name.startswith('hollowcountry_compat'):
            if path in absent or path not in {w.casefold() for w in wanted}:
                problems.append('unexpected compat PBO: ' + name)
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--out', type=Path, required=True,
                        help='new staging directory; existing output is refused')
    parser.add_argument('--rules', type=Path, action='append',
                        help='rule file (repeatable); default compat_rules.json + compat_vehicles.json if present')
    parser.add_argument('--strings', type=Path, default=compat_stringtable.STRINGS)
    parser.add_argument('--workshop', type=Path, default=weapon_pack_guards.WORKSHOP,
                        help='installed Workshop content root (read only when an optional provider is declared)')
    parser.add_argument('--manifest', type=Path, help='Workshop stack manifest (default tools/setup/workshop_mods.json)')
    parser.add_argument('--source', action='store_true', help='also write plain config/stringtable under source/')
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.exit(1, 'compat_addon: output already exists; use fresh staging\n')
    try:
        outputs, receipt = generate_all(args.rules, args.strings, workshop=args.workshop, manifest=args.manifest)
    except (OSError, ValueError) as error:
        # OSError text can carry account paths; never echo it.
        reason = str(error) if isinstance(error, ValueError) else 'input read failed'
        parser.exit(1, 'compat_addon: ' + reason + '\n')
    args.out.mkdir(parents=True)
    for name, blob, files in outputs:
        (args.out / name).write_bytes(blob)
        if args.source:
            target = args.out / 'source' / ('' if name == PBO_NAME else name[len('hollowcountry_compat_'):-4])
            target.mkdir(parents=True, exist_ok=True)
            for member, data in files.items():
                (target / member).write_bytes(data)
    (args.out / 'compat-addon.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('compat_addon: generated rules={own}+{dependency} strings={strings} pbos={pbos} optional_absent={absent} '
          'runtime=PENDING'.format(pbos=len(outputs), absent=sum(e['status'] == 'absent' for e in receipt['optional']),
                                   strings=receipt['strings'], **receipt['rules']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
