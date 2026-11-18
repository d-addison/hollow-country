"""#23 malformed requests, one synthetic authenticated client per handler.

Raw JSON frames here are EXPLICIT synthetic ParamsReadContext fixtures, not
DayZ's wire format. Bad native types/truncation are modelled as Read failure;
oversized typed fields execute the actual handler's validation. Replay checks
domain state, writes and receipts, allowing bounded admission accounting/replies.
Native allocation limits, trailing wire bytes and decoding remain runtime gaps.

TDD record (2026-11-17): the unmarked null-context regression failed with
"NoneType ... Read" at authored HCGroupService.c:298 (14-test focused run).
Product code is unchanged; the retained expected failure records that defect.
Green: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_v1_combined_rpc
"""
import copy
import json
import re
from types import SimpleNamespace as N
import unittest

from tests.unit import test_event_transport as events
from tests.unit import test_group_rpc as groups
from tests.unit import test_event_runtime as runtime
from tests.unit.test_group_server import body, execute_member

ROOT = events.ROOT


class SyntheticContext:
    """Synthetic typed-native read result; never a replacement RPC validator."""
    def __init__(self, frame, prototype):
        self.frame, self.prototype = frame, prototype
        self.reads = 0

    def Read(self):
        self.reads += 1
        try:
            fields = json.loads(self.frame)
            expected = vars(self.prototype)
            if not isinstance(fields, dict) or set(fields) != set(expected): return None
            if any(type(fields[k]) is not type(v) for k, v in expected.items()): return None
            result = copy.deepcopy(self.prototype)
            vars(result).update(fields)
            return result
        except (ValueError, TypeError):
            return None


def group_dispatch(h, request=None, sender='authenticated', context='typed'):
    """Existing group RPC adapter, with sender/context native inputs exposed."""
    match = re.search(r'void OnRPC\(([^)]*)\)\s*\{', h.source)
    text = body(h.source, match.end())
    text = text.replace('ctx.Read(request)', '((request := ctx.Read()) != null)')
    text = re.sub(r'JsonFileLoader<HCGroupRequest>.MakeData\(request, payload, error\)',
                  '((payload := encode(request)) != null)', text)
    text = text.replace('Clone(candidate)', '((candidate := self.Clone()) != null)')
    for name in ('Connected', 'Admit', 'Reply', 'Stop', 'Commit', 'Broadcast'):
        text = re.sub(r'(?<![\w.])' + name + r'\(', 'self.' + name + '(', text)
    return execute_member('void OnRPC(' + match[1] + ') {' + text + '}', 'OnRPC',
        h.e, h.service, h.identity if sender == 'authenticated' else sender, None,
        h.e['HCGroupProtocol'].RPC_REQUEST,
        N(Read=lambda: request) if context == 'typed' else context)


class RpcFixture:
    def __init__(self, kind):
        self.kind, self.logs = kind, []
        if kind == 'events':
            self.h = events.EventTransportTests(); self.h.setUp()
            self.h.e['Print'] = self.logs.append
            self.h.handshake()
        else:
            self.h = groups.GroupRpcTests(); self.h.setUp()
            self.h.e['Print'] = self.logs.append
        self.prototype = self.request()

    def request(self):
        if self.kind == 'events':
            return self.h.request(1, 1, 1, self.h.rpc.m_Peers[0].Session, 0)
        return self.h.request(self.h.e['HCGroupOp'].CREATE)

    def state(self):
        if self.kind == 'events':
            return copy.deepcopy(self.h.runtime.m_State), self.h.helper.store.calls
        return copy.deepcopy(self.h.service.m_State), list(self.h.h.writes)

    def send(self, context, sender='authenticated'):
        if self.kind == 'events':
            self.h.now += 2
            return self.h.rpc.OnRPC(self.h.sender if sender == 'authenticated' else sender,
                                   None, 4853801, context)
        return group_dispatch(self.h, sender=sender, context=context)

    def typed(self, request): return N(Read=lambda: request)


