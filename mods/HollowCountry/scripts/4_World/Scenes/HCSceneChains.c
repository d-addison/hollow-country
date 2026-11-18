// LC-T310 / #94, EXP-S3. Timed environmental stages, no artificial player IDs.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist, :525
// MakeDirectory, :528 DeleteFile, :531 CopyFile. No rename API exists in this
// installed script snapshot. HCGroupIO supplies bounded read/write/readback;
// HCGroupClock.Utc supplies bracketed UTC via EnSystem.c:76,100. JSON uses
// 3_Game/tools/JsonFileLoader.c:69 LoadData, :85 MakeData.
// Save is a fail-closed transaction: verified temp -> backup -> install ->
// readback -> remove intent. This is logically atomic admission, NOT a filesystem
// atomic rename/fsync guarantee. Interrupted writes never load backup or reset.
// Common natives: 3_Game/Global/Game.c:1120 IsServer; 1_Core/proto/EnDebug.c:96 Print;
// EnScript.c:380 Count, :394 Find, :407 Insert, :463 Remove; EnConvert.c:30 int.ToString;
// EnString.c:171 ToLower, :199 Length (1_Core/proto).

class HCSceneStageDefinition
{
    string Kit;
    int HoldSeconds = 21600;
    int DelaySeconds = 21600;
    ref HCEventMission Objective;
}

class HCSceneChainDefinition
{
    string Id;
    string SiteId;
    ref array<ref HCSceneStageDefinition> Stages = new array<ref HCSceneStageDefinition>();
}

class HCSceneCatalog
{
    int Version = 1;
    ref array<ref HCSceneChainDefinition> Chains = new array<ref HCSceneChainDefinition>();
}

class HCSceneChain
{
    string Id;
    int Stage;
    int DueAt;
    int ExpiresAt;
    int BeganAt;
    int EventId;
    bool Cancelled;
    bool Complete;
    ref HCEventState Director;
}

class HCSceneChainState
{
    int Version = 1;
    string WorldName;
    int Revision;
    int LastNow;
    // Pin the complete authored plan: edits to mission data cannot shorten a
    // running stage, revive a cancelled chain or silently replace its kit/site.
    ref HCSceneCatalog Catalog;
    ref array<ref HCSceneChain> Chains = new array<ref HCSceneChain>();
}

class HCSceneChains
{
    static bool StageFailed(int now, int expires, int status)
    {
        // Values are HCEventStatus: completed=4, expired=5, cancelled=6.
        // A finished stage may wait for unobserved cleanup past its deadline.
        if (status == 4) { return false; }
        return status == 5 || status == 6 || now >= expires;
    }

    static bool CancelExpired(HCSceneChain chain, int now, int status)
    {
        if (!StageFailed(now, chain.ExpiresAt, status)) { return false; }
        Cancel(chain, now);
        return true;
    }

    static HCEventSite Site(string siteId)
    {
        array<ref HCEventSite> sites = HCEventReviewedSites.Curated();
        foreach (HCEventSite site : sites)
        {
            if (site.Id == siteId) { return site; }
        }
        return null;
    }

    static HCEventContext Context(HCSceneChain chain, int now)
    {
        HCEventContext context = new HCEventContext;
        context.Server = GetGame() && GetGame().IsServer();
        context.WorldName = chain.Director.WorldName;
        context.Session = chain.Director.Session;
        context.Now = now;
        return context;
    }

    static HCSceneChainDefinition Plan(string id, string siteId, string first, string second, string third)
    {
        HCSceneChainDefinition plan = new HCSceneChainDefinition;
        plan.Id = id;
        plan.SiteId = siteId;
        array<string> kinds = new array<string>();
        kinds.Insert(first);
        kinds.Insert(second);
        kinds.Insert(third);
        for (int index = 0; index < kinds.Count(); index++)
        {
            HCSceneStageDefinition stage = new HCSceneStageDefinition;
            stage.Kit = kinds[index];
            if (index == 0) { stage.DelaySeconds = 0; }
            stage.Objective = HCEventReviewedSites.SceneMission(Site(siteId), id + "-" + kinds[index], 43200);
            plan.Stages.Insert(stage);
        }
        return plan;
    }

