"""Synthetic dependency-boundary fixtures; no engine behaviour claims."""
import json
import tempfile
import unittest
from unittest import mock

from tools.validate import enforce_lint as lint


W = 'mods/HollowCountryExpansionAI/scripts/4_World/'


class WeakParameterNewRule(unittest.TestCase):
    def findings(self, text):
        return [f for f in lint.lint_texts({W + 'Params.c': text}) if f.rule == 'HC-E060']

    def test_defaulted_weak_parameter(self):
        found = self.findings('class Probe { void Run(array<Man> r = null) { r = new array<Man>; } }')
        self.assertEqual(1, len(found))
        self.assertIn(lint.rule_weak_parameter_new, lint.ALL_RULES)
        self.assertIn('HC-E060', lint.RULES)
        self.assertEqual("native compile: Variable 'r' is not strong ref; own the new object "
                         'in a strong local (HCFuelSiphon.c:106-115 idiom)', found[0].message)

    def test_out_and_inout_parameters(self):
        for modifier in ('out', 'inout'):
            with self.subTest(modifier=modifier):
                self.assertEqual([], self.findings(
                    f'class Probe {{ void Run({modifier} array<Man> r) {{ r = new array<Man>; }} }}'))

    def test_strong_local_idiom_and_member_fields(self):
        self.assertEqual([], self.findings('''
            class Probe {
                ref array<Man> r;
                void Run(array<Man> r = null, Probe other = null) {
                    ref array<Man> strong = new array<Man>;
                    r = strong;
                    this /* member */ . r = new array<Man>;
                    other.
                        r = new array<Man>;
                }
                void LocalOnly() { array<Man> r = new array<Man>; }
            }
        '''))

    def test_multiline_comments_strings_constructor_and_method_scope(self):
        text = '''class Probe {
            void Run(
                map<string, ref array<Man>> r = null,
                out array<Man> permitted = null
            ) {
                // r = new map<string, ref array<Man>>;
                Print("r = new Thing(); { }");
                /* r = new Thing(); */
                if (!r) r /* assignment */ =
                    new map<string, ref array<Man>>();
                permitted = new array<Man>;
            }
            void Other() { ref Thing r = new Thing(); }
        }'''
        found = self.findings(text)
        self.assertEqual(1, len(found))
        self.assertEqual(9, found[0].line)

    def test_file_function_and_multiple_assignments(self):
        found = self.findings('void Run(Thing r) { r = new Thing();\n if (!r) { r = new Thing; } }')
        self.assertEqual(2, len(found))


