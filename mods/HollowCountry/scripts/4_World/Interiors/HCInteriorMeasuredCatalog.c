// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:866/902/917 map Get/Set/Contains.
class HCInteriorSourceLookup
{
    ref map<string, string> Left;
    ref map<string, string> Right;
}

// Candidate import only. Operator assertions are NOT native cryptographic
// verification, measured fit, CE ownership, or production acceptance.
class HCInteriorMeasuredCatalogBinding
{
    House HouseObject;
    vector Position;
    vector Orientation;
    string RecordSha256;
    ref HCInteriorMeasuredCatalogRecord Record;
}

class HCInteriorMeasuredCatalog
{
    static const string PROFILE_PATH = "$profile:HollowCountry/interiors-measured-profile.json";
    static const string DATA_ROOT = "$profile:HollowCountry/measured-interiors/";
    protected static bool s_Attempted = false;
    protected static bool s_Requested = false;
    protected static int s_WorldKey = -1;
    protected static ref HCInteriorMeasuredCatalogBinding s_Binding;

    static void MeasuredClear()
    {
        s_Binding = null;
        s_Attempted = false;
        s_Requested = false;
        s_WorldKey = -1;
    }

    static bool MeasuredRequested()
    {
        return s_Requested;
    }

    // No I/O: startup loads the optional legacy profile before template admission.
    static string MeasuredClaimedClass()
    {
        if (!s_Binding || !s_Binding.Record)
        {
            return "";
        }
        return s_Binding.Record.BuildingClass;
    }

    // Inspected ReadFile accepts string buffers and returns bytes read. Fixed
    // paths only; no directory enumeration, arbitrary artifact reads or writes.
    static string MeasuredRead(string path, int limit)
    {
        if (limit < 1 || limit > 262144)
        {
            return "";
        }
        FileHandle file = OpenFile(path, FileMode.READ);
        if (!file)
        {
            return "";
        }
        string content;
        int count = ReadFile(file, content, limit + 1);
        CloseFile(file);
        if (count < 1 || count > limit || content.Length() < 1 || content.Length() > limit)
        {
            return "";
        }
        return content;
    }

    static string MeasuredEngineBuild()
    {
        string build;
        GetGame().GetVersion(build);
        return build;
    }

    // Both texts must be admitted by the one shared matcher (pinned base or the full
    // native version observed in runs 047/048). Future suffixes need qualification there.
    static bool MeasuredBuildMatches(string actual, string pinned)
    {
        return HCBuildIdentity.Matches(pinned) && HCBuildIdentity.Matches(actual);
    }

    static bool MeasuredBound(float value, float low, float high)
    {
        // Ordered comparisons also reject NaN and infinities.
        return value >= low && value <= high;
    }

    static bool MeasuredVector(array<float> value, float limit)
    {
        if (!value || value.Count() != 3)
        {
            return false;
        }
        foreach (float component : value)
        {
            if (!MeasuredBound(component, -limit, limit))
            {
                return false;
            }
        }
        return true;
    }

    static vector MeasuredAsVector(array<float> value)
    {
        return Vector(value[0], value[1], value[2]);
    }

    static bool MeasuredSameVector(array<float> left, array<float> right)
    {
        if (!left || !right || left.Count() != 3 || right.Count() != 3)
        {
            return false;
        }
        return left[0] == right[0] && left[1] == right[1] && left[2] == right[2];
    }

    static bool MeasuredHash(string value)
    {
        if (value.Length() != 64)
        {
            return false;
        }
        bool nonzero = false;
        int i = 0;
        while (i < value.Length())
        {
            string ch = value.Get(i);
            int code = ch.ToAscii();
            if (!((code >= 48 && code <= 57) || (code >= 97 && code <= 102)))
            {
                return false;
            }
            if (code != 48)
            {
                nonzero = true;
            }
            i = i + 1;
        }
        return nonzero;
    }

    static bool MeasuredText(string value, int low, int high)
    {
        string trimmed = value.Trim();
        if (trimmed.Length() < low || value.Length() > high)
        {
            return false;
        }
        int i = 0;
        while (i < value.Length())
        {
            string ch = value.Get(i);
            if (ch.ToAscii() < 32)
            {
                return false;
            }
            i = i + 1;
        }
        trimmed.ToLower();
        return trimmed != "todo" && trimmed != "unknown" && trimmed != "placeholder" && trimmed != "unmeasured" && trimmed != "n/a";
    }

    static bool MeasuredIdentifier(string value)
    {
        if (value.Length() > 64 || !MeasuredText(value, 1, 64))
        {
            return false;
        }
        int i = 0;
        while (i < value.Length())
        {
            string ch = value.Get(i);
            int code = ch.ToAscii();
            if (i == 0 && !(code >= 97 && code <= 122))
            {
                return false;
            }
            if (!((code >= 97 && code <= 122) || (code >= 48 && code <= 57) || code == 45))
            {
                return false;
            }
            i = i + 1;
        }
        return true;
    }

    static bool MeasuredPortablePath(string value)
    {
        if (value.Length() > 160 || !MeasuredText(value, 1, 160))
        {
            return false;
        }
        int i = 0;
        while (i < value.Length())
        {
            string ch = value.Get(i);
            int code = ch.ToAscii();
            // Native Split drops empty components; reject them beforehand.
            if (code == 47)
            {
                if (i == 0 || i + 1 == value.Length())
                {
                    return false;
                }
                int previousIndex = i - 1;
                string previous = value.Get(previousIndex);
                if (previous.ToAscii() == 47)
                {
                    return false;
                }
            }
            if (!((code >= 65 && code <= 90) || (code >= 97 && code <= 122) || (code >= 48 && code <= 57) || code == 95 || code == 46 || code == 47 || code == 45))
            {
                return false;
            }
            i = i + 1;
        }
        array<string> parts = new array<string>();
        value.Split("/", parts);
        if (parts.Count() < 1 || parts.Count() > 80)
        {
            return false;
        }
        foreach (string part : parts)
        {
            if (part.Length() == 0 || part == "." || part == "..")
            {
                return false;
            }
            int last = part.Length() - 1;
            if (part.Get(last) == ".")
            {
                return false;
            }
            array<string> extensions = new array<string>();
            part.Split(".", extensions);
            string stem = extensions[0];
            stem.ToLower();
            if (stem == "con" || stem == "prn" || stem == "aux" || stem == "nul")
            {
                return false;
            }
            if (stem.Length() == 4)
            {
                string prefix = stem.Substring(0, 3);
                string suffix = stem.Substring(3, 1);
                int digit = suffix.ToAscii();
                if ((prefix == "com" || prefix == "lpt") && digit >= 48 && digit <= 57)
                {
                    return false;
                }
            }
        }
        return true;
    }

