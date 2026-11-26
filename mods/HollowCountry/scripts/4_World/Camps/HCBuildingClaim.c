// HC-17 / #151. Source implementation; runtime acceptance pending.
// Native evidence, relative to scripts-1.30.164289:
// 3_Game/Entities/Building.c:28/31/73/193 door index/count/sound position/
// compatibility; :55/67/70 native locked/lock/unlock semantics; :312 GetDoorInfo. We NEVER call the lock
// setters: native lockpicks retain durability, tool admission and breakability.
// 3_Game/Entities/Object.c:215/287/305/467/517 deletion/position/orientation/type/alive;
// 3_Game/Global/Game.c:914/934/1120 tick/world/server; gameplay.c:368 GetId;
// 3_Game/Entities/Man.c:21 GetIdentity;
// 4_World/Entities/ManBase/PlayerBase.c:2219/3925 restrained/unconscious;
// 4_World/Entities/DayZPlayerImplement.c:468 IsInVehicle; 1_Core/proto/EnMath.c:413 Round; EnConvert.c:30/210
// int/float ToString/DistanceSq (EnConvert.c:30/115/210); EnString.c:199/240 Length/IndexOf;
// EnScript.c:380/385/407/448/470 Count/Clear/Insert/InsertAll/RemoveOrdered;
// EnSystem.c:397 FileExist; EnDebug.c:96 Print; EnMath.c:553 Min.
// EnScript.c:869/902/906 map Get/Set/Remove (transient online baselines only).
// 4_World/Classes/UserActionsComponent/Actions/ActionConstants.c:111-114
// UAMaxDistances.DEFAULT; 3_Game/Enums/EBuildingLockTypes.c:10 LOCKPICK.
// 1_Core/proto/EnScript.c:94 Cast; 3_Game/gameplay.c:636 GetGame.
// 4_World/Entities/Building/Bunker.c:1/47/67 special opening/lock refusal;
// Entities/ItemBase/ContainerLocked.c:1 protected container class. HC-8 owns
// heavy pressure on ordinary native locks; claims never override its refusals.
// IO: HCCampStore + HCV2ThreatStore verified intent/backup/copy/readback.
// No engine entity store override, inventory serialization or lock replay.
class HCBuildingClaimConfig
{
    static const int DEFAULT_VERSION = 1;
    static const int DEFAULT_EXPIRY_DAYS = 30;
    static const float DEFAULT_VISIT_RADIUS_METERS = 25.0; // 1000m / 40
    // UAMaxDistances.DEFAULT = 2.0 in the installed 1.30 scripts; literal for native static initialization.
    static const float DEFAULT_ACTION_REACH_METERS = 2.0;
    int Version = DEFAULT_VERSION;
    int ExpiryDays = DEFAULT_EXPIRY_DAYS; // provisional owner-tunable default
    // 25m = 1/40 of the approx 1000m vanilla network/gunshot scale. Presence
    // near the anchor renews absence; it does not assert measured containment.
    float VisitRadiusMeters = DEFAULT_VISIT_RADIUS_METERS;
    // Interaction follows vanilla reach; no new remote claim distance.
    float ActionReachMeters = DEFAULT_ACTION_REACH_METERS;
    // Identity precision, NOT gameplay reach; fixed across profiles/restarts.
    static const int POSITION_UNITS_PER_METER = 100;
    static const int ANGLE_UNITS_PER_DEGREE = 10;

