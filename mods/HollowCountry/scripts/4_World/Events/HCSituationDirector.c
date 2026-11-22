// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:917/926 map.Contains/Insert.
// HC-38/39/40, Wave 6 / #147/#146: five retained named profiles, one HC-19
// state/store, transition barrier and HC-10 lease validator. No new scheduler,
// routine save, actor/cargo owner or gameplay capability. Runtime PENDING.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:1120 IsServer;
// 3_Game/gameplay.c:636 GetGame; 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnScript.c:380 Count, :394 Find, :407 Insert; EnString.c:199 Length.
// Backup scene-chains.json with world/custody AND engine inventory.
// Pacing native evidence (same installed snapshot): Game.c:945 GetPlayers
// via HCPerfPlayers; Object.c:287/517 GetPosition/IsAlive;
// 1_Core/proto/EnConvert.c:210 vector.DistanceSq. No new engine API.

class HCSituationLimits
{
    static const int MAX_PROFILE_ROWS = 5;
    static const int PACING_RECEIPTS = 32;
    static const int PACING_PLAYERS = 16;
    static const int PACING_SPACING = 300;
    static const int PACING_DECAY = 900;
    static const int PACING_LEAD = 120;
    static const int PACING_ACTIVE = 2;
    static const float PACING_RADIUS_SQ = 1000000;
    static const float PACING_HEAT = 2;
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

// Sparse recent starts, not player identities. Prune only after both the
// activity reservation and the linear heat tail expire; no separate save file.
class HCSituationPacingReceipt
{
    string Id;
    vector Anchor;
    int StartedAt;
    int ActiveUntil;
    bool PendingStart; // additive: legacy receipts remain confirmed
}

modded class HCStoryProgress
{
    int HCPacingBeganAt;
    ref array<ref HCSituationPacingReceipt> HCPacing;
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
    // Existing detached proposal anchor, NOT live actor tracking. Providers may
    // override with their current observed leader position. Never infer a player
    // target or move a party to satisfy pacing. Materializer has <=24 leases.
    bool HCAnchor(string lease, out vector anchor)
    {
        HCWorldMaterializer materializer = HCWorldMaterializer.HCDebugGet();
        if (!materializer || materializer.HCDebugProposalCount() > 24) { return false; }
        for (int index = 0; index < 24 && index < materializer.HCDebugProposalCount(); index++)
        {
            HCDebugProposalRow proposal = materializer.HCDebugProposal(index);
            if (!proposal || proposal.Id != lease || proposal.State != "claimed") { continue; }
            anchor = proposal.Position;
            return HCEventRuntimePolicy.PositionValid(anchor);
        }
        return false;
    }
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
    bool EndPending;
    ref HCSituationState Opportunity;
    ref HCSituationActorPort Actors;
}

class HCSituationDirector
{
    protected ref HCWorldActivityCounters m_Activity = new HCWorldActivityCounters("steps rows due active started closed unknown refused checkpoint budget clock provider lease pacing begin identity source store");
    protected ref HCSceneChainState m_State;
    protected ref HCSceneChainStore m_Store;
    protected ref array<ref HCSituationProfileRow> m_Rows = new array<ref HCSituationProfileRow>;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected float m_ActivityLastTick = -1;
    protected int m_Cursor;
    protected int m_OfferCursor;
    protected bool m_Enabled;
    protected bool m_Fault;
    protected string m_Effective = "off";
    protected string m_Reason = "not_started";
    // Last printed receipt: the pending-row refusal repeats every step (096: 130 lines in 8 min).
    protected string m_LastReport;

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
        if (!progress || !HCPacingValid(progress) || !HCValid(progress.HCFirstSurvivor, progress)) { return false; }
        map<string, bool> profiles = new map<string, bool>();
        map<string, bool> identities = new map<string, bool>();
        map<string, bool> leases = new map<string, bool>();
        HCSituationState survivor = progress.HCFirstSurvivor;
        if (survivor)
        {
            if (survivor.Profile != "" && survivor.Profile != "survivor") { return false; }
            identities.Insert(survivor.Id, true);
            if (survivor.Lease != "") { leases.Insert(survivor.Lease, true); }
        }
        // Old JSON images have no additive array. Never require an initializer
        // to have survived native deserialization or infer a cooldown receipt.
        if (!progress.HCSituations) { return true; }
        if (progress.HCSituations.Count() >= HCSituationLimits.MAX_PROFILE_ROWS) { return false; }
        foreach (HCSituationState row : progress.HCSituations)
        {
            if (!row || !HCValid(row, progress) || !HCProfileValid(row.Profile) || row.Profile == "survivor") { return false; }
            if (profiles.Contains(row.Profile) || identities.Contains(row.Id)) { return false; }
            if (row.Lease != "" && leases.Contains(row.Lease)) { return false; }
            profiles.Insert(row.Profile, true);
            identities.Insert(row.Id, true);
            if (row.Lease != "") { leases.Insert(row.Lease, true); }
        }
        return true;
    }

