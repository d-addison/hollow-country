// Catalogs ship empty. Operator evidence is server-profile data, never an RPC
// or client-owned catalog. Admission is data validation, NOT native qualification.
// Native references below are relative to the pinned external cache:
// ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 3_Game/Global/Game.c:1120 IsServer, :930 GetObjectsAtPosition3D,
// :934 GetWorldName, :942 GetVersion (out declared before call),
// :594 ConfigGetChildName, :611 ConfigGetChildrenCount, :1437 IsKindOf.
// 3_Game/Entities/Object.c:287 GetPosition, :305 GetOrientation, :467 GetType,
// :873 ModelToWorld, :874 WorldToModel. House: 4_World/Entities/Game/Super/Building.c:485.
// 3_Game/tools/JsonFileLoader.c:69 LoadData. 1_Core/proto/EnSystem.c:
// :397 FileExist, :417 OpenFile, :443 CloseFile, :425 ReadFile.
// Primitive/collection references are listed in scratchpad-review/wp5-r2/REPORT.md.
// Class templates (docs/INTERIOR_TEMPLATES_CONTRACT.md section 9):
// :930 GetObjectsAtPosition3D (out arrays declared before the call).
class HCInfectedRoomAnchor
{
    int Id;
    vector LocalPosition;
    vector LocalMin;
    vector LocalMax;

    bool Contains(vector point)
    {
        for (int i = 0; i < 3; i++)
        {
            if (point[i] < LocalMin[i] || point[i] > LocalMax[i])
                return false;
        }
        return true;
    }
}

class HCInfectedRoomSurvey
{
    string Build;
    string WorldName;
    string BuildingClass;
    string EvidenceId;
    int Revision;
    bool Measured = false;
    ref array<ref HCInfectedRoomAnchor> Anchors = new array<ref HCInfectedRoomAnchor>;
}

class HCInfectedRoomBinding
{
    House HouseObject;
    vector Position;
    vector Orientation;
    ref HCInfectedRoomSurvey Survey;
    // Template cache only: recency stamp for least-recently-used release.
    int Stamp;
}

// Diagnostic import only. Missing poses use invalid sentinels; omitted fields
// must not accidentally bind an origin house. No measured data ships here.
class HCInfectedRoomRecord
{
    vector Position = "200001 200001 200001";
    vector Orientation = "1000 1000 1000";
    ref HCInfectedRoomSurvey Survey;
}

class HCInfectedRoomDocument
{
    int SchemaVersion;
    bool EnableDiagnostic = false;
    string Build;
    string WorldName;
    ref array<ref HCInfectedRoomRecord> Buildings = new array<ref HCInfectedRoomRecord>;
}

// Production schema v1 is deliberately distinct from the diagnostic schema.
// No poses ship here. See WP5 report for census conversion and trust boundary.
class HCInfectedProductionRoomClass
{
    string BuildingClass;
    string Disposition;
}

// Flat native JSON DTO: inherited-member deserialization is unobserved.
class HCInfectedProductionRoomAnchor
{
    int Id;
    vector LocalPosition;
    vector LocalMin;
    vector LocalMax;
    string SourceRunId;
    string SourceSha256;
    string EvidenceKind;

    bool Contains(vector point)
    {
        for (int i = 0; i < 3; i++)
        {
            if (point[i] < LocalMin[i] || point[i] > LocalMax[i])
                return false;
        }
        return true;
    }
}

// Runtime-only owned subtype; never passed to JsonSerializer. Keeps provenance
// while the existing diagnostic/order interface consumes base room anchors.
class HCInfectedOwnedProductionRoomAnchor : HCInfectedRoomAnchor
{
    string SourceRunId;
    string SourceSha256;
    string EvidenceKind;
}

class HCInfectedProductionRoomRecord
{
    string BuildingClass;
    vector Position = "200001 200001 200001";
    vector Orientation = "1000 1000 1000";
    vector BoxMin = "513 513 513";
    vector BoxMax = "-513 -513 -513";
    ref array<ref HCInfectedProductionRoomAnchor> Anchors = new array<ref HCInfectedProductionRoomAnchor>;
}

class HCInfectedProductionRoomDocument
{
    int SchemaVersion;
    string Build;
    string WorldName;
    ref array<ref HCInfectedProductionRoomClass> Classes = new array<ref HCInfectedProductionRoomClass>;
    ref array<ref HCInfectedProductionRoomRecord> Buildings = new array<ref HCInfectedProductionRoomRecord>;
}

class HCInfectedRoomCatalog
{
    static const string DIAGNOSTIC_PATH = "$profile:HollowCountry/Infected/measured-rooms.json";
    protected static ref array<ref HCInfectedRoomBinding> s_Bindings = new array<ref HCInfectedRoomBinding>;
    protected static bool s_DiagnosticAttempted = false;
    static const string PRODUCTION_PATH = "$profile:HollowCountry/Infected/production-rooms.json";
    static const int MAX_PRODUCTION_BYTES = 1048576;
    static const int MAX_CONFIG_CLASSES = 32768;
    static const int MAX_PRODUCTION_CLASSES = 2048;
    static const int MAX_PRODUCTION_HOUSES = 64;
    static const int MAX_HOUSE_ANCHORS = 16;
    static const int MAX_TOTAL_ANCHORS = 256;
    // Class-template anchors (contract sections 8 and 9). Bound lazily from an observed
    // clue; never loaded at start, never scanned on a timer, never created or moved.
    static const int DEFAULT_BIND_RADIUS = 30;
    static const int DEFAULT_BIND_QUERIES = 2;
    static const int MAX_TEMPLATE_CANDIDATES = 1024;
    static const int MAX_TEMPLATE_FOUND = 16;
    static const int MAX_TEMPLATE_LOG = 64;
    static const string TEMPLATE_EVIDENCE_KIND = "native-room-survey-v1";
    static const string TEMPLATE_READY = "rooms_templates_provisional_path_audio_doors_pending";
    protected static ref array<ref HCInfectedRoomBinding> s_TemplateBindings = new array<ref HCInfectedRoomBinding>;
    protected static ref array<House> s_ConflictHouses = new array<House>;
    protected static ref array<string> s_TemplateRefusals = new array<string>;
    protected static int s_BindRadius = 30;
    protected static int s_BindQueryCap = 2;
    protected static int s_BindQueries = 0;
    protected static int s_BindStamp = 0;
    protected static bool s_ConflictsResolved = false;
    protected static bool s_TemplateLogged = false;
    protected static string s_TemplateReason = "rooms_templates_not_loaded";
    protected static int s_TemplateCovered = 0;
    protected static int s_TemplateDenominator = 0;
    protected static ref array<ref HCInfectedRoomBinding> s_ProductionBindings = new array<ref HCInfectedRoomBinding>;
    protected static ref array<ref HCInfectedProductionRoomClass> s_ProductionClasses = new array<ref HCInfectedProductionRoomClass>;
    protected static bool s_ProductionAttempted = false;
    protected static string s_ProductionReason = "rooms_not_loaded";
    protected static string s_ProductionContext;
    protected static int s_JsonOffset;

    static void Clear()
    {
        s_Bindings.Clear();
        s_DiagnosticAttempted = false;
        ClearProduction();
    }

    static bool DiagnosticServer()
    {
        bool diagnostic = false;
#ifdef DIAG_DEVELOPER
        diagnostic = true;
#endif
        return diagnostic && GetGame() && GetGame().IsServer();
    }

