"""Group discovery/expiry batching on explicit synthetic fixtures.

Counts Clone/Commit/serialise calls of the authored bodies. It never measures
DayZ tick time or establishes native persistence behaviour.
"""
import copy
import unittest
from types import SimpleNamespace as N

from tests.legacy import test_group_round2 as round2
from tests.legacy import test_group_rpc as group_rpc
from tests.legacy.test_group_persistence import StoreHarness
from tests.legacy.test_group_server import EArray

run = round2.run


class GroupBatchingService(unittest.TestCase):
    peer = round2.ServiceRound2.peer
    discover = round2.ServiceRound2.discover

    def setUp(self):
        round2.ServiceRound2.setUp(self)
        self.s.m_PendingVisits = EArray()
        self.s.m_BatchTime = 0.
        self.e['HCGroupPendingVisit'] = lambda: N(ExplorerId='', Place=None, Actual=[0., 0., 0.])
        self.e['this'] = self.s
        self.s.s_Instance = None

        def commit(candidate):
            self.writes.append(candidate)
            self.s.m_State = candidate
            return 0
        self.s.Commit = commit
        for name in ('FlushBatch', 'Disconnected'):
            setattr(self.s, name, lambda *args, name=name: run('HCGroupService', name, self.s, self.e, *args))

    def tick(self, seconds):
        self.now += seconds
        run('HCGroupService', 'Tick', self.s, self.e, seconds)

    def test_discovery_queues_visits_without_clone_or_commit(self):
        self.discover()
        self.assertEqual([], self.clones)
        self.assertEqual([], self.writes)
        self.assertEqual(['0', '1', '2', '3', '4', '5'], [v.ExplorerId for v in self.s.m_PendingVisits])

    def test_discovery_never_queues_the_same_visit_twice(self):
        self.discover()
        self.discover()
        queued = [v.ExplorerId for v in self.s.m_PendingVisits]
        self.assertEqual(8, len(queued))
        self.assertEqual(sorted(set(queued)), sorted(queued))

    def test_tick_commits_discovery_at_most_once_per_sixty_seconds(self):
        self.cfg.DiscoveryIntervalSeconds = 5
        for _ in range(11):
            self.tick(5.)
        self.assertEqual([], self.clones)
        self.assertEqual([], self.writes)
        self.tick(5.)
        self.assertEqual(1, len(self.writes))
        self.assertEqual(8, len(self.writes[0].Explorers))
        self.assertEqual([], self.s.m_PendingVisits)
        self.assertEqual(1, len(self.broadcasts))
        for _ in range(11):
            self.tick(5.)
        self.assertEqual(1, len(self.writes))

    def test_marker_expiry_waits_for_the_batch_and_touches_once(self):
        self.cfg.DiscoveryLayer = False
        marker = self.e['HCGroupMarker']()
        marker.ExpiresUtc = 900
        group = self.e['HCGroupRecord']()
        group.Members = EArray(['0'])
        group.Markers = EArray([marker])
        group.Revision = 4
        self.s.m_State.Groups = EArray([group])
        self.tick(2.)
        self.assertEqual([], self.clones)
        self.assertEqual([], self.writes)
        for _ in range(29):
            self.tick(2.)
        self.assertEqual(1, len(self.writes))
        self.assertEqual([], list(self.writes[0].Groups[0].Markers))
        self.assertEqual(5, self.writes[0].Groups[0].Revision)
        self.assertEqual(1, len(self.broadcasts))

    def test_idle_batch_window_writes_nothing(self):
        self.cfg.DiscoveryLayer = False
        for _ in range(31):
            self.tick(2.)
        self.assertEqual([], self.clones)
        self.assertEqual([], self.writes)

    def test_disconnect_flushes_pending_discovery_once(self):
        self.discover()
        self.assertEqual([], self.writes)
        identity = N(GetId=lambda: '0')
        leaving = self.peers[0]
        leaving.Identity = identity
        run('HCGroupService', 'Disconnected', self.s, self.e, identity)
        self.assertEqual(1, len(self.writes))
        self.assertEqual(6, len(self.writes[0].Explorers))
        self.assertEqual([], self.s.m_PendingVisits)
        self.assertNotIn(leaving, self.peers)

    def test_stop_flushes_pending_discovery_before_teardown(self):
        self.discover()
        self.assertEqual([], self.writes)
        run('HCGroupService', 'Stop', self.s, self.e)
        self.assertEqual(1, len(self.writes))
        self.assertEqual(6, len(self.writes[0].Explorers))
        self.assertFalse(self.s.m_Healthy)

    def test_stop_without_pending_discovery_writes_nothing(self):
        run('HCGroupService', 'Stop', self.s, self.e)
        self.assertEqual([], self.clones)
        self.assertEqual([], self.writes)

    def test_flush_limit_backs_off_discovery_sixty_seconds(self):
        self.s.Commit = lambda c: self.writes.append(c) or self.e['HCGroupCode'].LIMIT
        self.discover()
        self.assertEqual(self.e['HCGroupCode'].LIMIT, self.s.FlushBatch())
        self.discover()
        self.assertEqual([], self.s.m_PendingVisits)
        self.now += 60
        self.discover()
        self.assertEqual(6, len(self.s.m_PendingVisits))


