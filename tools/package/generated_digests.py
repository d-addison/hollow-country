"""Input/output receipts for generated artefacts; update only after byte comparison."""
import argparse
import ast
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
import hashlib
import importlib
import io
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from tools.release.ship_inputs import ADDONS
from tools.release.rpt_summary import filtered
from tools.setup.winproc import InteropError

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path('config/generated-digests.json')


class MissingInput(ValueError):
    """Installed evidence unavailable (CLI skip, release refusal)."""


@dataclass(frozen=True)
class Contract:
    name: str
    module: str
    outputs: tuple[str, ...]
    inputs: tuple[str, ...] = ()
    external_outputs: tuple[str, ...] = ()


def contracts():
    """Use generators' declared inventories, including install-time-only deltas."""
    from tools.package import admin_world_catalog as admin, economy, gui_icons as icons
    from tools.package import snafu_optional as snafu, tactical_flava_optional as tf
    from tools.package import inventory_sizes, new_buildings, ai_route_precompute
    delta = tuple(sorted(economy.DELTA_FILES))
    package_data = ('tools/package/*.json', 'config/military-loot.json')
    common = (*package_data, 'config/loot-dispositions.json', 'mission/hollow-country/economy-profiles/*.json')
    return (
        Contract('ai_route_precompute', 'tools.package.ai_route_precompute', ai_route_precompute.OUTPUTS,
                 (ai_route_precompute.PINS, 'mission/hollow-country/ai/caravans.json',
                  'tools/setup/workshop_mods.json')),
        Contract('admin_world_catalog', 'tools.package.admin_world_catalog', (str(admin.CATALOG),),
                 (*admin.JSON_INPUTS, *admin.CE_INPUTS, 'config/map-overlays/layers/*.json')),
        Contract('military_loot', 'tools.package.military_loot', ('mission/hollow-country/ce/types.xml',), package_data),
        Contract('inventory_sizes', 'tools.package.inventory_sizes',
                 ('mods/HollowCountry/config.cpp', 'mods/HollowCountryExpansionAI/config.cpp',
                  str(inventory_sizes.PACK_TABLE.relative_to(ROOT))),
                 ('config/inventory-sizes.json', 'tools/setup/workshop_mods.json', *package_data)),
        Contract('firearms', 'tools.package.firearms', (), common, delta),
        Contract('loot_point_preserve', 'tools.package.loot_point_preserve',
                 ('mission/hollow-country/loot-points/additions-interiors.json',),
                 ('config/loot-*.json', 'config/interior*.json', 'tools/package/interior_themes/*.json',
                  'tools/package/*.json')),
        Contract('snafu_optional', 'tools.package.snafu_optional', (), common, tuple(sorted(snafu.economy.DELTA_FILES))),
        Contract('tactical_flava_optional', 'tools.package.tactical_flava_optional', (), common, tuple(sorted(tf.DELTA_FILES))),
        Contract('gui_icons', 'tools.package.gui_icons',
                 tuple(str(icons.SOURCE / (n + '.png')) for n in icons.ICONS) +
                 tuple(str(icons.OUTPUT / (n + '.paa')) for n in icons.ICONS) + (str(icons.MANIFEST),)),
        Contract('new_buildings', 'tools.package.new_buildings', (str(new_buildings.PATH),),
                 ('config/map-overlays/**/*.json', 'mission/hollow-country/ce/hc-event-sites.json',
                  'config/loot-*.json', 'tools/package/*.json', 'tools/package/interior_themes/*.json')),
        Contract('economy', 'tools.package.economy', (), common, delta),
        Contract('ai_patrols', 'tools.audit.gapcov_regions', ('mission/hollow-country/ai/sites.json',)),
        Contract('anims_config', 'tools.anim.ce_variants',
                 ('mods/HollowCountryAnims/config.cpp', 'mission/hollow-country/infected/variants.json')),
    )


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def source_files(module, root=ROOT):
    """Follow repository imports, including lazy imports in generation functions."""
    pending, found = [module], set()
    while pending:
        name = pending.pop()
        path = Path(name.replace('.', '/') + '.py')
        if path in found or not (root / path).is_file():
            continue
        found.add(path)
        for node in ast.walk(ast.parse((root / path).read_bytes())):
            if isinstance(node, ast.Import):
                pending.extend(alias.name for alias in node.names if alias.name.startswith('tools.'))
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('tools'):
                pending.append(node.module)
                pending.extend(node.module + '.' + alias.name for alias in node.names)
    return sorted(found)