    bool HCValid()
    {
        // Native partial JSON leaves scalar fields at zero. Zero is absent;
        // explicit nonzero values still pass through the strict bounds below.
        if (Version == 0) { Version = DEFAULT_VERSION; Print("[HC Plan] HC-17 policy Version absent; default " + DEFAULT_VERSION.ToString()); }
        if (ExpiryDays == 0) { ExpiryDays = DEFAULT_EXPIRY_DAYS; Print("[HC Plan] HC-17 policy ExpiryDays absent; default " + DEFAULT_EXPIRY_DAYS.ToString()); }
        if (VisitRadiusMeters == 0) { VisitRadiusMeters = DEFAULT_VISIT_RADIUS_METERS; Print("[HC Plan] HC-17 policy VisitRadiusMeters absent; default " + DEFAULT_VISIT_RADIUS_METERS.ToString()); }
        if (ActionReachMeters == 0) { ActionReachMeters = DEFAULT_ACTION_REACH_METERS; Print("[HC Plan] HC-17 policy ActionReachMeters absent; default " + DEFAULT_ACTION_REACH_METERS.ToString()); }
        return Version == 1 && ExpiryDays >= 7 && ExpiryDays <= 365 && VisitRadiusMeters >= UAMaxDistances.DEFAULT && VisitRadiusMeters <= 1000.0 && ActionReachMeters == UAMaxDistances.DEFAULT;
    }
}

class HCBuildingClaim
{
    protected static ref HCBuildingClaim s_Instance;
    protected ref HCBuildingClaimConfig m_Config;
    protected HCCampModule m_Owner;
    protected HCCampData m_Data;
    protected HCSaveJob m_Save;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected bool m_Healthy;
    protected bool m_OperatorDisabled;
    protected int m_LastUtc;
    protected int m_OnlineSeconds;
    protected ref map<string, int> m_LastSteps = new map<string, int>;
    protected int m_Cursor;
    protected int m_ObserverCursor;
    protected HCBuildingClaimRecord m_Examining;
    protected ref array<Man> m_Observers = new array<Man>;
    protected int m_VisitObservedUtc;
    protected float m_Elapsed;

    static HCBuildingClaim HCGet()
    {
        if (s_Instance && s_Instance.m_Healthy) { return s_Instance; }
        return null;
    }
    static HCOperationalStatus HCObservedStatus()
    {
        if (s_Instance)
        {
            if (s_Instance.m_Healthy)
            {
                HCModuleReadiness.HCDerive(s_Instance.m_Status, s_Instance.m_Healthy, "", "", "claim_journal_loaded_native_acceptance_pending");
            }
            return s_Instance.m_Status;
        }
        HCOperationalStatus status = new HCOperationalStatus;
        status.HCPublish("off", "claim_owner_not_running");
        return status;
    }

