// W6 optional server tuning. Missing keys retain defaults despite native zero-fill.
// Existing EnableCamps/EnableGroups/EnableTeamPing preferences remain opt-outs.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; EnDebug.c:96 Print.
// Bounded IO uses HCGroupIO; this read-only config creates no persistence owner.
class HCGCCampGroupConfig
{
    int CampFireCandidates = 128;
    int CampPlayers = 32;
    int CampTickSeconds = 5;
    int CampScanSeconds = 600;
    int CampProbeScanSeconds = 30;
    int CampSaveSeconds = 600;
    int CampBindDistanceSq = 145;
    int PinLimit = 64;
    int LeadPins = 5;
    int TrailPins = 48;
    int ShelterQueries = 20;
    int TrailRadiusMeters = 40;
    int PinRefreshSeconds = 60;
    int PinLogSeconds = 600;
    int PinLogGroups = 1;
    int TeamPingRows = 90;
    int TeamPingSeconds = 60;
    int TeamPingCooldownSeconds = 10;
    int TeamPingPruneRows = 32;
    int TeamPingLogSeconds = 60;
    int TeamPingRadiusMeters = 5;
    int DebugGroups = 1;
    int DebugPins = 32;
    protected static ref HCGCCampGroupConfig s_Config;

    protected int HCValue(string text, string key, int value, int declared, int low, int high)
    {
        if (!HCJsonFields.Has(text, key)) { return declared; }
        string registryKey = "CampGroup." + key;
        // Literal ceilings remain until the shared registry integration lands.
        bool valid = value >= low && value <= high;
        if (HCOperatorSettingsRegistry.HCFind(registryKey)) { valid = valid && HCOperatorSettingsRegistry.HCValid(registryKey, value); }
        if (valid) { return value; }
        Print("[HC CampGroup] invalid_setting=" + key + " default_restored runtime=PENDING");
        return declared;
    }

    void HCNormalize(string text)
    {
        if (!HCJsonFields.Has(text, "CampFireCandidates")) { CampFireCandidates = 128; }
        CampFireCandidates = HCValue(text, "CampFireCandidates", CampFireCandidates, 128, 1, 128);
        if (!HCJsonFields.Has(text, "CampPlayers")) { CampPlayers = 32; }
        CampPlayers = HCValue(text, "CampPlayers", CampPlayers, 32, 1, 32);
        if (!HCJsonFields.Has(text, "CampTickSeconds")) { CampTickSeconds = 5; }
        CampTickSeconds = HCValue(text, "CampTickSeconds", CampTickSeconds, 5, 1, 60);
        if (!HCJsonFields.Has(text, "CampScanSeconds")) { CampScanSeconds = 600; }
        CampScanSeconds = HCValue(text, "CampScanSeconds", CampScanSeconds, 600, 30, 3600);
        if (!HCJsonFields.Has(text, "CampProbeScanSeconds")) { CampProbeScanSeconds = 30; }
        CampProbeScanSeconds = HCValue(text, "CampProbeScanSeconds", CampProbeScanSeconds, 30, 5, 600);
        if (!HCJsonFields.Has(text, "CampSaveSeconds")) { CampSaveSeconds = 600; }
        CampSaveSeconds = HCValue(text, "CampSaveSeconds", CampSaveSeconds, 600, 60, 3600);
        if (!HCJsonFields.Has(text, "CampBindDistanceSq")) { CampBindDistanceSq = 145; }
        CampBindDistanceSq = HCValue(text, "CampBindDistanceSq", CampBindDistanceSq, 145, 1, 145);
        if (!HCJsonFields.Has(text, "PinLimit")) { PinLimit = 64; }
        PinLimit = HCValue(text, "PinLimit", PinLimit, 64, 1, 64);
        if (!HCJsonFields.Has(text, "LeadPins")) { LeadPins = 5; }
        LeadPins = HCValue(text, "LeadPins", LeadPins, 5, 1, 5);
        if (!HCJsonFields.Has(text, "TrailPins")) { TrailPins = 48; }
        TrailPins = HCValue(text, "TrailPins", TrailPins, 48, 1, 48);
        if (!HCJsonFields.Has(text, "ShelterQueries")) { ShelterQueries = 20; }
        ShelterQueries = HCValue(text, "ShelterQueries", ShelterQueries, 20, 1, 20);
        if (!HCJsonFields.Has(text, "TrailRadiusMeters")) { TrailRadiusMeters = 40; }
        TrailRadiusMeters = HCValue(text, "TrailRadiusMeters", TrailRadiusMeters, 40, 1, 40);
        if (!HCJsonFields.Has(text, "PinRefreshSeconds")) { PinRefreshSeconds = 60; }
        PinRefreshSeconds = HCValue(text, "PinRefreshSeconds", PinRefreshSeconds, 60, 5, 600);
        if (!HCJsonFields.Has(text, "PinLogSeconds")) { PinLogSeconds = 600; }
        PinLogSeconds = HCValue(text, "PinLogSeconds", PinLogSeconds, 600, 60, 3600);
        if (!HCJsonFields.Has(text, "PinLogGroups")) { PinLogGroups = 1; }
        PinLogGroups = HCValue(text, "PinLogGroups", PinLogGroups, 1, 1, 4);
        if (!HCJsonFields.Has(text, "TeamPingRows")) { TeamPingRows = 90; }
        TeamPingRows = HCValue(text, "TeamPingRows", TeamPingRows, 90, 1, 90);
        if (!HCJsonFields.Has(text, "TeamPingSeconds")) { TeamPingSeconds = 60; }
        TeamPingSeconds = HCValue(text, "TeamPingSeconds", TeamPingSeconds, 60, 10, 60);
        if (!HCJsonFields.Has(text, "TeamPingCooldownSeconds")) { TeamPingCooldownSeconds = 10; }
        TeamPingCooldownSeconds = HCValue(text, "TeamPingCooldownSeconds", TeamPingCooldownSeconds, 10, 1, 60);
        if (!HCJsonFields.Has(text, "TeamPingPruneRows")) { TeamPingPruneRows = 32; }
        TeamPingPruneRows = HCValue(text, "TeamPingPruneRows", TeamPingPruneRows, 32, 1, 32);
        if (!HCJsonFields.Has(text, "TeamPingLogSeconds")) { TeamPingLogSeconds = 60; }
        TeamPingLogSeconds = HCValue(text, "TeamPingLogSeconds", TeamPingLogSeconds, 60, 10, 600);
        if (!HCJsonFields.Has(text, "TeamPingRadiusMeters")) { TeamPingRadiusMeters = 5; }
        TeamPingRadiusMeters = HCValue(text, "TeamPingRadiusMeters", TeamPingRadiusMeters, 5, 1, 5);
        if (!HCJsonFields.Has(text, "DebugGroups")) { DebugGroups = 1; }
        DebugGroups = HCValue(text, "DebugGroups", DebugGroups, 1, 1, 4);
        if (!HCJsonFields.Has(text, "DebugPins")) { DebugPins = 32; }
        DebugPins = HCValue(text, "DebugPins", DebugPins, 32, 1, 32);
    }

