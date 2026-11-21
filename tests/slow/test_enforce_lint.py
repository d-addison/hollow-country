"""Behaviour of tools/validate/enforce_lint: Enforce compile traps and silent server refusals.

Every fixture below is synthetic and explicit, shaped after a failure that a
native DayZ 1.30.164289 compile/boot or a real client actually showed (commit
ids in the comments). The tree test runs pinned-only (no engine cache), so its
result does not depend on local files. A clean lint is not DayZ evidence.
"""
import json
from pathlib import Path
import tempfile
import unittest

from tools.validate import enforce_lint as lint
from tools.validate import enforce_source as es

ROOT = Path(__file__).resolve().parents[2]
W = 'mods/HollowCountry/scripts/4_World/'
G = 'mods/HollowCountry/scripts/3_Game/'


def run(files, rule=None):
    findings = lint.lint_texts(files)
    return [f for f in findings if rule is None or f.rule == rule]


def where(findings):
    return [(f.path.rsplit('/', 1)[-1], f.line, f.symbol) for f in findings]


class SourceModel(unittest.TestCase):
    def test_unbalanced_prototype_attribute_is_reported_without_prior_model_reads(self):
        text = '[Broken(1)\nproto native void Lost();\nproto native void Following();'
        findings = run({W + 'A.c': text})
        self.assertEqual([('HC-E008', 1)], [(f.rule, f.line) for f in findings])

    def test_unbalanced_attribute_reports_lint_instead_of_silently_dropping_method(self):
        # Invalid synthetic source: the next balanced method must still be read.
        for wrapper in ('{}', 'class A {{\n{}\n}}'):
            with self.subTest(wrapper=wrapper):
                text = wrapper.format('[Broken("bracket ] in string")\n'
                                      'void Lost() {}\nvoid Following() {}')
                source = es.Source(Path(W + 'A.c'), text)
                # Repeated signature reads must not duplicate parse diagnostics.
                self.assertEqual(['Following'], [s.name for s in source.signatures])
                self.assertEqual(['Following'], [s.name for s in source.signatures])
                findings = lint.lint([source])
                self.assertEqual(1, len(findings))
                self.assertEqual('HC-E008', findings[0].rule)
                self.assertEqual(source.line_of(text.index('[Broken')), findings[0].line)
                self.assertIn('unbalanced', findings[0].message.lower())
                self.assertIn('attribute', findings[0].message.lower())

    def test_brace_array_attribute_argument_is_not_an_unbalanced_attribute(self):
        # Review P2: a { } array inside an attribute call is an argument, not a body.
        for wrapper in ('{}', 'class A {{\n{}\n}}'):
            with self.subTest(wrapper=wrapper):
                text = wrapper.format('[Attr({"a", "b"})]\nvoid Tagged() {}\nvoid Following() {}')
                self.assertEqual([], run({W + 'A.c': text}, 'HC-E008'))

    def test_comments_strings_and_preprocessor_lines_are_blanked_but_offsets_kept(self):
        text = 'int a; // x ? y\n/* { */ string s = "a ? { b";\n#ifdef DIAG\nint c;\n#endif\n'
        code = es.clean(text)
        self.assertEqual(len(text), len(code))
        self.assertEqual(text.count('\n'), code.count('\n'))
        self.assertNotIn('?', code)
        self.assertNotIn('{', code)
        self.assertNotIn('#', code)

    def test_classes_fields_and_methods_are_found_with_lines(self):
        source = es.Source(Path(W + 'A.c'), 'class HCA : Managed\n{\n    ref HCB m_B;\n    int m_N = 3;\n'
                                             '    void Go(int x)\n    {\n        if (x) { m_N = 1; }\n    }\n}\n')
        (definition,) = source.classes
        self.assertEqual(('HCA', 'Managed', False), (definition.name, definition.base, definition.modded))
        self.assertEqual([('m_B', 'HCB', True), ('m_N', 'int', False)],
                         [(f.name, f.type, f.strong) for f in definition.fields])
        (method,) = definition.methods
        self.assertEqual(('Go', 'void', 5), (method.name, method.return_type, source.line_of(method.offset)))


