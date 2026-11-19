// Authored bridge; no dependency code copied. Installed Vehicles/vehicles_scripts.pbo:
// 4_World/DayZExpansion_Vehicles/Entities/Vehicles/ExpansionHelicopterScript.c
// :769 EOnPostSimulate(IEntity,float), :1113 IsLanded(). The provider calls
// IsLanded during simulation; its own cached contact result is used unchanged.
// 0_vehicles_preload.pbo/Common/DayZExpansion_Vehicles_Defines.c:13 defines
// EXPANSIONMODVEHICLE. Integration must order DayZExpansion_Vehicles_Scripts
// before HollowCountry (requiredAddons). No extra physics or actor controller.
// Native 3_Game/Entities/Object.c:517 IsAlive; Game.c:1120 IsServer (via HCEnabled).
#ifdef EXPANSIONMODVEHICLE
modded class ExpansionHelicopterScript
{
    protected bool m_HCVehExpLandingKnown;
    protected bool m_HCVehExpWasLanded;

    override void EOnPostSimulate(IEntity other, float timeSlice)
    {
        super.EOnPostSimulate(other, timeSlice);
        if (!HCHeliPolicy.HCEnabled() || !IsAlive()) { return; }
        bool nowLanded = IsLanded();
        // Initial persisted/CE state is not a new landing event.
        if (!m_HCVehExpLandingKnown)
        {
            m_HCVehExpLandingKnown = true;
            m_HCVehExpWasLanded = nowLanded;
            return;
        }
        if (nowLanded == m_HCVehExpWasLanded) { return; }
        m_HCVehExpWasLanded = nowLanded;
        if (nowLanded) { HCHeliPolicy.HCIncident(this, false); }
        else { HCWorldIncidents.HCRetire(this); }
    }
}
#endif
