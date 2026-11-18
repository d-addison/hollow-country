// LC-T301 / LC-T401 data only. Native evidence: scripts-1.30.164289,
// 1_Core/proto/EnScript.c:380,385,389,394,407,470 (array operations),
// 1_Core/proto/EnString.c:199,240,448 (Length, IndexOf, Get),
// 1_Core/proto/EnConvert.c:30 (int.ToString),
// 1_Core/proto/EnDebug.c:96 (Print).
// Profile DTOs contain authored world positions and opaque item/journal refs,
// never player identities, player positions, reputation or provider entities.
class HCWorldLimits
{
    // Compatibility for the existing debug contributor (configured at settings load).
    static int HOLDOUTS;
    static int PARTIES;
    static const int SCHEMA = 1;
    static const int PLACES = 64;
    static const int FACTS = 256;
    static const int FACTIONS = 5;
    static const int TERRITORY = 64;
    static const int ROUTE = 16;
    static const int CARRY = 24;
    static const int MEMORIES = 256;
    static const int LEADS = 64;
    static const int GROUP_LEADS = 5;
    static const int SCENES = 8;
    static const int NOTES = 10;
    static const int THEFT_PER_CAMP = 32;
    static const int THEFT = 1024;
    static const int SALVAGE = 64;
    static const int SALVAGE_PARTS = 32;
    static const int SALVAGE_JOURNAL = 64;
    static const int PRESSURE_CAPS = 8;
    static const int STEP_ROWS = 32;
    static const int DAY = 86400;
    static const int FACT_LIFETIME = 604800;

    static bool Admit(int count, int cap, string collection)
    {
        if (count < 0 || count >= cap)
        {
            Print("[HollowCountry] V2 world insert refused collection=" + collection + " cap=" + cap.ToString());
            return false;
        }
        return true;
    }

    static bool Token(string value)
    {
        if (value.Length() < 1 || value.Length() > 96) { return false; }
        string alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.:/";
        for (int tokenIndex = 0; tokenIndex < value.Length(); tokenIndex++)
        {
            if (alphabet.IndexOf(value.Get(tokenIndex)) < 0) { return false; }
        }
        return true;
    }

    static bool Strings(array<string> values, int cap)
    {
        if (!values) { return false; }
        if (values.Count() > cap)
        {
            Admit(values.Count(), cap, "NestedRefs");
            return false;
        }
        foreach (string value : values)
        {
            if (!Token(value)) { return false; }
        }
        return true;
    }

    static bool Position(vector pos)
    {
        return pos[0] >= 0 && pos[0] <= 15360 && pos[1] >= -100 && pos[1] <= 2000 && pos[2] >= 0 && pos[2] <= 15360;
    }

}

class HCWorldMeta
{
    // Unix UTC seconds; Day() is zero-based, downtime counts.
    int SchemaVersion;
    int Epoch;
    int LastTick;
    string BuildId;
}

class HCWorldPlace
{
    string Id;
    string Name;
    vector Position;
}

class HCWorldFact
{
    string Kind;
    string PlaceId;
    int Severity;
    int At;
    int Expires;
}

class HCWorldFaction
{
    string Id;
    string Name;
    string Ethos;
    string ProviderFaction;
    int Strength;
    ref array<string> Territory = new array<string>();
    ref array<string> Hostile = new array<string>();
    ref array<string> Neutral = new array<string>();
    int Alert;
    int LastAlertDecay;
    int LastRegrowth;
}

class HCWorldHoldout
{
    string Id;
    string PlaceId;
    string FactionId;
    string HouseClass;
    vector HousePos;
    string CacheRef;
    int Occupants;
    string State = "DORMANT";
    int Since;
    int ReoccupyAfter;
    string Routine;
}

class HCWorldParty
{
    string Id;
    string FactionId;
    string Kind;
    int Size = 1;
    ref array<string> Route = new array<string>();
    int Edge;
    float Progress;
    ref array<string> Carry = new array<string>();
    string Home;
    int DailyTransfers;
    int TransferDay;
    int LastMoved;
    bool Materialized;
}

class HCWorldSiteMemory
{
    string PlaceId;
    string Event;
    int At;
    int Expires;
}

class HCWorldLead
{
    string Id;
    string Kind;
    string TargetPlaceId;
    string Source;
    string GroupId;
    int Expires;
    string TextId;
}