class MemberAccessRule(unittest.TestCase):
    def findings(self, text, symbols=None, coverage=None):
        source = lint.es.Source(lint.Path(W + 'Access.c'), text)
        return lint.lint([source], rules=(lint.rule_member_access,), symbols=symbols,
                         receiver_coverage=coverage)

    def test_group_hold_shape_reads_writes_and_calls(self):
        findings = self.findings("""
            class HCXAIGroupHold {
                protected ref eAIGroup Group;
                private void Hidden() {}
            }
            class HCXAIGroupHolds {
                void Run(HCXAIGroupHold held) {
                    if (held.Group
                        && held.Group.Count() > 0) {}
                    held.Group = null;
                    held.Hidden();
                }
            }
        """)
        self.assertEqual(['HC-E057'] * 4, [f.rule for f in findings])
        self.assertTrue(all(not f.native for f in findings))
        self.assertIn(lint.rule_member_access, lint.ALL_RULES)

    def test_protected_subclass_and_same_class_access_allowed(self):
        self.assertEqual([], self.findings("""
            class Base {
                protected int Value;
                protected void Hidden() {}
                void Own(Base other) { other.Value = 1; other.Hidden(); }
            }
            class Child : Base {}
            class Grandchild : Child {
                void Run(Base other) { other.Value = 2; other.Hidden(); this.Value = 3; }
            }
        """))

    def test_private_subclass_and_inherited_receiver_flagged(self):
        findings = self.findings("""
            class Base { private int Value; private void Hidden() {} }
            class Child : Base {
                void Run(Child other) { other.Value = 2; other.Hidden(); }
            }
        """)
        self.assertEqual(['HC-E057'] * 2, [f.rule for f in findings])
        self.assertTrue(all('declared in Base' in f.message for f in findings))

    def test_modded_class_is_declaring_class(self):
        self.assertEqual([], self.findings("""
            class Base { private int Value; protected void Hidden() {} }
            modded class Base {
                void Run(Base other) { other.Value = 2; other.Hidden(); }
            }
        """))

    def test_modded_super_targets_previous_body_not_parent(self):
        self.assertEqual([], self.findings("""
            class Ancestor { private void Hidden(int value) {} }
            class Base : Ancestor { protected void Hidden(int value, int extra) {} }
            modded class Base {
                override protected void Hidden(int value, int extra) { super.Hidden(value, extra); }
            }
        """))
        findings = self.findings("""
            class Base { private void Hidden() {} }
            class Child : Base { void Run() { super.Hidden(); } }
        """)
        self.assertEqual(['HC-E057'], [f.rule for f in findings])

    def test_static_class_access_and_public_shadow(self):
        findings = self.findings("""
            class Base { protected static int s_Field; private static void Hidden() {} }
            class Child : Base { static int s_Field; }
            class Caller {
                void Run() { Base.s_Field = 1; Base.Hidden(); Child.s_Field = 2; }
            }
        """)
        self.assertEqual(['HC-E057'] * 2, [f.rule for f in findings])

    def test_static_access_in_field_initializer(self):
        findings = self.findings("""
            class Base { private static int s_Field; }
            class Caller { int Value = Base.s_Field; }
            modded class Base { int OwnValue = Base.s_Field; }
        """)
        self.assertEqual(['HC-E057'], [f.rule for f in findings])
        self.assertEqual('Caller.<initializer>', findings[0].symbol)

    def test_unresolved_receivers_and_coverage(self):
        coverage = {}
        self.assertEqual([], self.findings("""
            class Base { private int Value; }
            class Caller {
                void Run(Unknown unknown, Base known) {
                    unknown.Value = 1;
                    missing.Hidden();
                    Factory().Value = 2;
                    known.ToString();
                }
            }
        """, coverage=coverage))
        self.assertEqual(dict(total=4, resolved=1, unresolved=3), coverage)

    def test_field_chains_typedefs_shadowing_and_unrelated_caller(self):
        findings = self.findings("""
            class Base { protected int Value; }
            typedef Base Alias;
            class Box { ref Alias Item; }
            class Child : Base {}
            class Caller {
                ref Box box;
                void Run() { box.Item.Value = 1; }
                void Shadow(Unknown box) { box.Item.Value = 2; }
                void Derived(Child child) { child.Value = 3; }
            }
        """)
        self.assertEqual(['HC-E057'] * 2, [f.rule for f in findings])

    def test_comments_strings_and_call_result_suffix_are_ignored(self):
        self.assertEqual([], self.findings("""
            class Base { private int Value; }
            class Caller {
                void Run(Base known) {
                    // known.Value = 1;
                    string text = "known.Value";
                    Factory(). known.Value = 2;
                }
            }
        """))

    def test_native_fields_methods_static_and_subclass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = lint.Path(directory)
            path = root / '3_Game' / 'Native.c'
            path.parent.mkdir()
            path.write_text("""
                class EngineBase {
                    protected int Value;
                    private int Secret;
                    protected static int s_Field;
                    protected proto native void Hidden();
                }
            """)
            symbols = {'classes': {'EngineBase': [{
                'layer': 2, 'modded': False, 'parent': '',
                'fields': {'Value': 'int', 'Secret': 'int', 's_Field': 'int'},
                'methods': ['Hidden']} ]},
                'access_classes': lint.native_member_access(root)}
            findings = self.findings("""
                class Child : EngineBase {
                    void Run(EngineBase other) { other.Value = 1; other.Secret = 2; other.Hidden(); }
                }
                class Caller {
                    void Run(EngineBase other) {
                        other.Value = 1; other.Hidden(); EngineBase.s_Field = 2;
                    }
                }
                modded class EngineBase {
                    void Own(EngineBase other) { other.Secret = 1; }
                }
            """, symbols=symbols)
            self.assertEqual(['HC-E057'] * 4, [f.rule for f in findings])
            self.assertTrue(all(f.native for f in findings))


