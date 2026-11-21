"""Deterministic authored DayZ layout/script checks (standard library only).

Class allowlist: installed 1.30.164289 EnWidgets.c/WidgetType and vanilla
GUI PBO layouts, inspected locally 2026-11-18. No vanilla content is distributed.
Literal script loads/lookups are checked per source file and reviewed borrowed
root declarations, never silently satisfied by an unrelated layout. Dynamic
names are outside this static check's scope.
"""
import argparse
from pathlib import Path
import re
import sys

if __package__ in (None, ''):
    # Support both python -m tools.validate.layout_lint and the script path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.package.pbo import original_addon_name, PREFIXES
from tools.validate import texture_index

WIDGET_CLASSES = frozenset('''Button Canvas CheckBox EditBox Embeded Frame
GridSpacer Html Image ItemPreview Map MultilineEditBox MultilineText Panel
PasswordEditBox PlayerPreview ProgressBar RichText Scroll ServerBrowser Slider
SmartPanel Spacer TextListbox Text ThreeStateCheckbox Video Window WrapSpacer
XComboBox RenderTarget RTTexture SimpleProgressBar BaseListbox SimpleListbox
Workspace'''.split())
WIDGET_CLASSES = frozenset(name + 'WidgetClass' for name in WIDGET_CLASSES)
LEX = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/|[{}]|[^\s{}]+')
SCRIPT_LEX = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/')

# Reviewed root handoffs. Each root is checked separately, including its loader;
# an unrelated layout cannot satisfy a consumer's lookup. Optional names describe
# the smaller Expansion admin-only root, whose absent fields are null-guarded.
_GROUP_MENU = 'mods/HollowCountry/scripts/5_Mission/Groups/HCGroupMapMenu.c'
_GROUP_LAYOUT = 'HollowCountry/gui/layouts/hc_group_map.layout'
BORROWED_ROOTS = {
    'mods/HollowCountry/scripts/5_Mission/Admin/HCAdminWorldClient.c': (
        (_GROUP_LAYOUT, _GROUP_MENU, (), 'Init passes layoutRoot to HCAdminWorldClient.Open.'),
    ),
    'mods/HollowCountry/scripts/5_Mission/Groups/HCGroupMapLayers.c': (
        (_GROUP_LAYOUT, _GROUP_MENU, (), 'Init passes layoutRoot to mHCLayers.Init.'),
    ),
}

# Reviewed lookups into a dependency's installed layout (not in this repo), per consumer script.
EXTERNAL_LOOKUPS = {
    'mods/HollowCountryExpansionAI/scripts/5_Mission/HCXAdminMapLayers.c': {
        'MarkerListPanelContent': 'Expansion Navigation layouts/expansion_map_markerlist.layout; '
                                  'the admin layer section is parented under it and null-guarded.',
    },
}


def uncomment(text):
    return SCRIPT_LEX.sub(lambda m: re.sub(r'[^\n]', ' ', m[0]) if m[0].startswith('/') else m[0], text)


def _parse(text):
    tokens = [t for t in LEX.findall(text) if not t.startswith(('//', '/*'))]
    names, paths, findings, declarations = set(), set(), [], {}
    for index, token in enumerate(tokens):
        if re.fullmatch(r'\w+WidgetClass', token):
            if token not in WIDGET_CLASSES:
                findings.append('unknown widget class: ' + token)
            if index + 2 >= len(tokens) or tokens[index + 2] != '{':
                findings.append('malformed widget declaration: ' + token)
                continue
            name = tokens[index + 1].strip('"')
            if name in names:
                findings.append('duplicate widget name: ' + name)
            names.add(name)
            declarations[index + 2] = name
    stack = []
    for index, token in enumerate(tokens):
        if token == '{':
            name = declarations.get(index)
            if name:
                paths.add('.'.join([p for p in stack if p] + [name]))
            stack.append(name)
        elif token == '}':
            if not stack:
                findings.append('brace balance: unexpected closing brace')
            else:
                stack.pop()
    if stack:
        findings.append('brace balance: unclosed braces=' + str(len(stack)))
    return names, paths, findings


