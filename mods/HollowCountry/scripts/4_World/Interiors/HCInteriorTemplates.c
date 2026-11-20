// Atomic admission, staged across startup ticks. SHA-256 authenticity belongs to the operator
// install receipt; script checks syntax and cross-file binding, never hashes.
// Pack source (Workshop self-provisioning, 2026-11-18): an operator pack in
// $profile:HollowCountry/templates always wins; otherwise the default pack that
// ships in the PBO (HollowCountry/data/defaults/templates/) is read in place and
// nothing is written to the profile. One root per load, never mixed.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist and :417
// OpenFile/:425 ReadFile on a PBO path, as 3_Game/tools/JsonFileLoader.c:9-18
// reads "scripts/data/notifications.json" (Client/Notifications/NotificationSystem.c:74,285).
// GetGame().IsServer: 3_Game/Global/Game.c:1120; TickCount: EnSystem.c:106.
// Native 1_Core/proto/EnDebug.c:96 Print.
class HCInteriorTemplates
{
    static const string ROOT_PATH = "$profile:HollowCountry/templates/";
    protected static string s_Root;
    protected static string s_Source;
    protected static bool s_Attempted;
    protected static bool s_Loaded;
    protected static ref HCInteriorTemplateIndex s_Index;
    protected static ref array<ref HCInteriorTemplateClassRow> s_Classes = new array<ref HCInteriorTemplateClassRow>;
    protected static ref array<ref HCInteriorTemplate> s_Templates = new array<ref HCInteriorTemplate>;
    protected static ref array<ref HCInteriorSearchGroup> s_Groups = new array<ref HCInteriorSearchGroup>;
    protected static ref array<ref HCInteriorFurnishRow> s_Furnish = new array<ref HCInteriorFurnishRow>;
    protected static ref HCInteriorPackJob s_Job = new HCInteriorPackJob;
    // Native map.Get/Set: 1_Core/proto/EnScript.c:866,902. Arrays keep authored
    // ordering; maps avoid repeated class/template/group scans (up to 32768 groups).
    protected static ref map<string, ref HCInteriorTemplateClassRow> s_ClassIndex = new map<string, ref HCInteriorTemplateClassRow>;
    protected static ref map<string, ref HCInteriorTemplate> s_TemplateIndex = new map<string, ref HCInteriorTemplate>;
    protected static ref map<string, ref HCInteriorSearchGroup> s_GroupIndex = new map<string, ref HCInteriorSearchGroup>;
    protected static ref map<string, string> s_TemplatePins = new map<string, string>;
    protected static ref map<int, bool> s_FurnishSlots = new map<int, bool>;
    protected static ref map<string, bool> s_FurnishInstances = new map<string, bool>;
    protected static int s_FurnishProps;
    protected static int s_PendingRooms;
    protected static int s_PendingFurniture;
    protected static int s_PendingSearch;
    protected static int s_LoadCheck;
    static const int DEFAULT_PACK_LOAD_STEPS = 8; // provisional, target-load measurement owed
    // Coverage/furnish rows validated per load step; bounded, provisional.
    static const int TEMPLATE_CHECKS_PER_STEP = 32;
    protected static int s_LoadPhase;
    protected static int s_LoadChunk;
    protected static string s_Reason;
    protected static int s_MaxProps = 5;

    static bool Loaded()

    {
        return s_Loaded;
    }

    static string HCLoadReason() { return s_Reason; }

    static string HCAdmissionReason()
    {
        if (s_PendingRooms > 0 || s_PendingFurniture > 0 || s_PendingSearch > 0)
        {
            return "template_pack_admitted_unverified_coverage_pending";
        }
        return "template_pack_admitted_runtime_pending";
    }

    static HCInteriorTemplateClassRow ClassRow(string cls)

    {
        if (!s_Loaded)

        {
            return null;
        }
        return FindClass(cls);
    }

    static HCInteriorTemplate Template(string cls)

    {
        if (!s_Loaded)

        {
            return null;
        }
        return FindTemplate(cls);
    }

    static HCInteriorSearchGroup Group(string id)

    {
        if (!s_Loaded)

        {
            return null;
        }
        return FindGroup(id);
    }

    static string SourcePin()

    {
        if (!s_Loaded || !s_Index)

        {
            return "";
        }
        return s_Index.SourcePin;
    }

    static string TemplateSha256(string cls)

    {
        if (!s_Loaded || !s_Index)

        {
            return "";
        }
        return s_TemplatePins.Get(cls);
    }

    static array<ref HCInteriorFurnishRow> FurnishRows()

    {
        if (!s_Loaded)

        {
            return null;
        }
        return s_Furnish;
    }

    static HCInteriorTemplateClassRow FindClass(string cls)
    {
        return s_ClassIndex.Get(cls);
    }

    static HCInteriorTemplate FindTemplate(string cls)
    {
        return s_TemplateIndex.Get(cls);
    }

    static HCInteriorSearchGroup FindGroup(string id)
    {
        return s_GroupIndex.Get(id);
    }

    static bool Refuse(string reason)

    {
        if (s_Reason != "")

        {
            return false;
        }
        // Emit one bounded pack refusal before clearing the retained job.
        if (s_Job.Started && s_Job.Reason == "") { HCInteriorPackIndex.HCFail(s_Job, reason); }
        HCInteriorPackIndex.HCReset(s_Job);
        s_Loaded = false;
        s_Index = null;
        s_Classes.Clear();
        s_Templates.Clear();
        s_Groups.Clear();
        s_Furnish.Clear();
        s_ClassIndex.Clear();
        s_TemplateIndex.Clear();
        s_GroupIndex.Clear();
        s_TemplatePins.Clear();
        s_FurnishSlots.Clear();
        s_FurnishInstances.Clear();
        s_FurnishProps = 0;
        s_PendingRooms = 0;
        s_PendingFurniture = 0;
        s_PendingSearch = 0;
        s_LoadCheck = 0;
        s_Reason = reason;
        Print("[HC Interiors] templates refused: " + reason);
        return false;
    }

