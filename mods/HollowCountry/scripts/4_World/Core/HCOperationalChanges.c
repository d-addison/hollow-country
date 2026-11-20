// Wave 16 (w32-status): late readiness. HCServer baselines every started module's reported state once
// at Start and compares it on the existing 15 s operational refresh. A change returns ONE log line
// (never printed here, so it stays testable); an unchanged module returns "" with no allocation.
// Parallel arrays are bounded by the registry cap of 128. Passive: no config, file or engine reads.
// Natives: EnScript.c:380,385,407 array Count/Clear/Insert; 1_Core/proto/EnString.c string compare.
class HCOperationalChanges
{
    static const int HC_CAP = 128;
    protected ref array<string> m_States = new array<string>();
    protected ref array<string> m_Reasons = new array<string>();

    void HCReset()
    {
        m_States.Clear();
        m_Reasons.Clear();
    }

    // Index == position in HCServer's active array. A status-less module stores unknown/"" and is never reported.
    void HCBaseline(HCOperationalStatus status)
    {
        if (m_States.Count() >= HCOperationalChanges.HC_CAP) { return; }
        if (!status)
        {
            m_States.Insert("unknown");
            m_Reasons.Insert("");
            return;
        }
        m_States.Insert(status.HCState());
        m_Reasons.Insert(status.HCReason());
    }

    // "" when nothing changed. A ready module whose reason text changed is not a state change.
    string HCChange(int index, string name, HCOperationalStatus status)
    {
        if (!status || index < 0 || index >= m_States.Count()) { return ""; }
        string state = status.HCState();
        string reason = status.HCReason();
        if (state == m_States[index] && (state == "ready" || reason == m_Reasons[index])) { return ""; }
        m_States[index] = state;
        m_Reasons[index] = reason;
        if (state == "ready") { return "[HC " + name + "] ready (late)"; }
        return "[HC " + name + "] " + state + " reason=" + reason;
    }
}
