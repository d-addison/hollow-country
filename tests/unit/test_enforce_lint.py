"""Synthetic dependency-boundary fixtures; no engine behaviour claims."""
import json
import tempfile
import unittest

from tools.validate import enforce_lint as lint


W = 'mods/HollowCountryExpansionAI/scripts/4_World/'


class BooleanStringFormulaRule(unittest.TestCase):
    def findings(self, body, rules=None):
        return lint.lint_texts({W + 'Formula.c':
                               f'class HCProbe {{ bool Run() {{ {body} }} }}'},
                               rules=rules or (lint.rule_boolean_string_formula,))

    def expression(self, count, concat='path != "prefix" + suffix'):
        return ' || '.join([concat] + [f'flag{i}' for i in range(count - 1)])

    def test_threshold_for_if_while_and_return(self):
        threshold = lint.MIN_STRING_BOOLEAN_TERMS
        for count in (threshold - 1, threshold, threshold + 1):
            for wrapper in ('if ({}) {{}}', 'while ({}) {{}}', 'return {};'):
                with self.subTest(count=count, wrapper=wrapper):
                    findings = self.findings(wrapper.format(self.expression(count)))
                    self.assertEqual(['HC-E030'] if count >= threshold else [],
                                     [f.rule for f in findings])
                    if findings:
                        self.assertIn(f'{count} boolean terms', findings[0].message)

    def test_nested_mixed_operators_multiline_and_concat_direction(self):
        for concat in ('path != suffix + ".json"', 'path != ("prefix") + suffix',
                       'path != suffix + (".json")'):
            expression = self.expression(lint.MIN_STRING_BOOLEAN_TERMS, concat)
            expression = '(' + expression.replace(' || ', ') &&\n(') + ')'
            findings = self.findings('if (\n' + expression + '\n) {}')
            self.assertEqual(['HC-E030'], [f.rule for f in findings])
            self.assertEqual([1], [f.line for f in findings])

    def test_long_conditions_without_inline_concat_pass(self):
        for term in ('path != expectedPath', 'value + 1 > limit',
                     'Contains("literal + || &&", value + 1)', 'value++ > limit'):
            self.assertEqual([], self.findings(
                'if (' + self.expression(lint.MIN_STRING_BOOLEAN_TERMS + 1, term) + ') {}'))

    def test_comments_literals_and_separate_expressions_do_not_combine(self):
        long = self.expression(lint.MIN_STRING_BOOLEAN_TERMS)
        short = self.expression(lint.MIN_STRING_BOOLEAN_TERMS - 1)
        self.assertEqual([], self.findings(
            '// if (' + long + ') {}\n/* return ' + long + '; */\n'
            'string example = "if (a || b + c) return";\n'
            'if (' + short + ') {} while (' + short + ') {} return ' + short + ';'))
        self.assertEqual([], self.findings('if (' + self.expression(
            lint.MIN_STRING_BOOLEAN_TERMS, 'flag /* "literal" + value */') + ') {}'))

    def test_build_167_shape_and_default_rule_registration(self):
        expression = '''!page || !pinned || page.Path != "prefix" + suffix + ".json"
            || page.Bytes < 1 || page.Bytes > 32768 || page.Rows < 1 || page.Rows > 64
            || page.Sha256.Length() != 64 || page.IdentitySha256.Length() != 64
            || pinned.IdentitySha256 != page.IdentitySha256 || pinned.Path != page.Path
            || pinned.Bytes != page.Bytes || pinned.Rows != page.Rows
            || pinned.Sha256 != page.Sha256'''
        findings = self.findings('if (' + expression + ') {}', rules=lint.ALL_RULES)
        self.assertIn('HC-E030', [f.rule for f in findings])


