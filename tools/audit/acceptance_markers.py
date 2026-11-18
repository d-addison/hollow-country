"""Static inventory of local-acceptance capability-admission markers; standard library only.

Scans mods/**/scripts/**/*.c for the gates that keep a feature closed until a local-server acceptance
run:

  profile_marker          a literal "$profile:HollowCountry/acceptance/<name>.enable" or ".disable" path
                          that script code probes with FileExist. A ".disable" marker is an opt-out: the
                          feature is on by default and an operator creates the empty file in the server
                          profile directory to turn it off. An ".enable" marker is an opt-in diagnostic
                          that stays off until the operator creates the file. The record's "polarity"
                          says which.
  dynamic_profile_marker  a string under HollowCountry/acceptance/ that is built at run time; its name
                          cannot be listed statically, so the checklist test fails on it
  source_qualification    a no-argument bool method whose name contains "Qualified" or "Accepted"; a
                          hard-coded source gate, closed until accepted evidence is recorded (no operator
                          switch exists)
  opt_in_gate             a no-argument bool method whose name contains "OptIn" that holds no literal marker

The scan reads text only. Output is JSON with repository-relative paths. It never starts DayZ, a
server or a network connection, and the scan itself writes nothing.

--write-profile-plan <dir> prints the empty ".enable" marker files it WOULD create under
<dir>/HollowCountry/acceptance/ (opt-in diagnostics only; it never creates a ".disable" marker, because
the features they gate are on by default). Only with --apply does it create them. <dir> must be an existing
directory (the server -profiles directory) outside every git checkout and outside this repository.
Existing files are never overwritten. Creating an ".enable" marker does not accept a feature; it only
lets the local acceptance run exercise it.

--opt-outs <dir> lists the ".disable" markers present under <dir>/HollowCountry/acceptance/ (the features
the operator has turned off) and any present ".disable" file that matches no marker in the source. It
writes nothing.

Feature/issue tags are inferred, not authoritative: an issue number is taken from the comment block
directly above the probing class (or the file's opening comment); failing that, from a small map of
numbers cited in this repository's own sources. A missing tag means none could be inferred.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "$profile:HollowCountry/acceptance/"
SCHEMA = 1

MARKER_LITERAL = re.compile(r'\$profile:HollowCountry/acceptance/(?P<tail>[^"\\\n]*)')
SAFE_MARKER = re.compile(r"(?P<name>[A-Za-z0-9_-]+)\.(?P<polarity>enable|disable)\Z")
CLASS_DECLARATION = re.compile(r"^[ \t]*(?:modded[ \t]+)?class[ \t]+(?P<name>[A-Za-z_]\w*)", re.MULTILINE)
GATE_DEFINITION = re.compile(
    r"(?:static[ \t]+)?bool[ \t]+(?P<name>\w*(?:Qualified|Accepted|OptIn)\w*)[ \t]*\([ \t]*\)[ \t]*\n?[ \t]*\{")
ISSUE_TAG = re.compile(r"#(\d{1,4})\b")

# Directory and file-name hints for the feature tag. First match wins; file hints beat directory hints.
FILE_FEATURES = (("Stamina", "stamina"), ("TapedLight", "taped_light"), ("FuelSiphon", "fuel_siphon"),
                 ("SiphonFuel", "fuel_siphon"), ("Weather", "weather"), ("Firearm", "firearms"))
DIRECTORY_FEATURES = {"Infected": "infected", "Ecology": "ecology", "Events": "events", "Groups": "groups",
                      "Interiors": "interiors", "Loot": "search", "Crafting": "crafting",
                      "Survival": "survival", "Weather": "weather", "Firearms": "firearms"}
# Issue numbers cited by this repository's own sources (commit titles, docstrings, catalog), used only
# when no comment carries one. Kept deliberately small.
FEATURE_ISSUES = {"fuel_siphon": ["#53"], "infected": ["#19", "#44"], "ecology": ["#34"], "stamina": ["#31"],
                  "groups": ["#37"], "events": ["#33"], "weather": ["#35"], "taped_light": ["#56"],
                  "crafting": ["#52"]}


class RefusedDestination(ValueError):
    """The requested profile-plan destination is unsafe or unusable."""


def strip_comments(text):
    """Blank // and /* */ comments (keeping newlines and offsets) while leaving string literals intact."""
    out = []
    index, length = 0, len(text)
    while index < length:
        char = text[index]
        if char == '"':
            end = index + 1
            while end < length and text[end] != '"' and text[end] != "\n":
                end += 2 if text[end] == "\\" else 1
            end = min(end + 1, length)
            out.append(text[index:end])
            index = end
        elif text.startswith("//", index):
            end = text.find("\n", index)
            end = length if end < 0 else end
            out.append(" " * (end - index))
            index = end
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            end = length if end < 0 else end + 2
            out.append("".join("\n" if c == "\n" else " " for c in text[index:end]))
            index = end
        else:
            out.append(char)
            index += 1
    return "".join(out)


def _line_of(text, offset):
    return text.count("\n", 0, offset) + 1


