// HC-37 / #146: observed receipts, never simulated combat or inventory.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380,407 Count/Insert;
// :389 Set; EnString.c:199,240,448 Length/IndexOf/Get; EnConvert.c:30 ToString.
// HCEncounterStore reuses verified intent/backup/copy/readback. This journal
// MUST be backed up with world.json, ai-custody.json, camp state and Hive.
// No routine writes: begin/death/finish are synchronous transaction barriers.
class HCTerritoryOutcomeRow
{
    string Id;
    string PlaceId;
    string Survey;
    string LeftLease;
    string RightLease;
    string LeftFaction;
    string RightFaction;
    string LeftParty;
    string RightParty;
    string LeftCargo;
    string RightCargo;
    int Generation;
    // Missing legacy keys zero-fill safely: historical receipts are not replayed.
    int TerritoryEpoch;
    bool TerritoryApplied;
    ref array<bool> LeftDead = new array<bool>;
    ref array<bool> RightDead = new array<bool>;
    int LeftSurvivors = -1;
    int RightSurvivors = -1;
    string State = "OBSERVING";
}

class HCTerritoryOutcomeData
{
    int Version = 1;
    int NextEncounter = 1;
    ref array<ref HCTerritoryOutcomeRow> Rows = new array<ref HCTerritoryOutcomeRow>;
}

class HCTerritoryOutcomes
{
    // Exhaustion refuses new encounters; NEVER prune completion identities to
    // obtain more fights. A measured compaction protocol is future work.
    // <=128 small receipts also fit HCEncounterStore's 256 KiB image limit
    // with maximum-length tokens and both SIZE_CEILING actor arrays.
    static const int MAX_ROWS = 128;

    // Run on the bounded persisted image: the native load zero-fills absent int
    // keys (only ints observed). A real stored 0/0 is valid; missing survivor
    // keys never prove NONE_REMAIN. HCFactionConflict.OnStart calls this on the
    // raw text of the encounter-store load.
    static bool HCFieldsPresent(string text)
    {
        return HCJsonFields.Every(text, "LeftSurvivors", 3) && HCJsonFields.Every(text, "RightSurvivors", 3);
    }

    static bool HCSamePair(HCTerritoryOutcomeRow row, string left, string right)
    {
        return (row.LeftLease == left && row.RightLease == right) || (row.LeftLease == right && row.RightLease == left);
    }

    static int HCDeaths(array<bool> slots)
    {
        int count = 0;
        foreach (bool dead : slots) { if (dead) { count++; } }
        return count;
    }

    // Called only after the owner observed a bound real body IsAlive()==false.
    // Slot identity, including the zero-death case, is retained across retries.
    static bool HCDeath(HCTerritoryOutcomeRow row, int side, int slot)
    {
        if (!row || row.State != "OBSERVING" || side < 0 || side > 1 || slot < 0) { return false; }
        array<bool> slots = row.LeftDead;
        if (side == 1) { slots = row.RightDead; }
        if (slot >= slots.Count() || slots[slot]) { return false; }
        slots.Set(slot, true);
        return true;
    }

    static string HCOutcome(HCTerritoryOutcomeRow row)
    {
        if (row.LeftSurvivors < 0 || row.RightSurvivors < 0) { return row.State; }
        if (row.LeftSurvivors > 0 && row.RightSurvivors > 0) { return "BOTH_REMAIN"; }
        if (row.LeftSurvivors > 0) { return "LEFT_REMAINS"; }
        if (row.RightSurvivors > 0) { return "RIGHT_REMAINS"; }
        return "NONE_REMAIN";
    }

    static bool HCResolve(HCTerritoryOutcomeRow row, int left, int right)
    {
        if (!row || row.State != "OBSERVING" || left < 0 || right < 0) { return false; }
        if (left != row.LeftDead.Count() - HCDeaths(row.LeftDead)) { return false; }
        if (right != row.RightDead.Count() - HCDeaths(row.RightDead)) { return false; }
        row.LeftSurvivors = left;
        row.RightSurvivors = right;
        row.State = HCOutcome(row);
        return true;
    }

