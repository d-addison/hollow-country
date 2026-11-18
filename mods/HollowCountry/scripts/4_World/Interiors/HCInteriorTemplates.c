// Atomic, startup-only admission. SHA-256 authenticity belongs to the operator
// install receipt; script checks syntax and cross-file binding, never hashes.
class HCInteriorTemplates
{
    static const string ROOT_PATH = "$profile:HollowCountry/templates/";
    protected static bool s_Attempted;
    protected static bool s_Loaded;
    protected static ref HCInteriorTemplateIndex s_Index;
    protected static ref array<ref HCInteriorTemplateClassRow> s_Classes = new array<ref HCInteriorTemplateClassRow>;
    protected static ref array<ref HCInteriorTemplate> s_Templates = new array<ref HCInteriorTemplate>;
    protected static ref array<ref HCInteriorSearchGroup> s_Groups = new array<ref HCInteriorSearchGroup>;
    protected static ref array<ref HCInteriorFurnishRow> s_Furnish = new array<ref HCInteriorFurnishRow>;
    protected static int s_Bytes;
    protected static int s_Files;
    protected static string s_Reason;
    protected static int s_MaxProps = 5;

    static bool Loaded()

    {
        return s_Loaded;
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
        foreach (HCInteriorTemplateFileBinding binding : s_Index.TemplateFiles)

        {
            if (binding.BuildingClass == cls)

            {
                return binding.Sha256;
            }
        }
        return "";
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
        foreach (HCInteriorTemplateClassRow row : s_Classes)

        {
            if (row.BuildingClass == cls)

            {
                return row;
            }
        }
        return null;
    }

    static HCInteriorTemplate FindTemplate(string cls)

    {
        foreach (HCInteriorTemplate row : s_Templates)

        {
            if (row.BuildingClass == cls)

            {
                return row;
            }
        }
        return null;
    }

    static HCInteriorSearchGroup FindGroup(string id)

    {
        foreach (HCInteriorSearchGroup row : s_Groups)

        {
            if (row.Id == id)

            {
                return row;
            }
        }
        return null;
    }

    static bool Refuse(string reason)

    {
        if (s_Reason != "")

        {
            return false;
        }
        s_Loaded = false;
        s_Index = null;
        s_Classes.Clear();
        s_Templates.Clear();
        s_Groups.Clear();
        s_Furnish.Clear();
        s_Reason = reason;
        Print("[HC Interiors] templates refused: " + reason);
        return false;
    }

    static string Read(string path, string kind)

    {
        FileHandle file = OpenFile(path, FileMode.READ);
        if (!file)

        {
            return "";
        }
        string content;
        int count = ReadFile(file, content, 32768);
        CloseFile(file);
        int length = content.Length();
        // First file of each kind: byte/length semantics await native evidence.
        if (kind == "index" || kind == "classes0" || kind == "template0" || kind == "furnish0" || kind == "groups0")

        {
            Print("[HC Interiors] template ReadFile " + kind + " count=" + count.ToString() + " length=" + length.ToString());
        }
        if (count != content.Length() || count < 1 || count > 32767)

        {
            return "";
        }
        return content;
    }

    static string ReadStrict(string fileName, string schema, string kind)