class HCWorldScene
{
    string Id;
    string SiteId;
    string ChainId;
    int Stage;
    string State;
    int Expires;
    string NoteId;
}

class HCWorldNote
{
    string Id;
    string SceneId;
    string EntityRef;
    int CreatedAt;
    string TextId;
}

class HCWorldCamp
{
    string Id;
    string GroupId;
    string FireRef;
    int Tier;
    // Native ITEM refs only, not group member/player identifiers.
    ref array<string> Members = new array<string>();
    int LastLit;
    string Flag;
    int LastVisit;
    int LastProbe;
    int LastTheft;
    bool NeighboursLost;
}

class HCWorldTheftRow
{
    string Id;
    string CampId;
    string ContainerRef;
    string ItemRef;
    string PartyId;
    int At;
    int Phase;
}

class HCWorldSalvage
{
    string WreckId;
    ref array<string> Remaining = new array<string>();
    ref array<string> Journal = new array<string>();
}

class HCWorldPressureCap
{
    string Kind;
    float Maximum;
}

class HCWorldEscalation
{
    // Day is derived again after load, never a source of elapsed time.
    int Day;
    ref array<ref HCWorldPressureCap> PressureCaps = new array<ref HCWorldPressureCap>();
}

// Stable catalog IDs for later modules: locals, volunteers, scavengers,
// raiders, travellers. AD-03 names are display data, not provider classes.
// Relation: -1 hostile, 0 neutral, +1 same faction. No player standing.
// Static symmetric table in the order above:
//                 locals volunteers scavengers raiders travellers
// locals             +1       0          0       -1        0
// volunteers          0      +1          0       -1        0
// scavengers          0       0         +1       -1        0
// raiders            -1      -1         -1       +1       -1
// travellers          0       0          0       -1       +1
class HCWorldFactionCatalog
{
    static bool Known(string id)
    {
        return id == "locals" || id == "volunteers" || id == "scavengers" || id == "raiders" || id == "travellers";
    }

    static int Relation(string a, string b)
    {
        if (!Known(a) || !Known(b)) { return 0; }
        if (a == b) { return 1; }
        if (a == "raiders" || b == "raiders") { return -1; }
        return 0;
    }

    static HCWorldFaction Make(string id, string name, string ethos)
    {
        HCWorldFaction faction = new HCWorldFaction;
        faction.Id = id;
        faction.Name = name;
        faction.Ethos = ethos;
        faction.Strength = HCAILimits.Get().FactionStrengthMax;
        // ProviderFaction intentionally empty until optional provider ownership.
        array<string> ids = {"locals", "volunteers", "scavengers", "raiders", "travellers"};
        foreach (string other : ids)
        {
            if (other == id) { continue; }
            if (Relation(id, other) < 0) { faction.Hostile.Insert(other); }
            else { faction.Neutral.Insert(other); }
        }
        return faction;
    }

    static void Populate(HCWorldData data)
    {
        data.InsertFaction(Make("locals", "Zimovniki", "Hold-out families; protect home and real caches"));
        data.InsertFaction(Make("volunteers", "Dobrovoltsy", "Police and self-defence volunteers"));
        data.InsertFaction(Make("scavengers", "Sborshchiki", "Pickers; salvage finite existing supplies"));
        data.InsertFaction(Make("raiders", "Volki", "Raiders; hostile to other factions"));
        data.InsertFaction(Make("travellers", "Travellers", "Refugees and lone walkers"));
    }
}

class HCWorldData
{
    ref HCWorldMeta Meta = new HCWorldMeta;
    ref array<ref HCWorldPlace> Places = new array<ref HCWorldPlace>();
    ref array<ref HCWorldFact> Facts = new array<ref HCWorldFact>();
    int FactHead;
    ref array<ref HCWorldFaction> Factions = new array<ref HCWorldFaction>();
    ref array<ref HCWorldHoldout> Holdouts = new array<ref HCWorldHoldout>();
    ref array<ref HCWorldParty> Parties = new array<ref HCWorldParty>();
    ref array<ref HCWorldSiteMemory> SiteMemory = new array<ref HCWorldSiteMemory>();
    int MemoryHead;
    ref array<ref HCWorldLead> Leads = new array<ref HCWorldLead>();
    ref array<ref HCWorldScene> Scenes = new array<ref HCWorldScene>();
    ref array<ref HCWorldNote> Notes = new array<ref HCWorldNote>();
    ref array<ref HCWorldCamp> Camps = new array<ref HCWorldCamp>();
    ref array<ref HCWorldTheftRow> TheftRows = new array<ref HCWorldTheftRow>();
    ref array<ref HCWorldSalvage> Salvage = new array<ref HCWorldSalvage>();
    ref HCWorldEscalation Escalation = new HCWorldEscalation;

