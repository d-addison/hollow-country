"""#168/5 spec -> bounded ground-observation plan -> admin/export task.

Explicit synthetic native worlds/HTTP/files only; execute the authored handlers
through the existing restricted statement adapter. Never DayZ acceptance.

RED: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_admin_lootmap -v
AssertionError: Missing authored method HCAdminWire.HCIsLootMap in HCAdminWire.c
GREEN (same command): Ran 1 test; OK.
Boundary extension RED (same command): AssertionError: False is not true
at self.assertTrue(oversized_class.HCStep()); GREEN: Ran 1 test; OK.
"""
import io
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch

from tests.unit.test_admin_test_kit import compile_authored, base_scope, authored_method
from tests.unit.test_group_server import EArray
from tests.unit.test_map_layers import EStr as NativeText

ROOT = Path(__file__).resolve().parents[2]
ADMIN = ROOT / 'mods/HollowCountry/scripts/4_World/Admin'
WIRE = ROOT / 'mods/HollowCountry/scripts/3_Game/Admin/HCAdminWire.c'


class EStr(NativeText):
    def ToLower(self):
        # This explicit native fixture already returns lowercase world names.
        assert self == self.lower()


class NativeArray(EArray):
    def Clear(self): self.clear()


def document():
    return N(version=1, time=100, world='chernarusplus', filter='', mode='',
             state='pending', reason='', scope='ground_world_observations',
             census='refused_ce_inventory_enumeration_unavailable', scanned=0,
             cells=0, matched=0, truncated=0, types=NativeArray(), points=NativeArray())


def bind(owner, path, cls, names, scope, members=()):
    for name in names:
        fn = compile_authored(path, cls, name, scope, members, modded=False,
                              native_strings=EStr, fields=('m_Document','m_Cursor','m_Cell','m_Ticks','m_MaxTicks'))
        setattr(owner, name, lambda *args, fn=fn: fn(owner, *args))


