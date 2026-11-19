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
// This provider only limits native eligibility AFTER super accepted it. It
// never nominates prey, acquires a target, moves an actor, or replaces a brain.

class HCWildlifeProviderSite
{
    string Id;
    vector Position;
}

class HCWildlifeProviderConfig
{
    int Version;
    bool Enabled;
    bool CarcassesEnabled;
    bool TargetPairsEnabled;
    int TickMs;
    int WorkUnits;
    int MaxCarcasses;
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

class HCWildlifePairLease
{
    EntityAI Attacker;
    EntityAI Prey;
    int UntilMs;
    int ReleaseMs;
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
    protected ref array<ref HCWildlifePairLease> m_Pairs = new array<ref HCWildlifePairLease>;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected bool m_Running;
    protected bool m_Fault;
    protected bool m_AdmissionPrinted;
    protected int m_PairChecks;
    protected string m_Refusal;
    protected string m_RuntimeFault;
    protected int m_LastTick = -1;
    protected int m_LastNow = -1;
    protected int m_Cursor;

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
        s_Owner.m_Running = false;
        s_Owner.m_Pairs.Clear();
        s_Owner.HCObserve();
    }

    static bool HCNativePermit(EntityAI attacker, EntityAI prey)
    {
        // Cheap no-op when this feature is off; native super remains authoritative.
        if (!s_Owner || !s_Owner.m_Running || !s_Owner.m_Config.TargetPairsEnabled) { return true; }
        return s_Owner.HCPermit(attacker, prey, GetGame().GetTime());
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
        array<string> seen = new array<string>;
        array<ref HCWildlifeProviderSite> sites = config.Sites;
        foreach (HCWildlifeProviderSite site : sites)
        {
            if (!site || !HCEventDirector.TextValid(site.Id, 48) || !HCEcologyRuntimeRules.PositionValid(site.Position)) { return false; }
            if (seen.Find(site.Id) >= 0) { return false; }
            seen.Insert(site.Id);
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
        if (m_Fault) { fault = "wildlife_allocation_store_uncertain"; }
        HCModuleReadiness.HCDerive(m_Status, m_Running, m_Refusal, fault, "finite_carcasses_native_pair_eligibility");
        HCOperationalOwner owner = HCOperationalContributors.HCRegisterOwner("HC-149");
        if (owner) { owner.HCObserve(m_Running, m_Status, GetGame().GetTickTime()); }
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
        if (!HCJsonFields.Every(text, "Position", 3)) { return HCRefuse("provider_site_position_missing"); }
        if (!HCOperatorSettingsRegistry.HCValid("WildlifeProviders.Version", 1)) { return HCRefuse("provider_settings_registry_missing"); }
        if (!HCValid(m_Config)) { return HCRefuse("provider_config_invalid"); }
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
            array<string> seen = new array<string>;
            foreach (string spentId : spent)
            {
                if (!HCEventDirector.TextValid(spentId, 48) || seen.Find(spentId) >= 0) { m_Fault = true; return HCRefuse("allocation_identity_invalid"); }
                seen.Insert(spentId);
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
        m_Running = true;
        m_RuntimeFault = "";
        m_Refusal = "";
        if (!m_AdmissionPrinted)
        {
            m_AdmissionPrinted = true;
            Print(HCV2Admission.Line("WildlifeProviders", true, "N9-wildlife", false) + " runtime=PENDING");
            Print("[HC Plan] HC-149 wildlife_provider native_brains=retained carcasses=finite pair_selection=native runtime=PENDING");
            Print("[HC Plan] HC-149 missing=animal_resource_goal_and_consumption_api seasonal_routes_blood_trails_carcass_attraction=unimplemented runtime=PENDING");
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
        if (!players || players.Count() > m_Config.MaxPlayerChecks) { return false; }
        foreach (Man candidate : players)
        {
            PlayerBase observer = PlayerBase.Cast(candidate);
            if (!observer) { return false; }
            if (vector.DistanceSq(observer.GetPosition(), point) <= m_Config.MinPlayerDistanceM * m_Config.MinPlayerDistanceM) { return false; }
            if (!HCEcologyMigrationNative.PointHidden(observer, null, point)) { return false; }
        }
        return true;
    }

    AnimalBase HCCreate(HCWildlifeProviderSite site)
    {
        if (!m_Running || m_Fault || !HCEcologyNative.Authority()) { return null; }
        if (!HCHidden(site.Position) || !HCClaim(site.Id)) { return null; }
        HCEventRewardPlan plan = m_Ledger.Commit(site.Id);
        if (!plan) { HCRefuse("carcass_economy_claim_not_issued"); return null; }
        int flags = ECE_PLACE_ON_SURFACE | ECE_NOPERSISTENCY_WORLD | ECE_INITAI;
        Object created = GetGame().CreateObjectEx(plan.Items.Get(0), site.Position, flags);
        AnimalBase body = AnimalBase.Cast(created);
        if (!body)
        {
            if (created) { GetGame().ObjectDelete(created); }
            HCRefuse("carcass_creation_failed_allocation_spent");
            return null;
        }
        body.SetHealth("", "Health", 0);
        Print("[HC Plan] HC-149 authored_carcass site=" + site.Id + " allocation=spent creation=issued death=issued runtime=PENDING");
        // Some animal deaths replace the body (native AnimalBase.c:32-40).
        // No retained handle, forced skinning, inventory writes or replay here.
        return body;
    }

    bool HCPermit(EntityAI attacker, EntityAI prey, int nowMs)
    {
        if (m_PairChecks >= m_Config.MaxPairChecksPerTick) { return false; }
        m_PairChecks = m_PairChecks + 1;
        if (!attacker || !prey || nowMs < 0 || nowMs < m_LastNow || !HCEcologyNative.Authority()) { return false; }
        if (!attacker.IsAlive() || !prey.IsAlive() || attacker.IsPendingDeletion() || prey.IsPendingDeletion()) { return false; }
        array<ref HCWildlifePairLease> pairs = m_Pairs;
        foreach (HCWildlifePairLease pair : pairs)
        {
            if (pair.Attacker == attacker) { return pair.Prey == prey && nowMs < pair.UntilMs; }
        }
        if (pairs.Count() >= m_Config.MaxPairs || nowMs > 2147483647 - m_Config.PairLifetimeMs - m_Config.PairCooldownMs) { return false; }
        HCWildlifePairLease lease = new HCWildlifePairLease;
        lease.Attacker = attacker;
        lease.Prey = prey;
        lease.UntilMs = nowMs + m_Config.PairLifetimeMs;
        lease.ReleaseMs = lease.UntilMs + m_Config.PairCooldownMs;
        pairs.Insert(lease);
        return true;
    }

    void HCStep(int nowMs)
    {
        if (!m_Running || !HCEcologyNative.Authority()) { return; }
        if (m_Fault) { HCObserve(); return; }
        if (nowMs < 0 || nowMs < m_LastNow) { m_Fault = true; HCRefuse("provider_clock_invalid"); return; }
        m_LastNow = nowMs;
        if (m_LastTick >= 0 && nowMs - m_LastTick < m_Config.TickMs) { return; }
        m_LastTick = nowMs;
        m_PairChecks = 0;
        HCUnitBudget work = HCServer.HCTickWork();
        int pairIndex = m_Pairs.Count() - 1;
        while (pairIndex >= 0)
        {
            if (!work.HCTake(1)) { break; }
            HCWildlifePairLease pair = m_Pairs.Get(pairIndex);
            if (!pair.Attacker || !pair.Prey || nowMs >= pair.ReleaseMs) { m_Pairs.RemoveOrdered(pairIndex); }
            pairIndex = pairIndex - 1;
        }
        if (m_Config.CarcassesEnabled && m_State.SpentSites.Count() < m_Config.MaxCarcasses && work.HCTake(m_Config.WorkUnits))
        {
            if (m_Cursor >= m_Config.Sites.Count()) { m_Cursor = 0; }
            HCWildlifeProviderSite authored = m_Config.Sites.Get(m_Cursor);
            m_Cursor = m_Cursor + 1;
            if (m_State.SpentSites.Find(authored.Id) < 0)
            {
                HCWildlifeProviderSite grounded = new HCWildlifeProviderSite;
                grounded.Id = authored.Id;
                grounded.Position = authored.Position;
                grounded.Position[1] = GetGame().SurfaceY(authored.Position[0], authored.Position[2]);
                if (HCEcologyRuntimeRules.PositionValid(grounded.Position)) { HCCreate(grounded); }
            }
        }
        HCObserve();
    }
}

modded class AnimalBase
{
    override bool CanBeTargetedByAI(EntityAI ai)
    {
        if (!super.CanBeTargetedByAI(ai)) { return false; }
        if (ZombieBase.Cast(ai)) { return HCWildlifeProviders.HCNativePermit(ai, this); }
        return true;
    }
}

modded class PlayerBase
{
    override bool CanBeTargetedByAI(EntityAI ai)
    {
        if (!super.CanBeTargetedByAI(ai)) { return false; }
        // Native/Expansion eligibility and faction checks remain in super.
        // Human players are untouched. Only live server AI camp actors qualify.
        if (!GetIdentity() && ai && ai.IsKindOf("Animal_CanisLupus")) { return HCWildlifeProviders.HCNativePermit(ai, this); }
        return true;
    }
}