def _classes(code):
    return [(match.start(), match.group("name")) for match in CLASS_DECLARATION.finditer(code)]


def _class_at(classes, offset):
    found = None
    for start, name in classes:
        if start > offset:
            break
        found = (start, name)
    return found


def _method_at(code, offset, class_start):
    """Nearest preceding method-like declaration within the class, for context only."""
    pattern = re.compile(r"(?:static[ \t]+|override[ \t]+|protected[ \t]+|private[ \t]+)*"
                         r"[A-Za-z_]\w*(?:<[^>\n]*>)?[ \t]+(?P<name>[A-Za-z_]\w*)[ \t]*\([^;{}\n]*\)[ \t]*\n?[ \t]*\{")
    found = None
    for match in pattern.finditer(code, class_start, offset):
        if match.group("name") not in {"if", "while", "for", "switch", "foreach"}:
            found = match.group("name")
    return found


def _block_end(code, open_brace):
    depth = 0
    in_string = False
    index = open_brace
    while index < len(code):
        char = code[index]
        if in_string:
            if char == "\\":
                index += 1
            elif char == '"' or char == "\n":
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return len(code) - 1


def _gate_state(body):
    compact = re.sub(r"\s+", "", body)
    if compact == "returnfalse;":
        return "closed"
    if compact == "returntrue;":
        return "open"
    return "computed"


def _comment_block_above(raw_lines, line):
    """Text of the contiguous // comment lines directly above a 1-based line number."""
    block = []
    index = line - 2
    while index >= 0 and raw_lines[index].lstrip().startswith("//"):
        block.append(raw_lines[index])
        index -= 1
    return "\n".join(reversed(block))


def _issue_tags(raw_lines, class_line):
    texts = [_comment_block_above(raw_lines, class_line)]
    head = []
    for line in raw_lines[:5]:
        if not line.lstrip().startswith("//"):
            break
        head.append(line)
    texts.append("\n".join(head))
    found = []
    for text in texts:
        for number in ISSUE_TAG.findall(text):
            tag = "#" + number
            if tag not in found:
                found.append(tag)
        if found:
            break
    return found


def _file_feature(relative):
    parts = Path(relative).parts
    stem = Path(relative).stem
    for needle, feature in FILE_FEATURES:
        if needle in stem:
            return feature
    for part in parts:
        if part in DIRECTORY_FEATURES:
            return DIRECTORY_FEATURES[part]
    return None


def _tags(relative, name, raw_lines, class_line):
    file_feature = _file_feature(relative)
    feature = name if name else file_feature
    issues = _issue_tags(raw_lines, class_line) if class_line else []
    source = "comment" if issues else None
    if not issues:
        for candidate in (feature, file_feature):
            if candidate in FEATURE_ISSUES:
                issues, source = list(FEATURE_ISSUES[candidate]), "feature-map"
                break
    return feature, issues, source


def scan_text(text, relative):
    raw_lines = text.splitlines()
    code = strip_comments(text)
    classes = _classes(code)
    records = []

    def record(kind, marker, name, offset, method, state=None, polarity=None):
        owner = _class_at(classes, offset)
        class_line = _line_of(code, owner[0]) if owner else 0
        feature, issues, source = _tags(relative, name, raw_lines, class_line)
        line = _line_of(code, offset)
        records.append({
            "marker": marker, "kind": kind, "name": name, "file": relative, "line": line,
            "location": "%s:%d" % (relative, line), "class": owner[1] if owner else None,
            "method": method, "state": state, "polarity": polarity, "feature": feature, "issues": issues, "issue_source": source,
        })

    gate_spans = []
    for match in GATE_DEFINITION.finditer(code):
        start = match.end() - 1
        end = _block_end(code, start)
        gate_spans.append((match.start(), end, match))
    marker_offsets = {m.start(): m for m in MARKER_LITERAL.finditer(code)}

    for match_start, end, match in gate_spans:
        owner = _class_at(classes, match_start)
        class_name = owner[1] if owner else None
        body = code[match.end():end]
        has_marker = any(match_start <= offset <= end for offset in marker_offsets)
        name = match.group("name")
        opt_in = "OptIn" in name and "Qualified" not in name and "Accepted" not in name
        if opt_in and has_marker:
            continue  # the marker record below already names this probe
        kind = "opt_in_gate" if opt_in else "source_qualification"
        marker = "%s.%s" % (class_name, name) if class_name else name
        record(kind, marker, None, match_start, name, _gate_state(body))

    for offset, match in sorted(marker_offsets.items()):
        tail = match.group("tail")
        owner = _class_at(classes, offset)
        method = _method_at(code, offset, owner[0] if owner else 0)
        safe = SAFE_MARKER.match(tail)
        closing = code[match.end():match.end() + 1]
        if safe and closing == '"' and not _concatenated(code, match.end() + 1):
            record("profile_marker", PREFIX + tail, safe.group("name"), offset, method,
                   polarity=safe.group("polarity"))
        else:  # built at run time, nested or traversal-shaped: reported, never creatable
            record("dynamic_profile_marker", PREFIX + tail, None, offset, method)
    records.sort(key=lambda item: (item["line"], item["marker"]))
    return records


