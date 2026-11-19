class CfgPatches
{
    class HollowCountryExpansionAI
    {
        units[] = {};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"HollowCountry", "DayZExpansion_AI_Scripts", "DayZExpansion_Vehicles_Scripts",
            "DayZExpansion_AI_Animations", "DayZExpansion_Sounds_AI",
            "DayZExpansion_Core_Scripts", "DayZExpansion_ModStorage_Scripts",
            "JM_CF_Scripts", "DF_Scripts", "DF_GUI"};
    };
};
class CfgMods
{
    class HollowCountryExpansionAI
    {
        dir = "HollowCountryExpansionAI";
        name = "Hollow Country optional Expansion AI adapter";
        author = "Hollow Country";
        version = "0.1.0-dev";
        type = "mod";
        dependencies[] = {"World"};
        class defs
        {
            class worldScriptModule
            {
                value = "";
                files[] = {"HollowCountryExpansionAI/scripts/4_World"};
            };
        };
    };
};
