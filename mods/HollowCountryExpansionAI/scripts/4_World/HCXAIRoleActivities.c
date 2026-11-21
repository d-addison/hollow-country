// W70 #144/#146. Original role scheduling; no Expansion source copied.
// Native scripts-1.30.164289 (inspected read-only):
// 3_Game/gameplay.c:636 GetGame; Global/Game.c:1120 IsServer, :931 GetWorld;
// Global/World.c:28 GetDate; Entities/Object.c:287 GetPosition, :517 IsAlive;
// Entities/Man.c:21 GetIdentity; 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnConvert.c:210 DistanceSq.
// EnScript.c:94 Cast, :380 Count, :407 Insert; EnConvert.c:30 ToString.
// Expansion read-only xref/ai/4_World/DayZExpansion_AI/:
// Classes/eAIGroup.c:671 GetFaction, :1123 IsInCombat, :1139 GetMember,
// :1185 Count; Entities/AI/eAIBase.c:1936 TargetCount, :1941 GetTarget,
// :2028 GetThreatToSelf (LOS-aware); Classes/eAITarget.c:214 GetEntity.
// Classes/eAIGroup.c:222 GetWaypoints, :251 SetWaypointBehaviour,
// :304 GetWaypointBehaviour.
// Providers own routes, reservations, combat, custody and physical inventory.
// Spec -> plan -> tasks: tests/unit/test_w70_roleplan.py. runtime=PENDING.
class HCXAIRoleRule
{
    string Role;
    string Faction;
    string Kind;
    string Loadout;
    string Home;
}

class HCXAIRoleActivity
{
    string Role;
    string Activity;
    int Weight;
    int NeedWeight;
    int DangerWeight;
    int InfectedWeight;
    int NightWeight;
    bool SafeOnly;
}

class HCXAIRolePolicy
{
    static bool HCMatch(string configured, string actual)
    {
        return configured == "" || configured == actual;
    }

    static string HCDerive(array<ref HCXAIRoleRule> rules, string faction, string kind, string loadout, string home)
    {
        array<ref HCXAIRoleRule> candidates = rules;
        foreach (HCXAIRoleRule rule : candidates)
        {
            if (!rule) { continue; }
            if (HCMatch(rule.Faction, faction) && HCMatch(rule.Kind, kind) && HCMatch(rule.Loadout, loadout) && HCMatch(rule.Home, home)) { return rule.Role; }
        }
        return "";
    }

    static bool HCNight(int hour, int start, int end)
    {
        if (start == end) { return false; }
        if (start < end) { return hour >= start && hour < end; }
        return hour >= start || hour < end;
    }

    static bool HCDue(bool enabled, bool budget, int now, int nextAt, int active, int cap)
    {
        return enabled && budget && now > 0 && now >= nextAt && active < cap;
    }

    static int HCWeight(HCXAIRoleActivity row, string role, bool need, bool danger, bool infected, bool night)
    {
        if (!row || row.Role != role) { return 0; }
        if (row.SafeOnly && (danger || infected)) { return 0; }
        int weight = row.Weight;
        if (need) { weight += row.NeedWeight; }
        if (danger) { weight += row.DangerWeight; }
        if (infected) { weight += row.InfectedWeight; }
        if (night) { weight += row.NightWeight; }
        return weight;
    }

    // Deterministic weighted cycle. No RNG engine dependency; cursor tickets
    // visit every weight slot, preserving reproducible operator policy choices.
    static string HCChoose(array<ref HCXAIRoleActivity> rows, string role, bool need, bool danger, bool infected, bool night, int ticket)
    {
        int total = 0;
        array<ref HCXAIRoleActivity> choices = rows;
        foreach (HCXAIRoleActivity row : choices) { total += HCWeight(row, role, need, danger, infected, night); }
        if (total < 1 || ticket < 0) { return ""; }
        int selected = ticket % total;
        foreach (HCXAIRoleActivity option : choices)
        {
            selected -= HCWeight(option, role, need, danger, infected, night);
            if (selected < 0) { return option.Activity; }
        }
        return "";
    }
}