    // Lead calls AFTER the camp owner is running, with the SAME loaded DTO.
    // No separate module/registry entry or hidden loop. Disabled Camps/Groups
    // must not call this start seam. Config reads are startup-only and bounded.
    static bool HCStart(HCCampModule owner, HCCampData data)
    {
        if (!GetGame() || !GetGame().IsServer() || !owner || !data || s_Instance) { return false; }
        HCBuildingClaim service = new HCBuildingClaim;
        s_Instance = service;
        service.m_Owner = owner;
        service.m_Data = data;
        if (FileExist("$profile:HollowCountry/acceptance/building_claims.disable"))
        {
            service.m_OperatorDisabled = true;
            service.m_Status.HCPublish("off", "building_claims_operator_disabled");
            Print("[HC Plan] HC-17 claims=off reason=building_claims_operator_disabled construction=off construction_scope=claim_aware native_construction=on runtime=PENDING");
            return true;
        }
        // Groups starts before Camps in the existing registry. An unavailable
        // provider is an observed off state, never a false ready admission or
        // a background retry/expiry loop. Restart may admit it after repair.
        HCGroupService groups = HCGroupService.Get();
        if (!groups || !groups.HCClaimHealthy())
        {
            service.m_Status.HCPublish("off", "groups_unavailable");
            Print("[HC Plan] HC-17 claims=off state=off expiry_days=0 construction=off construction_scope=claim_aware native_construction=on kits=fence,watchtower,flag,shelter ai_fortified=0 ai_provider=ExpansionAI count=0 reason=groups_unavailable runtime=PENDING");
            return true;
        }
        service.m_Config = new HCBuildingClaimConfig;
        string path = "$profile:HollowCountry/building-claims-config.json";
        if (FileExist(path) && !HCGroupJson<HCBuildingClaimConfig>.Load(path, 4096, service.m_Config)) { service.HCFail(); return false; }
        service.m_LastUtc = HCWorldClock.UTC();
        if (service.m_LastUtc < 1 || service.m_LastUtc < data.SavedUtc || !service.m_Config || !service.m_Config.HCValid() || !HCCampStore.HCClaimsValid(data, service.m_LastUtc, service.m_Config.ExpiryDays)) { service.HCFail(); return false; }
        service.m_Save = owner.HCCheckpointJob();
        service.m_Healthy = true;
        Print("[HC ClaimTargets] admitted schema=2 provenance=claim cooldowns=independent runtime=PENDING");
        HCModuleReadiness.HCDerive(service.m_Status, service.m_Healthy, "", "", "claim_journal_loaded_native_acceptance_pending");
        Print(HCV2Admission.Line("BuildingClaims", true, "HC-17-N2-N7-N15", false) + " runtime=PENDING");
        Print("[HC Plan] HC-17 claims=per-group state=" + service.m_Status.HCState() + " expiry_days=" + service.m_Config.ExpiryDays.ToString() + " construction=on construction_scope=claim_aware native_construction=on kits=fence,watchtower,flag,shelter ai_fortified=0 ai_provider=ExpansionAI count=" + data.Claims.Count().ToString() + " legacy_camps=" + data.Camps.Count().ToString() + " runtime=PENDING");
        Print("[HC Plan] HC-17 expiry=online_absence window_days=" + service.m_Config.ExpiryDays.ToString() + " runtime=PENDING");
        Print("[HC Plan] HC-17 locks=group_native_lockpick unlock=vanilla raiding=vanilla restart=native runtime=PENDING");
        return true;
    }

    void HCFail()
    {
        m_Healthy = false;
        m_Status.HCPublish("refused", "claim_config_clock_or_journal_fault");
        m_Observers.Clear();
        m_Examining = null;
        Print("[HC Plan] HC-17 claims=off state=refused reason=config_clock_or_journal_fault construction=off construction_scope=claim_aware native_construction=on kits=fence,watchtower,flag,shelter ai_fortified=0 ai_provider=ExpansionAI count=0 runtime=PENDING");
    }

    bool HCReady(int now)
    {
        if (!m_Healthy) { return false; }
        if (now < 1 || now < m_LastUtc) { HCFail(); return false; }
        m_LastUtc = now;
        return true;
    }

    // Barriers remain synchronous. An uncertain write disables both this
    // service and the owning camp module; never roll back/replay/refund items.
    bool HCCommit(int now)
    {
        if (!HCReady(now) || !m_Owner || !m_Owner.Commit(now)) { HCFail(); return false; }
        m_Save.HCDirty = false;
        return true;
    }

    // Trusted server-only input from HCRequest. No client-supplied group/key.
    // Empty result means success; all refusal text is authored/server-only.
    string HCApply(int groupId, bool manage, string buildingId, vector position, int now, bool release)
    {
        if (!HCReady(now)) { return "Claim service unavailable."; }
        if (groupId < 1 || !manage) { return "Only a group owner or officer can claim or release a building."; }
        if (buildingId == "") { return "Claim service unavailable."; }
        int index = 0;
        foreach (HCBuildingClaimRecord row : m_Data.Claims)
        {
            if (row.BuildingId == buildingId && row.GroupId != groupId) { return "Building already claimed by another group."; }
            if (row.GroupId == groupId)
            {
                if (!release) { return "Your group already claims a building."; }
                if (row.BuildingId != buildingId) { return "Your group's claim is on another building."; }
                m_LastSteps.Remove(row.BuildingId);
                m_Data.Claims.RemoveOrdered(index);
                if (!HCCommit(now)) { return "Claim persistence fault."; }
                return "";
            }
            index++;
        }
        if (release) { return "Your group holds no building claim."; }
        if (m_Data.Claims.Count() >= HCAILimits.Get().MaxCamps) { return "Claim limit reached."; }
        HCBuildingClaimRecord claim = new HCBuildingClaimRecord;
        claim.GroupId = groupId;
        claim.BuildingId = buildingId;
        claim.Position = position;
        claim.ClaimedUtc = now;
        claim.LastVisitUtc = now;
        m_LastSteps.Set(buildingId, m_OnlineSeconds);
        m_Data.Claims.Insert(claim);
        if (!HCCommit(now)) { return "Claim persistence fault."; }
        return "";
    }

