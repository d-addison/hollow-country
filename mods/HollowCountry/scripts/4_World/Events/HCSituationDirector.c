// HC-38/39/40, Wave 6 / #147/#146: five retained named profiles, one HC-19
// state/store, transition barrier and HC-10 lease validator. No new scheduler,
// routine save, actor/cargo owner or gameplay capability. Runtime PENDING.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:1120 IsServer;
// 3_Game/gameplay.c:636 GetGame; 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnScript.c:380 Count, :394 Find, :407 Insert; EnString.c:199 Length.
// Backup scene-chains.json with world/custody AND engine inventory.

class HCSituationLimits
{
    static const int MAX_PROFILE_ROWS = 5;
}

class HCSituationState
{
    int Version = 1;
    // Empty only for the legacy HCFirstSurvivor. No new version/int migration:
    // absent additive strings/arrays mean legacy; Version=0 is always refused.
    string Profile;
    string Id;
    int StorySequence;
    int DueAt;
    int EndsAt;
    string Phase = "pending";
    string Outcome;
    string Lease;
    string Refusal;
}

modded class HCStoryProgress
{
    ref HCSituationState HCFirstSurvivor;
    ref array<ref HCSituationState> HCSituations;
}

// Trusted server binding. Read-only selection precedes the durable intent;
// Begin/Observe/End never transfer ownership of HC-10 bodies or cargo.
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
    protected static ref HCSituationActorPort s_Raid;
    protected static ref HCSituationActorPort s_Transit;
    protected static ref HCSituationActorPort s_Unavailable = new HCSituationActorPort;

    static void HCBind(HCSituationActorPort adapter) { s_Adapter = adapter; }
    static void HCBindRaid(HCSituationActorPort adapter) { s_Raid = adapter; }
    static void HCBindTransit(HCSituationActorPort adapter) { s_Transit = adapter; }
    static HCSituationActorPort HCGet() { return HCForProfile("survivor"); }
    static HCSituationActorPort HCForProfile(string profile)
    {
        if (profile == "survivor" && s_Adapter) { return s_Adapter; }
        if ((profile == "raid" || profile == "column") && s_Raid) { return s_Raid; }
        if ((profile == "roadside-position" || profile == "threatened-exodus") && s_Transit) { return s_Transit; }
        return s_Unavailable;
    }
}

// Scene owner publishes its EXACT live state/store after HC-19 opens and clears
// before stopping. Never open another store over the same path. Missing binding
// is a named refusal, not authority to synthesize a new world or story clock.
class HCSituationSource
{
    protected static ref HCSceneChainState s_State;
    protected static ref HCSceneChainStore s_Store;
    static void HCBind(HCSceneChainState state, HCSceneChainStore store) { s_State = state; s_Store = store; }
    static void HCClear(HCSceneChainState state)
    {
        if (!s_State || s_State != state) { return; }
        HCEventModule.HCSourceClosing();
        s_State = null;
        s_Store = null;
    }
    static HCSceneChainState HCState() { return s_State; }
    static HCSceneChainStore HCStore() { return s_Store; }
}

class HCSituationProfileRow
{
    string Profile;
    bool Enabled;
    int LifetimeSeconds;
    bool Attempted;
    ref HCSituationState Opportunity;
    ref HCSituationActorPort Actors;
}

class HCSituationDirector
{
    protected ref HCSceneChainState m_State;
    protected ref HCSceneChainStore m_Store;
    protected ref array<ref HCSituationProfileRow> m_Rows = new array<ref HCSituationProfileRow>;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected int m_Cursor;
    protected bool m_Enabled;
    protected bool m_Fault;
    protected string m_Effective = "off";
    protected string m_Reason = "not_started";

    static bool HCProfileValid(string profile)
    {
        return profile == "survivor" || profile == "raid" || profile == "column" || profile == "roadside-position" || profile == "threatened-exodus";
    }

    static bool HCValid(HCSituationState row, HCStoryProgress progress)
    {
        if (!row) { return true; }
        if (!progress || row.Version != 1 || !HCEventDirector.TextValid(row.Id, 48)) { return false; }
        if (row.Profile != "" && !HCProfileValid(row.Profile)) { return false; }
        if (row.StorySequence <= progress.LegacyThrough || row.StorySequence >= progress.NextSequence) { return false; }
        if (row.DueAt < 1 || row.EndsAt <= row.DueAt || row.EndsAt > 1000086400) { return false; }
        if (row.Refusal.Length() > 96 || row.Lease.Length() > 96) { return false; }
        if (row.Phase == "pending") { return row.Lease == "" && row.Outcome == ""; }
        if (row.Phase == "intent" || row.Phase == "active") { return HCEventDirector.TextValid(row.Lease, 96) && row.Outcome == ""; }
        if (row.Phase != "closed") { return false; }
        return row.Outcome == "dead" || row.Outcome == "departed" || row.Outcome == "unknown";
    }

