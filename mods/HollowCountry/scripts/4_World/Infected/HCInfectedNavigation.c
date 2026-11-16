// Installed 1.30 native surfaces: 3_Game/AI/{AIWorld,AIGroup,AIGroupBehaviour}.
// No manual steering, script command or generated noise target is used.
class HCNativeInfectedPack
{
    protected static ref array<ref HCNativeInfectedPack> s_PendingRelease = new array<ref HCNativeInfectedPack>;
    AIGroup Group;
    protected ref array<ZombieBase> m_Members = new array<ZombieBase>;
    protected ref PGFilter m_Filter;
    protected float m_Expires;
    protected float m_LastProgress;
    protected vector m_LastPosition;
    protected bool m_Search;
    protected bool m_Releasing;
    protected int m_ReleaseAttempts;
    protected int m_NextReleaseUtc;
    vector RouteEnd;

    protected AIWorld World()
    {
        if (!GetGame() || !GetGame().GetWorld()) return null;
        return GetGame().GetWorld().GetAIWorld();
    }

    static void RetryPendingReleases()
    {
        // New packs are blocked while any release is pending. At most the two
        // horde packs, two investigators and one partial transfer can be owned.
        for (int i = s_PendingRelease.Count() - 1; i >= 0; i--)
            s_PendingRelease[i].Release();
    }

    protected void InitFilter()
    {
        m_Filter = new PGFilter;
        // Conservative walk/interior filter. Native collision/door state still
        // decide actual passage. No ladder, swimming, vault or crawl shortcuts.
        m_Filter.SetFlags(PGPolyFlags.WALK | PGPolyFlags.DOOR | PGPolyFlags.INSIDE, PGPolyFlags.DISABLED | PGPolyFlags.UNREACHABLE | PGPolyFlags.SWIM | PGPolyFlags.SWIM_SEA | PGPolyFlags.LADDER | PGPolyFlags.JUMP | PGPolyFlags.CLIMB | PGPolyFlags.CRAWL | PGPolyFlags.CROUCH, PGPolyFlags.NONE);
        m_Filter.SetCost(PGAreaType.DOOR_CLOSED, 1000);
    }

    protected bool Reachable(vector from, vector desired, float maxSegment, out vector sampled)
    {
        if (!World() || !HCInfectedStore.ValidPosition(from) || !HCInfectedStore.ValidPosition(desired))
            return false;
        if (vector.DistanceSq(from, desired) > maxSegment * maxSegment)
            return false;
        if (!World().SampleNavmeshPosition(desired, 1.5, m_Filter, sampled))
            return false;
        if (Math.AbsFloat(sampled[1] - desired[1]) > 1.5)
            return false;
        TVectorArray path = new TVectorArray;
        if (!World().FindPath(from, sampled, m_Filter, path) || !path || path.Count() < 2 || path.Count() > 32)
            return false;
        float length = 0;
        for (int i = 1; i < path.Count(); i++)
            length += vector.Distance(path[i - 1], path[i]);
        return length <= maxSegment * 2 && vector.DistanceSq(path[path.Count() - 1], sampled) <= 4;
    }

