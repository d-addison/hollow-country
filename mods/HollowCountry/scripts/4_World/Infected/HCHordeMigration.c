// LC-T312 / #96, EnableWorld; EXP-S4 is logged, never an admission veto.
// Native references in scripts-1.30.164289:
// 3_Game/AI/AIGroupBehaviour.c:9,14 waypoint DTO, :27 SetWaypoints;
// AIGroup.c:14 GetBehaviour, AIAgent.c:7 GetGroup; AIWorld.c:122/98
// SampleNavmeshPosition/FindPath via HCNativeInfectedPack.Reachable;
// 3_Game/Entities/DayZAnimal.c:193 GetAIAgent (DayZCreatureAI).
// 3_Game/Entities/Object.c:287 GetPosition, :517 IsAlive, :994 GetHealth;
// 4_World/Entities/Creatures/Infected/ZombieBase.c:182 GetMindStateSynced;
// 3_Game/Global/Game.c:1176 SurfaceY; 1_Core/proto/EnConvert.c:153,169,210 vector Normalize,
// Length, DistanceSq; :30 int.ToString;
// EnMath.c:553,566 Min/Max; EnScript.c:380,385,407 arrays; EnDebug.c:96 Print.
// Existing CE bodies form admitted native packs and walk native paths.
// CE seeds are adopted; HCHordeReinforce owns bounded supplemental creation/cleanup.
// Runtime herd movement, perception, replication and two clients stay pending.
// HC-46 / #121: finite observed noise, surveyed native points only. HC-11 owns
// canonical spec/plan/tasks; owner Wave 3 task is the source contract here.
// Survey content and successful FindPath are not traversal/perception evidence.
// 3_Game/Global/Game.c:934 GetWorldName; HCGroupJson.Load reuses capped HCGroupIO (EnSystem.c:417,425,443;
// 3_Game/tools/JsonFileLoader.c:69 LoadData). No profile writes or extra timer.
class HCHordeRouteDefaults
{
    // Provisional fractions of vanilla's ~1000 m network bubble / rifle hearing.
    // Existing drift envelopes are retained, never expanded by route content.
    float VanillaNetworkBubbleMetres = 1000;
    float VanillaRifleHearingMetres = 1000;
    float CueRangeMetres = 480;
    float SurveyBindMetres = 120;
    float CohesionMetres = 100;
    float ArrivalMetres = 8;
    float NativeSegmentMetres = 120;
    float ProgressMetres = 1;
    int MaxMembers = HCHordeLimits.MAX_PACK;
    int MaxHops = 2;
    float MaxNoiseSeconds = 60;
    float CooldownSeconds = 180;
    float StallSeconds = 90;
}

class HCHordeRouteSurvey
{
    string Id;
    string Place;
    bool Surveyed;
    string Evidence;
    ref array<vector> Nodes = new array<vector>;
}

class HCHordeRouteDocument
{
    int SchemaVersion;
    string WorldName;
    bool Enabled;
    ref HCHordeRouteDefaults Defaults = new HCHordeRouteDefaults;
    ref array<ref HCHordeRouteSurvey> Routes = new array<ref HCHordeRouteSurvey>;
}

class HCHordeRoutes
{
    protected static ref HCHordeRouteDocument s_Document;
    protected static string s_Reason = "ROUTE_SURVEY_NOT_LOADED";
    protected static ref HCActivityCounters s_Activity;

    static HCActivityCounters HCActivity()
    {
        if (!s_Activity) { s_Activity = new HCActivityCounters("authored_bound local_offer native_admitted native_refused legs_started legs_finished reached expired interrupted stalled invalid", "[HC HordeRoutes]"); }
        return s_Activity;
    }

    // A local offer is a CE-observed destination, not a surveyed corridor or
    // perception receipt. Native Start validates its only leg before transfer.
    // <=MAX_PACK candidates, <=100 m from the fixed offer anchor, no world scan.
    static HCHordeRouteSurvey HCLocalOffer(vector anchor, array<HCInfectedActor> candidates)
    {
        vector destination;
        float farthest = 16 * 16;
        foreach (HCInfectedActor actor : candidates)
        {
            if (!actor || !actor.InfectedEntity) { continue; }
            vector point = actor.InfectedEntity.GetPosition();
            float distance = vector.DistanceSq(anchor, point);
            if (!HCInfectedStore.ValidPosition(point) || distance <= farthest || distance > 10000) { continue; }
            farthest = distance;
            destination = point;
        }
        if (farthest <= 16 * 16) { return null; }
        HCHordeRouteSurvey route = new HCHordeRouteSurvey;
        route.Id = "local-ce-leg";
        route.Evidence = "ce_position_native_path_pending";
        route.Nodes.Insert(destination);
        HCActivity().Add("local_offer");
        return route;
    }

