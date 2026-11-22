// W4-08: boot-time, versioned, idempotent, self-repairing migrations for persisted
// HC profile files. Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist,
// :528 DeleteFile, :531 CopyFile (no rename API; replacement is delete then copy and is
// NOT atomic), :106 TickCount; 1_Core/proto/EnString.c:199/240/113 Length/IndexOf/Substring;
// 2_GameLib/tools.c ScriptCallQueue CallLater/Remove; EnDebug.c:96 Print.
//
// State lives only in the data, never in a ledger: every boot each registered step inspects
// its target, so a crash at any point leaves a state the next boot classifies and repairs.
// Per step, for target T, scratch image P = T.mig-<id>.tmp, backup slot B = T.pre-<id>.bak[n]:
//   1 verified backup copy B (never overwritten; up to HC_BACKUP_SLOTS slots)
//   2 verified full new image P (must classify CURRENT)
//   3 delete T, copy P to T, read T back == P
//   4 delete P
// Refusals never delete T, B or any operator file and never edit a file they cannot classify.
// A scratch image is deleted only when it is provably ours (empty, identical to the target, a
// torn prefix of the image being written, or reproduced by the transform from a retained backup);
// anything else is refused and kept. A refused scratch cleanup closes the store.
//
// Step contract (the runner enforces what it can, the rest is on the step author):
//   - One step per target file (a second step on the same HCTarget, compared case-folded, is
//     refused at registration; registering the same id on the same target again is a no-op).
//   - HCStore() must equal the recovery gate's store for the target (HCRecoveryGate.HCStoreFor),
//     so a target a store writes can never be migrated without that store being gated.
//     A schema change on a file that already has a step edits that step: CURRENT is always
//     what THIS build writes, and OLD widens to every earlier schema (v1 -> v3 is one
//     transform, never v1 -> v2 then v2 -> v3 as separate steps).
//   - HCClassify MUST return UNKNOWN for every torn prefix of any text it calls CURRENT or OLD
//     (and for the empty string). Recovery trusts this: a target that classifies CURRENT while a
//     scratch image exists is only a finished commit when the texts are identical.
//   - HCTransform and HCClassify are pure and deterministic across boots of the same build.
// No migration is registered by default: steps are added by HCBuiltins() only when a plan names
// the schema change.
class HCMigrationStep
{
    static const int STATE_UNKNOWN = 0;
    static const int STATE_CURRENT = 1;
    static const int STATE_OLD = 2;
    static const int STATE_NEWER = 3;

    // Stable token, [a-z0-9-], 1..48 chars; names the scratch and backup files.
    string HCId() { return ""; }
    // Gate store refused on this boot when the step refuses or is deferred:
    // "world", "escalation", "groups", or "" for a file no store gate covers. It must equal
    // HCRecoveryGate.HCStoreFor(HCTarget()). A step with store "" has no gate to close, so it
    // is never deferred: it always runs in the boot pass.
    string HCStore() { return ""; }
    // Full profile path, starting "$profile:HollowCountry/".
    string HCTarget() { return ""; }
    int HCLimit() { return HCGroupIO.HC_RAW_READ_CAP; }
    // Pure classification of the whole file text; no IO. A file that is torn or not
    // recognisably this store's format must be UNKNOWN (every torn prefix, no exceptions),
    // a higher version NEWER. CURRENT is what this build writes; OLD covers all earlier schemas.
    int HCClassify(string text) { return HCMigrationStep.STATE_UNKNOWN; }
    // Pure and deterministic OLD -> CURRENT text; no IO. Return false with a token reason to refuse.
    bool HCTransform(string text, out string migrated, out string reason)
    {
        reason = "not_implemented";
        return false;
    }
}

// Self-test probe: a synthetic two-version text format on a scratch file. Never a store.
class HCMigrationProbeStep : HCMigrationStep
{
    static const string PATH = "$profile:HollowCountry/migrate-selftest.probe";
    // Maps to the "escalation" gate by prefix; only ever holds scratch probe text.
    static const string STORE_PATH = "$profile:HollowCountry/escalation.json.migrate-selftest.probe";
    protected string m_Id = "selftest-probe";
    protected string m_Target = PATH;
    protected string m_Store = "";
    // Self-test only: lets a second probe carry another id, target or store.
    void HCSetId(string id) { m_Id = id; }
    void HCSetTarget(string target) { m_Target = target; }
    void HCSetStore(string store) { m_Store = store; }
    override string HCId() { return m_Id; }
    override string HCStore() { return m_Store; }
    override string HCTarget() { return m_Target; }
    override int HCLimit() { return 256; }
    override int HCClassify(string text)
    {
        int length = text.Length();
        if (length < 11 || text.Substring(length - 1, 1) != ";") { return HCMigrationStep.STATE_UNKNOWN; }
        string head = text.Substring(0, 9);
        if (head == "probe-v2:") { return HCMigrationStep.STATE_CURRENT; }
        if (head == "probe-v1:") { return HCMigrationStep.STATE_OLD; }
        if (head == "probe-v3:") { return HCMigrationStep.STATE_NEWER; }
        return HCMigrationStep.STATE_UNKNOWN;
    }
    override bool HCTransform(string text, out string migrated, out string reason)
    {
        reason = "";
        migrated = "probe-v2:" + text.Substring(9, text.Length() - 9);
        return true;
    }
}

// One migration step as a resumable machine. Every HCStep() call performs AT MOST ONE native
// file operation (EnSystem.c:397 FileExist, :417 OpenFile, :425 ReadFile, :443 CloseFile, :462
// FPrint, :528 DeleteFile, :531 CopyFile) and returns, so the server tick that drives it never
// blocks on more than one call. The boot pass drives the same machine in a bounded loop
// (HCMigrationRunner.HCRunStep), so there is a single implementation of the protocol.
//
// Protocol (unchanged on disk, per step for target T, scratch image P, backup slot B):
//   verified backup B -> verified full new image P -> delete T, copy P to T, read T back == P
//   -> delete P. State lives only in the data; a stopped machine (halt, shutdown, crash) leaves
//   exactly the on-disk states the recovery cases of HCMigrationRunner already classify.
// Transfers use 4 KiB chunks over one retained handle: native string/FPrint transfer is capped
// below 8 KiB per call (HCStagedSaveImage, build 113), which also bounds one op to 4 KiB.
// A handle is only ever open between a successful open stage and its close stage; a failing
// stage still runs the close stage before the machine reports a result.
class HCMigrationJob
{
    static const int STEP_DONE = 0;
    static const int STEP_MORE = 1;
    // Largest legitimate step: a handful of reads/writes of the 8 MiB cap in 4 KiB chunks
    // (<= 4 * 2048 reads + 3 * 2048 writes + provenance reads). A literal, like HC_MAX_STAGES.
    static const int HC_MAX_STEPS = 65536;
    static const int HC_CHUNK_BYTES = 4096;
    static const int HC_MAX_HOPS = 64;

    static const int OP_NONE = 0;
    static const int OP_EXISTS = 1;
    static const int OP_DELETE = 2;
    static const int OP_COPY = 3;
    static const int OP_OPEN_READ = 4;
    static const int OP_OPEN_WRITE = 5;
    static const int OP_READ = 6;
    static const int OP_WRITE = 7;
    static const int OP_CLOSE = 8;

    static const int SUB_NONE = 0;
    static const int SUB_READ = 1;
    static const int SUB_WRITE = 2;
    static const int SUB_DELETE = 3;

    static const int PH_START = 0;
    static const int PH_HAS_PENDING = 1;
    static const int PH_HAS_TARGET = 2;
    static const int PH_CLASSIFY = 3;
    static const int PH_CUR_LEFTOVER = 4;
    static const int PH_CUR_DELETED = 5;
    static const int PH_MIG = 6;
    static const int PH_MIG_PENDING = 7;
    static const int PH_MIG_STALE = 8;
    static const int PH_MIG_PROVED = 9;
    static const int PH_MIG_DELETE = 10;
    static const int PH_MIG_DELETED = 11;
    static const int PH_BACKUP = 12;
    static const int PH_BK_SLOT = 13;
    static const int PH_BK_EXISTS = 14;
    static const int PH_BK_COPIED = 15;
    static const int PH_BK_VERIFY = 16;
    static const int PH_BK_OCCUPANT = 17;
    static const int PH_WRITE = 18;
    static const int PH_W_EXISTS = 19;
    static const int PH_W_WRITTEN = 20;
    static const int PH_W_VERIFY = 21;
    static const int PH_REC = 22;
    static const int PH_REC_READ = 23;
    static const int PH_REC_PROVED = 24;
    static const int PH_PROV = 25;
    static const int PH_PV_SLOT = 26;
    static const int PH_PV_EXISTS = 27;
    static const int PH_PV_READ = 28;
    static const int PH_COMMIT = 29;
    static const int PH_C_TARGET = 30;
    static const int PH_C_DELETED = 31;
    static const int PH_C_COPY = 32;
    static const int PH_C_COPIED = 33;
    static const int PH_C_RETRY = 34;
    static const int PH_C_RETRY_DELETED = 35;
    static const int PH_C_VERIFY = 36;
    static const int PH_C_READBACK = 37;
    static const int PH_C_CLEANED = 38;
    static const int PH_C_CHECKED = 39;

