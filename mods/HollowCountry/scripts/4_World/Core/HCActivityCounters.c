// Fixed-schema process telemetry. Hash-map lookup is O(1) on the hit path;
// bounded ordered keys retain deterministic O(N) summaries (never GetKey(i)).
// Native EnScript.c:846 map, :877 Find, :902 Set; :396 EnString.c Split.
// This service is separate from HCModuleReadiness's [HC Use] evidence counters.
class HCActivityCounters
{
    static const int MAX_KEYS = 32;
    protected ref array<string> m_Keys = new array<string>;
    protected ref map<string, int> m_Window = new map<string, int>;
    protected ref map<string, int> m_Total = new map<string, int>;
    protected float m_Seconds;
    protected string m_LastReason = "none";

    void HCActivityCounters(string keys)
    {
        array<string> requested = new array<string>;
        keys.Split(" ", requested);
        for (int index = 0; index < requested.Count() && index < MAX_KEYS; index++)
        {
            string key = requested[index];
            int prior;
            if (key == "" || HCReached.Token(key) != key || m_Total.Find(key, prior)) { continue; }
            m_Keys.Insert(key);
            m_Window.Set(key, 0);
            m_Total.Set(key, 0);
        }
    }

    void HCHit(string key)
    {
        int total;
        if (!m_Total.Find(key, total)) { return; }
        int window = m_Window.Get(key);
        if (total < 2147483647) { m_Total.Set(key, total + 1); }
        if (window < 2147483647) { m_Window.Set(key, window + 1); }
    }

    void Add(string key) { HCHit(key); }
    int HCWindow(string key) { return m_Window.Get(key); }
    int HCTotal(string key) { return m_Total.Get(key); }

    void HCRefuse(string reason, string detail = "")
    {
        HCHit("refused");
        HCHit(reason);
        m_LastReason = reason;
        if (detail != "") { m_LastReason = detail; }
    }

    bool HCDue(float deltaTime)
    {
        if (!(deltaTime > 0) || deltaTime > 3600) { return false; }
        // Saturate elapsed time too if a caller delays its summary indefinitely.
        m_Seconds = Math.Min(m_Seconds + deltaTime, 3600);
        return m_Seconds >= 600;
    }

    void HCLog(string prefix, string gauges = "")
    {
        string line = prefix + " activity window_s=" + m_Seconds.ToString() + gauges;
        for (int index = 0; index < m_Keys.Count(); index++)
        {
            string key = m_Keys[index];
            line += " " + key + "_w=" + m_Window.Get(key).ToString();
            line += " " + key + "_total=" + m_Total.Get(key).ToString();
            m_Window.Set(key, 0);
        }
        Print(line + " last_reason=" + HCReached.Token(m_LastReason) + " runtime=PENDING");
        m_Seconds = 0;
        m_LastReason = "none";
    }
}
