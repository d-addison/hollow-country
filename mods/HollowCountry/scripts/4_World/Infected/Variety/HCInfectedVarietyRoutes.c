// #213 spec: waking fresh groups follow bounded HC-46 corridors; no new survey.
// Plan/tasks: shared HCGroupJson/HC-46 validation, nearest segment, native pack
// Start/Reachable/V2CommitSegment/Tick/Release; one pack and one segment per tick.
// Native snapshot scripts-1.30.164289: Object.c:287 GetPosition, :517 IsAlive
// (3_Game/Entities); DayZAnimal.c:193 GetAIAgent; 3_Game/AI/AIAgent.c:7 GetGroup;
// 4_World/Entities/Creatures/Infected/ZombieBase.c:182 GetMindStateSynced;
// 1_Core/proto/EnConvert.c:196 Distance, :210 DistanceSq; EnScript.c:380 Count,
// :394 Find, :407 Insert; EnMath.c:553/566 Min/Max; EnDebug.c:96 Print; 3_Game/Global/Game.c:934 GetWorldName.
// Native movement remains entirely in HCNativeInfectedPack (AIWorld.c:98/122,
// AIGroupBehaviour.c:27); no Expansion calls. Surveyed means authored source,
// never an observed terrain/traversal verdict. Native and two-client pending.
class HCInfectedVarietyRoutes
{
    protected static ref HCHordeRouteDocument s_Routes;
    protected static ref HCInfectedVarietyConfig s_Config;
    protected static ref HCInfectedVarietyRoutePack s_Pack;
    protected static string s_LastRefusal;
    protected static ref array<HCInfectedActor> s_Roster;
    protected static string s_Fault;

    protected static bool s_FallbackPrinted;
    protected static float s_NextScan;

    static string HCFault() { return s_Fault; }

    static void HCRefuse(string reason)
    {
        if (reason == s_LastRefusal) { return; }
        s_LastRefusal = reason;
        Print("[HC Variety] migration=" + reason + " runtime=PENDING");
    }

    static void HCStart()
    {
        s_Config = HCInfectedVariety.HCConfig();
        s_Routes = null;
        s_Fault = "";
        s_NextScan = 0;
        if (!s_Config) { return; }
        if (!s_Config.EnableMigration) { HCRefuse("off_EnableMigration"); return; }
        s_Fault = "variety_route_document_unavailable";
        HCHordeRouteDocument document;
        if (!HCGroupJson<HCHordeRouteDocument>.Load("$mission:hollow-country/infected/route-surveys.json", 32768, document))
        {
            HCRefuse("route_document_unavailable_authored_sites_fallback");
            return;
        }
        if (!document || document.SchemaVersion != 1 || document.WorldName != GetGame().GetWorldName() || !HCHordeRoutes.ValidDefaults(document.Defaults)) { HCRefuse("route_document_invalid_authored_sites_fallback"); return; }
        if (!document.Routes || document.Routes.Count() > 8) { HCRefuse("route_count_invalid_authored_sites_fallback"); return; }
        s_Routes = document;
        s_Fault = "";
        if (!document.Enabled) { HCRefuse("off_route_operator"); return; }
        bool surveyed = false;
        array<ref HCHordeRouteSurvey> surveys = document.Routes;
        foreach (HCHordeRouteSurvey survey : surveys)
        {
            if (HCHordeRoutes.ValidSurvey(survey, document.Defaults)) { surveyed = true; }
        }
        if (!surveyed) { s_Fault = "variety_route_survey_unavailable"; HCRefuse(s_Fault); return; }
        Print("[HC Variety] migration=survey_corridors_admitted_unverified opt_out=EnableMigration runtime=PENDING");
    }

    // Horizontal nearest point on a segment; no engine terrain extraction.
    static float HCSegmentFraction(vector pos, vector first, vector last)
    {
        float dx = last[0] - first[0];
        float dz = last[2] - first[2];
        float lengthSq = dx * dx + dz * dz;
        if (lengthSq <= 0) { return 0; }
        float fraction = (pos[0] - first[0]) * dx + (pos[2] - first[2]) * dz;
        fraction /= lengthSq;
        return Math.Max(0, Math.Min(1, fraction));
    }