    // Screened text for LoadData; the caller runs the matching census after LoadData.
    static string ReadStrict(string fileName, string schema, string pin)
    {
        string content = HCInteriorPackIndex.HCReadChunk(s_Job, fileName, schema, pin);
        if (s_Job.Reason != "") { Refuse(s_Job.Reason); }
        return content;
    }

    static void HCLoadReset(bool receipt = false)
    {
        if (receipt) { HCInteriorPackIndex.HCReceipt(s_Job, s_Classes.Count(), false); }
        HCInteriorPackIndex.HCReset(s_Job);
        s_Attempted = false;
        s_Loaded = false;
        s_Index = null;
        s_Classes.Clear();
        s_Templates.Clear();
        s_Groups.Clear();
        s_Furnish.Clear();
        s_ClassIndex.Clear();
        s_TemplateIndex.Clear();
        s_GroupIndex.Clear();
        s_TemplatePins.Clear();
        s_FurnishSlots.Clear();
        s_FurnishInstances.Clear();
        s_FurnishProps = 0;
        s_PendingRooms = 0;
        s_PendingFurniture = 0;
        s_PendingSearch = 0;
        s_LoadCheck = 0;
        s_Root = "";
        s_Source = "";
        s_Reason = "";
        s_LoadPhase = 0;
        s_LoadChunk = 0;
    }

    // "profile", "mission", "pbo" or "missing" once EnsureLoaded has run.
    static string PackSource()

    {
        return s_Source;
    }

    static string SelectRoot()

    {
        string index = HCProfileDefaults.Resolve("templates/index.json", HCProfileDefaults.PBO_ROOT);
        // Native EnSystem.c:397 FileExist; 3_Game/CfgGameplayHandler.c:3 $mission:.
        // Operator profile remains authoritative. Generated mission data takes
        // precedence over an older shipped default, with one root per load.
        string missionIndex = "$mission:hollow-country/interiors/templates/index.json";
        if (index != HCInteriorTemplates.ROOT_PATH + "index.json" && FileExist(missionIndex))
        {
            s_Source = "mission";
            return "$mission:hollow-country/interiors/templates/";
        }
        if (index == "")

        {
            s_Source = "missing";
            return "";
        }
        s_Source = "pbo";
        if (index == ROOT_PATH + "index.json")

        {
            s_Source = "profile";
        }
        int rootLength = index.Length() - 10;
        return index.Substring(0, rootLength);
    }

    static bool Disposition(string value)

    {
        return value == "covered" || value == "unmeasured" || value == "not_enterable" || value == "path_pending" || value == "door_pending" || value == "unsupported_geometry" || value == "frame_unverified" || value == "clearance_failed" || value == "no_ce_points" || value == "not_in_mapgrouppos" || value == "over_budget";
    }

    static bool Covered(HCInteriorTemplateClassRow row)

    {
        return row.Rooms == "covered" || row.Furniture == "covered" || row.Search == "covered";
    }

    static string Numbered(string prefix, int index, int width)

    {
        string digits = index.ToString();
        while (digits.Length() < width)

        {
            digits = "0" + digits;
        }
        return prefix + digits + ".json";
    }

    // Pins join the caller's hex batch; the caller checks the batch once.
    static bool FilesValid(array<ref HCInteriorTemplateFile> rows, string prefix, int cap, HCInteriorHexBatch pins)

    {
        if (!rows || rows.Count() > cap)

        {
            return false;
        }
        int number = 0;
        foreach (HCInteriorTemplateFile row : rows)

        {
            if (!row || row.FileName != Numbered(prefix, number, 3))

            {
                return false;
            }
            pins.HCAdd(row.Sha256, 64);
            number = number + 1;
        }
        return true;
    }

    static bool IndexValid(HCInteriorTemplateIndex index)

    {
        if (!index || index.SchemaVersion != 2 || index.Kind != "hc-interior-templates" || index.WorldName != "chernarusplus" || !HCBuildIdentity.Matches(index.Build) || index.Frame != "rot90" || !index.Provisional)

        {
            return false;
        }
        string world = GetGame().GetWorldName();
        world.ToLower();
        if (world != index.WorldName)

        {
            return false;
        }
        // Every hex pin in the index goes through one batch of native scans.
        HCInteriorHexBatch pins = new HCInteriorHexBatch;
        pins.HCAdd(index.PackId, 32);
        pins.HCAdd(index.SourcePin, 64);
        if (!index.Sources || index.Sources.Count() < 8 || index.Sources.Count() > 520)

        {
            return false;
        }
        string requiredSources = "mapgroupproto mapgrouppos types cfgspawnabletypes cfglimitsdefinition generator search-generator";
        array<string> sourceNames = new array<string>();
        requiredSources.Split(" ", sourceNames);
        foreach (string requiredSource : sourceNames)

        {
            if (!index.Sources.Contains(requiredSource))

            {
                return false;
            }
        }
        int sourceIndex = 0;
        while (sourceIndex < index.Sources.Count())

        {
            if (!HCInteriorTemplatesStrict.SourceName(index.Sources.GetKey(sourceIndex), pins))

            {
                return false;
            }
            pins.HCAdd(index.Sources.GetElement(sourceIndex), 64);
            sourceIndex = sourceIndex + 1;
        }
        if (!FilesValid(index.ClassFiles, "classes-", 16, pins) || index.ClassFiles.Count() < 1 || !FilesValid(index.FurnishFiles, "furnish-", 16, pins) || !FilesValid(index.GroupFiles, "search-groups-", 64, pins))

        {
            return false;
        }
        if (!index.TemplateFiles || index.TemplateFiles.Count() > 512)

        {
            return false;
        }
        int number = 0;
        map<string, bool> seen = new map<string, bool>();
        foreach (HCInteriorTemplateFileBinding binding : index.TemplateFiles)

        {
            if (!binding || binding.FileName != Numbered("t-", number, 4) || !HCInteriorTemplatesStrict.Text(binding.BuildingClass, 128) || seen.Contains(binding.BuildingClass))

            {
                return false;
            }
            pins.HCAdd(binding.Sha256, 64);
            seen.Set(binding.BuildingClass, true);
            number = number + 1;
        }
        if (!pins.HCValid())

        {
            return false;
        }
        return index.ClassFiles.Count() + index.TemplateFiles.Count() + index.FurnishFiles.Count() + index.GroupFiles.Count() <= 610;
    }

