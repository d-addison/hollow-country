// HC sites on Expansion AI: patrols, scavenger parties and holdouts with a
// cache. Expansion's own eAIDynamicPatrol and sphere trigger do the spawning;
// HC adds the budget, the 200 m and line-of-sight rules, a refusal to despawn
// in combat, finite fair actors, navmesh-qualified routes and journals.
// Nothing here moves an actor: Expansion places each one once when it spawns.
class HCXAISitePatrol : eAIDynamicPatrol
{
    string m_HCSiteId;
    string m_HCKind;
    int m_HCGroupMax;
    bool m_HCLive;
    string m_HCRefusal;

    override bool CanSpawn()
    {
        if (!super.CanSpawn()) { return false; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director) { return false; }
        string problem = director.SpawnProblemFor(this);
        if (problem != m_HCRefusal)
        {
            m_HCRefusal = problem;
            if (problem != "" && problem != "sites not running") { Print("[HC Expansion AI] site " + m_HCSiteId + " spawn held: " + problem); }
        }
        return problem == "";
    }
    override void Spawn()
    {
        if (m_Group) { return; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director) { return; }
        string problem = director.SpawnProblemFor(this);
        if (problem != "")
        {
            Print("[HC Expansion AI] site " + m_HCSiteId + " spawn refused: " + problem);
            return;
        }
        super.Spawn();
        if (!m_Group) { return; }
        m_HCLive = true;
        director.Spawned(this);
    }
    // Expansion creates members 2..N one per frame at formation offsets. Check
    // the same point it is about to use, before the member exists; a refused
    // member ends the group at the members that already passed.
    override void SpawnAI_Deferred(int i)
    {
        if (!m_Group || !m_Formation) { return; }
        vector raw = m_Formation.ToWorld(m_Formation.GetPosition(i));
        vector placed = ExpansionAISpawnBase.GetPlacementPosition(raw, true);
        string problem = "sites not running";
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (director)
        {
            problem = director.MemberProblemFor(raw);
            if (problem == "") { problem = director.MemberProblemFor(placed); }
        }
        if (problem != "")
        {
            m_NumberOfAI = m_Group.Count();
            m_Group.SetWaypointBehaviour(m_WaypointBehaviour);
            Print("[HC Expansion AI] site " + m_HCSiteId + " member " + i.ToString() + " refused: " + problem + "; group stays at " + m_NumberOfAI.ToString());
            if (director) { director.SaveOwned(); }
            return;
        }
        super.SpawnAI_Deferred(i);
    }
    override void Despawn(bool deferDespawnUntilLoosingAggro = false)
    {
        if (m_Group && !HCXAISiteRules.DespawnAllowed(m_Group.IsInCombat(), m_Group.m_ForcePatrolDespawn)) { return; }
        bool intact = false;
        if (m_Group) { intact = m_Group.Count() >= m_NumberOfAI && m_Group.DeceasedCount() == 0; }
        bool wasLive = m_HCLive;
        super.Despawn(false);
        m_HCLive = false;
        // An intact group that only lost its audience may return when a player
        // comes back; a group that lost members waits the full RespawnSeconds.
        if (intact) { m_TimeSinceLastSpawn = m_RespawnTime; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (wasLive && director) { director.Despawned(this, intact); }
    }
    override void SetupAI(eAIBase ai)
    {
        super.SetupAI(ai);
        ai.eAI_SetUnlimitedReload(0);
        ai.m_eAI_EnableFlankingOutsideCombat = false;
        ai.eAI_SetDamageMultiplier(1);
        ai.eAI_SetDamageReceivedMultiplier(1);
        ai.m_eAI_HeadshotResistance = 0;
        // Blocks Expansion's inventory-cloning recreate (no duplicate loot).
        ai.HCXAI_LeaseOwned = true;
        if (!ai.HCXAI_Fair())
        {
            Print("[HC Expansion AI] site " + m_HCSiteId + " actor failed the fairness check; removed");
            ai.eAI_Despawn();
        }
    }
}
class HCXAISiteState : Managed
{
    HCXAISite Site;
    HCXAISitePatrol Patrol;
    ref array<vector> Points = new array<vector>();
    ref array<vector> Sampled = new array<vector>();
    string Key;
    bool Bound;
    bool Qualified;
    bool Failed;
    bool Cached;
    string Reason;
    int Leg;
    Object HouseObject;
    vector CacheWorld;
    vector CacheOrientation;
    bool Diagnosed;
}
class HCXAISiteDirector : Managed
{
    static const string POLICY = "$profile:HollowCountry/expansion-ai-sites.json";
    static const string ROUTES = "$profile:HollowCountry/expansion-ai-routes.json";
    static const string CACHES = "$profile:HollowCountry/expansion-ai-caches.json";
    static const string OWNED = "$profile:HollowCountry/expansion-ai-owned.json";
    static const string DIAGNOSTIC = "$profile:HollowCountry/acceptance/xai_diagnostic_spawn.enable";
    static const string OBSERVER = "native-eai";
    static const int WORK_PER_TICK = 4;
    protected static HCXAISiteDirector s_Active;

