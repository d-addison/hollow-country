"""WP-7 parity with the pre-migration checks at a5dafac.

Fixtures are synthetic except the optional, read-only native-cache differential.
Expected findings were captured from the three old modules before editing them;
these checks establish no native DayZ behaviour.

TDD record (2026-11-18): the initial SharedModelMigration run failed with
AttributeError for missing Source.methods and syntax.exponent_literals. Separate
regressions then failed with [] for a bodyless override and {} for a multiline
native prototype. All passed after the additive shared-model helpers were added.
GREEN: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.slow.test_enforce_source_parity -v

Round 2 RED (2026-11-18):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.slow.test_enforce_source_parity.AttributedMethodParity -v
Ran 5 tests; FAILED (failures=13): duplicate locals [], native prototypes {},
override findings [], and two attributed method bodies missing from the census.
Round 2 GREEN:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_enforce_locals tests.slow.test_script_identifiers tests.slow.test_script_syntax tests.slow.test_enforce_source_parity -v
Ran 30 tests; OK.
python3 -B -m tools.validate.enforce_lint --no-native
enforce_lint: pass findings=144 new=0 stale=0 native=no
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v
Ran 5872 tests; OK (skipped=1, expected failures=3).

Issue #166 spec/plan/tasks: compare the frozen legacy collector with the local
vanilla tree; separate native newline-terminated prototypes; retain the first
conditional header and check its shared body once; report malformed attributes.
All four tasks use the shared Source model; runtime acceptance remains pending.

#166 actual RED (2026-11-18), before implementation:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.slow.test_enforce_source_parity.NativePrototypeDifferential tests.slow.test_enforce_source_parity.ParserGapParity -v
Ran 4 tests; FAILED (failures=4). Missing names: GetSoundPosition,
RefreshServerList, SetSoundFrequency. Conditional Refresh absent (two wrappers);
semicolonless fixture signatures expected six names, got ['Body'].
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.slow.test_enforce_lint.SourceModel.test_unbalanced_attribute_reports_lint_instead_of_silently_dropping_method -v
Ran 1 test; FAILED (failures=2): AssertionError: 1 != 0 lint findings.
The subsequent native-body/commented-else guard run failed twice: duplicate
['Defined', 'Defined'] signatures and a spurious First method, then passed after
distinguishing bodies from declarations and tracking real directive offsets.

#166 GREEN:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.slow.test_enforce_source_parity tests.slow.test_enforce_lint -v
Ran 48 tests; OK. NativePrototypeDifferential ran against the installed cache
(not skipped), including all four real proto.c sound declarations.
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.slow.test_enforce_source_parity tests.slow.test_enforce_lint tests.slow.test_script_syntax tests.unit.test_enforce_locals tests.slow.test_script_identifiers tests.legacy.test_refusal_report tests.legacy.test_taped_light_v1_evidence tests.unit.test_hygiene.EnvExampleTests -v
Ran 77 tests; OK (before adding the final bodyless-attribute test, which also
passed separately and in the 48-test run).
python3 -B -m tools.validate.enforce_lint --no-native
enforce_lint: pass findings=133 new=0 stale=0 native=no (baseline unchanged).
python3 -B -m tools.validate.hygiene
exit 0, valid=true, errors=[]. Git-writing HygieneTests fixtures were excluded
to honor this run's metadata restriction; the hygiene CLI only reads Git.
"""
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from tests.slow import test_script_syntax as syntax
from tests.unit import test_enforce_locals as locals_check
from tests.slow import test_script_identifiers as identifiers
from tools.validate import enforce_source as es

