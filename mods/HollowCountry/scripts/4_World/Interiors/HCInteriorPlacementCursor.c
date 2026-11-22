// W5-PERF-1. <=1 slot per HCTick call (the module runs HCTick calls until its shared HCUnitBudget
// is spent, issue #138: HCLastCost() reports SLOT_UNITS after a creation attempt, else CHEAP_UNITS); cursor advances only after an attempted slot or
// deliberate refusal. Deferred rows retain catalog references (<=1500), never
// re-resolve/claim a completed house. No new inventory or persistence state.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380/389/407
// Count/Set/Insert; EnDebug.c:96 Print; EnConvert.c:30 int.ToString.
// Native placement/time calls are owned by HCInteriorTemplatePlacement and
// World/HCWorkBudget.c, with their installed signatures cited there.
class HCInteriorPlacementCursor
{
    // Work units charged to the module's HCUnitBudget per HCTick call (issue #138). A slot that
    // reaches the creation path (Resolve + spawn + collision checks) is the measured burst source.
    static const int CHEAP_UNITS = 1;
    static const int SLOT_UNITS = 8;
    protected int m_LastCost = 1;
    protected bool m_Yield;
    protected int m_Next;
    protected int m_Slot;
    protected int m_HousePlaced;
    protected int m_DeferredNext;
    protected int m_DeferredSlot;
    protected int m_DeferredRemaining;
    protected bool m_FromDeferred;
    protected ref array<ref HCInteriorFurnishRow> m_Deferred = new array<ref HCInteriorFurnishRow>;
    protected HCInteriorFurnishRow m_Current;
    protected bool m_Complete;
    protected ref HCInteriorResolveCursor m_Resolve;
    protected bool m_Resolved;
    protected ref HCWorkBudget m_Budget = new HCPerfSlices("Interiors");

    // One deadline/count for the outer furnishing loop, never one per slot.
    void HCBeginTick() { m_Budget.HCReset(HCPerfConfig.HCGet().InteriorStepsPerTick, Math.Min(HCPerfConfig.HCGet().SliceMs, 2)); }

    bool HCComplete() { return m_Complete; }
    int HCLastCost() { return m_LastCost; }
    bool HCYield() { return m_Yield; }

