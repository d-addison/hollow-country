// HC-16 / #143. One existing state and at most one existing actor per dispatch.
// No spawner, new identity, route probe, inventory mutator, construction or door
// lock. HC-18 owns locality pages; HC-10 owns every transient party/cargo lease.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:1120 IsServer;
// 3_Game/Entities/Object.c:287 GetPosition, :517 IsAlive;
// Shared HCPerfPlayers: Game.c:1535 GetTime, :945 GetPlayers (one snapshot).
// 3_Game/Entities/Man.c:21 GetIdentity; 1_Core/proto/EnConvert.c:210 DistanceSq;
// 1_Core/proto/EnScript.c:380 Count; EnDebug.c:96 Print; EnConvert.c:30 ToString.
// 4_World/Entities/ManBase/PlayerBase.c:1892 GetEmoteManager;
// Classes/EmoteManager.c:640 PlayEmote (NOT invoked directly), :1026
// CanPlayEmote, :1328 IsEmotePlaying; EmoteClasses.c:475-486 EmoteSitA.
// Installed ai_scripts.pbo, read only (no provider code copied):
// 4_World/DayZExpansion_AI/Classes/eAIGroup.c:1123 IsInCombat, :1139
// GetMember, :1185 Count; Entities/DayZPlayerImplement.c:234 GetGroup,
// :431 EEKilled defers member cleanup; Entities/AI/eAIBase.c:4755
// OverrideTargetPosition, :10860 Expansion_SetEmote (FSM request, not success),
// :10867-10920 playback/autocancel. The existing qualified navmesh points are
// the ONLY destinations. Native eating/fire/repair custody is UNPROVEN.
modded class HCXAISiteState
{
    int HCCampMemberCursor;
    int HCCampRoleEpoch;
    int HCCampNextRoleAt;
    string HCCampRefusal;
}

class HCXAICampRoutine
{
    protected bool m_Enabled;
    protected bool m_Closed;
    protected int m_Cursor;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;

    void Open(HCSettings settings)
    {
        m_Enabled = settings && settings.EnableEncounters;
        m_Closed = false;
        if (!m_Enabled)
        {
            Print("[HC Plan] HC-16 camp=none level=-1 supply=0 roles=0 state=off runtime=PENDING");
        }
    }

    void Close()
    {
        m_Enabled = false;
        m_Closed = true;
        m_Cursor = 0;
        // No persistent action, group setting or target override is owned here.
        // Rest requests use the provider's bounded auto-cancel timer.
    }

    protected void HCRefuse(HCXAISiteState state, string reason)
    {
        if (state.HCCampRefusal == reason) { return; }
        state.HCCampRefusal = reason;
        Print("[HC Plan] HC-16 camp=" + state.ProposalId + " level=-1 supply=0 roles=0 state=refused refusal=" + reason + " runtime=PENDING");
    }

