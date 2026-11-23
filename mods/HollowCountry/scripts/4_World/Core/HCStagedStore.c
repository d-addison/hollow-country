// HCStagedStore: one recovery and one torn-copy routine around the shared staged writer
// (HCStagedSaveImage, World/HCWorkBudget.c). Native scripts-1.30.164289 1_Core/proto/EnSystem.c:
// 397 FileExist, 417 OpenFile, 425 ReadFile, 443 CloseFile, 462 FPrint, 528 DeleteFile, 531 CopyFile.
// The engine exposes NO rename and NO fsync, and FPrint returns void: the honest guarantee is "old
// image or new image after a process crash", never after a power cut. A script cannot make a native
// call fail, so copy/delete failures are handled by code review, not by the boot self-test.
//
// Recovery classifies <path>.tmp (the writer's intent), <path> and <path>.bak with the store's codec
// and then runs a fixed plan, ONE native operation per HCStepRecover call. Order is always: make the
// new copy, read it back, then delete the source, so the last codec-valid copy is never deleted.
// A missing .bak is normal. A file that exists but cannot be opened is a failure (read_unavailable),
// never "invalid". Torn copies move to <path>.torn.0..3 (bounded; the oldest slot rotates out only
// after the new copy is verified). Empty files are deleted, not preserved. With the recovery gate
// closed nothing is touched. With no valid copy and freshAllowed=false NOTHING is moved: the
// quarantine is then stable across boots. Not a path for stores above 64 KiB in HCDrainRecover.
//
// The two recovery policies of the existing stores are explicit and are never unified silently:
// roll-forward (a valid .tmp with revision >= the valid primary is promoted) and primary-wins (a valid
// primary is never replaced by a .tmp; the .bak stands in for a missing or damaged primary).
class HCStagedStoreCodec
{
    // Whole, schema-valid image. revision is 0 when the image is unversioned.
    bool HCValid(string text, out int revision)
    {
        revision = 0;
        return text.Length() > 0;
    }
}

class HCStagedStore
{
    static const int HC_ROLL_FORWARD = 0;
    static const int HC_PRIMARY_WINS = 1;
    protected static const int HC_PHASE_IDLE = 0;
    protected static const int HC_PHASE_PROBE = 1;
    protected static const int HC_PHASE_READ = 2;
    protected static const int HC_PHASE_PLAN = 3;
    protected static const int HC_PHASE_EXEC = 4;
    protected static const int HC_PHASE_DONE = 5;
    protected static const int HC_PHASE_FAILED = 6;
    protected static const int HC_OP_DELETE = 1;
    protected static const int HC_OP_COPY = 2;
    protected static const int HC_OP_VERIFY = 3;
    protected static const int HC_OP_PRESERVE = 4;
    protected static const int HC_CHUNK = 4096;

    protected string m_Path;
    protected string m_Tmp;
    protected string m_Bak;
    protected int m_Limit;
    protected int m_Policy;
    protected bool m_Backup;
    protected bool m_Fresh;
    protected bool m_Quiet;
    protected bool m_BackupNoted;
    protected ref HCStagedStoreCodec m_Codec;
    protected ref HCStagedSaveImage m_Image = new HCStagedSaveImage;
    protected int m_Phase;
    protected int m_Idx;
    // Per file (0 tmp, 1 primary, 2 bak): state 0 absent, 1 valid, 2 invalid, 3 present and unread.
    protected ref array<int> m_State = new array<int>;
    protected ref array<int> m_Rev = new array<int>;
    protected ref array<int> m_Bytes = new array<int>;
    protected ref array<int> m_Readable = new array<int>;
    protected ref array<string> m_Text = new array<string>;
    protected ref array<string> m_Why = new array<string>;
    // Plan: parallel arrays, executed one native operation at a time.
    protected ref array<int> m_Code = new array<int>;
    protected ref array<string> m_A = new array<string>;
    protected ref array<string> m_B = new array<string>;
    protected ref array<int> m_N = new array<int>;
    protected int m_Pc;
    protected int m_EmitAt = -1;
    protected int m_RotStart;
    protected int m_RotEnd;
    protected int m_PvStage;
    protected string m_Action = "none";
    protected string m_Reason = "";
    protected string m_FailReason = "";
    protected string m_TornNote = "";
    protected string m_Selected = "";
    protected int m_Revision;
    // Chunked read sub-machine shared by classification and copy verification.
    protected bool m_RdActive;
    protected int m_RdStage;
    protected FileHandle m_RdHandle;
    protected bool m_RdOpen;
    protected string m_RdPath;
    protected string m_RdText;
    protected int m_RdBytes;
    protected bool m_RdOver;
    protected bool m_RdBad;
    protected bool m_RdFault;

