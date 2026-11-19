"""HC-34 round 2: authored lifecycle over explicit SYNTHETIC actors/leases.
No DayZ, provider pathfinding, inventory persistence or runtime evidence.
"""
from types import SimpleNamespace as N
import unittest
from copy import deepcopy
from tests.unit.test_hc_pickers_survey import ROOT, method
from tests.unit.test_debug_map_layers import compile_authored
from tests.unit.test_admin_test_kit import base_scope
from tests.unit.test_group_server import EArray
from tests.unit.test_hc_scavenge import bind, PICKERS
from tests.unit.test_hc_picker_walk import WALK

HOOK = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIPickerLifecycle.c'


class PickerStarts(unittest.TestCase):
    def fixture(self):
        effects = []
        identity = N(HCPartyId=lambda: 'party:synthetic', HCRouteId=lambda: 'route:synthetic')
        route = N(HCHomePoint=lambda: (0, 0, 0))
        actor = N(GetPosition=lambda: (0, 0, 0))
        defaults = N(MaxConcurrentTrips=1, PartyCooldownSeconds=900)
        state = N(Phase='idle', PartyId='', LeaseId='', RouteId='', NextTripAt=0, Refusal='')
        port = N(Defaults=defaults, Actor=None, HCWalkRefusal=lambda: '', HCClear=lambda: effects.append('clear'))
        trip = N(m_State=state, m_IO=port, m_Ready=True, m_Busy=False,
                 HCCheckpoint=lambda: effects.append('checkpoint') is None)
        module = N(m_Trip=trip, m_Survey=N(HCFind=lambda key: route if key == 'route:synthetic' else None,
                                         ArrivalRangeMeters=2.5))
        def begin(i, lease, body):
            effects.append(('begin', i, lease, body))
            state.Phase, state.PartyId, state.LeaseId = 'leaving', i.HCPartyId(), lease
            return ''
        module.HCBeginSurveyed = begin
        budget = [True]
        scope = dict(GetGame=lambda: N(IsServer=lambda: True), HCAIPartyIdentity=N(HCValid=lambda i: i is not None),
                     HCServer=N(HCTickWork=lambda: N(HCTake=lambda cost: budget[0])),
                     vector=N(DistanceSq=lambda a,b: sum((x-y)**2 for x,y in zip(a,b))))
        module.HCTryParty = lambda *a: method('HCPickers', 'HCTryParty',
            members=('HCBeginSurveyed',), **scope)(module, *a)
        return N(module=module, trip=trip, state=state, actor=actor, identity=identity,
                 effects=effects, defaults=defaults, budget=budget)

    def test_idle_surveyed_party_starts_once_with_real_actor_and_lease(self):
        f = self.fixture()
        self.assertEqual('', f.module.HCTryParty(f.identity, 'lease:synthetic', f.actor, 1000, 0))
        self.assertEqual('PICKER_TRIP_ACTIVE', f.module.HCTryParty(f.identity, 'lease:synthetic', f.actor, 1001, 0))
        self.assertEqual([('begin',f.identity,'lease:synthetic',f.actor)], f.effects)

    def test_cooldown_cap_budget_and_real_home_position_precede_begin(self):
        for reason, mutate, now, eligible in (
            ('PICKER_PARTY_COOLDOWN', lambda f: None, 999, 1000),
            ('PICKER_GLOBAL_CAP', lambda f: setattr(f.defaults,'MaxConcurrentTrips',0),1000,0),
            ('PICKER_WORK_BUDGET', lambda f: f.budget.__setitem__(0,False),1000,0),
            ('PICKER_NOT_AT_HOME', lambda f: setattr(f.actor,'GetPosition',lambda:(5,0,0)),1000,0),
            ('PICKER_ROUTE_UNSURVEYED', lambda f: setattr(f.identity,'HCRouteId',lambda:'route:unknown'),1000,0),
        ):
            with self.subTest(reason=reason):
                f=self.fixture(); mutate(f)
                self.assertEqual(reason,f.module.HCTryParty(f.identity,'lease:synthetic',f.actor,now,eligible))
                self.assertEqual([], f.effects)

    def test_terminal_rearm_is_durable_and_quarantine_is_never_replayed(self):
        for phase in ('returned','lost','quarantined'):
            f=self.fixture(); f.state.Phase=phase
            f.state.NextTripAt=1900
            self.assertEqual('PICKER_PARTY_COOLDOWN' if phase != 'quarantined' else 'PICKER_JOURNAL_QUARANTINED',
                             f.module.HCTryParty(f.identity,'lease:synthetic',f.actor,1800,0))
            if phase != 'quarantined':
                self.assertEqual('', f.module.HCTryParty(f.identity,'lease:synthetic',f.actor,1900,0))
                self.assertEqual(['clear','checkpoint'],f.effects[:2])

    def test_lifecycle_exists_and_uses_existing_transient_step_and_loss_boundary(self):
        self.assertTrue(HOOK.exists(), 'HC-34 has no materialised-party trip initiation hook')
        source=HOOK.read_text()
        for seam in ('override void StepTransients()', 'super.StepTransients()',
                     'HCWorldMaterializer.HCIdentity', 'HCTryParty',
                     'override void FinishTransient', 'HCLose("PARTY_LEASE_LOST")'):
            self.assertIn(seam,source)


