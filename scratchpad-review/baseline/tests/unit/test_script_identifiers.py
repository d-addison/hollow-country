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


if __name__ == '__main__':
    unittest.main()