class CompileTraps(unittest.TestCase):
    def test_handle_null_checks_find_initialized_grouped_declarators(self):
        for kind in ('FileHandle', 'FindFileHandle', 'HCHandle'):
            with self.subTest(kind=kind):
                text = f'''typedef FileHandle HCHandle;
{kind} globalFirst = OpenFile("a,b", FileMode.READ), globalLater;
class HCGrouped {{
    {kind} fieldFirst = OpenFile("a,b", FileMode.READ), fieldLater;
    void Check() {{
        {kind} first = OpenFile(PathFor(1, 2), FileMode.READ),
            second = OpenFile("c,d", FileMode.READ), third;
        if (globalLater != null) {{}}
        if (null == this.fieldLater) {{}}
        if ((second) != (null)) {{}}
        if (third == null) {{}}
    }}
}}
'''
                found = run({W + 'Grouped.c': text}, 'HC-E016')
                self.assertEqual([('Grouped.c', line, 'HCGrouped.Check')
                                  for line in (8, 9, 10, 11)], where(found))

    def test_initialized_grouped_locals_preserve_shadowing_and_block_scope(self):
        text = '''class HCGrouped {
    FileHandle later;
    void Check() {
        if (later != null) {}
        {
            int first = Pick(1, 2), later;
            if (later != null) {}
        }
        if (later != null) {}
        Object firstObject = Pick(1, 2), later = null;
        if (later != null) {}
    }
}
'''
        found = run({W + 'Grouped.c': text}, 'HC-E016')
        self.assertEqual([('Grouped.c', line, 'HCGrouped.Check') for line in (4, 9)], where(found))

    def test_grouped_handle_initializers_keep_nested_commas_inside_expressions(self):
        # Exercise all delimiter pairs without requiring expression type inference.
        text = '''void Check() {
    FileHandle first = handles[Pick(1, 2)], second = Select({1, 2}), third;
    if (second != null) {}
    if (third != null) {}
}
'''
        found = run({W + 'Grouped.c': text}, 'HC-E016')
        self.assertEqual([('Grouped.c', line, '<file>.Check') for line in (3, 4)], where(found))

    def test_ternary_is_flagged_outside_strings_and_comments(self):
        found = run({W + 'T.c': 'class HCT\n{\n    int A(bool b)\n    {\n        return b ? 1 : 0;\n    }\n'
                                '    string B() { return "?"; } // ?\n}\n'}, 'HC-E001')
        self.assertEqual([('T.c', 5, '<file>')], where(found))

    def test_integer_assigned_to_a_file_handle_is_flagged(self):
        # Native boot 074 (38133ab): hcxaicaravanadapter.c,70 "Incompatible parameter 'm_File'".
        files = {W + 'HCRoads.c': 'class HCRoads\n{\n    FileHandle m_File;\n    void A()\n    {\n'
                                  '        m_File = OpenFile("$profile:x", FileMode.READ);\n'
                                  '        if (m_File != 0) { CloseFile(m_File); m_File = 0; }\n'
                                  '        FileHandle handle = OpenFile("$profile:y", FileMode.READ);\n'
                                  '        handle = 0;\n    }\n}\n'}
        found = run(files, 'HC-E010')
        self.assertEqual([('HCRoads.c', 7, 'm_File'), ('HCRoads.c', 9, 'handle')], where(found))

    def test_keyword_used_as_a_variable_name_is_flagged(self):
        # Native boot 075 (96d8dd3 parent): hcxaibaseraid.c,270 "Expected name, not a keyword 'local'".
        files = {W + 'HCRaid.c': 'class HCRaid\n{\n    int owned;\n    void A(out int count, notnull Object target)\n    {\n'
                                 '        array<Object> local = new array<Object>;\n'
                                 '        ref array<Object> kept = new array<Object>;\n'
                                 '        string text = "array<Object> local = x";\n    }\n'
                                 '    void B(int event) {}\n}\n'}
        found = run(files, 'HC-E011')
        self.assertEqual([('HCRaid.c', 3, 'owned'), ('HCRaid.c', 6, 'local'), ('HCRaid.c', 10, 'event')], where(found))

    def test_3_game_cannot_see_a_4_world_class(self):
        files = {W + 'HCWorldThing.c': 'class HCWorldThing\n{\n}\n',
                 G + 'HCGameThing.c': 'class HCGameThing\n{\n    ref HCWorldThing m_T;\n    PlayerBase m_P;\n}\n',
                 W + 'HCUser.c': 'class HCUser\n{\n    ref HCGameThing m_G;\n}\n'}
        found = run(files, 'HC-E002')
        self.assertEqual([('HCGameThing.c', 3, 'HCWorldThing'), ('HCGameThing.c', 4, 'PlayerBase')], where(found))

    def test_new_on_a_weak_member_is_flagged(self):
        # Native boot 022 (6daeb18): hccellarsampler.c:312 'Variable m_Instance is not strong ref'.
        files = {W + 'Interiors/HCCellarSampler.c':
                 'class HCCellarSampler\n{\n    protected HCCellarSamplerInstance m_Instance;\n'
                 '    protected ref HCCellarSamplerInstance m_Kept;\n    protected HCBudget m_Init = new HCBudget;\n'
                 '    int m_Count;\n    void HCBeginHouse()\n    {\n        m_Instance = new HCCellarSamplerInstance();\n'
                 '        m_Kept = new HCCellarSamplerInstance();\n        m_Count = 1;\n    }\n'
                 '    void Local()\n    {\n        HCCellarSamplerInstance m_Instance = new HCCellarSamplerInstance();\n    }\n}\n'}
        found = run(files, 'HC-E003')
        self.assertEqual([('HCCellarSampler.c', 5, 'HCCellarSampler.m_Init'),
                          ('HCCellarSampler.c', 9, 'HCCellarSampler.HCBeginHouse')], where(found))

    def test_new_into_a_collection_of_weak_elements_is_flagged(self):
        files = {W + 'C.c': 'typedef array<ref HCRow> HCRows;\nclass HCC\n{\n    ref array<HCRow> m_Weak;\n'
                            '    ref array<ref HCRow> m_Strong;\n    ref HCRows m_Typed;\n    ref map<string, HCRow> m_Map;\n'
                            '    void Fill()\n    {\n        m_Weak.Insert(new HCRow());\n        m_Strong.Insert(new HCRow());\n'
                            '        m_Typed.Insert(new HCRow());\n        m_Map.Set("a", new HCRow());\n    }\n}\n'}
        found = run(files, 'HC-E004')
        self.assertEqual([('C.c', 10, 'HCC.Fill'), ('C.c', 13, 'HCC.Fill')], where(found))

    def test_a_modded_link_calling_a_method_only_a_later_link_adds_is_flagged(self):
        # Native boot 021 (6daeb18): Undefined function HCNativeInfectedPack.HCVarietyWalkerHerd at
        # hchordemigration.c:156; Infected/Variety compiles after Infected/HCHordeMigration.c.
        base = 'class HCNativeInfectedPack\n{\n    void Tick() {}\n}\n'
        earlier = 'modded class HCNativeInfectedPack\n{\n    void V2Remember()\n    {\n        HCVarietyWalkerHerd();\n        Tick();\n    }\n}\n'
        later = 'modded class HCNativeInfectedPack\n{\n    void HCVarietyWalkerHerd() {}\n    void Late() { V2Remember(); }\n}\n'
        files = {W + 'Infected/HCInfectedNavigation.c': base, W + 'Infected/HCHordeMigration.c': earlier,
                 W + 'Infected/Variety/HCInfectedVarietyNative.c': later}
        found = run(files, 'HC-E005')
        self.assertEqual([('HCHordeMigration.c', 5, 'HCNativeInfectedPack.V2Remember')], where(found))
        # The fix that landed: an empty hook on the base class, overridden by the later link.
        files[W + 'Infected/HCInfectedNavigation.c'] = base.replace('void Tick() {}', 'void Tick() {}\n    void HCVarietyWalkerHerd() {}')
        files[W + 'Infected/Variety/HCInfectedVarietyNative.c'] = later.replace('void HCVarietyWalkerHerd', 'override void HCVarietyWalkerHerd')
        self.assertEqual([], run(files, 'HC-E005'))

    def test_substring_without_a_length_bound_is_flagged(self):
        # Native boot 023 (6daeb18): HCAtmosphereQualification.DisabledXmlRoot raised 'Wrong parameter value'.
        files = {W + 'S.c': 'class HCS\n{\n    string Head(string text)\n    {\n        return text.Substring(0, 5);\n    }\n'
                            '    string Safe(string text)\n    {\n        if (text.Length() < 5) return "";\n        return text.Substring(0, 5);\n    }\n'
                            '    string Cut(string tail)\n    {\n        int close = tail.IndexOf("x");\n        if (close < 0) return "";\n'
                            '        return tail.Substring(0, close);\n    }\n'
                            '    string Lease(HCRun run)\n    {\n        return run.Lease.Substring(0, run.Lease.LastIndexOf(":"));\n    }\n}\n'}
        found = run(files, 'HC-E006')
        self.assertEqual([('S.c', 5, 'HCS.Head'), ('S.c', 20, 'HCS.Lease')], where(found))

    def test_a_method_named_like_a_visible_type_and_called_unqualified_is_flagged(self):
        # Native boot 026 (acab865): HCXGrudge.Slot; the unqualified call bound to vanilla class Slot(float).
        files = {W + 'HCXDefence.c': 'class HCXGrudge\n{\n    int Slot(eAIBase ai) { return 0; }\n'
                                     '    int Use(eAIBase ai) { return Slot(ai); }\n}\n'
                                     'class HCXOther\n{\n    static void Step() {}\n}\n'
                                     'class HCXQualified\n{\n    int Slot(int i) { return i; }\n}\n'}
        found = run(files, 'HC-E007')
        self.assertEqual([('HCXDefence.c', 3, 'HCXGrudge.Slot')], where(found))


