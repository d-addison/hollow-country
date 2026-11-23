// Door state changes the DOOR_CLOSED/DOOR_OPENED area of the navmesh, so every cached route is stale.
// The engine refuses `modded class Building` ("Engine class 'Building' cannot be modded", compile gate
// 2026-11-22), so the hook sits on BuildingBase (4_World/Entities/Game/Super/Building.c:8), the scripted base
// of House, BuildingSuper and every map building with doors. Vanilla subclasses override these callbacks and
// call super, so the hook sees every such door. O(1) per callback.
modded class BuildingBase
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
