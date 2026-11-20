// Native evidence: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 1_Core/proto/EnSystem.c:397,417,425,443,462,525,528,531 (files),
// 3_Game/tools/JsonFileLoader.c:69,85 (JSON). Reuses HCWorldStore.Read/Write.
// 1_Core/proto/EnString.c:240 (IndexOf), EnConvert.c:30 (int.ToString),
// EnScript.c:380,394,407,470,502 (bounded arrays), EnDebug.c:96 (Print).
// 3_Game/Global/Game.c:1120 IsServer; EnString.c:199 Length.
// No native rename exists: verified temp intent -> backup -> copy promotion,
// matching HCWorldStore. Interrupted/corrupt loads suspend this feature;
// unknown physical notes keep their reservations, including offline inventory.
class HCLeadNote
{
    ref HCWorldNote Row = new HCWorldNote;
    ref HCClueLead Lead = new HCClueLead;
    int Expires;
    string NativeText; // identity-bearing native text; empty only for legacy Paper
    int Phase; // 0 reserved, 1 materialized; reservations are never replayed
}

class HCBodyStoryRow
{
    string Id;
    string SceneId;
    string FactId; // empty only for quarantined legacy static rows
    string PlaceId;
    vector Position; // legacy authored prop / already-dead body; never a live target
    int CreatedAt;
    int Expires;
    int Phase; // legacy 0/1 quarantined; 2 actual observed corpse; never replay
}

// Permanent at-most-once tombstone. Never prune to obtain story variety.
// The shared world lead identity is Kind-PlaceId-At (HCLeadModule/HC-20).
// No coordinates, equipment, live-player identity or reward are stored here.
class HCTraceReceipt
{
    string FactId;
    string SceneId;
    string NoteId;
    string BodyId;
}

class HCRadioChannel
{
    string Faction;
    float Frequency;
    int LastSent;
    int Sequence;
}

class HCLeadData
{
    int SchemaVersion = 1;
    int TraceVersion = 1;
    int TraceAfter; // legacy migration watermark; earlier history is unknown
    ref array<ref HCTraceReceipt> Traces = new array<ref HCTraceReceipt>();
    int LastWrite;
    int Serial;
    ref array<ref HCClueLead> Leads = new array<ref HCClueLead>();
    ref array<ref HCLeadNote> Notes = new array<ref HCLeadNote>();
    ref array<ref HCBodyStoryRow> Bodies = new array<ref HCBodyStoryRow>();
    ref array<ref HCRadioChannel> Channels = new array<ref HCRadioChannel>();
}

class HCLeadStore
{
    protected static ref HCLeadStore s_Instance;
    ref HCLeadData Data;
    protected bool m_Healthy;
    protected ref array<ref HCWorldFact> m_Facts = new array<ref HCWorldFact>();
    protected int m_DuplicateRefusals;
    protected string m_LastTraceRefusal;
    protected string m_FaultAt = "unspecified"; // names the refusing step in the fault line
    protected ref HCLeadSaveJob m_SaveJob;
    protected ref HCStagedSaveImage m_SaveImage = new HCStagedSaveImage;
    protected int m_SaveStage;
    protected int m_Revision;
    protected int m_DurableRevision;
    protected int m_SnapshotRevision;
    protected string m_PendText;
    protected string m_VerifiedText;
    protected string m_Path = "$profile:HollowCountry/leads.json";

    static HCLeadStore Get() { return s_Instance; }
    bool Healthy() { return m_Healthy; }

    string HCFactId(HCWorldFact fact)
    {
        if (!fact) { return ""; }
        return fact.Kind + "-" + fact.PlaceId + "-" + fact.At.ToString();
    }

    HCTraceReceipt HCTrace(string factId)
    {
        foreach (HCTraceReceipt receipt : Data.Traces)
        {
            if (receipt.FactId == factId) { return receipt; }
        }
        return null;
    }

    bool HCTraceRefuse(string reason)
    {
        if (reason == "DUPLICATE_FACT" && m_DuplicateRefusals < 2000000000) { m_DuplicateRefusals++; }
        if (m_LastTraceRefusal != reason)
        {
            m_LastTraceRefusal = reason;
            HCPlan("refused", reason);
        }
        return false;
    }

    void HCPlan(string state, string reason)
    {
        int facts;
        int traces;
        if (Data)
        {
            facts = Data.Traces.Count();
            traces = Data.Notes.Count() + Data.Bodies.Count();
        }
        string line = "[HC Plan] HC-44 facts=" + facts.ToString() + " traces=" + traces.ToString();
        line += " duplicate_refusals=" + m_DuplicateRefusals.ToString() + " state=" + state;
        Print(line + " reason=" + reason + " runtime=PENDING");
    }