// All tuning belongs to this owning DTO. Optional profile role-activities.json:
// absent scalar keys retain defaults. Authored table rows must be complete;
// native JsonFileLoader's zero-fill is never interpreted as an authored value.
class HCXAIRoleConfig
{
    bool Enabled = true;
    bool EnableCarRepair = true;
    int GroupsPerTick = 1;
    int MaxActive = 4;
    int CooldownSeconds = 300;
    int RetrySeconds = 30;
    int DangerMemorySeconds = 120;
    int SupplyNeedBelow = 4;
    int NightStartHour = 20;
    int NightEndHour = 6;
    int LogSeconds = 60;
    int MaxTableRows = 64;
    int MaxConfigBytes = 32768;
    int TicketCycle = 1000000;
    float PerceivedInfectedMeters = 100;
    ref array<ref HCXAIRoleRule> Rules = new array<ref HCXAIRoleRule>;
    ref array<ref HCXAIRoleActivity> Activities = new array<ref HCXAIRoleActivity>;

    void HCXAIRoleConfig()
    {
        HCAddRule("mechanic", "", "", "HCMechanic", "");
        HCAddRule("scavenger", "scavengers", "", "", "");
        HCAddRule("raider", "raiders", "", "", "");
        HCAddRule("traveller", "travellers", "", "", "");
        HCAddRule("scavenger", "", "scavenger", "", "");
        HCAddRule("guard", "", "holdout", "", "");
        HCAddRule("guard", "", "checkpoint", "", "");
        HCAddRule("patrol", "", "", "", "");
        HCAddActivity("scavenger", "scavenge", 1, 8, 0, 0, 0, true);
        HCAddActivity("scavenger", "patrol", 2, 0, 0, 0, 0, true);
        HCAddActivity("scavenger", "hold", 0, 0, 8, 8, 4, false);
        HCAddActivity("guard", "patrol", 3, 0, 0, 0, 0, true);
        HCAddActivity("guard", "encounter", 1, 0, 4, 0, 0, false);
        HCAddActivity("guard", "hold", 1, 0, 6, 8, 4, false);
        HCAddActivity("patrol", "patrol", 5, 0, 0, 0, 0, true);
        HCAddActivity("patrol", "encounter", 1, 0, 4, 0, 0, false);
        HCAddActivity("patrol", "hold", 0, 0, 6, 8, 4, false);
        HCAddActivity("raider", "raid", 5, 2, 0, 0, 0, true);
        HCAddActivity("raider", "encounter", 1, 0, 4, 0, 0, false);
        HCAddActivity("raider", "hold", 0, 0, 6, 8, 4, false);
        HCAddActivity("traveller", "trade", 4, 2, 0, 0, 0, true);
        HCAddActivity("traveller", "patrol", 2, 0, 0, 0, 0, true);
        HCAddActivity("traveller", "hold", 0, 0, 6, 8, 4, false);
        HCAddActivity("mechanic", "repair", 5, 0, 0, 0, 0, true);
        HCAddActivity("mechanic", "hold", 0, 0, 6, 8, 4, false);
    }

    void HCAddRule(string role, string faction, string kind, string loadout, string home)
    {
        HCXAIRoleRule rule = new HCXAIRoleRule;
        rule.Role = role; rule.Faction = faction; rule.Kind = kind; rule.Loadout = loadout; rule.Home = home;
        Rules.Insert(rule);
    }

    void HCAddActivity(string role, string activity, int weight, int need, int danger, int infected, int night, bool safe)
    {
        HCXAIRoleActivity row = new HCXAIRoleActivity;
        row.Role = role; row.Activity = activity; row.Weight = weight;
        row.NeedWeight = need; row.DangerWeight = danger; row.InfectedWeight = infected;
        row.NightWeight = night; row.SafeOnly = safe;
        Activities.Insert(row);
    }

    bool HCValid()
    {
        if (GroupsPerTick < 1 || GroupsPerTick > 8 || MaxActive < 1 || MaxActive > 32) { return false; }
        if (CooldownSeconds < 1 || CooldownSeconds > 86400 || RetrySeconds < 1 || RetrySeconds > CooldownSeconds) { return false; }
        if (DangerMemorySeconds < 1 || DangerMemorySeconds > 86400 || SupplyNeedBelow < 1 || SupplyNeedBelow > 256) { return false; }
        if (NightStartHour < 0 || NightStartHour > 23 || NightEndHour < 0 || NightEndHour > 23) { return false; }
        if (LogSeconds < 1 || LogSeconds > 86400 || MaxTableRows < 1 || MaxTableRows > 128) { return false; }
        if (PerceivedInfectedMeters < 1 || PerceivedInfectedMeters > 1000) { return false; }
        if (TicketCycle < 1 || TicketCycle > 1000000000) { return false; }
        if (MaxConfigBytes < 1024 || MaxConfigBytes > 32768) { return false; }
        if (!Rules || !Activities || Rules.Count() < 1 || Activities.Count() < 1) { return false; }
        if (Rules.Count() > MaxTableRows || Activities.Count() > MaxTableRows) { return false; }
        array<ref HCXAIRoleRule> rules = Rules;
        foreach (HCXAIRoleRule rule : rules) { if (!rule || rule.Role == "") { return false; } }
        array<ref HCXAIRoleActivity> activities = Activities;
        foreach (HCXAIRoleActivity row : activities)
        {
            if (!row || row.Role == "") { return false; }
            if (row.Activity != "scavenge" && row.Activity != "patrol" && row.Activity != "hold" && row.Activity != "raid" && row.Activity != "encounter" && row.Activity != "trade" && row.Activity != "repair") { return false; }
            if (row.Weight < 0 || row.Weight > 100 || row.NeedWeight < 0 || row.NeedWeight > 100) { return false; }
            if (row.DangerWeight < 0 || row.DangerWeight > 100 || row.InfectedWeight < 0 || row.InfectedWeight > 100 || row.NightWeight < 0 || row.NightWeight > 100) { return false; }
        }
        return true;
    }

