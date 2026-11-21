"""Build signed release artifacts from an isolated commit, never the live checkout.

Usage: python3 -B -m tools.release.release BUILD [--commit HEAD] [--allow-unpushed]
The interior template pack defaults to the committed mission pack at that commit; only the
disposable tree receives it (--templates overrides it for a diagnostic build).
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

from tools.package.sign_wine import CACHE, sign
from tools.package.weapon_pack_guards import WORKSHOP
from tools.release import compile_gate, ship_inputs

ROOT = Path(__file__).resolve().parents[2]
# Default PBO template pack: the committed mission pack at the pinned commit, so the
# Workshop PBO and the friend bundle carry the same interiors.
TEMPLATES_REL = 'mission/hollow-country/interiors/templates'
ADDONS = ship_inputs.ADDONS
NATIVE_SCRIPTS = Path.home() / '.cache/hollow-country/native-scripts/scripts-1.30.164289'


def run(command, cwd=ROOT):
    result = subprocess.run([str(arg) for arg in command], cwd=cwd, capture_output=True,
                            text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0'),
                            timeout=1800)
    if result.returncode:
        # Child diagnostics can contain private identifiers or local absolute paths.
        raise ValueError('Build command failed: ' + Path(str(command[0])).name)
    return result.stdout


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def build_number(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', value):
        raise argparse.ArgumentTypeError('build number must contain only letters, digits, _ or -')
    return value


def resolve_commit(commit, allow_unpushed=False):
    sha = run(['git', 'rev-parse', '--verify', '--end-of-options', commit + '^{commit}']).strip()
    if not allow_unpushed:
        run(['git', 'merge-base', '--is-ancestor', sha, 'origin/main'])
    return sha


def is_dirty(tree):
    return bool(run(['git', 'status', '--porcelain', '--untracked-files=all'], tree).strip())


@contextmanager
def worktree(sha, number):
    tree = CACHE / ('build-' + number)
    if tree.exists() or tree.is_symlink():
        raise ValueError('Build worktree already exists; inspect it before choosing another build number')
    tree.parent.mkdir(parents=True, exist_ok=True)
    run(['git', 'worktree', 'add', '--detach', tree, sha])
    try:
        if is_dirty(tree):
            raise ValueError('Fresh build worktree is dirty')
        yield tree
    finally:
        if is_dirty(tree):
            print('Build worktree is dirty; retained at ~/.cache/hollow-country/build-' + number,
                  file=sys.stderr)
        else:
            run(['git', 'worktree', 'remove', tree])


def json_record_counts(value, prefix=''):
    """Count every array by JSON pointer, including Sites rather than just top-level keys."""
    counts = {}
    if isinstance(value, list):
        counts[prefix or '/'] = len(value)
        for i, child in enumerate(value):
            if isinstance(child, (dict, list)):
                counts.update(json_record_counts(child, prefix + '/' + str(i)))
    elif isinstance(value, dict):
        for key, child in value.items():
            token = str(key).replace('~', '~0').replace('/', '~1')
            counts.update(json_record_counts(child, prefix + '/' + token))
    return counts


def source_json(tree):
    rows = {}
    # A superset of bundle inputs: all authored mission/config/default profile JSON.
    for folder in ('mission', 'config', 'mods/HollowCountry/data/defaults',
                   'mods/HollowCountryExpansionAI/data/defaults'):
        for path in sorted((tree / folder).rglob('*.json')):
            if path.is_symlink():
                raise ValueError('Symlinked JSON source refused')
            value = json.loads(path.read_bytes())
            counts = json_record_counts(value)
            rows[path.relative_to(tree).as_posix()] = {
                'sha256': digest(path), 'record_counts': counts,
                'records': len(value) if isinstance(value, (list, dict)) else 1}
    return rows


def copy_templates(source, dest):
    if not source.is_dir() or source.is_symlink():
        raise ValueError('Template input must be an existing directory')
    if source.resolve().is_relative_to(dest.resolve()):
        raise ValueError('Template source cannot be inside the injected destination')
    rows = {}
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlinked template input refused')
        if not path.is_file() or path.suffix != '.json' or path.name == 'receipt.json':
            continue
        rel = path.relative_to(source)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        rows[rel.as_posix()] = digest(target)
    if not rows:
        raise ValueError('No template JSON files found')
    return rows


def pbo_prefix(path):
    """Read only the PBO header's prefix property (empty string when absent)."""
    with open(path, 'rb') as stream:
        head = stream.read(4096)
    if not head.startswith(b'\0') or head[1:5] != b'sreV':
        return ''
    fields = head[21:].split(b'\0')
    for key, value in zip(fields[0::2], fields[1::2]):
        if not key:
            break
        if key == b'prefix':
            return value.decode('ascii', 'replace')
    return ''