    static HCSceneCatalog Defaults()
    {
        HCSceneCatalog catalog = new HCSceneCatalog;
        catalog.Chains.Insert(Plan("scene-kamenka", "kamenka-supply-cache", "convoy-wreck", "survivor-distress-camp", "supply-drop-remains"));
        catalog.Chains.Insert(Plan("scene-staroye", "staroye-traffic-cache", "quarantine-checkpoint", "evacuation-point", "last-stand"));
        catalog.Chains.Insert(Plan("scene-kumyrna", "kumyrna-ambush-cache", "last-stand", "survivor-distress-camp", "evacuation-point"));
        // First two finish around hour 30. Leave the third a fresh independent
        // window at hour 36, rather than exhausting its lifetime in a queue.
        catalog.Chains[2].Stages[0].DelaySeconds = 129600;
        return catalog;
    }

    static bool CatalogValid(HCSceneCatalog catalog)
    {
        if (!catalog || catalog.Version != 1 || !catalog.Chains || catalog.Chains.Count() < 1 || catalog.Chains.Count() > 3) { return false; }
        array<string> ids = new array<string>();
        array<string> siteIds = new array<string>();
        foreach (HCSceneChainDefinition plan : catalog.Chains)
        {
            if (!plan || !HCEventDirector.TextValid(plan.Id, 32) || ids.Find(plan.Id) >= 0 || siteIds.Find(plan.SiteId) >= 0) { return false; }
            HCEventSite site = Site(plan.SiteId);
            if (!HCSceneKits.Reviewed(site) || !plan.Stages || plan.Stages.Count() < 2 || plan.Stages.Count() > 3) { return false; }
            ids.Insert(plan.Id);
            siteIds.Insert(plan.SiteId);
            array<string> missions = new array<string>();
            foreach (HCSceneStageDefinition stage : plan.Stages)
            {
                if (!stage || !HCSceneKits.Find(stage.Kit) || stage.HoldSeconds < 3600 || stage.HoldSeconds > 43200 || stage.DelaySeconds < 0 || stage.DelaySeconds > 172800) { return false; }
                HCEventMission mission = stage.Objective;
                if (!HCEventRuntimePolicy.MissionValid(mission, site.WorldName)) { return false; }
                if (mission.SiteId != site.Id || vector.DistanceSq(mission.Source, site.Position) > 0.25 || vector.DistanceSq(mission.Destination, site.Position) > 0.25 || mission.Family != HCEventFamily.INVESTIGATION) { return false; }
                if (mission.ActorBudget != 0 || mission.RewardUnits != 0 || mission.RewardCache || mission.ItemClass != "" || mission.ContainerClass != "") { return false; }
                if (mission.Id != plan.Id + "-" + stage.Kit || missions.Find(mission.Id) >= 0 || mission.LifetimeSeconds <= stage.HoldSeconds) { return false; }
                missions.Insert(mission.Id);
            }
        }
        return true;
    }

    static HCSceneCatalog LoadCatalog()
    {
        string path = "$mission:hollow-country/events/scene-chains.json";
        if (!FileExist(path)) { return Defaults(); }
        string text;
        string error;
        HCSceneCatalog catalog;
        if (!HCGroupIO.Read(path, 32768, text) || !JsonFileLoader<HCSceneCatalog>.LoadData(text, catalog, error)) { return null; }
        if (!CatalogValid(catalog)) { return null; }
        return catalog;
    }

    static HCSceneChainState Fresh(HCSceneCatalog catalog, int now)
    {
        if (!CatalogValid(catalog) || now < 1 || now > 999000000) { return null; }
        HCSceneChainState state = new HCSceneChainState;
        state.WorldName = "chernarusplus";
        state.LastNow = now;
        state.Catalog = catalog;
        foreach (HCSceneChainDefinition plan : catalog.Chains)
        {
            HCSceneChain chain = new HCSceneChain;
            chain.Id = plan.Id;
            chain.Director = HCEventDirector.Initialize(state.WorldName, plan.Id);
            Schedule(chain, plan.Stages[0], now);
            state.Chains.Insert(chain);
        }
        return state;
    }

