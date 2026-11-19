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

from tests.unit.test_admin_test_kit import compile_authored, base_scope
from tests.unit.test_group_server import EArray
from tests.unit.test_hc_operational_snapshot import NativeMap, bind

ROOT = Path(__file__).resolve().parents[2]
DEBUG_DIR = ROOT / 'mods/HollowCountry/scripts/4_World/Debug'
SNAPSHOT = DEBUG_DIR / 'HCDebugSnapshot.c'
MODULE = DEBUG_DIR / 'HCDebugSnapshotModule.c'
STORE = DEBUG_DIR / 'HCDebugJsonStore.c'
CONSTANTS = dict(MAX_POINTS=1024, MAX_CONTRIBUTOR_POINTS=64, DEBUG_LAYER_POINTS=88,
                 CAMP_LAYER_CAP=24, MAX_LAYER_STATS=16, LEAD_LAYER_CAP=56, SCENE_LAYER_CAP=8)
LEADS = ROOT / 'mods/HollowCountry/scripts/4_World/Leads/HCLeadModule.c'
SCENES = ROOT / 'mods/HollowCountry/scripts/4_World/Scenes/HCScenesModule.c'
WIRE = ROOT / 'mods/HollowCountry/scripts/4_World/Admin/HCAdminSnapshotWire.c'


def snapshot_double():
    """A capture whose Describe-window methods are the authored ones."""
    scope = base_scope(array=EArray, HCDebugSnapshot=N(**CONSTANTS), HCDebugPoint=lambda: N(),
                       HCDebugLayerStat=lambda: N(), Vector=lambda x, y, z: (x, y, z))
    document = N(layers=NativeMap(), layerStats=EArray(), routes=EArray())
    snap = N(m_Describing=True, m_Document=document, m_PointCount=0, m_LayerPoints=0,
             m_ContributorPoints=0, HCText=lambda value, limit: value[:limit])
    fields = ('m_Describing', 'm_Document', 'm_PointCount', 'm_LayerPoints', 'm_ContributorPoints')
    members = ('HCText', 'HCPositionValid', 'HCInsertPoint')
    bind(snap, SNAPSHOT, 'HCDebugSnapshot',
         ('HCPositionValid', 'HCInsertPoint', 'AddPoint', 'HCAddLayerPoint', 'HCNoteLayer', 'HCPointCount'),
         scope, fields=fields, members=members)
    return snap