    void Step()
    {
        if (!m_Enabled || m_Closed || !GetGame() || !GetGame().IsServer()) { return; }
        array<Man> players = HCPerfPlayers.HCGet();
        if (!players || players.Count() == 0) { return; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        HCHoldouts camps = HCHoldouts.Get();
        if (!director || director.Phase() != "run" || !camps) { return; }
        array<ref HCXAISiteState> states = director.States();
        if (!states || states.Count() == 0) { return; }
        m_Units.HCReset(1);
        m_Work.HCReset(1);
        if (!m_Units.HCTake(1) || !m_Work.HCContinue()) { return; }
        m_Cursor = m_Cursor % states.Count();
        HCXAISiteState state = states[m_Cursor];
        m_Cursor++;
        if (!state || !state.Transient || state.Completed || !state.Qualified || !state.Patrol) { return; }
        HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(state.ProposalId);
        if (!identity || identity.HCCampId().IndexOf("camp:") != 0) { return; }
        HCAICampRoutineView view = camps.HCRoutineView(identity);
        if (!view) { HCRefuse(state, "FUNDED_HOME_UNAVAILABLE"); return; }
        if (view.Home.State == "ALERT") { return; }
        eAIGroup group = state.Patrol.m_Group;
        if (!group || group.Count() < 1 || group.IsInCombat()) { return; }
        if (group.Count() > view.Population) { HCRefuse(state, "POPULATION_EXCEEDS_FUNDED_HOME"); return; }
        HCAICampPolicy policy = camps.HCRoutinePolicy();
        int memberIndex = state.HCCampMemberCursor % group.Count();
        state.HCCampMemberCursor = (memberIndex + 1) % group.Count();
        eAIBase actor = eAIBase.Cast(group.GetMember(memberIndex));
        if (!actor || !actor.IsAlive() || actor.GetIdentity()) { return; }
        float rangeSq = policy.RoutineRangeMeters * policy.RoutineRangeMeters;
        if (vector.DistanceSq(actor.GetPosition(), view.Home.HousePos) > rangeSq)
        {
            HCRefuse(state, "HOUSE_ROUTE_CONNECTION_UNPROVEN");
            return;
        }
        if (!camps.HCOwnsOccupant(view.Home.Id, actor) && !camps.BindOccupant(view.Home.Id, actor))
        {
            HCRefuse(state, "HOME_BODY_BIND_REFUSED");
            return;
        }
        int now = HCWorldClock.UTC();
        if (now < state.HCCampNextRoleAt) { return; }
        if (state.HCCampNextRoleAt > 0)
        {
            state.HCCampMemberCursor = 0;
            state.HCCampNextRoleAt = 0;
            return;
        }
        // Shared epoch gives exactly one sentry slot; other slots rotate rest
        // and work-route walking. No harvest, repairs or nutrition are implied.
        int role = (memberIndex + state.HCCampRoleEpoch) % group.Count();
        string roleName = "sentry";
        if (role == 1)
        {
            EmoteManager emotes = actor.GetEmoteManager();
            if (!emotes || emotes.IsEmotePlaying() || !emotes.CanPlayEmote(EmoteConstants.ID_EMOTE_SITA))
            {
                HCRefuse(state, "REST_EMOTE_NOT_ADMITTED");
                return;
            }
            // Auto-cancel delay is milliseconds; observation still pending.
            actor.Expansion_SetEmote(EmoteConstants.ID_EMOTE_SITA, true, policy.RoleSeconds * 1000);
            roleName = "rest_requested";
        }
        else
        {
            if (!state.PatrolPoints || state.PatrolPoints.Count() < 1) { HCRefuse(state, "QUALIFIED_WORK_ROUTE_MISSING"); return; }
            int pointIndex = 0;
            if (role > 1) { pointIndex = state.HCCampRoleEpoch % state.PatrolPoints.Count(); roleName = "work_walk_requested"; }
            vector destination = state.PatrolPoints[pointIndex];
            if (vector.DistanceSq(destination, view.Home.HousePos) > rangeSq)
            {
                HCRefuse(state, "HOUSE_ROUTE_CONNECTION_UNPROVEN");
                return;
            }
            // Provider pathfinding owns locomotion, collision and combat. No
            // SetPosition, formation change or unobserved action outcome.
            actor.OverrideTargetPosition(destination, true, policy.ArrivalToleranceMeters, false);
        }
        // One role request per visit; all members get a slot before relief.
        if (memberIndex == group.Count() - 1)
        {
            state.HCCampNextRoleAt = now + policy.RoleSeconds;
            state.HCCampRoleEpoch = (state.HCCampRoleEpoch + 1) % group.Count();
        }
        state.HCCampRefusal = "";
        string line = "[HC Plan] HC-16 camp=" + view.Home.Id + " level=" + view.Level.ToString();
        line += " supply=" + view.Supply.ToString() + " roles=1 state=ready role=" + roleName;
        Print(line + " refusal=EAT_FIRE_REPAIR_UNPROVEN runtime=PENDING");
    }

    // Actual provider EEKilled, before its deferred group cleanup. Identity is
    // the current HC-10 lease; no client assertion or inferred timed casualty.
    static void HCObserveKilled(eAIBase body)
    {
        if (!body || !GetGame() || !GetGame().IsServer()) { return; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        HCHoldouts camps = HCHoldouts.Get();
        if (!director || !camps) { return; }
        eAIGroup group = body.GetGroup();
        if (!group) { return; }
        foreach (HCXAISiteState state : director.States())
        {
            if (!state.Transient || state.Completed || !state.Patrol || state.Patrol.m_Group != group) { continue; }
            HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(state.ProposalId);
            if (identity) { camps.HCPartyKilled(identity, body); }
            return;
        }
    }
}

modded class eAIBase
{
    protected bool m_HCCampDeathSent;
    override void EEKilled(Object killer)
    {
        if (!m_HCCampDeathSent)
        {
            m_HCCampDeathSent = true;
            HCXAICampRoutine.HCObserveKilled(this);
        }
        super.EEKilled(killer);
    }
}
