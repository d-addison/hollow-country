"""WP-7 parity with the pre-migration checks at a5dafac.

All fixtures are synthetic. Expected findings were captured from the three old
modules before editing them; these checks establish no native DayZ behaviour.

TDD record (2026-11-18): the initial SharedModelMigration run failed with
AttributeError for missing Source.methods and syntax.exponent_literals. Separate
regressions then failed with [] for a bodyless override and {} for a multiline
native prototype. All passed after the additive shared-model helpers were added.
GREEN: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_enforce_source_parity -v
"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.unit import test_script_syntax as syntax
from tests.unit import test_enforce_locals as locals_check
from tests.unit import test_script_identifiers as identifiers
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


if __name__ == '__main__':
    unittest.main()
