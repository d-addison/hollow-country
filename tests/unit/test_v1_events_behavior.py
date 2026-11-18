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
    cls = type(owner, (), {'s_' + n: None for n in re.findall(r'\bs_(\w+)\b', source)})
    env[owner] = cls
    source = re.sub(r'\bs_(\w+)\b', owner + r'.s_\1', source)
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

    def test_qualification_default_open_and_disable_marker_cached_once_per_process(self):
        env = dict(EArray=EArray, str=str); probes = []; logs = []
        env['FileExist'] = lambda path: probes.append(path) or False       # no .disable file: the default
        env['Print'] = logs.append
        source = (ROOT / '4_World/Events/HCEventQualification.c').read_text()
        source = re.sub(r'\bs_(Checked|OptIn)\b', r'HCEventQualification.s_\1', source)
        cls = type('AuthoredQualification', (), dict(s_Checked=False, s_OptIn=False))
        env['HCEventQualification'] = cls
        for name in ('Qualified', 'LocalAcceptanceOptIn', 'Admitted'):
            setattr(cls, name, staticmethod(translate(source, name, env, 'HCEventQualification')))
        self.assertFalse(cls.Qualified()); self.assertTrue(cls.Admitted()); self.assertTrue(cls.Admitted())
        self.assertEqual(['$profile:HollowCountry/acceptance/events.disable'], probes)
        self.assertEqual(1, len(logs)); self.assertIn('EXPERIMENTAL', logs[0])
        cls.s_Checked = False; env['FileExist'] = lambda path: True        # the opt-out file now exists
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
        module.m_RosterCursor = 0; module.m_AnnouncedMissions = EArray()
        module.m_Runtime = N(HasMission=lambda mission: mission.endswith('-1'),
            Announce=lambda mission, context: calls.append(('announce', mission.Id)) or 0)
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


def load_hooks(owner, env):
    """Executes the authored modded-class bodies; `super.` calls are engine-only no-ops."""
    source = (ROOT / '4_World/Events/HCEventEconomyObservation.c').read_text()
    start = source.index('modded class ' + owner)
    source = source[start:]
    following = source.find('\nmodded class ', 1)
    if following >= 0: source = source[:following]
    source = re.sub(r'super\.\w+\([^)]*\);', '', source)
    cls = type(owner, (), {'m_HCEventEconomyCandidate': False})
    for name in re.findall(r'^    (?:override )?(?:bool|void) (\w+)\(', source, re.M):
        setattr(cls, name, translate(source, name, env, owner, True))
    return cls


class V1EconomyHooks(unittest.TestCase):
    def setUp(self):
        self.server = True; self.admitted = True; self.seen = []; self.module = True
        test = self
        class Player: pass
        class Parent:
            def __init__(self, root): self.root = root
            def GetHierarchyRootPlayer(self): return self.root
        self.Player = Player; self.Parent = Parent
        module = N(ItemLocationChanged=lambda *a: test.seen.append(('item',) + a),
                   InfectedKilled=lambda *a: test.seen.append(('kill',) + a))
        self.env = dict(
            GetGame=lambda: N(IsServer=lambda: test.server),
            HCEventQualification=N(Admitted=lambda: test.admitted),
            HCEventModule=N(Get=lambda: module if test.module else None),
            PlayerBase=N(Cast=lambda v: v if isinstance(v, Player) else None),
            EntityAI=N(Cast=lambda v: v if hasattr(v, 'GetHierarchyRootPlayer') else None))

    def location(self, parent): return N(GetParent=lambda: parent)

    def test_gated_or_nonserver_callbacks_never_reach_the_module(self):
        item = load_hooks('ItemBase', self.env)(); zombie = load_hooks('ZombieBase', self.env)()
        player = self.Player(); old = self.location(self.Parent(player)); new = self.location(None)
        for label, setup in (('client', lambda: setattr(self, 'server', False)),
                             ('unadmitted', lambda: setattr(self, 'admitted', False)),
                             ('no module', lambda: setattr(self, 'module', False))):
            self.server = True; self.admitted = True; self.module = True
            setup()
            item.EEItemLocationChanged(old, new); zombie.EEKilled(player)
            self.assertEqual([], self.seen, label)
        self.server = True; self.admitted = True; self.module = True
        item.EEItemLocationChanged(old, new); zombie.EEKilled(player)
        self.assertEqual(['item', 'kill'], [call[0] for call in self.seen])

    def test_ce_create_marks_candidate_only_on_server(self):
        item = load_hooks('ItemBase', self.env)(); self.server = False
        item.EEOnCECreate(); self.assertFalse(item.HCEventEconomyCandidate())
        self.server = True; item.EEOnCECreate(); self.assertTrue(item.HCEventEconomyCandidate())
        zombie = load_hooks('ZombieBase', self.env)(); self.assertFalse(zombie.HCEventEconomyCandidate())
        zombie.EEOnCECreate(); self.assertTrue(zombie.HCEventEconomyCandidate())

    def test_previous_carrier_is_the_old_root_player_and_destination_is_forwarded(self):
        item = load_hooks('ItemBase', self.env)()
        player = self.Player(); destination = object()
        item.EEItemLocationChanged(self.location(self.Parent(player)), self.location(destination))
        self.assertEqual([('item', item, player, destination)], self.seen)
        self.seen.clear()
        item.EEItemLocationChanged(self.location(self.Parent(None)), self.location(destination))
        self.assertEqual([('item', item, None, destination)], self.seen)

    def test_killed_forwards_direct_or_root_player_killer_only(self):
        zombie = load_hooks('ZombieBase', self.env)(); player = self.Player()
        zombie.EEKilled(player)
        zombie.EEKilled(self.Parent(player))
        zombie.EEKilled(self.Parent(None)); zombie.EEKilled(None)
        self.assertEqual([('kill', zombie, player)] * 2, self.seen)


