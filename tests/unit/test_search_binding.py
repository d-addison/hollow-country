"""W1.2 (#15/#42): execute the authored binder against explicit synthetic data.

Spec: placed + reviewed sites only; finite CE handles; admitted server, one session.
Plan/tasks: validate reviewed geometry/context -> delayed bounded Prepare -> bind or
Abandon -> remove callbacks at stop. Python adapters are not engine acceptance.
The missing governance specs in this writer checkout are not runtime evidence.

Actual TDD record (PYTHONDONTWRITEBYTECODE=1 python3 -m unittest):
  RED: tests.unit.test_search_binding -v -> Ran 13 tests; FAILED (failures=13),
       AssertionError: missing authored search binder: HCSearchBinding.c
  GREEN: tests.unit.test_search_binding -v -> Ran 13 tests; OK.
  Yaw RED: test_equivalent_wrapped_storage_yaw_keeps_the_placed_binding -v
       -> Ran 1 test; FAILED (failures=1), AssertionError: unexpectedly None.
  Final GREEN: tests.unit.test_search_binding tests.unit.test_script_syntax
       tests.unit.test_acceptance_markers tests.unit.test_hygiene -v
       -> Ran 96 tests; OK (14 binder tests).
"""
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit import test_interior_measured_catalog as measured
from tests.unit.test_interiors_contract import authored as interior_rule
from tests.unit.test_group_server import EArray, body, execute_member
from tests.unit.test_search_supply_provider import Runtime, World, FS, Item, PIN

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/Loot/HCSearchBinding.c'
INTERIORS = ROOT / 'mods/HollowCountry/scripts/4_World/Interiors/HCInteriorModule.c'


def class_body(source, name):
    match = re.search(r'\bclass ' + name + r'(?:\s*:\s*\w+)?\s*\{', source)
    if not match:
        raise AssertionError('missing authored binder class: ' + name)
    return body(source, match.end())


class Queue:
    """Explicit synthetic one-shot queue; no real waiting or DayZ scheduling."""
    def __init__(self):
        self.now, self.pending, self.scheduled = 0, [], []

    def CallLater(self, fn, delay, repeat):
        if repeat:
            raise AssertionError('binder must use bounded one-shot calls')
        self.pending.append((self.now + delay, fn))
        self.scheduled.append(delay)

    def Remove(self, fn):
        self.pending[:] = [(at, call) for at, call in self.pending if call != fn]

    def fire(self):
        self.pending.sort(key=lambda pair: pair[0])
        self.now, fn = self.pending.pop(0)
        fn()

    def drain(self):
        for _ in range(10):
            if not self.pending:
                return
            self.fire()
        raise AssertionError('retry queue was not bounded')


class ScriptObject:
    def __init__(self, vm, name):
        self._vm, self._class = vm, name
        fields = class_body(vm.source, name)
        for match in re.finditer(r'^    (?:protected )?(?:ref )?(\w[\w<>, ]*?) (m_\w+)(?: = ([^;]+))?;', fields, re.M):
            typ, key, initial = match.groups()
            if 'array<' in typ:
                value = EArray() if initial else None
            elif initial:
                value = json.loads(initial)
            else:
                value = {'bool': False, 'int': 0, 'string': ''}.get(typ)
            setattr(self, key, value)

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        method = lambda *args: self._vm.call(self._class, name, self, *args)
        setattr(self, name, method)
        return method


