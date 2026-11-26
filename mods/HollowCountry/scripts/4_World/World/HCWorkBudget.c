// W5-PERF shared cooperative services; candidates for promotion to Core.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:914 GetTickTime (seconds),
// :1535 GetTime (mission milliseconds), :945 GetPlayers; Object.c:287 GetPosition;
// 1_Core/proto/EnScript.c:380 Count, :394 Find, :407 Insert, :463 Remove;
// 1_Core/proto/EnDebug.c:96 Print; EnConvert.c:30 int.ToString;
// EnSystem.c:106 TickCount (performance-counter ticks since prev).
// Bound: guard O(1); callers retain cursors BEFORE yielding. A native call or
// JSON serialization cannot be preempted; 4 ms is a cooperative target only.
// #278: GetTickTime stays fixed inside a server tick. Use TickCount for slices.
class HCWorkBudget
{
    // TickCount units are undocumented; one validated conversion serves all budgets.
    protected static float s_TicksPerMs = 10000;
    protected static bool s_ClockValidated;
    protected static int s_ClockTick;
    protected static float s_ClockTime;
    protected static bool s_ClockSeeded;
    protected static int s_ClockRejected;
    protected static int s_ClockReported;
    protected float m_Deadline;
    protected int m_SliceStart;
    protected float m_SliceTicksPerMs;
    protected int m_Limit;
    protected int m_Used;
    protected float m_LogAfter;

    // Invalid/stopped sampler windows retain the last valid rate (or boot seed).
    // Snapshot on reset so publication cannot change an active slice's deadline.
    static bool HCSetTicksPerMs(float ticksPerMs)
    {
        if (!(ticksPerMs >= HC_PERF_MIN_TICKS_PER_MS && ticksPerMs <= HC_PERF_MAX_TICKS_PER_MS)) { return false; }
        // Admit the first validated sample directly; smooth later samples in O(1).
        if (s_ClockValidated) { s_TicksPerMs = s_TicksPerMs * 0.75 + ticksPerMs * 0.25; }
        else { s_TicksPerMs = ticksPerMs; }
        s_ClockValidated = true;
        return true;
    }

    static float HCTicksPerMs() { return s_TicksPerMs; }

    protected static void HCRejectCalibration()
    {
        s_ClockRejected++;
        if (s_ClockRejected == 1)
        {
            Print("[HC Clock] rejected=1 retained_ticks_per_ms=" + s_TicksPerMs.ToString() + " runtime=PENDING");
        }
    }

    // Called by the existing perf-window emission, never by the hot reset path.
    static void HCPrintCalibrationSummary()
    {
        if (s_ClockRejected == s_ClockReported) { return; }
        int rejectedWindow = s_ClockRejected - s_ClockReported;
        Print("[HC Clock] rejected_window=" + rejectedWindow.ToString() + " rejected_total=" + s_ClockRejected.ToString() + " retained_ticks_per_ms=" + s_TicksPerMs.ToString() + " runtime=PENDING");
        s_ClockReported = s_ClockRejected;
    }

    // Shared calibration across startup and steady-state frames. Anchor a whole
    // >=1 s window: float uptime quantization must not amplify single-frame error.
    // No allocation, per-frame accumulation or counter read before the window ends.
    static void HCCalibrate()
    {
        if (!GetGame()) { return; }
        float now = GetGame().GetTickTime();
        if (s_ClockSeeded)
        {
            float intervalSeconds = now - s_ClockTime;
            if (intervalSeconds >= 0 && intervalSeconds < 1) { return; }
            bool accepted = false;
            if (intervalSeconds >= 1 && intervalSeconds <= HC_PERF_MAX_WINDOW_SECONDS)
            {
                int ticks = TickCount(s_ClockTick);
                if (ticks > 0) { accepted = HCSetTicksPerMs((float)ticks / (intervalSeconds * 1000)); }
            }
            if (!accepted) { HCRejectCalibration(); }
        }
        s_ClockTime = now;
        s_ClockTick = TickCount(0);
        s_ClockSeeded = true;
    }

    void HCReset(int limit, float milliseconds = 4)
    {
        HCCalibrate();
        m_SliceStart = TickCount(0);
        m_SliceTicksPerMs = s_TicksPerMs;
        // Keep HCMayContinue's elapsed-seconds contract and compare deltas,
        // avoiding precision loss from adding a small slice to an uptime.
        m_Deadline = milliseconds / 1000.0;
        m_Limit = limit;
        if (m_SliceTicksPerMs <= 0) { m_Limit = Math.Min(limit, 1); }
        m_Used = 0;
    }

    bool HCMayContinue(float now)
    {
        if (!(now >= 0) || !(now < m_Deadline) || m_Used >= m_Limit) { return false; }
        m_Used = m_Used + 1;
        return true;
    }

