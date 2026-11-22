// HC-44: real deceased AI keeps its native body, inventory and CE lifetime.
// No survivor clone, loadout, reward, cargo/cache grant, teleport or respawn.
// Inspected scripts-1.30.164289 native evidence:
// 3_Game/Global/Game.c:1120 IsServer; Entities/Object.c:215 IsPendingDeletion,
// :287 GetPosition, :517 IsAlive, :523 IsMan; Entities/EntityAI.c:1104 EEKilled.
// 3_Game/Entities/Man.c:21 GetIdentity; 1_Core/proto/EnScript.c:94 Cast,
// :380,394,407,470 Count/Find/Insert/RemoveOrdered; EnDebug.c:96 Print.
// HCUnitBudget/HCWorkBudget provide bounded maintenance. Native bodies are
// NEVER created, deleted, moved, re-equipped or given a new lifetime here.
// Optional profile body-stories.json. Effective limits can only lower the
// existing HCLeadStore ceilings; changing tuning never invalidates saved rows.
// Native: EnSystem.c:397 FileExist; JsonFileLoader.c:69 LoadData.
class HCBodyStoryConfig
{
    int MaxBodies = 3;
    int MaxActiveTraces = 10;
    int MaxSceneTraces = 3;
    float MaintenanceSeconds = 20;

    void HCApply(HCBodyStoryConfig decoded, string text)
    {
        if (HCJsonFields.Has(text, "MaxBodies")) { MaxBodies = decoded.MaxBodies; }
        if (HCJsonFields.Has(text, "MaxActiveTraces")) { MaxActiveTraces = decoded.MaxActiveTraces; }
        if (HCJsonFields.Has(text, "MaxSceneTraces")) { MaxSceneTraces = decoded.MaxSceneTraces; }
        if (HCJsonFields.Has(text, "MaintenanceSeconds")) { MaintenanceSeconds = decoded.MaintenanceSeconds; }
        // Registry mirror integration is external to this worker's scope. Its
        // missing rows use the same bounded fallback; ceilings stay local.
        if ((HCOperatorSettingsRegistry.HCFind("BodyStories.MaxBodies") && !HCOperatorSettingsRegistry.HCValid("BodyStories.MaxBodies", MaxBodies)) || MaxBodies < 1 || MaxBodies > 3) { MaxBodies = 3; }
        if ((HCOperatorSettingsRegistry.HCFind("BodyStories.MaxActiveTraces") && !HCOperatorSettingsRegistry.HCValid("BodyStories.MaxActiveTraces", MaxActiveTraces)) || MaxActiveTraces < 1 || MaxActiveTraces > 10) { MaxActiveTraces = 10; }
        if ((HCOperatorSettingsRegistry.HCFind("BodyStories.MaxSceneTraces") && !HCOperatorSettingsRegistry.HCValid("BodyStories.MaxSceneTraces", MaxSceneTraces)) || MaxSceneTraces < 1 || MaxSceneTraces > 3) { MaxSceneTraces = 3; }
        if ((HCOperatorSettingsRegistry.HCFind("BodyStories.MaintenanceSeconds") && !HCOperatorSettingsRegistry.HCValid("BodyStories.MaintenanceSeconds", MaintenanceSeconds)) || MaintenanceSeconds < 1 || MaintenanceSeconds > 300 || MaintenanceSeconds != MaintenanceSeconds) { MaintenanceSeconds = 20; }
    }

    static HCBodyStoryConfig HCLoad()
    {
        HCBodyStoryConfig config = new HCBodyStoryConfig;
        string path = "$profile:HollowCountry/body-stories.json";
        if (!FileExist(path)) { return config; }
        string text;
        string error;
        HCBodyStoryConfig decoded;
        if (!HCGroupIO.Read(path, 4096, text) || !JsonFileLoader<HCBodyStoryConfig>.LoadData(text, decoded, error) || !decoded)
        {
            Print("[HC BodyStories] CONFIG_INVALID defaults_retained runtime=PENDING");
            return config;
        }
        config.HCApply(decoded, text);
        return config;
    }
}

// Optional provider seam; the base addon never names Expansion types.
class HCBodyStoryProducer
{
    bool HCReady() { return false; }
}

// Process-local native observations. Restart never recreates a corpse/receipt.
class HCBodyStoryObservation
{
    string SceneId;
    ref HCWorldFact Fact;
    Object Corpse;
}

class HCBodyStories : HCModule
{
    protected static HCBodyStories s_Instance;
    protected static ref HCBodyStoryProducer s_Producer;
    protected ref HCBodyStoryConfig m_Config;
    protected ref array<ref HCBodyStoryObservation> m_Pending = new array<ref HCBodyStoryObservation>;
    protected int m_PendingCursor;
    protected string m_LastRefusal;
    protected ref HCLeadStore m_Store;
    protected ref array<Object> m_Observed = new array<Object>();
    protected ref array<string> m_ObservedIds = new array<string>();
    protected ref array<int> m_ReceiptRevisions = new array<int>;
    protected int m_ReceiptCursor;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected float m_Elapsed;
    protected int m_Cursor;
    protected bool m_Ready;
    protected bool m_AdmissionPrinted;
    protected bool m_StaticRefused;

