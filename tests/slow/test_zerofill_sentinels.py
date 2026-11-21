"""#188 follow-ups to #177: sentinel/string lint stays strict, comments stay honest.

Offline source checks only. They do not establish native JsonFileLoader behaviour;
only int zero-fill was observed (leads.json TraceVersion), never bool/float/string.
"""
import re
import unittest
from pathlib import Path

from tools.validate import enforce_lint as lint
from tools.validate import enforce_source as es

ROOT = Path(__file__).resolve().parents[2]
# Built from pieces so this file never matches its own scan.
MARKER = re.compile('boot' + r'\s+' + '05' + '7', re.I)
OVERCLAIM = re.compile(r'\bscalars?\b|\bprimitives?\b|bool|float|string', re.I)
HONEST = re.compile(r'\bints?\b', re.I)


class ZeroFillSentinels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.findings = lint.lint(es.mod_sources(ROOT))

    def test_sentinel_and_string_readers_named_in_188_are_not_baselined(self):
        symbols = {f.symbol for f in self.findings if f.rule == 'HC-S005'}
        baselined = {e['symbol'] for e in lint.load_baseline()['entries'] if e['rule'] == 'HC-S005'}
        for name in ('HCTerritoryOutcomeRow.LeftSurvivors', 'HCTerritoryOutcomeRow.RightSurvivors',
                     'HCHordeRecord.Living', 'HCHordeRecord.Reserved', 'HCHordeRecord.AdoptionStage',
                     'HCSituationState.Phase', 'HCWorldHoldout.State', 'HCAIPartyCustodyRow.Outcome'):
            with self.subTest(name=name):
                self.assertNotIn(name, symbols)
                self.assertNotIn(name, baselined)

    def test_boot_comments_claim_only_observed_int_zero_fill(self):
        roots = [ROOT / 'mods', ROOT / 'tests']
        checked = 0
        for base in roots:
            for path in sorted(base.rglob('*')):
                if path.suffix not in {'.c', '.py'} or not path.is_file():
                    continue
                lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
                for index, line in enumerate(lines):
                    if not MARKER.search(line):
                        continue
                    checked += 1
                    window = '\n'.join(lines[max(0, index - 3):index + 4])
                    with self.subTest(path=str(path.relative_to(ROOT)), line=index + 1):
                        self.assertRegex(window, HONEST, 'must say only ints were observed')
                        self.assertIsNone(re.search(r'\bscalars?\b|\bprimitives?\b', window, re.I),
                                          'must not generalise the observation beyond ints')
        self.assertGreater(checked, 0, 'the observation scan must exercise current comments')


if __name__ == '__main__':
    unittest.main()
