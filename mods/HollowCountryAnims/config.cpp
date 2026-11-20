// Hollow Country posed infected (experimental, runtime acceptance pending).
// Only the four HC posed classes (Sitter, Sleeper, Riser, Feeder) use the own-prefix graph;
// HC_ZmbM_Crawler and every vanilla infected keep the vanilla graph.
// Ships as HollowCountryAnims.pbo inside @HollowCountry/addons next to HollowCountry.pbo, so
// server and every client load it with the base mod. Built by tools/anim/build_anims_addon.py
// (our graph file and child instance reference the vanilla infected graph by DZ/ path; clips
// from tools/anim/build_infected_clips.py). See docs/ANIMATION_PIPELINE.md.
class CfgPatches
{
    class HollowCountryAnims
    {
        units[] = {"HC_ZmbM_Sitter", "HC_ZmbM_Sleeper", "HC_ZmbM_Riser", "HC_ZmbM_Feeder", "HC_ZmbM_Crawler"};
        weapons[] = {};
        requiredVersion = 0.1;
        // One-way dependency: shared HC-45 admission must compile before this
        // experimental script subclass. HollowCountry does not require Anims.
        requiredAddons[] = {"DZ_Data", "DZ_Scripts", "DZ_Characters_Zombies", "HollowCountry"};
    };
};
class CfgMods
{
    class HollowCountryAnims
    {
        dir = "HollowCountryAnims";
        name = "Hollow Country posed infected";
        author = "Hollow Country";
        version = "0.1.0-dev";
        type = "mod";
        dependencies[] = {"World"};
        class defs
        {
            class worldScriptModule
            {
                value = "";
                files[] = {"HollowCountryAnims/scripts/4_World"};
            };
        };
    };
};
class CfgVehicles
{
    class ZmbM_HermitSkinny_Beige;
    class ZmbM_CitizenASkinny_Grey;
    class ZmbM_CitizenASkinny_Red;
    class ZmbM_Jacket_brown;
    class ZmbM_FarmerFat_Brown;
    // #279: public so the vanilla CE can spawn them as children of the stock infected
    // events (tools/package/infected_variety.py); CE owns lifecycle, caps and cleanup.
    // Runtime acceptance (native playback, client graph, wake) remains PENDING.
    class HC_ZmbM_Sitter: ZmbM_HermitSkinny_Beige
    {
        scope = 2;
        // Same mesh, skeleton and input mapping as ZombieBase; only the graph and instance differ.
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    // Pose 2: flat sleeper. Outfit from a stock city male; every vanilla infected shares
    // the ZombieBase mesh/skeleton block above (only CfgVehicles/ZombieBase defines it).
    class HC_ZmbM_Sleeper: ZmbM_CitizenASkinny_Grey
    {
        scope = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    // Pose 3: lying body that rises when alerted.
    class HC_ZmbM_Riser: ZmbM_Jacket_brown
    {
        scope = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    // Pose 4: kneeling feeder.
    class HC_ZmbM_Feeder: ZmbM_FarmerFat_Brown
    {
        scope = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    // Native crawler: vanilla graph (inherited enfanimsys); the script requests the
    // vanilla crawl transition at spawn.
    class HC_ZmbM_Crawler: ZmbM_CitizenASkinny_Red
    {
        scope = 2;
    };
};
