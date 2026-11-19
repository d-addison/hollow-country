// HC-49 / #149 -> HC-15/48 bounded observations -> HC-19 issued story identity.
// Native evidence under ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/:
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnDebug.c:96 Print;
// EnScript.c:380/394/407 Count/Find/Insert; EnConvert.c:30 int.ToString.
// 3_Game/Entities/EntityAI.c:3374 GetPersistentID, reused ONLY through
// HCSearchSupplyRegistry.PersistentId (zero identity refuses, never session ID).
// Native live reads are confined to HCEcologyResourceSurvey.Carcass/Supply.
// N9 AnimalBase.c:32-40 DeathUpdate swaps some native bodies; ActionSkinning.c:
// 64-80 spends the body, creates native-config organs and schedules deletion.
// 1_Core/proto/EnScript.c:470 RemoveOrdered retains receipt order on eviction.
// No general CE corpse admission/paired Hive-restore receipt was established.
// Refuse authored materialization; no dummy, kill/spawn, loot, lifetime write,
// population count, predator command or inferred feeding. CE retains ownership.
// HCLeadStore.HCReserveTrace requires a delayed WORLD fact, not an HC-15 fact;
// do not fabricate that causal link. Here HCEncounterStore supplies the shared
// verified intent/backup/copy/readback protocol for permanent local receipts.
// Back up hc49-carcasses.json with native inventory and scene-chains.json.
// All saves below are transition barriers; no routine checkpoint/save loop.
// HC-11 trace integration and native N2/N3/N9 experiments remain PENDING.

class HCWildlifeSceneConfig
{
    int Version;
    bool Enabled;
    int MaxReceipts;
    int SamplesPerTick;
    int WorkUnits;
    int TickMs;
    ref array<string> Sites;
    string Origin;
    string SupplyOwner;
    string AuthoredDisposition;
}

class HCWildlifeSceneRow
{
    string Id;
    int StorySequence;
    int DueAt;
    int EndsAt;
    string CorpseId;
    string Origin = "observed";
    // pending -> native_skinnable -> depleted/unavailable/unknown.
    // missed: window ended without a body. Oldest terminal receipts may expire
    // from the bounded journal; pending/native_skinnable rows are never evicted.
    string Supply = "pending";
}

class HCWildlifeSceneState
{
    int Version = 2;
    ref array<ref HCWildlifeSceneRow> Rows = new array<ref HCWildlifeSceneRow>();
    // Independent spent-ID ring. Never overwrite an ID to admit a new body:
    // saturation refuses further reservations, so eviction cannot revive loot.
    ref array<string> SpentCorpseIds = new array<string>();
}

class HCWildlifeSceneDebug : HCDebugContributor
{
    HCWildlifeScenes Owner;
    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        if (Owner) { Owner.HCDescribe(snapshot); }
    }
}

// Owned by Ecology; no module registry, timer, native cohort or scheduler.
// The shared story director calls HCOffer AFTER its arrival save barrier.
// Ecology calls HCStep(world UTC since 2020, native mission milliseconds).
class HCWildlifeScenes
{
    static const int MAX_RECEIPTS = 64;
    // Fallback: 16 times the old lifetime allowance, bounded independently of
    // the 64 scene receipts. 1024 native numeric PIDs plus receipts fit the
    // shared HCEncounterStore 262144-byte ceiling. This is NOT safe eviction:
    // GetPersistentID (EntityAI.c:3374) identifies, but does not resolve an old
    // PID or prove its Hive corpse is gone. Old rows retain no handle/session.
    // Refuse at this named cap; never treat snapshot absence as destruction.
    static const int MAX_SPENT_CORPSES = 1024;
    protected static ref array<string> s_StoryOff = new array<string>;
    protected ref HCWildlifeSceneConfig m_Config;
    protected ref HCEncounterStore<HCWildlifeSceneState> m_Store;
    protected ref HCWildlifeSceneState m_State;
    protected ref HCWildlifeSceneRow m_Active;
    protected EntityAI m_Body;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected ref HCWildlifeSceneDebug m_Debug;
    protected bool m_Enabled;
    protected bool m_Fault;
    protected bool m_Opened;
    protected int m_Cursor;
    protected int m_LastTick = -1;
    protected int m_LastNow = -1;
    protected int m_Reports;
    protected string m_Effective = "off";
    protected string m_Reason = "not_started";
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;