    static int HCRecover(HCTerritoryOutcomeData data)
    {
        int unknown = 0;
        foreach (HCTerritoryOutcomeRow row : data.Rows)
        {
            if (row.State != "OBSERVING") { continue; }
            row.State = "UNKNOWN_RESTART";
            unknown++;
        }
        return unknown;
    }

    static bool HCHash(string value)
    {
        if (value.Length() != 64) { return false; }
        string alphabet = "0123456789abcdef";
        for (int index = 0; index < value.Length(); index++)
        {
            if (alphabet.IndexOf(value.Get(index)) < 0) { return false; }
        }
        return true;
    }

    static bool HCValid(HCTerritoryOutcomeData data)
    {
        if (!data || data.Version != 1 || !data.Rows || data.Rows.Count() > MAX_ROWS) { return false; }
        if (data.NextEncounter != data.Rows.Count() + 1) { return false; }
        int observing = 0;
        int sequence = 1;
        foreach (HCTerritoryOutcomeRow row : data.Rows)
        {
            if (!row || row.Id != "conflict:" + sequence.ToString() || row.Generation < 1) { return false; }
            sequence++;
            if (!HCWorldLimits.Token(row.PlaceId) || !HCHash(row.Survey)) { return false; }
            if (!HCWorldLimits.Token(row.LeftLease) || !HCWorldLimits.Token(row.RightLease) || row.LeftLease == row.RightLease) { return false; }
            if (!HCWorldLimits.Token(row.LeftParty) || !HCWorldLimits.Token(row.RightParty) || row.LeftParty == row.RightParty) { return false; }
            if (!HCWorldLimits.Token(row.LeftCargo) || !HCWorldLimits.Token(row.RightCargo) || row.LeftCargo == row.RightCargo) { return false; }
            if (HCWorldFactionCatalog.Relation(row.LeftFaction, row.RightFaction) != -1) { return false; }
            if (!row.LeftDead || !row.RightDead) { return false; }
            if (row.LeftDead.Count() < 1 || row.LeftDead.Count() > HCAILimits.SIZE_CEILING) { return false; }
            if (row.RightDead.Count() < 1 || row.RightDead.Count() > HCAILimits.SIZE_CEILING) { return false; }
            if (row.State == "OBSERVING" || row.State == "UNKNOWN_RESTART" || row.State == "UNKNOWN_STOP")
            {
                if (row.LeftSurvivors != -1 || row.RightSurvivors != -1) { return false; }
                if (row.State == "OBSERVING") { observing++; }
            }
            else
            {
                if (row.LeftSurvivors != row.LeftDead.Count() - HCDeaths(row.LeftDead)) { return false; }
                if (row.RightSurvivors != row.RightDead.Count() - HCDeaths(row.RightDead)) { return false; }
                if (row.State != HCOutcome(row)) { return false; }
            }
        }
        return observing <= 1;
    }
}

// Trusted server-only integration port. A setting, client assertion, authored
// cell or bool on a profile is never a survey/ownership/disengagement receipt.
// Expansion sources were absent in this worker; default refusal is deliberate.
// Lead implements these three methods after inspecting installed provider APIs.
class HCFactionCombatPort
{
    bool HCSurveyed(string placeId, string survey) { return false; }
    // Verify exact current lease/faction membership AND this surveyed site's
    // admitted route/actor connection. An arbitrary remote patrol is refused.
    bool HCOwns(string lease, string faction, Object actor, string placeId, string survey) { return false; }
    bool HCDisengaged(string encounter) { return false; }
    bool HCOffer(string placeId, string leftFaction, string rightFaction) { return false; }
    bool HCActiveAt(string placeId) { return false; }
}

