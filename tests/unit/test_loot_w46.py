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


class FloorAdmissionIntegrationFixture(unittest.TestCase):
    """The unowned-tool edit is applied ONLY to a local fixture copy, never production.

    This exercises the proposed lead integration; it does not assert that the
    checkout's generator admits these routes or that native flags yield floor loot.
    """
    def test_proposed_policy_keeps_finite_stock_flags_and_exact_rollback(self):
        import json
        import tempfile
        import types
        from pathlib import Path
        from unittest import mock
        from tools.package import datamined_items as dm, economy
        from tests.unit.test_datamined_items import stock_mission, profile, tree
        fixture_source, fixture_ledger = floor_integration_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'datamined_items.py'
            source.write_text(fixture_source)
            policy = root / 'loot-dispositions.json'
            policy.write_text(json.dumps(fixture_ledger))
            module = types.ModuleType('w46_fixture_datamined_items')
            module.__file__ = str(source)
            exec(compile(source.read_text(), str(source), 'exec'), module.__dict__)
            module.DATA = dm.DATA
            module.SUPPLY_DATA = policy
            mission = root / 'mission'
            mission.mkdir()
            stock_mission(mission, dm.load_rows())
            before = tree(mission)
            with mock.patch.object(economy, 'datamined_items', module):
                files = economy.generate(mission, (profile() | {'name': 'contextual-pilot'}))
                report = json.loads(files['economy-report.json'])['supply']
                self.assertEqual((report['admitted'], report['floor_refused'], report['observed']), (55, 0, 0))
                emitted = economy._unique(economy.xml(files['ce/types.xml'], 'types'))
                for row in dm.load_rows():
                    if row['class'] not in FLOOR_CLASSES: continue
                    item = emitted[row['class']]
                    self.assertEqual(int(item.findtext('nominal')), row['nominal'])
                    self.assertEqual(''.join(item.find('flags').get(k) for k in dm.FLAG_ORDER), row['flags'])
                    self.assertGreater(row['nominal'], 0)
                    self.assertGreaterEqual(row['nominal'], row['min'])
                stage = root / 'stage'
                stage.mkdir()
                for name, data in files.items():
                    path = stage / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                economy.install_delta(stage, mission)
                economy.rollback(mission)
                self.assertEqual(tree(mission), before)
                off = economy.generate(mission, (profile() | {'name': 'contextual-pilot'}), include_datamined=False)
                self.assertEqual(json.loads(off['economy-report.json'])['supply']['admitted'], 0)


FLOOR_CLASSES = frozenset(
    family + '_' + colour
    for family in ('LeatherJacket', 'LeatherShoes', 'LeatherHat')
    for colour in ('Natural', 'Beige', 'Brown', 'Black')) | {
        'LeatherShirt_Natural', 'DrysackBag_Green', 'DrysackBag_Orange',
        'DrysackBag_Yellow', 'TortillaBag_Desert'}


def floor_integration_fixture():
    """Exact proposed patch, isolated because tools/package is not worker-owned."""
    import json
    from tools.package import datamined_items as dm
    from pathlib import Path
    source = Path(dm.__file__).read_text()
    old = "        if row['flags'][4:] != '00':"
    new = """        # Owner 2026-11-19: exact shipped proposals admitted unverified; retain native flags.
        reviewed = next((r for r in load_rows() if r['class'] == row['class']), None)
        if row['flags'][4:] != '00' and (row['class'] not in SUPPLY_UNVERIFIED_FLOOR or row != reviewed):"""
    assert source.count(old) == 1
    constant = 'SUPPLY_UNVERIFIED_FLOOR = frozenset(' + repr(sorted(FLOOR_CLASSES)) + ')\n'
    source = source.replace('ACCEPTANCE = ', constant + 'ACCEPTANCE = ', 1).replace(old, new)
    ledger = json.loads(dm.SUPPLY_DATA.read_text())
    for entry in ledger['entries']:
        if entry['class'] in FLOOR_CLASSES:
            entry.update(route='native-floor', floor_admitted=True, refusal=None)
            entry['evidence'].append('Owner 2026-11-19: admit exact finite proposal unverified; crafted/deloot flags retained; ordinary floor acquisition runtime=PENDING')
    return source, ledger