def local_snapshot(contract, root=ROOT):
    names = set(contract.outputs)
    names.update(str(p) for p in source_files(contract.module, root))
    names.update(('tools/package/generated_digests.py', 'tools/package/regenerate_all.py'))
    # Conservative shared-data boundary: generators compose each other's policies.
    # Include additions/removals as well as edits; never include this receipt itself.
    shared = ('config/**/*.json', 'mission/hollow-country/**/*.json',
              'mission/hollow-country/**/*.xml', 'tools/package/**/*.json')
    for pattern in (*shared, *contract.inputs):
        matches = [p for p in root.glob(pattern) if p.is_file()]
        if not matches and not any(c in pattern for c in '*?['):
            raise ValueError('committed input missing: ' + pattern)
        names.update(p.relative_to(root).as_posix() for p in matches if p.relative_to(root) != MANIFEST)
    # Outputs with authored sections are also inputs; a full-file hash binds both.
    return {name: file_sha(root / name) for name in sorted(names)}


def require_file(path, label):
    if path is None or not Path(path).is_file():
        raise MissingInput(label + ' unavailable')
    return Path(path)


def installed_snapshot(contract, values):
    """Stable file-list/content identities only; never persist installed paths/content."""
    name = contract.name
    identities = {}
    if name == 'ai_route_precompute':
        from tools.package.ai_route_precompute import road_bytes
        try:
            identities['road_source'] = sha(road_bytes(ROOT, values['workshop']))
        except FileNotFoundError as exc:
            raise MissingInput('installed Expansion AI road source unavailable') from exc
    source = values.get('source')
    if name in {'economy', 'firearms', 'snafu_optional', 'tactical_flava_optional'}:
        from tools.package.economy import INPUTS
        for rel in INPUTS:
            path = require_file(source / rel if source else None, 'stock mission ' + rel)
            identities['stock/' + rel] = file_sha(path)
        # CE core registrations and carrier checks read additional mission XML.
        # Bind the whole XML file list so newly registered extension files count.
        for path in sorted(source.rglob('*.xml')):
            identities['stock/' + path.relative_to(source).as_posix()] = file_sha(path)
    if name in {'ai_patrols', 'new_buildings', 'loot_point_preserve'}:
        for rel in ('mapgrouppos.xml', 'mapgroupproto.xml'):
            path = require_file(source / rel if source else None, 'stock mission ' + rel)
            identities['stock/' + rel] = file_sha(path)
    if name == 'ai_patrols':
        # gapcov_regions also consumes optional CE/territory anchor metadata.
        # Bind its complete file list so additions/removals invalidate receipts.
        paths = [source / 'cfgeventspawns.xml', *sorted((source / 'env').glob('*territories.xml'))]
        for path in paths:
            if path.is_file():
                identities['stock/' + path.relative_to(source).as_posix()] = file_sha(path)
    if name in {'snafu_optional', 'tactical_flava_optional'}:
        key = 'snafu_report' if name == 'snafu_optional' else 'tactical_flava_report'
        report = require_file(values.get(key), 'weapon pack verification report')
        # The generator validates its pinned build/file-list evidence on regeneration.
        identities['verification_report'] = file_sha(report)
    if name == 'inventory_sizes':
        from tools.package import inventory_sizes as inv, inventory_sources as sources
        rules = json.loads((ROOT / 'config/inventory-sizes.json').read_bytes())
        active = inv.declared_sources(rules, ROOT / 'tools/setup/workshop_mods.json')
        for provider in sorted(active):
            directory = values['addons'] if provider == 'vanilla' else values['workshop'] / sources.WORKSHOP_FOLDERS.get(provider, provider) / 'addons'
            if not directory.is_dir():
                raise MissingInput('inventory provider Addons unavailable')
            # Match inventory_sources.documents: pin the config member bytes it reads,
            # and the opaque file inventory. No multi-gigabyte asset hashing needed.
            from tools.audit import pbo_config as reader
            members = {}
            families = ('characters_', 'gear_', 'weapon_', 'weapons_', 'vehicles_')
            for path in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
                if path.suffix.lower() == '.ebo':
                    members[path.name] = 'encrypted-ebo'
                    continue
                if path.suffix.lower() != '.pbo':
                    continue
                if provider == 'vanilla' and not (path.name.startswith(families) or path.name in {'dz.pbo', 'plants.pbo'}):
                    continue
                index = reader.read_pbo_index(path)
                entries = index['entries']
                bins = {e['name'].lower().replace('\\', '/')[:-3] for e in entries
                        if e['name'].lower().endswith('config.bin')}
                members[path.name] = {}
                for entry in entries:
                    member = entry['name'].lower().replace('\\', '/')
                    if not member.endswith(('config.bin', 'config.cpp')):
                        continue
                    if member.endswith('.cpp') and member[:-3] in bins:
                        continue
                    members[path.name][entry['name']] = sha(reader.read_member(path, index, entry['name']))
            if not members:
                raise MissingInput('inventory provider file list empty')
            identities['provider/' + provider] = sha(json.dumps(members, sort_keys=True).encode())
    if name == 'loot_point_preserve':
        from tools.package.regenerate_all import LOOT_REVISIONS, LOOT_OUTPUT
        for label, revision in LOOT_REVISIONS:
            result = subprocess.run(['git', 'show', f'{revision}:{LOOT_OUTPUT}'], cwd=ROOT,
                                    capture_output=True, timeout=values.get('timeout', 60))
            if result.returncode:
                raise ValueError('historical ' + label + ' input unavailable')
            identities['history/' + label] = sha(result.stdout)
    if name in {'new_buildings', 'loot_point_preserve'}:
        directory = values.get('reader')
        if directory is None or not directory.is_dir():
            raise MissingInput('pinned geometry reader unavailable')
        identities['geometry_reader'] = sha(json.dumps(
            {p.relative_to(directory).as_posix(): file_sha(p) for p in sorted(directory.rglob('*')) if p.is_file()},
            sort_keys=True).encode())
        directory = values['addons']
        files = sorted(directory.glob('*.pbo'))
        if not files:
            raise MissingInput('geometry Addons unavailable')
        identities['geometry_addons'] = sha(json.dumps({p.name: file_sha(p) for p in files}, sort_keys=True).encode())
        for i, census in enumerate(values.get('native_census', [])):
            identities['native_census/' + str(i)] = file_sha(require_file(census, 'native census'))
    if name == 'anims_config':
        path = require_file(values['addons'] / 'characters_zombies.pbo', 'stock zombie addon')
        identities['characters_zombies.pbo'] = file_sha(path)
        events = require_file(source / 'db/events.xml' if source else None, 'stock infected events')
        identities['stock/db/events.xml'] = file_sha(events)
    if name == 'gui_icons':
        from tools.package.gui_icons import DEFAULT_TOOL
        tool = require_file(values.get('image_to_paa', DEFAULT_TOOL), 'ImageToPAA converter')
        identities['ImageToPAA'] = file_sha(tool)
    if name == 'admin_world_catalog':
        from tools.package.admin_world_catalog import UPSTREAM
        identities['official_ce_source'] = UPSTREAM
    return identities


