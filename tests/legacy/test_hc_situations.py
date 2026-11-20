"""HC-38 / #147/#148: authored handlers; explicit synthetic ports, no DayZ proof.

Spec: independent survivor opportunity, no quest UI or client reward authority.
Plan/task: pin one HC-19 identity, reuse its store and HC-10 lease, retire UI.
Native placement/actions, emotes and two-client acceptance remain pending.

Wave 7 / #186, HC-38/39/40: consume the live HC-19 source and addon ports;
refused ports must not consume one-row-per-profile history. The supplied task
is the spec/plan/task trace; both AGENTS.md spec paths are absent here.
Actual RED (2026-11-19), before source edits:
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_situations -v
  AssertionError: namespace(Version=1, Profile='survivor', Id='hc-story-5-survivor', StorySequence=5, DueAt=100, EndsAt=200, Phase='pending', Outcome='', Lease='', Refusal='') is not None : unready survivor port must not consume durable history
  Ran 1 test; FAILED (failures=1).
  Scene-binding helper also failed: exact live state was not bound.
  Addon startup check failed: unexpectedly None : successful addon bind must install the survivor port.
  Null-clear helper failed: clearing an unbound source has no owner to close.
GREEN:
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_situations test_expansion_ai_adapter test_hc_story_module test_event_integration test_event_runtime test_core_lifecycle test_v1_combined_flags -v
  Ran 200 tests; OK (expected failures=1, existing combined-work budget case).
The broader affected-file run needs lead fixture-only updates in the read-only
modules test_hc_ai_trade (situation binding ports + service Adapter getter) and
test_hc_wildlife (HCStoryArrived port). Their current missing-port errors are
not DayZ evidence; applying those exact fixture updates in memory ran 2 tests,
OK, without changing either file. Native runtime acceptance remains PENDING.

Round 2 (#147): replace obsolete mint/permanent-refusal expectations with
existing physical stock and shared live-provider ports. Preserve finite stock,
no-refill, same-handle, no-delete and admission assertions. All fixtures synthetic.
"""
import copy
import json
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.legacy import test_event_transport as transport
from tests.legacy import test_event_ui as ui
from tests.legacy.test_group_server import EArray
from tests.legacy.test_map_layers import EStr, methods, translate
from types import MethodType

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mods/HollowCountry/scripts'


def cached_status():
    """Execute the HC-1 cache, with explicit synthetic native strings."""
    env = {}
    source = (SCRIPTS/'3_Game/HCOperationalStatus.c').read_text().replace('    protected ', '    ')
    translate(source, 'HCOperationalStatus', env, only=('HCPublish', 'HCState', 'HCReason'))
    owner = N(m_State=EStr('unknown'), m_Reason=EStr('owner_state_unknown'), m_Readiness=EStr('unknown'))
    for name in ('HCPublish', 'HCState', 'HCReason'):
        setattr(owner, name, MethodType(env[name], owner))
    return owner


def director_fixture(image=None, enabled=True, fail=False, ready=True):
    """Explicit synthetic DTO, HC-19 save barrier, HC-10 claim and actor port.

    Actor requests are counted, never claimed as executed in DayZ. No Python
    gameplay policy: all transitions/retirement decisions execute Enforce bodies.
    """
    source = (SCRIPTS/'4_World/Events/HCSituationDirector.c').read_text()
    source = source.replace('    protected ', '    ').replace('array<string> ', 'EArray ').replace('array<ref HCSituationProfileRow>', 'Slots')
    chain = N(Id=EStr('hc-story-5'), StorySequence=5, DueAt=100, ExpiresAt=200,
              Complete=False, Cancelled=False)
    state = copy.deepcopy(image) if image else N(LastNow=100,
        Stories=N(LegacyThrough=4, NextSequence=6, HCFirstSurvivor=None, HCSituations=None), Chains=EArray([chain]))
    calls, logs, images, selected_profiles = [], [], [], []
    actors = N(HCReady=lambda: ready, HCRefusal=lambda: EStr('NO_OBSERVED_SURVIVOR'),
               HCSelect=lambda row: EStr('synthetic-owned-lease'),
               HCBegin=lambda row: calls.append(('begin', row.Lease)) or True,
               HCObserve=lambda row: EStr(''), HCEnd=lambda row: calls.append(('end', row.Lease)))
    def save(value):
        calls.append(('save', value.Stories.HCFirstSurvivor.Phase))
        if fail:
            return False
        images.append(copy.deepcopy(value))
        return True
    refused = N(HCReady=lambda: False, HCRefusal=lambda: EStr('PROFILE_PROVIDER_UNAVAILABLE'),
                HCSelect=lambda row: (_ for _ in ()).throw(AssertionError('refused select')),
                HCBegin=lambda row: (_ for _ in ()).throw(AssertionError('refused begin')),
                HCObserve=lambda row: EStr(''), HCEnd=lambda row: calls.append(('end-refused', row.Lease)))
    def profile_port(profile):
        selected_profiles.append(profile)
        return actors if profile == 'survivor' else refused
    env = dict(GetGame=lambda: N(IsServer=lambda: True), Print=logs.append,
               FileExist=lambda path: False,
               HCV2Admission=N(Admitted=lambda preference: preference, Line=lambda *args: 'synthetic admission runtime=PENDING'),
               HCStoryPolicy=N(HCValid=lambda s: True),  # Synthetic already-admitted HC-19 owner.
               HCEventDirector=N(TextValid=lambda s, n: 0 < len(s) <= n),
               HCSituationActors=N(HCGet=lambda: actors, HCForProfile=profile_port),
               HCSituationLimits=N(MAX_PROFILE_ROWS=5), EArray=EArray,
               HCSituationProfileRow=lambda: N(Profile=EStr(''), Enabled=False,
                   LifetimeSeconds=0, Attempted=False, Opportunity=None, Actors=None),
               HCWorldMaterializer=N(HCIdentity=lambda lease: object() if lease == 'synthetic-owned-lease' else None),
               HCSituationState=lambda: N(Version=1, Profile=EStr(''), Id=EStr(''), StorySequence=0, DueAt=0,
                   EndsAt=0, Phase=EStr('pending'), Outcome=EStr(''), Lease=EStr(''), Refusal=EStr('')),
               HCOperationalStatus=lambda: N(HCPublish=lambda *args: calls.append(('status', args))))
    table, _ = methods(source, 'HCSituationDirector')
    translate(source, 'HCSituationDirector', env)
    owner = N(m_State=None, m_Store=None, m_Actors=None, m_Enabled=False,
              m_Rows=EArray(), m_Cursor=0, m_Status=cached_status(),
              m_Fault=False, m_Attempted=False, m_Effective=EStr('off'), m_Reason=EStr('not_started'),
              m_Units=N(HCReset=lambda n: calls.append(('units', n)), HCTake=lambda n: True),
              m_Work=N(HCReset=lambda n: None, HCContinue=lambda: True))
    for name, (static, _, _) in table.items():
        setattr(owner, name, env[name] if static else MethodType(env[name], owner))
    owner.HCOpen(state, N(Save=save), enabled)
    return N(owner=owner, state=state, actors=actors, calls=calls, logs=logs, images=images, selected_profiles=selected_profiles, refused=refused)


