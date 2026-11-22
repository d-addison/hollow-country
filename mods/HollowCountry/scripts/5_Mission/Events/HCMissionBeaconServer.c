// Connect-time delivery of the public mission list. New and Ready are separate
// connection paths, so the snapshot goes out on both; the single summary toast is
// only sent once the player is in the world (Ready and Reconnect).
// Native scripts-1.30.164289: 5_Mission/mission/missionServer.c:549,599,633
// OnClientNewEvent/OnClientReadyEvent/OnClientReconnectEvent.
modded class MissionServer
{
    override PlayerBase OnClientNewEvent(PlayerIdentity identity, vector pos, ParamsReadContext ctx)
    {
        PlayerBase player = super.OnClientNewEvent(identity, pos, ctx);
        HCEventModule.HCMissionMapConnected(identity, false);
        return player;
    }

    override void OnClientReadyEvent(PlayerIdentity identity, PlayerBase player)
    {
        super.OnClientReadyEvent(identity, player);
        HCEventModule.HCMissionMapConnected(identity, true);
    }

    override void OnClientReconnectEvent(PlayerIdentity identity, PlayerBase player)
    {
        super.OnClientReconnectEvent(identity, player);
        HCEventModule.HCMissionMapConnected(identity, true);
    }
}