def regenerate(contract, values, scratch):
    """Return freshly generated bytes, using disposable paths for CLI-only writers."""
    module = importlib.import_module(contract.module)
    name, source = contract.name, values.get('source')
    load = lambda p: json.loads((ROOT / p).read_bytes())
    if name == 'ai_route_precompute':
        return module.plan(ROOT, workshop=values['workshop'])
    if name == 'admin_world_catalog':
        out = scratch / 'catalog.c'
        module.generate(out)
        return {contract.outputs[0]: out.read_bytes()}
    if name == 'military_loot':
        out = scratch / 'types.xml'
        module.regenerate(out)
        return {contract.outputs[0]: out.read_bytes()}
    if name == 'inventory_sizes':
        paths = [scratch / ('output-' + str(i)) for i in range(len(contract.outputs))]
        for rel, path in zip(contract.outputs, paths):
            path.write_bytes((ROOT / rel).read_bytes())
        command = [sys.executable, '-B', '-m', contract.module, '--write', '--addons', str(values['addons']),
                   '--workshop', str(values['workshop'])]
        for flag, path in zip(('--config', '--stack-config', '--pack-table'), paths):
            command += [flag, str(path)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=values.get('timeout', 60))
        if result.returncode:
            raise ValueError('inventory regeneration refused')
        return {rel: path.read_bytes() for rel, path in zip(contract.outputs, paths)}
    if name in {'economy', 'firearms', 'snafu_optional', 'tactical_flava_optional'}:
        if name == 'economy':
            files = module.generate(source, load('mission/hollow-country/economy-profiles/contextual-pilot.json'),
                                    roster=load('tools/package/firearms_roster.json'))
            if set(files) != set(contract.external_outputs):
                raise ValueError('declared install-time output inventory differs')
            return {'external/' + p: data for p, data in files.items()}
        if name == 'firearms':
            files = module.generate(source, load('tools/package/firearms_roster.json'))
        else:
            key = 'snafu_report' if name == 'snafu_optional' else 'tactical_flava_report'
            files = module.generate(source, json.loads(module.ALLOWLIST_PATH.read_bytes()),
                                    json.loads(values[key].read_bytes()))
        if set(files) != set(contract.external_outputs):
            raise ValueError('declared install-time output inventory differs')
        # These deltas are not committed or included in the release PBOs.
        return {'external/' + p: data for p, data in files.items()}
    if name == 'ai_patrols':
        # The legacy ai_patrols seed is now authored (routes/tuning/HC43). The
        # final producer preserves it and rebuilds only gapcov regional rows.
        # Copy all repository inputs; the writer's three outputs stay disposable.
        shutil.copytree(ROOT / 'mission/hollow-country', scratch / 'mission/hollow-country')
        if module.main(['--repo', str(scratch), '--stock-mission', str(source), '--write']):
            raise ValueError('regional AI sites generation refused')
        return {p: (scratch / p).read_bytes() for p in contract.outputs}
    if name == 'anims_config':
        # Reproduce both outputs of ce_variants.main, including its policy derivation.
        policy = load('mission/hollow-country/infected/variants.json')
        classes, _, _ = module.stock_config(values['addons'], policy)
        policy['substitutions'], policy['ce_pose_coverage'] = module.derive(
            (source / 'db/events.xml').read_bytes(), policy, classes)
        policy['accessories']['explicit_classes'] = {
            n: b for n, b in policy['accessories']['explicit_classes'].items()
            if n in {'HC_ZmbM_' + m for m in module.MODES}}
        policy['accessories']['explicit_classes'].update({
            r['to']: r['from'] for r in policy['substitutions'] if r['to'].startswith('HC_')})
        config = module.render((ROOT / contract.outputs[0]).read_text(), policy, values['addons'])
        return {contract.outputs[0]: config.encode(),
                contract.outputs[1]: (json.dumps(policy, indent=2) + '\n').encode()}
    if name == 'gui_icons':
        from tools.package.gui_icons import DEFAULT_TOOL
        try:
            module.build(scratch, values.get('image_to_paa', DEFAULT_TOOL))
        except InteropError as exc:
            raise MissingInput('ImageToPAA Windows interop unavailable') from exc
        return {p: (scratch / p).read_bytes() for p in contract.outputs}
    if name == 'new_buildings':
        data = module.generate(values['addons'], source, values['reader'], scratch / 'geometry', values.get('native_census', []))
        return {contract.outputs[0]: data}
    if name == 'loot_point_preserve':
        from tools.package.regenerate_all import LOOT_REVISIONS, LOOT_OUTPUT
        history = []
        for label, revision in LOOT_REVISIONS:
            result = subprocess.run(['git', 'show', f'{revision}:{LOOT_OUTPUT}'], cwd=ROOT,
                                    capture_output=True, timeout=values.get('timeout', 60))
            if result.returncode:
                raise ValueError('historical ' + label + ' input unavailable')
            path = scratch / (label + '.json')
            path.write_bytes(result.stdout)
            history.append(path)
        doc = module.preserve(*history, values['addons'], values['reader'], source / 'mapgroupproto.xml', (0, 1))
        return {contract.outputs[0]: module.encode(doc)}
    raise ValueError('no regeneration adapter: ' + name)


