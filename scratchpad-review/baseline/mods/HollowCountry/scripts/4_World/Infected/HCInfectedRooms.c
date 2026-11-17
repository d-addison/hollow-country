// Survey interface, intentionally empty at shipment. Coordinates must be
// measured in DayZDiag; there is no invented house/room geometry in this source.
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

class HCInfectedRoomCatalog
{
    static const string DIAGNOSTIC_PATH = "$profile:HollowCountry/Infected/measured-rooms.json";
    protected static ref array<ref HCInfectedRoomBinding> s_Bindings = new array<ref HCInfectedRoomBinding>;
    protected static bool s_DiagnosticAttempted = false;

    static void Clear()
    {
        s_Bindings.Clear();
        s_DiagnosticAttempted = false;
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
        if (document.Build != "1.30.164289" || document.WorldName != GetGame().GetWorldName())
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
        bool sameBuildWorld = survey.Build == "1.30.164289" && survey.WorldName == GetGame().GetWorldName();
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

    static void BuildOrder(vector observedClue, int budget, out TVectorArray points)
    {
        points = new TVectorArray;
        if (!GetGame().IsServer() || budget < 1 || budget > 3 || !HCInfectedStore.ValidPosition(observedClue))
            return;
        EnsureDiagnosticLoaded();
        HCInfectedRoomBinding selected;
        vector localClue;
        // At most four explicitly bound houses, no world/house scan. A clue in
        // overlapping surveys is ambiguous and gets no semantic extension.
        foreach (HCInfectedRoomBinding binding : s_Bindings)
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
