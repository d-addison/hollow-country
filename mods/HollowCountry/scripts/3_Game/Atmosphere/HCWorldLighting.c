// LC-T104 / EXP-A2 authored lighting table loader, used by 5_Mission
// HCLightingClient. Installed native scripts-1.30.164289: 3_Game/WorldLighting.c
// (class WorldLighting), 3_Game/Global/World.c:105 LoadUserLightingCfg(path,name),
// 3_Game/Global/Game.c:931 GetWorld. A modded class must live in the base class's
// script module, so this stays in 3_Game. Native load returns void: a call is NOT
// evidence that a table parsed or rendered.
modded class WorldLighting
{
    void HCLoadLightingTable(string name)
    {
        // Closed authored set; never use a profile-supplied arbitrary path.
        string path = "";
        if (name == "dusk_warm") path = "HollowCountry\\data\\lighting\\hc_dusk_warm.txt";
        if (name == "dusk_cold") path = "HollowCountry\\data\\lighting\\hc_dusk_cold.txt";
        if (name == "overcast") path = "HollowCountry\\data\\lighting\\hc_overcast.txt";
        if (name == "storm") path = "HollowCountry\\data\\lighting\\hc_storm.txt";
        if (path != "") GetGame().GetWorld().LoadUserLightingCfg(path, name);
    }
}
