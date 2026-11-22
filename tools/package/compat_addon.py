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
base PBO may require mandatory addons only: the patches of the PBOs the release ships from
mods/ (the ship_inputs catalogue; the offline-built assets addon is not one of them), what
their configs require (minus the release-injected inventory block) and the installed vanilla
patches. A rule needing an optional addon names a `provider` slot; each slot becomes its own
PBO and nested prefix, built only when the provider's Workshop item is declared in
tools/setup/workshop_mods.json (weapon_pack_guards.declared_item) and present under
--workshop. An undeclared provider emits no PBO (receipt status absent); a declared but
missing one refuses generation. Provider PBOs also require the base compat patch, so a parent
class may live in the base PBO but never in another provider's PBO.

Installed-config checks (read only, tools.audit.pbo_config; static file evidence, not engine
proof). The engine does not refuse a reopened class with a different parent: it logs "Updating
base class" and silently re-parents it. So before generation every rule is checked against the
installed configs (our own shipped configs, the vanilla Addons folder and the declared Workshop
items), and each refusal carries a reason code:
  provider_requires_missing / provider_requires_foreign  a provider rule requires a patch the
                            provider's installed Workshop item does not define (or another item does)
  parent_mismatch / parent_ambiguous / parent_unverified  the target class exists upstream with a
                            different, conflicting or unreadable parent
  class_absent_upstream     the target class does not exist upstream; a rule that really creates a
                            class says so with "new_class": true and an evidence string. Retiring a
                            class later drops saved entities on a server that is never wiped, so a
                            new class is a deliberate, traceable act, not a typo
  parent_missing            the parent class exists nowhere upstream and is no other rule's class
  parent_requires_missing   the parent lives in an addon outside our shipped chain (a vanilla addon
                            we do not already require, or an optional one) and the rule's requires
                            does not name an addon that defines it

Rule schema (schema 1), file-level keys: schema, addon, providers, own_rules, dependency_rules.
  addon: {patch, prefix, pbo, required_addons[]}  required_addons must be our own patches.
  providers: [{slot, item}]  slot is one of pbo.COMPAT_SLOTS, item the Workshop id
  rule:  {id, section, class, parent, requires[], provider, new_class, set{}, evidence}
         id        unique (case-insensitive) [A-Za-z0-9_-]; printed as a comment only
         section   one of SECTIONS
         class     unique per section, case-insensitive (the engine ignores class-name case);
                   class, parent and property names may not be config keywords (RESERVED)
         parent    the UPSTREAM base class: it must be the class the target already inherits
                   from where it is defined. A different parent would re-parent the class, so
                   generation refuses it (parent_mismatch). It is never one of our own classes
                   unless the rule is an own rule.
         requires  addons (CfgPatches names) that define the parent; mandatory in dependency_rules
         provider  optional slot for rules whose requires names a non-mandatory addon
         new_class true only for a rule that defines a class absent upstream; needs evidence
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

from tools.audit import pbo_config
from tools.package import compat_stringtable, inventory_sources, pbo, weapon_pack_guards
from tools.release import ship_inputs

ROOT = Path(__file__).resolve().parents[2]
RULES = Path(__file__).with_name('compat_rules.json')
OPTIONAL_RULES = (Path(__file__).with_name('compat_vehicles.json'),)
SCHEMA = 1
PBO_NAME = pbo.COMPAT_PBO_NAME
PREFIX = pbo.COMPAT_PREFIX
PATCH = 'HollowCountryCompat'
SECTIONS = ('CfgVehicles', 'CfgWeapons', 'CfgMagazines', 'CfgAmmo', 'CfgNonAIVehicles')
IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,127}')
PROP = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}(\[\])?')
RULE_ID = re.compile(r'[A-Za-z0-9_-]{1,64}')
ITEM_ID = re.compile(r'[0-9]{6,12}')
SHA256 = re.compile(r'[0-9a-fA-F]{64}')
# Config-language keywords and preprocessor words: never a class, parent, property or addon name.
RESERVED = frozenset({'class', 'delete', 'import', 'enum', 'extern', 'include', 'define', 'undef',
                      'ifdef', 'ifndef', 'else', 'endif'})
