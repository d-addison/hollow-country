// Entry-local roster port: native scripts-1.30.164289 3_Game/Global/Game.c:945;
// resolver identity/life: Entities/Man.c:21, gameplay.c:368, Entities/Object.c:517.
// Registry insertion is owned by core; deliberately no competing registry mod.
class HCGroupModule extends HCModule
{
    protected ref HCGroupSettings m_Config;
    protected ref HCGroupService m_Service;
    // Wave 16: cached readiness derived from the live service, never hard-coded.
    protected string m_Refusal;
    protected string m_AdmissionReason;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "Groups"; }

    // Ready = the service started and the recovery gate is open. A started service whose gate was closed by
    // a store refusal is degraded (a real fault), a start that was refused reports the refusal.
    override HCOperationalStatus HCGetOperationalStatus()
    {
        bool started = false;
        string fault = "";
        if (m_Service) { started = true; }
        if (started && !HCRecoveryGate.HCReady("groups")) { fault = "recovery_gate_closed"; }
        HCModuleReadiness.HCDerive(m_Operational, started, m_Refusal, fault, "group_service_started");
        if (!started && m_Refusal == "" && m_AdmissionReason != "") { m_Operational.HCPublish("off", m_AdmissionReason); }
        return m_Operational;
    }

    override bool IsEnabled(HCSettings settings)
    {
        m_Refusal = "";
        m_AdmissionReason = "";
        if (!settings) { m_Refusal = "core_settings_unavailable"; return false; }
        if (!settings.EnableGroups) { m_AdmissionReason = "core_groups_disabled"; return false; }
        m_Config = HCGroupStore.LoadSettings(m_Refusal);
        if (!m_Config)
        {
            Print("[HC Groups] settings refused reason=" + m_Refusal + "; files preserved; service inactive");
            return false;
        }
        if (!m_Config.Enabled) { m_AdmissionReason = "groups_settings_disabled"; return false; }
        return true;
    }

    override void OnStart(HCSettings settings)
    {
        m_Service = new HCGroupService;
        if (!m_Service.Start(m_Config))
        {
            Print("[HC Groups] start refused: check settings, UTC, world and persistence; service inactive");
            m_Refusal = m_Service.Refusal();
            if (m_Refusal == "") { m_Refusal = "service_start_refused"; }
            m_Service = null;
            return;
        }
        DayZGame.Event_OnRPC.Insert(m_Service.OnRPC);
        HCReached.Mark("groups.rpc_bind");
    }

    override void OnTick(float deltaTime)
    {
        if (m_Service) m_Service.Tick(deltaTime);
    }

    override void OnStop()
    {
        if (!m_Service) return;
        map<string, PlayerBase> hcPlayers = HCGroupService.HCBuildPlayers();
        DayZGame.Event_OnRPC.Remove(m_Service.OnRPC);
        m_Service.Stop(hcPlayers);
        m_Service = null;
    }
}

// HC-28 wraps the existing service lifecycle. The base methods remain the
// native RPC attach/detach owner; this link owns only recovery admission.
modded class HCGroupModule
{
    override void OnStart(HCSettings settings)
    {
        m_Refusal = "";
        HCPersistenceDisposition.HCStartStore("groups");
        if (!HCPersistenceDisposition.HCLoad(settings.EnableWorld) || !HCPersistenceDisposition.HCAdmitStore("groups"))
        {
            Print("[HC Plan] HC-28 store=groups state=refused runtime=PENDING");
            m_Refusal = "recovery_gate_refused_groups_store";
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
    override void Stop(map<string, PlayerBase> hcPlayers)
    {
        super.Stop(hcPlayers);
        HCRecoveryGate.HCClose("groups");
    }
}
