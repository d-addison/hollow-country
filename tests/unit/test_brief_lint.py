"""Brief linter: the good fixture passes, each historical-shape bad fixture fails for its own reason."""
from pathlib import Path
import contextlib
import io
import unittest

from tools.validate import brief_lint

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/fixtures/briefs'
TEMPLATE = ROOT / 'docs/briefs/TEMPLATE.md'


def codes(name):
    return {f.code for f in brief_lint.lint((FIXTURES / name).read_text())}


def replace(text, old, new):
    assert old in text
    return text.replace(old, new, 1)


class BriefLintTests(unittest.TestCase):
    def good(self):
        return (FIXTURES / 'good.md').read_text()

    def test_good_brief_passes(self):
        self.assertEqual([], brief_lint.lint(self.good()))

    def test_bad_without_invariants_or_failure_table_or_review_line(self):
        found = codes('bad_no_invariants.md')
        self.assertEqual({'HC-B001', 'HC-B007'}, found)
        messages = ' '.join(f.message for f in brief_lint.lint((FIXTURES / 'bad_no_invariants.md').read_text()))
        for needed in ('invariants', 'failure table', 'required evidence', 'Design review'):
            self.assertIn(needed, messages)

    def test_bad_owned_files_described_not_listed(self):
        self.assertEqual({'HC-B003'}, codes('bad_unlisted_files.md'))

    def test_bad_failure_table_without_handling_column(self):
        self.assertEqual({'HC-B004', 'HC-B005', 'HC-B007'}, codes('bad_failure_table.md'))

    def test_every_rule_code_is_documented(self):
        for name in ('bad_no_invariants.md', 'bad_unlisted_files.md', 'bad_failure_table.md'):
            self.assertTrue(codes(name) <= set(brief_lint.RULES))

    def test_each_required_section_is_enforced(self):
        text = self.good()
        for section in ('Goal', 'Owned files', 'Invariants', 'Failure table', 'Required evidence',
                        'Base branch', 'Checks', 'Report format'):
            broken = replace(text, '## ' + section, '## Renamed ' + section)
            self.assertIn('HC-B001', {f.code for f in brief_lint.lint(broken)}, section)

    def test_placeholder_invariant_and_table_cell_rejected(self):
        text = self.good()
        self.assertIn('HC-B002', {f.code for f in brief_lint.lint(replace(text, '1. A torn file is preserved once per revision; a second boot never creates a second copy.', '1. <statement>'))})
        self.assertIn('HC-B004', {f.code for f in brief_lint.lint(replace(text, '| Compare by byte count, copy, then delete the original |', '| TBD |'))})

    def test_review_line_needs_reviewer_and_date_for_review_kinds_only(self):
        text = self.good()
        self.assertIn('HC-B007', {f.code for f in brief_lint.lint(replace(text, 'Design review: Opus 2026-11-20', 'Design review: Opus'))})
        self.assertIn('HC-B007', {f.code for f in brief_lint.lint(replace(text, 'Design review: Opus 2026-11-20\n', ''))})
        fix = replace(replace(text, 'Kind: persistence', 'Kind: fix'), 'Design review: Opus 2026-11-20\n', '')
        # A fix that owns a journal file must still declare a review kind.
        self.assertIn('HC-B007', {f.code for f in brief_lint.lint(fix)})
        quiet = replace(fix, 'HCEventJournal.c', 'HCEventTicker.c')
        self.assertEqual([], brief_lint.lint(quiet))

    def test_evidence_and_base_branch_rules(self):
        text = self.good()
        self.assertIn('HC-B005', {f.code for f in brief_lint.lint(replace(text, '[HC Use] module=Events', 'the boot is clean module=Events'))})
        self.assertIn('HC-B006', {f.code for f in brief_lint.lint(replace(text, 'dev at 2d2c075c.', 'some branch'))})
        tooling = replace(text, 'Kind: persistence', 'Kind: tooling')
        tooling = replace(tooling, 'Design review: Opus 2026-11-20\n', '')
        tooling = tooling.replace('HCEventJournal.c', 'HCEventTicker.c').replace('HCEventRuntime.c', 'HCEventTicker2.c')
        tooling = replace(tooling, '`[HC Use] module=Events feature=journal_repair count=1`', 'none: tooling only, no runtime line')
        self.assertEqual([], brief_lint.lint(tooling))

    def test_checks_follow_owned_file_types(self):
        text = self.good()
        self.assertIn('HC-B008', {f.code for f in brief_lint.lint(replace(text, 'tools.validate.hygiene', 'tools.validate.other'))})
        self.assertIn('HC-B008', {f.code for f in brief_lint.lint(replace(text, 'enforce_perf', 'enforce_other'))})

    def test_broad_or_absolute_owned_paths_rejected(self):
        text = self.good()
        for path in ('mods/**', '*.c', '/abs/path/File.c'):
            broken = replace(text, '`tests/unit/test_example_journal.py`', f'`{path}`')
            self.assertIn('HC-B003', {f.code for f in brief_lint.lint(broken)}, path)

    def test_peer_overlap_detected_and_disjoint_accepted(self):
        self.assertEqual([], brief_lint.peer_findings({'a': ['mods/X/A.c'], 'b': ['mods/X/B.c', 'docs/pitfalls/**']}))
        found = brief_lint.peer_findings({'a': ['mods/X/A.c'], 'b': ['mods/X/*.c']})
        self.assertEqual(['HC-B010'], [f.code for _, f in found])
        self.assertTrue(brief_lint.peer_findings({'a': ['docs/**'], 'b': ['docs/pitfalls/**']}))

    def test_template_has_every_section_and_fails_as_unfilled(self):
        text = TEMPLATE.read_text()
        found = {f.message for f in brief_lint.lint(text) if f.code == 'HC-B001'}
        self.assertEqual(set(), found)
        self.assertNotEqual([], brief_lint.lint(text))

    def test_cli_exit_codes(self):
        for name, expected in (('good.md', 0), ('bad_unlisted_files.md', 1)):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(expected, brief_lint.main([str(FIXTURES / name)]))
            self.assertIn('brief_lint: ' + ('pass' if expected == 0 else 'fail'), out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(1, brief_lint.main([str(FIXTURES / 'missing.md')]))
        self.assertIn('unreadable', out.getvalue())


if __name__ == '__main__':
    unittest.main()
