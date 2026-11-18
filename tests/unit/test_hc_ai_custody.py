"""HC-10: execute authored custody decisions through synthetic stdlib ports.

No engine/provider/inventory simulation or native acceptance. The existing
restricted syntax adapter executes the Enforce methods; DTOs and file IO are
explicit synthetic fixtures.

RED: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_ai_custody -v
AssertionError: missing authored method HCCustodyAllows; FAILED (failures=1).
Restart-cap RED (same command): missing authored method HCCustodyDebt; FAILED (failures=1).
GREEN: same command; Ran 1 test; OK. Runtime acceptance pending.
"""
import copy
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_expansion_ai_adapter import A, Authored

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = ROOT / 'mods/HollowCountry/scripts/3_Game/World/HCAIPartyIdentity.c'
MATERIALIZER = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCWorldMaterializer.c'
BRIDGE = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXMaterializerBridge.c'


def adapted(source, env):
    # Syntax only: let the existing restricted port strip our new DTO local
    # declarations. Class references, calls and all decisions remain authored.
    source = re.sub(r'\b(?:HCAIParty\w*|HCWorld\w+)\b(?=\s+\w+\s*[=;:)])',
                    'HCXAIValue', source)
    return Authored(source, env)


class CustodyBehavior(unittest.TestCase):
    def test_duplicate_lease_result_and_refilled_return_are_refused(self):
        source = MATERIALIZER.read_text()
        env = dict(A=A, len=len, str=str, HCAIPartyCustody=N(MAX_ROWS=64))
        from tests.unit.ai_limits_fixture import install
        install(env, MaxLiveAI=8, MaxMaterialized=2)
        runtime = N(m_CustodyReady=True, m_Custody=N(Rows=A()),
                    m_DuplicateRefused=0)
        # This executes the authored reservation decision (initial RED seam).
        runtime.HCCustodyAllows = lambda identity: adapted(source, env).call(
            'HCCustodyAllows', runtime, identity)
        synthetic_identity = N(HCPartyId=lambda: 'party:synthetic-caravan',
                               HCCargoId=lambda: 'cargo:synthetic-caravan')
        self.assertTrue(runtime.HCCustodyAllows(synthetic_identity))
        runtime.m_Custody.Rows.Insert(N(PartyId='party:synthetic-caravan',
                                       CargoId='cargo:synthetic-caravan'))
        self.assertFalse(runtime.HCCustodyAllows(synthetic_identity))
        self.assertEqual(1, runtime.m_DuplicateRefused)

        data_source = IDENTITY.read_text()
        policy = adapted(data_source, env)
        env['HCWorldLimits'] = N(Token=lambda value: bool(value) and len(value) <= 96)
        identity_api = N()
        env['HCAIPartyIdentity'] = identity_api
        identity_api.HCValid = lambda identity: policy.call('HCValid', None, identity)
        # Explicit immutable synthetic identity values; getter bodies are authored.
        identity = N(m_PartyId='party:synthetic-caravan', m_CampId='camp:synthetic',
                     m_HomeId='synthetic-home', m_RouteId='route:synthetic-caravan',
                     m_CargoId='cargo:synthetic-caravan', m_Generation=42)
        for name in ('HCPartyId', 'HCCampId', 'HCHomeId', 'HCRouteId',
                     'HCCargoId', 'HCGeneration'):
            setattr(identity, name, lambda name=name: policy.call(name, identity))
        self.assertTrue(identity_api.HCValid(identity))
        identity.m_Generation = 0
        self.assertFalse(identity_api.HCValid(identity))
        identity.m_Generation = 42
        env['HCAIPartyCustodyRow'] = lambda: N(Outcome='CLAIMED', Materialized=False,
                                              Survivors=0)
        row = policy.call('HCReservation', None, identity, 'lease:synthetic', 4)
        self.assertEqual('camp:synthetic', row.CampId)
        self.assertEqual('synthetic-home', row.HomeId)
        self.assertEqual('route:synthetic-caravan', row.RouteId)
        self.assertEqual(42, row.Generation)
        self.assertEqual(1, policy.call('HCFinish', None, row, True, 2))
        first = copy.deepcopy(vars(row))
        self.assertEqual(2, policy.call('HCFinish', None, row, True, 2))
        self.assertEqual(first, vars(row))  # duplicate death/retirement callback
        self.assertEqual(0, policy.call('HCFinish', None, row, True, 4))
        self.assertEqual('QUARANTINED', row.Outcome)  # refilled/contradictory return
        self.assertEqual(2, row.Survivors)  # never overwrite first observation
        self.assertEqual(0, policy.call('HCFinish', None, row, True, 2))
        runtime.m_Custody.Rows = A([row])
        restarted = copy.deepcopy(runtime.m_Custody)  # synthetic durable readback
        runtime.m_Custody = restarted
        self.assertFalse(runtime.HCCustodyAllows(identity))
        identity.m_Generation = 43  # a reset epoch cannot refill the same party
        self.assertFalse(runtime.HCCustodyAllows(identity))
        identity.m_PartyId = 'party:synthetic-other'
        self.assertFalse(runtime.HCCustodyAllows(identity))  # cargo alias refused
        # Exercise the actual claim + result handlers against explicit synthetic
        # durable/world ports. A saved intent must precede any provider claim;
        # duplicated callbacks cannot repeat either world mutation.
        env['HCAIPartyCustody'].HCReservation = lambda *args: policy.call(
            'HCReservation', None, *args)
        env['HCAIPartyCustody'].HCFinish = lambda *args: policy.call(
            'HCFinish', None, *args)
        facts, debits, saves = [], [], []
        world = N(GetFaction=lambda faction: True,
                  AddFact=lambda *args: facts.append(args) or True,
                  AdjustStrength=lambda *args: debits.append(args) or True)
        env['HCWorldModule'] = N(Get=lambda: world)
        methods = adapted(source, env)
        api = N(MAX_ACTORS=8, MAX_PROPOSALS=2, MAX_PER_PROPOSAL=4,
                PROVIDER_TIMEOUT=120)
        env['HCWorldMaterializer'] = api
        api.FoldBack = lambda *args: methods.call('FoldBack', None, *args)
        api.NoProvider = lambda *args: methods.call('NoProvider', None, *args)
        identity.m_PartyId = 'party:synthetic-caravan'
        identity.m_Generation = 42
        lease = N(Proposal=N(Id='lease:synthetic', Identity=identity,
                            ActorCap=4, FactionId='synthetic-faction',
                            PlaceId='synthetic-home', Kind='CARAVAN'),
                  Claimed=False, Finished=False, OutcomeApplied=False,
                  Materialized=False, Survivors=0, Created=0)
        runtime.m_Custody.Rows.Clear()
        runtime.m_Active = A([lease])
        runtime.m_Clock = 0
        runtime.m_Materialized = runtime.m_Traces = 0
        runtime.HCSaveCustody = lambda: saves.append(copy.deepcopy(
            runtime.m_Custody)) or True
        runtime.HCCustodyDebt = lambda *args: methods.call('HCCustodyDebt', runtime, *args)
        runtime.HCClaimFits = lambda: methods.call('HCClaimFits', runtime)
        env['MAX_ACTORS'] = 8
        env['MAX_PROPOSALS'] = 2
        runtime.HCRecordResult = lambda *args: methods.call('HCRecordResult', runtime, *args)
        runtime.Expire = lambda: methods.call('Expire', runtime)
        runtime.Resolve = lambda *args: methods.call('Resolve', runtime, *args)
        self.assertTrue(methods.call('HCClaim', runtime, lease))
        self.assertTrue(lease.Claimed)
        self.assertEqual(1, len(saves))
        self.assertFalse(methods.call('HCClaim', runtime, lease))
        methods.call('HCRecordResult', runtime, 'unknown-lease', True, 0)
        self.assertEqual(1, len(saves))
        result = N(HCIdentity=lambda: identity, HCLeaseId=lambda: 'lease:synthetic',
                   HCMaterialized=lambda: True, HCSurvivors=lambda: 2)
        methods.call('HCRecordTypedResult', runtime, result)
        methods.call('HCRecordTypedResult', runtime, result)
        self.assertEqual(1, len(facts))
        self.assertEqual([('synthetic-faction', -2)], debits)
        self.assertEqual(2, len(saves))
        self.assertEqual([], runtime.m_Active)
        result.HCSurvivors = lambda: 4
        methods.call('HCRecordTypedResult', runtime, result)
        methods.call('HCRecordTypedResult', runtime, result)
        self.assertEqual(3, len(saves))  # no quarantine save loop
        self.assertEqual('QUARANTINED', runtime.m_Custody.Rows[0].Outcome)
        self.assertEqual(1, len(debits))
        self.assertFalse(runtime.HCCustodyAllows(identity))
        self.assertEqual(4, methods.call('HCCustodyDebt', runtime, True))
        self.assertEqual(1, methods.call('HCCustodyDebt', runtime, False))
        # A restart/off transition must reserve unknown surviving actors against
        # the same 8/2 global cap; a new identity cannot bypass the old lease.
        runtime.m_Custody.Rows[0].Outcome = 'CLAIMED'
        runtime.m_Custody.Rows[0].Materialized = False
        runtime.m_Custody.Rows[0].Survivors = 0
        self.assertEqual(4, methods.call('HCCustodyDebt', runtime, True))
        runtime.m_Active.Insert(N(Proposal=N(Id='synthetic-second', ActorCap=4)))
        self.assertTrue(runtime.HCClaimFits())
        runtime.m_Active.Insert(N(Proposal=N(Id='synthetic-third', ActorCap=1)))
        self.assertFalse(runtime.HCClaimFits())
        runtime.m_Active.Clear()
        runtime.m_Active.Insert(lease)
        self.assertEqual(0, methods.call('HCCustodyDebt', runtime, True))
        runtime.m_Active.Clear()
        # Synthetic failed claim barrier: never hands the provider a lease.
        runtime.m_Custody.Rows.Clear()
        lease.Claimed = lease.Finished = False
        runtime.HCSaveCustody = lambda: False
        self.assertFalse(methods.call('HCClaim', runtime, lease))
        self.assertFalse(lease.Claimed)
        self.assertFalse(runtime.HCCustodyAllows(identity))
        runtime.m_CustodyReady = False
        runtime.m_Custody.Rows.Clear()
        self.assertFalse(runtime.HCCustodyAllows(identity))
        # Explicit synthetic legacy/typed callback ports: distinguish callbacks
        # with unknown identity from unique, attributable provider spawns.
        bridge_runtime = N(m_Running=True, m_Spawned=0,
                           m_UnattributedSpawnCallbacks=0, m_Started=A())
        env['s_Instance'] = bridge_runtime
        api.HCIdentity = lambda lease_id: identity if lease_id == 'lease:synthetic' else None
        bridge = adapted(BRIDGE.read_text(), env)
        bridge.call('SiteSpawned', None)
        self.assertEqual(0, bridge_runtime.m_Spawned)
        self.assertEqual(1, bridge_runtime.m_UnattributedSpawnCallbacks)
        bridge.call('SiteSpawned', None, 'unknown-lease')
        bridge.call('SiteSpawned', None, 'lease:synthetic')
        bridge.call('SiteSpawned', None, 'lease:synthetic')
        self.assertEqual(1, bridge_runtime.m_Spawned)


if __name__ == '__main__':
    unittest.main()
