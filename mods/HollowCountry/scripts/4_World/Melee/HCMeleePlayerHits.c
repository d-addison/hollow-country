// Native citations are relative to scripts-1.30.164289/.
modded class PlayerBase
{
    // 4_World/Entities/DayZPlayerImplement.c:1485-1503,1607,1620-1625:
    // preserve the native animation decision and juncture; only suppress repeat fullbody hits.
    override bool EvaluateDamageHitAnimation(TotalDamageResult pDamageResult, int pDamageType, EntityAI pSource, string pComponent, string pAmmoType, vector pModelPos, out int pAnimType, out float pAnimHitDir, out bool pAnimHitFullbody)
    {
        if (!GetGame().IsServer())
            return super.EvaluateDamageHitAnimation(pDamageResult, pDamageType, pSource, pComponent, pAmmoType, pModelPos, pAnimType, pAnimHitDir, pAnimHitFullbody);

        bool granted = super.EvaluateDamageHitAnimation(pDamageResult, pDamageType, pSource, pComponent, pAmmoType, pModelPos, pAnimType, pAnimHitDir, pAnimHitFullbody);
        if (!granted || !HCMeleeModule.Active() || !pAnimHitFullbody)
            return granted;

        HCMeleeSettings settings = HCMeleeConfig.HCGet();
        if (!settings.StaggerImmunity)
            return granted;

        // 3_Game/Global/Game.c:1120,1535: server authority and millisecond clock.
        float now = GetGame().GetTime() * 0.001;
        if (now < m_HCMeleeImmuneUntil)
        {
            pAnimHitFullbody = false;
            HCMeleeLog.Event("stagger_immunity", "fullbody=false");
        }
        else
        {
            m_HCMeleeImmuneUntil = now + settings.StaggerImmunitySeconds;
        }
        return granted;
    }

    // 4_World/Entities/ManBase/PlayerBase.c:1255,1311,1432-1441:
    // keep native hit processing and block feedback intact.
    override void EEHitBy(TotalDamageResult damageResult, int damageType, EntityAI source, int component, string dmgZone, string ammo, vector modelPos, float speedCoef)
    {
        if (!GetGame().IsServer())
        {
            super.EEHitBy(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);
            return;
        }

        super.EEHitBy(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);
        if (!HCMeleeModule.Active() || HCMeleeAmmo.IsHC(ammo) || damageType != DT_CLOSE_COMBAT)
            return;

        // 4_World/Entities/Creatures/Infected/ZombieBase.c:655-664:
        // blocked heavy/light attacks use MeleeZombie/Dummy_Light respectively.
        ZombieBase infected = ZombieBase.Cast(source);
        if (!infected || !HCMeleeAmmo.IsBlockedInfectedAmmo(ammo))
            return;

        HCMeleeSettings settings = HCMeleeConfig.HCGet();
        float now = GetGame().GetTime() * 0.001;
        if (settings.BlockCounter)
            HCMeleeRecordBlock(infected, now);

        // PlayerBase.c:2042; 4_World/Classes/StaminaHandler.c:1075-1083:
        // public Get/SetStamina; Set synchronizes via SyncStaminaEx (:825-838).
        StaminaHandler stamina = GetStaminaHandler();
        if (!stamina)
            return;

        float before = stamina.GetStamina();
        float cost = settings.BlockStaminaCost;
        stamina.SetStamina(Math.Clamp(before - cost, 0, before));
        HCMeleeLog.Event("block_cost", "before=" + before + " cost=" + cost);

        if (before < cost && settings.GuardBreak && settings.GuardBreakChipFraction > 0)
        {
            // P6's HCMeleeChip encodes the default half-light-hit chip (~3.5 Health).
            // Scale relative to that 0.5 default, rather than halving it a second time.
            // 3_Game/Entities/Object.c:1128-1138: damageCoef multiplies applied damage.
            float chipCoef = settings.GuardBreakChipFraction / 0.5;
            ProcessDirectDamage(DT_CUSTOM, infected, "Torso", "HCMeleeChip", modelPos, chipCoef, 0);
            HCMeleeLog.Event("guard_break", "chip_coef=" + chipCoef);
        }
    }

    // 3_Game/Entities/Object.c:1144-1147: a false result vetoes damage.
    override bool EEOnDamageCalculated(TotalDamageResult damageResult, int damageType, EntityAI source, int component, string dmgZone, string ammo, vector modelPos, float speedCoef)
    {
        if (!GetGame().IsServer())
            return super.EEOnDamageCalculated(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);

        bool allowed = super.EEOnDamageCalculated(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);
        if (!allowed)
            return false;
        if (!HCMeleeModule.Active() || HCMeleeAmmo.IsHC(ammo) || damageType != DT_CLOSE_COMBAT)
            return true;

        ZombieBase infected = ZombieBase.Cast(source);
        if (!infected || HCMeleeAmmo.IsBlockedInfectedAmmo(ammo))
            return true;

        int weakArms = infected.HCMeleeWeakArms();
        if (weakArms <= 0)
            return true;

        HCMeleeSettings settings = HCMeleeConfig.HCGet();
        if (!settings.ArmWeaken)
            return true;

        // 1_Core/proto/EnMath.c:126,540: bounded probability and native RNG.
        float chance = Math.Clamp(settings.ArmGlanceChance * weakArms, 0, 1);
        if (Math.RandomFloat01() < chance)
        {
            HCMeleeLog.Event("glance", "weak_arms=" + weakArms);
            return false;
        }
        return true;
    }
}
