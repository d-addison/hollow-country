"""w27/w28-debugmap: bounded Camps, lead-ledger and Scenes layers, per-layer stats,
own point share, fair admin wire truncation with carried layer stats.

Synthetic restricted-port fixtures execute the authored Enforce bodies; nothing
here observes DayZ. runtime=PENDING.

TDD receipt (same command for RED and GREEN):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_debug_map_layers -v
"""
import io
import json
import re
from pathlib import Path
from types import SimpleNamespace as N
import tempfile
import unittest

from tests.unit import test_admin_test_kit as _kit
from tests.unit.test_admin_test_kit import base_scope
from tests.unit.test_group_server import EArray
from tests.unit.test_hc_operational_snapshot import NativeMap, NativeString, bind

ROOT = Path(__file__).resolve().parents[2]


def compile_authored(path, cls, name, scope, members=(), modded=True, fields=(), native_strings=None):
    """The shared harness cannot split `array<ref X> name` parameters; hand it `array<X> name`."""
    original = _kit.authored_method

    def authored(path_, cls_, name_, modded_=True):
        params, text = original(path_, cls_, name_, modded_)
        return params.replace('<ref ', '<'), text
    _kit.authored_method = authored
    try:
        return _kit.compile_authored(path, cls, name, scope, members, modded, fields, native_strings)
    finally:
        _kit.authored_method = original
DEBUG_DIR = ROOT / 'mods/HollowCountry/scripts/4_World/Debug'
SNAPSHOT = DEBUG_DIR / 'HCDebugSnapshot.c'
MODULE = DEBUG_DIR / 'HCDebugSnapshotModule.c'
STORE = DEBUG_DIR / 'HCDebugJsonStore.c'
CONSTANTS = dict(MAX_POINTS=1024, MAX_CONTRIBUTOR_POINTS=64, DEBUG_LAYER_POINTS=148,
                 CAMP_LAYER_CAP=24, MAX_LAYER_STATS=16, LEAD_LAYER_CAP=56, SCENE_LAYER_CAP=8,
                 PICKER_LAYER_CAP=4, GROUP_PIN_LAYER_CAP=32, PROPOSAL_LAYER_CAP=24)
LEADS = ROOT / 'mods/HollowCountry/scripts/4_World/Leads/HCLeadModule.c'
SCENES = ROOT / 'mods/HollowCountry/scripts/4_World/Scenes/HCScenesModule.c'
WIRE = ROOT / 'mods/HollowCountry/scripts/4_World/Admin/HCAdminSnapshotWire.c'
LEAD_ROWS = DEBUG_DIR / 'HCDebugLeadRows.c'
PICKERS = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCPickers.c'
GROUPS = ROOT / 'mods/HollowCountry/scripts/4_World/Groups/HCGroupService.c'
MATERIALIZER = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCWorldMaterializer.c'
AI_LIMITS = ROOT / 'mods/HollowCountry/scripts/3_Game/World/HCAILimits.c'


def snapshot_double():
    """A capture whose Describe-window methods are the authored ones."""
    scope = base_scope(array=EArray, HCDebugSnapshot=N(**CONSTANTS), HCDebugPoint=lambda: N(),
                       HCDebugLayerStat=lambda: N(unplaced=0), Vector=lambda x, y, z: (x, y, z))
    document = N(layers=NativeMap(), layerStats=EArray(), routes=EArray())
    snap = N(m_Describing=True, m_Document=document, m_PointCount=0, m_LayerPoints=0,
             m_ContributorPoints=0, HCText=lambda value, limit: value[:limit])
    fields = ('m_Describing', 'm_Document', 'm_PointCount', 'm_LayerPoints', 'm_ContributorPoints')
    members = ('HCText', 'HCPositionValid', 'HCInsertPoint')
    bind(snap, SNAPSHOT, 'HCDebugSnapshot',
         ('HCPositionValid', 'HCInsertPoint', 'AddPoint', 'HCAddLayerPoint', 'HCNoteLayer', 'HCNoteUnplaced', 'HCPointCount'),
         scope, fields=fields, members=members)
    return snap


class Recorder:
    def __init__(self, accept=True):
        self.points, self.notes, self.unplaced, self.accept = [], [], [], accept

    def HCNoteUnplaced(self, layer, count):
        self.unplaced.append((layer, count))

    def HCAddLayerPoint(self, layer, ident, pos, label, detail):
        self.points.append((layer, ident, pos, label, detail))
        return self.accept

    def HCNoteLayer(self, layer, total, shown):
        self.notes.append((layer, total, shown))

    def AddPoint(self, layer, ident, pos, label, detail):
        self.shared = getattr(self, 'shared', []) + [(layer, ident, pos, label, detail)]


def camps_describe(holdouts, inherited=None):
    scope = base_scope(HCHoldouts=N(Get=lambda: holdouts), HCDebugSnapshot=N(**CONSTANTS))
    return compile_authored(SNAPSHOT, 'HCDebugCampSitesContributor', 'HCDescribe', scope, modded=False)


class CampsLayer(unittest.TestCase):
    def holdouts(self, count):
        rows = [N(Id='holdout-%d' % i, PlaceId='place-%d' % i, HousePos=(100.0 + i, 0, 200.0), State='OCCUPIED',
                  Routine='SECRET_ROUTINE', Occupants=3) for i in range(count)]
        self.snapshot_calls = []

        def snapshot(i):
            self.snapshot_calls.append(i)
            return rows[i] if i < len(rows) else None
        return N(Count=lambda: len(rows), Snapshot=snapshot)

    def test_bounded_to_named_cap_with_count_and_truncated_stat(self):
        inherited, recorder = [], Recorder()
        camps_describe(self.holdouts(30), inherited)(N(), recorder)
        self.assertEqual(24, len(recorder.points))
        self.assertEqual({'camps'}, {row[0] for row in recorder.points})
        self.assertEqual([('camps', 30, 24)], recorder.notes)

    def test_one_holdouts_snapshot_per_row_per_capture_feeds_both_layers(self):
        recorder = Recorder()
        camps_describe(self.holdouts(30))(N(), recorder)
        self.assertEqual(list(range(24)), self.snapshot_calls, 'one JSON round trip per row, not two')
        shared = recorder.shared
        self.assertEqual(24, len(shared))
        self.assertEqual({'holdouts'}, {row[0] for row in shared})
        self.assertIn('SECRET_ROUTINE', shared[0][4], 'the holdouts layer keeps its routine/occupant detail')
        self.assertIn('occupants=3', shared[0][4])

    def test_rows_carry_id_position_state_only(self):
        recorder = Recorder()
        camps_describe(self.holdouts(2), [])(N(), recorder)
        layer, ident, pos, label, detail = recorder.points[0]
        self.assertEqual(('holdout-0', (100.0, 0, 200.0)), (ident, pos))
        self.assertIn('state=OCCUPIED', detail)
        self.assertNotIn('SECRET_ROUTINE', detail + label)
        self.assertNotIn('occupants', detail.lower())

    def test_boot_069_total_is_the_catalog_size_not_a_double_count(self):
        # Local boot 069 printed camps total=48 shown=24. HCHoldouts.Count() is the
        # catalog row count (MaxHoldouts default 48); the layer reads it ONCE and
        # does not add the holdouts layer rows to it.
        self.assertRegex(AI_LIMITS.read_text(), r'int MaxHoldouts = 48;')
        holdouts_source = (ROOT / 'mods/HollowCountry/scripts/4_World/World/HCHoldouts.c').read_text()
        self.assertIn('int Count() { if (!m_State) { return 0; } return m_State.Rows.Count(); }', holdouts_source)
        calls, rows = [], self.holdouts(48)
        counted = N(Count=lambda: (calls.append(1), 48)[1], Snapshot=rows.Snapshot)
        recorder = Recorder()
        camps_describe(counted)(N(), recorder)
        self.assertEqual([('camps', 48, 24)], recorder.notes)
        self.assertEqual(1, len(calls), 'Count is read once per capture')
        self.assertEqual(24, len(recorder.shared), 'the holdouts layer rows are a separate, non-additive view')

    def test_refused_points_are_not_counted_as_shown(self):
        recorder = Recorder(accept=False)
        camps_describe(self.holdouts(5), [])(N(), recorder)
        self.assertEqual([('camps', 5, 0)], recorder.notes)

    def test_service_off_emits_nothing_and_no_stat(self):
        recorder, inherited = Recorder(), []
        camps_describe(None, inherited)(N(), recorder)
        self.assertEqual([], recorder.points)
        self.assertEqual([], recorder.notes)

    def test_module_replaces_holdouts_slot_so_registry_cap_is_unchanged(self):
        text = MODULE.read_text()
        self.assertIn('HCKeep(new HCDebugCampSitesContributor)', text)
        self.assertNotIn('HCKeep(new HCDebugHoldoutsContributor)', text)


