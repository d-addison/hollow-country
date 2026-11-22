//# file: mods/HollowCountry/scripts/4_World/Fixture/SpawnerBase.c
class HCSpawnerHandler
{
    static void HCSpawnLayer(string layer, vector origin)
    {
    }
}
//# file: mods/HollowCountry/scripts/4_World/Fixture/SpawnerModded.c
modded class HCSpawnerHandler
{
    override static void HCSpawnLayer(string layer, vector origin)
    {
        Print(layer);
    }
}
