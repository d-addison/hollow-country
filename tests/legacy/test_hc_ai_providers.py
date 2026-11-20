"""Wave 16 w32-aiprov: AI trade and faction conflict report ready with bound providers.

Owner decision 2026-11-19: no module may sit off/degraded for want of a provider
verdict. AITrade and FactionConflict now start `ready`; the Expansion AI addon
binds the trade port and the combat port; a base-only install reports a one-time
provider=absent line instead of refusing. Synthetic ports and source contracts
only, never DayZ evidence. Runtime acceptance PENDING.

Actual RED, 2026-11-19, before the source change:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_hc_ai_providers -v
Ran 12 tests in 0.0s / FAILED (failures=9, errors=3)
GREEN: same command: Ran 12 tests / OK.
"""
from pathlib import Path
from types import SimpleNamespace as N
import json
import re
import unittest

from tests.legacy.json_loader_port import json_fields_port
from tests.legacy.test_event_runtime import translate as execute
from tests.legacy.test_hc_scavenge import bind

ROOT = Path(__file__).resolve().parents[2]
TRADE = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCAITrade.c'
CONFLICT = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCFactionConflict.c'
HCX = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World'
TRADE_ADAPTER = HCX / 'HCXAITradeAdapter.c'
COMBAT_ADAPTER = HCX / 'HCXFactionCombatAdapter.c'
RECIPES = ROOT / 'mission/hollow-country/ai/trade-recipes.json'


def block(source, start, stop):
    return source[source.index(start):source.index(stop, source.index(start))]


class TradeReadiness(unittest.TestCase):
    def test_readiness_reason_names_the_real_provider_state(self):
        source = TRADE.read_text()
        reason = execute(source, 'HCTradeReadinessReason', {}, 'HCTradeReadiness')
        self.assertEqual('provider_absent_base_only', reason(False, False))
        self.assertEqual('provider_bound_waiting_site_director', reason(True, False))
        self.assertEqual('provider_bound_awaiting_funded_pair', reason(True, True))

    def test_gesture_gate_needs_both_actors_to_advance_and_bounds_requests(self):
        source = TRADE.read_text()
        gate = N(m_Trade='', m_LeftSerial=0, m_RightSerial=0, m_Requests=0, m_MaxRequests=0)
        names = ('HCArm', 'HCArmedFor', 'HCTakeRequest', 'HCObserved', 'HCReset')
        bind(source, 'HCTradeGestureGate', gate, names, {})
        self.assertFalse(gate.HCArmedFor('hc35-first-barter:100'))
        gate.HCArm('hc35-first-barter:100', 4, 7, 2)
        self.assertTrue(gate.HCArmedFor('hc35-first-barter:100'))
        self.assertFalse(gate.HCArmedFor('hc35-first-barter:101'), 'a later exchange re-arms')
        self.assertFalse(gate.HCObserved(4, 7), 'a request alone is never an observed gesture')
        self.assertFalse(gate.HCObserved(5, 7), 'one actor is not both gestures')
        self.assertTrue(gate.HCObserved(5, 8))
        self.assertTrue(gate.HCTakeRequest())
        self.assertTrue(gate.HCTakeRequest())
        self.assertFalse(gate.HCTakeRequest(), 'emote requests per exchange are capped by the recipe')
        gate.HCReset()
        self.assertFalse(gate.HCArmedFor('hc35-first-barter:100'))
        self.assertFalse(gate.HCObserved(99, 99), 'a disarmed gate observes nothing')

    def test_recipe_new_fields_default_when_absent_and_validate(self):
        source = TRADE.read_text()
        env = {'HCJsonFields': json_fields_port(),
               'HCScavengeDefaults': lambda: N(TransferRangeMeters=2.5),
               'HCTradeRecipe': N(DEFAULT_GESTURE_REQUESTS=3, DEFAULT_INVENTORY_SCAN_LIMIT=64)}
        recipe = N(Version=1, RecipeId='bandage-for-drink', LeftClass='BandageDressing',
                   RightClass='SodaCan_Kvass', TimeoutSeconds=120, TransferRangeMeters=2.5,
                   GestureRequests=0, InventoryScanLimit=0)
        bind(source, 'HCTradeRecipe', recipe, ('HCApplyDefaults', 'HCValid'), env)
        self.assertFalse(recipe.HCValid(), 'zero-filled new fields are invalid until defaulted')
        recipe.HCApplyDefaults('{"Version":1}')
        self.assertEqual((3, 64), (recipe.GestureRequests, recipe.InventoryScanLimit))
        self.assertTrue(recipe.HCValid())
        recipe.GestureRequests, recipe.InventoryScanLimit = 9, 8
        recipe.HCApplyDefaults('{"GestureRequests":9,"InventoryScanLimit":8}')
        self.assertEqual((9, 8), (recipe.GestureRequests, recipe.InventoryScanLimit), 'authored values win')
        recipe.GestureRequests = 0
        self.assertFalse(recipe.HCValid())

    def test_authored_recipe_carries_the_new_named_fields(self):
        data = json.loads(RECIPES.read_text())
        self.assertGreaterEqual(data['GestureRequests'], 1)
        self.assertGreaterEqual(data['InventoryScanLimit'], 1)

    def test_start_admits_the_emote_ack_unverified_and_derives_readiness(self):
        source = TRADE.read_text()
        start = block(source, 'override void OnStart', 'bool HCBegin(string leftLease')
        self.assertNotIn('"TRADE_RENDEZVOUS_EMOTE_ACK_UNVERIFIED")', start.split('HCRefreshStatus')[0].split('quarantined')[0],
                         'the emote-ack gate must not be a refusal at start')
        self.assertNotRegex(start, r'HCPublish\("refused", "TRADE_RENDEZVOUS_EMOTE_ACK_UNVERIFIED"\)')
        self.assertIn('admitted unverified', start)
        self.assertIn('ai_trade_emote_ack.disable', source)
        self.assertIn('FileExist(', start)
        self.assertIn('m_Status.HCPublish("ready", "awaiting_provider_bind")', start)
        tick = block(source, 'override void OnTick', 'override void OnStop')
        self.assertIn('HCRefreshStatus();', tick)
        self.assertIn('provider=absent', source)
        bound = block(source, 'static void HCBindProvider', 'override string GetName')
        self.assertIn('HCRefreshStatus', bound)

    def test_idle_trade_is_state_ready_without_a_provider_check(self):
        source = TRADE.read_text()
        log = block(source, 'void HCLog()', 'void HCClose()')
        self.assertNotIn('m_IO.HCReady()', log, 'module log state is the module state, not the provider')


