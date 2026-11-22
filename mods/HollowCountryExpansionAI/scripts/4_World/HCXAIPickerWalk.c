// HC-34 / LC-T409: original walk port, no copied Expansion implementation.
// Verified read-only against .banso-writer/xref/ai and xref/core (CC BY-NC-ND).
// Installed ai_scripts.pbo (script paths relative to PBO):
// 4_World/DayZExpansion_AI/Classes/eAIGroup.c:213 void AddWaypoint(vector pos),
// :222 array<vector> GetWaypoints(), :241 void ClearWaypoints(),
// :251 void SetWaypointBehaviour(eAIWaypointBehavior),
// :304 eAIWaypointBehavior GetWaypointBehaviour;
// :228 returns the GROUP-owned live waypoint array (never retain/clear it);
// :247-248 ClearWaypoints clears that array and resets its cursor.
// Classes/Patrols/eAIDynamicPatrol.c:649-655 installs group behavior/points;
// :673-687 deferred members finish before restoring patrol behavior. HC waits
// for m_HCPendingMembers == 0 before borrowing that same group.
// 4_World/DayZExpansion_AI/Entities/DayZPlayerImplement.c:234 GetGroup;
// 3_Game/DayZExpansion_AI/Enums/AIenums.c:6 eAIWaypointBehavior.ONCE.
// UTC seconds via HCXExpansionBridge.HCGetTimestamp (negative on refusal).
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380 Count, :385 Clear,
// :407 Insert. Other calls are existing HC ports. Runtime acceptance PENDING.
// Preserve the existing party's patrol, never create a second group. Each leg
// and saved patrol is capped by Survey.MaxWaypoints. No scheduler or arrival
// inference: the base observes real positions and owns the custody journal.
class HCXAIPickerWalk : HCScavengeInventory
{
    // #208: observation is transfer eligibility, never party identity.
    // Reuse the configured party cooldown as the maximum observed-home wait;
    // no new timer, scheduler, inventory owner or retry of a native move.
    protected int m_DepositWaitUntil;
    protected ref HCScavengeState m_TransferState;

    override bool HCAtHome()
    {
        if (!super.HCAtHome()) { return false; }
        HCScavengeState homeCheck = new HCScavengeState;
        homeCheck.Phase = "returning";
        if (HCCampTheft.HCGuard(this, homeCheck)) { return true; }
        int now = HCXExpansionBridge.HCGetTimestamp();
        if (now < 0) { return false; }
        if (m_DepositWaitUntil == 0) { m_DepositWaitUntil = now + Defaults.PartyCooldownSeconds; }
        // At expiry enter the normal durable intent/refusal path. HCMove still
        // vetoes observation, retaining the exact physical item on the carrier.
        return now >= m_DepositWaitUntil;
    }

    override int HCMove(bool returning, HCScavengeState row)
    {
        if (!HCCampTheft.HCGuard(this, row)) { return 4; }
        m_TransferState = row;
        int result = super.HCMove(returning, row);
        m_TransferState = null;
        return result;
    }

    override bool HCAccessible(EntityAI cache)
    {
        // Base HCMove repeats accessibility after inventory preflight callbacks.
        // Retain that second observer veto without changing HCPartyCurrent.
        if (m_TransferState && !HCCampTheft.HCGuard(this, m_TransferState)) { return false; }
        return super.HCAccessible(cache);
    }

    // #334: the walk holds its group only through the bridge handle; every read and write goes
    // through HCHold* and refuses once the group or the bridge is gone.
    protected ref HCXAIGroupHold m_HCHold;
    void ~HCXAIPickerWalk() { HCXAIGroupHolds.Retire(m_HCHold); }
    protected ref array<vector> m_PreviousPoints = new array<vector>();
    protected eAIWaypointBehavior m_PreviousBehavior;
    protected string m_WalkRefusal;

    override string HCWalkRefusal()
    {
        if (m_WalkRefusal != "") { return m_WalkRefusal; }
        // No actor between trips: the walk provider itself is installed.
        if (Actor && !HCXExpansionBridge.HCDayZPlayerImplementGetGroup(Actor)) { return "PICKER_ACTOR_GROUP_MISSING"; }
        return "";
    }

