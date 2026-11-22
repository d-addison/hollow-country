// E1 / owner direction 2026-11-19: Expansion AI groups react to world incidents.
// Reads ONLY the HCWorldIncidents registry (core, HCWorldIncidents.c) and only through a member's own
// perception (HCWorldIncidents.HCPerceives: member inside the incident's sound or sight range).
// A group never learns of an incident any other way (no AI radio receiver exists; the registry logs that).
// Responses are data (HCXAIIncidentPolicy rows, optional $profile:HollowCountry/ai-incident-response.json):
//   avoid       group inside a gas zone leaves by the radial route; a route that crosses a zone is vetted
//               (unsafe waypoints dropped) unless EVERY member's mask has real chemical protection;
//   investigate wreck: walk to a standoff point, watch, then walk to an inspect point; native Expansion
//               looting/targeting owns any pickup of real CE items; HC never touches an inventory;
//   react       scene / raid / gunfire: same shape, nearer standoff for allied factions (reinforce),
//               the inspect leg is the scavenge-after-the-fight leg;
//   flee        horde: withdraw along the radial away from it.
// Everything is a bounded lease: MaxLeases, per-group cooldown, per-incident responder claim, deadline,
// release on combat, dead group, retired incident or a route another system replaced. No spawning, no
// teleport, no SetPosition, no OverrideTargetPosition, no silent movement fix: the previous route and
// behaviour are restored when the lease ends.
// Offer point for the role scheduler: HCXAIIncidentResponse.HCOffer(group, home). true = the group is
// on (or just took) an incident lease; false = the scheduler keeps its own plan. Runtime acceptance PENDING.
// Native scripts-1.30.164289: 3_Game/Entities/Object.c:287 GetPosition, :517 IsAlive;
// 3_Game/Global/Game.c:1176 SurfaceY, :1196 SurfaceIsSea, :1197 SurfaceIsPond, :1535 GetTime;
// 4_World/Plugins/PluginBase/PluginTransmissionAgents.c:557 GetProtectionLevelEx (static, config-driven,
// valid-filter aware: 4_World/Entities/ItemBase.c:4077 GetProtectionLevel); 3_Game/constants.c:548 DEF_CHEMICAL;
// 4_World/Entities/ManBase/PlayerBase.c:6505 InventorySlots.MASK lookup pattern; 1_Core/proto/EnSystem.c:397 FileExist.
// Expansion AI (installed ai_scripts.pbo, read-only reference): 4_World/DayZExpansion_AI/Classes/eAIGroup.c
// :213 AddWaypoint, :222 GetWaypoints (live array), :241 ClearWaypoints, :251 SetWaypointBehaviour,
// :304 GetWaypointBehaviour, :671 GetFaction, :1123 IsInCombat, :1139 GetMember, :1185 Count (members are
// always alive; the deprecated GetAliveCount is not used); 3_Game/DayZExpansion_AI/Enums/AIenums.c:1-12
// eAIWaypointBehavior HALT/ONCE. Waypoints are index based and are not consumed on arrival.
class HCXAIIncidentRow
{
    string Response;
    float StandoffMeters;
    float AllyStandoffMeters;
    int HoldSeconds;
    float InspectMeters;
    int InspectSeconds;
    int ApproachSeconds;
}

class HCXAIIncidentPolicy
{
    int Version = 1;
    int MaxLeases = 4;
    int StepsPerTick = 2;
    float LeashMeters = 900;
    int CooldownSeconds = 300;
    int MaxCooldowns = 32;
    float ArriveMeters = 15;
    float ProtectionLevel = 0.5;
    int MaxRoutePoints = 32;
    ref array<ref HCXAIIncidentRow> Rows = new array<ref HCXAIIncidentRow>;

    protected static ref HCXAIIncidentPolicy s_Instance;
    protected static bool s_Loaded;
    protected static bool s_Logged;

    void HCAddRow(string response, float standoff, float allyStandoff, int hold, float inspectMeters, int inspectSeconds, int approach)
    {
        HCXAIIncidentRow row = new HCXAIIncidentRow;
        row.Response = response;
        row.StandoffMeters = standoff;
        row.AllyStandoffMeters = allyStandoff;
        row.HoldSeconds = hold;
        row.InspectMeters = inspectMeters;
        row.InspectSeconds = inspectSeconds;
        row.ApproachSeconds = approach;
        Rows.Insert(row);
    }

    // Source defaults; distances and windows are design budgets, not measured (two-client survey PENDING).
    // avoid: StandoffMeters is the margin beyond the zone edge, HoldSeconds the route-vet window.
    void HCDefaults()
    {
        Rows.Clear();
        HCAddRow("avoid", 30, 30, 300, 0, 0, 120);
        HCAddRow("investigate", 90, 90, 60, 25, 60, 240);
        HCAddRow("react", 70, 35, 30, 20, 45, 180);
        HCAddRow("flee", 200, 200, 90, 0, 0, 120);
    }

    HCXAIIncidentRow HCFindRow(string response)
    {
        array<ref HCXAIIncidentRow> rules = Rows;
        foreach (HCXAIIncidentRow row : rules)
        {
            if (row.Response == response) { return row; }
        }
        return null;
    }