MAX_RULES = 4096
MAX_ARRAY = 256
MAX_STRING = 256
INT32 = (-2 ** 31, 2 ** 31 - 1)
STRING_BANNED = ('//', '/*', '*/', '#')
RULE_KEYS = {'id', 'section', 'class', 'parent', 'requires', 'provider', 'new_class', 'set', 'evidence'}
FILE_KEYS = {'schema', 'addon', 'providers', 'own_rules', 'dependency_rules'}
ADDONS_DIR = '@HollowCountryExpansionAI/addons/'
COMPAT_STEM = ship_inputs.COMPAT_STEM
UPSTREAM_ROOTS = ('CfgPatches',) + SECTIONS
# Release-time injections are optional-pack dependencies: never part of the mandatory set.
INJECTED = (re.compile(r'/\* BEGIN HC inventory dependencies \*/.*?/\* END HC inventory dependencies \*/', re.S),
            re.compile(r'// BEGIN HC attachment scale.*?// END HC attachment scale[^\n]*', re.S))


def slot_pbo(slot):
    return pbo.compat_slot_pbo(slot)


def slot_prefix(slot):
    return f'{PREFIX}-{slot}'


def slot_patch(slot):
    return f'{PATCH}_{slot}'


def _refuse(rule_id, code, text):
    raise ValueError(f'compat rules: {rule_id}: {code}: {text}')


def _ident(value, what):
    if not isinstance(value, str) or not IDENT.fullmatch(value) or value.casefold() in RESERVED:
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
    if (not isinstance(name, str) or not PROP.fullmatch(name)
            or name.removesuffix('[]').casefold() in RESERVED):
        raise ValueError(f'compat rules: {rule_id}: invalid property name')
    what = f'{rule_id}.{name}'
    if name.endswith('[]'):
        if not isinstance(value, list) or len(value) > MAX_ARRAY:
            raise ValueError(f'compat rules: {what}: array property needs a bounded list')
        return f'{name} = {{' + ', '.join(_scalar(item, what) for item in value) + '};'
    if isinstance(value, list):
        raise ValueError(f'compat rules: {what}: list needs a "[]" property name')
    return f'{name} = {_scalar(value, what)};'


# ------------------------------------------------------------------ own shipped chain
def shipped_configs(root=ROOT):
    """config.cpp of the own source folders whose PBOs the release ships (the ship_inputs catalogue).

    The catalogue stems are matched to registered source prefixes. HollowCountryAssets is built
    offline, is not in the catalogue and so is never part of the mandatory set; the guard and
    compat PBOs are generated and have no source folder."""
    configs = []
    for stem, _, _ in ship_inputs.signing_inputs():
        for prefix in pbo.PREFIXES:
            config = Path(root) / 'mods' / prefix / 'config.cpp'
            if prefix.lower() == stem and config.is_file():
                configs.append(config)
    return configs


def _patch_names(text):
    """Top-level class names of the CfgPatches block of one config text."""
    match = re.search(r'\bclass\s+CfgPatches\s*\{', text)
    if not match:
        return set()
    depth, start, block = 1, match.end(), None
    for index in range(start, len(text)):
        if text[index] == '{':
            depth += 1
        elif text[index] == '}':
            depth -= 1
            if depth == 0:
                block = text[start:index]
                break
    if block is None:
        return set()
    names, depth = set(), 0
    for token in re.finditer(r'[{}]|\bclass\s+([A-Za-z_]\w*)', block):
        if token.group(0) == '{':
            depth += 1
        elif token.group(0) == '}':
            depth -= 1
        elif depth == 0:
            names.add(token.group(1))
    return names


