// Startup-only placement. No item creation, periodic furnishing or client state.
class HCInteriorTemplatePlacement
{
    protected static bool s_Started;
    protected static int s_Placed;
    protected static int s_Capped;
    protected static string s_ResolveReason;
    protected static ref array<Object> s_Houses = new array<Object>;
    protected static ref map<string, int> s_Refused = new map<string, int>;

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
        int flags = ECE_SETUP | ECE_KEEPHEIGHT | ECE_CREATEPHYSICS | ECE_UPDATEPATHGRAPH | ECE_NOLIFETIME | ECE_DYNAMIC_PERSISTENCY;
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
            placed.Insert(object);
            created.Insert(object);
            houseCount = houseCount + 1;
            s_Placed = s_Placed + 1;
        }
        Schedule(created);
    }

    static void Place(HCInteriorsModule module, HCSettings settings, array<Object> placed)

    {
        if (s_Started || !HCInteriorTemplates.Loaded())

        {
            return;
        }
        s_Started = true;
        array<ref HCInteriorFurnishRow> rows = HCInteriorTemplates.FurnishRows();
        foreach (HCInteriorFurnishRow row : rows)

        {
            if (HCInteriorRules.PlacementAdmitted())

            {
                module.PlaceCandidate(row, settings);
            }
            else

            {
                CountRefusal("acceptance_pending", row.Props.Count());
            }
        }
        string summary = "[HC Interiors] templates placement placed=" + s_Placed.ToString() + " capped=" + s_Capped.ToString();
        int reasonIndex = 0;
        // Only the fixed reasons authored above can enter this map (<=10).
        while (reasonIndex < s_Refused.Count() && reasonIndex < 16)

        {
            summary = summary + " refused_" + s_Refused.GetKey(reasonIndex) + "=" + s_Refused.GetElement(reasonIndex).ToString();
            reasonIndex = reasonIndex + 1;
        }
        Print(summary + "; native acceptance pending");
    }
}