class LeadLedgerLayer(unittest.TestCase):
    """#194: one clock read per capture, rows from one batch getter, unplaced counted apart."""

    def describe(self, leads, unknown=()):
        position = (3000.0, 0, 4000.0)
        self.clock_reads = []

        def utc():
            self.clock_reads.append(1)
            return 1000
        scope = base_scope(HCLeadModule=N(Get=lambda: leads), HCDebugSnapshot=N(**CONSTANTS),
                           array=EArray, HCWorldClock=N(UTC=utc),
                           HCLeadPolicy=N(Place=lambda ident: None if ident in unknown else N(Position=position, Name='Place ' + ident)))
        return compile_authored(SNAPSHOT, 'HCDebugLeadLedgerContributor', 'HCDescribe', scope, modded=False)

    def module(self, count):
        rows = [N(Id='lead-%d' % i, Kind='CACHE', TargetPlaceId='p%d' % i, Expires=9000 + i, GroupId='') for i in range(count)]
        self.seen_now = []

        def fill(now, out):
            self.seen_now.append(now)
            for row in rows:
                out.Insert(row)
            return len(rows)
        return N(HCDebugLeadRows=fill)

    def test_bounded_with_total_shown_stat_and_named_cap(self):
        recorder = Recorder()
        self.describe(self.module(64))(N(), recorder)
        self.assertEqual(56, len(recorder.points))
        self.assertEqual({'lead-ledger'}, {row[0] for row in recorder.points})
        self.assertEqual([('lead-ledger', 64, 56)], recorder.notes)

    def test_the_clock_is_read_once_per_capture_and_passed_to_the_owner(self):
        recorder = Recorder()
        self.describe(self.module(64))(N(), recorder)
        self.assertEqual(1, len(self.clock_reads), 'one HCWorldClock.UTC() per Describe, not one per row')
        self.assertEqual([1000], self.seen_now)

    def test_rows_are_place_level_and_never_expose_group_or_live_position(self):
        recorder = Recorder()
        self.describe(self.module(1))(N(), recorder)
        layer, ident, pos, label, detail = recorder.points[0]
        self.assertEqual(('lead-0', (3000.0, 0, 4000.0), 'Place p0'), (ident, pos, label))
        self.assertIn('kind=CACHE', detail)
        self.assertIn('expires=9000', detail)
        self.assertNotIn('solo', detail)

    def test_unknown_place_leads_are_counted_apart_not_in_the_layer_total(self):
        recorder = Recorder()
        self.describe(self.module(5), unknown=('p1', 'p3'))(N(), recorder)
        self.assertEqual([('lead-ledger', 3, 3)], recorder.notes, 'total counts drawable rows only')
        self.assertEqual([('lead-ledger', 2)], recorder.unplaced)
        self.assertEqual(['lead-0', 'lead-2', 'lead-4'], [row[1] for row in recorder.points])

    def test_all_unplaced_reads_total_zero_with_the_count(self):
        recorder = Recorder()
        self.describe(self.module(3), unknown=('p0', 'p1', 'p2'))(N(), recorder)
        self.assertEqual([('lead-ledger', 0, 0)], recorder.notes)
        self.assertEqual([('lead-ledger', 3)], recorder.unplaced)

    def test_unplaced_rows_do_not_eat_the_named_cap(self):
        recorder = Recorder()
        unknown = tuple('p%d' % i for i in range(8))
        self.describe(self.module(64), unknown=unknown)(N(), recorder)
        self.assertEqual(56, len(recorder.points))
        self.assertEqual([('lead-ledger', 56, 56)], recorder.notes)
        self.assertEqual([('lead-ledger', 8)], recorder.unplaced)

    def test_module_off_emits_nothing(self):
        recorder = Recorder()
        self.describe(None)(N(), recorder)
        self.assertEqual(([], []), (recorder.points, recorder.notes))
        self.assertEqual([], self.clock_reads)


class ScenesLayer(unittest.TestCase):
    def describe(self, module):
        scope = base_scope(HCScenesModule=N(HCDebugGet=lambda: module), HCDebugSnapshot=N(**CONSTANTS))
        return compile_authored(SNAPSHOT, 'HCDebugScenesContributor', 'HCDescribe', scope, modded=False)

    def module(self, rows):
        return N(HCDebugLeaseCount=lambda: len(rows), HCDebugLease=lambda i: rows[i] if i < len(rows) else None)

    def row(self, chain, placed=True, closing=False):
        return N(ChainId=chain, Stage=1, Anchor=(5000.0, 0, 6000.0), Closing=closing, Placed=placed,
                 Objects=4, DueAt=100, ExpiresAt=900, Complete=False)

    def test_one_row_per_lease_with_state_and_stat(self):
        recorder = Recorder()
        self.describe(self.module([self.row('chain-a'), self.row('chain-b', placed=False)]))(N(), recorder)
        self.assertEqual({'scenes'}, {row[0] for row in recorder.points})
        self.assertEqual([('scenes', 2, 2)], recorder.notes)
        first, second = recorder.points
        self.assertEqual(('chain-a', (5000.0, 0, 6000.0)), (first[1], first[2]))
        self.assertIn('state=placed', first[4])
        self.assertIn('state=placing', second[4])

    def test_closing_wins_and_text_is_not_an_entity_claim(self):
        recorder = Recorder()
        self.describe(self.module([self.row('c', closing=True)]))(N(), recorder)
        self.assertIn('state=closing', recorder.points[0][4])
        self.assertIn('lease anchor', recorder.points[0][4])

    def test_bounded_by_named_scene_cap(self):
        recorder = Recorder()
        self.describe(self.module([self.row('c%d' % i) for i in range(20)]))(N(), recorder)
        self.assertEqual(8, len(recorder.points))
        self.assertEqual([('scenes', 20, 8)], recorder.notes)

    def test_service_off_emits_nothing(self):
        recorder = Recorder()
        self.describe(None)(N(), recorder)
        self.assertEqual(([], []), (recorder.points, recorder.notes))


