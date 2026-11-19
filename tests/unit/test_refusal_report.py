"""WP-2 authored Enforce execution over explicit synthetic native boundaries.

Given a refused server action, emit one native status message and one id-free
RPT line per (player object, reason) in five seconds. Translation tests are not
DayZ/ChatMP delivery, normal PBO compilation or two-client acceptance evidence.

Issue #154 / WP-2 follows spec FR-006/007/012 and NFR-001/003/006; shared runtime
contract keeps native server inventory authority unchanged. Installed API evidence:
PlayerBase.c:6911/6915/6924 Message/ChatMP/MessageStatus, Global/Game.c:914/1034/1120
GetTickTime/ChatMP/IsServer in scripts-1.30.164289. World helper uses World-only
PlayerBase, ActionData and ActionTarget; Game contains only stable reason strings.

Actual red/green (2026-11-18, source-only synthetic tests):
  python3 -B -m unittest tests.unit.test_refusal_report -v
  RED before helper: 11 errors (HCRefusal.c missing).
  RED after helper, before conversions: 7 failures (expected one message, got zero).
  RED server gate matrix: 6 failures (expected one message, got zero).
  python3 -B -m unittest tests.unit.test_search_refusal_reasons.HouseRefusalTests.test_different_reason_in_same_window_is_reported -v
  RED: 1 failure (expected two different-reason messages, got one).
  GREEN: python3 -B -m unittest tests.unit.test_refusal_report tests.unit.test_search_refusal_reasons -v
  Lint: python3 -B -m tools.validate.enforce_lint --no-native (new=0 stale=0).
Final related-suite GREEN: 257 tests. Full discovery: 5875 tests, one unrelated
installed-mission read OSError(12, Cannot allocate memory) in test_event_sites.py:808;
that optional installed-data test passed alone. Native acceptance remains pending.
Native follow-up for lead: package/compile on the pinned build, force each server
refusal, observe a client status message plus `[HC Refusal] refused reason=<code> class=<type>`
in the RPT, no player ids, repeat within five seconds and after expiry. Repeat
with two clients for independent player windows. No runtime acceptance recorded.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.unit.test_search_economy_houses import Translator, HMap, find_out
from tests.unit.test_group_server import EArray

SCRIPTS = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts'


def install_refusal(env):
    env.update(EArray=EArray, HMap=HMap, find_out=find_out)
    for path in ('3_Game/Core/HCRefusal.c', '4_World/Core/HCRefusalReport.c'):
        for code in Translator((SCRIPTS / path).read_text()).classes():
            exec(compile(code, path + '(synthetic translation)', 'exec'), env)
    return env['HCRefusalReport']


class SyntheticPlayer:
    def __init__(self, ident='synthetic-secret-id'):
        self.messages = []
        self.ident = ident

    def MessageStatus(self, text):
        self.messages.append(text)

    def GetIdentity(self):
        raise AssertionError('reporting must never read player ids')


class MethodsTranslator(Translator):
    """Same statement translator, restricted to selected action methods/fields."""
    def __init__(self, source, owner, methods):
        self.methods = set(methods)
        super().__init__(source, only=(owner,))

    def members(self, body):
        import re
        return [(head, block) for head, block in super().members(body)
                if block is None or re.search(r'\b(' + '|'.join(self.methods) + r')\(', head)]


class RefusalReportTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.server = True
        self.lines = []
        self.player = SyntheticPlayer()
        self.subject = N(GetType=lambda: 'SyntheticCar')
        self.game = N(IsServer=lambda: self.server, GetTickTime=lambda: self.now)
        self.env = dict(GetGame=lambda: self.game, Print=self.lines.append)
        self.report = install_refusal(self.env)
        self.codes = self.env['HCRefusal']

    def send(self, player=None, reason='service', subject=None):
        return self.report.RefusalMessage(player or self.player, reason,
                                          subject or self.subject, 'Synthetic refusal.')

    def test_one_message_and_exactly_one_id_free_line_per_pair_window(self):
        self.assertTrue(self.send())
        self.assertFalse(self.send())
        self.assertEqual(['Synthetic refusal.'], self.player.messages)
        self.assertEqual(['[HC Refusal] refused reason=service class=SyntheticCar'], self.lines)
        self.now += 4.999
        self.assertFalse(self.send())
        self.now += .001
        self.assertTrue(self.send())
        self.assertEqual(2, len(self.player.messages))
        self.assertEqual(2, len(self.lines))

    def test_reasons_players_and_subjects_have_the_right_scope(self):
        self.send(reason='service')
        self.assertTrue(self.send(reason='busy'))
        self.assertFalse(self.send(reason='busy', subject=N(GetType=lambda: 'OtherCar')))
        other = SyntheticPlayer()  # Two anonymous/equal-id players never share a window.
        self.assertTrue(self.send(other, reason='busy'))
        self.assertEqual(2, len(self.player.messages))
        self.assertEqual(1, len(other.messages))
        self.assertEqual(3, len(self.lines))

    def test_role_nulls_empty_reason_and_success_do_not_report(self):
        self.server = False
        self.assertFalse(self.send())
        self.server = True
        self.assertFalse(self.report.RefusalMessage(None, 'service', self.subject, 'Refused.'))
        self.assertFalse(self.send(reason=''))
        self.assertEqual([], self.lines)
        self.assertEqual([], self.player.messages)
        self.assertTrue(self.report.RefusalMessage(self.player, 'service', None, 'Refused.'))
        self.assertEqual(['[HC Refusal] refused reason=service class=none'], self.lines)

    def test_full_cache_never_clears_live_windows_and_recovers_after_expiry(self):
        self.send()
        # Explicit small synthetic capacity. Production capacity remains authored.
        self.report.MAX_WINDOWS = 3
        self.send(SyntheticPlayer('two'))
        self.send(SyntheticPlayer('three'))
        self.assertFalse(self.send(SyntheticPlayer('overflow')))
        self.assertFalse(self.send())
        self.assertEqual(3, self.report.s_Windows.Count())
        self.now += 5
        self.assertTrue(self.send())
        self.assertEqual(1, self.report.s_Windows.Count())

    def test_clock_rollback_allows_one_fresh_window(self):
        self.send()
        self.now = 1
        self.assertTrue(self.send())
        self.assertFalse(self.send())
        self.assertEqual(2, len(self.lines))

    def test_disappeared_weak_player_handle_releases_capacity(self):
        self.report.MAX_WINDOWS = 1
        self.send()
        # Synthetic native weak-handle invalidation; this is not a DayZ disconnect proof.
        self.report.s_Windows[0].Actor = None
        self.assertTrue(self.send(SyntheticPlayer('replacement')))
        self.assertEqual(1, self.report.s_Windows.Count())

    def test_native_message_reentry_does_not_emit_a_second_line(self):
        calls = []
        def reenter(text):
            calls.append(text)
            self.assertFalse(self.send())
        self.player.MessageStatus = reenter
        self.assertTrue(self.send())
        self.assertEqual(['Synthetic refusal.'], calls)
        self.assertEqual(1, len(self.lines))

    def action(self, filename, owner, **extra):
        base = type('NativeAction', (), {'OnStartServer': lambda self, data: None})
        env = self.env
        env.update(ActionContinuousBase=base, ActionSingleUseBase=base, **extra)
        methods = ('ActionCondition', 'ActionConditionContinue', 'OnStartServer',
                   'OnFinishProgressServer', 'OnExecuteServer')
        if filename == 'HCActionSalvageWreck.c':
            # The salvage action words its refusals through HCCraftRefusal (real bodies).
            craft = ('WreckMessage', 'WreckTarget', 'WreckAction')
            for code in MethodsTranslator((SCRIPTS / '4_World/Crafting/HCNativeCraftingSafety.c').read_text(),
                                          'HCCraftRefusal', craft).classes():
                exec(compile(code, 'HCNativeCraftingSafety.c(synthetic)', 'exec'), env)
        for code in MethodsTranslator((SCRIPTS / '4_World/Actions' / filename).read_text(),
                                      owner, methods).classes():
            exec(compile(code, filename + '(synthetic action)', 'exec'), env)
        return env[owner]()

    def assert_window(self, callback, reason, subject='SyntheticCar'):
        for _ in range(3):
            callback()
        self.assertEqual(1, len(self.player.messages), 'each refusal needs exactly one player message')
        self.assertEqual(['[HC Refusal] refused reason=' + reason + ' class=' + subject], self.lines)
        self.now += 5
        callback()
        self.assertEqual(2, len(self.player.messages))
        self.assertEqual(2, len(self.lines))
        first = self.player
        self.player = SyntheticPlayer('second-private-id')
        callback()
        self.assertEqual(1, len(self.player.messages))
        self.assertEqual(2, len(first.messages))
        self.assertEqual(3, len(self.lines))

    def data(self):
        return N(m_Player=self.player, m_Target=N(GetObject=lambda: self.subject, GetParent=lambda: None),
                 m_MainItem=self.subject, Completed=False)

    def test_all_server_prediction_refusals_report_even_without_a_start_hook(self):
        cases = (
            ('HCActionFlipVehicle.c', 'HCActionFlipVehicle', 'flip_unavailable',
             dict(HCVehicleFlipModule=N(Get=lambda: None, HCCandidate=lambda *a: True),
                  CarScript=N(Cast=lambda value: value))),
            ('HCActionSalvageWreck.c', 'HCActionSalvageWreck', 'salvage_unavailable',
             dict(HCWreckSalvageModule=N(Get=lambda: None))),
            ('HCActionSiphonFuel.c', 'HCActionSiphonFuel', 'siphon_diagnostic_unavailable',
             dict(HCSiphonDiagnosticLocks=lambda: N(), ValidateLive=lambda *a: False)),
            ('HCFuelSiphon.c', 'HCActionSiphonFuelFromCar', 'siphon_unavailable',
             dict(HCFuelSiphon=N(Allowed=lambda *a: False, ServerEnabled=lambda: False))),
            ('HCTapedLightActions.c', 'HCActionMountTapedLight', 'taped_light_mount_unavailable',
             dict(HCTapedLightRuntime=N(CanExecute=lambda *a: False))),
            ('HCTapedLightActions.c', 'HCActionRemoveTapedLight', 'taped_light_remove_unavailable',
             dict(HCTapedLightRuntime=N(CanExecute=lambda *a: False))),
        )
        for filename, owner, reason, ports in cases:
            with self.subTest(action=owner):
                self.setUp()
                action = self.action(filename, owner, **ports)
                target = self.data().m_Target
                self.assert_window(lambda: self.assertFalse(
                    action.ActionCondition(self.player, target, self.subject)), reason)

    def test_flip_missing_module_is_reported_by_server_completion(self):
        action = self.action('HCActionFlipVehicle.c', 'HCActionFlipVehicle',
                             HCVehicleFlipModule=N(Get=lambda: None))
        self.assert_window(lambda: action.OnFinishProgressServer(self.data()), 'flip_unavailable')

    def test_flip_queue_rejection_is_reported(self):
        action = self.action('HCActionFlipVehicle.c', 'HCActionFlipVehicle',
                             HCVehicleFlipModule=N(Get=lambda: N(HCQueue=lambda *a: False)),
                             CarScript=N(Cast=lambda value: value))
        self.assert_window(lambda: action.OnFinishProgressServer(self.data()), 'flip_unavailable')

    def test_salvage_missing_module_is_reported_by_start_and_completion(self):
        action = self.action('HCActionSalvageWreck.c', 'HCActionSalvageWreck',
                             HCWreckSalvageModule=N(Get=lambda: None),
                             HCWreckSalvageActionData=N(Cast=lambda value: value))
        def attempt():
            action.OnStartServer(self.data())
            action.OnFinishProgressServer(self.data())
        self.assert_window(attempt, 'salvage_unavailable')

    def test_diagnostic_siphon_invalid_start_is_reported(self):
        action = self.action('HCActionSiphonFuel.c', 'HCActionSiphonFuel',
                             HCSiphonDiagnosticLocks=lambda: N(),
                             HCSiphonDiagnosticData=N(Cast=lambda value: value),
                             ValidateLive=lambda *a: False)
        # ValidateLive is an explicit synthetic policy port outside these hook bodies.
        data = self.data()
        data.Sampled, data.LockHeld = False, False
        def attempt():
            data.m_Player = self.player
            action.OnStartServer(data)
        self.assert_window(attempt, 'siphon_diagnostic_unavailable')

    def test_production_siphon_closed_gate_reports_from_server_start(self):
        action = self.action('HCFuelSiphon.c', 'HCActionSiphonFuelFromCar',
                             HCFuelSiphon=N(Allowed=lambda *a: True, ServerEnabled=lambda: False))
        self.assert_window(lambda: action.OnStartServer(self.data()), 'siphon_unavailable')

    def test_each_taped_light_action_reports_failed_execution(self):
        for owner, code in (('HCActionMountTapedLight', 'taped_light_mount_unavailable'),
                            ('HCActionRemoveTapedLight', 'taped_light_remove_unavailable')):
            with self.subTest(owner=owner):
                self.setUp()
                action = self.action('HCTapedLightActions.c', owner,
                                     HCTapedLightRuntime=N(Execute=lambda *a: 2),
                                     HCTapedLightCode=N(OK=0))
                self.assert_window(lambda: action.OnExecuteServer(self.data()), code)


if __name__ == '__main__':
    unittest.main()