    static int MeasuredDecimal(string value, int begin, int count)
    {
        if (begin < 0 || count < 1 || begin + count > value.Length())
        {
            return -1;
        }
        HCTextWindow digits = new HCTextWindow(value);
        int result = 0;
        int i = begin;
        while (i < begin + count)
        {
            string ch = digits.At(i);
            int code = ch.ToAscii();
            if (code < 48 || code > 57)
            {
                return -1;
            }
            result = result * 10 + code - 48;
            i = i + 1;
        }
        return result;
    }

    // Deliberately narrow ISO-8601 timestamp subset with an explicit timezone.
    static bool MeasuredTimestamp(string value)
    {
        if (value.Length() < 20 || value.Length() > 40)
        {
            return false;
        }
        if (value.Get(4) != "-" || value.Get(7) != "-" || value.Get(10) != "T" || value.Get(13) != ":" || value.Get(16) != ":")
        {
            return false;
        }
        int year = MeasuredDecimal(value, 0, 4);
        int month = MeasuredDecimal(value, 5, 2);
        int day = MeasuredDecimal(value, 8, 2);
        int hour = MeasuredDecimal(value, 11, 2);
        int minute = MeasuredDecimal(value, 14, 2);
        int second = MeasuredDecimal(value, 17, 2);
        if (year < 1 || month < 1 || month > 12 || hour < 0 || hour > 23 || minute < 0 || minute > 59 || second < 0 || second > 59)
        {
            return false;
        }
        int days = 31;
        if (month == 4 || month == 6 || month == 9 || month == 11)
        {
            days = 30;
        }
        if (month == 2)
        {
            days = 28;
            if (year % 4 == 0 && (year % 100 != 0 || year % 400 == 0))
            {
                days = 29;
            }
        }
        if (day < 1 || day > days)
        {
            return false;
        }
        int index = 19;
        if (value.Get(index) == ".")
        {
            index = index + 1;
            int first = index;
            while (index < value.Length())
            {
                string ch = value.Get(index);
                int code = ch.ToAscii();
                if (code < 48 || code > 57)
                {
                    break;
                }
                index = index + 1;
            }
            if (index == first)
            {
                return false;
            }
        }
        if (index >= value.Length())
        {
            return false;
        }
        if (value.Get(index) == "Z")
        {
            return index + 1 == value.Length();
        }
        if (index + 6 != value.Length() || (value.Get(index) != "+" && value.Get(index) != "-"))
        {
            return false;
        }
        int separator = index + 3;
        if (value.Get(separator) != ":")
        {
            return false;
        }
        int offsetHour = MeasuredDecimal(value, index + 1, 2);
        int offsetMinute = MeasuredDecimal(value, index + 4, 2);
        return offsetHour >= 0 && offsetHour <= 23 && offsetMinute >= 0 && offsetMinute <= 59;
    }

    // Exact JSON schemas. Arrays are denoted by @; scalar token types are
    // checked before native deserialization, including integer versus boolean.
    static string MeasuredKeys(string schema)
    {
        if (schema == "profile")
        {
            return "SchemaVersion EnableTrustedExperiment TrustedExternalValidation WorldName Build TrustedAddonSha256 TrustedValidatorSha256 SourceSha256 ExpectedRecordText ExpectedCandidateText ExpectedPolicyText ExpectedReportText";
        }
        if (schema == "record")
        {
            return "SchemaVersion Synthetic Context SourceSha256 BuildingType CatalogVersion Layouts Observations Policy";
        }
        if (schema == "context")
        {
            return "World Build NativeScriptsSha256 SurveyId BuildingPosition BuildingOrientation AssetPboSha256 Operator MeasuredAt Method CoordinateBasis BuildObservation AssetObservation";
        }
        if (schema == "sources")
        {
            return "HCInteriorCatalog.c HCInteriorRules.c HCInteriorStore.c";
        }
        if (schema == "assets")
        {
            return "structures_residential structures_furniture";
        }
        if (schema == "layout")
        {
            return "Id History Props Survey";
        }
        if (schema == "candidate-layout")
        {
            return "Id History Props";
        }
        if (schema == "prop")
        {
            return "Type Position Orientation Searchable SearchPoint";
        }
        if (schema == "survey")
        {
            return "Bounds Props Stairs DoorObservation StairObservation MinimumClearanceMetres Keepouts";
        }
        if (schema == "box")
        {
            return "Min Max";
        }
        if (schema == "measured-prop")
        {
            return "Index Room Bounds Observation";
        }
        if (schema == "keepout")
        {
            return "Id Kind Bounds";
        }
        if (schema == "observation")
        {
            return "Path Sha256 Kind";
        }
        if (schema == "policy")
        {
            return "ItemGroups Rules Limits";
        }
        if (schema == "group")
        {
            return "Id Items";
        }
        if (schema == "rule")
        {
            return "LayoutId Room History Risk ItemGroups EmptyAllowed MaxItems Selection Condition Storage Observation Rationale";
        }
        if (schema == "limits")
        {
            return "Slots Rag Battery9V";
        }
        if (schema == "candidate")
        {
            return "SchemaVersion CatalogVersion BuildingType Synthetic RecordSha256 Layouts";
        }
        if (schema == "report")
        {
            return "schema status synthetic runtime_loader_wired production_accepted record_sha256 source_sha256 observations world build candidate_sha256 pending";
        }
        if (schema == "files")
        {
            return "measured-record.json interior-layouts.candidate.json context-policy.candidate.json";
        }
        return "";
    }

    static string MeasuredChild(string schema, string key)
    {
        if (key == "SchemaVersion" || key == "CatalogVersion" || key == "Index" || key == "Slots" || key == "Rag" || key == "Battery9V" || key == "MaxItems" || key == "schema")
        {
            return "integer";
        }
        if (key == "EnableTrustedExperiment" || key == "TrustedExternalValidation" || key == "Synthetic" || key == "Searchable" || key == "EmptyAllowed" || key == "synthetic" || key == "runtime_loader_wired" || key == "production_accepted")
        {
            return "boolean";
        }
        if (key == "SourceSha256" || key == "source_sha256")
        {
            return "sources";
        }
        if (key == "AssetPboSha256")
        {
            return "assets";
        }
        if (key == "candidate_sha256")
        {
            return "files";
        }
        if (key == "Context")
        {
            return "context";
        }
        if (key == "Policy")
        {
            return "policy";
        }
        if (key == "Limits")
        {
            return "limits";
        }
        if (key == "Survey")
        {
            return "survey";
        }
        if (key == "Bounds")
        {
            return "box";
        }
        if (key == "Layouts")
        {
            if (schema == "candidate")
            {
                return "@candidate-layout";
            }
            return "@layout";
        }
        if (key == "Props")
        {
            if (schema == "survey")
            {
                return "@measured-prop";
            }
            return "@prop";
        }
        if (key == "Keepouts")
        {
            return "@keepout";
        }
        if (key == "Observations" || key == "observations")
        {
            return "@observation";
        }
        if (key == "ItemGroups")
        {
            if (schema == "policy")
            {
                return "@group";
            }
            return "@text";
        }
        if (key == "Rules")
        {
            return "@rule";
        }
        if (key == "Items" || key == "pending")
        {
            return "@text";
        }
        if (key == "Position" || key == "Orientation" || key == "SearchPoint" || key == "BuildingPosition" || key == "BuildingOrientation" || key == "Min" || key == "Max")
        {
            return "@number";
        }
        if (key == "MinimumClearanceMetres")
        {
            return "number";
        }
        return "text";
    }

