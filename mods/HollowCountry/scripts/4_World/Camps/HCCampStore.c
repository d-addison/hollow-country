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
    // #212: empty is the legacy hearth provenance. Claim anchors live ONLY
    // inside Claims[].Anchor, never Camps[]; no hearth/respawn is fabricated.
    string AnchorKind;
    string ClaimBuildingId;
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
    int AbsentSeconds; // Missing legacy JSON field is 0.
    int EncounterVersion; // 0 legacy/new claim, 2 durable encounter anchor.
    ref HCCampRecord Anchor; // LastVisit/LastProbe independent of LastVisitUtc.
}

class HCCampData
{
    int Version = 2;
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

    // #212 schema 1 -> 2: retain hearth rows and member presence verbatim.
    // JsonFileLoader zero-fills the new version/ref; only a version-zero row
    // with no anchor may initialise cooldowns. Unknown versions fail closed.
    // Also initialises a freshly authored claim before its first barrier save.
    static bool HCPrepareClaimTargets(HCCampData data)
    {
        if (!data || (data.Version != 1 && data.Version != 2) || !data.Claims || data.Claims.Count() > HCAILimits.Get().MaxCamps) { return false; }
        array<ref HCBuildingClaimRecord> claims = data.Claims;
        for (int claimIndex = 0; claimIndex < claims.Count(); claimIndex++)
        {
            HCBuildingClaimRecord row = claims[claimIndex];
            if (!row) { return false; }
            if (row.EncounterVersion == 0)
            {
                if (row.Anchor) { return false; }
                row.Anchor = new HCCampRecord;
                row.Anchor.Id = "claim-" + row.GroupId.ToString();
                row.Anchor.GroupId = row.GroupId.ToString();
                row.Anchor.Position = row.Position;
                row.Anchor.AnchorKind = "claim";
                row.Anchor.ClaimBuildingId = row.BuildingId;
                // Scheduling capability only; never inserted in hearth Camps.
                row.Anchor.Tier = 3;
                row.EncounterVersion = 2;
            }
            if (row.EncounterVersion != 2 || !row.Anchor) { return false; }
        }
        data.Version = 2;
        return true;
    }

    static bool HCClaimTargetValid(HCBuildingClaimRecord row, int now)
    {
        if (!row || row.EncounterVersion != 2 || !row.Anchor) { return false; }
        HCCampRecord target = row.Anchor;
        if (target.AnchorKind != "claim" || target.ClaimBuildingId != row.BuildingId || target.GroupId != row.GroupId.ToString() || target.Id != "claim-" + row.GroupId.ToString()) { return false; }
        if (vector.DistanceSq(target.Position, row.Position) != 0 || target.Tier != 3) { return false; }
        if (target.FireClass != "" || target.FireRef != "" || target.LastLit != 0) { return false; }
        if (target.LastVisit < 0 || target.LastVisit > now || target.LastProbe < 0 || target.LastProbe > now) { return false; }
        return true;
    }

    // Duplicate group/building rows are contested migration, never first-wins.
    static bool HCClaimsValid(HCCampData data, int now, int expiryDays = 365)
    {
        if (expiryDays < 7 || expiryDays > 365) { return false; }
        if (!data || data.ClaimsVersion != 1 || !data.Claims || data.Claims.Count() > HCAILimits.Get().MaxCamps) { return false; }
        // One pass with seen-sets: a claim is uncontested only when no other
        // row shares its group or building.
        map<int, bool> seenGroups = new map<int, bool>;
        map<string, bool> seenBuildings = new map<string, bool>;
        foreach (HCBuildingClaimRecord claim : data.Claims)
        {
            if (!claim || claim.GroupId < 1 || claim.BuildingId.Length() < 1 || claim.BuildingId.Length() > 512 || !HCGroupRules.PositionValid(claim.Position)) { return false; }
            if (claim.ClaimedUtc < 1 || claim.LastVisitUtc < claim.ClaimedUtc || claim.LastVisitUtc > now) { return false; }
            if (claim.AbsentSeconds < 0 || claim.AbsentSeconds > expiryDays * 86400) { return false; }
            if (seenGroups.Contains(claim.GroupId) || seenBuildings.Contains(claim.BuildingId)) { return false; }
            seenGroups.Insert(claim.GroupId, true);
            seenBuildings.Insert(claim.BuildingId, true);
        }
        return true;
    }

