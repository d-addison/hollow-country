// W5-PERF: scalar clock update/tick; hourly watermark checkpoints use the
// shared HCSaveScheduler (<=one routine store/tick), flushed at stop.
// Scheduling native evidence: HCWorkBudget.c (Game.c:914).
// LC-T311; EnableWorld. Input pressures only; never changes population or loot.
// Native evidence: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 1_Core/proto/EnSystem.c:76,100 UTC (via HCGroupClock.Utc), :397 FileExist,
// :525 MakeDirectory, :528 DeleteFile, :531 CopyFile; HCGroupIO uses :417
// OpenFile, :425 ReadFile, :443 CloseFile, :462 FPrint for bounded readback.
// 3_Game/tools/JsonFileLoader.c:69 LoadData, :85 MakeData (via HCGroupJson);
// 3_Game/Global/Game.c:1120 IsServer, :934 GetWorldName; gameplay.c:636 GetGame;
// 1_Core/proto/EnMath.c:540 Clamp; EnConvert.c:30 int / :115 float ToString;
// 1_Core/proto/EnDebug.c:96 Print.
// IMPORTANT: installed scripts expose no rename primitive. The shared store
// below uses a verified temporary intent, backup, copy/readback, then intent
// removal. This is NOT atomic rename or fsync. The first open of a path per
// session recovers an interrupted save from whole images (HCRecoverInterrupted);
// Without a backup, a whole pending image repairs an absent/torn primary;
// a torn first pending image is archived only when the primary is absent.
class HCV2ThreatStore<Class T>
{
    // Paths already crash-checked this session. Only the first open recovers:
    // later opens may run while this session's own staged save holds .tmp.
    protected static ref map<string, bool> s_Recovered;

