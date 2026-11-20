"""Run the actual DayZ compiler under Wine against a checkout or commit.

This launches and stops an isolated DayZServer_x64.exe. Do not execute against
an active server or in a session that forbids game executable launches.
"""
import argparse
import contextlib
import hashlib
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from tools.package import pbo
from tools.setup import wine_compile_probe as probe


def private(text):
    """Only filtered diagnostics go to the terminal; raw logs stay in cache."""
    text = str(text).replace(str(Path.home()), '~')
    text = re.sub(r'(?i)(?:[a-z]:[\\/]|/mnt/[a-z]/)users[\\/][^\\/\s"\']+', '~', text)
    text = re.sub(r'(?i)(?:[a-z]:)?[\\/](?:home|Users)[\\/][^\\/\s"\']+', '~', text)
    text = re.sub(r'\b\d{17}\b', '<identity>', text)
    text = re.sub(r'(?i)\b(password|admin_?id|player_?(?:id|name)|steam_?id)\s*[:=]\s*[^\s,;]+',
                  r'\1=<redacted>', text)
    return text


def git(tree, *args):
    result = subprocess.run(['git', '-C', str(tree), *args],
                            capture_output=True, check=False)
    if result.returncode:
        raise ValueError('git read failed: ' + result.stderr.decode(errors='replace'))
    return result.stdout


@contextlib.contextmanager
def source_tree(tree, commit, cache):
    if not commit:
        yield tree
        return
    sha = git(tree, 'rev-parse', '--verify', '--end-of-options', commit + '^{commit}').decode().strip()
    # Equivalent detached tracked tree without touching read-only .git metadata.
    # No checkout/reset/worktree registration; the unique snapshot always goes away.
    with tempfile.TemporaryDirectory(prefix='tree-' + sha[:12] + '-', dir=cache) as directory:
        root = Path(directory)
        archive = git(tree, 'archive', '--format=tar', sha)
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            for entry in stream:
                relative = Path(entry.name)
                if relative.is_absolute() or '..' in relative.parts:
                    raise ValueError('unsafe archive member')
                target = root / relative
                if entry.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif entry.isfile():
                    if target.suffix.lower() == '.biprivatekey' or target.name == 'hits_privkey.txt':
                        raise ValueError('private signing input forbidden')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with stream.extractfile(entry) as source, target.open('wb') as dest:
                        dest.write(source.read())
                elif entry.issym() or entry.islnk():
                    raise ValueError('links forbidden in compile snapshot')
        yield root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', type=Path, default=Path.cwd(), help='source checkout (default: current directory)')
    parser.add_argument('--commit', help='compile the exact tracked commit, discarding its temporary tree afterwards')
    parser.add_argument('--server-root', type=Path, help='complete isolated Linux-filesystem server copy')
    parser.add_argument('--prefix', type=Path, help='existing reusable isolated Wine prefix')
    parser.add_argument('--cache', type=Path, default=Path.home() / '.cache/hollow-country/compile-gate')
    parser.add_argument('--seconds', type=int, default=300, help='Wine probe budget, 15..900 seconds (default 300; use 900 on a busy host)')
    parser.add_argument('--prepare-only', action='store_true', help='package inputs only; NEVER establishes compiler acceptance')
    args = parser.parse_args()
    if not args.prepare_only and (args.server_root is None or args.prefix is None):
        parser.error('--server-root and --prefix are required unless --prepare-only')
    if not 15 <= args.seconds <= 900:
        parser.error('--seconds must be 15..900')
    started = time.monotonic()
    try:
        cache = args.cache.expanduser().resolve()
        probe.safe(cache)
        cache.mkdir(parents=True, exist_ok=True)
        with source_tree(args.tree.resolve(), args.commit, cache) as tree:
            blob = pbo.pack(pbo.collect_addon(tree / 'mods/HollowCountry'))
            digest = hashlib.sha256(blob).hexdigest()
            package = cache / (digest + '.pbo')
            reused = package.is_file() and package.read_bytes() == blob
            if not reused:
                # Atomic cache publication also tolerates independent packers.
                with tempfile.NamedTemporaryFile(dir=cache, delete=False) as output:
                    temporary = Path(output.name)
                    try:
                        output.write(blob)
                        output.close()
                        os.replace(temporary, package)
                    finally:
                        temporary.unlink(missing_ok=True)
            print('compile_gate: pbo_sha256=' + digest + ' package_cache=' + ('hit' if reused else 'miss'))
            if args.prepare_only:
                print('compile_gate: PREPARED ONLY; native compile NOT RUN')
                return 0
            # Unique experiment: profiles, storage, mission inputs and logs are
            # never reused. Only the server install, Wine prefix and PBO persist.
            experiment = cache / ('run-' + str(time.time_ns()))
            report = probe.run(args.server_root.expanduser().resolve(), package, experiment,
                               args.prefix.expanduser().resolve(), seconds=args.seconds)
            text, _, skipped = probe.collect_logs(experiment)
            errors = [line for line in text.splitlines()
                      if re.search(r"Can't compile|Cannot compile|SCRIPT\s*\(E\)", line, re.I)]
            for line in errors[:12]:
                print('compile_gate: ' + private(line)[:1200])
            # Conservatively reject cascade errors too, rather than risk hiding
            # a primary error with an overly broad cascade exemption.
            passed = report['status'] == 'initialized' and not errors and not skipped
            print('compile_gate: ' + ('PASS' if passed else 'FAIL') + ' status=' + report['status'])
            print('compile_gate: logs=' + private(experiment))
            return 0 if passed else 1
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as error:
        print('compile_gate: FAIL ' + private(error), file=sys.stderr)
        return 1
    finally:
        print('compile_gate: wall_seconds=%.3f' % (time.monotonic() - started))


if __name__ == '__main__':
    raise SystemExit(main())
