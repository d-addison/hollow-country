// Original HC DTOs. No provider implementation or assets are included.
class HCXAIEquipment
{
    string ClassName;
    bool InHands = false;
    bool IsMagazine = false;
    int AmmoCount = 0;
}
class HCXAIMission
{
    string MissionId;
    string SiteId;
    int GroupSize = 0;
    string ActorClass;
    string FactionName;
    vector Anchor;
    string SurveySha256;
    string LoadoutSha256;
    ref array<vector> Spawns = new array<vector>();
    ref array<vector> Waypoints = new array<vector>();
    ref array<ref HCXAIEquipment> Equipment = new array<ref HCXAIEquipment>();
}
class HCXAIProfile
{
    int SchemaVersion = 1;
    bool Enabled = true;
    bool Experimental = true;
    bool AllowBuiltinStuckRecovery = true;
    bool ProvisionalBounds = true;
    string SourceCommit = "d84d3c73694969eba2f969e9178a1914e2f1b31d";
    string ProviderVersion = "1.9.84";
    string BuildVersion = "1.30.164289";
    string NativeScriptsSha256 = "09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a";
    string WorldName;
    string WorldSession;
    string WorldSha256;
    string ArtifactSha256;
    string DependencyInventorySha256;
    int MaxGroups = 0;
    int MaxActors = 0;
    int MaxItems = 0;
    int MaxTickWork = 0;
    int MaxLeaseHistory = 0;
    int MaxObservationAgeMs = 0;
    int MaxLeaseMs = 0;
    float CoordinateBound = 0;
    ref HCObserverTransitionPolicy ObserverPolicy = new HCObserverTransitionPolicy();
    ref array<ref HCXAIMission> Missions = new array<ref HCXAIMission>();
}
// Obtained only from the installed trusted server hook, never profile/RPC JSON.
class HCXAIAdmission
{
    string SourceCommit;
    string BuildVersion;
    string NativeScriptsSha256;
    string WorldName;
    string WorldSession;
    string WorldSha256;
    string ArtifactSha256;
    string DependencyInventorySha256;
    int Sequence = 0;
    int ObservedAtMs = -1;
    bool ArtifactBytesVerified = false;
    bool DependencyClosureVerified = false;
    bool ObserverProviderQualified = false;
    bool RoutesQualified = false;
    bool InventoryLedgerQualified = false;
    bool OwnershipReconciled = false;
}
class HCXAIActorSlot
{
    Object Handle;
    bool Attempted = false;
    bool DeleteRequested = false;
    bool DeleteObserved = false;
    bool Gone = false;
    bool DeathObserved = false;
    ref HCObserverTransitionState SpawnGate = new HCObserverTransitionState();
    ref HCObserverTransitionState RetireGate = new HCObserverTransitionState();
}
class HCXAIKill
{
    string ParticipantId;
    string Token;
}
class HCXAILease
{
    string Id;
    string Session;
    string MissionId;
    vector Anchor;
    int RequestedCap = 0;
    int StartedAtMs = 0;
    int ActorReservation = 0;
    int ItemReservation = 0;
    int Cursor = 0;
    int Sequence = 0;
    string ReceiptToken;
    string ReceiptParticipant;
    bool Busy = false;
    bool IntentConfirmed = false;
    bool Retiring = false;
    bool Failed = false;
    bool Released = false;
    eAIGroup Group;
    ref HCXAIMission Objective;
    ref array<ref HCXAIActorSlot> Slots = new array<ref HCXAIActorSlot>();
    ref array<ref HCXAIKill> Kills = new array<ref HCXAIKill>();
}
// One AI_ENCOUNTER bound to an HC site patrol (in memory only; the journal
// keeps the intent row). It owns no actors: the patrol stays the director's.
class HCXAIEncounter
{
    string Id;
    string Session;
    string MissionId;
    string SiteId;
    float Gap = 0;
    string ReceiptToken;
    string ReceiptParticipant;
    bool Released = false;
    bool Ended = false;
    ref array<ref HCXAIKill> Kills = new array<ref HCXAIKill>();
}
// Metadata only: never serialize native actors, groups or inventories.
class HCXAIJournalRow
{
    string Id;
    string WorldSession;
    string Session;
    string MissionId;
    bool Closed = false;
    // Closed alone may be a restart tombstone or a faulted intent. Legacy rows
    // default false: only observed clean retirement may make history reusable.
    bool Prunable = false;
}
class HCXAIJournalData
{
    int SchemaVersion = 1;
    ref array<ref HCXAIJournalRow> Rows = new array<ref HCXAIJournalRow>();
}
// HC sites (patrols, scavenger parties, holdouts) run as native eAIDynamicPatrol
// subclasses. Shipped policy JSON; positions come from stock vanilla map data.
class HCXAISiteLoot
{
    string ClassName;
    int Quantity = 1;
}
class HCXAISite
{
    // Bound from HC43 authored content before native provider admission.
    ref HC43RoleContent ContentRole;
    string Id;
    string Kind;
    string Faction;
    string Loadout;
    int NumberOfAI = HCAILimits.Get().PatrolMin;
    int NumberOfAIMax = HCAILimits.Get().PatrolMax;
    string Behaviour = "LOOP";
    string Speed = "WALK";
    float ActivationRadius = 600;
    int DespawnSeconds = 600;
    int RespawnSeconds = 900;
    ref array<vector> Waypoints = new array<vector>();
    bool Checkpoint = false;
    bool Reviewed = false; // source review only, never runtime acceptance
    vector CheckpointProp;
    string HouseClass;
    vector HousePosition;
    ref array<vector> LocalPoints = new array<vector>();
    string CacheClass;
    vector CacheLocal;
    int CacheCooldownSeconds = 0;
    ref array<ref HCXAISiteLoot> CacheLoot = new array<ref HCXAISiteLoot>();
}
// HC-18 / #143..#147 shared catalog v1. Stable locality IDs are coverage
// identities, SiteIds reference existing reviewed gameplay inputs only. An
// empty SiteIds list is pending route/access work, never a quiet exclusion.
// HC-16 consumes these IDs; authored/selected/observed remain separate.
class HCXAILocality
{
    string Id;
    bool Island = false;
    string Source;
    ref array<string> SiteIds = new array<string>();
}
class HCXAILocalityCatalog
{
    int SchemaVersion = 1;
    bool Enabled = true;
    string WorldName;
    // JsonFileLoader absent ints are zero: resolve via named rule defaults.
    int PageSize = 0;
    int AttemptsPerTick = 0;
    int SelectionIntervalSeconds = 0;
    int OpportunitySeconds = 0;
    int RetrySeconds = 0;
    ref array<ref HCXAILocality> Localities = new array<ref HCXAILocality>();
}
class HCXAILocalityCoverage
{
    string LocalityId;
    int NextSite = 0;
    int LastSelected = 0;
    int LastObserved = 0;
    int PendingSinceSerial = 0;
    int RetryAt = 0;
    bool Pending = true;
    string Refusal = "route_not_reviewed";
}
class HCXAILocalityRotation
{
    int SchemaVersion = 1;
    string WorldName;
    string NextId;
    int SelectionSerial = 0;
    ref array<ref HCXAILocalityCoverage> Rows = new array<ref HCXAILocalityCoverage>();
}
// Gathered natively at startup; never read from profile or RPC data.
class HCXAISiteAdmission
{
    string BuildVersion;
    string WorldName;
    string MissingAddons;
    bool SettingsLoaded = false;
    string Globals;
    string UnfairFaction;
    string MissingLoadout;
    string ObserverPolicy;
    bool Marker = false;
    bool OwnershipReconciled = false;
}
class HCXAIRouteRow
{
    // Additive schema-1 fields: legacy rows have no reusable geometry.
    string ValidityKey;
    ref array<vector> Waypoints = new array<vector>();
    bool OpenRoute = false;
    string Key;
    string SiteId;
    bool Qualified = false;
    string Reason;
}
class HCXAIRouteCache
{
    int SchemaVersion = 1;
    ref array<ref HCXAIRouteRow> Rows = new array<ref HCXAIRouteRow>();
}
// One row per holdout site: State seeding (intent), seeded or looted.
class HCXAICacheRow
{
    string SiteId;
    int Lifecycle = 0;
    string ClassName;
    string State;
    int SeededAt = 0;
    int LootedAt = 0;
    int NextRefillAt = 0;
}
class HCXAICacheJournal
{
    int SchemaVersion = 1;
    ref array<ref HCXAICacheRow> Rows = new array<ref HCXAICacheRow>();
}
// Sites with live actors at the last save; a restart sweeps their "HC:" groups.
class HCXAIOwnedRow
{
    string SiteId;
    int Members = 0;
}
class HCXAIOwnership
{
    int SchemaVersion = 1;
    int Session = 0;
    ref array<ref HCXAIOwnedRow> Rows = new array<ref HCXAIOwnedRow>();
}

