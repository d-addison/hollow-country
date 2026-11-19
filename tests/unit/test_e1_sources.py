"""E1 source receipts: execute authored hooks using explicit synthetic handles.

Spec/plan/task: retain native/provider behavior, publish only successful physical
source transitions at their own coordinates through the existing bounded registry.
No fixture establishes DayZ lifecycle, audibility, visibility or replication.
"""
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_e1_incidents import bind, registry, looker
from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCIncidentEmissions.c'
RAID = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCIncidentRaid.c'


def hook(cls, name, receiver=None, parent=None, server=True, path=SOURCE, **extra):
    calls = []
    env = dict(receiver=receiver or N(), super=parent or N(), GetGame=lambda: N(IsServer=lambda: server),
               HCIncidentEmissions=N(HCPublish=lambda *args: calls.append(args)),
               HCEventCode=N(OK=0), Print=lambda line: None)
    env.update(extra)
    source = path.read_text().replace('override ', '').replace('protected ', '')
    source = re.sub(r'\bm_(\w+)', r'receiver.m_\1', source)
    # Inherited native methods are explicit fixture ports, never inferred APIs.
    for method in ('GetPosition', 'IsKindOf'):
        source = re.sub(r'(?<![.\w])' + method + r'\(', 'receiver.' + method + '(', source)
    obj = bind(source, cls, env, only=[name])
    return getattr(obj, name), calls


