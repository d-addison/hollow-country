// HC-25. No provider reads: cached HC fields and trivial HC getters.
// N1 3_Game/Global/Game.c:914 GetTickTime only timestamps lifecycle receipts.
// HCXAISites.c:281 Phase; HCXAIEncounters.c:50-52 Armed/Settled/State.
// Do NOT call Ready(), QualifiedCount(), Prerequisites() or GlobalsProblem():
// those inspect live patrols/settings and do not belong in an operator read.
modded class HCXAIAdapter
{
    protected ref HCOperationalOwner m_CaravanOperationalOwner;

    override void HCPublishCaravanStatus(bool boot)
    {
        if (!m_Caravan) { return; }
        HCOperationalStatus caravanStatus = m_Caravan.HCGetOperationalStatus();
        if (boot || !m_CaravanOperationalOwner)
        {
            m_CaravanOperationalOwner = HCOperationalContributors.HCRegisterOwner("hc36-caravan");
        }
        if (m_CaravanOperationalOwner)
        {
            m_CaravanOperationalOwner.HCObserve(m_CaravanRequested, caravanStatus, GetGame().GetTickTime());
        }
        if (!boot) { return; }
        int active = 0;
        if (m_Caravan.m_Ready && m_Caravan.HCActive()) { active = 1; }
        string line = "[HC Plan] HC-36 state=" + caravanStatus.HCState();
        line += " reason=" + caravanStatus.HCReason() + " authored=1";
        line += " provider_refused=" + m_Caravan.m_ProviderRefusal;
        Print(line + " count=" + active.ToString() + " count_cap=1 runtime=PENDING");
    }

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