    // The operation the next HCExec performs and its operands.
    protected int m_Op;
    protected string m_PathA;
    protected string m_PathB;
    protected string m_Chunk;
    protected int m_Count;
    protected bool m_Flag;
    protected FileHandle m_Handle;
    protected bool m_HandleOpen;
    protected int m_Steps;

    // Sub-routine (chunked read, chunked create-write, delete-and-verify) registers.
    protected int m_Sub;
    protected int m_SubStage;
    protected int m_Ret;
    protected string m_SubPath;
    protected string m_SubData;
    protected int m_SubLimit;
    protected bool m_SubEmpty;
    protected bool m_SubVerify;
    protected int m_SubBytes;
    protected bool m_SubFail;
    protected bool m_SubOk;
    protected string m_SubText;

    // Program registers.
    protected HCMigrationStep m_Step;
    protected int m_Phase;
    protected string m_Id;
    protected string m_Target;
    protected string m_Pending;
    protected int m_Limit;
    protected bool m_HasPending;
    protected bool m_Readable;
    protected string m_Text;
    protected string m_Migrated;
    protected string m_Image;
    protected bool m_RecReadable;
    protected string m_RecTarget;
    protected string m_OkReason;
    protected int m_Slot;
    protected int m_PvSlot;
    protected int m_ProvRet;
    protected bool m_ProvOk;
    protected string m_ProvImage;
    protected bool m_Copied;
    protected bool m_CopyRetried;
    protected bool m_PendingDeleteFailed;
    protected bool m_Interleaved;
    protected bool m_Finished;
    protected int m_Result;
    protected string m_Reason;

    void ~HCMigrationJob() { HCAbort(); }

    // The step must already have passed HCMigrationRunner.HCStepInvalid.
    void HCBegin(HCMigrationStep step)
    {
        m_Step = step;
        m_Phase = PH_START;
        m_Finished = false;
        m_Result = HCMigrationRunner.RESULT_REFUSED;
        m_Reason = "";
        m_Op = OP_NONE;
        m_Sub = SUB_NONE;
        m_Steps = 0;
        m_PendingDeleteFailed = false;
        m_CopyRetried = false;
        m_Id = step.HCId();
        m_Target = step.HCTarget();
        m_Limit = step.HCLimit();
        m_Pending = HCMigrationRunner.HCPendingPath(m_Target, m_Id);
    }

    // A tick-driven job shares the profile with the rest of the server between its steps: it
    // re-reads the target right before deleting it (see PH_C_TARGET). The synchronous boot pass
    // and self-test drivers do not need the extra read.
    void HCSetInterleaved() { m_Interleaved = true; }

    bool HCFinished() { return m_Finished; }
    int HCResult() { return m_Result; }
    string HCReason() { return m_Reason; }
    bool HCPendingDeleteFailed() { return m_PendingDeleteFailed; }
    // Calls made so far (every HCStep call, including the one that reported the result).
    int HCCalls() { return m_Steps; }

    // True when the last step changed a file (create, write, copy or delete): the points at
    // which a crash leaves a different on-disk state.
    bool HCMutated() { return m_Op == OP_DELETE || m_Op == OP_COPY || m_Op == OP_OPEN_WRITE || m_Op == OP_WRITE; }

    // Stops a machine that will not be resumed (halt, guard). Never deletes a file: the files
    // it leaves are a state the next boot classifies, exactly like a crash at this point.
    void HCAbort()
    {
        if (m_HandleOpen)
        {
            CloseFile(m_Handle);
            m_HandleOpen = false;
        }
        m_Finished = true;
    }

    // One step: plan the next operation from the previous result (no file access), then perform
    // that single operation. Returns STEP_MORE while operations remain, STEP_DONE with the
    // result readable through HCResult/HCReason.
    int HCStep()
    {
        m_Steps = m_Steps + 1;
        if (m_Finished) { return STEP_DONE; }
        m_Op = OP_NONE;
        HCPlan();
        if (m_Finished) { return STEP_DONE; }
        HCExec();
        return STEP_MORE;
    }

    // Exactly one native file operation per arm.
    protected void HCExec()
    {
        if (m_Op == OP_EXISTS) { m_Flag = FileExist(m_PathA); return; }
        if (m_Op == OP_DELETE) { m_Flag = DeleteFile(m_PathA); return; }
        if (m_Op == OP_COPY) { m_Flag = CopyFile(m_PathA, m_PathB); return; }
        if (m_Op == OP_OPEN_READ)
        {
            m_Handle = OpenFile(m_PathA, FileMode.READ);
            m_Flag = true;
            if (!m_Handle) { m_Flag = false; }
            m_HandleOpen = m_Flag;
            return;
        }
        if (m_Op == OP_OPEN_WRITE)
        {
            m_Handle = OpenFile(m_PathA, FileMode.WRITE);
            m_Flag = true;
            if (!m_Handle) { m_Flag = false; }
            m_HandleOpen = m_Flag;
            return;
        }
        if (m_Op == OP_READ)
        {
            string piece;
            m_Count = ReadFile(m_Handle, piece, HC_CHUNK_BYTES);
            m_Chunk = piece;
            return;
        }
        if (m_Op == OP_WRITE) { FPrint(m_Handle, m_Chunk); return; }
        if (m_Op == OP_CLOSE)
        {
            CloseFile(m_Handle);
            m_HandleOpen = false;
            m_Flag = true;
            return;
        }
    }

    // Pure: advances the program until it requests an operation or finishes.
    protected void HCPlan()
    {
        for (int hop = 0; hop < HC_MAX_HOPS; hop++)
        {
            if (m_Op != OP_NONE || m_Finished) { return; }
            if (m_Sub != SUB_NONE) { HCSubPlan(); }
            else { HCProgram(); }
        }
        if (m_Op == OP_NONE && !m_Finished) { HCFinish(HCMigrationRunner.RESULT_REFUSED, "machine_fault"); }
    }

    protected void HCFinish(int result, string reason)
    {
        m_Finished = true;
        m_Result = result;
        m_Reason = reason;
    }

    protected void HCRefuse(string reason) { HCFinish(HCMigrationRunner.RESULT_REFUSED, reason); }

    protected void HCGo(int phase) { m_Phase = phase; }

    // Single-operation requests: the result is in m_Flag when phase `next` runs.
    protected void HCAsk(int op, string pathA, string pathB, int next)
    {
        m_Op = op;
        m_PathA = pathA;
        m_PathB = pathB;
        m_Phase = next;
    }

    protected void HCExists(string path, int next) { HCAsk(OP_EXISTS, path, "", next); }
    protected void HCCopy(string from, string to, int next) { HCAsk(OP_COPY, from, to, next); }

    // Sub-routine calls: the result is in m_SubOk (and m_SubText for a read) when phase `next` runs.
    protected void HCCall(int sub, string path, string data, int limit, bool allowEmpty, int next)
    {
        m_Sub = sub;
        m_SubStage = 0;
        m_SubPath = path;
        m_SubData = data;
        m_SubLimit = limit;
        m_SubEmpty = allowEmpty;
        m_SubVerify = false;
        m_SubBytes = 0;
        m_SubFail = false;
        m_SubOk = false;
        m_SubText = "";
        m_Ret = next;
    }

    protected void HCCallRead(string path, bool allowEmpty, int next) { HCCall(SUB_READ, path, "", m_Limit, allowEmpty, next); }

    // Chunked comparison of a file with `expected`: each chunk is compared to the matching slice
    // as it arrives and nothing is accumulated. m_SubOk is true only for an identical file.
    protected void HCCallVerify(string path, string expected, bool allowEmpty, int next)
    {
        HCCall(SUB_READ, path, expected, m_Limit, allowEmpty, next);
        m_SubVerify = true;
    }

    protected void HCCallDelete(string path, int next) { HCCall(SUB_DELETE, path, "", 0, false, next); }

    protected void HCSubEnd(bool ok)
    {
        m_SubOk = ok;
        m_Sub = SUB_NONE;
        m_Phase = m_Ret;
    }

    protected void HCClose(int stage)
    {
        m_Op = OP_CLOSE;
        m_SubStage = stage;
    }

    protected void HCSubPlan()
    {
        if (m_Sub == SUB_READ) { HCSubRead(); return; }
        if (m_Sub == SUB_WRITE) { HCSubWrite(); return; }
        HCSubDelete();
    }

