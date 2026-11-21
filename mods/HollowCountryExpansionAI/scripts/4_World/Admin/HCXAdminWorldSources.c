// Reuse HCXAILive.Emit (faction/source/combat/weapon) and the provider-owned
// registry already inspected in HCXAILiveMap.c: eAIBase.eAI_GetAll (:466).
// No provider implementation copied. At most rows entries visited per tick.
modded class HCAdminWorldSources
{
    protected int m_AdminAICursor;
    protected bool m_AdminConvoyRead;
    override bool StepAI(HCAdminWorldCapture capture, int rows)
    {
        if (!m_AdminConvoyRead)
        {
            m_AdminConvoyRead = true;
            HCXConvoyService service = HCXConvoyService.HCGet();
            if (service && service.mHCRun)
            {
                HCXConvoyRun run = service.mHCRun;
                vector position;
                bool located = false;
                if (run.mHCCar) { position = run.mHCCar.GetPosition(); located = true; }
                else if (run.mHCLeader) { position = run.mHCLeader.GetPosition(); located = true; }
                if (located) { capture.Put("convoys", position, "Convoy", "phase=" + run.mHCPhase + "; reason=" + run.mHCReason); }
            }
        }
        array<eAIBase> all = eAIBase.eAI_GetAll();
        if (!all) { return true; }
        int end = Math.Min(all.Count(), m_AdminAICursor + rows);
        end = Math.Min(end, HCAdminWorldWire.ROWS);
        for (; m_AdminAICursor < end; m_AdminAICursor++)
        {
            eAIBase ai = all[m_AdminAICursor];
            if (!ai || !ai.IsAlive()) { continue; }
            // Emit normally uses AddPoint; bypass only the duplicate debug page filter.
            eAIGroup group = ai.GetGroup();
            string state = "patrol";
            if (group && group.IsInCombat()) { state = "combat"; }
            string detail = "faction=" + HCXAILive.FactionName(group) + "; source=" + HCXAILive.Source(group);
            if (group) { detail += "; role/site=" + group.GetName(); }
            detail += "; state=" + state + "; weapon=" + HCXAILive.WeaponName(ai);
            capture.Put("ai-units", ai.GetPosition(), ai.GetType(), detail);
        }
        if (m_AdminAICursor >= HCAdminWorldWire.ROWS && all.Count() > HCAdminWorldWire.ROWS) { capture.Dropped += all.Count() - HCAdminWorldWire.ROWS; }
        return m_AdminAICursor >= all.Count() || m_AdminAICursor >= HCAdminWorldWire.ROWS;
    }
}