    static int MeasuredCode(HCInteriorMeasuredCatalogCursor cursor)
    {
        if (cursor.Index >= cursor.Content.Length())
        {
            return -1;
        }
        string ch = cursor.HCAt(cursor.Index);
        return ch.ToAscii();
    }

    static void MeasuredSpace(HCInteriorMeasuredCatalogCursor cursor)
    {
        int code = MeasuredCode(cursor);
        while (code == 32 || code == 9 || code == 10 || code == 13)
        {
            cursor.Index = cursor.Index + 1;
            code = MeasuredCode(cursor);
        }
    }

    static bool MeasuredTake(HCInteriorMeasuredCatalogCursor cursor, int expected)
    {
        MeasuredSpace(cursor);
        if (MeasuredCode(cursor) != expected)
        {
            return false;
        }
        cursor.Index = cursor.Index + 1;
        return true;
    }

    static string MeasuredString(HCInteriorMeasuredCatalogCursor cursor, bool key)
    {
        if (!MeasuredTake(cursor, 34))
        {
            cursor.Failed = true;
            return "";
        }
        int begin = cursor.Index;
        while (cursor.Index < cursor.Content.Length())
        {
            int code = MeasuredCode(cursor);
            if (code == 34)
            {
                int length = cursor.Index - begin;
                string result = cursor.HCRange(begin, length);
                cursor.Index = cursor.Index + 1;
                return result;
            }
            if (code < 32 || (key && code > 126))
            {
                cursor.Failed = true;
                return "";
            }
            if (code == 92)
            {
                if (key)
                {
                    cursor.Failed = true;
                    return "";
                }
                cursor.Index = cursor.Index + 1;
                code = MeasuredCode(cursor);
                if (code == 117)
                {
                    int end = cursor.Index + 5;
                    cursor.Index = cursor.Index + 1;
                    while (cursor.Index < end)
                    {
                        code = MeasuredCode(cursor);
                        if (!((code >= 48 && code <= 57) || (code >= 65 && code <= 70) || (code >= 97 && code <= 102)))
                        {
                            cursor.Failed = true;
                            return "";
                        }
                        cursor.Index = cursor.Index + 1;
                    }
                    continue;
                }
                if (code != 34 && code != 92 && code != 47 && code != 98 && code != 102 && code != 110 && code != 114 && code != 116)
                {
                    cursor.Failed = true;
                    return "";
                }
            }
            cursor.Index = cursor.Index + 1;
        }
        cursor.Failed = true;
        return "";
    }

    static bool MeasuredValue(HCInteriorMeasuredCatalogCursor cursor, string schema, int depth)
    {
        cursor.Nodes = cursor.Nodes + 1;
        if (cursor.Failed || depth > 12 || cursor.Nodes > 4096)
        {
            return false;
        }
        MeasuredSpace(cursor);
        if (schema == "text")
        {
            MeasuredString(cursor, false);
            return !cursor.Failed;
        }
        if (schema == "boolean")
        {
            int remaining = cursor.Content.Length() - cursor.Index;
            if (remaining >= 4)
            {
                string yes = cursor.HCRange(cursor.Index, 4);
                if (yes == "true")
                {
                    cursor.Index = cursor.Index + 4;
                    return true;
                }
            }
            if (remaining >= 5)
            {
                string no = cursor.HCRange(cursor.Index, 5);
                if (no == "false")
                {
                    cursor.Index = cursor.Index + 5;
                    return true;
                }
            }
            return false;
        }
        if (schema == "integer" || schema == "number")
        {
            int begin = cursor.Index;
            if (MeasuredCode(cursor) == 45)
            {
                cursor.Index = cursor.Index + 1;
            }
            int code = MeasuredCode(cursor);
            if (code < 48 || code > 57)
            {
                return false;
            }
            if (code == 48)
            {
                cursor.Index = cursor.Index + 1;
            }
            else
            {
                while (code >= 48 && code <= 57)
                {
                    cursor.Index = cursor.Index + 1;
                    code = MeasuredCode(cursor);
                }
            }
            if (schema == "number" && MeasuredCode(cursor) == 46)
            {
                cursor.Index = cursor.Index + 1;
                int fraction = cursor.Index;
                code = MeasuredCode(cursor);
                while (code >= 48 && code <= 57)
                {
                    cursor.Index = cursor.Index + 1;
                    code = MeasuredCode(cursor);
                }
                if (cursor.Index == fraction)
                {
                    return false;
                }
            }
            code = MeasuredCode(cursor);
            if (schema == "number" && (code == 69 || code == 101))
            {
                cursor.Index = cursor.Index + 1;
                code = MeasuredCode(cursor);
                if (code == 43 || code == 45)
                {
                    cursor.Index = cursor.Index + 1;
                }
                int exponent = cursor.Index;
                code = MeasuredCode(cursor);
                while (code >= 48 && code <= 57)
                {
                    cursor.Index = cursor.Index + 1;
                    code = MeasuredCode(cursor);
                }
                if (cursor.Index == exponent)
                {
                    return false;
                }
            }
            if (schema == "integer")
            {
                // All schema integers have semantic maxima <=12. Reject long
                // tokens before native parsing could truncate or wrap them.
                return cursor.Index - begin <= 3;
            }
            return cursor.Index - begin <= 32;
        }
        if (schema.Length() > 1 && schema.Get(0) == "@")
        {
            if (!MeasuredTake(cursor, 91))
            {
                return false;
            }
            int childLength = schema.Length() - 1;
            string child = schema.Substring(1, childLength);
            int count = 0;
            MeasuredSpace(cursor);
            if (MeasuredCode(cursor) == 93)
            {
                cursor.Index = cursor.Index + 1;
                return true;
            }
            while (count < 32)
            {
                if (!MeasuredValue(cursor, child, depth + 1))
                {
                    return false;
                }
                count = count + 1;
                MeasuredSpace(cursor);
                if (MeasuredCode(cursor) == 93)
                {
                    cursor.Index = cursor.Index + 1;
                    return true;
                }
                if (!MeasuredTake(cursor, 44))
                {
                    return false;
                }
            }
            return false;
        }
        string keys = MeasuredKeys(schema);
        if (keys.Length() == 0 || !MeasuredTake(cursor, 123))
        {
            return false;
        }
        array<string> required = new array<string>();
        map<string, bool> seen = new map<string, bool>;
        keys.Split(" ", required);
        map<string, bool> requiredIndex = new map<string, bool>;
        foreach (string requiredKey : required) { requiredIndex.Set(requiredKey, true); }
        int fields = 0;
        while (fields < required.Count())
        {
            MeasuredSpace(cursor);
            int keyBegin = cursor.Index + 1;
            string key = MeasuredString(cursor, true);
            if (cursor.Failed || !requiredIndex.Contains(key) || seen.Contains(key))
            {
                return false;
            }
            seen.Set(key, true);
            if ((schema == "context" && key == "World") || (schema == "report" && key == "world"))
            {
                cursor.WorldKey = keyBegin;
            }
            // Record original key spans while validating the original schema.
            // Values, escaped embedded JSON, source-map names and raw inputs
            // are never searched/replaced or modified.
            string replacement = "";
            if ((schema == "context" && key == "World") || (schema == "report" && key == "world"))
            {
                replacement = "WorldName";
            }
            if ((schema == "record" || schema == "candidate") && key == "BuildingType")
            {
                replacement = "BuildingClass";
            }
            if (schema == "rule" && key == "Selection")
            {
                replacement = "SelectionMode";
            }
            if (replacement.Length() > 0)
            {
                cursor.Rewrites = cursor.Rewrites + 1;
                if (cursor.Rewrites > 64)
                {
                    return false;
                }
                int prefixLength = keyBegin - cursor.CopyFrom;
                string prefixText = MeasuredCopy(cursor.Content, cursor.CopyFrom, prefixLength);
                cursor.NativeText = cursor.NativeText + prefixText + replacement;
                cursor.CopyFrom = keyBegin + key.Length();
            }
            if (!MeasuredTake(cursor, 58))
            {
                return false;
            }
            string valueSchema = MeasuredChild(schema, key);
            if (!MeasuredValue(cursor, valueSchema, depth + 1))
            {
                return false;
            }
            fields = fields + 1;
            MeasuredSpace(cursor);
            if (MeasuredCode(cursor) == 125)
            {
                cursor.Index = cursor.Index + 1;
                return fields == required.Count();
            }
            if (!MeasuredTake(cursor, 44))
            {
                return false;
            }
        }
        return false;
    }

