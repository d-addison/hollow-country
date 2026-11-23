// Fixed process-lifetime telemetry. Keys describe a feature, never an entity.
// Summary owners supply a tag and use game time. Activity owners supply their
// existing tick deltas and report their own gauges and last refusal reason.
class HCActivityCounters
{
    protected static const int MAX_KEYS = 32;
    protected static const float WINDOW_SECONDS = 600;
    protected ref array<string> m_Keys = new array<string>;
    protected ref array<int> m_Window = new array<int>;
    protected ref array<int> m_Total = new array<int>;
    protected string m_Tag;
    protected string m_LastReason = "none";
    protected float m_Since;
    protected float m_Seconds;

    void HCActivityCounters(string keys, string tag = "")
    {
        keys.Split(" ", m_Keys);
        for (int index = 0; index < m_Keys.Count() && index < MAX_KEYS; index++)
        {
            m_Window.Insert(0);
            m_Total.Insert(0);
        }
        m_Tag = tag;
        if (m_Tag != "") { m_Since = GetGame().GetTickTime(); }
    }

    void Add(string key)
    {
        int index = m_Keys.Find(key);
        if (index < 0 || index >= m_Total.Count()) { return; }
        if (m_Window[index] < 2147483647) { m_Window[index] = m_Window[index] + 1; }
        if (m_Total[index] < 2147483647) { m_Total[index] = m_Total[index] + 1; }
    }

    void HCRefuse(string reason, string detail = "")
    {
        Add("refused");
        Add(reason);
        m_LastReason = reason;
        if (detail != "") { m_LastReason = detail; }
    }

    bool HCDue(float deltaTime)
    {
        if (!(deltaTime > 0) || deltaTime > 3600) { return false; }
        m_Seconds += deltaTime;
        return m_Seconds >= WINDOW_SECONDS;
    }

    void HCLog(string prefix, string gauges)
    {
        string line = prefix + " activity window_s=" + m_Seconds.ToString() + gauges;
        line += HCFieldsAndReset("_w");
        Print(line + " last_reason=" + HCReached.Token(m_LastReason) + " runtime=PENDING");
        m_Seconds = 0;
        m_LastReason = "none";
    }

    void Report(string state = "", bool force = false)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        float now = GetGame().GetTickTime();
        if (!force && now - m_Since < WINDOW_SECONDS) { return; }
        string line = m_Tag + " summary window_s=" + (now - m_Since).ToString();
        line += HCFieldsAndReset("");
        if (state != "") { line += " " + state; }
        Print(line + " runtime=PENDING");
        m_Since = now;
    }

    protected string HCFieldsAndReset(string windowSuffix)
    {
        string fields;
        for (int index = 0; index < m_Total.Count(); index++)
        {
            string key = " " + m_Keys[index];
            fields += key + windowSuffix + "=" + m_Window[index].ToString();
            fields += key + "_total=" + m_Total[index].ToString();
            m_Window[index] = 0;
        }
        return fields;
    }
}
