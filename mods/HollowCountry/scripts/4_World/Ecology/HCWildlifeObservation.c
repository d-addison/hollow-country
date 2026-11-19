// HC-15 / #149: native wildlife baseline, not a movement/feeding controller.
// Spec -> plan -> task: HC-15 in the consolidated coverage brief; trace owner
// HC-11 must retain N9 herd/flee/regroup/predator/pair experiments as PENDING.
// Installed source root: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// Native evidence for every engine read below:
// 3_Game/Global/Game.c:1120 IsServer, :1535 GetTime (via the existing authority/owner ports);
// 3_Game/Entities/Object.c:215 IsPendingDeletion, :287 GetPosition,
// :467 GetType, :511 IsKindOf, :517 IsAlive;
// 3_Game/Entities/DayZAnimal.c:60 CanBeSkinned, :193 GetAIAgent, :664 GetInputController;
// 3_Game/Entities/EntityAI.c:483 IsSkinned;
// 3_Game/AI/AIAgent.c:7 GetGroup (identity only, not a herd destination);
// 3_Game/Entities/DayZCreatureAIInputController.c:27 GetBehaviourSlot;
// 3_Game/Entities/DayZAnimalInputController.c:55 GetBehaviourAction;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 3_Game/CfgGameplayHandler.c:3 $mission:;
// 1_Core/proto/EnScript.c:380/385/399/407/470 array Count/Clear/Get/Insert/RemoveOrdered;
// EnDebug.c:96 Print; EnConvert.c:30 int.ToString.
// Existing HCEcologyRuntimeIO.Read bounds file IO (EnSystem.c:417/425/443).
// No animal target accessor/destination/feeding transaction was found in N9.
// Behaviour slots are raw engine readings, never proof of prey sight, fleeing,
// regroup success, feeding, ownership of a territory, or hostile pair support.

class HCWildlifeTargetPair
{
    string Source;
    string Target;
    string Verdict;
}

class HCWildlifeConfig
{
    int Version;
    bool Enabled;
    int MaxAnimals;
    int MaxFacts;
    int SamplePerTick;
    int WorkUnits;
    int MaxPlayerChecks;
    int TickMs;
    int FactLifetimeMs;
    float PlayerObservationRadiusM;
    string RangeBasis;
    ref array<string> Species;
    ref array<ref HCWildlifeTargetPair> TargetPairs;
}

// Finite server-only port for HC-48/49. A snapshot is a COPY; handles are weak,
// session-local, never persisted or sent to clients. Consumers must revalidate
// the live subject and native action/inventory conditions before acting.
// Target remains null/unknown: nearby animals and HUNTING are not target facts.
// Carcass means observed dead + CanBeSkinned, not a right to loot or an amount
// of available meat. Frozen/skinned/deleted bodies are rechecked on snapshot.
class HCWildlifeFact
{
    string Id;
    EntityAI Subject;
    string Species;
    vector Position;
    int ObservedAtMs;
    int BehaviourSlot = -1;
    int BehaviourAction = -1;
    AIGroup NativeGroup;
    bool Carcass;
    bool TargetKnown = false;
    EntityAI Target;
}

class HCWildlifeBinding
{
    EntityAI Live;
    int Serial;
    ref HCWildlifeFact Fact;
}

class HCWildlifeDebugContributor : HCDebugContributor
{
    HCWildlifeObservation Owner;

    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        if (Owner) { Owner.HCDescribe(snapshot); }
    }
}

// Lead binds this service inside the existing Ecology lifecycle and EE hooks.
// No module/registry/config.cpp edits, population search, timer, save or RPC.
class HCWildlifeObservation
{
    protected static ref HCWildlifeObservation s_Instance;
    protected ref array<ref HCWildlifeBinding> m_Bindings = new array<ref HCWildlifeBinding>;
    protected ref HCWildlifeConfig m_Config;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCWildlifeDebugContributor m_Debug;
    protected bool m_Collecting = true;
    protected bool m_Running;
    protected bool m_OverflowReported;
    protected int m_NextSerial = 1;
    protected int m_Cursor;
    protected int m_LastTick = -1;
    protected int m_LastNow = -1;

    static HCWildlifeObservation HCInstance()
    {
        if (!HCEcologyNative.Authority()) { return null; }
        if (!s_Instance) { s_Instance = new HCWildlifeObservation; }
        return s_Instance;
    }