class OwnerGetters(unittest.TestCase):
    def rows(self):
        return [N(Id='a', Kind='PLACE', TargetPlaceId='p', Expires=2000, GroupId='solo:secret', TextId='t', Source='x'),
                N(Id='old', Kind='PLACE', TargetPlaceId='p', Expires=500, GroupId='g', TextId='t', Source='x'),
                N(Id='b', Kind='DANGER', TargetPlaceId='q', Expires=3000, GroupId='g2', TextId='t', Source='x')]

    def lead_rows_fn(self, store_rows, healthy=True):
        def copy(row):
            return N(**vars(row))
        # No HCWorldClock in scope: the batch getter must use the caller's clock.
        scope = base_scope(HCLeadPolicy=N(Copy=copy), HC_DEBUG_LEAD_SCAN=64)
        receiver = N(m_Store=N(Data=N(Leads=EArray(store_rows))), Get=lambda: receiver if healthy else None)
        fn = compile_authored(LEAD_ROWS, 'HCLeadModule', 'HCDebugLeadRows', scope, ('Get',), modded=True)
        return receiver, fn

    def test_lead_rows_batch_getter_uses_the_passed_clock_and_scans_once(self):
        source = self.rows()
        receiver, rows_fn = self.lead_rows_fn(source)
        out = EArray()
        self.assertEqual(2, rows_fn(receiver, 1000, out))
        self.assertEqual(['a', 'b'], [row.Id for row in out])
        self.assertEqual(['', ''], [row.GroupId for row in out], 'group ids withheld on the copies')
        self.assertEqual('solo:secret', source[0].GroupId, 'the ledger rows are untouched')
        late = EArray()
        self.assertEqual(1, rows_fn(receiver, 2500, late), 'expiry is judged by the passed clock')
        self.assertEqual(['b'], [row.Id for row in late])

    def test_lead_rows_batch_getter_is_empty_when_module_unhealthy_or_clock_bad(self):
        receiver, rows_fn = self.lead_rows_fn(self.rows(), healthy=False)
        out = EArray()
        self.assertEqual(0, rows_fn(receiver, 1000, out))
        self.assertEqual([], list(out))
        receiver, rows_fn = self.lead_rows_fn(self.rows())
        self.assertEqual(0, rows_fn(receiver, 0, out))
        self.assertEqual(0, rows_fn(receiver, 1000, None))

    def test_lead_rows_batch_getter_is_bounded_by_the_named_scan(self):
        many = [N(Id='r%d' % i, Kind='PLACE', TargetPlaceId='p', Expires=5000, GroupId='g', TextId='t', Source='x') for i in range(90)]
        receiver, rows_fn = self.lead_rows_fn(many)
        out = EArray()
        self.assertEqual(64, rows_fn(receiver, 1000, out))
        self.assertEqual(64, len(out))

    def test_test_only_lead_getters_are_gone_and_nothing_calls_them(self):
        # #195: the contributor uses the one-pass HCDebugLeadRows batch getter, so the
        # older per-row getters were dead code kept alive by tests only.
        import re
        for path in LEADS.parent.parent.parent.rglob('*.c'):
            text = path.read_text()
            self.assertIsNone(re.search(r'\bHCDebugLead(?:Count)?\(', text), path.name)
        self.assertIn('HC_DEBUG_LEAD_SCAN', LEADS.read_text(), 'the named scan bound stays')

    def scene_receiver(self):
        lease = N(ChainId='chain-a', Stage=2, Anchor=(1.0, 0, 2.0), Closing=False, Objects=EArray([1, 2, 3]))
        chains = EArray([N(Id='other', DueAt=1, ExpiresAt=2, Complete=True),
                         N(Id='chain-a', DueAt=70, ExpiresAt=800, Complete=False)])
        return lease, N(m_Leases=EArray([lease]), m_State=N(Chains=chains), m_Running=True)

    def test_scene_lease_row_is_a_detached_copy_with_chain_times(self):
        lease, receiver = self.scene_receiver()
        scope = base_scope(HCDebugSceneLeaseRow=lambda: N(), HC_DEBUG_CHAIN_SCAN=16,
                           HCSceneKits=N(HCPlacementComplete=lambda item: True))
        fn = compile_authored(SCENES, 'HCScenesModule', 'HCDebugLease', scope, modded=False)
        row = fn(receiver, 0)
        self.assertEqual(('chain-a', 2, (1.0, 0, 2.0), False, True, 3, 70, 800),
                         (row.ChainId, row.Stage, row.Anchor, row.Closing, row.Placed, row.Objects, row.DueAt, row.ExpiresAt))
        self.assertIsNot(row, lease)
        self.assertIsNone(fn(receiver, 1))
        self.assertIsNone(fn(receiver, -1))

    def test_scene_count_and_owner_accessor(self):
        _lease, receiver = self.scene_receiver()
        count = compile_authored(SCENES, 'HCScenesModule', 'HCDebugLeaseCount', base_scope(), modded=False)
        self.assertEqual(1, count(receiver))
        owner = N(m_Running=True)
        get = compile_authored(SCENES, 'HCScenesModule', 'HCDebugGet', base_scope(s_DebugOwner=owner), modded=False)
        self.assertIs(owner, get(None))
        owner.m_Running = False
        self.assertIsNone(get(None))

    def test_scene_owner_is_published_on_start_and_released_on_stop_only_by_itself(self):
        text = SCENES.read_text()
        self.assertIn('s_DebugOwner = this;', text)
        self.assertIn('HCDebugRelease();', text)
        self.assertIn('if (s_DebugOwner == this) { s_DebugOwner = null; }', text)


