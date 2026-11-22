// Installed scripts-1.30.164289 native surfaces:
// 3_Game/AI/AIWorld.c:98 FindPath, :122 SampleNavmeshPosition;
// 3_Game/AI/AIGroupBehaviour.c:9 waypoint DTO, :27 SetWaypoints;
// AIGroup.c:14 GetBehaviour; AIAgent.c:7 GetGroup;
// 3_Game/Entities/DayZAnimal.c:193 GetAIAgent; Object.c:287 GetPosition;
// 4_World/Entities/Creatures/Infected/ZombieBase.c:182 GetMindStateSynced;
// 1_Core/proto/EnScript.c:380 Count; EnMath.c:553 Min;
// 3_Game/Entities/DayZInfectedInputController.c:9-10 mind/retained target.
// No manual steering, script command or generated noise target is used. Stuck recovery (WD-2A-3)
// only re-plans, queues a native door open, or stops counting the member; it never moves an entity.
// Per-member stuck bookkeeping (WD-2A-3). Runtime only.
class HCNavMemberTrack
{
    vector Pos;
    float At;
    float BestSq = -1;
    int Strikes;
    bool Dropped;
}

// Ring of the last 32 places where a pack member got stuck (WD-2A-3). A spot hit three times is a
// known trap: the next member stuck there skips the ladder and is dropped at once. Runtime only,
// never persisted, so there is no stored format to migrate. Only coordinates are ever printed.
class HCNavSpots
{
    static const int CAPACITY = 32;
    static const int TRAP_HITS = 3;
    static const float RADIUS_SQ = 36;
    static const float KEEP_SECONDS = 1800;

    protected static ref array<vector> s_Pos = new array<vector>;
    protected static ref array<float> s_At = new array<float>;
    protected static ref array<int> s_Hits = new array<int>;
    protected static int s_Next;
    protected static int s_Printed;

    protected static int HCFind(vector position, float now)
    {
        for (int slot = 0; slot < s_Pos.Count(); slot++)
        {
            if (now - s_At[slot] > KEEP_SECONDS) { continue; }
            if (vector.DistanceSq(s_Pos[slot], position) <= RADIUS_SQ) { return slot; }
        }
        return -1;
    }

    static void HCNote(vector position, float now)
    {
        int slot = HCFind(position, now);
        if (slot < 0)
        {
            if (s_Pos.Count() < CAPACITY)
            {
                slot = s_Pos.Count();
                s_Pos.Insert(position);
                s_At.Insert(now);
                s_Hits.Insert(0);
            }
            else
            {
                slot = s_Next;
                s_Next = (s_Next + 1) % CAPACITY;
                s_Pos.Set(slot, position);
                s_Hits.Set(slot, 0);
            }
        }
        s_At.Set(slot, now);
        int hits = s_Hits[slot] + 1;
        s_Hits.Set(slot, hits);
        s_Printed++;
        if (s_Printed <= 8 || s_Printed % 32 == 0 || hits == TRAP_HITS)
        {
            Print("[HC Infected] nav problem spot x=" + Math.Round(position[0]).ToString() + " z=" + Math.Round(position[2]).ToString() + " hits=" + hits.ToString() + " runtime=PENDING");
        }
    }

    static bool HCIsTrap(vector position, float now)
    {
        int slot = HCFind(position, now);
        return slot >= 0 && s_Hits[slot] >= TRAP_HITS;
    }
}

// Per-group quarantine (WD-2A-4), replacing the former global release ledger that blocked every new
// pack route. A group that was given up on (stalled, or every tracked member dropped) is refused as a
// Start candidate for a cooldown; every other group keeps routing. Entries expire; nothing blocks
// permanently. Runtime only.
class HCPackQuarantine
{
    static const int CAPACITY = 16;
    static const float COOLDOWN_SECONDS = 90;

    protected static ref array<AIGroup> s_Groups = new array<AIGroup>;
    protected static ref array<float> s_Until = new array<float>;

    static void HCAdd(AIGroup group, float now)
    {
        if (!group) { return; }
        int index = s_Groups.Find(group);
        if (index >= 0)
        {
            s_Until.Set(index, now + COOLDOWN_SECONDS);
            return;
        }
        HCAge(now);
        if (s_Groups.Count() >= CAPACITY)
        {
            s_Groups.RemoveOrdered(0);
            s_Until.RemoveOrdered(0);
        }
        s_Groups.Insert(group);
        s_Until.Insert(now + COOLDOWN_SECONDS);
        HCModuleReadiness.HCUse("Infected", "group_quarantine");
    }

    static bool HCHas(AIGroup group, float now)
    {
        if (!group) { return false; }
        int index = s_Groups.Find(group);
        return index >= 0 && now < s_Until[index];
    }

    // Drops expired entries and groups the engine already deleted (null).
    static void HCAge(float now)
    {
        for (int index = s_Groups.Count() - 1; index >= 0; index--)
        {
            if (!s_Groups[index] || now >= s_Until[index])
            {
                s_Groups.RemoveOrdered(index);
                s_Until.RemoveOrdered(index);
            }
        }
    }

    static int HCCount() { return s_Groups.Count(); }
}

// Pack-aware door queue (WD-2A-5). A member stuck beside a closed door queues that door (at most 4
// per pack, one door per Tick is opened). Only closed, UNLOCKED doors are opened, through the
// building's own CanDoorBeOpened(m_CheckIfLocked=true) so a lock is never defeated; a standing
// Fortify barricade, bunker doors and locked containers are skipped. An entry that is not served
// within 20 s is dropped, so a pack never waits on a door forever.
class HCNavDoorQueue
{
    static const int CAPACITY = 4;
    static const int MAX_OBJECTS = 64;
    static const int MAX_DOORS_PER_BUILDING = 16;
    static const float SEEK_RADIUS = 6;
    static const float DOOR_RADIUS_SQ = 9;
    static const float WAIT_SECONDS = 20;

