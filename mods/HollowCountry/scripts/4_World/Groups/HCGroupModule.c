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
        return m_Config && m_Config.Enabled;
    }

    override void OnStart(HCSettings settings)
    {
        m_Service = new HCGroupService;
        if (!m_Service.Start(m_Config)) { m_Service = null; return; }
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
