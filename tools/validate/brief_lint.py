"""Reject a worker brief that is missing a required section (template v2, docs/briefs/TEMPLATE.md).

Standard library only. This checks the shape of a brief, never whether its invariants are right.
A brief passes when every required section exists with real content: goal, owned files (listed, not
described), invariants, a failure table with a handling column, required evidence, base branch,
checks and report format; crash, persistence and dependency-boundary briefs also need a
"Design review: <reviewer> <date>" line. Several briefs on the command line are also checked for
overlapping owned files.

Usage: python3 -B -m tools.validate.brief_lint BRIEF.md [BRIEF.md ...]
"""
import argparse
from dataclasses import dataclass
import re
import sys
from pathlib import Path

REVIEW_KINDS = ('crash', 'persistence', 'dependency-boundary')
KINDS = REVIEW_KINDS + ('feature', 'fix', 'tooling', 'docs')
SECTIONS = ('goal', 'owned files', 'invariants', 'failure table', 'required evidence',
            'base branch', 'checks', 'report format')

RULES = {
    'HC-B001': 'required section is missing',
    'HC-B002': 'section is empty, a placeholder or too thin to act on',
    'HC-B003': 'owned files are not listed as concrete paths',
    'HC-B004': 'failure table has no handling column or no complete row',
    'HC-B005': 'required evidence names no [HC Use], [HC SelfTest] or [HC Ready] line',
    'HC-B006': 'base branch is not dev or main',
    'HC-B007': 'kind is missing or invalid, or a review kind lacks its design review line',
    'HC-B008': 'checks do not cover the owned file types',
    'HC-B009': 'report format is missing',
    'HC-B010': 'owned files overlap another brief',
}

_HEADING = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')
_FENCE = re.compile(r'^\s*(```|~~~)')
_LIST_ITEM = re.compile(r'^\s*(?:[-*+]|\d+[.)])\s+(.*\S)\s*$')
_PLACEHOLDER = re.compile(r'^\W*(?:<[^>]*>|tbd|todo|n/?a|none|nothing|\.\.\.|…|-+)\W*$', re.I)
_OPEN_ENDED = re.compile(r'\b(?:etc\.?|and (?:any )?(?:other|related|similar)|as needed|whatever|anything else'
                         r'|related files|and so on)\b|\.\.\.|…', re.I)
_PATHLIKE = re.compile(r'^[\w.\-*?{}\[\]/@+]+$')
_EVIDENCE = re.compile(r'\[HC (?:Use|SelfTest|Ready)\]')
_RUNNER = re.compile(r'\b(?:python3|agent-run|git|bash)\b')
_STORE_FILE = re.compile(r'store|journal|persist|save|migrat|bridge', re.I)
_DATE = re.compile(r'\b\d{4}-\d{2}-\d{2}\b')
_HANDLING_HEADER = re.compile(r'handl|recover|response|action|expected|outcome', re.I)


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    line: int = 0

    def __str__(self):
        where = f':{self.line}' if self.line else ''
        return f'{self.code}{where} {self.message}'


@dataclass
class Section:
    title: str
    line: int
    lines: list


def normalise(title):
    text = re.sub(r'^[\s\d.)(:-]+', '', title.lower())
    return re.sub(r'[\s:*`]+$', '', text)


def split_sections(text):
    """Sections by heading, outside code fences; a section runs to the next heading of equal or higher level."""
    headings = []
    fenced = False
    lines = text.splitlines()
    for number, line in enumerate(lines):
        if _FENCE.match(line):
            fenced = not fenced
            continue
        match = None if fenced else _HEADING.match(line)
        if match:
            headings.append((number, len(match.group(1)), normalise(match.group(2))))
    sections = {}
    for index, (number, level, title) in enumerate(headings):
        end = len(lines)
        for later_number, later_level, _ in headings[index + 1:]:
            if later_level <= level:
                end = later_number
                break
        sections.setdefault(title, Section(title, number + 1, lines[number + 1:end]))
    return sections


def find_section(sections, name):
    for title, section in sections.items():
        if title == name or title.startswith(name):
            return section
    return None


def list_items(lines):
    items = []
    fenced = False
    for line in lines:
        if _FENCE.match(line):
            fenced = not fenced
            continue
        match = None if fenced else _LIST_ITEM.match(line)
        if match:
            items.append(match.group(1).strip())
    return items


