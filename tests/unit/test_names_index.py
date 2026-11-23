"""The committed vanilla names-only index: generation, the refuse rule and the fallbacks."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.validate import class_index, enforce_lint, native_symbols as ns

CACHE = Path('~/.cache/hollow-country/native-scripts/scripts-1.30.164289').expanduser()

# Each marker is a body, comment or literal that must never reach the index.
SOURCE = '''
// BODYMARK comment line
class Base
{
    const string LITMARK = "literal-mark-one";
    int count = 41357;
    ref array<string> names;
    static void Make(int amount = 987654, string label = "literal-mark-two", out vector place)
    {
        Print("literal-mark-three"); /* BLOCKMARK */
        int hidden = 7;
    }
    proto native void Native(notnull Base other, float value);
    void Plain() { string BODYMARK2 = "x"; }
}
modded class Base
{
    override void Plain() { super.Plain(); }
}
class Child : Base {}
enum Mode { ONE = 1, TWO }
typedef array<string> TNames;
proto native void GlobalCall(string text);
void ScriptGlobal(int a) { Print("literal-mark-four"); }
'''


def strings(node):
    """Every key and value string of a JSON document."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)
    elif isinstance(node, str):
        yield node


def fixture(root):
    (root / '3_Game').mkdir(parents=True)
    (root / '3_Game/sample.c').write_text(SOURCE)
    for layer in ('1_Core', '2_GameLib', '4_World', '5_Mission'):
        (root / layer).mkdir()
    return root


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = fixture(Path(self.temp.name) / 'scripts')

    def test_index_holds_names_only(self):
        doc = ns.build_names_index(self.root)
        text = ns.dump_names_index(doc)
        for marker in ('BODYMARK', 'BLOCKMARK', 'literal-mark', '41357', '987654', 'hidden'):
            self.assertNotIn(marker, text)
        self.assertNotIn(str(self.temp.name), text)
        for value in strings(doc):
            self.assertFalse(set(value) & set('"\'{};=()/\\*#'), value)

    def test_structure_keeps_types_and_modifiers_but_not_parameter_names(self):
        doc = ns.build_names_index(self.root)
        base, modded = doc['classes']['Base']
        self.assertFalse(base['modded'])
        self.assertTrue(modded['modded'])
        self.assertEqual('Base', doc['classes']['Child'][0]['parent'])
        self.assertEqual({'LITMARK': 'string', 'count': 'int', 'names': 'array<string>'}, base['fields'])
        rows = {row[0]: row for row in base['methods']}
        self.assertEqual(['Make', 'static', ['int', 'string', 'out vector']], rows['Make'])
        self.assertEqual(['Native', 'native proto', ['Base', 'float']], rows['Native'])
        self.assertEqual([['Plain', 'override', []]], modded['methods'])
        self.assertEqual(['Mode'], doc['enums']['2'])
        self.assertTrue({'Base', 'Child', 'Mode', 'TNames'} <= set(doc['types']['2']))
        self.assertEqual([['native proto', 2]], doc['globals']['GlobalCall'])
        self.assertEqual([['', 2]], doc['globals']['ScriptGlobal'])

    def test_output_is_deterministic_and_sorted(self):
        first = ns.dump_names_index(ns.build_names_index(self.root))
        second = ns.dump_names_index(ns.build_names_index(self.root))
        self.assertEqual(first, second)
        self.assertTrue(first.endswith('\n'))
        self.assertEqual(first, json.dumps(json.loads(first), sort_keys=True, separators=(',', ':')) + '\n')

    def test_parameter_types_keep_generic_commas_and_drop_defaults(self):
        self.assertEqual(
            ['map<string,int>', 'out map<string,array<ref Base>>', 'int', 'string'],
            ns._parameter_types('map<string, int> values, '
                                'out map<string, array<ref Base>> nested, '
                                'int count = 2, string sep = ","'))

    def test_index_keeps_nested_generic_parameter_types(self):
        (self.root / '3_Game/sample.c').write_text(
            'class Probe { void Run(map<string, int> values, '
            'inout map<string, array<ref Base>> nested, string sep = ",") {} }')
        doc = ns.build_names_index(self.root)
        self.assertEqual(
            [['Run', '', ['map<string,int>', 'inout map<string,array<ref Base>>', 'string']]],
            doc['classes']['Probe'][0]['methods'])

    def test_missing_scripts_are_refused(self):
        with self.assertRaises(ValueError):
            ns.build_names_index(Path(self.temp.name) / 'absent')

    def test_emit_writes_validated_bytes_and_refusal_leaves_the_file_alone(self):
        output = Path(self.temp.name) / 'out/names.json'
        size = ns.emit_names_index(self.root, output)
        self.assertEqual(size, len(output.read_bytes()))
        ns.load_names_index(output)
        before = output.read_bytes()
        with patch.object(ns, 'build_names_index', side_effect=ns.NamesIndexError('refused')):
            with self.assertRaises(ns.NamesIndexError):
                ns.emit_names_index(self.root, output)
        self.assertEqual(before, output.read_bytes())


