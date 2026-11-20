"""Synthetic source execution; no DayZ navigation/targeting verdicts."""
import functools
import json
from pathlib import Path
from types import SimpleNamespace as N
import unittest
from tests.legacy.test_ecology_runtime import translated, environment
from tests.legacy.test_group_server import EArray
from tools.package import HCWildlife_habitats as habitats

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/Ecology/auditwild_Ecosystem.c'
MISSION = ROOT / 'mission/hollow-country/ecology/HCWildlife-providers.json'

class Ecosystem(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.exists(), 'seasonal wildlife consumer and bounded contact lifecycle missing')
        self.source = SOURCE.read_text().replace('HCWildlife', 'HCEventWildlife')
        self.env = environment()
        self.env['HCEventWildlifeContact'] = lambda: N(Attacker=None, Victim=None, StartedAt=0, EndsAt=0, RetryAt=0)
        self.env['HCEventWildlifeRoutes'] = N()
        for method in ('HCPhaseValid', 'HCSelect', 'HCValidRoute'):
            setattr(self.env['HCEventWildlifeRoutes'], method, translated(self.source, method, self.env, 'HCEventWildlifeRoutes'))

    def memory(self):
        owner = N(m_Config=N(MaxPairs=2, PairLifetimeMs=10, PairCooldownMs=20, MaxPairChecksPerTick=1), m_Contacts=EArray(), m_ContactCursor=0)
        for method in ('HCContact', 'HCSweep'):
            setattr(owner, method, functools.partial(translated(self.source, method, self.env, 'HCEventWildlifeInteractions', True), owner))
        return owner

    def test_actual_contact_deduplicates_without_extending_expiry_or_cooldown(self):
        owner = self.memory()
        a, b = object(), object()
        self.assertTrue(owner.HCContact(a,b,100))
        self.assertTrue(owner.HCContact(a,b,105))
        self.assertEqual((100,110,130), (owner.m_Contacts[0].StartedAt,owner.m_Contacts[0].EndsAt,owner.m_Contacts[0].RetryAt))
        self.assertFalse(owner.HCContact(a,b,110))
        self.assertFalse(owner.HCContact(a,b,129))
        self.assertTrue(owner.HCContact(a,b,130))
        self.assertEqual(140,owner.m_Contacts[0].EndsAt)

    def test_capacity_rejects_new_pairs_but_not_native_eligibility(self):
        owner = self.memory()
        self.assertTrue(owner.HCContact(object(),object(),100))
        self.assertTrue(owner.HCContact(object(),object(),100))
        self.assertFalse(owner.HCContact(object(),object(),100))
        provider=(ROOT/'mods/HollowCountry/scripts/4_World/Ecology/HCWildlifeProviders.c').read_text()
        self.assertIn('return true;', provider.split('static bool HCNativePermit',1)[1].split('static bool HCValid',1)[0])

    def test_sweep_resumes_with_a_bounded_slice_and_releases_expired_handles(self):
        owner = self.memory()
        owner.HCContact(object(),object(),100)
        owner.HCContact(object(),object(),100)
        owner.HCSweep(131)
        self.assertEqual(1,len(owner.m_Contacts))
        owner.HCSweep(131)
        self.assertEqual([],owner.m_Contacts)

    def test_invalid_contact_times_and_missing_handles_refuse(self):
        owner=self.memory()
        for a,b,now in ((None,object(),1),(object(),None,1),(object(),object(),-1),(object(),object(),2147483640)):
            self.assertFalse(owner.HCContact(a,b,now))
        a=object()
        self.assertFalse(owner.HCContact(a,a,1))

    def test_phase_selection_uses_only_active_phase_and_configured_route_order(self):
        routes=EArray([N(Species='deer',Phase=phase,Position=[phase+1,0,2],RadiusM=10,Role='Graze',Id=str(phase)) for phase in range(4)])
        select=self.env['HCEventWildlifeRoutes'].HCSelect
        for phase in range(4):
            self.assertIs(routes[phase],select(routes,'deer',phase))
        self.assertIsNone(select(routes,'deer',-1))
        self.assertIsNone(select(routes,'wolf',0))
        self.assertIsNone(select(routes,'deer',4))

    def test_route_validation_refuses_zero_filled_and_nonfinite_geometry(self):
        valid=self.env['HCEventWildlifeRoutes'].HCValidRoute
        route=N(Id='deer-spring',Species='Animal_CervusElaphus',Phase=0,Position=[10,0,20],RadiusM=10,Role='Graze')
        self.assertTrue(valid(route))
        for field,value in [('RadiusM',0),('RadiusM',float('nan')),('Phase',-1),('Role','Teleport'),('Species','PlayerBase')]:
            old=getattr(route,field);setattr(route,field,value)
            self.assertFalse(valid(route),(field,value));setattr(route,field,old)

    def test_shipped_policy_defaults_on_and_has_four_phase_native_route_data(self):
        config=json.loads(MISSION.read_text())
        self.assertTrue(config['SeasonalRoutesEnabled'])
        self.assertTrue(config['CluesEnabled'])
        self.assertTrue(config['InteractionObservationEnabled'])
        self.assertEqual(set(range(4)),{r['Phase'] for r in config['Routes']})
        for row in config['Routes']:
            self.assertTrue(self.env['HCEventWildlifeRoutes'].HCValidRoute(N(**row)))
            self.assertIn('territories.xml:',row['Source'])
        habitats.validate_ecosystem(config)