class SourceBehavior(unittest.TestCase):
    def test_source_adapter_names_have_hc_prefix(self):
        self.assertTrue((SOURCE.parent / 'HCIncidentEmissions.c').is_file())
        self.assertTrue((RAID.parent / 'HCIncidentRaid.c').is_file())
        self.assertTrue((RAID.parent / 'HCIncidentConflict.c').is_file())
        self.assertIn('class HCIncidentEmissions', SOURCE.read_text())

    def test_repeated_shots_remain_audible_after_original_sound_window(self):
        clock = [1000]
        reg = registry()
        env = dict(GetGame=lambda: N(IsServer=lambda: True), Print=lambda line: None,
                   HCWorldIncidents=N(HCPublish=lambda kind, pos, radius, life, anchor:
                                      reg.HCAdd(kind, pos, radius, life, anchor, clock[0]),
                                      HCGet=lambda: reg, HCNowSeconds=lambda: clock[0]))
        adapter = bind(SOURCE.read_text().replace('protected ', ''), 'HCIncidentEmissions', env, only=['HCPublish'])
        env['HCIncidentEmissions'] = N(s_Logged=False)
        fire, _ = hook('Weapon_Base', 'EEFired',
                       N(GetPosition=lambda: [100, 0, 100], IsKindOf=lambda kind: False),
                       N(EEFired=lambda *args: None), HCIncidentEmissions=adapter)
        fire(0, 0, 'synthetic-ammo')
        row = reg.HCRowAt(0)
        listener = looker([200, 0, 100])
        clock[0] = 1121
        self.assertFalse(reg.HCPerceives(row, listener, clock[0]))
        fire(0, 0, 'synthetic-ammo')
        self.assertEqual(1, reg.HCCount())
        self.assertTrue(reg.HCPerceives(row, listener, clock[0]))
        self.assertFalse(reg.HCPerceives(row, listener, 1242), 'silence still closes the refreshed window')
        # Other physical publications do not repeatedly renew their sound.
        adapter.HCPublish('horde', [900, 0, 900], None)
        clock[0] = 1242
        adapter.HCPublish('horde', [900, 0, 900], None)
        self.assertEqual(1121, reg.HCRowAt(1).StartAt)

    def test_smoke_publishes_at_native_work_start_after_super(self):
        order = []
        pos = [421, 8, 915]
        run, calls = hook('SmokeGrenadeBase', 'OnWorkStart', N(GetPosition=lambda: pos),
                          N(OnWorkStart=lambda: order.append('native')))
        run()
        self.assertEqual(['native'], order)
        self.assertEqual([('signal_smoke', pos, None)], calls)
        run, calls = hook('SmokeGrenadeBase', 'OnWorkStart', N(GetPosition=lambda: pos),
                          N(OnWorkStart=lambda: None), server=False)
        run()
        self.assertEqual([], calls)

    def test_event_success_publishes_source_and_failed_activation_never_does(self):
        mission = N(Source=[701, 19, 405])
        for result in (0, 3):
            run, calls = hook('HCEventRuntime', 'Announce', parent=N(Announce=lambda *args: result))
            self.assertEqual(result, run(mission, N()))
            self.assertEqual([('scene', mission.Source, None)] if result == 0 else [], calls)

    def test_pack_success_publishes_member_location_never_route_destination(self):
        pos = [202, 7, 903]
        actors = EArray([N(InfectedEntity=N(GetPosition=lambda: pos))])
        for success, search in ((True, False), (False, False), (True, True)):
            run, calls = hook('HCNativeInfectedPack', 'Start', parent=N(Start=lambda *args: success))
            self.assertEqual(success, run(actors, [9000, 0, 9000], search, 10, 30))
            self.assertEqual([('horde', pos, None)] if success and not search else [], calls)

    def test_warning_requires_accepted_reservation_and_uses_seen_point(self):
        camp = N(Position=[8000, 0, 8000])
        point = [512, 8, 204]
        for reserved, match in ((True, True), (False, True), (True, False)):
            run, calls = hook('HCXAIBaseRaid', 'HCWarned',
                              N(m_Reserved=reserved, m_Camp=camp if match else None, m_Point=point),
                              N(HCWarned=lambda *args: None), path=RAID)
            run(camp, 10)
            self.assertEqual([('raid', point, None)] if reserved and match else [], calls)

    def test_native_fired_hook_is_server_only_and_excludes_archery(self):
        point = [100, 11, 900]
        for server, bow in ((True, False), (False, False), (True, True)):
            order = []
            run, calls = hook('Weapon_Base', 'EEFired',
                              N(GetPosition=lambda: point, IsKindOf=lambda kind: bow),
                              N(EEFired=lambda *args: order.append('native')), server=server)
            run(0, 0, 'synthetic-ammo')
            self.assertEqual(['native'], order)
            self.assertEqual([('gunfire', point, None)] if server and not bow else [], calls)

    def test_adapter_reuses_registry_dedup_caps_and_operator_off(self):
        reg = registry(maxima=2)
        logs = []
        env = dict(GetGame=lambda: N(IsServer=lambda: True), Print=logs.append,
                   HCWorldIncidents=N(HCPublish=lambda kind, pos, radius, life, anchor:
                                      reg.HCAdd(kind, pos, radius, life, anchor, 1000),
                                      HCGet=lambda: reg, HCNowSeconds=lambda: 1000))
        source = SOURCE.read_text().replace('protected ', '')
        adapter = bind(source, 'HCIncidentEmissions', env, only=['HCPublish'])
        env['HCIncidentEmissions'] = N(s_Logged=False)
        adapter.HCPublish('gunfire', [10, 0, 10], None)
        adapter.HCPublish('gunfire', [10, 0, 10], None)
        self.assertEqual(1, reg.HCCount(), 'same-position shots share a registry row')
        adapter.HCPublish('horde', [900, 0, 900], None)
        adapter.HCPublish('scene', [500, 0, 500], None)
        self.assertEqual(2, reg.HCCount())
        self.assertEqual(2, len(logs))
        self.assertIn('E1_AIRDROP_OBSERVER_PENDING', logs[1])
        self.assertIn('runtime=PENDING', logs[0])
        retained = [(row.Id, row.Kind, row.Position) for row in reg.m_Rows]
        reg.m_Off = True
        adapter.HCPublish('raid', [300, 0, 300], None)
        self.assertEqual(2, reg.HCCount())
        self.assertEqual(retained, [(row.Id, row.Kind, row.Position) for row in reg.m_Rows])
        env['GetGame'] = lambda: None
        adapter.HCPublish('raid', [300, 0, 300], None)
        self.assertEqual(retained, [(row.Id, row.Kind, row.Position) for row in reg.m_Rows])
        env['GetGame'] = lambda: N(IsServer=lambda: False)
        adapter.HCPublish('raid', [300, 0, 300], None)
        self.assertEqual(retained, [(row.Id, row.Kind, row.Position) for row in reg.m_Rows])

    def test_faction_observation_publishes_once_per_seen_combat_transition(self):
        source = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCIncidentConflict.c'
        for initial, observed in ((False, True), (False, False), (True, True)):
            pos = [654, 9, 321]
            actor = N(GetPosition=lambda: pos)
            group = N(Count=lambda: 1, GetMember=lambda index: actor)
            receiver = N(m_SeenCombat=initial, m_Groups=EArray([group]))
            def native(encounter):
                receiver.m_SeenCombat = observed
                return False
            run, calls = hook('HCXFactionCombatAdapter', 'HCDisengaged', receiver,
                              N(HCDisengaged=native), path=source)
            self.assertFalse(run('synthetic-encounter'))
            self.assertEqual([('scene', pos, None)] if not initial and observed else [], calls)
