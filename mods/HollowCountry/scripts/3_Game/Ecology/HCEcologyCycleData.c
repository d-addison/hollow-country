// Runtime settings live at $profile:HollowCountry/Ecology/cycle.json.
class HCEcologyCycleSettings
{
    int Version = 1;
    bool Enabled = true;
    bool Animals = true;
    bool Infected = true;
    int MaxHerds = 32;
    int MaxMovers = 8;
    int HerdDriftHours = 6;
    int TownShiftDays = 2;
    int InfectedStepSeconds = 600;
    int SummarySeconds = 300;
}

// Persist the cadence, never native handles or a body position to replay.
class HCEcologyCycleState
{
    int Version;
    string WorldName;
    int EpochUtc;
}

modded class HCOperatorSettingsRegistry
{
    protected static bool s_EcologyCycleRegistered;
    static void HCEcologyCycleInit()
    {
        HCInit();
        if (s_EcologyCycleRegistered) { return; }
        s_EcologyCycleRegistered = true;
        HCAdd("EcologyCycle.Enabled", "bool", 1, 0, 1, "HCEcologyCycleSettings");
        HCAdd("EcologyCycle.Animals", "bool", 1, 0, 1, "HCEcologyCycleSettings");
        HCAdd("EcologyCycle.Infected", "bool", 1, 0, 1, "HCEcologyCycleSettings");
        HCAdd("EcologyCycle.MaxHerds", "int", 32, 1, 32, "HCEcologyCycleSettings");
        HCAdd("EcologyCycle.MaxMovers", "int", 8, 1, 8, "HCEcologyCycleSettings");
        HCAdd("EcologyCycle.HerdDriftHours", "int", 6, 1, 24, "HCEcologyCycleSettings");
        HCAdd("EcologyCycle.TownShiftDays", "int", 2, 1, 14, "HCEcologyCycleSettings");
        HCAdd("EcologyCycle.InfectedStepSeconds", "int", 600, 300, 3600, "HCEcologyCycleSettings");
        HCAdd("EcologyCycle.SummarySeconds", "int", 300, 60, 3600, "HCEcologyCycleSettings");
    }
}