class WireFairness(unittest.TestCase):
    def wire(self):
        scope = base_scope(array=EArray, str=NativeString, HCDebugSnapshot=N(HCText=lambda value, limit: value[:limit]),
                           HCOperationalContributors=N(HCAppend=lambda reply, rows, lost: None),
                           HCAdminReply=lambda: N(Lines=EArray(), Marks=EArray(), Notice=''),
                           HCAdminMark=lambda: N(), Vector=lambda x, y, z: (x, y, z),
                           HCAdminSnapshotWire=N(MAX_WIRE_LAYERS=24, NOTICE_BYTES=1024, NOTICE_UNPLACED_SHARE=4), Print=lambda line: None)
        wire = N()
        bind(wire, WIRE, 'HCAdminSnapshotWire', ('HCMark', 'HCSlot', 'HCAllocate', 'HCFitted', 'HCFitEntries', 'HCBuild'), scope,
             members=('HCMark', 'HCSlot', 'HCAllocate', 'HCFitted', 'HCFitEntries'), native_strings=NativeString)
        return wire

    def capture(self, layers, routes=(), stats=()):
        stats = [N(**dict(dict(unplaced=0), **vars(row))) for row in stats]
        rows = NativeMap({name: EArray([N(x=1, z=2, label=name, detail='d') for _ in range(count)])
                          for name, count in layers})
        document = N(layers=rows, routes=EArray(routes), layerStats=EArray(stats), operational=EArray(),
                     operationalTruncated=0, truncated=0)
        return N(HCDocument=lambda: document)

    def per_layer(self, reply):
        counts = {}
        for mark in reply.Marks:
            counts[mark.Layer] = counts.get(mark.Layer, 0) + 1
        return counts

    def test_water_fill_gives_every_layer_a_share_then_redistributes_the_rest(self):
        wire, allowance = self.wire(), EArray()
        wire.HCAllocate(EArray([400, 200, 24]), 512, allowance)
        self.assertEqual([288, 200, 24], list(allowance))
        small = EArray()
        wire.HCAllocate(EArray([3, 5]), 512, small)
        self.assertEqual([3, 5], list(small))
        zero = EArray()
        wire.HCAllocate(EArray(), 512, zero)
        self.assertEqual([], list(zero))

    def test_late_layer_is_not_starved_when_the_wire_is_full(self):
        reply = self.wire().HCBuild(self.capture([('ai-units', 400), ('players', 200), ('camps', 24)]), 7)
        counts = self.per_layer(reply)
        self.assertEqual(512, len(reply.Marks))
        self.assertEqual(24, counts['camps'], 'a late layer keeps its whole small set')
        self.assertGreaterEqual(counts['ai-units'], 200)
        self.assertIn('camps:24/24', reply.Notice)
        self.assertIn('ai-units:%d/400' % counts['ai-units'], reply.Notice)
        self.assertIn('dropped=112', reply.Notice)

    def test_layer_stats_carry_contributor_side_loss_in_total(self):
        stat = N(layer='camps', total=30, shown=24, truncated=1)
        reply = self.wire().HCBuild(self.capture([('camps', 24)], stats=[stat]), 1)
        self.assertIn('camps:24/30', reply.Notice)
        self.assertIn('dropped=0', reply.Notice, 'wire losses and contributor losses are reported apart')

    def test_routes_stay_whole_within_the_layer_share(self):
        route = N(layer='events', label='r', points=EArray([EArray([1, 2]) for _ in range(40)]))
        reply = self.wire().HCBuild(self.capture([('events', 30), ('players', 500)], routes=[route]), 1)
        events = [mark for mark in reply.Marks if mark.Layer == 'events' and mark.Route == 1]
        self.assertIn(len(events), (0, 40))
        counts = self.per_layer(reply)
        self.assertLessEqual(counts['events'], 256)
        self.assertEqual(512, len(reply.Marks))

    def test_more_than_the_named_layer_cap_reports_unsent_layers_and_stays_at_caps(self):
        reply = self.wire().HCBuild(self.capture([('l%02d' % i, 40) for i in range(28)]), 1)
        self.assertEqual(24, len(self.per_layer(reply)), 'MAX_WIRE_LAYERS leaves room for the w29 layers')
        self.assertLessEqual(len(reply.Marks), 512)
        self.assertIn('layers_unsent=4', reply.Notice)
        self.assertLessEqual(len(reply.Notice.encode('utf-8')), 1024)

    def test_unused_route_allowance_is_redistributed_to_layers_with_unsent_points(self):
        # events: 200 points + one 64-vertex route = demand 264, allowance 256: the
        # whole route cannot fit, so 56 of its allowance stay unused. players wants
        # 600 and must receive that leftover on top of its own 256 share.
        route = N(layer='events', label='r', points=EArray([EArray([1, 2]) for _ in range(64)]))
        reply = self.wire().HCBuild(self.capture([('events', 200), ('players', 600)], routes=[route]), 1)
        counts = self.per_layer(reply)
        self.assertEqual(200, counts['events'])
        self.assertEqual([], [mark for mark in reply.Marks if mark.Route == 1], 'the route stays whole or absent')
        self.assertEqual(312, counts['players'], '256 share + 56 leftover')
        self.assertEqual(512, len(reply.Marks))
        self.assertIn('players:312/600', reply.Notice)

    def test_redistribution_never_exceeds_the_mark_cap_or_a_layers_own_rows(self):
        route = N(layer='events', label='r', points=EArray([EArray([1, 2]) for _ in range(64)]))
        reply = self.wire().HCBuild(self.capture([('events', 200), ('players', 270)], routes=[route]), 1)
        counts = self.per_layer(reply)
        self.assertEqual(270, counts['players'], 'a layer is never given more than it has')
        self.assertLessEqual(len(reply.Marks), 512)

    def test_unplaced_counts_ride_in_the_notice_only_when_nonzero(self):
        stat = N(layer='lead-ledger', total=3, shown=3, truncated=0, unplaced=2)
        reply = self.wire().HCBuild(self.capture([('lead-ledger', 3)], stats=[stat]), 1)
        self.assertIn('unplaced=lead-ledger:2', reply.Notice)
        self.assertIn('lead-ledger:3/3', reply.Notice, 'unplaced rows are not part of the layer total')
        quiet = self.wire().HCBuild(self.capture([('camps', 2)], stats=[N(layer='camps', total=2, shown=2, truncated=0, unplaced=0)]), 1)
        self.assertNotIn('unplaced=', quiet.Notice)

    # w31-p3admin3 #196: the Notice keeps its fixed head and tail whole, adds layers=/unplaced=
    # entries only while they fit, cuts on entry boundaries and says how many were left out.
    def crowded_notice(self, with_unplaced=True):
        names = ['%02d' % i + 'x' * 22 for i in range(24)]  # 24 chars, the wire's name cap
        stats = [N(layer=name, total=900, shown=40, truncated=1, unplaced=(123 if with_unplaced else 0)) for name in names]
        return self.wire().HCBuild(self.capture([(name, 600) for name in names], stats=stats), 1).Notice

    def test_a_crowded_notice_keeps_its_tail_and_stays_inside_the_byte_cap(self):
        notice = self.crowded_notice()
        self.assertLessEqual(len(notice.encode('utf-8')), 1024)
        self.assertTrue(notice.endswith('; captured over several ticks; expires in 60s'), notice[-80:])
        self.assertIn('; layers_unsent=0', notice)

    def test_a_crowded_notice_cuts_on_entry_boundaries_and_counts_what_it_dropped(self):
        notice = self.crowded_notice()
        layers = re.search(r'; layers=(.*?); layers_unsent=', notice).group(1).split(',')
        entry = re.compile(r'^\d\dx{22}:\d+/\d+$')
        shown = [item for item in layers if entry.match(item)]
        self.assertEqual(layers[:len(shown)], shown, 'whole entries first, then only the marker')
        self.assertEqual(['+%d more' % (24 - len(shown))], layers[len(shown):])
        self.assertLess(len(shown), 24, 'the fixture must overflow, or this test proves nothing')
        unplaced = re.search(r'; unplaced=(.*?); captured', notice).group(1).split(',')
        kept = [item for item in unplaced if re.match(r'^\d\dx{22}:123$', item)]
        self.assertEqual(unplaced[:len(kept)], kept)
        self.assertGreater(len(kept), 0, 'unplaced keeps a reserved share')
        self.assertTrue(len(kept) == 24 or unplaced[len(kept):] == ['+%d more' % (24 - len(kept))])

    def test_a_notice_that_fits_has_no_more_marker(self):
        notice = self.wire().HCBuild(self.capture([('players', 3), ('camps', 2)]), 1).Notice
        self.assertNotIn(' more', notice)

    def test_light_snapshot_is_sent_whole(self):
        reply = self.wire().HCBuild(self.capture([('players', 3), ('camps', 2)]), 1)
        self.assertEqual(5, len(reply.Marks))
        self.assertIn('players:3/3', reply.Notice)
        self.assertIn('dropped=0', reply.Notice)


