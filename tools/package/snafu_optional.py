"""Optional SNAFU Weapons (Workshop 2443122116) dependency: read-only verifier and fail-closed CE delta.

The base Hollow Country addon never depends on this module or on SNAFU. SNAFU files are never copied,
bundled or re-hosted (the item is licensed DPL-ND: server use allowed, no repack/reupload). The verifier
only reads an operator's own installed copy (meta.cpp, bounded PBO headers and config.bin members,
the vendor class list and the terms file hash) and writes a report outside Git.

Generation is fail-closed: with no report, an unverified report, a report for a different allowlist,
or any class not individually verified, no spawn entries are produced. The delta registers a separate
managed folder (``hollow-country-snafu/ce``) with complete new ``types.xml`` entries only; it installs
on top of, and rolls back before (last in, first out), the vanilla roster delta.

Offline static checks establish nothing about DayZ behaviour: weapon firing, ammo acceptance, model
loading, signature checks, CE spawning and the 3-6 player balance stay pending local acceptance.
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
    from tools.package import economy
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.audit import pbo_config
    from tools.package import economy

ALLOWLIST_PATH = Path(__file__).with_name('snafu_allowlist.json')
WORKSHOP_ID = '2443122116'
MANAGED = 'hollow-country-snafu'
ROOTS = ('CfgWeapons', 'CfgMagazines', 'CfgAmmo')
TOP = {'schema', 'name', 'workshop_id', 'status', 'rights', 'entries', 'excluded'}
RIGHTS_REQUIRED = {'license', 'terms_file', 'terms_sha256', 'urls', 'redistribution'}
RIGHTS_OPTIONAL = {'notes'}
ENTRY_REQUIRED = {'class', 'kind', 'role', 'tier', 'set', 'usage', 'value', 'justification'}
WEAPON_EXTRA = {'vanilla_ammo', 'snafu_ammo', 'magazines'}
KINDS = {'weapon': {'wood', 'modern'}, 'magazine': {'support'}, 'ammo': {'support'}}
TIERS = {'common', 'uncommon', 'rare'}
SET_FIELDS = ('nominal', 'min', 'lifetime', 'restock')
CLASS = re.compile(r'[A-Za-z0-9_]{1,80}')
MAX_ENTRIES = 64
MAX_PBOS = 64
MAX_TERMS_BYTES = 8 * 1024 * 1024
MAX_VENDOR_BYTES = 8 * 1024 * 1024
MAX_META_BYTES = 4096
EXPECTED_ROOT_CE = economy.MANAGED + '/ce'
PENDING = ['normal PBO/server load with SNAFU installed on server and clients',
           'DayZDiag/local spawn, firing and ammo-acceptance trials per class',
           'CE spawn/error trials and 3-6-player budget measurement',
           'signature (bikey/bisign) validation on a signed server',
           'destination install/rollback on the real mission copy']


def allowlist_sha256(allowlist):
    return economy.sha(economy.encode(allowlist))


def _int(value, low):
    return type(value) is int and value >= low


def _names(value, name):
    if (not isinstance(value, list) or len(set(map(str, value))) != len(value)
            or any(not isinstance(v, str) or not CLASS.fullmatch(v) for v in value)):
        raise ValueError(f'invalid class list: {name}')


def validate_allowlist(allowlist):
    if not isinstance(allowlist, dict) or set(allowlist) != TOP or type(allowlist['schema']) is not int \
            or allowlist['schema'] != 1:
        raise ValueError('unsupported allowlist schema/fields')
    if not isinstance(allowlist['name'], str) or not re.fullmatch(r'[a-z0-9-]{1,64}', allowlist['name']):
        raise ValueError('invalid allowlist name')
    if allowlist['workshop_id'] != WORKSHOP_ID:
        raise ValueError('allowlist targets a different Workshop item')
    if allowlist['status'] != 'unverified':
        raise ValueError('a committed allowlist must stay unverified; verification is per install')
    rights = allowlist['rights']
    if (not isinstance(rights, dict) or not RIGHTS_REQUIRED <= set(rights) <= RIGHTS_REQUIRED | RIGHTS_OPTIONAL
            or rights['license'] != 'DPL-ND' or rights['redistribution'] != 'none'
            or not isinstance(rights['terms_file'], str)
            or not re.fullmatch(r'[0-9a-f]{64}', str(rights['terms_sha256']))
            or not isinstance(rights['urls'], list) or not rights['urls']
            or any(not isinstance(u, str) or not u.startswith('https://') for u in rights['urls'])):
        raise ValueError('invalid rights block')
    if 'notes' in rights and (not isinstance(rights['notes'], list)
                              or any(not isinstance(n, str) for n in rights['notes'])):
        raise ValueError('invalid rights notes')
    entries = allowlist['entries']
    if not isinstance(entries, list) or not 0 < len(entries) <= MAX_ENTRIES:
        raise ValueError('allowlist entries missing or over budget')
    by_kind, seen = {}, set()
    for e in entries:
        if not isinstance(e, dict):
            raise ValueError('invalid allowlist entry')
        kind = e.get('kind')
        needed = ENTRY_REQUIRED | (WEAPON_EXTRA if kind == 'weapon' else set())
        if set(e) != needed:
            raise ValueError(f'unsupported allowlist entry fields: {e.get("class")}')
        name = e['class']
        if not isinstance(name, str) or not CLASS.fullmatch(name):
            raise ValueError('invalid class name')
        if kind not in KINDS or e['role'] not in KINDS[kind] or e['tier'] not in TIERS:
            raise ValueError(f'invalid kind/role/tier: {name}')
        if name in seen:
            raise ValueError(f'duplicate allowlist class: {name}')
        seen.add(name)
        by_kind.setdefault(kind, set()).add(name)
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
        if kind == 'weapon':
            for field in WEAPON_EXTRA:
                _names(e[field], name)
    for e in entries:
        if e['kind'] == 'weapon':
            if not set(e['snafu_ammo']) <= by_kind.get('ammo', set()) \
                    or not set(e['magazines']) <= by_kind.get('magazine', set()):
                raise ValueError(f'unlisted ammo/magazine reference: {e["class"]}')
    excluded = allowlist['excluded']
    if not isinstance(excluded, list) or len(excluded) > MAX_ENTRIES:
        raise ValueError('invalid excluded list')
    for x in excluded:
        if (not isinstance(x, dict) or not {'group', 'reason'} <= set(x) <= {'group', 'reason', 'classes'}
                or not all(isinstance(x[k], str) and x[k].strip() for k in ('group', 'reason'))):
            raise ValueError('excluded groups need a group and a reason')
        if 'classes' in x:
            _names(x['classes'], x['group'])


# ---------------------------------------------------------------- verification

def _plain_dir(path, label):
    path = Path(path).absolute()
    if path.is_symlink():
        raise ValueError(f'{label} must not be a symlink')
    if not path.is_dir():
        raise ValueError(f'{label} is not a directory')
    return path


def _read_small(path, limit):
    if path.is_symlink() or not path.is_file():
        return None
    with open(path, 'rb') as handle:
        data = handle.read(limit + 1)
    return data if len(data) <= limit else None


def _safe_relative(text):
    parts = text.split('/')
    return (isinstance(text, str) and re.fullmatch(r'[A-Za-z0-9_ .\-/]{1,200}', text) is not None
            and all(p not in {'', '.', '..'} for p in parts))


def _vendor_names(root, problems):
    folder = root / 'XML_and_Clasnames'
    names = set()
    if folder.is_symlink() or not folder.is_dir():
        problems.append('vendor-types-missing')
        return names
    found = False
    for p in sorted(folder.iterdir()):
        low = p.name.lower()
        if not low.endswith('types.xml') or 'spawnable' in low:
            continue
        data = _read_small(p, MAX_VENDOR_BYTES)
        if data is None:
            problems.append(f'vendor-types-unreadable:{p.name}')
            continue
        try:
            for t in economy.xml(data, 'types').findall('type'):
                if t.get('name'):
                    names.add(t.get('name'))
            found = True
        except ValueError:
            problems.append(f'vendor-types-unreadable:{p.name}')
    if not found:
        problems.append('vendor-types-missing')
    return names


def _load_addons(root, problems, max_pbos):
    folder = root / 'Addons'
    pbos = []
    if not folder.is_symlink() and folder.is_dir():
        pbos = sorted(p for p in folder.iterdir() if p.name.lower().endswith('.pbo'))
    if len(pbos) > max_pbos:
        raise ValueError('addon PBO count exceeds budget')
    if not pbos:
        problems.append('no-addon-pbos')
    merged = {r: {} for r in ROOTS}
    owners = {r: {} for r in ROOTS}
    duplicates = {r: set() for r in ROOTS}
    models, listed = set(), []
    for p in pbos:
        if p.is_symlink() or not p.is_file():
            problems.append(f'{p.name}: not a regular file')
            continue
        try:
            index = pbo_config.read_pbo_index(p)
            configs = pbo_config.read_configs(p, ROOTS, index=index)
        except Exception as e:  # corrupt/oversized input is reported, never trusted
            problems.append(f'{p.name}: {type(e).__name__}: {str(e)[:120]}')
            continue
        listed.append({'name': p.name, 'size': index['size'], 'prefix': index['prefix']})
        models |= pbo_config.model_paths(index)
        for r in ROOTS:
            for cname, row in configs[r].items():
                if cname in owners[r] and owners[r][cname] != p.name:
                    duplicates[r].add(cname)
                    continue
                owners[r][cname] = p.name
                merged[r][cname] = row
    return merged, duplicates, models, listed


def _terms(root, rights):
    result = {'file': rights['terms_file'], 'present': False, 'sha256': None, 'matches_reviewed': False,
              'reviewed_sha256': rights['terms_sha256']}
    if not _safe_relative(rights['terms_file']):
        return result
    data = _read_small(root.joinpath(*rights['terms_file'].split('/')), MAX_TERMS_BYTES)
    if data is not None:
        result.update(present=True, sha256=hashlib.sha256(data).hexdigest())
        result['matches_reviewed'] = result['sha256'] == rights['terms_sha256']
    return result


def _evaluate(entry, merged, duplicates, models, vendor, state):
    kind, name = entry['kind'], entry['class']
    root = 'CfgWeapons' if kind == 'weapon' else 'CfgMagazines'
    classes = merged[root]
    reasons, notes = [], []
    if name not in classes:
        return {'status': 'missing', 'reasons': [f'not-defined-in-{root}'], 'notes': []}
    if name in duplicates[root]:
        reasons.append('multiple-definitions')
    scope = pbo_config.resolve_scope(classes, name)
    if scope is None:
        reasons.append('scope-unresolved')
    elif scope < 2:
        reasons.append(f'scope-{scope}-not-public')
    if name not in vendor:
        reasons.append('not-in-vendor-types')
    model = pbo_config.resolve_field(classes, name, 'model')
    if model is None:
        (reasons if kind == 'weapon' else notes).append('model-unresolved')
    elif pbo_config.normalize_path(model) not in models:
        reasons.append('model-missing-from-pbos')
    if kind == 'ammo':
        bullet = pbo_config.resolve_field(classes, name, 'ammo')
        if bullet is None or bullet not in merged['CfgAmmo']:
            reasons.append('bullet-class-missing')
    if kind == 'weapon':
        magazines = pbo_config.resolve_field(classes, name, 'magazines') or []
        chamber = pbo_config.resolve_field(classes, name, 'chamberableFrom') or []
        if '' in magazines:
            notes.append('empty-magazine-entry-ignored')
        for m in entry['magazines']:
            if m not in magazines:
                reasons.append(f'magazine-not-accepted:{m}')
            if state.get(m) != 'verified':
                reasons.append(f'magazine-unverified:{m}')
        for a in entry['vanilla_ammo'] + entry['snafu_ammo']:
            if a not in chamber:
                reasons.append(f'ammo-not-chamberable:{a}')
        for a in entry['snafu_ammo']:
            if state.get(a) != 'verified':
                reasons.append(f'ammo-unverified:{a}')
    return {'status': 'unverified' if reasons else 'verified', 'reasons': reasons, 'notes': notes}


def verify_install(install, allowlist, max_pbos=MAX_PBOS):
    """Read-only, bounded verification of an installed SNAFU Weapons copy against the allowlist."""
    validate_allowlist(allowlist)
    root = _plain_dir(install, 'install')
    problems = []
    meta = _read_small(root / 'meta.cpp', MAX_META_BYTES)
    published = None
    if meta is None:
        problems.append('meta-missing')
    else:
        found = re.search(rb'publishedid\s*=\s*([0-9]+)\s*;', meta)
        published = found.group(1).decode() if found else None
        if published != WORKSHOP_ID:
            problems.append('publishedid-mismatch')
    merged, duplicates, models, listed = _load_addons(root, problems, max_pbos)
    vendor = _vendor_names(root, problems)
    terms = _terms(root, allowlist['rights'])
    if not terms['present']:
        problems.append('terms-file-missing')
    elif not terms['matches_reviewed']:
        problems.append('terms-changed-since-review')
    entries = allowlist['entries']
    state, classes = {}, {}
    for entry in sorted(entries, key=lambda e: e['kind'] == 'weapon'):  # items before the weapons using them
        row = _evaluate(entry, merged, duplicates, models, vendor, state)
        state[entry['class']] = row['status']
        classes[entry['class']] = row
    counts = {s: sum(1 for r in classes.values() if r['status'] == s) for s in ('verified', 'missing', 'unverified')}
    ok = not problems and counts['verified'] == len(classes)
    return {'schema': 1, 'kind': 'snafu-verification', 'status': 'verified' if ok else 'unverified',
            'workshop_id': WORKSHOP_ID, 'allowlist_sha256': allowlist_sha256(allowlist),
            'install': {'name': root.name, 'publishedid': published, 'problems': problems, 'pbos': listed},
            'terms': terms, 'classes': dict(sorted(classes.items())), 'counts': counts,
            'basis': 'static read-only: meta.cpp, PBO headers/config.bin, vendor types, terms hash',
            'runtime_acceptance': 'pending'}


# ------------------------------------------------------------------ generation

def _check_report(allowlist, report):
    if not isinstance(report, dict) or report.get('status') != 'verified':
        raise ValueError('no verified SNAFU install report; refusing to generate (fail closed)')
    if report.get('allowlist_sha256') != allowlist_sha256(allowlist) or report.get('workshop_id') != WORKSHOP_ID:
        raise ValueError('verification report does not match this allowlist')
    install, terms, rows = report.get('install'), report.get('terms'), report.get('classes')
    if (not isinstance(install, dict) or install.get('problems') != [] or not isinstance(terms, dict)
            or terms.get('matches_reviewed') is not True or not isinstance(rows, dict)):
        raise ValueError('verification report is incomplete')
    wanted = {e['class'] for e in allowlist['entries']}
    if set(rows) != wanted or any(not isinstance(r, dict) or r.get('status') != 'verified' for r in rows.values()):
        raise ValueError('every allowlisted class must be individually verified')


def _roster_types(source):
    """Type names already registered by the vanilla roster managed folder (if installed)."""
    path = economy.child(source, economy.MANAGED + '/ce/types.xml')
    if not path.is_file():
        return set()
    return set(economy._unique(economy.xml(path.read_bytes(), 'types').findall('type')))


def _checked_core(data):
    core = economy.xml(data, 'economycore')
    for ce in core.findall('ce'):
        files = ce.findall('file')
        if (ce.attrib != {'folder': EXPECTED_ROOT_CE} or len(files) != 1
                or files[0].attrib != {'name': 'types.xml', 'type': 'types'}):
            raise ValueError('existing CE extensions need explicit operator reconciliation')
    if len(core.findall('ce')) > 1:
        raise ValueError('existing CE extensions need explicit operator reconciliation')
    return core


def _new_type(entry):
    s = entry['set']
    item = ET.Element('type', {'name': entry['class']})
    for tag in ('nominal', 'lifetime', 'restock', 'min'):
        ET.SubElement(item, tag).text = str(s[tag])
    ET.SubElement(item, 'quantmin').text = '-1'
    ET.SubElement(item, 'quantmax').text = '-1'
    ET.SubElement(item, 'cost').text = '100'
    ET.SubElement(item, 'flags', {'count_in_cargo': '0', 'count_in_hoarder': '0', 'count_in_map': '1',
                                  'count_in_player': '0', 'crafted': '0', 'deloot': '0'})
    ET.SubElement(item, 'category', {'name': 'weapons'})
    for u in entry['usage']:
        ET.SubElement(item, 'usage', {'name': u})
    for v in entry['value']:
        ET.SubElement(item, 'value', {'name': v})
    return item


def generate(source, allowlist, report):
    validate_allowlist(allowlist)
    _check_report(allowlist, report)
    data = economy.snapshot(source)
    _checked_core(data['cfgeconomycore.xml'])
    stock = set(economy._unique(economy.xml(data['db/types.xml'], 'types').findall('type')))
    taken = stock | _roster_types(source)
    limits = economy.xml(data['cfglimitsdefinition.xml'], 'lists')
    usage_vocab = set(economy._unique(limits.findall('./usageflags/usage')))
    value_vocab = set(economy._unique(limits.findall('./valueflags/value')))
    out = ET.Element('types')
    rows, totals = [], {'weapon_nominal': 0}
    for entry in allowlist['entries']:
        name = entry['class']
        if name in taken:
            raise ValueError(f'class already defined by stock or the vanilla roster: {name}')
        if any(u not in usage_vocab for u in entry['usage']) or any(v not in value_vocab for v in entry['value']):
            raise ValueError(f'unknown usage/value tag: {name}')
        item = _new_type(entry)
        economy._validate_budget(item)
        out.append(item)
        rows.append({'class': name, 'kind': entry['kind'], 'role': entry['role'], 'tier': entry['tier'],
                     'set': entry['set'], 'usage': entry['usage'], 'value': entry['value'],
                     'justification': entry['justification'],
                     'verification': report['classes'][name]['status']})
        if entry['kind'] == 'weapon':
            totals['weapon_nominal'] += entry['set']['nominal']
    fragment = ET.Element('economycore')
    ce = ET.SubElement(fragment, 'ce', {'folder': MANAGED + '/ce'})
    ET.SubElement(ce, 'file', {'name': 'types.xml', 'type': 'types'})
    meta = {'schema': 1, 'kind': 'snafu-optional', 'profile': allowlist['name'],
            'status': 'offline-only-runtime-pending', 'runtime_acceptance': 'pending',
            'workshop_id': WORKSHOP_ID, 'engine_merge_semantics': 'unobserved', 'loot_fix_claim': False,
            'dependency': 'optional; server and every client must load SNAFU Weapons; never bundled',
            'allowlist_sha256': allowlist_sha256(allowlist), 'entries': rows, 'totals': totals,
            'rights': allowlist['rights'], 'verification': report, 'pending': PENDING}
    files = {'ce/types.xml': ET.tostring(out, encoding='utf-8', xml_declaration=True) + b'\n',
             'cfgeconomycore.append.xml': ET.tostring(fragment, encoding='utf-8', xml_declaration=True) + b'\n',
             'core-defaults.patch.json': economy.encode({}), 'economy-report.json': economy.encode(meta)}
    files['delta-manifest.json'] = economy.encode({
        'schema': 1, 'kind': 'snafu-optional', 'profile': allowlist['name'],
        'allowlist_sha256': allowlist_sha256(allowlist),
        'sources': {n: economy.sha(d) for n, d in data.items()},
        'files': {n: economy.sha(d) for n, d in files.items()}, 'runtime_acceptance': 'pending'})
    return files


write_delta = economy.write_delta


# ------------------------------------------------------------- install/rollback

def _patched_core(original, fragment, patches):
    if patches != {}:
        raise ValueError('SNAFU delta may not patch core defaults')
    core = _checked_core(original)
    frag = economy.xml(fragment, 'economycore')
    if (len(frag) != 1 or frag[0].tag != 'ce' or frag[0].attrib != {'folder': MANAGED + '/ce'}
            or len(frag[0]) != 1 or frag[0][0].tag != 'file'
            or frag[0][0].attrib != {'name': 'types.xml', 'type': 'types'}):
        raise ValueError('unsupported CE registration')
    closing = list(re.finditer(rb'</economycore\s*>', original))
    if len(closing) != 1 or core.tag != 'economycore':
        raise ValueError('ambiguous core closing tag')
    offset = closing[0].start()
    result = original[:offset] + b'\n' + ET.tostring(frag[0], encoding='utf-8') + b'\n' + original[offset:]
    economy.xml(result, 'economycore')
    return result


def install(stage, target):
    target = economy._target(target)
    files, manifest = economy._load_delta(stage)
    if manifest.get('kind') != 'snafu-optional':
        raise ValueError('not a SNAFU optional delta')
    data = economy.snapshot(target)
    if {n: economy.sha(d) for n, d in data.items()} != manifest['sources']:
        raise ValueError('target source hashes differ; regenerate/reconcile')
    managed = economy.child(target, MANAGED)
    if managed.exists():
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
    taken = set(economy._unique(economy.xml(data['db/types.xml'], 'types').findall('type')))
    taken |= _roster_types(target)
    if names & taken:
        raise ValueError('delta redefines classes already defined by stock or the roster')
    limits = economy.xml(data['cfglimitsdefinition.xml'], 'lists')
    usage_vocab = set(economy._unique(limits.findall('./usageflags/usage')))
    value_vocab = set(economy._unique(limits.findall('./valueflags/value')))
    for item in types:
        economy._validate_budget(item)
        usages = item.findall('usage')
        if (not usages or any(u.get('name') not in usage_vocab or set(u.attrib) != {'name'} for u in usages)
                or any(v.get('name') not in value_vocab for v in item.findall('value'))):
            raise ValueError('invalid usage/value tags in delta')
    managed.mkdir()
    receipt = {'schema': 1, 'before': economy.sha(original), 'after': economy.sha(patched),
               'types_sha256': economy.sha(files['ce/types.xml']), 'sources': manifest['sources'],
               'verification_sha256': economy.sha(economy.encode(verification))}
    (managed / 'core.backup').write_bytes(original)
    (managed / 'receipt.json').write_bytes(economy.encode(receipt))
    (managed / 'verification.json').write_bytes(economy.encode(verification))
    (managed / 'ce').mkdir()
    (managed / 'ce/types.xml').write_bytes(files['ce/types.xml'])
    (managed / 'core.next').write_bytes(patched)
    os.replace(managed / 'core.next', economy.child(target, 'cfgeconomycore.xml'))
    return receipt


def rollback(target):
    target = economy._target(target)
    managed = economy.child(target, MANAGED)
    receipt = json.loads(economy.child(managed, 'receipt.json').read_bytes())
    expected = {'core.backup', 'receipt.json', 'verification.json', 'ce/types.xml', 'core.next'}
    for p in managed.rglob('*'):
        name = p.relative_to(managed).as_posix()
        economy.child(managed, name)
        if p.is_file() and name not in expected:
            raise ValueError('unexpected managed file; rollback refuses deletion')
    core = economy.child(target, 'cfgeconomycore.xml')
    backup = economy.child(managed, 'core.backup').read_bytes()
    if economy.sha(backup) != receipt['before'] \
            or economy.sha(core.read_bytes()) not in {receipt['before'], receipt['after']}:
        raise ValueError('core drift (roll back later installs first); manual reconciliation required')
    if economy.sha(economy.child(managed, 'ce/types.xml').read_bytes()) != receipt['types_sha256']:
        raise ValueError('installed delta drift; inspect before rollback')
    if {n: economy.sha(economy.child(target, n).read_bytes()) for n in economy.INPUTS
            if n != 'cfgeconomycore.xml'} != {n: h for n, h in receipt['sources'].items()
                                              if n != 'cfgeconomycore.xml'}:
        raise ValueError('stock drift; inspect before rollback')
    (managed / 'core.next').write_bytes(backup)
    os.replace(managed / 'core.next', core)
    shutil.rmtree(managed)


# ------------------------------------------------------------------------- CLI

def _refuse_git(path):
    path = Path(path).absolute()
    for p in (path, *path.parents):
        if (p / '.git').exists():
            raise ValueError('refusing to write a verification report inside a Git checkout')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('verify', help='read-only check of an installed SNAFU Weapons copy')
    p.add_argument('--install', type=Path, required=True)
    p.add_argument('--allowlist', type=Path, default=ALLOWLIST_PATH)
    p.add_argument('--out', type=Path, required=True, help='report file; must be outside any Git checkout')
    p = sub.add_parser('generate')
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--allowlist', type=Path, default=ALLOWLIST_PATH)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
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
            report = verify_install(args.install, json.loads(args.allowlist.read_bytes()))
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(economy.encode(report))
            print(f'{report["status"]}: {report["counts"]}')
            for name, row in report['classes'].items():
                print(f'  {row["status"]:10} {name} {" ".join(row["reasons"])}')
            for problem in report['install']['problems']:
                print(f'  install problem: {problem}')
            return
        if args.command == 'generate':
            write_delta(args.out, generate(args.source, json.loads(args.allowlist.read_bytes()),
                                           json.loads(args.report.read_bytes())))
        elif args.command == 'install':
            install(args.delta, args.target)
        else:
            rollback(args.target)
        print('Offline operation complete; DayZ runtime acceptance pending.')
    except (ValueError, OSError, KeyError, TypeError) as e:
        parser.exit(1, f'{e}\n')


if __name__ == '__main__':
    main()