    HCWorldPlace Place(string id)
    {
        foreach (HCWorldPlace placeRow : Places)
        {
            if (placeRow && (placeRow.Id == id || placeRow.Name == id)) { return placeRow; }
        }
        return null;
    }

    HCWorldFaction Faction(string id)
    {
        foreach (HCWorldFaction factionRow : Factions)
        {
            if (factionRow && factionRow.Id == id) { return factionRow; }
        }
        return null;
    }

    int OccupiedCount()
    {
        int occupied = 0;
        foreach (HCWorldHoldout occupiedRow : Holdouts)
        {
            if (occupiedRow && occupiedRow.Occupants > 0) { occupied++; }
        }
        return occupied;
    }

    bool PlaceValid(HCWorldPlace row)
    {
        return row && HCWorldLimits.Token(row.Id) && HCWorldLimits.Token(row.Name) && HCWorldLimits.Position(row.Position);
    }

    bool FactValid(HCWorldFact row)
    {
        return row && HCWorldLimits.Token(row.Kind) && Place(row.PlaceId) && row.Severity >= 0 && row.Severity <= 3 && row.At >= Meta.Epoch && row.Expires > row.At && row.Expires - row.At <= HCWorldLimits.FACT_LIFETIME;
    }

    bool FactionValid(HCWorldFaction row)
    {
        if (!row || !HCWorldFactionCatalog.Known(row.Id) || row.Name.Length() < 1 || row.Name.Length() > 64 || row.Ethos.Length() > 160 || row.ProviderFaction.Length() > 96) { return false; }
        if (row.Strength < 0 || row.Strength > HCAILimits.Get().FactionStrengthMax || row.Alert < 0 || row.Alert > 3 || row.LastAlertDecay < 0 || row.LastRegrowth < 0) { return false; }
        if (!HCWorldLimits.Strings(row.Territory, HCWorldLimits.TERRITORY) || !HCWorldLimits.Strings(row.Hostile, HCWorldLimits.FACTIONS) || !HCWorldLimits.Strings(row.Neutral, HCWorldLimits.FACTIONS)) { return false; }
        foreach (string hostileId : row.Hostile)
        {
            if (HCWorldFactionCatalog.Relation(row.Id, hostileId) != -1) { return false; }
        }
        foreach (string neutralId : row.Neutral)
        {
            if (!HCWorldFactionCatalog.Known(neutralId) || HCWorldFactionCatalog.Relation(row.Id, neutralId) != 0) { return false; }
        }
        return true;
    }

    bool HoldoutValid(HCWorldHoldout row)
    {
        if (!row || !HCWorldLimits.Token(row.Id) || !Faction(row.FactionId) || !Place(row.PlaceId) || !HCWorldLimits.Token(row.HouseClass) || !HCWorldLimits.Position(row.HousePos)) { return false; }
        if (row.Occupants < 0 || row.Occupants > HCAILimits.SIZE_CEILING || row.CacheRef.Length() > 96 || row.Routine.Length() > 96 || row.Since < 0 || row.ReoccupyAfter < 0) { return false; }
        if (row.State != "DORMANT" && row.State != "OCCUPIED" && row.State != "ALERT" && row.State != "RAIDED" && row.State != "ABANDONED") { return false; }
        if ((row.State == "RAIDED" || row.State == "ABANDONED" || row.State == "DORMANT") && row.Occupants != 0) { return false; }
        if ((row.State == "OCCUPIED" || row.State == "ALERT") && row.Occupants == 0) { return false; }
        if (row.State == "RAIDED" && row.ReoccupyAfter - row.Since < 7 * HCWorldLimits.DAY) { return false; }
        return true;
    }

