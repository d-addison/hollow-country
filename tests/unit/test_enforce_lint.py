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


class FreshArgumentOwnershipTests(unittest.TestCase):
    def findings(self, body, support=''):
        factory = '''
        class HCFactory {
            static array<float> Make() { return new array<float>; }
            static array<float> Local() { array<float> values = new array<float>; return values; }
            static array<float> Forward() { return Local(); }
            static HCThing Object() { return new HCThing; }
            static array<float> Borrow() { return Saved; }
            static array<float> Saved;
        }
        class HCThing {}
        '''
        return lint.lint_texts({W + 'Ownership.c': factory + support + body},
                               rules=(lint.rule_fresh_arguments,))

    def test_two_fresh_collections_are_errors_and_single_results_warn(self):
        result = self.findings('''class HCUse { void Run() {
            Check(HCFactory.Make(), HCFactory.Forward());
            Check(HCFactory.Local()); Check(HCFactory.Object());
        } }''')
        self.assertEqual(['error', 'error', 'warning', 'warning'], [f.severity for f in result])
        self.assertTrue(all(f.rule == 'HC-E026' for f in result))

    def test_declared_ref_adoption_and_shadowed_or_unrelated_insert(self):
        for collection, expected in [('array<ref HCThing>', []),
                                      ('array<HCThing>', ['HC-E026']),
                                      ('HCSink', ['HC-E026'])]:
            with self.subTest(collection=collection):
                result = self.findings('class HCUse { void Run() { ' + collection +
                                       ' sink; sink.Insert(HCFactory.Object()); } }',
                                       'class HCSink { void Insert(HCThing value) {} }')
                self.assertEqual(expected, [f.rule for f in result])
        self.assertEqual([], self.findings('''class HCUse {
            void Run(array<ref HCThing> sink) { sink.InsertAt(HCFactory.Object(), 0); }
        }'''))
        self.assertEqual(['HC-E026'], [f.rule for f in self.findings('''class HCUse {
            ref array<ref HCThing> sink;
            void Run() { { array<HCThing> sink; sink.Insert(HCFactory.Object()); } }
        }''')])

    def test_borrowed_locals_scalars_and_compound_expressions_are_not_fresh_arguments(self):
        self.assertEqual([], self.findings('''class HCUse { void Run() {
            array<float> held = HCFactory.Make(); Check(held);
            Check(HCFactory.Borrow()); Check(HCFactory.Make().Count() > 0);
            // Check(HCFactory.Make());
            string text = "Check(HCFactory.Make())";
        } }'''))

    def test_typed_inherited_receiver_and_forwarding_cycle(self):
        result = self.findings('''class HCBase { HCFactory factory; }
        class HCUse : HCBase { void Run() { Check(factory.Forward()); Check(HCCycle.Make()); } }
        class HCCycle { static array<float> Make() { return Other(); }
                       static array<float> Other() { return Make(); } }''')
        self.assertEqual(['HC-E026', 'HC-O026'], [f.rule for f in result])

    def test_unresolved_receiver_is_separate_and_never_an_error(self):
        result = self.findings('class HCUse { void Run() { Check(unknown.Make()); } }')
        self.assertEqual(['HC-O026'], [f.rule for f in result])
        self.assertEqual('warning', result[0].severity)

    def test_result_receivers_aliases_and_class_results(self):
        result = self.findings('''typedef array<ref HCThing> HCThings;
        class HCUse {
            HCUse Self() { return this; }
            void Run(HCThings adopted) {
                Self().Consume(HCFactory.Make());
                adopted.Insert(HCFactory.Object());
                Check(HCFactory.Object(), HCFactory.Make());
            }
        }''')
        self.assertEqual(['warning', 'warning', 'warning'], [f.severity for f in result])
        self.assertTrue(all(f.rule == 'HC-E026' for f in result))

    def test_unrelated_factory_name_and_mixed_local_are_not_guessed_fresh(self):
        result = self.findings('''class HCOther {
            array<float> Saved;
            array<float> Make() { return Saved; }
            array<float> Mixed(bool useSaved) {
                array<float> value = new array<float>;
                if (useSaved) { value = Saved; }
                return value;
            }
            void Run() { Check(Make()); Check(Mixed(true)); }
        }''')
        self.assertEqual(['HC-O026'], [f.rule for f in result])

    def test_crash_shape_cannot_be_hidden_by_a_baseline(self):
        findings = self.findings('class HCUse { void Run() { Check(HCFactory.Make(), HCFactory.Local()); } }')
        baseline = lint.baseline_from(findings, 'synthetic review')
        new, _ = lint.compare(findings, baseline, False)
        self.assertEqual(findings, new)


    def test_map_insert_uses_declared_value_slot(self):
        for kind, expected in [('map<string, ref HCThing>', []),
                               ('map<string, HCThing>', ['HC-E026'])]:
            with self.subTest(kind=kind):
                result = self.findings('class HCUse { void Run(' + kind + ' items) {'
                                       'items.Insert("key", HCFactory.Object()); } }')
                self.assertEqual(expected, [f.rule for f in result])


    def test_class_field_initializers_are_checked(self):
        result = self.findings("class HCUse { HCThing held = Consume(HCFactory.Object()); }")
        self.assertEqual(['HC-E026'], [f.rule for f in result])
        self.assertEqual('HCUse.<initializer:held>', result[0].symbol)

    def test_parameter_receivers_keep_each_generic_type_and_ref_slot(self):
        result = self.findings('''class HCUse {
            void Run(array<float> source, array<ref HCThing> sorted,
                     map<string, ref HCThing> adopted) {
                Check(source.Get(0)); Check(source.Count());
                sorted.Insert(HCFactory.Object()); adopted.Insert("key", HCFactory.Object());
                Check(unknown.Make());
            }
        }''')
        self.assertEqual(['HC-O026'], [f.rule for f in result])
        self.assertIn('unknown.Make', result[0].key)

    def test_member_index_and_cast_aliases_are_borrowed(self):
        self.assertEqual([], self.findings('''class HCUse {
            ref array<ref HCThing> Saved;
            HCThing Indexed() { return Saved[0]; }
            HCThing Local() { HCThing held = Saved[0]; return held; }
            HCThing CastLocal() { HCThing held = HCThing.Cast(Saved[0]); return held; }
            HCThing GetLocal() { HCThing held = Saved.Get(0); return held; }
            void Run() { Check(Indexed()); Check(Local()); Check(CastLocal()); Check(GetLocal()); }
        }'''))

    def test_foreach_alias_requires_retained_iterable_and_no_fresh_write(self):
        result = self.findings('''class HCUse {
            ref array<ref HCThing> Saved;
            HCThing Borrow() {
                foreach (HCThing held : Saved) { return held; }
                return null;
            }
            HCThing Temporary() {
                array<ref HCThing> values = new array<ref HCThing>;
                foreach (HCThing held : values) { return held; }
                return null;
            }
            HCThing Reassigned() {
                foreach (HCThing held : Saved) { held = new HCThing; return held; }
                return null;
            }
            void Run() {
                Check(Borrow());
                Check(Temporary());
                Check(Reassigned());
            }
        }''')
        self.assertEqual(['HC-O026', 'HC-E026'], [f.rule for f in result])

    def test_qualified_static_field_and_foreach_member_chain_are_retained(self):
        self.assertEqual([], self.findings('''class HCHolder {
            ref HCThing Item;
            static ref HCHolder Saved;
            static HCThing StaticItem() { return HCHolder.Saved.Item; }
        }
        class HCUse {
            ref array<ref HCHolder> Saved;
            HCThing Member() {
                foreach (HCHolder held : Saved) { return held.Item; }
                return null;
            }
            void Run() { Check(Member()); Check(HCHolder.StaticItem()); }
        }'''))

    def test_fresh_parent_unknown_out_and_alias_cycles_stay_unresolved(self):
        result = self.findings('''class HCHolder { ref HCThing Item; }
        class HCUse {
            HCThing FreshParent() { HCHolder held = new HCHolder; return held.Item; }
            HCThing UnknownOut() { HCThing held; Load(held); return held; }
            HCThing ReassignedParameter(HCHolder held) { held = new HCHolder; return held.Item; }
            HCThing AliasCycle() { HCThing first = second; HCThing second = first; return first; }
            void Run() {
                Check(FreshParent()); Check(UnknownOut()); Check(AliasCycle());
                Check(ReassignedParameter(null));
            }
        }''')
        self.assertEqual(['HC-O026', 'HC-O026', 'HC-O026', 'HC-O026'], [f.rule for f in result])

    def test_local_alias_mixed_allocation_is_never_resolved_as_borrowed(self):
        result = self.findings('''class HCUse {
            ref array<ref HCThing> Saved;
            HCThing Mixed(bool fresh) {
                HCThing held = Saved[0];
                if (fresh) { held = new HCThing; }
                return held;
            }
            void Run() { Check(Mixed(true)); }
        }''')
        self.assertEqual(['HC-O026'], [f.rule for f in result])

    def test_native_inventory_getters_are_borrowed_only_on_declared_receiver(self):
        self.assertEqual([], self.findings('''class HCUse {
            HCThing Held(PlayerBase player) { return HCThing.Cast(player.GetItemInHands()); }
            HCThing Worn(PlayerBase player) {
                HCThing held = HCThing.Cast(player.FindAttachmentBySlotName("Back"));
                return held;
            }
            void Run(PlayerBase player) { Check(Held(player)); Check(Worn(player)); }
        }'''))
        result = self.findings('''class PlayerBase {
            HCThing GetItemInHands() { return new HCThing; }
        }
        class HCUse {
            HCThing Held(PlayerBase player) { return player.GetItemInHands(); }
            void Run(PlayerBase player) { Check(Held(player)); }
        }''')
        self.assertEqual(['HC-E026'], [f.rule for f in result])
        result = self.findings('''class HCOther {
            HCThing GetItemInHands() { HCThing value; Load(value); return value; }
        }
        class HCUse {
            HCThing Held(HCOther player) { return player.GetItemInHands(); }
            void Run(HCOther player) { Check(Held(player)); }
        }''')
        self.assertEqual(['HC-O026'], [f.rule for f in result])

    def test_pinned_native_recipe_field_is_scoped_and_local_shadowing_wins(self):
        self.assertEqual([], self.findings('''modded class PluginRecipesManager {
            HCThing Registered() { HCThing recipe = m_RecipeList[0]; return recipe; }
            void Run() { Check(Registered()); }
        }'''))
        result = self.findings('''class HCOther {
            HCThing Registered() { HCThing recipe = m_RecipeList[0]; return recipe; }
            void Run() { Check(Registered()); }
        }
        modded class PluginRecipesManager {
            HCThing Temporary() {
                array<ref HCThing> m_RecipeList = new array<ref HCThing>;
                return m_RecipeList[0];
            }
            void Run() { Check(Temporary()); }
        }''')
        self.assertEqual(['HC-O026', 'HC-O026'], [f.rule for f in result])

    def test_out_and_unknown_calls_can_replace_borrowed_local(self):
        result = self.findings('''class HCUse {
            ref array<ref HCThing> Saved;
            void Replace(out HCThing value) { value = new HCThing; }
            HCThing Output() { HCThing held = Saved[0]; Replace(held); return held; }
            HCThing Unknown() { HCThing held = Saved[0]; Load(held); return held; }
            void Run() { Check(Output()); Check(Unknown()); }
        }''')
        self.assertEqual(['HC-O026', 'HC-O026'], [f.rule for f in result])


if __name__ == '__main__':
    unittest.main()