    static void Schedule(HCSceneChain chain, HCSceneStageDefinition stage, int now)
    {
        chain.DueAt = now + stage.DelaySeconds;
        chain.ExpiresAt = chain.DueAt + stage.Objective.LifetimeSeconds;
        chain.EventId = 0;
        chain.BeganAt = 0;
    }

    static bool StateValid(HCSceneChainState state)
    {
        if (!state || state.Version != 1 || state.WorldName != "chernarusplus" || state.Revision < 0 || state.Revision > 999999999 || state.LastNow < 1 || state.LastNow > 999000000) { return false; }
        if (!CatalogValid(state.Catalog) || !state.Chains || state.Chains.Count() != state.Catalog.Chains.Count()) { return false; }
        for (int index = 0; index < state.Chains.Count(); index++)
        {
            HCSceneChain chain = state.Chains[index];
            HCSceneChainDefinition plan = state.Catalog.Chains[index];
            if (!chain || chain.Id != plan.Id || chain.Stage < 0 || chain.Stage >= plan.Stages.Count() || (chain.Cancelled && chain.Complete)) { return false; }
            if (!HCEventDirector.StateValid(chain.Director) || chain.Director.WorldName != state.WorldName || chain.Director.Session != plan.Id || chain.Director.LastNow > state.LastNow) { return false; }
            if (chain.Director.Records.Count() > plan.Stages.Count() || chain.DueAt < 1 || chain.DueAt > 999300000 || chain.ExpiresAt - chain.DueAt != plan.Stages[chain.Stage].Objective.LifetimeSeconds) { return false; }
            if (chain.EventId < 0 || chain.BeganAt < 0 || chain.BeganAt > state.LastNow || (chain.Director.Records.Count() != chain.Stage + 1 && chain.Director.Records.Count() != chain.Stage)) { return false; }
            HCEventRecord active;
            if (chain.EventId == 0)
            {
                if (chain.BeganAt != 0 || chain.Director.Records.Count() != chain.Stage) { return false; }
            }
            else
            {
                active = HCEventDirector.FindRecord(chain.Director, chain.EventId);
                if (!active || chain.EventId != chain.Stage + 1 || chain.EventId != chain.Director.NextId - 1 || active.Expires != chain.ExpiresAt || chain.BeganAt < chain.DueAt) { return false; }
                if (active.Definition.Id != plan.Stages[chain.Stage].Objective.Id || active.Definition.Goal != 1 || chain.BeganAt >= chain.ExpiresAt) { return false; }
                if (chain.Cancelled && !HCEventDirector.Terminal(active.Status)) { return false; }
            }
            if (chain.Complete && (chain.Stage != plan.Stages.Count() - 1 || chain.EventId == 0)) { return false; }
            if (chain.Complete && active.Status != HCEventStatus.COMPLETED) { return false; }
            for (int recordIndex = 0; recordIndex < chain.Director.Records.Count(); recordIndex++)
            {
                HCEventRecord record = chain.Director.Records[recordIndex];
                HCSceneStageDefinition definition = plan.Stages[recordIndex];
                if (record.Definition.Id != definition.Objective.Id || record.Definition.ObjectiveTag != "scene-duration" || record.Definition.RewardUnits != 0 || record.Definition.ActorBudget != 0 || record.Definition.ItemBudget != 0 || record.Participants.Count() != 0) { return false; }
                if (recordIndex < chain.Stage && record.Status != HCEventStatus.COMPLETED) { return false; }
            }
        }
        return true;
    }

    static bool Begin(HCSceneChain chain, HCSceneStageDefinition stage, int now)
    {
        HCEventContext context = Context(chain, now);
        HCEventDefinition definition = HCEventRuntimePolicy.Definition(stage.Objective);
        definition.ObjectiveTag = "scene-duration";
        // The schedule owns the independent absolute deadline, including time
        // spent waiting on observer clearance or an active-scene budget slot.
        definition.LifetimeSeconds = chain.ExpiresAt - now;
        if (HCEventDirector.Propose(chain.Director, context, definition) != HCEventCode.OK) { return false; }
        chain.EventId = chain.Director.NextId - 1;
        chain.BeganAt = now;
        return Operation(chain, HCEventOp.ANNOUNCE, now) == HCEventCode.OK;
    }

