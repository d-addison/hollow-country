"""#151 authored handlers; native/Expansion boundaries are synthetic, never runtime proof."""
from pathlib import Path
from types import SimpleNamespace as NS
import re
import unittest
from tests.unit.test_hc_building_claim import run

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / 'mods/HollowCountry/scripts/4_World/Camps/HCBaseRaid.c'


def invoke(name, state, env, *args):
    source = CORE.read_text().replace('static HCOperationalStatus HCGetOperationalStatus', 'static HCGroupMember HCGetOperationalStatus')
    source = re.sub(r'\bHCBaseRaid\w* (?=\w+\s*=)', 'HCGroupPort ', source)
    source = source.replace('array<Man>', 'HCGroupPeople')
    return run(source, name, state, env, *args)


class BaseRaidBehavior(unittest.TestCase):
    def warning(self, ready=True, seen=True, recipients=True, reserved=True, saved=True):
        calls = []
        port = NS(HCReady=lambda: ready, HCRefusal=lambda: 'PROBE_PLAYER_BASE_DISPATCH_UNAVAILABLE',
                  HCSeen=lambda *args: seen, HCReserve=lambda *args: calls.append('reserve') or reserved,
                  HCCancel=lambda: calls.append('cancel'), HCWarned=lambda *args: calls.append('armed'))
        owner = NS(Commit=lambda now: calls.append('save') or saved,
                   Tell=lambda *args: calls.append('warning'))
        camp = NS(LastProbe=0)
        env = dict(HCBaseRaid=NS(HCEnabled=lambda: True, HCGet=lambda: port,
                               HCRecipients=lambda *args: recipients,
                               HCRefuse=lambda reason: calls.append(reason)))
        result = invoke('HCWarn', NS(), env, owner, camp, NS(), 1000)
        return result, camp, calls

    def test_missing_dispatch_and_no_sighting_spend_no_cooldown(self):
        for ready, seen in ((False, True), (True, False)):
            result, camp, calls = self.warning(ready=ready, seen=seen)
            self.assertFalse(result)
            self.assertEqual(0, camp.LastProbe)
            self.assertNotIn('save', calls)
            self.assertNotIn('warning', calls)

    def test_warning_requires_online_recipient_and_real_reservation(self):
        for fields in ({'recipients': False}, {'reserved': False}):
            result, camp, calls = self.warning(**fields)
            self.assertFalse(result)
            self.assertEqual(0, camp.LastProbe)
            self.assertNotIn('warning', calls)

    def test_success_persists_before_warning_then_arms_cooldown(self):
        result, camp, calls = self.warning()
        self.assertTrue(result)
        self.assertEqual(1000, camp.LastProbe)
        self.assertEqual(['reserve', 'save', 'warning', 'armed'], calls)

    def test_failed_durable_warning_barrier_cancels_party_without_warning(self):
        result, camp, calls = self.warning(saved=False)
        self.assertFalse(result)
        self.assertEqual(['reserve', 'save', 'cancel'], calls)
        # Ambiguous disk write conservatively retains debit; never replay.
        self.assertEqual(1000, camp.LastProbe)

    def test_status_is_derived_from_binding(self):
        for port, expected in ((None, ('degraded', 'PROBE_PLAYER_BASE_DISPATCH_UNAVAILABLE')),
                               (NS(HCReady=lambda: False, HCRefusal=lambda: 'store_fault'), ('degraded', 'store_fault')),
                               (NS(HCReady=lambda: True), ('ready', 'base_raid_provider_bound'))):
            published = []
            status = NS(HCPublish=lambda *args: published.append(args))
            env = dict(HCBaseRaid=NS(HCEnabled=lambda: True, HCGet=lambda: port),
                       s_Status=status)
            self.assertIs(status, invoke('HCGetOperationalStatus', NS(), env))
            self.assertEqual([expected], published)

    def test_perception_checks_range_before_raycast_and_never_selects_from_camps(self):
        path = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIBaseRaid.c'
        source = path.read_text()
        for distance, visible, expected in ((999, True, False), (25, False, False), (25, True, True)):
            calls = []
            state = NS(m_Actor=NS(GetPosition=lambda: (0, 0, 0)),
                       m_Config=NS(NoticeRangeMeters=10),
                       HCVisible=lambda target, point: calls.append('ray') or visible)
            adapted = source.replace('HCVisible(target, point)', 'self.HCVisible(target, point)')
            env = dict(vector=NS(DistanceSq=lambda *args: distance))
            self.assertEqual(expected, run(adapted, 'HCPerceive', state, env, object(), (1, 0, 1)))
            if distance == 999: self.assertEqual([], calls)
        sense = source.split('void HCSense()', 1)[1].split('override bool HCSeen', 1)[0]
        self.assertNotIn('Camps', sense)
        self.assertIn('GetObjectsAtPosition3D(m_Actor.GetPosition()', sense)



