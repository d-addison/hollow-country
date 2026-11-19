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
// ToString/DistanceSq; EnString.c:199/240 Length/IndexOf;
// EnScript.c:380/385/407/448/470 Count/Clear/Insert/InsertAll/RemoveOrdered;
// EnSystem.c:397 FileExist; EnDebug.c:96 Print; EnMath.c:553 Min.
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
    int Version = 1;
    int ExpiryDays = 30; // long absence, provisional owner-tunable default
    // 25m = 1/40 of the approx 1000m vanilla network/gunshot scale. Presence
    // near the anchor renews absence; it does not assert measured containment.
    float VisitRadiusMeters = 1000.0 / 40.0;
    // Interaction follows vanilla reach; no new remote claim distance.
    float ActionReachMeters = UAMaxDistances.DEFAULT;
    // Identity precision, NOT gameplay reach; fixed across profiles/restarts.
    static const int POSITION_UNITS_PER_METER = 100;
    static const int ANGLE_UNITS_PER_DEGREE = 10;

    bool HCValid()
    {
        return Version == 1 && ExpiryDays >= 7 && ExpiryDays <= 365 && VisitRadiusMeters >= UAMaxDistances.DEFAULT && VisitRadiusMeters <= 1000.0 && ActionReachMeters == UAMaxDistances.DEFAULT;
    }
}

