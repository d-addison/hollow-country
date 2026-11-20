// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:917/926 map.Contains/Insert.
// Finite, journaled reward ledger for reviewed event caches. It decides and records;
// it never touches the engine world. Native: 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnString.c:20 ToInt, :113 Substring, :240 IndexOf, :304 Trim; EnConvert.c:553 ToString.
// All file work reuses HCEventJournalIO (owned immutable files, readback on write).
// Contract: a grant is spent in memory and journaled BEFORE any item exists. A failed
// or uncertain write never allows a second grant for that site in this process.
// Each process start writes a new boot marker and only then prunes the prior boot, so
// the per-session cap is counted per process and a restart cannot replay a grant file.
// The pool is a per-session allowance, not a persistent economy; it never refills
// inside a session. Vanilla class names only.
class HCEventRewardIO : HCEventJournalIO
{
    void HCEventRewardIO()
    {
        m_Root = "$profile:HollowCountry/Events/rewards";
        m_Label = "reward directory";
    }
}
class HCEventRewardPools
{
    static HCEventRewardEntry Entry(string className, int count)
    {
        HCEventRewardEntry entry = new HCEventRewardEntry;
        entry.Type = className;
        entry.Count = count;
        return entry;
    }
    static HCEventRewardPool V1()
    {
        HCEventRewardPool pool = new HCEventRewardPool;
        pool.MaxCaches = 3;
        pool.ItemsPerCache = 4;
        pool.Entries.Insert(Entry("BandageDressing", 3));
        pool.Entries.Insert(Entry("TunaCan", 2));
        pool.Entries.Insert(Entry("Matchbox", 2));
        pool.Entries.Insert(Entry("Chemlight_Green", 2));
        pool.Entries.Insert(Entry("MetalWire", 1));
        pool.Entries.Insert(Entry("Battery9V", 1));
        pool.Entries.Insert(Entry("Rag", 1));
        return pool;
    }
    static bool Valid(HCEventRewardPool pool)
    {
        if (!pool || pool.Version != 1 || !pool.Entries) { return false; }
        if (pool.MaxCaches < 1 || pool.MaxCaches > 8 || pool.ItemsPerCache < 1 || pool.ItemsPerCache > 8) { return false; }
        if (pool.Entries.Count() < 1 || pool.Entries.Count() > 16) { return false; }
        map<string, bool> seen = new map<string, bool>();
        int total = 0;
        foreach (HCEventRewardEntry entry : pool.Entries)
        {
            if (!entry || !HCEventDirector.TextValid(entry.Type, 96) || entry.Count < 1 || entry.Count > 16) { return false; }
            if (seen.Contains(entry.Type)) { return false; }
            seen.Insert(entry.Type, true);
            total = total + entry.Count;
        }
        return total <= 64;
    }
}
class HCEventRewardLedger
{
    protected ref HCEventJournalIO m_IO;
    protected ref HCEventRewardPool m_Pool;
    protected ref array<int> m_Remaining;
    protected ref array<string> m_Granted;
    protected int m_Boot = 0;
    protected bool m_Ready = false;
    protected bool m_Fault = false;
    protected string m_Refusal;

