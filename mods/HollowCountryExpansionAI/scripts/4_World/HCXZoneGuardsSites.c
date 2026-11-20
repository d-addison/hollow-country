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
        super.SpawnAI_Deferred(i);
        m_Formation = previous;
    }
}
modded class HCXAISiteDirector
{
    // Called for one zone/tick by its HCWorkBudget admission. Use the existing
    // bind/qualify/create stages, never a second native patrol constructor.
    void HCZoneService(HCXZoneGuardsRuntime zone)
    {
        if (m_Phase != "run" || !m_Policy || !m_OwnedSaved) { return; }
        if (!zone.Site)
        {
            if (zone.Row.State != "held" || m_States.Count() >= HCXAISiteRules.HCMaxCatalogRows()) { return; }
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
            HCXAIDefaults.ProvisionLoadout(site.Loadout);
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
            return;
        }
        HCXAISiteState state = zone.Site;
        if (state.Failed || state.Patrol) { return; }
        if (!state.Bound) { this.Bind(state); return; }
        if (!state.Qualified) { this.QualifyStep(state); return; }
        this.Create(state);
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
                if (!patrol.m_Group)
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
