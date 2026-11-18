// W6 #133. Same-layer extension, no edits to shared core files.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:94 Class.Cast, :380,394,407
// Count/Find/Insert; EnConvert.c:30 ToString. <=64 registered modules/request.
// Do not call IsEnabled here: some modules load configuration in that method.
// Enabled means the existing server requested OnStart, not runtime admission.
modded class HCServer
{
    void HCAdminDescribe(HCAdminReply reply)
    {
        if (!m_Started || !m_Registry) { reply.Lines.Insert("[HC Admin] module=Core enabled=0 active=0 budget=n/a"); return; }
        array<ref HCModule> modules = m_Registry.GetModules();
        int work = Math.Min(64, modules.Count());
        for (int moduleIndex = 0; moduleIndex < work; moduleIndex++)
        {
            HCModule module = modules[moduleIndex];
            if (!module) { continue; }
            string enabled = "0";
            if (m_Active.Find(module) >= 0) { enabled = "1"; }
            string name = module.GetName();
            string metrics = "active=n/a budget=n/a";
            HCInfectedModule infected = HCInfectedModule.Cast(module);
            HCEventModule events = HCEventModule.Cast(module);
            HCCampModule camps = HCCampModule.Cast(module);
            HCHoldouts holdouts = HCHoldouts.Cast(module);
            if (infected) { metrics = infected.HCAdminCounts(); }
            else if (events) { metrics = events.HCAdminCounts(); }
            else if (camps) { metrics = camps.HCAdminCounts(); }
            else if (holdouts) { metrics = "sites=" + holdouts.Count().ToString() + " occupied=" + holdouts.Occupied().ToString() + " site_cap=24 occupied_cap=6"; }
            else if (name == "Scenes") { metrics = HCScenesModule.HCAdminCounts(); }
            else if (name == "Escalation") { metrics = "day=" + HCEscalationClock.Day().ToString() + " day_cap=3650 pressure_cap=1"; }
            else if (name == "AdminMap") { metrics = "command_cap=1 snapshot_cap=1 vertex_cap=512 allowlist_cap=32"; }
            reply.Lines.Insert("[HC Admin] module=" + name + " enabled=" + enabled + " " + metrics);
        }
    }
}
