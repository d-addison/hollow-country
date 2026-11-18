// Hollow Country posed infected (experimental, runtime acceptance pending).
// Only HC_ZmbM_Sitter uses the own-prefix graph; every vanilla infected keeps the vanilla graph.
// Ships as HollowCountryAnims.pbo inside @HollowCountry/addons next to HollowCountry.pbo, so
// server and every client load it with the base mod. Built by tools/anim/build_anims_addon.py
// (our graph file and child instance reference the vanilla infected graph by DZ/ path; clips
// from tools/anim/build_infected_clips.py). See docs/ANIMATION_PIPELINE.md.
class CfgPatches
{
    class HollowCountryAnims
    {
        units[] = {"HC_ZmbM_Sitter"};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"DZ_Data", "DZ_Scripts", "DZ_Characters_Zombies"};
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
};
