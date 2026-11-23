// Door state changes the DOOR_CLOSED/DOOR_OPENED area of the navmesh, so cached routes near the door are stale.
// The engine refuses `modded class Building` ("Engine class 'Building' cannot be modded", compile gate
// 2026-11-22), so the hook sits on BuildingBase (4_World/Entities/Game/Super/Building.c:8), the scripted base
// of House, BuildingSuper and every map building with doors. Vanilla subclasses override these callbacks and
// call super, so the hook sees every such door. O(1) per callback. A door bumps only the regional epoch
// around its building (HCNavRegionEpoch), so routes elsewhere stay cached; the world epoch is bumped by
// pathgraph refresh only.
modded class BuildingBase
{
    override void OnDoorOpenStart(DoorStartParams params)
    {
        super.OnDoorOpenStart(params);
        HCNavRegionEpoch.HCBumpAt(GetPosition());
    }

    override void OnDoorCloseStart(DoorStartParams params)
    {
        super.OnDoorCloseStart(params);
        HCNavRegionEpoch.HCBumpAt(GetPosition());
    }

    override void OnDoorLocked(DoorLockParams params)
    {
        super.OnDoorLocked(params);
        HCNavRegionEpoch.HCBumpAt(GetPosition());
    }

    override void OnDoorUnlocked(DoorLockParams params)
    {
        super.OnDoorUnlocked(params);
        HCNavRegionEpoch.HCBumpAt(GetPosition());
    }
}
