// Owner-only test tool, never an AI/player gameplay movement controller. runtime=PENDING.
// Installed native scripts-1.30.164289 evidence:
// 3_Game/Entities/Object.c:287,294,517 GetPosition/SetPosition/IsAlive;
// 4_World/Plugins/PluginBase/PluginDeveloper/DeveloperTeleport.c:143 native player SetPosition use;
// 3_Game/human.c:1528 GetCommand_Vehicle; Entities/Man.c:63 IsUnconscious;
// 4_World/Entities/ManBase/PlayerBase.c:2219 IsRestrained;
// 3_Game/Global/Game.c:449,578,594,611 config reads; :931,934 world/world name;
// :1120 IsServer; :1176 SurfaceY; :1196,1197 SurfaceIsSea/SurfaceIsPond;
// :1333 IsBoxColliding (object bounding geometry, NOT a surveyed walkability proof).
// 3_Game/Global/World.c:82 GetWorldSize; gameplay.c:636 GetGame;
// 1_Core/proto/EnScript.c:380,385,389,394,407 Count/Clear/Set/Find/Insert;
// EnMath.c:553,566,540 Min/Max/Clamp; EnMath3D.c:18 Vector;
// EnString.c:171,199 ToLower/Length; EnConvert.c:30,123 ToString/vector.Zero;
// EnSystem.c:397 FileExist; EnDebug.c:96 Print.
// 3_Game/Global/Game.c:923 GetObjectsAtPosition (horizontal circle);
// 3_Game/Entities/Object.c:370 GetCollisionBox, :642 IsBuilding, :874 WorldToModel;
// Entities/Building.c:267 IsBuilding override. No geometry/world mutation.
// JSON and core budgets reuse their owners' native citations. No Expansion API.
// MaxDestinations <=256 and PageSize <=64 are wire/schema ceilings. Configurable
// work uses HCTickWork plus HCPerfSlices; no new module or budget consumer slot.
class HCAdminTeleportConfig
{
    int Version = 1;
    int ConfigBytes = 4096;
    int SiteBytes = 262144;
    bool Enabled = true;
    bool IncludeActiveSituations = true;
    float BuildingQueryRadiusM = 100;
    int MaxBuildingObjects = 128;
    int MaxDestinations = 256;
    int MaxNameEntries = 512;
    int RowsPerTick = 8;
    int PageSize = 32;
    int SearchAttempts = 16;
    float SearchStepM = 4;
    float GroundOffsetM = 0.2;
    float ClearanceWidthM = 1;
    float ClearanceHeightM = 2;
    float MaxSlopeDeltaM = 0.4;
    float BoundaryMarginM = 2;

    void HCApply(HCAdminTeleportConfig decoded, string encoded)
    {
        if (HCJsonFields.Has(encoded, "ConfigBytes")) { ConfigBytes = decoded.ConfigBytes; }
        if (HCJsonFields.Has(encoded, "SiteBytes")) { SiteBytes = decoded.SiteBytes; }
        if (HCJsonFields.Has(encoded, "Version")) { Version = decoded.Version; }
        if (HCJsonFields.Has(encoded, "IncludeActiveSituations")) { IncludeActiveSituations = decoded.IncludeActiveSituations; }
        if (HCJsonFields.Has(encoded, "BuildingQueryRadiusM")) { BuildingQueryRadiusM = decoded.BuildingQueryRadiusM; }
        if (HCJsonFields.Has(encoded, "MaxBuildingObjects")) { MaxBuildingObjects = decoded.MaxBuildingObjects; }
        if (HCJsonFields.Has(encoded, "Enabled")) { Enabled = decoded.Enabled; }
        if (HCJsonFields.Has(encoded, "MaxDestinations")) { MaxDestinations = decoded.MaxDestinations; }
        if (HCJsonFields.Has(encoded, "MaxNameEntries")) { MaxNameEntries = decoded.MaxNameEntries; }
        if (HCJsonFields.Has(encoded, "RowsPerTick")) { RowsPerTick = decoded.RowsPerTick; }
        if (HCJsonFields.Has(encoded, "PageSize")) { PageSize = decoded.PageSize; }
        if (HCJsonFields.Has(encoded, "SearchAttempts")) { SearchAttempts = decoded.SearchAttempts; }
        if (HCJsonFields.Has(encoded, "SearchStepM")) { SearchStepM = decoded.SearchStepM; }
        if (HCJsonFields.Has(encoded, "GroundOffsetM")) { GroundOffsetM = decoded.GroundOffsetM; }
        if (HCJsonFields.Has(encoded, "ClearanceWidthM")) { ClearanceWidthM = decoded.ClearanceWidthM; }
        if (HCJsonFields.Has(encoded, "ClearanceHeightM")) { ClearanceHeightM = decoded.ClearanceHeightM; }
        if (HCJsonFields.Has(encoded, "MaxSlopeDeltaM")) { MaxSlopeDeltaM = decoded.MaxSlopeDeltaM; }
        if (HCJsonFields.Has(encoded, "BoundaryMarginM")) { BoundaryMarginM = decoded.BoundaryMarginM; }
    }