    static HCHordeRouteDefaults Defaults()
    {
        if (!s_Document) { return null; }
        return s_Document.Defaults;
    }

    static bool ValidDefaults(HCHordeRouteDefaults cfg)
    {
        if (!cfg) { return false; }
        HCHordeRouteDefaults ceiling = new HCHordeRouteDefaults;
        if (cfg.VanillaNetworkBubbleMetres != ceiling.VanillaNetworkBubbleMetres || cfg.VanillaRifleHearingMetres != ceiling.VanillaRifleHearingMetres) { return false; }
        if (!(cfg.CueRangeMetres > 0 && cfg.CueRangeMetres <= ceiling.CueRangeMetres)) { return false; }
        if (!(cfg.SurveyBindMetres > 0 && cfg.SurveyBindMetres <= ceiling.SurveyBindMetres)) { return false; }
        if (cfg.SurveyBindMetres > cfg.CueRangeMetres) { return false; }
        // The unchanged observer veto was designed for the original 100 m pack.
        if (!(cfg.CohesionMetres > 0 && cfg.CohesionMetres <= ceiling.CohesionMetres)) { return false; }
        if (!(cfg.NativeSegmentMetres > 0 && cfg.NativeSegmentMetres <= ceiling.NativeSegmentMetres)) { return false; }
        if (!(cfg.ArrivalMetres > 0 && cfg.ArrivalMetres <= ceiling.ArrivalMetres)) { return false; }
        if (!(cfg.ProgressMetres > 0 && cfg.ProgressMetres <= cfg.ArrivalMetres)) { return false; }
        if (cfg.MaxMembers < 1 || cfg.MaxMembers > HCHordeLimits.MAX_PACK || cfg.MaxHops < 0 || cfg.MaxHops > 2) { return false; }
        return cfg.MaxNoiseSeconds > 0 && cfg.MaxNoiseSeconds <= 60 && cfg.CooldownSeconds >= cfg.MaxNoiseSeconds && cfg.CooldownSeconds <= 600 && cfg.StallSeconds > 0 && cfg.StallSeconds <= 90;
    }

    static bool ValidSurvey(HCHordeRouteSurvey route, HCHordeRouteDefaults cfg)
    {
        if (!route || !route.Surveyed || route.Id == "" || route.Id.Length() > 64 || route.Evidence == "" || route.Evidence.Length() > 128) { return false; }
        if (!route.Nodes || route.Nodes.Count() < 2 || route.Nodes.Count() > 8) { return false; }
        vector previous;
        int index = 0;
        array<vector> routeNodes = route.Nodes;
        foreach (vector point : routeNodes)
        {
            if (!HCInfectedStore.ValidPosition(point)) { return false; }
            if (index > 0)
            {
                float lengthSq = vector.DistanceSq(previous, point);
                if (!(lengthSq > 0 && lengthSq <= cfg.NativeSegmentMetres * cfg.NativeSegmentMetres)) { return false; }
            }
            previous = point;
            index++;
        }
        return true;
    }

    static bool HCLoad(string world)
    {
        s_Document = null;
        s_Reason = "ROUTE_SURVEY_MISSING_OR_INVALID";
        HCHordeRouteDocument document;
        if (!HCGroupJson<HCHordeRouteDocument>.Load("$mission:hollow-country/infected/route-surveys.json", 32768, document)) { return false; }
        return HCBind(document, world);
    }

