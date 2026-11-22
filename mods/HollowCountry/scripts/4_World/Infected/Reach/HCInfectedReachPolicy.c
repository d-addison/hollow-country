// #137 infected anti-cheese: pure decision rules. No engine calls. Thresholds follow
// the installed vanilla tables in scripts-1.30.164289: 3_Game/Entities/DayZInfectedType.c
// :80-81 FIGHT up attacks reach 1.7 m at pitch 1; 4_World/Entities/Creatures/Infected/
// ZombieBase.c:401-411 GetVaultType bands (<=0.6 type 0, <=1.1 type 1, <=1.6 type 2,
// else 3; the module calls that vanilla method directly) and :768 GetAttackPitch
// (infected head at +1.8 m, 0.3 m centre band). These rules prove nothing about native
// animation, landing or damage behaviour.
class HCInfectedReachPolicy
{
    // HC-47 / #121. Legacy scalar experiments below are retained for traceability,
    // but callers must consume these effective flags. A sampled floor/navmesh
    // point or room anchor is not a traversal/landing/damage receipt.
    // Q3: the two fixes are settings (InfectedClimb.LegStrikes / InfectedClimb.BackOff, default on),
    // read once by HCInfectedClimbConfig.HCLoad. Leg strikes keep the ray-line guard in MayStrike;
    // the back-off steers only through the native controller overrides and releases on its own.
    static const string HC_LEG_STRIKES_REFUSAL = "disabled_by_setting";
    protected static bool s_HCLegStrikes = true;
    protected static bool s_HCBackOff = true;
    static void HCSetFixes(bool legStrikes, bool backOff)
    {
        s_HCLegStrikes = legStrikes;
        s_HCBackOff = backOff;
    }
    static bool HCExtendedReachSupported() { return s_HCLegStrikes; }
    static bool HCForcedMovementSupported() { return s_HCBackOff; }

    // Existing LineCheck endpoint defaults, not a new sensing/reach range.
    // Origin follows vanilla ZombieBase.c:774 GetAttackPitch (+1.8 m);
    // target shin (+0.5 m) reuses ReachModule.LineCheck, geometry unqualified.
    static const vector HC_CONTACT_ORIGIN_OFFSET = "0 1.8 0";
    static const vector HC_CONTACT_TARGET_OFFSET = "0 0.5 0";

    protected static ref HCUnitBudget s_HCThreatBudget;
    protected static float s_HCThreatBudgetAfter;

