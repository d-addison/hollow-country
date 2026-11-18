"""#162: authored Enforce decisions with explicit synthetic engine collaborators.

These tests establish offline dispatch/diagnostic behavior only, never DayZ proof.
Stock placement verification is optional and reads the local map without copying it.
"""
import math
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest
import xml.etree.ElementTree as ET

from tests.unit import test_event_police as police
from tests.unit.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXWeaponGuard.c'
STOCK = Path('/mnt/d/HollowCountryLocal/local-v1-test-1/mpmissions/dayzOffline.chernarusplus/mapgrouppos.xml')


class BindingDiagnostics(unittest.TestCase):
    def setUp(self):
        self.f = police.PoliceBinding()
        self.f.setUp()
        self.f.e['Math'].Sqrt = math.sqrt

    def test_empty_infected_is_transient_and_names_the_real_class_and_constraint(self):
        f = self.f
        for _ in range(4):
            self.assertFalse(f.binder.Bind(f.observer, f.missions[7]))
        self.assertEqual(1, len(f.logs))
        for text in ('reason=no_candidate', 'constraint=no_infected_in_radius',
                     'wanted=ZombieBase', 'nearest_candidate_m=none_within_60', 'radius_m=60'):
            self.assertIn(text, f.logs[0])
        self.assertNotIn('Land_Village_PoliceStation', f.logs[0])
        f.objects = [f.ground_infected(5)]
        self.assertTrue(f.binder.Bind(f.observer, f.missions[7]))
        self.assertIn('bind recovered', f.logs[-1])

    def test_ineligible_infected_report_the_failed_constraint_and_measured_distance(self):
        f = self.f
        actor = f.ground_infected(5)
        actor.alive = False
        f.objects = [actor]
        self.assertFalse(f.binder.Bind(f.observer, f.missions[7]))
        self.assertIn('constraint=no_live_infected_in_radius', f.logs[-1])
        self.assertIn('nearest_candidate_m=5', f.logs[-1])
        actor.alive = True
        actor.HCEventEconomyCandidate = lambda: False
        self.assertFalse(f.binder.Bind(f.observer, f.missions[7]))
        self.assertIn('constraint=no_ce_infected_in_radius', f.logs[-1])
        self.assertEqual(2, len(f.logs), 'changed constraint logs once')

    def test_startup_identifies_out_of_range_static_anchor_once_without_disabling_retries(self):
        f = self.f
        mission = f.missions[6]
        anchor = police.runtime.Handle(kind=mission.AnchorClass,
            position=[mission.Source[0] + 20, mission.Source[1], mission.Source[2]])
        f.objects = [anchor]
        cfg = f.e['HCEventSettings']()
        cfg.Sites.Insert(f.site)
        for _ in range(2):
            f.binder.BindSites(f.observer, cfg, 'ChernarusPlus')
        lines = [line for line in f.logs if 'startup anchor unbindable' in line]
        self.assertEqual(1, len(lines))
        for text in ('coastal-police-source-6', 'constraint=anchor_outside_bind_radius',
                     'nearest_candidate_m=20', 'wanted=Land_Village_PoliceStation'):
            self.assertIn(text, lines[0])
        self.assertEqual(1, len([line for line in f.logs if 'startup anchors checked=1 unbindable=1' in line]))
        anchor.position = list(mission.Source)
        self.assertTrue(f.binder.Bind(f.observer, mission))

    def test_startup_empty_infected_does_not_declare_a_valid_anchor_impossible(self):
        f = self.f
        mission = f.missions[6]
        f.objects = [police.runtime.Handle(kind=mission.AnchorClass, position=list(mission.Source))]
        cfg = f.e['HCEventSettings']()
        cfg.Sites.Insert(f.site)
        f.binder.BindSites(f.observer, cfg, 'chernarusplus')
        self.assertIn('[HC Events] startup anchors checked=1 unbindable=0', f.logs)
        self.assertFalse(any('startup anchor unbindable' in line for line in f.logs))

    def test_unreadable_startup_query_is_unknown_rather_than_proof_of_bad_anchor(self):
        f = self.f
        f.binder.QueryBounded = staticmethod(lambda anchor, radius: None)
        cfg = f.e['HCEventSettings']()
        cfg.Sites.Insert(f.site)
        f.binder.BindSites(f.observer, cfg, 'chernarusplus')
        self.assertFalse(any('startup anchor unbindable' in line for line in f.logs))
        self.assertTrue(any('startup anchor unresolved' in line for line in f.logs))

    def test_unreadable_ground_still_identifies_the_wanted_class(self):
        f = self.f
        f.game.height = math.nan
        self.assertFalse(f.binder.Bind(f.observer, f.missions[7]))
        self.assertIn('wanted=ZombieBase', f.logs[-1])
        self.assertIn('nearest_candidate_m=unknown_query_refused', f.logs[-1])

    @unittest.skipUnless(STOCK.is_file(), 'stock mission not installed')
    def test_police_anchors_exactly_match_stock_map_class_and_position(self):
        groups = {(g.get('name'), tuple(map(float, g.get('pos').split())))
                  for g in ET.parse(STOCK).getroot().iter('group')}
        for site in self.f.e['HCEventSites'].ChernarusPlus():
            self.assertIn((site.AnchorClass, tuple(site.Position)), groups)


