"""Deterministic authored DayZ layout/script checks (standard library only).

Class allowlist: installed 1.30.164289 EnWidgets.c/WidgetType and vanilla
GUI PBO layouts, inspected locally 2026-11-18. No vanilla content is distributed.
Literal script loads/lookups are checked per source file; a borrowed root with
no matching local load is reported for human review, never silently satisfied
by an unrelated layout. Dynamic names are outside this static check's scope.
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


def lint_tree(root):
    """Check every authored layout, load and literal lookup under root/mods."""
    root = Path(root)
    findings, parsed = [], {}
    for path in sorted((root / 'mods').glob('*/gui/layouts/**/*.layout')):
        names, paths, errors = _parse(path.read_text(encoding='utf-8-sig'))
        parsed[path] = (names, paths)
        findings.extend(f'{path.relative_to(root)}: {error}' for error in errors)
    for script in sorted((root / 'mods').glob('*/scripts/**/*.c')):
        text = uncomment(script.read_text(encoding='utf-8-sig'))
        label = script.relative_to(root).as_posix()
        loads = re.findall(r'"([^"\n]+\.layout)"', text)
        loaded_names, loaded_paths = set(), set()
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
        for kind, name in re.findall(r'\b(FindAnyWidget|FindWidget)\s*\(\s*"([^"]+)"\s*\)', text):
            if kind == 'FindAnyWidget' and '.' not in name:
                exists = name in loaded_names
            else:
                exists = any(p == name or p.endswith('.' + name) for p in loaded_paths)
            if not exists:
                findings.append(f'{label}: lookup {name!r} has no match in layouts loaded by this script (borrowed roots need review)')
    return findings


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
