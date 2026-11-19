// LC-T206, EXP-T5 / EXP-S3. Server-owned static exterior scenes.
// Regional scenes: one three-prop transaction per shared-budget tick; no retry
// after a real placement refusal. Native API citations below also cover this path.
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
// Soft vegetation: 3_Game/Entities/Object.c:613 IsBush (overridden true by
// BushHard/BushSoft at 4_World/Entities/Core/Inherited/Plant.c:76/96) and
// :577 IsInventoryItem; vanilla already treats bushes as non-blocking for
// crew access at 3_Game/Vehicles/Transport.c:810. Bushes are never deleted:
// no replicated map-object removal API was observed, so a yard prop may share
// space with a bush instead. Ring bearings: 1_Core/proto/EnMath.c:17 DEG2RAD,
// :331 Sin, :343 Cos; 1_Core/proto/EnScript.c:389/399 array Set/Get;
// 3_Game/Entities/Object.c:287 GetPosition for the ring placement log.
// 1_Core/proto/EnDebug.c:96 Print.
// Reused read-only HCInteriorTemplatePlacement.Resolve/Spawn and
// HCInteriorTemplates.SlotClear/BoxValid/AsVector. No acceptance gate bypass in
// Interiors: these V2 scenes follow EnableTravel and only LOG native verdicts.
class HCShelterModule : HCModule
{
    protected bool m_Started;
    protected bool m_CandidateSurveyReported;
    protected int m_RegionalCursor;
    protected int m_RegionalFailed;
    protected string m_RegionalReason;
    protected ref HCShelterRegionalScene m_RegionalScene;
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
    // Startup-only fallback when all eight authored variants fail: one screen
    // of at most HC_RING_CANDIDATES yard anchors (SurfaceY only, 15 reads per
    // candidate) and at most HC_RING_ATTEMPTS full prop placements.
    static const int HC_RING_CANDIDATES = 16;
    static const int HC_RING_ATTEMPTS = 4;
    static const float HC_RING_INNER = 6.0;
    static const float HC_RING_OUTER = 12.0;
    protected int m_RingCandidate = -1;
    protected float m_RingRise;
    protected int m_SoftVegetation;
    protected ref array<float> m_RingRises = new array<float>();
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "Shelters"; }

    // Ready follows a running placement service and at least one placed shelter.
    // Missing regional data or actual regional placement failure is degraded;
    // pending native acceptance alone never blocks the admitted scene queue.
    override HCOperationalStatus HCGetOperationalStatus()
    {
        string fault = "";
        if (m_Started && m_Placed < 1) { fault = "no_shelter_placed"; }
        if (m_Started && m_RegionalFailed > 0) { fault = "regional_scene_placement_failed"; }
        if (m_Started && HCShelterCatalog.HCRegionalFault() != "") { fault = HCShelterCatalog.HCRegionalFault(); }
        HCModuleReadiness.HCDerive(m_Operational, m_Started, "", fault, "shelters_placed_regional_queue_admitted");
        return m_Operational;
    }

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

    override void OnTick(float deltaTime)
    {
        if (!m_Started || !GetGame() || !GetGame().IsServer()) { return; }
        string regionalWorld = GetGame().GetWorldName();
        regionalWorld.ToLower();
        if (regionalWorld != "chernarusplus") { return; }
        HCRegionalTick();
    }

    // No recurring retries for failed scenes; startup tries at most eight layouts,
    // one 16-candidate terrain screen and HC_RING_ATTEMPTS ring placements.
    override void OnStop()
    {
        if (!m_Started) return;
        array<Object> ownedProps = m_Objects;
        foreach (Object ownedProp : ownedProps)
        {
            DeleteProp(ownedProp);
        }
        m_Objects.Clear();
        m_Placed = 0;
        m_Refused = 0;
        m_Started = false;
        m_RegionalFailed = 0;
        m_RegionalCursor = 0;
        m_RegionalScene = null;
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
        // The yard is the windowless west side only (model x < -11.5). Both end
        // doors are approached along z within the barn width, so the door lanes
        // span the full clipping width +2 m (x -10.5..10.5) out to 30 m beyond
        // each end; the east side door and inner south stairs stay inside that
        // reserved body/lane. The west yard may then extend along the side
        // wall for the bounded ring fallback without touching any approach.
        HCInteriorTemplate layout = new HCInteriorTemplate;
        HCInteriorTemplateRoom yard = new HCInteriorTemplateRoom;
        yard.Id = 1;
        yard.Min = Coordinates("-31 -20 -30");
        yard.Max = Coordinates("-11.5 20 30");
        layout.Rooms.Insert(yard);
        Keepout(layout, "door", 0, "-10.5 -20 -30", "10.5 20 30");
        Keepout(layout, "stair", 0, "-10.5 -20 -17.7", "10.5 20 -6");
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
            if (HCSoftVegetation(possibleOrphan))
            {
                m_SoftVegetation = m_SoftVegetation + 1;
                continue;
            }
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
        // 1.2m prop footprint + 0.3m collision margin. The barn clipping
        // envelope, its walk-around lane and both end-door approach lanes
        // (all at model x >= -10.5) stay clear; the yard stays within 30 m.
        if (offset[0] + 1.5 >= -10.5) { return true; }
        if (offset[0] - 1.5 <= -31) { return true; }
        if (offset[2] - 1.5 <= -30) { return true; }
        return offset[2] + 1.5 >= 30;
    }

    // Bushes (BushHard/BushSoft) are soft vegetation: never a yard blocker and
    // never deleted. Anything that is an inventory item still blocks.
    protected bool HCSoftVegetation(Object candidate)
    {
        if (!candidate) { return false; }
        if (candidate.IsInventoryItem()) { return false; }
        return candidate.IsBush();
    }

    // Ring candidate shift in the barn model frame around the variant-0 yard
    // anchor: 0..7 at HC_RING_INNER, 8..15 at HC_RING_OUTER, 45 degree steps,
    // bearing 0 pointing outward (away from the windowless wall).
    protected vector HCRingShift(int candidate)
    {
        float radius = HC_RING_INNER;
        int bearing = candidate;
        if (candidate >= 8)
        {
            radius = HC_RING_OUTER;
            bearing = candidate - 8;
        }
        float angle = bearing * 45 * Math.DEG2RAD;
        return Vector(-radius * Math.Cos(angle), 0, radius * Math.Sin(angle));
    }

    protected vector HCRingOffset(float localZ, int candidate)
    {
        vector shift = HCRingShift(candidate);
        return Vector(-13.5 + shift[0], 0, localZ + shift[2]);
    }

    // Worst footprint rise of the three yard props at one ring candidate, or
    // -1 when any prop would enter the reserved barn strip, water or a slope.
    protected float HCRingRise(Object house, int candidate)
    {
        float worst = 0;
        int propIndex = 0;
        while (propIndex < 3)
        {
            float localZ = -3 + 3 * propIndex;
            vector offset = HCRingOffset(localZ, candidate);
            if (HCInBarnAccessStrip(offset)) { return -1; }
            vector point = house.ModelToWorld(offset);
            point[1] = GetGame().SurfaceY(point[0], point[2]);
            if (!GroundFlat(point)) { return -1; }
            if (m_GroundRise > worst) { worst = m_GroundRise; }
            propIndex = propIndex + 1;
        }
        return worst;
    }

    // One bounded terrain screen per shelter; returns admissible candidates.
    protected int HCScreenRing(Object house)
    {
        m_RingRises.Clear();
        int admissible = 0;
        int candidate = 0;
        while (candidate < HC_RING_CANDIDATES)
        {
            float rise = HCRingRise(house, candidate);
            m_RingRises.Insert(rise);
            if (rise >= 0) { admissible = admissible + 1; }
            candidate = candidate + 1;
        }
        return admissible;
    }

    // Flattest untried screened candidate (each is offered once), or -1.
    protected int HCNextRingCandidate()
    {
        int best = -1;
        float bestRise = 0;
        int candidate = 0;
        while (candidate < m_RingRises.Count())
        {
            float rise = m_RingRises.Get(candidate);
            if (rise >= 0 && (best < 0 || rise < bestRise))
            {
                best = candidate;
                bestRise = rise;
            }
            candidate = candidate + 1;
        }
        if (best >= 0)
        {
            m_RingRises.Set(best, -1);
            m_RingRise = bestRise;
        }
        return best;
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
        if (m_RingCandidate >= 0) { offset = HCRingOffset(localZ, m_RingCandidate); }
        if (m_RegionalScene)
        {
            int regionalSlot = 0;
            if (localZ < 0) { regionalSlot = 1; }
            if (localZ > 0) { regionalSlot = 2; }
            offset = HCInteriorTemplates.AsVector(m_RegionalScene.Slots[regionalSlot]);
        }
        vector point = house.ModelToWorld(offset);
        point[1] = GetGame().SurfaceY(point[0], point[2]);
        m_RefusalPoint = point;
        if (m_RegionalScene && !HCObserverTransitionGate.CanTransition(point, HCShelterCatalog.HCRegionalConfig().ObserverDistance)) { return RefuseProp("observed_regional_prop"); }
        if (!GetGame().ConfigIsExisting("CfgVehicles " + propType) || !GetGame().IsKindOf(propType, "HouseNoDestruct")) { return RefuseProp("static_class_missing"); }
        if (!m_RegionalScene && HCInBarnAccessStrip(offset)) { return RefuseProp("access_strip"); }
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
            int hardCollisions = 0;
            foreach (Object blocker : collided)
            {
                if (!blocker) { continue; }
                if (HCSoftVegetation(blocker))
                {
                    m_SoftVegetation = m_SoftVegetation + 1;
                    continue;
                }
                hardCollisions = hardCollisions + 1;
                if (m_BlockingClass == "none") { m_BlockingClass = blocker.GetType(); }
            }
            m_CollisionCount = hardCollisions;
            if (hardCollisions > 0)
            {
                DeleteProp(prop);
                return RefuseProp("collision");
            }
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
        string ring = " ring=" + m_RingCandidate.ToString() + " soft_vegetation=" + m_SoftVegetation.ToString();
        return " variant=" + m_LayoutVariant.ToString() + ring + " prop=" + m_PropType + " blocking_class=" + m_BlockingClass + queryCounts + " cap=256 rise=" + m_GroundRise.ToString() + " rise_limit=0.25 point=" + m_RefusalPoint.ToString();
    }

    // Once per owner lifetime, bounded by the five authored survey rows.
    // A missing package is a real fault; native verdicts are admission-only.
    // Print: installed 1_Core/proto/EnDebug.c:96; array access is catalog-only.
    protected void HCReportCandidateSurveys()
    {
        if (m_CandidateSurveyReported) { return; }
        m_CandidateSurveyReported = true;
        HCShelterRegionalConfig candidateConfig = HCShelterCatalog.HCRegionalConfig();
        if (!candidateConfig)
        {
            Print("[HC Shelters] regional_scene_data_missing_or_invalid source=travel/auditshelter_scenes.json runtime=PENDING");
            return;
        }
        if (!candidateConfig.Enabled)
        {
            Print("[HC Shelters] regional_scenes=off operator=Enabled runtime=PENDING");
            return;
        }
        int candidateIndex = 0;
        while (candidateIndex < HCShelterCatalog.CandidateCount())
        {
            HCShelterSurvey candidate = HCShelterCatalog.GetCandidate(candidateIndex);
            if (candidate && candidateConfig.Scenes[candidateIndex].Enabled)
            {
                Print("[HC Shelters] candidate=" + candidate.Id + " admission=authored_exterior_scene access=" + candidate.Refusal + " source=travel/auditshelter_scenes.json runtime=PENDING");
            }
            candidateIndex = candidateIndex + 1;
        }
    }

    protected void PlaceShelter(int index)
    {
        if (index == 0) { HCReportCandidateSurveys(); }
        HCShelterEntry entry = HCShelterCatalog.Get(index);
        if (!entry) { return; }
        if (entry.Scene) { entry.Attempted = false; return; }
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
        m_RingCandidate = -1;
        m_RingRise = 0;
        m_SoftVegetation = 0;
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
        bool complete = false;
        while (m_LayoutVariant < 8)
        {
            complete = HCPlaceBatch(house, layout, batch);
            if (complete) { break; }
            Print("[HollowCountry] V2 shelter layout refused name=" + entry.Name + " reason=" + m_RefusalReason + HCRefusalDetails());
            if (m_LayoutVariant == 7) { break; }
            m_LayoutVariant = m_LayoutVariant + 1;
        }
        int admissible = 0;
        int attempts = 0;
        if (!complete)
        {
            string variantReason = m_RefusalReason;
            // Bounded nearby fallback: one 16-candidate terrain screen, then at
            // most HC_RING_ATTEMPTS full placements, flattest candidate first.
            admissible = HCScreenRing(house);
            while (attempts < HC_RING_ATTEMPTS)
            {
                m_RingCandidate = HCNextRingCandidate();
                if (m_RingCandidate < 0) { break; }
                attempts = attempts + 1;
                complete = HCPlaceBatch(house, layout, batch);
                if (complete) { break; }
                Print("[HollowCountry] V2 shelter ring candidate refused name=" + entry.Name + " reason=" + m_RefusalReason + HCRefusalDetails());
            }
            if (!complete)
            {
                Print("[HollowCountry] V2 shelter ring exhausted name=" + entry.Name + " candidates=" + HC_RING_CANDIDATES.ToString() + " admissible=" + admissible.ToString() + " attempts=" + attempts.ToString() + " cap=" + HC_RING_ATTEMPTS.ToString());
                if (attempts == 0) { m_RefusalReason = variantReason; }
                m_RingCandidate = -1;
                RefuseShelter(entry, m_RefusalReason);
                return;
            }
        }
        Object fireSpot = batch.Get(0);
        foreach (Object completedProp : batch)
        {
            m_Objects.Insert(completedProp);
            GetGame().UpdatePathgraphRegionByObject(completedProp);
        }
        m_Placed = m_Placed + 1;
        entry.Placed = true;
        entry.PlacementAnchor = fireSpot;
        if (m_RingCandidate >= 0)
        {
            Print("[HollowCountry] V2 shelter placed name=" + entry.Name + " variant=ring candidate=" + m_RingCandidate.ToString() + " rise=" + m_RingRise.ToString() + " admissible=" + admissible.ToString() + " attempts=" + attempts.ToString() + " soft_vegetation=" + m_SoftVegetation.ToString() + " point=" + fireSpot.GetPosition().ToString());
            m_RingCandidate = -1;
            return;
        }
        Print("[HollowCountry] V2 shelter placed name=" + entry.Name + " variant=" + m_LayoutVariant.ToString() + " soft_vegetation=" + m_SoftVegetation.ToString());
    }

    // Dedicated consumer preserves progress after Interiors spends its slice.
    // One complete 3-prop attempt costs configured units.
    // Observer veto leaves the row pending; all other failures are tried once.
    protected void HCRegionalTick()
    {
        HCShelterRegionalConfig config = HCShelterCatalog.HCRegionalConfig();
        if (!config || !config.Enabled) { return; }
        if (m_RegionalCursor >= HCShelterCatalog.Count()) { m_RegionalCursor = 0; }
        HCShelterEntry entry = HCShelterCatalog.Get(m_RegionalCursor);
        m_RegionalCursor = m_RegionalCursor + 1;
        if (!entry || !entry.Scene || !entry.Scene.Enabled || entry.Attempted) { return; }
        HCUnitBudget shared = HCServer.HCTickWork();
        if (!shared.HCTakeFor(HCUnitBudget.HC_WORK_SHELTER, config.WorkUnits)) { return; }
        if (!HCObserverTransitionGate.CanTransition(entry.Position, config.ObserverDistance)) { return; }
        entry.Attempted = true;
        HCPlaceRegional(entry);
    }

    protected bool HCRegionalRefuse(string reason)
    {
        m_RegionalFailed = m_RegionalFailed + 1;
        if (reason != m_RegionalReason)
        {
            m_RegionalReason = reason;
            Print("[HC Shelters] regional_refused=" + reason + " runtime=PENDING");
        }
        return false;
    }

    protected void HCPlaceRegional(HCShelterEntry entry)
    {
        m_RegionalScene = null;
        HCShelterRegionalScene scene = entry.Scene;
        HCInteriorFurnishRow binding = new HCInteriorFurnishRow;
        binding.BuildingClass = scene.BuildingClass;
        binding.Position = scene.Position;
        Object house = HCInteriorTemplatePlacement.Resolve(binding);
        if (!house) { HCRegionalRefuse("building_unresolved_or_tilted:" + scene.Id); return; }
        vector regionalClip[2];
        house.ClippingInfo(regionalClip);
        float tolerance = HCShelterCatalog.HCRegionalConfig().BoundsToleranceSquared;
        if (vector.DistanceSq(regionalClip[0], HCInteriorTemplates.AsVector(scene.ClipMin)) > tolerance || vector.DistanceSq(regionalClip[1], HCInteriorTemplates.AsVector(scene.ClipMax)) > tolerance)
        {
            HCRegionalRefuse("building_bounds:" + scene.Id);
            return;
        }
        HCInteriorTemplate layout = new HCInteriorTemplate;
        HCInteriorTemplateRoom yard = new HCInteriorTemplateRoom;
        yard.Id = 1;
        yard.Min = scene.YardMin;
        yard.Max = scene.YardMax;
        layout.Rooms.Insert(yard);
        vector accessMinimum = HCInteriorTemplates.AsVector(scene.AccessMin);
        vector accessMaximum = HCInteriorTemplates.AsVector(scene.AccessMax);
        Keepout(layout, "walkway", 0, accessMinimum, accessMaximum);
        array<Object> batch = new array<Object>;
        m_RingCandidate = -1;
        m_LayoutVariant = 0;
        m_RegionalScene = scene;
        if (!HCPlaceBatch(house, layout, batch))
        {
            m_RegionalScene = null;
            // HCPlaceBatch already rolled back every partial prop. A player
            // near a prop can veto after the anchor passed; retry on a later tick.
            if (m_RefusalReason == "observed_regional_prop")
            {
                entry.Attempted = false;
                return;
            }
            HCRegionalRefuse(m_RefusalReason + ":" + scene.Id);
            return;
        }
        m_RegionalScene = null;
        // The synchronous transaction cannot interleave a core tick. All three
        // props passed terrain, exact bounds, keepout and native collision checks.
        // No inventory, roof copy, durable loot or parallel world ledger is made.
        foreach (Object regionalProp : batch)
        {
            m_Objects.Insert(regionalProp);
            GetGame().UpdatePathgraphRegionByObject(regionalProp);
        }
        entry.PlacementAnchor = batch.Get(0);
        entry.Placed = true;
        m_Placed = m_Placed + 1;
        Print("[HC Shelters] regional_placed=" + scene.Id + " props=3 runtime=PENDING");
    }

    // Places the three yard props of the current variant or ring candidate,
    // or rolls the whole candidate back. The fire spot is a cold STATIC grate,
    // never an inventory fireplace, and is always batch[0] (the anchor).
    protected bool HCPlaceBatch(Object house, HCInteriorTemplate layout, array<Object> batch)
    {
        Object fireSpot = PlaceProp(house, layout, "StaticObj_Furniture_fireplace_grill", 0);
        if (fireSpot)
        {
            batch.Insert(fireSpot);
            Object chair = PlaceProp(house, layout, "StaticObj_Misc_Chair_Camp1", -3);
            if (chair)
            {
                batch.Insert(chair);
                Object emptyBox = PlaceProp(house, layout, "StaticObj_Furniture_PaperBox_01_small_closed", 3);
                if (emptyBox) { batch.Insert(emptyBox); }
            }
        }
        if (batch.Count() == 3) { return true; }
        foreach (Object partialProp : batch) { DeleteProp(partialProp); }
        batch.Clear();
        return false;
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