// Numeric policy fields share the compiled operator registry. The site rules
// additionally enforce timer holes and cross-field/native safety constraints.
class HCRespawnSiteRegistry
{
    static bool HCPolicyValid(HCXAISitePolicy p)
    {
        if (!HCOperatorSettingsRegistry.HCValid("AISites.SchemaVersion", p.SchemaVersion) || p.SchemaVersion != 1) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AISites.MinPlayerDistance", p.MinPlayerDistance) || p.MinPlayerDistance < 200 || p.MinPlayerDistance > 7500) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AISites.LineOfSightRange", p.LineOfSightRange) || p.LineOfSightRange < 200 || p.LineOfSightRange > 1500) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AISites.MaxLegLength", p.MaxLegLength) || p.MaxLegLength < 50 || p.MaxLegLength > 600) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AISites.CacheClearRadius", p.CacheClearRadius) || p.CacheClearRadius < 100 || p.CacheClearRadius > 1000) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AISites.AIRespawnSeconds", p.AIRespawnSeconds) || p.AIRespawnSeconds < 0 || p.AIRespawnSeconds > 604800) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AISites.PatrolRespawnSeconds", p.PatrolRespawnSeconds) || p.PatrolRespawnSeconds < 0 || p.PatrolRespawnSeconds > 604800) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AISites.HoldoutRespawnSeconds", p.HoldoutRespawnSeconds) || p.HoldoutRespawnSeconds < 0 || p.HoldoutRespawnSeconds > 604800) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AISites.MilitaryRespawnSeconds", p.MilitaryRespawnSeconds) || p.MilitaryRespawnSeconds < 0 || p.MilitaryRespawnSeconds > 604800) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AISites.MemberReplaceSeconds", p.MemberReplaceSeconds) || p.MemberReplaceSeconds < 0 || p.MemberReplaceSeconds > 604800) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AISites.RaidCooldownFloorSeconds", p.RaidCooldownFloorSeconds) || p.RaidCooldownFloorSeconds < 0 || p.RaidCooldownFloorSeconds > 604800) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AISites.ActivationRadiusScale", p.ActivationRadiusScale) || p.ActivationRadiusScale < 0 || p.ActivationRadiusScale > 2.0) { return false; }
        return true;
    }
}

