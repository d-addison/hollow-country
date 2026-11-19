"""Round 3 HC-34: execute authored seeding over explicit SYNTHETIC DTO/JSON ports.
No DayZ boot, spawn, pathfinding, real inventory or persistence evidence.
"""
import json
import re
import unittest
from copy import deepcopy
from types import SimpleNamespace as N
from tests.unit.test_hc_pickers_survey import ROOT, SURVEY, SITES, to_ns, method
from tests.unit.test_debug_map_layers import compile_authored
from tests.unit.test_admin_test_kit import base_scope
from tests.unit.test_group_server import EArray
from tests.unit.test_hc_scavenge import bind

SEED = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIPickerSeed.c'
DATA = ROOT / 'mods/HollowCountry/scripts/3_Game/World/HCWorldData.c'
WORLD = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCWorldModule.c'
MATERIALIZER = WORLD.with_name('HCWorldMaterializer.c')
FACTIONS = SEED.with_name('HCXFactions.c')


def seeded_fixture(cap=24, existing=()):
    """Fresh() + seed + real validation/insert; JSON roundtrip is a synthetic port."""
    data = N(Meta=N(), Parties=EArray(), Places=EArray(), Factions=EArray())
    data.Place = lambda key: next((p for p in data.Places if p.Id == key), None)
    data.Faction = lambda key: next((f for f in data.Factions if f.Id == key), None)
    catalog = N(Town=lambda d, key, name, pos: d.Places.append(N(Id=key, Position=pos)),
                ExtendPlaces=lambda d: None)
    fresh = compile_authored(DATA, 'HCWorldData', 'Fresh', base_scope(
        HCWorldData=lambda: data, HCWorldLimits=N(SCHEMA=1),
        HCBuildIdentity=N(Canonical=lambda:'synthetic-build'),
        HCWorldFactionCatalog=N(Populate=lambda d: d.Factions.extend(
            N(Id=key,Strength=32) for key in ('locals','volunteers','scavengers','raiders','travellers')))),
        modded=False, members=('Town','ExtendPlaces'))
    fresh(catalog, 1000)
    limits=N(SIZE_CEILING=6, Get=lambda:N(MaxParties=cap,MaxMaterialized=4,MaxHoldouts=24), Maximum=lambda kind:6)
    rules=N(Token=lambda key: bool(key) and len(key)<=96,
            Strings=lambda rows,maximum: rows is not None and len(rows)<=maximum,
            ROUTE=8,CARRY=8,Admit=lambda count,maximum,label: count<maximum)
    bind(DATA.read_text(),'HCWorldData',data,('PartyValid','InsertParty'),
         dict(HCAILimits=limits,HCWorldLimits=rules,Parties=data.Parties))
    data.Parties.extend(deepcopy(existing))
    world=N(m_Data=data,m_Running=True,m_Dirty=False,m_HCPickerSurvey=None)
    # Syntax adapter for native out parameters only; all AddParty decisions execute.
    source=WORLD.read_text()
    source=source.replace('JsonFileLoader<HCWorldParty>.MakeData(row, text, error)', 'SyntheticMake(row)')
    source=source.replace('JsonFileLoader<HCWorldParty>.LoadData(text, copy, error)', 'SyntheticLoad()')
    source=source.replace('HCWorldParty copy;', 'HCWorldParty copy = SyntheticCopy(row);')
    bind(source,'HCWorldModule',world,('AddParty',),dict(SyntheticMake=lambda row:True,
        SyntheticLoad=lambda:True,SyntheticCopy=deepcopy))
    survey=to_ns(json.loads(SURVEY.read_text()))
    policy=to_ns(json.loads(SITES.read_text()))
    for route in survey.Routes:
        route.HCHomePoint=lambda r=route:tuple(vars(r.Waypoints[r.HomeIndex])[key] for key in ('X','Y','Z'))
    survey.HCFind=lambda key:next((r for r in survey.Routes if r.RouteId==key),None)
    faction=compile_authored(FACTIONS,'HCXFactions','HCWorldId',base_scope(),modded=False)
    logs=[]
    scope=base_scope(this=world, HCWorldParty=lambda:N(Route=EArray(),Carry=EArray(),Materialized=False,
        Edge=0,Progress=0,DailyTransfers=0,TransferDay=0,LastMoved=0),
        HCXFactions=N(HCWorldId=lambda key:faction(None,key)),Print=logs.append,
        HCXAISiteRules=N(HCMaxCatalogRows=lambda:128))
    assert SEED.exists(), 'HC-34 default boot has no authored party seeder'
    for site in policy.Sites:
        site.Waypoints=EArray(tuple(p) for p in site.Waypoints)
    seed=compile_authored(SEED,'HCWorldModule','HCSeedPickerParties',scope,modded=True,members=('AddParty',))
    world.HCSeedPickerParties=lambda:seed(world,survey,policy)
    world.HCSeedPickerParties()
    return N(world=world,data=data,survey=survey,policy=policy,logs=logs,limits=limits)