    // -1 means unavailable/unhealthy ACL service, 0 confirmed disband, 1 exists.
    // Unknown ACL/rollback NEVER releases or renews a claim.
    bool HCShouldExpire(HCBuildingClaimRecord row, int now, int groupState)
    {
        if (!row || groupState < 0 || now < row.LastVisitUtc) { return false; }
        if (groupState == 0) { return true; }
        return row.AbsentSeconds >= m_Config.ExpiryDays * 86400;
    }

    void HCAccumulateAbsence(HCBuildingClaimRecord row, int groupState)
    {
        int previous = m_LastSteps.Get(row.BuildingId);
        m_LastSteps.Set(row.BuildingId, m_OnlineSeconds);
        if (groupState != 1) { return; }
        // At most two 5s slices per claim (32 observers, 40 work units).
        // Credit is bounded to one full walk interval even after stalled work.
        int creditCap = 10 * HCAILimits.Get().MaxCamps;
        int credit = Math.Min(m_OnlineSeconds - previous, creditCap);
        if (credit <= 0) { return; }
        row.AbsentSeconds = Math.Min(row.AbsentSeconds + credit, m_Config.ExpiryDays * 86400);
        m_Owner.HCRequestCheckpoint(HCWorldClock.UTC(), false);
    }

    static bool HCActor(PlayerBase player)
    {
        return player && player.GetIdentity() && player.IsAlive() && !player.IsPendingDeletion() && !player.IsUnconscious() && !player.IsRestrained() && !player.IsInVehicle();
    }

    // A native Land_ building with an observed compatible door; ancestry alone
    // is not enterability evidence. No area scan or invented bounds/inside API.
    static bool HCDoor(Building building, int door)
    {
        if (!building || building.IsPendingDeletion() || building.GetType().IndexOf("Land_") != 0 || !HCGroupRules.PositionValid(building.GetPosition())) { return false; }
        if (Bunker.Cast(building) || ContainerLockedBase.Cast(building)) { return false; }
        // #239: static car and vehicle wrecks and ruins carry lockpick doors but are not buildings to claim.
        if (building.GetType().IndexOf("Wreck") >= 0 || building.GetType().IndexOf("Ruin") >= 0) { return false; }
        if (door < 0 || door >= building.GetDoorCount() || !building.GetDoorInfo(door)) { return false; }
        return (building.GetLockCompatibilityType(door) & (1 << EBuildingLockType.LOCKPICK)) != 0;
    }

    static string HCQuantized(float value, int units)
    {
        int quantized = Math.Round(value * units);
        return quantized.ToString();
    }

    static string HCIdentity(Building building)
    {
        vector position = building.GetPosition();
        vector angles = building.GetOrientation();
        int posUnits = HCBuildingClaimConfig.POSITION_UNITS_PER_METER;
        int angleUnits = HCBuildingClaimConfig.ANGLE_UNITS_PER_DEGREE;
        string id = GetGame().GetWorldName() + ":" + building.GetType() + ":" + HCQuantized(position[0], posUnits);
        id = id + ":" + HCQuantized(position[1], posUnits) + ":" + HCQuantized(position[2], posUnits);
        id = id + ":" + HCQuantized(angles[0], angleUnits) + ":" + HCQuantized(angles[1], angleUnits) + ":" + HCQuantized(angles[2], angleUnits);
        return id;
    }