class HCXAISitePolicy
{
    ref HC43ContentManifest HC43;
    int SchemaVersion = 1;
    string WorldName = "chernarusplus";
    string BuildVersion = "1.30.164289";
    string ObserverPolicy = "native-eai";
    int MaxActiveAI = HCAILimits.Get().MaxActiveAI;
    int MaxActiveSites = HCAILimits.Get().MaxActiveSites;
    float MinPlayerDistance = 200;
    float LineOfSightRange = 1000;
    float MaxLegLength = 400;
    float CacheClearRadius = 300;
    // Respawn policy block. Zero means inherit; AIRespawnSeconds=0 uses
    // site.RespawnSeconds for legacy operator profiles. Shipped policy owns timing.
    int AIRespawnSeconds = 900;
    int PatrolRespawnSeconds = 0;
    int HoldoutRespawnSeconds = 0;
    int MilitaryRespawnSeconds = 0;
    int MemberReplaceSeconds = 600; // zero inherits effective full-group delay
    int RaidCooldownFloorSeconds = 0; // optional legacy operator minimum
    float ActivationRadiusScale = 0; // absent/zero means 1.0
    ref array<ref HCXAISite> Sites = new array<ref HCXAISite>();
    // Startup-only bounded joins. Content supplies identities and roles, never
    // routes, actors or runtime receipts; existing qualification stays mandatory.
    bool HCBindContent(HCXAILocalityCatalog catalog)
    {
        if (!HC43) { return true; } // legacy operator policies retain their sites
        int cap = HCXAISiteRules.HCMaxCatalogRows();
        if (!catalog || !catalog.Localities || !Sites) { return false; }
        if (HC43.SchemaVersion != 1 || !HC43.Localities || !HC43.Roles || !HC43.ResidentialClusters) { return false; }
        if (HC43.Localities.Count() > cap || HC43.Roles.Count() > 16 || HC43.ResidentialClusters.Count() > cap || catalog.Localities.Count() > cap || Sites.Count() > cap) { return false; }
        map<string, HC43RoleContent> roles = new map<string, HC43RoleContent>();
        foreach (HC43RoleContent role : HC43.Roles)
        {
            if (!role || !HCXAIRules.Token(role.Id) || !HCXAIRules.Token(role.ProviderFaction) || !HCXAIRules.Token(role.Loadout) || roles.Contains(role.Id)) { return false; }
            roles.Set(role.Id, role);
        }
        int references = 0;
        foreach (HC43LocalityContent checked : HC43.Localities)
        {
            if (!checked || !HCXAIRules.Token(checked.Id) || !checked.SiteIds || !roles.Contains(checked.Role)) { return false; }
            references += checked.SiteIds.Count();
            if (references > cap) { return false; }
        }
        map<string, HCXAISite> sites = new map<string, HCXAISite>();
        foreach (HCXAISite site : Sites) { sites.Set(site.Id, site); }
        map<string, HCXAILocality> localities = new map<string, HCXAILocality>();
        map<string, bool> mapped = new map<string, bool>();
        map<string, string> residentialRoles = new map<string, string>();
        foreach (HC43ResidentialContent residential : HC43.ResidentialClusters)
        {
            if (!residential || !roles.Contains(residential.Role)) { return false; }
            residentialRoles.Set("HC43.ResidentialClusters/" + residential.Id, residential.Role);
        }
        int bound = 0;
        int pending = 0;
        int catalogReferences = 0;
        foreach (HCXAILocality existing : catalog.Localities)
        {
            if (!existing || !existing.SiteIds) { return false; }
            localities.Set(existing.Id, existing);
            catalogReferences += existing.SiteIds.Count();
            if (catalogReferences > cap) { return false; }
            foreach (string existingId : existing.SiteIds)
            {
                mapped.Set(existingId, true);
                // Residential membership comes from the explicit source binding,
                // never a radius proxy or invented access to a nearby house.
                if (!residentialRoles.Contains(existing.Source) || !sites.Contains(existingId)) { continue; }
                HCXAISite residentialSite = sites.Get(existingId);
                residentialSite.ContentRole = roles.Get(residentialRoles.Get(existing.Source));
                residentialSite.Loadout = residentialSite.ContentRole.Loadout;
                bound++;
            }
        }
        foreach (HC43LocalityContent content : HC43.Localities)
        {
            HCXAILocality locality = localities.Get(content.Id);
            if (!locality)
            {
                if (catalog.Localities.Count() >= cap) { return false; }
                locality = new HCXAILocality();
                locality.Id = content.Id;
                locality.Source = content.Source;
                locality.Island = content.Island;
                catalog.Localities.Insert(locality);
                localities.Set(locality.Id, locality);
            }
            foreach (string siteId : content.SiteIds)
            {
                if (!sites.Contains(siteId)) { pending++; continue; } // no fabricated route
                HCXAISite selected = sites.Get(siteId);
                selected.ContentRole = roles.Get(content.Role);
                selected.Loadout = selected.ContentRole.Loadout;
                bound++;
                if (mapped.Contains(siteId)) { continue; }
                if (catalogReferences >= cap) { return false; }
                locality.SiteIds.Insert(siteId);
                catalogReferences++;
                mapped.Set(siteId, true);
            }
        }
        Print("[HC Expansion AI] HC43 content bound=" + bound.ToString() + " pending_site_refs=" + pending.ToString() + " named=" + HC43.Localities.Count().ToString() + " residential=" + HC43.ResidentialClusters.Count().ToString() + " runtime=PENDING");
        return true;
    }
}
