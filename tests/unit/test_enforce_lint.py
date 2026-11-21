"""Synthetic dependency-boundary fixtures; no engine behaviour claims."""
import unittest

from tools.validate import enforce_lint as lint


W = 'mods/HollowCountryExpansionAI/scripts/4_World/'


class ExpansionBridgeRule(unittest.TestCase):
    def findings(self, text, support='', path=W + 'Caller.c'):
        files = {path: text}
        if support:
            files[W + 'Types.c'] = support
        return lint.lint_texts(files, rules=(lint.rule_expansion_bridge,))

    def test_static_and_generic_calls_require_bridge(self):
        for call in ('eAIFaction.Create("Guards")',
                     'eAIBase.eAI_GetAll()',
                     'ExpansionAISpawnBase.GetPlacementPosition(vector.Zero)',
                     'GetExpansionSettings().GetAI()',
                     'eAIDynamicPatrolT<HCXPatrol>.CreateEx(config, vector.Zero)'):
            with self.subTest(call=call):
                result = self.findings('class HCProbe { void Run() { ' + call + '; } }')
                self.assertEqual(['HC-E022'], [f.rule for f in result])
                self.assertIn('HCXExpansionBridge', result[0].message)

    def test_static_calls_in_initializers_require_bridge(self):
        for text in ('class HCProbe { ref eAIFaction Faction = eAIFaction.Create("Guards"); }',
                     'ref array<eAIBase> Actors = eAIBase.eAI_GetAll();',
                     'class HCProbe { eAIGroup Party; int Size = Party.Count(); }'):
            with self.subTest(text=text):
                self.assertEqual(['HC-E022'], [f.rule for f in self.findings(text)])

    def test_parameter_local_field_and_inherited_field_receivers(self):
        fixtures = [
            'class HCProbe { void Run(eAIGroup party) { party.Count(); } }',
            'class HCProbe { void Run() { eAIGroup party; party.Count(); } }',
            'class HCProbe { eAIGroup Party; void Run() { Party.Count(); } }',
            'class HCBase { eAIGroup Party; } class HCProbe : HCBase { void Run() { Party.Count(); } }',
            'class HCHolder { eAIGroup Party; } class HCProbe { HCHolder Holder; void Run() { Holder.Party.Count(); } }',
            'class HCProbe { void Run(array<eAIBase> actors) { actors[0].IsAlive(); } }',
            'class HCProbe { void Run(array<ref eAIBase> actors) { actors[0].IsAlive(); } }',
            'class HCProbe { void Run(array<eAIBase> actors) { actors.Get(0).IsAlive(); } }',
            'class HCProbe { void Run(Object entity) { auto actor = eAIBase.Cast(entity); actor.GetPosition(); } }',
            'class HCProbe { void Run(Object entity) { eAIBase.Cast(entity).GetTarget(); } }',
            'class HCProbe { void Run(eAIGroup party) { (party).Count(); } }',
            'class HCActor : eAIBase {} class HCProbe { void Run(HCActor actor) { actor.GetPosition(); } }',
            'class HCPatrol : eAIDynamicPatrol {} class HCProbe { void Run(HCPatrol patrol) { patrol.m_Group.Count(); } }',
        ]
        for text in fixtures:
            with self.subTest(text=text):
                result = self.findings(text)
                self.assertEqual(['HC-E022'], [f.rule for f in result])

    def test_result_chains_and_player_extension_ports(self):
        for text, calls in (
            ('class HCProbe { void Run(PlayerBase player) { player.GetGroup().Count(); } }',
             ['player.GetGroup', 'player.GetGroup().Count']),
            ('class HCProbe { eAIGroup Party() { return null; } void Run() { Party().Count(); } }',
             ['Party().Count']),
        ):
            with self.subTest(text=text):
                result = self.findings(text)
                self.assertEqual(calls, [f.message.split(' (')[0] for f in result])

    def test_implicit_and_super_provider_calls(self):
        for call in ('SetLooseness(0)', 'this.SetLooseness(0)', 'super.SetLooseness(0)'):
            with self.subTest(call=call):
                result = self.findings('class HCFormation : eAIFormation { void Run() { ' + call + '; } }')
                self.assertEqual(['HC-E022'], [f.rule for f in result])

    def test_pure_types_casts_attributes_comments_and_engine_receivers_are_allowed(self):
        text = '''
        [eAIRegisterFaction(eAIFactionHCLocal)]
        class eAIFactionHCLocal : eAIFaction {}
        class HCProbe {
            eAIGroup Party;
            void Run(Object entity, PlayerBase player) {
                eAIBase actor = eAIBase.Cast(entity);
                Class.CastTo(actor, entity);
                entity.IsInherited(eAIBase);
                player.GetPosition();
                string example = "eAIBase.eAI_GetAll()";
                // Party.Count();
                /* eAIFaction.Create(""); */
            }
        }'''
        self.assertEqual([], self.findings(text))

    def test_hc_methods_and_hc_override_forwarding_are_allowed(self):
        text = '''
        class HCFormation : eAIFormation {
            void Configure() {}
            override vector GetPosition(int member) { return vector.Zero; }
        }
        modded class HCFormation {
            override vector GetPosition(int member) { return super.GetPosition(member); }
            void Run() { Configure(); this.Configure(); }
        }'''
        self.assertEqual([], self.findings(text))

    def test_hc_prefix_alone_does_not_bypass_boundary(self):
        result = self.findings('class HCProbe { void Run(eAIBase actor) { actor.HCUnknown(); } }')
        self.assertEqual(['HC-E022'], [f.rule for f in result])

    def test_only_the_owned_bridge_path_is_exempt(self):
        text = 'class HCProbe { void Run() { eAIBase.eAI_GetAll(); } }'
        self.assertEqual([], self.findings(text, path=lint._EXPANSION_BRIDGE))
        for path in (W + 'Other/HCXExpansionBridge.c',
                     'mods/Other/scripts/4_World/HCXExpansionBridge.c'):
            with self.subTest(path=path):
                self.assertEqual(['HC-E022'], [f.rule for f in self.findings(text, path=path)])

    def test_local_shadow_and_non_expansion_methods_do_not_inherit_type(self):
        text = '''class HCOrdinary { void Count() {} }
        class HCProbe { eAIGroup Party; void Run() { HCOrdinary Party; Party.Count(); } }'''
        self.assertEqual([], self.findings(text))


if __name__ == '__main__':
    unittest.main()