    bool HCHoldsClaim(int groupId, string buildingId)
    {
        foreach (HCBuildingClaimRecord row : m_Data.Claims)
        {
            if (row.GroupId == groupId && row.BuildingId == buildingId) { return true; }
        }
        return false;
    }

    // #252: completion-only, bounded ownership admission; no lock writes.
    // Native Building.c:31/55 GetDoorCount/IsDoorLocked; Object.c:370/874
    // GetCollisionBox/WorldToModel (scripts-1.30.164289).
    string HCFirstClaimRefusal(Building building, int groupId)
    {
        if (groupId < 1) { return "Only a group owner or officer can claim a building."; }
        int doors = building.GetDoorCount();
        if (doors < 1 || doors > 128) { return "Building door check unavailable."; }
        for (int doorIndex = 0; doorIndex < doors; doorIndex++)
        {
            if (building.IsDoorLocked(doorIndex)) { return "Cannot claim a building with a locked door."; }
        }
        if (!m_Data.Camps || m_Data.Camps.Count() > HCAILimits.Get().MaxCamps) { return "Camp ownership check unavailable."; }
        vector bounds[2];
        if (!building.GetCollisionBox(bounds) || bounds[0][0] > bounds[1][0] || bounds[0][1] > bounds[1][1] || bounds[0][2] > bounds[1][2]) { return "Building bounds check unavailable."; }
        string actorGroup = groupId.ToString();
        foreach (HCCampRecord camp : m_Data.Camps)
        {
            if (!camp) { return "Camp ownership check unavailable."; }
            if (camp.GroupId == actorGroup) { continue; }
            // Same 12m hearth envelope as HCCampScan.Read. Test against the
            // whole building's local box, not its potentially distant origin.
            vector campLocal = building.WorldToModel(camp.Position);
            vector nearest = campLocal;
            for (int axis = 0; axis < 3; axis++)
            {
                if (nearest[axis] < bounds[0][axis]) { nearest[axis] = bounds[0][axis]; }
                if (nearest[axis] > bounds[1][axis]) { nearest[axis] = bounds[1][axis]; }
            }
            if (vector.DistanceSq(campLocal, nearest) <= 144)
            {
                return "Cannot claim a building overlapping another group's hearth camp.";
            }
        }
        return "";
    }

    // #151: ownership controls who may SET a native lock. Unlock/forced entry
    // remain entirely native, including tool damage and broken-door state.
    // No periodic lock replay: a breached door stays breached until relocked
    // physically by a member with a vanilla tool. No collision/door override.
    bool HCCanLock(int groupId, string buildingId)
    {
        if (!m_Healthy) { return false; }
        array<ref HCBuildingClaimRecord> lockClaims = m_Data.Claims;
        foreach (HCBuildingClaimRecord lockClaim : lockClaims)
        {
            if (lockClaim.BuildingId == buildingId) { return groupId > 0 && lockClaim.GroupId == groupId; }
        }
        return true;
    }

    static bool HCLockAllowed(PlayerBase player, ActionTarget target)
    {
        if (!GetGame() || !GetGame().IsServer()) { return true; } // Client preview is vanilla.
        if (!s_Instance || s_Instance.m_OperatorDisabled) { return true; }
        if (!s_Instance.m_Healthy || !HCActor(player) || !target) { return false; }
        Building lockBuilding = Building.Cast(target.GetObject());
        if (!lockBuilding) { return false; }
        // Nonclaimable native targets retain their own action restrictions.
        int lockDoor = lockBuilding.GetDoorIndex(target.GetComponentIndex());
        if (!HCDoor(lockBuilding, lockDoor)) { return true; }
        HCGroupService lockGroups = HCGroupService.Get();
        if (!lockGroups || !lockGroups.HCClaimHealthy()) { return false; }
        int lockGroupId = lockGroups.HCClaimActorGroup(player, false);
        return s_Instance.HCCanLock(lockGroupId, HCIdentity(lockBuilding));
    }

