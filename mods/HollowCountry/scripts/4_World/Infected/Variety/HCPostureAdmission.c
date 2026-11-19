// HC-45 / #121: fixed support queue, not a spawn queue or a second LOD owner.
// N8 inspected in scripts-1.30.164289 (paths relative to that snapshot):
// 3_Game/AI/AIAgent.c:6 SetKeepInIdle; 3_Game/Entities/DayZAnimal.c:193
// GetAIAgent; 3_Game/Entities/DayZInfected.c:77,123-124 scripted commands.
// ZombieBase.c:203-231 native death/finished-command ordering; :811-833 crawl
// is an injury transition, :1089-1092 crawling remains after its command ends.
// There is no demonstrated reversible injured-crawler rise. Existing own-prefix
// sit/get-up assets/graph are source evidence only (ANIMATION_PIPELINE.md), not
// observed engine playback or safe wake evidence. No caller can promote them
// through a client assertion, JSON preference, successful bind or elapsed timer.
// Arrays/Print: 1_Core/proto/EnScript.c:380,385,407; EnDebug.c:96.
// Fixed four modes, <=1 queue row per core tick, retained cursor, then no-op.
// Native actor activation stays in the existing HC-14 observer/#135 budget path.
class HCPostureAdmission
{
    protected ref array<string> m_Queue = new array<string>;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected bool m_Running;
    protected int m_Cursor;

    // This supports holding an ALREADY crawling living actor in native idle,
    // then releasing our idle latch. It never stands it up or resurrects it.
    static bool HCCanEnter(string mode)
    {
        return mode == "native_crawler_idle";
    }

    static string HCPostureRefusal(string mode)
    {
        if (mode == "native_crawler_idle") { return "none_native_idle_only"; }
        if (mode == "sit_wall") { return "SIT_WAKE_NATIVE_PROOF_PENDING"; }
        if (mode == "prone_sleep") { return "PRONE_WAKE_GRAPH_UNVERIFIED"; }
        if (mode == "riser") { return "REVERSIBLE_RISE_UNEXPOSED"; }
        return "POSTURE_MODE_UNSUPPORTED";
    }

    static string HCPoseMode(int pose)
    {
        if (pose == 1) { return "sit_wall"; }
        if (pose == 2) { return "prone_sleep"; }
        if (pose == 3) { return "riser"; }
        return "unsupported";
    }

    static string HCLine(string mode, int checked)
    {
        string support = "refused";
        string wake = "refused";
        string state = "refused";
        if (HCCanEnter(mode))
        {
            support = "native_idle_api_only";
            wake = "resume_crawl_unverified";
            state = "on";
        }
        string line = "[HC Plan] HC-45 posture=" + mode + " support=" + support + " wake=" + wake;
        line = line + " state=" + state + " reason=" + HCPostureRefusal(mode);
        return line + " checked=" + checked.ToString() + "/4 max_attempts=1 runtime=PENDING";
    }

    void HCStart(bool preference)
    {
        if (m_Running) { return; }
        m_Queue.Clear();
        m_Cursor = 0;
        Print(HCV2Admission.Line("Postures", preference, "HC-45-rest-wake", false));
        if (!preference)
        {
            m_Status.HCPublish("off", "operator_preference");
            Print("[HC Plan] HC-45 posture=all support=off wake=off state=off checked=0/4 max_attempts=1 runtime=PENDING");
            return;
        }
        m_Queue.Insert("native_crawler_idle");
        m_Queue.Insert("sit_wall");
        m_Queue.Insert("prone_sleep");
        m_Queue.Insert("riser");
        m_Running = true;
        m_Status.HCPublish("degraded", "native_crawler_idle_only_rest_wake_unverified");
        HCSlice();
    }

    void HCSlice()
    {
        if (!m_Running || m_Cursor >= m_Queue.Count()) { return; }
        m_Units.HCReset(1);
        m_Work.HCReset(1);
        while (m_Cursor < m_Queue.Count())
        {
            if (!m_Units.HCTake(1) || !m_Work.HCContinue()) { return; }
            string mode = m_Queue[m_Cursor];
            m_Cursor++;
            Print(HCLine(mode, m_Cursor));
        }
    }

    HCOperationalStatus HCStatus() { return m_Status; }

    void HCStop()
    {
        m_Running = false;
        m_Queue.Clear();
        m_Cursor = 0;
        m_Status.HCPublish("off", "posture_queue_stopped");
    }
}
