"""Synthetic observer/raycast ports execute source; no DayZ visibility proof."""
import re
import unittest
from types import SimpleNamespace as NS
from tests.unit.test_ecology_runtime import ROOT, translated, EArray
from tests.unit.test_v1_ecology_migration import setup

NATIVE = ROOT / '4_World/Ecology/HCEcologyMigrationNative.c'


class MigrationSightBehavior(unittest.TestCase):
    def setUp(self):
        self.e = setup(); self.players = EArray(); self.rays = []; self.blocked = True
        self.authority = True
        self.e['HCEcologyNative'] = NS(Authority=lambda: self.authority)
        self.e['GetGame'] = lambda: NS(GetPlayers=lambda out: out.extend(self.players))
        self.e['PlayerBase'] = NS(Cast=lambda obj: obj)
        self.e['Vector'] = lambda x, y, z: [x, y, z]
        # Enforce vector arithmetic and native out vectors are syntax-only ports.
        class Vec(list):
            def __add__(self, other): return Vec(a+b for a,b in zip(self,other))
        self.vec = Vec
        self.e['Vector'] = lambda x, y, z: Vec([x,y,z])
        self.e['EArray'] = EArray
        self.e['HCEcologyObjects'] = EArray
        def ray(start, end, contact, normal, component, hits, with_obj, ignore, sorted_hits, ground, kind):
            self.rays.append((list(start), list(end), ignore, kind))
            contact[:] = [(a+b)/2 for a,b in zip(start,end)]
            if self.blocked == 'target':
                hits.Insert(self.target); return True
            if self.blocked == 'unknown':
                contact[:] = [float('nan'),0.,0.]; return True
            return self.blocked
        self.e['DayZPhysics'] = NS(RaycastRV=ray)
        self.e['ObjIntersectView'] = 0; self.e['ObjIntersectFire'] = 1
        source = NATIVE.read_text().replace('HCInfectedActor ', 'HCEcologyActor ')
        source = source.replace('HCInfectedClue ', 'HCEcologyClue ')
        source = source.replace('set<Object> hits = new set<Object>;', 'HCEcologyObjects hits = new HCEcologyObjects;')
        self.native = NS(); self.e['HCEcologyMigrationNative'] = self.native
        for name in ('RayBlocked', 'PointHidden', 'Unobserved'):
            setattr(self.native, name, translated(source, name, self.e, 'HCEcologyMigrationNative'))
        self.target = self.handle([0.,0.,0.])
        self.members = EArray([NS(InfectedEntity=self.target)])
        self.clue = NS(Origin=Vec([5.,0.,0.]))

    def handle(self, position):
        return NS(GetPosition=lambda: self.vec(position), IsAlive=lambda: True, GetParent=lambda: None,
                  GetBoneIndexByName=lambda name: 0,
                  GetBonePositionWS=lambda index: self.vec([position[0],position[1]+1.6,position[2]]))

    def test_all_players_and_members_checked_no_facing_or_distance_exemption(self):
        self.players.extend([self.handle([1000.,0.,0.]), self.handle([2000.,0.,0.])])
        self.members.Insert(NS(InfectedEntity=self.handle([1.,0.,0.])))
        self.assertTrue(self.native.Unobserved(self.members, self.clue))
        self.assertEqual(36, len(self.rays))  # 2 players * (2 members + endpoint) * 3 heights * 2 modes
        self.blocked = False
        self.assertFalse(self.native.Unobserved(self.members, self.clue))
        self.blocked = 'target'
        self.assertFalse(self.native.Unobserved(self.members, self.clue))
        self.blocked = 'unknown'
        self.assertFalse(self.native.Unobserved(self.members, self.clue))

    def test_observer_inside_a_vehicle_is_never_proof_of_cover(self):
        # The observer's own vehicle is the nearest ray contact, so blocked rays prove nothing.
        driver = self.handle([1000.,0.,0.])
        driver.GetParent = lambda: NS(Kind='car')
        self.players[:] = [driver]
        self.assertFalse(self.native.Unobserved(self.members, self.clue))

    def test_proximity_veto_even_through_cover_and_at_destination(self):
        for player, destination in (([100.,0.,0.],[5.,0.,0.]), ([500.,0.,0.],[500.,0.,0.])):
            self.players[:] = [self.handle(player)]
            self.clue.Origin = self.vec(destination)
            self.rays.clear()
            self.assertFalse(self.native.Unobserved(self.members, self.clue))

    def test_later_observer_or_member_can_veto(self):
        far = self.handle([1000.,0.,0.]); near = self.handle([0.,0.,0.])
        self.players[:] = [far, near]
        self.assertFalse(self.native.Unobserved(self.members, self.clue))
        self.players[:] = [far]
        self.members.Insert(NS(InfectedEntity=self.handle([1000.,0.,0.])))
        self.assertFalse(self.native.Unobserved(self.members, self.clue))

    def test_empty_roster_allowed_but_overflow_or_unknown_data_fail_closed(self):
        self.assertTrue(self.native.Unobserved(self.members, self.clue))
        self.players[:] = [self.handle([1000.,0.,0.])] * 33
        self.assertFalse(self.native.Unobserved(self.members, self.clue))
        self.assertEqual([], self.rays)
        for observer in (None, self.handle([float('nan'),0.,0.])):
            self.players[:] = [observer]
            self.assertFalse(self.native.Unobserved(self.members, self.clue))
        self.players.clear(); self.authority = False
        self.assertFalse(self.native.Unobserved(self.members, self.clue))
        self.authority = True
        self.assertFalse(self.native.Unobserved(EArray(), self.clue))
        self.members[0].InfectedEntity = None
        self.assertFalse(self.native.Unobserved(self.members, self.clue))