ADDON = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIBaseRaid.c'


def addon(name, state, env, *args):
    source = ADDON.read_text()
    source = re.sub(r'\b(?:HCScavengeState|HCXAIBaseRaidInventory|HCEncounterStore<HCScavengeState>|HCAIPartyIdentity|HCBaseRaidPort|ItemBase|EntityAI|ActionBase|ActionTarget|HCXAIBaseRaid|eAIBase|eAIGroup)\b(?=\s+\w+\s*[=;])', 'HCGroupValue', source)
    return run(source, name, state, env, *args)


class BaseRaidRuntimeHandlers(unittest.TestCase):
    def test_warning_delay_attendance_and_expiry_before_world_work(self):
        for now, unattended, expected in ((100, True, []), (301, False, ['cancel']),
                                          (901, True, ['cancel']), (301, True, ['walk'])):
            calls = []
            state = NS(m_Busy=False, m_Config=NS(MaxObjects=8, MaxPlayers=2, MaxRouteNodes=4),
                       m_Reserved=True, m_Camp=NS(LastProbe=1), m_Ends=900, m_Due=300,
                       m_Owner=object(), m_Point=(1, 0, 1), m_Walking=False,
                       m_Actor=NS(GetGroup=lambda: NS(IsInCombat=lambda: False)),
                       m_Building=None, m_Source=None,
                       HCReady=lambda: True, HCLiveParty=lambda: True,
                       HCCancel=lambda: calls.append('cancel'),
                       HCWalkTo=lambda point: calls.append('walk') or True)
            source = ADDON.read_text().replace('HCBuildingClaim claims', 'HCGroupClaims claims')
            # Local fixture supplies the lead-owned new budget consumer only.
            for helper in ('HCReady', 'HCLiveParty', 'HCCancel', 'HCWalkTo'):
                source = re.sub(r'(?<![.\w])'+helper+r'\(', 'self.'+helper+'(', source)
                source = source.replace('bool self.', 'bool ').replace('void self.', 'void ')
            env = dict(HCBaseRaid=NS(HCEnabled=lambda: True, HCUnattended=lambda *args: unattended),
                       HCCampProbes=NS(HCEnabled=lambda: True),
                       HCServer=NS(HCTickWork=lambda: NS(HCTakeFor=lambda *args: True)),
                       HCUnitBudget=NS(HC_WORK_BASE_RAID=12, HC_WORK_CONSUMERS=13))
            run(source, 'HCStep', state, env, now)
            self.assertEqual(expected, calls)

    def test_native_unlock_completion_rechecks_provider_and_calls_super_only_when_safe(self):
        source = ADDON.read_text().split('modded class ActionUnlockDoors\n', 1)[1].replace('action_data.m_Player', 'action_data.Player')
        for permitted, expected in ((False, ['veto']), (True, ['native'])):
            calls = []
            actor = NS(HCBaseRaidUnlock=True)
            env = dict(eAIBase=NS(Cast=lambda value: actor),
                       HCBaseRaid=NS(HCGet=lambda: 'bound', HCRefuse=lambda reason: calls.append('veto')),
                       HCXAIBaseRaid=NS(Cast=lambda value: NS(HCUnlockAllowed=lambda value: permitted)),
                       super=NS(OnFinishProgressServer=lambda data: calls.append('native')))
            adapted = re.sub(r'\b(?:eAIBase|HCBaseRaidPort|HCXAIBaseRaid) (?=\w+\s*=)', 'HCGroupValue ', source)
            run(adapted, 'OnFinishProgressServer', NS(), env, NS(Player=actor))
            self.assertEqual(expected, calls)
            self.assertFalse(actor.HCBaseRaidUnlock)

    def test_native_unlock_for_other_actors_remains_native(self):
        source = ADDON.read_text().split('modded class ActionUnlockDoors\n', 1)[1].replace('action_data.m_Player', 'action_data.Player')
        source = re.sub(r'\b(?:eAIBase|HCBaseRaidPort|HCXAIBaseRaid) (?=\w+\s*=)', 'HCGroupValue ', source)
        calls = []
        run(source, 'OnFinishProgressServer', NS(),
            dict(eAIBase=NS(Cast=lambda value: None),
                 super=NS(OnFinishProgressServer=lambda data: calls.append('native'))), NS(Player='human'))
        self.assertEqual(['native'], calls)

    def test_global_reservation_and_receipt_barrier_no_replay(self):
        state = NS(m_Reserved=False, m_Site=NS(ProposalId='lease-a'))
        self.assertFalse(addon('HCOwns', state, {}, 'lease-a'))
        state.m_Reserved = True
        self.assertTrue(addon('HCOwns', state, {}, 'lease-a'))
        self.assertFalse(addon('HCOwns', state, {}, 'lease-b'))
        source = ADDON.read_text()
        take = source.split('void HCTakeLoot()', 1)[1].split('void HCStep', 1)[0]
        self.assertLess(take.index('m_Store.Save(m_Receipt)'), take.index('m_Inventory.HCMove(false, m_Receipt)'))
        self.assertEqual(1, take.count('m_Inventory.HCMove('))
        opened = source.split('void HCOpen()', 1)[1].split('override bool HCReady', 1)[0]
        self.assertNotIn('HCMove(', opened)
        self.assertIn('BASE_RAID_RESTART_NO_REPLAY', opened)


