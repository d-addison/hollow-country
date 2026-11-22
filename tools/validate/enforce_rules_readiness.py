"""Wave 7 HC-S006/#175: pure, offline source checks; no native readiness proof.

The lead registers the two rule adapters in enforce_lint. Pure entry points take
source text only and share the established comment/string-aware source model.
"""
from dataclasses import dataclass
from pathlib import Path
import re

from tools.validate import enforce_source as es

# `Type` is left out on purpose: vanilla 1.30 declares `string Type;` JSON members
# (UndergroundAreaLoader.c, JsonDataContaminatedArea.c), so it is not the `Queue` trap.
ENGINE_TYPE_NAMES = frozenset({'Queue', 'Param', 'Class', 'Widget', 'Object', 'Man',
                               'Shape', 'Timer', 'Math', 'Managed'})
RULES = {
    'HC-S006': 'registered HCModule subclass has no authored GetName override',
    'HC-E009': 'variable named after a pinned engine type (native compile refusal)',
}


@dataclass(frozen=True)
class SourceFinding:
    rule: str
    path: str
    offset: int
    symbol: str
    message: str


def module_readiness(files):
    """Return missing-name findings for {path: source text or parsed Source}, without IO.

    A parsed Source (keyed by its own rel path) is reused as is; text goes through the shared parse cache.
    Follow authored inheritance and modded links, excluding HCModule's default
    unnamed implementation. Only registrations in HCServer/HCModuleRegistry count.
    """
    sources = [text if isinstance(text, es.Source) else es.parse(Path(path), text)
               for path, text in sorted(files.items())]
    links, registrations = {}, set()
    for source in sources:
        for definition in source.classes:
            links.setdefault(definition.name, []).append(definition)
            if definition.name in ('HCServer', 'HCModuleRegistry'):
                body = source.code[definition.body_start:definition.body_end]
                registrations.update(re.findall(r'\bRegister\s*\(\s*new\s+(\w+)', body))
    findings = []
    for source in sources:
        for definition in source.classes:
            if definition.modded or definition.name not in registrations:
                continue
            current, seen, named = definition.name, set(), False
            while current and current != 'HCModule' and current not in seen:
                seen.add(current)
                definitions = links.get(current, ())
                named |= any(method.name == 'GetName' for link in definitions for method in link.methods)
                current = next((link.base for link in definitions if not link.modded), '')
            if current == 'HCModule' and not named:
                findings.append(SourceFinding('HC-S006', source.rel, definition.offset,
                                              definition.name, RULES['HC-S006']))
    return findings


# A declaration's type must start at a statement/parameter boundary. Do not
# mistake casts, member accesses, method names or return expressions for fields.
_DECLARATION = re.compile(
    r'(?:^|[;{}(,:])\s*(?:(?:ref|autoptr|static|protected|private|const|out|inout)\s+)*'
    r'(?P<typ>[A-Za-z_]\w*(?:\s*<[^;(){}=]+>)?)\s+'
    r'(?P<name>[A-Za-z_]\w*)\s*(?=[=;\[,:)])', re.M)
_NOT_TYPES = frozenset({'return', 'new', 'delete', 'else', 'case', 'throw'})


def engine_type_names(text, path='<source>'):
    """Find pinned type names used as fields/locals (including JSON DTO fields).

    Parameters and foreach bindings count too: they have the same native trap.
    Type references and comments/strings do not count. Exact case is significant.
    ``text`` may also be an already parsed Source (path is then ignored).
    """
    source = text if isinstance(text, es.Source) else es.parse(Path(path), text)
    findings, seen = [], set()
    for match in _DECLARATION.finditer(source.code):
        if match['typ'] in _NOT_TYPES:
            continue
        declarations = [(match['name'], match.start('name'))]
        # Scalar comma declarations, including initialized first variables.
        # Shared split_top ignores commas inside calls/array initializers.
        cursor = match.end('name')
        tail = source.code[cursor:source.code.find(';', cursor)]
        if tail.lstrip().startswith(('=', ',', '[')):
            parts = es.split_top(tail, ',')
            part_offset = cursor + len(parts[0]) + 1
            for part in parts[1:]:
                following = re.match(r'\s*([A-Za-z_]\w*)\s*(?=[=\[]|$)', part)
                if following:
                    declarations.append((following[1], part_offset + following.start(1)))
                part_offset += len(part) + 1
        for name, offset in declarations:
            if name not in ENGINE_TYPE_NAMES or offset in seen:
                continue
            seen.add(offset)
            owner = next((c.name for c in source.classes if c.body_start < offset < c.body_end), '<global>')
            findings.append(SourceFinding('HC-E009', source.rel, offset,
                                          owner + '.' + name, RULES['HC-E009']))
    return findings


def _adapt(rows, source):
    # Lazy import keeps this module's pure functions independent of the lint
    # dispatcher and allows enforce_lint to import/register the adapters.
    from tools.validate.enforce_lint import _finding
    for row in rows:
        if row.path == source.rel:
            yield _finding(row.rule, source, row.offset, row.symbol, row.message)


def rule_module_names(project, source):
    # Registration is project-wide. Run the pure scan once, not once per file.
    if not project.sources or source is not project.sources[0]:
        return
    files = {item.rel: item for item in project.sources}
    by_path = {item.rel: item for item in project.sources}
    for row in module_readiness(files):
        yield from _adapt((row,), by_path[row.path])


def rule_engine_type_names(project, source):
    yield from _adapt(engine_type_names(source, source.rel), source)
