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
    bool HCFaulted;
    int HCPeakTicks;   // slowest stage logged so far; the [HC Save] line prints only on a new peak
    string HCName() { return "job"; }
    // Snapshot owners may have newer requests after a committed image.
    bool HCPendingCheckpoint() { return false; }
    int HCStep() { return STEP_FAILED; }
}

// Bound: <=32 registered stores examined (operator may lower), SaveStagesPerTick
// stages under the cooperative SaveStageTargetMs deadline. Only ONE job advances per tick;
// staged jobs retain ownership across ticks, never interleaved with another job.
// Existing verified intent/backup/copy writers remain authoritative. Native
// copy/JSON calls have no cancellation API; the time target is cooperative.
// Per-job new-peak save timing is logged as '[HC Save] job=.. stages=.. max_stage_ticks=.. total_ticks=..
// slowest_stage=.. op=.. runtime=PENDING' in raw EnSystem.c:106 TickCount units (divide by ticks_per_ms of the [HC Perf] line);
// slowest_stage is the 1-based stage that took max_stage_ticks (issue #138 round 2).
// scheduler_ticks counts this checkpoint's dispatches; max_stages_per_tick records
// actual throughput. Peak-only logging is unchanged; counters reset per checkpoint.
class HCSaveScheduler : HCModule
{
    protected static ref array<ref HCSaveJob> s_Jobs = new array<ref HCSaveJob>;
    protected static string s_RegistrationFault;
    protected int m_Next;
    protected ref HCWorkBudget m_Budget = new HCWorkBudget;
    protected ref HCSaveStageBudget m_StageBudget = new HCSaveStageBudget;
    protected int m_TickStages;
    protected int m_JobTicks;
    protected int m_MaxStagesPerTick;
    protected HCSaveJob m_Active;
    protected int m_Stages;
    protected int m_StageMax;
    protected int m_StageMaxIndex;
    protected string m_StageMaxOperation;
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
        Print("[HC PerfControl] WorldSaves stages_per_tick_cap=" + HCWorldRuntimeConfig.HCGet().SaveStagesPerTick.ToString() + " target_ms=" + HCPerfConfig.HCGet().SaveStageTargetMs.ToString() + " scope=tick_stages cooperative_only=1 runtime=PENDING");
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
        // 8 MiB / 4096 = 2048 chunks; two guards derived from the raw cap, plus 64 owner stages.
        int flushLimit = config.SaveFlushStageLimit;
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
        m_Stages = m_Stages + 1;
        m_TotalTicks = m_TotalTicks + ticks;
        if (ticks > m_StageMax)
        {
            m_StageMax = ticks;
            m_StageMaxIndex = m_Stages;
            m_StageMaxOperation = HCSaveJob.HCOperation;
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
            if (m_StageMax > job.HCPeakTicks)
            {
                job.HCPeakTicks = m_StageMax;
                string timing = "[HC Save] job=" + job.HCName() + " stages=" + m_Stages.ToString() + " max_stage_ticks=" + m_StageMax.ToString() + " total_ticks=" + m_TotalTicks.ToString();
                timing += " scheduler_ticks=" + m_JobTicks.ToString() + " max_stages_per_tick=" + m_MaxStagesPerTick.ToString();
                timing += " slowest_stage=" + m_StageMaxIndex.ToString() + " op=" + m_StageMaxOperation + " runtime=PENDING";
                Print("" + timing);
            }
        }
        else
        {
            // Faulted writer preserves its intent; no every-tick retry.
            job.HCFaulted = true;
            HCUnregister(job);
            m_Fault = "save_job_write_faulted";
        }
        m_Stages = 0;
        m_StageMax = 0;
        m_StageMaxIndex = 0;
        m_TotalTicks = 0;
        m_JobTicks = 0;
        m_MaxStagesPerTick = 0;
    }

    // Check both limits between stages; one atomic native operation may overrun.
    protected void HCRunStages(HCSaveJob job, float now)
    {
        m_StageBudget.HCReset(HCWorldRuntimeConfig.HCGet().SaveStagesPerTick, HCPerfConfig.HCGet().SaveStageTargetMs);
        m_JobTicks = m_JobTicks + 1;
        while (m_StageBudget.HCContinue())
        {
            m_TickStages = m_TickStages + 1;
            if (m_TickStages > m_MaxStagesPerTick) { m_MaxStagesPerTick = m_TickStages; }
            HCRunStep(job, now);
            HCReached.Mark("world_saves.stage");
            if (!m_Active) { break; }
        }
    }

    override void OnTick(float deltaTime)
    {
        m_TickStages = 0;
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
            m_JobTicks = 0;
            m_MaxStagesPerTick = 0;
        }
        if (m_Active)
        {
            HCRunStages(m_Active, now);
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
            if (job.HCFaulted || !job.HCDirty) { continue; }
            if (!job.HCUrgent && (now < job.HCDue || (job.HCHasCommitted && now < job.HCLastCommitSeconds + job.HCInterval()))) { continue; }
            HCRunStages(job, now);
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
        if (m_ReadOpen || m_WriteOpen) { return HCSaveJob.STEP_MORE; }
        return HCSaveJob.STEP_FAILED;
    }

    // Owners whose validation fails mid-image still drain one handle per stage.
    int HCAbort()
    {
        m_Failed = true;
        return HCStepImage();
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
        // Refuse without latching failure/active state, so owners can recover
        // stale intents or immutable targets before retrying Begin.
        if (mode != HC_IMAGE_REMOVE && (FileExist(temporary) || (mode == HC_IMAGE_CREATE && FileExist(path))))
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
        if (mode != HC_IMAGE_REPLACE) { m_CheckPrior = false; m_Backup = false; }
        if (mode == HC_IMAGE_REMOVE) { m_Phase = 5; }
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
        if (m_CheckPrior) { m_CheckPrior = false; }
        else { m_Phase++; }
        return HCSaveJob.STEP_MORE;
    }

    bool HCReadyToClearIntent() { return m_Phase == 5; }

    bool HCRefreshIntent(string text)
    {
        if (m_Phase != 5 || m_Failed || text.Length() < 1 || text.Length() > m_Limit) { return false; }
        m_Text = text;
        m_Phase = 0;
        m_Backup = false;
        m_BackupStage = 0;
        m_PriorChunks.Clear();
        m_PriorBytes = 0;
        m_CheckPrior = false;
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
