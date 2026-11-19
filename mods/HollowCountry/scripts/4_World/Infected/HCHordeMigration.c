// LC-T312 / #96, EnableWorld; EXP-S4 is logged, never an admission veto.
// Native references in scripts-1.30.164289:
// 3_Game/AI/AIGroupBehaviour.c:9,14 waypoint DTO, :27 SetWaypoints;
// AIGroup.c:14 GetBehaviour, AIAgent.c:7 GetGroup; AIWorld.c:122/98
// SampleNavmeshPosition/FindPath via HCNativeInfectedPack.Reachable;
// 3_Game/Entities/DayZAnimal.c:193 GetAIAgent (DayZCreatureAI).
// 3_Game/Entities/Object.c:287 GetPosition, :517 IsAlive, :994 GetHealth;
// 4_World/Entities/Creatures/Infected/ZombieBase.c:182 GetMindStateSynced;
// 3_Game/Global/Game.c:945 GetPlayers via HCObserverTransitionGate.V2Quiet,
// :1176 SurfaceY; 1_Core/proto/EnConvert.c:153,169,210 vector Normalize,
// Length, DistanceSq; :30 int.ToString;
// EnMath.c:553,566 Min/Max; EnScript.c:380,385,407 arrays; EnDebug.c:96 Print.
// Only existing, admitted v1 packs are moved, by native paths. No creation,
// deletion, teleport, membership transfer, synthetic sound or CE budget change.
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
    float SurveyBindMetres = 80;
    float CohesionMetres = 100;
    float ArrivalMetres = 8;
    float NativeSegmentMetres = 120;
    float ProgressMetres = 1;
    int MaxMembers = 6;
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
        if (cfg.MaxMembers < 1 || cfg.MaxMembers > 6 || cfg.MaxHops < 0 || cfg.MaxHops > 2) { return false; }
        return cfg.MaxNoiseSeconds > 0 && cfg.MaxNoiseSeconds <= 60 && cfg.CooldownSeconds >= cfg.MaxNoiseSeconds && cfg.CooldownSeconds <= 600 && cfg.StallSeconds > 0 && cfg.StallSeconds <= 90;
    }

    static bool ValidSurvey(HCHordeRouteSurvey route, HCHordeRouteDefaults cfg)
    {
        if (!route || !route.Surveyed || route.Id == "" || route.Id.Length() > 64 || route.Evidence == "" || route.Evidence.Length() > 128) { return false; }
        if (!route.Nodes || route.Nodes.Count() < 2 || route.Nodes.Count() > 8) { return false; }
        vector previous;
        int index = 0;
        foreach (vector point : route.Nodes)
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
        s_Document = document;
        s_Reason = "ROUTE_OPERATOR_OFF";
        if (!document.Enabled) { return false; }
        s_Reason = "ROUTE_SURVEY_PENDING";
        bool admitted = false;
        foreach (HCHordeRouteSurvey route : document.Routes)
        {
            if (route && route.Surveyed)
            {
                if (!ValidSurvey(route, document.Defaults)) { s_Document = null; s_Reason = "ROUTE_SURVEY_INVALID"; return false; }
                admitted = true;
            }
        }
        if (!admitted) { return false; }
        s_Reason = "SURVEY_SOURCE_READY_NATIVE_PENDING";
        return true;
    }

    static HCHordeRouteSurvey Select(vector start, HCInfectedClue clue)
    {
        if (!s_Document || !s_Document.Enabled || !clue) { return null; }
        HCHordeRouteDefaults cfg = s_Document.Defaults;
        float bindSq = cfg.SurveyBindMetres * cfg.SurveyBindMetres;
        foreach (HCHordeRouteSurvey route : s_Document.Routes)
        {
            if (!ValidSurvey(route, cfg)) { continue; }
            vector first = route.Nodes[0];
            vector last = route.Nodes[route.Nodes.Count() - 1];
            if (vector.DistanceSq(start, first) <= bindSq && vector.DistanceSq(clue.Origin, last) <= bindSq) { return route; }
            if (vector.DistanceSq(start, last) <= bindSq && vector.DistanceSq(clue.Origin, first) <= bindSq) { return route; }
        }
        return null;
    }

    static string Reason() { return s_Reason; }
    static void HCClear() { s_Document = null; s_Reason = "ROUTE_OWNER_STOPPED"; }
}

