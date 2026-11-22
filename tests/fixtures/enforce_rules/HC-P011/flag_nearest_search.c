// HC-P011 must flag: a nearest-target scan over a catalog that grows with the world.
class HCFixNearestModule
{
    protected ref array<ref HCFixTarget> m_Targets = new array<ref HCFixTarget>;

    int Nearest(vector from)
    {
        int best = -1;
        float bestGap = 0;
        for (int index = 0; index < m_Targets.Count(); index++)
        {
            float gap = vector.DistanceSq(from, m_Targets[index].Point);
            if (best < 0 || gap < bestGap) { best = index; bestGap = gap; }
        }
        return best;
    }

    void OnTick()
    {
        Nearest("0 0 0");
    }
}

class HCFixTarget
{
    vector Point;
}