    // Chunked read of the whole file; ends when the file reports 0 bytes. 0: open, 1: opened,
    // 2: a chunk arrived, 3: closed. Refused when it exceeds the limit or is empty (unless allowed).
    protected void HCSubRead()
    {
        if (m_SubStage == 0)
        {
            m_Op = OP_OPEN_READ;
            m_PathA = m_SubPath;
            m_SubStage = 1;
            return;
        }
        if (m_SubStage == 1)
        {
            if (!m_Flag) { HCSubEnd(false); return; }
            m_Op = OP_READ;
            m_SubStage = 2;
            return;
        }
        if (m_SubStage == 2)
        {
            if (m_Count < 0 || m_Count != m_Chunk.Length()) { m_SubFail = true; }
            else
            {
                if (m_SubBytes + m_Count > m_SubLimit) { m_SubFail = true; }
                else if (!m_SubVerify) { m_SubText = m_SubText + m_Chunk; }
                else if (m_SubBytes + m_Count > m_SubData.Length()) { m_SubFail = true; }
                else if (m_Count > 0 && m_SubData.Substring(m_SubBytes, m_Count) != m_Chunk) { m_SubFail = true; }
                m_SubBytes = m_SubBytes + m_Count;
            }
            if (m_SubFail || m_Count == 0) { HCClose(3); return; }
            m_Op = OP_READ;
            return;
        }
        bool ok = !m_SubFail;
        if (ok && m_SubVerify) { ok = m_SubBytes == m_SubData.Length(); }
        else if (ok) { ok = m_SubText.Length() == m_SubBytes; }
        if (m_SubBytes < 1 && !m_SubEmpty) { ok = false; }
        if (!ok) { m_SubText = ""; }
        HCSubEnd(ok);
    }

    // Chunked create-write of m_SubData. 0: open, 1: opened, 2: write chunks, 3: closed.
    // FPrint reports nothing: callers verify by reading the file back.
    protected void HCSubWrite()
    {
        if (m_SubStage == 0)
        {
            m_Op = OP_OPEN_WRITE;
            m_PathA = m_SubPath;
            m_SubStage = 1;
            return;
        }
        if (m_SubStage == 1)
        {
            if (!m_Flag) { HCSubEnd(false); return; }
            m_SubStage = 2;
        }
        if (m_SubStage == 2)
        {
            int remaining = m_SubData.Length() - m_SubBytes;
            if (remaining < 1) { HCClose(3); return; }
            int length = remaining;
            if (length > HC_CHUNK_BYTES) { length = HC_CHUNK_BYTES; }
            string piece = m_SubData.Substring(m_SubBytes, length);
            if (piece.Length() != length)
            {
                m_SubFail = true;
                HCClose(3);
                return;
            }
            m_Chunk = piece;
            m_SubBytes = m_SubBytes + length;
            m_Op = OP_WRITE;
            return;
        }
        HCSubEnd(!m_SubFail);
    }

    // Delete, then verify the file is gone. 0: delete, 1: deleted, 2: existence probed.
    protected void HCSubDelete()
    {
        if (m_SubStage == 0)
        {
            m_Op = OP_DELETE;
            m_PathA = m_SubPath;
            m_SubStage = 1;
            return;
        }
        if (m_SubStage == 1)
        {
            if (!m_Flag) { HCSubEnd(false); return; }
            m_Op = OP_EXISTS;
            m_PathA = m_SubPath;
            m_SubStage = 2;
            return;
        }
        HCSubEnd(!m_Flag);
    }

    // Pure program counter: each phase consumes the previous result and requests the next
    // operation, calls a sub-routine, or finishes.
    protected void HCProgram()
    {
        if (m_Phase == PH_START)
        {
            HCExists(m_Pending, PH_HAS_PENDING);
            return;
        }
        if (m_Phase == PH_HAS_PENDING)
        {
            m_HasPending = m_Flag;
            HCExists(m_Target, PH_HAS_TARGET);
            return;
        }
        if (m_Phase == PH_HAS_TARGET)
        {
            if (m_Flag)
            {
                HCCallRead(m_Target, true, PH_CLASSIFY);
                return;
            }
            if (!m_HasPending)
            {
                HCFinish(HCMigrationRunner.RESULT_SKIPPED, "target_absent");
                return;
            }
            // Crash between deleting the target and copying the verified image over it.
            m_RecReadable = false;
            m_RecTarget = "";
            m_OkReason = "recovered_missing_target";
            HCGo(PH_REC);
            return;
        }
        if (m_Phase < PH_MIG) { HCProgramClassify(); return; }
        if (m_Phase < PH_REC) { HCProgramMigrate(); return; }
        HCProgramRecover();
    }

    // Classification of the target and the scratch image that sits beside a CURRENT one.
    protected void HCProgramClassify()
    {
        if (m_Phase == PH_CLASSIFY)
        {
            m_Readable = m_SubOk;
            m_Text = m_SubText;
            int state = HCMigrationStep.STATE_UNKNOWN;
            if (m_Readable) { state = m_Step.HCClassify(m_Text); }
            if (state == HCMigrationStep.STATE_CURRENT)
            {
                if (!m_HasPending)
                {
                    HCFinish(HCMigrationRunner.RESULT_SKIPPED, "current");
                    return;
                }
                // A scratch image beside a CURRENT target is a finished commit only when it is the
                // same text. A torn prefix that misclassified CURRENT is recovered; anything else
                // is not ours to delete: refuse and keep both files. An empty scratch file (a crash
                // right after creating it) is ours and removable.
                HCCallRead(m_Pending, true, PH_CUR_LEFTOVER);
                return;
            }
            if (state == HCMigrationStep.STATE_NEWER)
            {
                HCRefuse("newer_schema");
                return;
            }
            if (state == HCMigrationStep.STATE_UNKNOWN)
            {
                if (m_HasPending && m_Readable)
                {
                    // Crash while copying the image over the target: a torn prefix of it, or empty.
                    // An unreadable (oversize or unopenable) target is evidence and never replaced.
                    m_RecReadable = true;
                    m_RecTarget = m_Text;
                    m_OkReason = "recovered_torn_commit";
                    HCGo(PH_REC);
                    return;
                }
                if (m_Readable) { HCRefuse("target_schema_unknown"); }
                else { HCRefuse("target_unreadable"); }
                return;
            }
            if (state != HCMigrationStep.STATE_OLD)
            {
                HCRefuse("classify_invalid");
                return;
            }
            HCGo(PH_MIG);
            return;
        }
        if (m_Phase == PH_CUR_LEFTOVER)
        {
            if (!m_SubOk)
            {
                HCRefuse("pending_conflicts_current");
                return;
            }
            if (m_SubText.Length() > 0 && m_SubText != m_Text)
            {
                if (HCMigrationRunner.HCHasPrefix(m_SubText, m_Text))
                {
                    m_RecReadable = true;
                    m_RecTarget = m_Text;
                    m_OkReason = "recovered_torn_commit";
                    HCGo(PH_REC);
                    return;
                }
                HCRefuse("pending_conflicts_current");
                return;
            }
            // A scratch image that stays beside a store that later writes a newer target is
            // dangerous (a torn swap could be "recovered" from it): refuse, which closes the store.
            HCCallDelete(m_Pending, PH_CUR_DELETED);
            return;
        }
        // PH_CUR_DELETED
        if (!m_SubOk)
        {
            HCRefuse("current_pending_cleanup_failed");
            return;
        }
        HCFinish(HCMigrationRunner.RESULT_SKIPPED, "current_pending_removed");
    }

    // OLD target: transform, clear a provably-ours scratch image, back up, write and commit.
    protected void HCProgramMigrate()
    {
        if (m_Phase == PH_MIG)
        {
            string migrated;
            string why;
            if (!m_Step.HCTransform(m_Text, migrated, why))
            {
                if (why == "") { why = "transform_refused"; }
                HCRefuse(why);
                return;
            }
            if (migrated.Length() < 1 || migrated.Length() > m_Limit || m_Step.HCClassify(migrated) != HCMigrationStep.STATE_CURRENT)
            {
                HCRefuse("transform_not_current");
                return;
            }
            m_Migrated = migrated;
            // A scratch image beside an OLD target was never committed and is recomputed. Delete it
            // only if it is provably ours: empty, identical to the target (or a torn prefix of the
            // image about to be written), or an image a retained backup reproduces through the
            // transform. A complete CURRENT image without that proof may be the only newest copy
            // (for example after the operator restored an older target): refuse and keep both.
            HCExists(m_Pending, PH_MIG_PENDING);
            return;
        }
        if (m_Phase == PH_MIG_PENDING)
        {
            if (m_Flag) { HCCallRead(m_Pending, true, PH_MIG_STALE); }
            else { HCGo(PH_BACKUP); }
            return;
        }
        if (m_Phase == PH_MIG_STALE)
        {
            if (!m_SubOk)
            {
                HCRefuse("pending_conflicts_old");
                return;
            }
            if (HCMigrationRunner.HCHasPrefix(m_Migrated, m_SubText) || m_SubText == m_Text)
            {
                HCGo(PH_MIG_DELETE);
                return;
            }
            m_ProvImage = m_SubText;
            m_ProvRet = PH_MIG_PROVED;
            HCGo(PH_PROV);
            return;
        }
        if (m_Phase == PH_MIG_PROVED)
        {
            if (!m_ProvOk)
            {
                HCRefuse("pending_conflicts_old");
                return;
            }
            HCGo(PH_MIG_DELETE);
            return;
        }
        if (m_Phase == PH_MIG_DELETE)
        {
            HCCallDelete(m_Pending, PH_MIG_DELETED);
            return;
        }
        if (m_Phase == PH_MIG_DELETED)
        {
            if (!m_SubOk)
            {
                HCRefuse("pending_cleanup_failed");
                return;
            }
            HCGo(PH_BACKUP);
            return;
        }
        if (m_Phase < PH_WRITE) { HCProgramBackup(); return; }
        HCProgramWrite();
    }