def _concatenated(code, after_quote):
    return re.match(r"[ \t]*\+", code[after_quote:after_quote + 8]) is not None


def scan_tree(root=ROOT):
    root = Path(root)
    records, scanned = [], 0
    mods = root / "mods"
    if mods.is_dir():
        for current, directories, files in os.walk(mods):
            directories.sort()
            for filename in sorted(files):
                path = Path(current) / filename
                relative = path.relative_to(root).as_posix()
                if not filename.endswith(".c") or "scripts" not in Path(relative).parts:
                    continue
                if path.is_symlink() or not path.is_file():
                    continue
                scanned += 1
                records.extend(scan_text(path.read_text(encoding="utf-8", errors="replace"), relative))
    records.sort(key=lambda item: (item["file"], item["line"], item["marker"]))
    return {"schema": SCHEMA, "root": ".", "scanned_files": scanned, "markers": records}


def creatable_names(result):
    """Opt-in (".enable") marker names only; ".disable" opt-outs are never written by this tool."""
    return sorted({item["name"] for item in result["markers"]
                   if item["kind"] == "profile_marker" and item["polarity"] == "enable"})


def opt_out_names(result):
    return sorted({item["name"] for item in result["markers"]
                   if item["kind"] == "profile_marker" and item["polarity"] == "disable"})


def present_opt_outs(result, directory):
    """The ".disable" markers present under <directory>/HollowCountry/acceptance/ (read only)."""
    base = Path(directory) / "HollowCountry" / "acceptance"
    known = set(opt_out_names(result))
    found, unknown = [], []
    if base.is_dir() and not base.is_symlink():
        for path in sorted(base.glob("*.disable")):
            name = path.name[:-len(".disable")]
            if path.is_symlink() or not path.is_file() or not re.fullmatch(r"[A-Za-z0-9_-]+", name):
                continue
            (found if name in known else unknown).append(name)
    return {"schema": SCHEMA, "directory": str(Path(directory)), "opt_outs": found, "unrecognised": unknown}


def _inside(path, parent):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _check_destination(destination, repo):
    try:
        resolved = Path(destination).resolve(strict=True)
    except (OSError, RuntimeError):
        raise RefusedDestination("destination must be an existing directory") from None
    if not resolved.is_dir():
        raise RefusedDestination("destination must be an existing directory")
    repo = Path(repo).resolve()
    if _inside(resolved, repo):
        raise RefusedDestination("destination is inside the repository")
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            raise RefusedDestination("destination is inside a git checkout")
    return resolved


def plan_profile(result, destination, repo=ROOT, only=None):
    resolved = _check_destination(destination, repo)
    names = creatable_names(result)
    if only:
        unknown = sorted(set(only) - set(names))
        if unknown:
            raise RefusedDestination("unknown marker name(s): " + ", ".join(unknown))
        names = sorted(set(only))
    base = resolved / "HollowCountry" / "acceptance"
    files = []
    for name in names:
        path = base / (name + ".enable")
        if path.is_symlink():
            raise RefusedDestination("refusing a symlinked marker path")
        files.append({"name": name, "path": str(path), "action": "exists" if path.exists() else "create"})
    return {"schema": SCHEMA, "destination": str(resolved), "applied": False, "files": files}


def apply_plan(plan):
    created = []
    for item in plan["files"]:
        if item["action"] != "create":
            continue
        path = Path(item["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "x", encoding="utf-8"):
            pass
        created.append(str(path))
    plan["applied"] = True
    plan["created"] = created
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=str(ROOT), help="repository root to scan (default: this repository)")
    parser.add_argument("--write-profile-plan", metavar="DIR",
                        help="existing server profile directory; print the marker files that would be created")
    parser.add_argument("--opt-outs", metavar="DIR",
                        help="existing server profile directory; list the .disable opt-out markers present in it")
    parser.add_argument("--apply", action="store_true", help="with --write-profile-plan, create the empty files")
    parser.add_argument("--only", action="append", metavar="NAME", help="restrict the plan to this marker name")
    args = parser.parse_args(argv)
    if args.apply and not args.write_profile_plan:
        parser.error("--apply requires --write-profile-plan <dir>")
    if args.only and not args.write_profile_plan:
        parser.error("--only requires --write-profile-plan <dir>")
    result = scan_tree(Path(args.root))
    if args.opt_outs:
        if args.write_profile_plan or args.apply or args.only:
            parser.error("--opt-outs is read only and cannot be combined with --write-profile-plan, --apply or --only")
        if not Path(args.opt_outs).is_dir():
            print("refused: destination must be an existing directory", file=sys.stderr)
            return 2
        print(json.dumps(present_opt_outs(result, args.opt_outs), indent=2, sort_keys=True))
        return 0
    if not args.write_profile_plan:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    try:
        plan = plan_profile(result, args.write_profile_plan, Path(args.root), args.only)
        if args.apply:
            apply_plan(plan)
    except RefusedDestination as error:
        print("refused: %s" % error, file=sys.stderr)
        return 2
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
