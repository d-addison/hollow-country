"""W5 #12: CSV of essential items with fewer than two configured CE usage routes.

Reads mission db/types.xml and type=types CE declarations, plus explicit candidate
--overlay types XML files. Does not install, change counts or claim spawn evidence.
Distinct usages count once; categories label a route, never multiply it. A route
requires nominal >0, category and usage, and crafted=0/deloot=0. The HC-22
floor proposals must clear those flags in their emitted XML; class names never
bypass this policy. Conflicting definitions contribute only common routes:
CE override ordering is not assumed.
Bounded to 128 files of 32 MiB each, 128 MiB total and the existing CE node/depth
limits. No engine API or runtime tick. Output only; no metrics artifact is written.
HC-33 --habitats appends authored flora/native-use dispositions with zero CE
usage credit; retained/refused routes and runtime-pending evidence stay explicit.
"""
import argparse
import csv
from collections import defaultdict
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.audit.ce_audit import BoundedTreeBuilder, InputProblem, _relative, MAX_FILE_BYTES, MAX_TOTAL_BYTES

# Exact vanilla classes, deliberately reviewable rather than guessed from substrings.
ESSENTIALS = ('BandageDressing', 'Rag', 'DisinfectantAlcohol', 'TetracyclineAntibiotics',
              'WaterBottle', 'Canteen', 'PurificationTablets', 'SardinesCan', 'BakedBeansCan',
              'KitchenKnife', 'HuntingKnife', 'StoneKnife', 'Matchbox', 'Lighter', 'Rope',
              'DuctTape', 'SewingKit', 'LeatherSewingKit', 'Whetstone', 'CanOpener')
TOKEN = re.compile(r'[A-Za-z][A-Za-z0-9_]*\Z')
USE_POLICY = Path(__file__).resolve().parents[1] / 'package/essential_routes.json'
MAX_ROUTE_BYTES = 128 * 1024


def native_route_rows(habitats, use_policy=USE_POLICY):
    """HC-33 authored native/use dispositions; NEVER count as CE usage routes.

    Two bounded local JSON inputs, <=15 flora and <=16 use families. The
    manifest is review/package metadata, not a runtime generator controller.
    """
    def read(path):
        with Path(path).open('rb') as stream:
            data = stream.read(MAX_ROUTE_BYTES + 1)
        if len(data) > MAX_ROUTE_BYTES:
            raise ValueError('native route byte limit exceeded')
        value = json.loads(data)
        if not isinstance(value, dict) or value.get('schema') != 1:
            raise ValueError('unsupported native route schema')
        return value

    manifest, policy = read(habitats), read(use_policy)
    if (manifest.get('kind') != 'hollow-country-forage-habitats'
            or policy.get('kind') != 'hollow-country-essential-routes'):
        raise ValueError('unsupported native route kind')
    flora, uses = manifest.get('flora'), policy.get('native_use_routes')
    if (not isinstance(flora, list) or len(flora) != 15
            or not isinstance(uses, list) or not 1 <= len(uses) <= 16):
        raise ValueError('native route entry limit')
    rows, seen = [], set()
    reasons = {'native_generator': 'native_route_runtime_pending',
               'hc_bounded_supplement': 'hc_bounded_supplement_runtime_pending',
               'refused': 'refused_no_acquisition_evidence'}
    for entry in flora + uses:
        if not isinstance(entry, dict):
            raise ValueError('invalid native route entry')
        name = entry.get('class', entry.get('id', ''))
        route = entry.get('route')
        acquisition, actions = entry.get('acquisition'), entry.get('uses')
        if (not isinstance(name, str) or not TOKEN.fullmatch(name) or name in seen
                or not isinstance(acquisition, str) or not 1 <= len(acquisition) <= 512
                or not isinstance(actions, list) or not 1 <= len(actions) <= 8
                or any(not isinstance(action, str) or not TOKEN.fullmatch(action) for action in actions)
                or not isinstance(route, str) or route not in (*reasons, 'native_use')):
            raise ValueError('invalid or duplicate native route')
        seen.add(name)
        reason = 'native_route_runtime_pending' if route == 'native_use' else reasons[route]
        rows.append((name, 0, ';'.join([acquisition] + actions), reason, 'authored_only_runtime_pending'))
    if (any(entry['route'] not in reasons for entry in flora)
            or any(entry['route'] != 'native_use' for entry in uses)):
        raise ValueError('flora and essential-use route kinds differ')
    return sorted(rows)