    // Reuse a slot already holding exactly this image; otherwise fill the first free slot.
    // An occupied slot with other bytes is evidence and is never touched.
    protected void HCProgramBackup()
    {
        if (m_Phase == PH_BACKUP)
        {
            m_Slot = 1;
            HCGo(PH_BK_SLOT);
            return;
        }
        if (m_Phase == PH_BK_SLOT)
        {
            if (m_Slot > HCMigrationRunner.HC_BACKUP_SLOTS)
            {
                HCRefuse("backup_slots_full");
                return;
            }
            HCExists(HCMigrationRunner.HCBackupPath(m_Target, m_Id, m_Slot), PH_BK_EXISTS);
            return;
        }
        string backup = HCMigrationRunner.HCBackupPath(m_Target, m_Id, m_Slot);
        if (m_Phase == PH_BK_EXISTS)
        {
            if (m_Flag)
            {
                HCCallVerify(backup, m_Text, false, PH_BK_OCCUPANT);
                return;
            }
            HCCopy(m_Target, backup, PH_BK_COPIED);
            return;
        }
        if (m_Phase == PH_BK_COPIED)
        {
            if (!m_Flag)
            {
                HCRefuse("backup_failed");
                return;
            }
            HCCallVerify(backup, m_Text, false, PH_BK_VERIFY);
            return;
        }
        if (m_Phase == PH_BK_VERIFY)
        {
            if (!m_SubOk)
            {
                HCRefuse("backup_failed");
                return;
            }
            HCGo(PH_WRITE);
            return;
        }
        // PH_BK_OCCUPANT
        if (m_SubOk)
        {
            HCGo(PH_WRITE);
            return;
        }
        m_Slot = m_Slot + 1;
        HCGo(PH_BK_SLOT);
    }

    // Create-only write of the scratch image, then a readback that must be identical.
    protected void HCProgramWrite()
    {
        if (m_Phase == PH_WRITE)
        {
            if (m_Migrated.Length() < 1 || m_Migrated.Length() > m_Limit)
            {
                HCRefuse("pending_write_failed");
                return;
            }
            HCExists(m_Pending, PH_W_EXISTS);
            return;
        }
        if (m_Phase == PH_W_EXISTS)
        {
            if (m_Flag)
            {
                HCRefuse("pending_write_failed");
                return;
            }
            HCCall(SUB_WRITE, m_Pending, m_Migrated, m_Limit, false, PH_W_WRITTEN);
            return;
        }
        if (m_Phase == PH_W_WRITTEN)
        {
            if (!m_SubOk)
            {
                HCRefuse("pending_write_failed");
                return;
            }
            HCCallVerify(m_Pending, m_Migrated, false, PH_W_VERIFY);
            return;
        }
        // PH_W_VERIFY
        if (!m_SubOk)
        {
            HCRefuse("pending_write_failed");
            return;
        }
        m_Image = m_Migrated;
        m_OkReason = "migrated";
        HCGo(PH_COMMIT);
    }

    // Recovery of a stopped commit, provenance of an image, and the commit itself.
    protected void HCProgramRecover()
    {
        if (m_Phase == PH_REC)
        {
            HCCallRead(m_Pending, false, PH_REC_READ);
            return;
        }
        if (m_Phase == PH_REC_READ)
        {
            if (!m_SubOk || m_Step.HCClassify(m_SubText) != HCMigrationStep.STATE_CURRENT)
            {
                HCRefuse("pending_image_invalid");
                return;
            }
            m_Image = m_SubText;
            // Only a torn prefix (or an empty file) of our own image may be replaced.
            if (m_RecReadable && !HCMigrationRunner.HCHasPrefix(m_Image, m_RecTarget))
            {
                HCRefuse("target_schema_unknown");
                return;
            }
            m_ProvImage = m_Image;
            m_ProvRet = PH_REC_PROVED;
            HCGo(PH_PROV);
            return;
        }
        if (m_Phase == PH_REC_PROVED)
        {
            if (!m_ProvOk)
            {
                HCRefuse("pending_provenance_missing");
                return;
            }
            HCGo(PH_COMMIT);
            return;
        }
        if (m_Phase < PH_COMMIT) { HCProgramProvenance(); return; }
        HCProgramCommit();
    }

    // A pending image may replace the target only when some backup slot proves it descends from
    // that backup: the slot classifies OLD and the deterministic transform reproduces the image.
    protected void HCProgramProvenance()
    {
        if (m_Phase == PH_PROV)
        {
            m_ProvOk = false;
            m_PvSlot = 1;
            HCGo(PH_PV_SLOT);
            return;
        }
        if (m_Phase == PH_PV_SLOT)
        {
            if (m_PvSlot > HCMigrationRunner.HC_BACKUP_SLOTS)
            {
                HCGo(m_ProvRet);
                return;
            }
            HCExists(HCMigrationRunner.HCBackupPath(m_Target, m_Id, m_PvSlot), PH_PV_EXISTS);
            return;
        }
        if (m_Phase == PH_PV_EXISTS)
        {
            if (m_Flag)
            {
                HCCallRead(HCMigrationRunner.HCBackupPath(m_Target, m_Id, m_PvSlot), false, PH_PV_READ);
                return;
            }
            m_PvSlot = m_PvSlot + 1;
            HCGo(PH_PV_SLOT);
            return;
        }
        // PH_PV_READ
        if (m_SubOk && m_Step.HCClassify(m_SubText) == HCMigrationStep.STATE_OLD)
        {
            string old = m_SubText;
            string migrated;
            string why;
            if (m_Step.HCTransform(old, migrated, why) && migrated == m_ProvImage)
            {
                m_ProvOk = true;
                HCGo(m_ProvRet);
                return;
            }
        }
        m_PvSlot = m_PvSlot + 1;
        HCGo(PH_PV_SLOT);
    }

    // Replace target with the verified pending image. Not atomic: the pending image and the
    // backup stay on disk until readback succeeds, which is what the recovery paths rely on.
    protected void HCProgramCommit()
    {
        if (m_Phase == PH_COMMIT)
        {
            HCExists(m_Target, PH_C_TARGET);
            return;
        }
        if (m_Phase == PH_C_TARGET)
        {
            if (!m_Flag) { HCGo(PH_C_COPY); return; }
            // Tick-driven: other server code ran since this job read the target. Delete it only
            // if it still holds exactly the text this job classified (empty if it was absent).
            if (m_Interleaved) { HCCallVerify(m_Target, m_Text, true, PH_C_CHECKED); }
            else { HCCallDelete(m_Target, PH_C_DELETED); }
            return;
        }
        if (m_Phase == PH_C_CHECKED)
        {
            if (!m_SubOk)
            {
                // Nothing is deleted: target, scratch image and backup stay for the next boot.
                HCRefuse("target_changed");
                return;
            }
            HCCallDelete(m_Target, PH_C_DELETED);
            return;
        }
        if (m_Phase == PH_C_DELETED)
        {
            if (!m_SubOk)
            {
                HCRefuse("target_delete_failed");
                return;
            }
            HCGo(PH_C_COPY);
            return;
        }
        if (m_Phase == PH_C_COPY)
        {
            // Installed EnSystem.c:531 CopyFile does not document overwrite, so never rely on it:
            // the target is absent here, and a failed first copy that left a partial file is
            // deleted before the single retry.
            m_CopyRetried = false;
            HCCopy(m_Pending, m_Target, PH_C_COPIED);
            return;
        }
        if (m_Phase == PH_C_COPIED)
        {
            m_Copied = m_Flag;
            if (!m_Copied && !m_CopyRetried)
            {
                m_CopyRetried = true;
                HCExists(m_Target, PH_C_RETRY);
                return;
            }
            HCGo(PH_C_VERIFY);
            return;
        }
        if (m_Phase == PH_C_RETRY)
        {
            if (m_Flag) { HCCallDelete(m_Target, PH_C_RETRY_DELETED); }
            else { HCCopy(m_Pending, m_Target, PH_C_COPIED); }
            return;
        }
        if (m_Phase == PH_C_RETRY_DELETED)
        {
            if (!m_SubOk)
            {
                HCRefuse("target_delete_failed");
                return;
            }
            HCCopy(m_Pending, m_Target, PH_C_COPIED);
            return;
        }
        if (m_Phase == PH_C_VERIFY)
        {
            if (!m_Copied)
            {
                HCRefuse("commit_failed_pending_kept");
                return;
            }
            HCCallVerify(m_Target, m_Image, false, PH_C_READBACK);
            return;
        }
        if (m_Phase == PH_C_READBACK)
        {
            if (!m_SubOk)
            {
                HCRefuse("commit_failed_pending_kept");
                return;
            }
            HCCallDelete(m_Pending, PH_C_CLEANED);
            return;
        }
        // PH_C_CLEANED. The target is committed and verified, but a scratch image that cannot be
        // deleted leaves the step unfinished: the runner closes the store for this boot. The next
        // boot sees a CURRENT target with an identical scratch image and tries to remove it again;
        // if that also fails it refuses as current_pending_cleanup_failed (store closed).
        if (!m_SubOk) { m_PendingDeleteFailed = true; }
        HCFinish(HCMigrationRunner.RESULT_APPLIED, m_OkReason);
    }
}

