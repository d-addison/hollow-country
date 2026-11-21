// Engine calls only. Installed 1.30.164289: Object.c:341/344/358/873,
// World.c:134/135, Game.c:1206. Call after the final snap/orientation/scale.
class HCPathgraphRefresh
{
    vector Minimum;
    vector Maximum;
    bool HasBounds;
    int Marked;
    int SkippedNoGeom;

    static bool Prepare(Object object)
    {
        if (!object) { return false; }
        // FireplaceBase's explicit geometry influence pattern; config defaults
        // can disable otherwise usable runtime furniture geometry.
        object.SetAffectPathgraph(false, true);
        return object.CanAffectPathgraph();
    }

    static bool Mark(Object object)
    {
        if (!Prepare(object)) { return false; }
        g_Game.GetWorld().MarkObjectForPathgraphUpdate(object);
        return true;
    }

    bool Include(Object object)
    {
        if (!Prepare(object)) { SkippedNoGeom++; return false; }
        vector clip[2];
        float radius = object.ClippingInfo(clip);
        if (radius <= 0) { SkippedNoGeom++; return false; }
        vector low = clip[0];
        vector high = clip[1];
        if (low[0] >= high[0] || low[1] >= high[1] || low[2] >= high[2])
        {
            SkippedNoGeom++;
            return false;
        }
        // All eight corners: rotating only min/max loses tilted/yawed extents.
        vector minimum = object.ModelToWorld(low);
        vector maximum = minimum;
        for (int corner = 0; corner < 8; corner++)
        {
            vector modelCorner = low;
            if ((corner & 1) != 0) { modelCorner[0] = high[0]; }
            if ((corner & 2) != 0) { modelCorner[1] = high[1]; }
            if ((corner & 4) != 0) { modelCorner[2] = high[2]; }
            vector world = object.ModelToWorld(modelCorner);
            for (int axis = 0; axis < 3; axis++)
            {
                minimum[axis] = Math.Min(minimum[axis], world[axis]);
                maximum[axis] = Math.Max(maximum[axis], world[axis]);
            }
        }
        minimum = minimum - Vector(0.5, 0.5, 0.5);
        maximum = maximum + Vector(0.5, 1.5, 0.5);
        if (!HasBounds)
        {
            Minimum = minimum;
            Maximum = maximum;
            HasBounds = true;
        }
        else
        {
            for (int component = 0; component < 3; component++)
            {
                Minimum[component] = Math.Min(Minimum[component], minimum[component]);
                Maximum[component] = Math.Max(Maximum[component], maximum[component]);
            }
        }
        Marked++;
        return true;
    }

    void Update()
    {
        if (!HasBounds || !g_Game) { return; }
        g_Game.UpdatePathgraphRegion(Minimum, Maximum);
    }
}