    // Strict field sets at each object depth. Native deserialization supplies
    // grammar/type validation; this pass rejects ignored/duplicate/missing keys.
    static int KeyBit(int depth, string key)
    {
        if (depth == 1)
        {
            if (key == "SchemaVersion") return 1;
            if (key == "EnableDiagnostic") return 2;
            if (key == "Build") return 4;
            if (key == "WorldName") return 8;
            if (key == "Buildings") return 16;
        }
        if (depth == 2)
        {
            if (key == "Position") return 1;
            if (key == "Orientation") return 2;
            if (key == "Survey") return 4;
        }
        if (depth == 3)
        {
            if (key == "Build") return 1;
            if (key == "WorldName") return 2;
            if (key == "BuildingClass") return 4;
            if (key == "EvidenceId") return 8;
            if (key == "Revision") return 16;
            if (key == "Measured") return 32;
            if (key == "Anchors") return 64;
        }
        if (depth == 4)
        {
            if (key == "Id") return 1;
            if (key == "LocalPosition") return 2;
            if (key == "LocalMin") return 4;
            if (key == "LocalMax") return 8;
        }
        return 0;
    }

    static int RequiredKeys(int depth)
    {
        if (depth == 1) return 31;
        if (depth == 2) return 7;
        if (depth == 3) return 127;
        if (depth == 4) return 15;
        return 0;
    }

    static bool JsonSpace(string ch)
    {
        return ch == " " || ch.ToAscii() == 9 || ch.ToAscii() == 10 || ch.ToAscii() == 13;
    }

    static bool ValidJsonKeys(string content)
    {
        if (content.Length() < 1 || content.Length() > 65536)
            return false;
        ref array<int> masks = new array<int>;
        int depth = 0;
        int roots = 0;
        int begin = 0;
        bool quoted = false;
        for (int i = 0; i < content.Length(); i++)
        {
            string ch = content.Get(i);
            // Diagnostic identifiers need no escapes. Reject all escapes so a
            // differently encoded key cannot bypass duplicate/unknown checks.
            if (ch.ToAscii() == 92)
                return false;
            if (ch.ToAscii() == 34)
            {
                if (!quoted)
                {
                    quoted = true;
                    begin = i + 1;
                }
                else
                {
                    quoted = false;
                    int next = i + 1;
                    while (next < content.Length() && JsonSpace(content.Get(next)))
                        next++;
                    if (next < content.Length() && content.Get(next) == ":")
                    {
                        if (depth < 1 || i - begin > 32)
                            return false;
                        int bit = KeyBit(depth, content.Substring(begin, i - begin));
                        if (bit == 0 || (masks[depth - 1] & bit) != 0)
                            return false;
                        masks[depth - 1] = masks[depth - 1] | bit;
                    }
                }
                continue;
            }
            if (quoted)
                continue;
            if (ch.ToAscii() == 123)
            {
                if (depth == 0)
                    roots++;
                depth++;
                if (roots > 1 || depth > 4)
                    return false;
                masks.Insert(0);
            }
            if (ch.ToAscii() == 125)
            {
                if (depth < 1 || masks[depth - 1] != RequiredKeys(depth))
                    return false;
                masks.Remove(depth - 1);
                depth--;
            }
        }
        return !quoted && depth == 0 && roots == 1;
    }

    static HCInfectedRoomDocument ReadDiagnostic()
    {
        if (!DiagnosticServer())
            return null;
        string content;
        if (!HCInfectedStore.ReadBounded(DIAGNOSTIC_PATH, content))
            return null;
        if (!ValidJsonKeys(content))
            return null;
        HCInfectedRoomDocument document = new HCInfectedRoomDocument;
        string error;
        if (!JsonFileLoader<HCInfectedRoomDocument>.LoadData(content, document, error))
            return null;
        return document;
    }

    static void EnsureDiagnosticLoaded()
    {
        if (!DiagnosticServer() || s_DiagnosticAttempted)
            return;
        // Claim before any I/O or binding; a missing/rejected file is not polled
        // on AI ticks. Clear (module stop) permits a fresh diagnostic attempt.
        s_DiagnosticAttempted = true;
        if (s_Bindings.Count() != 0)
            return;
        HCInfectedRoomDocument document = ReadDiagnostic();
        if (!document)
            return;
        if (!BindDiagnostic(document))
            Print("[HollowCountry] diagnostic measured room catalog rejected; no bindings published");
    }

    static House ResolveBuilding(HCInfectedRoomRecord record)
    {
        if (!record || !record.Survey || !HCInfectedStore.ValidPosition(record.Position))
            return null;
        for (int axis = 0; axis < 3; axis++)
        {
            if (!(record.Orientation[axis] >= -360 && record.Orientation[axis] <= 360))
                return null;
        }
        ref array<Object> candidates = new array<Object>;
        ref array<CargoBase> cargos = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(record.Position, 0.25, candidates, cargos);
        // Native query allocation is engine-owned; never iterate a dense result.
        if (candidates.Count() > 64 || cargos.Count() > 64)
            return null;
        House selected;
        foreach (Object candidate : candidates)
        {
            House building = House.Cast(candidate);
            if (!building || building.GetType() != record.Survey.BuildingClass)
                continue;
            if (!(vector.DistanceSq(record.Position, building.GetPosition()) <= 0.0001))
                continue;
            if (!(vector.DistanceSq(record.Orientation, building.GetOrientation()) <= 0.0001))
                continue;
            if (selected)
                return null;
            selected = building;
        }
        return selected;
    }

    static bool BindDiagnostic(HCInfectedRoomDocument document)
    {
        if (!DiagnosticServer() || !document || !document.EnableDiagnostic || document.SchemaVersion != 1)
            return false;
        if (!HCBuildIdentity.Matches(document.Build) || !HCBuildIdentity.SameWorld(document.WorldName, GetGame().GetWorldName()))
            return false;
        if (!document.Buildings || document.Buildings.Count() < 1 || document.Buildings.Count() > 4 || s_Bindings.Count() != 0)
            return false;
        ref array<ref HCInfectedRoomBinding> staged = new array<ref HCInfectedRoomBinding>;
        foreach (HCInfectedRoomRecord record : document.Buildings)
        {
            if (!record || !record.Survey)
                return false;
            House building = ResolveBuilding(record);
            HCInfectedRoomBinding binding = CreateBinding(building, record.Survey, staged);
            if (!binding)
                return false;
            staged.Insert(binding);
        }
        // Publish once, only after every instance and copied survey validates.
        s_Bindings = staged;
        return true;
    }

    static bool Register(House building, HCInfectedRoomSurvey survey)
    {
        HCInfectedRoomBinding binding = CreateBinding(building, survey, s_Bindings);
        if (!binding)
            return false;
        s_Bindings.Insert(binding);
        return true;
    }