    // Server-only comparison against detached shared history. An arbitrary
    // lead, scene fallback or alleged client outcome is never a fact receipt.
    HCWorldFact HCResolveFact(HCWorldLead lead)
    {
        if (!m_Healthy || !GetGame().IsServer() || !HCLeadPolicy.Valid(lead)) { return null; }
        if (lead.Source != "world" || !HCWorldLimits.Token(lead.Id)) { return null; }
        HCWorldModule world = HCWorldModule.Get();
        if (!world) { return null; }
        world.GetRecentFacts(HCWorldLimits.FACT_LIFETIME, m_Facts);
        int now = HCWorldClock.UTC();
        foreach (HCWorldFact fact : m_Facts)
        {
            if (HCFactId(fact) != lead.Id || fact.At <= Data.TraceAfter) { continue; }
            HCWorldLead expected = new HCWorldLead;
            if (!HCLeadPolicy.Build(fact, expected, fact.PlaceId, HCLeadPolicy.Kind(fact.Kind), now)) { continue; }
            if (lead.Kind != expected.Kind || lead.TextId != expected.TextId) { continue; }
            if (lead.TargetPlaceId == expected.TargetPlaceId && lead.Expires > now && lead.Expires <= expected.Expires) { return fact; }
        }
        return null;
    }

    // Reserve in the SAME image as the physical-note intent. A failed spawn
    // retains this receipt; an uncertain write closes the store, never retries.
    HCTraceReceipt HCReserveTrace(HCWorldLead lead, string sceneId)
    {
        if (!m_Healthy || !lead || !HCWorldLimits.Token(sceneId)) { return null; }
        if (HCTrace(lead.Id)) { HCTraceRefuse("DUPLICATE_FACT"); return null; }
        if (!HCResolveFact(lead)) { HCTraceRefuse("OBSERVED_FACT_RECEIPT_REQUIRED"); return null; }
        if (Data.Traces.Count() >= 256) { HCTraceRefuse("TRACE_HISTORY_CAP_NO_EVICTION"); return null; }
        HCTraceReceipt receipt = new HCTraceReceipt;
        receipt.FactId = lead.Id;
        receipt.SceneId = sceneId;
        Data.Traces.Insert(receipt);
        return receipt;
    }

    string HCTraceText(HCWorldLead lead)
    {
        string report = HCLeadPolicy.Text(lead);
        if (report == "") { return ""; }
        return report + "\n[HC trace " + lead.Id + "]";
    }

    int HCSceneTraces(HCLeadData value, string sceneId)
    {
        int count;
        foreach (HCLeadNote sceneNote : value.Notes)
        {
            if (sceneNote && sceneNote.Row && sceneNote.Row.SceneId == sceneId) { count++; }
        }
        foreach (HCBodyStoryRow sceneBody : value.Bodies)
        {
            if (sceneBody && sceneBody.SceneId == sceneId) { count++; }
        }
        return count;
    }

    bool HCTraceValid(HCLeadData value)
    {
        if (value.TraceVersion != 1 || value.TraceAfter < 0 || value.TraceAfter > HCWorldClock.UTC()) { return false; }
        if (!value.Traces || value.Traces.Count() > 256) { return false; }
        map<string, bool> facts = new map<string, bool>;
        map<string, bool> entities = new map<string, bool>;
        foreach (HCTraceReceipt receipt : value.Traces)
        {
            if (!receipt || !HCWorldLimits.Token(receipt.FactId) || !HCWorldLimits.Token(receipt.SceneId)) { return false; }
            if (facts.Contains(receipt.FactId) || (receipt.NoteId == "" && receipt.BodyId == "")) { return false; }
            facts.Insert(receipt.FactId, true);
            if (receipt.NoteId != "")
            {
                if (!HCWorldLimits.Token(receipt.NoteId) || entities.Contains(receipt.NoteId)) { return false; }
                entities.Insert(receipt.NoteId, true);
            }
            if (receipt.BodyId != "")
            {
                if (!HCWorldLimits.Token(receipt.BodyId) || entities.Contains(receipt.BodyId)) { return false; }
                entities.Insert(receipt.BodyId, true);
            }
        }
        return true;
    }

