// Regional door epoch for the infected route caches. A door open/close/lock bumps only the 3x3 block of
// 64 m coarse cells around the building, not the world epoch, so a town's doors no longer empty every
// cached route on the map. Cells are hashed into 1024 buckets (a collision only over-invalidates). Each
// bump takes a new value of one monotonic counter and stamps its buckets with it; a cache entry keeps the
// counter value it was stored at plus the cell box of its route (start, polyline, goal) and is live while
// no bucket in that box carries a newer stamp. A box wider than 8 cells on an axis is checked against the
// newest stamp anywhere (conservative). O(1) per door event, at most 64 integer compares per lookup.
// Pathgraph refresh still bumps the world epoch (HCNavEpoch, 3_Game). Runtime only; nothing stored.
class HCNavRegionEpoch
{
    static const float CELL_METRES = 64;
    static const int CELL_MAX = 255;
    static const int BUCKETS = 1024;
    static const int BOX_WIDE = 8;

    protected static bool s_Ready;
    protected static int s_Counter;
    protected static int s_Bumps;
    protected static ref array<int> s_Stamp;

    protected static void HCInit()
    {
        if (s_Ready) { return; }
        s_Ready = true;
        s_Stamp = new array<int>;
        for (int slot = 0; slot < BUCKETS; slot++) { s_Stamp.Insert(0); }
    }

    static int HCCell(float value)
    {
        int cell = Math.Floor(value / CELL_METRES);
        if (cell < 0) { cell = 0; }
        if (cell > CELL_MAX) { cell = CELL_MAX; }
        return cell;
    }

    // Counter value to store with an entry at store time.
    static int HCNow() { return s_Counter; }
    static int HCBumps() { return s_Bumps; }

    protected static int HCBucket(int cellX, int cellZ)
    {
        return (cellX * 31 + cellZ) % BUCKETS;
    }

    // O(1): stamp the 3x3 cells around a door's building with a new counter value.
    static void HCBumpAt(vector position)
    {
        HCInit();
        s_Counter++;
        s_Bumps++;
        int centreX = HCCell(position[0]);
        int centreZ = HCCell(position[2]);
        for (int dx = -1; dx <= 1; dx++)
        {
            for (int dz = -1; dz <= 1; dz++)
            {
                int cellX = centreX + dx;
                int cellZ = centreZ + dz;
                if (cellX < 0 || cellZ < 0) { continue; }
                int bucket = HCBucket(cellX, cellZ);
                s_Stamp[bucket] = s_Counter;
            }
        }
    }

    // The cell box of start, goal and every route point: box[0..3] = min x, min z, max x, max z.
    static void HCBox(vector from, vector goal, TVectorArray path, array<int> box, int offset)
    {
        int minX = HCCell(from[0]);
        int maxX = minX;
        int minZ = HCCell(from[2]);
        int maxZ = minZ;
        int goalX = HCCell(goal[0]);
        int goalZ = HCCell(goal[2]);
        if (goalX < minX) { minX = goalX; }
        if (goalX > maxX) { maxX = goalX; }
        if (goalZ < minZ) { minZ = goalZ; }
        if (goalZ > maxZ) { maxZ = goalZ; }
        if (path)
        {
            for (int point = 0; point < path.Count(); point++)
            {
                int pointX = HCCell(path[point][0]);
                int pointZ = HCCell(path[point][2]);
                if (pointX < minX) { minX = pointX; }
                if (pointX > maxX) { maxX = pointX; }
                if (pointZ < minZ) { minZ = pointZ; }
                if (pointZ > maxZ) { maxZ = pointZ; }
            }
        }
        box[offset] = minX;
        box[offset + 1] = minZ;
        box[offset + 2] = maxX;
        box[offset + 3] = maxZ;
    }

    // True while no door event newer than `stored` touched a cell in the entry's box.
    static bool HCLive(int stored, array<int> box, int offset)
    {
        HCInit();
        if (s_Counter == stored) { return true; }
        int minX = box[offset];
        int minZ = box[offset + 1];
        int maxX = box[offset + 2];
        int maxZ = box[offset + 3];
        if (maxX - minX >= BOX_WIDE || maxZ - minZ >= BOX_WIDE) { return false; }
        for (int cellX = minX; cellX <= maxX; cellX++)
        {
            for (int cellZ = minZ; cellZ <= maxZ; cellZ++)
            {
                if (s_Stamp[HCBucket(cellX, cellZ)] > stored) { return false; }
            }
        }
        return true;
    }
}