class VM:
    """Adapt Enforce syntax only; policy and retry decisions come from source."""
    def __init__(self):
        if not SOURCE.is_file():
            raise AssertionError('missing authored search binder: HCSearchBinding.c')
        self.source = SOURCE.read_text()
        self.queue, self.world, self.fs = Queue(), World(), FS()
        self.rt = Runtime(self.world, self.fs, world_name='chernarusplus')
        self.state = N(s_Instance=None, s_Binding=None)
        self.server, self.admitted, self.live = True, True, True
        self.settings = N(EnableInteriors=True, EnableSearch=True)
        self.prepared, self.abandoned, self.bound = [], [], []
        self.real_provider = self.rt.provider()
        self.prepare_result = self.real_provider.Prepare
        self.bind_result = True
        self.during_prepare = None
        self.economy = self.rt.economy()
        game = N(IsServer=lambda: self.server, GetCallQueue=lambda category: self.queue)
        pure = measured.authored()
        pure["Vector"] = lambda x, y, z: [x, y, z]
        self.env = dict(self.rt.env)
        self.env.update(
            GetGame=lambda: game, CALL_CATEGORY_SYSTEM=0, _state=self.state,
            HCInteriorRules=N(SearchAdmitted=lambda: self.admitted, Yaw=lambda value: interior_rule("Yaw", value)),
            HCSearchBinding=N(PlacementComplete=lambda *args: self.call('HCSearchBinding', 'PlacementComplete', N(), *args)),
            HCInteriorsModule=N(Get=lambda: self.interior),
            HCSearchSupplyProvider=lambda: N(Prepare=self.prepare, Abandon=self.abandon),
            HCSearchSiteVolume=lambda: N(Classes=EArray()),
            HCInteriorSearchContext=lambda: N(Items=EArray(), GroupId=''),
            HCSearchBindingReview=lambda: N(Volume=None, Context=None),
            MeasuredLive=lambda candidate: self.live,
        )
        for name in ('MeasuredRule', 'MeasuredGroup', 'MeasuredAsVector', 'MeasuredBox'):
            self.env[name] = pure[name]
        self.env['HCInteriorMeasuredCatalog'] = N(SearchBindingReview=lambda *args:
            self.call('HCInteriorMeasuredCatalog', 'SearchBindingReview', N(), *args))
        self.owner = ScriptObject(self, 'HCSearchBinding')
        self.interior = N(BindSearchEconomy=self.bind)
        self.config = N(Epoch=1, Seed=7, InitializeNewEpoch=True, Candidates=EArray())
        self.manifest = N(Epoch=1, Assignments=EArray())
        self.sites = EArray()
        self.fixture()

    def fixture(self):
        """Synthetic rotated house; geometry/pins below are never shipped evidence."""
        house = N(ModelToWorld=lambda p: [100. - p[2], 5. + p[1], 200. + p[0]])
        target = N(GetType=lambda: 'SyntheticCabinet', GetPosition=lambda: house.ModelToWorld([1., 0., 2.]),
                   GetOrientation=lambda: [180., 0., 0.], ModelToWorld=lambda p: [98. - p[0], 5. + p[1], 201. - p[2]])
        candidate = N(SlotId=4, Id=lambda epoch: 'synthetic_instance', Type='SyntheticHouse')
        assignment = N(SlotId=4, InstanceId='synthetic_instance', LayoutId='synthetic_layout',
                       History='family', MeasuredRecordSha256=PIN)
        searchable = N(Type='SyntheticCabinet', Position=EArray([1., 0., 2.]),
                       Orientation=EArray([90., 0., 0.]), SearchPoint=EArray([0., 1., 0.]), Searchable=True)
        bounds = N(Min=EArray([0., 0., 1.]), Max=EArray([2., 2., 3.]))
        layout = N(Id=assignment.LayoutId, History='family', Props=EArray([searchable]),
                   Survey=N(Props=EArray([N(Index=0, Room='kitchen', Bounds=bounds)])))
        rule = N(LayoutId=layout.Id, Room='kitchen', History='family', Storage='added-searchable-prop',
                 ItemGroups=EArray(['synthetic_food', 'synthetic_second']))
        groups = EArray([N(Id='synthetic_food', Items=EArray(['SyntheticFood'])),
                         N(Id='synthetic_second', Items=EArray(['SyntheticFood', 'SyntheticTool']))])
        record = N(Layouts=EArray([layout]), Policy=N(Rules=EArray([rule]), ItemGroups=groups))
        self.state.s_Binding = N(Record=record, RecordSha256=PIN, HouseObject=house, Orientation=[90., 0., 0.])
        self.config.Candidates.Insert(candidate)
        self.manifest.Assignments.Insert(assignment)
        self.sites.Insert(N(SlotId=4, Id='synthetic_instance_storage_v1', Target=target, Point=target.ModelToWorld([0., 1., 0.])))
        self.candidate, self.assignment, self.layout, self.rule = candidate, assignment, layout, rule

    def call(self, cls, name, instance, *args):
        source = class_body(self.source, cls)
        match = re.search(r'\b[\w<>]+ ' + name + r'\(([^)]*)\)\s*\{', source)
        if not match:
            raise AssertionError('missing authored member: ' + cls + '.' + name)
        text = body(source, match.end())
        text = re.sub(r'\b(?:ref )?array<[^;]+?> (\w+) = new array<[^;]+?>', r'\1 = EArray()', text)
        text = re.sub(r'\b(HC\w+|Object|vector) (?=\w+\s*=)', '', text)
        text = re.sub(r'\b(HC\w+|Object|vector) (\w+);', r'\2 = null;', text)
        text = text.replace('"0 0 0"', 'zero_vector()')
        text = re.sub(r'\bs_(Instance|Binding)\b', r'_state.s_\1', text)
        text = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', text)
        text = text.replace('this', 'self')
        for const, value in re.findall(r'static const (?:int|string) (\w+) = ([^;]+);', source):
            self.env[const] = json.loads(value)
        for helper in re.findall(r'^    (?:override |static )?[\w<>]+ (\w+)\(', source, re.M):
            text = re.sub(r'(?<![\w.])' + helper + r'(?=\(|\b(?!\.))', 'self.' + helper, text)
        params = re.sub(r'array<ref (\w+)>', r'\1Array', match[1])
        return execute_member('bool ' + name + '(' + params + ') {' + text + '}', name,
                              dict(self.env, zero_vector=lambda: [0., 0., 0.]), instance, *args)

    def prepare(self, *args):
        self.prepared.append(args)
        plan = self.prepare_result(*args)
        if self.during_prepare:
            self.during_prepare()
        return plan

    def abandon(self, plan):
        self.abandoned.append(plan)
        self.real_provider.Abandon(plan)

    def bind(self, registry, manifest, contexts, initialize):
        self.bound.append((registry, manifest, EArray(contexts), initialize))
        if not self.bind_result:
            return False
        return self.economy.Open(manifest, registry, initialize)

    def hook(self):
        self.env['HCSearchBinding'].PlacementComplete(self.interior, self.config, self.manifest, self.sites)

    def start(self):
        self.owner.OnStart(self.settings)
        self.hook()

    def item(self):
        return Item(self.world, (1, 2, 3, 4), position=(98., 6., 201.))

    def review(self):
        return self.env['HCInteriorMeasuredCatalog'].SearchBindingReview(self.candidate, self.assignment, self.sites[0])


