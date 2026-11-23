"""Pitfall cards: deterministic, complete against the rule tables and the cited comments, and checkable."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from tools.validate import pitfall_cards as cards

SYNTHETIC = '''class Sample
{
    // build 161: unowned call results passed straight into Check were released mid-call.
    void A()
    {
    }
    // #12 design note: the picker keeps a finite list; nothing failed here.
    void B()
    {
        int x = 1; // #77 access violation when the handle is stale
    }
    // #5 first line of a note
    // that continues and says the native compile failed with Unknown type.
    void C()
    {
    }
}
'''


def synthetic_root(directory, name='HCSample.c'):
    folder = Path(directory) / 'mods/HollowCountry/scripts/4_World'
    folder.mkdir(parents=True)
    (folder / name).write_text(SYNTHETIC)
    return Path(directory)


class PitfallCardTests(unittest.TestCase):
    def test_generation_is_deterministic(self):
        self.assertEqual(cards.build_cards(cards.ROOT), cards.build_cards(cards.ROOT))
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            self.assertEqual(cards.build_cards(synthetic_root(one)), cards.build_cards(synthetic_root(two)))

    def test_every_rule_appears_on_exactly_one_card(self):
        built = cards.build_cards(cards.ROOT)
        for rule_id, message in cards.rule_tables().items():
            owners = [name for name, text in built.items() if f'| {rule_id} | ' in text]
            self.assertEqual([cards.rule_card(rule_id)], owners, rule_id)
            self.assertIn(cards.cell(message), built[owners[0]])

    def test_every_perf_and_lint_table_is_included(self):
        from tools.validate import enforce_lint, enforce_perf
        self.assertTrue(set(enforce_lint.RULES) <= set(cards.rule_tables()))
        self.assertTrue(set(enforce_perf.RULES) <= set(cards.rule_tables()))
        self.assertTrue(all(cards.rule_card(r) == 'perf-tick' for r in enforce_perf.RULES if r not in cards.RULE_CARD))

    def test_every_cited_native_failure_comment_appears_on_exactly_one_card(self):
        built = cards.build_cards(cards.ROOT)
        found = cards.native_failure_comments(cards.ROOT)
        self.assertTrue(found)
        for path, text in found:
            hits = sum(card.count('- ' + text + '\n') for card in built.values())
            self.assertEqual(1, hits, path)

    def test_compile_pitfalls_are_on_the_enforce_card_and_cards_are_stable_names(self):
        built = cards.build_cards(cards.ROOT)
        self.assertEqual(set(cards.CARDS), set(built))
        for title, _ in cards.COMPILE_PITFALLS:
            self.assertIn(title, built['enforce-pitfalls'])
        self.assertIn('## Native compile pitfalls the lint cannot see', built['enforce-pitfalls'])
        for rule in ('HC-E042', 'HC-E043', 'HC-E044', 'HC-E045', 'HC-E046', 'HC-E047'):
            self.assertIn(rule, built['enforce-pitfalls'])

    def test_comment_selection_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            found = cards.native_failure_comments(synthetic_root(directory))
        texts = ' '.join(text for _, text in found)
        self.assertIn('build 161', texts)
        self.assertIn('#77 access violation', texts)
        self.assertIn('Unknown type', texts)
        self.assertNotIn('design note', texts)
        self.assertEqual({'mods/HollowCountry/scripts/4_World/HCSample.c'}, {path for path, _ in found})

    def test_cards_are_generated_and_headings_carry_no_line_numbers(self):
        for text in cards.build_cards(cards.ROOT).values():
            self.assertTrue(text.startswith(cards.MARKER))
            self.assertNotRegex(text, r'(?m)^### .*:\d+')

    def test_committed_cards_match_fresh_generation(self):
        self.assertEqual([], cards.check_cards(cards.ROOT, cards.OUT))

    def test_check_detects_hand_edits_missing_and_stale_files_and_write_repairs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = synthetic_root(directory)
            self.assertIn('enforce-pitfalls.md missing', cards.check_cards(root, cards.OUT))
            cards.write_cards(root, cards.OUT)
            self.assertEqual([], cards.check_cards(root, cards.OUT))
            folder = root / cards.OUT
            with (folder / 'persistence.md').open('a') as handle:
                handle.write('hand edit\n')
            (folder / 'extra.md').write_text('stale\n')
            problems = cards.check_cards(root, cards.OUT)
            self.assertEqual(2, len(problems))
            cards.write_cards(root, cards.OUT)
            self.assertEqual([], cards.check_cards(root, cards.OUT))
            self.assertFalse((folder / 'extra.md').exists())

    def test_each_card_has_a_skill_that_points_at_it(self):
        for name in cards.CARDS:
            skill = cards.ROOT / '.claude/skills' / ('hc-' + name) / 'SKILL.md'
            text = skill.read_text()
            self.assertIn('name: hc-' + name + '\n', text)
            self.assertIn('docs/pitfalls/' + name + '.md', text)
            self.assertTrue((cards.ROOT / cards.OUT / (name + '.md')).is_file())
        for name in ('hc-brief', 'hc-preland'):
            self.assertIn('name: ' + name + '\n', (cards.ROOT / '.claude/skills' / name / 'SKILL.md').read_text())

    def test_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = synthetic_root(directory)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(1, cards.main(['--check', '--root', str(root)]))
                self.assertEqual(0, cards.main(['--root', str(root)]))
                self.assertEqual(0, cards.main(['--check', '--root', str(root)]))
            self.assertIn('pitfall_cards: pass', out.getvalue())


if __name__ == '__main__':
    unittest.main()
