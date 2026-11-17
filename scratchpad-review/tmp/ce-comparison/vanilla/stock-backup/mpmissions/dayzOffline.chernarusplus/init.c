// SYNTHETIC mission, not purchased game source
void main() {}
class CustomMission: MissionServer {}
Mission CreateCustomMission(string path)
{
    return new CustomMission();
}
