"""Portable, bounded T0 census of a supplied Enforce Script source tree.

Run ``python -B -m tools.audit.crafting_audit --root PATH``. JSON goes only to
stdout; this tool never writes inputs, follows includes, or starts DayZ. Recheck
an approved snapshot with ``--expect-manifest-sha256 HASH``. All nested .c/.C
files are included, not just the stock Recipes directory or HC's three pilots.
UTF-8 is strict by default; explicitly opt into ``--fallback-encoding cp1252``
for legacy source comments. Raw hashes and the decoding policy are both pinned.

``registered`` means a literal registration CALL EXISTS IN SOURCE; ``disabled``
means only commented-out calls were found. Neither establishes the live registry.
Preprocessor branches, invocation/order, inheritance effects and arbitrary custom
methods are not executed or interpreted. Literal references are observations,
not resolved ingredient sets, effective outputs, or merged config item counts.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys


MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_SOURCE_FILES = 8192
MAX_TREE_ENTRIES = 32768
MAX_PATH_DEPTH = 32
MAX_PATH_CHARS = 1024
MAX_TOKENS = 4_000_000
MAX_NESTING = 128
MAX_CLASSES = 32768
MAX_ANCESTRY = 128
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
TOKEN = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|[0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?|[^\s]")
LIMITATIONS = [
    "T0 source census only; no native execution or runtime acceptance.",
    "Source registered/disabled evidence is not live registry membership; runtime status is always unknown.",
    "Every nested .c file is scanned; other suffixes and external includes are not parsed.",
    "Preprocessor conditions/macros, registration invocation/order and unregister effects are not evaluated.",
    "Commented registrations are disabled-source candidates, not instructions to enable recipes.",
    "Custom methods and inherited behavior remain unresolved; literal references do not prove effective inputs or outputs.",
    "No merged item configuration, action/cooking transformation audit, inventory atomicity or multiplayer behavior is established.",
    "Native attachment combinations, proxies, power and action compatibility remain unknown.",
    "Hashes pin supplied bytes and relative paths, not the authenticity/completeness of an installed game extraction.",
    "Input must remain quiescent; portable per-file change checks do not create an atomic filesystem snapshot.",
]


class CensusError(Exception):
    def __init__(self, code, source=".", line=0):
        self.code, self.source, self.line = code, source, line
        super().__init__(code)


@dataclass(frozen=True)
class Lexeme:
    text: str
    kind: str
    line: int
    start: int
    end: int
    conditions: tuple[str, ...]


def _bounded(condition, source=".", line=0):
    if not condition:
        raise CensusError("resource_limit", source, line)


def _unsafe(metadata):
    # Windows junctions/reparse points must not escape the supplied tree either.
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _stamp(metadata):
    return (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)


def _sources(root):
    """Yield bounded, stable file bytes, rejecting links and special entries."""
    try:
        root = Path(root).absolute()
        metadata = root.lstat()
        if _unsafe(metadata) or not stat.S_ISDIR(metadata.st_mode):
            raise CensusError("invalid_root")
        root = root.resolve(strict=True)
    except (OSError, ValueError, RuntimeError, TypeError):
        raise CensusError("invalid_root") from None
    pending = [(root, 0)]
    entries = total_bytes = source_count = 0
    while pending:
        folder, depth = pending.pop()
        relative_folder = folder.relative_to(root).as_posix()
        _bounded(depth <= MAX_PATH_DEPTH, relative_folder)
        try:
            metadata = folder.lstat()
            if _unsafe(metadata) or not stat.S_ISDIR(metadata.st_mode):
                raise CensusError("unsafe_source_path", relative_folder)
            children = []
            with os.scandir(folder) as scan:
                for entry in scan:
                    entries += 1
                    _bounded(entries <= MAX_TREE_ENTRIES, relative_folder)
                    children.append(entry.name)
            for name in sorted(children):
                path = folder / name
                relative = path.relative_to(root).as_posix()
                _bounded(len(relative) <= MAX_PATH_CHARS, relative_folder)
                _bounded(len(path.relative_to(root).parts) <= MAX_PATH_DEPTH, relative_folder)
                if any(ord(char) < 32 or char == "\\" for char in relative):
                    raise CensusError("unsafe_source_path", relative_folder)
                metadata = path.lstat()
                if _unsafe(metadata):
                    raise CensusError("unsafe_source_path", relative)
                if stat.S_ISDIR(metadata.st_mode):
                    _bounded(depth + 1 <= MAX_PATH_DEPTH, relative)
                    pending.append((path, depth + 1))
                elif not stat.S_ISREG(metadata.st_mode):
                    raise CensusError("unsafe_source_path", relative)
                elif path.suffix.lower() == ".c":
                    source_count += 1
                    _bounded(source_count <= MAX_SOURCE_FILES, relative)
                    _bounded(metadata.st_size <= MAX_FILE_BYTES, relative)
                    _bounded(total_bytes + metadata.st_size <= MAX_TOTAL_BYTES, relative)
                    with path.open("rb") as handle:
                        before = os.fstat(handle.fileno())
                        if not stat.S_ISREG(before.st_mode) or _stamp(before) != _stamp(metadata):
                            raise CensusError("input_changed", relative)
                        content = handle.read(MAX_FILE_BYTES + 1)
                        after = os.fstat(handle.fileno())
                    _bounded(len(content) <= MAX_FILE_BYTES, relative)
                    total_bytes += len(content)
                    _bounded(total_bytes <= MAX_TOTAL_BYTES, relative)
                    if _stamp(before) != _stamp(after) or len(content) != before.st_size:
                        raise CensusError("input_changed", relative)
                    yield relative, content
        except OSError:
            raise CensusError("unreadable_input", relative_folder) from None


def _lex(text, source, budget, *, first_line=1, strict=True, inherited=()):
    tokens, comments, directives = [], [], []
    branches = []
    i, line = 0, first_line
    while i < len(text):
        char = text[i]
        conditions = (*inherited, *(branch[1] for branch in branches))
        if char.isspace():
            line += char == "\n"
            i += 1
            continue
        if strict and char == "#" and not text[text.rfind("\n", 0, i) + 1:i].strip():
            end = text.find("\n", i)
            end = len(text) if end == -1 else end
            while text[i:end].rstrip().endswith("\\") and end < len(text):
                next_end = text.find("\n", end + 1)
                end = len(text) if next_end == -1 else next_end
            directive = text[i:end].strip()
            word = directive[1:].strip().split(maxsplit=1)[0] if directive[1:].strip() else ""
            directives.append({"source": source, "line": line, "text": directive})
            if word in ("if", "ifdef", "ifndef"):
                branches.append((directive, directive, False))
                _bounded(len(branches) <= MAX_NESTING, source, line)
            elif word in ("elif", "else"):
                if not branches or branches[-1][2]:
                    raise CensusError("invalid_source", source, line)
                origin = branches[-1][0]
                branches[-1] = (origin, directive + " after " + origin, word == "else")
            elif word == "endif":
                if not branches:
                    raise CensusError("invalid_source", source, line)
                branches.pop()
            line += text[i:end].count("\n")
            i = end
            continue
        if text.startswith("//", i) or text.startswith("/*", i):
            block = text.startswith("/*", i)
            end = text.find("*/" if block else "\n", i + 2)
            if end == -1:
                if block and strict:
                    raise CensusError("invalid_source", source, line)
                end = len(text)
            comments.append((text[i + 2:end], line, conditions))
            stop = end + 2 if block and end < len(text) else end
            line += text[i:stop].count("\n")
            i = stop
            continue
        start, start_line = i, line
        if char in ('"', "'"):
            i += 1
            while i < len(text) and text[i] != char:
                if text[i] == "\\":
                    i += 2
                else:
                    i += 1
            if i >= len(text):
                if strict:
                    raise CensusError("invalid_source", source, start_line)
                break  # Unclosed prose quotation in a comment is not source.
            i += 1
            kind = "string" if char == '"' else "char"
            line += text[start:i].count("\n")
        else:
            match = TOKEN.match(text, i)
            if not match or char == "\x00":
                raise CensusError("invalid_source", source, line)
            i = match.end()
            kind = "identifier" if IDENTIFIER.fullmatch(match.group()) else "symbol"
        budget[0] += 1
        _bounded(budget[0] <= MAX_TOKENS, source, start_line)
        tokens.append(Lexeme(text[start:i], kind, start_line, start, i, conditions))
    if branches:
        raise CensusError("invalid_source", source, line)
    return tokens, comments, directives


def _pairs(tokens, source, *, strict=True):
    pairs, stack = {}, []
    closing = {")": "(", "]": "[", "}": "{"}
    for index, token in enumerate(tokens):
        if token.kind in ("string", "char"):
            continue
        if token.text in ("(", "[", "{"):
            stack.append(index)
            _bounded(len(stack) <= MAX_NESTING, source, token.line)
        elif token.text in closing:
            if not stack or tokens[stack[-1]].text != closing[token.text]:
                if strict:
                    raise CensusError("invalid_source", source, token.line)
                continue
            opening = stack.pop()
            pairs[opening] = index
    if stack and strict:
        raise CensusError("invalid_source", source, tokens[stack[-1]].line)
    return pairs


def _arguments(tokens, opening, pairs):
    close = pairs[opening]
    result, start, i = [], opening + 1, opening + 1
    while i < close:
        if tokens[i].text == ",":
            result.append(tokens[start:i])
            start = i + 1
        elif i in pairs:
            i = pairs[i]
        i += 1
    if start < close:
        result.append(tokens[start:close])
    return result


def _string(argument):
    if len(argument) != 1 or argument[0].kind != "string":
        return None
    try:
        return json.loads(argument[0].text)
    except (ValueError, TypeError):
        return None


def _methods(tokens, start, stop, pairs, text, source):
    methods, declarations = [], set()
    i = start + 1
    while i < stop:
        if tokens[i].text == "(" and i in pairs and i > start + 1:
            name, close = tokens[i - 1], pairs[i]
            following = tokens[close + 1].text if close + 1 < stop else ""
            if name.kind == "identifier" and following in ("{", ";"):
                # A top-level initializer call is not a method declaration.
                previous = tokens[i - 2].text
                if previous not in ("=", "new", "."):
                    declarations.add(i - 1)
                    if following == "{":
                        end = pairs[close + 1]
                        body = text[tokens[close + 1].start:tokens[end].end]
                        methods.append({"name": name.text, "source": source, "line": name.line,
                                        "conditions": list(name.conditions),
                                        "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                                        "_start": close + 1, "_end": end})
                        i = end + 1
                        continue
        if tokens[i].text == "{" and i in pairs:
            i = pairs[i]
        i += 1
    return methods, declarations


def _classes(tokens, pairs, text, source):
    definitions, declarations = [], set()
    for i, token in enumerate(tokens):
        if token.text != "class" or token.kind != "identifier" or i + 2 >= len(tokens):
            continue
        name = tokens[i + 1]
        if name.kind != "identifier":
            continue
        j, parent = i + 2, None
        if tokens[j].text in ("extends", ":"):
            if j + 1 >= len(tokens) or tokens[j + 1].kind != "identifier":
                raise CensusError("invalid_source", source, token.line)
            parent = tokens[j + 1].text
            j += 2
        # Generic declarations are outside the simple header grammar. Preserve
        # the declaration name but do not claim its ancestry was resolved.
        header_unresolved = tokens[j].text not in ("{", ";") if j < len(tokens) else True
        while j < len(tokens) and tokens[j].text not in ("{", ";"):
            j += 1
        if j == len(tokens) or tokens[j].text == ";":
            continue
        end = pairs[j]
        methods, names = _methods(tokens, j, end, pairs, text, source)
        declarations.update(names)
        definitions.append({"class": name.text, "source": source, "line": token.line,
                            "parent": parent, "modded": i > 0 and tokens[i - 1].text == "modded",
                            "conditions": list(token.conditions), "methods": methods,
                            "header_unresolved": header_unresolved,
                            "_start": j, "_end": end})
    return definitions, declarations


def _registrations(tokens, pairs, source, declarations=(), *, disabled=False):
    rows = []
    for i, token in enumerate(tokens[:-1]):
        if token.kind != "identifier" or token.text not in ("RegisterRecipe", "UnregisterRecipe"):
            continue
        if i in declarations or tokens[i + 1].text != "(" or i + 1 not in pairs:
            continue
        arguments = _arguments(tokens, i + 1, pairs)
        name, unresolved = None, []
        if token.text == "RegisterRecipe":
            argument = arguments[0] if len(arguments) == 1 else []
            if len(argument) >= 2 and argument[0].text == "new" and argument[1].kind == "identifier":
                name = argument[1].text
                if [part.text for part in argument[2:]] not in ([], ["(", ")"]):
                    unresolved.append("constructor_expression")
            else:
                unresolved.append("dynamic_registration")
        else:
            name = _string(arguments[0]) if len(arguments) == 1 else None
            if not name or not IDENTIFIER.fullmatch(name):
                name = None
                unresolved.append("dynamic_unregistration")
        if token.conditions:
            unresolved.append("conditional_code")
        rows.append({"class": name, "call": token.text, "source": source, "line": token.line,
                     "disabled": disabled, "conditions": list(token.conditions), "unresolved": unresolved})
    return rows


def _literal_references(definition, tokens, pairs):
    facts, unresolved = [], []
    for i in range(definition["_start"] + 1, definition["_end"]):
        token = tokens[i]
        if token.kind != "identifier" or token.text not in ("InsertIngredient", "InsertIngredientEx", "RemoveIngredient", "AddResult"):
            continue
        if tokens[i + 1].text != "(" or i + 1 not in pairs:
            continue
        arguments = _arguments(tokens, i + 1, pairs)
        slot = None
        if token.text == "AddResult":
            item = _string(arguments[0]) if len(arguments) == 1 else None
        else:
            first = arguments[0] if arguments else []
            if len(first) == 1 and first[0].text in ("0", "1"):
                slot = int(first[0].text)
            item = _string(arguments[1]) if len(arguments) >= 2 and slot is not None else None
        if item is None:
            unresolved.append({"code": "dynamic_item_reference", "source": definition["source"], "line": token.line})
            continue
        method = next((method["name"] for method in definition["methods"]
                       if method["_start"] < i < method["_end"]), None)
        facts.append({"call": token.text, "slot": slot, "item": item,
                      "source": definition["source"], "line": token.line,
                      "method": method, "conditions": list(token.conditions)})
    return facts, unresolved


def _parse(text, source, budget):
    tokens, comments, directives = _lex(text, source, budget)
    pairs = _pairs(tokens, source)
    definitions, declarations = _classes(tokens, pairs, text, source)
    registrations = _registrations(tokens, pairs, source, declarations)
    for comment, line, conditions in comments:
        # Do not parse arbitrary prose unless a candidate call is present.
        if "RegisterRecipe" not in comment and "UnregisterRecipe" not in comment:
            continue
        parts, _, _ = _lex(comment, source, budget, first_line=line, strict=False, inherited=conditions)
        registrations.extend(_registrations(parts, _pairs(parts, source, strict=False), source, disabled=True))
    for definition in definitions:
        definition["literal_references"], definition["literal_unresolved"] = _literal_references(definition, tokens, pairs)
    return definitions, registrations, directives


def _ancestry(name, definitions):
    chain, seen = [], set()
    current = name
    while current:
        _bounded(len(chain) < MAX_ANCESTRY)
        chain.append(current)
        if current == "RecipeBase":
            return chain, True, None
        if current in seen:
            return chain, False, "cycle"
        seen.add(current)
        bases = [row for row in definitions.get(current, []) if not row["modded"]]
        if len(bases) != 1 or bases[0]["header_unresolved"]:
            return chain, False, "missing_or_ambiguous_parent"
        current = bases[0]["parent"]
    return chain, False, "not_recipe_ancestry"


def _public(row):
    return {key: value for key, value in row.items() if not key.startswith("_")}


def _reconcile(definitions, registrations):
    grouped = defaultdict(list)
    children = defaultdict(set)
    for definition in definitions:
        grouped[definition["class"]].append(definition)
        if definition["parent"]:
            children[definition["parent"]].add(definition["class"])
    ancestry = {name: _ancestry(name, grouped) for name in sorted(grouped)}
    # Candidate discovery must follow EVERY declared inheritance edge. A unique
    # resolved chain is insufficient: conditional duplicates can hide both an
    # unregistered recipe and all its descendants. This reverse graph visits
    # each name/edge once, including branching cycles, without choosing a branch.
    names = {"RecipeBase"}
    pending = deque(["RecipeBase"])
    while pending:
        for child in sorted(children.get(pending.popleft(), ())):
            if child not in names:
                names.add(child)
                pending.append(child)
    names.remove("RecipeBase")
    names.update(row["class"] for row in registrations if row["class"])
    by_name = defaultdict(list)
    for row in registrations:
        by_name[row["class"]].append(row)
    recipes = []
    for name in sorted(names):
        own = grouped.get(name, [])
        chain, derived, reason = ancestry.get(name, ([name], False, "missing_declaration"))
        active = [row for row in by_name[name] if not row["disabled"] and row["call"] == "RegisterRecipe"]
        disabled = [row for row in by_name[name] if row["disabled"] and row["call"] == "RegisterRecipe"]
        removals = [row for row in by_name[name] if not row["disabled"] and row["call"] == "UnregisterRecipe"]
        unresolved = []
        if not derived:
            unresolved.append({"code": "unresolved_ancestry", "reason": reason})
        if len([row for row in own if not row["modded"]]) > 1:
            unresolved.append({"code": "ambiguous_definition"})
        if any(row["modded"] for row in own):
            unresolved.append({"code": "modded_definition"})
        if len(active) > 1:
            unresolved.append({"code": "duplicate_registration"})
        if removals:
            unresolved.append({"code": "registration_order_and_unregistration"})
        methods, facts = [], []
        for definition in own:
            methods.extend(_public(method) for method in definition["methods"])
            facts.extend(definition["literal_references"])
            unresolved.extend(definition["literal_unresolved"])
            for method in definition["methods"]:
                unresolved.append({"code": "custom_method_semantics", "method": method["name"],
                                   "source": method["source"], "line": method["line"]})
        if len(chain) > 1:
            unresolved.append({"code": "inherited_semantics"})
        if any(row["conditions"] for row in own + active):
            unresolved.append({"code": "conditional_code"})
        if any(row["unresolved"] for row in active):
            unresolved.append({"code": "registration_expression"})
        if removals or len(active) > 1:
            status = "unresolved"
        elif active:
            status = "conditional" if active[0]["conditions"] or any(row["conditions"] for row in own) else "registered"
        elif disabled:
            status = "disabled"
        else:
            status = "unregistered"
        recipes.append({"class": name, "declaration_status": "declared" if own else "missing",
                        "definitions": [{key: row[key] for key in ("source", "line", "parent", "modded", "conditions")} for row in own],
                        "ancestry": chain, "recipe_ancestry_resolved": derived,
                        "source_status": status, "runtime_status": "unknown",
                        "registrations": active, "disabled_registrations": disabled,
                        "unregistrations": removals, "methods": methods,
                        "literal_references": facts, "unresolved": unresolved,
                        "semantics_resolved": False})
    return recipes


def audit_tree(root, *, expected_manifest_sha256=None, fallback_encoding=None):
    """Return deterministic JSON-compatible facts; partial/invalid scans fail closed.

    ``valid`` and ``source_census_complete`` only describe this lexical census of
    supplied .c inputs. They never mean crafting semantics/runtime coverage pass.
    Absolute machine paths, timestamps and source bodies are omitted from output.
    """
    sources, definitions, registrations, directives, diagnostics = [], [], [], [], []
    complete, budget = True, [0]
    if fallback_encoding not in (None, "cp1252"):
        diagnostics.append({"code": "invalid_encoding_policy", "source": ".", "line": 0, "severity": "error"})
        fallback_encoding = None
    try:
        for source, content in _sources(root):
            record = {"path": source, "bytes": len(content),
                      "sha256": hashlib.sha256(content).hexdigest()}
            sources.append(record)
            try:
                try:
                    text = content.decode("utf-8-sig")
                    record["encoding"] = "utf-8-sig"
                except UnicodeError:
                    if fallback_encoding is None:
                        raise CensusError("invalid_source", source) from None
                    try:
                        text = content.decode(fallback_encoding)
                        record["encoding"] = fallback_encoding
                    except UnicodeError:
                        raise CensusError("invalid_source", source) from None
                classes, calls, preprocessor = _parse(text, source, budget)
                _bounded(len(definitions) + len(classes) <= MAX_CLASSES, source)
                definitions.extend(classes)
                registrations.extend(calls)
                directives.extend(preprocessor)
            except CensusError as error:
                if error.code == "resource_limit":
                    raise
                complete = False
                diagnostics.append({"code": error.code, "source": error.source,
                                    "line": error.line, "severity": "error"})
    except CensusError as error:
        complete = False
        diagnostics.append({"code": error.code, "source": error.source,
                            "line": error.line, "severity": "error"})
    sources.sort(key=lambda row: row["path"])
    definitions.sort(key=lambda row: (row["source"], row["line"]))
    registrations.sort(key=lambda row: (row["source"], row["line"], row["disabled"], row["call"], row["class"] or ""))
    directives.sort(key=lambda row: (row["source"], row["line"]))
    if not sources and complete:
        complete = False
        diagnostics.append({"code": "no_sources", "source": ".", "line": 0, "severity": "error"})
    try:
        recipes = _reconcile(definitions, registrations)
    except CensusError as error:
        recipes, complete = [], False
        diagnostics.append({"code": error.code, "source": error.source,
                            "line": error.line, "severity": "error"})
    for directive in directives:
        diagnostics.append({"code": "preprocessor_not_evaluated", "source": directive["source"],
                            "line": directive["line"], "severity": "warning"})
    manifest = None
    if complete:
        payload = {"schema_version": 1, "suffix": ".c (case-insensitive)",
                   "fallback_encoding": fallback_encoding, "sources": sources}
        manifest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()
    if expected_manifest_sha256 is not None:
        if not isinstance(expected_manifest_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_manifest_sha256):
            diagnostics.append({"code": "invalid_manifest_pin", "source": ".", "line": 0, "severity": "error"})
        elif manifest != expected_manifest_sha256.lower():
            diagnostics.append({"code": "manifest_mismatch", "source": ".", "line": 0, "severity": "error"})
    diagnostics.sort(key=lambda row: (row["source"], row["line"], row["code"]))
    valid = complete and not any(row["severity"] == "error" for row in diagnostics)
    declared_candidates = [row for row in recipes if row["declaration_status"] == "declared"]
    declared = [row for row in declared_candidates if row["recipe_ancestry_resolved"]]
    active = [row for row in registrations if not row["disabled"] and row["call"] == "RegisterRecipe"]
    disabled = [row for row in registrations if row["disabled"] and row["call"] == "RegisterRecipe"]
    return {"schema_version": 1, "evidence_layer": "T0_source_only", "valid": valid,
            "inputs_complete": complete, "manifest_sha256": manifest, "sources": sources,
            "fallback_encoding": fallback_encoding,
            "registrations": registrations, "recipes": recipes, "directives": directives,
            "item_literals": sorted({fact["item"] for row in recipes for fact in row["literal_references"]}),
            "diagnostics": diagnostics, "limitations": list(LIMITATIONS),
            "coverage": {
                "source_census_complete": valid,
                "source_files": len(sources), "source_bytes": sum(row["bytes"] for row in sources),
                "declared_recipe_classes": len(declared),
                "declared_recipe_candidate_classes": len(declared_candidates),
                "declared_recipe_definitions": sum(len(row["definitions"]) for row in declared),
                "unresolved_ancestry_classes": sum(not row["recipe_ancestry_resolved"] for row in recipes),
                "source_registration_calls": len(active),
                "source_registered_names": len({row["class"] for row in active if row["class"] and not row["conditions"]}),
                "disabled_registration_calls": len(disabled),
                "source_disabled_names": sum(row["source_status"] == "disabled" for row in recipes),
                "unregistered_declared_names": sum(row["source_status"] == "unregistered" for row in declared_candidates),
                "conditional_registration_calls": sum(bool(row["conditions"]) for row in active),
                "unresolved_registration_calls": sum(bool(row["unresolved"]) for row in active),
                "unresolved_recipe_classes": sum(bool(row["unresolved"]) for row in recipes),
                "preprocessor_resolved": not directives,
                "runtime_registered_recipes": None, "merged_item_config_classes": None,
                "attachment_utility": {"status": "unknown", "combinations": None,
                                       "scope": ["native_attachments", "proxies", "power", "actions"]},
                "full_native_crafting_coverage": False,
            }}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", required=True, help="Supplied source tree; scan every nested .c/.C file")
    parser.add_argument("--expect-manifest-sha256", help="Fail if the complete input manifest differs")
    parser.add_argument("--fallback-encoding", choices=("cp1252",), help="Explicit legacy fallback after strict UTF-8 fails")
    args = parser.parse_args(argv)
    report = audit_tree(args.root, expected_manifest_sha256=args.expect_manifest_sha256,
                        fallback_encoding=args.fallback_encoding)
    print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
