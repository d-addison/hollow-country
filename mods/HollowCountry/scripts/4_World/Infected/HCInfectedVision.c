// #20 #35 #56 infected vision range from clothing, darkness and lights.
// Native AITargetCallbacksPlayer.GetMaxVisionRangeModifier (installed
// 4_World/Entities/ManBase/PlayerBase/AITargetCallbacksPlayer.c:45-84) scales
// the vision range from the target's speed and stance only. It never reads
// PlayerBase.GetVisibilityCoef (PlayerBase.c:5443), which the clothing mean
// feeds (PlayerBase.c:5405-5436, Clothing_Base visibilityModifier). This file
// multiplies the native result by one clamped factor 0.6..1.3 built ONLY from
// the target player's own state: worn-clothing visibility, a lit light held or
// worn, and the world clock. It reads nothing about the applicant infected, no
// other player, no scan, and allocates nothing per call.
// The multiplier semantics and every constant below are unobserved at runtime
// and provisional. Admission is closed (Qualified() is false) until a local
// DayZDiag run records detection distances; a server operator may create the
// marker named in LocalAcceptanceOptIn for a local acceptance run only. When
// not admitted the override returns exactly the native value.
class HCInfectedVisionQualification
{
    protected static bool s_Checked;
    protected static bool s_OptIn;

    // Evidence required: local-server runs logging detection distance with
    // the light on and off at night, and with and without worn camouflage.
    static bool Qualified()
    {
        return false;
    }

    static bool LocalAcceptanceOptIn()
    {
        return !FileExist("$profile:HollowCountry/acceptance/infected_vision.disable");
    }

    static bool Admitted()
    {
        if (Qualified())
            return true;
        if (!s_Checked)
        {
            s_Checked = true;
            s_OptIn = LocalAcceptanceOptIn();
            if (s_OptIn)
                Print("[HollowCountry] Infected vision EXPERIMENTAL local acceptance opt-in active; runtime acceptance PENDING");
            else
                Print("[HollowCountry] Infected vision not admitted; runtime acceptance PENDING");
        }
        return s_OptIn;
    }
}

// Pure scalar policy. Float parameters only: 1.0 means lit, anything else
// unlit. Invalid inputs (NaN, infinity, out-of-range clock, unset coefficient)
// degrade to the neutral factor, never to a penalty or a bonus.
class HCInfectedVisionPolicy
{
    static bool Finite(float value)
    {
        return value >= -1000000.0 && value <= 1000000.0;
    }

    // GetVisibilityCoef is the mean over ten slots (1.0 for an empty slot).
    static float ClothingFactor(float visibilityCoef)
    {
        if (!Finite(visibilityCoef) || visibilityCoef <= 0)
            return 1.0;
        if (visibilityCoef < 0.6)
            return 0.6;
        if (visibilityCoef > 1.3)
            return 1.3;
        return visibilityCoef;
    }

    // Hours from Game.GetDayTime (Game.c:440). Full night 21:00-05:00 with a
    // two hour linear dusk and dawn. Season is not modelled.
    static float Nightness(float hour)
    {
        if (!Finite(hour) || hour < 0 || hour >= 24.0)
            return 0;
        if (hour >= 21.0)
            return 1.0;
        if (hour < 5.0)
            return 1.0;
        if (hour >= 19.0)
            return (hour - 19.0) / 2.0;
        if (hour < 7.0)
            return (7.0 - hour) / 2.0;
        return 0;
    }

    static float DarknessFactor(float nightness)
    {
        if (!Finite(nightness) || nightness <= 0)
            return 1.0;
        if (nightness >= 1.0)
            return 0.75;
        return 1.0 - 0.25 * nightness;
    }

    static float LightFactor(float lit, float nightness)
    {
        if (!Finite(lit) || lit < 0.5)
            return 1.0;
        if (!Finite(nightness) || nightness <= 0)
            return 1.1;
        if (nightness >= 1.0)
            return 1.5;
        return 1.1 + 0.4 * nightness;
    }

    static float Factor(float visibilityCoef, float hour, float lit)
    {
        float nightness = Nightness(hour);
        float factor = ClothingFactor(visibilityCoef) * DarknessFactor(nightness) * LightFactor(lit, nightness);
        if (!Finite(factor))
            return 1.0;
        if (factor < 0.6)
            return 0.6;
        if (factor > 1.3)
            return 1.3;
        return factor;
    }
}

class HCInfectedVision
{
    // Lit means a switched-on, working light item: flashlight, headtorch,
    // weapon light, universal light (IsLightSource, InventoryItem lights), or
    // a burning torch, road flare, chemlight or gas lamp. Chemlight_ColorBase
    // (ChemLight.c:1) and PortableGasLamp (PortableGasLamp.c:1) inherit the
    // false ItemBase.IsLightSource default (ItemBase.c:865), so they are cast
    // explicitly. IsIgnited is the energy manager working state (EntityAI.c:544).
    static bool LitItem(ItemBase item)
    {
        if (!item)
            return false;
        if (item.IsLightSource())
            return item.IsIgnited();
        if (Flashlight.Cast(item) != null || Roadflare.Cast(item) != null || FlammableBase.Cast(item) != null)
            return item.IsIgnited();
        if (Chemlight_ColorBase.Cast(item) != null || PortableGasLamp.Cast(item) != null)
            return item.IsIgnited();
        return false;
    }

    // Held item, worn headgear, then at most eight attachments of the held item.
    static bool HasLitLight(PlayerBase player)
    {
        if (!player)
            return false;
        ItemBase held = player.GetItemInHands();
        if (LitItem(held))
            return true;
        if (LitItem(ItemBase.Cast(player.FindAttachmentBySlotName("Headgear"))))
            return true;
        if (!held)
            return false;
        GameInventory inventory = held.GetInventory();
        if (!inventory)
            return false;
        int count = inventory.AttachmentCount();
        if (count > 8)
            count = 8;
        for (int i = 0; i < count; i++)
        {
            if (LitItem(ItemBase.Cast(inventory.GetAttachmentFromIndex(i))))
                return true;
        }
        return false;
    }

    static float PlayerFactor(PlayerBase player)
    {
        if (!player)
            return 1.0;
        float lit = 0;
        if (HasLitLight(player))
            lit = 1;
        return HCInfectedVisionPolicy.Factor(player.GetVisibilityCoef(), GetGame().GetDayTime(), lit);
    }
}

modded class AITargetCallbacksPlayer
{
    // The vanilla player member is private (AITargetCallbacksPlayer.c:5) and
    // not readable from a modded class, so the target is captured here. The
    // vanilla constructor (AITargetCallbacksPlayer.c:7-12) still runs.
    protected PlayerBase m_HCVisionPlayer;

    void AITargetCallbacksPlayer(PlayerBase pPlayer)
    {
        m_HCVisionPlayer = pPlayer;
    }

    // Parameter name matches AITarget_callbacks.c:13.
    override float GetMaxVisionRangeModifier(EntityAI pApplicant)
    {
        float nativeRange = super.GetMaxVisionRangeModifier(pApplicant);
        if (!GetGame() || !GetGame().IsServer() || !HCInfectedVisionQualification.Admitted())
            return nativeRange;
        if (!m_HCVisionPlayer)
            return nativeRange;
        float factor = HCInfectedVision.PlayerFactor(m_HCVisionPlayer);
        return nativeRange * factor;
    }
}