    // At most 16 extra contact rays per running-server second (existing reach
    // slot cap). No observer scan, recurring job, save loop or new distance.
    // Game.c:914 GetTickTime, :1120 IsServer (installed 1.30.164289).
    static bool HCThreatTakeContact()
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        float now = GetGame().GetTickTime();
        if (!s_HCThreatBudget) { s_HCThreatBudget = new HCUnitBudget; }
        if (now >= s_HCThreatBudgetAfter)
        {
            s_HCThreatBudget.HCReset(16);
            s_HCThreatBudgetAfter = now + 1;
        }
        return s_HCThreatBudget.HCTake(1);
    }

    static void HCThreatResetBudget()
    {
        s_HCThreatBudget = null;
        s_HCThreatBudgetAfter = 0;
    }

    // Lead-owned module startup prints this AFTER observing vision admission.
    // This is a proposed diagnostic, never a native geometry acceptance receipt.
    static string HCThreatSummary(bool reachRequested)
    {
        string vision = HCInfectedVisionQualification.HCThreatState();
        if (!reachRequested)
        {
            return "[HC Plan] HC-47 reach=off vision=" + vision + " refusals=0 runtime=PENDING";
        }
        string line = "[HC Plan] HC-47 reach=on vision=" + vision;
        if (HCExtendedReachSupported()) { line = line + " extra_reach=on"; }
        else { line = line + " extra_reach=" + HCInfectedReachPolicy.HC_LEG_STRIKES_REFUSAL; }
        if (HCForcedMovementSupported()) { line = line + " forced_movement=native_overrides"; }
        else { line = line + " forced_movement=" + HCInfectedReachPolicy.HC_LEG_STRIKES_REFUSAL; }
        line = line + " climb=native_vault";
        return line + " rooms=" + HCInfectedRoomCatalog.HCThreatRoomReason() + " runtime=PENDING";
    }

    // Phases of the unreachable back-off. NONE also covers the cooldown.
    static int PhaseNone() { return 0; }
    static int PhaseRetreat() { return 1; }
    static int PhaseCircle() { return 2; }
    static int PhaseWait() { return 3; }

    static bool Elevated(float vertical)
    {
        return vertical >= HCInfectedTuning.Get().Reach.ElevatedMin && vertical <= HCInfectedTuning.Get().Reach.ElevatedMax;
    }

    // Vanilla keeps precedence: the reach strike only fills the gap where the
    // native attack logic refused an elevated target (3D distance or native
    // CanAttackToPosition). The line verdict comes from our own raycast.
    static bool MayStrike(float vertical, float horizontal, float reach, bool lineClear, bool lineFresh, bool cooled, bool vanillaCan)
    {
        if (vanillaCan || !lineClear || !lineFresh || !cooled)
        {
            return false;
        }
        if (!HCInfectedReachPolicy.Elevated(vertical))
        {
            return false;
        }
        return horizontal >= 0 && horizontal <= reach;
    }

    // First ray contact between infected head and target shin must be the
    // target itself or a surface within 0.3 m of the shin (the roof or deck
    // the player stands on). Anything earlier is a wall or floor.
    static bool LineClear(bool anyHit, bool hitTarget, float hitDistance, float segment)
    {
        if (!anyHit || hitTarget)
        {
            return true;
        }
        return hitDistance >= segment - 0.3;
    }

    // Climb (2026-11-20 owner report): a CHASE/FIGHT infected below an elevated
    // target plays the native vault command when the target is in the height band,
    // close horizontally, an obstacle blocks the way and no navmesh route exists.
    static bool ClimbBand(float vertical, float horizontal, float minHeight, float maxHeight, float maxHorizontal)
    {
        if (!(vertical >= minHeight) || !(vertical <= maxHeight)) { return false; }
        return horizontal >= 0 && horizontal <= maxHorizontal;
    }

    // Measured obstacle top above the infected's feet. Below 0.3 m is a kerb the
    // native walk already handles; above the band is a wall no vault clears.
    static bool ClimbObstacle(float height, float maxHeight)
    {
        return height >= 0.3 && height <= maxHeight;
    }

    static bool ClimbMayStart(float facing, float maxFacing, float now, float nextClimb, int concurrent, int maxConcurrent, bool retired)
    {
        if (retired || now < nextClimb || concurrent >= maxConcurrent) { return false; }
        return Math.AbsFloat(facing) <= maxFacing;
    }

    // A navmesh route reaches the target when its final waypoint lies within 1 m
    // horizontally and 0.7 m vertically of the sampled target (FindPath may return
    // a partial path that stops at the nearest reachable poly).
    static bool RouteReaches(vector finalWaypoint, vector goal)
    {
        float dx = finalWaypoint[0] - goal[0];
        float dz = finalWaypoint[2] - goal[2];
        if (dx * dx + dz * dz > 1.0) { return false; }
        return Math.AbsFloat(finalWaypoint[1] - goal[1]) <= 0.7;
    }

    // On top: the infected ended at least (height - 0.4 m), and at least 0.3 m,
    // above where it started. A landed vault with less rise went over the obstacle.
    static bool ClimbOnTop(float rise, float height)
    {
        float need = height - 0.4;
        if (need < 0.3) { need = 0.3; }
        return rise >= need;
    }

    // Retire for the session when the native command never ends on top.
    static bool ClimbRetired(int attempts, int onTop, int retireAttempts)
    {
        return attempts >= retireAttempts && onTop == 0;
    }

    static bool Unreachable(float vertical, float horizontal, bool offNavmesh, float sinceHit, float sinceAdmit)
    {
        if (!offNavmesh || horizontal > 4)
        {
            return false;
        }
        if (vertical < HCInfectedTuning.Get().Reach.ElevatedMin)
        {
            return false;
        }
        return sinceHit >= HCInfectedTuning.Get().Reach.UnreachableQuietSeconds && sinceAdmit >= HCInfectedTuning.Get().Reach.UnreachableQuietSeconds;
    }

    // RETREAT walks away until 3 m or 3 s, CIRCLE walks a tangent for 2 s,
    // WAIT faces the target for 3 s, then the infected is released (NONE).
    // Leaving the 2.5-4 m ring ends a moving phase early.
    static int NextPhase(int phase, float elapsed, float distance)
    {
        if (phase == 1)
        {
            if (distance >= 3 || elapsed >= 3)
            {
                return 2;
            }
            return 1;
        }
        if (phase == 2)
        {
            if (elapsed >= 2 || distance > 4)
            {
                return 3;
            }
            return 2;
        }
        if (phase == 3)
        {
            if (elapsed >= 3)
            {
                return 0;
            }
            return 3;
        }
        return 0;
    }

    // Native movement bands: 0 idle, 1 walk (3_Game/Entities/DayZInfected.c:20-26).
    static int PhaseSpeed(int phase)
    {
        if (phase == 1 || phase == 2)
        {
            return 1;
        }
        return 0;
    }

    // Absolute yaw in degrees, -180..180; the caller converts to radians.
    static float PhaseYaw(int phase, float toTargetYaw, int side)
    {
        float yaw = toTargetYaw;
        if (phase == 1)
        {
            yaw = toTargetYaw + 180;
        }
        if (phase == 2)
        {
            yaw = toTargetYaw + 90 * side;
        }
        // A non-finite or huge yaw would never normalise; NaN fails both loops.
        if (yaw > 1000 || yaw < -1000) { return 0; }
        while (yaw > 180)
        {
            yaw = yaw - 360;
        }
        while (yaw <= -180)
        {
            yaw = yaw + 360;
        }
        return yaw;
    }

    // Only a vehicle a target player occupies, or stands on while the leg
    // strike cannot reach them. Empty vehicles are never battered.
    static bool MayBatter(bool inVehicle, bool onVehicle, bool reachPossible, float contact, float now, float nextHit)
    {
        if (!inVehicle && !(onVehicle && !reachPossible))
        {
            return false;
        }
        return contact >= 0 && contact <= 1.8 && now >= nextHit;
    }

    static bool Keep(bool alive, bool sameTarget, bool engaged, float distance, float now, float expires)
    {
        if (!alive || !sameTarget || !engaged)
        {
            return false;
        }
        return distance <= 8 && now < expires;
    }
}
