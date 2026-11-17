
class CfgPatches
{
    class HCDeathSelectionProbe
    {
        units[] = {};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"DZ_Data", "DZ_Scripts"};
    };
};
class CfgMods
{
    class HCDeathSelectionProbe
    {
        dir = "HCDeathSelectionProbe";
        type = "mod";
        dependencies[] = {"World"};
        class defs
        {
            class worldScriptModule
            {
                value = "";
                files[] = {"HCDeathSelectionProbe/scripts/4_World"};
            };
        };
    };
};