    static HCHordeRouteSurvey HCSelect(vector pos)
    {
        if (!s_Config || !s_Routes || !s_Routes.Enabled) { return null; }
        HCHordeRouteSurvey selected;
        int selectedNode;
        vector entry;
        float nearest = s_Config.CorridorRangeMetres * s_Config.CorridorRangeMetres;
        array<ref HCHordeRouteSurvey> routes = s_Routes.Routes;
        foreach (HCHordeRouteSurvey route : routes)
        {
            if (!HCHordeRoutes.ValidSurvey(route, s_Routes.Defaults)) { continue; }
            for (int node = 0; node < route.Nodes.Count() - 1; node++)
            {
                vector first = route.Nodes[node];
                vector last = route.Nodes[node + 1];
                float fraction = HCSegmentFraction(pos, first, last);
                vector point = first + (last - first) * fraction;
                float distance = vector.DistanceSq(pos, point);
                if (distance > nearest) { continue; }
                nearest = distance;
                selected = route;
                selectedNode = node + 1;
                entry = point;
            }
        }
        if (!selected) { return null; }
        HCHordeRouteSurvey bounded = new HCHordeRouteSurvey;
        bounded.Id = selected.Id;
        bounded.Nodes.Insert(entry);
        float length = vector.Distance(pos, entry);
        vector previous = entry;
        for (int next = 0; next < selected.Nodes.Count(); next++)
        {
            if (next < selectedNode) { continue; }
            vector destination = selected.Nodes[next];
            float segment = vector.Distance(previous, destination);
            if (length + segment > s_Config.MaxMigrationMetres) { break; }
            if (segment > 0) { bounded.Nodes.Insert(destination); }
            length += segment;
            previous = destination;
        }
        return bounded;
    }

    static HCHordeRouteSurvey HCFallback(vector pos)
    {
        if (!s_FallbackPrinted)
        {
            s_FallbackPrinted = true;
            Print("[HC Variety] migration=authored_sites_fallback reason=no_corridor_in_range runtime=PENDING");
        }
        HCHordeRouteSurvey fallback = new HCHordeRouteSurvey;
        float nearest = Math.Min(s_Config.MaxMigrationMetres, s_Config.CorridorRangeMetres);
        nearest = nearest * nearest;
        vector target;
        array<ref HCInfectedVarietySite> sites = s_Config.Sites;
        foreach (HCInfectedVarietySite site : sites)
        {
            vector point = site.Position;
            point[0] = point[0] + s_Config.ContextRange;
            float distance = vector.DistanceSq(pos, point);
            if (distance <= 0 || distance > nearest) { continue; }
            nearest = distance;
            target = point;
            fallback.Id = site.Id;
        }
        if (fallback.Id == "") { return null; }
        fallback.Nodes.Insert(target);
        return fallback;
    }

