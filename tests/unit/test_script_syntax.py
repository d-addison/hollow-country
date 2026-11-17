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


if __name__ == '__main__':
    unittest.main()
