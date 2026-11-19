"""Wave 9 #190: loot map job finishability arithmetic, bounded sub-cell queries and
client wiring (`lootmap <filter>`, derived wait, reply-mark handling).

Explicit synthetic native values only; the authored handlers run through the
restricted statement adapter. Offline arithmetic never establishes DayZ cost or
behaviour: the 1 km/500 m query cost stays unmeasured.

RED (before the change): PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_admin_lootmap_wiring -v
AssertionError: Missing authored method HCAdminLootMap.HCJobTickCap in HCAdminLootMap.c

#191 (wave 10) RED, same command: AssertionError: Missing authored method
HCAdminLootMap.HCClientWindowSeconds in HCAdminLootMap.c (ClientWiring build, FAILED
failures=9, errors=1); the est_ticks window, floor/ceiling and the post-ack export
failure final reply tests are in ClientWiring. The server half of the failure reply is in
test_admin_lootmap (RED: AssertionError: 1 != 2).
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
        # Wave 12: the cap is sized from the GUARANTEED rows per tick (the wall-clock
        # deadline cannot cut a tick below MinRowUnitsPerTick), plus percent headroom.
        floor_units = min(limits.MinRowUnitsPerTick, limits.MaxRowsPerStep)
        row_ticks = math.ceil(units / floor_units)
        row_ticks += row_ticks * limits.TickCapHeadroomPercent // 100
        self.assertEqual(cells + row_ticks + 1, cap)
        self.assertEqual(1842, cap)
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
        # Count bounds on rows per tick: floor (progress guarantee) <= the unit ceiling.
        self.assertGreaterEqual(limits.MinRowUnitsPerTick, 1)
        self.assertLessEqual(limits.MinRowUnitsPerTick, limits.MaxRowsPerStep)
        self.assertGreaterEqual(limits.TickCapHeadroomPercent, 0)

    def test_client_wait_is_derived_from_the_job_not_ten_seconds(self):
        limits = authored_limits()
        lootmap = statics(('HCJobTickCap', 'HCClientWaitSeconds'), limits)
        ticks = lootmap.HCJobTickCap(limits, limits.MaxCells)
        expected = math.ceil(ticks * limits.MaxTickIntervalMs / 1000) + limits.ReplyGraceSeconds
        self.assertEqual(expected, lootmap.HCClientWaitSeconds())
        self.assertGreater(lootmap.HCClientWaitSeconds(), 10)
        # The largest admitted job (961 cells) is covered by the wait.
        self.assertGreaterEqual(lootmap.HCClientWaitSeconds(), 1842 * limits.MaxTickIntervalMs / 1000)

    def test_reply_grace_and_no_seen_list_or_wall_clock_cap(self):
        text = LOOT.read_text()
        self.assertIn('ReplyGraceSeconds', text.split('class HCAdminLootMapLimits')[1].split('class HCAdminLootType')[0])
        body = text.split('static int HCClientWaitSeconds')[1].split('int HCTotalCells')[0]
        self.assertIn('ReplyGraceSeconds', body)
        self.assertNotIn('MaxJobSeconds', text)
        self.assertNotIn('m_Seen', text)
        self.assertNotIn('QueryRadiusM', text)


class ObservedCadence(unittest.TestCase):
    """#194: the ack budget uses a bounded running cadence, not one tick sample."""

    def test_running_value_bounds_one_sample_and_is_named_config(self):
        limits = authored_limits()
        loot = statics(('HCSmoothTickMs',), limits)
        self.assertEqual(1000, loot.HCSmoothTickMs(0, 1000))  # first sample seeds
        self.assertEqual(0, loot.HCSmoothTickMs(0, 0))
        # One 30 s stall after a steady 1 s cadence moves the value by one divisor share only.
        stalled = loot.HCSmoothTickMs(1000, 30000)
        self.assertEqual(1000 + 29000 // limits.ObservedTickDivisor, stalled)
        self.assertLess(stalled, 10000)
        # One 0 ms tick lowers it by one share only.
        self.assertEqual(1000 - 1000 // limits.ObservedTickDivisor, loot.HCSmoothTickMs(1000, 0))
        # A sustained new cadence is converged on.
        value = 1000
        for _ in range(200):
            value = loot.HCSmoothTickMs(value, 2000)
        self.assertLessEqual(abs(value - 2000), limits.ObservedTickDivisor)
        # Pathological samples are clamped.
        self.assertEqual(limits.ObservedTickMaxMs, loot.HCSmoothTickMs(0, 10 ** 9))
        self.assertLessEqual(loot.HCSmoothTickMs(limits.ObservedTickMaxMs, 10 ** 9), limits.ObservedTickMaxMs)
        self.assertEqual(0, loot.HCSmoothTickMs(0, -5))


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
        window = statics(('HCJobTickCap', 'HCClientWaitSeconds', 'HCClientWindowSeconds', 'HCAckInt',
                          'HCBudgetMs'), limits)
        loot = N(HCClientWaitSeconds=window.HCClientWaitSeconds,
                 HCClientWindowSeconds=window.HCClientWindowSeconds, HCAckInt=window.HCAckInt,
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
                            Changed=N(Invoke=lambda: None), m_LootRunFilter='', m_LootShownFilter='',
                            m_LootStale=False)
        self.members = ('HCValid', 'HCSend', 'HCFeedback', 'HCMergeLootMap', 'HCCarryLootMarks',
                        'HCExpireMarks', 'HCExpireLoot', 'HCLog', 'HCLogReply', 'HCStop', 'HCLootMarkCount',
                        'HCLootFilterOf', 'HCLootLayerStatus')
        self.fields = ('m_Ticket', 'm_Expected', 'm_Pending', 'm_RequestUntil', 'm_Command', 'm_NextSend',
                       'm_LootTicket', 'm_LootUntil', 'm_LootViewUntil', 'm_SnapshotTicket', 'm_Player',
                       'm_Authorized', 'm_SnapshotUntil', 'm_Listening', 'm_OpenRequested', 'm_LastReply',
                       'Revision', 'Notice', 'View', 'Changed', 'Hidden', 'm_LootRunFilter', 'm_LootShownFilter',
                       'm_LootStale')
        for name in ('HCValid', 'HCSend', 'HCLootMap', 'HCMergeLootMap', 'HCLootMarkCount', 'HCCarryLootMarks',
                     'HCExpireMarks', 'HCExpireLoot', 'HCStop', 'HCLootFilterOf', 'HCLootLayerStatus'):
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
        self.assertEqual(101.0 + self.ceiling(authored_limits()), c.m_LootUntil)
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

    @staticmethod
    def ceiling(limits):
        """Largest admitted job (MaxCells) at the budgeted tick plus the reply grace."""
        units = limits.MaxItemsScanned + (limits.MatchRowUnits - 1) * limits.MaxMatches
        row_ticks = math.ceil(units / min(limits.MinRowUnitsPerTick, limits.MaxRowsPerStep))
        row_ticks += row_ticks * limits.TickCapHeadroomPercent // 100
        ticks = limits.MaxCells + row_ticks + 1
        return math.ceil(ticks * limits.MaxTickIntervalMs / 1000) + limits.ReplyGraceSeconds

    def ack(self, c, notice):
        c.HCLootMap(EStr('Bandage'))
        self.now = 101.0
        self.receive(c, self.reply(self.sent[-1].Ticket, notice=notice, marks=0))
        return self.sent[-1].Ticket

    def test_client_window_is_sized_from_the_budget_the_server_sent(self):
        limits = authored_limits()
        ceiling = self.ceiling(limits)
        self.assertGreaterEqual(limits.MinClientWaitSeconds, limits.ReplyGraceSeconds)
        c = self.build()
        ticket = self.ack(c, '[HC Admin] cmd=lootmap result=ok reason=started ticket=1 est_ticks=100 cells=4 tick_ms=1000 budget_ms=100000')
        self.assertEqual(ticket, c.m_LootTicket)
        self.assertEqual(101.0 + 100 + limits.ReplyGraceSeconds, c.m_LootUntil)  # not the largest-job ceiling
        # The window follows the server's own deadline, NOT est_ticks x tick_ms: the
        # server measured a 3 s real cadence (300 s budget) although tick_ms says 1000.
        c = self.build()
        self.ack(c, 'started ticket=1 est_ticks=100 cells=4 tick_ms=1000 budget_ms=300000')
        self.assertEqual(101.0 + 300 + limits.ReplyGraceSeconds, c.m_LootUntil)
        # A shorter server deadline gives a shorter window (100 ticks at 500 ms).
        c = self.build()
        self.ack(c, 'started ticket=1 est_ticks=100 cells=4 tick_ms=500 budget_ms=50000')
        self.assertEqual(101.0 + 50 + limits.ReplyGraceSeconds, c.m_LootUntil)
        # Floor: a tiny job still waits MinClientWaitSeconds.
        c = self.build()
        self.ack(c, 'started ticket=1 est_ticks=2 cells=1 tick_ms=1000 budget_ms=2000')
        self.assertEqual(101.0 + limits.MinClientWaitSeconds, c.m_LootUntil)
        # Ceiling: a deadline above the largest admitted job is clamped to it.
        c = self.build()
        self.ack(c, 'started ticket=1 est_ticks=999999 cells=4 tick_ms=1000 budget_ms=999999999')
        self.assertEqual(101.0 + ceiling, c.m_LootUntil)
        # Unreadable ack text (no budget_ms) falls back to the ceiling, never to a short wait.
        c = self.build()
        self.ack(c, '[HC Admin] cmd=lootmap result=ok reason=started est_ticks=100 tick_ms=1000')
        self.assertEqual(101.0 + ceiling, c.m_LootUntil)

    def test_server_budget_uses_the_slower_of_configured_and_observed_cadence(self):
        lootmap = statics(('HCBudgetMs',), authored_limits())
        self.assertEqual(100000, lootmap.HCBudgetMs(100, 1000, 0))      # no observation yet
        self.assertEqual(100000, lootmap.HCBudgetMs(100, 1000, 400))    # faster than configured
        self.assertEqual(300000, lootmap.HCBudgetMs(100, 1000, 3000))   # slower real cadence
        self.assertEqual(100000, lootmap.HCBudgetMs(100, 1000, -5))     # nonsense observation

    def test_session_and_ticket_expire_with_the_sized_window(self):
        limits = authored_limits()
        c = self.build()
        self.ack(c, 'started ticket=1 est_ticks=10 cells=1 tick_ms=1000 budget_ms=10000')
        window = limits.MinClientWaitSeconds  # 10 + 30 s is below the floor
        self.now = 101.0 + window - 1
        self.assertTrue(c.HCValid())
        self.now = 101.0 + window + 1
        c.HCExpireLoot(self.now)
        self.assertEqual(0, c.m_LootTicket)

    def test_export_failure_after_the_ack_is_a_final_reply_the_client_consumes(self):
        c = self.build()
        ticket = self.ack(c, 'started ticket=1 est_ticks=100 cells=4 tick_ms=1000 budget_ms=100000')
        self.assertEqual(ticket, c.m_LootTicket)
        self.now = 130.0
        failure = '[HC Admin] cmd=lootmap result=refused reason=lootmap_export_failed'
        self.receive(c, self.reply(ticket, snapshot=True, notice=failure, marks=0))
        self.assertEqual(0, c.m_LootTicket)  # no ~23 min "lootmap job running"
        self.assertEqual(failure, c.Notice)
        self.assertFalse(any('late reply' in line for line in self.printed))
        # Old behaviour (Snapshot=false after the ack) is dropped by the client: kept for contrast.
        c = self.build()
        ticket = self.ack(c, 'started ticket=1 est_ticks=100 cells=4 tick_ms=1000 budget_ms=100000')
        self.receive(c, self.reply(ticket, snapshot=False, notice=failure, marks=0))
        self.assertEqual(ticket, c.m_LootTicket)

    def test_refused_lootmap_request_is_not_tracked(self):
        c = self.build()
        c.HCLootMap(EStr('Bandage'))
        self.receive(c, self.reply(self.sent[0].Ticket, notice='[HC Admin] cmd=lootmap result=refused reason=lootmap_job_running', marks=0))
        self.assertEqual(0, c.m_LootTicket)
        self.assertFalse(c.m_Pending)

    def test_refused_final_reply_keeps_the_previous_lootmap_marks_and_shows_the_reason(self):
        for reason, marks in (('lootmap_export_failed', 0), ('job_tick_cap', 2)):  # 2 = partial refused marks
            c = self.build()
            first = self.ack(c, 'started ticket=1 est_ticks=100 cells=4 tick_ms=1000 budget_ms=100000')
            self.now = 120.0
            c.m_LastReply = 120.0
            self.receive(c, self.reply(first, snapshot=True, marks=3, notice='[HC Admin] cmd=lootmap result=ok reason='))
            self.assertEqual(['a0', 'a1', 'a2'], [m.Label for m in c.View.Marks])
            view_until = c.m_LootViewUntil
            self.now = 200.0
            c.m_NextSend = 0.0
            c.m_LastReply = 200.0
            c.HCLootMap(EStr('Bandage'))
            second = self.sent[-1].Ticket
            self.receive(c, self.reply(second, notice='started ticket=2 est_ticks=100 cells=4 tick_ms=1000 budget_ms=100000', marks=0))
            self.now = 260.0
            failure = '[HC Admin] cmd=lootmap result=refused reason=' + reason
            self.receive(c, self.reply(second, snapshot=True, marks=marks, notice=failure))
            self.assertEqual(0, c.m_LootTicket)  # the job is over either way
            self.assertEqual(['a0', 'a1', 'a2'], [m.Label for m in c.View.Marks], reason)  # owner-safe default
            self.assertEqual(view_until, c.m_LootViewUntil)  # the old view timer is not extended
            self.assertIn('reason=' + reason, c.Notice)
            self.assertIn('previous lootmap marks kept', c.Notice)

    def test_kept_marks_after_a_refused_final_reply_are_labelled_with_their_filter(self):
        # #194: a refused final reply keeps the previous marks; the status must say which
        # filter they came from and that they are from the previous run.
        c = self.build()
        c.HCLootMap(EStr('Bandage'))
        first = self.sent[-1].Ticket
        self.now = 101.0
        self.receive(c, self.reply(first, notice='started ticket=1 est_ticks=100 cells=4 tick_ms=1000 budget_ms=100000', marks=0))
        self.receive(c, self.reply(first, snapshot=True, marks=2, notice='[HC Admin] cmd=lootmap result=ok reason='))
        self.assertEqual('lootmap marks: filter=Bandage', c.HCLootLayerStatus())
        c.m_NextSend = 0.0
        self.now = 200.0
        c.m_LastReply = 200.0
        c.HCLootMap(EStr('Rag*'))
        second = self.sent[-1].Ticket
        self.receive(c, self.reply(second, notice='started ticket=2 est_ticks=100 cells=4 tick_ms=1000 budget_ms=100000', marks=0))
        # A running job's filter is not yet the marks' filter.
        self.assertEqual('lootmap marks: filter=Bandage', c.HCLootLayerStatus())
        self.receive(c, self.reply(second, snapshot=True, marks=0,
                                   notice='[HC Admin] cmd=lootmap result=refused reason=job_tick_cap'))
        self.assertIn('previous lootmap marks kept', c.Notice)
        self.assertIn('previous run', c.Notice)
        self.assertIn('filter=Bandage', c.Notice)
        self.assertNotIn('Rag', c.Notice)
        self.assertEqual('lootmap marks: filter=Bandage (previous run)', c.HCLootLayerStatus())
        # A later ok run replaces the layer and its label.
        c.m_NextSend = 0.0
        self.now = 300.0
        c.m_LastReply = 300.0
        c.HCLootMap(EStr('Rag*'))
        third = self.sent[-1].Ticket
        self.receive(c, self.reply(third, notice='started ticket=3 est_ticks=100 cells=4 tick_ms=1000 budget_ms=100000', marks=0))
        self.receive(c, self.reply(third, snapshot=True, marks=1, notice='[HC Admin] cmd=lootmap result=ok reason='))
        self.assertEqual('lootmap marks: filter=Rag*', c.HCLootLayerStatus())
        # No marks on the map means no label (an empty ok run clears the layer).
        c.m_NextSend = 0.0
        self.now = 400.0
        c.m_LastReply = 400.0
        c.HCLootMap(EStr('Gone'))
        fourth = self.sent[-1].Ticket
        self.receive(c, self.reply(fourth, notice='started ticket=4 est_ticks=100 cells=4 tick_ms=1000 budget_ms=100000', marks=0))
        self.receive(c, self.reply(fourth, snapshot=True, marks=0, notice='[HC Admin] cmd=lootmap result=ok reason='))
        self.assertEqual('', c.HCLootLayerStatus())

    def test_ok_final_reply_with_no_matches_still_clears_the_previous_layer(self):
        c = self.build()
        first = self.ack(c, 'started ticket=1 est_ticks=100 cells=4 tick_ms=1000 budget_ms=100000')
        self.receive(c, self.reply(first, snapshot=True, marks=3, notice='[HC Admin] cmd=lootmap result=ok reason='))
        c.m_NextSend = 0.0
        self.now = 200.0
        c.m_LastReply = 200.0
        c.HCLootMap(EStr('Bandage'))
        second = self.sent[-1].Ticket
        self.receive(c, self.reply(second, notice='started ticket=2 est_ticks=100 cells=4 tick_ms=1000 budget_ms=100000', marks=0))
        self.receive(c, self.reply(second, snapshot=True, marks=0, notice='[HC Admin] cmd=lootmap result=ok reason='))
        self.assertEqual([], list(c.View.Marks))
        self.assertNotIn('previous lootmap marks kept', c.Notice)

    def test_session_stays_valid_through_the_derived_job_window_then_stops_cleanly(self):
        c = self.build()
        c.HCLootMap(EStr('Bandage'))
        self.receive(c, self.reply(self.sent[0].Ticket, marks=0))
        self.now = 100.0 + 600  # 10 min, no reply: the 60 s rule alone would have ended it
        self.assertTrue(c.HCValid())
        c.HCExpireLoot(self.now)
        self.assertNotEqual(0, c.m_LootTicket)
        self.now = 101.0 + self.ceiling(authored_limits()) + 1  # derived window over, no final reply
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
