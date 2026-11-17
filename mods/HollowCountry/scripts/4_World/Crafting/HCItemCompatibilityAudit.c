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
    string EnumerationOrder = "native_child_index_CfgWeapons_then_CfgVehicles";
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
    protected static bool s_ExportActive;

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
        array<string> visitedClasses = new array<string>;
        visitedClasses.Insert(currentClass);
        for (int ancestorIndex = 0; ancestorIndex <= MAX_ANCESTORS; ancestorIndex++)
        {
            string parentName;
            if (!g_Game.ConfigGetBaseName(root + " " + currentClass, parentName))
                return true;
            if (parentName == "" || visitedClasses.Find(parentName) >= 0)
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
            visitedClasses.Insert(parentName);
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
        roots.Insert("CfgWeapons");
        roots.Insert("CfgVehicles");
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

    // Return true ONLY for a readback-verified, non-partial selected-root scan.
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
