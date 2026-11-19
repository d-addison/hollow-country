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
// removal. Interrupted writes fail closed; this is NOT atomic rename or fsync.
// A stale .tmp or missing primary with .bak needs operator recovery, not reset.
class HCV2ThreatStore<Class T>
{
    static bool CanOpen(string path)
    {
        if (!HCRecoveryGate.HCAllowRead(path)) { return false; }
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) return false;
        if (FileExist(path + ".tmp")) return false;
        if (!FileExist(path) && FileExist(path + ".bak")) return false;
        return true;
    }

    static bool Load(string path, int limit, out T state)
    {
        return HCGroupJson<T>.Load(path, limit, state);
    }

    static bool Save(string path, T state, int limit)
    {
        if (!HCRecoveryGate.HCAllowWrite(path)) { return false; }
        string text;
        string error;
        if (!JsonFileLoader<T>.MakeData(state, text, error)) return false;
        string temporary = path + ".tmp";
        string backup = path + ".bak";
        if (!HCGroupIO.WriteNew(temporary, text, limit)) return false;
        // Leave the intent on every failure from here onward. Never fall back
        // to a backup automatically or silently recreate a lost epoch/heat map.
        if (FileExist(path))
        {
            string previous;
            string backedUp;
            if (!HCGroupIO.Read(path, limit, previous)) return false;
            if (FileExist(backup) && !DeleteFile(backup)) return false;
            if (!CopyFile(path, backup)) return false;
            if (!HCGroupIO.Read(backup, limit, backedUp) || backedUp != previous) return false;
            if (!DeleteFile(path)) return false;
        }
        if (!CopyFile(temporary, path)) return false;
        string actual;
        if (!HCGroupIO.Read(path, limit, actual) || actual != text) return false;
        return DeleteFile(temporary);
    }
}

class HCEscalationState
{
    int Version;
    string WorldName;
    int EpochUtc;
    int SavedUtc;
}

class HCEscalationClock : HCModule
{
    protected static HCEscalationClock s_Instance;
    protected ref HCEscalationState m_State;
    protected int m_NowUtc;
    protected int m_LogUtc;
    protected int m_LogDay = -1;
    protected bool m_Healthy;
    protected ref HCEscalationSaveJob m_SaveJob;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;
    static const string PATH = "$profile:HollowCountry/escalation.json";

    override string GetName() { return "Escalation"; }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Operational; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableWorld; }

    // Authored piecewise knots at day 0 / 7 / 14 / 30; held at cap thereafter.
    static float Curve(int day, float week, float fortnight, float cap)
    {
        if (day <= 0) { return 0; }
        if (day <= 7) { return Math.Clamp(week * day / 7.0, 0, 1); }
        if (day <= 14) { return Math.Clamp(week + (fortnight - week) * (day - 7) / 7.0, 0, 1); }
        if (day <= 30) { return Math.Clamp(fortnight + (cap - fortnight) * (day - 14) / 16.0, 0, 1); }
        return Math.Clamp(cap, 0, 1);
    }

    static float PressureAtDay(string axis, int day)
    {
        if (axis == "infected") { return HCEscalationClock.Curve(day, 0.25, 0.55, 1); }
        if (axis == "raiders") { return HCEscalationClock.Curve(day, 0.10, 0.35, 1); }
        if (axis == "scarcity") { return HCEscalationClock.Curve(day, 0.15, 0.40, 1); }
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

    protected void Fail()
    {
        m_Healthy = false;
        HCPersistenceDisposition.HCQuarantine("escalation_schema_clock_or_store_fault");
        m_Operational.HCPublish("refused", "recovery_or_clock_fault");
        if (s_Instance == this) s_Instance = null;
        Print("[HollowCountry] V2 escalation disabled: UTC/schema/world/persistence fault; preserve escalation.json, .tmp and .bak");
    }

    protected bool Valid(int nowUtc)
    {
        if (!m_State || m_State.Version != 1 || m_State.WorldName != GetGame().GetWorldName()) return false;
        return m_State.EpochUtc > 0 && m_State.SavedUtc >= m_State.EpochUtc && nowUtc >= m_State.SavedUtc;
    }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings) || s_Instance) return;
        if (!HCPersistenceDisposition.HCAdmitStore("escalation")) { Fail(); return; }
        Print(HCV2Admission.Line("Escalation", true, "none", true));
        m_NowUtc = HCGroupClock.Utc();
        if (m_NowUtc < 1 || !HCV2ThreatStore<HCEscalationState>.CanOpen(PATH)) { Fail(); return; }
        if (FileExist(PATH))
        {
            if (!HCV2ThreatStore<HCEscalationState>.Load(PATH, 2048, m_State) || !Valid(m_NowUtc)) { Fail(); return; }
        }
        else
        {
            // Missing durable epoch is not an empty successful recovery.
            Fail();
            return;
        }
        m_Healthy = true;
        m_Operational.HCPublish("ready", "operator_paired_restore");
        s_Instance = this;
        m_SaveJob = new HCEscalationSaveJob;
        m_SaveJob.Owner = this;
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
            m_SaveJob.HCDirty = true;
        }
        float infected = Pressure("infected");
        float raiders = Pressure("raiders");
        Print("[HollowCountry] V2 escalation day=" + day.ToString() + " infected=" + infected.ToString() + " raiders=" + raiders.ToString());
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Healthy) return;
        if (!HCRecoveryGate.HCReady()) { Fail(); return; }
        int nowUtc = HCGroupClock.Utc();
        if (nowUtc < m_NowUtc) { Fail(); return; }
        m_NowUtc = nowUtc;
        Report();
    }

    bool HCFlushRoutine()
    {
        if (!m_Healthy) { return false; }
        if (!HCV2ThreatStore<HCEscalationState>.Save(PATH, m_State, 2048)) { Fail(); return false; }
        return true;
    }

    override void OnStop()
    {
        if (m_Healthy)
        {
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
        m_Operational.HCPublish("off", "stopped");
        m_Healthy = false;
        if (s_Instance == this) { s_Instance = null; }
    }
}

class HCEscalationSaveJob : HCSaveJob
{
    override string HCName() { return "EscalationClock"; }
    HCEscalationClock Owner;
    override bool HCWrite() { return Owner && Owner.HCFlushRoutine(); }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCEscalationClock);
    }
}
