void main() { Hive ce = CreateHive(); if (ce) ce.InitOffline(); }
class CustomMission: MissionServer {}
Mission CreateCustomMission(string path) { return new CustomMission(); }