ROOT = Path(__file__).resolve().parents[2]
W = 'mods/HollowCountry/scripts/4_World/'
SAMPLE = """enum State
{
    BAD = 0,
    OK = 1
}
class A
{
    ref Object Mission;
    void F()
    {
        Row created = new Row();
        if (a)
        {
            int created = 0;
        }
        if (a
            || b) {}
        if (c
            && d) {}
        float bound = 3.402823e38;
        return BAD;
    }
    override void Tick(float dt)
    {
    }
}
void A() { Object owned = null; }
void B() { m_Slots[i]++; }
int C() { if (!m_State) return 0; return 1; }
void F() { foreach (HCSceneLease owned : m_Leases) {} }
override void OnStoreSave(ParamsWriteContext ctx) {}
void G(Weather Weather) { Object Object = null; }
"""
EXPECTED = {
    'leading': [
        'mods/HollowCountry/scripts/4_World/sample.c:17',
        'mods/HollowCountry/scripts/4_World/sample.c:19',
    ],
    'overrides': [
        "mods/HollowCountry/scripts/4_World/sample.c:23: Tick('dt',) vs [('pDt',)]",
    ],
    'enum': [
        'mods/HollowCountry/scripts/4_World/sample.c:21: BAD (use State.BAD)',
    ],
    'locals': [
        'created',
    ],
    'exponents': [
        'mods/HollowCountry/scripts/4_World/sample.c:20',
    ],
    'declarations': [
        [8, 'Mission'],
        [11, 'created'],
        [14, 'created'],
        [20, 'bound'],
        [23, 'dt'],
        [27, 'owned'],
        [31, 'ctx'],
        [32, 'Weather'],
        [32, 'Object'],
    ],
    'collisions': [
        'mods/HollowCountry/scripts/4_World/sample.c:8: Mission',
        'mods/HollowCountry/scripts/4_World/sample.c:32: Weather',
        'mods/HollowCountry/scripts/4_World/sample.c:32: Object',
    ],
    'traps': [
        '27: keyword variable owned',
        '28: ++/-- on array element',
        '29: unbraced one-line return',
        '30: keyword variable owned',
        '31: entity storage override',
    ],
}


class LegacyFindingParity(unittest.TestCase):
    def test_captured_positive_findings_keep_names_lines_and_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / W / 'sample.c'
            path.parent.mkdir(parents=True)
            path.write_text(SAMPLE, encoding='utf-8')
            with patch.object(syntax, 'ROOT', root), patch.object(identifiers, 'ROOT', root):
                actual = {
                    'leading': syntax.leading_operator_lines([path]),
                    'overrides': syntax.mismatched_overrides([path], {'Tick': {('pDt',)}}),
                    'enum': syntax.bare_enum_members([path]),
                    'locals': locals_check.duplicate_locals(SAMPLE),
                    'exponents': syntax.exponent_literals([path]),
                    'declarations': [list(d) for d in identifiers.declarations(path)],
                    'collisions': identifiers.collisions([path], lambda _: identifiers.PINNED_ENGINE_TYPES),
                    'traps': identifiers.compile_traps(path),
                }
            self.assertEqual(EXPECTED, actual)

    def test_captured_class_layers_prototypes_and_native_visibility(self):
        files = {
            'mods/HollowCountry/scripts/3_Game/Base.c':
                'class Base {}\nclass Same {}\nenum NativeEnum { E }\nvoid Tick(float pDt)\n{\n}\n',
            W + 'Derived.c': 'modded class Base {}\nmodded class Same {}\nclass Same {}\n',
            'native/3_Game/Native.c': 'class NativeType {}\nenum NativeEnum { E }\n',
            W + 'Native.c': 'modded class NativeType {}\n',
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative, text in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding='utf-8')
            sources = sorted((root / 'mods').rglob('*.c'))
            defined, modded = identifiers.class_layers(sources)
            self.assertEqual({'Base': {2}, 'Same': {2, 3}}, defined)
            self.assertEqual([(W + 'Derived.c', 3, 'Base'), (W + 'Derived.c', 3, 'Same'),
                              (W + 'Native.c', 3, 'NativeType')],
                             [(p.relative_to(root).as_posix(), layer, name) for p, layer, name in modded])
            with patch.object(identifiers, 'ROOT', root):
                self.assertEqual([W + 'Derived.c: modded Base outside its base module',
                                  W + 'Native.c: modded NativeType outside its base module'],
                                 identifiers.cross_module_modded(sources, root / 'native'))
            self.assertEqual({'Tick': {('pDt',)}}, syntax.native_prototypes(root / 'mods'))
            self.assertEqual({0: set(), 1: set(), 2: {'NativeType', 'NativeEnum'}, 3: set(), 4: set()},
                             identifiers.native_types_by_layer(root / 'native'))

    def test_current_tree_retains_the_captured_empty_findings(self):
        sources = sorted((ROOT / 'mods').rglob('*.c'))
        self.assertTrue(sources)  # captured census at a5dafac: 263 sources
        self.assertEqual([], syntax.leading_operator_lines(sources))
        self.assertEqual([], syntax.bare_enum_members(sources))
        self.assertEqual({}, {p.relative_to(ROOT).as_posix(): names for p in sources
                              if (names := locals_check.duplicate_locals(p.read_text(encoding='utf-8')))})
        self.assertEqual([], identifiers.collisions(identifiers.authored_sources(),
                                                   lambda _: identifiers.PINNED_ENGINE_TYPES))
        self.assertEqual([], [trap for p in sources for trap in identifiers.compile_traps(p)])
        self.assertEqual([], identifiers.cross_module_modded(identifiers.authored_sources(), Path('/missing-cache')))


