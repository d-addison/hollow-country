// HC-51: bounded server-phase cache; no weather writes, effects, timers or IO.
// Lead's existing mission control transport calls HCApplyServer ONLY after its
// server-origin/target checks. Three ints: VERSION, revision (1..2e9), phase
// (-1 = off, 0..3 = HC-6 phase). No client gameplay request or local season clock.
// Repeat the same revision/phase as a heartbeat at <=30 seconds; expire at 90.
// New revision required after conflict. Revisions never wrap within a mission.
// Client preferences/effect cleanup remain HC-27 + HCLightingClient's GRADE.
// The cache retains one scalar snapshot while grade is off; no idle callback.
// Native scripts-1.30.164289, relative paths:
// 3_Game/Global/Game.c:909-914 GetTickTime, :1125 IsDedicatedServer;
// 3_Game/gameplay.c:636 GetGame; 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnConvert.c:30 int.ToString;
// 5_Mission/mission/missionGameplay.c:102 OnInit, :266 OnMissionFinish.
// No snowflake scale mutation: native/operator value remains deterministic.
// Runtime=PENDING: source/PBO and two-client transport/presentation acceptance.
class HCSeasonVisualClient
{
    protected static ref HCSeasonVisualClient s_Current;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected int m_Revision;
    protected int m_Phase = -1;
    protected float m_ReceivedAt;
    protected bool m_Conflict;
    protected string m_LastReceipt;

    HCOperationalStatus HCGetOperationalStatus() { return m_Status; }

    static void HCApplyServer(int version, int revision, int phaseCode)
    {
        if (!GetGame() || GetGame().IsDedicatedServer()) { return; }
        if (!s_Current) { s_Current = new HCSeasonVisualClient; }
        s_Current.HCAccept(version, revision, phaseCode, GetGame().GetTickTime());
    }

    static string HCGetPhase()
    {
        if (!s_Current || !GetGame()) { return "unavailable"; }
        return s_Current.HCPhase(GetGame().GetTickTime());
    }

    static void HCReset()
    {
        if (s_Current) { s_Current.HCStop(); }
        s_Current = null;
    }

    // Explicit 'now' port keeps acceptance/expiry decisions executable offline.
    // No untrusted wall clock/calendar or persisted uptime is accepted.
    bool HCAccept(int version, int revision, int phaseCode, float now)
    {
        if (version != HCSeasonVisualPolicy.VERSION || revision < 1 || revision > 2000000000)
        {
            HCRefuse("snapshot_version_revision");
            return false;
        }
        if (phaseCode < -1 || phaseCode > 3 || !(now >= 0) || !(now <= 2000000000))
        {
            HCRefuse("snapshot_bounds");
            return false;
        }
        if (revision < m_Revision) { return false; }
        if (revision == m_Revision)
        {
            if (m_Conflict) { return false; }
            if (phaseCode != m_Phase)
            {
                HCRefuse("snapshot_conflict");
                return false;
            }
            if (now < m_ReceivedAt)
            {
                HCRefuse("snapshot_clock_rollback");
                return false;
            }
        }
        m_Revision = revision;
        m_Phase = phaseCode;
        m_ReceivedAt = now;
        m_Conflict = false;
        if (phaseCode == -1) { HCReport("off", "server_off"); }
        else { HCReport("ready", "server_snapshot"); }
        return true;
    }

    string HCPhase(float now)
    {
        if (m_Revision == 0 || m_Conflict || m_Phase == -1) { return "unavailable"; }
        if (!(now >= m_ReceivedAt) || !(now <= 2000000000))
        {
            HCRefuse("snapshot_clock_rollback");
            return "unavailable";
        }
        if (now - m_ReceivedAt >= HCSeasonVisualPolicy.SNAPSHOT_TTL_SECONDS)
        {
            // Keep revision/phase for an identical server heartbeat to revive;
            // getters cannot start a loop or invent a new server phase.
            HCReport("off", "snapshot_expired");
            return "unavailable";
        }
        return HCSeasonVisualPolicy.HCPhaseName(m_Phase);
    }

    protected void HCRefuse(string reason)
    {
        m_Conflict = true;
        HCReport("refused", reason);
    }

    protected void HCReport(string state, string reason)
    {
        m_Status.HCPublish(state, reason);
        string receipt = state + ":" + reason + ":" + m_Phase.ToString();
        if (receipt == m_LastReceipt) { return; }
        m_LastReceipt = receipt;
        string phase = "unavailable";
        int count = 0;
        if (state == "ready")
        {
            phase = HCSeasonVisualPolicy.HCPhaseName(m_Phase);
            count = 1;
        }
        string line = "[HC Plan] HC-51 client_phase=" + phase + " state=" + state + " reason=" + reason;
        Print(line + " count=" + count.ToString() + " handles=0 runtime=PENDING");
    }

    void HCStop()
    {
        m_Revision = 0;
        m_Phase = -1;
        m_ReceivedAt = 0;
        m_Conflict = false;
        HCReport("off", "mission_stop");
    }
}

modded class MissionGameplay
{
    override void OnInit()
    {
        HCSeasonVisualClient.HCReset();
        super.OnInit();
    }

    override void OnMissionFinish()
    {
        HCSeasonVisualClient.HCReset();
        super.OnMissionFinish();
    }
}