    protected ref array<Building> m_Buildings = new array<Building>;
    protected ref array<int> m_Doors = new array<int>;
    protected ref array<float> m_At = new array<float>;
    protected ref array<Object> m_Objects = new array<Object>;
    protected ref array<CargoBase> m_Proxies = new array<CargoBase>;

    int HCCount() { return m_Doors.Count(); }

    protected bool HCQueued(Building building, int door)
    {
        for (int index = 0; index < m_Doors.Count(); index++)
        {
            if (m_Buildings[index] == building && m_Doors[index] == door) { return true; }
        }
        return false;
    }

    protected bool HCBarricaded(vector doorPos, int inspected)
    {
        for (int index = 0; index < inspected; index++)
        {
            Object candidate = m_Objects[index];
            if (!candidate || vector.DistanceSq(candidate.GetPosition(), doorPos) > DOOR_RADIUS_SQ) { continue; }
            if (HCFortifyBridge.HCBlocksDoor(candidate)) { return true; }
        }
        return false;
    }

    // Queue the closed unlocked doors within reach of a stuck member. Returns how many were added.
    int HCDiscover(vector position, float now)
    {
        if (m_Doors.Count() >= CAPACITY) { return 0; }
        m_Objects.Clear();
        m_Proxies.Clear();
        GetGame().GetObjectsAtPosition3D(position, SEEK_RADIUS, m_Objects, m_Proxies);
        int inspected = Math.Min(m_Objects.Count(), MAX_OBJECTS);
        bool fortified = HCFortifyBridge.HCActive();
        int added = 0;
        for (int objectIndex = 0; objectIndex < inspected; objectIndex++)
        {
            Building building = Building.Cast(m_Objects[objectIndex]);
            if (!building || Bunker.Cast(building) || ContainerLockedBase.Cast(building)) { continue; }
            int doors = Math.Min(building.GetDoorCount(), MAX_DOORS_PER_BUILDING);
            for (int door = 0; door < doors; door++)
            {
                if (m_Doors.Count() >= CAPACITY) { return added; }
                if (!building.IsDoorClosed(door)) { continue; }
                vector doorPos = building.GetDoorSoundPos(door);
                if (vector.DistanceSq(doorPos, position) > DOOR_RADIUS_SQ || HCQueued(building, door)) { continue; }
                if (building.IsDoorLocked(door))
                {
                    HCModuleReadiness.HCUse("Infected", "door_locked_skip");
                    continue;
                }
                if (fortified && HCBarricaded(doorPos, inspected)) { continue; }
                m_Buildings.Insert(building);
                m_Doors.Insert(door);
                m_At.Insert(now);
                added++;
            }
        }
        return added;
    }

    // Serves at most ONE queued door per call; stale, open, locked or timed-out entries are dropped.
    // Returns true when a door was opened.
    bool HCProcess(Object caller, float now)
    {
        if (m_Doors.Count() < 1) { return false; }
        Building building = m_Buildings[0];
        int door = m_Doors[0];
        float queuedAt = m_At[0];
        m_Buildings.RemoveOrdered(0);
        m_Doors.RemoveOrdered(0);
        m_At.RemoveOrdered(0);
        if (!building || building.IsPendingDeletion() || now - queuedAt > WAIT_SECONDS) { return false; }
        if (!building.IsDoorClosed(door) || building.IsDoorLocked(door)) { return false; }
        DoorManipulationParams request = new DoorManipulationParams;
        request.m_DoorIndex = door;
        request.m_CheckIfLocked = true;
        request.m_Caller = caller;
        if (!building.CanDoorBeOpened(request)) { return false; }
        building.OpenDoor(door);
        HCModuleReadiness.HCUse("Infected", "pack_door_open");
        return true;
    }
}

class HCNativeInfectedPack
{
    // Last logged release summary, so the status line is emitted on change only. The quarantine is per
    // group (HCPackQuarantine); the former global ledger that blocked every new route is gone.
    protected static int s_ReportedQuarantined;
    // Stuck recovery tuning (WD-2A-3): a member that moved less than STUCK_MIN_MOVE metres over a
    // STUCK_WINDOW second window, while still more than a waypoint radius + STUCK_NEAR away from the
    // waypoint and not in combat, takes a strike. Strike 1 queues a door, strike 2 re-plans the route,
    // strike 3 drops the member from the pack count. Recovery never moves the entity.
    static const float STUCK_WINDOW = 8;
    static const float STUCK_MIN_MOVE = 1.5;
    static const float STUCK_NEAR = 3;
    static const float PENDING_HOLD_SECONDS = 20;
    static const int MAX_REPATHS = 4;
    static const int NAV_FOUND = 1;
    static const int NAV_NONE = 2;
    static const int NAV_DEFERRED = 3;
    AIGroup Group;
    protected ref array<ZombieBase> m_Members = new array<ZombieBase>;
    protected PGFilter m_Filter;
    // Filter profile for the next Reachable call (HCNavFilters.PROFILE_*), the scheduler class of the
    // call (a deferrable caller is refused instead of forced) and the deferral verdict it leaves.
    protected int m_NavProfile;
    protected bool m_NavDeferrable;
    protected bool m_NavDeferred;
    // Route found by the latest Reachable call (reused, never reallocated per call).
    protected ref TVectorArray m_NavPath = new TVectorArray;
    protected ref map<ZombieBase, ref HCNavMemberTrack> m_Tracks = new map<ZombieBase, ref HCNavMemberTrack>;
    protected ref HCNavDoorQueue m_PackDoors;
    protected float m_HoldSince = -1;
    protected int m_Repaths;
    protected int m_Drops;
    protected float m_Expires;
    protected float m_LastProgress;
    protected float m_NextRetarget;
    protected float m_LastRetargetObserved = -1;