def difference_summary(path, committed, fresh):
    """Bounded entry-level evidence; formatting-only drift remains a byte failure."""
    def xml_entry(node):
        return (node.tag, sorted(node.attrib.items()), (node.text or '').strip(),
                sorted(xml_entry(child) for child in node))

    try:
        if path.endswith('.xml'):
            before, after = [
                {node.get('name'): xml_entry(node) for node in ET.fromstring(raw)}
                for raw in (committed, fresh)]
        elif path.endswith('.json'):
            docs = [json.loads(raw) for raw in (committed, fresh)]
            before, after = [{row['Id']: row for row in doc['Sites']} for doc in docs]
            metadata = []
            def fields(left, right, prefix=''):
                if isinstance(left, dict) and isinstance(right, dict):
                    for key in sorted(left.keys() | right.keys()):
                        if key == 'Sites' and not prefix:
                            continue
                        fields(left.get(key), right.get(key), prefix + '/' + key)
                elif left != right:
                    metadata.append(prefix)
            fields(*docs)
        else:
            return 'byte/format difference'
        added = sorted(after.keys() - before.keys())
        removed = sorted(before.keys() - after.keys())
        changed = sorted(k for k in before.keys() & after.keys() if before[k] != after[k])
        examples = ','.join((changed + added + removed)[:5])
        detail = ('; metadata=' + ','.join(metadata[:3])) if path.endswith('.json') and metadata else ''
        return f'entries added={len(added)} removed={len(removed)} changed={len(changed)}' + detail + (
            '; examples=' + examples if examples else '; formatting or document metadata differs')
    except (ValueError, KeyError, TypeError, ET.ParseError):
        return 'byte/structure difference'


