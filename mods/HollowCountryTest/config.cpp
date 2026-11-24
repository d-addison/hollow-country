// Dev-only test addon. Never packed, signed, staged or listed by a release, bundle,
// friendcycle or Workshop tool. Loaded only by the local test campaign (server and client).
class CfgPatches
{
    class HollowCountryTest
    {
        units[] = {};
        weapons[] = {};
        requiredVersion = 0.1;
        // The kill fixture uses public HC site accessors; load the adapter before this addon.
        requiredAddons[] = {"HollowCountry", "HollowCountryExpansionAI"};
    };
};
class CfgMods
{
    class HollowCountryTest
    {
        dir = "HollowCountryTest";
        name = "Hollow Country test addon (dev only)";
        author = "Hollow Country";
        version = "0.1.0-dev";
        type = "mod";
        dependencies[] = {"World", "Mission"};
        class defs
        {
            class worldScriptModule
            {
                value = "";
                files[] = {"HollowCountryTest/scripts/4_World"};
            };
            class missionScriptModule
            {
                value = "";
                files[] = {"HollowCountryTest/scripts/5_Mission"};
            };
        };
    };
};
