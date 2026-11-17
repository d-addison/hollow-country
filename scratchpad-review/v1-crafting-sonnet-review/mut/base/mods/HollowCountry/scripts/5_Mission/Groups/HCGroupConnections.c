// Exact installed MissionServer 1.30 signatures. New and Ready are separate
// connection paths; disconnect must revoke before delayed character logout.
modded class MissionServer
{
    override PlayerBase OnClientNewEvent(PlayerIdentity identity, vector pos, ParamsReadContext ctx)
    {
        PlayerBase player = super.OnClientNewEvent(identity, pos, ctx);
        if (HCGroupService.Get()) HCGroupService.Get().Connected(identity, player);
        return player;
    }

    override void OnClientReadyEvent(PlayerIdentity identity, PlayerBase player)
    {
        super.OnClientReadyEvent(identity, player);
        if (HCGroupService.Get()) HCGroupService.Get().Connected(identity, player);
    }

    override void OnClientReconnectEvent(PlayerIdentity identity, PlayerBase player)
    {
        super.OnClientReconnectEvent(identity, player);
        if (HCGroupService.Get()) HCGroupService.Get().Connected(identity, player);
    }

    override void OnClientDisconnectedEvent(PlayerIdentity identity, PlayerBase player, int logoutTime, bool authFailed)
    {
        if (HCGroupService.Get()) HCGroupService.Get().Disconnected(identity);
        super.OnClientDisconnectedEvent(identity, player, logoutTime, authFailed);
    }
}