    static bool MeasuredStrict(string content, string schema)
    {
        s_WorldKey = -1;
        if (content.Length() < 1 || content.Length() > 262144)
        {
            return false;
        }
        HCInteriorMeasuredCatalogCursor cursor = new HCInteriorMeasuredCatalogCursor;
        cursor.HCSetContent(content);
        if (!MeasuredValue(cursor, schema, 0))
        {
            return false;
        }
        MeasuredSpace(cursor);
        if (cursor.Failed || cursor.Index != content.Length())
        {
            return false;
        }
        s_WorldKey = cursor.WorldKey;
        return true;
    }

    // Enforce Substring returns at most 8191 characters (observed under Wine, diag-json-1: a 25 KB
    // class chunk reached LoadData as exactly 8191), so every copy of authored text goes in pieces.
    static string MeasuredCopy(string text, int start, int length)
    {
        if (start < 0 || length < 0 || start + length > text.Length())
        {
            return "";
        }
        string result = "";
        int done = 0;
        int piece = 0;
        while (done < length)
        {
            piece = length - done;
            if (piece > 4096)
            {
                piece = 4096;
            }
            result = result + text.Substring(start + done, piece);
            done = done + piece;
        }
        return result;
    }

    static string MeasuredNativeText(string content, string schema)
    {
        if (content.Length() < 1 || content.Length() > 262144)
        {
            return "";
        }
        HCInteriorMeasuredCatalogCursor cursor = new HCInteriorMeasuredCatalogCursor;
        cursor.HCSetContent(content);
        if (!MeasuredValue(cursor, schema, 0))
        {
            return "";
        }
        MeasuredSpace(cursor);
        if (cursor.Failed || cursor.Index != content.Length())
        {
            return "";
        }
        int remaining = content.Length() - cursor.CopyFrom;
        string tail = MeasuredCopy(content, cursor.CopyFrom, remaining);
        return cursor.NativeText + tail;
    }

    static bool MeasuredSources(map<string, string> left, map<string, string> right)
    {
        if (!left || !right || left.Count() != 3 || right.Count() != 3)
        {
            return false;
        }
        array<string> names = new array<string>();
        string keys = "HCInteriorCatalog.c HCInteriorRules.c HCInteriorStore.c";
        keys.Split(" ", names);
        HCInteriorSourceLookup lookup = new HCInteriorSourceLookup;
        lookup.Left = left;
        lookup.Right = right;
        foreach (string name : names)
        {
            string value = lookup.Left.Get(name);
            if (!MeasuredHash(value) || value != lookup.Right.Get(name))
            {
                return false;
            }
        }
        return true;
    }

    static bool MeasuredRoom(string value)
    {
        return value == "kitchen" || value == "pantry" || value == "bedroom" || value == "storage" || value == "living-room" || value == "workshop" || value == "bathroom" || value == "hallway";
    }

    static bool MeasuredObservations(array<ref HCInteriorMeasuredCatalogObservation> values)
    {
        if (!values || values.Count() < 5 || values.Count() > 16)
        {
            return false;
        }
        map<string, bool> paths = new map<string, bool>;
        foreach (HCInteriorMeasuredCatalogObservation value : values)
        {
            if (!value || !MeasuredPortablePath(value.Path) || !MeasuredHash(value.Sha256))
            {
                return false;
            }
            if (value.Kind != "native-build" && value.Kind != "asset-config" && value.Kind != "geometry" && value.Kind != "door-clearance" && value.Kind != "stairs-clearance")
            {
                return false;
            }
            string folded = value.Path;
            folded.ToLower();
            if (paths.Contains(folded))
            {
                return false;
            }
            paths.Set(folded, true);
        }
        return true;
    }

    static bool MeasuredReference(HCInteriorMeasuredCatalogRecord record, string path, string kind)
    {
        foreach (HCInteriorMeasuredCatalogObservation observation : record.Observations)
        {
            if (observation.Path == path)
            {
                return observation.Kind == kind;
            }
        }
        return false;
    }

    static bool MeasuredBox(HCInteriorMeasuredCatalogBox bounds)
    {
        if (!bounds || !MeasuredVector(bounds.Min, 100) || !MeasuredVector(bounds.Max, 100))
        {
            return false;
        }
        int axis = 0;
        while (axis < 3)
        {
            if (!(bounds.Min[axis] < bounds.Max[axis]))
            {
                return false;
            }
            axis = axis + 1;
        }
        return true;
    }

    static bool MeasuredContains(HCInteriorMeasuredCatalogBox outer, HCInteriorMeasuredCatalogBox inner)
    {
        int axis = 0;
        while (axis < 3)
        {
            if (!(outer.Min[axis] <= inner.Min[axis] && inner.Max[axis] <= outer.Max[axis]))
            {
                return false;
            }
            axis = axis + 1;
        }
        return true;
    }

