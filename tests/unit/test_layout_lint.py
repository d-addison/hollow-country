"""Synthetic layouts exercise validation; no offline check establishes rendering."""
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path

from tools.validate import layout_lint

ROOT = Path(__file__).resolve().parents[2]


class LayoutSyntax(unittest.TestCase):
    def test_braces_ignore_quoted_text_and_comments(self):
        names, findings = layout_lint.lint_layout('FrameWidgetClass Root { text "{ hi }" // }\n }')
        self.assertEqual({'Root'}, names)
        self.assertEqual([], findings)
        for text in ('FrameWidgetClass Root {', 'FrameWidgetClass Root { }}'):
            self.assertTrue(any('brace' in f for f in layout_lint.lint_layout(text)[1]))

    def test_unknown_class_and_duplicate_names_are_errors(self):
        _, findings = layout_lint.lint_layout('MadeUpWidgetClass A { } TextWidgetClass A { }')
        self.assertTrue(any('unknown widget class' in f for f in findings))
        self.assertTrue(any('duplicate widget name' in f for f in findings))

    def tree(self, layout='FrameWidgetClass Root { { TextWidgetClass Label { } } }', script=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        addon = root / 'mods/HollowCountry'
        (addon / 'gui/layouts').mkdir(parents=True)
        (addon / 'scripts/5_Mission').mkdir(parents=True)
        (addon / 'gui/layouts/test.layout').write_text(layout)
        (addon / 'scripts/5_Mission/Test.c').write_text(script or '''
            Widget root = workspace.CreateWidgets("HollowCountry/gui/layouts/test.layout");
            root.FindAnyWidget("Label");
        ''')
        return root

    def test_lookup_must_exist_in_the_loaded_layout(self):
        root = self.tree(script='w.CreateWidgets("HollowCountry/gui/layouts/test.layout"); w.FindAnyWidget("Missing");')
        self.assertTrue(any('Missing' in f and 'lookup' in f for f in layout_lint.lint_tree(root)))
        self.assertEqual([], layout_lint.lint_tree(self.tree()))

    def test_unrelated_layout_cannot_satisfy_lookup(self):
        root = self.tree(script='w.CreateWidgets("HollowCountry/gui/layouts/test.layout"); w.FindWidget("Other");')
        (root / 'mods/HollowCountry/gui/layouts/unloaded.layout').write_text('TextWidgetClass Other { }')
        self.assertTrue(any('Other' in f and 'lookup' in f for f in layout_lint.lint_tree(root)))

    def borrowed_tree(self):
        root = self.tree(script='root.FindAnyWidget("Label");')
        loader = 'mods/HollowCountry/scripts/5_Mission/Loader.c'
        layout = 'HollowCountry/gui/layouts/test.layout'
        (root / loader).write_text(f'w.CreateWidgets("{layout}");')
        consumer = 'mods/HollowCountry/scripts/5_Mission/Test.c'
        declarations = {consumer: [(layout, loader, (), 'Loader passes its root to Test.')]}
        return root, declarations, consumer, loader

    def test_reviewed_borrowed_root_checks_real_names(self):
        root, declarations, consumer, _ = self.borrowed_tree()
        self.assertEqual([], layout_lint.lint_tree(root, declarations))
        (root / consumer).write_text('root.FindAnyWidget("Missing");')
        self.assertTrue(any('Missing' in f and 'borrowed root' in f
                            for f in layout_lint.lint_tree(root, declarations)))

    def test_borrowed_loader_must_actually_load_the_layout(self):
        root, declarations, _, loader = self.borrowed_tree()
        (root / loader).write_text('// no layout loaded')
        self.assertTrue(any('does not load' in f for f in layout_lint.lint_tree(root, declarations)))
        (root / loader).unlink()
        self.assertTrue(any('invalid borrowed-root' in f for f in layout_lint.lint_tree(root, declarations)))

    def test_consumer_can_load_child_widgets_beside_borrowed_root(self):
        root, declarations, consumer, _ = self.borrowed_tree()
        child = 'HollowCountry/gui/layouts/child.layout'
        (root / 'mods' / child).write_text('TextWidgetClass ChildLabel { }')
        with (root / consumer).open('a') as output:
            output.write(f'w.CreateWidgets("{child}"); child.FindAnyWidget("ChildLabel");')
        self.assertEqual([], layout_lint.lint_tree(root, declarations))

    def test_each_borrowed_root_is_checked_with_explicit_optional_names(self):
        root, declarations, consumer, loader = self.borrowed_tree()
        smaller = 'HollowCountry/gui/layouts/smaller.layout'
        (root / 'mods' / smaller).write_text('FrameWidgetClass Root { }')
        with (root / loader).open('a') as output:
            output.write(f'w.CreateWidgets("{smaller}");')
        declarations[consumer].append((smaller, loader, (), 'Smaller root has no label.'))
        self.assertTrue(any('borrowed root ' + smaller in f
                            for f in layout_lint.lint_tree(root, declarations)))
        declarations[consumer][-1] = (smaller, loader, ('Label',), 'Label is optional on the smaller root.')
        self.assertEqual([], layout_lint.lint_tree(root, declarations))
        # Optional declarations cannot hide a name missing from every root.
        (root / consumer).write_text('root.FindAnyWidget("Missing");')
        declarations[consumer] = [(smaller, loader, ('Missing',), 'Optional synthetic field.')]
        self.assertTrue(any('Missing' in f and 'lookup' in f
                            for f in layout_lint.lint_tree(root, declarations)))

    def test_dotted_lookup_checks_ancestry(self):
        root = self.tree(script='w.CreateWidgets("HollowCountry/gui/layouts/test.layout"); w.FindWidget("Wrong.Label");')
        self.assertTrue(any('Wrong.Label' in f for f in layout_lint.lint_tree(root)))

    def test_missing_or_unshipped_layout_is_reported(self):
        root = self.tree(script='w.CreateWidgets("HollowCountry/gui/layouts/gone.layout");')
        self.assertTrue(any('missing layout' in f for f in layout_lint.lint_tree(root)))
        root = self.tree(script='w.CreateWidgets("HollowCountry/gui/layouts/nested/test.layout");')
        nested = root / 'mods/HollowCountry/gui/layouts/nested'
        nested.mkdir()
        (nested / 'test.layout').write_text('FrameWidgetClass Root { }')
        self.assertTrue(any('not shipped' in f for f in layout_lint.lint_tree(root)))

    def test_comment_lookups_do_not_count(self):
        root = self.tree(script='// w.FindWidget("Ghost");\nw.CreateWidgets("HollowCountry/gui/layouts/test.layout"); /* w.FindWidget("Ghost"); */')
        self.assertEqual([], layout_lint.lint_tree(root))

    def test_command_line_script_runs_from_another_directory(self):
        root = self.tree()
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/validate/layout_lint.py'),
                                 '--root', str(root)], cwd=root, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('layouts=1 findings=0', result.stdout)

    def test_every_layout_and_lookup_is_clean(self):
        self.assertEqual([], layout_lint.lint_tree(ROOT))