class HCBuildingClaim
{
    protected static ref HCBuildingClaim s_Instance;
    protected ref HCBuildingClaimConfig m_Config;
    protected HCCampModule m_Owner;
    protected HCCampData m_Data;
    protected ref HCBuildingClaimSave m_Save;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected bool m_Healthy;
    protected int m_LastUtc;
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
        if (s_Instance) { return s_Instance.m_Status; }
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
        // Groups starts before Camps in the existing registry. An unavailable
        // provider is an observed off state, never a false ready admission or
        // a background retry/expiry loop. Restart may admit it after repair.
        HCGroupService groups = HCGroupService.Get();
        if (!groups || !groups.HCClaimHealthy())
        {
            service.m_Status.HCPublish("off", "groups_unavailable");
            Print("[HC Plan] HC-17 claims=off state=off expiry_days=0 construction=off count=0 reason=groups_unavailable runtime=PENDING");
            return true;
        }
        service.m_Config = new HCBuildingClaimConfig;
        string path = "$profile:HollowCountry/building-claims-config.json";
        if (FileExist(path) && !HCGroupJson<HCBuildingClaimConfig>.Load(path, 4096, service.m_Config)) { service.HCFail(); return false; }
        service.m_LastUtc = HCWorldClock.UTC();
        if (service.m_LastUtc < 1 || service.m_LastUtc < data.SavedUtc || !service.m_Config || !service.m_Config.HCValid() || !HCCampStore.HCClaimsValid(data, service.m_LastUtc)) { service.HCFail(); return false; }
        service.m_Save = new HCBuildingClaimSave;
        service.m_Save.Owner = service;
        service.m_Healthy = true;
        HCSaveScheduler.HCRegister(service.m_Save);
        service.m_Status.HCPublish("ready", "claim_journal_loaded_native_acceptance_pending");
        Print(HCV2Admission.Line("BuildingClaims", true, "HC-17-N2-N7-N15", false));
        Print("[HC Plan] HC-17 claims=per-group state=ready expiry_days=" + service.m_Config.ExpiryDays.ToString() + " construction=off count=" + data.Claims.Count().ToString() + " legacy_camps=" + data.Camps.Count().ToString() + " runtime=PENDING");
        Print("[HC Plan] HC-17 state=refused reason=door_restart_and_heavy_infected_unobserved count=2 runtime=PENDING");
        return true;
    }

    void HCFail()
    {
        m_Healthy = false;
        m_Status.HCPublish("refused", "claim_config_clock_or_journal_fault");
        HCSaveScheduler.HCUnregister(m_Save);
        m_Observers.Clear();
        m_Examining = null;
        Print("[HC Plan] HC-17 claims=off state=refused reason=config_clock_or_journal_fault construction=off count=0 runtime=PENDING");
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
    bool HCApply(int groupId, bool manage, string buildingId, vector position, int now, bool release)
    {
        if (!HCReady(now) || groupId < 1 || !manage || buildingId == "") { return false; }
        int index = 0;
        foreach (HCBuildingClaimRecord row : m_Data.Claims)
        {
            if (row.GroupId == groupId || row.BuildingId == buildingId)
            {
                if (!release || row.GroupId != groupId || row.BuildingId != buildingId) { return false; }
                m_Data.Claims.RemoveOrdered(index);
                return HCCommit(now);
            }
            index++;
        }
        if (release || m_Data.Claims.Count() >= HCAILimits.Get().MaxCamps) { return false; }
        HCBuildingClaimRecord claim = new HCBuildingClaimRecord;
        claim.GroupId = groupId;
        claim.BuildingId = buildingId;
        claim.Position = position;
        claim.ClaimedUtc = now;
        claim.LastVisitUtc = now;
        m_Data.Claims.Insert(claim);
        return HCCommit(now);
    }

    // -1 means unavailable/unhealthy ACL service, 0 confirmed disband, 1 exists.
    // Unknown ACL/rollback NEVER releases or renews a claim.
    bool HCShouldExpire(HCBuildingClaimRecord row, int now, int groupState)
    {
        if (!row || groupState < 0 || now < row.LastVisitUtc) { return false; }
        return groupState == 0 || now - row.LastVisitUtc >= m_Config.ExpiryDays * 86400;
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
        return GetGame().GetWorldName() + ":" + building.GetType() + ":" + HCQuantized(position[0], posUnits) + ":" + HCQuantized(position[1], posUnits) + ":" + HCQuantized(position[2], posUnits) + ":" + HCQuantized(angles[0], angleUnits) + ":" + HCQuantized(angles[1], angleUnits) + ":" + HCQuantized(angles[2], angleUnits);
    }

    bool HCRequest(PlayerBase player, ActionTarget target, bool release)
    {
        if (!GetGame().IsServer() || !HCActor(player) || !target || target.GetParent()) { return false; }
        Building building = Building.Cast(target.GetObject());
        if (!building) { return false; }
        int door = building.GetDoorIndex(target.GetComponentIndex());
        if (!HCDoor(building, door)) { return false; }
        if (vector.DistanceSq(player.GetPosition(), building.GetDoorSoundPos(door)) > m_Config.ActionReachMeters * m_Config.ActionReachMeters) { return false; }
        HCGroupService groups = HCGroupService.Get();
        if (!groups) { return false; }
        // Re-read authenticated live peer and current manager role at completion.
        int groupId = groups.HCClaimActorGroup(player, true);
        return HCApply(groupId, true, HCIdentity(building), building.GetPosition(), HCWorldClock.UTC(), release);
    }

    // Called only by owner tick; one retained claim cursor, bounded snapshots.
    void HCStep(float deltaTime)
    {
        if (!m_Healthy || !(deltaTime > 0)) { return; }
        m_Elapsed += Math.Min(deltaTime, 5);
        if (m_Elapsed < 5) { return; }
        m_Elapsed = 0;
        int now = HCWorldClock.UTC();
        if (!HCReady(now)) { return; }
        HCGroupService groups = HCGroupService.Get();
        if (!groups || !groups.HCClaimHealthy() || m_Data.Claims.Count() == 0) { return; }
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
        if (groupState == 1 && m_VisitObservedUtc > m_Examining.LastVisitUtc)
        {
            m_Examining.LastVisitUtc = m_VisitObservedUtc;
            m_Save.HCDirty = true;
        }
        bool expired = HCShouldExpire(m_Examining, now, groupState);
        m_Examining = null;
        m_Observers.Clear();
        if (expired)
        {
            m_Data.Claims.RemoveOrdered(m_Cursor);
            // Release metadata only. Never enumerate/delete/unlock containers
            // or doors, and never restore an expired claim on a failed write.
            if (!HCCommit(now)) { return; }
        }
        else { m_Cursor++; }
    }

    bool HCCheckpoint()
    {
        return HCCommit(HCWorldClock.UTC());
    }

    static void HCStop()
    {
        if (!s_Instance) { return; }
        if (s_Instance.m_Healthy) { HCSaveScheduler.HCFlush(s_Instance.m_Save); }
        HCSaveScheduler.HCUnregister(s_Instance.m_Save);
        s_Instance.m_Observers.Clear();
        s_Instance.m_Examining = null;
        s_Instance.m_Healthy = false;
        s_Instance.m_Status.HCPublish("off", "claim_owner_stopped");
        s_Instance = null;
    }
}

class HCBuildingClaimSave : HCSaveJob
{
    HCBuildingClaim Owner;
    override string HCName() { return "BuildingClaimVisits"; }
    override bool HCWrite() { return Owner && Owner.HCCheckpoint(); }
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
    int HCClaimActorGroup(PlayerBase player, bool manager)
    {
        if (!HCClaimHealthy() || !player || !player.GetIdentity()) { return 0; }
        HCGroupPeer peer = Peer(player.GetIdentity().GetId());
        if (!Live(peer) || peer.Player != player) { return 0; }
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, peer.Id);
        if (!group || (manager && HCGroupRules.Role(group, peer.Id) < 1)) { return 0; }
        return group.Id;
    }
}