class BaseRaidCustodyHandlers(unittest.TestCase):
    def test_failed_intent_cannot_transfer_and_success_moves_once_then_closes(self):
        for saves_work in (False, True):
            events = []
            source_stock, raider_stock = ['finite-item'], []
            crate, actor, stock = object(), object(), object()
            def move(returning, row):
                events.append('move')
                raider_stock.append(source_stock.pop())
                return 2
            inventory = NS(Defaults=NS(TransferRangeMeters=2.5), HCAtSource=lambda: True,
                           HCTheftFirstItem=lambda source: stock, HCMove=move,
                           HCOwner=lambda: 'actor-id')
            identity = NS(HCPartyId=lambda: 'party', HCCargoId=lambda: 'cargo', HCGeneration=lambda: 1)
            def save(receipt):
                events.append('save:' + receipt.Phase)
                return saves_work
            state = NS(m_Source=crate, m_Config=NS(MaxCargoScan=32), m_Actor=actor,
                       m_Site=NS(ProposalId='lease'), m_Owner=object(), m_Camp=object(),
                       m_Store=NS(Save=save), m_Busy=False, m_Healthy=True,
                       HCCancel=lambda: events.append('cancel'))
            env = dict(HCLockTable=NS(CampUnlocked=lambda value: True),
                       HCXAIBaseRaidInventory=lambda: inventory, HCPickerSurvey=lambda: NS(),
                       HCScavengeState=lambda: NS(), HCWorldMaterializer=NS(HCIdentity=lambda lease: identity),
                       HCAIPartyIdentity=NS(HCValid=lambda value: True),
                       HCSearchSupplyRegistry=NS(PersistentId=lambda item: 'native-id'), Print=lambda line: None)
            source = ADDON.read_text()
            source = re.sub(r'\bHCAIPartyIdentity (?=\w+\s*=)', 'HCGroupIdentity ', source)
            source = source.replace('HCCancel();', 'self.HCCancel();')
            run(source, 'HCTakeLoot', state, env)
            if saves_work:
                self.assertEqual(['save:acquiring', 'move', 'save:returned', 'cancel'], events)
                self.assertEqual(([], ['finite-item']), (source_stock, raider_stock))
            else:
                self.assertEqual(['save:acquiring', 'cancel'], events)
                self.assertEqual((['finite-item'], []), (source_stock, raider_stock))