    static bool MeasuredPointInside(HCInteriorMeasuredCatalogBox bounds, array<float> point)
    {
        int axis = 0;
        while (axis < 3)
        {
            if (!(bounds.Min[axis] <= point[axis] && point[axis] <= bounds.Max[axis]))
            {
                return false;
            }
            axis = axis + 1;
        }
        return true;
    }

    static float MeasuredGapSquared(HCInteriorMeasuredCatalogBox left, HCInteriorMeasuredCatalogBox right)
    {
        float sum = 0;
        int axis = 0;
        while (axis < 3)
        {
            float gap = 0;
            if (left.Min[axis] > right.Max[axis])
            {
                gap = left.Min[axis] - right.Max[axis];
            }
            if (right.Min[axis] > left.Max[axis])
            {
                gap = right.Min[axis] - left.Max[axis];
            }
            sum = sum + gap * gap;
            axis = axis + 1;
        }
        return sum;
    }

    static bool MeasuredLayout(HCInteriorMeasuredCatalogRecord record, HCInteriorMeasuredCatalogLayout layout, int index)
    {
        if (!layout || !layout.Props || layout.Props.Count() != 2 || index < 0 || index > 2)
        {
            return false;
        }
        string id = "family-pantry-v1";
        string history = "family";
        string firstType = "StaticObj_Furniture_case_a";
        string secondType = "StaticObj_Furniture_kitchen_chair_a";
        if (index == 1)
        {
            id = "family-storage-v1";
            firstType = "StaticObj_Furniture_case_bedroom_b";
            secondType = "StaticObj_Furniture_PaperBox_01_small_closed";
        }
        if (index == 2)
        {
            id = "ransacked-storage-v1";
            history = "ransacked";
            firstType = "StaticObj_Furniture_case_a_open";
            secondType = "StaticObj_Furniture_PaperBox_01_small_ransacked";
        }
        if (layout.Id != id || layout.History != history)
        {
            return false;
        }
        int propIndex = 0;
        foreach (HCInteriorMeasuredCatalogProp prop : layout.Props)
        {
            if (!prop || !MeasuredVector(prop.Position, 100) || !MeasuredVector(prop.Orientation, 360) || !MeasuredVector(prop.SearchPoint, 3))
            {
                return false;
            }
            if (propIndex == 0 && (prop.Type != firstType || !prop.Searchable))
            {
                return false;
            }
            if (propIndex == 1 && (prop.Type != secondType || prop.Searchable || prop.SearchPoint[0] != 0 || prop.SearchPoint[1] != 0 || prop.SearchPoint[2] != 0))
            {
                return false;
            }
            propIndex = propIndex + 1;
        }
        HCInteriorMeasuredCatalogSurvey survey = layout.Survey;
        if (!survey || !MeasuredBox(survey.Bounds) || !survey.Props || survey.Props.Count() != 2 || !survey.Keepouts || survey.Keepouts.Count() < 1 || survey.Keepouts.Count() > 32)
        {
            return false;
        }
        if (!MeasuredBound(survey.MinimumClearanceMetres, 0.001, 5) || (survey.Stairs != "present" && survey.Stairs != "absent"))
        {
            return false;
        }
        if (!MeasuredReference(record, survey.DoorObservation, "door-clearance") || !MeasuredReference(record, survey.StairObservation, "stairs-clearance"))
        {
            return false;
        }
        bool door = false;
        bool stairs = false;
        map<string, bool> keepoutIds = new map<string, bool>;
        foreach (HCInteriorMeasuredCatalogKeepout keepout : survey.Keepouts)
        {
            if (!keepout || !MeasuredIdentifier(keepout.Id) || keepoutIds.Contains(keepout.Id) || !MeasuredBox(keepout.Bounds) || !MeasuredContains(survey.Bounds, keepout.Bounds))
            {
                return false;
            }
            keepoutIds.Set(keepout.Id, true);
            if (keepout.Kind == "door")
            {
                door = true;
            }
            else
            {
                if (keepout.Kind != "stairs")
                {
                    return false;
                }
                stairs = true;
            }
        }
        if (!door || stairs != (survey.Stairs == "present"))
        {
            return false;
        }
        propIndex = 0;
        foreach (HCInteriorMeasuredCatalogMeasuredProp measured : survey.Props)
        {
            if (!measured || measured.Index != propIndex || !MeasuredRoom(measured.Room) || !MeasuredBox(measured.Bounds) || !MeasuredContains(survey.Bounds, measured.Bounds))
            {
                return false;
            }
            if (!MeasuredPointInside(measured.Bounds, layout.Props[propIndex].Position) || !MeasuredReference(record, measured.Observation, "geometry"))
            {
                return false;
            }
            foreach (HCInteriorMeasuredCatalogKeepout barrier : survey.Keepouts)
            {
                float clearance = survey.MinimumClearanceMetres;
                if (MeasuredGapSquared(measured.Bounds, barrier.Bounds) < clearance * clearance)
                {
                    return false;
                }
            }
            if (propIndex == 1 && MeasuredGapSquared(measured.Bounds, survey.Props[0].Bounds) <= 0)
            {
                return false;
            }
            propIndex = propIndex + 1;
        }
        return true;
    }

    static HCInteriorMeasuredCatalogGroup MeasuredGroup(HCInteriorMeasuredCatalogPolicy policy, string id)
    {
        foreach (HCInteriorMeasuredCatalogGroup group : policy.ItemGroups)
        {
            if (group.Id == id)
            {
                return group;
            }
        }
        return null;
    }

    static HCInteriorMeasuredCatalogRule MeasuredRule(HCInteriorMeasuredCatalogPolicy policy, string id)
    {
        foreach (HCInteriorMeasuredCatalogRule rule : policy.Rules)
        {
            if (rule.LayoutId == id)
            {
                return rule;
            }
        }
        return null;
    }

