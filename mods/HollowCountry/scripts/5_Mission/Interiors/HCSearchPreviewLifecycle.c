// Mission owns the handler lifetime; House/ActionTarget cache policy stays in 4_World.
modded class MissionServer
{
    protected ref HCSearchPreviewServer m_HCSearchPreviewServer;

    override void OnInit()
    {
        super.OnInit();
        m_HCSearchPreviewServer = new HCSearchPreviewServer;
        m_HCSearchPreviewServer.Start();
    }

    override void OnMissionFinish()
    {
        if (m_HCSearchPreviewServer) m_HCSearchPreviewServer.Stop();
        m_HCSearchPreviewServer = null;
        super.OnMissionFinish();
    }
}

modded class MissionGameplay
{
    override void OnInit()
    {
        super.OnInit();
        HCSearchPreviewSites.Get().Start();
    }

    override void OnMissionFinish()
    {
        HCSearchPreviewSites.Get().Stop();
        super.OnMissionFinish();
    }
}