    bool Valid(HCLeadData value)
    {
        if (!value || value.SchemaVersion != 1 || value.Serial < 0 || value.LastWrite < 0 || value.LastWrite > HCWorldClock.UTC()) { return false; }
        if (!value.Leads || !value.Notes || !value.Bodies || !value.Channels || !HCTraceValid(value)) { return false; }
        if (value.Leads.Count() > 64 || value.Notes.Count() > 10 || value.Bodies.Count() > 3 || (value.Channels.Count() != 0 && value.Channels.Count() != 5)) { return false; }
        if (value.Notes.Count() + value.Bodies.Count() > 10) { return false; }
        // Receipt rows are unique per note/body id (HCTraceValid above), so one
        // lookup replaces the per-row scan of value.Traces.
        map<string, HCTraceReceipt> noteReceipts = new map<string, HCTraceReceipt>;
        map<string, HCTraceReceipt> bodyReceipts = new map<string, HCTraceReceipt>;
        foreach (HCTraceReceipt indexed : value.Traces)
        {
            if (indexed.NoteId != "") { noteReceipts.Insert(indexed.NoteId, indexed); }
            if (indexed.BodyId != "") { bodyReceipts.Insert(indexed.BodyId, indexed); }
        }
        map<string, bool> ids = new map<string, bool>;
        map<string, int> groupCounts = new map<string, int>;
        foreach (HCWorldLead leadRow : value.Leads)
        {
            if (!HCLeadPolicy.Valid(leadRow) || !HCWorldLimits.Token(leadRow.Id) || !HCWorldLimits.Token(leadRow.Source) || !HCWorldLimits.Token(leadRow.GroupId) || ids.Contains(leadRow.Id)) { return false; }
            ids.Insert(leadRow.Id, true);
            int groupCount = 0;
            if (groupCounts.Contains(leadRow.GroupId)) { groupCount = groupCounts.Get(leadRow.GroupId); }
            groupCount = groupCount + 1;
            if (groupCount > 5) { return false; }
            groupCounts.Set(leadRow.GroupId, groupCount);
        }
        map<string, bool> scenes = new map<string, bool>;
        foreach (HCLeadNote noteRow : value.Notes)
        {
            if (!noteRow || !noteRow.Row || !HCLeadPolicy.Valid(noteRow.Lead)) { return false; }
            if (!HCWorldLimits.Token(noteRow.Row.Id) || !HCWorldLimits.Token(noteRow.Row.SceneId) || noteRow.Row.CreatedAt < 1 || noteRow.Expires <= noteRow.Row.CreatedAt || noteRow.Phase < 0 || noteRow.Phase > 1) { return false; }
            if (scenes.Contains(noteRow.Row.SceneId) || ids.Contains(noteRow.Row.Id)) { return false; }
            if (noteRow.NativeText != "" && noteRow.NativeText != HCTraceText(noteRow.Lead)) { return false; }
            if (noteRow.NativeText != "")
            {
                bool boundNote = false;
                HCTraceReceipt noteReceipt;
                if (noteReceipts.Find(noteRow.Row.Id, noteReceipt))
                {
                    boundNote = noteReceipt.FactId == noteRow.Lead.Id && noteReceipt.SceneId == noteRow.Row.SceneId;
                }
                if (!boundNote) { return false; }
            }
            scenes.Insert(noteRow.Row.SceneId, true);
            ids.Insert(noteRow.Row.Id, true);
        }
        foreach (HCBodyStoryRow bodyRow : value.Bodies)
        {
            if (!bodyRow || !HCWorldLimits.Token(bodyRow.Id) || !HCWorldLimits.Token(bodyRow.SceneId) || !HCLeadPolicy.KnownPlace(bodyRow.PlaceId) || !HCWorldLimits.Position(bodyRow.Position)) { return false; }
            if (HCSceneTraces(value, bodyRow.SceneId) > 3) { return false; }
            if (bodyRow.FactId != "")
            {
                bool boundBody = false;
                HCTraceReceipt bodyReceipt;
                if (bodyReceipts.Find(bodyRow.Id, bodyReceipt))
                {
                    boundBody = bodyReceipt.FactId == bodyRow.FactId && bodyReceipt.SceneId == bodyRow.SceneId;
                }
                if (!boundBody) { return false; }
            }
            if (bodyRow.CreatedAt < 1 || bodyRow.Expires <= bodyRow.CreatedAt || bodyRow.Phase < 0 || bodyRow.Phase > 2 || ids.Contains(bodyRow.Id)) { return false; }
            ids.Insert(bodyRow.Id, true);
        }
        map<string, bool> factions = new map<string, bool>;
        foreach (HCRadioChannel channelRow : value.Channels)
        {
            if (!channelRow || HCRadioChatter.Frequency(channelRow.Faction) != channelRow.Frequency || channelRow.Frequency <= 0 || channelRow.LastSent < 0 || channelRow.LastSent > HCWorldClock.UTC() || channelRow.Sequence < 0 || factions.Contains(channelRow.Faction)) { return false; }
            factions.Insert(channelRow.Faction, true);
        }
        return true;
    }