class DuplicateRPCIdRule(unittest.TestCase):
    def findings(self, files):
        return lint.lint_texts({W + name: text for name, text in files.items()},
                               rules=(lint.rule_duplicate_rpc_ids,))

    def test_duplicate_pair_reports_both_locations(self):
        files = {'First.c': 'class First { static const int RPC_REQUEST = 4854011; }',
                 'Second.c': 'class Second {\nconst int RPC_TUNING = 4854011; }'}
        findings = self.findings(files)
        self.assertEqual(['HC-E054', 'HC-E054'], [f.rule for f in findings])
        for finding in findings:
            self.assertIn(W + 'First.c:1', finding.message)
            self.assertIn(W + 'Second.c:2', finding.message)
        self.assertEqual([1, 2], [f.line for f in findings])
        self.assertIn(lint.rule_duplicate_rpc_ids, lint.ALL_RULES)
        self.assertIn('HC-E054', lint.RULES)

    def test_named_references_do_not_allocate_ids(self):
        self.assertEqual([], self.findings({'Use.c': '''
            class Wire {
                static const int RPC_REQUEST = 4854012;
                void Run() {
                    ScriptRPC rpc = new ScriptRPC;
                    rpc.Send(null, RPC_REQUEST, true);
                    rpc.Send(null, RPC_REQUEST, true);
                    GetGame().RPCSingleParam(null, RPC_REQUEST, payload, true);
                }
            }
        '''}))

    def test_distinct_ids_pass(self):
        self.assertEqual([], self.findings({
            'First.c': 'static const int RPC_REQUEST = 4854012;',
            'Second.c': 'const int rpc_tuning = 4854011;'}))

    def test_direct_send_literal_collides_with_constant(self):
        findings = self.findings({'Send.c': '''
            class Wire {
                static const int RPC_REQUEST = 4854012;
                void Run() {
                    ScriptRPC rpc = new ScriptRPC;
                    rpc.Send(FindTarget(a, b),
                             4854012, true, identity);
                }
            }
        '''})
        self.assertEqual(['RPC_REQUEST', 'Send'], [f.symbol for f in findings])
        self.assertEqual([3, 7], [f.line for f in findings])

    def test_explicit_enum_members_and_integer_literal_forms(self):
        findings = self.findings({'Enum.c': '''
            enum Wire { OTHER = 7, rpc_first = 0x4A106B, RPC_IMPLICIT,
                        RPC_SECOND = +4853867, RPC_EXPRESSION = 4853867 + 1 }
        '''})
        self.assertEqual(['Wire.rpc_first', 'Wire.RPC_SECOND'], [f.symbol for f in findings])

    def test_game_single_param_literal_collides(self):
        findings = self.findings({'Game.c': '''
            const int RPC_REQUEST = -17;
            void Run() { GetGame().RPCSingleParam(Target(a, b), -17, payload, true); }
        '''})
        self.assertEqual(['RPC_REQUEST', 'RPCSingleParam'], [f.symbol for f in findings])

    def test_comments_strings_and_unrelated_send_are_ignored(self):
        self.assertEqual([], self.findings({'Ignored.c': '''
            const int RPC_REQUEST = 17;
            const int OTHER = 17;
            // const int RPC_COMMENT = 17;
            /* enum Wire { RPC_COMMENT = 17 } */
            class Example {
                void First() { ScriptRPC client; client.Send(null, RPC_REQUEST, true); }
                void Second() {
                    HCClient client;
                    client.Send(null, 17, true);
                    string example = "const int RPC_STRING = 17;";
                    // GetGame().RPCSingleParam(null, 17, payload, true);
                }
            }
        '''}))


