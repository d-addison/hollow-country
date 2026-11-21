"""Small synthetic AST fixtures; no repository suite imports or execution."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.validate.test_audit import analyze, audit


class TestAuditTests(unittest.TestCase):
    def test_categories_and_assertion_evidence_without_executing_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'tests/unit'
            folder.mkdir(parents=True)
            fixtures = {
                'source': '''from pathlib import Path
import unittest
class T(unittest.TestCase):
 def test_source(self):
  src = Path('mods/thing.c').read_text()
  self.assertIn('class Thing', src)
''',
                'snapshot': '''from pathlib import Path
import json
import unittest
class T(unittest.TestCase):
 def test_snapshot(self):
  data = json.loads(Path('config/rows.json').read_text())
  self.assertEqual(len(data), 12)
''',
                'behavior': '''import unittest
raise RuntimeError('must never execute')
class T(unittest.TestCase):
 def test_sum(self):
  values = [1, 2, 3]
  self.assertEqual(sum(values), sum(reversed(values)))
''',
                'contract': '''import unittest
class T(unittest.TestCase):
 def test_wire(self):
  # External contract: peer protocol version.
  self.assertEqual(encode_version(), 3)
''',
                'synthetic_data': '''import tempfile
import unittest
class T(unittest.TestCase):
 def setUp(self):
  self.tmp = tempfile.TemporaryDirectory()
 def test_synthetic_xml_count(self):
  filename = 'invented.xml'
  self.assertEqual(len([filename]), 1)
''',
                'tooling_source': '''import importlib
import tempfile
import unittest
class T(unittest.TestCase):
 def test_linter(self):
  tool = importlib.import_module('tools.validate.enforce_lint')
  with tempfile.TemporaryDirectory() as temp:
   filename = 'invented.c'
   self.assertEqual(tool.check(filename), [])
''',
                'broken': '''from tools.does_not_exist import run
import unittest
class T(unittest.TestCase):
 def test_missing(self):
  self.assertTrue(run())
''',
            }
            for name, source in fixtures.items():
                (folder / ('test_' + name + '.py')).write_text(source)
            report = audit(root)
            rows = {Path(row['path']).stem: row for row in report['files']}
            for name, category in (('source', 'A'), ('snapshot', 'B'), ('behavior', 'C'), ('contract', 'E'), ('synthetic_data', 'C'), ('tooling_source', 'C')):
                self.assertEqual(rows['test_' + name]['tests'][0]['category'], category)
            self.assertEqual(rows['test_broken']['categories']['D'], 1)
            self.assertEqual(rows['test_source']['tests'][0]['assertions'], {'assertIn': 1})
            self.assertEqual(rows['test_source']['tests'][0]['literal_operands'], 1)
            self.assertEqual(json.dumps(report, sort_keys=True), json.dumps(audit(root), sort_keys=True))

    def test_parse_errors_and_helpers_are_accounted_for(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'broken.py'
            path.write_text('def test_bad(:')
            self.assertEqual(analyze(path, root)['categories'], {'D': 0})
            path.write_text('return 1')
            self.assertEqual(analyze(path, root)['categories'], {'D': 0})
            path.write_text('def helper():\n return 1\n')
            self.assertEqual(analyze(path, root)['tests'], [])

    def test_local_helper_reads_are_followed_without_tainting_other_methods(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'mixed.py'
            path.write_text('''from pathlib import Path
import unittest
def source():
 return Path('mods/a.c').read_text()
class T(unittest.TestCase):
 def test_source(self):
  self.assertIn('void Tick()', source())
 def test_roundtrip(self):
  values = [1, 2]
  self.assertEqual(values, list(values))
''')
            rows = analyze(path, root)['tests']
            self.assertEqual([r['category'] for r in rows], ['A', 'C'])
