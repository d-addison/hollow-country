"""Capacity table for the loot balance's second re-investment (wh-econ round 7, owner 2026-11-23).

Nominal that no matching container can hold is loot nobody finds. ``loot_balance.balance`` therefore hands freed
nominal only to classes whose (usage, tier, category, tag) bucket still has spare capacity in the static feasibility
graph of ``ce_slot_pressure.feasibility`` (limit 1.0, all building-routed categories). This module derives that table
from a staged final mission and reads it back:

  python3 -B -m tools.package.loot_slack MISSION --write      # rewrite tools/package/loot_slack.json

The table is a derived, optimistic offline bound; it is rebuilt from the staged result of the plan it feeds, so run it
until the numbers stop moving. Nothing here establishes DayZ behaviour.
"""
import argparse
import json
from pathlib import Path

from tools.package import ce_slot_pressure

ROOT = Path(__file__).resolve().parents[2]
TABLE = 'tools/package/loot_slack.json'


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
    parser.add_argument('mission', type=Path)
    parser.add_argument('--write', action='store_true', help='rewrite %s' % TABLE)
    args = parser.parse_args(argv)
    doc = build(args.mission)
    text = json.dumps(doc, indent=1, sort_keys=False) + '\n'
    if args.write:
        (ROOT / TABLE).write_text(text)
    print('buckets %d classes %d slack %d deficit %d' % (len(doc['buckets']), len(doc['classes']),
                                                         sum(b['slack'] for b in doc['buckets'].values()), doc['deficit']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
