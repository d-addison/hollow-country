// Owner-requested infected memory; EnableWorld, EXP-S4 verdict logged only.
// Native evidence: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 4_World/Entities/Firearms/Weapon_Base.c:341 EEFired(int,int,string);
// 4_World/Entities/Core/Inherited/Weapon.c:407 GetAttachedSuppressor;
// 4_World/Entities/ExplosivesBase.c:183 protected OnExplode();
// 4_World/Entities/Firearms/Archery/Archery_Base.c:5 excluded quiet weapon base;
// 3_Game/Entities/Object.c:287 GetPosition, :511 IsKindOf, :981 IsDamageDestroyed;
// 3_Game/Global/Game.c:1120 IsServer, :934 GetWorldName; gameplay.c:636 GetGame;
// 1_Core/proto/EnMath.c:427 Floor, :413 Round, :540 Clamp, :553 Min;
// 1_Core/proto/EnScript.c:380 Count, :407 Insert, :463 Remove;
// 1_Core/proto/EnConvert.c:30 int / :115 float ToString; EnDebug.c:96 Print.
// HCGroupClock.SampleUtc uses EnSystem.c:76,100 UTC. HCV2ThreatStore/HCGroupIO
// use EnSystem.c:397,417,425,443,462,525,528,531 and JsonFileLoader.c:69,85.
// No native rename exists: verified temp/backup/copy with fail-closed intent,
// not atomic rename/fsync. Native compilation and EXP-S4 remain unobserved.
// Only noise locations are retained; no player identities or live destinations.
class HCInfectedMemoryCell
{
    int X = -401;
    int Z = -401;
    float Value;
    int UpdatedUtc;
}

class HCInfectedMemoryState
{
    int Version;
    string WorldName;
    int SavedUtc;
    float CellMetres;
    ref array<ref HCInfectedMemoryCell> Cells = new array<ref HCInfectedMemoryCell>;
}

class HCInfectedMemory
{
    // Native JSON zero-fills absent coordinate sentinels. Require both keys;
    // an explicitly stored origin remains valid. Read only at store open.
    static bool HCFieldsPresent(string text)
    {
        return HCJsonFields.Every(text, "X", 3) && HCJsonFields.Every(text, "Z", 3);
    }

    protected static HCInfectedMemory s_Instance;
    protected ref HCInfectedMemoryState m_State;
    protected bool m_Healthy;
    protected bool m_Dirty;
    protected int m_LastUtc;
    protected int m_LogUtc;
    protected int m_RecordUtc;
    protected int m_RecordCount;
    static const int MAX_CLOCK_SKEW_SECONDS = 300;
    static const string PATH = "$profile:HollowCountry/infected-memory.json";

    // Linear decay from the last real noise. The base and timestamp never get
    // rebased by a periodic tick, so repeated ticks cannot extend the window.
    static float Decayed(float heat, int elapsed)
    {
        if (elapsed < 0) return 0;
        return Math.Clamp(heat, 0, 1) * Math.Clamp(1.0 - elapsed / HCInfectedTuning.Get().Memory.DecaySeconds, 0, 1);
    }

    static int CohortSizeAtHeat(float heat, int available)
    {
        return Math.Min(available, HCInfectedTuning.Get().Memory.CohortBase + Math.Round(HCInfectedTuning.Get().Memory.CohortHeat * Math.Clamp(heat, 0, 1)));
    }

    static int ResponseLimitAtHeat(float heat)
    {
        return HCInfectedTuning.Get().Memory.ResponseBase + Math.Round(HCInfectedTuning.Get().Memory.ResponseHeat * Math.Clamp(heat, 0, 1));
    }

    static bool Active()
    {
        return s_Instance && s_Instance.m_Healthy;
    }

    // Alert root budget includes its seed, just as v1's twelve-recipient cap.
    static int ResponseLimit(vector pos)
    {
        if (!Active()) return 12;
        float heat = Heat(pos);
        if (!Active()) return 12;
        return ResponseLimitAtHeat(heat);
    }

    // Two small hooks in v1 TryAdopt trim its already-bounded candidate list.
    // Inactive/faulted/off uses the caller ceiling; active memory selects
    // its configured base plus heat. All admission/reservation,
    // cue, route, observer and distance checks remain in the original caller.
    static int CohortSize(vector pos, int available)
    {
        int requested = available;
        if (s_Instance && s_Instance.m_Healthy)
        {
            float heat = Heat(pos);
            if (s_Instance && s_Instance.m_Healthy)
            {
                requested = CohortSizeAtHeat(heat, available);
            }
        }
        // W5 #125 affects future CE adoption only, using the once-per-tick
        // online roster. Shared pack/global journal caps remain authoritative.
        return HCInfectedVarietyModule.HCScaledCohort(requested, available);
    }

