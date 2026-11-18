// #135 native experiment 1 (admin/diagnostic, OFF by default). Arms only when
// the acceptance marker infected_lod_experiment.enable exists at boot; then it
// picks ONE calm, unclaimed, standing tracked infected within 40 m of a player
// (the admin sitter first) and runs two 60 s phases on it:
//   keepidle: AIAgent.SetKeepInIdle(true), then SetKeepInIdle(false);
//   nosim:    EntityAI.DisableSimulation(true), then DisableSimulation(false).
// Every 5 s it logs a progress line and per phase one result line: does the
// pose hold (moved metres), does it wake on a hit or a nearby shot, mind state
// before and after. The client view is the admin's in-game observation (see
// docs/LOCAL_ACCEPTANCE_V1.md #135). A hit or death restores 5 s later at most;
// stop always restores. Nothing here establishes DayZ behaviour on its own:
// runtime=PENDING until the lead reads the lines in a native boot.
// Native scripts-1.30.164289: 3_Game/AI/AIAgent.c:6 SetKeepInIdle;
// 3_Game/Entities/Entity.c:3 DisableSimulation, :6 GetIsSimulationDisabled;
// 3_Game/Entities/DayZAnimal.c:193 GetAIAgent; 1_Core/proto/EnSystem.c:397
// FileExist; 3_Game/Global/Game.c:914 GetTickTime; Entities/Object.c:287
// GetPosition, :517 IsAlive; 4_World/Entities/Creatures/Infected/ZombieBase.c:182
// GetMindStateSynced, :1060 IsBeingBackstabbed; 4_World/Entities/Firearms/
// Weapon_Base.c:341 EEFired; 1_Core/proto/EnConvert.c:196 Distance.
// Bound: one subject, one AIAgent/simulation call per transition, one log line
// per 5 s, no scans of its own (the subject comes from the tracked actors).
class HCInfectedLODExperiment
{
    static const int PHASE_PICK = 0;
    static const int PHASE_KEEPIDLE = 1;
    static const int PHASE_GAP = 2;
    static const int PHASE_NOSIM = 3;
    static const int PHASE_DONE = 4;
    static const float PHASE_SECONDS = 60.0;
    static const float SHOT_RANGE = 60.0;

    protected static bool s_Armed;
    protected static vector s_ShotPos;
    protected static float s_ShotAt = -1;

    protected int m_Phase;
    protected ZombieBase m_Subject;
    protected vector m_Start;
    protected float m_PhaseAt;
    protected float m_NextLog;
    protected float m_EndAt;
    protected int m_MindStart;
    protected bool m_Applied;
    protected bool m_Hit;
    protected bool m_Shot;
    protected float m_ReactAt;
    protected float m_PickGiveUp;
    protected bool m_IdleReleasePending;

    // Cheap when the experiment is not armed: one static bool.
    static void HCRecordShot(vector pos)
    {
        if (!s_Armed) { return; }
        s_ShotPos = pos;
        s_ShotAt = GetGame().GetTickTime();
    }

    bool HCArm()
    {
        s_Armed = false;
        m_Phase = HCInfectedLODExperiment.PHASE_DONE;
        if (!GetGame().IsServer()) { return false; }
        if (!FileExist("$profile:HollowCountry/acceptance/infected_lod_experiment.enable")) { return false; }
        s_Armed = true;
        m_Phase = HCInfectedLODExperiment.PHASE_PICK;
        m_PickGiveUp = GetGame().GetTickTime() + 1800;
        Print("[HC InfectedLOD] experiment armed marker=infected_lod_experiment.enable phases=keepidle,nosim seconds=60 subject=calm-standing-within-40m-of-a-player runtime=PENDING");
        return true;
    }

    bool HCArmed() { return s_Armed; }

    protected string PhaseName()
    {
        if (m_Phase == HCInfectedLODExperiment.PHASE_KEEPIDLE) { return "keepidle"; }
        if (m_Phase == HCInfectedLODExperiment.PHASE_NOSIM) { return "nosim"; }
        if (m_Phase == HCInfectedLODExperiment.PHASE_GAP) { return "gap"; }
        if (m_Phase == HCInfectedLODExperiment.PHASE_PICK) { return "pick"; }
        return "done";
    }

