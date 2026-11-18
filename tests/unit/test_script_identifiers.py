"""Enforce rejects a variable or member whose name equals a visible type name.

Native compile 066 failed with "Variable name 'Mission' already used as type
name" (HCEventRuntimeData.c:60). Offline Python translations cannot see this,
so authored declarations are checked against pinned engine type names visible
from 3_Game, and against the full installed interface cache when present.
"""
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODS = ROOT / 'mods'
LAYERS = ['1_Core', '2_GameLib', '3_Game', '4_World', '5_Mission']
# Top-level classes defined in installed 1.30.164289 1_Core/2_GameLib/3_Game
# (verified in the extracted interface cache); visible to every authored layer.
PINNED_ENGINE_TYPES = {
    'Mission', 'Game', 'World', 'Weather', 'Object', 'Man', 'Camera', 'Hive',
    'Widget', 'Param', 'Class', 'Managed', 'Entity', 'Human', 'Car',
    'Transport', 'Building', 'Effect', 'Particle', 'Material', 'Shape',
    'Timer', 'Input',
}
CACHE = Path(os.environ.get(
    'HC_NATIVE_SCRIPTS',
    Path.home() / '.cache/hollow-country/native-scripts/scripts-1.30.164289'))
MODIFIERS = r'(?:(?:ref|autoptr|static|protected|private|const|owned|notnull|out|inout)\s+)*'
DECLARATION = re.compile(
    r'(?:^\s*|[({;,]\s*)' + MODIFIERS + r'([A-Za-z_]\w*(?:<[^;()=]*?>)?)\s+([A-Za-z_]\w*)\s*(?=[;=,)\[])')
KEYWORDS = {'return', 'new', 'class', 'typename', 'modded', 'override', 'delete', 'else', 'case'}


def strip_comments(text):
    text = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group(0).count('\n'), text, flags=re.S)
    return '\n'.join(line.split('//')[0] for line in text.splitlines())


def layer_of(path):
    for part in path.parts:
        if part in LAYERS:
            return LAYERS.index(part)
    return None


def declarations(path):
    for number, line in enumerate(strip_comments(path.read_text(encoding='utf-8')).splitlines(), 1):
        for match in DECLARATION.finditer(line):
            kind, name = match.groups()
            if kind not in KEYWORDS:
                yield number, name


def native_types_by_layer(cache):
    visible = {}
    for index, layer in enumerate(LAYERS):
        names = set()
        for source in (cache / layer).rglob('*.c'):
            text = source.read_text(encoding='utf-8', errors='replace')
            names.update(re.findall(r'^(?:modded\s+|sealed\s+)?(?:class|enum)\s+(\w+)', text, re.M))
        visible[index] = names
    return visible


def authored_sources():
    return sorted(p for p in MODS.rglob('*.c') if layer_of(p) is not None)


def collisions(sources, visible_for_layer):
    found = []
    for source in sources:
        names = visible_for_layer(layer_of(source))
        for number, name in declarations(source):
            if name in names:
                found.append(f'{source.relative_to(ROOT)}:{number}: {name}')
    return found


class ScriptIdentifierBehavior(unittest.TestCase):
    def test_detector_flags_the_observed_native_compile_failure_shape(self):
        lines = ['class HCEventRun', '{', '    ref HCEventMission Mission;', '    int Phase = 0;', '}',
                 'void F(Weather Weather) {}', 'void G() { int Value = 1; Object Object = null; }']
        found = [name for _, name in self._declarations_of('\n'.join(lines))]
        self.assertIn('Mission', found)
        self.assertIn('Weather', found)
        self.assertIn('Object', found)
        self.assertNotIn('HCEventRun', found)

    def _declarations_of(self, text):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'sample.c'
            path.write_text(text, encoding='utf-8')
            return list(declarations(path))

    def test_authored_declarations_do_not_reuse_pinned_engine_type_names(self):
        self.assertEqual([], collisions(authored_sources(), lambda _layer: PINNED_ENGINE_TYPES))

    def test_authored_declarations_do_not_reuse_installed_visible_type_names(self):
        if not (CACHE / '3_Game').is_dir():
            self.skipTest('installed native interface cache not present')
        visible = native_types_by_layer(CACHE)

        def visible_for(layer):
            names = set()
            for index in range(layer + 1):
                names |= visible[index]
            return names

        self.assertEqual([], collisions(authored_sources(), visible_for))


# Native compile traps found by Wine compiles 142-153 that offline translation accepts.
KEYWORD_VARIABLE = re.compile(r'\b[A-Za-z_]\w*(?:<[^;()=]*?>)?\s+owned\s*[;=,):]')
TEMPORARY_INCREMENT = re.compile(r'\]\s*(?:\+\+|--)')
UNBRACED_ONE_LINE_RETURN = re.compile(r'\)\s*\{\s*if\s*\([^{};]*\)\s*return\b[^{};]*;\s*return\b')
CLASS_DEFINITION = re.compile(r'^\s*(modded\s+)?class\s+(\w+)', re.M)


def compile_traps(path):
    found = []
    for number, line in enumerate(strip_comments(path.read_text(encoding='utf-8')).splitlines(), 1):
        for label, pattern in (('keyword variable owned', KEYWORD_VARIABLE),
                               ('++/-- on array element', TEMPORARY_INCREMENT),
                               ('unbraced one-line return', UNBRACED_ONE_LINE_RETURN)):
            if pattern.search(line):
                found.append(f'{number}: {label}')
    return found


def class_layers(paths):
    defined, modded = {}, []
    for path in paths:
        layer = layer_of(path)
        for match in CLASS_DEFINITION.finditer(strip_comments(path.read_text(encoding='utf-8', errors='replace'))):
            if match.group(1):
                modded.append((path, layer, match.group(2)))
            else:
                defined.setdefault(match.group(2), set()).add(layer)
    return defined, modded


def cross_module_modded(sources, cache):
    authored, modded = class_layers(sources)
    native = class_layers(list((cache).rglob('*.c')))[0] if (cache / '3_Game').is_dir() else {}
    found = []
    for path, layer, name in modded:
        layers = authored.get(name, set()) | native.get(name, set())
        if layers and layer not in layers:
            found.append(f'{path.relative_to(ROOT)}: modded {name} outside its base module')
    return found


class NativeCompileTraps(unittest.TestCase):
    def test_detector_flags_observed_trap_shapes(self):
        import tempfile
        sample = '\n'.join(['void A() { Object owned = null; }', 'void B() { m_Slots[i]++; }',
                            'int C() { if (!m_State) return 0; return 1; }',
                            'int D() { if (!m_State) { return 0; } return 1; }', 'owned string E;',
                            'void F() { foreach (HCSceneLease owned : m_Leases) {} }'])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'sample.c'
            path.write_text(sample, encoding='utf-8')
            self.assertEqual(['1: keyword variable owned', '2: ++/-- on array element',
                              '3: unbraced one-line return', '6: keyword variable owned'], compile_traps(path))

    def test_authored_sources_avoid_native_compile_traps(self):
        found = [f'{source.relative_to(ROOT)}:{trap}' for source in authored_sources() for trap in compile_traps(source)]
        self.assertEqual([], found)

    def test_modded_classes_stay_in_their_base_script_module(self):
        self.assertEqual([], cross_module_modded(authored_sources(), CACHE))


if __name__ == '__main__':
    unittest.main()