    static bool HCRowValid(HCXAIIncidentRow row)
    {
        if (!row) { return false; }
        if (row.Response != "avoid" && row.Response != "investigate" && row.Response != "react" && row.Response != "flee") { return false; }
        if (!HCWorldIncidentPolicy.HCRange(row.StandoffMeters, 0, 2000) || !HCWorldIncidentPolicy.HCRange(row.AllyStandoffMeters, 0, 2000)) { return false; }
        if (!HCWorldIncidentPolicy.HCRange(row.InspectMeters, 0, 500)) { return false; }
        if (row.HoldSeconds < 0 || row.HoldSeconds > 3600 || row.InspectSeconds < 0 || row.InspectSeconds > 3600) { return false; }
        return row.ApproachSeconds >= 30 && row.ApproachSeconds <= 3600;
    }

    static bool HCValid(HCXAIIncidentPolicy policy)
    {
        if (!policy || policy.Version != 1) { return false; }
        if (policy.MaxLeases < 1 || policy.MaxLeases > 16 || policy.StepsPerTick < 1 || policy.StepsPerTick > 8) { return false; }
        if (policy.CooldownSeconds < 0 || policy.CooldownSeconds > 86400 || policy.MaxCooldowns < 1 || policy.MaxCooldowns > 256) { return false; }
        if (policy.MaxRoutePoints < 1 || policy.MaxRoutePoints > 128) { return false; }
        if (!HCWorldIncidentPolicy.HCRange(policy.LeashMeters, 50, 5000) || !HCWorldIncidentPolicy.HCRange(policy.ArriveMeters, 1, 100)) { return false; }
        if (!HCWorldIncidentPolicy.HCRange(policy.ProtectionLevel, 0, 1)) { return false; }
        if (!policy.Rows || policy.Rows.Count() < 1 || policy.Rows.Count() > 8) { return false; }
        for (int rowIndex = 0; rowIndex < policy.Rows.Count(); rowIndex++)
        {
            if (!HCRowValid(policy.Rows[rowIndex])) { return false; }
            for (int otherIndex = 0; otherIndex < rowIndex; otherIndex++)
            {
                if (policy.Rows[otherIndex].Response == policy.Rows[rowIndex].Response) { return false; }
            }
        }
        return true;
    }

    static bool HCFields(string encoded)
    {
        if (!HCJsonFields.Has(encoded, "Version") || !HCJsonFields.Has(encoded, "MaxLeases") || !HCJsonFields.Has(encoded, "StepsPerTick")) { return false; }
        if (!HCJsonFields.Has(encoded, "LeashMeters") || !HCJsonFields.Has(encoded, "CooldownSeconds") || !HCJsonFields.Has(encoded, "MaxCooldowns")) { return false; }
        if (!HCJsonFields.Has(encoded, "ArriveMeters") || !HCJsonFields.Has(encoded, "ProtectionLevel") || !HCJsonFields.Has(encoded, "MaxRoutePoints")) { return false; }
        if (!HCJsonFields.Has(encoded, "Rows") || !HCJsonFields.Every(encoded, "Response", 3) || !HCJsonFields.Every(encoded, "StandoffMeters", 3)) { return false; }
        if (!HCJsonFields.Every(encoded, "AllyStandoffMeters", 3) || !HCJsonFields.Every(encoded, "HoldSeconds", 3) || !HCJsonFields.Every(encoded, "InspectMeters", 3)) { return false; }
        return HCJsonFields.Every(encoded, "InspectSeconds", 3) && HCJsonFields.Every(encoded, "ApproachSeconds", 3);
    }

    static void HCInvalid(string reason)
    {
        if (s_Logged) { return; }
        s_Logged = true;
        Print("[HCX Incidents] AI_INCIDENT_POLICY_INVALID reason=" + reason + " runtime=PENDING");
    }

    static HCXAIIncidentPolicy HCGet()
    {
        if (s_Loaded) { return s_Instance; }
        s_Loaded = true;
        HCXAIIncidentPolicy policy = new HCXAIIncidentPolicy;
        string path = "$profile:HollowCountry/ai-incident-response.json";
        if (FileExist(path))
        {
            string encoded;
            string error;
            if (!HCGroupIO.Read(path, 16384, encoded)) { HCInvalid("read"); return null; }
            if (!HCFields(encoded)) { HCInvalid("fields"); return null; }
            if (!JsonFileLoader<HCXAIIncidentPolicy>.LoadData(encoded, policy, error)) { HCInvalid("parse"); return null; }
        }
        else
        {
            policy.HCDefaults();
        }
        if (!HCValid(policy)) { HCInvalid("range"); return null; }
        s_Instance = policy;
        return s_Instance;
    }
}

class HCXAIIncidentLease
{
    bool Fixture;
    // eAIGroup is not Managed, so the lease never stores it: the group is reached only through
    // Hold (retired in HCFinish), and a group with no live members ends the lease.
    ref HCXAIGroupHold Hold;
    int IncidentId;
    string Response;
    string Phase;
    vector Target;
    int Placed;
    int Until;
    int Deadline;
    ref array<vector> Saved = new array<vector>;
    eAIWaypointBehavior Behavior;
    // The exact route and behaviour this lease installed; a different live state means another controller owns the group.
    ref array<vector> Route = new array<vector>;
    eAIWaypointBehavior Installed;
    // Time the group started holding outside a gas zone with no safe waypoint left (0 = not holding).
    int HoldSince;
    void ~HCXAIIncidentLease() { HCXAIGroupHolds.Retire(Hold); }
}

// Fixture offer: transient (60 s deadline), so it keeps the group id and never a raw handle.
class HCXAIIncidentOffer
{
    int GroupId;
    int IncidentId;
    int Deadline;
}

