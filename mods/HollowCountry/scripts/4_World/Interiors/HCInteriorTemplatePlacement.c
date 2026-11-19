// W5-PERF: production lifecycle uses HCInteriorPlacementCursor: <=1 prop attempt per
// cursor step, <=2 tiny spatial queries; the module's HCUnitBudget bounds steps per tick.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:930 GetObjectsAtPosition3D;
// Object.c:287/305/311/873 position/orientation/set/model transform;
// 1_Core/proto/EnScript.c:380/394/407 Count/Find/Insert;
// EnConvert.c:30/210 ToString/DistanceSq; EnDebug.c:96 Print;
// EnMath.c:553 Min. Shared time/player cache: World/HCWorkBudget.c.
// Native 1.30.164289: 3_Game/Global/Game.c:703 CreateObjectEx;
// 3_Game/CE/CentralEconomy.c:30-33 NOLIFETIME/NOPERSISTENCY_WORLD flags.
// One deterministic startup pass, advanced in bounded batches by module ticks.
// Issue #138 round 2: every native step of a creation attempt is sub-timed with EnSystem.c:106
// TickCount into the shared Core/HCStepTimer (owner=Interiors, one '[HC Step]' line per window).
// Placement decisions, flags, order and results are unchanged; only measurements are added.
class HCInteriorTemplatePlacement
{
    static const int STEP_RESOLVE = 0;   // Resolve: Game.c:930 GetObjectsAtPosition3D at the house
    static const int STEP_LOOKUP = 1;    // template/slot lookup, Object.c:873 ModelToWorld, :305 GetOrientation
    static const int STEP_INSPECT = 2;   // Available -> InspectProp: a second GetObjectsAtPosition3D
    static const int STEP_CREATE = 3;    // Game.c:703 CreateObjectEx (CREATEPHYSICS|UPDATEPATHGRAPH)
    static const int STEP_ORIENT = 4;    // Object.c:311 SetOrientation
    static const int STEP_LOG = 5;       // LogPropBox: Object.c:358 ClippingInfo + Print (<=25 types)
    static const int STEP_SCHEDULE = 6;  // CallLater queueing of the deferred pathgraph update
    static const int STEP_MAINT = 7;     // module search maintenance phases
    protected static ref HCStepTimer s_Steps;
    protected static string s_LastType;
    // Objects the last house resolve query returned; the step line shows it as heaviest=<type>#q<n>.
    protected static int s_LastQuery;
    protected static bool s_Started;
    protected static int s_Placed;
    protected static int s_Capped;
    protected static int s_DeferredNext;
    protected static ref array<ref HCInteriorFurnishRow> s_Deferred = new array<ref HCInteriorFurnishRow>;
    protected static string s_ResolveReason;
    protected static ref array<Object> s_Houses = new array<Object>;
    protected static ref map<string, int> s_Refused = new map<string, int>;
    protected static ref array<string> s_BoxLogged = new array<string>;
    // Exact query centres only: nearby rows can have different ambiguity/refusal results.
    // FIFO bounds retained snapshots and lookup work; never retain >256 native objects per entry.
    static const int RESOLVE_CACHE_LIMIT = 128;
    protected static ref array<ref HCInteriorResolveEntry> s_ResolveCache = new array<ref HCInteriorResolveEntry>;
    protected static int s_ResolveNext;

    static void ResetPlacement()
    {
        s_Started = false;
        s_Placed = 0;
        s_Capped = 0;
        s_DeferredNext = 0;
        s_Deferred.Clear();
        s_ResolveReason = "";
        s_Houses.Clear();
        s_Refused.Clear();
        s_BoxLogged.Clear();
        s_LastType = "";
        s_LastQuery = 0;
        s_ResolveCache.Clear();
        s_ResolveNext = 0;
    }

    // Shared sub-timer of the Interiors module tick; the step order matches the STEP_* indices.
    static HCStepTimer HCSteps()
    {
        if (s_Steps) { return s_Steps; }
        s_Steps = new HCStepTimer("Interiors");
        s_Steps.HCDefine("resolve");
        s_Steps.HCDefine("lookup");
        s_Steps.HCDefine("inspect");
        s_Steps.HCDefine("create");
        s_Steps.HCDefine("orient");
        s_Steps.HCDefine("log");
        s_Steps.HCDefine("schedule");
        s_Steps.HCDefine("maint");
        return s_Steps;
    }

    // House class, plus ':' and the prop type once a slot reached the creation path.
    static string HCLastType() { return s_LastType; }

