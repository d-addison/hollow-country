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

// HCStagedStore boot fault injection. Drives the REAL writer (HCStagedSaveImage through
// HCStagedStore.HCStepSave), abandons it after k steps, drops it (its destructor closes handles),
// then runs the REAL recovery and requires "old image or new image, never neither".
// Native scripts-1.30.164289 EnSystem.c:397 FileExist, :417 OpenFile, :425 ReadFile, :443 CloseFile,
// :462 FPrint, :525 MakeDirectory, :528 DeleteFile. Only these fixed names under
// $profile:HollowCountry/selftest/ are ever touched: every helper refuses any other prefix, there is
// no directory enumeration and no recursive delete. Work is bounded per core tick: at most 32 units
// and 2 ms (HCWorkBudget), each unit at most ~16 native calls (a unit is one recovery or save step,
// one scratch write set, one check or one cleanup of the eight fixed names); HC_MAX_TICKS in total.
// Limits (stated, not hidden): a script cannot make a native call fail, so CopyFile/DeleteFile
// failures and a locked file are covered by review and a lead-only DayZDiag check, and a power cut
// (unflushed OS cache) is not simulated; there is no fsync to call. Source holds ASCII only, so
// multi-byte payloads are not exercised. ASCII images span 4095/4096/4097 and 8192/8193 bytes;
// a binary fixture exercises a NUL beyond the first chunk.
class HCStagedSelfTestCodec : HCStagedStoreCodec
{
    // Tiny image: rev=<n>;len=<n>;<payload> with len equal to the payload byte count.
    override bool HCValid(string text, out int revision)
    {
        revision = 0;
        if (text.IndexOf("rev=") != 0) { return false; }
        int first = text.IndexOf(";");
        if (first < 5) { return false; }
        int at = first + 1;
        if (text.IndexOfFrom(at, "len=") != at) { return false; }
        int second = text.IndexOfFrom(at, ";");
        if (second < at + 5) { return false; }
        int declared = text.Substring(at + 4, second - at - 4).ToInt();
        if (declared < 0 || text.Length() - second - 1 != declared) { return false; }
        revision = text.Substring(4, first - 4).ToInt();
        return true;
    }
}

class HCStagedStoreSelfTest
{
    static const string DIR = "$profile:HollowCountry/selftest";
    static const string FILE = "$profile:HollowCountry/selftest/store.txt";
    // Content ids of a scratch file.
    protected static const int HC_C_NONE = 0;
    protected static const int HC_C_OLD = 1;
    protected static const int HC_C_NEW = 2;
    protected static const int HC_C_TORN = 3;
    protected static const int HC_C_EMPTY = 4;
    protected static const int HC_C_BIG = 5;
    protected static const int HC_C_EXACT = 6;
    protected static const int HC_C_HUGE = 7;
    protected static const int HC_C_EITHER = 8;
    protected static const int HC_C_BELOW = 9;
    protected static const int HC_C_ABOVE = 10;
    protected static const int HC_C_LIMIT = 11;
    protected static const int HC_C_OVER = 12;
    protected static const int HC_C_CUT4096 = 13;
    protected static const int HC_C_CUT4097 = 14;
    protected static const int HC_C_BIG_NEW = 15;
    protected static const int HC_C_NUL = 16;
    protected static const int HC_C_PAYLOAD999 = 17;
    protected static const int HC_C_PAYLOAD1000 = 18;
    protected static const int HC_C_BIG_TORN = 19;
    // Case groups.
    protected static const int HC_G_TABLE = 0;
    protected static const int HC_G_ABANDON_RF = 1;
    protected static const int HC_G_ABANDON_PW = 2;
    protected static const int HC_G_TWICE_RF = 3;
    protected static const int HC_G_TWICE_PW = 4;
    protected static const int HC_G_MEMO = 5;
    protected static const int HC_G_ABANDON_BIG_RF = 6;
    protected static const int HC_G_ABANDON_BIG_PW = 7;
    protected static const int HC_G_DONE = 8;
    // Whole-run guard in core ticks. The 2 ms slice binds before the 32-unit cap on a real
    // disk: the v1-test-16 boot reached cases=144 of ~268 at ticks=601 (native_ms=1626, ~2.7 ms
    // per tick) and ended cause=tick_cap with no case failure. ~4.2 ticks per case puts the
    // full run near 1200 ticks; 2400 keeps 2x headroom. Per-tick cost is unchanged.
    protected static const int HC_MAX_TICKS = 2400;
    // Stages of one case.
    protected static const int HC_S_SETUP = 0;
    protected static const int HC_S_PRESAVE = 1;
    protected static const int HC_S_SAVE = 2;
    protected static const int HC_S_RECOVER_BEGIN = 3;
    protected static const int HC_S_RECOVER = 4;
    protected static const int HC_S_RESAVE = 5;
    protected static const int HC_S_CHECK = 7;
    protected static const int HC_S_CLEAN = 8;
    protected static const int HC_S_CORRUPT = 9;

