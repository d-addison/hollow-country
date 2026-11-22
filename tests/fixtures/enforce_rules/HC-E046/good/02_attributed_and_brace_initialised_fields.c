class HCCampRecord
{
}

modded class HCCampRecord
{
    [NonSerialized()]
    int HCTheftCrateCursor;
    ref array<string> PoliceClasses = {"PersonalRadio", "Binoculars"};
}

class HCProbe
{
    int Read(HCCampRecord camp)
    {
        camp.HCTheftCrateCursor++;
        return camp.PoliceClasses.Count();
    }
}