    static HCXAIRoleConfig HCLoad()
    {
        HCXAIRoleConfig config = new HCXAIRoleConfig;
        string path = "$profile:HollowCountry/role-activities.json";
        if (!FileExist(path)) { return config; }
        string text;
        string error;
        HCXAIRoleConfig decoded;
        if (!HCGroupIO.Read(path, config.MaxConfigBytes, text)) { return null; }
        if (!JsonFileLoader<HCXAIRoleConfig>.LoadData(text, decoded, error) || !decoded) { return null; }
        // Scalar omissions retain defaults; table omissions retain the entire
        // compiled table. An explicit empty/malformed table is an operator error.
        if (HCJsonFields.Has(text, "Enabled")) { config.Enabled = decoded.Enabled; }
        if (HCJsonFields.Has(text, "EnableCarRepair")) { config.EnableCarRepair = decoded.EnableCarRepair; }
        if (HCJsonFields.Has(text, "GroupsPerTick")) { config.GroupsPerTick = decoded.GroupsPerTick; }
        if (HCJsonFields.Has(text, "MaxActive")) { config.MaxActive = decoded.MaxActive; }
        if (HCJsonFields.Has(text, "CooldownSeconds")) { config.CooldownSeconds = decoded.CooldownSeconds; }
        if (HCJsonFields.Has(text, "RetrySeconds")) { config.RetrySeconds = decoded.RetrySeconds; }
        if (HCJsonFields.Has(text, "DangerMemorySeconds")) { config.DangerMemorySeconds = decoded.DangerMemorySeconds; }
        if (HCJsonFields.Has(text, "SupplyNeedBelow")) { config.SupplyNeedBelow = decoded.SupplyNeedBelow; }
        if (HCJsonFields.Has(text, "NightStartHour")) { config.NightStartHour = decoded.NightStartHour; }
        if (HCJsonFields.Has(text, "NightEndHour")) { config.NightEndHour = decoded.NightEndHour; }
        if (HCJsonFields.Has(text, "LogSeconds")) { config.LogSeconds = decoded.LogSeconds; }
        if (HCJsonFields.Has(text, "MaxTableRows")) { config.MaxTableRows = decoded.MaxTableRows; }
        if (HCJsonFields.Has(text, "PerceivedInfectedMeters")) { config.PerceivedInfectedMeters = decoded.PerceivedInfectedMeters; }
        if (HCJsonFields.Has(text, "TicketCycle")) { config.TicketCycle = decoded.TicketCycle; }
        if (HCJsonFields.Has(text, "MaxConfigBytes")) { config.MaxConfigBytes = decoded.MaxConfigBytes; }
        if (HCJsonFields.Has(text, "Rules"))
        {
            string ruleImage = HCXAIRoleJson.HCArray(text, "Rules");
            if (ruleImage == "") { return null; }
            if (!HCJsonFields.Every(ruleImage, "Role", 2) || !HCJsonFields.Every(ruleImage, "Faction", 2) || !HCJsonFields.Every(ruleImage, "Kind", 2)) { return null; }
            if (!HCJsonFields.Every(ruleImage, "Loadout", 2) || !HCJsonFields.Every(ruleImage, "Home", 2)) { return null; }
            config.Rules = decoded.Rules;
        }
        if (HCJsonFields.Has(text, "Activities"))
        {
            string activityImage = HCXAIRoleJson.HCArray(text, "Activities");
            if (activityImage == "") { return null; }
            if (!HCJsonFields.Every(activityImage, "Role", 2) || !HCJsonFields.Every(activityImage, "Activity", 2) || !HCJsonFields.Every(activityImage, "Weight", 2)) { return null; }
            if (!HCJsonFields.Every(activityImage, "NeedWeight", 2) || !HCJsonFields.Every(activityImage, "DangerWeight", 2) || !HCJsonFields.Every(activityImage, "InfectedWeight", 2)) { return null; }
            if (!HCJsonFields.Every(activityImage, "NightWeight", 2) || !HCJsonFields.Every(activityImage, "SafeOnly", 2)) { return null; }
            config.Activities = decoded.Activities;
        }
        if (!config.HCValid() || text.Length() > config.MaxConfigBytes) { return null; }
        return config;
    }
}

