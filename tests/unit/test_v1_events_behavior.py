"""V1 events: authored Enforce under explicit synthetic native collaborators.
These fixtures do not establish CE provenance, persistence durability or gameplay.
"""
import copy
import json
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest
from tests.unit.test_event_runtime import ROOT, environment, translate, Handle
from tests.unit import test_event_runtime as event_fixtures
from tests.unit import test_event_integration as integration_fixtures
from tests.unit import test_event_ui as ui_fixtures
from tests.unit import test_event_transport as transport_fixtures
from tests.unit.test_group_server import EArray


def load_class(filename, owner, env):
    source = (ROOT / ('4_World/Events/' + filename)).read_text()
    start = source.index('class ' + owner)
    source = source[start:]
    following = source.find('\nclass ', 1)
    if following >= 0: source = source[:following]
    cls = type(owner, (), {})
    env[owner] = cls
    for static, name in re.findall(r'^    (?:override )?(static )?(?:bool|int|float|string|void|HCEvent\w+|array<[^>]+>) (\w+)\(', source, re.M):
        fn = translate(source, name, env, owner, not bool(static))
        setattr(cls, name, staticmethod(fn) if static else fn)
    return cls


class V1NativeObjectives(unittest.TestCase):
    def setUp(self):
        fixture = event_fixtures.NativeObservationTests(); fixture.setUp()
        self.f = fixture; self.e = fixture.e; self.o = fixture.o
        self.mission = fixture.mission; self.run = fixture.run
        self.player = fixture.player; self.item = fixture.item
        self.item.parent = None
        self.item.GetHierarchyParent = lambda: self.item.parent
        self.container = Handle(identity='', position=[30., 0., 40.], kind='SyntheticContainer')
        self.container.parent = None
        self.container.GetHierarchyParent = lambda: self.container.parent
        self.mission.ContainerClass = 'SyntheticContainer'
        self.e['HCEventQualification'] = N(Admitted=lambda: True)

    def test_delivery_requires_observed_custody_then_exact_container(self):
        self.mission.Family = 2
        self.assertTrue(self.o.RegisterTarget(self.mission.Id, self.item))
        self.assertTrue(self.o.RegisterContainer(self.mission.Id, self.container))
        self.assertTrue(self.o.Prepare(self.run.Lease, self.mission))
        self.player.position = [30., 0., 40.]; self.item.owner = self.player
        self.assertIsNone(self.o.Observe(self.run, self.player, 100), 'walking to the point is not delivery')
        self.item.owner = None; self.item.parent = Handle(identity='')
        self.assertIsNone(self.o.Observe(self.run, self.player, 101))
        self.item.parent = self.container
        self.o.RecordDelivery(self.run.Lease, self.item, self.player, self.container)
        self.assertTrue(self.o.Observe(self.run, self.player, 102).Observed)
        self.container.owner = self.player
        self.assertIsNone(self.o.Observe(self.run, self.player, 103), 'container must stay at the site')

    def test_direct_delivery_receipt_revoked_by_later_inventory_transition(self):
        self.mission.Family = 2
        self.o.RegisterTarget(self.mission.Id, self.item)
        self.o.RegisterContainer(self.mission.Id, self.container)
        self.assertTrue(self.o.Prepare(self.run.Lease, self.mission))
        self.player.position = [30., 0., 40.]
        self.item.owner = self.player; self.o.Observe(self.run, self.player, 100)
        self.item.owner = None; self.item.parent = self.container
        self.assertIsNone(self.o.Observe(self.run, self.player, 101), 'polling alone cannot attribute the actual delivery')
        self.o.RecordDelivery(self.run.Lease, self.item, self.player, self.container)
        self.assertTrue(self.o.Observe(self.run, self.player, 102).Observed)
        self.o.RecordDelivery(self.run.Lease, self.item, None, None)
        self.assertIsNone(self.o.Observe(self.run, self.player, 103))

    def test_delivery_cannot_claim_someone_elses_item_or_skip_custody(self):
        self.mission.Family = 2
        self.o.RegisterTarget(self.mission.Id, self.item)
        self.o.RegisterContainer(self.mission.Id, self.container)
        self.assertTrue(self.o.Prepare(self.run.Lease, self.mission))
        self.player.position = [30., 0., 40.]; self.item.parent = self.container
        self.assertIsNone(self.o.Observe(self.run, self.player, 100))
        self.item.parent = None; self.item.owner = Handle(identity='outsider')
        self.assertIsNone(self.o.Observe(self.run, self.player, 101))
        self.item.owner = None; self.item.parent = self.container
        self.assertIsNone(self.o.Observe(self.run, self.player, 102))

    def test_presence_needs_live_bound_entity_and_area_reach(self):
        self.mission.Family = 6; self.mission.AnchorClass = 'SyntheticSite'
        landmark = Handle(identity='', kind='SyntheticSite')
        self.assertTrue(self.o.RegisterPresence(self.mission.Id, landmark))
        self.assertTrue(self.o.Prepare(self.run.Lease, self.mission))
        self.assertTrue(self.o.Observe(self.run, self.player, 100).Observed)
        landmark.deleted = True
        self.assertIsNone(self.o.Observe(self.run, self.player, 101))
        landmark.deleted = False; self.player.position = [999., 0., 999.]
        self.assertIsNone(self.o.Observe(self.run, self.player, 102))

    def test_infected_requires_bound_live_actor_and_participant_kill_receipt(self):
        self.mission.Family = 7
        infected = Handle(identity='', kind='SyntheticInfected')
        self.assertTrue(self.o.RegisterInfected(self.mission.Id, infected))
        self.assertTrue(self.o.Prepare(self.run.Lease, self.mission))
        self.assertIsNone(self.o.Observe(self.run, self.player, 100))
        infected.alive = False
        self.assertIsNone(self.o.Observe(self.run, self.player, 101), 'a corpse is not a kill receipt')
        self.o.RecordKill(self.run.Lease, infected, 'outsider')
        self.assertIsNone(self.o.Observe(self.run, self.player, 102))
        self.o.RecordKill(self.run.Lease, infected, 'alice')
        self.assertIsNone(self.o.Observe(self.run, self.player, 103), 'first attributed death is immutable')

    def test_enrolled_killer_gets_one_lease_bound_observation(self):
        self.mission.Family = 7
        infected = Handle(identity='', kind='SyntheticInfected')
        self.o.RegisterInfected(self.mission.Id, infected)
        self.assertTrue(self.o.Prepare(self.run.Lease, self.mission))
        infected.alive = False; self.o.RecordKill(self.run.Lease, infected, 'alice')
        evidence = self.o.Observe(self.run, self.player, 100)
        self.assertEqual('alice', evidence.ParticipantId)
        self.assertEqual(self.run.Lease, evidence.Lease)
        self.o.Release(self.run.Lease)
        self.assertIsNone(self.o.Observe(self.run, self.player, 101))
        self.assertFalse(infected.deleted)


    def test_rebinding_unleased_target_does_not_replace_active_lease(self):
        self.o.RegisterTarget(self.mission.Id, self.item)
        self.assertTrue(self.o.ResetUnleasedTarget(self.mission.Id))
        self.assertIsNone(self.o.Target(self.mission.Id))
        self.f.bind()
        self.assertFalse(self.o.ResetUnleasedTarget(self.mission.Id))
        self.assertIs(self.item, self.o.Target(self.mission.Id).Item)

    def test_legacy_delivery_without_container_remains_loadable_but_not_ready(self):
        self.mission.Family = 2; self.mission.ContainerClass = ''
        self.assertTrue(self.e['HCEventRuntimePolicy'].MissionValid(self.mission, 'synthetic_world'))
        self.o.RegisterTarget(self.mission.Id, self.item)
        self.assertFalse(self.o.Ready(self.mission))


