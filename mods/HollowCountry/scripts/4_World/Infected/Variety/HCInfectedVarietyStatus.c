// #121: preserve the existing observed posture/dependency row; a bad required
// place catalog is real missing data, never ready through an admission verdict.
modded class HCInfectedVarietyModule
{
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCOperationalStatus observed = super.HCGetOperationalStatus();
        if (m_Running && m_Variety && HCInfectedVariety.HCFault() != "")
        {
            observed.HCPublish("refused", HCInfectedVariety.HCFault());
        }
        return observed;
    }
}
