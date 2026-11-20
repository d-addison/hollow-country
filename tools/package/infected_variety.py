"""HC-14 restart-bound child substitution; offline installation, runtime PENDING.

Stop the server. Supply installed stock db/events.xml, pinned in variants.json.
Only authored donor rows change; all other bytes (including comments/CRLF) are
retained, except a missing/nonstandard XML declaration is normalized through
xml_text to the double-quoted UTF-8 form. No CE extension is registered.
Off and rollback restore the original bytes, including the original declaration.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET
from xml.parsers import expat

from tools.package import economy, xml_text
from tools.package.optional_overlays import atomic, mission_target, read, safe

POLICY = Path(__file__).resolve().parents[2] / 'mission/hollow-country/infected/variants.json'
MANAGED = 'hollow-country-infected'
TARGET = 'db/events.xml'


def _signature(node):
    return (node.tag, sorted(node.attrib.items()), (node.text or '').strip(),
            tuple(_signature(c) for c in node))


def _events(data):
    root = economy.xml(data, 'events')
    return economy._unique(root.findall('event'))


def _spans(data):
    """Locate direct event child rows with Expat byte offsets, not XML regexes."""
    parser = expat.ParserCreate()
    stack = []
    rows = {}
    event = None
    pending = None

    def start(name, attrs):
        nonlocal event, pending
        if stack == ['events'] and name == 'event':
            event = attrs.get('name')
        if stack == ['events', 'event', 'children'] and name == 'child':
            pending = (event, attrs.get('type'), parser.CurrentByteIndex)
        stack.append(name)

    def end(name):
        nonlocal pending
        if stack == ['events', 'event', 'children', 'child']:
            event_name, type_name, begin = pending
            finish = parser.CurrentByteIndex
            # For <child/> Expat reports the following byte. For paired tags
            # it reports the beginning of </child>; that end tag has no attrs.
            if not data[begin:finish].rstrip().endswith(b'/>'):
                finish = data.index(b'>', finish) + 1
            rows[(event_name, type_name)] = (begin, finish)
            pending = None
        stack.pop()

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.Parse(data, True)
    return rows


def substitute(original, stock, policy):
    """Require stock-identical targeted events; preserve other mission content."""
    if economy.sha(stock) != policy['evidence']['stock_events_sha256']:
        raise ValueError('installed stock hash does not match pinned stock events')
    expected, current = _events(stock), _events(original)
    substitutions = policy['substitutions']
    targets = {s['event'] for s in substitutions}
    for name in targets:
        if name not in expected or name not in current:
            raise ValueError('missing stock target event: ' + name)
        if _signature(current[name]) != _signature(expected[name]):
            raise ValueError('target event differs from expected stock: ' + name)
        if len(current[name].findall('children')) != 1:
            raise ValueError('stock target needs one children element: ' + name)
        economy._unique(current[name].findall('./children/child'), 'type')
    spans = _spans(original)
    replacements = {}
    destinations = set()
    donors = {(r['event'], r['from']) for r in substitutions}
    changed = {}
    additions = {}
    for row in substitutions:
        name, donor, variant, share = row['event'], row['from'], row['to'], row['share']
        key, destination = (name, donor), (name, variant)
        if destination in destinations or destination in donors:
            raise ValueError('duplicate destination or donor/destination overlap')
        destinations.add(destination)
        children = economy._unique(current[name].findall('./children/child'), 'type')
        if donor not in children or key not in spans:
            raise ValueError('stock donor missing: ' + name)
        child = changed.setdefault(key, copy.deepcopy(children[donor]))
        if (set(child.attrib) != {'type', 'min', 'max', 'lootmin', 'lootmax'} or len(child)
                or (child.text or '').strip() or type(share) is not int or share <= 0
                or any(not re.fullmatch(r'[0-9]+', child.get(f, '')) for f in ('min', 'max', 'lootmin', 'lootmax'))
                or int(child.get('min')) <= share):
            # A donor always keeps a positive weight: no stock class leaves an event.
            raise ValueError('unsupported stock donor values: ' + donor)
        child.set('min', str(int(child.get('min')) - share))
        if variant in children:
            # Reweight an existing stock police outfit without duplicating its row
            # or changing its stock cap/loot policy.
            added = changed.setdefault(destination, copy.deepcopy(children[variant]))
            weight = int(added.get('min')) + share
            if int(added.get('max')) > 0 and weight > int(added.get('max')):
                raise ValueError('destination share exceeds stock cap: ' + variant)
            added.set('min', str(weight))
        else:
            added = copy.deepcopy(children[donor])
            added.set('min', str(share))
            added.set('max', '0')
            added.set('type', variant)
            additions.setdefault(key, []).append(added)
    for key, child in changed.items():
        begin, finish = spans[key]
        prefix = original[:begin].rsplit(b'\n', 1)[-1]
        indent = prefix if not prefix.strip() else b'      '
        newline = b'\r\n' if b'\r\n' in original else b'\n'
        nodes = [child] + additions.get(key, [])
        for node in nodes:
            node.tail = None
        replacements[key] = (begin, finish, (newline + indent).join(
            ET.tostring(node, encoding='utf-8') for node in nodes))
    result = original
    for begin, finish, replacement in sorted(replacements.values(), reverse=True):
        result = result[:begin] + replacement + result[finish:]
    declaration = re.match(br'(?:\xef\xbb\xbf)?<\?xml\s.*?\?>', result, re.S)
    if declaration:
        result = xml_text.DECLARATION.rstrip(b'\n') + result[declaration.end():]
    else:
        result = xml_text.DECLARATION + result
    # Validate emitted XML and each budget as an independent postcondition.
    after = _events(result)
    for name in targets:
        for field in ('min', 'max'):
            if sum(int(c.get(field)) for c in current[name].findall('./children/child')) != sum(
                    int(c.get(field)) for c in after[name].findall('./children/child')):
                raise ValueError('authored child budget changed: ' + name)
    return result


def install(mission, stock_events=None, off=False):
    """Write the optional-overlays style backup receipt before the atomic switch."""
    if off:
        return rollback(mission)
    mission = mission_target(mission)
    managed = safe(mission / MANAGED)
    if managed.exists():
        return check(mission)
    policy_bytes = read(POLICY)
    policy = json.loads(policy_bytes)
    original = read(mission / TARGET)
    if not policy['production_enabled']:
        raise ValueError('infected variety policy is disabled')
    if stock_events is None:
        # Habitat owns other events; validate only its events backup here.
        # Other layers may legitimately own gameplay/core files by this point.
        from tools.package.optional_overlays import BUNDLE_MANAGED
        bundle_receipt = safe(mission / BUNDLE_MANAGED / 'receipt.json')
        stock = original
        if bundle_receipt.exists():
            baseline = json.loads(read(bundle_receipt, 128 * 1024 * 1024))
            if baseline.get('schema') != 1 or not isinstance(baseline.get('files'), dict):
                raise ValueError('invalid bundle receipt for infected stock')
            row = baseline['files'].get(TARGET)
            if row is not None:
                stock = base64.b64decode(row['before'], validate=True)
                if (economy.sha(stock) != row['before_sha256']
                        or economy.sha(original) not in {row['before_sha256'], row['after']}):
                    raise ValueError('bundle events backup/mission drift')
    else:
        stock = read(Path(stock_events))
    result = substitute(original, stock, policy)
    receipt = {'schema': 1, 'kind': 'HC-14-infected-variety', 'runtime_acceptance': 'PENDING',
               'stock_events_sha256': economy.sha(stock), 'policy_sha256': economy.sha(policy_bytes),
               'files': {TARGET: {'before': base64.b64encode(original).decode('ascii'),
                                   'before_sha256': economy.sha(original), 'after': economy.sha(result)}}}
    # Recheck drift before creating recovery data. Operator must keep server stopped.
    if read(mission / TARGET) != original:
        raise ValueError('mission drift during planning')
    managed.mkdir()
    atomic(managed / 'receipt.json', economy.encode(receipt), managed)
    atomic(mission / TARGET, result, managed)
    return receipt


def check(mission):
    """Read-only integrity/policy check; an interrupted switch refuses reinstall."""
    mission = mission_target(mission)
    managed = safe(mission / MANAGED)
    economy.preflight_managed(managed, {'receipt.json', '.next'})
    receipt = json.loads(read(managed / 'receipt.json', 64 * 1024 * 1024))
    if (not isinstance(receipt, dict) or type(receipt.get('schema')) is not int
            or receipt['schema'] != 1 or receipt.get('kind') != 'HC-14-infected-variety'
            or receipt.get('policy_sha256') != economy.sha(read(POLICY))
            or set(receipt.get('files', {})) != {TARGET}):
        raise ValueError('infected variety receipt/policy mismatch; rollback first')
    row = receipt['files'][TARGET]
    if (not isinstance(row, dict) or set(row) != {'before', 'before_sha256', 'after'}
            or not isinstance(row.get('before'), str)
            or any(not isinstance(row.get(k), str) or not economy.HEX64.fullmatch(row[k])
                   for k in ('before_sha256', 'after'))):
        raise ValueError('invalid infected variety backup receipt')
    before = base64.b64decode(row['before'], validate=True)
    if (economy.sha(before) != row['before_sha256']
            or economy.sha(read(mission / TARGET)) != row['after']):
        raise ValueError('infected variety receipt/mission drift; rollback first')
    return receipt


def rollback(mission):
    """Refuse drift/missing evidence; interrupted pre-switch installs are reversible."""
    mission = mission_target(mission)
    managed = safe(mission / MANAGED)
    if not managed.exists():
        return []
    if not managed.is_dir():
        raise ValueError('managed receipt directory required')
    economy.preflight_managed(managed, {'receipt.json', '.next'})
    receipt_path = managed / 'receipt.json'
    if not receipt_path.exists():
        # No target is touched before the atomic receipt switch, so a
        # receipt-less directory is only safe to clear while the target still
        # carries none of the authored destinations (an operator may have
        # deleted the receipt after the switch).
        policy = json.loads(read(POLICY))
        current = _events(read(mission / TARGET))
        for row in policy['substitutions']:
            if row.get('existing_destination', False):
                continue
            event = current.get(row['event'])
            if event is not None and any(c.get('type') == row['to']
                                         for c in event.findall('./children/child')):
                raise ValueError('infected variety receipt missing; target modified; reconcile '
                                 + TARGET + ' against stock before rollback')
        shutil.rmtree(managed)
        return []
    with economy.refuse_missing(managed):
        receipt = json.loads(read(receipt_path, 64 * 1024 * 1024))
        if (not isinstance(receipt, dict) or type(receipt.get('schema')) is not int
                or receipt['schema'] != 1 or receipt.get('kind') != 'HC-14-infected-variety'
                or not isinstance(receipt.get('files'), dict) or set(receipt['files']) != {TARGET}):
            raise ValueError('invalid infected variety receipt')
        row = receipt['files'][TARGET]
        if (not isinstance(row, dict) or set(row) != {'before', 'before_sha256', 'after'}
                or any(not isinstance(row.get(k), str) or not economy.HEX64.fullmatch(row[k])
                       for k in ('before_sha256', 'after')) or not isinstance(row.get('before'), str)):
            raise ValueError('invalid infected variety backup receipt')
        before = base64.b64decode(row['before'], validate=True)
        if economy.sha(before) != row['before_sha256']:
            raise ValueError('infected variety backup drift')
        if economy.sha(read(mission / TARGET)) not in {row['before_sha256'], row['after']}:
            raise ValueError('infected variety mission drift; reconcile before rollback')
        atomic(mission / TARGET, before, managed)
    shutil.rmtree(managed)
    return [TARGET]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    apply = sub.add_parser('install', help='stopped isolated mission only; runtime acceptance pending')
    apply.add_argument('--mission', type=Path, required=True)
    apply.add_argument('--stock-events', type=Path, help='pristine events matching policy pin; default: validated bundle backup or current file')
    apply.add_argument('--off', action='store_true', help='restore receipt backup byte for byte')
    undo = sub.add_parser('rollback')
    undo.add_argument('--mission', type=Path, required=True)
    preview = sub.add_parser('dry-run', help='report child counts without writing the mission')
    preview.add_argument('--mission', type=Path, required=True)
    preview.add_argument('--stock-events', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'dry-run':
            policy = json.loads(read(POLICY))
            original = read(args.mission / TARGET)
            result = substitute(original, read(args.stock_events), policy)
            before, after = _events(original), _events(result)
            for name in sorted({r['event'] for r in policy['substitutions']}):
                old, new = before[name].findall('./children/child'), after[name].findall('./children/child')
                print(name + ': children=' + str(len(old)) + '->' + str(len(new))
                      + ' shares=' + str(sum(int(c.get('min')) for c in old)) + '->'
                      + str(sum(int(c.get('min')) for c in new)))
            print('HC-14 dry-run; population_delta=0; runtime=PENDING')
            return
        if args.command == 'install':
            install(args.mission, args.stock_events, args.off)
        else:
            rollback(args.mission)
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + '\n')
    print('HC-14 ' + ('restored/off' if args.command == 'rollback' or args.off else 'installed') + '; runtime=PENDING')


if __name__ == '__main__':
    main()