    // Each pack class must be a House class the engine knows. The engine has thousands of House
    // classes (walls, wrecks, ruins); the pack covers only the ones it lists, so it is not an
    // exact census of CfgVehicles and the config is read per listed class, never enumerated.
    static bool EngineHouse(string cls)

    {
        // Native 1.30.164289 3_Game/Global/Game.c:612 ConfigIsExisting, :1437 IsKindOf.
        return GetGame().ConfigIsExisting("CfgVehicles " + cls) && GetGame().IsKindOf(cls, "House");
    }

    static bool VectorValid(array<float> value, float limit)

    {
        if (!value || value.Count() != 3)

        {
            return false;
        }
        return HCInteriorRules.SaneVector(AsVector(value), limit);
    }

    static vector AsVector(array<float> value)

    {
        return Vector(value[0], value[1], value[2]);
    }

    static bool BoxValid(array<float> minimum, array<float> maximum)

    {
        return VectorValid(minimum, 512) && VectorValid(maximum, 512) && minimum[0] < maximum[0] && minimum[1] < maximum[1] && minimum[2] < maximum[2];
    }

    static bool Inside(array<float> point, array<float> minimum, array<float> maximum)

    {
        return point[0] >= minimum[0] && point[0] <= maximum[0] && point[1] >= minimum[1] && point[1] <= maximum[1] && point[2] >= minimum[2] && point[2] <= maximum[2];
    }

    static bool Intersects(array<float> aMin, array<float> aMax, array<float> bMin, array<float> bMax, float margin)

    {
        if (margin > 0)
        {
            // Distance between the floor rectangles, including diagonal gaps.
            // Exactly 0.6 m is sufficient; less is refused.
            float gapX = Math.Max(0, Math.Max(bMin[0] - aMax[0], aMin[0] - bMax[0]));
            float gapZ = Math.Max(0, Math.Max(bMin[2] - aMax[2], aMin[2] - bMax[2]));
            return aMax[1] >= bMin[1] && aMin[1] <= bMax[1] && gapX * gapX + gapZ * gapZ < margin * margin;
        }
        return aMax[0] >= bMin[0] && aMin[0] <= bMax[0] && aMax[1] >= bMin[1] && aMin[1] <= bMax[1] && aMax[2] >= bMin[2] && aMin[2] <= bMax[2];
    }

    static HCInteriorTemplateRoom Room(HCInteriorTemplate templateRow, int id)

    {
        foreach (HCInteriorTemplateRoom roomRow : templateRow.Rooms)

        {
            if (roomRow.Id == id)

            {
                return roomRow;
            }
        }
        return null;
    }

    static HCInteriorTemplatePropSlot Prop(HCInteriorTemplate templateRow, int id)

    {
        foreach (HCInteriorTemplatePropSlot propRow : templateRow.PropSlots)

        {
            if (propRow.Id == id)

            {
                return propRow;
            }
        }
        return null;
    }

    static bool PropType(string type)

    {
        return HCInteriorCatalog.SearchType(type) || type == "StaticObj_Furniture_PaperBox_01_small_closed" || type == "StaticObj_Furniture_PaperBox_01_small_ransacked" || type == "StaticObj_Furniture_kitchen_chair_a" || type == "StaticObj_Furniture_matress_white" || type == "StaticObj_Furniture_postel_panelak1" || type == "StaticObj_Furniture_kitchen_table_a" || type == "StaticObj_Furniture_Kitchen_desk_A" || type == "StaticObj_Furniture_case_sink_a" || type == "StaticObj_Furniture_Dkamna_bila" || type == "StaticObj_Furniture_Kitchenstove_Elec" || type == "StaticObj_Furniture_sofa_leather_old" || type == "StaticObj_Furniture_PaperBox_01_small_destroyed" || type == "StaticObj_Furniture_debris_small_house" || type == "StaticObj_Furniture_dirtpile_small_house";
    }

    static bool SlotClear(HCInteriorTemplate templateRow, HCInteriorTemplatePropSlot propRow)

    {
        HCInteriorTemplateRoom roomRow = Room(templateRow, propRow.Room);
        if (!roomRow || !propRow.Bounds || !BoxValid(propRow.Bounds.Min, propRow.Bounds.Max) || !Inside(propRow.Bounds.Min, roomRow.Min, roomRow.Max) || !Inside(propRow.Bounds.Max, roomRow.Min, roomRow.Max))

        {
            return false;
        }
        if (!VectorValid(propRow.Position, 512) || !Inside(propRow.Position, propRow.Bounds.Min, propRow.Bounds.Max) || !VectorValid(propRow.Orientation, 360) || propRow.Orientation[1] != 0 || propRow.Orientation[2] != 0)

        {
            return false;
        }
        foreach (HCInteriorTemplateKeepOut keepOut : templateRow.KeepOuts)

        {
            float margin = 0;
            if (keepOut.Kind == "door")

            {
                margin = 0.6;
            }
            if (Intersects(propRow.Bounds.Min, propRow.Bounds.Max, keepOut.Min, keepOut.Max, margin))

            {
                return false;
            }
        }
        return true;
    }

    static bool Container(string value)

