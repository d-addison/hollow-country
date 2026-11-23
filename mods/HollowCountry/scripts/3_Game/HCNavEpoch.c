// World epoch for the infected route caches (P2.1). It lives in 3_Game so the HCPathgraphRefresh hook below
// can bump it; the door hooks are in 4_World/Infected/HCNavEpochDoors.c because the engine refuses
// `modded class Building`. HCNavRouteCache and HCHordeFlowCache (4_World) read it. Runtime only.
class HCNavEpoch
{
    protected static int s_Epoch = 1;
    protected static int s_Bumps;

    static int HCValue() { return s_Epoch; }
    static int HCBumps() { return s_Bumps; }

    // O(1). Every door open/close/lock change and every pathgraph refresh lands here.
    static void HCBump()
    {
        s_Epoch++;
        s_Bumps++;
    }
}

// Pathgraph refresh (object placement, shelters, interiors) changes polygons: new epoch.
modded class HCPathgraphRefresh
{
    override void Update()
    {
        super.Update();
        if (HasBounds) { HCNavEpoch.HCBump(); }
    }

    override static bool Mark(Object object)
    {
        bool marked = super.Mark(object);
        if (marked) { HCNavEpoch.HCBump(); }
        return marked;
    }
}