class IdentityComparisonRule(unittest.TestCase):
    def test_typed_comparisons_and_allowed_checks(self):
        source = """
class Man {}
class PlayerBase : Man {}
class HCPartyIdentity {}
class HCPeer { PlayerIdentity Identity; }
class HCProbe
{
    ref array<PlayerIdentity> Identities;
    ref map<string, PlayerIdentity> ById;
    PlayerIdentity Current() {}
    void Run(PlayerIdentity sender, PlayerBase player, HCPeer peer)
    {
        PlayerIdentity local = sender;
        if (local == sender) {}
        if (peer.Identity != sender) {}
        if (player.GetIdentity() != sender) {}
        if (Identities[0] == sender) {}
        if ((sender) == (local)) {}
        if (Current() == player.GetIdentity()) {}
        if (ById.Get("key") != sender) {}
        if (!sender || sender == null || null != local) {}
        if (sender.GetId() == local.GetId()) {}
        if (player == player || peer == peer) {}
        HCPartyIdentity party;
        if (party == party) {}
        string text = "sender == local";
        // if (local == sender) {}
    }
}
"""
        findings = lint.lint_texts({W + 'Identity.c': source},
                                   rules=(lint.rule_identity_comparisons,))
        self.assertEqual(['HC-E056'] * 7, [f.rule for f in findings])
        self.assertIn(lint.rule_identity_comparisons, lint.ALL_RULES)


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
            # Expansion core adds Expansion_* reads to the player classes; they go through the bridge too.
            ('class HCProbe { void Run(PlayerBase player) { player.Expansion_GetAimDirection(); } }',
             ['player.Expansion_GetAimDirection']),
            ('class HCProbe { void Run(DayZPlayerImplement leader) { leader.Expansion_GetMovementSpeed(); } }',
             ['leader.Expansion_GetMovementSpeed']),
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


def _engine(parent, methods=(), fields=None):
    return [dict(layer=3, modded=False, parent=parent, methods=set(methods), fields=fields or {})]


ENGINE_SYMBOLS = {'classes': {
    'Class': _engine(''),
    'EntityAI': _engine('Class', {'GetInventory'}),
    'ItemBase': _engine('EntityAI', {'SetQuantity'}),
    'ItemTransmitter': _engine('ItemBase', {'GetTunedFrequency'}),
    'TransmitterBase': _engine('ItemTransmitter'),
    'DayZPlayerImplement': _engine('Class', {'GetIdentity'}),
    'PlayerBase': _engine('DayZPlayerImplement', {'GetInventory'}),
    'string': _engine('', {'Length'}),
    'Orphan': _engine('UnknownEngineParent', {'Known'}),
}}