class CombinedRpcTests(unittest.TestCase):
    # HARDENING GAP (reviewed: engine always passes a non-null ctx; optional guard) mods/HollowCountry/scripts/4_World/Groups/HCGroupService.c:298:
    # authenticated live sender, correct RPC_REQUEST, target=null, ctx=null.
    @unittest.expectedFailure
    def test_groups_null_context(self):
        null_context_case('groups')(self)

    def test_handler_inventory_includes_only_two_mod_server_requests_and_native_sync(self):
        # Pin the inventory so a new handler cannot silently escape this matrix.
        found = set()
        for path in ROOT.rglob('*.c'):
            if re.search(r'\b(?:override )?void OnRPC\(', path.read_text()):
                found.add(str(path.relative_to(ROOT)))
        self.assertEqual({
            '4_World/Groups/HCGroupService.c', '4_World/Events/HCEventRPC.c',
            '5_Mission/Groups/HCGroupClient.c', '5_Mission/Events/HCEventClient.c',
            # V2 Morse is server-to-holder only; it accepts no server request.
            '5_Mission/Leads/HCMorseClient.c',
            '3_Game/Survival/HCStaminaConfiguration.c',
            # Search prompt sites: the server answers class geometry only, rate-limited per sender.
            '4_World/Interiors/HCSearchPreviewSites.c'}, found)

    def test_native_gameplay_sync_server_path_never_reads_any_payload(self):
        calls = []
        class Base:
            def IsServer(self): return True
            def OnRPC(self, *args): calls.append(args)
        env = dict(base=N(OnRPC=lambda *args: calls.append(args)),
                ERPCs=N(RPC_CFG_GAMEPLAY_SYNC=99),
                HCStaminaConfiguration=N(ClientActive=lambda: True),
                CfgGameplayHandler=N(m_Data='synthetic-state'))
        source = (ROOT / '3_Game/Survival/HCStaminaConfiguration.c').read_text()
        source = source[source.index('modded class DayZGame'):]
        source = source.replace('super.OnRPC(', 'base.OnRPC(').replace(
            'IsServer()', 'self.IsServer()').replace('CfgGameplayJson previous', 'HCEventNative previous')
        receive = runtime.translate(source, 'OnRPC', env, None, True)
        game = Base()
        for ctx in (None, N(Read=lambda: self.fail('server must not deserialize'))):
            for sender in (None, object()):
                receive(game, sender, None, 99, ctx)
        self.assertEqual([], calls)
        self.assertEqual('synthetic-state', env['CfgGameplayHandler'].m_Data)


def rejection_case(kind, mode):
    def test(self):
        f = RpcFixture(kind)
        before = f.state()
        q = f.request()
        encoded = json.dumps(vars(q))
        if mode == 'truncated': ctx = SyntheticContext(encoded[:len(encoded)//2], q)
        elif mode == 'wrong_types':
            fields = vars(copy.deepcopy(q)); fields['RequestId'] = '1'
            ctx = SyntheticContext(json.dumps(fields), q)
        elif mode == 'oversized':
            q.Session = 'x' * 4097
            ctx = f.typed(q)
        elif mode == 'unauthenticated':
            ctx = N(Read=lambda: self.fail('unauthenticated request read'))
        else: raise AssertionError(mode)
        # Flood rejection too: logs/replies must remain bounded per input.
        for _ in range(64):
            f.send(ctx, None if mode == 'unauthenticated' else 'authenticated')
        self.assertEqual(before, f.state())
        self.assertLessEqual(len(f.logs), 64)
        self.assertLessEqual(sum(map(len, f.logs)), 64 * 1024)
        self.assertLessEqual(len(f.h.sent), 65)
    return test


def replay_case(kind):
    def test(self):
        f = RpcFixture(kind)
        q = f.request()
        f.send(f.typed(q))
        after = f.state()
        for _ in range(64): f.send(f.typed(q))
        self.assertEqual(after, f.state())
        # Same nonce with changed intent also cannot mutate or write.
        changed = copy.deepcopy(q)
        if kind == 'events': changed.Op = 2
        else: changed.Name = 'Different synthetic name'
        f.send(f.typed(changed))
        self.assertEqual(after, f.state())
        self.assertLessEqual(len(f.logs), 65)
    return test


def null_context_case(kind):
    def test(self):
        f = RpcFixture(kind)
        before = f.state()
        try:
            f.send(None)
        except AttributeError as exc:
            self.fail('authored handler dereferenced absent ParamsReadContext: ' + str(exc))
        self.assertEqual(before, f.state())
    return test


for _kind in ('events', 'groups'):
    for _mode in ('truncated', 'oversized', 'wrong_types', 'unauthenticated'):
        setattr(CombinedRpcTests, 'test_' + _kind + '_' + _mode, rejection_case(_kind, _mode))
    setattr(CombinedRpcTests, 'test_' + _kind + '_replayed_nonce', replay_case(_kind))
    if _kind == 'events':
        setattr(CombinedRpcTests, 'test_events_null_context', null_context_case(_kind))


if __name__ == '__main__': unittest.main()