    {
        return value == "lootshelves" || value == "loot" || value == "lootFloor" || value == "lootweapons";
    }

    static bool Texts(array<string> values, int minimum, int maximum)

    {
        if (!values || values.Count() < minimum || values.Count() > maximum)

        {
            return false;
        }
        // Character set was screened for the whole file; a map refuses duplicates.
        // Native map.Contains/Set: 1_Core/proto/EnScript.c:917/902 (1.30.164289).
        map<string, bool> seenValues = new map<string, bool>();
        foreach (string value : values)

        {
            if (!HCInteriorTemplatesStrict.Text(value, 128) || seenValues.Contains(value))

            {
                return false;
            }
            seenValues.Set(value, true);
        }
        return true;
    }

    static bool TemplateValid(HCInteriorTemplate templateRow)

    {
        if (!templateRow || templateRow.SchemaVersion != 2 || !HCInteriorTemplatesStrict.Text(templateRow.TemplateId, 128) || !templateRow.Box || !BoxValid(templateRow.Box.Min, templateRow.Box.Max))

        {
            return false;
        }
        HCInteriorTemplateClassRow classRow = FindClass(templateRow.BuildingClass);
        if (!classRow || !Covered(classRow))

        {
            return false;
        }
        if (!templateRow.Evidence || templateRow.Evidence.Count() < 1 || templateRow.Evidence.Count() > 512)

        {
            return false;
        }
        array<string> runs = new array<string>();
        foreach (HCInteriorTemplateEvidence evidence : templateRow.Evidence)

        {
            // Sources keys and pins passed the hex batch in IndexValid, so a matching
            // census-<RunId> entry proves RunId and Sha256 are lowercase hex.
            if (!evidence || evidence.Kind != "native-room-survey-v1" || evidence.RunId.Length() != 32 || evidence.Sha256.Length() != 64 || s_Index.Sources.Get("census-" + evidence.RunId) != evidence.Sha256 || runs.Find(evidence.RunId) >= 0)

            {
                return false;
            }
            runs.Insert(evidence.RunId);
        }
        // A search-only template (rooms lack path/door proof) carries no rooms: search runs at the class's
        // vanilla CE container points, while infected rooms and furniture need Rooms == "covered".
        bool searchOnly = classRow.Rooms != "covered" && classRow.Furniture != "covered";
        if (!templateRow.Rooms || templateRow.Rooms.Count() > 16 || (templateRow.Rooms.Count() < 1 && !searchOnly))

        {
            return false;
        }
        array<int> roomIds = new array<int>();
        array<vector> anchors = new array<vector>();
        foreach (HCInteriorTemplateRoom roomRow : templateRow.Rooms)

        {
            if (!roomRow || roomRow.Id < 1 || roomIds.Find(roomRow.Id) >= 0 || !HCInteriorTemplatesStrict.Text(roomRow.Label, 128) || !BoxValid(roomRow.Min, roomRow.Max) || !Inside(roomRow.Min, templateRow.Box.Min, templateRow.Box.Max) || !Inside(roomRow.Max, templateRow.Box.Min, templateRow.Box.Max) || !VectorValid(roomRow.Anchor, 512) || !Inside(roomRow.Anchor, roomRow.Min, roomRow.Max) || !(roomRow.FloorY >= roomRow.Min[1] && roomRow.FloorY <= roomRow.Max[1]) || roomRow.Cells < 1)

            {
                return false;
            }
            vector anchor = AsVector(roomRow.Anchor);
            foreach (vector previousAnchor : anchors)

            {
                if (vector.DistanceSq(anchor, previousAnchor) < 1)

                {
                    return false;
                }
            }
            roomIds.Insert(roomRow.Id);
            anchors.Insert(anchor);
        }
        if (!templateRow.KeepOuts || templateRow.KeepOuts.Count() > 32)

        {
            return false;
        }
        array<string> keepKeys = new array<string>();
        foreach (HCInteriorTemplateKeepOut keepOut : templateRow.KeepOuts)

        {
            if (!keepOut || (keepOut.Kind != "door" && keepOut.Kind != "stair" && keepOut.Kind != "ce-point") || keepOut.Index < 0 || !BoxValid(keepOut.Min, keepOut.Max) || !Inside(keepOut.Min, templateRow.Box.Min, templateRow.Box.Max) || !Inside(keepOut.Max, templateRow.Box.Min, templateRow.Box.Max))

            {
                return false;
            }
            string keepKey = keepOut.Kind + "_" + keepOut.Index.ToString();
            if (keepKeys.Find(keepKey) >= 0)

            {
                return false;
            }
            keepKeys.Insert(keepKey);
        }
        // Validate the bounded catalog independently of the operator's placement cap.
        // PlaceRow emits only the allowed prefix and logs each capped building class once.
        if (!templateRow.PropSlots || templateRow.PropSlots.Count() > 20 || (classRow.Furniture == "covered" && templateRow.PropSlots.Count() < 1))

        {
            return false;
        }
        array<int> propIds = new array<int>();
        foreach (HCInteriorTemplatePropSlot propRow : templateRow.PropSlots)

        {
            if (!propRow || propRow.Id < 1 || propIds.Find(propRow.Id) >= 0 || !HCInteriorTemplatesStrict.Text(propRow.Type, 128) || !PropType(propRow.Type) || !GetGame().ConfigIsExisting("CfgVehicles " + propRow.Type) || !SlotClear(templateRow, propRow) || !Texts(propRow.History, 1, 3))

            {
                return false;
            }
            foreach (string history : propRow.History)

            {
                if (history != "family" && history != "ransacked" && history != "abandoned")

                {
                    return false;
                }
            }
            propIds.Insert(propRow.Id);
        }
        if (!templateRow.SearchSites || templateRow.SearchSites.Count() > 24 || (classRow.Search == "covered" && templateRow.SearchSites.Count() < 1))

        {
            return false;
        }
        array<int> siteIds = new array<int>();
        foreach (HCInteriorTemplateSearchSite siteRow : templateRow.SearchSites)

        {
            if (!siteRow || siteRow.Id < 1 || siteIds.Find(siteRow.Id) >= 0 || !(Room(templateRow, siteRow.Room) || (siteRow.Room == 0 && templateRow.Rooms.Count() == 0)) || !VectorValid(siteRow.Center, 512) || !Inside(siteRow.Center, templateRow.Box.Min, templateRow.Box.Max) || !(siteRow.Radius >= 0.25 && siteRow.Radius <= 8) || !Container(siteRow.Source) || !Texts(siteRow.Groups, 1, 8) || !siteRow.Points || siteRow.Points.Count() < 1 || siteRow.Points.Count() > 8192)

            {
                return false;
            }
            array<int> pointIds = new array<int>();
            foreach (int pointId : siteRow.Points)

            {
                if (pointId < 0 || pointIds.Find(pointId) >= 0)

                {
                    return false;
                }
                pointIds.Insert(pointId);
            }
            foreach (string groupId : siteRow.Groups)

            {
                HCInteriorSearchGroup groupRow = FindGroup(groupId);
                if (!groupRow || groupRow.Container != siteRow.Source)

                {
                    return false;
                }
            }
            siteIds.Insert(siteRow.Id);
        }
        return true;
    }