    // Lead calls once at scene publication when the Stories schedule is off.
    // Chosen disposition: named refusal, never replay or replenish that scene.
    // Bounded process-local dedup; the final slot represents aggregate overflow.
    static void HCStoryOff(string sceneId)
    {
        if (!HCEventDirector.TextValid(sceneId, 80) || s_StoryOff.Find(sceneId) >= 0) { return; }
        if (s_StoryOff.Count() > HCWildlifeScenes.MAX_RECEIPTS) { return; }
        if (s_StoryOff.Count() == HCWildlifeScenes.MAX_RECEIPTS)
        {
            s_StoryOff.Insert("");
            Print("[HC Plan] HC-49 state=refused refusal=STORIES_NOT_READY scene=overflow retained=64 offered=0 runtime=PENDING");
            return;
        }
        s_StoryOff.Insert(sceneId);
        Print("[HC Plan] HC-49 state=refused refusal=STORIES_NOT_READY scene=" + sceneId + " offered=0 runtime=PENDING");
    }

    bool HCActive() { return m_Enabled && !m_Fault && m_Active != null; }

    static HCWildlifeSceneConfig HCLoadConfig()
    {
        string text = HCEcologyRuntimeIO.Read("$mission:hollow-country/ecology/carcass-sites.json", 8192);
        HCWildlifeSceneConfig config;
        string error;
        if (text == "" || !JsonFileLoader<HCWildlifeSceneConfig>.LoadData(text, config, error)) { return null; }
        return config;
    }

    static bool HCConfigValid(HCWildlifeSceneConfig config)
    {
        // No initializer/missing-field migration: native missing ints are zero.
        if (!config || config.Version != 1 || !config.Sites || config.Sites.Count() != 0) { return false; }
        if (config.MaxReceipts < 1 || config.MaxReceipts > HCWildlifeScenes.MAX_RECEIPTS) { return false; }
        if (config.SamplesPerTick < 1 || config.SamplesPerTick > 16) { return false; }
        if (config.WorkUnits < 1 || config.WorkUnits > 64 || config.TickMs < 1 || config.TickMs > 60000) { return false; }
        if (config.Origin != "observed" || config.SupplyOwner != "native_skinning") { return false; }
        return config.AuthoredDisposition == "AUTHORED_CORPSE_CE_ADMISSION_UNPROVEN";
    }

    static bool HCValid(HCWildlifeSceneState state)
    {
        if (!state || (state.Version != 1 && state.Version != 2) || !state.Rows || state.Rows.Count() > HCWildlifeScenes.MAX_RECEIPTS) { return false; }
        array<string> spent = new array<string>();
        if (state.Version == 2)
        {
            if (!state.SpentCorpseIds || state.SpentCorpseIds.Count() > HCWildlifeScenes.MAX_SPENT_CORPSES) { return false; }
            foreach (string spentId : state.SpentCorpseIds)
            {
                if (!HCEventDirector.TextValid(spentId, 96) || spent.Find(spentId) >= 0) { return false; }
                spent.Insert(spentId);
            }
        }
        array<string> identities = new array<string>();
        array<string> bodies = new array<string>();
        array<int> stories = new array<int>();
        int active = 0;
        foreach (HCWildlifeSceneRow row : state.Rows)
        {
            if (!row || !HCEventDirector.TextValid(row.Id, 96) || row.Origin != "observed") { return false; }
            if (row.StorySequence < 1 || row.StorySequence >= 999999999 || stories.Find(row.StorySequence) >= 0) { return false; }
            if (row.DueAt < 1 || row.EndsAt <= row.DueAt || row.EndsAt > 1000086400) { return false; }
            if (identities.Find(row.Id) >= 0) { return false; }
            identities.Insert(row.Id);
            stories.Insert(row.StorySequence);
            if (row.CorpseId != "")
            {
                if (!HCEventDirector.TextValid(row.CorpseId, 96) || bodies.Find(row.CorpseId) >= 0) { return false; }
                if (state.Version == 2 && spent.Find(row.CorpseId) < 0) { return false; }
                bodies.Insert(row.CorpseId);
            }
            if (row.Supply == "pending" || row.Supply == "native_skinnable") { active = active + 1; }
            if (row.Supply == "pending" && row.CorpseId != "") { return false; }
            if (row.Supply == "native_skinnable" || row.Supply == "depleted" || row.Supply == "unavailable")
            {
                if (row.CorpseId == "") { return false; }
            }
            if (row.Supply != "pending" && row.Supply != "native_skinnable" && row.Supply != "depleted" && row.Supply != "unavailable" && row.Supply != "unknown" && row.Supply != "missed") { return false; }
            if (row.Supply == "missed" && row.CorpseId != "") { return false; }
        }
        return active <= 1;
    }