    // Hook for Infected/Variety (#121): declared here because modded classes
    // compiled earlier in the chain (HCHordeMigration.c) cannot see methods a
    // later modded class adds (DayZ 021 boot: Undefined function HCVarietyWalkerHerd).
    void HCVarietyWalkerHerd() {}
    // Physical route hook; the migration extension owns authored corridor state.
    bool HCAdmitPatrol(HCHordeRouteSurvey route, int id, float now, int target) { return false; }
    bool HCReinforcePending() { return false; }
    bool HCReinforceActive() { return false; }
    protected int m_RetargetAttempts;
    protected vector m_LastPosition;
    protected bool m_Search;
    protected bool m_Releasing;
    // Presence records transfer intent; retain the expected native owner across
    // failed/no-op AddAgent calls. A missing old owner is never a receipt.
    protected ref map<ZombieBase, AIGroup> m_ReleaseFallbacks = new map<ZombieBase, AIGroup>;
    protected bool m_ReleaseQuarantined;
    protected int m_ReleaseAttempts;
    protected int m_NextReleaseUtc;
    protected ref array<ref BehaviourGroupInfectedPackWaypointParams> m_RoutePlan;
    protected float m_BestRouteDistanceSq = -1;
    // Surveyed rooms awaiting their one-per-tick segment test (ExtendRoute).
    protected ref TVectorArray m_PendingRooms;
    protected vector m_PendingFrom;
    vector RouteEnd;
    int RoutePurpose;
    int RouteResult;
    int RoutePlanned;
    int RouteCompleted;
    // #160 HC-S002: why the latest Start returned false ("" after a success or
    // before the first call). Callers may read it; every refusal also logs once
    // per reason, then every 512th time, so a per-tick caller cannot flood.
    protected string m_RefusalReason;
    // Latched once Start has been called at all (success or refusal), so a
    // quarantine line can tell "Start never ran" from "ran, empty reason".
    protected bool m_HCStartRan;
    protected static ref map<string, int> s_RefusalSeen = new map<string, int>;

    protected bool ActivateWaypoint(float now)
    {
        if (!Group || !m_RoutePlan || RouteCompleted >= m_RoutePlan.Count())
            return false;
        BehaviourGroupInfectedPack behaviour = BehaviourGroupInfectedPack.Cast(Group.GetBehaviour());
        if (!behaviour) return false;
        ref array<ref BehaviourGroupInfectedPackWaypointParams> currentRoute = new array<ref BehaviourGroupInfectedPackWaypointParams>;
        currentRoute.Insert(m_RoutePlan[RouteCompleted]);
        // Native loop=false is patrol, not one-shot stop. Supply one point at a
        // time and advance only on bounded observations of actual owned members.
        behaviour.SetWaypoints(currentRoute, 0, true, false);
        m_BestRouteDistanceSq = -1;
        m_LastProgress = now;
        m_HoldSince = -1;
        HCResetTracks(now);
        return true;
    }

    // A new waypoint restarts every member's progress window; drops stay dropped.
    protected void HCResetTracks(float now)
    {
        for (int index = 0; index < m_Tracks.Count(); index++)
        {
            HCNavMemberTrack track = m_Tracks.GetElement(index);
            track.BestSq = -1;
            track.Strikes = 0;
            track.At = now;
        }
    }

    protected AIWorld GetAIWorld()
    {
        if (!GetGame() || !GetGame().GetWorld()) return null;
        return GetGame().GetWorld().GetAIWorld();
    }

    static int QuarantinedReleaseCount()
    {
        return HCPackQuarantine.HCCount();
    }

    // Bounded status: only the listed groups are refused as Start candidates, and only for the
    // cooldown; new routes for every other group are never blocked.
    static string ReleaseStatus()
    {
        int quarantined = QuarantinedReleaseCount();
        return "pending=0 quarantined=" + quarantined.ToString() + " new_routes_blocked=no";
    }

    static void RetryPendingReleases()
    {
        HCPackQuarantine.HCAge(GetGame().GetTickTime());
        int quarantined = QuarantinedReleaseCount();
        if (quarantined != s_ReportedQuarantined)
        {
            s_ReportedQuarantined = quarantined;
            Print("[HC Infected] native release status: " + ReleaseStatus());
        }
    }

    protected void InitFilter()
    {
        // Shared INF_OUTDOOR / INF_INTERIOR profiles; SetFlags always runs when they are built.
        m_Filter = HCNavFilters.HCFor(HCNavFilters.PROFILE_OUTDOOR);
    }

    // Route lookup order: shared route cache, 32 m flow cache, then one FindPath. A deferrable caller
    // is refused (NAV_DEFERRED) when this tick's FindPath token is spent; a mandatory caller always runs
    // and is counted as forced when it exceeds the token. Failed searches are cached as "no route".
    protected int HCFindRoute(vector from, vector goal, int profile, bool mandatory, TVectorArray path)
    {
        int hit = HCNavRouteCache.HCLookup(profile, from, goal, path);
        if (hit == HCNavRouteCache.HIT_ROUTE) { return NAV_FOUND; }
        if (hit == HCNavRouteCache.HIT_NO_ROUTE) { return NAV_NONE; }
        if (HCHordeFlowCache.HCShare(profile, from, goal, path)) { return NAV_FOUND; }
        if (mandatory)
        {
            HCNavScheduler.HCTakeMandatory();
        }
        else if (!HCNavScheduler.HCTake())
        {
            return NAV_DEFERRED;
        }
        path.Clear();
        PGFilter filter = HCNavFilters.HCFor(profile);
        bool found = GetAIWorld().FindPath(from, goal, filter, path);
        if (!found || path.Count() < 2 || path.Count() > HCNavRouteCache.MAX_POINTS)
        {
            HCNavRouteCache.HCStore(profile, from, goal, null, true);
            return NAV_NONE;
        }
        HCNavRouteCache.HCStore(profile, from, goal, path, false);
        HCHordeFlowCache.HCStore(profile, from, goal, path);
        return NAV_FOUND;
    }