    void HCStagedStore(string path, int limit, int policy, HCStagedStoreCodec codec, bool backup, bool freshAllowed = false)
    {
        m_Path = path;
        m_Tmp = path + ".tmp";
        m_Bak = path + ".bak";
        m_Limit = limit;
        m_Policy = policy;
        m_Codec = codec;
        m_Backup = backup;
        m_Fresh = freshAllowed;
        m_Phase = HC_PHASE_IDLE;
        HCResetFiles();
    }

    void ~HCStagedStore()
    {
        if (m_RdOpen) { CloseFile(m_RdHandle); m_RdOpen = false; }
    }

    // The self-test instances print their own receipt; production stores print the evidence line.
    void HCSilence() { m_Quiet = true; }

    string HCRecovered() { return m_Selected; }
    string HCRecoverAction() { return m_Action; }
    string HCRecoverReason() { return m_Reason; }
    string HCFailReason() { return m_FailReason; }
    int HCRevision() { return m_Revision; }
    bool HCRecoverDone() { return m_Phase == HC_PHASE_DONE; }
    bool HCQuarantined() { return m_Action == "quarantine"; }
    bool HCFaulted() { return m_Phase == HC_PHASE_FAILED; }
    bool HCSaveActive() { return m_Image.Active(); }

    protected void HCResetFiles()
    {
        m_State.Clear();
        m_Rev.Clear();
        m_Bytes.Clear();
        m_Readable.Clear();
        m_Text.Clear();
        m_Why.Clear();
        for (int i = 0; i < 3; i++)
        {
            m_State.Insert(0);
            m_Rev.Insert(0);
            m_Bytes.Insert(0);
            m_Readable.Insert(0);
            m_Text.Insert("");
            m_Why.Insert("");
        }
    }

    protected string HCPathAt(int index)
    {
        if (index == 0) { return m_Tmp; }
        if (index == 1) { return m_Path; }
        return m_Bak;
    }

    protected string HCPolicyName()
    {
        if (m_Policy == HC_PRIMARY_WINS) { return "pw"; }
        return "rf";
    }

    // File name only: never print a profile path.
    protected string HCFileName()
    {
        int cut = m_Path.LastIndexOf("/");
        if (cut < 0) { cut = m_Path.LastIndexOf(":"); }
        return m_Path.Substring(cut + 1, m_Path.Length() - cut - 1);
    }

    // Writers that change a file behind the shared writer's back retire its verified-primary memo.
    protected void HCTouched()
    {
        HCStagedSaveImage.HCForget(m_Path);
        m_Image.HCForgetVerified();
    }

    // Starts a recovery. Call once before the first read of the store.
    bool HCBeginRecover()
    {
        if (m_Phase == HC_PHASE_PROBE || m_Phase == HC_PHASE_READ || m_Phase == HC_PHASE_PLAN || m_Phase == HC_PHASE_EXEC) { return false; }
        HCResetFiles();
        m_Code.Clear();
        m_A.Clear();
        m_B.Clear();
        m_N.Clear();
        m_Pc = 0;
        m_EmitAt = -1;
        m_RotStart = 0;
        m_RotEnd = 0;
        m_PvStage = 0;
        m_RdActive = false;
        m_Action = "none";
        m_Reason = "";
        m_FailReason = "";
        m_TornNote = "";
        m_Selected = "";
        m_Revision = 0;
        m_Idx = 0;
        if (!HCRecoveryGate.HCAllowWrite(m_Path))
        {
            m_Action = "quarantine";
            m_Reason = "gate";
            m_Phase = HC_PHASE_DONE;
            HCEvidence();
            return true;
        }
        m_Phase = HC_PHASE_PROBE;
        return true;
    }