    protected void Fail(string reason = "UTC/schema/world/persistence fault")
    {
        m_Healthy = false;
        if (s_Instance == this) s_Instance = null;
        Print("[HollowCountry] V2 infected memory disabled: " + reason + "; preserve infected-memory.json, .tmp and .bak");
    }

    protected int Now(bool write)
    {
        // Sampling must not advance the shared groups watermark. Reads never
        // mutate memory, even for an invalid sample or a large backwards step.
        int nowUtc = HCGroupClock.SampleUtc();
        if (nowUtc < 1)
        {
            if (write) { Fail(); return -1; }
            return m_LastUtc;
        }
        if (nowUtc < m_LastUtc)
        {
            if (write && m_LastUtc - nowUtc > MAX_CLOCK_SKEW_SECONDS)
            {
                Fail("clock-skew");
                return -1;
            }
            // No additional decay; retain sample timestamps and rate window
            // until wall time catches up. Small-skew writes still add heat.
            return m_LastUtc;
        }
        if (write) m_LastUtc = nowUtc;
        return nowUtc;
    }

    // Legacy v1 stores used configurable grids without recording their size.
    // After schema validation, deliberately expire that unknowable heat rather
    // than re-key it. Start supplies the configured grid for the empty store.
    // Native EnScript.c:385 Clear; existing Tick owns the bounded durable save.
    protected void HCResolveGrid(string image)
    {
        if (!HCJsonFields.Has(image, "CellMetres"))
        {
            m_State.Cells.Clear();
            m_Dirty = true;
            Print("[HC InfectedMemory] grid=legacy_heat_expired_unknown_grid runtime=PENDING");
        }
    }

    protected bool Valid(int nowUtc)
    {
        if (!m_State || m_State.Version != 1 || m_State.WorldName != GetGame().GetWorldName()) return false;
        if (!(m_State.CellMetres >= 50 && m_State.CellMetres <= 2000)) return false;
        if (!m_State.Cells || m_State.Cells.Count() > 64 || m_State.SavedUtc < 1 || m_State.SavedUtc > nowUtc) return false;
        for (int i = 0; i < m_State.Cells.Count(); i++)
        {
            HCInfectedMemoryCell cell = m_State.Cells[i];
            if (!cell || cell.X < -400 || cell.X > 400 || cell.Z < -400 || cell.Z > 400) return false;
            if (!(cell.Value > 0 && cell.Value <= 1) || cell.UpdatedUtc < 1 || cell.UpdatedUtc > m_State.SavedUtc) return false;
            for (int j = 0; j < i; j++)
            {
                if (m_State.Cells[j].X == cell.X && m_State.Cells[j].Z == cell.Z) return false;
            }
        }
        return true;
    }

    bool Start()
    {
        if (!GetGame().IsServer()) return false;
        if (s_Instance)
        {
            Print("[HollowCountry] V2 infected memory start refused: already_active");
            return false;
        }
        int nowUtc = HCGroupClock.SampleUtc();
        if (nowUtc < 1 || !HCV2ThreatStore<HCInfectedMemoryState>.CanOpen(PATH)) { Fail(); return false; }
        if (FileExist(PATH))
        {
            string image;
            string error;
            if (!HCGroupIO.Read(PATH, 16384, image) || !JsonFileLoader<HCInfectedMemoryState>.LoadData(image, m_State, error)) { Fail("read/json"); return false; }
            if (!m_State) { Fail("null state"); return false; }
            // Supply only the grid for future records, never legacy metadata.
            if (!HCJsonFields.Has(image, "CellMetres")) { m_State.CellMetres = HCInfectedTuning.Get().Memory.CellMetres; }
            if (!HCFieldsPresent(image) || !Valid(nowUtc)) { Fail("missing X/Z or invalid state"); return false; }
            HCResolveGrid(image);
        }
        else
        {
            m_State = new HCInfectedMemoryState;
            m_State.Version = 1;
            m_State.CellMetres = HCInfectedTuning.Get().Memory.CellMetres;
            m_State.WorldName = GetGame().GetWorldName();
            m_State.SavedUtc = nowUtc;
            m_State.Cells = new array<ref HCInfectedMemoryCell>;
            m_Dirty = true;
        }
        if (m_State.CellMetres != HCInfectedTuning.Get().Memory.CellMetres)
        {
            Print("[HC InfectedMemory] grid=persisted_retained_until_empty runtime=PENDING");
        }
        m_Healthy = true;
        m_LastUtc = nowUtc;
        s_Instance = this;
        Tick();
        return m_Healthy;
    }