    HCLeadData Decode(string text)
    {
        HCLeadData value;
        string error;
        // Field initializers must never turn a truncated/empty JSON object into
        // a fresh ledger and silently release physical-note reservations.
        m_FaultAt = "decode_header";
        if (text.IndexOf("\"SchemaVersion\"") < 0 || text.IndexOf("\"LastWrite\"") < 0 || text.IndexOf("\"Serial\"") < 0 || text.IndexOf("\"Leads\"") < 0 || text.IndexOf("\"Notes\"") < 0 || text.IndexOf("\"Bodies\"") < 0 || text.IndexOf("\"Channels\"") < 0) { return null; }
        bool hasTraceVersion = text.IndexOf("\"TraceVersion\"") >= 0;
        if (hasTraceVersion && (text.IndexOf("\"Traces\"") < 0 || text.IndexOf("\"TraceAfter\"") < 0)) { return null; }
        m_FaultAt = "decode_json";
        if (text == "" || !JsonFileLoader<HCLeadData>.LoadData(text, value, error)) { return null; }
        // A legacy ledger has no record of already destroyed/expired clues.
        // Admit only facts observed AFTER migration; never invent old history.
        // Native JsonFileLoader leaves a missing int at 0, not its declared
        // initializer (boot 057: legacy image faulted at=decode_traces_invalid).
        // A legacy image therefore gets the current trace schema stamped here.
        if (!hasTraceVersion && value)
        {
            value.TraceVersion = 1;
            value.TraceAfter = HCWorldClock.UTC();
            if (!value.Traces) { value.Traces = new array<ref HCTraceReceipt>(); }
        }
        m_FaultAt = "decode_rows";
        if (value && !value.Traces) { m_FaultAt = "decode_traces_missing"; }
        if (value && value.Traces && !HCTraceValid(value)) { m_FaultAt = "decode_traces_invalid"; }
        if (!Valid(value)) { return null; }
        return value;
    }

