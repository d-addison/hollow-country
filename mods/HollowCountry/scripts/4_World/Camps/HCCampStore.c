// LC-T412..416. Native evidence scripts-1.30.164289:
// 1_Core/proto/EnSystem.c:397 FileExist; 3_Game/Global/Game.c:934
// GetWorldName; persistence delegates to HCV2ThreatStore (World/) and
// HCGroupIO: EnSystem.c:417/425/443/462/525/528/531 read/write/mkdir/copy/delete;
// 3_Game/tools/JsonFileLoader.c:69/85 JSON load/save. No rename API exists.
// 1_Core/proto/EnScript.c:380/394/407 array count/find/insert.
// Temp intent + backup + copy/readback is fail-closed, NOT atomic rename/fsync.
class HCCampRecord : HCWorldCamp
{
    vector Position;
    string FireClass;
    int LastScan;
    int LastMailbox;
    int Neighbours; // abstract living refugees, bounded by AILimits; never provider bodies
    bool NeighboursSettled;
    int ProbeUntil;
    int ProbePhase; // 0 idle, 1 warned, 2 signs issued; maximum 20 minutes
    int LastSignal;
    string Signal;
    ref array<string> Answered = new array<string>(); // paper refs only, no text
}

class HCCampData
{
    int Version = 1;
    string WorldName;
    int SavedUtc;
    ref array<ref HCCampRecord> Camps = new array<ref HCCampRecord>();
    ref array<ref HCWorldTheftRow> TheftRows = new array<ref HCWorldTheftRow>();
}

class HCCampStore
{
    static const string PATH = "$profile:HollowCountry/camps.json";
    static const int BYTES = 1048576;

    static bool Valid(HCCampData data, int now)
    {
        if (!data || data.Version != 1 || data.WorldName != GetGame().GetWorldName() || data.SavedUtc < 1 || data.SavedUtc > now) { return false; }
        if (!data.Camps || data.Camps.Count() > HCAILimits.Get().MaxCamps || !data.TheftRows || data.TheftRows.Count() > 1024) { Print("[HC AI] camps state invalid or exceeds AILimits.MaxCamps; load refused"); return false; }
        array<string> groups = new array<string>();
        array<string> ids = new array<string>();
        foreach (HCCampRecord camp : data.Camps)
        {
            if (!camp || !HCWorldLimits.Token(camp.Id) || !HCWorldLimits.Token(camp.GroupId) || !HCWorldLimits.Token(camp.FireRef) || !HCWorldLimits.Token(camp.FireClass) || camp.Tier < 0 || camp.Tier > 3) { return false; }
            if (!HCGroupRules.PositionValid(camp.Position) || groups.Find(camp.GroupId) >= 0 || ids.Find(camp.Id) >= 0) { return false; }
            if (!HCWorldLimits.Strings(camp.Members, HCAILimits.Get().MaxCampItems) || !HCWorldLimits.Strings(camp.Answered, 32) || camp.Flag.Length() > 96 || camp.Signal.Length() > 32) { return false; }
            if (camp.Neighbours < 0 || camp.Neighbours > HCAILimits.SIZE_CEILING || (camp.NeighboursLost && camp.Neighbours != 0)) { return false; }
            if (camp.ProbePhase < 0 || camp.ProbePhase > 2 || camp.ProbeUntil < 0 || camp.ProbeUntil > now + 1200) { return false; }
            if (camp.LastLit < 1 || camp.LastLit > now || camp.LastScan < 0 || camp.LastScan > now || camp.LastVisit < 0 || camp.LastVisit > now || camp.LastProbe < 0 || camp.LastProbe > now || camp.LastTheft < 0 || camp.LastTheft > now || camp.LastMailbox < 0 || camp.LastMailbox > now || camp.LastSignal < 0 || camp.LastSignal > now) { return false; }
            groups.Insert(camp.GroupId);
            ids.Insert(camp.Id);
            int theftCount = 0;
            foreach (HCWorldTheftRow theft : data.TheftRows)
            {
                if (!theft || theft.At < 1 || theft.At > now || theft.Phase < 0 || theft.Phase > 4 || theft.Id == "" || theft.ContainerRef == "" || theft.ItemRef == "" || theft.PartyId == "") { return false; }
                if (theft.CampId == camp.Id) { theftCount++; }
            }
            if (theftCount > 32) { return false; }
        }
        foreach (HCWorldTheftRow orphan : data.TheftRows)
        {
            if (!orphan || ids.Find(orphan.CampId) < 0) { return false; }
        }
        return true;
    }

    static HCCampData Load(int now)
    {
        if (now < 1 || !HCV2ThreatStore<HCCampData>.CanOpen(PATH)) { return null; }
        HCCampData data;
        if (FileExist(PATH))
        {
            if (!HCV2ThreatStore<HCCampData>.Load(PATH, BYTES, data) || !Valid(data, now)) { return null; }
            return data;
        }
        data = new HCCampData;
        data.WorldName = GetGame().GetWorldName();
        data.SavedUtc = now;
        if (!HCV2ThreatStore<HCCampData>.Save(PATH, data, BYTES)) { return null; }
        return data;
    }

    static bool Save(HCCampData data, int now)
    {
        data.SavedUtc = now;
        return Valid(data, now) && HCV2ThreatStore<HCCampData>.Save(PATH, data, BYTES);
    }
}
