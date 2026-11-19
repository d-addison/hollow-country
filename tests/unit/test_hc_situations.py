"""HC-38 / #147/#148: authored handlers; explicit synthetic ports, no DayZ proof.

Spec: independent survivor opportunity, no quest UI or client reward authority.
Plan/task: pin one HC-19 identity, reuse its store and HC-10 lease, retire UI.
Native placement/actions, emotes and two-client acceptance remain pending.
"""
import copy
import json
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.unit import test_event_transport as transport
from tests.unit import test_event_ui as ui
from tests.unit.test_group_server import EArray
from tests.unit.test_map_layers import EStr, methods, translate
from types import MethodType

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mods/HollowCountry/scripts'


def director_fixture(image=None, enabled=True, fail=False):
    """Explicit synthetic DTO, HC-19 save barrier, HC-10 claim and actor port.

    Actor requests are counted, never claimed as executed in DayZ. No Python
    gameplay policy: all transitions/retirement decisions execute Enforce bodies.
    """
    source = (SCRIPTS/'4_World/Events/HCSituationDirector.c').read_text()
    source = source.replace('    protected ', '    ')
    chain = N(Id=EStr('hc-story-5'), StorySequence=5, DueAt=100, ExpiresAt=200,
              Complete=False, Cancelled=False)
    state = copy.deepcopy(image) if image else N(LastNow=100,
        Stories=N(LegacyThrough=4, NextSequence=6, HCFirstSurvivor=None), Chains=EArray([chain]))
    calls, logs, images = [], [], []
    actors = N(HCReady=lambda: True, HCRefusal=lambda: EStr('NO_OBSERVED_SURVIVOR'),
               HCSelect=lambda row: EStr('synthetic-owned-lease'),
               HCBegin=lambda row: calls.append(('begin', row.Lease)) or True,
               HCObserve=lambda row: EStr(''), HCEnd=lambda row: calls.append(('end', row.Lease)))
    def save(value):
        calls.append(('save', value.Stories.HCFirstSurvivor.Phase))
        if fail:
            return False
        images.append(copy.deepcopy(value))
        return True
    env = dict(GetGame=lambda: N(IsServer=lambda: True), Print=logs.append,
               HCV2Admission=N(Admitted=lambda preference: preference),
               HCStoryPolicy=N(HCValid=lambda s: True),  # Synthetic already-admitted HC-19 owner.
               HCEventDirector=N(TextValid=lambda s, n: 0 < len(s) <= n),
               HCSituationActors=N(HCGet=lambda: actors),
               HCWorldMaterializer=N(HCIdentity=lambda lease: object() if lease == 'synthetic-owned-lease' else None),
               HCSituationState=lambda: N(Version=1, Id=EStr(''), StorySequence=0, DueAt=0,
                   EndsAt=0, Phase=EStr('pending'), Outcome=EStr(''), Lease=EStr(''), Refusal=EStr('')),
               HCOperationalStatus=lambda: N(HCPublish=lambda *args: calls.append(('status', args))))
    table, _ = methods(source, 'HCSituationDirector')
    translate(source, 'HCSituationDirector', env)
    owner = N(m_State=None, m_Store=None, m_Actors=None, m_Enabled=False,
              m_Fault=False, m_Attempted=False, m_Effective=EStr('off'), m_Reason=EStr('not_started'),
              m_Units=N(HCReset=lambda n: calls.append(('units', n)), HCTake=lambda n: True),
              m_Work=N(HCReset=lambda n: None, HCContinue=lambda: True))
    for name, (static, _, _) in table.items():
        setattr(owner, name, env[name] if static else MethodType(env[name], owner))
    owner.HCOpen(state, N(Save=save), enabled)
    return N(owner=owner, state=state, actors=actors, calls=calls, logs=logs, images=images)