def lint_layout(text):
    """Return declared names and diagnostics for one layout's text."""
    names, _, findings = _parse(text)
    return names, findings


def lint_tree(root, borrowed_roots=None, texture_names=None, warnings=None):
    """Check every authored layout, load and literal lookup under root/mods."""
    root = Path(root)
    if borrowed_roots is None:
        borrowed_roots = BORROWED_ROOTS
    findings, parsed = [], {}
    for path in sorted((root / 'mods').glob('*/gui/**/*.layout')):
        names, paths, errors = _parse(path.read_text(encoding='utf-8-sig'))
        parsed[path] = (names, paths)
        findings.extend(f'{path.relative_to(root)}: {error}' for error in errors)
    for script in sorted((root / 'mods').glob('*/scripts/**/*.c')):
        text = uncomment(script.read_text(encoding='utf-8-sig'))
        label = script.relative_to(root).as_posix()
        loads = re.findall(r'"([^"\n]+\.layout)"', text)
        local_loads = set(loads)
        borrowed = borrowed_roots.get(label, ())
        for layout, loader, optional, reason in borrowed:
            loader_path = root / loader
            if not reason.strip() or not loader_path.is_file():
                findings.append(f'{label}: invalid borrowed-root declaration: {layout}')
                continue
            loader_loads = re.findall(r'"([^"\n]+\.layout)"', uncomment(loader_path.read_text(encoding='utf-8-sig')))
            if layout not in loader_loads:
                findings.append(f'{label}: borrowed-root loader {loader} does not load {layout}')
            loads.append(layout)
        loaded_names, loaded_paths = set(), set()
        local_names, local_paths = set(), set()
        for load in sorted(set(loads)):
            canonical = load.replace('\\\\', '/').replace('\\', '/').lstrip('/')
            parts = canonical.split('/', 1)
            if len(parts) != 2:
                findings.append(f'{label}: missing layout: {load}')
                continue
            prefix, relative = parts
            path = root / 'mods' / prefix / relative
            if not path.is_file():
                findings.append(f'{label}: missing layout: {load}')
            if prefix not in PREFIXES or not original_addon_name(relative):
                findings.append(f'{label}: layout not shipped by PBO packer: {load}')
            if path in parsed:
                names, paths = parsed[path]
                loaded_names.update(names)
                loaded_paths.update(paths)
                if load in local_loads:
                    local_names.update(names)
                    local_paths.update(paths)
        external = EXTERNAL_LOOKUPS.get(label, {})
        for kind, name in re.findall(r'\b(FindAnyWidget|FindWidget)\s*\(\s*"([^"]+)"\s*\)', text):
            if name in external:
                continue
            for layout, loader, optional, reason in borrowed:
                names, paths = parsed.get(root / 'mods' / layout, (set(), set()))
                if name in optional:
                    continue
                # A consumer can also create its own child widgets (map icons).
                if not _lookup_exists(kind, name, names | local_names, paths | local_paths):
                    findings.append(f'{label}: lookup {name!r} has no match in borrowed root {layout} ({reason})')
            exists = _lookup_exists(kind, name, loaded_names, loaded_paths)
            if not exists:
                findings.append(f'{label}: lookup {name!r} has no match in layouts loaded by this script (borrowed roots need review)')
    texture_findings, texture_warnings = lint_textures(root, texture_names)
    findings.extend(texture_findings)
    if warnings is not None:
        warnings.extend(texture_warnings)
    return findings


def _lookup_exists(kind, name, names, paths):
    if kind == 'FindAnyWidget' and '.' not in name:
        return name in names
    return any(p == name or p.endswith('.' + name) for p in paths)


