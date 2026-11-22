"""Synthetic coverage for the overlay stack engine; these checks do not establish DayZ behavior."""
import itertools
import unittest

from tools.package import ce_extensions, overlay_stack, rag_optional

Layer, Stack = overlay_stack.Layer, overlay_stack.Stack


class StackOrderTests(unittest.TestCase):
    def layers(self):
        return [Layer('c', 'f/c', (('types.xml', 'types'),), after=('b',)),
                Layer('b', 'f/b', (('events.xml', 'events'),), after=('a',)),
                Layer('a', 'f/a'),
                Layer('z')]

    def test_order_is_independent_of_registration_order(self):
        results = {tuple(layer.name for layer in Stack(p).ordered())
                   for p in itertools.permutations(self.layers())}
        self.assertEqual(len(results), 1)
        order = results.pop()
        for earlier, later in (('a', 'b'), ('b', 'c')):
            self.assertLess(order.index(earlier), order.index(later))

    def test_soft_after_ignores_absent_layers_but_requires_does_not(self):
        self.assertEqual([x.name for x in Stack([Layer('x', after=('missing',))]).ordered()], ['x'])
        with self.assertRaisesRegex(ValueError, 'requires missing layer'):
            Stack([Layer('x', requires=('missing',))]).ordered()

    def test_cycle_is_refused(self):
        stack = Stack([Layer('a', after=('b',)), Layer('b', after=('a',))])
        with self.assertRaisesRegex(ValueError, 'cycle'):
            stack.ordered()

    def test_registrations_follow_stack_order_and_skip_folderless_layers(self):
        regs = Stack(self.layers()).registrations()
        self.assertEqual(list(regs), ['f/a', 'f/b', 'f/c'])
        self.assertEqual(regs['f/b'], {'events.xml': 'events'})


class StackConflictTests(unittest.TestCase):
    def refused(self, pattern, *layers):
        with self.assertRaisesRegex(ValueError, pattern):
            Stack(layers).ordered()

    def test_duplicate_layer_name(self):
        self.refused('duplicate overlay layer', Layer('a'), Layer('a'))

    def test_folder_claimed_twice_ignoring_case(self):
        self.refused('claimed twice', Layer('a', 'Mod/ce'), Layer('b', 'mod/CE'))

    def test_unsafe_folders(self):
        for folder in ('/abs', '../up', 'a//b', 'a/./b', 'a\\b', 'c:x'):
            self.refused('unsafe overlay folder', Layer('a', folder))

    def test_file_registration_problems(self):
        self.refused('unsupported overlay file kind', Layer('a', 'f', (('x.xml', 'bogus'),)))
        self.refused('invalid or duplicate', Layer('a', 'f', (('x.xml', 'types'), ('X.xml', 'types'))))
        self.refused('invalid or duplicate', Layer('a', 'f', (('d/x.xml', 'types'),)))
        self.refused('without a folder', Layer('a', '', (('x.xml', 'types'),)))

    def test_self_dependency(self):
        self.refused('depends on itself', Layer('a', after=('a',)))

    def test_class_collisions_are_case_insensitive_and_sorted(self):
        with self.assertRaisesRegex(ValueError, 'ClassB, classa'):
            overlay_stack.refuse_class_collisions(iter(['classa', 'ClassB', 'new']), ['ClassA', 'classb'])
        overlay_stack.refuse_class_collisions(['new'], ['ClassA'])


class ConsumerTests(unittest.TestCase):
    def test_ce_extensions_registrations_come_from_one_valid_stack(self):
        stack = ce_extensions._stack()
        stack.ordered()
        regs = ce_extensions._registrations()
        self.assertEqual(regs, stack.registrations())
        self.assertTrue(regs)
        for files in regs.values():
            self.assertTrue(set(files.values()) <= set(overlay_stack.KINDS))
        self.assertEqual(list(regs), list(ce_extensions._registrations()))

    def test_ce_extensions_still_admits_and_refuses_by_folder(self):
        folder = next(iter(ce_extensions._registrations()))
        ce_extensions.checked_core(('<economycore><ce folder="%s"/></economycore>' % folder).encode())
        with self.assertRaisesRegex(ValueError, 'reconciliation'):
            ce_extensions.checked_core(b'<economycore><ce folder="operator/ce"/></economycore>')
        with self.assertRaisesRegex(ValueError, 'duplicate or unsupported'):
            ce_extensions.checked_core(
                ('<economycore><ce folder="%s"/><ce folder="%s"/></economycore>' % (folder, folder)).encode())
        with self.assertRaisesRegex(ValueError, 'already defined'):
            ce_extensions.refuse_collisions(['Same'], ['same'])

    def test_rag_packs_apply_in_stack_order(self):
        calls = []
        saved = dict(rag_optional._APPLY)
        try:
            for name in saved:
                rag_optional._APPLY[name] = lambda *a, n=name: calls.append(n)
            rag_optional.append_types({name: None for name in saved}, None, None, None, None, None)
        finally:
            rag_optional._APPLY.update(saved)
        self.assertEqual(calls, [layer.name for layer in rag_optional.STACK.ordered()])
        self.assertEqual(set(calls), {name for name, _ in rag_optional.OVERLAY_PACKS})
        self.assertLess(calls.index('RaGVehicles'), calls.index('Navigation'))


if __name__ == '__main__':
    unittest.main()