    protected bool Reachable(vector from, vector desired, float maxSegment, out vector sampled)
    {
        m_NavDeferred = false;
        if (!GetAIWorld() || !HCInfectedStore.ValidPosition(from) || !HCInfectedStore.ValidPosition(desired))
            return false;
        if (vector.DistanceSq(from, desired) > maxSegment * maxSegment)
            return false;
        PGFilter filter = HCNavFilters.HCFor(m_NavProfile);
        if (!GetAIWorld().SampleNavmeshPosition(desired, HCInfectedTuning.Get().Navigation.SampleRadius, filter, sampled))
            return false;
        if (Math.AbsFloat(sampled[1] - desired[1]) > HCInfectedTuning.Get().Navigation.VerticalTolerance)
            return false;
        int route = HCFindRoute(from, sampled, m_NavProfile, !m_NavDeferrable, m_NavPath);
        if (route == NAV_DEFERRED)
        {
            m_NavDeferred = true;
            return false;
        }
        if (route != NAV_FOUND || m_NavPath.Count() < 2 || m_NavPath.Count() > HCNavRouteCache.MAX_POINTS)
            return false;
        // A cached or shared route may start a few metres from this start: count that leg too.
        float length = vector.Distance(from, m_NavPath[0]);
        for (int i = 1; i < m_NavPath.Count(); i++)
            length += vector.Distance(m_NavPath[i - 1], m_NavPath[i]);
        return length <= maxSegment * 2 && vector.DistanceSq(m_NavPath[m_NavPath.Count() - 1], sampled) <= 4;
    }

    protected bool HCRefuse(string reason)
    {
        m_RefusalReason = reason;
        int seen = 0;
        if (s_RefusalSeen.Contains(reason)) { seen = s_RefusalSeen.Get(reason); }
        seen = seen + 1;
        s_RefusalSeen.Set(reason, seen);
        if (seen == 1 || seen % 512 == 0)
        {
            Print("[HC Infected] native pack route refused reason=" + reason + " count=" + seen.ToString() + " runtime=PENDING");
        }
        return false;
    }

    string HCRefusalReason() { return m_RefusalReason; }
    bool HCStartRan() { return m_HCStartRan; }

    bool Start(array<HCInfectedActor> actors, vector destination, bool search, float now, float expires)
    {
        m_RefusalReason = "";
        m_HCStartRan = true;
        if (!GetGame().IsServer()) return HCRefuse("not_server");
        if (!actors || actors.Count() < 1 || actors.Count() > HCHordeLimits.MAX_PACK) return HCRefuse("roster_bounds");
        if (!GetAIWorld()) return HCRefuse("no_ai_world");
        if (expires <= now) return HCRefuse("clue_expired");
        // Per-group quarantine: refuse only candidates whose current native group was recently given
        // up on. Checked before any path work is spent.
        foreach (HCInfectedActor held : actors)
        {
            if (!held.InfectedEntity || !held.InfectedEntity.GetAIAgent()) { continue; }
            if (HCPackQuarantine.HCHas(held.InfectedEntity.GetAIAgent().GetGroup(), now)) return HCRefuse("group_quarantined");
        }
        // The exact template and its type=InfectedPack exist in installed
        // DZ/aiconfigs/config.bin. Check again in the running config database.
        if (!GetGame().ConfigIsExisting("GroupBehaviourTemplates DZInfectedPackBeh"))
            return HCRefuse("pack_template_missing");
        ZombieBase leader = actors[0].InfectedEntity;
        if (!leader || !leader.IsAlive())
            return HCRefuse("leader_unavailable");
        InitFilter();
        vector start;
        if (!GetAIWorld().SampleNavmeshPosition(leader.GetPosition(), HCInfectedTuning.Get().Navigation.SampleRadius, m_Filter, start))
            return HCRefuse("leader_off_navmesh");
        vector end;
        float radius = 120;
        if (search)
            radius = HCInfectedTuning.Get().Navigation.SearchRing;
        if (!Reachable(start, destination, radius, end))
            return HCRefuse("route_unreachable");
        ref array<ref BehaviourGroupInfectedPackWaypointParams> route = new array<ref BehaviourGroupInfectedPackWaypointParams>;
        route.Insert(new BehaviourGroupInfectedPackWaypointParams(end, HCInfectedTuning.Get().Navigation.WaypointRadius));
        TVectorArray rooms;
        if (search && actors[0].SearchAnchorLimit > 1)
        {
            // Only explicitly surveyed rooms may extend the frozen clue route.
            // No fabricated offsets. Start spends one path; each queued room
            // segment is tested later by ExtendRoute, one FindPath per module
            // tick. Failed anchors still consume the finite catalog budget.
            HCInfectedRoomCatalog.BuildOrder(destination, Math.Min(2, actors[0].SearchAnchorLimit - 1), rooms);
        }
        // Validate every agent before changing any native membership.
        foreach (HCInfectedActor candidate : actors)
        {
            if (!candidate.InfectedEntity || !candidate.InfectedEntity.IsAlive() || !candidate.InfectedEntity.GetAIAgent())
                return HCRefuse("member_unavailable");
            int mind = candidate.InfectedEntity.GetMindStateSynced();
            if (mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT || candidate.Profile == "native_injured")
                return HCRefuse("member_engaged");
        }
        m_LastPosition = leader.GetPosition();
        m_Search = search;
        m_Expires = expires;
        m_LastProgress = now;
        RouteEnd = end;
        Group = GetAIWorld().CreateGroup("DZInfectedPackBeh");
        if (!Group)
            return HCRefuse("group_create_failed");
        BehaviourGroupInfectedPack behaviour = BehaviourGroupInfectedPack.Cast(Group.GetBehaviour());
        if (!behaviour)
        {
            Group = null; // Empty groups are deleted next frame by AIWorld.
            return HCRefuse("group_behaviour_missing");
        }
        m_RoutePlan = route;
        m_PendingRooms = rooms;
        m_PendingFrom = end;
        RoutePlanned = route.Count();
        RouteCompleted = 0;
        RoutePurpose = 1;
        RouteResult = 1;
        RouteEnd = route[route.Count() - 1].m_CenterPosition;
        if (!ActivateWaypoint(now))
        {
            Group = null; // Still empty; no agents are destroyed.
            RouteResult = 6;
            return HCRefuse("waypoint_failed");
        }
        foreach (HCInfectedActor actor : actors)
        {
            AIAgent agent = actor.InfectedEntity.GetAIAgent();
            AIGroup previous = agent.GetGroup();
            if (previous)
                previous.RemoveAgent(agent);
            Group.AddAgent(agent);
            m_Members.Insert(actor.InfectedEntity);
            if (agent.GetGroup() != Group)
            {
                // A partial transfer may still own agents. Returning true while
                // release is pending keeps that ownership with the caller.
                return !Release();
            }
        }
        m_Search = search;
        m_Expires = expires;
        m_LastProgress = now;
        m_LastPosition = leader.GetPosition();
        RouteEnd = route[route.Count() - 1].m_CenterPosition;
        return true;
    }

