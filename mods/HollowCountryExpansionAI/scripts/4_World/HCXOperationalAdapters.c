// HC-25. No Expansion/native API calls: cached HC fields and trivial HC getters.
// HCXAISites.c:281 Phase; HCXAIEncounters.c:50-52 Armed/Settled/State.
// Do NOT call Ready(), QualifiedCount(), Prerequisites() or GlobalsProblem():
// those inspect live patrols/settings and do not belong in an operator read.
modded class HCXAIAdapter
{
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCOperationalStatus status = new HCOperationalStatus;
        if (!m_Sites || !m_Encounters)
        {
            status.HCPublish("refused", "cached_site_or_encounter_owner_missing");
            return status;
        }
        string phase = m_Sites.Phase();
        if (phase == "off" || phase == "stopped")
        {
            status.HCPublish("off", "cached_sites_" + phase);
        }
        else if (phase == "refused")
        {
            status.HCPublish("refused", "cached_sites_refused");
        }
        else if (phase == "run" && m_Encounters.Armed())
        {
            // Operational admission only. Native/perf qualification is pending.
            status.HCPublish("ready", "cached_sites_run_encounters_armed");
        }
        else if (m_Encounters.Settled())
        {
            status.HCPublish("degraded", "cached_encounters_" + m_Encounters.State());
        }
        else { status.HCPublish("requested", "cached_sites_" + phase); }
        return status;
    }
}
