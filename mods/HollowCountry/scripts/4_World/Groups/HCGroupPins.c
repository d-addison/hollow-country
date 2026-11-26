// Row cursor native evidence: 1_Core/proto/EnScript.c:380 Count, :399 Get.
// LC-T207 / LC-T305. EXP-T5 is diagnostic only (owner 2026-11-17).
// Native snapshot scripts-1.30.164289: 3_Game/Entities/Object.c:287,517
// (GetPosition/IsAlive), 4_World/Entities/ManBase/PlayerBase.c:3925
// (IsUnconscious), 1_Core/proto/EnScript.c:380,394,399,407 (arrays),
// 3_Game/Global/Game.c:914 (GetTickTime for quota retry backoff),
// 1_Core/proto/EnString.c:113,199,240 (Substring/Length/IndexOf),
// 3_Game/Client/Notifications/NotificationSystem.c:125 (server notification).
// 3_Game/Entities/Man.c:21 GetIdentity; 3_Game/gameplay.c:362/368 GetName/GetId;
// 3_Game/Global/Game.c:1120 IsServer (authenticated native death hook).
// 1_Core/proto/EnConvert.c:30 (int.ToString), EnDebug.c:96 (Print).
// Uses existing HCGroupService authenticated peers, Clone/Commit/Broadcast,
// HCLeadModule.GroupLeads and HCLeadPolicy.Place (authored named-place catalog).
// No world accessor or core hook needed. No item/entity mutation or new RPC.

class HCGroupPinPolicy
{
    static bool AddTrail(HCGroupRecord group, string shelterId, HCGroupStringIndex trails)
    {
        if (!group || !group.HCTrailPlaceIds || group.HCTrailPlaceIds.Count() >= HCGCCampGroupConfig.Get().TrailPins || !trails || trails.Has(shelterId)) { return false; }
        group.HCTrailPlaceIds.Insert(shelterId);
        trails.Add(shelterId);
        return true;
    }

    static HCGroupPlace TrailPin(HCShelterEntry shelter)
    {
        if (!shelter || !shelter.Placed) { return null; }
        HCGroupPlace pin = new HCGroupPlace;
        pin.Id = "hc-found:" + shelter.Name;
        pin.Name = shelter.Name;
        // Keep the wire's 64-character label bound while showing its history.
        int historyLength = 61 - shelter.Name.Length();
        if (historyLength > shelter.History.Length()) { historyLength = shelter.History.Length(); }
        if (historyLength > 0) { pin.Name = shelter.Name + ": " + shelter.History.Substring(0, historyLength); }
        pin.Position = shelter.Position;
        pin.Radius = HCGCCampGroupConfig.Get().TrailRadiusMeters;
        if (!HCGroupRules.PlaceValid(pin)) { return null; }
        return pin;
    }

    static HCGroupPlace LeadPin(HCWorldLead lead, int now)
    {
        if (!lead || now < 1 || lead.Expires <= now) { return null; }
        HCWorldPlace namedPlace = HCLeadPolicy.Place(lead.TargetPlaceId);
        if (!namedPlace) { return null; }
        HCGroupPlace pin = new HCGroupPlace;
        pin.Id = "hc-lead:" + lead.Id;
        pin.Name = namedPlace.Name;
        pin.Position = namedPlace.Position;
        pin.HCPinExpiresUtc = lead.Expires;
        if (!HCGroupRules.PlaceValid(pin)) { return null; }
        return pin;
    }
}

class HCGroupPins : HCModule
{
    protected static HCGroupPins s_Instance;
    protected bool m_Trail;
    protected bool m_Leads;
    protected bool m_AdmissionPrinted;
    protected float m_RefreshSeconds;
    protected float m_LogSeconds = 600;
    protected ref HCDeathPins m_DeathPins;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    static HCGroupPins Get() { return s_Instance; }
    override string GetName() { return "MapPins"; }

