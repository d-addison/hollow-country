"""Offline tooling checks for the compat stringtable generator; not DayZ behaviour."""
import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.package import compat_stringtable as table


class StringtableTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def strings(self, rows, schema=table.SCHEMA):
        path = self.root / 'strings.json'
        path.write_text(json.dumps({'schema': schema, 'strings': rows}))
        return path

    def test_committed_strings_load(self):
        pairs = table.load()
        self.assertEqual(len(pairs), len({key.casefold() for key, _ in pairs}))
        blob, keys = table.build()
        self.assertEqual(blob is None, not keys)

    def test_empty_list_writes_no_table(self):
        self.assertEqual((None, []), table.build(self.strings([])))

    def test_render_is_deterministic_and_complete(self):
        rows = [{'key': 'STR_Zeta', 'text': 'Last, "quoted"'}, {'key': 'STR_alpha', 'text': 'First'}]
        blob, keys = table.build(self.strings(rows))
        self.assertEqual(['STR_alpha', 'STR_Zeta'], keys)
        self.assertEqual(blob, table.build(self.strings(list(reversed(rows))))[0])
        parsed = list(csv.reader(io.StringIO(blob.decode('utf-8'), newline='')))
        self.assertEqual(list(table.HEADER), parsed[0])
        self.assertEqual(['STR_alpha'] + ['First'] * len(table.LANGUAGES), parsed[1])
        self.assertEqual('Last, "quoted"', parsed[2][1])
        self.assertTrue(all(len(row) == len(table.HEADER) for row in parsed))

    def test_invalid_rows_are_refused(self):
        bad = [
            [{'key': 'NotStr_x', 'text': 'x'}],
            [{'key': 'STR_x', 'text': ''}],
            [{'key': 'STR_x', 'text': 'line\nbreak'}],
            [{'key': 'STR_x', 'text': 'a'}, {'key': 'STR_X', 'text': 'b'}],
            [{'key': 'STR_x', 'text': 'a', 'extra': 1}],
            [{'key': 'STR_x', 'text': 'a' * (table.MAX_TEXT + 1)}],
            'not a list',
        ]
        for rows in bad:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                table.load(self.strings(rows))
        with self.assertRaises(ValueError):
            table.load(self.strings([], schema=table.SCHEMA + 1))

    def test_missing_keys_come_from_localization_lines_only(self):
        rpt = self.root / 'rpt.log'
        rpt.write_text('\n'.join([
            'GUI string STR_one not found in stringtable',
            'Warning: stringtable lookup failed for $STR_Two',
            'GUI string STR_one not found in stringtable',
            'No entry STR_unrelated.scope',
            'x' * (table.rpt_config_audit.MAX_LINE + 10) + ' STR_huge not found in stringtable',
            'ok',
        ]))
        self.assertEqual(['STR_one', 'STR_Two'], table.missing_keys([rpt]))

    def test_cli_reports_uncovered_and_refuses_existing_output(self):
        rpt = self.root / 'rpt.log'
        rpt.write_text('GUI string STR_one not found in stringtable\nGUI string STR_two not found in stringtable\n')
        strings = self.strings([{'key': 'STR_one', 'text': 'One'}])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = table.main(['--strings', str(strings), '--rpt', str(rpt), '--out', str(self.root / 'a.csv')])
        self.assertEqual(0, code)
        self.assertIn('uncovered=1', out.getvalue())
        self.assertIn('uncovered STR_two', out.getvalue())
        self.assertTrue((self.root / 'a.csv').is_file())
        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stderr(io.StringIO()):
            table.main(['--strings', str(strings), '--out', str(self.root / 'a.csv')])
        self.assertEqual(1, raised.exception.code)


if __name__ == '__main__':
    unittest.main()