    {
        if (s_Files >= 610)

        {
            Refuse("file_cap");
            return "";
        }
        string raw = Read(ROOT_PATH + fileName, kind);
        if (raw.Length() < 1 || raw.Length() > 32767)

        {
            Refuse("file_size_or_read:" + fileName);
            return "";
        }
        s_Files = s_Files + 1;
        s_Bytes = s_Bytes + raw.Length();
        if (s_Bytes > 20971520)

        {
            Refuse("pack_size");
            return "";
        }
        string nativeText = HCInteriorTemplatesStrict.NativeText(raw, schema);
        if (nativeText == "")

        {
            Refuse("strict_keys_or_json:" + fileName);
        }
        return nativeText;
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

    static bool FilesValid(array<ref HCInteriorTemplateFile> rows, string prefix, int cap)

    {
        if (!rows || rows.Count() > cap)

        {
            return false;
        }
        int number = 0;
        foreach (HCInteriorTemplateFile row : rows)

        {
            if (!row || row.FileName != Numbered(prefix, number, 3) || !HCSearchRules.PinValid(row.Sha256))

            {
                return false;
            }
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
        if (world != index.WorldName || !HCInteriorTemplatesStrict.Hex(index.PackId, 32) || !HCSearchRules.PinValid(index.SourcePin))

        {
            return false;
        }
        if (!index.Sources || index.Sources.Count() < 8 || index.Sources.Count() > 520)

        {
            return false;
        }
        string requiredSources = "mapgroupproto mapgrouppos types cfgspawnabletypes cfglimitsdefinition generator search-generator";
        array<string> sourceNames = new array<string>();
        requiredSources.Split(" ", sourceNames);
        foreach (string requiredSource : sourceNames)

        {
            if (!HCSearchRules.PinValid(index.Sources.Get(requiredSource)))

            {
                return false;
            }
        }
        int sourceIndex = 0;
        while (sourceIndex < index.Sources.Count())

        {
            if (!HCInteriorTemplatesStrict.SourceName(index.Sources.GetKey(sourceIndex)) || !HCSearchRules.PinValid(index.Sources.GetElement(sourceIndex)))

            {
                return false;
            }
            sourceIndex = sourceIndex + 1;
        }
        if (!FilesValid(index.ClassFiles, "classes-", 16) || index.ClassFiles.Count() < 1 || !FilesValid(index.FurnishFiles, "furnish-", 16) || !FilesValid(index.GroupFiles, "search-groups-", 64))

        {
            return false;
        }
        if (!index.TemplateFiles || index.TemplateFiles.Count() > 512)

        {
            return false;
        }
        int number = 0;
        array<string> seen = new array<string>();
        foreach (HCInteriorTemplateFileBinding binding : index.TemplateFiles)

        {
            if (!binding || binding.FileName != Numbered("t-", number, 4) || !HCSearchRules.PinValid(binding.Sha256) || !HCSearchRules.TextValid(binding.BuildingClass, 128) || seen.Find(binding.BuildingClass) >= 0)

            {
                return false;
            }
            seen.Insert(binding.BuildingClass);
            number = number + 1;
        }
        return 1 + index.ClassFiles.Count() + index.TemplateFiles.Count() + index.FurnishFiles.Count() + index.GroupFiles.Count() <= 610;
    }

    // Each pack class must be a House class the engine knows. The engine has thousands of House
    // classes (walls, wrecks, ruins); the pack covers only the ones it lists, so it is not an
    // exact census of CfgVehicles and the config is read per listed class, never enumerated.
    static bool EngineHouse(string cls)

    {
        return GetGame().ConfigIsExisting("CfgVehicles " + cls) && GetGame().IsKindOf(cls, "House");
    }

    static bool ClassesValid()

    {
        if (s_Classes.Count() < 1)

        {
            return false;
        }
        foreach (HCInteriorTemplateClassRow row : s_Classes)

        {
            if (!row || !EngineHouse(row.BuildingClass))

            {
                return false;
            }
        }
        return true;
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
        return HCInteriorCatalog.SearchType(type) || type == "StaticObj_Furniture_kitchen_chair_a" || type == "StaticObj_Furniture_PaperBox_01_small_closed" || type == "StaticObj_Furniture_PaperBox_01_small_ransacked";
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
        // Sort a private copy once; preserve authored group order for consumers.
        // Native array.Sort: 1_Core/proto/EnScript.c:493 (1.30.164289).
        array<string> sortedValues = new array<string>();
        foreach (string value : values)

        {
            if (!HCSearchRules.TextValid(value, 128))

            {
                return false;
            }
            sortedValues.Insert(value);
        }
        sortedValues.Sort();
        int valueIndex = 1;
        while (valueIndex < sortedValues.Count())
        {
            if (sortedValues[valueIndex] == sortedValues[valueIndex - 1])
            {
                return false;
            }
            valueIndex = valueIndex + 1;
        }
        return true;
    }

    static bool TemplateValid(HCInteriorTemplate templateRow)

    {
        if (!templateRow || templateRow.SchemaVersion != 2 || !HCSearchRules.TextValid(templateRow.TemplateId, 128) || !templateRow.Box || !BoxValid(templateRow.Box.Min, templateRow.Box.Max))

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
            if (!evidence || evidence.Kind != "native-room-survey-v1" || !HCInteriorTemplatesStrict.Hex(evidence.RunId, 32) || !HCSearchRules.PinValid(evidence.Sha256) || s_Index.Sources.Get("census-" + evidence.RunId) != evidence.Sha256 || runs.Find(evidence.RunId) >= 0)

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
            if (!roomRow || roomRow.Id < 1 || roomIds.Find(roomRow.Id) >= 0 || !HCSearchRules.TextValid(roomRow.Label, 128) || !BoxValid(roomRow.Min, roomRow.Max) || !Inside(roomRow.Min, templateRow.Box.Min, templateRow.Box.Max) || !Inside(roomRow.Max, templateRow.Box.Min, templateRow.Box.Max) || !VectorValid(roomRow.Anchor, 512) || !Inside(roomRow.Anchor, roomRow.Min, roomRow.Max) || !(roomRow.FloorY >= roomRow.Min[1] && roomRow.FloorY <= roomRow.Max[1]) || roomRow.Cells < 1)

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
        if (!templateRow.PropSlots || templateRow.PropSlots.Count() > s_MaxProps || (classRow.Furniture == "covered" && templateRow.PropSlots.Count() < 1))

        {
            return false;
        }
        array<int> propIds = new array<int>();
        foreach (HCInteriorTemplatePropSlot propRow : templateRow.PropSlots)

        {
            if (!propRow || propRow.Id < 1 || propIds.Find(propRow.Id) >= 0 || !HCSearchRules.TextValid(propRow.Type, 128) || !PropType(propRow.Type) || !GetGame().ConfigIsExisting("CfgVehicles " + propRow.Type) || !SlotClear(templateRow, propRow) || !Texts(propRow.History, 1, 2))

            {
                return false;
            }
            foreach (string history : propRow.History)

            {
                if (history != "family" && history != "ransacked")

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

    static bool FurnishValid()

    {
        array<int> slots = new array<int>();
        array<string> instances = new array<string>();
        int props = 0;
        foreach (HCInteriorFurnishRow row : s_Furnish)

        {
            HCInteriorTemplate templateRow = FindTemplate(row.BuildingClass);
            HCInteriorTemplateClassRow classRow = FindClass(row.BuildingClass);
            if (!templateRow || !classRow || classRow.Furniture != "covered" || row.SlotId < 0 || row.SlotId >= 1500 || slots.Find(row.SlotId) >= 0 || !VectorValid(row.Position, 20000) || !(row.Yaw >= -360 && row.Yaw <= 360) || !row.Props || row.Props.Count() < 1 || row.Props.Count() > 5 || (row.History != "family" && row.History != "ransacked"))

            {
                return false;
            }
            string key = row.BuildingClass + "_" + HCInteriorRules.TransformKey(AsVector(row.Position), Vector(0, 0, 0));
            if (instances.Find(key) >= 0)

            {
                return false;
            }
            instances.Insert(key);
            slots.Insert(row.SlotId);
            array<int> ids = new array<int>();
            foreach (int id : row.Props)

            {
                HCInteriorTemplatePropSlot propRow = Prop(templateRow, id);
                if (!propRow || propRow.History.Find(row.History) < 0 || ids.Find(id) >= 0)

                {
                    return false;
                }
                ids.Insert(id);
                props = props + 1;
                if (props > 1500)

                {
                    return false;
                }
            }
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

    static void EnsureLoaded(HCInteriorConfig legacy, int maxProps = 5)

    {
        if (s_Attempted)

        {
            return;
        }
        s_Attempted = true;
        if (maxProps < 1 || maxProps > 20)

        {
            Refuse("prop_setting");
            return;
        }
        s_MaxProps = maxProps;
        string error;
        string content = ReadStrict("index.json", "index", "index");
        if (content == "")

        {
            return;
        }
        HCInteriorTemplateIndex index = new HCInteriorTemplateIndex;
        if (!JsonFileLoader<HCInteriorTemplateIndex>.LoadData(content, index, error) || !IndexValid(index))

        {
            Refuse("index_or_pin");
            return;
        }
        s_Index = index;
        int chunk = 0;
        foreach (HCInteriorTemplateFile classFile : index.ClassFiles)

        {
            content = ReadStrict(classFile.FileName, "classes", "classes" + chunk.ToString());
            HCInteriorTemplateClasses classes = new HCInteriorTemplateClasses;
            if (content == "" || !JsonFileLoader<HCInteriorTemplateClasses>.LoadData(content, classes, error) || classes.SchemaVersion != 2 || classes.Chunk != chunk || !classes.Rows || classes.Rows.Count() < 1 || classes.Rows.Count() > 160)

            {
                Refuse("classes_chunk");
                return;
            }
            foreach (HCInteriorTemplateClassRow classRow : classes.Rows)

            {
                if (!classRow || !HCSearchRules.TextValid(classRow.BuildingClass, 128) || !Disposition(classRow.Rooms) || !Disposition(classRow.Furniture) || !Disposition(classRow.Search) || FindClass(classRow.BuildingClass) || s_Classes.Count() >= 2048)

                {
                    Refuse("class_row");
                    return;
                }
                s_Classes.Insert(classRow);
            }
            chunk = chunk + 1;
        }
        if (!ClassesValid())

        {
            Refuse("house_denominator");
            return;
        }
        if (LegacyConflict(legacy))

        {
            Refuse("rooms_conflict");
            return;
        }
        chunk = 0;
        foreach (HCInteriorTemplateFile groupFile : index.GroupFiles)

        {
            content = ReadStrict(groupFile.FileName, "groups", "groups" + chunk.ToString());
            HCInteriorTemplateGroups groups = new HCInteriorTemplateGroups;
            if (content == "" || !JsonFileLoader<HCInteriorTemplateGroups>.LoadData(content, groups, error) || groups.SchemaVersion != 2 || groups.Chunk != chunk || !groups.Groups || groups.Groups.Count() < 1 || groups.Groups.Count() > 512)

            {
                Refuse("groups_chunk");
                return;
            }
            foreach (HCInteriorSearchGroup groupRow : groups.Groups)

            {
                if (!groupRow || !HCSearchRules.TextValid(groupRow.Id, 128) || FindGroup(groupRow.Id) || !Container(groupRow.Container) || !Texts(groupRow.Usages, 0, 8192) || !Texts(groupRow.Categories, 1, 8192) || !Texts(groupRow.Tags, 0, 8192) || !Texts(groupRow.Items, 1, 1024) || s_Groups.Count() >= 32768)

                {
                    Refuse("group_row");
                    return;
                }
                s_Groups.Insert(groupRow);
            }
            chunk = chunk + 1;
        }
        chunk = 0;
        foreach (HCInteriorTemplateFileBinding templateFile : index.TemplateFiles)

        {
            content = ReadStrict(templateFile.FileName, "template", "template" + chunk.ToString());
            HCInteriorTemplate templateRow = new HCInteriorTemplate;
            if (content == "" || !JsonFileLoader<HCInteriorTemplate>.LoadData(content, templateRow, error) || templateRow.BuildingClass != templateFile.BuildingClass || FindTemplate(templateRow.BuildingClass) || !TemplateValid(templateRow))

            {
                Refuse("template_or_evidence_pin");
                return;
            }
            s_Templates.Insert(templateRow);
            chunk = chunk + 1;
        }
        foreach (HCInteriorTemplateClassRow checkRow : s_Classes)

        {
            if (Covered(checkRow) != (FindTemplate(checkRow.BuildingClass) != null))

            {
                Refuse("template_coverage");
                return;
            }
        }
        chunk = 0;
        foreach (HCInteriorTemplateFile furnishFile : index.FurnishFiles)

        {
            content = ReadStrict(furnishFile.FileName, "furnish", "furnish" + chunk.ToString());
            HCInteriorTemplateFurnish furnish = new HCInteriorTemplateFurnish;
            if (content == "" || !JsonFileLoader<HCInteriorTemplateFurnish>.LoadData(content, furnish, error) || furnish.SchemaVersion != 2 || furnish.Chunk != chunk || !furnish.Rows || furnish.Rows.Count() < 1 || furnish.Rows.Count() > 128)

            {
                Refuse("furnish_chunk");
                return;
            }
            foreach (HCInteriorFurnishRow furnishRow : furnish.Rows)

            {
                if (!furnishRow || s_Furnish.Count() >= 1500)

                {
                    Refuse("furnish_rows");
                    return;
                }
                s_Furnish.Insert(furnishRow);
            }
            chunk = chunk + 1;
        }
        if (!FurnishValid())

        {
            Refuse("furnish_binding_or_budget");
            return;
        }
        s_Loaded = true;
        Print("[HC Interiors] templates provisional; native clearance/path/audio/replication acceptance pending; files=" + s_Files.ToString() + " bytes=" + s_Bytes.ToString());
    }
}
