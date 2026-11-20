// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:902/917 map Set/Contains (hash lookup).
// #52/#56 diagnostic acquisition ONLY; no module registration or startup hook.
// Installed 1.30.164289 APIs inspected: 3_Game/Global/Game.c:445-614,
// 1_Core/proto/EnSystem.c:382-531, EnString.c:184-212,
// 3_Game/tools/JsonFileLoader.c:9-90; native config ancestry example:
// 4_World/Plugins/PluginBase/PluginConfigViewer.c:GetBaseClasses.
// Config array APIs materialize whole native arrays before script can check size.
// FileMode has no exclusive-create flag; use an isolated SINGLE WRITER profile.
// Caller must confirm the actual -profiles directory is outside every Git tree.
// No geometry, proxies, asset contents, player state or eligibility is acquired.
// Actual native-030 (build 1.30.164289.70) initialized then exported Partial=1,
// Rows=0, visited=2/216 CfgWeapons, StopReason=field_type:inventorySlot.
// It did NOT record class/type. Read-only staged dta/bin.pbo config metadata
// (SHA256 2bd35c18c2a3bbb284fb5faf308249b0a4836b99353f349811649f592ba66ef1)
// orders access then Weapon_Base: inventorySlot is scalar string "" (RAP tag 0).
// This explains that failure; actual numeric CT code must come from the rerun.

class HCItemCompatibilityField
{
    string ConfigPath;
    string ReadAs;
    string ExpectedReadAs;
    int ConfigType;
    string ConfigTypeName;
    string Status = "captured";
    bool ValueCaptured;
    ref array<string> UnresolvedReasons = new array<string>;
    string ValueText;
    int ValueInt;
    float ValueFloat;
    ref array<string> TextValues = new array<string>;
    ref array<int> IntValues = new array<int>;
    ref array<float> FloatValues = new array<float>;
}

class HCItemCompatibilitySpec
{
    string ConfigPath;
    string ReadAs;
}

class HCItemCompatibilityRow
{
    string ConfigRoot;
    string ItemClass;
    string ParentClass;
    int UnresolvedFields;
    int KindVariantFields;
    ref array<string> ConfigAncestors = new array<string>;
    ref array<ref HCItemCompatibilityField> Fields = new array<ref HCItemCompatibilityField>;
}

class HCItemCompatibilityRoot
{
    string ConfigRoot;
    string ConfigRole;
    int AdvertisedChildren;
    int VisitedChildren;
    int RowsWritten;
    bool EnumerationComplete;
}

class HCItemCompatibilityHeader
{
    int SchemaVersion = 1;
    string Acquisition = "effective_native_config_all_classes_in_selected_roots";
    string ActualWorld;
    string ActualBuild;
    string ConfigProvenance;
    string RunId;
    string ProvenancePolicy = "caller_supplied_not_independently_verified";
    string FieldPolicy = "whitelist_present_only_missing_paths_omitted_no_eligibility_inference";
    string ArrayPolicy = "schema_typed_native_array_reads_element_kind_unverified_per_field";
    string BytePolicy = "conservative_four_UTF8_bytes_per_string_unit";
    string FilePolicy = "isolated_profile_single_writer_no_atomic_exclusive_create_API";
    string EnumerationOrder;
    bool FullCoverage = false;
    bool Partial = false;
    string StopReason;
    string StopClassPath;
    int UnresolvedFields;
    int KindVariantFields;
    int RowsWritten;
    int VisitedChildren;
    int MaxRows;
    int MaxBytes;
    int MaxFields;
    int MaxArrayValues;
    int MaxValueUnits;
    int MaxAncestors;
    int MaxVisitedChildren;
    int RowByteBound;
    ref array<string> SchemaFields = new array<string>;
    ref array<string> Unknowns = new array<string>;
    ref array<ref HCItemCompatibilityRoot> Roots = new array<ref HCItemCompatibilityRoot>;
}

// ExportAll's immutable manifest includes the complete bounded native index.
// Chunks contain row-plan indices and explicit non-class indices; no resume.
class HCItemCompatibilityIndexEntry
{
    int RootIndex;
    int ChildIndex;
    string ChildName;
    int ConfigType;
    string ConfigTypeName;
}

class HCItemCompatibilityChunk
{
    string ArtifactKind = "item_compatibility_chunk";
    ref HCItemCompatibilityHeader Header;
    int Sequence;
    int StartPlanIndex;
    int NextPlanIndex;
    string BoundaryReason;
    ref array<int> RowPlanIndices = new array<int>;
    ref array<int> NonClassPlanIndices = new array<int>;
}

class HCItemCompatibilityChunkWork
{
    ref HCItemCompatibilityChunk Chunk;
    ref array<string> Rows = new array<string>;
    int RowByteBound;
}

class HCItemCompatibilityChunkReference
{
    string FileName;
    int Sequence;
    int StartPlanIndex;
    int NextPlanIndex;
    int RowsWritten;
    int NonClassChildren;
    int ByteBound;
    bool ReadbackVerified;
}

class HCItemCompatibilityManifest
{
    int SchemaVersion = 1;
    string ArtifactKind = "item_compatibility_manifest";
    string IntegrityPolicy = "readback_equality_only_external_SHA256_required";
    ref HCItemCompatibilityHeader Header;
    bool FullCoverage = false;
    bool IndexPlanComplete;
    bool EnumerationComplete;
    int AdvertisedChildren;
    int ExpectedClassRows;
    int NonClassChildren;
    int CommittedChunkByteBound;
    string UncommittedFile;
    int UncommittedByteBound;
    int MaxChildren = 16384;
    int MaxChunks = 64;
    int MaxChunkBytes = 16777216;
    int MaxTotalBytes = 268435456;
    int TargetChildrenPerChunk = 512;
    int MaxManifestBytes = 8388608;
    ref array<ref HCItemCompatibilityIndexEntry> IndexPlan = new array<ref HCItemCompatibilityIndexEntry>;
    ref array<ref HCItemCompatibilityChunkReference> Chunks = new array<ref HCItemCompatibilityChunkReference>;
}

