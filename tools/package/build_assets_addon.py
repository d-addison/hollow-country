"""Build unsigned HollowCountryAssets.pbo from sealed, admitted inputs (offline).

Usage: python3 -B -m tools.package.build_assets_addon --plan build/assets/plan.json
       --out build/assets
Plan: {"inputs": [{"candidate": "sealed-directory", "members":
                    {"config.cpp": "config.cpp", "$PBOPREFIX$": "$PBOPREFIX$",
                     "models/example.p3d": "output/example.p3d"}}]}.
Candidate paths are relative to the plan directory. Every source file under
mods/HollowCountryAssets, including prefix metadata, must occur byte-for-byte
in the plan and have a freshly recomputed shippable provenance.v2 verdict.
Only explicitly listed candidate payloads ship; licences/provenance stay in the
sealed build directory. Keep attribution there for release review/distribution.
The source notice mods/HollowCountryAssets/NOTICE.txt (DayZ EULA / ADPL-SA) is a source
member like any other: it must be admitted in the plan and ships inside the PBO.

P3D inputs must be binarized ODOL56, validated by the clean-room reader.
--allow-mlod is an explicit offline development escape hatch, never used by the
release wiring. No native process is launched; native acceptance stays pending.
"""
import argparse
import json
from pathlib import Path

from tools.assets import licence_gate, mlod, provenance
from tools.audit import odol56
from tools.package import pbo

PREFIX = 'HollowCountryAssets'
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods' / PREFIX
EXTENSIONS = {'.cpp', '.cfg', '.p3d', '.paa', '.rvmat', '.txt'}  # .txt carries NOTICE.txt


def model_format(data, *, allow_mlod=False):
    """Magic determines format; validate the whole model, never just its suffix."""
    if data[:4] == b'ODOL':
        odol56.read_odol(data)
        return 'ODOL56'
    if data[:4] == b'MLOD' and allow_mlod:
        mlod.read_mlod(data)
        return 'MLOD-unbinarized'
    raise provenance.Refusal('assets.binarized_odol_required')


def build(plan, *, plan_dir, out, source=SOURCE, allow_mlod=False):
    """Reverify all sealed bytes, refuse missing source coverage and collisions."""
    if not isinstance(plan, dict) or set(plan) != {'inputs'} or not isinstance(plan['inputs'], list):
        raise provenance.Refusal('assets.plan_invalid')
    source = Path(source)
    source_files = {}
    if source.is_symlink() or not source.is_dir():
        raise provenance.Refusal('assets.source_invalid')
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise provenance.Refusal('assets.source_link')
        if path.is_file():
            name = path.relative_to(source).as_posix()
            source_files[name] = provenance.read_regular(source, name)
    if source_files.get('$PBOPREFIX$', b'').decode('ascii').strip() != PREFIX:
        raise provenance.Refusal('assets.prefix_invalid')
    if 'config.cpp' not in source_files:
        raise provenance.Refusal('assets.config_missing')
    files, origins = {}, {}
    formats = set()
    folded = set()
    for row in plan['inputs']:
        if not isinstance(row, dict) or set(row) != {'candidate', 'members'} or not isinstance(row['members'], dict) or not row['members']:
            raise provenance.Refusal('assets.input_invalid')
        candidate = Path(plan_dir) / provenance.relative_path(row['candidate'])
        # Reject links in the candidate's path before audit resolves anything.
        current = Path(plan_dir)
        for part in provenance.relative_path(row['candidate']).parts:
            current = current / part
            if current.is_symlink():
                raise provenance.Refusal('assets.candidate_link')
        verdict = licence_gate.audit(candidate / 'provenance.json')
        if not verdict['shippable']:
            raise provenance.Refusal('assets.input_not_shippable')
        inventory = provenance.verify_candidate(candidate)
        for member, payload in sorted(row['members'].items()):
            provenance.relative_path(member)
            pbo.safe_name(member)
            if member.casefold() in folded:
                raise provenance.Refusal('assets.member_collision')
            if member != '$PBOPREFIX$' and Path(member).suffix.lower() not in EXTENSIONS:
                raise provenance.Refusal('assets.member_type')
            if payload in {'provenance.json', 'manifest.json', 'candidate.sha256'} or payload not in inventory:
                raise provenance.Refusal('assets.payload_not_listed')
            data = provenance.read_regular(candidate, payload)
            if provenance.digest(data) != inventory[payload]:
                raise provenance.Refusal('assets.payload_changed')
            if member in source_files and data != source_files[member]:
                raise provenance.Refusal('assets.source_mismatch')
            if Path(member).suffix.lower() == '.p3d':
                formats.add(model_format(data, allow_mlod=allow_mlod))
            files[member] = data
            origins[member] = {'sha256': inventory[payload],
                               'provenance_sha256': inventory['provenance.json']}
            folded.add(member.casefold())
    if not source_files.keys() <= files.keys():
        raise provenance.Refusal('assets.source_not_admitted')
    files.pop('$PBOPREFIX$')
    blob = pbo.pack(files, prefix=PREFIX)
    pbo.parse(blob, prefixes=(PREFIX,))
    manifest = {'schema': 'assets-addon.v1', 'prefix': PREFIX, 'format': '+'.join(sorted(formats)) or 'no-models',
                'engine_verified': False,
                'native_acceptance': 'pending', 'pbo_sha256': provenance.digest(blob),
                'files': {name: origins[name] for name in sorted(files)}}
    out = Path(out)
    # Generated bytes belong in a build directory, never in source/mod trees.
    resolved = out.resolve()
    if resolved.is_relative_to(ROOT) and not resolved.is_relative_to(ROOT / 'build'):
        raise provenance.Refusal('assets.output_not_build_directory')
    target = out / 'addons' / (PREFIX + '.pbo')
    receipt = out / 'assets-addon.json'
    if any(p.is_symlink() for p in (out, *out.parents, target.parent, target, receipt)):
        raise provenance.Refusal('assets.output_link')
    if target.exists() or receipt.exists():
        raise provenance.Refusal('assets.output_exists')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(blob)
    receipt.write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('build/assets'))
    parser.add_argument('--allow-mlod', action='store_true', help='offline development only; not native proof')
    args = parser.parse_args(argv)
    try:
        result = build(provenance.load_json(args.plan.read_bytes()), plan_dir=args.plan.parent, out=args.out, allow_mlod=args.allow_mlod)
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({'valid': False, 'reason': 'assets.build_refused'}))
        return 1
    print(json.dumps({'valid': True, 'pbo_sha256': result['pbo_sha256']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
