// Native bounded file/serialization adapters; no qualification is inferred here.
//
// The lease journal is write-behind staged persistence. HCXAIJournal still gets a bool
// per mutation, but the bool means "validated and queued" (the encounter binds an
// already-owned patrol and spawns, moves or deletes nothing, and nothing is restored
// after a restart, so no world state is released or created ahead of the image).
// The image itself is HCStagedSaveImage (one native file operation per scheduler
// stage) with the legacy .pending.json file as its intent file. Any failure latches
// s_JournalUncertain: admission stays refused for the process, as before.
// Boot read and recovery are one native operation per HCXAIJournalBoot step, pumped
// by the startup pump with a one-step-per-tick fallback (HCXAIEncounters.Step).
// Native scripts-1.30.164289: EnSystem.c OpenFile/ReadFile/CloseFile/FileExist/
// DeleteFile/CopyFile/MakeDirectory; EnScript.c JsonFileLoader.LoadData/MakeData.

// Boot recovery protocol (every step is a single native file operation):
//   0 mkdir, 1 probe pending, 2 probe primary,
//   3 open, 4 read 4096-byte chunk (repeat to EOF), 5 close + parse/route,
//   6 delete primary, 7 copy pending -> primary (then re-read primary and compare),
//   8 delete pending, 9 done.
// The staged writer keeps the old primary until the intent file is verified, then
// deletes the primary and copies the intent over it. A crash anywhere leaves either a
// valid primary (partial intent: discarded) or a complete intent (primary absent or
// partial: promoted again). A complete intent that parses is always the newest image.
// Only an unreadable pair is refused, as the legacy loader refused.
class HCXAIJournalBoot
{
    static const int PHASE_MKDIR = 0;
    static const int PHASE_PROBE_PENDING = 1;
    static const int PHASE_PROBE_PRIMARY = 2;
    static const int PHASE_OPEN = 3;
    static const int PHASE_READ = 4;
    static const int PHASE_CLOSE = 5;
    static const int PHASE_DELETE_PRIMARY = 6;
    static const int PHASE_COPY = 7;
    static const int PHASE_DELETE_PENDING = 8;
    static const int PHASE_DONE = 9;
    static const int READ_BYTES = 4096;
    static const int MAX_BYTES = 65536;
    protected int m_Phase;
    protected bool m_HavePending;
    protected bool m_HavePrimary;
    protected bool m_ReadingPending;
    protected bool m_Verify;
    protected bool m_Failed;
    protected bool m_Opened;
    protected FileHandle m_Handle;
    protected string m_Source;
    protected string m_Data;
    protected string m_Recovered;
    protected ref HCXAIJournalData m_Journal;
    protected ref HCXAIJournalData m_Recovery;
    protected int m_Ops;

    bool Done() { return m_Phase == PHASE_DONE; }
    int Ops() { return m_Ops; }
    HCXAIJournalData Journal() { return m_Journal; }

    protected void HCFail()
    {
        m_Failed = true;
        m_Journal = null;
        m_Recovery = null;
        if (m_Opened) { m_Phase = PHASE_CLOSE; return; }
        m_Phase = PHASE_DONE;
    }

    protected int HCStepResult()
    {
        if (m_Phase == PHASE_DONE)
        {
            if (m_Failed) { return HCSaveJob.STEP_FAILED; }
            return HCSaveJob.STEP_DONE;
        }
        return HCSaveJob.STEP_MORE;
    }

    // Parses a bounded journal image. Null on a malformed or oversize image.
    protected HCXAIJournalData HCParse(string data)
    {
        if (data.Length() < 1 || data.Length() > MAX_BYTES) { return null; }
        string error;
        HCXAIJournalData journal;
        if (!JsonFileLoader<HCXAIJournalData>.LoadData(data, journal, error)) { return null; }
        return journal;
    }

    // After close: decide the next stage from the bytes just read. No file operation.
    protected void HCRoute()
    {
        if (m_Failed) { m_Phase = PHASE_DONE; return; }
        if (m_Verify)
        {
            if (m_Data != m_Recovered) { this.HCFail(); return; }
            m_Journal = m_Recovery;
            m_Phase = PHASE_DELETE_PENDING;
            return;
        }
        HCXAIJournalData parsed = this.HCParse(m_Data);
        if (m_ReadingPending)
        {
            if (parsed)
            {
                // The complete intent is the newest image: promote it to the primary.
                m_Recovered = m_Data;
                m_Recovery = parsed;
                m_Phase = PHASE_COPY;
                if (m_HavePrimary) { m_Phase = PHASE_DELETE_PRIMARY; }
                return;
            }
            // Partial intent: the protocol keeps the old primary until the intent is
            // verified, so the primary (when present) is the last committed image.
            m_ReadingPending = false;
            if (m_HavePrimary)
            {
                m_Source = HCXAIStore.HCJournalPath();
                m_Phase = PHASE_OPEN;
                return;
            }
            m_Journal = new HCXAIJournalData();
            m_Phase = PHASE_DELETE_PENDING;
            return;
        }
        if (!parsed) { this.HCFail(); return; }
        m_Journal = parsed;
        m_Phase = PHASE_DONE;
        if (m_HavePending) { m_Phase = PHASE_DELETE_PENDING; }
    }

