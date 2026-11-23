"""Documentation drift checks (run by tools.validate.hygiene on every tracked Markdown file).

Three classes of drift fail automatically, each reported as (code, path, line):

  doc_rule_unknown       a document cites a lint or perf rule id (HC-E040, HC-P003, HC-A011 ...) that no
                         rule table defines. The one intentionally unused id (HC-P002) is reserved below.
  rule_undocumented      a rule in enforce_lint.RULES or enforce_perf.RULES appears in no document (path is
                         the rule table's module, line is the rule number, e.g. 40 for HC-E040). The
                         generated pitfall cards (docs/pitfalls) carry every rule, so this also fails when
                         those cards are stale; regenerate them with tools.validate.pitfall_cards.
  doc_command_module     a documented `python3 -B -m tools.x.y` or `python3 tools/x/y.py` command names a
                         module or script that does not exist.
  doc_command_flag       a documented command passes a `--flag` its module (or a tools module it imports,
                         one level deep, for the thin entry points that delegate their parser) never declares.
  doc_command_subcommand a documented command passes a first word its module's subcommands do not declare.
  doc_script_path        a document cites `tools/.../x.py|sh` that is not in the checkout.
  doc_test_reference     a document cites a test module (`tests.unit.test_x`, `tests/slow/test_x.py`, a bare
                         `test_x` on a `-m unittest` line whose PYTHONPATH lacks its directory), a test class or a test method that is not in
                         the checkout, or any other `tests/...` file path that does not exist.
  doc_calibration        docs/tools/WORKBENCH_COMPILE.md lacks the `Calibration status: N/M` line that
                         tools/release/test_queue.py parses, or M differs from the number of rows in the
                         wb_calibrate CORPUS.

Reads files only. The rule registries are imported from the live checkout, and only when the
checked root is that checkout; for any other root (unit tests) the registry checks are skipped
unless the caller passes the registries explicitly.
"""
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

RULE_ID = re.compile(r"\bHC-[A-Z]\d{3}\b")
# HC-P002 is deliberately unused (source-only configured float bounds are ambiguous);
# docs/PERFORMANCE_PRACTICES.md says so by name.
RESERVED_RULES = frozenset({"HC-P002"})
# Asset and animation lints carry HC-A ids in their source rather than in one RULES table.
ASSET_SOURCES = ("tools/validate/asset_lint.py", "tools/validate/anim_lint.py")
RULE_OWNERS = {"lint": "tools/validate/enforce_lint.py", "perf": "tools/validate/enforce_perf.py"}

CALIBRATION_DOC = "docs/tools/WORKBENCH_COMPILE.md"
CALIBRATION_LINE = re.compile(r"^Calibration status:\s*(\d+)\s*/\s*(\d+)\s*$", re.M)

FLAG = re.compile(r"(?<![\w-])(--[A-Za-z][\w-]*)")
MODULE_COMMAND = re.compile(r"-m (tools(?:\.\w+)+)")
SCRIPT_COMMAND = re.compile(r"\bpython3?\s+(?:-B\s+)?(tools/[\w/]+\.py)")
SCRIPT_PATH = re.compile(r"(?<![\w/.-])(tools/(?:[\w-]+/)*[\w-]+\.(?:py|sh))\b")
SUBCOMMAND = re.compile(r"[a-z][a-z0-9_-]*\Z")
FENCE = re.compile(r"^\s*(```|~~~)")
FLAG_FREE = frozenset({"--help"})

TEST_DOTTED = re.compile(r"(?<![\w./-])(tests(?:\.[A-Za-z_]\w*)+)")
TEST_PATH = re.compile(r"(?<![\w./-])(tests/(?:[\w-]+/)*[\w-]+\.(?:py|json|md))(?:::(\w+)(?:::(\w+))?)?")
UNITTEST_LINE = re.compile(r"-m unittest\b(?!\s+discover)")
BARE_TEST = re.compile(r"(?<![\w./:-])(test_\w+)((?:\.\w+){0,2})")
PYTHONPATH = re.compile(r"PYTHONPATH=(\S+)")