    bool PartyValid(HCWorldParty row)
    {
        if (!row || !HCWorldLimits.Token(row.Id) || !Faction(row.FactionId) || row.Size < 1 || row.Size > HCAILimits.SIZE_CEILING || !Place(row.Home)) { return false; }
        if (row.Kind != "PICKER" && row.Kind != "PATROL" && row.Kind != "COURIER" && row.Kind != "VISITOR" && row.Kind != "RAIDER") { return false; }
        if (!HCWorldLimits.Strings(row.Route, HCWorldLimits.ROUTE) || row.Route.Count() < 2 || !HCWorldLimits.Strings(row.Carry, HCWorldLimits.CARRY)) { return false; }
        if (row.Edge < 0 || row.Edge >= row.Route.Count() || !(row.Progress >= 0 && row.Progress < 1) || row.DailyTransfers < 0 || row.DailyTransfers > 6 || row.LastMoved < 0 || row.TransferDay < 0) { return false; }
        foreach (string routePlace : row.Route)
        {
            if (!Place(routePlace)) { return false; }
        }
        return true;
    }

    bool MemoryValid(HCWorldSiteMemory row)
    {
        if (!row || !Place(row.PlaceId) || row.At < Meta.Epoch || row.Expires <= row.At) { return false; }
        return row.Event == "RAIDED" || row.Event == "CACHE_EMPTIED" || row.Event == "SHOTS_HEARD" || row.Event == "BODY_FOUND" || row.Event == "ABANDONED" || row.Event == "STOLEN";
    }

    bool LeadValid(HCWorldLead row)
    {
        if (!row || !HCWorldLimits.Token(row.Id) || !Place(row.TargetPlaceId) || !HCWorldLimits.Token(row.Source) || !HCWorldLimits.Token(row.GroupId) || !HCWorldLimits.Token(row.TextId) || row.Expires < Meta.Epoch) { return false; }
        return row.Kind == "PLACE" || row.Kind == "CACHE" || row.Kind == "EVENT" || row.Kind == "DANGER";
    }

    bool SceneValid(HCWorldScene row)
    {
        return row && HCWorldLimits.Token(row.Id) && HCWorldLimits.Token(row.SiteId) && HCWorldLimits.Token(row.ChainId) && HCWorldLimits.Token(row.State) && row.Stage >= 0 && row.Stage <= 32 && row.Expires >= Meta.Epoch && row.NoteId.Length() <= 96;
    }

    bool NoteValid(HCWorldNote row)
    {
        return row && HCWorldLimits.Token(row.Id) && HCWorldLimits.Token(row.SceneId) && HCWorldLimits.Token(row.EntityRef) && HCWorldLimits.Token(row.TextId) && row.CreatedAt >= Meta.Epoch;
    }

    bool CampValid(HCWorldCamp row)
    {
        return row && HCWorldLimits.Token(row.Id) && HCWorldLimits.Token(row.GroupId) && HCWorldLimits.Token(row.FireRef) && row.Tier >= 0 && row.Tier <= 3 && HCWorldLimits.Strings(row.Members, HCAILimits.Get().MaxCampItems) && row.Flag.Length() <= 96 && row.LastLit >= 0 && row.LastVisit >= 0 && row.LastProbe >= 0 && row.LastTheft >= 0;
    }

    bool TheftValid(HCWorldTheftRow row)
    {
        if (!row || !HCWorldLimits.Token(row.Id) || !HCWorldLimits.Token(row.ContainerRef) || !HCWorldLimits.Token(row.ItemRef) || !HCWorldLimits.Token(row.PartyId) || row.At < Meta.Epoch || row.Phase < 0 || row.Phase > 4) { return false; }
        foreach (HCWorldCamp theftCamp : Camps)
        {
            if (theftCamp.Id == row.CampId) { return true; }
        }
        return false;
    }

    bool SalvageValid(HCWorldSalvage row)
    {
        return row && HCWorldLimits.Token(row.WreckId) && HCWorldLimits.Strings(row.Remaining, HCWorldLimits.SALVAGE_PARTS) && HCWorldLimits.Strings(row.Journal, HCWorldLimits.SALVAGE_JOURNAL);
    }

