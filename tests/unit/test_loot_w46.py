"""W46 behavior over explicit synthetic adapters; never native/runtime evidence."""
import math
import unittest
from types import SimpleNamespace as N
from tests.unit import test_search_preview_sites as preview


class CabinetSites(unittest.TestCase):
    def harness(self):
        h = preview.Harness(self)
        h.house.cls = 'StaticObj_Furniture_case_a'
        h.env['HCInteriorCatalog'] = N(SearchType=lambda cls: cls == h.house.cls)
        h.env['Math'] = N(Sqrt=math.sqrt)
        h.site = N(Target=h.house, Point=[100., 1., 100.])
        h.module = N(FindSite=lambda obj: h.site if obj is h.house else None,
                     SearchGate=lambda player, site: bool(site))
        h.module.HCLootKnownPilotSite = lambda player, obj: h.module.FindSite(obj) if h.module.SearchGate(player, h.module.FindSite(obj)) else None
        h.env['HCInteriorsModule'] = N(Get=lambda: h.module)
        return h

    def test_only_bound_instance_gets_a_server_known_preview(self):
        h = self.harness()
        collect = h.env['HCSearchPreviewSites'].CollectPilot
        h.game.server = True
        self.assertEqual(len(collect(h.player, h.house)), 1)
        other = preview.houses.FakeHouse(h.house.cls, [110., 0., 100.])
        self.assertEqual(collect(h.player, other), [])
        h.module.SearchGate = lambda *args: False
        self.assertEqual(collect(h.player, h.house), [])

    def test_pilot_request_round_trip_is_instance_bound_and_expires(self):
        h = self.harness()
        self.assertFalse(h.client.PilotMatches(h.player, h.target()))
        values, args = h.sent.pop()
        self.assertIs(args[0], h.house)
        h.game.server = True
        server = h.env['HCSearchPreviewServer']()
        server.Start()
        identity = N(GetPlayer=lambda: h.player)
        h.player.GetIdentity = lambda: identity
        server.OnRPC(identity, h.house, 4853901, preview.Context(*values))
        reply, destination = h.sent.pop()
        self.assertEqual(destination, (h.player, 4853902, True, identity))
        h.game.server = False
        h.receive(*reply)
        self.assertTrue(h.client.PilotMatches(h.player, h.target()))
        h.game.now += 3.1
        self.assertTrue(h.client.PilotMatches(h.player, h.target()), 'refreshing membership must not cancel a six-second search')
        self.assertEqual(len(h.sent), 1)
        for elapsed in (4., 5., 6.5):
            h.game.now = 10. + elapsed
            self.assertTrue(h.client.PilotMatches(h.player, h.target()))
        h.receive(reply[0], 0)
        self.assertFalse(h.client.PilotMatches(h.player, h.target()))

    def test_spoofed_instance_key_and_decorative_cabinet_return_no_sites(self):
        h = self.harness()
        h.game.server = True
        server = h.env['HCSearchPreviewServer']()
        server.Start()
        identity = N(GetPlayer=lambda: h.player)
        h.player.GetIdentity = lambda: identity
        server.OnRPC(identity, h.house, 4853901, preview.Context('wrong-key'))
        self.assertEqual(h.sent, [])
        h.module.FindSite = lambda obj: None
        key = h.env['HCSearchPreviewSites'].PilotKey(h.house)
        server.OnRPC(identity, h.house, 4853901, preview.Context(key))
        self.assertEqual(h.sent[0][0], [key, 0])

    def test_same_pose_decoration_cannot_reuse_a_bound_object_reply(self):
        h = self.harness()
        h.client.PilotMatches(h.player, h.target())
        key = h.sent[0][0][0]
        h.receive(key, 1, [0., 1., 0.], 2.5)
        self.assertTrue(h.client.PilotMatches(h.player, h.target()))
        decoration = preview.houses.FakeHouse(h.house.cls, [100., 0., 100.])
        target = preview.houses.FakeTarget(decoration, [100., 1., 100.])
        target.GetComponentIndex = lambda: 0
        self.assertFalse(h.client.PilotMatches(h.player, target))
        self.assertEqual(len(h.sent), 1)

    def test_pilot_cache_keeps_shared_request_and_entry_bounds(self):
        h = self.harness()
        for _ in range(20):
            self.assertFalse(h.client.PilotMatches(h.player, h.target()))
        self.assertEqual(len(h.sent), 1)
        h.receive(h.sent[0][0][0], 0)
        h.game.now += 59.9
        self.assertFalse(h.client.PilotMatches(h.player, h.target()))
        self.assertEqual(len(h.sent), 1)
        h.game.now += .1
        self.assertFalse(h.client.PilotMatches(h.player, h.target()))
        self.assertEqual(len(h.sent), 2)

    def test_decorative_cabinets_cannot_starve_a_bound_cabinet(self):
        h = self.harness()
        for index in range(300):
            cabinet = preview.houses.FakeHouse(h.house.cls, [float(index), 0., 0.])
            key = h.env['HCSearchPreviewSites'].PilotKey(cabinet)
            h.client.EntryForTarget(key, cabinet)
            self.assertEqual(h.sent[-1][0], [key])
            h.receive(key, 0)
            h.game.now += .5
            self.assertLessEqual(h.client.m_Cache.Count(), 256)
        self.assertFalse(h.client.PilotMatches(h.player, h.target()))
        key = h.env['HCSearchPreviewSites'].PilotKey(h.house)
        self.assertEqual(h.sent[-1][0], [key])
        h.receive(key, 1, [0., 1., 0.], 2.5)
        self.assertTrue(h.client.PilotMatches(h.player, h.target()))

    def test_throttled_unsent_entries_cannot_starve_the_next_request(self):
        h = self.harness()
        h.client.EntryFor('SyntheticInFlight')
        pending = h.client.m_Cache.Get('SyntheticInFlight')
        for index in range(300):
            h.client.EntryFor('SyntheticUnsent' + str(index))
        self.assertEqual(len(h.sent), 1)
        h.game.now += .5
        h.client.PilotMatches(h.player, h.target())
        self.assertEqual(len(h.sent), 2)
        self.assertIs(h.client.m_Cache.Get('SyntheticInFlight'), pending)
        self.assertLessEqual(h.client.m_Cache.Count(), 256)

    def test_cache_pressure_preserves_in_flight_and_positive_entries(self):
        h = self.harness()
        h.client.PilotMatches(h.player, h.target())
        pending_key = h.sent[-1][0][0]
        pending = h.client.m_Cache.Get(pending_key)
        h.game.now += .5
        h.client.EntryFor('SyntheticPositive')
        h.receive('SyntheticPositive', 1, [0., 1., 0.], 1.)
        positive = h.client.m_Cache.Get('SyntheticPositive')
        for index in range(300):
            h.game.now += .5
            key = 'SyntheticNegative' + str(index)
            h.client.EntryFor(key)
            h.receive(key, 0)
        self.assertIs(h.client.m_Cache.Get(pending_key), pending)
        self.assertIs(h.client.m_Cache.Get('SyntheticPositive'), positive)
        self.assertLessEqual(h.client.m_Cache.Count(), 256)