    // Tests at most one queued surveyed room per call (one FindPath), in the
    // catalog order. A failed segment is dropped and the next room is tried
    // from the last reachable point, exactly as the former inline loop did.
    // Returns true only when a path test was spent.
    bool ExtendRoute()
    {
        if (m_Releasing || !Group || !m_RoutePlan || !m_PendingRooms)
            return false;
        while (m_PendingRooms.Count() > 0)
        {
            vector desiredRoom = m_PendingRooms[0];
            if (vector.DistanceSq(m_PendingFrom, desiredRoom) < 1)
            {
                m_PendingRooms.RemoveOrdered(0);
                continue;
            }
            // Room segments are short interior hops: INF_INTERIOR, and deferrable. A refused token
            // keeps the room queued for a later tick (the pending-room hold in Tick is bounded).
            vector sampledRoom;
            m_NavProfile = HCNavFilters.PROFILE_INTERIOR;
            m_NavDeferrable = true;
            bool roomReachable = Reachable(m_PendingFrom, desiredRoom, 8, sampledRoom);
            m_NavProfile = HCNavFilters.PROFILE_OUTDOOR;
            m_NavDeferrable = false;
            if (m_NavDeferred)
                return false;
            m_PendingRooms.RemoveOrdered(0);
            if (roomReachable)
            {
                m_RoutePlan.Insert(new BehaviourGroupInfectedPackWaypointParams(sampledRoom, 1));
                RoutePlanned = m_RoutePlan.Count();
                RoutePurpose = 2;
                RouteEnd = sampledRoom;
                m_PendingFrom = sampledRoom;
            }
            return true;
        }
        return false;
    }

    bool OwnsMember(ZombieBase infected)
    {
        if (!Group || !infected || m_Releasing) return false;
        AIAgent agent = infected.GetAIAgent();
        return agent && agent.GetGroup() == Group;
    }