    // One retained furnishing row per step; no all-pack scan at the phase boundary.
    static bool HCFurnishRowValid(HCInteriorFurnishRow row)
    {
        HCInteriorTemplate templateRow = FindTemplate(row.BuildingClass);
        HCInteriorTemplateClassRow classRow = FindClass(row.BuildingClass);
        if (!templateRow || !classRow || classRow.Furniture != "covered" || row.SlotId < 0 || row.SlotId >= 1500 || s_FurnishSlots.Get(row.SlotId) || !VectorValid(row.Position, 20000) || !(row.Yaw >= -360 && row.Yaw <= 360) || !row.Props || row.Props.Count() < 1 || row.Props.Count() > 5 || (row.History != "family" && row.History != "ransacked" && row.History != "abandoned"))
        {
            return false;
        }
        string instanceKey = row.BuildingClass + "_" + HCInteriorRules.TransformKey(AsVector(row.Position), Vector(0, 0, 0));
        if (s_FurnishInstances.Get(instanceKey)) { return false; }
        s_FurnishInstances.Set(instanceKey, true);
        s_FurnishSlots.Set(row.SlotId, true);
        array<int> ids = new array<int>();
        foreach (int id : row.Props)
        {
            HCInteriorTemplatePropSlot propRow = Prop(templateRow, id);
            if (!propRow || propRow.History.Find(row.History) < 0 || ids.Find(id) >= 0) { return false; }
            ids.Insert(id);
            s_FurnishProps = s_FurnishProps + 1;
            if (s_FurnishProps > 1500) { return false; }
        }
        return true;
    }

    static bool LegacyConflict(HCInteriorConfig legacy)

    {
        // Section 9 requires both room owners to refuse when this legacy
        // document and a pack coexist, even before its bindings are published.
        if (FileExist("$profile:HollowCountry/Infected/production-rooms.json"))

        {
            return true;
        }
        string measuredClass = HCInteriorMeasuredCatalog.MeasuredClaimedClass();
        HCInteriorTemplateClassRow measuredRow = FindClass(measuredClass);
        if (measuredRow && Covered(measuredRow))

        {
            return true;
        }
        if (!legacy || !legacy.Candidates || legacy.Candidates.Count() > 12)

        {
            return false;
        }
        foreach (HCInteriorCandidate candidate : legacy.Candidates)

        {
            if (candidate)

            {
                HCInteriorTemplateClassRow row = FindClass(candidate.Type);
                if (row && Covered(row))

                {
                    return true;
                }
            }
        }
        return false;
    }

    // Begin once at boot. The owning module advances this retained job on ticks.
    static void EnsureLoaded(HCInteriorConfig legacy, int maxProps = 5)
    {
        if (s_Attempted) { return; }
        s_Attempted = true;
        if (maxProps < 1 || maxProps > 20) { Refuse("prop_setting"); return; }
        s_MaxProps = maxProps;
        s_Root = SelectRoot();
        Print(HCV2Admission.Line("InteriorTemplates", true, "interior_placement", false) + " runtime=PENDING");
        Print("[HC Interiors] templates source=" + s_Source + " root=" + s_Root + "; operator profile pack wins, shipped pack is read in place and never copied");
        if (s_Root == "")
        {
            Print("[HC Interiors] template pack missing: profile, mission and PBO defaults absent runtime=PENDING");
        }
        bool started = HCInteriorPackIndex.HCStart(s_Job, s_Root);
        if (s_Job.Reason != "") { Refuse(s_Job.Reason); return; }
        if (!started) { Refuse("pack_start"); }
    }

    static bool HCLoadFinished()
    {
        return s_Attempted && (s_Loaded || s_Reason != "");
    }

    // Native EnSystem.c:106 TickCount and Game.c:1535 GetTime. Raw deltas
    // include staged waiting and are sampled per step; ms use the mission clock.
    static string HCLoadDuration(HCInteriorPackJob job)
    {
        float loadTicks = 0;
        int loadMs = 0;
        if (job.Started)
        {
            loadTicks = job.LoadTicks;
            loadMs = job.LoadMs;
            if (!job.TimingFinished)
            {
                int loadStart = job.TickSample;
                loadTicks = loadTicks + TickCount(loadStart);
                loadMs = GetGame().GetTime() - job.StartMs;
            }
        }
        return " load_ticks=" + loadTicks.ToString() + " load_ms=" + loadMs.ToString();
    }