    static void HCStep(float now)
    {
        if (!s_Config || !s_Config.EnableMigration || !HCInfectedVarietyModule.VarietyActive()) { return; }
        if (s_Routes && !s_Routes.Enabled) { return; }
        if (!s_Pack && now < s_NextScan) { return; }
        if (s_Pack)
        {
            // Safety release (expiry, wake, combat, ownership, sight) never waits
            // for budget; only segment advancement and native upkeep are funded.
            bool keep;
            if (HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_INFECTED_VARIETY_ROUTES, 8)) { keep = s_Pack.Tick(now); }
            else { keep = s_Pack.HCMaintain(now); }
            if (!keep) { HCClearRoster(); s_Pack = null; }
            return;
        }
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_INFECTED_VARIETY_ROUTES, 8)) { return; }
        s_NextScan = now + s_Config.MigrationScanSeconds;
        array<HCInfectedActor> roster = HCInfectedModule.Instance.HCVarietyRouteRoster();
        if (!roster || roster.Count() < 1) { return; }
        ZombieBase leader = roster[0].InfectedEntity;
        HCHordeRouteSurvey route = HCSelect(leader.GetPosition());
        if (!route) { route = HCFallback(leader.GetPosition()); }
        if (!route)
        {
            foreach (HCInfectedActor unavailable : roster) { unavailable.InfectedEntity.HCVarietyRouteMark(); }
            HCRefuse("authored_site_unavailable_native_wander_retained");
            return;
        }
        array<Man> players = HCPerfPlayers.HCGet();
        foreach (HCInfectedActor actor : roster)
        {
            if (!HCInfectedVariety.HCHidden(actor.InfectedEntity.GetPosition(), players)) { return; }
        }
        if (!HCInfectedVariety.HCHidden(route.Nodes[0], players)) { return; }
        HCInfectedVarietyRoutePack pack = new HCInfectedVarietyRoutePack;
        HCHordeRouteDefaults nativeDefaults = new HCHordeRouteDefaults;
        if (s_Routes) { nativeDefaults = s_Routes.Defaults; }
        foreach (HCInfectedActor attempted : roster) { attempted.InfectedEntity.HCVarietyRouteMark(); }
        if (!pack.HCBegin(roster, route, nativeDefaults, now, s_Config.MigrationLifetimeSeconds)) { HCRefuse("native_route_start_refused"); return; }
        s_Pack = pack;
        s_Roster = roster;
        foreach (HCInfectedActor admitted : roster)
        {
            admitted.SearchPack = pack;
        }
        Print("[HC Variety] migration=native_corridor_requested route=" + route.Id + " runtime=PENDING");
    }

    static void HCClearRoster()
    {
        if (!s_Roster) { return; }
        array<HCInfectedActor> roster = s_Roster;
        foreach (HCInfectedActor actor : roster)
        {
            if (actor && actor.SearchPack == s_Pack) { actor.SearchPack = null; }
        }
        s_Roster = null;
    }

    static void HCStop()
    {
        if (s_Pack) { s_Pack.Release(); }
        HCClearRoster();
        s_Pack = null;
        s_Config = null;
        s_Routes = null;
        s_Fault = "";
    }
}

class HCInfectedVarietyRoutePack : HCNativeInfectedPack
{
    protected ref HCHordeRouteSurvey m_VarietyRoute;
    protected int m_VarietyNode;
    protected ref HCHordeRouteDefaults m_VarietyDefaults;
    protected bool m_VarietyArrived;

    bool HCBegin(array<HCInfectedActor> roster, HCHordeRouteSurvey route, HCHordeRouteDefaults nativeDefaults, float now, float lifetime)
    {
        if (!route || route.Nodes.Count() < 1 || !nativeDefaults || !roster || roster.Count() < 1) { return false; }
        InitFilter();
        vector entry;
        if (!Reachable(roster[0].InfectedEntity.GetPosition(), route.Nodes[0], nativeDefaults.NativeSegmentMetres, entry)) { return false; }
        if (!Start(roster, route.Nodes[0], false, now, now + lifetime)) { return false; }
        m_VarietyRoute = route;
        m_VarietyDefaults = nativeDefaults;
        m_VarietyNode = 1;
        m_V2MemberCount = roster.Count();
        return true;
    }

    bool HCVarietyNextSegment(float now)
    {
        vector desired = m_VarietyRoute.Nodes[m_VarietyNode];
        if (!HCInfectedVariety.HCHidden(desired, HCPerfPlayers.HCGet())) { return false; }
        vector sampled;
        if (!Reachable(m_Members[0].GetPosition(), desired, m_VarietyDefaults.NativeSegmentMetres, sampled)) { return false; }
        if (!V2CommitSegment(sampled, now)) { return false; }
        m_VarietyNode++;
        return true;
    }

    // Bounded by the pack roster; runs every step even when work budget is refused.
    bool HCMaintain(float now)
    {
        if (m_Releasing) { return !Release(); }
        if (!HCInfectedVarietyModule.VarietyActive() || now >= m_Expires) { return !Release(); }
        if (!m_VarietyRoute || !m_VarietyDefaults) { return !Release(); }
        bool arrived = true;
        array<Man> players = HCPerfPlayers.HCGet();
        array<ZombieBase> members = m_Members;
        foreach (ZombieBase member : members)
        {
            if (!member || !member.IsAlive() || member.HCVarietyDormant()) { return !Release(); }
            if (member.GetMindStateSynced() != DayZInfectedConstants.MINDSTATE_CALM) { return !Release(); }
            AIAgent agent = member.GetAIAgent();
            if (!agent || agent.GetGroup() != Group) { return !Release(); }
            if (!HCInfectedVariety.HCHidden(member.GetPosition(), players)) { return !Release(); }
            if (vector.DistanceSq(member.GetPosition(), RouteEnd) > m_VarietyDefaults.ArrivalMetres * m_VarietyDefaults.ArrivalMetres) { arrived = false; }
        }
        m_VarietyArrived = arrived;
        return true;
    }