def prose(lines):
    return ' '.join(line.strip() for line in lines if line.strip() and not line.strip().startswith('|'))


def real(text):
    return bool(text.strip()) and not _PLACEHOLDER.match(text.strip())


def table_rows(lines):
    rows = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            cells = [cell.strip() for cell in stripped.strip('|').split('|')]
            if not all(re.fullmatch(r':?-{2,}:?', cell) for cell in cells):
                rows.append(cells)
    return rows


def entry_paths(entry):
    ticked = re.findall(r'`([^`]+)`', entry)
    if ticked:
        return [token.strip() for token in ticked]
    words = entry.split()
    return [words[0].rstrip(',;:.')] if words else []


def glob_regex(pattern):
    out = ''
    index = 0
    while index < len(pattern):
        if pattern.startswith('**', index):
            out += '.*'
            index += 2
        elif pattern[index] == '*':
            out += '[^/]*'
            index += 1
        elif pattern[index] == '?':
            out += '[^/]'
            index += 1
        else:
            out += re.escape(pattern[index])
            index += 1
    return re.compile(out)


def literal_prefix(pattern):
    return re.split(r'[*?\[{]', pattern, maxsplit=1)[0]


def too_broad(path):
    """A wildcard in the first component, or a bare ** / * directly below the top level, owns a whole tree."""
    parts = path.split('/')
    for position, part in enumerate(parts):
        if re.search(r'[*?]', part):
            return position == 0 or (position == 1 and part in ('*', '**'))
    return False


def owned_paths(sections):
    section = find_section(sections, 'owned files')
    if section is None:
        return []
    paths = []
    for entry in list_items(section.lines):
        for token in entry_paths(entry):
            if _PATHLIKE.match(token) and ('/' in token or '.' in token):
                paths.append(token)
    return paths


