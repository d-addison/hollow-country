// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:902/917 map Set/Contains (hash lookup).
// #149 / w39: finite carcass economy + native wildlife activity/target providers.
// Spec/plan/task: supplied #149 brief; central spec paths absent in this worktree.
// Installed scripts-1.30.164289 native evidence:
// 2_GameLib/gameLib.c:4 GetGame; 1_Core/proto/EnConvert.c:210 vector.DistanceSq;
// 3_Game/Global/Game.c:703 CreateObjectEx, :705 ObjectDelete, :1120 IsServer,
// :914 GetTickTime, :1176 SurfaceY, :1535 GetTime; 3_Game/Entities/Object.c:215 IsPendingDeletion,
// :287 GetPosition, :511 IsKindOf, :517 IsAlive, :1015 SetHealth;
// 3_Game/Entities/Man.c:21 GetIdentity; EntityAI.c:754 CanBeTargetedByAI;
// 4_World/Entities/ManBase/PlayerBase.c:3935 CanBeTargetedByAI;
// 3_Game/Entities/DayZAnimalInputController.c:3-24 behaviour slot enum;
// 3_Game/CE/CentralEconomy.c:17 ECE_INITAI, :31 ECE_NOPERSISTENCY_WORLD,
// :38 ECE_PLACE_ON_SURFACE; 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; EnDebug.c:96 Print;
// 1_Core/proto/EnScript.c:380/385/399/394/407/470 Count/Clear/Get/Find/Insert/RemoveOrdered.
// Visibility is the existing HCEcologyMigrationNative.PointHidden ray provider.
// Native ZombieBase.c:70-72 already includes AnimalBase in targetable types;
// :685 reads the ENGINE's selected target, not a script-selected nearby animal.
// Expansion evidence (read only, no copied implementation or API calls):
// ai/4_World/DayZExpansion_AI/Entities/DayZPlayerImplement.c:95-103 preserves
// native CanBeTargetedByAI plus faction checks. AnimalBase.c:42-49 exposes its
// creature target information to Expansion's existing perception pipeline.
// Eligibility is a pure native passthrough: never reserve a queried candidate.
// Damage-contact receipts are bounded; no native combat cap is installed.
// Follow-up: a safe actual-target lifecycle
// covering both infected and wolves, preserving native target choice/brains.
// Inspected: 4_World/Entities/Creatures/Infected/ZombieBase.c:685,726 reads
// actual infected targets; 3_Game/Entities/DayZAnimal.c:772-775 starts/signals
// animal attacks without a target argument. No shared pair lifecycle found.
// W2 reinspection: 3_Game/AI/AIAgent.c:6-7 exposes idle/group only;
// AIGroup.c:15 exposes behaviour, but AIGroupBehaviour.c:1-5 has no goal API.
// AIGroupBehaviour.c:20-35 waypoints belong to BehaviourGroupInfectedPack,
// not animals. DayZCreatureAIInputController.c:3-27 movement/slot overrides
// and DayZAnimalInputController.c:54 action override are not destination,
// perception or consumption transactions. Do not substitute these for goals.

class HCWildlifeProviderSite
{
    string Id;
    vector Position;
}

class HCWildlifeProviderConfig
{
    int Version;
    bool Enabled;
    bool SeasonalRoutesEnabled;
    bool CluesEnabled;
    bool InteractionObservationEnabled;
    int ClueLifetimeSeconds;
    ref array<ref HCWildlifeRoute> Routes;
    bool CarcassesEnabled;
    bool TargetPairsEnabled;
    int TickMs;
    int WorkUnits;
    int MaxCarcasses;
    // Bound actual damage-contact bookkeeping; never cap native combat.
    int MaxPairs;
    int MaxPairChecksPerTick;
    int PairLifetimeMs;
    int PairCooldownMs;
    int MaxPlayerChecks;
    float MinPlayerDistanceM;
    string CarcassClass;
    string WorldName;
    ref array<ref HCWildlifeProviderSite> Sites;
}