    override bool HCWalk(bool returning)
    {
        m_WalkRefusal = "";
        if (!HCLive() || !Survey) { m_WalkRefusal = "PICKER_WALK_NOT_LIVE"; return false; }
        eAIGroup group = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(Actor);
        if (!group) { m_WalkRefusal = "PICKER_ACTOR_GROUP_MISSING"; return false; }
        if (m_HCHold && !HCXExpansionBridge.HCHoldSame(m_HCHold, group)) { m_WalkRefusal = "PICKER_ACTOR_GROUP_CHANGED"; return false; }
        HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(LeaseId);
        if (!HCAIPartyIdentity.HCValid(identity)) { m_WalkRefusal = "PICKER_IDENTITY_INVALID"; return false; }
        HCPickerRoute route = Survey.HCFind(identity.HCRouteId());
        if (!route || !route.Waypoints || route.Waypoints.Count() > Survey.MaxWaypoints) { m_WalkRefusal = "PICKER_ROUTE_UNSURVEYED"; return false; }
        array<vector> points = new array<vector>();
        route.HCLegPoints(returning, points);
        if (points.Count() < 1 || points.Count() > Survey.MaxWaypoints) { m_WalkRefusal = "PICKER_ROUTE_LEG_INVALID"; return false; }
        array<vector> previous = HCXExpansionBridge.HCGroupGetWaypoints(group);
        if (!m_HCHold && previous.Count() > Survey.MaxWaypoints) { m_WalkRefusal = "PICKER_PATROL_WAYPOINT_CAP"; return false; }
        if (!HCServer.HCTickWork().HCTakeAISlice(HCUnitBudget.HC_AI_PICKER_WALK, HCUnitBudget.HC_WORK_AI_SITES, 1)) { m_WalkRefusal = "PICKER_WALK_WORK_BUDGET"; return false; }
        if (!m_HCHold)
        {
            m_PreviousPoints.Clear();
            for (int priorIndex = 0; priorIndex < previous.Count(); priorIndex++) { m_PreviousPoints.Insert(previous[priorIndex]); }
            m_PreviousBehavior = HCXExpansionBridge.HCGroupGetWaypointBehaviour(group);
            m_HCHold = HCXAIGroupHolds.Follow(m_HCHold, group);
            if (!m_HCHold) { m_WalkRefusal = "PICKER_GROUP_HANDLE_REFUSED"; return false; }
        }
        HCXExpansionBridge.HCHoldClearWaypoints(m_HCHold);
        for (int legIndex = 0; legIndex < points.Count(); legIndex++) { HCXExpansionBridge.HCHoldAddWaypoint(m_HCHold, points[legIndex]); }
        HCXExpansionBridge.HCHoldSetWaypointBehaviour(m_HCHold, eAIWaypointBehavior.ONCE);
        return true;
    }

    // #144: one detour waypoint on the group HCWalk already claimed (its previous
    // patrol is saved there and restored by HCFinishWalk). Never claims a new group,
    // never moves a member directly. eAIGroup.c:213 AddWaypoint, :241 ClearWaypoints,
    // :251 SetWaypointBehaviour (ONCE). Arrival is observed by position only.
    override bool HCWalkTo(vector point)
    {
        if (!m_HCHold || !HCLive() || !Survey) { return false; }
        if (!HCXExpansionBridge.HCHoldSame(m_HCHold, HCXExpansionBridge.HCDayZPlayerImplementGetGroup(Actor))) { return false; }
        if (!HCServer.HCTickWork().HCTakeAISlice(HCUnitBudget.HC_AI_PICKER_WALK, HCUnitBudget.HC_WORK_AI_SITES, 1)) { return false; }
        HCXExpansionBridge.HCHoldClearWaypoints(m_HCHold);
        HCXExpansionBridge.HCHoldAddWaypoint(m_HCHold, point);
        HCXExpansionBridge.HCHoldSetWaypointBehaviour(m_HCHold, eAIWaypointBehavior.ONCE);
        return true;
    }

    // eAIGroup.c:1185 Count, :1123 IsInCombat (read only).
    override int HCPartyMembers()
    {
        if (!Actor) { return -1; }
        eAIGroup group = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(Actor);
        if (!group) { return -1; }
        return HCXExpansionBridge.HCGroupCount(group);
    }

    override bool HCPartyInCombat()
    {
        if (!Actor) { return false; }
        eAIGroup group = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(Actor);
        return group && HCXExpansionBridge.HCGroupIsInCombat(group);
    }

    // Terminal custody, uncertain checkpoint or stop: resume the same group's
    // prior patrol list and behavior. Reset cursor via ClearWaypoints, exactly
    // as a fresh patrol request; never move or respawn a member. The group
    // handle stays valid through m_HCHold until the walk finishes (#334).
    void HCFinishWalk()
    {
        if (m_HCHold)
        {
            HCXExpansionBridge.HCHoldClearWaypoints(m_HCHold);
            array<vector> restorePoints = m_PreviousPoints;
            for (int restoreIndex = 0; restoreIndex < restorePoints.Count(); restoreIndex++) { HCXExpansionBridge.HCHoldAddWaypoint(m_HCHold, restorePoints[restoreIndex]); }
            HCXExpansionBridge.HCHoldSetWaypointBehaviour(m_HCHold, m_PreviousBehavior);
        }
        HCXAIGroupHolds.Retire(m_HCHold);
        m_HCHold = null;
        m_PreviousPoints.Clear();
    }

