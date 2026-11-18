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
class HCHordeMigration : HCModule
{
    protected static bool s_Active;
    protected bool m_WaitingPrinted;
    override string GetName() { return "HordeMigration"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableWorld; }
    static bool Active() { return s_Active; }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("HordeMigration", true, "EXP-S4", HCV2Gates.Qualified("EXP-S4")));
        s_Active = true;
    }
    override void OnTick(float deltaTime)
    {
        HCInfectedModule infected = HCInfectedModule.Instance;
        if (!infected) { return; }
        int packs = infected.HCV2MigrationStep();
        if (packs == 0 && !m_WaitingPrinted)
        {
            m_WaitingPrinted = true;
            Print("[HollowCountry] V2 herd drift waiting: no eligible owned v1 native pack; v1 adoption/pack prerequisites unchanged");
        }
    }
    override void OnStop() { s_Active = false; }
}

modded class HCInfectedModule
{
    protected int m_V2DriftCursor;

    // Called by the self-registered V2 driver. At most two packs/24 actors;
    // one cohort gets a clue selection each tick. No external world scan.
    int HCV2MigrationStep()
    {
        if (!m_Healthy || !m_Hordes || !m_State || m_Packs.Count() < 1 || !HCHordeMigration.Active()) { return 0; }
        // The v1 horde_stimulus_routes opt-out and heard gate also stop V2 drift.
        if (!m_Config.EnableHordeStimulusRoutes || !m_Admission.HordeStimulusRoutes || !HeardAdmitted()) { return 0; }
        int count = m_Packs.Count();
        int eligible = 0;
        for (int packIndex = 0; packIndex < count; packIndex++)
        {
            HCHordeRecord candidate = m_State.Groups[packIndex];
            if (m_Packs[packIndex] && !m_Packs[packIndex].IsReleasing() && candidate.State != 5 && candidate.State != 6 && !candidate.RecoveryConflicted) { eligible++; }
        }
        int index = m_V2DriftCursor % count;
        m_V2DriftCursor = (index + 1) % count;
        HCNativeInfectedPack pack = m_Packs[index];
        HCHordeRecord record = m_State.Groups[index];
        if (!pack || pack.IsReleasing() || record.State == 5 || record.State == 6 || record.RecoveryConflicted) { return eligible; }
        HCInfectedClue chosen;
        float bestHeat = -1;
        foreach (HCInfectedActor actor : m_Actors)
        {
            if (actor.GroupId != record.Id || !actor.InfectedEntity || !pack.OwnsMember(actor.InfectedEntity)) { continue; }
            HCInfectedClue clue = HCHordeStimulus.MigrationClue(actor, m_Now);
            if (!clue) { continue; }
            // Memory heat is an attractor ONLY among places this herd heard.
            float heat = HCInfectedMemory.Heat(clue.Origin);
            if (!chosen || heat > bestHeat || (heat == bestHeat && HCHordeStimulus.PreferClue(clue, chosen, m_Now)))
            {
                chosen = clue;
                bestHeat = heat;
            }
        }
        if (chosen) { pack.V2Remember(record.Id, chosen, m_Now); }
        return eligible;
    }

    bool HCV2DriftRouteToken()
    {
        if (m_RoutesRemaining < 1) { return false; }
        m_RoutesRemaining--;
        return true;
    }

    override protected void RetargetCohorts()
    {
        // V2 owns only a pack with a remembered, in-range drift destination.
        // Empty/out-of-range/rejected packs retain the v1/ecology route path.
        super.RetargetCohorts();
    }
}

