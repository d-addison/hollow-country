// E1 warning receipt. HCXAIBaseRaid.HCWarned is an authored HC port, not an
// Expansion API. No new native/Expansion calls. m_Point is the actual freshly
// perceived storage/door point retained by HCSense; camp.Position is a ledger
// anchor and MUST NOT stand in for that source. Runtime acceptance PENDING.
// Default ON; registry opt-out: acceptance/world_incidents.disable.
modded class HCXAIBaseRaid
{
    override void HCWarned(HCCampRecord camp, int now)
    {
        super.HCWarned(camp, now);
        if (!m_Reserved || m_Camp != camp) { return; }
        HCIncidentEmissions.HCPublish("raid", m_Point, null);
    }
}