    int Retarget(HCInfectedClue clue, float now)
    {
        if (!GetGame().IsServer() || m_Search || m_Releasing || !Group || !clue)
            return 0;
        if (!clue.IsLive(now) || !HCInfectedStore.ValidPosition(clue.Origin))
            return 0;
        if (m_Members.Count() < 1 || m_Members.Count() > HCHordeLimits.MAX_PACK || now >= m_Expires)
            return 0;
        ZombieBase leader;
        foreach (ZombieBase member : m_Members)
        {
            if (!member) return 0;
            if (!member.IsAlive()) continue;
            AIAgent currentAgent = member.GetAIAgent();
            if (!currentAgent || currentAgent.GetGroup() != Group) return 0;
            int mind = member.GetMindStateSynced();
            if (mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT)
                return 0;
            if (member.GetHealth("LeftLeg", "Health") <= 0 || member.GetHealth("RightLeg", "Health") <= 0)
                return 0;
            if (!leader) leader = member;
        }
        // Two attempts per cooldown window, with a new observed clue still
        // required. Re-arming never extends the original pack/root lifetime.
        if (m_RetargetAttempts >= 2 && now >= m_NextRetarget)
        {
            m_RetargetAttempts = 0;
        }
        if (!HCInfectedPolicy.RetargetAllowed(now, m_NextRetarget, clue.Observed, m_LastRetargetObserved, clue.Expires, m_RetargetAttempts, leader != null, false))
            return 0;
        // This tick's FindPath token is already spent: report a pre-path rejection (0) so no attempt or
        // cooldown is consumed and the module offers the clue again on a later tick.
        if (!HCNavScheduler.HCAvailable())
            return 0;
        // Failed geometry still spends an attempt/cooldown. A repeated blocked
        // clue cannot repeatedly consume native pathfinding work.
        int priorAttempts = m_RetargetAttempts;
        float priorNext = m_NextRetarget;
        float priorObserved = m_LastRetargetObserved;
        m_RetargetAttempts++;
        m_NextRetarget = now + 10;
        if (m_RetargetAttempts >= 2)
        {
            m_NextRetarget = now + HCInfectedPolicy.HordeCooldownSeconds();
        }
        m_LastRetargetObserved = clue.Observed;
        vector end;
        m_NavDeferrable = true;
        bool clueReachable = Reachable(leader.GetPosition(), clue.Origin, 120, end);
        m_NavDeferrable = false;
        if (m_NavDeferred)
        {
            // The shared work budget refused the path after the preflight peek: nothing was spent.
            m_RetargetAttempts = priorAttempts;
            m_NextRetarget = priorNext;
            m_LastRetargetObserved = priorObserved;
            return 0;
        }
        if (!clueReachable)
            return 1;
        BehaviourGroupInfectedPack behaviour = BehaviourGroupInfectedPack.Cast(Group.GetBehaviour());
        if (!behaviour) return 1;
        ref array<ref BehaviourGroupInfectedPackWaypointParams> route = new array<ref BehaviourGroupInfectedPackWaypointParams>;
        route.Insert(new BehaviourGroupInfectedPackWaypointParams(end, HCInfectedTuning.Get().Navigation.WaypointRadius));
        // ActivateWaypoint uses the inspected SetWaypoints API on this group.
        m_RoutePlan = route;
        RoutePlanned = 1;
        RouteCompleted = 0;
        RoutePurpose = 1;
        RouteResult = 1;
        if (!ActivateWaypoint(now))
        {
            RouteResult = 6;
            return 1;
        }
        // Absolute inherited expiry: never turn fresh processing time into a
        // longer pursuit. Native combat remains authoritative.
        m_Expires = Math.Min(m_Expires, clue.Expires);
        m_LastProgress = now;
        m_LastPosition = leader.GetPosition();
        RouteEnd = end;
        return 2;
    }

    protected HCNavMemberTrack HCTrackFor(ZombieBase member, vector position, float now)
    {
        HCNavMemberTrack track;
        if (m_Tracks.Find(member, track)) { return track; }
        track = new HCNavMemberTrack;
        track.Pos = position;
        track.At = now;
        m_Tracks.Insert(member, track);
        return track;
    }

    // One recovery step for the member that just took a strike. Never moves the entity: it queues a door
    // for the native door API, re-plans the pack route, or stops counting the member.
    protected void HCRecover(ZombieBase member, HCNavMemberTrack track, float now)
    {
        vector position = member.GetPosition();
        if (track.Strikes == 1)
        {
            HCNavSpots.HCNote(position, now);
            HCModuleReadiness.HCUse("Infected", "stuck_strike");
            if (HCNavSpots.HCIsTrap(position, now) && track.Strikes < 3)
            {
                // A known trap: the ladder already failed here, so the member is dropped at once.
                track.Strikes = 3;
            }
        }
        if (track.Strikes == 1)
        {
            if (!m_PackDoors) { m_PackDoors = new HCNavDoorQueue; }
            m_PackDoors.HCDiscover(position, now);
            return;
        }
        if (track.Strikes == 2)
        {
            if (m_Repaths >= MAX_REPATHS || IsV2Drifting())
            {
                track.Strikes = 3;
            }
            else
            {
                // One deferrable path from the stuck member to the route end. A refused token reverts
                // the strike so the same step is tried again on a later tick.
                vector repathEnd;
                m_NavDeferrable = true;
                bool repathable = Reachable(position, RouteEnd, 200, repathEnd);
                m_NavDeferrable = false;
                if (m_NavDeferred)
                {
                    track.Strikes = 1;
                    track.At = now - STUCK_WINDOW;
                    return;
                }
                if (repathable && HCApplyRepath(now))
                {
                    m_Repaths++;
                    HCModuleReadiness.HCUse("Infected", "repath_ok");
                    return;
                }
                track.Strikes = 3;
            }
        }
        if (track.Strikes >= 3)
        {
            track.Dropped = true;
            m_Drops++;
            HCModuleReadiness.HCUse("Infected", "straggler_drop");
            HCNavSpots.HCNote(position, now);
            Print("[HC Infected] nav straggler dropped from pack count drops=" + m_Drops.ToString() + " runtime=PENDING");
        }
    }

    // Replace the plan with up to two intermediate points of the freshly found route plus the old end.
    protected bool HCApplyRepath(float now)
    {
        int count = m_NavPath.Count();
        if (count < 2 || !Group) return false;
        ref array<ref BehaviourGroupInfectedPackWaypointParams> plan = new array<ref BehaviourGroupInfectedPackWaypointParams>;
        float radius = HCInfectedTuning.Get().Navigation.WaypointRadius;
        vector last = m_NavPath[0];
        for (int third = 1; third <= 2; third++)
        {
            int pick = (count * third) / 3;
            if (pick < 1 || pick >= count - 1) continue;
            vector point = m_NavPath[pick];
            if (vector.DistanceSq(point, last) < 36 || vector.DistanceSq(point, RouteEnd) < 36) continue;
            plan.Insert(new BehaviourGroupInfectedPackWaypointParams(point, radius));
            last = point;
        }
        plan.Insert(new BehaviourGroupInfectedPackWaypointParams(RouteEnd, radius));
        m_RoutePlan = plan;
        RoutePlanned = plan.Count();
        RouteCompleted = 0;
        RouteResult = 1;
        return ActivateWaypoint(now);
    }

