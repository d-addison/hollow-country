// #239: the client claim hint listens for the mission's lifetime (HCBuildingClaimHint).
modded class MissionGameplay
{
    override void OnInit()
    {
        super.OnInit();
        HCBuildingClaimHint.Get().Start();
    }

    override void OnMissionFinish()
    {
        HCBuildingClaimHint.Get().Stop();
        super.OnMissionFinish();
    }
}