    protected ref HCStagedSelfTestCodec m_Codec = new HCStagedSelfTestCodec;
    protected ref HCWorkBudget m_Budget = new HCWorkBudget;
    protected ref HCStagedStore m_Store;
    protected ref HCStagedStore m_Rec;
    protected string m_Old;
    protected string m_New;
    protected string m_Torn;
    protected string m_Big;
    protected string m_Exact;
    protected string m_Huge;
    protected string m_Below;
    protected string m_Above;
    protected string m_Limit;
    protected string m_Over;
    protected string m_Cut4096;
    protected string m_Cut4097;
    protected string m_BigNew;
    protected string m_BigTorn;
    protected string m_Payload999;
    protected string m_Payload1000;
    protected bool m_Active;
    protected bool m_Booted;
    protected int m_Ticks;
    protected int m_NativeTicks;
    protected int m_Group = -1;
    protected int m_Index;
    protected int m_K;
    protected int m_Stage;
    protected int m_Steps;
    protected int m_Round;
    protected bool m_Second;
    protected bool m_SaveDone;
    protected bool m_GroupEnd;
    protected bool m_Cleaned = true;
    protected bool m_FirstClean;
    // Case definition.
    protected string m_Name;
    protected int m_Pol;
    protected bool m_Fresh;
    protected int m_SetP;
    protected int m_SetT;
    protected int m_SetB;
    protected string m_ExpAction;
    protected int m_ExpPri;
    protected int m_TornMin;
    protected int m_TornMax;
    protected bool m_TmpLeft;
    protected bool m_CaseOk;
    protected string m_CaseWhy;
    // Totals.
    protected int m_Cases;
    protected int m_Failed;
    protected int m_Reported;
    protected string m_FirstFail = "none";
    protected int m_PointsRf;
    protected int m_PointsPw;
    protected int m_PointsBigRf;
    protected int m_PointsBigPw;
    protected int m_TwiceRf;
    protected int m_TwicePw;

    bool HCActive() { return m_Active; }

    // Starts the run. Returns false (and prints nothing) when it cannot start.
    bool HCBegin()
    {
        if (m_Active) { return false; }
        m_Old = HCMakeImage(1, 60);
        m_New = HCMakeImage(2, 80);
        m_Torn = m_New.Substring(0, m_New.Length() / 2);
        // Four-digit payload lengths have a 15-byte header: total = payload + 15.
        // Exact multiples of 4096 still require a final zero-byte read.
        m_Big = HCMakeImage(3, 4985);
        m_Exact = HCMakeImage(3, 4081);
        m_Huge = HCMakeImage(3, 9000);
        m_Below = HCMakeImage(3, 4080);
        m_Above = HCMakeImage(3, 4082);
        m_Limit = HCMakeImage(3, 8177);
        m_Over = HCMakeImage(3, 8178);
        m_Cut4096 = m_Big.Substring(0, 4096);
        m_Cut4097 = m_Big.Substring(0, 4097);
        m_BigNew = HCMakeImage(4, 4985);
        m_BigTorn = "rev=3;len=4984;" + m_Big.Substring(15, 4985);
        m_Payload999 = HCMakeImage(3, 999);
        m_Payload1000 = HCMakeImage(3, 1000);
        // Fail fixture construction before any store case can misdiagnose it.
        if (m_Old.Length() != 73 || m_New.Length() != 93 || m_Torn.Length() != 46 || m_Big.Length() != 5000 || m_Exact.Length() != 4096 || m_Huge.Length() != 9015) { return HCEnd("fixture_size_mismatch"); }
        if (m_Below.Length() != 4095 || m_Above.Length() != 4097 || m_Limit.Length() != 8192 || m_Over.Length() != 8193) { return HCEnd("fixture_size_mismatch"); }
        if (m_Cut4096.Length() != 4096 || m_Cut4097.Length() != 4097 || m_BigNew.Length() != 5000 || m_BigTorn.Length() != 5000 || m_Payload999.Length() != 1013 || m_Payload1000.Length() != 1015) { return HCEnd("fixture_size_mismatch"); }
        m_Active = true;
        m_Group = HC_G_TABLE;
        m_Index = -1;
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { return HCEnd("scratch_dir_failed"); }
        if (!FileExist(DIR) && !MakeDirectory(DIR)) { return HCEnd("scratch_dir_failed"); }
        // Binary fixture preflight uses the same fixed primary slot as its table case.
        m_Cleaned = false;
        if (!HCWriteNul(FILE) || !HCCheckNul(FILE))
        {
            HCRemoveAll();
            return HCEnd("fixture_size_mismatch");
        }
        // The first case starts from a clean scratch folder.
        m_Cleaned = false;
        m_Stage = HC_S_CLEAN;
        m_FirstClean = true;
        return true;
    }