def own_patches(root=ROOT):
    """CfgPatches class names of the shipped own configs (see shipped_configs)."""
    names = set()
    for config in shipped_configs(root):
        names |= _patch_names(config.read_text(encoding='utf-8', errors='replace'))
    return names


def chain_addons(root=ROOT):
    """Patches every install already has through our own chain, case-folded: the shipped own
    patches plus what the shipped own configs require. The release-injected optional-pack blocks
    are stripped first, so an optional pack never becomes mandatory through them."""
    names = {name.casefold() for name in own_patches(root)}
    for config in shipped_configs(root):
        text = config.read_text(encoding='utf-8', errors='replace')
        for pattern in INJECTED:
            text = pattern.sub('', text)
        text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
        for array in re.findall(r'\brequiredAddons\s*\[\s*\]\s*=\s*\{([^{}]*)\}\s*;', text):
            names.update(name.casefold() for name in re.findall(r'"([^"\n]+)"', array))
    return names


def mandatory_addons(root=ROOT, vanilla=frozenset()):
    """Patches a base PBO may require: our chain plus the installed vanilla patches (case-folded).

    Vanilla patches are present on every install, so a rule needing one never needs a provider."""
    return chain_addons(root) | {name.casefold() for name in vanilla}


# ------------------------------------------------------------------ installed configs
def _pbo_files(directory):
    try:
        entries = sorted(Path(directory).iterdir(), key=lambda path: path.name.casefold())
    except OSError:
        return []
    return [path for path in entries if path.is_file() and path.suffix.lower() == '.pbo']


def _item_pbos(workshop, item):
    """PBOs under the installed Workshop item's addons folder (empty when absent or ambiguous)."""
    try:
        folders = [path for path in (Path(workshop) / item).iterdir()
                   if path.is_dir() and path.name.lower() == 'addons']
    except OSError:
        return []
    return _pbo_files(folders[0]) if len(folders) == 1 else []


def _read_pbo(path, roots):
    """(patch names, {root: [(class, parent or None)]}) of one installed PBO, read only."""
    patches, classes = set(), {}
    try:
        for _, found in pbo_config.read_config_members(path, roots):
            patches.update(found.get('CfgPatches', {}))
            for root_name, rows in found.items():
                if root_name != 'CfgPatches':
                    classes.setdefault(root_name, []).extend((name, row.get('parent')) for name, row in rows.items())
    except (OSError, ValueError) as error:
        raise ValueError('compat upstream: unreadable installed config in ' + Path(path).name) from error
    return patches, classes


def vanilla_patches(addons=ship_inputs.ADDONS):
    """Case-folded CfgPatches names of the installed vanilla Addons folder (empty when absent)."""
    names = set()
    for path in _pbo_files(addons) if addons else []:
        names.update(name.casefold() for name in _read_pbo(path, ('CfgPatches',))[0])
    return names


class Upstream:
    """What the installed configs say: patches per source and every top-level class definition."""

    def __init__(self):
        self.patches = {}   # source -> {case-folded patch}
        self.defs = {}      # (section, case-folded class) -> [(source, owning patches, parent or None)]

    def add(self, source, patches, classes):
        owners = frozenset(name.casefold() for name in patches)
        self.patches.setdefault(source, set()).update(owners)
        for section, rows in classes.items():
            for name, parent in rows:
                self.defs.setdefault((section, name.casefold()), []).append((source, owners, parent or None))


def _declared_items(manifest=None):
    data = json.loads(Path(manifest or ROOT / 'tools/setup/workshop_mods.json').read_bytes())
    if data.get('schema') != 1 or not isinstance(data.get('mods'), list):
        raise ValueError('invalid Workshop stack manifest')
    return [row['id'] for row in data['mods'] if row.get('id') and not row.get('publish')]