    // Wave 16: started = this module is the registered pin source (s_Instance), never hard-coded.
    override HCOperationalStatus HCGetOperationalStatus()
    {
        bool started = false;
        if (s_Instance == this) { started = true; }
        HCModuleReadiness.HCDerive(m_Operational, started, "", "", "map_pins_started");
        return m_Operational;
    }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableGroups; }

    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings) || s_Instance) { return; }
        HCGCCampGroupConfig.Get();
        m_Trail = settings.EnableTravel;
        m_Leads = settings.EnableLeads;
        s_Instance = this;
        m_DeathPins = new HCDeathPins;
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("MapPins", true, "EXP-T5", HCV2Gates.Qualified("EXP-T5")));
            m_AdmissionPrinted = true;
        }
    }

    // Output is a received-only view, not the world catalog. Re-resolved on
    // every FULL frame; client expiry removes a lead without waiting for one.
    void Collect(HCGroupRecord group, int cap, array<ref HCGroupPlace> output)
    {
        if (!group || !output || cap < 1) { return; }
        HCGCCampGroupConfig limits = HCGCCampGroupConfig.Get();
        if (cap > limits.PinLimit) { cap = limits.PinLimit; }
        // Effective pin policy applies to snapshots and debug collection alike.
        HCTeamPingModule teamPings = HCTeamPingModule.Get();
        if (teamPings) { teamPings.HCCollect(group, cap, output); }
        // A corpse-run pin has priority over leads/trails at the existing cap.
        if (m_DeathPins) { m_DeathPins.HCCollect(group, cap, output); }
        HCLeadModule leads = HCLeadModule.Get();
        HCWorldModule world = HCWorldModule.Get();
        if (m_Leads && leads && world)
        {
            array<ref HCWorldLead> received;
            string groupId = "group-" + group.Id.ToString();
            leads.GroupLeads(groupId, received);
            int leadCount = 0;
            int leadNow = HCGroupClock.Utc();
            foreach (HCWorldLead row : received)
            {
                if (output.Count() >= cap || leadCount >= limits.LeadPins) { break; }
                if (row.GroupId != groupId) { continue; }
                HCGroupPlace leadPin = HCGroupPinPolicy.LeadPin(row, leadNow);
                if (!leadPin) { continue; }
                output.Insert(leadPin);
                HCModuleReadiness.HCUse("MapPins", "pins_published");
                leadCount++;
            }
        }
        if (!m_Trail || !group.HCTrailPlaceIds) { return; }
        HCGroupStringIndex trails = new HCGroupStringIndex(group.HCTrailPlaceIds);
        int shelterCount = HCShelterCatalog.Count();
        if (shelterCount > HCGCCampGroupConfig.Get().ShelterQueries) { shelterCount = HCGCCampGroupConfig.Get().ShelterQueries; }
        for (int shelterIndex = 0; shelterIndex < shelterCount; shelterIndex++)
        {
            if (output.Count() >= cap) { break; }
            HCShelterEntry placedShelter = HCShelterCatalog.Get(shelterIndex);
            if (!placedShelter || !placedShelter.Placed) { continue; }
            HCGroupPlace trailPin = HCGroupPinPolicy.TrailPin(placedShelter);
            if (trailPin && trails.Has(trailPin.Id)) { output.Insert(trailPin); HCModuleReadiness.HCUse("MapPins", "pins_published"); }
        }
    }

    override void OnTick(float deltaTime)
    {
        if (s_Instance != this || !(deltaTime > 0)) { return; }
        HCGroupService groups = HCGroupService.Get();
        if (!groups) { return; }
        if (m_Trail) { groups.HCPinsDiscover(); }
        HCReached.Mark("map_pins.refresh");
        // Refresh FULL through the existing group path, including newly
        // received leads when no membership or discovery mutation occurs.
        m_RefreshSeconds += deltaTime;
        if (m_RefreshSeconds >= HCGCCampGroupConfig.Get().PinRefreshSeconds)
        {
            m_RefreshSeconds = 0;
            groups.Broadcast();
        }
        m_LogSeconds += deltaTime;
        if (m_LogSeconds >= HCGCCampGroupConfig.Get().PinLogSeconds)
        {
            m_LogSeconds = 0;
            groups.HCPinsLog(this);
        }
    }

    void HCPlayerFell(PlayerBase player)
    {
        HCGroupService groups = HCGroupService.Get();
        if (!groups || !m_DeathPins) { return; }
        groups.HCPinsDeath(player, m_DeathPins);
    }

    override void OnStop()
    {
        if (s_Instance == this) { s_Instance = null; }
        m_DeathPins = null;
    }
}

