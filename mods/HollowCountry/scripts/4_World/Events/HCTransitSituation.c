// HC-40 / #146/#147. Two finite content profiles for HC-38, NOT a second
// situation director, population owner, route planner or persistence service.
// Spec/plan/task: HC-19 issues fresh durable identities -> HC-38 intent/store
// barriers -> existing HC-10 lease -> HC-36 verified walking route. The last
// seam is absent in this checkout; source authoring stops at named refusal.
// HC-5/37 remain the sole observed signal, stance and betrayal owners.
//
// Native scripts-1.30.164289 inspected evidence:
// 3_Game/Global/Game.c:1120 IsServer; 3_Game/gameplay.c:636 GetGame;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnScript.c:380 Count. File IO uses bounded HCGroupIO.Read.
// N16 DayZPhysics.c:199/208 rays and :222/228 overlaps are geometry queries,
// NOT a surveyed passable road/entrance corridor or an AI walking guarantee.
// Object.c:287/294 exposes position/set-position; never relocate an actor to
// make this scene work. N17 human move commands are NOT an AI SDK.
// No new distance: reuse admitted HC-36 geometry/proximity constraints once
// available. No world/player scan, routine save, tick or authored prop spawn.

class HCTransitProfile
{
    string Id;
    string Kind;
    int MaxMembers;
    int LifetimeSeconds;
    int MaxExitNodes;
    int Reinforcements;
    bool CollisionBarricades;
    string CorridorPolicy;
    string ExitPolicy;
}

class HCTransitManifest
{
    int SchemaVersion;
    ref array<ref HCTransitProfile> Profiles;
}

class HCTransitSituation
{
    protected ref HCTransitManifest m_Manifest;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected bool m_Opened;
    protected bool m_Closed;
    protected int m_Authored;
    protected string m_Effective = "off";
    protected string m_Reason = "not_started";

    static bool HCProfileValid(HCTransitProfile profile)
    {
        if (!profile) { return false; }
        if (profile.Kind == "roadside")
        {
            if (profile.Id != "hc40-roadside-position") { return false; }
        }
        else if (profile.Kind == "exodus")
        {
            if (profile.Id != "hc40-threatened-exodus") { return false; }
        }
        else { return false; }
        // Missing native JSON ints are zero: refuse rather than invent defaults
        // or silently turn an unbounded/legacy profile into an admitted one.
        if (profile.MaxMembers < 1 || profile.MaxMembers > 6) { return false; }
        if (profile.LifetimeSeconds < 1 || profile.LifetimeSeconds > 3600) { return false; }
        if (profile.MaxExitNodes < 2 || profile.MaxExitNodes > 8) { return false; }
        if (profile.Reinforcements != 0 || profile.CollisionBarricades) { return false; }
        if (profile.CorridorPolicy != "native_clear_road_and_entrances") { return false; }
        return profile.ExitPolicy == "verified_walk_or_refuse";
    }

    static bool HCManifestValid(HCTransitManifest manifest)
    {
        if (!manifest || manifest.SchemaVersion != 1 || !manifest.Profiles) { return false; }
        if (manifest.Profiles.Count() != 2) { return false; }
        HCTransitProfile first = manifest.Profiles[0];
        HCTransitProfile second = manifest.Profiles[1];
        if (!HCProfileValid(first) || !HCProfileValid(second)) { return false; }
        return first.Id != second.Id && first.Kind != second.Kind;
    }

    static HCTransitManifest HCLoad()
    {
        string encoded;
        string error;
        HCTransitManifest manifest;
        if (!HCGroupIO.Read("$mission:hollow-country/events/transit-situations.json", 8192, encoded)) { return null; }
        if (!JsonFileLoader<HCTransitManifest>.LoadData(encoded, manifest, error)) { return null; }
        if (!HCManifestValid(manifest)) { return null; }
        return manifest;
    }

    // Caller already owns the HC-19 chain. Template keys never become story
    // identities; completed/cancelled chains cannot be offered again.
    static string HCIdentity(HCSceneChain chain, HCTransitProfile profile)
    {
        if (!HCProfileValid(profile) || !chain || chain.Complete || chain.Cancelled) { return ""; }
        if (chain.StorySequence < 1 || !HCEventDirector.TextValid(chain.Id, 32)) { return ""; }
        return chain.Id + "-" + profile.Kind;
    }

    // Compose the SINGLE HC-38 situation validator, including terminal phases,
    // lease and legacy sequence rules. No independent transit state schema.
    // This is content validity only; it cannot establish geometry or readiness.
    static bool HCOpportunityValid(HCTransitProfile profile, HCSituationState row, HCStoryProgress progress)
    {
        if (!HCProfileValid(profile) || !row || !progress || !progress.LegacyIds) { return false; }
        if (!HCSituationDirector.HCValid(row, progress)) { return false; }
        if (row.EndsAt - row.DueAt > profile.LifetimeSeconds) { return false; }
        string sourceId = HCStoryPolicy.HCIdentity(row.StorySequence, progress.LegacyIds);
        return row.Id == sourceId + "-" + profile.Kind;
    }

    HCTransitProfile HCFind(string profileId)
    {
        if (!m_Opened || m_Closed || !m_Manifest) { return null; }
        // Validated exactly two rows. No retained cursor or tick is needed.
        if (m_Manifest.Profiles[0].Id == profileId) { return m_Manifest.Profiles[0]; }
        if (m_Manifest.Profiles[1].Id == profileId) { return m_Manifest.Profiles[1]; }
        return null;
    }

    void HCReport(string kind, string phase)
    {
        string authored = "0";
        if (m_Authored == 2) { authored = "1"; }
        string line = "[HC Plan] HC-40 kind=" + kind + " lease=none phase=" + phase;
        line += " state=" + m_Effective + " refusal=" + m_Reason;
        line += " authored=" + authored + " admitted=0 observed=0 count_cap=2 runtime=PENDING";
        Print("" + line);
    }

    // The lead wires HCEventModule to call this once at startup, never from an offer/tick
    // loop. Startup diagnostics only: no module registration or actor ownership.
    void HCOpen(bool enabled)
    {
        if (m_Opened || !GetGame() || !GetGame().IsServer()) { return; }
        m_Opened = true;
        m_Effective = "off";
        m_Reason = "operator_off";
        if (HCV2Admission.Admitted(enabled))
        {
            m_Effective = "refused";
            m_Reason = "TRANSIT_MANIFEST_INVALID";
            m_Manifest = HCLoad();
            if (m_Manifest)
            {
                m_Authored = 2;
                m_Reason = "TRANSIT_PROVIDER_SOURCE_ROUTE_CLEARANCE_UNVERIFIED";
            }
        }
        m_Status.HCPublish(m_Effective, m_Reason);
        HCReport("roadside", m_Effective);
        HCReport("exodus", m_Effective);
    }

    HCOperationalStatus HCStatus() { return m_Status; }

    void HCClose()
    {
        if (!m_Opened || m_Closed) { return; }
        m_Closed = true;
        m_Manifest = null;
        m_Effective = "off";
        m_Reason = "owner_closed";
        m_Status.HCPublish(m_Effective, m_Reason);
        HCReport("roadside", "off");
        HCReport("exodus", "off");
        // No actor, provider override, reservation or inventory to release.
        // HC-38/HC-10 own all future bindings and uncertain-stop reconciliation.
    }
}
