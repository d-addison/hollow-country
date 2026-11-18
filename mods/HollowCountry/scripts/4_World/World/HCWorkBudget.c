// W5-PERF shared cooperative services; candidates for promotion to Core.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:914 GetTickTime (seconds),
// :1535 GetTime (mission milliseconds), :945 GetPlayers; Object.c:287 GetPosition;
// 1_Core/proto/EnScript.c:380 Count, :394 Find, :407 Insert, :463 Remove;
// 1_Core/proto/EnDebug.c:96 Print; EnConvert.c:30 int.ToString.
// Bound: guard O(1); callers retain cursors BEFORE yielding. A native call or
// JSON serialization cannot be preempted; 4 ms is a cooperative target only.
class HCWorkBudget
{
    protected float m_Deadline;
    protected float m_Began;
    protected int m_Limit;
    protected int m_Used;
    protected float m_LogAfter;

    void HCReset(int limit, float milliseconds = 4)
    {
        m_Began = GetGame().GetTickTime();
        // Compare a delta: adding 0.004 to a long-running float clock can round
        // back to the same timestamp and starve every future slice.
        m_Deadline = milliseconds / 1000.0;
        m_Limit = limit;
        m_Used = 0;
    }

    bool HCMayContinue(float now)
    {
        if (!(now >= 0) || !(now < m_Deadline) || m_Used >= m_Limit) { return false; }
        m_Used = m_Used + 1;
        return true;
    }

    bool HCContinue() { return HCMayContinue(GetGame().GetTickTime() - m_Began); }

    void HCDeferred(string moduleName, int count)
    {
        if (count < 1) { return; }
        float now = GetGame().GetTickTime();
        if (now < m_LogAfter) { return; }
        m_LogAfter = now + 600;
        Print("[HollowCountry] perf budget module=" + moduleName + " deferred=" + count.ToString());
    }
}

// One snapshot per native mission frame, shared by owned proximity callers.
// No retained identity/position DTO or full-world enumeration. Core can promote
// this seam to an explicit HCServer.Tick snapshot if other modules adopt it.
class HCPerfPlayers
{
    protected static int s_Frame = -1;
    protected static ref array<Man> s_Players = new array<Man>;

    static array<Man> HCGet()
    {
        int frameTime = GetGame().GetTime();
        if (s_Frame != frameTime)
        {
            s_Frame = frameTime;
            s_Players.Clear();
            GetGame().GetPlayers(s_Players);
        }
        return s_Players;
    }
}

// Only routine checkpoints belong here. Creation, spend, inventory/provenance
// and claim/result durability barriers MUST remain synchronous until their
// callers have durable continuation state. Shutdown bypasses staggering.
class HCSaveJob
{
    bool HCDirty;
    float HCDue;
    bool HCWrite() { return false; }
}

// Bound: <=32 registered stores examined, ONE whole-store callback per tick.
// Existing verified intent/backup/copy writers remain authoritative. Native
// copy/JSON calls have no cancellation API; this does not promise a 5 ms save.
class HCSaveScheduler : HCModule
{
    protected static ref array<ref HCSaveJob> s_Jobs = new array<ref HCSaveJob>;
    protected int m_Next;
    protected ref HCWorkBudget m_Budget = new HCWorkBudget;

    override string GetName() { return "WorldSaves"; }
    override bool IsEnabled(HCSettings settings) { return settings != null; }

    static void HCRegister(HCSaveJob job)
    {
        if (!job || s_Jobs.Find(job) >= 0 || s_Jobs.Count() >= 32) { return; }
        // Stagger first eligibility; subsequent writes coalesce for 60 seconds.
        job.HCDue = GetGame().GetTickTime() + 30 + s_Jobs.Count();
        s_Jobs.Insert(job);
    }

    static bool HCFlush(HCSaveJob job)
    {
        if (!job || !job.HCDirty) { return true; }
        if (!job.HCWrite()) { return false; }
        job.HCDirty = false;
        job.HCDue = GetGame().GetTickTime() + 60;
        return true;
    }

    static void HCUnregister(HCSaveJob job)
    {
        int index = s_Jobs.Find(job);
        if (index >= 0) { s_Jobs.Remove(index); }
    }

    override void OnTick(float deltaTime)
    {
        if (s_Jobs.Count() == 0) { return; }
        float now = GetGame().GetTickTime();
        m_Budget.HCReset(32);
        int examined = 0;
        while (examined < s_Jobs.Count() && m_Budget.HCContinue())
        {
            if (m_Next >= s_Jobs.Count()) { m_Next = 0; }
            HCSaveJob job = s_Jobs[m_Next];
            m_Next = m_Next + 1;
            examined = examined + 1;
            if (!job.HCDirty || now < job.HCDue) { continue; }
            if (!HCFlush(job))
            {
                // Faulted writer preserves its intent; no every-tick retry.
                HCUnregister(job);
            }
            return;
        }
        m_Budget.HCDeferred(GetName(), s_Jobs.Count() - examined);
    }

    // Each owner flushes BEFORE releasing its state in OnStop, irrespective of
    // registry order. No second global flush that could touch a stopped owner.
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCSaveScheduler);
    }
}
