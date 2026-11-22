"""Derive CE outfit-preserving pose/crawl children from pinned installed stock data.

No native assets are emitted. Re-run with --stock-events and --addons to refresh
variants.json and the generated config section. Build refuses stale config/classes.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from tools.audit import pbo_config as pc

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / 'mission/hollow-country/infected/variants.json'
CONFIG = ROOT / 'mods/HollowCountryAnims/config.cpp'
MODES = ('Sitter', 'Sleeper', 'Riser', 'Feeder', 'Crawler')
# Hand-authored public classes: the admin/herd sitter. Every other mode exists only as generated per-outfit children.
PUBLIC = ('HC_ZmbM_Sitter',)
BEGIN = '    // BEGIN GENERATED CE OUTFITS (tools.anim.ce_variants)'
END = '    // END GENERATED CE OUTFITS'


def stock_config(addons, policy):
    path = Path(addons) / 'characters_zombies.pbo'
    if hashlib.sha256(path.read_bytes()).hexdigest() != policy['evidence']['source_addon_sha256']:
        raise ValueError('stock zombie addon hash differs from policy')
    index = pc.read_pbo_index(path)
    data = pc.read_member(path, index, 'config.bin')
    classes = pc.parse_rap(data, ('CfgVehicles',))['CfgVehicles']
    rap = pc._Rap(data)
    offsets = {}
    for kind, name, offset in rap.entries(16)[1]:
        if kind == 'class' and name == 'CfgVehicles':
            offsets = {n: o for k, n, o in rap.entries(offset)[1] if k == 'class'}
    # Inspect nested enfanimsys using the bounded audit reader. Female and male
    # inherit ZombieBase's complete block in 1.30.164289; fail if any input drifts.
    def anim(name):
        for ancestor in pc.ancestry(classes, name):
            for kind, field, value in rap.entries(offsets[ancestor])[1]:
                if kind == 'class' and field == 'enfanimsys':
                    return dict((n, v) for k, n, v in rap.entries(value)[1] if k == 'value')
        raise ValueError('missing stock animation inputs: ' + name)
    baseline = anim('ZombieBase')
    for sex in ('ZombieMaleBase', 'ZombieFemaleBase'):
        if anim(sex) != baseline:
            raise ValueError('stock sex animation inputs differ: ' + sex)
    return classes, anim, baseline


def derive(stock, policy, classes):
    if hashlib.sha256(stock).hexdigest() != policy['evidence']['stock_events_sha256']:
        raise ValueError('stock events hash differs from policy')
    legacy = [r for r in policy['substitutions'] if not r['to'].startswith('HC_')]
    outgoing = Counter()
    for r in legacy + policy.get('palette_rebalance', {}).get('transfers', []):
        outgoing[r['event'], r['from']] += r['share']
    canonical = {n.casefold(): n for n in classes}
    rows, coverage = [], {}
    for event in ET.fromstring(stock).findall('event'):
        name = event.get('name')
        if not name.startswith('Infected'):
            continue
        children = event.findall('./children/child')
        total = sum(int(c.get('min')) for c in children)
        # Ten percent normally; the ten-weight NBCYellow event needs five
        # integer units to expose all five modes (50%). No population increase.
        budget = max(len(MODES), total // 10)
        available = {c.get('type'): int(c.get('min')) - outgoing[name, c.get('type')] - 1
                     for c in children if c.get('type').casefold() in canonical
                     and pc.resolve_scope(classes, canonical[c.get('type').casefold()]) == 2}
        available = {n: w for n, w in available.items() if w > 0}
        # Alternate sexes where present, then cycle outfits before reusing one.
        male = sorted((n for n in available if not n.startswith('ZmbF_')), key=lambda n: (-available[n], n))
        female = sorted((n for n in available if n.startswith('ZmbF_')), key=lambda n: (-available[n], n))
        order = []
        while male or female:
            if male: order.append(male.pop(0))
            if female: order.append(female.pop(0))
        allocated = Counter()
        for unit in range(budget):
            candidates = [n for n in order if available[n] > 0]
            if not candidates:
                raise ValueError('insufficient positive CE donor reserve: ' + name)
            donor = candidates[unit % len(candidates)]
            allocated[donor, MODES[unit % len(MODES)]] += 1
            available[donor] -= 1
        for (donor, mode), share in sorted(allocated.items()):
            base = canonical[donor.casefold()]
            rows.append(dict(event=name, **{'from': donor}, to='HC_' + base.split('_', 1)[0] + '_' + mode + '_' + base,
                             share=share, min_delta=0, max_delta=0))
        coverage[name] = dict(rows=len(allocated), classes=len(allocated), weight=budget,
                              stock_weight=total, population_delta=0)
    return legacy + rows, coverage


def render(config, policy, addons):
    classes, anim, baseline = stock_config(addons, policy)
    generated = {}
    for row in policy['substitutions']:
        if not row['to'].startswith('HC_'):
            continue
        _, sex, mode, base = row['to'].split('_', 3)
        if mode not in MODES or base not in classes or pc.resolve_scope(classes, base) != 2:
            raise ValueError('missing or nonpublic stock variant base: ' + base)
        if anim(base) != baseline:
            raise ValueError('outfit animation inputs differ: ' + base)
        generated[row['to']] = (mode, base)
    lines = [BEGIN]
    # Forward-declare only bases the authored part of the file does not
    # already declare: the engine refuses a repeated class at config load
    # ("Member already defined"), before any script compiles.
    authored = config
    if BEGIN in authored:
        authored = authored[:authored.index(BEGIN)] + authored[authored.index(END) + len(END):]
    declared = set(re.findall(r'^    class (\w+)\s*;', authored, re.M))
    for base in sorted({b for _, b in generated.values()} - declared):
        lines.append('    class ' + base + ';')
    for name, (mode, base) in sorted(generated.items()):
        lines.extend(['    class ' + name + ': ' + base, '    {', '        scope = 2;',
                      '        hcSpawnPose = ' + str(MODES.index(mode) + 1) + ';'])
        if mode != 'Crawler':
            lines.extend(['        class enfanimsys', '        {',
                          '            meshObject = "' + baseline['meshObject'] + '";',
                          '            graphname = "HollowCountryAnims\\anims\\infected\\hc_infected.agr";',
                          '            defaultinstance = "HollowCountryAnims\\anims\\infected\\hc_infected.asi";',
                          '            skeletonName = "' + baseline['skeletonName'] + '";',
                          '            startnode = "HCMasterControl";', '        };'])
        lines.append('    };')
    lines.append(END)
    block = '\n'.join(lines)
    if BEGIN in config:
        config = config[:config.index(BEGIN)] + block + config[config.index(END) + len(END):]
    else:
        at = config.rfind('};')
        config = config[:at] + block + '\n' + config[at:]
    vehicles = config[config.index('class CfgVehicles'):]
    top = re.findall(r'^    class (\w+)\s*[;:{\n]', vehicles, re.M)
    repeated = sorted({n for n in top if top.count(n) > 1})
    if repeated:
        raise ValueError('class declared more than once in config.cpp: ' + ', '.join(repeated))
    names = list(PUBLIC) + sorted(generated)
    return re.sub(r'units\[\] = \{[^}]*\};', 'units[] = {' + ', '.join('"' + n + '"' for n in names) + '};', config)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-events', type=Path, required=True)
    parser.add_argument('--addons', type=Path, required=True)
    args = parser.parse_args()
    policy = json.loads(POLICY.read_bytes())
    classes, _, _ = stock_config(args.addons, policy)
    policy['substitutions'], policy['ce_pose_coverage'] = derive(args.stock_events.read_bytes(), policy, classes)
    policy['accessories']['explicit_classes'] = {n: b for n, b in policy['accessories']['explicit_classes'].items() if n in PUBLIC}
    policy['accessories']['explicit_classes'].update({r['to']: r['from'] for r in policy['substitutions'] if r['to'].startswith('HC_')})
    config = render(CONFIG.read_text(), policy, args.addons)
    POLICY.write_text(json.dumps(policy, indent=2) + '\n')
    CONFIG.write_text(config)


if __name__ == '__main__':
    main()
