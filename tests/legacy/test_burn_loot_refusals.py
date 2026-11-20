"""#160 HC-S001/S002 burn-down for the interiors / search-loot files (synthetic fixtures).

Each baselined silent refusal in HCInteriorModule, HCInteriorStore, HCSearchBinding,
HCSearchHouses and HCSearchRefresh now carries a stable reason. These tests drive the
authored Enforce through the existing translators/harnesses (test_search_economy_houses,
test_search_binding, test_search_economy_integration) and assert the reason; they are not
DayZ evidence. Runtime acceptance stays PENDING.
"""
import unittest
from types import SimpleNamespace as N

from tests.legacy import test_search_binding as binding
from tests.legacy import test_search_economy_houses as houses
from tests.legacy import test_search_economy_integration as integ
from tests.legacy.test_search_economy_houses import SITE_A, site_world
from tests.legacy.test_group_server import EArray


class HouseReasonTests(houses.HouseCase):
    def begin(self):
        house = self.h.house()
        self.h.food(1, site_world(house, SITE_A))
        player = self.h.player()
        action = self.h.action(player, house, [0., 1., 0.], [0., 1., 1.])
        self.h.houses.Begin(action)
        return player, action

    def test_begin_without_interior_action_data_records_session_reason(self):
        self.h.houses.Begin(object())
        self.assertEqual('session_changed', self.h.houses.Refusal())

    def test_continue_refuses_an_unknown_action_with_a_reason(self):
        self.assertFalse(self.h.houses.CanContinue(object()))
        self.assertEqual('session_changed', self.h.houses.Refusal())

    def test_continue_refuses_an_expired_session_with_a_reason(self):
        _, action = self.begin()
        self.assertTrue(self.h.houses.CanContinue(action))
        self.h.world.now += 16.
        self.assertFalse(self.h.houses.CanContinue(action))
        self.assertEqual('session_changed', self.h.houses.Refusal())

    def test_continue_refuses_a_moved_cursor_with_a_reason(self):
        player, action = self.begin()
        player.position = list(action.m_Target.GetObject().ModelToWorld([0., 1., 3.]))
        self.assertFalse(self.h.houses.CanContinue(action))
        self.assertNotEqual('', self.h.houses.Refusal())

    def test_second_commit_on_a_finished_site_is_refused_as_busy(self):
        _, action = self.begin()
        self.h.world.now += 7.
        self.h.houses.Commit(action)
        self.assertEqual(1, len(self.h.moves()))
        self.h.houses.Commit(action)
        self.assertEqual(1, len(self.h.moves()))
        self.assertEqual('busy', self.h.houses.Refusal())

    def test_faulted_service_refuses_the_journal_with_a_storage_reason(self):
        self.h.houses.m_Fault = True
        self.assertFalse(self.h.houses.EnsureJournal())
        self.assertEqual('storage_unavailable', self.h.houses.Refusal())


class PilotJournalReasonTests(houses.HouseCase):
    INHERITED = ('protected ref HCSearchHouseJournal m_Journal; protected ref HCSearchSupplyRegistry m_Registry; '
                 'protected bool m_Fault; protected string m_Refusal;')

    def pilot(self):
        """Translate the pilot subclass; the translator only knows a class's own members, so the
        inherited fields it touches are declared explicitly (their types come from HCSearchHouses)."""
        text = (houses.LOOT / 'HCSearchRefresh.c').read_text()
        header = 'class HCSearchRefreshPilotHouses : HCSearchHouses'
        text = text.replace(header + '\n{', header + '\n{\n    ' + self.INHERITED, 1)
        self.assertIn(self.INHERITED, text)
        env = self.h.env
        env['HCSearchRules'] = N(PinValid=lambda pin: len(pin) == 64)
        for source in houses.Translator(text, only=('HCSearchRefreshPilotJournal', 'HCSearchRefreshPilotHouses')).classes():
            exec(source, env)
        return env['HCSearchRefreshPilotHouses']()

    def test_pilot_journal_without_a_valid_pin_refuses_with_a_storage_reason(self):
        pilot = self.pilot()
        self.assertFalse(pilot.EnsureJournal())
        self.assertEqual('storage_unavailable', pilot.Refusal())

    def test_pilot_faulted_service_refuses_with_a_storage_reason(self):
        pilot = self.pilot()
        pilot.SetPin('d' * 64)
        pilot.m_Fault = True
        self.assertFalse(pilot.EnsureJournal())
        self.assertEqual('storage_unavailable', pilot.Refusal())


class BinderReasonTests(unittest.TestCase):
    def setUp(self):
        self.v = binding.VM()

    def log(self):
        return ' | '.join(str(line) for line in self.v.rt.log)

    def test_unadmitted_search_marker_is_reported_at_start(self):
        self.v.admitted = False
        self.v.owner.OnStart(self.v.settings)
        self.assertIn('admission marker', self.log())
        self.assertEqual([], self.v.queue.pending)

    def test_start_after_stop_is_reported(self):
        self.v.owner.OnStop()
        self.v.owner.OnStart(self.v.settings)
        self.assertIn('start refused', self.log())

    def test_begin_while_disabled_is_reported_and_schedules_nothing(self):
        self.v.owner.OnStart(self.v.settings)
        self.v.settings.EnableSearch = False
        self.v.hook()
        self.assertIn('begin refused', self.log())
        self.assertEqual([], self.v.queue.pending)

    def test_second_begin_is_reported_as_already_handed_over(self):
        self.v.start()
        self.v.hook()
        self.assertIn('begin ignored', self.log())
        self.assertEqual(1, len(self.v.queue.pending))


