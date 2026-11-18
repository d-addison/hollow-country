// LC-T402 / #98. Native evidence: installed scripts-1.30.164289/
// 1_Core/proto/EnConvert.c:30 int.ToString; EnDebug.c:96 Print.
// Only project APIs otherwise. No Expansion classes copied or native actor API
// called. HCXAISites.c:810 protected Create needs an owned, bound and route-
// qualified state; :916 SpawnProblemFor budgets only its own m_States. The
// public States() is explicitly read-only for encounter consumers (:184).
// Therefore an arbitrary transient site cannot safely join that director from
// this scope. Required fallback: refuse, report traces, create zero bodies.
// A future director-owned transient admission API must reserve within the SAME
// 8-body/2-site budget, qualify routes, observe each spawn/despawn, then report
// group absence and survivors through HCWorldMaterializer.Result. EXP-L1/P2
// runtime and two-client acceptance remain pending.
class HCXMaterializerBridge : HCModule
{
    protected bool m_Running;
    protected bool m_RefusalPrinted;
    protected float m_LogSeconds;
    protected int m_Refused;

    override string GetName() { return "MaterializerBridge"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }

    override void OnStart(HCSettings settings)
    {
        if (m_Running || !IsEnabled(settings)) { return; }
        m_Running = true;
        m_LogSeconds = 0;
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || !(deltaTime > 0) || deltaTime > 3600) { return; }
        // One claim/tick; no player data, world scans, actor/item operations or
        // mutation of the existing qualified site director's states.
        HCWorldProposal proposal;
        if (HCWorldMaterializer.Next(proposal))
        {
            m_Refused++;
            if (!m_RefusalPrinted)
            {
                Print("[HC Expansion AI] materializer bridge refused: qualified site director has no transient admission API; traces only");
                m_RefusalPrinted = true;
            }
            HCWorldMaterializer.Result(proposal.Id, false, 0);
        }
        m_LogSeconds += deltaTime;
        if (m_LogSeconds >= 600)
        {
            m_LogSeconds = 0;
            Print("[HC Expansion AI] materializer bridge spawned=0 refused=" + m_Refused.ToString());
        }
    }

    override void OnStop() { m_Running = false; }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCXMaterializerBridge);
    }
}