def report_rows(mission, overlays=(), essentials=ESSENTIALS):
    budget = SimpleNamespace(xml_nodes=0)
    total = 0
    seen = set()

    def read_xml(path, tag):
        nonlocal total
        size = path.stat().st_size
        total += size
        if size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise ValueError('XML byte limit exceeded')
        parser = ET.XMLParser(target=BoundedTreeBuilder(budget))
        root = ET.fromstring(path.read_bytes(), parser=parser)
        if root.tag != tag:
            raise ValueError('unexpected XML root')
        return root

    root_path = Path(mission).resolve()
    sources = [root_path / 'db/types.xml']
    core = root_path / 'cfgeconomycore.xml'
    if core.exists():
        for ce in read_xml(core, 'economycore').findall('ce'):
            for entry in ce.findall('file'):
                if entry.get('type') == 'types':
                    folder = ce.get('folder', '')
                    prefix = folder + '/' if folder else ''
                    relative = _relative(prefix + entry.get('name', ''))
                    path = (root_path / relative).resolve()
                    if not path.is_relative_to(root_path):
                        raise ValueError('CE path escapes mission')
                    sources.append(path)
    sources.extend(Path(path).resolve() for path in overlays)
    if len(sources) > 128:
        raise ValueError('too many sources')
    definitions = defaultdict(list)
    for source in sources:
        resolved = source.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        for entry in read_xml(source, 'types').findall('type'):
            name = entry.get('name', '')
            if not TOKEN.fullmatch(name):
                raise ValueError('invalid item name')
            definitions[name].append(entry)
    rows = []
    for name in sorted(set(essentials)):
        if not TOKEN.fullmatch(name):
            raise ValueError('invalid essential name')
        candidates = definitions[name]
        route_sets = []
        labels = defaultdict(set)
        for entry in candidates:
            nominal = entry.findtext('nominal', '')
            if not nominal.isdecimal():
                raise ValueError('missing or invalid nominal')
            categories = {node.get('name', '') for node in entry.findall('category')}
            usages = {node.get('name', '') for node in entry.findall('usage')}
            if any(not TOKEN.fullmatch(token) for token in categories | usages):
                raise ValueError('invalid category or usage')
            flags = entry.find('flags')
            # Read actual XML flags, including for the 17 HC-22 floor overrides.
            special = flags is not None and (flags.get('crafted', '0') != '0' or flags.get('deloot', '0') != '0')
            routes = usages if int(nominal) > 0 and categories and not special else set()
            route_sets.append(routes)
            for usage in routes:
                labels[usage].update(categories)
        routes = set.intersection(*route_sets) if route_sets else set()
        if len(routes) >= 2:
            continue
        reason = 'fewer_than_two_configured_usages'
        if not candidates:
            reason = 'missing_type'
        elif len({ET.tostring(entry) for entry in candidates}) > 1:
            reason = 'conflicting_definitions_common_routes_only'
        rows.append((name, len(routes), ';'.join('+'.join(sorted(labels[u])) + '@' + u for u in sorted(routes)),
                     reason, 'configured_only_runtime_pending'))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mission', required=True, type=Path, help='installed or staged complete mission directory')
    parser.add_argument('--overlay', action='append', type=Path, default=[], help='candidate types XML; repeat in any order')
    parser.add_argument('--essential', action='append', help='exact item class; repeat to replace the default essential list')
    parser.add_argument('--habitats', type=Path, help='append HC-33 authored routes; zero CE usage credit')
    parser.add_argument('--use-policy', type=Path, default=USE_POLICY, help='HC-33 native-use metadata in essential route policy')
    args = parser.parse_args(argv)
    try:
        rows = report_rows(args.mission, args.overlay, args.essential or ESSENTIALS)
        if args.habitats:
            rows.extend(native_route_rows(args.habitats, args.use_policy))
    except (OSError, ValueError, ET.ParseError, InputProblem, RecursionError):
        print('loot_routes: unreadable or invalid mission/overlay XML or native route JSON', file=sys.stderr)
        return 2
    writer = csv.writer(sys.stdout, lineterminator='\n')
    writer.writerow(('item', 'route_count', 'routes', 'reason', 'evidence'))
    writer.writerows(rows)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
