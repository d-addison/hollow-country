// LC-T206, EXP-T5 / EXP-S3. Server-owned static exterior scenes.
// Regional scenes: one retained transaction, one retained substep per admission; bounded
// nearby layouts keep collision/terrain refusals from discarding an entire site.
// Native API citations below also cover this path.
// Sub-step timing: installed 1_Core/proto/EnSystem.c:106 TickCount (raw ticks).
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
enum HCShelterPropStage
{
    PREPARE,
    OCCUPIED_QUERY,
    OCCUPIED_FILTER,
    CREATE,
    ORIENT,
    SPAWN_SNAP,
    BOUNDS,
    GROUND_SUPPORT,
    FOOTPRINT,
    KEEPOUT,
    COLLISION_QUERY,
    COLLISION_FILTER,
    COMPLETE
}

// Folds the placed props of one regional scene into its pathgraph bounds across stages, a few
// props per admission, through HCBoundedJob. The module owns the batch and the region; the job
// holds weak pointers to them and finishes as empty if either is freed.
class HCShelterBoundsJob : HCBoundedJob
{
    array<Object> Batch;
    HCPathgraphRefresh Region;

    void HCStart(array<Object> batch, HCPathgraphRefresh region)
    {
        Batch = batch;
        Region = region;
        // The module is a plain class and owns this job by ref, so it cannot be tracked weakly.
        HCBegin(null);
    }

    override int HCItemCount()
    {
        if (!Batch || !Region) { return 0; }
        return Batch.Count();
    }

    override string HCJobModule() { return "Shelters"; }

    override void HCOnClear()
    {
        Batch = null;
        Region = null;
    }

    override int HCStepItem(int index)
    {
        Region.Include(Batch[index]);
        return ITEM_ADVANCE;
    }
}

class HCShelterModule : HCModule
{
    protected string m_StatusLogLine;
    protected float m_StatusLogAt;
    protected bool m_Started;
    protected bool m_CandidateSurveyReported;
    protected int m_RegionalCursor;
    protected int m_RegionalFailed;
    protected int m_RegionalPlaced;
    protected int m_RegionalRemaining;
    protected int m_RegionalNearbyRetries;
    protected float m_RegionalSummarySeconds;
    protected ref map<string, int> m_RegionalRefusals = new map<string, int>;
    protected ref map<string, int> m_RegionalCandidateRefusals = new map<string, int>;
    protected string m_RegionalFailedSites;
    protected ref map<string, int> m_RegionalSideRefusals = new map<string, int>;
    // Preserve all authored-side attempts before trying the other three sides.
    // Each side retains the same finite yard envelope and per-grant substeps.
    static const int HC_REGIONAL_LAYOUTS_PER_SIDE = 35;
    static const int HC_REGIONAL_LAYOUTS = 140;
    protected ref HCShelterRegionalScene m_RegionalScene;
    // One retained regional transaction: resolve/layout, one prop substep, or one
    // pathgraph update per SHELTER admission. Publish the anchor only at end.
    protected ref HCShelterEntry m_RegionalJobEntry;
    protected Object m_RegionalHouse;
    protected ref HCInteriorTemplate m_RegionalLayout;
    protected ref array<Object> m_RegionalBatch = new array<Object>;
    protected ref HCShelterBoundsJob m_RegionalBounds = new HCShelterBoundsJob;
    static const int HC_REGIONAL_BOUNDS_UNITS = 4;
    static const float HC_REGIONAL_BOUNDS_MS = 1.0;
    protected ref HCPathgraphRefresh m_RegionalRegion;
    // A private cursor never publishes partial props. Native calls cannot be
    // preempted; each costly query/create/snap/rebuild has its own admission.
    protected ref HCInteriorResolveCursor m_RegionalResolve;
    protected ref HCInteriorFurnishRow m_RegionalBinding;
    protected Object m_RegionalProp;
    protected HCShelterPropStage m_RegionalPropStep;
    protected vector m_RegionalPoint;
    protected vector m_RegionalMin;
    protected vector m_RegionalMax;
    protected int m_RegionalProbe;
    protected float m_RegionalLow;
    protected float m_RegionalHigh;
    protected ref array<Object> m_RegionalNearby = new array<Object>;
    protected ref array<CargoBase> m_RegionalCargos = new array<CargoBase>;
    protected int m_RegionalInspect;
    protected ref array<ref HCPathgraphRefresh> m_PathgraphPending = new array<ref HCPathgraphRefresh>;
    protected string m_StepKind;
    protected string m_HeaviestStep = "idle";
    protected int m_HeaviestTicks;
    protected int m_StepWindow;
    protected int m_StepTicks;
    protected int m_StepItems;
    protected int m_WorstSliceTicks;
    protected int m_WorstSliceItems;
    protected ref HCStartupShelters m_Startup;
    protected int m_ResolveWaitFrame = -1;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected int m_StartupPeakTicks;
    protected int m_PathgraphMarked;
    protected int m_PathgraphRegions;
    protected int m_PathgraphSkipped;

    protected void HCQueuePathgraph(HCPathgraphRefresh region)
    {
        m_PathgraphMarked += region.Marked;
        m_PathgraphSkipped += region.SkippedNoGeom;
        if (!region.HasBounds) { return; }
        // Retained locally: no uncharged CallLater rebuild or synchronous
        // pending-cap fallback. Runtime drains one region before more placement.
        m_PathgraphPending.Insert(region);
    }

    protected void HCApplyPathgraph(HCPathgraphRefresh region)
    {
        if (!GetGame() || !region) { return; }
        region.Update();
        m_PathgraphRegions++;
        HCModuleReadiness.HCUse("Shelters", "pathgraph_refresh");
    }

    protected bool m_RegionalRollingBack;
    protected int m_Placed;
    protected int m_Refused;
    protected string m_RefusalReason;
    protected string m_BlockingClass;
    protected string m_PropType;
    protected string m_KeepoutCheck;
    protected vector m_RefusalPoint;
    protected vector m_SlotMinimum;
    protected vector m_SlotMaximum;
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

    override void RegisterUses()
    {
        HCModuleReadiness.HCRegisterUse("Shelters", "shelter_placed");
        HCModuleReadiness.HCRegisterUse("Shelters", "pathgraph_refresh");
    }

    override void PerfSampleCosts(HCPerfSampler sampler, int slot, float ticksPerMs)
    {
        sampler.SampleCost(slot, 0, m_StartupPeakTicks);
        m_StartupPeakTicks = 0;
    }

