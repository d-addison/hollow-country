// Static evidence: installed gear_cooking.pbo CfgVehicles/PortableGasLamp and
// gear_consumables.pbo CfgVehicles/Roadflare, read with tools.audit.pbo_config.
// Our class uses the lamp's inventory/hand ancestry with self-contained fuel.
class CfgPatches
{
    class HollowCountryAssets
    {
        units[] = {"HC_TinCanLantern"};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"DZ_Data", "DZ_Gear_Cooking"};
    };
};
class CfgVehicles
{
    class PortableGasLamp;
    class HC_TinCanLantern: PortableGasLamp
    {
        scope = 2;
        displayName = "Tin-can lantern";
        descriptionShort = "A rusted tin can, wire handle and a small candle. Ignite with a fire source; extinguish before packing.";
        model = "\HollowCountryAssets\lantern\hc_tincanlantern.p3d";
        weight = 180;
        itemSize[] = {2, 3};
        attachments[] = {};
        inventorySlot[] = {};
        hiddenSelections[] = {"can", "handle", "candle", "flame"};
        simpleHiddenSelections[] = {"flame"};
        hiddenSelectionsTextures[] = {
            "HollowCountryAssets\lantern\tin_co.paa",
            "HollowCountryAssets\lantern\wire_co.paa",
            "HollowCountryAssets\lantern\wax_co.paa",
            "HollowCountryAssets\lantern\flame_co.paa"
        };
        hiddenSelectionsMaterials[] = {
            "HollowCountryAssets\lantern\tin.rvmat",
            "HollowCountryAssets\lantern\wire.rvmat",
            "HollowCountryAssets\lantern\wax.rvmat",
            "HollowCountryAssets\lantern\flame.rvmat"
        };
        // Override inherited gas-lamp damage materials: all art remains our own.
        // Same no-swap material set at each health level; damage art is deferred.
        class DamageSystem
        {
            class GlobalHealth
            {
                class Health
                {
                    hitpoints = 100;
                    healthLevels[] = {{1.0, {}}, {0.7, {}}, {0.5, {}}, {0.3, {}}, {0.0, {}}};
                };
            };
        };
        // Native ComponentEnergyManager.c:181-202; 7200 units / 1 unit/s = 2 h.
        // Provisional balance target, not a measured real candle burn duration.
        class EnergyManager
        {
            switchOnAtSpawn = 0;
            autoSwitchOff = 1;
            autoSwitchOffWhenInCargo = 1;
            hasIcon = 1;
            energyAtSpawn = 7200;
            energyStorageMax = 7200;
            energyUsagePerSecond = 1;
            updateInterval = 1;
            powerSocketsCount = 0;
            plugType = 0;
            attachmentAction = 0;
            convertEnergyToQuantity = 0;
            wetnessExposure = 1;
        };
    };
};