class DuplicateLocalRule(unittest.TestCase):
    def findings(self, body, parameters=''):
        return lint.lint_texts({W + 'Locals.c':
                               f'class HCProbe {{ void Run({parameters}) {{ {body} }} }}'},
                               rules=(lint.rule_duplicate_locals,))

    def test_same_scope_and_auto_redeclarations(self):
        for body in ('bool retainedTmp; string retainedTmp;',
                     'int value; auto value = Factory();',
                     'auto value = Factory(); int value;',
                     'int value; Load(out int value);'):
            with self.subTest(body=body):
                findings = self.findings(body)
                self.assertEqual(['HC-E029'], [f.rule for f in findings])
                self.assertIn('local at line', findings[0].message)

    def test_nested_and_sibling_blocks_are_function_scoped(self):
        for body in ('int value; if (true) { int value; }',
                     'if (true) { int value; } int value;',
                     'if (true) { int value; } else { int value; }',
                     'for (int i = 0; i < 2; i++) {} for (int i = 0; i < 2; i++) {}',
                     'for (int i = 0; i < 2; i++) { int i; }'):
            with self.subTest(body=body):
                self.assertEqual(['HC-E029'], [f.rule for f in self.findings(body)])

    def test_parameter_shadow_including_out_and_generic_parameters(self):
        for parameters, body in (('int value', 'int value;'),
                                  ('out int value', '{ auto value = Factory(); }'),
                                  ('map<string, ref Thing> values', 'array<Thing> values;')):
            with self.subTest(parameters=parameters):
                findings = self.findings(body, parameters)
                self.assertEqual(['HC-E029'], [f.rule for f in findings])
                self.assertIn('first declared as parameter', findings[0].message)

    def test_foreach_slots_and_grouped_declarations(self):
        for body in ('int value; foreach (Thing value : values) {}',
                     'foreach (int key, Thing value : values) {} int key; int value;',
                     'int first = Factory(1, 2), value = 3; int value;',
                     'ref map<string, ref Thing> first = Factory(), value; Thing value;',
                     'map <string, ref Thing> first = Factory(), value; Thing value;',
                     'int first[2], value[3]; int value;'):
            with self.subTest(body=body):
                findings = self.findings(body)
                expected = ['key', 'value'] if 'int key;' in body else ['value']
                self.assertCountEqual(expected, [f.message.split(':')[0] for f in findings])

    def test_comments_strings_references_and_assignments_are_ignored(self):
        self.assertEqual([], self.findings('''
            int i; string example = "int i; foreach (int i : values) {}";
            int maxRise = 1; if (i < -2 || i > maxRise) {}
            // int i;
            /* auto i = Factory(); */
            for (i = 0; i < 2; i++) {} for (i = 0; i < 2; i++) {}
            Load(i); Load(out i); example = "int i;";
            foreach (int key, Thing value : values) { Use(key, value); }
        '''))

    def test_methods_fields_and_global_functions_have_separate_bindings(self):
        self.assertEqual([], lint.lint_texts({W + 'Locals.c': '''
            int value;
            void Global(int other) { int value; }
            class HCProbe {
                int value;
                void First() { int value; }
                void Second() { int value; }
            }
        '''}, rules=(lint.rule_duplicate_locals,)))
        findings = lint.lint_texts({W + 'Locals.c': 'void Global() { int value; int value; }'})
        self.assertIn('HC-E029', [f.rule for f in findings])

    def test_diagnostic_points_to_second_declaration(self):
        findings = self.findings('int value;\nfloat value;')
        self.assertEqual([2], [f.line for f in findings])
        self.assertTrue(all(f.severity == 'error' for f in findings))