class EngineReceiverMethodRule(unittest.TestCase):
    """HC-E012 on engine-declared receivers (synthetic symbol table, no engine claims)."""

    def findings(self, text, path=W + 'Caller.c', symbols=ENGINE_SYMBOLS, support=''):
        sources = [lint.es.Source(path, text)]
        if support:
            sources.append(lint.es.Source(W + 'Types.c', support))
        return lint.lint(sources, rules=(lint.rule_receiver_methods,), symbols=symbols)

    def test_engine_method_declared_on_a_subclass_is_flagged_on_every_declaration_form(self):
        for name, text in (
            ('member (the soak compile error)',
             'class HCProbe { protected ItemBase m_Main; float Run() { return m_Main.GetTunedFrequency(); } }'),
            ('parameter', 'class HCProbe { void Run(ItemBase item) { item.GetTunedFrequency(); } }'),
            ('local', 'class HCProbe { void Run() { ItemBase item; item.GetTunedFrequency(); } }'),
            ('after a template parameter',
             'class HCProbe { void Run(map<string, string> a, ItemBase item) { item.GetTunedFrequency(); } }'),
        ):
            with self.subTest(name):
                result = self.findings(text)
                self.assertEqual(['HC-E012'], [f.rule for f in result])
                self.assertIn('ItemBase has no visible method GetTunedFrequency', result[0].message)

    def test_cast_inherited_and_authored_modded_methods_are_not_flagged(self):
        for name, text, support in (
            ('cast to the declaring subclass',
             'class HCProbe { void Run(ItemBase item) { TransmitterBase t = TransmitterBase.Cast(item); '
             't.GetTunedFrequency(); } }', ''),
            ('method inherited from an engine parent',
             'class HCProbe { void Run(ItemBase item) { item.GetInventory(); item.SetQuantity(1); } }', ''),
            ('method added by our own modded class',
             'class HCProbe { void Run(ItemBase item) { item.HCMark(); } }',
             'modded class ItemBase { void HCMark() {} }'),
            ('template parameter does not split a parameter list',
             'class HCProbe { void Run(map<string, string> left, string name) { left.Count(); name.Length(); } }', ''),
        ):
            with self.subTest(name):
                self.assertEqual([], self.findings(text, support=support))

    def test_template_parameters_keep_their_own_type(self):
        source = lint.es.Source(W + 'Caller.c', 'class HCProbe { void Run(map<string, bool> a, int b, '
                                                'array<ref map<string, string>> c = null) {} }')
        parameters = source.classes[0].methods[0].parameters()
        self.assertEqual(['a', 'b', 'c'], [name for _, name, _ in parameters])
        self.assertEqual(['map<string, bool>', 'int'], [kind for kind, _, _ in parameters[:2]])

    def test_parameter_split_ignores_quoted_commas_and_brackets(self):
        for literal in ('","', '"<"', '">"', '"([<,>])"',
                        r'"escaped \",<"', r'"backslash \\"'):
            with self.subTest(literal=literal):
                parts = ['string text = ' + literal, ' map<string, array<int>> values', ' int count = 1']
                self.assertEqual(parts, lint.es.split_parameters(','.join(parts)))

    def test_expression_split_keeps_less_than_comparisons(self):
        self.assertEqual(['left < right', ' next'], lint.es.split_top('left < right, next', ','))

    def test_provider_bridge_files_do_not_judge_engine_receivers(self):
        text = 'class HCProbe { void Run(DayZPlayerImplement value) { value.GetGroup(); } }'
        for bridge in lint._PROVIDER_BRIDGES:
            with self.subTest(bridge=bridge):
                self.assertEqual([], self.findings(text, path=bridge))
        self.assertEqual(['HC-E012'], [f.rule for f in self.findings(text)])

    def test_provider_method_outside_a_bridge_needs_an_exact_allowlist_entry(self):
        path = W + 'HCXDefence.c'
        text = ('class HCXDefence { void OnShot(PlayerBase shooter) { shooter.%s(); } }')
        entry = {(path, 'HCXDefence.OnShot', 'PlayerBase', 'ProviderAim')}
        with mock.patch.object(lint, 'load_provider_methods', return_value=entry):
            self.assertEqual([], self.findings(text % 'ProviderAim', path=path))
            # Same method elsewhere, another method in the same file, and another receiver type all fail.
            self.assertEqual(['HC-E012'], [f.rule for f in self.findings(text % 'ProviderAim')])
            self.assertEqual(['HC-E012'], [f.rule for f in self.findings(text % 'ProviderOther', path=path)])
            self.assertEqual(['HC-E012'], [f.rule for f in self.findings(
                text.replace('PlayerBase', 'DayZPlayerImplement') % 'ProviderAim', path=path)])

    def test_allowlist_entries_need_a_reason_and_exact_fields(self):
        entries = lint.load_provider_methods()
        self.assertTrue(all(len(entry) == 4 for entry in entries))
        # Both parked Expansion reads moved behind HCXExpansionBridge; their entries are gone.
        self.assertFalse({entry[3] for entry in entries} & {'Expansion_GetAimDirection', 'Expansion_GetMovementSpeed'})
        with tempfile.TemporaryDirectory() as folder:
            path = lint.Path(folder) / 'allow.json'
            for entry in ({'path': 'a.c', 'symbol': 'A.B', 'receiver_type': 'PlayerBase', 'method': 'M'},
                          {'path': 'a.c', 'symbol': 'A.B', 'receiver_type': 'PlayerBase', 'method': 'M',
                           'reason': ' '}):
                path.write_text(json.dumps({'schema': 1, 'entries': [entry]}), encoding='utf-8')
                with self.assertRaises(ValueError):
                    lint.load_provider_methods(path)

    def test_unresolvable_receivers_are_skipped_not_guessed(self):
        text = 'class HCProbe { void Run(Orphan a, UnknownType b) { a.Other(); b.Other(); } }'
        self.assertEqual([], self.findings(text))
        known = 'class HCProbe { void Run(Orphan a) { a.Known(); } }'
        self.assertEqual([], self.findings(known))
        # No symbol table, or only the committed names index: engine receivers are not judged.
        bad = 'class HCProbe { void Run(ItemBase item) { item.GetTunedFrequency(); } }'
        self.assertEqual([], self.findings(bad, symbols=None))
        self.assertEqual([], self.findings(bad, symbols=dict(ENGINE_SYMBOLS, origin='names-index')))

    def test_authored_receivers_are_still_checked(self):
        text = 'class HCOwn { void A() {} } class HCProbe { void Run(HCOwn own) { own.B(); } }'
        self.assertEqual(['HC-E012'], [f.rule for f in self.findings(text, symbols=None)])


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


