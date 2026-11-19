"""Wave 9 #190: loot map job finishability arithmetic, bounded sub-cell queries and
client wiring (`lootmap <filter>`, derived wait, reply-mark handling).

Explicit synthetic native values only; the authored handlers run through the
restricted statement adapter. Offline arithmetic never establishes DayZ cost or
behaviour: the 1 km/500 m query cost stays unmeasured.

RED (before the change): PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_admin_lootmap_wiring -v
AssertionError: Missing authored method HCAdminLootMap.HCJobTickCap in HCAdminLootMap.c
"""
import math
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch

from tests.unit.test_admin_test_kit import compile_authored, base_scope
from tests.unit.test_group_server import EArray
from tests.unit.test_map_layers import EStr

ROOT = Path(__file__).resolve().parents[2]
LOOT = ROOT / 'mods/HollowCountry/scripts/4_World/Admin/HCAdminLootMap.c'
CLIENT = ROOT / 'mods/HollowCountry/scripts/5_Mission/Admin/HCAdminClient.c'
WIRE = ROOT / 'mods/HollowCountry/scripts/3_Game/Admin/HCAdminWire.c'
CHERNARUS_M = 15360  # explicit synthetic world edge (GetWorldSize), not read from DayZ


def authored_limits():
    """Parse the authored defaults so the arithmetic cannot drift from the source."""
    text = LOOT.read_text()
    block = text[text.index('class HCAdminLootMapLimits'):text.index('class HCAdminLootType')]
    return N(**{name: int(value) for name, value in re.findall(r'(?m)^    int (\w+) = (\d+);', block)})


class Arr(EArray):
    def Clear(self): self.clear()
    def RemoveOrdered(self, index): del self[index]


def statics(names, limits):
    env = base_scope(HCAdminLootMapLimits=lambda: limits)
    env['Math'].Ceil = math.ceil
    holder = N()
    env['HCAdminLootMap'] = holder
    # The statement adapter floors every '/'; Enforce float division is exact, so the
    # one float division (world edge / sub-cell) goes through an explicit true divide.
    env['HCDivide'] = lambda a, b: a / b
    source = LOOT.read_text().replace('worldSize / subCellM', 'HCDivide(worldSize, subCellM)')
    for name in names:
        with patch.object(Path, 'read_text', return_value=source):
            fn = compile_authored(LOOT, 'HCAdminLootMap', name, env, modded=False, native_strings=EStr)
        setattr(holder, name, lambda *args, fn=fn: fn(holder, *args))
    return holder