    // The same bounded 25m claim envelope used for visits protects new native
    // construction at the building. This grants no door immunity and never
    // intercepts dismantling/raiding. Client previews remain native; commit ACL
    // is server-authoritative, including a membership change mid-action.
    static bool HCConstructionAllowed(PlayerBase player, vector position)
    {
        if (!GetGame() || !GetGame().IsServer()) { return true; }
        if (!s_Instance || s_Instance.m_OperatorDisabled) { return true; }
        if (!s_Instance.m_Healthy || !HCActor(player)) { return false; }
        HCGroupService groups = HCGroupService.Get();
        if (!groups || !groups.HCClaimHealthy()) { return false; }
        int groupId = groups.HCClaimActorGroup(player, false);
        float radius = s_Instance.m_Config.VisitRadiusMeters;
        foreach (HCBuildingClaimRecord claim : s_Instance.m_Data.Claims)
        {
            if (vector.DistanceSq(position, claim.Position) <= radius * radius && claim.GroupId != groupId) { return false; }
        }
        return true;
    }

    // True when a recorded claim envelope (the same visit radius) covers the
    // position. Read only; lets fortification kits tell claimed from unclaimed ground.
    static bool HCClaimCoversAt(vector position)
    {
        if (!s_Instance || s_Instance.m_OperatorDisabled || !s_Instance.m_Healthy) { return false; }
        float radius = s_Instance.m_Config.VisitRadiusMeters;
        foreach (HCBuildingClaimRecord claim : s_Instance.m_Data.Claims)
        {
            if (vector.DistanceSq(position, claim.Position) <= radius * radius) { return true; }
        }
        return false;
    }

    // AI cannot fortify a player's claimed building or hearth camp. There is
    // no implicit AI group ownership and no mutation of native doors/locks.
    static bool HCAIFortificationAllowed(vector position)
    {
        if (!s_Instance || s_Instance.m_OperatorDisabled) { return true; }
        if (!s_Instance.m_Healthy) { return false; }
        float radius = s_Instance.m_Config.VisitRadiusMeters;
        foreach (HCBuildingClaimRecord claim : s_Instance.m_Data.Claims)
        {
            if (vector.DistanceSq(position, claim.Position) <= radius * radius) { return false; }
        }
        foreach (HCCampRecord camp : s_Instance.m_Data.Camps)
        {
            if (vector.DistanceSq(position, camp.Position) <= 625) { return false; }
        }
        return true;
    }

    string HCRequest(PlayerBase player, ActionTarget target, bool release)
    {
        if (!m_Healthy || !GetGame() || !GetGame().IsServer()) { return "Claim service unavailable."; }
        if (!HCActor(player)) { return "Group access changed."; }
        if (!target || target.GetParent()) { return "Use an ordinary building door."; }
        Building building = Building.Cast(target.GetObject());
        if (!building) { return "Use an ordinary building door."; }
        int door = building.GetDoorIndex(target.GetComponentIndex());
        if (!HCDoor(building, door)) { return "Use an ordinary building door."; }
        if (vector.DistanceSq(player.GetPosition(), building.GetDoorSoundPos(door)) > m_Config.ActionReachMeters * m_Config.ActionReachMeters) { return "Move within door reach."; }
        HCGroupService groups = HCGroupService.Get();
        if (!groups || !groups.HCClaimHealthy()) { return "Claim service unavailable."; }
        // Re-read authenticated live peer and manager role at completion.
        int groupId = groups.HCClaimActorGroup(player, true);
        if (!release)
        {
            string refusal = HCFirstClaimRefusal(building, groupId);
            if (refusal != "") { return refusal; }
        }
        string result = HCApply(groupId, true, HCIdentity(building), building.GetPosition(), HCWorldClock.UTC(), release);
        if (result == "")
        {
            // The actor's prompt flips at once; other members follow within one 5 s slice.
            HCBuildingClaimHint requestHints = HCBuildingClaimHint.Get();
            requestHints.HCIndex(m_Data.Claims);
            requestHints.HCSend(player, groups, m_OnlineSeconds, true);
        }
        return result;
    }

