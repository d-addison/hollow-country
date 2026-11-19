// W5-PERF shared cooperative services; candidates for promotion to Core.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:914 GetTickTime (seconds),
// :1535 GetTime (mission milliseconds), :945 GetPlayers; Object.c:287 GetPosition;
// 1_Core/proto/EnScript.c:380 Count, :394 Find, :407 Insert, :463 Remove;
// 1_Core/proto/EnDebug.c:96 Print; EnConvert.c:30 int.ToString.
// Bound: guard O(1); callers retain cursors BEFORE yielding. A native call or
// JSON serialization cannot be preempted; 4 ms is a cooperative target only.
class HCWorkBudget
{
    protected float m_Deadline;
    protected float m_Began;
    protected int m_Limit;
    protected int m_Used;
    protected float m_LogAfter;

    void HCReset(int limit, float milliseconds = 4)
    {
        m_Began = GetGame().GetTickTime();
        // Compare a delta: adding 0.004 to a long-running float clock can round
        // back to the same timestamp and starve every future slice.
        m_Deadline = milliseconds / 1000.0;
        m_Limit = limit;
        m_Used = 0;
    }

    bool HCMayContinue(float now)
    {
        if (!(now >= 0) || !(now < m_Deadline) || m_Used >= m_Limit) { return false; }
        m_Used = m_Used + 1;
        return true;
    }

    bool HCContinue() { return HCMayContinue(GetGame().GetTickTime() - m_Began); }

    void HCDeferred(string moduleName, int count)
    {
        if (count < 1) { return; }
        float now = GetGame().GetTickTime();
        if (now < m_LogAfter) { return; }
        m_LogAfter = now + HCWorldRuntimeConfig.HCGet().BudgetDeferredLogSeconds;
        Print("[HollowCountry] perf budget module=" + moduleName + " deferred=" + count.ToString());
    }
}

// One snapshot per native mission frame, shared by owned proximity callers.
// No retained identity/position DTO or full-world enumeration. Core can promote
// this seam to an explicit HCServer.Tick snapshot if other modules adopt it.
class HCPerfPlayers
{
    protected static int s_Frame = -1;
    protected static ref array<Man> s_Players = new array<Man>;

    static array<Man> HCGet()
    {
        int frameTime = GetGame().GetTime();
        if (s_Frame != frameTime)
        {
            s_Frame = frameTime;
            s_Players.Clear();
            GetGame().GetPlayers(s_Players);
        }
        return s_Players;
    }
}

// Only routine checkpoints belong here. Creation, spend, inventory/provenance
// and claim/result durability barriers MUST remain synchronous until their
// callers have durable continuation state. Shutdown bypasses staggering.
// Issue #138: a routine save may span several module ticks. HCStep() runs ONE bounded stage and
// reports whether more stages follow; the default is the unchanged single whole write.
class HCSaveJob
{
    static const int STEP_DONE = 0;
    static const int STEP_MORE = 1;
    static const int STEP_FAILED = 2;
    bool HCDirty;
    float HCDue;
    bool HCInFlight;
    int HCPeakTicks;   // slowest stage logged so far; the [HC Save] line prints only on a new peak
    string HCName() { return "job"; }
    bool HCWrite() { return false; }
    int HCStep()
    {
        if (HCWrite()) { return STEP_DONE; }
        return STEP_FAILED;
    }
}