    bool InsertPlace(HCWorldPlace row)
    {
        if (!PlaceValid(row) || Place(row.Id) || Place(row.Name) || !HCWorldLimits.Admit(Places.Count(), HCWorldLimits.PLACES, "Places")) { return false; }
        Places.Insert(row);
        return true;
    }

    bool InsertFaction(HCWorldFaction row)
    {
        if (!FactionValid(row) || Faction(row.Id) || !HCWorldLimits.Admit(Factions.Count(), HCWorldLimits.FACTIONS, "Factions")) { return false; }
        Factions.Insert(row);
        return true;
    }

    bool InsertFact(HCWorldFact row)
    {
        if (!FactValid(row) || !HCWorldLimits.Admit(Facts.Count(), HCWorldLimits.FACTS, "Facts")) { return false; }
        Facts.Insert(row);
        return true;
    }

    bool AppendFact(HCWorldFact row)
    {
        if (!FactValid(row)) { return false; }
        if (Facts.Count() < HCWorldLimits.FACTS) { return InsertFact(row); }
        // Ring replacement is explicit; an insertion never exceeds the cap.
        Facts.Set(FactHead, row);
        FactHead = (FactHead + 1) % HCWorldLimits.FACTS;
        return true;
    }

    bool InsertHoldout(HCWorldHoldout row)
    {
        if (!HoldoutValid(row) || !HCWorldLimits.Admit(Holdouts.Count(), HCAILimits.Get().MaxHoldouts, "Holdouts")) { return false; }
        foreach (HCWorldHoldout priorHoldout : Holdouts)
        {
            if (priorHoldout.Id == row.Id) { return false; }
        }
        if (row.Occupants > 0 && !HCWorldLimits.Admit(OccupiedCount(), HCAILimits.Get().MaxOccupiedPlaces, "OccupiedHoldouts")) { return false; }
        Holdouts.Insert(row);
        return true;
    }

    bool InsertParty(HCWorldParty row)
    {
        if (!PartyValid(row) || !HCWorldLimits.Admit(Parties.Count(), HCAILimits.Get().MaxParties, "Parties")) { return false; }
        int materialized = 0;
        foreach (HCWorldParty priorParty : Parties)
        {
            if (priorParty.Id == row.Id) { return false; }
            if (priorParty.Materialized) { materialized++; }
        }
        if (row.Materialized && !HCWorldLimits.Admit(materialized, HCAILimits.Get().MaxMaterialized, "MaterializedParties")) { return false; }
        Parties.Insert(row);
        return true;
    }

    bool InsertMemory(HCWorldSiteMemory row)
    {
        if (!MemoryValid(row) || !HCWorldLimits.Admit(SiteMemory.Count(), HCWorldLimits.MEMORIES, "SiteMemory")) { return false; }
        SiteMemory.Insert(row);
        return true;
    }

    bool AppendMemory(HCWorldSiteMemory row)
    {
        if (!MemoryValid(row)) { return false; }
        if (SiteMemory.Count() < HCWorldLimits.MEMORIES) { return InsertMemory(row); }
        SiteMemory.Set(MemoryHead, row);
        MemoryHead = (MemoryHead + 1) % HCWorldLimits.MEMORIES;
        return true;
    }

    bool InsertLead(HCWorldLead row)
    {
        if (!LeadValid(row) || !HCWorldLimits.Admit(Leads.Count(), HCWorldLimits.LEADS, "Leads")) { return false; }
        int groupLeads = 0;
        foreach (HCWorldLead priorLead : Leads)
        {
            if (priorLead.Id == row.Id) { return false; }
            if (priorLead.GroupId == row.GroupId) { groupLeads++; }
        }
        if (!HCWorldLimits.Admit(groupLeads, HCWorldLimits.GROUP_LEADS, "GroupLeads")) { return false; }
        Leads.Insert(row);
        return true;
    }

    bool InsertScene(HCWorldScene row)
    {
        if (!SceneValid(row) || !HCWorldLimits.Admit(Scenes.Count(), HCWorldLimits.SCENES, "Scenes")) { return false; }
        foreach (HCWorldScene priorScene : Scenes)
        {
            if (priorScene.Id == row.Id) { return false; }
        }
        Scenes.Insert(row);
        return true;
    }

