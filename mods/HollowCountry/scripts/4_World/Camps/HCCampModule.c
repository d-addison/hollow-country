// LC-T412..416 / #105..109. Preference EnableCamps admits V2 by default;
// experiment verdicts are diagnostics, never claimed as observed/accepted.
// Native evidence ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/:
// 4_World/Entities/ItemBase/FireplaceBase.c:1760 StartFire(bool), :1951
// StopFire(FireplaceFireState), :1639 IsBurning; 3_Game/Entities/EntityAI.c:
// :905 EEInit, :946 EEDelete; 3_Game/Global/Game.c:945 GetPlayers, :1120
// IsServer; 3_Game/Entities/Object.c:215 IsPendingDeletion, :287 GetPosition,
// :467 GetType, :517 IsAlive; 3_Game/Entities/Man.c:21 GetIdentity;
// 3_Game/gameplay.c:368 PlayerIdentityBase.GetId; EnMath.c:553 Math.Min;
// 1_Core/proto/EnScript.c:470 array.RemoveOrdered.
// EnScript.c:94/380/385/394/407 Cast/count/clear/find/insert.
// 1_Core/proto/EnConvert.c:30 int.ToString, :210 vector.DistanceSq;
// 1_Core/proto/EnString.c:171 ToLower; 1_Core/proto/EnDebug.c:96 Print;
// 3_Game/Client/Notifications/NotificationSystem.c:125
// SendNotificationToPlayerExtended. Persistent native refs: HCCampScan header.
// Project APIs reused: HCGroupRules.FindGroup, HCGroupService.Peer/Live;
// HCWorldClock.UTC, HCWorldModule.Get, HCEscalationClock; HCCampStore.
class HCCampModule : HCModule
{
    protected static HCCampModule s_Instance;
    protected static ref array<FireplaceBase> s_Fires = new array<FireplaceBase>();
    protected static bool s_FireCapLogged;
    protected ref HCCampData m_Data;
    protected ref array<Man> m_Players = new array<Man>();
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCOperationalOwner m_TheftOwner;
    protected string m_TheftLine;
    protected bool m_Running;
    protected bool m_AdmissionPrinted;
    protected float m_Elapsed;
    protected int m_FireCursor;
    protected int m_CampCursor;
    protected int m_LastUtc;
    protected int m_LastSaved;
    protected ref HCCampScan m_ClaimSelectionScan;
    protected HCCampRecord m_ClaimSelectionTarget;
    protected int m_ClaimSelectionUtc;

    override string GetName() { return "Camps"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableCamps; }
    void HCCampModule() { m_Status.HCPublish("off", "camp_owner_not_running"); }
    override HCOperationalStatus HCGetOperationalStatus()
    {
        if (!m_Running) { return m_Status; }
        HCObserveTheft();
        return HCBuildingClaim.HCObservedStatus();
    }

    // CampTheft is a non-module contributor riding this owner's status hook,
    // which the shared server calls once at startup and on its 15 s refresh.
    protected void HCObserveTheft()
    {
        if (!m_TheftOwner) { m_TheftOwner = HCOperationalContributors.HCRegisterOwner("CampTheft"); }
        HCOperationalStatus theft = HCCampTheft.HCGetOperationalStatus();
        if (!theft || !GetGame()) { return; }
        if (m_TheftOwner) { m_TheftOwner.HCObserve(true, theft, GetGame().GetTickTime()); }
        string line = "[HC CampTheft] " + theft.HCState() + " reason=" + theft.HCReason();
        if (theft.HCState() == "ready") { line = "[HC CampTheft] ready"; }
        if (line == m_TheftLine) { return; }
        m_TheftLine = line;
        Print("" + line);
    }

    static HCCampModule Get()
    {
        if (s_Instance && s_Instance.m_Running) { return s_Instance; }
        return null;
    }

