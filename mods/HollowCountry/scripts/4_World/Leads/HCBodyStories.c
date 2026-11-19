// HC-44: real deceased AI keeps its native body, inventory and CE lifetime.
// No survivor clone, loadout, reward, cargo/cache grant, teleport or respawn.
// Inspected scripts-1.30.164289 native evidence:
// 3_Game/Global/Game.c:1120 IsServer; Entities/Object.c:215 IsPendingDeletion,
// :287 GetPosition, :517 IsAlive, :523 IsMan; Entities/EntityAI.c:1104 EEKilled.
// 3_Game/Entities/Man.c:21 GetIdentity; 1_Core/proto/EnScript.c:94 Cast,
// :380,394,407,470 Count/Find/Insert/RemoveOrdered; EnDebug.c:96 Print.
// HCUnitBudget/HCWorkBudget provide bounded maintenance. Native bodies are
// NEVER created, deleted, moved, re-equipped or given a new lifetime here.
class HCBodyStories : HCModule
{
    protected static HCBodyStories s_Instance;
    protected ref HCLeadStore m_Store;
    protected ref array<Object> m_Observed = new array<Object>();
    protected ref array<string> m_ObservedIds = new array<string>();
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected float m_Elapsed;
    protected int m_Cursor;
    protected bool m_Ready;
    protected bool m_AdmissionPrinted;
    protected bool m_StaticRefused;

    static HCBodyStories Get() { return s_Instance; }
    override string GetName() { return "BodyStories"; }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }
    override bool IsEnabled(HCSettings settings)
    {
        bool enabled = settings && settings.EnableLeads;
        if (!enabled) { m_Status.HCPublish("off", "operator_preference"); }
        return enabled;
    }
    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings) || s_Instance) { return; }
        if (!GetGame().IsServer()) { m_Status.HCPublish("refused", "SERVER_AUTHORITY_REQUIRED"); return; }
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("BodyStories", true, "EXP-S3", HCV2Gates.Qualified("EXP-S3")));
            m_AdmissionPrinted = true;
        }
        m_Store = HCLeadStore.Get();
        if (!m_Store || !m_Store.Healthy()) { m_Status.HCPublish("refused", "LEAD_STORE_UNAVAILABLE"); return; }
        m_Ready = true;
        s_Instance = this;
        m_Status.HCPublish("ready", "real_corpse_binding_only_producer_pending");
        m_Store.HCPlan("ready", "BODY_RECEIPT_PRODUCER_BINDING_PENDING");
    }

    // Legacy call signature remains safe. A scene note is not evidence of a
    // death. Explicit authored static scenery needs separate provenance; it
    // cannot impersonate a live party's casualty. No random death props remain.
    void Consider(string sceneId, vector position, HCWorldLead lead)
    {
        if (!m_Ready || m_StaticRefused || !m_Store) { return; }
        m_StaticRefused = true;
        m_Store.HCTraceRefuse("STATIC_DEATH_UNOBSERVED");
    }

    // Trusted server death producer only, with the SAME delayed shared fact
    // identity used by notes/radio. Not an RPC/config assertion. Lead must bind
    // the actual cause and reviewed scene; no live coordinates enter clue text.
    // Existing human bodies only: AI has no player identity. Native death and
    // body ownership/lifetime remain with the original provider and vanilla CE.
    bool HCObserveBody(string sceneId, HCWorldLead lead, Object corpse)
    {
        if (!m_Ready || !m_Store || !m_Store.Healthy() || !GetGame().IsServer()) { return false; }
        if (!corpse || corpse.IsPendingDeletion() || !corpse.IsMan() || corpse.IsAlive()) { return false; }
        Man deceased = Man.Cast(corpse);
        if (!deceased || deceased.GetIdentity()) { return false; }
        if (!HCWorldLimits.Token(sceneId) || !m_Store.HCResolveFact(lead)) { return false; }
        HCTraceReceipt receipt = m_Store.HCTrace(lead.Id);
        if (receipt && (receipt.BodyId != "" || receipt.SceneId != sceneId)) { return m_Store.HCTraceRefuse("DUPLICATE_FACT"); }
        int activeTraces = m_Store.Data.Notes.Count() + m_Store.Data.Bodies.Count();
        if (activeTraces >= 10 || m_Store.HCSceneTraces(m_Store.Data, sceneId) >= 3) { return false; }
        if (m_Store.Data.Bodies.Count() >= 3 || m_Observed.Find(corpse) >= 0) { return false; }
        if (!receipt) { receipt = m_Store.HCReserveTrace(lead, sceneId); }
        if (!receipt) { return false; }
        HCBodyStoryRow story = new HCBodyStoryRow;
        story.Id = m_Store.NextId("body");
        story.SceneId = sceneId;
        story.FactId = lead.Id;
        story.PlaceId = lead.TargetPlaceId;
        story.Position = corpse.GetPosition(); // already dead; never a live target
        story.CreatedAt = HCWorldClock.UTC();
        story.Expires = lead.Expires;
        story.Phase = 2; // actual corpse already exists; never replay on restart
        receipt.BodyId = story.Id;
        m_Store.Data.Bodies.Insert(story);
        if (!m_Store.Save()) { return false; }
        m_Observed.Insert(corpse);
        m_ObservedIds.Insert(story.Id);
        m_Store.HCPlan("ready", "real_body_observed_inventory_untouched");
        return true;
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Ready || !m_Store || !(deltaTime > 0)) { return; }
        if (!m_Store.Healthy()) { m_Status.HCPublish("refused", "LEAD_STORE_UNCERTAIN"); return; }
        m_Elapsed += deltaTime;
        if (m_Elapsed < 20) { return; }
        m_Elapsed = 0;
        if (m_Store.Data.Bodies.Count() == 0) { return; }
        m_Units.HCReset(1);
        m_Work.HCReset(1);
        if (!m_Units.HCTake(1) || !m_Work.HCContinue()) { return; }
        if (m_Cursor >= m_Store.Data.Bodies.Count()) { m_Cursor = 0; }
        int bodyIndex = m_Cursor;
        m_Cursor++;
        HCBodyStoryRow story = m_Store.Data.Bodies[bodyIndex];
        // Legacy unbound static intents are quarantined until expiry too.
        // No native object lookup, recreation, deletion or inventory scan.
        if (story.Expires > HCWorldClock.UTC()) { return; }
        int observedIndex = m_ObservedIds.Find(story.Id);
        if (observedIndex >= 0)
        {
            m_Observed.RemoveOrdered(observedIndex);
            m_ObservedIds.RemoveOrdered(observedIndex);
        }
        m_Store.Data.Bodies.RemoveOrdered(bodyIndex);
        m_Store.HCRequestCheckpoint();
    }

    override void OnStop()
    {
        m_Ready = false;
        m_Observed.Clear();
        m_ObservedIds.Clear();
        m_Store = null;
        s_Instance = null;
        m_Status.HCPublish("off", "stopped");
    }
}