class LayerShare(unittest.TestCase):
    def test_shared_pool_stops_before_the_reserved_share_and_total_stays_at_wire_cap(self):
        snap = snapshot_double()
        for index in range(1100):
            snap.m_ContributorPoints = 0
            snap.AddPoint('ai-units', 'u%d' % index, (10.0, 0, 20.0), 'u', 'd')
        self.assertEqual(1024 - 148, snap.m_PointCount, 'ai-units and friends are not squeezed below their pool')
        for index in range(200):
            snap.m_ContributorPoints = 0
            snap.HCAddLayerPoint('camps', 'c%d' % index, (10.0, 0, 20.0), 'c', 'd')
        self.assertEqual(148, snap.m_LayerPoints)
        self.assertEqual(1024, snap.HCPointCount())
        self.assertEqual(1024, sum(len(rows) for rows in snap.m_Document.layers.values()))

    def test_layer_point_respects_per_contributor_cap_and_validity(self):
        snap = snapshot_double()
        self.assertFalse(snap.HCAddLayerPoint('camps', '', (10.0, 0, 20.0), 'l', 'd'))
        self.assertFalse(snap.HCAddLayerPoint('camps', 'x', (-1.0, 0, 20.0), 'l', 'd'))
        accepted = [snap.HCAddLayerPoint('camps', 'c%d' % i, (10.0, 0, 20.0), 'l', 'd') for i in range(70)]
        self.assertEqual(64, accepted.count(True))
        snap.m_Describing = False
        snap.m_ContributorPoints = 0
        self.assertFalse(snap.HCAddLayerPoint('camps', 'late', (10.0, 0, 20.0), 'l', 'd'))

    def test_note_layer_records_count_shown_truncated_and_is_bounded(self):
        snap = snapshot_double()
        snap.HCNoteLayer('camps', 30, 24)
        snap.HCNoteLayer('quiet', 3, 3)
        first, second = snap.m_Document.layerStats
        self.assertEqual(('camps', 30, 24, 1), (first.layer, first.total, first.shown, first.truncated))
        self.assertEqual(('quiet', 3, 3, 0), (second.layer, second.total, second.shown, second.truncated))
        for index in range(40):
            snap.HCNoteLayer('l%d' % index, 1, 1)
        self.assertEqual(16, len(snap.m_Document.layerStats))
        snap.m_Describing = False
        before = len(snap.m_Document.layerStats)
        snap.HCNoteLayer('outside', 1, 1)
        self.assertEqual(before, len(snap.m_Document.layerStats))


class UnplacedStat(unittest.TestCase):
    def test_note_unplaced_sets_the_count_on_the_layers_stat_row(self):
        snap = snapshot_double()
        snap.HCNoteLayer('lead-ledger', 3, 3)
        snap.HCNoteLayer('camps', 5, 5)
        snap.HCNoteUnplaced('lead-ledger', 2)
        ledger, camps = snap.m_Document.layerStats
        self.assertEqual((3, 3, 0, 2), (ledger.total, ledger.shown, ledger.truncated, ledger.unplaced))
        self.assertEqual(0, camps.unplaced, 'default is zero and other layers are untouched')

    def test_note_unplaced_without_a_stat_row_or_outside_describe_is_a_no_op(self):
        snap = snapshot_double()
        snap.HCNoteUnplaced('missing', 4)
        self.assertEqual(0, len(snap.m_Document.layerStats))
        snap.HCNoteLayer('x', 1, 1)
        snap.m_Describing = False
        snap.HCNoteUnplaced('x', 9)
        self.assertEqual(0, snap.m_Document.layerStats[0].unplaced)

    def test_negative_counts_are_ignored(self):
        snap = snapshot_double()
        snap.HCNoteLayer('x', 1, 1)
        snap.HCNoteUnplaced('x', -3)
        self.assertEqual(0, snap.m_Document.layerStats[0].unplaced)

    def test_the_document_dto_carries_the_field_and_the_doc_names_it(self):
        text = SNAPSHOT.read_text()
        dto = text[text.index('class HCDebugLayerStat'):text.index('class HCDebugDocument')]
        self.assertIn('int unplaced;', dto)


class LayerShareSplit(unittest.TestCase):
    def test_the_hardened_share_is_exactly_the_sum_of_the_named_layer_caps(self):
        text = SNAPSHOT.read_text()
        caps = {name: int(re.search(r'static const int %s = (\d+);' % name, text).group(1))
                for name in ('CAMP_LAYER_CAP', 'LEAD_LAYER_CAP', 'SCENE_LAYER_CAP', 'PICKER_LAYER_CAP',
                             'GROUP_PIN_LAYER_CAP', 'PROPOSAL_LAYER_CAP', 'DEBUG_LAYER_POINTS', 'MAX_POINTS')}
        self.assertEqual(1024, caps['MAX_POINTS'], 'the wire cap is unchanged')
        shares = sum(value for name, value in caps.items() if name.endswith('_LAYER_CAP'))
        self.assertEqual(caps['DEBUG_LAYER_POINTS'], shares)
        for name, value in caps.items():
            self.assertEqual(CONSTANTS[name], value, name + ' drifted from the test constants')


def strip_generics(text, name):
    """Language scaffolding only: drop <...> after a template class name."""
    out, index = [], 0
    while True:
        found = text.find(name + '<', index)
        if found < 0:
            out.append(text[index:])
            return ''.join(out)
        out.append(text[index:found + len(name)])
        depth, cursor = 0, found + len(name)
        while True:
            depth += (text[cursor] == '<') - (text[cursor] == '>')
            cursor += 1
            if depth == 0:
                break
        index = cursor


class SaveSerializesStats(unittest.TestCase):
    def authored_save(self, tmp, saved):
        source = strip_generics(STORE.read_text(), 'JsonFileLoader')
        # MakeData(value, outText, error, false) writes an out string: model it as a
        # returned string, keeping the authored failure check as `if (!text)`.
        source = re.sub(r'if \(!JsonFileLoader\.MakeData\((\S+), (\w+), error, false\)\) \{ return false; \}',
                        r'\2 = JsonFileLoader.Make(\1); if (!\2) { return false; }', source)
        path = Path(tmp) / 'HCDebugJsonStore.c'
        path.write_text(source)
        scope = base_scope(JsonFileLoader=N(Make=lambda value: json.dumps(value) if value is not None else ''))
        out = N(value=0)
        fn = compile_authored(path, 'HCDebugJsonStore', 'HCSave', scope, ('HCSaveText',), modded=False)
        holder = N(HCSaveText=lambda p, text, limit, bytes: (saved.append(text), True)[1])
        return lambda document: fn(holder, 'x', document, 1048576, out)

    def test_saved_snapshot_text_carries_layer_stats(self):
        saved = []
        document = N(time=5, layers={}, routes=[], operational=[], contributors=3, truncated=0,
                     operationalTruncated=0,
                     layerStats=[{'layer': 'camps', 'total': 30, 'shown': 24, 'truncated': 1}])
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(self.authored_save(tmp, saved)(document))
        envelope = json.loads(saved[0])
        self.assertEqual(document.layerStats, envelope['layerStats'])
        self.assertEqual(1, envelope['version'])
        self.assertEqual(3, envelope['contributors'])

    def test_failed_stats_encoding_refuses_the_save(self):
        saved = []
        document = N(time=5, layers={}, routes=[], operational=[], contributors=0, truncated=0,
                     operationalTruncated=0, layerStats=None)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(self.authored_save(tmp, saved)(document))
        self.assertEqual([], saved)


class Text(str):
    """Synthetic native string: only the IndexOf used by the authored pin kind map."""
    def IndexOf(self, needle):
        return self.find(needle)


