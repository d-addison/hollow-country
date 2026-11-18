// W6 #133. Narrow admin adapters; no replacement directors or stores.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:612 ConfigIsExisting,
// :703 CreateObjectEx, :705 ObjectDelete, :914 GetTickTime, :930 bounded
// GetObjectsAtPosition3D, :945 GetPlayers, :1176 SurfaceY, :1196 SurfaceIsSea;
// Entities/Object.c:287 GetPosition, :314 GetDirection, :370 GetCollisionBox,
// :517 IsAlive; Entities/Building.c:31 GetDoorCount, :73 GetDoorSoundPos;
// CE/CentralEconomy.c:18 ECE_INITAI, :38 ECE_PLACE_ON_SURFACE;
// 4_World/Entities/Creatures/Infected/ZombieBase.c:182 GetMindStateSynced;
// 1_Core/proto/EnMath.c:225 AbsFloat, :305 Sqrt, :540 Clamp, :566 Max;
// EnConvert.c:30 ToString, :210 DistanceSq; EnMath3D.c:18 Vector;
// EnScript.c:94 Cast, :380,394,407 Count/Find/Insert; EnString.c:171 ToLower;
// gameplay.c:636 GetGame.
// No recurring tick. One admitted command/core tick. Work ceilings: sitter
// 128 queried objects +64 doors +5 surface probes, horde <=24 tracked actors
// then existing <=32-work adoption, event <=32 sites/7 missions, scene <=4
// chains then ONE normal director Work (existing geometry query caps), camp
// <=32 camps then ONE normal StepCamp; holdout <=24 rows then ONE occupancy
// transition; day ONE normal persisted clock change. No clock aging of camps.

class HCAdminPlacement
{
    // Shared bounded point clearance for future admin placement consumers.
    // Conservative refusal on unknown geometry; never correct an entity's move.
    static bool HCClear(vector pos)
    {
        if (!HCDebugSnapshot.HCPositionValid(pos) || pos[1] != pos[1]) { return false; }
        if (GetGame().SurfaceIsSea(pos[0], pos[2])) { return false; }
        array<Object> objects = new array<Object>;
        array<CargoBase> proxies = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(pos, 40, objects, proxies);
        if (objects.Count() > 128 || proxies.Count() > 0) { return false; }
        int doorWork = 0;
        for (int objectIndex = 0; objectIndex < objects.Count(); objectIndex++)
        {
            Object obstacle = objects[objectIndex];
            if (!obstacle) { continue; }
            Man person = Man.Cast(obstacle);
            if (person)
            {
                if (vector.DistanceSq(pos, person.GetPosition()) <= 4) { return false; }
                continue;
            }
            Building building = Building.Cast(obstacle);
            if (building)
            {
                int doors = building.GetDoorCount();
                if (doors < 0 || doors > 32 || doorWork + doors > 64) { return false; }
                doorWork += doors;
                for (int doorIndex = 0; doorIndex < doors; doorIndex++)
                {
                    if (!HCSceneKits.OutsideDoor(pos, building.GetDoorSoundPos(doorIndex), 0.6)) { return false; }
                }
            }
            vector bounds[2];
            if (!obstacle.GetCollisionBox(bounds)) { return false; }
            float extentX = Math.Max(Math.AbsFloat(bounds[0][0]), Math.AbsFloat(bounds[1][0]));
            float extentZ = Math.Max(Math.AbsFloat(bounds[0][2]), Math.AbsFloat(bounds[1][2]));
            float clearance = Math.Sqrt(extentX * extentX + extentZ * extentZ) + 2;
            vector center = obstacle.GetPosition();
            float dx = center[0] - pos[0];
            float dz = center[2] - pos[2];
            if (dx * dx + dz * dz <= clearance * clearance) { return false; }
        }
        float east = GetGame().SurfaceY(pos[0] + 1, pos[2]);
        float west = GetGame().SurfaceY(pos[0] - 1, pos[2]);
        float north = GetGame().SurfaceY(pos[0], pos[2] + 1);
        float south = GetGame().SurfaceY(pos[0], pos[2] - 1);
        if (east != east || west != west || north != north || south != south) { return false; }
        if (Math.AbsFloat(east - pos[1]) > 0.3 || Math.AbsFloat(west - pos[1]) > 0.3) { return false; }
        if (Math.AbsFloat(north - pos[1]) > 0.3 || Math.AbsFloat(south - pos[1]) > 0.3) { return false; }
        return true;
    }
}