    static HCInfectedRoomBinding CreateBinding(House building, HCInfectedRoomSurvey survey, array<ref HCInfectedRoomBinding> existing)
    {
        if (!DiagnosticServer() || !building || !survey || !survey.Anchors || !existing)
            return null;
        bool sameBuildWorld = HCBuildIdentity.Matches(survey.Build) && HCBuildIdentity.SameWorld(survey.WorldName, GetGame().GetWorldName());
        if (!HCInfectedPolicy.AdmitRoomCatalog(survey.Measured, sameBuildWorld, survey.Revision, survey.Anchors.Count(), existing.Count(), 4))
            return null;
        if (survey.BuildingClass != building.GetType() || survey.EvidenceId.Length() < 1 || survey.EvidenceId.Length() > 128)
            return null;
        if (!HCInfectedStore.ValidPosition(building.GetPosition()) || !HCInfectedStore.ValidPosition(building.GetOrientation()))
            return null;
        foreach (HCInfectedRoomBinding previous : existing)
        {
            if (previous.HouseObject == building)
                return null;
        }
        HCInfectedRoomSurvey ownedSurvey = new HCInfectedRoomSurvey;
        ownedSurvey.Build = survey.Build;
        ownedSurvey.WorldName = survey.WorldName;
        ownedSurvey.BuildingClass = survey.BuildingClass;
        ownedSurvey.EvidenceId = survey.EvidenceId;
        ownedSurvey.Revision = survey.Revision;
        ownedSurvey.Measured = survey.Measured;
        foreach (HCInfectedRoomAnchor anchor : survey.Anchors)
        {
            if (!anchor || anchor.Id < 1 || anchor.Id > 64 || !HCInfectedStore.ValidPosition(anchor.LocalPosition) || !anchor.Contains(anchor.LocalPosition))
                return null;
            for (int axis = 0; axis < 3; axis++)
            {
                if (!(anchor.LocalMin[axis] >= -32 && anchor.LocalMax[axis] <= 32 && anchor.LocalMin[axis] < anchor.LocalMax[axis]))
                    return null;
            }
            foreach (HCInfectedRoomAnchor accepted : ownedSurvey.Anchors)
            {
                if (anchor.Id == accepted.Id || vector.DistanceSq(anchor.LocalPosition, accepted.LocalPosition) < 1)
                    return null;
            }
            HCInfectedRoomAnchor copy = new HCInfectedRoomAnchor;
            copy.Id = anchor.Id;
            copy.LocalPosition = anchor.LocalPosition;
            copy.LocalMin = anchor.LocalMin;
            copy.LocalMax = anchor.LocalMax;
            ownedSurvey.Anchors.Insert(copy);
        }
        HCInfectedRoomBinding binding = new HCInfectedRoomBinding;
        binding.HouseObject = building;
        binding.Position = building.GetPosition();
        binding.Orientation = building.GetOrientation();
        binding.Survey = ownedSurvey;
        return binding;
    }

    static bool ProductionServer()
    {
        return GetGame() && GetGame().IsServer();
    }

    static void ClearProduction()
    {
        s_ProductionBindings.Clear();
        s_ProductionClasses.Clear();
        s_ProductionAttempted = false;
        s_ProductionReason = "rooms_not_loaded";
        s_ProductionContext = "";
        s_TemplateBindings.Clear();
        s_ConflictHouses.Clear();
        s_TemplateRefusals.Clear();
        s_BindRadius = DEFAULT_BIND_RADIUS;
        s_BindQueryCap = DEFAULT_BIND_QUERIES;
        s_BindQueries = 0;
        s_BindStamp = 0;
        s_ConflictsResolved = false;
        s_TemplateLogged = false;
        s_TemplateReason = "rooms_templates_not_loaded";
        s_TemplateCovered = 0;
        s_TemplateDenominator = 0;
    }

    static string ProductionReason()
    {
        return s_ProductionReason;
    }

    // Copied report: each installed House config class appears exactly once.
    // "covered" means at least one measured instance, never all map placements.
    static void ProductionCoverage(out TStringArray covered, out TStringArray excluded)
    {
        covered = new TStringArray;
        excluded = new TStringArray;
        if (!ProductionServer())
            return;
        foreach (HCInfectedProductionRoomClass entry : s_ProductionClasses)
        {
            if (entry.Disposition == "covered")
            {
                covered.Insert(entry.BuildingClass);
            }
            else
            {
                excluded.Insert(entry.BuildingClass + "=" + entry.Disposition);
            }
        }
    }

    static bool ProductionToken(string value, int limit)
    {
        if (value.Length() < 1 || value.Length() > limit)
            return false;
        for (int i = 0; i < value.Length(); i++)
        {
            string ch = value.Get(i);
            int ascii = ch.ToAscii();
            bool letter = (ascii >= 65 && ascii <= 90) || (ascii >= 97 && ascii <= 122);
            if (!letter && !(ascii >= 48 && ascii <= 57) && ascii != 45 && ascii != 95)
                return false;
        }
        return true;
    }

    static bool ProductionHash(string value)
    {
        if (value.Length() != 64)
            return false;
        bool nonzero = false;
        for (int i = 0; i < 64; i++)
        {
            string ch = value.Get(i);
            int ascii = ch.ToAscii();
            if (!(ascii >= 48 && ascii <= 57) && !(ascii >= 97 && ascii <= 102))
                return false;
            if (ascii != 48)
                nonzero = true;
        }
        return nonzero;
    }

    static bool ProductionEvidence(HCInfectedProductionRoomAnchor anchor)
    {
        if (!anchor || !ProductionToken(anchor.SourceRunId, 96) || anchor.SourceRunId.Length() < 8)
            return false;
        string runId = anchor.SourceRunId;
        runId.ToLower();
        if (runId.Substring(0, 7) != "native-" || runId.Contains("synthetic") || runId.Contains("fixture") || runId.Contains("selftest"))
            return false;
        // Census floor hits alone lack semantic room bounds. A reviewed native
        // room survey must supply these; never relabel generated/test poses.
        return anchor.EvidenceKind == "native-room-survey-v1" && ProductionHash(anchor.SourceSha256);
    }

    static bool ProductionDisposition(string value)
    {
        return value == "covered" || value == "unmeasured" || value == "not_enterable" || value == "path_pending" || value == "door_pending" || value == "unsupported_geometry";
    }

    static int ProductionClassIndex(HCInfectedProductionRoomDocument document, string className)
    {
        for (int i = 0; i < document.Classes.Count(); i++)
        {
            if (document.Classes[i].BuildingClass == className)
                return i;
        }
        return -1;
    }

    static bool ValidateProductionCoverage(HCInfectedProductionRoomDocument document)
    {
        // Full denominator = all loaded CfgVehicles subclasses of House,
        // including base/closed/non-enterable classes, explicitly excluded.
        int configCount = GetGame().ConfigGetChildrenCount("CfgVehicles");
        if (configCount < 1 || configCount > MAX_CONFIG_CLASSES)
        {
            s_ProductionReason = "rooms_denominator_cap";
            return false;
        }
        ref array<string> known = new array<string>;
        foreach (HCInfectedProductionRoomClass entry : document.Classes)
        {
            if (!entry || !ProductionToken(entry.BuildingClass, 128) || !ProductionDisposition(entry.Disposition))
                return false;
            if (known.Find(entry.BuildingClass) >= 0)
                return false;
            known.Insert(entry.BuildingClass);
        }
        int houseClasses = 0;
        bool complete = true;
        for (int i = 0; i < configCount; i++)
        {
            string className;
            if (!GetGame().ConfigGetChildName("CfgVehicles", i, className))
                return false;
            if (!GetGame().IsKindOf(className, "House"))
                continue;
            houseClasses++;
            if (known.Find(className) < 0)
                complete = false;
        }
        if (houseClasses > MAX_PRODUCTION_CLASSES)
        {
            s_ProductionReason = "rooms_house_class_cap";
            s_ProductionContext = "; config children=" + configCount.ToString() + "; House classes=" + houseClasses.ToString();
            return false;
        }
        if (!complete)
            return false;
        if (houseClasses != known.Count())
            return false;
        // Coverage is bidirectional: no omitted class, no excluded house used,
        // and no "covered" class without at least one admitted instance.
        ref array<string> usedClasses = new array<string>;
        foreach (HCInfectedProductionRoomRecord record : document.Buildings)
        {
            if (!record)
                return false;
            int classIndex = ProductionClassIndex(document, record.BuildingClass);
            if (classIndex < 0 || document.Classes[classIndex].Disposition != "covered")
                return false;
            if (usedClasses.Find(record.BuildingClass) < 0)
                usedClasses.Insert(record.BuildingClass);
        }
        foreach (HCInfectedProductionRoomClass declared : document.Classes)
        {
            if (declared.Disposition == "covered" && usedClasses.Find(declared.BuildingClass) < 0)
                return false;
        }
        return true;
    }

