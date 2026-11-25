modded class MissionServer
{
    override void OnInit()
    {
        super.OnInit();
        HCServer.Get().Start();
        HCLogCameraMode();
    }

    // Owner rule: first person on foot, third person in vehicles (disable3rdPerson=0 plus thirdPersonView=2).
    // Native mode source: 3_Game/Global/World.c:301 enum, 4_World/Entities/DayZPlayerImplement.c:2032 reader.
    void HCLogCameraMode()
    {
        if (!GetGame() || !GetGame().GetWorld()) return;
        int viewMode = GetGame().GetWorld().GetThirdPersonViewMode();
        string viewLabel = "unknown " + viewMode.ToString();
        if (viewMode == ThirdPersonMode.ENABLED) viewLabel = "third person";
        if (viewMode == ThirdPersonMode.DISABLED) viewLabel = "first person only";
        if (viewMode == ThirdPersonMode.VEHICLES_ONLY) viewLabel = "first person on foot, third person in vehicles";
        Print("[HollowCountry] Camera mode: " + viewLabel);
        // No script setter exists (World.c:177 is a reader); the operator owns serverDZ.cfg.
        if (viewMode != ThirdPersonMode.VEHICLES_ONLY) Print("[HollowCountry] Camera mode WARNING: owner rule is first person on foot, third person in vehicles; set thirdPersonView = 2; and disable3rdPerson = 0; in serverDZ.cfg and restart");
    }

    override void OnMissionFinish()
    {
        HCServer.HCBeginMissionFinish();
        HCGroundCELoot.HCFinish();
        HCScenesModule.HCFinish();
        HCServer.Get().Stop();
        HCServer.HCReportTeardown();
        HCModuleReadiness.HCUseShutdown();
        super.OnMissionFinish();
    }
}