    // Also the restricted offline data port. Never creates/adopts a cohort.
    static bool HCBind(HCHordeRouteDocument document, string world)
    {
        s_Document = null;
        s_Reason = "ROUTE_DOCUMENT_INVALID";
        if (!document || document.SchemaVersion != 1 || document.WorldName != world || !ValidDefaults(document.Defaults)) { return false; }
        if (!document.Routes || document.Routes.Count() > 8) { return false; }
        // The shipped schema-1 pilot had a fixed six-member ceiling. Migrate
        // legacy six-member defaults in memory; explicit smaller caps remain authoritative.
        if (document.Defaults.MaxMembers == 6) { document.Defaults.MaxMembers = HCHordeLimits.MAX_PACK; }
        s_Document = document;
        s_Reason = "ROUTE_OPERATOR_OFF";
        if (!document.Enabled) { return false; }
        s_Reason = "ROUTE_SURVEY_PENDING";
        bool admitted = false;
        int admittedRoutes;
        int admittedNodes;
        array<ref HCHordeRouteSurvey> documentRoutes = document.Routes;
        foreach (HCHordeRouteSurvey route : documentRoutes)
        {
            if (route && route.Surveyed)
            {
                if (!ValidSurvey(route, document.Defaults)) { s_Document = null; s_Reason = "ROUTE_SURVEY_INVALID"; return false; }
                admitted = true;
                admittedRoutes++;
                admittedNodes += route.Nodes.Count();
            }
        }
        if (!admitted) { return false; }
        s_Reason = "SURVEY_SOURCE_READY_NATIVE_PENDING";
        // Complete source validation: <=8 routes x <=8 nodes. This receipt
        // does not relabel offline-authored points as native-survey evidence.
        Print("[HC HordeRoutes] source_validated routes=" + admittedRoutes.ToString() + " nodes=" + admittedNodes.ToString() + " native_survey=PENDING runtime=PENDING");
        return true;
    }

    static HCHordeRouteSurvey Select(vector start, HCInfectedClue clue)
    {
        if (!s_Document || !s_Document.Enabled) { return null; }
        HCHordeRouteDefaults cfg = s_Document.Defaults;
        float bindSq = cfg.SurveyBindMetres * cfg.SurveyBindMetres;
        array<ref HCHordeRouteSurvey> selectedRoutes = s_Document.Routes;
        foreach (HCHordeRouteSurvey route : selectedRoutes)
        {
            if (!ValidSurvey(route, cfg)) { continue; }
            vector first = route.Nodes[0];
            vector last = route.Nodes[route.Nodes.Count() - 1];
            if (vector.DistanceSq(start, first) <= bindSq) { HCActivity().Add("authored_bound"); return route; }
            if (vector.DistanceSq(start, last) <= bindSq) { HCActivity().Add("authored_bound"); return route; }
        }
        return null;
    }

    static string Reason() { return s_Reason; }
    static void HCClear() { s_Document = null; s_Reason = "ROUTE_OWNER_STOPPED"; }
}

class HCHordeMigration : HCModule
{
    protected static bool s_Active;
    protected string m_LastSummary;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    override string GetName() { return "HordeMigration"; }
    override int StartupPhase() { return HC_PHASE_FEATURE; }
    override void RegisterUses() { HCModuleReadiness.HCRegisterUse("HordeMigration", "route_advanced"); }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableWorld; }
    static bool Active() { return s_Active; }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }

    // Summaries describe the existing route/owner state. No route survey or
    // native verdict is fabricated, and a quiet cohort is not a service refusal.
    protected void HCReport(string phase, int drifting)
    {
        string signature = phase + ":" + m_Status.HCState() + ":" + drifting.ToString();
        if (signature == m_LastSummary) { return; }
        m_LastSummary = signature;
        string admitted = "0";
        if (s_Active) { admitted = "1"; }
        string line = "[HC Plan] HC-46 route=all phase=" + phase + " state=" + m_Status.HCState();
        Print(line + " routes_admitted=" + admitted + " drifting_cohorts=" + drifting.ToString() + " runtime=PENDING");
    }

    protected void HCRefreshStatus(HCInfectedModule infected)
    {
        if (!s_Active)
        {
            m_Status.HCPublish("refused", HCHordeRoutes.Reason());
            if (HCHordeRoutes.Reason() == "ROUTE_OPERATOR_OFF") { m_Status.HCPublish("off", "route_operator_off"); }
            HCReport(HCHordeRoutes.Reason(), 0);
            return;
        }
        string reason = "infected_provider_missing";
        if (infected) { reason = infected.HCV2MigrationReason(); }
        HCModuleReadiness.HCDerive(m_Status, s_Active, "", reason, "survey_routes_loaded_admitted_unverified_runtime_pending");
        if (reason == "hordes_operator_off" || reason == "stimulus_routes_operator_off") { m_Status.HCPublish("off", reason); }
        if (reason != "") { HCReport(reason, 0); return; }
        int drifting = infected.HCV2MigrationDrifting();
        string phase = "waiting_for_perceived_cue_or_eligible_cohort";
        if (drifting > 0) { phase = "native_route_in_progress"; }
        HCReport(phase, drifting);
    }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("HordeMigration", IsEnabled(settings), "EXP-S4", HCV2Gates.Qualified("EXP-S4")) + " runtime=PENDING");
        m_LastSummary = "";
        s_Active = false;
        if (!IsEnabled(settings))
        {
            m_Status.HCPublish("off", "world_operator_off");
            HCReport("world_operator_off", 0);
            return;
        }
        s_Active = HCHordeRoutes.HCLoad(GetGame().GetWorldName());
    }
    override void OnAllModulesStarted()
    {
        HCRefreshStatus(HCInfectedModule.Instance);
    }
    override void OnTick(float deltaTime)
    {
        if (!s_Active) { return; }
        HCInfectedModule infected = HCInfectedModule.Instance;
        if (infected && infected.HCV2MigrationReason() == "")
        {
            infected.HCV2MigrationStep();
            HCReached.Mark("horde_migration.tick");
        }
        HCRefreshStatus(infected);
        HCHordeRoutes.HCActivity().Report();
    }
    override void OnStop()
    {
        s_Active = false;
        HCHordeRoutes.HCActivity().Report("stopped", true);
        // Infected owner's retained release ledger owns native cleanup.
        HCHordeRoutes.HCClear();
        m_Status.HCPublish("off", "route_owner_stopped");
        HCReport("stopped", 0);
    }
}

