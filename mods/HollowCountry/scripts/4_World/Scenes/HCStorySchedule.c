// HC-19 / #147. Bounded independent arrivals; runtime acceptance pending.
// Consumed by Scenes AFTER #138 integration; no module registration here.
// World schedule: existing HCScenesModule.Now / HCGroupClock.Utc, UTC seconds
// since 2020 INCLUDING downtime. Never use HCVisualSeasons' server-uptime clock.
// Native 1.30.164289: 3_Game/tools/JsonFileLoader.c:69 LoadData;
// 1_Core/proto/EnSystem.c:397 FileExist; EnDebug.c:96 Print;
// EnScript.c:380 Count, :394 Find, :407 Insert, :463 Remove, :470 RemoveOrdered;
// EnConvert.c:30 int.ToString. IO remains HCGroupIO / HCSceneChainStore.
// HCWorkBudget owns Game.c:914 GetTickTime; no new engine observation API.
// N10 CentralEconomy.c CEApi exposes economy controls, not a demonstrated
// durable story identity/lifecycle port. Refusal: native-ce-story-identity.
// This service schedules HC-owned reviewed scenes ONLY. No CE discovery,
// inventory creation/refund, corpse mutation or external event adoption.

class HCStorySettings
{
    int Version = 1;
    bool EnableStories = true;
    int ArrivalSeconds = 21600;
    int Window = 4;
}

class HCStoryProgress
{
    int Version = 1;
    int NextSequence = 1;
    int LegacyThrough;
    int TerminalThrough;
    int NextArrival;
    // Fixed migration set (<=4), not an ever-growing terminal ledger.
    ref array<string> LegacyIds = new array<string>();
    ref array<int> TerminalExceptions = new array<int>();
}

class HCStoryPolicy
{
    static bool HCConfigValid(HCStorySettings config)
    {
        return config && config.Version == 1 && config.ArrivalSeconds >= 3600 && config.ArrivalSeconds <= 259200 && config.Window == 4;
    }

    static HCStorySettings HCLoadConfig()
    {
        string path = "$profile:HollowCountry/hollow-country-stories.json";
        HCStorySettings config = new HCStorySettings;
        if (!FileExist(path)) { return config; }
        string text;
        string error;
        if (!HCGroupIO.Read(path, 4096, text) || !JsonFileLoader<HCStorySettings>.LoadData(text, config, error)) { return null; }
        if (!HCConfigValid(config)) { return null; }
        return config;
    }

    // Every issued identity is either retained, in bounded terminal exceptions,
    // or <= TerminalThrough. No hole, duplicate or replay can be admitted.
    static bool HCValid(HCSceneChainState state)
    {
        if (!state || !state.Chains) { return false; }
        if (state.Chains.Count() > 4) { return false; }
        if (!state.Stories)
        {
            if (state.Chains.Count() < 1) { return false; }
            foreach (HCSceneChain legacy : state.Chains)
            {
                if (!legacy || legacy.StorySequence != 0) { return false; }
            }
            return true;
        }
        HCStoryProgress progress = state.Stories;
        if (progress.Version != 1 || progress.LegacyThrough < 1 || progress.LegacyThrough > 4 || progress.TerminalThrough < 0) { return false; }
        if (progress.NextSequence < progress.LegacyThrough + 1 || progress.NextSequence > 999999999 || progress.TerminalThrough >= progress.NextSequence) { return false; }
        if (progress.NextSequence - progress.TerminalThrough > 5 || progress.NextArrival < 1 || progress.NextArrival > 999300000) { return false; }
        if (!progress.TerminalExceptions || progress.TerminalExceptions.Count() > 4 || state.Chains.Count() > 4) { return false; }
        if (!progress.LegacyIds || progress.LegacyIds.Count() != progress.LegacyThrough) { return false; }
        array<string> legacyIds = new array<string>();
        foreach (string legacyId : progress.LegacyIds)
        {
            if (!HCEventDirector.TextValid(legacyId, 32) || legacyIds.Find(legacyId) >= 0) { return false; }
            legacyIds.Insert(legacyId);
        }
        array<int> seen = new array<int>();
        foreach (int terminal : progress.TerminalExceptions)
        {
            if (terminal <= progress.TerminalThrough + 1 || terminal >= progress.NextSequence || seen.Find(terminal) >= 0) { return false; }
            seen.Insert(terminal);
        }
        foreach (HCSceneChain chain : state.Chains)
        {
            if (!chain || chain.StorySequence <= progress.TerminalThrough || chain.StorySequence >= progress.NextSequence || seen.Find(chain.StorySequence) >= 0) { return false; }
            if (chain.StorySequence <= progress.LegacyThrough)
            {
                if (chain.Id != progress.LegacyIds[chain.StorySequence - 1]) { return false; }
            }
            else
            {
                if (chain.Id != HCIdentity(chain.StorySequence, progress.LegacyIds)) { return false; }
            }
            seen.Insert(chain.StorySequence);
        }
        return seen.Count() == progress.NextSequence - progress.TerminalThrough - 1;
    }

