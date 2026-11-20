"""Optional Tactical Flava (Workshop 2646817942) dependency: read-only verifier and fail-closed CE delta.

The base Hollow Country addon never depends on this module or on Tactical Flava (TF). TF files are never
copied, bundled, repacked or re-hosted: the item ships no licence file, its Workshop page forbids
monetisation and repacks, and says nothing about dependency use, so a rights review stays pending. The
verifier only reads an operator's own installed copy (meta.cpp, bounded PBO headers, rapified ``config.bin``
and plain-text ``config.cpp`` members, and a vendor readme hash plus pinned PBO hashes) next to the vanilla DayZ addons, and writes
its report outside Git.

Generation is fail-closed: with no report, an unverified report, a report for a different allowlist, or any
class not individually verified, no spawn entries are produced. The delta registers a separate managed folder
(``hollow-country-tactical-flava/ce``) with complete new ``types.xml`` entries and required adapter
preattachments. It installs on top of, and rolls back before (last in, first out), the vanilla roster and
the optional SNAFU deltas.

Offline static checks establish nothing about DayZ behaviour: weapon firing, ammo acceptance, attachment
fitting, model loading, script interaction, signature checks, CE spawning and the 3-6 player balance stay
pending local acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

try:
    from tools.audit import pbo_config
    from tools.package import economy, firearms
    from tools.package import xml_text
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.audit import pbo_config
    from tools.package import economy, firearms
    from tools.package import xml_text

from tools.package import ce_extensions, snafu_optional

ALLOWLIST_PATH = Path(__file__).with_name('tactical_flava_allowlist.json')
WORKSHOP_ID = '2646817942'
MANAGED = 'hollow-country-tactical-flava'
SNAFU_MANAGED = 'hollow-country-snafu'
ROOTS = ('CfgWeapons', 'CfgMagazines', 'CfgAmmo', 'CfgVehicles')
VANILLA_ROOTS = ROOTS
KIND = 'tactical-flava-optional'
SPAWNABLE = 'ce/cfgspawnabletypes.xml'
DELTA_FILES = economy.DELTA_FILES | {SPAWNABLE}
TOP = {'schema', 'name', 'workshop_id', 'status', 'rights', 'entries', 'excluded'}
RIGHTS_REQUIRED = {'license', 'redistribution', 'dependency_use', 'review', 'terms_file', 'terms_sha256', 'urls'}
RIGHTS_FIXED = {'license': 'none-recorded', 'redistribution': 'none', 'dependency_use': 'unstated',
                'review': 'pending'}
ENTRY_REQUIRED = {'class', 'kind', 'role', 'tier', 'set', 'usage', 'value', 'justification'}
EXTRA = {'weapon': {'vanilla_ammo', 'magazines', 'optic_requires'}, 'magazine': set(), 'ammo': set(),
         'optic': {'slot', 'fits'}, 'attachment': {'slot', 'fits'}}
ROLES = {'weapon': {'modern', 'civilian', 'police'}, 'magazine': {'support'}, 'ammo': {'support'}, 'optic': {'modern'}, 'attachment': {'support'}}
TIERS = {'common', 'uncommon', 'rare'}
SET_FIELDS = ('nominal', 'min', 'lifetime', 'restock')
MODERN_USAGE = {'Military', 'Police'}
CLASS = re.compile(r'[A-Za-z0-9_]{1,80}')
MAX_ENTRIES = 1024
MAX_PBOS = 64
MAX_VANILLA_PBOS = 1024
MAX_TERMS_BYTES = 8 * 1024 * 1024
MAX_META_BYTES = 4096
PENDING = ['normal PBO/server load with TF installed on server and clients, signed bikey on a signed server',
           'DayZDiag/local spawn, firing, magazine and ammo-acceptance trials per class',
           'M4A1 BUIS/carry handle, vanilla Mosin and AK attachments, keybinds and stacked ZombieBase.EEKilled / '
           'ActionConstructor.RegisterActions behaviour with TF loaded',
           'M14 adapter and Elcan optic fitting (TF_M14_STD needs weaponDMRAdapter before any optic)',
           'CE spawn/error trials and 3-6-player budget measurement',
           'rights review of the missing licence file before any hosted server depends on TF',
           'destination install/rollback on the real mission copy']


def allowlist_sha256(allowlist):
    return economy.sha(economy.encode(allowlist))


def _int(value, low):
    return type(value) is int and value >= low


def _names(value, name):
    if (not isinstance(value, list) or len(set(map(str, value))) != len(value)
            or any(not isinstance(v, str) or not CLASS.fullmatch(v) for v in value)):
        raise ValueError(f'invalid class list: {name}')


def _safe_relative(text):
    if not isinstance(text, str) or re.fullmatch(r'[A-Za-z0-9_ .\-/]{1,200}', text) is None:
        return False
    return all(p not in {'', '.', '..'} for p in text.split('/'))


def validate_allowlist(allowlist):
    if not isinstance(allowlist, dict) or not TOP <= set(allowlist) <= TOP | {'hc61', 'test_abundance_multiplier'} \
            or type(allowlist['schema']) is not int or allowlist['schema'] != 1:
        raise ValueError('unsupported allowlist schema/fields')
    if not isinstance(allowlist['name'], str) or not re.fullmatch(r'[a-z0-9-]{1,64}', allowlist['name']):
        raise ValueError('invalid allowlist name')
    if allowlist['workshop_id'] != WORKSHOP_ID:
        raise ValueError('allowlist targets a different Workshop item')
    if allowlist['status'] != 'unverified':
        raise ValueError('a committed allowlist must stay unverified; verification is per install')
    rights = allowlist['rights']
    if (not isinstance(rights, dict) or not RIGHTS_REQUIRED <= set(rights) <= RIGHTS_REQUIRED | {'notes'}
            or any(rights[k] != v for k, v in RIGHTS_FIXED.items())
            or not _safe_relative(rights['terms_file'])
            or not re.fullmatch(r'[0-9a-f]{64}', str(rights['terms_sha256']))
            or not isinstance(rights['urls'], list) or not rights['urls']
            or any(not isinstance(u, str) or not u.startswith('https://') for u in rights['urls'])):
        raise ValueError('invalid rights block (licence, redistribution, dependency use and review are fixed)')
    if 'notes' in rights and (not isinstance(rights['notes'], list)
                              or any(not isinstance(n, str) for n in rights['notes'])):
        raise ValueError('invalid rights notes')
    snafu_optional._nominal_scale(allowlist.get('test_abundance_multiplier', 1))
    entries = allowlist['entries']
    if not isinstance(entries, list) or not 0 < len(entries) <= MAX_ENTRIES:
        raise ValueError('allowlist entries missing or over budget')
    rows, seen = {}, set()
    for e in entries:
        if not isinstance(e, dict):
            raise ValueError('invalid allowlist entry')
        kind = e.get('kind')
        if kind not in EXTRA or set(e) != ENTRY_REQUIRED | EXTRA[kind]:
            raise ValueError(f'unsupported allowlist entry fields: {e.get("class")}')
        name = e['class']
        if not isinstance(name, str) or not CLASS.fullmatch(name):
            raise ValueError('invalid class name')
        if e['role'] not in ROLES[kind] or e['tier'] not in TIERS:
            raise ValueError(f'invalid kind/role/tier: {name}')
        if name in seen:
            raise ValueError(f'duplicate allowlist class: {name}')
        seen.add(name)
        rows[name] = e
        if not isinstance(e['justification'], str) or not e['justification'].strip():
            raise ValueError(f'justification required: {name}')
        s = e['set']
        if (not isinstance(s, dict) or set(s) != set(SET_FIELDS) or not _int(s['nominal'], 0)
                or not _int(s['min'], 0) or s['min'] > s['nominal'] or not _int(s['lifetime'], 1)
                or not _int(s['restock'], 0)):
            raise ValueError(f'invalid budget fields: {name}')
        _names(e['usage'], name)
        _names(e['value'], name)
        if not e['usage']:
            raise ValueError(f'usage required: {name}')
        for field in ('vanilla_ammo', 'magazines', 'optic_requires', 'fits'):
            if field in e:
                _names(e[field], name)
        if 'slot' in e and (not isinstance(e['slot'], str) or not CLASS.fullmatch(e['slot'])):
            raise ValueError(f'invalid slot: {name}')
        if kind in {'optic', 'attachment'} and not e['fits']:
            raise ValueError(f'fits required: {name}')
    _validate_usage_rules(rows)
    snafu_optional._family_policy(allowlist)
    excluded = allowlist['excluded']
    if not isinstance(excluded, list) or len(excluded) > MAX_ENTRIES:
        raise ValueError('invalid excluded list')
    for x in excluded:
        if (not isinstance(x, dict) or not {'group', 'reason'} <= set(x) <= {'group', 'reason', 'classes'}
                or not all(isinstance(x[k], str) and x[k].strip() for k in ('group', 'reason'))):
            raise ValueError('excluded groups need a group and a reason')
        if 'classes' in x:
            _names(x['classes'], x['group'])
            if set(x['classes']) & set(rows):
                raise ValueError(f'excluded group names a selected class: {x["group"]}')


def _validate_usage_rules(rows):
    weapons = {n: e for n, e in rows.items() if e['kind'] == 'weapon'}
    magazines = {n: e for n, e in rows.items() if e['kind'] == 'magazine'}
    attachments = {n: e for n, e in rows.items() if e['kind'] == 'attachment'}
    for name, e in rows.items():
        usage = set(e['usage'])
        if e['kind'] in {'weapon', 'optic'} and e['role'] == 'modern':
            if 'Military' not in usage or not usage <= MODERN_USAGE:
                raise ValueError(f'modern pick must be Military (and Police only): {name}')
        elif e['kind'] == 'weapon' and e['role'] == 'civilian' and usage & MODERN_USAGE:
            raise ValueError(f'civilian pick may not use Military or Police: {name}')
    for name, e in weapons.items():
        if not set(e['magazines']) <= set(magazines):
            raise ValueError(f'unlisted magazine reference: {name}')
        for need in e['optic_requires']:
            if need not in attachments or name not in attachments[need]['fits']:
                raise ValueError(f'optic_requires must name an attachment that fits the weapon: {name}')
        if e['set']['nominal'] > 0:
            if not e['vanilla_ammo']:
                raise ValueError(f'spawning weapon needs vanilla ammo: {name}')
            if e['magazines'] and not any(magazines[m]['set']['nominal'] > 0 for m in e['magazines']):
                raise ValueError(f'spawning weapon has no spawning compatible magazine: {name}')
            if e['magazines'] and not any(magazines[m]['set']['nominal'] > 0 and
                                          set(magazines[m]['usage']) & set(e['usage']) for m in e['magazines']):
                raise ValueError(f'no magazine spawns where the weapon does: {name}')
    for name, e in magazines.items():
        parents = [w for w in weapons.values() if name in w['magazines']]
        if not parents:
            raise ValueError(f'magazine no weapon lists: {name}')
        if not set(e['usage']) <= {u for w in parents for u in w['usage']}:
            raise ValueError(f'magazine usage outside its weapons: {name}')
        if all(w['role'] == 'modern' for w in parents) and 'Military' not in e['usage']:
            raise ValueError(f'magazine of modern weapons must be Military: {name}')
    for name, e in rows.items():
        if e['kind'] in {'optic', 'attachment'}:
            if not set(e['fits']) <= set(weapons):
                raise ValueError(f'fits names an unlisted weapon: {name}')
            if not set(e['usage']) <= {u for w in e['fits'] for u in weapons[w]['usage']}:
                raise ValueError(f'usage outside the weapons it fits: {name}')
            if e['kind'] == 'attachment' and all(weapons[w]['role'] == 'modern' for w in e['fits']) \
                    and 'Military' not in e['usage']:
                raise ValueError(f'attachment of modern weapons must be Military: {name}')


# ---------------------------------------------------------------- verification

def _plain_dir(path, label):
    path = Path(path).absolute()
    if path.is_symlink():
        raise ValueError(f'{label} must not be a symlink')
    if not path.is_dir():
        raise ValueError(f'{label} is not a directory')
    return path


def _read_small(path, limit):
    if path is None or path.is_symlink() or not path.is_file():
        return None
    with open(path, 'rb') as handle:
        data = handle.read(limit + 1)
    return data if len(data) <= limit else None


def _child_ci(base, name):
    """Case-insensitive child lookup (Workshop folders vary in case); never follows a symlinked parent."""
    if base is None or base.is_symlink() or not base.is_dir():
        return None
    low = name.lower()
    for p in sorted(base.iterdir()):
        if p.name.lower() == low:
            return p
    return None


def _load_addons(root, problems, max_pbos, whole_hash=True):
    folder = _child_ci(root, 'addons')
    pbos = []
    if folder is not None and not folder.is_symlink() and folder.is_dir():
        pbos = sorted(p for p in folder.iterdir() if p.name.lower().endswith('.pbo'))
    if len(pbos) > max_pbos:
        raise ValueError('addon PBO count exceeds budget')
    if not pbos:
        problems.append('no-addon-pbos')
    merged = {r: {} for r in ROOTS}
    defined = {r: {} for r in ROOTS}
    models, listed = set(), []
    for p in pbos:
        if p.is_symlink() or not p.is_file():
            problems.append(f'{p.name}: not a regular file')
            continue
        try:
            index = pbo_config.read_pbo_index(p)
            members = pbo_config.read_config_members(p, ROOTS, index=index)
        except Exception as e:  # corrupt/oversized input is reported, never trusted
            problems.append(f'{p.name}: {type(e).__name__}: {str(e)[:120]}')
            continue
        row = {'name': p.name, 'size': index['size'], 'prefix': index['prefix']}
        if whole_hash:
            row['sha256'] = snafu_optional._pbo_sha256(p)
        listed.append(row)
        models |= pbo_config.model_paths(index)
        for member, configs in members:
            for r in ROOTS:
                for cname, row in configs[r].items():
                    defined[r].setdefault(cname, set()).add((p.name, member))
                    merged[r].setdefault(cname, row)
    duplicates = {r: {c for c, owners in defined[r].items() if len(owners) > 1} for r in ROOTS}
    return snafu_optional.canonical_config(merged), duplicates, models, listed


def load_vanilla(addons_dir, max_pbos=MAX_VANILLA_PBOS):
    """Vanilla loose-ammo magazines and bullet classes from the game's own addon PBOs (read-only)."""
    folder = _plain_dir(addons_dir, 'vanilla addons')
    pbos = sorted(p for p in folder.iterdir() if p.name.lower().endswith('.pbo'))
    if len(pbos) > max_pbos:
        raise ValueError('vanilla addon PBO count exceeds budget')
    table = {r: {} for r in VANILLA_ROOTS}
    table['problems'], table['pbo_count'], table['models'] = [], len(pbos), set()
    for p in pbos:
        if p.is_symlink() or not p.is_file():
            table['problems'].append(f'{p.name}: not a regular file')
            continue
        try:
            index = pbo_config.read_pbo_index(p)
            configs = pbo_config.read_configs(p, VANILLA_ROOTS, index=index)
            table['models'].update(pbo_config.model_paths(index))
        except Exception as e:
            table['problems'].append(f'{p.name}: {type(e).__name__}: {str(e)[:120]}')
            continue
        for r in VANILLA_ROOTS:
            for cname, row in configs[r].items():
                table[r].setdefault(cname, row)
    return table