    static int HCLoadStepLimit(HCInteriorConfig config)
    {
        // Missing legacy int fields are zero-filled by JsonFileLoader.
        if (!config || config.TemplateLoadStepsPerTick < 1 || config.TemplateLoadStepsPerTick > 64)
        {
            return HCInteriorTemplates.DEFAULT_PACK_LOAD_STEPS;
        }
        return config.TemplateLoadStepsPerTick;
    }

    // Native EnScript.c:400 array.Get, :380 Count (installed 1.30.164289).
    // Only the production slice adapter asks for the next leaf. Metadata and
    // transitions retain the original reader's admission/ordering checks.
    static string HCNextLeaf()
    {
        if (s_Loaded || s_Reason != "") { return ""; }
        if (!s_Job.Ready)
        {
            if (s_Job.Started && s_Job.Header && s_Job.NextPage < s_Job.Header.IndexFiles.Count()) { return s_Job.Header.IndexFiles.Get(s_Job.NextPage).FileName; }
            return "";
        }
        if (s_Job.PendingClasses || s_Job.PendingGroups || s_Job.PendingFurnish) { return ""; }
        HCInteriorTemplateIndex nextIndex = s_Job.Index;
        if (s_LoadPhase == 0 && s_LoadChunk < nextIndex.ClassFiles.Count()) { return nextIndex.ClassFiles.Get(s_LoadChunk).FileName; }
        if (s_LoadPhase == 1 && s_LoadChunk < nextIndex.GroupFiles.Count()) { return nextIndex.GroupFiles.Get(s_LoadChunk).FileName; }
        if (s_LoadPhase == 2 && s_LoadChunk < nextIndex.TemplateFiles.Count()) { return nextIndex.TemplateFiles.Get(s_LoadChunk).FileName; }
        if (s_LoadPhase == 3 && s_LoadChunk < nextIndex.FurnishFiles.Count()) { return nextIndex.FurnishFiles.Get(s_LoadChunk).FileName; }
        return "";
    }

    static HCInteriorPackJob HCPackJob() { return s_Job; }

