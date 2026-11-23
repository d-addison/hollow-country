"""Pack and sign the dev-only HollowCountryTest addon into a scratch folder OUTSIDE the repository.

The test addon (mods/HollowCountryTest, PBO prefix HollowCountryTest, file hollowcountrytest.pbo) holds the
scripted client driver and the setup fixtures the local soak campaign uses. It is never shipped: its prefix is
not in tools.package.pbo.PREFIXES, no release, bundle, friendcycle or Workshop tool lists it, and this module is the
only code that opens pbo.test_prefix_scope().

Signing reuses the existing Wine flow (tools.package.sign_wine, the same development key the local build uses).
This module never reads, copies, prints or creates key material: it only hands the pre-existing key pathnames
to the official signing tool through that flow.

  python3 -B -m tools.testing.test_addon plan            # what would be built; writes nothing
  python3 -B -m tools.testing.test_addon build           # pack + sign into the scratch folder
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

from tools.package import pbo

ROOT = Path(__file__).resolve().parents[2]
SOURCE_REL = 'mods/HollowCountryTest'
FOLDER = '@HollowCountryTest'
PBO_NAME = 'hollowcountrytest.pbo'
SCRATCH = Path.home() / '.cache/hollow-country/test-addon'
# Only addon payload goes into the PBO; a README or other notes beside it never do.
PAYLOAD_TOP = ('scripts', 'gui', 'data')
PAYLOAD_FILES = ('config.cpp', 'inputs.xml', 'mod.cpp', 'meta.cpp', '$PBOPREFIX$')
MOD_CPP = 'name = "HollowCountry Test (dev only, never shipped)";\n'


class TestAddonError(ValueError):
    """The test addon cannot be built; the message names no private path."""


def source_dir(root=ROOT):
    path = Path(root) / SOURCE_REL
    if not path.is_dir():
        raise TestAddonError(SOURCE_REL + ' is not in this checkout (the driver brief adds it)')
    return path


def scratch_outside_repo(scratch, root=ROOT):
    scratch = Path(scratch).absolute()
    root = Path(root).resolve()
    if scratch == root or root in scratch.resolve().parents:
        raise TestAddonError('the scratch folder must be outside the repository')
    return scratch


def payload(source, staging):
    """Copy only addon payload into a throwaway folder so pbo.collect_addon keeps its own allowlist."""
    source = Path(source)
    count = 0
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise TestAddonError('symlink refused in the test addon source')
        rel = path.relative_to(source)
        if path.is_dir() or not (rel.parts[0] in PAYLOAD_TOP or rel.as_posix() in PAYLOAD_FILES):
            continue
        target = Path(staging) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        count += 1
    if not count:
        raise TestAddonError(SOURCE_REL + ' holds no addon payload')
    return count


def collect(root=ROOT):
    """The validated file map of the test addon (the same strict allowlist as every shipped addon)."""
    with tempfile.TemporaryDirectory(prefix='hc-test-addon-') as staging:
        payload(source_dir(root), staging)
        try:
            return pbo.collect_addon(staging, pbo.TEST_PREFIX)
        except ValueError as error:
            raise TestAddonError('test addon source refused: ' + str(error)) from None


def plan(root=ROOT, scratch=SCRATCH):
    files = collect(root)
    return dict(source=SOURCE_REL, prefix=pbo.TEST_PREFIX, pbo=PBO_NAME, folder=FOLDER, files=len(files),
                scripts=sorted(name for name in files if name.endswith('.c')), writes_nothing=True)


def default_signer(source, output):
    # The shared Wine flow; it alone resolves and uses the existing development key.
    from tools.package import sign_wine
    return sign_wine.sign(source, output)


def build(root=ROOT, scratch=SCRATCH, signer=default_signer):
    """Pack under TEST_PREFIX, sign with the dev key, and write scratch/@HollowCountryTest; return a report.

    Always rebuilt from the repo source at this checkout, into a fresh folder (the old one is replaced)."""
    scratch = scratch_outside_repo(scratch, root)
    files = collect(root)
    with pbo.test_prefix_scope():
        blob = pbo.pack(files, pbo.TEST_PREFIX)
        prefix, parsed = pbo.parse(blob, prefixes=(pbo.TEST_PREFIX,))
        if prefix != pbo.TEST_PREFIX or set(parsed) != set(files):
            raise TestAddonError('packed test addon does not round-trip')
        if pbo.pbo_file_name(pbo.TEST_PREFIX) != PBO_NAME:
            raise TestAddonError('unexpected test addon file name')
        scratch.mkdir(parents=True, exist_ok=True)
        work = scratch / 'work'
        if work.exists():
            shutil.rmtree(work)
        work.mkdir()
        source = work / PBO_NAME
        source.write_bytes(blob)
        out = scratch / FOLDER
        if out.exists():
            shutil.rmtree(out)  # sign_and_verify needs a fresh output folder
        try:
            signer(source, out)
        except (OSError, ValueError) as error:
            raise TestAddonError('test addon signing failed: ' + type(error).__name__) from None
    if any(p.suffix.lower() == '.biprivatekey' for p in out.rglob('*')):
        shutil.rmtree(out)
        raise TestAddonError('a private key reached the scratch folder; build refused')
    mod_cpp = Path(root) / SOURCE_REL / 'mod.cpp'
    (out / 'mod.cpp').write_bytes(mod_cpp.read_bytes() if mod_cpp.is_file() else MOD_CPP.encode())
    shutil.rmtree(work)
    signed = out / 'addons' / PBO_NAME
    sigs = sorted(p.name for p in (out / 'addons').glob(PBO_NAME + '.*.bisign'))
    if not signed.is_file() or len(sigs) != 1:
        raise TestAddonError('test addon is not signed')
    return dict(folder=FOLDER, pbo=PBO_NAME, prefix=pbo.TEST_PREFIX, files=len(files), signatures=len(sigs),
                sha256=hashlib.sha256(signed.read_bytes()).hexdigest(), path=str(out))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mode', choices=('plan', 'build'), nargs='?', default='plan')
    parser.add_argument('--scratch', type=Path, default=SCRATCH)
    args = parser.parse_args(argv)
    try:
        result = plan(scratch=args.scratch) if args.mode == 'plan' else build(scratch=args.scratch)
    except TestAddonError as error:
        print('test_addon: ' + str(error))
        return 2
    result = {k: v for k, v in result.items() if k != 'path'}  # never print a local path
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
