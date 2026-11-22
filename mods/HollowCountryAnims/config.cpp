// Hollow Country posed infected (experimental, runtime acceptance pending).
// HC posed classes and their outfit variants use the own-prefix graph;
// HC crawlers and unmarked vanilla infected keep the vanilla graph.
// Ships as HollowCountryAnims.pbo inside @HollowCountry/addons next to HollowCountry.pbo, so
// server and every client load it with the base mod. Built by tools/anim/build_anims_addon.py
// (our graph file and child instance reference the vanilla infected graph by DZ/ path; clips
// from tools/anim/build_infected_clips.py). See docs/ANIMATION_PIPELINE.md.
class CfgPatches
{
    class HollowCountryAnims
    {
        units[] = {"HC_ZmbM_Sitter", "HC_ZmbF_Crawler_ZmbF_JoggerSkinny_Red", "HC_ZmbF_Crawler_ZmbF_MechanicNormal_Beige", "HC_ZmbF_Crawler_ZmbF_MilkMaidOld_Black", "HC_ZmbF_Crawler_ZmbF_ParamedicNormal_Green", "HC_ZmbF_Crawler_ZmbF_SurvivorNormal_Orange", "HC_ZmbF_Crawler_ZmbF_usSoldier_normal_Desert", "HC_ZmbF_Feeder_ZmbF_BlueCollarFat_Green", "HC_ZmbF_Feeder_ZmbF_CitizenBSkinny", "HC_ZmbF_Feeder_ZmbF_Clerk_Normal_Green", "HC_ZmbF_Feeder_ZmbF_HikerSkinny_Green", "HC_ZmbF_Feeder_ZmbF_JoggerSkinny_Brown", "HC_ZmbF_Feeder_ZmbF_MilkMaidOld_Black", "HC_ZmbF_Feeder_ZmbF_NurseFat", "HC_ZmbF_Feeder_ZmbF_PoliceWomanNormal", "HC_ZmbF_Feeder_ZmbF_VillagerOld_Blue", "HC_ZmbF_Feeder_ZmbF_usSoldier_Heavy_Desert", "HC_ZmbF_Riser_ZmbF_BlueCollarFat_White", "HC_ZmbF_Riser_ZmbF_HikerSkinny_Red", "HC_ZmbF_Riser_ZmbF_MilkMaidOld_Black", "HC_ZmbF_Riser_ZmbF_ParamedicNormal_Blue", "HC_ZmbF_Riser_ZmbF_PoliceWomanNormal", "HC_ZmbF_Riser_ZmbF_ShortSkirt_Black", "HC_ZmbF_Riser_ZmbF_usSoldier_Heavy_Desert", "HC_ZmbF_Riser_ZmbF_usSoldier_normal_Desert", "HC_ZmbF_Sitter_ZmbF_BlueCollarFat_Red", "HC_ZmbF_Sitter_ZmbF_HikerSkinny_Grey", "HC_ZmbF_Sitter_ZmbF_JournalistNormal_White", "HC_ZmbF_Sitter_ZmbF_MilkMaidOld_Black", "HC_ZmbF_Sitter_ZmbF_MilkMaidOld_Green", "HC_ZmbF_Sitter_ZmbF_PatientOld", "HC_ZmbF_Sitter_ZmbF_PoliceWomanNormal", "HC_ZmbF_Sitter_ZmbF_usSoldier_Heavy_Desert", "HC_ZmbF_Sleeper_ZmbF_BlueCollarFat_Blue", "HC_ZmbF_Sleeper_ZmbF_BlueCollarFat_White", "HC_ZmbF_Sleeper_ZmbF_CitizenANormal_Brown", "HC_ZmbF_Sleeper_ZmbF_DoctorSkinny", "HC_ZmbF_Sleeper_ZmbF_HikerSkinny_Blue", "HC_ZmbF_Sleeper_ZmbF_JoggerSkinny_Blue", "HC_ZmbF_Sleeper_ZmbF_JoggerSkinny_Red", "HC_ZmbF_Sleeper_ZmbF_MilkMaidOld_Black", "HC_ZmbF_Sleeper_ZmbF_PoliceWomanNormal", "HC_ZmbF_Sleeper_ZmbF_usSoldier_normal_Desert", "HC_ZmbM_Crawler_ZmbM_CitizenASkinny_Blue", "HC_ZmbM_Crawler_ZmbM_CitizenBFat_Red", "HC_ZmbM_Crawler_ZmbM_CommercialPilotOld_Grey", "HC_ZmbM_Crawler_ZmbM_ConstrWorkerNormal_Green", "HC_ZmbM_Crawler_ZmbM_FarmerFat_Blue", "HC_ZmbM_Crawler_ZmbM_FirefighterNormal", "HC_ZmbM_Crawler_ZmbM_FishermanOld_Green", "HC_ZmbM_Crawler_ZmbM_HandymanNormal_Beige", "HC_ZmbM_Crawler_ZmbM_HermitSkinny_Beige", "HC_ZmbM_Crawler_ZmbM_Jacket_blue", "HC_ZmbM_Crawler_ZmbM_Jacket_magenta", "HC_ZmbM_Crawler_ZmbM_NBC_Grey", "HC_ZmbM_Crawler_ZmbM_NBC_Yellow", "HC_ZmbM_Crawler_ZmbM_PatientSkinny", "HC_ZmbM_Crawler_ZmbM_PatrolNormal_Flat", "HC_ZmbM_Crawler_ZmbM_PolicemanFat", "HC_ZmbM_Crawler_ZmbM_PolicemanSpecForce_Heavy", "HC_ZmbM_Crawler_ZmbM_PrisonerSkinny", "HC_ZmbM_Crawler_ZmbM_Santa", "HC_ZmbM_Crawler_ZmbM_priestPopSkinny", "HC_ZmbM_Crawler_ZmbM_usSoldier_normal_Desert", "HC_ZmbM_Crawler_ZmbM_usSoldier_normal_Woodland", "HC_ZmbM_Feeder_ZmbM_CitizenBFat_Green", "HC_ZmbM_Feeder_ZmbM_FirefighterNormal", "HC_ZmbM_Feeder_ZmbM_FishermanOld_Red", "HC_ZmbM_Feeder_ZmbM_HandymanNormal_Beige", "HC_ZmbM_Feeder_ZmbM_Jacket_black", "HC_ZmbM_Feeder_ZmbM_JoggerSkinny_Red", "HC_ZmbM_Feeder_ZmbM_MotobikerFat_Black", "HC_ZmbM_Feeder_ZmbM_NBC_Grey", "HC_ZmbM_Feeder_ZmbM_NBC_Yellow", "HC_ZmbM_Feeder_ZmbM_ParamedicNormal_Blue", "HC_ZmbM_Feeder_ZmbM_PatrolNormal_Autumn", "HC_ZmbM_Feeder_ZmbM_PatrolNormal_Summer", "HC_ZmbM_Feeder_ZmbM_PolicemanSpecForce_Heavy", "HC_ZmbM_Feeder_ZmbM_PrisonerSkinny", "HC_ZmbM_Feeder_ZmbM_Santa", "HC_ZmbM_Feeder_ZmbM_priestPopSkinny", "HC_ZmbM_Feeder_ZmbM_usSoldier_Heavy_Woodland", "HC_ZmbM_Feeder_ZmbM_usSoldier_normal_Desert", "HC_ZmbM_Riser_ZmbM_CitizenBFat_Blue", "HC_ZmbM_Riser_ZmbM_ClerkFat_Brown", "HC_ZmbM_Riser_ZmbM_ConstrWorkerNormal_Black", "HC_ZmbM_Riser_ZmbM_FirefighterNormal", "HC_ZmbM_Riser_ZmbM_FishermanOld_Blue", "HC_ZmbM_Riser_ZmbM_HandymanNormal_Beige", "HC_ZmbM_Riser_ZmbM_Jacket_beige", "HC_ZmbM_Riser_ZmbM_Jacket_bluechecks", "HC_ZmbM_Riser_ZmbM_JoggerSkinny_Green", "HC_ZmbM_Riser_ZmbM_JournalistSkinny", "HC_ZmbM_Riser_ZmbM_NBC_Grey", "HC_ZmbM_Riser_ZmbM_NBC_Yellow", "HC_ZmbM_Riser_ZmbM_PatrolNormal_PautRev", "HC_ZmbM_Riser_ZmbM_PolicemanFat", "HC_ZmbM_Riser_ZmbM_PolicemanSpecForce_Heavy", "HC_ZmbM_Riser_ZmbM_PrisonerSkinny", "HC_ZmbM_Riser_ZmbM_Santa", "HC_ZmbM_Riser_ZmbM_SoldierNormal", "HC_ZmbM_Riser_ZmbM_VillagerOld_Green", "HC_ZmbM_Riser_ZmbM_priestPopSkinny", "HC_ZmbM_Riser_ZmbM_usSoldier_Officer_Desert", "HC_ZmbM_Sitter_ZmbM_CitizenASkinny_Brown", "HC_ZmbM_Sitter_ZmbM_CitizenASkinny_Grey", "HC_ZmbM_Sitter_ZmbM_ConstrWorkerNormal_Beige", "HC_ZmbM_Sitter_ZmbM_DoctorFat", "HC_ZmbM_Sitter_ZmbM_FarmerFat_Brown", "HC_ZmbM_Sitter_ZmbM_FirefighterNormal", "HC_ZmbM_Sitter_ZmbM_HandymanNormal_Beige", "HC_ZmbM_Sitter_ZmbM_HunterOld_Autumn", "HC_ZmbM_Sitter_ZmbM_JoggerSkinny_Blue", "HC_ZmbM_Sitter_ZmbM_JoggerSkinny_Red", "HC_ZmbM_Sitter_ZmbM_MotobikerFat_Beige", "HC_ZmbM_Sitter_ZmbM_NBC_Grey", "HC_ZmbM_Sitter_ZmbM_NBC_Yellow", "HC_ZmbM_Sitter_ZmbM_PatrolNormal_Autumn", "HC_ZmbM_Sitter_ZmbM_PatrolNormal_Summer", "HC_ZmbM_Sitter_ZmbM_PolicemanFat", "HC_ZmbM_Sitter_ZmbM_PolicemanSpecForce_Heavy", "HC_ZmbM_Sitter_ZmbM_PrisonerSkinny", "HC_ZmbM_Sitter_ZmbM_Santa", "HC_ZmbM_Sitter_ZmbM_SoldierNormal", "HC_ZmbM_Sitter_ZmbM_priestPopSkinny", "HC_ZmbM_Sitter_ZmbM_usSoldier_normal_Desert", "HC_ZmbM_Sleeper_ZmbM_CitizenASkinny_Red", "HC_ZmbM_Sleeper_ZmbM_ConstrWorkerNormal_Grey", "HC_ZmbM_Sleeper_ZmbM_FarmerFat_Beige", "HC_ZmbM_Sleeper_ZmbM_FarmerFat_Green", "HC_ZmbM_Sleeper_ZmbM_FirefighterNormal", "HC_ZmbM_Sleeper_ZmbM_FishermanOld_Grey", "HC_ZmbM_Sleeper_ZmbM_HandymanNormal_Beige", "HC_ZmbM_Sleeper_ZmbM_NBC_Grey", "HC_ZmbM_Sleeper_ZmbM_NBC_Yellow", "HC_ZmbM_Sleeper_ZmbM_ParamedicNormal_Black", "HC_ZmbM_Sleeper_ZmbM_PatrolNormal_Flat", "HC_ZmbM_Sleeper_ZmbM_PolicemanFat", "HC_ZmbM_Sleeper_ZmbM_PolicemanSpecForce_Heavy", "HC_ZmbM_Sleeper_ZmbM_PrisonerSkinny", "HC_ZmbM_Sleeper_ZmbM_Santa", "HC_ZmbM_Sleeper_ZmbM_SkaterYoung_Blue", "HC_ZmbM_Sleeper_ZmbM_priestPopSkinny", "HC_ZmbM_Sleeper_ZmbM_usSoldier_Heavy_Woodland", "HC_ZmbM_Sleeper_ZmbM_usSoldier_normal_Desert", "HC_ZmbM_Sleeper_ZmbM_usSoldier_normal_Woodland"};
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
    // #279: public so the vanilla CE can spawn them as children of the stock infected
    // events (tools/package/infected_variety.py); CE owns lifecycle, caps and cleanup.
    // Runtime acceptance (native playback, client graph, wake) remains PENDING.
    class HC_ZmbM_Sitter: ZmbM_HermitSkinny_Beige
    {
        scope = 2;
        hcSpawnPose = 1;
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
    // BEGIN GENERATED CE OUTFITS (tools.anim.ce_variants)
    class ZmbF_BlueCollarFat_Blue;
    class ZmbF_BlueCollarFat_Green;
    class ZmbF_BlueCollarFat_Red;
    class ZmbF_BlueCollarFat_White;
    class ZmbF_CitizenANormal_Brown;
    class ZmbF_CitizenBSkinny;
    class ZmbF_Clerk_Normal_Green;
    class ZmbF_DoctorSkinny;
    class ZmbF_HikerSkinny_Blue;
    class ZmbF_HikerSkinny_Green;
    class ZmbF_HikerSkinny_Grey;
    class ZmbF_HikerSkinny_Red;
    class ZmbF_JoggerSkinny_Blue;
    class ZmbF_JoggerSkinny_Brown;
    class ZmbF_JoggerSkinny_Red;
    class ZmbF_JournalistNormal_White;
    class ZmbF_MechanicNormal_Beige;
    class ZmbF_MilkMaidOld_Black;
    class ZmbF_MilkMaidOld_Green;
    class ZmbF_NurseFat;
    class ZmbF_ParamedicNormal_Blue;
    class ZmbF_ParamedicNormal_Green;
    class ZmbF_PatientOld;
    class ZmbF_PoliceWomanNormal;
    class ZmbF_ShortSkirt_Black;
    class ZmbF_SurvivorNormal_Orange;
    class ZmbF_VillagerOld_Blue;
    class ZmbF_usSoldier_Heavy_Desert;
    class ZmbF_usSoldier_normal_Desert;
    class ZmbM_CitizenASkinny_Blue;
    class ZmbM_CitizenASkinny_Brown;
    class ZmbM_CitizenASkinny_Grey;
    class ZmbM_CitizenASkinny_Red;
    class ZmbM_CitizenBFat_Blue;
    class ZmbM_CitizenBFat_Green;
    class ZmbM_CitizenBFat_Red;
    class ZmbM_ClerkFat_Brown;
    class ZmbM_CommercialPilotOld_Grey;
    class ZmbM_ConstrWorkerNormal_Beige;
    class ZmbM_ConstrWorkerNormal_Black;
    class ZmbM_ConstrWorkerNormal_Green;
    class ZmbM_ConstrWorkerNormal_Grey;
    class ZmbM_DoctorFat;
    class ZmbM_FarmerFat_Beige;
    class ZmbM_FarmerFat_Blue;
    class ZmbM_FarmerFat_Brown;
    class ZmbM_FarmerFat_Green;
    class ZmbM_FirefighterNormal;
    class ZmbM_FishermanOld_Blue;
    class ZmbM_FishermanOld_Green;
    class ZmbM_FishermanOld_Grey;
    class ZmbM_FishermanOld_Red;
    class ZmbM_HandymanNormal_Beige;
    class ZmbM_HunterOld_Autumn;
    class ZmbM_Jacket_beige;
    class ZmbM_Jacket_black;
    class ZmbM_Jacket_blue;
    class ZmbM_Jacket_bluechecks;
    class ZmbM_Jacket_magenta;
    class ZmbM_JoggerSkinny_Blue;
    class ZmbM_JoggerSkinny_Green;
    class ZmbM_JoggerSkinny_Red;
    class ZmbM_JournalistSkinny;
    class ZmbM_MotobikerFat_Beige;
    class ZmbM_MotobikerFat_Black;
    class ZmbM_NBC_Grey;
    class ZmbM_NBC_Yellow;
    class ZmbM_ParamedicNormal_Black;
    class ZmbM_ParamedicNormal_Blue;
    class ZmbM_PatientSkinny;
    class ZmbM_PatrolNormal_Autumn;
    class ZmbM_PatrolNormal_Flat;
    class ZmbM_PatrolNormal_PautRev;
    class ZmbM_PatrolNormal_Summer;
    class ZmbM_PolicemanFat;
    class ZmbM_PolicemanSpecForce_Heavy;
    class ZmbM_PrisonerSkinny;
    class ZmbM_Santa;
    class ZmbM_SkaterYoung_Blue;
    class ZmbM_SoldierNormal;
    class ZmbM_VillagerOld_Green;
    class ZmbM_priestPopSkinny;
    class ZmbM_usSoldier_Heavy_Woodland;
    class ZmbM_usSoldier_Officer_Desert;
    class ZmbM_usSoldier_normal_Desert;
    class ZmbM_usSoldier_normal_Woodland;
    class HC_ZmbF_Crawler_ZmbF_JoggerSkinny_Red: ZmbF_JoggerSkinny_Red
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbF_Crawler_ZmbF_MechanicNormal_Beige: ZmbF_MechanicNormal_Beige
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbF_Crawler_ZmbF_MilkMaidOld_Black: ZmbF_MilkMaidOld_Black
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbF_Crawler_ZmbF_ParamedicNormal_Green: ZmbF_ParamedicNormal_Green
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbF_Crawler_ZmbF_SurvivorNormal_Orange: ZmbF_SurvivorNormal_Orange
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbF_Crawler_ZmbF_usSoldier_normal_Desert: ZmbF_usSoldier_normal_Desert
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbF_Feeder_ZmbF_BlueCollarFat_Green: ZmbF_BlueCollarFat_Green
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Feeder_ZmbF_CitizenBSkinny: ZmbF_CitizenBSkinny
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Feeder_ZmbF_Clerk_Normal_Green: ZmbF_Clerk_Normal_Green
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Feeder_ZmbF_HikerSkinny_Green: ZmbF_HikerSkinny_Green
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Feeder_ZmbF_JoggerSkinny_Brown: ZmbF_JoggerSkinny_Brown
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Feeder_ZmbF_MilkMaidOld_Black: ZmbF_MilkMaidOld_Black
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Feeder_ZmbF_NurseFat: ZmbF_NurseFat
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Feeder_ZmbF_PoliceWomanNormal: ZmbF_PoliceWomanNormal
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Feeder_ZmbF_VillagerOld_Blue: ZmbF_VillagerOld_Blue
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Feeder_ZmbF_usSoldier_Heavy_Desert: ZmbF_usSoldier_Heavy_Desert
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Riser_ZmbF_BlueCollarFat_White: ZmbF_BlueCollarFat_White
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Riser_ZmbF_HikerSkinny_Red: ZmbF_HikerSkinny_Red
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Riser_ZmbF_MilkMaidOld_Black: ZmbF_MilkMaidOld_Black
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Riser_ZmbF_ParamedicNormal_Blue: ZmbF_ParamedicNormal_Blue
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Riser_ZmbF_PoliceWomanNormal: ZmbF_PoliceWomanNormal
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Riser_ZmbF_ShortSkirt_Black: ZmbF_ShortSkirt_Black
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Riser_ZmbF_usSoldier_Heavy_Desert: ZmbF_usSoldier_Heavy_Desert
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Riser_ZmbF_usSoldier_normal_Desert: ZmbF_usSoldier_normal_Desert
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sitter_ZmbF_BlueCollarFat_Red: ZmbF_BlueCollarFat_Red
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sitter_ZmbF_HikerSkinny_Grey: ZmbF_HikerSkinny_Grey
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sitter_ZmbF_JournalistNormal_White: ZmbF_JournalistNormal_White
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sitter_ZmbF_MilkMaidOld_Black: ZmbF_MilkMaidOld_Black
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sitter_ZmbF_MilkMaidOld_Green: ZmbF_MilkMaidOld_Green
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sitter_ZmbF_PatientOld: ZmbF_PatientOld
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sitter_ZmbF_PoliceWomanNormal: ZmbF_PoliceWomanNormal
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sitter_ZmbF_usSoldier_Heavy_Desert: ZmbF_usSoldier_Heavy_Desert
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sleeper_ZmbF_BlueCollarFat_Blue: ZmbF_BlueCollarFat_Blue
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sleeper_ZmbF_BlueCollarFat_White: ZmbF_BlueCollarFat_White
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sleeper_ZmbF_CitizenANormal_Brown: ZmbF_CitizenANormal_Brown
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sleeper_ZmbF_DoctorSkinny: ZmbF_DoctorSkinny
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sleeper_ZmbF_HikerSkinny_Blue: ZmbF_HikerSkinny_Blue
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sleeper_ZmbF_JoggerSkinny_Blue: ZmbF_JoggerSkinny_Blue
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sleeper_ZmbF_JoggerSkinny_Red: ZmbF_JoggerSkinny_Red
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sleeper_ZmbF_MilkMaidOld_Black: ZmbF_MilkMaidOld_Black
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sleeper_ZmbF_PoliceWomanNormal: ZmbF_PoliceWomanNormal
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbF_Sleeper_ZmbF_usSoldier_normal_Desert: ZmbF_usSoldier_normal_Desert
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Crawler_ZmbM_CitizenASkinny_Blue: ZmbM_CitizenASkinny_Blue
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_CitizenBFat_Red: ZmbM_CitizenBFat_Red
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_CommercialPilotOld_Grey: ZmbM_CommercialPilotOld_Grey
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_ConstrWorkerNormal_Green: ZmbM_ConstrWorkerNormal_Green
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_FarmerFat_Blue: ZmbM_FarmerFat_Blue
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_FirefighterNormal: ZmbM_FirefighterNormal
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_FishermanOld_Green: ZmbM_FishermanOld_Green
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_HandymanNormal_Beige: ZmbM_HandymanNormal_Beige
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_HermitSkinny_Beige: ZmbM_HermitSkinny_Beige
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_Jacket_blue: ZmbM_Jacket_blue
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_Jacket_magenta: ZmbM_Jacket_magenta
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_NBC_Grey: ZmbM_NBC_Grey
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_NBC_Yellow: ZmbM_NBC_Yellow
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_PatientSkinny: ZmbM_PatientSkinny
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_PatrolNormal_Flat: ZmbM_PatrolNormal_Flat
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_PolicemanFat: ZmbM_PolicemanFat
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_PolicemanSpecForce_Heavy: ZmbM_PolicemanSpecForce_Heavy
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_PrisonerSkinny: ZmbM_PrisonerSkinny
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_Santa: ZmbM_Santa
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_priestPopSkinny: ZmbM_priestPopSkinny
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_usSoldier_normal_Desert: ZmbM_usSoldier_normal_Desert
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Crawler_ZmbM_usSoldier_normal_Woodland: ZmbM_usSoldier_normal_Woodland
    {
        scope = 2;
        hcSpawnPose = 5;
    };
    class HC_ZmbM_Feeder_ZmbM_CitizenBFat_Green: ZmbM_CitizenBFat_Green
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_FirefighterNormal: ZmbM_FirefighterNormal
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_FishermanOld_Red: ZmbM_FishermanOld_Red
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_HandymanNormal_Beige: ZmbM_HandymanNormal_Beige
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_Jacket_black: ZmbM_Jacket_black
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_JoggerSkinny_Red: ZmbM_JoggerSkinny_Red
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_MotobikerFat_Black: ZmbM_MotobikerFat_Black
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_NBC_Grey: ZmbM_NBC_Grey
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_NBC_Yellow: ZmbM_NBC_Yellow
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_ParamedicNormal_Blue: ZmbM_ParamedicNormal_Blue
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_PatrolNormal_Autumn: ZmbM_PatrolNormal_Autumn
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_PatrolNormal_Summer: ZmbM_PatrolNormal_Summer
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_PolicemanSpecForce_Heavy: ZmbM_PolicemanSpecForce_Heavy
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_PrisonerSkinny: ZmbM_PrisonerSkinny
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_Santa: ZmbM_Santa
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_priestPopSkinny: ZmbM_priestPopSkinny
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_usSoldier_Heavy_Woodland: ZmbM_usSoldier_Heavy_Woodland
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Feeder_ZmbM_usSoldier_normal_Desert: ZmbM_usSoldier_normal_Desert
    {
        scope = 2;
        hcSpawnPose = 4;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_CitizenBFat_Blue: ZmbM_CitizenBFat_Blue
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_ClerkFat_Brown: ZmbM_ClerkFat_Brown
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_ConstrWorkerNormal_Black: ZmbM_ConstrWorkerNormal_Black
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_FirefighterNormal: ZmbM_FirefighterNormal
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_FishermanOld_Blue: ZmbM_FishermanOld_Blue
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_HandymanNormal_Beige: ZmbM_HandymanNormal_Beige
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_Jacket_beige: ZmbM_Jacket_beige
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_Jacket_bluechecks: ZmbM_Jacket_bluechecks
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_JoggerSkinny_Green: ZmbM_JoggerSkinny_Green
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_JournalistSkinny: ZmbM_JournalistSkinny
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_NBC_Grey: ZmbM_NBC_Grey
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_NBC_Yellow: ZmbM_NBC_Yellow
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_PatrolNormal_PautRev: ZmbM_PatrolNormal_PautRev
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_PolicemanFat: ZmbM_PolicemanFat
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_PolicemanSpecForce_Heavy: ZmbM_PolicemanSpecForce_Heavy
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_PrisonerSkinny: ZmbM_PrisonerSkinny
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_Santa: ZmbM_Santa
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_SoldierNormal: ZmbM_SoldierNormal
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_VillagerOld_Green: ZmbM_VillagerOld_Green
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_priestPopSkinny: ZmbM_priestPopSkinny
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Riser_ZmbM_usSoldier_Officer_Desert: ZmbM_usSoldier_Officer_Desert
    {
        scope = 2;
        hcSpawnPose = 3;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_CitizenASkinny_Brown: ZmbM_CitizenASkinny_Brown
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_CitizenASkinny_Grey: ZmbM_CitizenASkinny_Grey
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_ConstrWorkerNormal_Beige: ZmbM_ConstrWorkerNormal_Beige
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_DoctorFat: ZmbM_DoctorFat
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_FarmerFat_Brown: ZmbM_FarmerFat_Brown
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_FirefighterNormal: ZmbM_FirefighterNormal
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_HandymanNormal_Beige: ZmbM_HandymanNormal_Beige
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_HunterOld_Autumn: ZmbM_HunterOld_Autumn
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_JoggerSkinny_Blue: ZmbM_JoggerSkinny_Blue
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_JoggerSkinny_Red: ZmbM_JoggerSkinny_Red
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_MotobikerFat_Beige: ZmbM_MotobikerFat_Beige
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_NBC_Grey: ZmbM_NBC_Grey
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_NBC_Yellow: ZmbM_NBC_Yellow
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_PatrolNormal_Autumn: ZmbM_PatrolNormal_Autumn
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_PatrolNormal_Summer: ZmbM_PatrolNormal_Summer
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_PolicemanFat: ZmbM_PolicemanFat
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_PolicemanSpecForce_Heavy: ZmbM_PolicemanSpecForce_Heavy
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_PrisonerSkinny: ZmbM_PrisonerSkinny
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_Santa: ZmbM_Santa
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_SoldierNormal: ZmbM_SoldierNormal
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_priestPopSkinny: ZmbM_priestPopSkinny
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sitter_ZmbM_usSoldier_normal_Desert: ZmbM_usSoldier_normal_Desert
    {
        scope = 2;
        hcSpawnPose = 1;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_CitizenASkinny_Red: ZmbM_CitizenASkinny_Red
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_ConstrWorkerNormal_Grey: ZmbM_ConstrWorkerNormal_Grey
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_FarmerFat_Beige: ZmbM_FarmerFat_Beige
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_FarmerFat_Green: ZmbM_FarmerFat_Green
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_FirefighterNormal: ZmbM_FirefighterNormal
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_FishermanOld_Grey: ZmbM_FishermanOld_Grey
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_HandymanNormal_Beige: ZmbM_HandymanNormal_Beige
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_NBC_Grey: ZmbM_NBC_Grey
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_NBC_Yellow: ZmbM_NBC_Yellow
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_ParamedicNormal_Black: ZmbM_ParamedicNormal_Black
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_PatrolNormal_Flat: ZmbM_PatrolNormal_Flat
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_PolicemanFat: ZmbM_PolicemanFat
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_PolicemanSpecForce_Heavy: ZmbM_PolicemanSpecForce_Heavy
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_PrisonerSkinny: ZmbM_PrisonerSkinny
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_Santa: ZmbM_Santa
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_SkaterYoung_Blue: ZmbM_SkaterYoung_Blue
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_priestPopSkinny: ZmbM_priestPopSkinny
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_usSoldier_Heavy_Woodland: ZmbM_usSoldier_Heavy_Woodland
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_usSoldier_normal_Desert: ZmbM_usSoldier_normal_Desert
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    class HC_ZmbM_Sleeper_ZmbM_usSoldier_normal_Woodland: ZmbM_usSoldier_normal_Woodland
    {
        scope = 2;
        hcSpawnPose = 2;
        class enfanimsys
        {
            meshObject = "dz\characters\zombies\z_hermit_m.xob";
            graphname = "HollowCountryAnims\anims\infected\hc_infected.agr";
            defaultinstance = "HollowCountryAnims\anims\infected\hc_infected.asi";
            skeletonName = "hermit_newbindpose.xob";
            startnode = "HCMasterControl";
        };
    };
    // END GENERATED CE OUTFITS
};