    static void HCMigrate(HCSceneChainState state, int now, HCStorySettings config)
    {
        HCStoryProgress progress = new HCStoryProgress;
        // Preserve old IDs, stage deadlines, terminal flags, director/cargo and
        // the entire pinned catalog; numbering adds metadata only.
        foreach (HCSceneChain chain : state.Chains)
        {
            progress.LegacyIds.Insert(chain.Id);
            chain.StorySequence = progress.NextSequence;
            progress.NextSequence = progress.NextSequence + 1;
        }
        progress.LegacyThrough = state.Chains.Count();
        progress.NextArrival = now + config.ArrivalSeconds;
        state.Stories = progress;
    }

    static void HCRetired(HCStoryProgress progress, int sequence)
    {
        progress.TerminalExceptions.Insert(sequence);
        int next = progress.TerminalExceptions.Find(progress.TerminalThrough + 1);
        while (next >= 0)
        {
            progress.TerminalExceptions.Remove(next);
            progress.TerminalThrough = progress.TerminalThrough + 1;
            next = progress.TerminalExceptions.Find(progress.TerminalThrough + 1);
        }
    }

    static string HCIdentity(int sequence, array<string> legacyIds)
    {
        string identity = "hc-story-" + sequence.ToString();
        // <=4 collisions: max length 26 for nine digit sequences, within the
        // existing 32-character chain ID limit. Sequence text never recurs.
        while (legacyIds.Find(identity) >= 0) { identity = identity + "-n"; }
        return identity;
    }

    static HCSceneChainDefinition HCPlan(int sequence, HCSceneCatalog templates, array<string> legacyIds)
    {
        // Fresh definition, never reuse a terminal director or its cargo. Finite
        // reviewed kits remain unchanged; deterministic site and stage ordering.
        HCSceneChainDefinition seed = templates.Chains[(sequence - 1) % templates.Chains.Count()];
        int count = seed.Stages.Count();
        int variant = sequence % count;
        HCSceneChainDefinition plan = HCSceneChains.Plan(HCIdentity(sequence, legacyIds), seed.SiteId, seed.Stages[variant].Kit, seed.Stages[(variant + 1) % count].Kit, seed.Stages[(variant + 2) % count].Kit);
        // A two-stage seed must stay two-stage (no repeated objective IDs).
        if (count == 2) { plan.Stages.RemoveOrdered(2); }
        int index = 0;
        foreach (HCSceneStageDefinition stage : plan.Stages)
        {
            HCSceneStageDefinition original = seed.Stages[(variant + index) % count];
            stage.HoldSeconds = original.HoldSeconds;
            stage.DelaySeconds = original.DelaySeconds;
            stage.Objective.LifetimeSeconds = original.Objective.LifetimeSeconds;
            stage.Objective.Radius = original.Objective.Radius;
            stage.Objective.DwellSeconds = original.Objective.DwellSeconds;
            stage.Objective.MaxParticipants = original.Objective.MaxParticipants;
            stage.Objective.AnchorClass = original.Objective.AnchorClass;
            index = index + 1;
        }
        return plan;
    }
}

class HCStorySchedule
{
    protected HCSceneChainState m_State;
    protected HCSceneChainStore m_Store;
    protected ref HCStorySettings m_Config;
    protected ref HCSceneCatalog m_Templates;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected int m_Cursor;
    protected bool m_Ready;
    protected string m_Reason;

    // Owner can perform its existing observer-gated cleanup for this exact
    // retained row before supplying the server-only receipt to HCStep.
    HCSceneChain HCCandidate()
    {
        if (!m_Ready || !m_State || m_State.Chains.Count() == 0) { return null; }
        int selected = m_Cursor;
        if (selected >= m_State.Chains.Count()) { selected = 0; }
        return m_State.Chains[selected];
    }

    bool HCReady() { return m_Ready; }
    string HCReason() { return m_Reason; }

    bool HCRefuse(string reason)
    {
        m_Ready = false;
        m_Reason = reason;
        HCReport("refused");
        return false;
    }

    void HCReport(string effective)
    {
        int sequence = 0;
        int active = 0;
        if (m_State && m_State.Stories)
        {
            sequence = m_State.Stories.NextSequence - 1;
            foreach (HCSceneChain retained : m_State.Chains)
            {
                if (!retained.Complete && !retained.Cancelled) { active = active + 1; }
            }
        }
        Print("[HC Plan] HC-19 story_seq=" + sequence.ToString() + " active=" + active.ToString() + " terminal_replay=0 state=" + effective + " reason=" + m_Reason + " clock=world-utc runtime=PENDING");
    }