def proposal_fixture(f, index=0):
    identity_path=ROOT / 'mods/HollowCountry/scripts/3_Game/World/HCAIPartyIdentity.c'
    def dto():
        identity=N()
        for name in ('HCPartyId','HCCampId','HCHomeId','HCRouteId','HCCargoId','HCGeneration'):
            getter=compile_authored(identity_path,'HCAIPartyIdentity',name,base_scope(),modded=False)
            setattr(identity,name,lambda getter=getter:getter(identity))
        return identity
    valid=compile_authored(identity_path,'HCAIPartyIdentity','HCValid',base_scope(
        HCWorldLimits=N(Token=lambda key:bool(key) and len(key)<=96)),modded=False)
    factory=N(HCValid=lambda identity:valid(None,identity))
    create=compile_authored(identity_path,'HCAIPartyIdentity','HCCreate',base_scope(
        HCAIPartyIdentity=dto),modded=False,members=('HCValid',))
    run=compile_authored(MATERIALIZER,'HCWorldModule','MaterializerRow',base_scope(
        HCWorldProposal=N,HCAILimits=f.limits,
        HCAIPartyIdentity=N(HCCreate=lambda *args:create(factory,*args))),
        modded=True,members=('Epoch',))
    f.world.Epoch=lambda:1000
    row=run(f.world,24+index)
    mapped=compile_authored(SEED,'HCWorldModule','MaterializerRow',base_scope(
        **{'super':N(MaterializerRow=lambda index:row)}),modded=True)
    return mapped(f.world,24+index)


def admitted_fixture(proposal, patrol):
    """Execute bridge Offer -> AdmitTransient -> Spawned with synthetic native ports.

    The provider's spawn callback is explicitly simulated; it proves no engine
    spawn. The transient flag and lease binding come from production admission.
    """
    from tests.unit.test_expansion_ai_adapter import Authored
    class Vec(tuple):
        def __add__(self, other):return Vec(a+b for a,b in zip(self,other))
    sites=SEED.with_name('HCXAISites.c')
    director=N(m_Phase='run',m_Policy=object(),m_States=EArray(),
        BudgetProblem=lambda *a:'',MemberProblemFor=lambda pos:'',SaveOwned=lambda:None)
    faction=N(IsInvincible=lambda:False,IsObserver=lambda:False,IsPassive=lambda:False,
        HasUnlimitedStamina=lambda:False,GetMeleeDamageMultiplier=lambda:1,GetMeleeYeetForce=lambda:0)
    callbacks=[]
    env=dict(HCAILimits=N(SIZE_CEILING=6), HCXAIQualification=N(
        EncountersEnabled=lambda:True,ProviderProblem=lambda:''),
        HCXAIRules=N(Token=lambda key:True,PositionValid=lambda *a:True),
        eAIFaction=N(Create=lambda key:faction),FileExist=lambda path:True,
        EXPANSION_LOADOUT_FOLDER='synthetic/',
        HCXAISite=lambda:N(Waypoints=EArray()),
        HCXAISiteState=lambda:N(Materialized=False,Completed=False),
        GetGame=lambda:N(GetTime=lambda:1000),Vector=lambda *p:Vec(p),Print=lambda line:None,
        Math=N(Round=round),HCXMaterializerBridge=N(SiteSpawned=lambda:callbacks.append('spawned')))
    authored=Authored(sites.read_text(),env)
    director.AdmitTransient=lambda lease,faction,pos,count,reason:authored.call(
        'AdmitTransient',director,lease,faction,Vec(pos),count,reason)
    bridge=Authored(SEED.with_name('HCXMaterializerBridge.c').read_text(),dict(
        HCXAISiteDirector=N(Active=lambda:director),
        HCWorldMaterializer=N(Result=lambda *a:callbacks.append('refused'))))
    proposal.Id='lease:synthetic'  # explicit synthetic output of custody NextLease
    bridge.call('Offer',N(m_Refused=0),proposal)
    state=director.m_States[0]
    state.Patrol=patrol
    authored.call('Spawned',director,patrol)
    assert callbacks==['spawned']
    return state