class PickersLayer(unittest.TestCase):
    def describe(self, pickers):
        scope = base_scope(HCPickers=N(Get=lambda: pickers), HCDebugSnapshot=N(**CONSTANTS))
        return compile_authored(SNAPSHOT, 'HCDebugPickersContributor', 'HCDescribe', scope, modded=False)

    def module(self, rows):
        return N(HCDebugPickerCount=lambda: len(rows), HCDebugPicker=lambda i: rows[i] if i < len(rows) else None)

    def row(self, located=True, phase='leaving'):
        return N(Phase=phase, Locator='actor', Refusal='', HasPosition=located, Position=(700.0, 0, 800.0), Generation=2)

    def test_a_located_trip_is_one_point_with_phase_and_no_identity(self):
        recorder = Recorder()
        self.describe(self.module([self.row()]))(N(), recorder)
        self.assertEqual([('pickers', 1, 1)], recorder.notes)
        layer, ident, pos, label, detail = recorder.points[0]
        self.assertEqual(('pickers', 'picker-0', (700.0, 0, 800.0)), (layer, ident, pos))
        self.assertIn('phase=leaving', detail)
        self.assertIn('located=actor', detail)
        self.assertIn('not a body-presence claim', detail)

    def test_a_trip_without_a_known_position_is_counted_unplaced_not_drawn(self):
        recorder = Recorder()
        self.describe(self.module([self.row(located=False, phase='quarantined')]))(N(), recorder)
        self.assertEqual([], recorder.points)
        self.assertEqual([('pickers', 0, 0)], recorder.notes)
        self.assertEqual([('pickers', 1)], recorder.unplaced)

    def test_bounded_by_the_named_picker_cap(self):
        recorder = Recorder()
        self.describe(self.module([self.row() for _ in range(9)]))(N(), recorder)
        self.assertEqual(4, len(recorder.points))
        self.assertEqual([('pickers', 9, 4)], recorder.notes, 'the stat row keeps the true total')

    def test_module_off_or_idle_emits_nothing_and_no_stat(self):
        recorder = Recorder()
        self.describe(None)(N(), recorder)
        self.assertEqual(([], [], []), (recorder.points, recorder.notes, recorder.unplaced))

    def test_picker_getter_reports_active_trips_only_and_detached_data(self):
        actor = N(GetPosition=lambda: (10.0, 0, 20.0))
        trip = N(m_Ready=True, m_State=N(Phase='leaving', Generation=3, Refusal=''),
                 m_IO=N(Actor=actor, Source=None, Home=None, HCLive=lambda: True))
        receiver = N(m_Trip=trip)
        scope = base_scope(HCDebugPickerRow=lambda: N(Locator='none', HasPosition=False), HCDebugSnapshot=N(**CONSTANTS))
        count = compile_authored(PICKERS, 'HCPickers', 'HCDebugPickerCount', scope, modded=False)
        row_fn = compile_authored(PICKERS, 'HCPickers', 'HCDebugPicker', scope, modded=False)
        self.assertEqual(1, count(receiver))
        row = row_fn(receiver, 0)
        self.assertEqual(('leaving', 'actor', True, (10.0, 0, 20.0), 3),
                         (row.Phase, row.Locator, row.HasPosition, row.Position, row.Generation))
        self.assertFalse(hasattr(row, 'PartyId') or hasattr(row, 'ActorId'), 'no ids leave the owner')
        self.assertIsNone(row_fn(receiver, 1))
        self.assertIsNone(row_fn(receiver, -1))
        trip.m_State.Phase = 'idle'
        self.assertEqual(0, count(receiver), 'an idle or refused picker has nothing to place')
        self.assertIsNone(row_fn(receiver, 0))

    def test_picker_getters_return_nothing_while_the_journal_is_not_ready(self):
        # #195: a journal with an invalid phase leaves m_Ready false; the layer must
        # not show a row carrying that phase text.
        actor = N(GetPosition=lambda: (10.0, 0, 20.0))
        scope = base_scope(HCDebugPickerRow=lambda: N(Locator='none', HasPosition=False), HCDebugSnapshot=N(**CONSTANTS))
        count = compile_authored(PICKERS, 'HCPickers', 'HCDebugPickerCount', scope, modded=False)
        row_fn = compile_authored(PICKERS, 'HCPickers', 'HCDebugPicker', scope, modded=False)
        for phase in ('leaving', 'returning', 'not-a-phase', 'quarantined'):
            trip = N(m_Ready=False, m_State=N(Phase=phase, Generation=3, Refusal=''),
                     m_IO=N(Actor=actor, Source=None, Home=None, HCLive=lambda: True))
            receiver = N(m_Trip=trip)
            self.assertEqual(0, count(receiver), phase)
            self.assertIsNone(row_fn(receiver, 0), phase)
            trip.m_Ready = True
            self.assertEqual(1, count(receiver), phase)
            self.assertIsNotNone(row_fn(receiver, 0), phase)

    def test_picker_getter_falls_back_to_source_then_home_and_then_unplaced(self):
        source = N(GetPosition=lambda: (1.0, 0, 2.0))
        home = N(GetPosition=lambda: (3.0, 0, 4.0))
        scope = base_scope(HCDebugPickerRow=lambda: N(Locator='none', HasPosition=False), HCDebugSnapshot=N(**CONSTANTS))
        row_fn = compile_authored(PICKERS, 'HCPickers', 'HCDebugPicker', scope, modded=False)

        def receiver(actor_live, src, hom):
            io = N(Actor=None, Source=src, Home=hom, HCLive=lambda: actor_live)
            return N(m_Trip=N(m_Ready=True, m_State=N(Phase='returning', Generation=1, Refusal=''), m_IO=io))
        self.assertEqual(('source', (1.0, 0, 2.0)), tuple(getattr(row_fn(receiver(False, source, home), 0), k) for k in ('Locator', 'Position')))
        self.assertEqual('home', row_fn(receiver(False, None, home), 0).Locator)
        none = row_fn(receiver(False, None, None), 0)
        self.assertEqual(('none', False), (none.Locator, none.HasPosition))


