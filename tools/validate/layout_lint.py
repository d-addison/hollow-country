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
_EXPANSION_MAP = 'mods/HollowCountryExpansionAI/scripts/5_Mission/HCXAdminExpansionMap.c'
_GROUP_LAYOUT = 'HollowCountry/gui/layouts/hc_group_map.layout'
_ADMIN_LAYOUT = 'HollowCountry/gui/layouts/hc_admin_world_overlay.layout'
BORROWED_ROOTS = {
    'mods/HollowCountry/scripts/5_Mission/Admin/HCAdminWorldClient.c': (
        (_GROUP_LAYOUT, _GROUP_MENU, (), 'Init passes layoutRoot to HCAdminWorldClient.Open.'),
        (_ADMIN_LAYOUT, _EXPANSION_MAP, (), 'OnShow passes mHCXAdminOverlay to HCAdminWorldClient.Open.'),
    ),
    'mods/HollowCountry/scripts/5_Mission/Groups/HCGroupMapLayers.c': (
        (_GROUP_LAYOUT, _GROUP_MENU, (), 'Init passes layoutRoot to mHCLayers.Init.'),
        (_ADMIN_LAYOUT, _EXPANSION_MAP, ('HCGrid', 'HCNavigation', 'HCKnownEvents'),
         'Init passes mHCXAdminOverlay to mHCXAdminLayers.Init; DrawAdminOverlay uses pins only. '
         'Grid, navigation and events fields are optional and null-guarded.'),
    ),
}


def uncomment(text):
    return SCRIPT_LEX.sub(lambda m: ' ' if m[0].startswith(('/', '/*')) else m[0], text)


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


def lint_tree(root, borrowed_roots=None):
    """Check every authored layout, load and literal lookup under root/mods."""
    root = Path(root)
    if borrowed_roots is None:
        borrowed_roots = BORROWED_ROOTS
    findings, parsed = [], {}
    for path in sorted((root / 'mods').glob('*/gui/layouts/**/*.layout')):
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
        for kind, name in re.findall(r'\b(FindAnyWidget|FindWidget)\s*\(\s*"([^"]+)"\s*\)', text):
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
    return findings


def _lookup_exists(kind, name, names, paths):
    if kind == 'FindAnyWidget' and '.' not in name:
        return name in names
    return any(p == name or p.endswith('.' + name) for p in paths)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    findings = lint_tree(args.root)
    for finding in findings:
        print(finding)
    print(f'layout_lint: layouts={len(list((args.root / "mods").glob("*/gui/layouts/**/*.layout")))} findings={len(findings)}')
    return int(bool(findings))


if __name__ == '__main__':
    raise SystemExit(main())
