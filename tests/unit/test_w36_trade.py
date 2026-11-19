"""#145/#198 synthetic ports execute authored trade policy/transaction code.
No fixture here observes DayZ inventory, pathfinding or replication.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest
import re
from tests.unit.test_hc_scavenge import bind
from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import EArray
from tests.unit.test_map_layers import EStr

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCAITrade.c'


class TradeBehavior(unittest.TestCase):
    def test_pair_requires_distinct_friendly_funded_surplus_and_cooldown(self):
        source = SOURCE.read_text()
        eligible = translate(source, 'HCEligible', {}, 'HCTradeOfferPolicy')
        due = translate(source, 'HCDue', {}, 'HCTradeOfferPolicy')
        self.assertTrue(eligible('camp-a', 'camp-b', 1, 8, 9, 4))
        for args in [('camp-a', 'camp-a', 1, 8, 9, 4),
                     ('camp-a', 'camp-b', -1, 8, 9, 4),
                     ('camp-a', 'camp-b', 0, 8, 9, 4),
                     ('camp-a', 'camp-b', 1, 4, 9, 4),
                     ('camp-a', 'camp-b', 1, 8, 4, 4)]:
            self.assertFalse(eligible(*args))
        self.assertFalse(due(999, 100, 900))
        self.assertTrue(due(1000, 100, 900))
        self.assertFalse(due(99, 100, 900), 'clock rollback cannot issue a trip')

    def test_readiness_sequence_uses_the_transaction_fault_and_provider(self):
        source = SOURCE.read_text()
        publications = []
        status = N(HCPublish=lambda *args: publications.append(args))
        state = N(Phase='idle', Refusal='')
        transaction = N(m_Enabled=True, m_Ready=True, m_State=state, m_LogRefusal='')
        provider_ready = [False]
        provider_fault = ['']
        env = dict(s_Provider=None,
                   HCTradeReadiness=N(HCTradeReadinessReason=translate(source,
                       'HCTradeReadinessReason', {}, 'HCTradeReadiness')))
        module = N(m_Trade=transaction, m_Status=status, m_StatusReason='')
        bind(source, 'HCAITrade', module, ('HCRefreshStatus',), env)
        module.HCRefreshStatus()
        env['s_Provider'] = N(HCReady=lambda: provider_ready[0], HCOperationalFault=lambda: provider_fault[0])
        module.HCRefreshStatus()
        provider_ready[0] = True
        module.HCRefreshStatus()
        provider_fault[0] = 'CARAVAN_INSTALLED_ROAD_DATA_MISSING'
        module.HCRefreshStatus()
        provider_fault[0] = ''
        module.HCRefreshStatus()
        transaction.m_Ready = False
        state.Refusal = 'TRADE_JOURNAL_UNCERTAIN'
        module.HCRefreshStatus()
        self.assertEqual([
            ('ready', 'provider_absent_base_only'),
            ('ready', 'provider_bound_waiting_site_director'),
            ('ready', 'provider_bound_awaiting_funded_pair'),
            ('refused', 'CARAVAN_INSTALLED_ROAD_DATA_MISSING'),
            ('ready', 'provider_bound_awaiting_funded_pair'),
            ('refused', 'TRADE_JOURNAL_UNCERTAIN')], publications)

    def test_both_camp_stocks_change_in_one_existing_owner_save(self):
        source = SOURCE.read_text().replace('modded class HCHoldouts\n{',
            'modded class HCHoldouts\n{\n    bool m_Ready;\n    bool m_Dirty;\n    HCHoldoutState m_State;')
        source = source.replace('return SaveChanged();', 'return self.SaveChanged();')
        source = re.sub(r'array<[^>]+>', 'HCEventArray', source.replace('array<ref ', 'array<'))
        left = N(Ledger=N(Id='a'), Camp=N(Allocated=True, Supply=5))
        right = N(Ledger=N(Id='b'), Camp=N(Allocated=True, Supply=2))
        other = N(Ledger=N(Id='c'), Camp=N(Allocated=True, Supply=7))
        saves = []
        homes = N(m_Ready=True, m_Dirty=False, m_State=N(Rows=EArray([left, right, other])),
                  SaveChanged=lambda: saves.append((left.Camp.Supply, right.Camp.Supply)) is None)
        bind(source, 'HCHoldouts', homes, ('HCTradeDebit',), dict(Math=N(Max=max), HCEventArray=EArray))
        self.assertTrue(homes.HCTradeDebit('a', 'b', 3))
        self.assertEqual([(2, 0)], saves)
        self.assertEqual(7, other.Camp.Supply)
        self.assertFalse(homes.HCTradeDebit('a', 'a', 1))
        self.assertFalse(homes.HCTradeDebit('a', 'missing', 1))
        self.assertEqual(1, len(saves))

    def test_loss_intent_precedes_both_camp_debit_and_never_replays(self):
        source = SOURCE.read_text()
        events = []
        row = N(Key='trip:1', Phase='new', LeftCamp='a', RightCamp='b', Debit=2)
        book = N(m_Row=row, m_Data=row, m_Ready=True,
                 m_Store=N(Save=lambda image: events.append(('save', image.Phase)) is None),
                 HCDebit=lambda image: events.append(('both-debits', image.Debit)) is None)
        bind(source, 'HCTradeLossBarrier', book, ('HCApply',), {})
        self.assertTrue(book.HCApply())
        self.assertTrue(book.HCApply())
        self.assertEqual([('save', 'intent'), ('both-debits', 2), ('save', 'complete')], events)
        # A loaded ambiguous intent never issues the debit again.
        row.Phase = 'intent'
        self.assertFalse(book.HCApply())
        self.assertEqual(3, len(events))
        row.Phase = 'new'
        book.m_Store.Save = lambda image: False
        self.assertFalse(book.HCApply())
        self.assertEqual(3, len(events), 'failed intent cannot spend camp stock')


class CaravanProviderBehavior(unittest.TestCase):
    def test_inventory_scan_yields_resumes_and_never_enumerates_whole_tree(self):
        source = (ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAITradeAdapter.c').read_text()
        # Syntax only: the translator recognises native PlayerBase declarations.
        source = re.sub(r'array<[^>]+>', 'HCEventArray', source.replace('eAIBase', 'PlayerBase').replace('array<ref ', 'array<'))
        remaining = [0]
        native_reads = [0]
        def take(cost):
            if remaining[0] < cost: return False
            remaining[0] -= cost
            return True
        children = EArray()
        actor = N(IsAlive=lambda: True, GetHumanInventory=lambda: N(GetEntityInHands=lambda: None))
        def inventory(cargo):
            def at(index):
                native_reads[0] += 1
                return cargo[index]
            return N(AttachmentCount=lambda: 0,
                     GetCargo=lambda: N(GetItemCount=lambda: len(cargo), GetItem=at))
        actor.GetInventory = lambda: inventory(children)
        for index in range(200):
            children.append(N(GetInventory=lambda: inventory([]), GetType=lambda i=index: 'wanted' if i == 10 else 'other',
                              IsRuined=lambda: False, GetHierarchyRootPlayer=lambda: actor))
        scan = N(Actor=None, Wanted='', Found=None, Visited=0, Complete=False, Frames=EArray())
        env = dict(HCEventArray=EArray, HCServer=N(HCTickWork=lambda: N(HCTake=take)),
                   HCXTradeInventoryFrame=lambda: N(NodeEntity=None, Checked=False, Attachment=0, CargoIndex=0),
                   ItemBase=N(Cast=lambda entity: None if entity is actor else entity))
        bind(source, 'HCXTradeInventoryScan', scan, ('HCStart', 'HCStep'), env)
        scan.HCStart(actor, 'wanted')
        for tick in range(100):
            remaining[0] = 2
            before = native_reads[0]
            found = scan.HCStep(64)
            self.assertLessEqual(native_reads[0] - before, 2)
            if found: break
        self.assertIs(children[10], found, 'deep traversal must resume at the retained frame')
        self.assertLess(native_reads[0], 20, '200 native items were never enumerated')
        scan.Wanted, scan.Found = 'absent', None
        for tick in range(200):
            remaining[0] = 2
            scan.HCStep(64)
            if scan.Complete: break
        self.assertTrue(scan.Complete)
        self.assertEqual(64, scan.Visited)
        self.assertLess(native_reads[0], 64)

    def test_return_ambush_records_the_exchanged_physical_cargo_once(self):
        source = (ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAITradeAdapter.c').read_text()
        source = re.sub(r'array<[^>]+>', 'HCEventArray', source.replace('array<ref ', 'array<'))
        carrier, partner, raider = N(IsAlive=lambda: True), N(IsAlive=lambda: True), N()
        owner, applied = [carrier], []
        outbound = N(IsRuined=lambda: False, GetQuantity=lambda: 2, GetHierarchyRootPlayer=lambda: partner)
        inbound = N(IsRuined=lambda: False, GetQuantity=lambda: 1, GetHierarchyRootPlayer=lambda: owner[0])
        producer = N(m_Carrier=carrier, m_Partner=partner, m_Outbound=outbound, m_Inbound=inbound,
                     m_Losses=N(Rows=EArray()), m_Recipe=N(MaxLossReceipts=8, LossSupplyDebit=1),
                     m_Store=N(), m_LeftHome='a', m_RightHome='b', m_Failed=False,
                     HCRefuse=lambda reason: None)
        env = dict(HCTradeLossRow=N, HCTradeLossBarrier=lambda: N(HCApply=lambda: applied.append(True) is None),
                   Print=lambda line: None, HCEventArray=EArray)
        bind(source, 'HCXAITradeProducer', producer, ('HCLoss',), env)
        state = N(Id=EStr('hc35-first-barter'), StartedAt=100, Phase='complete',
                  Transfer='reciprocal_confirmed', LeftQuantity=2, RightQuantity=1)
        producer.HCLoss(state)
        self.assertEqual([], applied, 'a confirmed swap is delivery, not cargo loss')
        owner[0] = raider
        producer.HCLoss(state)
        producer.HCLoss(state)
        self.assertEqual([True], applied, 'return cargo ambush must damage both camps once')
        state.StartedAt = 101  # a separate synthetic departure
        producer.m_Inbound = None
        producer.HCLoss(state)
        self.assertEqual([True, True], applied, 'deleted retained cargo is also a loss')

    def test_home_route_restore_defers_cleanup_during_combat(self):
        source = (ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAICaravanAdapter.c').read_text()
        source = re.sub(r'array<[^>]+>', 'HCEventArray', source.replace('array<ref ', 'array<').replace('eAIGroup', 'HCGroupPort'))
        events, combat = [], [True]
        group = N(IsInCombat=lambda: combat[0], ClearWaypoints=lambda: events.append('clear'),
                  SetWaypointBehaviour=lambda value: events.append(value),
                  AddWaypoint=lambda point: events.append(point))
        walker = N(m_Group=group, m_Original=EArray(['original']), m_Behaviour=3,
                   HCReleasePartner=lambda: None)
        bind(source, 'HCXAICaravanAdapter', walker, ('HCRestoreRoute',), {})
        self.assertIs(False, walker.HCRestoreRoute())
        self.assertEqual([], events)
        combat[0] = False
        self.assertIs(True, walker.HCRestoreRoute())
        self.assertEqual(['clear', 3, 'original'], events)
        # Refusing an oversized partner route must not acquire restoration
        # ownership before its original route has been copied.
        source = source.replace('eAIBase', 'PlayerBase').replace(
            'class HCXAICaravanAdapter : HCCaravanInventory\n{',
            'class HCXAICaravanAdapter : HCCaravanInventory\n{\n    ref HCCaravanCorridor Corridor;')
        group.GetWaypoints = lambda: EArray(['a', 'b', 'c'])
        actor = N(IsAlive=lambda: True, GetGroup=lambda: group)
        walker.m_Group, walker.m_PartnerGroup = N(), None
        walker.Corridor = N(MaxRouteNodes=2)
        bind(source, 'HCXAICaravanAdapter', walker, ('HCHoldPartner',),
             dict(PlayerBase=N(Cast=lambda value: value)))
        self.assertFalse(walker.HCHoldPartner(actor))
        self.assertIsNone(walker.m_PartnerGroup)

    def test_group_walk_uses_road_order_and_does_not_override_combat(self):
        source = (ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAICaravanAdapter.c').read_text()
        source = re.sub(r'array<[^>]+>', 'HCEventArray', source.replace('array<ref ', 'array<').replace('eAIGroup', 'HCGroupPort'))
        events, combat = [], [False]
        group = N(IsInCombat=lambda: combat[0], ClearWaypoints=lambda: events.append('clear'),
                  SetWaypointBehaviour=lambda value: events.append(('behaviour', value)),
                  AddWaypoint=lambda point: events.append(point))
        roads = N(Phase='ready', Path=EArray(['destination-road', 'middle-road', 'source-road']))
        walker = N(m_Group=group, HCReady=lambda: True, m_From='home', m_To='meeting')
        env = dict(HCXAICaravanRoads=N(HCGet=lambda: roads), eAIWaypointBehavior=N(HALT=0))
        bind(source, 'HCXAICaravanAdapter', walker, ('HCRequest',), env)
        self.assertTrue(walker.HCRequest(False))
        self.assertEqual(['clear', ('behaviour', 0), 'source-road', 'middle-road', 'destination-road', 'meeting'], events)
        events.clear()
        combat[0] = True
        self.assertFalse(walker.HCRequest(True))
        self.assertEqual([], events)
        combat[0] = False
        self.assertTrue(walker.HCRequest(True))
        self.assertEqual(['clear', ('behaviour', 0), 'destination-road', 'middle-road', 'source-road', 'home'], events)

    def test_bounded_road_search_retains_cursor_and_waypoint_order(self):
        source = (ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAICaravanAdapter.c').read_text().replace('array<ref ', 'array<')
        source = re.sub(r'array<[^>]+>', 'HCEventArray', source)
        units = [0]
        def take(cost):
            if units[0] < cost: return False
            units[0] -= cost
            return True
        nodes = EArray(N(Position=[index, 0, 0], Links=EArray(links), Parent=-2)
                       for index, links in enumerate(([1], [0, 2], [1, 3], [2])))
        graph = N(Config=N(MaxApproachMeters=0.1, RoadWorkPerTick=2, RoadNodesPerWorkUnit=1, MaxRouteNodes=8, MaxJourneyMeters=10),
                  Nodes=nodes, Frontier=EArray(), Path=EArray(), Phase='idle', Reason='',
                  m_Scan=0, m_Head=0, m_Start=-1, m_End=-1, m_StartGap=0, m_EndGap=0,
                  From=None, To=None, m_Length=0, m_Work=N(HCReset=lambda *a: None, HCContinue=lambda: True))
        env = dict(HCEventArray=EArray, HCServer=N(HCTickWork=lambda: N(HCTake=take)),
                   vector=N(Distance=lambda a,b: sum((x-y)**2 for x,y in zip(a,b))**0.5, DistanceSq=lambda a,b: sum((x-y)**2 for x,y in zip(a,b))))
        bind(source, 'HCXAICaravanRoads', graph, ('HCPlan', 'HCNearest', 'HCSearch', 'HCStep'), env)
        self.assertTrue(graph.HCPlan([0,0,0], [3,0,0]))
        units[0] = 1
        graph.HCStep()
        self.assertEqual(1, graph.m_Scan)
        graph.HCStep()
        self.assertEqual(1, graph.m_Scan, 'exhausted shared work leaves cursor unchanged')
        for tick in range(30):
            units[0] = 2
            graph.HCStep()
            if graph.Phase == 'ready': break
        self.assertEqual('ready', graph.Phase)
        self.assertEqual([[3,0,0], [2,0,0], [1,0,0], [0,0,0]], graph.Path)
        # Disconnected graph cannot turn into a straight-line substitute.
        nodes[1].Links = EArray([0])
        graph.HCPlan([0,0,0], [3,0,0])
        for tick in range(30):
            units[0] = 2
            graph.HCStep()
            if graph.Phase == 'idle': break
        self.assertEqual('CARAVAN_ROAD_DISCONNECTED', graph.Reason)
        self.assertEqual([], graph.Path)


if __name__ == '__main__':
    unittest.main()