modded class HCInfectedModule
{
    protected int m_V2DriftCursor;
    protected int m_HCRouteActorCursor;
    protected ref HCUnitBudget m_HCRouteUnits = new HCUnitBudget;
    protected ref HCWorkBudget m_HCRouteWork = new HCWorkBudget;

    // Read-only observations bounded by the validated settings ceilings.
    string HCV2MigrationReason()
    {
        if (!m_Healthy) { return "infected_owner_unhealthy"; }
        if (!m_Hordes) { return "hordes_operator_off"; }
        if (!m_Config || !m_State || !m_Admission) { return "infected_owner_state_missing"; }
        if (!m_Config.EnableHordeStimulusRoutes) { return "stimulus_routes_operator_off"; }
        if (!m_Admission.HordeStimulusRoutes) { return "stimulus_route_dependency_unavailable"; }
        if (m_Packs.Count() > m_GroupCap || m_Packs.Count() != m_State.Groups.Count() || m_Actors.Count() > m_Config.MaxTracked) { return "cohort_roster_inconsistent"; }
        return "";
    }

    int HCV2MigrationDrifting()
    {
        int drifting = 0;
        for (int packIndex = 0; packIndex < m_Packs.Count() && packIndex < m_GroupCap; packIndex++)
        {
            HCNativeInfectedPack candidate = m_Packs[packIndex];
            if (candidate && candidate.IsV2Drifting()) { drifting++; }
        }
        return drifting;
    }

    int HCV2MigrationStep()
    {
        if (!m_Healthy || !m_Hordes || !m_State || !HCHordeMigration.Active()) { return 0; }
        if (!m_Config.EnableHordeStimulusRoutes || !m_Admission.HordeStimulusRoutes || !HeardAdmitted()) { return 0; }
        int count = m_Packs.Count();
        if (count < 1 || count > m_GroupCap || count != m_State.Groups.Count() || m_Actors.Count() > m_Config.MaxTracked) { return 0; }
        int index = m_V2DriftCursor % count;
        m_V2DriftCursor = (index + 1) % count;
        HCNativeInfectedPack pack = m_Packs[index];
        HCHordeRecord record = m_State.Groups[index];
        if (!pack || !record || pack.IsReleasing() || record.State == 5 || record.State == 6 || record.RecoveryConflicted) { return 0; }
        HCInfectedClue chosen;
        m_HCRouteUnits.HCReset(m_WorkCap);
        m_HCRouteWork.HCReset(m_WorkCap);
        int scanned = 0;
        while (scanned < m_Actors.Count())
        {
            if (!m_HCRouteUnits.HCTake(1) || !m_HCRouteWork.HCContinue()) { break; }
            m_HCRouteActorCursor = m_HCRouteActorCursor % m_Actors.Count();
            HCInfectedActor actor = m_Actors[m_HCRouteActorCursor];
            m_HCRouteActorCursor++;
            scanned++;
            if (actor.GroupId != record.Id || !actor.InfectedEntity || !pack.OwnsMember(actor.InfectedEntity)) { continue; }
            HCInfectedClue clue = HCHordeStimulus.MigrationClue(actor, m_Now);
            if (HCHordeStimulus.PreferHotClue(clue, chosen, m_Now)) { chosen = clue; }
        }
        if (chosen) { pack.V2Remember(record.Id, chosen, m_Now); }
        return 1;
    }

    bool HCV2DriftRouteToken()
    {
        if (m_RoutesRemaining < 1) { return false; }
        m_RoutesRemaining--;
        return true;
    }

    override protected void RetargetCohorts() { super.RetargetCohorts(); }
}

