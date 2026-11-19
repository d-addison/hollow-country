"""#212: execute authored selection/policy/store with explicit synthetic IO.
No native inventory, visibility, persistence or two-client evidence is supplied.
"""
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from tests.unit.test_admin_test_kit import Cell, base_scope, compile_authored
from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
CAMPS = ROOT / 'mods/HollowCountry/scripts/4_World/Camps'
ADMIN = ROOT / 'mods/HollowCountry/scripts/4_World/Admin/HCAdminDirectors.c'


def anchor():
    return NS(Id='', GroupId='', Position=(0, 0, 0), AnchorKind='', ClaimBuildingId='',
              Tier=0, LastVisit=0, LastProbe=0, FireClass='', FireRef='', LastLit=0)


def claim(group=1, x=20, held=14):
    return NS(GroupId=group, BuildingId='synthetic-house-' + str(group), Position=(x, 0, 0),
              ClaimedUtc=NOW-held*86400, LastVisitUtc=NOW, AbsentSeconds=0,
              EncounterVersion=0, Anchor=None)

NOW = 30*86400



def policy_scope():
    eligible = compile_authored(CAMPS / 'HCCampProbes.c', 'HCCampProbes', 'Eligible',
                               base_scope(), modded=False)
    policy = compile_authored(CAMPS / 'HCCampProbes.c', 'HCCampProbes', 'HCClaimEligibility',
        base_scope(HCCampProbes=NS(Eligible=lambda *args: eligible(None, *args))), modded=False)
    return NS(HCClaimEligibility=lambda *args: policy(None, *args))