class InteriorCoverage(unittest.TestCase):
    def test_refusal_cursor_uses_loaded_rows_and_shared_budget(self):
        from pathlib import Path
        source = Path('mods/HollowCountry/scripts/4_World/Loot/HCLootInteriorCoverage.c')
        self.assertTrue(source.exists(), 'missing bounded per-building furnishing refusal reporter')
        rows = preview.houses.EArray([
            N(BuildingClass='SyntheticA', Furniture='unmeasured', Search='covered'),
            N(BuildingClass='SyntheticB', Furniture='covered', Search='covered'),
            N(BuildingClass='SyntheticC', Furniture='door_pending', Search='covered')])
        state = N(pin='pin-a', loaded=True, left=1)
        logs = []
        def take(*args):
            if state.left <= 0: return False
            state.left -= 1
            return True
        env = dict(preview.houses.Harness().env)
        env.update(HCInteriorTemplates=N(Loaded=lambda: state.loaded, SourcePin=lambda: state.pin,
                       HCLootCoverageRows=lambda: rows, TEMPLATE_CHECKS_PER_STEP=32),
                   HCServer=N(HCTickWork=lambda: N(HCTakeFor=take)),
                   HCUnitBudget=N(HC_WORK_SEARCH_MAINT=1), Print=logs.append)
        for code in preview.NativeSyntax(source.read_text(), only=('HCLootInteriorCoverage',)).classes():
            exec(code, env)
        reporter = env['HCLootInteriorCoverage']()
        reporter.HCTick()
        self.assertEqual(reporter.m_Next, 1)
        self.assertEqual(logs, ['[HC Interiors] building=SyntheticA furnishing_refused=unmeasured search=covered runtime=PENDING'])
        state.left = 3
        reporter.HCTick()
        reporter.HCTick()
        self.assertEqual(reporter.m_Next, 3)
        self.assertEqual(len(logs), 2)
        self.assertIn('SyntheticC furnishing_refused=door_pending', logs[1])
        state.pin = 'pin-b'
        state.left = 1
        reporter.HCTick()
        self.assertEqual(len(logs), 3)
        state.loaded = False
        reporter.HCTick()
        self.assertEqual(len(logs), 3)