    void HCTick(HCInteriorsModule module, HCSettings settings, array<Object> placed)
    {
        int visitStart = TickCount(0);
        m_LastCost = CHEAP_UNITS;
        m_Yield = false;
        if (m_Complete || !HCInteriorTemplates.Loaded()) { return; }
        if (!m_Budget.HCContinue()) { m_Budget.HCDeferred("Interiors", 1); return; }
        array<ref HCInteriorFurnishRow> rows = HCInteriorTemplates.FurnishRows();
        if (!m_Current)
        {
            if (m_Next < rows.Count())
            {
                m_FromDeferred = false;
                m_Current = rows[m_Next];
                m_Next = m_Next + 1;
            }
            else
            {
                if (m_DeferredRemaining > 0)
                {
                    if (m_DeferredNext >= m_Deferred.Count()) { m_DeferredNext = 0; }
                    m_DeferredSlot = m_DeferredNext;
                    m_DeferredNext = m_DeferredNext + 1;
                    m_Current = m_Deferred[m_DeferredSlot];
                    m_FromDeferred = true;
                    // Tombstones avoid ordered-array shifts and swap/remove
                    // starvation when several occupied rows keep deferring.
                    if (!m_Current) { return; }
                }
            }
            m_Resolve = null;
            m_Resolved = false;
            m_Slot = 0;
            m_HousePlaced = 0;
        }
        if (!m_Current)
        {
            m_Complete = true;
            Print("[HC Interiors] templates placement complete props=" + placed.Count().ToString() + "; native acceptance pending");
            return;
        }
        // Recheck proximity on EVERY continuation; a joining player must never
        // see a subsequent furnishing appear in the same house.
        if (HCInteriorTemplatePlacement.PlayersNearRow(m_Current, HCPerfPlayers.HCGet()))
        {
            // A player can hold a partially filtered row for many ticks.
            // Retain the pending resolver on the row binding across this hold;
            // map buildings are static, so no native tile is paid twice.
            m_Resolve = null;
            m_Resolved = false;
            if (m_Slot == 0)
            {
                if (!m_FromDeferred)
                {
                    m_Deferred.Insert(m_Current);
                    m_DeferredRemaining = m_DeferredRemaining + 1;
                }
                m_Current = null;
            }
            m_Budget.HCDeferred("Interiors", rows.Count() - m_Next + m_DeferredRemaining + 1);
            return;
        }
        if (m_FromDeferred)
        {
            m_Deferred.Set(m_DeferredSlot, null);
            m_DeferredRemaining = m_DeferredRemaining - 1;
            m_FromDeferred = false;
        }
        if (HCInteriorRules.PlacementAdmitted())
        {
            m_LastCost = SLOT_UNITS;
            // The outer shared HCWorkBudget admits ONE resolve chunk; keep
            // the candidate index across uninterrupted module ticks.
            if (!m_Resolve)
            {
                m_Resolve = HCInteriorTemplatePlacement.HCResolver(m_Current);
                // Separate row/cursor preparation from native query cost.
                // Build 131's CementWorks query-labelled 33 ms item had only
                // 0.5 ms inside HCStep: its remaining cost was not a query.
                HCInteriorTemplatePlacement.HCRecordResolve(m_Current, 0, "prepare", TickCount(visitStart));
                m_Yield = true;
                return;
            }
            if (!m_Resolved)
            {
                m_Resolved = m_Resolve.HCStep(m_Current);
                // A completed candidate loop gets no prop inspection/creation
                // in the same grant. The resolved house and slot stay pinned.
                m_Yield = true;
                return;
            }
            int beforeCount = placed.Count();
            if (!HCInteriorTemplatePlacement.HCPlaceRowSlice(module, m_Current, settings, placed, m_Slot, 1, m_Slot, m_HousePlaced, m_Resolve))
            {
                m_Current = null;
                return;
            }
            m_HousePlaced = m_HousePlaced + placed.Count() - beforeCount;
        }
        else
        {
            HCInteriorTemplatePlacement.CountRefusal("acceptance_pending", m_Current.Props.Count());
            m_Current = null;
            return;
        }
        m_Resolve = null;
        m_Resolved = false;
        m_Slot = m_Slot + 1;
        if (m_Slot >= m_Current.Props.Count()) { m_Current = null; }
        m_Budget.HCDeferred("Interiors", rows.Count() - m_Next + m_DeferredRemaining);
    }
}

// Weak Object handles become null when the native object is deleted.
class HCInteriorResolvedBuilding
{
    string Key;
    Object BoundObject;
    string Reason;
    bool Complete;
    bool HadHouse;
    bool Retried;
    ref HCInteriorResolveCursor Pending;
}

