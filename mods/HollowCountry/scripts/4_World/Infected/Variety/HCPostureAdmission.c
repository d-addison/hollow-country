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
// Audit #121: tier-C modes are admitted by SHIPPED ASSETS, not by a client verdict.
// A mode is shipped only when mods/HollowCountryAnims has its clips (tools/anim
// build_anims_addon.py CLIPS) and its entry state in hc_poses.agf; tests/unit/
// test_auditpose_riser.py forces the three to change together. The native playback
// verdict is admitted unverified (owner decision 2026-11-19), logged runtime=PENDING.
// Unshipped modes (flat sleeper, lying riser, feeding) refuse with a named reason
// pointing at the exact asset spec in docs/ANIMATION_PIPELINE.md.
// Fixed four queued modes (feed_kneel is a pose id only, not a queue row), <=1 queue row per core tick, retained cursor, then no-op.
// Native actor activation stays in the existing HC-14 observer/#135 budget path.
class HCPostureAdmission
{
    protected ref array<string> m_Queue = new array<string>;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected bool m_Running;
    protected int m_Cursor;

    // Native DayZInfected.c:39-40 stance/idle; ZombieBase.c:96-99 stance
    // [0,4), :450-477 mind-driven idle/wake, :1089-1092 persistent crawl.
    // Native idle/wake is admitted unverified, under EnableInfectedVariety.
    // Tier C aliases below require assets/graph, not merely a client verdict.
    // This supports holding an ALREADY crawling living actor in native idle,
    // then releasing our idle latch. It never stands it up or resurrects it.
    static bool HCCanEnter(string mode)
    {
        if (mode == "native_stance_idle" || mode == "native_mind_idle") { return true; }
        if (mode == "native_crawler_idle" || mode == "native_crawler_wake") { return true; }
        // Tier C: only the sit pair has authored clips and a graph entry state.
        // prone_sleep, riser and feed_kneel flip here, with their clips and AGF states.
        return mode == "sit_wall";
    }

    static string HCPostureRefusal(string mode)
    {
        if (mode == "native_crawler_idle") { return "none_native_idle_only"; }
        if (mode == "native_crawler_wake") { return "none_native_resume_crawl_unverified"; }
        if (mode == "native_stance_idle" || mode == "native_mind_idle") { return "none_native_move_api_unverified"; }
        if (mode == "sit_wall") { return "none_graph_admitted_unverified"; }
        if (mode == "prone_sleep" || mode == "riser" || mode == "feed_kneel") { return "ASSET_NOT_AUTHORED_" + mode; }
        return "POSTURE_MODE_UNSUPPORTED";
    }

    static string HCTierCState(string mode)
    {
        if (HCCanEnter(mode)) { return "admitted_unverified"; }
        return "asset_missing";
    }

    static string HCPoseMode(int pose)
    {
        if (pose == 1) { return "sit_wall"; }
        if (pose == 2) { return "prone_sleep"; }
        if (pose == 3) { return "riser"; }
        if (pose == 4) { return "feed_kneel"; }
        return "unsupported";
    }

    // Length of the get-up clip played when LEAVING a pose. These are asset
    // facts, not tuning: each value is the authored clip length plus its blend
    // (sit: hc_sit_wall_getup 1.6 s). The unshipped rows are the asset spec
    // targets in docs/ANIMATION_PIPELINE.md and must match the clip when authored.
    static float HCRiseSeconds(int pose)
    {
        if (pose == 1) { return 1.7; }
        if (pose == 2) { return 2.6; }
        if (pose == 3) { return 2.8; }
        if (pose == 4) { return 2.0; }
        return 0;
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
        if (mode == "native_stance_idle" || mode == "native_mind_idle")
        {
            support = "native_move_api_only";
            wake = "native_mind_state_unverified";
        }
        if (mode == "sit_wall")
        {
            support = "own_graph_command_unverified";
            wake = "native_mind_state_unverified";
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
        // Wave 16 owner decision: the missing native rest-wake verdict is an admitted-unverified
        // verdict (logged once by the HCV2Admission line above; HC-45 per-mode lines name each
        // refused mode), not a degraded module. Opt-out stays EnableInfectedVariety.
        string state = "refused";
        if (HCPostureAdmission.HCCanEnter("native_crawler_idle") && HCPostureAdmission.HCCanEnter("native_stance_idle") && HCPostureAdmission.HCCanEnter("native_mind_idle") && HCPostureAdmission.HCCanEnter("native_crawler_wake")) { state = "ready"; }
        m_Status.HCPublish(state, "native_crawler_idle_admitted_rest_wake_unverified_runtime_pending");
        Print("[HC Variety] native_postures=admitted_unverified stance=0..3 idle=native_mind_state wake=resume_crawl opt_out=EnableInfectedVariety runtime=PENDING");
        string tierC = "[HC Variety] tier_c=custom_graph sit_wall=" + HCTierCState("sit_wall") + " prone_sleep=" + HCTierCState("prone_sleep");
        tierC = tierC + " lying_riser=" + HCTierCState("riser") + " feed_kneel=" + HCTierCState("feed_kneel");
        Print(tierC + " native_crawl_reverse=unexposed asset_spec=docs/ANIMATION_PIPELINE.md runtime=PENDING");
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