    // One native operation per call. STEP_MORE, STEP_DONE or STEP_FAILED (HCSaveJob).
    int HCStepRecover()
    {
        if (m_Phase == HC_PHASE_DONE) { return HCSaveJob.STEP_DONE; }
        if (m_Phase == HC_PHASE_FAILED || m_Phase == HC_PHASE_IDLE) { return HCSaveJob.STEP_FAILED; }
        int result = HCSaveJob.STEP_MORE;
        if (m_Phase == HC_PHASE_PROBE) { result = HCStepProbe(); }
        else if (m_Phase == HC_PHASE_READ) { result = HCStepReadPhase(); }
        else if (m_Phase == HC_PHASE_PLAN) { HCPlan(); }
        else { result = HCStepExec(); }
        if (result == HCSaveJob.STEP_FAILED)
        {
            HCFailRecover();
            return HCSaveJob.STEP_FAILED;
        }
        if (m_Phase == HC_PHASE_DONE) { return HCSaveJob.STEP_DONE; }
        return HCSaveJob.STEP_MORE;
    }

    // Synchronous drain for OnStart callers: at most 64 steps (4 x 16), every step one native
    // operation, so a store up to 8 KiB recovers in well under that (3 probes, 3 files x <= 3
    // reads, plan, <= ~12 exec ops). A larger store, or one that needs more steps, fails with
    // drain_limit / drain_guard and must be driven by the scheduler through HCStepRecover.
    int HCDrainRecover()
    {
        if (m_Limit > 8192) { m_FailReason = "drain_limit"; return HCSaveJob.STEP_FAILED; }
        if (!HCBeginRecover()) { return HCSaveJob.STEP_FAILED; }
        int result = HCSaveJob.STEP_MORE;
        for (int round = 0; round < 4 && result == HCSaveJob.STEP_MORE; round++)
        {
            for (int step = 0; step < 16 && result == HCSaveJob.STEP_MORE; step++)
            {
                result = HCStepRecover();
            }
        }
        if (result == HCSaveJob.STEP_MORE)
        {
            m_FailReason = "drain_guard";
            HCFailRecover();
            return HCSaveJob.STEP_FAILED;
        }
        return result;
    }

    // Moves a copy that failed the owner's own validation into a torn slot (same routine recovery uses).
    // Drive it with HCStepRecover until STEP_DONE. Only this store's three files are accepted.
    bool HCPreserveTorn(string source)
    {
        if (m_Phase == HC_PHASE_PROBE || m_Phase == HC_PHASE_READ || m_Phase == HC_PHASE_PLAN || m_Phase == HC_PHASE_EXEC) { return false; }
        if (source != m_Path && source != m_Tmp && source != m_Bak) { return false; }
        m_Code.Clear();
        m_A.Clear();
        m_B.Clear();
        m_N.Clear();
        m_Pc = 0;
        m_EmitAt = -1;
        m_RotStart = 0;
        m_RotEnd = 0;
        m_PvStage = 0;
        m_FailReason = "";
        m_Action = "preserve_torn";
        m_Reason = "caller";
        HCEmit(HC_OP_PRESERVE, source, "", -1);
        m_Phase = HC_PHASE_EXEC;
        return true;
    }

    // Save is refused until recovery finished and no copy is quarantined.
    bool HCBeginSave(string text)
    {
        if (m_Phase != HC_PHASE_DONE || m_Action == "quarantine")
        {
            Print("[HC Store] save_refused path=" + HCFileName() + " reason=not_recovered");
            return false;
        }
        int revision;
        if (!m_Codec.HCValid(text, revision))
        {
            Print("[HC Store] save_refused path=" + HCFileName() + " reason=codec_rejected");
            return false;
        }
        return m_Image.Begin(m_Path, text, m_Limit, m_Backup, false);
    }

    // The caller may act on a save only after this returned STEP_DONE (both policies).
    int HCStepSave() { return m_Image.HCStepImage(); }