class HCItemCompatibilityAudit
{
    static const int MAX_ROWS = 65536;
    static const int MAX_BYTES = 33554432;
    static const int MIN_BYTES = 65536;
    static const int HEADER_RESERVE = 32768;
    static const int MAX_ROW_BYTES = 65536;
    static const int MAX_FIELDS = 96;
    static const int MAX_ARRAY_VALUES = 128;
    static const int MAX_VALUE_UNITS = 512;
    static const int MAX_ANCESTORS = 64;
    static const int MAX_RUN_ID = 96;
    static const int MAX_VISITED_FACTOR = 2;
    static const int ALL_MAX_CHILDREN = 16384;
    static const int ALL_MAX_CHUNKS = 64;
    static const int ALL_CHUNK_BYTES = 16777216;
    static const int ALL_TOTAL_BYTES = 268435456;
    static const int ALL_CHILD_TARGET = 512;
    static const int ALL_CHUNK_RESERVE = 65536;
    static const int ALL_PLAN_BYTES = 4194304;
    static const int ALL_MANIFEST_BYTES = 8388608;
    static const int ALL_FINAL_RESERVE = 16777216;
    protected static bool s_ExportActive;

    // Native Game.IsKindOf resolves these roots separately. Magazine extends
    // InventoryItemSuper; Ammunition_Base extends Magazine_Base. CfgAmmo is
    // projectile metadata, not proof of a craftable inventory item.
    protected static void BuildRoots(array<string> roots)
    {
        roots.Insert("CfgWeapons");
        roots.Insert("CfgVehicles");
        roots.Insert("CfgMagazines");
        roots.Insert("CfgAmmo");
    }

    static string RootRole(string root)
    {
        if (root == "CfgWeapons")
            return "weapon_config_not_inventory_eligibility";
        if (root == "CfgVehicles")
            return "vehicle_and_equipment_config_not_inventory_eligibility";
        if (root == "CfgMagazines")
            return "magazine_and_ammunition_inventory_config";
        if (root == "CfgAmmo")
            return "projectile_config_not_inventory_eligibility";
        return "unresolved_root_role";
    }

    static bool AllChildrenFit(int already, int additional)
    {
        if (already < 0 || already > ALL_MAX_CHILDREN || additional < 0)
            return false;
        return additional <= ALL_MAX_CHILDREN - already;
    }

    static bool ChunkFits(int coveredChildren, int rowByteBound, int candidateBound)
    {
        if (coveredChildren < 0 || coveredChildren >= ALL_CHILD_TARGET || rowByteBound < 0 || candidateBound < 0 || candidateBound > MAX_ROW_BYTES)
            return false;
        return rowByteBound <= ALL_CHUNK_BYTES - ALL_CHUNK_RESERVE - candidateBound;
    }

    static bool AllBytesFit(int chunkCount, int committedBound, int candidateBound)
    {
        if (chunkCount < 0 || chunkCount >= ALL_MAX_CHUNKS || committedBound < 0 || candidateBound <= 0 || candidateBound > ALL_CHUNK_BYTES)
            return false;
        return committedBound <= ALL_TOTAL_BYTES - ALL_FINAL_RESERVE - candidateBound;
    }

    static bool WindowFollows(int expectedStart, int startIndex, int nextIndex, int planned, int rows, int nonclass)
    {
        if (expectedStart < 0 || startIndex != expectedStart || nextIndex <= startIndex || nextIndex > planned || planned > ALL_MAX_CHILDREN)
            return false;
        if (rows < 0 || nonclass < 0 || rows > ALL_CHILD_TARGET || nonclass > ALL_CHILD_TARGET || nextIndex - startIndex > ALL_CHILD_TARGET)
            return false;
        return rows + nonclass == nextIndex - startIndex;
    }

    static bool AllCountsComplete(int advertised, int planned, int covered, int expectedRows, int rows, int nonclass)
    {
        if (advertised < 0 || advertised > ALL_MAX_CHILDREN || expectedRows < 0 || rows < 0 || nonclass < 0)
            return false;
        return advertised == planned && planned == covered && expectedRows == rows && rows <= covered && nonclass == covered - rows;
    }

    static bool ValidLimits(int maxRows, int maxBytes)
    {
        return maxRows >= 1 && maxRows <= MAX_ROWS && maxBytes >= MIN_BYTES && maxBytes <= MAX_BYTES;
    }

    static bool AllowedRunIdCharacter(int code)
    {
        return (code >= 48 && code <= 57) || (code >= 65 && code <= 90) || (code >= 97 && code <= 122) || code == 95 || code == 45;
    }

    static bool SafeRunId(string runId)
    {
        if (runId.Length() < 1 || runId.Length() > MAX_RUN_ID)
            return false;
        for (int tokenIndex = 0; tokenIndex < runId.Length(); tokenIndex++)
        {
            if (!AllowedRunIdCharacter(runId.Get(tokenIndex).ToAscii()))
                return false;
        }
        return true;
    }

    static int Utf8ByteBound(int units)
    {
        if (units < 0 || units > 8388607)
            return -1;
        return units * 4;
    }

    static bool FiniteNumber(float value)
    {
        return value == value && value >= -float.MAX && value <= float.MAX;
    }

    static bool FitsRowBudget(int rowCount, int byteBound, int rowByteBound, int maxRows, int maxBytes)
    {
        if (rowCount < 0 || rowCount >= maxRows || byteBound < 0 || rowByteBound < 0 || rowByteBound > MAX_ROW_BYTES)
            return false;
        return byteBound <= maxBytes - HEADER_RESERVE - rowByteBound;
    }

    static bool TypeMatches(int configType, string readAs)
    {
        if (readAs == "text")
            return configType == CT_STRING;
        if (readAs == "number")
            return configType == CT_INT || configType == CT_FLOAT;
        if (readAs == "text_array" || readAs == "int_array" || readAs == "float_array")
            return configType == CT_ARRAY;
        return false;
    }

