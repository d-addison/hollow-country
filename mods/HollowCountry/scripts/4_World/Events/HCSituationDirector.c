// HC-38 / #147/#148. One pinned survivor opportunity, carried by HC-19's
// schedule/store, NOT another module, scheduler, spawner or scenario engine.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:1120 IsServer;
// 1_Core/proto/EnDebug.c:96 Print. All remaining calls are existing HC ports.
// Only transition barriers save (HCSceneChainStore.Save: verified intent,
// backup/copy/readback); routine saves remain with the owner's HCSaveJob.
// Backup scene-chains.json with world/custody AND engine inventory. An unknown
// result never recreates a body, replenishes cargo or restarts this identity.

class HCSituationState
{
    int Version = 1;
    string Id;
    int StorySequence;
    int DueAt;
    int EndsAt;
    string Phase = "pending";
    string Outcome;
    string Lease;
    string Refusal;
}

// Fixed-size retained history survives HC-19 retirement of its source chain.
// Absent/null on old saves means no first opportunity has been issued yet.
modded class HCStoryProgress
{
    ref HCSituationState HCFirstSurvivor;
}

// Server-only binding to an EXISTING HC-10-owned survivor, never a client
// request. Select is read-only; Begin can request a verified emote only AFTER
// the intent barrier. End releases this observation binding, never the body,
// cargo or HC-10 reservation. The provider continues its ordinary lifecycle.
class HCSituationActorPort
{
    bool HCReady() { return false; }
    string HCRefusal() { return "SURVIVOR_PROVIDER_UNAVAILABLE"; }
    string HCSelect(HCSituationState opportunity) { return ""; }
    bool HCBegin(HCSituationState opportunity) { return false; }
    string HCObserve(HCSituationState opportunity) { return ""; }
    void HCEnd(HCSituationState opportunity) {}
}

class HCSituationActors
{
    protected static ref HCSituationActorPort s_Adapter;

    static void HCBind(HCSituationActorPort adapter) { s_Adapter = adapter; }
    static HCSituationActorPort HCGet()
    {
        if (s_Adapter) { return s_Adapter; }
        return new HCSituationActorPort;
    }
}

class HCSituationDirector
{
    protected ref HCSceneChainState m_State;
    protected ref HCSceneChainStore m_Store;
    protected ref HCSituationActorPort m_Actors;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected bool m_Enabled;
    protected bool m_Fault;
    protected bool m_Attempted;
    protected string m_Effective = "off";
    protected string m_Reason = "not_started";

    static bool HCValid(HCSituationState row, HCStoryProgress progress)
    {
        if (!row) { return true; }
        if (!progress || row.Version != 1 || !HCEventDirector.TextValid(row.Id, 48)) { return false; }
        if (row.StorySequence <= progress.LegacyThrough || row.StorySequence >= progress.NextSequence) { return false; }
        if (row.DueAt < 1 || row.EndsAt <= row.DueAt || row.EndsAt > 1000086400) { return false; }
        if (row.Refusal.Length() > 96 || row.Lease.Length() > 96) { return false; }
        if (row.Phase == "pending") { return row.Lease == "" && row.Outcome == ""; }
        if (row.Phase == "intent" || row.Phase == "active") { return HCEventDirector.TextValid(row.Lease, 96) && row.Outcome == ""; }
        if (row.Phase != "closed") { return false; }
        return row.Outcome == "dead" || row.Outcome == "departed" || row.Outcome == "unknown";
    }

    void HCReport()
    {
        string identity = "none";
        string phase = "none";
        string pinned = "0";
        if (m_State && m_State.Stories && m_State.Stories.HCFirstSurvivor)
        {
            identity = m_State.Stories.HCFirstSurvivor.Id;
            phase = m_State.Stories.HCFirstSurvivor.Phase;
            pinned = "1";
        }
        string line = "[HC Plan] HC-38 opportunity=" + identity + " phase=" + phase;
        line += " quest_ui=off state=" + m_Effective + " refusal=" + m_Reason;
        Print(line + " pinned=" + pinned + " count_cap=1 runtime=PENDING");
    }

    HCOperationalStatus HCStatus()
    {
        HCOperationalStatus status = new HCOperationalStatus;
        status.HCPublish(m_Effective, m_Reason);
        return status;
    }

    protected bool HCCommit()
    {
        if (m_Fault || !HCValid(m_State.Stories.HCFirstSurvivor, m_State.Stories) || !m_Store.Save(m_State))
        {
            m_Fault = true;
            m_Enabled = false;
            m_Effective = "refused";
            m_Reason = "SITUATION_STORE_UNCERTAIN";
            HCReport();
            return false;
        }
        HCReport();
        return true;
    }