class JobArithmetic(unittest.TestCase):
    def test_old_budget_could_not_finish_and_derived_cap_can(self):
        limits = authored_limits()
        # Former design (b1fae85): 1 km cells, 32 rows per 1 s tick, 300 s wall clock.
        old_cells, old_rows, old_cap_s = math.ceil(CHERNARUS_M / 1000) ** 2, 32, 300
        old_min_ticks = old_cells + math.ceil(limits.MaxItemsScanned / old_rows)
        self.assertEqual(256, old_cells)
        self.assertGreater(old_min_ticks, old_cap_s)  # 2304 ticks > 300 s: unfinishable

        lootmap = statics(('HCJobTickCap', 'HCCellsAcross'), limits)
        across = lootmap.HCCellsAcross(CHERNARUS_M, limits.SubCellM)
        cells = across * across
        self.assertEqual((31, 961), (across, cells))
        self.assertLessEqual(cells, limits.MaxCells)
        cap = lootmap.HCJobTickCap(limits, cells)
        units = limits.MaxItemsScanned + (limits.MatchRowUnits - 1) * limits.MaxMatches
        self.assertEqual(cells + math.ceil(units / limits.MaxRowsPerStep) + 1, cap)
        self.assertEqual(1314, cap)
        # Every row mismatching (the prefilter case) and every row matching both fit.
        self.assertLessEqual(cells + math.ceil(limits.MaxItemsScanned / limits.MaxRowsPerStep), cap)
        # A per-cell object cap refusal needs 4096 rows in ONE 500 m cell; the former
        # 1 km query covered four times the area per native call.
        self.assertEqual(4, (1000 // limits.SubCellM) ** 2)
        self.assertEqual(16, math.ceil(limits.MaxObjectsPerCell / limits.MaxRowsPerStep))

    def test_prefilter_charges_match_rows_more_than_rejected_rows(self):
        limits = authored_limits()
        self.assertGreaterEqual(limits.MatchRowUnits, 2)
        self.assertGreater(limits.MaxRowsPerStep, 32)  # raised from the former 32 rows

    def test_client_wait_is_derived_from_the_job_not_ten_seconds(self):
        limits = authored_limits()
        lootmap = statics(('HCJobTickCap', 'HCClientWaitSeconds'), limits)
        ticks = lootmap.HCJobTickCap(limits, limits.MaxCells)
        expected = math.ceil(ticks * limits.MaxTickIntervalMs / 1000) + limits.ReplyGraceSeconds
        self.assertEqual(expected, lootmap.HCClientWaitSeconds())
        self.assertGreater(lootmap.HCClientWaitSeconds(), 10)
        # The largest admitted job (961 cells) is covered by the wait.
        self.assertGreaterEqual(lootmap.HCClientWaitSeconds(), 1314 * limits.MaxTickIntervalMs / 1000)

    def test_reply_grace_and_no_seen_list_or_wall_clock_cap(self):
        text = LOOT.read_text()
        self.assertIn('ReplyGraceSeconds', text.split('class HCAdminLootMapLimits')[1].split('class HCAdminLootType')[0])
        body = text.split('static int HCClientWaitSeconds')[1].split('int HCTotalCells')[0]
        self.assertIn('ReplyGraceSeconds', body)
        self.assertNotIn('MaxJobSeconds', text)
        self.assertNotIn('m_Seen', text)
        self.assertNotIn('QueryRadiusM', text)


class ClientWiring(unittest.TestCase):
    def build(self):
        limits = authored_limits()
        self.now = 100.0
        sent = self.sent = []
        self.feedback = []
        self.printed = []
        self.logged = []
        game = N(GetTickTime=lambda: self.now, GetPlayer=lambda: self.player, IsServer=lambda: False)
        self.player = N(IsAlive=lambda: True, IsUnconscious=lambda: False)
        wire = N(REQUEST=1, REPLY=2)
        wire.HCIsLootMap = compile_authored(WIRE, 'HCAdminWire', 'HCIsLootMap',
                                            base_scope(), modded=False, native_strings=EStr)
        wire_static = N(REQUEST=1, REPLY=2, HCIsLootMap=lambda command: wire.HCIsLootMap(wire, command))
        loot = N(HCClientWaitSeconds=lambda: 1344,
                 HCValidFilter=lambda name: bool(re.fullmatch(r'[A-Za-z0-9_]{1,96}', name)))
        self.env = base_scope(GetGame=lambda: game, HCAdminWire=wire_static, HCAdminLootMap=loot,
                         HCAdminLootMapLimits=lambda: limits,
                         HCAdminRequest=lambda: N(Ticket=0, Command='', Value=0),
                         ScriptRPC=lambda: N(Write=lambda request: sent.append(request),
                                             Send=lambda *args: None),
                         PlayerBase=N(Cast=lambda player: player),
                         DayZGame=N(Event_OnRPC=N(Remove=lambda fn: None)), HCReceive=lambda *args: None,
                         HCAdminReply=lambda: N(Marks=Arr(), Lines=Arr(), Authorized=False),
                         Print=lambda line: self.printed.append(line),
                         HCDebugSnapshot=N(HCPositionValid=lambda pos: True))
        c = self.client = N(m_Listening=True, m_Authorized=True, m_Player=self.player, m_Pending=False,
                            m_Ticket=0, m_Expected=0, m_SnapshotTicket=0, m_LootTicket=0, m_NextSend=0.0,
                            m_LastReply=100.0, m_RequestUntil=0.0, m_Command='', m_SnapshotUntil=0.0,
                            m_LootUntil=0.0, m_LootViewUntil=0.0, m_OpenRequested=False,
                            m_Checks=Arr(), Revision=0, Notice='', View=None, Hidden=Arr(),
                            Changed=N(Invoke=lambda: None))
        self.members = ('HCValid', 'HCSend', 'HCFeedback', 'HCMergeLootMap', 'HCCarryLootMarks',
                        'HCExpireMarks', 'HCExpireLoot', 'HCLog', 'HCLogReply', 'HCStop')
        self.fields = ('m_Ticket', 'm_Expected', 'm_Pending', 'm_RequestUntil', 'm_Command', 'm_NextSend',
                       'm_LootTicket', 'm_LootUntil', 'm_LootViewUntil', 'm_SnapshotTicket', 'm_Player',
                       'm_Authorized', 'm_SnapshotUntil', 'm_Listening', 'm_OpenRequested', 'm_LastReply',
                       'Revision', 'Notice', 'View', 'Changed', 'Hidden')
        for name in ('HCValid', 'HCSend', 'HCLootMap', 'HCMergeLootMap', 'HCCarryLootMarks',
                     'HCExpireMarks', 'HCExpireLoot', 'HCStop'):
            fn = compile_authored(CLIENT, 'HCAdminClient', name, self.env, self.members, modded=False,
                                  native_strings=EStr, fields=self.fields)
            setattr(c, name, lambda *args, fn=fn: fn(c, *args))
        raw_send = c.HCSend  # the adapter has no default parameters: HCSend(command, value = 0)
        c.HCSend = lambda command, value=0: raw_send(command, value)
        c.HCFeedback = lambda text: self.feedback.append(text)
        c.HCLog = lambda command, ok, text: self.logged.append((command, ok, text))
        c.HCLogReply = lambda reply, command: None
        return c

    def test_wait_helper_is_gone_and_only_the_ack_has_the_short_timeout(self):
        self.assertNotIn('HCWaitSeconds', CLIENT.read_text())
        c = self.build()
        for bad in ('', '*', '../x', 'a b', 'x' * 97):
            self.assertFalse(c.HCLootMap(EStr(bad)))
        self.assertEqual([], self.sent)
        self.assertEqual(5, len(self.feedback))
        self.assertTrue(c.HCLootMap(EStr('Bandage*')))
        self.assertEqual('lootmap Bandage*', self.sent[0].Command)
        self.assertEqual(110.0, c.m_RequestUntil)  # the ordinary 10 s: ack only, not the job
        self.assertEqual(0, c.m_LootTicket)  # tracked only once the server acknowledged
        # 96-char prefix + '*' would exceed the 104-character wire command.
        self.now = 200.0
        c.m_Pending = False
        c.m_NextSend = 0.0
        self.assertFalse(c.HCLootMap(EStr('x' * 96 + '*')))

    def receive(self, c, reply, extra=()):
        source = CLIENT.read_text().replace('HCAdminReply reply;', 'HCAdminReply reply = ctx;').replace('ctx.Read(reply)', 'true')
        with patch.object(Path, 'read_text', return_value=source):
            fn = compile_authored(CLIENT, 'HCAdminClient', 'HCReceive', self.env, self.members, modded=False,
                                  native_strings=EStr, fields=self.fields)
        fn(c, None, None, 2, reply)

    def reply(self, ticket, snapshot=False, notice='[HC Admin] cmd=lootmap result=ok reason=started', marks=1):
        mark = lambda i: N(Layer=EStr('lootmap'), Position=(1, 0, 1), Label=EStr('a%d' % i), Detail=EStr('b'))
        return N(Ticket=ticket, Authorized=True, Snapshot=snapshot, Notice=EStr(notice),
                 Lines=Arr(), Marks=Arr([mark(i) for i in range(marks)]))

    def test_ack_frees_the_client_and_the_final_marks_arrive_later_by_ticket(self):
        c = self.build()
        self.assertTrue(c.HCLootMap(EStr('Bandage')))
        ticket = self.sent[0].Ticket
        self.assertTrue(c.m_Pending)
        self.now = 101.0
        self.receive(c, self.reply(ticket, marks=0))  # the immediate ack
        self.assertFalse(c.m_Pending)  # menu and other commands work during the job
        self.assertEqual(ticket, c.m_LootTicket)
        self.assertEqual(101.0 + 1344, c.m_LootUntil)
        self.assertEqual([], list(c.View.Marks) if c.View else [])  # no marks yet
        # Another admin command can be sent while the job runs.
        self.now = 110.0
        self.assertTrue(c.HCSend(EStr('status')))
        self.receive(c, self.reply(c.m_Ticket, notice='Status: ok', marks=0))
        self.assertEqual(ticket, c.m_LootTicket)  # still tracked
        # Marks arrive long afterwards, matched by m_LootTicket only.
        self.now = 900.0
        self.receive(c, self.reply(ticket + 50, snapshot=True, marks=2))
        self.assertEqual([], list(c.View.Marks) if c.View else [])
        self.assertTrue(any('late reply ticket=%d' % (ticket + 50) in line for line in self.printed))
        self.receive(c, self.reply(ticket, snapshot=True, marks=2,
                                   notice='[HC Admin] cmd=lootmap result=ok reason='))
        self.assertEqual(['a0', 'a1'], [m.Label for m in c.View.Marks])
        self.assertEqual(0, c.m_LootTicket)
        self.assertEqual(900.0 + authored_limits().ViewSeconds, c.m_LootViewUntil)
        self.receive(c, self.reply(ticket, snapshot=True, marks=3))  # one final reply per job
        self.assertEqual(2, len(c.View.Marks))

    def test_refused_lootmap_request_is_not_tracked(self):
        c = self.build()
        c.HCLootMap(EStr('Bandage'))
        self.receive(c, self.reply(self.sent[0].Ticket, notice='[HC Admin] cmd=lootmap result=refused reason=lootmap_job_running', marks=0))
        self.assertEqual(0, c.m_LootTicket)
        self.assertFalse(c.m_Pending)

    def test_session_stays_valid_through_the_derived_job_window_then_stops_cleanly(self):
        c = self.build()
        c.HCLootMap(EStr('Bandage'))
        self.receive(c, self.reply(self.sent[0].Ticket, marks=0))
        self.now = 100.0 + 600  # 10 min, no reply: the 60 s rule alone would have ended it
        self.assertTrue(c.HCValid())
        c.HCExpireLoot(self.now)
        self.assertNotEqual(0, c.m_LootTicket)
        self.now = 101.0 + 1344 + 1  # derived window over, no final reply
        c.HCExpireLoot(self.now)
        self.assertEqual(0, c.m_LootTicket)
        self.assertTrue(any(row[0] == 'lootmap' and not row[1] and 'client-timeout' in row[2] for row in self.logged))
        self.assertFalse(c.HCValid())  # ordinary 60 s rule applies again

    def test_session_drop_logs_the_dropped_job_and_a_late_final_reply_is_ignored(self):
        c = self.build()
        c.HCLootMap(EStr('Bandage'))
        ticket = self.sent[0].Ticket
        self.receive(c, self.reply(ticket, marks=0))
        c.HCStop()
        self.assertEqual(0, c.m_LootTicket)
        self.assertTrue(any('lootmap ticket=%d dropped' % ticket in line for line in self.printed))
        c.m_Listening, c.m_Player = True, self.player  # the admin reopened the session
        self.receive(c, self.reply(ticket, snapshot=True, marks=2))  # server finished anyway
        self.assertIsNone(c.View)  # dropped: no crash, no state
        self.assertTrue(any('late reply ticket=%d' % ticket in line for line in self.printed))

    def test_final_reply_replaces_only_the_lootmap_layer(self):
        c = self.build()
        mark = lambda layer, label: N(Layer=layer, Label=label)
        c.View = N(Marks=Arr([mark('hordes', 'h'), mark('lootmap', 'old')]))
        reply = N(Marks=Arr([mark('lootmap', 'new1'), mark('evil', 'x'), mark('lootmap', 'new2')]))
        c.m_LastReply = 500.0
        c.HCMergeLootMap(reply)
        self.assertEqual([('hordes', 'h'), ('lootmap', 'new1'), ('lootmap', 'new2')],
                         [(m.Layer, m.Label) for m in c.View.Marks])
        self.assertEqual(500.0 + authored_limits().ViewSeconds, c.m_LootViewUntil)
        self.assertEqual(0.0, c.m_SnapshotUntil)  # the snapshot view timer is untouched

    def test_later_snapshot_reply_keeps_the_lootmap_layer_and_expiry_is_per_layer(self):
        c = self.build()
        mark = lambda layer, label: N(Layer=layer, Label=label)
        c.View = N(Marks=Arr([mark('lootmap', 'loot1'), mark('hordes', 'old')]), Lines=Arr())
        fresh = N(Marks=Arr([mark('hordes', 'h1'), mark('camps', 'c1')]))
        c.HCCarryLootMarks(fresh)
        self.assertEqual(['h1', 'c1', 'loot1'], [m.Label for m in fresh.Marks])
        # Whole-view receive: the snapshot path calls the carry before replacing the view.
        self.assertIn('HCCarryLootMarks(reply);', CLIENT.read_text().split('else if (reply.Snapshot)')[1].split('else if (reply.Lines')[0])
        # Expiry: the 60 s snapshot timer drops only snapshot layers, the 300 s timer only loot.
        c.View = N(Marks=Arr([mark('lootmap', 'loot1'), mark('hordes', 'h1')]))
        c.m_SnapshotUntil, c.m_LootViewUntil = 160.0, 400.0
        c.HCExpireMarks(200.0)
        self.assertEqual(['loot1'], [m.Label for m in c.View.Marks])
        self.assertEqual(0.0, c.m_SnapshotUntil)
        c.HCExpireMarks(399.0)
        self.assertEqual(['loot1'], [m.Label for m in c.View.Marks])
        c.HCExpireMarks(400.0)
        self.assertEqual([], list(c.View.Marks))


if __name__ == '__main__':
    unittest.main()