    bool HCStartupPending()
    {
        if (!m_Started) { return false; }
        // Legacy/rollback pathgraph receipts still drain when regional scenes
        // are off; an enabled scene flag alone must not keep the pump spinning.
        if (m_PathgraphPending.Count() > 0) { return true; }
        HCShelterRegionalConfig config = HCShelterCatalog.HCRegionalConfig();
        return config && config.Enabled && m_RegionalRemaining > 0;
    }

    // The one-second module cadence made every query result/corner cost a second.
    // Catch up on the shared startup pump; its deadline/opt-out retains tick fallback.
    // A half-ms cooperative guard leaves room for the last indivisible native call;
    // 16 units also bound a slice before clock calibration. HCContinue admits
    // its first unit before checking elapsed time: that unit visits ONE catalog
    // entry, then ONE retained stage (never a full layout or candidate retry).
    // Filters visit one object/corner; resolve filters at most eight objects;
    // publish/handle checks visit at most three props, pathgraph bounds eight
    // corners. Rollback deletes one prop and scans only the finite catalog.
    // Worst-case slice = 0.5 ms + one indivisible stage plus guard overhead;
    // native query/create/snap/pathgraph latency has no API upper bound. The
    // <=3 ms target therefore remains a native measurement, not a static claim.
    void HCPumpRegional()
    {
        if (!HCStartupPending()) { return; }
        // The shared pump may revisit this owner in the same frame. A deferred
        // resolver is idle for that entire frame, not another 16 failed units.
        if (m_ResolveWaitFrame == GetGame().GetTime()) { return; }
        int sliceStart = TickCount(0);
        int itemsBefore = m_StepItems;
        float sliceMs = 0.5;
        if (HCStartupPump.HCInSlice()) { sliceMs = HCStartupPump.HCSliceMs(sliceMs); }
        m_Work.HCReset(16, sliceMs);
        while (HCStartupPending() && m_Work.HCContinue())
        {
            HCRegionalMeasuredStep();
            if (m_StepKind == "idle") { break; }
        }
        int sliceTicks = TickCount(sliceStart);
        m_StepTicks++;
        if (sliceTicks > m_WorstSliceTicks && m_StepItems > itemsBefore)
        {
            m_WorstSliceTicks = sliceTicks;
            m_WorstSliceItems = m_StepItems - itemsBefore;
        }
        if (HCStartupPump.HCInSlice() && sliceTicks > m_StartupPeakTicks) { m_StartupPeakTicks = sliceTicks; }
    }

