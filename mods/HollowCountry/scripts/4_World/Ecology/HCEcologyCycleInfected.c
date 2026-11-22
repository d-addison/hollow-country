// Same owner and native waypoint machinery as ordinary HC packs. This is an
// environmental goal, NOT a perceived player/noise clue. No group transfers,
// spawns, speed overrides or position writes. API evidence: AIWorld.c:98/122;
// AIGroupBehaviour.c:27; DayZInfectedInputController.c:9/10; Object.c:994.
modded class HCNativeInfectedPack
{
    bool HCEcologyOwnsTown(array<HCInfectedActor> members)
    {
        if (m_Releasing || m_ReleaseQuarantined || !members || members.Count() < 1 || members.Count() > HCHordeLimits.MAX_PACK || members.Count() != m_Members.Count()) { return false; }
        map<ZombieBase, bool> seen = new map<ZombieBase, bool>;
        foreach (HCInfectedActor actor : members)
        {
            if (!actor || !actor.InfectedEntity || !actor.InfectedEntity.IsAlive() || !OwnsMember(actor.InfectedEntity) || seen.Contains(actor.InfectedEntity)) { return false; }
            seen.Set(actor.InfectedEntity, true);
        }
        return true;
    }

    int HCEcologyTownStep(vector goal, float now, int interval)
    {
        if (!GetGame().IsServer() || m_Search || m_Releasing || !Group || IsV2Drifting() || now >= m_Expires || now < m_NextRetarget) { return 0; }
        if (m_Members.Count() < 1 || m_Members.Count() > HCHordeLimits.MAX_PACK) { return 0; }
        ZombieBase leader;
        foreach (ZombieBase member : m_Members)
        {
            if (!member || !member.IsAlive() || !OwnsMember(member)) { return 0; }
            DayZInfectedInputController controller = member.GetInputController();
            if (!controller || controller.GetTargetEntity() || controller.GetMindState() != DayZInfectedConstants.MINDSTATE_CALM) { return 0; }
            if (member.GetHealth("LeftLeg", "Health") <= 0 || member.GetHealth("RightLeg", "Health") <= 0) { return 0; }
            if (!leader) { leader = member; }
        }
        m_NextRetarget = now + interval;
        vector end;
        if (!Reachable(leader.GetPosition(), goal, 120, end)) { return 1; }
        m_RoutePlan = new array<ref BehaviourGroupInfectedPackWaypointParams>;
        m_RoutePlan.Insert(new BehaviourGroupInfectedPackWaypointParams(end, HCInfectedTuning.Get().Navigation.WaypointRadius));
        RoutePlanned = 1;
        RouteCompleted = 0;
        RoutePurpose = 1;
        RouteResult = 1;
        m_PendingRooms = null;
        RouteEnd = end;
        m_LastPosition = leader.GetPosition();
        m_LastProgress = now;
        if (!ActivateWaypoint(now)) { RouteResult = 6; return 1; }
        return 2; // command issued, not arrival evidence
    }
}

// Extend the existing owner's route-budget seam; never register another
// infected roster. At most one bounded native pack (at most 40 members) is offered per tick.
modded class HCInfectedModule
{
    protected int m_HCEcologyPackCursor;
    override protected void RetargetCohorts()
    {
        HCEcologyCycle cycle = HCEcologyCycle.Active();
        int count = m_Packs.Count();
        if (cycle && cycle.Ready() && cycle.NeedsMigration() && HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_ECOLOGY_MIGRATION, 1) && m_Healthy && m_Hordes && m_State && m_RoutesRemaining > 0 && count > 0 && count == m_State.Groups.Count())
        {
            int index = m_HCEcologyPackCursor % count;
            m_HCEcologyPackCursor = (index + 1) % count;
            HCHordeRecord record = m_State.Groups[index];
            HCNativeInfectedPack pack = m_Packs[index];
            if (record && pack && record.State != 5 && record.State != 6 && !record.RecoveryConflicted && !pack.IsReleasing() && !pack.IsV2Drifting())
            {
                int result = HCEcologyMigration.SubmitTown(record.Id, pack, m_Actors, m_Now);
                if (HCInfectedPolicy.RetargetSpent(result))
                {
                    m_RoutesRemaining--;
                    SnapshotRoute(record, pack);
                }
                // Prepared durable intent owns the pack until its outcome is
                // saved. No ordinary cue may overwrite it during that window.
                if (result == 3) { return; }
            }
        }
        super.RetargetCohorts();
    }
}