    static bool CanOpen(string path)
    {
        if (!HCRecoveryGate.HCAllowRead(path)) { return false; }
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) return false;
        if (!s_Recovered) { s_Recovered = new map<string, bool>; }
        if (!s_Recovered.Contains(path))
        {
            s_Recovered.Set(path, true);
            HCRecoverInterrupted(path);
        }
        if (FileExist(path + ".tmp")) return false;
        if (!FileExist(path) && FileExist(path + ".bak")) return false;
        return true;
    }

    // A whole image: bounded raw read, one {...} object, parseable as T. The
    // shape check runs first so a torn file never reaches the native parser.
    static bool HCWholeImage(string path)
    {
        if (!FileExist(path)) { return false; }
        if (!HCGroupIO.HCLooksWholeObject(path, HCGroupIO.HC_RAW_READ_CAP)) { return false; }
        string text;
        if (!HCGroupIO.HCReadRaw(path, HCGroupIO.HC_RAW_READ_CAP, text)) { return false; }
        T probe;
        string error;
        return JsonFileLoader<T>.LoadData(text, probe, error) && probe != null;
    }

    // Boot-only evidence copy keyed by content, not time. A crash after copy
    // but before delete reuses the same byte-verified archive on the next boot.
    // Hash/length name collisions refuse; equality, never the hash, admits reuse.
    static bool HCArchiveFirstPending(string path, int limit)
    {
        string original;
        if (!HCPersistenceDisposition.HCReadArchive(path, limit, original, true)) { return false; }
        string suffix = ".interrupted-first-" + original.Length().ToString() + "-" + original.Hash().ToString();
        if (!FileExist(path + suffix)) { return HCPersistenceDisposition.HCArchive(path, suffix, limit, true); }
        string archived;
        return HCPersistenceDisposition.HCReadArchive(path + suffix, limit, archived, true) && archived == original;
    }

    // Only an absent primary and absent backup admit retiring a torn first
    // pending image. Never discard a torn primary: it may hold committed state.
    static bool HCRetireFirstPending(string path, string pending, int limit)
    {
        if (FileExist(path) || FileExist(path + ".bak")) { return false; }
        if (!HCArchiveFirstPending(pending, limit)) { return false; }
        return DeleteFile(pending) && !FileExist(pending);
    }

    // Boot-only copy after caller verifies the pending image. Archive a torn
    // primary by content before touching it; retain pending until whole readback.
    static bool HCPromoteWholePending(string path, string pending, int limit)
    {
        string intended;
        if (!HCGroupIO.HCReadRaw(pending, limit, intended)) { return false; }
        if (FileExist(path))
        {
            if (!HCArchiveFirstPending(path, limit) || !DeleteFile(path)) { return false; }
        }
        if (!CopyFile(pending, path)) { return false; }
        string promoted;
        if (!HCGroupIO.HCReadRaw(path, limit, promoted) || promoted != intended) { return false; }
        return HCWholeImage(path);
    }

    // No backup decision table: whole pending + absent/torn primary -> promote
    // with whole readback; torn pending + absent primary -> archive once/empty;
    // both torn -> operator (never reset); whole primary -> primary wins.
    // Any existing backup keeps the verified-predecessor recovery below.
    static void HCRecoverInterrupted(string path)
    {
        string tmp = path + ".tmp";
        string bak = path + ".bak";
        bool hasTmp = FileExist(tmp);
        bool primaryWhole = HCWholeImage(path);
        if (!hasTmp && (primaryWhole || !FileExist(bak))) { return; }
        if (hasTmp && !primaryWhole && !FileExist(bak))
        {
            string firstAction = "left_for_operator";
            string firstReason = "no_whole_image";
            if (HCWholeImage(tmp))
            {
                firstReason = "pending_promotion_failed";
                if (HCPromoteWholePending(path, tmp, HCGroupIO.HC_RAW_READ_CAP))
                {
                    firstReason = "pending_clear_failed";
                    if (DeleteFile(tmp) && !FileExist(tmp))
                    {
                        firstAction = "promoted_whole_pending";
                        firstReason = "no_predecessor";
                    }
                }
            }
            else if (!FileExist(path))
            {
                firstReason = "first_pending_retirement_failed";
                if (HCRetireFirstPending(path, tmp, HCGroupIO.HC_RAW_READ_CAP))
                {
                    firstAction = "archived_first_pending";
                    firstReason = "no_predecessor";
                }
            }
            string firstName = path;
            int firstSlash = firstName.LastIndexOf("/");
            if (firstSlash >= 0) { firstName = firstName.Substring(firstSlash + 1, firstName.Length() - firstSlash - 1); }
            Print("[HC Store] crash_recovery file=" + firstName + " action=" + firstAction + " reason=" + firstReason + " runtime=PENDING");
            return;
        }
        string action = "left_for_operator";
        string reason = "no_verified_predecessor";
        string suffix = ".interrupted-" + HCGroupClock.Utc().ToString();
        bool pendingArchived = !hasTmp;
        if (hasTmp)
        {
            reason = "pending_unverified";
            if (HCWholeImage(tmp)) { reason = "pending_not_committed"; }
            pendingArchived = HCPersistenceDisposition.HCArchive(tmp, suffix, HCGroupIO.HC_RAW_READ_CAP, true);
            if (!pendingArchived) { reason = "pending_archive_failed"; }
        }
        bool recovered = primaryWhole;
        if (!primaryWhole && pendingArchived && HCWholeImage(bak))
        {
            string prior;
            string restored;
            if (HCGroupIO.HCReadRaw(bak, HCGroupIO.HC_RAW_READ_CAP, prior))
            {
                bool retained = true;
                if (FileExist(path))
                {
                    retained = HCPersistenceDisposition.HCArchive(path, suffix, HCGroupIO.HC_RAW_READ_CAP, true);
                    if (retained) { retained = DeleteFile(path); }
                }
                if (retained && CopyFile(bak, path))
                {
                    recovered = HCGroupIO.HCReadRaw(path, HCGroupIO.HC_RAW_READ_CAP, restored) && restored == prior;
                    if (recovered) { recovered = HCWholeImage(path); }
                }
            }
            if (recovered) { action = "restored_verified_backup"; }
            else { reason = "backup_restore_failed"; }
        }
        if (recovered && pendingArchived)
        {
            bool cleared = !hasTmp;
            if (hasTmp) { cleared = DeleteFile(tmp); }
            if (cleared)
            {
                if (primaryWhole) { action = "retained_verified_primary"; }
            }
            else { action = "left_for_operator"; reason = "pending_clear_failed"; }
        }
        string name = path;
        int slash = name.LastIndexOf("/");
        if (slash >= 0) { name = name.Substring(slash + 1, name.Length() - slash - 1); }
        Print("[HC Store] crash_recovery file=" + name + " action=" + action + " reason=" + reason + " runtime=PENDING");
    }

    static bool Load(string path, int limit, out T state)
    {
        return HCGroupJson<T>.Load(path, limit, state);
    }

    protected ref HCStagedSaveImage m_SaveImage = new HCStagedSaveImage;
    protected bool m_SaveFault;
    protected int m_SnapshotRevision;

    bool SaveInFlight() { return m_SaveImage.Active(); }
    bool FinishSave()
    {
        if (m_SaveFault) { return false; }
        if (!m_SaveImage.Finish()) { m_SaveFault = true; return false; }
        return true;
    }

    // Snapshot stage has no disk effects. Subsequent per-stage crash states are
    // documented in HCStagedSaveImage.HCStepImage; CanOpen/Load refusal is unchanged.
    // Disk stage boundaries: write_tmp/read_tmp retain old primary + intent;
    // copy_backup retains old primary/backup + intent; copy_primary/read_primary
    // retain new primary, old backup and intent; clear_intent admits new primary.
    int SaveStep(string path, T state, int limit, int revision = 0)
    {
        if (m_SaveFault) { return HCSaveJob.STEP_FAILED; }
        if (!m_SaveImage.Active())
        {
            HCSaveJob.HCOperation = "encode";
            string text;
            string error;
            if (!JsonFileLoader<T>.MakeData(state, text, error) || !m_SaveImage.Begin(path, text, limit))
            {
                m_SaveFault = true;
                return HCSaveJob.STEP_FAILED;
            }
            m_SnapshotRevision = revision;
            return HCSaveJob.STEP_MORE;
        }
        if (m_SaveImage.HCReadyToClearIntent() && revision != m_SnapshotRevision)
        {
            string refreshed;
            string refreshError;
            if (!JsonFileLoader<T>.MakeData(state, refreshed, refreshError) || !m_SaveImage.HCRefreshIntent(refreshed)) { m_SaveFault = true; return HCSaveJob.STEP_FAILED; }
            m_SnapshotRevision = revision;
            return HCSaveJob.STEP_MORE;
        }
        int result = m_SaveImage.HCStepImage();
        if (result == HCSaveJob.STEP_FAILED) { m_SaveFault = true; }
        return result;
    }

    static bool Save(string path, T state, int limit)
    {
        HCV2ThreatStore<T> writer = new HCV2ThreatStore<T>;
        int result = writer.SaveStep(path, state, limit);
        if (result == HCSaveJob.STEP_FAILED) { return false; }
        return writer.FinishSave();
    }

}

