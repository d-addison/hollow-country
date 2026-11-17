"""Official Windows DSSignFile + DSCheckSignatures orchestration.

Unit tests use fake tools and synthetic non-keys. Only real tool execution with
real keys can produce a signed-development report. This never accepts runtime.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

try:
    from . import pbo
except ImportError:
    import pbo


def sign_and_verify(source, tools, private, public, output, runner=subprocess.run):
    source, tools, private, public, output = [Path(p).absolute() for p in (source, tools, private, public, output)]
    for path in (source, tools, private, public, output):
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('symlinked signing paths forbidden')
    if output.exists():
        raise ValueError('signing output must be fresh')
    if (private.suffix != '.biprivatekey' or public.suffix != '.bikey'
            or private.stem != public.stem or not re.fullmatch(r'[A-Za-z0-9_-]+', public.stem)):
        raise ValueError('matching private/public key basenames required')
    source_bytes = source.read_bytes()
    prefix, _ = pbo.parse(source_bytes, prefixes=pbo.PREFIXES)
    private.stat()  # do not read/copy/print private material
    public.stat()
    executables = [tools / 'Bin/DsUtils' / name for name in ('DSSignFile.exe', 'DSCheckSignatures.exe')]
    for path in executables:
        if not path.is_file():
            raise ValueError(f'official tool not found: {path.name}')
    (output / 'addons').mkdir(parents=True)
    (output / 'keys').mkdir()
    dest = output / 'addons' / source.name
    dest.write_bytes(source_bytes)
    shutil.copyfile(public, output / 'keys' / public.name)
    commands = [[str(executables[0]), str(private), str(dest)],
                [str(executables[1]), str(output / 'addons'), str(output / 'keys')]]
    sign_log = runner(commands[0], capture_output=True, text=True, shell=False, timeout=60)
    if sign_log.returncode:
        raise ValueError('DSSignFile failed; no verified signature')
    sig = dest.with_name(dest.name + '.' + public.stem + '.bisign')
    if not sig.is_file() or not sig.stat().st_size:
        raise ValueError('DSSignFile did not produce the expected signature')
    check_log = runner(commands[1], capture_output=True, text=True, shell=False, timeout=60)
    text = check_log.stdout + '\n' + check_log.stderr
    (output / 'verification.log').write_text(text, encoding='utf-8')
    # Do not infer success from exit=0 or silence; require a positive result.
    if (check_log.returncode or not re.search(r'^Signature .+ is OK\s*$', text, re.MULTILINE)
            or re.search(r'wrong|not found|not loaded|No signature|deprecated|error', text, re.IGNORECASE)):
        raise ValueError('DSCheckSignatures did not positively verify; release remains gated')
    if dest.read_bytes() != source_bytes:
        raise ValueError('PBO changed during signing')
    report = {'schema': 1, 'status': 'signed-development', 'runtime_acceptance': 'pending',
              'release_allowed': False, 'prefix': prefix,
              'files': {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in (dest, sig, output / 'keys' / public.name)},
              'tools': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in executables}}
    (output / 'signing-report.json').write_bytes(pbo.json_bytes(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('pbo', 'tools', 'private-key', 'public-key', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        report = sign_and_verify(args.pbo, args.tools, args.private_key, args.public_key, args.out)
        print(json.dumps({'status': report['status'], 'release_allowed': False}))
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        parser.exit(1, f'{e}\n')


if __name__ == '__main__':
    main()