class ProviderIntegration(unittest.TestCase):
    def setUp(self):
        self.source=(ROOT/'mods/HollowCountry/scripts/4_World/Ecology/HCWildlifeProviders.c').read_text()
        self.source=self.source.replace('HCWildlife','HCEventWildlife').replace('HCUnitBudget','HCEventUnitBudget').replace('AnimalBase','HCEventAnimal')
        self.env=environment()
        self.trace=[]
        self.allowed=True
        self.config=N(CluesEnabled=True,InteractionObservationEnabled=True,ClueLifetimeSeconds=300)
        self.owner=N(m_Running=True,m_EcosystemOpen=True,m_LastNow=0,m_Config=self.config,
                     m_Interactions=N(HCContact=lambda *args:self.trace.append(('contact',args))))
        self.env.update(s_Owner=self.owner,
            HCEcologyNative=N(Authority=lambda:True),
            GetGame=lambda:N(GetTime=lambda:100),
            HCServer=N(HCTickWork=lambda:N(HCTakeFor=lambda *args:self.allowed)),
            HCEventUnitBudget=N(HC_WORK_INCIDENTS=17),
            HCEventAnimal=N(Cast=lambda entity: entity if entity and entity.animal else None),
            ZombieBase=N(Cast=lambda entity:entity if entity and entity.zombie else None),
            PlayerBase=N(Cast=lambda entity:entity if entity and not entity.animal else None),
            HCWorldIncidents=N(HCPublish=lambda kind,point,*args:self.trace.append((kind,tuple(point)))))
        self.victim=N(animal=True,IsPendingDeletion=lambda:False,GetPosition=lambda:[10,0,20])
        self.attacker=N(zombie=True,IsKindOf=lambda kind:False)
        self.damage=N(GetDamage=lambda zone,kind:1)

    def record(self):
        translated(self.source,'HCRecordDamage',self.env,'HCEventWildlifeProviders')(self.victim,self.attacker,self.damage,'synthetic-zone')

    def test_all_ecosystem_features_off_skip_shared_budget_entirely(self):
        self.config.SeasonalRoutesEnabled=False
        self.config.CluesEnabled=False
        self.config.InteractionObservationEnabled=False
        self.env['HCServer']=N(HCTickWork=lambda:self.fail('disabled ecosystem requested shared work'))
        translated(self.source,'HCEcosystemStep',self.env,'HCEventWildlifeProviders',True)(self.owner,100)

    def test_positive_blood_damage_records_historical_point_and_actual_contact(self):
        self.record()
        self.assertEqual('wildlife_blood',self.trace[0][0])
        self.assertEqual((10,0,20),self.trace[0][1])
        self.assertEqual('contact',self.trace[1][0])
        self.victim.GetPosition=lambda:[100,0,200]
        self.assertEqual((10,0,20),self.trace[0][1])

    def test_zero_blood_damage_never_invents_blood_clues(self):
        self.damage.GetDamage=lambda *args:0
        self.record()
        self.assertEqual(['contact'],[row[0] for row in self.trace])

    def test_feature_off_and_budget_denial_do_no_damage_or_position_queries(self):
        self.victim.GetPosition=lambda:self.fail('unexpected position query')
        self.damage.GetDamage=lambda *args:self.fail('unexpected damage query')
        self.config.CluesEnabled=False
        self.config.InteractionObservationEnabled=False
        self.record()
        self.assertEqual([],self.trace)
        self.config.CluesEnabled=True
        self.allowed=False
        self.record()
        self.assertEqual([],self.trace)
        self.allowed=True
        self.owner.m_Running=False
        self.record()
        self.assertEqual([],self.trace)

    def test_season_adapter_preserves_owner_unavailable_sentinel(self):
        source=SOURCE.read_text().replace('HCWildlife','HCEventWildlife').replace('ChernarusPlusData','HCEventClimate').replace('Mission mission','HCEventMission mission')
        self.env['GetGame']=lambda:N(GetMission=lambda:N(GetWorldData=lambda:N(HCSeasonPhaseCode=lambda:-1)))
        self.env['HCEventClimate']=N(Cast=lambda value:value)
        phase=translated(source,'HCPhase',self.env,'HCEventWildlifeRoutes')
        self.assertEqual(-1,phase())
        self.env['GetGame']=lambda:N(GetMission=lambda:None)
        phase=translated(source,'HCPhase',self.env,'HCEventWildlifeRoutes')
        self.assertEqual(-1,phase())

class NativeRouteAuthoring(unittest.TestCase):
    def test_extracts_only_real_native_zone_centres_with_source_lines(self):
        xml=b'<territory-type>\n<territory>\n<zone name="Graze" x="10" z="20" r="30"/>\n<zone name="Rest" x="40" z="50" r="60"/>\n</territory>\n</territory-type>'
        rows=habitats.seasonal_routes(xml,'env/red_deer_territories.xml','Animal_CervusElaphus',('Graze','Rest','Graze','Rest'))
        self.assertEqual(4,len(rows))
        self.assertEqual([10.,0.,20.],rows[0]['Position'])
        self.assertEqual('env/red_deer_territories.xml:3',rows[0]['Source'])
        with self.assertRaisesRegex(ValueError,'zone'):
            habitats.seasonal_routes(xml,'env/red_deer_territories.xml','Animal_CervusElaphus',('Water',)*4)

if __name__=='__main__': unittest.main()