// One resolve chunk per admitted HCWorkBudget visit. Cold misses first try up to RAY_ATTEMPTS
// geometry rays (one native call per grant, see HCRayBuilding), then the existing sphere.
// Measured-heavy circle fallbacks cover the original 0.75 m circle with four overlapping
// 0.531 m circles, one per tick.
// The sphere is one indivisible native call whose cost is the building's proxy count, not the
// radius (soaks 165-175: 17-29 ms on Land_Tenement_Small, 92-98 ms on Land_House_2B04; sliced 2D
// tiles cost the same). A class in HCRayHeavy therefore never pays the sphere, the tiled path or
// the plain query: when every ray misses, the row is refused this boot with `heavy_ray_miss`
// and the miss is not stored in the binding, so the next boot retries the rays. A class listed in
// HCQuerySliced, or whose sphere/circle call measured >= HEAVY_MS, takes the four-tile path.
// Each circle covers a quadrant's 0.75 x 0.75 m bounding square (half diagonal
// sqrt(2)*0.375). Merge drops overlap and origins outside the original circle;
// exact 3D/class/ambiguity/tilt checks below still decide placement. Native
// Game.c:923 documents circle enumeration; origin membership/binding equivalence
// and the <=16 ms tick target require a native run, especially cold models.
// Query merging and filtering visit <=8 candidates per tick. No house is
// claimed and no cache snapshot is published until all query work completes.
class HCInteriorResolveCursor
{
    static const int CANDIDATES_PER_STEP = 8;
    // Probe order (cheapest and most likely first), see HCRayBuilding: 0 vertical through the
    // origin, 1-2 vertical onto the roof offset by RAY_ROOF_OFFSET_M, 3-4 horizontal at 3 m on X
    // and Z, 5-6 horizontal at 6 m, 7-8 horizontal at 1.5 m.
    static const int RAY_ATTEMPTS = 9;
    // Horizontal rays cross every object on a 2 x RAY_REACH_M line, so the scan must outlast them.
    static const int RAY_HITS_SCANNED = 32;
    static const int RAY_DIAG_HITS = 4;
    static const int HEAVY_CLASS_CAP = 64;
    static const float HEAVY_MS = 10;
    // Horizontal rays start and end this far from the recorded origin, outside any footprint
    // (the repo holds no per-class size outside two apartment prototypes of +-10 and +-20 m).
    static const float RAY_REACH_M = 48;
    static const float RAY_ROOF_OFFSET_M = 3;
    static const float RAY_LOW_HEIGHT_M = 1.5;
    static const float RAY_MID_HEIGHT_M = 3;
    static const float RAY_HIGH_HEIGHT_M = 6;
    protected static int s_SphereFrame = -1;
    // Once per class and boot (bounded by HEAVY_CLASS_CAP, never persisted).
    protected static ref array<string> s_RayMissLogged = new array<string>;
    protected static ref array<string> s_HeavyMissLogged = new array<string>;
    // Hits of the last ray, kept only for the all-miss diagnostic; no extra native call.
    protected ref array<ref RaycastRVResult> m_RayHits;
    // Classes whose single native resolve call measured >= HEAVY_MS this boot (bounded, never persisted).
    protected static ref array<string> s_HeavyClasses = new array<string>;
    protected ref HCInteriorResolveEntry m_Entry;
    protected ref HCInteriorResolvedBuilding m_Binding;
    protected int m_RayAttempts;
    protected bool m_TrySphere;
    protected bool m_Sphere;
    protected bool m_Fresh;
    protected int m_Next;
    protected int m_QueryTile;
    protected int m_QueryNext;
    protected bool m_QueryMerging;
    protected bool m_QueryComplete;
    protected ref array<Object> m_QueryObjects = new array<Object>;
    protected Object m_Found;
    protected string m_Reason = "unresolved";
    protected bool m_Complete;
    protected bool m_FrameWait;
    protected bool m_StartupDeferred;

    bool HCWaitingForFrame() { return m_FrameWait; }
    Object HCHouse() { return m_Found; }
    string HCReason() { return m_Reason; }
    int HCQuerySize() { return m_Entry.QuerySize; }

