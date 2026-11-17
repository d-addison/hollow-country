class CfgPatches
{
    class HollowCountry
    {
        units[] = {};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"DZ_Data", "DZ_Scripts"};
    };
};
class CfgMods
{
    class HollowCountry
    {
        dir = "HollowCountry";
        name = "Hollow Country";
        author = "David Addison";
        version = "0.1.0-dev";
        type = "mod";
        inputs = "HollowCountry\inputs.xml";
        dependencies[] = {"Game", "World", "Mission"};
        class defs
        {
            class gameScriptModule { value = ""; files[] = {"HollowCountry/scripts/3_Game"}; };
            class worldScriptModule { value = ""; files[] = {"HollowCountry/scripts/4_World"}; };
            class missionScriptModule { value = ""; files[] = {"HollowCountry/scripts/5_Mission"}; };
        };
    };
};