    static bool ValidateProductionHouse(HCInfectedProductionRoomRecord record)
    {
        s_ProductionReason = "rooms_geometry";
        for (int axis = 0; axis < 3; axis++)
        {
            if (!(record.BoxMin[axis] >= -512 && record.BoxMax[axis] <= 512 && record.BoxMin[axis] < record.BoxMax[axis]))
                return false;
        }
        ref array<int> usedIds = new array<int>;
        ref array<vector> usedPositions = new array<vector>;
        foreach (HCInfectedProductionRoomAnchor anchor : record.Anchors)
        {
            if (!anchor || anchor.Id < 1 || anchor.Id > 64 || usedIds.Find(anchor.Id) >= 0)
                return false;
            for (int anchorAxis = 0; anchorAxis < 3; anchorAxis++)
            {
                // Positive comparisons reject NaN and infinity as well as bad
                // ordering; both semantic room box and point stay in house box.
                if (!(anchor.LocalMin[anchorAxis] >= record.BoxMin[anchorAxis] && anchor.LocalMax[anchorAxis] <= record.BoxMax[anchorAxis] && anchor.LocalMin[anchorAxis] < anchor.LocalMax[anchorAxis]))
                    return false;
                if (!(anchor.LocalPosition[anchorAxis] >= anchor.LocalMin[anchorAxis] && anchor.LocalPosition[anchorAxis] <= anchor.LocalMax[anchorAxis]))
                    return false;
            }
            foreach (vector previousPoint : usedPositions)
            {
                if (vector.DistanceSq(previousPoint, anchor.LocalPosition) < 1)
                    return false;
            }
            if (!ProductionEvidence(anchor))
            {
                s_ProductionReason = "rooms_evidence";
                return false;
            }
            usedIds.Insert(anchor.Id);
            usedPositions.Insert(anchor.LocalPosition);
        }
        return true;
    }

    static string ProductionBuildLabel(string value)
    {
        string label = "";
        int limit = value.Length();
        if (limit > 32)
            limit = 32;
        for (int i = 0; i < limit; i++)
        {
            string ch = value.Get(i);
            int ascii = ch.ToAscii();
            if (ascii >= 32 && ascii <= 126)
            {
                label = label + ch;
            }
            else
            {
                label = label + "?";
            }
        }
        return label;
    }

    static bool BindProduction(HCInfectedProductionRoomDocument document)
    {
        if (!ProductionServer())
            return false;
        if (s_ProductionReason == "rooms_admitted_measurements_path_audio_doors_pending")
            return false;
        s_ProductionContext = "";
        s_ProductionReason = "rooms_schema";
        if (!document || document.SchemaVersion != 1)
            return false;
        s_ProductionReason = "rooms_build";
        string currentBuild;
        GetGame().GetVersion(currentBuild);
        if (!HCBuildIdentity.Matches(document.Build) || !HCBuildIdentity.Matches(currentBuild))
        {
            s_ProductionContext = "; observed build=" + ProductionBuildLabel(currentBuild);
            return false;
        }
        s_ProductionReason = "rooms_world";
        if (!ProductionToken(document.WorldName, 64) || !HCBuildIdentity.SameWorld(document.WorldName, GetGame().GetWorldName()))
            return false;
        s_ProductionReason = "rooms_limits";
        if (!document.Classes || document.Classes.Count() < 1 || document.Classes.Count() > MAX_PRODUCTION_CLASSES)
            return false;
        if (!document.Buildings || document.Buildings.Count() > MAX_PRODUCTION_HOUSES)
            return false;
        int total = 0;
        foreach (HCInfectedProductionRoomRecord counted : document.Buildings)
        {
            if (!counted || !counted.Anchors || counted.Anchors.Count() < 1 || counted.Anchors.Count() > MAX_HOUSE_ANCHORS)
                return false;
            total = total + counted.Anchors.Count();
            if (total > MAX_TOTAL_ANCHORS)
                return false;
        }
        s_ProductionReason = "rooms_coverage";
        if (!ValidateProductionCoverage(document))
            return false;
        ref array<ref HCInfectedRoomBinding> staged = new array<ref HCInfectedRoomBinding>;
        ref array<ref HCInfectedProductionRoomClass> coverage = new array<ref HCInfectedProductionRoomClass>;
        foreach (HCInfectedProductionRoomRecord record : document.Buildings)
        {
            if (!ValidateProductionHouse(record))
                return false;
            HCInfectedRoomSurvey survey = new HCInfectedRoomSurvey;
            survey.Build = document.Build;
            survey.WorldName = document.WorldName;
            survey.BuildingClass = record.BuildingClass;
            survey.Measured = true;
            survey.Revision = 1;
            // Provenance remains on the runtime-only owned anchor subtype.
            foreach (HCInfectedProductionRoomAnchor anchor : record.Anchors)
            {
                HCInfectedOwnedProductionRoomAnchor ownedAnchor = new HCInfectedOwnedProductionRoomAnchor;
                ownedAnchor.Id = anchor.Id;
                ownedAnchor.LocalPosition = anchor.LocalPosition;
                ownedAnchor.LocalMin = anchor.LocalMin;
                ownedAnchor.LocalMax = anchor.LocalMax;
                ownedAnchor.SourceRunId = anchor.SourceRunId;
                ownedAnchor.SourceSha256 = anchor.SourceSha256;
                ownedAnchor.EvidenceKind = anchor.EvidenceKind;
                survey.Anchors.Insert(ownedAnchor);
            }
            HCInfectedRoomRecord lookup = new HCInfectedRoomRecord;
            lookup.Position = record.Position;
            lookup.Orientation = record.Orientation;
            lookup.Survey = survey;
            s_ProductionReason = "rooms_binding";
            House building = ResolveBuilding(lookup);
            if (!building)
                return false;
            foreach (HCInfectedRoomBinding previous : staged)
            {
                if (previous.HouseObject == building)
                    return false;
            }
            HCInfectedRoomBinding binding = new HCInfectedRoomBinding;
            binding.HouseObject = building;
            binding.Position = building.GetPosition();
            binding.Orientation = building.GetOrientation();
            binding.Survey = survey;
            staged.Insert(binding);
        }
        foreach (HCInfectedProductionRoomClass entry : document.Classes)
        {
            HCInfectedProductionRoomClass ownedClass = new HCInfectedProductionRoomClass;
            ownedClass.BuildingClass = entry.BuildingClass;
            ownedClass.Disposition = entry.Disposition;
            coverage.Insert(ownedClass);
        }
        s_ProductionBindings = staged;
        s_ProductionClasses = coverage;
        s_ProductionReason = "rooms_admitted_measurements_path_audio_doors_pending";
        return true;
    }

