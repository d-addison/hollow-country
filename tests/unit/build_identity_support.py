"""Executes the authored HCBuildIdentity.c statics, never a Python re-implementation.

The class is deliberately written in the tiny Enforce subset handled here:
static const strings, static bool state, single-line `if (...) return ...;`,
string locals, `x.ToLower();`, Print and GetVersion(out string). Anything else fails loudly,
so the matcher cannot drift into a shape this adapter silently mis-executes.
This is a restricted offline translation; it is NOT DayZ engine evidence.
"""
import json
import re
from pathlib import Path
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts/3_Game/HCBuildIdentity.c"


def _expression(text, literals, names):
    text = re.sub(r"\b(\w+)\.ToLower\(\)", r"\1.lower()", text)
    text = text.replace("&&", " and ").replace("||", " or ")
    text = re.sub(r"!(?!=)", " not ", text)
    text = re.sub(r"\btrue\b", "True", text)
    text = re.sub(r"\bfalse\b", "False", text)
    for name in names:
        text = re.sub(r"(?<![.\w])" + re.escape(name) + r"\b", "_ns." + name, text)
    for key, value in literals.items():
        text = text.replace(key, repr(value))
    return text


def translate(source=None):
    """Return a namespace exposing every static of HCBuildIdentity."""
    text = SOURCE.read_text(encoding="utf-8") if source is None else source
    text = re.sub(r"//[^\n]*", "", text)
    literals = {}

    def literal(match):
        key = "_lit%d_" % len(literals)
        literals[key] = json.loads(match[0])
        return key

    text = re.sub(r'"(?:\\.|[^"\\])*"', literal, text)
    namespace = SimpleNamespace()
    # Explicit inert synthetic engine defaults preserve existing pure-predicate users.
    # Tests that inspect logging/native reads replace these adapters in the shared scope.
    scope = {"_ns": namespace, "Print": lambda value: None, "GetGame": lambda: None}
    for match in re.finditer(r"static const string (\w+) = (\w+);", text):
        setattr(namespace, match[1], literals[match[2]])
        scope[match[1]] = literals[match[2]]
    functions = list(re.finditer(r"static (bool|string) (\w+)\(([^)]*)\)\s*\{", text))
    assert functions, "HCBuildIdentity statics not found"
    state = set()
    for match in re.finditer(r"static bool (\w+) = (true|false);", text):
        state.add(match[1])
        setattr(namespace, match[1], match[2] == "true")
    names = state | {match[2] for match in functions}
    for match in functions:
        depth, end = 1, match.end()
        while depth:
            depth += (text[end] == "{") - (text[end] == "}")
            end += 1
        parameters = [p.split()[-1] for p in match[3].split(",") if p.strip()]
        lines = ["def %s(%s):" % (match[2], ", ".join(parameters))]
        # Native string parameters are values; other harnesses may pass mutable
        # synthetic out-string boxes whose __str__ exposes that value.
        for parameter in match[3].split(","):
            if parameter.strip().startswith("string "):
                name = parameter.split()[-1]
                lines.append("    %s = str(%s)" % (name, name))
        for statement in filter(None, (s.strip() for s in text[match.end():end - 1].split(";"))):
            if statement.startswith("if ("):
                depth, cursor = 1, 4
                while depth:
                    depth += (statement[cursor] == "(") - (statement[cursor] == ")")
                    cursor += 1
                condition, rest = statement[4:cursor - 1], statement[cursor:].strip()
                assert rest.startswith("return "), "only single-line if/return is supported: " + statement
                lines.append("    if %s: %s" % (_expression(condition, literals, names), _expression(rest, literals, names)))
            elif statement.startswith("return "):
                lines.append("    " + _expression(statement, literals, names))
            elif re.fullmatch(r"string \w+ = [\w.]+", statement):
                lines.append("    " + _expression(statement[len("string "):], literals, names))
            elif re.fullmatch(r"string \w+", statement):
                lines.append("    " + statement[len("string "):] + " = ''")
            elif re.fullmatch(r"\w+\.ToLower\(\)", statement):
                variable = statement.split(".")[0]
                lines.append("    %s = %s.lower()" % (variable, variable))
            elif re.fullmatch(r"\w+ = (?:true|false)", statement) and statement.split()[0] in state:
                lines.append("    " + _expression(statement, literals, names))
            elif re.fullmatch(r"Print\(.+\)", statement):
                lines.append("    " + _expression(statement, literals, names))
            elif re.fullmatch(r"GetGame\(\)\.GetVersion\(\w+\)", statement):
                variable = statement[statement.rfind("(") + 1:-1]
                lines.append("    %s = GetGame().GetVersion()" % variable)
            else:
                raise AssertionError("unsupported HCBuildIdentity statement: " + statement)
        exec("\n".join(lines), scope)
        setattr(namespace, match[2], scope[match[2]])
    return namespace