// Cooldowns outlive their groups: keep the id (never reused), not a raw eAIGroup handle.
class HCXAIIncidentCooldown
{
    int GroupId;
    int Until;
}

class HCXAIIncidentResponse : HCModule
{
    protected static ref HCXAIIncidentResponse s_Instance;
    protected ref HCXAIIncidentPolicy m_Policy;
    protected ref array<ref HCXAIIncidentLease> m_Leases = new array<ref HCXAIIncidentLease>;
    protected ref array<ref HCXAIIncidentCooldown> m_Cooldowns = new array<ref HCXAIIncidentCooldown>;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCXAIIncidentOffer m_FixtureOffer;
    protected int m_Cursor;
    protected bool m_Running;
    protected string m_Refusal;

    override string GetName() { return "AIIncidents"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }
    override HCOperationalStatus HCGetOperationalStatus() { return HCStatus(); }

    // Offer point for the role scheduler (registration line reported to the lead).
    static bool HCOffer(eAIGroup group, vector home)
    {
        if (!s_Instance || !s_Instance.m_Running) { return false; }
        return s_Instance.HCAccept(group, home, HCWorldIncidents.HCNowSeconds());
    }

    override void OnStart(HCSettings settings)
    {
        m_Running = false;
        m_Refusal = "";
        if (!GetGame() || !GetGame().IsServer() || !IsEnabled(settings)) { return; }
        bool optedOut = FileExist("$profile:HollowCountry/acceptance/incident_response.disable");
        Print(HCV2Admission.Line("ai_incident_response", !optedOut, "native_ai_incident_survey", false) + " runtime=PENDING");
        if (optedOut) { Print("[HCX Incidents] responder off operator_marker=incident_response.disable runtime=PENDING"); return; }
        m_Policy = HCXAIIncidentPolicy.HCGet();
        if (!m_Policy)
        {
            m_Refusal = "ai_incident_policy_invalid";
            return;
        }
        m_Running = true;
        s_Instance = this;
        Print("[HCX Incidents] responder rows=" + m_Policy.Rows.Count().ToString() + " leases<=" + m_Policy.MaxLeases.ToString() + " cooldown=" + m_Policy.CooldownSeconds.ToString() + "s perception=member_sound_or_sight offer=role_scheduler runtime=PENDING");
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || m_Leases.Count() < 1) { return; }
        HCStep(HCWorldIncidents.HCNowSeconds());
        HCReached.Mark("ai_incident_response.lease_step");
    }

    override void OnStop()
    {
        int now = HCWorldIncidents.HCNowSeconds();
        while (m_Leases.Count() > 0)
        {
            HCFinish(m_Leases[0], now);
        }
        m_Running = false;
        m_FixtureOffer = null;
        m_Cooldowns.Clear();
        if (s_Instance == this) { s_Instance = null; }
    }

    HCOperationalStatus HCStatus()
    {
        bool started = m_Running;
        string refusal = m_Refusal;
        HCWorldIncidents registry = HCWorldIncidents.HCGet();
        if (m_Running && !registry.HCActive())
        {
            started = false;
            refusal = "incident_registry_off";
        }
        HCModuleReadiness.HCDerive(m_Status, started, refusal, "", "ai_incident_response_started");
        return m_Status;
    }

    void HCNote(string what, HCXAIIncidentLease lease)
    {
        string line = "[HCX Incidents] " + what + " response=" + lease.Response + " phase=" + lease.Phase;
        line = line + " incident=" + lease.IncidentId.ToString() + " leases=" + m_Leases.Count().ToString() + " runtime=PENDING";
        if (lease.Fixture) { line += " fixture=1"; }
        Print("" + line);
    }

    // ------------------------------------------------------------------ offers

    // Queue one existing pair. The role scheduler must offer this group after
    // its private busy checks; this command never borrows a route itself.
    static bool HCFixtureIncident(vector pos, bool apply, out string reason)
    {
        reason = "EnableSmokeFixtures-off";
        if (!HCAdminFixtures.HCEnabled()) { return false; }
        HCXAIIncidentResponse owner = s_Instance;
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        reason = "incident-service-unavailable";
        if (!owner || !owner.m_Running || !director || director.Phase() != "run") { return false; }
        if (owner.m_Leases.Count() >= owner.m_Policy.MaxLeases) { reason = "incident-lease-cap"; return false; }
        HCWorldIncidents registry = HCWorldIncidents.HCGet();
        int now = HCWorldIncidents.HCNowSeconds();
        HCWorldIncident selected;
        float nearest = float.MAX;
        // Use the owner's normal incident work family; never a registry probe credit.
        for (int index = 0; index < registry.HCCount(); index++)
        {
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_INCIDENT_RESPONSE, 1)) { reason = "fixture-budget"; return false; }
            HCWorldIncident row = registry.HCRowAt(index);
            if (!row || !owner.m_Policy.HCFindRow(row.Response)) { continue; }
            float gap = vector.DistanceSq(pos, row.Position);
            if (gap < nearest) { nearest = gap; selected = row; }
        }
        reason = "no-existing-incident";
        if (!selected) { return false; }
        eAIGroup chosen;
        nearest = float.MAX;
        map<int, bool> coolingGroups = new map<int, bool>;
        array<ref HCXAIIncidentCooldown> cooldowns = owner.m_Cooldowns;
        foreach (HCXAIIncidentCooldown cooldown : cooldowns)
        {
            if (cooldown.GroupId > 0 && cooldown.Until > now) { coolingGroups.Set(cooldown.GroupId, true); }
        }
        array<ref HCXAISiteState> states = director.States();
        foreach (HCXAISiteState state : states)
        {
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_INCIDENT_RESPONSE, 1)) { reason = "fixture-budget"; return false; }
            if (!state || !state.Site || !state.Qualified || state.Failed || state.Completed || !state.Patrol || !state.Patrol.m_HCLive || state.HCJourneyWalking) { continue; }
            eAIGroup group = state.Patrol.m_Group;
            if (!group || owner.HCLeaseFor(group) || HCXExpansionBridge.HCGroupIsInCombat(group) || owner.HCAlive(group) < 1) { continue; }
            if (HCBaseRaid.HCOwns(state.ProposalId) || HCAITrade.HCJourneyBusy(state.ProposalId) || HCW38SituationRuntime.HCUsed(state.ProposalId)) { continue; }
            HCXAIAdapter adapter = HCXAIService.Adapter();
            if (adapter && adapter.HCJourneyBusy(state.ProposalId)) { continue; }
            if (coolingGroups.Contains(HCXExpansionBridge.HCGroupGetID(group))) { continue; }
            vector home = state.Site.HousePosition;
            if (state.PatrolPoints.Count() > 0) { home = state.PatrolPoints[0]; }
            if (!owner.HCEligible(selected, group, home, now)) { continue; }
            float distance = vector.DistanceSq(pos, owner.HCLead(group));
            if (distance < nearest) { nearest = distance; chosen = group; }
        }
        reason = "no-eligible-group-for-nearest-incident";
        if (!chosen) { return false; }
        if (apply)
        {
            HCXAIIncidentOffer offer = new HCXAIIncidentOffer;
            offer.GroupId = HCXExpansionBridge.HCGroupGetID(chosen);
            offer.IncidentId = selected.Id;
            offer.Deadline = now + 60;
            owner.m_FixtureOffer = offer;
        }
        reason = "pair-queued-awaiting-normal-role-owner-busy-checks";
        return true;
    }

    bool HCAccept(eAIGroup group, vector home, int now)
    {
        if (!group || !m_Policy) { return false; }
        if (HCLeaseFor(group)) { return true; }
        if (HCCooling(group, now)) { return false; }
        if (m_Leases.Count() >= m_Policy.MaxLeases) { return false; }
        if (HCXExpansionBridge.HCGroupIsInCombat(group) || HCAlive(group) < 1) { return false; }
        HCWorldIncidents registry = HCWorldIncidents.HCGet();
        if (m_FixtureOffer && m_FixtureOffer.Deadline < now) { m_FixtureOffer = null; }
        if (m_FixtureOffer && m_FixtureOffer.GroupId == HCXExpansionBridge.HCGroupGetID(group))
        {
            HCWorldIncident fixtureRow = registry.HCById(m_FixtureOffer.IncidentId);
            m_FixtureOffer = null;
            if (!fixtureRow || !HCEligible(fixtureRow, group, home, now)) { return false; }
            return HCStartLease(registry, group, fixtureRow, now, true);
        }
        int skipId = 0;
        for (int attempt = 0; attempt < 2; attempt++)
        {
            HCWorldIncident best = HCBest(registry, group, home, now, skipId);
            if (!best) { return false; }
            if (HCStartLease(registry, group, best, now)) { return true; }
            skipId = best.Id;
        }
        return false;
    }

    HCXAIIncidentLease HCLeaseFor(eAIGroup group)
    {
        array<ref HCXAIIncidentLease> leases = m_Leases;
        foreach (HCXAIIncidentLease lease : leases)
        {
            if (HCXExpansionBridge.HCHoldSame(lease.Hold, group)) { return lease; }
        }
        return null;
    }

    bool HCCooling(eAIGroup group, int now)
    {
        int groupId = 0;
        if (group) { groupId = HCXExpansionBridge.HCGroupGetID(group); }
        int index = 0;
        bool cooling = false;
        while (index < m_Cooldowns.Count())
        {
            HCXAIIncidentCooldown entry = m_Cooldowns[index];
            if (entry.Until <= now)
            {
                m_Cooldowns.RemoveOrdered(index);
                continue;
            }
            if (groupId > 0 && entry.GroupId == groupId) { cooling = true; }
            index++;
        }
        return cooling;
    }

    void HCCool(HCXAIGroupHold hold, int now)
    {
        if (!hold || m_Policy.CooldownSeconds < 1) { return; }
        int coolId = HCXExpansionBridge.HCHoldId(hold);
        if (coolId <= 0) { return; }
        while (m_Cooldowns.Count() >= m_Policy.MaxCooldowns)
        {
            m_Cooldowns.RemoveOrdered(0);
        }
        HCXAIIncidentCooldown entry = new HCXAIIncidentCooldown;
        entry.GroupId = coolId;
        entry.Until = now + m_Policy.CooldownSeconds;
        m_Cooldowns.Insert(entry);
    }

    // Best usable incident for this group: gas safety first, then severity, then nearest. One shared
    // budget unit per registry row examined; a denied unit ends the scan for this tick.
    HCWorldIncident HCBest(HCWorldIncidents registry, eAIGroup group, vector home, int now, int skipId)
    {
        HCWorldIncident best = null;
        float bestScore = 0;
        vector lead = HCLead(group);
        int total = registry.HCCount();
        for (int index = 0; index < total; index++)
        {
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_INCIDENT_RESPONSE, 1)) { return best; }
            HCWorldIncident row = registry.HCRowAt(index);
            if (!row || row.Id == skipId) { continue; }
            if (!HCEligible(row, group, home, now)) { continue; }
            float score = row.Severity * 100000 - Math.Sqrt(HCFlat(row.Position, lead));
            if (row.Response == "avoid") { score = score + 1000000; }
            if (!best || score > bestScore)
            {
                best = row;
                bestScore = score;
            }
        }
        return best;
    }

    bool HCEligible(HCWorldIncident row, eAIGroup group, vector home, int now)
    {
        HCXAIIncidentRow rule = m_Policy.HCFindRow(row.Response);
        if (!rule) { return false; }
        if (!HCPerceived(row, group, now)) { return false; }
        if (row.Response == "avoid") { return HCAvoidMode(row, group) != ""; }
        float leash = m_Policy.LeashMeters;
        if (HCFlat(home, row.Position) > leash * leash) { return false; }
        if (row.Response == "flee")
        {
            float reach = row.Radius + rule.StandoffMeters;
            return HCFlat(HCLead(group), row.Position) < reach * reach;
        }
        return true;
    }

    // Perception: some living member is inside the incident's sound or sight range. Nothing else counts.
    bool HCPerceived(HCWorldIncident row, eAIGroup group, int now)
    {
        HCWorldIncidents registry = HCWorldIncidents.HCGet();
        for (int index = 0; index < HCXExpansionBridge.HCGroupCount(group); index++)
        {
            DayZPlayerImplement member = HCXExpansionBridge.HCGroupGetMember(group, index);
            if (!member || !member.IsAlive()) { continue; }
            if (registry.HCPerceives(row, member, now)) { return true; }
        }
        return false;
    }

    // ------------------------------------------------------------------ gas

    int HCAlive(eAIGroup group)
    {
        int alive = 0;
        for (int index = 0; index < HCXExpansionBridge.HCGroupCount(group); index++)
        {
            DayZPlayerImplement member = HCXExpansionBridge.HCGroupGetMember(group, index);
            if (member && member.IsAlive()) { alive++; }
        }
        return alive;
    }

    // Real, config-driven chemical protection of the mask slot (a gas mask needs a valid filter; a surgical
    // mask or a spent filter gives none). One unprotected face makes the whole group avoid the zone.
    bool HCProtected(DayZPlayerImplement member)
    {
        float level = PluginTransmissionAgents.GetProtectionLevelEx(DEF_CHEMICAL, InventorySlots.MASK, member, true);
        return level >= m_Policy.ProtectionLevel;
    }

    bool HCAllProtected(eAIGroup group)
    {
        for (int index = 0; index < HCXExpansionBridge.HCGroupCount(group); index++)
        {
            DayZPlayerImplement member = HCXExpansionBridge.HCGroupGetMember(group, index);
            if (!member || !member.IsAlive()) { continue; }
            if (!HCProtected(member)) { return false; }
        }
        return true;
    }

    float HCMargin()
    {
        HCXAIIncidentRow rule = m_Policy.HCFindRow("avoid");
        if (!rule) { return 0; }
        return rule.StandoffMeters;
    }

    // "exit" = a living member stands inside the zone, "vet" = the route enters or crosses it, "" = nothing to do.
    string HCAvoidMode(HCWorldIncident row, eAIGroup group)
    {
        if (HCAllProtected(group)) { return ""; }
        float edge = row.Radius;
        for (int index = 0; index < HCXExpansionBridge.HCGroupCount(group); index++)
        {
            DayZPlayerImplement member = HCXExpansionBridge.HCGroupGetMember(group, index);
            if (!member || !member.IsAlive()) { continue; }
            if (HCFlat(member.GetPosition(), row.Position) <= edge * edge) { return "exit"; }
        }
        array<vector> route = HCXExpansionBridge.HCGroupGetWaypoints(group);
        if (!route || route.Count() > m_Policy.MaxRoutePoints) { return ""; }
        array<vector> kept = new array<vector>();
        HCKeep(row, HCLead(group), route, kept);
        if (kept.Count() != route.Count()) { return "vet"; }
        return "";
    }

    // Points of the source route that stay outside radius + margin, with each leg checked from the previous
    // kept point (the first leg from the group's own position).
    void HCKeep(HCWorldIncident row, vector origin, array<vector> source, array<vector> kept)
    {
        float reach = row.Radius + HCMargin();
        vector previous = origin;
        for (int index = 0; index < source.Count(); index++)
        {
            vector point = source[index];
            if (HCFlat(point, row.Position) <= reach * reach) { continue; }
            if (HCLegHits(previous, point, row.Position, reach)) { continue; }
            kept.Insert(point);
            previous = point;
        }
    }

    // True when the 2D segment from..to passes within reach of the centre.
    bool HCLegHits(vector origin, vector goal, vector centre, float reach)
    {
        float legX = goal[0] - origin[0];
        float legZ = goal[2] - origin[2];
        float span = legX * legX + legZ * legZ;
        float offX = centre[0] - origin[0];
        float offZ = centre[2] - origin[2];
        float along = 0;
        if (span > 0.0001) { along = (offX * legX + offZ * legZ) / span; }
        if (along < 0) { along = 0; }
        if (along > 1) { along = 1; }
        float missX = offX - along * legX;
        float missZ = offZ - along * legZ;
        return missX * missX + missZ * missZ <= reach * reach;
    }

    // ------------------------------------------------------------------ leases

    bool HCStartLease(HCWorldIncidents registry, eAIGroup group, HCWorldIncident row, int now, bool fixture = false)
    {
        HCXAIIncidentRow rule = m_Policy.HCFindRow(row.Response);
        if (!rule) { return false; }
        string mode = "";
        bool claimed = false;
        if (row.Response == "avoid")
        {
            mode = HCAvoidMode(row, group);
            if (mode == "") { return false; }
        }
        else
        {
            if (!registry.HCClaim(row)) { return false; }
            claimed = true;
        }
        HCXAIIncidentLease lease = new HCXAIIncidentLease;
        lease.Fixture = fixture;
        lease.Hold = HCXAIGroupHolds.Follow(null, group);
        if (!lease.Hold)
        {
            if (claimed) { registry.HCRelease(row.Id); }
            return false;
        }
        lease.IncidentId = row.Id;
        lease.Response = row.Response;
        lease.Phase = "move";
        lease.Deadline = now + rule.ApproachSeconds;
        bool started = HCBorrow(lease);
        if (started && mode == "vet")
        {
            lease.Phase = "vet";
            lease.Deadline = now + rule.HoldSeconds;
            HCVet(lease, row);
        }
        else if (started)
        {
            vector target = HCRadial(row, group, mode, HCStandoff(row, rule, group));
            started = HCUsable(registry, target, row.Id);
            if (started) { HCWalk(lease, target); }
        }
        if (!started)
        {
            if (claimed) { registry.HCRelease(row.Id); }
            HCXAIGroupHolds.Retire(lease.Hold);
            lease.Hold = null;
            return false;
        }
        m_Leases.Insert(lease);
        if (lease.Fixture) { HCModuleReadiness.HCUseFixture("AIIncidents", "response_started"); }
        else { HCModuleReadiness.HCUse("AIIncidents", "response_started"); }
        HCNote("lease_start", lease);
        return true;
    }

    // Takes the group's route and behaviour for the lease; refused when it is too large to keep.
    bool HCBorrow(HCXAIIncidentLease lease)
    {
        if (!HCXExpansionBridge.HCHoldAlive(lease.Hold)) { return false; }
        array<vector> live = HCXExpansionBridge.HCHoldGetWaypoints(lease.Hold);
        if (!live || live.Count() > m_Policy.MaxRoutePoints) { return false; }
        for (int index = 0; index < live.Count(); index++)
        {
            lease.Saved.Insert(live[index]);
        }
        lease.Behavior = HCXExpansionBridge.HCHoldGetWaypointBehaviour(lease.Hold);
        return true;
    }

    void HCWalk(HCXAIIncidentLease lease, vector target)
    {
        HCXExpansionBridge.HCHoldClearWaypoints(lease.Hold);
        HCXExpansionBridge.HCHoldAddWaypoint(lease.Hold, target);
        HCXExpansionBridge.HCHoldSetWaypointBehaviour(lease.Hold, eAIWaypointBehavior.ONCE);
        lease.Target = target;
        lease.Placed = 1;
        lease.Route.Clear();
        lease.Route.Insert(target);
        lease.Installed = eAIWaypointBehavior.ONCE;
    }

    // Route vet: only waypoints that stay clear remain; nothing clear means the group holds in place.
    void HCVet(HCXAIIncidentLease lease, HCWorldIncident row)
    {
        array<vector> kept = new array<vector>();
        HCKeep(row, HCLead(lease.Hold.HCResolve()), lease.Saved, kept);
        HCXExpansionBridge.HCHoldClearWaypoints(lease.Hold);
        for (int index = 0; index < kept.Count(); index++)
        {
            HCXExpansionBridge.HCHoldAddWaypoint(lease.Hold, kept[index]);
        }
        lease.Placed = kept.Count();
        lease.Route.Clear();
        for (int copyIndex = 0; copyIndex < kept.Count(); copyIndex++)
        {
            lease.Route.Insert(kept[copyIndex]);
        }
        if (kept.Count() > 0) { lease.Target = kept[0]; }
        else { HCXExpansionBridge.HCHoldSetWaypointBehaviour(lease.Hold, eAIWaypointBehavior.HALT); }
        lease.Installed = HCXExpansionBridge.HCHoldGetWaypointBehaviour(lease.Hold);
    }

    float HCStandoff(HCWorldIncident row, HCXAIIncidentRow rule, eAIGroup group)
    {
        if (row.Faction == "") { return rule.StandoffMeters; }
        if (row.Faction == HCXFactions.HCWorldId(HCXFactions.Id(HCXExpansionBridge.HCGroupGetFaction(group)))) { return rule.AllyStandoffMeters; }
        return rule.StandoffMeters;
    }

    // Point on the radial from the incident through the group (through the member inside a zone when
    // leaving it), at radius + distance, on the ground. Never the incident position itself.
    vector HCRadial(HCWorldIncident row, eAIGroup group, string mode, float distance)
    {
        vector focus = HCLead(group);
        if (mode == "exit") { focus = HCInside(group, row); }
        float dirX = focus[0] - row.Position[0];
        float dirZ = focus[2] - row.Position[2];
        float norm = Math.Sqrt(dirX * dirX + dirZ * dirZ);
        if (norm < 0.5)
        {
            dirX = 1;
            dirZ = 0;
            norm = 1;
        }
        float reach = row.Radius + distance;
        float px = row.Position[0] + dirX / norm * reach;
        float pz = row.Position[2] + dirZ / norm * reach;
        return Vector(px, GetGame().SurfaceY(px, pz), pz);
    }

    vector HCInside(eAIGroup group, HCWorldIncident row)
    {
        float edge = row.Radius;
        for (int index = 0; index < HCXExpansionBridge.HCGroupCount(group); index++)
        {
            DayZPlayerImplement member = HCXExpansionBridge.HCGroupGetMember(group, index);
            if (!member || !member.IsAlive()) { continue; }
            if (HCFlat(member.GetPosition(), row.Position) <= edge * edge) { return member.GetPosition(); }
        }
        return HCLead(group);
    }

    // Walkable-looking target: inside the map, not open water, not inside another avoided zone.
    // Navmesh qualification of the point is native (Expansion pathing); not proven offline.
    bool HCUsable(HCWorldIncidents registry, vector point, int exceptId)
    {
        if (!HCWorldLimits.Position(point)) { return false; }
        if (GetGame().SurfaceIsSea(point[0], point[2]) || GetGame().SurfaceIsPond(point[0], point[2])) { return false; }
        float margin = HCMargin();
        for (int index = 0; index < registry.HCCount(); index++)
        {
            HCWorldIncident row = registry.HCRowAt(index);
            if (!row || row.Id == exceptId || row.Response != "avoid") { continue; }
            float reach = row.Radius + margin;
            if (HCFlat(point, row.Position) <= reach * reach) { return false; }
        }
        return true;
    }

    // ------------------------------------------------------------------ progress

    void HCStep(int now)
    {
        int steps = 0;
        while (steps < m_Policy.StepsPerTick && m_Leases.Count() > 0)
        {
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_INCIDENT_RESPONSE, 1)) { return; }
            if (m_Cursor >= m_Leases.Count()) { m_Cursor = 0; }
            HCXAIIncidentLease lease = m_Leases[m_Cursor];
            steps++;
            int before = m_Leases.Count();
            HCAdvance(lease, now);
            if (m_Leases.Count() == before) { m_Cursor++; }
        }
    }

    void HCAdvance(HCXAIIncidentLease lease, int now)
    {
        HCWorldIncidents registry = HCWorldIncidents.HCGet();
        HCWorldIncident row = registry.HCById(lease.IncidentId);
        eAIGroup group = null;
        if (lease.Hold) { group = lease.Hold.HCResolve(); }
        if (!row || !group || HCAlive(group) < 1 || HCXExpansionBridge.HCHoldIsInCombat(lease.Hold))
        {
            HCFinish(lease, now);
            return;
        }
        if (!HCMine(lease))
        {
            // Another system replaced the route: never fight it; HCFinish will not restore over it.
            HCFinish(lease, now);
            return;
        }
        HCXAIIncidentRow rule = m_Policy.HCFindRow(lease.Response);
        if (!rule)
        {
            HCFinish(lease, now);
            return;
        }
        if (lease.Phase == "vet")
        {
            if (now >= lease.Deadline && !HCHolding(lease, row, rule, now)) { HCFinish(lease, now); }
            return;
        }
        if (lease.Phase == "hold" || lease.Phase == "linger")
        {
            if (now < lease.Until) { return; }
            if (lease.Phase == "hold" && HCInspect(lease, row, rule, registry, now)) { return; }
            HCFinish(lease, now);
            return;
        }
        if (HCArrived(lease))
        {
            if (lease.Response == "avoid")
            {
                if (!HCHolding(lease, row, rule, now)) { HCFinish(lease, now); }
                return;
            }
            if (lease.Phase == "move")
            {
                lease.Phase = "hold";
                lease.Until = now + rule.HoldSeconds;
                return;
            }
            lease.Phase = "linger";
            lease.Until = now + rule.InspectSeconds;
            return;
        }
        if (now >= lease.Deadline) { HCFinish(lease, now); }
    }

    // After the watch: walk to the inspect point (the scavenge leg). Native Expansion owns whatever it
    // picks up; HC creates nothing. False when this response has no inspect leg or the point is unusable.
    bool HCInspect(HCXAIIncidentLease lease, HCWorldIncident row, HCXAIIncidentRow rule, HCWorldIncidents registry, int now)
    {
        if (rule.InspectMeters <= 0 || lease.Response == "flee" || lease.Response == "avoid") { return false; }
        eAIGroup group = lease.Hold.HCResolve();
        if (!group) { return false; }
        vector look = HCRadial(row, group, "", rule.InspectMeters);
        if (!HCUsable(registry, look, row.Id)) { return false; }
        HCWalk(lease, look);
        lease.Phase = "inspect";
        lease.Deadline = now + rule.ApproachSeconds;
        return true;
    }

    bool HCArrived(HCXAIIncidentLease lease)
    {
        float arrive = m_Policy.ArriveMeters;
        for (int index = 0; index < HCXExpansionBridge.HCHoldCount(lease.Hold); index++)
        {
            DayZPlayerImplement member = HCXExpansionBridge.HCHoldGetMember(lease.Hold, index);
            if (!member || !member.IsAlive()) { continue; }
            if (HCFlat(member.GetPosition(), lease.Target) <= arrive * arrive) { return true; }
        }
        return false;
    }

    // The lease still owns the group's route: every installed waypoint is still in place and the waypoint
    // behaviour is the one the lease set. Any other state belongs to another controller and is left alone.
    bool HCMine(HCXAIIncidentLease lease)
    {
        if (!HCXExpansionBridge.HCHoldAlive(lease.Hold)) { return false; }
        array<vector> live = HCXExpansionBridge.HCHoldGetWaypoints(lease.Hold);
        if (!live || live.Count() != lease.Route.Count()) { return false; }
        for (int index = 0; index < live.Count(); index++)
        {
            if (vector.DistanceSq(live[index], lease.Route[index]) >= 1.0) { return false; }
        }
        return HCXExpansionBridge.HCHoldGetWaypointBehaviour(lease.Hold) == lease.Installed;
    }

    // Holding windows (of the avoid rule's HoldSeconds) a gas hold may keep its lease slot before letting go.
    static const int HOLD_WINDOWS = 4;

    // Gas with nothing safe left on the route: the group holds with an empty route (no waypoint is ever put
    // back inside a live zone) and the lease stays open until the zone retires, a safe waypoint exists, or the
    // bounded hold runs out. A zone that never retires cannot pin a lease slot; the group stays halted.
    bool HCHolding(HCXAIIncidentLease lease, HCWorldIncident row, HCXAIIncidentRow rule, int now)
    {
        if (lease.Response != "avoid" || !row || lease.Saved.Count() < 1) { return false; }
        array<vector> safe = new array<vector>();
        HCKeep(row, HCLead(lease.Hold.HCResolve()), lease.Saved, safe);
        if (safe.Count() > 0) { return false; }
        if (lease.HoldSince < 1) { lease.HoldSince = now; }
        if (now - lease.HoldSince >= HCXAIIncidentResponse.HOLD_WINDOWS * (rule.HoldSeconds + 1)) { return false; }
        if (lease.Phase != "vet")
        {
            HCXExpansionBridge.HCHoldClearWaypoints(lease.Hold);
            HCXExpansionBridge.HCHoldSetWaypointBehaviour(lease.Hold, eAIWaypointBehavior.HALT);
            lease.Installed = eAIWaypointBehavior.HALT;
            lease.Placed = 0;
            lease.Route.Clear();
            lease.Phase = "vet";
        }
        lease.Deadline = now + rule.HoldSeconds + 1;
        return true;
    }

    // Ends a lease: restores the route and behaviour when the lease still owned them, releases the
    // incident claim, starts the group's cooldown (not after gas avoidance), and drops the lease.
    void HCFinish(HCXAIIncidentLease lease, int now)
    {
        HCWorldIncidents registry = HCWorldIncidents.HCGet();
        eAIGroup group = null;
        if (lease.Hold) { group = lease.Hold.HCResolve(); }
        if (group && HCAlive(group) > 0 && HCMine(lease)) { HCRestore(lease, registry); }
        if (lease.Response != "avoid")
        {
            registry.HCRelease(lease.IncidentId);
            HCCool(lease.Hold, now);
        }
        HCNote("lease_end", lease);
        int slot = m_Leases.Find(lease);
        if (slot >= 0) { m_Leases.RemoveOrdered(slot); }
        HCXAIGroupHolds.Retire(lease.Hold);
        lease.Hold = null;
    }

    // Gas leases restore the route minus any waypoint still inside a live zone (nothing safe left means an empty
    // route: hold); every other lease, and a retired zone, restores exactly the route the group had.
    void HCRestore(HCXAIIncidentLease lease, HCWorldIncidents registry)
    {
        array<vector> route = new array<vector>();
        HCWorldIncident row = registry.HCById(lease.IncidentId);
        if (row && lease.Response == "avoid") { HCKeep(row, HCLead(lease.Hold.HCResolve()), lease.Saved, route); }
        bool zoneLive = row && lease.Response == "avoid";
        if (route.Count() < 1 && !zoneLive)
        {
            for (int copyIndex = 0; copyIndex < lease.Saved.Count(); copyIndex++)
            {
                route.Insert(lease.Saved[copyIndex]);
            }
        }
        HCXExpansionBridge.HCHoldClearWaypoints(lease.Hold);
        for (int index = 0; index < route.Count(); index++)
        {
            HCXExpansionBridge.HCHoldAddWaypoint(lease.Hold, route[index]);
        }
        if (route.Count() < 1 && zoneLive)
        {
            // Nothing safe to give back while the zone is live: leave the group halted, never walking an empty route.
            HCXExpansionBridge.HCHoldSetWaypointBehaviour(lease.Hold, eAIWaypointBehavior.HALT);
            return;
        }
        HCXExpansionBridge.HCHoldSetWaypointBehaviour(lease.Hold, lease.Behavior);
    }

    // ------------------------------------------------------------------ geometry

    vector HCLead(eAIGroup group)
    {
        for (int index = 0; index < HCXExpansionBridge.HCGroupCount(group); index++)
        {
            DayZPlayerImplement member = HCXExpansionBridge.HCGroupGetMember(group, index);
            if (member && member.IsAlive()) { return member.GetPosition(); }
        }
        return Vector(0, 0, 0);
    }

    // Squared horizontal distance.
    float HCFlat(vector left, vector right)
    {
        float dx = left[0] - right[0];
        float dz = left[2] - right[2];
        return dx * dx + dz * dz;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        HCXAIIncidentResponse responder = new HCXAIIncidentResponse;
        Register(responder);
    }
}