    static int HCPacingNow()
    {
        int utc = HCGroupClock.Utc();
        if (utc < 1577836801) { return 0; }
        return utc - 1577836800;
    }

    static bool HCPacingValid(HCStoryProgress progress)
    {
        if (progress.HCPacingBeganAt < 0 || progress.HCPacingBeganAt > 999000000) { return false; }
        if (!progress.HCPacing) { return true; } // additive legacy image
        if (progress.HCPacing.Count() > HCSituationLimits.PACING_RECEIPTS) { return false; }
        map<string, bool> seen = new map<string, bool>;
        array<ref HCSituationPacingReceipt> receipts = progress.HCPacing;
        foreach (HCSituationPacingReceipt receipt : receipts)
        {
            if (!receipt || !HCEventDirector.TextValid(receipt.Id, 96) || seen.Contains(receipt.Id)) { return false; }
            if (!HCEventRuntimePolicy.PositionValid(receipt.Anchor)) { return false; }
            if (receipt.StartedAt < 1 || receipt.StartedAt > 999000000 || receipt.ActiveUntil < receipt.StartedAt || receipt.ActiveUntil > 1000086400) { return false; }
            seen.Insert(receipt.Id, true);
        }
        return true;
    }

    protected HCSituationPacingReceipt HCPacingFind(string identity)
    {
        if (!m_State.Stories.HCPacing) { return null; }
        array<ref HCSituationPacingReceipt> receipts = m_State.Stories.HCPacing;
        foreach (HCSituationPacingReceipt receipt : receipts)
        {
            if (receipt.Id == identity) { return receipt; }
        }
        return null;
    }

    // One candidate, <=16 living observers x <=32 receipts. No object scan,
    // RNG, player IDs, CE control or actor creation. Check EVERY nearby player:
    // the quietest member cannot admit more pressure for an already busy group.
    protected bool HCPacingAllows(vector anchor, int now, int dueAt = 0, string excluding = "")
    {
        if (!HCEventRuntimePolicy.PositionValid(anchor) || now < m_State.Stories.HCPacingBeganAt) { return false; }
        array<Man> players = HCPerfPlayers.HCGet();
        if (!players || players.Count() > HCSituationLimits.PACING_PLAYERS) { return false; }
        bool nearby = false;
        array<ref HCSituationPacingReceipt> receipts = m_State.Stories.HCPacing;
        for (int index = 0; index < 16 && index < players.Count(); index++)
        {
            Man observer = players[index];
            if (!observer || !observer.IsAlive()) { continue; }
            vector point = observer.GetPosition();
            if (vector.DistanceSq(point, anchor) > HCSituationLimits.PACING_RADIUS_SQ) { continue; }
            nearby = true;
            int active = 0;
            float heat = 0;
            int last = m_State.Stories.HCPacingBeganAt;
            if (receipts)
            {
                for (int recent = 0; recent < 32 && recent < receipts.Count(); recent++)
                {
                    HCSituationPacingReceipt receipt = receipts[recent];
                    if (receipt.Id == excluding) { continue; }
                    if (vector.DistanceSq(point, receipt.Anchor) > HCSituationLimits.PACING_RADIUS_SQ) { continue; }
                    if (receipt.StartedAt > now) { return false; }
                    if (receipt.StartedAt > last) { last = receipt.StartedAt; }
                    if (now < receipt.ActiveUntil) { active++; }
                    int age = now - receipt.StartedAt;
                    if (age < HCSituationLimits.PACING_SPACING) { return false; }
                    if (age < HCSituationLimits.PACING_DECAY) { heat += 1.0 - age / 900.0; }
                }
            }
            if (active >= HCSituationLimits.PACING_ACTIVE || heat + 1 > HCSituationLimits.PACING_HEAT) { return false; }
            // Normal eligible offers settle for two minutes. After 15 quiet
            // minutes the next eligible offer skips that wait, never its native
            // eligibility, DueAt, ownership, visibility or safety checks.
            if (dueAt > 0 && now - last < HCSituationLimits.PACING_DECAY && now - dueAt < HCSituationLimits.PACING_LEAD) { return false; }
        }
        return nearby;
    }

