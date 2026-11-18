"""Synthetic authenticated null-context refusal; native networking is pending.

2026-11-18 RED, decorator removed before source edits:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_v1_combined_rpc.CombinedRpcTests.test_groups_null_context -v
Ran 1 test; FAILED (failures=1).
AssertionError: authored handler dereferenced absent ParamsReadContext: 'NoneType' object has no attribute 'Read'
GREEN (21 tests, OK):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_memory_clock tests.unit.test_group_null_context tests.unit.test_v1_combined_rpc -v
"""
import unittest

from tests.unit.test_v1_combined_rpc import RpcFixture


class GroupNullContextTests(unittest.TestCase):
    def test_null_context_returns_one_invalid_refusal_without_mutating_state(self):
        f = RpcFixture('groups')
        before = f.state()
        peer_before = (f.h.peer.LastRequest, f.h.peer.LastPayload, f.h.peer.LastReply)
        for count in range(1, 65):
            f.send(None)
            self.assertTrue(f.h.service.m_Healthy)
            self.assertEqual(before, f.state())
            self.assertEqual(peer_before, (f.h.peer.LastRequest, f.h.peer.LastPayload,
                                          f.h.peer.LastReply))
            self.assertEqual(count, len(f.h.sent))
            self.assertEqual(f.h.e['HCGroupCode'].INVALID, f.h.sent[-1][0].Code)
            self.assertEqual(0, f.h.sent[-1][0].RequestId)
        self.assertEqual([], f.logs)


if __name__ == '__main__':
    unittest.main()
