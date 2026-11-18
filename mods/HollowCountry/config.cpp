class CfgPatches
{
    class HollowCountry
    {
        units[] = {};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"DZ_Data", "DZ_Scripts", "DZ_Characters_Zombies", "DZ_Weapons_Firearms_Scout"};
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

// #58 item 1: installed 1.30.164289 Scout model already has the native light proxy.
// Read-only tools.audit.pbo_config evidence, client AND server addons/weapons_firearms.pbo:
// scout/config.bin: Scout attachments = weaponWrap, weaponOptics, weaponMuzzleM4;
// Scout_Chernarus and Scout_Livonia inherit Scout and its model.
// scout/scout.p3d: proxy:\dz\weapons\attachments\light\weaponlight_universal.001
// at member byte 8586 (client) / 8457 (server). No model or proxy is authored here.
// addons/weapon_lights.pbo/config.bin: UniversalLight inventorySlot includes weaponFlashlight.
// Existing probe-006 observations.json independently lists that proxy for all three hosts;
// patched attachment, beam/alignment, persistence and two-client acceptance remain PENDING.
// CfgPatches requiredAddons includes DZ_Weapons_Firearms_Scout (verified in the installed weapons_firearms.pbo).
class CfgWeapons
{
    class Scout_Base;
    class Scout: Scout_Base
    {
        // Preserve every installed vanilla slot; colour variants inherit this addition.
        attachments[] = {"weaponWrap", "weaponOptics", "weaponMuzzleM4", "weaponFlashlight"};
    };
};
