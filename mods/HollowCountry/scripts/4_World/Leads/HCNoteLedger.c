// LC-T308, #92. Native evidence: scripts-1.30.164289/
// 4_World/Entities/ItemBase/Paper.c:12,23,30 (store/load/written data),
// 4_World/Classes/WrittenNoteData.c:73,78 (GetNoteText/SetNoteText),
// 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionReadPaper.c:23-24
// (native read-note RPC), :31 (deprecated action retained in installed scripts),
// 4_World/Entities/ItemBase/Paper.c:65 (SetActions),
// 3_Game/Global/Game.c:703,705 (CreateObjectEx/ObjectDelete),
// 3_Game/Entities/EntityAI.c:3377 (SetLifetime),
// 3_Game/Entities/Object.c:287 (GetPosition),
// 3_Game/Systems/Inventory/Inventory.c:127,134 (read-only inventory),
// 1_Core/proto/EnScript.c:877,902,906,917 (map find/set/remove/contains),
// 4_World/Entities/ItemBase.c:255 (AddAction),
// 4_World/Classes/UserActionsComponent/ActionBase.c:1391 (OnStartServer),
// 4_World/Classes/UserActionsComponent/ActionConstructor.c:27 (RegisterActions),
// 5_Mission/mission/missionBase.c:257 (native note menu remains registered).
// 3_Game/Entities/EntityAI.c:1419 and 4_World/Entities/ItemBase.c:3222
// (AfterStoreLoad). No HC field is added to Paper storage: the vanilla note text
// persists and identifies an HC note after a restart (native compile 009 showed
// an extra stored field corrupting every Paper saved before it existed).
// 1_Core/proto/EnScript.c:94,852 (Class.Cast / map Count),
// 3_Game/Entities/EntityAI.c:946 (EEDelete),
// 1_Core/proto/EnScript.c:470,502 (ordered removal / RemoveItem).
// HC-44 authority: 3_Game/Global/Game.c:1120 IsServer.
// Paper is the sole created item, has no reward/loadout, and uses vanilla UI.
// Unknown/offline items retain reservations until one day past lead expiry.
class HCNoteEntities
{
    protected static ref map<string, Paper> s_Entities;

    static void Track(Paper paper)
    {
        if (!paper || paper.HCNoteId() == "") { return; }
        if (!s_Entities) { s_Entities = new map<string, Paper>(); }
        if (s_Entities.Count() >= 10 && !s_Entities.Contains(paper.HCNoteId())) { return; }
        s_Entities.Set(paper.HCNoteId(), paper);
    }

    static Paper Find(string id)
    {
        if (!s_Entities) { return null; }
        Paper paper;
        s_Entities.Find(id, paper);
        return paper;
    }

    static void Forget(Paper paper)
    {
        if (paper && s_Entities && Find(paper.HCNoteId()) == paper) { s_Entities.Remove(paper.HCNoteId()); }
    }

    // Papers restored from storage with written text wait here until the
    // ledger matches them by text. Bounded; blank Papers are never queued.
    protected static ref array<Paper> s_Loaded;

    static void Loaded(Paper paper)
    {
        if (!paper || !paper.GetWrittenNoteData() || paper.GetWrittenNoteData().GetNoteText() == "") { return; }
        if (!s_Loaded) { s_Loaded = new array<Paper>(); }
        if (s_Loaded.Count() >= 32) { return; }
        s_Loaded.Insert(paper);
    }

    static array<Paper> TakeLoaded()
    {
        array<Paper> loaded = s_Loaded;
        s_Loaded = null;
        return loaded;
    }
}

class HCTraceDefaults
{
    // Existing 500 m cleanup guard, now named: half the vanilla ~1000 m
    // network bubble / ~1 km rifle hearing anchor. Provisional, not visibility proof.
    float CleanupQuietMetres = 500;
}

// Native EnScript.c:877/926 map.Find/Insert; candidate arrays preserve ledger order.
class HCNoteTextMatches
{
    ref array<ref HCLeadNote> Entries = new array<ref HCLeadNote>;
    int Cursor;