class LogLines(unittest.TestCase):
    def test_print_of_a_bare_variable_is_flagged(self):
        # Boot 032 RPT: Print(line) logged "string line = '[HC XAI] live ...'", so the RPT line no longer
        # starts with its tag; Print("" + line) prints the text itself (see HCPerfSampler).
        files = {W + 'L.c': 'class HCL\n{\n    string m_Last;\n    void Log(string line)\n    {\n'
                            '        Print(line);\n        Print("" + line);\n        Print("[HC] plain");\n'
                            '        Print( m_Last );\n        Print(Describe());\n        // Print(line);\n'
                            '        PrintFormat("%1", line);\n        GetGame().Print(line);\n        Print(true);\n    }\n'
                            '    string Describe() { return "x"; }\n}\n'}
        found = run(files, 'HC-L001')
        self.assertEqual([('L.c', 6, 'HCL.Log'), ('L.c', 9, 'HCL.Log')], where(found))

class IdentityGates(unittest.TestCase):
    """Synthetic engine/build comparisons; no fixture is native runtime evidence."""

    def test_wave8_raw_build_values_and_getter_forms_require_shared_identity(self):
        text = '''class HCI {
    bool Profile(HCProfile p) { return p.BuildVersion != m_Build; }
    bool Receipt(HCProfile p, HCReceipt r) { return r.BuildVersion == p.BuildVersion; }
    bool Getter() { return NativeBuild() == profile.BuildVersion; }
    bool Reversed(HCProfile p) { return observed == p.BuildVersion; }
    bool Wrapped(string build) { return (build) == ("1.30.164289"); }
    bool Shared(HCProfile p) { return HCBuildIdentity.SameBuild(p.BuildVersion, m_Build); }
    bool Dependency(HCProfile p) { return p.ProviderVersion == provider.Version; }
    bool Empty(string build) { return build == ""; }
    bool Normalized(HCProfile p) { return HCBuildIdentity.Normalize(p.GameBuild) == HCBuildIdentity.Normalize(m_Build); }
}'''
        self.assertEqual([('I.c', n, 'HCI.' + name) for n, name in
                          ((2, 'Profile'), (3, 'Receipt'), (4, 'Getter'), (5, 'Reversed'), (6, 'Wrapped'))],
                         where(run({W + 'I.c': text}, 'HC-S004')))

    def test_silent_literal_build_comparisons_are_flagged_in_both_directions(self):
        files = {W + 'Identity.c': '''class HCIdentity
{
    bool Engine()
    {
        string seen;
        GetGame().GetVersion(seen);
        return seen == "1.30.164289.70";
    }
    bool Reversed(string build)
    {
        return "1.30." != build;
    }
    bool Profile(HCProfile profile)
    {
        return profile.BuildVersion == "build 1.30.164289";
    }
    void Admit()
    {
        string seen;
        GetGame().GetVersion(seen);
        string alias = seen;
        if (alias != "1.30.164289") return;
    }
    bool Direct()
    {
        return GetVersion() == "1.30.164289";
    }
}
'''}
        self.assertEqual([('Identity.c', 7, 'HCIdentity.Engine'),
                          ('Identity.c', 11, 'HCIdentity.Reversed'),
                          ('Identity.c', 15, 'HCIdentity.Profile'),
                          ('Identity.c', 22, 'HCIdentity.Admit'),
                          ('Identity.c', 26, 'HCIdentity.Direct')],
                         where(run(files, 'HC-S004')))

    def test_print_or_log_must_be_code_in_the_same_method(self):
        for emitter in ('Print("[HC] mismatch");', 'PrintFormat("%1", build);',
                        'HCIdentityLog.Mismatch(build);', 'LogMismatch(build);'):
            with self.subTest(emitter=emitter):
                text = ('class HCI { bool Gate(string build) { ' + emitter
                        + ' return build == "1.30.164289"; } }')
                self.assertEqual([], run({W + 'I.c': text}, 'HC-S004'))
        text = '''class HCI {
    void Other() { Print("logged elsewhere"); }
    bool Gate(string build) {
        // Print("not a log");
        string text = "Print(build)";
        return build != "1.30.164289";
    }
}'''
        self.assertEqual([('I.c', 6, 'HCI.Gate')], where(run({W + 'I.c': text}, 'HC-S004')))

    def test_only_literal_engine_or_build_comparisons_are_identity_findings(self):
        text = '''class HCI {
    bool Shared(string build) { return HCBuildIdentity.Matches(build); }
    bool Values(string label, string other) { return label == other; }
    bool Label(string label) { return label == "release 1.30."; }
    bool Dependency(HCProfile p) { return p.ProviderVersion == "1.9.84"; }
    bool Empty(string build) { return build == ""; }
    bool Unrelated() {
        string observed;
        GetGame().GetVersion(observed);
        return label == "1.30.164289";
    }
    string Documentation() { return "build == \\\"1.30.164289\\\""; }
    // bool Comment(string build) { return build == "1.30.164289"; }
}'''
        self.assertEqual([], run({W + 'I.c': text}, 'HC-S004'))

    def test_build_aliases_two_component_versions_and_non_logger_names(self):
        text = '''class HCI {
    bool Gate(string build) {
        Catalog();
        string pin = build;
        return pin == "1.30";
    }
}'''
        self.assertEqual([('I.c', 5, 'HCI.Gate')], where(run({W + 'I.c': text}, 'HC-S004')))