    // Reuse ecology's registered EEInit cohort. Duplicate callback origins
    // (herd labels / territory labels / repeated EEInit) cannot own two rows.
    static bool HCRegister(EntityAI entity)
    {
        HCWildlifeObservation owner = HCInstance();
        if (!owner) { return false; }
        return owner.HCAdd(entity);
    }

    static void HCUnregister(EntityAI entity)
    {
        if (s_Instance) { s_Instance.HCRemove(entity); }
    }

    static void HCStart(bool ecologyEnabled)
    {
        HCWildlifeObservation owner = HCInstance();
        if (!owner) { return; }
        HCWildlifeConfig config;
        if (ecologyEnabled)
        {
            string text = HCEcologyRuntimeIO.Read("$mission:hollow-country/ecology/species.json", 16384);
            string error;
            if (text != "" && !JsonFileLoader<HCWildlifeConfig>.LoadData(text, config, error)) { config = null; }
        }
        owner.HCBegin(ecologyEnabled, config);
    }

    static void HCTick(int nowMs)
    {
        if (s_Instance) { s_Instance.HCSample(nowMs); }
    }

    static void HCStop()
    {
        if (s_Instance) { s_Instance.HCEnd(); }
    }

    static HCOperationalStatus HCStatus()
    {
        if (!s_Instance) { return null; }
        return s_Instance.m_Status;
    }

    static bool HCDestinationSupported() { return false; }
    static bool HCFeedingSupported() { return false; }
    static bool HCTargetObservationSupported() { return false; }

    static bool HCConfigValid(HCWildlifeConfig config)
    {
        if (!config || config.Version != 1 || !config.Species || !config.TargetPairs) { return false; }
        if (config.MaxAnimals < 1 || config.MaxAnimals > HCEcologyRuntimeRules.REGISTRY_ACTORS) { return false; }
        if (config.MaxFacts < 1 || config.MaxFacts > 64 || config.MaxFacts > config.MaxAnimals) { return false; }
        if (config.SamplePerTick < 1 || config.SamplePerTick > 32 || config.WorkUnits < 1 || config.WorkUnits > 1024) { return false; }
        if (config.MaxPlayerChecks < 1 || config.MaxPlayerChecks > 64) { return false; }
        if (config.TickMs < 1 || config.TickMs > 60000 || config.FactLifetimeMs < 1 || config.FactLifetimeMs > 60000) { return false; }
        if (!(config.PlayerObservationRadiusM > 0) || !(config.PlayerObservationRadiusM <= FLT_MAX)) { return false; }
        if (config.Species.Count() < 1 || config.Species.Count() > 32 || config.TargetPairs.Count() > 16) { return false; }
        array<string> speciesSeen = new array<string>;
        foreach (string species : config.Species)
        {
            if (!HCEcologyRules.TextValid(species) || speciesSeen.Find(species) >= 0) { return false; }
            speciesSeen.Insert(species);
        }
        array<string> pairsSeen = new array<string>;
        foreach (HCWildlifeTargetPair pair : config.TargetPairs)
        {
            if (!pair || pair.Verdict != "pending_native_pair_matrix") { return false; }
            if (pair.Source != "animal" && pair.Source != "ai" && pair.Source != "infected") { return false; }
            if (pair.Target != "animal" && pair.Target != "ai" && pair.Target != "infected") { return false; }
            if (pair.Source != "animal" && pair.Target != "animal") { return false; }
            string key = pair.Source + ":" + pair.Target;
            if (pairsSeen.Find(key) >= 0) { return false; }
            pairsSeen.Insert(key);
        }
        return true;
    }

