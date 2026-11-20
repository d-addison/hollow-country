// P5 / MEL-10, MEL-11. Native scripts-1.30.164289 evidence:
// PlayerBase.c:10102 and StaminaHandler.c:1144 DepleteStaminaEx;
// 3_Game/Entities/Object.c:892 ConfigGetFloat reads the object's config class;
// DayZPlayerMeleeFightLogic_LightHeavy.c:386-398,535-541 sets m_HitType
// before distance selection for both initial attacks and combos; :936 retains
// native hit-position/head-distance semantics via IsShortDistance.
// A11/A12 remain unverified until observed on one server and one client.
class HCMeleeFightSettings
{
    protected static ref HCMeleeSettings s_Client;

    static void HCReset() { s_Client = null; }
    static void HCApply(HCMeleeSettings settings) { s_Client = settings; }

    // Never let the client's default-on config predict before server delivery.
    // The server always consults its own admission/config, including opt-out.
    static HCMeleeSettings HCGet()
    {
        if (!GetGame()) { return null; }
        if (GetGame().IsServer())
        {
            if (HCMeleeModule.Active()) { return HCMeleeConfig.HCGet(); }
            return null;
        }
        return s_Client;
    }
}

class HCMeleeWeaponWeight
{
    // Keys come only from actual hands-item types in the installed config.
    // Cache static kilograms, never wetness, cargo or attachment weight.
    protected static ref map<string, float> s_Kg = new map<string, float>;

    static float HCCoefficient(EntityAI item, HCMeleeSettings settings)
    {
        if (!item) { return settings.WeightStaminaFist; }
        string type = item.GetType();
        float kg;
        if (!s_Kg.Find(type, kg))
        {
            kg = Math.Max(0, item.ConfigGetFloat("weight") / 1000.0);
            s_Kg.Set(type, kg);
        }
        return Math.Clamp(settings.WeightStaminaBase + settings.WeightStaminaPerKg * kg, settings.WeightStaminaMin, settings.WeightStaminaMax);
    }
}

modded class PlayerBase
{
    override void DepleteStamina(EStaminaModifiers modifier, float dT = -1)
    {
        if (modifier != EStaminaModifiers.MELEE_LIGHT && modifier != EStaminaModifiers.MELEE_HEAVY)
        {
            super.DepleteStamina(modifier, dT);
            return;
        }
        HCMeleeSettings settings = HCMeleeFightSettings.HCGet();
        if (!settings || !settings.WeightStamina)
        {
            super.DepleteStamina(modifier, dT);
            return;
        }
        StaminaHandler handler = GetStaminaHandler();
        if (!handler) { return; }
        float coef = HCMeleeWeaponWeight.HCCoefficient(GetEntityInHands(), settings);
        handler.DepleteStaminaEx(modifier, dT, coef);
        HCMeleeLog.Event("weight_stamina", "coef=" + coef.ToString());
    }
}

modded class DayZPlayerMeleeFightLogic_LightHeavy
{
    override protected float GetAttackTypeByDistanceToTarget(EntityAI pTarget, EMeleeTargetType pTargetType = EMeleeTargetType.ALIGNABLE)
    {
        HCMeleeSettings settings = HCMeleeFightSettings.HCGet();
        if (!settings || !settings.InPlaceLight || m_HitType != EMeleeHitType.LIGHT)
        {
            return super.GetAttackTypeByDistanceToTarget(pTarget, pTargetType);
        }
        if (pTargetType == EMeleeTargetType.NONALIGNABLE) { return 1.0; }
        if (IsShortDistance(pTarget, Math.SqrFloat(settings.InPlaceDistance))) { return 1.0; }
        return 0.0;
    }
}
