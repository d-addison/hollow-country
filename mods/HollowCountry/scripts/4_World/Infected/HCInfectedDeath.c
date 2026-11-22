// #32 supported infected death selection. Closed by default.
// Hook: ZombieBase.EvaluateDeathAnimationEx, called on the server from EEHitBy
// once the infected is no longer alive; vanilla CommandHandler then feeds the
// chosen type and direction to StartCommand_Death. Nothing else is touched:
// corpse, collision, loot, replication and cleanup stay on the vanilla path.
// Evidence and the unsupported list: docs/INFECTED_DEATHS.md.
class HCInfectedDeathQualification
{
    protected static bool s_Checked;
    protected static bool s_OptIn;

    // Evidence required: paired DayZDiag controls (vanilla vs selected) with a
    // rendered corpse, then a local-server run with one client.
    static bool Qualified()
    {
        return false;
    }

    static bool LocalAcceptanceOptIn()
    {
        return !FileExist("$profile:HollowCountry/acceptance/infected_deaths.disable");
    }

    static bool Admitted()
    {
        if (Qualified())
        {
            return true;
        }
        if (!s_Checked)
        {
            s_Checked = true;
            s_OptIn = LocalAcceptanceOptIn();
            if (s_OptIn)
            {
                Print("[HollowCountry] V1 admission feature=InfectedDeaths preference=on gate=infected_deaths qualified=0 result=admitted unverified: infected_deaths has no recorded native verdict; opt out with acceptance/infected_deaths.disable; EXPERIMENTAL; runtime acceptance PENDING");
            }
            else
            {
                Print("[HollowCountry] V1 admission feature=InfectedDeaths preference=off gate=infected_deaths qualified=0 result=off: operator opt-out acceptance/infected_deaths.disable; not admitted; runtime acceptance PENDING");
            }
        }
        return s_OptIn;
    }
}

class HCInfectedDeathLog
{
    protected static int s_Logged;

    static void Decision(string ammo, string zone, int nativeType, int selectedType, float hitDirection)
    {
        if (s_Logged < 16)
        {
            s_Logged++;
            string line = "[HollowCountry] Infected death ammo=" + ammo + " zone=" + zone;
            line = line + " native=" + nativeType.ToString() + " selected=" + selectedType.ToString();
            Print(line + " dir=" + hitDirection.ToString());
        }
    }
}

modded class ZombieBase
{
    override bool EvaluateDeathAnimationEx(EntityAI pSource, ZombieHitData data, out int pAnimType, out float pAnimHitDir)
    {
        bool result = super.EvaluateDeathAnimationEx(pSource, data, pAnimType, pAnimHitDir);
        if (!result || !data)
        {
            return result;
        }
        if (!GetGame().IsServer())
        {
            return result;
        }
        if (!HCInfectedDeathQualification.Admitted())
        {
            return result;
        }
        int nativeType = pAnimType;
        int ammoHitAnimation = HCConfigHelper.GetInt("cfgAmmo " + data.m_AmmoType + " hitAnimation", 0);
        pAnimType = HCInfectedDeathPolicy.SelectDeathType(nativeType, IsBeingBackstabbed(), ammoHitAnimation, m_HeavyHitOverride, data.m_DamageZone, pAnimHitDir);
        HCInfectedDeathLog.Decision(data.m_AmmoType, data.m_DamageZone, nativeType, pAnimType, pAnimHitDir);
        // #240: vanilla only plays IMPULSE together with dBodyApplyImpulse (doPhxImpulse ammo,
        // ZombieBase.c:370-388). Our upgrade played the IMPULSE clip with no impulse, so the
        // corpse tipped over stiffly from the feet. Apply the vanilla vertical impulse (80 * 1.5)
        // plus a small push away from the attacker, once, at death. Server only, no movement of
        // a live actor. Native: 1_Core/proto/EnPhysics.c:141 dBodyApplyImpulse;
        // 3_Game/Entities/EntityAI.c:879 GetHierarchyRoot; Object.c:287 GetPosition;
        // 1_Core/proto/EnConvert.c Normalize.
        if (pAnimType == DayZInfectedDeathAnims.ANIM_DEATH_IMPULSE && nativeType != DayZInfectedDeathAnims.ANIM_DEATH_IMPULSE)
        {
            vector push = "0 0 0";
            EntityAI attacker = pSource;
            if (pSource && pSource.GetHierarchyRoot()) { attacker = pSource.GetHierarchyRoot(); }
            if (attacker)
            {
                push = GetPosition() - attacker.GetPosition();
                push[1] = 0;
                if (push.Length() > 0.01) { push.Normalize(); }
                else { push = "0 0 0"; }
            }
            vector impulse = push * HCInfectedDeathPolicy.PushImpulse();
            impulse[1] = 80 * 1.5;
            dBodyApplyImpulse(this, impulse);
        }
        return result;
    }
}