def _terms(root, rights):
    result = {'file': rights['terms_file'], 'present': False, 'sha256': None, 'matches_reviewed': False,
              'reviewed_sha256': rights['terms_sha256']}
    node = root
    try:
        for part in rights['terms_file'].split('/'):
            node = _child_ci(node, part)
            if node is None or node.is_symlink():
                return result
        data = _read_small(node, MAX_TERMS_BYTES)
    except OSError:
        return result
    if data is not None:
        result.update(present=True, sha256=hashlib.sha256(data).hexdigest())
        result['matches_reviewed'] = result['sha256'] == rights['terms_sha256']
    return result


def _array(classes, name, field):
    """(first array found up the parent chain or None, whether that declaration only appended)."""
    seen = set()
    while name in classes and name not in seen and len(seen) < 128:
        seen.add(name)
        row = classes[name]
        if row.get(field) is not None:
            return row[field], field in row.get('appended', ())
        name = row.get('parent')
        if not name:
            break
    return None, False


def _common(entry, classes, root, duplicates, models, reasons, notes):
    name = entry['class']
    if name in duplicates[root]:
        reasons.append('multiple-definitions')
    scope = pbo_config.resolve_scope(classes, name)
    if scope is None:
        reasons.append('scope-unresolved')
    elif scope < 2:
        reasons.append(f'scope-{scope}-not-public')
    model = pbo_config.resolve_field(classes, name, 'model')
    if model is None:
        (notes if entry['kind'] == 'magazine' else reasons).append('model-unresolved')
    elif pbo_config.normalize_path(model) not in models:
        (notes if entry['kind'] == 'magazine' else reasons).append('model-missing-from-pbos')