class SituationBehavior(unittest.TestCase):
    def test_independent_lifecycle_and_retired_quest_requests(self):
        self.check_refused_arrival()
        self.check_scene_binding()
        self.check_named_profile_wiring()
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
        adapter_env = dict(HCW38SituationRuntime=N(HCReady=lambda: False,
            HCReason=lambda: EStr('LIVE_PARTY_PENDING'), HCSelect=lambda row: EStr(''),
            HCBegin=lambda row: False, HCObserve=lambda row: EStr('')))
        adapter_source = (ROOT/'mods/HollowCountryExpansionAI/scripts/4_World/HCXAISituationAdapter.c').read_text()
        translate(adapter_source.replace('    override ', '    '), 'HCXAISituationAdapter', adapter_env)
        self.assertFalse(adapter_env['HCReady'](N()))
        self.assertEqual('', adapter_env['HCSelect'](N(), N()))
        self.assertEqual('LIVE_PARTY_PENDING', adapter_env['HCRefusal'](N()))
        unavailable = director_fixture()
        unavailable.actors.HCReady = lambda: False
        unavailable.actors.HCRefusal = lambda: adapter_env['HCRefusal'](N())
        unavailable.actors.HCSelect = lambda row: self.fail('unready adapter must not select/scan')
        unavailable.owner.HCOffer(unavailable.state.Chains[0])
        unavailable.owner.HCStep(100)
        unavailable.owner.HCStep(101)
        self.assertIsNone(unavailable.state.Stories.HCFirstSurvivor)
        self.assertEqual([], unavailable.images)
        self.assertEqual(1, sum('LIVE_PARTY_PENDING' in line for line in unavailable.logs))
        self.assertFalse(any(call[0] == 'begin' for call in unavailable.calls))

        # HC-39 uses this same lifecycle validator/test. Synthetic references
        # exercise authored admission only; no route/actor success is fabricated.
        self.check_raid_profiles()
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
            opportunity = N(Version=1, Profile=EStr(''), Id=identity, StorySequence=NativeInt(5), DueAt=100,
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

        # Explicit unready shared-runtime port: adapter must forward its refusal.
        transit_adapter = dict(HCW38SituationRuntime=N(HCReady=lambda: False,
            HCReason=lambda: EStr('LIVE_PARTY_PENDING'), HCSelect=lambda row: EStr(''),
            HCBegin=lambda row: False, HCObserve=lambda row: EStr('')))
        translate((ROOT/'mods/HollowCountryExpansionAI/scripts/4_World/HCXAITransitAdapter.c')
                  .read_text().replace('    override ', '    '), 'HCXAITransitAdapter', transit_adapter)
        self.assertFalse(transit_adapter['HCReady'](N()))
        self.assertEqual('', transit_adapter['HCSelect'](N(), opportunity))
        self.assertFalse(transit_adapter['HCBegin'](N(), opportunity))
        self.assertEqual('', transit_adapter['HCObserve'](N(), opportunity))
        self.assertEqual('LIVE_PARTY_PENDING',
                         transit_adapter['HCRefusal'](N()))

        # Existing module owns lifecycle. Off/repeated open/stop do no IO or
        # actor work; each start reports two bounded refusal/off diagnostics.
        def transit_boot(enabled, configured=manifest):
            loads, receipts, status = [], [], []
            lifecycle = dict(GetGame=lambda: N(IsServer=lambda: True),
                             FileExist=lambda path: False,
                             HCV2Admission=N(Admitted=lambda preference: preference, Line=lambda *args: 'synthetic admission runtime=PENDING'),
                             Print=receipts.append,
                             HCSituationActors=N(HCForProfile=lambda profile: N(HCReady=lambda: False, HCRefusal=lambda: EStr('LIVE_PARTY_PENDING'))),
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
            self.assertEqual(1, sum('HC-40' in line for line in receipts))
            self.assertTrue(all('runtime=PENDING' in line for line in receipts))
            return owner, loads, receipts, status
        transit_off, off_loads, _, off_status = transit_boot(False)
        self.assertEqual([], off_loads)
        self.assertEqual(('off', 'operator_off'), off_status[-1])
        transit_on, on_loads, on_receipts, on_status = transit_boot(True)
        self.assertEqual(['load'], on_loads)
        self.assertEqual(('refused', 'LIVE_PARTY_PENDING'), on_status[-1])
        self.assertTrue(all('authored=2 admitted=0 observed=0' in line for line in on_receipts if 'HC-40' in line))
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

    def check_named_profile_wiring(self):
        run = director_fixture()
        names = ('survivor', 'raid', 'column', 'roadside-position', 'threatened-exodus')
        self.assertEqual(list(names), [slot.Profile for slot in run.owner.m_Rows])
        self.assertEqual(5, run.owner.HCCount())
        self.assertFalse(run.owner.HCEnableProfile('sixth', True, 0))
        for name in names[1:]:
            self.assertTrue(run.owner.HCEnableProfile(name, True, 0))
        run.refused.HCReady = lambda: True  # Explicit synthetic readiness for all five profiles.
        self.assertTrue(run.owner.HCOffer(run.state.Chains[0]))
        run.refused.HCReady = lambda: False
        self.assertEqual(1, len(run.images), 'all named offers share one durable barrier')
        self.assertEqual(4, len(run.state.Stories.HCSituations))
        self.assertEqual(5, len({row.Id for row in
            [run.state.Stories.HCFirstSurvivor] + run.state.Stories.HCSituations}))
        self.assertFalse(run.owner.HCOffer(run.state.Chains[0]))
        self.assertEqual(1, len(run.images), 'retained identities never replay')
        # One retained row per budgeted step, with independent attempts/leases.
        for _ in names:
            run.owner.HCStep(100)
        self.assertEqual(1, sum(call[0] == 'begin' for call in run.calls))
        self.assertTrue(all(row.Phase == 'pending' for row in run.state.Stories.HCSituations))
        self.assertEqual(list(names), run.selected_profiles[:5])
        self.assertIs(run.owner.HCStatus(), run.owner.HCStatus())
        legacy = copy.deepcopy(run.images[0])
        legacy.Stories.HCSituations = None  # Native absent additive array.
        old = director_fixture(legacy)
        self.assertEqual(5, old.owner.HCCount())
        self.assertEqual('pending', old.state.Stories.HCFirstSurvivor.Phase)
        corrupt = copy.deepcopy(run.images[0])
        corrupt.Stories.HCSituations.append(copy.deepcopy(corrupt.Stories.HCSituations[0]))
        self.assertFalse(director_fixture(corrupt).owner.m_Enabled)
        zero_version = copy.deepcopy(run.images[0])
        zero_version.Stories.HCSituations[0].Version = 0
        self.assertFalse(director_fixture(zero_version).owner.m_Enabled)
        # Native boot 076: a JSON-loaded first survivor came back fully zero-filled
        # (Version 0, no id/phase); it carries no state and is treated as absent.
        zero_filled = copy.deepcopy(run.images[0])
        zero_filled.Stories.HCFirstSurvivor = N(Version=0, Profile=EStr(''), Id=EStr(''), StorySequence=0, DueAt=0,
            EndsAt=0, Phase=EStr(''), Outcome=EStr(''), Lease=EStr(''), Refusal=EStr(''))
        reopened = director_fixture(zero_filled)
        self.assertTrue(reopened.owner.m_Enabled)
        self.assertIsNone(reopened.state.Stories.HCFirstSurvivor)
        partial = copy.deepcopy(zero_filled)
        partial.Stories.HCFirstSurvivor.Id = EStr('hc-story-5-survivor')
        self.assertFalse(director_fixture(partial).owner.m_Enabled, 'a version-0 row with state is still refused')
        duplicate_lease = copy.deepcopy(run.images[0])
        for row in duplicate_lease.Stories.HCSituations[:2]:
            row.Lease, row.Phase = EStr('synthetic-owned-lease'), EStr('active')
        self.assertFalse(director_fixture(duplicate_lease).owner.m_Enabled)
        # Existing restricted actor selection dispatches by exact profile.
        actor_source = (SCRIPTS/'4_World/Events/HCSituationDirector.c').read_text()
        actor_source = actor_source.replace('s_Adapter', 'HCSituationActors.s_Adapter')
        actor_source = actor_source.replace('s_Raid', 'HCSituationActors.s_Raid')
        actor_source = actor_source.replace('s_Transit', 'HCSituationActors.s_Transit')
        actor_source = actor_source.replace('s_Unavailable', 'HCSituationActors.s_Unavailable')
        registry = N(s_Adapter=object(), s_Raid=object(), s_Transit=object(), s_Unavailable=object())
        actor_env = dict(HCSituationActors=registry)
        translate(actor_source, 'HCSituationActors', actor_env,
                  only=('HCForProfile', 'HCBind', 'HCBindRaid', 'HCBindTransit'))
        for name, expected in zip(names, (registry.s_Adapter, registry.s_Raid, registry.s_Raid,
                                           registry.s_Transit, registry.s_Transit)):
            self.assertIs(expected, actor_env['HCForProfile'](name))
        self.assertIs(registry.s_Unavailable, actor_env['HCForProfile']('unknown'))
        for binder in ('HCBind', 'HCBindRaid', 'HCBindTransit'):
            actor_env[binder](None)
            actor_env[binder](None)
        for name in names:
            self.assertIs(registry.s_Unavailable, actor_env['HCForProfile'](name))
        self.check_module_wiring()

    def check_refused_arrival(self):
        # #186: bound HC-19 source, shipping-style refused ports. Execute the
        # actual server arrival callback; no Python situation policy is modeled.
        run = director_fixture(ready=False)
        run.actors.HCRefusal = lambda: EStr('SURVIVOR_PLACEMENT_ACTION_API_UNVERIFIED')
        for profile in ('raid', 'column', 'roadside-position', 'threatened-exodus'):
            run.owner.HCEnableProfile(profile, True, 0)
        module = N(m_SituationEnabled=True, m_Situations=run.owner)
        env = dict(HCEventModule=N(s_SituationOwner=module))
        source = (SCRIPTS/'4_World/Events/HCEventModule.c').read_text()
        source = source.replace('s_SituationOwner', 'HCEventModule.s_SituationOwner')
        translate(source, 'HCEventModule', env, only=('HCStoryArrived', 'HCOfferSituation'))
        module.HCOfferSituation = MethodType(env['HCOfferSituation'], module)
        for _ in range(2):
            env['HCStoryArrived'](run.state.Chains[0])
        self.assertIsNone(run.state.Stories.HCFirstSurvivor,
                          'unready survivor port must not consume durable history')
        self.assertIsNone(run.state.Stories.HCSituations)
        self.assertEqual([], run.images, 'refused arrivals perform no save')
        self.assertEqual(('refused', 'SURVIVOR_PLACEMENT_ACTION_API_UNVERIFIED'),
                         (run.owner.HCStatus().HCState(), run.owner.HCStatus().HCReason()))
        self.assertIn('[HC Plan] HC-38 opportunity=none phase=none quest_ui=off state=refused refusal=SURVIVOR_PLACEMENT_ACTION_API_UNVERIFIED pinned=0 count_cap=1 runtime=PENDING', run.logs)
        self.assertEqual(1, sum('SURVIVOR_PLACEMENT_ACTION_API_UNVERIFIED' in line for line in run.logs))
        # A later trusted ready port can consume the still-unused profile once.
        run.actors.HCReady = lambda: True
        env['HCStoryArrived'](run.state.Chains[0])
        env['HCStoryArrived'](run.state.Chains[0])
        self.assertEqual('pending', run.state.Stories.HCFirstSurvivor.Phase)
        self.assertEqual(1, len(run.images))
        self.assertIsNone(run.state.Stories.HCSituations)

    def check_scene_binding(self):
        from tests.legacy.test_hc_story_module import StoryModuleBehavior
        # Synthetic store/scheduler/native lifecycle; authored Scenes methods
        # must bind the exact owner and push only the newly saved identity.
        fixture = StoryModuleBehavior()
        owner = fixture.owner()
        owner.m_Running = False
        owner.m_AdmissionPrinted = True
        owner.m_SummaryPrinted = True
        owner.IsEnabled = lambda settings: True
        state = owner.m_State
        bound = N(state=None, store=None)
        def bind_source(live, store):
            bound.state, bound.store = live, store
            fixture.calls.append(('bind',))
        def clear_source(live):
            if bound.state is live:
                bound.state, bound.store = None, None
                fixture.calls.append(('clear',))
        fixture.env.update(
            GetGame=lambda: N(IsServer=lambda: True, GetWorldName=lambda: 'chernarusplus', GetTickTime=lambda: 20.),
            HCSceneChainStore=lambda: N(Open=lambda now: state),
            HCStoryPolicy=N(HCLoadConfig=lambda: N()),
            HCStorySchedule=lambda: N(HCStart=lambda *args: True,
                                     HCStop=lambda: fixture.calls.append(('story-stop',))),
            HCSituationSource=N(HCBind=bind_source, HCClear=clear_source),
            HCSceneSaveJob=lambda: N(HCDirty=False, HCInFlight=False, HCDue=0),
            HCSaveScheduler=N(HCRegister=lambda job: None, HCFlush=lambda job: None, HCUnregister=lambda job: None))
        fixture.bind(owner, 'OnStart', 'OnStop', 'SaveBarrierDone', 'StoryStep')
        owner.OnStart(N())
        owner.OnStart(N())
        self.assertIs(state, bound.state)
        self.assertIs(owner.m_Store, bound.store)
        self.assertEqual(1, fixture.calls.count(('bind',)))
        old = N(Id='synthetic-old', StorySequence=1)
        arrived = N(Id='synthetic-new', StorySequence=2)
        state.Chains = EArray([old, arrived])
        state.Stories.NextSequence = 2
        def issue(now, released):
            state.Stories.NextSequence = 3
            fixture.calls.append(('story-saved',))
            return True
        owner.m_Stories.HCReady = lambda: True
        owner.m_Stories.HCCandidate = lambda: None
        owner.m_Stories.HCStep = issue
        # Wildlife unavailable must not suppress the independent event callback.
        fixture.env['HCEcologyRuntimeModule'] = N(HCEventWildlife=lambda: None)
        fixture.env['HCEventModule'] = N(HCEventStoryArrived=lambda chain: fixture.calls.append(('arrived', chain)))
        fixture.bind(owner, 'StoryStep')
        owner.StoryStep(1000)
        self.assertIn(('arrived', arrived), fixture.calls)
        self.assertLess(fixture.calls.index(('story-saved',)), fixture.calls.index(('arrived', arrived)))
        fixture.calls.clear()
        owner.m_Stories.HCStep = lambda *args: True  # Retirement save, no new identity.
        owner.StoryStep(1001)
        self.assertNotIn(('arrived', arrived), fixture.calls)
        owner.OnStop()
        owner.OnStop()
        self.assertIsNone(bound.state)
        self.assertIsNone(bound.store)
        self.assertEqual(1, fixture.calls.count(('clear',)))
        self.assertLess(fixture.calls.index(('clear',)), fixture.calls.index(('story-stop',)))

    def check_module_wiring(self):
        source = (SCRIPTS/'4_World/Events/HCEventModule.c').read_text()
        for fragment in ('new HCSituationDirector', 'new HCCampRaidSituation',
                         'new HCTransitSituation', 'm_Situations.HCStep(',
                         'm_Situations.HCClose()', 'm_Raids.HCClose()',
                         'm_Transit.HCClose()', 'override HCOperationalStatus HCGetOperationalStatus()'):
            self.assertIn(fragment, source)
        source = source.replace('    protected ', '    ').replace('    override ', '    ')
        for field in ('s_SituationOwner', 's_Instance', 's_CleanupOwner'):
            source = source.replace(field, 'HCEventModule.' + field)
        source = source.replace('this', 'self').replace('array<ref HCEventMission> ', 'Roster ')
        raid_source = (SCRIPTS/'4_World/Events/HCCampRaidSituation.c').read_text().replace('    protected ', '    ').replace('s_Profiles', 'raid_registry.profiles')
        transit_source = (SCRIPTS/'4_World/Events/HCTransitSituation.c').read_text().replace('    protected ', '    ')
        raid_json = json.loads((ROOT/'mission/hollow-country/events/raids.json').read_text())
        transit_json = json.loads((ROOT/'mission/hollow-country/events/transit-situations.json').read_text())
        def dto(value):
            if isinstance(value, dict):
                return N(**{key: dto(item) for key, item in value.items()})
            if isinstance(value, list):
                return EArray(dto(item) for item in value)
            return EStr(value) if isinstance(value, str) else value
        raid_config, transit_config = dto(raid_json), dto(transit_json)
        for enabled, bind_source in ((True, True), (False, True), (True, False)):
            loads, receipts, published, directors = [], [], [], []
            upstream = director_fixture()
            bound = N(state=upstream.state if bind_source else None,
                      store=upstream.owner.m_Store if bind_source else None)
            native = N(game=N(IsServer=lambda: True, GetTickTime=lambda: 200))
            common = dict(GetGame=lambda: native.game,
                          FileExist=lambda path: False,
                          HCV2Admission=N(Admitted=lambda preference: preference, Line=lambda *args: 'synthetic admission runtime=PENDING'), Print=receipts.append)
            def raid_factory():
                env = dict(common, raid_registry=N(profiles=None), HCCampRaidActors=N(HCGet=lambda: N(HCReady=lambda: False, HCRefusal=lambda: EStr('RAID_PROVIDER_UNAVAILABLE'))))
                table, _ = methods(raid_source, 'HCCampRaidSituation')
                translate(raid_source, 'HCCampRaidSituation', env,
                          only=tuple(name for name in table if name != 'HCLoad'))
                owner = N(m_Config=None, m_Enabled=False, m_Reports=0, m_Status=cached_status(),
                          m_Effective=EStr('off'), m_Reason=EStr('not_started'))
                for name, (static, _, _) in table.items():
                    if name != 'HCLoad':
                        setattr(owner, name, env[name] if static else MethodType(env[name], owner))
                return owner
            def transit_factory():
                env = dict(common, HCLoad=lambda: loads.append('transit') or transit_config,
                           HCSituationActors=N(HCForProfile=lambda profile: N(HCReady=lambda: False, HCRefusal=lambda: EStr('LIVE_PARTY_PENDING'))))
                names = ('HCOpen', 'HCClose', 'HCReport', 'HCStatus', 'HCFind')
                translate(transit_source, 'HCTransitSituation', env, only=names)
                owner = N(m_Opened=False, m_Closed=False, m_Manifest=None, m_Authored=0,
                          m_Status=cached_status(), m_Effective=EStr('off'), m_Reason=EStr('not_started'))
                for name in names:
                    setattr(owner, name, MethodType(env[name], owner))
                return owner
            def director_factory():
                run = director_fixture(enabled=False)
                run.actors.HCReady = lambda: False
                directors.append(run)
                return run.owner
            # Static load and instance construction are distinct authored ports.
            raid_factory.HCLoad = lambda: loads.append('raid') or raid_config
            module_type = N(s_SituationOwner=None, s_Instance=None, s_CleanupOwner=None)
            env = dict(common, HCEventModule=module_type,
                       HCSituationDirector=director_factory, HCCampRaidSituation=raid_factory,
                       HCTransitSituation=transit_factory,
                       # Shipping transit port: unbound, so the unavailable port refuses.
                       HCSituationActors=N(HCForProfile=lambda profile: N(HCReady=lambda: False, HCRefusal=lambda: EStr('LIVE_PARTY_PENDING'))),
                       HCSituationSource=N(HCState=lambda: bound.state, HCStore=lambda: bound.store),
                       HCGroupClock=N(Utc=lambda: 1577836900),
                       HCOperationalContributors=N(HCRegisterOwner=lambda name:
                           N(HCObserve=lambda requested, status, now: published.append((name, requested, status.HCState())))))
            names = ('HCStartSituations', 'HCStepSituations', 'HCPublishSituations',
                     'HCCloseSituations', 'HCGetOperationalStatus', 'HCStartRefused', 'OnStart', 'OnTick', 'OnStop')
            translate(source, 'HCEventModule', env, only=names)
            module = N(m_SituationStatus=cached_status(), m_Situations=None, m_Raids=None,
                       m_Transit=None, m_Runtime=None, m_EventRPC=None, m_Config=N(Enabled=False),
                       m_StartRefusal='')
            for name in names:
                setattr(module, name, MethodType(env[name], module))
            module.OnStart(N(EnableEncounters=enabled))
            director, raids, transit = module.m_Situations, module.m_Raids, module.m_Transit
            self.assertEqual(['raid', 'transit'] if enabled else [], loads)
            self.assertEqual(1, sum('HC-39' in line for line in receipts))
            self.assertEqual(1, sum('HC-40' in line for line in receipts))
            self.assertEqual('refused' if enabled else 'off', raids.HCStatus().HCState())
            self.assertEqual('refused' if enabled else 'off', transit.HCStatus().HCState())
            self.assertIs(raids.HCStatus(), raids.HCStatus())
            self.assertIs(transit.HCStatus(), transit.HCStatus())
            self.assertIs(module.HCGetOperationalStatus(), module.HCGetOperationalStatus())
            for _ in range(12):
                module.OnTick(1)
            self.assertEqual(['raid', 'transit'] if enabled else [], loads, 'tick never reloads manifests')
            self.assertIsNone(upstream.state.Stories.HCFirstSurvivor)
            self.assertEqual(0, len(upstream.state.Stories.HCSituations or []),
                'unready transit providers write no durable situation rows')
            rows = [getattr(row, 'Profile', '') for row in (upstream.state.Stories.HCSituations or [])]
            # A refused transit port must not write durable rows: history admits one
            # row per profile, so an unready provider would burn the profile for the world.
            self.assertNotIn('roadside-position', rows)
            self.assertNotIn('threatened-exodus', rows)
            self.assertFalse(any(call[0] == 'begin' for run in directors for call in run.calls),
                             'shipping-style refused ports never begin an actor action')
            self.assertEqual(0, len(upstream.images))
            self.assertEqual('off', module.HCGetOperationalStatus().HCState(), 'legacy Events is disabled')
            module.m_Config.Enabled = True
            module.HCPublishSituations()
            if director.HCProviderPending():
                # Wave 16: director and source run, only the actor provider is missing.
                self.assertEqual('ready', module.HCGetOperationalStatus().HCState())
                self.assertEqual('situation_director_running_actor_provider_pending',
                                 module.HCGetOperationalStatus().HCReason())
            else:
                self.assertEqual(director.HCStatus().HCState(), module.HCGetOperationalStatus().HCState())
                self.assertEqual(director.HCStatus().HCReason(), module.HCGetOperationalStatus().HCReason())
            module.m_Config.Enabled = False
            module.HCPublishSituations()
            self.assertEqual(3, len({name for name, _, _ in published}))
            module.OnStop()
            count = len(receipts)
            module.OnStop()
            module.OnTick(1)
            self.assertEqual(count, len(receipts))
            self.assertEqual('off', module.HCGetOperationalStatus().HCState())
            self.assertIsNone(module.m_Situations)
            module.OnStart(N(EnableEncounters=enabled))
            self.assertIsNot(director, module.m_Situations)
            self.assertEqual(['raid', 'transit'] * 2 if enabled else [], loads)
            native.game = None  # Shutdown must still release/cache without a Game singleton.
            module.OnStop()

        # Exact shared binding clears only its own live source, after requesting
        # situation closure. There is no second state/store or null-before-close.
        source_port = (SCRIPTS/'4_World/Events/HCSituationDirector.c').read_text()
        source_port = source_port.replace('s_State', 'HCSituationSource.s_State')
        source_port = source_port.replace('s_Store', 'HCSituationSource.s_Store')
        registry = N(s_State=None, s_Store=None)
        closures = []
        ports = dict(HCSituationSource=registry,
                     HCEventModule=N(HCSourceClosing=lambda: closures.append((registry.s_State, registry.s_Store))))
        translate(source_port, 'HCSituationSource', ports)
        live_state, live_store = N(synthetic='state'), N(synthetic='store')
        ports['HCClear'](None)
        self.assertEqual([], closures, 'clearing an unbound source has no owner to close')
        ports['HCBind'](live_state, live_store)
        ports['HCBind'](live_state, live_store)
        ports['HCClear'](N(synthetic='other-owner'))
        self.assertEqual([], closures)
        self.assertIs(live_state, ports['HCState']())
        ports['HCClear'](live_state)
        ports['HCClear'](live_state)
        ports['HCClear'](None)
        self.assertEqual([(live_state, live_store)], closures)
        self.assertIsNone(ports['HCState']())
        self.assertIsNone(ports['HCStore']())

    def check_raid_profiles(self):
        manifest = json.loads((ROOT/'mission/hollow-country/events/raids.json').read_text())
        self.assertFalse(manifest['Enabled'])
        self.assertEqual(['raid', 'column'], [p['Kind'] for p in manifest['Profiles']])
        profile_rows = EArray(N(**p) for p in manifest['Profiles'])
        config = N(Version=manifest['Version'], Enabled=True, Profiles=profile_rows)
        calls, logs = [], []
        camp_clock = N(now=1000)  # Explicit synthetic UTC, distinct from HC-38's epoch.
        identity = N(HCPartyId=lambda: 'party:synthetic-raider', HCCargoId=lambda: 'cargo:synthetic-raider',
                     HCGeneration=lambda: 7, HCRouteId=lambda: 'route:synthetic-raider')
        target_identity = N(HCPartyId=lambda: 'holdout:synthetic-home', HCCargoId=lambda: 'cargo:synthetic-home',
                            HCGeneration=lambda: 7, HCCampId=lambda: 'camp:synthetic-home')
        camp = N(Level=1, Supply=8, Population=2,
                 Home=N(Id='synthetic-home', CacheRef=EStr('existing-native-cache'), FactionId='locals',
                        State='OCCUPIED', ReoccupyAfter=0))
        leases = {'synthetic-lease': identity, 'synthetic-target': target_identity}
        proposal = N(Id='synthetic-lease', Identity=identity, Kind='RAIDER', FactionId='raiders')
        opportunity = N(Version=1, Profile=EStr(''), Id=EStr('hc-story-5-raid'), StorySequence=5,
                        Phase='pending', DueAt=100, EndsAt=500, Lease=EStr(''),
                        Outcome='', Refusal=EStr(''))
        progress = N(LegacyThrough=4, NextSequence=6)
        adapter_env = dict(HCW38SituationRuntime=N(HCReady=lambda: False,
            HCReason=lambda: EStr('LIVE_PARTY_PENDING'), HCSelect=lambda row: EStr(''),
            HCBegin=lambda row: False, HCObserve=lambda row: EStr('')))
        adapter_source = (ROOT/'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIRaidAdapter.c').read_text()
        translate(adapter_source.replace('    override ', '    '), 'HCXAIRaidAdapter', adapter_env)
        self.assertFalse(adapter_env['HCReady'](N()))
        self.assertEqual('', adapter_env['HCSelect'](N(), opportunity))
        self.assertFalse(adapter_env['HCBegin'](N(), opportunity))
        self.assertEqual('', adapter_env['HCObserve'](N(), opportunity))
        provider = N(HCReady=lambda: False, HCRefusal=lambda: adapter_env['HCRefusal'](N()))
        env = dict(HCWorldLimits=N(Token=lambda s: bool(s) and len(s) <= 96),
                   HCAIPartyIdentity=N(HCValid=lambda value: value is not None),
                   HCWorldMaterializer=N(HCIdentity=lambda lease: leases.get(lease)),
                   HCHoldouts=N(Get=lambda: N(HCRoutineView=lambda claim: camp if claim is target_identity else None)),
                   HCWorldFactionCatalog=N(Relation=lambda a, b: -1 if (a, b) == ('raiders', 'locals') else 0),
                   HCSituationDirector=N(HCValid=director_fixture().owner.HCValid),
                   HCWorldClock=N(UTC=lambda: camp_clock.now), raid_registry=N(profiles=None),
                   FileExist=lambda path: False,
                   HCV2Admission=N(Admitted=lambda preference: preference, Line=lambda *args: 'synthetic admission runtime=PENDING'),
                   GetGame=lambda: N(IsServer=lambda: True), Print=logs.append,
                   HCCampRaidActors=N(HCGet=lambda: provider),
                   HCOperationalStatus=lambda: N(HCPublish=lambda *args: calls.append(args)))
        source = (SCRIPTS/'4_World/Events/HCCampRaidSituation.c').read_text().replace('    protected ', '    ').replace('s_Profiles', 'raid_registry.profiles')
        raid_methods, _ = methods(source, 'HCCampRaidSituation')
        translate(source, 'HCCampRaidSituation', env, only=tuple(name for name in raid_methods if name != 'HCLoad'))
        self.assertTrue(env['HCValidConfig'](config))
        config.Version = 0  # Native missing-int behavior: never silently upgrade or enable.
        self.assertFalse(env['HCValidConfig'](config))
        config.Version = 1
        profile_rows[0].PartyRole = 'COURIER'
        self.assertFalse(env['HCValidConfig'](config))
        profile_rows[0].PartyRole = 'RAIDER'

        def check(profile=profile_rows[0], last_ended=0, exit_ref='exit:surveyed', return_ref='return:surveyed', now=100):
            return env['HCValidate'](profile, opportunity, progress, proposal, 'synthetic-target',
                                     now, last_ended, exit_ref, return_ref)
        for profile in profile_rows:
            self.assertEqual('', check(profile))
            self.assertEqual('RAID_COOLDOWN_ACTIVE', check(profile, last_ended=99))
            self.assertEqual('RAID_COOLDOWN_UNOBSERVED', check(profile, last_ended=-1))
            self.assertEqual('RAID_ROUTE_EXITS_MISSING', check(profile, exit_ref=''))
            self.assertEqual('RAID_ROUTE_EXITS_MISSING', check(profile, return_ref=''))
        opportunity.Phase = 'closed'
        opportunity.Outcome = 'departed'
        self.assertEqual('RAID_SITUATION_NOT_PENDING', check())
        opportunity.Phase = 'pending'
        opportunity.Outcome = ''
        self.assertEqual('RAID_SITUATION_NOT_DUE', check(now=99))
        leases.pop('synthetic-lease')
        self.assertEqual('RAID_PARTY_LEASE_UNOWNED', check())
        leases['synthetic-lease'] = identity
        proposal.Kind = 'COURIER'
        self.assertEqual('RAID_PARTY_ROLE_MISMATCH', check())
        proposal.Kind = 'RAIDER'
        camp.Supply = 0
        self.assertEqual('RAID_FUNDED_TARGET_UNAVAILABLE', check())
        camp.Supply = 8
        camp.Home.ReoccupyAfter = 999
        self.assertEqual('', check(), 'camp UTC must not be compared to the HC-38 epoch')
        camp.Home.ReoccupyAfter = 1001
        self.assertEqual('RAID_TARGET_LOCKOUT', check())
        camp.Home.ReoccupyAfter = 0
        camp.Home.FactionId = 'raiders'
        self.assertEqual('RAID_TARGET_NOT_HOSTILE', check())
        camp.Home.FactionId = 'locals'
        # A column needs its owned party/route, but no target or camp raid.
        leases.pop('synthetic-target')
        self.assertEqual('', check(profile_rows[1]))
        self.assertEqual('RAID_TARGET_LEASE_UNOWNED', check())
        leases['synthetic-target'] = target_identity

        owner = N(m_Config=None, m_Enabled=False, m_Reports=0,
                  m_Status=N(HCPublish=lambda *args: None),
                  m_Effective=EStr('off'), m_Reason=EStr('not_started'))
        table, _ = methods(source, 'HCCampRaidSituation')
        for name, (static, _, _) in table.items():
            if name == 'HCLoad':
                continue
            setattr(owner, name, env[name] if static else MethodType(env[name], owner))
        owner.HCOpen(None, True)
        self.assertEqual('refused', owner.m_Effective, 'a failed config load must not look operator-disabled')
        self.assertEqual('RAID_CONFIG_INVALID', owner.m_Reason)
        config.Enabled = False
        owner.HCOpen(config, True)
        self.assertEqual('refused', owner.m_Effective, 'legacy Enabled is superseded by named opt-out')
        config.Enabled = True
        owner.HCOpen(config, False)
        self.assertEqual('off', owner.m_Effective)
        self.assertFalse(owner.HCAdmit(profile_rows[0], opportunity, progress, proposal,
                                      'synthetic-target', 100, 0, 'exit:surveyed', 'return:surveyed'))
        owner.HCOpen(config, True)
        self.assertEqual('refused', owner.m_Effective)
        self.assertFalse(owner.HCAdmit(profile_rows[0], opportunity, progress, proposal,
                                      'synthetic-target', 100, 0, 'exit:surveyed', 'return:surveyed'))
        self.assertEqual('LIVE_PARTY_PENDING', owner.m_Reason)
        # Explicit zero means a trusted durable owner observed no prior raid;
        # it is not inferred from deserializing a missing history field.
        self.assertTrue(any('HC-39 kind=raid party=party:synthetic-raider outcome=refused' in s
                            and 'observed=0' in s and 'runtime=PENDING' in s for s in logs))
        for _ in range(30):
            owner.HCAdmit(profile_rows[1], opportunity, progress, proposal,
                          '', 100, 0, 'exit:surveyed', 'return:surveyed')
        self.assertLessEqual(sum('HC-39' in line for line in logs), 16)
        owner.HCClose()
        self.assertFalse(owner.m_Enabled)
        self.assertEqual([], calls)  # No engine inventory, spawner, movement or save port exists.

    @staticmethod
    def mission_with_vector(fixture):
        return N(SiteId='synthetic-site', Source=N(ToString=lambda: '<1, 0, 1>'))


if __name__ == '__main__':
    unittest.main()
