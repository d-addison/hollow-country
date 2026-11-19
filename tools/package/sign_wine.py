"""Sign and positively verify one PBO with the cached official tools under Wine."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from tools.package.sign import sign_and_verify

CACHE = Path.home() / '.cache/hollow-country'


def sign(source, output, toolroot=None, key_dir=None, prefix=None):
    toolroot = Path(toolroot or CACHE / 'official-signing-tools-20261116')
    key_dir = Path(key_dir or CACHE / 'development-signing-20261116')
    prefix = Path(prefix or CACHE / 'wine-signing-20261116')

    def run(command, **kwargs):
        # Only DSSignFile receives the private key pathname. Never read or copy it.
        windows = ['Z:' + str(Path(arg).absolute()).replace('/', '\\') for arg in command]
        return subprocess.run(['/usr/lib/wine/wine64', *windows], cwd=toolroot,
                              env=dict(os.environ, WINEPREFIX=str(prefix), WINEARCH='win64',
                                       WINEDEBUG='-all'), **kwargs)

    return sign_and_verify(source, toolroot,
                           key_dir / 'HollowCountryDevelopment20261116.biprivatekey',
                           key_dir / 'HollowCountryDevelopment20261116.bikey', output, runner=run, reject_diagnostics=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pbo', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--tools', type=Path)
    parser.add_argument('--key-dir', type=Path)
    parser.add_argument('--wine-prefix', type=Path)
    args = parser.parse_args()
    try:
        report = sign(args.pbo, args.out, args.tools, args.key_dir, args.wine_prefix)
    except (OSError, ValueError, subprocess.SubprocessError):
        parser.exit(1, 'Signing/verification failed; inspect the local verification.log if present.\n')
    print(json.dumps({'status': report['status'], 'files': report['files']}))


if __name__ == '__main__':
    main()