    override void HCClear()
    {
        HCFinishWalk();
        m_DepositWaitUntil = 0;
        m_TransferState = null;
        m_WalkRefusal = "";
        super.HCClear();
    }
}

// Observe the existing durable trip boundary, including native reentrant loss.
// No polling observer, extra save, inventory owner or cargo replay.
modded class HCScavengeTrip
{
    protected string m_HCPickerLoggedPhase;
    protected bool m_HCPickerClockPending;
    protected int m_HCPickerClockRefusals;

    bool HCPickerClockPending() { return m_HCPickerClockPending; }

    override void HCStep()
    {
        if (m_HCPickerClockPending)
        {
            // One checkpoint retry per existing trip tick, never a native move.
            if (m_Ready && !m_Busy) { HCCheckpoint(); }
            return;
        }
        super.HCStep();
    }

    void HCLogTripBoundary(bool saved)
    {
        if (!m_State || m_HCPickerLoggedPhase == m_State.Phase) { return; }
        m_HCPickerLoggedPhase = m_State.Phase;
        string phase = m_State.Phase;
        string boundary = "";
        if (saved && phase == "leaving") { boundary = "start"; }
        if (phase == "returned" || phase == "lost" || phase == "quarantined") { boundary = "end"; }
        if (boundary == "") { return; }
        string line = "[HC Pickers] trip=" + boundary + " party=" + m_State.PartyId;
        line += " route=" + m_State.RouteId + " outcome=" + phase;
        Print(line + " reason=" + m_State.Refusal + " runtime=PENDING");
    }

    override bool HCCheckpoint()
    {
        // UTC seconds, same existing clock as the site's raid journal. Stamp
        // before the durable terminal barrier; old V1 receipts zero-fill safely.
        bool clockValid = true;
        if (m_State && m_IO)
        {
            string terminal = m_State.Phase;
            if (terminal == "returned" || terminal == "lost" || terminal == "quarantined")
            {
                int now = HCXExpansionBridge.HCGetTimestamp();
                if (now < 0)
                {
                    // Keep the terminal phase, exact cargo owner and original
                    // refusal. Three consecutive attempts allow a transient
                    // clock failure to recover over two further ticks, while
                    // bounding retries when the clock remains unavailable.
                    clockValid = false;
                    m_HCPickerClockPending = true;
                    m_HCPickerClockRefusals++;
                    if (m_HCPickerClockRefusals >= 3) { m_Ready = false; }
                }
                else
                {
                    m_HCPickerClockPending = false;
                    m_HCPickerClockRefusals = 0;
                    m_State.NextTripAt = now + m_IO.Defaults.PartyCooldownSeconds;
                }
            }
        }
        bool saved = false;
        if (clockValid) { saved = super.HCCheckpoint(); }
        if (clockValid) { HCLogTripBoundary(saved); }
        HCXAIPickerWalk walkPort = HCXAIPickerWalk.Cast(m_IO);
        if (walkPort && m_State)
        {
            string phase = m_State.Phase;
            if (!saved || phase == "returned" || phase == "lost" || phase == "quarantined") { walkPort.HCFinishWalk(); }
        }
        return saved;
    }
}

// A terminal receipt awaiting its clock stamp must survive admission attempts.
modded class HCPickers
{
    override void OnTick(float deltaTime)
    {
        // Base OnTick skips terminal phases. Service the pending terminal
        // barrier with the same one-unit budget before allowing admission.
        if (m_Trip && m_Trip.HCPickerClockPending())
        {
            HCPublishReadiness();
            if (!m_Trip.m_Ready) { return; }
            m_WorkBudget.HCReset(1);
            if (!m_WorkBudget.HCContinue()) { return; }
            if (!HCServer.HCTickWork().HCTakeAISlice(HCUnitBudget.HC_AI_PICKER_PARTY, HCUnitBudget.HC_WORK_AI_SITES, 1)) { return; }
            m_Trip.HCStep();
            HCPublishReadiness();
            return;
        }
        super.OnTick(deltaTime);
    }

    override string HCTryParty(HCAIPartyIdentity identity, string lease, PlayerBase actor, int now, int eligibleAt)
    {
        if (m_Trip && m_Trip.HCPickerClockPending()) { return "PICKER_CLOCK_UNAVAILABLE"; }
        return super.HCTryParty(identity, lease, actor, now, eligibleAt);
    }
}
