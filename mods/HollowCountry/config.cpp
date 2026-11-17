class CfgPatches
{
    class HollowCountry
    {
        units[] = {};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"DZ_Data", "DZ_Scripts", "DZ_Characters_Zombies"};
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
// Infected leg hits can drop a runner to a crawler sooner (native crawl transition fires when a
// leg zone health reaches 0). The other leg inherits this class; bosses that set their own zones stay vanilla.
// Provisional value; see tools/package/gameplay.py LEG_HITPOINTS. Runtime acceptance pending.
class CfgVehicles
{
    class DayZInfected;
    class ZombieBase: DayZInfected
    {
        class DamageSystem
        {
            class DamageZones
            {
                class LeftLeg
                {
                    class Health { hitpoints = 50; };
                };
            };
        };
    };
};
