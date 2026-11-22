"""Precision cases for tools/validate/enforce_perf.py (offline lint tooling only).

Each case feeds a small synthetic Enforce source to check(); nothing here
establishes DayZ behaviour. Every precision rule has a clearing case and a
neighbouring case that must keep flagging.
"""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.validate import enforce_perf as perf
from tools.validate import enforce_source as es


def findings(text, rule=None):
    result = perf.check([es.Source(Path('/virtual/mods/HollowCountry/scripts/4_World/T.c'), text, Path('/virtual'))],
                        Path('/virtual'))
    return [f for f in result if rule is None or f.rule == rule]


class P004ArrayGetTests(unittest.TestCase):
    NESTED = '''
class A
{
    void F(array<string> keys, array<string> rows)
    {
        for (int i = 0; i < keys.Count(); i++)
        {
            string key = keys.Get(i);
            %s
        }
    }
}
'''

    def test_array_get_by_index_is_not_a_scan(self):
        self.assertEqual(findings(self.NESTED % 'string row = rows.Get(i);', 'HC-P004'), [])

    def test_array_find_in_a_loop_still_flags(self):
        found = findings(self.NESTED % 'int at = rows.Find(key);', 'HC-P004')
        self.assertEqual([f.key for f in found], ['rows.Find#1'])


class P001BoundTests(unittest.TestCase):
    def scan(self, body, params='string text, int cursor'):
        text = 'class A\n{\n    static const int LIMIT = 256;\n    void F(%s)\n    {\n%s\n    }\n}\n' % (params, body)
        return [f.key for f in findings(text, 'HC-P001')]

    def test_constant_length_substring_is_bounded(self):
        self.assertEqual(self.scan('for (int i = 0; i < 9; i++) { string c = text.Substring(i, 1); }'), [])
        self.assertEqual(self.scan('for (int i = 0; i < 9; i++) { string c = text.Substring(i, LIMIT); }'), [])

    def test_variable_or_oversized_substring_still_flags(self):
        self.assertEqual(self.scan('for (int i = 0; i < 9; i++) { string c = text.Substring(i, cursor); }'),
                         ['text.Substring#1'])
        self.assertEqual(self.scan('for (int i = 0; i < 9; i++) { string c = text.Substring(i, 2048); }'),
                         ['text.Substring#1'])

    def test_local_from_short_pieces_is_bounded(self):
        body = ('string piece = text.Substring(0, 4);\n'
                'for (int i = 0; i < 9; i++) { int at = piece.IndexOf("x"); }')
        self.assertEqual(self.scan(body), [])
        # One unbounded write defeats the bound.
        long_body = body.replace('text.Substring(0, 4)', 'text.Substring(0, cursor)')
        self.assertEqual(self.scan(long_body), ['piece.IndexOf#1'])

    def test_single_character_get_local_is_bounded(self):
        body = ('string ch = text.Get(0);\n'
                'for (int i = 0; i < 9; i++) { int at = ch.IndexOf("x"); }')
        self.assertEqual(self.scan(body), [])

    def test_parameter_is_never_bounded_by_a_short_write(self):
        body = ('if (cursor > 0) { piece = text.Substring(0, 4); }\n'
                'for (int i = 0; i < 9; i++) { int at = piece.IndexOf("x"); }')
        self.assertEqual(self.scan(body, 'string piece, int cursor, string text'), ['piece.IndexOf#1'])

    def test_length_guards_with_constants_and_ge(self):
        loop = 'for (int i = 0; i < 9; i++) { int at = text.IndexOf("x"); }'
        self.assertEqual(self.scan('if (text.Length() > LIMIT) { return; }\n' + loop), [])
        self.assertEqual(self.scan('if (text.Length() >= LIMIT) { return; }\n' + loop), [])
        self.assertEqual(self.scan('if (text.Length() > 4096) { return; }\n' + loop), ['text.IndexOf#1'])

    def test_greater_than_guard_with_literal_only_callers(self):
        template = '''
class A
{
    static bool Check(string text, int limit)
    {
        if (text.Length() > limit) { return false; }
        for (int i = 0; i < 9; i++) { int at = text.IndexOf("x"); }
        return true;
    }
    void G(string s) { A.Check(s, %s); }
}
'''
        self.assertEqual(findings(template % '96', 'HC-P001'), [])
        self.assertEqual([f.key for f in findings(template % 'cursor', 'HC-P001')], ['text.IndexOf#1'])


