"""Round 4: authored cache hooks over explicit SYNTHETIC native inventory ports.
No engine persistence, visibility, navigation or runtime acceptance evidence.
"""
import json
import unittest
from copy import deepcopy
from types import SimpleNamespace as N
from tests.legacy.test_hc_pickers_survey import ROOT, SURVEY, to_ns, method
from tests.legacy.test_debug_map_layers import compile_authored
from tests.legacy.test_admin_test_kit import base_scope
from tests.legacy.test_group_server import EArray

CACHE = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIPickerCaches.c'
RULES = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAISiteRules.c'


def inventory_fixture(route=None):
    """Persistent synthetic world survives director recreation; no crate/bind stubs."""
    survey = to_ns(json.loads(SURVEY.read_text()))
    route = route or survey.Routes[0]
    for p in route.Waypoints:
        p.HCPosition = lambda p=p: (p.X,p.Y,p.Z)
    route.HCHomePoint=lambda:route.Waypoints[route.HomeIndex].HCPosition()
    route.HCSourcePoint=lambda:route.Waypoints[route.SourceIndex].HCPosition()
    world=EArray()
    def create(kind,at,flags):
        entries=EArray()
        crate=N(Name='crate-'+str(len(world)),Position=at,entries=entries,
                GetType=lambda:kind,IsKindOf=lambda k:k==kind)
        cargo=N(GetItemCount=lambda:len(entries),GetItem=lambda i:entries[i])
        def stock(kind):
            item=N(Name=crate.Name+'-'+str(len(entries)),IsTakeable=lambda:True,IsRuined=lambda:False)
            entries.append(item)
            return item
        crate.GetInventory=lambda:N(GetCargo=lambda:cargo,CreateEntityInCargo=stock)
        world.append(crate)
        return crate
    def scan(at,radius,objects,cargos):
        objects.extend(c for c in world if c.Position==at)
    game=N(IsServer=lambda:True,GetObjectsAtPosition3D=scan,CreateObjectEx=create)
    registry=N(PersistentId=lambda e:e.Name if e else '')
    scope=base_scope(GetGame=lambda:game,EntityAI=N(Cast=lambda e:e),ItemBase=N(Cast=lambda e:e),
                     HCSearchSupplyRegistry=registry,ECE_SETUP=1,ECE_CREATEPHYSICS=2,ECE_KEEPHEIGHT=4,
                     ECE_UPDATEPATHGRAPH=8,ECE_NOLIFETIME=16)
    port=N(Survey=survey,Actor=None,Home=None,Source=None,Item=None,LeaseId='',HCAccessible=lambda c:True,
           HCWalkRefusal=lambda:'')
    port.HCClear=lambda:[setattr(port,k,None) for k in ('Actor','Home','Source','Item')]
    for name in ('HCFindCrate','HCFirstItem','HCBindSurveyed'):
        run=method('HCScavengeInventory',name,fields=('Survey','Actor','Home','Source','Item','LeaseId'),
                   members=('HCClear','HCFindCrate','HCFirstItem','HCAccessible'),
                   GetGame=lambda:game,ItemBase=N(Cast=lambda e:e),HCSearchSupplyRegistry=registry)
        setattr(port,name,lambda *a,run=run:run(port,*a))
    return N(survey=survey,route=route,world=world,game=game,registry=registry,scope=scope,port=port)


