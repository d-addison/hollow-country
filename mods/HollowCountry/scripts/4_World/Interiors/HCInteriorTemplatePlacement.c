// Native 1.30.164289: 3_Game/Global/Game.c:703 CreateObjectEx;
// 3_Game/CE/CentralEconomy.c:30-33 NOLIFETIME/NOPERSISTENCY_WORLD flags.
// One deterministic startup pass, advanced in bounded batches by module ticks.
class HCInteriorTemplatePlacement
{
    protected static bool s_Started;
    protected static int s_Placed;
    protected static int s_Capped;
    protected static int s_DeferredNext;
    protected static ref array<ref HCInteriorFurnishRow> s_Deferred = new array<ref HCInteriorFurnishRow>;
    protected static string s_ResolveReason;
    protected static ref array<Object> s_Houses = new array<Object>;
    protected static ref map<string, int> s_Refused = new map<string, int>;
    protected static ref array<string> s_BoxLogged = new array<string>;

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

    static Object Resolve(HCInteriorFurnishRow row)

    {
        s_ResolveReason = "unresolved";
        array<Object> objects = new array<Object>();
        array<CargoBase> cargos = new array<CargoBase>();
        vector position = HCInteriorTemplates.AsVector(row.Position);
        GetGame().GetObjectsAtPosition3D(position, 0.75, objects, cargos);
        if (objects.Count() > 256)

        {
            s_ResolveReason = "query_cap";
            return null;
        }
        Object found;
        foreach (Object object : objects)

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
        Object object = GetGame().CreateObjectEx(type, position, flags, RF_IGNORE);
        if (object)

        {
            object.SetOrientation(orientation);
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
                GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(GetGame().UpdatePathgraphRegionByObject, 100, false, placedObject);
            }
            index = index + 1;
        }
    }

    static void PlaceRow(HCInteriorsModule module, HCInteriorFurnishRow row, HCSettings settings, array<Object> placed)

    {
        int limit = Math.Min(settings.MaxFurnishedProps, 1500);
        int houseLimit = Math.Min(settings.MaxPropsPerInterior, 5);
        if (placed.Count() >= limit)

        {
            s_Capped = s_Capped + row.Props.Count();
            return;
        }
        Object house = Resolve(row);
        if (!house)

        {
            CountRefusal(s_ResolveReason, row.Props.Count());
            return;
        }
        if (s_Houses.Find(house) >= 0)

        {
            CountRefusal("duplicate_house", row.Props.Count());
            return;
        }
        s_Houses.Insert(house);
        HCInteriorTemplate templateRow = HCInteriorTemplates.Template(row.BuildingClass);
        if (!templateRow)

        {
            CountRefusal("binding", row.Props.Count());
            return;
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
        int houseCount = 0;
        array<Object> created = new array<Object>();
        foreach (int slotId : row.Props)

        {
            if (placed.Count() >= limit || houseCount >= houseLimit)

            {
                s_Capped = s_Capped + 1;
                continue;
            }
            HCInteriorTemplatePropSlot slot = HCInteriorTemplates.Prop(templateRow, slotId);
            if (!slot || slot.History.Find(row.History) < 0 || !HCInteriorTemplates.SlotClear(templateRow, slot))

            {
                CountRefusal("clearance", 1);
                continue;
            }
            vector position = house.ModelToWorld(HCInteriorTemplates.AsVector(slot.Position));
            vector orientation = HCInteriorTemplates.AsVector(slot.Orientation);
            orientation[0] = orientation[0] + house.GetOrientation()[0];
            if (!Available(module, position, orientation, slot.Type))

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
            LogPropBox(object);
            placed.Insert(object);
            created.Insert(object);
            houseCount = houseCount + 1;
            s_Placed = s_Placed + 1;
        }
        Schedule(created);
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
        if (firstRow == 0)
        {
            int queuedRows = rows.Count();
            Print("[HC Interiors] templates placement queued rows=" + queuedRows.ToString() + " max_attempted_props_per_tick=50");
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
