"""Capacity table for the loot balance's second re-investment (wh-econ round 7, owner 2026-11-23).

Nominal that no matching container can hold is loot nobody finds. ``loot_balance.balance`` therefore hands freed
nominal only to classes whose (usage, tier, category, tag) bucket still has spare capacity in the static feasibility
graph of ``ce_slot_pressure.feasibility`` (limit 1.0, all building-routed categories). This module derives that table
from a staged final mission and reads it back:

  python3 -B -m tools.package.loot_slack --source STOCK_MISSION --write   # stage, plan, rewrite the table to a fixpoint
  python3 -B -m tools.package.loot_slack --source STOCK_MISSION --check   # rebuild once, compare bytes (exit 1 when stale)
  python3 -B -m tools.package.loot_slack MISSION --write                  # read an already staged mission instead

The table is a derived, optimistic offline bound that the plan it feeds reads back, so the committed table is correct
only when it is a fixpoint: staging the stock mission with the travel layer, planning with the committed table and
the shipped points, adding the optional gun packs (scaled by their allowlists), and rebuilding the table from that
result must give the same bytes. ``--check`` runs that single pass, so any change to the capacity settings, the points
overlays, the types rows or the balance code that moves a bucket fails it. Nothing here establishes DayZ behaviour.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET

from tools.package import ce_slot_pressure

ROOT = Path(__file__).resolve().parents[2]
TABLE = 'tools/package/loot_slack.json'
PACKS = ('snafu_allowlist.json', 'tactical_flava_allowlist.json')
PACK_FOLDER = 'hc-packs-scratch'
MAX_ROUNDS = 6


def build(mission):
    """{schema, buckets: {id: {slack, nominal, unassigned, route}}, classes: {lowercase class: id}} of a staged mission."""
    result = ce_slot_pressure.feasibility(Path(mission), False, 1.0, slack=True)
    buckets, classes = {}, {}
    ordered = sorted(result['bucket_slack'], key=lambda b: (b['categories'], b['usages'], b['tiers'], b['tags']))
    for index, bucket in enumerate(ordered):
        ident = str(index)
        buckets[ident] = {'slack': bucket['slack'], 'nominal': bucket['nominal'], 'unassigned': bucket['unassigned'],
                          'route': '%s / %s / %s / %s' % tuple(','.join(bucket[k]) for k in
                                                              ('usages', 'tiers', 'categories', 'tags'))}
        for name in bucket['classes']:
            classes[name.lower()] = ident
    return {'schema': 1, 'limit': 1.0, 'deficit': result.get('deficit', 0), 'buckets': buckets, 'classes': dict(sorted(classes.items()))}


def encode(doc):
    return (json.dumps(doc, indent=1, sort_keys=False) + '\n').encode()


def stage(source, scratch):
    """The final staged mission the table describes: stock mission, travel layer, loot boost, optional gun packs.

    The packs are not installed by this stage; their rows are added as a scratch CE folder (weapons category, the
    allowlist usages and values, nominal scaled by the allowlist's own abundance multiplier) because they are demand
    the table's buckets must see. Returns the staged directory.
    """
    from tools.package import loot_boost, snafu_optional, travel
    staged = Path(scratch) / 'staged'
    shutil.copytree(source, staged, ignore=shutil.ignore_patterns('storage_*'))
    travel.install(ROOT / 'mission/hollow-country', staged)
    result = loot_boost.plan(staged, points=loot_boost.shipped_points())
    for name, _, after in result['files']:
        path = staged / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(after)
    types = ET.Element('types')
    for filename in PACKS:
        allowlist = json.loads((ROOT / 'tools/package' / filename).read_bytes())
        entries, _, _ = snafu_optional._scaled_entries(allowlist['entries'], allowlist['test_abundance_multiplier'], None)
        for entry in entries:
            row = ET.SubElement(types, 'type', {'name': entry['class']})
            ET.SubElement(row, 'nominal').text = str(entry['set']['nominal'])
            ET.SubElement(row, 'min').text = str(entry['set'].get('min', 0))
            ET.SubElement(row, 'category', {'name': 'weapons'})
            for usage in entry.get('usage', entry.get('set_usage', [])):
                ET.SubElement(row, 'usage', {'name': usage})
            for value in entry.get('value', entry.get('set_value', [])):
                ET.SubElement(row, 'value', {'name': value})
    (staged / PACK_FOLDER).mkdir()
    ET.ElementTree(types).write(staged / PACK_FOLDER / 'types.xml')
    core = staged / 'cfgeconomycore.xml'
    core.write_text(core.read_text().replace(
        '</economycore>', '<ce folder="%s"><file name="types.xml" type="types"/></ce>\n</economycore>' % PACK_FOLDER))
    return staged


def generate(source):
    """Table bytes after one staged plan with the committed table (the --check pass)."""
    with tempfile.TemporaryDirectory(prefix='hc-loot-slack-') as scratch:
        return encode(build(stage(Path(source), scratch)))


def load(root=None):
    """The committed table as {'bucket': {id: slack}, 'class': {lowercase class: id}}, or None when it is absent."""
    path = Path(root or ROOT) / TABLE
    if not path.is_file():
        return None
    doc = json.loads(path.read_bytes())
    if doc.get('schema') != 1 or not isinstance(doc.get('buckets'), dict) or not isinstance(doc.get('classes'), dict):
        raise ValueError('invalid loot slack table')
    return {'bucket': {k: int(v['slack']) for k, v in doc['buckets'].items()}, 'class': dict(doc['classes'])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('mission', type=Path, nargs='?', help='an already staged mission (no stage, no fixpoint loop)')
    parser.add_argument('--source', type=Path, help='stock mission directory to stage from')
    parser.add_argument('--write', action='store_true', help='rewrite %s' % TABLE)
    parser.add_argument('--check', action='store_true', help='one staged pass; exit 1 when %s differs' % TABLE)
    args = parser.parse_args(argv)
    if args.check and args.write:
        parser.error('--check and --write are exclusive')
    if (args.mission is None) == (args.source is None):
        parser.error('give exactly one of MISSION or --source')
    table = ROOT / TABLE
    if args.source is None:
        text = encode(build(args.mission))
        if args.write:
            table.write_bytes(text)
    else:
        text = generate(args.source)
        current = table.read_bytes() if table.is_file() else None
        if args.check:
            if current != text:
                print('FAIL %s is not a fixpoint of the staged plan; run --source STOCK --write' % TABLE)
                return 1
            print('PASS %s matches the staged plan' % TABLE)
        elif args.write:
            for _ in range(MAX_ROUNDS):
                if table.is_file() and table.read_bytes() == text:
                    break
                table.write_bytes(text)
                text = generate(args.source)
            else:
                print('FAIL table did not settle in %d rounds' % MAX_ROUNDS)
                return 1
    doc = json.loads(text)
    print('buckets %d classes %d slack %d deficit %d' % (len(doc['buckets']), len(doc['classes']),
                                                         sum(b['slack'] for b in doc['buckets'].values()), doc['deficit']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