    protected HCInfectedMemoryCell Find(int x, int z)
    {
        array<ref HCInfectedMemoryCell> cells = m_State.Cells;
        foreach (HCInfectedMemoryCell cell : cells)
        {
            if (cell.X == x && cell.Z == z) return cell;
        }
        return null;
    }

    static float Heat(vector pos)
    {
        if (!GetGame().IsServer() || !s_Instance || !s_Instance.m_Healthy) return 0;
        if (!HCInfectedStore.ValidPosition(pos)) return 0;
        int nowUtc = s_Instance.Now(false);
        if (nowUtc < 1) return 0;
        int x = Math.Floor(pos[0] / s_Instance.m_State.CellMetres);
        int z = Math.Floor(pos[2] / s_Instance.m_State.CellMetres);
        HCInfectedMemoryCell cell = s_Instance.Find(x, z);
        if (!cell) return 0;
        return Decayed(cell.Value, nowUtc - cell.UpdatedUtc);
    }

    static void Record(vector pos, float loudness)
    {
        if (!GetGame().IsServer() || !s_Instance || !s_Instance.m_Healthy) return;
        if (!HCInfectedStore.ValidPosition(pos) || !(loudness > 0 && loudness <= 100)) return;
        s_Instance.Add(pos, Math.Clamp(loudness, 0, 1));
    }

    protected void Add(vector pos, float loudness)
    {
        int nowUtc = Now(true);
        if (nowUtc < 1) return;
        // At most 32 admitted records per wall-clock second. No queue, world
        // scan or disk write in a shot callback; every array is capped at 64.
        if (m_RecordUtc != nowUtc) { m_RecordUtc = nowUtc; m_RecordCount = 0; }
        if (m_RecordCount >= 32) return;
        m_RecordCount++;
        int x = Math.Floor(pos[0] / m_State.CellMetres);
        int z = Math.Floor(pos[2] / m_State.CellMetres);
        HCInfectedMemoryCell cell = Find(x, z);
        if (!cell)
        {
            if (m_State.Cells.Count() >= 64)
            {
                // Deterministic weakest-cell eviction; old/expired heat goes
                // first. Constant 64-entry bound even under dispersed firing.
                int weakest = 0;
                float lowest = 2;
                for (int i = 0; i < m_State.Cells.Count(); i++)
                {
                    HCInfectedMemoryCell candidate = m_State.Cells[i];
                    float value = Decayed(candidate.Value, nowUtc - candidate.UpdatedUtc);
                    if (value < lowest) { lowest = value; weakest = i; }
                }
                m_State.Cells.Remove(weakest);
            }
            cell = new HCInfectedMemoryCell;
            cell.X = x;
            cell.Z = z;
            cell.UpdatedUtc = nowUtc;
            m_State.Cells.Insert(cell);
        }
        cell.Value = Math.Clamp(Decayed(cell.Value, nowUtc - cell.UpdatedUtc) + HCInfectedTuning.Get().Memory.LoudnessGain * loudness, 0, 1);
        cell.UpdatedUtc = nowUtc;
        m_Dirty = true;
    }

    protected bool Save(int nowUtc)
    {
        if (!m_Dirty) return true;
        m_State.SavedUtc = nowUtc;
        if (!HCV2ThreatStore<HCInfectedMemoryState>.Save(PATH, m_State, 16384)) { Fail(); return false; }
        m_Dirty = false;
        return true;
    }

    void Tick()
    {
        if (!m_Healthy) return;
        int nowUtc = Now(true);
        if (nowUtc < 1) return;
        float hottest = 0;
        for (int i = m_State.Cells.Count() - 1; i >= 0; i--)
        {
            HCInfectedMemoryCell cell = m_State.Cells[i];
            float heat = Decayed(cell.Value, nowUtc - cell.UpdatedUtc);
            if (heat <= 0) { m_State.Cells.Remove(i); m_Dirty = true; }
            else if (heat > hottest) { hottest = heat; }
        }
        if (m_State.Cells.Count() == 0 && m_State.CellMetres != HCInfectedTuning.Get().Memory.CellMetres)
        {
            m_State.CellMetres = HCInfectedTuning.Get().Memory.CellMetres;
            m_Dirty = true;
        }
        if (!Save(nowUtc)) return;
        if (m_LogUtc == 0 || nowUtc - m_LogUtc >= 600)
        {
            m_LogUtc = nowUtc;
            int count = m_State.Cells.Count();
            Print("[HollowCountry] V2 infected memory cells=" + count.ToString() + " hottest=" + hottest.ToString());
        }
    }

