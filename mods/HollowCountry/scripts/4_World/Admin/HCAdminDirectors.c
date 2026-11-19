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
// Test-kit hooks (each only primes the owner's normal bounded path, never a
// parallel spawner): memory <=3 normal Record calls; clear deletes only the
// admin sitter; radio/deaddrop/loot/forage/decay clear one owner timer and
// request that owner's own next tick (<=1 row/node/town; no loot or item is
// created here); weather picks a seeded day within 64 for the owner's profile.

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
    // handle: native economy owns normal cleanup. Only the explicit admin
    // clear command deletes it, never an automatic refill.
    protected Object m_HCAdminSitter;

    string HCAdminCounts()
    {
        if (!m_Healthy || !m_State) { return "active=n/a budget=unavailable admission=" + AdmissionStatus(); }
        int cap = Math.Min(m_Config.MaxTracked, m_MemberCap);
        return "tracked=" + m_Actors.Count().ToString() + " tracked_cap=" + cap.ToString() + " reserved=" + m_State.Reserved.ToString() + " member_cap=" + m_MemberCap.ToString() + " groups=" + m_State.Groups.Count().ToString() + " group_cap=" + m_GroupCap.ToString();
    }

    // HCLODMaterialize supplies tracked fresh bodies, but no normal service can
    // turn a fresh standing body into a reversible dormant crawler. The native
    // ZombieBase.c:811-818 crawl transition is injury, not a resting posture.
    // Do not allocate a live body only to discover that missing transition.
    bool HCAdminDormant(vector pos, out string reason)
    {
        reason = "missing-hook-HCRequestFreshDormant; fresh-body-rest-transition-unavailable; runtime=PENDING";
        return false;
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
        if (!HCPostureAdmission.HCCanEnter("sit_wall"))
        {
            reason = "created-at-8m; pose-refused:" + HCPostureAdmission.HCPostureRefusal("sit_wall") + "; runtime-unverified";
        }
        return true;
    }

    bool HCAdminClearSitter(out string reason)
    {
        reason = "no-admin-sitter";
        if (!m_HCAdminSitter) { return false; }
        GetGame().ObjectDelete(m_HCAdminSitter);
        m_HCAdminSitter = null;
        reason = "admin-sitter-deleted; other infected untouched";
        return true;
    }

    string HCAdminNear(vector pos)
    {
        if (!m_HCAdminSitter) { return "admin_sitter=none"; }
        float distance = Math.Sqrt(vector.DistanceSq(pos, m_HCAdminSitter.GetPosition()));
        return "admin_sitter=present distance=" + Math.Round(distance).ToString() + "m";
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

    // Metadata-only controls use the existing configured camp cap and store.
    // No distance threshold, player scan, world fact, inventory or body creation.
    protected HCCampRecord HCAdminSelectCamp(vector pos, out string reason)
    {
        reason = "camp-service-unavailable";
        if (!m_Running || !m_Data || !m_Data.Camps) { return null; }
        reason = "camp-configured-cap-exceeded";
        int cap = HCAILimits.Get().MaxCamps;
        if (m_Data.Camps.Count() > cap) { return null; }
        int now = HCWorldClock.UTC();
        reason = "camp-clock-unavailable";
        if (now < 1 || now < m_LastUtc) { return null; }
        HCCampRecord selected;
        float best = -1;
        array<ref HCCampRecord> camps = m_Data.Camps;
        for (int candidateIndex = 0; candidateIndex < camps.Count(); candidateIndex++)
        {
            reason = "camp-admin-shared-work-budget";
            if (!HCServer.Get().HCTickWork().HCTake(1)) { return null; }
            HCCampRecord candidate = camps[candidateIndex];
            if (!candidate) { continue; }
            float distance = vector.DistanceSq(pos, candidate.Position);
            if (best < 0 || distance < best) { selected = candidate; best = distance; }
        }
        reason = "no-recognised-camp";
        return selected;
    }

    bool HCAdminTier(vector pos, int requested, out string reason)
    {
        reason = "camp-service-unavailable";
        if (!m_Running) { return false; }
        // 0..3 is the existing HCCampStore schema, not a new tunable limit.
        reason = "camp-tier-must-be-0-to-3";
        if (requested < 0 || requested > 3) { return false; }
        HCCampRecord selected = HCAdminSelectCamp(pos, reason);
        if (!selected) { return false; }
        int previous = selected.Tier;
        selected.Tier = requested;
        reason = "camp-tier-persistence-refused";
        if (!Commit(HCWorldClock.UTC())) { selected.Tier = previous; return false; }
        reason = "camp-tier-persisted; next-normal-scan-reclassifies; runtime=PENDING";
        return true;
    }

    bool HCAdminArrival(vector pos, bool raid, out string reason)
    {
        HCCampRecord selected = HCAdminSelectCamp(pos, reason);
        if (!selected) { return false; }
        return HCAdminRequestArrival(selected, raid, reason);
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

// Test-kit hooks below. Each reads or primes ONE owner's normal path.
modded class HCInfectedMemory
{
    static string HCAdminCounts()
    {
        if (!Active()) { return "active=n/a cells_cap=64 record_cap=32/s"; }
        return "cells=" + s_Instance.m_State.Cells.Count().ToString() + " cells_cap=64 record_cap=32/s";
    }

    static string HCAdminNear(vector pos)
    {
        if (!Active()) { return "heat=unavailable"; }
        float heat = Heat(pos);
        return "heat=" + heat.ToString() + " cohort=" + CohortSizeAtHeat(heat, 6).ToString() + " alert_limit=" + ResponseLimitAtHeat(heat).ToString() + " cell=500m";
    }

    // shots 1..3 call the normal Record path at full loudness (0.35 heat each,
    // clamped at 1). 0 removes only the 500 m cell under the admin.
    static bool HCAdminHeat(vector pos, int shots, out string reason)
    {
        reason = "infected-memory-unavailable";
        if (!Active()) { return false; }
        reason = "heat-shots-0-to-3";
        if (shots < 0 || shots > 3) { return false; }
        reason = "heat-position-invalid";
        if (!HCInfectedStore.ValidPosition(pos)) { return false; }
        if (shots == 0)
        {
            int cellX = Math.Floor(pos[0] / 500.0);
            int cellZ = Math.Floor(pos[2] / 500.0);
            for (int cellIndex = 0; cellIndex < s_Instance.m_State.Cells.Count(); cellIndex++)
            {
                HCInfectedMemoryCell cell = s_Instance.m_State.Cells[cellIndex];
                if (cell.X == cellX && cell.Z == cellZ)
                {
                    s_Instance.m_State.Cells.Remove(cellIndex);
                    s_Instance.m_Dirty = true;
                    reason = "heat-cell-cleared; next horde and alert use base cohort";
                    return true;
                }
            }
            reason = "no-heat-in-this-cell";
            return false;
        }
        for (int shot = 0; shot < shots; shot++) { Record(pos, 1); }
        float heat = Heat(pos);
        // Record() drops samples past its per-second cap or without a clock.
        reason = "heat-record-refused-or-capped";
        if (heat <= 0) { return false; }
        reason = "heat-recorded shots=" + shots.ToString() + " heat=" + heat.ToString() + " cohort=" + CohortSizeAtHeat(heat, 6).ToString() + " alert_limit=" + ResponseLimitAtHeat(heat).ToString() + "; next horde adoption in this 500 m cell uses it";
        return true;
    }
}

modded class HCRadioChatter
{
    string HCAdminCounts()
    {
        if (!m_Store || !m_Store.Healthy()) { return "active=n/a channels=n/a"; }
        int busy = 0;
        if (m_Channel) { busy = 1; }
        return "channels=" + m_Store.Data.Channels.Count().ToString() + " busy=" + busy.ToString() + " fallback=" + m_Fallback.Count().ToString() + "/4 channel_gap=600s";
    }

    bool HCAdminRadio(PlayerBase player, out string reason)
    {
        reason = "radio-service-unavailable";
        if (!m_Store || !m_Store.Healthy() || m_Store.Data.Channels.Count() != 5) { return false; }
        reason = "radio-channel-busy; wait for the current line to finish";
        if (m_Channel) { return false; }
        for (int channelIndex = 0; channelIndex < 5; channelIndex++)
        {
            HCRadioChannel channel = m_Store.Data.Channels[channelIndex];
            if (!Receiving(player, channel.Frequency)) { continue; }
            int previous = channel.LastSent;
            channel.LastSent = 0;
            if (!m_Store.Save())
            {
                channel.LastSent = previous;
                reason = "radio-channel-save-refused";
                return false;
            }
            m_ChannelCursor = channelIndex;
            reason = "rate-limit-cleared freq=" + channel.Frequency.ToString() + "; normal radio tick sends the next line to tuned powered radios";
            return true;
        }
        reason = "no-receiving-radio; carry a powered personal radio, receiving, tuned to 87.8 89.5 91.3 94.6 or 96.6";
        return false;
    }
}

modded class HCDeadDrops
{
    string HCAdminCounts()
    {
        if (!m_Ready || !m_State) { return "active=n/a drops=n/a"; }
        int deposits = 0;
        int work = Math.Min(64, Count());
        for (int rowIndex = 0; rowIndex < work; rowIndex++) { deposits += m_State.Rows[rowIndex].Deposits; }
        return "drops=" + Count().ToString() + " deposits=" + deposits.ToString() + " deposit_cap=4/drop day_gap=1";
    }

    string HCAdminNear(vector pos)
    {
        if (!m_Ready || !m_State) { return "dead_drop=unavailable"; }
        int selected = -1;
        float best = 4000000;
        int work = Math.Min(64, Count());
        for (int rowIndex = 0; rowIndex < work; rowIndex++)
        {
            float distance = vector.DistanceSq(pos, m_State.Rows[rowIndex].Cache.Position);
            if (distance < best) { selected = rowIndex; best = distance; }
        }
        if (selected < 0) { return "dead_drop=none-within-2000m"; }
        HCDeadDropRow row = m_State.Rows[selected];
        int quarantined = 0;
        if (row.Quarantined) { quarantined = 1; }
        return "dead_drop=" + row.Id + " distance=" + Math.Round(Math.Sqrt(best)).ToString() + "m phase=" + row.Cache.Phase.ToString() + " used=" + row.Deposits.ToString() + "/4 next_day=" + row.NextDay.ToString() + " today=" + HCEscalationClock.Day().ToString() + " quarantined=" + quarantined.ToString();
    }

    bool HCAdminDeadDrop(vector pos, out string reason)
    {
        reason = "dead-drop-service-unavailable";
        if (!m_Ready || !m_State) { return false; }
        int selected = -1;
        float best = 1000000;
        int work = Math.Min(64, Count());
        for (int rowIndex = 0; rowIndex < work; rowIndex++)
        {
            float distance = vector.DistanceSq(pos, m_State.Rows[rowIndex].Cache.Position);
            if (distance < best) { selected = rowIndex; best = distance; }
        }
        reason = "no-dead-drop-within-1000m";
        if (selected < 0) { return false; }
        HCDeadDropRow row = m_State.Rows[selected];
        reason = "dead-drop-quarantined id=" + row.Id;
        if (row.Quarantined) { return false; }
        reason = "deposits-exhausted id=" + row.Id + " used=4/4";
        if (row.Deposits >= 4) { return false; }
        int today = HCEscalationClock.Day();
        if (row.NextDay > today)
        {
            row.NextDay = today;
            m_Dirty = true;
        }
        reason = "dead-drop-persistence-refused";
        if (!SaveChanged()) { return false; }
        m_Next = selected;
        m_Elapsed = 60;
        reason = "dead-drop-due id=" + row.Id + " used=" + row.Deposits.ToString() + "/4; next 60 s tick runs the normal crate and one house-item deposit (needs a player within 500 m of the crate and a holdout house)";
        return true;
    }
}

modded class HCSearchRefreshModule
{
    string HCAdminCounts()
    {
        if (!Active()) { return "active=n/a timers=n/a"; }
        return "timers=" + m_State.Rows.Count().ToString() + " pending=" + m_Pending.ToString() + " timers_cap=" + MAX_RECORDS.ToString() + " per_minute=" + RECORDS_PER_MINUTE.ToString();
    }

    // Ages ONLY the oldest pending timer by its own interval; the module's
    // normal minute tick then marks it Ready. No loot is created here.
    bool HCAdminDue(out string reason)
    {
        reason = "loot-refresh-service-unavailable";
        if (!Active()) { return false; }
        int selected = -1;
        int oldest = 0;
        for (int rowIndex = 0; rowIndex < m_State.Rows.Count(); rowIndex++)
        {
            HCSearchRefreshRow candidate = m_State.Rows[rowIndex];
            if (candidate.Ready) { continue; }
            if (selected < 0 || candidate.SearchedUtc < oldest)
            {
                selected = rowIndex;
                oldest = candidate.SearchedUtc;
            }
        }
        reason = "no-pending-refresh-timer; search a container first, a timer starts at the search";
        if (selected < 0) { return false; }
        int now = HCGroupClock.Utc();
        reason = "loot-refresh-clock-behind";
        if (now < m_State.LastUtc) { return false; }
        HCSearchRefreshRow row = m_State.Rows[selected];
        int previousSearched = row.SearchedUtc;
        int previousLast = m_State.LastUtc;
        row.SearchedUtc = now - HCSearchRefreshPolicy.Interval(row.SiteId);
        m_State.LastUtc = now;
        if (!m_Store.Save(m_State))
        {
            row.SearchedUtc = previousSearched;
            m_State.LastUtc = previousLast;
            reason = "refresh-timer-save-refused";
            return false;
        }
        m_Next = selected;
        m_Minute = 60.0;
        reason = "oldest-timer-aged site=" + row.SiteId + "; next tick marks it Ready, no loot created; search that container again to see the refresh";
        return true;
    }
}

modded class HCForageModule
{
    string HCAdminCounts()
    {
        if (!m_Healthy || !m_Nodes) { return "active=n/a nodes=n/a"; }
        int live = 0;
        for (int nodeIndex = 0; nodeIndex < m_Nodes.Count(); nodeIndex++)
        {
            if (m_Nodes[nodeIndex].Item) { live++; }
        }
        return "nodes=" + m_Nodes.Count().ToString() + " live=" + live.ToString() + " nodes_cap=40 cell_live_cap=3 spawn_tick=10s";
    }

    string HCAdminNear(vector pos)
    {
        if (!m_Healthy || !m_Nodes) { return "forage=unavailable"; }
        int cellX = Math.Floor(pos[0] / 200);
        int cellZ = Math.Floor(pos[2] / 200);
        int inCell = 0;
        int live = 0;
        for (int nodeIndex = 0; nodeIndex < m_Nodes.Count(); nodeIndex++)
        {
            HCForageNode node = m_Nodes[nodeIndex];
            if (node.Spot.CellX != cellX || node.Spot.CellZ != cellZ) { continue; }
            inCell++;
            if (node.Item) { live++; }
        }
        return "forage_cell=" + cellX.ToString() + "," + cellZ.ToString() + " nodes=" + inCell.ToString() + " live=" + live.ToString() + " month=" + HCAdminMonth().ToString() + " season_months=6-11";
    }

    protected int HCAdminMonth()
    {
        int year;
        int month;
        int day;
        int hour;
        int minute;
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
        return month;
    }

    // Clears only idle cooldowns in the admin's 200 m cell and asks the normal
    // 10 s tick to run. The tick still requires forest surface, a slot 30 m
    // away from every player, and the 3 per cell and 40 total live caps.
    bool HCAdminForage(PlayerBase player, out string reason)
    {
        reason = "forage-service-unavailable";
        if (!m_Healthy || !m_Nodes) { return false; }
        int month = HCAdminMonth();
        reason = "forage-out-of-season month=" + month.ToString() + "; season months 6 to 11";
        if (month < 6 || month > 11) { return false; }
        vector position = player.GetPosition();
        int cellX = Math.Floor(position[0] / 200);
        int cellZ = Math.Floor(position[2] / 200);
        int cleared = 0;
        for (int nodeIndex = 0; nodeIndex < m_Nodes.Count(); nodeIndex++)
        {
            HCForageNode node = m_Nodes[nodeIndex];
            if (node.Spot.CellX != cellX || node.Spot.CellZ != cellZ) { continue; }
            if (node.Item || node.WasLive) { continue; }
            if (node.Spot.ReadyUtc > 0)
            {
                node.Spot.ReadyUtc = 0;
                cleared++;
            }
        }
        if (cleared > 0) { m_Dirty = true; }
        m_Elapsed = 10;
        reason = "forage-primed cleared=" + cleared.ToString() + " cell=" + cellX.ToString() + "," + cellZ.ToString() + "; normal tick spawns one node when you stand in forest 30 m or more from its slot (cycles 3 slots, up to 30 s)";
        return true;
    }
}

modded class HCSettlementDecay
{
    string HCAdminCounts()
    {
        if (m_Fault || !m_State) { return "active=n/a towns=n/a"; }
        int ransacked = 0;
        int work = Math.Min(256, m_State.Towns.Count());
        for (int townIndex = 0; townIndex < work; townIndex++)
        {
            if (m_State.Towns[townIndex].Ransack > 0) { ransacked++; }
        }
        int pending = 0;
        if (m_HistoryPending) { pending = 1; }
        return "towns=" + m_State.Towns.Count().ToString() + " ransacked=" + ransacked.ToString() + " day=" + HCEscalationClock.Day().ToString() + " scan_pending=" + pending.ToString();
    }

    string HCAdminNear(vector pos)
    {
        if (m_Fault || !m_State || !m_Catalog) { return "decay=unavailable"; }
        int selected = -1;
        float best = 25000000;
        int work = Math.Min(Math.Min(m_State.Towns.Count(), m_Catalog.Places.Count()), 256);
        for (int townIndex = 0; townIndex < work; townIndex++)
        {
            float distance = vector.DistanceSq(pos, m_Catalog.Places[townIndex].Position);
            if (distance < best) { selected = townIndex; best = distance; }
        }
        if (selected < 0) { return "decay=none-within-5000m"; }
        HCSettlementTown town = m_State.Towns[selected];
        return "town=" + town.Id + " distance=" + Math.Round(Math.Sqrt(best)).ToString() + "m ransack=" + town.Ransack.ToString() + "/3 barricades=" + town.Barricades.ToString() + "/2 remains=" + town.Remains.ToString() + " notices=" + town.Notices.ToString();
    }

    // Queues the nearest town for the owner's normal step; the owner's history
    // scan, quiet gate and visual gates still run. Escalation day drives severity.
    bool HCAdminTown(vector pos, out string reason)
    {
        reason = "decay-not-initialised; wait for the first normal step";
        if (m_Fault || !m_State || !m_Catalog) { return false; }
        reason = "history-scan-in-progress; retry in a few seconds";
        if (m_HistoryPending) { return false; }
        int selected = -1;
        float best = 1000000;
        int work = Math.Min(Math.Min(m_State.Towns.Count(), m_Catalog.Places.Count()), 256);
        for (int townIndex = 0; townIndex < work; townIndex++)
        {
            float distance = vector.DistanceSq(pos, m_Catalog.Places[townIndex].Position);
            if (distance < best) { selected = townIndex; best = distance; }
        }
        reason = "no-town-within-1000m";
        if (selected < 0) { return false; }
        m_Cursor = selected;
        m_Elapsed = 10;
        reason = "town-queued id=" + m_State.Towns[selected].Id + " ransack=" + m_State.Towns[selected].Ransack.ToString() + "/3; normal step runs within seconds, visuals still wait for the quiet gate";
        return true;
    }
}

modded class HCBodyStories
{
    string HCAdminCounts()
    {
        if (!m_Store || !m_Store.Healthy()) { return "active=n/a bodies=n/a"; }
        return "bodies=" + m_Store.Data.Bodies.Count().ToString() + "/3 observed=" + m_Observed.Count().ToString() + "/3 trigger=trusted-death-producer-pending";
    }
}
