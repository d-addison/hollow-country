// LC-T309 / #93 / #120, EXP-S3. Source/package only; no native acceptance.
// Installed scripts-1.30.164289: 3_Game/Global/Game.c:703 CreateObjectEx,
// :680 CreateStaticObjectUsingP3D, :705 ObjectDelete, :930 GetObjectsAtPosition3D,
// :465 ConfigGetTextOut, :612 ConfigIsExisting, :1176 SurfaceY, :1196 SurfaceIsSea;
// 3_Game/Entities/Building.c:31 GetDoorCount, :73 GetDoorSoundPos (world position);
// 3_Game/Entities/Object.c:215 IsPendingDeletion, :287 GetPosition, :311 SetOrientation,
// :370 GetCollisionBox; 1_Core/proto/EnMath.c:225 AbsFloat, :305 Sqrt, :566 Max.
// 3_Game/CE/CentralEconomy.c:9,17,30,31,38 ECE flags. EnMath3D.c:18 Vector.
// Class/model provenance and stock mapgroupproto presence/absence: MIS/events/scene-provenance.json.
// All scenery is non-inventory. No real item is created, moved or deleted here;
// v1 journal/reward capability remains authoritative. The terminal cache is empty scenery.
// Common natives: 3_Game/Global/Game.c:1120 IsServer; 1_Core/proto/EnDebug.c:96 Print;
// EnScript.c:380 Count, :394 Find, :407 Insert, :463 Remove; EnConvert.c:30 int.ToString;
// EnString.c:171 ToLower, :199 Length (1_Core/proto).

class HCSceneProp
{
    string Type;
    vector Offset;
    float Yaw;
    float Radius;
    bool StaticModel;
}

class HCSceneKit
{
    string Id;
    ref array<ref HCSceneProp> Props = new array<ref HCSceneProp>();
}

class HCSceneLease
{
    string ChainId;
    int Stage;
    vector Anchor;
    bool Closing;
    int ViewEventId;
    string ViewSession;
    ref array<Object> Objects = new array<Object>();
}

class HCSceneKits
{
    // Horizontal footprint, including the whole prop, never just its origin.
    static bool OutsideDoor(vector position, vector door, float propRadius)
    {
        float dx = position[0] - door[0];
        float dz = position[2] - door[2];
        float clearance = 4.0 + propRadius;
        return dx * dx + dz * dz > clearance * clearance;
    }

    static void Add(HCSceneKit kit, string type, float x, float z, float yaw, float radius, bool staticModel = false)
    {
        HCSceneProp prop = new HCSceneProp;
        prop.Type = type;
        prop.Offset = Vector(x, 0, z);
        prop.Yaw = yaw;
        prop.Radius = radius;
        prop.StaticModel = staticModel;
        kit.Props.Insert(prop);
    }