    // ---- probe and classification -------------------------------------------------------------

    protected int HCStepProbe()
    {
        if (FileExist(HCPathAt(m_Idx))) { m_State.Set(m_Idx, 3); }
        m_Idx++;
        if (m_Idx >= 3)
        {
            m_Idx = 0;
            m_Phase = HC_PHASE_READ;
        }
        return HCSaveJob.STEP_MORE;
    }

    protected int HCNextPending()
    {
        for (int i = 0; i < 3; i++)
        {
            if (m_State[i] == 3) { return i; }
        }
        return -1;
    }

    protected int HCStepReadPhase()
    {
        if (!m_RdActive)
        {
            int next = HCNextPending();
            if (next < 0)
            {
                m_Phase = HC_PHASE_PLAN;
                return HCSaveJob.STEP_MORE;
            }
            m_Idx = next;
            HCStartRead(HCPathAt(next));
        }
        int result = HCStepRead();
        if (result == HCSaveJob.STEP_FAILED) { return result; }
        if (result == HCSaveJob.STEP_DONE)
        {
            HCClassify(m_Idx);
            m_RdActive = false;
        }
        return HCSaveJob.STEP_MORE;
    }

    protected void HCStartRead(string path)
    {
        m_RdPath = path;
        m_RdStage = 0;
        m_RdText = "";
        m_RdBytes = 0;
        m_RdOver = false;
        m_RdBad = false;
        m_RdFault = false;
        m_RdActive = true;
    }

    // Open, then one <=4096 byte read per call, then close. Never one whole-file read.
    protected int HCStepRead()
    {
        if (m_RdStage == 0)
        {
            m_RdHandle = OpenFile(m_RdPath, FileMode.READ);
            if (!m_RdHandle)
            {
                m_FailReason = "read_unavailable";
                return HCSaveJob.STEP_FAILED;
            }
            m_RdOpen = true;
            m_RdStage = 1;
            return HCSaveJob.STEP_MORE;
        }
        if (m_RdStage == 1)
        {
            string piece;
            int count = ReadFile(m_RdHandle, piece, HC_CHUNK);
            m_RdStage = 2;
            if (count < 0)
            {
                m_RdFault = true;
                return HCSaveJob.STEP_MORE;
            }
            if (count != piece.Length())
            {
                // A NUL byte shortens a script string: the image is not whole.
                m_RdBad = true;
                return HCSaveJob.STEP_MORE;
            }
            if (count == 0) { return HCSaveJob.STEP_MORE; }
            m_RdBytes = m_RdBytes + count;
            if (m_RdBytes > m_Limit)
            {
                m_RdOver = true;
                return HCSaveJob.STEP_MORE;
            }
            m_RdText = m_RdText + piece;
            m_RdStage = 1;
            return HCSaveJob.STEP_MORE;
        }
        CloseFile(m_RdHandle);
        m_RdOpen = false;
        if (m_RdFault)
        {
            m_FailReason = "read_unavailable";
            return HCSaveJob.STEP_FAILED;
        }
        return HCSaveJob.STEP_DONE;
    }

    protected void HCClassify(int index)
    {
        int state = 2;
        string why = "";
        int revision = 0;
        if (m_RdOver) { why = "oversize"; }
        else if (m_RdBad) { why = "torn"; }
        else if (m_RdBytes < 1) { why = "empty"; }
        else if (m_Codec.HCValid(m_RdText, revision)) { state = 1; }
        else
        {
            why = "torn";
            revision = 0;
        }
        m_State.Set(index, state);
        m_Rev.Set(index, revision);
        m_Bytes.Set(index, m_RdBytes);
        m_Why.Set(index, why);
        if (!m_RdOver && !m_RdBad)
        {
            m_Readable.Set(index, 1);
            m_Text.Set(index, m_RdText);
        }
        m_RdText = "";
    }

    // ---- plan ---------------------------------------------------------------------------------