    bool HCOpen(HCSceneChainState state, HCSceneChainStore store, bool enabled)
    {
        // Caller must close before reuse. A fault cannot be cleared in process.
        if (m_Enabled || m_Fault) { return false; }
        m_Effective = "off";
        m_Reason = "operator_off";
        if (!HCV2Admission.Admitted(enabled) || !GetGame() || !GetGame().IsServer()) { HCReport(); return false; }
        if (!state || !store || !state.Stories || !HCStoryPolicy.HCValid(state))
        {
            m_Effective = "refused";
            m_Reason = "SITUATION_STATE_INVALID";
            HCReport();
            return false;
        }
        if (!HCValid(state.Stories.HCFirstSurvivor, state.Stories))
        {
            m_Effective = "refused";
            m_Reason = "SITUATION_STATE_INVALID";
            HCReport();
            return false;
        }
        m_State = state;
        m_Store = store;
        m_Actors = HCSituationActors.HCGet();
        m_Enabled = true;
        m_Attempted = false;
        m_Effective = "refused";
        m_Reason = m_Actors.HCRefusal();
        if (m_Actors.HCReady()) { m_Effective = "ready"; m_Reason = "observed_actor_port_ready"; }
        HCSituationState restored = state.Stories.HCFirstSurvivor;
        // Restart never binds a replacement to an issued intent/active story.
        // Provider ownership is independent; no death or rescue is inferred.
        if (restored && (restored.Phase == "intent" || restored.Phase == "active"))
        {
            m_Actors.HCEnd(restored);
            return HCFinish("unknown");
        }
        HCReport();
        return true;
    }

    // Owner calls after HC-19's new arrival has been durably issued. The first
    // new identity pins this one content slice, even with zero connected players.
    // Legacy/completed chains cannot become a new survivor or replay cargo.
    bool HCOffer(HCSceneChain chain)
    {
        if (!m_Enabled || !chain || m_State.Stories.HCFirstSurvivor) { return false; }
        if (chain.Complete || chain.Cancelled || m_State.Chains.Find(chain) < 0) { return false; }
        if (chain.StorySequence <= m_State.Stories.LegacyThrough || chain.StorySequence >= m_State.Stories.NextSequence) { return false; }
        HCSituationState row = new HCSituationState;
        row.Id = chain.Id + "-survivor";
        row.StorySequence = chain.StorySequence;
        row.DueAt = chain.DueAt;
        row.EndsAt = chain.ExpiresAt;
        m_State.Stories.HCFirstSurvivor = row;
        return HCCommit();
    }

    protected bool HCFinish(string outcome)
    {
        HCSituationState row = m_State.Stories.HCFirstSurvivor;
        row.Phase = "closed";
        row.Outcome = outcome;
        if (!HCCommit()) { return false; }
        m_Actors.HCEnd(row);
        return true;
    }

    void HCStep(int now)
    {
        if (!m_Enabled || !GetGame() || !GetGame().IsServer()) { return; }
        HCSituationState row = m_State.Stories.HCFirstSurvivor;
        if (!row || row.Phase == "closed") { return; }
        m_Units.HCReset(1);
        m_Work.HCReset(1);
        if (!m_Units.HCTake(1) || !m_Work.HCContinue()) { return; }
        if (now < m_State.LastNow || now > 999000000) { return; }
        if (now >= row.EndsAt) { HCFinish("unknown"); return; }
        if (now < row.DueAt) { return; }
        if (row.Phase == "pending")
        {
            // One binding attempt per open, no hidden route/player scan loop.
            if (m_Attempted) { return; }
            m_Attempted = true;
            // Optional addon startup may follow the base scene owner. Resolve
            // its binding at the first due slice, after all modules started.
            m_Actors = HCSituationActors.HCGet();
            if (!m_Actors.HCReady())
            {
                m_Effective = "refused";
                m_Reason = m_Actors.HCRefusal();
                HCReport();
                return;
            }
            m_Effective = "ready";
            m_Reason = "observed_actor_port_ready";
            string lease = m_Actors.HCSelect(row);
            if (lease == "" || !HCWorldMaterializer.HCIdentity(lease))
            {
                m_Effective = "refused";
                m_Reason = m_Actors.HCRefusal();
                HCReport();
                return;
            }
            row.Lease = lease;
            row.Phase = "intent";
            if (!HCCommit()) { return; }
            if (!m_Actors.HCBegin(row)) { HCFinish("unknown"); return; }
            row.Phase = "active";
            HCCommit();
            return;
        }
        if (row.Phase != "active") { return; }
        if (!HCWorldMaterializer.HCIdentity(row.Lease)) { HCFinish("unknown"); return; }
        // Never accept client completion, inferred intervention or a timer as
        // rescue. The port may only report an actual native death/departure.
        string outcome = m_Actors.HCObserve(row);
        if (outcome == "dead" || outcome == "departed") { HCFinish(outcome); }
    }

    void HCClose()
    {
        if (m_State && m_State.Stories && m_Actors)
        {
            HCSituationState row = m_State.Stories.HCFirstSurvivor;
            if (row && (row.Phase == "intent" || row.Phase == "active"))
            {
                if (!m_Fault) { HCFinish("unknown"); }
                m_Actors.HCEnd(row);
            }
        }
        m_Enabled = false;
        m_Effective = "off";
        if (m_Fault) { m_Effective = "refused"; }
        else { m_Reason = "owner_closed"; }
        HCReport();
    }
}