class SituationBehavior(unittest.TestCase):
    def test_independent_lifecycle_and_retired_quest_requests(self):
        # Existing restricted transport port executes the actual OnRPC handler
        # with synthetic native identities, journal and transport. No reward
        # grant is fabricated: legacy runtime already blocks reward completion.
        fixture = transport.EventTransportTests()
        fixture.setUp()
        before = copy.deepcopy(fixture.runtime.m_State)
        view = fixture.handshake()
        self.assertFalse(view.Enabled, 'HC-38 legacy quest browse remains admitted')
        self.assertEqual([], view.Rows)
        fixture.now += 3
        fixture.mutate()
        self.assertEqual(before, fixture.runtime.m_State)
        # No retired payload is deserialized, including alleged reward fields.
        fixture.now += 3
        fixture.rpc.OnRPC(fixture.sender, None, 4853801,
                          N(Read=lambda: self.fail('retired payload deserialized')))
        self.assertEqual(before, fixture.runtime.m_State)
        outsider = transport.Sender('forged', transport.Handle())
        count = len(fixture.sent)
        fixture.receive(fixture.request(), sender=outsider)
        self.assertEqual(count, len(fixture.sent), 'native authentication still required')

        client = ui.EventClientTests()
        client.setUp()
        client.client.Start()
        client.client.SetBrowsing(True)
        client.client.Transmit(client.e['HCEventWireRequest']())
        client.client.Update()
        self.assertFalse(client.client.Browse())
        self.assertFalse(client.client.Send(1, 1))
        self.assertFalse(client.client.Fresh())
        self.assertEqual([], client.sent)
        self.assertIsNone(client.client.GetView())

        # Factory rejects the old menu ID but delegates every native menu.
        menu_env = dict(HCEventWire=N(MENU_EVENTS=48538),
                        super=N(CreateScriptedMenu=lambda ident: ('native', ident)))
        translate((SCRIPTS/'5_Mission/Events/HCEventMenuFactory.c').read_text().replace('    override ', '    '),
                  'MissionBase', menu_env)
        self.assertIsNone(menu_env['CreateScriptedMenu'](N(), 48538))
        self.assertEqual(('native', 42), menu_env['CreateScriptedMenu'](N(), 42))
        translate((SCRIPTS/'5_Mission/Events/HCEventMenu.c').read_text().replace('    override ', '    '), 'HCEventMenu', menu_env)
        self.assertIsNone(menu_env['Init'](N()))

        pins = EArray([N(Label='stale quest')])
        info_env = {}
        translate((SCRIPTS/'5_Mission/Groups/HCInfoLayers.c').read_text(),
                  'HCInfoEventSites', info_env, only=('Collect',))
        info_env['Collect'](N(Enabled=True, Rows=EArray([N()])), 15360, pins)
        self.assertEqual([], pins)
        clue = fixture.e['HCEventBriefing'].Describe(self.mission_with_vector(fixture))
        self.assertIn('Signs of activity', clue)
        self.assertNotIn('Collect', clue)

        # No players, enrollment or inventory ports exist in this fixture.
        run = director_fixture()
        self.assertTrue(run.owner.HCOffer(run.state.Chains[0]))
        self.assertEqual('pending', run.images[-1].Stories.HCFirstSurvivor.Phase)
        run.owner.HCStep(100)
        self.assertEqual(['pending', 'intent', 'active'],
                         [state.Stories.HCFirstSurvivor.Phase for state in run.images])
        self.assertEqual(1, sum(call[0] == 'begin' for call in run.calls))
        run.actors.HCObserve = lambda row: EStr('rescued')  # Unsupported observations never count.
        run.owner.HCStep(101)
        self.assertEqual('active', run.state.Stories.HCFirstSurvivor.Phase)
        run.actors.HCObserve = lambda row: EStr('dead')
        run.owner.HCStep(102)
        self.assertEqual('dead', run.images[-1].Stories.HCFirstSurvivor.Outcome)
        restored = director_fixture(run.images[-1])
        self.assertFalse(restored.owner.HCOffer(restored.state.Chains[0]))
        restored.owner.HCStep(103)
        self.assertFalse(any(call[0] == 'begin' for call in restored.calls))
        self.assertEqual('dead', restored.state.Stories.HCFirstSurvivor.Outcome)

        # A crash after intent/activation never rebinds or reports rescue/death.
        crashed = director_fixture(run.images[1])
        self.assertEqual('unknown', crashed.images[-1].Stories.HCFirstSurvivor.Outcome)
        crashed.owner.HCStep(104)
        self.assertFalse(any(call[0] == 'begin' for call in crashed.calls))
        barrier = director_fixture()
        barrier.owner.HCOffer(barrier.state.Chains[0])
        barrier.owner.m_Store.Save = lambda state: False
        barrier.owner.HCStep(100)
        self.assertTrue(barrier.owner.m_Fault)
        self.assertFalse(any(call[0] == 'begin' for call in barrier.calls))
        failed_count = len(barrier.calls)
        barrier.owner.HCStep(101)
        self.assertEqual(failed_count, len(barrier.calls))

        # Missing HC-10 claim cannot bind; expiry records uncertainty, no refill.
        refused = director_fixture()
        refused.owner.HCOffer(refused.state.Chains[0])
        refused.actors.HCSelect = lambda row: EStr('unowned-lease')
        refused.owner.HCStep(100)
        refused.owner.HCStep(101)
        self.assertFalse(any(call[0] == 'begin' for call in refused.calls))
        refused.owner.HCStep(200)
        self.assertEqual('unknown', refused.images[-1].Stories.HCFirstSurvivor.Outcome)
        stopped = director_fixture()
        stopped.owner.HCOffer(stopped.state.Chains[0])
        stopped.owner.HCStep(100)
        stopped.owner.HCClose()
        self.assertEqual('unknown', stopped.images[-1].Stories.HCFirstSurvivor.Outcome)
        self.assertEqual(1, sum(call[0] == 'end' for call in stopped.calls),
                         'close releases the actor binding exactly once')
        stop_count = len(stopped.calls)
        stopped.owner.HCStep(101)
        stopped.owner.HCClose()
        self.assertEqual(stop_count, len(stopped.calls), 'stop is idempotent and off does no work')
        # Failed closure barriers still release the observation binding once.
        # No durable success or actor outcome is inferred from the failure.
        for fault_before_close in (False, True):
            uncertain = director_fixture()
            uncertain.owner.HCOffer(uncertain.state.Chains[0])
            uncertain.owner.HCStep(100)
            uncertain.owner.m_Fault = fault_before_close
            uncertain.owner.m_Store.Save = lambda state: False
            uncertain.owner.HCClose()
            self.assertTrue(uncertain.owner.m_Fault)
            self.assertFalse(uncertain.owner.m_Enabled)
            self.assertEqual(1, sum(call[0] == 'end' for call in uncertain.calls))
            self.assertEqual('active', uncertain.images[-1].Stories.HCFirstSurvivor.Phase)
        off = director_fixture(enabled=False)
        off.owner.HCStep(100)
        self.assertFalse(off.owner.HCOffer(off.state.Chains[0]))
        self.assertEqual([], off.calls)

        # Execute the actual shipping adapter: no fabricated Expansion primitive.
        adapter_env = {}
        adapter_source = (ROOT/'mods/HollowCountryExpansionAI/scripts/4_World/HCXAISituationAdapter.c').read_text()
        translate(adapter_source.replace('    override ', '    '), 'HCXAISituationAdapter', adapter_env)
        self.assertFalse(adapter_env['HCReady'](N()))
        self.assertEqual('', adapter_env['HCSelect'](N(), N()))
        self.assertEqual('SURVIVOR_PLACEMENT_ACTION_API_UNVERIFIED', adapter_env['HCRefusal'](N()))
        unavailable = director_fixture()
        unavailable.actors.HCReady = lambda: False
        unavailable.actors.HCRefusal = lambda: adapter_env['HCRefusal'](N())
        unavailable.actors.HCSelect = lambda row: self.fail('unready adapter must not select/scan')
        unavailable.owner.HCOffer(unavailable.state.Chains[0])
        unavailable.owner.HCStep(100)
        unavailable.owner.HCStep(101)
        self.assertEqual('pending', unavailable.state.Stories.HCFirstSurvivor.Phase)
        self.assertEqual(1, sum('SURVIVOR_PLACEMENT_ACTION_API_UNVERIFIED' in line for line in unavailable.logs))
        self.assertFalse(any(call[0] == 'begin' for call in unavailable.calls))
        self.assertTrue(any('HC-38 opportunity=hc-story-5-survivor' in line and
                            'quest_ui=off' in line and 'runtime=PENDING' in line for line in run.logs))

        # HC-40 shares this one situation check. Explicitly synthetic HC-19
        # chain/parsed DTOs: execute authored validation, never model movement.
        transit_source = (SCRIPTS/'4_World/Events/HCTransitSituation.c').read_text()
        def dto(value):
            if isinstance(value, dict):
                return N(**{key: dto(item) for key, item in value.items()})
            if isinstance(value, list):
                return EArray(dto(item) for item in value)
            return EStr(value) if isinstance(value, str) else value
        manifest = dto(json.loads((ROOT/'mission/hollow-country/events/transit-situations.json').read_text()))
        class NativeInt(int):
            def ToString(self):
                return EStr(str(self))
        run.state.Stories.LegacyIds = EArray([EStr('synthetic-legacy')])
        story_identity = {}
        translate((SCRIPTS/'4_World/Scenes/HCStorySchedule.c').read_text(),
                  'HCStoryPolicy', story_identity, only=('HCIdentity',))
        policies = dict(HCSituationDirector=N(HCValid=run.owner.HCValid),
                        HCEventDirector=N(TextValid=lambda s, n: 0 < len(s) <= n),
                        HCStoryPolicy=N(HCIdentity=story_identity['HCIdentity']))
        translate(transit_source, 'HCTransitSituation', policies,
                  only=('HCProfileValid', 'HCManifestValid', 'HCIdentity', 'HCOpportunityValid'))
        self.assertTrue(policies['HCManifestValid'](manifest))
        self.assertEqual({'roadside', 'exodus'}, {p.Kind for p in manifest.Profiles})
        identities = []
        for profile in manifest.Profiles:
            identity = policies['HCIdentity'](run.state.Chains[0], profile)
            identities.append(identity)
            opportunity = N(Version=1, Id=identity, StorySequence=NativeInt(5), DueAt=100,
                            EndsAt=100 + profile.LifetimeSeconds, Phase=EStr('pending'),
                            Lease=EStr(''), Outcome=EStr(''), Refusal=EStr(''))
            self.assertTrue(policies['HCOpportunityValid'](profile, opportunity, run.state.Stories))
            opportunity.EndsAt += 1
            self.assertFalse(policies['HCOpportunityValid'](profile, opportunity, run.state.Stories))
            opportunity.EndsAt -= 1
            opportunity.Id = EStr('hc-story-5-survivor')
            self.assertFalse(policies['HCOpportunityValid'](profile, opportunity, run.state.Stories))
            for field, value in (('MaxExitNodes', 0), ('MaxMembers', 0),
                                 ('Reinforcements', 1), ('CollisionBarricades', True),
                                 ('CorridorPolicy', EStr('assume_clear')),
                                 ('ExitPolicy', EStr('teleport'))):
                unsafe = copy.deepcopy(profile)
                setattr(unsafe, field, value)
                self.assertFalse(policies['HCProfileValid'](unsafe), field)
        self.assertEqual(2, len(set(identities)))
        for invalid in (N(SchemaVersion=0, Profiles=manifest.Profiles),
                        N(SchemaVersion=1, Profiles=EArray([manifest.Profiles[0]])),
                        N(SchemaVersion=1, Profiles=EArray([manifest.Profiles[0]] * 2))):
            self.assertFalse(policies['HCManifestValid'](invalid))

        # Shipping transit adapter cannot select, command or invent an outcome.
        transit_adapter = {}
        translate((ROOT/'mods/HollowCountryExpansionAI/scripts/4_World/HCXAITransitAdapter.c')
                  .read_text().replace('    override ', '    '), 'HCXAITransitAdapter', transit_adapter)
        self.assertFalse(transit_adapter['HCReady'](N()))
        self.assertEqual('', transit_adapter['HCSelect'](N(), opportunity))
        self.assertFalse(transit_adapter['HCBegin'](N(), opportunity))
        self.assertEqual('', transit_adapter['HCObserve'](N(), opportunity))
        self.assertEqual('TRANSIT_PROVIDER_SOURCE_ROUTE_CLEARANCE_UNVERIFIED',
                         transit_adapter['HCRefusal'](N()))

        # Existing module owns lifecycle. Off/repeated open/stop do no IO or
        # actor work; each start reports two bounded refusal/off diagnostics.
        def transit_boot(enabled, configured=manifest):
            loads, receipts, status = [], [], []
            lifecycle = dict(GetGame=lambda: N(IsServer=lambda: True),
                             HCV2Admission=N(Admitted=lambda preference: preference),
                             Print=receipts.append,
                             HCLoad=lambda: loads.append('load') or configured)
            cleaned = transit_source.replace('    protected ', '    ')
            translate(cleaned, 'HCTransitSituation', lifecycle,
                      only=('HCOpen', 'HCClose', 'HCReport', 'HCStatus'))
            owner = N(m_Opened=False, m_Closed=False, m_Authored=0, m_Manifest=None,
                      m_Effective=EStr('off'), m_Reason=EStr('not_started'),
                      m_Status=N(HCPublish=lambda *args: status.append(args)))
            for name in ('HCOpen', 'HCClose', 'HCReport', 'HCStatus'):
                setattr(owner, name, MethodType(lifecycle[name], owner))
            owner.HCOpen(enabled)
            owner.HCOpen(enabled)
            self.assertEqual(2, len(receipts))
            self.assertTrue(all('lease=none' in line and 'runtime=PENDING' in line for line in receipts))
            return owner, loads, receipts, status
        transit_off, off_loads, _, off_status = transit_boot(False)
        self.assertEqual([], off_loads)
        self.assertEqual(('off', 'operator_off'), off_status[-1])
        transit_on, on_loads, on_receipts, on_status = transit_boot(True)
        self.assertEqual(['load'], on_loads)
        self.assertEqual(('refused', 'TRANSIT_PROVIDER_SOURCE_ROUTE_CLEARANCE_UNVERIFIED'), on_status[-1])
        self.assertTrue(all('authored=1 admitted=0 observed=0' in line for line in on_receipts))
        transit_on.HCClose()
        close_receipts = len(on_receipts)
        transit_on.HCClose()
        transit_on.HCOpen(True)
        self.assertEqual(close_receipts, len(on_receipts))
        self.assertEqual(['load'], on_loads)
        self.assertEqual(('off', 'owner_closed'), on_status[-1])
        _, bad_loads, _, bad_status = transit_boot(True, None)
        self.assertEqual(['load'], bad_loads)
        self.assertEqual(('refused', 'TRANSIT_MANIFEST_INVALID'), bad_status[-1])

    @staticmethod
    def mission_with_vector(fixture):
        return N(SiteId='synthetic-site', Source=N(ToString=lambda: '<1, 0, 1>'))


if __name__ == '__main__':
    unittest.main()