    bool Open()
    {
        s_Instance = this;
        m_FaultAt = "open_clock_or_folder";
        if (HCWorldClock.UTC() < 1 || (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry"))) { return Fault(); }
        m_FaultAt = "open_tmp_present";
        if (FileExist(m_Path + ".tmp")) { return Fault(); }
        if (FileExist(m_Path))
        {
            m_VerifiedText = HCWorldStore.Read(m_Path);
            Data = Decode(m_VerifiedText);
            if (!Data) { return Fault(); }
        }
        else
        {
            // A lone backup is an uncertain deletion, never permission to reset caps.
            m_FaultAt = "open_lone_backup";
            if (FileExist(m_Path + ".bak")) { return Fault(); }
            Data = new HCLeadData;
        }
        m_Healthy = true;
        if (!Save()) { return false; }
        m_SaveJob = new HCLeadSaveJob;
        m_SaveJob.Owner = this;
        HCSaveScheduler.HCRegister(m_SaveJob);
        if (Data.TraceAfter > 0) { HCPlan("ready", "LEGACY_HISTORY_QUARANTINED_BEFORE_WATERMARK"); }
        return true;
    }

    bool Fault()
    {
        m_Healthy = false;
        Print("[HollowCountry] V2 leads persistence fault; feature suspended; files and reservations preserved at=" + m_FaultAt);
        return false;
    }

    void HCRequestCheckpoint()
    {
        if (!m_Healthy || !m_SaveJob) { return; }
        m_Revision++;
        m_SaveJob.HCDirty = true;
    }

    int HCRequestBarrier()
    {
        if (!m_Healthy || !m_SaveJob) { return -1; }
        HCRequestCheckpoint();
        m_SaveJob.HCUrgent = true;
        m_SaveJob.HCDue = GetGame().GetTickTime();
        return m_Revision;
    }

    bool HCDurable(int revision) { return m_Healthy && revision >= 0 && m_DurableRevision >= revision; }
    void HCPumpCheckpoint() { HCSaveScheduler.HCPumpFallback(m_SaveJob); }

    void HCCloseCheckpoint()
    {
        if (!m_SaveJob) { return; }
        if (m_Healthy) { HCSaveScheduler.HCFlush(m_SaveJob); }
        HCSaveScheduler.HCUnregister(m_SaveJob);
        m_SaveJob = null;
    }

    protected int HCSaveFailed()
    {
        m_SaveStage = 0;
        m_PendText = "";
        Fault();
        return HCSaveJob.STEP_FAILED;
    }

    // Encode/read-prior stages leave disk unchanged. HCStagedSaveImage.HCStepImage
    // documents subsequent crash states; Open still refuses .tmp/backup-only.
    // Revision changes may restart only before intent; afterwards finish the
    // old snapshot then persist the newer authoritative rows before DONE.
    // Disk stage boundaries: write_tmp/read_tmp retain old primary + intent;
    // copy_backup retains old primary/backup + intent; copy_primary/read_primary
    // retain new primary, old backup and intent; clear_intent admits new primary.
    int HCCheckpointStep()
    {
        if (!m_Healthy) { return HCSaveFailed(); }
        if (m_SaveStage == 0)
        {
            HCSaveJob.HCOperation = "encode";
            m_FaultAt = "save_rows";
            if (!Valid(Data)) { return HCSaveFailed(); }
            m_FaultAt = "save_serialize";
            Data.LastWrite = HCWorldClock.UTC();
            string error;
            if (!JsonFileLoader<HCLeadData>.MakeData(Data, m_PendText, error)) { return HCSaveFailed(); }
            if (m_PendText.Length() > HCWorldStore.MAX_BYTES) { return HCSaveFailed(); }
            m_SnapshotRevision = m_Revision;
            m_SaveStage = 1;
            return HCSaveJob.STEP_MORE;
        }
        if (m_SaveStage == 1)
        {
            // The startup decoder/last commit already validated this exact
            // image; stream its comparison at the shared prior-read boundary.
            m_SaveStage = 2;
        }
        if (m_SaveStage == 2)
        {
            if (m_SnapshotRevision != m_Revision) { m_SaveStage = 0; return HCSaveJob.STEP_MORE; }
            m_FaultAt = "save_commit";
            if (!m_SaveImage.Begin(m_Path, m_PendText, HCWorldStore.MAX_BYTES, m_VerifiedText != "", m_VerifiedText != "", m_VerifiedText)) { return HCSaveFailed(); }
            m_SaveStage = 3;
        }
        // Never clear intent over an obsolete cleanup snapshot: a crash must
        // refuse, rather than admit removed rows. Re-encode under the same intent
        // (no file IO this stage); original backup survives all refresh stages.
        if (m_SaveImage.HCReadyToClearIntent() && m_SnapshotRevision != m_Revision)
        {
            HCSaveJob.HCOperation = "encode_refresh";
            if (!Valid(Data)) { return HCSaveFailed(); }
            Data.LastWrite = HCWorldClock.UTC();
            string refreshError;
            if (!JsonFileLoader<HCLeadData>.MakeData(Data, m_PendText, refreshError)) { return HCSaveFailed(); }
            if (!m_SaveImage.HCRefreshIntent(m_PendText)) { return HCSaveFailed(); }
            m_SnapshotRevision = m_Revision;
            return HCSaveJob.STEP_MORE;
        }
        int result = m_SaveImage.HCStepImage();
        if (result == HCSaveJob.STEP_FAILED) { return HCSaveFailed(); }
        if (result == HCSaveJob.STEP_MORE) { return result; }
        m_SaveStage = 0;
        m_VerifiedText = m_PendText;
        m_PendText = "";
        if (m_SnapshotRevision != m_Revision) { return HCSaveJob.STEP_MORE; }
        m_DurableRevision = m_SnapshotRevision;
        return HCSaveJob.STEP_DONE;
    }

    bool Save()
    {
        if (!m_Healthy) { return false; }
        // Force freshness through the same continuation, including an older
        // intent already in flight. Never bypass its verified-image bookkeeping.
        m_Revision++;
        if (m_SaveJob) { m_SaveJob.HCInFlight = false; }
        int result = HCSaveJob.STEP_MORE;
        int steps;
        while (result == HCSaveJob.STEP_MORE && steps < HCStagedSaveImage.HC_MAX_STAGES * 2 + 6)
        {
            result = HCCheckpointStep();
            steps++;
        }
        if (m_SaveJob && result == HCSaveJob.STEP_DONE) { m_SaveJob.HCDirty = false; m_SaveJob.HCUrgent = false; }
        return result == HCSaveJob.STEP_DONE;
    }

    string NextId(string kind)
    {
        if (!m_Healthy || Data.Serial >= 2000000000) { return ""; }
        Data.Serial++;
        return kind + "-" + Data.Serial.ToString();
    }
}

class HCLeadSaveJob : HCSaveJob
{
    HCLeadStore Owner;
    override string HCName() { return "CausalLeads"; }
    override int HCStep()
    {
        if (!Owner) { return HCSaveJob.STEP_FAILED; }
        return Owner.HCCheckpointStep();
    }
}