def lint(text):
    findings = []
    sections = split_sections(text)
    found = {name: find_section(sections, name) for name in SECTIONS}
    for name, section in found.items():
        if section is None:
            findings.append(Finding('HC-B001', f'missing section: {name}'))

    kind_match = re.search(r'(?im)^[\s>*-]*kind\s*:\s*`?([\w-]+)`?', text)
    kind = kind_match.group(1).lower() if kind_match else ''
    owned = owned_paths(sections)
    if kind not in KINDS:
        findings.append(Finding('HC-B007', 'Kind: line missing or not one of ' + ', '.join(KINDS)))
    if kind in REVIEW_KINDS:
        review = re.search(r'(?im)^[\s>*-]*design review\s*:\s*(.+)$', text)
        value = review.group(1).strip() if review else ''
        reviewer = re.sub(r'\d{4}-\d{2}-\d{2}', '', value).strip(' `*-:')
        if not (_DATE.search(value) and reviewer and not _PLACEHOLDER.match(reviewer)):
            findings.append(Finding('HC-B007', f'{kind} brief needs a "Design review: <reviewer> <YYYY-MM-DD>" line'))
    elif kind in KINDS and any(path.endswith('.c') and _STORE_FILE.search(path.rsplit('/', 1)[-1]) for path in owned):
        findings.append(Finding('HC-B007', f'owned files touch a store, journal, save or bridge file; Kind: {kind} must be '
                                'crash, persistence or dependency-boundary with a design review line'))

    section = found['goal']
    if section is not None and (len(prose(section.lines).split()) < 8 or not real(prose(section.lines))):
        findings.append(Finding('HC-B002', 'goal is empty or a placeholder', section.line))

    section = found['owned files']
    if section is not None:
        items = list_items(section.lines)
        bad = [item for item in items if not any(_PATHLIKE.match(t) and ('/' in t or '.' in t) for t in entry_paths(item))]
        if not items:
            findings.append(Finding('HC-B003', 'owned files section lists no files; list one path per bullet', section.line))
        for item in bad:
            findings.append(Finding('HC-B003', f'owned entry is not a concrete path: {item[:60]}', section.line))
        if _OPEN_ENDED.search(' '.join(section.lines)):
            findings.append(Finding('HC-B003', 'owned files are open ended (etc, "and other", ...); list every file', section.line))
        for path in owned:
            if re.fullmatch(r'[*]+', path) or too_broad(path):
                findings.append(Finding('HC-B003', f'owned glob is too broad: {path}', section.line))
            if any(token in path for token in ('<', '>')) or path.startswith(('/', '~')):
                findings.append(Finding('HC-B003', f'owned path must be repo relative: {path}', section.line))

    section = found['invariants']
    if section is not None:
        items = list_items(section.lines)
        if not items or not all(real(item) and len(item.split()) >= 3 for item in items):
            findings.append(Finding('HC-B002', 'invariants need at least one real numbered statement of 3+ words, no placeholders', section.line))

    section = found['failure table']
    if section is not None:
        rows = table_rows(section.lines)
        header, body = (rows[0], rows[1:]) if rows else ([], [])
        handling = [i for i, cell in enumerate(header) if _HANDLING_HEADER.search(cell)]
        if len(header) < 2 or not handling:
            findings.append(Finding('HC-B004', 'failure table needs a table whose header has a handling column', section.line))
        elif not body:
            findings.append(Finding('HC-B004', 'failure table has no rows', section.line))
        elif any(len(row) != len(header) or not all(real(cell) for cell in row) for row in body):
            findings.append(Finding('HC-B004', 'every failure table row needs every column filled with real text', section.line))

    section = found['required evidence']
    if section is not None:
        body = '\n'.join(section.lines)
        lines = [line for line in section.lines if _EVIDENCE.search(line)]
        ok = any('<' not in line for line in lines)
        waived = kind in ('tooling', 'docs') and re.search(r'(?im)^\W*none\s*:\s*\S+(?:\s+\S+){2,}', body)
        if not ok and not waived:
            findings.append(Finding('HC-B005', 'required evidence needs a concrete [HC Use] / [HC SelfTest] / [HC Ready] line '
                                    '(tooling and docs may write "none: <reason>")', section.line))

    section = found['base branch']
    if section is not None:
        first = next((re.sub(r'[`*_]', '', line).strip() for line in section.lines if line.strip()), '')
        if not re.match(r'(?i)^(?:base(?: branch)?\s*[:=]\s*)?(?:dev|main)\b', first):
            findings.append(Finding('HC-B006', 'base branch section must start with dev or main', section.line))

    section = found['checks']
    if section is not None:
        body = '\n'.join(section.lines)
        if not _RUNNER.search(body):
            findings.append(Finding('HC-B008', 'checks list no command to run', section.line))
        if any(path.endswith('.c') for path in owned) and not ('enforce_lint' in body and 'enforce_perf' in body):
            findings.append(Finding('HC-B008', 'owned .c files need the enforce_lint and enforce_perf checks', section.line))
        if any(path.endswith('.py') for path in owned) and 'hygiene' not in body:
            findings.append(Finding('HC-B008', 'owned .py files need the hygiene check', section.line))

    section = found['report format']
    if section is not None and len(prose(section.lines).split()) < 8:
        findings.append(Finding('HC-B009', 'report format is empty or too thin', section.line))
    return findings


def overlaps(first, second):
    if first == second or glob_regex(first).fullmatch(second) or glob_regex(second).fullmatch(first):
        return True
    one, two = literal_prefix(first), literal_prefix(second)
    wild = ('*' in first and '*' in second)
    return wild and (one.startswith(two) or two.startswith(one))


def peer_findings(owned_by_brief):
    findings = []
    names = sorted(owned_by_brief)
    for index, name in enumerate(names):
        for other in names[index + 1:]:
            for path in owned_by_brief[name]:
                for peer in owned_by_brief[other]:
                    if overlaps(path, peer):
                        findings.append((name, Finding('HC-B010', f'{path} overlaps {peer} owned by {other}')))
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('briefs', nargs='+', type=Path, help='brief files; several are also checked for overlapping owned files')
    args = parser.parse_args(argv)
    failures = 0
    owned = {}
    for path in args.briefs:
        try:
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError) as exc:
            print(f'brief_lint: {path.name}: unreadable ({type(exc).__name__})')
            failures += 1
            continue
        found = lint(text)
        owned[path.name] = owned_paths(split_sections(text))
        for finding in found:
            print(f'{path.name}: {finding}')
        failures += len(found)
    if len(args.briefs) > 1:
        for name, finding in peer_findings(owned):
            print(f'{name}: {finding}')
            failures += 1
    print(f'brief_lint: {"fail" if failures else "pass"} briefs={len(args.briefs)} findings={failures}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