modded class HCInfectedModule
{
    // One native admin-created body at a time, including its corpse. Weak
    // handle: native economy owns normal cleanup; never delete it to refill.
    protected Object m_HCAdminSitter;

    string HCAdminCounts()
    {
        if (!m_Healthy || !m_State) { return "active=n/a budget=unavailable admission=" + AdmissionStatus(); }
        int cap = Math.Min(m_Config.MaxTracked, m_MemberCap);
        return "tracked=" + m_Actors.Count().ToString() + " tracked_cap=" + cap.ToString() + " reserved=" + m_State.Reserved.ToString() + " member_cap=" + m_MemberCap.ToString() + " groups=" + m_State.Groups.Count().ToString() + " group_cap=" + m_GroupCap.ToString();
    }

    bool HCAdminSitter(PlayerBase player, out string reason)
    {
        reason = "infected-admission-unavailable";
        if (!m_Healthy || !m_Config || !m_State) { return false; }
        reason = "sitter-body-cap=1; includes-corpse";
        if (m_HCAdminSitter) { return false; }
        reason = "infected-tracking-or-registration-cap";
        if (m_Actors.Count() >= Math.Min(m_Config.MaxTracked, m_MemberCap) || m_RegistrationAttempts >= m_WorkCap) { return false; }
        vector forward = player.GetDirection();
        forward[1] = 0;
        float length = Math.Sqrt(forward[0] * forward[0] + forward[2] * forward[2]);
        reason = "forward-vector-unavailable";
        if (length < 0.1 || length != length) { return false; }
        vector pos = player.GetPosition() + forward * (8 / length);
        pos[1] = GetGame().SurfaceY(pos[0], pos[2]);
        reason = "placement-clearance-or-query-cap; use-open-flat-ground";
        if (!HCAdminPlacement.HCClear(pos)) { return false; }
        // String lookup deliberately avoids a compile dependency on the addon.
        Object body = GetGame().CreateObjectEx("HC_ZmbM_Sitter", pos, ECE_INITAI | ECE_PLACE_ON_SURFACE);
        ZombieBase infected = ZombieBase.Cast(body);
        reason = "native-create-or-track-refused";
        if (!infected)
        {
            if (body) { GetGame().ObjectDelete(body); }
            return false;
        }
        if (!FindActor(infected) && !Track(infected)) { GetGame().ObjectDelete(body); return false; }
        m_HCAdminSitter = body;
        reason = "created-at-8m; addon-owns-pose; runtime-unverified";
        return true;
    }

    bool HCAdminHorde(vector pos, out string reason)
    {
        reason = "horde-admission-unavailable";
        if (!m_Healthy || !m_State || !m_Hordes || !m_Admission.CEAdoption) { return false; }
        reason = "horde-budget-cap";
        if (m_State.Reserved >= m_MemberCap) { return false; }
        int selected = -1;
        float best = 10000;
        for (int actorIndex = 0; actorIndex < m_Actors.Count(); actorIndex++)
        {
            HCInfectedActor actor = m_Actors[actorIndex];
            if (!actor.InfectedEntity || !actor.InfectedEntity.IsAlive()) { continue; }
            if (!HCInfectedStore.ValidPosition(actor.InfectedEntity.GetPosition())) { continue; }
            if (actor.EverAssigned || actor.SearchPack || actor.Profile == "native_injured") { continue; }
            int mind = actor.InfectedEntity.GetMindStateSynced();
            if (mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT) { continue; }
            float distance = vector.DistanceSq(pos, actor.InfectedEntity.GetPosition());
            if (distance < best) { best = distance; selected = actorIndex; }
        }
        reason = "no-eligible-native-cohort-within-100m";
        if (selected < 0) { return false; }
        int nowUtc = HCGroupClock.Utc();
        reason = "horde-clock-unavailable";
        if (nowUtc < m_LastUtc || nowUtc < 1) { return false; }
        int before = m_State.Reserved;
        m_AdoptionCursor = selected;
        TryAdopt(nowUtc);
        reason = "normal-adoption-refused; check-budget-quarantine-genuine-cue-and-native-admission";
        if (!m_Healthy || m_State.Reserved <= before) { return false; }
        reason = "normal-native-cohort-adoption; runtime-unverified";
        return true;
    }
}

