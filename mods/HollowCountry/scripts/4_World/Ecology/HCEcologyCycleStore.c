// Native scripts-1.30.164289: EnSystem.c:397/417/425/443/462/525/528;
// JsonFileLoader.c:69,85. Shared staged writer verifies intent and primary.
// An unfinished intent refuses admission; never silently reset the cadence.
class HCEcologyCycleSaveJob : HCSaveJob
{
    ref HCStagedSaveImage Image = new HCStagedSaveImage;
    bool Failed;
    bool Committed;
    override string HCName() { return "EcologyCycle"; }
    override int HCStep()
    {
        int result = Image.HCStepImage();
        if (result == STEP_FAILED) { Failed = true; }
        if (result == STEP_DONE) { Committed = true; }
        return result;
    }
}

class HCEcologyCycleStore
{
    static HCEcologyCycleSettings Settings()
    {
        HCEcologyCycleSettings settings = new HCEcologyCycleSettings;
        string path = "$profile:HollowCountry/Ecology/cycle.json";
        string text;
        string error;
        if (FileExist(path))
        {
            text = HCEcologyRuntimeIO.Read(path, 2048);
            if (text == "" || !JsonFileLoader<HCEcologyCycleSettings>.LoadData(text, settings, error)) { return null; }
        }
        else
        {
            if (!JsonFileLoader<HCEcologyCycleSettings>.MakeData(settings, text, error) || !HCEcologyRuntimeIO.WriteNew(path, text, 2048)) { return null; }
        }
        if (!settings) { return null; }
        // Native LoadData zero-fills missing scalars. Missing optional keys keep
        // their shipped defaults; explicit false/zero is still validated.
        if (!HCJsonFields.Has(text, "Version")) { return null; }
        if (!HCJsonFields.Has(text, "Enabled")) { settings.Enabled = true; }
        if (!HCJsonFields.Has(text, "Animals")) { settings.Animals = true; }
        if (!HCJsonFields.Has(text, "Infected")) { settings.Infected = true; }
        if (!HCJsonFields.Has(text, "MaxHerds")) { settings.MaxHerds = 32; }
        if (!HCJsonFields.Has(text, "MaxMovers")) { settings.MaxMovers = 8; }
        if (!HCJsonFields.Has(text, "HerdDriftHours")) { settings.HerdDriftHours = 6; }
        if (!HCJsonFields.Has(text, "TownShiftDays")) { settings.TownShiftDays = 2; }
        if (!HCJsonFields.Has(text, "InfectedStepSeconds")) { settings.InfectedStepSeconds = 600; }
        if (!HCJsonFields.Has(text, "SummarySeconds")) { settings.SummarySeconds = 300; }
        HCOperatorSettingsRegistry.HCEcologyCycleInit();
        if (!settings || settings.Version != 1) { return null; }
        if (!HCOperatorSettingsRegistry.HCValid("EcologyCycle.MaxHerds", settings.MaxHerds)) { return null; }
        if (!HCOperatorSettingsRegistry.HCValid("EcologyCycle.MaxMovers", settings.MaxMovers)) { return null; }
        if (!HCOperatorSettingsRegistry.HCValid("EcologyCycle.HerdDriftHours", settings.HerdDriftHours)) { return null; }
        if (!HCOperatorSettingsRegistry.HCValid("EcologyCycle.TownShiftDays", settings.TownShiftDays)) { return null; }
        if (!HCOperatorSettingsRegistry.HCValid("EcologyCycle.InfectedStepSeconds", settings.InfectedStepSeconds)) { return null; }
        if (!HCOperatorSettingsRegistry.HCValid("EcologyCycle.SummarySeconds", settings.SummarySeconds)) { return null; }
        return settings;
    }

    static HCEcologyCycleState Open(HCEcologyCycleSaveJob job, string world, int utc)
    {
        if (!HCEcologyMigrationRules.UtcValid(utc)) { return null; }
        string path = "$profile:HollowCountry/Ecology/cycle-" + world + ".json";
        // #336: clear only a .tmp byte-identical to the primary (hard stop before clear_intent), never mid-save.
        if (FileExist(path + ".tmp") && (job.Image.Active() || !HCStagedSaveImage.HCClearCompletedIntent(path, 2048, "ecology_cycle"))) { return null; }
        HCEcologyCycleState state;
        string text;
        string error;
        if (FileExist(path))
        {
            text = HCEcologyRuntimeIO.Read(path, 2048);
            if (!JsonFileLoader<HCEcologyCycleState>.LoadData(text, state, error)) { return null; }
            if (!state || state.Version != 1 || state.WorldName != world || !HCEcologyMigrationRules.UtcValid(state.EpochUtc) || state.EpochUtc > utc) { return null; }
            job.Committed = true;
            return state;
        }
        state = new HCEcologyCycleState;
        state.Version = 1;
        state.WorldName = world;
        state.EpochUtc = utc;
        if (!JsonFileLoader<HCEcologyCycleState>.MakeData(state, text, error)) { return null; }
        if (!job.Image.Begin(path, text, 2048, false, false)) { return null; }
        job.HCDirty = true;
        job.HCUrgent = true;
        job.HCDue = GetGame().GetTickTime();
        return state;
    }
}