// Bounded top-level table extraction after successful JSON decoding. Strings
// and escaped brackets are skipped. Every() can then enforce each row at depth
// two without confusing Rules and Activities or accepting nested lookalikes.
// Native EnString.c:113 Substring, :199 Length, :448 Get.
class HCXAIRoleJson
{
    // Per-character reads go through the shared 1 KB HCTextWindow (boot 084: raw Get cost grows
    // with the text size); the extracted array is copied out in clamped 1 KB pieces.
    static string HCArray(string text, string key)
    {
        HCTextWindow window = new HCTextWindow(text);
        int length = text.Length();
        int cursor = 0;
        int depth = 0;
        int start = -1;
        bool selected = false;
        while (cursor < length)
        {
            string token = window.At(cursor);
            if (token == "\"")
            {
                int keyStart = cursor + 1;
                cursor = keyStart;
                while (cursor < length && window.At(cursor) != "\"")
                {
                    if (window.At(cursor) == "\\") { cursor++; }
                    cursor++;
                }
                int after = cursor + 1;
                while (after < length && (window.At(after) == " " || window.At(after) == "\n" || window.At(after) == "\r" || window.At(after) == "\t")) { after++; }
                if (depth == 1 && after < length && window.At(after) == ":") { selected = HCJsonFields.KeyMatchesAt(window, keyStart, cursor, key); }
            }
            else
            {
                if (token == "[" && depth == 1 && selected) { start = cursor; }
                if (token == "{" || token == "[") { depth++; }
                if (token == "}" || token == "]")
                {
                    if (token == "]" && depth == 2 && start >= 0)
                    {
                        string image = "";
                        int offset = start;
                        int stop = cursor + 1;
                        while (offset < stop)
                        {
                            int piece = stop - offset;
                            if (piece > 1024) { piece = 1024; }
                            image = image + text.Substring(offset, piece);
                            offset = offset + piece;
                        }
                        return image;
                    }
                    depth--;
                }
            }
            cursor++;
        }
        return "";
    }
}

// Short process-local scheduling lease, never a party or cargo identity. Native
// expiry releases only our HALT behaviour; it never writes positions or targets.
// Expansion Classes/eAIGroup.c:222 GetWaypoints, :251 SetWaypointBehaviour,
// :304 GetWaypointBehaviour;
// 3_Game/DayZExpansion_AI/Enums/AIenums.c:1-6 HALT/LOOP/ALTERNATE/ONCE.
class HCXAIRoleLease
{
    eAIGroup Group;
    int Until;
    bool Held;
    eAIWaypointBehavior Previous;
    string LeaseId;

    bool HCProviderBusy()
    {
        if (LeaseId == "") { return false; }
        if (HCBaseRaid.HCOwns(LeaseId)) { return true; }
        HCPickers pickers = HCPickers.Get();
        HCScavengeTrip trip;
        if (pickers) { trip = pickers.HCTrip(); }
        if (trip && trip.m_State && trip.m_State.LeaseId == LeaseId)
        {
            string phase = trip.m_State.Phase;
            if (trip.m_Busy || phase == "leaving" || phase == "acquiring" || phase == "returning" || phase == "depositing") { return true; }
        }
        HCAITrade trade = HCAITrade.HCGet();
        HCTradeState row;
        if (trade) { row = trade.HCState(); }
        if (trade && trade.HCTrading() && row && (row.LeftLease == LeaseId || row.RightLease == LeaseId)) { return true; }
        return false;
    }

    void HCRelease()
    {
        if (Held && Group && HCXExpansionBridge.HCGroupGetWaypointBehaviour(Group) == eAIWaypointBehavior.HALT) { HCXExpansionBridge.HCGroupSetWaypointBehaviour(Group, Previous); }
        Held = false;
    }
}