class V1EventsReviewFixes(unittest.TestCase):
    def site(self, env, name='synthetic', world='chernarusplus'):
        site = env['HCEventSite'](); site.Id = name; site.WorldName = world; site.Reviewed = True
        site.Position = [10., 0., 20.]; site.Destination = [30., 0., 40.]; site.ItemClass = 'SyntheticSupply'
        site.ContainerClass = 'SyntheticContainer'; site.AnchorClass = 'SyntheticSite'
        return site

    def test_engine_world_case_never_blocks_lowercase_sites(self):
        for site_world, engine in (('chernarusplus', 'ChernarusPlus'), ('ChernarusPlus', 'chernarusplus')):
            with self.subTest(site=site_world, engine=engine):
                fixture = integration_fixtures.EventIntegrationTests(); fixture.setUp()
                fixture.game.GetWorldName = lambda engine=engine: engine
                fixture.cfg.Sites = EArray([N(WorldName=site_world)])
                self.assertEqual('chernarusplus', fixture.module.Context().WorldName)
                fixture.start()
                self.assertIn('roster.build', fixture.calls)

    def test_roster_copies_lowercase_world_and_refresh_and_binding_compare_lowercase(self):
        env = environment(); calls = []
        mixed = self.site(env, world='ChernarusPlus')
        self.assertEqual({'chernarusplus'}, {m.WorldName for m in env['HCEventRoster'].Build(mixed, True)})
        env['HCEventWorldBinding'] = N(Bind=lambda observer, mission: calls.append(('bind', mission.Id)))
        module = integration_fixtures.authored_module(env)()
        cfg = env['HCEventSettings'](); cfg.Sites.Insert(mixed)
        module.m_Config = cfg; module.m_NativeObserver = N(); module.m_RosterCursor = 0
        module.m_AnnouncedMissions = EArray()
        module.m_Runtime = N(HasMission=lambda mission: False,
            Announce=lambda mission, context: calls.append(('announce', mission.WorldName)) or 0)
        context = env['HCEventContext'](); context.WorldName = 'chernarusplus'
        module.RefreshRoster(context)
        self.assertEqual([('bind', 'synthetic-1'), ('announce', 'chernarusplus')], calls)
        bound = []
        binder = load_class('HCEventWorldBinding.c', 'HCEventWorldBinding', env)
        binder.Bind = staticmethod(lambda observer, mission: bound.append(mission.Id))
        binder.BindSites(N(), cfg, 'chernarusplus')
        self.assertEqual(6, len(bound))

    def test_pruned_terminal_missions_never_reannounce_with_five_or_more_sites(self):
        env = environment(); announced = []
        env['HCEventWorldBinding'] = N(Bind=lambda observer, mission: True)
        module = integration_fixtures.authored_module(env)()
        cfg = env['HCEventSettings']()
        for index in range(6): cfg.Sites.Insert(self.site(env, name='site' + str(index)))
        module.m_Config = cfg; module.m_NativeObserver = N(); module.m_RosterCursor = 0
        module.m_AnnouncedMissions = EArray()
        module.m_Runtime = N(HasMission=lambda mission: False,  # pruned records are invisible
            Announce=lambda mission, context: announced.append(mission.Id) or 0)
        context = env['HCEventContext'](); context.WorldName = 'chernarusplus'
        for _ in range(6 * 7 * 3): module.RefreshRoster(context)
        self.assertEqual(len(announced), len(set(announced)))
        self.assertEqual(6 * 6, len(announced), "no AI provider: the AI encounter family is never offered")

    def test_failed_announcement_stays_retryable_and_start_clears_session_memory(self):
        fixture = integration_fixtures.EventIntegrationTests(); fixture.setUp()
        fixture.start()
        self.assertEqual(['synthetic-mission'], list(fixture.module.m_AnnouncedMissions))
        fixture.module.OnStop(); fixture.start()
        self.assertEqual(['synthetic-mission'], list(fixture.module.m_AnnouncedMissions))

    def test_item_moves_without_a_previous_carrier_skip_context_but_still_revoke(self):
        fixture = integration_fixtures.EventIntegrationTests(); fixture.setUp(); fixture.start()
        module = fixture.module; revoked = []; delivered = []; clock = []
        module.m_NativeObserver = N(RevokeDelivery=lambda item: revoked.append(item))
        module.m_Runtime = N(ItemDelivered=lambda *a: delivered.append(a))
        module.Context = lambda: clock.append(1) or N(Server=True)
        module.ItemLocationChanged('item', None, 'box')
        self.assertEqual((['item'], [], []), (revoked, delivered, clock))
        module.ItemLocationChanged('item', 'alice', 'box')
        self.assertEqual((['item', 'item'], 1, 1), (revoked, len(delivered), len(clock)))

    def test_blocked_mission_is_logged_once_per_mission_per_session(self):
        helper = event_fixtures.EventRuntimeTests(); helper.setUp(); lines = []
        helper.e['Print'] = lines.append
        runtime = helper.runtime(); helper.observer.ready = False
        for _ in range(3): self.assertEqual(helper.code.BLOCKED, runtime.Announce(helper.mission, helper.ctx))
        self.assertEqual(1, len([l for l in lines if 'mission blocked' in l]))
        helper.mission.Id = 'other'
        runtime.Announce(helper.mission, helper.ctx)
        self.assertEqual(2, len([l for l in lines if 'mission blocked' in l]))

    def test_participant_cap_is_the_target_load_everywhere(self):
        helper = event_fixtures.EventRuntimeTests(); helper.setUp()
        for count, valid in ((6, True), (7, False)):
            helper.mission.MaxParticipants = count
            self.assertEqual(valid, helper.p.MissionValid(helper.mission, helper.ctx.WorldName), count)
        client = ui_fixtures.EventClientTests(); client.setUp(); client.ready()
        for count, valid in ((6, True), (7, False)):
            frame = client.frame(seq=2); frame.Rows[0].MaxParticipants = count
            self.assertEqual(valid, client.client.ViewValid(frame), count)
        source = (ROOT / '4_World/Events/HCEventDirector.c').read_text()
        self.assertNotRegex(source, r'MaxParticipants > 90|Count\(\) > 90')

    def test_far_participant_cannot_observe_a_delivery(self):
        v1 = V1NativeObjectives('test_delivery_requires_observed_custody_then_exact_container'); v1.setUp()
        mission = v1.mission; mission.Family = 2
        v1.o.RegisterTarget(mission.Id, v1.item); v1.o.RegisterContainer(mission.Id, v1.container)
        self.assertTrue(v1.o.Prepare(v1.run.Lease, mission))
        v1.player.position = [30., 0., 40.]; v1.item.owner = v1.player; v1.o.Observe(v1.run, v1.player, 100)
        v1.item.owner = None; v1.item.parent = v1.container
        v1.o.RecordDelivery(v1.run.Lease, v1.item, v1.player, v1.container)
        v1.player.position = [900., 0., 900.]
        self.assertIsNone(v1.o.Observe(v1.run, v1.player, 101), 'delivering then walking far away is not completion')
        v1.player.position = [30., 0., 40.]
        self.assertTrue(v1.o.Observe(v1.run, v1.player, 102).Observed)


if __name__ == '__main__': unittest.main()
