"""T014/T015, FR-006: source-flow regression with explicit SYNTHETIC ports.

Spec: template-only startup -> server action -> finite native handle or clear empty
response; startup facts must describe actual service/journal/marker readiness.
Plan/tasks: exercise real binding startup, House hook and transaction; cover stale
first supply, absent/invalid pilot logging, and bounded readiness reporting.
No DayZ, CE population, native I/O, inventory atomicity or client proof is implied.

Actual TDD (2026-11-17), PYTHONDONTWRITEBYTECODE=1 python3 -m unittest:
  tests.unit.test_house_search_flow tests.unit.test_search_preview_sites -v
  RED: Ran 21 tests in 1.073s; FAILED (failures=5, errors=3).
  First-supply/expiry failures verbatim: AssertionError: False is not true
  and AssertionError: 2 != 1. Missing readiness hook verbatim:
  AttributeError: type object 'HCSearchBinding' has no attribute 'TemplatesComplete'
  Rebind/depleted regressions RED: Ran 2 tests in 0.155s; FAILED (failures=2).
  Both failures verbatim: AssertionError: False is not true
  Stop-callback regression RED: Ran 2 tests in 0.071s; FAILED (errors=1).
  Failure verbatim: AttributeError: 'NoneType' object has no attribute 'Count'
  Focused GREEN (the four requested modules plus this one):
  Ran 132 tests in 4.800s; OK.
Full command output is retained in .banso-writer/house-search-*.txt (local only).
"""
import re
import unittest
from types import SimpleNamespace as N

from tests.unit import test_search_economy_houses as houses
from tests.unit import test_search_economy_integration as pilot
from tests.unit.test_enforce_locals import duplicate_locals

SCRIPTS = houses.SCRIPTS
BINDING = SCRIPTS / '4_World/Loot/HCSearchBinding.c'
TEMPLATES = SCRIPTS / '4_World/Interiors/HCInteriorTemplatesModule.c'
ACTION = SCRIPTS / '4_World/Interiors/HCInteriorAction.c'


def member(path, name):
    return member_text(path.read_text(), name)


def member_text(source, name):
    match = re.search(r'\b(?:static |override )?\w+ ' + name + r'\([^)]*\)\s*\{', source)
    if not match:
        raise AssertionError('missing authored method ' + name)
    end = houses.match_brace(source, match.end() - 1)
    return source[match.start():end + 1]


class Flow:
    def __init__(self, marker=True, **settings):
        self.h = houses.Harness(**settings)
        self.logs = []
        self.marker = marker
        self.env = self.h.env
        self.env.update(HCModule=object, Print=self.logs.append, _binding_state=N(s_Instance=None))
        self.env['HCInteriorRules'].SearchAdmitted = lambda: self.marker
        self.env['HCInteriorRules'].SearchOptIn = lambda: self.marker
        for code in BindingSyntax(BINDING.read_text(), only=('HCSearchBinding',)).classes():
            exec(code, self.env)
        self.binding = self.env['HCSearchBinding']()
        self.binding.OnStart(self.h.settings)
        self.service = self.env['HCSearchBinding'].Houses()
        self.owner = self.h.hook
        self.env['HCInteriorsModule'].Get = staticmethod(lambda: self.owner)
        # A failed House Begin has no wrapper/session. The real pilot's continuation
        # refuses it; the older hook harness uses a permissive spy instead.
        self.env['_Base_HCInteriorsModule'].CanContinue = lambda obj, data: False
        # The actual action methods call HCInteriorsModule.Get, the source hook then
        # calls the actual binding, rather than Harness's manually started service.
        base = type('ActionBasePort', (), {
            'OnStartServer': lambda *a: None, 'OnEndServer': lambda *a: None})
        self.env['ActionContinuousBase'] = base
        self.env['HCSearchNoise'] = N(PhaseOf=lambda data: 0, OnCommitted=lambda *a: None)
        names = ('ActionCondition', 'ActionConditionContinue', 'OnStartServer',
                 'OnFinishProgressServer', 'OnEndServer')
        code = 'class ActionFlow : ActionContinuousBase\n{\n'
        code += '\n'.join(member(ACTION, name) for name in names) + '\n}'
        for translated in houses.Translator(code).classes(): exec(translated, self.env)
        self.action = self.env['ActionFlow']()

    def target(self):
        house = self.h.house()
        player = self.h.player()
        data = self.h.action(player, house, [0., 1., 0.], [0., 1., 1.])
        return house, player, data

    def report(self):
        self.env['HCSearchBinding'].TemplatesComplete(self.owner)


