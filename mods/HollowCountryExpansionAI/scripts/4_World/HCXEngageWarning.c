// #276: give the existing HCXWarningShout a finite lead before engagement.
// Original adapter; installed provider scripts inspected for interfaces only.
// Expansion ai_scripts.pbo, 4_World/DayZExpansion_AI/Entities/AI/eAIBase.c:
// eAI_Targeting:6941 updates LOS before eAI_OnUpdate:7036 returns to aiming;
// eAI_UpdateFSM:7071 runs the FSM; eAI_CanFire:1276 guards TryFireWeapon:1138;
// CanRaiseWeapon:9743 and RaiseWeapon:9755 own raising/queued-shot cancellation.
// Classes/Targets/eAITarget.c derives from eAITargetInformationState.
// Native sound: MeleeAttackHeavyEvent maps MELEE_ATTACK_HEAVY to voice class 17
// (4_World/Classes/SoundEvents/PlayerSoundEvents/Events/MeleeAttack.c).
// HCXWarningShout already requests that voice event after fresh LOS, within
// 80 m, before combat/raising, with 60 s per-actor and per-player cooldowns
// (64-player cap). Reuse its receipt: no second sound, timer or player table.
// Client audibility and ordering remain runtime=PENDING until native testing.
modded class eAIBase
{
    protected static const int HCX_ENGAGE_WARNING_LEAD_MS = 1500;
    protected bool m_HCXEngageWarningConsumed;
    protected int m_HCXEngageWarningStamp;
    protected PlayerBase m_HCXEngageWarningPlayer;

    // Called at the native combat boundaries rather than wrapping targeting:
    // every modded targeting layer must finish before we consume its receipt.
    // One weak contact per actor; no scans, callbacks, persistence or new senses.
    protected bool HCXEngageWarningBlocked()
    {
        if (!GetGame() || !GetGame().IsServer() || !HCWarningActor) { return false; }
        int now = GetGame().GetTime();
        eAITarget target = GetTarget();
        if (m_HCHasWarned && (!m_HCXEngageWarningConsumed || m_HCXEngageWarningStamp != m_HCWarningTime))
        {
            m_HCXEngageWarningConsumed = true;
            m_HCXEngageWarningStamp = m_HCWarningTime;
            m_HCXEngageWarningPlayer = null;
            int age = now - m_HCWarningTime;
            // Only a newly requested, actually observed contact can arm a hold.
            // Expired receipts cannot create a late pause or replay a warning.
            if (age >= 0 && age < HCX_ENGAGE_WARNING_LEAD_MS && target && target.GetEntity() == m_HCWarningContact && eAI_HasLOS())
            {
                m_HCXEngageWarningPlayer = m_HCWarningContact;
            }
        }
        if (!m_HCXEngageWarningPlayer) { return false; }
        int elapsed = now - m_HCXEngageWarningStamp;
        if (elapsed < 0 || elapsed >= HCX_ENGAGE_WARNING_LEAD_MS || !IsAlive() || IsUnconscious() || IsRestrained())
        {
            m_HCXEngageWarningPlayer = null;
            return false;
        }
        // Other perceived targets retain ordinary defence. A switch back within
        // the original lead does not restart or lengthen that lead.
        if (!target || target.GetEntity() != m_HCXEngageWarningPlayer) { return false; }
        // Reuse the owning defence classifier, including its perception and
        // rescue-shot rules. An accepted hit/kill/near miss cancels this hold.
        if (HCXDefence.Hostile(this, m_HCXEngageWarningPlayer, target))
        {
            m_HCXEngageWarningPlayer = null;
            return false;
        }
        HCReached.Mark("ai.warning_fire_hold");
        return true;
    }

    override void eAI_UpdateFSM(float pDt, int simulationPrecision)
    {
        if (HCXEngageWarningBlocked()) { RaiseWeapon(false); }
        // Keep navigation, perception and the provider FSM running normally.
        super.eAI_UpdateFSM(pDt, simulationPrecision);
    }

    override bool CanRaiseWeapon()
    {
        if (HCXEngageWarningBlocked()) { return false; }
        return super.CanRaiseWeapon();
    }

    override void RaiseWeapon(bool up = true)
    {
        if (up && HCXEngageWarningBlocked()) { up = false; }
        // Native lowering clears queued shots, including queued bursts.
        super.RaiseWeapon(up);
    }

    override bool eAI_CanFire(Weapon_Base weapon)
    {
        if (HCXEngageWarningBlocked())
        {
            RaiseWeapon(false);
            return false;
        }
        return super.eAI_CanFire(weapon);
    }
}