    static string NativeTypeName(int configType)
    {
        if (configType == CT_INT)
            return "CT_INT";
        if (configType == CT_FLOAT)
            return "CT_FLOAT";
        if (configType == CT_STRING)
            return "CT_STRING";
        if (configType == CT_ARRAY)
            return "CT_ARRAY";
        if (configType == CT_CLASS)
            return "CT_CLASS";
        if (configType == CT_OTHER)
            return "CT_OTHER";
        return "UNKNOWN_NATIVE_TYPE";
    }

    static string NativeReadMode(int configType, string expectedMode)
    {
        if (configType == CT_STRING)
            return "text";
        if (configType == CT_INT || configType == CT_FLOAT)
            return "number";
        if (configType == CT_ARRAY && (expectedMode == "text_array" || expectedMode == "int_array" || expectedMode == "float_array"))
            return expectedMode;
        if (configType == CT_ARRAY)
            return "text_array";
        return "unresolved";
    }

    protected static void AddSpecs(array<ref HCItemCompatibilitySpec> schema, string paths, string readAs)
    {
        array<string> entries = new array<string>;
        paths.Split(",", entries);
        foreach (string entryPath : entries)
        {
            HCItemCompatibilitySpec entry = new HCItemCompatibilitySpec;
            entry.ConfigPath = entryPath;
            entry.ReadAs = readAs;
            schema.Insert(entry);
        }
    }

    protected static void BuildSchema(array<ref HCItemCompatibilitySpec> schema)
    {
        AddSpecs(schema, "model,ClothingTypes male,ClothingTypes female,stackedUnit,quantityType", "text");
        AddSpecs(schema, "inventorySlot,attachments,hiddenSelections", "text_array");
        AddSpecs(schema, "scope,weight,hasRailFunctionality,repairKitType,liquidContainerType,varLiquidTypeInit,varQuantityInit,varQuantityMin,varQuantityMax,varQuantityDestroyOnMin,canBeSplit,quantityBar,absorbency", "number");
        AddSpecs(schema, "repairableWithKits,itemSize,itemsCargoSize,Cargo itemsCargoSize", "int_array");
        AddSpecs(schema, "repairCosts", "float_array");
        AddSpecs(schema, "EnergyManager energyUsagePerSecond,EnergyManager switchOnAtSpawn,EnergyManager autoSwitchOff,EnergyManager autoSwitchOffWhenInCargo,EnergyManager energyAtSpawn,EnergyManager energyStorageMax,EnergyManager reduceMaxEnergyByDamageCoef,EnergyManager powerSocketsCount,EnergyManager isPassiveDevice,EnergyManager cordLength,EnergyManager plugType,EnergyManager attachmentAction,EnergyManager wetnessExposure,EnergyManager updateInterval,EnergyManager convertEnergyToQuantity", "number");
        AddSpecs(schema, "EnergyManager compatiblePlugTypes", "int_array");
    }

    protected static bool ReadAncestry(string root, HCItemCompatibilityRow row, out string error)
    {
        string currentClass = row.ItemClass;
        map<string, bool> visitedClasses = new map<string, bool>;
        visitedClasses.Set(currentClass, true);
        for (int ancestorIndex = 0; ancestorIndex <= MAX_ANCESTORS; ancestorIndex++)
        {
            string parentName;
            if (!g_Game.ConfigGetBaseName(root + " " + currentClass, parentName))
                return true;
            if (parentName == "" || visitedClasses.Contains(parentName))
            {
                error = "invalid_or_cyclic_ancestry";
                return false;
            }
            if (ancestorIndex >= MAX_ANCESTORS || parentName.Length() > MAX_VALUE_UNITS)
            {
                error = "ancestry_budget";
                return false;
            }
            if (!g_Game.ConfigIsExisting(root + " " + parentName))
            {
                error = "missing_config_parent";
                return false;
            }
            if (ancestorIndex == 0)
                row.ParentClass = parentName;
            row.ConfigAncestors.Insert(parentName);
            visitedClasses.Set(parentName, true);
            currentClass = parentName;
        }
        error = "ancestry_budget";
        return false;
    }

    protected static bool ReadField(string classPath, HCItemCompatibilitySpec spec, HCItemCompatibilityRow row, out string error)
    {
        string fieldPath = classPath + " " + spec.ConfigPath;
        if (!g_Game.ConfigIsExisting(fieldPath))
            return true;
        int fieldType = g_Game.ConfigGetType(fieldPath);
        if (row.Fields.Count() >= MAX_FIELDS)
        {
            error = "field_budget";
            return false;
        }
        HCItemCompatibilityField field = new HCItemCompatibilityField;
        field.ConfigPath = spec.ConfigPath;
        field.ExpectedReadAs = spec.ReadAs;
        field.ReadAs = NativeReadMode(fieldType, spec.ReadAs);
        field.ConfigType = fieldType;
        field.ConfigTypeName = NativeTypeName(fieldType);
        if (!TypeMatches(fieldType, spec.ReadAs))
        {
            field.Status = "kind_variant";
            field.UnresolvedReasons.Insert("schema_kind_variant");
            row.KindVariantFields++;
        }
        if (field.ReadAs == "unresolved")
        {
            field.Status = "unresolved";
            field.UnresolvedReasons.Insert("unsupported_native_kind");
            row.Fields.Insert(field);
            row.UnresolvedFields++;
            return true;
        }
        if (fieldType == CT_ARRAY)
        {
            field.UnresolvedReasons.Insert("array_element_kind_unverified");
            if (field.Status == "captured")
                field.Status = "captured_unresolved";
        }
        if (field.ReadAs == "text")
        {
            if (!g_Game.ConfigGetTextRaw(fieldPath, field.ValueText))
            {
                error = "text_read:" + spec.ConfigPath;
                return false;
            }
            if (field.ValueText.Length() > MAX_VALUE_UNITS)
            {
                error = "value_budget:" + spec.ConfigPath;
                return false;
            }
        }
        if (field.ReadAs == "number")
        {
            if (fieldType == CT_INT)
                field.ValueInt = g_Game.ConfigGetInt(fieldPath);
            else
                field.ValueFloat = g_Game.ConfigGetFloat(fieldPath);
            if (!FiniteNumber(field.ValueFloat))
            {
                error = "nonfinite_number:" + spec.ConfigPath;
                return false;
            }
        }
        if (field.ReadAs == "text_array")
        {
            g_Game.ConfigGetTextArrayRaw(fieldPath, field.TextValues);
            if (field.TextValues.Count() > MAX_ARRAY_VALUES)
            {
                error = "array_budget:" + spec.ConfigPath;
                return false;
            }
            foreach (string textValue : field.TextValues)
            {
                if (textValue.Length() > MAX_VALUE_UNITS)
                {
                    error = "value_budget:" + spec.ConfigPath;
                    return false;
                }
            }
        }
        if (field.ReadAs == "int_array")
        {
            g_Game.ConfigGetIntArray(fieldPath, field.IntValues);
            if (field.IntValues.Count() > MAX_ARRAY_VALUES)
            {
                error = "array_budget:" + spec.ConfigPath;
                return false;
            }
        }
        if (field.ReadAs == "float_array")
        {
            g_Game.ConfigGetFloatArray(fieldPath, field.FloatValues);
            if (field.FloatValues.Count() > MAX_ARRAY_VALUES)
            {
                error = "array_budget:" + spec.ConfigPath;
                return false;
            }
            foreach (float numericValue : field.FloatValues)
            {
                if (!FiniteNumber(numericValue))
                {
                    error = "nonfinite_array:" + spec.ConfigPath;
                    return false;
                }
            }
        }
        field.ValueCaptured = true;
        if (field.UnresolvedReasons.Count() > 0)
            row.UnresolvedFields++;
        row.Fields.Insert(field);
        return true;
    }