def read_upstream(rules, root=ROOT, vanilla=ship_inputs.ADDONS, workshop=None, manifest=None):
    """Scan our shipped configs, the vanilla Addons folder and the declared Workshop items, but
    only the sections the rules touch."""
    roots = ('CfgPatches',) + tuple(sorted({rule['section'] for rule in rules}))
    upstream = Upstream()
    for config in shipped_configs(root):
        found = pbo_config.parse_text_config(config.read_text(encoding='utf-8', errors='replace'), roots)
        upstream.add('own', found.get('CfgPatches', {}),
                     {name: [(c, row.get('parent')) for c, row in rows.items()]
                      for name, rows in found.items() if name != 'CfgPatches'})
    for path in _pbo_files(vanilla) if vanilla else []:
        upstream.add('vanilla', *_read_pbo(path, roots))
    if workshop is not None and Path(workshop).is_dir():
        for item in _declared_items(manifest):
            for path in _item_pbos(workshop, item):
                upstream.add(item, *_read_pbo(path, roots))
    return upstream


def verify_upstream(rules, providers, active, root, upstream):
    """Refuse (reason-coded) a rule the installed configs contradict. See the module docstring.

    active is the set of provider slots that will be built; rules of other slots are not emitted
    and so not checked."""
    chain = chain_addons(root)
    ours = {(rule['section'], rule['class'].casefold()) for rule in rules}
    for rule in rules:
        if rule['provider'] is not None and rule['provider'] not in active:
            continue
        rule_id, section = rule['id'], rule['section']
        if rule['provider'] is not None:
            item = providers[rule['provider']]
            for name in rule['requires']:
                if name.casefold() in chain or name.casefold() in upstream.patches.get('vanilla', ()):
                    continue
                if name.casefold() not in upstream.patches.get(item, ()):
                    foreign = any(name.casefold() in found for source, found in upstream.patches.items()
                                  if source not in (item, 'own', 'vanilla'))
                    _refuse(rule_id, 'provider_requires_foreign' if foreign else 'provider_requires_missing',
                            f'the installed provider item does not define the required patch {name}')
        entries = upstream.defs.get((section, rule['class'].casefold()), [])
        if entries:
            if rule['new_class']:
                _refuse(rule_id, 'new_class_exists', 'new_class is set but the class exists upstream')
            parents = {parent.casefold() for _, _, parent in entries if parent}
            if not parents:
                _refuse(rule_id, 'parent_unverified', 'the upstream class carries no readable parent')
            if len(parents) > 1:
                _refuse(rule_id, 'parent_ambiguous', 'the upstream class is defined with different parents')
            if rule['parent'].casefold() not in parents:
                _refuse(rule_id, 'parent_mismatch',
                        'the parent differs from the installed one; the engine would silently re-parent the class')
        elif not rule['new_class']:
            _refuse(rule_id, 'class_absent_upstream',
                    'no such class upstream; a rule that creates one needs "new_class": true and evidence '
                    '(retiring a class later drops saved entities)')
        if (section, rule['parent'].casefold()) in ours:
            continue
        definers = set()
        for _, owners, _ in upstream.defs.get((section, rule['parent'].casefold()), []):
            definers |= owners
        if not definers:
            _refuse(rule_id, 'parent_missing', 'the parent class exists nowhere upstream')
        if not definers & chain and not definers & {name.casefold() for name in rule['requires']}:
            _refuse(rule_id, 'parent_requires_missing',
                    'the parent lives in an addon outside our chain; requires must name an addon that defines it')


# ------------------------------------------------------------------ rule files
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


def rule_paths(root=ROOT):
    """The rule files of one tree: compat_rules.json plus compat_vehicles.json when present."""
    base = Path(root) / 'tools/package'
    return [base / RULES.name] + [base / path.name for path in OPTIONAL_RULES if (base / path.name).is_file()]


def _read_rules(paths=None, root=ROOT):
    """Parse and statically validate rule files: (addon block, rules, providers). No installed data."""
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
    _check_parents(rules)
    return addon, rules, providers


