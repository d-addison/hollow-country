"""Executes the authored HCBuildIdentity.c statics, never a Python re-implementation.

The class is deliberately written in the tiny Enforce subset handled here:
static const strings, single-line `if (...) return ...;`, `string x = y;`,
`x.ToLower();` and `return ...;`. Anything else makes translation fail loudly,
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
    text = re.sub(r"\btrue\b", "True", text).replace("false", "False")
    text = re.sub(r"\b(?:Canonical|Matches|Normalize|SameBuild|CanonicalWorld|SameWorld)\(", lambda m: "_ns." + m[0], text)
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
    scope = {"_ns": namespace}
    for match in re.finditer(r"static const string (\w+) = (\w+);", text):
        setattr(namespace, match[1], literals[match[2]])
        scope[match[1]] = literals[match[2]]
    functions = list(re.finditer(r"static (bool|string) (\w+)\(([^)]*)\)\s*\{", text))
    assert functions, "HCBuildIdentity statics not found"
    for match in functions:
        depth, end = 1, match.end()
        while depth:
            depth += (text[end] == "{") - (text[end] == "}")
            end += 1
        parameters = [p.split()[-1] for p in match[3].split(",") if p.strip()]
        lines = ["def %s(%s):" % (match[2], ", ".join(parameters))]
        for statement in filter(None, (s.strip() for s in text[match.end():end - 1].split(";"))):
            if statement.startswith("if ("):
                depth, cursor = 1, 4
                while depth:
                    depth += (statement[cursor] == "(") - (statement[cursor] == ")")
                    cursor += 1
                condition, rest = statement[4:cursor - 1], statement[cursor:].strip()
                assert rest.startswith("return "), "only single-line if/return is supported: " + statement
                lines.append("    if %s: %s" % (_expression(condition, literals, scope), _expression(rest, literals, scope)))
            elif statement.startswith("return "):
                lines.append("    " + _expression(statement, literals, scope))
            elif re.fullmatch(r"string \w+ = [\w.]+", statement):
                lines.append("    " + _expression(statement[len("string "):], literals, scope))
            elif re.fullmatch(r"\w+\.ToLower\(\)", statement):
                variable = statement.split(".")[0]
                lines.append("    %s = %s.lower()" % (variable, variable))
            else:
                raise AssertionError("unsupported HCBuildIdentity statement: " + statement)
        exec("\n".join(lines), scope)
        setattr(namespace, match[2], scope[match[2]])
    return namespace
