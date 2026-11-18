// HC-1: cached lifecycle observations, never native/runtime qualification.
// Native scripts-1.30.164289: 1_Core/proto/EnString.c:113,199
// Substring/Length; EnConvert.c:30 int.ToString; EnScript.c:380,385,407
// array Count/Clear/Insert; EnDebug.c:96 Print. No engine/config reads here.
class HCOperationalStatus
{
    protected string m_Name;
    protected string m_State = "unknown";
    protected string m_Reason = "owner_state_unknown";
    protected string m_Readiness = "unknown";
    protected bool m_StartRequested;

    // Owners publish from already observed admission state. Calling a getter
    // must never start a service, reload settings or repeat IsEnabled.
    void HCPublish(string state, string reason)
    {
        m_State = "unknown";
        m_Readiness = "unknown";
        m_Reason = "owner_state_unknown";
        if (state != "off" && state != "requested" && state != "refused" && state != "ready" && state != "degraded") { return; }
        m_State = state;
        m_Readiness = "owner_reported";
        m_Reason = reason;
        if (m_Reason.Length() > 128) { m_Reason = m_Reason.Substring(0, 128); }
        if (m_Reason == "") { m_Reason = "owner_reported"; }
    }

    // Copy the owner's result, so later mutation cannot rewrite the receipt.
    // A false IsEnabled alone cannot explain local preference vs provider loss:
    // that fallback is off/unknown, not an assertion of operator intent.
    void HCCapture(string name, bool startRequested, HCOperationalStatus reported)
    {
        m_Name = name;
        if (m_Name.Length() > 64) { m_Name = m_Name.Substring(0, 64); }
        m_StartRequested = startRequested;
        HCPublish("unknown", "owner_state_unknown");
        if (reported) { HCPublish(reported.HCState(), reported.HCReason()); }
        if (m_State == "unknown")
        {
            m_State = "off";
            if (startRequested) { m_State = "requested"; }
        }
        if (!startRequested && (m_State == "ready" || m_State == "degraded" || m_State == "requested"))
        {
            m_State = "refused";
            m_Readiness = "unknown";
            m_Reason = "owner_report_conflicts_with_no_start";
        }
    }

    string HCState() { return m_State; }
    string HCReason() { return m_Reason; }
    bool HCUnknown() { return m_Readiness == "unknown"; }

    void HCStop()
    {
        m_State = "off";
        m_StartRequested = false;
        m_Readiness = "unknown";
        m_Reason = "server_stop_requested";
    }

    string HCLine()
    {
        string requested = "0";
        if (m_StartRequested) { requested = "1"; }
        return "[HC Plan] HC-1 module=" + m_Name + " state=" + m_State + " start_requested=" + requested + " readiness=" + m_Readiness + " reason=" + m_Reason + " runtime=PENDING";
    }
}

class HCOperationalStatusCache
{
    protected ref array<ref HCOperationalStatus> m_Rows = new array<ref HCOperationalStatus>();

    void HCReset() { m_Rows.Clear(); }
    int HCCount() { return m_Rows.Count(); }

    void HCCapture(string name, bool startRequested, HCOperationalStatus reported)
    {
        // Same fixed maximum as HCModuleRegistry and HCPerfSampler. This is
        // startup-only work: no extra scheduler, tick scan or config IO.
        if (m_Rows.Count() >= 64) { return; }
        HCOperationalStatus row = new HCOperationalStatus();
        row.HCCapture(name, startRequested, reported);
        m_Rows.Insert(row);
        Print(row.HCLine());
    }

    string HCLine(int index)
    {
        if (index < 0 || index >= m_Rows.Count()) { return ""; }
        return m_Rows[index].HCLine();
    }

    int HCCountState(string state)
    {
        int count = 0;
        foreach (HCOperationalStatus row : m_Rows)
        {
            if (row.HCState() == state) { count = count + 1; }
        }
        return count;
    }

    int HCUnknownCount()
    {
        int count = 0;
        foreach (HCOperationalStatus row : m_Rows)
        {
            if (row.HCUnknown()) { count = count + 1; }
        }
        return count;
    }

    void HCStopAll()
    {
        foreach (HCOperationalStatus row : m_Rows) { row.HCStop(); }
    }

    // Unknown readiness overlaps the lifecycle state counts.
    string HCSummary()
    {
        int rows = HCCount();
        int off = HCCountState("off");
        int refused = HCCountState("refused");
        int ready = HCCountState("ready");
        int degraded = HCCountState("degraded");
        int requested = HCCountState("requested");
        int unknown = HCUnknownCount();
        return "[HC Plan] HC-1 status rows=" + rows.ToString() + " off=" + off.ToString() + " refused=" + refused.ToString() + " ready=" + ready.ToString() + " degraded=" + degraded.ToString() + " requested=" + requested.ToString() + " unknown=" + unknown.ToString() + " runtime=PENDING";
    }
}
