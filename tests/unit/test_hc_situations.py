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

        # HC-39 uses this same lifecycle validator/test. Synthetic references
        # exercise authored admission only; no route/actor success is fabricated.
        self.check_raid_profiles()
        self.assertTrue(any('HC-38 opportunity=hc-story-5-survivor' in line and
                            'quest_ui=off' in line and 'runtime=PENDING' in line for line in run.logs))

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
        opportunity = N(Version=1, Id=EStr('hc-story-5-raid'), StorySequence=5,
                        Phase='pending', DueAt=100, EndsAt=500, Lease=EStr(''),
                        Outcome='', Refusal=EStr(''))
        progress = N(LegacyThrough=4, NextSequence=6)
        adapter_env = {}
        adapter_source = (ROOT/'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIRaidAdapter.c').read_text()
        translate(adapter_source.replace('    override ', '    '), 'HCXAIRaidAdapter', adapter_env)
        provider = N(HCRefusal=lambda: adapter_env['HCRefusal'](N()))
        env = dict(HCWorldLimits=N(Token=lambda s: bool(s) and len(s) <= 96),
                   HCAIPartyIdentity=N(HCValid=lambda value: value is not None),
                   HCWorldMaterializer=N(HCIdentity=lambda lease: leases.get(lease)),
                   HCHoldouts=N(Get=lambda: N(HCRoutineView=lambda claim: camp if claim is target_identity else None)),
                   HCWorldFactionCatalog=N(Relation=lambda a, b: -1 if (a, b) == ('raiders', 'locals') else 0),
                   HCSituationDirector=N(HCValid=director_fixture().owner.HCValid),
                   HCWorldClock=N(UTC=lambda: camp_clock.now),
                   HCV2Admission=N(Admitted=lambda preference: preference),
                   GetGame=lambda: N(IsServer=lambda: True), Print=logs.append,
                   HCCampRaidActors=N(HCGet=lambda: provider),
                   HCOperationalStatus=lambda: N(HCPublish=lambda *args: calls.append(args)))
        source = (SCRIPTS/'4_World/Events/HCCampRaidSituation.c').read_text().replace('    protected ', '    ')
        translate(source, 'HCCampRaidSituation', env)
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
                  m_Effective=EStr('off'), m_Reason=EStr('not_started'))
        table, _ = methods(source, 'HCCampRaidSituation')
        for name, (static, _, _) in table.items():
            setattr(owner, name, env[name] if static else MethodType(env[name], owner))
        owner.HCOpen(None, True)
        self.assertEqual('refused', owner.m_Effective, 'a failed config load must not look operator-disabled')
        self.assertEqual('RAID_CONFIG_INVALID', owner.m_Reason)
        config.Enabled = False
        owner.HCOpen(config, True)
        self.assertEqual('off', owner.m_Effective)
        config.Enabled = True
        owner.HCOpen(config, False)
        self.assertEqual('off', owner.m_Effective)
        self.assertFalse(owner.HCAdmit(profile_rows[0], opportunity, progress, proposal,
                                      'synthetic-target', 100, 0, 'exit:surveyed', 'return:surveyed'))
        owner.HCOpen(config, True)
        self.assertEqual('refused', owner.m_Effective)
        self.assertFalse(owner.HCAdmit(profile_rows[0], opportunity, progress, proposal,
                                      'synthetic-target', 100, 0, 'exit:surveyed', 'return:surveyed'))
        self.assertEqual('RAID_FOOT_ROUTE_COMBAT_CUSTODY_UNVERIFIED', owner.m_Reason)
        # Explicit zero means a trusted durable owner observed no prior raid;
        # it is not inferred from deserializing a missing history field.
        self.assertTrue(any('HC-39 kind=raid party=party:synthetic-raider outcome=refused' in s
                            and 'observed=0' in s and 'runtime=PENDING' in s for s in logs))
        for _ in range(30):
            owner.HCAdmit(profile_rows[1], opportunity, progress, proposal,
                          '', 100, 0, 'exit:surveyed', 'return:surveyed')
        self.assertLessEqual(len(logs), 16)
        owner.HCClose()
        self.assertFalse(owner.m_Enabled)
        self.assertEqual([], calls)  # No engine inventory, spawner, movement or save port exists.

    @staticmethod
    def mission_with_vector(fixture):
        return N(SiteId='synthetic-site', Source=N(ToString=lambda: '<1, 0, 1>'))


if __name__ == '__main__':
    unittest.main()
