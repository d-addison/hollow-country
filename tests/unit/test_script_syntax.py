"""Enforce statement shapes the native compiler has rejected.

Native compile 068 (DayZDiag 1.30.164289) failed on HCInfectedModule.c:120-131
with "Missing ';' at the end of line" / "Invalid statement ')'" where a
condition continued on a line that began with `||` or `&&`. Offline Python
translations accept that shape, so authored sources are checked directly.

Native compile 069 then failed with "Can't find variable 'dt'" at
HCInfectedNative.c:34: an override whose parameter names differ from the
engine prototype (FIX-ME warning) binds the prototype names, not its own.
"""
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEADING_OPERATOR = re.compile(r'^\s*(\|\||&&)')
CACHE = Path(os.environ.get(
    'HC_NATIVE_SCRIPTS',
    Path.home() / '.cache/hollow-country/native-scripts/scripts-1.30.164289'))
METHOD = re.compile(r'\b([A-Za-z_]\w*)\s*\(([^()]*)\)\s*(?:\{|$)', re.M)
OVERRIDE = re.compile(r'\boverride\b[^(;{}]*?\b([A-Za-z_]\w*)\s*\(([^()]*)\)')


def parameter_names(text):
    names = []
    for parameter in filter(None, (p.strip() for p in text.split(','))):
        parameter = parameter.split('=')[0].strip()
        match = re.search(r'([A-Za-z_]\w*)\s*(?:\[\s*\d*\s*\])?$', parameter)
        if not match or len(parameter.split()) < 2:
            return None
        names.append(match.group(1))
    return tuple(names)


def native_prototypes(*roots):
    prototypes = {}
    for source in (s for root in roots for s in root.rglob('*.c')):
        text = '\n'.join(strip_comments(source.read_text(encoding='utf-8', errors='replace')))
        for match in METHOD.finditer(text):
            name, parameters = match.groups()
            if re.search(r'\boverride\b[^;{}]*$', text[text.rfind('\n', 0, match.start()) + 1:match.start()]):
                continue
            names = parameter_names(parameters)
            if names is not None:
                prototypes.setdefault(name, set()).add(names)
    return prototypes


def mismatched_overrides(paths, prototypes):
    found = []
    for path in paths:
        text = '\n'.join(strip_comments(path.read_text(encoding='utf-8')))
        for match in OVERRIDE.finditer(text):
            name, names = match.group(1), parameter_names(match.group(2))
            candidates = {p for p in prototypes.get(name, ()) if names is not None and len(p) == len(names)}
            if candidates and names not in candidates:
                line = text.count('\n', 0, match.start()) + 1
                found.append(f'{path.relative_to(ROOT)}:{line}: {name}{names} vs {sorted(candidates)}')
    return found


def strip_comments(text):
    text = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group(0).count('\n'), text, flags=re.S)
    return [line.split('//')[0] for line in text.splitlines()]


def leading_operator_lines(paths):
    found = []
    for path in paths:
        for number, line in enumerate(strip_comments(path.read_text(encoding='utf-8')), 1):
            if LEADING_OPERATOR.match(line):
                found.append(f'{path.relative_to(ROOT)}:{number}')
    return found


ENUM_BLOCK = re.compile(r'\benum\s+(\w+)\s*\{([^}]*)\}', re.S)


def bare_enum_members(paths):
    # Native compile 078: Enforce rejected `return HC_STIMULUS_NONE;` with
    # "Can't find variable"; members must be referenced as Enum.MEMBER.
    texts = {path: '\n'.join(strip_comments(path.read_text(encoding='utf-8'))) for path in paths}
    members = {}
    for text in texts.values():
        for match in ENUM_BLOCK.finditer(text):
            for entry in match.group(2).split(','):
                name = entry.split('=')[0].strip()
                if name:
                    members[name] = match.group(1)
    found = []
    for path, text in texts.items():
        body = ENUM_BLOCK.sub(lambda m: '\n' * m.group(0).count('\n'), text)
        body = re.sub(r'"[^"\n]*"', '""', body)
        # A class constant or local of the same name (HCEcologyCode.OK) shadows the enum member.
        declared = set(re.findall(r'\b(?:int|float|bool|string)\s+(\w+)', body))
        for number, line in enumerate(body.splitlines(), 1):
            for match in re.finditer(r'(?<![\w.])(\w+)\b', line):
                if match.group(1) in members and match.group(1) not in declared:
                    found.append(f'{path.relative_to(ROOT)}:{number}: {match.group(1)} (use {members[match.group(1)]}.{match.group(1)})')
    return found