    protected static string YesNo(bool value)
    {
        if (value) { return "yes"; }
        return "no";
    }

    protected bool Apply(bool enable)
    {
        if (!m_Subject) { return false; }
        if (m_Phase == HCInfectedLODExperiment.PHASE_KEEPIDLE)
        {
            AIAgent agent = m_Subject.GetAIAgent();
            if (!agent) { return false; }
            if (enable)
            {
                agent.SetKeepInIdle(true);
                return true;
            }
            // Same release guard as the variety dormancy wake.
            if (m_Subject.IsBeingBackstabbed()) { return false; }
            agent.SetKeepInIdle(false);
            return true;
        }
        if (m_Phase == HCInfectedLODExperiment.PHASE_NOSIM)
        {
            if (enable) { m_Subject.DisableSimulation(true); }
            else { m_Subject.DisableSimulation(false); }
            return true;
        }
        return false;
    }

    protected void Begin(int phase, float now)
    {
        m_Phase = phase;
        m_PhaseAt = now;
        m_EndAt = now + HCInfectedLODExperiment.PHASE_SECONDS;
        m_NextLog = now + 5;
        m_Hit = false;
        m_Shot = false;
        m_ReactAt = -1;
        m_Start = m_Subject.GetPosition();
        m_MindStart = m_Subject.GetMindStateSynced();
        m_Applied = Apply(true);
        Print("[HC InfectedLOD] experiment begin phase=" + PhaseName() + " applied=" + YesNo(m_Applied) + " mind=" + m_MindStart.ToString() + " pos=" + m_Start.ToString() + " runtime=PENDING");
    }

    protected float Moved()
    {
        if (!m_Subject) { return -1; }
        return vector.Distance(m_Start, m_Subject.GetPosition());
    }

    // The result line the lead greps; "untested" when no hit/shot happened.
    protected void Finish(string reason)
    {
        bool alive = m_Subject && m_Subject.IsAlive();
        int mindEnd = -1;
        if (m_Subject) { mindEnd = m_Subject.GetMindStateSynced(); }
        float moved = Moved();
        bool restored = true;
        if (m_Applied) { restored = Apply(false); }
        // A backstab in progress defers the idle release to the next steps.
        m_IdleReleasePending = !restored && m_Phase == HCInfectedLODExperiment.PHASE_KEEPIDLE;
        m_Applied = false;
        bool awake = mindEnd != m_MindStart || moved > 1.0;
        string pose = "moved";
        if (moved >= 0 && moved <= 0.5) { pose = "held"; }
        string wokeHit = "untested";
        if (m_Hit) { wokeHit = YesNo(awake); }
        string wokeNoise = "untested";
        if (m_Shot && !m_Hit) { wokeNoise = YesNo(awake); }
        string simulation = "n/a";
        if (m_Subject) { simulation = YesNo(m_Subject.GetIsSimulationDisabled()); }
        Print("[HC InfectedLOD] experiment result phase=" + PhaseName() + " reason=" + reason + " pose=" + pose + " moved=" + moved.ToString() + " woke_hit=" + wokeHit + " woke_noise=" + wokeNoise + " mind_start=" + m_MindStart.ToString() + " mind_end=" + mindEnd.ToString() + " alive=" + YesNo(alive) + " restored=" + YesNo(restored) + " simdisabled_after=" + simulation + " client_view=see-checklist runtime=PENDING");
    }