# Formats evidenced in native 1.30 scripts: RemoteDetonator (co), ItemBase
# (CO), Hologram (ca). Other generators are explicitly unverified, not accepted.
_NUMBER = r"[+-]?\d+(?:\.\d+)?"
_COLOR = re.compile(r"#\((rgb|argb|ai|a|i),([1-9]\d*),([1-9]\d*),([1-9]\d*)\)color\("
                    + ','.join([f'({_NUMBER})'] * 4) + r"(?:,([a-z]+))?\)", re.I)
_STRING = re.compile(r'"((?:\\.|[^"\\])*)"')
_CALL = re.compile(r'\b(LoadImageFile|SetImage|LoadMaskTexture|SetTexture|ImageWidget)\s*\(')
_ASSET = re.compile(r"\.(paa|edds|tga|png|jpg|jpeg|bmp)$", re.I)


def _call_arguments(text, start):
    """Split balanced calls without splitting commas inside strings/nested calls."""
    depth, begin, args = 1, start, []
    tokens = re.compile(r'"(?:\\.|[^"\\])*"|[(),]')
    for token in tokens.finditer(text, start):
        if token[0] == '(':
            depth += 1
        elif token[0] == ')':
            depth -= 1
            if depth == 0:
                return args + [text[begin:token.start()].strip()]
        elif token[0] == ',' and depth == 1:
            args.append(text[begin:token.start()].strip())
            begin = token.end()
    return args


def texture_references(text, suffix):
    """Yield (offset, value, dynamic) from authored texture contexts.

    Script asset literals include constants and arrays as well as direct arguments;
    this catches table-fed paths without pretending to perform data-flow analysis.
    """
    text = uncomment(text)
    seen = set()
    if suffix == '.c':
        code = _STRING.sub(lambda m: re.sub(r'[^\n]', ' ', m[0]), text)
        for call in _CALL.finditer(code):
            args = _call_arguments(text, call.end())
            slot = 1 if call[1] in ('LoadImageFile', 'SetTexture') else 0
            if len(args) <= slot:
                continue
            value = args[slot]
            literal = _STRING.fullmatch(value)
            if literal:
                seen.add((call.start(), literal[1], False))
            elif value and not re.fullmatch(r'[+-]?\d+', value):
                seen.add((call.start(), value, True))
        # Runtime marker tables are unsafe to assume resolvable even when passed
        # through a helper such as Pin/AddUserMark instead of an ImageWidget call.
        for table in re.finditer(r'\bMapMarkerTypes\s*\.\s*\w+\s*\(', code):
            seen.add((table.start(), 'MapMarkerTypes', True))
        for literal in _STRING.finditer(text):
            if _ASSET.search(literal[1]) or literal[1].startswith(('#(', '#argb', 'image:', 'set:')):
                seen.add((literal.start(), literal[1], False))
    elif suffix in ('.layout', '.imageset'):
        fields = re.compile(r'\b(?:image\d*|texture\w*|masktexture|file|path)\s*(?:=\s*)?"((?:\\.|[^"\\])*)"', re.I)
        for field in fields.finditer(text):
            seen.add((field.start(), field[1], False))
    else:  # config.cpp: scalar and array texture fields, including hidden selections
        fields = re.compile(r'\b(?:\w*texture\w*|icon|picture)\s*(?:\[\s*\])?\s*\+?=\s*(\{[^;]*?\}|"(?:\\.|[^"\\])*")', re.I)
        for field in fields.finditer(text):
            for literal in _STRING.finditer(field[1]):
                seen.add((field.start(), literal[1], False))
    # Deduplicate literals seen both in a call and the general constant scan.
    emitted = set()
    for offset, value, dynamic in sorted(seen):
        line = text.count('\n', 0, offset) + 1
        key = (line, value, dynamic)
        if key not in emitted:
            emitted.add(key)
            yield line, value, dynamic


def diagnostic_value(value):
    """Redact private home prefixes, including paths embedded in expressions."""
    value = re.sub(r'\\+', '/', value)
    home = Path.home().as_posix().rstrip('/')
    if home:
        value = re.sub(re.escape(home) + r'(?=/|[\s"\']|$)', '<home>', value, flags=re.I)
    return re.sub(r'(?:[a-z]:)?/(?:home|users)/[^/"\'\r\n]+',
                  '<home>', value, flags=re.I)