    static void Remember(FireplaceBase fire)
    {
        if (!GetGame() || !GetGame().IsServer() || !fire || s_Fires.Find(fire) >= 0) { return; }
        if (s_Fires.Count() >= 128)
        {
            if (!s_FireCapLogged) { Print("[HollowCountry] V2 camps fire candidate cap=128; extra fires ignored"); s_FireCapLogged = true; }
            return;
        }
        s_Fires.Insert(fire);
    }

    static void Forget(FireplaceBase fire)
    {
        int index = s_Fires.Find(fire);
        if (index >= 0) { s_Fires.RemoveOrdered(index); }
    }

    override void OnStart(HCSettings settings)
    {
        if (m_Running || !GetGame().IsServer() || !IsEnabled(settings)) { return; }
        HCBuildingClaim.HCStop(); // Clear a failed singleton before a fresh start.
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("Camps", true, "EXP-L7", HCV2Gates.Qualified("EXP-L7")));
            m_AdmissionPrinted = true;
        }
        m_LastUtc = HCWorldClock.UTC();
        m_Data = HCCampStore.Load(m_LastUtc);
        if (!m_Data) { Fail(); return; }
        m_LastSaved = m_LastUtc;
        m_Running = true;
        m_Status.HCPublish("ready", "camp_store_loaded_native_acceptance_pending");
        s_Instance = this;
        if (settings.EnableGroups)
        {
            if (!HCBuildingClaim.HCStart(this, m_Data)) { Print("[HC Plan] HC-17 claims=off reason=claims_start_refused fire_camps=running runtime=PENDING"); }
        }
        // One opt-out-aware CampTheft admission line, sampled once.
        HCCampTheft.HCEnabled();
        Print("[HollowCountry] V2 camps started camps=" + m_Data.Camps.Count().ToString() + " visitors=abstract probes=abstract mailbox=off; native acceptance pending");
    }

    protected void Fail()
    {
        HCBuildingClaim claims = HCBuildingClaim.HCGet();
        if (claims) { claims.HCFail(); }
        m_Running = false;
        m_Status.HCPublish("refused", "camp_clock_schema_or_persistence_fault");
        if (s_Instance == this) { s_Instance = null; }
        Print("[HollowCountry] V2 camps disabled: UTC/schema/world/persistence fault; preserve camps.json, .tmp and .bak");
    }

    bool Commit(int now)
    {
        if (!m_Running || now < m_LastUtc || !HCCampStore.Save(m_Data, now)) { Fail(); return false; }
        m_LastSaved = now;
        return true;
    }

    string GroupId(PlayerBase player)
    {
        HCGroupService groups = HCGroupService.Get();
        if (!groups || !player || !player.GetIdentity()) { return ""; }
        return groups.HCCampReadGroupId(player);
    }

    int NearMembers(HCCampRecord camp, float radius)
    {
        int count;
        foreach (Man person : m_Players)
        {
            PlayerBase player = PlayerBase.Cast(person);
            if (!player || !player.GetIdentity() || !player.IsAlive() || player.IsPendingDeletion()) { continue; }
            if (vector.DistanceSq(player.GetPosition(), camp.Position) <= radius * radius && GroupId(player) == camp.GroupId) { count++; }
        }
        return count;
    }

    void Tell(HCCampRecord camp, string authoredText)
    {
        // Cached online recipients, max 32, group ACL re-read for each send.
        foreach (Man person : m_Players)
        {
            PlayerBase player = PlayerBase.Cast(person);
            if (!player || !player.GetIdentity() || !player.IsAlive() || player.IsPendingDeletion() || GroupId(player) != camp.GroupId) { continue; }
            NotificationSystem.SendNotificationToPlayerExtended(player, 8, "Hollow Country camp", authoredText);
        }
    }

    void Fact(HCCampRecord camp, string kind, int severity)
    {
        HCWorldModule world = HCWorldModule.Get();
        if (!world) { return; }
        // Current catalog Name is the title-cased Id. NearestPlace returns Name,
        // despite AddFact requiring Id. Normalise for that read-only contract;
        // AddFact itself validates and rejects unknown future catalog names.
        string place = world.NearestPlace(camp.Position);
        place.ToLower();
        world.AddFact(kind, place, severity);
    }

    protected void Candidate(FireplaceBase fire, int now)
    {
        if (!fire || fire.IsPendingDeletion() || fire.GetHierarchyParent() || !fire.IsBurning()) { return; }
        vector position = fire.GetPosition();
        string selected;
        float best = 145;
        foreach (Man person : m_Players)
        {
            PlayerBase player = PlayerBase.Cast(person);
            if (!player || !player.IsAlive() || !player.GetIdentity()) { continue; }
            string group = GroupId(player);
            float distance = vector.DistanceSq(player.GetPosition(), position);
            if (group != "" && distance < best) { best = distance; selected = group; }
        }
        foreach (HCCampRecord known : m_Data.Camps)
        {
            // Existing camp keeps its binding even when all members are away.
            if (known.FireClass == fire.GetType() && vector.DistanceSq(known.Position, position) <= 1)
            {
                known.LastLit = now;
                return;
            }
            if (selected != "" && known.GroupId == selected) { return; }
        }
        if (selected == "" || m_Data.Camps.Count() >= HCAILimits.Get().MaxCamps) { return; }
        HCCampRecord camp = new HCCampRecord;
        camp.GroupId = selected;
        camp.Id = "camp-" + selected;
        camp.Position = position;
        camp.FireClass = fire.GetType();
        camp.FireRef = HCCampScan.RefOf(fire);
        // Fresh fires may have no persistent ID until native persistence runs.
        // Store a fixed camp anchor token; runtime rebind is class + <=1m.
        if (camp.FireRef == "") { camp.FireRef = camp.Id + "-hearth"; }
        camp.LastLit = now;
        m_Data.Camps.Insert(camp);
        if (!Commit(now)) { return; }
        Tell(camp, "Your group's fire is recognised as a camp. Nearby native structures determine its tier.");
        Print("[HollowCountry] V2 camps recognised camp=" + camp.Id + " tier=0");
    }

    protected FireplaceBase FireFor(HCCampRecord camp)
    {
        foreach (FireplaceBase fire : s_Fires)
        {
            if (fire && !fire.IsPendingDeletion() && !fire.GetHierarchyParent() && fire.GetType() == camp.FireClass && vector.DistanceSq(fire.GetPosition(), camp.Position) <= 1) { return fire; }
        }
        return null;
    }

    protected void StepCamp(HCCampRecord camp, int now)
    {
        int interval = 600;
        if (camp.ProbePhase > 0) { interval = 30; }
        if (camp.LastScan > 0 && now - camp.LastScan < interval) { return; }
        FireplaceBase fire = FireFor(camp);
        bool burning = fire && fire.IsBurning();
        HCCampScan scan = HCCampScan.Read(camp.Position, burning);
        if (!scan) { return; }
        camp.LastScan = now;
        if (burning) { camp.LastLit = now; }
        int previous = camp.Tier;
        int tier = HCCampTiers.Evaluate(fire != null, scan.Shelter, scan.Storage, scan.RaisedFlag, scan.Garden || scan.Traps >= 2, scan.Kitchen, scan.Walls, scan.Lights, scan.HasRadio);
        camp.Tier = HCCampTiers.Decayed(tier, now, camp.LastLit);
        camp.Flag = scan.Flag;
        camp.Members = scan.Items;
        if (!Commit(now)) { return; }
        if (previous != camp.Tier)
        {
            Tell(camp, "Camp tier is now " + camp.Tier.ToString() + ". Tiers change visits only.");
            Print("[HollowCountry] V2 camps tier camp=" + camp.Id + " from=" + previous.ToString() + " to=" + camp.Tier.ToString());
            if (camp.Tier == 3) { Fact(camp, "camp_settlement", 0); }
        }
        HCCampVisitors.Step(this, camp, scan, burning, now);
        if (!m_Running) { return; }
        HCCampMailbox.Step(this, camp, scan, now);
        if (!m_Running) { return; }
        string visitorReason;
        HCCampProbes.HCRequestVisitorParty(this, camp, scan, burning, now, visitorReason);
        if (!m_Running) { return; }
        HCCampProbes.Step(this, camp, scan, burning, now);
        if (!m_Running) { return; }
        HCCampTheft.Step(this, camp, scan, now);
    }

    // #212: one bounded index space for the normal cursor and admin selector.
    // Claims keep their own DTO reference, so provider cooldown writes enter
    // the SAME camp-store barrier. They never appear in hearth/respawn lists.
    int HCEncounterCount()
    {
        if (!m_Data || !m_Data.Camps || !m_Data.Claims) { return 0; }
        int cap = HCAILimits.Get().MaxCamps;
        if (m_Data.Camps.Count() > cap || m_Data.Claims.Count() > cap) { return 0; }
        if (!HCBuildingClaim.HCGet()) { return m_Data.Camps.Count(); }
        return m_Data.Camps.Count() + m_Data.Claims.Count();
    }

    HCCampRecord HCEncounterTarget(int index, int now)
    {
        if (index < 0 || index >= HCEncounterCount()) { return null; }
        if (index < m_Data.Camps.Count()) { return m_Data.Camps[index]; }
        HCBuildingClaimRecord row = m_Data.Claims[index - m_Data.Camps.Count()];
        if (!row || !HCCampStore.HCClaimTargetValid(row, now)) { return null; }
        HCGroupService groups = HCGroupService.Get();
        if (!groups || groups.HCClaimGroupState(row.GroupId) != 1) { return null; }
        if (now < row.ClaimedUtc) { return null; }
        int heldDays = (now - row.ClaimedUtc) / 86400;
        if (!HCCampProbes.Eligible(3, heldDays, now, 0, false)) { return null; }
        return row.Anchor;
    }

    protected HCBuildingClaimRecord HCClaimForTarget(HCCampRecord target)
    {
        if (!HCBuildingClaim.HCGet() || !m_Data || !m_Data.Claims) { return null; }
        array<ref HCBuildingClaimRecord> claims = m_Data.Claims;
        foreach (HCBuildingClaimRecord row : claims)
        {
            if (row.Anchor == target) { return row; }
        }
        return null;
    }

    // Native scripts-1.30.164289: Game.c:930 GetObjectsAtPosition3D;
    // Object.c:215/1219 IsPendingDeletion/IsRuined; EntityAI.c:1884
    // GetInventory; Systems/Inventory/Inventory.c:138 GetCargo;
    // Systems/Inventory/Cargo.c:28 GetItemCount. StorageItem/Read retain their
    // existing native evidence in HCCampScan.c. No inventory is moved or owned.
    // The existing raid source range/object cap bound physical storage evidence.
    // Admin selection is synchronous: reserve its bounded worst case once,
    // rather than starving later/nearer candidates after the first scan. Normal
    // ticks still inspect just one target. 128 is HCCampScan.Read's existing
    // cap (also StepCamp/admin work); the second scan uses config.MaxObjects.
    // Charging both prevents a lowered cargo cap undercounting the first scan.
    protected bool HCReserveClaimSelection(int count, out string reason)
    {
        reason = "CLAIM_SCAN_CONFIG_UNAVAILABLE";
        if (!HCBaseRaid.HCEnabled()) { return false; }
        HCBaseRaidConfig config = HCBaseRaid.HCConfig();
        if (!config) { return false; }
        reason = "CLAIM_SELECTION_WORK_BUDGET";
        int cost = count * (128 + config.MaxObjects + config.MaxPlayers);
        return HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_BASES, cost);
    }

    protected HCCampScan HCReadClaimScan(HCCampRecord target, out string reason, bool budgeted = false)
    {
        reason = "CLAIM_SCAN_CONFIG_UNAVAILABLE";
        if (!HCBaseRaid.HCEnabled()) { return null; }
        HCBaseRaidConfig config = HCBaseRaid.HCConfig();
        if (!config) { return null; }
        reason = "CLAIM_SCAN_WORK_BUDGET";
        if (!budgeted && !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_BASES, 128 + config.MaxObjects + config.MaxPlayers)) { return null; }
        HCCampScan scan = HCCampScan.Read(target.Position, false);
        reason = "CLAIM_SCAN_UNAVAILABLE";
        if (!scan) { return null; }
        array<Object> objects = new array<Object>;
        array<CargoBase> cargos = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(target.Position, config.SourceRangeMeters, objects, cargos);
        reason = "CLAIM_STORAGE_SCAN_CAP";
        if (objects.Count() > config.MaxObjects || cargos.Count() > config.MaxObjects) { return null; }
        // A container alone is insufficient: require real stored cargo. The
        // radius is an anchor-local policy, not a claim of building containment.
        scan.Storage = false;
        for (int objectIndex = 0; objectIndex < objects.Count(); objectIndex++)
        {
            ItemBase storage = ItemBase.Cast(objects[objectIndex]);
            if (!storage || storage.IsPendingDeletion() || storage.IsRuined() || !HCCampScan.StorageItem(storage)) { continue; }
            CargoBase cargo = storage.GetInventory().GetCargo();
            if (cargo && cargo.GetItemCount() > 0) { scan.Storage = true; break; }
        }
        reason = "";
        return scan;
    }

    protected bool HCRequestClaimArrival(HCCampRecord target, HCCampScan scan, int now, bool raid, out string reason)
    {
        reason = "CLAIM_ANCHOR_UNAVAILABLE";
        HCBuildingClaimRecord row = HCClaimForTarget(target);
        if (!row || !HCCampStore.HCClaimTargetValid(row, now)) { return false; }
        HCGroupService groups = HCGroupService.Get();
        reason = "CLAIM_GROUP_UNAVAILABLE";
        if (!groups || groups.HCClaimGroupState(row.GroupId) != 1) { return false; }
        reason = HCCampProbes.HCClaimEligibility(row, now, scan.Storage, scan.Hidden(false), raid);
        if (reason != "") { HCCampProbes.HCRefuse(reason); return false; }
        if (raid) { return HCCampProbes.HCRequestRaidParty(this, target, scan, false, now, reason); }
        return HCCampProbes.HCRequestVisitorParty(this, target, scan, false, now, reason);
    }

    protected void HCStepClaim(HCCampRecord target, int now)
    {
        if (!HCCampProbes.HCEnabled()) { return; }
        string reason;
        HCCampScan scan = HCReadClaimScan(target, reason, false);
        if (!scan) { HCCampProbes.HCRefuse(reason); return; }
        HCRequestClaimArrival(target, scan, now, false, reason);
        if (!m_Running) { return; }
        HCRequestClaimArrival(target, scan, now, true, reason);
    }

    // #203: select is bounded by the admin owner; native scans and dispatch
    // consume the SAME shared budget as normal physical camp work.
    bool HCAdminRequestArrival(HCCampRecord camp, bool raid, out string reason)
    {
        reason = "camp-service-unavailable";
        if (!m_Running || !camp || !GetGame() || !GetGame().IsServer()) { return false; }
        int now = HCWorldClock.UTC();
        reason = "camp-clock-unavailable";
        if (now < 1 || now < m_LastUtc) { return false; }
        reason = "camp-admin-shared-work-budget";
        if (camp.AnchorKind != "claim" && !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_BASES, 128 + 32)) { return false; }
        m_Players.Clear();
        GetGame().GetPlayers(m_Players);
        reason = "camp-player-cap-exceeded";
        if (m_Players.Count() > 32) { m_Players.Clear(); return false; }
        if (camp.AnchorKind == "claim")
        {
            HCCampScan claimScan;
            if (m_ClaimSelectionTarget == camp && m_ClaimSelectionUtc == now) { claimScan = m_ClaimSelectionScan; }
            m_ClaimSelectionScan = null;
            m_ClaimSelectionTarget = null;
            if (!claimScan) { claimScan = HCReadClaimScan(camp, reason, false); }
            if (!claimScan) { HCCampProbes.HCRefuse(reason); return false; }
            return HCRequestClaimArrival(camp, claimScan, now, raid, reason);
        }
        FireplaceBase fire = FireFor(camp);
        bool burning = fire && fire.IsBurning();
        HCCampScan scan = HCCampScan.Read(camp.Position, burning);
        reason = "camp-scan-unavailable";
        if (!scan) { return false; }
        if (raid) { return HCCampProbes.HCRequestRaidParty(this, camp, scan, burning, now, reason); }
        return HCCampProbes.HCRequestVisitorParty(this, camp, scan, burning, now, reason);
    }

    protected void HCStepEncounter(int now)
    {
        int targetCount = HCEncounterCount();
        if (targetCount > 0)
        {
            if (m_CampCursor >= targetCount) { m_CampCursor = 0; }
            HCCampRecord target = HCEncounterTarget(m_CampCursor, now);
            if (target)
            {
                if (target.AnchorKind == "claim") { HCStepClaim(target, now); }
                else { StepCamp(target, now); }
            }
            m_CampCursor++;
        }
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || !(deltaTime > 0)) { return; }
        HCBuildingClaim claims = HCBuildingClaim.HCGet();
        if (claims) { claims.HCStep(deltaTime); }
        m_Elapsed += Math.Min(deltaTime, 5);
        if (m_Elapsed < 5) { return; }
        m_Elapsed = 0;
        int now = HCWorldClock.UTC();
        if (now < m_LastUtc || now < 1) { Fail(); return; }
        m_LastUtc = now;
        m_Players.Clear();
        GetGame().GetPlayers(m_Players);
        // No partial observer/group snapshot is used if the server exceeds cap.
        if (m_Players.Count() > 32) { m_Players.Clear(); return; }
        if (s_Fires.Count() > 0)
        {
            if (m_FireCursor >= s_Fires.Count()) { m_FireCursor = 0; }
            Candidate(s_Fires[m_FireCursor], now);
            m_FireCursor++;
        }
        if (!m_Running) { return; }
        HCStepEncounter(now);
        if (m_Running && now - m_LastSaved >= 600) { Commit(now); }
    }

    override void OnStop()
    {
        HCBuildingClaim.HCStop();
        if (m_Running) { Commit(HCWorldClock.UTC()); }
        m_Running = false;
        m_Status.HCPublish("off", "camp_owner_stopped");
        if (s_Instance == this) { s_Instance = null; }
        m_Players.Clear();
    }
}

// Read-only group bridge in the Camps scope. No group files/ACLs/protocols change.
// Uses the exact service-owned live peer and HCGroupRules.FindGroup; no player
// identity is persisted in camp data. No RPC or client-owned group admission.
modded class HCGroupService
{
    string HCCampReadGroupId(PlayerBase player)
    {
        if (!m_Healthy || !m_State || !player || !player.GetIdentity()) { return ""; }
        HCGroupPeer peer = Peer(player.GetIdentity().GetId());
        if (!Live(peer) || peer.Player != player) { return ""; }
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, peer.Id);
        if (!group) { return ""; }
        return group.Id.ToString();
    }
}

modded class FireplaceBase
{
    override void EEInit()
    {
        super.EEInit();
        HCCampModule.Remember(this);
    }

    override void StartFire(bool force_start = false)
    {
        super.StartFire(force_start);
        HCCampModule.Remember(this);
    }

    override void StopFire(FireplaceFireState fire_state = FireplaceFireState.END_FIRE)
    {
        super.StopFire(fire_state);
        HCCampModule.Remember(this);
    }

    override void EEDelete(EntityAI parent)
    {
        HCCampModule.Forget(this);
        super.EEDelete(parent);
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCCampModule);
    }
}