    static bool MeasuredPolicy(HCInteriorMeasuredCatalogRecord record, HCInteriorMeasuredCatalogPolicy policy)
    {
        if (!policy || !policy.Limits || !policy.ItemGroups || policy.ItemGroups.Count() < 1 || policy.ItemGroups.Count() > 8 || !policy.Rules || policy.Rules.Count() != 3)
        {
            return false;
        }
        HCInteriorMeasuredCatalogLimits limits = policy.Limits;
        if (limits.Slots < 1 || limits.Slots > 12 || limits.Rag < 0 || limits.Rag > 4 || limits.Battery9V < 0 || limits.Battery9V > 2)
        {
            return false;
        }
        map<string, bool> groupIds = new map<string, bool>;
        foreach (HCInteriorMeasuredCatalogGroup group : policy.ItemGroups)
        {
            if (!group || !MeasuredIdentifier(group.Id) || groupIds.Contains(group.Id) || !group.Items || group.Items.Count() < 1 || group.Items.Count() > 2)
            {
                return false;
            }
            groupIds.Set(group.Id, true);
            map<string, bool> items = new map<string, bool>;
            foreach (string item : group.Items)
            {
                if (items.Contains(item) || (item != "Rag" && item != "Battery9V"))
                {
                    return false;
                }
                if ((item == "Rag" && limits.Rag < 1) || (item == "Battery9V" && limits.Battery9V < 1))
                {
                    return false;
                }
                items.Set(item, true);
            }
        }
        map<string, ref HCInteriorMeasuredCatalogLayout> layoutIndex = new map<string, ref HCInteriorMeasuredCatalogLayout>;
        foreach (HCInteriorMeasuredCatalogLayout indexedLayout : record.Layouts) { layoutIndex.Set(indexedLayout.Id, indexedLayout); }
        map<string, bool> layouts = new map<string, bool>;
        map<string, bool> used = new map<string, bool>;
        foreach (HCInteriorMeasuredCatalogRule rule : policy.Rules)
        {
            if (!rule || layouts.Contains(rule.LayoutId) || !MeasuredIdentifier(rule.Risk) || !MeasuredText(rule.Rationale, 16, 512) || !MeasuredReference(record, rule.Observation, "geometry"))
            {
                return false;
            }
            HCInteriorMeasuredCatalogLayout matched = layoutIndex.Get(rule.LayoutId);
            if (!matched || rule.History != matched.History || rule.Room != matched.Survey.Props[0].Room)
            {
                return false;
            }
            if (!rule.EmptyAllowed || rule.MaxItems != 1 || rule.SelectionMode != "unweighted-review-only" || rule.Condition != "unmodified-native" || rule.Storage != "added-searchable-prop")
            {
                return false;
            }
            if (!rule.ItemGroups || rule.ItemGroups.Count() < 1 || rule.ItemGroups.Count() > 8)
            {
                return false;
            }
            layouts.Set(rule.LayoutId, true);
            map<string, bool> selected = new map<string, bool>;
            foreach (string id : rule.ItemGroups)
            {
                if (selected.Contains(id) || !MeasuredGroup(policy, id))
                {
                    return false;
                }
                selected.Set(id, true);
                if (!used.Contains(id))
                {
                    used.Set(id, true);
                }
            }
        }
        return used.Count() == groupIds.Count();
    }

    static bool MeasuredPolicySame(HCInteriorMeasuredCatalogPolicy left, HCInteriorMeasuredCatalogPolicy right)
    {
        if (left.Limits.Slots != right.Limits.Slots || left.Limits.Rag != right.Limits.Rag || left.Limits.Battery9V != right.Limits.Battery9V || left.ItemGroups.Count() != right.ItemGroups.Count())
        {
            return false;
        }
        int i = 0;
        while (i < left.ItemGroups.Count())
        {
            HCInteriorMeasuredCatalogGroup a = left.ItemGroups[i];
            HCInteriorMeasuredCatalogGroup b = right.ItemGroups[i];
            if (a.Id != b.Id || a.Items.Count() != b.Items.Count())
            {
                return false;
            }
            int item = 0;
            while (item < a.Items.Count())
            {
                if (a.Items[item] != b.Items[item])
                {
                    return false;
                }
                item = item + 1;
            }
            i = i + 1;
        }
        i = 0;
        while (i < 3)
        {
            HCInteriorMeasuredCatalogRule x = left.Rules[i];
            HCInteriorMeasuredCatalogRule y = right.Rules[i];
            if (x.LayoutId != y.LayoutId || x.Room != y.Room || x.History != y.History)
            {
                return false;
            }
            if (x.Risk != y.Risk || x.EmptyAllowed != y.EmptyAllowed || x.MaxItems != y.MaxItems)
            {
                return false;
            }
            if (x.SelectionMode != y.SelectionMode || x.Condition != y.Condition || x.Storage != y.Storage)
            {
                return false;
            }
            if (x.Observation != y.Observation || x.Rationale != y.Rationale || x.ItemGroups.Count() != y.ItemGroups.Count())
            {
                return false;
            }
            int group = 0;
            while (group < x.ItemGroups.Count())
            {
                if (x.ItemGroups[group] != y.ItemGroups[group])
                {
                    return false;
                }
                group = group + 1;
            }
            i = i + 1;
        }
        return true;
    }

    static bool MeasuredRecord(HCInteriorMeasuredCatalogRecord record)
    {
        if (!record || record.SchemaVersion != 1 || record.CatalogVersion != 1 || record.Synthetic || record.BuildingClass != "Land_House_1W01" || !record.Context || !record.Layouts || record.Layouts.Count() != 3)
        {
            return false;
        }
        if (!MeasuredObservations(record.Observations))
        {
            return false;
        }
        HCInteriorMeasuredCatalogContext context = record.Context;
        if (context.WorldName != "chernarusplus" || !HCBuildIdentity.Matches(context.Build) || context.NativeScriptsSha256 != "09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a")
        {
            return false;
        }
        if (!context.AssetPboSha256 || context.AssetPboSha256.Count() != 2)
        {
            return false;
        }
        if (context.AssetPboSha256.Get("structures_residential") != "f47cbd5f46f3597cc83fef822ed405cbd69de0f160c414b6deb843cc3ff2106a" || context.AssetPboSha256.Get("structures_furniture") != "e5add5e387d17df70e680e966f1705f55940ba267dcb05e7b76b8013e9d4b448")
        {
            return false;
        }
        if (!MeasuredVector(context.BuildingPosition, 30000) || !MeasuredVector(context.BuildingOrientation, 360) || context.BuildingOrientation[1] != 0 || context.BuildingOrientation[2] != 0)
        {
            return false;
        }
        if (!MeasuredIdentifier(context.SurveyId) || !MeasuredText(context.Operator, 1, 256) || !MeasuredTimestamp(context.MeasuredAt))
        {
            return false;
        }
        if (context.Method != "DayZDiag" && context.Method != "Workbench" && context.Method != "normal-server-survey")
        {
            return false;
        }
        if (context.CoordinateBasis != "building-model-local-metres" || !MeasuredReference(record, context.BuildObservation, "native-build") || !MeasuredReference(record, context.AssetObservation, "asset-config"))
        {
            return false;
        }
        int index = 0;
        while (index < 3)
        {
            if (!MeasuredLayout(record, record.Layouts[index], index))
            {
                return false;
            }
            index = index + 1;
        }
        return MeasuredPolicy(record, record.Policy);
    }