    bool Tick(float now)
    {
        if (m_Releasing)
            return !Release();
        if (!Group || !m_RoutePlan || RouteCompleted >= RoutePlanned)
        {
            RouteResult = 6;
            return !Release();
        }
        int ownedMembers = 0;
        int arrivedMembers = 0;
        bool ambiguous = false;
        bool interrupted = false;
        bool anyProgress = false;
        bool laddering = false;
        float worstDistanceSq = 0;
        vector destination = m_RoutePlan[RouteCompleted].m_CenterPosition;
        float radius = m_RoutePlan[RouteCompleted].m_Radius;
        float nearSq = (radius + STUCK_NEAR) * (radius + STUCK_NEAR);
        ZombieBase leader;
        ZombieBase stuckMember;
        HCNavMemberTrack stuckTrack;
        foreach (ZombieBase member : m_Members)
        {
            if (!member)
            {
                ambiguous = true;
                continue;
            }
            if (!member.IsAlive()) continue;
            AIAgent currentAgent = member.GetAIAgent();
            bool sameGroup = currentAgent && currentAgent.GetGroup() == Group;
            if (!HCInfectedPolicy.CountsOwnedMember(member.IsAlive(), currentAgent != null, sameGroup))
            {
                ambiguous = true;
                continue;
            }
            vector position = member.GetPosition();
            if (!HCInfectedStore.ValidPosition(position))
            {
                ambiguous = true;
                continue;
            }
            HCNavMemberTrack track = HCTrackFor(member, position, now);
            // A dropped straggler no longer counts toward arrival or the pack's worst distance, so
            // one wedged member cannot stall or deadlock the rest of the pack.
            if (track.Dropped) continue;
            if (!leader) leader = member;
            ownedMembers++;
            float distanceSq = vector.DistanceSq(position, destination);
            worstDistanceSq = Math.Max(worstDistanceSq, distanceSq);
            if (distanceSq <= radius * radius) arrivedMembers++;
            if (track.BestSq < 0)
            {
                track.BestSq = distanceSq;
            }
            else if (distanceSq <= track.BestSq - 1)
            {
                track.BestSq = distanceSq;
                anyProgress = true;
            }
            int mind = member.GetMindStateSynced();
            bool engaged = mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT;
            if (engaged)
                interrupted = true;
            if (member.GetHealth("LeftLeg", "Health") <= 0 || member.GetHealth("RightLeg", "Health") <= 0)
                interrupted = true;
            if (engaged || member.IsCrawling() || distanceSq <= nearSq)
            {
                // Fighting, crawling or about to arrive is never "stuck".
                track.Strikes = 0;
                track.Pos = position;
                track.At = now;
                continue;
            }
            if (now - track.At >= STUCK_WINDOW)
            {
                if (vector.DistanceSq(position, track.Pos) >= STUCK_MIN_MOVE * STUCK_MIN_MOVE)
                {
                    track.Strikes = 0;
                    track.Pos = position;
                    track.At = now;
                }
                else if (!stuckMember)
                {
                    // One strike per Tick across the pack keeps recovery bounded.
                    track.Strikes++;
                    track.Pos = position;
                    track.At = now;
                    stuckMember = member;
                    stuckTrack = track;
                }
            }
            if (track.Strikes > 0) laddering = true;
        }
        if (leader) m_LastPosition = leader.GetPosition();
        if (stuckMember) HCRecover(stuckMember, stuckTrack, now);
        // At most one queued door is served per Tick.
        if (m_PackDoors && m_PackDoors.HCCount() > 0 && leader) m_PackDoors.HCProcess(leader, now);
        if (ownedMembers == 0 && m_Drops > 0 && !ambiguous)
        {
            // Every tracked member was dropped: a clean give-up, quarantined so the same wedged group
            // is not immediately re-routed.
            RouteResult = 3;
            return !Release();
        }
        if (m_BestRouteDistanceSq < 0)
            m_BestRouteDistanceSq = worstDistanceSq;
        if (anyProgress || HCInfectedPolicy.RouteMadeProgress(worstDistanceSq, m_BestRouteDistanceSq))
        {
            m_BestRouteDistanceSq = Math.Min(worstDistanceSq, m_BestRouteDistanceSq);
            m_LastProgress = now;
        }
        // While the ladder is still working on a member the pack is not declared stalled (the ladder
        // ends in a drop within three windows, which is the backstop).
        float stalled = now - m_LastProgress;
        if (laddering && stalled > 14)
            stalled = 14;
        RouteResult = HCInfectedPolicy.RouteObservationResult(now, m_Expires, stalled, ownedMembers, arrivedMembers, ambiguous, interrupted);
        if (RouteResult == 2 && RouteCompleted + 1 >= RoutePlanned && m_PendingRooms && m_PendingRooms.Count() > 0)
        {
            // Hold the reached point until a queued room gets its path test on a later tick;
            // expiry/interruption still end the route, and the hold itself is bounded so a deferred
            // room can never keep the pack parked forever.
            if (m_HoldSince < 0) m_HoldSince = now;
            if (now - m_HoldSince < PENDING_HOLD_SECONDS)
            {
                RouteResult = 1;
                return true;
            }
            m_PendingRooms.Clear();
        }
        if (RouteResult == 2)
        {
            RouteCompleted++;
            if (RouteCompleted < RoutePlanned)
            {
                RouteResult = 1;
                if (ActivateWaypoint(now)) return true;
                RouteResult = 6;
            }
        }
        if (RouteResult != 1)
            return !Release();
        return true;
    }

