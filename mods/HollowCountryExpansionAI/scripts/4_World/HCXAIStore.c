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
    // Last refusal code, printed once with the phase that raised it.
    protected string m_Reason;

    // A retired or abandoned boot read must not leak its handle.
    void ~HCXAIJournalBoot()
    {
        if (m_Opened) { CloseFile(m_Handle); m_Opened = false; }
    }

    bool Done() { return m_Phase == PHASE_DONE; }
    int Ops() { return m_Ops; }
    HCXAIJournalData Journal() { return m_Journal; }

    protected void HCFail(string reason)
    {
        if (!m_Failed) { Print("[HC Expansion AI] lease journal boot refused reason=" + reason + " phase=" + m_Phase.ToString() + " file_ops=" + m_Ops.ToString() + " runtime=PENDING"); }
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

    // Parses a bounded journal image. Null on a malformed or oversize image, with the
    // reason in m_Reason. A sealed image (HCXAIStore.HCSeal) ends in a length line and
    // is complete only when that length equals the JSON body length; images written
    // before the seal existed have no such line and are read as before (upgrade path).
    protected HCXAIJournalData HCParse(string data)
    {
        m_Reason = "";
        if (data.Length() < 1 || data.Length() > MAX_BYTES) { m_Reason = "size_out_of_bounds"; return null; }
        string body = data;
        int mark = data.LastIndexOf(HCXAIStore.SEAL_MARK);
        // A cut inside the length line leaves a stray "\n#" with no whole mark.
        if (mark < 0 && data.LastIndexOf("\n#") >= 0) { m_Reason = "seal_truncated"; return null; }
        if (mark >= 0)
        {
            string tail = data.Substring(mark + HCXAIStore.SEAL_MARK.Length(), data.Length() - mark - HCXAIStore.SEAL_MARK.Length());
            if (tail != mark.ToString() + "\n") { m_Reason = "seal_length_mismatch"; return null; }
            body = data.Substring(0, mark);
        }
        string error;
        HCXAIJournalData journal;
        if (!JsonFileLoader<HCXAIJournalData>.LoadData(body, journal, error) || !journal) { m_Reason = "json_unparseable"; return null; }
        return journal;
    }

    // After close: decide the next stage from the bytes just read. No file operation.
    protected void HCRoute()
    {
        if (m_Failed) { m_Phase = PHASE_DONE; return; }
        if (m_Verify)
        {
            if (m_Data != m_Recovered) { this.HCFail("promoted_primary_mismatch"); return; }
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
            // Without a primary this is the very first image of the file, torn before
            // it was ever verified: nothing was committed, so the journal starts empty.
            m_ReadingPending = false;
            string partialReason = m_Reason;
            if (m_HavePrimary)
            {
                Print("[HC Expansion AI] lease journal pending discarded reason=pending_partial_primary_kept detail=" + partialReason + " runtime=PENDING");
                m_Source = HCXAIStore.HCJournalPath();
                m_Phase = PHASE_OPEN;
                return;
            }
            Print("[HC Expansion AI] lease journal pending discarded reason=pending_partial_no_primary detail=" + partialReason + " action=start_empty runtime=PENDING");
            m_Journal = new HCXAIJournalData();
            m_Phase = PHASE_DELETE_PENDING;
            return;
        }
        if (!parsed) { this.HCFail("primary_" + m_Reason); return; }
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
            if (!m_Handle) { this.HCFail("open_failed"); return this.HCStepResult(); }
            m_Opened = true;
            m_Data = "";
            m_Phase = PHASE_READ;
        }
        else if (m_Phase == PHASE_READ)
        {
            string piece;
            int count = ReadFile(m_Handle, piece, READ_BYTES);
            if (count < 0 || count != piece.Length() || m_Data.Length() + count > MAX_BYTES) { this.HCFail("read_failed_or_oversize"); return this.HCStepResult(); }
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
            if (!DeleteFile(path)) { this.HCFail("delete_primary_failed"); return this.HCStepResult(); }
            m_Phase = PHASE_COPY;
        }
        else if (m_Phase == PHASE_COPY)
        {
            if (!CopyFile(pending, path)) { this.HCFail("promote_copy_failed"); return this.HCStepResult(); }
            // Re-read the promoted primary and compare it with the recovered bytes.
            m_Verify = true;
            m_Source = path;
            m_Phase = PHASE_OPEN;
        }
        else if (m_Phase == PHASE_DELETE_PENDING)
        {
            if (!DeleteFile(pending)) { this.HCFail("delete_pending_failed"); return this.HCStepResult(); }
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
    // Completeness line appended to every journal image this build writes.
    static const string SEAL_MARK = "\n#hc-end ";
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
        if (!s_Boot.Done() && !HCStartupPump.HCInSlice() && HCServer.HCTickWork().HCTakeAISlice(HCUnitBudget.HC_AI_CARAVAN, HCUnitBudget.HC_WORK_ROADS, 1)) { s_Boot.HCStepBoot(); }
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
    // The text carries a length line (HCSeal) so a reader can tell a whole image
    // from a torn one without relying on the JSON merely parsing.
    static string HCSeal(string text)
    {
        return text + SEAL_MARK + text.Length().ToString() + "\n";
    }
    static bool SaveJournal(HCXAIJournalData journal)
    {
        if (!GetGame() || !GetGame().IsServer() || !journal || !journal.Rows || journal.Rows.Count() > 64) { return false; }
        if (s_JournalUncertain || !s_Save || !HCXAIStore.HCJournalSettled()) { return false; }
        string text;
        string error;
        if (!JsonFileLoader<HCXAIJournalData>.MakeData(journal, text, error)) { return false; }
        string image = HCXAIStore.HCSeal(text);
        if (image.Length() > HCXAIJournalBoot.MAX_BYTES) { return false; }
        if (!s_Save.HCQueue(image)) { return false; }
        s_BootJournal = journal;
        return true;
    }
    // A new lease intent consumes its id: a tombstone lost to a crash would let the
    // same id be issued again and rebind its receipt tokens. Intent creation is
    // therefore a durability barrier (rare, one bounded image); other mutations stay
    // write-behind.
    static bool SaveJournalDurable(HCXAIJournalData journal)
    {
        if (!HCXAIStore.SaveJournal(journal)) { return false; }
        if (HCSaveScheduler.HCFlush(s_Save)) { return true; }
        HCXAIStore.HCJournalFault("intent_flush_failed");
        return false;
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