class HCEscalationState
{
    float InfectedWeek = 0.25;
    float InfectedFortnight = 0.55;
    float InfectedCap = 1.0;
    float RaidersWeek = 0.1;
    float RaidersFortnight = 0.35;
    float RaidersCap = 1.0;
    float ScarcityWeek = 0.15;
    float ScarcityFortnight = 0.4;
    float ScarcityCap = 1.0;
    int HorizonDays = 30;

    bool HCNormalize(string text)
    {
        bool invalid = false;
        if (!HCJsonFields.Has(text, "InfectedWeek")) { this.InfectedWeek = 0.25; }
        if (!(this.InfectedWeek >= 0 && this.InfectedWeek <= 1)) { this.InfectedWeek = 0.25; invalid = true; }
        if (!HCJsonFields.Has(text, "InfectedFortnight")) { this.InfectedFortnight = 0.55; }
        if (!(this.InfectedFortnight >= 0 && this.InfectedFortnight <= 1)) { this.InfectedFortnight = 0.55; invalid = true; }
        if (!HCJsonFields.Has(text, "InfectedCap")) { this.InfectedCap = 1.0; }
        if (!(this.InfectedCap >= 0 && this.InfectedCap <= 1)) { this.InfectedCap = 1.0; invalid = true; }
        if (!HCJsonFields.Has(text, "RaidersWeek")) { this.RaidersWeek = 0.1; }
        if (!(this.RaidersWeek >= 0 && this.RaidersWeek <= 1)) { this.RaidersWeek = 0.1; invalid = true; }
        if (!HCJsonFields.Has(text, "RaidersFortnight")) { this.RaidersFortnight = 0.35; }
        if (!(this.RaidersFortnight >= 0 && this.RaidersFortnight <= 1)) { this.RaidersFortnight = 0.35; invalid = true; }
        if (!HCJsonFields.Has(text, "RaidersCap")) { this.RaidersCap = 1.0; }
        if (!(this.RaidersCap >= 0 && this.RaidersCap <= 1)) { this.RaidersCap = 1.0; invalid = true; }
        if (!HCJsonFields.Has(text, "ScarcityWeek")) { this.ScarcityWeek = 0.15; }
        if (!(this.ScarcityWeek >= 0 && this.ScarcityWeek <= 1)) { this.ScarcityWeek = 0.15; invalid = true; }
        if (!HCJsonFields.Has(text, "ScarcityFortnight")) { this.ScarcityFortnight = 0.4; }
        if (!(this.ScarcityFortnight >= 0 && this.ScarcityFortnight <= 1)) { this.ScarcityFortnight = 0.4; invalid = true; }
        if (!HCJsonFields.Has(text, "ScarcityCap")) { this.ScarcityCap = 1.0; }
        if (!(this.ScarcityCap >= 0 && this.ScarcityCap <= 1)) { this.ScarcityCap = 1.0; invalid = true; }
        if (!HCJsonFields.Has(text, "HorizonDays")) { this.HorizonDays = 30; }
        if (!(this.HorizonDays >= 15 && this.HorizonDays <= 365)) { this.HorizonDays = 30; invalid = true; }
        return invalid;
    }