def fresh_record(contract, values):
    before = local_snapshot(contract)
    installed = installed_snapshot(contract, values)
    with tempfile.TemporaryDirectory(prefix='hc-generated-digests-') as tmp, \
            redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        fresh = regenerate(contract, values, Path(tmp))
    external = {p.removeprefix('external/'): data for p, data in fresh.items() if p.startswith('external/')}
    fresh = {p: data for p, data in fresh.items() if not p.startswith('external/')}
    if set(external) != set(contract.external_outputs):
        raise ValueError('install-time output inventory differs')
    if set(fresh) != set(contract.outputs):
        raise ValueError('declared output inventory differs')
    for path, data in fresh.items():
        if (ROOT / path).read_bytes() != data:
            raise ValueError('committed bytes differ: ' + path + '; ' + difference_summary(path, (ROOT / path).read_bytes(), data))
    if before != local_snapshot(contract) or installed != installed_snapshot(contract, values):
        raise ValueError('inputs changed during regeneration')
    return {'inputs': before, 'installed': installed,
            'outputs': {p: sha(data) for p, data in sorted(fresh.items())},
            'external_outputs': {p: sha(data) for p, data in sorted(external.items())}}


def verify_record(contract, recorded, values):
    installed = installed_snapshot(contract, values)
    if not isinstance(recorded, dict) or recorded.get('verified') is not True:
        raise ValueError('no byte-verified digest receipt')
    if recorded.get('inputs') != local_snapshot(contract):
        raise ValueError('committed input/source/output digest differs')
    if set(recorded.get('outputs', {})) != set(contract.outputs):
        raise ValueError('output inventory differs')
    for path, digest in recorded['outputs'].items():
        if file_sha(ROOT / path) != digest:
            raise ValueError('output digest differs: ' + path)
    if set(recorded.get('external_outputs', {})) != set(contract.external_outputs):
        raise ValueError('install-time output inventory differs')
    if recorded.get('installed') != installed:
        raise ValueError('installed input identity differs')