class BaseRaidAdmissionAndAttendance(unittest.TestCase):
    def test_live_attendance_rechecks_current_group_and_vetoes_unknown_overflow(self):
        from tests.unit.test_group_server import EArray
        group, distance, clear = ['owners'], [0], [True]
        player = NS(IsAlive=lambda: True, GetIdentity=lambda: 'identity', GetPosition=lambda: (0, 0, 0))
        people = [player]
        owner = NS(GroupId=lambda actor: group[0])
        camp = NS(GroupId='owners', Position=(0, 0, 0))
        config = NS(MaxPlayers=2, AttendanceRangeMeters=500, ObserverRangeMeters=500)
        env = dict(HCCampModule=NS(Get=lambda: owner), HCEnabled=lambda: True,
                   GetGame=lambda: NS(IsServer=lambda: True, GetPlayers=lambda out: out.extend(people)),
                   HCGroupPeople=EArray, PlayerBase=NS(Cast=lambda value: value),
                   s_Config=config, vector=NS(DistanceSq=lambda *args: distance[0]),
                   HCObserverTransitionGate=NS(CanTransition=lambda *args: clear[0]))
        check = lambda: invoke('HCUnattended', NS(), env, owner, camp, (0, 0, 0))
        self.assertFalse(check())
        distance[0] = 500 * 500 + 1
        self.assertTrue(check())
        distance[0], group[0] = 0, 'visitors'
        self.assertTrue(check(), 'membership is read live')
        clear[0] = False
        self.assertFalse(check(), 'all-player observer veto is additional to group attendance')
        clear[0] = True
        people.extend([player, player])
        self.assertFalse(check(), 'never use a partial player snapshot')

    def test_warning_checks_the_exact_cached_tell_recipients(self):
        from tests.unit.test_group_server import EArray
        player = NS(IsAlive=lambda: True, IsPendingDeletion=lambda: False, GetIdentity=lambda: 'peer')
        state = NS(m_Players=EArray([player]))
        group = ['owners']
        env = dict(PlayerBase=NS(Cast=lambda value: value), GroupId=lambda peer: group[0])
        camp = NS(GroupId='owners')
        self.assertTrue(invoke('HCBaseRaidHasRecipients', state, env, camp, 32))
        group[0] = 'visitors'
        self.assertFalse(invoke('HCBaseRaidHasRecipients', state, env, camp, 32))
        group[0] = 'owners'
        state.m_Players.clear()
        self.assertFalse(invoke('HCBaseRaidHasRecipients', state, env, camp, 32))

    def test_operator_off_never_reads_provider_or_spends_work(self):
        def unexpected():
            self.fail('disabled raid read the provider')
        env = dict(HCBaseRaid=NS(HCEnabled=lambda: False, HCGet=unexpected))
        self.assertFalse(invoke('HCWarn', NS(), env, NS(), NS(), NS(), 1000))

    def test_config_missing_fields_nan_and_out_of_range_are_refused(self):
        defaults = dict(Version=1, NoticeRangeMeters=40, AttendanceRangeMeters=500,
                        ObserverRangeMeters=500, SourceRangeMeters=12, WarningSeconds=300,
                        RaidSeconds=600, MaxPlayers=32, MaxObjects=128, MaxDoors=32,
                        MaxRouteNodes=32, MaxCargoScan=32)
        for changed, expected in (({}, True), ({'NoticeRangeMeters': float('nan')}, False),
                                  ({'NoticeRangeMeters': 0}, False), ({'MaxObjects': 129}, False),
                                  ({'WarningSeconds': 0}, False), ({'MaxCargoScan': 0}, False)):
            state = NS(**(defaults | changed))
            self.assertEqual(expected, invoke('HCValid', state,
                dict(this=state, HCOperatorSettingsRegistry=NS(HCFind=lambda key: False))))



class BaseRaidSettingsIntegration(unittest.TestCase):
    def test_lead_settings_edits_in_local_fixture_match_source(self):
        import json
        from unittest.mock import patch
        from tools.validate import settings_consistency as sc
        # Explicit LOCAL copy only: shared registry/mirror/validator are read-only.
        fields = [('Version', 'int', 1, 1, 1), ('NoticeRangeMeters', 'float', 40, 2, 100),
                  ('AttendanceRangeMeters', 'float', 500, 500, 1000),
                  ('ObserverRangeMeters', 'float', 500, 500, 1000),
                  ('SourceRangeMeters', 'float', 12, 2, 12), ('WarningSeconds', 'int', 300, 60, 600),
                  ('RaidSeconds', 'int', 600, 60, 600), ('MaxPlayers', 'int', 32, 1, 32),
                  ('MaxObjects', 'int', 128, 1, 128), ('MaxDoors', 'int', 32, 1, 32),
                  ('MaxRouteNodes', 'int', 32, 1, 32), ('MaxCargoScan', 'int', 32, 1, 32)]
        added = [dict(key='BaseRaid.'+key, type=kind, default=value, min=low, max=high,
                      owner='HCBaseRaidConfig') for key, kind, value, low, high in fields]
        rows = json.loads(sc.REGISTRY.read_text()) + added
        native = sc.NATIVE.read_text().replace('        // END GENERATED SETTINGS REGISTRY',
                    sc.render_native_registry(added) + '\n        // END GENERATED SETTINGS REGISTRY')
        with patch.dict(sc.EXTERNAL_OWNERS, {'HCBaseRaidConfig':
             ('mods/HollowCountry/scripts/4_World/Camps/HCBaseRaid.c', 'BaseRaid', 'config.')}):
            self.assertEqual([], sc.check_consistency(registry=rows, native=native))


if __name__ == '__main__':
    unittest.main()
