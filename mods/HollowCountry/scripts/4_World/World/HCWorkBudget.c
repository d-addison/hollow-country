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
    static string HCOperation; // operation executed by the current scheduler stage
    bool HCDirty;
    float HCDue;
    bool HCInFlight;
    bool HCUrgent; // durable continuation, including when routine scheduling is off
    bool HCFaulted;
    int HCPeakTicks;   // slowest stage logged so far; the [HC Save] line prints only on a new peak
    string HCName() { return "job"; }
    // Snapshot owners may have newer requests after a committed image.
    bool HCPendingCheckpoint() { return false; }
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
// slowest_stage=.. op=.. runtime=PENDING' in raw EnSystem.c:106 TickCount units (divide by ticks_per_ms of the [HC Perf] line);
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
    // that never reports completion is abandoned at SaveFlushStageLimit (default/ceiling 4096: a staged
    // image flush may finish an older snapshot before writing the current one).
    static bool HCFlush(HCSaveJob job)
    {
        if (!job || (!job.HCDirty && !job.HCInFlight)) { return true; }
        if (job.HCFaulted) { return false; }
        int result = HCSaveJob.STEP_MORE;
        int guard = 0;
        HCWorldRuntimeConfig config = HCWorldRuntimeConfig.HCGet();
        while ((result == HCSaveJob.STEP_MORE || (result == HCSaveJob.STEP_DONE && job.HCPendingCheckpoint())) && guard < config.SaveFlushStageLimit)
        {
            result = job.HCStep();
            guard = guard + 1;
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
        job.HCDue = GetGame().GetTickTime() + config.SaveCoalesceSeconds;
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
        int result = job.HCStep();
        job.HCInFlight = result == HCSaveJob.STEP_MORE;
        if (result == HCSaveJob.STEP_DONE) { job.HCDirty = job.HCPendingCheckpoint(); if (!job.HCDirty) { job.HCUrgent = false; } }
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
            job.HCDirty = job.HCPendingCheckpoint();
            if (!job.HCDirty) { job.HCUrgent = false; }
            job.HCDue = now + config.SaveCoalesceSeconds;
            if (m_StageMax > job.HCPeakTicks)
            {
                job.HCPeakTicks = m_StageMax;
                string timing = "[HC Save] job=" + job.HCName() + " stages=" + m_Stages.ToString() + " max_stage_ticks=" + m_StageMax.ToString() + " total_ticks=" + m_TotalTicks.ToString();
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
            HCReached.Mark("world_saves.stage");
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
            if (job.HCFaulted || !job.HCDirty || now < job.HCDue) { continue; }
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

// Shared image transaction. Native scripts-1.30.164289/1_Core/proto/EnSystem.c:
// 397 FileExist, 417 OpenFile (WRITE/READ), 425 sequential ReadFile, 443 CloseFile,
// 462 FPrint, 528 DeleteFile. No rename/fsync API is exposed by this snapshot.
// Retained handles transfer at most 64 KiB per stage. The .tmp intent stays until
// primary readback completes; interrupted promotion remains fail-closed.
class HCStagedSaveImage
{
    static const int HC_CHUNK_BYTES = 65536;
    static const int HC_IMAGE_REPLACE = 0;
    static const int HC_IMAGE_CREATE = 1;
    static const int HC_IMAGE_REMOVE = 2;
    protected int m_Mode;
    // Six streaming passes at 8 MiB, including EOF stages and metadata.
    static const int HC_MAX_STAGES = 800;
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

    void ~HCStagedSaveImage() { HCClose(); }

    protected void HCClose()
    {
        if (m_ReadOpen) { CloseFile(m_Read); m_ReadOpen = false; }
        if (m_WriteOpen) { CloseFile(m_Write); m_WriteOpen = false; }
        m_Opened = false;
        m_Offset = 0;
    }

    protected int HCFail()
    {
        HCClose();
        m_Failed = true;
        return HCSaveJob.STEP_FAILED;
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
        if (!HCRecoveryGate.HCAllowWrite(path) || (mode == HC_IMAGE_REPLACE && FileExist(temporary)) || (mode == HC_IMAGE_CREATE && FileExist(path)))
        {
            Print("[HC SaveImage] state=refused reason=gate_or_intent runtime=PENDING");
            return false;
        }
        m_Temporary = temporary;
        m_Mode = mode;
        m_Path = path;
        m_Text = text;
        m_Limit = limit;
        m_Backup = backup;
        m_CheckPrior = checkPrior;
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
        if (m_Failed || !Active() || !HCRecoveryGate.HCAllowWrite(m_Path)) { return HCFail(); }
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
            HCSaveJob.HCOperation = "copy_backup";
            if (m_Backup) { source = m_Path; target = m_Path + ".bak"; }
        }
        else if (m_Phase == 3) { HCSaveJob.HCOperation = "copy_primary"; source = m_Temporary; target = m_Path; expected = m_Text; compare = true; }
        else if (m_Phase == 4) { HCSaveJob.HCOperation = "read_primary"; source = m_Path; expected = m_Text; compare = true; }
        else
        {
            HCSaveJob.HCOperation = "clear_intent";
            string intent = m_Temporary;
            if (m_Mode == HC_IMAGE_REMOVE) { intent = m_Path; }
            bool removed = true;
            if (m_Mode != HC_IMAGE_REMOVE || FileExist(intent)) { removed = DeleteFile(intent); }
            if (!removed) { return HCFail(); }
            m_Phase = -1;
            m_Text = "";
            m_ExpectedPrior = "";
            return HCSaveJob.STEP_DONE;
        }
        if (m_Mode == HC_IMAGE_CREATE && m_Phase == 1) { source = m_Path; }
        if (!m_Opened)
        {
            if ((m_CheckPrior || m_Phase == 2) && source != "" && !FileExist(source))
            {
                // Absent prior is legitimate only for an originally fresh store.
                if (m_CheckPrior && compare) { return HCFail(); }
                source = "";
                target = "";
            }
            if (source != "")
            {
                m_Read = OpenFile(source, FileMode.READ);
                m_ReadOpen = false;
                if (m_Read) { m_ReadOpen = true; }
                if (!m_ReadOpen) { return HCFail(); }
            }
            if (target != "")
            {
                if (m_Phase != 0 && FileExist(target) && !DeleteFile(target)) { return HCFail(); }
                m_Write = OpenFile(target, FileMode.WRITE);
                m_WriteOpen = false;
                if (m_Write) { m_WriteOpen = true; }
                if (!m_WriteOpen) { return HCFail(); }
            }
            m_Opened = true;
        }
        bool done = false;
        string piece;
        if (m_ReadOpen)
        {
            int count = ReadFile(m_Read, piece, HC_CHUNK_BYTES);
            if (count < 0 || count != piece.Length() || m_Offset + count > m_Limit) { return HCFail(); }
            if (compare)
            {
                if (m_Offset + count > expected.Length()) { return HCFail(); }
                if (count > 0 && piece != expected.Substring(m_Offset, count)) { return HCFail(); }
            }
            if (count == 0)
            {
                if (m_Offset < 1 || (compare && m_Offset != expected.Length())) { return HCFail(); }
                done = true;
            }
        }
        else if (m_WriteOpen)
        {
            int remaining = m_Text.Length() - m_Offset;
            int length = Math.Min(remaining, HC_CHUNK_BYTES);
            piece = m_Text.Substring(m_Offset, length);
            done = length == remaining;
        }
        else { done = true; }
        if (m_WriteOpen && piece.Length() > 0) { FPrint(m_Write, piece); }
        m_Offset = m_Offset + piece.Length();
        if (!done) { return HCSaveJob.STEP_MORE; }
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
        m_CheckPrior = false;
        return true;
    }

    bool Finish()
    {
        if (m_Failed) { return false; }
        int result = HCSaveJob.STEP_MORE;
        int stages;
        while (Active() && result == HCSaveJob.STEP_MORE && stages < HC_MAX_STAGES)
        {
            result = HCStepImage();
            stages++;
        }
        return !Active() && result != HCSaveJob.STEP_FAILED;
    }
}
