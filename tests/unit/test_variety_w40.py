"""#121 spec/plan/tasks: admit exposed native modes; repair role posture changes.

Explicit synthetic ports execute authored Enforce. No DayZ animation proof.
Plan: retain HC-14 cursor/LOD, native mind-state idle and existing wake services;
never turn an injured crawler into a standing actor. EnableInfectedVariety opts out.
"""
from types import SimpleNamespace as N
import unittest

from tests.unit.test_hc_postures import ADMISSION, NATIVE, bind
from tests.unit.test_infected_admission import Array
from tests.unit.test_event_runtime import translate as scalar


class VarietyW40(unittest.TestCase):
    def test_native_modes_admitted_but_custom_graphs_remain_unavailable(self):
        admit = scalar(ADMISSION.read_text(), 'HCCanEnter', {})
        for mode in ('native_stance_idle', 'native_mind_idle',
                     'native_crawler_idle', 'native_crawler_wake'):
            self.assertTrue(admit(mode), mode + ' must be admitted unverified')
        for mode in ('sit_wall', 'prone_sleep', 'riser', 'invented'):
            self.assertFalse(admit(mode))

    def test_native_admission_lines_do_not_report_unsupported_modes(self):
        policy = N()
        for name in ('HCCanEnter', 'HCPostureRefusal', 'HCLine'):
            setattr(policy, name, scalar(ADMISSION.read_text(), name,
                    dict(HCPostureAdmission=policy), 'HCPostureAdmission'))
        for mode in ('native_stance_idle', 'native_mind_idle', 'native_crawler_wake'):
            self.assertTrue(policy.HCPostureRefusal(mode).startswith('none_'),
                            'admitted native mode still reports unsupported')
            line = policy.HCLine(mode, 1)
            self.assertIn('state=on', line)
            self.assertIn('runtime=PENDING', line)
            self.assertNotIn('POSTURE_MODE_UNSUPPORTED', line)
        self.assertIn('wake=native_mind_state_unverified', policy.HCLine('native_stance_idle', 1))

    def test_role_change_invalidates_pose_once_and_same_role_keeps_it(self):
        actor = N(m_HCVarietyRole=2, m_HCVarietyPosture=True,
                  m_HCVarietyPlace='old')
        bind(NATIVE, actor, ('HCVarietyAssign',), {})
        actor.HCVarietyAssign(0, 'herd')
        self.assertFalse(actor.m_HCVarietyPosture,
                         'walker herd retained its previous runner stance')
        self.assertEqual((0, 'herd'), (actor.m_HCVarietyRole, actor.m_HCVarietyPlace))
        actor.m_HCVarietyPosture = True
        actor.HCVarietyAssign(0, 'new-place')
        self.assertTrue(actor.m_HCVarietyPosture, 'place refresh restarted native pose')

    def test_role_stances_cover_native_range_without_changing_mind_idle(self):
        policy = scalar(NATIVE.with_name('HCInfectedVarietyPolicy.c').read_text(),
                        'HCStanceForRole', {})
        self.assertEqual([0, 1, 3], [policy(role, False) for role in range(3)])
        self.assertEqual([2, 2, 2], [policy(role, True) for role in range(3)])
        # No invented idle enum: vanilla HandleMindStateChange owns 0/1/2.
        source = NATIVE.read_text().split('override bool ModCommandHandlerBefore', 1)[1]
        self.assertNotIn('move.SetIdleState(0)', source,
                         'role assignment must not overwrite native mind-state idle')

    def test_native_handler_reapplies_role_only_on_a_calm_move_command(self):
        stances = []
        mind = [0]
        controller = N(GetMindState=lambda: mind[0], GetMovementSpeed=lambda: 0)
        actor = N(m_HCVarietyRole=2, m_HCVarietyPosture=False,
                  m_HCVarietySpeed=False, m_HCVarietyDormant=False,
                  m_StanceVariation=-1, m_HCVarietyPlace='place',
                  GetInputController=lambda: controller, IsAlive=lambda: True,
                  IsBeingBackstabbed=lambda: False, IsCrawling=lambda: False,
                  IsZombieMilitary=lambda: False,
                  HCVarietyWake=lambda: self.fail('standing actor was woken'),
                  HCVarietyRelease=lambda: self.fail('active actor was released'),
                  GetCommand_Move=lambda: N(SetStanceVariation=stances.append,
                     SetIdleState=lambda idle: self.fail('native mind idle overwritten')))
        text = NATIVE.with_name('HCInfectedVarietyPolicy.c').read_text()
        policy = N(**{name: scalar(text, name, {}) for name in
                     ('HCStanceForRole', 'MovementLimit')})
        bound = ('GetInputController', 'IsAlive', 'IsBeingBackstabbed',
                 'IsCrawling', 'IsZombieMilitary', 'GetCommand_Move',
                 'HCVarietyWake', 'HCVarietyRelease')
        bind(NATIVE, actor, ('HCVarietyAssign', 'ModCommandHandlerBefore'),
             dict(GetGame=lambda: N(IsServer=lambda: True),
                  super=N(ModCommandHandlerBefore=lambda *args: False),
                  HCInfectedVarietyModule=N(VarietyActive=lambda: True),
                  HCInfectedVarietyPolicy=policy,
                  HCPostureAdmission=N(HCCanEnter=scalar(ADMISSION.read_text(), 'HCCanEnter', {})),
                  DayZInfectedConstants=N(COMMANDID_MOVE=0, MINDSTATE_CALM=0,
                                         MINDSTATE_FIGHT=4)), bound=bound)
        actor.ModCommandHandlerBefore(.1, 1, False)  # attack/vault owns its command
        self.assertEqual([], stances)
        actor.ModCommandHandlerBefore(.1, 0, False)
        actor.ModCommandHandlerBefore(.1, 0, False)
        self.assertEqual([3], stances)
        actor.HCVarietyAssign(0, 'herd')
        mind[0] = 4
        actor.ModCommandHandlerBefore(.1, 0, False)
        self.assertEqual([3], stances)
        mind[0] = 0
        actor.ModCommandHandlerBefore(.1, 0, False)
        self.assertEqual([3, 0], stances)

    def test_existing_crawler_cluster_uses_room_catalog_without_relocation(self):
        queries = []
        room = [False]
        entity = N(GetPosition=lambda: [100., 2., 100.])
        def room_order(position, budget, points):
            queries.append((position, budget))
            if room[0]:
                points.Insert([101., 2., 101.])
        owner = N()
        self.assertIn('bool HCVarietyPlaceFits(', NATIVE.with_name('HCInfectedVarietyModule.c').read_text(),
                      'room context cannot currently admit an existing crawler cluster')
        bind(NATIVE.with_name('HCInfectedVarietyModule.c'), owner,
             ('HCVarietyPlaceFits',),
             dict(TVectorArray=Array,
                  HCInfectedRoomCatalog=N(BuildProductionOrder=room_order)),
             bound=('HCVarietyNearCorpse',))
        self.assertFalse(owner.HCVarietyPlaceFits(entity))
        room[0] = True
        self.assertTrue(owner.HCVarietyPlaceFits(entity),
                        'a crawler already inside a catalog room was excluded')
        self.assertEqual(2, len(queries))
        self.assertTrue(all(budget == 1 for _, budget in queries))


if __name__ == '__main__':
    unittest.main()
