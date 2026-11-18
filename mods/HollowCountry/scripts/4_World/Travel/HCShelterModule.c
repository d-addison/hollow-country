// LC-T206, EXP-T5 / EXP-S3. Startup-only, server-owned static yard scenes.
// Verified installed native-scripts/scripts-1.30.164289 interfaces:
// 3_Game/Global/Game.c:612 ConfigIsExisting, :703 CreateObjectEx, :705 ObjectDelete,
// :930 GetObjectsAtPosition3D, :934 GetWorldName(), :1120 IsServer, :1176 SurfaceY,
// :1196-1197 SurfaceIsSea/SurfaceIsPond, :1206 UpdatePathgraphRegion,
// :1293 UpdatePathgraphRegionByObject, :1333 IsBoxColliding, :1437 IsKindOf.
// 3_Game/Entities/Object.c:287 GetPosition, :294 SetPosition, :305 GetOrientation,
// :311 SetOrientation, :358 ClippingInfo, :467 GetType, :873-874 ModelToWorld/WorldToModel.
// 3_Game/CE/CentralEconomy.c:9/13/17/28/30/33/57 flags used by the reused Spawn:
// ECE_DYNAMIC_PERSISTENCY explicitly spawns WITHOUT persistence until taken;
// these HouseNoDestruct statics cannot be taken. No lootable Fireplace is made.
// 1_Core/proto/EnScript.c:380/385/407 array Count/Clear/Insert;
// 1_Core/proto/EnString.c:171 ToLower; 1_Core/proto/EnConvert.c:30 int.ToString,
// :115 float.ToString, :138 vector.ToString, :210 DistanceSq;
// 1_Core/proto/EnMath.c:225 AbsFloat; EnMath3D.c:18 Vector.
// 3_Game/Systems/Inventory/Cargo.c:12 GetCargoOwner for refusal diagnostics.
// 1_Core/proto/EnDebug.c:96 Print.
// Reused read-only HCInteriorTemplatePlacement.Resolve/Spawn and
// HCInteriorTemplates.SlotClear/BoxValid/AsVector. No acceptance gate bypass in
// Interiors: these V2 scenes follow EnableTravel and only LOG native verdicts.
class HCShelterModule : HCModule
{
    protected bool m_Started;
    protected int m_Placed;
    protected int m_Refused;
    protected string m_RefusalReason;
    protected string m_BlockingClass;
    protected string m_PropType;
    protected vector m_RefusalPoint;
    protected int m_QueryObjects;
    protected int m_QueryCargos;
    protected int m_CollisionCount;
    protected int m_LayoutVariant;
    protected float m_GroundRise;
    protected ref array<Object> m_Objects = new array<Object>;

