class HCScanBase
{
    [NonSerialized()] int Attributed;
    ref array<string> Braced = {"a", "b"};
    static const int LIMIT = 4;
    int First, Second;
    int Table[3];
}

//# file: mods/HollowCountry/scripts/4_World/Fixture/FixtureOther.c
modded class HCScanBase
{
    int ExtraCursor;
}

class HCScanUser : HCScanBase
{
    int Sum()
    {
        return Attributed + Braced.Count() + LIMIT + First + Second + Table[0] + ExtraCursor;
    }
}