def _need(array, appended, item, reason, reasons):
    if array is None or item not in array:
        reasons.append(f'array-append-unresolved:{reason[0]}' if appended else reason[1])


def _evaluate(entry, merged, duplicates, models, vanilla, state):
    kind, name = entry['kind'], entry['class']
    root = {'weapon': 'CfgWeapons', 'magazine': 'CfgMagazines', 'ammo': 'CfgMagazines'}.get(kind, 'CfgVehicles')
    classes = merged[root]
    reasons, notes = [], []
    if name not in classes:
        return {'status': 'missing', 'reasons': [f'not-defined-in-{root}'], 'notes': []}
    _common(entry, classes, root, duplicates, models, reasons, notes)
    if kind in {'magazine', 'ammo'}:
        bullet = pbo_config.resolve_field(classes, name, 'ammo')
        if bullet is None or (bullet not in vanilla['CfgAmmo'] and bullet not in merged['CfgAmmo']):
            reasons.append(f'bullet-class-missing:{bullet}')
    elif kind in {'optic', 'attachment'}:
        slots, _app = _array(classes, name, 'inventorySlot')
        if slots is None:
            reasons.append('inventory-slot-unresolved')
        elif entry['slot'] not in slots:
            reasons.append(f'slot-mismatch:{entry["slot"]}')
        for w in entry['fits']:
            if w not in merged['CfgWeapons']:
                reasons.append(f'fits-class-missing:{w}')
                continue
            attach, appended = _array(merged['CfgWeapons'], w, 'attachments')
            _need(attach, appended, entry['slot'], ('attachments', f'weapon-lacks-slot:{w}:{entry["slot"]}'),
                  reasons)
    else:
        mags, mags_app = _array(classes, name, 'magazines')
        chamber, chamber_app = _array(classes, name, 'chamberableFrom')
        allowed = set()
        for a in entry['vanilla_ammo']:
            _need(chamber, chamber_app, a, ('chamberableFrom', f'ammo-not-chamberable:{a}'), reasons)
            if a in vanilla['CfgMagazines']:
                allowed.add(pbo_config.resolve_field(vanilla['CfgMagazines'], a, 'ammo'))
            elif a in merged['CfgMagazines'] and state.get(a) == 'verified':
                allowed.add(pbo_config.resolve_field(merged['CfgMagazines'], a, 'ammo'))
            else:
                reasons.append(f'ammo-not-in-vanilla:{a}')
        for m in entry['magazines']:
            _need(mags, mags_app, m, ('magazines', f'magazine-not-accepted:{m}'), reasons)
            if state.get(m) != 'verified':
                reasons.append(f'magazine-unverified:{m}')
            if m in merged['CfgMagazines'] \
                    and pbo_config.resolve_field(merged['CfgMagazines'], m, 'ammo') not in allowed:
                reasons.append(f'magazine-bullet-mismatch:{m}')
        for need in entry['optic_requires']:
            if state.get(need) != 'verified':
                reasons.append(f'optic-requires-unverified:{need}')
    result = {'status': 'unverified' if reasons else 'verified', 'reasons': reasons, 'notes': notes}
    if kind == 'ammo':
        result['unit_rounds'] = pbo_config.resolve_field(classes, name, 'count')
    if kind == 'weapon':
        result['compatible_magazines'] = [m for m in (mags or []) if m]
    return result