    static HCSceneKit Find(string kind)
    {
        HCSceneKit kit = new HCSceneKit;
        kit.Id = kind;
        // Leave the entire east/west access strip z=-4..4 clear. Never surround
        // the anchor with a ring of barricades. Slots are off the stock event origin.
        if (kind == "last-stand")
        {
            Add(kit, "StaticObj_Misc_Barricade", -4, 8, 70, 2.5);
            Add(kit, "StaticObj_Decon_HazmatBag_01_F", 3, 8, 15, 1.5);
            Add(kit, "FxCartridge_556", -1, 7, 35, 0.1, true);
            Add(kit, "FxCartridge_556", -0.7, 7.3, 120, 0.1, true);
            Add(kit, "FxCartridge_556", -1.3, 7.2, 240, 0.1, true);
        }
        else if (kind == "quarantine-checkpoint")
        {
            Add(kit, "StaticObj_PartyTent", -6, 11, 0, 4.5);
            Add(kit, "StaticObj_Roadblock_Bags_EndL", 3, 8, 90, 2);
            Add(kit, "StaticObj_Furniture_metalcrate", 3, 12, 15, 1);
            Add(kit, "StaticObj_Decon_CBRNCase_01_F", 5, 12, 45, 1);
        }
        else if (kind == "evacuation-point")
        {
            Add(kit, "Land_Wreck_Lada_Green", -5, 10, 35, 3.5);
            Add(kit, "StaticObj_Furniture_bag_DZ", 2, 7, 15, 0.8);
            Add(kit, "StaticObj_Furniture_bag_DZ", 4, 8, 200, 0.8);
            Add(kit, "StaticObj_Furniture_PaperBox_01_small_ransacked", 2, 10, 60, 1);
        }
        else if (kind == "supply-drop-remains")
        {
            Add(kit, "StaticObj_Misc_Pallet", -3, 8, 25, 1.2);
            Add(kit, "StaticObj_Furniture_metalcrate", 1, 8, 10, 1);
            Add(kit, "StaticObj_Furniture_PaperBox_01_small_ransacked", 4, 9, 65, 1);
        }
        else if (kind == "convoy-wreck")
        {
            Add(kit, "Land_Wreck_Uaz", -6, 10, 15, 3.5);
            Add(kit, "Land_Wreck_V3S", 6, 12, 40, 5);
            Add(kit, "StaticObj_Misc_Pallet", 0, 8, 75, 1.2);
        }
        else if (kind == "survivor-distress-camp")
        {
            Add(kit, "StaticObj_PartyTent", -6, 11, 25, 4.5);
            Add(kit, "StaticObj_Furniture_foldingbed_open", 2, 9, 45, 1.5);
            Add(kit, "StaticObj_Furniture_bag_DZ", 5, 8, 160, 0.8);
            Add(kit, "StaticObj_Furniture_metalcrate", 4, 12, 15, 1);
        }
        else { return null; }
        return kit;
    }

    static bool Reviewed(HCEventSite site)
    {
        if (!site || !site.Reviewed || site.WorldName != "chernarusplus") { return false; }
        array<ref HCEventSite> reviewed = HCEventReviewedSites.Curated();
        foreach (HCEventSite approved : reviewed)
        {
            if (site.Id == approved.Id && site.Position == approved.Position) { return true; }
        }
        return false;
    }

    static bool Preflight(HCSceneKit kit, HCEventSite site, out array<vector> positions)
    {
        positions = new array<vector>();
        if (!GetGame() || !GetGame().IsServer() || !Reviewed(site) || !kit || kit.Props.Count() < 1 || kit.Props.Count() > 8) { return false; }
        if (!HCObserverTransitionGate.CanTransition(site.Position, 500)) { return false; }
        array<Object> nearby = new array<Object>();
        array<CargoBase> proxies = new array<CargoBase>();
        GetGame().GetObjectsAtPosition3D(site.Position, 40, nearby, proxies);
        if (nearby.Count() > 128 || proxies.Count() > 128) { return false; }
        array<vector> doors = new array<vector>();
        array<vector> occupied = new array<vector>();
        array<float> footprints = new array<float>();
        foreach (Object candidate : nearby)
        {
            Building building = Building.Cast(candidate);
            if (!building || building.IsPendingDeletion()) { continue; }
            int count = building.GetDoorCount();
            if (count < 0 || count > 32 || doors.Count() + count > 64) { return false; }
            for (int doorIndex = 0; doorIndex < count; doorIndex++)
            {
                doors.Insert(building.GetDoorSoundPos(doorIndex));
            }
            // Stock event wrecks are also buildings: reserve their actual
            // bounding radius rather than rejecting the entire reviewed site.
            // Preserve stairs/doorless structures as well as named doors.
            vector bounds[2];
            if (!building.GetCollisionBox(bounds)) { return false; }
            if (!HCEventRuntimePolicy.PositionValid(bounds[0]) || !HCEventRuntimePolicy.PositionValid(bounds[1])) { return false; }
            float extentX = Math.Max(Math.AbsFloat(bounds[0][0]), Math.AbsFloat(bounds[1][0]));
            float extentZ = Math.Max(Math.AbsFloat(bounds[0][2]), Math.AbsFloat(bounds[1][2]));
            if (extentX == 0 && extentZ == 0) { return false; }
            occupied.Insert(building.GetPosition());
            footprints.Insert(Math.Sqrt(extentX * extentX + extentZ * extentZ) + 2);
        }
        foreach (HCSceneProp prop : kit.Props)
        {
            string configPath = "CfgVehicles " + prop.Type;
            if (!GetGame().ConfigIsExisting(configPath)) { return false; }
            vector position = site.Position + prop.Offset;
            position[1] = GetGame().SurfaceY(position[0], position[2]);
            if (!HCEventRuntimePolicy.PositionValid(position) || GetGame().SurfaceIsSea(position[0], position[2])) { return false; }
            // The authored access corridor remains clear even for the largest footprint.
            if (prop.Offset[2] - prop.Radius <= 4) { return false; }
            foreach (vector door : doors)
            {
                if (!OutsideDoor(position, door, prop.Radius)) { return false; }
            }
            for (int footprintIndex = 0; footprintIndex < occupied.Count(); footprintIndex++)
            {
                vector obstacle = occupied[footprintIndex];
                float dx = position[0] - obstacle[0];
                float dz = position[2] - obstacle[2];
                float keepout = prop.Radius + footprints[footprintIndex];
                if (dx * dx + dz * dz <= keepout * keepout) { return false; }
            }
            // Refuse steep/uneven ground instead of making stairs or floating props.
            float east = GetGame().SurfaceY(position[0] + prop.Radius, position[2]);
            float west = GetGame().SurfaceY(position[0] - prop.Radius, position[2]);
            float north = GetGame().SurfaceY(position[0], position[2] + prop.Radius);
            float south = GetGame().SurfaceY(position[0], position[2] - prop.Radius);
            if (east != east || west != west || north != north || south != south) { return false; }
            if (Math.AbsFloat(east - position[1]) > 0.8 || Math.AbsFloat(west - position[1]) > 0.8 || Math.AbsFloat(north - position[1]) > 0.8 || Math.AbsFloat(south - position[1]) > 0.8) { return false; }
            if (!HCObserverTransitionGate.CanTransition(position, 500)) { return false; }
            positions.Insert(position);
        }
        return true;
    }