modded class HCEventModule
{
    string HCAdminCounts()
    {
        if (!m_Runtime || !m_Config) { return "active=n/a budget=unavailable"; }
        HCEventRuntimeState state = m_Runtime.Snapshot();
        if (!state) { return "active=n/a budget=unavailable"; }
        int active = 0;
        for (int runIndex = 0; runIndex < state.Runs.Count(); runIndex++)
        {
            if (state.Runs[runIndex].Phase != HCEventRunPhase.CLOSED) { active++; }
        }
        return "active=" + active.ToString() + " run_cap=" + m_Config.MaxRuns.ToString();
    }

    bool HCAdminEvent(vector pos, out string reason)
    {
        reason = "event-service-or-site-cap-unavailable";
        if (!m_Runtime || !m_Config || !m_NativeObserver || m_Stopping) { return false; }
        if (m_Config.Sites.Count() > 32) { return false; }
        HCEventContext context = Context();
        HCEventSite nearest;
        float best = 500000000;
        for (int siteIndex = 0; siteIndex < m_Config.Sites.Count(); siteIndex++)
        {
            HCEventSite site = m_Config.Sites[siteIndex];
            if (!site || !site.Reviewed) { continue; }
            string world = site.WorldName;
            world.ToLower();
            if (world != context.WorldName) { continue; }
            float distance = vector.DistanceSq(pos, site.Position);
            if (distance < best) { best = distance; nearest = site; }
        }
        reason = "no-reviewed-event-site";
        if (!nearest) { return false; }
        array<ref HCEventMission> roster = HCEventRoster.Build(nearest, AIReady(context));
        reason = "roster-gate-or-normal-runtime-admission-refused";
        for (int missionIndex = 0; missionIndex < roster.Count(); missionIndex++)
        {
            HCEventMission mission = roster[missionIndex];
            if (m_Runtime.HasMission(mission.Id)) { continue; }
            HCEventWorldBinding.Bind(m_NativeObserver, mission);
            int code = m_Runtime.Announce(mission, context);
            reason = "normal-event-director-code=" + code.ToString();
            if (code == HCEventCode.OK)
            {
                RememberAnnounced(mission.Id);
                reason = "announced-nearest-site; join-via-O; runtime-unverified";
                return true;
            }
            return false;
        }
        return false;
    }
}

modded class HCScenesModule
{
    protected static HCScenesModule s_HCAdminScenes;

    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (m_Running) { s_HCAdminScenes = this; }
    }

    override void OnStop()
    {
        if (s_HCAdminScenes == this) { s_HCAdminScenes = null; }
        super.OnStop();
    }

    static string HCAdminCounts()
    {
        if (!s_HCAdminScenes || !s_HCAdminScenes.m_Running) { return "active=n/a lease_cap=2 admission=unavailable"; }
        return "leases=" + s_HCAdminScenes.m_Leases.Count().ToString() + " lease_cap=2";
    }

    static bool HCAdminScene(vector pos, out string reason)
    {
        reason = "scene-service-unavailable";
        if (!s_HCAdminScenes || !s_HCAdminScenes.m_Running) { return false; }
        return s_HCAdminScenes.HCAdminNearestScene(pos, reason);
    }

    bool HCAdminNearestScene(vector pos, out string reason)
    {
        reason = "scene-lease-cap=2";
        if (m_Leases.Count() >= 2) { return false; }
        int selected = -1;
        float best = 500000000;
        int work = Math.Min(4, m_State.Chains.Count());
        for (int chainIndex = 0; chainIndex < work; chainIndex++)
        {
            HCSceneChain chain = m_State.Chains[chainIndex];
            if (chain.Cancelled || chain.Complete || Lease(chain.Id)) { continue; }
            HCEventSite site = HCSceneChains.Site(m_State.Catalog.Chains[chainIndex].SiteId);
            if (!site) { continue; }
            float distance = vector.DistanceSq(pos, site.Position);
            if (distance < best) { selected = chainIndex; best = distance; }
        }
        reason = "no-unplaced-reviewed-scene";
        if (selected < 0) { return false; }
        int now = Now();
        reason = "scene-clock-unavailable";
        if (now < m_LastNow || now < 1) { return false; }
        // Do not forge completion, reset deadlines or accelerate a live chain.
        HCSceneChain nearest = m_State.Chains[selected];
        reason = "scene-not-due; normal-stage-delay-retained";
        if (now < nearest.DueAt) { return false; }
        m_Cursor = selected;
        Work(now);
        reason = "normal-scene-director-refused; check-preflight-and-observer-gates";
        HCSceneLease placed = Lease(nearest.Id);
        if (!m_Running || nearest.Cancelled || !HCSceneKits.Healthy(placed)) { return false; }
        reason = "nearest-due-scene-placed; runtime-unverified";
        return true;
    }
}

