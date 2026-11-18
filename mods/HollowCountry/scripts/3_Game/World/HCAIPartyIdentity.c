// HC-10 / #143-147, #139: immutable Wave 2 identity and custody result contract.
// Native script snapshot scripts-1.30.164289: 1_Core/proto/EnScript.c:380,407
// array Count/Insert. HCWorldLimits.Token is an existing bounded project port.
// No entity, position, inventory, provider or 4_World type in this layer.
// A generation identifies an independently authored population, NEVER a return,
// cooldown, restart or observer change. Party/cargo IDs exclude concurrent live
// copies; completed leases may return. Camp/home/route are provenance IDs.
class HCAIPartyIdentity
{
    protected string m_PartyId;
    protected string m_CampId;
    protected string m_HomeId;
    protected string m_RouteId;
    protected string m_CargoId;
    protected int m_Generation;

    string HCPartyId() { return m_PartyId; }
    string HCCampId() { return m_CampId; }
    string HCHomeId() { return m_HomeId; }
    string HCRouteId() { return m_RouteId; }
    string HCCargoId() { return m_CargoId; }
    int HCGeneration() { return m_Generation; }

    static bool HCValid(HCAIPartyIdentity identity)
    {
        return identity && identity.HCGeneration() > 0 && HCWorldLimits.Token(identity.HCPartyId()) && HCWorldLimits.Token(identity.HCCampId()) && HCWorldLimits.Token(identity.HCHomeId()) && HCWorldLimits.Token(identity.HCRouteId()) && HCWorldLimits.Token(identity.HCCargoId());
    }

    static HCAIPartyIdentity HCCreate(string partyId, string campId, string homeId, string routeId, string cargoId, int generation)
    {
        HCAIPartyIdentity identity = new HCAIPartyIdentity();
        identity.m_PartyId = partyId;
        identity.m_CampId = campId;
        identity.m_HomeId = homeId;
        identity.m_RouteId = routeId;
        identity.m_CargoId = cargoId;
        identity.m_Generation = generation;
        if (!HCValid(identity)) { return null; }
        return identity;
    }
}

// Detached, immutable provider result. Authority must remain in the server
// director: call ONLY after all live/deferred actors are absent. This is not a
// cargo snapshot or permission to restore/reseed inventory. Cargo remains in
// its owner store; this contract only transfers identity custody.
class HCAIPartyResult
{
    protected ref HCAIPartyIdentity m_Identity;
    protected string m_LeaseId;
    protected bool m_Materialized;
    protected int m_Survivors;

    HCAIPartyIdentity HCIdentity() { return m_Identity; }
    string HCLeaseId() { return m_LeaseId; }
    bool HCMaterialized() { return m_Materialized; }
    int HCSurvivors() { return m_Survivors; }

    static HCAIPartyResult HCCreateResult(HCAIPartyIdentity identity, string leaseId, bool materialized, int survivors)
    {
        if (!HCAIPartyIdentity.HCValid(identity) || !HCWorldLimits.Token(leaseId) || survivors < 0 || survivors > HCAILimits.SIZE_CEILING || (!materialized && survivors != 0)) { return null; }
        HCAIPartyResult result = new HCAIPartyResult();
        result.m_Identity = identity;
        result.m_LeaseId = leaseId;
        result.m_Materialized = materialized;
        result.m_Survivors = survivors;
        return result;
    }
}

// Public persistence DTOs, never handed to the provider. Completed history can
// be evicted; CLAIMED/QUARANTINED rows always exclude a second live copy.
class HCAIPartyCustodyRow
{
    string PartyId;
    string CampId;
    string HomeId;
    string RouteId;
    string CargoId;
    int Generation;
    string LeaseId;
    int ActorCap;
    string Outcome = "CLAIMED";
    bool Materialized;
    int Survivors;
}

class HCAIPartyCustodyData
{
    int SchemaVersion = 2;
    int NextLease = 1;
    ref array<ref HCAIPartyCustodyRow> Rows = new array<ref HCAIPartyCustodyRow>();
}

// Exact previous image for canonical validation before upgrading in memory.
class HCAIPartyCustodyLegacyData
{
    int SchemaVersion = 1;
    ref array<ref HCAIPartyCustodyRow> Rows = new array<ref HCAIPartyCustodyRow>();
}

class HCAIPartyCustody
{
    // Two WORLD_CEILING spans: every configured holdout and party can be live.
    static const int MAX_ROWS = 256;

    static HCAIPartyCustodyRow HCReservation(HCAIPartyIdentity identity, string leaseId, int actorCap)
    {
        if (!HCAIPartyIdentity.HCValid(identity) || !HCWorldLimits.Token(leaseId) || actorCap < 1 || actorCap > HCAILimits.SIZE_CEILING) { return null; }
        HCAIPartyCustodyRow row = new HCAIPartyCustodyRow();
        row.PartyId = identity.HCPartyId();
        row.CampId = identity.HCCampId();
        row.HomeId = identity.HCHomeId();
        row.RouteId = identity.HCRouteId();
        row.CargoId = identity.HCCargoId();
        row.Generation = identity.HCGeneration();
        row.LeaseId = leaseId;
        row.ActorCap = actorCap;
        return row;
    }

    // 1 = first valid result, 2 = already finished, 0 = quarantined/refused.
    // Finished means body absence was confirmed. A late callback cannot undo
    // that confirmation, restore debt or overwrite the first observation.
    static int HCFinish(HCAIPartyCustodyRow row, bool materialized, int survivors)
    {
        if (!row || row.Outcome == "QUARANTINED") { return 0; }
        if (row.Outcome == "FINISHED") { return 2; }
        if (survivors < 0 || survivors > row.ActorCap || (!materialized && survivors != 0))
        {
            row.Outcome = "QUARANTINED";
            return 0;
        }
        if (row.Outcome != "CLAIMED") { row.Outcome = "QUARANTINED"; return 0; }
        row.Materialized = materialized;
        row.Survivors = survivors;
        row.Outcome = "FINISHED";
        return 1;
    }
}