modded class HCXAISiteState
{
    int HCW70NextAt;
    int HCW70PlaceCursor;
    string HCW70Place;
    int HCW70DangerUntil;
    int HCW70Ticket;
    int HCW70LogAt;
    string HCW70LastLog;
}

// Narrow bridge to the EXISTING installed port. It retains surveyed-pair,
// hostility and custody validation; never constructs or replaces a combat port.
modded class HCFactionConflict
{
    static bool HCW70Offer(string place, string leftFaction, string rightFaction, string lease)
    {
        if (!s_Active || !s_CombatPort) { return false; }
        if (!s_CombatPort.HCOffer(place, leftFaction, rightFaction)) { return false; }
        if (!s_Instance || !s_Instance.m_Current) { return false; }
        return s_Instance.m_Current.LeftLease == lease || s_Instance.m_Current.RightLease == lease;
    }
}

// Call the existing funded producer's public planning entry. Calling HCBegin
// directly here would bypass its retained homes, route and loss receipt. Only
// an already selected, funded matching pair can advance through this role hook.
class HCXAIRoleTradePort
{
    protected static HCXAITradeProducer s_Producer;
    static void HCBind(HCXAITradeProducer producer) { s_Producer = producer; }
    static void HCUnbind(HCXAITradeProducer producer)
    {
        if (s_Producer == producer) { s_Producer = null; }
    }

    static string HCOffer(string leftLease, string rightLease)
    {
        HCXAITradeProducer producer = s_Producer;
        if (!producer || !producer.m_Planning || producer.m_Travelling || producer.m_Returning) { return "TRADE_FUNDED_PLAN_ABSENT"; }
        if (producer.m_LeftLease != leftLease || producer.m_RightLease != rightLease) { return "TRADE_DIFFERENT_FUNDED_PAIR"; }
        producer.HCPlan();
        if (producer.m_Travelling) { return ""; }
        return "TRADE_EXISTING_PLAN_PENDING";
    }
}

// This extends the concrete producer's existing lifecycle, avoiding a call
// from an earlier HCXAIAdapter modded link to later-added adapter members.
modded class HCXAITradeProducer
{
    override void HCOpen(HCXAITradeAdapter port)
    {
        super.HCOpen(port);
        HCXAIRoleTradePort.HCBind(this);
    }

    override void HCClose()
    {
        HCXAIRoleTradePort.HCUnbind(this);
        super.HCClose();
    }
}

class HCXAIRoleActivities : HCModule
{
    protected ref HCXAIRoleConfig m_Config;
    protected ref HCPerfSlices m_Work = new HCPerfSlices("Roles");
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected bool m_Running;
    protected int m_Cursor;
    protected ref array<ref HCXAIRoleLease> m_Leases = new array<ref HCXAIRoleLease>;
    protected int m_LeaseCursor;
    protected string m_Fault;
    protected bool m_RaidMissingLogged;
    protected string m_DirectorState = "requested";
    protected string m_DirectorReason = "ROLE_SITE_OWNER_PENDING";
    protected string m_OwnerLog;

    protected void HCObserveSiteOwner(HCXAISiteDirector director)
    {
        m_DirectorState = "requested";
        m_DirectorReason = "ROLE_SITE_OWNER_MISSING";
        if (director)
        {
            HCOperationalStatus siteStatus = director.HCGetOperationalStatus();
            m_DirectorState = siteStatus.HCState();
            m_DirectorReason = siteStatus.HCReason();
        }
        string signature = m_DirectorState + ":" + m_DirectorReason;
        if (signature == m_OwnerLog) { return; }
        m_OwnerLog = signature;
        Print("[HC Roles] site_owner state=" + m_DirectorState + " reason=" + m_DirectorReason + " runtime=PENDING");
    }

    protected bool HCHasGroupLease(eAIGroup group)
    {
        array<ref HCXAIRoleLease> activeLeases = m_Leases;
        foreach (HCXAIRoleLease activeLease : activeLeases)
        {
            if (activeLease.Group == group) { return true; }
        }
        return false;
    }