    // 1 budget exhausted; 3 metadata page merged (caller may take another step).
    static int HCLoadStep(HCInteriorConfig legacy, HCWorkBudget budget)
    {
        if (!s_Attempted || s_Loaded || s_Reason != "") { return 0; }
        int status = HCInteriorPackIndex.HCStep(s_Job, budget);
        if (s_Job.Reason != "") { Refuse(s_Job.Reason); return 2; }
        if (status == 1) { return 1; }
        if (status == 2) { Refuse("pack_step"); return 2; }
        if (status == 3) { return 3; }
        // Guard phase transitions and validation too, not only file reads.
        if (!budget || !budget.HCContinue()) { return 1; }
        // Consume the admitted index object; never reload index.json.
        s_Index = s_Job.Index;
        HCInteriorTemplateIndex index = s_Index;
        string error;
        string content;
        if (s_LoadPhase == 0)
        {
            if (s_LoadChunk >= index.ClassFiles.Count())
            {
                if (s_Classes.Count() < 1) { Refuse("house_denominator"); return 2; }
                if (LegacyConflict(legacy))
                {
                    if (s_Source == "pbo") { Print("[HC Interiors] shipped pack yields to legacy room owner"); }
                    Refuse("rooms_conflict");
                    return 2;
                }
                s_LoadPhase = 1;
                s_LoadChunk = 0;
                return 0;
            }
            if (!s_Job.PendingClasses)
            {
                HCInteriorTemplateFile classFile = index.ClassFiles.Get(s_LoadChunk);
                content = ReadStrict(classFile.FileName, "classes", classFile.Sha256);
                HCInteriorTemplateClasses classes = new HCInteriorTemplateClasses;
                if (content == "" || !JsonFileLoader<HCInteriorTemplateClasses>.LoadData(content, classes, error) || !HCInteriorTemplatesStrict.ClassesCensus(content, classes) || classes.SchemaVersion != 2 || classes.Chunk != s_LoadChunk || !classes.Rows || classes.Rows.Count() < 1 || classes.Rows.Count() > 160)

                {
                    Refuse("classes_chunk");
                    return 2;
                }
                s_Job.PendingClasses = classes;
                s_Job.ValidateNext = 0;
                return 0;
            }
            if (s_Job.ValidateNext < s_Job.PendingClasses.Rows.Count())
            {
                int classBatch = 0;
                while (s_Job.ValidateNext < s_Job.PendingClasses.Rows.Count() && classBatch < HCInteriorTemplates.TEMPLATE_CHECKS_PER_STEP)
                {
                    if (classBatch > 0 && !budget.HCContinue()) { return 1; }
                    HCInteriorTemplateClassRow classRow = s_Job.PendingClasses.Rows.Get(s_Job.ValidateNext);

                    if (!classRow || !HCInteriorTemplatesStrict.Text(classRow.BuildingClass, 128) || !Disposition(classRow.Rooms) || !Disposition(classRow.Furniture) || !Disposition(classRow.Search) || FindClass(classRow.BuildingClass) || s_Classes.Count() >= 2048)

                    {
                        Refuse("class_row");
                        return 2;
                    }
                    if (!EngineHouse(classRow.BuildingClass)) { Refuse("house_denominator"); return 2; }
                    if (classRow.Rooms != "covered") { s_PendingRooms = s_PendingRooms + 1; }
                    if (classRow.Furniture != "covered") { s_PendingFurniture = s_PendingFurniture + 1; }
                    if (classRow.Search != "covered") { s_PendingSearch = s_PendingSearch + 1; }
                    s_Classes.Insert(classRow);
                    s_ClassIndex.Set(classRow.BuildingClass, classRow);
                    s_Job.ValidateNext = s_Job.ValidateNext + 1;
                    classBatch = classBatch + 1;
                }
                return 0;
            }
            s_Job.PendingClasses = null;

        }
        if (s_LoadPhase == 1)
        {
            if (s_LoadChunk >= index.GroupFiles.Count())
            {
                s_LoadPhase = 2;
                s_LoadChunk = 0;
                return 0;
            }
            if (!s_Job.PendingGroups)
            {
                HCInteriorTemplateFile groupFile = index.GroupFiles.Get(s_LoadChunk);
                content = ReadStrict(groupFile.FileName, "groups", groupFile.Sha256);
                HCInteriorTemplateGroups groups = new HCInteriorTemplateGroups;
                if (content == "" || !JsonFileLoader<HCInteriorTemplateGroups>.LoadData(content, groups, error) || !HCInteriorTemplatesStrict.GroupsCensus(content, groups) || groups.SchemaVersion != 2 || groups.Chunk != s_LoadChunk || !groups.Groups || groups.Groups.Count() < 1 || groups.Groups.Count() > 512)

                {
                    Refuse("groups_chunk");
                    return 2;
                }
                s_Job.PendingGroups = groups;
                s_Job.ValidateNext = 0;
                return 0;
            }
            if (s_Job.ValidateNext < s_Job.PendingGroups.Groups.Count())
            {
                int groupBatch = 0;
                while (s_Job.ValidateNext < s_Job.PendingGroups.Groups.Count() && groupBatch < HCInteriorTemplates.TEMPLATE_CHECKS_PER_STEP)
                {
                    if (groupBatch > 0 && !budget.HCContinue()) { return 1; }
                    HCInteriorSearchGroup groupRow = s_Job.PendingGroups.Groups.Get(s_Job.ValidateNext);

                    if (!groupRow || !HCInteriorTemplatesStrict.Text(groupRow.Id, 128) || FindGroup(groupRow.Id) || !Container(groupRow.Container) || !Texts(groupRow.Usages, 0, 8192) || !Texts(groupRow.Categories, 1, 8192) || !Texts(groupRow.Tags, 0, 8192) || !Texts(groupRow.Items, 1, 1024) || s_Groups.Count() >= 32768)

                    {
                        Refuse("group_row");
                        return 2;
                    }
                    s_Groups.Insert(groupRow);
                    s_GroupIndex.Set(groupRow.Id, groupRow);
                    s_Job.ValidateNext = s_Job.ValidateNext + 1;
                    groupBatch = groupBatch + 1;
                }
                return 0;
            }
            s_Job.PendingGroups = null;

        }
        if (s_LoadPhase == 2)
        {
            if (s_LoadChunk >= index.TemplateFiles.Count())
            {
                s_LoadPhase = 4;
                s_LoadCheck = 0;
                return 0;
            }
            HCInteriorTemplateFileBinding templateFile = index.TemplateFiles.Get(s_LoadChunk);
            content = ReadStrict(templateFile.FileName, "template", templateFile.Sha256);
            HCInteriorTemplate loadedTemplate = new HCInteriorTemplate;
            if (content == "" || !JsonFileLoader<HCInteriorTemplate>.LoadData(content, loadedTemplate, error) || !HCInteriorTemplatesStrict.TemplateCensus(content, loadedTemplate) || loadedTemplate.BuildingClass != templateFile.BuildingClass || FindTemplate(loadedTemplate.BuildingClass) || !TemplateValid(loadedTemplate))

            {
                Refuse("template_or_evidence_pin");
                return 2;
            }
            s_Templates.Insert(loadedTemplate);
            s_TemplateIndex.Set(loadedTemplate.BuildingClass, loadedTemplate);
            s_TemplatePins.Set(loadedTemplate.BuildingClass, templateFile.Sha256);
        }
        if (s_LoadPhase == 3)
        {
            if (s_LoadChunk >= index.FurnishFiles.Count())
            {
                s_LoadPhase = 5;
                s_LoadCheck = 0;
                return 0;
            }
            if (!s_Job.PendingFurnish)
            {
                HCInteriorTemplateFile furnishFile = index.FurnishFiles.Get(s_LoadChunk);
                content = ReadStrict(furnishFile.FileName, "furnish", furnishFile.Sha256);
                HCInteriorTemplateFurnish furnish = new HCInteriorTemplateFurnish;
                if (content == "" || !JsonFileLoader<HCInteriorTemplateFurnish>.LoadData(content, furnish, error) || !HCInteriorTemplatesStrict.FurnishCensus(content, furnish) || furnish.SchemaVersion != 2 || furnish.Chunk != s_LoadChunk || !furnish.Rows || furnish.Rows.Count() < 1 || furnish.Rows.Count() > 128)

                {
                    Refuse("furnish_chunk");
                    return 2;
                }
                s_Job.PendingFurnish = furnish;
                s_Job.ValidateNext = 0;
                return 0;
            }
            if (s_Job.ValidateNext < s_Job.PendingFurnish.Rows.Count())
            {
                // Rows are only queued here; phase 5 validates them in budgeted batches.
                while (s_Job.ValidateNext < s_Job.PendingFurnish.Rows.Count())
                {
                    HCInteriorFurnishRow furnishRow = s_Job.PendingFurnish.Rows.Get(s_Job.ValidateNext);

                    if (!furnishRow || s_Furnish.Count() >= 1500)

                    {
                        Refuse("furnish_rows");
                        return 2;
                    }
                    s_Furnish.Insert(furnishRow);
                    s_Job.ValidateNext = s_Job.ValidateNext + 1;
                }
                return 0;
            }
            s_Job.PendingFurnish = null;

        }
        if (s_LoadPhase == 4)
        {
            if (s_LoadCheck < s_Classes.Count())
            {
                int coverageBatch = 0;
                HCInteriorTemplateClassRow checkRow;
                while (s_LoadCheck < s_Classes.Count() && coverageBatch < HCInteriorTemplates.TEMPLATE_CHECKS_PER_STEP)
                {
                    if (coverageBatch > 0 && !budget.HCContinue()) { return 1; }
                    checkRow = s_Classes.Get(s_LoadCheck);
                    if (Covered(checkRow) != (FindTemplate(checkRow.BuildingClass) != null))
                    {
                        Refuse("template_coverage");
                        return 2;
                    }
                    s_LoadCheck = s_LoadCheck + 1;
                    coverageBatch = coverageBatch + 1;
                }
                return 0;
            }
            s_LoadPhase = 3;
            s_LoadChunk = 0;
            return 0;
        }
        if (s_LoadPhase == 5)
        {
            if (s_LoadCheck < s_Furnish.Count())
            {
                int furnishBatch = 0;
                while (s_LoadCheck < s_Furnish.Count() && furnishBatch < HCInteriorTemplates.TEMPLATE_CHECKS_PER_STEP)
                {
                    if (furnishBatch > 0 && !budget.HCContinue()) { return 1; }
                    if (!HCFurnishRowValid(s_Furnish.Get(s_LoadCheck))) { Refuse("furnish_binding_or_budget"); return 2; }
                    s_LoadCheck = s_LoadCheck + 1;
                    furnishBatch = furnishBatch + 1;
                }
                return 0;
            }
            s_Loaded = true;
            HCInteriorPackIndex.HCReceipt(s_Job, s_Classes.Count(), true);
            Print("[HC Interiors] templates provisional; native clearance/path/audio/replication acceptance pending; files=" + s_Job.Files.ToString());
            string coverageReceipt = "[HC Interiors] coverage admitted unverified classes=" + s_Classes.Count().ToString() + " templates=" + s_Templates.Count().ToString();
            coverageReceipt = coverageReceipt + " furnishing_rows=" + s_Furnish.Count().ToString() + " props=" + s_FurnishProps.ToString() + " runtime=PENDING";
            Print("" + coverageReceipt);
            Print("[HC Interiors] coverage native_queue rooms=" + s_PendingRooms.ToString() + " furniture=" + s_PendingFurniture.ToString() + " search=" + s_PendingSearch.ToString() + " runtime=PENDING");
            return 0;
        }
        s_LoadChunk = s_LoadChunk + 1;
        return 0;
    }
}

