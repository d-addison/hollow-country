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
// OverrideTargetPosition (no matching clear operation), :10860
// Expansion_SetEmote (FSM request, not success),
// :10867-10920 playback/autocancel. The existing qualified navmesh points are
// the ONLY admitted route candidates, but camp movement requests remain refused:
// eAIBase.c:4999-5005 writes the path target without a clear operation;
// :656-660 eAI_ResetPathfinding only resets unreachable bookkeeping/ladder loops.
// No zero-vector/current-position substitute or provider field write is used.
// Native eating/fire/repair custody is UNPROVEN.
modded class HCXAISiteState
{
    int HCCampMemberCursor;
    int HCCampRoleEpoch;
    int HCCampNextRoleAt;
    string HCCampRefusal;
    int HCCampRefusalRepeats;
}

class HCXAICampRoutine
{
    // #190: a repeated refusal is logged once per camp until the reason changes,
    // then one bounded summary per this many suppressed repeats.
    static const int REFUSAL_SUMMARY_EVERY = 50;
    static const string STRUCTURAL_REFUSAL = "ROUTINE_TARGET_CLEAR_UNAVAILABLE";
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
        // No camp target override is issued: the installed provider exposes no
        // matching clear call for release/close/combat/threat takeover.
        // Rest requests use the provider's bounded auto-cancel timer.
    }

    protected void HCRefuse(HCXAISiteState state, string reason)
    {
        if (state.HCCampRefusal == reason)
        {
            state.HCCampRefusalRepeats++;
            if (state.HCCampRefusalRepeats % REFUSAL_SUMMARY_EVERY == 0)
            {
                Print("[HC Plan] HC-16 camp=" + state.ProposalId + " state=refused refusal=" + reason + " refusal_repeats=" + state.HCCampRefusalRepeats.ToString() + " runtime=PENDING");
            }
            return;
        }
        state.HCCampRefusal = reason;
        state.HCCampRefusalRepeats = 0;
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
        eAIGroup group = state.Patrol.m_Group;
        if (!group || HCXExpansionBridge.HCGroupCount(group) < 1 || HCXExpansionBridge.HCGroupIsInCombat(group)) { return; }
        // Cooldown and relief have no content to read. In particular, do not
        // clone HCRoutineView's JSON ledger on these otherwise idle dispatches.
        int now = HCWorldClock.UTC();
        if (now < state.HCCampNextRoleAt) { return; }
        if (state.HCCampNextRoleAt > 0)
        {
            state.HCCampMemberCursor = 0;
            state.HCCampNextRoleAt = 0;
            return;
        }
        HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(state.ProposalId);
        if (!identity || identity.HCCampId().IndexOf("camp:") != 0) { return; }
        HCAICampRoutineView view = camps.HCRoutineView(identity);
        if (!view) { HCRefuse(state, "FUNDED_HOME_UNAVAILABLE"); return; }
        if (view.Home.State == "ALERT") { return; }
        if (HCXExpansionBridge.HCGroupCount(group) > view.Population) { HCRefuse(state, "POPULATION_EXCEEDS_FUNDED_HOME"); return; }
        HCAICampPolicy policy = camps.HCRoutinePolicy();
        int memberIndex = state.HCCampMemberCursor % HCXExpansionBridge.HCGroupCount(group);
        state.HCCampMemberCursor = (memberIndex + 1) % HCXExpansionBridge.HCGroupCount(group);
        eAIBase actor = eAIBase.Cast(HCXExpansionBridge.HCGroupGetMember(group, memberIndex));
        if (!actor || !HCXExpansionBridge.HCBaseIsAlive(actor) || HCXExpansionBridge.HCBaseGetIdentity(actor)) { return; }
        float rangeSq = policy.RoutineRangeMeters * policy.RoutineRangeMeters;
        if (vector.DistanceSq(HCXExpansionBridge.HCBaseGetPosition(actor), view.Home.HousePos) > rangeSq)
        {
            HCRefuse(state, "HOUSE_ROUTE_CONNECTION_UNPROVEN");
            return;
        }
        if (!camps.HCOwnsOccupant(view.Home.Id, actor) && !camps.BindOccupant(view.Home.Id, actor))
        {
            HCRefuse(state, "HOME_BODY_BIND_REFUSED");
            return;
        }
        // Two or more members retain one sentry slot in the role schedule.
        // A solo member keeps rest; movement slots are explicitly refused.
        int role = (memberIndex + state.HCCampRoleEpoch) % HCXExpansionBridge.HCGroupCount(group);
        if (HCXExpansionBridge.HCGroupCount(group) == 1) { role = 1; }
        string roleName = "sentry";
        if (role == 1)
        {
            EmoteManager emotes = HCXExpansionBridge.HCBaseGetEmoteManager(actor);
            if (!emotes || emotes.IsEmotePlaying() || !emotes.CanPlayEmote(EmoteConstants.ID_EMOTE_SITA))
            {
                HCRefuse(state, "REST_EMOTE_NOT_ADMITTED");
                return;
            }
            // Auto-cancel delay is milliseconds; observation still pending.
            HCXExpansionBridge.HCBaseExpansion_SetEmote(actor, EmoteConstants.ID_EMOTE_SITA, true, policy.RoleSeconds * 1000);
            roleName = "rest_requested";
        }
        else
        {
            // A path request without a verified release cannot be safely owned
            // across role relief, camp close, combat or an ALERT transition.
            HCRefuse(state, "ROUTINE_TARGET_CLEAR_UNAVAILABLE");
        }
        // One role request per visit; all members get a slot before relief.
        if (memberIndex == HCXExpansionBridge.HCGroupCount(group) - 1)
        {
            state.HCCampNextRoleAt = now + policy.RoleSeconds;
            state.HCCampRoleEpoch = (state.HCCampRoleEpoch + 1) % HCXExpansionBridge.HCGroupCount(group);
        }
        if (role != 1) { return; }
        // The sentry/work refusal is structural (no proven target-clear), so a
        // rest slot admitted in the same cycle must not re-arm its log line.
        if (state.HCCampRefusal != STRUCTURAL_REFUSAL) { state.HCCampRefusal = ""; }
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
        eAIGroup group = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(body);
        if (!group) { return; }
        array<ref HCXAISiteState> killedStates = director.States();
        foreach (HCXAISiteState state : killedStates)
        {
            if (!state.Transient || state.Completed || !state.Patrol || state.Patrol.m_Group != group) { continue; }
            HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(state.ProposalId);
            if (identity) { camps.HCPartyKilled(identity, body); }
            return;
        }
    }
}
// Expansion AI hook implementations live in HCXExpansionBridge.c.
