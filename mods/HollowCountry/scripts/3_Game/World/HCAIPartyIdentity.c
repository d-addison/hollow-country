// HC-10 / #143-147, #139: immutable Wave 2 identity and custody result contract.
// Native script snapshot scripts-1.30.164289: 1_Core/proto/EnScript.c:380,407
// array Count/Insert. HCWorldLimits.Token is an existing bounded project port.
// No entity, position, inventory, provider or 4_World type in this layer.
// A generation identifies an independently authored population, NEVER a return,
// cooldown, restart or observer change. Reusing a party/cargo ID is refused even
// with a newer generation. Camp/home/route are provenance IDs, not coordinates.
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
// cargo snapshot or permission to restore/reseed a loadout. Missing inventory
// continuity always means no rematerialization. Legacy callbacks remain usable.
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

// Public persistence DTOs, never handed to the provider. Bounded tombstones are
// retained without eviction. Full history refuses new admission, never replay.
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
    int SchemaVersion = 1;
    ref array<ref HCAIPartyCustodyRow> Rows = new array<ref HCAIPartyCustodyRow>();
}

class HCAIPartyCustody
{
    static const int MAX_ROWS = 64;

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

    // 1 = first valid result, 2 = identical duplicate, 0 = quarantined/refused.
    // Preserve the first observation even if a later callback claims a refill.
    static int HCFinish(HCAIPartyCustodyRow row, bool materialized, int survivors)
    {
        if (!row || row.Outcome == "QUARANTINED") { return 0; }
        if (survivors < 0 || survivors > row.ActorCap || (!materialized && survivors != 0))
        {
            row.Outcome = "QUARANTINED";
            return 0;
        }
        if (row.Outcome == "FINISHED")
        {
            if (row.Materialized == materialized && row.Survivors == survivors) { return 2; }
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