def verify_release(tree, addons, workshop, waive_unavailable=False):
    """Run the pinned checker before any release-tree injection or packaging.

    Strict by default. waive_unavailable is for local test builds only: an
    artefact whose installed inputs are absent on this host (checker SKIP) is
    returned as a named waiver instead of refusing. FAIL (missing/pending
    receipt, changed inputs, stale outputs) still refuses. Callers record the
    waivers in BUILD_MANIFEST; the release gate refuses any bundle carrying them.
    """
    argv = [sys.executable, '-B', '-m', 'tools.package.generated_digests', '--check',
            '--addons', str(addons), '--workshop', str(workshop)]
    if not waive_unavailable:
        argv.insert(5, '--require-installed')
    result = subprocess.run(argv, cwd=tree, capture_output=True, text=True, timeout=1800)
    waived = []
    for line in result.stdout.splitlines():
        safe = filtered(line)
        if safe:
            print(safe[:400], flush=True)
        parts = line.split(' ', 2)
        if waive_unavailable and len(parts) >= 2 and parts[0] == 'SKIP':
            waived.append({'artefact': parts[1], 'reason': filtered(parts[2])[:200] if len(parts) > 2 else ''})
    if result.returncode:
        raise ValueError('generated artefact digest verification refused release')
    for item in waived:
        print('WAIVER generated_digests ' + item['artefact'] + ' installed input unavailable (local test build only)',
              flush=True)
    return {'strict': not waive_unavailable, 'waived_unavailable': waived}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--update', action='store_true')
    mode.add_argument('--compare', help=argparse.SUPPRESS)
    parser.add_argument('--artefact', action='append', help='limit receipt updates to named artefacts')
    parser.add_argument('--require-installed', action='store_true')
    parser.add_argument('--addons', type=Path, default=ADDONS)
    parser.add_argument('--workshop', type=Path, default=Path('/mnt/g/SteamLibrary/steamapps/workshop/content/221100'))
    parser.add_argument('--source', type=Path, default=os.environ.get('HC_GENERATED_SOURCE'))
    parser.add_argument('--reader', type=Path, default=os.environ.get('HC_GENERATED_READER'))
    parser.add_argument('--native-census', type=Path, action='append', default=[])
    for flag in ('image-to-paa', 'snafu-report', 'tactical-flava-report'):
        parser.add_argument('--' + flag, type=Path,
                            default=os.environ.get('HC_GENERATED_' + flag.upper().replace('-', '_')))
    parser.add_argument('--timeout', type=int, default=60)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    if not args.native_census and os.environ.get('HC_GENERATED_NATIVE_CENSUS'):
        try:
            paths = json.loads(os.environ['HC_GENERATED_NATIVE_CENSUS'])
            if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
                raise ValueError('expected paths')
            args.native_census = [Path(p).expanduser().resolve() for p in paths]
        except ValueError:
            parser.error('HC_GENERATED_NATIVE_CENSUS must be a JSON array of local paths')
    values = {k: v for k, v in vars(args).items() if v is not None}
    for key in ('source', 'reader', 'image_to_paa', 'snafu_report', 'tactical_flava_report'):
        if values.get(key) is not None:
            values[key] = Path(values[key]).expanduser().resolve()
    values['source'] = values.get('source') or args.addons.parent / 'mpmissions/dayzOffline.chernarusplus'
    path = ROOT / MANIFEST
    try:
        manifest = json.loads(path.read_bytes())
        if not isinstance(manifest, dict) or manifest.get('schema') != 1 or not isinstance(manifest.get('artefacts'), dict):
            raise ValueError('invalid digest manifest schema')
    except (OSError, ValueError):
        if not args.update and not args.compare:
            print('FAIL generated_digests missing or invalid digest manifest')
            return 1
        manifest = {'schema': 1, 'artefacts': {}}
    inventory = contracts()
    failures = skips = 0
    if args.compare and args.compare not in {c.name for c in inventory}:
        parser.error('unknown generator')
    if not args.compare and not args.update and set(manifest['artefacts']) != {c.name for c in inventory}:
        print('FAIL generated_digests artefact inventory differs')
        failures += 1
    if args.artefact and (not args.update or set(args.artefact) - {c.name for c in inventory}):
        parser.error('--artefact requires --update and known artefact names')
    for contract in inventory:
        if args.artefact and contract.name not in args.artefact:
            continue
        if args.compare and contract.name != args.compare:
            continue
        try:
            if args.update or args.compare:
                record = fresh_record(contract, values)
                if args.update:
                    manifest['artefacts'][contract.name] = dict(verified=True, **record)
            else:
                verify_record(contract, manifest['artefacts'].get(contract.name), values)
            detail = 'byte-verified digest contract' if contract.outputs else 'install-time delta generation validated'
            print('PASS ' + contract.name + ' ' + detail)
        except MissingInput as exc:
            skips += 1
            print(('FAIL' if args.require_installed else 'SKIP') + ' ' + contract.name + ' ' + str(exc))
        except Exception as exc:
            # CLI boundary: failed generator diagnostics must not emit private tracebacks.
            failures += 1
            reason = filtered(str(exc)).replace('\n', ' ')[:300]
            print('FAIL ' + contract.name + ' ' + (reason or 'regeneration refused'))
    if args.update:
        # Only proven records are replaced; failed or unavailable entries stay pending/stale.
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return int(bool(failures or (args.require_installed and skips)))


if __name__ == '__main__':
    raise SystemExit(main())
