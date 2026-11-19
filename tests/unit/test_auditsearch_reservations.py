"""#144: authored finite house transaction over explicit synthetic native ports.

The shared registry hook patch below is applied ONLY to an in-memory fixture copy;
HCSearchNativeSupply.c belongs to integration. These tests do not establish DayZ behaviour.
"""
import unittest
from types import SimpleNamespace as N

from tests.unit import test_search_economy_houses as houses
from tests.unit import test_search_supply_provider as supply
from tests.unit import test_hc_tick_budget_fixes as fixes


def registry_hooks(source):
    """Exact integration request: preserve one Move, delegate only actor identity."""
    if 'string HCSearchActorId(PlayerBase actor)' in source:
        return source
    anchor = '    protected bool Preflight(HCSearchEntry entry, PlayerBase actor)'
    hooks = '''    string HCSearchActorId(PlayerBase actor)
    {
        if (!actor || !actor.GetIdentity() || actor.GetIdentity().GetPlayer() != actor) return "";
        return actor.GetIdentity().GetId();
    }

    bool HCSearchActorAuthorized(PlayerBase actor, string actorId)
    {
        return actorId != "" && HCSearchActorId(actor) == actorId;
    }

'''
    source = source.replace(anchor, hooks + anchor)
    source = source.replace('if (!actor.GetIdentity() || actor.GetIdentity().GetPlayer() != actor) return false;',
                            'if (HCSearchActorId(actor) == "") return false;')
    source = source.replace('string actorId = actor.GetIdentity().GetId();', 'string actorId = HCSearchActorId(actor);')
    source = source.replace('if (!actor.IsAlive() || actor.IsUnconscious() || !actor.GetIdentity()) return 4;\n        if (actor.GetIdentity().GetId() != actorId || actor.GetIdentity().GetPlayer() != actor) return 4;',
                            'if (!actor.IsAlive() || actor.IsUnconscious() || !HCSearchActorAuthorized(actor, actorId)) return 4;')
    return source


def install(h):
    # Explicit fixture-copy integration, no edits to the shared registry source.
    path = 'HCSearchNativeSupply.c'
    h.rt.sources[path] = registry_hooks(h.rt.sources[path])
    h.rt.methods[path] = supply.method_names(h.rt.sources[path])
    source = (houses.LOOT / 'auditsearch_PickerReservations.c').read_text()
    env = h.env
    env['HCV2Admission'] = N(Line=lambda feature, pref, gate, qualified: 'synthetic admission runtime unverified')
    env['_Base_HCSearchHouses'] = env['HCSearchHouses']
    # Registry runtime dispatch is already an authored-source interpreter. Subclass
    # adapters bind translated subclass methods onto that same registry object.
    env['_RegistryBase'] = object
    adapted = source.replace(': HCSearchSupplyRegistry', ': _RegistryBase')
    for code in fixes.ModdedLinkTranslator(adapted).classes():
        exec(code, env)
    fixes.HouseBudgetCase.chain_init(env['HCSearchHouses'], env['_Base_HCSearchHouses'])
    registry_type = env['auditsearch_SupplyRegistry']

    def registry_factory():
        registry = h.rt.env['HCSearchSupplyRegistry']()
        registry.HCHouses = None
        for name in ('HCSearchActorId', 'HCSearchActorAuthorized'):
            method = getattr(registry_type, name)
            # Execute the authored subclass hook over the same registry owner.
            setattr(registry, name, lambda *args, method=method: method(registry, *args))
        return registry

    env['auditsearch_SupplyRegistry'] = registry_factory
    h.houses = env['HCSearchHouses']()
    h.houses.Start(h.settings)
    h.houses_binding.houses = h.houses
    return h