    bool HCValid()
    {
        if (!(ConfigBytes == 4096)) { return false; }
        if (!(SiteBytes >= 4096 && SiteBytes <= 1048576)) { return false; }
        if (!(BuildingQueryRadiusM >= 25 && BuildingQueryRadiusM <= 500)) { return false; }
        if (!(MaxBuildingObjects >= 1 && MaxBuildingObjects <= 512)) { return false; }
        if (!(Version >= 1 && Version <= 1)) { return false; }
        if (!(MaxDestinations >= 1 && MaxDestinations <= 256)) { return false; }
        if (!(MaxNameEntries >= 1 && MaxNameEntries <= 2048)) { return false; }
        if (!(RowsPerTick >= 1 && RowsPerTick <= 32)) { return false; }
        if (!(PageSize >= 1 && PageSize <= 64)) { return false; }
        if (!(SearchAttempts >= 1 && SearchAttempts <= 64)) { return false; }
        if (!(SearchStepM >= 1 && SearchStepM <= 25)) { return false; }
        if (!(GroundOffsetM >= 0.05 && GroundOffsetM <= 1)) { return false; }
        if (!(ClearanceWidthM >= 0.5 && ClearanceWidthM <= 3)) { return false; }
        if (!(ClearanceHeightM >= 1.8 && ClearanceHeightM <= 4)) { return false; }
        if (!(MaxSlopeDeltaM >= 0.1 && MaxSlopeDeltaM <= 1)) { return false; }
        if (!(BoundaryMarginM >= 1 && BoundaryMarginM <= 10)) { return false; }
        return true;
    }
}

// Read-only projection of HC-authored sites.json. No third-party source/content.
class HCAdminTeleportSite
{
    string Id;
    ref array<vector> Waypoints;
}
class HCAdminTeleportSites
{
    int SchemaVersion;
    string WorldName;
    ref array<ref HCAdminTeleportSite> Sites;
}
class HCAdminTeleportDestination
{
    string Label;
    vector Position;
}

class HCAdminTeleport
{
    static const string CONFIG = "$profile:HollowCountry/admin-teleport.json";
    protected ref HCAdminTeleportConfig m_Config;
    protected ref array<ref HCAdminTeleportDestination> m_Destinations = new array<ref HCAdminTeleportDestination>;
    protected ref HCAdminTeleportSites m_Sites;
    protected ref HCEventRuntimeState m_EventSnapshot;
    protected ref HCWorkBudget m_Work = new HCPerfSlices("AdminTeleport");
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected bool m_Enabled;
    protected bool m_Complete;
    protected bool m_CatalogStarted;
    protected int m_Stage;
    protected int m_Cursor;
    protected int m_NameCount;
    protected string m_Names;
    protected string m_Fault;
    protected string m_LastRefusal;

    protected void HCRefuse(string reason)
    {
        if (reason == m_LastRefusal) { return; }
        m_LastRefusal = reason;
        Print("[HC AdminTeleport] reason=" + reason + " runtime=PENDING");
    }