    protected ref HCXAISitePolicy m_Policy;
    protected ref HCXAIRouteCache m_Routes;
    protected ref HCXAICacheJournal m_Caches;
    protected ref HCXAIOwnership m_Owned;
    protected ref array<ref HCXAISiteState> m_States = new array<ref HCXAISiteState>();
    protected ref PGFilter m_Filter;
    protected string m_Build;
    protected string m_Phase = "wait";
    protected int m_Cursor;
    protected int m_CacheCursor;
    protected int m_Ticks;
    protected int m_LastActiveAI = -1;
    protected bool m_Diagnostic;
    protected bool m_WaitLogged;

    static HCXAISiteDirector Active() { return s_Active; }
    string Phase() { return m_Phase; }

    void Start()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        s_Active = this;
        m_Build = HCXAIStore.NativeBuild();
        m_Diagnostic = FileExist(HCXAISiteDirector.DIAGNOSTIC);
        m_Policy = HCXAISiteDirector.LoadPolicy();
        if (!m_Policy)
        {
            m_Phase = "off";
            Print("[HC Expansion AI] sites off: no readable policy at " + HCXAISiteDirector.POLICY);
            return;
        }
        string problem = HCXAISiteRules.PolicyProblem(m_Policy);
        if (problem != "")
        {
            m_Phase = "off";
            Print("[HC Expansion AI] sites off: policy refused: " + problem);
            return;
        }
        int count = m_Policy.Sites.Count();
        Print("[HC Expansion AI] sites policy accepted: " + count.ToString() + " sites; waiting for Expansion AI settings");
        if (m_Diagnostic) { Print("[HC Expansion AI] DIAGNOSTIC marker present: one site of each kind spawns once with no player (Wine observation only)"); }
    }
    void Stop()
    {
        foreach (HCXAISiteState stopping : m_States)
        {
            if (stopping.Patrol) { stopping.Patrol.Stop(); }
        }
        this.SaveOwned();
        m_Phase = "stopped";
        if (s_Active == this) { s_Active = null; }
    }
    void Step()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        m_Ticks++;
        if (m_Phase == "wait") { this.StepWait(); return; }
        if (m_Phase == "bind") { this.StepBind(); return; }
        if (m_Phase == "qualify") { this.StepQualify(); return; }
        if (m_Phase == "create") { this.StepCreate(); return; }
        if (m_Phase == "run") { this.StepRun(); }
    }
    protected void StepWait()
    {
        bool aiLoaded = GetExpansionSettings() && GetExpansionSettings().GetAI() && GetExpansionSettings().GetAI().IsLoaded();
        bool patrolLoaded = false;
        if (aiLoaded && GetExpansionSettings().GetAIPatrol(false)) { patrolLoaded = GetExpansionSettings().GetAIPatrol(false).IsLoaded(); }
        if (!aiLoaded || !patrolLoaded) { return; }
        HCXAISiteAdmission admission = this.Observe();
        string problem = HCXAISiteRules.AdmissionProblem(m_Policy, admission);
        if (problem != "")
        {
            m_Phase = "refused";
            Print("[HC Expansion AI] sites admission refused: " + problem);
            return;
        }
        m_Routes = HCXAISiteDirector.LoadRoutes();
        m_Caches = HCXAISiteDirector.LoadCaches();
        if (!m_Routes || !m_Caches)
        {
            m_Phase = "refused";
            Print("[HC Expansion AI] sites admission refused: route or cache journal unreadable or over budget");
            return;
        }
        m_Filter = new PGFilter();
        int include = PGPolyFlags.UNREACHABLE | PGPolyFlags.DISABLED | PGPolyFlags.WALK | PGPolyFlags.DOOR | PGPolyFlags.INSIDE | PGPolyFlags.LADDER;
        int exclude = PGPolyFlags.CRAWL | PGPolyFlags.CROUCH | PGPolyFlags.SWIM_SEA | PGPolyFlags.SWIM;
        if (eAIBase.AI_HANDLEVAULTING) { include = include | PGPolyFlags.SPECIAL; }
        else { exclude = exclude | PGPolyFlags.SPECIAL; }
        m_Filter.SetFlags(include, exclude, PGPolyFlags.NONE);
        foreach (HCXAISite site : m_Policy.Sites)
        {
            HCXAISiteState state = new HCXAISiteState();
            state.Site = site;
            m_States.Insert(state);
        }
        Print("[HC Expansion AI] sites admitted: build=" + admission.BuildVersion + " world=" + admission.WorldName + " addons=present expansion_ai_settings=loaded globals=fair factions=fair loadouts=present observer=" + admission.ObserverPolicy + " pve_patrols=true ownership=reconciled; binding sites");
        m_Phase = "bind";
        m_Cursor = 0;
    }
    // Every admission input is observed here from the engine, never read from a file.
    protected HCXAISiteAdmission Observe()
    {
        HCXAISiteAdmission a = new HCXAISiteAdmission();
        a.BuildVersion = m_Build;
        string world = GetGame().GetWorldName();
        world.ToLower();
        a.WorldName = world;
        array<string> addons = {"HollowCountryExpansionAI", "DayZExpansion_AI_Scripts", "DayZExpansion_Core_Scripts", "DayZExpansion_Animations_AI", "JM_CF_Scripts"};
        foreach (string addon : addons)
        {
            if (!GetGame().ConfigIsExisting("CfgPatches " + addon)) { a.MissingAddons = a.MissingAddons + addon + " "; }
        }
        a.SettingsLoaded = true;
        HCXAIAdapter adapter = HCXAIService.Adapter();
        if (adapter) { a.Globals = adapter.GlobalsProblem(); }
        else { a.Globals = "adapter not bound"; }
        foreach (HCXAISite factionSite : m_Policy.Sites)
        {
            eAIFaction faction = eAIFaction.Create(factionSite.Faction);
            if (!faction || faction.IsInvincible() || faction.IsObserver() || faction.IsPassive() || faction.HasUnlimitedStamina() || faction.GetMeleeDamageMultiplier() != 1 || faction.GetMeleeYeetForce() != 0)
            {
                a.UnfairFaction = factionSite.Faction;
                break;
            }
        }
        foreach (HCXAISite loadoutSite : m_Policy.Sites)
        {
            if (!FileExist(EXPANSION_LOADOUT_FOLDER + loadoutSite.Loadout + ".json"))
            {
                a.MissingLoadout = loadoutSite.Loadout;
                break;
            }
        }
        a.ObserverPolicy = HCXAISiteDirector.OBSERVER;
        a.Marker = HCXAIQualification.Admitted();
        a.OwnershipReconciled = this.Reconcile();
        return a;
    }
    // Orphan cleanup: any actor in an "HC:" group at startup belongs to a
    // previous session (this director has created nothing yet) and is removed.
    protected bool Reconcile()
    {
        HCXAIOwnership previous = HCXAISiteDirector.LoadOwned();
        if (!previous) { return false; }
        array<eAIBase> all = new array<eAIBase>();
        all.Copy(eAIBase.eAI_GetAll());
        int removed = 0;
        foreach (eAIBase actor : all)
        {
            if (!actor) { continue; }
            eAIGroup group = actor.GetGroup();
            if (!group) { continue; }
            string groupName = group.GetName();
            if (groupName.Length() < 3 || groupName.Substring(0, 3) != "HC:") { continue; }
            actor.eAI_Despawn();
            removed++;
        }
        int rows = previous.Rows.Count();
        Print("[HC Expansion AI] sites ownership: previous session " + previous.Session.ToString() + " listed " + rows.ToString() + " live sites; removed " + removed.ToString() + " orphan actors");
        m_Owned = new HCXAIOwnership();
        m_Owned.Session = previous.Session + 1;
        return this.SaveOwned();
    }
    protected void StepBind()
    {
        int work = 0;
        while (work < HCXAISiteDirector.WORK_PER_TICK && m_Cursor < m_States.Count())
        {
            this.Bind(m_States[m_Cursor]);
            m_Cursor++;
            work++;
        }
        if (m_Cursor < m_States.Count()) { return; }
        int bound = 0;
        foreach (HCXAISiteState counted : m_States)
        {
            if (counted.Bound) { bound++; }
        }
        Print("[HC Expansion AI] sites bound: " + bound.ToString() + "/" + m_States.Count().ToString() + "; qualifying routes on the navmesh");
        m_Phase = "qualify";
        m_Cursor = 0;
    }
    protected void Bind(HCXAISiteState state)
    {
        HCXAISite site = state.Site;
        if (site.Kind != "holdout")
        {
            foreach (vector waypoint : site.Waypoints)
            {
                state.Points.Insert(Vector(waypoint[0], GetGame().SurfaceY(waypoint[0], waypoint[2]), waypoint[2]));
            }
        }
        else
        {
            array<Object> objects = new array<Object>();
            array<CargoBase> cargos = new array<CargoBase>();
            GetGame().GetObjectsAtPosition(site.HousePosition, 10, objects, cargos);
            float best = 11;
            foreach (Object candidate : objects)
            {
                if (!candidate || candidate.GetType() != site.HouseClass) { continue; }
                float gap = vector.Distance(candidate.GetPosition(), site.HousePosition);
                if (gap < best)
                {
                    best = gap;
                    state.HouseObject = candidate;
                }
            }
            if (!state.HouseObject)
            {
                state.Failed = true;
                state.Reason = "house " + site.HouseClass + " not found at its position";
                Print("[HC Expansion AI] site " + site.Id + " not bound: " + state.Reason);
                return;
            }
            foreach (vector inner : site.LocalPoints)
            {
                state.Points.Insert(state.HouseObject.ModelToWorld(inner));
            }
            state.CacheWorld = ExpansionAISpawnBase.GetPlacementPosition(state.HouseObject.ModelToWorld(site.CacheLocal));
            state.CacheOrientation = state.HouseObject.GetOrientation();
        }
        ExpansionSHA256.Update(HCXAISiteRules.RouteText(site, m_Build));
        state.Key = ExpansionSHA256.HexDigest();
        ExpansionSHA256.Reset();
        state.Bound = true;
    }
    protected HCXAIRouteRow RouteRow(string key)
    {
        foreach (HCXAIRouteRow row : m_Routes.Rows)
        {
            if (row.Key == key) { return row; }
        }
        return null;
    }
    protected void StepQualify()
    {
        int work = 0;
        while (work < HCXAISiteDirector.WORK_PER_TICK && m_Cursor < m_States.Count())
        {
            HCXAISiteState state = m_States[m_Cursor];
            if (!state.Bound || state.Failed || state.Qualified)
            {
                m_Cursor++;
                continue;
            }
            this.QualifyStep(state);
            work++;
        }
        if (m_Cursor < m_States.Count()) { return; }
        int qualified = 0;
        foreach (HCXAISiteState counted : m_States)
        {
            if (counted.Qualified) { qualified++; }
        }
        this.SaveRoutes();
        Print("[HC Expansion AI] sites routes qualified: " + qualified.ToString() + "/" + m_States.Count().ToString() + " (navmesh sample + FindPath per leg; cache " + HCXAISiteDirector.ROUTES + " keyed by route and build)");
        m_Phase = "create";
        m_Cursor = 0;
    }
    // One unit of work: sample every point (first call), then one leg per call.
    protected void QualifyStep(HCXAISiteState state)
    {
        AIWorld world = GetGame().GetWorld().GetAIWorld();
        HCXAIRouteRow cached = this.RouteRow(state.Key);
        if (cached && !cached.Qualified)
        {
            state.Failed = true;
            state.Reason = "cached refusal: " + cached.Reason;
            Print("[HC Expansion AI] site " + state.Site.Id + " route refused (cached for this route and build): " + cached.Reason);
            return;
        }
        float radius = 12;
        if (state.Site.Kind == "holdout") { radius = 2; }
        if (state.Sampled.Count() == 0)
        {
            foreach (vector wanted : state.Points)
            {
                vector found = wanted;
                if (!world || !world.SampleNavmeshPosition(wanted, radius, m_Filter, found))
                {
                    this.Refuse(state, HCXAISiteRules.LegProblem(false, false, 0, 0, 0, 0));
                    return;
                }
                state.Sampled.Insert(found);
            }
            if (cached)
            {
                state.Qualified = true;
                state.Cached = true;
            }
            return;
        }
        int legs = state.Sampled.Count() - 1;
        if (state.Site.Behaviour == "LOOP") { legs = state.Sampled.Count(); }
        if (state.Leg >= legs)
        {
            state.Qualified = true;
            HCXAIRouteRow passed = new HCXAIRouteRow();
            passed.Key = state.Key;
            passed.SiteId = state.Site.Id;
            passed.Qualified = true;
            this.Remember(passed);
            return;
        }
        vector legFrom = state.Sampled[state.Leg];
        vector legTo = state.Sampled[(state.Leg + 1) % state.Sampled.Count()];
        TVectorArray path = new TVectorArray();
        bool pathFound = world.FindPath(legFrom, legTo, m_Filter, path);
        float length = 0;
        float endGap = 1000;
        int pathPoints = 0;
        if (pathFound) { pathPoints = path.Count(); }
        int index = 1;
        while (index < pathPoints)
        {
            length = length + vector.Distance(path[index - 1], path[index]);
            index++;
        }
        if (pathPoints > 0) { endGap = vector.Distance(path[pathPoints - 1], legTo); }
        string problem = HCXAISiteRules.LegProblem(true, true, pathPoints, endGap, length, vector.Distance(legFrom, legTo));
        if (problem != "")
        {
            this.Refuse(state, "leg " + state.Leg.ToString() + ": " + problem);
            return;
        }
        state.Leg++;
    }
    protected void Refuse(HCXAISiteState state, string reason)
    {
        state.Failed = true;
        state.Reason = reason;
        HCXAIRouteRow failed = new HCXAIRouteRow();
        failed.Key = state.Key;
        failed.SiteId = state.Site.Id;
        failed.Qualified = false;
        failed.Reason = reason;
        this.Remember(failed);
        Print("[HC Expansion AI] site " + state.Site.Id + " route refused: " + reason);
    }
    protected void Remember(HCXAIRouteRow row)
    {
        int index = m_Routes.Rows.Count() - 1;
        while (index >= 0)
        {
            if (m_Routes.Rows[index].SiteId == row.SiteId) { m_Routes.Rows.Remove(index); }
            index--;
        }
        if (m_Routes.Rows.Count() >= 64) { m_Routes.Rows.Remove(0); }
        m_Routes.Rows.Insert(row);
    }
    protected void StepCreate()
    {
        int work = 0;
        while (work < HCXAISiteDirector.WORK_PER_TICK && m_Cursor < m_States.Count())
        {
            HCXAISiteState state = m_States[m_Cursor];
            m_Cursor++;
            if (!state.Qualified) { continue; }
            this.Create(state);
            work++;
        }
        if (m_Cursor < m_States.Count()) { return; }
        int created = 0;
        string ids = "";
        foreach (HCXAISiteState counted : m_States)
        {
            if (!counted.Patrol) { continue; }
            created++;
            ids = ids + " " + counted.Site.Id;
        }
        Print("[HC Expansion AI] sites created: " + created.ToString() + " native dynamic patrols (activate when a player is inside ActivationRadius and every player is beyond MinPlayerDistance):" + ids);
        m_Phase = "run";
    }
    protected void Create(HCXAISiteState state)
    {
        HCXAISite site = state.Site;
        ExpansionAIDynamicSpawnBase config = new ExpansionAIDynamicSpawnBase(site.NumberOfAI, site.Speed, "SPRINT", site.Behaviour, site.Faction, site.Loadout, true, 0, 1.0, m_Policy.MinPlayerDistance, site.ActivationRadius);
        config.Name = "HC:" + site.Id;
        config.NumberOfAI = site.NumberOfAI;
        config.NumberOfAIMax = site.NumberOfAIMax;
        config.Persist = false;
        config.CanBeLooted = true;
        config.UnlimitedReload = 0;
        config.Chance = 1.0;
        config.CanBeTriggeredByAI = false;
        config.CanSpawnInContaminatedArea = false;
        config.MinDistRadius = m_Policy.MinPlayerDistance;
        config.MaxDistRadius = site.ActivationRadius;
        config.DespawnRadius = site.ActivationRadius + 100;
        config.DespawnTime = site.DespawnSeconds;
        config.RespawnTime = site.RespawnSeconds;
        config.MinSpreadRadius = 0;
        config.MaxSpreadRadius = 0;
        config.DamageMultiplier = 1;
        config.DamageReceivedMultiplier = 1;
        config.HeadshotResistance = 0;
        config.ShoryukenChance = 0;
        config.ShoryukenDamageMultiplier = 1;
        config.EnableFlankingOutsideCombat = 0;
        config.LootingBehaviour = "NONE";
        config.UseRandomWaypointAsStartPoint = false;
        if (site.Kind == "holdout")
        {
            config.Formation = "File";
            config.FormationScale = 1.0;
        }
        config.Waypoints = new TVectorArray();
        foreach (vector point : state.Sampled)
        {
            config.Waypoints.Insert(point);
        }
        HCXAISitePatrol patrol = eAIDynamicPatrolT<HCXAISitePatrol>.CreateEx(config, vector.Zero);
        if (!patrol)
        {
            Print("[HC Expansion AI] site " + site.Id + " native patrol setup refused");
            return;
        }
        patrol.m_HCSiteId = site.Id;
        patrol.m_HCKind = site.Kind;
        patrol.m_HCGroupMax = site.NumberOfAIMax;
        state.Patrol = patrol;
    }
    protected void StepRun()
    {
        this.StepCache();
        if (m_Diagnostic) { this.StepDiagnostic(); }
        if (m_Ticks % 60 != 0) { return; }
        int sites = 0;
        int actors = 0;
        foreach (HCXAISiteState counted : m_States)
        {
            if (!counted.Patrol || !counted.Patrol.m_Group) { continue; }
            sites++;
            actors = actors + counted.Patrol.m_Group.Count();
        }
        if (actors == m_LastActiveAI) { return; }
        m_LastActiveAI = actors;
        Print("[HC Expansion AI] sites active: " + sites.ToString() + " sites, " + actors.ToString() + " actors");
    }
    // Diagnostic only (marker off by default): the first created site of each
    // kind spawns once with no player so Wine runs can observe loadouts.
    protected void StepDiagnostic()
    {
        string done = "|";
        foreach (HCXAISiteState state : m_States)
        {
            if (state.Diagnosed) { done = done + state.Site.Kind + "|"; }
        }
        foreach (HCXAISiteState candidate : m_States)
        {
            if (!candidate.Patrol || candidate.Diagnosed || done.Contains("|" + candidate.Site.Kind + "|")) { continue; }
            candidate.Diagnosed = true;
            Print("[HC Expansion AI] DIAGNOSTIC spawn of site " + candidate.Site.Id + " (" + candidate.Site.Kind + ")");
            candidate.Patrol.Spawn();
            return;
        }
    }
    string SpawnProblemFor(HCXAISitePatrol patrol)
    {
        if (!m_Policy || m_Phase != "run") { return "sites not running"; }
        int activeSites = 0;
        int activeAI = 0;
        foreach (HCXAISiteState state : m_States)
        {
            if (!state.Patrol || state.Patrol == patrol || !state.Patrol.m_Group) { continue; }
            activeSites++;
            activeAI = activeAI + state.Patrol.m_NumberOfAI;
        }
        return HCXAISiteRules.SpawnProblem(m_Policy, activeAI, activeSites, patrol.m_HCGroupMax, this.NearestPlayer(patrol.m_Position), this.SeenByPlayer(patrol.m_Position));
    }
    string MemberProblemFor(vector pos)
    {
        if (!m_Policy || m_Phase != "run") { return "sites not running"; }
        return HCXAISiteRules.MemberSpawnProblem(m_Policy, this.NearestPlayer(pos), this.SeenByPlayer(pos));
    }
    float NearestPlayer(vector pos)
    {
        array<Man> players = new array<Man>();
        GetGame().GetPlayers(players);
        float nearest = 100000;
        foreach (Man player : players)
        {
            if (!player || !player.GetIdentity() || !player.IsAlive()) { continue; }
            float gap = vector.Distance(player.GetPosition(), pos);
            if (gap < nearest) { nearest = gap; }
        }
        return nearest;
    }
    // Native ray from each live player's eye to a standing chest height at pos.
    bool SeenByPlayer(vector pos)
    {
        array<Man> players = new array<Man>();
        GetGame().GetPlayers(players);
        vector aim = pos + Vector(0, 1.2, 0);
        foreach (Man player : players)
        {
            if (!player || !player.GetIdentity() || !player.IsAlive()) { continue; }
            if (vector.Distance(player.GetPosition(), pos) > m_Policy.LineOfSightRange) { continue; }
            vector eye = player.GetPosition() + Vector(0, 1.6, 0);
            vector contact;
            vector contactDir;
            int component;
            bool hit = DayZPhysics.RaycastRV(eye, aim, contact, contactDir, component, null, null, player);
            if (!hit || vector.Distance(contact, aim) < 1.0) { return true; }
        }
        return false;
    }
    void Spawned(HCXAISitePatrol patrol)
    {
        Print("[HC Expansion AI] site " + patrol.m_HCSiteId + " spawned " + patrol.m_NumberOfAI.ToString() + " actors (" + patrol.m_HCKind + ", finite loadout, no unlimited reload)");
        this.SaveOwned();
    }
    void Despawned(HCXAISitePatrol patrol, bool intact)
    {
        Print("[HC Expansion AI] site " + patrol.m_HCSiteId + " despawned (intact=" + intact.ToString() + ")");
        this.SaveOwned();
    }
    // One holdout cache per tick: seed once per lifecycle, adopt after a crash,
    // mark looted when empty or gone, refill only after the cooldown.
    protected void StepCache()
    {
        int count = m_States.Count();
        int tries = 0;
        while (tries < count)
        {
            HCXAISiteState state = m_States[m_CacheCursor % count];
            m_CacheCursor++;
            tries++;
            if (state.Site.Kind != "holdout" || !state.Patrol || !state.HouseObject) { continue; }
            this.CacheStep(state);
            return;
        }
    }
    protected void CacheStep(HCXAISiteState state)
    {
        HCXAISite site = state.Site;
        EntityAI crate = this.FindCrate(state);
        int items = 0;
        if (crate && crate.GetInventory() && crate.GetInventory().GetCargo()) { items = crate.GetInventory().GetCargo().GetItemCount(); }
        bool playerNear = false;
        array<Man> players = new array<Man>();
        GetGame().GetPlayers(players);
        foreach (Man player : players)
        {
            if (player && player.GetIdentity() && vector.Distance(player.GetPosition(), state.CacheWorld) < m_Policy.CacheClearRadius) { playerNear = true; }
        }
        HCXAICacheRow row = this.CacheRow(site.Id);
        int now = ExpansionStatic.GetTimestamp(true);
        bool present = false;
        if (crate) { present = true; }
        string action = HCXAISiteRules.CacheAction(row, present, items, now, playerNear);
        if (action == "seed" || action == "refill")
        {
            this.SeedCache(state, row, now, crate);
            return;
        }
        if (action == "adopt")
        {
            row.State = "seeded";
            this.SaveCaches();
            Print("[HC Expansion AI] site " + site.Id + " cache adopted after an interrupted seed (no new items)");
            return;
        }
        if (action == "mark-looted")
        {
            row.State = "looted";
            row.LootedAt = now;
            row.NextRefillAt = HCXAISiteRules.RefillAt(now, site.CacheCooldownSeconds);
            this.SaveCaches();
            Print("[HC Expansion AI] site " + site.Id + " cache looted or gone; refill not before " + row.NextRefillAt.ToString());
            return;
        }
        if (action == "refuse") { Print("[HC Expansion AI] site " + site.Id + " cache journal row in unknown state " + row.State); }
    }
    protected EntityAI FindCrate(HCXAISiteState state)
    {
        array<Object> objects = new array<Object>();
        array<CargoBase> cargos = new array<CargoBase>();
        GetGame().GetObjectsAtPosition(state.CacheWorld, 1.5, objects, cargos);
        foreach (Object candidate : objects)
        {
            if (candidate && candidate.GetType() == state.Site.CacheClass) { return EntityAI.Cast(candidate); }
        }
        return null;
    }
    protected HCXAICacheRow CacheRow(string siteId)
    {
        foreach (HCXAICacheRow row : m_Caches.Rows)
        {
            if (row.SiteId == siteId) { return row; }
        }
        return null;
    }
    void SeedCache(HCXAISiteState state, HCXAICacheRow row, int now, EntityAI crate)
    {
        HCXAISite site = state.Site;
        if (!row)
        {
            if (m_Caches.Rows.Count() >= 64) { return; }
            HCXAICacheRow newRow = new HCXAICacheRow();
            newRow.SiteId = site.Id;
            m_Caches.Rows.Insert(newRow);
            row = newRow;
        }
        row.ClassName = site.CacheClass;
        row.State = "seeding";
        row.Lifecycle = row.Lifecycle + 1;
        row.SeededAt = now;
        row.LootedAt = 0;
        row.NextRefillAt = 0;
        // Intent is durable before any item exists: a crash from here on can
        // only adopt or mark the cache looted, never seed it twice.
        if (!this.SaveCaches())
        {
            Print("[HC Expansion AI] site " + site.Id + " cache intent not saved; nothing created");
            return;
        }
        if (!crate)
        {
            crate = EntityAI.Cast(GetGame().CreateObjectEx(site.CacheClass, state.CacheWorld, ECE_SETUP | ECE_CREATEPHYSICS | ECE_KEEPHEIGHT | ECE_UPDATEPATHGRAPH | ECE_NOLIFETIME));
            if (crate) { crate.SetOrientation(state.CacheOrientation); }
        }
        if (!crate || !crate.GetInventory())
        {
            Print("[HC Expansion AI] site " + site.Id + " cache container could not be created; left as seeding");
            return;
        }
        int created = 0;
        foreach (HCXAISiteLoot loot : site.CacheLoot)
        {
            int made = 0;
            while (made < loot.Quantity)
            {
                EntityAI item = crate.GetInventory().CreateEntityInCargo(loot.ClassName);
                made++;
                if (!item) { continue; }
                created++;
                Magazine ammo = Magazine.Cast(item);
                if (ammo) { ammo.ServerSetAmmoCount(ammo.GetAmmoMax() / 2); }
            }
        }
        row.State = "seeded";
        this.SaveCaches();
        vector at = state.CacheWorld;
        Print("[HC Expansion AI] site " + site.Id + " cache " + site.CacheClass + " seeded lifecycle " + row.Lifecycle.ToString() + " with " + created.ToString() + " items at " + at.ToString());
    }
    bool SaveCaches()
    {
        if (!m_Caches || m_Caches.Rows.Count() > 64) { return false; }
        string error;
        MakeDirectory("$profile:HollowCountry");
        return JsonFileLoader<HCXAICacheJournal>.SaveFile(HCXAISiteDirector.CACHES, m_Caches, error);
    }
    bool SaveRoutes()
    {
        if (!m_Routes || m_Routes.Rows.Count() > 64) { return false; }
        string error;
        MakeDirectory("$profile:HollowCountry");
        return JsonFileLoader<HCXAIRouteCache>.SaveFile(HCXAISiteDirector.ROUTES, m_Routes, error);
    }
    bool SaveOwned()
    {
        if (!m_Owned) { return false; }
        m_Owned.Rows.Clear();
        foreach (HCXAISiteState state : m_States)
        {
            if (!state.Patrol || !state.Patrol.m_Group) { continue; }
            HCXAIOwnedRow ownedRow = new HCXAIOwnedRow();
            ownedRow.SiteId = state.Site.Id;
            ownedRow.Members = state.Patrol.m_Group.Count();
            m_Owned.Rows.Insert(ownedRow);
        }
        string error;
        MakeDirectory("$profile:HollowCountry");
        return JsonFileLoader<HCXAIOwnership>.SaveFile(HCXAISiteDirector.OWNED, m_Owned, error);
    }
    static string ReadBounded(string path)
    {
        if (!FileExist(path)) { return ""; }
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) { return ""; }
        string data;
        int count = ReadFile(handle, data, 65537);
        CloseFile(handle);
        if (count < 1 || count > 65536) { return ""; }
        return data;
    }
    static HCXAISitePolicy LoadPolicy()
    {
        string data = HCXAISiteDirector.ReadBounded(HCXAISiteDirector.POLICY);
        if (data == "") { return null; }
        string error;
        HCXAISitePolicy policy;
        if (!JsonFileLoader<HCXAISitePolicy>.LoadData(data, policy, error)) { return null; }
        return policy;
    }
    static HCXAIRouteCache LoadRoutes()
    {
        if (!FileExist(HCXAISiteDirector.ROUTES)) { return new HCXAIRouteCache(); }
        string data = HCXAISiteDirector.ReadBounded(HCXAISiteDirector.ROUTES);
        if (data == "") { return null; }
        string error;
        HCXAIRouteCache routes;
        if (!JsonFileLoader<HCXAIRouteCache>.LoadData(data, routes, error) || !routes.Rows || routes.Rows.Count() > 64) { return null; }
        return routes;
    }
    static HCXAICacheJournal LoadCaches()
    {
        if (!FileExist(HCXAISiteDirector.CACHES)) { return new HCXAICacheJournal(); }
        string data = HCXAISiteDirector.ReadBounded(HCXAISiteDirector.CACHES);
        if (data == "") { return null; }
        string error;
        HCXAICacheJournal caches;
        if (!JsonFileLoader<HCXAICacheJournal>.LoadData(data, caches, error) || !caches.Rows || caches.Rows.Count() > 64) { return null; }
        return caches;
    }
    static HCXAIOwnership LoadOwned()
    {
        if (!FileExist(HCXAISiteDirector.OWNED)) { return new HCXAIOwnership(); }
        string data = HCXAISiteDirector.ReadBounded(HCXAISiteDirector.OWNED);
        if (data == "") { return null; }
        string error;
        HCXAIOwnership journal;
        if (!JsonFileLoader<HCXAIOwnership>.LoadData(data, journal, error) || !journal.Rows || journal.Rows.Count() > 64) { return null; }
        return journal;
    }
}