class ReservationTests(unittest.TestCase):
    def setUp(self):
        self.h = houses.Harness()
        self.assertTrue(hasattr(self.h.houses, 'HCCommitReservation'), 'shared finite reservation commit missing')
        install(self.h)
        self.house = self.h.house()
        self.item = self.h.food(1, houses.site_world(self.house, houses.SITE_A))
        self.actor = self.h.player('synthetic_ai')
        self.actor.GetIdentity = lambda: None
        self.actor.position = houses.site_world(self.house, houses.SITE_A)
        self.current = True
        self.authority = N(HCValid=lambda actor, actor_id: self.current and actor is self.actor and actor_id == 'synthetic_party')

    def reserve(self, actor=None, authority=None, actor_id='synthetic_party'):
        return self.h.houses.HCReservePicker(actor or self.actor, self.house, 1, actor_id, authority or self.authority)

    def test_one_shared_lock_and_one_real_transfer_with_no_replay(self):
        token = self.reserve()
        self.assertIsNotNone(token)
        self.assertIs(self.item, self.h.houses.HCPickerItem(token))
        self.assertIsNone(self.reserve())
        player = self.h.player('human')
        action = self.h.action(player, self.house, [0., 1., 0.], [0., 1., 1.])
        self.h.houses.Begin(action)
        self.assertEqual(1, self.h.houses.SessionCount())
        self.assertFalse(self.h.houses.HCCommitReservation(token))
        self.h.world.now += 6.5
        self.assertTrue(self.h.houses.HCCommitReservation(token))
        self.assertFalse(self.h.houses.HCCommitReservation(token))
        self.assertEqual([self.item], self.actor.cargo)
        self.assertEqual(1, len(self.h.moves()))
        self.h.houses.HCReleasePicker(token)
        self.assertIsNone(self.h.houses.HCPickerItem(token))
        self.assertIsNone(self.reserve())
        self.assertEqual([], self.h.rt.created)

    def test_a_spent_shared_pool_still_binds_once_without_pre_spending_the_scan_unit(self):
        budget = fixes.spent_budget()
        fixes.route_budget(self.h.env, budget)
        self.assertIsNotNone(self.reserve())
        self.assertEqual(1, budget.HCStarved())

    def test_full_inventory_or_changed_stock_does_not_grant(self):
        self.actor.capacity = 0
        self.assertIsNone(self.reserve())
        self.actor.capacity = 10
        token = self.reserve()
        self.assertIsNotNone(token)
        self.item.quantity += 1
        self.h.world.now += 6.5
        self.assertFalse(self.h.houses.HCCommitReservation(token))
        self.assertEqual([], self.h.moves())

    def test_player_reservation_blocks_picker(self):
        player = self.h.player('human')
        action = self.h.action(player, self.house, [0., 1., 0.], [0., 1., 1.])
        self.h.houses.Begin(action)
        self.assertIsNone(self.reserve())

    def test_authority_loss_range_death_deadline_and_opt_out_refuse_without_move(self):
        for cause in ('authority', 'range', 'death', 'deadline', 'off', 'stop'):
            with self.subTest(cause=cause):
                self.setUp()
                token = self.reserve()
                self.assertIsNotNone(token)
                self.h.world.now += 6.5
                if cause == 'authority': self.current = False
                if cause == 'range': self.actor.position = [9000., 0., 9000.]
                if cause == 'death': self.actor.alive = False
                if cause == 'deadline': self.h.world.now += 20.
                if cause == 'off': self.h.settings.EnableSearch = False
                if cause == 'stop': self.h.houses.Stop()
                self.assertFalse(self.h.houses.HCCommitReservation(token))
                self.assertEqual([], self.h.moves())

    def test_native_preflight_callback_revocation_cannot_move(self):
        token = self.reserve()
        # Revoke at the final inventory callback, after durable claim/attempt.
        # The original registry must call the authority hook again before TakeToDst.
        revoke_at = self.actor.finds + 3
        self.actor.during_find = lambda n: setattr(self, 'current', n < revoke_at)
        self.h.world.now += 6.5
        self.assertFalse(self.h.houses.HCCommitReservation(token))
        self.assertEqual([], self.h.moves())
        self.assertEqual(4, self.h.houses.m_Journal.Row(token.Row).Phase)

    def test_release_and_expiry_do_not_consume_stock(self):
        token = self.reserve()
        self.h.houses.HCReleasePicker(token)
        token = self.reserve()
        self.assertIsNotNone(token)
        self.h.world.now += 20.
        replacement = self.reserve()
        self.assertIsNotNone(replacement)
        self.assertFalse(self.h.houses.HCCommitReservation(token))
        self.assertEqual(0, self.h.houses.m_Journal.Row(replacement.Row).Phase)

    def test_restart_keeps_depletion_and_uncertain_move_is_not_replayed(self):
        token = self.reserve()
        self.h.world.now += 6.5
        self.actor.crash_after_move = True
        with self.assertRaises(supply.Crash): self.h.houses.HCCommitReservation(token)
        self.assertEqual(1, len(self.h.moves()))
        self.h.restart()
        install(self.h)
        self.assertIsNone(self.reserve())
        self.assertEqual(1, len(self.h.moves()))

    def test_invalid_authority_site_or_identity_never_binds_stock(self):
        self.assertIsNone(self.reserve(actor_id=''))
        self.current = False
        self.assertIsNone(self.reserve())
        self.current = True
        self.assertIsNone(self.h.houses.HCReservePicker(self.actor, self.house, 999, 'synthetic_party', self.authority))
        self.assertIsNone(self.h.houses.m_Journal)


if __name__ == '__main__':
    unittest.main()