    override bool Tick(float now)
    {
        bool keep = HCMaintain(now);
        if (!keep || m_Releasing) { return keep; }
        if (m_VarietyArrived && m_VarietyNode < m_VarietyRoute.Nodes.Count())
        {
            if (!HCVarietyNextSegment(now)) { return !Release(); }
        }
        // Existing native consumer owns death/leg injury, expiry, stalls,
        // ownership receipts and final arrival/release, with no body deletion.
        return super.Tick(now);
    }
}

modded class ZombieBase
{
    protected bool m_HCVarietyRouteTried;
    bool HCVarietyRouteTried() { return m_HCVarietyRouteTried; }
    void HCVarietyRouteMark() { m_HCVarietyRouteTried = true; }
}

modded class HCInfectedModule
{
    protected int m_HCVarietyRouteCursor;

    array<HCInfectedActor> HCVarietyRouteRoster()
    {
        if (!m_Healthy || !m_Config) { return null; }
        HCInfectedVarietyConfig variety = HCInfectedVariety.HCConfig();
        if (!variety || !variety.EnableMigration) { return null; }
        array<ref HCInfectedActor> actors = m_Actors;
        int count = actors.Count();
        // MaxTracked is the existing validated actor cap. Never truncate a
        // place roster if the owner has somehow exceeded that cap.
        if (count < 1 || count > m_Config.MaxTracked) { return null; }
        array<Man> players = HCPerfPlayers.HCGet();
        map<string, bool> visited = new map<string, bool>;
        // At most MaxTracked candidates and MaxTracked members per place.
        // Advance before testing so blocked places cannot pin the next scan.
        for (int scan = 0; scan < count; scan++)
        {
            m_HCVarietyRouteCursor = m_HCVarietyRouteCursor % count;
            HCInfectedActor candidate = actors[m_HCVarietyRouteCursor];
            m_HCVarietyRouteCursor = (m_HCVarietyRouteCursor + 1) % count;
            if (!candidate) { continue; }
            ZombieBase candidateBody = candidate.InfectedEntity;
            if (!candidateBody || !candidateBody.IsAlive() || !candidateBody.HCVarietyTriedDormant() || candidateBody.HCVarietyRouteTried()) { continue; }
            if (candidate.GroupId != 0 || candidate.SearchPack || candidate.EverAssigned) { continue; }
            string place = candidateBody.HCVarietyPlace();
            if (place == "" || visited.Contains(place)) { continue; }
            visited.Insert(place, true);
            array<HCInfectedActor> roster = new array<HCInfectedActor>;
            bool blocked = false;
            foreach (HCInfectedActor actor : actors)
            {
                if (!actor) { continue; }
                ZombieBase body = actor.InfectedEntity;
                if (!body || !body.IsAlive() || !body.HCVarietyTriedDormant() || body.HCVarietyRouteTried()) { continue; }
                if (actor.GroupId != 0 || actor.SearchPack || actor.EverAssigned || body.HCVarietyPlace() != place) { continue; }
                // Wait for the whole capped place group, without starving
                // awake hidden groups elsewhere. Existing native owners win.
                if (body.HCVarietyDormant() || body.GetMindStateSynced() != DayZInfectedConstants.MINDSTATE_CALM) { blocked = true; break; }
                if (!HCInfectedVariety.HCHidden(body.GetPosition(), players)) { blocked = true; break; }
                if (roster.Count() >= variety.GroupMembers) { blocked = true; break; }
                roster.Insert(actor);
            }
            if (!blocked && roster.Count() > 0) { return roster; }
        }
        return null;
    }
}

modded class HCInfectedVarietyModule
{
    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        HCInfectedVarietyRoutes.HCStart();
    }
    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (m_Running && m_Variety) { HCInfectedVarietyRoutes.HCStep(m_Clock); }
    }
    override void OnStop()
    {
        HCInfectedVarietyRoutes.HCStop();
        super.OnStop();
    }
}