    // The deferred pathgraph update, timed: the same Game.c:1293 UpdatePathgraphRegionByObject call
    // the CallLater formerly targeted directly (it null-checks and rebuilds the ClippingInfo-radius
    // region through Game.c:1206 UpdatePathgraphRegion). Runs outside the module timer.
    static void HCTimedPathgraph(Object placedObject)
    {
        if (!GetGame()) { return; }
        int mark = TickCount(0);
        GetGame().UpdatePathgraphRegionByObject(placedObject);
        if (placedObject) { HCSteps().HCDeferred(TickCount(mark)); }
    }

    static void LogPropBox(Object prop)
    {
        if (!prop)
        {
            return;
        }
        string propType = prop.GetType();
        if (s_BoxLogged.Find(propType) >= 0 || s_BoxLogged.Count() >= 25)
        {
            return;
        }
        s_BoxLogged.Insert(propType);
        // Installed 1.30.164289: 3_Game/Entities/Object.c:358 (model clipping min/max).
        // 1_Core/proto/EnConvert.c:138: false emits space-separated vector components.
        // Observe only the already-created furnishing prop; no measurement spawns.
        vector propBox[2];
        prop.ClippingInfo(propBox);
        vector propMin = propBox[0];
        vector propMax = propBox[1];
        if (!HCInteriorRules.SaneVector(propMin, 100) || !HCInteriorRules.SaneVector(propMax, 100) || propMin[0] >= propMax[0] || propMin[1] >= propMax[1] || propMin[2] >= propMax[2])
        {
            return;
        }
        Print("[HC Interiors] prop box type=" + propType + " min=<" + propMin.ToString(false) + "> max=<" + propMax.ToString(false) + ">");
    }

    static void CountRefusal(string reason, int count)

    {
        s_Refused.Set(reason, s_Refused.Get(reason) + count);
    }

    // Native 1_Core/proto/EnScript.c:380/385/389/407 Count/Clear/Set/Insert.
    // Reuse the unmodified 0.75 m native query for all slices/templates at this building centre.
    // Filtering still runs on live object state in Resolve; cached failure snapshots retain #q.
    static HCInteriorResolveEntry HCResolveObjects(vector position)
    {
        foreach (HCInteriorResolveEntry cached : s_ResolveCache)
        {
            if (cached.Position == position)
            {
                return cached;
            }
        }
        HCInteriorResolveEntry entry = new HCInteriorResolveEntry;
        entry.Position = position;
        array<CargoBase> cargos = new array<CargoBase>();
        GetGame().GetObjectsAtPosition3D(position, 0.75, entry.Objects, cargos);
        entry.QuerySize = entry.Objects.Count();
        if (entry.QuerySize > 256)
        {
            entry.Objects.Clear();
        }
        if (s_ResolveCache.Count() < RESOLVE_CACHE_LIMIT)
        {
            s_ResolveCache.Insert(entry);
        }
        else
        {
            s_ResolveCache.Set(s_ResolveNext, entry);
            s_ResolveNext = (s_ResolveNext + 1) % RESOLVE_CACHE_LIMIT;
        }
        return entry;
    }

    static Object Resolve(HCInteriorFurnishRow row)

    {
        s_ResolveReason = "unresolved";
        vector position = HCInteriorTemplates.AsVector(row.Position);
        HCInteriorResolveEntry entry = HCResolveObjects(position);
        s_LastQuery = entry.QuerySize;
        if (s_LastQuery > 256)

        {
            s_ResolveReason = "query_cap";
            return null;
        }
        Object found;
        foreach (Object object : entry.Objects)

        {
            if (!object || object.GetType() != row.BuildingClass || vector.DistanceSq(position, object.GetPosition()) > 0.5625)

            {
                continue;
            }
            if (found)

            {
                s_ResolveReason = "ambiguous";
                return null;
            }
            found = object;
        }
        if (!found)

        {
            return null;
        }
        vector orientation = found.GetOrientation();
        if (!HCInteriorRules.SaneVector(orientation, 360) || !HCInteriorRules.TiltAcceptable(orientation, HCInteriorRules.MAX_HOUSE_TILT_DEGREES))

        {
            s_ResolveReason = "tilted";
            return null;
        }
        s_ResolveReason = "";
        return found;
    }

    static bool Available(HCInteriorsModule module, vector position, vector orientation, string type)

    {
        Object reusable;
        // Same orphan refusal as pilot placement. Never adopt a foreign prop or
        // duplicate a possible persistent object at the intended slot.
        return module.InspectProp(position, orientation, type, reusable) == 0;
    }

    static Object Spawn(string type, vector position, vector orientation)

