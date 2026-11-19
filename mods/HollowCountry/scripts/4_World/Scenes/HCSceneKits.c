// HC-42 content index: MIS/events/story-sites.json names finite kit/site
// opportunities, NOT runtime HCEventSite approvals. The ten layouts below and
// their verified class/model provenance are unchanged. A locality label is not
// a placement transform; source-reviewed anchors are not native kit surveys.
// Reserved Scenes/#138 integration must resolve an indexed, qualified pair,
// pin its plan through HC-19 BEFORE materialization and keep the existing lease,
// observer, work/save budgets and cleanup ownership. Never mint identities from
// candidate IDs or rotate/rewrite the pinned plans of already issued stories.
// Receipt/refusals are HC-62's bounded status integration, not a content tick.
// W5-PERF-3: queued kits create <=1 prop per module tick; <=2 live leases.
// Pending creation uses only runtime handles; existing chain intent is durable.
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
// #120 follow-up: four additional kits; installed vanilla class AND P3D member
// checks recorded in scene-provenance.json. No new native dependency. Container
// and cold hearth use Game.c:680 static models, never live inventory entities.

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
    ref HCSceneKit PlacementKit;
    ref array<vector> PlacementPositions;
    int PlacementVariant;
    bool StoryPublished;
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
        else if (kind == "supply-drop-opened")
        {
            // Open container shell and scattered empty crates, with its opening
            // clear. The shell is model-only: no native container door or cargo.
            Add(kit, "Land_Container_1Bo", -6, 13, 0, 4, true);
            Add(kit, "StaticObj_Furniture_metalcrate", 1, 9, 20, 1);
            Add(kit, "StaticObj_Furniture_metalcrate_02", 4, 12, 65, 1);
            Add(kit, "StaticObj_Furniture_metalcrate", 0, 15, 130, 1);
            Add(kit, "StaticObj_Misc_Pallet", 4, 16, 35, 1.2);
        }
        else if (kind == "convoy-roadside")
        {
            // Military wrecks sit on the same side of the authored access strip.
            // Actual shoulder/route alignment still needs the EXP-S3 site walk.
            Add(kit, "StaticObj_Wreck_MTVR_Cargo", -8, 13, 0, 6);
            Add(kit, "Land_Wreck_Uaz", 6, 12, 0, 3.5);
            Add(kit, "StaticObj_Furniture_metalcrate_02", 2, 19, 75, 1);
        }
        else if (kind == "quarantine-cordon")
        {
            Add(kit, "StaticObj_PartyTent", -8, 13, 0, 4.5);
            Add(kit, "StaticObj_Roadblock_Bags_EndL", 2, 8, 90, 2);
            Add(kit, "StaticObj_Roadblock_Bags_EndR", 7, 9, 90, 2);
            Add(kit, "StaticObj_Sign_Roadblock_Stop", 1, 13, 180, 1);
            // Vanilla static hazard/body-bag scenery, never a corpse or item.
            Add(kit, "StaticObj_Decon_HazmatBag_01_F", 3, 16, 0, 1.5);
            Add(kit, "StaticObj_Decon_HazmatBag_01_F", 7, 16, 15, 1.5);
        }
        else if (kind == "survivor-cold-camp")
        {
            Add(kit, "StaticObj_Mil_CamoNet_Tent2", -7, 12, 0, 4);
            // Only the verified Fireplace P3D: no FireplaceBase, fire, fuel,
            // cooking slots, warmth, camp registration or inventory is created.
            Add(kit, "Fireplace", 1, 9, 0, 1, true);
            Add(kit, "StaticObj_Furniture_foldingbed_open", 0, 14, 30, 1.5);
            Add(kit, "StaticObj_Furniture_kitchen_chair_a", 4, 9, 220, 0.8);
            Add(kit, "StaticObj_Furniture_bag_DZ", 4, 14, 70, 0.8);
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

    // Last Preflight refusal, for one bounded diagnostic line per chain and reason.
    protected static string s_Refusal;
    static string Refusal() { return s_Refusal; }
    protected static bool HCSceneRefuse(string reason)
    {
        s_Refusal = reason;
        return false;
    }

    static bool Preflight(HCSceneKit kit, HCEventSite site, out array<vector> positions, out int variant)
    {
        positions = new array<vector>();
        variant = 0;
        s_Refusal = "";
        if (!GetGame() || !GetGame().IsServer()) { return HCSceneRefuse("not-server"); }
        if (!Reviewed(site)) { return HCSceneRefuse("site-not-reviewed"); }
        if (!kit) { return HCSceneRefuse("kit-missing"); }
        if (kit.Props.Count() < 1 || kit.Props.Count() > 8) { return HCSceneRefuse("kit-size"); }
        if (!HCObserverTransitionGate.CanTransition(site.Position, 500)) { return HCSceneRefuse("observed-site"); }
        array<Object> nearby = new array<Object>();
        array<CargoBase> proxies = new array<CargoBase>();
        GetGame().GetObjectsAtPosition3D(site.Position, 40, nearby, proxies);
        if (nearby.Count() > 256 || proxies.Count() > 256) { return HCSceneRefuse("query-cap objects=" + nearby.Count().ToString()); }
        array<vector> doors = new array<vector>();
        array<vector> occupied = new array<vector>();
        array<float> footprints = new array<float>();
        foreach (Object candidate : nearby)
        {
            Building building = Building.Cast(candidate);
            if (!building || building.IsPendingDeletion()) { continue; }
            int count = building.GetDoorCount();
            if (count < 0 || count > 32 || doors.Count() + count > 64) { return HCSceneRefuse("door-cap " + building.GetType()); }
            for (int doorIndex = 0; doorIndex < count; doorIndex++)
            {
                doors.Insert(building.GetDoorSoundPos(doorIndex));
            }
            // Stock event wrecks are also buildings: reserve their actual
            // bounding radius rather than rejecting the entire reviewed site.
            // Preserve stairs/doorless structures as well as named doors.
            vector bounds[2];
            if (!building.GetCollisionBox(bounds)) { return HCSceneRefuse("no-collision-box " + building.GetType()); }
            if (!HCEventRuntimePolicy.PositionValid(bounds[0]) || !HCEventRuntimePolicy.PositionValid(bounds[1])) { return HCSceneRefuse("bounds-invalid " + building.GetType()); }
            float extentX = Math.Max(Math.AbsFloat(bounds[0][0]), Math.AbsFloat(bounds[1][0]));
            float extentZ = Math.Max(Math.AbsFloat(bounds[0][2]), Math.AbsFloat(bounds[1][2]));
            if (extentX == 0 && extentZ == 0) { return HCSceneRefuse("zero-extent " + building.GetType()); }
            occupied.Insert(building.GetPosition());
            footprints.Insert(Math.Sqrt(extentX * extentX + extentZ * extentZ) + 2);
        }
        // Kit offsets are world-axis aligned, not tied to a site heading: try the
        // authored layout first, then the same kit rotated in quarter turns about
        // the anchor and mirrored. Every check applies to every variant.
        if (Layout(kit, site, doors, occupied, footprints, 0, positions)) { return true; }
        string authored = s_Refusal;
        for (int layoutIndex = 1; layoutIndex < 8; layoutIndex++)
        {
            if (Layout(kit, site, doors, occupied, footprints, layoutIndex, positions))
            {
                variant = layoutIndex;
                s_Refusal = "";
                return true;
            }
        }
        s_Refusal = authored + "; 7 rotated/mirrored layouts refused, last " + s_Refusal;
        return false;
    }

    // Variant 0..3: quarter turns clockwise seen from above; 4..7 the same, mirrored in x first.
    static vector LayoutOffset(vector offset, int variant)
    {
        float x = offset[0];
        float z = offset[2];
        if (variant >= 4) { x = -x; }
        int quarter = variant;
        if (quarter >= 4) { quarter = quarter - 4; }
        float turnedX = x;
        float turnedZ = z;
        if (quarter == 1) { turnedX = z; turnedZ = -x; }
        if (quarter == 2) { turnedX = -x; turnedZ = -z; }
        if (quarter == 3) { turnedX = -z; turnedZ = x; }
        return Vector(turnedX, offset[1], turnedZ);
    }

    static float LayoutYaw(float yaw, int variant)
    {
        float turned = yaw;
        if (variant >= 4) { turned = 360 - yaw; }
        int quarter = variant;
        if (quarter >= 4) { quarter = quarter - 4; }
        turned = turned + 90 * quarter;
        while (turned >= 360) { turned = turned - 360; }
        return turned;
    }

    // No prop footprint may overlap the east/west access strip z=-4..4, whichever side it is on.
    static bool InAccessStrip(vector offset, float radius)
    {
        if (offset[2] - radius > 4) { return false; }
        return offset[2] + radius >= -4;
    }

    protected static bool Layout(HCSceneKit kit, HCEventSite site, array<vector> doors, array<vector> occupied, array<float> footprints, int variant, out array<vector> positions)
    {
        positions = new array<vector>();
        foreach (HCSceneProp prop : kit.Props)
        {
            string configPath = "CfgVehicles " + prop.Type;
            if (!GetGame().ConfigIsExisting(configPath)) { return HCSceneRefuse("class-missing " + prop.Type); }
            vector offset = LayoutOffset(prop.Offset, variant);
            vector position = site.Position + offset;
            position[1] = GetGame().SurfaceY(position[0], position[2]);
            if (!HCEventRuntimePolicy.PositionValid(position) || GetGame().SurfaceIsSea(position[0], position[2])) { return HCSceneRefuse("position-or-sea " + prop.Type); }
            // The world east/west access strip stays clear in every layout: test the turned offset, not the authored one.
            if (InAccessStrip(offset, prop.Radius)) { return HCSceneRefuse("corridor " + prop.Type); }
            foreach (vector door : doors)
            {
                if (!OutsideDoor(position, door, prop.Radius)) { return HCSceneRefuse("door " + prop.Type); }
            }
            for (int footprintIndex = 0; footprintIndex < occupied.Count(); footprintIndex++)
            {
                vector obstacle = occupied[footprintIndex];
                float dx = position[0] - obstacle[0];
                float dz = position[2] - obstacle[2];
                float keepout = prop.Radius + footprints[footprintIndex];
                if (dx * dx + dz * dz <= keepout * keepout) { return HCSceneRefuse("building-footprint " + prop.Type); }
            }
            // Refuse steep/uneven ground instead of making stairs or floating props.
            float east = GetGame().SurfaceY(position[0] + prop.Radius, position[2]);
            float west = GetGame().SurfaceY(position[0] - prop.Radius, position[2]);
            float north = GetGame().SurfaceY(position[0], position[2] + prop.Radius);
            float south = GetGame().SurfaceY(position[0], position[2] - prop.Radius);
            if (east != east || west != west || north != north || south != south) { return HCSceneRefuse("surface-nan " + prop.Type); }
            float ground = position[1];
            float rise = Math.AbsFloat(east - ground);
            float riseWest = Math.AbsFloat(west - ground);
            float riseNorth = Math.AbsFloat(north - ground);
            float riseSouth = Math.AbsFloat(south - ground);
            if (riseWest > rise) { rise = riseWest; }
            if (riseNorth > rise) { rise = riseNorth; }
            if (riseSouth > rise) { rise = riseSouth; }
            if (rise > 0.8) { return HCSceneRefuse("slope " + prop.Type + " rise=" + rise.ToString()); }
            if (!HCObserverTransitionGate.CanTransition(position, 500)) { return HCSceneRefuse("observed-prop " + prop.Type); }
            positions.Insert(position);
        }
        return true;
    }

    // Caller retains the lease BEFORE calling: partial creation is never orphaned.
    static bool Place(HCSceneLease lease, HCSceneKit kit, array<vector> positions, int variant = 0)
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        if (!lease || !kit || !positions || positions.Count() != kit.Props.Count() || lease.Objects.Count() != 0) { return false; }
        lease.PlacementKit = kit;
        lease.PlacementPositions = positions;
        lease.PlacementVariant = variant;
        return true;
    }

    static bool HCPlacementComplete(HCSceneLease lease)
    {
        if (!lease || lease.Closing) { return true; }
        if (!lease.PlacementKit) { return false; }
        return lease.Objects.Count() >= lease.PlacementKit.Props.Count();
    }

    // Caller keeps the lease before any native create. Check observers again
    // for every prop; a newly arrived player cancels the remaining partial kit.
    static bool HCPlaceOne(HCSceneLease lease)
    {
        if (!lease || lease.Closing || HCPlacementComplete(lease)) { return false; }
        HCSceneKit kit = lease.PlacementKit;
        if (!kit) { return false; }
        array<vector> positions = lease.PlacementPositions;
        int variant = lease.PlacementVariant;
        int index = lease.Objects.Count();
        HCSceneProp prop = kit.Props[index];
        vector position = positions[index];
        if (!HCObserverTransitionGate.CanTransition(position, 500)) { lease.Closing = true; return false; }
        vector orientation = Vector(LayoutYaw(prop.Yaw, variant), 0, 0);
        Object object;
        if (prop.StaticModel)
        {
            // Render only the verified model (casings, open shell or cold
            // hearth): no projectile, inventory or fireplace simulation.
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
        foreach (Object ownedObject : lease.Objects)
        {
            if (ownedObject)
            {
                gone = false;
                if (!ownedObject.IsPendingDeletion()) { GetGame().ObjectDelete(ownedObject); }
            }
        }
        // Confirm native reference invalidation on a later bounded pass.
        return gone;
    }

    static bool Healthy(HCSceneLease lease)
    {
        if (!lease || lease.Closing || lease.Objects.Count() == 0) { return false; }
        foreach (Object ownedObject : lease.Objects)
        {
            if (!ownedObject || ownedObject.IsPendingDeletion()) { return false; }
        }
        return true;
    }
}