    // Native boot 076: the JSON-loaded first survivor came back as a fully
    // zero-filled row. It has no identity, phase, lease or times, so it is
    // absent; a version-0 row carrying any state is still refused.
    static bool HCZeroFilled(HCSituationState row)
    {
        if (!row || row.Version != 0 || row.StorySequence != 0 || row.DueAt != 0 || row.EndsAt != 0) { return false; }
        return row.Profile == "" && row.Id == "" && row.Phase == "" && row.Outcome == "" && row.Lease == "" && row.Refusal == "";
    }

    static bool HCHistoryValid(HCStoryProgress progress)
    {
        if (!progress || !HCValid(progress.HCFirstSurvivor, progress)) { return false; }
        array<string> profiles = new array<string>();
        array<string> identities = new array<string>();
        array<string> leases = new array<string>();
        HCSituationState survivor = progress.HCFirstSurvivor;
        if (survivor)
        {
            if (survivor.Profile != "" && survivor.Profile != "survivor") { return false; }
            identities.Insert(survivor.Id);
            if (survivor.Lease != "") { leases.Insert(survivor.Lease); }
        }
        // Old JSON images have no additive array. Never require an initializer
        // to have survived native deserialization or infer a cooldown receipt.
        if (!progress.HCSituations) { return true; }
        if (progress.HCSituations.Count() >= HCSituationLimits.MAX_PROFILE_ROWS) { return false; }
        foreach (HCSituationState row : progress.HCSituations)
        {
            if (!row || !HCValid(row, progress) || !HCProfileValid(row.Profile) || row.Profile == "survivor") { return false; }
            if (profiles.Find(row.Profile) >= 0 || identities.Find(row.Id) >= 0) { return false; }
            if (row.Lease != "" && leases.Find(row.Lease) >= 0) { return false; }
            profiles.Insert(row.Profile);
            identities.Insert(row.Id);
            if (row.Lease != "") { leases.Insert(row.Lease); }
        }
        return true;
    }

    protected void HCAddProfile(string profile)
    {
        if (m_Rows.Count() >= HCSituationLimits.MAX_PROFILE_ROWS || HCFind(profile)) { return; }
        HCSituationProfileRow slot = new HCSituationProfileRow;
        slot.Profile = profile;
        slot.Enabled = true;
        m_Rows.Insert(slot);
    }

    HCSituationProfileRow HCFind(string profile)
    {
        foreach (HCSituationProfileRow slot : m_Rows)
        {
            if (slot.Profile == profile) { return slot; }
        }
        return null;
    }

    int HCCount() { return m_Rows.Count(); }

    bool HCEnableProfile(string profile, bool enabled, int lifetimeSeconds)
    {
        HCSituationProfileRow slot = HCFind(profile);
        if (!slot || lifetimeSeconds < 0 || lifetimeSeconds > 3600) { return false; }
        slot.Enabled = enabled;
        slot.LifetimeSeconds = lifetimeSeconds;
        return true;
    }

    void HCReport()
    {
        m_Status.HCPublish(m_Effective, m_Reason);
        string identity = "none";
        string phase = "none";
        string pinned = "0";
        if (m_State && m_State.Stories && m_State.Stories.HCFirstSurvivor)
        {
            identity = m_State.Stories.HCFirstSurvivor.Id;
            phase = m_State.Stories.HCFirstSurvivor.Phase;
            pinned = "1";
        }
        // Preserve the first-survivor receipt byte for byte, including its cap.
        string line = "[HC Plan] HC-38 opportunity=" + identity + " phase=" + phase;
        line += " quest_ui=off state=" + m_Effective + " refusal=" + m_Reason;
        Print(line + " pinned=" + pinned + " count_cap=1 runtime=PENDING");
    }

    HCOperationalStatus HCStatus() { return m_Status; }

