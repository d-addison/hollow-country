// Native BaseBuildingBase.c:136/264/348/811 exposes native part replication,
// physics/navmesh and save state. No OnStore overrides, free kits or cargo.
// FullyBuild is deliberately avoided: it requires a notnull player and creates
// a recoverable kit. Only native wooden parts are admitted here.
modded class BaseBuildingBase
{
    bool HCBuildCampFortification()
    {
        if (!GetGame().IsServer() || (!Fence.Cast(this) && !Watchtower.Cast(this))) { return false; }
        Construction construction = GetConstruction();
        if (!construction) { return false; }
        array<ConstructionPart> parts = construction.GetConstructionParts().GetValueArray();
        if (!parts || parts.Count() < 1 || parts.Count() > 128) { return false; }
        int built;
        foreach (ConstructionPart part : parts)
        {
            string partName = part.GetPartName();
            if (partName.Length() > 128) { return false; }
            if (part.IsGate() || partName.Contains("_metal_")) { continue; }
            if (part.IsBase()) { SetBaseState(true); }
            RegisterPartForSync(part.GetId());
            SetPartFromSyncData(part);
            built++;
        }
        SynchronizeBaseState();
        construction.UpdateVisuals();
        UpdateVisuals();
        UpdateNavmesh();
        SetSynchDirty();
        return built > 0 && HasBase();
    }
}

class HCCampFortification
{
    // Same CE-persistent flags as HCGroundObjectSpawner's enableCEPersistency
    // path; HCGroundSnap owns support correction. No lifetime refresh loop.
    // Native Game.c:1366 clearance box; EntityAI defaults own CE lifetime.
    static BaseBuildingBase Place(string kind, vector at, vector angles)
    {
        if (!GetGame() || !GetGame().IsServer() || (kind != "Fence" && kind != "Watchtower")) { return null; }
        int flags = ECE_SETUP | ECE_UPDATEPATHGRAPH | ECE_CREATEPHYSICS | ECE_OBJECT_SPAWNER;
        BaseBuildingBase fort = BaseBuildingBase.Cast(GetGame().CreateObjectEx(kind, at, flags, RF_IGNORE));
        if (!fort) { return null; }
        fort.SetOrientation(angles);
        if (!HCGroundSnap.Snap(fort, 3, 0.01) || !fort.HCBuildCampFortification())
        {
            GetGame().ObjectDelete(fort);
            return null;
        }
        return fort;
    }
}