def _module_file(root, module):
    base = Path(root) / module.replace(".", "/")
    for candidate in (base.with_suffix(".py"), base / "__main__.py"):
        if candidate.is_file():
            return candidate
    return None


class _Surface:
    """Declared flags, subcommand words and whether a parser has subcommands, per module."""

    def __init__(self, root):
        self.root = Path(root)
        self._cache = {}

    def _own(self, path):
        if path in self._cache:
            return self._cache[path]
        words, imports, has_subparsers = set(), set(), False
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeError):
            tree = None
        for node in ast.walk(tree) if tree else ():
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) < 80:
                words.add(node.value)
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("tools"):
                imports.add(node.module)
                imports.update(node.module + "." + alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names if alias.name.startswith("tools"))
            elif isinstance(node, ast.Attribute) and node.attr == "add_parser":
                has_subparsers = True
        self._cache[path] = (words, imports, has_subparsers)
        return self._cache[path]

    def of(self, path):
        words, imports, has_subparsers = self._own(path)
        words = set(words)
        for name in imports:
            other = _module_file(self.root, name)
            if other:
                other_words, _, other_sub = self._own(other)
                words |= other_words
                has_subparsers = has_subparsers or other_sub
        flags = {word for word in words if re.fullmatch(r"--[A-Za-z][\w-]*", word)}
        return flags, words, has_subparsers


def _arguments(lines, index, start, in_fence):
    """The argument text of the command that starts at lines[index][start:]."""
    text = lines[index][start:]
    if in_fence:
        count = index
        while text.rstrip().endswith("\\") and count + 1 < len(lines):
            count += 1
            text = text.rstrip()[:-1] + " " + lines[count].strip()
        return re.split(r"\s\|\s|;|&&|\s#\s|\s2?>", text)[0]
    # Inline code: up to the closing backtick, which may be on a later line of the paragraph.
    count = index
    while "`" not in text and count + 1 < len(lines) and lines[count + 1].strip() and count - index < 3:
        count += 1
        text += " " + lines[count].strip()
    return text.split("`")[0]


def command_drift(root, documents):
    """(code, path, line) for every documented tools command that no longer matches its module."""
    surface = _Surface(root)
    findings = []
    for relative, text in sorted(documents.items()):
        lines = text.splitlines()
        in_fence = False
        for index, line in enumerate(lines):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            number = index + 1
            for match in SCRIPT_PATH.finditer(line):
                if not (Path(root) / match[1]).is_file():
                    findings.append(("doc_script_path", relative, number))
            commands = [(m[1], _module_file(root, m[1]), m.end()) for m in MODULE_COMMAND.finditer(line)]
            commands += [(m[1], Path(root) / m[1], m.end()) for m in SCRIPT_COMMAND.finditer(line)]
            for name, path, end in commands:
                if path is None or not path.is_file():
                    if not name.endswith(".py"):
                        findings.append(("doc_command_module", relative, number))
                    continue
                flags, words, has_subparsers = surface.of(path)
                arguments = _arguments(lines, index, end, in_fence)
                for flag in FLAG.findall(arguments):
                    if flag not in flags and flag not in FLAG_FREE:
                        findings.append(("doc_command_flag", relative, number))
                first = arguments.split()[0] if arguments.split() else ""
                if has_subparsers and SUBCOMMAND.match(first) and first not in words:
                    findings.append(("doc_command_subcommand", relative, number))
    return sorted(set(findings))