    static int Operation(HCSceneChain chain, int op, int now)
    {
        HCEventRecord record = HCEventDirector.FindRecord(chain.Director, chain.EventId);
        if (!record) { return HCEventCode.NOT_FOUND; }
        HCEventRequest request = new HCEventRequest;
        request.EventId = record.Id;
        request.ExpectedRevision = record.Revision;
        request.Op = op;
        return HCEventDirector.Command(chain.Director, Context(chain, now), request);
    }

    static void Cancel(HCSceneChain chain, int now)
    {
        chain.Cancelled = true;
        if (chain.EventId == 0) { return; }
        HCEventRecord record = HCEventDirector.FindRecord(chain.Director, chain.EventId);
        if (!record || HCEventDirector.Terminal(record.Status)) { return; }
        int op = HCEventOp.CANCEL;
        if (now >= record.Expires) { op = HCEventOp.EXPIRE; }
        Operation(chain, op, now);
    }
}

class HCSceneChainStore
{
    protected string m_Path = "$profile:HollowCountry/scene-chains.json";
    protected bool m_Fault;
    protected string m_Image;
    protected int m_Revision;

    bool Fault()
    {
        m_Fault = true;
        Print("[HollowCountry] V2 scenes persistence refused; preserve scene-chains.json/.tmp/.bak for recovery");
        return false;
    }

    HCSceneChainState Open(int now)
    {
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { Fault(); return null; }
        if (FileExist(m_Path + ".tmp")) { Fault(); return null; }
        HCSceneChainState state;
        if (FileExist(m_Path))
        {
            string error;
            if (!HCGroupIO.Read(m_Path, 65536, m_Image) || !JsonFileLoader<HCSceneChainState>.LoadData(m_Image, state, error)) { Fault(); return null; }
            if (!HCSceneChains.StateValid(state) || now < state.LastNow) { Fault(); return null; }
            m_Revision = state.Revision;
            return state;
        }
        // A missing current image with a surviving backup is not a new world.
        if (FileExist(m_Path + ".bak")) { Fault(); return null; }
        state = HCSceneChains.Fresh(HCSceneChains.LoadCatalog(), now);
        if (!state || !Save(state)) { return null; }
        return state;
    }

    bool Save(HCSceneChainState state)
    {
        if (m_Fault || !HCSceneChains.StateValid(state) || state.Revision != m_Revision || m_Revision >= 999999998) { return Fault(); }
        string actual;
        if (FileExist(m_Path) && (!HCGroupIO.Read(m_Path, 65536, actual) || actual != m_Image)) { return Fault(); }
        state.Revision = m_Revision + 1;
        string text;
        string error;
        if (!JsonFileLoader<HCSceneChainState>.MakeData(state, text, error) || text.Length() > 65536) { return Fault(); }
        m_Fault = true;
        if (!HCGroupIO.WriteNew(m_Path + ".tmp", text, 65536)) { return Fault(); }
        if (FileExist(m_Path))
        {
            if (FileExist(m_Path + ".bak") && !DeleteFile(m_Path + ".bak")) { return Fault(); }
            if (!CopyFile(m_Path, m_Path + ".bak")) { return Fault(); }
            string backup;
            if (!HCGroupIO.Read(m_Path + ".bak", 65536, backup) || backup != m_Image) { return Fault(); }
            if (!DeleteFile(m_Path)) { return Fault(); }
        }
        if (!CopyFile(m_Path + ".tmp", m_Path)) { return Fault(); }
        string installed;
        if (!HCGroupIO.Read(m_Path, 65536, installed) || installed != text || !DeleteFile(m_Path + ".tmp")) { return Fault(); }
        m_Revision = state.Revision;
        m_Image = text;
        m_Fault = false;
        return true;
    }
}
