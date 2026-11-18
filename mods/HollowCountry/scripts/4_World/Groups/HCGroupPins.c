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
    static bool AddTrail(HCGroupRecord group, string shelterId)
    {
        if (!group || !group.HCTrailPlaceIds || group.HCTrailPlaceIds.Count() >= 48 || group.HCTrailPlaceIds.Find(shelterId) >= 0) { return false; }
        group.HCTrailPlaceIds.Insert(shelterId);
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
        pin.Radius = 40;
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

    static HCGroupPins Get() { return s_Instance; }
    override string GetName() { return "MapPins"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableGroups; }

    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings) || s_Instance) { return; }
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
        // #131: at most 90 expiring team pings, sharing the existing wire cap.
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
                if (output.Count() >= cap || leadCount >= 5) { break; }
                if (row.GroupId != groupId) { continue; }
                HCGroupPlace leadPin = HCGroupPinPolicy.LeadPin(row, leadNow);
                if (!leadPin) { continue; }
                output.Insert(leadPin);
                leadCount++;
            }
        }
        if (!m_Trail || !group.HCTrailPlaceIds) { return; }
        int shelterCount = HCShelterCatalog.Count();
        if (shelterCount > 20) { shelterCount = 20; }
        for (int shelterIndex = 0; shelterIndex < shelterCount; shelterIndex++)
        {
            if (output.Count() >= cap) { break; }
            HCShelterEntry placedShelter = HCShelterCatalog.Get(shelterIndex);
            if (!placedShelter || !placedShelter.Placed) { continue; }
            HCGroupPlace trailPin = HCGroupPinPolicy.TrailPin(placedShelter);
            if (trailPin && group.HCTrailPlaceIds.Find(trailPin.Id) >= 0) { output.Insert(trailPin); }
        }
    }

    override void OnTick(float deltaTime)
    {
        if (s_Instance != this || !(deltaTime > 0)) { return; }
        HCGroupService groups = HCGroupService.Get();
        if (!groups) { return; }
        if (m_Trail) { groups.HCPinsDiscover(); }
        // Refresh FULL through the existing group path, including newly
        // received leads when no membership or discovery mutation occurs.
        m_RefreshSeconds += deltaTime;
        if (m_RefreshSeconds >= 60)
        {
            m_RefreshSeconds = 0;
            groups.Broadcast();
        }
        m_LogSeconds += deltaTime;
        if (m_LogSeconds >= 600)
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
        if (!m_Healthy || !m_Config.DiscoveryLayer || m_Peers.Count() == 0) { return; }
        if (GetGame().GetTickTime() < m_DiscoveryBlockedUntil) { return; }
        if (m_HCPinsCursor >= m_Peers.Count()) { m_HCPinsCursor = 0; }
        HCGroupPeer explorer = m_Peers.Get(m_HCPinsCursor);
        m_HCPinsCursor++;
        if (!Live(explorer) || !explorer.Player.IsAlive() || explorer.Player.IsUnconscious()) { return; }
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, explorer.Id);
        if (!group || !group.HCTrailPlaceIds || group.HCTrailPlaceIds.Count() >= 48) { return; }
        vector actual = explorer.Player.GetPosition();
        if (!HCGroupRules.PositionValid(actual)) { return; }
        HCGroupState candidate;
        HCGroupRecord candidateGroup;
        int shelterCount = HCShelterCatalog.Count();
        if (shelterCount > 20) { shelterCount = 20; }
        for (int shelterIndex = 0; shelterIndex < shelterCount; shelterIndex++)
        {
            HCShelterEntry placedShelter = HCShelterCatalog.Get(shelterIndex);
            if (!placedShelter || !placedShelter.Placed) { continue; }
            HCGroupPlace shelter = HCGroupPinPolicy.TrailPin(placedShelter);
            if (!shelter || group.HCTrailPlaceIds.Find(shelter.Id) >= 0) { continue; }
            float dx = actual[0] - shelter.Position[0];
            float dz = actual[2] - shelter.Position[2];
            if (dx * dx + dz * dz > 1600) { continue; }
            if (!candidate)
            {
                if (!Clone(candidate)) { m_DiscoveryBlockedUntil = GetGame().GetTickTime() + 60; return; }
                candidateGroup = HCGroupRules.ById(candidate, group.Id);
                if (!candidateGroup) { return; }
            }
            HCGroupPinPolicy.AddTrail(candidateGroup, shelter.Id);
        }
        if (!candidate) { return; }
        if (candidateGroup.Revision >= 1000000000) { return; }
        HCGroupRules.Touch(candidateGroup, false);
        int result = Commit(candidate);
        if (result == HCGroupCode.LIMIT) { m_DiscoveryBlockedUntil = GetGame().GetTickTime() + 60; }
        if (result == HCGroupCode.STORAGE) { Stop(); return; }
        if (result == HCGroupCode.OK)
        {
            Broadcast();
            // Notify only after the discovery ledger was committed successfully.
            for (int noticeIndex = 0; noticeIndex < shelterCount; noticeIndex++)
            {
                HCShelterEntry discoveredShelter = HCShelterCatalog.Get(noticeIndex);
                if (!discoveredShelter || !discoveredShelter.Placed) { continue; }
                string discoveredId = "hc-found:" + discoveredShelter.Name;
                bool newlyFound = group.HCTrailPlaceIds.Find(discoveredId) < 0;
                bool committedFound = candidateGroup.HCTrailPlaceIds.Find(discoveredId) >= 0;
                if (newlyFound && committedFound)
                {
                    NotificationSystem.SendNotificationToPlayerExtended(explorer.Player, 10, discoveredShelter.Name, discoveredShelter.History);
                }
            }
        }
    }

    void HCPinsLog(HCGroupPins pins)
    {
        if (!m_Healthy) { return; }
        int trailCount = 0;
        int leadCount = 0;
        int deathCount = 0;
        foreach (HCGroupRecord group : m_State.Groups)
        {
            array<ref HCGroupPlace> known = new array<ref HCGroupPlace>();
            pins.Collect(group, m_Config.MaxDiscoveries, known);
            foreach (HCGroupPlace pin : known)
            {
                if (pin.Id.IndexOf("hc-found:") == 0) { trailCount++; }
                if (pin.Id.IndexOf("hc-lead:") == 0) { leadCount++; }
                if (pin.Id.IndexOf("hc-death:") == 0) { deathCount++; }
            }
        }
        Print("[HollowCountry] V2 map pins groups=" + m_State.Groups.Count().ToString() + " trail=" + trailCount.ToString() + " leads=" + leadCount.ToString() + " deaths=" + deathCount.ToString());
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
