// Installed 1.30 native surfaces: 3_Game/AI/{AIWorld,AIGroup,AIGroupBehaviour}.
// No manual steering, script command or generated noise target is used.
class HCNativeInfectedPack
{
    protected static ref array<ref HCNativeInfectedPack> s_PendingRelease = new array<ref HCNativeInfectedPack>;
    // Last logged release summary, so the status line is emitted on change only.
    protected static int s_ReportedPending;
    protected static int s_ReportedQuarantined;
    AIGroup Group;
    protected ref array<ZombieBase> m_Members = new array<ZombieBase>;
    protected ref PGFilter m_Filter;
    protected float m_Expires;
    protected float m_LastProgress;
    protected float m_NextRetarget;
    protected float m_LastRetargetObserved = -1;
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
    vector RouteEnd;
    int RoutePurpose;
    int RouteResult;
    int RoutePlanned;
    int RouteCompleted;

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
        return true;
    }

    protected AIWorld GetAIWorld()
    {
        if (!GetGame() || !GetGame().GetWorld()) return null;
        return GetGame().GetWorld().GetAIWorld();
    }

    static int QuarantinedReleaseCount()
    {
        int quarantined = 0;
        for (int i = 0; i < s_PendingRelease.Count(); i++)
        {
            if (s_PendingRelease[i].IsReleaseQuarantined())
                quarantined++;
        }
        return quarantined;
    }

    // Bounded status: a pending or quarantined release blocks every new native
    // route (Start refuses while the ledger is non-empty), so it must be visible.
    static string ReleaseStatus()
    {
        string blocked = "no";
        if (s_PendingRelease.Count() > 0)
            blocked = "yes";
        int pending = s_PendingRelease.Count();
        int quarantined = QuarantinedReleaseCount();
        return "pending=" + pending.ToString() + " quarantined=" + quarantined.ToString() + " new_routes_blocked=" + blocked;
    }

    static void RetryPendingReleases()
    {
        // New packs are blocked while any release is pending. At most the two
        // horde packs, two investigators and one partial transfer can be owned.
        for (int i = s_PendingRelease.Count() - 1; i >= 0; i--)
            s_PendingRelease[i].Release();
        int pending = s_PendingRelease.Count();
        int quarantined = QuarantinedReleaseCount();
        if (pending != s_ReportedPending || quarantined != s_ReportedQuarantined)
        {
            s_ReportedPending = pending;
            s_ReportedQuarantined = quarantined;
            Print("[HC Infected] native release status: " + ReleaseStatus());
        }
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
        if (!GetAIWorld() || !HCInfectedStore.ValidPosition(from) || !HCInfectedStore.ValidPosition(desired))
            return false;
        if (vector.DistanceSq(from, desired) > maxSegment * maxSegment)
            return false;
        if (!GetAIWorld().SampleNavmeshPosition(desired, 1.5, m_Filter, sampled))
            return false;
        if (Math.AbsFloat(sampled[1] - desired[1]) > 1.5)
            return false;
        TVectorArray path = new TVectorArray;
        if (!GetAIWorld().FindPath(from, sampled, m_Filter, path) || !path || path.Count() < 2 || path.Count() > 32)
            return false;
        float length = 0;
        for (int i = 1; i < path.Count(); i++)
            length += vector.Distance(path[i - 1], path[i]);
        return length <= maxSegment * 2 && vector.DistanceSq(path[path.Count() - 1], sampled) <= 4;
    }

    bool Start(array<HCInfectedActor> actors, vector destination, bool search, float now, float expires)
    {
        if (s_PendingRelease.Count() > 0) return false;
        if (!GetGame().IsServer() || !actors || actors.Count() < 1 || actors.Count() > 6 || !GetAIWorld() || expires <= now)
            return false;
        // The exact template and its type=InfectedPack exist in installed
        // DZ/aiconfigs/config.bin. Check again in the running config database.
        if (!GetGame().ConfigIsExisting("GroupBehaviourTemplates DZInfectedPackBeh"))
            return false;
        ZombieBase leader = actors[0].InfectedEntity;
        if (!leader || !leader.IsAlive())
            return false;
        InitFilter();
        vector start;
        if (!GetAIWorld().SampleNavmeshPosition(leader.GetPosition(), 1.5, m_Filter, start))
            return false;
        vector end;
        float radius = 120;
        if (search)
            radius = 24;
        if (!Reachable(start, destination, radius, end))
            return false;
        ref array<ref BehaviourGroupInfectedPackWaypointParams> route = new array<ref BehaviourGroupInfectedPackWaypointParams>;
        route.Insert(new BehaviourGroupInfectedPackWaypointParams(end, 1.5));
        if (search && actors[0].SearchAnchorLimit > 1)
        {
            // Only explicitly surveyed rooms may extend the frozen clue route.
            // No fabricated offsets. Every segment is tested before membership
            // changes; failed anchors consume the finite catalog budget.
            TVectorArray rooms;
            HCInfectedRoomCatalog.BuildOrder(destination, Math.Min(2, actors[0].SearchAnchorLimit - 1), rooms);
            vector previousPoint = end;
            foreach (vector desiredRoom : rooms)
            {
                vector sampledRoom;
                if (vector.DistanceSq(previousPoint, desiredRoom) < 1)
                    continue;
                if (Reachable(previousPoint, desiredRoom, 8, sampledRoom))
                {
                    route.Insert(new BehaviourGroupInfectedPackWaypointParams(sampledRoom, 1));
                    previousPoint = sampledRoom;
                }
            }
        }
        // Validate every agent before changing any native membership.
        foreach (HCInfectedActor candidate : actors)
        {
            if (!candidate.InfectedEntity || !candidate.InfectedEntity.IsAlive() || !candidate.InfectedEntity.GetAIAgent())
                return false;
            int mind = candidate.InfectedEntity.GetMindStateSynced();
            if (mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT || candidate.Profile == "native_injured")
                return false;
        }
        m_LastPosition = leader.GetPosition();
        m_Search = search;
        m_Expires = expires;
        m_LastProgress = now;
        RouteEnd = end;
        Group = GetAIWorld().CreateGroup("DZInfectedPackBeh");
        if (!Group)
            return false;
        BehaviourGroupInfectedPack behaviour = BehaviourGroupInfectedPack.Cast(Group.GetBehaviour());
        if (!behaviour)
        {
            Group = null; // Empty groups are deleted next frame by AIWorld.
            return false;
        }
        m_RoutePlan = route;
        RoutePlanned = route.Count();
        RouteCompleted = 0;
        RoutePurpose = 1;
        if (search && route.Count() > 1) RoutePurpose = 2;
        RouteResult = 1;
        RouteEnd = route[route.Count() - 1].m_CenterPosition;
        if (!ActivateWaypoint(now))
        {
            Group = null; // Still empty; no agents are destroyed.
            RouteResult = 6;
            return false;
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
        if (m_Members.Count() < 1 || m_Members.Count() > 6 || now >= m_Expires)
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
        if (!HCInfectedPolicy.RetargetAllowed(now, m_NextRetarget, clue.Observed, m_LastRetargetObserved, clue.Expires, m_RetargetAttempts, leader != null, false))
            return 0;
        // Failed geometry still spends an attempt/cooldown. A repeated blocked
        // clue cannot repeatedly consume native pathfinding work.
        m_RetargetAttempts++;
        m_NextRetarget = now + 10;
        m_LastRetargetObserved = clue.Observed;
        vector end;
        if (!Reachable(leader.GetPosition(), clue.Origin, 120, end))
            return 1;
        BehaviourGroupInfectedPack behaviour = BehaviourGroupInfectedPack.Cast(Group.GetBehaviour());
        if (!behaviour) return 1;
        ref array<ref BehaviourGroupInfectedPackWaypointParams> route = new array<ref BehaviourGroupInfectedPackWaypointParams>;
        route.Insert(new BehaviourGroupInfectedPackWaypointParams(end, 1.5));
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
        float worstDistanceSq = 0;
        vector destination = m_RoutePlan[RouteCompleted].m_CenterPosition;
        float radius = m_RoutePlan[RouteCompleted].m_Radius;
        ZombieBase leader;
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
            if (!leader) leader = member;
            ownedMembers++;
            float distanceSq = vector.DistanceSq(position, destination);
            worstDistanceSq = Math.Max(worstDistanceSq, distanceSq);
            if (distanceSq <= radius * radius) arrivedMembers++;
            int mind = member.GetMindStateSynced();
            if (mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT)
                interrupted = true;
            if (member.GetHealth("LeftLeg", "Health") <= 0 || member.GetHealth("RightLeg", "Health") <= 0)
                interrupted = true;
        }
        if (leader) m_LastPosition = leader.GetPosition();
        if (m_BestRouteDistanceSq < 0)
            m_BestRouteDistanceSq = worstDistanceSq;
        if (HCInfectedPolicy.RouteMadeProgress(worstDistanceSq, m_BestRouteDistanceSq))
        {
            m_BestRouteDistanceSq = worstDistanceSq;
            m_LastProgress = now;
        }
        RouteResult = HCInfectedPolicy.RouteObservationResult(now, m_Expires, now - m_LastProgress, ownedMembers, arrivedMembers, ambiguous, interrupted);
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
        // Only a disappeared entity or confirmed expected fallback can leave
        // this ledger. Even a temporarily missing AIAgent remains unresolved.
        for (int i = m_Members.Count() - 1; i >= 0; i--)
        {
            ZombieBase member = m_Members[i];
            if (!member)
            {
                m_ReleaseFallbacks.Remove(member);
                m_Members.Remove(i);
                continue;
            }
            AIAgent observedAgent = member.GetAIAgent();
            AIGroup expected = m_ReleaseFallbacks.Get(member);
            if (observedAgent && expected && observedAgent.GetGroup() == expected)
            {
                m_ReleaseFallbacks.Remove(member);
                m_Members.Remove(i);
            }
        }
        if (m_Members.Count() == 0)
        {
            m_ReleaseFallbacks.Clear();
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
        {
            if (m_ReleaseAttempts >= HCInfectedPolicy.MaxReleaseAttempts() && !m_ReleaseQuarantined)
            {
                m_ReleaseQuarantined = true;
                Print("[HC Infected] native release quarantined; fallback ownership unconfirmed");
            }
            return false;
        }
        m_ReleaseAttempts++;
        m_NextReleaseUtc = nowUtc + 5;
        AIWorld world = GetAIWorld();
        if (!world) return false;
        for (int j = m_Members.Count() - 1; j >= 0; j--)
        {
            AIAgent agent = m_Members[j].GetAIAgent();
            if (!agent)
                continue;
            // Never detach an unexpected native owner in order to make our
            // bookkeeping succeed. Keep that member quarantinable instead.
            if (agent.GetGroup() && agent.GetGroup() != Group)
                continue;
            AIGroup fallback = m_ReleaseFallbacks.Get(m_Members[j]);
            if (!fallback)
            {
                // AIWorld deletes empty groups next frame. If a failed add's
                // expected group has disappeared, record a replacement before
                // another transfer attempt; never accept null == null as proof.
                fallback = world.CreateDefaultGroup();
                if (!fallback)
                    continue;
                m_ReleaseFallbacks.Set(m_Members[j], fallback);
            }
            if (Group && agent.GetGroup() == Group)
                Group.RemoveAgent(agent);
            // RemoveAgent is void too: verify detachment before attempting add.
            if (!agent.GetGroup())
                fallback.AddAgent(agent);
            if (agent.GetGroup() == fallback)
            {
                m_ReleaseFallbacks.Remove(m_Members[j]);
                m_Members.Remove(j);
            }
        }
        if (m_Members.Count() == 0)
        {
            m_ReleaseFallbacks.Clear();
            Group = null;
            s_PendingRelease.RemoveItem(this);
            return true;
        }
        return false;
    }
}

class HCInfectedObservation
{
    // Module budget gate: false while VisualProvenanceEstablished has no
    // observed evidence source, so no sampling slot is spent on a known no-op.
    static bool VisualSamplingAvailable()
    {
        return true;
    }

    static bool VisualProvenanceEstablished(DayZInfectedInputController controller)
    {
        // 1.30.164289 3_Game/Entities/DayZInfectedInputController.c:9-10
        // exposes mind state and retained target, not a fresh visual receipt.
        // No observed lighting-aware source exists here. Leave native pursuit
        // alone; unknown sight must not read hidden coordinates or refresh clues.
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
