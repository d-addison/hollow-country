// HC-6 / #150. Source implementation; runtime acceptance pending.
// Owned by the EXISTING HCWeatherDays ChernarusPlusData instance, never a
// module/forecast writer. HC-51 consumes HCSeason(); HC-50 owns terrain feasibility.
// Four 604800-second phases, using running-server time only. No UTC, game date,
// temperature, clothing, holdout/claim clock or weather/calendar calls here.
// Native scripts-1.30.164289 (root ~/.cache/hollow-country/native-scripts/scripts-1.30.164289):
// 3_Game/Global/Game.c:909-914 GetTickTime (seconds since game start), :1120 IsServer;
// 3_Game/gameplay.c:636 GetGame; 1_Core/proto/EnMath.c:427 Floor;
// 1_Core/proto/EnDebug.c:96 Print; 1_Core/proto/EnConvert.c:30 int.ToString.
// Baselines are NEVER persisted. A new baseline on restart excludes downtime.
// Rollback/save faults require review and restart. Checkpoint lag resumes once
// the saver catches up, resetting the baseline so paused time is never credited.
// Default crash-lost running time <=300 seconds, enforced against the last
// committed snapshot (including queue delay). A stalled saver pauses instead
// of growing this loss. Checkpoint eligibility is 60 seconds; shared scheduler
// timing is provisional. Fractional seconds survive a normal stop/restart.
class HCVisualSeasonConfig : HCc2SeasonTuning
{
    int SchemaVersion = 1;
    bool EnableVisualSeasons = true;
    int PhaseSeconds = 604800;
    int CheckpointSeconds = 60;
    int MaxUncheckpointedSeconds = 300;
    float MaxClockDeltaSeconds = 10;

    bool HCValid()
    {
        // Four phases must fit the existing 2,000,000,000-second clock envelope.
        if (SchemaVersion != 1 || PhaseSeconds < 1 || PhaseSeconds > 500000000) { return false; }
        if (CheckpointSeconds < 1 || CheckpointSeconds > 300) { return false; }
        if (MaxUncheckpointedSeconds < CheckpointSeconds + 10 || MaxUncheckpointedSeconds > 600) { return false; }
        return MaxClockDeltaSeconds >= 1 && MaxClockDeltaSeconds <= 30;
    }
}

class HCVisualSeasons
{
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCVisualSeasonConfig m_Config;
    protected ref HCVisualSeasonStore m_Store;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected bool m_Running;
    protected bool m_Paused;
    protected string m_PauseReason = "none";
    protected int m_PauseCheckpointSeconds;
    protected float m_NextSummary;
    protected float m_LastTick;
    protected bool m_HitchReported;
    protected float m_Fraction;
    protected int m_LastPhase = -1;

    // Call only after the existing owner admits Chernarus/weather authority.
    // Do not add a registry slot, queued callback or another Chernarus writer.
    bool HCStart(bool ownerAdmitted)
    {
        if (m_Running) { return !m_Paused; }
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        if (!ownerAdmitted)
        {
            Print("[HC Plan] HC-6 season=unavailable elapsed=0 clock=server-uptime state=refused reason=weather-owner count=0 runtime=PENDING");
            return false;
        }
        m_Config = HCVisualSeasonIO.HCLoadConfig();
        if (!m_Config)
        {
            Print("[HC Plan] HC-6 season=unavailable elapsed=0 clock=server-uptime state=refused reason=config count=0 runtime=PENDING");
            return false;
        }
        Print(HCV2Admission.Line("VisualSeasons", m_Config.EnableVisualSeasons, "HC-6", false));
        if (!HCV2Admission.Admitted(m_Config.EnableVisualSeasons))
        {
            Print("[HC Plan] HC-6 season=unavailable elapsed=0 clock=server-uptime state=off count=0 runtime=PENDING");
            return false;
        }
        m_Store = new HCVisualSeasonStore;
        if (!m_Store.HCOpen()) { return false; }
        m_Store.HCClockOwner = this;
        if (!HCBeginClock(GetGame().GetTickTime()))
        {
            m_Store.HCStop();
            return false;
        }
        return true;
    }