class HCWildlifeProviderState
{
    int Version = 1;
    // Permanent finite allocation: never pruned/reset at boot or after looting.
    ref array<string> SpentSites = new array<string>;
}

class HCWildlifeCarcassIO : HCEventRewardIO
{
    void HCWildlifeCarcassIO()
    {
        m_Root = "$profile:HollowCountry/Events/wildlife-carcasses";
    }
}

class HCWildlifeProviders
{
    protected static ref HCWildlifeProviders s_Owner;
    protected ref HCWildlifeProviderConfig m_Config;
    protected ref HCWildlifeProviderState m_State;
    protected ref HCEncounterStore<HCWildlifeProviderState> m_Store;
    protected ref HCEventRewardLedger m_Ledger;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCOperationalStatus m_GoalsStatus = new HCOperationalStatus;
    protected bool m_Running;
    protected bool m_Fault;
    protected bool m_AdmissionPrinted;
    protected string m_Refusal;
    protected string m_RuntimeFault;
    protected string m_ClueFault;
    protected string m_LastDependency;
    protected int m_LastTick = -1;
    protected int m_LastNow = -1;
    protected int m_Cursor;
    // Alternate the finite creation item with maintenance on the existing slot.
    // Neither path can consume the other path's starvation allowance first.
    protected bool m_CarcassTurn = true;
    protected int m_LastReport = -1;
    protected int m_Attempts;
    protected int m_Spawned;
    protected int m_RefusedBudget;
    protected int m_RefusedPlayers;
    protected int m_RefusedNear;
    protected int m_RefusedVisible;
    protected int m_RefusedPosition;
    protected int m_RefusedSpent;
    protected int m_RefusedAllocation;
    protected int m_RefusedEconomy;
    protected int m_RefusedCreation;
    protected int m_PairsAdmitted;
    protected int m_PairsRefused;

    static string HCActivity(int slot)
    {
        if (slot == DayZAnimalBehaviourSlot.EATING) { return "feeding"; }
        if (slot == DayZAnimalBehaviourSlot.DRINKING) { return "drinking"; }
        if (slot == DayZAnimalBehaviourSlot.CALM_GRAZING) { return "grazing"; }
        // Travelling alone cannot identify what resource, if any, was sought.
        if (slot == DayZAnimalBehaviourSlot.CALM_TRAVELLING) { return "resource_seeking_unknown"; }
        return "native";
    }

    static void HCStart(bool enabled)
    {
        if (!HCEcologyNative.Authority()) { return; }
        // Retain owner across off/on: a toggle must not reset the session ledger.
        if (!s_Owner) { s_Owner = new HCWildlifeProviders; }
        s_Owner.HCOpen(enabled);
    }

    static void HCTick(int nowMs)
    {
        if (s_Owner) { s_Owner.HCStep(nowMs); }
    }

    static void HCStop()
    {
        if (!s_Owner) { return; }
        if (s_Owner.m_Running) { s_Owner.HCReport(true); }
        s_Owner.m_Running = false;
        s_Owner.m_Refusal = "";
        s_Owner.m_RuntimeFault = "";
        s_Owner.HCEcosystemStop();
        s_Owner.HCObserve();
    }

    static bool HCNativePermit(EntityAI attacker, EntityAI prey)
    {
        // No query-side budget, reservation, timer or engine access. Native
        // eligibility remains authoritative even when queried repeatedly.
        return true;
    }