    static bool MeasuredCandidate(HCInteriorMeasuredCatalogRecord record, HCInteriorMeasuredCatalogCandidate candidate)
    {
        if (!candidate || candidate.SchemaVersion != 1 || candidate.CatalogVersion != 1 || candidate.Synthetic || candidate.BuildingClass != record.BuildingClass || !MeasuredHash(candidate.RecordSha256) || !candidate.Layouts || candidate.Layouts.Count() != 3)
        {
            return false;
        }
        int i = 0;
        while (i < 3)
        {
            HCInteriorMeasuredCatalogLayout left = record.Layouts[i];
            HCInteriorMeasuredCatalogLayout right = candidate.Layouts[i];
            if (!right || right.Survey || right.Id != left.Id || right.History != left.History || !right.Props || right.Props.Count() != 2)
            {
                return false;
            }
            int j = 0;
            while (j < 2)
            {
                HCInteriorMeasuredCatalogProp a = left.Props[j];
                HCInteriorMeasuredCatalogProp b = right.Props[j];
                if (!b || a.Type != b.Type || a.Searchable != b.Searchable || !MeasuredSameVector(a.Position, b.Position) || !MeasuredSameVector(a.Orientation, b.Orientation) || !MeasuredSameVector(a.SearchPoint, b.SearchPoint))
                {
                    return false;
                }
                j = j + 1;
            }
            i = i + 1;
        }
        return true;
    }

    static bool MeasuredReport(HCInteriorMeasuredCatalogRecord record, HCInteriorMeasuredCatalogCandidate candidate, HCInteriorMeasuredCatalogReport report)
    {
        if (!report || report.schema != 1 || report.status != "candidate-native-validation-required" || report.synthetic || report.runtime_loader_wired || report.production_accepted || report.record_sha256 != candidate.RecordSha256 || report.WorldName != record.Context.WorldName || report.build != record.Context.Build)
        {
            return false;
        }
        if (!MeasuredSources(record.SourceSha256, report.source_sha256) || !MeasuredObservations(report.observations) || report.observations.Count() != record.Observations.Count())
        {
            return false;
        }
        int i = 0;
        while (i < record.Observations.Count())
        {
            HCInteriorMeasuredCatalogObservation a = record.Observations[i];
            HCInteriorMeasuredCatalogObservation b = report.observations[i];
            if (a.Path != b.Path || a.Sha256 != b.Sha256 || a.Kind != b.Kind)
            {
                return false;
            }
            i = i + 1;
        }
        if (!report.candidate_sha256 || report.candidate_sha256.Count() != 3 || report.candidate_sha256.Get("measured-record.json") != candidate.RecordSha256)
        {
            return false;
        }
        if (!MeasuredHash(report.candidate_sha256.Get("interior-layouts.candidate.json")) || !MeasuredHash(report.candidate_sha256.Get("context-policy.candidate.json")))
        {
            return false;
        }
        if (!report.pending || report.pending.Count() != 6)
        {
            return false;
        }
        return report.pending[0] == "measured-evidence-review" && report.pending[1] == "runtime-loader-and-live-house-binding" && report.pending[2] == "DayZDiag-fit-collision-door-stair-targeting" && report.pending[3] == "normal-PBO-server-and-two-client-tests" && report.pending[4] == "CE-ownership-and-durable-inventory-commit" && report.pending[5] == "rarity-condition-balance-and-3-6-player-benchmarks";
    }

    static House MeasuredResolve(vector position, vector orientation)
    {
        array<Object> objects = new array<Object>();
        array<CargoBase> cargos = new array<CargoBase>();
        GetGame().GetObjectsAtPosition3D(position, 0.05, objects, cargos);
        if (objects.Count() > 256)
        {
            return null;
        }
        House found = null;
        foreach (Object object : objects)
        {
            House house = House.Cast(object);
            if (!house || house.GetType() != "Land_House_1W01")
            {
                continue;
            }
            if (vector.DistanceSq(position, house.GetPosition()) != 0 || vector.DistanceSq(orientation, house.GetOrientation()) != 0)
            {
                continue;
            }
            if (found)
            {
                return null;
            }
            found = house;
        }
        return found;
    }

    // Record layout: root { Layouts [ layout { Survey { Props [ prop { ... }: prop objects sit at
    // JSON depth 6; Keepouts also sit there but carry no Room key, so Room selects measured props.
    static bool HCFieldsPresent(string recordText)
    {
        return HCJsonFields.Every(recordText, "Index", 6, "Room");
    }

    // Compatibility for catalog selection: OnStart owns loading. Selection never opens files.
    static void MeasuredEnsureLoaded() {}