    bool HCBegin(bool ecologyEnabled, HCWildlifeConfig config)
    {
        // Preserve pre-start bindings only on first admission. Stop releases
        // them and closes callbacks; it never silently recollects while off.
        m_Running = false;
        if (m_Debug) { HCDebugSnapshot.HCUnregister(m_Debug); m_Debug = null; }
        if (!HCEcologyNative.Authority()) { HCEnd(); return false; }
        if (!ecologyEnabled || (config && !config.Enabled))
        {
            HCEnd();
            Print("[HC Plan] HC-15 wildlife provider=native destination=unsupported targets=0 state=off runtime=PENDING");
            return false;
        }
        if (!HCConfigValid(config)) { HCRefuse("invalid_species_config"); return false; }
        Print(HCV2Admission.Line("WildlifeBaseline", config.Enabled, "native_wildlife_baseline", false));
        if (!HCV2Admission.Admitted(config.Enabled)) { HCEnd(); return false; }
        if (m_Bindings.Count() > config.MaxAnimals) { HCRefuse("prestart_cohort_over_cap"); return false; }
        m_Config = config;
        m_Collecting = true;
        m_Running = true;
        m_Cursor = 0;
        m_LastTick = -1;
        m_LastNow = -1;
        m_Debug = new HCWildlifeDebugContributor;
        m_Debug.Owner = this;
        HCDebugSnapshot.HCRegister(m_Debug);
        m_Status.HCPublish("ready", "native_observation_only");
        int targets = config.TargetPairs.Count();
        Print("[HC Plan] HC-15 wildlife provider=native destination=unsupported targets=" + targets.ToString() + " state=ready authored_pairs=" + targets.ToString() + " observed_targets=0 runtime=PENDING");
        Print("[HC Plan] HC-15 state=refused capability=destination reason=no_inspected_animal_destination_api runtime=PENDING");
        Print("[HC Plan] HC-15 state=refused capability=feeding reason=no_inspected_feeding_transaction runtime=PENDING");
        Print("[HC Plan] HC-15 state=refused capability=animal_target reason=no_inspected_animal_target_accessor pair_matrix=PENDING runtime=PENDING");
        return true;
    }

    bool HCAdd(EntityAI entity)
    {
        if (!m_Collecting || !HCEcologyNative.Authority() || !entity || entity.IsPendingDeletion() || !AnimalBase.Cast(entity)) { return false; }
        // Canonical identity is the actual native handle, never a herd name,
        // CE/territory label, nearby position or caller-provided entity ID.
        foreach (HCWildlifeBinding existing : m_Bindings)
        {
            if (existing.Live == entity) { return true; }
        }
        int limit = HCEcologyRuntimeRules.REGISTRY_ACTORS;
        if (m_Config) { limit = m_Config.MaxAnimals; }
        if (m_Bindings.Count() >= limit || m_NextSerial >= 2147483647)
        {
            if (!m_OverflowReported)
            {
                m_OverflowReported = true;
                Print("[HC Plan] HC-15 state=refused reason=cohort_capacity coverage=partial runtime=PENDING");
            }
            return false;
        }
        HCWildlifeBinding binding = new HCWildlifeBinding;
        binding.Live = entity;
        binding.Serial = m_NextSerial;
        m_NextSerial = m_NextSerial + 1;
        m_Bindings.Insert(binding);
        return true;
    }

    void HCRemove(EntityAI entity)
    {
        int index = m_Bindings.Count() - 1;
        while (index >= 0)
        {
            if (!m_Bindings.Get(index).Live || m_Bindings.Get(index).Live == entity) { m_Bindings.RemoveOrdered(index); }
            index = index - 1;
        }
        // The retained cursor is normalized before the next sample.
    }

    bool HCNear(vector position, array<Man> players)
    {
        if (!HCEcologyRuntimeRules.PositionValid(position) || !players) { return false; }
        int index = 0;
        while (index < players.Count() && index < m_Config.MaxPlayerChecks)
        {
            Man player = players.Get(index);
            if (player && player.IsAlive())
            {
                float gap = vector.DistanceSq(position, player.GetPosition());
                if (gap <= m_Config.PlayerObservationRadiusM * m_Config.PlayerObservationRadiusM) { return true; }
            }
            index = index + 1;
        }
        return false;
    }

    HCWildlifeFact HCRead(HCWildlifeBinding binding, int nowMs, array<Man> players)
    {
        if (!binding || !binding.Live || binding.Live.IsPendingDeletion()) { return null; }
        AnimalBase animal = AnimalBase.Cast(binding.Live);
        if (!animal || !HCNear(animal.GetPosition(), players)) { return null; }
        bool permittedSpecies = false;
        foreach (string species : m_Config.Species)
        {
            if (animal.IsKindOf(species)) { permittedSpecies = true; break; }
        }
        if (!permittedSpecies) { return null; }
        HCWildlifeFact fact = new HCWildlifeFact;
        fact.Subject = animal;
        fact.Id = "wildlife:" + binding.Serial.ToString();
        fact.Species = animal.GetType();
        fact.Position = animal.GetPosition();
        fact.ObservedAtMs = nowMs;
        fact.Carcass = !animal.IsAlive() && animal.CanBeSkinned() && !animal.IsSkinned();
        if (!animal.IsAlive() && !fact.Carcass) { return null; }
        if (animal.IsAlive())
        {
            DayZAnimalInputController input = animal.GetInputController();
            AIAgent agent = animal.GetAIAgent();
            if (input)
            {
                fact.BehaviourSlot = input.GetBehaviourSlot();
                fact.BehaviourAction = input.GetBehaviourAction();
            }
            if (agent) { fact.NativeGroup = agent.GetGroup(); }
        }
        return fact;
    }