    void HCReport()
    {
        // Lifecycle status stays current even when bounded diagnostics are full.
        m_Status.HCPublish(m_Effective, m_Reason);
        if (m_Reports >= 32) { return; }
        m_Reports = m_Reports + 1;
        string carcassId = "none";
        string supply = "none";
        int retained = 0;
        if (m_State) { retained = m_State.Rows.Count(); }
        if (m_Active) { carcassId = m_Active.Id; supply = m_Active.Supply; }
        string line = "[HC Plan] HC-49 carcass=" + carcassId + " origin=observed supply=" + supply;
        line += " state=" + m_Effective + " refusal=" + m_Reason;
        int receiptCap = HCWildlifeScenes.MAX_RECEIPTS;
        Print(line + " retained=" + retained.ToString() + " receipt_cap=" + receiptCap.ToString() + " active_cap=1 authored=0 runtime=PENDING");
    }

    HCOperationalStatus HCStatus()
    {
        return m_Status;
    }

    protected bool HCRefuse(string reason)
    {
        if (m_Effective == "refused" && m_Reason == reason) { return false; }
        m_Effective = "refused";
        m_Reason = reason;
        HCReport();
        return false;
    }

    protected bool HCCommit()
    {
        if (m_Fault || !HCValid(m_State) || !m_Store.Save(m_State))
        {
            m_Fault = true;
            m_Enabled = false;
            m_Body = null;
            HCReleaseDebug();
            return HCRefuse("CARCASS_STORE_UNCERTAIN");
        }
        HCReport();
        return true;
    }

    bool HCOpen(bool enabled)
    {
        // One open per owner. Off is disk/query free; faults never retry.
        if (m_Opened || m_Fault) { return false; }
        m_Opened = true;
        m_Reason = "operator_off";
        if (!HCV2Admission.Admitted(enabled)) { HCReport(); return false; }
        if (!HCEcologyNative.Authority()) { return HCRefuse("CARCASS_SERVER_REQUIRED"); }
        m_Config = HCLoadConfig();
        if (!HCConfigValid(m_Config)) { return HCRefuse("CARCASS_MANIFEST_INVALID"); }
        if (!m_Config.Enabled) { HCReport(); return false; }
        m_Store = new HCEncounterStore<HCWildlifeSceneState>("hc49-carcasses");
        m_State = m_Store.Load(new HCWildlifeSceneState, "Rows");
        if (!HCValid(m_State)) { m_Fault = true; return HCRefuse("CARCASS_STATE_INVALID"); }
        if (m_State.Rows.Count() > m_Config.MaxReceipts) { return HCRefuse("CARCASS_HISTORY_OVER_CONFIG_CAP"); }
        m_Enabled = true;
        m_Effective = "ready";
        m_Reason = "native_observation_only";
        bool changed = false;
        if (m_State.Version == 1)
        {
            // Native missing Version=0 is refused above, never treated as v1.
            // Only retained legacy receipts are recoverable; never infer IDs
            // of scenes already evicted before this migration.
            m_State.SpentCorpseIds = new array<string>();
            foreach (HCWildlifeSceneRow legacy : m_State.Rows)
            {
                if (legacy.CorpseId != "") { m_State.SpentCorpseIds.Insert(legacy.CorpseId); }
            }
            m_State.Version = 2;
            changed = true;
        }
        foreach (HCWildlifeSceneRow restored : m_State.Rows)
        {
            if (restored.Supply == "native_skinnable")
            {
                // No Hive/journal atomicity or restoration proof. Keep spent ID;
                // never scan for a replacement, recreate, rebind or refund.
                restored.Supply = "unknown";
                changed = true;
            }
            if (restored.Supply == "pending") { m_Active = restored; }
        }
        if (changed && !HCCommit()) { return false; }
        m_Debug = new HCWildlifeSceneDebug;
        m_Debug.Owner = this;
        HCDebugSnapshot.HCRegister(m_Debug);
        HCReport();
        Print("[HC Plan] HC-49 carcass=none origin=authored supply=pending state=refused refusal=AUTHORED_CORPSE_CE_ADMISSION_UNPROVEN count=0 runtime=PENDING");
        int spentCap = HCWildlifeScenes.MAX_SPENT_CORPSES;
        Print("[HC Plan] HC-49 state=refused refusal=CARCASS_SPENT_EVICTION_UNPROVEN spent_cap=" + spentCap.ToString() + " runtime=PENDING");
        return true;
    }

