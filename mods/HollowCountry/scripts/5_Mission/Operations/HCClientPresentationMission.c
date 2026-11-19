// HC-27 lifecycle wiring. Installed scripts-1.30.164289 native evidence:
// 5_Mission/mission/missionGameplay.c:102,266,287 OnInit/Finish/Update,
// :1119 IsControlDisabled; missionServer.c:108 OnUpdate, :549/599/633
// OnClientNewEvent/Ready/Reconnect; 3_Game/Global/Game.c:1125 IsDedicatedServer,
// :943 GetUIManager; 3_Game/tools/UIManager.c:59 GetMenu.
// All hooks call native super; no HCServer or HCModule modification required.
// Runtime=PENDING: DayZDiag, normal PBO/server and two clients.
modded class MissionGameplay
{
    protected ref HCClientPresentation m_HCClientPresentation;

    override void OnInit()
    {
        super.OnInit();
        if (GetGame().IsDedicatedServer()) { return; }
        m_HCClientPresentation = new HCClientPresentation;
        m_HCClientPresentation.HCStart();
    }

    override void OnUpdate(float timeslice)
    {
        super.OnUpdate(timeslice);
        if (m_HCClientPresentation)
        {
            bool allowInput = !IsControlDisabled() && !GetGame().GetUIManager().GetMenu();
            m_HCClientPresentation.HCUpdate(timeslice, allowInput);
        }
    }

    override void OnMissionFinish()
    {
        if (m_HCClientPresentation) { m_HCClientPresentation.HCStop(); }
        m_HCClientPresentation = null;
        super.OnMissionFinish();
    }
}

modded class MissionServer
{
    override PlayerBase OnClientNewEvent(PlayerIdentity identity, vector pos, ParamsReadContext ctx)
    {
        PlayerBase player = super.OnClientNewEvent(identity, pos, ctx);
        HCClientPresentationServer.SendTo(identity);
        HCSeasonSnapshotRPC.SendTo(identity);
        return player;
    }

    override void OnClientReadyEvent(PlayerIdentity identity, PlayerBase player)
    {
        super.OnClientReadyEvent(identity, player);
        HCClientPresentationServer.SendTo(identity);
        HCSeasonSnapshotRPC.SendTo(identity);
    }

    override void OnClientReconnectEvent(PlayerIdentity identity, PlayerBase player)
    {
        super.OnClientReconnectEvent(identity, player);
        HCClientPresentationServer.SendTo(identity);
        HCSeasonSnapshotRPC.SendTo(identity);
    }

    override void OnUpdate(float timeslice)
    {
        super.OnUpdate(timeslice);
        HCClientPresentationServer.HCTick(timeslice);
        HCSeasonSnapshotRPC.HCTick(timeslice);
    }
}