    protected void HCEmit(int code, string first, string second, int number)
    {
        if (m_EmitAt < 0 || m_EmitAt >= m_Code.Count())
        {
            m_Code.Insert(code);
            m_A.Insert(first);
            m_B.Insert(second);
            m_N.Insert(number);
            if (m_EmitAt >= 0) { m_EmitAt++; }
            return;
        }
        m_Code.InsertAt(code, m_EmitAt);
        m_A.InsertAt(first, m_EmitAt);
        m_B.InsertAt(second, m_EmitAt);
        m_N.InsertAt(number, m_EmitAt);
        m_EmitAt++;
    }

    protected void HCAddPreserve(int index)
    {
        if (m_Bytes[index] < 1)
        {
            // Nothing worth keeping: an empty file is deleted, not archived.
            HCEmit(HC_OP_DELETE, HCPathAt(index), "", -1);
            return;
        }
        int verify = -1;
        if (m_Readable[index] == 1) { verify = index; }
        HCEmit(HC_OP_PRESERVE, HCPathAt(index), "", verify);
        if (index == 1) { m_TornNote = "primary"; }
    }

    protected void HCAddRestoreBak()
    {
        HCEmit(HC_OP_COPY, m_Bak, m_Path, -1);
        HCEmit(HC_OP_VERIFY, m_Path, "", 2);
    }

    protected void HCAddPromote()
    {
        HCEmit(HC_OP_COPY, m_Tmp, m_Path, -1);
        HCEmit(HC_OP_VERIFY, m_Path, "", 0);
        HCEmit(HC_OP_DELETE, m_Tmp, "", -1);
    }

    protected void HCSelect(int index)
    {
        m_Selected = m_Text[index];
        m_Revision = m_Rev[index];
    }

    protected void HCNoValidCopy()
    {
        m_Reason = "no_valid_copy";
        if (!m_Fresh)
        {
            m_Action = "quarantine";
            return;
        }
        m_Action = "start_empty";
        for (int i = 0; i < 3; i++)
        {
            if (m_State[i] == 2) { HCAddPreserve(i); }
        }
    }

    protected string HCWhyPrimary()
    {
        if (m_State[1] == 2) { return "primary_invalid"; }
        return "primary_missing";
    }

    protected void HCPlan()
    {
        int tmpState = m_State[0];
        int priState = m_State[1];
        int bakState = m_State[2];
        m_Action = "none";
        m_Reason = "";
        if (tmpState == 0 && priState == 0 && bakState == 0)
        {
            // Nothing on disk: a fresh store.
            m_Action = "start_empty";
        }
        else if (tmpState == 0)
        {
            if (priState == 1)
            {
                HCSelect(1);
                if (bakState == 2 && !m_BackupNoted)
                {
                    m_BackupNoted = true;
                    if (!m_Quiet) { Print("[HC Store] backup_invalid path=" + HCFileName()); }
                }
            }
            else if (bakState == 1)
            {
                if (priState == 2) { HCAddPreserve(1); }
                HCAddRestoreBak();
                m_Action = "restore_bak";
                m_Reason = HCWhyPrimary();
                HCSelect(2);
            }
            else { HCNoValidCopy(); }
        }
        else if (tmpState == 1)
        {
            HCPlanValidTmp(priState, bakState);
        }
        else
        {
            m_Reason = m_Why[0];
            if (m_Reason != "oversize") { m_Reason = "tmp_invalid"; }
            if (priState == 1)
            {
                HCAddPreserve(0);
                m_Action = "discard_tmp";
                HCSelect(1);
            }
            else if (bakState == 1)
            {
                if (priState == 2) { HCAddPreserve(1); }
                HCAddRestoreBak();
                HCAddPreserve(0);
                m_Action = "restore_bak";
                m_Reason = HCWhyPrimary();
                HCSelect(2);
            }
            else { HCNoValidCopy(); }
        }
        m_Pc = 0;
        m_EmitAt = -1;
        m_Phase = HC_PHASE_EXEC;
        if (m_Code.Count() < 1) { HCFinishRecover(); }
    }