def verify_install(install, allowlist, vanilla=None, max_pbos=MAX_PBOS, evidence_root=None):
    """Read-only, bounded verification of an installed Tactical Flava copy against the allowlist."""
    validate_allowlist(allowlist)
    root = _plain_dir(install, 'install')
    problems = []
    meta = _read_small(_child_ci(root, 'meta.cpp'), MAX_META_BYTES)
    published = None
    if meta is None:
        problems.append('meta-missing')
    else:
        found = re.search(rb'publishedid\s*=\s*([0-9]+)\s*;', meta)
        published = found.group(1).decode() if found else None
        if published != WORKSHOP_ID:
            problems.append('publishedid-mismatch')
    merged, duplicates, models, listed = _load_addons(root, problems, max_pbos,
                                                      whole_hash=snafu_optional._needs_whole_hash(allowlist))
    pack_weapons = set(merged['CfgWeapons'])
    merged = snafu_optional.native_parents(merged, vanilla)
    evidence = _plain_dir(evidence_root, 'Workshop evidence') if evidence_root is not None else root
    terms = _terms(evidence, allowlist['rights'])
    if not terms['present']:
        problems.append('terms-file-missing')
    elif not terms['matches_reviewed']:
        problems.append('terms-changed-since-review')
    class_hashes = snafu_optional.subset_pins(allowlist, merged)
    snafu_optional._check_pins(allowlist, listed, problems, class_hashes)
    warnings = snafu_optional.dependency_warnings(allowlist, listed)
    if vanilla is None:
        problems.append('vanilla-not-provided')
        vanilla_report = {'checked': False, 'problems': [], 'magazines': 0, 'ammo': 0}
        vanilla = {'CfgMagazines': {}, 'CfgAmmo': {}}
    else:
        models |= vanilla.get('models', set())
        vanilla_report = {'checked': True, 'problems': list(vanilla.get('problems', [])),
                          'magazines': len(vanilla['CfgMagazines']), 'ammo': len(vanilla['CfgAmmo'])}
    order = {'ammo': 0, 'magazine': 0, 'optic': 1, 'attachment': 1, 'weapon': 2}
    state, classes = {}, {}
    for entry in sorted(allowlist['entries'], key=lambda e: order[e['kind']]):
        row = _evaluate(entry, merged, duplicates, models, vanilla, state)
        state[entry['class']] = row['status']
        classes[entry['class']] = row
    counts = {s: sum(1 for r in classes.values() if r['status'] == s) for s in ('verified', 'missing', 'unverified')}
    ok = not problems and counts['verified'] == len(classes)
    return {'schema': 1, 'kind': 'tactical-flava-verification', 'status': 'verified' if ok else 'unverified',
            'workshop_id': WORKSHOP_ID, 'allowlist_sha256': allowlist_sha256(allowlist),
            'install': {'name': root.name, 'publishedid': published, 'problems': problems,
                        'warnings': warnings, 'pbos': listed},
            'dependency_changed': bool(warnings), 'subset_pins': class_hashes, 'subset_pins_scope': snafu_optional.SUBSET_PIN_SCOPE,
            'allowlist': allowlist, 'terms': terms, 'vanilla': vanilla_report, 'classes': dict(sorted(classes.items())),
            'counts': counts,
            'basis': 'static read-only: meta.cpp, PBO headers, config.bin/config.cpp members, vendor readme hash, '
                     'vanilla loose-ammo and bullet classes',
            'subset': {'authored_weapons': sum(e['kind'] == 'weapon' for e in allowlist['entries']),
                       'static_verified_weapons': sum(e['kind'] == 'weapon' and classes[e['class']]['status'] == 'verified'
                                                      for e in allowlist['entries']),
                       'installed_public_weapons': sum((pbo_config.resolve_scope(merged['CfgWeapons'], name) or 0) >= 2
                                                       for name in pack_weapons),
                       'runtime_accepted_weapons': 0, 'full_pack_admitted': False},
            'runtime_acceptance': 'pending'}