    // ONLY shared server director input; not an RPC or an alleged native CE
    // event. Story issue must already have passed HC-19's synchronous barrier.
    bool HCOffer(HCSceneChain chain, HCSceneChainState state)
    {
        if (!m_Enabled || m_Fault || m_Active || !HCEcologyNative.Authority()) { return false; }
        if (!chain || !state || !HCStoryPolicy.HCValid(state) || !state.Stories) { return false; }
        if (chain.Complete || chain.Cancelled || state.Chains.Find(chain) < 0) { return false; }
        if (chain.StorySequence <= state.Stories.LegacyThrough || chain.StorySequence >= state.Stories.NextSequence) { return false; }
        if (!HCEventDirector.TextValid(chain.Id, 80) || chain.DueAt < 1 || chain.ExpiresAt <= chain.DueAt) { return false; }
        if (chain.ExpiresAt > 1000086400) { return false; }
        foreach (HCWildlifeSceneRow prior : m_State.Rows)
        {
            if (prior.StorySequence == chain.StorySequence || prior.Id == chain.Id + "-carcass") { return false; }
        }
        if (m_State.Rows.Count() >= m_Config.MaxReceipts)
        {
            // StorySequence is durable issue order even if JSON rows reorder.
            // At most MAX_RECEIPTS rows; eviction and insertion share ONE barrier.
            int oldest = -1;
            int oldestSequence = 999999999;
            int receiptIndex = 0;
            foreach (HCWildlifeSceneRow receipt : m_State.Rows)
            {
                if (receipt.Supply != "pending" && receipt.Supply != "native_skinnable" && receipt.StorySequence < oldestSequence)
                {
                    oldest = receiptIndex;
                    oldestSequence = receipt.StorySequence;
                }
                receiptIndex = receiptIndex + 1;
            }
            if (oldest < 0) { return HCRefuse("CARCASS_HISTORY_FULL_NO_TERMINAL"); }
            m_State.Rows.RemoveOrdered(oldest);
        }
        HCWildlifeSceneRow row = new HCWildlifeSceneRow;
        row.Id = chain.Id + "-carcass";
        row.StorySequence = chain.StorySequence;
        row.DueAt = chain.DueAt;
        row.EndsAt = chain.ExpiresAt;
        m_State.Rows.Insert(row);
        m_Active = row;
        return HCCommit();
    }

    protected bool HCSpent(string corpseId)
    {
        return m_State.SpentCorpseIds.Find(corpseId) >= 0;
    }

    protected void HCFinish(string supply)
    {
        m_Active.Supply = supply;
        m_Body = null;
        HCCommit();
        m_Active = null;
    }