class ClaimTargets(unittest.TestCase):
    def store(self, name, *args):
        fn = compile_authored(CAMPS / 'HCCampStore.c', 'HCCampStore', name,
                              base_scope(HCCampRecord=anchor, HCAILimits=NS(Get=lambda: NS(MaxCamps=32)),
                                         Print=lambda line: None), modded=False)
        return fn(None, *args)

    def test_nearest_eligible_claim_without_a_hearth_uses_admin_selection(self):
        rows = EArray([claim(1, 20), claim(2, 10), claim(3, 1, 1)])
        # Explicit synthetic preloaded claim encounter rows; no fire is created.
        for row in rows:
            row.Anchor = anchor()
            row.Anchor.AnchorKind = 'claim'
            row.Anchor.Id = 'claim-' + str(row.GroupId)
            row.Anchor.Position = row.Position
        owner = NS(m_Running=True, m_LastUtc=NOW, m_Data=NS(Camps=EArray(), Claims=rows))
        scope = base_scope(HCAILimits=NS(Get=lambda: NS(MaxCamps=32)),
                           HCWorldClock=NS(UTC=lambda: NOW),
                           HCBuildingClaim=NS(HCGet=lambda: True),
                           HCServer=NS(Get=lambda: NS(HCTickWork=lambda: NS(HCTake=lambda cost: True))),
                           HCCampProbes=policy_scope())
        owner.HCReadClaimScan = lambda candidate, reason, budgeted: NS(Hidden=lambda burning: False, Storage=True)
        owner.HCReserveClaimSelection = lambda count, reason: True
        owner.HCEncounterCount = lambda: len(rows)
        owner.HCEncounterTarget = lambda index, now: rows[index].Anchor if index < 2 else None
        fn = compile_authored(ADMIN, 'HCCampModule', 'HCAdminSelectCamp', scope,
                              ('HCEncounterCount', 'HCEncounterTarget', 'HCReadClaimScan', 'HCReserveClaimSelection'))
        self.assertIs(rows[1].Anchor, fn(owner, (0, 0, 0), Cell(), True),
                      'nearest eligible claim must be selectable without a hearth camp')
        owner.HCReadClaimScan = lambda candidate, reason, budgeted: NS(Hidden=lambda burning: False, Storage=candidate is rows[0].Anchor)
        self.assertIs(rows[0].Anchor, fn(owner, (0, 0, 0), Cell(), True),
                      'an empty closer claim must not mask stored cargo farther away')
        owner.HCReadClaimScan = lambda candidate, reason, budgeted: NS(Hidden=lambda burning: False, Storage=False)
        refusal = Cell()
        self.assertIsNone(fn(owner, (0, 0, 0), refusal, True))
        self.assertEqual('CLAIM_NO_STORED_ITEMS', refusal.value)

    def test_claim_cooldowns_survive_json_reload_and_do_not_renew_member_presence(self):
        data = NS(Version=1, Claims=EArray([claim()]))
        self.assertTrue(self.store('HCPrepareClaimTargets', data))
        self.assertEqual(2, data.Version)
        row = data.Claims[0]
        self.assertEqual(('claim', row.BuildingId), (row.Anchor.AnchorKind, row.Anchor.ClaimBuildingId))
        self.assertEqual(('', '', 0), (row.Anchor.FireClass, row.Anchor.FireRef, row.Anchor.LastLit))
        row.Anchor.LastVisit = NOW
        row.Anchor.LastProbe = NOW-17
        encoded = json.dumps(data, default=vars)
        reloaded = json.loads(encoded, object_hook=lambda fields: NS(**fields))
        reloaded.Claims = EArray(reloaded.Claims)
        self.assertTrue(self.store('HCPrepareClaimTargets', reloaded))
        target = reloaded.Claims[0].Anchor
        self.assertEqual((NOW, NOW-17), (target.LastVisit, target.LastProbe))
        self.assertEqual(NOW, reloaded.Claims[0].LastVisitUtc)
        target.LastProbe = NOW+1
        self.assertFalse(self.store('HCClaimTargetValid', reloaded.Claims[0], NOW))

    def test_authored_store_save_then_load_preserves_claim_encounter_cooldowns(self):
        data = NS(Version=1, ClaimsVersion=1, SavedUtc=NOW,
                  Claims=EArray([claim()]), Camps=EArray())
        self.assertTrue(self.store('HCPrepareClaimTargets', data))
        data.Claims[0].Anchor.LastVisit = NOW-1
        data.Claims[0].Anchor.LastProbe = NOW-2
        durable = []
        def save(path, row, cap):
            durable[:] = [json.dumps(row, default=vars)]
            return True
        def validate(row, now):
            # Real authored anchor migration/validation, synthetic empty camp
            # list; legacy claim metadata validation is covered by its suite.
            return self.store('HCPrepareClaimTargets', row) and all(
                self.store('HCClaimTargetValid', claim_row, now) for claim_row in row.Claims)
        source = (CAMPS / 'HCCampStore.c').read_text()
        # Language-only adaptation of native generic and out-reference IO.
        source = source.replace('HCV2ThreatStore<HCCampData>', 'SyntheticIO')
        source = source.replace('HCCampData data;', 'HCCampData data = fixture_data;')
        source = source.replace('SyntheticIO.Load(PATH, BYTES, data)', 'SyntheticIO.Load(PATH, BYTES)')
        with tempfile.TemporaryDirectory(prefix='w57-store-') as directory:
            path = Path(directory) / 'HCCampStore.c'
            path.write_text(source)
            scope = base_scope(PATH='synthetic/camps.json', BYTES=1048576,
                SyntheticIO=NS(CanOpen=lambda path: True, Save=save, Load=lambda *args: bool(durable)),
                Valid=validate, HCClaimsMigrate=lambda row: None, FileExist=lambda path: True)
            save_fn = compile_authored(path, 'HCCampStore', 'Save', scope, modded=False)
            self.assertTrue(save_fn(None, data, NOW))
            loaded = json.loads(durable[0], object_hook=lambda values: NS(**values))
            loaded.Claims = EArray(loaded.Claims)
            loaded.Camps = EArray(loaded.Camps)
            scope['fixture_data'] = loaded
            load_fn = compile_authored(path, 'HCCampStore', 'Load', scope, modded=False)
            result = load_fn(None, NOW+1)
        self.assertIs(loaded, result)
        self.assertEqual((NOW-1, NOW-2), (result.Claims[0].Anchor.LastVisit, result.Claims[0].Anchor.LastProbe))
        self.assertEqual(('', '', 0), (result.Claims[0].Anchor.FireClass, result.Claims[0].Anchor.FireRef,
                                      result.Claims[0].Anchor.LastLit))

    def test_claim_eligibility_names_age_storage_hidden_and_independent_cooldowns(self):
        eligible = compile_authored(CAMPS / 'HCCampProbes.c', 'HCCampProbes', 'Eligible', base_scope(), modded=False)
        fn = compile_authored(CAMPS / 'HCCampProbes.c', 'HCCampProbes', 'HCClaimEligibility',
                              base_scope(HCCampProbes=NS(Eligible=lambda *args: eligible(None, *args))), modded=False)
        row = claim()
        row.Anchor = anchor()
        cases = [(NOW, True, False, False, ''),
                 (row.ClaimedUtc+13*86400, True, False, False, 'CLAIM_HOLD_DAYS'),
                 (NOW, False, False, False, 'CLAIM_NO_STORED_ITEMS'),
                 (NOW, True, True, False, 'CLAIM_HIDDEN')]
        for now, stored, hidden, raid, expected in cases:
            self.assertEqual(expected, fn(None, row, now, stored, hidden, raid))
        row.Anchor.LastVisit = NOW
        self.assertEqual('CLAIM_VISIT_COOLDOWN', fn(None, row, NOW, True, False, False))
        self.assertEqual('', fn(None, row, NOW, True, False, True))
        row.Anchor.LastProbe = NOW
        self.assertEqual('CLAIM_PROBE_COOLDOWN', fn(None, row, NOW, True, False, True))
        self.assertEqual('', fn(None, row, NOW+259200, True, False, True))

    def test_shared_index_keeps_hearth_and_rejects_young_or_disbanded_claim(self):
        row = claim()
        self.assertTrue(self.store('HCPrepareClaimTargets', NS(Version=1, Claims=EArray([row]))))
        hearth = anchor()
        hearth.Id = 'synthetic-hearth'
        owner = NS(m_Data=NS(Camps=EArray([hearth]), Claims=EArray([row])))
        live, group_state = [True], [1]
        eligible = compile_authored(CAMPS / 'HCCampProbes.c', 'HCCampProbes', 'Eligible', base_scope(), modded=False)
        scope = base_scope(HCAILimits=NS(Get=lambda: NS(MaxCamps=32)),
            HCBuildingClaim=NS(HCGet=lambda: live[0]),
            HCCampStore=NS(HCClaimTargetValid=lambda r, now: self.store('HCClaimTargetValid', r, now)),
            HCGroupService=NS(Get=lambda: NS(HCClaimGroupState=lambda group: group_state[0])),
            HCCampProbes=NS(Eligible=lambda *args: eligible(None, *args)))
        count = compile_authored(CAMPS / 'HCCampModule.c', 'HCCampModule', 'HCEncounterCount', scope, modded=False)
        target = compile_authored(CAMPS / 'HCCampModule.c', 'HCCampModule', 'HCEncounterTarget', scope,
                                  ('HCEncounterCount',), modded=False)
        owner.HCEncounterCount = lambda: count(owner)
        self.assertEqual(2, count(owner))
        self.assertIs(hearth, target(owner, 0, NOW))
        self.assertIs(row.Anchor, target(owner, 1, NOW))
        self.assertIsNone(target(owner, 1, row.ClaimedUtc+13*86400))
        group_state[0] = 0
        self.assertIsNone(target(owner, 1, NOW))
        live[0] = False
        self.assertEqual(1, count(owner))
        self.assertIsNone(target(owner, 1, NOW))

    def test_bounded_native_storage_scan_requires_actual_cargo_and_budget(self):
        # Synthetic native object/cargo arrays, no DayZ inventory evidence.
        items, permitted = [], [True]
        config = NS(MaxObjects=2, MaxPlayers=2, SourceRangeMeters=12)
        def objects_at(position, radius, objects, cargos):
            self.assertEqual(12, radius)
            objects.extend(items)
        scope = base_scope(HCBaseRaid=NS(HCEnabled=lambda: True, HCConfig=lambda: config),
            HCServer=NS(HCTickWork=lambda: NS(HCTakeFor=lambda consumer, cost: permitted[0])),
            HCUnitBudget=NS(HC_WORK_BASES=8), array=EArray,
            GetGame=lambda: NS(GetObjectsAtPosition3D=objects_at),
            HCCampScan=NS(Read=lambda *args: NS(Storage=True), StorageItem=lambda item: item.storage),
            ItemBase=NS(Cast=lambda obj: obj))
        fn = compile_authored(CAMPS / 'HCCampModule.c', 'HCCampModule', 'HCReadClaimScan', scope, modded=False)
        def item(count, storage=True):
            return NS(storage=storage, IsPendingDeletion=lambda: False, IsRuined=lambda: False,
                GetInventory=lambda: NS(GetCargo=lambda: NS(GetItemCount=lambda: count)))
        reason = Cell()
        for entries, expected in (([], False), ([item(0)], False), ([item(1, False)], False),
                                  ([item(1)], True)):
            items[:] = entries
            self.assertEqual(expected, fn(NS(), anchor(), reason, False).Storage)
        items[:] = [item(1)]*3
        self.assertIsNone(fn(NS(), anchor(), reason, False))
        self.assertEqual('CLAIM_STORAGE_SCAN_CAP', reason.value)
        permitted[0] = False
        self.assertIsNone(fn(NS(), anchor(), reason, False))
        self.assertEqual('CLAIM_SCAN_WORK_BUDGET', reason.value)

    def test_existing_hearth_selector_cases_with_explicit_native_defaults(self):
        # The existing module is read-only in this worker. Run its unmodified
        # scenarios with a local fixture adapter for the new optional argument
        # and the native zero-filled provenance field.
        from tests.unit import test_ops_admin_controls as existing
        original = existing.compile_authored
        def compile_fixture(*args, **kwargs):
            fn = original(*args, **kwargs)
            def invoke(owner, pos, reason, *ignored):
                for camp in owner.m_Data.Camps:
                    camp.AnchorKind = ''
                return fn(owner, pos, reason, False)
            return invoke
        with patch.object(existing, 'compile_authored', compile_fixture):
            existing.CampSelection('test_nearest_scan_is_bounded_by_config_and_shared_work').test_nearest_scan_is_bounded_by_config_and_shared_work()

    def test_hearth_policy_is_unchanged(self):
        fn = compile_authored(CAMPS / 'HCCampProbes.c', 'HCCampProbes', 'Eligible', base_scope(), modded=False)
        self.assertTrue(fn(None, 3, 14, NOW, 0, False))
        for args in ((2, 14, NOW, 0, False), (3, 13, NOW, 0, False),
                     (3, 14, NOW, NOW-1, False), (3, 14, NOW, 0, True)):
            self.assertFalse(fn(None, *args))


