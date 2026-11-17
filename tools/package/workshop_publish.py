"""Prepare the signed @HollowCountry for an Unlisted Steam Workshop upload (the owner runs the upload).

Subcommands (standard library only; no network, no Steam, no subprocess):

``prepare`` validates a signed mod folder against a strict allowlist, stages a clean copy, writes a
steamcmd ``workshop_build_item`` VDF and prints the exact steamcmd command for the owner to run.
``record`` writes ``publishedid = N;`` into the mod's meta.cpp after the first upload so later builds
update the same item and the DayZ launcher can map the mod to its Workshop item.

Only our own mod is ever published: addons/hollowcountry.pbo with its .bisign, keys/*.bikey, mod.cpp and
meta.cpp. Third-party mods (CF, Dabs Framework, Expansion, SNAFU Weapons, Tactical Flava) stay Workshop
dependencies referenced by id. @HollowCountryExpansionAI is a -serverMod and is never published.
Private keys (.biprivatekey), profiles, logs and source are refused.

This tool never asks for, stores, logs or passes a Steam password. The owner runs steamcmd themselves;
steamcmd's interactive login and Steam Guard prompt handle credentials.

Alternative to steamcmd: the DayZ Tools "Publisher" (Steam > DayZ Tools > Publisher) uploads a mod folder
through a GUI. Point it at the staged ``content`` folder that ``prepare`` produced (not at the working
mod folder), set the visibility to Unlisted and keep the Workshop id it shows; then run ``record`` with it.

Visibility: Steam's ERemoteStoragePublishedFileVisibility values are 0 Public, 1 Friends-only, 2 Private
and 3 Unlisted (see the Steamworks documentation for ISteamUGC::SetItemVisibility, and the Steamworks
"Workshop Implementation Guide" for workshop_build_item). Unlisted items are hidden from Workshop search
and visible to anyone holding the link. This tool accepts only Unlisted.

Offline validation establishes nothing about Workshop or DayZ behaviour; the upload and the join-time
auto-subscribe stay pending owner acceptance.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import sys
import tempfile

APP_ID = '221100'  # DayZ (the Workshop app id used by DayZ mods)
VISIBILITY_UNLISTED = '3'  # ERemoteStoragePublishedFileVisibility_Unlisted
TITLE = 'Hollow Country'
DESCRIPTION = ('Hollow Country is a DayZ survival overhaul for a small private server of three to six players. '
               'This item contains only the signed Hollow Country mod. When you join the server the DayZ launcher '
               'subscribes to it automatically. Optional weapon packs and the PvE patrol mods are separate '
               'Workshop items and are never bundled here.')
PBO_NAME = 'hollowcountry.pbo'
MAX_PREVIEW_BYTES = 1024 * 1024
MAX_ENTRIES = 5000
MAX_META_BYTES = 64 * 1024
MAX_NOTE = 2000
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
VDF_NAME = 'workshop_item.vdf'
OUR_OUTPUTS = ('content', VDF_NAME, 'preview.png')
COMMAND_USER = '<their_username>'

BISIGN = re.compile(r'^' + re.escape(PBO_NAME) + r'\.([A-Za-z0-9_.-]+)\.bisign$')
BIKEY = re.compile(r'^([A-Za-z0-9_.-]+)\.bikey$')
PUBLISHED = re.compile(r'(?im)^[ \t]*publishedid[ \t]*=[ \t]*(\d+)[ \t]*;')
PROTOCOL = re.compile(r'(?im)^[ \t]*protocol[ \t]*=[^;\r\n]*;[ \t]*(?:\r\n|\n|\r|$)')
DRIVE_PATH = re.compile(r'^/mnt/([A-Za-z])(?:/(.*))?$')


class PublishError(ValueError):
    """A safety rule or precondition failed; nothing further was written."""


def to_windows(path):
    """Convert a WSL /mnt/<drive>/... path to a Windows path; any other path is returned unchanged."""
    match = DRIVE_PATH.match(str(path))
    if not match:
        return str(path)
    return match.group(1).upper() + ':\\' + (match.group(2) or '').replace('/', '\\')


# ---------------------------------------------------------------- validation
def _scan(root):
    """Every entry under root as (relative posix path, lstat result); symlinks are never followed."""
    found = []
    stack = [(root, '')]
    while stack:
        directory, prefix = stack.pop()
        with os.scandir(directory) as it:
            for entry in sorted(it, key=lambda e: e.name):
                rel = prefix + entry.name
                if entry.is_symlink():
                    raise PublishError('%s is a symlink; symlinks are never published' % rel)
                info = entry.stat(follow_symlinks=False)
                found.append((rel, info))
                if len(found) > MAX_ENTRIES:
                    raise PublishError('more than %d entries; this is not a mod folder' % MAX_ENTRIES)
                if entry.is_dir(follow_symlinks=False):
                    stack.append((entry.path, rel + '/'))
    return found


def validate_content(mod):
    """Check a signed mod folder against the allowlist and return its file list and pbo digest.

    Allowed: addons/hollowcountry.pbo, addons/hollowcountry.pbo.<key>.bisign (at least one), keys/<key>.bikey
    (one per signing key), mod.cpp and, optionally, meta.cpp. Anything else is refused.
    """
    mod = Path(mod)
    if mod.is_symlink():
        raise PublishError('%s is a symlink; give the real mod folder' % mod)
    if not mod.is_dir():
        raise PublishError('%s is not a directory' % mod)
    entries = _scan(str(mod))
    for rel, _ in entries:
        if rel.lower().endswith('.biprivatekey'):
            raise PublishError('%s is a private key; it must never be published' % rel)
    files = []
    bisigns, bikeys = set(), set()
    for rel, info in entries:
        parts = rel.split('/')
        if stat.S_ISDIR(info.st_mode):
            if rel not in ('addons', 'keys'):
                raise PublishError('%s/ is not allowed in the content folder' % rel)
            continue
        if not stat.S_ISREG(info.st_mode):
            raise PublishError('%s is not a regular file' % rel)
        if info.st_nlink > 1:
            raise PublishError('%s is a hard link (%d names); hard links are never published' % (rel, info.st_nlink))
        if info.st_size == 0:
            raise PublishError('%s is empty' % rel)
        if len(parts) == 1 and rel in ('mod.cpp', 'meta.cpp'):
            if rel == 'meta.cpp' and info.st_size > MAX_META_BYTES:
                raise PublishError('meta.cpp is unexpectedly large')
        elif len(parts) == 2 and parts[0] == 'addons' and rel == 'addons/' + PBO_NAME:
            pass
        elif len(parts) == 2 and parts[0] == 'addons' and BISIGN.match(parts[1]):
            bisigns.add(BISIGN.match(parts[1]).group(1))
        elif len(parts) == 2 and parts[0] == 'keys' and BIKEY.match(parts[1]):
            bikeys.add(BIKEY.match(parts[1]).group(1))
        else:
            raise PublishError('%s is not allowed in the content folder' % rel)
        files.append(rel)
    if 'mod.cpp' not in files:
        raise PublishError('mod.cpp is missing')
    if 'addons/' + PBO_NAME not in files:
        raise PublishError('addons/%s is missing' % PBO_NAME)
    if not bisigns:
        raise PublishError('addons/%s has no matching .bisign signature' % PBO_NAME)
    if not bikeys:
        raise PublishError('keys/ has no public .bikey')
    for key in sorted(bisigns - bikeys):
        raise PublishError('signature key "%s" has no keys/%s.bikey' % (key, key))
    digest = hashlib.sha256((mod / 'addons' / PBO_NAME).read_bytes()).hexdigest()
    return {'files': sorted(files), 'pbo_sha256': digest, 'keys': sorted(bikeys)}


# ---------------------------------------------------------------- meta.cpp
def _published_id(mod):
    meta = Path(mod) / 'meta.cpp'
    if not meta.is_file() or meta.is_symlink():
        return None
    matches = PUBLISHED.findall(meta.read_text(encoding='utf-8', errors='replace'))
    if len(matches) > 1:
        raise PublishError('meta.cpp has more than one publishedid line')
    value = int(matches[0]) if matches else 0
    return value or None


def _check_id(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PublishError('published id must be a positive integer, got %r' % (value,))
    return value


def _atomic_write(path, data):
    fd, temp = tempfile.mkstemp(dir=str(path.parent), prefix='.meta-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o644)
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def record(mod, published_id):
    """Write or update ``publishedid = N;`` in the mod's meta.cpp; create meta.cpp if absent."""
    published_id = _check_id(published_id)
    mod = Path(mod)
    if mod.is_symlink() or not mod.is_dir():
        raise PublishError('%s is not a real directory' % mod)
    meta = mod / 'meta.cpp'
    if meta.is_symlink():
        raise PublishError('%s is a symlink; refusing to write through it' % meta)
    if not meta.exists():
        data = 'protocol = 1;\npublishedid = %d;\nname = "%s";\n' % (published_id, TITLE)
    else:
        if not meta.is_file():
            raise PublishError('%s is not a regular file' % meta)
        try:
            text = meta.read_bytes().decode('utf-8')
        except UnicodeDecodeError:
            raise PublishError('meta.cpp is not UTF-8 text')
        nl = '\r\n' if '\r\n' in text else '\n'
        found = list(PUBLISHED.finditer(text))
        if len(found) > 1:
            raise PublishError('meta.cpp has more than one publishedid line')
        line = 'publishedid = %d;' % published_id
        if found:
            data = text[:found[0].start()] + line + text[found[0].end():]
        else:
            proto = PROTOCOL.search(text)
            if proto:
                at = proto.end()
                head = text[:at]
                if not head.endswith(('\n', '\r')):
                    head += nl
                data = head + line + nl + text[at:]
            else:
                data = line + nl + text
    _atomic_write(meta, data.encode('utf-8'))
    return meta


