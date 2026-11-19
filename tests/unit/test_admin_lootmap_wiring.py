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
        wait = [None]
        game = N(GetTickTime=lambda: self.now, GetPlayer=lambda: self.player)
        self.player = N(IsAlive=lambda: True, IsUnconscious=lambda: False)
        wire = N(REQUEST=1)
        wire.HCIsLootMap = compile_authored(WIRE, 'HCAdminWire', 'HCIsLootMap',
                                            base_scope(), modded=False, native_strings=EStr)
        wire_static = N(REQUEST=1, HCIsLootMap=lambda command: wire.HCIsLootMap(wire, command))
        loot = N(HCClientWaitSeconds=lambda: 1344,
                 HCValidFilter=lambda name: bool(re.fullmatch(r'[A-Za-z0-9_]{1,96}', name)))
        env = base_scope(GetGame=lambda: game, HCAdminWire=wire_static, HCAdminLootMap=loot,
                         HCAdminLootMapLimits=lambda: limits,
                         HCAdminRequest=lambda: N(Ticket=0, Command='', Value=0),
                         ScriptRPC=lambda: N(Write=lambda request: sent.append(request),
                                             Send=lambda *args: None),
                         PlayerBase=N(Cast=lambda player: player))
        c = self.client = N(m_Listening=True, m_Authorized=True, m_Player=self.player, m_Pending=False,
                            m_Ticket=0, m_Expected=0, m_SnapshotTicket=0, m_LootTicket=0, m_NextSend=0.0,
                            m_LastReply=100.0, m_RequestUntil=0.0, m_Command='', m_SnapshotUntil=0.0,
                            Revision=0, Notice='', View=None, Hidden=Arr(),
                            Changed=N(Invoke=lambda: None))
        members = ('HCValid', 'HCSend', 'HCWaitSeconds', 'HCFeedback', 'HCMergeLootMap')
        fields = ('m_Ticket', 'm_Expected', 'm_Pending', 'm_RequestUntil', 'm_Command', 'm_NextSend',
                  'm_LootTicket', 'm_SnapshotTicket', 'm_Player', 'm_Authorized', 'm_SnapshotUntil',
                  'Revision', 'Notice', 'View', 'Changed')
        for name in ('HCValid', 'HCWaitSeconds', 'HCSend', 'HCLootMap', 'HCMergeLootMap'):
            fn = compile_authored(CLIENT, 'HCAdminClient', name, env, members, modded=False,
                                  native_strings=EStr, fields=fields)
            setattr(c, name, lambda *args, fn=fn: fn(c, *args))
        raw_send = c.HCSend  # the adapter has no default parameters: HCSend(command, value = 0)
        c.HCSend = lambda command, value=0: raw_send(command, value)
        c.HCFeedback = lambda text: self.feedback.append(text)
        return c

    def test_lootmap_command_validates_then_sends_with_derived_wait(self):
        c = self.build()
        for bad in ('', '*', '../x', 'a b', 'x' * 97):
            self.assertFalse(c.HCLootMap(EStr(bad)))
        self.assertEqual([], self.sent)
        self.assertEqual(5, len(self.feedback))
        self.assertTrue(c.HCLootMap(EStr('Bandage*')))
        self.assertEqual('lootmap Bandage*', self.sent[0].Command)
        self.assertEqual(100.0 + 1344, c.m_RequestUntil)  # derived, not now + 10
        self.assertEqual(self.sent[0].Ticket, c.m_LootTicket)
        # 96-char prefix + '*' would exceed the 104-character wire command.
        self.now = 200.0
        c.m_Pending = False
        c.m_NextSend = 0.0
        self.assertFalse(c.HCLootMap(EStr('x' * 96 + '*')))

    def test_other_commands_keep_ten_seconds_and_session_survives_the_long_wait(self):
        c = self.build()
        self.assertTrue(c.HCSend(EStr('status')))
        self.assertEqual(110.0, c.m_RequestUntil)
        c.m_Pending = False
        self.now = 102.0
        c.m_NextSend = 0.0
        self.assertTrue(c.HCSend(EStr('lootmap Bandage')))
        self.now = 100.0 + 600  # 10 minutes with no reply: >60 s since the last reply
        self.assertTrue(c.HCValid())
        self.now = 102.0 + 1344 + 1
        self.assertFalse(c.HCValid())  # derived wait over: ordinary 60 s rule applies
        c.m_Pending = False
        self.now = 102.0 + 61
        self.assertFalse(c.HCValid())

    def test_final_reply_replaces_only_the_lootmap_layer(self):
        c = self.build()
        mark = lambda layer, label: N(Layer=layer, Label=label)
        c.View = N(Marks=Arr([mark('hordes', 'h'), mark('lootmap', 'old')]))
        reply = N(Marks=Arr([mark('lootmap', 'new1'), mark('evil', 'x'), mark('lootmap', 'new2')]))
        c.m_LastReply = 500.0
        c.HCMergeLootMap(reply)
        self.assertEqual([('hordes', 'h'), ('lootmap', 'new1'), ('lootmap', 'new2')],
                         [(m.Layer, m.Label) for m in c.View.Marks])
        self.assertEqual(500.0 + authored_limits().ViewSeconds, c.m_SnapshotUntil)

    def test_receive_accepts_late_final_lootmap_reply_by_ticket_only(self):
        text = CLIENT.read_text()
        source = text.replace('HCAdminReply reply;', 'HCAdminReply reply = ctx;').replace('ctx.Read(reply)', 'true')
        c = self.build()
        limits = authored_limits()
        merged, logged = [], []
        game = N(GetTickTime=lambda: self.now, GetPlayer=lambda: self.player, IsServer=lambda: False)
        env = base_scope(GetGame=lambda: game, HCAdminWire=N(REPLY=2),
                         HCDebugSnapshot=N(HCPositionValid=lambda pos: True))
        with patch.object(Path, 'read_text', return_value=source):
            receive = compile_authored(CLIENT, 'HCAdminClient', 'HCReceive', env,
                                       ('HCStop', 'HCLogReply', 'HCMergeLootMap'), modded=False,
                                       native_strings=EStr, fields=('m_Pending', 'm_Expected', 'm_Authorized',
                                       'm_LastReply', 'm_LootTicket', 'm_SnapshotTicket', 'm_SnapshotUntil',
                                       'Notice', 'View', 'Revision', 'Changed'))
        c.HCStop = lambda: logged.append('stop')
        c.HCLogReply = lambda reply, command: logged.append(command)
        c.HCMergeLootMap = lambda reply: merged.append(reply.Ticket)
        c.m_Listening = True
        c.m_Pending = False  # the client already timed out the request
        c.m_Expected = 0
        c.m_LootTicket = 9

        def reply(ticket, snapshot=True):
            return N(Ticket=ticket, Authorized=True, Snapshot=snapshot, Notice=EStr('ok'),
                     Lines=Arr(), Marks=Arr([N(Layer=EStr('lootmap'), Position=(1, 0, 1),
                                               Label=EStr('a'), Detail=EStr('b'))]))
        receive(c, None, None, 2, reply(8))  # wrong ticket: dropped
        self.assertEqual([], merged)
        receive(c, None, None, 2, reply(9))
        self.assertEqual([9], merged)
        self.assertIn('lootmap', logged)
        self.assertEqual(0, c.m_LootTicket)
        receive(c, None, None, 2, reply(9))  # one reply per request
        self.assertEqual([9], merged)


if __name__ == '__main__':
    unittest.main()