class GroupIdText(str):
    def ToInt(self):
        return int(self)


class RetainedClaimAttendance(unittest.TestCase):
    """Lead review fix: a claim target stays raidable only while its group holds the claim."""
    def test_claim_target_rechecks_live_group_and_claim_before_attendance(self):
        from tests.unit.test_bases_raid import invoke
        state = NS(group=1, holds=True, asked=[])
        def holds(group, building):
            state.asked.append((group, building))
            return state.holds
        camp = NS(GroupId=GroupIdText('7'), Position=(0, 0, 0), AnchorKind='claim', ClaimBuildingId='b-1')
        owner = NS(GroupId=lambda actor: 'other')
        env = dict(HCCampModule=NS(Get=lambda: owner), HCEnabled=lambda: True,
                   GetGame=lambda: NS(IsServer=lambda: True, GetPlayers=lambda out: None),
                   HCGroupPeople=EArray, PlayerBase=NS(Cast=lambda value: value),
                   s_Config=NS(MaxPlayers=2, AttendanceRangeMeters=500, ObserverRangeMeters=500),
                   vector=NS(DistanceSq=lambda *args: 0),
                   HCObserverTransitionGate=NS(CanTransition=lambda *args: True),
                   HCBuildingClaim=NS(HCGet=lambda: NS(HCHoldsClaim=holds)),
                   HCGroupService=NS(Get=lambda: NS(HCClaimGroupState=lambda group: state.group)))
        check = lambda: invoke('HCUnattended', NS(), env, owner, camp, (0, 0, 0))
        self.assertTrue(check())
        self.assertEqual([(7, 'b-1')], state.asked)
        state.holds = False
        self.assertFalse(check())
        state.holds, state.group = True, 2
        self.assertFalse(check())
        env['HCGroupService'] = NS(Get=lambda: None)
        self.assertFalse(check())