    protected static bool ReadRow(string root, string itemClass, array<ref HCItemCompatibilitySpec> schema, out string rowJson, out string error, out int unresolvedFields, out int kindVariantFields)
    {
        unresolvedFields = 0;
        kindVariantFields = 0;
        if (itemClass == "" || itemClass.Length() > MAX_VALUE_UNITS)
        {
            error = "class_name_budget";
            return false;
        }
        HCItemCompatibilityRow row = new HCItemCompatibilityRow;
        row.ConfigRoot = root;
        row.ItemClass = itemClass;
        if (!ReadAncestry(root, row, error))
            return false;
        foreach (HCItemCompatibilitySpec spec : schema)
        {
            if (!ReadField(root + " " + itemClass, spec, row, error))
                return false;
        }
        if (!JsonFileLoader<HCItemCompatibilityRow>.MakeData(row, rowJson, error, false))
            return false;
        unresolvedFields = row.UnresolvedFields;
        kindVariantFields = row.KindVariantFields;
        return true;
    }

    protected static void StopPartial(HCItemCompatibilityHeader header, string reason)
    {
        header.Partial = true;
        header.StopReason = reason;
    }

    protected static void Collect(HCItemCompatibilityHeader header, array<string> rowChunks, int maxRows, int maxBytes)
    {
        array<string> roots = new array<string>;
        BuildRoots(roots);
        array<ref HCItemCompatibilitySpec> schema = new array<ref HCItemCompatibilitySpec>;
        BuildSchema(schema);
        if (schema.Count() > MAX_FIELDS)
        {
            StopPartial(header, "schema_field_budget");
            return;
        }
        foreach (HCItemCompatibilitySpec spec : schema)
            header.SchemaFields.Insert(spec.ConfigPath);
        foreach (string rootName : roots)
        {
            HCItemCompatibilityRoot rootRecord = new HCItemCompatibilityRoot;
            rootRecord.ConfigRoot = rootName;
            rootRecord.ConfigRole = RootRole(rootName);
            header.Roots.Insert(rootRecord);
        }
        for (int rootIndex = 0; rootIndex < roots.Count(); rootIndex++)
        {
            string root = roots[rootIndex];
            HCItemCompatibilityRoot rootInfo = header.Roots[rootIndex];
            if (!g_Game.ConfigIsExisting(root) || g_Game.ConfigGetType(root) != CT_CLASS)
            {
                StopPartial(header, "missing_root:" + root);
                return;
            }
            int childCount = g_Game.ConfigGetChildrenCount(root);
            rootInfo.AdvertisedChildren = childCount;
            if (childCount < 0)
            {
                StopPartial(header, "invalid_child_count");
                return;
            }
            for (int childIndex = 0; childIndex < childCount; childIndex++)
            {
                if (header.VisitedChildren >= maxRows * MAX_VISITED_FACTOR)
                {
                    StopPartial(header, "visited_budget");
                    return;
                }
                if (header.RowsWritten >= maxRows)
                {
                    StopPartial(header, "row_budget");
                    return;
                }
                string childName;
                if (!g_Game.ConfigGetChildName(root, childIndex, childName))
                {
                    StopPartial(header, "child_name_read");
                    return;
                }
                header.VisitedChildren++;
                rootInfo.VisitedChildren++;
                if (g_Game.ConfigGetType(root + " " + childName) != CT_CLASS)
                    continue;
                string rowJson;
                string rowError;
                int unresolvedFields;
                int kindVariantFields;
                if (!ReadRow(root, childName, schema, rowJson, rowError, unresolvedFields, kindVariantFields))
                {
                    header.StopClassPath = root + " " + childName;
                    StopPartial(header, rowError);
                    return;
                }
                int rowBound = Utf8ByteBound(rowJson.Length() + 1);
                if (!FitsRowBudget(header.RowsWritten, header.RowByteBound, rowBound, maxRows, maxBytes))
                {
                    header.StopClassPath = root + " " + childName;
                    StopPartial(header, "byte_budget");
                    return;
                }
                rowChunks.Insert(rowJson);
                header.RowByteBound += rowBound;
                header.RowsWritten++;
                header.UnresolvedFields += unresolvedFields;
                header.KindVariantFields += kindVariantFields;
                rootInfo.RowsWritten++;
            }
            rootInfo.EnumerationComplete = true;
        }
    }