modded class HCCampModule
{
    string HCAdminCounts()
    {
        if (!m_Running || !m_Data) { return "active=n/a camp_cap=32"; }
        return "camps=" + m_Data.Camps.Count().ToString() + " camp_cap=32";
    }

    bool HCAdminCamp(vector pos, array<Man> players, out string reason)
    {
        reason = "camp-service-unavailable";
        if (!m_Running || !m_Data) { return false; }
        HCCampRecord nearest;
        float best = 10000;
        int work = Math.Min(32, m_Data.Camps.Count());
        for (int campIndex = 0; campIndex < work; campIndex++)
        {
            HCCampRecord camp = m_Data.Camps[campIndex];
            float distance = vector.DistanceSq(pos, camp.Position);
            if (distance < best) { nearest = camp; best = distance; }
        }
        reason = "no-recognised-camp-within-100m";
        if (!nearest) { return false; }
        int now = HCWorldClock.UTC();
        reason = "camp-clock-unavailable";
        if (now < m_LastUtc || now < 1) { return false; }
        int previousScan = nearest.LastScan;
        m_Players.Clear();
        for (int playerIndex = 0; playerIndex < players.Count(); playerIndex++)
        {
            if (playerIndex >= 32) { break; }
            m_Players.Insert(players[playerIndex]);
        }
        reason = "camp-observer-cap=32";
        if (players.Count() > 32) { m_Players.Clear(); return false; }
        StepCamp(nearest, now);
        m_Players.Clear();
        reason = "normal-camp-criteria-or-cooldown; no-forced-age-tier-or-theft";
        if (!m_Running || nearest.LastScan == previousScan) { return false; }
        reason = "normal-camp-evaluation tier=" + nearest.Tier.ToString() + "; visitor-gates-retained; runtime-unverified";
        return true;
    }
}

modded class HCHoldouts
{
    bool HCAdminHoldout(vector pos, out string reason)
    {
        reason = "holdout-service-unavailable";
        if (!m_Ready || !m_State) { return false; }
        int selected = -1;
        float best = 10000;
        int work = Math.Min(24, Count());
        for (int rowIndex = 0; rowIndex < work; rowIndex++)
        {
            float distance = vector.DistanceSq(pos, m_State.Rows[rowIndex].Ledger.HousePos);
            if (distance < best) { selected = rowIndex; best = distance; }
        }
        reason = "no-holdout-within-100m";
        if (selected < 0) { return false; }
        int now = HCWorldClock.UTC();
        reason = "holdout-clock-unavailable";
        if (now < 1 || now < m_State.Rows[selected].Ledger.Since) { return false; }
        reason = "normal-occupancy-cooldown-cache-body-or-site-cap";
        if (!HCAdvanceOccupancy(selected, now)) { return false; }
        m_State.Rows[selected].Published = false;
        m_Dirty = true;
        reason = "holdout-persistence-refused";
        if (!SaveChanged()) { return false; }
        PublishState(m_State.Rows[selected]);
        HCSyncLights();
        if (!SaveChanged()) { return false; }
        reason = "holdout-transition-persisted; world-publish-pending";
        if (!m_State.Rows[selected].Published) { return false; }
        reason = "normal-occupancy-transition; no-body-or-loot-fabricated; runtime-unverified";
        return true;
    }
}

modded class HCEscalationClock
{
    static bool HCAdminDay(int requested, out string reason)
    {
        reason = "escalation-clock-unavailable";
        HCEscalationClock clock = s_Instance;
        if (!clock || !clock.m_Healthy) { return false; }
        int now = HCGroupClock.Utc();
        if (now < clock.m_NowUtc || now < 1) { return false; }
        int day = Math.Clamp(requested, 0, 3650);
        int epoch = now - day * 86400;
        if (epoch < 1) { return false; }
        HCEscalationState candidate = new HCEscalationState;
        candidate.Version = clock.m_State.Version;
        candidate.WorldName = clock.m_State.WorldName;
        candidate.EpochUtc = epoch;
        candidate.SavedUtc = now;
        reason = "escalation-persistence-refused";
        if (!HCV2ThreatStore<HCEscalationState>.Save(PATH, candidate, 2048)) { clock.Fail(); return false; }
        clock.m_State = candidate;
        clock.m_NowUtc = now;
        clock.m_LogDay = -1;
        clock.Report();
        reason = "persisted-escalation-day=" + day.ToString() + "; camp-age-and-other-clocks-unchanged; runtime-unverified";
        return true;
    }
}