    protected bool HCPacingReserve(string identity, vector anchor, int now, int until)
    {
        if (!m_State.Stories.HCPacing) { m_State.Stories.HCPacing = new array<ref HCSituationPacingReceipt>; }
        array<ref HCSituationPacingReceipt> receipts = m_State.Stories.HCPacing;
        for (int index = receipts.Count() - 1; index >= 0; index--)
        {
            HCSituationPacingReceipt prior = receipts[index];
            if (now >= prior.ActiveUntil && now - prior.StartedAt >= HCSituationLimits.PACING_DECAY) { receipts.Remove(index); }
        }
        if (receipts.Count() >= HCSituationLimits.PACING_RECEIPTS) { return false; }
        HCSituationPacingReceipt receipt = new HCSituationPacingReceipt;
        receipt.Id = identity;
        receipt.Anchor = anchor;
        receipt.StartedAt = now;
        receipt.ActiveUntil = until;
        receipts.Insert(receipt);
        return true;
    }

    bool HCExternalAvailable() { return m_Enabled && !m_Fault; }

    // Refusal releases only an unstarted reservation. Completed starts retain
    // their spacing/heat tail. RequestCheckpoint queues behind an in-flight
    // immutable image, so cancellation and confirmation cannot be dropped.
    void HCCancelExternal(string identity)
    {
        if (!m_Enabled || m_Fault || !m_Store.HCCheckpointHealthy()) { return; }
        HCSituationPacingReceipt receipt = HCPacingFind(identity);
        if (!receipt || !receipt.PendingStart) { return; }
        m_State.Stories.HCPacing.RemoveItem(receipt);
        HCCommit();
    }

    // A finished or cancelled confirmed start stops counting as active at once;
    // StartedAt is kept, so the spacing/decay tail still applies.
    void HCEndExternal(string identity)
    {
        if (!m_Enabled || m_Fault || !m_Store.HCCheckpointHealthy()) { return; }
        HCSituationPacingReceipt receipt = HCPacingFind(identity);
        if (!receipt || receipt.PendingStart) { return; }
        int now = HCPacingNow();
        if (now < receipt.StartedAt || now >= receipt.ActiveUntil) { return; }
        receipt.ActiveUntil = now;
        HCCommit();
    }

    // External HC owners retry the SAME stable identity after the shared store
    // barrier drains. Provider ownership/journals still prevent spawn replay.
    bool HCReserveExternal(string identity, vector anchor, int lifetimeSeconds)
    {
        if (!m_Enabled || m_Fault || !HCEventDirector.TextValid(identity, 96)) { return false; }
        if (m_Store.HCBarrierPending() || !m_Store.HCCheckpointHealthy()) { return false; }
        int now = HCPacingNow();
        if (now < 1 || now < m_State.LastNow || lifetimeSeconds < 1 || lifetimeSeconds > 86400) { return false; }
        HCSituationPacingReceipt retained = HCPacingFind(identity);
        if (retained)
        {
            if (now < retained.StartedAt) { return false; }
            if (now < retained.ActiveUntil)
            {
                // Restoring an already issued scene/event remains the native
                // owner's decision; its durable identity prevents replay.
                if (!retained.PendingStart) { return HCPacingAllows(anchor, now, 0, identity); }
                if (!HCPacingAllows(anchor, now, 0, identity)) { return false; }
                if (vector.DistanceSq(retained.Anchor, anchor) > 10000)
                {
                    retained.Anchor = anchor;
                    HCCommit();
                    return false;
                }
                return true;
            }
            if (now - retained.StartedAt < HCSituationLimits.PACING_DECAY) { return false; }
        }
        if (!HCPacingAllows(anchor, now) || !HCPacingReserve(identity, anchor, now, now + lifetimeSeconds)) { return false; }
        HCSituationPacingReceipt pending = HCPacingFind(identity);
        pending.PendingStart = true;
        HCCommit();
        return false; // durable reservation first, provider only on a later tick
    }

