// HC-6 / #150. Bounded 2048-byte config/state, no saved wall-clock baseline.
// Native scripts-1.30.164289 (root ~/.cache/hollow-country/native-scripts/scripts-1.30.164289):
// 1_Core/proto/EnSystem.c:397 FileExist; 3_Game/Global/Game.c:934 GetWorldName;
// 3_Game/gameplay.c:636 GetGame; 1_Core/proto/EnDebug.c:96 Print.
// Delegates: HCV2ThreatStore/HCGroupJson/HCGroupIO use EnSystem.c:417,425,443,462
// OpenFile/ReadFile/CloseFile/FPrint; :525,528,531 MakeDirectory/DeleteFile/CopyFile;
// 3_Game/tools/JsonFileLoader.c:69,85 LoadData/MakeData. Verified intent, backup,
// copy/readback only; NO atomic rename/fsync guarantee. Pending intent or invalid
// state refuses admission, preserves files and never falls back/reset to spring.
// Routine job: stage 0 snapshots scalars; stage 1 calls the existing verified
// store. Live uptime after the snapshot is retained for the next checkpoint.
class HCVisualSeasonState
{
    int Version;
    string WorldName;
    int ElapsedSeconds = -1;
    float RemainderSeconds = -1;
}

class HCVisualSeasonIO
{
    static bool HCFieldsPresent(string text)
    {
        return HCJsonFields.Has(text, "ElapsedSeconds") && HCJsonFields.Has(text, "RemainderSeconds");
    }

    static const string CONFIG_PATH = "$profile:HollowCountry/seasons.json";
    static const string STATE_PATH = "$profile:HollowCountry/visual-seasons.json";
    static const int LIMIT = 2048;

    static HCVisualSeasonConfig HCLoadConfig()
    {
        if (!HCV2ThreatStore<HCVisualSeasonConfig>.CanOpen(CONFIG_PATH)) { return null; }
        HCVisualSeasonConfig config = new HCVisualSeasonConfig;
        if (FileExist(CONFIG_PATH))
        {
            string image;
            string error;
            HCVisualSeasonConfig loaded;
            if (!HCGroupIO.Read(CONFIG_PATH, LIMIT, image) || !JsonFileLoader<HCVisualSeasonConfig>.LoadData(image, loaded, error) || !loaded) { return null; }
            // Required clock fields retain their previous validation semantics.
            config.SchemaVersion = loaded.SchemaVersion;
            config.EnableVisualSeasons = loaded.EnableVisualSeasons;
            config.PhaseSeconds = loaded.PhaseSeconds;
            config.CheckpointSeconds = loaded.CheckpointSeconds;
            config.MaxUncheckpointedSeconds = loaded.MaxUncheckpointedSeconds;
            config.MaxClockDeltaSeconds = loaded.MaxClockDeltaSeconds;
            config.HCApply(image, loaded);
        }
        else if (!HCV2ThreatStore<HCVisualSeasonConfig>.Save(CONFIG_PATH, config, LIMIT)) { return null; }
        if (!config || !config.HCValid()) { return null; }
        HCSeasonVisualPolicy.HCConfigure(config);
        return config;
    }

    static bool HCValid(HCVisualSeasonState state)
    {
        if (!state || state.Version != 1 || state.WorldName != "chernarusplus") { return false; }
        if (state.ElapsedSeconds < 0 || state.ElapsedSeconds > 2000000000) { return false; }
        // A saved remainder may round to 1 in JSON; accept it rather than refusing every later boot.
        return state.RemainderSeconds >= 0 && state.RemainderSeconds <= 1;
    }

    static HCVisualSeasonState HCLoadState()
    {
        string world = GetGame().GetWorldName();
        world.ToLower();
        if (world != "chernarusplus") { return null; }
        if (!HCV2ThreatStore<HCVisualSeasonState>.CanOpen(STATE_PATH)) { return null; }
        HCVisualSeasonState state;
        if (FileExist(STATE_PATH))
        {
            string image;
            string error;
            if (!HCGroupIO.Read(STATE_PATH, LIMIT, image) || !JsonFileLoader<HCVisualSeasonState>.LoadData(image, state, error)) { return null; }
            if (!HCFieldsPresent(image)) { return null; }
        }
        else
        {
            state = new HCVisualSeasonState;
            state.Version = 1;
            state.WorldName = "chernarusplus";
            state.ElapsedSeconds = 0;
            state.RemainderSeconds = 0;
        }
        if (!HCValid(state)) { return null; }
        return state;
    }