def lint_textures(root, texture_names=None):
    root = Path(root)
    local = texture_index.local_files(root)
    installed = None if texture_names is None else {texture_index.canonical(n) for n in texture_names}
    findings, warnings = [], []
    files = set((root / 'mods').glob('*/gui/**/*.layout'))
    files.update((root / 'mods').glob('*/gui/**/*.imageset'))
    files.update((root / 'mods').glob('*/scripts/**/*.c'))
    files.update((root / 'mods').rglob('config.cpp'))
    local_prefixes = {texture_index.canonical(texture_index.addon_prefix(p)) for p in
                      (root / 'mods').iterdir() if p.is_dir()} if (root / 'mods').is_dir() else set()
    for path in sorted(files):
        text = path.read_text(encoding='utf-8-sig')
        for line, value, dynamic in texture_references(text, path.suffix):
            label = f'{path.relative_to(root).as_posix()}:{line}'
            display = diagnostic_value(value)
            if dynamic:
                warnings.append(f'{label}: runtime texture expression needs native review: {display}')
                continue
            if not value:  # native calls use an empty string to clear textures
                continue
            if value.startswith('#'):
                if '%' in value:
                    warnings.append(f'{label}: procedural texture template needs runtime review: {display}')
                elif _COLOR.fullmatch(value):
                    dimensions = [int(v) for v in _COLOR.fullmatch(value).groups()[1:3]]
                    if any(v & (v - 1) for v in dimensions):
                        findings.append(f'{label}: procedural dimensions must be powers of two: {display}')
                    elif (_COLOR.fullmatch(value).group(1).lower() != 'argb'
                          or (_COLOR.fullmatch(value).group(9) or '').lower() not in ('co', 'ca')):
                        warnings.append(f'{label}: documented procedural form needs DayZ native review: {display}')
                elif 'color' in value.casefold():
                    findings.append(f'{label}: malformed procedural color texture: {display}')
                else:
                    warnings.append(f'{label}: unverified procedural texture grammar: {display}')
                continue
            if value.startswith(('image:', 'set:')):
                warnings.append(f'{label}: imageset symbolic reference needs native review: {display}')
                continue
            canonical = texture_index.canonical(value)
            if Path(canonical).suffix not in ('.paa', '.edds'):
                findings.append(f'{label}: wrong texture extension (expected .paa/.edds): {display}')
                continue
            if canonical in local:
                if not local[canonical]:
                    findings.append(f'{label}: texture not shipped by PBO packer: {display}')
            elif any(canonical == prefix or canonical.startswith(prefix + '/') for prefix in local_prefixes):
                findings.append(f'{label}: missing authored texture: {display}')
            elif installed is not None and canonical not in installed:
                findings.append(f'{label}: missing indexed texture: {display}')
    return findings, warnings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--texture-index', type=Path, default=texture_index.DEFAULT_CACHE)
    parser.add_argument('--no-texture-index', action='store_true', help='explicit offline run')
    args = parser.parse_args(argv)
    names = None
    if not args.no_texture_index:
        try:
            names = texture_index.load_index(args.texture_index)
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    if names is None:
        print('layout_lint: NOTICE installed texture index unavailable; skipping unresolved vanilla file checks '
              '(build with python3 -B -m tools.validate.texture_index)')
    else:
        print('layout_lint: installed index loaded; rebuild after DayZ updates (cache freshness not checked)')
    warnings = []
    findings = lint_tree(args.root, texture_names=names, warnings=warnings)
    for warning in warnings:
        print('WARNING ' + warning)
    for finding in findings:
        print(finding)
    print(f'layout_lint: layouts={len(list((args.root / "mods").glob("*/gui/**/*.layout")))} findings={len(findings)}')
    return int(bool(findings))


if __name__ == '__main__':
    raise SystemExit(main())