class StaticConstLiteralRule(unittest.TestCase):
    def findings(self, text):
        return lint.lint_texts({W + 'Constants.c': text},
                               rules=(lint.rule_static_const_literals,))

    def test_single_literals_pass(self):
        for kind, values in (
            ('int', ('0', '16512', '-8', '+8', '0xFF')),
            ('float', ('0.0', '-1.25', '+.5', '2.', '1e-3')),
            ('bool', ('true', 'false')),
            ('string', ('""', '"hello;,+world"', r'"quote\" and slash\\"')),
        ):
            for value in values:
                with self.subTest(kind=kind, value=value):
                    self.assertEqual([], self.findings(
                        f'class Constants {{ static const {kind} VALUE = {value}; }}'))

    def test_cross_class_and_local_references_fail(self):
        for value in ('HCGroupIO.HC_RAW_READ_CAP', 'OTHER', 'int.MAX'):
            with self.subTest(value=value):
                findings = self.findings(f'class Constants {{ static const int VALUE = {value}; }}')
                self.assertEqual(['HC-E028'], [f.rule for f in findings])
                self.assertIn('initializer must be a literal', findings[0].message)
                self.assertIn('build 169', findings[0].message)

    def test_arithmetic_and_other_expressions_fail(self):
        for kind, value in (('int', '8 * (HCGroupIO.HC_RAW_READ_CAP / HC_CHUNK_BYTES) + 128'),
                            ('int', '8 * 2048 + 128'), ('float', '1.0 + 2.0'),
                            ('bool', '!false'), ('string', '"a" + "b"'),
                            ('int', '(16512)'), ('int', 'GetValue()')):
            with self.subTest(kind=kind, value=value):
                self.assertEqual(['HC-E028'], [f.rule for f in self.findings(
                    f'class Constants {{ static const {kind} VALUE = {value}; }}')])

    def test_comments_strings_and_nonstatic_constants_are_ignored(self):
        self.assertEqual([], self.findings('''
            // static const int BAD = 1 + 2;
            /* static const int BAD = Other.VALUE; */
            class Constants {
                string Example = "static const int BAD = 1 + 2;";
                const int INSTANCE = 1 + 2;
                static int MUTABLE = 1 + 2;
                static /* comment */ const int GOOD = - /* comment */ 8;
                static const string TEXT = "Other.VALUE + 2";
            }
        '''))

    def test_multiline_and_grouped_declarations(self):
        findings = self.findings('''
            class Constants {
                static const int GOOD = 1, BAD = Other.VALUE;
                static const float BAD_FLOAT =
                    2 * 4.0;
                const static bool BAD_BOOL = !true;
            }
        ''')
        self.assertEqual(['BAD', 'BAD_FLOAT', 'BAD_BOOL'], [f.symbol for f in findings])
        self.assertTrue(all(f.rule == 'HC-E028' for f in findings))

    def test_rule_is_enabled_by_default(self):
        findings = lint.lint_texts({W + 'Constants.c':
                                   'class Constants { static const int VALUE = 1 + 2; }'})
        self.assertIn('HC-E028', [f.rule for f in findings])


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




