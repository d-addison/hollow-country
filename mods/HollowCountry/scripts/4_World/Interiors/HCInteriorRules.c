// Authored scalar algorithms: also exercised by HCInteriorSelfTests in DayZDiag.
// Schema 1: no automatic wipe, downgrade, migration or refill.
class HCInteriorRules
{
    static int Quantize(float value)
    {
        return Math.Floor(value * 100.0 + 0.5);
    }

    static int Yaw(float angle)
    {
        int turns = Math.Floor(angle / 360.0);
        return Quantize(angle - turns * 360.0) % 36000;
    }

    static int Layout(int x, int y, int z, int yaw, int seed)
    {
        int mixed = (Math.AbsInt(x) % 1009) * 31 + (Math.AbsInt(y) % 1009) * 17 + (Math.AbsInt(z) % 1009) * 13 + yaw + seed;
        return mixed % 3;
    }

    // 0 = empty, 1 = one Rag, 2 = one Battery9V. Fixed supplementary escrow.
    static int Allocation(int layout, int rags, int batteries)
    {
        if (rags < 0 || batteries < 0) return 0;
        if (layout == 0 && rags < 4) return 1;
        if (layout == 1 && batteries < 2) return 2;
        return 0;
    }

    // available -> reserved -> spent/quarantined. No reverse transition.
    static bool Transition(int before, int after)
    {
        return (before == 0 && after == 1) || (before == 1 && (after == 2 || after == 3));
    }

    static int Recover(bool exists, bool parses, int schema, int phase)
    {
        if (!exists) return 0;
        if (parses && schema == 1 && phase == 2) return 2;
        return 3;
    }

    static bool MaySearch(bool server, bool interiors, bool search, bool proof, bool ready, bool livePlayer, bool available)
    {
        return server && interiors && search && proof && ready && livePlayer && available;
    }

    // Only change alongside recorded runtime artifacts and normal signed-PBO tests.
    static bool PlacementAccepted()
    {
        return false;
    }

    static bool SearchAccepted()
    {
        return false;
    }

    static string TransformKey(vector position, vector orientation)
    {
        return Quantize(position[0]).ToString() + "_" + Quantize(position[1]).ToString() + "_" + Quantize(position[2]).ToString() + "_" + Yaw(orientation[0]).ToString() + "_" + Quantize(orientation[1]).ToString() + "_" + Quantize(orientation[2]).ToString();
    }

    static bool SaneVector(vector value, float limit)
    {
        // Explicit comparisons also reject NaN and infinities.
        return value[0] >= -limit && value[0] <= limit && value[1] >= -limit && value[1] <= limit && value[2] >= -limit && value[2] <= limit;
    }
}