    static HCBodyStories Get() { return s_Instance; }
    static void HCBindProducer(HCBodyStoryProducer producer) { s_Producer = producer; }

    bool HCRefuse(string reason)
    {
        if (m_LastRefusal != reason)
        {
            m_LastRefusal = reason;
            Print("[HC BodyStories] refused reason=" + reason + " runtime=PENDING");
        }
        return false;
    }

    void HCRefreshStatus()
    {
        if (!m_Ready) { return; }
        if (!m_Store || !m_Store.Healthy()) { m_Status.HCPublish("refused", "LEAD_STORE_UNCERTAIN"); return; }
        if (!s_Producer || !s_Producer.HCReady()) { m_Status.HCPublish("degraded", "BODY_SCENE_PRODUCER_UNAVAILABLE"); return; }
        if (!HCWorldModule.Get()) { m_Status.HCPublish("degraded", "WORLD_FACT_PROVIDER_UNAVAILABLE"); return; }
        m_Status.HCPublish("ready", "owned_scene_death_producer_bound_runtime_pending");
    }
    bool HCCanObserveOwnedDeath()
    {
        if (!m_Ready || !m_Store || !m_Store.Healthy()) { return false; }
        if (m_Pending.Count() + m_Store.Data.Bodies.Count() >= m_Config.MaxBodies) { return HCRefuse("OBSERVED_BODY_CAP"); }
        return true;
    }

    // Only the server provider calls this after observing an owned death in a
    // retained situation story. The fact is detached from HCWorldModule after
    // AddFact, not a client/config allegation. The original identity is retained.
    void HCQueueOwnedDeath(string sceneId, HCWorldFact fact, Object corpse)
    {
        if (!m_Ready || !m_Store || !m_Store.Healthy() || !fact || !corpse) { return; }
        if (!HCWorldLimits.Token(sceneId) || !HCLeadPolicy.KnownPlace(fact.PlaceId)) { return; }
        if (!HCCanObserveOwnedDeath()) { return; }
        array<ref HCBodyStoryObservation> pending = m_Pending;
        foreach (HCBodyStoryObservation prior : pending)
        {
            if (prior.Corpse == corpse) { return; }
        }
        HCBodyStoryObservation observation = new HCBodyStoryObservation;
        observation.SceneId = sceneId;
        observation.Fact = fact;
        observation.Corpse = corpse;
        m_Pending.Insert(observation);
        Print("[HC BodyStories] OWNED_DEATH_CAPTURED delayed_fact_pending runtime=PENDING");
    }

    protected void HCProcessObservedDeath()
    {
        if (m_Pending.Count() == 0) { return; }
        if (m_PendingCursor >= m_Pending.Count()) { m_PendingCursor = 0; }
        int pendingIndex = m_PendingCursor;
        m_PendingCursor++;
        HCBodyStoryObservation observation = m_Pending[pendingIndex];
        Object corpse = observation.Corpse;
        int now = HCWorldClock.UTC();
        if (!corpse || corpse.IsPendingDeletion() || corpse.IsAlive() || observation.Fact.Expires <= now)
        {
            m_Pending.RemoveOrdered(pendingIndex);
            HCRefuse("OBSERVED_CORPSE_OR_FACT_EXPIRED");
            return;
        }
        HCWorldLead lead = new HCWorldLead;
        if (!HCLeadPolicy.Build(observation.Fact, lead, observation.Fact.PlaceId, HCLeadPolicy.Kind(observation.Fact.Kind), now)) { return; }
        lead.Id = m_Store.HCFactId(observation.Fact);
        lead.Source = "world";
        // Always re-resolve against the current world ledger. Missing history
        // is not permission to manufacture a replacement fact or body.
        if (!m_Store.HCResolveFact(lead))
        {
            m_Pending.RemoveOrdered(pendingIndex);
            HCRefuse("OBSERVED_WORLD_FACT_NO_LONGER_AVAILABLE");
            return;
        }
        HCObserveBody(observation.SceneId, lead, corpse);
        // A receipt refusal/cap is terminal for this observation, never replayed.
        m_Pending.RemoveOrdered(pendingIndex);
    }