    protected static HCItemCompatibilityHeader NewHeader(string runId, string actualWorld, string actualBuild, string configProvenance, int maxRows, int maxBytes)
    {
        HCItemCompatibilityHeader header = new HCItemCompatibilityHeader;
        array<string> roots = new array<string>;
        BuildRoots(roots);
        header.EnumerationOrder = "native_child_index_" + string.Join("_then_", roots);
        header.RunId = runId;
        header.ActualWorld = actualWorld;
        header.ActualBuild = actualBuild;
        header.ConfigProvenance = configProvenance;
        header.MaxRows = maxRows;
        header.MaxBytes = maxBytes;
        header.MaxFields = MAX_FIELDS;
        header.MaxArrayValues = MAX_ARRAY_VALUES;
        header.MaxValueUnits = MAX_VALUE_UNITS;
        header.MaxAncestors = MAX_ANCESTORS;
        header.MaxVisitedChildren = maxRows * MAX_VISITED_FACTOR;
        header.Unknowns.Insert("live_geometry");
        header.Unknowns.Insert("model_proxies");
        header.Unknowns.Insert("beam_alignment");
        header.Unknowns.Insert("player_condition");
        header.Unknowns.Insert("runtime_inventory_eligibility");
        header.Unknowns.Insert("power_and_switch_behavior");
        header.Unknowns.Insert("liquid_transfer_eligibility");
        header.Unknowns.Insert("script_ancestry_is_not_config_ancestry");
        header.Unknowns.Insert("native_array_preallocation_size");
        return header;
    }

    protected static bool WriteFreshVerified(string destination, string payload, int maxBytes, out string error)
    {
        int byteBound = Utf8ByteBound(payload.Length());
        if (byteBound < 0 || byteBound > maxBytes)
        {
            error = "output_byte_budget";
            return false;
        }
        if (FileExist(destination))
        {
            error = "destination_exists";
            return false;
        }
        FileHandle writeHandle = OpenFile(destination, FileMode.WRITE);
        if (!writeHandle)
        {
            error = "output_open_failed";
            return false;
        }
        FPrint(writeHandle, payload);
        CloseFile(writeHandle);
        FileHandle verifyHandle = OpenFile(destination, FileMode.READ);
        if (!verifyHandle)
        {
            error = "output_readback_open_failed";
            return false;
        }
        string readback;
        ReadFile(verifyHandle, readback, maxBytes + 1);
        CloseFile(verifyHandle);
        if (readback != payload)
        {
            error = "output_readback_mismatch";
            return false;
        }
        return true;
    }

    protected static bool BuildIndexPlan(HCItemCompatibilityManifest manifest, out string error)
    {
        array<string> roots = new array<string>;
        BuildRoots(roots);
        // Read every denominator before iterating any children. No allocation
        // proportional to an unvalidated native count; all root counts survive.
        bool countsFit = true;
        for (int countRootIndex = 0; countRootIndex < roots.Count(); countRootIndex++)
        {
            HCItemCompatibilityRoot rootInfo = new HCItemCompatibilityRoot;
            rootInfo.ConfigRoot = roots[countRootIndex];
            rootInfo.ConfigRole = RootRole(rootInfo.ConfigRoot);
            manifest.Header.Roots.Insert(rootInfo);
            if (!g_Game.ConfigIsExisting(rootInfo.ConfigRoot) || g_Game.ConfigGetType(rootInfo.ConfigRoot) != CT_CLASS)
            {
                error = "missing_root:" + rootInfo.ConfigRoot;
                countsFit = false;
                continue;
            }
            rootInfo.AdvertisedChildren = g_Game.ConfigGetChildrenCount(rootInfo.ConfigRoot);
            if (!AllChildrenFit(manifest.AdvertisedChildren, rootInfo.AdvertisedChildren))
            {
                error = "native_child_budget";
                countsFit = false;
                continue;
            }
            manifest.AdvertisedChildren += rootInfo.AdvertisedChildren;
        }
        if (!countsFit || manifest.AdvertisedChildren > ALL_MAX_CHILDREN)
        {
            manifest.AdvertisedChildren = -1;
            return false;
        }
        int planBound;
        map<string, bool> classIdentities = new map<string, bool>;
        for (int planRootIndex = 0; planRootIndex < roots.Count(); planRootIndex++)
        {
            HCItemCompatibilityRoot scanRoot = manifest.Header.Roots[planRootIndex];
            for (int nativeIndex = 0; nativeIndex < scanRoot.AdvertisedChildren; nativeIndex++)
            {
                HCItemCompatibilityIndexEntry entry = new HCItemCompatibilityIndexEntry;
                entry.RootIndex = planRootIndex;
                entry.ChildIndex = nativeIndex;
                if (!g_Game.ConfigGetChildName(scanRoot.ConfigRoot, nativeIndex, entry.ChildName) || entry.ChildName == "" || entry.ChildName.Length() > MAX_VALUE_UNITS)
                {
                    error = "index_child_name_read_or_budget";
                    return false;
                }
                entry.ConfigType = g_Game.ConfigGetType(scanRoot.ConfigRoot + " " + entry.ChildName);
                entry.ConfigTypeName = NativeTypeName(entry.ConfigType);
                if (entry.ConfigType == CT_CLASS)
                {
                    string classIdentity = scanRoot.ConfigRoot + " " + entry.ChildName;
                    classIdentity.ToLower();
                    if (classIdentities.Contains(classIdentity))
                    {
                        manifest.Header.StopClassPath = classIdentity;
                        error = "duplicate_class_identity";
                        return false;
                    }
                    classIdentities.Insert(classIdentity, true);
                }
                string entryJson;
                if (!JsonFileLoader<HCItemCompatibilityIndexEntry>.MakeData(entry, entryJson, error, false))
                    return false;
                int entryBound = Utf8ByteBound(entryJson.Length() + 1);
                if (entryBound < 0 || entryBound > ALL_PLAN_BYTES - planBound)
                {
                    error = "index_plan_byte_budget";
                    return false;
                }
                manifest.IndexPlan.Insert(entry);
                planBound += entryBound;
                if (entry.ConfigType == CT_CLASS)
                    manifest.ExpectedClassRows++;
            }
        }
        manifest.IndexPlanComplete = manifest.IndexPlan.Count() == manifest.AdvertisedChildren;
        return manifest.IndexPlanComplete;
    }