modded class HCGroupService
{
    protected int m_HCPinsCursor;
    protected int m_HCPinsLogCursor;
    // Id + session, not the peer: HCGroupPeer is not Managed and a logout or reconnect frees it while the
    // staged save is still pending. Re-resolved through Peer() after the save.
    protected string m_TrailExplorerId;
    protected string m_TrailExplorerSession;
    protected ref HCGroupStringIndex m_TrailPrior;
    protected int m_TrailGroup;

    void HCPinsDeath(PlayerBase player, HCDeathPins pins)
    {
        if (!m_Healthy || !player || !pins || !GetGame().IsServer()) { return; }
        PlayerIdentity identity = player.GetIdentity();
        if (!identity) { return; }
        string uid = identity.GetId();
        HCGroupPeer peer = Peer(uid);
        if (!Live(peer) || peer.Player != player) { return; }
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, uid);
        if (!group) { return; }
        if (!pins.HCPublish(group, uid, identity.GetName(), player.GetPosition())) { return; }
        Print("[HollowCountry] V2 map pins death group=" + group.Id.ToString());
        Broadcast();
    }

    void HCPinsDiscover()
    {
        if (!m_Healthy || m_PendingState || !m_Config.DiscoveryLayer || m_Peers.Count() == 0) { return; }
        if (GetGame().GetTickTime() < m_DiscoveryBlockedUntil) { return; }
        if (m_HCPinsCursor >= m_Peers.Count()) { m_HCPinsCursor = 0; }
        HCGroupPeer explorer = m_Peers.Get(m_HCPinsCursor);
        m_HCPinsCursor++;
        if (!Live(explorer) || !explorer.Player.IsAlive() || explorer.Player.IsUnconscious()) { return; }
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, explorer.Id);
        if (!group || !group.HCTrailPlaceIds || group.HCTrailPlaceIds.Count() >= HCGCCampGroupConfig.Get().TrailPins) { return; }
        vector actual = explorer.Player.GetPosition();
        if (!HCGroupRules.PositionValid(actual)) { return; }
        HCGroupState candidate;
        HCGroupRecord candidateGroup;
        HCGroupStringIndex candidateTrails;
        HCGroupStringIndex trails = new HCGroupStringIndex(group.HCTrailPlaceIds);
        int shelterCount = HCShelterCatalog.Count();
        if (shelterCount > HCGCCampGroupConfig.Get().ShelterQueries) { shelterCount = HCGCCampGroupConfig.Get().ShelterQueries; }
        for (int shelterIndex = 0; shelterIndex < shelterCount; shelterIndex++)
        {
            HCShelterEntry placedShelter = HCShelterCatalog.Get(shelterIndex);
            if (!placedShelter || !placedShelter.Placed) { continue; }
            HCGroupPlace shelter = HCGroupPinPolicy.TrailPin(placedShelter);
            if (!shelter || trails.Has(shelter.Id)) { continue; }
            float dx = actual[0] - shelter.Position[0];
            float dz = actual[2] - shelter.Position[2];
            if (dx * dx + dz * dz > HCGCCampGroupConfig.Get().TrailRadiusMeters * HCGCCampGroupConfig.Get().TrailRadiusMeters) { continue; }
            if (!candidate)
            {
                if (!Clone(candidate)) { m_DiscoveryBlockedUntil = GetGame().GetTickTime() + 60; return; }
                candidateGroup = HCGroupRules.ById(candidate, group.Id);
                if (!candidateGroup) { return; }
                candidateTrails = new HCGroupStringIndex(candidateGroup.HCTrailPlaceIds);
            }
            HCGroupPinPolicy.AddTrail(candidateGroup, shelter.Id, candidateTrails);
        }
        if (!candidate) { return; }
        if (candidateGroup.Revision >= 1000000000) { return; }
        HCGroupRules.Touch(candidateGroup, false);
        int result = HCQueueCommit(candidate);
        if (result == HCGroupCode.LIMIT) { m_DiscoveryBlockedUntil = GetGame().GetTickTime() + 60; }
        if (result == HCGroupCode.STORAGE) { Stop(); return; }
        if (result == HCGroupCode.OK)
        {
            m_TrailExplorerId = explorer.Id;
            m_TrailExplorerSession = explorer.Session;
            m_TrailPrior = trails;
            m_TrailGroup = candidateGroup.Id;
        }
    }

    override void HCPostBatchSave()
    {
        super.HCPostBatchSave();
        HCGroupPeer explorer = null;
        if (m_TrailExplorerId != "") { explorer = Peer(m_TrailExplorerId); }
        if (explorer && explorer.Session != m_TrailExplorerSession) { explorer = null; }
        HCGroupStringIndex prior = m_TrailPrior;
        m_TrailExplorerId = "";
        m_TrailExplorerSession = "";
        m_TrailPrior = null;
        if (!Live(explorer) || !prior || !explorer.Player.IsAlive() || explorer.Player.IsUnconscious()) { return; }
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, explorer.Id);
        if (!group || group.Id != m_TrailGroup) { return; }
        HCGroupStringIndex committed = new HCGroupStringIndex(group.HCTrailPlaceIds);
        int shelterCount = Math.Min(HCShelterCatalog.Count(), HCGCCampGroupConfig.Get().ShelterQueries);
        for (int noticeIndex = 0; noticeIndex < shelterCount; noticeIndex++)
        {
            HCShelterEntry shelter = HCShelterCatalog.Get(noticeIndex);
            if (!shelter || !shelter.Placed) { continue; }
            string id = "hc-found:" + shelter.Name;
            if (!prior.Has(id) && committed.Has(id))
            {
                NotificationSystem.SendNotificationToPlayerExtended(explorer.Player, 10, shelter.Name, shelter.History);
            }
        }
    }

    void HCPinsLog(HCGroupPins pins)
    {
        if (!m_Healthy) { return; }
        int trailCount = 0;
        int leadCount = 0;
        int deathCount = 0;
        int scanCount = m_State.Groups.Count();
        if (scanCount > HCGCCampGroupConfig.Get().PinLogGroups) { scanCount = HCGCCampGroupConfig.Get().PinLogGroups; }
        // HCGCCampGroupConfig.HCNormalize bounds PinLogGroups to 1..4.
        // Keep that invariant explicit here: this is a rolling diagnostic sample.
        for (int scanIndex = 0; scanIndex < 4 && scanIndex < scanCount; scanIndex++)
        {
            if (m_HCPinsLogCursor >= m_State.Groups.Count()) { m_HCPinsLogCursor = 0; }
            HCGroupRecord group = m_State.Groups[m_HCPinsLogCursor];
            m_HCPinsLogCursor++;
            array<ref HCGroupPlace> known = new array<ref HCGroupPlace>();
            pins.Collect(group, m_Config.MaxDiscoveries, known);
            foreach (HCGroupPlace pin : known)
            {
                if (pin.Id.IndexOf("hc-found:") == 0) { trailCount++; }
                if (pin.Id.IndexOf("hc-lead:") == 0) { leadCount++; }
                if (pin.Id.IndexOf("hc-death:") == 0) { deathCount++; }
            }
        }
        string logHead = "[HollowCountry] V2 map pins groups=" + m_State.Groups.Count().ToString() + " sampled=" + scanCount.ToString();
        Print(logHead + " trail=" + trailCount.ToString() + " leads=" + leadCount.ToString() + " deaths=" + deathCount.ToString() + " rolling_sample runtime=PENDING");
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCGroupPins);
    }
}