    override string GetName() { return "AIRoles"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }
    override HCOperationalStatus HCGetOperationalStatus()
    {
        if (m_Running && m_DirectorState != "ready")
        {
            string ownerState = "requested";
            if (m_DirectorState == "refused" || m_DirectorState == "off" || m_DirectorState == "degraded") { ownerState = "degraded"; }
            m_Status.HCPublish(ownerState, m_DirectorReason);
            return m_Status;
        }
        HCModuleReadiness.HCDerive(m_Status, m_Running, m_Fault, "", "role_policy_loaded_site_owner_running");
        return m_Status;
    }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame() || !GetGame().IsServer()) { m_Fault = "ROLE_SERVER_REQUIRED"; return; }
        m_Config = HCXAIRoleConfig.HCLoad();
        if (!m_Config)
        {
            m_Fault = "ROLE_CONFIG_INVALID";
            Print("[HC Roles] admission refused reason=ROLE_CONFIG_INVALID runtime=PENDING");
            return;
        }
        bool enabled = IsEnabled(settings) && m_Config.Enabled;
        if (FileExist("$profile:HollowCountry/acceptance/role_activities.disable")) { enabled = false; }
        m_Running = HCV2Admission.Admitted(enabled);
        Print(HCV2Admission.Line("AIRoles", enabled, "role_activities", false) + " runtime=PENDING");
    }

    protected void HCRefuse(HCXAISiteState state, int groupIndex, string role, string activity, string reason, int now)
    {
        string outcome = "refused";
        if (reason == "") { outcome = "started"; }
        string signature = role + ":" + activity + ":" + reason;
        if (state.HCW70LastLog == signature || now < state.HCW70LogAt) { return; }
        state.HCW70LastLog = signature;
        state.HCW70LogAt = now + m_Config.LogSeconds;
        string line = "[HC Roles] group=" + groupIndex.ToString() + " role=" + role + " activity=" + activity;
        Print(line + " " + outcome + " reason=" + reason + " runtime=PENDING");
    }

    protected string HCStart(HCXAISiteDirector director, HCXAISiteState state, HCXAISiteState partner, eAIGroup group, string activity, vector home, int now)
    {
        if (activity == "scavenge")
        {
            HCPickers pickers = HCPickers.Get();
            if (!pickers) { return "PICKER_OWNER_MISSING"; }
            director.HCParty(state, now);
            HCScavengeTrip trip = pickers.HCTrip();
            if (trip && trip.m_State && trip.m_State.LeaseId == state.ProposalId && trip.m_State.Phase == "leaving") { return ""; }
            return "PICKER_OFFER_NOT_STARTED";
        }
        if (activity == "patrol" || activity == "hold")
        {
            // Reuse the native waypoint controller and its combat response.
            // HALT is a temporary behavior lease; endpoints stay unchanged.
            if (state.PatrolPoints.Count() < 1) { return "PATROL_ROUTE_ABSENT"; }
            if (activity == "patrol")
            {
                if (HCXExpansionBridge.HCGroupGetWaypointBehaviour(group) == eAIWaypointBehavior.HALT) { return "PATROL_HALTED"; }
                array<vector> route = HCXExpansionBridge.HCGroupGetWaypoints(group);
                if (!route || route.Count() < 1) { return "PATROL_ROUTE_ABSENT"; }
            }
            if (activity == "hold") { HCXExpansionBridge.HCGroupSetWaypointBehaviour(group, eAIWaypointBehavior.HALT); }
            return "";
        }
        if (activity == "raid")
        {
            if (HCBaseRaid.HCOwns(state.ProposalId)) { return "RAID_ALREADY_RESERVED"; }
            // The public raid owner senses/warns/reserves its own party. A role
            // offer cannot skip that warning or manufacture an observed camp.
            if (!m_RaidMissingLogged)
            {
                m_RaidMissingLogged = true;
                Print("[HC Roles] RAID_GROUP_OFFER_PORT_MISSING existing_warned_raid_owner_retained=1 runtime=PENDING");
            }
            return "RAID_AWAITING_PERCEIVED_WARNED_CAMP";
        }
        if (activity == "encounter")
        {
            if (!partner || !partner.Site || !partner.Patrol || !partner.Patrol.m_Group) { return "ENCOUNTER_PARTNER_ABSENT"; }
            string leftFaction = HCXFactions.HCWorldId(HCXFactions.Id(HCXExpansionBridge.HCGroupGetFaction(group)));
            string rightFaction = HCXFactions.HCWorldId(HCXFactions.Id(HCXExpansionBridge.HCGroupGetFaction(partner.Patrol.m_Group)));
            if (state.HCW70Place == "")
            {
                HCWorldMaterializer materializer = HCWorldMaterializer.HCDebugGet();
                if (!materializer || materializer.HCDebugProposalCount() < 1) { return "ENCOUNTER_PLACE_ABSENT"; }
                state.HCW70PlaceCursor = state.HCW70PlaceCursor % materializer.HCDebugProposalCount();
                HCDebugProposalRow proposal = materializer.HCDebugProposal(state.HCW70PlaceCursor);
                state.HCW70PlaceCursor++;
                if (!proposal || proposal.Id != state.ProposalId || proposal.State != "claimed") { return "ENCOUNTER_PLACE_LOOKUP_PENDING"; }
                state.HCW70Place = proposal.PlaceId;
            }
            if (HCFactionConflict.HCW70Offer(state.HCW70Place, leftFaction, rightFaction, state.ProposalId)) { return ""; }
            return "ENCOUNTER_SURVEYED_PAIR_REFUSED";
        }
        if (activity == "trade")
        {
            HCAITrade trade = HCAITrade.HCGet();
            if (!trade || !partner || !state.Transient || !partner.Transient) { return "TRADE_FUNDED_PAIR_ABSENT"; }
            if (trade.HCTrading()) { return "TRADE_ALREADY_ACTIVE"; }
            return HCXAIRoleTradePort.HCOffer(state.ProposalId, partner.ProposalId);
        }
        if (activity == "repair")
        {
            if (!m_Config.EnableCarRepair) { return "REPAIR_OPERATOR_OFF"; }
            if (HCXAICarRepair.HCOffer(group, home)) { return ""; }
            return "REPAIR_OFFER_REFUSED";
        }
        return "ROLE_ACTIVITY_UNSUPPORTED";
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || !m_Config) { return; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        this.HCObserveSiteOwner(director);
        // One expiry per tick, independent of the director retaining a state.
        // This bounds release work and prevents retired groups leaking slots.
        if (m_Leases.Count() > 0)
        {
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_ROLES, 1)) { return; }
            m_LeaseCursor = m_LeaseCursor % m_Leases.Count();
            HCXAIRoleLease expiring = m_Leases[m_LeaseCursor];
            HCReached.Mark("ai_roles.lease");
            bool expired = HCWorldClock.UTC() >= expiring.Until;
            if (expired && expiring.HCProviderBusy()) { expired = false; }
            if (expired || !expiring.Group || HCXExpansionBridge.HCGroupCount(expiring.Group) < 1)
            {
                expiring.HCRelease();
                m_Leases.RemoveOrdered(m_LeaseCursor);
            }
            else { m_LeaseCursor++; }
        }
        if (!director || director.Phase() != "run") { return; }
        array<ref HCXAISiteState> states = director.States();
        if (!states || states.Count() < 1) { return; }
        m_Work.HCReset(m_Config.GroupsPerTick);
        int visited = 0;
        while (visited < m_Config.GroupsPerTick && visited < states.Count())
        {
            if (!m_Work.HCContinue()) { return; }
            // Integration requests a separate consumer id. Until assigned, use
            // the existing conflict family rather than an unregistered bit.
            bool granted = HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_ROLES, 1);
            if (!granted) { return; }
            m_Cursor = m_Cursor % states.Count();
            int groupIndex = m_Cursor;
            HCXAISiteState state = states[m_Cursor];
            m_Cursor++;
            visited++;
            if (!state) { continue; }
            int now = HCWorldClock.UTC();
            if (!state.Site || !state.Qualified || state.Failed || state.Completed || !state.Patrol || !state.Patrol.m_HCLive) { continue; }
            eAIGroup group = state.Patrol.m_Group;
            if (!group || HCXExpansionBridge.HCGroupCount(group) < 1 || this.HCHasGroupLease(group)) { continue; }
            if (HCXExpansionBridge.HCGroupIsInCombat(group)) { state.HCW70DangerUntil = now + m_Config.DangerMemorySeconds; }
            // Never steal a reserved route/cargo controller. Native combat
            // remains free to act during every role lease.
            if (HCBaseRaid.HCOwns(state.ProposalId)) { continue; }
            HCPickers pickerOwner = HCPickers.Get();
            HCScavengeTrip liveTrip;
            if (pickerOwner) { liveTrip = pickerOwner.HCTrip(); }
            if (liveTrip && liveTrip.m_State && liveTrip.m_State.LeaseId == state.ProposalId)
            {
                string tripPhase = liveTrip.m_State.Phase;
                if (tripPhase == "leaving" || tripPhase == "acquiring" || tripPhase == "returning" || tripPhase == "depositing") { continue; }
            }
            HCAITrade tradeOwner = HCAITrade.HCGet();
            HCTradeState tradeState;
            if (tradeOwner) { tradeState = tradeOwner.HCState(); }
            if (tradeOwner && tradeOwner.HCTrading() && tradeState)
            {
                if (tradeState.LeftLease == state.ProposalId || tradeState.RightLease == state.ProposalId) { continue; }
            }
            // E1: a perceived world incident (gas, wreck, fight, horde) preempts a new
            // role pick; the responder owns its own lease, budget and route restore.
            vector incidentHome = state.Site.HousePosition;
            if (state.PatrolPoints.Count() > 0) { incidentHome = state.PatrolPoints[0]; }
            if (HCXAIIncidentResponse.HCOffer(group, incidentHome)) { continue; }
            if (!HCXAIRolePolicy.HCDue(m_Running, granted, now, state.HCW70NextAt, m_Leases.Count(), m_Config.MaxActive)) { continue; }
            HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(state.ProposalId);
            string homeId = "";
            vector home = state.Site.HousePosition;
            if (state.PatrolPoints.Count() > 0) { home = state.PatrolPoints[0]; }
            HCAICampRoutineView camp;
            HCHoldouts camps = HCHoldouts.Get();
            if (identity)
            {
                homeId = identity.HCCampId();
                if (camps) { camp = camps.HCRoutineView(identity); }
            }
            bool need = false;
            if (camp && camp.Home)
            {
                home = camp.Home.HousePos;
                need = camp.Supply < m_Config.SupplyNeedBelow;
                if (camp.Home.State == "ALERT") { state.HCW70DangerUntil = now + m_Config.DangerMemorySeconds; }
            }
            bool infected = false;
            eAIBase actor = eAIBase.Cast(HCXExpansionBridge.HCGroupGetMember(group, 0));
            if (actor && HCXExpansionBridge.HCBaseIsAlive(actor) && !HCXExpansionBridge.HCBaseGetIdentity(actor) && HCXExpansionBridge.HCBaseTargetCount(actor) > 0 && HCXExpansionBridge.HCBaseGetThreatToSelf(actor) > 0)
            {
                eAITarget perceived = HCXExpansionBridge.HCBaseGetTarget(actor);
                if (perceived)
                {
                    ZombieBase perceivedInfected = ZombieBase.Cast(HCXExpansionBridge.HCTargetGetEntity(perceived));
                    float perceivedRangeSq = m_Config.PerceivedInfectedMeters * m_Config.PerceivedInfectedMeters;
                    if (perceivedInfected && vector.DistanceSq(HCXExpansionBridge.HCBaseGetPosition(actor), perceivedInfected.GetPosition()) <= perceivedRangeSq) { infected = true; }
                }
            }
            int year; int month; int day; int hour; int minute;
            GetGame().GetWorld().GetDate(year, month, day, hour, minute);
            bool night = HCXAIRolePolicy.HCNight(hour, m_Config.NightStartHour, m_Config.NightEndHour);
            string faction = HCXFactions.HCWorldId(HCXFactions.Id(HCXExpansionBridge.HCGroupGetFaction(group)));
            string role = HCXAIRolePolicy.HCDerive(m_Config.Rules, faction, state.Site.Kind, state.Site.Loadout, homeId);
            string activity = HCXAIRolePolicy.HCChoose(m_Config.Activities, role, need, now < state.HCW70DangerUntil, infected, night, state.HCW70Ticket);
            state.HCW70Ticket = (state.HCW70Ticket + 1) % m_Config.TicketCycle;
            HCXAISiteState partner = states[m_Cursor % states.Count()];
            if (partner == state || !partner || partner.Completed || partner.Failed || !partner.Qualified) { partner = null; }
            eAIWaypointBehavior previous = HCXExpansionBridge.HCGroupGetWaypointBehaviour(group);
            string reason = HCStart(director, state, partner, group, activity, home, now);
            state.HCW70NextAt = now + m_Config.RetrySeconds;
            if (reason == "")
            {
                state.HCW70NextAt = now + m_Config.CooldownSeconds;
                HCXAIRoleLease lease = new HCXAIRoleLease;
                lease.Group = group;
                lease.LeaseId = state.ProposalId;
                lease.Until = state.HCW70NextAt;
                lease.Held = activity == "hold";
                lease.Previous = previous;
                m_Leases.Insert(lease);
            }
            HCRefuse(state, groupIndex, role, activity, reason, now);
        }
    }

    override void OnStop()
    {
        m_Running = false;
        array<ref HCXAIRoleLease> leases = m_Leases;
        foreach (HCXAIRoleLease lease : leases) { lease.HCRelease(); }
        m_Leases.Clear();
    }
}

// HCModule.c currently registers two base modules; 57 source registration
// lines across both addons, below the 64 cap. No edit to shared HCModule.c.
modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCXAIRoleActivities());
    }
}
