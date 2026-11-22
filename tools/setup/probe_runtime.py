"""Shared staging and lint runtime for the disposable native probes; never launches anything.

tools/setup/ce_probe.py and tools/setup/taped_light_probe.py both stage a fresh runtime from the
verified vanilla runtime, append a generated hook to a copy of the stock mission and write a
plan the Windows launcher (tools/setup/Start-CEProbeServer.ps1) re-verifies. Everything the two
stagers must agree on lives here so a hardening fix cannot land in only one of them:

* the Windows runtime-name rule, including trailing dot/space and reserved device aliases;
* hash-verified inputs read once, with symlinked/reparse inputs refused, and the exact verified
  inventory (not whatever is on disk later) staged, with the written bytes verified again;
* the Enforce compile-shape lint of the generated hook;
* the server constants, the exact launcher argument list and the common plan fields.

Nothing here proves how DayZ behaves. It only prepares files and refuses unsafe input.

New launch-free path, quoting, JSON-source and host-lease primitives live in
probe_core. Consumer migration is deferred: importing that library here also
requires updating the release bundle's explicit transitive-file inventory.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat

try:
    from . import diagnostic_mission as dm
except ImportError:  # executed as a script from tools/setup
    import diagnostic_mission as dm

SERVER_EXE = r"D:\SteamLibrary\steamapps\common\DayZServer\DayZServer_x64.exe"
SERVER_INSTALL = r"D:\SteamLibrary\steamapps\common\DayZServer"
SERVER_EXE_SHA256 = "987fbc47bab1dab37f74d7f700aa2e5b6af936a7181a62f5ba9f0090aebba805"
BATTLEYE_SHA256 = "224ab091fd806245ac4f0c3ec896f45f4682ae97ebef599ea546a1bbe37531bc"
WINDOWS_PARENT = r"D:\HollowCountryLocal"
WSL_PARENT = Path("/mnt/d/HollowCountryLocal")
VERIFIED_RUNTIME_NAME = "vanilla-p0-001"
DEFAULT_SOURCE_RUNTIME = "/mnt/d/HollowCountryLocal/vanilla-p0-001"
MISSION_NAME = "dayzOffline.chernarusplus"
PORT = 2302
MAX_PLAN_BYTES = 1024 * 1024
MAX_HELD_BYTES = 16 * 1024 * 1024
MAX_CONFIG_BYTES = 1024 * 1024
MAX_BATTLEYE_BYTES = 64 * 1024 * 1024
# The last character may not be a dot (Windows silently strips trailing dots and spaces, so
# `vanilla-p0-001.` would name the verified runtime). Mirrored in Start-CEProbeServer.ps1.
NAME_RULE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9_-])?$")
IDENT_RULE = re.compile(r"^[A-Za-z0-9_]{1,64}$")
# Win32 device names stay reserved with any extension and any case (CON.txt, nul.log).
RESERVED_DEVICE = re.compile(r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$", re.I)
# Stock files whose launch-plan pin is the verified runtime's scheduled-shutdown delta,
# not the stock bytes. They are recorded with their stock hash, never silently accepted.
PLAN_PIN_DELTAS = frozenset({"db/messages.xml"})


def sha256(data):
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Bounded, link-refusing file access
# ---------------------------------------------------------------------------


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _open_regular(path):
    """Open a regular file for reading; no component of the path, leaf included, is followed as a symlink.

    The path is walked from "/" on directory descriptors (dm.open_file_at), so a directory swapped for a
    symlink between the earlier lstat checks and this open is refused by the kernel in this call.
    """
    try:
        descriptor = dm.open_file_at(path, os.O_RDONLY)
    except ValueError as error:
        raise ValueError(f"symlinked input refused: {path}") from error
    except OSError as error:
        if os.path.islink(path):
            raise ValueError(f"symlinked input refused: {path}") from error
        raise
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"regular file required: {path}")
        return os.fdopen(descriptor, "rb"), info
    except BaseException:
        os.close(descriptor)
        raise


def _read_bounded(path, limit):
    return read_identified(path, limit)[0]


def read_identified(path, limit):
    """Return (bytes, identity) of one regular non-symlink file read within its byte budget."""
    stream, info = _open_regular(path)
    with stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{path} exceeds its byte budget")
    return data, _identity(info)


def _hash_file(path):
    digest = hashlib.sha256()
    size = 0
    stream, _info = _open_regular(path)
    with stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def new_file(path, data):
    """Create a new file (O_EXCL) under a no-follow directory walk; never writes through a link."""
    dm.create_exclusive(path, data)


_new_file = new_file


def refuse_links(base, *relative_parts):
    """Refuse a symlink at base or at any component below it (lstat, never following)."""
    base = Path(base)
    if base.is_symlink():
        raise ValueError(f"symlinked input refused: {base}")
    for part in relative_parts:
        current = base
        for piece in Path(part).parts:
            current = current / piece
            if current.is_symlink():
                raise ValueError(f"symlinked input refused: {current}")


# ---------------------------------------------------------------------------
# Enforce compile-shape lint (rules observed in native compiles 066-072)
# ---------------------------------------------------------------------------

# Engine class names visible to authored mission code (same pins as test_script_identifiers).
ENGINE_TYPE_NAMES = frozenset({
    "Mission", "Game", "World", "Weather", "Object", "Man", "Camera", "Hive", "Widget", "Param", "Class",
    "Managed", "Entity", "Human", "Car", "Transport", "Building", "Effect", "Particle", "Material", "Shape",
    "Timer", "Input", "CGame", "CargoBase", "ItemBase", "EntityAI", "Math", "Print",
})
RESERVED_WORDS = frozenset({
    "local", "ref", "autoptr", "owned", "notnull", "out", "inout", "static", "const", "private", "protected",
    "override", "modded", "sealed", "proto", "native", "external", "volatile", "event", "thread", "typename",
    "class", "enum", "typedef", "new", "delete", "this", "super", "null", "NULL", "true", "false", "void",
    "int", "float", "bool", "string", "vector", "auto", "if", "else", "for", "foreach", "while", "do",
    "switch", "case", "default", "break", "continue", "return", "array", "map", "set",
})
_MODIFIERS = r"(?:(?:ref|autoptr|static|protected|private|const|owned|notnull|out|inout)\s+)*"
_DECLARATION = re.compile(
    r"(?:^[ \t]*|[({;,][ \t]*)" + _MODIFIERS + r"([A-Za-z_]\w*(?:<[^;()=]*?>)?)[ \t]+([A-Za-z_]\w*)[ \t]*(?=[;=,)\[])", re.M)
_NOT_TYPES = frozenset({"return", "new", "class", "typename", "modded", "override", "delete", "else", "case"})
# A method header at any indentation, with the opening brace on its own line or on the header line.
# `else if (...) {` is the one control-flow shape that looks like `type name(...)`, so it is excluded.
_FUNCTION = re.compile(
    r"^[ \t]*((?:(?:override|static|protected|private|ref|autoptr|owned|notnull)[ \t]+)*)"
    r"(?!(?:else|return|new|delete|case)\b)[\w<>]+[ \t]+"
    r"(?!(?:if|while|for|foreach|switch)\b)(\w+)[ \t]*\(([^()]*)\)\s*\{", re.M)
_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')
_EXPONENT = re.compile(r"\b\d+(?:\.\d+)?[eE][+-]?\d+\b")
# (callee, positions of arguments that are `out` parameters and must be declared first); the union
# of what the CE hook and the taped-light hook call, so one lint covers both generated hooks.
_OUT_CALLS = (("GetObjectsAtPosition3D", (2, 3)), ("ClippingInfo", (0,)), ("GetCollisionBox", (0,)),
              ("GetSelectionForSlotId", (1,)), ("GetBoneNameForSlotId", (1,)), ("GetSelectionList", (0,)),
              ("GetLODS", (0,)), ("GetSelections", (0,)), ("ConfigGetChildName", (2,)))

# Native compile evidence for the expression limits below. A real DayZServer 1.30.164289 run refused
# the generated taped-light init.c with `Formula too complex` and `Incompatible parameter 'slot'` on
# one row built from about 27 '+' operators that also concatenated a bare int; 22 '+' on one line
# failed later in the same file. The ce-probe-001 hook compiled and ran natively: its longest
# statement has 9 '+'. (That hook does concatenate bare ints in places, e.g. Print("n=" + list.Count()),
# so a bare number is not proven to be a compile error by itself; explicit_numbers is a precaution.)
# The bound is that observed maximum.
MAX_STATEMENT_PLUS = 9
HOOK_EXPRESSION_EVIDENCE = (
    "DayZServer 1.30.164289 refused a generated hook with 'Formula too complex' and "
    "'Incompatible parameter' on a statement of about 27 binary '+' operators that concatenated "
    "a bare int; the ce-probe-001 hook (max 9 per statement) compiled and ran natively.")
_NUMERIC_TYPES = frozenset({"int", "float", "bool"})
_NUMERIC_LITERAL = re.compile(r"^-?\d+(?:\.\d+)?$")
_CALL_TERM = re.compile(r"^(\w+)\s*\(.*\)$", re.S)
_NUMERIC_METHOD = re.compile(r"\.(?:Count|Length|IndexOf|GetTime)\s*\([^()]*\)$", re.S)
_FUNCTION_RETURN = re.compile(
    r"^[ \t]*(?:(?:override|static|protected|private|ref|autoptr|owned|notnull)[ \t]+)*([\w<>]+)[ \t]+(\w+)[ \t]*\(", re.M)


def _clean(text):
    """Return text with comments removed and string literal contents blanked."""
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    lines = []
    for line in text.splitlines():
        stripped = _STRING.sub('""', line)
        lines.append(stripped.split("//")[0])
    return "\n".join(lines)


def _split_arguments(text):
    args, depth, current = [], 0, []
    for char in text:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        if char == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    args.append("".join(current).strip())
    return args


def _parameter_names(text):
    names = []
    for parameter in filter(None, (p.strip() for p in text.split(","))):
        parameter = parameter.split("=")[0].strip()
        match = re.search(r"([A-Za-z_]\w*)\s*(?:\[\s*\d*\s*\])?$", parameter)
        if not match or len(parameter.split()) < 2:
            return None
        names.append(match.group(1))
    return tuple(names)


def _function_bodies(clean):
    for match in _FUNCTION.finditer(clean):
        start = match.end() - 1
        depth = 0
        for position in range(start, len(clean)):
            if clean[position] == "{":
                depth += 1
            elif clean[position] == "}":
                depth -= 1
                if depth == 0:
                    yield match, clean[start:position + 1], start
                    break


def _plus_count(statement):
    """Binary '+' operators of one statement; '++' and '+=' are not concatenation terms."""
    return re.sub(r"\+\+|\+=", "", statement).count("+")


def _statements(clean):
    """Yield (line, text) for each statement of comment-free, string-blanked text."""
    position = 0
    for match in re.finditer(r"[;{}]", clean):
        text = clean[position:match.start()]
        if text.strip():
            offset = position + len(text) - len(text.lstrip())
            yield clean.count("\n", 0, offset) + 1, text
        position = match.end()


def max_statement_plus(text):
    """The largest number of binary '+' operators in any one statement of a hook text."""
    return max((_plus_count(statement) for _line, statement in _statements(_clean(text))), default=0)


def _top_level_terms(expression):
    terms, depth, current = [], 0, []
    for index, char in enumerate(expression):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        plus = (char == "+" and depth == 0 and expression[index + 1:index + 2] not in ("+", "=")
                and expression[index - 1:index] != "+")
        if plus:
            terms.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    terms.append("".join(current).strip())
    return terms


def _after_assignment(term):
    depth = 0
    for index, char in enumerate(term):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif (char == "=" and depth == 0 and term[index - 1:index] not in ("=", "!", "<", ">", "+", "-", "*", "/")
              and term[index + 1:index + 2] != "="):
            return term[index + 1:].strip()
    return re.sub(r"^return\b\s*", "", term)


def _segments(expression):
    yield expression
    depth, start = 0, 0
    for index, char in enumerate(expression):
        if char in "([":
            if depth == 0:
                start = index + 1
            depth += 1
        elif char in ")]":
            depth -= 1
            if depth == 0:
                for argument in _split_arguments(expression[start:index]):
                    yield from _segments(argument)


def _unwrap(term):
    """Drop parentheses that enclose the whole term: `((count))` is `count`."""
    while term.startswith("(") and term.endswith(")"):
        depth = 0
        for index, char in enumerate(term):
            depth += {"(": 1, ")": -1}.get(char, 0)
            if depth == 0 and index < len(term) - 1:
                return term
        term = term[1:-1].strip()
    return term


def _operands(expression):
    """Operands of an arithmetic expression, split at its top-level + - * / % operators."""
    operands, depth, current = [], 0, []
    for char in expression:
        depth += {"(": 1, "[": 1, ")": -1, "]": -1}.get(char, 0)
        if depth == 0 and char in "+-*/%":
            operands.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    operands.append("".join(current).strip())
    return [operand for operand in operands if operand]


def _compound_destination(statement):
    """(destination, right-hand side) of a top-level `name += expression` statement, else None."""
    depth = 0
    for index, char in enumerate(statement):
        depth += {"(": 1, "[": 1, ")": -1, "]": -1}.get(char, 0)
        if depth == 0 and statement[index:index + 2] == "+=":
            destination = statement[:index].strip()
            return (destination, statement[index + 2:].strip()) if re.match(r"^[A-Za-z_]\w*$", destination) else None
    return None


def _concatenation_issues(line, statement, numeric, strings, string_functions, numeric_functions, vectors=()):
    issues = []

    def stringy(term):
        term = _unwrap(term)
        call = _CALL_TERM.match(term)
        return (term == '""' or term in strings or term.endswith(".ToString()")
                or bool(call and call.group(1) in string_functions))

    def numeric_term(term):
        term = _unwrap(term)
        if term.endswith(".ToString()"):
            return False
        call = _CALL_TERM.match(term)
        indexed = re.match(r"^(\w+)\[[^\]]*\]$", term)
        if (term in numeric or bool(_NUMERIC_LITERAL.match(term)) or bool(indexed and indexed.group(1) in vectors)
                or bool(call and call.group(1) in numeric_functions) or bool(_NUMERIC_METHOD.search(term))):
            return True
        operands = _operands(term)  # a parenthesised arithmetic expression such as (count + 1) or (ratio * 2)
        return (len(operands) > 1 and not any(stringy(o) for o in operands) and any(numeric_term(o) for o in operands))

    for index, segment in enumerate(_segments(statement)):
        into_string = False
        if index == 0 and _compound_destination(segment):
            destination, segment = _compound_destination(segment)
            into_string = destination in strings
            terms = _top_level_terms(segment)
        else:
            terms = _top_level_terms(segment)
            if len(terms) < 2:
                continue
            if index == 0:
                terms[0] = _after_assignment(terms[0])
        if into_string or any(stringy(term) for term in terms):
            for term in terms:
                if numeric_term(term):
                    issues.append(f"line {line}: bare numeric '{term}' concatenated into a string "
                                  "(use an explicit .ToString())")
    return issues


def _expression_issues(clean, explicit_numbers=False):
    """Statement-size and bare-number concatenation findings for comment-free, string-blanked text.

    The size bound needs no scope, so it covers every statement of the text whatever the layout of the
    enclosing method (inline braces, any indentation, or no method at all). The numeric rule needs the
    declared names of each recognised method body.
    """
    issues = []
    for line, statement in _statements(clean):
        count = _plus_count(statement)
        if count > MAX_STATEMENT_PLUS:
            issues.append(f"line {line}: statement has {count} binary '+' operators (limit {MAX_STATEMENT_PLUS}); "
                          "the native compiler reports 'Formula too complex' (" + HOOK_EXPRESSION_EVIDENCE + ")")
    bodies = list(_function_bodies(clean))
    spans = [(start, start + len(body)) for _header, body, start in bodies]
    members = set()
    strings_global = set()
    vectors = set()
    for match in _DECLARATION.finditer(clean):
        if any(low <= match.start(2) < high for low, high in spans) or match.group(1) in _NOT_TYPES:
            continue
        (members if match.group(1) in _NUMERIC_TYPES else strings_global if match.group(1) == "string"
         else vectors if match.group(1) == "vector" else set()).add(match.group(2))
    string_functions, numeric_functions = set(), set()
    for match in _FUNCTION_RETURN.finditer(clean):
        if match.group(1) == "string":
            string_functions.add(match.group(2))
        elif match.group(1) in _NUMERIC_TYPES:
            numeric_functions.add(match.group(2))
    for header, body, start in bodies:
        numeric, strings = set(members), set(strings_global)
        local_vectors = set(vectors)
        for match in _DECLARATION.finditer("(" + header.group(3) + ")"):
            (numeric if match.group(1) in _NUMERIC_TYPES else local_vectors if match.group(1) == "vector"
             else strings).add(match.group(2))
        for match in _DECLARATION.finditer(body):
            if match.group(1) in _NOT_TYPES:
                continue
            (numeric if match.group(1) in _NUMERIC_TYPES else local_vectors if match.group(1) == "vector"
             else strings).add(match.group(2))
        if explicit_numbers:
            for line, statement in _statements(body):
                issues.extend(_concatenation_issues(line + clean.count("\n", 0, start), statement, numeric, strings,
                                                    string_functions, numeric_functions, local_vectors))
    return issues


def native_type_names(cache):
    """Class/enum names declared anywhere in an extracted native script cache."""
    names = set()
    for layer in ("1_Core", "2_GameLib", "3_Game", "4_World", "5_Mission"):
        for source in (Path(cache) / layer).rglob("*.c"):
            text = source.read_text(encoding="utf-8", errors="replace")
            names.update(re.findall(r"^(?:modded\s+|sealed\s+)?(?:class|enum)\s+(\w+)", text, re.M))
    return frozenset(names)


def lint_hook(text, native_types=frozenset(), prototypes=None, explicit_numbers=False):
    """Return a list of issues; empty means no observed-rejected shape was found.

    Besides the declaration/scope shapes, it refuses the two expression shapes a real DayZServer
    1.30.164289 compile rejected ("Formula too complex" / "Incompatible parameter" on a ~27 '+' row
    that concatenated a bare int): a statement with more than MAX_STATEMENT_PLUS (9, the maximum
    of the ce-probe-001 hook that compiled natively) binary '+' operators, always; and, with
    explicit_numbers=True, a bare int, float or bool concatenated into a string instead of through
    an explicit .ToString(). The ce-probe-001 hook compiled natively while concatenating bare
    ints (for example `"targets=" + list.Count()`), so that second rule is not proven necessary;
    only the taped-light stager enables it, as a precaution, and the CE stager keeps its bytes.
    """
    issues = []
    for number, line in enumerate(text.splitlines(), 1):
        for literal in _STRING.findall(line):
            if "//" in literal or "/*" in literal:
                issues.append(f"line {number}: comment marker inside a string literal")
            if '\\"' in literal.replace('\\\\', ''):
                issues.append(f"line {number}: escaped quote inside a string literal")
    clean = _clean(text)
    for number, line in enumerate(clean.splitlines(), 1):
        if "?" in line:
            issues.append(f"line {number}: ternary operator is not accepted by the native compiler")
        if re.match(r"^\s*(\|\||&&)", line):
            issues.append(f"line {number}: condition continuation with leading operator")
        if _EXPONENT.search(line):
            issues.append(f"line {number}: exponent float literal (use FLT_MAX)")
    issues.extend(_expression_issues(clean, explicit_numbers))
    forbidden = set(ENGINE_TYPE_NAMES) | set(native_types)
    for match in _DECLARATION.finditer(clean):
        kind, name = match.groups()
        if kind in _NOT_TYPES:
            continue
        line = clean.count("\n", 0, match.start(2)) + 1
        if name in RESERVED_WORDS:
            issues.append(f"line {line}: reserved word '{name}' used as an identifier")
        if name in forbidden:
            issues.append(f"line {line}: identifier '{name}' equals an engine type name")
    for header, body, start in _function_bodies(clean):
        function = header.group(2)
        names = list(_parameter_names(header.group(3)) or ())
        declared = []
        for match in _DECLARATION.finditer(body):
            if match.group(1) in _NOT_TYPES:
                continue
            names.append(match.group(2))
            declared.append((match.start(2), match.group(2)))
        seen = set()
        for name in names:
            if name in seen:
                issues.append(f"{function}: duplicate local '{name}' (Enforce shares one scope per function)")
            seen.add(name)
        for callee, positions in _OUT_CALLS:
            for call in re.finditer(r"\b%s\s*\(" % callee, body):
                end, depth = call.end(), 1
                while end < len(body) and depth:
                    depth += {"(": 1, ")": -1}.get(body[end], 0)
                    end += 1
                args = _split_arguments(body[call.end():end - 1])
                for position in positions:
                    name = args[position] if position < len(args) else ""
                    if not re.match(r"^[A-Za-z_]\w*$", name) or not any(
                            n == name and offset < call.start() for offset, n in declared):
                        issues.append(f"{function}: out argument '{name}' of {callee} must be declared before the call")
    if prototypes:
        for match in re.finditer(r"\boverride\b[^(;{}]*?\b([A-Za-z_]\w*)\s*\(([^()]*)\)", clean):
            name, names = match.group(1), _parameter_names(match.group(2))
            candidates = {p for p in prototypes.get(name, ()) if names is not None and len(p) == len(names)}
            if candidates and names not in candidates:
                issues.append(f"override {name}{names} does not match engine prototype {sorted(candidates)}")
    return issues


def _safe_plan_path(value):
    if (not isinstance(value, str) or not value or value.startswith("/") or "\\" in value or ":" in value
            or ".." in value.split("/")):
        raise ValueError("unsafe mission manifest path")
    return value


# Only these stock mission shapes may be copied into the disposable runtime. Anything else,
# listed in the launch plan or not, is refused rather than silently staged.
SENSITIVE_PART = re.compile(
    r"(?i)^(?:keys?|profiles?|storage|players?|saves?|credentials?|secrets?|battleye|logs?|backups?)$"
    r"|\.(?:biprivatekey|bikey|bisign|vars|pem|key|pfx|p12|pub|crt|sqlite|db|sav|log|rpt|adm|mdmp|cfg|bin|dll|exe|ps1|bat|cmd|sh)$"
    r"|(?i:credential|password|secret|token|private)")
ALLOWED_MISSION_DIRS = frozenset({"db", "env"})
ALLOWED_MISSION_FILE = re.compile(r"^(?:(?:db|env)/)?[A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:xml|json|map|c)$")


def _check_mission_entry(relative, *, directory=False):
    """Refuse sensitive or unvalidated mission content regardless of any manifest."""
    name = relative.as_posix()
    for part in relative.parts:
        if SENSITIVE_PART.search(part):
            raise ValueError(f"sensitive or unvalidated mission path refused: {name}")
    if directory:
        if name not in ALLOWED_MISSION_DIRS:
            raise ValueError(f"unvalidated mission directory refused: {name}")
    elif not ALLOWED_MISSION_FILE.match(name):
        raise ValueError(f"unvalidated mission file refused: {name}")


# ---------------------------------------------------------------------------
# Windows runtime root
# ---------------------------------------------------------------------------


def plain_runtime_name(name):
    """The launcher's plain-name rule: NAME_RULE and no consecutive dots.

    Start-CEProbeServer.ps1 refuses ``..`` anywhere in the runtime path (``$root -match '\\.\\.'``), so a name
    such as ``a..b`` that NAME_RULE alone accepts would be staged and then refused at launch; refuse it here.
    """
    return bool(NAME_RULE.fullmatch(name)) and ".." not in name


def windows_normalized_name(name):
    """The name Windows resolves: trailing dots and spaces are stripped, case is ignored."""
    return name.rstrip(" .").casefold()


def windows_runtime_root(path, wsl_parent=None):
    """Map a direct child of the probe parent to its Windows runtime root, or raise.

    Refused: names that Windows normalizes onto the verified runtime (trailing dot/space, case)
    and reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9, with or without extension).
    """
    path = Path(path)
    parent = Path(WSL_PARENT if wsl_parent is None else wsl_parent)
    if path.parent != parent or not plain_runtime_name(path.name):
        raise ValueError(f"destination must be a new direct child of {parent} with a plain name")
    if RESERVED_DEVICE.match(path.name):
        raise ValueError("reserved Windows device names are refused")
    if windows_normalized_name(path.name) == VERIFIED_RUNTIME_NAME.casefold():
        raise ValueError("the verified runtime must not be reused")
    root = WINDOWS_PARENT + "\\" + path.name
    parts = PureWindowsPath(root)
    if str(parts.parent) != WINDOWS_PARENT or parts.name != path.name:
        raise ValueError("Windows runtime root must be one named child of " + WINDOWS_PARENT)
    return str(parts)


def server_arguments(windows_root, mods=None):
    """The exact argument list Start-CEProbeServer.ps1 requires (including battleye and logs)."""
    mission = f"{windows_root}\\mpmissions\\{MISSION_NAME}"
    arguments = ["-ip=127.0.0.1", f"-port={PORT}", f"-config={windows_root}\\serverDZ.cfg", f"-mission={mission}",
            f"-storage={windows_root}\\storage", f"-profiles={windows_root}\\profiles",
            f"-BEpath={windows_root}\\battleye", "-doLogs", "-adminLog"]
    if mods:
        validate_mods(mods)
        arguments.extend(key + "=" + ";".join(row["path"] for row in rows)
                         for key, rows in mods.items())
    return arguments


def validate_mods(mods, verify=False):
    """Admit only pinned friend-install mod directories; never copy their content."""
    if not isinstance(mods, dict) or not mods or set(mods) - {'-mod', '-serverMod'}:
        raise ValueError('invalid optional mod list')
    seen = set()
    for rows in mods.values():
        if not isinstance(rows, list) or not rows:
            raise ValueError('empty optional mod switch')
        for row in rows:
            path = row['path']
            prefix = 'E:\\HollowCountryLocal\\friend-local-1\\'
            leaf = path[len(prefix):] if path.startswith(prefix) else ''
            if not re.fullmatch(r'@[A-Za-z0-9_-]+', leaf) or path.casefold() in seen:
                raise ValueError('mod must be a unique installed friend directory')
            seen.add(path.casefold())
            pbos = row['pbos']
            if not isinstance(pbos, list) or not pbos or len(pbos) > 4096:
                raise ValueError('invalid PBO inventory')
            listed = set()
            for entry in pbos:
                name = entry['path']
                if (not re.fullmatch(r'[A-Za-z0-9_./ -]+\.pbo', name, re.I)
                        or name.startswith('/') or '..' in name.split('/')
                        or name.casefold() in listed or not re.fullmatch('[a-f0-9]{64}', entry['sha256'])):
                    raise ValueError('invalid PBO pin')
                listed.add(name.casefold())
            if verify:
                root = Path('/mnt/e/HollowCountryLocal/friend-local-1') / leaf
                actual = {n.casefold(): n for n in dm.walk_plain(root) if n.lower().endswith('.pbo')}
                if set(actual) != listed:
                    raise ValueError('mod PBO inventory drift')
                for entry in pbos:
                    if _hash_file(root / actual[entry['path'].casefold()])[0] != entry['sha256']:
                        raise ValueError('mod PBO hash drift')


# ---------------------------------------------------------------------------
# Source verification
# ---------------------------------------------------------------------------


def verify_source(source_runtime, battleye_sha256, *, hold=()):
    """Verify the vanilla runtime once and return the admitted inventory and held bytes.

    Config, BattlEye DLL, launch plan and the files named in ``hold`` are read exactly once
    through no-follow descriptors; later stages write these verified bytes, never a re-read.
    """
    source_runtime = Path(source_runtime)
    stock = Path("stock-backup/mpmissions") / MISSION_NAME
    refuse_links(source_runtime, stock, "launch-plan.json", "serverDZ.cfg", "battleye/BEServer_x64.dll")
    mission = source_runtime / stock
    if not mission.is_dir():
        raise ValueError("stock-backup mission directory required in the source runtime")
    plan_path = source_runtime / "launch-plan.json"
    plan_bytes, plan_identity = read_identified(plan_path, MAX_PLAN_BYTES)
    launch_plan = json.loads(plan_bytes)
    if not isinstance(launch_plan, dict):
        raise ValueError("launch plan must be a JSON object")
    entries = launch_plan.get("mission_files", [])
    if not isinstance(entries, list):
        raise ValueError("launch plan mission_files must be a list")
    pinned = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("malformed launch-plan mission entry")
        path = _safe_plan_path(entry.get("path"))
        _check_mission_entry(Path(path))
        if path in pinned or not re.match(r"^[a-f0-9]{64}$", str(entry.get("sha256"))):
            raise ValueError("duplicate or malformed launch-plan mission entry")
        pinned[path] = entry["sha256"]
    files, directories, _total = dm._inventory(mission)
    for relative in directories:
        _check_mission_entry(relative, directory=True)
    for relative, _info in files:
        _check_mission_entry(relative)
    records, held, admitted = {}, {}, {}
    for relative, _info in files:
        name = relative.as_posix()
        if name in hold:
            data, _identity_unused = read_identified(mission / relative, MAX_HELD_BYTES)
            held[name] = data
            digest, size = sha256(data), len(data)
        else:
            digest, size = _hash_file(mission / relative)
        if name not in pinned:
            status = "absent-from-launch-plan-recorded"
        elif pinned[name] == digest:
            status = "match"
        elif name in PLAN_PIN_DELTAS:
            status = "differs-from-launch-plan-recorded"
        else:
            raise ValueError(f"stock mission file differs from launch plan: {name}")
        records[name] = {"path": name, "source_sha256": digest, "bytes": size, "plan_hash_status": status}
        admitted[name] = (digest, size)
    missing = sorted(set(pinned) - set(records))
    if missing:
        raise ValueError(f"launch plan lists files absent from the stock mission: {missing[:3]}")
    config = source_runtime / "serverDZ.cfg"
    config_bytes, config_identity = read_identified(config, MAX_CONFIG_BYTES)
    if sha256(config_bytes) != launch_plan.get("config_sha256"):
        raise ValueError("serverDZ.cfg does not match the launch plan hash")
    battleye = source_runtime / "battleye/BEServer_x64.dll"
    battleye_bytes, battleye_identity = read_identified(battleye, MAX_BATTLEYE_BYTES)
    if sha256(battleye_bytes) != battleye_sha256:
        raise ValueError("BEServer_x64.dll does not match the pinned hash")
    for name in hold:
        if name not in held:
            raise ValueError(f"stock mission lacks {name}")
    return {"mission": mission, "records": records, "held": held, "config": config, "battleye": battleye,
            "config_bytes": config_bytes, "battleye_bytes": battleye_bytes,
            "launch_plan_sha256": sha256(plan_bytes),
            "admitted": {"files": admitted, "directories": sorted(d.as_posix() for d in directories)},
            "identities": {plan_path: plan_identity, config: config_identity, battleye: battleye_identity}}


_verify_source = verify_source


def check_unchanged(source):
    """Refuse when a verified single-read input was replaced or modified since verification."""
    for path, identity in source["identities"].items():
        try:
            info = dm.lstat_at(path)
        except (OSError, ValueError) as error:
            raise ValueError(f"source changed during staging: {path.name}") from error
        if not stat.S_ISREG(info.st_mode) or _identity(info) != identity:
            raise ValueError(f"source changed during staging: {path.name}")


# ---------------------------------------------------------------------------
# Staging skeleton
# ---------------------------------------------------------------------------


def begin(source_runtime, destination, *, parent, battleye_sha256, hold=()):
    """Validate destination and source; creates nothing. Returns the staging context."""
    source_runtime, destination = dm._safe_path(source_runtime), dm._safe_path(destination)
    if source_runtime == destination or source_runtime in destination.parents or destination in source_runtime.parents:
        raise ValueError("source/destination overlap forbidden")
    if destination.exists() or destination.is_symlink():
        raise ValueError("destination must be fresh; no overwrite")
    parent = Path(parent)
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError(f"probe parent directory {parent} must exist and not be a symlink")
    windows_root = windows_runtime_root(destination, parent)
    source = verify_source(source_runtime, battleye_sha256, hold=hold)
    return {"source_runtime": source_runtime, "destination": destination, "windows_root": windows_root,
            "source": source, "battleye_sha256": battleye_sha256}


def _is_empty_directory(path):
    descriptor = dm.open_dir_at(path)
    try:
        with os.scandir(descriptor) as scan:
            return next(scan, None) is None
    finally:
        os.close(descriptor)


def _write_verified(path, data):
    new_file(path, data)
    digest, size = _hash_file(path)
    if digest != sha256(data) or size != len(data):
        raise ValueError(f"written bytes differ from the admitted bytes: {Path(path).name}")


def build_runtime(context, hook, *, purpose, replacements=None):
    """Create the runtime from the exact admitted inventory and verify what was written."""
    replacements = dict(replacements or {})
    destination, source = context["destination"], context["source"]
    for name in replacements:
        if name not in source["records"]:
            raise ValueError(f"replacement target absent from the stock mission: {name}")
    check_unchanged(source)
    mission_dest = destination / "mpmissions" / MISSION_NAME
    manifest = dm.prepare_diagnostic_mission(source["mission"], mission_dest, purpose=purpose, hook=hook,
                                             admitted=source["admitted"], entry_check=_check_mission_entry)
    for name in ("storage", "profiles", "battleye"):
        dm.mkdir_at(destination / name)
    _write_verified(destination / "serverDZ.cfg", source["config_bytes"])
    _write_verified(destination / "battleye/BEServer_x64.dll", source["battleye_bytes"])
    for name, data in sorted(replacements.items()):
        dm.unlink_at(mission_dest / name)
        _write_verified(mission_dest / name, data)
    check_unchanged(source)

    prefix = f"mpmissions/{MISSION_NAME}/"
    expected = {"serverDZ.cfg": sha256(source["config_bytes"]),
                "battleye/BEServer_x64.dll": sha256(source["battleye_bytes"])}
    for name, entry in manifest["files"].items():
        expected[prefix + name] = entry["staged_sha256"]
    for name, data in replacements.items():
        expected[prefix + name] = sha256(data)
    marker = prefix + dm.MARKER_NAME
    on_disk = dm.walk_plain(destination)       # lstat-walk backstop: refuses any link or special file
    staged = []
    for name in sorted(on_disk):
        digest, size = _hash_file(destination / name)
        if name != marker and expected.get(name) != digest:
            raise ValueError(f"unexpected or altered staged file: {name}")
        staged.append({"path": name, "sha256": digest, "bytes": size})
    if {entry["path"] for entry in staged} != set(expected) | {marker}:
        raise ValueError("staged inventory differs from the admitted inventory")
    for name in ("storage", "profiles"):
        if not _is_empty_directory(destination / name):
            raise ValueError(f"{name} must start empty")
    staged_hash = {entry["path"]: entry["sha256"] for entry in staged}
    mission_files = []
    for name, record in sorted(source["records"].items()):
        entry = dict(record)
        entry["sha256"] = staged_hash[prefix + name]
        if manifest["files"][name]["source_sha256"] != record["source_sha256"]:
            raise ValueError(f"source changed while staging: {name}")
        if name == "init.c":
            entry["origin"] = "instrumented"
        elif name in replacements:
            entry["origin"] = "treatment-replacement"
        else:
            if entry["sha256"] != record["source_sha256"]:
                raise ValueError(f"staged copy differs from the admitted source: {name}")
            entry["origin"] = "stock-copy"
        mission_files.append(entry)
    return {"manifest": manifest, "mission_dest": mission_dest, "staged": staged, "staged_hash": staged_hash,
            "mission_files": mission_files}


def plan_header(kind, now, *, before=None, after=None):
    """Leading plan fields; ``before`` precedes and ``after`` follows the staged timestamp."""
    header = {"schema_version": 1, "kind": kind, "status": "staged-only-not-launched"}
    header.update(before or {})
    header["staged_utc"] = (now or datetime.datetime.now(datetime.timezone.utc)).isoformat()
    header.update(after or {})
    return header


def plan_runtime_fields(context, built, mods=None):
    """Server, paths, exact arguments and source provenance shared by every probe plan."""
    root = context["windows_root"]
    mission = f"{root}\\mpmissions\\{MISSION_NAME}"
    fields = {
        "server_exe": SERVER_EXE, "server_exe_sha256": SERVER_EXE_SHA256, "working_directory": SERVER_INSTALL,
        "port": PORT, "requested_bind": f"127.0.0.1:{PORT}",
        "runtime_root": root, "mission": mission,
        "storage": root + "\\storage", "profiles": root + "\\profiles", "battleye": root + "\\battleye",
        "arguments": server_arguments(root, mods),
        "source": {"runtime_wsl_path": str(context["source_runtime"]),
                   "launch_plan_sha256": context["source"]["launch_plan_sha256"],
                   "config_sha256": built["staged_hash"]["serverDZ.cfg"],
                   "battleye_sha256": context["battleye_sha256"]},
    }

    if mods:
        fields["mods"] = mods
    return fields


# What the launcher fixes per probe kind; nothing is read from the plan to choose these.
LAUNCHER_PROBES = {"ce-fill-probe": ("ce-fill-probe-plan.json", "HCCEFillProbe", "complete.txt"),
                   "ce-probe": ("ce-probe-plan.json", "HCCEProbe", "census.json"),
                   "taped-light-probe": ("taped-light-probe-plan.json", "HCTapedLightProbe", "observations.json"),
                   "weather-probe": ("weather-probe-plan.json", "HCWeatherProbe", "observations.json"),
                   "interior-sampler": ("interior-sampler-plan.json", "HCInteriorSampler", "census.json"),
                   "infected-competence-probe": ("infected-competence-probe-plan.json", "HCInfectedCompetence",
                                                 "observations.json")}


def launcher_problems(plan, destination, plan_name):
    """Re-run the launcher's plan checks (see Start-CEProbeServer.ps1) on a staged plan."""
    problems = []
    kind = plan.get("kind")
    root = plan.get("runtime_root", "")
    if kind not in LAUNCHER_PROBES or LAUNCHER_PROBES[kind][0] != plan_name:
        problems.append("kind and plan file name are not a launcher probe")
    if plan.get("status") != "staged-only-not-launched":
        problems.append("status")
    mods = plan.get("mods") if kind == "ce-fill-probe" else None
    if mods:
        validate_mods(mods, verify=True)
    if plan.get("arguments") != server_arguments(root, mods):
        problems.append("arguments differ from the launcher list")
    if (plan.get("server_exe"), plan.get("working_directory"), plan.get("port"), plan.get("server_exe_sha256"),
            plan.get("mission")) != (SERVER_EXE, SERVER_INSTALL, PORT, SERVER_EXE_SHA256,
                                     f"{root}\\mpmissions\\{MISSION_NAME}"):
        problems.append("server fields differ from the launcher constants")
    leaf = root.rsplit("\\", 1)[-1]
    if root != WINDOWS_PARENT + "\\" + leaf or not plain_runtime_name(leaf) or RESERVED_DEVICE.match(leaf) \
            or windows_normalized_name(leaf) == VERIFIED_RUNTIME_NAME.casefold():
        problems.append("runtime root is not an allowed launcher name")
    minutes = plan.get("probe", {}).get("wait_minutes")
    if not isinstance(minutes, int) or isinstance(minutes, bool) or not 5 <= minutes <= 120:
        problems.append("probe wait_minutes must be 5..120")
    listed = set()
    for entry in plan.get("staged_files", []):
        name = entry["path"]
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", name) or name.startswith("/") or ".." in name.split("/"):
            problems.append(f"unsafe staged path {name}")
            continue
        listed.add(name)
        if _hash_file(Path(destination) / name)[0] != entry["sha256"]:
            problems.append(f"staged file hash {name}")
    present = set(dm.walk_plain(destination))          # no-follow walk: a link is an error, never a "file"
    if present != listed:
        problems.append("runtime files differ from staged_files")
    return problems


def write_plan(destination, plan_name, plan):
    """Write the plan only when the launcher would accept it."""
    problems = launcher_problems(plan, destination, plan_name)
    if problems:
        raise ValueError("plan would be refused by the launcher: " + "; ".join(problems[:3]))
    dm.create_exclusive(Path(destination) / plan_name, (json.dumps(plan, indent=2) + "\n").encode("utf-8"))
    return plan