modded class HCNativeInfectedPack
{
    protected int m_HCReinforceTarget;
    protected int m_HCReinforced;
    // Admission receipts, not the release ledger's shrinking member count.
    protected int m_HCReinforceAdmitted;
    protected bool m_HCReinforceLogged;
    protected float m_HCFarSince = -1;
    protected float m_HCReinforceUntil;
    override bool HCReinforcePending() { return !m_HCReinforceLogged && m_HCReinforceTarget > m_Members.Count() && HCReinforceActive(); }
    override bool HCReinforceActive() { return m_V2Drift && !m_Releasing; }
    protected bool m_V2Drift;
    protected bool m_V2Segment;
    protected vector m_V2Destination;
    protected float m_V2Deadline;
    protected float m_V2LastEvidence = -1;
    protected float m_V2Cooldown;
    protected float m_V2BestDistance = -1;
    protected float m_V2Progress;
    protected int m_V2MemberCount;
    protected int m_V2Id;
    protected int m_HCRouteStimulus;
    protected int m_HCRouteNode;
    protected bool m_HCRouteReverse;
    protected ref HCHordeRouteSurvey m_HCRoute;
    protected ref HCHordeRouteDefaults m_HCRouteConfig;
    protected ref array<ZombieBase> m_HCRouteMembers = new array<ZombieBase>;

    override bool IsV2Drifting() { return m_V2Drift; }

    override int Retarget(HCInfectedClue clue, float now)
    {
        if (HCHordeMigration.Active() && m_V2Drift) { return 0; }
        return super.Retarget(clue, now);
    }

    void V2Remember(int id, HCInfectedClue clue, float now)
    {
        if (!HCHordeMigration.Active() || m_V2Drift || m_Search || m_Releasing || !Group) { return; }
        HCHordeRouteDefaults cfg = HCHordeRoutes.Defaults();
        if (!HCHordeStimulus.HCRouteNoise(clue, now, m_V2LastEvidence, m_V2Cooldown, cfg)) { return; }
        if (!HCHordeRecovery.HCRouteRoster(m_Members.Count(), cfg.MaxMembers, m_Members.Count(), false)) { return; }
        ZombieBase leader = m_Members[0];
        if (!leader || !HCInfectedStore.ValidPosition(clue.Origin)) { return; }
        if (vector.DistanceSq(leader.GetPosition(), clue.Origin) > cfg.CueRangeMetres * cfg.CueRangeMetres) { return; }
        HCHordeRouteSurvey route = HCHordeRoutes.Select(leader.GetPosition(), clue);
        if (!route) { return; }
        m_HCRouteMembers.Clear();
        // Native scripts-1.30.164289: EnScript.c:917/:926 map Contains/Insert.
        ref map<ZombieBase, bool> admittedIndex = new map<ZombieBase, bool>;
        array<ZombieBase> admittedMembers = m_Members;
        foreach (ZombieBase admittedMember : admittedMembers)
        {
            if (!admittedMember || admittedIndex.Contains(admittedMember)) { m_HCRouteMembers.Clear(); return; }
            admittedIndex.Insert(admittedMember, true);
            m_HCRouteMembers.Insert(admittedMember);
        }
        m_HCRoute = route;
        m_HCRouteConfig = cfg;
        bool forward = vector.DistanceSq(leader.GetPosition(), route.Nodes[0]) <= vector.DistanceSq(leader.GetPosition(), route.Nodes[route.Nodes.Count() - 1]);
        m_HCRouteReverse = !forward;
        m_HCRouteNode = 0;
        m_HCRouteStimulus = clue.EventId;
        m_V2Id = id;
        m_V2Destination = route.Nodes[route.Nodes.Count() - 1];
        if (m_HCRouteReverse) { m_V2Destination = route.Nodes[0]; }
        m_V2MemberCount = m_Members.Count();
        m_V2LastEvidence = clue.Observed;
        m_V2Deadline = Math.Min(clue.Expires, clue.Observed + cfg.MaxNoiseSeconds);
        m_V2Progress = now;
        m_V2Segment = false;
        m_V2Drift = true;
        HCVarietyWalkerHerd();
        HCRouteLog("admitted", "on");
    }

    // Native physical walking uses AIGroupBehaviour.c:27 SetWaypoints and
    // Object.c:287 GetPosition (scripts-1.30.164289). No observer absence is
    // needed: membership is already physical and every waypoint is pathed.
    // This is a finite patrol lifetime, never a fabricated noise receipt.
    override bool HCAdmitPatrol(HCHordeRouteSurvey route, int id, float now, int target)
    {
        HCHordeRouteDefaults cfg = HCHordeRoutes.Defaults();
        if (!HCHordeMigration.Active() || !cfg || !route || !Group || m_Releasing || m_Search) { return false; }
        if (target < HCHordeLimits.MIN_PATROL || target > cfg.MaxMembers || target > HCHordeLimits.MAX_PACK) { return false; }
        if (!HCHordeRecovery.HCRouteRoster(m_Members.Count(), cfg.MaxMembers, m_Members.Count(), false)) { return false; }
        ZombieBase leader = m_Members[0];
        if (!leader) { return false; }
        m_HCRouteMembers.Clear();
        array<ZombieBase> patrolMembers = m_Members;
        foreach (ZombieBase member : patrolMembers)
        {
            if (!member) { return false; }
            m_HCRouteMembers.Insert(member);
        }
        m_HCRoute = route;
        m_HCRouteConfig = cfg;
        m_HCRouteReverse = vector.DistanceSq(leader.GetPosition(), route.Nodes[0]) > vector.DistanceSq(leader.GetPosition(), route.Nodes[route.Nodes.Count() - 1]);
        m_HCRouteNode = 0;
        m_HCRouteStimulus = 0;
        m_V2Id = id;
        m_V2Destination = route.Nodes[route.Nodes.Count() - 1];
        if (m_HCRouteReverse) { m_V2Destination = route.Nodes[0]; }
        m_V2MemberCount = m_Members.Count();
        m_HCReinforceTarget = target;
        m_HCReinforced = 0;
        m_HCReinforceAdmitted = m_Members.Count();
        m_HCReinforceLogged = false;
        // Visibility may veto every top-up. Never hold the walking CE seed
        // for its entire 600-second patrol waiting for hidden creation.
        m_HCReinforceUntil = now + 30;
        m_HCFarSince = -1;
        m_V2Deadline = now + 600;
        m_V2Progress = now;
        // Start already sampled, pathed and activated the entry waypoint.
        // Observe that leg rather than issuing a second path to an endpoint
        // the members may have reached during the bounded top-up window.
        m_V2Segment = true;
        m_V2BestDistance = -1;
        m_V2Drift = true;
        HCHordeRoutes.HCActivity().Add("legs_started");
        HCRouteLog("admitted", "patrol");
        return true;
    }

    override bool Release()
    {
        HCReinforceLog();
        return super.Release();
    }

    protected void HCReinforceLog()
    {
        if (m_HCReinforceTarget < 1 || m_HCReinforceLogged) { return; }
        // Latch before the checkpoint: a failed write quarantines the owner
        // and re-enters Release. Never retry that boundary recursively.
        m_HCReinforceLogged = true;
        if (m_HCReinforceAdmitted < m_HCReinforceTarget)
        {
            HCInfectedModule owner = HCInfectedModule.Instance;
            if (owner) { owner.HCReinforceRetire(this, m_V2Id, m_HCReinforceAdmitted, m_HCReinforceTarget); }
        }
        Print("[HC Plan] HC-46 cohort=" + m_V2Id.ToString() + " reinforced=" + m_HCReinforced.ToString() + " total=" + m_Members.Count().ToString() + " runtime=PENDING");
    }

    protected void HCReinforceStep(float now)
    {
        HCInfectedModule owner = HCInfectedModule.Instance;
        if (!owner || !Group || m_Releasing || !m_HCRoute || m_Members.Count() < 1) { return; }
        vector entry = m_HCRoute.Nodes[0];
        if (m_HCRouteReverse) { entry = m_HCRoute.Nodes[m_HCRoute.Nodes.Count() - 1]; }
        // At most two attempts globally per core tick; the full reserved roster
        // is already charged by HCServer.HCTickWork before pack.Tick.
        for (int attempt = 0; attempt < 2 && m_Members.Count() < m_HCReinforceTarget; attempt++)
        {
            if (!owner.HCReinforceRoom()) { return; }
            ZombieBase body = HCHordeReinforce.HCCreate(m_Members[0].GetType(), entry, this);
            if (!body) { return; }
            // Same transfer/receipt path as Start: AIGroup.c:11-12 Add/RemoveAgent,
            // AIAgent.c:7 GetGroup; DayZAnimal.c:193 GetAIAgent (1.30.164289).
            AIAgent agent = body.GetAIAgent();
            if (!agent) { GetGame().ObjectDelete(body); return; }
            AIGroup previous = agent.GetGroup();
            if (previous) { previous.RemoveAgent(agent); }
            Group.AddAgent(agent);
            if (agent.GetGroup() != Group || !owner.HCReinforceTrack(body, m_V2Id))
            {
                GetGame().ObjectDelete(body);
                return;
            }
            m_Members.Insert(body);
            m_HCRouteMembers.Insert(body);
            m_V2MemberCount = m_Members.Count();
            m_HCReinforced++;
            m_HCReinforceAdmitted++;
        }
    }

    // Keep this shared segment port/registration stable. The 4 m waypoint
    // radius is the pre-existing native pack setting; arrival is per member.
    bool V2CommitSegment(vector end, float now)
    {
        if (m_Members.Count() != m_V2MemberCount) { return false; }
        m_RoutePlan.Clear();
        BehaviourGroupInfectedPackWaypointParams routeWaypoint = new BehaviourGroupInfectedPackWaypointParams(end, 4);
        m_RoutePlan.Insert(routeWaypoint);
        RoutePlanned = 1;
        RouteCompleted = 0;
        RoutePurpose = 1;
        RouteResult = 1;
        RouteEnd = end;
        return ActivateWaypoint(now);
    }

    protected void HCRouteLog(string phase, string state)
    {
        string line = "[HC Plan] HC-46 route=" + m_HCRoute.Id + " cohort=" + m_V2Id.ToString();
        line = line + " stimulus=" + m_HCRouteStimulus.ToString() + " phase=" + phase + " state=" + state;
        Print(line + " members=" + m_V2MemberCount.ToString() + " node=" + m_HCRouteNode.ToString() + "/" + m_HCRoute.Nodes.Count().ToString() + " runtime=PENDING");
    }

    protected bool V2End(float now, int result)
    {
        HCReinforceLog();
        if (m_V2Drift)
        {
            string phase = "refused_native_or_expired";
            string outcome = "invalid";
            if (result == 2) { phase = "reached"; outcome = "reached"; }
            if (result == 3) { outcome = "stalled"; }
            if (result == 5)
            {
                outcome = "interrupted";
                if (now >= m_V2Deadline) { outcome = "expired"; }
            }
            phase = outcome;
            HCHordeRoutes.HCActivity().Add(outcome);
            HCRouteLog(phase, "off");
            m_V2Cooldown = now + m_HCRouteConfig.CooldownSeconds;
        }
        m_V2Drift = false;
        m_HCRoute = null;
        m_HCRouteConfig = null;
        m_HCRouteMembers.Clear();
        RouteResult = result;
        if (result == 2) { RouteCompleted = RoutePlanned; }
        return !Release();
    }

    protected bool V2Tick(float now)
    {
        if (!HCHordeMigration.Active() || now >= m_V2Deadline || m_Releasing || !Group || !m_RoutePlan) { return V2End(now, 5); }
        HCHordeRouteDefaults cfg = m_HCRouteConfig;
        if (!cfg || !m_HCRoute || !HCHordeRecovery.HCRouteRoster(m_Members.Count(), cfg.MaxMembers, m_V2MemberCount, false)) { return V2End(now, 6); }
        if (m_HCRouteMembers.Count() != m_V2MemberCount) { return V2End(now, 6); }
        ZombieBase leader;
        vector centroid;
        float worst = 0;
        int memberIndex = 0;
        array<ZombieBase> currentMembers = m_Members;
        foreach (ZombieBase member : currentMembers)
        {
            if (member != m_HCRouteMembers[memberIndex]) { return V2End(now, 6); }
            memberIndex++;
            if (!member || !member.IsAlive()) { return V2End(now, 5); }
            AIAgent agent = member.GetAIAgent();
            if (!agent || agent.GetGroup() != Group) { return V2End(now, 6); }
            int mind = member.GetMindStateSynced();
            if (mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT || member.GetHealth("LeftLeg", "Health") <= 0 || member.GetHealth("RightLeg", "Health") <= 0) { return V2End(now, 5); }
            vector memberPosition = member.GetPosition();
            if (!HCInfectedStore.ValidPosition(memberPosition)) { return V2End(now, 6); }
            centroid = centroid + memberPosition;
            if (!leader) { leader = member; }
            if (m_V2Segment) { worst = Math.Max(worst, vector.DistanceSq(memberPosition, RouteEnd)); }
        }
        if (!leader) { return V2End(now, 6); }
        centroid = centroid * (1.0 / m_V2MemberCount);
        m_LastPosition = leader.GetPosition();
        array<ZombieBase> clusterMembers = m_Members;
        foreach (ZombieBase clustered : clusterMembers)
        {
            if (vector.DistanceSq(clustered.GetPosition(), centroid) > cfg.CohesionMetres * cfg.CohesionMetres) { return V2End(now, 5); }
        }
        if (!m_HCReinforceLogged && m_HCReinforceTarget > 0 && m_Members.Count() < m_HCReinforceTarget && now < m_HCReinforceUntil)
        {
            HCReinforceStep(now);
            if (m_Members.Count() < m_HCReinforceTarget) { return true; }
        }
        HCReinforceLog();
        // A shortfall has a durable terminal record, not a completed roster.
        // Release before refund; do not continue walking a retired offer.
        if (m_HCReinforceAdmitted < m_HCReinforceTarget) { return V2End(now, 5); }
        float nearest = HCInfectedLOD.NearestDistance(HCPerfPlayers.HCGet(), centroid);
        // Cohesion bounds every member within 100 m, hence >=600 proves all >=500.
        if (nearest >= 500 + cfg.CohesionMetres)
        {
            if (m_HCFarSince < 0) { m_HCFarSince = now; }
            if (now - m_HCFarSince >= 60) { return V2End(now, 5); }
        }
        else { m_HCFarSince = -1; }
        // Physical cohorts walk under native AI, including when visible.
        // Observer-clear grace belongs to LOD/materialization, not locomotion.
        if (m_V2Segment)
        {
            if (worst <= cfg.ArrivalMetres * cfg.ArrivalMetres)
            {
                HCHordeRoutes.HCActivity().Add("legs_finished");
                m_HCRouteNode++;
                HCModuleReadiness.HCUse("HordeMigration", "route_advanced");
                m_V2Segment = false;
                if (m_HCRouteNode >= m_HCRoute.Nodes.Count()) { return V2End(now, 2); }
            }
            else
            {
                if (m_V2BestDistance < 0 || worst < m_V2BestDistance - cfg.ProgressMetres * cfg.ProgressMetres)
                {
                    m_V2BestDistance = worst;
                    m_V2Progress = now;
                }
                if (now - m_V2Progress >= cfg.StallSeconds) { return V2End(now, 3); }
                return true;
            }
        }
        HCInfectedModule owner = HCInfectedModule.Instance;
        if (!owner || !owner.HCV2DriftRouteToken()) { return true; }
        int nodeIndex = m_HCRouteNode;
        if (m_HCRouteReverse) { nodeIndex = m_HCRoute.Nodes.Count() - 1 - m_HCRouteNode; }
        vector desired = m_HCRoute.Nodes[nodeIndex];
        vector sampled;
        if (!Reachable(leader.GetPosition(), desired, cfg.NativeSegmentMetres, sampled)) { return V2End(now, 6); }
        if (!V2CommitSegment(sampled, now)) { return V2End(now, 6); }
        m_V2Segment = true;
        m_V2BestDistance = -1;
        m_V2Progress = now;
        HCHordeRoutes.HCActivity().Add("legs_started");
        HCRouteLog("native_waypoint_requested", "on");
        return true;
    }

    override bool Tick(float now)
    {
        if (m_V2Drift) { return V2Tick(now); }
        return super.Tick(now);
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        HCHordeMigration migrationModule = new HCHordeMigration;
        Register(migrationModule);
    }
}