    protected static HCItemCompatibilityChunkWork NewChunk(HCItemCompatibilityManifest manifest, int startIndex)
    {
        HCItemCompatibilityChunkWork work = new HCItemCompatibilityChunkWork;
        work.Chunk = new HCItemCompatibilityChunk;
        work.Chunk.Sequence = manifest.Chunks.Count();
        work.Chunk.StartPlanIndex = startIndex;
        work.Chunk.NextPlanIndex = startIndex;
        HCItemCompatibilityHeader original = manifest.Header;
        work.Chunk.Header = NewHeader(original.RunId, original.ActualWorld, original.ActualBuild, original.ConfigProvenance, ALL_CHILD_TARGET, ALL_CHUNK_BYTES);
        work.Chunk.Header.MaxVisitedChildren = ALL_CHILD_TARGET;
        work.Chunk.Header.SchemaFields = original.SchemaFields;
        return work;
    }

    protected static bool CommitChunk(HCItemCompatibilityManifest manifest, HCItemCompatibilityChunkWork work, string runDirectory, out string error)
    {
        HCItemCompatibilityChunk chunk = work.Chunk;
        int rowCount = chunk.RowPlanIndices.Count();
        int nonClassCount = chunk.NonClassPlanIndices.Count();
        if (!WindowFollows(manifest.Header.VisitedChildren, chunk.StartPlanIndex, chunk.NextPlanIndex, manifest.IndexPlan.Count(), rowCount, nonClassCount) || work.Rows.Count() != rowCount || chunk.Header.RowsWritten != rowCount)
        {
            error = "noncontiguous_chunk_or_counts";
            return false;
        }
        chunk.Header.VisitedChildren = chunk.NextPlanIndex - chunk.StartPlanIndex;
        chunk.Header.RowByteBound = work.RowByteBound;
        string chunkJson;
        if (!JsonFileLoader<HCItemCompatibilityChunk>.MakeData(chunk, chunkJson, error, false))
            return false;
        int envelopeBound = Utf8ByteBound(chunkJson.Length() + 32);
        if (envelopeBound < 0 || envelopeBound > ALL_CHUNK_RESERVE)
        {
            error = "chunk_envelope_byte_budget";
            return false;
        }
        string payload = "{\"Chunk\":" + chunkJson + ",\"Rows\":[" + string.Join(",", work.Rows) + "]}";
        int chunkBound = Utf8ByteBound(payload.Length());
        if (!AllBytesFit(manifest.Chunks.Count(), manifest.CommittedChunkByteBound, chunkBound))
        {
            error = "chunk_count_or_aggregate_byte_budget";
            return false;
        }
        int rowCursor;
        int nonClassCursor;
        for (int checkedIndex = chunk.StartPlanIndex; checkedIndex < chunk.NextPlanIndex; checkedIndex++)
        {
            if (manifest.IndexPlan[checkedIndex].ConfigType == CT_CLASS)
            {
                if (rowCursor >= rowCount || chunk.RowPlanIndices[rowCursor] != checkedIndex)
                {
                    error = "chunk_class_index_mismatch";
                    return false;
                }
                rowCursor++;
            }
            else
            {
                if (nonClassCursor >= nonClassCount || chunk.NonClassPlanIndices[nonClassCursor] != checkedIndex)
                {
                    error = "chunk_nonclass_index_mismatch";
                    return false;
                }
                nonClassCursor++;
            }
        }
        string fileName = "chunk-" + chunk.Sequence.ToString() + ".json";
        manifest.UncommittedFile = fileName;
        manifest.UncommittedByteBound = chunkBound;
        if (!WriteFreshVerified(runDirectory + "/" + fileName, payload, ALL_CHUNK_BYTES, error))
            return false;
        HCItemCompatibilityChunkReference chunkReference = new HCItemCompatibilityChunkReference;
        chunkReference.FileName = fileName;
        chunkReference.Sequence = chunk.Sequence;
        chunkReference.StartPlanIndex = chunk.StartPlanIndex;
        chunkReference.NextPlanIndex = chunk.NextPlanIndex;
        chunkReference.RowsWritten = rowCount;
        chunkReference.NonClassChildren = nonClassCount;
        chunkReference.ByteBound = chunkBound;
        chunkReference.ReadbackVerified = true;
        manifest.Chunks.Insert(chunkReference);
        manifest.CommittedChunkByteBound += chunkBound;
        manifest.Header.RowByteBound += work.RowByteBound;
        manifest.Header.VisitedChildren = chunk.NextPlanIndex;
        manifest.Header.RowsWritten += rowCount;
        manifest.Header.UnresolvedFields += chunk.Header.UnresolvedFields;
        manifest.Header.KindVariantFields += chunk.Header.KindVariantFields;
        manifest.NonClassChildren += nonClassCount;
        manifest.UncommittedFile = "";
        manifest.UncommittedByteBound = 0;
        for (int committedIndex = chunk.StartPlanIndex; committedIndex < chunk.NextPlanIndex; committedIndex++)
        {
            HCItemCompatibilityIndexEntry committed = manifest.IndexPlan[committedIndex];
            HCItemCompatibilityRoot rootSummary = manifest.Header.Roots[committed.RootIndex];
            rootSummary.VisitedChildren++;
            if (committed.ConfigType == CT_CLASS)
                rootSummary.RowsWritten++;
            rootSummary.EnumerationComplete = rootSummary.VisitedChildren == rootSummary.AdvertisedChildren;
        }
        return true;
    }
    protected static bool CollectAllChunks(HCItemCompatibilityManifest manifest, string runDirectory, out string error)
    {
        array<ref HCItemCompatibilitySpec> schema = new array<ref HCItemCompatibilitySpec>;
        BuildSchema(schema);
        HCItemCompatibilityChunkWork work = NewChunk(manifest, 0);
        for (int planIndex = 0; planIndex < manifest.IndexPlan.Count(); planIndex++)
        {
            if (work.Chunk.NextPlanIndex - work.Chunk.StartPlanIndex >= ALL_CHILD_TARGET)
            {
                work.Chunk.BoundaryReason = "child_target";
                if (!CommitChunk(manifest, work, runDirectory, error))
                    return false;
                work = NewChunk(manifest, planIndex);
            }
            HCItemCompatibilityIndexEntry entry = manifest.IndexPlan[planIndex];
            HCItemCompatibilityRoot root = manifest.Header.Roots[entry.RootIndex];
            string candidateRow;
            int candidateBound = 0;
            int unresolvedFields;
            int kindVariantFields;
            if (entry.ConfigType == CT_CLASS)
            {
                string rowError;
                if (!ReadRow(root.ConfigRoot, entry.ChildName, schema, candidateRow, rowError, unresolvedFields, kindVariantFields))
                {
                    manifest.Header.StopClassPath = root.ConfigRoot + " " + entry.ChildName;
                    work.Chunk.BoundaryReason = "source_failure";
                    if (work.Chunk.NextPlanIndex > work.Chunk.StartPlanIndex)
                    {
                        if (!CommitChunk(manifest, work, runDirectory, error))
                            return false;
                    }
                    error = rowError;
                    return false;
                }
                candidateBound = Utf8ByteBound(candidateRow.Length() + 1);
            }
            if (candidateBound < 0 || candidateBound > MAX_ROW_BYTES)
            {
                manifest.Header.StopClassPath = root.ConfigRoot + " " + entry.ChildName;
                work.Chunk.BoundaryReason = "single_row_budget";
                if (work.Chunk.NextPlanIndex > work.Chunk.StartPlanIndex)
                {
                    if (!CommitChunk(manifest, work, runDirectory, error))
                        return false;
                }
                error = "single_row_budget";
                return false;
            }
            if (!ChunkFits(work.Chunk.NextPlanIndex - work.Chunk.StartPlanIndex, work.RowByteBound, candidateBound))
            {
                work.Chunk.BoundaryReason = "byte_target";
                if (!CommitChunk(manifest, work, runDirectory, error))
                    return false;
                // Carry the already-read candidate; never rescan native prefixes.
                work = NewChunk(manifest, planIndex);
            }
            if (entry.ConfigType == CT_CLASS)
            {
                work.Rows.Insert(candidateRow);
                work.Chunk.RowPlanIndices.Insert(planIndex);
                work.RowByteBound += candidateBound;
                work.Chunk.Header.RowsWritten++;
                work.Chunk.Header.UnresolvedFields += unresolvedFields;
                work.Chunk.Header.KindVariantFields += kindVariantFields;
            }
            else
                work.Chunk.NonClassPlanIndices.Insert(planIndex);
            work.Chunk.NextPlanIndex = planIndex + 1;
        }
        if (work.Chunk.NextPlanIndex > work.Chunk.StartPlanIndex)
        {
            work.Chunk.BoundaryReason = "end_plan";
            if (!CommitChunk(manifest, work, runDirectory, error))
                return false;
        }
        return true;
    }

