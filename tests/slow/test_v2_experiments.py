"""V2 experiment register (LC-T002, V2 core issue).

Every V2 feature with a Gate experiment keeps Qualified() false until the
register records a GO (or accepted FALLBACK) verdict with the build, date,
evidence and artifacts that support it. The register is evidence bookkeeping,
not evidence: an offline test never establishes DayZ behaviour, so the shipped
register is all PENDING until a native session records a verdict.

TDD record (2026-11-17): RED before tools/validate/experiments.py existed:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.slow.test_v2_experiments
failed with ImportError: cannot import name 'experiments' from 'tools.validate'.
"""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools.validate import experiments as ex

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / 'docs/experiments/v2-experiments.json'
EXPECTED = {
    'EXP-P1', 'EXP-P2', 'EXP-D1',
    'EXP-A1', 'EXP-A2', 'EXP-A3', 'EXP-A4', 'EXP-A5',
    'EXP-T1', 'EXP-T2', 'EXP-T3', 'EXP-T4', 'EXP-T5',
    'EXP-S1', 'EXP-S2', 'EXP-S3', 'EXP-S4',
    'EXP-L1', 'EXP-L2', 'EXP-L3', 'EXP-L4', 'EXP-L5', 'EXP-L6', 'EXP-L7', 'EXP-L8', 'EXP-L9',
    'EXP-POL-1', 'EXP-POL-2',
}


def shipped():
    return json.loads(REGISTER.read_text())


def decided(entry, verdict='GO'):
    entry.update(Verdict=verdict, Build='1.30.164289', Date='2026-11-18',
                 Evidence='server log lines observed in a DayZDiag session',
                 Artifacts=['local-only/exp-p1-20261118.log sha256=' + '0' * 64])
    return entry


class RegisterTests(unittest.TestCase):
    def test_shipped_register_seeds_all_28_experiments_pending(self):
        data = shipped()
        self.assertEqual([], ex.validate(data))
        ids = [e['Id'] for e in data['Experiments']]
        self.assertEqual(28, len(ids))
        self.assertEqual(EXPECTED, set(ids))
        # No native experiment has run: only EXP-D1, a terms and version review
        # rather than an engine run, may carry a verdict.
        self.assertEqual({'PENDING'}, {e['Verdict'] for e in data['Experiments'] if e['Id'] != 'EXP-D1'})
        for entry in data['Experiments']:
            with self.subTest(id=entry['Id']):
                self.assertTrue(entry['Question'].strip())
                self.assertTrue(entry['Method'].strip())
                self.assertTrue(entry['Fallback'].strip())
                self.assertEqual(entry['Id'] == 'EXP-D1', ex.qualified(data, entry['Id']))

    def test_a_verdict_without_build_date_evidence_or_artifacts_is_refused(self):
        for field, bad in (('Build', ''), ('Date', ''), ('Evidence', ''), ('Artifacts', []),
                           ('Date', '18/11/2026'), ('Build', 'latest')):
            for verdict in ('GO', 'NO-GO', 'FALLBACK'):
                with self.subTest(field=field, bad=bad, verdict=verdict):
                    data = shipped()
                    entry = decided(data['Experiments'][0], verdict)
                    self.assertEqual([], ex.validate(data))
                    entry[field] = bad
                    errors = ex.validate(data)
                    self.assertTrue(any(field in e for e in errors), errors)

    def test_pending_entries_carry_no_verdict_fields(self):
        data = shipped()
        data['Experiments'][0]['Build'] = '1.30.164289'
        self.assertTrue(any('PENDING' in e for e in ex.validate(data)))

    def test_shape_errors_are_refused(self):
        cases = {
            'unknown verdict': lambda d: d['Experiments'][0].update(Verdict='PASS'),
            'duplicate': lambda d: d['Experiments'].append(copy.deepcopy(d['Experiments'][0])),
            'missing': lambda d: d['Experiments'].pop(),
            'unknown id': lambda d: d['Experiments'][0].update(Id='EXP-X9'),
            'unknown field': lambda d: d['Experiments'][0].update(Passed=True),
            'empty question': lambda d: d['Experiments'][0].update(Question=' '),
            'schema': lambda d: d.update(SchemaVersion=2),
            'not a list': lambda d: d.update(Experiments={}),
        }
        for name, mutate in cases.items():
            with self.subTest(name):
                data = shipped()
                mutate(data)
                self.assertTrue(ex.validate(data), name)
        self.assertTrue(ex.validate([]))

    def test_only_go_or_accepted_fallback_qualifies_a_gate(self):
        for verdict, expected in (('GO', True), ('FALLBACK', True), ('NO-GO', False)):
            with self.subTest(verdict=verdict):
                data = shipped()
                decided(next(e for e in data['Experiments'] if e['Id'] == 'EXP-A1'), verdict)
                self.assertEqual([], ex.validate(data))
                self.assertEqual(expected, ex.qualified(data, 'EXP-A1'))
                self.assertFalse(ex.qualified(data, 'EXP-A2'))
        with self.assertRaises(KeyError):
            ex.qualified(shipped(), 'EXP-X9')
        # An invalid register qualifies nothing, even a well-formed GO entry.
        data = shipped()
        decided(data['Experiments'][0])
        data['Experiments'][1]['Verdict'] = 'PASS'
        self.assertFalse(ex.qualified(data, data['Experiments'][0]['Id']))

    def test_cli_reports_counts_and_refuses_an_invalid_file(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(0, ex.main([]))
        self.assertIn('experiments=28 pending=27 go=0 fallback=1 no-go=0', out.getvalue())
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder) / 'bad.json'
            data = shipped()
            data['Experiments'][0]['Verdict'] = 'GO'
            bad.write_text(json.dumps(data))
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                self.assertEqual(1, ex.main(['--register', str(bad)]))
            self.assertIn('EXP-', err.getvalue())
            bad.write_text('{not json')
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(1, ex.main(['--register', str(bad)]))


if __name__ == '__main__':
    unittest.main()
