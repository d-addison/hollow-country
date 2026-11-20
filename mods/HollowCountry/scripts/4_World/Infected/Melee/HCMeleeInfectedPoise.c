// Native evidence relative to scripts-1.30.164289:
// 4_World/Entities/Creatures/Infected/ZombieBase.c:610 cooldown field,
// :716/:761 attack cooldown assignments, :735-738 cooldown decrement,
// :858-865 hit fields, :867-897 hit processing and native 0.3 s throttle.
// 3_Game/Entities/DayZAnimal.c:175 ModCommandHandlerBefore signature;
// 3_Game/Entities/DayZInfected.c:111 StartCommand_Hit (called only by super).
// 3_Game/Global/Game.c:914 GetTickTime, :1120 IsServer.
// Shared P1 state/config/log API; no gameplay acceptance is inferred here.
modded class ZombieBase
{
    override bool HandleDamageHit(int pCurrentCommandID)
    {
        if (!GetGame().IsServer()) { return super.HandleDamageHit(pCurrentCommandID); }
        if (!HCMeleeModule.Active()) { return super.HandleDamageHit(pCurrentCommandID); }

        // A counter is consumed with its queued hit even if native throttling
        // discards that hit. It cannot leak onto a later unrelated hit.
        if (m_DamageHitToProcess && m_HCMeleeCounterPending)
        {
            m_DamageHitHeavy = true;
            m_HCMeleeCounterPending = false;
        }

        // Leave the native throttle in sole control of its elapsed time and
        // discard path. Neither resisted hits nor throttled hits count.
        if (pCurrentCommandID == DayZInfectedConstants.COMMANDID_HIT && m_HitElapsedTime < HIT_INTERVAL_MIN)
        {
            return super.HandleDamageHit(pCurrentCommandID);
        }
        if (!m_DamageHitToProcess) { return super.HandleDamageHit(pCurrentCommandID); }

        HCMeleeSettings settings = HCMeleeConfig.HCGet();
        bool lightHit = !m_DamageHitHeavy;
        float now = GetGame().GetTickTime();
        if (settings.InfectedPoise)
        {
            if (now - m_HCMeleePoiseWindowStart >= settings.InfectedPoiseWindowSeconds)
            {
                m_HCMeleePoiseCount = 0;
                m_HCMeleePoiseWindowStart = now;
            }
            if (lightHit && m_HCMeleePoiseCount >= settings.InfectedPoiseLightStaggers)
            {
                m_DamageHitToProcess = false;
                m_ShockDamage = 0;
                HCMeleeLog.Event("poise_resist", "");
            }
        }

        bool processed = super.HandleDamageHit(pCurrentCommandID);
        // processed also excludes an already-zero elapsed time with no new
        // command (for example a resisted hit). Heavy/counter hits never count.
        if (settings.InfectedPoise && processed && lightHit && m_HitElapsedTime == 0)
        {
            if (m_HCMeleePoiseCount == 0) { m_HCMeleePoiseWindowStart = now; }
            m_HCMeleePoiseCount++;
        }
        return processed;
    }

    override bool ModCommandHandlerBefore(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)
    {
        if (!GetGame().IsServer()) { return super.ModCommandHandlerBefore(pDt, pCurrentCommandID, pCurrentCommandFinished); }
        bool consumed = super.ModCommandHandlerBefore(pDt, pCurrentCommandID, pCurrentCommandFinished);
        if (!HCMeleeModule.Active()) { return consumed; }

        int weakArms = HCMeleeWeakArms();
        if (weakArms > 0)
        {
            if (m_AttackCooldownTime > m_HCMeleeCooldownSeen + 0.01)
            {
                HCMeleeSettings settings = HCMeleeConfig.HCGet();
                if (settings.ArmWeaken)
                {
                    float multiplier = settings.ArmWeakCooldownMultiplier;
                    if (weakArms == 2) { multiplier *= settings.ArmWeakCooldownMultiplier; }
                    if (multiplier > 2.25) { multiplier = 2.25; }
                    m_AttackCooldownTime *= multiplier;
                }
            }
        }
        // Observe even healthy arms; storing the scaled value prevents
        // compounding on the next command tick. Reach's return is unchanged.
        m_HCMeleeCooldownSeen = m_AttackCooldownTime;
        return consumed;
    }
}