    void HCStart(bool controls)
    {
        m_Config = new HCAdminTeleportConfig;
        if (!controls || FileExist("$profile:HollowCountry/acceptance/AdminTeleport.disable"))
        {
            Print(HCV2Admission.Line("AdminTeleport", false, "w67-admintp", false) + " runtime=PENDING");
            return;
        }
        if (!HCV2ThreatStore<HCAdminTeleportConfig>.CanOpen(HCAdminTeleport.CONFIG))
        {
            m_Enabled = true;
            m_Fault = "teleport-config-recovery-required";
            Print(HCV2Admission.Line("AdminTeleport", true, "w67-admintp", false) + " runtime=PENDING");
            HCRefuse(m_Fault);
            return;
        }
        HCAdminTeleportConfig decoded;
        if (FileExist(HCAdminTeleport.CONFIG))
        {
            string encoded;
            if (!HCGroupIO.Read(HCAdminTeleport.CONFIG, m_Config.ConfigBytes, encoded) || !HCV2ThreatStore<HCAdminTeleportConfig>.Load(HCAdminTeleport.CONFIG, m_Config.ConfigBytes, decoded)) { m_Fault = "teleport-config-load"; }
            else { m_Config.HCApply(decoded, encoded); }
        }
        else if (!HCV2ThreatStore<HCAdminTeleportConfig>.Save(HCAdminTeleport.CONFIG, m_Config, m_Config.ConfigBytes)) { m_Fault = "teleport-config-save"; }
        m_Enabled = m_Config.Enabled;
        Print(HCV2Admission.Line("AdminTeleport", m_Enabled, "w67-admintp", false) + " runtime=PENDING");
        if (!m_Config.HCValid()) { m_Fault = "teleport-config-range"; }
        if (m_Fault != "") { HCRefuse(m_Fault); return; }
        if (!m_Enabled) { return; }
        string sitesPath = "$profile:HollowCountry/expansion-ai-sites.json";
        if (!FileExist(sitesPath)) { sitesPath = "$mission:hollow-country/ai/sites.json"; }
        if (!HCV2ThreatStore<HCAdminTeleportSites>.Load(sitesPath, m_Config.SiteBytes, m_Sites)) { m_Fault = "teleport-sites-load"; }
        string currentWorld = GetGame().GetWorldName();
        currentWorld.ToLower();
        if (!m_Sites || m_Sites.SchemaVersion != 1 || m_Sites.WorldName != currentWorld || !m_Sites.Sites || m_Sites.Sites.Count() > m_Config.MaxDestinations)
        {
            m_Fault = "teleport-sites-invalid-or-missing";
            m_Sites = null;
        }
        if (m_Fault != "") { HCRefuse(m_Fault); }
        m_CatalogStarted = true;
        m_Names = "CfgWorlds " + GetGame().GetWorldName() + " Names";
        m_NameCount = Math.Clamp(GetGame().ConfigGetChildrenCount(m_Names), 0, m_Config.MaxNameEntries);
    }

    HCOperationalStatus HCGetOperationalStatus()
    {
        string fault = m_Fault;
        if (m_Enabled && !m_Complete && fault == "") { fault = "teleport-destinations-building"; }
        HCModuleReadiness.HCDerive(m_Status, m_Enabled, "", fault, "teleport-server-catalog-built_native_pending");
        return m_Status;
    }

    protected void HCAdd(string label, vector position)
    {
        if (m_Destinations.Count() >= m_Config.MaxDestinations || label == "" || label.Length() > 96) { return; }
        float size = GetGame().GetWorld().GetWorldSize();
        if (!(position[0] > 0 && position[2] > 0 && position[0] < size && position[2] < size)) { return; }
        HCAdminTeleportDestination entry = new HCAdminTeleportDestination;
        entry.Label = label;
        entry.Position = position;
        m_Destinations.Insert(entry);
    }

    // A refresh keeps indices frozen until the next explicit list request. No
    // client supplied coordinates, entity handles, identity or target player.
    bool HCRefresh()
    {
        if (!m_Enabled || !m_CatalogStarted) { return false; }
        m_Destinations.Clear();
        m_EventSnapshot = null;
        m_Stage = 0;
        m_Cursor = 0;
        m_Complete = false;
        return true;
    }

