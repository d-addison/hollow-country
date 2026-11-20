// Activated only in the separate compatibility PBO by tools/package/weapon_pack_guards.py.
// Keep the ordinary adapter independent of an absent weapon pack and its load order.
#ifdef HCX_WEAPON_PACK_GUARDS
modded class DayZPlayerImplementAiming
{
    protected static int s_HCXPackSwayFallbacks;
    protected static int s_HCXPackSwayDelegated;
    protected static int s_HCXPackSwayNextReport;
    protected static bool s_HCXPackSwayReported;

    override float CalculateWeight(int stance_index, float current_stamina, float camera_sway_modifier, bool holding_breath)
    {
        Weapon_Base heldWeapon;
        if (g_Game && g_Game.GetPlayer() && g_Game.GetPlayer().GetHumanInventory())
        {
            heldWeapon = Weapon_Base.Cast(g_Game.GetPlayer().GetHumanInventory().GetEntityInHands());
        }

        // The upstream override uses the local client's hands, even for another aiming instance.
        // Validate that exact receiver, rather than substituting this instance's actor.
        if (heldWeapon)
        {
            s_HCXPackSwayDelegated++;
            HCXReportPackSway();
            return super.CalculateWeight(stance_index, current_stamina, camera_sway_modifier, holding_breath);
        }

        s_HCXPackSwayFallbacks++;
        HCXReportPackSway();
        // No safe super call exists here: it would enter the faulty override.
        // Match native 1.30 non-firearm stance/roll weighting; never return a zero sentinel.
        // Source: native 4_World/Entities/DayZPlayerImplementAiming.c CalculateWeight.
        if (m_PlayerDpi && m_PlayerDpi.GetCommand_Move() && m_PlayerDpi.GetCommand_Move().IsInRoll())
        {
            return PlayerSwayConstants.SWAY_ROLL;
        }
        float stanceWeight = 0.25;
        if (stance_index == DayZPlayerConstants.STANCEIDX_RAISEDERECT)
        {
            stanceWeight = 0.5;
        }
        else if (stance_index == DayZPlayerConstants.STANCEIDX_RAISEDPRONE)
        {
            stanceWeight = 0.075;
        }
        return stanceWeight * m_AimNoiseAllowed * camera_sway_modifier * SWAY_WEIGHT_SCALER;
    }

    protected void HCXReportPackSway()
    {
        if (!g_Game)
        {
            return;
        }
        int now = g_Game.GetTime();
        if (s_HCXPackSwayReported && now < s_HCXPackSwayNextReport)
        {
            return;
        }
        s_HCXPackSwayReported = true;
        s_HCXPackSwayNextReport = now + 60000;
        string report = "[HC Expansion AI] weapon_pack_sway guarded_nonweapon=" + s_HCXPackSwayFallbacks.ToString();
        report += " delegated_weapon=" + s_HCXPackSwayDelegated.ToString();
        Print(report + " runtime=PENDING");
    }
};
#endif