    HCLeadNote HCTake()
    {
        while (Cursor < Entries.Count())
        {
            HCLeadNote entry = Entries[Cursor];
            Cursor++;
            if (!HCNoteEntities.Find(entry.Row.Id)) { return entry; }
        }
        return null;
    }
}

class HCNoteLedger : HCModule
{
    protected static HCNoteLedger s_Instance;
    protected ref HCLeadStore m_Store;
    protected float m_Elapsed;
    protected float m_LogElapsed = 600;
    protected int m_LastCount = -1;
    protected bool m_AdmissionPrinted;
    protected bool m_Ready;
    protected string m_LastRefusal;
    protected int m_Cursor;
    protected ref HCTraceDefaults m_Defaults = new HCTraceDefaults;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;

    static HCNoteLedger Get() { return s_Instance; }
    override string GetName() { return "Notes"; }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }
    override bool IsEnabled(HCSettings settings)
    {
        bool enabled = settings && settings.EnableLeads;
        if (!enabled)
        {
            m_Status.HCPublish("off", "operator_preference");
            Print("[HC Plan] HC-44 facts=0 traces=0 duplicate_refusals=0 state=off reason=operator_preference runtime=PENDING");
        }
        return enabled;
    }

    protected void HCRefuse(string reason)
    {
        m_Status.HCPublish("refused", reason);
        if (m_LastRefusal == reason) { return; }
        m_LastRefusal = reason;
        if (m_Store) { m_Store.HCTraceRefuse(reason); }
    }

    string HCText(HCLeadNote entry)
    {
        if (entry.NativeText != "") { return entry.NativeText; }
        return HCLeadPolicy.Text(entry.Lead);
    }

    static bool CanCreate(int worldCount, int sceneCount)
    {
        return worldCount >= 0 && worldCount < HCWorldLimits.NOTES && sceneCount == 0;
    }

    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings) || s_Instance) { return; }
        if (!GetGame().IsServer()) { HCRefuse("SERVER_AUTHORITY_REQUIRED"); return; }
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("Notes", true, "EXP-S1", HCV2Gates.Qualified("EXP-S1")));
            m_AdmissionPrinted = true;
        }
        m_Store = HCLeadStore.Get();
        if (!m_Store || !m_Store.Healthy()) { HCRefuse("LEAD_STORE_UNAVAILABLE"); return; }
        m_Ready = true;
        s_Instance = this;
        m_Status.HCPublish("ready", "observed_fact_notes_native_acceptance_pending");
        m_Store.HCPlan("ready", "observed_fact_notes");
        ResolveLoaded();
        LogCount();
    }

    protected ref map<string, ref HCNoteTextMatches> m_LoadedText;

    protected void HCIndexText(string text, HCLeadNote entry)
    {
        HCNoteTextMatches matches;
        if (!m_LoadedText.Find(text, matches))
        {
            matches = new HCNoteTextMatches;
            m_LoadedText.Insert(text, matches);
        }
        matches.Entries.Insert(entry);
    }

    // Re-identify restored HC notes by their exact vanilla note text.
    protected void ResolveLoaded()
    {
        array<Paper> loaded = HCNoteEntities.TakeLoaded();
        if (!loaded) { return; }
        m_LoadedText = new map<string, ref HCNoteTextMatches>;
        foreach (HCLeadNote indexed : m_Store.Data.Notes)
        {
            if (!indexed || HCNoteEntities.Find(indexed.Row.Id)) { continue; }
            string current = HCText(indexed);
            HCIndexText(current, indexed);
            if (indexed.NativeText == "")
            {
                string legacy = HCLeadPolicy.LegacyText(indexed.Lead);
                if (legacy != current) { HCIndexText(legacy, indexed); }
            }
        }
        foreach (Paper paper : loaded)
        {
            if (!paper || paper.HCNoteId() != "" || !paper.GetWrittenNoteData()) { continue; }
            string noteText = paper.GetWrittenNoteData().GetNoteText();
            HCNoteTextMatches matches;
            if (!m_LoadedText.Find(noteText, matches)) { continue; }
            HCLeadNote entry = matches.HCTake();
            if (entry) { paper.HCAssignNote(entry.Row.Id); }
        }
        m_LoadedText = null;
    }

    void LogCount()
    {
        int count = m_Store.Data.Notes.Count();
        if (count == m_LastCount && m_LogElapsed < 600) { return; }
        m_LastCount = count;
        m_LogElapsed = 0;
        Print("[HollowCountry] V2 notes world=" + m_Store.Data.Notes.Count().ToString() + "/10");
    }

    HCLeadNote Scene(string sceneId)
    {
        if (!m_Store || !m_Store.Healthy()) { return null; }
        foreach (HCLeadNote entry : m_Store.Data.Notes)
        {
            if (entry.Row.SceneId == sceneId) { return entry; }
        }
        return null;
    }

    void RadioFallback(HCWorldLead lead)
    {
        HCRadioChatter radio = HCRadioChatter.Get();
        if (radio) { radio.Fallback(lead); }
    }

    Paper Create(string sceneId, vector position, HCWorldLead lead)
    {
        if (!m_Ready || !GetGame().IsServer() || !m_Store || !m_Store.Healthy() || !HCWorldLimits.Token(sceneId) || !HCWorldLimits.Position(position) || !HCLeadPolicy.Valid(lead) || lead.Expires <= HCWorldClock.UTC()) { return null; }
        int sceneCount;
        if (Scene(sceneId)) { sceneCount = 1; }
        int activeTraces = m_Store.Data.Notes.Count() + m_Store.Data.Bodies.Count();
        if (!CanCreate(activeTraces, sceneCount) || m_Store.HCSceneTraces(m_Store.Data, sceneId) >= 3) { return null; }
        string text = m_Store.HCTraceText(lead);
        if (text == "") { RadioFallback(lead); return null; }
        string noteId = m_Store.NextId("note");
        if (noteId == "") { return null; } // serial cap: never leave an id-less receipt
        HCTraceReceipt receipt = m_Store.HCReserveTrace(lead, sceneId);
        if (!receipt) { return null; }
        HCLeadNote entry = new HCLeadNote;
        entry.Row.Id = noteId;
        entry.Row.SceneId = sceneId;
        receipt.NoteId = entry.Row.Id;
        entry.NativeText = text;
        entry.Row.EntityRef = entry.Row.Id;
        entry.Row.CreatedAt = HCWorldClock.UTC();
        entry.Row.TextId = lead.TextId;
        entry.Lead = HCLeadPolicy.Copy(lead);
        entry.Expires = lead.Expires;
        m_Store.Data.Notes.Insert(entry);
        // Durable reservation precedes entity creation. An interrupted spawn is
        // quarantined in its slot, never replayed into a second physical note.
        if (!m_Store.Save()) { return null; }
        Paper paper = Paper.Cast(GetGame().CreateObjectEx("Paper", position, ECE_PLACE_ON_SURFACE));
        if (!paper || !paper.GetWrittenNoteData())
        {
            if (paper) { GetGame().ObjectDelete(paper); }
            m_Store.Data.Notes.RemoveItem(entry);
            m_Store.HCRequestCheckpoint(); // rollback of an unspawned note; the reservation barrier above already held
            RadioFallback(lead);
            return null;
        }
        paper.GetWrittenNoteData().SetNoteText(text);
        if (paper.GetWrittenNoteData().GetNoteText() != text)
        {
            GetGame().ObjectDelete(paper);
            m_Store.Data.Notes.RemoveItem(entry);
            m_Store.HCRequestCheckpoint(); // rollback of an unspawned note; the reservation barrier above already held
            RadioFallback(lead);
            return null;
        }
        paper.HCAssignNote(entry.Row.Id);
        // Leave cleanup time before native CE expiry; carried/offline items
        // remain reserved until positively identified on a later load.
        paper.SetLifetime(entry.Expires - entry.Row.CreatedAt + 3600);
        entry.Phase = 1;
        m_Store.HCRequestCheckpoint(); // materialized marker; the reserved row is already durable
        LogCount();
        // A factual note never implies a death or authorizes a corpse/cache.
        m_Store.HCPlan("ready", "note_reserved_once");
        return paper;
    }

    void Read(PlayerBase player, Paper paper)
    {
        if (!m_Ready || !GetGame().IsServer() || !m_Store || !m_Store.Healthy() || !paper || !player || !player.IsAlive() || !player.GetIdentity()) { return; }
        if (!paper.GetWrittenNoteData()) { return; }
        foreach (HCLeadNote entry : m_Store.Data.Notes)
        {
            if (entry.Row.Id != paper.HCNoteId() || entry.Expires <= HCWorldClock.UTC()) { continue; }
            if (paper.GetWrittenNoteData().GetNoteText() != HCText(entry)) { return; }
            HCLeadModule leads = HCLeadModule.Get();
            if (leads) { leads.ReceivePlayer(entry.Lead, player, "note"); }
            return;
        }
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Ready || !m_Store || !(deltaTime > 0)) { return; }
        if (!m_Store.Healthy()) { HCRefuse("LEAD_STORE_UNCERTAIN"); return; }
        m_Elapsed += deltaTime;
        m_LogElapsed += deltaTime;
        if (m_Elapsed < 60) { return; }
        m_Elapsed = 0;
        m_Units.HCReset(1);
        m_Work.HCReset(1);
        if (!m_Units.HCTake(1) || !m_Work.HCContinue()) { return; }
        ResolveLoaded(); // <=32 restored handles x <=10 notes, no world scan
        HCReached.Mark("note_ledger.resolve");
        if (m_Store.Data.Notes.Count() == 0) { return; }
        if (m_Cursor >= m_Store.Data.Notes.Count()) { m_Cursor = 0; }
        int entryIndex = m_Cursor;
        m_Cursor++;
        HCLeadNote entry = m_Store.Data.Notes[entryIndex];
        Paper paper = HCNoteEntities.Find(entry.Row.Id);
        int now = HCWorldClock.UTC();
        if (!paper)
        {
            // Offline inventory is unknown; grace releases only the active
            // slot. Permanent fact receipts remain and cannot refill it.
            if (now <= entry.Expires + 86400) { return; }
        }
        else
        {
            if (entry.Expires > now) { return; }
            if (paper.GetHierarchyParent())
            {
                HCNoteEntities.Forget(paper);
                paper.HCAssignNote("");
            }
            else
            {
                array<Man> observers = HCPerfPlayers.HCGet();
                if (!observers || observers.Count() > 32) { return; }
                if (!HCObserverTransitionGate.CanTransition(paper.GetPosition(), m_Defaults.CleanupQuietMetres)) { return; }
                GetGame().ObjectDelete(paper);
            }
        }
        m_Store.Data.Notes.RemoveOrdered(entryIndex);
        m_Store.HCRequestCheckpoint();
        LogCount();
    }

    override void OnStop()
    {
        m_Ready = false;
        if (m_Store) { m_Store.HCCloseCheckpoint(); }
        m_Store = null;
        s_Instance = null;
        m_Status.HCPublish("off", "stopped");
    }
}