    protected static bool WriteFinalManifest(HCItemCompatibilityManifest manifest, string runDirectory, out string manifestPath, out string error)
    {
        manifest.Header.Partial = !manifest.EnumerationComplete;
        if (manifest.Header.Partial && manifest.Header.StopReason == "")
            manifest.Header.StopReason = "incomplete_run";
        string manifestJson;
        if (!JsonFileLoader<HCItemCompatibilityManifest>.MakeData(manifest, manifestJson, error, false))
            return false;
        manifestPath = runDirectory + "/manifest.json";
        string writeError;
        if (WriteFreshVerified(manifestPath, manifestJson, ALL_MANIFEST_BYTES, writeError))
            return true;
        // At most one fresh failure record; retain any torn primary file. The
        // aggregate ceiling reserves room for both bounded manifest attempts.
        manifest.EnumerationComplete = false;
        manifest.Header.Partial = true;
        manifest.Header.StopReason = "manifest_write:" + writeError;
        error = manifest.Header.StopReason;
        string partialJson;
        string partialError;
        if (!JsonFileLoader<HCItemCompatibilityManifest>.MakeData(manifest, partialJson, partialError, false))
            return false;
        manifestPath = runDirectory + "/manifest-partial.json";
        if (!WriteFreshVerified(manifestPath, partialJson, ALL_MANIFEST_BYTES, partialError))
            error = error + "; partial_manifest:" + partialError;
        return false;
    }