def native_compile_gate(tree, sha, workshop=WORKSHOP, addons=ADDONS):
    server_root, prefix, reason = compile_gate.prerequisites()
    if reason:
        print('compile gate not run: ' + reason, flush=True)
        return {'ran': False, 'passed': None, 'status': 'not_run', 'reason': reason,
                'commit': sha}
    print('Native compile gate for pinned commit ' + sha, flush=True)
    result = subprocess.run(
        [sys.executable, '-B', str(ROOT / 'tools/release/compile_gate.py'),
         '--tree', str(tree), '--commit', sha, '--server-root', str(server_root),
         '--prefix', str(prefix), '--workshop', str(workshop), '--addons', str(addons)], cwd=tree, capture_output=True, text=True,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0'), timeout=1800)
    for line in (result.stdout + '\n' + result.stderr).splitlines():
        print(compile_gate.private(line), flush=True)
    if result.returncode:
        raise ValueError('Native compile gate failed for pinned commit')
    return {'ran': True, 'passed': True, 'status': 'passed', 'commit': sha}


def build(args):
    sha = resolve_commit(args.commit, args.allow_unpushed)
    out = (args.out or Path('/mnt/d/HollowCountryLocal/signed-v1-' + args.build)).absolute()
    if out.exists() or out.is_symlink():
        raise ValueError('Release output already exists; choose a fresh directory')
    # Refuse output/input placement that could modify the caller checkout.
    if out.resolve().is_relative_to(ROOT) or out.resolve().is_relative_to(CACHE / ('build-' + args.build)):
        raise ValueError('Release output must be outside the source/build worktree')
    with worktree(sha, args.build) as tree, tempfile.TemporaryDirectory(prefix='hc-release-') as temp:
        scratch = Path(temp)
        target = tree / 'mods/HollowCountry/data/defaults/templates'
        backup = scratch / 'original-templates'
        if any(p.is_symlink() for p in (target, *target.parents)):
            raise ValueError('Symlinked template destination refused')
        had_templates = target.exists()
        if had_templates:
            shutil.copytree(target, backup, symlinks=True)
        attachment_config = tree / 'mods/HollowCountryExpansionAI/config.cpp'
        if any(p.is_symlink() for p in (attachment_config, *attachment_config.parents)):
            raise ValueError('Symlinked attachment sizing destination refused')
        original_attachment_config = attachment_config.read_bytes()
        injected_attachment_config = None
        try:
            sources = source_json(tree)
            templates = copy_templates(args.templates.absolute() if args.templates else tree / TEMPLATES_REL, target)
            py = [sys.executable, '-B']
            # The pinned generator verifies the committed table against its rules
            # and generator hashes; provider identifiers enter only this tree.
            attachment_scale = json.loads(run(
                [*py, '-m', 'tools.package.inventory_sizes', '--inject', tree], tree))
            injected_attachment_config = attachment_config.read_bytes()
            # Build 098 shipped a keyword name that only the native compiler refused; lint the
            # pinned tree first so known compile refusals never reach a signed build.
            lint = [*py, '-m', 'tools.validate.enforce_lint']
            if NATIVE_SCRIPTS.is_dir():
                lint += ['--native-scripts', NATIVE_SCRIPTS]
            print('Linting pinned commit ' + sha, flush=True)
            run(lint, cwd=tree)
            workshop = Path(getattr(args, 'workshop', WORKSHOP)).absolute()
            guard_dir = scratch / 'weapon-pack-guards'
            run([*py, '-m', 'tools.package.weapon_pack_guards', '--declared-stack',
                 '--workshop', workshop, '--out', guard_dir], tree)
            guard_receipt = json.loads((guard_dir / 'weapon-pack-guards.json').read_bytes())
            gate_result = native_compile_gate(tree, sha, workshop, args.addons.absolute())
            if guard_receipt['status'] == 'generated' and gate_result['passed'] is True:
                guard_receipt['native_compile'] = 'passed'
            print('Packing pinned commit ' + sha, flush=True)
            for mod, name, prefix in (
                    ('HollowCountry', 'hollowcountry', 'HollowCountry'),
                    ('HollowCountryExpansionAI', 'hollowcountryexpansionai', 'HollowCountryExpansionAI')):
                pbo = scratch / (name + '.pbo')
                run([*py, '-m', 'tools.package.pbo', 'pbo', '--prefix', prefix,
                     '--addon', tree / 'mods' / mod, '--out', pbo], tree)
                run([*py, '-m', 'tools.package.pbo', 'verify', '--prefix', prefix, pbo], tree)
            print('Building animation addon', flush=True)
            shutil.copyfile(ship_inputs.build_anims(tree, args.addons.absolute(), scratch, run),
                            scratch / 'hollowcountryanims.pbo')
            stage = scratch / 'output'
            stage.mkdir()
            reports = {}
            guard_name = guard_receipt['pbo'] if guard_receipt['status'] == 'generated' else None
            if guard_name:
                shutil.copyfile(guard_dir / guard_name, scratch / guard_name)
            signing_inputs = ship_inputs.signing_inputs(guard_name)
            for name, mod, label in signing_inputs:
                print('Signing and verifying ' + name, flush=True)
                signed = scratch / ('signed-' + label)
                reports[label] = sign(scratch / (name + '.pbo'), signed)
                for folder in ('addons', 'keys'):
                    shutil.copytree(signed / folder, stage / ('@' + mod) / folder, dirs_exist_ok=True)
                shutil.copyfile(signed / 'signing-report.json', stage / ('signing-report-' + label + '.json'))
            for mod in ('HollowCountry', 'HollowCountryExpansionAI'):
                for filename in ('mod.cpp', 'meta.cpp'):
                    shutil.copyfile(tree / 'mods' / mod / filename, stage / ('@' + mod) / filename)
            if any(p.suffix.lower() == '.biprivatekey' for p in stage.rglob('*')):
                raise ValueError('Private key in release output refused')
            # Two PBOs with one prefix in one mod folder crash the native server
            # while it mounts packages (build 121); refuse that layout here.
            for addons in sorted(stage.glob('@*/addons')):
                seen = {}
                for packed in sorted(addons.glob('*.pbo')):
                    prefix = pbo_prefix(packed)
                    if prefix.casefold() in seen:
                        raise ValueError('Duplicate PBO prefix ' + prefix + ' in ' + addons.parent.name + ': '
                                         + seen[prefix.casefold()] + ', ' + packed.name)
                    seen[prefix.casefold()] = packed.name
            shutil.rmtree(target)
            if had_templates:
                shutil.copytree(backup, target, symlinks=True)
            # Admit exactly the generated bytes. A build step changing any other
            # portion (or even the injection itself) must leave the tree dirty.
            if attachment_config.read_bytes() != injected_attachment_config:
                raise ValueError('Build changed source outside attachment sizing injection')
            attachment_config.write_bytes(original_attachment_config)
            if is_dirty(tree):
                raise ValueError('Build changed tracked/untracked source outside allowed injections')
            manifest = {
                'schema': 1, 'build_number': args.build, 'commit': sha, 'dirty': False,
                'tool_versions': {'python': platform.python_version(),
                                  'git': run(['git', '--version']).strip(),
                                  'wine': run(['/usr/lib/wine/wine64', '--version']).strip(),
                                  'signing_tools': reports['base']['tools'],
                                  'source_tools': {str(p): digest(tree / p) for p in (
                                      'tools/package/pbo.py', 'tools/package/weapon_pack_guards.py',
                                      'tools/setup/workshop_mods.json', 'tools/anim/build_infected_clips.py',
                                      'tools/anim/build_anims_addon.py')},
                                  'driver_tools': {p: digest(ROOT / p) for p in (
                                      'tools/release/release.py', 'tools/release/compile_gate.py', 'tools/package/sign.py',
                                      'tools/package/sign_wine.py')}},
                'files': {p.relative_to(stage).as_posix(): digest(p)
                          for p in sorted(stage.rglob('*')) if p.is_file()},
                # friend_bundle --build-manifest compares this exact PBO catalogue.
                'pbos': {p.relative_to(stage).as_posix(): digest(p)
                         for p in sorted(stage.rglob('*.pbo')) if p.is_file()},
                'weapon_pack_guards': guard_receipt,
                'templates': templates, 'attachment_scale': attachment_scale, 'source_json': sources,
                'signatures_verified': True, 'compile_gate': gate_result, 'runtime_acceptance': 'pending'}
            (stage / 'BUILD_MANIFEST.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(stage, out)
            print('Release complete; all PBO signatures verified; BUILD_MANIFEST.json written')
        finally:
            # Restore only our exact injection; retain unexpected changes for inspection.
            if injected_attachment_config is not None and attachment_config.read_bytes() == injected_attachment_config:
                attachment_config.write_bytes(original_attachment_config)
            # Undo only the explicit template injection; never force-remove a dirty worktree.
            if target.exists():
                shutil.rmtree(target)
            if had_templates:
                shutil.copytree(backup, target, symlinks=True)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=build_number)
    parser.add_argument('--commit', default='HEAD')
    parser.add_argument('--allow-unpushed', action='store_true')
    parser.add_argument('--templates', type=Path, help='override pack (default: the commit\'s ' + TEMPLATES_REL + ')')
    parser.add_argument('--addons', type=Path, default=ADDONS)
    parser.add_argument('--workshop', type=Path, default=WORKSHOP, help='installed Workshop content root for guard verification')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    try:
        build(args)
    except (OSError, ValueError, subprocess.SubprocessError):
        parser.exit(1, 'Release failed; check commit ancestry, inputs, cached signing tools and retained worktree.\n')


if __name__ == '__main__':
    main()