modded class Paper
{
    protected string m_HCNoteId;

    string HCNoteId() { return m_HCNoteId; }
    void HCAssignNote(string id)
    {
        m_HCNoteId = id;
        HCNoteEntities.Track(this);
    }

    override void AfterStoreLoad()
    {
        super.AfterStoreLoad();
        HCNoteEntities.Loaded(this);
    }

    override void EEDelete(EntityAI parent)
    {
        HCNoteEntities.Forget(this);
        super.EEDelete(parent);
    }

    override void SetActions()
    {
        super.SetActions();
        AddAction(ActionReadPaper);
    }
}

modded class ActionReadPaper
{
    override void OnStartServer(ActionData action_data)
    {
        super.OnStartServer(action_data);
        HCNoteLedger ledger = HCNoteLedger.Get();
        if (ledger) { ledger.Read(action_data.m_Player, Paper.Cast(action_data.m_MainItem)); }
    }
}

// Vanilla retains the deprecated action implementation but no longer registers
// it. Both client and server must construct it before Paper.AddAction can work.
modded class ActionConstructor
{
    override void RegisterActions(TTypenameArray actions)
    {
        super.RegisterActions(actions);
        if (actions.Find(ActionReadPaper) < 0) { actions.Insert(ActionReadPaper); }
    }
}