    bool HCStep(HCInteriorFurnishRow row)
    {
        m_FrameWait = false;
        if (m_Complete) { return true; }
        int mark = TickCount(0);
        vector position = HCInteriorTemplates.AsVector(row.Position);
        if (!m_Binding)
        {
            m_Binding = HCInteriorTemplatePlacement.HCBinding(row);
            if (m_Binding.Complete && m_Binding.HadHouse && !m_Binding.BoundObject && !m_Binding.Retried)
            {
                // One fresh native retry for a deleted static object; never reuse
                // its stale query snapshot. Further deletion is a stable refusal.
                m_Binding.Complete = false;
                m_Binding.Retried = true;
                m_Fresh = true;
                HCModuleReadiness.HCUse("Interiors", "resolve_deleted_retry");
            }
            if (m_Binding.Complete)
            {
                m_Entry = new HCInteriorResolveEntry;
                m_Found = m_Binding.BoundObject;
                m_Reason = m_Binding.Reason;
                if (m_Binding.HadHouse && !m_Found) { m_Reason = "deleted_cached_object"; }
                m_Complete = true;
                m_Binding.Pending = null;
                HCInteriorTemplatePlacement.HCRecordResolve(row, 0, "cache", TickCount(mark));
                return true;
            }
            m_TrySphere = HCInteriorQueryConfig.HCGet().UseSphereLookup;
            if (m_TrySphere && HCQueryTiled(row.BuildingClass))
            {
                m_TrySphere = false;
                HCModuleReadiness.HCUse("Interiors", "resolve_tiled_routed");
            }
        }
        if (!m_Entry)
        {
            // Reuse only the same native query shape at this exact centre;
            // sphere and circle snapshots have different candidate-cap semantics.
            if (!m_Fresh) { m_Entry = HCInteriorTemplatePlacement.HCFindResolveObjects(position, m_TrySphere); }
            if (m_Entry) { m_QueryComplete = true; m_Sphere = m_Entry.Sphere; }
            else
            {
                if (m_RayAttempts < RAY_ATTEMPTS)
                {
                    if (!HCNativeQueryAdmitted(row, mark)) { return false; }
                    int rayIndex = m_RayAttempts;
                    m_RayAttempts = m_RayAttempts + 1;
                    m_RayHits = null;
                    Object rayHouse = HCRayBuilding(position, row.BuildingClass, rayIndex);
                    int raySize = 0;
                    string rayPhase = "ray";
                    if (rayIndex > 0) { rayPhase = "ray" + rayIndex.ToString(); }
                    if (rayHouse)
                    {
                        // Private single-hit entry: never publish it as a complete
                        // sphere/circle snapshot. The normal filter binds the row.
                        m_Entry = new HCInteriorResolveEntry;
                        m_Entry.Position = position;
                        m_Entry.Objects.Insert(rayHouse);
                        m_Entry.QuerySize = 1;
                        m_QueryComplete = true;
                        raySize = 1;
                        HCModuleReadiness.HCUse("Interiors", "resolve_ray_hit");
                        if (rayIndex > 0) { HCModuleReadiness.HCUse("Interiors", "resolve_ray_hit_alt"); }
                        m_RayHits = null;
                    }
                    else
                    {
                        if (m_RayAttempts >= RAY_ATTEMPTS)
                        {
                            HCModuleReadiness.HCUse("Interiors", "resolve_ray_fallback");
                            HCRayMissDiagnostic(position, row.BuildingClass);
                            m_RayHits = null;
                        }
                    }
                    HCInteriorTemplatePlacement.HCRecordResolve(row, raySize, rayPhase, TickCount(mark));
                    // A miss leaves the next probe, the sphere and the tiled paths intact,
                    // each starting on its own grant; never two native queries here.
                    return false;
                }
                // Measured-heavy class: the building's proxy count makes any query that
                // includes it cost 17-98 ms, so no sphere, tile or plain query is ever made.
                if (HCRayHeavy(row.BuildingClass)) { return HCRefuseHeavy(row, mark); }
                if (m_TrySphere)
                {
                    if (!HCNativeQueryAdmitted(row, mark)) { return false; }
                    m_Entry = new HCInteriorResolveEntry;
                    m_Entry.Position = position;
                    m_Entry.Sphere = true;
                    // Installed Game.c:930, sphere encloses every admissible
                    // origin (<=0.75 m in the unchanged exact filter).
                    int sphereMark = TickCount(0);
                    GetGame().GetObjectsAtPosition3D(position, 0.75, m_Entry.Objects, null);
                    HCNoteQueryCost(row.BuildingClass, TickCount(sphereMark));
                    m_Entry.QuerySize = m_Entry.Objects.Count();
                    if (m_Entry.QuerySize > 256) { m_Entry.Objects.Clear(); }
                    HCInteriorTemplatePlacement.HCStoreResolveObjects(m_Entry);
                    m_QueryComplete = true;
                    m_Sphere = true;
                    HCInteriorTemplatePlacement.HCRecordResolve(row, m_Entry.QuerySize, "query3d", TickCount(mark));
                    return false;
                }
                if (!HCQueryTiled(row.BuildingClass))
                {
                    int plainMark = TickCount(0);
                    m_Entry = HCInteriorTemplatePlacement.HCResolveObjects(position, m_Fresh);
                    HCNoteQueryCost(row.BuildingClass, TickCount(plainMark));
                    m_QueryComplete = true;
                    HCInteriorTemplatePlacement.HCRecordResolve(row, m_Entry.QuerySize, "query", TickCount(mark));
                    return false;
                }
                m_Entry = new HCInteriorResolveEntry;
                m_Entry.Position = position;
            }
        }
        if (!m_QueryComplete)
        {
            string phase = "query" + m_QueryTile.ToString();
            if (m_QueryMerging) { phase = "merge"; }
            HCQueryStep(position);
            int querySize = m_Entry.QuerySize;
            if (phase != "merge") { querySize = m_QueryObjects.Count(); }
            int phaseTicks = TickCount(mark);
            // Evidence only: a slow tile cannot be split further, so count it for the soak.
            if (phaseTicks >= HCHeavyTicks()) { HCModuleReadiness.HCUse("Interiors", "resolve_tile_slow"); }
            HCInteriorTemplatePlacement.HCRecordResolve(row, querySize, phase, phaseTicks);
            return false;
        }
        bool done = HCFilter(position, row.BuildingClass);
        HCInteriorTemplatePlacement.HCRecordResolve(row, m_Entry.QuerySize, "filter", TickCount(mark));
        if (done && m_Sphere && (m_Reason == "unresolved" || m_Reason == "query_cap"))
        {
            // Fallback starts on a separate grant; never hide a second native
            // query in this filter's timing/count. Keep exact class/tilt rules.
            m_TrySphere = false;
            m_Sphere = false;
            m_Fresh = true;
            m_Entry = null;
            m_Next = 0;
            m_QueryComplete = false;
            m_Complete = false;
            m_Reason = "unresolved";
            HCModuleReadiness.HCUse("Interiors", "resolve_query_fallback");
            return false;
        }
        if (done)
        {
            m_Binding.BoundObject = m_Found;
            m_Binding.HadHouse = m_Found != null;
            m_Binding.Reason = m_Reason;
            m_Binding.Complete = true;
            m_Binding.Pending = null;
        }
        return done;
    }

