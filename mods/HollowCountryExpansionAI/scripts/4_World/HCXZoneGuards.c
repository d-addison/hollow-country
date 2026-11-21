// R5 ZoneGuards. One zone serviced/tick, <=2 escalation transitions/day.
// Native evidence inspected: scripts-1.30.164289 Game.c GetTickTime,
// SurfaceY, ConfigIsExisting; Object.c IsAlive/GetPosition. Expansion installed
// ai_scripts.pbo eAIDynamicPatrol SpawnAI_Deferred/Despawn and eAIFormation
// ToWorld/GetPosition are reused by HCXZoneGuardsSites. No targeting port.
// All capacity/slice values remain provisional for 3..6 players; runtime=PENDING.
class HCXZoneGuardsPack : HCNativeInfectedPack
{
    bool Active = true;
    override bool HCReinforceActive() { return Active; }
}
class HCXZoneGuardsRuntime
{
    ref HCXZoneGuardsZone Zone;
    ref HCXZoneGuardsRow Row;
    ref HCXAISiteState Site;
    ref HCXZoneGuardsPack Pack = new HCXZoneGuardsPack;
    ref array<ZombieBase> Bodies = new array<ZombieBase>;
    bool Initialised;
    int Spent;
    float NextAttempt;
}
class HCXZoneGuardsDebug : HCDebugContributor
{
    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        HCXZoneGuards owner = HCXZoneGuards.Active();
        if (!owner || !snapshot) { return; }
        array<ref HCXZoneGuardsRuntime> zones = owner.Zones();
        int shown;
        foreach (HCXZoneGuardsRuntime zone : zones)
        {
            if (shown >= 16) { break; }
            snapshot.AddPoint("zones", zone.Zone.id, zone.Zone.center, zone.Zone.area, "state=" + zone.Row.State + " changed_day=" + zone.Row.ChangedDay.ToString());
            shown++;
        }
    }
}
class HCXZoneGuards : HCModule
{
    protected string m_StatusLogLine;
    protected float m_StatusLogAt;
    protected static HCXZoneGuards s_Active;
    protected ref HCXZoneGuardsConfig m_Config;
    protected ref HCXZoneGuardsJournal m_Data;
    protected ref HCXZoneGuardsSave m_Save;
    protected ref array<ref HCXZoneGuardsRuntime> m_Zones = new array<ref HCXZoneGuardsRuntime>;
    protected ref map<string, HCXZoneGuardsRuntime> m_BySite = new map<string, HCXZoneGuardsRuntime>;
    protected ref HCPerfSlices m_Work = new HCPerfSlices("ZoneGuards");
    protected ref HCXZoneGuardsDebug m_Debug;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected bool m_Started;
    protected string m_Refusal;
    protected int m_Cursor;
    protected int m_DailyRemaining;
    protected int m_ActorsSpawned;
    static HCXZoneGuards Active() { return s_Active; }
    array<ref HCXZoneGuardsRuntime> Zones() { return m_Zones; }
    override string GetName() { return "ZoneGuards"; }
    override bool IsEnabled(HCSettings settings)
    {
        m_Config = HCXZoneGuardsConfig.Load();
        return settings && settings.EnableEncounters && (!m_Config || !m_Config.Disabled);
    }
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Status, m_Started, m_Refusal, m_Refusal, "zone_catalog_and_state_loaded");
        return m_Status;
    }
    static bool StateValid(string state) { return state == "held" || state == "overrun" || state == "abandoned"; }
    // An absent mission catalog has the same small stock-map sample compiled in
    // for Workshop-only installs. Invalid existing catalogs fail closed.
    protected HCXZoneGuardsCatalog LoadCatalog()
    {
        string path = "$mission:hollow-country/ai/zones.json";
        if (!FileExist(path)) { path = "$mission:hollow-country/ai/zones.sample.json"; }
        HCXZoneGuardsCatalog catalog = new HCXZoneGuardsCatalog;
        if (FileExist(path))
        {
            string raw = HCWorldStore.Read(path);
            string error;
            if (raw == "" || !JsonFileLoader<HCXZoneGuardsCatalog>.LoadData(raw, catalog, error)) { return null; }
            return catalog;
        }
        AddSample(catalog, "sample-nwaf", "NWAF", "4710 340.478149 10500", "held", 2);
        AddSample(catalog, "sample-balota", "Balota", "5560 69.383011 2750", "abandoned", 2);
        AddSample(catalog, "sample-tisy", "Tisy", "1890 435.890961 14840", "overrun", 3);
        return catalog;
    }
    protected void AddSample(HCXZoneGuardsCatalog catalog, string id, string area, vector center, string state, int tier)
    {
        HCXZoneGuardsZone zone = new HCXZoneGuardsZone;
        zone.id = id;
        zone.area = area;
        zone.center = center;
        zone.default_state = state;
        zone.tier = tier;
        zone.radius_m = 250;
        zone.guard_slots.Insert(center);
        zone.guard_slots.Insert(center + "12 0 0");
        zone.guard_slots.Insert(center + "12 0 12");
        zone.guard_slots.Insert(center + "0 0 12");
        zone.guard_slots.Insert(center + "-12 0 12");
        zone.guard_slots.Insert(center + "-12 0 0");
        catalog.zones.Insert(zone);
    }
    protected bool LoadState()
    {
        string path = "$profile:HollowCountry/zone-guards-state.json";
        if (!HCV2ThreatStore<HCXZoneGuardsJournal>.CanOpen(path)) { return false; }
        m_Data = new HCXZoneGuardsJournal;
        if (FileExist(path))
        {
            string raw = HCWorldStore.Read(path);
            string error;
            if (raw == "" || raw.Length() > 65536 || !HCJsonFields.Has(raw, "LastDay") || !JsonFileLoader<HCXZoneGuardsJournal>.LoadData(raw, m_Data, error)) { return false; }
        }
        if (!m_Data || m_Data.Version != 1 || !m_Data.Rows || m_Data.Rows.Count() > 128 || m_Data.LastDay < -1 || m_Data.ChangedToday < 0 || m_Data.ChangedToday > 2 || m_Data.Cursor < 0) { return false; }
        map<string, bool> ids = new map<string, bool>;
        foreach (HCXZoneGuardsRow row : m_Data.Rows)
        {
            if (!row || !HCXAIRules.Token(row.Id) || !StateValid(row.State) || row.ChangedDay < 0 || ids.Contains(row.Id)) { return false; }
            ids.Set(row.Id, true);
        }
        return true;
    }
    override void OnStart(HCSettings settings)
    {
        m_StatusLogLine = "";
        m_StatusLogAt = 0;
        if (!m_Config) { m_Refusal = "zone_settings_invalid"; return; }
        if (!HCBuildIdentity.SameWorld("chernarusplus", GetGame().GetWorldName())) { m_Refusal = "zone_world_mismatch"; return; }
        HCXZoneGuardsCatalog catalog = LoadCatalog();
        if (!catalog || !catalog.zones || catalog.zones.Count() < 1 || catalog.zones.Count() > m_Config.MaxZones || !LoadState()) { m_Refusal = "zone_catalog_or_journal_invalid"; return; }
        map<string, bool> ids = new map<string, bool>;
        map<string, HCXZoneGuardsRow> rowsById = new map<string, HCXZoneGuardsRow>;
        foreach (HCXZoneGuardsRow loaded : m_Data.Rows) { rowsById.Set(loaded.Id, loaded); }
        foreach (HCXZoneGuardsZone zone : catalog.zones)
        {
            if (!zone || !HCXAIRules.Token(zone.id) || zone.id.Length() > 44 || zone.area.Length() > 64 || ids.Contains(zone.id) || !HCInfectedStore.ValidPosition(zone.center) || !(zone.radius_m >= 20 && zone.radius_m <= 2000) || zone.tier < 1 || zone.tier > 4 || !StateValid(zone.default_state) || !zone.guard_slots || zone.guard_slots.Count() < 3 || zone.guard_slots.Count() > 8 || !zone.sites || zone.sites.Count() > 256) { m_Refusal = "zone_row_invalid"; return; }
            ids.Set(zone.id, true);
            foreach (vector slot : zone.guard_slots)
            {
                if (!HCInfectedStore.ValidPosition(slot) || vector.Distance(slot, zone.center) > zone.radius_m) { m_Refusal = "zone_slot_invalid"; return; }
            }
            HCXZoneGuardsRow state = rowsById.Get(zone.id);
            if (!state)
            {
                if (m_Data.Rows.Count() >= 128) { m_Refusal = "zone_journal_capacity"; return; }
                state = new HCXZoneGuardsRow;
                state.Id = zone.id;
                state.State = zone.default_state;
                state.ChangedDay = HCEscalationClock.Day();
                m_Data.Rows.Insert(state);
            }
            HCXZoneGuardsRuntime runtime = new HCXZoneGuardsRuntime;
            runtime.Zone = zone;
            runtime.Row = state;
            m_Zones.Insert(runtime);
            m_BySite.Set("zg-" + zone.id, runtime);
        }
        m_Save = new HCXZoneGuardsSave;
        m_Save.Data = m_Data;
        HCSaveScheduler.HCRegister(m_Save);
        if (!Checkpoint()) { return; }
        if (!GetGame().ConfigIsExisting("CfgVehicles ZmbM_SoldierNormal") || !GetGame().ConfigIsExisting("CfgVehicles ZmbM_PatrolNormal_Summer")) { m_Refusal = "military_infected_config_missing"; return; }
        if (settings.EnableDebugSnapshot)
        {
            m_Debug = new HCXZoneGuardsDebug;
            HCDebugSnapshot.HCRegister(m_Debug);
        }
        s_Active = this;
        m_Started = true;
    }
    protected bool Checkpoint()
    {
        if (!m_Save || m_Save.Fault || m_Refusal != "") { return false; }
        m_Save.HCDirty = true;
        if (!HCSaveScheduler.HCFlush(m_Save)) { m_Refusal = "zone_state_write_fault"; return false; }
        return true;
    }
    HCXZoneGuardsRuntime BySite(string id) { return m_BySite.Get(id); }
    // Ownership is explicit: radius is an audit envelope, not a blanket hold.
    // A replacement must be operational before the ordinary site yields to it.
    bool Manages(HCXZoneGuardsRuntime zone)
    {
        if (!m_Started || m_Refusal != "" || !zone.Initialised) { return false; }
        if (zone.Row.State == "held")
        {
            return !zone.Row.Wiped && zone.Site && !zone.Site.Failed && zone.Site.Patrol && !zone.Site.Patrol.m_HCFinished && zone.Site.Patrol.m_Group && zone.Site.Patrol.m_Group.Count() > 0;
        }
        if (zone.Row.State == "overrun")
        {
            foreach (ZombieBase body : zone.Bodies)
            {
                if (body && body.IsAlive()) { return true; }
            }
        }
        return false;
    }
    // <=128 catalog rows; called only at spawn gates and four audit rows/tick.
    bool OwnsAnchor(vector anchor, string id)
    {
        foreach (HCXZoneGuardsRuntime zone : m_Zones)
        {
            if (zone.Zone.sites.Find(id) >= 0 && Manages(zone)) { return true; }
        }
        return false;
    }
    bool AnchorInZone(vector anchor, string id)
    {
        foreach (HCXZoneGuardsRuntime zone : m_Zones)
        {
            if (zone.Zone.sites.Find(id) >= 0 || vector.DistanceSq(anchor, zone.Zone.center) <= zone.Zone.radius_m * zone.Zone.radius_m) { return true; }
        }
        return false;
    }
    void ActorSpawned(int count)
    {
        if (count > 0 && m_ActorsSpawned <= 2147483647 - count) { m_ActorsSpawned += count; }
    }
    // Ownership counts cover one bounded rolling director sweep, not live actors.
    void Summary(int ownedSites, int held, int released, int sampled)
    {
        int initialised;
        int heldZones;
        int overrun;
        int abandoned;
        int created;
        foreach (HCXZoneGuardsRuntime zone : m_Zones)
        {
            if (zone.Initialised) { initialised++; }
            if (zone.Row.State == "held") { heldZones++; }
            if (zone.Row.State == "overrun") { overrun++; }
            if (zone.Row.State == "abandoned") { abandoned++; }
            if (zone.Site) { created++; }
        }
        string line = "[HC ZoneGuards] summary zones_initialised=" + initialised.ToString() + " zones_total=" + m_Zones.Count().ToString();
        line += " held=" + heldZones.ToString() + " overrun=" + overrun.ToString() + " abandoned=" + abandoned.ToString();
        line += " sites_owned=" + ownedSites.ToString() + " sites_held=" + held.ToString() + " sites_released=" + released.ToString();
        line += " sites_sampled=" + sampled.ToString() + " zg_sites_created=" + created.ToString() + " actors_spawned=" + m_ActorsSpawned.ToString();
        line += " last_day=" + m_Data.LastDay.ToString() + " runtime=PENDING";
        string statusLine = "" + line;
        // First receipt, changed content, or one unchanged heartbeat per 30 minutes.
        float statusNow = GetGame().GetTickTime();
        if (statusLine != m_StatusLogLine || statusNow < m_StatusLogAt || statusNow - m_StatusLogAt >= 1800)
        {
            Print("" + statusLine);
            m_StatusLogLine = statusLine;
            m_StatusLogAt = statusNow;
        }
    }
    bool Held(string id)
    {
        HCXZoneGuardsRuntime zone = BySite(id);
        return m_Started && m_Refusal == "" && zone && zone.Row.State == "held" && !zone.Row.Wiped;
    }
    // Death callback shares HCX's pre-cleanup receipt. No inferred deaths from
    // a missing group, audience despawn or a failed factory call.
    void ObserveDeath(eAIGroup group)
    {
        if (!group || m_Refusal != "") { return; }
        foreach (HCXZoneGuardsRuntime zone : m_Zones)
        {
            if (!zone.Site || !zone.Site.Patrol || zone.Site.Patrol.m_Group != group || zone.Row.State != "held") { continue; }
            int alive;
            for (int i = 0; i < group.Count() && i < 6; i++)
            {
                DayZPlayerImplement member = group.GetMember(i);
                if (member && member.IsAlive()) { alive++; }
            }
            if (alive == 0 || group.Count() == 1)
            {
                zone.Row.Wiped = true;
                Change(zone, "abandoned", HCEscalationClock.Day());
            }
            return;
        }
    }
    protected bool Change(HCXZoneGuardsRuntime zone, string next, int day)
    {
        string previous = zone.Row.State;
        zone.Row.State = next;
        zone.Row.ChangedDay = day;
        if (next == "held") { zone.Row.Wiped = false; }
        zone.Initialised = false;
        zone.Spent = 0;
        zone.Bodies.Clear();
        if (!Checkpoint()) { return false; }
        zone.Pack.Active = next == "overrun";
        Print("[HC ZoneGuards] zone=" + zone.Zone.id + " from=" + previous + " to=" + next);
        return true;
    }
    override void OnTick(float deltaTime)
    {
        if (!m_Started || m_Refusal != "" || m_Zones.Count() == 0) { return; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director || director.Phase() != "run") { return; }
        m_Work.HCReset(1, HCPerfConfig.HCGet().SliceMs);
        if (!m_Work.HCContinue() || !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_ZONE_GUARDS, 1)) { return; }
        director.HCZoneAuditStep(this);
        int day = HCEscalationClock.Day();
        if (day > m_Data.LastDay)
        {
            m_Data.LastDay = day;
            m_Data.ChangedToday = 0;
            m_DailyRemaining = m_Zones.Count();
            if (!Checkpoint()) { return; }
        }
        int index = m_Cursor % m_Zones.Count();
        m_Cursor = (m_Cursor + 1) % m_Zones.Count();
        HCXZoneGuardsRuntime zone = m_Zones[index];
        director.HCZoneService(zone);
        zone.Initialised = true;
        if (zone.Site && zone.Site.Failed) { m_Refusal = "zone_route_refused_" + zone.Zone.id; return; }
        if (zone.Row.State == "overrun") { StepOverrun(zone, director); }
        if (m_DailyRemaining < 1 || m_Data.ChangedToday >= m_Config.MaxChangesPerDay) { return; }
        HCXZoneGuardsRuntime candidate = m_Zones[m_Data.Cursor % m_Zones.Count()];
        m_Data.Cursor = (m_Data.Cursor + 1) % m_Zones.Count();
        m_DailyRemaining--;
        if (day < candidate.Row.ChangedDay || day - candidate.Row.ChangedDay < m_Config.CooldownDays || !Quiet(candidate)) { return; }
        string next = "held";
        if (candidate.Row.State == "held")
        {
            int seed = candidate.Zone.id.Hash() % 100;
            if (seed < 0) { seed = -seed; }
            if (HCEscalationClock.Pressure("infected") <= seed / 100.0) { return; }
            next = "overrun";
        }
        if (candidate.Row.State == "overrun") { next = "abandoned"; }
        m_Data.ChangedToday++;
        Change(candidate, next, day);
    }
    protected bool Quiet(HCXZoneGuardsRuntime zone)
    {
        if (zone.Site && zone.Site.Patrol && (zone.Site.Patrol.m_HCPendingMembers > 0 || zone.Site.Patrol.m_Group)) { return false; }
        foreach (ZombieBase body : zone.Bodies)
        {
            if (body && body.IsAlive()) { return false; }
        }
        return true;
    }
    protected void StepOverrun(HCXZoneGuardsRuntime zone, HCXAISiteDirector director)
    {
        if (GetGame().GetTickTime() < zone.NextAttempt) { return; }
        zone.NextAttempt = GetGame().GetTickTime() + 10;
        float gap = director.NearestPlayer(zone.Zone.center);
        zone.Pack.Active = gap <= 1000;
        if (!zone.Pack.Active || gap < 300 || zone.Spent >= m_Config.MaxOverrunMembers) { return; }
        vector slot = zone.Zone.guard_slots[zone.Spent % zone.Zone.guard_slots.Count()];
        string type = "ZmbM_SoldierNormal";
        if (zone.Spent % 2 == 1) { type = "ZmbM_PatrolNormal_Summer"; }
        ZombieBase body = HCHordeReinforce.HCCreate(type, slot, zone.Pack);
        if (!body) { return; }
        zone.Bodies.Insert(body);
        zone.Spent++;
        ActorSpawned(1);
    }
    override void OnStop()
    {
        if (m_Debug) { HCDebugSnapshot.HCUnregister(m_Debug); }
        foreach (HCXZoneGuardsRuntime zone : m_Zones)
        {
            zone.Pack.Active = false;
            if (zone.Site && zone.Site.Patrol) { zone.Site.Patrol.m_HCFinished = true; }
        }
        if (m_Save)
        {
            HCSaveScheduler.HCFlush(m_Save);
            HCSaveScheduler.HCUnregister(m_Save);
        }
        if (s_Active == this) { s_Active = null; }
        m_Started = false;
    }
}
modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCXZoneGuards);
    }
}
