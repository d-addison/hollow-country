// Native scripts-1.30.164289: EnSystem.c:397/417/425/443/462/525/528;
// JsonFileLoader.c:69,85. Shared staged writer verifies intent and primary.
// Recovery and writing go through the shared HCStagedStore (primary-wins). The v1 layout is
// unchanged: cycle-<world>.json plus a transient .tmp, no backup; the codec checks structure only,
// so a file the cadence rules refuse today is never moved or deleted by recovery. An unrecoverable
// copy refuses admission with a reason; never silently reset the cadence.
class HCEcologyCycleCodec : HCStagedStoreCodec
{
    override bool HCValid(string text, out int revision)
    {
        revision = 0;
        if (text == "" || text.Length() > 2048) { return false; }
        string error;
        HCEcologyCycleState parsed;
        if (!JsonFileLoader<HCEcologyCycleState>.LoadData(text, parsed, error)) { return false; }
        return parsed != null;
    }
}

class HCEcologyCycleSaveJob : HCSaveJob
{
    ref HCStagedStore Store;
    bool Failed;
    bool Committed;
    override string HCName() { return "EcologyCycle"; }
    override int HCStep()
    {
        if (!Store) { Failed = true; return STEP_FAILED; }
        int result = Store.HCStepSave();
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

    // The damaged copy could not be moved aside and verified: it stays exactly where it is (nothing is
    // deleted or overwritten) and Ecology runs this boot from fresh in-memory cycle state with no save.
    // The line names the operator action; the next boot retries the recovery by itself.
    static HCEcologyCycleState HCInMemory(HCEcologyCycleSaveJob job, string world, int utc, string reason)
    {
        HCEcologyCycleState fallback = new HCEcologyCycleState;
        fallback.Version = 1;
        fallback.WorldName = world;
        fallback.EpochUtc = utc;
        job.Committed = true;
        Print("[HC Ecology] cycle store unrecoverable reason=" + reason + " file=cycle-" + world + ".json action=kept_in_place cadence=in_memory_this_boot operator=delete_or_repair_the_file_to_persist_the_cadence");
        return fallback;
    }

    static HCEcologyCycleState Open(HCEcologyCycleSaveJob job, string world, int utc)
    {
        if (!HCEcologyMigrationRules.UtcValid(utc)) { return null; }
        string path = "$profile:HollowCountry/Ecology/cycle-" + world + ".json";
        // Primary-wins: a valid primary is kept, a valid lone .tmp (first-ever save cut short) is
        // promoted, a stale .tmp is preserved as a torn copy. A primary with no valid sibling is moved
        // into a verified .torn.N slot (copy, read-back, byte-compare, then delete) and the cadence
        // starts fresh, so one torn 2 KB file never refuses Ecology on every later boot. The core
        // self-test verdict is deliberately not consulted: its scratch directory is not this store's path.
        job.Store = new HCStagedStore(path, 2048, HCStagedStore.HC_PRIMARY_WINS, new HCEcologyCycleCodec, false, true);
        int drained = job.Store.HCDrainRecover();
        if (drained != HCSaveJob.STEP_DONE && job.Store.HCFailReason() == "drain_guard") { drained = job.Store.HCDrainResume(); }
        if (drained != HCSaveJob.STEP_DONE || job.Store.HCQuarantined())
        {
            return HCInMemory(job, world, utc, job.Store.HCRecoverReason() + "/" + job.Store.HCFailReason());
        }
        HCEcologyCycleState state;
        string text = job.Store.HCRecovered();
        string error;
        if (text != "")
        {
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
        if (!job.Store.HCBeginSave(text)) { return null; }
        job.HCDirty = true;
        job.HCUrgent = true;
        job.HCDue = GetGame().GetTickTime();
        return state;
    }
}
