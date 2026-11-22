"""Build a pinned friend bundle, apply it via Windows Python, then check it.

Requires explicit mission/profile/config inputs; no historical profile snapshot default.
Use --build-only to prepare a reviewable bundle without any Windows install calls.
"""
import argparse
import csv
import importlib
import io
import json
from pathlib import Path
import subprocess
import sys

from tools.package import compat_addon
from tools.package.weapon_pack_guards import WORKSHOP, PBO_NAME, declared
from tools.release.release import (ADDONS, TEMPLATES_REL, build, build_number, digest,
                                   native_compile_gate, resolve_commit, run, worktree)


def require_stopped():
    """Unknown process state refuses installation. Never stops or signals a process."""
    try:
        winproc = importlib.import_module('tools.setup.winproc')
    except ModuleNotFoundError as error:
        if error.name != 'tools.setup.winproc':
            raise
    else:
        # Prefer the shared stopped-server guard when available; older revisions
        # without that API use the fail-closed CSV tasklist check below.
        guard = getattr(winproc, 'require_server_stopped', None)
        if guard is not None:
            result = guard()
            if result is False:
                raise ValueError('DayZ server is running or its state is unknown')
            return
    cmd = Path('/mnt/c/Windows/System32/cmd.exe')
    result = subprocess.run([str(cmd), '/d', '/c', 'tasklist /FO CSV /NH'], cwd='/mnt/c',
                            capture_output=True, text=True, timeout=40)
    if result.returncode:
        raise ValueError('Windows process state is unknown; installation refused')
    rows = list(csv.reader(io.StringIO(result.stdout)))
    if not rows or any(len(row) < 5 or not row[1].isdigit() for row in rows):
        raise ValueError('Windows process table is invalid; installation refused')
    if any('dayzserver' in row[0].lower() for row in rows):
        raise ValueError('A DayZ server is running; installation refused')


def windows_path(path):
    path = Path(path).absolute()
    if len(path.parts) < 4 or path.parts[1] != 'mnt' or len(path.parts[2]) != 1:
        raise ValueError('Windows installation requires a bundle under /mnt/<drive>')
    return path.parts[2].upper() + ':\\' + '\\'.join(path.parts[3:])


def install(bundle, server_root, workshop):
    bundle_win = windows_path(bundle)
    # cmd.exe has expansion and quoting semantics beyond normal subprocess argv, and
    # WSL interop backslash-escapes embedded quotes, so paths are passed unquoted.
    for value in (bundle_win, server_root, workshop):
        if any(char in value for char in ' \t\r\n"%!?&|<>^()'):
            raise ValueError('Unsafe Windows command path')
    cmd = '/mnt/c/Windows/System32/cmd.exe'
    for options in (f'--apply --yes --workshop-content {workshop}', '--check'):
        require_stopped()
        command = (f'cd /d {bundle_win} && set PYTHONDONTWRITEBYTECODE=1&& '
                   f'py -3 -B -m tools.setup.friend_install --server-root {server_root} {options}')
        try:
            run([cmd, '/d', '/c', command], Path('/mnt/c'))
        except ValueError as error:
            # The installer's own output can carry private paths; name only the failed step.
            raise ValueError('friend_install ' + options.split()[0] + ' failed; rerun it from the bundle '
                             'folder to see its report') from error
    print('Friend install and --check succeeded')