// #146 data-only policy. Holdings are finite claims, never body or loot grants.
// Native EnScript.c:380 Count, :394 Find, :407 Insert, :463 Remove.
class HCConflictPolicy
{
    static bool HCOpposed(HCWorldFaction left, HCWorldFaction right, string cell)
    {
        if (!left || !right || left.Id == right.Id || left.Strength < 1 || right.Strength < 1) { return false; }
        if (left.Hostile.Find(right.Id) < 0 || right.Hostile.Find(left.Id) < 0) { return false; }
        return left.Territory.Find(cell) >= 0 && right.Territory.Find(cell) >= 0;
    }

    static string HCWinner(HCWorldFaction left, HCWorldFaction right)
    {
        if (left.Strength > right.Strength) { return left.Id; }
        if (right.Strength > left.Strength) { return right.Id; }
        return "";
    }

    static bool HCTransfer(HCWorldFaction winner, HCWorldFaction loser, string cell)
    {
        if (!winner || !loser || winner == loser || winner.Strength < 1) { return false; }
        int lost = loser.Territory.Find(cell);
        if (lost < 0) { return false; }
        if (winner.Territory.Find(cell) < 0)
        {
            if (winner.Territory.Count() >= HCWorldLimits.TERRITORY) { return false; }
            winner.Territory.Insert(cell);
        }
        loser.Territory.Remove(lost);
        return true;
    }
}

class HCConflictPlaceStamp
{
    string Id;
    int At;
}

// Separate durable quota intent: a crash may consume an opportunity, never
// refund one. Rolling world facts cannot grant additional daily outcomes.
class HCConflictQuota
{
    int Version = 1;
    int Day = -1;
    int Count;
    ref array<ref HCConflictPlaceStamp> Rows = new array<ref HCConflictPlaceStamp>;

    static bool HCValid(HCConflictQuota data, string encoded)
    {
        if (!data || data.Version != 1 || data.Day < -1 || data.Count < 0 || data.Count > 8) { return false; }
        if (!data.Rows || data.Rows.Count() > HCWorldLimits.PLACES) { return false; }
        if (encoded != "")
        {
            if (!HCJsonFields.Every(encoded, "Day", 1) || !HCJsonFields.Every(encoded, "Count", 1)) { return false; }
            if (!HCJsonFields.Every(encoded, "At", 3)) { return false; }
        }
        map<string, bool> ids = new map<string, bool>;
        array<ref HCConflictPlaceStamp> rows = data.Rows;
        foreach (HCConflictPlaceStamp row : rows)
        {
            if (!row || !HCWorldLimits.Token(row.Id) || row.At < 1 || ids.Contains(row.Id)) { return false; }
            ids.Set(row.Id, true);
        }
        return true;
    }

    static bool HCReserve(HCConflictQuota data, HCConflictConfig config, string place, int now)
    {
        if (!data || !config || !config.Enabled || now < 1 || !HCWorldLimits.Token(place)) { return false; }
        int day = Math.Floor(now / HCWorldLimits.DAY);
        if (day < data.Day) { return false; }
        if (day == data.Day && data.Count >= config.MaxDailyOutcomes) { return false; }
        HCConflictPlaceStamp stamp;
        array<ref HCConflictPlaceStamp> rows = data.Rows;
        foreach (HCConflictPlaceStamp prior : rows)
        {
            if (prior.Id == place) { stamp = prior; break; }
        }
        if (stamp && (now <= stamp.At || now - stamp.At < config.CooldownSeconds)) { return false; }
        if (!stamp)
        {
            if (rows.Count() >= HCWorldLimits.PLACES) { return false; }
            stamp = new HCConflictPlaceStamp;
            stamp.Id = place;
            rows.Insert(stamp);
        }
        if (day != data.Day) { data.Day = day; data.Count = 0; }
        data.Count++;
        stamp.At = now;
        return true;
    }
}