    void HCStep()
    {
        if (!m_CatalogStarted || !m_Enabled || m_Complete) { return; }
        m_Work.HCReset(m_Config.RowsPerTick);
        while (m_Work.HCContinue())
        {
            if (!HCServer.Get().HCTickWork().HCTake(1)) { return; }
            if (m_Destinations.Count() >= m_Config.MaxDestinations) { m_Complete = true; return; }
            if (m_Stage == 0)
            {
                HCWorldIncidents incidents;
                if (m_Config.IncludeActiveSituations) { incidents = HCWorldIncidents.HCGet(); }
                if (m_Config.IncludeActiveSituations && incidents && incidents.HCActive() && m_Cursor < incidents.HCCount())
                {
                    HCWorldIncident incident = incidents.HCRowAt(m_Cursor);
                    m_Cursor = m_Cursor + 1;
                    if (!incident || incidents.HCGone(incident)) { continue; }
                    if (incident.ExpiresAt > 0 && incident.ExpiresAt <= HCWorldIncidents.HCNowSeconds()) { continue; }
                    if (incident.Position != vector.Zero) { HCAdd("Incident " + incident.Kind, incident.Position); }
                    continue;
                }
            }
            else if (m_Stage == 1)
            {
                // Clone once per catalogue refresh, never mutate the runtime/store.
                if (m_Config.IncludeActiveSituations && m_Cursor == 0)
                {
                    HCEventModule events = HCEventModule.Get();
                    if (events && events.Runtime()) { m_EventSnapshot = events.Runtime().Snapshot(); }
                }
                if (m_Config.IncludeActiveSituations && m_EventSnapshot && m_EventSnapshot.Runs && m_Cursor < m_EventSnapshot.Runs.Count())
                {
                    HCEventRun run = m_EventSnapshot.Runs[m_Cursor];
                    m_Cursor = m_Cursor + 1;
                    if (run && run.Phase == HCEventRunPhase.ACTIVE && run.Objective && run.Objective.Source != vector.Zero)
                    {
                        HCAdd("Event " + run.Objective.Id, run.Objective.Source);
                    }
                    continue;
                }
                m_EventSnapshot = null;
            }
            else if (m_Stage == 2)
            {
                if (m_Sites && m_Cursor < m_Sites.Sites.Count())
                {
                    HCAdminTeleportSite site = m_Sites.Sites[m_Cursor];
                    m_Cursor = m_Cursor + 1;
                    if (site && site.Waypoints && site.Waypoints.Count() > 0) { HCAdd("AI " + site.Id, site.Waypoints[0]); }
                    continue;
                }
            }
            else if (m_Stage == 3)
            {
                HCCampModule camps = HCCampModule.Get();
                if (camps && m_Cursor < camps.HCEncounterCount())
                {
                    HCCampRecord camp = camps.HCEncounterTarget(m_Cursor, HCWorldClock.UTC());
                    m_Cursor = m_Cursor + 1;
                    if (camp) { HCAdd("Camp " + m_Cursor.ToString(), camp.Position); }
                    continue;
                }
            }
            else if (m_Stage == 4)
            {
                HCHoldouts homes = HCHoldouts.Get();
                if (homes && m_Cursor < homes.Count())
                {
                    HCWorldHoldout home = homes.Snapshot(m_Cursor);
                    m_Cursor = m_Cursor + 1;
                    if (home) { HCAdd("Holdout " + m_Cursor.ToString(), home.HousePos); }
                    continue;
                }
            }
            else if (m_Stage == 5)
            {
                if (m_Cursor < m_NameCount)
                {
                    string child;
                    bool childFound = GetGame().ConfigGetChildName(m_Names, m_Cursor, child);
                    m_Cursor = m_Cursor + 1;
                    if (!childFound) { continue; }
                    string root = m_Names + " " + child;
                    string kind;
                    GetGame().ConfigGetText(root + " type", kind);
                    if (kind != "NameCityCapital" && kind != "NameCity" && kind != "NameVillage") { continue; }
                    string title;
                    GetGame().ConfigGetText(root + " name", title);
                    array<float> coordinates = new array<float>;
                    GetGame().ConfigGetFloatArray(root + " position", coordinates);
                    if (coordinates.Count() == 2) { HCAdd(title, Vector(coordinates[0], 0, coordinates[1])); }
                    continue;
                }
                m_Complete = true;
                if (m_Destinations.Count() == 0) { m_Fault = "teleport-no-destinations"; HCRefuse(m_Fault); }
                return;
            }
            m_Stage = m_Stage + 1;
            m_Cursor = 0;
        }
    }

    bool HCList(HCAdminReply reply, int page)
    {
        if (!m_Enabled) { reply.Notice = "Teleport disabled"; return false; }
        if (!m_Complete) { reply.Notice = "Teleport destinations building; retry tplist"; return false; }
        int pages = Math.Max(1, (m_Destinations.Count() + m_Config.PageSize - 1) / m_Config.PageSize);
        page = Math.Clamp(page, 0, pages - 1);
        int first = page * m_Config.PageSize;
        int end = Math.Min(first + m_Config.PageSize, m_Destinations.Count());
        for (int listIndex = first; listIndex < end; listIndex++)
        {
            reply.Lines.Insert(listIndex.ToString() + ": " + m_Destinations[listIndex].Label);
        }
        reply.Notice = "tplist page=" + page.ToString() + " pages=" + pages.ToString() + "; tp selects an index; use tprefresh to rebuild; runtime=PENDING";
        return true;
    }