    override string GetName() { return "BodyStories"; }
    override int StartupPhase() { return HC_PHASE_FEATURE; }
    override void RegisterUses() { HCModuleReadiness.HCRegisterUse("BodyStories", "body_observed"); }
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
        m_Config = HCBodyStoryConfig.HCLoad();
        s_Instance = this;
    }

    override void OnAllModulesStarted()
    {
        if (s_Instance != this) { return; }
        // Leads, World and the optional death producer have all started now.
        m_Store = HCLeadStore.Get();
        if (!m_Store || !m_Store.Healthy()) { m_Status.HCPublish("refused", "LEAD_STORE_UNAVAILABLE"); return; }
        m_Ready = true;
        HCRefreshStatus();
        Print("[HC BodyStories] BODY_SCENE_PRODUCER_ADMITTED state=" + m_Status.HCState() + " reason=" + m_Status.HCReason() + " runtime=PENDING");
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
    // an existing scene context; the native callback, not that earlier fact,
    // proves death. No new claim about the killer/cause or clue text is made.
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
        // A note and the real corpse for the same fact share one receipt by design.
        if (receipt && (receipt.BodyId != "" || receipt.SceneId != sceneId)) { return m_Store.HCTraceRefuse("DUPLICATE_FACT"); }
        int activeTraces = m_Store.Data.Notes.Count() + m_Store.Data.Bodies.Count();
        if (activeTraces >= m_Config.MaxActiveTraces || m_Store.HCSceneTraces(m_Store.Data, sceneId) >= m_Config.MaxSceneTraces) { return HCRefuse("OBSERVED_TRACE_CAP"); }
        if (m_Store.Data.Bodies.Count() >= m_Config.MaxBodies || m_Observed.Find(corpse) >= 0) { return HCRefuse("OBSERVED_BODY_CAP_OR_DUPLICATE"); }
        string bodyId = m_Store.NextId("body");
        if (bodyId == "") { return false; } // serial cap: never leave an id-less receipt
        if (!receipt) { receipt = m_Store.HCReserveTrace(lead, sceneId); }
        if (!receipt) { return false; }
        HCBodyStoryRow story = new HCBodyStoryRow;
        story.Id = bodyId;
        story.SceneId = sceneId;
        story.FactId = lead.Id;
        story.PlaceId = lead.TargetPlaceId;
        story.Position = corpse.GetPosition(); // already dead; never a live target
        story.CreatedAt = HCWorldClock.UTC();
        story.Expires = lead.Expires;
        story.Phase = 2; // actual corpse already exists; never replay on restart
        receipt.BodyId = story.Id;
        m_Store.Data.Bodies.Insert(story);
        // This is an observation of an already-dead native body, with no
        // creation, inventory mutation or replay. Reserve in memory immediately;
        // the shared checkpoint owns schedule/shutdown durability.
        int revision = m_Store.HCRequestBarrier();
        if (revision < 0) { HCRefreshStatus(); return false; }
        m_Observed.Insert(corpse);
        HCModuleReadiness.HCUse("BodyStories", "body_observed");
        m_ObservedIds.Insert(story.Id);
        m_ReceiptRevisions.Insert(revision);
        m_LastRefusal = "";
        HCRefreshStatus();
        return true;
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Ready || !m_Store || !(deltaTime > 0)) { return; }
        HCRefreshStatus();
        if (!m_Store.Healthy()) { return; }
        if (m_ReceiptRevisions.Count() > 0)
        {
            if (m_ReceiptCursor >= m_ReceiptRevisions.Count()) { m_ReceiptCursor = 0; }
            int receipt = m_ReceiptRevisions[m_ReceiptCursor];
            if (receipt >= 0 && m_Store.HCDurable(receipt))
            {
                m_ReceiptRevisions[m_ReceiptCursor] = -1;
                m_Store.HCPlan(m_Status.HCState(), "BODY_SCENE_RECEIPT_BOUND_inventory_untouched");
            }
            m_ReceiptCursor++;
        }
        m_Elapsed += deltaTime;
        if (m_Elapsed < m_Config.MaintenanceSeconds) { return; }
        m_Elapsed = 0;
        m_Units.HCReset(1);
        m_Work.HCReset(1);
        if (!m_Units.HCTake(1) || !m_Work.HCContinue()) { return; }
        HCProcessObservedDeath();
        HCReached.Mark("body_stories.death_check");
        if (!m_Store.Healthy() || m_Store.Data.Bodies.Count() == 0) { return; }
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
            m_ReceiptRevisions.RemoveOrdered(observedIndex);
        }
        m_Store.Data.Bodies.RemoveOrdered(bodyIndex);
        m_Store.HCRequestCheckpoint();
    }

    override void OnStop()
    {
        m_Ready = false;
        m_Pending.Clear();
        m_Observed.Clear();
        m_ObservedIds.Clear();
        m_ReceiptRevisions.Clear();
        m_ReceiptCursor = 0;
        m_Store = null;
        s_Instance = null;
        m_Status.HCPublish("off", "stopped");
    }
}

// Detached active-lease context for the optional server death producer. Reading
// the lease's admitted place avoids using a travelling party's home as its
// death location. No ledger mutation or native object ownership is exposed.
modded class HCWorldMaterializer
{
    static HCWorldProposal HCBodyProposal(string leaseId)
    {
        if (!s_Instance || !s_Instance.m_Running) { return null; }
        array<ref HCWorldProposalLease> leases = s_Instance.m_Active;
        foreach (HCWorldProposalLease lease : leases)
        {
            if (!lease || !lease.Claimed || lease.Finished || !lease.Proposal || lease.Proposal.Id != leaseId) { continue; }
            HCWorldProposal copy = new HCWorldProposal;
            copy.Id = lease.Proposal.Id;
            copy.PlaceId = lease.Proposal.PlaceId;
            copy.FactionId = lease.Proposal.FactionId;
            copy.ActorCap = lease.Proposal.ActorCap;
            return copy;
        }
        return null;
    }
}
