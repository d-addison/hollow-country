// HC-38 retired the quest input, menu and client polling; none of that returns.
// Native scripts-1.30.164289: 3_Game/DayZGame.c:991,3144 Event_OnRPC;
// 2_GameLib/tools.c:120,122 ScriptInvoker.Insert/Remove; missionGameplay.c:102,266
// OnInit/OnMissionFinish; 3_Game/Global/Game.c:914 GetTickTime.
// Receives the server's public mission snapshot (HCBeaconWire.RPC_PUBLIC) into
// HCMissionBeaconStore. Same trusted-sender rule as the other connect-time pushes:
// a server push has no sender and no target. There is no client request.
class HCMissionBeaconClient
{
    void HCReceive(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (rpcType != HCBeaconWire.RPC_PUBLIC || GetGame().IsServer() || sender || target) { return; }
        HCMissionBeaconStore.Get().Receive(ctx, GetGame().GetTickTime());
    }
}

modded class MissionGameplay
{
    protected ref HCMissionBeaconClient m_HCMissionBeaconClient;

    override void OnInit()
    {
        super.OnInit();
        HCMissionBeaconStore.Get().Clear();
        if (GetGame().IsDedicatedServer()) { return; }
        m_HCMissionBeaconClient = new HCMissionBeaconClient;
        DayZGame.Event_OnRPC.Insert(m_HCMissionBeaconClient.HCReceive);
    }

    override void OnMissionFinish()
    {
        if (m_HCMissionBeaconClient) { DayZGame.Event_OnRPC.Remove(m_HCMissionBeaconClient.HCReceive); }
        m_HCMissionBeaconClient = null;
        HCMissionBeaconStore.Get().Clear();
        super.OnMissionFinish();
    }
}