class PickerLifecycle(unittest.TestCase):
    """SYNTHETIC site/policy/group; execute the authored hook, not a model."""
    def fixture(self):
        f=PickerStarts().fixture()
        logs=[]
        group=N(Count=lambda:1, GetMember=lambda index:f.actor, IsInCombat=lambda:False)
        f.actor.GetGroup=lambda:group
        home=N(Id='site:synthetic')
        route=f.module.m_Survey.HCFind('route:synthetic')
        route.SiteId=home.Id
        f.trip.m_IO.Survey=f.module.m_Survey
        f.module.HCTrip=lambda:f.trip
        state=N(Transient=True,Materialized=True,Completed=False,ProposalId='lease:synthetic',
                Patrol=N(m_Group=group, m_HCPendingMembers=0), HCPickerSiteCursor=0,HCPickerHomeSite=None,
                HCPickerEligibleAt=0,HCPickerRefusal='')
        refuse=compile_authored(HOOK,'HCXAISiteState','HCRefusePicker',base_scope(Print=logs.append),modded=True, fields=('HCPickerRefusal',))
        state.HCRefusePicker=lambda *a:refuse(state,*a)
        enabled,server,locked=[True],[True],[False]
        director=N(m_Policy=N(Sites=EArray([home])), RaidLocked=lambda site,now:locked[0])
        scope=base_scope(this=director, HCPickers=N(Get=lambda:f.module if enabled[0] else None),
            GetGame=lambda:N(IsServer=lambda:server[0]),
            HCWorldMaterializer=N(HCIdentity=lambda lease:f.identity if lease==state.ProposalId else None),
            HCAIPartyIdentity=N(HCValid=lambda identity:identity is f.identity),
            PlayerBase=N(Cast=lambda actor:actor))
        run=compile_authored(HOOK,'HCXAISiteDirector','HCParty',scope,modded=True)
        f.step=lambda now=1000:run(director,state,now)
        return N(f=f,state=state,logs=logs,enabled=enabled,server=server,locked=locked,director=director)

    def test_lifecycle_passes_claimed_identity_actor_lease_once(self):
        f=self.fixture()
        f.step=f.f.step
        f.step(); f.step()
        self.assertEqual([('begin',f.f.identity,'lease:synthetic',f.f.actor)],f.f.effects)

    def test_missing_group_or_unsurveyed_route_refuses_once_by_name(self):
        for reason in ('PICKER_ACTOR_GROUP_MISSING','PICKER_ROUTE_UNSURVEYED'):
            f=self.fixture()
            if reason.endswith('MISSING'):f.state.Patrol.m_Group=None
            else:f.f.identity.HCRouteId=lambda:'route:unknown'
            f.f.step(); f.f.step()
            self.assertEqual([],f.f.effects)
            self.assertEqual(1,len(f.logs))
            self.assertIn('outcome='+reason,f.logs[0])
            self.assertIn('runtime=PENDING',f.logs[0])

    def test_feature_off_client_or_site_cooldown_never_begins(self):
        for blocker in ('enabled','server','locked'):
            f=self.fixture()
            getattr(f,blocker)[0]=(blocker=='locked')
            f.f.step();f.f.step()
            self.assertEqual([],f.f.effects)
            if blocker=='locked':self.assertIn('PICKER_SITE_COOLDOWN',f.logs[0])

    def test_combat_or_pending_spawn_is_not_an_idle_party(self):
        for pending in (False,True):
            f=self.fixture()
            if pending:f.state.Patrol.m_HCPendingMembers=1
            else:f.state.Patrol.m_Group.IsInCombat=lambda:True
            f.f.step();f.f.step()
            self.assertEqual([],f.f.effects)
            self.assertIn('PICKER_PARTY_BUSY',f.logs[0])

    def test_missing_group_is_named_before_base_lifecycle_removes_state(self):
        f=self.fixture()
        f.state.Patrol.m_Group=None
        f.director.m_States=EArray([f.state]);f.director.m_HCPickerCursor=0
        f.director.HCParty=lambda state,now:f.f.step(now)
        def release(*args):
            f.state.Completed=True
            f.director.m_States.clear()
        finish=compile_authored(HOOK,'HCXAISiteDirector','FinishTransient',
            base_scope(this=f.director,HCPickers=N(Get=lambda:f.f.module),
                       ExpansionStatic=N(GetTimestamp=lambda utc:1000),
                       **{'super':N(FinishTransient=release)}),modded=True)
        def retire():
            finish(f.director,f.state,True,0)
        scope=base_scope(this=f.director, GetGame=lambda:N(IsServer=lambda:True),
            HCPickers=N(Get=lambda:f.f.module),
            HCServer=N(HCTickWork=lambda:N(HCTake=lambda cost:True)),
            ExpansionStatic=N(GetTimestamp=lambda utc:1000),
            **{'super':N(StepTransients=retire)})
        run=compile_authored(HOOK,'HCXAISiteDirector','StepTransients',scope,modded=True,
                             fields=('m_HCPickerCursor',))
        run(f.director)
        self.assertEqual(1,len(f.logs))
        self.assertIn('PICKER_ACTOR_GROUP_MISSING',f.logs[0])
        self.assertEqual([],f.f.effects)

    def test_existing_step_visits_one_state_under_shared_budget(self):
        calls=[]
        director=N(m_States=EArray([object(),object()]),m_HCPickerCursor=0,
                   HCParty=lambda state,now:calls.append((state,now)))
        allowed,enabled=[False],[True]
        scope=base_scope(this=director,GetGame=lambda:N(IsServer=lambda:True),
            HCPickers=N(Get=lambda:object() if enabled[0] else None),
            HCServer=N(HCTickWork=lambda:N(HCTake=lambda cost:allowed[0])),
            ExpansionStatic=N(GetTimestamp=lambda utc:1000),
            **{'super':N(StepTransients=lambda:calls.append('base'))})
        run=compile_authored(HOOK,'HCXAISiteDirector','StepTransients',scope,modded=True, fields=('m_HCPickerCursor',))
        run(director)
        self.assertEqual(['base'],calls)
        allowed[0]=True
        run(director);run(director);run(director)
        self.assertEqual([director.m_States[0],director.m_States[1],director.m_States[0]],
                         [call[0] for call in calls if isinstance(call,tuple)])
        enabled[0]=False;calls.clear();run(director)
        self.assertEqual(['base'],calls)

    def test_per_party_receipt_survives_another_partys_journal(self):
        f=self.fixture()
        f.f.state.PartyId=f.f.identity.HCPartyId()
        f.f.state.Phase='returned';f.f.state.NextTripAt=1900
        f.f.step(1800)
        self.assertEqual(1900,f.state.HCPickerEligibleAt)
        f.f.state.PartyId='party:other';f.f.state.Phase='idle';f.f.state.NextTripAt=0
        f.f.step(1801)
        self.assertEqual([],f.f.effects)
        f.f.step(1900)
        self.assertEqual(1,len(f.f.effects))

    def test_despawn_mid_trip_uses_loss_journal_without_item_copy_or_move(self):
        f=self.fixture()
        saved,moves,order=[],[],[]
        physical=['actor'] # ONE existing item, already acquired; never copied/refunded.
        row=f.f.state
        row.Phase='returning';row.LeaseId=f.state.ProposalId;row.CargoOwner='actor'
        trip=f.f.trip
        trip.m_Store=N(Save=lambda state:(saved.append(deepcopy(state)),True)[1])
        trip.HCLog=lambda:order.append('journal')
        trip.m_IO.HCOwner=lambda:physical[0]
        trip.m_IO.HCMove=lambda *a:moves.append(a)
        bind(PICKERS.read_text(),'HCScavengeTrip',trip,
             ('HCLose','HCCheckpoint','HCStep','HCRestore'),{})
        scope=base_scope(HCPickers=N(Get=lambda:f.f.module),
                        **{'super':N(FinishTransient=lambda *a:order.append('release'))})
        run=compile_authored(HOOK,'HCXAISiteDirector','FinishTransient',scope,modded=True)
        run(f.director,f.state,True,1)
        self.assertEqual(['journal','release'],order)
        self.assertEqual(('lost','PARTY_LEASE_LOST','actor'),(row.Phase,row.Refusal,row.CargoOwner))
        self.assertEqual('lost',saved[-1].Phase)
        trip.HCStep();trip.HCRestore()
        run(f.director,f.state,True,1)
        self.assertEqual(['actor'],physical)
        self.assertEqual([],moves)
        self.assertEqual(1,len(saved),'repeat retirement must not duplicate loss or custody writes')

    def test_start_and_end_logs_once_per_phase_include_persisted_party_and_route(self):
        lines=[]
        trip=N(m_HCPickerLoggedPhase='',m_State=N(Phase='leaving',PartyId='party:synthetic',
               RouteId='route:synthetic',Refusal=''))
        run=compile_authored(WALK,'HCScavengeTrip','HCLogTripBoundary',base_scope(Print=lines.append),modded=True)
        run(trip,True);run(trip,True)
        trip.m_State.Phase='returning';run(trip,True)
        trip.m_State.Phase='lost';trip.m_State.Refusal='PARTY_LEASE_LOST'
        run(trip,True);run(trip,True)
        self.assertEqual(2,len(lines))
        for line in lines:
            for token in ('party=party:synthetic','route=route:synthetic','runtime=PENDING'):
                self.assertIn(token,line)
        self.assertIn('trip=start',lines[0]);self.assertIn('trip=end',lines[1])


if __name__ == '__main__':
    unittest.main()