class Recorder:
    def __init__(self, accept=True):
        self.points, self.notes, self.accept = [], [], accept

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
    def describe(self, leads, place=True):
        position = (3000.0, 0, 4000.0)
        scope = base_scope(HCLeadModule=N(Get=lambda: leads), HCDebugSnapshot=N(**CONSTANTS),
                           HCLeadPolicy=N(Place=lambda ident: N(Position=position, Name='Place ' + ident) if place else None))
        return compile_authored(SNAPSHOT, 'HCDebugLeadLedgerContributor', 'HCDescribe', scope, modded=False)

    def module(self, count):
        rows = [N(Id='lead-%d' % i, Kind='CACHE', TargetPlaceId='p%d' % i, Expires=9000 + i, GroupId='') for i in range(count)]
        return N(HCDebugLeadCount=lambda: len(rows), HCDebugLead=lambda i: rows[i] if i < len(rows) else None)

    def test_bounded_with_total_shown_stat_and_named_cap(self):
        recorder = Recorder()
        self.describe(self.module(64))(N(), recorder)
        self.assertEqual(56, len(recorder.points))
        self.assertEqual({'lead-ledger'}, {row[0] for row in recorder.points})
        self.assertEqual([('lead-ledger', 64, 56)], recorder.notes)

    def test_rows_are_place_level_and_never_expose_group_or_live_position(self):
        recorder = Recorder()
        self.describe(self.module(1))(N(), recorder)
        layer, ident, pos, label, detail = recorder.points[0]
        self.assertEqual(('lead-0', (3000.0, 0, 4000.0), 'Place p0'), (ident, pos, label))
        self.assertIn('kind=CACHE', detail)
        self.assertIn('expires=9000', detail)
        self.assertNotIn('solo', detail)

    def test_unknown_place_row_is_not_counted_as_shown(self):
        recorder = Recorder()
        self.describe(self.module(3), place=False)(N(), recorder)
        self.assertEqual([('lead-ledger', 3, 0)], recorder.notes)

    def test_module_off_emits_nothing(self):
        recorder = Recorder()
        self.describe(None)(N(), recorder)
        self.assertEqual(([], []), (recorder.points, recorder.notes))


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
    def lead_fn(self, name, store_rows, now=1000, healthy=True):
        copies = []

        def copy(row):
            clone = N(**vars(row))
            copies.append(clone)
            return clone
        scope = base_scope(HCWorldClock=N(UTC=lambda: now), HCLeadPolicy=N(Copy=copy), HC_DEBUG_LEAD_SCAN=64)
        receiver = N(m_Store=N(Data=N(Leads=EArray(store_rows))), Get=lambda: receiver if healthy else None)
        fn = compile_authored(LEADS, 'HCLeadModule', name, scope, ('Get',), modded=False)
        return receiver, fn

    def rows(self):
        return [N(Id='a', Kind='PLACE', TargetPlaceId='p', Expires=2000, GroupId='solo:secret', TextId='t', Source='x'),
                N(Id='old', Kind='PLACE', TargetPlaceId='p', Expires=500, GroupId='g', TextId='t', Source='x'),
                N(Id='b', Kind='DANGER', TargetPlaceId='q', Expires=3000, GroupId='g2', TextId='t', Source='x')]

    def test_lead_count_is_unexpired_rows_only(self):
        receiver, count = self.lead_fn('HCDebugLeadCount', self.rows())
        self.assertEqual(2, count(receiver))

    def test_lead_getter_returns_withheld_group_copy_and_does_not_mutate(self):
        source = self.rows()
        receiver, lead = self.lead_fn('HCDebugLead', source)
        first, second = lead(receiver, 0), lead(receiver, 1)
        self.assertEqual(('a', 'b'), (first.Id, second.Id))
        self.assertEqual('', first.GroupId)
        self.assertEqual('solo:secret', source[0].GroupId, 'the ledger row itself is untouched')
        self.assertIsNone(lead(receiver, 2))
        self.assertIsNone(lead(receiver, -1))

    def test_lead_getters_are_empty_when_module_unhealthy(self):
        receiver, count = self.lead_fn('HCDebugLeadCount', self.rows(), healthy=False)
        self.assertEqual(0, count(receiver))
        receiver, lead = self.lead_fn('HCDebugLead', self.rows(), healthy=False)
        self.assertIsNone(lead(receiver, 0))

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
        scope = base_scope(array=EArray, HCDebugSnapshot=N(HCText=lambda value, limit: value[:limit]),
                           HCOperationalContributors=N(HCAppend=lambda reply, rows, lost: None),
                           HCAdminReply=lambda: N(Lines=EArray(), Marks=EArray(), Notice=''),
                           HCAdminMark=lambda: N(), Vector=lambda x, y, z: (x, y, z),
                           Print=lambda line: None)
        wire = N()
        bind(wire, WIRE, 'HCAdminSnapshotWire', ('HCMark', 'HCSlot', 'HCAllocate', 'HCBuild'), scope,
             members=('HCMark', 'HCSlot', 'HCAllocate'))
        return wire

    def capture(self, layers, routes=(), stats=()):
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

    def test_more_than_sixteen_layers_reports_unsent_layers_and_stays_at_caps(self):
        reply = self.wire().HCBuild(self.capture([('l%02d' % i, 40) for i in range(20)]), 1)
        self.assertEqual(16, len(self.per_layer(reply)))
        self.assertLessEqual(len(reply.Marks), 512)
        self.assertIn('layers_unsent=4', reply.Notice)
        self.assertLessEqual(len(reply.Notice.encode('utf-8')), 1024)

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
        self.assertEqual(1024 - 88, snap.m_PointCount, 'ai-units and friends are not squeezed below their pool')
        for index in range(200):
            snap.m_ContributorPoints = 0
            snap.HCAddLayerPoint('camps', 'c%d' % index, (10.0, 0, 20.0), 'c', 'd')
        self.assertEqual(88, snap.m_LayerPoints)
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

    def test_layer_stats_for_new_layers_validate(self):
        stats = [{'layer': 'lead-ledger', 'total': 64, 'shown': 56, 'truncated': 1},
                 {'layer': 'scenes', 'total': 2, 'shown': 2, 'truncated': 0}]
        self.assertEqual(200, self.serve(self.base(stats)))


if __name__ == '__main__':
    unittest.main()
