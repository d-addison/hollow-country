void main() { Hive ce = CreateHive();
    if (!ce) return;

    HCDS.Begin();
}
class CustomMission: MissionServer {}
Mission CreateCustomMission(string path) { return new HCDSMission(); }

class HCDSMission : CustomMission
{
    override void OnMissionFinish()
    {
        HCDS.Interrupt();
        super.OnMissionFinish();
    }
}