class HCHordeMigration : HCModule
{
    protected static bool s_Active;
    protected bool m_WaitingPrinted;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    override string GetName() { return "HordeMigration"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableWorld; }
    static bool Active() { return s_Active; }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("HordeMigration", true, "EXP-S4", HCV2Gates.Qualified("EXP-S4")));
        m_WaitingPrinted = false;
        s_Active = HCHordeRoutes.HCLoad(GetGame().GetWorldName());
        m_Status.HCPublish("refused", HCHordeRoutes.Reason());
        if (HCHordeRoutes.Reason() == "ROUTE_OPERATOR_OFF") { m_Status.HCPublish("off", "route_operator_off"); }
        // Wave 16 owner decision: a loaded, valid route document is admitted unverified (the EXP-S4
        // admission line above names the missing native verdict once; the two HC-46 lines below
        // name the physical observer and fresh-visual parts that stay refused). Ready is derived
        // from the loaded document; operator opt-out is Enabled=false in route-surveys.json.
        if (s_Active) { m_Status.HCPublish("ready", "survey_routes_loaded_admitted_unverified_runtime_pending"); }
        Print("[HC Plan] HC-46 route=all cohort=0 stimulus=0 phase=" + HCHordeRoutes.Reason() + " state=" + m_Status.HCState() + " admitted=0 max_cohorts=2 runtime=PENDING");
        Print("[HC Plan] HC-46 route=all cohort=0 stimulus=0 phase=FRESH_VISUAL_RECEIPT_UNEXPOSED state=refused count=0 runtime=PENDING");
        Print("[HC Plan] HC-46 route=all cohort=0 stimulus=0 phase=PHYSICAL_ROUTE_OBSERVER_CONTRACT_PENDING state=refused noise_ttl_max=30 observer_quiet=60 count=0 runtime=PENDING");
    }
    override void OnTick(float deltaTime)
    {
        if (!s_Active) { return; }
        HCInfectedModule infected = HCInfectedModule.Instance;
        if (!infected) { return; }
        int packs = infected.HCV2MigrationStep();
        if (packs == 0 && !m_WaitingPrinted)
        {
            m_WaitingPrinted = true;
            Print("[HC Plan] HC-46 route=all cohort=0 stimulus=0 phase=PHYSICAL_COHORT_OR_ADMISSION_PENDING state=refused admitted=0 max_cohorts=2 runtime=PENDING");
        }
    }
    override void OnStop()
    {
        s_Active = false;
        // Infected owner's existing Tick/OnStop and retained release ledger own
        // native cleanup. No membership transfer or LOD body mutation here.
        HCHordeRoutes.HCClear();
        m_Status.HCPublish("off", "route_owner_stopped");
        Print("[HC Plan] HC-46 route=all cohort=0 stimulus=0 phase=stopped state=off max_cohorts=2 runtime=PENDING");
    }
}

