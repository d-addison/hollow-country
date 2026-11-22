// World epoch for the infected route caches (P2.1). It lives in 3_Game because the hooks below are
// modded classes of 3_Game originals (3_Game/Entities/Building.c:102-139 door callbacks;
// HCPathgraphRefresh). HCNavRouteCache and HCHordeFlowCache (4_World) read it. Runtime only.
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

// Door state changes the DOOR_CLOSED/DOOR_OPENED area of the navmesh, so every cached route is stale.
// Vanilla subclasses override these callbacks and call super, so the hook sees every door.
modded class Building
{
    override void OnDoorOpenStart(DoorStartParams params)
    {
        super.OnDoorOpenStart(params);
        HCNavEpoch.HCBump();
    }

    override void OnDoorCloseStart(DoorStartParams params)
    {
        super.OnDoorCloseStart(params);
        HCNavEpoch.HCBump();
    }

    override void OnDoorLocked(DoorLockParams params)
    {
        super.OnDoorLocked(params);
        HCNavEpoch.HCBump();
    }

    override void OnDoorUnlocked(DoorLockParams params)
    {
        super.OnDoorUnlocked(params);
        HCNavEpoch.HCBump();
    }
}