class MigrationStartBehavior(unittest.TestCase):
    def test_start_build_authority_and_marker_veto_before_journal_io(self):
        env = setup(); opened = []; created = []; gates = dict(build=True, authority=True, admitted=True)
        env['HCEcologyNative'] = NS(Authority=lambda:gates['authority'])
        env['HCEcologyMigrationQualification'] = NS(Admitted=lambda:gates['admitted'])
        env['HCEcologyMigrationNative'] = NS(BuildSupported=lambda:gates['build'],
            CurrentWorld=lambda:'synthetic-world', Utc=lambda:1800000000)
        def service():
            created.append(True)
            return NS(m_Fault=False, m_Store=None, m_State=None, m_World='')
        env['HCEcologyService'] = service
        env['HCEcologyMigrationStore'] = lambda:NS(Open=lambda world, now: opened.append(world) or NS(Schedules=EArray()))
        source = (ROOT/'4_World/Ecology/HCEcologyMigration.c').read_text()
        source = source.replace('HCEcologyMigration service = new HCEcologyMigration;',
                                'HCEcologyService service = new HCEcologyService;')
        source = re.sub(r'\bs_Service\b', 'HCEcologyMigration.s_Service', source)
        facade = NS(s_Service=None); env['HCEcologyMigration'] = facade
        start = translated(source, 'Start', env, 'HCEcologyMigration')
        for key in gates:
            gates[key] = False
            self.assertFalse(start('SYNTHETIC-WORLD'), key)
            self.assertEqual([], created+opened)
            gates[key] = True
        self.assertTrue(start('SYNTHETIC-WORLD'))
        self.assertEqual(['synthetic-world'], opened)
        self.assertEqual('synthetic-world', facade.s_Service.m_World)

    def test_live_build_uses_exact_shared_matcher(self):
        env = setup(); current = ['1.30.164289.70']
        env['HCEcologyNative'] = NS(Authority=lambda:True)
        env['SyntheticVersion'] = lambda:current[0]
        # GetVersion is an out string; only its syntax is replaced here.
        source = NATIVE.read_text().replace('GetGame().GetVersion(build);', 'build = SyntheticVersion();')
        fn = translated(source, 'BuildSupported', env, 'HCEcologyMigrationNative')
        for version in ('1.30.164289', '1.30.164289.70', '1.30.164289.700', ''):
            current[0] = version
            self.assertEqual(env['HCBuildIdentity'].Matches(version), fn())


class EcologyDispositionBehavior(unittest.TestCase):
    def test_each_disposition_logged_once_with_its_reason(self):
        env = setup(); logs = []; env['Print'] = logs.append
        source = (ROOT/'4_World/Ecology/HCEcologyRuntimeModule.c').read_text()
        source = re.sub(r'\bs_Reported\b', 'HCEcologyDisposition.s_Reported', source)
        env['HCEcologyDisposition'] = NS(s_Reported=False)
        report = translated(source, 'Report', env, 'HCEcologyDisposition')
        report(); first = logs[:]; report()
        self.assertEqual(first, logs)
        for disposition in ('observation_path=available', 'coverage=partial', 'feeding=unsupported',
                            'drinking=unsupported', 'migration=unsupported'):
            matching = [line for line in logs if disposition in line]
            self.assertEqual(1, len(matching), disposition)
            self.assertIn('reason=', matching[0])