class LootmapBehavior(unittest.TestCase):
    def test_admin_job_is_bounded_filtered_readonly_and_exports_honest_counts(self):
        wire = N()
        bind(wire, WIRE, 'HCAdminWire', ('HCIsLootMap',), base_scope())
        self.assertTrue(wire.HCIsLootMap(EStr('lootmap BandageDressing')))
        self.assertTrue(wire.HCIsLootMap(EStr('lootmap')))
        self.assertFalse(wire.HCIsLootMap(EStr('lootmapx BandageDressing')))
        path = ADMIN / 'HCAdminLootMap.c'
        defaults = N(SubCellM=1000, MaxPositionsPerReply=2, MaxRowsPerStep=2, MatchRowUnits=1,
                     MaxObjectsPerCell=16, MaxItemsScanned=40, MaxMatches=20,
                     MaxTypes=4, MaxCells=16, CooldownSeconds=30, MaxTickIntervalMs=1000)
        query_calls, probes, sent, exported = [], [], [], []
        server = [True]
        ce_ready = [True]
        clock = [100]

        def item(name, x, z, nominal=8, parent=None):
            return N(GetType=lambda:EStr(name), GetPosition=lambda:(x, 0, z),
                     GetEconomyProfile=lambda:N(GetNominal=lambda:nominal),
                     GetHierarchyParent=lambda:parent)

        bandage = item('BandageDressing', 1000, 100)
        match = item('BandageDressing', 100, 100)
        cargo = item('BandageDressing', 100, 100, parent=object())
        longer = item('BandageDressingExtra', 100, 200)
        no_ce = item('BandageDressing', 100, 300)
        no_ce.GetEconomyProfile = lambda:None
        worlds = [[match, cargo, longer, no_ce, bandage], [bandage, match], [], []]

        def query(pos, radius, candidates, cargos):
            query_calls.append((pos, radius))
            candidates.extend(worlds[len(query_calls)-1])

        game = N(IsServer=lambda:server[0], GetTickTime=lambda:0,
                 GetWorld=lambda:N(GetWorldSize=lambda:2000), GetWorldName=lambda:EStr('chernarusplus'),
                 ConfigIsExisting=lambda name: name == 'CfgVehicles BandageDressing',
                 GetObjectsAtPosition=query)
        env = base_scope(GetGame=lambda:game, GetCEApi=lambda:object() if ce_ready[0] else None,
                         EntityAI=N(Cast=lambda entity:entity), Vector=lambda x,y,z:(x,y,z),
                         HCGroupClock=N(Utc=lambda:clock[0]),
                         HCAdminLootType=lambda:N(className='', count=0, nominal=-1),
                         HCAdminLootPoint=lambda:N(), HCAdminLootDocument=document)
        env['Math'].Ceil = math.ceil
        env['Math'].Sqrt = math.sqrt
        valid = compile_authored(ADMIN.parent/'Debug/HCDebugSnapshot.c', 'HCDebugSnapshot',
                                 'HCPositionValid', env, modded=False)
        env['HCDebugSnapshot'] = N(HCPositionValid=lambda pos:valid(None, pos))
        static = N()
        env['HCAdminLootMap'] = static
        bind(static, path, 'HCAdminLootMap', ('HCValidFilter', 'HCJobTickCap', 'HCCellsAcross'), env)

        class Units:
            # Explicit synthetic twin of HCUnitBudget (first item always admitted).
            def HCReset(self, limit): self.limit, self.used, self.items = max(limit, 1), 0, 0
            def HCTake(self, cost):
                if self.items and self.used + max(cost, 1) > self.limit: return False
                self.used, self.items = self.used + max(cost, 1), self.items + 1
                return True
            def HCCharge(self, cost): self.used += max(cost, 0)

        def job():
            owner = N(m_Limits=defaults, m_Document=None, m_Candidates=NativeArray(),
                      m_Cargos=NativeArray(), m_Seen=NativeArray(), m_Cursor=0,
                      m_Cell=0, m_Across=0, m_Size=0, m_Loaded=False,
                      m_MinX=0, m_MinZ=0, m_MaxX=0, m_MaxZ=0, m_Ticks=0, m_MaxTicks=0,
                      m_Budget=N(HCReset=lambda count:probes.append(count), HCContinue=lambda:True),
                      m_Units=Units())
            names = ('HCStart', 'HCStep', 'HCQueryCell', 'HCObserve', 'HCFinish',
                     'HCDocument', 'HCReply', 'HCMatches', 'HCTotalCells', 'HCMaxTicks')
            bind(owner, path, 'HCAdminLootMap', names, env, names)
            return owner

        exact = job()
        self.assertTrue(exact.HCStart(EStr('BandageDressing'), 1000))
        previous = 0
        for _ in range(20):
            done = exact.HCStep()
            self.assertLessEqual(exact.m_Document.scanned - previous, 2)
            previous = exact.m_Document.scanned
            if done: break
        self.assertTrue(done)
        result = exact.HCDocument()
        self.assertEqual('observed', result.state)
        self.assertEqual((2, 0), (result.matched, result.truncated))
        self.assertEqual([('BandageDressing', 2, 8)],
                         [(t.className, t.count, t.nominal) for t in result.types])
        self.assertEqual('refused_ce_inventory_enumeration_unavailable', result.census)
        self.assertEqual(4, len(query_calls))
        # Circle = half diagonal of the 1000 m sub-cell (707.1), rounded up: covers the cell.
        self.assertEqual([708]*4, [call[1] for call in query_calls])
        self.assertNotIn('m_Seen', (ADMIN/'HCAdminLootMap.c').read_text())
        self.assertEqual(2, len(result.points))  # overlapping queries did not double count
        env.update(HCAdminReply=lambda:N(Lines=NativeArray(), Marks=NativeArray()), HCAdminMark=lambda:N())
        bind(exact, path, 'HCAdminLootMap', ('HCReply',), env)
        reply = exact.HCReply(7)
        self.assertEqual(7, reply.Ticket)
        self.assertEqual(2, len(reply.Marks))
        self.assertIn('nominal=8', reply.Lines[0])

        query_calls.clear()
        prefix = job()
        self.assertTrue(prefix.HCStart(EStr('Bandage*'), 1000))
        for _ in range(20):
            if prefix.HCStep(): break
        self.assertEqual(3, prefix.HCDocument().matched)
        self.assertEqual(1, prefix.HCDocument().truncated)
        self.assertEqual(2, len(prefix.HCDocument().points))
        for bad in ('', '*', '../Bandage', 'Bandage x', 'x'*97):
            invalid = job()
            self.assertFalse(invalid.HCStart(EStr(bad), 1000))
            self.assertEqual('invalid_class_or_prefix', invalid.HCDocument().reason)
        ce_ready[0] = False
        refused = job()
        self.assertFalse(refused.HCStart(EStr('Bandage'), 1000))
        self.assertEqual('ce_world_enumeration_unavailable', refused.HCDocument().reason)
        ce_ready[0] = True
        server[0] = False
        self.assertFalse(job().HCStart(EStr('Bandage'), 1000))
        server[0] = True
        # An unavailable clock must refuse, not export time=-1 that the webmap rejects.
        clock[0] = -1
        unclocked = job()
        self.assertFalse(unclocked.HCStart(EStr('Bandage'), 1000))
        self.assertEqual('clock_unavailable', unclocked.HCDocument().reason)
        clock[0] = 100
        # The tick cap is exact only while the core tick is not slower than budgeted.
        slow = job()
        self.assertFalse(slow.HCStart(EStr('Bandage'), 2000))
        self.assertEqual('tick_interval_exceeds_job_budget', slow.HCDocument().reason)
        self.assertFalse(job().HCStart(EStr('Bandage'), 0))
        query_calls.clear()
        defaults.MaxObjectsPerCell = 1
        capped = job()
        self.assertTrue(capped.HCStart(EStr('Bandage'), 1000))
        self.assertTrue(capped.HCStep())
        self.assertEqual('objects_per_cell_cap', capped.HCDocument().reason)
        self.assertEqual(0, capped.HCDocument().matched)
        defaults.MaxObjectsPerCell = 16
        query_calls.clear()
        deferred = job()
        self.assertTrue(deferred.HCStart(EStr('Bandage'), 1000))
        deferred.m_Budget.HCContinue = lambda:False
        self.assertFalse(deferred.HCStep())
        self.assertEqual((0, 0, 1), (deferred.m_Cursor, deferred.HCDocument().scanned, len(query_calls)))
        deferred.m_Budget.HCContinue = lambda:True
        self.assertFalse(deferred.HCStep())
        self.assertEqual(1, len(query_calls))  # retained native output, no requery
        defaults.MaxItemsScanned = 2
        self.assertTrue(deferred.HCStep())
        self.assertEqual('items_scanned_cap', deferred.HCDocument().reason)
        defaults.MaxItemsScanned = 40
        deferred = job()
        self.assertTrue(deferred.HCStart(EStr('Bandage'), 1000))
        deferred.m_Ticks = deferred.m_MaxTicks
        before = len(query_calls)
        self.assertTrue(deferred.HCStep())
        self.assertEqual('job_tick_cap', deferred.HCDocument().reason)
        self.assertEqual(before, len(query_calls))
        query_calls.clear()
        worlds[0] = [item('Bandage'+'x'*96, 100, 100)]
        oversized_class = job()
        self.assertTrue(oversized_class.HCStart(EStr('Bandage'), 1000))
        self.assertTrue(oversized_class.HCStep())
        self.assertEqual('class_name_cap', oversized_class.HCDocument().reason)
        worlds[0] = [match, cargo, longer, no_ce, bandage]

        # Execute final authority gate; revoked/non-admin cannot receive positions.
        authorized = [False]
        module = N(HCAuthorized=lambda who:authorized[0], HCRefused=lambda who:None,
                   HCStatus=lambda *args:None,
                   HCStartLootMap=lambda *args:sent.append(args), HCCommand=lambda *args:None)
        dispatch = compile_authored(ADMIN/'HCAdminModule.c', 'HCAdminModule', 'HCDispatch',
                    base_scope(HCAdminWire=wire),
                    ('HCAuthorized','HCRefused','HCStatus','HCStartLootMap','HCCommand'), modded=False)
        dispatch(module, object(), EStr('lootmap Bandage'), 0, 1)
        self.assertEqual([], sent)
        authorized[0] = True
        dispatch(module, object(), EStr('lootmap Bandage'), 0, 1)
        self.assertEqual(1, len(sent))
        send = compile_authored(ADMIN/'HCAdminModule.c', 'HCAdminModule', 'HCSend',
                    base_scope(ScriptRPC=lambda:N(Write=lambda data:None,
                    Send=lambda *args:exported.append(args)), HCAdminWire=N(REPLY=7)),
                    ('HCAuthorized',), modded=False)
        authorized[0] = False
        send(module, object(), reply)
        self.assertEqual([], exported)

        # Execute request/export lifecycle, erasing only the adapter's unsupported
        # generic-type syntax. Store, directory and identity ports are recorders.
        receipts, notices, printed = [], [], []
        exported.clear()
        store_ok = [True]
        now = [10]
        game.GetTickTime = lambda:now[0]
        factory = lambda:job()
        factory.PATH = '$profile:HollowCountry/debug/lootmap.json'
        factory.MAX_BYTES = 65536
        module = N(m_DebugEnabled=True, m_LootMap=None, m_LootMapAfter=0,
                   m_LootMapSender=None, m_LootMapTicket=0,
                   HCAuthorized=lambda who:authorized[0], HCPlayer=lambda who:object(),
                   HCReply=lambda *args:notices.append(args),
                   HCSend=lambda *args:exported.append(args))
        module_env = base_scope(GetGame=lambda:game, HCAdminLootMap=factory,
                HCAdminLootMapLimits=lambda:defaults, HCV2ThreatStore=N(
                CanOpen=lambda path:True, Save=lambda path,data,limit:
                receipts.append((path,data.state,limit)) or store_ok[0]),
                FileExist=lambda path:True, MakeDirectory=lambda path:True, Print=lambda line:printed.append(line),
                HCServer=N(Get=lambda:N(GetSettings=lambda:N(TickIntervalMs=1000))))
        source = (ADMIN/'HCAdminModule.c').read_text().replace('HCV2ThreatStore<HCAdminLootDocument>', 'HCV2ThreatStore')
        with patch.object(Path, 'read_text', return_value=source):
            start = compile_authored(ADMIN/'HCAdminModule.c', 'HCAdminModule', 'HCStartLootMap',
                    module_env, ('HCAuthorized','HCReply','HCSend'), modded=False)
            tick = compile_authored(ADMIN/'HCAdminModule.c', 'HCAdminModule', 'HCLootMapTick',
                    module_env, ('HCAuthorized','HCPlayer','HCReply','HCSend'), modded=False)
        self.assertFalse(start(module, object(), EStr('lootmap Bandage'), 5))
        self.assertEqual([], receipts)  # no profile IO for unauthorized requests
        authorized[0] = True
        module.m_DebugEnabled = False
        self.assertFalse(start(module, object(), EStr('lootmap Bandage'), 5))
        self.assertEqual('EnableDebugSnapshot-off', notices[-1][-1])
        self.assertEqual([], receipts)
        module.m_DebugEnabled = True
        query_calls.clear()
        self.assertTrue(start(module, object(), EStr('lootmap Bandage'), 5))
        self.assertEqual('pending', receipts[-1][1])
        started = [line for line in printed if 'state=started' in line]
        self.assertEqual(1, len(started))
        for token in ('cells=4', 'sub_cell_m=1000', 'max_ticks=', 'query_cost=unmeasured', 'runtime=PENDING'):
            self.assertIn(token, started[0])
        # Immediate ack (the snapshot pattern): started, the request ticket and the
        # derived tick estimate. The marks are NOT sent yet; they come later by ticket.
        ack = notices[-1]
        self.assertEqual((5, 'lootmap', True), ack[1:4])
        for token in ('started', 'ticket=5', 'est_ticks=', 'final_reply=by_ticket'):
            self.assertIn(token, ack[-1])
        self.assertEqual([], exported)
        # A second lootmap while one runs is refused server-side with a named reason.
        self.assertFalse(start(module, object(), EStr('lootmap Bandage'), 6))
        self.assertEqual((6, 'lootmap', False), notices[-1][1:4])
        self.assertTrue(notices[-1][-1].startswith('lootmap_job_running'))
        for _ in range(20):
            tick(module)
            if module.m_LootMap is None: break
        self.assertEqual('observed', receipts[-1][1])
        self.assertEqual(1, len(exported))
        self.assertEqual(2, len(exported[0][1].Marks))
        self.assertFalse(start(module, object(), EStr('lootmap Bandage'), 6))
        self.assertEqual('lootmap_cooldown', notices[-1][-1])
        now[0] = 50
        self.assertTrue(start(module, object(), EStr('lootmap Bandage'), 6))
        authorized[0] = False
        before = len(query_calls)
        tick(module)
        self.assertIsNone(module.m_LootMap)
        self.assertEqual(before, len(query_calls))
        self.assertEqual(1, len(exported))  # cancellation neither scans nor delivers
        authorized[0] = True
        now[0] = 90
        store_ok[0] = False
        self.assertFalse(start(module, object(), EStr('lootmap Bandage'), 7))
        self.assertEqual('lootmap_export_failed', notices[-1][-1])
        self.assertIsNone(module.m_LootMap)

        # Offline loopback-handler port; no socket or game/profile data.
        from tools.webmap import server as web
        class Connection:
            def __init__(self, path):
                self.input = io.BytesIO(f'GET {path} HTTP/1.0\r\n\r\n'.encode())
                self.output = io.BytesIO()
            def makefile(self, *_args): return self.input
            def sendall(self, data): self.output.write(data)
        def plain(row):
            if isinstance(row, N): return {k:plain(v) for k,v in vars(row).items()}
            if isinstance(row, list): return [plain(v) for v in row]
            return row
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            loot = root/'lootmap.json'
            handler = web.make_handler(root/'snapshot.json')
            def get(path):
                conn = Connection(path)
                handler(conn, ('127.0.0.1', 1), None)
                head, body = conn.output.getvalue().split(b'\r\n\r\n', 1)
                return int(head.split()[1]), body
            loot.write_text(json.dumps(plain(result)))
            self.assertEqual(200, get('/lootmap.json')[0])
            self.assertEqual(2, json.loads(get('/lootmap.json')[1])['matched'])
            (root/'lootmap.json.tmp').write_text('synthetic intent')
            self.assertEqual(503, get('/lootmap.json')[0])
            (root/'lootmap.json.tmp').unlink()
            broken = plain(result)
            broken['points'][0]['x'] = float('nan')
            loot.write_text(json.dumps(broken))
            self.assertEqual(503, get('/lootmap.json')[0])
            loot.write_bytes(b' '*(web.MAX_LOOTMAP_BYTES+1))
            self.assertEqual(503, get('/lootmap.json')[0])
            broken = plain(result)
            broken['version'] = 0  # native/legacy zero-fill cannot imply v1
            loot.write_text(json.dumps(broken))
            self.assertEqual(503, get('/lootmap.json')[0])
            broken = plain(result)
            broken['matched'] += 1
            loot.write_text(json.dumps(broken))
            self.assertEqual(503, get('/lootmap.json')[0])
            self.assertEqual(404, get('/lootmap.json.bak')[0])
            self.assertIn(b'id="loot-filter"', get('/')[1])


if __name__ == '__main__':
    unittest.main()
