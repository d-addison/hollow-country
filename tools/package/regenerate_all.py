"""Read-only aggregate checks and disposable regeneration; never replaces outputs."""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from tools.release.rpt_summary import filtered
from tools.release.ship_inputs import ADDONS

ROOT = Path(__file__).resolve().parents[2]
WORKSHOP = Path('/mnt/g/SteamLibrary/steamapps/workshop/content/221100')
LOOT_OUTPUT = 'mission/hollow-country/loot-points/additions-interiors.json'
# Historical inputs documented in docs/LOOT_POINTS.md, Reproduction and validation.
LOOT_REVISIONS = (('prior', '335915c6'), ('candidate', 'fa0c2ac8'))


@dataclass(frozen=True)
class Generator:
    name: str
    arguments: tuple[str, ...]
    inputs: tuple[str, ...] = ()
    success: str = 'existing offline check passed'
    package: str = 'tools.package'
    # Generators whose outputs are bound in config/generated-digests.json; a repo-local derived
    # document set (the pitfall cards) is compared by its own --check and has no digest contract.
    digest: bool = True


# All check-capable generators live here, including positional check subcommands.
GENERATORS = (
    Generator('admin_world_catalog', ('--check',)),
    Generator('ai_route_precompute', ('--check', '--workshop', '{workshop}'), ('ai_roads',)),
    Generator('military_loot', ('--check',)),
    Generator('inventory_sizes', ('--check', '--addons', '{addons}', '--workshop', '{workshop}'),
              ('addons', 'inventory_stack')),
    Generator('variety_packs', ('--check', '--addons', '{addons}', '--workshop', '{workshop}', '--source', '{source}'),
              ('addons', 'source', 'variety_packs')),
    Generator('firearms', ('generate', '--check', '--source', '{source}'), ('source',),
              'committed bytes match fresh generation'),
    Generator('loot_point_preserve', ('--check', '--prior', '{prior}', '--candidate', '{candidate}',
                                     '--out', LOOT_OUTPUT)),
    Generator('snafu_optional', ('generate', '--check', '--source', '{source}', '--report', '{snafu_report}'),
              ('source', 'snafu_report'), 'committed bytes match fresh generation'),
    Generator('tactical_flava_optional', ('generate', '--check', '--source', '{source}', '--report', '{tactical_flava_report}'),
              ('source', 'tactical_flava_report'), 'committed bytes match fresh generation'),
    Generator('gui_icons', ('check',)),
    Generator('economy', (), ('source',)),
    Generator('ai_patrols', (), ('source',)),
    Generator('anims_config', (), ('addons',)),
    Generator('new_buildings', ('check', '--mission', '{source}'), ('source',),
              'shipped layer dry-run passed; CLI does not regenerate geometry'),
    Generator('pitfall_cards', ('--check',), (), 'committed docs/pitfalls cards match fresh generation',
              package='tools.validate', digest=False),
)
# The aggregate has --check but is an orchestrator, not a generator. Never recurse.
EXCLUDED_CHECK_MODULES = {
    'regenerate_all': 'aggregate orchestrator; would recursively invoke itself',
    'generated_digests': 'digest orchestrator; checked separately before release packaging',
    'hc_events': 'install-time CE scene installer with no committed outputs; friend_bundle runs hc_events.validate on every bundle build',
}


def diagnostic(result):
    """One bounded, privacy-filtered reason, never raw child output."""
    lines = (result.stderr + '\n' + result.stdout).splitlines()
    for line in reversed(lines):
        safe = filtered(line)
        if safe and safe.strip():
            return safe.strip()[:300]
    return 'no publishable diagnostic'


def missing_inputs(generator, values):
    for name in generator.inputs:
        if name == 'ai_roads':
            from tools.package.ai_route_precompute import road_bytes
            try:
                road_bytes(ROOT, values['workshop'])
            except FileNotFoundError:
                return 'installed Expansion AI road source unavailable'
        elif name == 'inventory_stack':
            # Match the generator's declared provider selection and folder aliases.
            from tools.package import inventory_sizes, inventory_sources
            rules = json.loads((ROOT / 'config/inventory-sizes.json').read_bytes())
            active = inventory_sizes.declared_sources(rules, ROOT / 'tools/setup/workshop_mods.json')
            for folder in sorted(active - {'vanilla'}):
                path = values['workshop'] / inventory_sources.WORKSHOP_FOLDERS.get(folder, folder) / 'addons'
                if not path.is_dir():
                    return 'installed inventory provider Addons directory unavailable'
        elif name == 'variety_packs':
            from tools.package import variety_packs
            if any(path is None for path in variety_packs.pack_directories(values['workshop']).values()):
                return 'installed variety pack Addons directory unavailable'
        else:
            path = values[name]
            is_file = name.endswith('_report')
            if path is None or not (path.is_file() if is_file else path.is_dir()):
                return f'required {name.replace("_", " ")} {"file" if is_file else "directory"} unavailable'
    return None