class PickerCaches(unittest.TestCase):
    def fixture(self, inventory=None, persisted=()):
        self.assertTrue(CACHE.exists(),'HC-34 has no endpoint cache lifecycle extension')
        f=inventory or inventory_fixture()
        rows=EArray(deepcopy(persisted));saved=[];custody=[None]
        rules=N(CacheAction=lambda *a:compile_authored(RULES,'HCXAISiteRules','CacheAction',base_scope(),modded=False)(None,*a),
                RefillAt=lambda now,cooldown:now+cooldown,HCMaxCatalogRows=lambda:1024)
        director=N(m_Caches=N(Rows=rows),m_Policy=N(CacheClearRadius=300),m_Players=EArray(),
                   HCRefreshPlayers=lambda:None,CacheRow=lambda key:next((r for r in rows if r.SiteId==key),None),
                   SaveCaches=lambda:(saved.append(deepcopy(rows)),True)[1])
        scope=dict(f.scope, array=lambda:EArray(), this=director,HCXAISiteRules=rules,Print=lambda s:None,
                   HCXAICacheRow=lambda:N(SiteId='',State='',Lifecycle=0,ClassName='',SeededAt=0,
                       LootedAt=0,NextRefillAt=0,HCPickerCrateId=''),
                   HCPickers=N(Get=lambda:N(HCTrip=lambda:custody[0])))
        for name in ('HCPickerFindCache','HCPickerCacheNear','HCPickerCustody','HCPickerSeedCache','HCPickerCacheStep'):
            run=compile_authored(CACHE,'HCXAISiteDirector',name,scope,modded=True)
            setattr(director,name,lambda *a,run=run:run(director,*a))
        def step(now=1000):
            director.HCPickerCacheStep(f.survey,f.route,False,now)
            director.HCPickerCacheStep(f.survey,f.route,True,now)
        f.step=step;f.director=director;f.rows=rows;f.saved=saved;f.custody=custody
        return f

    def test_default_endpoints_seed_finite_stock_and_real_trip_binds(self):
        f=self.fixture();f.step()
        self.assertEqual(2,len(f.world));self.assertEqual([],f.world[0].entries)
        self.assertEqual(sum(x.Quantity for x in f.survey.CacheLoot),len(f.world[1].entries))
        from tests.legacy.test_hc_picker_starts import PickerStarts
        start=PickerStarts().fixture(inventory=f)
        self.assertEqual('',start.module.HCTryParty(start.identity,'lease:synthetic',start.actor,1000,0))
        self.assertIs(f.world[0],f.port.Home);self.assertIs(f.world[1],f.port.Source)
        self.assertEqual('leaving',start.state.Phase)

    def test_restart_adopts_identity_without_stock_replay_including_interrupted_seed(self):
        f=self.fixture();f.step();count=len(f.world[1].entries)
        persisted=deepcopy(f.saved[-1])
        # New director, restored JSON rows, same synthetic CE world. No runtime
        # handles survive on the director, matching native restart ownership.
        restarted=self.fixture(inventory=inventory_fixture(),persisted=persisted)
        restarted.world.extend(f.world)
        restarted.step(1001);restarted.step(1002)
        self.assertEqual(2,len(restarted.world))
        self.assertEqual(count,len(restarted.world[1].entries))
        persisted[1].State='seeding';persisted[1].HCPickerCrateId=''
        interrupted=self.fixture(inventory=inventory_fixture(),persisted=persisted)
        interrupted.world.extend(f.world)
        interrupted.step(1003);interrupted.step(1004)
        self.assertEqual(2,len(interrupted.world))
        self.assertEqual(count,len(interrupted.world[1].entries))
        self.assertEqual([c.Name for c in interrupted.world],[r.HCPickerCrateId for r in interrupted.rows])

    def test_empty_or_gone_source_waits_for_cooldown_and_clear_radius(self):
        for gone in (False,True):
            f=self.fixture();f.step();f.world[1].entries.clear()
            if gone:f.world.pop()
            f.step(2000);due=f.rows[1].NextRefillAt
            f.step(due-1);self.assertEqual(1 if gone else 2,len(f.world))
            player=N(GetIdentity=lambda:object(),GetPosition=f.route.HCSourcePoint)
            f.director.m_Players.append(player);f.step(due)
            self.assertEqual('looted',f.rows[1].State)
            f.director.m_Players.clear();f.step(due)
            self.assertEqual(2,len(f.world));self.assertGreater(len(f.world[1].entries),0)

    def test_custody_blocks_empty_or_gone_source_even_after_cooldown(self):
        for gone in (False,True):
            f=self.fixture();f.step();source=f.world[1];source.entries.clear()
            f.step(2000);due=f.rows[1].NextRefillAt
            if gone:f.world.pop()
            for phase in ('leaving','acquiring','returning','depositing','quarantined','lost'):
                f.custody[0]=N(m_State=N(RouteId=f.route.RouteId,Phase=phase,CargoOwner='actor'))
                f.step(due)
                self.assertEqual([],source.entries)
                self.assertEqual(1 if gone else 2,len(f.world))
            f.custody[0]=None;f.step(due)
            self.assertEqual(2,len(f.world))
            self.assertGreater(len(f.world[1].entries),0)

    def test_initial_creation_waits_for_players_at_either_endpoint(self):
        f=self.fixture()
        for point in (f.route.HCHomePoint,f.route.HCSourcePoint):
            f.director.m_Players[:]=[N(GetIdentity=lambda:object(),GetPosition=point)]
            f.step();self.assertEqual([],f.world)
        f.director.m_Players.clear();f.step();self.assertEqual(2,len(f.world))

    def test_crowded_native_scan_fails_closed_without_creating_duplicate_crate(self):
        f=self.fixture();f.step()
        f.survey.MaxScannedObjects=0
        f.rows.clear() # no journal after an interrupted profile provision
        f.step()
        self.assertEqual(2,len(f.world))

    def test_intent_save_failure_creates_nothing(self):
        f=self.fixture();f.director.SaveCaches=lambda:False
        f.step();f.step()
        self.assertEqual(0,len(f.world))

    def test_each_authored_route_has_empty_home_and_finite_source(self):
        for route in json.loads(SURVEY.read_text())['Routes']:
            f=self.fixture()
            route=to_ns(route)
            for p in route.Waypoints:p.HCPosition=lambda p=p:(p.X,p.Y,p.Z)
            route.HCHomePoint=lambda:route.Waypoints[route.HomeIndex].HCPosition()
            route.HCSourcePoint=lambda:route.Waypoints[route.SourceIndex].HCPosition()
            f.director.HCPickerCacheStep(f.survey,route,False,1000)
            f.director.HCPickerCacheStep(f.survey,route,True,1000)
            self.assertEqual([route.HCHomePoint(),route.HCSourcePoint()],[c.Position for c in f.world])
            self.assertEqual(0,len(f.world[0].entries))
            self.assertGreater(len(f.world[1].entries),0)
            self.assertLessEqual(len(f.world[1].entries),f.survey.CacheMaxItems)

    def test_authored_loot_matches_existing_cache_table_and_config_refuses_excess(self):
        from tests.legacy.test_hc_pickers_survey import SITES
        f=self.fixture()
        holdout=next(s for s in json.loads(SITES.read_text())['Sites'] if s['Kind']=='holdout')
        self.assertEqual(holdout['CacheLoot'],json.loads(SURVEY.read_text())['CacheLoot'])
        refusal=compile_authored(CACHE,'HCPickerSurvey','HCPickerCacheRefusal',base_scope(),modded=True,
            fields=('CacheClass','CacheCooldownSeconds','CacheMaxItems','MaxCargoScan','CacheMaxLootRows','CacheLoot'))
        self.assertEqual('',refusal(f.survey))
        f.survey.CacheMaxItems=1
        self.assertEqual('PICKER_CACHE_LIMITS_INVALID',refusal(f.survey))
        f.survey.CacheMaxItems=json.loads(SURVEY.read_text())['CacheMaxItems']
        f.survey.CacheLoot=None
        self.assertEqual('PICKER_CACHE_LOOT_INVALID',refusal(f.survey))
        f.survey.CacheClass=''
        self.assertEqual('PICKER_CACHE_CLASS_INVALID',refusal(f.survey))

    def test_invalid_cache_section_logs_one_named_refusal_and_does_no_endpoint_work(self):
        # #205: a zero-filled cache section used to look exactly like "no work yet".
        f=self.fixture();visits=[];lines=[];taken=[]
        f.survey.HCPickerCacheRefusal=lambda:'PICKER_CACHE_LIMITS_INVALID'
        f.director.m_HCPickerCacheCursor=0
        f.director.m_HCPickerCacheRefusal=''
        f.director.HCPickerCacheStep=lambda *a:visits.append(a)
        trip=N(m_IO=f.port,m_Ready=True)
        scope=dict(f.scope,this=f.director,HCPickers=N(Get=lambda:N(HCTrip=lambda:trip)),
            HCServer=N(HCTickWork=lambda:N(HCTake=lambda cost:taken.append(cost) or True)),
            ExpansionStatic=N(GetTimestamp=lambda utc:1000),Print=lines.append,
            **{'super':N(StepCache=lambda:None)})
        f.director.HCPickerCacheRefused=lambda reason:compile_authored(CACHE,'HCXAISiteDirector','HCPickerCacheRefused',scope,
            modded=True,fields=('m_HCPickerCacheRefusal',))(f.director,reason)
        run=compile_authored(CACHE,'HCXAISiteDirector','StepCache',scope,modded=True,fields=('m_HCPickerCacheCursor',))
        for _ in range(3):run(f.director)
        self.assertEqual(['[HC Pickers] caches refused reason=PICKER_CACHE_LIMITS_INVALID runtime=PENDING'],lines)
        self.assertEqual([],visits)
        self.assertEqual([],taken)

    def test_picker_readiness_degrades_on_an_invalid_cache_section(self):
        published=[];status=N(state='ready',reason='journal_and_survey_loaded')
        status.HCState=lambda:status.state;status.HCReason=lambda:status.reason
        status.HCPublish=lambda state,reason:published.append((state,reason))
        owner=N(m_Status=status,m_Survey=N(HCPickerCacheRefusal=lambda:'PICKER_CACHE_LOOT_INVALID'))
        run=compile_authored(CACHE,'HCPickers','HCPublishReadiness',
            dict(base_scope(),**{'super':N(HCPublishReadiness=lambda:None)}),modded=True,fields=('m_Status','m_Survey'))
        run(owner)
        self.assertEqual([('degraded','PICKER_CACHE_LOOT_INVALID')],published)
        owner.m_Survey=N(HCPickerCacheRefusal=lambda:'')
        run(owner)
        self.assertEqual(1,len(published))

    def test_existing_cache_step_visits_one_endpoint_with_shared_budget(self):
        f=self.fixture();visits=[];base=[];allowed=[False]
        f.survey.HCPickerCacheValid=lambda:True
        f.survey.HCPickerCacheRefusal=lambda:''
        f.director.m_HCPickerCacheCursor=0
        f.director.HCPickerCacheStep=lambda survey,route,source,now:visits.append((route.RouteId,source))
        trip=N(m_IO=f.port,m_Ready=True)
        run=compile_authored(CACHE,'HCXAISiteDirector','StepCache',dict(f.scope,
            this=f.director,HCPickers=N(Get=lambda:N(HCTrip=lambda:trip)),
            HCServer=N(HCTickWork=lambda:N(HCTake=lambda cost:allowed[0])),
            ExpansionStatic=N(GetTimestamp=lambda utc:1000),
            **{'super':N(StepCache=lambda:base.append('holdouts'))}),modded=True,fields=('m_HCPickerCacheCursor',))
        run(f.director);self.assertEqual([],visits)
        allowed[0]=True
        for _ in range(11):run(f.director)
        expected=[(r.RouteId,source) for r in f.survey.Routes for source in (False,True)]
        self.assertEqual(expected+[expected[0]],visits)
        self.assertEqual(12,len(base))

    def test_step_extends_existing_cache_scheduler_with_shared_budget(self):
        self.assertTrue(CACHE.exists(),'HC-34 has no endpoint cache lifecycle extension')
        text=CACHE.read_text()
        for token in ('override void StepCache()', 'super.StepCache()', 'HCServer.HCTickWork().HCTake(1)',
                      'HCXAISiteRules.CacheAction','this.CacheRow(', 'this.SaveCaches()'):
            self.assertIn(token,text)

if __name__=='__main__':unittest.main()
