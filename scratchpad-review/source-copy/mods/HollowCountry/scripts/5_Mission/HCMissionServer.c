modded class MissionServer
{
    override void OnInit()
    {
        super.OnInit();
        HCServer.Get().Start();
    }

    override void OnMissionFinish()
    {
        HCServer.Get().Stop();
        super.OnMissionFinish();
    }
}
