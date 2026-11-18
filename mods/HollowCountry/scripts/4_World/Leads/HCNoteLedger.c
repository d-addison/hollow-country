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
// 1_Core/proto/Serializer.c:57,58 (context Write/Read),
// 1_Core/proto/EnScript.c:94,852 (Class.Cast / map Count),
// 3_Game/Entities/EntityAI.c:946 (EEDelete),
// 1_Core/proto/EnScript.c:470,502 (ordered removal / RemoveItem).
// Paper is the sole created item, has no reward/loadout, and uses vanilla UI.
// Unknown/offline physical items retain cap reservations; never respawn them.
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
}

class HCNoteLedger : HCModule
{
    protected static HCNoteLedger s_Instance;
    protected ref HCLeadStore m_Store;
    protected float m_Elapsed;
    protected bool m_AdmissionPrinted;

    static HCNoteLedger Get() { return s_Instance; }
    override string GetName() { return "Notes"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableLeads; }

    static bool CanCreate(int worldCount, int sceneCount)
    {
        return worldCount >= 0 && worldCount < HCWorldLimits.NOTES && sceneCount == 0;
    }

    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings) || s_Instance) { return; }
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("Notes", true, "EXP-S1", HCV2Gates.Qualified("EXP-S1")));
            m_AdmissionPrinted = true;
        }
        m_Store = HCLeadStore.Get();
        if (!m_Store || !m_Store.Healthy()) { return; }
        s_Instance = this;
        LogCount();
    }

    void LogCount()
    {
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
        if (!m_Store || !m_Store.Healthy() || !HCWorldLimits.Token(sceneId) || !HCWorldLimits.Position(position) || !HCLeadPolicy.Valid(lead) || lead.Expires <= HCWorldClock.UTC()) { return null; }
        int sceneCount;
        if (Scene(sceneId)) { sceneCount = 1; }
        if (!CanCreate(m_Store.Data.Notes.Count(), sceneCount)) { return null; }
        string text = HCLeadPolicy.Text(lead);
        if (text == "") { RadioFallback(lead); return null; }
        HCLeadNote entry = new HCLeadNote;
        entry.Row.Id = m_Store.NextId("note");
        entry.Row.SceneId = sceneId;
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
            m_Store.Save();
            RadioFallback(lead);
            return null;
        }
        paper.GetWrittenNoteData().SetNoteText(text);
        if (paper.GetWrittenNoteData().GetNoteText() != text)
        {
            GetGame().ObjectDelete(paper);
            m_Store.Data.Notes.RemoveItem(entry);
            m_Store.Save();
            RadioFallback(lead);
            return null;
        }
        paper.HCAssignNote(entry.Row.Id);
        // Leave cleanup time before native CE expiry; carried/offline items
        // remain reserved until positively identified on a later load.
        paper.SetLifetime(entry.Expires - entry.Row.CreatedAt + 3600);
        entry.Phase = 1;
        if (!m_Store.Save()) { return paper; }
        LogCount();
        HCBodyStories bodies = HCBodyStories.Get();
        if (bodies) { bodies.Consider(sceneId, position, lead); }
        return paper;
    }

    void Read(PlayerBase player, Paper paper)
    {
        if (!m_Store || !m_Store.Healthy() || !paper || !player || !player.IsAlive() || !player.GetIdentity()) { return; }
        foreach (HCLeadNote entry : m_Store.Data.Notes)
        {
            if (entry.Row.Id != paper.HCNoteId() || entry.Expires <= HCWorldClock.UTC()) { continue; }
            HCLeadModule leads = HCLeadModule.Get();
            if (leads) { leads.ReceivePlayer(entry.Lead, player, "note"); }
            return;
        }
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Store || !m_Store.Healthy() || deltaTime <= 0) { return; }
        m_Elapsed += deltaTime;
        if (m_Elapsed < 60) { return; }
        m_Elapsed = 0;
        bool changed;
        for (int entryIndex = m_Store.Data.Notes.Count() - 1; entryIndex >= 0; entryIndex--)
        {
            HCLeadNote entry = m_Store.Data.Notes[entryIndex];
            Paper paper = HCNoteEntities.Find(entry.Row.Id);
            // No world scan; only positively identified loaded HC items. Keep
            // unresolved reservations, even past expiry, to preserve world cap.
            if (!paper || entry.Expires > HCWorldClock.UTC()) { continue; }
            if (paper.GetHierarchyParent())
            {
                // Review P1: never delete a note a player or container holds. It
                // becomes an ordinary zero-value Paper and its slot is released.
                HCNoteEntities.Forget(paper);
                paper.HCAssignNote("");
            }
            else
            {
                // Expired loose notes vanish only where no player can see them.
                if (!HCObserverTransitionGate.CanTransition(paper.GetPosition(), 500)) { continue; }
                GetGame().ObjectDelete(paper);
            }
            m_Store.Data.Notes.RemoveOrdered(entryIndex);
            changed = true;
        }
        if (changed && !m_Store.Save()) { return; }
        LogCount();
    }

    override void OnStop() { s_Instance = null; }
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

    override void OnStoreSave(ParamsWriteContext ctx)
    {
        super.OnStoreSave(ctx);
        ctx.Write(m_HCNoteId);
    }

    override bool OnStoreLoad(ParamsReadContext ctx, int version)
    {
        if (!super.OnStoreLoad(ctx, version)) { return false; }
        // Existing vanilla notes predate this optional extension.
        if (!ctx.Read(m_HCNoteId)) { m_HCNoteId = ""; }
        HCNoteEntities.Track(this);
        return true;
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