    bool InsertNote(HCWorldNote row)
    {
        if (!NoteValid(row) || !HCWorldLimits.Admit(Notes.Count(), HCWorldLimits.NOTES, "Notes")) { return false; }
        foreach (HCWorldNote priorNote : Notes)
        {
            if (priorNote.Id == row.Id || priorNote.SceneId == row.SceneId)
            {
                Print("[HollowCountry] V2 world note refused duplicate id or scene");
                return false;
            }
        }
        Notes.Insert(row);
        return true;
    }

    bool InsertCamp(HCWorldCamp row)
    {
        if (!CampValid(row) || !HCWorldLimits.Admit(Camps.Count(), HCAILimits.Get().MaxCamps, "Camps")) { return false; }
        foreach (HCWorldCamp priorCamp : Camps)
        {
            if (priorCamp.Id == row.Id || priorCamp.GroupId == row.GroupId)
            {
                Print("[HollowCountry] V2 world camp refused duplicate id or group");
                return false;
            }
        }
        Camps.Insert(row);
        return true;
    }

    bool InsertTheft(HCWorldTheftRow row)
    {
        if (!TheftValid(row) || !HCWorldLimits.Admit(TheftRows.Count(), HCWorldLimits.THEFT, "TheftRows")) { return false; }
        int campRows = 0;
        foreach (HCWorldTheftRow priorTheft : TheftRows)
        {
            if (priorTheft.Id == row.Id) { return false; }
            if (priorTheft.CampId == row.CampId) { campRows++; }
        }
        if (!HCWorldLimits.Admit(campRows, HCWorldLimits.THEFT_PER_CAMP, "CampTheftRows")) { return false; }
        TheftRows.Insert(row);
        return true;
    }

    bool InsertSalvage(HCWorldSalvage row)
    {
        if (!SalvageValid(row) || !HCWorldLimits.Admit(Salvage.Count(), HCWorldLimits.SALVAGE, "Salvage")) { return false; }
        foreach (HCWorldSalvage priorSalvage : Salvage)
        {
            if (priorSalvage.WreckId == row.WreckId) { return false; }
        }
        Salvage.Insert(row);
        return true;
    }

    bool AppendTheft(HCWorldTheftRow row)
    {
        if (!TheftValid(row)) { return false; }
        int campCount = 0;
        int oldestIndex = -1;
        int oldestAt = 2147483647;
        for (int theftIndex = 0; theftIndex < TheftRows.Count(); theftIndex++)
        {
            HCWorldTheftRow prior = TheftRows[theftIndex];
            if (prior.Id == row.Id) { return false; }
            if (prior.CampId != row.CampId) { continue; }
            campCount++;
            // Never rotate away pending or quarantined inventory intent.
            if ((prior.Phase == 2 || prior.Phase == 4) && prior.At < oldestAt)
            {
                oldestIndex = theftIndex;
                oldestAt = prior.At;
            }
        }
        if (campCount < HCWorldLimits.THEFT_PER_CAMP) { return InsertTheft(row); }
        if (oldestIndex < 0)
        {
            Print("[HollowCountry] V2 world theft ring full; unresolved rows preserved");
            return false;
        }
        TheftRows.Set(oldestIndex, row);
        return true;
    }

    bool InsertPressureCap(HCWorldPressureCap row)
    {
        if (!row || !HCWorldLimits.Token(row.Kind) || !(row.Maximum >= 0 && row.Maximum <= 12) || !HCWorldLimits.Admit(Escalation.PressureCaps.Count(), HCWorldLimits.PRESSURE_CAPS, "PressureCaps")) { return false; }
        foreach (HCWorldPressureCap priorCap : Escalation.PressureCaps)
        {
            if (priorCap.Kind == row.Kind) { return false; }
        }
        Escalation.PressureCaps.Insert(row);
        return true;
    }