# ------------------------------------------------------------------ generation

def _check_report(allowlist, report):
    if not isinstance(report, dict) or report.get('status') != 'verified' \
            or report.get('kind') != 'tactical-flava-verification':
        raise ValueError('no verified Tactical Flava install report; refusing to generate (fail closed)')
    if report.get('allowlist_sha256') != allowlist_sha256(allowlist) or report.get('workshop_id') != WORKSHOP_ID:
        raise ValueError('verification report does not match this allowlist')
    install, terms, rows = report.get('install'), report.get('terms'), report.get('classes')
    vanilla = report.get('vanilla')
    if (not isinstance(install, dict) or install.get('problems') != [] or not isinstance(terms, dict)
            or terms.get('matches_reviewed') is not True or not isinstance(rows, dict)
            or not isinstance(vanilla, dict) or vanilla.get('checked') is not True):
        raise ValueError('verification report is incomplete')
    wanted = {e['class'] for e in allowlist['entries']}
    if set(rows) != wanted or any(not isinstance(r, dict) or r.get('status') != 'verified' for r in rows.values()):
        raise ValueError('every allowlisted class must be individually verified')
    for e in allowlist['entries']:
        if e['kind'] == 'weapon' and not isinstance(report['classes'][e['class']].get('compatible_magazines'), list):
            raise ValueError('verification report lacks compatible magazine evidence; reverify the installed copy')


_checked_core = ce_extensions.checked_core


def _new_type(entry):
    s = entry['set']
    item = ET.Element('type', {'name': entry['class']})
    for tag in ('nominal', 'lifetime', 'restock', 'min'):
        ET.SubElement(item, tag).text = str(s[tag])
    magazine = entry['kind'] == 'magazine'
    ET.SubElement(item, 'quantmin').text = '30' if magazine else '-1'
    ET.SubElement(item, 'quantmax').text = '70' if magazine else '-1'
    ET.SubElement(item, 'cost').text = '100'
    ET.SubElement(item, 'flags', {'count_in_cargo': '0', 'count_in_hoarder': '0', 'count_in_map': '1',
                                  'count_in_player': '0', 'crafted': '0', 'deloot': '0'})
    ET.SubElement(item, 'category', {'name': 'weapons'})
    for u in entry['usage']:
        ET.SubElement(item, 'usage', {'name': u})
    for v in entry['value']:
        ET.SubElement(item, 'value', {'name': v})
    return item


def _spawnable_types(entries):
    """Author only preattachments declared by individually verified allowlist rows."""
    rows = {e['class']: e for e in entries}
    root = ET.Element('spawnabletypes')
    for e in entries:
        if e['kind'] != 'weapon' or e['set']['nominal'] <= 0 or not e['optic_requires']:
            continue
        node = ET.SubElement(root, 'type', {'name': e['class']})
        attachments = ET.SubElement(node, 'attachments', {'chance': '1.00'})
        for name in e['optic_requires']:
            attachment = rows.get(name)
            if not attachment or attachment['kind'] != 'attachment' or e['class'] not in attachment['fits']:
                raise ValueError('spawnable attachment must be a verified attachment that fits the weapon')
            ET.SubElement(attachments, 'item', {'name': name, 'chance': '1.00'})
    return root


def generate(source, allowlist, report, nominal_scale=snafu_optional.DEFAULT_SCALE, tier_scales=None):
    validate_allowlist(allowlist)
    _check_report(allowlist, report)
    snafu_optional._check_hc61_report(allowlist, report)
    if nominal_scale is snafu_optional.DEFAULT_SCALE:
        nominal_scale = allowlist.get('test_abundance_multiplier', 1)
    entries, totals, scale_policy = snafu_optional._scaled_entries(allowlist['entries'], nominal_scale, tier_scales)
    data = economy.snapshot(source)
    core = _checked_core(data['cfgeconomycore.xml'])
    stock = economy._unique(economy.xml(data['db/types.xml'], 'types').findall('type'))
    taken = set(stock) | set(ce_extensions.registered_types(source, core))
    limits = economy.xml(data['cfglimitsdefinition.xml'], 'lists')
    usage_vocab = set(economy._unique(limits.findall('./usageflags/usage')))
    value_vocab = set(economy._unique(limits.findall('./valueflags/value')))
    out = ET.Element('types')
    rows = []
    for entry in entries:
        name = entry['class']
        ce_extensions.refuse_collisions([name], taken)
        if any(u not in usage_vocab for u in entry['usage']) or any(v not in value_vocab for v in entry['value']):
            raise ValueError(f'unknown usage/value tag: {name}')
        item = _new_type(entry)
        economy._validate_budget(item)
        out.append(item)
        row = {k: entry[k] for k in ('class', 'kind', 'role', 'tier', 'set', 'usage', 'value', 'justification')}
        row.update({k: entry[k] for k in ('vanilla_ammo', 'magazines', 'optic_requires', 'slot', 'fits')
                    if k in entry})
        row['verification'] = report['classes'][name]['status']
        rows.append(row)
    firearms.check_effective_support(source, stock, entries, out, (economy.MANAGED, SNAFU_MANAGED),
                                     ammo_fields=('vanilla_ammo',), verification=report['classes'])
    family_status = snafu_optional._check_family_delta(allowlist, entries, out, source, MANAGED)
    fragment = ET.Element('economycore')
    ce = ET.SubElement(fragment, 'ce', {'folder': MANAGED + '/ce'})
    ET.SubElement(ce, 'file', {'name': 'types.xml', 'type': 'types'})
    ET.SubElement(ce, 'file', {'name': 'cfgspawnabletypes.xml', 'type': 'spawnabletypes'})
    meta = {'schema': 1, 'kind': KIND, 'profile': allowlist['name'],
            'status': 'offline-only-runtime-pending', 'runtime_acceptance': 'pending',
            'workshop_id': WORKSHOP_ID, 'engine_merge_semantics': 'unobserved', 'loot_fix_claim': False,
            'dependency': 'optional; server and every client must load Tactical Flava; never bundled or repacked',
            'allowlist_sha256': allowlist_sha256(allowlist), 'entries': rows, 'totals': totals,
            'rights': allowlist['rights'], 'verification': report, 'pending': PENDING, **scale_policy,
            'allowlist': allowlist, 'hc61': family_status}
    files = {SPAWNABLE: xml_text.document(_spawnable_types(entries)) + b'\n',
             'ce/types.xml': xml_text.document(out) + b'\n',
             'cfgeconomycore.append.xml': xml_text.document(fragment) + b'\n',
             'core-defaults.patch.json': economy.encode({}), 'economy-report.json': economy.encode(meta)}
    files['delta-manifest.json'] = economy.encode({
        'schema': 1, 'kind': KIND, 'profile': allowlist['name'],
        'allowlist_sha256': allowlist_sha256(allowlist),
        **scale_policy,
        'sources': {n: economy.sha(d) for n, d in data.items()},
        'files': {n: economy.sha(d) for n, d in files.items()}, 'runtime_acceptance': 'pending'})
    return files


