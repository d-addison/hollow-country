// #126 native scripts-1.30.164289/5_Mission/mission/missionServer.c:499
// CreateCharacter(identity,pos,ctx,characterName) calls CreatePlayer at :502;
// fresh OnClientNewEvent :549/:573/:589 uses it; Ready :599 restores separately.
// 1_Core/proto/EnDebug.c:96 Print. No periodic work; selection precedes creation.
modded class MissionServer
{
    override PlayerBase CreateCharacter(PlayerIdentity identity, vector pos, ParamsReadContext ctx, string characterName)
    {
        HCCampRespawnModule respawn = HCCampRespawnModule.Get();
        vector campPosition;
        if (respawn)
        {
            if (respawn.HCChoose(identity, campPosition)) { pos = campPosition; }
            else { Print("[HollowCountry] W5 camp-respawn refused; vanilla spawn retained"); }
        }
        return super.CreateCharacter(identity, pos, ctx, characterName);
    }
}