    // Strict typed JSON preflight. Unlike the diagnostic depth-only key pass,
    // this enforces array/object roles and scalar types before native allocation.
    // Recursion follows fixed schema kinds only: root -> class/house -> anchor.
    static string ProductionJsonChar(string content)
    {
        if (s_JsonOffset < 0 || s_JsonOffset >= content.Length())
            return "";
        return content.Get(s_JsonOffset);
    }

    static int ProductionJsonCode(string content)
    {
        string ch = ProductionJsonChar(content);
        if (ch.Length() != 1)
            return -1;
        return ch.ToAscii();
    }

    static void ProductionJsonSkip(string content)
    {
        while (s_JsonOffset < content.Length() && JsonSpace(ProductionJsonChar(content)))
            s_JsonOffset++;
    }

    static string ProductionJsonText(string content)
    {
        if (ProductionJsonCode(content) != 34)
            return "";
        s_JsonOffset++;
        int begin = s_JsonOffset;
        while (s_JsonOffset < content.Length() && s_JsonOffset - begin <= 128)
        {
            int ascii = ProductionJsonCode(content);
            if (ascii == 34)
            {
                string value = content.Substring(begin, s_JsonOffset - begin);
                s_JsonOffset++;
                return value;
            }
            if (ascii < 32 || ascii > 126 || ascii == 92)
                return "";
            s_JsonOffset++;
        }
        return "";
    }

    static bool ProductionJsonNumber(string content, bool integerOnly)
    {
        int begin = s_JsonOffset;
        if (ProductionJsonChar(content) == "-")
            s_JsonOffset++;
        int ascii = ProductionJsonCode(content);
        if (ascii < 48 || ascii > 57)
            return false;
        bool zero = ascii == 48;
        s_JsonOffset++;
        while (s_JsonOffset < content.Length())
        {
            int digit = ProductionJsonCode(content);
            if (digit < 48 || digit > 57)
                break;
            if (zero || s_JsonOffset - begin > 32)
                return false;
            s_JsonOffset++;
        }
        if (!integerOnly && ProductionJsonChar(content) == ".")
        {
            s_JsonOffset++;
            int fractionBegin = s_JsonOffset;
            while (s_JsonOffset < content.Length())
            {
                int fractionDigit = ProductionJsonCode(content);
                if (fractionDigit < 48 || fractionDigit > 57)
                    break;
                if (s_JsonOffset - begin > 32)
                    return false;
                s_JsonOffset++;
            }
            if (s_JsonOffset == fractionBegin)
                return false;
        }
        string exponent = ProductionJsonChar(content);
        if (!integerOnly && (exponent == "e" || exponent == "E"))
        {
            s_JsonOffset++;
            string sign = ProductionJsonChar(content);
            if (sign == "+" || sign == "-")
                s_JsonOffset++;
            int exponentBegin = s_JsonOffset;
            while (s_JsonOffset < content.Length())
            {
                int exponentDigit = ProductionJsonCode(content);
                if (exponentDigit < 48 || exponentDigit > 57)
                    break;
                if (s_JsonOffset - begin > 32)
                    return false;
                s_JsonOffset++;
            }
            if (s_JsonOffset == exponentBegin)
                return false;
        }
        // DTO integers are parsed by the VM as signed int. Limit digits before
        // native decoding so an overflow cannot wrap a schema/anchor id to 1.
        if (integerOnly && s_JsonOffset - begin > 9)
            return false;
        return s_JsonOffset - begin <= 32;
    }

    // Kinds: 1 root; 2 class rows; 3 class; 4 house rows; 5 house;
    // 6 anchors; 7 anchor; 8 numeric vector. Keys are exact ASCII literals.
    static int ProductionKeyBit(int kind, string key)
    {
        if (kind == 1)
        {
            if (key == "SchemaVersion") return 1;
            if (key == "Build") return 2;
            if (key == "WorldName") return 4;
            if (key == "Classes") return 8;
            if (key == "Buildings") return 16;
        }
        if (kind == 3)
        {
            if (key == "BuildingClass") return 1;
            if (key == "Disposition") return 2;
        }
        if (kind == 5)
        {
            if (key == "BuildingClass") return 1;
            if (key == "Position") return 2;
            if (key == "Orientation") return 4;
            if (key == "BoxMin") return 8;
            if (key == "BoxMax") return 16;
            if (key == "Anchors") return 32;
        }
        if (kind == 7)
        {
            if (key == "Id") return 1;
            if (key == "LocalPosition") return 2;
            if (key == "LocalMin") return 4;
            if (key == "LocalMax") return 8;
            if (key == "SourceRunId") return 16;
            if (key == "SourceSha256") return 32;
            if (key == "EvidenceKind") return 64;
        }
        return 0;
    }

    static int ProductionRequiredKeys(int kind)
    {
        if (kind == 1) return 31;
        if (kind == 3) return 3;
        if (kind == 5) return 63;
        if (kind == 7) return 127;
        return 0;
    }

    static bool ProductionJsonValue(string content, int kind, string key)
    {
        if (kind == 1 && key == "Classes")
            return ProductionJsonArray(content, 2);
        if (kind == 1 && key == "Buildings")
            return ProductionJsonArray(content, 4);
        if (kind == 5 && key == "Anchors")
            return ProductionJsonArray(content, 6);
        if ((kind == 1 && key == "SchemaVersion") || (kind == 7 && key == "Id"))
            return ProductionJsonNumber(content, true);
        bool houseVector = kind == 5 && (key == "Position" || key == "Orientation" || key == "BoxMin" || key == "BoxMax");
        bool anchorVector = kind == 7 && (key == "LocalPosition" || key == "LocalMin" || key == "LocalMax");
        if (houseVector || anchorVector)
            return ProductionJsonArray(content, 8);
        int textBegin = s_JsonOffset;
        string textValue = ProductionJsonText(content);
        if (textValue.Length() > 0)
            return true;
        // Empty JSON strings are typed correctly; semantic admission assigns
        // their specific build/world/class/evidence refusal instead.
        if (s_JsonOffset != textBegin + 2)
            return false;
        string closingQuote = content.Get(textBegin + 1);
        return closingQuote.ToAscii() == 34;
    }

    static bool ProductionJsonArray(string content, int kind)
    {
        if (ProductionJsonChar(content) != "[")
            return false;
        s_JsonOffset++;
        ProductionJsonSkip(content);
        int limit = MAX_PRODUCTION_CLASSES;
        if (kind == 4) limit = MAX_PRODUCTION_HOUSES;
        if (kind == 6) limit = MAX_HOUSE_ANCHORS;
        if (kind == 8) limit = 3;
        int count = 0;
        if (ProductionJsonChar(content) != "]")
        {
            while (s_JsonOffset < content.Length())
            {
                if (count >= limit)
                {
                    return false;
                }
                if (kind == 8)
                {
                    if (!ProductionJsonNumber(content, false))
                        return false;
                }
                else
                {
                    if (!ProductionJsonObject(content, kind + 1))
                        return false;
                }
                count++;
                ProductionJsonSkip(content);
                if (ProductionJsonChar(content) == "]")
                    break;
                if (ProductionJsonChar(content) != ",")
                    return false;
                s_JsonOffset++;
                ProductionJsonSkip(content);
            }
        }
        if (kind == 8 && count != 3)
            return false;
        if (ProductionJsonChar(content) != "]")
            return false;
        s_JsonOffset++;
        return true;
    }