// HC-24 lifecycle bridge stays with its reader. All overridden hooks are declared
// on the base HCInteriorsModule; no call depends on a later modded link's methods.
// The existing template extension begins the load after super.OnStart returns.
// Shared module ticks (runtime contract) advance metadata/leaves before that
// extension's instance guard, including when the optional legacy pilot is absent.
modded class HCInteriorsModule
{
    protected bool m_PackLoading;
    protected ref HCOperationalStatus m_PackStatus = new HCOperationalStatus;

    override HCOperationalStatus HCGetOperationalStatus()
    {
        // Select once from cached owner/load state; never publish transient
        // off/refused revisions before the final ready state in the same read.
        string state = "off";
        string reason = "template_owner_not_running";
        if (m_PackLoading)
        {
            state = "requested";
            reason = "template_pack_loading";
        }
        if (HCInteriorTemplates.HCLoadFinished())
        {
            state = "refused";
            reason = "template_pack_" + HCInteriorTemplates.HCLoadReason();
            if (HCInteriorTemplates.Loaded())
            {
                state = "ready";
                reason = HCInteriorTemplates.HCAdmissionReason();
            }
        }
        if (m_Ready && s_Instance == this && !HCInteriorTemplates.HCLoadFinished() && !m_PackLoading)
        {
            state = "ready";
            reason = "legacy_pilot_admitted_runtime_pending";
        }
        m_PackStatus.HCPublish(state, reason);
        return m_PackStatus;
    }
    protected ref HCWorkBudget m_PackBudget = new HCWorkBudget;
    // Search readiness (journal open) runs on the tick after the load finishes, so the
    // finishing slice never also pays for it.
    protected bool m_PackCompletePending;

    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        m_PackLoading = GetGame().IsServer() && IsEnabled(settings);
    }

    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (m_PackCompletePending)
        {
            m_PackCompletePending = false;
            HCSearchBinding.TemplatesComplete(this);
        }
        if (!m_PackLoading || !GetGame().IsServer()) { return; }
        HCSettings settings = HCServer.Get().GetSettings();
        if (!IsEnabled(settings)) { this.OnStop(); return; }
        int stepLimit = HCInteriorTemplates.HCLoadStepLimit(m_Config);
        if (!HCInteriorTemplates.HCLoadFinished())
        {
            m_PackBudget.HCReset(stepLimit);
            HCPackAdvance(stepLimit);
        }
        // A later slice (HCPerfInteriorSlices) may finish the load; publish on the module tick.
        if (!HCInteriorTemplates.HCLoadFinished()) { return; }
        m_PackLoading = false;
        if (HCInteriorTemplates.Loaded())
        {
            s_Instance = this;
            HCInteriorTemplatePlacement.Place(this, settings, m_Objects, -1);
            if (!FileExist("$profile:HollowCountry/interiors.json")) { Print("[HC Interiors] legacy pilot absent; template path in use"); }
        }
        m_PackCompletePending = true;
    }

    // Up to stepLimit load steps under m_PackBudget; the caller resets the budget.
    // Returns true when another call could make progress in the same slice.
    protected bool HCPackAdvance(int stepLimit)
    {
        int slice = 0;
        int status = 0;
        while (slice < stepLimit && !HCInteriorTemplates.HCLoadFinished())
        {
            status = HCInteriorTemplates.HCLoadStep(m_Config, m_PackBudget);
            if (status == 1) { return false; }
            slice = slice + 1;
        }
        return !HCInteriorTemplates.HCLoadFinished();
    }

    override void OnStop()
    {
        m_PackLoading = false;
        m_PackCompletePending = false;
        HCInteriorTemplates.HCLoadReset(true);
        super.OnStop();
    }
}