# ---------------------------------------------------------------- prepare
def _clean_text(value, what):
    text = re.sub(r'\s*[\r\n]+\s*', ' ', value).replace('"', "'").strip()
    if not text:
        raise PublishError('%s is empty' % what)
    if len(text) > MAX_NOTE:
        raise PublishError('%s is longer than %d characters' % (what, MAX_NOTE))
    return text


def _vdf_path(path, style):
    text = to_windows(path) if style == 'windows' else str(path)
    if '"' in text or '\n' in text or '\r' in text:
        raise PublishError('path %r contains a character a VDF cannot hold' % text)
    return text


def _check_preview(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise PublishError('preview %s is not a regular file' % path)
    size = path.stat().st_size
    if size > MAX_PREVIEW_BYTES:
        raise PublishError('preview %s is too large (%d bytes; limit %d)' % (path, size, MAX_PREVIEW_BYTES))
    if path.read_bytes()[:8] != PNG_MAGIC:
        raise PublishError('preview %s is not a PNG file' % path)
    return path


def _prepare_out(out, mod):
    real_out, real_mod = Path(os.path.realpath(out)), Path(os.path.realpath(mod))
    if real_out == real_mod or real_mod in real_out.parents or real_out in real_mod.parents:
        raise PublishError('the output folder %s must not overlap the mod folder %s' % (out, mod))
    out = Path(out)
    if out.is_symlink():
        raise PublishError('%s is a symlink' % out)
    if out.exists():
        if not out.is_dir():
            raise PublishError('%s is not a directory' % out)
        foreign = sorted(p.name for p in out.iterdir() if p.name not in OUR_OUTPUTS)
        if foreign:
            raise PublishError('%s contains files this tool did not write (%s); use an empty folder'
                               % (out, ', '.join(foreign)))
    return out


def _stage(mod, files, content):
    if content.exists():
        shutil.rmtree(content)
    for rel in files:
        target = content / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(mod) / rel, target)
        os.chmod(target, 0o644)