    void HCSample(int nowMs)
    {
        if (!m_Running) { return; }
        if (!HCEcologyNative.Authority() || nowMs < 0 || nowMs < m_LastNow) { HCRefuse("authority_or_clock"); return; }
        m_LastNow = nowMs;
        if (m_LastTick >= 0 && nowMs - m_LastTick < m_Config.TickMs) { return; }
        m_LastTick = nowMs;
        int total = m_Bindings.Count();
        if (total == 0) { return; }
        array<Man> players = HCPerfPlayers.HCGet();
        m_Units.HCReset(m_Config.WorkUnits);
        m_Work.HCReset(m_Config.SamplePerTick);
        int examined = 0;
        while (examined < total && examined < m_Config.SamplePerTick)
        {
            if (!m_Units.HCTake(1 + m_Config.MaxPlayerChecks) || !m_Work.HCContinue()) { break; }
            if (m_Cursor >= m_Bindings.Count()) { m_Cursor = 0; }
            HCWildlifeBinding binding = m_Bindings.Get(m_Cursor);
            binding.Fact = HCRead(binding, nowMs, players);
            m_Cursor = m_Cursor + 1;
            examined = examined + 1;
        }
    }

    // Caller supplies the current native mission time, never a client assertion.
    // HC-48/49 receive only observed facts, <=MaxFacts (hard ceiling 64).
    array<ref HCWildlifeFact> HCFacts(int nowMs)
    {
        array<ref HCWildlifeFact> facts = new array<ref HCWildlifeFact>;
        if (!m_Running || !HCEcologyNative.Authority() || nowMs < m_LastNow) { return facts; }
        foreach (HCWildlifeBinding binding : m_Bindings)
        {
            if (facts.Count() >= m_Config.MaxFacts) { break; }
            HCWildlifeFact fact = binding.Fact;
            if (!fact || !fact.Subject || fact.Subject.IsPendingDeletion()) { continue; }
            if (!HCEcologyRuntimeRules.Fresh(fact.ObservedAtMs, nowMs, m_Config.FactLifetimeMs)) { continue; }
            if (fact.Carcass && (fact.Subject.IsAlive() || !fact.Subject.CanBeSkinned() || fact.Subject.IsSkinned())) { continue; }
            if (!fact.Carcass && !fact.Subject.IsAlive()) { continue; }
            HCWildlifeFact copy = new HCWildlifeFact;
            copy.Id = fact.Id;
            copy.Subject = fact.Subject;
            copy.Species = fact.Species;
            copy.Position = fact.Position;
            copy.ObservedAtMs = fact.ObservedAtMs;
            copy.BehaviourSlot = fact.BehaviourSlot;
            copy.BehaviourAction = fact.BehaviourAction;
            copy.NativeGroup = fact.NativeGroup;
            copy.Carcass = fact.Carcass;
            facts.Insert(copy);
        }
        return facts;
    }

    static array<ref HCWildlifeFact> HCSnapshot(int nowMs)
    {
        if (!s_Instance) { return new array<ref HCWildlifeFact>; }
        return s_Instance.HCFacts(nowMs);
    }

    void HCDescribe(HCDebugSnapshot snapshot)
    {
        array<ref HCWildlifeFact> facts = HCFacts(GetGame().GetTime());
        foreach (HCWildlifeFact fact : facts)
        {
            string detail = "native behaviour sample; targets unknown; runtime=PENDING";
            if (fact.Carcass) { detail = "native dead/skinnable sample; inventory unclaimed; runtime=PENDING"; }
            snapshot.AddPoint("wildlife", fact.Id, fact.Position, fact.Species, detail);
        }
    }

    void HCEnd()
    {
        m_Running = false;
        m_Collecting = false;
        if (m_Debug) { HCDebugSnapshot.HCUnregister(m_Debug); m_Debug.Owner = null; m_Debug = null; }
        m_Bindings.Clear();
        m_Config = null;
        m_Cursor = 0;
        m_Status.HCPublish("off", "ecology_off_or_stopped");
        // Serial never resets inside a mission, preventing stale ID reuse.
    }

    void HCRefuse(string reason)
    {
        HCEnd();
        m_Status.HCPublish("refused", reason);
        Print("[HC Plan] HC-15 wildlife provider=native destination=unsupported targets=0 state=refused reason=" + reason + " runtime=PENDING");
    }
}