class SilentRefusals(unittest.TestCase):
    # Shaped after HCSearchHouses.Begin: the client predicted the search, the server returned
    # silently, the progress ring spun and stopped with no message and no log line.
    BEGIN = ('class HCSearchHouses\n{\n    bool m_Started;\n    void Begin(ActionData data)\n    {\n'
             '        if (!data || !data.m_Player) return;\n'
             '        HCHit hit = Resolve(data.m_Player, data.m_Target);\n'
             '        if (!hit || SessionOfSite(hit.SiteId)) return;\n'
             '        string actorId = ActorOf(data.m_Player);\n'
             '        if (actorId == "" || !EnsureJournal()) return;\n'
             '        if (!Gate(data.m_Player))\n        {\n            Refuse(data.m_Player, "search.gate");\n            return;\n        }\n'
             '        if (m_Busy)\n        {\n            houses.Begin(data);\n            return;\n        }\n'
             '        if (!GetGame().IsServer()) return;\n    }\n'
             '    bool Gate(PlayerBase player)\n    {\n        if (!m_Started || m_Fault) return false;\n'
             '        if (!player.IsAlive()) { m_Reason = HCRefusal.DEAD; return false; }\n        return true;\n    }\n'
             '    bool EnsureJournal(out string reason)\n    {\n        if (!OpenJournal()) { reason = "journal"; return false; }\n        return true;\n    }\n'
             '    static bool CanStartPolicy(int a) { if (a < 0) return false; return true; }\n'
             '    override void OnStart(HCSettings settings)\n    {\n        if (m_Started || !IsEnabled(settings)) return;\n'
             '        if (!LoadConfig()) return;\n    }\n}\n')

    def test_silent_early_returns_in_server_commit_points_are_flagged(self):
        found = run({W + 'Loot/HCSearchHouses.c': self.BEGIN}, 'HC-S001')
        self.assertEqual([('HCSearchHouses.c', 8, 'HCSearchHouses.Begin'), ('HCSearchHouses.c', 10, 'HCSearchHouses.Begin'),
                          ('HCSearchHouses.c', 38, 'HCSearchHouses.OnStart')], where(found))
        self.assertIn('actorId == "" || !EnsureJournal()', found[1].message)

    def test_silent_false_in_server_gates_is_flagged(self):
        found = run({W + 'Loot/HCSearchHouses.c': self.BEGIN}, 'HC-S002')
        self.assertEqual([('HCSearchHouses.c', 25, 'HCSearchHouses.Gate')], where(found))

    # Shaped after the 64b22ab search fix: a member reason code set before each refusal and
    # reported by the caller is a reason; clearing it to "" is not.
    MEMBER_REASON = ('class HCSearchHouses\n{\n    string m_Refusal;\n    bool Admit(HCHit hit)\n    {\n'
                     '        if (!hit) return false;\n'
                     '        m_Refusal = "busy";\n'
                     '        if (SessionOfSite(hit.SiteId)) return false;\n'
                     '        m_Refusal = "";\n'
                     '        if (Full()) return false;\n        return true;\n    }\n}\n')

    def test_a_member_reason_code_set_before_the_refusal_counts_as_a_reason(self):
        found = run({W + 'Loot/HCSearchHouses.c': self.MEMBER_REASON}, 'HC-S002')
        self.assertEqual([('HCSearchHouses.c', 10, 'HCSearchHouses.Admit')], where(found))

    def test_harness_classes_are_not_gameplay_gates(self):
        text = self.BEGIN.replace('HCSearchHouses', 'HCGroupNativeChecks')
        self.assertEqual([], run({W + 'Groups/HCGroupNativeChecks.c': text}, 'HC-S001'))

    ACTION = ('class HCActionPry : ActionContinuousBase\n{\n'
              '    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)\n    {\n'
              '        if (!GetGame().IsServer()) return Preview(player, target);\n'
              '        return HCPry.Get().CanStart(player, target);\n    }\n'
              '    override void OnStartServer(ActionData action_data)\n    {\n        HCPry.Get().BeginPry(action_data);\n    }\n}\n'
              'class HCPry\n{\n    void BeginPry(ActionData data)\n    {\n        if (!Ready()) { TELL; return; }\n    }\n}\n')

    def test_predicted_action_needs_a_server_path_that_messages_the_player(self):
        silent = self.ACTION.replace('TELL;', '')
        self.assertEqual([('A.c', 1, 'HCActionPry')], where(run({W + 'A.c': silent}, 'HC-S003')))
        told = self.ACTION.replace('TELL;', 'data.m_Player.MessageStatus("Nothing to pry here.");')
        self.assertEqual([], run({W + 'A.c': told}, 'HC-S003'))