def _quote(value, style):
    if style == 'windows':
        return '"%s"' % value if re.search(r'\s', value) else value
    return shlex.quote(value)


def prepare(mod, out, published_id=None, preview=None, change_note=None, visibility='unlisted',
            path_style='native'):
    """Validate, stage and write the VDF. Returns a dict with the vdf path, content folder and command."""
    if visibility != 'unlisted':
        raise PublishError('only the "unlisted" visibility is supported (got %r); public, friends-only and '
                           'private are not accepted' % visibility)
    mod = Path(os.path.abspath(mod))
    info = validate_content(mod)
    recorded = _published_id(mod)
    if published_id is not None:
        _check_id(published_id)
    if published_id is not None and recorded is not None and published_id != recorded:
        raise PublishError('--published-id %d conflicts with publishedid = %d in meta.cpp; fix one of them'
                           % (published_id, recorded))
    item_id = published_id if published_id is not None else (recorded or 0)
    note = _clean_text(change_note, 'change note') if change_note else \
        'Hollow Country build %s' % info['pbo_sha256'][:12]
    if preview is not None:
        preview = _check_preview(preview)
    out = Path(os.path.abspath(out))
    _prepare_out(out, mod)
    out.mkdir(parents=True, exist_ok=True)
    content = out / 'content'
    _stage(mod, info['files'], content)
    validate_content(content)
    fields = [('appid', APP_ID), ('contentfolder', _vdf_path(content, path_style))]
    if preview is not None:
        staged_preview = out / 'preview.png'
        shutil.copyfile(preview, staged_preview)
        fields.append(('previewfile', _vdf_path(staged_preview, path_style)))
    fields += [('visibility', VISIBILITY_UNLISTED), ('title', TITLE), ('description', DESCRIPTION),
               ('changenote', note), ('publishedfileid', str(item_id))]
    text = '"workshopitem"\n{\n' + ''.join('\t"%s"\t\t"%s"\n' % pair for pair in fields) + '}\n'
    vdf = out / VDF_NAME
    vdf.write_text(text, encoding='utf-8')
    shown = _vdf_path(vdf, path_style)
    command = 'steamcmd +login %s +workshop_build_item %s +quit' % (COMMAND_USER, _quote(shown, path_style))
    return {'vdf': vdf, 'content': content, 'command': command, 'published_id': item_id,
            'files': info['files'], 'pbo_sha256': info['pbo_sha256'], 'has_preview': preview is not None,
            'change_note': note}