    // Stamp actual success too: checkpoint latency/retries must never make the
    // next start's spacing run from an old reservation rather than the start.
    void HCConfirmExternal(string identity)
    {
        if (!m_Enabled || m_Fault || !m_Store.HCCheckpointHealthy()) { return; }
        HCSituationPacingReceipt receipt = HCPacingFind(identity);
        int now = HCPacingNow();
        if (!receipt || !receipt.PendingStart || now < receipt.StartedAt) { return; }
        receipt.PendingStart = false;
        int lifetime = receipt.ActiveUntil - receipt.StartedAt;
        receipt.StartedAt = now;
        receipt.ActiveUntil = now + lifetime;
        HCCommit();
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
        // HC-1 has a fixed lifecycle vocabulary; waiting for gameplay input
        // leaves the director running. The situation/activity line is explicit.
        if (m_Effective == "needs_player") { m_Status.HCPublish("ready", "needs_player"); }
        else { m_Status.HCPublish(m_Effective, m_Reason); }
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
        line += " pinned=" + pinned + " count_cap=1 runtime=PENDING";
        if (line == m_LastReport) { return; }
        m_LastReport = line;
        Print("" + line);
    }

    // Startup readiness is not permanent: the live-party provider settles later,
    // and no-player boots cannot materialize the parties this feature borrows.
    protected void HCRefreshProvider()
    {
        if (!m_Enabled || m_Fault) { return; }
        HCSituationActorPort actors = HCSituationActors.HCForProfile("survivor");
        m_Effective = "refused";
        m_Reason = actors.HCRefusal();
        if (actors.HCReady())
        {
            m_Effective = "ready";
            m_Reason = actors.HCRefusal();
        }
        else
        {
            m_Reason = actors.HCRefusal();
            if (m_Reason == "SITUATION_NEEDS_PLAYER") { m_Effective = "needs_player"; }
        }
        HCReport();
    }

    HCOperationalStatus HCStatus() { return m_Status; }

    protected bool HCCommit()
    {
        if (m_Fault || !HCHistoryValid(m_State.Stories) || m_Store.HCRequestCheckpoint(m_State) < 0)
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
            HCModuleReadiness.HCRegisterUse("Events", "situation_started");
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
        m_OfferCursor = 0;
        // Validated retained profiles are unique; build once before binding slots.
        map<string, HCSituationState> opportunities = new map<string, HCSituationState>;
        if (state.Stories.HCSituations)
        {
            foreach (HCSituationState retained : state.Stories.HCSituations) { opportunities.Insert(retained.Profile, retained); }
        }
        foreach (HCSituationProfileRow slot : m_Rows)
        {
            slot.Attempted = false;
            slot.Opportunity = null;
            slot.Actors = HCSituationActors.HCForProfile(slot.Profile);
            if (slot.Profile == "survivor") { slot.Opportunity = state.Stories.HCFirstSurvivor; }
            else { slot.Opportunity = opportunities.Get(slot.Profile); }
        }
        HCRefreshProvider();
        // A crash never rebinds an issued intent/active story to a replacement.
        foreach (HCSituationProfileRow restored : m_Rows)
        {
            if (restored.Opportunity && (restored.Opportunity.Phase == "intent" || restored.Opportunity.Phase == "active"))
            {
                if (!HCFinish(restored, "unknown")) { return false; }
            }
        }
        if (m_State.Stories.HCPacingBeganAt == 0)
        {
            m_State.Stories.HCPacingBeganAt = HCPacingNow();
            if (m_State.Stories.HCPacingBeganAt < 1 || !HCCommit()) { return false; }
        }
        Print("[HC Situations] pacing radius_m=1000 active_cap=2 heat_cap=2 decay_s=900 spacing_s=300 quiet_s=900 lead_s=120 receipts=32 players=16 anchor=proposal runtime=PENDING");
        HCReport();
        return true;
    }