    protected void HCPlanValidTmp(int priState, int bakState)
    {
        bool same = priState == 1 && m_Bytes[0] == m_Bytes[1] && m_Text[0] == m_Text[1];
        if (same)
        {
            HCEmit(HC_OP_DELETE, m_Tmp, "", -1);
            m_Action = "discard_tmp";
            m_Reason = "already_committed";
            HCSelect(1);
            return;
        }
        if (priState == 1)
        {
            if (m_Policy == HC_ROLL_FORWARD && m_Rev[0] >= m_Rev[1])
            {
                // The valid older primary is replaced; the valid tmp stays until the primary is read back.
                HCEmit(HC_OP_DELETE, m_Path, "", -1);
                HCAddPromote();
                m_Action = "promote_tmp";
                m_Reason = "newer_tmp";
                HCSelect(0);
                return;
            }
            HCAddPreserve(0);
            m_Action = "discard_tmp";
            m_Reason = "primary_wins";
            if (m_Policy == HC_ROLL_FORWARD) { m_Reason = "stale_tmp"; }
            HCSelect(1);
            return;
        }
        if (m_Policy == HC_PRIMARY_WINS && bakState == 1)
        {
            if (priState == 2) { HCAddPreserve(1); }
            HCAddRestoreBak();
            HCAddPreserve(0);
            m_Action = "restore_bak";
            m_Reason = HCWhyPrimary();
            HCSelect(2);
            return;
        }
        if (priState == 2) { HCAddPreserve(1); }
        HCAddPromote();
        m_Action = "promote_tmp";
        m_Reason = HCWhyPrimary();
        if (m_Policy == HC_PRIMARY_WINS) { m_Reason = "no_other_valid_copy"; }
        HCSelect(0);
    }

    // ---- execution ----------------------------------------------------------------------------

    protected string HCFailName(string reason)
    {
        if (m_Pc >= m_RotStart && m_Pc < m_RotEnd) { return "torn_rotation_failed"; }
        return reason;
    }

    protected int HCStepExec()
    {
        if (m_Pc >= m_Code.Count())
        {
            HCFinishRecover();
            return HCSaveJob.STEP_MORE;
        }
        if (!HCRecoveryGate.HCAllowWrite(m_Path))
        {
            m_FailReason = "gate";
            return HCSaveJob.STEP_FAILED;
        }
        int code = m_Code[m_Pc];
        if (code == HC_OP_DELETE)
        {
            bool removed = DeleteFile(m_A[m_Pc]);
            HCTouched();
            if (!removed)
            {
                m_FailReason = HCFailName("delete_failed");
                return HCSaveJob.STEP_FAILED;
            }
            m_Pc++;
            return HCSaveJob.STEP_MORE;
        }
        if (code == HC_OP_COPY)
        {
            bool copied = CopyFile(m_A[m_Pc], m_B[m_Pc]);
            HCTouched();
            if (!copied)
            {
                m_FailReason = HCFailName("copy_unverified");
                return HCSaveJob.STEP_FAILED;
            }
            m_Pc++;
            return HCSaveJob.STEP_MORE;
        }
        if (code == HC_OP_VERIFY) { return HCStepVerify(); }
        return HCStepPreserve();
    }

    // Reads the new copy back chunk by chunk and compares byte count and text with its source image.
    protected int HCStepVerify()
    {
        if (!m_RdActive) { HCStartRead(m_A[m_Pc]); }
        int result = HCStepRead();
        if (result == HCSaveJob.STEP_FAILED) { return result; }
        if (result == HCSaveJob.STEP_MORE) { return result; }
        m_RdActive = false;
        int source = m_N[m_Pc];
        if (m_RdOver || m_RdBad || m_RdBytes != m_Bytes[source] || m_RdText != m_Text[source])
        {
            m_FailReason = HCFailName("copy_unverified");
            return HCSaveJob.STEP_FAILED;
        }
        m_Pc++;
        return HCSaveJob.STEP_MORE;
    }