# ---------------------------------------------------------------- command line
def _positive(value):
    if not re.fullmatch(r'[1-9][0-9]*', value):
        raise argparse.ArgumentTypeError('%r is not a positive integer' % value)
    return int(value)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0], allow_abbrev=False)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare', help='validate, stage and write the steamcmd VDF', allow_abbrev=False)
    p.add_argument('--mod', required=True, help='signed @HollowCountry folder')
    p.add_argument('--out', required=True, help='output folder for the staged content and the VDF')
    p.add_argument('--published-id', type=_positive, help='Workshop id of an existing item (omit for the first upload)')
    p.add_argument('--preview', help='preview PNG (at most 1 MiB)')
    p.add_argument('--change-note', help='change note shown on the Workshop page')
    p.add_argument('--visibility', default='unlisted', help='only "unlisted" is accepted')
    p.add_argument('--path-style', choices=('native', 'windows'), default='native',
                   help='write Windows paths (converts /mnt/<drive>/...) when steamcmd runs on Windows')
    r = sub.add_parser('record', help='write publishedid into the mod meta.cpp', allow_abbrev=False)
    r.add_argument('--mod', required=True)
    r.add_argument('--published-id', type=_positive, required=True)
    return parser


def main(argv=None, out=None):
    out = out or sys.stdout
    args = build_parser().parse_args(argv)

    def say(text=''):
        print(text, file=out)

    try:
        if args.command == 'record':
            meta = record(args.mod, args.published_id)
            say('wrote publishedid = %d; to %s' % (args.published_id, meta))
            say('Rebuild and re-sign only if the pbo changed; meta.cpp is not part of the signature.')
            return 0
        result = prepare(args.mod, args.out, published_id=args.published_id, preview=args.preview,
                         change_note=args.change_note, visibility=args.visibility, path_style=args.path_style)
    except PublishError as exc:
        print('error: %s' % exc, file=sys.stderr)
        return 1
    except OSError as exc:
        print('error: %s' % exc, file=sys.stderr)
        return 1
    say('Content folder (staged copy, allowlisted files only): %s' % result['content'])
    for rel in result['files']:
        say('  %s' % rel)
    say('pbo sha256: %s' % result['pbo_sha256'])
    say('VDF: %s' % result['vdf'])
    say('Visibility: Unlisted (Steam value %s): hidden from Workshop search, visible to anyone with the link.'
        % VISIBILITY_UNLISTED)
    say('Item: %s' % ('new item (publishedfileid 0)' if not result['published_id']
                      else 'update of %d' % result['published_id']))
    if not result['has_preview']:
        say('Warning: no preview image given (--preview); Steam may require one for the first upload.')
    say()
    say('Run this yourself; enter your own Steam login name. steamcmd asks for the password and the')
    say('Steam Guard code itself. This tool never sees or stores them:')
    say('  %s' % result['command'])
    say()
    say('After the first upload, record the new Workshop id: workshop_publish.py record --mod <dir> '
        '--published-id <id>')
    return 0


if __name__ == '__main__':
    sys.exit(main())