    // Shared cold-query admission for ray and sphere. GetTime is the existing
    // frame token; no caller can perform both native calls in that frame.
    protected bool HCNativeQueryAdmitted(HCInteriorFurnishRow row, int mark)
    {
        if (!HCStartupPump.HCInteriorQueriesReady())
        {
            m_FrameWait = true;
            if (!m_StartupDeferred)
            {
                m_StartupDeferred = true;
                HCModuleReadiness.HCUse("Interiors", "resolve_startup_deferred");
            }
            HCInteriorTemplatePlacement.HCRecordResolve(row, 0, "startup_wait", TickCount(mark));
            return false;
        }
        int queryFrame = GetGame().GetTime();
        if (s_SphereFrame == queryFrame) { m_FrameWait = true; return false; }
        s_SphereFrame = queryFrame;
        return true;
    }

    // Measured-heavy classes, committed list (no list type exists in the settings registry).
    // Evidence: soaks 165-175, window 2, `[HC Step] owner=Interiors ... heaviest=<class>#q2:query3d`,
    // one GetObjectsAtPosition3D(position, 0.75) costing 16.9, 20.8, 25.05 and 29.1 ms on
    // Land_Tenement_Small and 92-98 ms on Land_House_2B04 (soaks 170-172). No repo data shows that
    // Land_Tenement_Big or the other Land_House_2B variants share those models, so they stay unlisted
    // until a soak measures them. One comparison per statement (a continued "||" fails to compile).
    protected static bool HCRayHeavy(string buildingClass)
    {
        if (buildingClass == "Land_Tenement_Small") { return true; }
        return buildingClass == "Land_House_2B04";
    }

    // All rays missed for a heavy class: refuse this row for this boot. The binding is NOT marked
    // complete, so nothing is cached and the next boot retries the rays. No native call here.
    protected bool HCRefuseHeavy(HCInteriorFurnishRow row, int mark)
    {
        m_Entry = new HCInteriorResolveEntry;
        m_Found = null;
        m_Reason = "heavy_ray_miss";
        m_Complete = true;
        if (m_Binding) { m_Binding.Pending = null; }
        HCModuleReadiness.HCUse("Interiors", "resolve_heavy_ray_miss");
        if (s_HeavyMissLogged.Find(row.BuildingClass) < 0 && s_HeavyMissLogged.Count() < HEAVY_CLASS_CAP)
        {
            s_HeavyMissLogged.Insert(row.BuildingClass);
            int rayCount = RAY_ATTEMPTS;
            Print("[HC Interiors] resolve heavy_ray_miss class=" + row.BuildingClass + " rays=" + rayCount.ToString() + " runtime=PENDING");
        }
        HCInteriorTemplatePlacement.HCRecordResolve(row, 0, "heavy_ray_miss", TickCount(mark));
        return true;
    }