    static bool ProductionJsonObject(string content, int kind)
    {
        if (ProductionJsonChar(content) != "{")
            return false;
        s_JsonOffset++;
        int mask = 0;
        for (int fieldIndex = 0; fieldIndex < 7; fieldIndex++)
        {
            ProductionJsonSkip(content);
            string key = ProductionJsonText(content);
            int bit = ProductionKeyBit(kind, key);
            if (bit == 0 || (mask & bit) != 0)
                return false;
            mask = mask | bit;
            ProductionJsonSkip(content);
            if (ProductionJsonChar(content) != ":")
                return false;
            s_JsonOffset++;
            ProductionJsonSkip(content);
            if (!ProductionJsonValue(content, kind, key))
                return false;
            ProductionJsonSkip(content);
            if (ProductionJsonChar(content) == "}")
            {
                s_JsonOffset++;
                return mask == ProductionRequiredKeys(kind);
            }
            if (ProductionJsonChar(content) != ",")
                return false;
            s_JsonOffset++;
        }
        return false;
    }

    static bool ValidProductionJson(string content)
    {
        s_JsonOffset = 0;
        if (content.Length() < 1 || content.Length() > MAX_PRODUCTION_BYTES)
            return false;
        ProductionJsonSkip(content);
        if (!ProductionJsonObject(content, 1))
            return false;
        ProductionJsonSkip(content);
        return s_JsonOffset == content.Length();
    }

    static void EnsureProductionLoaded()
    {
        if (!ProductionServer() || s_ProductionAttempted)
            return;
        s_ProductionAttempted = true;
        // Fixed operator-only path; native LoadFile has an excessive allocation
        // bound, so use capped I/O then LoadData. Never print parser errors/catalog input.
        s_ProductionReason = "rooms_missing";
        if (FileExist(PRODUCTION_PATH))
        {
            s_ProductionReason = "rooms_read";
            FileHandle handle = OpenFile(PRODUCTION_PATH, FileMode.READ);
            if (handle)
            {
                string content;
                int bytesRead = ReadFile(handle, content, MAX_PRODUCTION_BYTES + 1);
                CloseFile(handle);
                // Like HCInfectedStore.ReadBounded, bound the received string
                // length independently of the requested read size. Additionally
                // fail closed on negative/mismatched counts for this ASCII-only
                // schema. ReadFile(string) byte/length semantics remain unobserved;
                // ReadBounded currently ignores the native count. Compare both
                // observed values in DayZDiag before enabling production data.
                if (bytesRead >= 0 && bytesRead == content.Length())
                {
                    s_ProductionReason = "rooms_size";
                    if (content.Length() > 0 && content.Length() <= MAX_PRODUCTION_BYTES)
                    {
                        s_ProductionReason = "rooms_json";
                        if (ValidProductionJson(content))
                        {
                            HCInfectedProductionRoomDocument document = new HCInfectedProductionRoomDocument;
                            string error;
                            if (JsonFileLoader<HCInfectedProductionRoomDocument>.LoadData(content, document, error))
                                BindProduction(document);
                        }
                    }
                }
            }
        }
        // Single bounded log per lifecycle, even for a missing/rejected file.
        // Complete copied class/exclusion rows are available via ProductionCoverage.
        if (s_ProductionReason != "rooms_missing") Print("[HollowCountry] " + s_ProductionReason + s_ProductionContext + "; room classes=" + s_ProductionClasses.Count().ToString() + "; instances=" + s_ProductionBindings.Count().ToString());
        // The template reader may already be loaded; otherwise the first bind logs it.
        LogTemplateAdmission();
    }

    // Module start passes InfectedBindRadius (5..60) and MaxBindQueriesPerTick (1..8)
    // before EnsureProductionLoaded. Out-of-range values keep the defaults.
    static bool ConfigureBinding(int radius, int queriesPerTick)
    {
        if (radius < 5 || radius > 60 || queriesPerTick < 1 || queriesPerTick > 8)
            return false;
        s_BindRadius = radius;
        s_BindQueryCap = queriesPerTick;
        return true;
    }

    static string TemplateReason()
    {
        return s_TemplateReason;
    }

    // One bounded log per (reason, class); the latest reason stays readable.
    static void NoteTemplateRefusal(string reason, string detail)
    {
        s_TemplateReason = reason;
        string key = reason + ":" + detail;
        if (s_TemplateRefusals.Find(key) >= 0 || s_TemplateRefusals.Count() >= MAX_TEMPLATE_LOG)
            return;
        s_TemplateRefusals.Insert(key);
        Print("[HollowCountry] " + reason + "; class=" + detail);
    }

    // Denominator = every loaded CfgVehicles House class, as ValidateProductionCoverage counts it.
    static void CountTemplateClasses()
    {
        s_TemplateCovered = 0;
        s_TemplateDenominator = 0;
        int configCount = GetGame().ConfigGetChildrenCount("CfgVehicles");
        if (configCount < 1 || configCount > MAX_CONFIG_CLASSES)
            return;
        for (int i = 0; i < configCount; i++)
        {
            string className;
            if (!GetGame().ConfigGetChildName("CfgVehicles", i, className))
                return;
            if (!GetGame().IsKindOf(className, "House"))
                continue;
            s_TemplateDenominator++;
            HCInteriorTemplateClassRow row = HCInteriorTemplates.ClassRow(className);
            if (row && row.Rooms == "covered")
                s_TemplateCovered++;
            if (s_TemplateDenominator >= MAX_PRODUCTION_CLASSES)
                return;
        }
    }

    static void LogTemplateAdmission()
    {
        if (s_TemplateLogged || !ProductionServer() || !HCInteriorTemplates.Loaded())
            return;
        s_TemplateLogged = true;
        s_TemplateReason = TEMPLATE_READY;
        CountTemplateClasses();
        Print("[HollowCountry] " + TEMPLATE_READY + "; classes=" + s_TemplateCovered.ToString() + "/" + s_TemplateDenominator.ToString());
    }

    static int TemplateAnchorTotal()
    {
        int total = 0;
        foreach (HCInfectedRoomBinding cached : s_TemplateBindings)
        {
            total = total + cached.Survey.Anchors.Count();
        }
        return total;
    }

    // Release the least recently used houses (or any whose object is gone) until one
    // more house with this many anchors fits the 64-house and 256-anchor caps.
    static void EvictTemplates(int incoming)
    {
        while (s_TemplateBindings.Count() > 0 && (s_TemplateBindings.Count() >= MAX_PRODUCTION_HOUSES || TemplateAnchorTotal() + incoming > MAX_TOTAL_ANCHORS))
        {
            int victim = 0;
            for (int i = 0; i < s_TemplateBindings.Count(); i++)
            {
                if (!s_TemplateBindings[i].HouseObject)
                {
                    victim = i;
                    break;
                }
                if (s_TemplateBindings[i].Stamp < s_TemplateBindings[victim].Stamp)
                    victim = i;
            }
            s_TemplateBindings.Remove(victim);
        }
    }