    protected string HCFill(int length)
    {
        string unit = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnopqrstuvwxyz";
        string payload;
        int remaining = length;
        int n = unit.Length();
        while (remaining >= n)
        {
            payload = payload + unit;
            remaining = remaining - n;
        }
        if (remaining > 0) { payload = payload + unit.Substring(0, remaining); }
        return payload;
    }

    protected string HCMakeImage(int revision, int length)
    {
        return "rev=" + revision.ToString() + ";len=" + length.ToString() + ";" + HCFill(length);
    }

    protected bool HCScratch(string path)
    {
        return path.IndexOf(DIR + "/") == 0;
    }

    protected string HCTextOf(int id)
    {
        if (id == HC_C_OLD) { return m_Old; }
        if (id == HC_C_NEW) { return m_New; }
        if (id == HC_C_TORN) { return m_Torn; }
        if (id == HC_C_BIG) { return m_Big; }
        if (id == HC_C_EXACT) { return m_Exact; }
        if (id == HC_C_HUGE) { return m_Huge; }
        if (id == HC_C_BELOW) { return m_Below; }
        if (id == HC_C_ABOVE) { return m_Above; }
        if (id == HC_C_LIMIT) { return m_Limit; }
        if (id == HC_C_OVER) { return m_Over; }
        if (id == HC_C_CUT4096) { return m_Cut4096; }
        if (id == HC_C_CUT4097) { return m_Cut4097; }
        if (id == HC_C_BIG_NEW) { return m_BigNew; }
        if (id == HC_C_BIG_TORN) { return m_BigTorn; }
        if (id == HC_C_PAYLOAD999) { return m_Payload999; }
        if (id == HC_C_PAYLOAD1000) { return m_Payload1000; }
        return "";
    }

    protected bool HCWriteRaw(string path, string text)
    {
        if (!HCScratch(path)) { m_CaseWhy = "path_refused"; return false; }
        // Three chunks cover up to 12288 bytes (largest fixture: 9015); each transfer <=4096.
        if (text.Length() > 12288) { m_CaseWhy = "scratch_size_refused"; return false; }
        FileHandle handle = OpenFile(path, FileMode.WRITE);
        if (!handle) { m_CaseWhy = "scratch_open_failed"; return false; }
        int total = text.Length();
        if (total > 0) { FPrint(handle, text.Substring(0, Math.Min(total, 4096))); }
        if (total > 4096) { FPrint(handle, text.Substring(4096, Math.Min(total - 4096, 4096))); }
        if (total > 8192) { FPrint(handle, text.Substring(8192, total - 8192)); }
        CloseFile(handle);
        return true;
    }

    // Native scripts-1.30.164289: 1_Core/proto/Serializer.c:57 Write, :108 Open,
    // :110 Close; EnSystem.c:402 APPEND, :417 OpenFile, :425 ReadFile, :443 CloseFile,
    // :462 FPrint. A binary zero int puts four NUL bytes at offsets 4100..4103.
    // Raw preflight below checks the representation and total size, rather than assuming them.
    protected bool HCWriteNul(string path)
    {
        if (m_Big.Length() != 5000) { m_CaseWhy = "fixture_size_mismatch"; return false; }
        if (!HCWriteRaw(path, m_Big.Substring(0, 4100))) { return false; }
        FileSerializer binary = new FileSerializer;
        if (!binary.Open(path, FileMode.APPEND)) { m_CaseWhy = "scratch_open_failed"; return false; }
        bool wrote = binary.Write(0);
        binary.Close();
        if (!wrote) { m_CaseWhy = "scratch_write_failed"; return false; }
        FileHandle handle = OpenFile(path, FileMode.APPEND);
        if (!handle) { m_CaseWhy = "scratch_open_failed"; return false; }
        FPrint(handle, m_Big.Substring(4104, 896));
        CloseFile(handle);
        return true;
    }