class TradeAddon(unittest.TestCase):
    def test_trade_adapter_is_bound_from_the_addon_and_unbound_on_stop(self):
        source = TRADE_ADAPTER.read_text()
        self.assertIn('modded class HCXAIAdapter', source)
        on_start = block(source, 'override void OnStart', 'override void OnStop')
        self.assertIn('super.OnStart(settings);', on_start)
        self.assertIn('HCXAIService.Adapter() == this', on_start)
        self.assertIn('HCAITrade.HCBindProvider(tradePort);', on_start)
        self.assertIn('HCFactionConflict.HCInstallCombatPort(combatPort);', on_start)
        on_stop = source[source.index('override void OnStop'):]
        self.assertIn('HCAITrade.HCBindProvider(null);', on_stop)
        self.assertIn('HCFactionConflict.HCRemoveCombatPort', on_stop)
        self.assertNotIn('HCBindProvider(new', source, 'never pass new X as a non-out argument')
        self.assertNotIn('HCInstallCombatPort(new', source)

    def test_trade_adapter_binds_existing_party_items_and_never_mints_or_teleports(self):
        source = TRADE_ADAPTER.read_text()
        for method in ('HCReady', 'HCRefusal', 'HCBind', 'HCBeginWalk', 'HCObservedGestures'):
            self.assertRegex(source, r'override \w+ ' + method + r'\(')
        cls = source[source.index('class HCXAITradeAdapter'):source.index('modded class HCXAIAdapter')]
        self.assertIn('HCInventoryBound(row)', cls)
        self.assertNotIn('EnumerateInventory(', cls)
        self.assertIn('HCXTradeInventoryScan', cls)
        self.assertIn('HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_TRADE, 1)', source)
        self.assertIn('Recipe.InventoryScanLimit', cls)
        self.assertIn('state.ProposalId != lease', cls)
        self.assertIn('HCSignalGreetingSerial()', cls)
        self.assertNotIn('.HCSignalSerial()', cls)
        self.assertIn('HCXStance.Visible(left, right) || !HCXStance.Visible(right, left)', cls)
        self.assertIn('Expansion_PlayEmote()', cls)
        for forbidden in ('SetPosition(', 'CreateInInventory', 'CreateObject', 'SpawnEntity', 'return true; }\n    override string HCRefusal'):
            self.assertNotIn(forbidden, cls)
        walk = block(cls, 'override bool HCBeginWalk', 'override bool HCObservedGestures')
        self.assertIn('HCAtMeeting()', walk)
        self.assertIn('TRADE_RENDEZVOUS_ROUTE_UNSURVEYED', walk)
        self.assertNotIn('AddWaypoint', cls, 'no unsurveyed route may be commanded')
        self.assertNotIn('TRADE_RENDEZVOUS_EMOTE_ACK_UNVERIFIED', cls)