    bool HCContinue()
    {
        // Preserve first-unit progress under a positive deadline/unit cap,
        // including work done between reset and this first guard. Zero/negative
        // deadlines and exhausted unit caps still refuse in HCMayContinue.
        float elapsed = 0;
        if (m_Used > 0)
        {
            int elapsedTicks = TickCount(m_SliceStart);
            // Negative deltas refuse the remainder of this slice; reset seeds
            // a fresh counter next time. Never convert a raw uptime to float.
            if (elapsedTicks < 0) { return false; }
            if (m_SliceTicksPerMs <= 0) { return false; }
            elapsed = (float)elapsedTicks / m_SliceTicksPerMs / 1000.0;
        }
        return HCMayContinue(elapsed);
    }

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
// reports whether more stages follow; each owner must supply its staged implementation.
class HCSaveJob
{
    static const int STEP_DONE = 0;
    static const int STEP_MORE = 1;
    static const int STEP_FAILED = 2;
    static string HCOperation; // operation executed by the current scheduler stage
    bool HCDirty;
    float HCDue;
    // Routine debounce is measured from the last clean commit.
    float HCLastCommitSeconds;
    bool HCHasCommitted;
    float HCInterval()
    {
        return HCWorldRuntimeConfig.HCGet().SaveCoalesceSeconds;
    }
    void HCCommitted(float now)
    {
        HCLastCommitSeconds = now;
        HCHasCommitted = true;
        HCDue = now + HCInterval();
    }
    bool HCInFlight;
    bool HCUrgent; // durable continuation, including when routine scheduling is off
    // Crash-safe publish chain whose caller waits on it (event journal). Dispatched before
    // every other job, including other urgent ones, at stage boundaries (issue #333).
    bool HCPreempt;
    bool HCFaulted;
    int HCPeakTicks;   // slowest stage logged so far; the [HC Save] line prints only on a new peak
    // Checkpoint counters for the [HC Save] summary, per job so a parked job keeps its own.
    int HCStatStages;
    int HCStatStageMax;
    int HCStatStageMaxIndex;
    string HCStatStageMaxOperation;
    int HCStatTotalTicks;
    int HCStatJobTicks;
    int HCStatMaxPerTick;
    void HCResetStats()
    {
        HCStatStages = 0;
        HCStatStageMax = 0;
        HCStatStageMaxIndex = 0;
        HCStatStageMaxOperation = "";
        HCStatTotalTicks = 0;
        HCStatJobTicks = 0;
        HCStatMaxPerTick = 0;
    }
    string HCName() { return "job"; }
    // Snapshot owners may have newer requests after a committed image.
    bool HCPendingCheckpoint() { return false; }
    int HCStep() { return STEP_FAILED; }
}

// Bound: <=32 registered stores examined (operator may lower), one stage per routine dispatch
// (HC_DISPATCH_STAGES) and up to HC_URGENT_DISPATCH_STAGES per preempt/urgent dispatch, both under the
// cooperative SaveStageTargetMs deadline. Only ONE job advances per dispatch.
// Issue #333: dispatch picks by priority (HCPreempt journal, then HCUrgent, then routine) at
// stage boundaries, so a higher-priority job parks a retained lower one that resumes where it
// stopped; jobs own their cursors and handles, so a parked job is exactly a job that waited.
// Urgent and preempt jobs are also dispatched once per frame (SYSTEM update queue, at most
// HC_FRAME_MS per frame); routine jobs advance on the 1 Hz module tick only. On the tick a
// preempt job still ranks first, then an in-flight or due routine job, then plain urgent work
// (which already has the frame drive), so a perpetually urgent image cannot starve routine saves.
// Preempt and urgent jobs are always scanned (<= SaveJobLimit entries); only the routine scan is
// bounded by SaveScanLimit, and its start cursor rotates so no routine job is left outside the window.
// Known and benign (kept): a job parked mid-image resumes at the next dispatch of its own class, so a
// parked routine image can wait a tick or more; stats and dispatch counts are per dispatch (tick or frame).
// Existing verified intent/backup/copy writers remain authoritative. Native
// copy/JSON calls have no cancellation API; the time target is cooperative.
// Per-job new-peak save timing is logged as '[HC Save] job=.. stages=.. max_stage_ticks=.. total_ticks=..
// slowest_stage=.. op=.. runtime=PENDING' in raw EnSystem.c:106 TickCount units (divide by ticks_per_ms of the [HC Perf] line);
// slowest_stage is the 1-based stage that took max_stage_ticks (issue #138 round 2).
// scheduler_ticks counts this checkpoint's dispatches (tick or frame); max_stages_per_tick records
// actual throughput. Peak-only logging is unchanged; counters reset per checkpoint.
class HCSaveScheduler : HCModule
{
    protected static ref array<ref HCSaveJob> s_Jobs = new array<ref HCSaveJob>;
    protected static string s_RegistrationFault;
    protected int m_Next;
    protected ref HCWorkBudget m_Budget = new HCWorkBudget;
    protected ref HCSaveStageBudget m_StageBudget = new HCSaveStageBudget;
    protected int m_TickStages;
    protected int m_StageLimit = 1; // stage cap of the dispatch that is running or ran last
    // ref: HCSaveJob is not Managed. An owner that quarantines unregisters and drops its job outside the
    // dispatch (HCInfectedModule.Quarantine), which freed a raw m_Active held across ticks.
    protected ref HCSaveJob m_Active;
    protected int m_SelectIndex;
    protected bool m_InDispatch;      // set for the whole of a dispatch; still set on entry = the last one aborted
    protected int m_TickDispatchMs = -1; // GetTime() of the last module-tick dispatch (one dispatch per frame)
    protected string m_DispatchedName;
    // Per-60 s window of the frame-driven dispatches, printed as [HC Step] owner=WorldSavesFrame so the
    // release R2 gate (worst_tick_ticks) sees the cost that bypasses the module tick sample.
    protected float m_FrameWindow;
    protected int m_FrameSeq;
    protected int m_FrameCount;
    protected int m_FrameWorst;
    protected int m_FrameWorstStages;
    protected string m_FrameWorstJob;
    // Per-frame dispatch budget (ms, cooperative). Urgent and preempt jobs run per frame from
    // their first stage; a routine job is STARTED by the 1 Hz module tick and then driven per frame
    // until it completes, so no image waits one second per stage.
    static const int HC_FRAME_MS = 2;
    // A routine dispatch, tick or frame, runs exactly one stage (one native file operation) and at most
    // one dispatch runs per frame. A preempt or urgent dispatch runs up to HC_URGENT_DISPATCH_STAGES
    // stages while the dispatch budget lasts (the first stage always runs). The SaveStagesPerTick
    // setting no longer widens this; it bounds the owner fallback pump only.
    static const int HC_DISPATCH_STAGES = 1;
    // Preempt and urgent jobs (custody, journals, durable continuations) may run up to this many
    // stages in one dispatch, still inside the dispatch time budget (HC_FRAME_MS per frame): a
    // one-stage dispatch made a ~10 call image take ten frames. Routine jobs stay at one stage.
    static const int HC_URGENT_DISPATCH_STAGES = 8;
    protected bool m_FrameInstalled;
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
        if (!m_FrameInstalled)
        {
            m_FrameInstalled = true;
            GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Insert(HCFrame);
        }
        Print("[HC PerfControl] WorldSaves target_ms=" + HCPerfConfig.HCGet().SaveStageTargetMs.ToString() + " scope=tick_stages stages_per_dispatch=" + HC_DISPATCH_STAGES.ToString() + " urgent_stages_per_dispatch=" + HC_URGENT_DISPATCH_STAGES.ToString() + " frame_ms=" + HC_FRAME_MS.ToString() + " frame_scope=urgent_preempt_in_flight cooperative_only=1 runtime=PENDING");
    }

