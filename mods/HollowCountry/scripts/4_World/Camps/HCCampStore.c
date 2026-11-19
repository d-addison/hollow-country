// LC-T412..416. Native evidence scripts-1.30.164289:
// 1_Core/proto/EnSystem.c:397 FileExist; 3_Game/Global/Game.c:934
// GetWorldName; persistence delegates to HCV2ThreatStore (World/) and
// HCGroupIO: EnSystem.c:417/425/443/462/525/528/531 read/write/mkdir/copy/delete;
// 3_Game/tools/JsonFileLoader.c:69/85 JSON load/save. No rename API exists.
// 1_Core/proto/EnScript.c:380/394/407 array count/find/insert.
// HC-17 metadata validation: 1_Core/proto/EnString.c:199 Length;
// 1_Core/proto/EnDebug.c:96 Print. Position/ACL limits use HCGroupRules/HCAILimits.
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
    // Legacy JSON zero-fills to empty: the first observed refusal is pending.
    // This is a diagnostic state, never evidence that a visitor body exists.
    string VisitorRefusal;
    ref array<string> Answered = new array<string>(); // paper refs only, no text
}

// HC-17 ownership metadata only. Native containers retain their own inventory
// and persistence. No item IDs, quantities, decorative stash or door health.
class HCBuildingClaimRecord
{
    int GroupId;
    string BuildingId;
    vector Position;
    int ClaimedUtc;
    int LastVisitUtc;
    int AbsentSeconds; // Missing legacy JSON field is 0; schema remains 1.
}

class HCCampData
{
    int Version = 1;
    int ClaimsVersion = 1; // old fire camps get EMPTY claims; never infer buildings
    ref array<ref HCBuildingClaimRecord> Claims = new array<ref HCBuildingClaimRecord>();
    string WorldName;
    int SavedUtc;
    ref array<ref HCCampRecord> Camps = new array<ref HCCampRecord>();
    ref array<ref HCWorldTheftRow> TheftRows = new array<ref HCWorldTheftRow>();
}

class HCCampStore
{
    static const string PATH = "$profile:HollowCountry/camps.json";
    static const int BYTES = 1048576;

    // Duplicate group/building rows are contested migration, never first-wins.
    static bool HCClaimsValid(HCCampData data, int now, int expiryDays = 365)
    {
        if (expiryDays < 7 || expiryDays > 365) { return false; }
        if (!data || data.ClaimsVersion != 1 || !data.Claims || data.Claims.Count() > HCAILimits.Get().MaxCamps) { return false; }
        foreach (HCBuildingClaimRecord claim : data.Claims)
        {
            if (!claim || claim.GroupId < 1 || claim.BuildingId.Length() < 1 || claim.BuildingId.Length() > 512 || !HCGroupRules.PositionValid(claim.Position)) { return false; }
            if (claim.ClaimedUtc < 1 || claim.LastVisitUtc < claim.ClaimedUtc || claim.LastVisitUtc > now) { return false; }
            if (claim.AbsentSeconds < 0 || claim.AbsentSeconds > expiryDays * 86400) { return false; }
            int matches = 0;
            foreach (HCBuildingClaimRecord other : data.Claims)
            {
                if (!other) { return false; }
                if (other.GroupId == claim.GroupId || other.BuildingId == claim.BuildingId) { matches++; }
            }
            if (matches != 1) { return false; }
        }
        return true;
    }

    static bool Valid(HCCampData data, int now)
    {
        if (!data || data.Version != 1 || data.WorldName != GetGame().GetWorldName() || data.SavedUtc < 1 || data.SavedUtc > now) { return false; }
        if (!HCClaimsValid(data, now)) { Print("[HC Plan] HC-17 state=refused reason=claims_schema_or_contested_migration runtime=PENDING"); return false; }
        if (!data.Camps || data.Camps.Count() > HCAILimits.Get().MaxCamps || !data.TheftRows || data.TheftRows.Count() > 1024) { Print("[HC AI] camps state invalid or exceeds AILimits.MaxCamps; load refused"); return false; }
        array<string> groups = new array<string>();
        array<string> ids = new array<string>();
        foreach (HCCampRecord camp : data.Camps)
        {
            if (!camp || !HCWorldLimits.Token(camp.Id) || !HCWorldLimits.Token(camp.GroupId) || !HCWorldLimits.Token(camp.FireRef) || !HCWorldLimits.Token(camp.FireClass) || camp.Tier < 0 || camp.Tier > 3) { return false; }
            if (!HCGroupRules.PositionValid(camp.Position) || groups.Find(camp.GroupId) >= 0 || ids.Find(camp.Id) >= 0) { return false; }
            if (!HCWorldLimits.Strings(camp.Members, HCAILimits.Get().MaxCampItems) || !HCWorldLimits.Strings(camp.Answered, 32) || camp.Flag.Length() > 96 || camp.Signal.Length() > 32) { return false; }
            if (camp.VisitorRefusal != "" && camp.VisitorRefusal != "VISITOR_BODY_NOT_OBSERVED") { return false; }
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

    static void HCClaimsMigrate(HCCampData data)
    {
        // Legacy fire camps are retained verbatim, never inferred as buildings.
        // Nonempty unknown claim schemas remain refused by Valid.
        if (data && data.ClaimsVersion == 0 && (!data.Claims || data.Claims.Count() == 0))
        {
            data.Claims = new array<ref HCBuildingClaimRecord>();
            data.ClaimsVersion = 1;
            Print("[HC Plan] HC-17 claims_schema=1 migrated=empty_legacy runtime=PENDING");
        }
    }

    static HCCampData Load(int now)
    {
        if (now < 1 || !HCV2ThreatStore<HCCampData>.CanOpen(PATH)) { return null; }
        HCCampData data;
        if (FileExist(PATH))
        {
            if (!HCV2ThreatStore<HCCampData>.Load(PATH, BYTES, data)) { return null; }
            HCClaimsMigrate(data);
            if (!Valid(data, now)) { return null; }
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
        if (!data || !HCV2ThreatStore<HCCampData>.CanOpen(PATH)) { return false; }
        data.SavedUtc = now;
        return Valid(data, now) && HCV2ThreatStore<HCCampData>.Save(PATH, data, BYTES);
    }
}