    static bool HCValid(HCWildlifeProviderConfig config)
    {
        if (!config || !config.Sites) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("WildlifeProviders.Version", config.Version)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("WildlifeProviders.TickMs", config.TickMs)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("WildlifeProviders.WorkUnits", config.WorkUnits)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("WildlifeProviders.MaxCarcasses", config.MaxCarcasses)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("WildlifeProviders.MaxPairs", config.MaxPairs)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("WildlifeProviders.MaxPairChecksPerTick", config.MaxPairChecksPerTick)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("WildlifeProviders.PairLifetimeMs", config.PairLifetimeMs)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("WildlifeProviders.PairCooldownMs", config.PairCooldownMs)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("WildlifeProviders.MaxPlayerChecks", config.MaxPlayerChecks)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("WildlifeProviders.MinPlayerDistanceM", config.MinPlayerDistanceM)) { return false; }
        if (config.WorldName != "chernarusplus") { return false; }
        // Only the inspected stock red deer body; no arbitrary operator loot class.
        if (config.CarcassClass != "Animal_CervusElaphus") { return false; }
        if (config.Sites.Count() < 1 || config.Sites.Count() > config.MaxCarcasses) { return false; }
        map<string, bool> seen = new map<string, bool>;
        array<ref HCWildlifeProviderSite> sites = config.Sites;
        foreach (HCWildlifeProviderSite site : sites)
        {
            if (!site || !HCEventDirector.TextValid(site.Id, 48) || !HCEcologyRuntimeRules.PositionValid(site.Position)) { return false; }
            if (seen.Contains(site.Id)) { return false; }
            seen.Set(site.Id, true);
        }
        return true;
    }

    bool HCRefuse(string reason)
    {
        if (m_Running) { m_RuntimeFault = reason; }
        if (m_Refusal != reason)
        {
            m_Refusal = reason;
            Print("[HC Plan] HC-149 wildlife_provider reason=" + reason + " runtime=PENDING");
        }
        HCObserve();
        return false;
    }

    void HCObserve()
    {
        string fault = m_RuntimeFault;
        string dependency = HCClueDependency();
        if (fault == "") { fault = dependency; }
        if (m_Fault) { fault = "wildlife_allocation_store_uncertain"; }
        // A missing goal port never disables independent observation/carcasses.
        // A configured clue dependency failure is real degradation (#223).
        string ready = "configured_carcasses_phase_data_contacts_admitted_goals_separate";
        HCModuleReadiness.HCDerive(m_Status, m_Running, m_Refusal, fault, ready);
        HCOperationalOwner owner = HCOperationalContributors.HCRegisterOwner("HC-149");
        if (owner) { owner.HCObserve(m_Running, m_Status, GetGame().GetTickTime()); }
        if (dependency != m_LastDependency)
        {
            m_LastDependency = dependency;
            string availability = "available_or_opted_out";
            if (dependency != "") { availability = dependency; }
            Print("[HC Wildlife] W2_CLUE_DEPENDENCY state=" + availability + " carcasses_and_contacts=independent runtime=PENDING");
        }
        bool goalsRequested = m_Running && m_Config && (m_Config.SeasonalRoutesEnabled || m_Config.CluesEnabled);
        HCModuleReadiness.HCDerive(m_GoalsStatus, false, "", "", "");
        if (goalsRequested) { m_GoalsStatus.HCPublish("requested", "admitted_unverified_no_native_animal_goal_port"); }
        HCOperationalOwner goals = HCOperationalContributors.HCRegisterOwner("HC-149-goals");
        if (goals) { goals.HCObserve(goalsRequested, m_GoalsStatus, GetGame().GetTickTime()); }
    }

    string HCClueDependency()
    {
        if (!m_Running || !m_Config || !m_Config.CluesEnabled) { return ""; }
        if (m_ClueFault != "") { return m_ClueFault; }
        if (HCWorldIncidents.HCOff()) { return "clues_unavailable_world_incidents_off"; }
        if (!HCWorldIncidents.HCGet().HCActive()) { return "clues_unavailable_world_incidents_not_started"; }
        if (!HCWildlifeObservation.HCObservationAvailable()) { return "carcass_clues_unavailable_observation_off_or_refused"; }
        return "";
    }

    bool HCOpen(bool enabled)
    {
        if (!enabled || FileExist("$profile:HollowCountry/acceptance/wildlife_providers.disable")) { HCStop(); return false; }
        if (m_Running || m_Fault) { return m_Running && !m_Fault; }
        string text = HCEcologyRuntimeIO.Read("$mission:hollow-country/ecology/HCWildlife-providers.json", 16384);
        string error;
        if (text == "" || !JsonFileLoader<HCWildlifeProviderConfig>.LoadData(text, m_Config, error)) { return HCRefuse("provider_config_unreadable"); }
        // Explicit false remains distinct from omitted booleans zero-filled by JSON.
        if (!HCJsonFields.Every(text, "Enabled", 1) || !HCJsonFields.Every(text, "CarcassesEnabled", 1) || !HCJsonFields.Every(text, "TargetPairsEnabled", 1)) { return HCRefuse("provider_flags_missing"); }
        if (!HCJsonFields.Has(text, "SeasonalRoutesEnabled") || !HCJsonFields.Has(text, "CluesEnabled") || !HCJsonFields.Has(text, "InteractionObservationEnabled")) { return HCRefuse("ecosystem_flags_missing"); }
        if (!HCJsonFields.Every(text, "Phase", 3, "Species") || !HCJsonFields.Every(text, "RadiusM", 3, "Species")) { return HCRefuse("ecosystem_route_fields_missing"); }
        if (!HCJsonFields.Every(text, "Position", 3)) { return HCRefuse("provider_site_position_missing"); }
        if (!HCOperatorSettingsRegistry.HCValid("WildlifeProviders.Version", 1)) { return HCRefuse("provider_settings_registry_missing"); }
        if (!HCValid(m_Config)) { return HCRefuse("provider_config_invalid"); }
        // Old profiles requested 16 units before doing any maintenance. Keep
        // those profiles usable, with a hard four-item maintenance slice.
        m_Config.WorkUnits = Math.Min(m_Config.WorkUnits, 4);
        m_Config.MaxPairChecksPerTick = Math.Min(m_Config.MaxPairChecksPerTick, m_Config.WorkUnits);
        m_Config.MaxPlayerChecks = Math.Min(m_Config.MaxPlayerChecks, 16);
        if (m_Config.WorldName != HCEcologyMigrationNative.CurrentWorld()) { return HCRefuse("provider_world_mismatch"); }
        if (!m_Config.Enabled) { HCStop(); return false; }
        if (m_Config.CarcassesEnabled)
        {
            if (!m_Store)
            {
                m_Store = new HCEncounterStore<HCWildlifeProviderState>("hc149-wildlife-allocations");
                HCWildlifeProviderState fresh = new HCWildlifeProviderState;
                m_State = m_Store.Load(fresh, "SpentSites");
            }
            if (!m_State || m_State.Version != 1 || !m_State.SpentSites || m_State.SpentSites.Count() > 8) { m_Fault = true; return HCRefuse("allocation_state_invalid"); }
            array<string> spent = m_State.SpentSites;
            map<string, bool> seen = new map<string, bool>;
            foreach (string spentId : spent)
            {
                if (!HCEventDirector.TextValid(spentId, 48) || seen.Contains(spentId)) { m_Fault = true; return HCRefuse("allocation_identity_invalid"); }
                seen.Set(spentId, true);
            }
            if (!m_Ledger)
            {
                HCEventRewardPool pool = new HCEventRewardPool;
                pool.MaxCaches = m_Config.MaxCarcasses;
                pool.ItemsPerCache = 1;
                HCEventRewardEntry entry = HCEventRewardPools.Entry(m_Config.CarcassClass, m_Config.MaxCarcasses);
                pool.Entries.Insert(entry);
                HCWildlifeCarcassIO io = new HCWildlifeCarcassIO;
                m_Ledger = new HCEventRewardLedger;
                if (!m_Ledger.Configure(io, pool) || !m_Ledger.Start()) { m_Fault = true; return HCRefuse("carcass_economy_unavailable"); }
            }
        }
        if (!HCEcosystemOpen()) { return false; }
        m_Running = true;
        m_RuntimeFault = "";
        m_Refusal = "";
        if (!m_AdmissionPrinted)
        {
            m_AdmissionPrinted = true;
            Print(HCV2Admission.Line("WildlifeProviders", true, "N9-wildlife", false) + " runtime=PENDING");
            Print("[HC Plan] HC-149 wildlife_provider native_brains=retained carcasses=finite pair_selection=native interaction_observation=bounded combat_cap=unavailable runtime=PENDING");
            Print("[HC Wildlife] provider_budget creation_units=8 maintenance_items=" + m_Config.WorkUnits.ToString() + " scheduling=alternating target_pairs=" + m_Config.TargetPairsEnabled.ToString() + " pair_mode=damage_contacts_only runtime=PENDING");
        }
        HCObserve();
        return true;
    }

    bool HCClaim(string siteId)
    {
        if (m_Fault || m_State.SpentSites.Count() >= m_Config.MaxCarcasses || m_State.SpentSites.Find(siteId) >= 0) { return false; }
        m_State.SpentSites.Insert(siteId);
        // The permanent claim is spent even when economy admission or creation
        // fails. A crash between either barrier and native creation cannot replay.
        if (!m_Store.Save(m_State)) { m_Fault = true; return false; }
        return true;
    }

    bool HCHidden(vector point)
    {
        array<Man> players = HCPerfPlayers.HCGet();
        if (!players || players.Count() > m_Config.MaxPlayerChecks) { m_RefusedPlayers++; return false; }
        foreach (Man candidate : players)
        {
            PlayerBase observer = PlayerBase.Cast(candidate);
            if (!observer) { m_RefusedPlayers++; return false; }
            if (vector.DistanceSq(observer.GetPosition(), point) <= m_Config.MinPlayerDistanceM * m_Config.MinPlayerDistanceM) { m_RefusedNear++; return false; }
            if (!HCEcologyMigrationNative.PointHidden(observer, null, point)) { m_RefusedVisible++; return false; }
        }
        return true;
    }

    AnimalBase HCCreate(HCWildlifeProviderSite site)
    {
        if (!m_Running || m_Fault || !HCEcologyNative.Authority()) { return null; }
        if (!HCHidden(site.Position)) { return null; }
        if (!HCClaim(site.Id)) { m_RefusedAllocation++; HCRefuse("carcass_allocation_claim_failed"); return null; }
        HCEventRewardPlan plan = m_Ledger.Commit(site.Id);
        if (!plan) { m_RefusedEconomy++; HCRefuse("carcass_economy_claim_not_issued"); return null; }
        int flags = ECE_PLACE_ON_SURFACE | ECE_NOPERSISTENCY_WORLD | ECE_INITAI;
        Object created = GetGame().CreateObjectEx(plan.Items.Get(0), site.Position, flags);
        AnimalBase body = AnimalBase.Cast(created);
        if (!body)
        {
            if (created) { GetGame().ObjectDelete(created); }
            m_RefusedCreation++;
            HCRefuse("carcass_creation_failed_allocation_spent");
            return null;
        }
        body.SetHealth("", "Health", 0);
        m_Spawned++;
        HCReached.Mark("wildlife.carcass.spawn");
        Print("[HC Plan] HC-149 authored_carcass site=" + site.Id + " allocation=spent creation=issued death=issued runtime=PENDING");
        // Some animal deaths replace the body (native AnimalBase.c:32-40).
        // No retained handle, forced skinning, inventory writes or replay here.
        return body;
    }

    void HCStep(int nowMs)
    {
        if (!m_Running || !HCEcologyNative.Authority()) { return; }
        if (m_Fault) { HCObserve(); return; }
        if (nowMs < 0 || nowMs < m_LastNow) { m_Fault = true; HCRefuse("provider_clock_invalid"); return; }
        m_LastNow = nowMs;
        if (m_LastTick >= 0 && nowMs - m_LastTick < m_Config.TickMs) { return; }
        m_LastTick = nowMs;
        bool pending = m_Config.CarcassesEnabled && m_State && m_State.SpentSites.Count() < m_Config.MaxCarcasses;
        if (pending && m_CarcassTurn)
        {
            // One atomic creation attempt, including at most 16 current
            // observers (six native rays each). Never reuse stale sight checks.
            // Cost 8 is the shared budget's object-creation convention; use the
            // named consumer so exhausted earlier modules cannot starve it.
            HCUnitBudget work = HCServer.HCTickWork();
            if (work.HCTakeFor(HCUnitBudget.HC_WORK_WILDLIFE, 8))
            {
                m_CarcassTurn = false;
                if (m_Cursor >= m_Config.Sites.Count()) { m_Cursor = 0; }
                HCWildlifeProviderSite authored = m_Config.Sites.Get(m_Cursor);
                m_Cursor = m_Cursor + 1;
                if (m_State.SpentSites.Find(authored.Id) >= 0) { m_RefusedSpent++; }
                else
                {
                    m_Attempts++;
                    HCWildlifeProviderSite grounded = new HCWildlifeProviderSite;
                    grounded.Id = authored.Id;
                    grounded.Position = authored.Position;
                    grounded.Position[1] = GetGame().SurfaceY(authored.Position[0], authored.Position[2]);
                    if (HCEcologyRuntimeRules.PositionValid(grounded.Position)) { HCCreate(grounded); }
                    else { m_RefusedPosition++; }
                }
            }
            else { m_RefusedBudget++; }
        }
        else
        {
            m_CarcassTurn = true;
            HCEcosystemStep(nowMs);
        }
        HCReport(false);
        HCObserve();
    }

    // Session counters: first attempted slice, then at most once per ten
    // minutes, plus stop. Fixed fields distinguish idle, spent and refused.
    void HCReport(bool force)
    {
        if (!force && m_LastReport >= 0 && m_LastNow - m_LastReport < 600000) { return; }
        m_LastReport = m_LastNow;
        int spent = 0;
        if (m_State) { spent = m_State.SpentSites.Count(); }
        Print("[HC Wildlife] carcasses attempts=" + m_Attempts.ToString() + " spawned=" + m_Spawned.ToString() + " spent=" + spent.ToString() + " cap=" + m_Config.MaxCarcasses.ToString() + " enabled=" + m_Config.CarcassesEnabled.ToString() + " refused_budget=" + m_RefusedBudget.ToString() + " refused_observers=" + m_RefusedPlayers.ToString() + " refused_near=" + m_RefusedNear.ToString() + " refused_visible=" + m_RefusedVisible.ToString() + " refused_position=" + m_RefusedPosition.ToString() + " skipped_spent=" + m_RefusedSpent.ToString() + " refused_allocation=" + m_RefusedAllocation.ToString() + " refused_economy=" + m_RefusedEconomy.ToString() + " refused_creation=" + m_RefusedCreation.ToString() + " pairs_admitted=" + m_PairsAdmitted.ToString() + " pairs_refused=" + m_PairsRefused.ToString() + " target_pairs=" + m_Config.TargetPairsEnabled.ToString() + " runtime=PENDING");
    }

    protected ref HCWildlifeInteractions m_Interactions;
    protected int m_SeasonPhase = -2;
    protected int m_ClueCursor;
    protected bool m_EcosystemOpen;
    protected bool m_EcosystemPrinted;

    bool HCEcosystemOpen()
    {
        if (!HCWildlifeRoutes.HCConfigValid(m_Config)) { return HCRefuse("ecosystem_config_invalid"); }
        if (!m_Interactions) { m_Interactions = new HCWildlifeInteractions; }
        m_Interactions.HCConfigure(m_Config);
        m_ClueFault = "";
        if (m_Config.CluesEnabled)
        {
            HCWorldIncidentPolicy policy = HCWorldIncidentPolicy.HCGet();
            if (!policy) { m_ClueFault = "ecosystem_incident_policy_missing"; }
            else { HCPrepareClues(policy); }
        }
        m_EcosystemOpen = true;
        if (!m_EcosystemPrinted)
        {
            m_EcosystemPrinted = true;
            string clues = "shared_incidents_dependency_checked";
            if (!m_Config.CluesEnabled) { clues = "off"; }
            Print("[HC Wildlife] AUDITWILD_MEMORY admitted_unverified clues=" + clues + " contacts=observed_only runtime=PENDING");
            bool goalsEnabled = m_Config.SeasonalRoutesEnabled || m_Config.CluesEnabled;
            Print(HCV2Admission.Line("WildlifeGoals", goalsEnabled, "N9-wildlife-goals", false) + " runtime=PENDING");
            if (goalsEnabled)
            {
                Print("[HC Wildlife] AUDITWILD_GOALS_PENDING admitted_unverified reason=no_native_animal_destination_target_or_consumption_port routes=data_only attraction=unavailable crows=unavailable combat_cap=unavailable runtime=PENDING");
            }
        }
        return true;
    }

    void HCPrepareClues(HCWorldIncidentPolicy policy)
    {
        int missing = 0;
        if (!policy.HCFind("wildlife_blood")) { missing = missing + 1; }
        if (!policy.HCFind("wildlife_carcass")) { missing = missing + 1; }
        if (policy.Kinds.Count() + missing > 24) { m_ClueFault = "ecosystem_incident_kind_capacity"; return; }
        // No auditory/visual stimulus invented for a blood point/body.
        // Response none: the registry records memory without giving AI
        // knowledge or silently enlisting Expansion's human-only observer.
        if (!policy.HCFind("wildlife_blood")) { policy.HCAddKind("wildlife_blood", "", "none", 0, 0, 0, 0, m_Config.ClueLifetimeSeconds, 0, ""); }
        if (!policy.HCFind("wildlife_carcass")) { policy.HCAddKind("wildlife_carcass", "", "none", 0, 0, 0, 0, m_Config.ClueLifetimeSeconds, 0, ""); }
    }

    void HCEcosystemStop()
    {
        m_EcosystemOpen = false;
        if (m_Interactions) { m_Interactions.HCClear(); }
        m_SeasonPhase = -2;
    }

    void HCEcosystemStep(int nowMs)
    {
        if (!m_EcosystemOpen) { return; }
        if (!m_Config.SeasonalRoutesEnabled && !m_Config.CluesEnabled && !m_Config.InteractionObservationEnabled) { return; }
        // Share the existing world-incident consumer: these are incident
        // observations. One finite slice; no fresh consumer id or timer.
        HCUnitBudget work = HCServer.HCTickWork();
        if (!work.HCTakeFor(HCUnitBudget.HC_WORK_WILDLIFE, 1)) { m_RefusedBudget++; return; }
        if (m_Config.TargetPairsEnabled && m_Config.InteractionObservationEnabled) { m_Interactions.HCSweep(nowMs); }
        if (m_Config.SeasonalRoutesEnabled)
        {
            int phase = HCWildlifeRoutes.HCPhase();
            if (phase != m_SeasonPhase)
            {
                m_SeasonPhase = phase;
                HCWildlifeRoute graze = HCWildlifeRoutes.HCSelect(m_Config.Routes, "Animal_CervusElaphus", phase);
                HCWildlifeRoute patrol = HCWildlifeRoutes.HCSelect(m_Config.Routes, "Animal_CanisLupus", phase);
                string grazeId = "unavailable";
                string patrolId = "unavailable";
                if (graze) { grazeId = graze.Id; }
                if (patrol) { patrolId = patrol.Id; }
                Print("[HC Wildlife] AUDITWILD_PHASE phase=" + phase.ToString() + " graze=" + grazeId + " territory=" + patrolId + " animal_movement=unavailable runtime=PENDING");
            }
        }
        if (!m_Config.CluesEnabled || HCClueDependency() != "") { return; }
        // HC-15 snapshots already bound freshness, handles, species and count.
        array<ref HCWildlifeFact> facts = HCWildlifeObservation.HCSnapshot(nowMs);
        int examined = 0;
        while (examined < facts.Count() && examined < m_Config.WorkUnits)
        {
            // The first row shares the admitted maintenance item. Additional
            // rows each need another unit; WorkUnits=1 still advances clues.
            if (examined > 0 && !work.HCTakeFor(HCUnitBudget.HC_WORK_WILDLIFE, 1)) { m_RefusedBudget++; break; }
            if (m_ClueCursor >= facts.Count()) { m_ClueCursor = 0; }
            HCWildlifeFact fact = facts.Get(m_ClueCursor);
            m_ClueCursor = m_ClueCursor + 1;
            examined = examined + 1;
            if (!HCEcologyResourceSurvey.Carcass(fact)) { continue; }
            HCWorldIncidents.HCPublish("wildlife_carcass", fact.Position, 0, m_Config.ClueLifetimeSeconds, null);
        }
    }

    static void HCRecordDamage(EntityAI victim, EntityAI source, TotalDamageResult damageResult, string zone)
    {
        if (!s_Owner || !s_Owner.m_Running || !s_Owner.m_EcosystemOpen || !HCEcologyNative.Authority()) { return; }
        if (!s_Owner.m_Config.CluesEnabled && !(s_Owner.m_Config.TargetPairsEnabled && s_Owner.m_Config.InteractionObservationEnabled)) { return; }
        if (!victim || victim.IsPendingDeletion() || !damageResult) { return; }
        int nowMs = GetGame().GetTime();
        if (nowMs < s_Owner.m_LastNow || nowMs < 0) { return; }
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_WILDLIFE, 1)) { return; }
        // Actual positive blood damage only, never inferred from proximity,
        // bleeding state, live position polling or a targeting eligibility query.
        if (s_Owner.m_Config.CluesEnabled && s_Owner.m_ClueFault == "" && !HCWorldIncidents.HCOff() && HCWorldIncidents.HCGet().HCActive() && damageResult.GetDamage(zone, "Blood") > 0)
        {
            vector point = victim.GetPosition();
            if (HCEcologyRuntimeRules.PositionValid(point)) { HCWorldIncidents.HCPublish("wildlife_blood", point, 0, s_Owner.m_Config.ClueLifetimeSeconds, null); }
        }
        // This setting controls bounded receipts of actual pairs, never native
        // targeting or combat admission. Clues remain independent of it.
        if (!s_Owner.m_Config.TargetPairsEnabled || !s_Owner.m_Config.InteractionObservationEnabled || !source) { return; }
        bool pair = AnimalBase.Cast(victim) && ZombieBase.Cast(source);
        PlayerBase campActor = PlayerBase.Cast(victim);
        if (campActor && !campActor.GetIdentity() && source.IsKindOf("Animal_CanisLupus")) { pair = true; }
        if (pair)
        {
            if (s_Owner.m_Interactions.HCContact(source, victim, nowMs)) { s_Owner.m_PairsAdmitted++; }
            else { s_Owner.m_PairsRefused++; }
        }
    }

}

modded class AnimalBase
{
    override bool CanBeTargetedByAI(EntityAI ai)
    {
        bool nativeEligible = super.CanBeTargetedByAI(ai);
        if (!nativeEligible) { return nativeEligible; }
        if (ZombieBase.Cast(ai) && !HCWildlifeProviders.HCNativePermit(ai, this)) { return false; }
        return nativeEligible;
    }
}

modded class PlayerBase
{
    override bool CanBeTargetedByAI(EntityAI ai)
    {
        bool nativeEligible = super.CanBeTargetedByAI(ai);
        if (!nativeEligible) { return nativeEligible; }
        // Native/Expansion eligibility and faction checks remain in super.
        // Human players are untouched. Only live server AI camp actors qualify.
        if (!GetIdentity() && ai && ai.IsKindOf("Animal_CanisLupus") && !HCWildlifeProviders.HCNativePermit(ai, this)) { return false; }
        return nativeEligible;
    }
}