class BindingSyntax(houses.Translator):
    def expr(self, text, names):
        # Enforce static fields are shared between instance and static methods.
        return super().expr(text, names).replace('self.s_Instance', '_binding_state.s_Instance')


class ServerFlowTests(unittest.TestCase):
    def test_binding_starts_without_placement_then_action_grants_exact_existing_item(self):
        f = Flow()
        self.assertTrue(f.service.Started())
        self.assertFalse(f.binding.m_Claimed)  # No pilot PlacementComplete/Begin.
        house, player, data = f.target()
        item = f.h.food(1, houses.site_world(house, houses.SITE_A))
        self.assertTrue(f.action.ActionCondition(player, data.m_Target, None))
        f.action.OnStartServer(data)
        self.assertTrue(f.action.ActionConditionContinue(data))
        f.h.world.now += 5.49  # Server tolerance starts at 5.5, native action remains six seconds.
        f.action.OnFinishProgressServer(data)
        self.assertEqual([], player.cargo)
        f.h.world.now += .01
        f.action.OnFinishProgressServer(data)
        f.action.OnFinishProgressServer(data)
        self.assertEqual([item], player.cargo)
        self.assertEqual(['Search stopped; action completed too early. Please try again.',
                          'Search complete.'], player.messages)
        f.action.OnEndServer(data)
        self.assertEqual(0, f.service.SessionCount())
        self.assertEqual([], f.h.pilot_calls)
        self.assertEqual([], f.h.rt.created)

    def test_empty_begin_reports_empty_and_never_creates_or_journals_supply(self):
        f = Flow()
        _, player, data = f.target()
        f.action.OnStartServer(data)
        self.assertEqual(['Nothing here to search.'], player.messages)
        self.assertFalse(f.action.ActionConditionContinue(data))
        self.assertEqual(0, f.service.m_Journal.Count())
        self.assertEqual([], f.h.rt.created)

    def test_changed_first_supply_does_not_block_later_transferable_row(self):
        f = Flow()
        house, player, data = f.target()
        stale = f.h.food(1, houses.site_world(house, houses.SITE_A))
        usable = f.h.food(2, houses.site_world(house, houses.SITE_A))
        f.action.OnStartServer(data)
        f.action.OnEndServer(data)  # Cancel leaves finite rows available.
        stale.quantity += 1.  # Existing registered handle is no longer unchanged.
        player.messages.clear()
        f.action.OnStartServer(data)
        self.assertTrue(f.action.ActionConditionContinue(data))
        f.h.world.now += 6.
        f.action.OnFinishProgressServer(data)
        self.assertEqual([usable], player.cargo)
        self.assertEqual(0, f.service.m_Journal.Row(0).Phase)
        self.assertEqual(2, f.service.m_Journal.Row(1).Phase)

    def test_readiness_opens_healthy_journal_without_observing_or_binding_ce(self):
        f = Flow()
        self.assertIsNone(f.service.m_Journal)
        # Registry construction would fail this test: startup may precede CE readiness.
        def unexpected_registry():
            self.fail('startup must leave native supply registry lazy')
        f.env['HCSearchSupplyRegistry'] = unexpected_registry
        f.report()
        f.report()
        self.assertTrue(f.service.m_Journal.Healthy())
        self.assertIsNone(f.service.m_Registry)
        self.assertEqual(0, f.service.m_Journal.Count())
        facts = [line for line in f.logs if '[HC Search Houses] armed=' in line]
        self.assertEqual([
            '[HC Search Houses] armed=1 templates_loaded=1 service_started=1 journal_healthy=1 marker_present=1; supply=lazy stock CE; runtime acceptance PENDING'
        ], facts)

    def test_unhealthy_journal_is_never_reported_armed(self):
        f = Flow()
        self.assertTrue(f.service.EnsureJournal())
        f.service.m_Journal.m_Fault = True
        f.report()
        self.assertIn('armed=0 templates_loaded=1 service_started=1 journal_healthy=0 marker_present=1', f.logs[-1])

    def test_missing_marker_or_disabled_preference_cannot_be_armed(self):
        for disabled in ('marker', 'EnableSearch', 'EnableInteriors'):
            f = Flow(**{disabled: False})
            f.report()
            self.assertIn('[HC Search Houses] armed=0 ', f.logs[-1])

    def test_stop_during_supply_selection_refuses_without_session_or_transfer(self):
        f = Flow()
        house, player, data = f.target()
        f.h.food(1, houses.site_world(house, houses.SITE_A))
        f.h.food(2, houses.site_world(house, houses.SITE_A))
        player.during_find = lambda count: f.service.Stop()
        f.action.OnStartServer(data)
        self.assertEqual(0, f.service.SessionCount())
        self.assertEqual([], player.cargo)

    def test_depleted_site_can_report_empty_without_allocating_replacement_loot(self):
        f = Flow()
        house, player, data = f.target()
        f.h.food(1, houses.site_world(house, houses.SITE_A))
        f.action.OnStartServer(data)
        f.h.world.now += 6.
        f.action.OnFinishProgressServer(data)
        f.action.OnEndServer(data)
        player.messages.clear()
        f.h.food(9, houses.site_world(house, houses.SITE_A))  # Later CE is not a refill.
        self.assertTrue(f.action.ActionCondition(player, data.m_Target, None))
        f.action.OnStartServer(data)
        self.assertEqual(['Nothing here to search.'], player.messages)
        self.assertEqual(1, f.service.m_Journal.Count())
        self.assertEqual(1, len(player.cargo))

    def test_absent_journaled_handle_can_rebind_after_sixty_seconds_without_refill(self):
        f = Flow()
        house, player, data = f.target()
        item = f.h.food(1, houses.site_world(house, houses.SITE_A))
        f.action.OnStartServer(data)
        f.action.OnEndServer(data)
        self.assertTrue(f.service.ReleaseIdle())
        item.position = [0., 0., 0.]  # Synthetic incomplete world restoration.
        f.action.OnStartServer(data)
        self.assertEqual(0, f.service.SessionCount())
        item.position = houses.site_world(house, houses.SITE_A)
        f.h.world.now += 60.
        f.action.OnStartServer(data)
        self.assertTrue(f.action.ActionConditionContinue(data))
        f.h.world.now += 6.
        f.action.OnFinishProgressServer(data)
        self.assertEqual([item], player.cargo)
        self.assertEqual(1, f.service.m_Journal.Count())

    def test_room_log_suppresses_only_missing_optional_legacy_file(self):
        path = SCRIPTS / '4_World/Infected/HCInfectedRooms.c'
        # Execute just the owned diagnostic statement; no room admissions are changed.
        line = next(line for line in path.read_text().splitlines() if 'Print(' in line and 'room classes=' in line)
        code = 'class RoomLogPort\n{\n static void Log()\n {\n' + line + '\n }\n}'
        for reason, expected in (('rooms_missing', 0), ('rooms_json', 1), ('rooms_build', 1)):
            logs = []
            env = dict(s_ProductionReason=reason, s_ProductionContext='',
                       s_ProductionClasses=houses.EArray(), s_ProductionBindings=houses.EArray(),
                       Print=logs.append, tostr=str)
            for translated in houses.Translator(code).classes(): exec(translated, env)
            env['RoomLogPort'].Log()
            self.assertEqual(expected, len(logs), reason)

    def test_template_pack_tick_reports_after_installing_owner_and_pilot_absence(self):
        # HC-24 review P2-1: the staged pack load finishes in a later tick, so OnStart must not
        # report readiness (ReportReadiness latches the first templates_loaded/armed line).
        start = member(TEMPLATES, 'OnStart')
        self.assertNotIn('HCSearchBinding.TemplatesComplete(this)', start)
        self.assertNotIn('HCInteriorTemplatePlacement.Place(', start)
        source = (SCRIPTS / '4_World/Interiors/HCInteriorTemplates.c').read_text()
        bridge = source[source.index('protected bool m_PackLoading;'):]
        tick = member_text(bridge, 'OnTick')
        self.assertIn('HCSearchBinding.TemplatesComplete(this)', tick)
        self.assertLess(tick.index('s_Instance = this'), tick.index('HCSearchBinding.TemplatesComplete(this)'))
        self.assertIn('legacy pilot absent; template path in use', tick)

    def test_absent_pilot_returns_quietly_but_present_invalid_pilot_is_an_error(self):
        for present in (False, True):
            target = N(s_Instance=None, IsEnabled=lambda settings: True, m_Config=None,
                       ValidateConfig=lambda settings: False)
            logs = []
            env = dict(GetGame=lambda: N(IsServer=lambda: True), Print=logs.append,
                       FileExist=lambda path: present, load_config=lambda: False)
            pilot.invoke('OnStart', env, target, houses.settings())
            if present:
                self.assertIn('[HC Interiors] invalid legacy pilot configuration; pilot disabled', logs)
            else:
                self.assertEqual([], logs)

    def test_changed_sources_obey_enforce_local_rules(self):
        for path in (BINDING, TEMPLATES, SCRIPTS / '4_World/Loot/HCSearchHouses.c'):
            self.assertEqual([], duplicate_locals(path.read_text()), path.name)


if __name__ == '__main__':
    unittest.main()