class HCMigrationRunner
{
    static const int RESULT_APPLIED = 1;
    static const int RESULT_SKIPPED = 2;
    static const int RESULT_REFUSED = 3;
    static const int HC_BACKUP_SLOTS = 4;
    static const int HC_BOOT_STEP_CAP = 8;
    static const float HC_BOOT_BUDGET_MS = 250;
    // First continuation after the boot pass, and the pause between the single file operations
    // of a deferred step (one HCMigrationJob.HCStep per call).
    static const int HC_TICK_INTERVAL_MS = 1000;
    static const int HC_STEP_INTERVAL_MS = 25;
    static const string HC_PREFIX = "$profile:HollowCountry/";

    protected static ref array<ref HCMigrationStep> s_Steps = new array<ref HCMigrationStep>;
    // Steps still to run this boot or on later ticks (gated steps only; ungated run in the boot pass).
    protected static ref array<HCMigrationStep> s_Queue = new array<HCMigrationStep>;
    // Stores closed by steps refused at registration. Registration happens once per script
    // lifetime, so HCHalt must not clear these; HCGate applies them on every boot.
    protected static ref array<string> s_RegStores = new array<string>;
    protected static ref array<string> s_RegReasons = new array<string>;
    // Registration refusals this script lifetime (not cleared by HCHalt; shown in every summary).
    protected static int s_RegRefused;
    protected static ref HCWorkBudget s_Budget = new HCWorkBudget;
    protected static bool s_BuiltinsRegistered;
    protected static bool s_SelfTested;
    protected static bool s_SelfTestPassed;
    protected static bool s_Scheduled;
    // The deferred step in flight (tick driver only) and the registry entry it runs.
    protected static ref HCMigrationJob s_Job;
    protected static HCMigrationStep s_JobStep;
    protected static bool s_WorldEnabled = true;
    protected static int s_Next;
    protected static int s_Applied;
    protected static int s_Skipped;
    protected static int s_Refused;
    protected static string s_BlockWorld;
    protected static string s_BlockEscalation;
    protected static string s_BlockGroups;

    // Steps for stores or files introduced by a plan-named schema change register here.
    // Intentionally empty: nothing that changes behaviour is registered by default.
    protected static void HCBuiltins()
    {
    }

    static bool HCRegisterStep(HCMigrationStep step)
    {
        if (!step) { return false; }
        string id = step.HCId();
        string why = HCRegistrationWhy(step, s_Steps);
        if (why == "already_registered") { return true; }
        if (why != "")
        {
            s_RegRefused++;
            HCReceipt(id, HCMigrationRunner.RESULT_REFUSED, why);
            // A refused step never runs, so its store would otherwise open on an unmigrated
            // file. Close both the declared store and the one the gate maps the target to;
            // HCHalt does not clear this and HCGate applies it on every boot.
            HCRegClose(step.HCStore(), why);
            HCRegClose(HCStoreOfTarget(step.HCTarget()), why);
            return false;
        }
        s_Steps.Insert(step);
        return true;
    }

    protected static void HCRegClose(string store, string why)
    {
        if (store != "world" && store != "escalation" && store != "groups") { return; }
        if (s_RegStores.Find(store) >= 0) { return; }
        s_RegStores.Insert(store);
        s_RegReasons.Insert(why);
    }

    // Store the recovery gate maps this path to. The gate matches case-sensitively but the
    // profile filesystem may not, so a path that maps differently once case-folded still names a
    // store file; report the store in that case too.
    protected static string HCStoreOfTarget(string target)
    {
        string store = HCRecoveryGate.HCStoreFor(target);
        if (store != "") { return store; }
        string folded = target;
        folded.ToLower();
        if (folded.IndexOf("$profile:hollowcountry/groups/state/") == 0) { return "groups"; }
        if (folded.IndexOf("$profile:hollowcountry/world.json") == 0) { return "world"; }
        if (folded.IndexOf("$profile:hollowcountry/escalation.json") == 0) { return "escalation"; }
        return "";
    }
    // Returns "" when the step may join the registry, "already_registered" when this exact id on
    // this target is already in it (a no-op), otherwise a refusal token. One step per target
    // (case-folded): two steps on one file cannot chain (the first would see the second's output
    // as NEWER).
    protected static string HCRegistrationWhy(HCMigrationStep step, array<ref HCMigrationStep> registered)
    {
        string why = HCStepInvalid(step);
        if (why != "") { return why; }
        string id = step.HCId();
        string target = step.HCTarget();
        string foldedTarget = target;
        foldedTarget.ToLower();
        string knownTarget;
        foreach (HCMigrationStep known : registered)
        {
            knownTarget = known.HCTarget();
            knownTarget.ToLower();
            if (known.HCId() == id && knownTarget == foldedTarget) { return "already_registered"; }
            if (known.HCId() == id) { return "duplicate_id"; }
            if (knownTarget == foldedTarget) { return "duplicate_target"; }
        }
        return "";
    }

    // Called once per boot by HCPersistenceDisposition.HCLoad after the recovery gate is
    // admitted and before any store module opens its file. Bounded by a step cap and a time
    // budget; steps left over are deferred to later ticks and their stores refuse this boot.
    static void HCBoot(bool enableWorld)
    {
        HCHalt();
        s_WorldEnabled = enableWorld;
        if (!s_BuiltinsRegistered)
        {
            s_BuiltinsRegistered = true;
            HCBuiltins();
        }
        if (!s_SelfTested)
        {
            s_SelfTested = true;
            HCSelfTest();
        }
        if (s_Steps.Count() < 1)
        {
            if (s_RegRefused < 1) { Print("[HC Migrate] id=runner action=skipped reason=no_registered_migrations"); }
            else { HCSummary(); }
            return;
        }
        if (!s_SelfTestPassed)
        {
            // The runner's own IO path is not proven on this host: no step may touch a file.
            HCRefuseAll("selftest_failed");
            HCSummary();
            return;
        }
        s_Queue.Clear();
        foreach (HCMigrationStep step : s_Steps)
        {
            // No store gate exists for store "": deferral would let its file be used unmigrated.
            if (step.HCStore() == "") { HCRunOne(step); }
            else { s_Queue.Insert(step); }
        }
        s_Budget.HCReset(HCMigrationRunner.HC_BOOT_STEP_CAP, HCMigrationRunner.HC_BOOT_BUDGET_MS);
        while (s_Next < s_Queue.Count() && s_Budget.HCContinue())
        {
            HCRunOne(s_Queue.Get(s_Next));
            s_Next++;
        }
        if (s_Next < s_Queue.Count())
        {
            int index = s_Next;
            while (index < s_Queue.Count())
            {
                HCMigrationStep deferred = s_Queue.Get(index);
                HCBlock(deferred.HCStore(), "deferred_budget");
                HCReceipt(deferred.HCId(), HCMigrationRunner.RESULT_SKIPPED, "deferred_budget");
                index++;
            }
            HCSchedule(HCMigrationRunner.HC_TICK_INTERVAL_MS);
            return;
        }
        HCSummary();
    }

    // Refuse, for this boot only, every store whose migration refused or is deferred.
    // Files stay exactly as they are; the gate reports through the shared quarantine line.
    static void HCGate()
    {
        for (int i = 0; i < s_RegStores.Count(); i++)
        {
            HCRecoveryGate.HCRefuse(s_RegStores.Get(i), "migration_" + s_RegReasons.Get(i));
        }
        if (s_BlockWorld != "") { HCRecoveryGate.HCRefuse("world", "migration_" + s_BlockWorld); }
        if (s_BlockEscalation != "") { HCRecoveryGate.HCRefuse("escalation", "migration_" + s_BlockEscalation); }
        if (s_BlockGroups != "") { HCRecoveryGate.HCRefuse("groups", "migration_" + s_BlockGroups); }
    }