class RefuseTests(unittest.TestCase):
    """The generator and the loader fail if any entry is more than a name."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.doc = ns.build_names_index(fixture(Path(self.temp.name) / 'scripts'))

    def refused(self, mutate):
        doc = copy.deepcopy(self.doc)
        mutate(doc)
        with self.assertRaises(ns.NamesIndexError):
            ns.validate_names_index(doc)

    def test_a_valid_index_passes(self):
        ns.validate_names_index(self.doc)

    def test_body_comment_and_literal_are_each_refused(self):
        entry = lambda d: d['classes']['Base'][0]
        for bad in ('Foo() { return 1; }', 'Foo // comment', 'Foo /* c */', 'Foo"text"', "Foo'x'", 'a;b', 'a=b',
                    'Foo\\n', '7', '3.5', 'x y(z)', ''):
            self.refused(lambda d, b=bad: entry(d)['methods'].append([b, '', []]))
            self.refused(lambda d, b=bad: entry(d)['fields'].update({'ok': b}))
            self.refused(lambda d, b=bad: entry(d)['methods'].append(['ok', '', [b]]))
            self.refused(lambda d, b=bad: d['classes'].update({b: []}))
            self.refused(lambda d, b=bad: d['types']['2'].append(b))

    def test_a_default_value_or_initializer_field_is_refused(self):
        self.refused(lambda d: d['classes']['Base'][0].update({'body': 'int x;'}))
        self.refused(lambda d: d['classes']['Base'][0]['methods'].append(['ok', '', ['int', 'default']]) or
                     d['classes']['Base'][0]['methods'][-1].append('{ }'))
        self.refused(lambda d: d.update({'comments': []}))
        self.refused(lambda d: d['classes']['Base'][0]['methods'].append(['ok', 'private; evil', []]))

    def test_wrong_schema_build_or_hash_is_refused(self):
        self.refused(lambda d: d.update({'schema': 99}))
        self.refused(lambda d: d.update({'game_build': '0.0'}))
        self.refused(lambda d: d.update({'source_hash': 'not-a-hash'}))

    def test_loader_refuses_a_tampered_file(self):
        path = Path(self.temp.name) / 'names.json'
        doc = copy.deepcopy(self.doc)
        doc['classes']['Base'][0]['fields']['bad'] = 'string = "x"'
        path.write_text(json.dumps(doc))
        with self.assertRaises(ns.NamesIndexError):
            ns.load_names_index(path)
        path.write_text('not json')
        with self.assertRaises(ns.NamesIndexError):
            ns.load_names_index(path)
        with self.assertRaises(ns.NamesIndexError):
            ns.load_names_index(Path(self.temp.name) / 'absent.json')


class CommittedIndexTests(unittest.TestCase):
    def test_committed_index_is_valid_names_only_and_small(self):
        self.assertLess(ns.NAMES_INDEX.stat().st_size, 3 * 1024 * 1024)
        doc = ns.load_names_index()
        self.assertEqual(ns.BUILD, doc['game_build'])
        self.assertIn('PlayerBase', doc['classes'])
        self.assertIn('ItemBase', doc['classes'])
        text = ns.NAMES_INDEX.read_text(encoding='utf-8')
        for value in strings(doc):
            self.assertFalse(set(value) & set('"\'{};=()/\\*#'), value)
        for marker in ('/home', 'steam', 'Users'):
            self.assertNotIn(marker, text)
        self.assertEqual(text, ns.dump_names_index(doc))

    def test_symbols_match_the_loader_shape(self):
        symbols = ns.symbols_from_names_index(ns.load_names_index())
        self.assertEqual('names-index', symbols['origin'])
        self.assertTrue({'parent', 'modded', 'layer', 'methods', 'fields'} <= set(symbols['classes']['PlayerBase'][0]))
        self.assertEqual({str(i) for i in range(5)}, set(symbols['types']))
        self.assertIn(0, symbols['global_functions']['Print'])

    @unittest.skipUnless((CACHE / '3_Game').is_dir(), 'native scripts cache unavailable on this host')
    def test_committed_index_matches_the_cache_and_the_cache_loader(self):
        self.assertEqual(('PASS', 'committed names index matches the native scripts cache'),
                         ns.check_names_index(CACHE))
        cached = ns.load(CACHE, allow_uncached=True)
        symbols = ns.symbols_from_names_index(ns.load_names_index())
        self.assertEqual(cached['classes'], symbols['classes'])
        self.assertEqual(cached['types'], symbols['types'])
        names = set(symbols['global_functions']) | {'Slot', 'NotAGlobal'}
        self.assertEqual(enforce_lint.native_global_functions(CACHE, names),
                         {n: set(v) for n, v in symbols['global_functions'].items() if n in names})


class FallbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_resolve_prefers_the_cache_and_falls_back_to_the_committed_index(self):
        symbols, origin = ns.resolve(self.root / 'absent')
        self.assertEqual('names-index', origin)
        self.assertIn('PlayerBase', symbols['classes'])
        scripts = fixture(self.root / 'scripts')
        with patch.object(ns, 'load', return_value={'classes': {}, 'types': {}}) as load:
            self.assertEqual('cache', ns.resolve(scripts)[1])
        load.assert_called_once()

    def test_check_skips_without_the_cache_and_compares_when_present(self):
        status, reason = ns.check_names_index(self.root / 'absent')
        self.assertEqual('SKIP', status)
        self.assertIn('needs-host-check', reason)
        scripts = fixture(self.root / 'scripts')
        names = self.root / 'names.json'
        self.assertEqual('FAIL', ns.check_names_index(scripts, self.root / 'missing.json')[0])
        ns.emit_names_index(scripts, names)
        self.assertEqual('PASS', ns.check_names_index(scripts, names)[0])
        (scripts / '3_Game/sample.c').write_text(SOURCE + '\nclass Extra {}\n')
        self.assertEqual('FAIL', ns.check_names_index(scripts, names)[0])

    def test_enforce_lint_summary_says_names_index(self):
        output = io.StringIO()
        with patch.object(enforce_lint.es, 'mod_sources', return_value=[]), \
                patch.object(enforce_lint, 'run_perf', return_value=False), \
                contextlib.redirect_stdout(output):
            code = enforce_lint.main(['--root', str(self.root), '--native-scripts', str(self.root / 'absent')])
        self.assertEqual(0, code)
        self.assertIn('native=names-index', output.getvalue())
        self.assertIsNotNone(enforce_lint.native_cache(str(self.root / 'absent')))

    def test_enforce_lint_without_native_stays_no(self):
        output = io.StringIO()
        with patch.object(enforce_lint.es, 'mod_sources', return_value=[]), \
                patch.object(enforce_lint, 'run_perf', return_value=False), \
                contextlib.redirect_stdout(output):
            enforce_lint.main(['--root', str(self.root), '--no-native'])
        self.assertIn('native=no', output.getvalue())

    def test_class_index_falls_back_without_writing_a_cache(self):
        output = io.StringIO()
        with patch.object(class_index, 'write_index') as write, contextlib.redirect_stdout(output):
            code = class_index.main(['--addons', str(self.root / 'absent')])
        self.assertEqual(0, code)
        write.assert_not_called()
        self.assertIn('names-index', output.getvalue())
        rows = class_index.script_class_names()
        self.assertEqual('ManBase', rows['PlayerBase'])


if __name__ == '__main__':
    unittest.main()