class LatchTests(unittest.TestCase):
    def test_early_return_latch_clears_load_once_io(self):
        src = '''
class Cfg
{
    protected static ref Cfg s_Config;
    static Cfg Get()
    {
        if (s_Config) { return s_Config; }
        s_Config = new Cfg;
        if (FileExist("$profile:x.json")) { return s_Config; }
        return s_Config;
    }
}
class M
{
    void OnTick() { Cfg.Get(); }
}
'''
        self.assertEqual(findings(src, 'HC-P003'), [])

    def test_wrapped_latch_clears_calls_inside(self):
        src = '''
class Cfg
{
    protected static bool s_Checked;
    protected static bool s_On;
    static bool On()
    {
        if (!s_Checked)
        {
            s_Checked = true;
            s_On = !FileExist("$profile:x.disable");
        }
        return s_On;
    }
}
class M
{
    void OnTick() { Cfg.On(); }
}
'''
        self.assertEqual(findings(src, 'HC-P003'), [])

    def test_ungated_io_stays_flagged(self):
        src = '''
class Cfg
{
    static bool On() { return !FileExist("$profile:x.disable"); }
}
class M
{
    void OnTick() { Cfg.On(); }
}
'''
        self.assertEqual([f.key for f in findings(src, 'HC-P003')], ['FileExist#1'])

    def test_conditional_latch_set_stays_flagged(self):
        src = '''
class Cfg
{
    protected static bool s_Checked;
    static bool On(bool ok)
    {
        if (!s_Checked)
        {
            if (ok) { s_Checked = true; }
            return !FileExist("$profile:x.disable");
        }
        return true;
    }
}
class M
{
    void OnTick() { Cfg.On(true); }
}
'''
        self.assertEqual([f.key for f in findings(src, 'HC-P003')], ['FileExist#1'])

    def test_return_before_the_set_stays_flagged(self):
        src = '''
class Cfg
{
    protected static ref Cfg s_Config;
    static Cfg Get()
    {
        if (s_Config) { return s_Config; }
        if (!FileExist("$profile:x.json")) { return null; }
        s_Config = new Cfg;
        return s_Config;
    }
}
class M
{
    void OnTick() { Cfg.Get(); }
}
'''
        self.assertEqual([f.key for f in findings(src, 'HC-P003')], ['FileExist#1'])

    def test_latch_reset_on_a_tick_path_stays_flagged(self):
        src = '''
class Cfg
{
    protected static bool s_Checked;
    static bool On()
    {
        if (!s_Checked)
        {
            s_Checked = true;
            return !FileExist("$profile:x.disable");
        }
        return true;
    }
    static void Forget() { s_Checked = false; }
}
class M
{
    void OnTick() { Cfg.On(); Cfg.Forget(); }
}
'''
        self.assertEqual([f.key for f in findings(src, 'HC-P003')], ['FileExist#1'])

    def test_print_behind_a_set_once_latch_is_not_per_item(self):
        src = '''
class M
{
    protected bool m_Warned;
    void OnTick()
    {
        for (int i = 0; i < 40; i++)
        {
            if (!m_Warned) { Print("once"); m_Warned = true; }
        }
    }
}
'''
        self.assertEqual(findings(src, 'HC-P005'), [])

    def test_print_in_loop_without_latch_flags(self):
        src = '''
class M
{
    void OnTick()
    {
        for (int i = 0; i < 40; i++) { Print("each"); }
    }
}
'''
        self.assertEqual([f.key for f in findings(src, 'HC-P005')], ['Print#1'])

    def test_print_directly_before_return_is_once_per_call(self):
        src = '''
class M
{
    void OnTick()
    {
        for (int i = 0; i < 40; i++)
        {
            if (i == 3) { Print("stop"); return; }
        }
    }
}
'''
        self.assertEqual(findings(src, 'HC-P005'), [])

    def test_store_save_behind_a_latch_is_not_per_tick(self):
        src = '''
class FooStore { bool Save() { return true; } }
class M
{
    protected ref FooStore m_Store;
    protected bool m_Migrated;
    void OnTick()
    {
        if (!m_Migrated) { m_Migrated = true; m_Store.Save(); }
    }
}
'''
        self.assertEqual(findings(src, 'HC-P008'), [])
        self.assertEqual([f.key for f in findings(src.replace('m_Migrated = true; ', ''), 'HC-P008')],
                         ['m_Store.Save#1'])


class BaselineRatchetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'mods/HollowCountry/scripts/4_World/Fixture.c'
        self.source.parent.mkdir(parents=True)
        self.source.write_text('class Fixture\n{\n    void OnTick(float dt)\n    {\n        FileExist("fixture");\n    }\n}')
        self.live = perf.check(es.mod_sources(self.root), self.root)
        self.assertTrue(self.live)
        self.kept = [perf.asdict(f) for f in self.live]
        self.stale = dict(self.kept[0], symbol='Removed.OnTick')
        self.baseline = {'version': 1, 'note': 'keep review metadata', 'findings': [*self.kept, self.stale]}
        self.path = self.root / 'baseline.json'
        self.path.write_text(json.dumps(self.baseline))

    def run_cli(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            result = perf.main(['--root', str(self.root), '--baseline', str(self.path), *args])
        return result, output.getvalue()

    def test_stale_report_and_strict_are_read_only(self):
        before = self.path.read_bytes()
        result, output = self.run_cli()
        self.assertEqual(result, 0)
        self.assertIn(self.stale['symbol'], output)
        self.assertEqual(self.run_cli('--strict-baseline')[0], 1)
        self.assertEqual(self.path.read_bytes(), before)

    def test_ratchet_preserves_entries_and_never_admits_new_findings(self):
        self.source.write_text(self.source.read_text().replace('FileExist("fixture");', 'FileExist("fixture"); OpenFile("fixture", FileMode.READ);'))
        self.assertEqual(self.run_cli('--ratchet', '--strict-baseline')[0], 1)
        self.assertEqual(json.loads(self.path.read_text()), dict(self.baseline, findings=self.kept))
        before = self.path.read_bytes()
        self.run_cli('--ratchet')
        self.assertEqual(self.path.read_bytes(), before)

    def test_selected_paths_use_full_live_graph_for_staleness(self):
        other = self.source.with_name('Other.c')
        other.write_text('class Other\n{\n    void OnTick(float dt)\n    {\n        FileExist("other");\n    }\n}')
        all_live = perf.check(es.mod_sources(self.root), self.root)
        self.path.write_text(json.dumps(dict(self.baseline, findings=[perf.asdict(f) for f in all_live])))
        self.assertEqual(self.run_cli('--strict-baseline', str(self.source))[0], 0)

    def test_legacy_alias_can_prune_to_empty(self):
        self.source.write_text('class Fixture {}')
        self.assertEqual(self.run_cli('--prune-baseline', '--strict-baseline')[0], 0)
        self.assertEqual(json.loads(self.path.read_text())['findings'], [])


class ConstantLoopTests(unittest.TestCase):
    """P009: a counting loop with a constant, small trip count is not an unbounded scan."""
    TEXT = '''
class M
{
    void OnStart() { for (int i = 0; i < %s; i++) { Probe(i); } }
    void Probe(int i) { if (FileExist("$profile:a")) { return; } }
}
'''

    def keys(self, limit):
        return [f.key for f in findings(self.TEXT % limit, 'HC-P009')]

    def test_small_constant_trip_count_is_bounded(self):
        self.assertEqual([], self.keys(perf.TRIP_LOOP_CAP))

    def test_trip_count_over_the_cap_stays_flagged(self):
        self.assertEqual(['FileExist#1'], self.keys(perf.TRIP_LOOP_CAP + 1))

    def test_computed_bound_stays_flagged(self):
        self.assertEqual(['FileExist#1'], self.keys('m_Rows.Count()'))

    def test_nest_product_over_the_cap_stays_flagged(self):
        side = int(perf.TRIP_PRODUCT_CAP ** 0.5) + 1
        text = self.TEXT % side
        text = text.replace('Probe(i);', 'for (int j = 0; j < %d; j++) { Probe(j); }' % side)
        self.assertEqual(['FileExist#1'], [f.key for f in findings(text, 'HC-P009')])


class CappedRetryTests(unittest.TestCase):
    """A CallLater re-arm under a constant retry counter is a finite retry, not a tick."""
    TEXT = '''
class M
{
    int m_Tries;
    void Start() { %s }
    void Work() { FileHandle h = OpenFile("$profile:x.json", FileMode.READ); CloseFile(h); %s }
}
'''
    LATER = 'GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Work, 1000, false);'

    def keys(self, rearm, reset=''):
        return [f.key for f in findings(self.TEXT % (self.LATER, rearm + reset), 'HC-P003')]

    def test_counter_capped_rearm_is_not_a_root(self):
        cap = perf.TRIP_LOOP_CAP
        self.assertEqual([], self.keys('if (m_Tries < %d) { m_Tries++; %s }' % (cap, self.LATER)))

    def test_uncapped_rearm_stays_a_root(self):
        self.assertEqual(['OpenFile#1'], self.keys(self.LATER))

    def test_cap_over_the_limit_stays_a_root(self):
        cap = perf.TRIP_LOOP_CAP + 1
        self.assertEqual(['OpenFile#1'], self.keys('if (m_Tries < %d) { m_Tries++; %s }' % (cap, self.LATER)))

    def test_callback_that_resets_the_counter_stays_a_root(self):
        self.assertEqual(['OpenFile#1'], self.keys('if (m_Tries < 3) { m_Tries++; %s }' % self.LATER, 'm_Tries = 0;'))


class ShutdownResetTests(unittest.TestCase):
    """A latch reset reachable only from OnStop is not a tick-path reset."""
    TEXT = '''
class Store
{
    bool m_Loaded;
    void Reset() { m_Loaded = false; }
    void Load() { if (m_Loaded) { return; } m_Loaded = true; if (FileExist("$profile:a")) { OpenFile("$profile:a", FileMode.READ); } }
}
class Mod
{
    ref Store m_Store;
    void OnStart() { m_Store = new Store; }
    void OnTick(float dt) { m_Store.Load(); %s }
    void OnStop() { m_Store.Reset(); }
}
'''

    def test_reset_from_on_stop_keeps_the_latch(self):
        self.assertEqual([], findings(self.TEXT % '', 'HC-P003'))

    def test_reset_from_the_tick_path_stays_flagged(self):
        self.assertEqual(['FileExist#1', 'OpenFile#1'],
                         sorted(f.key for f in findings(self.TEXT % 'm_Store.Reset();', 'HC-P003')))


class ConcreteFieldDispatchTests(unittest.TestCase):
    """A field only ever assigned `new T` dispatches to T's lineage, not every override."""
    TEXT = '''
class Base { void Work() {} }
class Quiet : Base { override void Work() {} }
class Loud : Base { override void Work() { FileExist("$profile:a"); } }
class Mod
{
    ref Base m_Impl;
    void OnStart() { m_Impl = new Quiet; }
    %s
    void OnTick(float dt) { m_Impl.Work(); }
}
'''

    def keys(self, extra):
        return [f.key for f in findings(self.TEXT % extra, 'HC-P003')]

    def test_single_constructed_type_excludes_sibling_overrides(self):
        self.assertEqual([], self.keys(''))

    def test_second_constructed_type_keeps_the_override(self):
        self.assertEqual(['FileExist#1'], self.keys('void Swap() { m_Impl = new Loud; }'))

    def test_assignment_from_a_parameter_keeps_the_override(self):
        self.assertEqual(['FileExist#1'], self.keys('void Set(Base impl) { m_Impl = impl; }'))


class StagedStepTests(unittest.TestCase):
    """A step that advances a cursor and does at most STAGE_OPS file operations is one stage."""
    TEXT = '''
class Job
{
    int m_Cursor;
    ref array<string> m_Rows;
    void Write() { FileHandle h = OpenFile("$profile:s", FileMode.WRITE); CloseFile(h); }
    void HCStep() { %s }
}
'''

    def keys(self, body):
        return [f.key for f in findings(self.TEXT % body, 'HC-P003')]

    def test_single_operation_with_a_cursor_is_a_stage(self):
        self.assertEqual([], self.keys('m_Cursor++; Write();'))

    def test_operation_in_a_loop_stays_flagged(self):
        self.assertEqual(['OpenFile#1'], self.keys('for (int i = 0; i < m_Rows.Count(); i++) { Write(); } m_Cursor++;'))

    def test_step_without_a_cursor_stays_flagged(self):
        self.assertEqual(['OpenFile#1'], self.keys('Write();'))

    def test_more_operations_than_a_stage_stay_flagged(self):
        body = 'm_Cursor++; ' + 'Write(); ' * (perf.STAGE_OPS + 1)
        self.assertEqual(['OpenFile#1'], self.keys(body))

    def test_branches_cost_the_larger_arm_not_the_sum(self):
        self.assertEqual([], self.keys('m_Cursor++; if (m_Rows) { Write(); } else { Write(); }'))


class ConsumeLatchTests(unittest.TestCase):
    """`if (!latch) return;` then `latch = null;` makes the rest of the method once-per-arming."""
    TEXT = '''
class Job { bool Busy; }
class Pump
{
    static ref Job s_Job;
    static void Begin(Job job) { s_Job = job; }
    static void Run()
    {
        if (!s_Job) { return; }
        if (s_Job.Busy) { return; }
        FileExist("$profile:a");
        s_Job = null;
        DeleteFile("$profile:a");
    }
}
class HCServer
{
    void OnTick(float dt) { Pump.Run(); }
    %s
}
'''

    def keys(self, extra):
        return [f.key for f in findings(self.TEXT % extra, 'HC-P003')]

    def test_consumed_latch_clears_the_work_after_the_guards(self):
        self.assertEqual([], self.keys(''))

    def test_latch_armed_again_on_a_tick_path_stays_flagged(self):
        self.assertEqual(['DeleteFile#1', 'FileExist#1'], sorted(self.keys('void OnUpdate(float dt) { Pump.Begin(new Job); }')))

    def test_work_before_the_last_guard_stays_flagged(self):
        text = self.TEXT.replace('if (s_Job.Busy) { return; }', 'FileExist("$profile:b"); if (s_Job.Busy) { return; }')
        self.assertEqual(['FileExist#1'], [f.key for f in findings(text % '', 'HC-P003')])


if __name__ == '__main__':
    unittest.main()


class CallbackRootTests(unittest.TestCase):
    """B-14: CallLater targets that repeat or re-arm are tick roots."""
    TEXT = '''
class HCProbe
{
    void Start() { %s }
    void Work() { FileHandle h = OpenFile("$profile:x.json", FileMode.READ); CloseFile(h); %s }
}
'''

    def keys(self, schedule, rearm=''):
        return [f.key for f in findings(self.TEXT % (schedule, rearm), 'HC-P003')]

    def test_repeating_call_later_target_is_a_root(self):
        self.assertEqual(['OpenFile#1'], self.keys('GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Work, 1000, true);'))

    def test_one_shot_call_later_target_is_not_a_root(self):
        self.assertEqual([], self.keys('GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Work, 1000, false);'))
        self.assertEqual([], self.keys('GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Work, 1000);'))

    def test_self_rearming_one_shot_is_a_root(self):
        schedule = 'GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Work, 1000, false);'
        self.assertEqual(['OpenFile#1'], self.keys(schedule, schedule))

    def test_call_later_by_name_uses_the_string_callback(self):
        self.assertEqual(['OpenFile#1'], self.keys(
            'GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLaterByName(this, "Work", 1000, true);'))
        self.assertEqual([], self.keys(
            'GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLaterByName(this, "Work", 1000, false);'))


class P010PrivateBudgetTests(unittest.TestCase):
    """A module-owned budget has no other consumer; the shared pool and unprovable receivers keep flagging."""
    BUDGET = 'class HCUnitBudget { bool HCTake(int cost) { return true; } void HCSetProfile(int x) {} }\n'

    def keys(self, body, fields='', params=''):
        text = self.BUDGET + 'class M\n{\n%s\n    void F(%s)\n    {\n%s\n    }\n}\n' % (fields, params, body)
        return [f.key for f in findings(text, 'HC-P010')]

    def test_field_only_ever_new_or_null_is_private(self):
        fields = '    ref HCUnitBudget m_Budget = new HCUnitBudget();'
        self.assertEqual(self.keys('m_Budget.HCTake(1);', fields), [])
        self.assertEqual(self.keys('m_Budget = new HCUnitBudget(); m_Budget.HCTake(1);', fields), [])

    def test_local_new_budget_is_private(self):
        self.assertEqual(self.keys('HCUnitBudget budget = new HCUnitBudget(); budget.HCTake(1);'), [])

    def test_alias_of_the_shared_accessor_stays_flagged(self):
        fields = '    ref HCUnitBudget m_Budget;'
        self.assertEqual(self.keys('m_Budget = HCServer.HCTickWork(); m_Budget.HCTake(1);', fields), ['HCTake#1'])
        self.assertEqual(self.keys('HCUnitBudget budget = HCServer.HCTickWork(); budget.HCTake(1);'), ['HCTake#1'])

    def test_parameter_receiver_stays_flagged(self):
        self.assertEqual(self.keys('budget.HCTake(1);', params='HCUnitBudget budget'), ['HCTake#1'])

    def test_profiled_budget_is_attributed_so_stays_flagged(self):
        fields = '    ref HCUnitBudget m_Budget = new HCUnitBudget();'
        self.assertEqual(self.keys('m_Budget.HCSetProfile(1); m_Budget.HCTake(1);', fields), ['HCTake#1'])

    def test_shared_accessor_chain_stays_flagged(self):
        self.assertEqual(self.keys('HCServer.HCTickWork().HCTake(1);'), ['HCTake#1'])


class P001FieldBoundTests(unittest.TestCase):
    """A string field whose every write is provably capped is bounded; any unproven write defeats it."""
    SOURCE = '''
class A
{
    static const int CHUNK = 32768;
    string m_Window;
    void Load(FileHandle h) { FGets(h, m_Window, CHUNK); }
    void Fill(string other) { %s }
    void Scan()
    {
        for (int i = 0; i < 9; i++) { int at = m_Window.IndexOf("x"); }
    }
}
'''

    def keys(self, write):
        return [f.key for f in findings(self.SOURCE % write, 'HC-P001')]

    def test_capped_reads_bound_the_field(self):
        self.assertEqual(self.keys(''), [])

    def test_unproven_write_defeats_the_bound(self):
        self.assertEqual(self.keys('m_Window = other;'), ['m_Window.IndexOf#1'])

    def test_oversized_read_cap_does_not_bound(self):
        text = self.SOURCE.replace('CHUNK = 32768', 'CHUNK = 1048576') % ''
        self.assertEqual([f.key for f in findings(text, 'HC-P001')], ['m_Window.IndexOf#1'])


class P001RefusalBlockTests(unittest.TestCase):
    """A block that always returns bounds the scan after it; a write inside the refusing branch does not."""
    SOURCE = '''
class A
{
    void F(string text)
    {
        if (text.Length() > 256)
        {
            %s
        }
        for (int i = 0; i < 9; i++) { int at = text.IndexOf("x"); }
    }
}
'''

    def keys(self, inside):
        return [f.key for f in findings(self.SOURCE % inside, 'HC-P001')]

    def test_block_that_ends_in_return_is_a_refusal_guard(self):
        self.assertEqual(self.keys('Print("too long"); return;'), [])

    def test_conditional_return_is_not_a_guard(self):
        self.assertEqual(self.keys('if (i > 0) { return; }'), ['text.IndexOf#1'])

    def test_block_without_return_is_not_a_guard(self):
        self.assertEqual(self.keys('Print("too long");'), ['text.IndexOf#1'])


class P008DurabilityBarrierTests(unittest.TestCase):
    """A Save only reachable through a module OnStop is the shutdown barrier; other tick-reachable Saves flag."""
    SOURCE = '''
class FooStore { bool Save() { return true; } }
class M
{
    ref FooStore m_Store = new FooStore();
    override void OnStop() { Flush(); }
    void Flush() { m_Store.Save(); }
    void OnUpdate() { %s }
}
'''

    def keys(self, tick):
        return [f.key for f in findings(self.SOURCE % tick, 'HC-P008')]

    def test_save_reached_only_from_on_stop_is_a_barrier(self):
        self.assertEqual(self.keys('OnStop();'), [])
        self.assertEqual(self.keys(''), [])

    def test_save_also_reached_without_on_stop_still_flags(self):
        self.assertEqual(self.keys('Flush();'), ['m_Store.Save#1'])


class P005SingleLinePerPassTests(unittest.TestCase):
    def test_print_after_the_loop_is_not_per_item(self):
        text = '''
class M
{
    void OnUpdate()
    {
        string lines = "";
        for (int i = 0; i < 9; i++) { lines += "x"; }
        Print("" + lines);
    }
}
'''
        self.assertEqual([f.key for f in findings(text, 'HC-P005')], [])
        looped = text.replace('{ lines += "x"; }', '{ Print("x"); }')
        self.assertEqual([f.key for f in findings(looped, 'HC-P005')], ['Print#1'])


class ParameterDispatchTests(unittest.TestCase):
    """A parameter's virtual call dispatches only to the classes authored call sites pass."""
    TEXT = '''
class Job { int HCStep() { return 0; } }
class QuietJob : Job { override int HCStep() { return 0; } }
class FileJob : Job
{
    int m_Index;
    override int HCStep()
    {
        for (int i = 0; i < 3; i++) { if (FileExist("$profile:f" + i + ".json")) { m_Index++; } }
        return 0;
    }
}
class Sched
{
    static void Flush(Job job) { while (job.HCStep() == 1) { } }
}
class Holder
{
    bool m_Flag;
    %s
    void Run() { Sched.Flush(%s); }
}
class M
{
    ref Holder m_Holder = new Holder;
    void OnStart() { m_Holder.Run(); }
}
'''

    def keys(self, field, argument, rule='HC-P009'):
        return [f.key for f in findings(self.TEXT % (field, argument), rule)]

    def test_exact_field_limits_dispatch_to_its_class(self):
        self.assertEqual(self.keys('ref Job m_Job = new QuietJob;', 'm_Job'), [])

    def test_new_expression_limits_dispatch_to_its_class(self):
        self.assertEqual(self.keys('', 'new QuietJob'), [])

    def test_caller_passing_the_io_class_still_flags(self):
        self.assertTrue(self.keys('ref Job m_Job = new FileJob;', 'm_Job'))

    def test_second_call_site_passing_the_io_class_still_flags(self):
        text = (self.TEXT % ('ref Job m_Job = new QuietJob;', 'm_Job')).replace(
            'class M\n', 'class Other { void Go() { Sched.Flush(new FileJob); } }\nclass M\n')
        self.assertTrue([f.key for f in findings(text, 'HC-P009')])

    def test_unresolvable_argument_keeps_full_dispatch(self):
        text = (self.TEXT % ('', 'Pick()')).replace('void Run()', 'Job Pick() { return null; }\n    void Run()')
        self.assertTrue([f.key for f in findings(text, 'HC-P009')])

    def test_reassigned_parameter_keeps_full_dispatch(self):
        text = (self.TEXT % ('ref Job m_Job = new QuietJob;', 'm_Job')).replace(
            'static void Flush(Job job) {',
            'static Job Fallback() { return new FileJob; }\n    static void Flush(Job job) { job = Fallback();')
        self.assertTrue([f.key for f in findings(text, 'HC-P009')])

    def test_field_written_elsewhere_with_the_io_class_still_flags(self):
        text = (self.TEXT % ('ref Job m_Job = new QuietJob;', 'm_Job')).replace(
            'void Run()', 'void Swap() { m_Job = new FileJob; }\n    void Run()')
        self.assertTrue([f.key for f in findings(text, 'HC-P009')])

    def test_field_assigned_from_a_call_that_returns_new(self):
        text = (self.TEXT % ('ref Job m_Job;', 'm_Job')).replace(
            'void Run()', 'Job Make() { return new QuietJob; }\n    void Init() { m_Job = Make(); }\n    void Run()')
        self.assertEqual([f.key for f in findings(text, 'HC-P009')], [])
        loose = text.replace('return new QuietJob;', 'if (m_Flag) { return new FileJob; } return new QuietJob;')
        self.assertTrue([f.key for f in findings(loose, 'HC-P009')])

    def test_qualified_field_chain(self):
        other = (self.TEXT % ('ref Job m_Job = new QuietJob;', 'm_Box.m_Inner')).replace(
            'class Holder', 'class Box { ref Job m_Inner = new QuietJob; }\nclass Holder').replace(
            'void Run()', 'ref Box m_Box = new Box;\n    void Run()')
        self.assertEqual([f.key for f in findings(other, 'HC-P009')], [])
        wrote = other.replace('class M\n', 'class Writer { void Put(Box b) { b.m_Inner = new FileJob; } }\nclass M\n')
        self.assertTrue([f.key for f in findings(wrote, 'HC-P009')])

    def test_same_named_field_of_another_class_is_not_a_write(self):
        text = (self.TEXT % ('ref Job m_Job = new QuietJob;', 'm_Job')).replace(
            'class M\n', 'class Elsewhere { ref Job m_Job; void Put() { m_Job = new FileJob; } }\nclass M\n')
        self.assertEqual([f.key for f in findings(text, 'HC-P009')], [])

class PairedReadTests(unittest.TestCase):
    """OpenFile plus the first bounded ReadFile on that local handle is one file visit."""
    TEXT = '''
class Job
{
    int m_Cursor;
    ref array<string> m_Rows;
    string Load(string path)
    {
        %s
    }
    void HCStep() { m_Cursor++; Load("$profile:a"); }
}
'''

    def keys(self, body):
        return [f.key for f in findings(self.TEXT % body, 'HC-P003')]

    def test_open_then_bounded_read_of_one_handle_is_one_stage(self):
        body = 'FileHandle h = OpenFile(path, FileMode.READ); string c; ReadFile(h, c, 1024); CloseFile(h); return c;'
        self.assertEqual([], self.keys(body))

    def test_second_read_of_the_handle_is_counted(self):
        body = ('FileHandle h = OpenFile(path, FileMode.READ); string c; ReadFile(h, c, 1024); ReadFile(h, c, 1024); '
                'CloseFile(h); return c;')
        self.assertEqual(['OpenFile#1', 'ReadFile#1', 'ReadFile#2'], self.keys(body))

    def test_read_of_a_handle_opened_outside_the_loop_is_counted(self):
        body = ('FileHandle h = OpenFile(path, FileMode.READ); string c; '
                'for (int i = 0; i < m_Rows.Count(); i++) { ReadFile(h, c, 1024); } CloseFile(h); return c;')
        self.assertEqual(['OpenFile#1', 'ReadFile#1'], self.keys(body))

    def test_unbounded_read_is_not_paired(self):
        body = 'FileHandle h = OpenFile(path, FileMode.READ); string c; ReadFile(h, c, m_Cursor); CloseFile(h); return c;'
        self.assertEqual(['OpenFile#1', 'ReadFile#1'], self.keys(body))

    def test_read_of_a_field_handle_is_not_paired(self):
        text = self.TEXT.replace('int m_Cursor;', 'int m_Cursor; FileHandle h;')
        body = 'h = OpenFile(path, FileMode.READ); string c; ReadFile(h, c, 1024); return c;'
        self.assertEqual(['OpenFile#1', 'ReadFile#1'], [f.key for f in findings(text % body, 'HC-P003')])


class ParameterStateStepTests(unittest.TestCase):
    """A static step that advances a field of its class-typed job parameter is a stage."""
    TEXT = '''
class JobState { int Phase; }
class Reader
{
    static void Read() { FileExist("$profile:a"); }
    static void HCStep(JobState job, int count) { %s Read(); }
}
'''

    def keys(self, body):
        return [f.key for f in findings(self.TEXT % body, 'HC-P003')]

    def test_field_write_through_the_job_parameter_is_a_stage(self):
        self.assertEqual([], self.keys('job.Phase = 2;'))
        self.assertEqual([], self.keys('job.Phase++;'))

    def test_step_without_a_state_write_stays_flagged(self):
        self.assertEqual(['FileExist#1'], self.keys(''))

    def test_write_to_an_undeclared_member_stays_flagged(self):
        self.assertEqual(['FileExist#1'], self.keys('job.Missing = 2;'))

    def test_assignment_to_a_primitive_parameter_stays_flagged(self):
        self.assertEqual(['FileExist#1'], self.keys('count = 2;'))


class BudgetLoopTests(unittest.TestCase):
    """File work inside a loop an HCWorkBudget bounds is the budget's slice, not an unbounded drain."""
    TEXT = '''
class HCWorkBudget { void HCReset(int limit, float ms = 4) {} bool HCContinue() { return true; } }
class Gauge { bool HCContinue() { return true; } }
class Unit
{
    bool Step(HCWorkBudget budget) { %s return true; }
}
class Pump
{
    ref HCWorkBudget m_Work = new HCWorkBudget;
    ref Gauge m_Gauge = new Gauge;
    ref Unit m_Unit = new Unit;
    ref array<string> m_Rows;
    int m_Skips;
    void Read() { FileExist("$profile:a"); }
    void HCStep() { m_Work.HCReset(4, 2); %s }
}
'''

    def keys(self, loop, gate='if (!budget.HCContinue()) { return false; } FileExist("$profile:b");'):
        return [f.key for f in findings(self.TEXT % (gate, loop), 'HC-P003')]

    def test_loop_headed_by_the_budget_is_bounded(self):
        self.assertEqual([], self.keys('while (m_Work.HCContinue()) { Read(); }', 'FileExist("$profile:b");'))
        self.assertEqual([], self.keys('while (m_Skips < 9 && m_Work.HCContinue()) { Read(); FileExist("$profile:c"); }'))

    def test_first_statement_guard_that_returns_bounds_the_loop(self):
        self.assertEqual([], self.keys('for (int i = 0; i < m_Rows.Count(); i++) { if (!m_Work.HCContinue()) { return; } Read(); }'))

    def test_guard_that_falls_through_does_not_bound_the_loop(self):
        self.assertEqual(['FileExist#1'], self.keys(
            'for (int i = 0; i < m_Rows.Count(); i++) { if (!m_Work.HCContinue()) { m_Skips++; } Read(); }'))

    def test_loop_without_a_budget_stays_flagged(self):
        self.assertEqual(['FileExist#1'], self.keys('for (int i = 0; i < m_Rows.Count(); i++) { Read(); }'))

    def test_receiver_that_is_not_a_work_budget_stays_flagged(self):
        self.assertEqual(['FileExist#1'], self.keys('while (m_Gauge.HCContinue()) { Read(); }'))

    def test_negated_head_is_not_a_budget_loop(self):
        self.assertEqual(['FileExist#1'], self.keys('while (!m_Work.HCContinue()) { Read(); }'))

    def test_callee_that_gates_the_budget_before_file_work_bounds_the_loop(self):
        self.assertEqual([], self.keys('for (int i = 0; i < 8; i++) { m_Unit.Step(m_Work); }'))

    def test_callee_with_file_work_before_the_gate_stays_flagged(self):
        late = 'FileExist("$profile:b"); if (!budget.HCContinue()) { return false; }'
        self.assertIn('FileExist#1', self.keys('for (int i = 0; i < 8; i++) { m_Unit.Step(m_Work); }', late))

    def test_callee_that_never_tests_the_budget_stays_flagged(self):
        self.assertIn('FileExist#1', self.keys('for (int i = 0; i < 8; i++) { m_Unit.Step(m_Work); }', 'FileExist("$profile:b");'))

    def test_budget_not_handed_to_the_callee_stays_flagged(self):
        self.assertIn('FileExist#1', self.keys('for (int i = 0; i < 8; i++) { m_Unit.Step(null); }'))

    def test_work_outside_the_budget_loop_stays_flagged(self):
        self.assertEqual(['FileExist#1'], self.keys('while (m_Work.HCContinue()) { Read(); } FileExist("$profile:z");'))


class SlowPollTests(unittest.TestCase):
    """A repeating CallLater at a constant slow interval with a few finite file operations is no tick root."""
    TEXT = '''
class HCProbe
{
    ref array<string> m_Rows;
    void Start() { %s }
    void Other() { %s }
    void Work() { FileExist("$profile:a"); %s }
}
'''
    SLOW = 'GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Work, 30000, true);'

    def keys(self, schedule, other='', body=''):
        return [f.key for f in findings(self.TEXT % (schedule, other, body), 'HC-P003')]

    def test_slow_constant_poll_is_not_a_root(self):
        self.assertEqual([], self.keys(self.SLOW))
        self.assertEqual([], self.keys('GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLaterByName(this, "Work", 30000, true);'))
        self.assertEqual([], self.keys(f'GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Work, {perf.SLOW_POLL_MS}, true);'))

    def test_fast_poll_stays_a_root(self):
        fast = f'GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Work, {perf.SLOW_POLL_MS - 1}, true);'
        self.assertEqual(['FileExist#1'], self.keys(fast))

    def test_non_constant_interval_stays_a_root(self):
        self.assertEqual(['FileExist#1'], self.keys('GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Work, m_Rows.Count(), true);'))

    def test_any_fast_scheduling_keeps_the_root(self):
        fast = 'GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Work, 50, true);'
        self.assertEqual(['FileExist#1'], self.keys(self.SLOW, fast))

    def test_slow_poll_with_unbounded_file_work_stays_a_root(self):
        looped = 'for (int i = 0; i < m_Rows.Count(); i++) { FileExist("$profile:b"); }'
        self.assertIn('FileExist#2', self.keys(self.SLOW, '', looped))

    def test_slow_poll_with_more_operations_than_the_cap_stays_a_root(self):
        many = 'FileExist("$profile:b"); ' * perf.SLOW_POLL_OPS
        self.assertIn('FileExist#1', self.keys(self.SLOW, '', many))