    // Defensive re-check of a loaded template: box within +-512, 1..16 rooms, room boxes in
    // the house box, anchors in their room and at least 1 m apart, evidence present.
    static bool TemplateGeometry(HCInteriorTemplate layout)
    {
        if (!layout || !layout.Box || !layout.Rooms || !layout.Evidence)
            return false;
        if (layout.Rooms.Count() < 1 || layout.Rooms.Count() > MAX_HOUSE_ANCHORS)
            return false;
        // T3 DTO boxes and points are array<float>; BoxValid/VectorValid also check Count() == 3.
        if (!HCInteriorTemplates.BoxValid(layout.Box.Min, layout.Box.Max))
            return false;
        ref array<int> usedIds = new array<int>;
        ref array<vector> usedPositions = new array<vector>;
        foreach (auto room : layout.Rooms)
        {
            if (!room || room.Id < 1 || room.Id > 64 || usedIds.Find(room.Id) >= 0)
                return false;
            if (!HCInteriorTemplates.BoxValid(room.Min, room.Max) || !HCInteriorTemplates.VectorValid(room.Anchor, 512))
                return false;
            // Positive comparisons reject NaN and infinity as well as bad ordering.
            if (!HCInteriorTemplates.Inside(room.Min, layout.Box.Min, layout.Box.Max) || !HCInteriorTemplates.Inside(room.Max, layout.Box.Min, layout.Box.Max))
                return false;
            if (!HCInteriorTemplates.Inside(room.Anchor, room.Min, room.Max))
                return false;
            vector anchorPoint = HCInteriorTemplates.AsVector(room.Anchor);
            foreach (vector previousPoint : usedPositions)
            {
                if (vector.DistanceSq(previousPoint, anchorPoint) < 1)
                    return false;
            }
            usedIds.Insert(room.Id);
            usedPositions.Insert(anchorPoint);
        }
        return true;
    }

    // One house's runtime binding: model-frame anchors only. OrderBindings converts them with
    // ModelToWorld and re-checks the live pose on every order, so a moved house yields nothing.
    static HCInfectedRoomBinding TemplateBinding(House house, HCInteriorTemplate layout)
    {
        string houseType = house.GetType();
        vector orientation = house.GetOrientation();
        if (!HCInfectedStore.ValidPosition(house.GetPosition()) || !HCInfectedStore.ValidPosition(orientation))
        {
            NoteTemplateRefusal("rooms_template_pose", houseType);
            return null;
        }
        // Near-level instances retain model-frame anchors and full ModelToWorld conversion.
        if (!HCInteriorRules.TiltAcceptable(orientation, HCInteriorRules.MAX_HOUSE_TILT_DEGREES))
        {
            NoteTemplateRefusal("tilted", houseType);
            return null;
        }
        if (layout.BuildingClass != houseType || !TemplateGeometry(layout))
        {
            NoteTemplateRefusal("rooms_template_geometry", houseType);
            return null;
        }
        if (layout.Evidence.Count() < 1)
        {
            NoteTemplateRefusal("rooms_template_evidence", houseType);
            return null;
        }
        auto evidence = layout.Evidence[0];
        if (!evidence || evidence.Kind != TEMPLATE_EVIDENCE_KIND || evidence.RunId.Length() < 1 || evidence.Sha256.Length() < 1)
        {
            NoteTemplateRefusal("rooms_template_evidence", houseType);
            return null;
        }
        HCInfectedRoomSurvey survey = new HCInfectedRoomSurvey;
        survey.BuildingClass = houseType;
        survey.EvidenceId = layout.TemplateId;
        survey.Measured = true;
        survey.Revision = 1;
        foreach (auto source : layout.Rooms)
        {
            HCInfectedOwnedProductionRoomAnchor anchor = new HCInfectedOwnedProductionRoomAnchor;
            anchor.Id = source.Id;
            anchor.LocalPosition = HCInteriorTemplates.AsVector(source.Anchor);
            anchor.LocalMin = HCInteriorTemplates.AsVector(source.Min);
            anchor.LocalMax = HCInteriorTemplates.AsVector(source.Max);
            anchor.SourceRunId = evidence.RunId;
            anchor.SourceSha256 = evidence.Sha256;
            anchor.EvidenceKind = TEMPLATE_EVIDENCE_KIND;
            survey.Anchors.Insert(anchor);
        }
        HCInfectedRoomBinding binding = new HCInfectedRoomBinding;
        binding.HouseObject = house;
        binding.Position = house.GetPosition();
        binding.Orientation = orientation;
        binding.Survey = survey;
        return binding;
    }

    static HCInfectedRoomBinding FindTemplateBinding(House house)
    {
        foreach (HCInfectedRoomBinding cached : s_TemplateBindings)
        {
            if (cached.HouseObject == house)
                return cached;
        }
        return null;
    }

    static bool LegacyClaims(House house)
    {
        foreach (HCInfectedRoomBinding claim : s_ProductionBindings)
        {
            if (claim.HouseObject == house)
                return true;
        }
        return false;
    }

    static void DropLegacy(House house)
    {
        int index = 0;
        while (index < s_ProductionBindings.Count())
        {
            if (s_ProductionBindings[index].HouseObject == house)
            {
                s_ProductionBindings.Remove(index);
            }
            else
            {
                index++;
            }
        }
    }

    // A cached template binding for the house: remove it (anchor totals are summed from the cache).
    static void DropTemplate(House house)
    {
        int index = 0;
        while (index < s_TemplateBindings.Count())
        {
            if (s_TemplateBindings[index].HouseObject == house)
            {
                s_TemplateBindings.Remove(index);
            }
            else
            {
                index++;
            }
        }
    }

    static bool ConflictKnown(House house)
    {
        return s_ConflictHouses.Find(house) >= 0;
    }

    // Claimed by both the legacy file and the templates: use neither, and say so once.
    static void MarkConflict(House house)
    {
        DropTemplate(house);
        if (s_ConflictHouses.Count() < MAX_PRODUCTION_HOUSES)
            s_ConflictHouses.Insert(house);
        NoteTemplateRefusal("rooms_conflict", house.GetType());
    }

    // Two live objects of the class within 0.75 m cannot be told apart: refuse both.
    static bool TemplateAmbiguous(House house, array<House> found)
    {
        foreach (House other : found)
        {
            if (other == house || other.GetType() != house.GetType())
                continue;
            if (vector.DistanceSq(other.GetPosition(), house.GetPosition()) <= 0.5625)
                return true;
        }
        return false;
    }

    static void AdmitTemplateHouse(House house, array<House> found)
    {
        string houseType = house.GetType();
        if (ConflictKnown(house))
            return;
        HCInfectedRoomBinding cached = FindTemplateBinding(house);
        if (cached)
        {
            s_BindStamp++;
            cached.Stamp = s_BindStamp;
            return;
        }
        if (LegacyClaims(house))
        {
            DropLegacy(house);
            MarkConflict(house);
            return;
        }
        if (TemplateAmbiguous(house, found))
        {
            NoteTemplateRefusal("rooms_template_ambiguous", houseType);
            return;
        }
        HCInteriorTemplate layout = HCInteriorTemplates.Template(houseType);
        if (!layout)
        {
            NoteTemplateRefusal("rooms_template_missing", houseType);
            return;
        }
        HCInfectedRoomBinding binding = TemplateBinding(house, layout);
        if (!binding)
            return;
        EvictTemplates(binding.Survey.Anchors.Count());
        s_BindStamp++;
        binding.Stamp = s_BindStamp;
        s_TemplateBindings.Insert(binding);
    }

    // The module tick calls this once per tick. Without it the budget is never reset and the cap
    // still holds: past it only cached houses are used. GetTickTime is an elapsed clock, not a tick id.
    static void BeginTick()
    {
        s_BindQueries = 0;
    }

