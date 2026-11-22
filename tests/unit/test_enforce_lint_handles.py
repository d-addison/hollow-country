"""Synthetic fixtures for HC-E041; no engine behaviour claims."""
import unittest

from tools.validate import enforce_lint as lint
from tools.validate import enforce_lint_handles as handles

W = 'mods/HollowCountryExpansionAI/scripts/4_World/'


class StoredHandleRule(unittest.TestCase):
    def findings(self, body, path=W + 'Holder.c'):
        text = f'class HCHolder {{ {body} }}'
        return [f for f in lint.lint_texts({path: text}, rules=(lint.rule_stored_handles,))]

    def test_member_with_and_without_ref(self):
        for decl in ('eAIGroup Group;', 'ref eAIGroup Group;', 'autoptr eAIGroup Group;',
                     'protected eAIGroup Group;'):
            with self.subTest(decl=decl):
                found = self.findings(decl)
                self.assertEqual(['HC-E041'], [f.rule for f in found])
                self.assertEqual('HCHolder.Group', found[0].symbol)

    def test_static_member(self):
        self.assertEqual(['HC-E041'], [f.rule for f in self.findings('static eAIGroup s_Last;')])

    def test_container_element_types(self):
        for decl in ('ref array<eAIGroup> Groups = new array<eAIGroup>();',
                     'ref array<ref eAIGroup> Groups;',
                     'ref map<int, eAIGroup> ByWave;',
                     'ref map<string, ref eAIGroup> ByName;'):
            with self.subTest(decl=decl):
                self.assertEqual(['HC-E041'], [f.rule for f in self.findings(decl)])

    def test_strong_agent_member(self):
        for decl in ('ref eAIBase Leader;', 'autoptr eAIBase Leader;', 'ref array<ref eAIBase> Crew;'):
            with self.subTest(decl=decl):
                self.assertEqual(['HC-E041'], [f.rule for f in self.findings(decl)])

    def test_plain_agent_members_and_handles_are_allowed(self):
        for decl in ('eAIBase Leader;', 'ref array<eAIBase> Crew;', 'ref HCXAIGroupHold Hold;',
                     'eAIGroupSettings Other;', 'ref array<HCeAIGroup> Wrapped;'):
            with self.subTest(decl=decl):
                self.assertEqual([], self.findings(decl))

    def test_locals_and_parameters_are_allowed(self):
        body = ('void Run(eAIGroup party) { eAIGroup group = party; ref array<eAIGroup> tmp; } '
                'static bool Check(eAIGroup party, eAIBase leader) { eAIBase actor = leader; return true; }')
        self.assertEqual([], self.findings(body))

    def test_bridge_file_is_allowed(self):
        self.assertEqual([], self.findings('protected ref eAIGroup Group;', path=handles.BRIDGE_FILE))

    def test_comment_and_string_do_not_count(self):
        self.assertEqual([], self.findings('// eAIGroup Group;\n string note = "eAIGroup Group;";'))

    def test_rule_is_registered_and_described(self):
        self.assertIn(lint.rule_stored_handles, lint.ALL_RULES)
        self.assertIn('HC-E041', lint.RULES)


if __name__ == '__main__':
    unittest.main()