def load_rules(paths=None, root=ROOT, vanilla=frozenset()):
    """Validate rule files; return (addon block, rules list of dicts with a 'source' key, providers).

    providers maps slot -> Workshop item id. Rules are checked against the mandatory-addon set
    (our chain plus the case-folded vanilla patch names given): a rule without a provider may
    require only mandatory addons. Installed-config checks are verify_upstream's."""
    addon, rules, providers = _read_rules(paths, root)
    _check_requires(rules, providers, mandatory_addons(root, vanilla))
    return addon, rules, providers


def declared_providers(paths=None, root=ROOT, manifest=None):
    """slot -> Workshop item for the provider slots that have rules and whose item the stack declares.

    The compile gate uses this to load the dependency stack even when the weapon pack is not declared."""
    _, rules, providers = _read_rules(paths, root)
    used = sorted({rule['provider'] for rule in rules if rule['provider'] is not None})
    return {slot: providers[slot] for slot in used
            if slot in providers and weapon_pack_guards.declared_item(providers[slot], manifest)}


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
            or any(not isinstance(a, str) or not IDENT.fullmatch(a) or a.casefold() in RESERVED for a in requires)):
        raise ValueError(f'compat rules: {rule_id}: invalid requires')
    provider = row.get('provider')
    if provider is not None and provider not in pbo.COMPAT_SLOTS:
        raise ValueError(f'compat rules: {rule_id}: invalid provider slot')
    evidence = row.get('evidence', '')
    if not isinstance(evidence, str) or len(evidence) > 300:
        raise ValueError(f'compat rules: {rule_id}: invalid evidence')
    new_class = row.get('new_class', False)
    if not isinstance(new_class, bool):
        raise ValueError(f'compat rules: {rule_id}: new_class must be true or false')
    if new_class and not evidence.strip():
        raise ValueError(f'compat rules: {rule_id}: a new class needs an evidence string')
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
            'requires': list(requires), 'provider': provider, 'new_class': new_class,
            'lines': lines, 'source': source}


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


def generate_all(rule_paths=None, strings=compat_stringtable.STRINGS, root=ROOT, workshop=None, manifest=None,
                 vanilla=ship_inputs.ADDONS):
    """Return (outputs, receipt): outputs is [(pbo name, blob, files)], base first.

    Optional-provider PBOs are gated like weapon_pack_guards: not declared in the stack manifest
    means no PBO (receipt status absent); declared but not installed under workshop refuses. With
    rules present, every emitted rule is also verified against the installed configs (vanilla is
    the installed vanilla Addons folder; see verify_upstream)."""
    _, known, _ = _read_rules(rule_paths, root)
    vanilla_names = vanilla_patches(vanilla) if known else frozenset()
    addon, rules, providers = load_rules(rule_paths, root, vanilla_names)
    table, keys = compat_stringtable.build(strings)
    active = set()
    for slot in sorted({r['provider'] for r in rules if r['provider'] is not None}):
        if not weapon_pack_guards.declared_item(providers[slot], manifest):
            continue
        if workshop is None or not Path(workshop).is_dir():
            raise ValueError('Workshop content root is missing; absence is not verified')
        if not (Path(workshop) / providers[slot]).exists():
            raise ValueError('declared compat provider is missing; generation required')
        active.add(slot)
    if rules:
        verify_upstream(rules, providers, active, root,
                        read_upstream(rules, root, vanilla, workshop, manifest))
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
        if slot not in active:
            entry.update(status='absent', reason='provider not declared')
            continue
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


def generate(rule_paths=None, strings=compat_stringtable.STRINGS, root=ROOT, workshop=None, manifest=None,
             vanilla=ship_inputs.ADDONS):
    """Return (base PBO bytes, base source files dict, full receipt)."""
    outputs, receipt = generate_all(rule_paths, strings, root, workshop, manifest, vanilla)
    return outputs[0][1], outputs[0][2], receipt


# ------------------------------------------------------------------ receipt checks
def _hex(value):
    """A 64-hex sha256 as lower case, or None; anything else (None, short, odd) never matches."""
    if isinstance(value, str) and SHA256.fullmatch(value):
        return value.lower()
    return None