    override void OnStop()
    {
        m_Started = false;
        if (m_FrameInstalled && GetGame())
        {
            GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Remove(HCFrame);
        }
        m_FrameInstalled = false;
        m_InDispatch = false;
        m_TickDispatchMs = -1;
    }

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
    // that never reports completion is abandoned at the configured limit. Only custody opts into a larger default.
    static bool HCFlush(HCSaveJob job, bool custodyBarrier = false)
    {
        if (!job || (!job.HCDirty && !job.HCInFlight)) { return true; }
        // Parameters are weak: a failing step may quarantine its owner, which unregisters and drops
        // this job (build 151: NULL 'HCInFlight' after HCInfectedSaveJob.HCStep). Hold it for the call.
        HCSaveJob hold = job;
        if (job.HCFaulted) { return false; }
        int result = HCSaveJob.STEP_MORE;
        int guard = 0;
        HCWorldRuntimeConfig config = HCWorldRuntimeConfig.HCGet();
        // Custody alone needs room for two maximum-size images (an older snapshot
        // plus a refresh). Explicit lower operator limits remain authoritative.
        // Replacement core: prior + tmp write/read + backup read + primary read
        // <=5*N+64 stages (CopyFile is one stage), N=ceil(bytes/4096).
        // At 8 MiB: <=10,304/image; two <=20,608 < 33,088 (2*16,512+64).
        // SearchRefresh.Stop opts into this barrier; its 6 MiB cap needs
        // <=7,744/image, two <=15,488. Finish's 16,512 covers one max image.
        // Explicit limits below the default 4096 still intentionally refuse.
        int flushLimit = config.SaveFlushStageLimit;
        // Journal shutdown drains need room for three capped immutable images,
        // their prior checks and pruning, even with a low routine operator limit.
        if (job.HCName() == "EventJournal") { flushLimit = Math.Max(flushLimit, 3 * HCStagedSaveImage.HC_MAX_STAGES + 128); }
        // Search journal barrier: up to 256 queued ops (HCSearchJournalJob.MAX_OPS) at <=12 stages each
        // (a record is <=8192 bytes). A literal: a cross-class constant expression read as 0 natively.
        if (job.HCName() == "SearchJournal") { flushLimit = Math.Max(flushLimit, 3136); }
        if (custodyBarrier && flushLimit == 4096) { flushLimit = 2 * HCStagedSaveImage.HC_MAX_STAGES + 64; }
        while ((result == HCSaveJob.STEP_MORE || (result == HCSaveJob.STEP_DONE && job.HCPendingCheckpoint())) && guard < flushLimit)
        {
            result = job.HCStep();
            guard = guard + 1;
        }
        if (guard >= flushLimit && (result == HCSaveJob.STEP_MORE || (result == HCSaveJob.STEP_DONE && job.HCPendingCheckpoint())))
        {
            Print("[HC WorldRuntime] owner=" + job.HCName() + " guard=save_flush_stage_guard steps=" + guard.ToString());
        }
        job.HCInFlight = false;
        if (result != HCSaveJob.STEP_DONE || job.HCPendingCheckpoint())
        {
            job.HCFaulted = true;
            // A faulted job is never dispatched again; release its scheduler slot.
            HCUnregister(job);
            Print("[HC WorldRuntime] save_flush_failed job=" + job.HCName() + " stages=" + guard.ToString() + " runtime=PENDING");
            return false;
        }
        job.HCDirty = false;
        job.HCUrgent = false;
        job.HCCommitted(GetGame().GetTickTime());
        return true;
    }

    // True when routine dispatch owns this job; a job refused at save_job_capacity must
    // advance its own stages (bounded) or it never clears its dirty state.
    static bool HCRegistered(HCSaveJob job)
    {
        return job && s_Jobs.Find(job) >= 0;
    }

    // Durable continuations still advance when routine scheduling is disabled or
    // registration was refused. Owners call once per tick; never drain a job here.
    static void HCPumpFallback(HCSaveJob job)
    {
        if (!job || job.HCFaulted || !job.HCUrgent || !job.HCDirty || (HCPerfConfig.HCGet().EnableSharedSaves && HCRegistered(job))) { return; }
        // Parameters are weak: a failing step may quarantine its owner, which unregisters and drops
        // this job (build 151: NULL 'HCInFlight' after HCInfectedSaveJob.HCStep). Hold it for the call.
        HCSaveJob hold = job;
        int result = job.HCStep();
        job.HCInFlight = result == HCSaveJob.STEP_MORE;
        if (result == HCSaveJob.STEP_DONE)
        {
            job.HCDirty = job.HCPendingCheckpoint();
            if (!job.HCDirty) { job.HCUrgent = false; }
            job.HCCommitted(GetGame().GetTickTime());
        }
        if (result == HCSaveJob.STEP_FAILED) { job.HCFaulted = true; }
    }

    static void HCUnregister(HCSaveJob job)
    {
        int index = s_Jobs.Find(job);
        if (index >= 0) { s_Jobs.Remove(index); }
    }

