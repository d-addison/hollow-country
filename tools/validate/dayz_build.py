"""Single DayZ build pin and per-build offline cache locations (stdlib only)."""
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PIN = ROOT / 'config/dayz-build.json'
CACHE = Path.home() / '.cache/hollow-country'


def build_value(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('DayZ build must be major.minor.build')
    return value


def pin_record():
    record = json.loads(PIN.read_text(encoding='utf-8'))
    if record.get('schema') != 1:
        raise ValueError('unsupported DayZ pin schema')
    build_value(record.get('build'))
    return record


def pinned():
    return build_value(os.environ.get('HC_DAYZ_BUILD') or pin_record()['build'])


def native_scripts_dir(build=None):
    return CACHE / 'native-scripts' / ('scripts-' + build_value(build or pinned()))


def names_index_path(build=None):
    return ROOT / 'tools/validate/data' / ('vanilla_names_' + build_value(build or pinned()) + '.json')


def symbols_cache_path(build=None):
    return CACHE / ('native-symbols-' + build_value(build or pinned()) + '.json')


CLIENT_APPS = Path('/mnt/g/SteamLibrary/steamapps')
SERVER_APPS = Path('/mnt/d/SteamLibrary/steamapps')
APPS = {'221100': 'Client', '223350': 'Server', '830640': 'Tools'}


def parse_acf(text):
    """Parse Valve KeyValues, including nested objects, escaped quotes and comments."""
    tokens = re.finditer(r'"((?:\\.|[^"\\])*)"|([{}])|(?m://[^\n]*)', text)
    values = [(match[2] if match[2] is not None else match[1].replace('\\"', '"').replace('\\\\', '\\'))
              for match in tokens if match[1] is not None or match[2] is not None]
    position = 0

    def block(nested=False, depth=0):
        nonlocal position
        if depth > 32:
            raise ValueError('ACF nesting exceeds budget')
        result = {}
        while position < len(values):
            key = values[position]
            position += 1
            if key == '}':
                if not nested:
                    raise ValueError('unexpected ACF closing brace')
                return result
            if key == '{' or position == len(values):
                raise ValueError('incomplete ACF key/value')
            value = values[position]
            position += 1
            result[key.lower()] = block(True, depth + 1) if value == '{' else value
        if nested:
            raise ValueError('unclosed ACF object')
        return result
    return block()


def read_acf(path):
    if Path(path).stat().st_size > 16 * 1024 * 1024:
        raise ValueError('ACF exceeds read budget')
    return parse_acf(Path(path).read_text(encoding='utf-8-sig'))


def manifest(appid, client_apps=CLIENT_APPS, server_apps=SERVER_APPS):
    roots = [server_apps] if appid == '223350' else [client_apps]
    if appid == '830640':
        roots.append(server_apps)
    for root in roots:
        path = Path(root) / ('appmanifest_' + appid + '.acf')
        if path.is_file():
            app = read_acf(path)['appstate']
            if app.get('appid') != appid or not str(app.get('buildid', '')).isdigit():
                raise ValueError('invalid app manifest identity/buildid')
            install = app.get('installdir', '')
            if not install or '/' in install or '\\' in install or install in ('.', '..'):
                raise ValueError('invalid app manifest install directory')
            return {'buildid': app['buildid'], 'root': Path(root) / 'common' / install}
    raise ValueError('app manifest unavailable')


def build_check(client_apps=CLIENT_APPS, server_apps=SERVER_APPS, pin=None):
    """Shared preland/R3 check. Any installed/pinned mismatch requires investigation."""
    pin = pin or pin_record()
    mismatches, missing = [], []
    for appid in ('223350', '221100'):
        try:
            installed = manifest(appid, client_apps, server_apps)['buildid']
        except (OSError, ValueError, KeyError):
            missing.append(APPS[appid])
            continue
        expected = str(pin['steam'][appid])
        if installed != expected:
            reason = 'prepare+bump first: native cache is stale' if appid == '223350' and int(installed) > int(expected) else 'installed build differs from pin'
            mismatches.append(APPS[appid] + ': ' + reason)
    if mismatches:
        return 'FAIL', '; '.join(mismatches)
    if missing:
        return 'needs-host-check', 'manifests unreadable: ' + ', '.join(missing)
    return 'pass', 'installed client/server buildids equal pin'


def main(argv=None):
    status, reason = build_check()
    print('dayz_build: ' + status + ': ' + reason)
    return 0 if status == 'pass' else 3 if status == 'needs-host-check' else 1


if __name__ == '__main__':
    raise SystemExit(main())