def receipt_hashes(receipt):
    """(wanted, absent) of a compat receipt: wanted maps case-folded PBO file name -> sha256 for the
    base and every generated optional PBO, absent holds the optional names that must not ship.
    Raises ValueError for a receipt that is missing, not generated or carries a non-sha256 value."""
    if (not isinstance(receipt, dict) or receipt.get('status') != 'generated'
            or receipt.get('pbo') != PBO_NAME or not isinstance(receipt.get('optional'), list)):
        raise ValueError('compat receipt missing or not generated')
    wanted, absent = {PBO_NAME.casefold(): _hex(receipt.get('sha256'))}, set()
    for entry in receipt['optional']:
        slot = entry.get('slot') if isinstance(entry, dict) else None
        if slot not in pbo.COMPAT_SLOTS:
            raise ValueError('compat receipt has an invalid optional entry')
        name = slot_pbo(slot).casefold()
        if entry.get('status') == 'generated' and entry.get('pbo') == slot_pbo(slot):
            wanted[name] = _hex(entry.get('sha256'))
        elif entry.get('status') == 'absent':
            absent.add(name)
        else:
            raise ValueError('compat receipt has an invalid optional entry')
    if not all(wanted.values()):
        raise ValueError('compat receipt sha256 is not a 64-hex value')
    return wanted, absent


def check_hashes(receipt, hashes):
    """Problems (fixed text) between a compat receipt and {PBO file name: sha256} actually produced.

    Every value must be a 64-hex sha256 on both sides; the set of compat names must match exactly.
    Used by the release (generator output, gate output), the compile gate and friendcycle."""
    try:
        wanted, absent = receipt_hashes(receipt)
    except ValueError as error:
        return [str(error)]
    problems, got = [], {}
    for name, sha in (hashes or {}).items():
        if _hex(sha) is None:
            problems.append('compat sha256 is not a 64-hex value: ' + str(name))
        got[str(name).casefold()] = _hex(sha)
    for name, sha in wanted.items():
        if got.get(name) != sha:
            problems.append('compat PBO missing or changed: ' + name)
    for name in got:
        if name.startswith(COMPAT_STEM) and (name in absent or name not in wanted):
            problems.append('unexpected compat PBO: ' + name)
    return problems


def check_receipt(receipt, present):
    """Problems (fixed text) between a compat receipt and the shipped PBO hashes.

    present maps '@HollowCountryExpansionAI/addons/<name>.pbo' -> sha256 for every shipped PBO;
    used by friendcycle and friend_bundle so both reject a bundle that drifted from the build."""
    shipped = {path.rsplit('/', 1)[-1]: sha for path, sha in present.items()
               if path.casefold().startswith(ADDONS_DIR.casefold())}
    return check_hashes(receipt, shipped)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--out', type=Path, required=True,
                        help='new staging directory; existing output is refused')
    parser.add_argument('--rules', type=Path, action='append',
                        help='rule file (repeatable); default compat_rules.json + compat_vehicles.json if present')
    parser.add_argument('--strings', type=Path, default=compat_stringtable.STRINGS)
    parser.add_argument('--workshop', type=Path, default=weapon_pack_guards.WORKSHOP,
                        help='installed Workshop content root (read when a provider is declared or rules exist)')
    parser.add_argument('--addons', type=Path, default=ship_inputs.ADDONS,
                        help='installed vanilla Addons folder (read only; the vanilla side of the upstream checks)')
    parser.add_argument('--manifest', type=Path, help='Workshop stack manifest (default tools/setup/workshop_mods.json)')
    parser.add_argument('--source', action='store_true', help='also write plain config/stringtable under source/')
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.exit(1, 'compat_addon: output already exists; use fresh staging\n')
    try:
        outputs, receipt = generate_all(args.rules, args.strings, workshop=args.workshop, manifest=args.manifest,
                                        vanilla=args.addons)
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
