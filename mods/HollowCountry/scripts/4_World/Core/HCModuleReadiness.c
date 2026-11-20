// Wave 16 (w32-status): one shared, allocation-free derivation of a module's cached operational status
// from state the module already owns (a started flag, an optional refusal string, an optional runtime
// fault string). Nothing here reads config, files or the engine, and nothing is hard-coded ready:
// a module that did not reach its started state can never publish ready. Policy only; runtime=PENDING.
// Receipt logging also uses the verified HCReached token API, array Find/Insert
// (EnScript.c) and Print (EnDebug.c). HCDerive remains allocation-free.
class HCModuleReadiness
{
    protected static ref array<string> s_Reported = new array<string>();
    protected static ref array<bool> s_BootReady = new array<bool>();
    protected static ref array<bool> s_LatePrinted = new array<bool>();

    static void HCPrintLate(string name, bool enabled, bool started, HCOperationalStatus status)
    {
        int index = s_Reported.Find(name);
        if (index < 0 || s_BootReady[index] || s_LatePrinted[index]) { return; }
        if (!HCModuleReadiness.HCReady(enabled, started, status)) { return; }
        s_LatePrinted[index] = true;
        HCModuleReadiness.HCLine(name, enabled, started, status);
    }

    static bool HCReady(bool enabled, bool started, HCOperationalStatus status)
    {
        return enabled && started && status && status.HCState() == "ready";
    }

    static void HCPrint(string name, bool enabled, bool started, HCOperationalStatus status)
    {
        if (s_Reported.Find(name) >= 0 || s_Reported.Count() >= 64) { return; }
        s_Reported.Insert(name);
        s_BootReady.Insert(HCModuleReadiness.HCReady(enabled, started, status));
        s_LatePrinted.Insert(false);
        HCModuleReadiness.HCLine(name, enabled, started, status);
    }

    protected static void HCLine(string name, bool enabled, bool started, HCOperationalStatus status)
    {
        string enabledWord = "false";
        string readyWord = "false";
        string reason = "owner_state_unreported";
        if (enabled) { enabledWord = "true"; }
        if (HCModuleReadiness.HCReady(enabled, started, status)) { readyWord = "true"; }
        if (status) { reason = status.HCReason(); }
        string line = "[HC Ready] module=" + HCReached.Token(name) + " enabled=" + enabledWord;
        line = line + " ready=" + readyWord + " reason=" + HCReached.Token(reason) + " runtime=PENDING";
        Print("" + line);
    }

    static const string HC_OFF_REASON = "not_started_or_disabled";

    // started + runtimeFault  -> degraded (a real fault of a running module, never a missing verdict)
    // started                  -> ready (readyReason names what loaded)
    // refusal                  -> refused (the module tried to start and said why it could not)
    // otherwise                -> off (disabled by setting, or OnStart returned before starting)
    static void HCDerive(HCOperationalStatus status, bool started, string refusal, string runtimeFault, string readyReason)
    {
        if (!status) { return; }
        if (started && runtimeFault != "")
        {
            status.HCPublish("degraded", runtimeFault);
            return;
        }
        if (started)
        {
            status.HCPublish("ready", readyReason);
            return;
        }
        if (refusal != "")
        {
            status.HCPublish("refused", refusal);
            return;
        }
        status.HCPublish("off", HCModuleReadiness.HC_OFF_REASON);
    }
}