    protected bool HCBeginClock(float now)
    {
        if (!(now >= 0) || now > 2000000000)
        {
            Print("[HC Plan] HC-6 season=unavailable elapsed=0 clock=server-uptime state=refused reason=baseline count=0 runtime=PENDING");
            return false;
        }
        m_LastTick = now;
        m_Fraction = m_Store.HCRemainder();
        m_LastPhase = -1;
        m_Running = true;
        m_Paused = false;
        m_PauseReason = "none";
        m_HitchReported = false;
        HCReport("on", "start");
        Print(HCV2Admission.Line("SeasonLeaves", true, "HC-226", false) + " runtime=PENDING");
        return true;
    }

    int HCElapsed()
    {
        if (!m_Store) { return 0; }
        return m_Store.HCElapsed();
    }

    int HCPhase()
    {
        if (!m_Config) { return 0; }
        // Integer remainder first: no binary32 rounding near week boundaries.
        int within = HCElapsed() % (m_Config.PhaseSeconds * 4);
        if (within >= m_Config.PhaseSeconds * 3) { return 3; }
        if (within >= m_Config.PhaseSeconds * 2) { return 2; }
        if (within >= m_Config.PhaseSeconds) { return 1; }
        return 0;
    }

    string HCSeason()
    {
        int phase = HCPhase();
        if (phase == 1) { return "summer"; }
        if (phase == 2) { return "autumn"; }
        if (phase == 3) { return "winter"; }
        return "spring";
    }

    // Consumer contract: no phase cache, clock advance, config IO or weather writes.
    // -1 means unavailable; callers retain their non-seasonal policy. In particular,
    // do not turn the legacy HCPhase() fallback 0 into a spring gameplay signal.
    // Native scripts-1.30.164289: 3_Game/Global/Game.c:1093 GetMission,
    // :1120 IsServer; 3_Game/gameplay.c:742 Mission.GetWorldData;
    // 1_Core/proto/EnScript.c:94 inherited Class.Cast.
    static int HCReadPhase()
    {
        return auditseason_Phase.HCReadOwnerPhase();
    }

    int HCReadActivePhase()
    {
        if (!HCValidClock()) { return -1; }
        return HCPhase();
    }

    // A healthy checkpoint-lag pause freezes elapsed time, not its valid phase.
    // Consumers can keep seasonal policy while the shared saver catches up.
    bool HCValidClock()
    {
        if (!m_Running || !m_Config || !m_Store) { return false; }
        if (m_Paused && m_PauseReason != "checkpoint-lag") { return false; }
        return m_Config.EnableVisualSeasons && m_Store.HCHealthy();
    }

    bool HCActive()
    {
        return !m_Paused && HCValidClock();
    }

    HCOperationalStatus HCGetOperationalStatus()
    {
        // Publish only already observed owner/store state; runtime remains pending.
        m_Status.HCPublish("off", "clock_inactive");
        if (!m_Running) { return m_Status; }
        if (m_Paused)
        {
            m_Status.HCPublish("refused", "clock_paused");
            return m_Status;
        }
        if (!m_Store || !m_Store.HCHealthy())
        {
            m_Status.HCPublish("refused", "store_unhealthy");
            return m_Status;
        }
        if (HCActive()) { m_Status.HCPublish("ready", "active_clock"); }
        return m_Status;
    }

    protected void HCReport(string status, string reason)
    {
        m_LastPhase = HCPhase();
        int elapsed = HCElapsed();
        // Build in pieces: the native compiler refuses over 9 binary '+' in one.
        string line = "[HC Plan] HC-6 season=" + HCSeason() + " elapsed=" + elapsed.ToString() + " clock=server-uptime state=" + status;
        int day = elapsed / 86400 + 1;
        line += " day=" + day.ToString() + " paused_reason=" + m_PauseReason;
        Print(line + " reason=" + reason + " count=1 unsaved_cap=" + m_Config.MaxUncheckpointedSeconds.ToString() + " runtime=PENDING");
        m_NextSummary = GetGame().GetTickTime() + 300;
    }

    protected void HCPause(string reason)
    {
        if (m_Paused) { return; }
        m_Paused = true;
        m_PauseReason = reason;
        m_PauseCheckpointSeconds = m_Store.HCCheckpointedSeconds();
        m_Store.HCQueueCheckpoint(0);
        HCReport("paused", reason);
    }