def cycle(args):
    signed = (args.out or Path('/mnt/d/HollowCountryLocal/signed-v1-' + args.build)).absolute()
    bundle = (args.bundle_out or Path('/mnt/d/HollowCountryLocal/friend-bundle-' + args.build)).absolute()
    if bundle.exists() or bundle.is_symlink():
        raise ValueError('Bundle output already exists')
    built = not signed.exists()
    if built:
        build(args)
    manifest_path = signed / 'BUILD_MANIFEST.json'
    manifest = json.loads(manifest_path.read_text())
    sha = resolve_commit(args.commit, args.allow_unpushed)
    if (manifest.get('schema') != 1 or manifest.get('build_number') != args.build
            or manifest.get('commit') != sha or manifest.get('dirty') is not False
            or manifest.get('signatures_verified') is not True or not manifest.get('files')):
        raise ValueError('Release manifest does not match requested clean, verified build')
    actual = {p.relative_to(signed).as_posix() for p in signed.rglob('*')
              if p.is_file() and p != manifest_path}
    if actual != set(manifest['files']):
        raise ValueError('Release file inventory differs from manifest')
    if any(p.is_symlink() for p in signed.rglob('*')):
        raise ValueError('Symlinked release artifact refused')
    for rel, expected in manifest['files'].items():
        path = signed / rel
        if not path.resolve().is_relative_to(signed.resolve()) or digest(path) != expected:
            raise ValueError('Release artifact hash mismatch')
    if any(p.suffix.lower() == '.biprivatekey' for p in signed.rglob('*')):
        raise ValueError('Private key in release refused')
    with worktree(sha, args.build + '-friend') as tree:
        guard = manifest.get('weapon_pack_guards', {})
        guard_path = '@HollowCountryExpansionAI/addons/' + PBO_NAME
        wanted = declared(tree / 'tools/setup/workshop_mods.json')
        if not isinstance(guard, dict):
            raise ValueError('Invalid release weapon-pack guard receipt; rebuild required')
        if ((wanted and (guard.get('status') != 'generated' or guard_path not in actual
                        or manifest['files'].get(guard_path) != guard.get('sha256')))
                or (not wanted and (guard.get('status') != 'absent' or guard_path in actual))):
            raise ValueError('Release weapon-pack guard differs from declared stack; rebuild required')
        # The compat PBO(s) are built at bundle time and ship in the HCX addons folder; the signed
        # directory must carry exactly the PBOs the build receipt lists, with the receipt's hashes.
        shipped = {rel: sha for rel, sha in manifest['files'].items() if rel.lower().endswith('.pbo')}
        if compat_addon.check_receipt(manifest.get('compat_addon'), shipped):
            raise ValueError('Release compat addon differs from its receipt; rebuild required')
        if not built:
            # Reusing signed artifacts must not bypass today's available gate.
            # The manifest is outside its own hashed file inventory.
            manifest['compile_gate'] = native_compile_gate(tree, sha, args.workshop)
            if (manifest['compile_gate'].get('passed') is True
                    and compat_addon.check_hashes(manifest.get('compat_addon'),
                                                  manifest['compile_gate'].get('compat_sha256'))):
                raise ValueError('Compile gate compat PBOs differ from the release receipt; rebuild required')
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        command = [sys.executable, '-B', '-m', 'tools.setup.friend_bundle', 'build']
        help_text = run([*command, '--help'], tree)
        command += ['--mission', args.mission.absolute(), '--profiles', args.profiles.absolute(),
                    '--server-cfg', args.server_cfg.absolute(),
                    '--mod', signed / '@HollowCountry', '--addon', signed / '@HollowCountryExpansionAI',
                    '--out', bundle]
        if '--build-manifest' in help_text:
            command += ['--build-manifest', manifest_path]
        else:
            print('Pinned friend_bundle has no --build-manifest option; bundle freshness gate unavailable',
                  file=sys.stderr)
        run(command, tree)
    print('Friend bundle built')
    if not args.build_only:
        install(bundle, args.server_root, args.workshop_content)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=build_number)
    parser.add_argument('--commit', default='HEAD')
    parser.add_argument('--allow-unpushed', action='store_true')
    parser.add_argument('--templates', type=Path, help='override pack (default: the commit\'s ' + TEMPLATES_REL + ')')
    parser.add_argument('--addons', type=Path, default=ADDONS)
    parser.add_argument('--workshop', type=Path, default=WORKSHOP, help='installed Workshop content root for building/compiling')
    parser.add_argument('--out', type=Path, help='signed release directory')
    parser.add_argument('--bundle-out', type=Path)
    parser.add_argument('--mission', type=Path, required=True)
    parser.add_argument('--profiles', type=Path, required=True)
    parser.add_argument('--server-cfg', type=Path, required=True)
    parser.add_argument('--server-root', default=r'E:\HollowCountryLocal\friend-local-1')
    parser.add_argument('--workshop-content', default=r'G:\SteamLibrary\steamapps\workshop\content\221100')
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--local-test-waivers', action='store_true',
                        help='local test build: list generated artefacts whose installed inputs are '
                             'unavailable here as BUILD_MANIFEST waivers; the release gate refuses them')
    args = parser.parse_args(argv)
    try:
        from tools.release.host_lock import host_lock
        with host_lock('friendcycle'):
            cycle(args)
    except ValueError as error:
        # ValueError messages here are authored text without paths or identifiers.
        parser.exit(1, 'Friend cycle refused or failed: ' + str(error) + '\n')
    except (OSError, subprocess.SubprocessError) as error:
        parser.exit(1, 'Friend cycle refused or failed (' + type(error).__name__ + '); verify inputs and the stopped-server state.\n')


if __name__ == '__main__':
    main()
