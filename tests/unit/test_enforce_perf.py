"""Precision cases for tools/validate/enforce_perf.py (offline lint tooling only).

Each case feeds a small synthetic Enforce source to check(); nothing here
establishes DayZ behaviour. Every precision rule has a clearing case and a
neighbouring case that must keep flagging.
"""
from pathlib import Path
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


if __name__ == '__main__':
    unittest.main()