    static void MeasuredLoadAtStart()
    {
        if (s_Attempted) { return; }
        if (!GetGame() || !GetGame().IsServer())
        {
            return;
        }
        s_Attempted = true;
        s_Requested = FileExist(PROFILE_PATH);
        if (!s_Requested)
        {
            return;
        }
        string profileText = MeasuredRead(PROFILE_PATH, 262144);
        if (!MeasuredStrict(profileText, "profile"))
        {
            return;
        }
        HCInteriorMeasuredCatalogProfile profile = new HCInteriorMeasuredCatalogProfile;
        string error;
        if (!JsonFileLoader<HCInteriorMeasuredCatalogProfile>.LoadData(profileText, profile, error))
        {
            return;
        }
        if (profile.SchemaVersion != 1 || !profile.EnableTrustedExperiment || !profile.TrustedExternalValidation || profile.WorldName != "chernarusplus" || !HCBuildIdentity.Matches(profile.Build))
        {
            return;
        }
        // These identify externally reviewed inputs. No native SHA API is
        // assumed and no hash is recomputed or signature verified here.
        if (!MeasuredHash(profile.TrustedAddonSha256) || !MeasuredHash(profile.TrustedValidatorSha256) || !MeasuredSources(profile.SourceSha256, profile.SourceSha256))
        {
            return;
        }
        string worldName = GetGame().GetWorldName();
        worldName.ToLower();
        if (worldName != profile.WorldName || !MeasuredBuildMatches(MeasuredEngineBuild(), profile.Build))
        {
            return;
        }
        string recordText = MeasuredRead(DATA_ROOT + "measured-record.json", 32767);
        string candidateText = MeasuredRead(DATA_ROOT + "interior-layouts.candidate.json", 32767);
        string policyText = MeasuredRead(DATA_ROOT + "context-policy.candidate.json", 32767);
        string reportText = MeasuredRead(DATA_ROOT + "interior-report.json", 32767);
        if (recordText.Length() == 0 || candidateText.Length() == 0 || policyText.Length() == 0 || reportText.Length() == 0)
        {
            return;
        }
        // Exact trusted reference texts avoid substituting string.Hash() for
        // SHA-256. Authenticity and current-addon/source qualification remain
        // the external operator/validator's responsibility.
        if (recordText != profile.ExpectedRecordText || candidateText != profile.ExpectedCandidateText || policyText != profile.ExpectedPolicyText || reportText != profile.ExpectedReportText)
        {
            return;
        }
        // Native JsonFileLoader zero-fills a missing Index to 0, which would alias the first
        // prop at the propIndex comparison in MeasuredLayout. Check the raw keys first.
        if (!HCFieldsPresent(recordText))
        {
            Print("[HC Interiors] measured record refused: measured_prop_index_missing; native acceptance pending");
            return;
        }
        if (!MeasuredStrict(recordText, "record"))
        {
            return;
        }
        string nativeRecordText = MeasuredNativeText(recordText, "record");
        HCInteriorMeasuredCatalogRecord record = new HCInteriorMeasuredCatalogRecord;
        if (!JsonFileLoader<HCInteriorMeasuredCatalogRecord>.LoadData(nativeRecordText, record, error) || !MeasuredRecord(record) || !MeasuredSources(profile.SourceSha256, record.SourceSha256))
        {
            return;
        }
        if (!MeasuredStrict(candidateText, "candidate"))
        {
            return;
        }
        string nativeCandidateText = MeasuredNativeText(candidateText, "candidate");
        HCInteriorMeasuredCatalogCandidate candidate = new HCInteriorMeasuredCatalogCandidate;
        if (!JsonFileLoader<HCInteriorMeasuredCatalogCandidate>.LoadData(nativeCandidateText, candidate, error) || !MeasuredCandidate(record, candidate))
        {
            return;
        }
        if (!MeasuredStrict(policyText, "policy"))
        {
            return;
        }
        string nativePolicyText = MeasuredNativeText(policyText, "policy");
        HCInteriorMeasuredCatalogPolicy policy = new HCInteriorMeasuredCatalogPolicy;
        if (!JsonFileLoader<HCInteriorMeasuredCatalogPolicy>.LoadData(nativePolicyText, policy, error) || !MeasuredPolicy(record, policy) || !MeasuredPolicySame(record.Policy, policy))
        {
            return;
        }
        if (!MeasuredStrict(reportText, "report"))
        {
            return;
        }
        string nativeReportText = MeasuredNativeText(reportText, "report");
        HCInteriorMeasuredCatalogReport report = new HCInteriorMeasuredCatalogReport;
        if (!JsonFileLoader<HCInteriorMeasuredCatalogReport>.LoadData(nativeReportText, report, error) || !MeasuredReport(record, candidate, report))
        {
            return;
        }
        vector position = MeasuredAsVector(record.Context.BuildingPosition);
        vector orientation = MeasuredAsVector(record.Context.BuildingOrientation);
        House house = MeasuredResolve(position, orientation);
        if (!house)
        {
            return;
        }
        HCInteriorMeasuredCatalogBinding staged = new HCInteriorMeasuredCatalogBinding;
        staged.HouseObject = house;
        staged.Position = position;
        staged.Orientation = orientation;
        staged.RecordSha256 = candidate.RecordSha256;
        // These parsed DTOs were constructed privately above and never escape.
        // Selection returns fresh native layout/prop/vector values below.
        staged.Record = record;
        s_Binding = staged;
        Print("[HC Interiors] trusted experimental measured candidate bound; native acceptance pending");
    }

    static bool MeasuredLive(HCInteriorCandidate candidate)
    {
        if (!candidate || !s_Binding || !s_Binding.HouseObject || !GetGame() || !GetGame().IsServer())
        {
            return false;
        }
        string worldName = GetGame().GetWorldName();
        worldName.ToLower();
        if (worldName != s_Binding.Record.Context.WorldName || !MeasuredBuildMatches(MeasuredEngineBuild(), s_Binding.Record.Context.Build) || candidate.Type != s_Binding.Record.BuildingClass)
        {
            return false;
        }
        if (vector.DistanceSq(candidate.Position, s_Binding.Position) != 0 || vector.DistanceSq(candidate.Orientation, s_Binding.Orientation) != 0)
        {
            return false;
        }
        if (s_Binding.HouseObject.GetType() != candidate.Type || vector.DistanceSq(s_Binding.HouseObject.GetPosition(), s_Binding.Position) != 0 || vector.DistanceSq(s_Binding.HouseObject.GetOrientation(), s_Binding.Orientation) != 0)
        {
            return false;
        }
        // A changed/ambiguous live object set cannot reuse the old binding.
        return MeasuredResolve(s_Binding.Position, s_Binding.Orientation) == s_Binding.HouseObject;
    }

    static HCInteriorLayout MeasuredSelect(int index, HCInteriorCandidate candidate)
    {
        if (index < 0 || index > 2 || !MeasuredLive(candidate))
        {
            return null;
        }
        HCInteriorMeasuredCatalogLayout source = s_Binding.Record.Layouts[index];
        HCInteriorLayout layout = new HCInteriorLayout;
        layout.Id = source.Id;
        layout.History = source.History;
        foreach (HCInteriorMeasuredCatalogProp prop : source.Props)
        {
            vector position = MeasuredAsVector(prop.Position);
            vector orientation = MeasuredAsVector(prop.Orientation);
            vector point = MeasuredAsVector(prop.SearchPoint);
            HCInteriorProp copied = new HCInteriorProp(prop.Type, position, orientation, prop.Searchable, point);
            layout.Props.Insert(copied);
        }
        return layout;
    }

    static string MeasuredDigest(HCInteriorCandidate candidate)
    {
        if (!MeasuredLive(candidate))
        {
            return "";
        }
        return s_Binding.RecordSha256;
    }

    // Filters the existing finite allocation; never grants, replenishes,
    // changes condition, or supplies an independent CE/inventory transaction.
    static bool MeasuredGroupHasItem(HCInteriorMeasuredCatalogGroup group, string item)
    {
        // Validated policies have one or two items; no per-group linear search.
        return group.Items[0] == item || (group.Items.Count() == 2 && group.Items[1] == item);
    }

    static int MeasuredAllocation(int index, HCInteriorCandidate candidate, int proposed, int rags, int batteries)
    {
        if (index < 0 || index > 2 || proposed < 1 || proposed > 2 || rags < 0 || batteries < 0 || rags > 4 || batteries > 2 || !MeasuredLive(candidate))
        {
            return 0;
        }
        HCInteriorMeasuredCatalogPolicy policy = s_Binding.Record.Policy;
        if (rags + batteries >= policy.Limits.Slots)
        {
            return 0;
        }
        string item = "Rag";
        if (proposed == 1 && rags >= policy.Limits.Rag)
        {
            return 0;
        }
        if (proposed == 2)
        {
            item = "Battery9V";
            if (batteries >= policy.Limits.Battery9V)
            {
                return 0;
            }
        }
        string id = s_Binding.Record.Layouts[index].Id;
        HCInteriorMeasuredCatalogRule rule = MeasuredRule(policy, id);
        if (!rule)
        {
            return 0;
        }
        foreach (string groupId : rule.ItemGroups)
        {
            HCInteriorMeasuredCatalogGroup group = MeasuredGroup(policy, groupId);
            if (group && MeasuredGroupHasItem(group, item))
            {
                return proposed;
            }
        }
        return 0;
    }
}