    override string GetName() { return "Shelters"; }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableTravel;
    }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame() || !GetGame().IsServer() || !IsEnabled(settings) || m_Started) return;
        m_Started = true;
        Print(HCV2Admission.Line("Shelters", true, "EXP-T5", HCV2Gates.Qualified("EXP-T5")));
        string worldName = GetGame().GetWorldName();
        worldName.ToLower();
        if (worldName == "chernarusplus")
        {
            int shelterIndex = 0;
            while (shelterIndex < HCShelterCatalog.Count())
            {
                PlaceShelter(shelterIndex);
                shelterIndex = shelterIndex + 1;
            }
        }
        else
        {
            m_Refused = HCShelterCatalog.Count() * 3;
        }
        int propCount = m_Objects.Count();
        Print("[HollowCountry] V2 shelters placed=" + m_Placed.ToString() + " props=" + propCount.ToString() + " refused=" + m_Refused.ToString());
    }

    // No tick work or recurring retries; startup tries at most eight layouts.
    override void OnStop()
    {
        if (!m_Started) return;
        foreach (Object ownedProp : m_Objects)
        {
            DeleteProp(ownedProp);
        }
        m_Objects.Clear();
        m_Placed = 0;
        m_Refused = 0;
        m_Started = false;
    }

    protected array<float> Coordinates(vector point)
    {
        array<float> result = new array<float>;
        result.Insert(point[0]);
        result.Insert(point[1]);
        result.Insert(point[2]);
        return result;
    }

    protected void Keepout(HCInteriorTemplate layout, string kind, int index, vector minimum, vector maximum)
    {
        HCInteriorTemplateKeepOut excluded = new HCInteriorTemplateKeepOut;
        excluded.Kind = kind;
        excluded.Index = index;
        excluded.Min = Coordinates(minimum);
        excluded.Max = Coordinates(maximum);
        layout.KeepOuts.Insert(excluded);
    }

    protected HCInteriorTemplate YardLayout()
    {
        // Class geometry reviewed read-only in the local authored template cache:
        // profiles-v1/HollowCountry/templates/index.json -> Land_Barn_Wood2.
        // Occupied class box [-6.487,-2.581,-8.659]..[6.841,3.468,8.844].
        // Doors at both z ends and east x side, stairs inside the south end.
        // The census ClippingInfo box is larger: [-8.48698,-5.7232,-15.659]
        // ..[8.48698,5.7232,15.659]. Use that larger envelope here, not the
        // occupied room box. Source: interior-sampler-110/profiles/HCInteriorSampler/census.json.
        // Reserve the WHOLE clipping box + 2m and full end approaches, including all
        // stairs/CE positions, instead of trying to furnish unobserved rooms.
        HCInteriorTemplate layout = new HCInteriorTemplate;
        HCInteriorTemplateRoom yard = new HCInteriorTemplateRoom;
        yard.Id = 1;
        yard.Min = Coordinates("-23 -20 -5.5");
        yard.Max = Coordinates("-11.5 20 5.5");
        layout.Rooms.Insert(yard);
        Keepout(layout, "door", 0, "-10.5 -20 -17.7", "10.5 20 17.7");
        Keepout(layout, "stair", 0, "-30 -20 -30", "30 20 -6");
        Keepout(layout, "door", 1, "-30 -20 6", "30 20 30");
        // Continuous walk-around lane beside the windowless side wall.
        Keepout(layout, "walkway", 0, "-11.5 -20 -30", "-10.5 20 30");
        return layout;
    }

    protected bool Available(vector point)
    {
        array<Object> nearby = new array<Object>;
        array<CargoBase> cargos = new array<CargoBase>;
        // Include the shifted model pivot after grounding, even for a foreign
        // static with no collision geometry. A ground-level 0.75m sphere could
        // otherwise miss the same prop whose origin is above its lowest vertex.
        GetGame().GetObjectsAtPosition3D(point, 3, nearby, cargos);
        m_QueryObjects = nearby.Count();
        m_QueryCargos = cargos.Count();
        if (m_QueryObjects > 256)
        {
            m_BlockingClass = "query_cap_no_single_blocker";
            m_RefusalReason = "query_cap";
            return false;
        }
        if (m_QueryCargos > 0)
        {
            m_BlockingClass = "cargo_owner_unavailable";
            CargoBase blockingCargo = cargos.Get(0);
            if (blockingCargo)
            {
                EntityAI cargoOwner = blockingCargo.GetCargoOwner();
                if (cargoOwner) { m_BlockingClass = cargoOwner.GetType(); }
            }
            m_RefusalReason = "cargo_query";
            return false;
        }
        foreach (Object possibleOrphan : nearby)
        {
            // Refuse even non-colliding foreign/orphan statics. Never infer
            // ownership from coordinates or adopt/delete a restored object.
            if (!possibleOrphan) { continue; }
            vector orphanPosition = possibleOrphan.GetPosition();
            float gapX = orphanPosition[0] - point[0];
            float gapZ = orphanPosition[2] - point[2];
            if (gapX * gapX + gapZ * gapZ < 0.5625)
            {
                m_BlockingClass = possibleOrphan.GetType();
                m_RefusalReason = "occupied";
                return false;
            }
        }
        return true;
    }

    protected bool GroundFlat(vector point)
    {
        m_GroundRise = 0;
        if (GetGame().SurfaceIsSea(point[0], point[2]) || GetGame().SurfaceIsPond(point[0], point[2]))
        {
            m_BlockingClass = "water";
            return false;
        }
        float height = point[1];
        // Conservative 2.4m footprint; reject steep yards instead of sinking props.
        m_GroundRise = Math.AbsFloat(GetGame().SurfaceY(point[0] - 1.2, point[2] - 1.2) - height);
        float rise = Math.AbsFloat(GetGame().SurfaceY(point[0] + 1.2, point[2] - 1.2) - height);
        if (rise > m_GroundRise) { m_GroundRise = rise; }
        rise = Math.AbsFloat(GetGame().SurfaceY(point[0] - 1.2, point[2] + 1.2) - height);
        if (rise > m_GroundRise) { m_GroundRise = rise; }
        rise = Math.AbsFloat(GetGame().SurfaceY(point[0] + 1.2, point[2] + 1.2) - height);
        if (rise > m_GroundRise) { m_GroundRise = rise; }
        return m_GroundRise <= 0.25;
    }

    // As in HCSceneKits.LayoutOffset/LayoutYaw: bounded mirrored layouts,
    // followed by the same keepout/collision checks. Rotating a whole yard
    // about the barn pivot would put props in end-door approaches, so keep
    // all eight variants on its windowless side and move the anchor outward.
    protected vector HCYardOffset(float localZ, int variant)
    {
        int outward = variant;
        float shiftedZ = localZ;
        if (variant >= 4)
        {
            outward = variant - 4;
            shiftedZ = -localZ + 1;
        }
        return Vector(-13.5 - 2.5 * outward, 0, shiftedZ);
    }

    protected bool HCInBarnAccessStrip(vector offset)
    {
        // 1.2m prop footprint + 0.3m collision margin. End approaches and
        // the entire barn clipping envelope stay clear in every variant.
        if (offset[0] + 1.5 >= -10.5) { return true; }
        if (offset[2] - 1.5 <= -6) { return true; }
        return offset[2] + 1.5 >= 6;
    }

    protected Object PlaceProp(Object house, HCInteriorTemplate layout, string propType, float localZ)
    {
        m_PropType = propType;
        m_BlockingClass = "none";
        m_QueryObjects = 0;
        m_QueryCargos = 0;
        m_CollisionCount = 0;
        m_GroundRise = 0;
        m_RefusalReason = "";
        vector offset = HCYardOffset(localZ, m_LayoutVariant);
        vector point = house.ModelToWorld(offset);
        point[1] = GetGame().SurfaceY(point[0], point[2]);
        m_RefusalPoint = point;
        if (!GetGame().ConfigIsExisting("CfgVehicles " + propType) || !GetGame().IsKindOf(propType, "HouseNoDestruct")) { return RefuseProp("static_class_missing"); }
        if (HCInBarnAccessStrip(offset)) { return RefuseProp("access_strip"); }
        if (!GroundFlat(point)) { return RefuseProp("terrain"); }
        if (!Available(point)) { return null; }
        Object prop = HCInteriorTemplatePlacement.Spawn(propType, point, house.GetOrientation());
        if (!prop) return RefuseProp("create_failed");
        vector clip[2];
        prop.ClippingInfo(clip);
        vector propMin = clip[0];
        vector propMax = clip[1];
        // Use actual native bounds, never a guessed furniture footprint. Both
        // objects share orientation, so their model axes agree (including tilt).
        // Simple statements with named locals: the single nine-term condition
        // crashed the native server (Wine compile 152) right at this check.
        array<float> propMinCoordinates = Coordinates(propMin);
        array<float> propMaxCoordinates = Coordinates(propMax);
        bool boundsOk = HCInteriorTemplates.BoxValid(propMinCoordinates, propMaxCoordinates);
        float minX = propMin[0];
        float maxX = propMax[0];
        float minY = propMin[1];
        float maxY = propMax[1];
        float minZ = propMin[2];
        float maxZ = propMax[2];
        if (minX < -1.2 || maxX > 1.2) boundsOk = false;
        if (minZ < -1.2 || maxZ > 1.2) boundsOk = false;
        if (minY < -2 || maxY > 2) boundsOk = false;
        if (maxY - minY > 2) boundsOk = false;
        if (!boundsOk)
        {
            DeleteProp(prop);
            return RefuseProp("prop_bounds");
        }
        point[1] = point[1] - propMin[1];
        prop.SetPosition(point);
        HCInteriorTemplatePropSlot slot = new HCInteriorTemplatePropSlot;
        slot.Room = 1;
        slot.Position = Coordinates(house.WorldToModel(point));
        slot.Orientation = Coordinates("0 0 0");
        slot.Bounds = new HCInteriorTemplateBox;
        vector localPoint = HCInteriorTemplates.AsVector(slot.Position);
        slot.Bounds.Min = Coordinates(localPoint + propMin);
        slot.Bounds.Max = Coordinates(localPoint + propMax);
        array<Object> excluded = new array<Object>;
        excluded.Insert(prop);
        vector center = prop.ModelToWorld((propMin + propMax) * 0.5);
        vector size = propMax - propMin + Vector(0.6, 0.1, 0.6);
        if (!HCInteriorTemplates.SlotClear(layout, slot))
        {
            DeleteProp(prop);
            return RefuseProp("keepout");
        }
        array<Object> collided = new array<Object>;
        if (GetGame().IsBoxColliding(center, prop.GetOrientation(), size, excluded, collided))
        {
            m_CollisionCount = collided.Count();
            foreach (Object blocker : collided)
            {
                if (!blocker) { continue; }
                if (m_BlockingClass == "none") { m_BlockingClass = blocker.GetType(); }
            }
            DeleteProp(prop);
            return RefuseProp("collision");
        }
        return prop;
    }

    protected Object RefuseProp(string reason)
    {
        if (m_RefusalReason == "") m_RefusalReason = reason;
        return null;
    }

    protected void RefuseShelter(HCShelterEntry entry, string reason)
    {
        m_Refused = m_Refused + 3;
        Print("[HollowCountry] V2 shelter refused name=" + entry.Name + " reason=" + reason + HCRefusalDetails());
    }

    protected string HCRefusalDetails()
    {
        string queryCounts = " objects=" + m_QueryObjects.ToString() + " cargos=" + m_QueryCargos.ToString() + " collisions=" + m_CollisionCount.ToString();
        return " variant=" + m_LayoutVariant.ToString() + " prop=" + m_PropType + " blocking_class=" + m_BlockingClass + queryCounts + " cap=256 rise=" + m_GroundRise.ToString() + " rise_limit=0.25 point=" + m_RefusalPoint.ToString();
    }

    protected void PlaceShelter(int index)
    {
        HCShelterEntry entry = HCShelterCatalog.Get(index);
        if (!entry) { return; }
        entry.Placed = false;
        entry.PlacementAnchor = null;
        m_RefusalReason = "";
        m_BlockingClass = "none";
        m_PropType = "none";
        m_QueryObjects = 0;
        m_QueryCargos = 0;
        m_CollisionCount = 0;
        m_GroundRise = 0;
        m_LayoutVariant = 0;
        m_RefusalPoint = entry.Position;
        HCInteriorFurnishRow binding = new HCInteriorFurnishRow;
        binding.BuildingClass = HCShelterCatalog.BUILDING_CLASS;
        binding.Position = Coordinates(entry.Position);
        Object house = HCInteriorTemplatePlacement.Resolve(binding);
        if (!house)
        {
            RefuseShelter(entry, "building_unresolved_or_tilted");
            return;
        }
        vector houseClip[2];
        house.ClippingInfo(houseClip);
        // Refuse changed/unknown geometry instead of trusting a class name.
        if (!HCInteriorRules.SaneVector(houseClip[0], 20) || !HCInteriorRules.SaneVector(houseClip[1], 20) || vector.DistanceSq(houseClip[0], "-8.48698 -5.7232 -15.659") > 0.04 || vector.DistanceSq(houseClip[1], "8.48698 5.7232 15.659") > 0.04)
        {
            RefuseShelter(entry, "building_bounds");
            return;
        }
        HCInteriorTemplate layout = YardLayout();
        array<Object> batch = new array<Object>;
        // Fire spot is a cold STATIC grate, never an inventory fireplace.
        Object fireSpot;
        Object chair;
        Object emptyBox;
        while (m_LayoutVariant < 8)
        {
            fireSpot = PlaceProp(house, layout, "StaticObj_Furniture_fireplace_grill", 0);
            if (fireSpot)
            {
                batch.Insert(fireSpot);
                chair = PlaceProp(house, layout, "StaticObj_Misc_Chair_Camp1", -3);
                if (chair)
                {
                    batch.Insert(chair);
                    emptyBox = PlaceProp(house, layout, "StaticObj_Furniture_PaperBox_01_small_closed", 3);
                    if (emptyBox) { batch.Insert(emptyBox); }
                }
            }
            if (batch.Count() == 3) { break; }
            // Roll back the whole candidate before trying a shifted layout.
            foreach (Object partialProp : batch) { DeleteProp(partialProp); }
            batch.Clear();
            Print("[HollowCountry] V2 shelter layout refused name=" + entry.Name + " reason=" + m_RefusalReason + HCRefusalDetails());
            if (m_LayoutVariant == 7) { break; }
            m_LayoutVariant = m_LayoutVariant + 1;
        }
        if (batch.Count() != 3)
        {
            RefuseShelter(entry, m_RefusalReason);
            return;
        }
        foreach (Object completedProp : batch)
        {
            m_Objects.Insert(completedProp);
            GetGame().UpdatePathgraphRegionByObject(completedProp);
        }
        m_Placed = m_Placed + 1;
        entry.Placed = true;
        entry.PlacementAnchor = fireSpot;
        Print("[HollowCountry] V2 shelter placed name=" + entry.Name + " variant=" + m_LayoutVariant.ToString());
    }

    protected void DeleteProp(Object prop)
    {
        if (!prop || !GetGame() || !GetGame().IsServer()) return;
        for (int shelterIndex = 0; shelterIndex < HCShelterCatalog.Count(); shelterIndex++)
        {
            HCShelterEntry entry = HCShelterCatalog.Get(shelterIndex);
            if (entry.PlacementAnchor != prop) { continue; }
            entry.Placed = false;
            entry.PlacementAnchor = null;
        }
        vector position = prop.GetPosition();
        // Covers the bounded yard prop plus its 0.3m collision margin. Update
        // AFTER deletion, so the pathgraph does not retain the removed blocker.
        GetGame().ObjectDelete(prop);
        GetGame().UpdatePathgraphRegion(position - Vector(3, 3, 3), position + Vector(3, 3, 3));
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCShelterModule);
    }
}
