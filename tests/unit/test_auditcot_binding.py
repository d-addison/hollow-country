"""Authored COT binding policy; all native/vendor services below are synthetic.
Offline execution is not evidence of COT or DayZ runtime behavior.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.unit.test_admin_test_kit import compile_authored, base_scope, authored_method
from tests.unit import test_auditdiag_behavior as adapter_fixture

ROOT = Path(__file__).resolve().parents[2]
ADMIN = ROOT / 'mods/HollowCountry/scripts/4_World/Admin/HCAdminModule.c'
COT = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXCotPermissions.c'


class CotBinding(unittest.TestCase):
    def fixture(self):
        self.assertTrue(COT.is_file(), 'COT permission provider is missing')
        server, live, allowed = [True], [True], [True]
        lookups, checks = [], []
        player = N(HasPermission=lambda permission: checks.append(permission) or allowed[0])
        players = {'synthetic-guid': player}
        manager = N(HCXCotReady=lambda: live[0], GetPlayer=lambda guid:
                    lookups.append(guid) or players.get(guid))
        scope = base_scope(GetGame=lambda: N(IsServer=lambda: server[0]),
                           GetPermissionsManager=lambda: manager,
                           HCAdminPermissionAdapter=N(PERMISSION='HollowCountry.Admin'))
        port = N()
        for name in ('HCReady', 'HCAllowed'):
            fn = compile_authored(COT, 'HCXCotPermissionPort', name, scope,
                                  ('HCReady',), modded=False)
            setattr(port, name, lambda *args, fn=fn: fn(port, *args))
        return port, server, live, allowed, players, lookups, checks

    def test_live_named_permission_and_revocation_never_cache_grants(self):
        port, _, _, allowed, _, lookups, checks = self.fixture()
        peer = N(GetId=lambda: 'synthetic-guid')
        self.assertTrue(port.HCAllowed(peer, 'HollowCountry.Admin'))
        allowed[0] = False
        self.assertFalse(port.HCAllowed(peer, 'HollowCountry.Admin'))
        self.assertEqual(['synthetic-guid'] * 2, lookups)
        self.assertEqual(['HollowCountry.Admin'] * 2, checks)

    def test_unknown_sender_provider_loss_wrong_permission_and_client_deny(self):
        port, server, live, _, players, _, checks = self.fixture()
        peer = N(GetId=lambda: 'synthetic-guid')
        self.assertFalse(port.HCAllowed(None, 'HollowCountry.Admin'))
        self.assertFalse(port.HCAllowed(peer, 'Other.Permission'))
        live[0] = False
        self.assertFalse(port.HCAllowed(peer, 'HollowCountry.Admin'))
        live[0], server[0] = True, False
        self.assertFalse(port.HCAllowed(peer, 'HollowCountry.Admin'))
        server[0] = True
        players.clear()
        self.assertFalse(port.HCAllowed(peer, 'HollowCountry.Admin'))
        self.assertEqual([], checks)

    def test_factory_is_used_at_start_and_cleared_at_stop(self):
        adapter, _, _, _, verdicts = adapter_fixture.PermissionLifecycle().fixture()
        port = N(HCReady=lambda: True, HCAllowed=lambda *args: True)
        adapter.HCDefaultPort = lambda: port
        adapter.HCStart()
        self.assertIs(adapter.m_Port, port)
        self.assertEqual(('ready', 'server_permission_provider_bound_runtime_pending'), verdicts[-1])
        adapter.HCStop()
        self.assertIsNone(adapter.m_Port)

    def test_attached_provider_recovers_after_mission_load_and_opt_out_skips_factory(self):
        adapter, _, disabled, _, verdicts = adapter_fixture.PermissionLifecycle().fixture()
        live, factories = [False], []
        port = N(HCReady=lambda: live[0], HCAllowed=lambda *args: True)
        adapter.HCDefaultPort = lambda: factories.append(True) or port
        adapter.HCStart()
        self.assertFalse(adapter.HCAllowed(N()))
        self.assertEqual(('degraded', 'cot_permission_provider_unavailable'), verdicts[-1])
        live[0] = True
        adapter.HCRefresh()
        self.assertTrue(adapter.HCAllowed(N()))
        self.assertEqual(('ready', 'server_permission_provider_bound_runtime_pending'), verdicts[-1])
        adapter.HCStop()
        disabled[0] = True
        adapter.HCStart()
        self.assertEqual([True], factories)
        self.assertIsNone(adapter.m_Port)

    def test_registration_precedes_mission_and_readiness_uses_actual_service_fields(self):
        self.assertTrue(COT.is_file(), 'COT permission provider is missing')
        registered = []
        owner = N(m_HCXCotRegistered=False, m_MissionLoaded=False,
                  RootPermission=N(), Players=N(), Roles=N(),
                  RegisterPermission=registered.append)
        scope = base_scope(HCAdminPermissionAdapter=N(PERMISSION='HollowCountry.Admin'))
        register = compile_authored(COT, 'JMPermissionManager', 'JMPermissionManager', scope,
                                    ('RegisterPermission',), fields=('RootPermission',))
        ready = compile_authored(COT, 'JMPermissionManager', 'HCXCotReady', scope,
                                 fields=('RootPermission', 'Players', 'Roles'))
        register(owner)
        self.assertEqual(['HollowCountry.Admin'], registered)
        self.assertFalse(ready(owner))
        owner.m_MissionLoaded = True
        self.assertTrue(ready(owner))
        owner.RootPermission = None
        self.assertFalse(ready(owner))
        owner.m_MissionLoaded = True
        register(owner)
        self.assertEqual(['HollowCountry.Admin'], registered, 'late registration must refuse')

    def test_base_has_no_vendor_dependency_and_addon_factory_is_guarded(self):
        _, factory = authored_method(ADMIN, 'HCAdminPermissionAdapter', 'HCDefaultPort', False)
        self.assertIn('return null', factory)
        self.assertNotIn('JMPermissionManager', ADMIN.read_text())
        self.assertTrue(COT.is_file(), 'COT permission provider is missing')
        source = COT.read_text()
        self.assertIn('#ifdef JM_COT_LOADED', source)
        self.assertNotIn('HasRole(', source)
        self.assertNotIn('Print(', source, 'binding never logs peer identifiers')


if __name__ == '__main__':
    unittest.main()