    bool HCOffer(HCSceneChain chain)
    {
        if (!m_Enabled || !chain || m_Store.HCBarrierPending()) { return false; }
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
                m_Activity.HCRefuse("provider");
                if (slot.Profile == "survivor") { HCRefreshProvider(); }
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
        HCSituationPacingReceipt pacing = HCPacingFind(slot.Opportunity.Id);
        int now = HCPacingNow();
        if (pacing && slot.Opportunity.Phase == "intent") { m_State.Stories.HCPacing.RemoveItem(pacing); }
        else if (pacing && now >= pacing.StartedAt && now < pacing.ActiveUntil) { pacing.ActiveUntil = now; }
        slot.Opportunity.Phase = "closed";
        slot.Opportunity.Outcome = outcome;
        if (!HCCommit()) { return false; }
        m_Activity.HCHit("closed");
        if (outcome == "unknown") { m_Activity.HCHit("unknown"); }
        slot.EndPending = true;
        return true;
    }

    protected void HCStepRow(HCSituationProfileRow slot, int now)
    {
        HCSituationState row = slot.Opportunity;
        if (!row || row.Phase == "closed") { return; }
        m_Activity.HCHit("rows");
        if (now >= row.DueAt) { m_Activity.HCHit("due"); }
        if (row.Phase == "active") { m_Activity.HCHit("active"); }
        if (now >= row.EndsAt) { HCFinish(slot, "unknown"); return; }
        if (!slot.Enabled || now < row.DueAt) { return; }
        if (row.Phase == "pending")
        {
            if (slot.Attempted) { return; }
            slot.Actors = HCSituationActors.HCForProfile(slot.Profile);
            if (!slot.Actors.HCReady())
            {
                m_Activity.HCRefuse("provider");
                if (slot.Profile == "survivor") { HCRefreshProvider(); }
                return;
            }
            string lease = slot.Actors.HCSelect(row);
            if (lease == "" || !HCWorldMaterializer.HCIdentity(lease))
            {
                m_Activity.HCRefuse("lease");
                if (slot.Profile == "survivor")
                {
                    m_Effective = "ready";
                    m_Reason = slot.Actors.HCRefusal();
                    HCReport();
                }
                return;
            }
            vector anchor;
            if (!slot.Actors.HCAnchor(lease, anchor) || !HCPacingAllows(anchor, now, row.DueAt)) { m_Activity.HCRefuse("pacing"); return; }
            if (!HCPacingReserve(row.Id, anchor, now, row.EndsAt)) { m_Activity.HCRefuse("pacing"); return; }
            slot.Attempted = true;
            row.Lease = lease;
            row.Phase = "intent";
            if (slot.Profile == "survivor") { m_Effective = "ready"; m_Reason = "observed_actor_port_ready"; }
            HCCommit();
            return; // intent must commit before the retained actor can begin

        }
        if (row.Phase == "intent" && slot.Attempted)
        {
            HCSituationPacingReceipt reserved = HCPacingFind(row.Id);
            vector liveAnchor;
            if (!reserved || !slot.Actors || !slot.Actors.HCAnchor(row.Lease, liveAnchor)) { m_Activity.HCRefuse("pacing"); return; }
            if (!HCPacingAllows(liveAnchor, now, 0, row.Id)) { m_Activity.HCRefuse("pacing"); return; }
            reserved.Anchor = liveAnchor;
            // HCBegin re-resolves this exact lease and checks current native
            // ownership, exclusions and living roster; selection is never replayed.
            if (!slot.Actors || !slot.Actors.HCReady() || !slot.Actors.HCBegin(row)) { m_Activity.HCRefuse("begin"); HCFinish(slot, "unknown"); return; }
            HCSituationPacingReceipt started = HCPacingFind(row.Id);
            if (started) { started.StartedAt = now; }
            m_Activity.HCHit("started");
            HCModuleReadiness.HCUse("Events", "situation_started");
            row.Phase = "active";
            HCCommit();
            return;
        }
        if (row.Phase != "active") { return; }
        if (!HCWorldMaterializer.HCIdentity(row.Lease)) { m_Activity.HCRefuse("identity"); HCFinish(slot, "unknown"); return; }
        string outcome = slot.Actors.HCObserve(row);
        if (outcome == "dead" || outcome == "departed") { HCFinish(slot, outcome); }
    }

