"""Focused HC-E058 fixtures. Static checks do not establish DayZ behaviour."""
import unittest

from tools.validate import enforce_lint as lint
from tools.validate import enforce_source as es

PATH = 'mods/HollowCountry/scripts/4_World/Fixture.c'


class UseAfterRemoveRule(unittest.TestCase):
    def findings(self, body, fields='ref array<ref Row> Rows;', params='', extra='', row='class Row { int Id; Row Next; }'):
        source = row + extra + f'class Holder {{ {fields} void Run({params}) {{ {body} }} }}'
        return lint.lint_texts({PATH: source}, rules=(lint.rule_use_after_remove,))

    def test_registered(self):
        self.assertIn('HC-E058', lint.RULES)
        self.assertIn(lint.rule_use_after_remove, lint.ALL_RULES)

    def test_array_reads_writes_and_passes(self):
        for get in ('Rows[0]', 'Rows.Get(0)'):
            for mutation in ('Rows.Remove(0)', 'Rows.RemoveOrdered(0)', 'Rows.RemoveItem(row)', 'Rows.Clear()', 'Rows.Set(0, new Row)'):
                for use in ('row.Id = 2;', 'int value = row.Id;', 'Use(row);', 'return row.Id;'):
                    with self.subTest(get=get, mutation=mutation, use=use):
                        found = self.findings(f'Row row = {get}; {mutation}; {use}')
                        self.assertEqual(['HC-E058'], [f.rule for f in found])

    def test_map_get_index_and_find_output(self):
        for bind in ('Row row = Rows.Get(key);', 'Row row = Rows[key];', 'Row row; Rows.Find(key, row);', 'Row row; if (!Rows.Find(key, row)) return;'):
            for mutation in ('Rows.Remove(key);', 'Rows.Set(key, new Row);', 'Rows.Clear();'):
                with self.subTest(bind=bind, mutation=mutation):
                    self.assertEqual(1, len(self.findings(bind + mutation + 'Use(row.Id);',
                        fields='ref map<string, ref Row> Rows;', params='string key')))

    def test_foreach(self):
        self.assertEqual(1, len(self.findings('foreach (Row row : Rows) { Rows.RemoveItem(row); Use(row); }')))
        self.assertEqual([], self.findings('foreach (Row row : Rows) { if (row.Id == 0) { Rows.RemoveItem(row); continue; } Use(row.Id); }'))

    def test_ref_and_autoptr_are_safe(self):
        for modifier in ('ref', 'autoptr'):
            self.assertEqual([], self.findings(f'{modifier} Row row = Rows[0]; Rows.Clear(); Use(row.Id);'))

    def test_managed_and_inherited_managed_are_excluded(self):
        for row in ('class Row : Managed { int Id; }', 'class Base : Managed {} class Row : Base { int Id; }',
                    'class Row : Object { int Id; }', 'class Row : Widget { int Id; }',
                    'class Row : PlayerIdentity { int Id; }', 'class Row : Unknown { int Id; }'):
            self.assertEqual([], self.findings('Row row = Rows[0]; Rows.Clear(); Use(row.Id);', row=row))

    def test_native_managed_ancestry(self):
        source = es.Source(PATH, 'class Row : NativeBase { int Id; } class Holder { ref array<ref Row> Rows; void Run() { Row row = Rows[0]; Rows.Clear(); Use(row.Id); } }')
        symbols = {'classes': {'NativeBase': [{'modded': False, 'parent': 'Managed', 'layer': 2, 'fields': {}, 'methods': {}}]}}
        self.assertEqual([], lint.lint([source], symbols=symbols, rules=(lint.rule_use_after_remove,)))

    def test_nonowning_containers_and_primitive_values(self):
        for fields in ('ref array<Row> Rows;', 'ref map<int, Row> Rows;'):
            self.assertEqual([], self.findings('Row row = Rows[0]; Rows.Clear(); Use(row.Id);', fields=fields))
        self.assertEqual([], self.findings('int row = Rows[0]; Rows.Clear(); Use(row);', fields='ref array<int> Rows;'))

    def test_return_continue_and_break_before_use(self):
        for jump in ('return', 'continue', 'break'):
            self.assertEqual([], self.findings(f'while (true) {{ Row row = Rows[0]; if (row.Id < 1) {{ Rows.RemoveOrdered(0); {jump}; }} Use(row.Id); }}'))

    def test_break_and_continue_do_not_hide_use_after_loop(self):
        for jump in ('break', 'continue'):
            self.assertEqual(1, len(self.findings(f'Row row = Rows[0]; for (int i = 0; i < 1; i++) {{ Rows.Clear(); {jump}; }} Use(row.Id);')))

    def test_opposite_if_else_arms(self):
        for body in ('if (row.Id < 1) { Rows.Clear(); } else { Use(row.Id); }',
                     'if (row.Id < 1) Rows.Clear(); else if (row.Id > 1) Use(row.Id);'):
            self.assertEqual([], self.findings('Row row = Rows[0];' + body))

    def test_if_arm_joins_are_checked(self):
        self.assertEqual(1, len(self.findings('Row row = Rows[0]; if (row.Id < 1) Rows.Clear(); Use(row.Id);')))
        self.assertEqual(1, len(self.findings('Row row = Rows[0]; Rows.Clear(); if (stop) return; Use(row.Id);', params='bool stop')))

    def test_mutually_exclusive_pressure_guard(self):
        body = 'Row row = Rows[index]; if (!pressure && row.Id < 1) { Rows.Remove(index); changed = true; } if (pressure && row.Id <= oldest) { oldest = row.Id; }'
        self.assertEqual([], self.findings(body, params='bool pressure, int index, int oldest'))

    def test_reassign_kills_but_rhs_is_checked_first(self):
        self.assertEqual([], self.findings('Row row = Rows[0]; Rows.Clear(); row = null; Use(row.Id);'))
        self.assertEqual(1, len(self.findings('Row row = Rows[0]; Rows.Clear(); row = row.Next;')))

    def test_same_container_and_literal_slot_precision(self):
        for mutation in ('Other.Clear();', 'Rows.Set(1, new Row);', 'Rows.RemoveOrdered(1);', 'Rows.Set(0, row);', 'Rows.Insert(new Row);'):
            self.assertEqual([], self.findings('Row row = Rows[0];' + mutation + 'Use(row.Id);', fields='ref array<ref Row> Rows; ref array<ref Row> Other;'))

    def test_strong_local_owner_and_its_release(self):
        for suffix, count in (('Use(row.Id);', 0), ('hold = null; Use(row.Id);', 1)):
            self.assertEqual(count, len(self.findings('Row row = Rows[0]; ref Row hold = row; Rows.Clear();' + suffix)))

    def test_strong_member_owner(self):
        for suffix, count in (('Use(row.Id);', 0), ('Hold = null; Use(row.Id);', 1)):
            self.assertEqual(count, len(self.findings('Row row = Rows[0]; Hold = row; Rows.Clear();' + suffix,
                                                    fields='ref array<ref Row> Rows; ref Row Hold;')))
        self.assertEqual([], self.findings('Row row = Hold; int index = Rows.Find(row); Rows.Remove(index); Use(row.Id);', fields='ref array<ref Row> Rows; ref Row Hold;'))

    def test_swap_remove_safe_only_when_retained_slot_differs(self):
        prefix = 'Row tail = Rows[last]; Rows[index] = tail; Rows.Remove(last);'
        self.assertEqual([], self.findings(prefix + 'if (index != last) Use(tail.Id);', params='int index, int last'))
        self.assertEqual(1, len(self.findings(prefix + 'Use(tail.Id);', params='int index, int last')))
        self.assertEqual(1, len(self.findings('Row tail = Rows[last]; Rows.Remove(last); Use(tail.Id);', params='int last')))

    def test_transferred_slot_cleared_before_use(self):
        self.assertEqual(1, len(self.findings('Row tail = Rows[last]; Rows[index] = tail; Rows.Remove(last); Rows.Clear(); if (index != last) Use(tail.Id);', params='int index, int last')))

    def test_registry_retains_secondary_list_entries(self):
        extra = '''class Registry {
            ref array<ref Row> Entries;
            array<ref Row> GetRows() { return Entries; }
        }'''
        fields = '''ref Registry RegistryOwner;
            ref array<ref Row> Rows;
            void Start() {
                array<ref Row> entries = RegistryOwner.GetRows();
                foreach (Row row : entries) { Rows.Insert(row); }
            }'''
        self.assertEqual([], self.findings('Row row = Rows[0]; Rows.Remove(0); Use(row.Id);', fields=fields, extra=extra))
        # Mixing fresh sole-owned entries into the list defeats that proof.
        self.assertEqual(1, len(self.findings('Row row = Rows[0]; Rows.Remove(0); Use(row.Id);', fields=fields + 'void Add() { Rows.Insert(new Row); }', extra=extra)))

    def test_template_catalog_retains_deferred_rows(self):
        extra = '''class Catalog {
            static ref array<ref Row> Entries;
            static array<ref Row> GetRows() { if (!Entries) return null; return Entries; }
        }'''
        fields = '''ref array<ref Row> Rows;
            void Queue() {
                array<ref Row> entries = Catalog.GetRows();
                Row row = entries[0];
                Rows.Insert(row);
            }'''
        self.assertEqual([], self.findings('Row row = Rows[0]; Rows.Clear(); Use(row.Id);', fields=fields, extra=extra))

    def test_remove_find_parameter_and_index_local(self):
        for mutation in ('Rows.Remove(Rows.Find(row));', 'int index = Rows.Find(row); Rows.Remove(index);', 'Rows.RemoveItem(row);'):
            self.assertEqual(1, len(self.findings(mutation + 'row.Id = 2;', params='Row row')))

    def test_disconnected_pre_fix_text(self):
        # Verbatim pre-fix method; only unrelated declarations are stubbed.
        source = '''class HCGroupPeer { string Id; PlayerIdentity Identity; PlayerBase Player; }
        class HCGroupService {
            ref array<ref HCGroupPeer> m_Peers;
            HCGroupPeer Peer(string uid) {
                foreach (HCGroupPeer peer : m_Peers) {
                    if (peer.Id == uid) return peer;
                }
                return null;
            }
            void Disconnected(PlayerIdentity identity)
            {
                if (!identity) return;
                HCGroupPeer peer = Peer(identity.GetId());
                // A cleared weak identity still belongs to this id-keyed disconnect cleanup.
                if (!peer || (peer.Identity && !HCPlayerIdentity.Same(peer.Identity, identity))) return;
                // Persist batched discovery while the leaving explorer is still live.
                if (m_Healthy && FlushBatch() == HCGroupCode.STORAGE) { Stop(); return; }
                m_Peers.Remove(m_Peers.Find(peer));
                HCGroupRules.DropInvites(m_State, 0, peer.Id);
                peer.Identity = null;
                peer.Player = null;
                Broadcast();
            }
        }'''
        found = lint.lint_texts({PATH: source}, rules=(lint.rule_use_after_remove,))
        self.assertEqual(1, len(found))
        self.assertEqual('HCGroupService.Disconnected', found[0].symbol)
        fixed = source.replace('HCGroupPeer peer = Peer(identity.GetId());', 'ref HCGroupPeer peer = Peer(identity.GetId());')
        self.assertEqual([], lint.lint_texts({PATH: fixed}, rules=(lint.rule_use_after_remove,)))

    def test_cache_seed_revert_pre_fix_text(self):
        source = '''class HCXAICacheRow { string SiteId; }
        class HCXAICacheRowMemo : Managed {}
        class Cache { ref array<ref HCXAICacheRow> Rows; }
        class HCXAISiteStorage {
            ref Cache m_Caches;
            ref map<string, HCXAICacheRow> m_CacheRows;
            protected void HCCacheSeedRevert(HCXAICacheRow row, HCXAICacheRowMemo memo, bool added)
            {
                if (added)
                {
                    m_Caches.Rows.RemoveItem(row);
                    if (m_CacheRows.Contains(row.SiteId)) { m_CacheRows.Remove(row.SiteId); }
                    return;
                }
                memo.Restore(row);
            }
        }'''
        found = lint.lint_texts({PATH: source}, rules=(lint.rule_use_after_remove,))
        self.assertEqual(1, len(found))
        self.assertEqual('HCXAISiteStorage.HCCacheSeedRevert', found[0].symbol)
        fixed = source.replace('m_Caches.Rows.RemoveItem(row);', 'string siteId = row.SiteId; m_Caches.Rows.RemoveItem(row);').replace('m_CacheRows.Contains(row.SiteId)', 'm_CacheRows.Contains(siteId)').replace('m_CacheRows.Remove(row.SiteId)', 'm_CacheRows.Remove(siteId)')
        self.assertEqual([], lint.lint_texts({PATH: fixed}, rules=(lint.rule_use_after_remove,)))

    def test_comments_strings_and_lookalikes(self):
        self.assertEqual([], self.findings('Row row = Rows[0]; // Rows.Clear();\n string text = "Rows.Clear(); row.Id"; Other.Clear(); Use(row.Id);'))

    def test_diagnostic_location(self):
        found = self.findings('Row row = Rows[0];\nRows.Clear();\nrow.Id = 2;')
        self.assertEqual(3, found[0].line)
        self.assertEqual('Holder.Run', found[0].symbol)


if __name__ == '__main__':
    unittest.main()
