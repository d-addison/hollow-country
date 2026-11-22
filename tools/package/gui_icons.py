"""Render original RGBA map icons and convert them with installed ImageToPAA.

No third-party art, Pillow, or Windows dependency is needed for render/check.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib

from tools.setup import winproc

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path('art/gui-icons')
OUTPUT = Path('mods/HollowCountry/gui/icons/map')
MANIFEST = SOURCE / 'manifest.json'
DEFAULT_TOOL = Path('/mnt/d/SteamLibrary/steamapps/common/DayZ Tools/Bin/ImageToPAA/ImageToPAA.exe')
# White faces support runtime tinting; dark outlines preserve contrast on light maps.
ICONS = {
    'ai_group': ('triangle', 'dot'), 'police': ('diamond', 'cross'),
    'event': ('triangle', 'bar'), 'loot': ('square', 'cross'),
    'wreck': ('cross', 'dot'), 'vehicle': ('square', 'bar'),
    'shelter': ('triangle', 'door'), 'group_member': ('circle', 'dot'),
    'player': ('diamond', 'dot'), 'poi': ('circle', 'cross'),
}
SIZE = 64


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _inside(shape, x, y, radius):
    if shape == 'circle':
        return x*x + y*y <= radius*radius
    if shape == 'diamond':
        return abs(x) + abs(y) <= radius
    if shape == 'square':
        return max(abs(x), abs(y)) <= radius * .79
    if shape == 'triangle':
        return -radius <= y <= radius * .8 and abs(x) <= (y + radius) * .53
    return (abs(x) <= radius * .28 and abs(y) <= radius or
            abs(y) <= radius * .28 and abs(x) <= radius)


def render_png(name):
    """Fixed 4x coverage sampling, PNG RGBA8, no timestamps or machine metadata."""
    shape, detail = ICONS[name]
    pixels = bytearray()
    for py in range(SIZE):
        pixels.append(0)  # PNG filter: none
        for px in range(SIZE):
            rgb = alpha = 0
            for sy in range(4):
                for sx in range(4):
                    x, y = px + (sx+.5)/4 - 32, py + (sy+.5)/4 - 32
                    if not _inside(shape, x, y, 26):
                        continue
                    ink = not _inside(shape, x, y, 21)
                    if detail == 'dot':
                        ink |= x*x + y*y <= 4.5**2
                    elif detail == 'cross':
                        ink |= abs(x) <= 2 and abs(y) <= 8 or abs(y) <= 2 and abs(x) <= 8
                    elif detail == 'bar':
                        ink |= abs(x) <= 8 and abs(y) <= 2.5
                    else:
                        ink |= abs(x) <= 4 and 0 <= y <= 13
                    rgb += 24 if ink else 255
                    alpha += 1
            value = round(rgb/alpha) if alpha else 0
            pixels.extend((value, value, value, round(255*alpha/16)))
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>2I5B', SIZE, SIZE, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(pixels), 9)) + chunk(b'IEND', b''))


def render(root):
    directory = root / SOURCE
    directory.mkdir(parents=True, exist_ok=True)
    for name in ICONS:
        (directory / (name + '.png')).write_bytes(render_png(name))


def windows_path(path):
    if os.name == 'nt':
        return str(path.resolve())
    try:
        return subprocess.run(['wslpath', '-w', str(path.resolve())], check=True,
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError('WSL path conversion unavailable') from exc


def convert(tool, source, destination):
    """Observed CLI: ImageToPAA <source> <destination>; capture private native output."""
    args = [windows_path(p) for p in (tool, source, destination)]
    if os.name == 'nt':
        result = subprocess.run(args, capture_output=True, timeout=60)
        code = result.returncode
    else:
        quote = lambda s: "'" + s.replace("'", "''") + "'"
        script = '& ' + ' '.join(map(quote, args)) + ' 2>&1 | Out-Null; Write-Output "HC_ICON_EXIT=$LASTEXITCODE"'
        result = winproc.run('powershell', [script], attempts=1, timeout=60)
        code = 0 if result.returncode == 0 and 'HC_ICON_EXIT=0' in result.stdout.splitlines() else 1
    if code or not destination.is_file() or destination.stat().st_size < 16:
        raise ValueError('ImageToPAA conversion failed; no provenance recorded')


def windows_sees(directory):
    """A sandboxed WSL process can have a private /tmp or mount namespace that the
    Windows converter cannot reach; that is missing interop, not a conversion fault."""
    if os.name == 'nt':
        return True
    quote = lambda s: "'" + s.replace("'", "''") + "'"
    result = winproc.run('powershell', ['if (Test-Path -LiteralPath ' + quote(windows_path(directory)) + ') { "HC_SEEN=1" }'],
                         attempts=1, timeout=30)
    return result.returncode == 0 and 'HC_SEEN=1' in result.stdout.splitlines()


def build(root, tool=DEFAULT_TOOL, converter=convert):
    render(root)  # Keep useful sources even when Windows conversion is unavailable.
    if not tool.is_file():
        raise ValueError('ImageToPAA executable missing; sources rendered, conversion pending')
    # Convert all ten before replacing any published output or its manifest.
    output = root / OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.gui-icons-', dir=root / SOURCE) as tmp:
        staged = Path(tmp)
        (staged / '.visible').write_bytes(b'1')
        if converter is convert and not windows_sees(staged / '.visible'):
            raise winproc.InteropError('Windows cannot reach the WSL staging directory')
        (staged / '.visible').unlink()
        entries = {}
        for name in ICONS:
            source = root / SOURCE / (name + '.png')
            target = staged / (name + '.paa')
            converter(tool, source, target)
            data = target.read_bytes()
            if len(data) < 16:
                raise ValueError('ImageToPAA output is empty or truncated')
            entries[name] = {'source': (SOURCE / source.name).as_posix(), 'source_sha256': sha(source.read_bytes()),
                             'paa': (OUTPUT / target.name).as_posix(), 'paa_sha256': sha(data)}
        manifest = {'schema': 1, 'size': SIZE, 'generator': 'tools.package.gui_icons',
                    'converter': 'ImageToPAA', 'converter_sha256': sha(tool.read_bytes()), 'icons': entries}
        for name in ICONS:
            (output / (name + '.paa')).write_bytes((staged / (name + '.paa')).read_bytes())
        (root / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    check(root)


def check(root):
    """Require the exact category inventory, generated sources and recorded hashes."""
    try:
        manifest = json.loads((root / MANIFEST).read_text())
        if manifest['schema'] != 1 or manifest['size'] != SIZE or set(manifest['icons']) != set(ICONS):
            raise ValueError('manifest category/schema mismatch')
        for directory, suffix in ((SOURCE, '.png'), (OUTPUT, '.paa')):
            if {p.stem for p in (root / directory).glob('*' + suffix)} != set(ICONS):
                raise ValueError('source/PAA inventory mismatch')
        for name in ICONS:
            row = manifest['icons'][name]
            for key, rel in (('source', SOURCE / (name + '.png')), ('paa', OUTPUT / (name + '.paa'))):
                path = root / rel
                if row[key] != rel.as_posix() or path.is_symlink() or sha(path.read_bytes()) != row[key + '_sha256']:
                    raise ValueError('icon provenance mismatch: ' + name)
            if (root / SOURCE / (name + '.png')).read_bytes() != render_png(name):
                raise ValueError('source differs from procedural recipe: ' + name)
    except (KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        raise ValueError('icon manifest/files missing or invalid; run build') from exc
    return len(ICONS)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'check', 'render'])
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--image-to-paa', type=Path, default=DEFAULT_TOOL)
    args = parser.parse_args(argv)
    try:
        if args.command == 'build':
            build(args.root, args.image_to_paa)
        elif args.command == 'render':
            render(args.root)
        else:
            check(args.root)
    except (ValueError, OSError, subprocess.SubprocessError, winproc.InteropError):
        print('GUI icons failed: files/converter unavailable or provenance mismatch; see docs/tools/GUI_ICONS.md')
        return 1
    print('GUI icons: ' + args.command + ' passed (10 categories)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