// W6: retain the existing registered anonymous rolling contributor. At most
// DebugGroups bounded Collect calls and DebugPins emitted rows per Describe.
// The counters describe the effective pin policy; they are not a world census.
modded class HCDebugGroupPinsContributor
{
    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        HCGroupService groups = HCGroupService.Get();
        HCGCCampGroupConfig limits = HCGCCampGroupConfig.Get();
        if (!snapshot.HCStarted)
        {
            snapshot.HCStarted = true;
            // Do not retain another owner's sample across disable/restart.
            if (!groups || groups != m_GroupOwner)
            {
                m_GroupOwner = groups;
                m_Cursor = 0;
                m_Total = 0;
                m_PublishedTotal = 0;
                m_Rows.Clear();
                m_PublishedRows.Clear();
            }
            if (!groups) { return; }
            int groupCount = groups.HCDebugPinGroupCount();
            if (groupCount == 0)
            {
                m_Cursor = 0;
                m_Total = 0;
                m_Rows.Clear();
                m_PublishedRows.Clear();
                m_PublishedTotal = 0;
                snapshot.HCNoteLayer("group-pins", 0, 0);
                return;
            }
            // One group per capture; keep the last complete rolling sample visible
            // until the next sweep completes. No whole-catalogue Collect call.
            int groupWork = groupCount - m_Cursor;
            if (groupWork > limits.DebugGroups) { groupWork = limits.DebugGroups; }
            m_Total += groups.HCDebugPins(m_Cursor, groupWork, limits.DebugPins, m_Rows);
            m_Cursor += groupWork;
            if (m_Cursor >= groupCount)
            {
                m_PublishedRows = m_Rows;
                m_PublishedTotal = m_Total;
                m_Rows = new array<ref HCDebugGroupPinRow>;
                m_Cursor = 0;
                m_Total = 0;
            }
            if (m_Cursor > 0 && m_PublishedRows.Count() == 0 && m_PublishedTotal == 0) { return; }
        }

        int emitCount = m_PublishedRows.Count();
        if (emitCount > limits.DebugPins) { emitCount = limits.DebugPins; }
        for (int index = snapshot.HCRow; index < emitCount; index++)
        {
            if (!snapshot.HCRowStep()) { return; }
            HCDebugGroupPinRow row = m_PublishedRows[index];
            string detail = "kind=" + row.Kind + "; expires=" + row.ExpiresUtc.ToString() + "; rolling sample; group, player and name withheld";
            if (snapshot.HCAddLayerPoint("group-pins", "pin-" + index.ToString(), row.Position, row.Kind, detail)) { snapshot.HCShown++; }
        }
        snapshot.HCNoteLayer("group-pins", m_PublishedTotal, snapshot.HCShown);
    }
}