def weapon_fixture(ai=True, fsm=None, server=True):
    if not GUARD.exists():
        raise AssertionError('missing authored HCX missing-FSM guard')
    text = GUARD.read_text()
    # Language seams only: eAIBase local declaration, native super dispatch, casts.
    text = text.replace('eAIBase ai;', 'PlayerBase ai;')
    text = text.replace('e.m_player', 'e.player')
    text = text.replace('GetHierarchyRootPlayer()', 'self.GetHierarchyRootPlayer()')
    text = text.replace('GetType()', 'self.GetType()')
    text = text.replace('super.ProcessWeaponEvent(e)', 'engine.Event(e)')
    text = text.replace('super.ProcessWeaponAbortEvent(e)', 'engine.Abort(e)')
    calls, logs = [], []
    actor = N(is_ai=ai)
    event = N(player=actor)
    env = dict(eAIBase=N(Cast=lambda obj: obj if obj and obj.is_ai else None),
               GetGame=lambda: N(IsServer=lambda: server), Print=logs.append,
               engine=N(Event=lambda e: calls.append(('event', e)) or True,
                        Abort=lambda e: calls.append(('abort', e)) or True))
    cls = type('SyntheticWeapon', (), dict(m_fsm=fsm, m_HCXMissingFSMReported=False,
        GetHierarchyRootPlayer=lambda self: actor, GetType=lambda self: 'SyntheticBrokenWeapon'))
    for name in re.findall(r'^    (?:override |protected )?(?:bool|void) (\w+)\(', text, re.M):
        setattr(cls, name, translate(text, name, env, owner='SyntheticWeapon', member=True))
    return cls(), event, calls, logs


class WeaponGuard(unittest.TestCase):
    def test_missing_fsm_ai_never_dispatches_and_logs_once_across_both_paths(self):
        weapon, event, calls, logs = weapon_fixture()
        for _ in range(200):
            self.assertFalse(weapon.ProcessWeaponEvent(event))
            self.assertFalse(weapon.ProcessWeaponAbortEvent(event))
        self.assertEqual([], calls)
        self.assertEqual(1, len(logs))
        self.assertIn('missing_fsm', logs[0])
        self.assertIn('SyntheticBrokenWeapon', logs[0])

    def test_healthy_ai_and_human_dispatch_results_are_preserved(self):
        for ai, fsm in ((True, object()), (False, None), (False, object())):
            with self.subTest(ai=ai, fsm=bool(fsm)):
                weapon, event, calls, logs = weapon_fixture(ai, fsm)
                self.assertTrue(weapon.ProcessWeaponEvent(event))
                self.assertTrue(weapon.ProcessWeaponAbortEvent(event))
                self.assertEqual(['event', 'abort'], [c[0] for c in calls])
                self.assertEqual([], logs)

    def test_initialization_can_recover_without_replacing_or_moving_weapon(self):
        weapon, event, calls, logs = weapon_fixture()
        self.assertFalse(weapon.ProcessWeaponEvent(event))
        weapon.m_fsm = object()
        self.assertTrue(weapon.ProcessWeaponEvent(event))
        self.assertEqual(1, len(calls))
        self.assertEqual(1, len(logs))

    def test_ai_root_covers_events_without_a_player_and_clients_do_not_spam_logs(self):
        weapon, event, calls, logs = weapon_fixture(server=False)
        event.player = None
        self.assertFalse(weapon.ProcessWeaponEvent(event))
        self.assertFalse(weapon.ProcessWeaponAbortEvent(None))
        self.assertEqual([], calls)
        self.assertEqual([], logs)


if __name__ == '__main__':
    unittest.main()