    // Load validation reuses insert admission on an isolated empty ledger. Live
    // simulation never calls this whole-image check once per row.
    static bool Valid(HCWorldData data)
    {
        if (!data || !data.Meta || data.Meta.SchemaVersion != HCWorldLimits.SCHEMA || data.Meta.Epoch < 1 || data.Meta.LastTick < data.Meta.Epoch || data.Meta.BuildId.Length() > 64) { return false; }
        if (!data.Places || !data.Facts || !data.Factions || !data.Holdouts || !data.Parties || !data.SiteMemory || !data.Leads || !data.Scenes || !data.Notes || !data.Camps || !data.TheftRows || !data.Salvage || !data.Escalation || !data.Escalation.PressureCaps) { return false; }
        if (data.Holdouts.Count() > HCAILimits.Get().MaxHoldouts || data.Parties.Count() > HCAILimits.Get().MaxParties || data.Camps.Count() > HCAILimits.Get().MaxCamps || data.OccupiedCount() > HCAILimits.Get().MaxOccupiedPlaces)
        {
            Print("[HC AI] saved world exceeds AILimits; load refused; original preserved");
            return false;
        }
        if (data.Places.Count() > HCWorldLimits.PLACES || data.Factions.Count() != HCWorldLimits.FACTIONS || data.Facts.Count() > HCWorldLimits.FACTS || data.Holdouts.Count() > HCAILimits.Get().MaxHoldouts || data.Parties.Count() > HCAILimits.Get().MaxParties || data.SiteMemory.Count() > HCWorldLimits.MEMORIES || data.Leads.Count() > HCWorldLimits.LEADS || data.Scenes.Count() > HCWorldLimits.SCENES || data.Notes.Count() > HCWorldLimits.NOTES || data.Camps.Count() > HCAILimits.Get().MaxCamps || data.TheftRows.Count() > HCWorldLimits.THEFT || data.Salvage.Count() > HCWorldLimits.SALVAGE || data.Escalation.PressureCaps.Count() > HCWorldLimits.PRESSURE_CAPS) { return false; }
        if (data.FactHead < 0 || data.FactHead >= HCWorldLimits.FACTS || (data.Facts.Count() < HCWorldLimits.FACTS && data.FactHead != 0) || data.MemoryHead < 0 || data.MemoryHead >= HCWorldLimits.MEMORIES || (data.SiteMemory.Count() < HCWorldLimits.MEMORIES && data.MemoryHead != 0)) { return false; }
        HCWorldData check = new HCWorldData;
        check.Meta = data.Meta;
        foreach (HCWorldPlace validPlace : data.Places) { if (!check.InsertPlace(validPlace)) { return false; } }
        foreach (HCWorldFaction validFaction : data.Factions) { if (!check.InsertFaction(validFaction)) { return false; } }
        foreach (HCWorldFact validFact : data.Facts) { if (!check.InsertFact(validFact)) { return false; } }
        foreach (HCWorldHoldout validHoldout : data.Holdouts) { if (!check.InsertHoldout(validHoldout)) { return false; } }
        foreach (HCWorldParty validParty : data.Parties) { if (!check.InsertParty(validParty)) { return false; } }
        foreach (HCWorldSiteMemory validMemory : data.SiteMemory) { if (!check.InsertMemory(validMemory)) { return false; } }
        foreach (HCWorldLead validLead : data.Leads) { if (!check.InsertLead(validLead)) { return false; } }
        foreach (HCWorldScene validScene : data.Scenes) { if (!check.InsertScene(validScene)) { return false; } }
        foreach (HCWorldNote validNote : data.Notes) { if (!check.InsertNote(validNote)) { return false; } }
        foreach (HCWorldCamp validCamp : data.Camps) { if (!check.InsertCamp(validCamp)) { return false; } }
        foreach (HCWorldTheftRow validTheft : data.TheftRows) { if (!check.InsertTheft(validTheft)) { return false; } }
        foreach (HCWorldSalvage validSalvage : data.Salvage) { if (!check.InsertSalvage(validSalvage)) { return false; } }
        foreach (HCWorldPressureCap validCap : data.Escalation.PressureCaps) { if (!check.InsertPressureCap(validCap)) { return false; } }
        return data.Places.Count() > 0 && data.Escalation.Day >= 0;
    }

    static void Town(HCWorldData data, string id, string name, vector position)
    {
        if (data.Place(id)) { return; }
        HCWorldPlace town = new HCWorldPlace;
        town.Id = id;
        town.Name = name;
        town.Position = position;
        data.InsertPlace(town);
    }