class InteriorModuleReasonTests(unittest.TestCase):
    def setUp(self):
        self.t = integ.SearchIntegrationTests('test_stop_disables_adapter_before_clearing_sessions_and_sites')
        self.t.setUp()
        self.t.t.m_SearchRefusal = ''

    def reason(self):
        return self.t.t.m_SearchRefusal

    def test_missing_settings_refuse_the_gate_as_service(self):
        self.t.settings = None
        self.assertFalse(self.t.call('SearchGate', self.t.actor, self.t.site))
        self.assertEqual('service', self.reason())

    def test_disabled_search_refuses_the_gate_as_service(self):
        self.t.settings.EnableSearch = False
        self.assertFalse(self.t.call('SearchGate', self.t.actor, self.t.site))
        self.assertEqual('service', self.reason())

    def test_economy_veto_refuses_the_gate_as_supply(self):
        self.t.economy.CanGrant = lambda *a: False
        self.assertFalse(self.t.call('SearchGate', self.t.actor, self.t.site))
        self.assertEqual('supply_changed', self.reason())

    def test_admitted_gate_clears_the_reason(self):
        self.t.t.m_SearchRefusal = 'service'
        self.assertTrue(self.t.call('SearchGate', self.t.actor, self.t.site))
        self.assertEqual('', self.reason())

    def test_start_reports_the_gate_reason_once_per_window(self):
        self.t.economy.CanGrant = lambda *a: False
        self.t.site.Owner = None
        self.assertFalse(self.t.call('CanStart', self.t.actor, self.t.target))
        self.assertTrue(any('reason=supply_changed' in str(e) for e in self.t.events), self.t.events)

    def test_continue_without_a_site_refuses_as_session_changed(self):
        data = integ.NativeRef(player_arg=self.t.actor, target_arg=self.t.target, Site=None)
        self.assertFalse(self.t.call('CanContinue', data))
        self.assertEqual('session_changed', self.reason())

    def test_continue_after_the_deadline_refuses_as_session_changed(self):
        self.t.now = 200.0
        self.assertFalse(self.t.call('CanContinue', self.t.data))
        self.assertEqual('session_changed', self.reason())

    def test_continue_off_target_refuses_as_no_site(self):
        self.t.t.ValidateTarget = lambda *a: False
        self.assertFalse(self.t.call('CanContinue', self.t.data))
        self.assertEqual('no_site', self.reason())

    def test_continue_inside_the_window_is_admitted_with_no_reason(self):
        self.assertTrue(self.t.call('CanContinue', self.t.data))
        self.assertEqual('', self.reason())

    def test_start_without_a_manifest_is_reported(self):
        self.t.startup_ports()
        self.t.t.AllocateManifest = lambda: None
        self.t.t.m_Ready = False
        self.t.call('OnStart', self.t.settings)
        self.assertTrue(any('layout manifest unavailable' in str(e) for e in self.t.events), self.t.events)
        self.assertFalse(self.t.t.m_Ready)

    def test_start_with_unrestorable_layout_state_is_reported(self):
        self.t.startup_ports('restore')
        self.t.t.m_Ready = False
        self.t.call('OnStart', self.t.settings)
        self.assertTrue(any('layout state not restored' in str(e) for e in self.t.events), self.t.events)
        self.assertFalse(self.t.t.m_Ready)


class StoreGrantReasonTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.env = {'Print': self.events.append}
        self.store = N(m_Fault=False, m_Pool=None, m_LastRefusal='')
        self.store.Refuse = lambda reason: integ.invoke('Refuse', self.env, self.store, reason, path=integ.STORE_SOURCE)
        self.site = N(Id='instance_storage_v1', SlotId=0)

    def grant(self):
        return integ.invoke('BeginGrant', self.env, self.store, self.site, 'actor', path=integ.STORE_SOURCE)

    def test_grant_without_a_pool_reports_no_reservation(self):
        self.assertFalse(self.grant())
        self.assertIn('no reserved site', self.store.m_LastRefusal)
        self.assertEqual(1, len(self.events))

    def test_grant_without_a_reserved_site_reports_no_reservation(self):
        self.store.m_Pool = N(Reserved=lambda site: False)
        self.assertFalse(self.grant())
        self.assertIn('no reserved site', self.store.m_LastRefusal)

    def test_faulted_store_reports_the_fault(self):
        self.store.m_Fault = True
        self.assertFalse(self.grant())
        self.assertIn('faulted', self.store.m_LastRefusal)

    def test_repeated_refusal_logs_once_per_reason_change(self):
        self.assertFalse(self.grant())
        self.assertFalse(self.grant())
        self.assertEqual(1, len(self.events))
        self.store.m_Fault = True
        self.assertFalse(self.grant())
        self.assertEqual(2, len(self.events))
        for line in self.events:
            self.assertNotIn('actor', str(line))

    def success_ports(self):
        """Synthetic ports for a clean BeginGrant: exact claim on disk, no attempt/result yet."""
        claim = N(SchemaVersion=2, Phase=1, PlayerId='actor')
        self.env.update(ClaimPath=lambda slot: 'claim', AttemptPath=lambda slot: 'attempt',
                        ResultPath=lambda slot: 'result', FileExist=lambda path: False,
                        MatchesClaim=lambda row, site: True,
                        load_json=lambda path: claim, write_new=lambda path, data: True)
        self.store.m_Pool = N(Reserved=lambda site: True)

    def test_refusal_after_a_successful_grant_is_logged_again(self):
        self.assertFalse(self.grant())
        self.assertEqual(1, len(self.events))
        self.success_ports()
        self.assertTrue(self.grant())
        self.assertEqual('', self.store.m_LastRefusal)
        self.store.m_Pool = None
        self.assertFalse(self.grant())
        self.assertEqual(2, len(self.events), self.events)


if __name__ == '__main__':
    unittest.main()
