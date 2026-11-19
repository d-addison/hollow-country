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
    // HC-47: module owner supplies effective EnableInfected at start/stop. Off
    // returns the exact native scalar before marker/light/clothing work. This
    // range callback never establishes LOS or changes native target selection;
    // rain/fog/snow/light occlusion and HCVisualSeasons remain native-owned.
    protected static bool s_HCThreatEnabled = true;
    protected static bool s_Checked;
    protected static bool s_OptIn;

    static void HCThreatReset(bool enabled)
    {
        s_HCThreatEnabled = enabled;
        s_Checked = false;
        s_OptIn = false;
    }

    // Cached observation only: an unqueried preference is not effective on.
    static string HCThreatState()
    {
        if (!s_HCThreatEnabled) { return "off"; }
        if (!s_Checked) { return "pending"; }
        if (!s_OptIn) { return "off"; }
        return "on";
    }

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
        if (!s_HCThreatEnabled) { return false; }
        if (Qualified())
            return true;
        if (!s_Checked)
        {
            s_Checked = true;
            s_OptIn = LocalAcceptanceOptIn();
            if (s_OptIn)
                Print("[HollowCountry] V1 admission feature=InfectedVision preference=on gate=infected_vision qualified=0 result=admitted unverified: infected_vision has no recorded native verdict; opt out with acceptance/infected_vision.disable; EXPERIMENTAL; runtime acceptance PENDING");
            else
                Print("[HollowCountry] V1 admission feature=InfectedVision preference=off gate=infected_vision qualified=0 result=off: operator opt-out acceptance/infected_vision.disable; not admitted; runtime acceptance PENDING");
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
        if (visibilityCoef < HCInfectedTuning.Get().Vision.FactorMin)
            return HCInfectedTuning.Get().Vision.FactorMin;
        if (visibilityCoef > HCInfectedTuning.Get().Vision.FactorMax)
            return HCInfectedTuning.Get().Vision.FactorMax;
        return visibilityCoef;
    }

    // Hours from Game.GetDayTime (Game.c:440). Full night 21:00-05:00 with a
    // two hour linear dusk and dawn. Season is not modelled.
    static float Nightness(float hour)
    {
        if (!Finite(hour) || hour < 0 || hour >= 24.0)
            return 0;
        if (hour >= HCInfectedTuning.Get().Vision.NightStart)
            return 1.0;
        if (hour < HCInfectedTuning.Get().Vision.DawnStart)
            return 1.0;
        if (hour >= HCInfectedTuning.Get().Vision.DuskStart)
            return (hour - HCInfectedTuning.Get().Vision.DuskStart) / (HCInfectedTuning.Get().Vision.NightStart - HCInfectedTuning.Get().Vision.DuskStart);
        if (hour < HCInfectedTuning.Get().Vision.DawnEnd)
            return (HCInfectedTuning.Get().Vision.DawnEnd - hour) / (HCInfectedTuning.Get().Vision.DawnEnd - HCInfectedTuning.Get().Vision.DawnStart);
        return 0;
    }

    static float DarknessFactor(float nightness)
    {
        if (!Finite(nightness) || nightness <= 0)
            return 1.0;
        if (nightness >= 1.0)
            return HCInfectedTuning.Get().Vision.DarkFactor;
        return 1.0 - (1.0 - HCInfectedTuning.Get().Vision.DarkFactor) * nightness;
    }

    static float LightFactor(float lit, float nightness)
    {
        if (!Finite(lit) || lit < 0.5)
            return 1.0;
        if (!Finite(nightness) || nightness <= 0)
            return HCInfectedTuning.Get().Vision.LightDay;
        if (nightness >= 1.0)
            return HCInfectedTuning.Get().Vision.LightNight;
        return HCInfectedTuning.Get().Vision.LightDay + HCInfectedTuning.Get().Vision.LightNightIncrement * nightness;
    }

    static float Factor(float visibilityCoef, float hour, float lit)
    {
        float nightness = Nightness(hour);
        float factor = ClothingFactor(visibilityCoef) * DarknessFactor(nightness) * LightFactor(lit, nightness);
        if (!Finite(factor))
            return 1.0;
        if (factor < HCInfectedTuning.Get().Vision.FactorMin)
            return HCInfectedTuning.Get().Vision.FactorMin;
        if (factor > HCInfectedTuning.Get().Vision.FactorMax)
            return HCInfectedTuning.Get().Vision.FactorMax;
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