    // First RAY_DIAG_HITS entries of the last ray's result array, already held: hit type, parent type
    // and distance of the contact from the row position. At most one line per class and boot.
    // Installed 3_Game/Global/DayZPhysics.c:96-107 RaycastRVResult obj/parent/pos;
    // 1_Core/proto/EnConvert.c:196 vector.Distance.
    protected void HCRayMissDiagnostic(vector position, string buildingClass)
    {
        if (s_RayMissLogged.Find(buildingClass) >= 0 || s_RayMissLogged.Count() >= HEAVY_CLASS_CAP) { return; }
        s_RayMissLogged.Insert(buildingClass);
        int hitTotal = 0;
        if (m_RayHits) { hitTotal = m_RayHits.Count(); }
        int rayCount = RAY_ATTEMPTS;
        string line = "[HC Interiors] ray_miss class=" + buildingClass + " rays=" + rayCount.ToString() + " last_ray_hits=" + hitTotal.ToString();
        int diagStop = Math.Min(hitTotal, RAY_DIAG_HITS);
        int diagIndex = 0;
        while (diagIndex < diagStop)
        {
            RaycastRVResult diagHit = m_RayHits[diagIndex];
            string hitType = "none";
            string parentType = "none";
            float hitDistance = -1;
            if (diagHit)
            {
                if (diagHit.obj) { hitType = diagHit.obj.GetType(); }
                if (diagHit.parent) { parentType = diagHit.parent.GetType(); }
                hitDistance = vector.Distance(position, diagHit.pos);
            }
            line = line + " h" + diagIndex.ToString() + "=" + hitType + "/" + parentType + "/" + hitDistance.ToString() + "m";
            diagIndex = diagIndex + 1;
        }
        Print(line + " runtime=PENDING");
        m_RayHits = null;
    }

    // Installed scripts-1.30.164289: 3_Game/Global/DayZPhysics.c:49-92
    // RaycastRVParams; :98-107 hit obj/parent; :208 RaycastRVProxy reports those handles,
    // including landscape proxies. 1_Core/proto/EnDebug.c:140-148 CollisionFlags; the vanilla
    // callers 4_World/Classes/Hologram.c:1439 and UserActionsComponent/ActionTargets.c:249 use
    // ALLOBJECTS ("first contact for each object") to get several results from one ray.
    // Each probe is ONE RaycastRVProxy (the caller holds the native grant). Order, cheapest first:
    //   0    vertical 66 m segment through the recorded origin (zero radius, NEARESTCONTACT as before);
    //   1,2  the same vertical segment offset by RAY_ROOF_OFFSET_M on (+X,+Z) and (-X,-Z), for an
    //        open stairwell, courtyard or roof opening under the centre;
    //   3,4  horizontal segments along X then Z at RAY_MID_HEIGHT_M;
    //   5,6  the same at RAY_HIGH_HEIGHT_M;
    //   7,8  the same at RAY_LOW_HEIGHT_M (door and window openings can pass this height).
    // Horizontal segments run from -RAY_REACH_M to +RAY_REACH_M, so they begin and end outside the
    // footprint and cross an outer face (the former +-20 m probes could start inside a long building).
    // They use ALLOBJECTS because NEARESTCONTACT could return only a neighbour or tree nearest to the
    // start. Every hit (bounded by RAY_HITS_SCANNED) is checked, since a proxy hierarchy can return
    // several results; the unchanged exact class/0.75 m/tilt filter below decides, only a unique
    // match binds, so a wrong or ambiguous hit never places anything. This bounds requests, not
    // native latency: ray cost needs retail soak evidence.
    protected Object HCRayBuilding(vector position, string buildingClass, int probe)
    {
        vector rayStart = position + "0 64 0";
        vector rayEnd = position + "0 -2 0";
        bool horizontal = probe >= 3;
        if (probe == 1 || probe == 2)
        {
            float roofOffset = RAY_ROOF_OFFSET_M;
            if (probe == 2) { roofOffset = -RAY_ROOF_OFFSET_M; }
            rayStart = position + Vector(roofOffset, 64, roofOffset);
            rayEnd = position + Vector(roofOffset, -2, roofOffset);
        }
        if (horizontal)
        {
            float rayHeight = RAY_MID_HEIGHT_M;
            if (probe == 5 || probe == 6) { rayHeight = RAY_HIGH_HEIGHT_M; }
            if (probe == 7 || probe == 8) { rayHeight = RAY_LOW_HEIGHT_M; }
            if (probe % 2 == 1)
            {
                rayStart = position + Vector(-RAY_REACH_M, rayHeight, 0);
                rayEnd = position + Vector(RAY_REACH_M, rayHeight, 0);
            }
            else
            {
                rayStart = position + Vector(0, rayHeight, -RAY_REACH_M);
                rayEnd = position + Vector(0, rayHeight, RAY_REACH_M);
            }
        }
        RaycastRVParams ray = new RaycastRVParams(rayStart, rayEnd);
        ray.type = ObjIntersectGeom;
        if (horizontal) { ray.flags = CollisionFlags.ALLOBJECTS; }
        array<ref RaycastRVResult> hits = new array<ref RaycastRVResult>;
        bool rayHit = DayZPhysics.RaycastRVProxy(ray, hits);
        m_RayHits = hits;
        if (!rayHit) { return null; }
        Object matched;
        int hitStop = Math.Min(hits.Count(), RAY_HITS_SCANNED);
        int hitIndex = 0;
        while (hitIndex < hitStop)
        {
            RaycastRVResult hit = hits[hitIndex];
            hitIndex = hitIndex + 1;
            if (!hit) { continue; }
            Object candidate = hit.obj;
            if (!HCRayObjectMatches(candidate, position, buildingClass)) { candidate = hit.parent; }
            if (!HCRayObjectMatches(candidate, position, buildingClass)) { continue; }
            if (matched && matched != candidate) { return null; }
            matched = candidate;
        }
        return matched;
    }