    // Runs ONE stage of a job and keeps it as the active job until it reports completion.
    protected void HCRunStep(HCSaveJob job, float now)
    {
        // Parameters are weak: a failing step may quarantine its owner, which unregisters and drops
        // this job (build 151: NULL 'HCInFlight' after HCInfectedSaveJob.HCStep). Hold it for the call.
        HCSaveJob hold = job;
        HCSaveJob.HCOperation = "checkpoint";
        int started = TickCount(0);
        int result = job.HCStep();
        int ticks = TickCount(started);
        job.HCStatStages = job.HCStatStages + 1;
        job.HCStatTotalTicks = job.HCStatTotalTicks + ticks;
        if (ticks > job.HCStatStageMax)
        {
            job.HCStatStageMax = ticks;
            job.HCStatStageMaxIndex = job.HCStatStages;
            job.HCStatStageMaxOperation = HCSaveJob.HCOperation;
        }
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
            job.HCDirty = job.HCPendingCheckpoint();
            if (!job.HCDirty) { job.HCUrgent = false; }
            job.HCCommitted(now);
            HCModuleReadiness.HCUse("WorldSaves", "stage_written");
            if (job.HCStatStageMax > job.HCPeakTicks)
            {
                job.HCPeakTicks = job.HCStatStageMax;
                string timing = "[HC Save] job=" + job.HCName() + " stages=" + job.HCStatStages.ToString() + " max_stage_ticks=" + job.HCStatStageMax.ToString() + " total_ticks=" + job.HCStatTotalTicks.ToString();
                timing += " scheduler_ticks=" + job.HCStatJobTicks.ToString() + " max_stages_per_tick=" + job.HCStatMaxPerTick.ToString();
                timing += " stage_limit=" + m_StageLimit.ToString() + " slowest_stage=" + job.HCStatStageMaxIndex.ToString() + " op=" + job.HCStatStageMaxOperation + " runtime=PENDING";
                Print("" + timing);
            }
        }
        else
        {
            // Faulted writer preserves its intent; no every-tick retry.
            job.HCFaulted = true;
            HCUnregister(job);
            // Events and the search journal own their journal admission/failure readiness (the search
            // journal reports through HCJobFailed); an unrelated store must not become unready because
            // this one candidate failed.
            if (job.HCName() == "EventJournal" || job.HCName() == "SearchJournal") { Print("[HC Save] job=" + job.HCName() + " state=failed reason=job_local runtime=PENDING"); }
            else { m_Fault = "save_job_write_faulted"; }
        }
        job.HCResetStats();
    }

    // Check both limits between stages; one atomic native operation may overrun.
    // budgetMs 0 = the configured SaveStageTargetMs; a smaller value only tightens it.
    protected void HCRunStages(HCSaveJob job, float now, int budgetMs = 0)
    {
        int targetMs = HCPerfConfig.HCGet().SaveStageTargetMs;
        if (budgetMs > 0) { targetMs = Math.Min(targetMs, budgetMs); }
        m_StageLimit = HC_DISPATCH_STAGES;
        if (job.HCPreempt || job.HCUrgent) { m_StageLimit = HC_URGENT_DISPATCH_STAGES; }
        m_StageBudget.HCReset(m_StageLimit, targetMs);
        // A job not in flight starts a new checkpoint; a flush may have left old counters.
        if (!job.HCInFlight) { job.HCResetStats(); }
        job.HCStatJobTicks = job.HCStatJobTicks + 1;
        while (m_StageBudget.HCContinue())
        {
            m_TickStages = m_TickStages + 1;
            if (m_TickStages > job.HCStatMaxPerTick) { job.HCStatMaxPerTick = m_TickStages; }
            HCRunStep(job, now);
            HCReached.Mark("world_saves.stage");
            if (!m_Active) { break; }
        }
    }

    protected static int HCPriority(HCSaveJob job)
    {
        if (job.HCPreempt) { return 2; }
        if (job.HCUrgent) { return 1; }
        return 0;
    }

    // Highest ranked dispatchable job. Rank: preempt 16; tick mode (routine=true): due/in-flight routine 4,
    // plain urgent 0; frame mode (routine=false): urgent 8, in-flight routine 2, a routine job that is not
    // in flight never. Ties keep the active job (+2), then any in-flight job (+1), then ring order from m_Next;
    // the bonuses never lift a lower class over a higher one. Preempt and urgent jobs are scanned without the scan cap;
    // routine positions are bounded by SaveScanLimit and examined reports how many ring positions were
    // covered (count when the routine scan was not cut). No allocation.
    protected HCSaveJob HCSelect(float now, bool routine, out int examined)
    {
        HCSaveJob best = null;
        int bestRank = -1;
        int count = s_Jobs.Count();
        bool routineCut = false;
        int scanned = 0;
        examined = count;
        while (scanned < count)
        {
            int index = (m_Next + scanned) % count;
            scanned = scanned + 1;
            HCSaveJob job = s_Jobs[index];
            int priority = HCPriority(job);
            if (priority == 0)
            {
                // Frame mode never starts a routine job; it only continues one already in flight.
                if (!routine)
                {
                    if (!job.HCInFlight) { continue; }
                }
                else
                {
                    if (!routineCut && !m_Budget.HCContinue())
                    {
                        routineCut = true;
                        examined = scanned - 1;
                    }
                    if (routineCut) { continue; }
                }
            }
            if (job.HCFaulted || (!job.HCDirty && !job.HCInFlight)) { continue; }
            if (priority == 0 && !job.HCInFlight && (now < job.HCDue || (job.HCHasCommitted && now < job.HCLastCommitSeconds + job.HCInterval()))) { continue; }
            // Frame mode: every urgent job (8..10) outranks every routine job (2..4), and preempt
            // (16..18) outranks both, so a custody checkpoint never waits for a routine backlog.
            // Tick mode keeps routine (4..6) ahead of plain urgent (0..2); the frame drive serves urgent.
            int rank = 4;
            if (priority == 2) { rank = 16; }
            else if (priority == 1)
            {
                rank = 8;
                if (routine) { rank = 0; }
            }
            else if (!routine) { rank = 2; }
            if (job == m_Active) { rank = rank + 2; }
            else if (job.HCInFlight) { rank = rank + 1; }
            if (rank > bestRank)
            {
                bestRank = rank;
                best = job;
                m_SelectIndex = index;
            }
        }
        return best;
    }

    // Diagnostic hook after every dispatch (tick or frame); HCPerfSaveSlices overrides it.
    protected void HCAfterDispatch() {}

    // The previous dispatch never reached its end (a throwing stage aborts the script call): drop the job
    // that was running instead of repeating the exception every frame.
    protected void HCDispatchAborted()
    {
        HCSaveJob bad = m_Active;
        string name = "unknown";
        m_InDispatch = false;
        m_Active = null;
        if (bad)
        {
            name = bad.HCName();
            bad.HCFaulted = true;
            bad.HCInFlight = false;
            HCUnregister(bad);
            if (name != "EventJournal" && name != "SearchJournal") { m_Fault = "save_job_write_faulted"; }
        }
        Print("[HC Save] job=" + name + " state=failed reason=dispatch_aborted runtime=PENDING");
    }

    protected void HCDispatch(float now, bool routine, int budgetMs)
    {
        m_TickStages = 0;
        m_DispatchedName = "";
        int count = s_Jobs.Count();
        if (count == 0) { return; }
        if (m_InDispatch)
        {
            HCDispatchAborted();
            return;
        }
        m_InDispatch = true;
        if (m_Active && (s_Jobs.Find(m_Active) < 0 || !m_Active.HCInFlight))
        {
            // Completed or abandoned outside the scheduler (barrier write, stop).
            m_Active = null;
        }
        if (routine)
        {
            HCWorldRuntimeConfig config = HCWorldRuntimeConfig.HCGet();
            m_Budget.HCReset(config.SaveScanLimit, config.SaveScanSliceMs);
        }
        int examined = count;
        HCSaveJob job = HCSelect(now, routine, examined);
        bool cut = examined < count;
        if (routine)
        {
            // Rotate the routine window so jobs outside SaveScanLimit are reached on later ticks.
            if (cut) { m_Next = (m_Next + examined) % count; }
            else if (job && !job.HCInFlight) { m_Next = (m_SelectIndex + 1) % count; }
        }
        if (job)
        {
            m_Active = job;
            m_DispatchedName = job.HCName();
            HCRunStages(job, now, budgetMs);
            HCAfterDispatch();
        }
        else if (routine) { m_Budget.HCDeferred(GetName(), count - examined); }
        m_InDispatch = false;
    }

    override void OnTick(float deltaTime)
    {
        m_TickDispatchMs = GetGame().GetTime();
        HCDispatch(GetGame().GetTickTime(), true, 0);
    }

    // Cheap flag scan (<= SaveJobLimit entries, no clock, no budget) so an idle frame costs almost nothing.
    protected bool HCHasFrameWork()
    {
        if (m_InDispatch) { return true; }
        int i = 0;
        while (i < s_Jobs.Count())
        {
            HCSaveJob job = s_Jobs[i];
            i = i + 1;
            if (job.HCFaulted) { continue; }
            if (job.HCInFlight) { return true; }
            if ((job.HCPreempt || job.HCUrgent) && job.HCDirty) { return true; }
        }
        return false;
    }

    protected void HCFrameSummary()
    {
        m_FrameWindow = 0;
        if (m_FrameCount == 0) { return; }
        m_FrameSeq = m_FrameSeq + 1;
        // Same field shape as HCStepTimer lines so tick_cost_report counts worst_tick_ticks toward R2.
        Print("[HC Step] owner=WorldSavesFrame window=" + m_FrameSeq.ToString() + " ticks=" + m_FrameCount.ToString() + " worst_tick_ticks=" + m_FrameWorst.ToString() + " worst_tick_items=" + m_FrameWorstStages.ToString() + " save_dispatch=" + m_FrameWorst.ToString() + " other=0 heaviest_item_ticks=0 heaviest=" + m_FrameWorstJob + " deferred_n=0 deferred_max_ticks=0; raw TickCount units; runtime acceptance pending");
        m_FrameCount = 0;
        m_FrameWorst = 0;
        m_FrameWorstStages = 0;
        m_FrameWorstJob = "";
    }

    // Issue #333: one bounded dispatch (one stage) per frame for urgent/preempt jobs and for any job
    // already in flight. The module tick is 1 Hz, which made every journal image take ~31 s at 8
    // stages per tick. A routine job is only started by the tick, never here.
    void HCFrame(float timeslice)
    {
        if (!m_Started) { return; }
        m_FrameWindow = m_FrameWindow + timeslice;
        if (m_FrameWindow >= 60) { HCFrameSummary(); }
        // The call queue runs the module tick and then this update queue in the same frame.
        if (GetGame().GetTime() == m_TickDispatchMs) { return; }
        if (!HCHasFrameWork()) { return; }
        int started = TickCount(0);
        HCDispatch(GetGame().GetTickTime(), false, HC_FRAME_MS);
        int ticks = TickCount(started);
        if (m_TickStages == 0) { return; }
        m_FrameCount = m_FrameCount + 1;
        if (ticks > m_FrameWorst)
        {
            m_FrameWorst = ticks;
            m_FrameWorstStages = m_TickStages;
            m_FrameWorstJob = m_DispatchedName;
        }
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

// Shared image transaction. Native scripts-1.30.164289/1_Core/proto/EnSystem.c:
// 397 FileExist, 417 OpenFile (WRITE/READ), 425 sequential ReadFile, 443 CloseFile,
// 462 FPrint, 528 DeleteFile, 531 CopyFile. No rename/fsync API is exposed by this snapshot.
// Retained handles transfer at most 4 KiB per read/write stage. The .tmp intent stays until
// primary readback completes; interrupted promotion remains fail-closed.
// CopyFile is atomic to this scheduler: an image up to the 8 MiB raw cap can
// occupy one stage. SaveStageTargetMs is checked BETWEEN stages and cannot
// preempt that copy; the largest current staged store is search refresh (8 MiB).
class HCStagedSaveImage
{
    // Build 113 boot: every 64 KiB chunk landed as exactly 8191 bytes (holdouts.json.tmp
    // 16382 = 2 x 8191; routes/snapshot .tmp 8191), so native string/FPrint transfer is
    // capped below 8 KiB per call. Keep each chunk well under that cap.
    static const int HC_CHUNK_BYTES = 4096;
    static const int HC_IMAGE_REPLACE = 0;
    static const int HC_IMAGE_CREATE = 1;
    static const int HC_IMAGE_REMOVE = 2;
    protected int m_Mode;
    // Conservative synchronous finish guard, including optional prior reads:
    // 8 * (HCGroupIO.HC_RAW_READ_CAP 8388608 / HC_CHUNK_BYTES 4096) + 128.
    // Keep a literal: a cross-class static const expression read as 0 natively
    // (build 169 boot: Leads Save exhausted a 6-step guard, lead_store_unavailable).
    static const int HC_MAX_STAGES = 16512;
    protected string m_Path;
    protected string m_Temporary;
    protected string m_Text;
    protected int m_Limit;
    protected int m_Phase = -1;
    protected bool m_Backup;
    protected bool m_CheckPrior;
    protected string m_ExpectedPrior;
    protected bool m_Failed;
    protected FileHandle m_Read;
    protected FileHandle m_Write;
    protected bool m_Opened;
    protected bool m_ReadOpen;
    protected bool m_WriteOpen;
    protected int m_Offset;
    protected int m_OpenStage;
    protected bool m_SourceAbsent;
    protected bool m_TargetExists;
    protected ref array<string> m_PriorChunks = new array<string>;
    protected int m_PriorBytes;
    protected int m_BackupChunk;
    protected int m_BackupStage;
    protected bool m_BackupExists;
    protected bool m_Unchanged = true;
    protected bool m_PriorUnchanged;
    protected bool m_PrimaryKnown;
    protected bool m_PrimaryExists;
    protected bool m_StreamDone;
    protected string m_Piece;
    protected int m_PrimaryOpenStage;
    // Phase 5 reached with nothing modified (the verified primary already holds the candidate):
    // there is no intent file to clear. Never set once this transaction has written an intent.
    protected bool m_NoIntent;
    // True from the moment this transaction opens its intent file for writing. A refreshed
    // candidate that equals the primary must still clear that intent (clear_intent), so the
    // no-intent shortcut is only legal while this stays false.
    protected bool m_IntentWritten;
    // One verified primary per image instance: the path, the exact text this instance wrote or
    // read back and verified into it, and the invalidation epoch of that path when it did.
    // A candidate is skipped only when the path, the epoch and the whole text still match, so a
    // hash collision can never skip a write. Memory is one image per instance (<= the image cap).
    protected string m_VerifiedPath;
    protected string m_VerifiedText;
    protected int m_VerifiedEpoch;
    // Path -> invalidation epoch. Only paths a memo currently covers are tracked (the fixed set of
    // REPLACE stores, capped), so recovery, migration, disposition and REMOVE writers can retire
    // every instance's memo for a path with one call. A path beyond the cap is never memoised.
    static const int HC_MEMO_PATHS = 64;
    protected static ref map<string, int> s_VerifiedEpoch = new map<string, int>;

    // Every writer that changes a covered primary outside HCStagedSaveImage (recovery, migration,
    // quarantine, delete) calls this with the exact path. Cheap: one map lookup, no native call.
    static void HCForget(string path)
    {
        int epoch;
        if (!s_VerifiedEpoch.Find(path, epoch)) { return; }
        if (epoch < 2147483647) { epoch = epoch + 1; }
        else { epoch = 0; }
        s_VerifiedEpoch.Set(path, epoch);
    }

    protected void HCDropVerified()
    {
        m_VerifiedPath = "";
        m_VerifiedText = "";
    }

    protected void HCRemember(string path, string text)
    {
        int epoch;
        if (!s_VerifiedEpoch.Find(path, epoch))
        {
            if (s_VerifiedEpoch.Count() >= HC_MEMO_PATHS)
            {
                HCDropVerified();
                return;
            }
            epoch = 0;
            s_VerifiedEpoch.Set(path, epoch);
        }
        m_VerifiedPath = path;
        m_VerifiedEpoch = epoch;
        m_VerifiedText = text;
    }

    // Length first, then the whole text: no hash, so a collision cannot skip a write and no stage
    // spends time hashing an image. A native string compare ends at the first differing byte.
    protected bool HCRemembered(string path, string text)
    {
        if (m_VerifiedPath != path || m_VerifiedText.Length() != text.Length()) { return false; }
        int epoch;
        if (!s_VerifiedEpoch.Find(path, epoch) || epoch != m_VerifiedEpoch) { return false; }
        return m_VerifiedText == text;
    }

    void ~HCStagedSaveImage() { HCClose(); }

    protected void HCClose()
    {
        if (m_ReadOpen) { CloseFile(m_Read); m_ReadOpen = false; }
        if (m_WriteOpen) { CloseFile(m_Write); m_WriteOpen = false; }
        m_Opened = false;
        m_Offset = 0;
        m_BackupChunk = 0;
        m_OpenStage = 0;
        m_SourceAbsent = false;
        m_TargetExists = false;
        m_StreamDone = false;
        m_Piece = "";
        m_PrimaryOpenStage = 0;
    }

    protected int HCFail()
    {
        // The failing stage may already have made its native call. Drain retained
        // handles on subsequent stages before exposing terminal failure.
        m_Failed = true;
        HCDropVerified();
        if (m_ReadOpen || m_WriteOpen) { return HCSaveJob.STEP_MORE; }
        return HCSaveJob.STEP_FAILED;
    }

    // Latches the failure without stepping; the owner then drains with HCStepImage, one retained
    // handle per stage. For owners whose image never carries a bounded child writer
    // (HCAbort is the same latch plus the first drain step).
    void HCLatchFailed()
    {
        m_Failed = true;
        HCDropVerified();
    }

    // Owners that read, recover or delete their primary outside this writer call this on the
    // instance that wrote it; static HCForget(path) retires every instance's memo for the path.
    void HCForgetVerified() { HCDropVerified(); }

    // Owners whose validation fails mid-image still drain one handle per stage.
    int HCAbort()
    {
        m_Failed = true;
        return HCStepImage();
    }

    // Crash recovery for the primary-wins stores (#336): a hard stop after the primary was
    // promoted and before clear_intent leaves path.tmp byte-identical to path. Returns true only
    // after deleting such a .tmp; every other case returns false and touches nothing, so the
    // caller keeps its existing refusal. Callers run it at open, never while this session has a
    // staged save in flight for the path (copy_primary_delete_target would lose both files).
    // The .bak is never read or touched. Pass the cap as a literal.
    static bool HCClearCompletedIntent(string path, int limit, string store)
    {
        if (limit < 1 || path.Length() < 1 || path.Length() > 200) { return false; }
        string intentPath = path + ".tmp";
        if (!HCRecoveryGate.HCAllowWrite(path)) { return false; }
        if (!FileExist(intentPath) || !FileExist(path)) { return false; }
        if (!HCSameImage(intentPath, path, limit)) { return false; }
        if (!DeleteFile(intentPath) || FileExist(intentPath)) { return false; }
        int start = 0;
        int cut = path.IndexOf("/");
        while (cut >= 0)
        {
            start = cut + 1;
            cut = path.IndexOfFrom(start, "/");
        }
        cut = path.IndexOfFrom(start, ":");
        if (cut >= 0) { start = cut + 1; }
        string fileName = path.Substring(start, path.Length() - start);
        Print("[HC Store] crash_recovery file=" + fileName + " store=" + store + " action=cleared_completed_intent reason=tmp_matches_primary");
        return true;
    }

    // Two read-only handles walked in lockstep, 4096 bytes per read (the staged writer's chunk,
    // kept a literal inside this static method). Each read must return count == string length (a
    // NUL-truncated tail fails), the files must have equal chunks and reach EOF (count 0) on the
    // same read, within the cap and non-empty. The guard bounds the loop. Handles close on every path.
    protected static bool HCSameImage(string first, string second, int limit)
    {
        FileHandle left = OpenFile(first, FileMode.READ);
        if (!left) { return false; }
        FileHandle right = OpenFile(second, FileMode.READ);
        if (!right) { CloseFile(left); return false; }
        bool same = true;
        bool ended = false;
        int total = 0;
        int guard = limit / 4096 + 2;
        while (same && !ended && guard > 0)
        {
            guard--;
            string leftPiece;
            string rightPiece;
            int leftCount = ReadFile(left, leftPiece, 4096);
            int rightCount = ReadFile(right, rightPiece, 4096);
            if (leftCount < 0 || rightCount < 0 || leftCount != leftPiece.Length() || rightCount != rightPiece.Length() || leftCount != rightCount)
            {
                same = false;
            }
            else if (leftCount == 0)
            {
                ended = true;
            }
            else
            {
                total += leftCount;
                if (total > limit || leftPiece != rightPiece) { same = false; }
            }
        }
        CloseFile(left);
        CloseFile(right);
        return same && ended && total > 0;
    }

    bool Active() { return m_Phase >= 0; }
    bool Begin(string path, string text, int limit, bool backup = true, bool checkPrior = true, string expectedPrior = "", int mode = 0, string temporaryPath = "")
    {
        if (mode < HC_IMAGE_REPLACE || mode > HC_IMAGE_REMOVE || m_Failed || Active() || limit < 1 || text.Length() < 1 || text.Length() > limit || limit > HCGroupIO.HC_RAW_READ_CAP)
        {
            Print("[HC SaveImage] state=refused reason=active_or_size runtime=PENDING");
            return false;
        }
        string temporary = temporaryPath;
        if (temporary == "") { temporary = path + ".tmp"; }
        if (!HCRecoveryGate.HCAllowWrite(path))
        {
            Print("[HC SaveImage] state=refused reason=gate_or_intent runtime=PENDING");
            return false;
        }
        // This instance already wrote or read back exactly these bytes into the primary and
        // cleared its own intent: nothing to write, read or compare. Begin's one primary probe
        // proves the primary is still on disk; an absent primary (deleted or recovered file) drops
        // the skip and runs the full transaction. An intent that appeared since could only come
        // from outside; the next changed image checks for it.
        bool verified = mode == HC_IMAGE_REPLACE && HCRemembered(path, text);
        bool primaryPresent = false;
        if (mode != HC_IMAGE_REMOVE && (verified || mode == HC_IMAGE_CREATE)) { primaryPresent = FileExist(path); }
        if (verified && !primaryPresent) { verified = false; }
        // A removal retires every instance's memo for that exact path.
        if (mode == HC_IMAGE_REMOVE) { HCForget(path); }
        // Refuse without latching failure/active state, so owners can recover
        // stale intents or immutable targets before retrying Begin.
        if (!verified && mode != HC_IMAGE_REMOVE && (FileExist(temporary) || (mode == HC_IMAGE_CREATE && primaryPresent)))
        {
            Print("[HC SaveImage] state=refused reason=gate_or_intent runtime=PENDING");
            return false;
        }
        m_PriorChunks.Clear();
        m_PriorBytes = 0;
        m_BackupStage = 0;
        m_BackupExists = false;
        m_Unchanged = true;
        m_PriorUnchanged = false;
        m_PrimaryKnown = false;
        m_PrimaryExists = false;
        m_Temporary = temporary;
        m_Mode = mode;
        m_Path = path;
        m_Text = text;
        m_Limit = limit;
        m_Backup = backup;
        // Backup rotation needs a readable prior image even when the caller
        // skips expected-prior comparison (e.g. HCXAISites and HCHints). Refuse
        // unreadable existing primaries rather than rotate unverified bytes.
        m_CheckPrior = checkPrior || backup;
        m_ExpectedPrior = expectedPrior;
        m_Phase = 0;
        m_NoIntent = false;
        m_IntentWritten = false;
        if (mode != HC_IMAGE_REPLACE) { m_CheckPrior = false; m_Backup = false; }
        if (mode == HC_IMAGE_REMOVE) { m_Phase = 5; }
        if (verified)
        {
            m_CheckPrior = false;
            m_NoIntent = true;
            m_Phase = 5;
        }
        else if (mode == HC_IMAGE_REPLACE)
        {
            // The primary may change from here on; it is trusted again only after verification.
            HCDropVerified();
        }
        return true;
    }

    // Immutable journals retain their original intent/image/commit filenames.
    bool BeginNew(string path, string text, int limit)
    {
        return Begin(path, text, limit, false, false, "", HC_IMAGE_CREATE);
    }

    // Only owners nominate exact, obsolete journal filenames after new commit.
    bool BeginRemove(string path)
    {
        return Begin(path, ".", 1, false, false, "", HC_IMAGE_REMOVE);
    }

    // Optional prior verification leaves original files untouched. Every chunk
    // in phases 0..4 retains .tmp: partial temp/backup/primary is never admitted.
    // 0 write_tmp, 1 read_tmp, 2 copy_backup, 3 copy_primary, 4 read_primary,
    // 5 clear_intent. Old primary is retained until temp verification succeeds.
    int HCStepImage()
    {
        if (m_Failed)
        {
            if (m_ReadOpen)
            {
                HCSaveJob.HCOperation = "failed_close_read";
                CloseFile(m_Read);
                m_ReadOpen = false;
                return HCSaveJob.STEP_MORE;
            }
            if (m_WriteOpen)
            {
                HCSaveJob.HCOperation = "failed_close_write";
                CloseFile(m_Write);
                m_WriteOpen = false;
                return HCSaveJob.STEP_MORE;
            }
            return HCSaveJob.STEP_FAILED;
        }
        if (!Active() || !HCRecoveryGate.HCAllowWrite(m_Path)) { return HCFail(); }
        if (m_Mode == HC_IMAGE_CREATE && m_Phase == 2)
        {
            m_Phase = -1;
            m_Text = "";
            return HCSaveJob.STEP_DONE;
        }
        string source;
        string target;
        string expected;
        bool compare = false;
        if (m_CheckPrior)
        {
            HCSaveJob.HCOperation = "read_prior";
            source = m_Path;
            expected = m_ExpectedPrior;
            compare = expected != "";
        }
        else if (m_Phase == 0)
        {
            HCSaveJob.HCOperation = "write_tmp";
            target = m_Temporary;
            if (m_Mode == HC_IMAGE_CREATE) { target = m_Path; }
        }
        else if (m_Phase == 1) { HCSaveJob.HCOperation = "read_tmp"; source = m_Temporary; expected = m_Text; compare = true; }
        else if (m_Phase == 2)
        {
            if (m_PriorUnchanged)
            {
                // Primary already holds the verified candidate. Never touch it:
                // whenever primary is touched, .bak equals the verified prior.
                // Still visit phase 5 so owners may refresh a newer snapshot.
                m_PriorChunks.Clear();
                m_PriorBytes = 0;
                m_Phase = 5;
                Print("[HC SaveImage] state=unchanged reason=verified_primary_retained runtime=PENDING");
                return HCSaveJob.STEP_MORE;
            }
            // A verified prior read already established primary presence. Only
            // owners that deliberately skipped that read need a presence probe.
            if (!m_PrimaryKnown)
            {
                HCSaveJob.HCOperation = "copy_backup_check_source";
                m_PrimaryExists = FileExist(m_Path);
                m_PrimaryKnown = true;
                return HCSaveJob.STEP_MORE;
            }
            if (m_Backup && m_PrimaryExists)
            {
                string backup = m_Path + ".bak";
                if (m_BackupStage == 0)
                {
                    HCSaveJob.HCOperation = "copy_backup_check_target";
                    m_BackupExists = FileExist(backup);
                    m_BackupStage = 1;
                    return HCSaveJob.STEP_MORE;
                }
                // An identical primary may keep an existing backup, but must
                // create one when absent. Retain primary and verified temp
                // throughout backup rotation: neither is deleted on failure.
                if ((!m_PriorUnchanged || !m_BackupExists) && m_BackupStage < 3)
                {
                    if (m_BackupStage == 1)
                    {
                        m_BackupStage = 2;
                        if (m_BackupExists)
                        {
                            HCSaveJob.HCOperation = "copy_backup_delete_target";
                            if (!DeleteFile(backup)) { return HCFail(); }
                            return HCSaveJob.STEP_MORE;
                        }
                    }
                    HCSaveJob.HCOperation = "copy_backup";
                    if (!CopyFile(m_Path, backup)) { return HCFail(); }
                    m_BackupStage = 3;
                    return HCSaveJob.STEP_MORE;
                }
            }
            if (m_BackupStage == 3)
            {
                // Verify the copied prior image before deleting the primary.
                // Reuse the bounded open/read/close stages below.
                HCSaveJob.HCOperation = "read_backup";
                source = m_Path + ".bak";
                // Compare backup chunks to the observed prior, without a growing
                // concatenated string (linear storage even for large images).
                compare = true;
            }
            else
            {
                m_PriorChunks.Clear();
                m_PriorBytes = 0;
                m_Phase = 3;
                return HCSaveJob.STEP_MORE;
            }
        }
        else if (m_Phase == 3)
        {
            // CopyFile replaces the old streamed read/write pair. Native copies
            // cannot be preempted; attribute each as its own tick stage. Retain
            // the verified .tmp and backup through promotion and readback.
            if (m_PrimaryOpenStage == 0)
            {
                m_PrimaryOpenStage = 1;
                if (m_PrimaryExists)
                {
                    HCSaveJob.HCOperation = "copy_primary_delete_target";
                    if (!DeleteFile(m_Path)) { return HCFail(); }
                    return HCSaveJob.STEP_MORE;
                }
            }
            HCSaveJob.HCOperation = "copy_primary";
            if (!CopyFile(m_Temporary, m_Path)) { return HCFail(); }
            m_PrimaryExists = true;
            HCClose();
            m_Phase = 4;
            return HCSaveJob.STEP_MORE;
        }
        else if (m_Phase == 4) { HCSaveJob.HCOperation = "read_primary"; source = m_Path; expected = m_Text; compare = true; }
        else if (m_NoIntent)
        {
            // Nothing was written, so there is no intent to clear and no native call to make.
            HCSaveJob.HCOperation = "unchanged_done";
            HCRemember(m_Path, m_Text);
            HCClose();
            m_NoIntent = false;
            m_Phase = -1;
            m_Text = "";
            m_ExpectedPrior = "";
            return HCSaveJob.STEP_DONE;
        }
        else
        {
            HCSaveJob.HCOperation = "clear_intent";
            string intent = m_Temporary;
            if (m_Mode == HC_IMAGE_REMOVE) { intent = m_Path; }
            if (m_Mode == HC_IMAGE_REMOVE && m_OpenStage == 0)
            {
                HCSaveJob.HCOperation = "clear_intent_check_target";
                m_TargetExists = FileExist(intent);
                m_OpenStage = 1;
                return HCSaveJob.STEP_MORE;
            }
            bool removed = true;
            if (m_Mode != HC_IMAGE_REMOVE || m_TargetExists) { removed = DeleteFile(intent); }
            if (!removed) { return HCFail(); }
            // Primary and backup are verified and the intent is gone: the primary is now known.
            if (m_Mode == HC_IMAGE_REPLACE) { HCRemember(m_Path, m_Text); }
            HCClose();
            m_Phase = -1;
            m_Text = "";
            m_ExpectedPrior = "";
            return HCSaveJob.STEP_DONE;
        }
        if (m_Mode == HC_IMAGE_CREATE && m_Phase == 1) { source = m_Path; }
        // Open/read/write/close each yield after ONE native file call; native
        // filesystem stalls cannot be preempted, only attributed.
        string operation = HCSaveJob.HCOperation;
        if (!m_Opened)
        {
            if (m_OpenStage == 0)
            {
                m_OpenStage = 1;
                if ((m_CheckPrior || m_Phase == 2) && source != "")
                {
                    HCSaveJob.HCOperation = operation + "_check_source";
                    m_SourceAbsent = !FileExist(source);
                    if (m_CheckPrior)
                    {
                        m_PrimaryKnown = true;
                        m_PrimaryExists = !m_SourceAbsent;
                    }
                    // Absent prior is legitimate only for an originally fresh store.
                    if (m_SourceAbsent && (m_Phase == 2 || (m_CheckPrior && compare))) { return HCFail(); }
                    return HCSaveJob.STEP_MORE;
                }
            }
            if (m_SourceAbsent) { source = ""; target = ""; }
            if (m_OpenStage == 1) { m_OpenStage = 3; }
            if (m_OpenStage == 3)
            {
                m_OpenStage = 4;
                if (source != "")
                {
                    HCSaveJob.HCOperation = operation + "_open_read";
                    m_Read = OpenFile(source, FileMode.READ);
                    if (!m_Read) { return HCFail(); }
                    m_ReadOpen = true;
                    return HCSaveJob.STEP_MORE;
                }
            }
            if (m_OpenStage == 4)
            {
                m_OpenStage = 5;
                if (target != "")
                {
                    HCSaveJob.HCOperation = operation + "_open_write";
                    // From here an intent may exist on disk: the no-intent shortcut is off.
                    if (target == m_Temporary) { m_IntentWritten = true; }
                    m_Write = OpenFile(target, FileMode.WRITE);
                    if (!m_Write) { return HCFail(); }
                    m_WriteOpen = true;
                    return HCSaveJob.STEP_MORE;
                }
            }
            m_Opened = true;
        }
        if (m_Piece != "")
        {
            HCSaveJob.HCOperation = operation + "_write";
            FPrint(m_Write, m_Piece);
            m_Piece = "";
            return HCSaveJob.STEP_MORE;
        }
        string piece;
        if (!m_StreamDone && m_ReadOpen)
        {
            HCSaveJob.HCOperation = operation + "_read";
            int count = ReadFile(m_Read, piece, HC_CHUNK_BYTES);
            if (count < 0 || count != piece.Length() || m_Offset + count > m_Limit) { return HCFail(); }
            if (m_CheckPrior && count > 0)
            {
                if (m_Backup) { m_PriorChunks.Insert(piece); m_PriorBytes += count; }
                if (m_Offset + count > m_Text.Length()) { m_Unchanged = false; }
                else if (piece != m_Text.Substring(m_Offset, count)) { m_Unchanged = false; }
            }
            if (compare)
            {
                if (m_Phase == 2 && !m_CheckPrior)
                {
                    int chunk = m_BackupChunk;
                    if (m_Offset + count > m_PriorBytes || (count == 0 && m_Offset != m_PriorBytes)) { return HCFail(); }
                    if (count > 0)
                    {
                        if (chunk >= m_PriorChunks.Count() || piece != m_PriorChunks[chunk]) { return HCFail(); }
                        m_BackupChunk++;
                    }
                }
                else
                {
                    if (m_Offset + count > expected.Length()) { return HCFail(); }
                    if (count > 0)
                    {
                        string want = expected.Substring(m_Offset, count);
                        if (want.Length() != count || piece != want) { return HCFail(); }
                    }
                }
            }
            if (count == 0)
            {
                if (m_Offset < 1 || (compare && m_Phase != 2 && m_Offset != expected.Length())) { return HCFail(); }
                m_StreamDone = true;
            }
            if (m_WriteOpen) { m_Piece = piece; }
            m_Offset = m_Offset + count;
            return HCSaveJob.STEP_MORE;
        }
        if (!m_StreamDone && m_WriteOpen)
        {
            int remaining = m_Text.Length() - m_Offset;
            int length = Math.Min(remaining, HC_CHUNK_BYTES);
            piece = m_Text.Substring(m_Offset, length);
            if (piece.Length() != length) { return HCFail(); }
            HCSaveJob.HCOperation = operation + "_write";
            FPrint(m_Write, piece);
            m_Offset = m_Offset + length;
            m_StreamDone = length == remaining;
            return HCSaveJob.STEP_MORE;
        }
        if (m_ReadOpen)
        {
            HCSaveJob.HCOperation = operation + "_close_read";
            CloseFile(m_Read);
            m_ReadOpen = false;
            return HCSaveJob.STEP_MORE;
        }
        if (m_WriteOpen)
        {
            HCSaveJob.HCOperation = operation + "_close_write";
            CloseFile(m_Write);
            m_WriteOpen = false;
            return HCSaveJob.STEP_MORE;
        }
        HCSaveJob.HCOperation = operation + "_done";
        // Avoid rotating the backup for an identical image, but still reach
        // the normal phase-5 boundary: owners refresh newer revisions there.
        if (m_CheckPrior)
        {
            m_PriorUnchanged = m_PrimaryExists && m_Unchanged && m_Offset == m_Text.Length();
        }
        if (m_Phase == 2 && !m_CheckPrior) { m_PriorChunks.Clear(); m_PriorBytes = 0; }
        HCClose();
        if (m_CheckPrior)
        {
            m_CheckPrior = false;
            if (m_PriorUnchanged && m_Mode == HC_IMAGE_REPLACE && !m_IntentWritten)
            {
                // The verified primary already holds the candidate: skip the tmp write and
                // readback, the backup rotation and the intent. Nothing has been modified, so
                // a crash here leaves exactly the verified primary and backup. Phase 5 stays
                // reachable so owners may still refresh a newer snapshot.
                m_PriorChunks.Clear();
                m_PriorBytes = 0;
                m_NoIntent = true;
                m_Phase = 5;
                Print("[HC SaveImage] state=unchanged reason=verified_primary_retained runtime=PENDING");
            }
        }
        else { m_Phase++; }
        return HCSaveJob.STEP_MORE;
    }

    bool HCReadyToClearIntent() { return m_Phase == 5; }

    bool HCRefreshIntent(string text)
    {
        if (m_Phase != 5 || m_Failed || text.Length() < 1 || text.Length() > m_Limit) { return false; }
        // The just-verified primary is the refreshed transaction's predecessor.
        // Recheck/rotate it before touching primary again; a previously identical
        // image must not suppress promotion of this newer candidate.
        m_ExpectedPrior = m_Text;
        m_Text = text;
        m_NoIntent = false;
        HCDropVerified();
        m_Phase = 0;
        m_Backup = true;
        m_PriorUnchanged = false;
        m_Unchanged = true;
        m_BackupStage = 0;
        m_PriorChunks.Clear();
        m_PriorBytes = 0;
        m_CheckPrior = true;
        return true;
    }

    bool Finish()
    {
        // Even a faulted in-flight image must drain its handles through stages.
        int result = HCSaveJob.STEP_MORE;
        int stages;
        while (Active() && result == HCSaveJob.STEP_MORE && stages < HC_MAX_STAGES)
        {
            result = HCStepImage();
            stages++;
        }
        if (Active() && result == HCSaveJob.STEP_MORE && stages >= HC_MAX_STAGES)
        {
            Print("[HC Persistence] owner=HCStagedSaveImage guard=finish_stage_guard steps=" + stages.ToString());
            HCFail();
            // A synchronous refusal still releases retained handles, preserving the image/intent.
            HCClose();
            return false;
        }
        return !m_Failed && !Active() && result != HCSaveJob.STEP_FAILED;
    }
}