    // Called only by owner tick; one retained claim cursor, bounded snapshots.
    void HCStep(float deltaTime)
    {
        if (!m_Healthy || !(deltaTime > 0)) { return; }
        m_Elapsed += Math.Min(deltaTime, 5);
        if (m_Elapsed < 5) { return; }
        // Tick delta is online-only; a hitch contributes at most 5 seconds.
        // Preserve fractional seconds without persisting a process clock.
        int elapsedSeconds = m_Elapsed;
        m_Elapsed -= elapsedSeconds;
        m_OnlineSeconds += elapsedSeconds;
        int now = HCWorldClock.UTC();
        if (!HCReady(now)) { return; }
        HCGroupService groups = HCGroupService.Get();
        if (!groups || !groups.HCClaimHealthy()) { return; }
        HCHintRound(groups);
        // Preserve the fixed checkpoint image; online time still advances so
        // the existing capped absence credit accounts for the paused walk.
        if (m_Owner.HCCheckpointInFlight()) { return; }
        if (m_Data.Claims.Count() == 0) { return; }
        m_Units.HCReset(40);
        m_Work.HCReset(40);
        if (!m_Examining)
        {
            array<Man> people = HCPerfPlayers.HCGet();
            if (!people || people.Count() > 32) { return; }
            if (m_Cursor >= m_Data.Claims.Count()) { m_Cursor = 0; }
            m_Examining = m_Data.Claims[m_Cursor];
            m_Observers.Clear();
            m_Observers.InsertAll(people);
            m_ObserverCursor = 0;
            m_VisitObservedUtc = 0;
            m_Units.HCCharge(people.Count());
        }
        // Actions may release the row between slices. Never save an orphan
        // visit or let it release a newly inserted row at the same array index.
        m_Cursor = m_Data.Claims.Find(m_Examining);
        if (m_Cursor < 0)
        {
            m_Cursor = 0;
            m_Examining = null;
            m_Observers.Clear();
            return;
        }
        while (m_ObserverCursor < m_Observers.Count())
        {
            if (!m_Work.HCContinue() || !m_Units.HCTake(1)) { return; }
            PlayerBase player = PlayerBase.Cast(m_Observers[m_ObserverCursor]);
            m_ObserverCursor++;
            if (!HCActor(player)) { continue; }
            if (vector.DistanceSq(player.GetPosition(), m_Examining.Position) <= m_Config.VisitRadiusMeters * m_Config.VisitRadiusMeters && groups.HCClaimActorGroup(player, false) == m_Examining.GroupId) { m_VisitObservedUtc = now; }
        }
        int groupState = groups.HCClaimGroupState(m_Examining.GroupId);
        HCAccumulateAbsence(m_Examining, groupState);
        if (groupState == 1 && m_VisitObservedUtc > 0)
        {
            m_Examining.LastVisitUtc = m_VisitObservedUtc;
            m_Examining.AbsentSeconds = 0;
            m_Owner.HCRequestCheckpoint(HCWorldClock.UTC(), false);
        }
        bool expired = HCShouldExpire(m_Examining, now, groupState);
        if (expired) { m_LastSteps.Remove(m_Examining.BuildingId); }
        m_Examining = null;
        m_Observers.Clear();
        if (expired)
        {
            m_Data.Claims.RemoveOrdered(m_Cursor);
            // Release metadata only. Never enumerate/delete/unlock containers
            // or doors, and never restore an expired claim on a failed write.
            if (m_Owner.HCRequestCheckpoint(now) < 1) { HCFail(); return; }
        }
        else { m_Cursor++; }
    }

