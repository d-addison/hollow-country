// Registry insertion is owned by core; deliberately no competing registry mod.
class HCGroupModule extends HCModule
{
    protected ref HCGroupSettings m_Config;
    protected ref HCGroupService m_Service;

    override string GetName() { return "Groups"; }

    override bool IsEnabled(HCSettings settings)
    {
        if (!settings || !settings.EnableGroups) return false;
        m_Config = HCGroupStore.LoadSettings();
        if (!m_Config) Print("[HC Groups] settings unavailable or invalid; service inactive");
        return m_Config && m_Config.Enabled;
    }

    override void OnStart(HCSettings settings)
    {
        m_Service = new HCGroupService;
        if (!m_Service.Start(m_Config))
        {
            Print("[HC Groups] start refused: check settings, UTC, world and persistence; service inactive");
            m_Service = null;
            return;
        }
        DayZGame.Event_OnRPC.Insert(m_Service.OnRPC);
    }

    override void OnTick(float deltaTime)
    {
        if (m_Service) m_Service.Tick(deltaTime);
    }

    override void OnStop()
    {
        if (!m_Service) return;
        DayZGame.Event_OnRPC.Remove(m_Service.OnRPC);
        m_Service.Stop();
        m_Service = null;
    }
}

// HC-28 wraps the existing service lifecycle. The base methods remain the
// native RPC attach/detach owner; this link owns only recovery admission.
modded class HCGroupModule
{
    override void OnStart(HCSettings settings)
    {
        HCPersistenceDisposition.HCStartStore("groups");
        if (!HCPersistenceDisposition.HCLoad(settings.EnableWorld) || !HCPersistenceDisposition.HCAdmitStore("groups"))
        {
            Print("[HC Plan] HC-28 store=groups state=refused runtime=PENDING");
            return;
        }
        super.OnStart(settings);
        if (!m_Service) { HCRecoveryGate.HCClose("groups"); }
    }

    override void OnTick(float deltaTime)
    {
        if (HCRecoveryGate.HCReady("groups")) { super.OnTick(deltaTime); }
        if (m_Service && !HCGroupService.Get()) { HCRecoveryGate.HCClose("groups"); }
    }

    override void OnStop()
    {
        super.OnStop();
        HCPersistenceDisposition.HCStopStore("groups");
    }
}

// Keep the existing immutable group revision protocol and its local m_Fault
// quarantine. Close only this IO gate immediately on any store refusal; the
// original store owns parse/partial/revision diagnostics and preserves files.
modded class HCGroupStore
{
    override bool Fault()
    {
        if (m_HCDamaged) { HCRecoveryGate.HCRefuse("groups", "groups_parse_partial_or_revision_regression"); }
        else { HCRecoveryGate.HCClose("groups"); }
        return super.Fault();
    }
}

// Service stops may originate in RPC/clock validation, outside module Stop.
// Flush the healthy discovery batch before closing its own write gate.
modded class HCGroupService
{
    override void Stop()
    {
        super.Stop();
        HCRecoveryGate.HCClose("groups");
    }
}