    protected bool HCCommit()
    {
        if (m_Fault || !HCHistoryValid(m_State.Stories) || !m_Store.Save(m_State))
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

    protected void HCEnsureRows()
    {
        if (m_Rows.Count() == 0)
        {
            HCAddProfile("survivor");
            HCAddProfile("raid");
            HCAddProfile("column");
            HCAddProfile("roadside-position");
            HCAddProfile("threatened-exodus");
        }
    }

    // Wave 16: the scene owner binds the shared source in ITS OnStart, which runs
    // after this module's OnStart (registry order). The module resolves the source
    // once on its first tick, so at start the director is started and waiting by
    // design, not refused. A missing source on that first tick is then refused by
    // name through HCOpen. Requested is the HC-1 pending state; it never claims
    // a loaded/running director. Operator-off and non-server stay off.
    void HCDeferSource(bool enabled)
    {
        if (m_Enabled || m_Fault) { return; }
        HCEnsureRows();
        m_Effective = "off";
        m_Reason = "operator_off";
        if (!HCV2Admission.Admitted(enabled) || !GetGame() || !GetGame().IsServer()) { HCReport(); return; }
        m_Effective = "requested";
        m_Reason = "situation_source_pending";
        HCReport();
    }

    // True while the director owns the bound source and only the actor provider
    // (the optional Expansion AI addon) is missing: offers wait, nothing is stuck.
    bool HCProviderPending() { return m_Enabled && !m_Fault && m_Effective == "refused"; }

    bool HCOpen(HCSceneChainState state, HCSceneChainStore store, bool enabled)
    {
        if (m_Enabled || m_Fault) { return false; }
        HCEnsureRows();
        m_Effective = "off";
        m_Reason = "operator_off";
        if (!HCV2Admission.Admitted(enabled) || !GetGame() || !GetGame().IsServer()) { HCReport(); return false; }
        m_Effective = "refused";
        m_Reason = "SITUATION_SOURCE_UNAVAILABLE";
        if (!state || !store) { HCReport(); return false; }
        if (state.Stories && HCZeroFilled(state.Stories.HCFirstSurvivor)) { state.Stories.HCFirstSurvivor = null; }
        if (!state.Stories || !HCStoryPolicy.HCValid(state) || !HCHistoryValid(state.Stories))
        {
            m_Reason = "SITUATION_STATE_INVALID";
            HCReport();
            return false;
        }
        m_State = state;
        m_Store = store;
        m_Enabled = true;
        m_Cursor = 0;
        foreach (HCSituationProfileRow slot : m_Rows)
        {
            slot.Attempted = false;
            slot.Opportunity = null;
            slot.Actors = HCSituationActors.HCForProfile(slot.Profile);
            if (slot.Profile == "survivor") { slot.Opportunity = state.Stories.HCFirstSurvivor; }
            else if (state.Stories.HCSituations)
            {
                foreach (HCSituationState retained : state.Stories.HCSituations)
                {
                    if (retained.Profile == slot.Profile) { slot.Opportunity = retained; }
                }
            }
        }
        HCSituationActorPort survivorActors = HCFind("survivor").Actors;
        m_Reason = survivorActors.HCRefusal();
        if (survivorActors.HCReady()) { m_Effective = "ready"; m_Reason = "observed_actor_port_ready"; }
        // A crash never rebinds an issued intent/active story to a replacement.
        foreach (HCSituationProfileRow restored : m_Rows)
        {
            if (restored.Opportunity && (restored.Opportunity.Phase == "intent" || restored.Opportunity.Phase == "active"))
            {
                if (!HCFinish(restored, "unknown")) { return false; }
            }
        }
        HCReport();
        return true;
    }

    bool HCOffer(HCSceneChain chain)
    {
        if (!m_Enabled || !chain) { return false; }
        if (chain.Complete || chain.Cancelled || m_State.Chains.Find(chain) < 0) { return false; }
        if (chain.StorySequence <= m_State.Stories.LegacyThrough || chain.StorySequence >= m_State.Stories.NextSequence) { return false; }
        bool changed = false;
        foreach (HCSituationProfileRow slot : m_Rows)
        {
            if (!slot.Enabled || slot.Opportunity) { continue; }
            // One durable row per profile: a refused port must leave that
            // history unused. Resolve after addon startup, before any save.
            slot.Actors = HCSituationActors.HCForProfile(slot.Profile);
            if (!slot.Actors.HCReady())
            {
                if (slot.Profile == "survivor" && (m_Effective != "refused" || m_Reason != slot.Actors.HCRefusal()))
                {
                    m_Effective = "refused";
                    m_Reason = slot.Actors.HCRefusal();
                    HCReport();
                }
                continue;
            }
            HCSituationState row = new HCSituationState;
            row.Profile = slot.Profile;
            row.Id = chain.Id + "-" + slot.Profile;
            // HC-40's established durable suffixes are roadside/exodus.
            if (slot.Profile == "roadside-position") { row.Id = chain.Id + "-roadside"; }
            if (slot.Profile == "threatened-exodus") { row.Id = chain.Id + "-exodus"; }
            row.StorySequence = chain.StorySequence;
            row.DueAt = chain.DueAt;
            row.EndsAt = chain.ExpiresAt;
            if (slot.LifetimeSeconds > 0 && row.EndsAt - row.DueAt > slot.LifetimeSeconds) { row.EndsAt = row.DueAt + slot.LifetimeSeconds; }
            slot.Opportunity = row;
            if (slot.Profile == "survivor") { m_State.Stories.HCFirstSurvivor = row; }
            else
            {
                if (!m_State.Stories.HCSituations) { m_State.Stories.HCSituations = new array<ref HCSituationState>(); }
                m_State.Stories.HCSituations.Insert(row);
            }
            changed = true;
        }
        if (!changed) { return false; }
        return HCCommit();
    }

    protected bool HCFinish(HCSituationProfileRow slot, string outcome)
    {
        slot.Opportunity.Phase = "closed";
        slot.Opportunity.Outcome = outcome;
        if (!HCCommit()) { return false; }
        slot.Actors.HCEnd(slot.Opportunity);
        return true;
    }

    protected void HCStepRow(HCSituationProfileRow slot, int now)
    {
        HCSituationState row = slot.Opportunity;
        if (!row || row.Phase == "closed") { return; }
        if (now >= row.EndsAt) { HCFinish(slot, "unknown"); return; }
        if (!slot.Enabled || now < row.DueAt) { return; }
        if (row.Phase == "pending")
        {
            if (slot.Attempted) { return; }
            slot.Actors = HCSituationActors.HCForProfile(slot.Profile);
            if (!slot.Actors.HCReady())
            {
                if (slot.Profile == "survivor")
                {
                    m_Effective = "refused";
                    m_Reason = slot.Actors.HCRefusal();
                    HCReport();
                }
                return;
            }
            string lease = slot.Actors.HCSelect(row);
            if (lease == "" || !HCWorldMaterializer.HCIdentity(lease))
            {
                if (slot.Profile == "survivor")
                {
                    m_Effective = "refused";
                    m_Reason = slot.Actors.HCRefusal();
                    HCReport();
                }
                return;
            }
            slot.Attempted = true;
            row.Lease = lease;
            row.Phase = "intent";
            if (slot.Profile == "survivor") { m_Effective = "ready"; m_Reason = "observed_actor_port_ready"; }
            if (!HCCommit()) { return; }
            if (!slot.Actors.HCBegin(row)) { HCFinish(slot, "unknown"); return; }
            row.Phase = "active";
            HCCommit();
            return;
        }
        if (row.Phase != "active") { return; }
        if (!HCWorldMaterializer.HCIdentity(row.Lease)) { HCFinish(slot, "unknown"); return; }
        string outcome = slot.Actors.HCObserve(row);
        if (outcome == "dead" || outcome == "departed") { HCFinish(slot, outcome); }
    }

    void HCStep(int now)
    {
        if (!m_Enabled || !GetGame() || !GetGame().IsServer()) { return; }
        if (now < m_State.LastNow || now > 999000000) { return; }
        m_Units.HCReset(1);
        m_Work.HCReset(1);
        // A live provider may settle after HC-19's one startup offer. Revisit
        // one of its bounded retained chains; unused profiles alone can write.
        // Closed history is never refilled and an unready port performs no save.
        bool needsOffer = false;
        array<ref HCSituationProfileRow> waitingRows = m_Rows;
        foreach (HCSituationProfileRow waiting : waitingRows)
        {
            if (waiting.Enabled && !waiting.Opportunity) { needsOffer = true; }
        }
        if (needsOffer && m_State.Chains && m_State.Chains.Count() > 0)
        {
            HCOffer(m_State.Chains[m_Cursor % m_State.Chains.Count()]);
        }
        // Find one retained nonterminal row; bounded by the five-profile cap.
        // Empty/off rows cost no actor calls; survivor-only cadence is unchanged.
        for (int index = 0; index < m_Rows.Count(); index++)
        {
            if (m_Cursor >= m_Rows.Count()) { m_Cursor = 0; }
            HCSituationProfileRow slot = m_Rows[m_Cursor];
            m_Cursor++;
            if (!slot.Opportunity || slot.Opportunity.Phase == "closed") { continue; }
            if (!m_Units.HCTake(1) || !m_Work.HCContinue()) { return; }
            HCStepRow(slot, now);
            return;
        }
    }

    void HCClose()
    {
        // Clear bindings after a single release even when a close barrier fails.
        foreach (HCSituationProfileRow slot : m_Rows)
        {
            HCSituationState row = slot.Opportunity;
            if (row && slot.Actors && (row.Phase == "intent" || row.Phase == "active"))
            {
                bool ended = false;
                if (!m_Fault) { ended = HCFinish(slot, "unknown"); }
                if (!ended) { slot.Actors.HCEnd(row); }
            }
            slot.Actors = null;
        }
        m_Enabled = false;
        m_Effective = "off";
        if (m_Fault) { m_Effective = "refused"; }
        else { m_Reason = "owner_closed"; }
        HCReport();
    }
}
