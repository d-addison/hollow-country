"""Read-only, privacy-safe RPT/config census; offline evidence, never engine acceptance.

Run with RPT --vanilla-rpt BASELINE and repeatable --ours-pbo, --dependency-pbo,
--vanilla-pbo inputs (files or directories). Output defaults to compat_audit.json.
Only fixed vocabulary, numbers and per-run diagnostic IDs leave the process: no
log excerpts, config symbols, resource paths, filenames or exception text.

The supplied brief documents taxonomy rows 1, 4, 7, 9, 11, 12 and 15 only. Missing
rows remain explicitly unavailable; --category-pattern ID=REGEX can supply their
local matchers without publishing the private taxonomy. Specific rules run before
row 4's generic Warning Message fallback. Unknown warnings remain unclassified.
Config declarations identify candidates, not the author of an engine warning;
reopenings, missing inputs and ambiguous matches never become proven blame.
Exit 0 = census written, 2 = input/storage failure (with no partial report).
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys
import tempfile

from tools.audit import pbo_config

MAX_LINE = 16384
MAX_DIAGNOSTICS = 100000
MAX_PBOS = 10000
MAX_SYMBOLS = 1000000
MAX_DEPTH = 32
OWNERS = ('ours', 'dependency', 'vanilla')
# Stable IDs are the evidence-table row numbers, not guessed missing categories.
RULES = {
    1: ('config_no_entry', r'\bNo entry\b|Trying to access error value'),
    4: ('other_warning_message', r'Warning Message'),
    7: ('animation_resource', r'\.anm\b'),
    9: ('inventory_shape', r'Wrong inventory shape'),
    11: ('unknown_object_class', r'Unknown object class'),
    12: ('localization', r'(?:locali[sz]ation|stringtable|string table).*STR_|STR_.*(?:locali[sz]ation|stringtable|string table|not found)'),
    15: ('input_or_skeleton', r'UAGestureSlot.*(?:twice|duplicate|already)|(?:twice|duplicate|already).*UAGestureSlot|ZSUSkeleton.*(?:bone|missing)|(?:bone|missing).*ZSUSkeleton'),
}
WARNING = re.compile(r'warning|error|cannot|can.t|missing|not found|unknown|\.anm\b|inserted twice', re.I)
TOKENS = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
RESOURCE = re.compile(r'[A-Za-z0-9_./\\-]+\.(?:p3d|anm|asi|agr|paa|emat|rvmat|ogg|wav)\b', re.I)
CONFIG_REF = re.compile(r'\b(Cfg[A-Za-z0-9_]+)[/\\]([A-Za-z_][A-Za-z0-9_]*)', re.I)
STAMP = re.compile(r'^\s*(?:\d{1,4}[:./-]){1,5}\d+(?:[.,]\d+)?\s*')


class InputError(ValueError):
    """Fixed-message input refusal; caller must never echo underlying exceptions."""


class PrivateParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes invalid arguments, which can contain private paths.
        raise InputError('invalid_arguments')


def category_rules(overrides=()):
    rules = {key: re.compile(value[1], re.I) for key, value in RULES.items()}
    for override in overrides:
        key, sep, pattern = override.partition('=')
        if not sep or not key.isdigit() or not 1 <= int(key) <= 15 or not pattern or len(pattern) > 512:
            raise InputError('invalid_taxonomy')
        try:
            rules[int(key)] = re.compile(pattern, re.I)
        except re.error:
            raise InputError('invalid_taxonomy') from None
    return rules


def classify(line, rules):
    for key in sorted(rules, key=lambda key: (key == 4, key)):
        if rules[key].search(line):
            return key
    return 0 if WARNING.search(line) else None


def scan_rpt(path, rules):
    """Bound line length and retained distinct diagnostics; raw text stays in RAM."""
    counts, skipped = Counter(), 0
    with Path(path).open(encoding='utf-8-sig', errors='replace') as stream:
        while True:
            line = stream.readline(MAX_LINE + 1)
            if not line:
                break
            if len(line) > MAX_LINE:
                skipped += 1
                while line and not line.endswith('\n'):
                    line = stream.readline(MAX_LINE + 1)
                continue
            category = classify(line, rules)
            if category is None:
                continue
            key = (category, STAMP.sub('', line).strip().lower())
            if key not in counts and len(counts) >= MAX_DIAGNOSTICS:
                raise InputError('diagnostic_budget')
            counts[key] += 1
    return counts, skipped


class ConfigIndex:
    """Bounded provenance from installed PBO members and nested RAP declarations."""

    def __init__(self):
        self.symbols = defaultdict(set)
        self.classes = defaultdict(set)
        self.resources = defaultdict(set)
        self.fields = defaultdict(set)
        self.pbos = Counter()
        self.configs = Counter()
        self.entries = 0

    def add(self, pbo, owner):
        index = pbo_config.read_pbo_index(pbo)
        self.pbos[owner] += 1
        for entry in index['entries']:
            self.entries += 1
            if self.entries > MAX_SYMBOLS:
                raise InputError('symbol_budget')
            name = pbo_config.normalize_path(entry['name'])
            prefix = pbo_config.normalize_path(index['prefix'])
            self.resources[(prefix + '\\' if prefix else '') + name].add(owner)
        data = pbo_config.read_member(pbo, index, 'config.bin')
        if data is None:
            return
        if len(data) < 16 or data[:4] != b'\0raP':
            raise InputError('unsupported_config')
        self.configs[owner] += 1
        # Reuse the existing bounded RAP decoder; walk nested fields rather than
        # parse_rap's intentionally firearm-only projection. Offsets may not cycle
        # or alias previously visited class bodies.
        rap = pbo_config._Rap(data)
        pending, seen = [(16, ())], set()
        while pending:
            offset, scope = pending.pop()
            if offset in seen or len(scope) > MAX_DEPTH:
                raise InputError('config_graph')
            seen.add(offset)
            _parent, entries = rap.entries(offset)
            for kind, name, value in entries:
                self.entries += 1
                if self.entries > MAX_SYMBOLS:
                    raise InputError('symbol_budget')
                name = name.lower()
                if kind == 'class':
                    self.symbols[name].add(owner)
                    self.classes[scope + (name,)].add(owner)
                    pending.append((value, scope + (name,)))
                elif kind in ('value', 'array', 'array+'):
                    field_type = 'array' if kind != 'value' else 'scalar'
                    self.fields[scope + (name,)].add((owner, field_type))
                    # Localization references can identify a candidate provider.
                    values = value if isinstance(value, list) else [value]
                    for item in values:
                        if isinstance(item, str) and re.fullmatch(r'\$?STR_[A-Za-z0-9_]+', item, re.I):
                            self.symbols[item.lstrip('$').lower()].add(owner)

    def candidates(self, line):
        owners = set()
        refs = CONFIG_REF.findall(line)
        for root, name in refs:
            owners.update(self.classes.get((root.lower(), name.lower()), ()))
        if not refs:
            for token in TOKENS.findall(line):
                owners.update(self.symbols.get(token.lower(), ()))
        for resource in RESOURCE.findall(line):
            owners.update(self.resources.get(pbo_config.normalize_path(resource), ()))
        return sorted(owners)

    def field_evidence(self, line):
        # Never serialize config paths or names. Presence/types are static evidence
        # only; absence in declarations does not account for merged inheritance.
        kinds = set()
        for path in re.findall(r'\bCfg[A-Za-z0-9_]+(?:[/\\][A-Za-z_][A-Za-z0-9_]*){2,}', line, re.I):
            parts = tuple(re.split(r'[/\\]', path.lower()))
            kinds.update(kind for _owner, kind in self.fields.get(parts, ()))
        return sorted(kinds)


def pbo_files(inputs):
    found = set()
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            for child in path.rglob('*'):
                if child.is_file() and child.suffix.lower() == '.pbo':
                    found.add(child.resolve())
                    if len(found) > MAX_PBOS:
                        raise InputError('pbo_budget')
        elif path.is_file() and path.suffix.lower() == '.pbo':
            found.add(path.resolve())
        else:
            raise InputError('missing_pbo_input')
    if inputs and not found:
        raise InputError('empty_pbo_input')
    return sorted(found)


def audit(rpt, vanilla_rpt, pbo_inputs=None, overrides=()):
    rules = category_rules(overrides)
    observed, skipped = scan_rpt(rpt, rules)
    baseline, baseline_skipped = scan_rpt(vanilla_rpt, rules)
    index = ConfigIndex()
    all_files = set()
    for owner in OWNERS:
        files = pbo_files((pbo_inputs or {}).get(owner, ()))
        if all_files.intersection(files):
            raise InputError('conflicting_pbo_ownership')
        all_files.update(files)
        if len(all_files) > MAX_PBOS:
            raise InputError('pbo_budget')
        for path in files:
            index.add(path, owner)
    rows = []
    for number, ((category, line), count) in enumerate(sorted(observed.items()), 1):
        candidates = index.candidates(line)
        matched = min(count, baseline[(category, line)])
        rows.append(dict(diagnostic_id=number, category=category, count=count,
                         vanilla_matches=matched, excess_count=count - matched,
                         origin_candidates=candidates,
                         attribution='candidate' if len(candidates) == 1 else (
                             'ambiguous' if candidates else 'unresolved'),
                         declared_field_types=index.field_evidence(line)))
    categories = []
    for key in range(1, 16):
        categories.append(dict(category=key, label=RULES[key][0] if key in RULES else 'not_supplied',
                               matcher_available=key in rules,
                               count=sum(n for (cat, _), n in observed.items() if cat == key),
                               vanilla_count=sum(n for (cat, _), n in baseline.items() if cat == key)))
    return dict(schema_version=1, evidence='offline_only', taxonomy_complete=len(rules) == 15,
                categories=categories, diagnostics=rows,
                unclassified_count=sum(n for (cat, _), n in observed.items() if cat == 0),
                vanilla_unclassified_count=sum(n for (cat, _), n in baseline.items() if cat == 0),
                oversized_lines=skipped, vanilla_oversized_lines=baseline_skipped,
                pbo_counts={owner: index.pbos[owner] for owner in OWNERS},
                config_counts={owner: index.configs[owner] for owner in OWNERS})


def main(argv=None):
    parser = PrivateParser(description=__doc__)
    parser.add_argument('rpt', type=Path)
    parser.add_argument('--vanilla-rpt', type=Path, required=True)
    for owner in OWNERS:
        parser.add_argument('--' + owner + '-pbo', action='append', default=[], type=Path)
    parser.add_argument('--category-pattern', action='append', default=[])
    parser.add_argument('--output', type=Path, default=Path('compat_audit.json'))
    try:
        args = parser.parse_args(argv)
        inputs = {owner: getattr(args, owner + '_pbo') for owner in OWNERS}
        # Refuse output aliases of inputs, including symlinks, before truncation.
        protected = {args.rpt.resolve(), args.vanilla_rpt.resolve()}
        for values in inputs.values():
            protected.update(pbo_files(values))
        if args.output.resolve() in protected:
            raise InputError('output_is_input')
        result = audit(args.rpt, args.vanilla_rpt, inputs, args.category_pattern)
        encoded = json.dumps(result, indent=2, sort_keys=True) + '\n'
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             dir=args.output.parent, prefix='.compat-audit-',
                                             delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(encoded)
            temporary.replace(args.output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        print('compat_audit: written')
        return 0
    except (OSError, ValueError, KeyError, OverflowError, RecursionError):
        print('compat_audit: input_or_storage_error', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