    bool HCCommit(int now)
    {
        m_State.LastNow = now;
        // A synchronous creation/retirement barrier interrupts any staged
        // heartbeat using the existing store.Save protocol. Caller clears its
        // HCSceneSaveJob.HCInFlight/HCDirty after a successful HCStep mutation.
        // On failure the owner MUST stop Scenes, never materialize live state.
        if (!m_Store.Save(m_State)) { return HCRefuse("save-failed"); }
        HCReport("ready");
        return true;
    }

    bool HCStart(HCSceneChainState state, HCSceneChainStore store, HCStorySettings config, int now, bool enabled)
    {
        if (m_Ready) { return true; }
        m_Reason = "";
        if (!enabled || (config && !HCV2Admission.Admitted(config.EnableStories)))
        {
            m_Reason = "operator-off";
            HCReport("off");
            return false;
        }
        if (!HCStoryPolicy.HCConfigValid(config)) { return HCRefuse("invalid-config"); }
        if (!state || !store || !HCStoryPolicy.HCValid(state)) { return HCRefuse("invalid-state"); }
        if (now < state.LastNow || now < 1 || now > 999000000) { return HCRefuse("world-clock"); }
        m_State = state;
        m_Store = store;
        m_Config = config;
        // Respect the operator catalog for NEW arrivals; pinned old plans are
        // never edited. A future HC-18 admitted template provider plugs in here.
        m_Templates = HCSceneChains.LoadCatalog();
        if (!m_Templates) { return HCRefuse("template-catalog"); }
        m_Cursor = 0;
        if (!state.Stories)
        {
            HCStoryPolicy.HCMigrate(state, now, config);
            // Metadata-only migration must retain the last heartbeat: Scenes
            // still needs ResumeAfterGap to pause its old unfinished stages.
            // NextArrival uses world UTC independently and is never shifted.
            if (!HCCommit(state.LastNow)) { return false; }
        }
        m_Ready = true;
        HCReport("ready");
        // Explicit scope refusal, emitted once per start, not a polling loop.
        Print("[HC Plan] HC-19 state=refused scope=native-ce-story-identity count=0 runtime=PENDING");
        return true;
    }

    // releasedIds: owner-authoritative Cleanup(lease)==true receipts, including
    // no-lease cases. Never accept a client assertion or just a terminal flag.
    // Returns true only after a mutation is durably saved. <=1 retained row per
    // call and <=1 arrival; existing owner still enforces TWO active scene leases,
    // observer clearance, site occupancy and finite placement/cargo policies.
    bool HCStep(int now, array<string> releasedIds)
    {
        if (!m_Ready) { return false; }
        if (now < m_State.LastNow || now < 1 || now > 999000000) { return HCRefuse("world-clock"); }
        m_Units.HCReset(1);
        m_Work.HCReset(1);
        if (!m_Work.HCContinue() || !m_Units.HCTake(1)) { return false; }
        if (m_State.Chains.Count() > 0)
        {
            if (m_Cursor >= m_State.Chains.Count()) { m_Cursor = 0; }
            int selected = m_Cursor;
            m_Cursor = m_Cursor + 1;
            HCSceneChain chain = m_State.Chains[selected];
            if ((chain.Complete || chain.Cancelled) && releasedIds && releasedIds.Find(chain.Id) >= 0)
            {
                HCStoryPolicy.HCRetired(m_State.Stories, chain.StorySequence);
                // Ordered removal keeps each pinned definition aligned with its
                // director; held engine objects never belong to this service.
                m_State.Chains.RemoveOrdered(selected);
                m_State.Catalog.Chains.RemoveOrdered(selected);
                m_Cursor = selected;
                return HCCommit(now);
            }
        }
        HCStoryProgress progress = m_State.Stories;
        if (now < progress.NextArrival || m_State.Chains.Count() >= m_Config.Window) { return false; }
        // Slow/observed oldest story pins the window rather than accumulating
        // unbounded exceptions. A later owner expiry/cleanup unblocks it.
        if (progress.NextSequence - progress.TerminalThrough > m_Config.Window) { return false; }
        if (progress.NextSequence >= 999999999) { return HCRefuse("sequence-exhausted"); }
        HCSceneChainDefinition plan = HCStoryPolicy.HCPlan(progress.NextSequence, m_Templates, progress.LegacyIds);
        HCSceneChain arrived = new HCSceneChain;
        arrived.Id = plan.Id;
        arrived.StorySequence = progress.NextSequence;
        arrived.Director = HCEventDirector.Initialize(m_State.WorldName, arrived.Id);
        HCSceneChains.Schedule(arrived, plan.Stages[0], now);
        m_State.Catalog.Chains.Insert(plan);
        m_State.Chains.Insert(arrived);
        progress.NextSequence = progress.NextSequence + 1;
        // Downtime makes ONE arrival eligible. No catch-up burst or replenishment.
        progress.NextArrival = now + m_Config.ArrivalSeconds;
        return HCCommit(now);
    }

    void HCStop()
    {
        m_Ready = false;
        m_State = null;
        m_Store = null;
        m_Config = null;
        m_Templates = null;
        m_Cursor = 0;
    }
}