class V1SiteAndBinding(unittest.TestCase):
    def setUp(self):
        self.e = environment()
        self.e['HCEventQualification'] = N(Admitted=lambda: True)
        self.catalog = load_class('HCEventSites.c', 'HCEventSites', self.e)

    def test_bounded_source_reviewed_sites_are_not_claimed_surveyed(self):
        sites = self.catalog.ChernarusPlus()
        self.assertEqual(2, len(sites))
        self.assertEqual(2, len({s.Id for s in sites}))
        for site in sites:
            self.assertEqual('chernarusplus', site.WorldName)
            self.assertTrue(site.Reviewed)
            self.assertFalse(site.Surveyed)
            self.assertEqual('stock-mapgrouppos-source-review', site.Provenance)
            self.assertEqual(64, len(site.SourceSha256))
            roster = self.e['HCEventRoster'].Build(site, False)
            self.assertEqual({1, 2, 3, 4, 6, 7}, {m.Family for m in roster})
            self.assertTrue(all(m.RewardUnits == 0 for m in roster))
            self.assertTrue(all(m.AnchorClass == site.AnchorClass for m in roster))
            self.assertTrue(all(self.e['HCEventRuntimePolicy'].MissionValid(m, site.WorldName) for m in roster))

    def test_native_queries_bind_real_handles_and_delivery_uses_that_container(self):
        fixture = event_fixtures.NativeObservationTests(); fixture.setUp()
        env = fixture.e; mission = fixture.mission; mission.Family = 2
        container = Handle(identity='', position=mission.Destination, kind='SyntheticContainer')
        fixture.item.HCEventEconomyCandidate = lambda: True
        container.HCEventEconomyCandidate = lambda: True
        calls = []
        def query(anchor, radius, objects, proxies):
            calls.append((anchor, radius))
            objects.extend([fixture.item] if anchor == mission.Source else [container])
        env['GetGame'] = lambda: N(IsServer=lambda: True, GetObjectsAtPosition3D=query)
        env['ItemBase'] = N(Cast=lambda value: value)
        env['ZombieBase'] = N(Cast=lambda value: None)
        binder = load_class('HCEventWorldBinding.c', 'HCEventWorldBinding', env)
        self.assertTrue(binder.Bind(fixture.o, mission))
        self.assertEqual([(mission.Source, 15), (mission.Destination, 15)], calls)
        self.assertTrue(fixture.o.Prepare(fixture.run.Lease, mission))
        fixture.player.position = mission.Destination
        fixture.item.parent = container
        fixture.o.RecordDelivery(fixture.run.Lease, fixture.item, fixture.player, container)
        self.assertTrue(fixture.o.Observe(fixture.run, fixture.player, 100).Observed)
        calls.clear()
        self.assertTrue(binder.Bind(fixture.o, mission))
        self.assertEqual([], calls, 'active leases never rebind')

    def test_native_query_rejects_nonfinite_or_oversized_inputs_before_engine_call(self):
        calls = []
        self.e['GetGame'] = lambda: N(IsServer=lambda: True,
            GetObjectsAtPosition3D=lambda *args: calls.append(args))
        binder = load_class('HCEventWorldBinding.c', 'HCEventWorldBinding', self.e)
        for anchor, radius in (([0.,0.,0.], float('nan')),
                               ([float('inf'),0.,0.], 15), ([0.,0.,0.], 31)):
            self.assertIsNone(binder.Query(anchor, radius))
        self.assertEqual([], calls)

    def test_settings_rejects_oversized_binding_and_provenance_fields(self):
        cfg = self.e['HCEventSettings'](); cfg.Sites = self.catalog.ChernarusPlus()
        policy = self.e['HCEventRuntimePolicy']
        self.assertTrue(policy.SettingsValid(cfg))
        for field, length in (('ContainerClass', 97), ('AnchorClass', 97),
                              ('DeliveryClass', 97), ('SalvageClass', 97),
                              ('Provenance', 161), ('SourceSha256', 65)):
            broken = copy.deepcopy(cfg); setattr(broken.Sites[0], field, 'x' * length)
            self.assertFalse(policy.SettingsValid(broken), field)

    def test_unqualified_unsurveyed_sites_are_not_admitted(self):
        self.e['HCEventQualification'].Admitted = lambda: False
        self.assertEqual([], self.e['HCEventRoster'].Build(self.catalog.ChernarusPlus()[0], True))

    def test_native_selection_refuses_ambiguity_overflow_player_custody_and_unknown_economy(self):
        cls = load_class('HCEventWorldBinding.c', 'HCEventWorldBinding', self.e)
        def candidate(kind='SyntheticSupply', ce=True):
            item = Handle(identity='', kind=kind)
            item.GetHierarchyParent = lambda: None
            item.HCEventEconomyCandidate = lambda: ce
            return item
        self.e['ItemBase'] = N(Cast=lambda obj: obj)
        self.e['ZombieBase'] = N(Cast=lambda obj: None)
        good = candidate()
        self.e['HCEventTarget'] = lambda: N(Presence=None, Item=None)
        self.assertIs(good, cls.Select(EArray([good]), 'SyntheticSupply', True).Item)
        self.assertIsNone(cls.Select(EArray([good, candidate()]), 'SyntheticSupply', True))
        self.assertIsNone(cls.Select(EArray([good] * 129), 'SyntheticSupply', True))
        self.assertIsNone(cls.Select(EArray([candidate(ce=False)]), 'SyntheticSupply', True))
        good.owner = Handle()
        self.assertIsNone(cls.Select(EArray([good]), 'SyntheticSupply', True))


