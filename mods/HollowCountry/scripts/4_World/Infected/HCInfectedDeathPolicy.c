// #32 infected death selection policy: pure scalar decision, no engine access.
// Chooses between the two vanilla death animation variants only. It never
// applies an impulse, moves an actor or touches corpse, loot or cleanup.
// DEFAULT and IMPULSE visual differences are UNOBSERVED; see docs/INFECTED_DEATHS.md.
class HCInfectedDeathPolicy
{
    // Half-angle of the frontal cone. ComputeHitDirectionAngle reports 0 when
    // the source is in front of the infected and +-180 when behind (ZombieBase.c).
    static float FrontHalfAngle()
    {
        return 60.0;
    }

    static bool IsLegZone(string zone)
    {
        if (zone == "LeftLeg")
        {
            return true;
        }
        if (zone == "RightLeg")
        {
            return true;
        }
        return false;
    }

    static bool IsUpperZone(string zone)
    {
        if (zone == "Torso")
        {
            return true;
        }
        if (zone == "Head")
        {
            return true;
        }
        return false;
    }

    // Mirrors the vanilla heavy-hit test: ammo hitAnimation above zero or the
    // DayZInfected shock override.
    static bool IsHeavy(int ammoHitAnimation, bool heavyOverride)
    {
        if (ammoHitAnimation > 0)
        {
            return true;
        }
        return heavyOverride;
    }

    static bool IsFrontal(float hitDirection)
    {
        if (hitDirection != hitDirection)
        {
            return false;
        }
        return Math.AbsFloat(hitDirection) <= FrontHalfAngle();
    }

    // The only departure from vanilla: a heavy, frontal torso or head kill
    // that vanilla left on DEFAULT is upgraded to the native IMPULSE variant.
    // Finishers, leg kills, light or rear hits and any type vanilla already
    // chose other than DEFAULT are returned unchanged.
    static int SelectDeathType(int nativeType, bool finisher, int ammoHitAnimation, bool heavyOverride, string zone, float hitDirection)
    {
        if (finisher)
        {
            return nativeType;
        }
        if (nativeType != DayZInfectedDeathAnims.ANIM_DEATH_DEFAULT)
        {
            return nativeType;
        }
        if (IsLegZone(zone))
        {
            return DayZInfectedDeathAnims.ANIM_DEATH_DEFAULT;
        }
        if (!IsHeavy(ammoHitAnimation, heavyOverride))
        {
            return DayZInfectedDeathAnims.ANIM_DEATH_DEFAULT;
        }
        if (!IsFrontal(hitDirection))
        {
            return DayZInfectedDeathAnims.ANIM_DEATH_DEFAULT;
        }
        if (IsUpperZone(zone))
        {
            return DayZInfectedDeathAnims.ANIM_DEATH_IMPULSE;
        }
        return DayZInfectedDeathAnims.ANIM_DEATH_DEFAULT;
    }
}