    // Called on every verified save and checked on ticks as well. Never recover
    // clock discontinuity, elapsed overflow or a failed persistence store here.
    void HCCheckpointSaved()
    {
        if (!m_Running || !m_Paused || m_PauseReason != "checkpoint-lag") { return; }
        if (!m_Store.HCHealthy()) { return; }
        // The uncredited tick that crossed the cap is excluded from unsaved
        // time. A lower value alone cannot prove the saver has made progress.
        if (m_Store.HCCheckpointedSeconds() <= m_PauseCheckpointSeconds) { return; }
        if (m_Store.HCUnsavedSeconds() + m_Fraction >= m_Config.MaxUncheckpointedSeconds) { return; }
        float now = GetGame().GetTickTime();
        if (!(now >= m_LastTick) || now > 2000000000) { return; }
        m_LastTick = now;
        m_Paused = false;
        m_PauseReason = "none";
        HCReport("on", "checkpoint-caught-up");
    }

    protected void HCAdvance(float now)
    {
        if (!m_Running || m_Paused) { return; }
        if (!m_Store.HCHealthy()) { HCPause("store-fault"); return; }
        float delta = now - m_LastTick;
        // NaN fails the ordered comparisons; infinity fails the upper bound.
        if (!(now >= 0) || now > 2000000000 || !(delta >= 0))
        {
            HCPause("clock-discontinuity");
            return;
        }
        // A finite forward gap (server start, save or CE hitch) is skipped
        // without crediting it; the clock keeps running (boot 042 paused here).
        if (!(delta <= m_Config.MaxClockDeltaSeconds))
        {
            m_LastTick = now;
            if (!m_HitchReported)
            {
                m_HitchReported = true;
                HCReport("on", "hitch");
            }
            return;
        }
        if (m_Store.HCUnsavedSeconds() + m_Fraction + delta > m_Config.MaxUncheckpointedSeconds)
        {
            HCPause("checkpoint-lag");
            return;
        }
        m_LastTick = now;
        float sum = m_Fraction + delta;
        int whole = Math.Floor(sum);
        if (HCElapsed() > 2000000000 - whole) { HCPause("elapsed-cap"); return; }
        m_Fraction = sum - whole;
        m_Store.HCSetElapsed(HCElapsed() + whole, m_Fraction);
        m_Store.HCQueueCheckpoint(m_Config.CheckpointSeconds);
        if (HCPhase() != m_LastPhase) { HCReport("on", "boundary"); }
    }

    void HCTick()
    {
        if (!m_Running) { return; }
        // One scalar update, no entity/player scan or retained work queue.
        m_Units.HCReset(1);
        m_Work.HCReset(1);
        if (!m_Units.HCTake(1) || !m_Work.HCContinue()) { return; }
        HCCheckpointSaved();
        // Completion of an older in-flight image clears scheduler dirty state.
        // Keep requesting the frozen image until a newer checkpoint commits.
        if (m_Paused && m_PauseReason == "checkpoint-lag") { m_Store.HCQueueCheckpoint(0); }
        HCAdvance(GetGame().GetTickTime());
        if (GetGame().GetTickTime() >= m_NextSummary)
        {
            string status = "on";
            if (m_Paused) { status = "paused"; }
            HCReport(status, "summary");
        }
    }

    void HCStop()
    {
        if (!m_Running) { return; }
        HCAdvance(GetGame().GetTickTime());
        m_Store.HCStop();
        m_Store.HCClockOwner = null;
        m_Running = false;
        HCReport("stopped", "stop");
    }
}

// Native owner resolution is separate from scalar clock decisions. No retained state.
class auditseason_Phase
{
    static int HCReadOwnerPhase()
    {
        if (!GetGame() || !GetGame().IsServer()) { return -1; }
        Mission seasonMission = GetGame().GetMission();
        if (!seasonMission) { return -1; }
        ChernarusPlusData seasonData = ChernarusPlusData.Cast(seasonMission.GetWorldData());
        if (!seasonData) { return -1; }
        HCVisualSeasons seasons = seasonData.HCWinterTerrainSeasons();
        if (!seasons) { return -1; }
        return seasons.HCReadActivePhase();
    }
}
