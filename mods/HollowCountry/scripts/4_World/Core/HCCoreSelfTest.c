// Native scripts-1.30.164289: EnSystem.c:106 TickCount, :397 FileExist,
// :417 OpenFile, :425 ReadFile, :443 CloseFile, :525 MakeDirectory, :528 DeleteFile;
// JsonFileLoader.c:69 LoadData; Game.c:1120 IsServer; EnDebug.c:96 Print.
// Three receipts per script lifetime. No live job registration or settings mutation.
// The save probe takes one configured scheduler slice per core tick, <=64 ticks.
class HCCoreDeadlineProbe : HCWorkBudget
{
    bool Run(out string detail)
    {
        HCReset(1000000, 0.1);
        bool first = HCContinue();
        int elapsed;
        // Bounded synthetic overrun of the first cooperative unit. Never waits on
        // mission time (which is fixed inside a tick), nor changes calibration.
        for (int i = 0; i < 65536; i++)
        {
            elapsed = TickCount(m_SliceStart);
            if (elapsed < 0 || (float)elapsed / m_SliceTicksPerMs / 1000.0 >= m_Deadline) { break; }
        }
        bool expired = elapsed >= 0 && (float)elapsed / m_SliceTicksPerMs / 1000.0 >= m_Deadline;
        bool refused = !HCContinue();
        detail = "clock=TickCount elapsed_ticks=" + elapsed.ToString() + " cooperative_next_unit_refused=" + refused.ToString();
        return first && expired && refused && m_Used == 1;
    }
}

class HCCoreSelfTestSaveJob : HCSaveJob
{
    int Records;
    int Written;
    int Calls;
    string Expected;
    ref HCStagedSaveImage Image = new HCStagedSaveImage;
    override string HCName() { return "core_selftest"; }
    override int HCStep()
    {
        Calls++;
        if (Written < Records)
        {
            // One synthetic record per stage; no gameplay DTOs or state touched.
            Expected += "record=" + Written.ToString() + ";";
            Written++;
            return STEP_MORE;
        }
        if (!Image.Active())
        {
            if (!Image.Begin(HCCoreSelfTest.PATH, Expected, 1024, false, false)) { return STEP_FAILED; }
        }
        return Image.HCStepImage();
    }
}

// A private instance exercises the real scheduler's stage cap, time budget and
// completion flags. It is never started, ticked via OnTick, or registered.
modded class HCSaveScheduler
{
    int HCCoreSelfTestSlice(HCSaveJob job)
    {
        m_TickStages = 0;
        HCRunStages(job, GetGame().GetTickTime());
        return m_TickStages;
    }
}

class HCCoreSelfTest
{
    static const string PATH = "$profile:HollowCountry/core-selftest.records";
    protected static bool s_Started;
    protected static int s_Ticks;
    protected static bool s_StepValid = true;
    protected static ref HCCoreSelfTestSaveJob s_Job;
    protected static ref HCSaveScheduler s_Scheduler;

    static void Receipt(string name, bool passed, string detail)
    {
        Print("[HC SelfTest] name=" + name + " pass=" + passed.ToString() + " detail=" + detail);
    }

    static bool Cleanup()
    {
        bool clean = true;
        if (FileExist(PATH) && !DeleteFile(PATH)) { clean = false; }
        if (FileExist(PATH + ".tmp") && !DeleteFile(PATH + ".tmp")) { clean = false; }
        return clean;
    }

    static void Begin(HCCoreDeadlineProbe deadline, HCCoreSelfTestSaveJob job)
    {
        if (s_Started || !GetGame() || !GetGame().IsServer()) { return; }
        s_Started = true;
        string detail;
        bool deadlinePassed = deadline.Run(detail);
        Receipt("workbudget_deadline", deadlinePassed, detail);
        CheckJson();
        if (!FileExist("$profile:HollowCountry")) { MakeDirectory("$profile:HollowCountry"); }
        if (!Cleanup())
        {
            Receipt("savescheduler_step", false, "scratch_cleanup_failed");
            return;
        }
        s_Job = job;
        s_Job.Records = HCWorldRuntimeConfig.HCGet().SaveStagesPerTick + 1;
        s_Job.HCDirty = true;
        s_Scheduler = new HCSaveScheduler;
    }

    static void CheckJson()
    {
        // HCPerfConfig.HCGet passes an uninitialized decoded reference to the
        // engine, then HCApply uses HCJsonFields.Has to retain absent defaults.
        // Its zero-fill comment and auditleather_recipes' keep-defaults comment
        // disagree; verify the actual presence-guard contract for either result.
        string text = "{\"SliceMs\":2}";
        string error;
        HCPerfConfig decoded;
        if (!JsonFileLoader<HCPerfConfig>.LoadData(text, decoded, error) || !decoded)
        {
            Receipt("jsonloader_missing_fields", false, "deserialize_failed");
            return;
        }
        bool zeroFill = !decoded.EnableSharedSaves && decoded.SaveStageTargetMs == 0;
        bool defaults = decoded.EnableSharedSaves && decoded.SaveStageTargetMs == 10;
        string observed = "mixed_or_unknown";
        if (zeroFill) { observed = "zero_fill"; }
        if (defaults) { observed = "constructor_defaults"; }
        HCPerfConfig applied = new HCPerfConfig;
        HCOperatorSettingsRegistry.HCPerfInit();
        applied.HCApply(decoded, text);
        bool kept = applied.EnableSharedSaves && applied.SaveStageTargetMs == 10 && applied.SliceMs == 2;
        Receipt("jsonloader_missing_fields", (zeroFill || defaults) && kept, "observed=" + observed + " presence_guard_defaults=" + kept.ToString());
    }

    static void Pump()
    {
        if (!s_Job) { return; }
        s_Ticks++;
        int before = s_Job.Calls;
        int writtenBefore = s_Job.Written;
        int stages = s_Scheduler.HCCoreSelfTestSlice(s_Job);
        int cap = HCWorldRuntimeConfig.HCGet().SaveStagesPerTick;
        // Time-budget yields may make a slice shorter than the configured cap.
        if (stages < 1 || stages > cap || s_Job.Calls - before != stages || s_Job.Written - writtenBefore > stages) { s_StepValid = false; }
        if (!s_Job.HCFaulted && s_Job.HCDirty && s_Ticks < 64) { return; }
        bool passed = s_StepValid && !s_Job.HCFaulted && !s_Job.HCDirty && !s_Job.HCInFlight && s_Job.Written == s_Job.Records;
        string actual;
        FileHandle handle = OpenFile(PATH, FileMode.READ);
        if (handle)
        {
            ReadFile(handle, actual, 1024);
            CloseFile(handle);
        }
        else { passed = false; }
        if (actual != s_Job.Expected) { passed = false; }
        string detail = "records=" + s_Job.Written.ToString() + " stages_per_tick_cap=" + cap.ToString() + " ticks=" + s_Ticks.ToString();
        // Release retained writer handles before removing even failed images.
        s_Scheduler = null;
        s_Job = null;
        if (!Cleanup()) { passed = false; detail += " cleanup_failed"; }
        Receipt("savescheduler_step", passed, detail);
    }

    static void Stop()
    {
        if (!s_Job) { return; }
        s_Scheduler = null;
        s_Job = null;
        bool clean = Cleanup();
        Receipt("savescheduler_step", false, "shutdown_before_completion cleanup=" + clean.ToString());
    }
}
