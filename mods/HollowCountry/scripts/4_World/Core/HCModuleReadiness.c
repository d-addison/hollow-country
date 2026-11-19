// Wave 16 (w32-status): one shared, allocation-free derivation of a module's cached operational status
// from state the module already owns (a started flag, an optional refusal string, an optional runtime
// fault string). Nothing here reads config, files or the engine, and nothing is hard-coded ready:
// a module that did not reach its started state can never publish ready. Policy only; runtime=PENDING.
// Natives: 1_Core/proto/EnString.c string compare only.
class HCModuleReadiness
{
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