class ProtoNativeMethodRule(unittest.TestCase):
    def setUp(self):
        from pathlib import Path
        self.cache = tempfile.TemporaryDirectory()
        self.addCleanup(self.cache.cleanup)
        self.root = Path(self.cache.name)
        folder = self.root / '3_Game'
        folder.mkdir()
        (folder / 'Native.c').write_text("""
class CGame {
    proto native int Connect(int a, int b, int c, int d);
    proto external void External(int value);
    static proto void StaticCall(map<string, int> values, int value = 0);
    proto void Plain();
};
class DayZGame : CGame { void Connect() {} };
""")
        self.patch = mock.patch.object(lint._syntax, 'NATIVE_ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def sources(self, text):
        return [lint.es.Source('mods/HollowCountryTest/scripts/3_Game/Probe.c', text)]

    def findings(self, text):
        return lint.lint(self.sources(text), rules=(lint.rule_proto_native_methods,))

    def test_native_match_with_and_without_override_and_changed_types(self):
        for prefix in ('override ', '', 'static ', 'proto '):
            for owner in ('modded class DayZGame', 'class HCGame : DayZGame'):
                with self.subTest(prefix=prefix, owner=owner):
                    result = self.findings(owner + ' { ' + prefix
                        + 'int Connect(string a, int b, int c, int d) {} }')
                    self.assertEqual(['HC-E053'], [f.rule for f in result])
                    self.assertIn('proto CGame.Connect', result[0].message)

    def test_new_native_name_overload_is_rejected_but_script_hook_is_allowed(self):
        self.assertEqual(['HC-E053'], [f.rule for f in self.findings(
            'modded class DayZGame { int Connect(int value) {} }')])
        self.assertEqual([], self.findings(
            'modded class DayZGame { override void Connect() {} void HCConnect() {} }'))
        self.assertEqual([], self.findings('class Unrelated { void Connect(int a) {} }'))

    def test_external_static_plain_proto_and_template_arity(self):
        for declaration in ('override void External(int value)',
                            'override static void StaticCall(map<string, int> values, int value)',
                            'void Plain()'):
            with self.subTest(declaration=declaration):
                self.assertEqual(['HC-E053'], [f.rule for f in self.findings(
                    'modded class CGame { ' + declaration + ' {} }')])

    def test_authored_chain_cycle_unknown_parent_and_layer_visibility(self):
        self.assertEqual(['HC-E053'], [f.rule for f in self.findings(
            'class HCBase : DayZGame {} class HCLeaf : HCBase { void Plain() {} }')])
        self.assertEqual([], self.findings('class HCBase : Missing { void Plain() {} }'))
        self.assertEqual([], self.findings('class A : B {} class B : A { void Plain() {} }'))
        folder = self.root / '4_World'
        folder.mkdir()
        (folder / 'Later.c').write_text('modded class CGame { proto void Later(); }')
        lint._syntax._NATIVE.pop(str(self.root), None)
        self.assertEqual([], self.findings('modded class CGame { void Later() {} }'))

    def test_rule_registered_and_comments_do_not_declare_methods(self):
        self.assertIn(lint.rule_proto_native_methods, lint.ALL_RULES)
        self.assertEqual([], self.findings('modded class CGame { // void Plain() {}\n'
                                          'void Run() { string s = "void Plain()"; } }'))

    def test_branch_inventory_handles_nested_elif_else_and_ignores_examples(self):
        source = self.sources("""// #ifndef SERVER
/* #ifdef CLIENT */
#ifndef SERVER
#ifdef OTHER
class A {}
#endif
#elif defined(CLIENT)
class B {}
#else
class C {}
#endif
#if !defined(SERVER) && defined(CLIENT)
class D {}
#endif
""")[0]
        self.assertEqual([], lint.client_only_blocks(self.sources(
            '#ifdef OTHER // CLIENT\nclass E {}\n#endif\n')[0]))
        blocks = lint.client_only_blocks(source)
        self.assertEqual(['#ifndef SERVER', '#elif defined(CLIENT)', '#else',
                          '#if !defined(SERVER) && defined(CLIENT)'], [b[2] for b in blocks])
        self.assertEqual([3, 7, 9, 12], [source.line_of(b[0]) for b in blocks])

    def test_client_branch_rules_keep_class_context_and_run_both_rules(self):
        sources = self.sources("""class HCTarget { void Known() {} }
#ifndef SERVER
modded class DayZGame { override void Plain() {} }
class HCClient { void Run(HCTarget target) { target.Missing(); } }
#else
class HCServer {}
#endif
""")
        inventory, findings = lint.client_branch_coverage(sources)
        self.assertEqual(2, len(inventory))
        self.assertEqual(['HC-E012', 'HC-E053'], sorted(f.rule for f in findings))
        self.assertTrue(all(f.path.endswith('Probe.c') for f in findings))

    def test_no_role_blocks_means_no_explicit_client_findings(self):
        inventory, findings = lint.client_branch_coverage(self.sources(
            'modded class CGame { void Plain() {} }'))
        self.assertEqual(([], []), (inventory, findings))


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
        for rule in ('HC-E031', 'HC-E032', 'HC-E033', 'HC-E034', 'HC-E035', 'HC-E036', 'HC-E037', 'HC-E038', 'HC-E048', 'HC-E051'):
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

    def test_call_in_an_assigned_index_is_flagged(self):
        rule = lint.rule_call_in_assigned_index
        self.assertEqual(['HC-E051'], self.rules(self.body('s_Stamp[HCBucket(x, z)] = s_Counter;'), rule))
        self.assertEqual(['HC-E051'], self.rules(self.body('if (ok) m.Counts[Key(a)] += 1;'), rule))
        self.assertEqual([], self.rules(self.body('int b = HCBucket(x, z); s_Stamp[b] = s_Counter;'), rule))
        self.assertEqual([], self.rules(self.body('int v = s_Stamp[HCBucket(x, z)];'), rule))
        self.assertEqual([], self.rules(self.body('if (s_Stamp[HCBucket(x, z)] == s_Counter) { return; }'), rule))

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


class ConfigOnlyWeaponCompatRule(unittest.TestCase):
    def test_scopes_queries_aliases_and_allowed_fixture_calls(self):
        scopes = ('mods/HollowCountry/scripts/4_World/Loot/HCGunPile.c',
                  'mods/Other/scripts/4_World/Loot/HCGunPileExtra.c',
                  'mods/HollowCountryTest/scripts/4_World/HCTestReachFixtures.c')
        calls = ('GetMagazineTypeCount', 'GetRandomMagazineTypeName', 'GetMaxMagazineTypeName',
                 'GetRandomChamberableAmmoTypeName', 'HasInternalMagazine', 'SpawnAmmo',
                 'SpawnAttachedMagazine', 'FillChamber', 'GetMuzzleCount', 'GetMagazineTypeName',
                 'GetChamberableAmmoTypeName', 'GetChamberAmmoTypeName', 'GetAmmoMax')
        for path in scopes:
            for call in calls:
                with self.subTest(path=path, call=call):
                    body = f'class HCProbe {{ void Run() {{ alias.{call}(0); }} }}'
                    findings = lint.lint_texts({path: body}, rules=(lint.rule_config_only_weapon_compat,))
                    self.assertEqual(['HC-E052'], [f.rule for f in findings])
        safe = '''class HCProbe { void Run() {
            // gun.GetMuzzleCount();
            string text = "gun.GetMagazineTypeCount()";
            gun.PushCartridgeToChamber(0, 0, ammo); gun.CanFire();
            gun.IsChamberEmpty(0); gun.Fire(0, pos, dir, vel);
        } }'''
        self.assertEqual([], lint.lint_texts({scopes[2]: safe}, rules=(lint.rule_config_only_weapon_compat,)))
        self.assertEqual([], lint.lint_texts({'mods/Other/scripts/4_World/Weapon.c':
            'class HCProbe { void Run() { gun.GetMuzzleCount(); } }'},
            rules=(lint.rule_config_only_weapon_compat,)))
        self.assertIn(lint.rule_config_only_weapon_compat, lint.ALL_RULES)
        self.assertIn('HC-E052', lint.RULES)