class V1DurableMission(unittest.TestCase):
    def test_old_delivery_image_loads_missing_additive_fields_and_cancels_safely(self):
        helper = event_fixtures.EventRuntimeTests(); helper.setUp(); runtime = helper.active(family=2)
        fixture = event_fixtures.EventJournalTests(); fixture.setUp()
        state = copy.deepcopy(runtime.m_State); state.Revision = 1
        payload = json.loads(fixture.codec.Encode(state))
        for run in payload['Runs']:
            run['Objective'].pop('ContainerClass'); run['Objective'].pop('AnchorClass')
        image = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        receipt = N(Version=1, Revision=1, WorldName='synthetic_world',
                    Length=len(image), Hash=fixture.codec.Digest(image))
        intent = fixture.codec.EncodeReceipt(receipt)
        fixture.io.files = {'intent-1.json': intent, 'image-1.json': image, 'commit-1.json': intent}
        journal = fixture.open(); restored = journal.Load('synthetic_world')
        self.assertIsNotNone(restored)
        self.assertEqual('', restored.Runs[0].Objective.ContainerClass)
        self.assertEqual(image, fixture.io.files['image-1.json'])
        helper.ctx.Session = 'restarted'
        self.assertTrue(runtime.Start(helper.cfg, helper.ctx, fixture.open(), helper.observer, helper.ai))
        self.assertEqual(6, runtime.m_State.Director.Records[0].Status)
        self.assertEqual([], runtime.m_Subscriptions)

    def test_completed_objective_roundtrips_real_authored_journal_and_restart(self):
        helper = event_fixtures.EventRuntimeTests(); helper.setUp(); runtime = helper.active()
        journal_fixture = event_fixtures.EventJournalTests(); journal_fixture.setUp()
        journal = journal_fixture.j
        journal.Load('synthetic_world')
        # Explicit synthetic storage, but authored journal and runtime execute.
        runtime.m_Store = journal
        runtime.m_State.Revision = 0
        self.assertTrue(runtime.Publish(copy.deepcopy(runtime.m_State)))
        helper.observer.evidence = helper.evidence(runtime)
        runtime.Tick(helper.ctx)
        self.assertEqual(4, runtime.m_State.Director.Records[0].Status)
        runtime.Tick(helper.ctx)
        saved = copy.deepcopy(runtime.m_State)
        restored = journal_fixture.open().Load('synthetic_world')
        self.assertEqual(saved, restored)
        helper.ctx.Session = 'restart'
        self.assertTrue(runtime.Start(helper.cfg, helper.ctx, journal_fixture.open(), helper.observer, helper.ai))
        self.assertEqual(4, runtime.m_State.Director.Records[0].Status)
        self.assertEqual(1, runtime.m_State.Director.Records[0].Progress)
        self.assertEqual([], runtime.m_Subscriptions)
        self.assertEqual(0, runtime.m_State.Runs[0].Objective.RewardUnits)