    // Fresh single run only. The immutable terminal manifest is written LAST.
    static bool ExportAll(string runId, string actualWorld, string actualBuild, string configProvenance, bool profileOutsideGitConfirmed, out string manifestPath, out string error)
    {
        manifestPath = "";
        error = "";
        if (s_ExportActive)
        {
            error = "export_already_active";
            return false;
        }
        if (!g_Game || !profileOutsideGitConfirmed || !SafeRunId(runId))
        {
            error = "invalid_request_or_profile_not_confirmed_outside_git";
            return false;
        }
        if (actualWorld.Length() < 1 || actualWorld.Length() > 128 || actualBuild.Length() < 1 || actualBuild.Length() > 128 || configProvenance.Length() < 1 || configProvenance.Length() > 1024)
        {
            error = "missing_or_oversized_caller_provenance";
            return false;
        }
        string parentDirectory = "$profile:HollowCountry/ItemCompatibilityAudit/";
        string runDirectory = parentDirectory + runId + "-all";
        if (FileExist(runDirectory))
        {
            error = "fresh_run_directory_exists";
            return false;
        }
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry"))
        {
            error = "profile_directory_create_failed";
            return false;
        }
        if (!FileExist(parentDirectory) && !MakeDirectory(parentDirectory))
        {
            error = "audit_directory_create_failed";
            return false;
        }
        s_ExportActive = true;
        if (!MakeDirectory(runDirectory))
        {
            error = "fresh_run_directory_create_failed";
            s_ExportActive = false;
            return false;
        }
        HCItemCompatibilityManifest manifest = new HCItemCompatibilityManifest;
        manifest.Header = NewHeader(runId, actualWorld, actualBuild, configProvenance, ALL_MAX_CHILDREN, ALL_TOTAL_BYTES);
        manifest.Header.MaxVisitedChildren = ALL_MAX_CHILDREN;
        array<ref HCItemCompatibilitySpec> schema = new array<ref HCItemCompatibilitySpec>;
        BuildSchema(schema);
        bool collected = false;
        if (schema.Count() > MAX_FIELDS)
            error = "schema_field_budget";
        else
        {
            foreach (HCItemCompatibilitySpec spec : schema)
                manifest.Header.SchemaFields.Insert(spec.ConfigPath);
            if (BuildIndexPlan(manifest, error))
                collected = CollectAllChunks(manifest, runDirectory, error);
        }
        manifest.EnumerationComplete = collected && manifest.IndexPlanComplete && AllCountsComplete(manifest.AdvertisedChildren, manifest.IndexPlan.Count(), manifest.Header.VisitedChildren, manifest.ExpectedClassRows, manifest.Header.RowsWritten, manifest.NonClassChildren);
        foreach (HCItemCompatibilityRoot rootSummary : manifest.Header.Roots)
        {
            rootSummary.EnumerationComplete = manifest.IndexPlanComplete && rootSummary.VisitedChildren == rootSummary.AdvertisedChildren;
            if (!rootSummary.EnumerationComplete)
                manifest.EnumerationComplete = false;
        }
        if (!manifest.EnumerationComplete)
        {
            manifest.Header.Partial = true;
            if (error == "")
                error = "incomplete_run";
            manifest.Header.StopReason = error;
        }
        bool manifestWritten = WriteFinalManifest(manifest, runDirectory, manifestPath, error);
        s_ExportActive = false;
        if (!manifestWritten)
            return false;
        if (!manifest.EnumerationComplete)
        {
            error = manifest.Header.StopReason;
            return false;
        }
        return true;
    }

    // Backward-compatible single-file export; incomplete scans remain partial.
    // A partial JSON is retained at outputPath, returns false, and carries reason.
    // Caller supplies an independently observed world/build + config hash/load-order
    // reference; these strings are provenance assertions, not measurements here.
    static bool Export(string runId, string actualWorld, string actualBuild, string configProvenance, bool profileOutsideGitConfirmed, out string outputPath, out string error, int maxRows = 32768, int maxBytes = 16777216)
    {
        outputPath = "";
        error = "";
        if (s_ExportActive)
        {
            error = "export_already_active";
            return false;
        }
        if (!g_Game || !profileOutsideGitConfirmed || !SafeRunId(runId) || !ValidLimits(maxRows, maxBytes))
        {
            error = "invalid_request_or_profile_not_confirmed_outside_git";
            return false;
        }
        if (actualWorld.Length() < 1 || actualWorld.Length() > 128 || actualBuild.Length() < 1 || actualBuild.Length() > 128 || configProvenance.Length() < 1 || configProvenance.Length() > 1024)
        {
            error = "missing_or_oversized_caller_provenance";
            return false;
        }
        string directory = "$profile:HollowCountry/ItemCompatibilityAudit/";
        string destination = directory + runId + ".json";
        if (FileExist(destination))
        {
            error = "destination_exists";
            return false;
        }
        s_ExportActive = true;
        HCItemCompatibilityHeader header = NewHeader(runId, actualWorld, actualBuild, configProvenance, maxRows, maxBytes);
        array<string> rowChunks = new array<string>;
        Collect(header, rowChunks, maxRows, maxBytes);
        string headerJson;
        if (!JsonFileLoader<HCItemCompatibilityHeader>.MakeData(header, headerJson, error, false))
        {
            s_ExportActive = false;
            return false;
        }
        int headerBound = Utf8ByteBound(headerJson.Length() + 32);
        if (headerBound < 0 || headerBound > HEADER_RESERVE)
        {
            error = "header_byte_budget";
            s_ExportActive = false;
            return false;
        }
        string payload = "{\"Header\":" + headerJson + ",\"Rows\":[" + string.Join(",", rowChunks) + "]}";
        int payloadBound = Utf8ByteBound(payload.Length());
        if (payloadBound < 0 || payloadBound > maxBytes)
        {
            error = "payload_byte_budget";
            s_ExportActive = false;
            return false;
        }
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry"))
        {
            error = "profile_directory_create_failed";
            s_ExportActive = false;
            return false;
        }
        if (!FileExist(directory) && !MakeDirectory(directory))
        {
            error = "audit_directory_create_failed";
            s_ExportActive = false;
            return false;
        }
        // Recheck immediately before the sole write. Native WRITE is not O_EXCL;
        // an unrelated process racing this isolated writer cannot be excluded.
        if (FileExist(destination))
        {
            error = "destination_exists";
            s_ExportActive = false;
            return false;
        }
        FileHandle writeHandle = OpenFile(destination, FileMode.WRITE);
        if (!writeHandle)
        {
            error = "output_open_failed";
            s_ExportActive = false;
            return false;
        }
        FPrint(writeHandle, payload);
        CloseFile(writeHandle);
        outputPath = destination;
        FileHandle verifyHandle = OpenFile(destination, FileMode.READ);
        if (!verifyHandle)
        {
            error = "output_readback_open_failed";
            s_ExportActive = false;
            return false;
        }
        string readback;
        ReadFile(verifyHandle, readback, maxBytes + 1);
        CloseFile(verifyHandle);
        s_ExportActive = false;
        if (readback != payload)
        {
            error = "output_readback_mismatch";
            return false;
        }
        if (header.Partial)
            error = header.StopReason;
        return !header.Partial;
    }
}