class ScriptSyntaxBehavior(unittest.TestCase):
    def test_detector_flags_the_observed_rejected_continuation(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            sample = Path(temporary) / 'sample.c'
            sample.write_text('if (a\n    || b)\n{\n}\n// || comment\nif (c && d) {}\n', encoding='utf-8')
            found = [line for line in strip_comments(sample.read_text()) if LEADING_OPERATOR.match(line)]
        self.assertEqual(['    || b)'], found)

    def test_authored_conditions_do_not_continue_with_a_leading_logical_operator(self):
        sources = sorted((ROOT / 'mods').rglob('*.c'))
        self.assertTrue(sources)
        self.assertEqual([], leading_operator_lines(sources))

    def test_override_parameter_names_match_an_installed_engine_prototype(self):
        if not (CACHE / '4_World').is_dir():
            self.skipTest('installed native interface cache not present')
        sources = sorted((ROOT / 'mods').rglob('*.c'))
        self.assertEqual([], mismatched_overrides(sources, native_prototypes(CACHE, ROOT / 'mods')))

    def test_override_detector_flags_the_observed_renamed_parameters(self):
        prototypes = {'ModCommandHandlerBefore': {('pDt', 'pCurrentCommandID', 'pCurrentCommandFinished')}}
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            sample = Path(temporary) / 'sample.c'
            sample.write_text('override bool ModCommandHandlerBefore(float dt, int command, bool finished)\n{\n}\n'
                              'override bool ModCommandHandlerBefore(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)\n{\n}\n',
                              encoding='utf-8')
            global ROOT
            saved, ROOT = ROOT, Path(temporary)
            try:
                found = mismatched_overrides([sample], prototypes)
            finally:
                ROOT = saved
        self.assertEqual(1, len(found))
        self.assertIn('sample.c:1: ModCommandHandlerBefore', found[0])

    def test_authored_float_limits_use_native_constants_not_exponent_literals(self):
        # Compile 072 accepted 3.402823e38 but its parsed value is unobserved;
        # an ecology Finite() bound read as 3.402823 would reject world positions.
        exponent = re.compile(r'\b\d+(?:\.\d+)?[eE][+-]?\d+\b')
        found = []
        for path in sorted((ROOT / 'mods').rglob('*.c')):
            for number, line in enumerate(strip_comments(path.read_text(encoding='utf-8')), 1):
                if exponent.search(re.sub(r'"[^"]*"', '""', line)):
                    found.append(f'{path.relative_to(ROOT)}:{number}')
        self.assertEqual([], found)


    def test_detector_flags_the_observed_unqualified_enum_member(self):
        import tempfile
        global ROOT
        with tempfile.TemporaryDirectory() as temporary:
            sample = Path(temporary) / 'sample.c'
            sample.write_text('enum HCStimulusCategory\n{\n    HC_STIMULUS_NONE = 0,\n    HC_STIMULUS_HEARD = 1\n}\n'
                              'int A() { return HC_STIMULUS_NONE; }\n'
                              'int B() { return HCStimulusCategory.HC_STIMULUS_HEARD; }\n'
                              '// HC_STIMULUS_NONE in a comment\nstring C() { return "HC_STIMULUS_NONE"; }\n'
                              'class Other { static const int HC_STIMULUS_HEARD = 1; }\n',
                              encoding='utf-8')
            saved, ROOT = ROOT, Path(temporary)
            try:
                found = bare_enum_members([sample])
            finally:
                ROOT = saved
        self.assertEqual(['sample.c:6: HC_STIMULUS_NONE (use HCStimulusCategory.HC_STIMULUS_NONE)'], found)

    def test_authored_enum_members_are_referenced_through_their_enum(self):
        sources = sorted((ROOT / 'mods').rglob('*.c'))
        self.assertEqual([], bare_enum_members(sources))


if __name__ == '__main__':
    unittest.main()