    // Caller retains the lease BEFORE calling: partial creation is never orphaned.
    static bool Place(HCSceneLease lease, HCSceneKit kit, array<vector> positions)
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        if (!lease || !kit || !positions || positions.Count() != kit.Props.Count() || lease.Objects.Count() != 0) { return false; }
        for (int index = 0; index < kit.Props.Count(); index++)
        {
            HCSceneProp prop = kit.Props[index];
            vector position = positions[index];
            if (!HCObserverTransitionGate.CanTransition(position, 500)) { lease.Closing = true; return false; }
            vector orientation = Vector(prop.Yaw, 0, 0);
            Object object;
            if (prop.StaticModel)
            {
                // Spent cartridges use their verified model as static clutter:
                // no projectile simulation and no usable ammunition item.
                string model = GetGame().ConfigGetTextOut("CfgVehicles " + prop.Type + " model");
                if (model == "") { lease.Closing = true; return false; }
                object = GetGame().CreateStaticObjectUsingP3D(model, position, orientation, 1, false, false);
            }
            else
            {
                int flags = ECE_PLACE_ON_SURFACE | ECE_NOLIFETIME | ECE_NOPERSISTENCY_WORLD;
                object = GetGame().CreateObjectEx(prop.Type, position, flags);
            }
            if (!object) { lease.Closing = true; return false; }
            lease.Objects.Insert(object);
            object.SetOrientation(orientation);
        }
        return true;
    }

    static bool Remove(HCSceneLease lease)
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        if (!lease || !HCObserverTransitionGate.CanTransition(lease.Anchor, 500)) { return false; }
        foreach (Object pending : lease.Objects)
        {
            if (pending && !HCObserverTransitionGate.CanTransition(pending.GetPosition(), 500)) { return false; }
        }
        bool gone = true;
        foreach (Object owned : lease.Objects)
        {
            if (owned)
            {
                gone = false;
                if (!owned.IsPendingDeletion()) { GetGame().ObjectDelete(owned); }
            }
        }
        // Confirm native reference invalidation on a later bounded pass.
        return gone;
    }

    static bool Healthy(HCSceneLease lease)
    {
        if (!lease || lease.Closing || lease.Objects.Count() == 0) { return false; }
        foreach (Object owned : lease.Objects)
        {
            if (!owned || owned.IsPendingDeletion()) { return false; }
        }
        return true;
    }
}