    protected void HCRegionalMeasuredStep()
    {
        m_StepKind = "idle";
        int stepStart = TickCount(0);
        HCRegionalTick();
        int stepTicks = TickCount(stepStart);
        if (m_StepKind == "idle") { return; }
        m_StepItems++;
        if (stepTicks > m_HeaviestTicks)
        {
            m_HeaviestTicks = stepTicks;
            m_HeaviestStep = m_StepKind;
            // The shared resolve cursor records the building class, query size and phase of its last
            // native call (soak 176: a 29 ms resolve with no class named).
            if (m_StepKind == "resolve") { m_HeaviestStep = m_StepKind + ":" + HCInteriorTemplatePlacement.HCLastType(); }
        }
    }

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
        m_StatusLogLine = "";
        m_StatusLogAt = 0;
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
            m_Startup = new HCStartupShelters;
            m_Startup.Module = this;
            HCStartupPump.HCRegister(m_Startup, "shelters");
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
        HCPumpRegional();
        m_RegionalSummarySeconds += deltaTime;
        if (m_RegionalSummarySeconds >= 300)
        {
            m_RegionalSummarySeconds = 0;
            HCRegionalSummary();
            m_StepWindow++;
            // Same raw TickCount/heaviest fields as the shared HCStepTimer.
            // Only the five-minute heartbeat emits this bounded diagnostic.
            string stepLine = "[HC Step] owner=Shelters window=" + m_StepWindow.ToString() + " ticks=" + m_StepTicks.ToString();
            stepLine += " worst_tick_ticks=" + m_WorstSliceTicks.ToString() + " worst_tick_items=" + m_WorstSliceItems.ToString();
            stepLine += " other=" + m_WorstSliceTicks.ToString() + " heaviest_item_ticks=" + m_HeaviestTicks.ToString() + " heaviest=" + m_HeaviestStep;
            stepLine += " deferred_n=0 deferred_max_ticks=0; raw TickCount units; runtime acceptance pending";
            if (m_StepItems > 0) { Print("" + stepLine); }
            m_HeaviestTicks = 0;
            m_HeaviestStep = "idle";
            m_StepItems = 0;
            m_StepTicks = 0;
            m_WorstSliceTicks = 0;
            m_WorstSliceItems = 0;
        }
        HCReached.Mark("shelters.regional_tick");
    }

    // Legacy startup tries at most eight layouts, one 16-candidate terrain
    // screen and HC_RING_ATTEMPTS ring placements. Regional retries are finite.
    override void OnStop()
    {
        if (!m_Started) return;
        HCStartupPump.HCFinish(m_Startup);
        if (m_Startup) { m_Startup.Module = null; }
        m_Startup = null;
        HCDrainRegionalBatch();
        HCClearRegionalJob();
        array<Object> ownedProps = m_Objects;
        foreach (Object ownedProp : ownedProps)
        {
            DeleteProp(ownedProp);
        }
        m_Objects.Clear();
        // Shutdown already drains owned objects synchronously; no callbacks
        // survive stop or carry stale regions into a later service lifetime.
        foreach (HCPathgraphRefresh stoppedRegion : m_PathgraphPending) { HCApplyPathgraph(stoppedRegion); }
        m_PathgraphPending.Clear();
        m_HeaviestTicks = 0;
        m_HeaviestStep = "idle";
        m_StepItems = 0;
        m_StepTicks = 0;
        m_WorstSliceTicks = 0;
        m_WorstSliceItems = 0;
        m_StartupPeakTicks = 0;
        m_CandidateSurveyReported = false;
        m_Placed = 0;
        m_Refused = 0;
        m_Started = false;
        m_RegionalFailed = 0;
        m_RegionalPlaced = 0;
        m_RegionalRemaining = 0;
        m_RegionalNearbyRetries = 0;
        m_RegionalSummarySeconds = 0;
        m_RegionalRefusals.Clear();
        m_RegionalCandidateRefusals.Clear();
        m_RegionalSideRefusals.Clear();
        m_RegionalFailedSites = "";
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

    protected vector HCRegionalShift(int variant)
    {
        variant = variant % HC_REGIONAL_LAYOUTS_PER_SIDE;
        int row = variant / 5;
        int lateral = variant % 5;
        float outward = 3 * row;
        float nearShift = 3;
        float farShift = 6;
        if (variant >= 20)
        {
            // Fill gaps between the original rows/columns rather than walking
            // beyond the authored locality/yard. Maximum outward shift is 9m.
            row = (variant - 20) / 5;
            outward = 1.5 + 3 * row;
            nearShift = 1.5;
            farShift = 4.5;
        }
        float shiftZ = 0;
        if (lateral == 1) { shiftZ = nearShift; }
        if (lateral == 2) { shiftZ = -nearShift; }
        if (lateral == 3) { shiftZ = farShift; }
        if (lateral == 4) { shiftZ = -farShift; }
        return Vector(-outward, 0, shiftZ);
    }

    // Side 0=-X (authored), 1=+X, 2=-Z, 3=+Z. Rotate the
    // slot pattern and preserve its distance from the measured building edge,
    // rather than rotating a rectangular building's X edge into its Z edge.
    protected vector HCRegionalRotate(vector point, int side)
    {
        if (side == 1) { return Vector(-point[0], point[1], -point[2]); }
        if (side == 2) { return Vector(-point[2], point[1], point[0]); }
        if (side == 3) { return Vector(point[2], point[1], -point[0]); }
        return point;
    }

    protected vector HCRegionalSidePoint(HCShelterRegionalScene scene, vector point, int variant)
    {
        int side = variant / HC_REGIONAL_LAYOUTS_PER_SIDE;
        if (side == 0) { return point; }
        vector low = HCInteriorTemplates.AsVector(scene.ClipMin);
        vector high = HCInteriorTemplates.AsVector(scene.ClipMax);
        vector center = (low + high) * 0.5;
        vector relative = Vector(point[0] - low[0], point[1], point[2] - center[2]);
        vector rotated = HCRegionalRotate(relative, side);
        if (side == 1) { return rotated + Vector(high[0], 0, center[2]); }
        if (side == 2) { return rotated + Vector(center[0], 0, low[2]); }
        return rotated + Vector(center[0], 0, high[2]);
    }

    // A quarter turn/mirror reverses some corner coordinates. Reorder both
    // opposite corners before passing the axis-aligned box to SlotClear.
    protected void HCRegionalBox(HCInteriorTemplateBox box, vector first, vector second)
    {
        vector low = first;
        vector high = second;
        for (int axis = 0; axis < 3; axis++)
        {
            if (first[axis] > second[axis])
            {
                low[axis] = second[axis];
                high[axis] = first[axis];
            }
        }
        box.Min = Coordinates(low);
        box.Max = Coordinates(high);
    }

    // SlotClear deliberately receives only the authored exterior yard and its
    // full roof/access envelope, never a building's interior room/door data.
    // Keep its verdict authoritative; explain its otherwise ambiguous failure.
    protected string HCRegionalKeepoutCheck(HCInteriorTemplate layout, HCInteriorTemplatePropSlot slot)
    {
        HCInteriorTemplateRoom yard = HCInteriorTemplates.Room(layout, slot.Room);
        if (!yard) { return "yard_missing"; }
        if (!HCInteriorTemplates.BoxValid(slot.Bounds.Min, slot.Bounds.Max)) { return "slot_geometry"; }
        if (!HCInteriorTemplates.Inside(slot.Bounds.Min, yard.Min, yard.Max) || !HCInteriorTemplates.Inside(slot.Bounds.Max, yard.Min, yard.Max)) { return "yard_bounds"; }
        if (!HCInteriorTemplates.VectorValid(slot.Position, 512) || !HCInteriorTemplates.Inside(slot.Position, slot.Bounds.Min, slot.Bounds.Max)) { return "slot_geometry"; }
        foreach (HCInteriorTemplateKeepOut reserved : layout.KeepOuts)
        {
            if (HCInteriorTemplates.Intersects(slot.Bounds.Min, slot.Bounds.Max, reserved.Min, reserved.Max, 0)) { return "access_envelope"; }
        }
        return "slot_geometry";
    }

    protected Object PlaceProp(Object house, HCInteriorTemplate layout, string propType, float localZ)
    {
        m_PropType = propType;
        m_KeepoutCheck = "";
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
            offset = offset + HCRegionalShift(m_LayoutVariant);
        }
        vector point = house.ModelToWorld(offset);
        point[1] = GetGame().SurfaceY(point[0], point[2]);
        m_RefusalPoint = point;
        if (m_RegionalScene && !HCObserverTransitionGate.CanTransition(point, HCShelterCatalog.HCRegionalConfig().ObserverDistance)) { return RefuseProp("observed_regional_prop"); }
        if (!GetGame().ConfigIsExisting("CfgVehicles " + propType) || !GetGame().IsKindOf(propType, "HouseNoDestruct")) { return RefuseProp("static_class_missing"); }
        if (!m_RegionalScene && HCInBarnAccessStrip(offset)) { return RefuseProp("access_strip"); }
        // Regional props use their actual footprint below. The legacy yard's
        // terrain screen intentionally retains its conservative 2.4m footprint.
        if (!m_RegionalScene && !GroundFlat(point)) { return RefuseProp("terrain"); }
        if (GetGame().SurfaceIsSea(point[0], point[2]) || GetGame().SurfaceIsPond(point[0], point[2])) { return RefuseProp("water"); }
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
        if (!HCGroundSnap.Snap(prop))
        {
            DeleteProp(prop);
            return RefuseProp("ground_support");
        }
        point = prop.GetPosition();
        m_RefusalPoint = point;
        if (m_RegionalScene && !HCRegionalFootprintFlat(prop, propMin, propMax))
        {
            DeleteProp(prop);
            return RefuseProp("terrain");
        }
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
            if (m_RegionalScene)
            {
                m_KeepoutCheck = HCRegionalKeepoutCheck(layout, slot);
                m_SlotMinimum = HCInteriorTemplates.AsVector(slot.Bounds.Min);
                m_SlotMaximum = HCInteriorTemplates.AsVector(slot.Bounds.Max);
            }
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

    // Sample the observed prop footprint, not the legacy 2.4m yard square.
    // SurfaceRoadY includes stock road support; HCGroundSnap still requires a
    // native support ray and the original 0.25m slope limit remains in force.
    protected bool HCRegionalFootprintFlat(Object prop, vector minimum, vector maximum)
    {
        float lowest = 1000000;
        float highest = -1000000;
        for (int corner = 0; corner < 4; corner++)
        {
            vector sample = minimum;
            if (corner & 1) { sample[0] = maximum[0]; }
            if (corner & 2) { sample[2] = maximum[2]; }
            vector world = prop.ModelToWorld(sample);
            if (GetGame().SurfaceIsSea(world[0], world[2]) || GetGame().SurfaceIsPond(world[0], world[2])) { m_BlockingClass = "water"; return false; }
            float height = GetGame().SurfaceRoadY(world[0], world[2]);
            if (height < lowest) { lowest = height; }
            if (height > highest) { highest = height; }
        }
        m_GroundRise = highest - lowest;
        return m_GroundRise <= 0.25;
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
        if (m_RefusalReason == "keepout" && m_KeepoutCheck != "") { ring += " keepout_check=" + m_KeepoutCheck + " slot_min=" + m_SlotMinimum.ToString() + " slot_max=" + m_SlotMaximum.ToString(); }
        return " variant=" + m_LayoutVariant.ToString() + ring + " prop=" + m_PropType + " blocking_class=" + m_BlockingClass + queryCounts + " cap=256 rise=" + m_GroundRise.ToString() + " rise_limit=0.25 point=" + m_RefusalPoint.ToString();
    }

    // Once per owner lifetime, bounded by the authored survey catalog.
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
        int enabledCandidates = 0;
        while (candidateIndex < HCShelterCatalog.CandidateCount())
        {
            HCShelterSurvey candidate = HCShelterCatalog.GetCandidate(candidateIndex);
            if (candidate && candidateConfig.Scenes[candidateIndex].Enabled)
            {
                enabledCandidates++;
            }
            candidateIndex = candidateIndex + 1;
        }
        Print("[HC Shelters] candidates=" + candidateIndex.ToString() + " enabled=" + enabledCandidates.ToString() + " admission=authored_exterior_scene source=travel/auditshelter_scenes.json runtime=PENDING");
    }

    protected void PlaceShelter(int index)
    {
        if (index == 0) { HCReportCandidateSurveys(); }
        HCShelterEntry entry = HCShelterCatalog.Get(index);
        if (!entry) { return; }
        if (entry.Scene)
        {
            entry.Attempted = false;
            entry.PlacementVariant = 0;
            entry.Placed = false;
            entry.PlacementAnchor = null;
            if (entry.Scene.Enabled) { m_RegionalRemaining++; }
            return;
        }
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
        HCPathgraphRefresh region = HCInteriorPathgraph.Bounds(batch);
        HCQueuePathgraph(region);
        Object fireSpot = batch.Get(0);
        foreach (Object completedProp : batch)
        {
            m_Objects.Insert(completedProp);
        }
        m_Placed = m_Placed + 1;
        entry.Placed = true;
        HCModuleReadiness.HCUse("Shelters", "shelter_placed");
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
    // Each retained resolve/prop/update/rollback step costs configured units.
    // Observer veto leaves the same candidate pending; placement refusals advance
    // through at most HC_REGIONAL_LAYOUTS candidates across separate ticks.
    protected void HCRegionalTick()
    {
        HCShelterRegionalConfig config = HCShelterCatalog.HCRegionalConfig();
        // Includes legacy startup and rollback regions, even after the last
        // regional scene terminates. Exactly one region consumes this grant.
        if (m_PathgraphPending.Count() > 0)
        {
            int pathCost = 1;
            if (config) { pathCost = config.WorkUnits; }
            if (!HCStartupPump.HCInSlice() && !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_SHELTER, pathCost)) { return; }
            m_StepKind = "pathgraph_refresh";
            HCApplyPathgraph(m_PathgraphPending[0]);
            m_PathgraphPending.RemoveOrdered(0);
            if (m_RegionalRemaining == 0 && m_PathgraphPending.Count() == 0) { HCRegionalSummary(); }
            return;
        }
        if (!config || !config.Enabled || m_RegionalRemaining <= 0) { return; }
        HCShelterEntry entry = m_RegionalJobEntry;
        if (!entry)
        {
            if (m_RegionalCursor >= HCShelterCatalog.Count()) { m_RegionalCursor = 0; }
            entry = HCShelterCatalog.Get(m_RegionalCursor);
            if (!entry || !entry.Scene || !entry.Scene.Enabled || entry.Attempted)
            {
                // One skipped entry per visit, with no shared work charge.
                m_RegionalCursor++;
                return;
            }
        }
        HCUnitBudget shared = HCServer.HCTickWork();
        if (!HCStartupPump.HCInSlice() && !shared.HCTakeFor(HCUnitBudget.HC_WORK_SHELTER, config.WorkUnits)) { return; }
        // Advance only after admission, so a denied grant cannot skip a site.
        if (!m_RegionalJobEntry) { m_RegionalCursor++; }
        m_StepKind = "observer";
        if (m_RegionalRollingBack)
        {
            m_StepKind = "rollback";
            if (m_RegionalProp)
            {
                DeleteProp(m_RegionalProp);
                m_RegionalProp = null;
                return;
            }
            if (m_RegionalBatch.Count() > 0)
            {
                int last = m_RegionalBatch.Count() - 1;
                DeleteProp(m_RegionalBatch[last]);
                m_RegionalBatch.RemoveOrdered(last);
                return;
            }
            HCRegionalBatchRefused(entry);
            return;
        }
        if (!HCObserverTransitionGate.CanTransition(entry.Position, config.ObserverDistance))
        {
            if (m_RegionalJobEntry)
            {
                m_RefusalReason = "observed_regional_prop";
                HCRegionalBatchRefused(entry);
            }
            return;
        }
        entry.Attempted = true;
        HCPlaceRegional(entry);
    }

    protected void HCRegionalSummary()
    {
        // Reasons come only from the finite placement checks, never world rows.
        // One bounded line per five minutes and when the queue completes.
        string refusedReasons = "";
        foreach (string reason, int count : m_RegionalRefusals)
        {
            refusedReasons += reason + ":" + count.ToString() + ",";
        }
        string candidateReasons = "";
        foreach (string candidateReason, int candidateCount : m_RegionalCandidateRefusals)
        {
            candidateReasons += candidateReason + ":" + candidateCount.ToString() + ",";
        }
        string line = "[HC Shelters] regional_summary placed=" + m_RegionalPlaced.ToString() + " refused=" + m_RegionalFailed.ToString() + " pending=" + m_RegionalRemaining.ToString();
        line += " retry=nearby retry_count=" + m_RegionalNearbyRetries.ToString();
        line += " layouts_per_site=" + HC_REGIONAL_LAYOUTS.ToString() + " refused_by_reason=" + refusedReasons + " candidate_refused_by_reason=" + candidateReasons;
        string sideReasons = "";
        foreach (string sideKey, int sideCount : m_RegionalSideRefusals)
        {
            sideReasons += sideKey + ":" + sideCount.ToString() + ",";
        }
        line += " candidate_refused_by_side=" + sideReasons;
        string statusLine = line + " runtime=PENDING";
        // First receipt, changed content, or one unchanged heartbeat per 30 minutes.
        float statusNow = GetGame().GetTickTime();
        if (statusLine != m_StatusLogLine || statusNow < m_StatusLogAt || statusNow - m_StatusLogAt >= 1800)
        {
            Print("" + "[HC Pathgraph] domain=shelters marked=" + m_PathgraphMarked.ToString() + " affected=" + m_PathgraphRegions.ToString() + " skipped_no_geom=" + m_PathgraphSkipped.ToString());
            Print("" + statusLine);
            if (m_RegionalFailed > 0) { Print("[HC Shelters] degraded reason=regional_scene_placement_failed sites=" + m_RegionalFailedSites); }
            m_StatusLogLine = statusLine;
            m_StatusLogAt = statusNow;
        }
    }

    protected void HCRegionalRefuse(HCShelterEntry entry, string reason)
    {
        m_RegionalFailed++;
        if (m_RegionalFailedSites != "") { m_RegionalFailedSites += ","; }
        m_RegionalFailedSites += entry.Scene.Id;
        m_RegionalRemaining--;
        m_RegionalRefusals.Set(reason, m_RegionalRefusals.Get(reason) + 1);
        Print("[HC Shelters] regional_refused=" + entry.Scene.Id + " reason=" + reason + " variant=" + entry.PlacementVariant.ToString() + " rise=" + m_GroundRise.ToString() + " rise_limit=0.25 runtime=PENDING");
        if (m_RegionalRemaining == 0 && m_PathgraphPending.Count() == 0) { HCRegionalSummary(); }
    }

    // Shutdown alone deletes the partial scene synchronously; the tick path rolls back one prop per admission.
    protected void HCDrainRegionalBatch()
    {
        if (m_RegionalProp) { DeleteProp(m_RegionalProp); }
        foreach (Object partial : m_RegionalBatch) { DeleteProp(partial); }
    }

    protected void HCClearRegionalJob()
    {
        m_RegionalBatch.Clear();
        m_RegionalProp = null;
        m_RegionalPropStep = HCShelterPropStage.PREPARE;
        m_RegionalNearby.Clear();
        m_RegionalCargos.Clear();
        m_RegionalResolve = null;
        m_RegionalBinding = null;
        m_RegionalBounds.HCClear();
        m_RegionalRegion = null;
        m_RegionalRollingBack = false;
        m_RegionalJobEntry = null;
        m_RegionalHouse = null;
        m_RegionalLayout = null;
        m_RegionalScene = null;
    }

    protected void HCRegionalBatchRefused(HCShelterEntry entry)
    {
        // Delete at most one partial prop on each later admission. OnStop
        // alone drains the remaining bounded batch synchronously.
        if (m_RegionalProp || m_RegionalBatch.Count() > 0) { m_RegionalRollingBack = true; return; }
        HCClearRegionalJob();
        // Keep the existing candidate order, rollback and refusal policy.
        if (m_RefusalReason == "observed_regional_prop")
        {
            entry.Attempted = false;
            return;
        }
        m_RegionalCandidateRefusals.Set(m_RefusalReason, m_RegionalCandidateRefusals.Get(m_RefusalReason) + 1);
        int refusedSide = entry.PlacementVariant / HC_REGIONAL_LAYOUTS_PER_SIDE;
        string sideKey = refusedSide.ToString();
        m_RegionalSideRefusals.Set(sideKey, m_RegionalSideRefusals.Get(sideKey) + 1);
        bool retryable = m_RefusalReason == "terrain" || m_RefusalReason == "collision" || m_RefusalReason == "occupied" || m_RefusalReason == "cargo_query" || m_RefusalReason == "ground_support" || m_RefusalReason == "water" || m_RefusalReason == "keepout";
        if (retryable && entry.PlacementVariant + 1 < HC_REGIONAL_LAYOUTS)
        {
            m_RegionalNearbyRetries++;
            entry.PlacementVariant++;
            entry.Attempted = false;
            m_RegionalCursor--;
            return;
        }
        HCRegionalRefuse(entry, m_RefusalReason);
    }

    protected void HCPlaceRegional(HCShelterEntry entry)
    {
        if (!m_RegionalJobEntry)
        {
            m_StepKind = "resolve_prepare";
            m_RegionalJobEntry = entry;
            m_RegionalBinding = new HCInteriorFurnishRow;
            m_RegionalBinding.SlotId = -1;
            m_RegionalBinding.BuildingClass = entry.Scene.BuildingClass;
            m_RegionalBinding.Position = entry.Scene.Position;
            m_RegionalResolve = new HCInteriorResolveCursor;
            m_RefusalReason = "";
            m_BlockingClass = "none";
            m_PropType = "none";
            m_QueryObjects = 0;
            m_QueryCargos = 0;
            m_CollisionCount = 0;
            m_GroundRise = 0;
            m_RefusalPoint = entry.Position;
            m_SoftVegetation = 0;
            m_RingCandidate = -1;
            m_LayoutVariant = entry.PlacementVariant;
            return;
        }
        if (m_RegionalResolve)
        {
            m_StepKind = "resolve";
            if (!m_RegionalResolve.HCStep(m_RegionalBinding))
            {
                if (m_RegionalResolve.HCWaitingForFrame())
                {
                    m_ResolveWaitFrame = GetGame().GetTime();
                    m_StepKind = "idle";
                }
                return;
            }
            m_RegionalHouse = m_RegionalResolve.HCHouse();
            m_RegionalResolve = null;
            if (!m_RegionalHouse)
            {
                // Initial resolve failures were terminal site refusals,
                // never candidate-refusal counters or layout retries.
                HCClearRegionalJob();
                HCRegionalRefuse(entry, "building_unresolved_or_tilted");
            }
            return;
        }
        if (!m_RegionalHouse || m_RegionalHouse.IsPendingDeletion())
        {
            m_RefusalReason = "building_unresolved_or_tilted";
            HCRegionalBatchRefused(entry);
            return;
        }
        if (!m_RegionalLayout)
        {
            m_StepKind = "layout";
            HCShelterRegionalScene scene = entry.Scene;
            Object house = m_RegionalHouse;
            vector regionalClip[2];
            house.ClippingInfo(regionalClip);
            float tolerance = HCShelterCatalog.HCRegionalConfig().BoundsToleranceSquared;
            if (vector.DistanceSq(regionalClip[0], HCInteriorTemplates.AsVector(scene.ClipMin)) > tolerance || vector.DistanceSq(regionalClip[1], HCInteriorTemplates.AsVector(scene.ClipMax)) > tolerance)
            {
                HCClearRegionalJob();
                HCRegionalRefuse(entry, "building_bounds");
                return;
            }
            HCInteriorTemplate layout = new HCInteriorTemplate;
            HCInteriorTemplateRoom yard = new HCInteriorTemplateRoom;
            yard.Id = 1;
            HCInteriorTemplateBox yardBox = new HCInteriorTemplateBox;
            vector yardFirst = HCRegionalSidePoint(scene, HCInteriorTemplates.AsVector(scene.YardMin), entry.PlacementVariant);
            vector yardSecond = HCRegionalSidePoint(scene, HCInteriorTemplates.AsVector(scene.YardMax), entry.PlacementVariant);
            HCRegionalBox(yardBox, yardFirst, yardSecond);
            yard.Min = yardBox.Min;
            yard.Max = yardBox.Max;
            layout.Rooms.Insert(yard);
            vector accessMinimum = HCInteriorTemplates.AsVector(scene.AccessMin);
            vector accessMaximum = HCInteriorTemplates.AsVector(scene.AccessMax);
            Keepout(layout, "walkway", 0, accessMinimum, accessMaximum);
            m_RegionalRegion = new HCPathgraphRefresh;
            m_RegionalJobEntry = entry;
            m_RegionalHouse = house;
            m_RegionalLayout = layout;
            return;
        }
        m_StepKind = "validate_handles";
        // A retained handle can disappear between visits (for example during
        // administrative cleanup); never publish a partially missing scene.
        foreach (Object pendingProp : m_RegionalBatch)
        {
            if (!pendingProp || pendingProp.IsPendingDeletion())
            {
                m_RefusalReason = "create_failed";
                HCRegionalBatchRefused(entry);
                return;
            }
        }
        if (m_RegionalBatch.Count() < 3)
        {
            HCRegionalPropStep(entry);
            return;
        }
        if (!m_RegionalBounds.HCDone())
        {
            m_StepKind = "pathgraph_bounds";
            if (!m_RegionalBounds.HCRunning()) { m_RegionalBounds.HCStart(m_RegionalBatch, m_RegionalRegion); }
            m_Work.HCReset(HC_REGIONAL_BOUNDS_UNITS, HC_REGIONAL_BOUNDS_MS);
            if (m_RegionalBounds.HCRun(m_Work)) { return; }
            if (!m_RegionalBounds.HCDone())
            {
                m_RefusalReason = "create_failed";
                HCRegionalBatchRefused(entry);
            }
            // The stage that finished the walk ends here; the next admission publishes.
            return;
        }
        m_StepKind = "publish";
        HCQueuePathgraph(m_RegionalRegion);
        // All props passed the original exact terrain/bounds/keepout/collision
        // checks. Until this point no incomplete scene is discoverable.
        foreach (Object regionalProp : m_RegionalBatch) { m_Objects.Insert(regionalProp); }
        entry.PlacementAnchor = m_RegionalBatch.Get(0);
        entry.Placed = true;
        int placedSide = entry.PlacementVariant / HC_REGIONAL_LAYOUTS_PER_SIDE;
        Print("[HC Shelters] regional_placed=" + entry.Scene.Id + " variant=" + entry.PlacementVariant.ToString() + " side=" + placedSide.ToString() + " runtime=PENDING");
        HCModuleReadiness.HCUse("Shelters", "shelter_placed");
        m_Placed = m_Placed + 1;
        m_RegionalPlaced++;
        m_RegionalRemaining--;
        HCClearRegionalJob();
        if (m_RegionalRemaining == 0 && m_PathgraphPending.Count() == 0) { HCRegionalSummary(); }
    }

    // Regional equivalent of PlaceProp, in the same predicate/transform order.
    // The two Snap calls are intentional: Spawn previously snapped once before
    // the clipping-bottom correction, then PlaceProp snapped again afterwards.
    // Query results are retained, but only ONE result/corner is visited per unit.
    protected void HCRegionalPropStep(HCShelterEntry entry)
    {
        if (m_RegionalPropStep >= HCShelterPropStage.ORIENT && (!m_RegionalProp || m_RegionalProp.IsPendingDeletion()))
        {
            m_RefusalReason = "create_failed";
            HCRegionalBatchRefused(entry);
            return;
        }
        if (m_RegionalPropStep != HCShelterPropStage.PREPARE && !HCObserverTransitionGate.CanTransition(m_RegionalPoint, HCShelterCatalog.HCRegionalConfig().ObserverDistance))
        {
            m_RefusalReason = "observed_regional_prop";
            HCRegionalBatchRefused(entry);
            return;
        }
        if (m_RegionalPropStep == HCShelterPropStage.PREPARE)
        {
            m_StepKind = "prop_prepare";
            int propSlot = m_RegionalBatch.Count();
            m_PropType = "StaticObj_Furniture_fireplace_grill";
            if (propSlot == 1) { m_PropType = "StaticObj_Misc_Chair_Camp1"; }
            if (propSlot == 2) { m_PropType = "StaticObj_Furniture_PaperBox_01_small_closed"; }
            m_KeepoutCheck = "";
            m_BlockingClass = "none";
            m_QueryObjects = 0;
            m_QueryCargos = 0;
            m_CollisionCount = 0;
            m_GroundRise = 0;
            m_RefusalReason = "";
            vector authoredOffset = HCInteriorTemplates.AsVector(entry.Scene.Slots[propSlot]) + HCRegionalShift(entry.PlacementVariant);
            vector offset = HCRegionalSidePoint(entry.Scene, authoredOffset, entry.PlacementVariant);
            m_RegionalPoint = m_RegionalHouse.ModelToWorld(offset);
            m_RegionalPoint[1] = GetGame().SurfaceY(m_RegionalPoint[0], m_RegionalPoint[2]);
            m_RefusalPoint = m_RegionalPoint;
            if (!HCObserverTransitionGate.CanTransition(m_RegionalPoint, HCShelterCatalog.HCRegionalConfig().ObserverDistance)) { m_RefusalReason = "observed_regional_prop"; }
            else if (!GetGame().ConfigIsExisting("CfgVehicles " + m_PropType) || !GetGame().IsKindOf(m_PropType, "HouseNoDestruct")) { m_RefusalReason = "static_class_missing"; }
            else if (GetGame().SurfaceIsSea(m_RegionalPoint[0], m_RegionalPoint[2]) || GetGame().SurfaceIsPond(m_RegionalPoint[0], m_RegionalPoint[2])) { m_RefusalReason = "water"; }
            if (m_RefusalReason != "") { HCRegionalBatchRefused(entry); return; }
            m_RegionalNearby.Clear();
            m_RegionalCargos.Clear();
            m_RegionalPropStep = HCShelterPropStage.OCCUPIED_QUERY;
            return;
        }
        if (m_RegionalPropStep == HCShelterPropStage.OCCUPIED_QUERY)
        {
            m_StepKind = "occupied_query";
            // Preserve sphere and proxy-cargo semantics. Native exposes no
            // resumable enumeration or cost ceiling for this single call.
            GetGame().GetObjectsAtPosition3D(m_RegionalPoint, 3, m_RegionalNearby, m_RegionalCargos);
            m_QueryObjects = m_RegionalNearby.Count();
            m_QueryCargos = m_RegionalCargos.Count();
            if (m_QueryObjects > 256)
            {
                m_BlockingClass = "query_cap_no_single_blocker";
                m_RefusalReason = "query_cap";
            }
            else if (m_QueryCargos > 0)
            {
                m_BlockingClass = "cargo_owner_unavailable";
                CargoBase cargo = m_RegionalCargos.Get(0);
                if (cargo)
                {
                    EntityAI owner = cargo.GetCargoOwner();
                    if (owner) { m_BlockingClass = owner.GetType(); }
                }
                m_RefusalReason = "cargo_query";
            }
            if (m_RefusalReason != "") { HCRegionalBatchRefused(entry); return; }
            m_RegionalInspect = 0;
            m_RegionalPropStep = HCShelterPropStage.OCCUPIED_FILTER;
            return;
        }
        if (m_RegionalPropStep == HCShelterPropStage.OCCUPIED_FILTER)
        {
            m_StepKind = "occupied_filter";
            if (m_RegionalInspect >= m_RegionalNearby.Count()) { m_RegionalPropStep = HCShelterPropStage.CREATE; return; }
            Object nearby = m_RegionalNearby[m_RegionalInspect];
            m_RegionalInspect++;
            if (!nearby) { return; }
            if (HCSoftVegetation(nearby)) { m_SoftVegetation++; return; }
            vector orphan = nearby.GetPosition();
            float gapX = orphan[0] - m_RegionalPoint[0];
            float gapZ = orphan[2] - m_RegionalPoint[2];
            if (gapX * gapX + gapZ * gapZ < 0.5625)
            {
                m_BlockingClass = nearby.GetType();
                m_RefusalReason = "occupied";
                HCRegionalBatchRefused(entry);
            }
            return;
        }
        if (m_RegionalPropStep == HCShelterPropStage.CREATE)
        {
            m_StepKind = "create";
            // Same flags as HCInteriorTemplatePlacement.Spawn. Separate its
            // native create, orientation and initial snap into three grants.
            int flags = ECE_SETUP | ECE_KEEPHEIGHT | ECE_CREATEPHYSICS | ECE_NOLIFETIME | ECE_NOPERSISTENCY_WORLD;
            m_RegionalProp = GetGame().CreateObjectEx(m_PropType, m_RegionalPoint, flags, RF_IGNORE);
            if (!m_RegionalProp) { m_RefusalReason = "create_failed"; HCRegionalBatchRefused(entry); return; }
            m_RegionalPropStep = HCShelterPropStage.ORIENT;
            return;
        }
        if (m_RegionalPropStep == HCShelterPropStage.ORIENT)
        {
            m_StepKind = "orient";
            vector orientation = m_RegionalHouse.GetOrientation();
            int side = entry.PlacementVariant / HC_REGIONAL_LAYOUTS_PER_SIDE;
            if (side == 1) { orientation[0] = orientation[0] + 180; }
            if (side == 2) { orientation[0] = orientation[0] - 90; }
            if (side == 3) { orientation[0] = orientation[0] + 90; }
            m_RegionalProp.SetOrientation(orientation);
            m_RegionalPropStep = HCShelterPropStage.SPAWN_SNAP;
            return;
        }
        if (m_RegionalPropStep == HCShelterPropStage.SPAWN_SNAP)
        {
            m_StepKind = "spawn_snap";
            HCGroundSnap.Snap(m_RegionalProp);
            m_RegionalPropStep = HCShelterPropStage.BOUNDS;
            return;
        }
        if (m_RegionalPropStep == HCShelterPropStage.BOUNDS)
        {
            m_StepKind = "prop_bounds";
            vector clip[2];
            m_RegionalProp.ClippingInfo(clip);
            m_RegionalMin = clip[0];
            m_RegionalMax = clip[1];
            // Hold the arrays in locals: unowned call results passed straight
            // into BoxValid were released mid-call (access violation, build 161).
            array<float> regionalMinCoordinates = Coordinates(m_RegionalMin);
            array<float> regionalMaxCoordinates = Coordinates(m_RegionalMax);
            bool boundsOk = HCInteriorTemplates.BoxValid(regionalMinCoordinates, regionalMaxCoordinates);
            // Keep simple checks: a compound bounds predicate crashed build 152.
            if (m_RegionalMin[0] < -1.2 || m_RegionalMax[0] > 1.2) { boundsOk = false; }
            if (m_RegionalMin[2] < -1.2 || m_RegionalMax[2] > 1.2) { boundsOk = false; }
            if (m_RegionalMin[1] < -2 || m_RegionalMax[1] > 2) { boundsOk = false; }
            if (m_RegionalMax[1] - m_RegionalMin[1] > 2) { boundsOk = false; }
            if (!boundsOk) { m_RefusalReason = "prop_bounds"; HCRegionalBatchRefused(entry); return; }
            m_RegionalPoint[1] = m_RegionalPoint[1] - m_RegionalMin[1];
            m_RegionalProp.SetPosition(m_RegionalPoint);
            m_RegionalPropStep = HCShelterPropStage.GROUND_SUPPORT;
            return;
        }
        if (m_RegionalPropStep == HCShelterPropStage.GROUND_SUPPORT)
        {
            m_StepKind = "ground_support";
            if (!HCGroundSnap.Snap(m_RegionalProp)) { m_RefusalReason = "ground_support"; HCRegionalBatchRefused(entry); return; }
            m_RegionalPoint = m_RegionalProp.GetPosition();
            m_RefusalPoint = m_RegionalPoint;
            m_RegionalProbe = 0;
            m_RegionalLow = 1000000;
            m_RegionalHigh = -1000000;
            m_RegionalPropStep = HCShelterPropStage.FOOTPRINT;
            return;
        }
        if (m_RegionalPropStep == HCShelterPropStage.FOOTPRINT)
        {
            m_StepKind = "footprint_probe";
            vector sample = m_RegionalMin;
            if (m_RegionalProbe & 1) { sample[0] = m_RegionalMax[0]; }
            if (m_RegionalProbe & 2) { sample[2] = m_RegionalMax[2]; }
            vector world = m_RegionalProp.ModelToWorld(sample);
            if (GetGame().SurfaceIsSea(world[0], world[2]) || GetGame().SurfaceIsPond(world[0], world[2]))
            {
                m_BlockingClass = "water";
                m_RefusalReason = "terrain";
                HCRegionalBatchRefused(entry);
                return;
            }
            float height = GetGame().SurfaceRoadY(world[0], world[2]);
            if (height < m_RegionalLow) { m_RegionalLow = height; }
            if (height > m_RegionalHigh) { m_RegionalHigh = height; }
            m_RegionalProbe++;
            if (m_RegionalProbe < 4) { return; }
            m_GroundRise = m_RegionalHigh - m_RegionalLow;
            if (m_GroundRise > 0.25) { m_RefusalReason = "terrain"; HCRegionalBatchRefused(entry); return; }
            m_RegionalPropStep = HCShelterPropStage.KEEPOUT;
            return;
        }
        if (m_RegionalPropStep == HCShelterPropStage.KEEPOUT)
        {
            m_StepKind = "keepout";
            HCInteriorTemplatePropSlot slot = new HCInteriorTemplatePropSlot;
            slot.Room = 1;
            slot.Position = Coordinates(m_RegionalHouse.WorldToModel(m_RegionalPoint));
            slot.Orientation = Coordinates("0 0 0");
            slot.Bounds = new HCInteriorTemplateBox;
            vector localPoint = HCInteriorTemplates.AsVector(slot.Position);
            int boundsSide = entry.PlacementVariant / HC_REGIONAL_LAYOUTS_PER_SIDE;
            vector firstCorner = localPoint + HCRegionalRotate(m_RegionalMin, boundsSide);
            vector secondCorner = localPoint + HCRegionalRotate(m_RegionalMax, boundsSide);
            HCRegionalBox(slot.Bounds, firstCorner, secondCorner);
            if (!HCInteriorTemplates.SlotClear(m_RegionalLayout, slot))
            {
                m_KeepoutCheck = HCRegionalKeepoutCheck(m_RegionalLayout, slot);
                m_SlotMinimum = HCInteriorTemplates.AsVector(slot.Bounds.Min);
                m_SlotMaximum = HCInteriorTemplates.AsVector(slot.Bounds.Max);
                m_RefusalReason = "keepout";
                HCRegionalBatchRefused(entry);
                return;
            }
            m_RegionalPropStep = HCShelterPropStage.COLLISION_QUERY;
            return;
        }
        if (m_RegionalPropStep == HCShelterPropStage.COLLISION_QUERY)
        {
            m_StepKind = "collision_query";
            vector center = m_RegionalProp.ModelToWorld((m_RegionalMin + m_RegionalMax) * 0.5);
            vector size = m_RegionalMax - m_RegionalMin + Vector(0.6, 0.1, 0.6);
            array<Object> excluded = new array<Object>;
            excluded.Insert(m_RegionalProp);
            m_RegionalNearby.Clear();
            bool collision = GetGame().IsBoxColliding(center, m_RegionalProp.GetOrientation(), size, excluded, m_RegionalNearby);
            m_RegionalInspect = 0;
            m_RegionalPropStep = HCShelterPropStage.COLLISION_FILTER;
            if (!collision) { m_RegionalPropStep = HCShelterPropStage.COMPLETE; }
            return;
        }
        if (m_RegionalPropStep == HCShelterPropStage.COLLISION_FILTER)
        {
            m_StepKind = "collision_filter";
            if (m_RegionalInspect < m_RegionalNearby.Count())
            {
                Object blocker = m_RegionalNearby[m_RegionalInspect];
                m_RegionalInspect++;
                if (!blocker) { return; }
                if (HCSoftVegetation(blocker)) { m_SoftVegetation++; return; }
                m_CollisionCount++;
                if (m_BlockingClass == "none") { m_BlockingClass = blocker.GetType(); }
                return;
            }
            if (m_CollisionCount > 0) { m_RefusalReason = "collision"; HCRegionalBatchRefused(entry); return; }
            m_RegionalPropStep = HCShelterPropStage.COMPLETE;
            return;
        }
        m_StepKind = "prop_complete";
        m_RegionalBatch.Insert(m_RegionalProp);
        m_RegionalProp = null;
        m_RegionalPropStep = HCShelterPropStage.PREPARE;
        m_RegionalNearby.Clear();
        m_RegionalCargos.Clear();
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
        // Capture the transformed geometry before deletion; rebuild after it.
        HCPathgraphRefresh region = new HCPathgraphRefresh;
        region.Include(prop);
        GetGame().ObjectDelete(prop);
        HCQueuePathgraph(region);
    }
}

// Weak module handle: the module owns this registration and clears it on stop.
class HCStartupShelters : HCStartupOwner
{
    HCShelterModule Module;
    override bool HCNeedsWork() { return Module && Module.HCStartupPending(); }
    override void HCSlice() { if (Module) { Module.HCPumpRegional(); } }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCShelterModule);
    }
}