modded class HCNativeInfectedPack
{
    protected bool m_V2Drift;
    protected bool m_V2Paused;
    protected bool m_V2Reported;
    protected bool m_V2Segment;
    protected vector m_V2Destination;
    protected float m_V2Deadline;
    protected float m_V2ClearSince = -1;
    protected float m_V2NextSegment;
    protected float m_V2LastEvidence = -1;
    protected float m_V2Cooldown;
    protected float m_V2BestDistance = -1;
    protected float m_V2Progress;
    protected int m_V2Attempts;
    protected int m_V2MemberCount;
    protected int m_V2Id;

    override bool IsV2Drifting()
    {
        return m_V2Drift;
    }

    override int Retarget(HCInfectedClue clue, float now)
    {
        if (HCHordeMigration.Active() && m_V2Drift)
        {
            return 0;
        }
        return super.Retarget(clue, now);
    }

    void V2Remember(int id, HCInfectedClue clue, float now)
    {
        if (m_V2Drift || m_Search || m_Releasing || !Group || !clue || !clue.IsLive(now)) { return; }
        if (now < m_V2Cooldown || clue.Provenance != 1 || clue.Observed <= m_V2LastEvidence || !HCInfectedStore.ValidPosition(clue.Origin)) { return; }
        if (m_Members.Count() < 1 || m_Members.Count() > 6) { return; }
        ZombieBase leader = m_Members[0];
        if (!leader || vector.DistanceSq(leader.GetPosition(), clue.Origin) > 230400) { return; }
        m_V2Id = id;
        m_V2Destination = clue.Origin;
        m_V2MemberCount = m_Members.Count();
        m_V2LastEvidence = clue.Observed;
        // A remembered location, not renewed live perception. At most ten
        // minutes from ORIGINAL observation, never extended by heat or ticks.
        m_V2Deadline = clue.Observed + 600;
        m_V2Attempts = 0;
        m_V2ClearSince = -1;
        m_V2NextSegment = now;
        m_V2Progress = now;
        m_V2Reported = false;
        m_V2Segment = false;
        m_V2Paused = false;
        m_V2Drift = true;
        // W5 #121: the same capped native roster becomes a walker herd while
        // variety is enabled. Its command adapter only caps requested speed.
        HCVarietyWalkerHerd();
    }

    // Actual production segment commit is exercised by the one synthetic smoke.
    // The same native group and m_Members references survive every waypoint.
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

    protected bool V2End(float now, int result)
    {
        m_V2Drift = false;
        m_V2Cooldown = now + 180;
        RouteResult = result;
        if (result == 2) { RouteCompleted = RoutePlanned; }
        // Original retained release ledger handles native group ownership. It
        // never deletes infected, refills reservations or resurrects a member.
        return !Release();
    }

    protected bool V2Tick(float now)
    {
        if (!HCHordeMigration.Active() || now >= m_V2Deadline || m_Releasing || !Group || !m_RoutePlan) { return V2End(now, 5); }
        if (m_Members.Count() != m_V2MemberCount) { return V2End(now, 6); }
        ZombieBase leader;
        vector centroid;
        // Same pointer roster, every member alive and still owned. Injury,
        // death, ambiguity or native combat ends the drift instead of refilling.
        foreach (ZombieBase member : m_Members)
        {
            if (!member || !member.IsAlive()) { return V2End(now, 5); }
            AIAgent agent = member.GetAIAgent();
            if (!agent || agent.GetGroup() != Group) { return V2End(now, 6); }
            int mind = member.GetMindStateSynced();
            if (mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT || member.GetHealth("LeftLeg", "Health") <= 0 || member.GetHealth("RightLeg", "Health") <= 0) { return V2End(now, 5); }
            vector memberPosition = member.GetPosition();
            if (!HCInfectedStore.ValidPosition(memberPosition)) { return V2End(now, 6); }
            centroid = centroid + memberPosition;
            if (!leader) { leader = member; }
        }
        if (!leader) { return V2End(now, 6); }
        centroid = centroid * (1.0 / m_V2MemberCount);
        m_LastPosition = leader.GetPosition();
        // Reject a scattered pack, so checking its centroid covers every member
        // by >1 km even at the edge of the conservative 1200 m observer veto.
        foreach (ZombieBase clustered : m_Members)
        {
            if (vector.DistanceSq(clustered.GetPosition(), centroid) > 10000) { return V2End(now, 5); }
        }
        bool quiet = HCObserverTransitionGate.V2Quiet(centroid, m_V2Destination, now, 60, m_V2ClearSince);
        if (!quiet)
        {
            if (!m_V2Paused)
            {
                BehaviourGroupInfectedPack behaviour = BehaviourGroupInfectedPack.Cast(Group.GetBehaviour());
                if (!behaviour) { return V2End(now, 6); }
                // Cancel authored drift. Native combat stays authoritative;
                // W5 variety independently caps requested movement speed.
                array<ref BehaviourGroupInfectedPackWaypointParams> hold = new array<ref BehaviourGroupInfectedPackWaypointParams>;
                hold.Insert(new BehaviourGroupInfectedPackWaypointParams(centroid, 4));
                behaviour.SetWaypoints(hold, 0, true, false);
                m_V2Paused = true;
                m_V2Segment = false;
            }
            m_V2Progress = now;
            return true;
        }
        float remaining = vector.DistanceSq(centroid, m_V2Destination);
        if (remaining <= 64) { return V2End(now, 2); }
        if (m_V2Segment)
        {
            float segmentDistance = vector.DistanceSq(centroid, RouteEnd);
            if (m_V2BestDistance < 0 || segmentDistance < m_V2BestDistance - 1)
            {
                m_V2BestDistance = segmentDistance;
                m_V2Progress = now;
            }
            if (segmentDistance > 64)
            {
                if (now - m_V2Progress >= 90) { return V2End(now, 3); }
                return true;
            }
        }
        if (now < m_V2NextSegment) { return true; }
        if (m_V2Attempts >= 10) { return V2End(now, 5); }
        HCInfectedModule owner = HCInfectedModule.Instance;
        if (!owner || !owner.HCV2DriftRouteToken()) { return true; }
        m_V2Attempts++;
        // Pressure changes cadence only, never population, movement speed or TTL.
        m_V2NextSegment = now + 45 - 15 * HCEscalationClock.Pressure("infected");
        vector delta = m_V2Destination - centroid;
        delta[1] = 0;
        float distance = delta.Length();
        delta.Normalize();
        vector desired = centroid + delta * Math.Min(48, distance);
        desired[1] = GetGame().SurfaceY(desired[0], desired[2]);
        vector sampled;
        if (!Reachable(leader.GetPosition(), desired, 120, sampled))
        {
            // A refused navmesh segment ends this finite attempt. No fallback
            // displacement, guessed road nodes or repeated stuck correction.
            return V2End(now, 6);
        }
        if (!V2CommitSegment(sampled, now)) { return V2End(now, 6); }
        m_V2Paused = false;
        m_V2Segment = true;
        m_V2BestDistance = -1;
        m_V2Progress = now;
        if (!m_V2Reported)
        {
            m_V2Reported = true;
            string place = "heard-location";
            HCWorldModule world = HCWorldModule.Get();
            if (world) { place = world.NearestPlace(m_V2Destination); }
            Print("[HollowCountry] V2 herd drift id=" + m_V2Id.ToString() + " toward=" + place);
            Print("[HollowCountry] V2 herd drift members=" + m_V2MemberCount.ToString() + " population=preserved native-waypoints runtime-unverified");
        }
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