    bool Start(array<HCInfectedActor> actors, vector destination, bool search, float now, float expires)
    {
        if (s_PendingRelease.Count() > 0) return false;
        if (!GetGame().IsServer() || !actors || actors.Count() < 1 || actors.Count() > 6 || !World() || expires <= now)
            return false;
        // The exact template and its type=InfectedPack exist in installed
        // DZ/aiconfigs/config.bin. Check again in the running config database.
        if (!GetGame().ConfigIsExisting("GroupBehaviourTemplates DZInfectedPackBeh"))
            return false;
        ZombieBase leader = actors[0].Entity;
        if (!leader || !leader.IsAlive())
            return false;
        InitFilter();
        vector start;
        if (!World().SampleNavmeshPosition(leader.GetPosition(), 1.5, m_Filter, start))
            return false;
        vector end;
        float radius = 120;
        if (search)
            radius = 24;
        if (!Reachable(start, destination, radius, end))
            return false;
        ref array<ref BehaviourGroupInfectedPackWaypointParams> route = new array<ref BehaviourGroupInfectedPackWaypointParams>;
        route.Insert(new BehaviourGroupInfectedPackWaypointParams(end, 1.5));
        if (search && HCInfectedPolicy.SearchAnchorBudget(leader.IsZombieMilitary(), false) > 1)
        {
            // At most two reachable nearby anchors on the observed floor. These
            // are navmesh anchors, not an invented semantic room inventory.
            vector next;
            if (Reachable(end, end + "4 0 0", 8, next))
                route.Insert(new BehaviourGroupInfectedPackWaypointParams(next, 1));
            vector last;
            if (Reachable(end, end + "0 0 4", 8, last))
                route.Insert(new BehaviourGroupInfectedPackWaypointParams(last, 1));
        }
        else if (!search)
        {
            route.Insert(new BehaviourGroupInfectedPackWaypointParams(start, 3));
        }
        // Validate every agent before changing any native membership.
        foreach (HCInfectedActor candidate : actors)
        {
            if (!candidate.Entity || !candidate.Entity.IsAlive() || !candidate.Entity.GetAIAgent())
                return false;
            int mind = candidate.Entity.GetMindStateSynced();
            if (mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT || candidate.Profile == "native_injured")
                return false;
        }
        m_LastPosition = leader.GetPosition();
        m_Search = search;
        m_Expires = expires;
        m_LastProgress = now;
        RouteEnd = end;
        Group = World().CreateGroup("DZInfectedPackBeh");
        if (!Group)
            return false;
        BehaviourGroupInfectedPack behaviour = BehaviourGroupInfectedPack.Cast(Group.GetBehaviour());
        if (!behaviour)
        {
            Group = null; // Empty groups are deleted next frame by AIWorld.
            return false;
        }
        behaviour.SetWaypoints(route, 0, true, false);
        foreach (HCInfectedActor actor : actors)
        {
            AIAgent agent = actor.Entity.GetAIAgent();
            AIGroup previous = agent.GetGroup();
            if (previous)
                previous.RemoveAgent(agent);
            Group.AddAgent(agent);
            m_Members.Insert(actor.Entity);
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
        RouteEnd = end;
        return true;
    }

    bool Tick(float now)
    {
        if (m_Releasing)
            return !Release();
        ZombieBase leader;
        bool interrupted = false;
        foreach (ZombieBase member : m_Members)
        {
            if (!member || !member.IsAlive())
                continue;
            AIAgent currentAgent = member.GetAIAgent();
            bool sameGroup = currentAgent && currentAgent.GetGroup() == Group;
            if (!HCInfectedPolicy.CountsOwnedMember(member.IsAlive(), currentAgent != null, sameGroup))
                continue;
            if (!leader)
                leader = member;
            // Keep native combat and injury control: investigations end as soon
            // as native AI reacquires a threat; horde packs use native combat.
            int mind = member.GetMindStateSynced();
            if (m_Search && (mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT))
                interrupted = true;
            if (m_Search && (member.GetHealth("LeftLeg", "Health") <= 0 || member.GetHealth("RightLeg", "Health") <= 0))
                interrupted = true;
        }
        if (leader && vector.DistanceSq(leader.GetPosition(), m_LastPosition) >= 1)
        {
            m_LastPosition = leader.GetPosition();
            m_LastProgress = now;
        }
        if (!Group || !HCInfectedPolicy.RouteAlive(now, m_Expires, now - m_LastProgress, leader != null, interrupted))
        {
            return !Release();
        }
        return true;
    }

    bool IsReleasing()
    {
        return m_Releasing;
    }

    bool Release()
    {
        // A previous empty CE group may already have been deleted by AIWorld.
        // Rehome surviving agents in a native default group; never DeleteGroup,
        // which destroys its agents. Ownership/CE cleanup still need native tests.
        // Stop patrol intent before rehoming, including allocation-failure cases.
        // Native combat may still run; this never cancels injury/death commands.
        if (!m_Releasing && Group)
        {
            BehaviourGroupInfectedPack behaviour = BehaviourGroupInfectedPack.Cast(Group.GetBehaviour());
            if (behaviour)
            {
                ref array<ref BehaviourGroupInfectedPackWaypointParams> hold = new array<ref BehaviourGroupInfectedPackWaypointParams>;
                hold.Insert(new BehaviourGroupInfectedPackWaypointParams(m_LastPosition, 1));
                behaviour.SetWaypoints(hold, 0, true, false);
            }
        }
        m_Releasing = true;
        // Prune only members whose actual native ownership has ended.
        for (int i = m_Members.Count() - 1; i >= 0; i--)
        {
            ZombieBase member = m_Members[i];
            if (!member || !member.GetAIAgent())
            {
                m_Members.Remove(i);
                continue;
            }
            if (!Group || member.GetAIAgent().GetGroup() != Group)
                m_Members.Remove(i);
        }
        if (m_Members.Count() == 0)
        {
            Group = null;
            s_PendingRelease.RemoveItem(this);
            return true;
        }
        // Retain ownership even when callers discard an expired/failed pack or
        // the module is quarantined. Exhausted retries remain visible/owned;
        // no replacement pack is admitted until native cleanup succeeds.
        if (s_PendingRelease.Find(this) < 0)
        {
            s_PendingRelease.Insert(this);
            Print("[HC Infected] native release pending; pack retained and new routes blocked");
        }
        int nowUtc = HCInfectedClock.UtcSeconds();
        if (!HCInfectedPolicy.MayRetryRelease(m_ReleaseAttempts, nowUtc, m_NextReleaseUtc))
            return false;
        m_ReleaseAttempts++;
        m_NextReleaseUtc = nowUtc + 5;
        AIWorld world = World();
        if (!world) return false;
        AIGroup fallback = world.CreateDefaultGroup();
        if (!fallback)
            return false; // Retain members AND group; caller retains this pack.
        for (int j = m_Members.Count() - 1; j >= 0; j--)
        {
            AIAgent agent = m_Members[j].GetAIAgent();
            if (agent && agent.GetGroup() == Group)
            {
                Group.RemoveAgent(agent);
                fallback.AddAgent(agent);
                if (agent.GetGroup() == fallback)
                    m_Members.Remove(j);
            }
        }
        if (m_Members.Count() == 0)
        {
            Group = null;
            s_PendingRelease.RemoveItem(this);
            return true;
        }
        return false;
    }
}

class HCInfectedObservation
{
    static bool SampleVisual(HCInfectedActor actor, float now)
    {
        ZombieBase infected = actor.Entity;
        if (!infected || !infected.IsAlive())
            return false;
        DayZInfectedInputController controller = infected.GetInputController();
        if (!controller)
            return false;
        int mind = controller.GetMindState();
        if (mind != DayZInfectedConstants.MINDSTATE_CHASE && mind != DayZInfectedConstants.MINDSTATE_FIGHT)
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
        if (!HCInfectedPolicy.DirectlyObserved(true, distanceSq, facing, viewTarget, fireTarget))
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
