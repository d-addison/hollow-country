class HCScanBase
{
    int Visited;
}

//# file: mods/HollowCountry/scripts/4_World/Fixture/FixtureOther.c
modded class HCScanBase
{
    void Reset()
    {
        Visited = 0;
        Cursor = 0;
    }
}