    static HCGCCampGroupConfig Get()
    {
        if (s_Config) { return s_Config; }
        s_Config = new HCGCCampGroupConfig;
        string path = "$profile:HollowCountry/camp-group-config.json";
        if (FileExist(path))
        {
            string text;
            string error;
            HCGCCampGroupConfig decoded;
            if (HCGroupIO.Read(path, 16384, text) && JsonFileLoader<HCGCCampGroupConfig>.LoadData(text, decoded, error) && decoded)
            {
                decoded.HCNormalize(text);
                s_Config = decoded;
            }
            else { Print("[HC CampGroup] invalid_config defaults_restored runtime=PENDING"); }
        }
        s_Config.HCLog();
        return s_Config;
    }

    void HCLog()
    {
        Print("[HC CampGroup] limits CampFireCandidates=" + CampFireCandidates.ToString() + " CampPlayers=" + CampPlayers.ToString() + " CampTickSeconds=" + CampTickSeconds.ToString() + " CampScanSeconds=" + CampScanSeconds.ToString() + " runtime=PENDING");
        Print("[HC CampGroup] limits CampProbeScanSeconds=" + CampProbeScanSeconds.ToString() + " CampSaveSeconds=" + CampSaveSeconds.ToString() + " CampBindDistanceSq=" + CampBindDistanceSq.ToString() + " runtime=PENDING");
        Print("[HC CampGroup] limits PinLimit=" + PinLimit.ToString() + " LeadPins=" + LeadPins.ToString() + " TrailPins=" + TrailPins.ToString() + " ShelterQueries=" + ShelterQueries.ToString() + " runtime=PENDING");
        Print("[HC CampGroup] limits TrailRadiusMeters=" + TrailRadiusMeters.ToString() + " PinRefreshSeconds=" + PinRefreshSeconds.ToString() + " PinLogSeconds=" + PinLogSeconds.ToString() + " PinLogGroups=" + PinLogGroups.ToString() + " runtime=PENDING");
        Print("[HC CampGroup] limits TeamPingRows=" + TeamPingRows.ToString() + " TeamPingSeconds=" + TeamPingSeconds.ToString() + " TeamPingCooldownSeconds=" + TeamPingCooldownSeconds.ToString() + " TeamPingPruneRows=" + TeamPingPruneRows.ToString() + " runtime=PENDING");
        Print("[HC CampGroup] limits TeamPingLogSeconds=" + TeamPingLogSeconds.ToString() + " TeamPingRadiusMeters=" + TeamPingRadiusMeters.ToString() + " DebugGroups=" + DebugGroups.ToString() + " DebugPins=" + DebugPins.ToString() + " runtime=PENDING");
    }
}

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
    protected int m_CheckpointUtc;
    protected ref HCV2ThreatStore<HCCampData> m_CheckpointWriter = new HCV2ThreatStore<HCCampData>;
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
        if (s_Fires.Count() >= HCGCCampGroupConfig.Get().CampFireCandidates)
        {
            if (!s_FireCapLogged) { Print("[HC CampGroup] fire_candidate_cap=" + HCGCCampGroupConfig.Get().CampFireCandidates.ToString() + " extra_fires_ignored runtime=PENDING"); s_FireCapLogged = true; }
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
        HCGCCampGroupConfig.Get();
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
        HCOperationalStatus visitors = HCCampProbes.HCGetOperationalStatus();
        HCOperationalStatus probes = HCBaseRaid.HCGetOperationalStatus();
        Print("[HC CampGroup] camps_started camps=" + m_Data.Camps.Count().ToString() + " runtime=PENDING");
        Print("[HC CampGroup] visitors=" + visitors.HCState() + " reason=" + visitors.HCReason() + " runtime=PENDING");
        Print("[HC CampGroup] probes=" + probes.HCState() + " reason=" + probes.HCReason() + " mailbox=retired runtime=PENDING");
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
        if (!m_Running || now < m_LastUtc || !m_CheckpointWriter.FinishSave() || !HCCampStore.Save(m_Data, now)) { Fail(); return false; }
        m_LastSaved = now;
        return true;
    }

    // Snapshot serialization leaves files untouched; subsequent crash states
    // follow HCStagedSaveImage.HCStepImage. HCCampStore admission remains unchanged.
    int HCStepCheckpoint(int now)
    {
        if (!m_Running || now < m_LastUtc) { return HCSaveJob.STEP_FAILED; }
        if (!m_CheckpointWriter.SaveInFlight())
        {
            m_CheckpointUtc = now;
            if (!HCCampStore.CanCheckpoint(m_Data, now)) { Fail(); return HCSaveJob.STEP_FAILED; }
        }
        int result = m_CheckpointWriter.SaveStep(HCCampStore.PATH, m_Data, HCCampStore.BYTES);
        if (result == HCSaveJob.STEP_FAILED) { Fail(); }
        // Use the snapshot timestamp so a later automatic Commit remains due.
        if (result == HCSaveJob.STEP_DONE) { m_LastSaved = m_CheckpointUtc; }
        return result;
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
        float best = HCGCCampGroupConfig.Get().CampBindDistanceSq;
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
        int interval = HCGCCampGroupConfig.Get().CampScanSeconds;
        if (camp.ProbePhase > 0) { interval = HCGCCampGroupConfig.Get().CampProbeScanSeconds; }
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
        if (camp.AnchorKind != "claim" && !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_BASES, 128 + HCGCCampGroupConfig.Get().CampPlayers)) { return false; }
        m_Players.Clear();
        GetGame().GetPlayers(m_Players);
        reason = "camp-player-cap-exceeded";
        if (m_Players.Count() > HCGCCampGroupConfig.Get().CampPlayers) { m_Players.Clear(); return false; }
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
        HCReached.Mark("camps.maintenance");
        m_Elapsed += Math.Min(deltaTime, HCGCCampGroupConfig.Get().CampTickSeconds);
        if (m_Elapsed < HCGCCampGroupConfig.Get().CampTickSeconds) { return; }
        m_Elapsed = 0;
        int now = HCWorldClock.UTC();
        if (now < m_LastUtc || now < 1) { Fail(); return; }
        m_LastUtc = now;
        m_Players.Clear();
        GetGame().GetPlayers(m_Players);
        // No partial observer/group snapshot is used if the server exceeds cap.
        if (m_Players.Count() > HCGCCampGroupConfig.Get().CampPlayers) { m_Players.Clear(); return; }
        if (s_Fires.Count() > 0)
        {
            if (m_FireCursor >= s_Fires.Count()) { m_FireCursor = 0; }
            Candidate(s_Fires[m_FireCursor], now);
            m_FireCursor++;
        }
        if (!m_Running) { return; }
        HCStepEncounter(now);
        if (m_Running && now - m_LastSaved >= HCGCCampGroupConfig.Get().CampSaveSeconds) { Commit(now); }
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
