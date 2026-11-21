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



class NativeCompileRetroRules(unittest.TestCase):
    path = 'mods/HollowCountry/scripts/4_World/Probe.c'

    def check_rule(self, text, rule, symbols=None):
        source = lint.es.Source(self.path, text)
        return lint.lint([source], rules=(rule,), symbols=symbols)

    def test_intervening_statement_breaks_else(self):
        for chain in (
            'if (a) X(); HCModuleReadiness.HCUse("M", "f");\nelse {}',
            'if (a) {} Foo();\nelse if (b) {}',
            'if (a) X(); else if (b) Y(); Foo();\nelse {}',
            'if (a) { if (b) X(); Foo();\nelse Y(); }',
        ):
            text = 'class HCProbe { void Run() {\n' + chain + '\n} }'
            with self.subTest(chain=chain):
                result = self.check_rule(text, lint.rule_broken_else)
                self.assertEqual(['HC-E023'], [f.rule for f in result])
                self.assertEqual(self.path, result[0].path)
                self.assertEqual(text[:text.rindex('else')].count('\n') + 1, result[0].line)

    def test_adjacent_else_and_nested_statements_are_allowed(self):
        for chain in (
            'if (a) X(); else Y();',
            'if (a) {} else if (b) {} else {}',
            'if (a) if (b) X(); else Y(); else Z();',
            'if (a) while (b) X(); else Y();',
            'if (a) for (int i = 0; i < 2; i++) { X(); } else Y();',
            'switch (a) { case 1: if (b) X(); else Y(); break; default: break; }',
            'if (a) { X(); Foo(); } /* else X(); */ else { Y(); }',
            'if (a) X("else"); else Y();',
            'if (a) do { X(); } while (b); else Y();',
        ):
            with self.subTest(chain=chain):
                self.assertEqual([], self.check_rule('class HCProbe { void Run() { ' + chain + ' } }',
                                                    lint.rule_broken_else))

    def test_typename_null_return_is_rejected(self):
        for value in ('null', 'NULL'):
            text = 'class HCProbe {\nstatic typename Kind() {\nreturn ' + value + ';\n} }'
            result = self.check_rule(text, lint.rule_typename_null)
            self.assertEqual(['HC-E024'], [f.rule for f in result])
            self.assertEqual(text[:text.index('return ' + value)].count('\n') + 1, result[0].line)

    def test_empty_typename_and_object_null_are_allowed(self):
        text = '''class HCProbe {
            typename Kind() { typename refused; return refused; }
            Object Entity() { return null; }
            typename Literal() { Print("return null;"); /* return NULL; */ return HCProbe; }
        }'''
        self.assertEqual([], self.check_rule(text, lint.rule_typename_null))

    def test_native_global_and_class_collisions(self):
        symbols = {'classes': {'Queue': [{'layer': 0}]}, 'globals': {'Print': {0}}}
        for name in ('Queue', 'Print'):
            text = 'class HCProbe {\nvoid ' + name + '(int x) {}\nvoid Run() { ' + name + '(1); } }'
            result = self.check_rule(text, lint.rule_native_named_methods, symbols)
            self.assertEqual(['HC-E025'], [f.rule for f in result])
            self.assertEqual(text[:text.index(name)].count('\n') + 1, result[0].line)
            self.assertIn(name, result[0].message)

    def test_observed_queue_collision_is_pinned_without_native_sources(self):
        text = 'class HCProbe { void Queue(int x) {} void Run() { Queue(1); } }'
        result = self.check_rule(text, lint.rule_native_named_methods)
        self.assertEqual(['HC-E025'], [f.rule for f in result])

    def test_same_class_modded_body_call_counts_but_other_class_does_not(self):
        symbols = {'globals': {'Global': {0}}}
        declaration = 'class HCProbe { void Global() {} }'
        same = declaration + 'modded class HCProbe { void Run() { Global(); } }'
        other = declaration + 'class HCOther { void Run() { Global(); } }'
        self.assertEqual(['HC-E025'], [f.rule for f in self.check_rule(
            same, lint.rule_native_named_methods, symbols)])
        self.assertEqual([], self.check_rule(other, lint.rule_native_named_methods, symbols))

    def test_native_collision_exclusions(self):
        symbols = {'classes': {'Queue': [{'layer': 0}], 'EngineBase': [{'layer': 0}]},
                   'globals': {'Print': {0}, 'Future': {4}}}
        for text in (
            'class HCProbe : EngineBase { override void Queue(int x) {} void Run() { Queue(1); } }',
            'modded class EngineBase { override void Print(int x) {} void Run() { Print(1); } }',
            'class Queue { void Queue() {} void Run() { new Queue(); } }',
            'class HCProbe { void Queue() {} void Run() { this . Queue(); other.Queue(); new Queue (); } }',
            'class HCProbe { void Queue() {} void Run() { Print("Queue()"); /* Queue(); */ } }',
            'class HCProbe { void Future() {} void Run() { Future(); } }',
            'class HCProbe { void Local() {} void Run() { Local(); } }',
        ):
            with self.subTest(text=text):
                self.assertEqual([], self.check_rule(text, lint.rule_native_named_methods, symbols))

    def test_native_global_census_uses_only_global_proto_or_native(self):
        import tempfile
        from pathlib import Path
        text = '''proto native void Global(int x);
        native void\n            Other();
        class Engine { proto void Member(); }
        void Script() {}
        // proto void Comment();
        '''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '1_Core').mkdir()
            (root / '1_Core' / 'Native.c').write_text(text)
            names = {'Global', 'Other', 'Member', 'Script', 'Comment'}
            result = lint.native_global_functions(root, names)
        self.assertEqual({'Global': {0}, 'Other': {0}}, result)

if __name__ == '__main__':
    unittest.main()