class GroupPinsLayer(unittest.TestCase):
    def describe(self, groups):
        scope = base_scope(HCGroupService=N(Get=lambda: groups), HCDebugSnapshot=N(**CONSTANTS),
                           HCDebugGroupPinRow=lambda: N(), array=EArray)
        fields = ('m_Cursor', 'm_Total', 'm_Rows', 'm_PublishedRows', 'm_PublishedTotal', 'm_GroupOwner')
        fn = compile_authored(SNAPSHOT, 'HCDebugGroupPinsContributor', 'HCDescribe', scope, modded=False, fields=fields)
        def describe(obj, recorder):
            for key, value in dict(m_Cursor=0, m_Total=0, m_Rows=EArray(), m_PublishedRows=EArray(),
                                   m_PublishedTotal=0, m_GroupOwner=None).items():
                if not hasattr(obj, key): setattr(obj, key, value)
            return fn(obj, recorder)
        return describe

    def service(self, rows, total=None):
        self.caps = []

        def fill(cursor, group_cap, cap, out):
            self.caps.append(cap)
            for row in rows[:cap]:
                out.Insert(row)
            return len(rows) if total is None else total
        return N(HCDebugPins=fill, HCDebugPinGroupCount=lambda:1)

    def pin(self, kind='ping', i=0):
        return N(Kind=kind, Position=(100.0 + i, 0, 200.0), ExpiresUtc=5000)

    def test_rows_are_position_and_kind_only_with_anonymous_ids(self):
        recorder = Recorder()
        self.describe(self.service([self.pin('ping', 0), self.pin('death', 1)]))(N(), recorder)
        self.assertEqual([('group-pins', 2, 2)], recorder.notes)
        first, second = recorder.points
        self.assertEqual(('group-pins', 'pin-0', (100.0, 0, 200.0), 'ping'), first[:4])
        self.assertEqual('pin-1', second[1])
        for row in recorder.points:
            self.assertIn('group, player and name withheld', row[4])
        self.assertIn('kind=ping', first[4])
        self.assertIn('expires=5000', first[4])

    def test_the_owner_is_asked_for_no_more_than_the_named_cap_and_total_can_exceed_it(self):
        recorder = Recorder()
        self.describe(self.service([self.pin(i=i) for i in range(40)], total=40))(N(), recorder)
        self.assertEqual([32], self.caps)
        self.assertEqual(32, len(recorder.points))
        self.assertEqual([('group-pins', 40, 32)], recorder.notes)

    def test_service_off_emits_nothing_and_no_stat(self):
        recorder = Recorder()
        self.describe(None)(N(), recorder)
        self.assertEqual(([], []), (recorder.points, recorder.notes))

    def owner(self, groups=2, healthy=True, pin_sets=None, pins_enabled=True):
        records = [N(Id=10 + i) for i in range(groups)]
        pin_sets = pin_sets if pin_sets is not None else {}
        collect_caps = []

        def collect(group, cap, out):
            collect_caps.append(cap)
            for place in pin_sets.get(group.Id, []):
                out.Insert(place)
        pins = N(Collect=collect)
        receiver = N(m_Healthy=healthy, m_State=N(Groups=EArray(records)), m_Config=N(MaxGroups=32),
                     HCDebugPinKind=None)
        scope = base_scope(HCGroupPins=N(Get=lambda: pins if pins_enabled else None), array=EArray,
                           HCDebugGroupPinRow=lambda: N(), HCGroupService=N(), int=N(MAX=2147483647))
        kind_fn = compile_authored(GROUPS, 'HCGroupService', 'HCDebugPinKind', scope, modded=False)
        receiver.HCDebugPinKind = lambda ident: kind_fn(receiver, ident)
        count_fn = compile_authored(GROUPS, 'HCGroupService', 'HCDebugPinGroupCount', scope, modded=False)
        receiver.HCDebugPinGroupCount = lambda: count_fn(receiver)
        fn = compile_authored(GROUPS, 'HCGroupService', 'HCDebugPins', scope, ('HCDebugPinKind', 'HCDebugPinGroupCount'), modded=False)
        return receiver, fn, collect_caps

    def place(self, ident, name='Alice Smith', x=1.0, expires=0):
        return N(Id=Text(ident), Name=name, Position=(x, 0, 2.0), HCPinExpiresUtc=expires)

    def test_getter_maps_kinds_withholds_ids_and_names_and_detaches(self):
        places = {10: [self.place('hc-ping:10:SESSION42', name='Bob (need help)', expires=900),
                       self.place('hc-death:7:steam-76561190000000000'),
                       self.place('hc-lead:lead-1'), self.place('hc-found:Old Barn'), self.place('weird')]}
        receiver, fn, _caps = self.owner(pin_sets=places)
        rows = EArray()
        self.assertEqual(5, fn(receiver, 0, 32, 32, rows))
        self.assertEqual(['ping', 'death', 'lead', 'trail', 'pin'], [row.Kind for row in rows])
        self.assertEqual(900, rows[0].ExpiresUtc)
        for row in rows:
            self.assertEqual({'Kind', 'Position', 'ExpiresUtc'}, set(vars(row)), 'no id, name or group leaves the owner')
        self.assertIsNot(rows[0].Position, places[10][0])

    def test_getter_is_bounded_by_cap_and_still_counts_the_rest(self):
        places = {10: [self.place('hc-ping:10:s%d' % i) for i in range(6)], 11: [self.place('hc-lead:l%d' % i) for i in range(6)]}
        receiver, fn, caps = self.owner(pin_sets=places)
        rows = EArray()
        self.assertEqual(12, fn(receiver, 0, 32, 5, rows))
        self.assertEqual(5, len(rows))
        self.assertTrue(all(cap == 2147483647 for cap in caps), 'display cap never truncates the page total')

    def test_getter_scans_at_most_the_configured_group_count(self):
        receiver, fn, caps = self.owner(groups=50, pin_sets={g: [self.place('hc-ping:x:y')] for g in range(10, 60)})
        rows = EArray()
        self.assertEqual(32, fn(receiver, 0, 32, 64, rows), 'MaxGroups is the existing config bound')
        self.assertEqual(32, len(caps))

    def test_getter_is_empty_when_unhealthy_or_pins_module_off_or_bad_arguments(self):
        for kwargs in (dict(healthy=False), dict(pins_enabled=False)):
            receiver, fn, _caps = self.owner(pin_sets={10: [self.place('hc-ping:a:b')]}, **kwargs)
            rows = EArray()
            self.assertEqual(0, fn(receiver, 0, 32, 8, rows))
            self.assertEqual([], list(rows))
        receiver, fn, _caps = self.owner(pin_sets={10: [self.place('hc-ping:a:b')]})
        self.assertEqual(0, fn(receiver, 0, 32, 0, EArray()))
        self.assertEqual(0, fn(receiver, 0, 32, 8, None))