    // Last Start refusal; logged once per reason change (Commit can retry per cache).
    string Refusal() { return m_Refusal; }
    bool HCRefuse(string reason)
    {
        if (m_Refusal != reason)
        {
            m_Refusal = reason;
            Print("[HC Events] reward ledger refused reason=" + reason);
        }
        return false;
    }
    bool Configure(HCEventJournalIO io, HCEventRewardPool pool)
    {
        if (!io || !HCEventRewardPools.Valid(pool)) { return false; }
        m_IO = io;
        m_Pool = pool;
        m_Remaining = new array<int>();
        m_Granted = new array<string>();
        m_Boot = 0;
        m_Ready = false;
        m_Fault = false;
        m_Refusal = "";
        return true;
    }
    bool Fault()
    {
        m_Fault = true;
        Print("[HC Events] reward journal fault; preserving files, no reward caches this session");
        return false;
    }
    int BootOf(string name)
    {
        int dash = name.IndexOf("-");
        if (dash < 1 || dash > 9) { return 0; }
        string prefix = name.Substring(0, dash);
        int value = prefix.ToInt();
        string canonical = value.ToString();
        if (value < 1 || canonical != prefix) { return 0; }
        int tail = name.Length() - dash;
        string rest = name.Substring(dash, tail);
        if (rest == "-boot.txt") { return value; }
        int restLength = rest.Length();
        if (restLength < 12 || rest.IndexOf("-grant-") != 0 || rest.IndexOf(".txt") != restLength - 4) { return 0; }
        int middle = restLength - 11;
        string serial = rest.Substring(7, middle);
        int number = serial.ToInt();
        string text = number.ToString();
        if (number < 1 || text != serial) { return 0; }
        return value;
    }
    bool Start()
    {
        if (m_Fault) { return HCRefuse("journal_fault"); }
        if (m_Ready) { return true; }
        if (!m_IO || !m_Pool) { return HCRefuse("not_configured"); }
        array<string> names = m_IO.Names();
        if (!names) { return Fault(); }
        int highest = 0;
        foreach (string name : names)
        {
            int boot = BootOf(name);
            if (boot < 1) { return Fault(); }
            if (boot > highest) { highest = boot; }
        }
        int next = highest + 1;
        string marker = next.ToString() + "-boot.txt";
        if (!m_IO.WriteNew(marker, "HC-EVENT-REWARDS v1 boot " + next.ToString(), 128)) { return Fault(); }
        foreach (string prior : names)
        {
            m_IO.Remove(prior);
        }
        m_Boot = next;
        m_Remaining = new array<int>();
        foreach (HCEventRewardEntry entry : m_Pool.Entries)
        {
            m_Remaining.Insert(entry.Count);
        }
        m_Granted = new array<string>();
        m_Ready = true;
        return true;
    }
    // Round-robin over the remaining pool, one unit per hit, spending it immediately.
    HCEventRewardPlan Take(string siteId)
    {
        HCEventRewardPlan plan = new HCEventRewardPlan;
        plan.SiteId = siteId;
        plan.Boot = m_Boot;
        int entries = m_Remaining.Count();
        int cursor = 0;
        int idle = 0;
        if (entries > 0) { cursor = m_Granted.Count() % entries; }
        while (entries > 0 && plan.Items.Count() < m_Pool.ItemsPerCache && idle < entries)
        {
            if (m_Remaining[cursor] > 0)
            {
                m_Remaining[cursor] = m_Remaining[cursor] - 1;
                plan.Items.Insert(m_Pool.Entries[cursor].Type);
                idle = 0;
            }
            else
            {
                idle = idle + 1;
            }
            cursor = (cursor + 1) % entries;
        }
        return plan;
    }
    HCEventRewardPlan Commit(string siteId)
    {
        if (!HCEventDirector.TextValid(siteId, 48) || siteId.Trim().Length() < 1) { return null; }
        // Owners start the ledger before publishing it (wildlife HCStart and
        // HCEventRewards.Ledger). Tick grants must never enumerate/prune boots.
        if (!m_Ready || m_Fault) { HCRefuse("not_started_or_faulted"); return null; }
        if (m_Granted.Find(siteId) >= 0 || m_Granted.Count() >= m_Pool.MaxCaches) { return null; }
        HCEventRewardPlan plan = Take(siteId);
        if (plan.Items.Count() < 1) { return null; }
        m_Granted.Insert(siteId);
        int serial = m_Granted.Count();
        string text = "HC-EVENT-REWARD v1 boot " + m_Boot.ToString() + " site " + siteId + " items";
        foreach (string item : plan.Items)
        {
            text = text + " " + item;
        }
        string name = m_Boot.ToString() + "-grant-" + serial.ToString() + ".txt";
        if (!m_IO.WriteNew(name, text, 512))
        {
            Fault();
            return null;
        }
        return plan;
    }
}
class HCEventRewards
{
    protected static ref HCEventRewardLedger s_Ledger;
    static HCEventRewardLedger Ledger()
    {
        if (!s_Ledger)
        {
            s_Ledger = new HCEventRewardLedger;
            s_Ledger.Configure(new HCEventRewardIO, HCEventRewardPools.V1());
            s_Ledger.Start();
        }
        return s_Ledger;
    }
}
