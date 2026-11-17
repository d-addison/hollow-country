// HCServer is authored (4_World/Core/HCServer.c); no HCModule registration.
// Native snapshot: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 3_Game/Global/Game.c:932 GetWorldName(out string), :1093 GetMission;
// 1_Core/proto/EnString.c:171 ToLower; 3_Game/gameplay.c:742 GetWorldData;
// 1_Core/proto/EnScript.c:94 Class.Cast;
// 5_Mission/mission/missionBase.c:188 implementation returns the world instance.
// Native MissionServer.OnInit loads cfgGameplay before core startup:
// 5_Mission/mission/missionServer.c:85-96, :161-166.
modded class HCServer
{
    override void Start()
    {
        super.Start();
        if (!HCAtmosphereQualification.Enabled())
            return;
        string atmosphereWorld;
        GetGame().GetWorldName(atmosphereWorld);
        atmosphereWorld.ToLower();
        if (atmosphereWorld != "chernarusplus")
        {
            Print("[HollowCountry][Atmosphere] BLOCKED unsupported map; ChernarusPlus only");
            return;
        }
        Mission atmosphereMission = GetGame().GetMission();
        if (!atmosphereMission)
            return;
        ChernarusPlusData atmosphereData = ChernarusPlusData.Cast(atmosphereMission.GetWorldData());
        if (atmosphereData)
            atmosphereData.HCStartAtmosphere();
    }
}