    // Exactly one native file operation (or none, for the parse/route part of close).
    int HCStepBoot()
    {
        if (m_Phase == PHASE_DONE) { return this.HCStepResult(); }
        string path = HCXAIStore.HCJournalPath();
        string pending = HCXAIStore.HCPendingPath();
        m_Ops++;
        if (m_Phase == PHASE_MKDIR)
        {
            MakeDirectory("$profile:HollowCountry");
            m_Phase = PHASE_PROBE_PENDING;
        }
        else if (m_Phase == PHASE_PROBE_PENDING)
        {
            m_HavePending = FileExist(pending);
            m_Phase = PHASE_PROBE_PRIMARY;
        }
        else if (m_Phase == PHASE_PROBE_PRIMARY)
        {
            m_HavePrimary = FileExist(path);
            m_Source = path;
            if (m_HavePending) { m_Source = pending; m_ReadingPending = true; }
            m_Phase = PHASE_OPEN;
            if (!m_HavePending && !m_HavePrimary)
            {
                m_Journal = new HCXAIJournalData();
                m_Phase = PHASE_DONE;
            }
        }
        else if (m_Phase == PHASE_OPEN)
        {
            m_Handle = OpenFile(m_Source, FileMode.READ);
            if (!m_Handle) { this.HCFail(); return this.HCStepResult(); }
            m_Opened = true;
            m_Data = "";
            m_Phase = PHASE_READ;
        }
        else if (m_Phase == PHASE_READ)
        {
            string piece;
            int count = ReadFile(m_Handle, piece, READ_BYTES);
            if (count < 0 || count != piece.Length() || m_Data.Length() + count > MAX_BYTES) { this.HCFail(); return this.HCStepResult(); }
            if (count == 0) { m_Phase = PHASE_CLOSE; }
            else { m_Data = m_Data + piece; }
        }
        else if (m_Phase == PHASE_CLOSE)
        {
            CloseFile(m_Handle);
            m_Opened = false;
            this.HCRoute();
        }
        else if (m_Phase == PHASE_DELETE_PRIMARY)
        {
            if (!DeleteFile(path)) { this.HCFail(); return this.HCStepResult(); }
            m_Phase = PHASE_COPY;
        }
        else if (m_Phase == PHASE_COPY)
        {
            if (!CopyFile(pending, path)) { this.HCFail(); return this.HCStepResult(); }
            // Re-read the promoted primary and compare it with the recovered bytes.
            m_Verify = true;
            m_Source = path;
            m_Phase = PHASE_OPEN;
        }
        else if (m_Phase == PHASE_DELETE_PENDING)
        {
            if (!DeleteFile(pending)) { this.HCFail(); return this.HCStepResult(); }
            m_Phase = PHASE_DONE;
        }
        return this.HCStepResult();
    }
}

// Startup pump owner: catches the boot read up within the frame deadline.
class HCStartupJournal : HCStartupOwner
{
    HCXAIJournalBoot Boot;
    override bool HCNeedsWork() { return Boot && !Boot.Done(); }
    override void HCSlice()
    {
        if (!Boot) { return; }
        int steps = 0;
        while (steps < 8 && !Boot.Done() && HCStartupPump.HCSliceMs(2) > 0)
        {
            Boot.HCStepBoot();
            steps++;
        }
    }
}

// One staged image per queued snapshot. The newest snapshot wins; an image that
// finishes behind a newer revision is followed by another image of the newest text.
class HCXAIJournalSave : HCSaveJob
{
    protected ref HCStagedSaveImage m_Image = new HCStagedSaveImage();
    protected string m_Text;
    protected int m_Revision;
    protected int m_SnapshotRevision;
    override string HCName() { return "HCX-journal"; }
    bool HCQueue(string text)
    {
        if (HCFaulted || text.Length() < 1 || text.Length() > HCXAIJournalBoot.MAX_BYTES) { return false; }
        m_Text = text;
        m_Revision++;
        HCDirty = true;
        HCUrgent = true;
        return true;
    }
    override int HCStep()
    {
        if (!HCDirty) { return STEP_DONE; }
        if (!m_Image.Active())
        {
            m_SnapshotRevision = m_Revision;
            if (!m_Image.Begin(HCXAIStore.HCJournalPath(), m_Text, HCXAIJournalBoot.MAX_BYTES, false, false, "", 0, HCXAIStore.HCPendingPath()))
            {
                HCXAIStore.HCJournalFault("begin_refused");
                return STEP_FAILED;
            }
            return STEP_MORE;
        }
        int result = m_Image.HCStepImage();
        if (result == STEP_FAILED) { HCXAIStore.HCJournalFault("image_failed"); }
        if (result == STEP_DONE && m_SnapshotRevision != m_Revision) { return STEP_MORE; }
        return result;
    }
}

