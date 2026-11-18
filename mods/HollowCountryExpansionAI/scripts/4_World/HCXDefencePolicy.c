// HCX self-defence pure policy (owner bug 2026-11-18). Numbers only: no native
// API, entity or identity, so the offline smoke can execute every rule. Synthetic
// results are not native acceptance; hostility, noise and impact behaviour stay
// runtime-pending until a server session is observed.
// Proportional response: a hit holds a grudge for minutes, a kill a little
// longer, a near miss only briefly. Every grudge expires; none is server-wide.
class HCXDefencePolicy
{
    static const int KIND_HIT = 1;
    static const int KIND_KILL = 2;
    static const int KIND_MISS = 3;
    static const int KIND_RESCUE = 4;
    static const int NEAR_NONE = 0;
    static const int NEAR_PASS = 1;
    static const int NEAR_CLOSE = 2;
    static const int GRUDGE_CAP = 64;
    static const int SHOT_WINDOW_CAP = 6;
    static const int SHOT_SPACING_MS = 750;
    static const int LOS_MEMORY_MS = 15000;
    static const int SEED_WINDOW_MS = 20000;
    static const int RESCUE_WINDOW_MS = 30000;
    static const int RAYCASTS_PER_SHOT = 4;
    static const float INFECTED_RADIUS = 25.0;
    static const float PASS_RADIUS = 4.0;
    static const float PASS_REACH = 200.0;
    static const float PASS_MARGIN = 2.0;
    static const float CLOSE_RADIUS = 12.0;
    static const float FIGHT_THREAT = 0.6;
    static const float ORIGIN_REACH = 150.0;

    // Milliseconds a grudge lasts after the last aggression of this kind.
    static int HoldMs(int kind)
    {
        if (kind == HCXDefencePolicy.KIND_KILL) { return 300000; }
        if (kind == HCXDefencePolicy.KIND_HIT) { return 240000; }
        if (kind == HCXDefencePolicy.KIND_MISS) { return 90000; }
        if (kind == HCXDefencePolicy.KIND_RESCUE) { return 30000; }
        return 0;
    }

    // A grudge applies only until its deadline, only near where it happened, and
    // only to an actor that perceived the attacker: live LOS, LOS within
    // LOS_MEMORY_MS, or the short native hit-direction window after Expansion
    // itself seeded this very actor (seededAtMs). The Expansion seeded flag is not
    // perception, so it is never an input here.
    static bool Active(int nowMs, int untilMs, float distanceToOrigin, bool los, int lastLosMs, int seededAtMs)
    {
        if (untilMs <= 0 || nowMs >= untilMs) { return false; }
        if (distanceToOrigin != distanceToOrigin || distanceToOrigin > HCXDefencePolicy.ORIGIN_REACH) { return false; }
        if (los) { return true; }
        if (lastLosMs > 0 && nowMs >= lastLosMs && nowMs - lastLosMs <= HCXDefencePolicy.LOS_MEMORY_MS) { return true; }
        if (seededAtMs > 0 && nowMs >= seededAtMs && nowMs - seededAtMs <= HCXDefencePolicy.SEED_WINDOW_MS) { return true; }
        return false;
    }

    // First non-lethal hit on a friendly or allied actor while infected are near
    // is a stray rescue round: excused once per RESCUE_WINDOW_MS. priorUntilMs is
    // the deadline of the latest record for this group and player (0 when none);
    // a real grudge or an unexpired excuse makes the next hit count.
    static bool RescueHitExcused(bool friendly, int infectedNear, bool lethal, int nowMs, int priorUntilMs)
    {
        if (!friendly || lethal || infectedNear <= 0) { return false; }
        return nowMs >= priorUntilMs;
    }

    // End of the near-miss ray: the first raycast hit plus a small margin, never
    // beyond PASS_REACH. A negative or zero hit distance means no hit.
    static float PassEnd(float hitDistance)
    {
        if (hitDistance != hitDistance || hitDistance <= 0) { return HCXDefencePolicy.PASS_REACH; }
        return Math.Min(HCXDefencePolicy.PASS_REACH, hitDistance + HCXDefencePolicy.PASS_MARGIN);
    }

    // Lifts a watching or eyeballing actor to the fight threat; never lowers a
    // stronger native threat.
    static float Threat(float baseThreat, bool active)
    {
        if (!active) { return baseThreat; }
        return Math.Max(baseThreat, HCXDefencePolicy.FIGHT_THREAT);
    }

    // A shot near a person who is also being attacked by infected is a rescue,
    // not aggression: any infected near the shooter or the actor excuses it.
    static bool Excused(int infectedNearShooter, int infectedNearActor)
    {
        return infectedNearShooter > 0 || infectedNearActor > 0;
    }

    // along: metres along the shot ray to the point closest to the actor;
    // perp: perpendicular metres from the ray to the actor; shooterDistance:
    // metres shooter to actor. A bullet passing within PASS_RADIUS is a near
    // miss only before passEnd (the bullet's first hit); a loud weapon fired within CLOSE_RADIUS of the actor is a close shot.
    static int Classify(float along, float perp, float shooterDistance, bool loud, float passEnd)
    {
        if (along != along || perp != perp || shooterDistance != shooterDistance) { return HCXDefencePolicy.NEAR_NONE; }
        if (along > 0 && along <= passEnd && perp <= HCXDefencePolicy.PASS_RADIUS) { return HCXDefencePolicy.NEAR_PASS; }
        if (loud && shooterDistance <= HCXDefencePolicy.CLOSE_RADIUS) { return HCXDefencePolicy.NEAR_CLOSE; }
        return HCXDefencePolicy.NEAR_NONE;
    }

    // Per-player spacing and a shared window cap bound the near-miss work.
    static bool ShotAllowed(int nowMs, int nextMs, int windowCount, int windowCap)
    {
        if (nowMs < nextMs) { return false; }
        if (windowCount >= windowCap) { return false; }
        return true;
    }

    // Index of the grudge to replace when the store is full (the oldest), else -1.
    static int EvictIndex(int count, int cap)
    {
        if (count < cap) { return -1; }
        return 0;
    }
}