def check_generator(generator, values, timeout):
    missing = missing_inputs(generator, values)
    if missing:
        return 'SKIP', missing
    # Historical inputs and regenerated outputs stay in disposable directories.
    with tempfile.TemporaryDirectory(prefix='hc-regenerate-check-') as scratch:
        arguments = dict(values)
        if generator.name == 'loot_point_preserve':
            for name, revision in LOOT_REVISIONS:
                result = subprocess.run(['git', 'show', f'{revision}:{LOOT_OUTPUT}'], cwd=ROOT,
                                        capture_output=True, text=True, errors='replace', timeout=timeout)
                if result.returncode:
                    return 'FAIL', f'historical {name} input unavailable: ' + diagnostic(result)
                path = Path(scratch) / (name + '.json')
                path.write_text(result.stdout)
                arguments[name] = path
        command = [sys.executable, '-B', '-m', generator.package + '.' + generator.name,
                   *(arg.format_map(arguments) for arg in generator.arguments)]
        if generator.arguments:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                    errors='replace', timeout=timeout)
            if result.returncode:
                return 'FAIL', f'exit {result.returncode}: ' + diagnostic(result)
        if not generator.digest:
            return 'PASS', generator.success
        command = [sys.executable, '-B', '-m', 'tools.package.generated_digests', '--compare', generator.name,
                   '--timeout', str(timeout)]
        for key in ('addons', 'workshop', 'source', 'snafu_report', 'tactical_flava_report', 'image_to_paa'):
            if values.get(key) is not None:
                command += ['--' + key.replace('_', '-'), str(values[key])]
        for census in values.get('native_census', []):
            command += ['--native-census', str(census)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                errors='replace', timeout=timeout)
    if result.returncode:
        return 'FAIL', f'exit {result.returncode}: ' + diagnostic(result)
    if result.stdout.startswith('SKIP '):
        return 'SKIP', ('existing validation passed; byte regeneration: ' if generator.arguments else '') + diagnostic(result).split(' ', 2)[-1]
    if generator.name in {'economy', 'firearms', 'snafu_optional', 'tactical_flava_optional'}:
        return 'PASS', 'install-time delta generation validated; no committed outputs'
    return 'PASS', 'committed bytes match fresh generation'


def positive_timeout(value):
    seconds = int(value)
    if seconds <= 0:
        raise argparse.ArgumentTypeError('timeout must be positive seconds')
    return seconds


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='read-only checks (the default)')
    parser.add_argument('--require-installed', action='store_true', help='fail if any required input is skipped')
    parser.add_argument('--addons', type=Path, default=ADDONS)
    parser.add_argument('--workshop', type=Path, default=WORKSHOP, help='inventory provider Workshop root')
    parser.add_argument('--source', type=Path, help='pristine stock mission; default: sibling of Addons under mpmissions/dayzOffline.chernarusplus')
    parser.add_argument('--snafu-report', type=Path, help='existing external verification report')
    parser.add_argument('--tactical-flava-report', type=Path, help='existing external verification report')
    parser.add_argument('--reader', type=Path, default=None, help=argparse.SUPPRESS)  # legacy, ignored
    parser.add_argument('--native-census', type=Path, action='append', default=[])
    parser.add_argument('--image-to-paa', type=Path, help='installed ImageToPAA converter')
    parser.add_argument('--timeout', type=positive_timeout, default=60, help='seconds per child (default: 60)')
    args = parser.parse_args(argv)
    values = {name: path.expanduser().resolve() if path is not None else None
              for name, path in vars(args).items() if name in
              {'addons', 'workshop', 'source', 'snafu_report', 'tactical_flava_report', 'image_to_paa'}}
    values['native_census'] = [p.expanduser().resolve() for p in args.native_census]
    if values['source'] is None:
        values['source'] = values['addons'].parent / 'mpmissions/dayzOffline.chernarusplus'
    counts = {'PASS': 0, 'FAIL': 0, 'SKIP': 0}
    for generator in GENERATORS:
        try:
            status, reason = check_generator(generator, values, args.timeout)
        except subprocess.TimeoutExpired:
            status, reason = 'FAIL', 'child timed out'
        except (OSError, ValueError, KeyError, TypeError) as exc:
            status, reason = 'FAIL', 'check unavailable: ' + diagnostic(
                subprocess.CompletedProcess([], 1, '', str(exc)))
        counts[status] += 1
        print(f'{status} {generator.name} {reason}', flush=True)
    failed = counts['FAIL'] > 0 or (args.require_installed and counts['SKIP'] > 0)
    print(f'regenerate_all: {"fail" if failed else "pass"} '
          f'checked={counts["PASS"] + counts["FAIL"]} failed={counts["FAIL"]} skipped={counts["SKIP"]}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
