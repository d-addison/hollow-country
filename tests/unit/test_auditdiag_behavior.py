"""Scope K: execute authored bodies with explicit synthetic native/storage ports.
These fixtures never establish native permissions, durability, or DayZ behavior.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.unit import test_debug_map_layers as wire_fixture
from tests.unit import test_hc48_habitat_boot as habitat_fixture
from tests.unit.test_admin_test_kit import compile_authored, base_scope
from tests.unit.test_group_server import EArray
from tests.unit.test_hc_scavenge import bind
from tests.unit.test_map_layers import EStr

ROOT = Path(__file__).resolve().parents[2]
W = ROOT / 'mods/HollowCountry/scripts/4_World'
ADMIN = W / 'Admin/HCAdminModule.c'


class Notice(unittest.TestCase):
    def test_tiny_room_retains_identifiable_first_entry_and_counts_others(self):
        wire = wire_fixture.WireFairness().wire()
        result = wire.HCFitEntries(EArray([EStr('players:120/900'), EStr('camps:0/40')]), 12)
        self.assertEqual('pla~,+1 more', result)

    def test_every_tiny_room_is_bounded_and_never_only_an_omission_count(self):
        wire = wire_fixture.WireFairness().wire()
        entries = EArray([EStr('players:120/900'), EStr('camps:0/40')])
        for room in range(15):
            value = wire.HCFitEntries(entries, room)
            self.assertLessEqual(len(value), room, (room, value))
            if room:
                self.assertTrue(value.startswith('p'), (room, value))
        self.assertEqual('', wire.HCFitEntries(EArray(), 0))


class Journal(unittest.TestCase):
    def fixture(self, phase='complete', save=True, ready=True):
        row = N(Phase=EStr(phase), Refusal=EStr('old_terminal_reason'))
        logs, publications, saved = [], [], []
        status = N(HCState=lambda: 'ready', HCPublish=lambda *args: publications.append(args))
        trade = N(m_State=row, m_Ready=ready, m_Store=N(Save=lambda idle: saved.append(idle) or save),
                  m_LogRefusal='TRADE_JOURNAL_UNCERTAIN', m_Reports=0, m_Released=0, m_Status=status)
        env = dict(HCTradeState=lambda: N(Phase='idle', Refusal=''), Print=logs.append)
        source = (W / 'World/HCAITrade.c').read_text()
        bind(source, 'HCTradeTransaction', trade, ('HCTerminal', 'HCReleaseSlot'), env)
        trade.HCValidState = lambda idle: idle.Phase == 'idle'
        trade.HCLog = lambda: logs.append(trade.m_LogRefusal)
        return trade, saved, logs, publications

    def test_durable_healthy_idle_replacement_clears_log_refusal_before_log(self):
        trade, saved, logs, _ = self.fixture()
        self.assertTrue(trade.HCReleaseSlot())
        self.assertEqual(1, len(saved))
        self.assertEqual('', trade.m_LogRefusal)
        self.assertEqual('', logs[0])

    def test_failure_and_quarantine_do_not_clear_evidence_or_retry(self):
        for phase, save, ready in [('complete', False, True), ('complete', True, False),
                                   ('quarantined', True, True)]:
            trade, saved, _, _ = self.fixture(phase, save, ready)
            trade.HCReleaseSlot()
            self.assertEqual('TRADE_JOURNAL_UNCERTAIN', trade.m_LogRefusal)
            self.assertEqual(phase, trade.m_State.Phase)
            writes = len(saved)
            trade.HCReleaseSlot()
            self.assertEqual(writes, len(saved), 'uncertain journal must never retry itself healthy')


class CapsAndUnits(unittest.TestCase):
    def test_all_remaining_one_mib_limits_use_the_shared_qualified_constant(self):
        for path, count in [(W / 'Core/HCPersistenceDisposition.c', 3),
                            (W / 'Atmosphere/HCCellarsModule.c', 1)]:
            source = path.read_text()
            self.assertNotIn('1048576', source)
            self.assertEqual(count, source.count('HCGroupIO.HC_RAW_READ_CAP'))

    def test_manifest_diagnostic_names_characters_without_claiming_byte_size(self):
        fixture = habitat_fixture.HabitatReceiptLine()
        fixture.setUp()
        fixture.fresh(fixture.synthetic() + '  /* synthetic non-ASCII: é */')
        fixture.call('ready')
        self.assertIn('manifest_chars=', fixture.logs[0])
        self.assertNotIn('manifest_bytes=', fixture.logs[0])
        self.assertIn('runtime=PENDING', fixture.logs[0])


class PermissionLifecycle(unittest.TestCase):
    def fixture(self):
        server, disabled = [True], [False]
        logs, verdicts = [], []
        adapter = N(m_Running=False, m_Enabled=False, m_Port=None, m_Reason='',
                    m_Status=N(HCPublish=lambda *args: verdicts.append(args)))
        scope = base_scope(GetGame=lambda: N(IsServer=lambda: server[0]),
                           FileExist=lambda path: disabled[0], Print=logs.append,
                           HCV2Admission=N(Line=lambda *args: 'admission'),
                           HCAdminPermissionAdapter=N(PERMISSION='HollowCountry.Admin'))
        names = ('HCDefaultPort', 'HCStart', 'HCStop', 'HCBind', 'HCUnbind', 'HCAllowed', 'HCRefresh', 'HCRefuse')
        for name in names:
            method = compile_authored(ADMIN, 'HCAdminPermissionAdapter', name, scope,
                                      names, modded=False, native_strings=EStr)
            setattr(adapter, name, lambda *args, fn=method: fn(adapter, *args))
        return adapter, server, disabled, logs, verdicts

    def test_default_on_missing_binding_fails_closed_with_one_named_receipt(self):
        adapter, _, _, logs, verdicts = self.fixture()
        adapter.HCStart()
        adapter.HCRefresh()
        self.assertFalse(adapter.HCAllowed(N()))
        self.assertEqual(('degraded', 'cot_permission_binding_missing'), verdicts[-1])
        self.assertEqual(1, sum('cot_permission_binding_missing' in line for line in logs))
        self.assertTrue(all('runtime=PENDING' in line for line in logs))

    def test_live_revocation_opt_out_unbind_stop_and_client_fail_closed(self):
        adapter, server, disabled, _, verdicts = self.fixture()
        allowed, ready = [True], [True]
        calls = []
        peer = N()
        port = N(HCReady=lambda: ready[0], HCAllowed=lambda sender, permission:
                 calls.append((sender, permission)) or allowed[0])
        adapter.HCStart()
        self.assertTrue(adapter.HCBind(port))
        self.assertTrue(adapter.HCAllowed(peer))
        self.assertEqual([(peer, 'HollowCountry.Admin')], calls)
        allowed[0] = False
        self.assertFalse(adapter.HCAllowed(peer), 'never cache a grant')
        allowed[0], ready[0] = True, False
        self.assertFalse(adapter.HCAllowed(peer))
        adapter.HCRefresh()
        self.assertEqual(('degraded', 'cot_permission_provider_unavailable'), verdicts[-1])
        ready[0] = True
        adapter.HCUnbind(N())
        self.assertTrue(adapter.HCAllowed(peer), 'foreign unbind cannot remove the owner')
        adapter.HCUnbind(port)
        self.assertFalse(adapter.HCAllowed(peer))
        adapter.HCBind(port)
        adapter.HCStop()
        self.assertFalse(adapter.HCAllowed(peer))
        self.assertIsNone(adapter.m_Port)
        disabled[0] = True
        adapter.HCStart()
        self.assertFalse(adapter.HCBind(port))
        self.assertEqual(('off', 'operator_opt_out'), verdicts[-1])
        disabled[0], server[0] = False, False
        adapter.HCStart()
        self.assertFalse(adapter.HCBind(port))
        self.assertFalse(adapter.HCAllowed(peer))

    def test_lost_server_authority_cannot_keep_a_ready_receipt_or_a_binding(self):
        adapter, server, _, _, verdicts = self.fixture()
        adapter.HCStart()
        port = N(HCReady=lambda: True, HCAllowed=lambda *args: True)
        self.assertTrue(adapter.HCBind(port))
        server[0] = False
        adapter.HCRefresh()
        self.assertEqual(('off', 'server_stopped'), verdicts[-1])
        self.assertIsNone(adapter.m_Port)

    def test_authored_authorization_and_delayed_send_recheck_live_permission(self):
        allowed, server, sends = [True], [True], []
        peer = N(GetPlainId=lambda: 'synthetic-cot')
        local = N(GetPlainId=lambda: 'synthetic-local')
        owner = N(m_Running=True, m_Admins=N(PlainIds=EArray(['synthetic-local'])),
                  m_Permissions=N(HCAllowed=lambda sender: allowed[0]))
        scope = base_scope(GetGame=lambda: N(IsServer=lambda: server[0]),
                           HCAdminWire=N(REPLY=77), ScriptRPC=lambda: N(
                               Write=lambda row: sends.append(row), Send=lambda *args: None))
        auth = compile_authored(ADMIN, 'HCAdminModule', 'HCAuthorized', scope, modded=False)
        owner.HCAuthorized = lambda sender: auth(owner, sender)
        send = compile_authored(ADMIN, 'HCAdminModule', 'HCSend', scope,
                                ('HCAuthorized',), modded=False)
        reply = N(Authorized=False)
        send(owner, peer, reply)
        self.assertTrue(reply.Authorized)
        self.assertEqual(1, len(sends))
        allowed[0] = False
        self.assertFalse(owner.HCAuthorized(peer))
        send(owner, peer, N(Authorized=False))
        self.assertEqual(1, len(sends), 'revoked delayed snapshot must not leave server')
        self.assertTrue(owner.HCAuthorized(local), 'independent allowlist still works')
        server[0] = False
        self.assertFalse(owner.HCAuthorized(local))
        owner.m_Running, server[0] = False, True
        self.assertFalse(owner.HCAuthorized(local))

    def test_cot_peer_uses_bounded_existing_ingress_slots_without_allowlist_mutation(self):
        peers = [N(GetPlainId=lambda i=i: EStr('synthetic-%d' % i)) for i in range(33)]
        owner = N(m_Identities=EArray([None] * 32), HCAuthorized=lambda sender: sender in peers)
        method = compile_authored(ADMIN, 'HCAdminModule', 'HCAuthSlot', base_scope(),
                                  ('HCAuthorized',), modded=False, native_strings=EStr)
        for i in range(32):
            slot = method(owner, peers[i])
            self.assertEqual(i, slot)
            owner.m_Identities[slot] = peers[i]
        self.assertEqual(-1, method(owner, peers[32]))
        owner.HCAuthorized = lambda sender: sender in peers[1:]
        self.assertEqual(0, method(owner, peers[32]), 'revoked peer frees only its bounded slot')


if __name__ == '__main__':
    unittest.main()
