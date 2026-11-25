// Setup fixture: only the isolated soak profile writes this marker. Fresh characters only;
// persistence logins use the separate ready path. Native missionServer.c:549 exact signature;
// :573/:589 pass pos to CreateCharacter before equipment. Hook before stock CustomMission,
// which overrides CreateCharacter without super, so a base CreateCharacter hook is bypassed.
#ifdef SERVER
modded class MissionServer
{
    override PlayerBase OnClientNewEvent(PlayerIdentity identity, vector pos, ParamsReadContext ctx)
    {
        if (FileExist("$profile:HollowCountry/autoplayer-initial-spawn"))
        {
            pos = Vector(6500, GetGame().SurfaceY(6500, 2500), 2500);
            Print("[HC Driver] spawn fixture=1 initial=1 at=<6500,2500>");
        }
        return super.OnClientNewEvent(identity, pos, ctx);
    }
}
#endif
