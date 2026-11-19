"""HC-26 synthetic authored-handler execution; never DayZ acceptance.

Spec/plan/task: HC-26 group presentation privacy and lifecycle (Wave 2).
RED/GREEN command:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_team_ping -v
Actual RED: AssertionError: [] != [namespace(HCPinExpiresUtc=200)] : removed/rejoined member received cached death pin
GREEN: Ran 1 test; OK. Extended below for the same HC-26 behavior.
Native RPC, renderer, persistence and two-client acceptance remain PENDING.
"""
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit.test_group_server import EArray, translated_rules
from tests.unit.test_map_layers import EStr, translate
from tests.unit.test_v2_pins import DeathStoreFixture, string_calls

ROOT = Path(__file__).resolve().parents[2]
GROUPS = ROOT / 'mods/HollowCountry/scripts/4_World/Groups'


def source(name):
    text = string_calls((GROUPS / (name + '.c')).read_text()).replace('protected ', '').replace('override ', '')
    text = re.sub(r'(?<![\w.])m_\w+\b', lambda m: 'self.' + m[0], text)
    text = re.sub(r'([\w.]+)--(?=;)', r'\1 -= 1', text)
    return re.sub(r'for \(int (\w+) = ([^;]+); \1 >= 0; \1--\)',
                  r'foreach (int \1 : reverse_indices(\2))', text)