    // Installed 3_Game/Entities/Object.c:287/305 position/orientation;
    // 1_Core/proto/EnConvert.c:210 DistanceSq. Same exact filter and tilt rules.
    protected bool HCRayObjectMatches(Object candidate, vector position, string buildingClass)
    {
        if (!candidate) { return false; }
        if (candidate.GetType() != buildingClass) { return false; }
        if (vector.DistanceSq(position, candidate.GetPosition()) > 0.5625) { return false; }
        vector orientation = candidate.GetOrientation();
        if (!HCInteriorRules.SaneVector(orientation, 360)) { return false; }
        return HCInteriorRules.TiltAcceptable(orientation, HCInteriorRules.MAX_HOUSE_TILT_DEGREES);
    }

    // Raw TickCount units for HEAVY_MS, from the shared calibrated clock rate.
    protected static float HCHeavyTicks()
    {
        return HCWorkBudget.HCTicksPerMs() * HEAVY_MS;
    }

    // A class whose one native resolve call took >= HEAVY_MS is remembered for the boot; its
    // remaining rows are routed to the sliced path. The first occurrence still pays once.
    protected static void HCNoteQueryCost(string buildingClass, int ticks)
    {
        if (ticks < HCHeavyTicks()) { return; }
        HCModuleReadiness.HCUse("Interiors", "resolve_query_heavy");
        if (s_HeavyClasses.Find(buildingClass) >= 0 || s_HeavyClasses.Count() >= HEAVY_CLASS_CAP) { return; }
        s_HeavyClasses.Insert(buildingClass);
        float heavyMs = ticks / HCWorkBudget.HCTicksPerMs();
        Print("[HC Interiors] heavy resolve query routed to sliced path class=" + buildingClass + " ms=" + heavyMs.ToString());
    }

    // Measured-heavy this boot, or in the build 131 list below.
    protected bool HCQueryTiled(string buildingClass)
    {
        if (HCQuerySliced(buildingClass)) { return true; }
        return s_HeavyClasses.Find(buildingClass) >= 0;
    }

    // Build 131's five heaviest query-labelled classes. Avoid multiplying
    // startup latency for the remaining catalog's already-cheap queries.
    protected bool HCQuerySliced(string buildingClass)
    {
        // One comparison per statement: a continued "||" line fails to compile.
        if (buildingClass == "Land_CementWorks_ExpeditionA") { return true; }
        if (buildingClass == "Land_Tenement_Small") { return true; }
        if (buildingClass == "Land_Mil_Barracks3") { return true; }
        if (buildingClass == "Land_Mil_Barracks4") { return true; }
        return buildingClass == "Land_House_2B01";
    }