class BindingBehavior(unittest.TestCase):
    def setUp(self):
        self.vm = VM()

    def test_after_placement_observes_late_ce_supply_then_binds_same_handles_once(self):
        v = self.vm
        v.start()
        self.assertEqual([], v.prepared)
        self.assertEqual(1, len(v.queue.pending))
        v.queue.fire()  # CE still empty
        item = v.item()
        v.queue.drain()
        self.assertEqual(2, len(v.prepared))
        self.assertEqual(1, len(v.bound))
        registry, manifest, contexts, initialize = v.bound[0]
        self.assertIs(item, registry.m_Entries[0].ItemHandle)
        self.assertEqual('synthetic_instance_storage_v1', manifest.Entries[0].SiteId)
        self.assertEqual(['SyntheticFood', 'SyntheticTool'], list(contexts[0].Items))
        self.assertEqual(PIN, contexts[0].SourcePin)
        self.assertEqual(PIN, contexts[0].EvidencePin)
        self.assertEqual('kitchen', contexts[0].Room)
        self.assertTrue(initialize)
        self.assertEqual([], v.abandoned)
        self.assertEqual([], v.world.events)
        self.assertEqual([], v.rt.created)
        v.hook()
        v.owner.OnStart(v.settings)
        v.hook()
        self.assertEqual([], v.queue.pending)
        self.assertEqual(1, len(v.bound))

    def test_empty_ce_refuses_after_three_equal_delays_and_never_reactivates(self):
        v = self.vm
        v.start()
        v.queue.drain()
        self.assertEqual([10000] * 3, v.queue.scheduled)
        self.assertEqual(3, len(v.prepared))
        self.assertEqual([], v.bound)
        self.assertTrue(any('3 attempts' in line for line in v.rt.log), v.rt.log)
        v.item()
        v.hook()
        self.assertEqual([], v.queue.pending)
        self.assertEqual({}, v.fs.files)

    def test_client_marker_and_settings_gates_never_prepare_or_schedule(self):
        for attr, value in (('server', False), ('admitted', False), ('EnableInteriors', False), ('EnableSearch', False)):
            with self.subTest(gate=attr):
                v = VM()
                setattr(v.settings if attr.startswith('Enable') else v, attr, value)
                v.start()
                self.assertEqual([], v.queue.pending)
                self.assertEqual([], v.prepared)

    def test_stop_removes_callback_and_late_delivery_cannot_prepare(self):
        v = self.vm
        v.start()
        callback = v.queue.pending[0][1]
        v.owner.OnStop()
        v.owner.OnStop()
        self.assertEqual([], v.queue.pending)
        callback()
        v.hook()
        self.assertEqual([], v.prepared)

    def test_refused_economy_is_terminal_and_abandons_prepared_registry(self):
        v = self.vm
        v.item()
        v.bind_result = False
        v.start()
        v.queue.drain()
        self.assertEqual(1, len(v.bound))
        self.assertEqual(1, len(v.abandoned))
        self.assertEqual([], v.rt.s_Registered)
        self.assertEqual([], v.rt.s_Registries)
        self.assertTrue(any('bind refused' in line for line in v.rt.log), v.rt.log)

    def test_stop_during_prepare_abandons_plan_without_binding(self):
        v = self.vm
        v.item()
        v.during_prepare = v.owner.OnStop
        v.start()
        v.queue.drain()
        self.assertEqual([], v.bound)
        self.assertEqual(1, len(v.abandoned))
        self.assertEqual([], v.rt.s_Registered)

    def test_unplaced_duplicate_or_changed_assignment_refuses_before_observation(self):
        for kind in ('unplaced', 'duplicate', 'digest', 'instance', 'slot', 'layout', 'history', 'dead_target', 'not_live'):
            with self.subTest(kind=kind):
                v = VM()
                if kind == 'unplaced': v.sites.Clear()
                if kind == 'duplicate': v.sites.Insert(v.sites[0])
                if kind == 'digest': v.assignment.MeasuredRecordSha256 = 'b' * 64
                if kind == 'instance': v.assignment.InstanceId = 'foreign'
                if kind == 'slot': v.assignment.SlotId = 9
                if kind == 'layout': v.assignment.LayoutId = 'unknown'
                if kind == 'history': v.assignment.History = 'unknown'
                if kind == 'dead_target': v.sites[0].Target = None
                if kind == 'not_live': v.live = False
                v.start()
                v.queue.drain()
                self.assertEqual([], v.prepared)
                self.assertEqual([], v.bound)
                self.assertTrue(any('refused' in line for line in v.rt.log), v.rt.log)

    def test_gate_loss_between_retries_stops_without_another_prepare(self):
        v = self.vm
        v.start()
        v.queue.fire()
        v.admitted = False
        v.queue.drain()
        self.assertEqual(1, len(v.prepared))
        self.assertEqual([], v.bound)

    def test_initialize_permission_is_passed_through_and_never_invented(self):
        v = self.vm
        v.config.InitializeNewEpoch = False
        v.item()
        v.start()
        v.queue.drain()
        self.assertEqual([], v.bound)
        self.assertTrue(all(args[-1] is False for args in v.prepared))
        self.assertEqual({}, v.fs.files)

    def test_existing_epoch_rebinds_without_new_initialization_or_refill(self):
        v = self.vm
        item = v.item()
        v.start()
        v.queue.drain()
        v.economy.Stop()
        # Explicit new mission/process with retained synthetic CE object and files.
        restarted = VM()
        restarted.fs.files.update(v.fs.files)
        restarted.fs.dirs.update(v.fs.dirs)
        restarted.world.items.append(item)
        restarted.config.InitializeNewEpoch = False
        restarted.start()
        restarted.queue.drain()
        self.assertEqual(1, len(restarted.bound))
        self.assertFalse(restarted.bound[0][-1])
        self.assertIs(item, restarted.bound[0][0].m_Entries[0].ItemHandle)

    def test_review_uses_rotated_storage_bounds_and_deduplicated_context_classes(self):
        review = self.vm.review()
        self.assertIsNotNone(review)
        self.assertEqual([98., 6., 201.], review.Volume.Center)
        self.assertEqual(1., review.Volume.Radius)
        self.assertEqual(['SyntheticFood', 'SyntheticTool'], list(review.Volume.Classes))
        self.assertEqual(list(review.Context.Items), list(review.Volume.Classes))
        self.assertEqual('synthetic_food+synthetic_second', review.Context.GroupId)
        # Thin reviewed geometry shrinks the sphere; no minimum-radius inflation.
        self.vm.layout.Survey.Props[0].Bounds.Max[1] = 0.2
        self.assertAlmostEqual(0.1, self.vm.review().Volume.Radius)

    def test_equivalent_wrapped_storage_yaw_keeps_the_placed_binding(self):
        self.vm.sites[0].Target.GetOrientation = lambda: [-180., 0., 0.]
        self.assertIsNotNone(self.vm.review())
        self.vm.sites[0].Target.GetOrientation = lambda: [-179., 0., 0.]
        self.assertIsNone(self.vm.review())

    def test_no_unreviewed_geometry_context_or_fallback_radius(self):
        for kind in ('bounds', 'zero_radius', 'oversize', 'room', 'group', 'storage', 'target_type', 'target_position', 'target_orientation', 'point'):
            with self.subTest(kind=kind):
                v = VM()
                if kind == 'bounds': v.layout.Survey.Props[0].Bounds = None
                if kind == 'zero_radius': v.layout.Survey.Props[0].Bounds.Max[0] = 0.
                if kind == 'oversize':
                    v.layout.Survey.Props[0].Bounds.Min[:] = [-20.] * 3
                    v.layout.Survey.Props[0].Bounds.Max[:] = [20.] * 3
                if kind == 'room': v.rule.Room = 'foreign'
                if kind == 'group': v.rule.ItemGroups[0] = 'unknown'
                if kind == 'storage': v.rule.Storage = 'ground'
                if kind == 'target_type': v.sites[0].Target.GetType = lambda: 'foreign'
                if kind == 'target_position': v.sites[0].Target.GetPosition = lambda: [0.] * 3
                if kind == 'target_orientation': v.sites[0].Target.GetOrientation = lambda: [0.] * 3
                if kind == 'point': v.sites[0].Point = [0.] * 3
                self.assertIsNone(v.review())

    def test_single_hook_follows_ready_placement_and_preserves_module_scope(self):
        text = INTERIORS.read_text()
        self.assertEqual(1, text.count('HCSearchBinding.PlacementComplete('))
        start = body(text, re.search(r'override void OnStart\([^)]*\)\s*\{', text).end())
        self.assertLess(start.index('PlaceCandidate('), start.index('HCSearchBinding.PlacementComplete('))
        self.assertLess(start.index('s_Instance = this;'), start.index('HCSearchBinding.PlacementComplete('))


    def test_binder_is_registered_before_interiors_in_the_same_registry(self):
        text = INTERIORS.read_text()
        registry = re.search(r'modded class HCModuleRegistry\s*\{(.*?)\n\}', text, re.S)
        self.assertIsNotNone(registry, 'interiors modded registry missing')
        block = registry.group(1)
        self.assertEqual(1, block.count('Register(new HCSearchBinding'))
        self.assertLess(block.index('super.RegisterModules();'), block.index('Register(new HCSearchBinding'))
        self.assertLess(block.index('Register(new HCSearchBinding'), block.index('Register(new HCInteriorsModule'))

if __name__ == '__main__':
    unittest.main()