class DependencyBridgeRule(unittest.TestCase):
    def findings(self, text, support='', path=W + 'Caller.c', symbols=None):
        sources = [lint.es.Source(path, text)]
        if support:
            sources.append(lint.es.Source(W + 'Types.c', support))
        return lint.lint(sources, rules=(lint.rule_dependency_bridges,), symbols=symbols)

    def test_dependency_calls_route_to_their_owned_bridges(self):
        for call, bridge in (
            ('GetPermissionsManager()', lint._COT_BRIDGE),
            ('GetRPCManager()', lint._CF_BRIDGE),
            ('CF_Date.Timestamp(1970, 1, 1, 0, 0, 0)', lint._CF_BRIDGE),
            ('ExpansionStatic.GetTimestamp()', lint._EXPANSION_BRIDGE),
        ):
            text = 'class HCProbe { void Run() { ' + call + '; } }'
            with self.subTest(call=call):
                result = self.findings(text)
                self.assertEqual(['HC-E027'], [f.rule for f in result])
                self.assertIn(lint.Path(bridge).stem, result[0].message)
                self.assertEqual([], self.findings(text, path=bridge))
                self.assertTrue(self.findings(text, path=W + 'Other/' + lint.Path(bridge).name))

    def test_native_owner_and_inherited_methods_shadow_vendor_globals(self):
        symbols = {'classes': {
            'PlayerBase': [dict(layer=3, modded=False, parent='Man', methods={'Message': []}, fields={})],
            'Man': [dict(layer=3, modded=False, parent='', methods={'GetPlayer': []}, fields={})],
            'StateBase': [dict(layer=3, modded=False, parent='', methods={'GetPlayer': []}, fields={})],
            'ModifierBase': [dict(layer=3, modded=False, parent='', methods={'GetPlayer': []}, fields={})],
        }}
        for owner, call in (('PlayerBase', 'Message("a", "b")'),
                            ('PlayerBase', 'GetPlayer()'),
                            ('StateBase', 'GetPlayer()'), ('ModifierBase', 'GetPlayer()')):
            with self.subTest(owner=owner, call=call):
                self.assertEqual([], self.findings(
                    'modded class ' + owner + ' { void Run() { ' + call + '; } }', symbols=symbols))
        self.assertEqual(['HC-E027'], [f.rule for f in self.findings(
            'class HCProbe { void Run() { Message("a", "b"); } }', symbols=symbols)])

    def test_native_globals_shadow_vendor_globals_only_at_visible_layers(self):
        text = 'class HCProbe { void Run() { GetPlayer(); } }'
        self.assertEqual([], self.findings(text, symbols={'globals': {'GetPlayer': {0}}}))
        self.assertEqual(['HC-E027'], [f.rule for f in self.findings(
            text, symbols={'globals': {'GetPlayer': {4}}})])

    def test_authored_members_and_globals_shadow_vendor_globals(self):
        text = 'class HCProbe : HCBase { void Run() { GetPlayer(); Message("a", "b"); } }'
        support = 'class HCBase { void GetPlayer() {} } void Message(string a, string b) {}'
        self.assertEqual([], self.findings(text, support))

    def test_cf_aliases_and_legacy_names_precede_jm_prefix(self):
        for support, call in (
            ('typedef CF_Date JMDate;', 'JMDate()'),
            ('typedef CF_Date JMDate;', 'JMDate.Timestamp(1970, 1, 1, 0, 0, 0)'),
            ('typedef CF_Date JMDate; typedef JMDate COTDate;', 'COTDate()'),
            ('', 'JMDate()'),
            ('', 'JMModuleManager()'),
        ):
            text = 'class HCProbe { void Run() { ' + call + '; } }'
            with self.subTest(support=support, call=call):
                result = self.findings(text, support)
                self.assertEqual(['HC-E027'], [f.rule for f in result])
                self.assertIn('HCXCFBridge', result[0].message)
                self.assertEqual([], self.findings(text, support, path=lint._CF_BRIDGE))
                self.assertTrue(self.findings(text, support, path=lint._COT_BRIDGE))

    def test_baseline_data_round_trips_without_dependency_injection(self):
        baseline = lint.load_baseline()
        with tempfile.TemporaryDirectory() as folder:
            path = lint.Path(folder) / 'baseline.json'
            path.write_text(json.dumps(baseline), encoding='utf-8')
            self.assertEqual(baseline, lint.load_baseline(path))
            path.write_text('{"entries": []}', encoding='utf-8')
            self.assertEqual({'entries': []}, lint.load_baseline(path))
        # Any E027 rows that remain must still name their file (the original sites were
        # migrated to the bridge, so an empty set is a valid state, not a failure).
        for entry in (e for e in baseline['entries'] if e['rule'] == 'HC-E027'):
            self.assertIn(lint.Path(entry['path']).stem, entry['review'])
        # A synthetic E027 row survives the round trip unchanged and keeps its identity.
        synthetic = {'entries': [{'rule': 'HC-E027', 'path': W + 'Probe.c', 'symbol': 'HCProbe.Run',
                                  'key': 'Call()', 'count': 1, 'review': 'Probe: reviewed'}]}
        with tempfile.TemporaryDirectory() as folder:
            path = lint.Path(folder) / 'synthetic.json'
            path.write_text(json.dumps(synthetic), encoding='utf-8')
            self.assertEqual(synthetic, lint.load_baseline(path))


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