    // Probes the four torn slots, one FileExist per call, then expands into plain operations.
    protected int HCStepPreserve()
    {
        string source = m_A[m_Pc];
        int verify = m_N[m_Pc];
        if (m_PvStage < 4)
        {
            string slot = m_Path + ".torn." + m_PvStage.ToString();
            if (!FileExist(slot))
            {
                HCExpandPreserve(source, verify, m_PvStage, false);
                m_PvStage = 0;
                return HCSaveJob.STEP_MORE;
            }
            m_PvStage++;
            return HCSaveJob.STEP_MORE;
        }
        // All four slots hold an earlier copy: stage the new one under a fifth name first.
        bool staged = FileExist(m_Path + ".torn.tmp");
        HCExpandPreserve(source, verify, -1, staged);
        m_PvStage = 0;
        return HCSaveJob.STEP_MORE;
    }

    protected void HCExpandPreserve(string source, int verify, int slot, bool staged)
    {
        m_Code.RemoveOrdered(m_Pc);
        m_A.RemoveOrdered(m_Pc);
        m_B.RemoveOrdered(m_Pc);
        m_N.RemoveOrdered(m_Pc);
        m_EmitAt = m_Pc;
        if (slot >= 0)
        {
            string target = m_Path + ".torn." + slot.ToString();
            HCEmit(HC_OP_COPY, source, target, -1);
            if (verify >= 0) { HCEmit(HC_OP_VERIFY, target, "", verify); }
            HCEmit(HC_OP_DELETE, source, "", -1);
            m_EmitAt = -1;
            return;
        }
        string stage = m_Path + ".torn.tmp";
        m_RotStart = m_Pc;
        if (staged) { HCEmit(HC_OP_DELETE, stage, "", -1); }
        HCEmit(HC_OP_COPY, source, stage, -1);
        if (verify >= 0) { HCEmit(HC_OP_VERIFY, stage, "", verify); }
        for (int j = 0; j < 3; j++)
        {
            string older = m_Path + ".torn." + j.ToString();
            string newer = m_Path + ".torn." + (j + 1).ToString();
            HCEmit(HC_OP_DELETE, older, "", -1);
            HCEmit(HC_OP_COPY, newer, older, -1);
        }
        string last = m_Path + ".torn.3";
        HCEmit(HC_OP_DELETE, last, "", -1);
        HCEmit(HC_OP_COPY, stage, last, -1);
        HCEmit(HC_OP_DELETE, stage, "", -1);
        m_RotEnd = m_EmitAt;
        HCEmit(HC_OP_DELETE, source, "", -1);
        m_EmitAt = -1;
    }

    protected void HCEvidence()
    {
        if (m_Quiet) { return; }
        string line = "[HC Store] recover path=" + HCFileName() + " policy=" + HCPolicyName() + " action=" + m_Action + " reason=" + m_Reason + " revision=" + m_Revision.ToString();
        if (m_TornNote != "") { line = line + " torn=" + m_TornNote; }
        Print("" + line);
    }

    protected void HCFinishRecover()
    {
        m_Phase = HC_PHASE_DONE;
        m_RdActive = false;
        m_Pc = 0;
        m_RotStart = 0;
        m_RotEnd = 0;
        // Drop the retained images; the selected one stays in m_Selected.
        m_Text.Clear();
        for (int i = 0; i < 3; i++) { m_Text.Insert(""); }
        HCTouched();
        // One evidence line per recovery that changed anything (or refused to).
        if (m_Code.Count() > 0 || m_Action == "quarantine") { HCEvidence(); }
        m_Code.Clear();
        m_A.Clear();
        m_B.Clear();
        m_N.Clear();
    }

    protected void HCFailRecover()
    {
        if (m_FailReason == "") { m_FailReason = "failed"; }
        m_Reason = m_FailReason;
        m_Action = "failed";
        if (m_FailReason == "torn_rotation_failed") { m_Action = "quarantine"; }
        m_Phase = HC_PHASE_FAILED;
        m_RdActive = false;
        if (m_RdOpen)
        {
            CloseFile(m_RdHandle);
            m_RdOpen = false;
        }
        HCTouched();
        m_Selected = "";
        if (!m_Quiet) { Print("[HC Store] recover path=" + HCFileName() + " policy=" + HCPolicyName() + " action=" + m_Action + " reason=" + m_FailReason + " revision=0"); }
    }
}
