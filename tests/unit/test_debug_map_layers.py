"""w27-debugmap: bounded Camps layer, per-layer count/truncated stats, own point share.

Synthetic restricted-port fixtures execute the authored Enforce bodies; nothing
here observes DayZ. Leads and Scenes layers are deliberately NOT authored: the
modules expose no read-only enumeration (see docs/DEBUG_MAP.md). runtime=PENDING.

TDD receipt (same command for RED and GREEN):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_debug_map_layers -v
"""
import io
import json
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
CONSTANTS = dict(MAX_POINTS=1024, MAX_CONTRIBUTOR_POINTS=64, DEBUG_LAYER_POINTS=88,
                 CAMP_LAYER_CAP=24, MAX_LAYER_STATS=16)


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


def camps_describe(holdouts, inherited):
    scope = base_scope(HCHoldouts=N(Get=lambda: holdouts), HCDebugSnapshot=N(**CONSTANTS),
                       super=N(HCDescribe=lambda snapshot: inherited.append(snapshot)))
    return compile_authored(SNAPSHOT, 'HCDebugCampSitesContributor', 'HCDescribe', scope, modded=False)


class CampsLayer(unittest.TestCase):
    def holdouts(self, count):
        rows = [N(Id='holdout-%d' % i, PlaceId='place-%d' % i, HousePos=(100.0 + i, 0, 200.0), State='OCCUPIED',
                  Routine='SECRET_ROUTINE', Occupants=3) for i in range(count)]
        return N(Count=lambda: len(rows), Snapshot=lambda i: rows[i] if i < len(rows) else None)

    def test_bounded_to_named_cap_with_count_and_truncated_stat(self):
        inherited, recorder = [], Recorder()
        camps_describe(self.holdouts(30), inherited)(N(), recorder)
        self.assertEqual([recorder], inherited, 'existing holdouts rows must still be described by the base')
        self.assertEqual(24, len(recorder.points))
        self.assertEqual({'camps'}, {row[0] for row in recorder.points})
        self.assertEqual([('camps', 30, 24)], recorder.notes)

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


if __name__ == '__main__':
    unittest.main()