    int Version;
    string WorldName;
    int EpochUtc;
    int SavedUtc;
}

class HCEscalationClock : HCModule
{
    protected static HCEscalationClock s_Instance;
    protected ref HCV2ThreatStore<HCEscalationState> m_Writer = new HCV2ThreatStore<HCEscalationState>;
    protected ref HCEscalationState m_State;
    protected int m_NowUtc;
    protected int m_LogUtc;
    protected int m_LogDay = -1;
    protected bool m_Healthy;
    protected bool m_Stopping;
    protected float m_SaveStepTime = -1;
    protected ref HCEscalationSaveJob m_SaveJob;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;
    static const string PATH = "$profile:HollowCountry/escalation.json";

    override string GetName() { return "Escalation"; }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Operational; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableWorld; }

    static HCEscalationState HCParameters()
    {
        if (s_Instance && s_Instance.m_State) { return s_Instance.m_State; }
        HCEscalationState defaults = new HCEscalationState;
        return defaults;
    }

    // Authored piecewise knots at day 0 / 7 / 14 / 30; held at cap thereafter.
    static float Curve(int day, float week, float fortnight, float cap)
    {
        if (day <= 0) { return 0; }
        if (day <= 7) { return Math.Clamp(week * day / 7.0, 0, 1); }
        if (day <= 14) { return Math.Clamp(week + (fortnight - week) * (day - 7) / 7.0, 0, 1); }
        if (day <= HCEscalationClock.HCParameters().HorizonDays) { return Math.Clamp(fortnight + (cap - fortnight) * (day - 14) / (HCEscalationClock.HCParameters().HorizonDays - 14.0), 0, 1); }
        return Math.Clamp(cap, 0, 1);
    }

    static float PressureAtDay(string axis, int day)
    {
        if (axis == "infected") { return HCEscalationClock.Curve(day, HCEscalationClock.HCParameters().InfectedWeek, HCEscalationClock.HCParameters().InfectedFortnight, HCEscalationClock.HCParameters().InfectedCap); }
        if (axis == "raiders") { return HCEscalationClock.Curve(day, HCEscalationClock.HCParameters().RaidersWeek, HCEscalationClock.HCParameters().RaidersFortnight, HCEscalationClock.HCParameters().RaidersCap); }
        if (axis == "scarcity") { return HCEscalationClock.Curve(day, HCEscalationClock.HCParameters().ScarcityWeek, HCEscalationClock.HCParameters().ScarcityFortnight, HCEscalationClock.HCParameters().ScarcityCap); }
        return 0;
    }

    // Inactive/faulted clocks cannot accidentally admit a day-14 camp probe.
    static int Day()
    {
        if (!s_Instance || !s_Instance.m_Healthy) return 0;
        return (s_Instance.m_NowUtc - s_Instance.m_State.EpochUtc) / 86400;
    }

    // Public axis names: infected, raiders, scarcity. Unknown axes return zero.
    static float Pressure(string axis)
    {
        if (!s_Instance || !s_Instance.m_Healthy) return 0;
        return PressureAtDay(axis, Day());
    }

    protected void Fail(bool damaged = false)
    {
        m_Healthy = false;
        HCRecoveryGate.HCClose("escalation");
        if (damaged) { HCPersistenceDisposition.HCQuarantine("escalation", "escalation_schema_or_interrupted_pair"); }
        m_Operational.HCPublish("refused", "recovery_or_clock_fault");
        if (s_Instance == this) s_Instance = null;
        Print("[HollowCountry] V2 escalation disabled: UTC/schema/world/persistence fault; preserve escalation.json, .tmp and .bak");
    }

    protected bool Valid(int nowUtc)
    {
        if (!m_State || m_State.Version != 1 || m_State.WorldName != GetGame().GetWorldName()) return false;
        return m_State.EpochUtc > 0 && m_State.SavedUtc >= m_State.EpochUtc;
    }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings) || s_Instance) return;
        HCPersistenceDisposition.HCStartStore("escalation");
        if (!HCPersistenceDisposition.HCLoad(settings.EnableWorld) || !HCPersistenceDisposition.HCAdmitStore("escalation")) { Fail(); return; }
        Print(HCV2Admission.Line("Escalation", true, "none", true));
        m_NowUtc = HCGroupClock.Utc();
        if (m_NowUtc < 1) { Fail(); return; }
        if (FileExist(PATH + ".tmp") || (!FileExist(PATH) && FileExist(PATH + ".bak"))) { Fail(true); return; }
        if (!HCV2ThreatStore<HCEscalationState>.CanOpen(PATH)) { Fail(); return; }
        if (FileExist(PATH))
        {
            if (!HCV2ThreatStore<HCEscalationState>.Load(PATH, 2048, m_State) || !Valid(m_NowUtc)) { Fail(true); return; }
            if (m_NowUtc < m_State.SavedUtc) { Fail(); return; }
            if (FileExist(PATH + ".bak"))
            {
                HCEscalationState previous;
                if (!HCGroupJson<HCEscalationState>.Load(PATH + ".bak", 2048, previous) || !previous) { Fail(true); return; }
                if (previous.Version != 1 || previous.WorldName != m_State.WorldName || previous.EpochUtc < 1 || previous.SavedUtc < previous.EpochUtc || previous.SavedUtc > m_State.SavedUtc) { Fail(true); return; }
            }
        }
        else
        {
            m_State = new HCEscalationState;
            m_State.Version = 1;
            m_State.WorldName = GetGame().GetWorldName();
            m_State.EpochUtc = m_NowUtc;
            m_State.SavedUtc = m_NowUtc;
        }
        // Preserve epoch/watermark semantics; optional tuning is restored independently.
        string tuningText;
        if (FileExist(PATH))
        {
            if (!HCGroupIO.Read(PATH, 2048, tuningText)) { Fail(); return; }
            if (m_State.HCNormalize(tuningText)) { Print("[HC Config] HCEscalationState invalid_range defaults_restored runtime=PENDING"); }
        }
        m_Stopping = false;
        m_Healthy = true;
        m_Operational.HCPublish("ready", "files_validated_runtime_pending");
        s_Instance = this;
        m_SaveJob = new HCEscalationSaveJob;
        m_SaveJob.Owner = this;
        if (!FileExist(PATH)) { m_SaveJob.HCDirty = true; }
        HCSaveScheduler.HCRegister(m_SaveJob);
        Report();
    }

    protected void Report()
    {
        int day = Day();
        if (day == m_LogDay && m_NowUtc - m_LogUtc < 3600) return;
        m_LogDay = day;
        m_LogUtc = m_NowUtc;
        // Persist a UTC watermark on the same bounded hourly/day boundary.
        if (m_State.SavedUtc != m_NowUtc)
        {
            m_State.SavedUtc = m_NowUtc;
            HCModuleReadiness.HCUse("Escalation", "state_advanced");
            m_SaveJob.HCDirty = true;
        }
        float infected = Pressure("infected");
        float raiders = Pressure("raiders");
        Print("[HollowCountry] V2 escalation day=" + day.ToString() + " infected=" + infected.ToString() + " raiders=" + raiders.ToString());
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Healthy) return;
        if (!HCRecoveryGate.HCReady("escalation")) { Fail(); return; }
        int nowUtc = HCGroupClock.Utc();
        if (nowUtc < m_NowUtc) { Fail(); return; }
        m_NowUtc = nowUtc;
        HCReached.Mark("escalation.clock_step");
        Report();
    }

    bool HCFlushRoutine()
    {
        if (!m_Healthy || !HCRecoveryGate.HCReady("escalation")) { return false; }
        if (!m_Writer.FinishSave() || !HCV2ThreatStore<HCEscalationState>.Save(PATH, m_State, 2048)) { Fail(); return false; }
        return true;
    }

    int HCStepRoutine()
    {
        if (!m_Healthy || !HCRecoveryGate.HCReady("escalation")) { return HCSaveJob.STEP_FAILED; }
        float now = GetGame().GetTickTime();
        if (!m_Stopping && now == m_SaveStepTime) { return HCSaveJob.STEP_MORE; }
        m_SaveStepTime = now;
        // A day/hour watermark can advance while an older image is in flight.
        // Retain the existing SaveStep revision-refresh contract at commit.
        int result = m_Writer.SaveStep(PATH, m_State, 2048, m_State.SavedUtc);
        if (result == HCSaveJob.STEP_FAILED) { Fail(); }
        return result;
    }

    override void OnStop()
    {
        m_Stopping = true;
        if (m_Healthy)
        {
            if (m_SaveJob.HCInFlight && !HCSaveScheduler.HCFlush(m_SaveJob))
            {
                Fail();
                HCSaveScheduler.HCUnregister(m_SaveJob);
                HCPersistenceDisposition.HCStopStore("escalation");
                return;
            }
            int nowUtc = HCGroupClock.Utc();
            if (nowUtc < m_NowUtc) { Fail(); }
            else
            {
                if (nowUtc > m_State.SavedUtc)
                {
                    m_State.SavedUtc = nowUtc;
                    m_SaveJob.HCDirty = true;
                }
                HCSaveScheduler.HCFlush(m_SaveJob);
            }
        }
        HCSaveScheduler.HCUnregister(m_SaveJob);
        HCPersistenceDisposition.HCStopStore("escalation");
        m_Operational.HCPublish("off", "stopped");
        m_Healthy = false;
        if (s_Instance == this) { s_Instance = null; }
    }
}

class HCEscalationSaveJob : HCSaveJob
{
    override string HCName() { return "EscalationClock"; }
    HCEscalationClock Owner;
    override int HCStep()
    {
        if (!Owner) { return STEP_FAILED; }
        return Owner.HCStepRoutine();
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCEscalationClock);
    }
}
