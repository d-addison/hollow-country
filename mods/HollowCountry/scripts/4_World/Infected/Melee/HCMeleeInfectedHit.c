// Native evidence (scripts-1.30.164289, paths relative to the scripts root):
// 4_World/Entities/Creatures/Infected/ZombieBase.c:981-1012 EEHitBy;
// :826-850 crawl selection from a zero-health leg; :1090 IsCrawling.
// 3_Game/Entities/DayZInfected.c:138-177 preserves the original killer source.
// 3_Game/Entities/Object.c:1-7 transfer flags; :517 IsAlive;
// :1129-1138 damageCoef multiplies applied ammo damage (model-space hit).
// 3_Game/DamageSystem.c:1-4 TotalDamageResult.GetDamage.
// 3_Game/Global/Game.c:1120 IsServer; :1535 GetTime (milliseconds).
modded class ZombieBase
{
    override void EEHitBy(TotalDamageResult damageResult, int damageType, EntityAI source, int component, string dmgZone, string ammo, vector modelPos, float speedCoef)
    {
        if (!GetGame().IsServer())
        {
            super.EEHitBy(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);
            return;
        }
        super.EEHitBy(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);

        // Keep super on nested HC hits: native crawl/death selection must still run.
        if (!HCMeleeModule.Active() || damageType != DT_CLOSE_COMBAT || HCMeleeAmmo.IsHC(ammo) || !IsAlive())
            return;

        PlayerBase attacker = HCMeleeTarget.Attacker(source);
        if (!HCMeleeTarget.Plausible(attacker, this, dmgZone, modelPos))
        {
            HCMeleeLog.Event("implausible", "zone=" + dmgZone);
            return;
        }
        if (!attacker || !source)
            return;

        HCMeleeSettings settings = HCMeleeConfig.HCGet();
        bool heavy = HCMeleeAmmo.IsHeavy(ammo);
        float ammoDamage = HCMeleeAmmo.HealthDamage(ammo);

        if (settings.HeadExecute && dmgZone == "Head")
        {
            float armour = HCMeleeTarget.HeadArmour(this);
            float multiplier = 1.0;
            string headEvent = "";
            if (heavy && ammoDamage >= settings.HeadExecuteMinHeavyDamage)
            {
                if (armour < settings.HeadArmoredThreshold)
                {
                    multiplier = settings.HeadArmoredHeavyMultiplier;
                    headEvent = "head_armored";
                }
                else
                {
                    ProcessDirectDamage(DT_CUSTOM, source, "Head", "HCMeleeExecute", modelPos, 1.0, 0);
                    HCMeleeLog.Event("head_execute", "zone=Head");
                }
            }
            else if (!heavy)
            {
                multiplier = settings.HeadLightMultiplier;
                headEvent = "head_light";
            }

            if (headEvent != "" && multiplier > 1.0 && damageResult && armour > 0)
            {
                // P6's HCMeleeExecute must use DamageApplied type="Melee".
                // GetDamage supplies the original hit's dealt head damage. Divide
                // the desired extra by the synthetic ammo's armoured damage at
                // coef=1, rather than applying the armour reduction twice.
                // Native declares the multiplier; exact DT_CUSTOM scaling and
                // synchronous EEHitBy re-entry remain engine acceptance checks.
                float executeDamage = HCMeleeAmmo.HealthDamage("HCMeleeExecute");
                float extraDamage = (multiplier - 1.0) * damageResult.GetDamage("Head", "Health");
                if (executeDamage > 0 && extraDamage > 0)
                {
                    float damageCoef = extraDamage / (executeDamage * armour);
                    ProcessDirectDamage(DT_CUSTOM, source, "Head", "HCMeleeExecute", modelPos, damageCoef, 0);
                    HCMeleeLog.Event(headEvent, "zone=Head");
                }
            }
        }
        else if (settings.LegCripple && (dmgZone == "LeftLeg" || dmgZone == "RightLeg"))
        {
            if (!IsCrawling() && heavy && ammoDamage >= settings.LegCrippleMinHeavyDamage)
            {
                ProcessDirectDamage(DT_CUSTOM, source, dmgZone, "HCMeleeCripple", modelPos, 1.0, ProcessDirectDamageFlags.NO_GLOBAL_TRANSFER);
                HCMeleeLog.Event("cripple", "zone=" + dmgZone);
            }
        }
        else if (settings.ArmWeaken && (dmgZone == "LeftArm" || dmgZone == "RightArm"))
        {
            // Compare state, so this also tolerates the package contract's
            // void/bool return-type typo for HCMeleeMarkArmHit.
            int weakArmsBefore = HCMeleeWeakArms();
            HCMeleeMarkArmHit(dmgZone == "LeftArm", heavy, settings.ArmWeakLightHits);
            if (HCMeleeWeakArms() > weakArmsBefore)
                HCMeleeLog.Event("arm_weak", "zone=" + dmgZone);
        }

        // A bonus may have killed the target or scheduled a crawl in nested
        // vanilla EEHitBy. Do not leave a counter stagger pending in either case.
        if (settings.BlockCounter && IsAlive() && !IsCrawling() && m_CrawlTransition == -1)
        {
            float now = GetGame().GetTime() * 0.001;
            if (attacker.HCMeleeConsumeCounter(this, now, settings.CounterWindowSeconds))
            {
                m_HCMeleeCounterPending = true;
                HCMeleeLog.Event("counter", "zone=" + dmgZone);
            }
        }
    }
}