    // Query and examine only; result count is capped before script iteration.
    // The padded local X/Z envelope deliberately excludes covered courtyards too.
    bool HCOutsideBuildings(vector placed)
    {
        array<Object> nearby = new array<Object>;
        array<CargoBase> proxies = new array<CargoBase>;
        GetGame().GetObjectsAtPosition(placed, m_Config.BuildingQueryRadiusM, nearby, proxies);
        if (nearby.Count() > m_Config.MaxBuildingObjects || proxies.Count() > 0) { return false; }
        for (int obstacleIndex = 0; obstacleIndex < nearby.Count(); obstacleIndex++)
        {
            Object obstacle = nearby[obstacleIndex];
            if (!obstacle || !obstacle.IsBuilding()) { continue; }
            vector bounds[2];
            if (!obstacle.GetCollisionBox(bounds)) { return false; }
            vector localPoint = obstacle.WorldToModel(placed);
            float padding = m_Config.ClearanceWidthM * 2;
            if (!(bounds[0][0] <= bounds[1][0] && bounds[0][2] <= bounds[1][2])) { return false; }
            if (!(localPoint[0] == localPoint[0] && localPoint[2] == localPoint[2])) { return false; }
            if (localPoint[0] >= bounds[0][0] - padding && localPoint[0] <= bounds[1][0] + padding && localPoint[2] >= bounds[0][2] - padding && localPoint[2] <= bounds[1][2] + padding) { return false; }
        }
        return true;
    }

    vector HCGround(vector candidate, PlayerBase player)
    {
        float size = GetGame().GetWorld().GetWorldSize();
        float margin = m_Config.BoundaryMarginM + m_Config.ClearanceWidthM;
        float x = candidate[0];
        float z = candidate[2];
        if (!(x > margin && z > margin && x < size - margin && z < size - margin)) { return vector.Zero; }
        if (GetGame().SurfaceIsSea(x, z) || GetGame().SurfaceIsPond(x, z)) { return vector.Zero; }
        float y = GetGame().SurfaceY(x, z);
        float width = m_Config.ClearanceWidthM;
        float low = Math.Min(GetGame().SurfaceY(x - width, z), GetGame().SurfaceY(x + width, z));
        low = Math.Min(low, Math.Min(GetGame().SurfaceY(x, z - width), GetGame().SurfaceY(x, z + width)));
        float high = Math.Max(GetGame().SurfaceY(x - width, z), GetGame().SurfaceY(x + width, z));
        high = Math.Max(high, Math.Max(GetGame().SurfaceY(x, z - width), GetGame().SurfaceY(x, z + width)));
        low = Math.Min(low, y);
        high = Math.Max(high, y);
        if (!(y >= 0 && y < size && high - low <= m_Config.MaxSlopeDeltaM)) { return vector.Zero; }
        vector placed = Vector(x, y + m_Config.GroundOffsetM, z);
        if (!HCOutsideBuildings(placed)) { return vector.Zero; }
        vector center = Vector(x, high + m_Config.GroundOffsetM + m_Config.ClearanceHeightM / 2, z);
        vector extent = Vector(width, m_Config.ClearanceHeightM, width);
        array<Object> excluded = new array<Object>;
        excluded.Insert(player);
        if (GetGame().IsBoxColliding(center, vector.Zero, extent, excluded)) { return vector.Zero; }
        return placed;
    }

    vector HCFindGround(vector anchor, PlayerBase player)
    {
        m_Work.HCReset(m_Config.SearchAttempts);
        for (int attempt = 0; attempt < m_Config.SearchAttempts; attempt++)
        {
            if (!m_Work.HCContinue() || !HCServer.Get().HCTickWork().HCTake(1)) { return vector.Zero; }
            vector candidate = anchor;
            float distance = ((attempt + 3) / 4) * m_Config.SearchStepM;
            int direction = attempt % 4;
            if (direction == 0) { candidate[0] = candidate[0] + distance; }
            else if (direction == 1) { candidate[0] = candidate[0] - distance; }
            else if (direction == 2) { candidate[2] = candidate[2] + distance; }
            else { candidate[2] = candidate[2] - distance; }
            vector ground = HCGround(candidate, player);
            if (ground != vector.Zero) { return ground; }
        }
        return vector.Zero;
    }