class WorkflowDefectRules(unittest.TestCase):
    """WD-L1..L5, L9, the ConfigGet rule and the unordered head Remove rule."""
    path = 'mods/HollowCountry/scripts/4_World/Probe.c'

    def check(self, text, rule):
        return lint.lint([lint.es.Source(self.path, text)], rules=(rule,))

    def rules(self, text, rule):
        return [f.rule for f in self.check(text, rule)]

    def body(self, text, extra=''):
        return extra + 'class HCProbe { void Run() {\n' + text + '\n} }'

    def test_every_new_rule_id_is_documented_once(self):
        for rule in ('HC-E031', 'HC-E032', 'HC-E033', 'HC-E034', 'HC-E035', 'HC-E036', 'HC-E037', 'HC-E038', 'HC-E048'):
            self.assertIn(rule, lint.RULES)
        self.assertEqual(len(set(lint.RULES)), len(lint.RULES))

    def test_config_get_needs_a_guard_or_the_sanctioned_helper(self):
        bare = self.body('float v = GetGame().ConfigGetFloat("CfgAmmo X y");')
        guarded = self.body('if (GetGame().ConfigIsExisting("CfgAmmo X y")) { float v = GetGame().ConfigGetFloat("CfgAmmo X y"); }')
        helper = self.body('float v = HCConfigHelper.HCGetFloat("CfgAmmo X y", 1.0); float w = GetGame().ConfigGetFloat("CfgAmmo X z");')
        self.assertEqual(['HC-E031'], self.rules(bare, lint.rule_config_get))
        self.assertEqual([], self.rules(guarded, lint.rule_config_get))
        self.assertEqual([], self.rules(helper, lint.rule_config_get))

    def test_config_get_helper_class_and_enumerators_are_exempt(self):
        helper = 'class HCConfigHelper { static float Read() { return GetGame().ConfigGetFloat("A b"); } }'
        self.assertEqual([], self.rules(helper, lint.rule_config_get))
        enumerate_children = self.body('int n = GetGame().ConfigGetChildrenCount("CfgWorlds"); string c; GetGame().ConfigGetChildName("CfgWorlds", 0, c);')
        self.assertEqual([], self.rules(enumerate_children, lint.rule_config_get))

    def test_findpath_output_must_be_allocated(self):
        for bad in ('array<vector> out; ai.FindPath(a, b, f, out);', 'array<vector> out = null; ai.FindPath(a, b, f, out);',
                    'ai.FindPath(a, b, f, null);'):
            with self.subTest(bad=bad):
                self.assertEqual(['HC-E032'], self.rules(self.body(bad), lint.rule_findpath_output))
        for good in ('array<vector> out = new array<vector>; ai.FindPath(a, b, f, out);',
                     'array<vector> out; out = new array<vector>; ai.FindPath(a, b, f, out);'):
            with self.subTest(good=good):
                self.assertEqual([], self.rules(self.body(good), lint.rule_findpath_output))

    def test_navmesh_filter_needs_set_flags(self):
        bad = self.body('PGFilter f = new PGFilter; ai.SampleNavmeshPosition(p, 5, f, q);')
        inline = self.body('ai.FindPath(a, b, new PGFilter, out);')
        good = self.body('PGFilter f = new PGFilter; f.SetFlags(PGPolyFlags.WALK, PGPolyFlags.NONE, PGPolyFlags.NONE); ai.SampleNavmeshPosition(p, 5, f, q);')
        self.assertEqual(['HC-E033'], self.rules(bad, lint.rule_navmesh_filter_flags))
        self.assertEqual(['HC-E033'], self.rules(inline, lint.rule_navmesh_filter_flags))
        self.assertEqual([], self.rules(good, lint.rule_navmesh_filter_flags))

    def test_delete_group_needs_a_living_member_check(self):
        bad = self.body('world.DeleteGroup(group);')
        good = self.body('if (group.Count() == 0) { world.DeleteGroup(group); }')
        self.assertEqual(['HC-E034'], self.rules(bad, lint.rule_delete_group))
        self.assertEqual([], self.rules(good, lint.rule_delete_group))

    def test_script_inst_on_an_infected_is_flagged_but_the_command_object_path_is_not(self):
        infected = 'class ZombieBase {}\nclass HCZ : ZombieBase { void Run() { StartCommand_ScriptInst(HCCmd, 1); } }'
        other = 'class HCOther { void Run() { StartCommand_ScriptInst(HCCmd, 1); } }'
        sanctioned = 'class ZombieBase {}\nclass HCZ : ZombieBase { void Run() { StartCommand_Script(new HCPoseCommand(this)); } }'
        self.assertEqual(['HC-E035'], self.rules(infected, lint.rule_infected_script_inst))
        self.assertEqual([], self.rules(other, lint.rule_infected_script_inst))
        self.assertEqual([], self.rules(sanctioned, lint.rule_infected_script_inst))

    def test_new_object_argument_needs_an_owner(self):
        support = ('class HCKeep { ref HCThing m_Kept; void Take(HCThing t) { m_Kept = t; } }\n'
                   'class HCForward { HCThing m_Kept; void Take(HCThing t) { Inner(t); } void Inner(HCThing t) { m_Kept = t; } }\n'
                   'class HCDrop { void Take(HCThing t) { Print(t); } }\n'
                   'class HCThing {}\n')
        use = ('class HCProbe { ref HCKeep m_Keep; ref HCForward m_Forward; ref HCDrop m_Drop; ref array<ref HCThing> m_List;\n'
               'void Run() { %s } }')
        for call, flagged in (('m_Keep.Take(new HCThing);', False), ('m_Forward.Take(new HCThing);', False),
                              ('m_Drop.Take(new HCThing);', True), ('m_List.Insert(new HCThing);', False)):
            with self.subTest(call=call):
                found = self.rules(support + use % call, lint.rule_new_argument)
                self.assertEqual(['HC-E036'] if flagged else [], found)

    def test_flat_pathgraph_refresh_is_flagged(self):
        self.assertEqual(['HC-E037'], self.rules(self.body('g.UpdatePathgraphRegionByObject(obj);'), lint.rule_flat_pathgraph))
        self.assertEqual([], self.rules(self.body('HCPathgraphRefresh.Run(obj);'), lint.rule_flat_pathgraph))

    def test_foreach_over_a_call_result_is_flagged(self):
        rule = lint.rule_foreach_call_iterable
        self.assertEqual(['HC-E048'], self.rules(self.body('foreach (Man m : HCPerfPlayers.HCGet()) { m.Foo(); }'), rule))
        self.assertEqual(['HC-E048'], self.rules(self.body('foreach (H h : m_Store.State().Herds) {}'), rule))
        self.assertEqual(['HC-E048'], self.rules(self.body('foreach (int i, S s : d.States()) {}'), rule))
        self.assertEqual([], self.rules(self.body('array<Man> ps = HCPerfPlayers.HCGet(); foreach (Man m : ps) {}'), rule))
        self.assertEqual([], self.rules(self.body('foreach (H h : m_State.Herds) {}'), rule))
        self.assertEqual([], self.rules(self.body('// foreach (Man m : Get()) {}\nint x;'), rule))

    def test_unordered_head_remove_on_arrays_only(self):
        fields = 'class HCProbe { ref array<string> m_Queue; ref TStringArray m_Names; ref map<int, string> m_Map; void Run() {\n%s\n} }'
        rule = lint.rule_unordered_head_remove
        self.assertEqual(['HC-E038'], self.rules(fields % 'm_Queue.Remove(0);', rule))
        self.assertEqual(['HC-E038'], self.rules(fields % 'm_Names.Remove(0);', rule))
        self.assertEqual([], self.rules(fields % 'm_Queue.RemoveOrdered(0);', rule))
        self.assertEqual([], self.rules(fields % 'm_Queue.Remove(i);', rule))
        self.assertEqual([], self.rules(fields % 'm_Map.Remove(0);', rule))

    def test_unordered_head_remove_waiver_on_same_or_previous_line(self):
        fields = 'class HCProbe { ref array<string> m_Queue; void Run() {\n%s\n} }'
        rule = lint.rule_unordered_head_remove
        marker = '// HC-ORDER: unordered ok'
        self.assertEqual([], self.rules(fields % f'm_Queue.Remove(0); {marker}', rule))
        self.assertEqual([], self.rules(fields % f'{marker}\nm_Queue.Remove(0);', rule))
        self.assertEqual(['HC-E038'], self.rules(fields % f'{marker}\nFoo();\nm_Queue.Remove(0);', rule))
        self.assertEqual(['HC-E038'], self.rules(fields % 'm_Queue.Remove(0); // unordered', rule))