    static bool HCSave(HCVisualSeasonState state)
    {
        if (!HCValid(state)) { return false; }
        return HCV2ThreatStore<HCVisualSeasonState>.Save(STATE_PATH, state, LIMIT);
    }
}

class HCVisualSeasonSaveJob : HCSaveJob
{
    HCVisualSeasonStore Owner;
    override string HCName() { return "VisualSeasons"; }
    override int HCStep()
    {
        if (!Owner) { return HCSaveJob.STEP_FAILED; }
        return Owner.HCStepCheckpoint();
    }
}

class HCVisualSeasonStore
{
    protected ref HCVisualSeasonState m_State;
    protected ref HCVisualSeasonState m_Snapshot;
    protected ref HCVisualSeasonSaveJob m_Job;
    protected bool m_Healthy;
    protected int m_SaveStage;
    protected int m_PersistedSeconds;

    bool HCHealthy() { return m_Healthy; }
    int HCElapsed()
    {
        if (!m_State) { return 0; }
        return m_State.ElapsedSeconds;
    }

    float HCRemainder()
    {
        if (!m_State) { return 0; }
        return m_State.RemainderSeconds;
    }

    int HCUnsavedSeconds()
    {
        if (!m_State) { return 0; }
        return m_State.ElapsedSeconds - m_PersistedSeconds;
    }

    bool HCOpen()
    {
        m_State = HCVisualSeasonIO.HCLoadState();
        if (!m_State) { HCFault(); return false; }
        m_PersistedSeconds = m_State.ElapsedSeconds;
        m_Healthy = true;
        m_Job = new HCVisualSeasonSaveJob;
        m_Job.Owner = this;
        HCSaveScheduler.HCRegister(m_Job);
        // Also verifies a fresh zero image; routine scheduling remains shared.
        m_Job.HCDirty = true;
        return true;
    }

    void HCSetElapsed(int seconds, float remainder)
    {
        m_State.ElapsedSeconds = seconds;
        m_State.RemainderSeconds = remainder;
    }

    void HCQueueCheckpoint(int interval)
    {
        if (!m_Healthy || !m_Job) { return; }
        if (HCUnsavedSeconds() >= interval) { m_Job.HCDirty = true; }
    }

    protected void HCFault()
    {
        m_Healthy = false;
        Print("[HC Plan] HC-6 season=unavailable elapsed=0 clock=server-uptime state=refused reason=store count=0 runtime=PENDING; preserve visual-seasons.json/.tmp/.bak");
    }

    int HCStepCheckpoint()
    {
        if (!m_Healthy) { return HCSaveJob.STEP_FAILED; }
        if (m_SaveStage == 0)
        {
            m_Snapshot = new HCVisualSeasonState;
            m_Snapshot.Version = m_State.Version;
            m_Snapshot.WorldName = m_State.WorldName;
            m_Snapshot.ElapsedSeconds = m_State.ElapsedSeconds;
            m_Snapshot.RemainderSeconds = m_State.RemainderSeconds;
            m_SaveStage = 1;
            return HCSaveJob.STEP_MORE;
        }
        if (!HCVisualSeasonIO.HCSave(m_Snapshot))
        {
            HCFault();
            return HCSaveJob.STEP_FAILED;
        }
        m_PersistedSeconds = m_Snapshot.ElapsedSeconds;
        m_Snapshot = null;
        m_SaveStage = 0;
        return HCSaveJob.STEP_DONE;
    }

    void HCStop()
    {
        if (!m_Job) { return; }
        // Finish any older snapshot first, then persist the latest uptime,
        // including its fractional second. Independent of module stop order.
        if (m_Healthy && m_Job.HCInFlight)
        {
            if (!HCSaveScheduler.HCFlush(m_Job)) { HCFault(); }
        }
        if (m_Healthy)
        {
            m_Job.HCDirty = true;
            if (!HCSaveScheduler.HCFlush(m_Job)) { HCFault(); }
        }
        HCSaveScheduler.HCUnregister(m_Job);
        m_Job.Owner = null;
        m_Job = null;
        m_Healthy = false;
    }
}