    protected bool HCCheckNul(string path)
    {
        if (m_Big.Length() != 5000) { return false; }
        if (!HCScratch(path)) { return false; }
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) { return false; }
        string piece;
        bool exact = ReadFile(handle, piece, 4096) == 4096 && piece == m_Big.Substring(0, 4096);
        piece = "";
        if (ReadFile(handle, piece, 4) != 4 || piece != m_Big.Substring(4096, 4)) { exact = false; }
        piece = "";
        if (ReadFile(handle, piece, 4) != 4 || piece.Length() != 0) { exact = false; }
        piece = "";
        if (ReadFile(handle, piece, 896) != 896 || piece != m_Big.Substring(4104, 896)) { exact = false; }
        if (ReadFile(handle, piece, 1) != 0) { exact = false; }
        CloseFile(handle);
        return exact;
    }

    protected bool HCWriteContent(string path, int id)
    {
        if (id == HC_C_NONE) { return true; }
        if (id == HC_C_NUL) { return HCWriteNul(path); }
        if (id == HC_C_EMPTY) { return HCWriteRaw(path, ""); }
        return HCWriteRaw(path, HCTextOf(id));
    }

    // Reads a scratch file of at most 8 chunks; "" when it cannot be opened.
    protected string HCReadAll(string path)
    {
        string text;
        if (!HCScratch(path)) { return ""; }
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) { return ""; }
        for (int i = 0; i < 8; i++)
        {
            string piece;
            int count = ReadFile(handle, piece, 4096);
            if (count < 1) { break; }
            text = text + piece;
        }
        CloseFile(handle);
        return text;
    }

    protected bool HCDeleteScratch(string path)
    {
        if (!HCScratch(path)) { return false; }
        if (!FileExist(path)) { return true; }
        return DeleteFile(path);
    }

    protected void HCDef(string name, int policy, bool fresh, int primary, int tmp, int bak, string action, int expected, int tornMin, int tornMax, bool tmpLeft)
    {
        m_Name = name;
        m_Pol = policy;
        m_Fresh = fresh;
        m_SetP = primary;
        m_SetT = tmp;
        m_SetB = bak;
        m_ExpAction = action;
        m_ExpPri = expected;
        m_TornMin = tornMin;
        m_TornMax = tornMax;
        m_TmpLeft = tmpLeft;
    }

    // The fixed table. Policy 0 roll-forward, 1 primary-wins.
    protected bool HCLoadTable(int id)
    {
        int rf = 0;
        int pw = 1;
        int none = HC_C_NONE;
        int old = HC_C_OLD;
        int newer = HC_C_NEW;
        int torn = HC_C_TORN;
        if (id == 0) { HCDef("valid_only", rf, true, old, none, none, "none", old, 0, 0, false); return true; }
        if (id == 1) { HCDef("torn_tmp_rf", rf, true, old, torn, none, "discard_tmp", old, 1, 1, false); return true; }
        if (id == 2) { HCDef("torn_tmp_pw", pw, true, old, torn, none, "discard_tmp", old, 1, 1, false); return true; }
        if (id == 3) { HCDef("empty_tmp", rf, true, old, HC_C_EMPTY, none, "discard_tmp", old, 0, 0, false); return true; }
        if (id == 4) { HCDef("torn_primary_rf", rf, true, torn, newer, old, "promote_tmp", newer, 1, 1, false); return true; }
        if (id == 5) { HCDef("torn_primary_pw", pw, true, torn, newer, old, "restore_bak", old, 2, 2, false); return true; }
        if (id == 6) { HCDef("torn_bak", rf, true, old, none, torn, "none", old, 0, 0, false); return true; }
        if (id == 7) { HCDef("bak_restore_torn_primary", rf, true, torn, none, old, "restore_bak", old, 1, 1, false); return true; }
        if (id == 8) { HCDef("bak_restore_missing_primary", rf, true, none, none, old, "restore_bak", old, 0, 0, false); return true; }
        if (id == 9) { HCDef("stale_tmp", rf, true, newer, old, none, "discard_tmp", newer, 1, 1, false); return true; }
        if (id == 10) { HCDef("committed_tmp", rf, true, newer, newer, none, "discard_tmp", newer, 0, 0, false); return true; }
        if (id == 11) { HCDef("promote_rf", rf, true, old, newer, none, "promote_tmp", newer, 0, 0, false); return true; }
        if (id == 12) { HCDef("keep_primary_pw", pw, true, old, newer, none, "discard_tmp", old, 1, 1, false); return true; }
        if (id == 13) { HCDef("promote_missing_primary_rf", rf, true, none, newer, old, "promote_tmp", newer, 0, 0, false); return true; }
        if (id == 14) { HCDef("restore_missing_primary_pw", pw, true, none, newer, old, "restore_bak", old, 1, 1, false); return true; }
        if (id == 15) { HCDef("tmp_only_pw", pw, true, none, newer, none, "promote_tmp", newer, 0, 0, false); return true; }
        if (id == 16) { HCDef("big_promote", rf, true, old, HC_C_BIG, none, "promote_tmp", HC_C_BIG, 0, 0, false); return true; }
        if (id == 17) { HCDef("exact_4096_promote", rf, true, old, HC_C_EXACT, none, "promote_tmp", HC_C_EXACT, 0, 0, false); return true; }
        if (id == 18) { HCDef("big_valid_primary", rf, true, HC_C_BIG, none, none, "none", HC_C_BIG, 0, 0, false); return true; }
        if (id == 19) { HCDef("no_copy_fresh", rf, true, torn, none, torn, "start_empty", none, 2, 2, false); return true; }
        if (id == 20) { HCDef("no_copy_strict", rf, false, torn, none, torn, "quarantine", torn, 0, 0, false); return true; }
        if (id == 21) { HCDef("all_absent_fresh", rf, true, none, none, none, "start_empty", none, 0, 0, false); return true; }
        if (id == 22) { HCDef("all_absent_strict", rf, false, none, none, none, "start_empty", none, 0, 0, false); return true; }
        if (id == 23) { HCDef("tmp_only_torn_fresh", rf, true, none, torn, none, "start_empty", none, 1, 1, false); return true; }
        if (id == 24) { HCDef("tmp_only_torn_strict", rf, false, none, torn, none, "quarantine", none, 0, 0, true); return true; }
        if (id == 25) { HCDef("oversize_primary_fresh", rf, true, HC_C_HUGE, none, none, "start_empty", none, 1, 1, false); return true; }
        if (id == 26) { HCDef("oversize_tmp", rf, true, old, HC_C_HUGE, none, "discard_tmp", old, 1, 1, false); return true; }
        if (id == 27) { HCDef("below_4096_promote", rf, true, old, HC_C_BELOW, none, "promote_tmp", HC_C_BELOW, 0, 0, false); return true; }
        if (id == 28) { HCDef("above_4096_promote", rf, true, old, HC_C_ABOVE, none, "promote_tmp", HC_C_ABOVE, 0, 0, false); return true; }
        if (id == 29) { HCDef("limit_8192_promote", rf, true, old, HC_C_LIMIT, none, "promote_tmp", HC_C_LIMIT, 0, 0, false); return true; }
        if (id == 30) { HCDef("over_8193_discard", rf, true, old, HC_C_OVER, none, "discard_tmp", old, 1, 1, false); return true; }
        if (id == 31) { HCDef("big_cut_4096", rf, true, old, HC_C_CUT4096, none, "discard_tmp", old, 1, 1, false); return true; }
        if (id == 32) { HCDef("big_cut_4097", rf, true, old, HC_C_CUT4097, none, "discard_tmp", old, 1, 1, false); return true; }
        if (id == 33) { HCDef("big_primary_wins", pw, true, HC_C_BIG, HC_C_BIG_NEW, none, "discard_tmp", HC_C_BIG, 1, 1, false); return true; }
        if (id == 34) { HCDef("big_torn_primary_pw", pw, true, HC_C_BIG_TORN, HC_C_BIG, old, "restore_bak", old, 2, 2, false); return true; }
        if (id == 35) { HCDef("big_nul_primary", rf, true, HC_C_NUL, none, none, "start_empty", none, 1, 1, false); return true; }
        if (id == 36) { HCDef("payload_999_promote", rf, true, old, HC_C_PAYLOAD999, none, "promote_tmp", HC_C_PAYLOAD999, 0, 0, false); return true; }
        if (id == 37) { HCDef("payload_1000_promote", rf, true, old, HC_C_PAYLOAD1000, none, "promote_tmp", HC_C_PAYLOAD1000, 0, 0, false); return true; }
        return false;
    }

    // Defines the next case of the current group; false when the group is exhausted.
    protected bool HCLoadNext()
    {
        m_Steps = 0;
        m_Second = false;
        m_SaveDone = false;
        m_Round = 0;
        m_CaseOk = true;
        m_CaseWhy = "";
        m_Pol = 0;
        m_Fresh = true;
        m_ExpAction = "";
        m_TornMin = 0;
        m_TornMax = -1;
        m_TmpLeft = false;
        m_SetP = HC_C_NONE;
        m_SetT = HC_C_NONE;
        m_SetB = HC_C_NONE;
        m_Index++;
        if (m_Group == HC_G_TABLE) { return HCLoadTable(m_Index); }
        if (m_Index > 120 && !m_GroupEnd)
        {
            m_Failed++;
            if (m_FirstFail == "none") { m_FirstFail = "scan_runaway"; }
            return false;
        }
        if (m_GroupEnd) { return false; }
        m_K = m_Index;
        m_SetP = HC_C_OLD;
        m_ExpPri = HC_C_EITHER;
        m_Name = "abandon_k" + m_K.ToString();
        if (m_Group == HC_G_ABANDON_PW || m_Group == HC_G_ABANDON_BIG_PW) { m_Pol = 1; }
        if (m_Group == HC_G_ABANDON_BIG_RF) { m_Name = "abandon_big_rf_k" + m_K.ToString(); }
        if (m_Group == HC_G_ABANDON_BIG_PW) { m_Name = "abandon_big_pw_k" + m_K.ToString(); }
        if (m_Group == HC_G_TWICE_RF || m_Group == HC_G_TWICE_PW)
        {
            m_Name = "recover_twice_k" + m_K.ToString();
            m_SetP = HC_C_TORN;
            m_SetT = HC_C_NEW;
            m_SetB = HC_C_OLD;
            if (m_Group == HC_G_TWICE_PW) { m_Pol = 1; }
        }
        if (m_Group == HC_G_MEMO)
        {
            if (m_Index > 0) { return false; }
            m_Name = "memo_forget";
            m_ExpAction = "restore_bak";
            m_ExpPri = HC_C_NEW;
            m_TornMin = 1;
        }
        return true;
    }

    protected string HCSaveText()
    {
        if (m_Group == HC_G_ABANDON_BIG_RF || m_Group == HC_G_ABANDON_BIG_PW) { return m_Big; }
        return m_New;
    }

    protected HCStagedStore HCNewStore()
    {
        HCStagedStore store = new HCStagedStore(FILE, 8192, m_Pol, m_Codec, true, m_Fresh);
        store.HCSilence();
        return store;
    }

    protected void HCFailCase(string why)
    {
        if (m_CaseOk) { m_CaseWhy = why; }
        m_CaseOk = false;
    }

    // One unit of work: at most one recovery/save step, one write set, one check or one cleanup.
    protected void HCUnit()
    {
        if (m_Ticks > HC_MAX_TICKS)
        {
            // Tick cap: stop, remove the scratch files, report once.
            m_Failed++;
            HCRemoveAll();
            HCEnd("tick_cap");
            return;
        }
        if (m_Stage == HC_S_CLEAN) { HCUnitClean(); return; }
        if (m_Stage == HC_S_SETUP) { HCUnitSetup(); return; }
        if (m_Stage == HC_S_PRESAVE) { HCUnitPresave(); return; }
        if (m_Stage == HC_S_SAVE) { HCUnitSave(); return; }
        if (m_Stage == HC_S_CORRUPT)
        {
            // Change the primary behind the writer's back, as a damaged disk would.
            if (!HCWriteContent(FILE, HC_C_TORN)) { HCFailCase(m_CaseWhy); }
            m_Stage = HC_S_RECOVER_BEGIN;
            return;
        }
        if (m_Stage == HC_S_RECOVER_BEGIN) { HCUnitRecoverBegin(); return; }
        if (m_Stage == HC_S_RECOVER) { HCUnitRecover(); return; }
        if (m_Stage == HC_S_RESAVE)
        {
            if (!m_Store.HCBeginSave(m_New)) { HCFailCase("resave_refused"); m_Stage = HC_S_CHECK; return; }
            m_Round = 1;
            m_Stage = HC_S_SAVE;
            return;
        }
        HCUnitCheck();
    }

    protected void HCUnitSetup()
    {
        m_Cleaned = false;
        if (!HCWriteContent(FILE, m_SetP) || !HCWriteContent(FILE + ".tmp", m_SetT) || !HCWriteContent(FILE + ".bak", m_SetB)) { HCFailCase(m_CaseWhy); }
        if (m_Group == HC_G_TABLE) { m_Stage = HC_S_RECOVER_BEGIN; return; }
        if (m_Group == HC_G_TWICE_RF || m_Group == HC_G_TWICE_PW) { m_Stage = HC_S_RECOVER_BEGIN; return; }
        m_Stage = HC_S_PRESAVE;
    }

    protected void HCUnitPresave()
    {
        // A bounded synchronous drain of a clean scratch store (a handful of native calls).
        m_Store = HCNewStore();
        if (m_Store.HCDrainRecover() != HCSaveJob.STEP_DONE)
        {
            HCFailCase("presave_recover_" + m_Store.HCFailReason());
            m_GroupEnd = true;
            m_Stage = HC_S_CHECK;
            return;
        }
        if (!m_Store.HCBeginSave(HCSaveText()))
        {
            HCFailCase("presave_begin_refused");
            m_GroupEnd = true;
            m_Stage = HC_S_CHECK;
            return;
        }
        m_Steps = 0;
        m_Stage = HC_S_SAVE;
    }

    protected void HCUnitSave()
    {
        if (m_Group != HC_G_MEMO && m_Steps >= m_K)
        {
            // Abandon the writer here: dropping it closes any handle it holds.
            m_Store = null;
            m_Stage = HC_S_RECOVER_BEGIN;
            return;
        }
        int result = m_Store.HCStepSave();
        m_Steps++;
        if (result == HCSaveJob.STEP_FAILED)
        {
            HCFailCase("save_failed");
            m_GroupEnd = true;
            m_Stage = HC_S_CHECK;
            return;
        }
        if (result != HCSaveJob.STEP_DONE) { return; }
        m_SaveDone = true;
        if (m_Group != HC_G_MEMO)
        {
            m_Store = null;
            m_ExpPri = HC_C_NEW;
            if (m_Group == HC_G_ABANDON_BIG_RF || m_Group == HC_G_ABANDON_BIG_PW) { m_ExpPri = HC_C_BIG; }
            m_Stage = HC_S_RECOVER_BEGIN;
            return;
        }
        if (m_Round == 0) { m_Stage = HC_S_CORRUPT; }
        else { m_Stage = HC_S_CHECK; }
    }

    protected void HCUnitRecoverBegin()
    {
        m_Rec = HCNewStore();
        if (!m_Rec.HCBeginRecover()) { HCFailCase("recover_begin_refused"); m_Stage = HC_S_CHECK; return; }
        m_Steps = 0;
        m_Stage = HC_S_RECOVER;
    }

    protected void HCUnitRecover()
    {
        bool twice = m_Group == HC_G_TWICE_RF || m_Group == HC_G_TWICE_PW;
        if (twice && !m_Second && m_Steps >= m_K)
        {
            // Crash during recovery itself: drop it and recover again from whatever it left.
            m_Rec = null;
            m_Second = true;
            m_Stage = HC_S_RECOVER_BEGIN;
            return;
        }
        int result = m_Rec.HCStepRecover();
        m_Steps++;
        if (result == HCSaveJob.STEP_MORE) { return; }
        if (result == HCSaveJob.STEP_FAILED)
        {
            HCFailCase("recover_failed_" + m_Rec.HCFailReason());
            m_Stage = HC_S_CHECK;
            return;
        }
        if (twice && !m_Second)
        {
            // Recovery finished inside the allowed prefix: this was the last point of the scan.
            m_GroupEnd = true;
            m_Second = true;
        }
        if (m_Group == HC_G_MEMO) { m_Stage = HC_S_RESAVE; return; }
        m_Stage = HC_S_CHECK;
    }

    protected void HCUnitCheck()
    {
        m_Store = null;
        string primary;
        bool primaryExists = FileExist(FILE);
        if (primaryExists) { primary = HCReadAll(FILE); }
        string recoveredAction = "";
        if (m_Rec)
        {
            recoveredAction = m_Rec.HCRecoverAction();
            if (!m_Rec.HCRecoverDone() || m_Rec.HCFaulted()) { HCFailCase("recovery_not_done"); }
            if (m_ExpAction != "" && recoveredAction != m_ExpAction) { HCFailCase("action_" + recoveredAction); }
            if (m_Group != HC_G_TABLE && m_Rec.HCQuarantined()) { HCFailCase("quarantined"); }
            if (m_Group == HC_G_TABLE && primaryExists && recoveredAction != "quarantine" && m_Rec.HCRecovered() != primary) { HCFailCase("recovered_text_differs"); }
            if (m_Group == HC_G_TABLE && !primaryExists && m_Rec.HCRecovered() != "") { HCFailCase("recovered_without_primary"); }
        }
        else { HCFailCase("no_recovery"); }
        m_Rec = null;
        if (m_ExpPri == HC_C_NONE)
        {
            if (primaryExists) { HCFailCase("primary_present"); }
        }
        else if (!primaryExists) { HCFailCase("primary_missing"); }
        else if (m_ExpPri == HC_C_EITHER)
        {
            if (primary != m_Old && primary != HCSaveText()) { HCFailCase("neither_old_nor_new"); }
        }
        else if (primary != HCTextOf(m_ExpPri)) { HCFailCase("primary_text"); }
        if (FileExist(FILE + ".tmp") != m_TmpLeft) { HCFailCase("tmp_state"); }
        int torn = 0;
        for (int i = 0; i < 4; i++)
        {
            if (FileExist(FILE + ".torn." + i.ToString())) { torn++; }
        }
        if (torn < m_TornMin || (m_TornMax >= 0 && torn > m_TornMax)) { HCFailCase("torn_slots_" + torn.ToString()); }
        m_Stage = HC_S_CLEAN;
    }

    // All fixtures reuse these eight slots: primary, tmp, bak, torn.tmp and torn.0..3.
    // Eight fixed names, delete each that exists. Ends the case and picks the next one.
    protected bool HCRemoveAll()
    {
        m_Rec = null;
        m_Store = null;
        bool clean = true;
        if (!HCDeleteScratch(FILE)) { clean = false; }
        if (!HCDeleteScratch(FILE + ".tmp")) { clean = false; }
        if (!HCDeleteScratch(FILE + ".bak")) { clean = false; }
        if (!HCDeleteScratch(FILE + ".torn.tmp")) { clean = false; }
        for (int i = 0; i < 4; i++)
        {
            if (!HCDeleteScratch(FILE + ".torn." + i.ToString())) { clean = false; }
        }
        m_Cleaned = clean;
        return clean;
    }

    protected void HCUnitClean()
    {
        if (!HCRemoveAll()) { HCFailCase("cleanup_failed"); }
        if (m_FirstClean) { m_FirstClean = false; }
        else { HCCaseEnd(); }
        HCAdvance();
    }

    protected void HCCaseEnd()
    {
        m_Cases++;
        if (m_CaseOk) { return; }
        m_Failed++;
        if (m_FirstFail == "none") { m_FirstFail = m_Name; }
        if (m_Reported < 8)
        {
            m_Reported++;
            Print("[HC Store] selftest_case_failed name=" + m_Name + " why=" + m_CaseWhy);
        }
        // A failing abandon or recovery scan does not continue to the end.
        if (m_Group != HC_G_TABLE) { m_GroupEnd = true; }
    }

    // Records the scan length of a finished group and moves to the next case or group.
    protected void HCAdvance()
    {
        if (m_Group == HC_G_ABANDON_RF && m_SaveDone) { m_GroupEnd = true; m_PointsRf = m_K; }
        if (m_Group == HC_G_ABANDON_PW && m_SaveDone) { m_GroupEnd = true; m_PointsPw = m_K; }
        if (m_Group == HC_G_ABANDON_BIG_RF && m_SaveDone) { m_GroupEnd = true; m_PointsBigRf = m_K; }
        if (m_Group == HC_G_ABANDON_BIG_PW && m_SaveDone) { m_GroupEnd = true; m_PointsBigPw = m_K; }
        if (m_Group == HC_G_TWICE_RF && m_GroupEnd) { m_TwiceRf = m_K; }
        if (m_Group == HC_G_TWICE_PW && m_GroupEnd) { m_TwicePw = m_K; }
        if (HCLoadNext())
        {
            m_Stage = HC_S_SETUP;
            return;
        }
        m_Group++;
        m_Index = -1;
        m_GroupEnd = false;
        if (m_Group >= HC_G_DONE)
        {
            HCEnd("");
            return;
        }
        HCAdvance();
    }

    protected bool HCEnd(string cause)
    {
        m_Active = false;
        m_Store = null;
        m_Rec = null;
        bool passed = cause == "" && m_Failed == 0 && m_Cleaned;
        string detail = "cases=" + m_Cases.ToString() + " failed=" + m_Failed.ToString() + " first_fail=" + m_FirstFail;
        detail = detail + " abandon_points_rf=" + m_PointsRf.ToString() + " abandon_points_pw=" + m_PointsPw.ToString();
        detail = detail + " abandon_points_big_rf=" + m_PointsBigRf.ToString() + " abandon_points_big_pw=" + m_PointsBigPw.ToString();
        detail = detail + " recover_points_rf=" + m_TwiceRf.ToString() + " recover_points_pw=" + m_TwicePw.ToString();
        float nativeMs = 0;
        if (HCWorkBudget.HCTicksPerMs() > 0) { nativeMs = (float)m_NativeTicks / HCWorkBudget.HCTicksPerMs(); }
        detail = detail + " native_ms=" + nativeMs.ToString() + " ticks=" + m_Ticks.ToString();
        if (cause != "") { detail = detail + " cause=" + cause; }
        if (!m_Cleaned) { detail = detail + " cleanup_failed"; }
        HCCoreSelfTest.HCStagedDone(passed, detail);
        return false;
    }

    // #368 adds 11 table cases and two 35-case scans (k=0..34), total 268 cases.
    // Added work <=81*96=7776 HCUnit calls: each new case uses <=34 save steps,
    // <=62 recovery steps (table) or <=37 (abandon), plus <=7 driver units.
    // Table cases do not save. The fixed binary preflight is 17 native calls in HCBegin.
    // Per-tick cap stays 32 units / 2 ms; the whole-run guard is HC_MAX_TICKS (2400) ticks.
    // One bounded slice per core tick: at most 32 units and 2 ms.
    void HCRunSlice()
    {
        if (!m_Active) { return; }
        m_Ticks++;
        int started = TickCount(0);
        m_Budget.HCReset(32, 2.0);
        while (m_Active && m_Budget.HCContinue()) { HCUnit(); }
        int spent = TickCount(started);
        if (spent > 0) { m_NativeTicks = m_NativeTicks + spent; }
    }

    // Shutdown before the run ended: remove the scratch files, report once.
    void HCAbort()
    {
        if (!m_Active) { return; }
        m_Active = false;
        m_Failed++;
        HCRemoveAll();
        HCEnd("shutdown_before_completion");
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
    protected static ref HCStagedStoreSelfTest s_Staged;
    // 0 pending, 1 pass, 2 fail.
    protected static int s_StagedVerdict;

    static void Receipt(string name, bool passed, string detail)
    {
        Print("[HC SelfTest] name=" + name + " pass=" + passed.ToString() + " detail=" + detail);
    }

    static void HCStagedDone(bool passed, string detail)
    {
        s_StagedVerdict = 1;
        if (!passed) { s_StagedVerdict = 2; }
        Receipt("staged_store", passed, detail);
    }

    // True once the boot fault injection of the shared staged store has failed.
    static bool HCStagedStoreFailed() { return s_StagedVerdict == 2; }

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
        s_Staged = new HCStagedStoreSelfTest;
        s_Staged.HCBegin();
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
        PumpScheduler();
        if (!s_Staged) { return; }
        s_Staged.HCRunSlice();
        if (!s_Staged.HCActive()) { s_Staged = null; }
    }

    protected static void StopStaged()
    {
        if (!s_Staged) { return; }
        ref HCStagedStoreSelfTest staged = s_Staged;
        s_Staged = null;
        staged.HCAbort();
    }

    protected static void PumpScheduler()
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
        StopStaged();
        if (!s_Job) { return; }
        s_Scheduler = null;
        s_Job = null;
        bool clean = Cleanup();
        Receipt("savescheduler_step", false, "shutdown_before_completion cleanup=" + clean.ToString());
    }
}