    {
        int flags = ECE_SETUP | ECE_KEEPHEIGHT | ECE_CREATEPHYSICS | ECE_UPDATEPATHGRAPH | ECE_NOLIFETIME | ECE_NOPERSISTENCY_WORLD;
        HCStepTimer steps = HCSteps();
        int mark = TickCount(0);
        Object object = GetGame().CreateObjectEx(type, position, flags, RF_IGNORE);
        steps.HCAdd(STEP_CREATE, TickCount(mark));
        if (object)

        {
            mark = TickCount(0);
            object.SetOrientation(orientation);
            steps.HCAdd(STEP_ORIENT, TickCount(mark));
        }
        return object;
    }

    static void Schedule(array<Object> objects)

    {
        // Same inspected native pathgraph call as HCInteriorPathgraph; keep the
        // large pack's diagnostics to its single aggregate placement summary.
        int count = Math.Min(objects.Count(), 5);
        int index = 0;
        while (index < count)

        {
            Object placedObject = objects[index];
            if (placedObject)

            {
                GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCInteriorTemplatePlacement.HCTimedPathgraph, 100, false, placedObject);
            }
            index = index + 1;
        }
    }

    static void PlaceRow(HCInteriorsModule module, HCInteriorFurnishRow row, HCSettings settings, array<Object> placed)
    {
        HCPlaceRowSlice(module, row, settings, placed, 0, 5, 0, 0);
    }

    static bool HCPlaceRowSlice(HCInteriorsModule module, HCInteriorFurnishRow row, HCSettings settings, array<Object> placed, int firstSlot, int slotCount, int resume, int placedBefore)

    {
        int limit = Math.Min(settings.HCSearchCap("MaxFurnishedProps", settings.MaxFurnishedProps), 1500);
        int houseLimit = Math.Min(settings.HCSearchCap("MaxPropsPerInterior", settings.MaxPropsPerInterior), 5);
        s_LastType = row.BuildingClass;
        if (placed.Count() >= limit)

        {
            s_Capped = s_Capped + row.Props.Count();
            return false;
        }
        HCStepTimer steps = HCSteps();
        int mark = TickCount(0);
        Object house = Resolve(row);
        steps.HCAdd(STEP_RESOLVE, TickCount(mark));
        s_LastType = row.BuildingClass + "#q" + s_LastQuery.ToString();
        if (!house)

        {
            CountRefusal(s_ResolveReason, row.Props.Count());
            return false;
        }
        if (resume == 0 && s_Houses.Find(house) >= 0)

        {
            CountRefusal("duplicate_house", row.Props.Count());
            return false;
        }
        if (resume == 0) { s_Houses.Insert(house); }
        mark = TickCount(0);
        HCInteriorTemplate templateRow = HCInteriorTemplates.Template(row.BuildingClass);
        steps.HCAdd(STEP_LOOKUP, TickCount(mark));
        if (!templateRow)

        {
            CountRefusal("binding", row.Props.Count());
            return false;
        }
        if (row.Props.Count() > houseLimit)
        {
            // Namespaced keys share the existing once-only diagnostic cache.
            string capKey = "cap_" + row.BuildingClass;
            if (s_BoxLogged.Find(capKey) < 0)
            {
                Print("[HC Interiors] furnishing capped class=" + row.BuildingClass + " limit=" + houseLimit.ToString());
                s_BoxLogged.Insert(capKey);
            }
        }
        int houseCount = placedBefore;
        int slotIndex = -1;
        array<Object> created = new array<Object>();
        foreach (int slotId : row.Props)

        {
            slotIndex = slotIndex + 1;
            if (slotIndex < firstSlot || slotIndex >= firstSlot + slotCount) { continue; }
            if (placed.Count() >= limit || houseCount >= houseLimit)

            {
                s_Capped = s_Capped + 1;
                continue;
            }
            mark = TickCount(0);
            HCInteriorTemplatePropSlot slot = HCInteriorTemplates.Prop(templateRow, slotId);
            if (!slot || slot.History.Find(row.History) < 0 || !HCInteriorTemplates.SlotClear(templateRow, slot))

            {
                steps.HCAdd(STEP_LOOKUP, TickCount(mark));
                CountRefusal("clearance", 1);
                continue;
            }
            vector position = house.ModelToWorld(HCInteriorTemplates.AsVector(slot.Position));
            vector orientation = HCInteriorTemplates.AsVector(slot.Orientation);
            orientation[0] = orientation[0] + house.GetOrientation()[0];
            s_LastType = row.BuildingClass + ":" + slot.Type + "#q" + s_LastQuery.ToString();
            steps.HCAdd(STEP_LOOKUP, TickCount(mark));
            mark = TickCount(0);
            bool available = Available(module, position, orientation, slot.Type);
            steps.HCAdd(STEP_INSPECT, TickCount(mark));
            if (!available)

            {
                CountRefusal("foreign_or_ambiguous_prop", 1);
                continue;
            }
            Object object = Spawn(slot.Type, position, orientation);
            if (!object)

            {
                CountRefusal("create_failed", 1);
                continue;
            }
            mark = TickCount(0);
            LogPropBox(object);
            steps.HCAdd(STEP_LOG, TickCount(mark));
            placed.Insert(object);
            created.Insert(object);
            houseCount = houseCount + 1;
            s_Placed = s_Placed + 1;
        }
        mark = TickCount(0);
        Schedule(created);
        steps.HCAdd(STEP_SCHEDULE, TickCount(mark));
        return true;
    }

    // Native 1.30.164289: 3_Game/Global/Game.c:945 GetPlayers(out array<Man>),
    // 3_Game/Entities/Object.c:287 GetPosition; 1_Core/proto/EnConvert.c:210 DistanceSq.
    static bool PlayersNearRow(HCInteriorFurnishRow row, array<Man> players)
    {
        vector rowPosition = HCInteriorTemplates.AsVector(row.Position);
        foreach (Man nearbyPlayer : players)
        {
            if (nearbyPlayer && vector.DistanceSq(nearbyPlayer.GetPosition(), rowPosition) <= 900.0)
            {
                return true;
            }
        }
        return false;
    }

    static bool DeferredPlacementPending()
    {
        return s_Deferred.Count() > 0;
    }

    static void Place(HCInteriorsModule module, HCSettings settings, array<Object> placed, int firstRow = 0)
    {
        if (s_Started || !HCInteriorTemplates.Loaded())
        {
            return;
        }
        array<ref HCInteriorFurnishRow> rows = HCInteriorTemplates.FurnishRows();
        if (firstRow < 0)
        {
            Print("[HC Interiors] templates placement queued max_attempted_props_per_tick=1");
            return;
        }
        if (firstRow == 0)
        {
            int queuedRows = rows.Count();
            Print("[HC Interiors] templates placement queued rows=" + queuedRows.ToString() + " max_attempted_props_per_tick=1");
        }
        array<Man> players = new array<Man>();
        GetGame().GetPlayers(players);
        bool retrying = firstRow >= rows.Count();
        int rowCount = Math.Min(10, rows.Count() - firstRow);
        if (retrying)
        {
            rowCount = Math.Min(10, s_Deferred.Count());
        }
        int examined = 0;
        // Every admitted row contains <=5 slots: <=50 attempted props per tick.
        // Deferred rows are existing catalog references, bounded by its row cap.
        while (examined < rowCount)
        {
            HCInteriorFurnishRow row;
            if (retrying)
            {
                if (s_DeferredNext >= s_Deferred.Count()) { s_DeferredNext = 0; }
                row = s_Deferred[s_DeferredNext];
            }
            else
            {
                row = rows[firstRow + examined];
            }
            examined = examined + 1;
            // Defer before resolving/claiming the house or mutating any prop state.
            if (PlayersNearRow(row, players))
            {
                if (retrying)
                {
                    s_DeferredNext = s_DeferredNext + 1;
                }
                else
                {
                    s_Deferred.Insert(row);
                }
                continue;
            }
            if (retrying)
            {
                // Native 1_Core/proto/EnScript.c:463 swaps the last row into this slot.
                s_Deferred.Remove(s_DeferredNext);
            }
            if (HCInteriorRules.PlacementAdmitted())
            {
                module.PlaceCandidate(row, settings);
            }
            else
            {
                CountRefusal("acceptance_pending", row.Props.Count());
            }
        }
        if (firstRow + examined < rows.Count() || DeferredPlacementPending()) { return; }
        s_Started = true;
        string summary = "[HC Interiors] templates placement placed=" + s_Placed.ToString() + " capped=" + s_Capped.ToString();
        int reasonIndex = 0;
        // Only fixed refusal reasons enter this map (<=10).
        while (reasonIndex < s_Refused.Count() && reasonIndex < 16)
        {
            summary = summary + " refused_" + s_Refused.GetKey(reasonIndex) + "=" + s_Refused.GetElement(reasonIndex).ToString();
            reasonIndex = reasonIndex + 1;
        }
        Print(summary + "; native acceptance pending");
    }
}