class SharedModelMigration(unittest.TestCase):
    def test_checks_ignore_the_same_noncode_and_keep_real_line_numbers(self):
        text = ('enum State { BAD }\n'
                '/* class Fake {\n'
                '    override void Tick(float dt) {}\n'
                '    || BAD\n'
                '    Object Mission; m_Slots[i]++;\n'
                '} */\n'
                'class A\n{\n'
                '    void F()\n    {\n'
                '        string label = "/* // BAD; Object Mission; m_Slots[i]++";\n'
                '        string escaped = "say \\" Object Mission; BAD";\n'
                '        /* Row created;\n'
                '           int created; */\n'
                '        Row created;\n'
                '        return BAD;\n'
                '        Object Mission;\n'
                '    }\n}\n')
        source = es.Source(Path(W + 'sample.c'), text)
        with patch.object(syntax, 'ROOT', Path('.')):
            self.assertEqual([], syntax.leading_operator_lines([source]))
            self.assertEqual([], syntax.mismatched_overrides([source], {'Tick': {('pDt',)}}))
            self.assertEqual([W + 'sample.c:16: BAD (use State.BAD)'], syntax.bare_enum_members([source]))
        self.assertEqual([], locals_check.duplicate_locals(source))
        self.assertEqual([], identifiers.compile_traps(source))
        self.assertEqual([(17, 'Mission')],
                         [(line, name) for line, name in identifiers.declarations(source)
                          if name in identifiers.PINNED_ENGINE_TYPES])
        self.assertEqual(({'A': {3}}, []), identifiers.class_layers([source]))

    def test_local_names_reset_at_each_shared_method_body(self):
        text = ('class A\n{\n'
                '    void F()\n    {\n'
                '        Row created;\n'
                '        if (x) { int created; }\n'
                '    }\n'
                '    void G()\n    {\n'
                '        Row created;\n'
                '    }\n}\n')
        self.assertEqual(['created'], locals_check.duplicate_locals(text))

    def test_bodyless_signatures_do_not_become_executable_methods(self):
        source = es.Source(Path('sample.c'), 'proto void Global(int pDt);\n'
                           'class A {\n'
                           '    ref Row m_Row = new Row();\n'
                           '    proto void Native(int pDt);\n'
                           '    override void Tick(int dt) {}\n}\n')
        self.assertEqual(['Tick'], [m.name for m in source.methods])
        self.assertEqual(['Global', 'Native', 'Tick'], [m.name for m in source.signatures])
        self.assertEqual([1, 4, 5], [source.line_of(m.offset) for m in source.signatures])

    def test_shared_methods_and_enum_offsets_support_the_old_checks(self):
        source = es.Source(Path(W + 'sample.c'), SAMPLE)
        self.assertEqual(['F', 'Tick', 'A', 'B', 'C', 'F', 'OnStoreSave', 'G'],
                         [m.name for m in source.methods])
        self.assertEqual([('State', 1, 5)],
                         [(e.name, source.line_of(e.offset), source.line_of(e.body_end))
                          for e in source.enum_blocks])
        self.assertEqual(['created'], locals_check.duplicate_locals(source))

    def test_bodyless_override_keeps_the_old_positive_finding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'sample.c'
            path.write_text('class A\n{\n    override void Tick(float dt);\n'
                            '    proto void Native(float pDt);\n}\n', encoding='utf-8')
            with patch.object(syntax, 'ROOT', root):
                self.assertEqual(["sample.c:3: Tick('dt',) vs [('pDt',)]"],
                                 syntax.mismatched_overrides([path], {'Tick': {('pDt',)}}))
            # The legacy prototype collector considers definitions, not same-line prototypes.
            self.assertEqual({}, syntax.native_prototypes(root))

    def test_multiline_native_prototype_keeps_the_old_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'sample.c'
            path.write_text('class A\n{\n    proto void Tick(float pDt)\n    ;\n}\n', encoding='utf-8')
            self.assertEqual({'Tick': {('pDt',)}}, syntax.native_prototypes(root))

    def test_exponent_detector_keeps_the_old_positive_case(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'sample.c'
            path.write_text('float bound = 3.402823e38;\nstring safe = "3e38"; // 2e30\n', encoding='utf-8')
            with patch.object(syntax, 'ROOT', root):
                self.assertEqual(['sample.c:1'], syntax.exponent_literals([path]))


# Synthetic attribute syntax exercises the source model, not engine acceptance.
ATTRIBUTES = (
    '[Obsolete("x")]',
    '[Obsolete("use F(x)) instead")]',
    '[Attr(Nested(Value(1)), [Other(2)])]',
    '[Obsolete("brackets ] [ and escaped \\\" quote )")][Other(1)]',
)


class AttributedMethodParity(unittest.TestCase):
    def test_duplicate_locals_survive_leading_attributes(self):
        for attribute in ATTRIBUTES:
            with self.subTest(attribute=attribute):
                text = f'class A {{ {attribute} void F(){{ int a; int a; }} }}'
                self.assertEqual(['a'], locals_check.duplicate_locals(text))

    def test_native_prototypes_survive_leading_attributes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'sample.c'
            for attribute in ATTRIBUTES:
                with self.subTest(attribute=attribute):
                    path.write_text(f'class A {{\n{attribute}\nvoid F(int value) {{}}\n'
                                    f'{attribute}\nproto void G(int other)\n;\n}}', encoding='utf-8')
                    self.assertEqual({'F': {('value',)}, 'G': {('other',)}},
                                     syntax.native_prototypes(root))

    def test_mismatched_overrides_survive_leading_attributes(self):
        for attribute in ATTRIBUTES:
            with self.subTest(attribute=attribute), patch.object(syntax, 'ROOT', Path('.')):
                source = es.Source(Path('sample.c'), f'class A {{\n{attribute}\n'
                                   f'override void F(int wrong) {{}}\n{attribute}\n'
                                   'override void G(int wrong);\n}')
                self.assertEqual(["sample.c:3: F('wrong',) vs [('value',)]",
                                  "sample.c:5: G('wrong',) vs [('other',)]"],
                                 syntax.mismatched_overrides([source],
                                                             {'F': {('value',)}, 'G': {('other',)}}))

    def test_every_fixture_method_body_is_registered_with_its_original_offset(self):
        # This fixture has only class and method braces; no control/initializer blocks.
        source = es.Source(Path('sample.c'),
                           '[Obsolete("free )")] void Free(int value) {}\n'
                           'class A {\n A() {}\n ~A() {}\n'
                           ' [Obsolete("old ] )")][Attr(Nested(1))] void F() {}\n'
                           ' [Obsolete("declaration")] proto void G(int value);\n}')
        body_braces = {i for i, ch in enumerate(source.code) if ch == '{'}
        body_braces -= {c.body_start for c in source.classes}
        self.assertEqual(body_braces, {m.body_start for m in source.methods})
        self.assertEqual(['Free', 'A', '~A', 'F'], [m.name for m in source.methods])
        self.assertEqual(['Free', 'A', '~A', 'F', 'G'], [m.name for m in source.signatures])
        for method in source.signatures:
            self.assertTrue(source.text[method.offset:].startswith(method.name))
            self.assertEqual(')', source.text[method.end - 1])

    def test_destructor_keys_and_dropped_zero_arg_calls_cannot_mask_parameter_mismatches(self):
        """Source keeps ~A and omits call expressions the old regex counted.

        These differences are harmless to the prototype consumer: destructors
        cannot be overridden, and zero-argument candidates always compare as
        the same empty tuple, so neither can reveal a parameter-name mismatch.
        Actual zero-argument declarations remain available in Source.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'sample.c'
            path.write_text('class A { A() {} ~A() {} void Zero() {} }\n'
                            'void Caller() {\n ZeroOnlyCall()\n;\n}\n', encoding='utf-8')
            prototypes = syntax.native_prototypes(root)
            self.assertEqual({'A': {()}, '~A': {()}, 'Zero': {()}, 'Caller': {()}}, prototypes)
            override = es.Source(root / 'override.c',
                                 'class B { override void Zero() {} override void ZeroOnlyCall() {} }')
            with patch.object(syntax, 'ROOT', root):
                self.assertEqual([], syntax.mismatched_overrides([override], prototypes))
                self.assertEqual([], syntax.mismatched_overrides([override],
                                                                {'Zero': {()}, 'ZeroOnlyCall': {()}}))


# Frozen from git show 785f82a^:tests/slow/test_script_syntax.py: METHOD,
# strip_comments, parameter_names and the native_prototypes candidate loop.
# Keep this reference independent of Source and the migrated syntax helpers.
LEGACY_METHOD = re.compile(r'\b([A-Za-z_]\w*)\s*\(([^()]*)\)\s*(?:\{|$)', re.M)


def legacy_prototype_names(raw):
    text = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group(0).count('\n'), raw, flags=re.S)
    text = '\n'.join(line.split('//')[0] for line in text.splitlines())
    classes = set(re.findall(r'\bclass\s+(\w+)', text))
    names = set()
    for match in LEGACY_METHOD.finditer(text):
        name, parameters = match.groups()
        prefix = text[text.rfind('\n', 0, match.start()) + 1:match.start()]
        if re.search(r'\boverride\b[^;{}]*$', prefix):
            continue
        valid = True
        for parameter in filter(None, (p.strip() for p in parameters.split(','))):
            parameter = parameter.split('=')[0].strip()
            if (not re.search(r'([A-Za-z_]\w*)\s*(?:\[\s*\d*\s*\])?$', parameter)
                    or len(parameter.split()) < 2):
                valid = False
                break
        if not valid:
            continue
        # The old regex also counts control flow, calls and text in strings.
        # Require declaration context, independently of the new parser's output:
        # a return type (optionally modified/attributed), or a class constructor.
        prefix = re.split(r'[;{}]', prefix)[-1]
        prefix = re.sub(r'^\s*\[.*\]\s*', '', prefix).strip()
        if name in classes and prefix in ('', '~'):
            names.add(name)  # legacy regex aliases ~Class to Class
        elif (re.fullmatch(r'[A-Za-z_]\w*(?:[\w\s<>,@]*[\w>])?', prefix)
              and not set(prefix.split()) & {'return', 'new', 'delete', 'else', 'case', 'thread', '#define'}
              and name not in {'if', 'while', 'for', 'foreach', 'switch', 'catch'}):
            names.add(name)
    return names


NATIVE_CACHE = Path('~/.cache/hollow-country/native-scripts/scripts-1.30.164289').expanduser()


class NativePrototypeDifferential(unittest.TestCase):
    def test_frozen_reference_excludes_keyword_call_and_string_noise(self):
        # Synthetic fixture, including zero-argument calls accepted by METHOD.
        text = ('class A {\n A() {}\n ~A() {}\n void Real(int value) {}\n'
                ' proto native int Semicolonless(int value)\n'
                ' override void Ignored(int value) {}\n'
                ' void Caller() {\n CallOnly()\n;\n return OtherCall()\n;\n'
                ' if (int x) {}\n thread ThreadCall()\n;\n'
                ' string text = "void StringNoise()\n";\n }\n}\n')
        self.assertEqual({'A', 'Real', 'Semicolonless', 'Caller'}, legacy_prototype_names(text))

    @unittest.skipUnless((NATIVE_CACHE / '1_Core').is_dir(),
                         'native script cache scripts-1.30.164289 not installed under ~/.cache/hollow-country')
    def test_real_vanilla_tree_preserves_legacy_prototype_names(self):
        cache = NATIVE_CACHE
        paths = sorted(cache.rglob('*.c'))
        self.assertTrue(paths, 'native cache exists but has no .c files')
        old_names, new_names = set(), set()
        for path in paths:
            raw = path.read_text(encoding='utf-8', errors='replace')
            old_names.update(legacy_prototype_names(raw))
            source = es.Source(path, raw)
            # ~Class is the intentional destructor spelling in the shared model.
            new_names.update(m.name.lstrip('~') for m in source.signatures)
            if path.relative_to(cache).as_posix() == '1_Core/proto/proto.c':
                self.assertTrue({'SetSoundVolume', 'SetSoundFrequency', 'GetSoundLength',
                                 'GetSoundPosition'} <= {m.name for m in source.signatures})
        self.assertGreater(len(old_names), 10000, 'frozen reference lost native declaration coverage')
        self.assertFalse(old_names - new_names, sorted(old_names - new_names))


class ParserGapParity(unittest.TestCase):
    def test_native_headers_with_bodies_are_not_also_bodyless_signatures(self):
        source = es.Source(Path('sample.c'), 'proto native void Defined()\n{}\n')
        self.assertEqual(['Defined'], [m.name for m in source.signatures])
        self.assertEqual(['Defined'], [m.name for m in source.methods])

    def test_commented_else_does_not_turn_consecutive_headers_into_alternatives(self):
        source = es.Source(Path('sample.c'), 'void First()\n/*\n#else\n*/\nvoid Second()\n{}')
        self.assertEqual([], source.methods)

    def test_semicolonless_native_prototypes_stay_separate(self):
        # Synthetic reproduction of 1_Core/proto/proto.c:85-93; no vanilla dump.
        source = es.Source(Path('sample.c'),
                           'proto native int SetSoundVolume(HSOUND sound, float volume)\n'
                           'proto native int SetSoundFrequency(HSOUND sound, int freq)\n'
                           'proto native int GetSoundLength(HSOUND sound)\n'
                           'proto native int GetSoundPosition(HSOUND sound)\n'
                           'proto native void Following(int value);\n'
                           'void Body() { int a; int a; }\n')
        expected = ['SetSoundVolume', 'SetSoundFrequency', 'GetSoundLength',
                    'GetSoundPosition', 'Following', 'Body']
        self.assertEqual(expected, [m.name for m in source.signatures])
        self.assertEqual(['Body'], [m.name for m in source.methods])
        self.assertEqual(['a'], locals_check.duplicate_locals(source))
        for line, method in enumerate(source.signatures, 1):
            self.assertEqual(line, source.line_of(method.offset))
            self.assertEqual(')', source.text[method.end - 1])

    def test_conditional_headers_keep_first_signature_and_check_shared_body_once(self):
        # Synthetic class/global alternatives with a shared body, as in vanilla
        # ServerBrowserTabConsolePages.c:454-459; directives remain unselected.
        for wrapper in ('{}', 'class A {{\n{}\n}}'):
            with self.subTest(wrapper=wrapper):
                text = wrapper.format('#ifdef DIAG_DEVELOPER\n'
                                      'void Refresh(bool force = false)\n'
                                      '#else\nvoid Refresh()\n#endif\n'
                                      '{ int repeated; int repeated; }\n'
                                      'void Following() {}')
                source = es.Source(Path('sample.c'), text)
                self.assertIn(('Refresh', 'bool force = false'),
                              [(s.name, s.params) for s in source.signatures])
                self.assertEqual(['Refresh', 'Following'], [m.name for m in source.methods])
                self.assertEqual(['repeated'], locals_check.duplicate_locals(source))
                method = source.methods[0]
                self.assertEqual('{ int repeated; int repeated; }', source.body(method))
                self.assertEqual(text.index('Refresh'), method.offset)


if __name__ == '__main__':
    unittest.main()
