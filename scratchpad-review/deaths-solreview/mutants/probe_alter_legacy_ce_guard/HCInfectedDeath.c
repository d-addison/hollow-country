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
        return FileExist("$profile:HollowCountry/acceptance/infected_deaths.enable");
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
                Print("[HollowCountry] Infected deaths EXPERIMENTAL local acceptance opt-in active; runtime acceptance PENDING");
            }
            else
            {
                Print("[HollowCountry] Infected deaths not admitted; runtime acceptance PENDING");
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
        int ammoHitAnimation = GetGame().ConfigGetInt("cfgAmmo " + data.m_AmmoType + " hitAnimation");
        pAnimType = HCInfectedDeathPolicy.SelectDeathType(nativeType, IsBeingBackstabbed(), ammoHitAnimation, m_HeavyHitOverride, data.m_DamageZone, pAnimHitDir);
        HCInfectedDeathLog.Decision(data.m_AmmoType, data.m_DamageZone, nativeType, pAnimType, pAnimHitDir);
        return result;
    }
}
