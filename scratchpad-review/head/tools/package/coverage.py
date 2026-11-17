"""Prepare conservative full-file CE point candidates from pinned diagnostic exports.

This does not install or claim engine eligibility. Export/log hashes bind operator
evidence, not its truth; review geometry and run native controls before deployment.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

try:
    from .economy import xml
    from .pbo import safe_name
except ImportError:
    from economy import xml
    from pbo import safe_name


def digest(data):
    return hashlib.sha256(data).hexdigest()


def named(nodes):
    result = {}
    for node in nodes:
        key = node.get('name')
        if not key or key in result:
            raise ValueError('missing or duplicate CE name')
        result[key] = node
    return result


def canonical(node):
    return (node.tag, tuple(sorted(node.attrib.items())), (node.text or '').strip(),
            tuple(canonical(child) for child in node))


def points(container):
    result = set()
    for point in container.findall('point'):
        if set(point.attrib) - {'pos', 'range', 'height', 'flags'} or 'pos' not in point.attrib or len(point):
            raise ValueError('unsupported CE point fields')
        try:
            position = tuple(float(n) for n in point.get('pos').split())
            if len(position) != 3 or any(not math.isfinite(n) or abs(n) > 1000 for n in position):
                raise ValueError('invalid local point position')
            for field in ('range', 'height'):
                value = float(point.get(field, '0'))
                if not math.isfinite(value) or not 0 <= value <= 100:
                    raise ValueError('invalid point dimensions')
        except (TypeError, OverflowError) as exc:
            raise ValueError('invalid point number') from exc
        if position in result:
            raise ValueError('duplicate point position')
        result.add(position)
        if 'flags' in point.attrib and not re.fullmatch('[0-9]{1,5}', point.get('flags')):
            raise ValueError('invalid point flags')
    return result


def shell(node, excluded):
    result = copy.deepcopy(node)
    result.attrib.pop('lootmax', None)
    for child in list(result):
        if child.tag in excluded:
            result.remove(child)
    return canonical(result)


def budget(node):
    value = node.get('lootmax')
    if value is None or not re.fullmatch('[0-9]{1,5}', value):
        raise ValueError('explicit bounded lootmax required on changed groups/containers')
    return int(value)


def prepare(stock, exported, evidence, artifacts):
    required = {'schema', 'world', 'build', 'source_sha256', 'export_sha256', 'groups', 'observations'}
    if (not isinstance(evidence, dict) or set(evidence) != required
            or type(evidence['schema']) is not int or evidence['schema'] != 1
            or evidence['world'] != 'chernarusplus'
            or not isinstance(evidence['build'], str)
            or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', evidence['build'])
            or evidence['source_sha256'] != digest(stock)
            or evidence['export_sha256'] != digest(exported)):
        raise ValueError('invalid schema/build/world or source/export hash mismatch')
    requested = evidence['groups']
    observations = evidence['observations']
    if (not isinstance(requested, list) or not 1 <= len(requested) <= 32
            or any(not isinstance(n, str) or not n for n in requested)
            or len(set(requested)) != len(requested)
            or not isinstance(observations, list) or not 1 <= len(observations) <= 32):
        raise ValueError('bounded unique groups and observations required')
    observed = set()
    for item in observations:
        if not isinstance(item, dict) or set(item) != {'path', 'sha256'}:
            raise ValueError('invalid observation')
        name = safe_name(item['path'])
        if name.casefold() in observed or name not in artifacts:
            raise ValueError('duplicate or missing observation')
        observed.add(name.casefold())
        data = artifacts[name]
        if not isinstance(data, bytes) or not 0 < len(data) <= 16 * 1024 * 1024 or digest(data) != item['sha256']:
            raise ValueError('invalid observation bytes/hash')
    before, after = xml(stock, 'prototype'), xml(exported, 'prototype')
    old, new = named(before.findall('group')), named(after.findall('group'))
    if set(old) != set(new) or not set(requested) <= set(old) or shell(before, {'group'}) != shell(after, {'group'}):
        raise ValueError('export changes group set or prototype fields')
    changed, added = [], 0
    for name in old:
        a, b = old[name], new[name]
        if canonical(a) == canonical(b):
            if name in requested:
                raise ValueError('requested group has no change')
            continue
        if name not in requested or shell(a, {'container'}) != shell(b, {'container'}):
            raise ValueError('unrequested group or non-point policy change')
        ca, cb = named(a.findall('container')), named(b.findall('container'))
        if set(ca) != set(cb):
            raise ValueError('container set changes are unsupported')
        group_added = 0
        old_max, new_max = budget(a), budget(b)
        if new_max < old_max or new_max > old_max + 32:
            raise ValueError('group lootmax must be a minimal nondecreasing change')
        for key in ca:
            left, right = ca[key], cb[key]
            if shell(left, {'point'}) != shell(right, {'point'}):
                raise ValueError('container categories/policy changed')
            existing, candidate = points(left), points(right)
            # Existing point metadata must also remain unchanged, not merely positions.
            old_nodes = {canonical(p) for p in left.findall('point')}
            new_nodes = {canonical(p) for p in right.findall('point')}
            if not existing <= candidate or not old_nodes <= new_nodes:
                raise ValueError('existing points removed or changed')
            count = len(candidate) - len(existing)
            group_added += count
            if canonical(left) != canonical(right):
                lo, hi = budget(left), budget(right)
                if hi < lo or hi > lo + count or hi > len(candidate):
                    raise ValueError('container lootmax exceeds added opportunities')
        if not 1 <= group_added <= 32 or new_max > old_max + group_added:
            raise ValueError('point-only patch requires 1..32 added points per group')
        changed.append(name)
        added += group_added
    if set(changed) != set(requested):
        raise ValueError('requested/exported changes differ')
    # Preserve untouched stock nodes and root ordering; replace changed groups only.
    for index, node in enumerate(list(before)):
        if node.tag == 'group' and node.get('name') in changed:
            before.remove(node)
            before.insert(index, copy.deepcopy(new[node.get('name')]))
    candidate = ET.tostring(before, encoding='utf-8', xml_declaration=True) + b'\n'
    return candidate, {'schema': 1, 'status': 'candidate-native-validation-required',
                       'changed_groups': sorted(changed), 'added_raw_points': added,
                       'engine_eligibility_verified': False, 'evidence': copy.deepcopy(evidence),
                       'candidate_sha256': digest(candidate)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock', required=True, type=Path)
    parser.add_argument('--export', dest='exported', required=True, type=Path)
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--artifacts', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try:
        e = json.loads(args.evidence.read_text())
        artifacts = {}
        root = args.artifacts.absolute()
        for item in e.get('observations', []):
            name = safe_name(item['path'])
            path = root / name
            if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
                raise ValueError('observation must be a regular file without symlink ancestors')
            if path.stat().st_size > 16 * 1024 * 1024:
                raise ValueError('observation too large')
            artifacts[name] = path.read_bytes()
        candidate, report = prepare(args.stock.read_bytes(), args.exported.read_bytes(), e, artifacts)
        # A fresh review directory only. Never writes the stock input or installs.
        if any(p.is_symlink() for p in (args.out, *args.out.absolute().parents)):
            raise ValueError('symlink output forbidden')
        args.out.mkdir()
        (args.out / 'mapgroupproto.xml').write_bytes(candidate)
        (args.out / 'coverage-report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
        print(json.dumps({'status': report['status'], 'added_raw_points': report['added_raw_points']}))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
