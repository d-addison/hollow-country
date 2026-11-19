// LC-T402 / #98, EXP-L1 + EXP-P2 (runtime acceptance pending).
// Native evidence: installed scripts-1.30.164289/1_Core/proto/
// EnConvert.c:30 int.ToString; EnDebug.c:96 Print;
// EnScript.c:380,385,394,407 array Count/Clear/Find/Insert. All lifecycle, settings,
// proposal and director calls below are existing/project-owned interfaces.
// No body creation, native handles, inventories or persistence in this bridge.
// HC-10: Next has already verified the durable party/cargo claim. Wave 2 uses
// CustodyIdentity + SiteEndedTyped; no position-only ownership or refill grant.
// No new provider/native API call: the installed optional provider source path
// was unavailable for this worker. Native source inspection/boot is pending.
class HCXMaterializerBridge : HCModule
{
    protected static HCXMaterializerBridge s_Instance;
    protected bool m_Running;
    protected bool m_AdmissionPrinted;
    protected float m_LogSeconds;
    protected int m_Spawned;
    protected int m_Refused;
    protected int m_UnattributedSpawnCallbacks;
    protected ref array<string> m_Started = new array<string>();

    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "MaterializerBridge"; }

    // Wave 16: started = the bridge is the registered offer target (m_Running); the site director is resolved
    // per offer, so a missing director refuses that offer (counted) and is not a module fault.
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Running, "", "", "materializer_bridge_started");
        return m_Operational;
    }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }

    override void OnStart(HCSettings settings)
    {
        if (m_Running || !IsEnabled(settings)) { return; }
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("MaterializerBridge", true, "EXP-L1", HCV2Gates.Qualified("EXP-L1")));
            m_AdmissionPrinted = true;
        }
        m_Running = true;
        m_LogSeconds = 0;
        m_Started.Clear();
        s_Instance = this;
    }

    protected void Offer(HCWorldProposal proposal)
    {
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        string reason = "site director unavailable";
        bool admitted = false;
        if (director) { admitted = director.AdmitTransient(proposal.Id, proposal.FactionId, proposal.Position, proposal.ActorCap, reason); }
        if (admitted) { return; }
        m_Refused++;
        HCWorldMaterializer.Result(proposal.Id, false, 0);
    }

    // Director callbacks, including async route/setup refusal. Only a real
    // Spawned callback increments spawned; admission itself only reserves.
    static void SiteSpawned(string proposalId = "")
    {
        // The legacy no-ID callback cannot establish unique spawned counts.
        // Lead replaces it with SiteSpawned(spawnedState.ProposalId) in HC-18.
        if (!s_Instance || !s_Instance.m_Running) { return; }
        if (proposalId == "")
        {
            if (s_Instance.m_UnattributedSpawnCallbacks < 2147483647) { s_Instance.m_UnattributedSpawnCallbacks++; }
            return;
        }
        if (!HCWorldMaterializer.HCIdentity(proposalId)) { return; }
        if (s_Instance.m_Started.Find(proposalId) >= 0 || s_Instance.m_Started.Count() >= HCAIPartyCustody.MAX_ROWS) { return; }
        s_Instance.m_Started.Insert(proposalId);
        s_Instance.m_Spawned++;
    }
    static void SiteEnded(string proposalId, bool materialized, int survivors)
    {
        if (!materialized && s_Instance && s_Instance.m_Running) { s_Instance.m_Refused++; }
        HCWorldMaterializer.Result(proposalId, materialized, survivors);
    }

    static HCAIPartyIdentity CustodyIdentity(string proposalId)
    {
        return HCWorldMaterializer.HCIdentity(proposalId);
    }

    static void SiteEndedTyped(HCAIPartyResult result)
    {
        HCWorldMaterializer.HCTypedResult(result);
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || !(deltaTime > 0) || deltaTime > 3600) { return; }
        // One claim/tick. Director owns shared reservations, qualification,
        // native patrol triggers and the eventual death/despawn callback.
        HCWorldProposal proposal;
        if (HCWorldMaterializer.Next(proposal)) { this.Offer(proposal); }
        m_LogSeconds += deltaTime;
        if (m_LogSeconds >= 600)
        {
            m_LogSeconds = 0;
            Print("[HC Expansion AI] materializer bridge spawned=" + m_Spawned.ToString() + " unattributed_spawn_callbacks=" + m_UnattributedSpawnCallbacks.ToString() + " refused=" + m_Refused.ToString() + " runtime=PENDING");
        }
    }

    override void OnStop()
    {
        m_Running = false;
        if (s_Instance == this) { s_Instance = null; }
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCXMaterializerBridge);
    }
}
