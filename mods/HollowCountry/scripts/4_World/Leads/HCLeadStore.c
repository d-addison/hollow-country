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
    ref HCWorldLead Lead = new HCWorldLead;
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
    ref array<ref HCWorldLead> Leads = new array<ref HCWorldLead>();
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
    protected int m_SaveStage;
    protected int m_Revision;
    protected int m_SnapshotRevision;
    protected string m_PendText;
    protected string m_PendPrior;
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
        array<string> facts = new array<string>();
        array<string> entities = new array<string>();
        foreach (HCTraceReceipt receipt : value.Traces)
        {
            if (!receipt || !HCWorldLimits.Token(receipt.FactId) || !HCWorldLimits.Token(receipt.SceneId)) { return false; }
            if (facts.Find(receipt.FactId) >= 0 || (receipt.NoteId == "" && receipt.BodyId == "")) { return false; }
            facts.Insert(receipt.FactId);
            if (receipt.NoteId != "")
            {
                if (!HCWorldLimits.Token(receipt.NoteId) || entities.Find(receipt.NoteId) >= 0) { return false; }
                entities.Insert(receipt.NoteId);
            }
            if (receipt.BodyId != "")
            {
                if (!HCWorldLimits.Token(receipt.BodyId) || entities.Find(receipt.BodyId) >= 0) { return false; }
                entities.Insert(receipt.BodyId);
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
        array<string> ids = new array<string>();
        foreach (HCWorldLead leadRow : value.Leads)
        {
            if (!HCLeadPolicy.Valid(leadRow) || !HCWorldLimits.Token(leadRow.Id) || !HCWorldLimits.Token(leadRow.Source) || !HCWorldLimits.Token(leadRow.GroupId) || ids.Find(leadRow.Id) >= 0) { return false; }
            ids.Insert(leadRow.Id);
            int groupCount = 0;
            foreach (HCWorldLead groupRow : value.Leads)
            {
                if (groupRow.GroupId == leadRow.GroupId) { groupCount++; }
            }
            if (groupCount > 5) { return false; }
        }
        array<string> scenes = new array<string>();
        foreach (HCLeadNote noteRow : value.Notes)
        {
            if (!noteRow || !noteRow.Row || !HCLeadPolicy.Valid(noteRow.Lead)) { return false; }
            if (!HCWorldLimits.Token(noteRow.Row.Id) || !HCWorldLimits.Token(noteRow.Row.SceneId) || noteRow.Row.CreatedAt < 1 || noteRow.Expires <= noteRow.Row.CreatedAt || noteRow.Phase < 0 || noteRow.Phase > 1) { return false; }
            if (scenes.Find(noteRow.Row.SceneId) >= 0 || ids.Find(noteRow.Row.Id) >= 0) { return false; }
            if (noteRow.NativeText != "" && noteRow.NativeText != HCTraceText(noteRow.Lead)) { return false; }
            if (noteRow.NativeText != "")
            {
                bool boundNote = false;
                foreach (HCTraceReceipt noteReceipt : value.Traces)
                {
                    if (noteReceipt.NoteId == noteRow.Row.Id && noteReceipt.FactId == noteRow.Lead.Id && noteReceipt.SceneId == noteRow.Row.SceneId) { boundNote = true; }
                }
                if (!boundNote) { return false; }
            }
            scenes.Insert(noteRow.Row.SceneId);
            ids.Insert(noteRow.Row.Id);
        }
        foreach (HCBodyStoryRow bodyRow : value.Bodies)
        {
            if (!bodyRow || !HCWorldLimits.Token(bodyRow.Id) || !HCWorldLimits.Token(bodyRow.SceneId) || !HCLeadPolicy.KnownPlace(bodyRow.PlaceId) || !HCWorldLimits.Position(bodyRow.Position)) { return false; }
            if (HCSceneTraces(value, bodyRow.SceneId) > 3) { return false; }
            if (bodyRow.FactId != "")
            {
                bool boundBody = false;
                foreach (HCTraceReceipt bodyReceipt : value.Traces)
                {
                    if (bodyReceipt.BodyId == bodyRow.Id && bodyReceipt.FactId == bodyRow.FactId && bodyReceipt.SceneId == bodyRow.SceneId) { boundBody = true; }
                }
                if (!boundBody) { return false; }
            }
            if (bodyRow.CreatedAt < 1 || bodyRow.Expires <= bodyRow.CreatedAt || bodyRow.Phase < 0 || bodyRow.Phase > 2 || ids.Find(bodyRow.Id) >= 0) { return false; }
            ids.Insert(bodyRow.Id);
        }
        array<string> factions = new array<string>();
        foreach (HCRadioChannel channelRow : value.Channels)
        {
            if (!channelRow || HCRadioChatter.Frequency(channelRow.Faction) != channelRow.Frequency || channelRow.Frequency <= 0 || channelRow.LastSent < 0 || channelRow.LastSent > HCWorldClock.UTC() || channelRow.Sequence < 0 || factions.Find(channelRow.Faction) >= 0) { return false; }
            factions.Insert(channelRow.Faction);
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
        if (!hasTraceVersion) { value.TraceAfter = HCWorldClock.UTC(); }
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
            Data = Decode(HCWorldStore.Read(m_Path));
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
        m_PendPrior = "";
        Fault();
        return HCSaveJob.STEP_FAILED;
    }

    // Reuse HC-138's three-stage pattern: serialize, inspect prior image,
    // then intent/backup/copy/readback in one uninterrupted commit stage.
    int HCCheckpointStep()
    {
        if (!m_Healthy) { return HCSaveFailed(); }
        if (m_SaveStage == 0)
        {
            m_FaultAt = "save_rows";
            if (!Valid(Data)) { return HCSaveFailed(); }
            m_FaultAt = "save_serialize";
            Data.LastWrite = HCWorldClock.UTC();
            string error;
            if (!JsonFileLoader<HCLeadData>.MakeData(Data, m_PendText, error)) { return HCSaveFailed(); }
            if (m_PendText.Length() > HCWorldStore.MAX_BYTES) { return HCSaveFailed(); }
            m_SnapshotRevision = m_Revision;
            m_PendPrior = "";
            m_SaveStage = 1;
            return HCSaveJob.STEP_MORE;
        }
        if (m_SaveStage == 1)
        {
            if (FileExist(m_Path))
            {
                m_PendPrior = HCWorldStore.Read(m_Path);
                if (!Decode(m_PendPrior)) { m_FaultAt = "save_prior_" + m_FaultAt; return HCSaveFailed(); }
            }
            m_SaveStage = 2;
            return HCSaveJob.STEP_MORE;
        }
        // A cleanup during the staged snapshot cannot resurrect a removed row.
        if (m_SnapshotRevision != m_Revision) { m_SaveStage = 0; return HCSaveJob.STEP_MORE; }
        string text = m_PendText;
        string prior = m_PendPrior;
        m_SaveStage = 0;
        m_PendText = "";
        m_PendPrior = "";
        m_FaultAt = "save_commit";
        if (!HCWorldStore.Write(m_Path + ".tmp", text)) { return HCSaveFailed(); }
        if (prior != "")
        {
            if (FileExist(m_Path + ".bak") && !DeleteFile(m_Path + ".bak")) { return HCSaveFailed(); }
            if (!CopyFile(m_Path, m_Path + ".bak") || HCWorldStore.Read(m_Path + ".bak") != prior) { return HCSaveFailed(); }
        }
        if (FileExist(m_Path) && !DeleteFile(m_Path)) { return HCSaveFailed(); }
        if (!CopyFile(m_Path + ".tmp", m_Path) || HCWorldStore.Read(m_Path) != text || !DeleteFile(m_Path + ".tmp")) { return HCSaveFailed(); }
        return HCSaveJob.STEP_DONE;
    }

    bool Save()
    {
        // Creation/read receipts remain synchronous durability barriers. Cancel
        // any older routine snapshot before serializing current authoritative Data.
        m_SaveStage = 0;
        if (m_SaveJob) { m_SaveJob.HCInFlight = false; }
        int result = HCSaveJob.STEP_MORE;
        int steps;
        while (result == HCSaveJob.STEP_MORE && steps < 3)
        {
            result = HCCheckpointStep();
            steps++;
        }
        if (m_SaveJob) { m_SaveJob.HCDirty = false; }
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
