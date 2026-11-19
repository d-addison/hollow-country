"""#210 spec/plan/tasks: retry leased smoke; bounded wreck shelter query.
Spec: preserve signals on refused work, never consume unrelated stock, and admit
survivors at existing reviewed wrecks. Driving remains traced to the missing port.
Plan: retain one stock handle and a bounded inventory cursor on the existing lease;
retry through HCObserve; validate radius before native allocation; preserve routes.
Tasks: RED behavioral tests, implement the three review fixes and wreck eligibility,
then focused regression/native-compile lint; native/two-client verdicts stay pending.
Explicit synthetic engine/Expansion ports execute authored methods, never DayZ proof.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest
import re
from tests.unit.test_map_layers import translate
from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT/'mods/HollowCountryExpansionAI/scripts/4_World/HCW38SituationRuntime.c'


def binding(**values):
    result = N(SmokeAttempts=0, SmokeDone=False, SmokeStock=None, SmokeOwner=None,
               SmokeDropped=False, FactPublished=False, SmokeScan=None, SmokeMember=0, Profile='survivor',
               Lease='owned', Members=EArray(), Group=N(Count=lambda: 1, GetMember=lambda index: N(GetPosition=lambda: 0, IsAlive=lambda: True)))
    vars(result).update(values)
    return result


def signal_fixture():
    state = N(grant=False, visible=False, stock=None, refusals=[], fired=[], queries=[])
    source = RUNTIME.read_text().replace('eAIBase witness', 'HCWitness witness')
    source = source.replace('array<Object>', 'EArray').replace('array<CargoBase>', 'EArray')
    source = source.replace('s_FactPending', 'pending.fact').replace('s_SmokePending', 'pending.smoke')
    env = dict(pending=N(fact=False, smoke=False), s_Policy=N(ScanRows=3, ShelterMeters=20, PhysicalScanObjects=64),
               GetGame=lambda: N(GetObjectsAtPosition3D=lambda at,radius,nearby,proxies: nearby.append(N(GetPosition=lambda: 0, IsAlive=lambda: True))),
               SmokeGrenadeBase=N(Cast=lambda value: value),
               eAIBase=N(Cast=lambda value: value), Print=lambda line: None,
               HCRefuse=lambda reason: state.refusals.append(reason) or False,
               HCProfileOn=lambda profile: True, FileExist=lambda path: False,
               HCWorldMaterializer=N(HCIdentity=lambda lease: lease == 'owned'),
               HCSituationSignals=N(HCPublish=lambda at: True, HCSmoke=lambda item: state.fired.append(item) or True),
               HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda consumer,cost: state.grant)),
               HCUnitBudget=N(HC_WORK_SITUATIONS=11),
               HCXAISiteDirector=N(Active=lambda: N(MemberProblemFor=lambda at: 'visible' if state.visible else '')),
               HCLeaseSmoke=lambda active: active.SmokeStock or state.stock,
               vector=N(DistanceSq=lambda a,b: (a-b)**2))
    translate(source, 'HCW38SituationRuntime', env, only=('HCSignals', 'HCSmokeFailed'))
    return env, state


class W58Situations(unittest.TestCase):
    def test_budget_refusal_defers_then_fires_same_leased_item_once(self):
        env, state = signal_fixture()
        smoke = N(GetPosition=lambda: 0, GetHierarchyRootPlayer=lambda: None,
                  GetHierarchyParent=lambda: None, IsPendingDeletion=lambda: False)
        active = binding(SmokeStock=smoke, SmokeDropped=True)
        env['HCSignals'](active)
        self.assertEqual([], state.fired)
        self.assertFalse(active.SmokeDone)
        state.grant = True
        env['HCSignals'](active)
        env['HCSignals'](active)
        self.assertEqual([smoke], state.fired)
        self.assertTrue(active.SmokeDone)

    def test_minimum_retry_policy_still_defers_the_initial_refusal(self):
        env, state = signal_fixture()
        env['s_Policy'].ScanRows = 1
        active = binding()
        env['HCSignals'](active)
        self.assertFalse(active.SmokeDone, 'one configured retry must survive the initial refusal')
        env['HCSignals'](active)
        self.assertTrue(active.SmokeDone)

    def test_smoke_retries_publish_the_place_fact_only_once(self):
        env, state = signal_fixture()
        facts = []
        state.grant = True
        env['HCSituationSignals'].HCPublish = lambda at: facts.append(at) or True
        active = binding()
        for _ in range(3): env['HCSignals'](active)
        self.assertEqual([0], facts)

    def test_budget_denial_has_finite_named_give_up(self):
        env, state = signal_fixture()
        active = binding()
        for _ in range(12): env['HCSignals'](active)
        self.assertTrue(active.SmokeDone)
        self.assertEqual(4, active.SmokeAttempts)
        self.assertEqual(['SITUATION_SMOKE_RETRY_EXHAUSTED_BUDGET'], state.refusals)

    def test_player_item_and_visible_stock_are_never_consumed(self):
        env, state = signal_fixture()
        state.grant = True
        player_item = N(GetPosition=lambda: 0, GetHierarchyRootPlayer=lambda: object(),
                        GetHierarchyParent=lambda: object(), IsPendingDeletion=lambda: False)
        active = binding(SmokeStock=player_item, SmokeDropped=True)
        env['HCSignals'](active)
        self.assertEqual([], state.fired)
        active = binding(SmokeStock=N(GetPosition=lambda: 0, GetHierarchyRootPlayer=lambda: None,
                                     GetHierarchyParent=lambda: None, IsPendingDeletion=lambda: False), SmokeDropped=True)
        state.visible = True
        env['HCSignals'](active)
        self.assertEqual([], state.fired)
        self.assertFalse(active.SmokeDone)

    def test_wreck_query_refuses_radius_before_native_query(self):
        queried = []
        policy = N(ShelterMeters=500, PhysicalScanObjects=64, PhysicalScanCargo=16)
        source = RUNTIME.read_text().replace('array<Object>', 'EArray').replace('array<CargoBase>', 'EArray')
        env = dict(EArray=EArray, s_Policy=policy,
                   HCOperatorSettingsRegistry=N(HCValid=lambda key,value: 1 <= value <= 50),
                   HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda consumer,cost: True)),
                   HCUnitBudget=N(HC_WORK_SITUATIONS=11), HCRefuse=lambda reason: False,
                   HCWreckSalvage=N(Reviewed=lambda name: name == 'reviewed-wreck'),
                   GetGame=lambda: N(GetObjectsAtPosition3D=lambda at,radius,nearby,proxies: queried.append(radius) or nearby.append(N(GetType=lambda: 'reviewed-wreck'))))
        translate(source, 'HCW38SituationRuntime', env, only=('HCWreckNear',))
        self.assertIn('HCWreckNear', env, 'vehicle shelter must use the capped query port')
        self.assertFalse(env['HCWreckNear'](0))
        self.assertEqual([], queried)
        policy.ShelterMeters = float('nan')
        self.assertFalse(env['HCWreckNear'](0))
        policy.ShelterMeters = 20
        self.assertTrue(env['HCWreckNear'](0))
        self.assertEqual([20], queried)

    def test_observation_services_deferred_smoke(self):
        source = RUNTIME.read_text().replace('array<eAIBase>', 'EArray').replace('s_Active', 'active')
        calls = []
        env = dict(active=N(Id='incident', Members=EArray([N(IsAlive=lambda: True, IsPendingDeletion=lambda: False)])),
                   HCSignals=lambda active: calls.append(active))
        translate(source, 'HCW38SituationRuntime', env, only=('HCObserve',))
        env['HCObserve'](N(Id='other'))
        self.assertEqual([], calls)
        env['HCObserve'](N(Id='incident'))
        self.assertEqual([env['active']], calls)

    def test_wiped_or_destroyed_group_still_reaches_the_dead_outcome(self):
        """Review P1: Expansion removes killed members (GetMember indexes directly)."""
        for group in (None, N(Count=lambda: 0, GetMember=lambda index: [][index])):
            with self.subTest(group=group):
                env, state = signal_fixture()
                state.grant = True
                source = RUNTIME.read_text().replace('array<eAIBase>', 'EArray').replace('s_Active', 'active')
                corpse = N(IsAlive=lambda: False, IsPendingDeletion=lambda: False)
                env['active'] = binding(Id='incident', Group=group, Members=EArray([corpse]))
                translate(source, 'HCW38SituationRuntime', env, only=('HCObserve',))
                self.assertEqual('dead', env['HCObserve'](N(Id='incident')))
                self.assertEqual(0, env['active'].SmokeAttempts)
                self.assertEqual([], state.refusals)


class W58StockAndShelter(unittest.TestCase):
    def test_inventory_cursor_charges_before_each_step_and_retains_nested_smoke(self):
        scanner_path = RUNTIME.with_name('HCW38SituationSmokeStock.c')
        source = scanner_path.read_text().replace('    override ', '    ')
        # Inherited fields are explicit syntax bindings for this translator.
        for field in ('Actor', 'Found', 'Complete', 'Visited', 'Frames'):
            source = re.sub(r'(?<![\w.])' + field + r'\b', 'self.' + field, source)
        state = N(allow=False, charges=0)
        def charge(consumer, cost):
            self.assertEqual((11, 1), (consumer, cost))
            state.charges += 1
            return state.allow
        def node(children=(), smoke=False, owner=None):
            cargo = N(GetItemCount=lambda: len(children), GetItem=lambda index: children[index])
            inventory = N(AttachmentCount=lambda: 0, GetCargo=lambda: cargo)
            return N(smoke=smoke, GetInventory=lambda: inventory, IsRuined=lambda: False,
                     GetHierarchyRootPlayer=lambda: owner)
        actor = node()
        actor.IsAlive = lambda: True
        stock = node(smoke=True, owner=actor)
        bag = node([stock])
        actor.GetInventory = node([bag]).GetInventory
        frame = lambda: N(NodeEntity=None, Checked=False, Attachment=0, CargoIndex=0)
        root = frame(); root.NodeEntity = actor
        cursor = N(Actor=actor, Found=None, Complete=False, Visited=0, Frames=EArray([root]), HCRetire=lambda: None)
        env = dict(HCServer=N(HCTickWork=lambda: N(HCTakeFor=charge)), HCUnitBudget=N(HC_WORK_SITUATIONS=11),
                   SmokeGrenadeBase=N(Cast=lambda entity: entity if entity.smoke else None),
                   HCXTradeInventoryFrame=frame)
        translate(source, 'HCW38SituationSmokeStock', env, only=('HCStep',))
        self.assertIsNone(env['HCStep'](cursor, 64))
        self.assertEqual(0, cursor.Visited)
        state.allow = True
        self.assertIs(stock, env['HCStep'](cursor, 64))
        self.assertEqual(3, cursor.Visited)
        stock.GetHierarchyRootPlayer = lambda: object()
        self.assertIsNone(env['HCStep'](cursor, 64), 'a transferred item cannot be recaptured')
        self.assertTrue(cursor.Complete)

    def test_inventory_cursor_total_bound_rejects_deeper_stock(self):
        source = RUNTIME.with_name('HCW38SituationSmokeStock.c').read_text().replace('    override ', '    ')
        for field in ('Actor', 'Found', 'Complete', 'Visited', 'Frames'):
            source = re.sub(r'(?<![\w.])' + field + r'\b', 'self.' + field, source)
        cursor = N(Actor=N(IsAlive=lambda: True), Found=None, Complete=False, Visited=64,
                   Frames=EArray([N()]))
        env = dict()
        translate(source, 'HCW38SituationSmokeStock', env, only=('HCStep',))
        self.assertIsNone(env['HCStep'](cursor, 64))
        self.assertTrue(cursor.Complete)

    def test_survivor_uses_reviewed_wreck_when_not_under_roof(self):
        source = RUNTIME.read_text().replace('eAIBase leader', 'HCLeader leader').replace('eAIGroup group', 'HCGroup group')
        checked = []
        group = N(Count=lambda: 2, IsInCombat=lambda: False,
                  GetMember=lambda index: N(IsAlive=lambda: True, GetPosition=lambda: 42))
        env = dict(s_Policy=N(MaxMembers=6, MaxRouteNodes=32), eAIBase=N(Cast=lambda actor: actor),
                   MiscGameplayFunctions=N(IsUnderRoof=lambda actor: False),
                   HCWreckNear=lambda at: checked.append(at) or True)
        translate(source, 'HCW38SituationRuntime', env, only=('HCProfileFits',))
        party = N(Patrol=N(m_Group=group), PatrolPoints=EArray([0, 1]), ProviderFaction='HCSurvivors')
        self.assertTrue(env['HCProfileFits'](party, 'survivor'))
        self.assertEqual([42], checked)
        env['HCWreckNear'] = lambda at: False
        self.assertFalse(env['HCProfileFits'](party, 'survivor'))

    def test_only_captured_owner_can_drop_and_only_same_handle_is_activated(self):
        env, state = signal_fixture()
        state.grant = True
        drops = []
        stock = N(GetPosition=lambda: 0, IsPendingDeletion=lambda: False,
                  GetHierarchyParent=lambda: None)
        owner = N(GetPosition=lambda: 0, ServerDropEntity=lambda item: drops.append(item) or True)
        stock.GetHierarchyRootPlayer = lambda: None if drops else owner
        active = binding(SmokeStock=stock, SmokeOwner=owner)
        env['HCSignals'](active)
        self.assertEqual([stock], drops)
        self.assertEqual([stock], state.fired)
        # Refuse before the drop when the owner is visible, even with a hidden witness.
        drops.clear(); state.fired.clear()
        active = binding(SmokeStock=stock, SmokeOwner=owner)
        owner.GetPosition = lambda: 10
        env['HCXAISiteDirector'].Active = lambda: N(MemberProblemFor=lambda at: 'seen' if at == 10 else '')
        env['HCSignals'](active)
        self.assertEqual([], drops)
        self.assertEqual([], state.fired)

    def test_lease_stock_reader_never_adopts_ground_items(self):
        source = RUNTIME.read_text().replace('eAIBase holder', 'HCActor holder')
        group = N()
        stock = object()
        holder = N(IsAlive=lambda: True, GetIdentity=lambda: None, GetGroup=lambda: group)
        calls = []
        scanner = N(HCStart=lambda actor,wanted: calls.append(actor), HCStep=lambda limit: stock, Complete=False)
        env = dict(s_Policy=N(PhysicalScanObjects=64), HCW38SituationSmokeStock=lambda: scanner)
        translate(source, 'HCW38SituationRuntime', env, only=('HCLeaseSmoke',))
        active = binding(Members=EArray([holder]), Group=group)
        self.assertIs(stock, env['HCLeaseSmoke'](active))
        self.assertIs(holder, active.SmokeOwner)
        self.assertIs(stock, active.SmokeStock)
        self.assertEqual([holder], calls)
        self.assertIs(stock, env['HCLeaseSmoke'](active))
        self.assertEqual([holder], calls, 'never replace the recorded handle')
        self.assertIsNone(env['HCLeaseSmoke'](binding()), 'no world query or stock creation fallback')

if __name__ == '__main__': unittest.main()
