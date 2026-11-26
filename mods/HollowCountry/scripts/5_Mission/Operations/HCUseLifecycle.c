// Native scripts-1.30.164289: 5_Mission/mission/missionGameplay.c
// OnInit/OnMissionFinish; GUI/InventoryMenu.c:105 and MapMenu.c:177 OnShow.
// Server inventory also declares ClientUI so absent client activity stays zero.
modded class MissionGameplay
{
    protected bool m_HCReleaseAISiteObserved;
    protected bool m_HCReleaseMissionObserved;

    override void OnInit()
    {
        super.OnInit();
        if (GetGame().IsServer()) { return; }
        HCModuleReadiness.HCUseBegin();
        HCModuleReadiness.HCRegisterModuleUses("ClientUI");
        HCModuleReadiness.HCRegisterUse("optional-expansion-human-ai", "site_radius_entered");
        HCModuleReadiness.HCRegisterUse("Events", "mission_radius_entered");
        m_HCReleaseAISiteObserved = false;
        m_HCReleaseMissionObserved = false;
        DayZGame.Event_OnRPC.Insert(HCReceiveReleaseRadius);
    }

    override void OnMissionFinish()
    {
        super.OnMissionFinish();
        if (!GetGame().IsServer())
        {
            DayZGame.Event_OnRPC.Remove(HCReceiveReleaseRadius);
            HCModuleReadiness.HCUseShutdown();
        }
    }

    void HCReceiveReleaseRadius(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (rpcType != HCReleaseRadiusWire.RPC_ENTRY || !ctx || GetGame().IsServer() || sender || target) { return; }
        int observation;
        if (!ctx.Read(observation)) { return; }
        if (observation == HCReleaseRadiusWire.AI_SITE && !m_HCReleaseAISiteObserved)
        {
            m_HCReleaseAISiteObserved = true;
            HCModuleReadiness.HCUse("optional-expansion-human-ai", "site_radius_entered");
        }
        else if (observation == HCReleaseRadiusWire.MISSION && !m_HCReleaseMissionObserved)
        {
            m_HCReleaseMissionObserved = true;
            HCModuleReadiness.HCUse("Events", "mission_radius_entered");
        }
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