class GroupBatchingRpc(unittest.TestCase):
    setUp = group_rpc.GroupRpcTests.setUp
    request = group_rpc.GroupRpcTests.request
    dispatch = group_rpc.GroupRpcTests.dispatch

    def test_expired_marker_never_blocks_a_new_marker_before_the_flush(self):
        op = self.e['HCGroupOp']
        self.dispatch(self.request(op.CREATE, 1))
        self.assertEqual(0, self.sent[-1][0].Code)
        group = self.service.m_State.Groups[0]
        for index in range(self.cfg.MaxMarkers):
            marker = self.e['HCGroupMarker']()
            marker.Id = 100 + index
            marker.CreatorId = 'alice'
            marker.Name = 'Synthetic'
            marker.Position = [10., 0., 10.]
            marker.ExpiresUtc = self.now + 600
            group.Markers.Insert(marker)
        group.Markers[0].ExpiresUtc = self.now - 1
        self.service.m_State.NextId = 100 + self.cfg.MaxMarkers
        writes = len(self.h.writes)
        self.dispatch(self.request(op.MARKER_CREATE, 2, ExpectedRevision=group.Revision,
                                   Position=[20., 0., 20.], TtlSeconds=60))
        self.assertEqual(0, self.sent[-1][0].Code)
        self.assertGreater(len(self.h.writes), writes)
        live = self.service.m_State.Groups[0].Markers
        self.assertEqual(self.cfg.MaxMarkers, len(live))
        self.assertTrue(all(m.ExpiresUtc > self.now for m in live))


class GroupStoreSerialisation(unittest.TestCase):
    def test_save_serialises_once_and_keeps_live_invitations(self):
        h = StoreHarness()
        e = h.rules
        cfg = e['HCGroupSettings']()
        store = h.store(cfg)
        ok, state = store.Open(cfg, None)
        self.assertTrue(ok)
        q = e['HCGroupRequest']()
        q.Op = e['HCGroupOp'].CREATE
        q.Name = 'Synthetic'
        self.assertEqual(0, e['Apply'](state, cfg, q, 'alice', 2000000001))
        q.Op = e['HCGroupOp'].INVITE
        q.TargetId = 'bob'
        q.ExpectedRevision = 1
        self.assertEqual(0, e['Apply'](state, cfg, q, 'alice', 2000000001))
        state.LastMutationUtc = 2000000001
        state.Revision += 1
        calls = []
        encode, decode = h.env['encode'], h.env['decode']
        h.env['encode'] = lambda value: calls.append('encode') or encode(value)
        h.env['decode'] = lambda text, kind: calls.append('decode') or decode(text, kind)
        self.assertTrue(store.Save(state))
        self.assertEqual(['encode'], calls)
        self.assertEqual(1, len(state.Invitations))
        h.env['encode'], h.env['decode'] = encode, decode
        ok, loaded = h.store(cfg).Open(cfg, None)
        self.assertTrue(ok)
        self.assertEqual([], loaded.Invitations)
        self.assertEqual(['alice'], loaded.Groups[0].Members)


if __name__ == '__main__':
    unittest.main()
