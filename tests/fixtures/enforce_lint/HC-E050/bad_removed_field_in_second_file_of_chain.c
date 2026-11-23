class HCScanBase
{
    int Visited;
}

//# file: mods/HollowCountry/scripts/4_World/Fixture/FixtureOther.c
class HCScanTactics : HCScanBase
{
    int Step()
    {
        Visited++;
        return Actor;
    }
}