    void Stop()
    {
        if (m_Healthy)
        {
            int nowUtc = Now(true);
            if (nowUtc > 0) Save(nowUtc);
        }
        m_Healthy = false;
        if (s_Instance == this) s_Instance = null;
    }
}

class HCInfectedMemoryModule : HCModule
{
    protected ref HCInfectedMemory m_Memory;
    protected float m_Elapsed;
    override string GetName() { return "InfectedMemory"; }
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    // Wave 16: started = the memory object exists; an unhealthy memory store is a real fault (degraded).
    override HCOperationalStatus HCGetOperationalStatus()
    {
        bool started = false;
        string fault = "";
        if (m_Memory) { started = true; }
        if (started && !HCInfectedMemory.Active()) { fault = "memory_state_unhealthy"; }
        HCModuleReadiness.HCDerive(m_Operational, started, "", fault, "infected_memory_started");
        return m_Operational;
    }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableWorld; }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings)) return;
        if (m_Memory)
        {
            // OnStart runs once per boot; a second call is a lifecycle fault worth one line.
            Print("[HC InfectedMemory] start ignored: already_started");
            return;
        }
        Print(HCV2Admission.Line("InfectedMemory", true, "EXP-S4", HCV2Gates.Qualified("EXP-S4")));
        m_Memory = new HCInfectedMemory;
        m_Memory.Start();
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Memory) return;
        m_Elapsed += deltaTime;
        if (m_Elapsed < 60) return;
        m_Elapsed = 0;
        m_Memory.Tick();
        HCReached.Mark("infected_memory.maintenance");
    }

    override void OnStop()
    {
        if (m_Memory) m_Memory.Stop();
        m_Memory = null;
    }
}

// Keep the original v1 relay implementation authoritative for geometry, live
// native voice evidence, rooted expiry, cooldowns and recipient deduplication.
// This wrapper only lowers the existing twelve-recipient budget in cool areas;
// gunfire/explosions restore more of it for up to three days, even after the
// finite cohort adoption reservations are spent. No alert is created by heat.
modded class HCAlertChain
{
    override int ProcessPending(array<ref HCInfectedActor> actors, float now, int work)
    {
        if (!HCInfectedMemory.Active()) return super.ProcessPending(actors, now, work);
        Expire(now);
        if (!GetGame().IsServer() || !actors || actors.Count() < 1 || actors.Count() > 24) return 0;
        int spent = 0;
        while (spent < work && m_Queue.Count() > 0)
        {
            HCAlertEmission emission = m_Queue[0];
            int limit = HCInfectedMemory.ResponseLimit(emission.Clue.Origin);
            if (emission.Root.Recipients.Count() >= limit)
            {
                m_Queue.Remove(0);
                spent++;
                continue;
            }
            int used = super.ProcessPending(actors, now, 1);
            if (used < 1) break;
            spent += used;
        }
        return spent;
    }
}

// Observe native events only, call super once, never emit additional AI noise.
// Suppression is an authored heat weight, not a claim about measured audibility.
modded class Weapon_Base
{
    override void EEFired(int muzzleType, int mode, string ammoType)
    {
        super.EEFired(muzzleType, mode, ammoType);
        if (!GetGame().IsServer() || IsKindOf("Archery_Base")) return;
        float loudness = 1;
        ItemBase suppressor = GetAttachedSuppressor();
        if (suppressor && !suppressor.IsDamageDestroyed()) loudness = HCInfectedTuning.Get().Memory.SuppressedLoudness;
        HCInfectedMemory.Record(GetPosition(), loudness);
        if (loudness >= 1) { HCInfectedVarietyModule.HCRecordShot(GetPosition()); }
    }
}

modded class ExplosivesBase
{
    override protected void OnExplode()
    {
        if (GetGame().IsServer()) HCInfectedMemory.Record(GetPosition(), 1);
        super.OnExplode();
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCInfectedMemoryModule);
    }
}
