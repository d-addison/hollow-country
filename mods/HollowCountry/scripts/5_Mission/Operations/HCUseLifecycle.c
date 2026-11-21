// Native scripts-1.30.164289: 5_Mission/mission/missionGameplay.c
// OnInit/OnMissionFinish; GUI/InventoryMenu.c:105 and MapMenu.c:177 OnShow.
// Server inventory also declares ClientUI so absent client activity stays zero.
modded class MissionGameplay
{
    override void OnInit()
    {
        super.OnInit();
        if (GetGame().IsServer()) { return; }
        HCModuleReadiness.HCUseBegin();
        HCModuleReadiness.HCRegisterModuleUses("ClientUI");
    }

    override void OnMissionFinish()
    {
        super.OnMissionFinish();
        if (!GetGame().IsServer()) { HCModuleReadiness.HCUseShutdown(); }
    }
}

modded class InventoryMenu
{
    override void OnShow()
    {
        super.OnShow();
        if (layoutRoot) { HCModuleReadiness.HCUse("ClientUI", "inventory_open"); }
    }
}

modded class MapMenu
{
    override void OnShow()
    {
        super.OnShow();
        if (layoutRoot) { HCModuleReadiness.HCUse("ClientUI", "map_open"); }
    }
}
