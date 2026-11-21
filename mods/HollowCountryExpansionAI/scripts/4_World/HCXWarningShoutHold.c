// Original adapter; installed Expansion interfaces only, no provider code.
// ai_scripts.pbo/4_World/DayZExpansion_AI/Entities/AI/eAIBase.c:
// eAI_UpdateFSM:7071; eAI_CanFire:1276; RaiseWeapon:9755 clears queued shots;
// AimAtPosition:9944; LookAtPosition:9937. Target/LOS APIs: HCXStance.c header.
modded class eAIBase
{
    PlayerBase HCXWarningPlayer;
    PlayerBase HCXWarningShotPlayer;
    int HCXWarningSeen;
    int HCXWarningStarted;
    bool HCXWarningPending;

    bool HCXWarningBlocked()
    {
        if (!GetGame() || !GetGame().IsServer() || !HCXWarningPlayer) { return false; }
        if (!HCXStance.Owns(this) || HCXLivingRefused || HCXAIQualification.ProviderProblem() != "") { return false; }
        int age = GetGame().GetTime() - HCXWarningSeen;
        eAITarget target = GetTarget();
        if (age < 0 || age > 2000 || !target || target.GetEntity() != HCXWarningPlayer || !eAI_HasLOS()) { return false; }
        if (!IsAlive() || IsUnconscious() || IsRestrained() || !HCXWarningPlayer.IsAlive()) { return false; }
        if (HCXStance.Relation(this, HCXWarningPlayer) < 0 || HCXStance.RaisedWeapon(HCXWarningPlayer)) { return false; }
        float distance = vector.Distance(GetPosition(), HCXWarningPlayer.GetPosition());
        if (distance <= 40 || distance > 80 || HCXDefence.Hostile(this, HCXWarningPlayer, target)) { return false; }
        return true;
    }

    override bool eAI_CanFire(Weapon_Base weapon)
    {
        if (HCXWarningBlocked()) { HCReached.Mark("ai.warning_fire_hold"); return false; }
        return super.eAI_CanFire(weapon);
    }

    override void eAI_UpdateFSM(float pDt, int simulationPrecision)
    {
        // Perception/navigation/FSM continue; only normal fire at this contact is held.
        super.eAI_UpdateFSM(pDt, simulationPrecision);
        if (!HCXWarningBlocked()) { HCXWarningPending = false; return; }
        vector aim = HCXWarningPlayer.GetPosition() + Vector(0, 1.2, 0);
        LookAtPosition(aim);
        AimAtPosition(aim);
        if (CanRaiseWeapon()) { RaiseWeapon(true); }
        if (!HCXWarningPending) { return; }
        if (HCXWarningShotPlayer != HCXWarningPlayer) { HCXWarningPending = false; return; }
        int elapsed = GetGame().GetTime() - HCXWarningStarted;
        if (elapsed < 1500) { return; }
        // Exactly one attempt per admitted warning, including empty/unsafe fallback.
        HCXWarningPending = false;
        Weapon_Base weapon = Weapon_Base.Cast(GetHumanInventory().GetEntityInHands());
        if (!weapon || !super.eAI_CanFire(weapon))
        {
            Print("[HollowCountry] Stance warning_shot fallback=no_ready_firearm");
            return;
        }
        HCXWarningShot.Fire(this, HCXWarningPlayer, weapon);
    }
}