    // Authored ownership hook; the optional V2 extension overrides it.
    bool IsV2Drifting()
    {
        return false;
    }

    bool IsReleasing()
    {
        return m_Releasing;
    }

    bool IsReleaseQuarantined()
    {
        return m_ReleaseQuarantined;
    }

    bool Release()
    {
        if (RouteResult == 1) RouteResult = 5;
        // Crash fix (both build-152 boots, 2026-11-21): moving agents out of the
        // pack group (RemoveAgent + AIWorld.CreateDefaultGroup + AddAgent) crashed
        // the server natively within a second each time; vanilla never moves
        // infected between groups. Release now only parks the native pack: hold at
        // a live member's current position and drop our ownership. Members stay in
        // their native DZInfectedPackBeh group, so native perception, chase and
        // combat are unchanged; AIWorld deletes the group once it is empty. Never
        // DeleteGroup (destroys agents) and never re-add agents to another group.
        if (!m_Releasing && Group)
        {
            vector hold = m_LastPosition;
            for (int i = 0; i < m_Members.Count(); i++)
            {
                if (m_Members[i] && !m_Members[i].IsPendingDeletion())
                {
                    hold = m_Members[i].GetPosition();
                    break;
                }
            }
            BehaviourGroupInfectedPack behaviour = BehaviourGroupInfectedPack.Cast(Group.GetBehaviour());
            if (behaviour)
            {
                ref array<ref BehaviourGroupInfectedPackWaypointParams> parked = new array<ref BehaviourGroupInfectedPackWaypointParams>;
                parked.Insert(new BehaviourGroupInfectedPackWaypointParams(hold, 1));
                behaviour.SetWaypoints(parked, 0, true, false);
            }
            Print("[HC Infected] pack released in place members=" + m_Members.Count().ToString() + " (no native group transfer)");
        }
        // A route that stalled (or lost every member to the straggler drop) quarantines only this
        // group: new routes for it are refused for the cooldown, other packs are never held back.
        if (!m_Releasing && Group && RouteResult == 3)
        {
            HCPackQuarantine.HCAdd(Group, GetGame().GetTickTime());
            m_ReleaseQuarantined = true;
        }
        m_Releasing = true;
        m_Members.Clear();
        m_ReleaseFallbacks.Clear();
        m_Tracks.Clear();
        m_PackDoors = null;
        Group = null;
        return true;
    }
}

class HCInfectedObservation
{
    // Module budget gate: false while VisualProvenanceEstablished has no
    // observed evidence source, so no sampling slot is spent on a known no-op.
    static bool VisualSamplingAvailable()
    {
        return false;
    }

    static bool VisualProvenanceEstablished(DayZInfectedInputController controller)
    {
        // 1.30.164289 3_Game/Entities/DayZInfectedInputController.c:9-10
        // exposes mind state and retained target, not a fresh visual receipt.
        // ZombieBase.c:556 OnSoundVoiceEvent reports an animation sound, while
        // :981 EEHitBy reports damage/source, not sight. Neither establishes a
        // fresh visual receipt; the base DayZCreatureAIInputController likewise
        // exposes no sight event. Keep disabled; do not relabel damage/hearing
        // as vision or sample hidden coordinates from a retained target.
        return false;
    }

    static bool SampleVisual(HCInfectedActor actor, float now)
    {
        ZombieBase infected = actor.InfectedEntity;
        if (!infected || !infected.IsAlive())
            return false;
        DayZInfectedInputController controller = infected.GetInputController();
        if (!controller)
            return false;
        int mind = controller.GetMindState();
        if (mind != DayZInfectedConstants.MINDSTATE_CHASE && mind != DayZInfectedConstants.MINDSTATE_FIGHT)
            return false;
        bool visualObserved = HCInfectedObservation.VisualProvenanceEstablished(controller);
        if (!visualObserved)
            return false;
        // GetTargetEntity may retain an occluded target. It is only a candidate
        // for this bounded sensor check, never directly a pursuit destination.
        EntityAI candidate = controller.GetTargetEntity();
        if (!candidate || !candidate.IsAlive())
            return false;
        vector origin = infected.GetPosition() + "0 1.4 0";
        vector point = candidate.ModelToWorld(candidate.GetDefaultHitPosition());
        vector direction = point - origin;
        float distanceSq = vector.DistanceSq(point, origin);
        if (!(distanceSq <= 400 && distanceSq >= 0.01))
            return false;
        direction.Normalize();
        float facing = vector.Dot(infected.GetDirection(), direction);
        if (facing < 0.5)
            return false;
        vector contact, normal;
        int component;
        ref set<Object> hits = new set<Object>;
        bool hit = DayZPhysics.RaycastRV(origin, point, contact, normal, component, hits, null, infected, true, false, ObjIntersectView);
        bool viewTarget = hit && hits.Count() > 0 && hits[0] == candidate;
        if (!viewTarget)
            return false;
        // A second fire-geometry test avoids a visual proxy allowing wall clues.
        hits.Clear();
        hit = DayZPhysics.RaycastRV(origin, point, contact, normal, component, hits, null, infected, true, false, ObjIntersectFire);
        bool fireTarget = hit && hits.Count() > 0 && hits[0] == candidate;
        if (!HCInfectedPolicy.DirectlyObserved(visualObserved, distanceSq, facing, viewTarget, fireTarget))
            return false;
        if (!HCInfectedStore.ValidPosition(point))
            return false;
        actor.Visual = new HCInfectedClue;
        actor.Visual.Provenance = 2;
        actor.Visual.Origin = point;
        actor.Visual.Observed = now;
        actor.Visual.Expires = now + actor.ClueLifetime;
        actor.SearchAttempts = 0;
        return true;
    }
}