    void HCStep(HCInfectedModule infected, array<Man> players, float now)
    {
        if (m_IdleReleasePending)
        {
            AIAgent pendingAgent;
            if (m_Subject) { pendingAgent = m_Subject.GetAIAgent(); }
            if (!pendingAgent) { m_IdleReleasePending = false; }
            if (pendingAgent && !m_Subject.IsBeingBackstabbed())
            {
                pendingAgent.SetKeepInIdle(false);
                m_IdleReleasePending = false;
                Print("[HC InfectedLOD] experiment idle-released-late runtime=PENDING");
            }
        }
        if (!s_Armed || m_Phase == HCInfectedLODExperiment.PHASE_DONE) { return; }
        if (m_Applied && !m_Subject)
        {
            // Body gone: nothing left to restore.
            m_Applied = false;
        }
        if (m_Phase == HCInfectedLODExperiment.PHASE_PICK)
        {
            if (!infected) { return; }
            if (now > m_PickGiveUp)
            {
                Print("[HC InfectedLOD] experiment result phase=pick reason=no-subject-in-30-minutes runtime=PENDING");
                m_Phase = HCInfectedLODExperiment.PHASE_DONE;
                return;
            }
            m_Subject = infected.HCLODProbeSubject(players, 40);
            if (!m_Subject) { return; }
            Begin(HCInfectedLODExperiment.PHASE_KEEPIDLE, now);
            return;
        }
        if (m_Phase == HCInfectedLODExperiment.PHASE_GAP)
        {
            if (now < m_EndAt) { return; }
            if (!m_Subject || !m_Subject.IsAlive())
            {
                Print("[HC InfectedLOD] experiment result phase=nosim reason=subject-lost-before-phase runtime=PENDING");
                m_Phase = HCInfectedLODExperiment.PHASE_DONE;
                return;
            }
            Begin(HCInfectedLODExperiment.PHASE_NOSIM, now);
            return;
        }
        if (!m_Subject || !m_Subject.IsAlive())
        {
            Finish("subject-dead-or-deleted");
            m_Phase = HCInfectedLODExperiment.PHASE_DONE;
            return;
        }
        if (!m_Hit && m_Subject.HCLODHitAt() >= m_PhaseAt)
        {
            m_Hit = true;
            if (m_ReactAt < 0) { m_ReactAt = now + 5; }
        }
        if (!m_Shot && s_ShotAt >= m_PhaseAt && vector.Distance(s_ShotPos, m_Subject.GetPosition()) <= HCInfectedLODExperiment.SHOT_RANGE)
        {
            m_Shot = true;
            if (m_ReactAt < 0) { m_ReactAt = now + 5; }
        }
        if (now >= m_NextLog)
        {
            m_NextLog = now + 5;
            float moved = Moved();
            float elapsed = now - m_PhaseAt;
            int mind = m_Subject.GetMindStateSynced();
            Print("[HC InfectedLOD] experiment phase=" + PhaseName() + " t=" + elapsed.ToString() + " moved=" + moved.ToString() + " mind=" + mind.ToString() + " alive=yes hit=" + YesNo(m_Hit) + " shot=" + YesNo(m_Shot) + " simdisabled=" + YesNo(m_Subject.GetIsSimulationDisabled()) + " runtime=PENDING");
        }
        bool reacted = m_ReactAt >= 0 && now >= m_ReactAt;
        if (now < m_EndAt && !reacted) { return; }
        string reason = "timer";
        if (reacted) { reason = "reaction-window"; }
        Finish(reason);
        if (m_Phase == HCInfectedLODExperiment.PHASE_KEEPIDLE)
        {
            m_Phase = HCInfectedLODExperiment.PHASE_GAP;
            m_EndAt = now + 10;
            return;
        }
        m_Phase = HCInfectedLODExperiment.PHASE_DONE;
        Print("[HC InfectedLOD] experiment done runtime=PENDING");
    }

    // Always leave the subject simulated and not kept idle.
    void HCRestore()
    {
        if (m_Subject && (m_Phase == HCInfectedLODExperiment.PHASE_KEEPIDLE || m_IdleReleasePending))
        {
            AIAgent agent = m_Subject.GetAIAgent();
            if (agent) { agent.SetKeepInIdle(false); }
        }
        if (m_Subject && m_Phase == HCInfectedLODExperiment.PHASE_NOSIM) { m_Subject.DisableSimulation(false); }
        if (m_Subject && m_Applied) { Print("[HC InfectedLOD] experiment restored-on-stop phase=" + PhaseName() + " runtime=PENDING"); }
        m_Applied = false;
        m_IdleReleasePending = false;
        m_Phase = HCInfectedLODExperiment.PHASE_DONE;
        s_Armed = false;
    }
}

modded class Weapon_Base
{
    override void EEFired(int muzzleType, int mode, string ammoType)
    {
        super.EEFired(muzzleType, mode, ammoType);
        if (GetGame().IsServer()) { HCInfectedLODExperiment.HCRecordShot(GetPosition()); }
    }
}