    void HCStep(int now, int nowMs)
    {
        if (!m_Enabled || m_Fault || !m_Active || !HCEcologyNative.Authority()) { return; }
        // A missing/invalid UTC sample is transient; retain the opportunity and
        // both cursors without a save, report or native body query.
        if (now < 1) { return; }
        if (now > 999000000 || nowMs < 0 || nowMs < m_LastNow)
        {
            HCFinish("unknown");
            HCRefuse("CARCASS_CLOCK_INVALID");
            return;
        }
        m_LastNow = nowMs;
        if (m_LastTick >= 0 && nowMs - m_LastTick < m_Config.TickMs) { return; }
        m_LastTick = nowMs;
        m_Units.HCReset(m_Config.WorkUnits);
        m_Work.HCReset(m_Config.SamplesPerTick);
        if (!m_Units.HCTake(1) || !m_Work.HCContinue()) { return; }
        if (m_Active.Supply == "native_skinnable")
        {
            string supply = HCEcologyResourceSurvey.CarcassSupply(m_Body);
            if (supply != "native_skinnable") { HCFinish(supply); return; }
            if (HCSearchSupplyRegistry.PersistentId(m_Body) != m_Active.CorpseId) { HCFinish("unknown"); return; }
            if (now >= m_Active.EndsAt) { HCFinish("unknown"); }
            return;
        }
        if (now >= m_Active.EndsAt) { HCFinish("missed"); return; }
        if (now < m_Active.DueAt) { return; }
        // Inherits HCPerfPlayers proximity/freshness/species limits. No new
        // range or native count. A fresh bounded snapshot carries weak handles.
        array<ref HCWildlifeFact> facts = HCWildlifeObservation.HCSnapshot(nowMs);
        int examined = 0;
        while (examined < facts.Count() && examined < m_Config.SamplesPerTick)
        {
            if (examined > 0 && (!m_Units.HCTake(1) || !m_Work.HCContinue())) { break; }
            if (m_Cursor >= facts.Count()) { m_Cursor = 0; }
            HCWildlifeFact fact = facts[m_Cursor];
            m_Cursor = m_Cursor + 1;
            examined = examined + 1;
            AnimalBase corpse = HCEcologyResourceSurvey.Carcass(fact);
            if (!corpse) { continue; }
            string corpseId = HCSearchSupplyRegistry.PersistentId(corpse);
            if (!HCEventDirector.TextValid(corpseId, 96))
            {
                HCRefuse("CARCASS_PERSISTENT_ID_UNAVAILABLE");
                continue;
            }
            if (HCSpent(corpseId)) { continue; }
            if (m_State.SpentCorpseIds.Count() >= HCWildlifeScenes.MAX_SPENT_CORPSES)
            {
                HCRefuse("CARCASS_SPENT_HISTORY_FULL");
                return;
            }
            m_State.SpentCorpseIds.Insert(corpseId);
            m_Active.CorpseId = corpseId;
            m_Active.Supply = "native_skinnable";
            m_Effective = "ready";
            m_Reason = "native_observation_only";
            if (!HCCommit()) { return; }
            // A successful reservation only observes this EXISTING native body.
            // Inventory stays native, including future skinning/loot decisions.
            m_Body = corpse;
            return;
        }
    }

    void HCDescribe(HCDebugSnapshot snapshot)
    {
        if (!m_Enabled || !m_Active || !m_Body) { return; }
        if (HCEcologyResourceSurvey.CarcassSupply(m_Body) != "native_skinnable") { return; }
        // Native Object.GetPosition, 3_Game/Entities/Object.c:287.
        snapshot.AddPoint("wildlife", m_Active.Id, m_Body.GetPosition(), "Observed carcass", "native skinning only; runtime=PENDING");
    }

    protected void HCReleaseDebug()
    {
        if (!m_Debug) { return; }
        HCDebugSnapshot.HCUnregister(m_Debug);
        m_Debug.Owner = null;
        m_Debug = null;
    }

    void HCClose()
    {
        if (!m_Enabled) { return; }
        // Unbound pending opportunities survive ordinary owner stop/restart.
        // Bound native bodies still lack a paired Hive restoration receipt.
        if (m_Active && m_Active.CorpseId != "") { HCFinish("unknown"); }
        m_Active = null;
        m_Enabled = false;
        m_Body = null;
        HCReleaseDebug();
        if (m_Fault) { return; }
        m_Effective = "off";
        m_Reason = "owner_closed";
        HCReport();
    }
}