    // A house claimed by the legacy file whose class the templates cover is claimed by both
    // sources: use neither. Decided once, from loaded data alone, before any query or ordering,
    // so the query quota can never let a conflicted house through.
    static void ResolveLegacyConflicts()
    {
        if (s_ConflictsResolved)
            return;
        if (!ProductionServer() || !HCInteriorTemplates.Loaded())
            return;
        if (s_ProductionReason != "rooms_admitted_measurements_path_audio_doors_pending")
            return;
        s_ConflictsResolved = true;
        ref array<House> claimed = new array<House>;
        foreach (HCInfectedRoomBinding legacy : s_ProductionBindings)
        {
            if (!legacy.HouseObject || claimed.Count() >= MAX_PRODUCTION_HOUSES)
                continue;
            HCInteriorTemplateClassRow legacyRow = HCInteriorTemplates.ClassRow(legacy.HouseObject.GetType());
            if (!legacyRow || legacyRow.Rooms != "covered")
                continue;
            if (claimed.Find(legacy.HouseObject) < 0)
                claimed.Insert(legacy.HouseObject);
        }
        foreach (House conflicted : claimed)
        {
            DropLegacy(conflicted);
            DropTemplate(conflicted);
            if (!ConflictKnown(conflicted))
                MarkConflict(conflicted);
        }
    }

    // Called from BuildProductionOrder with an observed clue only. One spatial query per call,
    // at most s_BindQueryCap between BeginTick calls; past the cap the cached houses are used as they are.
    static void BindTemplateHouses(vector observedClue)
    {
        if (!ProductionServer() || !HCInteriorTemplates.Loaded())
            return;
        LogTemplateAdmission();
        if (s_BindQueries >= s_BindQueryCap)
            return;
        s_BindQueries++;
        ref array<Object> candidates = new array<Object>;
        ref array<CargoBase> cargos = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(observedClue, s_BindRadius, candidates, cargos);
        int limit = candidates.Count();
        if (limit > MAX_TEMPLATE_CANDIDATES)
        {
            limit = MAX_TEMPLATE_CANDIDATES;
            NoteTemplateRefusal("rooms_bind_dense", "");
        }
        float radiusSq = s_BindRadius * s_BindRadius;
        ref array<House> found = new array<House>;
        for (int i = 0; i < limit; i++)
        {
            if (found.Count() >= MAX_TEMPLATE_FOUND)
                break;
            House house = House.Cast(candidates[i]);
            if (!house)
                continue;
            // Clue to house origin, whatever the native query's own bounds test returned.
            if (!(vector.DistanceSq(observedClue, house.GetPosition()) <= radiusSq))
                continue;
            HCInteriorTemplateClassRow row = HCInteriorTemplates.ClassRow(house.GetType());
            if (!row || row.Rooms != "covered")
                continue;
            found.Insert(house);
        }
        foreach (House admitted : found)
        {
            AdmitTemplateHouse(admitted, found);
        }
    }

    static void BuildOrder(vector observedClue, int budget, out TVectorArray points)
    {
        points = new TVectorArray;
        if (!GetGame().IsServer() || budget < 1 || budget > 3 || !HCInfectedStore.ValidPosition(observedClue))
            return;
        EnsureDiagnosticLoaded();
        OrderBindings(observedClue, budget, s_Bindings, points);
        // A loaded template pack opts the production sources in; otherwise this consumer stays DIAG only.
        if (points.Count() == 0 && HCInteriorTemplates.Loaded())
        {
            BuildProductionOrder(observedClue, budget, points);
        }
    }

    // Only data: caller still owns Investigation AND NativePackRoutes admission,
    // nav/path checks, expiry, retry budgets and release. No capability is granted.
    // Sources: the legacy production file (once admitted at startup) and the lazily bound
    // class templates. Without a loaded template pack this is the legacy path unchanged.
    static void BuildProductionOrder(vector observedClue, int budget, out TVectorArray points)
    {
        points = new TVectorArray;
        if (!ProductionServer() || budget < 1 || budget > 3 || !HCInfectedStore.ValidPosition(observedClue))
            return;
        // Startup owns the bounded read/config census; AI ticks never load.
        bool legacyReady = s_ProductionReason == "rooms_admitted_measurements_path_audio_doors_pending";
        bool templatesReady = HCInteriorTemplates.Loaded();
        if (!legacyReady && !templatesReady)
            return;
        if (!templatesReady)
        {
            OrderBindings(observedClue, budget, s_ProductionBindings, points);
            return;
        }
        ResolveLegacyConflicts();
        BindTemplateHouses(observedClue);
        ref array<ref HCInfectedRoomBinding> merged = new array<ref HCInfectedRoomBinding>;
        if (legacyReady)
        {
            foreach (HCInfectedRoomBinding legacy : s_ProductionBindings)
            {
                if (!ConflictKnown(legacy.HouseObject))
                    merged.Insert(legacy);
            }
        }
        foreach (HCInfectedRoomBinding bound : s_TemplateBindings)
        {
            if (!ConflictKnown(bound.HouseObject))
                merged.Insert(bound);
        }
        OrderBindings(observedClue, budget, merged, points);
    }

    static void OrderBindings(vector observedClue, int budget, array<ref HCInfectedRoomBinding> bindings, out TVectorArray points)
    {
        points = new TVectorArray;
        HCInfectedRoomBinding selected;
        vector localClue;
        // At most 64 production instances, four diagnostic instances. A clue in
        // overlapping surveys is ambiguous; no world scan or hidden player input.
        foreach (HCInfectedRoomBinding binding : bindings)
        {
            if (!binding.HouseObject || binding.HouseObject.GetType() != binding.Survey.BuildingClass)
                continue;
            if (vector.DistanceSq(binding.Position, binding.HouseObject.GetPosition()) > 0.0001 || vector.DistanceSq(binding.Orientation, binding.HouseObject.GetOrientation()) > 0.0001)
                continue;
            vector localPoint = binding.HouseObject.WorldToModel(observedClue);
            int matches = 0;
            foreach (HCInfectedRoomAnchor room : binding.Survey.Anchors)
            {
                if (room.Contains(localPoint))
                    matches++;
            }
            if (matches > 1 || (matches == 1 && selected))
                return;
            if (matches == 1)
            {
                selected = binding;
                localClue = localPoint;
            }
        }
        if (!selected)
            return;
        ref array<int> used = new array<int>;
        for (int n = 0; n < budget; n++)
        {
            HCInfectedRoomAnchor best;
            float bestDistance;
            bool bestClueRoom;
            foreach (HCInfectedRoomAnchor candidate : selected.Survey.Anchors)
            {
                if (used.Find(candidate.Id) >= 0)
                    continue;
                float distanceSq = vector.DistanceSq(candidate.LocalPosition, localClue);
                bool clueRoom = candidate.Contains(localClue);
                if (!best || HCInfectedPolicy.PreferRoom(clueRoom, bestClueRoom, distanceSq, bestDistance, candidate.Id, best.Id))
                {
                    best = candidate;
                    bestDistance = distanceSq;
                    bestClueRoom = clueRoom;
                }
            }
            if (!best)
                break;
            used.Insert(best.Id);
            vector world = selected.HouseObject.ModelToWorld(best.LocalPosition);
            if (HCInfectedStore.ValidPosition(world))
                points.Insert(world);
        }
    }
}