    // Cancel continuation and clear per-boot state; the registry itself is kept.
    static void HCHalt()
    {
        if (s_Scheduled && GetGame())
        {
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCTick);
        }
        s_Scheduled = false;
        // A deferred step stopped mid-way leaves a state the next boot classifies, like a crash.
        if (s_Job) { s_Job.HCAbort(); }
        s_Job = null;
        s_JobStep = null;
        s_Next = 0;
        s_Applied = 0;
        s_Skipped = 0;
        s_Refused = 0;
        s_BlockWorld = "";
        s_BlockEscalation = "";
        s_BlockGroups = "";
    }

    protected static void HCSchedule(int delayMs)
    {
        if (s_Scheduled || !GetGame()) { return; }
        s_Scheduled = true;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCTick, delayMs, false);
    }

    // Deferred steps run as one HCMigrationJob at a time, ONE job.HCStep() per call: at most one
    // native file operation (a read or write chunk is at most 4 KiB), so no tick pays for a whole
    // step. The boot pass (HCRunStep) drives the same machine to completion instead.
    protected static void HCTick()
    {
        s_Scheduled = false;
        if (!s_Job && !HCTickBegin()) { return; }
        int status = s_Job.HCStep();
        if (status == HCMigrationJob.STEP_MORE)
        {
            HCSchedule(HCMigrationRunner.HC_STEP_INTERVAL_MS);
            return;
        }
        HCTickEnd();
    }

    // Pure: takes the next queued step that needs file work. Steps that refuse before any file is
    // touched (world disabled, malformed) are recorded here. False when the queue is finished.
    protected static bool HCTickBegin()
    {
        while (s_Next < s_Queue.Count())
        {
            HCMigrationStep step = s_Queue.Get(s_Next);
            string invalid = HCStepInvalid(step);
            if (HCWorldSkips(step))
            {
                HCRecord(step, HCMigrationRunner.RESULT_SKIPPED, "world_disabled");
                s_Next++;
            }
            else if (invalid != "")
            {
                HCRecord(step, HCMigrationRunner.RESULT_REFUSED, invalid);
                s_Next++;
            }
            else
            {
                s_Job = new HCMigrationJob;
                s_Job.HCBegin(step);
                s_Job.HCSetInterleaved();
                s_JobStep = step;
                return true;
            }
        }
        HCSummary();
        return false;
    }

    // Pure: books the finished job and schedules the next queued step.
    protected static void HCTickEnd()
    {
        HCMigrationStep step = s_JobStep;
        HCNoteJob(step, s_Job);
        HCRecord(step, s_Job.HCResult(), s_Job.HCReason());
        s_Job = null;
        s_JobStep = null;
        s_Next++;
        if (s_Next < s_Queue.Count())
        {
            HCSchedule(HCMigrationRunner.HC_STEP_INTERVAL_MS);
            return;
        }
        HCSummary();
    }

    protected static void HCSummary()
    {
        int refused = s_Refused + s_RegRefused;
        Print("[HC Migrate] id=runner action=skipped reason=summary applied=" + s_Applied.ToString() + " skipped=" + s_Skipped.ToString() + " refused=" + refused.ToString());
    }

    // Refuse every registered step without touching a file and close every store it gates.
    protected static void HCRefuseAll(string reason)
    {
        foreach (HCMigrationStep step : s_Steps)
        {
            HCBlock(step.HCStore(), reason);
            s_Refused++;
            HCReceipt(step.HCId(), HCMigrationRunner.RESULT_REFUSED, reason);
        }
    }

    protected static void HCBlock(string store, string reason)
    {
        if (store == "world" && s_BlockWorld == "") { s_BlockWorld = reason; }
        if (store == "escalation" && s_BlockEscalation == "") { s_BlockEscalation = reason; }
        if (store == "groups" && s_BlockGroups == "") { s_BlockGroups = reason; }
    }

    protected static void HCReceipt(string id, int result, string reason)
    {
        string action = "refused";
        if (result == HCMigrationRunner.RESULT_APPLIED) { action = "applied"; }
        if (result == HCMigrationRunner.RESULT_SKIPPED) { action = "skipped"; }
        Print("[HC Migrate] id=" + id + " action=" + action + " reason=" + reason);
    }

    // True when the step's store is switched off with the world module, so it must not touch files.
    protected static bool HCWorldSkips(HCMigrationStep step)
    {
        string store = step.HCStore();
        return !s_WorldEnabled && (store == "world" || store == "escalation");
    }

    protected static void HCRunOne(HCMigrationStep step)
    {
        string reason;
        int result;
        if (HCWorldSkips(step))
        {
            result = HCMigrationRunner.RESULT_SKIPPED;
            reason = "world_disabled";
        }
        else
        {
            result = HCRunStep(step, reason);
        }
        HCRecord(step, result, reason);
    }

    protected static void HCRecord(HCMigrationStep step, int result, string reason)
    {
        HCCount(step.HCStore(), result, reason);
        HCReceipt(step.HCId(), result, reason);
    }

    // The target is committed and verified, but a scratch image that cannot be deleted leaves the
    // step unfinished: close the store for this boot. The next boot sees a CURRENT target with an
    // identical scratch image and tries to remove it again; if that also fails it refuses as
    // current_pending_cleanup_failed (store closed) until the file is removed.
    protected static void HCNoteJob(HCMigrationStep step, HCMigrationJob job)
    {
        if (!job.HCPendingDeleteFailed()) { return; }
        HCBlock(step.HCStore(), "pending_delete_failed");
        Print("[HC Migrate] id=runner action=skipped reason=pending_delete_failed");
    }

    // Per-boot counters; a refusal (including a failed scratch cleanup) closes the step's store.
    protected static void HCCount(string store, int result, string reason)
    {
        if (result == HCMigrationRunner.RESULT_APPLIED) { s_Applied++; }
        if (result == HCMigrationRunner.RESULT_SKIPPED) { s_Skipped++; }
        if (result == HCMigrationRunner.RESULT_REFUSED)
        {
            s_Refused++;
            HCBlock(store, reason);
        }
    }

    // Returns "" when the step is well formed, otherwise a refusal token.
    static string HCStepInvalid(HCMigrationStep step)
    {
        string id = step.HCId();
        string target = step.HCTarget();
        string store = step.HCStore();
        if (id.Length() < 1 || id.Length() > 48) { return "step_invalid_id"; }
        string allowed = "abcdefghijklmnopqrstuvwxyz0123456789-";
        for (int i = 0; i < id.Length(); i++)
        {
            if (allowed.IndexOf(id.Substring(i, 1)) < 0) { return "step_invalid_id"; }
        }
        string prefix = HCMigrationRunner.HC_PREFIX;
        if (target.Length() <= prefix.Length() || target.Length() > 160 || target.IndexOf(prefix) != 0) { return "step_invalid_target"; }
        if (target.IndexOf("..") >= 0 || target.IndexOf("\\") >= 0 || target.IndexOf("//") >= 0 || target.IndexOf("/./") >= 0) { return "step_invalid_target"; }
        if (target.Substring(target.Length() - 2, 2) == "/." || target.Substring(target.Length() - 1, 1) == "/") { return "step_invalid_target"; }
        if (store != "" && store != "world" && store != "escalation" && store != "groups") { return "step_invalid_store"; }
        // The declared store must be the one the recovery gate maps this file to: a store file
        // declared ungated, or gated by the wrong store, would be migrated while it stays open.
        if (store != HCStoreOfTarget(target)) { return "step_invalid_store"; }
        if (step.HCLimit() < 1 || step.HCLimit() > HCGroupIO.HC_RAW_READ_CAP) { return "step_invalid_limit"; }
        return "";
    }

    // True when part is a prefix of whole (an empty part is a prefix of everything).
    static bool HCHasPrefix(string whole, string part)
    {
        int count = part.Length();
        if (count > whole.Length()) { return false; }
        if (count < 1) { return true; }
        return whole.Substring(0, count) == part;
    }

    static string HCPendingPath(string target, string id) { return target + ".mig-" + id + ".tmp"; }

    static string HCBackupSuffix(string id, int slot)
    {
        string suffix = ".pre-" + id + ".bak";
        if (slot > 1) { suffix = suffix + slot.ToString(); }
        return suffix;
    }

    static string HCBackupPath(string target, string id, int slot) { return target + HCBackupSuffix(id, slot); }

    // Classify and, if needed, repair one step. Pure of receipts; the caller prints them.
    // Synchronous driver of the same HCMigrationJob the tick drives one operation at a time:
    // used by the boot pass (stores open right after, so their migration must be settled) and by
    // the self-test. The guard bounds a machine that never finishes; a stopped machine is the
    // same on-disk state as a crash at that point and the next boot repairs it.
    static int HCRunStep(HCMigrationStep step, out string reason)
    {
        reason = HCStepInvalid(step);
        if (reason != "") { return HCMigrationRunner.RESULT_REFUSED; }
        HCMigrationJob job = new HCMigrationJob;
        job.HCBegin(step);
        int status = HCMigrationJob.STEP_MORE;
        int guard = 0;
        while (status == HCMigrationJob.STEP_MORE && guard < HCMigrationJob.HC_MAX_STEPS)
        {
            status = job.HCStep();
            guard = guard + 1;
        }
        if (status == HCMigrationJob.STEP_MORE)
        {
            job.HCAbort();
            reason = "step_guard_exhausted";
            return HCMigrationRunner.RESULT_REFUSED;
        }
        HCNoteJob(step, job);
        reason = job.HCReason();
        return job.HCResult();
    }

    // Exercises the real IO path on scratch files once per script lifetime: apply, idempotent
    // rerun, stale scratch, torn commit, missing target, newer-schema refusal, an
    // unclassifiable file, scratch conflicts, an unreadable target and duplicate registration.
    // Touches no store file and no registry. Prints one [HC SelfTest] line.
    protected static void HCSelfTest()
    {
        string detail = "ok";
        bool passed = false;
        if (GetGame() && GetGame().IsServer()) { passed = HCSelfTestCases(detail); }
        else { detail = "server_required"; }
        HCProbeClear();
        s_SelfTestPassed = passed;
        Print("[HC SelfTest] name=migration_runner pass=" + passed.ToString() + " detail=" + detail);
    }

    protected static void HCProbeClear()
    {
        HCMigrationProbeStep probe = new HCMigrationProbeStep;
        string target = HCMigrationProbeStep.PATH;
        HCProbeDelete(target);
        HCProbeDelete(HCPendingPath(target, probe.HCId()));
        HCProbeDelete(HCBackupPath(target, probe.HCId(), 1));
        HCProbeDelete(HCBackupPath(target, probe.HCId(), 2));
        HCProbeDelete(HCMigrationProbeStep.STORE_PATH);
        HCProbeDelete(HCPendingPath(HCMigrationProbeStep.STORE_PATH, probe.HCId()));
        HCProbeDelete(HCBackupPath(HCMigrationProbeStep.STORE_PATH, probe.HCId(), 1));
    }

    protected static void HCProbeDelete(string path)
    {
        if (FileExist(path)) { DeleteFile(path); }
    }

    protected static bool HCProbeIs(string path, string expected)
    {
        string text;
        return HCGroupIO.HCReadRaw(path, 256, text) && text == expected;
    }

    protected static bool HCProbePut(string path, string text)
    {
        return HCPersistenceDisposition.HCWriteRawNew(path, text, 256);
    }

    // A zero-byte scratch file (HCWriteRawNew refuses empty text). EnSystem.c:417/443 OpenFile/CloseFile.
    protected static bool HCProbeEmpty(string path)
    {
        if (FileExist(path)) { return false; }
        FileHandle handle = OpenFile(path, FileMode.WRITE);
        if (!handle) { return false; }
        CloseFile(handle);
        return FileExist(path);
    }

    // Runs one refused step through HCRunOne and checks the escalation store is closed and the
    // per-boot counters and blocks are restored afterwards (the self-test is not a real step run).
    protected static bool HCSelfTestStoreClose(HCMigrationProbeStep gated, out string detail)
    {
        string savedBlock = s_BlockEscalation;
        bool savedWorld = s_WorldEnabled;
        int savedApplied = s_Applied;
        int savedSkipped = s_Skipped;
        int savedRefused = s_Refused;
        string storeTarget = HCMigrationProbeStep.STORE_PATH;
        string storePending = HCPendingPath(storeTarget, gated.HCId());
        gated.HCSetTarget(storeTarget);
        gated.HCSetStore("escalation");
        s_WorldEnabled = true;
        s_BlockEscalation = "";
        bool closed = false;
        string reason;
        int result;
        bool setup = HCProbePut(storeTarget, "probe-v2:alpha;") && HCProbePut(storePending, "probe-v2:beta;");
        if (setup)
        {
            result = HCRunStep(gated, reason);
            HCCount(gated.HCStore(), result, reason);
            closed = s_BlockEscalation == "pending_conflicts_current" && s_Refused == savedRefused + 1;
        }
        s_BlockEscalation = savedBlock;
        s_WorldEnabled = savedWorld;
        s_Applied = savedApplied;
        s_Skipped = savedSkipped;
        s_Refused = savedRefused;
        HCProbeDelete(storeTarget);
        HCProbeDelete(storePending);
        if (!setup) { detail = "setup_storeclose"; return false; }
        if (!closed) { detail = "storeclose_refused_not_blocked"; return false; }
        return true;
    }

    // Stops a fresh migration after its cut-th file-changing operation (the machine's state is
    // only the files, so an abort is a crash), then runs a new machine: every cut must converge on
    // the migrated target with no scratch image left. Cuts end when the machine finishes first.
    protected static bool HCSelfTestCuts(HCMigrationProbeStep probe, out string detail)
    {
        string target = HCMigrationProbeStep.PATH;
        string pending = HCPendingPath(target, probe.HCId());
        string reason;
        int result;
        for (int cut = 1; cut < 32; cut++)
        {
            HCProbeClear();
            if (!HCProbePut(target, "probe-v1:alpha;")) { detail = "setup_cut"; return false; }
            HCMigrationJob job = new HCMigrationJob;
            job.HCBegin(probe);
            job.HCSetInterleaved();
            int status = HCMigrationJob.STEP_MORE;
            int mutations = 0;
            int guard = 0;
            while (status == HCMigrationJob.STEP_MORE && mutations < cut && guard < HCMigrationJob.HC_MAX_STEPS)
            {
                status = job.HCStep();
                if (job.HCMutated()) { mutations = mutations + 1; }
                guard = guard + 1;
            }
            if (status != HCMigrationJob.STEP_MORE) { return true; }
            job.HCAbort();
            result = HCRunStep(probe, reason);
            if ((result != HCMigrationRunner.RESULT_APPLIED && result != HCMigrationRunner.RESULT_SKIPPED) || !HCProbeIs(target, "probe-v2:alpha;") || FileExist(pending))
            {
                detail = "cut_" + cut.ToString() + "_" + reason;
                return false;
            }
        }
        detail = "cut_unbounded";
        return false;
    }

    // A tick-driven job whose target is modified after classification (here: after the backup
    // copy) must refuse before deleting it and leave the new target untouched; the next run
    // proves the scratch image from the backup, discards it and migrates the new text.
    protected static bool HCSelfTestChanged(HCMigrationProbeStep probe, out string detail)
    {
        string target = HCMigrationProbeStep.PATH;
        string pending = HCPendingPath(target, probe.HCId());
        string reason;
        HCProbeClear();
        if (!HCProbePut(target, "probe-v1:alpha;")) { detail = "setup_changed"; return false; }
        HCMigrationJob job = new HCMigrationJob;
        job.HCBegin(probe);
        job.HCSetInterleaved();
        int status = HCMigrationJob.STEP_MORE;
        int mutations = 0;
        int guard = 0;
        while (status == HCMigrationJob.STEP_MORE && mutations < 1 && guard < HCMigrationJob.HC_MAX_STEPS)
        {
            status = job.HCStep();
            if (job.HCMutated()) { mutations = mutations + 1; }
            guard = guard + 1;
        }
        if (status != HCMigrationJob.STEP_MORE) { detail = "changed_early"; return false; }
        HCProbeDelete(target);
        if (!HCProbePut(target, "probe-v1:gamma;")) { detail = "setup_changed_put"; return false; }
        guard = 0;
        while (status == HCMigrationJob.STEP_MORE && guard < HCMigrationJob.HC_MAX_STEPS)
        {
            status = job.HCStep();
            guard = guard + 1;
        }
        if (status == HCMigrationJob.STEP_MORE) { job.HCAbort(); detail = "changed_unfinished"; return false; }
        if (job.HCResult() != HCMigrationRunner.RESULT_REFUSED || job.HCReason() != "target_changed" || !HCProbeIs(target, "probe-v1:gamma;") || !HCProbeIs(pending, "probe-v2:alpha;")) { detail = "changed_" + job.HCReason(); return false; }
        int result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_APPLIED || !HCProbeIs(target, "probe-v2:gamma;") || FileExist(pending)) { detail = "changed_rerun_" + reason; return false; }
        return true;
    }

    protected static bool HCSelfTestCases(out string detail)
    {
        HCMigrationProbeStep probe = new HCMigrationProbeStep;
        string target = HCMigrationProbeStep.PATH;
        string pending = HCPendingPath(target, probe.HCId());
        string backup = HCBackupPath(target, probe.HCId(), 1);
        string reason;
        int result;
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { detail = "profile_unavailable"; return false; }
        HCProbeClear();
        if (HCStepInvalid(probe) != "") { detail = "probe_step_invalid"; return false; }

        // Apply, then an idempotent rerun.
        if (!HCProbePut(target, "probe-v1:alpha;")) { detail = "setup_apply"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_APPLIED || reason != "migrated" || !HCProbeIs(target, "probe-v2:alpha;")) { detail = "apply_" + reason; return false; }
        if (!HCProbeIs(backup, "probe-v1:alpha;") || FileExist(pending)) { detail = "apply_backup_or_scratch"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_SKIPPED || reason != "current" || !HCProbeIs(target, "probe-v2:alpha;")) { detail = "rerun_" + reason; return false; }

        // Crash after backup and scratch, before the commit: recomputed, backup reused.
        HCProbeClear();
        if (!HCProbePut(target, "probe-v1:alpha;") || !HCProbePut(backup, "probe-v1:alpha;") || !HCProbePut(pending, "probe-v2:alpha;")) { detail = "setup_stale"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_APPLIED || !HCProbeIs(target, "probe-v2:alpha;") || FileExist(pending) || FileExist(HCBackupPath(target, probe.HCId(), 2))) { detail = "stale_" + reason; return false; }

        // Crash while copying the image over the target: a torn prefix.
        HCProbeClear();
        if (!HCProbePut(target, "probe-v2:al") || !HCProbePut(backup, "probe-v1:alpha;") || !HCProbePut(pending, "probe-v2:alpha;")) { detail = "setup_torn"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_APPLIED || reason != "recovered_torn_commit" || !HCProbeIs(target, "probe-v2:alpha;") || !HCProbeIs(backup, "probe-v1:alpha;")) { detail = "torn_" + reason; return false; }

        // Crash between deleting the target and copying the image.
        HCProbeClear();
        if (!HCProbePut(backup, "probe-v1:alpha;") || !HCProbePut(pending, "probe-v2:alpha;")) { detail = "setup_missing"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_APPLIED || reason != "recovered_missing_target" || !HCProbeIs(target, "probe-v2:alpha;")) { detail = "missing_" + reason; return false; }

        // A pending image without provenance never replaces anything.
        HCProbeClear();
        if (!HCProbePut(target, "probe-v2:al") || !HCProbePut(pending, "probe-v2:alpha;")) { detail = "setup_noprov"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_REFUSED || reason != "pending_provenance_missing" || !HCProbeIs(target, "probe-v2:al")) { detail = "noprov_" + reason; return false; }

        // A newer schema and an unclassifiable file are refused and left untouched.
        HCProbeClear();
        if (!HCProbePut(target, "probe-v3:alpha;")) { detail = "setup_newer"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_REFUSED || reason != "newer_schema" || !HCProbeIs(target, "probe-v3:alpha;") || FileExist(backup)) { detail = "newer_" + reason; return false; }
        HCProbeClear();
        if (!HCProbePut(target, "garbage")) { detail = "setup_unknown"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_REFUSED || reason != "target_schema_unknown" || !HCProbeIs(target, "garbage")) { detail = "unknown_" + reason; return false; }

        // A leftover scratch image beside a CURRENT target is deleted only when it is the same text.
        HCProbeClear();
        if (!HCProbePut(target, "probe-v2:alpha;") || !HCProbePut(pending, "probe-v2:alpha;")) { detail = "setup_same"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_SKIPPED || reason != "current_pending_removed" || FileExist(pending) || !HCProbeIs(target, "probe-v2:alpha;")) { detail = "same_" + reason; return false; }
        HCProbeClear();
        if (!HCProbePut(target, "probe-v2:alpha;") || !HCProbePut(pending, "probe-v2:beta;")) { detail = "setup_conflict"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_REFUSED || reason != "pending_conflicts_current" || !HCProbeIs(target, "probe-v2:alpha;") || !HCProbeIs(pending, "probe-v2:beta;")) { detail = "conflict_" + reason; return false; }

        // An empty scratch file beside a CURRENT target is removed, not refused.
        HCProbeClear();
        if (!HCProbePut(target, "probe-v2:alpha;") || !HCProbeEmpty(pending)) { detail = "setup_emptycur"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_SKIPPED || reason != "current_pending_removed" || FileExist(pending) || !HCProbeIs(target, "probe-v2:alpha;")) { detail = "emptycur_" + reason; return false; }

        // Beside an OLD target a foreign scratch image is kept and refused; a torn one is recomputed.
        HCProbeClear();
        if (!HCProbePut(target, "probe-v1:alpha;") || !HCProbePut(pending, "garbage")) { detail = "setup_oldforeign"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_REFUSED || reason != "pending_conflicts_old" || !HCProbeIs(target, "probe-v1:alpha;") || !HCProbeIs(pending, "garbage") || FileExist(backup)) { detail = "oldforeign_" + reason; return false; }
        HCProbeClear();
        if (!HCProbePut(target, "probe-v1:alpha;") || !HCProbePut(pending, "probe-v2:al")) { detail = "setup_oldtorn"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_APPLIED || !HCProbeIs(target, "probe-v2:alpha;") || FileExist(pending)) { detail = "oldtorn_" + reason; return false; }

        // A complete CURRENT scratch image beside an OLD target is not proof it is ours: it may be the
        // only newest copy (operator restored an older target). Without backup provenance it is kept.
        HCProbeClear();
        if (!HCProbePut(target, "probe-v1:alpha;") || !HCProbePut(pending, "probe-v2:beta;")) { detail = "setup_oldcurrent"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_REFUSED || reason != "pending_conflicts_old" || !HCProbeIs(target, "probe-v1:alpha;") || !HCProbeIs(pending, "probe-v2:beta;") || FileExist(backup)) { detail = "oldcurrent_" + reason; return false; }
        // The same image is deleted once a retained backup reproduces it (slot 1 holds another old text).
        HCProbeClear();
        if (!HCProbePut(target, "probe-v1:alpha;") || !HCProbePut(backup, "probe-v1:beta;") || !HCProbePut(pending, "probe-v2:beta;")) { detail = "setup_oldprov"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_APPLIED || !HCProbeIs(target, "probe-v2:alpha;") || FileExist(pending) || !HCProbeIs(backup, "probe-v1:beta;") || !HCProbeIs(HCBackupPath(target, probe.HCId(), 2), "probe-v1:alpha;")) { detail = "oldprov_" + reason; return false; }
        // A scratch image identical to the old target is a stray copy and is deleted.
        HCProbeClear();
        if (!HCProbePut(target, "probe-v1:alpha;") || !HCProbePut(pending, "probe-v1:alpha;")) { detail = "setup_oldsame"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_APPLIED || !HCProbeIs(target, "probe-v2:alpha;") || FileExist(pending)) { detail = "oldsame_" + reason; return false; }

        // A crash after every file-changing operation of the machine converges on the next run.
        if (!HCSelfTestCuts(probe, detail)) { return false; }
        if (!HCSelfTestChanged(probe, detail)) { return false; }

        // A torn-commit recovery only replaces a prefix of its own image, and never an unreadable target.
        HCProbeClear();
        if (!HCProbePut(target, "probe-v2:xx") || !HCProbePut(backup, "probe-v1:alpha;") || !HCProbePut(pending, "probe-v2:alpha;")) { detail = "setup_notprefix"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_REFUSED || reason != "target_schema_unknown" || !HCProbeIs(target, "probe-v2:xx") || !HCProbeIs(pending, "probe-v2:alpha;")) { detail = "notprefix_" + reason; return false; }
        HCProbeClear();
        string oversize = "probe-v2:";
        while (oversize.Length() <= 300) { oversize = oversize + "xxxxxxxxxx"; }
        if (!HCPersistenceDisposition.HCWriteRawNew(target, oversize, 1024) || !HCProbePut(backup, "probe-v1:alpha;") || !HCProbePut(pending, "probe-v2:alpha;")) { detail = "setup_unreadable"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_REFUSED || reason != "target_unreadable" || !FileExist(target) || !FileExist(pending)) { detail = "unreadable_" + reason; return false; }

        // Registration: one step per target (case-folded); the same id on the same target again is a
        // no-op, another id on the target or another target with the id is refused.
        array<ref HCMigrationStep> known = new array<ref HCMigrationStep>;
        known.Insert(probe);
        HCMigrationProbeStep alt = new HCMigrationProbeStep;
        alt.HCSetId("selftest-probe-alt");
        HCMigrationProbeStep twin = new HCMigrationProbeStep;
        HCMigrationProbeStep elsewhere = new HCMigrationProbeStep;
        elsewhere.HCSetTarget("$profile:HollowCountry/migrate-selftest-other.probe");
        HCMigrationProbeStep shouting = new HCMigrationProbeStep;
        shouting.HCSetId("selftest-probe-shout");
        shouting.HCSetTarget("$profile:HollowCountry/MIGRATE-SELFTEST.PROBE");
        array<ref HCMigrationStep> empty = new array<ref HCMigrationStep>;
        if (HCRegistrationWhy(alt, known) != "duplicate_target") { detail = "duplicate_target"; return false; }
        if (HCRegistrationWhy(shouting, known) != "duplicate_target") { detail = "duplicate_target_case"; return false; }
        if (HCRegistrationWhy(elsewhere, known) != "duplicate_id") { detail = "duplicate_id"; return false; }
        if (HCRegistrationWhy(twin, known) != "already_registered") { detail = "already_registered"; return false; }
        if (HCRegistrationWhy(alt, empty) != "") { detail = "register_clean"; return false; }

        // The declared store must equal the gate's store for the target, and path tricks are refused.
        HCMigrationProbeStep gated = new HCMigrationProbeStep;
        gated.HCSetTarget(HCMigrationProbeStep.STORE_PATH);
        if (HCStepInvalid(gated) != "step_invalid_store") { detail = "store_undeclared"; return false; }
        gated.HCSetStore("world");
        if (HCStepInvalid(gated) != "step_invalid_store") { detail = "store_wrong"; return false; }
        gated.HCSetStore("escalation");
        if (HCStepInvalid(gated) != "") { detail = "store_declared"; return false; }
        gated.HCSetTarget("$profile:HollowCountry/ESCALATION.JSON");
        if (HCStepInvalid(gated) != "") { detail = "store_declared_case"; return false; }
        gated.HCSetStore("");
        if (HCStepInvalid(gated) != "step_invalid_store") { detail = "store_undeclared_case"; return false; }
        HCMigrationProbeStep ungated = new HCMigrationProbeStep;
        ungated.HCSetStore("groups");
        if (HCStepInvalid(ungated) != "step_invalid_store") { detail = "store_on_plain_file"; return false; }
        ungated.HCSetStore("");
        ungated.HCSetTarget("$profile:HollowCountry/./migrate-selftest.probe");
        if (HCStepInvalid(ungated) != "step_invalid_target") { detail = "dot_segment"; return false; }
        ungated.HCSetTarget("$profile:HollowCountry/..");
        if (HCStepInvalid(ungated) != "step_invalid_target") { detail = "dotdot_segment"; return false; }

        // A refused step closes its real store: a conflicting scratch image on a gated target.
        if (!HCSelfTestStoreClose(gated, detail)) { return false; }
        detail = "cases_ok";
        return true;
    }
}