    void HCActivityStep(int now, string prerequisite = "")
    {
        // Also called by the event owner when scene prerequisites refuse work.
        // Native Game.c:914 GetTickTime; only a due summary scans the five rows.
        if (prerequisite != "") { m_Activity.HCRefuse(prerequisite); }
        if (GetGame() && GetGame().IsServer())
        {
            float activityNow = GetGame().GetTickTime();
            if (m_ActivityLastTick >= 0 && m_Activity.HCDue(activityNow - m_ActivityLastTick))
            {
                int dueRows;
                int activeRows;
                foreach (HCSituationProfileRow activitySlot : m_Rows)
                {
                    if (!activitySlot.Opportunity || activitySlot.Opportunity.Phase == "closed") { continue; }
                    if (now >= activitySlot.Opportunity.DueAt) { dueRows++; }
                    if (activitySlot.Opportunity.Phase == "active") { activeRows++; }
                }
                string activityState = " due=" + dueRows.ToString() + " active=" + activeRows.ToString();
                activityState += " state=" + m_Effective + " reason=" + m_Reason;
                m_Activity.HCLog("[HC Situations]", activityState);
            }
            m_ActivityLastTick = activityNow;
        }
    }

    void HCStep(int now)
    {
        HCRefreshProvider();
        HCActivityStep(now);
        if (!m_Enabled || !GetGame() || !GetGame().IsServer()) { return; }
        m_Activity.HCHit("steps");
        m_Store.HCPumpCheckpoint();
        if (!m_Store.HCCheckpointHealthy()) { m_Fault = true; m_Enabled = false; m_Effective = "refused"; m_Reason = "SITUATION_STORE_UNCERTAIN"; HCReport(); return; }
        if (m_Store.HCBarrierPending()) { m_Activity.HCRefuse("checkpoint"); return; }
        foreach (HCSituationProfileRow ended : m_Rows)
        {
            if (!ended.EndPending) { continue; }
            ended.EndPending = false;
            if (ended.Actors) { ended.Actors.HCEnd(ended.Opportunity); }
            return;
        }
        if (now < m_State.LastNow || now > 999000000) { m_Activity.HCRefuse("clock"); return; }
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
            // Profile iteration wraps at five; it cannot rotate a chain catalog.
            // Keep an independent bounded cursor so a terminal chain cannot starve
            // a later eligible retained chain, including after a server upgrade.
            m_OfferCursor = m_OfferCursor % m_State.Chains.Count();
            HCOffer(m_State.Chains[m_OfferCursor]);
            m_OfferCursor++;
            if (m_Store.HCBarrierPending()) { return; }
        }
        // Find one retained nonterminal row; bounded by the five-profile cap.
        // Empty/off rows cost no actor calls; survivor-only cadence is unchanged.
        for (int index = 0; index < m_Rows.Count(); index++)
        {
            if (m_Cursor >= m_Rows.Count()) { m_Cursor = 0; }
            HCSituationProfileRow slot = m_Rows[m_Cursor];
            m_Cursor++;
            if (!slot.Opportunity || slot.Opportunity.Phase == "closed") { continue; }
            if (!m_Units.HCTake(1) || !m_Work.HCContinue()) { m_Activity.HCRefuse("budget"); return; }
            HCStepRow(slot, now);
            return;
        }
    }

    void HCClose()
    {
        // Shutdown is the explicit synchronous flush boundary. Persist closed
        // receipts before releasing live actor bindings; never replay an intent.
        foreach (HCSituationProfileRow closing : m_Rows)
        {
            HCSituationState row = closing.Opportunity;
            if (row && closing.Actors && (row.Phase == "intent" || row.Phase == "active") && !m_Fault)
            {
                HCFinish(closing, "unknown");
            }
        }
        if (m_Store && !m_Store.HCFlushCheckpoint()) { m_Fault = true; }
        foreach (HCSituationProfileRow slot : m_Rows)
        {
            if (slot.Actors && slot.Opportunity && (slot.EndPending || slot.Opportunity.Phase == "intent" || slot.Opportunity.Phase == "active"))
            {
                slot.Actors.HCEnd(slot.Opportunity);
            }
            slot.EndPending = false;
            slot.Actors = null;
        }
        m_Enabled = false;
        m_Effective = "off";
        if (m_Fault) { m_Effective = "refused"; }
        else { m_Reason = "owner_closed"; }
        HCReport();
    }
}