modded class HCInfectedModule
{
    protected int m_V2DriftCursor;
    protected int m_HCRouteActorCursor;
    protected ref HCUnitBudget m_HCRouteUnits = new HCUnitBudget;
    protected ref HCWorkBudget m_HCRouteWork = new HCWorkBudget;

    int HCV2MigrationStep()
    {
        if (!m_Healthy || !m_Hordes || !m_State || !HCHordeMigration.Active()) { return 0; }
        if (!m_Config.EnableHordeStimulusRoutes || !m_Admission.HordeStimulusRoutes || !HeardAdmitted()) { return 0; }
        int count = m_Packs.Count();
        if (count < 1 || count > 2 || count != m_State.Groups.Count() || m_Actors.Count() > 24) { return 0; }
        int index = m_V2DriftCursor % count;
        m_V2DriftCursor = (index + 1) % count;
        HCNativeInfectedPack pack = m_Packs[index];
        HCHordeRecord record = m_State.Groups[index];
        if (!pack || !record || pack.IsReleasing() || record.State == 5 || record.State == 6 || record.RecoveryConflicted) { return 0; }
        HCInfectedClue chosen;
        m_HCRouteUnits.HCReset(24);
        m_HCRouteWork.HCReset(24);
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
    protected bool m_V2Drift;
    protected bool m_V2Segment;
    protected vector m_V2Destination;
    protected float m_V2Deadline;
    protected float m_V2ClearSince = -1;
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
        foreach (ZombieBase admittedMember : m_Members)
        {
            if (!admittedMember || m_HCRouteMembers.Find(admittedMember) >= 0) { m_HCRouteMembers.Clear(); return; }
            m_HCRouteMembers.Insert(admittedMember);
        }
        m_HCRoute = route;
        m_HCRouteConfig = cfg;
        float bindSq = cfg.SurveyBindMetres * cfg.SurveyBindMetres;
        bool forward = vector.DistanceSq(leader.GetPosition(), route.Nodes[0]) <= bindSq && vector.DistanceSq(clue.Origin, route.Nodes[route.Nodes.Count() - 1]) <= bindSq;
        m_HCRouteReverse = !forward;
        m_HCRouteNode = 0;
        m_HCRouteStimulus = clue.EventId;
        m_V2Id = id;
        m_V2Destination = route.Nodes[route.Nodes.Count() - 1];
        if (m_HCRouteReverse) { m_V2Destination = route.Nodes[0]; }
        m_V2MemberCount = m_Members.Count();
        m_V2LastEvidence = clue.Observed;
        m_V2Deadline = Math.Min(clue.Expires, clue.Observed + cfg.MaxNoiseSeconds);
        m_V2ClearSince = -1;
        m_V2Progress = now;
        m_V2Segment = false;
        m_V2Drift = true;
        HCVarietyWalkerHerd();
        HCRouteLog("admitted", "on");
    }

    // Keep this shared segment port/registration stable. The 4 m waypoint
    // radius is the pre-existing native pack setting; arrival is per member.
    bool V2CommitSegment(vector end, float now)
    {
        if (m_Members.Count() != m_V2MemberCount) { return false; }
        m_RoutePlan.Clear();
        m_RoutePlan.Insert(new BehaviourGroupInfectedPackWaypointParams(end, 4));
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
        if (m_V2Drift)
        {
            string phase = "refused_native_or_expired";
            if (result == 2) { phase = "reached"; }
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
        foreach (ZombieBase member : m_Members)
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
        foreach (ZombieBase clustered : m_Members)
        {
            if (vector.DistanceSq(clustered.GetPosition(), centroid) > cfg.CohesionMetres * cfg.CohesionMetres) { return V2End(now, 5); }
        }
        // Reuse the existing observer gate/HCPerfPlayers snapshot; a centroid
        // is ONLY the conservative observer envelope, never proof of arrival.
        bool quiet = HCObserverTransitionGate.V2Quiet(centroid, m_V2Destination, now, 60, m_V2ClearSince);
        if (!quiet)
        {
            // End and release to native ownership; do not issue centroid holds
            // that could drag the cohort away from its surveyed corridor.
            HCRouteLog("OBSERVER_QUIET_CONTRACT_REFUSED", "refused");
            return V2End(now, 5);
        }
        if (m_V2Segment)
        {
            if (worst <= cfg.ArrivalMetres * cfg.ArrivalMetres)
            {
                m_HCRouteNode++;
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
        Register(new HCHordeMigration);
    }
}