def _test_members(path):
    """{class name: {method names}} of a test module, read from source."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
        return {}
    return {node.name: {item.name for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
            for node in tree.body if isinstance(node, ast.ClassDef)}


def _member_missing(members, names):
    """True when a documented Class[.method] tail names a class or method the module does not define."""
    if not names:
        return False
    if names[0] not in members:
        return True
    return len(names) > 1 and names[1] not in members[names[0]]


def _dotted_missing(root, dotted):
    parts = dotted.split(".")
    for end in range(len(parts), 0, -1):
        base = Path(root).joinpath(*parts[:end])
        if base.with_suffix(".py").is_file():
            return _member_missing(_test_members(base.with_suffix(".py")), parts[end:])
        if base.is_dir() and end == len(parts):
            return False
    return True


def tests_drift(root, documents):
    """(code, path, line) for every documented test module, class, method or tests/ file that is gone."""
    findings = []
    for relative, text in sorted(documents.items()):
        if relative.startswith("tests/fixtures/"):
            continue  # synthetic inputs for the document linters, not claims about this tree
        for number, line in enumerate(text.splitlines(), 1):
            if any(_dotted_missing(root, m[1]) for m in TEST_DOTTED.finditer(line)):
                findings.append(("doc_test_reference", relative, number))
            for match in TEST_PATH.finditer(line):
                path = Path(root) / match[1]
                names = [name for name in match.groups()[1:] if name]
                if not path.is_file() or (path.suffix == ".py" and _member_missing(_test_members(path), names)):
                    findings.append(("doc_test_reference", relative, number))
            if UNITTEST_LINE.search(line):
                # A bare module name runs only from a directory the same line puts on PYTHONPATH.
                search = [part for found in PYTHONPATH.findall(line) for part in found.split(":") if part not in ("", ".")]
                for match in BARE_TEST.finditer(line):
                    paths = [Path(root) / folder / (match[1] + ".py") for folder in search]
                    found = [path for path in paths if path.is_file()]
                    tail = [name for name in match[2].split(".") if name]
                    if not found or _member_missing(_test_members(found[0]), tail):
                        findings.append(("doc_test_reference", relative, number))
    return sorted(set(findings))


def known_rules(root=ROOT):
    """(lint ids, perf ids, other ids) from the live rule tables of the checked-out tools."""
    from tools.validate import enforce_lint, enforce_perf
    other = set()
    for relative in ASSET_SOURCES:
        path = Path(root) / relative
        if path.is_file():
            other |= set(RULE_ID.findall(path.read_text(encoding="utf-8")))
    return set(enforce_lint.RULES), set(enforce_perf.RULES), other


def rule_drift(documents, lint, perf, other=frozenset()):
    """Rule ids cited by documents but undefined, and defined rules that no document cites."""
    known = set(lint) | set(perf) | set(other) | RESERVED_RULES
    cited, findings = set(), []
    for relative, text in sorted(documents.items()):
        for number, line in enumerate(text.splitlines(), 1):
            for rule in RULE_ID.findall(line):
                cited.add(rule)
                if rule not in known:
                    findings.append(("doc_rule_unknown", relative, number))
    for owner, rules in ((RULE_OWNERS["lint"], lint), (RULE_OWNERS["perf"], perf)):
        for rule in sorted(set(rules) - cited):
            findings.append(("rule_undocumented", owner, int(rule[-3:])))  # line = the rule number
    return sorted(set(findings))


def calibration_drift(documents, corpus_total):
    """The Workbench doc must carry the Calibration status line the test queue parses."""
    text = documents.get(CALIBRATION_DOC)
    if text is None:
        return []
    found = CALIBRATION_LINE.search(text)
    if not found:
        return [("doc_calibration", CALIBRATION_DOC, 0)]
    line = text.count("\n", 0, found.start()) + 1
    agreed, total = int(found[1]), int(found[2])
    if corpus_total is not None and (total != corpus_total or agreed > total):
        return [("doc_calibration", CALIBRATION_DOC, line)]
    return []


def corpus_total(root):
    """Rows in tools/release/wb_calibrate.CORPUS, read from source; None when unavailable."""
    path = Path(root) / "tools/release/wb_calibrate.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CORPUS" for t in node.targets):
            if isinstance(node.value, (ast.Tuple, ast.List)):
                return len(node.value.elts)
    return None


def check(root, documents):
    """Every drift finding for the checked root as (code, path, line)."""
    root = Path(root).absolute()
    findings = list(command_drift(root, documents))
    findings += tests_drift(root, documents)
    findings += calibration_drift(documents, corpus_total(root))
    if root == ROOT.absolute():
        lint, perf, other = known_rules(root)
        findings += rule_drift(documents, lint, perf, other)
    return sorted(set(findings))