class TeamPingPrivacy(unittest.TestCase):
    def test_current_membership_receipts_and_refusals(self):
        """One HC-26 behavior, with explicit synthetic DTO/clock/transport ports."""
        now = [100]
        group = N(Id=1, Epoch=8, Members=EArray(['alice', 'bob']))
        old = N(GroupId=1, Epoch=7, PlayerId='alice',
                Pin=N(HCPinExpiresUtc=200))
        death = N(m_State=N(Rows=EArray([old])), m_Expired=0)
        env = dict(HCGroupClock=N(Utc=lambda: now[0]),
                   HCGroupVisibility=N(HCSnapshotActive=lambda: False),
                   reverse_indices=lambda n: range(n, -1, -1))
        translate(source('HCDeathPin'), 'HCDeathPins', env,
                  only=('HCPrune', 'HCCollect'))
        death.HCPrune = lambda at, replaced='': env['HCPrune'](death, at, replaced)
        output = EArray()
        env['HCCollect'](death, group, 64, output)
        self.assertEqual([], output, 'removed/rejoined member received cached death pin')
        # Current epoch is accepted, expiry is exclusive, old schema fails closed.
        for epoch, expiry, count in ((8, 101, 1), (8, 100, 0), (0, 200, 0)):
            old.Epoch, old.Pin.HCPinExpiresUtc = epoch, expiry
            death.m_State.Rows = EArray([old])
            output.clear()
            env['HCCollect'](death, group, 64, output)
            self.assertEqual(count, len(output))

        rules = translated_rules()
        clock, logs, sent, notices = [100], [], [], []
        def peer(uid, x, session='synthetic-session'):
            identity = N(GetId=lambda: uid)
            player = N(GetIdentity=lambda: identity, IsAlive=lambda: True,
                       IsUnconscious=lambda: False, GetPosition=lambda: [x, 0, 100])
            return N(Id=uid, Identity=identity, Player=player, Session=session,
                     Name=EStr(uid))
        alice, bob, stranger = peer('alice', 100), peer('bob', 200), peer('stranger', 150)
        service = N(m_Healthy=True, m_State=N(Groups=EArray([group])),
                    m_Config=N(Enabled=True, HCTeamPingEnabled=True, MaxIconDistance=1000.,
                               RequireLOS=False, RequireRadio=False),
                    m_Peers=EArray([alice, bob, stranger]),
                    Live=lambda p: bool(p and p.Player and p.Identity and
                                        p.Player.GetIdentity() is p.Identity),
                    Peer=lambda uid: next((p for p in service.m_Peers if p.Id == uid), None),
                    HasGPS=lambda p: True, VisibilityAllows=lambda a, b: True,
                    SendSnapshot=lambda p, kind, request: sent.append(p.Id))
        singleton = N(value=None)
        module = N(m_Rows=EArray(), m_AdmissionPrinted=False, m_LogAfter=0,
                   m_Expired=0, m_Refused=0, m_PruneCursor=0, m_LastRefusal="none",
                   m_Work=N(HCReset=lambda *a: None, HCContinue=lambda: True),
                   m_Units=N(HCReset=lambda *a: None, HCTake=lambda cost: True))
        singleton.value = module
        shared = dict(HCGroupClock=N(Utc=lambda: clock[0]),
                      GetGame=lambda: N(IsServer=lambda: True, GetTickTime=lambda: clock[0]),
                      HCGroupRules=N(**{name: rules[name] for name in
                                       ('FindGroup', 'ById', 'PositionValid', 'DeadlineFits')}),
                      HCGroupCode=rules['HCGroupCode'],
                      HCGroupSnapshotKind=N(FULL=0),
                      HCGroupService=N(Get=lambda: service),
                      HCGroupPins=N(Get=lambda: None), HCDeathPins=N(Get=lambda: None),
                      NotificationSystem=N(SendNotificationToPlayerExtended=lambda p, *args:
                                           notices.append(p)),
                      Print=logs.append, str=str, singleton=singleton,
                      reverse_indices=lambda n: range(n, -1, -1),
                      HCGroupPlace=lambda: N(), HCTeamPingRow=lambda: N())
        snapshot_context = N(active=False, uid='')
        visibility = dict(shared)
        translate(source('HCGroupVisibility'), 'HCGroupVisibility', visibility,
                  only=('HCWithinRange',))
        context_env = dict(shared, snapshot_context=snapshot_context)
        context_source = source('HCGroupVisibility').replace('s_InSnapshot', 'snapshot_context.active').replace('s_Recipient', 'snapshot_context.uid')
        translate(context_source, 'HCGroupVisibility', context_env,
                  only=('HCSnapshotActive', 'HCRecipient', 'HCSnapshot'))
        shared['HCGroupVisibility'] = N(
            HCWithinRange=visibility['HCWithinRange'],
            **{name: context_env[name] for name in ('HCSnapshotActive', 'HCRecipient', 'HCSnapshot')})
        shared['HCTeamPingModule'] = N(Get=lambda: singleton.value)
        def bind(filename, classname, target, names, replacements=()):
            text = source(filename)
            if classname == 'HCGroupService':
                text = re.sub(r'(?<![\w.])(Live|Peer|HasGPS|VisibilityAllows|SendSnapshot)\(', r'self.\1(', text)
            for before, after in replacements:
                text = text.replace(before, after)
            table = dict(shared)
            translate(text, classname, table, only=names)
            for name in names:
                if name in table:
                    setattr(target, name, lambda *a, name=name: table[name](target, *a))
            return table
        service_names = ('HCPingGroup', 'HCPingDeliver', 'HCPingPreference',
                         'HCPresentationGroup', 'HCPresentationRange',
                         'HCPresentationAllows', 'HCPresentationReady')
        bind('HCTeamPing', 'HCGroupService', service, service_names)
        names = ('HCReceive', 'HCCollect', 'HCStatus', 'HCForget', 'HCInvalidate',
                 'HCReport', 'HCVisible', 'OnStop')
        bind('HCTeamPing', 'HCTeamPingModule', module, names,
                     (('s_Instance', 'singleton.value'), ('this', 'self')))
        code = shared['HCGroupCode']
        # Direct forged calls cannot bypass the RPC's authenticated canonical peer.
        forged = peer('alice', 100)
        self.assertEqual(code.DENIED, module.HCReceive(forged, 0))
        self.assertEqual([], module.m_Rows)
        self.assertEqual(code.INVALID, module.HCReceive(alice, 99))
        self.assertEqual(code.OK, module.HCReceive(alice, 0))
        self.assertEqual(['alice', 'bob'], sent)
        # The sender's own snapshot shows its marker; only teammates are notified.
        self.assertEqual(1, len(notices))
        self.assertEqual(60, module.m_Rows[0].Pin.HCPinExpiresUtc - clock[0])
        self.assertEqual(code.RATE, module.HCReceive(alice, 0))
        clock[0] += 9
        self.assertEqual(code.RATE, module.HCReceive(alice, 0))
        clock[0] += 1
        self.assertEqual(code.OK, module.HCReceive(alice, 0))
        identity_id = alice.Identity.GetId
        alice.Identity.GetId = lambda: 'spoofed-sender-id'
        self.assertEqual(code.DENIED, module.HCReceive(alice, 0))
        alice.Identity.GetId = identity_id
        self.assertTrue(module.HCVisible('bob', module.m_Rows[0].Pin))
        self.assertFalse(module.HCVisible('stranger', module.m_Rows[0].Pin))
        bob.Player.GetPosition = lambda: [1101, 0, 100]  # Just outside 1 km cap.
        self.assertFalse(module.HCVisible('bob', module.m_Rows[0].Pin))
        bob.Player.GetPosition = lambda: [1100, 0, 100]
        self.assertTrue(module.HCVisible('bob', module.m_Rows[0].Pin))
        service.VisibilityAllows = lambda a, b: False
        self.assertFalse(module.HCVisible('bob', module.m_Rows[0].Pin))
        service.VisibilityAllows = lambda a, b: True
        snapshot_context.active, snapshot_context.uid = True, 'stranger'
        output.clear()
        module.HCCollect(group, 64, output)
        self.assertEqual([], output, 'transport collection leaked a pin to a stranger')
        snapshot_context.active, snapshot_context.uid = False, ''
        # Purge on group epoch and connection/life change, not only hide on read.
        group.Epoch += 1
        module.HCInvalidate()
        self.assertEqual([], module.m_Rows)
        clock[0] += 10
        self.assertEqual(code.OK, module.HCReceive(alice, 1))
        alice.Session = 'synthetic-reconnect'
        module.HCInvalidate()
        self.assertEqual([], module.m_Rows)
        clock[0] += 10
        self.assertEqual(code.OK, module.HCReceive(alice, 2))
        alice.Player.IsAlive = lambda: False
        module.HCInvalidate()
        self.assertEqual([], module.m_Rows)
        alice.Player.IsAlive = lambda: True
        clock[0] += 10
        self.assertEqual(code.OK, module.HCReceive(alice, 0))
        clock[0] += 60
        output.clear()
        module.HCCollect(group, 64, output)
        self.assertEqual([], output)
        module.HCInvalidate()
        self.assertEqual([], module.m_Rows)
        # Recipient-specific final Places filter executes the authored wrapper.
        clock[0] += 10
        self.assertEqual(code.OK, module.HCReceive(alice, 0))
        ping = module.m_Rows[0].Pin
        death_pin = N(Id=EStr('hc-death:synthetic'), Position=[100, 0, 100])
        service.m_Config.RequireLOS = True
        self.assertFalse(service.HCPresentationAllows('bob', death_pin))
        service.m_Config.RequireLOS = False
        self.assertTrue(service.HCPresentationAllows('bob', death_pin))
        # Execute the authored snapshot boundary around real pin collection.
        death.m_State.Rows = EArray([N(GroupId=group.Id, Epoch=group.Epoch,
                                       PlayerId='alice', Pin=death_pin)])
        death_pin.HCPinExpiresUtc = 10000
        death_table = bind('HCDeathPin', 'HCDeathPins', death, ('HCCollect', 'HCPrune'))
        death.HCPrune = lambda at, replaced='': death_table['HCPrune'](death, at, replaced)
        frames = []
        def base_snapshot(peer, kind, request):
            pins = EArray()
            module.HCCollect(group, 64, pins)
            death.HCCollect(group, 64, pins)
            frames.append((peer.Id, pins))
        boundary = dict(shared, super_SendSnapshot=base_snapshot)
        text = source('HCTeamPing').replace('super.SendSnapshot(', 'super_SendSnapshot(')
        text = re.sub(r'(?<![\w.])(Live|Peer)\(', r'self.\1(', text)
        translate(text, 'HCGroupService', boundary, only=('SendSnapshot',))
        boundary['SendSnapshot'](service, bob, 0, 0)
        self.assertEqual([ping, death_pin], frames[-1][1])
        boundary['SendSnapshot'](service, stranger, 0, 0)
        self.assertEqual([], frames[-1][1])
        bob.Player.GetPosition = lambda: [1101, 0, 100]
        boundary['SendSnapshot'](service, bob, 0, 0)
        # Pings are range-bound; a corpse-run pin is membership-bound only.
        self.assertEqual([death_pin], frames[-1][1])
        bob.Player.GetPosition = lambda: [5100, 0, 100]
        self.assertTrue(service.HCPresentationAllows('bob', death_pin))
        self.assertFalse(service.HCPresentationAllows('stranger', death_pin))
        bob.Player.GetPosition = lambda: [200, 0, 100]
        self.assertFalse(snapshot_context.active)
        self.assertEqual('', snapshot_context.uid)
        # The death writer captures membership epoch at the existing save barrier.
        store = DeathStoreFixture()
        store.owner.m_State = N(NextId=1, Rows=EArray())
        self.assertTrue(store.owner.HCPublish(group, 'alice', 'Alice', [100, 0, 100]))
        self.assertEqual(group.Epoch, store.owner.m_State.Rows[0].Epoch)
        self.assertEqual(group.Epoch, store.saves[0][1].Rows[0].Epoch)
        # Exercise real read/recover/validation with explicit synthetic epoch DTOs.
        image = json.loads(store.image())
        image['Rows'][0]['Epoch'] = 0  # Pre-HC-26/unknown: valid store, never a grant.
        store.files[store.path] = json.dumps(image)
        recovered = store.owner.HCReadState(store.path)
        self.assertIsNotNone(recovered)
        self.assertEqual(0, recovered.Rows[0].Epoch)
        # Retained cleanup cursors eventually purge all stale membership receipts.
        death.m_State.Rows = EArray(N(GroupId=1, Epoch=group.Epoch - 1,
                                     PlayerId='alice', Pin=N(HCPinExpiresUtc=10000))
                                   for _ in range(70))
        death.m_PruneCursor, death.m_Expired = 0, 0
        death.m_LogAfter, death.m_LastRefusal = 0, 'none'
        allowance = [0]
        def take(cost):
            allowance[0] -= cost
            return allowance[0] >= 0
        death.m_Work = N(HCReset=lambda *a: None, HCContinue=lambda: True)
        death.m_Units = N(HCReset=lambda limit: allowance.__setitem__(0, limit), HCTake=take)
        bind('HCDeathPin', 'HCDeathPins', death, ('HCInvalidate', 'HCLog'))
        for expected in (38, 6, 0):
            death.HCInvalidate()
            self.assertEqual(expected, len(death.m_State.Rows))
        self.assertEqual(70, death.m_Expired)
        shared['HCDeathPins'].Get = lambda: death
        clock[0] += 60
        service.m_Config.RequireRadio = True
        self.assertFalse(service.HCPresentationAllows('bob', death_pin))
        self.assertIn('refused=death_los_radio_unavailable', logs[-1])
        service.m_Config.RequireRadio = False
        # Existing connection/death callbacks invoke source cleanup only for
        # canonical identities; no shared mission edit or client permission hook.
        lifecycle = dict(shared, super_Connected=lambda *a: None,
                         super_Disconnected=lambda *a: None,
                         super_Broadcast=lambda: None)
        lifecycle_source = source('HCTeamPing')
        for name in ('Connected', 'Disconnected', 'Broadcast'):
            lifecycle_source = lifecycle_source.replace('super.' + name + '(', 'super_' + name + '(')
        lifecycle_source = re.sub(r'(?<![\w.])(Live|Peer)\(', r'self.\1(', lifecycle_source)
        translate(lifecycle_source, 'HCGroupService', lifecycle,
                  only=('Connected', 'Disconnected', 'HCPresentationFell'))
        service.Broadcast = lambda: sent.append('replacement-full')
        lifecycle['Disconnected'](service, forged.Identity)
        self.assertEqual(1, len(module.m_Rows))
        lifecycle['Connected'](service, forged.Identity, alice.Player)
        self.assertEqual(1, len(module.m_Rows))
        lifecycle['Disconnected'](service, alice.Identity)
        self.assertEqual([], module.m_Rows)
        clock[0] += 10
        self.assertEqual(code.OK, module.HCReceive(alice, 0))
        lifecycle['Connected'](service, alice.Identity, alice.Player)
        self.assertEqual([], module.m_Rows)
        clock[0] += 10
        self.assertEqual(code.OK, module.HCReceive(alice, 0))
        lifecycle['HCPresentationFell'](service, forged.Player)
        self.assertEqual(1, len(module.m_Rows))
        lifecycle['HCPresentationFell'](service, alice.Player)
        self.assertEqual([], module.m_Rows)
        # Refusal logging stays bounded under repeated requests, retaining reason.
        before = len(logs)
        for _ in range(20):
            module.HCReport('sender_rate', 0)
        self.assertLessEqual(len(logs) - before, 1)
        clock[0] += 60
        module.HCReport('none', 0)
        self.assertIn('refused=sender_rate', logs[-1])
        # Feature off removes source receipts and actively replaces cached views.
        service.Broadcast = lambda: sent.append('replacement-full')
        module.m_Status = N(HCPublish=lambda *a: None)
        module.OnStop()
        self.assertIsNone(singleton.value)
        self.assertIsNone(module.m_Rows)
        self.assertFalse(service.m_Config.HCTeamPingEnabled)
        self.assertEqual('replacement-full', sent[-1])
        self.assertEqual(code.DISABLED, module.HCReceive(alice, 0))


if __name__ == '__main__':
    unittest.main()