    // Append-only additions verified against our existing authored mission data.
    // These are locality anchors, not newly surveyed village centres or geometry.
    // ai/sites.json: police-komarovo Waypoints[0]; holdout-* HousePosition;
    // events/scene-chains.json: scene-kamenka/scene-staroye Stages[0].Objective.Source.
    // W6 #134 completes the requested 30-place catalog using installed config
    // anchors below; position[]={x,z} becomes {x,0,z}, not terrain/placement proof.
    // Startup/load only: <=12 Town calls; <=3 scans of <=64 places per new
    // insertion via existing validation/dedupe. No added tick work.
    static void ExtendPlaces(HCWorldData data)
    {
        if (!data || !data.Places) { return; }
        Town(data, "komarovo", "Komarovo", "3588.9 0 2191.5");
        Town(data, "mogilevka", "Mogilevka", "7562.9 0 5149.57");
        Town(data, "nadezhdino", "Nadezhdino", "5853.87 0 4722.04");
        Town(data, "pogorevka", "Pogorevka", "4446.81 0 6376.18");
        Town(data, "polana", "Polana", "10719.43 0 8035.76");
        Town(data, "kamenka", "Kamenka", "2512.352 0 2054.215");
        Town(data, "staroye", "Staroye", "10676.524 0 4579.396");
        // addons/worlds_chernarusplus.pbo/config.bin: CfgWorlds/ChernarusPlus/Names/Settlement_Bor/position[]
        Town(data, "bor", "Bor", "3316.406 0 4070.966");
        // addons/worlds_chernarusplus.pbo/config.bin: CfgWorlds/ChernarusPlus/Names/Settlement_Dolina/position[]
        Town(data, "dolina", "Dolina", "11285.17 0 6633.58");
        // addons/worlds_chernarusplus.pbo/config.bin: CfgWorlds/ChernarusPlus/Names/Settlement_Sosnovka/position[]
        Town(data, "sosnovka", "Sosnovka", "2556 0 6307");
        // addons/worlds_chernarusplus.pbo/config.bin: CfgWorlds/ChernarusPlus/Names/Settlement_Grishino/position[]
        Town(data, "grishino", "Grishino", "5980 0 10257");
        // addons/worlds_chernarusplus.pbo/config.bin: CfgWorlds/ChernarusPlus/Names/Settlement_Kabanino/position[]
        Town(data, "kabanino", "Kabanino", "5300.71 0 8645.9");
    }

    static HCWorldData Fresh(int now)
    {
        HCWorldData fresh = new HCWorldData;
        fresh.Meta.SchemaVersion = HCWorldLimits.SCHEMA;
        fresh.Meta.Epoch = now;
        fresh.Meta.LastTick = now;
        fresh.Meta.BuildId = HCBuildIdentity.Canonical();
        // Own approximate Chernarus town centres, not spawn/geometry evidence.
        Town(fresh, "chernogorsk", "Chernogorsk", "6700 0 2600");
        Town(fresh, "elektrozavodsk", "Elektrozavodsk", "10400 0 2200");
        Town(fresh, "berezino", "Berezino", "12100 0 9600");
        Town(fresh, "svetloyarsk", "Svetloyarsk", "13900 0 13300");
        Town(fresh, "novodmitrovsk", "Novodmitrovsk", "11500 0 14500");
        Town(fresh, "severograd", "Severograd", "7900 0 12700");
        Town(fresh, "novaya-petrovka", "Novaya-Petrovka", "3400 0 12900");
        Town(fresh, "vybor", "Vybor", "3800 0 8900");
        Town(fresh, "nw-airfield", "NW-Airfield", "4600 0 10400");
        Town(fresh, "stary-sobor", "Stary-Sobor", "6100 0 7700");
        Town(fresh, "novy-sobor", "Novy-Sobor", "7100 0 7700");
        Town(fresh, "gorka", "Gorka", "9600 0 8800");
        Town(fresh, "zelenogorsk", "Zelenogorsk", "2800 0 5300");
        Town(fresh, "pavlovo", "Pavlovo", "1700 0 3800");
        Town(fresh, "balota", "Balota", "4500 0 2500");
        Town(fresh, "green-mountain", "Green-Mountain", "3700 0 6000");
        Town(fresh, "devils-castle", "Devils-Castle", "6900 0 11400");
        Town(fresh, "tisy", "Tisy", "1700 0 14200");
        ExtendPlaces(fresh);
        HCWorldFactionCatalog.Populate(fresh);
        // No invented house catalog, caches, loot or world observations.
        return fresh;
    }
}