    protected void HCQueryStep(vector position)
    {
        if (!m_QueryMerging)
        {
            int column = m_QueryTile % 2;
            int line = m_QueryTile / 2;
            vector centre = position + Vector(column * 0.75 - 0.375, 0, line * 0.75 - 0.375);
            // Native scripts-1.30.164289: 3_Game/Global/Game.c:923.
            // Never enumerate proxy cargo. Rounded outward to cover seams.
            GetGame().GetObjectsAtPosition(centre, 0.531, m_QueryObjects, null);
            m_QueryNext = 0;
            m_QueryMerging = true;
            return;
        }
        int stop = Math.Min(m_QueryNext + CANDIDATES_PER_STEP, m_QueryObjects.Count());
        while (m_QueryNext < stop)
        {
            Object candidate = m_QueryObjects[m_QueryNext];
            m_QueryNext = m_QueryNext + 1;
            if (!candidate) { continue; }
            vector origin = candidate.GetPosition();
            float dx = origin[0] - position[0];
            float dz = origin[2] - position[2];
            // Each origin belongs to exactly one quadrant, including seams.
            // That quadrant's query circle covers its entire bounding square.
            // This removes overlapping results without a nested object scan.
            int ownerTile = 0;
            if (dx >= 0) { ownerTile = 1; }
            if (dz >= 0) { ownerTile = ownerTile + 2; }
            // Retain nonmatching classes for the existing 256-object refusal.
            if (ownerTile != m_QueryTile || dx * dx + dz * dz > 0.5625) { continue; }
            m_Entry.QuerySize = m_Entry.QuerySize + 1;
            if (m_Entry.QuerySize > 256)
            {
                m_Entry.Objects.Clear();
                HCQueryFinish();
                return;
            }
            m_Entry.Objects.Insert(candidate);
        }
        if (m_QueryNext < m_QueryObjects.Count()) { return; }
        m_QueryObjects.Clear();
        m_QueryMerging = false;
        m_QueryTile = m_QueryTile + 1;
        if (m_QueryTile == 4) { HCQueryFinish(); }
    }

    protected void HCQueryFinish()
    {
        m_QueryObjects.Clear();
        m_QueryComplete = true;
        HCInteriorTemplatePlacement.HCStoreResolveObjects(m_Entry);
    }

    protected bool HCFilter(vector position, string buildingClass)
    {
        if (m_Entry.QuerySize > 256)
        {
            m_Reason = "query_cap";
            m_Complete = true;
            return true;
        }
        int stop = Math.Min(m_Next + CANDIDATES_PER_STEP, m_Entry.Objects.Count());
        while (m_Next < stop)
        {
            Object candidate = m_Entry.Objects[m_Next];
            m_Next = m_Next + 1;
            if (!candidate || candidate.GetType() != buildingClass || vector.DistanceSq(position, candidate.GetPosition()) > 0.5625) { continue; }
            if (m_Found)
            {
                m_Found = null;
                m_Reason = "ambiguous";
                m_Complete = true;
                return true;
            }
            m_Found = candidate;
        }
        if (m_Next < m_Entry.Objects.Count()) { return false; }
        m_Complete = true;
        if (!m_Found) { return true; }
        vector orientation = m_Found.GetOrientation();
        if (!HCInteriorRules.SaneVector(orientation, 360) || !HCInteriorRules.TiltAcceptable(orientation, HCInteriorRules.MAX_HOUSE_TILT_DEGREES))
        {
            m_Found = null;
            m_Reason = "tilted";
            return true;
        }
        m_Reason = "";
        return true;
    }
}

// Only pack loading and house recovery delay cold ray/sphere queries. Shelters may
// itself be a pump owner; waiting for the whole pump would deadlock its resolver.
modded class HCStartupPump
{
    static bool HCInteriorQueriesReady()
    {
        // Fixed shared registration cap is 32. Consult actual work even after
        // an owner's pump deadline: normal-tick fallback may still be loading.
        foreach (HCStartupOwner queryOwner : s_Owners)
        {
            bool relevant = queryOwner.Name == "interiors_pack" || queryOwner.Name == "search_house_recovery" || queryOwner.Name == "search_house_recovery_pilot";
            if (relevant && queryOwner.HCNeedsWork()) { return false; }
        }
        // Template completion publishes after the inner placement tick. Do not
        // slip a cold query into the gap before recovery registers its owner.
        HCSearchHouses houses = HCSearchBinding.Houses();
        if (houses && houses.HCJournalWaiting()) { return false; }
        return true;
    }
}