def write_delta(stage, files):
    """TF owns its expanded file set; the base economy delta remains unchanged."""
    stage = Path(stage)
    if set(files) != DELTA_FILES:
        raise ValueError('unexpected generated file set')
    if stage.exists() or stage.is_symlink():
        raise ValueError('output must be a fresh directory')
    for name in files:
        economy.child(stage, name)
    stage.mkdir(parents=True)
    for name, data in files.items():
        path = economy.child(stage, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _load_delta(stage):
    stage = Path(stage)
    found = set()
    for path in stage.rglob('*'):
        name = path.relative_to(stage).as_posix()
        economy.child(stage, name)
        if path.is_file():
            found.add(name)
        elif not path.is_dir():
            raise ValueError('special stage file')
    if found != DELTA_FILES:
        raise ValueError('unexpected or missing stage files')
    files = {name: economy.read_plain(stage, name) for name in found}
    manifest = json.loads(files['delta-manifest.json'])
    if (manifest.get('schema') != 1 or set(manifest.get('sources', {})) != set(economy.INPUTS)
            or set(manifest.get('files', {})) != DELTA_FILES - {'delta-manifest.json'}):
        raise ValueError('invalid delta manifest')
    if any(economy.sha(files[name]) != digest for name, digest in manifest['files'].items()):
        raise ValueError('delta checksum mismatch')
    return files, manifest


# ------------------------------------------------------------- install/rollback

def _patched_core(original, fragment, patches):
    if patches != {}:
        raise ValueError('Tactical Flava delta may not patch core defaults')
    core = _checked_core(original)
    frag = economy.xml(fragment, 'economycore')
    if (len(frag) != 1 or frag[0].tag != 'ce' or frag[0].attrib != {'folder': MANAGED + '/ce'}
            or len(frag[0]) != 2 or any(n.tag != 'file' for n in frag[0])
            or [n.attrib for n in frag[0]] != [{'name': 'types.xml', 'type': 'types'},
                                             {'name': 'cfgspawnabletypes.xml', 'type': 'spawnabletypes'}]):
        raise ValueError('unsupported CE registration')
    if any(ce.get('folder') == MANAGED + '/ce' for ce in core.findall('ce')):
        raise ValueError('CE folder already registered: ' + MANAGED + '/ce')
    closing = list(re.finditer(rb'</economycore\s*>', original))
    if len(closing) != 1 or core.tag != 'economycore':
        raise ValueError('ambiguous core closing tag')
    offset = closing[0].start()
    result = original[:offset] + b'\n' + ET.tostring(frag[0], encoding='utf-8') + b'\n' + original[offset:]
    economy.xml(result, 'economycore')
    return result


def install(stage, target):
    target = economy._target(target)
    files, manifest = _load_delta(stage)
    if manifest.get('kind') != KIND:
        raise ValueError('not a Tactical Flava optional delta')
    data = economy.snapshot(target)
    if {n: economy.sha(d) for n, d in data.items()} != manifest['sources']:
        raise ValueError('target source hashes differ; regenerate/reconcile')
    managed = economy.child(target, MANAGED)
    if os.path.lexists(managed):
        raise ValueError('already installed or interrupted installation; inspect/rollback first')
    meta = json.loads(files['economy-report.json'])
    verification = meta.get('verification')
    if not isinstance(verification, dict) or verification.get('status') != 'verified' \
            or verification.get('allowlist_sha256') != manifest.get('allowlist_sha256'):
        raise ValueError('delta lacks a matching verified report')
    original = data['cfgeconomycore.xml']
    patched = _patched_core(original, files['cfgeconomycore.append.xml'],
                            json.loads(files['core-defaults.patch.json']))
    types = economy.xml(files['ce/types.xml'], 'types')
    names = set(economy._unique(types.findall('type')))
    rows = verification.get('classes')
    if (not isinstance(rows, dict) or names != set(rows)
            or any(not isinstance(r, dict) or r.get('status') != 'verified' for r in rows.values())):
        raise ValueError('delta types must equal the individually verified classes')
    stock = economy._unique(economy.xml(data['db/types.xml'], 'types').findall('type'))
    taken = set(stock) | set(ce_extensions.registered_types(target, _checked_core(original)))
    ce_extensions.refuse_collisions(names, taken)
    limits = economy.xml(data['cfglimitsdefinition.xml'], 'lists')
    usage_vocab = set(economy._unique(limits.findall('./usageflags/usage')))
    value_vocab = set(economy._unique(limits.findall('./valueflags/value')))
    for item in types:
        economy._validate_budget(item)
        usages = item.findall('usage')
        if (not usages or any(u.get('name') not in usage_vocab or set(u.attrib) != {'name'} for u in usages)
                or any(v.get('name') not in value_vocab for v in item.findall('value'))):
            raise ValueError('invalid usage/value tags in delta')
    entries = meta.get('entries', [])
    if {e['class'] for e in entries} != names:
        raise ValueError('spawnable policy must cover the verified classes')
    firearms.check_effective_support(target, stock, entries, types, (economy.MANAGED, SNAFU_MANAGED),
                                     ammo_fields=('vanilla_ammo',), verification=rows)
    expected = _spawnable_types(entries)
    if economy._full(economy.xml(files[SPAWNABLE], 'spawnabletypes')) != economy._full(expected):
        raise ValueError('spawnable delta differs from verified attachment policy')
    snafu_optional._check_install_policy(meta, verification, types, target, MANAGED,
                                         validate_allowlist, _check_report)
    managed.mkdir()
    receipt = {'schema': 1, 'before': economy.sha(original), 'after': economy.sha(patched),
               'types_sha256': economy.sha(files['ce/types.xml']), 'sources': manifest['sources'],
               'nominal_scale': meta.get('nominal_scale', 1.0), 'tier_scales': meta.get('tier_scales', {}),
               'scale_decimal': meta.get('scale_decimal', {'nominal_scale': '1', 'tier_scales': {}}),
               'economy_report_sha256': economy.sha(files['economy-report.json']),
               'spawnable_sha256': economy.sha(files[SPAWNABLE]),
               'verification_sha256': economy.sha(economy.encode(verification))}
    try:
        os.replace(economy.fresh_write(managed, 'core.backup.next', original), managed / 'core.backup')  # never half-written
        economy.fresh_write(managed, 'receipt.json', economy.encode(receipt))
        economy.fresh_write(managed, 'verification.json', economy.encode(verification))
        (managed / 'ce').mkdir()
        economy.fresh_write(managed, 'ce/types.xml', files['ce/types.xml'])
        economy.fresh_write(managed, SPAWNABLE, files[SPAWNABLE])
        os.replace(economy.fresh_write(managed, 'core.next', patched), economy.child(target, 'cfgeconomycore.xml'))
    except OSError:
        # Receipt/backup precede the core switch. A failed write before that
        # switch has changed no mission input; remove only preflighted intent.
        if economy.read_plain(target, 'cfgeconomycore.xml') == original:
            economy.preflight_managed(managed, {'core.backup', 'core.backup.next', 'receipt.json', 'verification.json',
                                                'ce/types.xml', SPAWNABLE, 'core.next'})
            shutil.rmtree(managed)
        raise
    return receipt


def rollback(target):
    target = economy._target(target)
    managed = economy.child(target, MANAGED)
    with economy.refuse_missing(managed):
        outcome, receipt = economy.read_receipt_or_recover(
            target, managed, digests=('types_sha256', 'verification_sha256'), optional=('spawnable_sha256',))
        if outcome == economy.RECOVERED_BOOTSTRAP:
            return outcome
        expected_files = {'core.backup', 'receipt.json', 'verification.json', 'ce/types.xml', 'core.next'}
        if 'spawnable_sha256' in receipt:
            expected_files.add(SPAWNABLE)
        economy.preflight_managed(managed, expected_files)
        core = economy.plain_file(target, economy.child(target, 'cfgeconomycore.xml'))
        backup = economy.read_plain(managed, 'core.backup')
        core_sha = economy.sha(core.read_bytes())
        if economy.sha(backup) != receipt['before'] or core_sha not in {receipt['before'], receipt['after']}:
            raise ValueError('core drift (roll back later installs first); manual reconciliation required')
        # install order: verification.json, ce/types.xml, spawnable (absent before it existed), then the core switch
        delta = [('verification.json', 'verification_sha256', 'verification evidence drift; inspect before rollback'),
                 ('ce/types.xml', 'types_sha256', 'installed delta drift; inspect before rollback')]
        if 'spawnable_sha256' in receipt:
            delta.append((SPAWNABLE, 'spawnable_sha256', 'spawnable delta drift; inspect before rollback'))
        switched = economy.needs_restore(managed, receipt, core_sha, delta)
        if {n: economy.sha(economy.child(target, n).read_bytes()) for n in economy.INPUTS
                if n != 'cfgeconomycore.xml'} != {n: h for n, h in receipt['sources'].items()
                                                  if n != 'cfgeconomycore.xml'}:
            raise ValueError('stock drift; inspect before rollback')
        if switched:
            economy.restore_core(managed, core, backup)
        shutil.rmtree(managed)
        return economy.ROLLED_BACK


# ------------------------------------------------------------------------- CLI

def _refuse_git(path):
    path = Path(path).absolute().resolve()  # resolves symlinked ancestors that lead into a checkout
    for p in (path, *path.parents):
        if (p / '.git').exists():
            raise ValueError('refusing to write a verification report inside a Git checkout')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('verify', help='read-only check of an installed Tactical Flava copy')
    p.add_argument('--install', type=Path, required=True)
    p.add_argument('--vanilla-addons', type=Path, required=True, help='the game\'s own Addons folder (read-only)')
    p.add_argument('--allowlist', type=Path, default=ALLOWLIST_PATH)
    p.add_argument('--out', type=Path, required=True, help='report file; must be outside any Git checkout')
    p = sub.add_parser('generate')
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--allowlist', type=Path, default=ALLOWLIST_PATH)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    snafu_optional._add_scale_arguments(p)
    p = sub.add_parser('install')
    p.add_argument('--delta', type=Path, required=True)
    p.add_argument('--target', type=Path, required=True)
    p = sub.add_parser('rollback')
    p.add_argument('--target', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify':
            _refuse_git(args.out)
            if args.out.exists() or args.out.is_symlink():
                raise ValueError('report output must be a new file')
            allowlist = json.loads(args.allowlist.read_bytes())
            report = verify_install(args.install, allowlist, vanilla=load_vanilla(args.vanilla_addons))
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(economy.encode(report))
            print(f'{report["status"]}: {report["counts"]}')
            for name, row in report['classes'].items():
                print(f'  {row["status"]:10} {name} {" ".join(row["reasons"])}')
            for problem in report['install']['problems']:
                print(f'  install problem: {problem}')
            for warning in report['install']['warnings']:
                print(f'  install warning: {warning}')
            for problem in report['vanilla']['problems']:
                print(f'  vanilla note: {problem}')
            if report['status'] == 'verified' and not snafu_optional._subset_pinned(allowlist):
                print(snafu_optional.subset_pin_hint())
            return
        if args.command == 'generate':
            selected = json.loads(args.allowlist.read_bytes())
            files = generate(args.source, selected,
                             json.loads(args.report.read_bytes()), nominal_scale=args.nominal_scale,
                             tier_scales=snafu_optional._cli_tier_scales(args.tier_scale))
            write_delta(args.out, files)
            snafu_optional._print_scale_totals(json.loads(files['economy-report.json']))
        elif args.command == 'install':
            install(args.delta, args.target)
        else:
            if rollback(args.target) == economy.RECOVERED_BOOTSTRAP:
                print('Recovered an interrupted install: it never changed the core; managed directory removed.')
        print('Offline operation complete; DayZ runtime acceptance pending.')
    except (ValueError, OSError, KeyError, TypeError) as e:
        parser.exit(1, f'{e}\n')



def apply_weapon_packs(mission, packs, vanilla_addons, report_root, say=print):
    """Verify each local dependency, generate and install its CE layer independently.

    Reports/staging stay outside Git. Installed evidence/receipts use each writer's
    existing byte-exact rollback protocol. Call only on a stopped private mission;
    later layers must be removed before replacing this stack.
    """
    from tools.package import snafu_optional as sf
    report_root = Path(report_root)
    sf._refuse_git(report_root)
    report_root.mkdir(parents=True, exist_ok=True)
    failures = []
    vanilla = load_vanilla(vanilla_addons) if packs else None
    for label, writer in (('SNAFU', sf), ('TF', sys.modules[__name__])):
        install_root = packs.get(writer.WORKSHOP_ID)
        if install_root is None:
            say(f'optional weapons {label}: absent; skipped (no CE entries installed)')
            continue
        allowlist = json.loads(writer.ALLOWLIST_PATH.read_bytes())
        try:
            evidence_root = None
            if isinstance(install_root, dict):
                evidence_root = install_root['evidence']
                install_root = install_root['install']
            kwargs = {'vanilla': vanilla} if writer is sys.modules[__name__] else {'vanilla': vanilla}
            report = writer.verify_install(install_root, allowlist, evidence_root=evidence_root, **kwargs)
            report_path = report_root / (label + '-verification.json')
            if report_path.exists() or report_path.is_symlink():
                raise ValueError('verification output already exists; use a fresh report directory')
            report_path.write_bytes(economy.encode(report))
            if report['status'] != 'verified':
                details = report['install']['problems'][:8]
                details += [name + ': ' + ','.join(row['reasons'])
                            for name, row in report['classes'].items() if row['status'] != 'verified'][:8]
                for detail in details:
                    say(f'optional weapons {label}: verification refusal: {detail}')
            writer._check_report(allowlist, report)
            say(f'optional weapons {label}: verify {report["status"]} types={report["counts"]["verified"]}')
            stage = report_root / (label + '-delta')
            files = writer.generate(mission, allowlist, report)
            writer.write_delta(stage, files)
            meta = json.loads(files['economy-report.json'])
            say(f'optional weapons {label}: generate types={len(allowlist["entries"])} '
                f'firearm_nominal={meta["totals"]["weapon_nominal"]}')
            writer.install(stage, mission)
            say(f'optional weapons {label}: installed; receipt and rollback backup written; runtime=PENDING')
        except (OSError, ValueError, KeyError, TypeError) as error:
            # Never bypass a verification/generation refusal. Do not print local paths.
            detail = str(error) if isinstance(error, ValueError) else type(error).__name__
            say(f'optional weapons {label}: REFUSED (fail closed): {detail}')
            failures.append(label)
    return failures



def check_weapon_packs(mission, packs):
    """Read-only receipt/policy check, including a scratch reverse-stack rehearsal."""
    import tempfile
    mission = Path(mission)
    present = []
    for label, writer in (('SNAFU', snafu_optional), ('TF', sys.modules[__name__])):
        managed = mission / writer.MANAGED
        expected = writer.WORKSHOP_ID in packs
        if not expected and not os.path.lexists(managed):
            continue
        if not expected or not managed.is_dir() or managed.is_symlink():
            raise ValueError('optional weapons ' + label + ': dependency/layer mismatch; run installer')
        allowlist = json.loads(writer.ALLOWLIST_PATH.read_bytes())
        report = json.loads(economy.read_plain(managed, 'verification.json'))
        writer._check_report(allowlist, report)
        snafu_optional._check_hc61_report(allowlist, report)
        present.append(label)
    if present:
        with tempfile.TemporaryDirectory(prefix='hc-weapon-check-') as temporary:
            scratch = Path(temporary) / 'mission'
            shutil.copytree(mission, scratch, ignore=shutil.ignore_patterns('storage_*'), symlinks=True)
            rollback_weapon_packs(scratch)
    return present

def rollback_weapon_packs(mission):
    """Reverse the optional weapon stack before any earlier CE installer."""
    from tools.package import snafu_optional as sf
    for writer in (sys.modules[__name__], sf):
        if os.path.lexists(Path(mission) / writer.MANAGED):
            writer.rollback(mission)


if __name__ == '__main__':
    main()