class HCXAIStore
{
    protected static bool s_JournalPrimed;
    protected static bool s_JournalUncertain;
    protected static bool s_JournalLoaded;
    protected static ref HCXAIJournalData s_BootJournal;
    protected static ref HCXAIJournalBoot s_Boot;
    protected static ref HCXAIJournalSave s_Save;
    protected static ref HCStartupJournal s_Startup;

    static string HCJournalPath() { return "$profile:HollowCountry/expansion-ai-leases.json"; }
    static string HCPendingPath() { return "$profile:HollowCountry/expansion-ai-leases.pending.json"; }

    // Called by the site director's Start before encounters can tick. Registers the
    // staged boot read and the save job; it performs no file operation itself. A
    // failed boot read stays refused; encounter maintenance never retries a disk read.
    static void HCPrimeJournal()
    {
        if (s_JournalPrimed) { return; }
        s_JournalPrimed = true;
        s_Boot = new HCXAIJournalBoot();
        s_Save = new HCXAIJournalSave();
        HCSaveScheduler.HCRegister(s_Save);
        s_Startup = new HCStartupJournal();
        s_Startup.Boot = s_Boot;
        HCStartupPump.HCRegister(s_Startup, "xai_journal", 0);
    }

    // One boot step per call when the startup pump is not draining it, plus the
    // scheduler fallback for the save job. Called from HCXAIEncounters.Step each visit.
    static void HCStepJournal()
    {
        if (!s_Boot) { return; }
        if (!s_Boot.Done() && !HCStartupPump.HCInSlice()) { s_Boot.HCStepBoot(); }
        if (s_Save) { HCSaveScheduler.HCPumpFallback(s_Save); }
    }

    // True once there is no boot read still in flight (or none was ever started).
    static bool HCJournalSettled()
    {
        if (!s_Boot) { return true; }
        if (!s_Boot.Done()) { return false; }
        if (!s_JournalLoaded) { HCXAIStore.HCBootFinished(); }
        return true;
    }


    protected static void HCBootFinished()
    {
        s_JournalLoaded = true;
        s_BootJournal = s_Boot.Journal();
        if (!s_BootJournal)
        {
            s_JournalUncertain = true;
            Print("[HC Expansion AI] lease journal unreadable; admission refused (no AI restoration) runtime=PENDING");
            return;
        }
        Print("[HC Expansion AI] lease journal loaded rows=" + s_BootJournal.Rows.Count().ToString() + " file_ops=" + s_Boot.Ops().ToString());
    }

    static void HCJournalFault(string reason)
    {
        if (!s_JournalUncertain) { Print("[HC Expansion AI] lease journal save failed reason=" + reason + "; admission refused until restart runtime=PENDING"); }
        s_JournalUncertain = true;
    }

    // Orderly stop: drain the queued image synchronously (OnStop-only caller).
    static void HCFlushJournal()
    {
        if (s_Save && !s_JournalUncertain) { HCSaveScheduler.HCFlush(s_Save); }
    }

    static string NativeBuild()
    {
        string version;
        GetGame().GetVersion(version);
        return HCBuildIdentity.Normalize(version);
    }
    static HCXAIJournalData LoadJournal()
    {
        if (s_JournalUncertain || !HCXAIStore.HCJournalSettled()) { return null; }
        return s_BootJournal;
    }
    // Begin/Prune/End consume this bool as acceptance of the mutation. The journal
    // text is validated and bounded here, then staged by HCXAIJournalSave; failure of
    // a later stage latches s_JournalUncertain so every following mutation is refused.
    static bool SaveJournal(HCXAIJournalData journal)
    {
        if (!GetGame() || !GetGame().IsServer() || !journal || !journal.Rows || journal.Rows.Count() > 64) { return false; }
        if (s_JournalUncertain || !s_Save || !HCXAIStore.HCJournalSettled()) { return false; }
        string text;
        string error;
        if (!JsonFileLoader<HCXAIJournalData>.MakeData(journal, text, error) || text.Length() > HCXAIJournalBoot.MAX_BYTES) { return false; }
        if (!s_Save.HCQueue(text)) { return false; }
        s_BootJournal = journal;
        return true;
    }
}

// The encounter arm latch is one-shot (HCXAIEncounters.Step): it must not run before
// the journal boot read settles, and it drives the boot/save fallbacks on the tick.
modded class HCXAIEncounters
{
    override void Step()
    {
        HCXAIStore.HCStepJournal();
        if (!HCXAIStore.HCJournalSettled()) { return; }
        super.Step();
    }

    override void Close()
    {
        super.Close();
        HCXAIStore.HCFlushJournal();
    }
}