class V1LifecycleAndPresentation(unittest.TestCase):
    def test_delivery_dto_member_does_not_shadow_native_inventory_container_type(self):
        # Installed 5_Mission/GUI/InventoryNew/Containers/Container.c:1.
        source = (ROOT / '4_World/Events/HCEventNativeObserver.c').read_text()
        self.assertEqual([], re.findall(r'\bItemBase\s+Container\s*;', source))

    def test_qualification_default_closed_and_marker_cached_once_per_process(self):
        env = dict(EArray=EArray, str=str); probes = []; logs = []
        env['FileExist'] = lambda path: probes.append(path) or True
        env['Print'] = logs.append
        source = (ROOT / '4_World/Events/HCEventQualification.c').read_text()
        source = re.sub(r'\bs_(Checked|OptIn)\b', r'HCEventQualification.s_\1', source)
        cls = type('AuthoredQualification', (), dict(s_Checked=False, s_OptIn=False))
        env['HCEventQualification'] = cls
        for name in ('Qualified', 'LocalAcceptanceOptIn', 'Admitted'):
            setattr(cls, name, staticmethod(translate(source, name, env, 'HCEventQualification')))
        self.assertFalse(cls.Qualified()); self.assertTrue(cls.Admitted()); self.assertTrue(cls.Admitted())
        self.assertEqual(['$profile:HollowCountry/acceptance/events.enable'], probes)
        self.assertEqual(1, len(logs)); self.assertIn('EXPERIMENTAL', logs[0])
        cls.s_Checked = False; env['FileExist'] = lambda path: False
        self.assertFalse(cls.Admitted())

    def test_optional_ai_selection_constructs_only_the_fixed_script_provider(self):
        env = dict(EArray=EArray, str=str, Print=lambda line: None)
        class Provider:
            @staticmethod
            def Cast(value): return value if isinstance(value, Provider) else None
        env['HCEventAIProvider'] = Provider
        requested = []; provider = Provider()
        env['NativeType'] = lambda name: requested.append(name) or None
        source = (ROOT / '4_World/Events/HCEventAISelection.c').read_text()
        source = source.replace('providerName.ToType()', 'NativeType(providerName)') # native typename seam
        create = translate(source, 'Create', env)
        self.assertIsInstance(create(), Provider)
        self.assertEqual(['HCExpansionAIEventProvider'], requested)
        env['NativeType'] = lambda name: N(Spawn=lambda: provider)
        self.assertIs(provider, create())
        env['NativeType'] = lambda name: N(Spawn=lambda: N(wrong=True))
        self.assertIsInstance(create(), Provider)

    def test_module_qualification_rejection_never_starts_runtime_or_rpc(self):
        fixture = integration_fixtures.EventIntegrationTests(); fixture.setUp()
        fixture.env['HCEventQualification'].Admitted = lambda: False
        fixture.start()
        self.assertEqual([], fixture.calls)
        self.assertIsNone(fixture.module.Runtime())

    def test_late_roster_discovery_never_reannounces_current_terminal_missions(self):
        env = environment(); calls = []
        env['HCEventWorldBinding'] = N(Bind=lambda observer, mission: calls.append(('bind', mission.Id)))
        module_cls = integration_fixtures.authored_module(env)
        site = env['HCEventSite'](); site.Id = 'synthetic'; site.WorldName = 'synthetic_world'
        site.Reviewed = True; site.ItemClass = 'SyntheticSupply'
        site.ContainerClass = 'SyntheticContainer'; site.AnchorClass = 'SyntheticSite'
        cfg = env['HCEventSettings'](); cfg.Sites.Insert(site)
        module = module_cls(); module.m_Config = cfg; module.m_NativeObserver = N()
        module.m_RosterCursor = 0
        module.m_Runtime = N(HasMission=lambda mission: mission.endswith('-1'),
            Announce=lambda mission, context: calls.append(('announce', mission.Id)))
        context = env['HCEventContext'](); context.WorldName = 'synthetic_world'
        module.RefreshRoster(context)
        self.assertEqual([], calls)
        module.RefreshRoster(context)
        self.assertEqual([('bind', 'synthetic-2'), ('announce', 'synthetic-2')], calls)

    def test_kill_callback_only_attributes_current_joined_mission(self):
        helper = event_fixtures.EventRuntimeTests(); helper.setUp()
        runtime = helper.active(family=7)
        receipts = []
        helper.observer.RecordKill = lambda lease, actor, identity: receipts.append((lease, actor, identity))
        infected = Handle(identity=''); infected.alive = False
        outsider = Handle(identity='outsider')
        runtime.InfectedKilled(infected, outsider, helper.ctx)
        self.assertEqual([], receipts)
        runtime.InfectedKilled(infected, helper.player, helper.ctx)
        self.assertEqual([(runtime.m_State.Runs[0].Lease, infected, 'alice')], receipts)
        receipts.clear(); runtime.Leave(1, helper.player, helper.ctx)
        runtime.InfectedKilled(infected, helper.player, helper.ctx)
        self.assertEqual([], receipts)

    def test_menu_displays_server_briefing_and_rejects_unbounded_details(self):
        fixture = ui_fixtures.EventMenuTests(); fixture.setUp()
        fixture.client.m_View.Rows[0].Briefing = 'Put the existing supply inside the green barrel.'
        fixture.menu.Render(fixture.client.GetView()); fixture.menu.m_List.selected = 0
        fixture.menu.Controls()
        self.assertIn('inside the green barrel', fixture.menu.m_Detail.text)
        frame = fixture.client.GetView(); frame.Rows[0].Briefing = 'x' * 769
        self.assertFalse(fixture.client.ViewValid(frame))

    def test_projection_carries_site_and_objective_instructions_without_identity(self):
        fixture = transport_fixtures.EventTransportTests(); fixture.setUp()
        row = fixture.handshake().Rows[0]
        self.assertIn('synthetic-site', row.Briefing)
        self.assertIn('SyntheticSupply', row.Briefing)
        self.assertNotIn('alice', row.Briefing)


if __name__ == '__main__': unittest.main()