class ProposalsLayer(unittest.TestCase):
    def describe(self, materializer):
        scope = base_scope(HCWorldMaterializer=N(HCDebugGet=lambda: materializer), HCDebugSnapshot=N(**CONSTANTS))
        return compile_authored(SNAPSHOT, 'HCDebugProposalsContributor', 'HCDescribe', scope, modded=False)

    def module(self, count):
        rows = [N(Id='prop-%d' % i, PlaceId='place-%d' % i, Kind='holdout', Position=(400.0 + i, 0, 500.0),
                  ActorCap=3, State='queued', AgeSeconds=12) for i in range(count)]
        return N(HCDebugProposalCount=lambda: len(rows), HCDebugProposal=lambda i: rows[i] if i < len(rows) else None)

    def test_rows_show_state_and_are_not_live_body_claims(self):
        recorder = Recorder()
        self.describe(self.module(2))(N(), recorder)
        self.assertEqual({'materializer-proposals'}, {row[0] for row in recorder.points})
        self.assertEqual([('materializer-proposals', 2, 2)], recorder.notes)
        layer, ident, pos, label, detail = recorder.points[0]
        self.assertEqual(('prop-0', (400.0, 0, 500.0), 'place-0'), (ident, pos, label))
        self.assertIn('state=queued', detail)
        self.assertIn('actor_cap=3', detail)
        self.assertIn('not a live-body claim', detail)

    def test_bounded_by_the_named_proposal_cap(self):
        recorder = Recorder()
        self.describe(self.module(40))(N(), recorder)
        self.assertEqual(24, len(recorder.points))
        self.assertEqual([('materializer-proposals', 40, 24)], recorder.notes)

    def test_module_off_emits_nothing(self):
        recorder = Recorder()
        self.describe(None)(N(), recorder)
        self.assertEqual(([], []), (recorder.points, recorder.notes))

    def getters(self, running=True):
        leases = EArray([
            N(Proposal=N(Id='a', FactionId='f', PlaceId='p1', Position=(5.0, 0, 6.0), ActorCap=4, Kind='party'),
              Claimed=False, Finished=False, Materialized=False, Created=100.0),
            N(Proposal=N(Id='b', FactionId='f', PlaceId='p2', Position=(7.0, 0, 8.0), ActorCap=2, Kind='holdout'),
              Claimed=True, Finished=False, Materialized=False, Created=40.0),
            N(Proposal=N(Id='c', FactionId='f', PlaceId='p3', Position=(9.0, 0, 9.0), ActorCap=1, Kind='holdout'),
              Claimed=True, Finished=True, Materialized=True, Created=10.0)])
        receiver = N(m_Active=leases, m_Running=running, m_Clock=160.0)
        scope = base_scope(HCDebugProposalRow=lambda: N(State='queued'), s_Instance=receiver, Math=N(Floor=lambda value: int(value)))
        return receiver, scope

    def test_getter_returns_detached_rows_with_derived_state_and_age_without_claiming(self):
        receiver, scope = self.getters()
        count = compile_authored(MATERIALIZER, 'HCWorldMaterializer', 'HCDebugProposalCount', scope, modded=False)
        row_fn = compile_authored(MATERIALIZER, 'HCWorldMaterializer', 'HCDebugProposal', scope, modded=False)
        self.assertEqual(3, count(receiver))
        states = [row_fn(receiver, i) for i in range(3)]
        self.assertEqual(['queued', 'claimed', 'materialized'], [row.State for row in states])
        self.assertEqual([60, 120, 150], [row.AgeSeconds for row in states])
        self.assertEqual(('a', 'p1', 'party', 4, (5.0, 0, 6.0)),
                         (states[0].Id, states[0].PlaceId, states[0].Kind, states[0].ActorCap, states[0].Position))
        self.assertIsNone(row_fn(receiver, 3))
        self.assertIsNone(row_fn(receiver, -1))
        self.assertFalse(receiver.m_Active[0].Claimed, 'reading never claims or expires a proposal')
        self.assertFalse(hasattr(states[0], 'Identity'), 'no party identity leaves the owner')

    def test_owner_accessor_requires_a_running_module(self):
        receiver, scope = self.getters()
        scope['s_Instance'] = receiver
        get = compile_authored(MATERIALIZER, 'HCWorldMaterializer', 'HCDebugGet', scope, modded=False)
        self.assertIs(receiver, get(None))
        receiver.m_Running = False
        self.assertIsNone(get(None))
        scope['s_Instance'] = None
        self.assertIsNone(get(None))

    def test_source_never_calls_next_or_expire_from_the_debug_seam(self):
        text = MATERIALIZER.read_text()
        body = text[text.index('HCDebugProposalCount'):]
        body = body[:body.index('protected void HCPlanLine') if 'protected void HCPlanLine' in body else len(body)]
        for forbidden in ('Next(', 'Expire(', 'HCClaim(', 'Result('):
            self.assertNotIn(forbidden, text[text.index('int HCDebugProposalCount'):text.index('HCDebugProposal(int') + 1500])


class NewLayersAreRegistered(unittest.TestCase):
    def test_the_three_layers_are_module_built_ins_inside_the_registry_cap(self):
        text = MODULE.read_text()
        for name in ('HCDebugPickersContributor', 'HCDebugGroupPinsContributor', 'HCDebugProposalsContributor'):
            self.assertIn('HCKeep(new %s);' % name, text)
        self.assertEqual(13, len(re.findall(r'^\s*HCKeep\(', text, re.M)))

    def test_no_contributor_exports_player_identity(self):
        text = SNAPSHOT.read_text()
        for cls in ('HCDebugPickersContributor', 'HCDebugGroupPinsContributor', 'HCDebugProposalsContributor'):
            body = text[text.index('class ' + cls):]
            body = body[:body.index('\n}\n')]
            for forbidden in ('GetIdentity', 'GetName', 'GetId', 'GetPlayers', 'PlayerBase'):
                self.assertNotIn(forbidden, body, cls)


class WebmapLegend(unittest.TestCase):
    def serve(self, fixture):
        from tools.webmap import server

        class Connection:
            def __init__(self, request):
                self.input, self.output = io.BytesIO(request), io.BytesIO()

            def makefile(self, *_args):
                return self.input

            def sendall(self, data):
                self.output.write(data)

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'snapshot.json'
            path.write_text(json.dumps(fixture), encoding='utf-8')
            connection = Connection(b'GET /snapshot.json HTTP/1.0\r\n\r\n')
            server.make_handler(path, None)(connection, ('127.0.0.1', 1), None)
            return int(connection.output.getvalue().split()[1])

    def base(self, stats):
        return {'version': 1, 'time': 1, 'map': 'chernarusplus', 'routes': [], 'layerStats': stats,
                'layers': {'camps': [{'id': 'c', 'x': 1, 'z': 2, 'label': 'l', 'detail': 'd'}]}}

    def test_layer_stats_are_validated_when_present(self):
        good = [{'layer': 'camps', 'total': 30, 'shown': 24, 'truncated': 1}]
        self.assertEqual(200, self.serve(self.base(good)))
        self.assertEqual(503, self.serve(self.base([{'layer': 'camps', 'total': 3, 'shown': 4, 'truncated': 0}])))
        self.assertEqual(503, self.serve(self.base([{'layer': 'camps', 'total': 3, 'shown': 3, 'truncated': 2}])))
        self.assertEqual(503, self.serve(self.base(good * 17)))

    def test_index_renders_stats_and_camps_legend(self):
        page = (ROOT / 'tools/webmap/index.html').read_text(encoding='utf-8')
        self.assertIn('layerStats', page)
        self.assertIn('truncated', page)
        self.assertIn("camps:", page)

    def test_legend_describes_lead_ledger_and_scenes_without_live_claims(self):
        page = (ROOT / 'tools/webmap/index.html').read_text(encoding='utf-8')
        self.assertIn("'lead-ledger':", page)
        self.assertIn("scenes:", page)
        self.assertIn('not an entity-presence claim', page)

    def test_legend_describes_the_w29_layers_without_live_claims(self):
        page = (ROOT / 'tools/webmap/index.html').read_text(encoding='utf-8')
        for name in ("pickers:", "'group-pins':", "'materializer-proposals':"):
            self.assertIn(name, page)
        self.assertIn('no player ids or names', page)
        self.assertIn('not a live-body claim', page)
        self.assertIn('unplaced', page)

    def test_unplaced_is_optional_and_validated_when_present(self):
        row = {'layer': 'lead-ledger', 'total': 3, 'shown': 3, 'truncated': 0}
        self.assertEqual(200, self.serve(self.base([dict(row, unplaced=2)])))
        self.assertEqual(200, self.serve(self.base([row])), 'older snapshots stay valid')
        self.assertEqual(503, self.serve(self.base([dict(row, unplaced=-1)])))
        self.assertEqual(503, self.serve(self.base([dict(row, unplaced='2')])))
        self.assertEqual(503, self.serve(self.base([dict(row, unplaced=1000001)])))

    def test_layer_stats_for_new_layers_validate(self):
        stats = [{'layer': 'lead-ledger', 'total': 64, 'shown': 56, 'truncated': 1},
                 {'layer': 'scenes', 'total': 2, 'shown': 2, 'truncated': 0}]
        self.assertEqual(200, self.serve(self.base(stats)))


if __name__ == '__main__':
    unittest.main()