    static bool Valid(HCCampData data, int now)
    {
        if (!data || (data.Version != 1 && data.Version != 2) || data.WorldName != GetGame().GetWorldName() || data.SavedUtc < 1 || data.SavedUtc > now) { return false; }
        if (!HCPrepareClaimTargets(data)) { Print("[HC Plan] claim_targets=refused reason=CLAIM_ANCHOR_SCHEMA runtime=PENDING"); return false; }
        array<ref HCBuildingClaimRecord> claimTargets = data.Claims;
        bool targetsValid = true;
        foreach (HCBuildingClaimRecord claimTarget : claimTargets)
        {
            if (!HCClaimTargetValid(claimTarget, now)) { targetsValid = false; break; }
        }
        if (!targetsValid) { Print("[HC Plan] claim_targets=refused reason=CLAIM_ANCHOR_INVALID runtime=PENDING"); return false; }
        if (!HCClaimsValid(data, now)) { Print("[HC Plan] HC-17 state=refused reason=claims_schema_or_contested_migration runtime=PENDING"); return false; }
        if (!data.Camps || data.Camps.Count() > HCAILimits.Get().MaxCamps || !data.TheftRows || data.TheftRows.Count() > 1024) { Print("[HC AI] camps state invalid or exceeds AILimits.MaxCamps; load refused"); return false; }
        map<string, bool> groups = new map<string, bool>;
        map<string, bool> ids = new map<string, bool>;
        map<string, int> theftCounts = new map<string, int>;
        // Theft rows are checked once; per-camp counts come from this index.
        foreach (HCWorldTheftRow theft : data.TheftRows)
        {
            if (!theft || theft.At < 1 || theft.At > now || theft.Phase < 0 || theft.Phase > 4 || theft.Id == "" || theft.ContainerRef == "" || theft.ItemRef == "" || theft.PartyId == "") { return false; }
            int rowCount = 0;
            theftCounts.Find(theft.CampId, rowCount);
            theftCounts.Set(theft.CampId, rowCount + 1);
        }
        foreach (HCCampRecord camp : data.Camps)
        {
            if (!camp || camp.AnchorKind != "" || camp.ClaimBuildingId != "" || !HCWorldLimits.Token(camp.Id) || !HCWorldLimits.Token(camp.GroupId) || !HCWorldLimits.Token(camp.FireRef) || !HCWorldLimits.Token(camp.FireClass) || camp.Tier < 0 || camp.Tier > 3) { return false; }
            if (!HCGroupRules.PositionValid(camp.Position) || groups.Contains(camp.GroupId) || ids.Contains(camp.Id)) { return false; }
            if (!HCWorldLimits.Strings(camp.Members, HCAILimits.Get().MaxCampItems) || !HCWorldLimits.Strings(camp.Answered, 32) || camp.Flag.Length() > 96 || camp.Signal.Length() > 32) { return false; }
            if (camp.VisitorRefusal != "" && camp.VisitorRefusal != "VISITOR_BODY_NOT_OBSERVED") { return false; }
            if (camp.Neighbours < 0 || camp.Neighbours > HCAILimits.SIZE_CEILING || (camp.NeighboursLost && camp.Neighbours != 0)) { return false; }
            if (camp.ProbePhase < 0 || camp.ProbePhase > 2 || camp.ProbeUntil < 0 || camp.ProbeUntil > now + 1200) { return false; }
            if (camp.LastLit < 1 || camp.LastLit > now || camp.LastScan < 0 || camp.LastScan > now || camp.LastVisit < 0 || camp.LastVisit > now || camp.LastProbe < 0 || camp.LastProbe > now || camp.LastTheft < 0 || camp.LastTheft > now || camp.LastMailbox < 0 || camp.LastMailbox > now || camp.LastSignal < 0 || camp.LastSignal > now) { return false; }
            groups.Insert(camp.GroupId, true);
            ids.Insert(camp.Id, true);
            int theftCount = 0;
            theftCounts.Find(camp.Id, theftCount);
            if (theftCount > 32) { return false; }
        }
        for (int theftIndex = 0; theftIndex < theftCounts.Count(); theftIndex++)
        {
            if (!ids.Contains(theftCounts.GetKey(theftIndex))) { return false; }
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

    static bool CanCheckpoint(HCCampData data, int now)
    {
        if (!data || !HCV2ThreatStore<HCCampData>.CanOpen(PATH)) { return false; }
        data.SavedUtc = now;
        return Valid(data, now);
    }

    static bool Save(HCCampData data, int now)
    {
        if (!data || !HCV2ThreatStore<HCCampData>.CanOpen(PATH)) { return false; }
        data.SavedUtc = now;
        return Valid(data, now) && HCV2ThreatStore<HCCampData>.Save(PATH, data, BYTES);
    }
}
