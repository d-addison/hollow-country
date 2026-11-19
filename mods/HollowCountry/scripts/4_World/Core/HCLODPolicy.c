// #135 shared level-of-detail policy. Scalar rules only: no entities, players,
// files or engine calls, so every LOD consumer (infected today) shares one
// definition of the tiers and of "far", "hidden" and "safe to fold".
// Native math: scripts-1.30.164289/1_Core/proto/EnMath.c:553 Min, :566 Max.
// All ranges, speeds and caps are provisional until measured with 3-6 players;
// runtime acceptance pending.
class HCLODPolicy
{
    // Tiers: virtual = data only, far from every player; idle = posed or
    // dormant at middle range; full = native AI near players.
    static const int TIER_VIRTUAL = 0;
    static const int TIER_IDLE = 1;
    static const int TIER_FULL = 2;

    // Fold outcomes for a materialized herd member.
    static const int FOLD_KEEP = 0;
    static const int FOLD_NOW = 1;
    static const int FOLD_DEAD = 2;
    static const int FOLD_RELEASE = 3;

    // Fastest observer assumed between two distance samples (vehicles
    // included) and the oldest sample a consumer may reuse.
    // A member hit within this many seconds is never folded.
    // Structural caps: snapshot players, persisted herds and head count.
    static const int MAX_PLAYERS = 64;
    static const int MAX_HERDS = 16;
    static const int MAX_HEAD = 64;
    static const int MAX_TRACKED = 24;
    static const int MAX_BUDGET = 24;
    static const float WORLD_SIZE = 15360.0;

    // Unknown (negative) distance never degrades: it stays full AI.
    static int Tier(float distance, float fullRange, float idleRange)
    {
        if (!(distance >= 0)) { return HCLODPolicy.TIER_FULL; }
        if (distance <= fullRange) { return HCLODPolicy.TIER_FULL; }
        if (distance <= idleRange) { return HCLODPolicy.TIER_IDLE; }
        return HCLODPolicy.TIER_VIRTUAL;
    }

    // True only when a fresh sampled nearest-player distance proves no player
    // can be within radius now, even closing at MAX_OBSERVER_SPEED.
    static bool SafelyFar(float sampledDistance, float age, float radius)
    {
        if (!(sampledDistance >= 0) || !(age >= 0)) { return false; }
        if (age > HCInfectedTuning.Get().LevelOfDetail.SampleAge) { return false; }
        return sampledDistance - age * HCInfectedTuning.Get().LevelOfDetail.ObserverSpeed > radius;
    }

    // Bodies a herd wants in the world: its nearest members, only while a
    // player is within materialize range, never more than its living count.
    static int DesiredMembers(int alive, float nearest, float materializeRange, int perHerd)
    {
        if (!(nearest >= 0) || nearest > materializeRange) { return 0; }
        return Math.Max(0, Math.Min(alive, perHerd));
    }

    static bool MayMaterialize(int desired, int leasedHerd, int leasedTotal, int maxTotal, int tracked, int trackedCap)
    {
        if (leasedHerd >= desired) { return false; }
        if (leasedTotal >= maxTotal) { return false; }
        return tracked < trackedCap;
    }

    // A spawn point is hidden only beyond the minimum distance from every
    // player and with every observer inside visibility range occluded.
    static bool SpawnHidden(float nearest, float minSpawn, int observers, int occluded, int maxObservers)
    {
        if (!(nearest > minSpawn)) { return false; }
        if (observers > maxObservers) { return false; }
        return occluded >= observers;
    }

    // Never fold a body a player can see, is fighting, that is alerted or
    // chasing, was hit recently, or that a horde has claimed.
    static int FoldDecision(bool alive, bool calm, float sinceHit, bool claimed, float nearest, float foldRange, int observers, int occluded, int maxObservers)
    {
        if (!alive) { return HCLODPolicy.FOLD_DEAD; }
        if (claimed) { return HCLODPolicy.FOLD_RELEASE; }
        if (!calm) { return HCLODPolicy.FOLD_KEEP; }
        if (sinceHit >= 0 && sinceHit < HCInfectedTuning.Get().LevelOfDetail.HitQuiet) { return HCLODPolicy.FOLD_KEEP; }
        if (!(nearest > foldRange)) { return HCLODPolicy.FOLD_KEEP; }
        if (observers > maxObservers || occluded < observers) { return HCLODPolicy.FOLD_KEEP; }
        return HCLODPolicy.FOLD_NOW;
    }

    // One head back per period, only while the whole herd is data.
    static bool MayRegrow(int alive, int headCount, int leased, float elapsed, float regrowSeconds)
    {
        if (!(regrowSeconds > 0) || leased > 0) { return false; }
        if (alive >= headCount) { return false; }
        return elapsed >= regrowSeconds;
    }

    static bool ValidRanges(float fullRange, float idleRange, float minSpawn, float materializeRange, float foldRange, float visibility)
    {
        if (!(fullRange > 0) || !(idleRange > fullRange) || idleRange > 2000) { return false; }
        if (!(minSpawn >= 60) || !(materializeRange > minSpawn)) { return false; }
        if (!(foldRange > materializeRange) || !(visibility >= foldRange)) { return false; }
        return visibility <= 3000;
    }

    static bool ValidCaps(int classify, int maxMaterialized, int perHerd, int posed, int posedFull, int posedIdle, int herds)
    {
        if (classify < 1 || classify > HCLODPolicy.MAX_TRACKED) { return false; }
        if (maxMaterialized < 0 || maxMaterialized > HCLODPolicy.MAX_TRACKED) { return false; }
        if (perHerd < 1 || perHerd > 12) { return false; }
        if (posed < 0 || posed > HCLODPolicy.MAX_BUDGET) { return false; }
        if (posedFull < 0 || posedFull > HCLODPolicy.MAX_BUDGET) { return false; }
        if (posedIdle < 0 || posedIdle > HCLODPolicy.MAX_BUDGET) { return false; }
        return herds >= 0 && herds <= HCLODPolicy.MAX_HERDS;
    }

    static bool ValidHerd(float x, float z, float radius, int headCount, int alive)
    {
        if (!(x >= 0) || !(x <= HCLODPolicy.WORLD_SIZE)) { return false; }
        if (!(z >= 0) || !(z <= HCLODPolicy.WORLD_SIZE)) { return false; }
        if (!(radius >= 10) || !(radius <= 200)) { return false; }
        if (headCount < 1 || headCount > HCLODPolicy.MAX_HEAD) { return false; }
        return alive >= 0 && alive <= headCount;
    }
}