// Bound: <=32 registered stores examined (operator may lower), ONE save STAGE per tick (a single-step job is one whole
// store; a staged job such as WorldSaves spans several ticks and is never interleaved with another
// job's stage). Existing verified intent/backup/copy writers remain authoritative. Native
// copy/JSON calls have no cancellation API; this does not promise a 5 ms save.
// Per-job new-peak save timing is logged as '[HC Save] job=.. stages=.. max_stage_ticks=.. total_ticks=..
// slowest_stage=..' in raw EnSystem.c:106 TickCount units (divide by ticks_per_ms of the [HC Perf] line);
// slowest_stage is the 1-based stage that took max_stage_ticks (issue #138 round 2).
class HCSaveScheduler : HCModule
{
    protected static ref array<ref HCSaveJob> s_Jobs = new array<ref HCSaveJob>;
    protected static string s_RegistrationFault;
    protected int m_Next;
    protected ref HCWorkBudget m_Budget = new HCWorkBudget;
    protected HCSaveJob m_Active;
    protected int m_Stages;
    protected int m_StageMax;
    protected int m_StageMaxIndex;
    protected int m_TotalTicks;
    protected bool m_Started;
    protected string m_Fault;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "WorldSaves"; }
    // This switch stops routine dispatch only. Owners retain dirty state and their
    // existing synchronous HCFlush/SaveChanged shutdown and durability barriers.
    // It is read once per process; change it with the server stopped.
    override bool IsEnabled(HCSettings settings)
    {
        return settings != null && HCPerfConfig.HCGet().EnableSharedSaves;
    }

    // Wave 16: ready = the scheduler is started and ticking; a writer that faulted and was dropped from the
    // scheduler (see HCRunStep) is a real degradation, reported until the process restarts.
    override HCOperationalStatus HCGetOperationalStatus()
    {
        string fault = m_Fault;
        if (s_RegistrationFault != "") { fault = s_RegistrationFault; }
        HCModuleReadiness.HCDerive(m_Operational, m_Started, "", fault, "save_scheduler_started");
        return m_Operational;
    }

    override void OnStart(HCSettings settings)
    {
        m_Fault = "";
        HCWorldRuntimeConfig.HCGet();
        m_Started = true;
        Print("[HC PerfControl] WorldSaves stages=1 target_ms=" + HCPerfConfig.HCGet().SaveStageTargetMs.ToString() + " cooperative_only=1 runtime=PENDING");
    }

    override void OnStop() { m_Started = false; }

    static void HCRegister(HCSaveJob job)
    {
        if (!job || s_Jobs.Find(job) >= 0) { return; }
        HCWorldRuntimeConfig config = HCWorldRuntimeConfig.HCGet();
        if (s_Jobs.Count() >= config.SaveJobLimit)
        {
            if (s_RegistrationFault != "save_job_capacity")
            {
                s_RegistrationFault = "save_job_capacity";
                Print("[HC WorldRuntime] save_job_capacity; routine registration refused; owner barrier/shutdown flush retained runtime=PENDING");
            }
            return;
        }
        // Operator limits affect routine eligibility, never owner durability barriers.
        job.HCDue = GetGame().GetTickTime() + config.SaveFirstDelaySeconds + s_Jobs.Count() * config.SaveStaggerSeconds;
        s_Jobs.Insert(job);
    }

    // Synchronous path (shutdown, barriers): finishes every remaining stage in this call. A job
    // that never reports completion is abandoned at SaveFlushStageLimit (ceiling 16).
    static bool HCFlush(HCSaveJob job)
    {
        if (!job || (!job.HCDirty && !job.HCInFlight)) { return true; }
        int result = HCSaveJob.STEP_MORE;
        int guard = 0;
        HCWorldRuntimeConfig config = HCWorldRuntimeConfig.HCGet();
        while (result == HCSaveJob.STEP_MORE && guard < config.SaveFlushStageLimit)
        {
            result = job.HCStep();
            guard = guard + 1;
        }
        job.HCInFlight = false;
        if (result != HCSaveJob.STEP_DONE)
        {
            Print("[HC WorldRuntime] save_flush_failed job=" + job.HCName() + " stages=" + guard.ToString() + " runtime=PENDING");
            return false;
        }
        job.HCDirty = false;
        job.HCDue = GetGame().GetTickTime() + config.SaveCoalesceSeconds;
        return true;
    }

    static void HCUnregister(HCSaveJob job)
    {
        int index = s_Jobs.Find(job);
        if (index >= 0) { s_Jobs.Remove(index); }
    }

    // Runs ONE stage of a job and keeps it as the active job until it reports completion.
    protected void HCRunStep(HCSaveJob job, float now)
    {
        int started = TickCount(0);
        int result = job.HCStep();
        int ticks = TickCount(started);
        m_Stages = m_Stages + 1;
        m_TotalTicks = m_TotalTicks + ticks;
        if (ticks > m_StageMax)
        {
            m_StageMax = ticks;
            m_StageMaxIndex = m_Stages;
        }
        HCWorldRuntimeConfig config = HCWorldRuntimeConfig.HCGet();
        if (result == HCSaveJob.STEP_MORE)
        {
            job.HCInFlight = true;
            m_Active = job;
            return;
        }
        job.HCInFlight = false;
        m_Active = null;
        if (result == HCSaveJob.STEP_DONE)
        {
            job.HCDirty = false;
            job.HCDue = now + config.SaveCoalesceSeconds;
            if (m_StageMax > job.HCPeakTicks)
            {
                job.HCPeakTicks = m_StageMax;
                Print("[HC Save] job=" + job.HCName() + " stages=" + m_Stages.ToString() + " max_stage_ticks=" + m_StageMax.ToString() + " total_ticks=" + m_TotalTicks.ToString() + " slowest_stage=" + m_StageMaxIndex.ToString() + "; runtime acceptance pending");
            }
        }
        else
        {
            // Faulted writer preserves its intent; no every-tick retry.
            HCUnregister(job);
            m_Fault = "save_job_write_faulted";
        }
        m_Stages = 0;
        m_StageMax = 0;
        m_StageMaxIndex = 0;
        m_TotalTicks = 0;
    }

    override void OnTick(float deltaTime)
    {
        if (s_Jobs.Count() == 0) { return; }
        float now = GetGame().GetTickTime();
        if (m_Active && (!m_Active.HCInFlight || s_Jobs.Find(m_Active) < 0))
        {
            // Completed or abandoned outside the scheduler (barrier write, stop): its partial stage
            // counts must not be reported as part of the next job's save.
            m_Active = null;
            m_Stages = 0;
            m_StageMax = 0;
            m_StageMaxIndex = 0;
            m_TotalTicks = 0;
        }
        if (m_Active)
        {
            HCRunStep(m_Active, now);
            return;
        }
        HCWorldRuntimeConfig config = HCWorldRuntimeConfig.HCGet();
        m_Budget.HCReset(config.SaveScanLimit, config.SaveScanSliceMs);
        int examined = 0;
        while (examined < s_Jobs.Count() && m_Budget.HCContinue())
        {
            if (m_Next >= s_Jobs.Count()) { m_Next = 0; }
            HCSaveJob job = s_Jobs[m_Next];
            m_Next = m_Next + 1;
            examined = examined + 1;
            if (!job.HCDirty || now < job.HCDue) { continue; }
            HCRunStep(job, now);
            return;
        }
        m_Budget.HCDeferred(GetName(), s_Jobs.Count() - examined);
    }

    // Each owner flushes BEFORE releasing its state in OnStop, irrespective of
    // registry order. No second global flush that could touch a stopped owner.
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCSaveScheduler);
    }
}
