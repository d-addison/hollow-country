//# file: mods/HollowCountry/scripts/4_World/Fixture/Record.c
class HCRecord
{
    int Until;
}
//# file: mods/HollowCountry/scripts/4_World/Fixture/RecordExtra.c
modded class HCRecord
{
    int Expires;
}
//# file: mods/HollowCountry/scripts/4_World/Fixture/Reader.c
class HCProbe
{
    int Read(HCRecord record)
    {
        return record.Expires;
    }
}
