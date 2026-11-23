// Registration adapters only: all path qualification, actor reservation, native
// trigger, accuracy (0.20..0.45), perception, death journal and despawn remain HCX.
// Installed Expansion ai_scripts.pbo: eAIFormation.c:37 GetPosition, :57 ToWorld;
// eAIDynamicPatrol.c:617 first spawn, :681 deferred member uses formation.ToWorld.
// Temporary spawn formation is restored synchronously; routine formations retain
// their existing owner. No live actor position is written.
class HCXZoneGuardsSite : HCXAISite
{
    int Members;
    string ProviderFaction;
}
class HCXZoneGuardsSpawnFormation : eAIFormation
{
    ref array<vector> Slots;
    override vector GetPosition(int member_no)
    {
        if (!Slots || Slots.Count() == 0) { return vector.Zero; }
        vector at = Slots[member_no % Slots.Count()];
        at[1] = GetGame().SurfaceY(at[0], at[2]);
        return at;
    }
    override vector ToWorld(vector fs) { return fs; }
    override vector GetDirection(int member_no) { return vector.Forward; }
}
modded class HCXAISitePatrol
{
    override void SpawnAI_Deferred(int i)
    {
        HCXZoneGuards owner = HCXZoneGuards.Active();
        HCXZoneGuardsRuntime zone;
        if (owner) { zone = owner.BySite(m_HCSiteId); }
        if (!zone) { super.SpawnAI_Deferred(i); return; }
        if (!owner.Held(m_HCSiteId)) { m_HCRefusal = "zone_not_held"; m_HCPendingMembers = 0; return; }
        eAIFormation previous = m_Formation;
        HCXZoneGuardsSpawnFormation slots = new HCXZoneGuardsSpawnFormation;
        slots.Slots = zone.Zone.guard_slots;
        m_Formation = slots;
        int before;
        before = HCXExpansionBridge.HCHoldCount(this.HCGroupHold());
        super.SpawnAI_Deferred(i);
        m_Formation = previous;
        if (HCXExpansionBridge.HCHoldAlive(this.HCGroupHold())) { owner.ActorSpawned(HCXExpansionBridge.HCHoldCount(this.HCGroupHold()) - before); }
    }
}
modded class HCXAISiteDirector
{
    protected int m_HCZoneAuditCursor;
    protected int m_HCZoneAuditOwned;
    protected int m_HCZoneAuditReleased;
    protected int m_HCZoneAuditSampled;
    protected float m_HCZoneAuditNext;
    // At most four catalog rows per admitted zone tick; one summary per sweep
    // and no more often than 300 seconds. Counts are a rolling observation.
    void HCZoneAuditStep(HCXZoneGuards owner)
    {
        for (int checked = 0; checked < 4 && m_HCZoneAuditCursor < m_States.Count(); checked++)
        {
            HCXAISiteState state = m_States[m_HCZoneAuditCursor];
            m_HCZoneAuditCursor++;
            if (state && state.Site && !owner.BySite(state.Site.Id) && state.Site.Waypoints.Count() > 0)
            {
                vector anchor = state.Site.Waypoints[0];
                m_HCZoneAuditSampled++;
                if (owner.OwnsAnchor(anchor, state.Site.Id)) { m_HCZoneAuditOwned++; }
                else if (owner.AnchorInZone(anchor, state.Site.Id)) { m_HCZoneAuditReleased++; }
            }
        }
        if (m_HCZoneAuditCursor < m_States.Count() || GetGame().GetTickTime() < m_HCZoneAuditNext) { return; }
        owner.Summary(m_HCZoneAuditOwned, m_HCZoneAuditOwned, m_HCZoneAuditReleased, m_HCZoneAuditSampled);
        m_HCZoneAuditNext = GetGame().GetTickTime() + 300;
        m_HCZoneAuditCursor = 0;
        m_HCZoneAuditOwned = 0;
        m_HCZoneAuditReleased = 0;
        m_HCZoneAuditSampled = 0;
    }
    override void Spawned(HCXAISitePatrol patrol)
    {
        super.Spawned(patrol);
        HCXZoneGuards owner = HCXZoneGuards.Active();
        if (owner && owner.BySite(patrol.m_HCSiteId) && HCXExpansionBridge.HCHoldAlive(patrol.HCGroupHold())) { owner.ActorSpawned(HCXExpansionBridge.HCHoldCount(patrol.HCGroupHold())); }
    }
    // Called for one zone/tick by its HCWorkBudget admission. Use the existing
    // bind/qualify/create stages, never a second native patrol constructor.
    // Returns true when this call ran one stage that made progress; false when it ran none
    // or a Create stage was refused (counted with a reason code, retried after 60 s). A call runs at most one stage, and
    // HCXZoneGuards.OnTick makes at most one call per tick inside its single
    // HC_WORK_ZONE_GUARDS unit, so a tick can never run two sites' stages.
    bool HCZoneService(HCXZoneGuardsRuntime zone)
    {
        if (m_Phase != "run" || !m_Policy || !m_OwnedSaved) { return false; }
        int began = TickCount(0);
        if (!zone.Site)
        {
            if (zone.Row.State != "held" || m_States.Count() >= HCXAISiteRules.HCMaxCatalogRows()) { return false; }
            HCXZoneGuardsSite site = new HCXZoneGuardsSite;
            site.Id = "zg-" + zone.Zone.id;
            site.Kind = "patrol";
            site.Faction = "West";
            site.Members = Math.Clamp(2 + zone.Zone.tier, 3, 6);
            if (site.Members > zone.Zone.guard_slots.Count()) { site.Members = zone.Zone.guard_slots.Count(); }
            site.NumberOfAI = site.Members;
            site.NumberOfAIMax = site.Members;
            site.Loadout = "HollowCountry_Patrol";
            site.ProviderFaction = "HCVolunteers";
            if (zone.Zone.id.Hash() % 2 == 0)
            {
                site.ProviderFaction = "HCRaiders";
                site.Loadout = "HollowCountry_Raider";
            }
            if (zone.Zone.tier == 1) { site.Loadout = "HollowCountry_Holdout"; }
            // Guards never spawn without the HC loadout: a missing default file refuses the
            // admission (no site state, no stage) and is retried on the zone's next visit.
            if (!HCXAIDefaults.ProvisionLoadout(site.Loadout))
            {
                HCXZoneGuards refusing = HCXZoneGuards.Active();
                if (refusing) { refusing.StageRefused(zone, "zone_loadout_missing"); }
                return false;
            }
            int points;
            foreach (vector slot : zone.Zone.guard_slots)
            {
                if (points >= 6) { break; }
                site.Waypoints.Insert(slot);
                points++;
            }
            zone.Site = new HCXAISiteState;
            zone.Site.Site = site;
            m_States.Insert(zone.Site);
            m_AdmittedTotal++;
            this.HCZoneStage(zone, "admit", began);
            return true;
        }
        HCXAISiteState state = zone.Site;
        if (zone.Row.State != "held" || zone.Row.Wiped) { return false; }
        if (state.Failed || state.Patrol) { return false; }
        if (!state.Bound)
        {
            this.Bind(state);
            this.HCZoneStage(zone, "bind", began);
            return true;
        }
        if (!state.Qualified)
        {
            this.QualifyStep(state);
            this.HCZoneStage(zone, "qualify", began);
            return true;
        }
        // A refused Create (provider issue, native setup refused) sets neither Patrol nor
        // Failed. Retry it at most once a minute per zone, count the refusal with its reason
        // code and report no progress, so a persistent refusal never holds the zone's visit.
        if (GetGame().GetTickTime() < zone.CreateRetryAt) { return false; }
        this.Create(state);
        this.HCZoneStage(zone, "create", began);
        if (!state.Patrol && !state.Failed)
        {
            zone.CreateRetryAt = GetGame().GetTickTime() + 60;
            HCXZoneGuards creating = HCXZoneGuards.Active();
            if (creating) { creating.StageRefused(zone, "zone_create_refused"); }
            return false;
        }
        return true;
    }
    // Existing site_stage peak line (>= 40000 ticks) plus the zone-guards progress counters.
    protected void HCZoneStage(HCXZoneGuardsRuntime zone, string stage, int began)
    {
        int elapsed = TickCount(began);
        this.HCSiteStageCost("zone_" + stage, began);
        HCXZoneGuards owner = HCXZoneGuards.Active();
        if (owner) { owner.StageProgress(zone.Zone.id, stage, elapsed); }
    }
    override string HCPrepareRingSpawn(HCXAISitePatrol patrol)
    {
        HCXZoneGuards owner = HCXZoneGuards.Active();
        if (owner)
        {
            HCXZoneGuardsRuntime zone = owner.BySite(patrol.m_HCSiteId);
            if (zone)
            {
                if (!owner.Held(patrol.m_HCSiteId)) { return "zone_not_held"; }
                if (!patrol.HCHasGroup())
                {
                    vector first = zone.Zone.guard_slots[0];
                    first[1] = GetGame().SurfaceY(first[0], first[2]);
                    patrol.m_Position = first;
                }
                return ""; // authored slots, never player-relative ring relocation
            }
            if (owner.OwnsAnchor(patrol.m_Position, patrol.m_HCSiteId)) { return "zone_managed_anchor"; }
        }
        return super.HCPrepareRingSpawn(patrol);
    }
    override string SpawnProblemFor(HCXAISitePatrol patrol)
    {
        HCXZoneGuards owner = HCXZoneGuards.Active();
        if (owner && owner.BySite(patrol.m_HCSiteId) && !owner.Held(patrol.m_HCSiteId)) { return "zone_not_held"; }
        return super.SpawnProblemFor(patrol);
    }
    override void RecordDeath(eAIGroup killedGroup)
    {
        HCXZoneGuards owner = HCXZoneGuards.Active();
        if (owner) { owner.ObserveDeath(killedGroup); }
        super.RecordDeath(killedGroup);
    }
}
