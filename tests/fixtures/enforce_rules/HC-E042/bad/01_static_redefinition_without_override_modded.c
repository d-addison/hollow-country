// 91a364d1: the modded spawner redefined static methods without override.
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
    static void HCSpawnLayer(string layer, vector origin)
    {
        Print(layer);
    }
}