    bool HCMove(HCAdminModule admin, PlayerIdentity sender, PlayerBase player, int requested, out int selected, out string reason)
    {
        selected = -1;
        reason = "non-admin";
        if (!GetGame().IsServer() || !admin || !admin.HCAuthorized(sender)) { return false; }
        reason = "teleport-disabled";
        if (!m_Enabled || !admin.HCOperatorControls() || !HCServer.Get().GetSettings().EnableAdminMap) { return false; }
        if (FileExist("$profile:HollowCountry/acceptance/AdminControls.disable") || FileExist("$profile:HollowCountry/acceptance/AdminTeleport.disable")) { return false; }
        reason = "live-sender-unavailable";
        if (!player) { return false; }
        reason = "in-vehicle";
        if (player.GetCommand_Vehicle()) { return false; }
        reason = "unconscious";
        if (player.IsUnconscious()) { return false; }
        reason = "restrained";
        if (player.IsRestrained()) { return false; }
        reason = "destination-build-pending-or-empty";
        if (!m_Complete || m_Destinations.Count() == 0) { return false; }
        int index = Math.Clamp(requested, 0, m_Destinations.Count() - 1);
        selected = index;
        vector destination = HCFindGround(m_Destinations[index].Position, player);
        reason = "no-safe-ground-or-work-budget";
        if (destination == vector.Zero) { return false; }
        player.SetPosition(destination);
        reason = "admin-only; runtime=PENDING";
        return true;
    }
}

// Same-layer extension keeps all identity matching, replies and sender-only
// movement inside the existing module. No later-link hook called by an earlier
// modded link: HCDispatch calls the already declared HCCommand virtual method.
modded class HCAdminModule
{
    protected ref HCAdminTeleport m_HCTeleport;

    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (m_Running && !m_HCTeleport)
        {
            m_HCTeleport = new HCAdminTeleport;
            m_HCTeleport.HCStart(m_OperatorControls);
        }
    }

    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCOperationalStatus baseStatus = super.HCGetOperationalStatus();
        if (!m_Running || !m_HCTeleport) { return baseStatus; }
        HCOperationalStatus teleportStatus = m_HCTeleport.HCGetOperationalStatus();
        // Re-derive from running transport and the actual cached feature fault.
        string fault = "";
        if (teleportStatus.HCState() == "degraded" || teleportStatus.HCState() == "refused") { fault = teleportStatus.HCReason(); }
        HCModuleReadiness.HCDerive(m_Status, m_Running, "", fault, "allowlist_loaded_teleport_catalog_native_pending");
        return m_Status;
    }

    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (m_Running && m_HCTeleport) { m_HCTeleport.HCStep(); }
    }

    override void OnStop()
    {
        m_HCTeleport = null;
        super.OnStop();
    }

    override bool HCCommand(PlayerIdentity sender, string command, int value, int ticket)
    {
        if (command != "tp" && command != "tplist" && command != "tprefresh") { return super.HCCommand(sender, command, value, ticket); }
        if (!HCAuthorized(sender)) { HCRefused(sender); return false; }
        if (!m_HCTeleport) { HCReply(sender, ticket, command, false, "teleport-service-unavailable"); return false; }
        if (command == "tprefresh")
        {
            bool refreshed = m_HCTeleport.HCRefresh();
            string refreshReason = "teleport-disabled-or-config-unavailable";
            if (refreshed) { refreshReason = "destination-refresh-queued; runtime=PENDING"; }
            HCReply(sender, ticket, command, refreshed, refreshReason);
            return refreshed;
        }
        if (command == "tplist")
        {
            HCAdminReply listing = new HCAdminReply;
            listing.Ticket = ticket;
            bool listed = m_HCTeleport.HCList(listing, value);
            HCSend(sender, listing);
            Print("[HC Admin] cmd=tplist runtime=PENDING");
            return listed;
        }
        int selected;
        string reason;
        bool ok = m_HCTeleport.HCMove(this, sender, HCPlayer(sender), value, selected, reason);
        string result = "refused";
        if (ok) { result = "ok"; }
        string line = "[HC Admin] cmd=tp dest=" + selected.ToString() + " " + result + " reason=" + reason;
        Print("" + line);
        HCAdminReply reply = new HCAdminReply;
        reply.Ticket = ticket;
        reply.Notice = line;
        HCSend(sender, reply);
        return ok;
    }
}