class CabinetBindingPolicy(unittest.TestCase):
    def test_real_binding_helper_handles_original_refresh_and_failed_provider(self):
        h = preview.houses.Harness()
        module = h.hook
        site = N(Id='synthetic-site')
        module.m_Ready = True
        module.m_SearchProof = True
        module.m_Store = N(Healthy=lambda: True)
        module.m_Economy = N(Serving=lambda: True)
        module.FindSite = lambda obj: site if obj == 'bound' else None
        module.SearchGate = lambda player, row: True
        # Mechanical adapter: the small translator does not discover inherited fields/methods.
        h.env.update(m_Ready=True, m_SearchProof=True, m_Store=module.m_Store,
                     m_Economy=module.m_Economy, FindSite=lambda obj: module.FindSite(obj),
                     SearchGate=lambda player, row: module.SearchGate(player, row))
        h.env['HCSearchRefreshModule'] = N(Pilot=lambda: None)
        h.env['HCSearchRefreshPilotCatalog'] = N(Find=lambda key: None)
        self.assertIs(module.HCLootKnownPilotSite(h.player(), 'bound'), site)
        self.assertIsNone(module.HCLootKnownPilotSite(h.player(), 'decoration'))
        module.SearchGate = lambda *args: False
        self.assertIsNone(module.HCLootKnownPilotSite(h.player(), 'bound'))
        h.env['HCSearchRefreshModule'] = N(Pilot=lambda: N(Gate=lambda player: True))
        h.env['HCSearchRefreshPilotCatalog'] = N(Find=lambda key: N(Site=site))
        self.assertIs(module.HCLootKnownPilotSite(h.player(), 'bound'), site)
        module.m_Economy.Serving = lambda: False
        self.assertIsNone(module.HCLootKnownPilotSite(h.player(), 'bound'))

    def test_runtime_action_uses_instance_preview_and_keeps_server_authority(self):
        h = CabinetSites().harness()
        from pathlib import Path
        calls = []
        class BaseAction:
            def ActionCondition(self, *args): calls.append('server-start'); return False
            def ActionConditionContinue(self, *args): calls.append('server-continue'); return False
        h.env['_Base_HCActionSearchInterior'] = BaseAction
        h.env['Preview'] = lambda *args: False
        source = Path('mods/HollowCountry/scripts/4_World/Loot/HCLootCabinetAction.c')
        for code in preview.NativeSyntax(source.read_text()).classes(): exec(code, h.env)
        action = h.env['HCActionSearchInterior']()
        self.assertFalse(action.ActionCondition(h.player, h.target(), None))
        self.assertEqual(len(h.sent), 1)
        key = h.sent[0][0][0]
        h.receive(key, 1, [0., 1., 0.], 2.5)
        self.assertTrue(action.ActionCondition(h.player, h.target(), None))
        self.assertFalse(action.ActionCondition(h.player, h.target(), object()))
        h.game.server = True
        self.assertFalse(action.ActionCondition(h.player, h.target(), None))
        self.assertEqual(calls, ['server-start'])


class FloorAdmissionIntegration(unittest.TestCase):
    """Integrated generator over an explicit synthetic stock mission; no CE proof."""
    def test_floor_flags_finite_stock_and_byte_exact_rollback(self):
        import json
        import tempfile
        from pathlib import Path
        from tools.package import datamined_items as dm, economy
        from tests.unit.test_datamined_items import stock_mission, profile, tree
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            mission = root / 'mission'
            stock_mission(mission, dm.load_rows())
            before = tree(mission)
            expected_floor = {
                family + '_' + colour
                for family in ('LeatherJacket', 'LeatherShoes', 'LeatherHat')
                for colour in ('Natural', 'Beige', 'Brown', 'Black')
            } | {'LeatherGloves_' + c for c in ('Natural', 'Beige', 'Brown', 'Black')} | {'LeatherShirt_Natural', 'DrysackBag_Green', 'DrysackBag_Orange',
                 'DrysackBag_Yellow', 'TortillaBag_Desert'}
            self.assertEqual(dm.SUPPLY_UNVERIFIED_FLOOR, expected_floor)
            files = economy.generate(mission, profile() | {'name': 'contextual-pilot'})
            emitted = economy._unique(economy.xml(files['ce/types.xml'], 'types'))
            self.assertEqual(emitted['DrysackBag_Green'].find('flags').get('crafted'), '0')
            report = json.loads(files['economy-report.json'])['supply']
            self.assertEqual((report['admitted'], report['floor_refused'], report['observed']), (59, 0, 0))
            for row in dm.load_rows():
                item = emitted[row['class']]
                self.assertEqual(int(item.findtext('nominal')), row['nominal'])
                expected = row['flags']
                if row['class'] in expected_floor:
                    expected = expected[:4] + '00'
                self.assertEqual(''.join(item.find('flags').get(k) for k in dm.FLAG_ORDER), expected)
                self.assertGreater(row['nominal'], 0)
                self.assertGreaterEqual(row['nominal'], row['min'])
            self.assertEqual(tree(mission), before, 'generation must preserve stock bytes')
            stage = root / 'stage'
            economy.write_delta(stage, files)
            economy.install_delta(stage, mission)
            economy.rollback(mission)
            self.assertEqual(tree(mission), before)
            off = economy.generate(mission, profile() | {'name': 'contextual-pilot'}, include_datamined=False)
            self.assertEqual(json.loads(off['economy-report.json'])['supply']['admitted'], 0)
