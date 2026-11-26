"""Read-only update discovery and offline DayZ cache preparation. Never launches DayZ."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from tools.audit.pbo_config import read_pbo_index, read_member
from tools.validate import dayz_build

ROOT = dayz_build.ROOT
APPS = {'221100': 'Client', '223350': 'Server', '830640': 'Tools'}
CLIENT_APPS = Path('/mnt/g/SteamLibrary/steamapps')
SERVER_APPS = Path('/mnt/d/SteamLibrary/steamapps')
REPORT_ROOT = dayz_build.CACHE / 'dayz-update'
MAX_EXE = 128 * 1024 * 1024
MAX_MEMBER = 16 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024


def safe(text):
    """Only sanitized tool diagnostics belong in reports."""
    from tools.release.rpt_summary import filtered
    text = str(text).replace(str(Path.home()), '~')
    return '\n'.join(value for line in text.splitlines() if (value := filtered(line)))


def scrub(value):
    if isinstance(value, str):
        return safe(value)
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


parse_acf = dayz_build.parse_acf
read_acf = dayz_build.read_acf
manifest = dayz_build.manifest
build_check = dayz_build.build_check


def installed_server(args):
    # Existing setup/release probes use HC_SERVER_ROOT. Never write into it.
    configured = getattr(args, 'server_root', None) or os.environ.get('HC_SERVER_ROOT')
    return Path(configured).expanduser() if configured else manifest('223350', args.client_apps, args.server_apps)['root']


def parse_exe_version(data):
    """Extract a UTF-16 FileVersion/ProductVersion string; reject conflicting versions."""
    versions = set()
    for key in ('FileVersion', 'ProductVersion'):
        marker = (key + '\0').encode('utf-16le')
        start = 0
        while (offset := data.find(marker, start)) >= 0:
            start = offset + len(marker)
            tail = data[start:start + 160]
            text = tail.decode('utf-16le', errors='ignore').lstrip('\0 ')
            match = re.match(r'(\d+)\s*[.,]\s*(\d+)\s*[.,]\s*(\d+)(?:\s*[.,]\s*(\d+))?\x00', text)
            if match:
                major, minor, revision, tail_version = match.groups()
                if key == 'FileVersion' and tail_version and len(revision) == 3 and len(tail_version) == 3:
                    revision += tail_version
                versions.add('.'.join((major, minor, revision)))
    if len(versions) != 1:
        raise ValueError('executable version missing or ambiguous')
    return versions.pop()


def exe_version(path):
    with Path(path).open('rb') as stream:
        data = stream.read(MAX_EXE + 1)
    if len(data) > MAX_EXE:
        raise ValueError('executable exceeds read budget')
    return parse_exe_version(data)


def request_json(url, payload=None):
    request = urllib.request.Request(url, data=payload, headers={'User-Agent': 'hollow-country-tools'})
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError('network response exceeds budget')
    return json.loads(raw)


def latest_app(appid):
    doc = request_json('https://api.steamcmd.net/v1/info/' + appid)
    branches = doc['data'][appid]['depots']['branches']
    return {name: str(branches.get(name, {}).get('buildid', '')) or None
            for name in ('public', 'experimental')}


def latest_workshop(ids):
    fields = {'itemcount': str(len(ids)), **{'publishedfileids[%d]' % i: ident for i, ident in enumerate(ids)}}
    doc = request_json('https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/',
                       urllib.parse.urlencode(fields).encode('ascii'))
    return {str(row['publishedfileid']): row for row in doc['response']['publishedfiledetails']
            if row.get('result') == 1}


def app_state(installed, pin, public=None, experimental=None, network=True):
    if installed is None:
        return 'unknown(network)'
    if public and int(public) > int(installed):
        return 'update-available'
    if installed != pin:
        return 'installed-not-pinned'
    if not network or public is None:
        return 'unknown(network)'
    if experimental and int(experimental) > int(public):
        return 'experimental-only'
    return 'current'


def workshop_state(client, server, latest):
    if latest is not None and any(value is not None and int(value) < int(latest) for value in (client, server)):
        return 'update-available'
    if latest is None or client is None or server is None:
        return 'unknown(network)'
    return 'current'


def receipt_times(doc):
    """Older workshop_sync receipts contain file hashes only: no invented timestamps."""
    result = {}
    for group in ('mods', 'items', 'files'):
        rows = doc.get(group, [])
        if isinstance(rows, dict):
            rows = [dict(row, id=key) for key, row in rows.items() if isinstance(row, dict)]
        for row in rows:
            ident = row.get('id', row.get('publishedfileid'))
            stamp = row.get('timeupdated', row.get('time_updated'))
            if ident and stamp is not None:
                result[str(ident)] = int(stamp)
    return result


def check(args):
    pin = dayz_build.pin_record()
    ids = [str(row['id']) for row in json.loads((ROOT / 'tools/setup/workshop_mods.json').read_text())['mods'] if row.get('id')]
    remote, workshop = {}, {}
    errors = []
    if not args.offline:
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = {appid: pool.submit(latest_app, appid) for appid in APPS}
            workshop_job = pool.submit(latest_workshop, ids)
            for appid, job in jobs.items():
                try:
                    remote[appid] = job.result()
                except Exception:
                    errors.append(APPS[appid] + ': network data unavailable')
            try:
                workshop = workshop_job.result()
            except Exception:
                errors.append('Workshop: network data unavailable')
    rows = []
    for appid, name in APPS.items():
        installed, version = None, None
        try:
            local = manifest(appid, args.client_apps, args.server_apps)
            installed = local['buildid']
            if appid != '830640':
                root = installed_server(args) if appid == '223350' else local['root']
                version = exe_version(root / ('DayZServer_x64.exe' if appid == '223350' else 'DayZ_x64.exe'))
        except (OSError, ValueError, KeyError):
            errors.append(name + ': installed manifest or executable version unavailable')
        branch = remote.get(appid, {})
        state = app_state(installed, pin['steam'].get(appid), branch.get('public'), branch.get('experimental'), not args.offline)
        if version and version != dayz_build.pinned() and state in ('current', 'unknown(network)', 'experimental-only'):
            state = 'installed-not-pinned'
        if appid != '830640' and version is None and state in ('current', 'experimental-only'):
            state = 'unknown(network)'
        rows.append(dict(kind='app', id=appid, name=name, installed=installed, version=version,
                         pinned=pin['steam'].get(appid), public=branch.get('public'), experimental=branch.get('experimental'), state=state))
    client, server = {}, {}
    try:
        acf = read_acf(Path(args.client_apps) / 'workshop/appworkshop_221100.acf')['appworkshop']
        client = {ident: int(row['timeupdated']) for ident, row in acf.get('workshopitemsinstalled', {}).items() if 'timeupdated' in row}
    except (OSError, ValueError, KeyError):
        errors.append('Workshop: client ACF unavailable')
    try:
        receipt = installed_server(args) / 'hollow-country-workshop-receipt.json'
        if receipt.is_file():
            server = receipt_times(json.loads(receipt.read_text()))
    except (OSError, ValueError, KeyError):
        errors.append('Workshop: server receipt unavailable')
    if any(ident not in server for ident in ids):
        errors.append('Workshop: server receipt timestamps absent; freshness unknown')
    for ident in ids:
        row = workshop.get(ident, {})
        latest = row.get('time_updated')
        rows.append(dict(kind='workshop', id=ident, name=row.get('title', 'Workshop ' + ident), installed=client.get(ident),
                         server=server.get(ident), public=latest, experimental=None, pinned=None,
                         state=workshop_state(client.get(ident), server.get(ident), latest)))
    result = dict(schema=1, build=dayz_build.pinned(), offline=args.offline, rows=rows, notes=errors)
    if args.json:
        print(json.dumps(scrub(result), indent=2))
    else:
        print('Pin: ' + result['build'] + (' (offline; remote data skipped)' if args.offline else ''))
        print('App/dependency | Installed client / server | Pin | Public | Experimental | Exe | State')
        print('--- | --- | --- | --- | --- | --- | ---')
        for row in rows:
            label = safe(row['name']).replace('|', '/').replace('\n', ' ')
            installed = str(row.get('installed') or '?')
            if row['kind'] == 'workshop':
                installed += ' / ' + str(row.get('server') or '?')
            print(' | '.join(str(value or '?') for value in (label, installed, row['pinned'], row['public'], row['experimental'], row.get('version'), row['state'])))
        for note in errors:
            print('Note: ' + note)
    if any(row['state'] in ('update-available', 'installed-not-pinned', 'experimental-only') for row in rows):
        return 10
    return 2 if any(row['state'] == 'unknown(network)' for row in rows) else 0


def no_links(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink cache/report destination refused')


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def extract_scripts(pbo, destination):
    """Validate all members first, extract privately, compare existing cache, atomic rename."""
    destination = Path(destination).absolute()
    no_links(destination)
    index = read_pbo_index(pbo)
    entries, seen, total = [], set(), 0
    for entry in index['entries']:
        name = entry['name'].replace('\\', '/')
        path = Path(name)
        if (not name or PureWindowsPath(name).drive or path.is_absolute() or
                any(part in ('', '.', '..') for part in name.split('/')) or ':' in name):
            raise ValueError('unsafe PBO member path')
        if entry['method'] != 0:
            raise ValueError('compressed PBO member refused')
        if entry['size'] > MAX_MEMBER:
            raise ValueError('PBO member exceeds budget')
        total += entry['size']
        if total > MAX_TOTAL:
            raise ValueError('PBO total exceeds budget')
        if name.casefold() in seen:
            raise ValueError('duplicate PBO member path')
        seen.add(name.casefold())
        entries.append((entry, path))
    if not entries:
        raise ValueError('empty scripts PBO refused')
    digest = sha256(pbo)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.dayz-scripts-', dir=destination.parent) as temporary:
        stage = Path(temporary) / 'scripts'
        stage.mkdir()
        for entry, relative in entries:
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(read_member(pbo, index, entry['name'], max_bytes=MAX_MEMBER))
        if sha256(pbo) != digest:
            raise ValueError('scripts PBO changed during extraction')
        if destination.exists():
            for path in destination.rglob('*'):
                no_links(path)
            old = {p.relative_to(destination).as_posix(): sha256(p) for p in destination.rglob('*') if p.is_file()}
            new = {p.relative_to(stage).as_posix(): sha256(p) for p in stage.rglob('*') if p.is_file()}
            if old != new:
                raise ValueError('existing different native cache refused')
        else:
            stage.rename(destination)
    return {'sha256': digest, 'entry_count': len(entries), 'bytes': total}


def signature_index(scripts):
    """Full declarations, including return types and overloads (the names index omits returns)."""
    from tools.validate import enforce_source as es, native_symbols
    result = {}
    for _layer, path in native_symbols._script_files(scripts):
        source = es.Source(path, path.read_text(encoding='utf-8', errors='replace'))
        for cls in source.classes:
            result.setdefault('class:' + cls.name, set()).add((str(source.layer), cls.base, str(cls.modded)))
            for field in cls.fields:
                result.setdefault('field:' + cls.name + '.' + field.name, set()).add((str(source.layer), field.type, ' '.join(sorted(field.modifiers))))
            for method in source.class_signatures(cls):
                header = source.code[source.header_start(method):method.offset]
                returned = re.search(r'([A-Za-z_]\w*(?:\s*<[^;{}()]*>)?)\s*$', header)
                return_type = returned[1] if returned and returned[1] not in es.MODIFIERS else ''
                declaration = (str(source.layer), return_type, ' '.join(sorted(method.modifiers)),
                               ','.join(native_symbols._parameter_types(method.params)))
                result.setdefault('method:' + cls.name + '.' + method.name, set()).add(declaration)
    return {name: sorted(rows) for name, rows in sorted(result.items())}


def symbol_diff(old, new, references):
    """Conservative name scan: retain member changes when the member OR owner is referenced."""
    all_changes = []
    for key in sorted(old):
        if key not in new or old[key] != new[key]:
            all_changes.append({'symbol': key, 'change': 'removed' if key not in new else 'changed',
                                'before': old[key], 'after': new.get(key)})
    filtered = [row for row in all_changes if set(row['symbol'].split(':', 1)[1].split('.')) & references]
    return {'full_count': len(all_changes), 'referenced_count': len(filtered), 'referenced': filtered,
            'filter': 'conservative identifier scan of mods/**/*.c; owner OR member match'}


def run_tool(module, arguments, build):
    if module == 'tools.package.regenerate_all' and os.environ.get('HC_NO_DAYZ_TOOLS') == '1':
        arguments = [*arguments, '--image-to-paa', ROOT / 'build/disabled-ImageToPAA.exe']
    try:
        result = subprocess.run([sys.executable, '-B', '-m', module, *map(str, arguments)], cwd=ROOT,
                                env={**os.environ, 'HC_DAYZ_BUILD': build, 'PYTHONDONTWRITEBYTECODE': '1'},
                                capture_output=True, text=True, errors='replace', timeout=1800)
    except (OSError, subprocess.SubprocessError) as error:
        return {'passed': False, 'exit_code': 2, 'output': module + ': launch/timeout failure (' + type(error).__name__ + ')'}
    return {'passed': result.returncode == 0, 'exit_code': result.returncode,
            'output': safe(result.stdout + '\n' + result.stderr)}


def write_report(folder, report):
    no_links(folder)
    folder.mkdir(parents=True, exist_ok=True)
    report = scrub(report)
    markdown = ['# DayZ ' + report['build'] + ' offline preparation', '',
                'Offline source evidence only; native compile, boot and gameplay remain pending.', '',
                '```json', json.dumps(report, indent=2), '```', '']
    for name, content in (('report.json', json.dumps(report, indent=2) + '\n'), ('report.md', '\n'.join(markdown))):
        no_links(folder / name)
        (folder / name).write_text(content + '\n', encoding='utf-8')


def target_build(args):
    return exe_version(installed_server(args) / 'DayZServer_x64.exe') if args.build == 'auto' else dayz_build.build_value(args.build)


def prepare(args):
    build = target_build(args)
    server = installed_server(args)
    if exe_version(server / 'DayZServer_x64.exe') != build:
        raise ValueError('installed server executable does not equal target build')
    destination = Path(args.cache_root).expanduser() / ('scripts-' + build)
    no_links(destination.absolute())
    protected = [server, Path(args.client_apps), Path(args.server_apps)]
    for path in (destination, Path(args.report_root).expanduser() / build):
        if any(path.resolve().is_relative_to(root.resolve()) for root in protected):
            raise ValueError('cache/report destination inside installed Steam inputs refused')
    extraction = extract_scripts(server / 'dta/scripts.pbo', destination)
    report = dict(schema=1, build=build, old_build=dayz_build.pin_record()['build'],
                  cache=str(destination.absolute()), extraction=extraction, prepared=False, native_steps={})
    folder = Path(args.report_root).expanduser() / build
    write_report(folder, report)
    # Target build travels in the subprocess environment; the repository pin is untouched.
    report['symbols'] = run_tool('tools.validate.native_symbols', ['--native-scripts', destination,
                                '--output', folder / 'native-symbols.json'], build)
    report['names_index'] = run_tool('tools.validate.native_symbols', ['--native-scripts', destination,
                                    '--emit-names-index', '--names-output', dayz_build.names_index_path(build)], build)
    write_report(folder, report)
    old = dayz_build.native_scripts_dir(report['old_build'])
    if not (old / '3_Game').is_dir():
        report['error'] = 'old pinned native scripts required for full signature diff'
        write_report(folder, report)
        raise ValueError(report['error'])
    references = set()
    from tools.validate.enforce_source import Source
    for path in (ROOT / 'mods').rglob('*.c'):
        references.update(re.findall(r'\b[A-Za-z_]\w*\b', Source(path, path.read_text(encoding='utf-8', errors='replace')).code))
    report['api_diff'] = symbol_diff(signature_index(old), signature_index(destination), references)
    for name in ('enforce_lint', 'enforce_perf'):
        report[name] = run_tool('tools.validate.' + name, ['--native-scripts', destination], build)
    report['prepared'] = report['symbols']['passed'] and report['names_index']['passed']
    report['changelog_url'] = dayz_build.pin_record().get('changelog_url')
    write_report(folder, report)
    print(safe('Report: ' + str(folder / 'report.md')))
    print('Extraction: entries=%d sha256=%s' % (extraction['entry_count'], extraction['sha256']))
    print('API changes: full=%d referenced=%d' % (report['api_diff']['full_count'], report['api_diff']['referenced_count']))
    for name in ('symbols', 'names_index', 'enforce_lint', 'enforce_perf'):
        print(name + ': ' + ('PASS' if report[name]['passed'] else 'FAIL'))
    return 0 if report['prepared'] and report['enforce_lint']['passed'] and report['enforce_perf']['passed'] else 2


def load_report(args, build):
    folder = Path(args.report_root).expanduser() / build
    report = json.loads((folder / 'report.json').read_text())
    if report.get('schema') != 1 or report.get('build') != build:
        raise ValueError('prepare report identity mismatch')
    return folder, report


def bump(args):
    build = dayz_build.build_value(args.build)
    folder, report = load_report(args, build)
    if not report.get('prepared'):
        raise ValueError('successful prepare required')
    if not report.get('enforce_lint', {}).get('passed') and not args.force:
        raise ValueError('prepare lint must pass (or --force REASON)')
    if args.force is not None and not safe(args.force).strip():
        raise ValueError('--force requires a reason')
    if exe_version(installed_server(args) / 'DayZServer_x64.exe') != build:
        raise ValueError('installed server no longer equals prepared build')
    if sha256(installed_server(args) / 'dta/scripts.pbo') != report['extraction']['sha256']:
        raise ValueError('installed scripts PBO differs from prepared evidence')
    pin = dayz_build.pin_record()
    pin.update(build=build, steam={appid: manifest(appid, args.client_apps, args.server_apps)['buildid'] for appid in APPS},
               server_scripts_pbo_sha256=report['extraction']['sha256'])
    if args.force:
        report['force_reason'] = safe(args.force)
    no_links(dayz_build.PIN)
    dayz_build.PIN.write_text(json.dumps(pin, indent=2) + '\n')
    # Check mode never changes generated files; name every generator mismatch in its output.
    report['regenerate_all'] = run_tool('tools.package.regenerate_all', ['--check'], build)
    report['bumped'] = True
    write_report(folder, report)
    print('Pin updated: ' + build)
    print(report['regenerate_all']['output'])
    print('Generated files changed by check mode: none; review reported mismatches before committing.')
    return 0 if report['regenerate_all']['passed'] else 2


def next_steps(args):
    build = target_build(args)
    try:
        _, report = load_report(args, build)
    except FileNotFoundError:
        report = {'api_diff': {}, 'native_steps': {}}
    print('Title: DayZ ' + build + ': update checklist\n')
    if not report.get('prepared'):
        print('- [ ] Run offline prepare for ' + build)
    if report.get('prepared') and any(not report.get(name, {}).get('passed') for name in ('enforce_lint', 'enforce_perf')):
        print('- [ ] Resolve failed offline validators and rerun prepare')
    if report.get('regenerate_all', {}).get('passed') is False:
        print('- [ ] Resolve generated-file mismatches reported by regenerate_all before native acceptance')
    if dayz_build.pin_record()['build'] != build:
        print('- [ ] Review API diff, resolve lint and bump the pin')
    steps = (
        ('workshop', 'Review updated dependencies: tools.setup.workshop_sync plan, then owner runs workshop_sync fetch/install as needed'),
        ('compile', 'Queue compile gate through tools.release.test_queue; never while the owner plays'),
        ('soak', 'Run friendcycle and a 30-minute soak via tools.release.release_gate'),
        ('client', 'Owner completes one-client smoke'),
        ('r3', 'Complete R3 release gate and record evidence'),
        ('publish', 'ASK the owner before any GitHub Release or Workshop upload'),
    )
    for key, label in steps:
        if report.get('native_steps', {}).get(key) != 'passed':
            print('- [ ] ' + label)
    diff = report.get('api_diff', {})
    print('\nAPI diff: full=%s; referenced=%s.' % (diff.get('full_count', 'pending'), diff.get('referenced_count', 'pending')))
    for row in diff.get('referenced', []):
        print('- ' + row['change'] + ': ' + row['symbol'])
    print('Changelog: ' + (report.get('changelog_url') or dayz_build.pin_record().get('changelog_url') or 'not supplied'))
    print('\nOffline evidence is source validation only. Attach native gate/soak/client evidence to this issue.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('check', 'prepare', 'bump', 'next'):
        command = commands.add_parser(name)
        command.add_argument('--client-apps', type=Path, default=CLIENT_APPS, help='client and Tools steamapps root')
        command.add_argument('--server-apps', type=Path, default=SERVER_APPS, help='server steamapps root; Tools fallback')
        command.add_argument('--server-root', type=Path, help='installed server; defaults to HC_SERVER_ROOT then appmanifest')
        if name == 'check':
            command.add_argument('--offline', action='store_true')
            command.add_argument('--json', action='store_true')
        else:
            command.add_argument('--build', default='auto', required=name == 'bump')
            command.add_argument('--report-root', type=Path, default=REPORT_ROOT)
        if name == 'prepare':
            command.add_argument('--cache-root', type=Path, default=dayz_build.CACHE / 'native-scripts')
        if name == 'bump':
            command.add_argument('--force', metavar='REASON')
    args = parser.parse_args(argv)
    try:
        return {'check': check, 'prepare': prepare, 'bump': bump, 'next': next_steps}[args.command](args)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print('dayz_update: error: ' + safe(str(exc)), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