class ConflictReadiness(unittest.TestCase):
    def test_readiness_reason_names_the_provider_and_pair_state(self):
        source = CONFLICT.read_text()
        reason = execute(source, 'HCConflictReadinessReason', {}, 'HCConflictReadiness')
        self.assertEqual('provider_absent_base_only', reason(False, False))
        self.assertEqual('awaiting_surveyed_opposed_pair', reason(True, False))
        self.assertEqual('surveyed_pair_bound_observation_only', reason(True, True))

    def test_start_is_ready_and_a_missing_provider_is_not_a_refusal(self):
        source = CONFLICT.read_text()
        start = block(source, 'override void OnStart', 'override void OnStop')
        self.assertNotIn('COMBAT_PROVIDER_UNVERIFIED', source)
        self.assertIn('m_Operational.HCPublish("ready", "awaiting_provider_bind")', start)
        self.assertIn('HCDecline("COMBAT_PROVIDER_ABSENT")', source)
        tick = block(source, 'override void OnTick', 'static bool HCFinish(')
        self.assertIn('HCRefreshStatus();', tick)
        self.assertIn('static bool HCRemoveCombatPort', source)
        decline = block(source, 'protected bool HCDecline', 'protected void HCLog')
        self.assertNotIn('HCPublish', decline, 'a declined offer waits; it never flips the module state')

    def test_decline_logs_once_per_reason_and_publishes_nothing(self):
        source = CONFLICT.read_text()
        lines, published = [], []
        module = N(m_Declined='', m_Current=None, m_Operational=N(HCPublish=lambda *a: published.append(a)))
        module.HCLog = lambda row, state, reason: lines.append((state, reason))
        bind(source, 'HCFactionConflict', module, ('HCDecline',), {})
        self.assertFalse(module.HCDecline('CONTESTED_SURVEY_UNVERIFIED'))
        self.assertFalse(module.HCDecline('CONTESTED_SURVEY_UNVERIFIED'))
        self.assertFalse(module.HCDecline('COMBAT_PROVIDER_ABSENT'))
        self.assertEqual([('ready', 'CONTESTED_SURVEY_UNVERIFIED'), ('ready', 'COMBAT_PROVIDER_ABSENT')], lines)
        self.assertEqual([], published)


class CombatAddon(unittest.TestCase):
    def test_combat_adapter_uses_the_site_director_and_group_state(self):
        source = COMBAT_ADAPTER.read_text()
        self.assertIn('class HCXFactionCombatAdapter : HCFactionCombatPort', source)
        for method in ('HCSurveyed', 'HCOwns', 'HCDisengaged'):
            self.assertRegex(source, r'override bool ' + method + r'\(')
        surveyed = block(source, 'override bool HCSurveyed', 'override bool HCOwns')
        self.assertIn('state.Key == survey', source)
        self.assertIn('state.Qualified', source)
        self.assertIn('m_Groups.Clear()', surveyed)
        owns = block(source, 'override bool HCOwns', 'override bool HCDisengaged')
        self.assertIn('HCXFactions.HCWorldId(HCXFactions.Id(group.GetFaction()))', owns)
        self.assertIn('HCWorldMaterializer.HCIdentity(lease)', owns)
        self.assertIn('group != owner.Patrol.m_Group', owns)
        disengaged = source[source.index('override bool HCDisengaged'):]
        self.assertIn('IsInCombat()', disengaged)
        for forbidden in ('SetPosition(', 'Delete(', 'SetHealth', 'eAI_Despawn'):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()