class PickerSeed(unittest.TestCase):
    def test_fresh_shipped_survey_restart_and_identity_resolution(self):
        f=seeded_fixture()
        self.assertEqual([r.SiteId for r in f.survey.Routes],[p.Id for p in f.data.Parties])
        self.assertEqual(5,len(f.data.Parties))
        before=deepcopy(f.data.Parties)
        restarted=seeded_fixture(existing=before)
        self.assertEqual([vars(p) for p in before],[vars(p) for p in restarted.data.Parties])
        self.assertIn('added=0 existing=5 refused=0',restarted.logs[-1])
        for index,party in enumerate(f.data.Parties):
            route=f.survey.Routes[index]
            site=next(s for s in f.policy.Sites if s.Id==party.Id)
            self.assertEqual(site.NumberOfAI,party.Size)
            self.assertEqual(site.Faction.lower(),party.FactionId)
            self.assertEqual(route.LocalityId,party.Home)
            proposal=proposal_fixture(f,index)
            self.assertIs(route,f.survey.HCFind(proposal.Identity.HCRouteId()))
            self.assertEqual(route.HCHomePoint(),proposal.Position)

    def test_caps_missing_repair_and_existing_row_is_never_rewritten(self):
        f=seeded_fixture(cap=2)
        self.assertEqual(2,len(f.data.Parties))
        f.data.Parties[0].Size=1
        f.data.Parties.pop()
        f.world.HCSeedPickerParties()
        self.assertEqual(2,len(f.data.Parties))
        self.assertEqual(1,f.data.Parties[0].Size)
        self.assertTrue(f.world.m_Dirty)

    def test_mismatched_route_scheme_and_unknown_faction_are_not_seeded(self):
        for defect in ('route','faction'):
            f=seeded_fixture()
            removed=f.data.Parties.pop(0)
            if defect=='route':f.survey.Routes[0].RouteId='route:mismatch'
            else:next(s for s in f.policy.Sites if s.Id==removed.Id).Faction='Unknown'
            f.world.HCSeedPickerParties()
            self.assertEqual(4,len(f.data.Parties))
            self.assertIn('added=0 existing=4 refused=1',f.logs[-1])

    def test_start_hook_is_server_once_after_world_load_and_not_a_tick(self):
        self.assertTrue(SEED.exists(),'HC-34 default boot has no authored party seeder')
        calls=[]
        world=N(m_Running=False,m_HCPickerSurvey=None,HCSeedPickerParties=lambda *a:calls.append('seed'),
                HCLoadPickerSites=lambda:object())
        def start(settings):world.m_Running=True
        run=compile_authored(SEED,'HCWorldModule','OnStart',base_scope(
            this=world,GetGame=lambda:N(IsServer=lambda:True),
            HCPickerSurvey=N(HCLoad=lambda refusal:object()),HCXAISiteDirector=N(LoadPolicy=lambda:object()),
            **{'super':N(OnStart=start)}),modded=True,members=('HCSeedPickerParties',))
        run(world,N(EnableEncounters=True));run(world,N(EnableEncounters=True))
        self.assertEqual(['seed'],calls)
        self.assertNotIn('OnTick',SEED.read_text())
        self.assertIn('$mission:hollow-country/ai/sites.json',SEED.read_text())


if __name__=='__main__':unittest.main()