    // #239: tell each online player's own client whether it may claim and which
    // building its group holds. Same 5 s slice and 32-player cap as the visit walk.
    protected void HCHintRound(HCGroupService groups)
    {
        array<Man> people = HCPerfPlayers.HCGet();
        if (!people || people.Count() > 32) { return; }
        HCBuildingClaimHint hints = HCBuildingClaimHint.Get();
        hints.HCPrune(people);
        hints.HCIndex(m_Data.Claims);
        foreach (Man person : people)
        {
            hints.HCSend(PlayerBase.Cast(person), groups, m_OnlineSeconds, false);
        }
    }

    int HCStepCheckpoint()
    {
        int now = HCWorldClock.UTC();
        if (!HCReady(now) || !m_Owner) { HCFail(); return HCSaveJob.STEP_FAILED; }
        int result = m_Owner.HCStepCheckpoint(now);
        if (result == HCSaveJob.STEP_FAILED) { HCFail(); }
        return result;
    }

    bool HCCheckpoint()
    {
        return HCCommit(HCWorldClock.UTC());
    }

    static void HCStop()
    {
        if (!s_Instance) { return; }
        if (s_Instance.m_Healthy) { HCSaveScheduler.HCFlush(s_Instance.m_Save); }
        s_Instance.m_Observers.Clear();
        s_Instance.m_Examining = null;
        s_Instance.m_Healthy = false;
        s_Instance.m_Status.HCPublish("off", "claim_owner_stopped");
        s_Instance = null;
    }
}

// Same layer, narrow server-only bridge. No group journal/ACL/RPC changes.
modded class HCGroupService
{
    bool HCClaimHealthy() { return m_Healthy && m_State != null; }
    int HCClaimGroupState(int groupId)
    {
        if (!HCClaimHealthy()) { return -1; }
        if (HCGroupRules.ById(m_State, groupId)) { return 1; }
        return 0;
    }
    // Native scripts-1.30.164289: 3_Game/Global/Game.c:945 GetPlayers;
    // Entities/Man.c:21 GetIdentity; gameplay.c:368 GetId. Entry-local only.
    int HCClaimActorGroup(PlayerBase player, bool manager, array<Man> hcRoster = null)
    {
        if (!hcRoster)
        {
            hcRoster = new array<Man>;
            GetGame().GetPlayers(hcRoster);
        }
        if (!HCClaimHealthy() || !player || !player.GetIdentity()) { return 0; }
        HCGroupPeer peer = Peer(player.GetIdentity().GetId());
        PlayerBase hcPeerPlayer;
        if (peer) hcPeerPlayer = HCPlayerOf(hcRoster, peer.Id);
        if (!Live(peer, hcRoster) || hcPeerPlayer != player) { return 0; }
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, peer.Id);
        if (!group || (manager && HCGroupRules.Role(group, peer.Id) < 1)) { return 0; }
        return group.Id;
    }
}

// Native evidence scripts-1.30.164289:
// 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionLockDoors.c:
// 31-63 ActionCondition checks native reach/tool/door compatibility;
// 62-74 LockDoor, 76-81 OnFinishProgressServer locks and damages the tool.
// ActionUnlockDoors.c:31-63/76-85 stays unmodified (vanilla raiding).
// ActionTargets.c:142/159 GetObject/GetComponentIndex;
// 3_Game/Global/Game.c:1120 IsServer; gameplay.c:636 GetGame.
modded class ActionLockDoors
{
    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        return super.ActionCondition(player, target, item) && HCBuildingClaim.HCLockAllowed(player, target);
    }

    override void OnFinishProgressServer(ActionData action_data)
    {
        if (!action_data) { return; }
        // Recheck the native condition as well as the current live group ACL.
        // A membership change during the animation must not acquire a lock.
        if (!ActionCondition(action_data.m_Player, action_data.m_Target, action_data.m_MainItem))
        {
            if (action_data.m_Player) { action_data.m_Player.MessageStatus("Door locking refused: group access or native door/tool condition changed."); }
            return;
        }
        super.OnFinishProgressServer(action_data);
    }
}