class Baseline(unittest.TestCase):
    def test_new_and_stale_entries_are_reported_by_identity_not_line(self):
        first = run({W + 'T.c': 'class HCT\n{\n    int A(bool b) { return b ? 1 : 0; }\n}\n'})
        baseline = lint.baseline_from(first, 'reviewed in test')
        moved = run({W + 'T.c': '\n\nclass HCT\n{\n    int A(bool b) { return b ? 1 : 0; }\n}\n'})
        self.assertEqual(([], []), lint.compare(moved, baseline, False))
        added = run({W + 'T.c': 'class HCT\n{\n    int A(bool b) { return b ? 1 : 0; }\n    int B(bool b) { return b ? 2 : 0; }\n}\n'})
        new, stale = lint.compare(added, baseline, False)
        self.assertEqual([4], [f.line for f in new])
        new, stale = lint.compare([], baseline, False)
        self.assertEqual((0, 1), (len(new), len(stale)))

    def test_native_only_entries_are_ignored_without_the_engine_cache(self):
        baseline = {'entries': [{'rule': 'HC-E007', 'path': 'p', 'symbol': 's', 'key': 'k', 'native': True}]}
        self.assertEqual(([], []), lint.compare([], baseline, False))
        self.assertEqual(1, len(lint.compare([], baseline, True)[1]))

    def test_cli_fails_on_a_new_trap_and_passes_once_it_is_baselined(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'mods/HollowCountry/scripts/4_World/T.c'
            source.parent.mkdir(parents=True)
            source.write_text('class HCT\n{\n    int A(bool b) { return b ? 1 : 0; }\n}\n', encoding='utf-8')
            baseline = root / 'baseline.json'
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(1, lint.main(['--root', temporary, '--no-native', '--baseline', str(baseline)]))
                self.assertEqual(0, lint.main(['--root', temporary, '--no-native', '--baseline', str(baseline),
                                               '--write-baseline', 'test review']))
                self.assertEqual(0, lint.main(['--root', temporary, '--no-native', '--baseline', str(baseline)]))
            self.assertIn('NEW  mods/HollowCountry/scripts/4_World/T.c:3: HC-E001', out.getvalue())


class CompileFormulaShapes(unittest.TestCase):
    # #313: build 132 compile gate refused both shapes (fixed in 386809e1).
    def concat(self, operands):
        return 'class A { void F() { string s = "a"' + ' + x' * operands + '; } }'

    def test_string_assignment_is_flagged_only_beyond_the_operand_limit(self):
        limit = lint.MAX_STRING_PLUS
        self.assertEqual([], run({W + 'A.c': self.concat(limit)}, 'HC-E020'))
        self.assertEqual(1, len(run({W + 'A.c': self.concat(limit + 1)}, 'HC-E020')))

    def test_long_concatenation_passed_straight_to_a_call_is_not_flagged(self):
        text = 'class A { void F() { Print("a"' + ' + x' * (lint.MAX_STRING_PLUS * 2) + '); } }'
        self.assertEqual([], run({W + 'A.c': text}, 'HC-E020'))

    def test_line_led_by_a_binary_operator_is_flagged_and_increment_is_not(self):
        for operator in ('||', '&&', '+', '==', '!='):
            with self.subTest(operator=operator):
                text = 'class A { bool F() {\n return a\n ' + operator + ' b; } }'
                self.assertEqual(1, len(run({W + 'A.c': text}, 'HC-E021')))
        text = 'class A { void F() {\n ++i;\n // || in a comment\n Print("|| in a string");\n } }'
        self.assertEqual([], run({W + 'A.c': text}, 'HC-E021'))


class CurrentTree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.findings = lint.lint(es.mod_sources(ROOT))
        cls.baseline = lint.load_baseline()

    def test_authored_sources_add_no_finding_beyond_the_reviewed_baseline(self):
        new, stale = lint.compare(self.findings, self.baseline, native_available=False)
        self.assertEqual([], [f.render() for f in new], 'fix the new finding; baseline only reviewed legacy cases')
        self.assertEqual([], stale, 'a baselined finding is gone: remove it from enforce_lint_baseline.json')

    def test_every_baseline_entry_carries_a_review_note(self):
        entries = self.baseline['entries']
        self.assertTrue(entries)
        for entry in entries:
            self.assertIn(entry['rule'], lint.RULES)
            self.assertTrue(entry.get('review', '').strip())
            self.assertNotIn('UNREVIEWED', entry['review'])
        self.assertEqual(entries, json.loads(json.dumps(entries)))

    def test_the_compile_trap_rules_have_no_baselined_exceptions(self):
        # Compile traps stop a native boot outright; they are fixed, never baselined.
        self.assertEqual([], [e for e in self.baseline['entries'] if e['rule'] in ('HC-E001', 'HC-E002', 'HC-E003',
                                                                                   'HC-E004', 'HC-E005', 'HC-E007', 'HC-E008',
                                                                                   'HC-E020', 'HC-E021', 'HC-L001')])


if __name__ == '__main__':
    unittest.main()
