// #135 infected LOD preferences (Infected/lod.json) and the virtual herd
// journal ($profile:HollowCountry/infected-lod.json). Source implementation;
// runtime acceptance pending, every limit provisional until measured with
// 3-6 players.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:42 SaveFile, :69 LoadData; 3_Game/Global/Game.c:612
// ConfigIsExisting, :934 GetWorldName, :1437 IsKindOf(cfg, parent);
// 1_Core/proto/EnScript.c:380 Count, :407 Insert. Persistence reuses
// HCV2ThreatStore (World/HCEscalationClock.c: verified temp, backup, copy and
// readback; fail-closed intent, no native rename) and the shared
// HCSaveScheduler (World/HCWorkBudget.c). Caps: 16 herds, 64 head per herd,
// 16 member classes, 16384 journal bytes, 65536 config bytes. Only herd ids,
// centres and counts are stored: no player identities, entities or loot.
class HCInfectedLODHerdSeed
{
    string Id;
    float X;
    float Z;
    float Radius = 60;
    int HeadCount = 12;
}

class HCInfectedLODConfig
{
    int SchemaVersion = 3;
    // Classification and the tiered posed budget: a strict refinement of the
    // shipped behaviour at these defaults (same posed cap, same wake outcome).
    bool EnableLOD = true;
    // Owner default-on preference; explicit false remains the operator opt-out.
    // HCV2Admission logs W7-135 unverified; schema 3 supplies inland seeds.
    bool EnableVirtualHerds = true;
    // Provisional design bands, not measured hearing cutoffs. The repo's
    // LOCAL_ACCEPTANCE_V1.md:413 documents the 1000 m visibility/network
    // baseline; OUTSTANDING.md:78 calls for the same gunshot/network scale.
    // mission/hollow-country/ai/README.md:221-222 uses a 300 m near-threat
    // setting; transferring that to full infected AI is a design assumption.
    // Idle extends through the provisional 1000 m bubble.
    float FullRange = 300;
    float IdleRange = 1000;
    float MinSpawnDistance = 120;
    float MaterializeRange = 900;
    float FoldRange = 1000;
    // Materialize 100 m inside the bubble; fold beyond its edge. Check sight
    // 500 m farther as a provisional observer margin, never alter serverDZ.
    // Operators must extend these if measured network/hearing ranges demand it.
    float VisibilityRange = 1500;
    int ClassifyPerTick = 12;
    int MaxMaterialized = 12;
    int MaxPerHerd = 6;
    int MaxObservers = 6;
    float RegrowSeconds = 1800;
    int PosedBudget = 12;
    int PosedFullBudget = 12;
    int PosedIdleBudget = 12;
    // Seconds a non-calm native crawler is held before the next rest roll (variety).
    // Range HCInfectedVarietyPolicy.MIN/MAX_NONCALM_HOLD_SECONDS; default 600 = shipped.
    float VarietyNonCalmHoldSeconds = 600;
    // Seeds apply only on this world (lower case as GetWorldName reports it).
    string HerdWorld = "chernarusplus";
    ref array<string> MemberTypes = new array<string>;
    ref array<ref HCInfectedLODHerdSeed> Herds = new array<ref HCInfectedLODHerdSeed>;

    // #135 / w48: source-authored chernarusplus seed catalogue, not a native
    // terrain/path survey. Reuse inland rural barns and woodland stock anchors
    // already authored in Travel; never borrow the coastal/town pack corridors.
    // Radius/HeadCount remain the named, operator-editable seed DTO defaults.
    // Runtime placement and every observer veto remain authoritative.
    // Native scripts-1.30.164289: 1_Core/proto/EnScript.c:407 Insert,
    // :380 Count; 1_Core/proto/EnDebug.c:96 Print; EnConvert.c:30 int.ToString.
    static void HCSeed(HCInfectedLODConfig config, string id, float x, float z)
    {
        HCInfectedLODHerdSeed seed = new HCInfectedLODHerdSeed;
        seed.Id = id;
        seed.X = x;
        seed.Z = z;
        config.Herds.Insert(seed);
    }

    static void HCSeedDefaults(HCInfectedLODConfig config)
    {
        if (!config.Herds || config.Herds.Count() != 0 || config.HerdWorld != "chernarusplus") { return; }
        // mods/HollowCountry/scripts/4_World/Travel/HCShelterCatalog.c:107 inland farm approach above coast.
        HCSeed(config, "bor-farm", 3100.955811, 4238.387207);
        // mods/HollowCountry/scripts/4_World/Travel/HCShelterCatalog.c:109 northbound farm/woodland edge.
        HCSeed(config, "sosnovka-woods", 3560.896484, 7004.783203);
        // mods/HollowCountry/scripts/4_World/Travel/HCShelterCatalog.c:111 farmland between wooded ridges.
        HCSeed(config, "pulkovo-fields", 5271.449219, 5515.677246);
        // mods/HollowCountry/scripts/4_World/Travel/HCShelterCatalog.c:113 rural ridge west of Dolina.
        HCSeed(config, "dolina-ridge", 9710.349609, 6487.099121);
        // mods/HollowCountry/scripts/4_World/Travel/HCShelterCatalog.c:115 southern farm approach to Polana.
        HCSeed(config, "polana-farm", 10677.808594, 7923.848633);
        // mods/HollowCountry/scripts/4_World/Travel/HCShelterCatalog.c:72 northwest woodland stock anchor.
        HCSeed(config, "sinystok-woods", 1987.282837, 12965.870117);
        // mods/HollowCountry/scripts/4_World/Travel/HCShelterCatalog.c:73 northern woodland stock anchor.
        HCSeed(config, "kamensk-woods", 7428.081543, 12732.728516);
        // mods/HollowCountry/scripts/4_World/Travel/HCShelterCatalog.c:74 northeast woodland stock anchor.
        HCSeed(config, "northeast-woods", 12818.673828, 13117.182617);
    }

    // Stock civilian infected classes; used when MemberTypes is empty.
    static string DefaultMemberType(int index)
    {
        if (index == 1) { return "ZmbF_JournalistNormal_Blue"; }
        if (index == 2) { return "ZmbM_CitizenASkinny_Brown"; }
        if (index == 3) { return "ZmbF_CitizenANormal_Blue"; }
        if (index == 4) { return "ZmbM_ConstrWorkerNormal_Beige"; }
        return "ZmbM_HermitSkinny_Beige";
    }

    static int DefaultMemberTypes() { return 5; }

    bool IsValid()
    {
        if (SchemaVersion != 3 || !MemberTypes || !Herds) { return false; }
        if (!HCLODPolicy.ValidRanges(FullRange, IdleRange, MinSpawnDistance, MaterializeRange, FoldRange, VisibilityRange)) { return false; }
        if (IdleRange > VisibilityRange || MaterializeRange < FullRange || FoldRange < IdleRange) { return false; }
        if (!HCLODPolicy.ValidCaps(ClassifyPerTick, MaxMaterialized, MaxPerHerd, PosedBudget, PosedFullBudget, PosedIdleBudget, Herds.Count())) { return false; }
        if (MaxObservers < 1 || MaxObservers > 8 || RegrowSeconds < 0 || RegrowSeconds > 86400) { return false; }
        if (MemberTypes.Count() > 16 || HerdWorld.Length() > 64) { return false; }
        if (!HCInfectedVarietyPolicy.ValidNonCalmHold(VarietyNonCalmHoldSeconds)) { return false; }
        for (int typeIndex = 0; typeIndex < MemberTypes.Count(); typeIndex++)
        {
            string type = MemberTypes[typeIndex];
            if (type.Length() < 1 || type.Length() > 64) { return false; }
            if (!GetGame().ConfigIsExisting("CfgVehicles " + type) || !GetGame().IsKindOf(type, "ZombieBase")) { return false; }
        }
        for (int herdIndex = 0; herdIndex < Herds.Count(); herdIndex++)
        {
            HCInfectedLODHerdSeed seed = Herds[herdIndex];
            if (!seed || seed.Id.Length() < 1 || seed.Id.Length() > 48) { return false; }
            if (!HCLODPolicy.ValidHerd(seed.X, seed.Z, seed.Radius, seed.HeadCount, seed.HeadCount)) { return false; }
            for (int earlier = 0; earlier < herdIndex; earlier++)
            {
                if (Herds[earlier].Id == seed.Id) { return false; }
            }
        }
        return true;
    }

    int MemberTypeCount()
    {
        if (MemberTypes.Count() > 0) { return MemberTypes.Count(); }
        return DefaultMemberTypes();
    }

    string MemberType(int index)
    {
        if (MemberTypes.Count() > 0) { return MemberTypes[index % MemberTypes.Count()]; }
        return DefaultMemberType(index % DefaultMemberTypes());
    }

    // Stock defaults must exist before a template or empty list is trusted.
    bool DefaultsExist()
    {
        for (int index = 0; index < DefaultMemberTypes(); index++)
        {
            string type = DefaultMemberType(index);
            if (!GetGame().ConfigIsExisting("CfgVehicles " + type) || !GetGame().IsKindOf(type, "ZombieBase")) { return false; }
        }
        return true;
    }

    // Native LoadData zero-fills a missing key to 0/"" instead of keeping the
    // initializer. HerdWorld "" would silently disable every herd seed and a 0
    // hold is out of range, so a lod.json written before these keys existed would
    // disable the whole module. Restore the declared defaults of missing added keys
    // (taken from a fresh instance). Version 1 preferences are migrated once
    // through the verified temp/backup store; version 2 opt-outs are preserved.
    // One line per boot lists every restored key (#194); every other
    // missing or invalid key still fails IsValid exactly as before.
    static void HCRestoreMissingDefaults(HCInfectedLODConfig config, string content)
    {
        HCInfectedLODConfig declared = new HCInfectedLODConfig;
        string keys = "";
        string restored = "";
        if (!HCJsonFields.Has(content, "HerdWorld"))
        {
            config.HerdWorld = declared.HerdWorld;
            keys = "HerdWorld";
            restored = "HerdWorld=" + declared.HerdWorld;
        }
        if (!HCJsonFields.Has(content, "VarietyNonCalmHoldSeconds"))
        {
            config.VarietyNonCalmHoldSeconds = declared.VarietyNonCalmHoldSeconds;
            if (keys != "")
            {
                keys = keys + ",";
                restored = restored + " ";
            }
            keys = keys + "VarietyNonCalmHoldSeconds";
            restored = restored + "VarietyNonCalmHoldSeconds=" + declared.VarietyNonCalmHoldSeconds.ToString();
        }
        if (!HCJsonFields.Has(content, "EnableVirtualHerds"))
        {
            config.EnableVirtualHerds = declared.EnableVirtualHerds;
            if (keys != "")
            {
                keys = keys + ",";
                restored = restored + " ";
            }
            keys = keys + "EnableVirtualHerds";
            restored = restored + "EnableVirtualHerds=true";
        }
        if (keys == "") { return; }
        Print("[HC InfectedLOD] lod.json missing keys " + keys + "; declared defaults restored " + restored + " runtime=PENDING");
    }

    // Bounded read (64 KiB) then parse; a missing file gets the template.
    static HCInfectedLODConfig Load(out string reason)
    {
        HCInfectedLODConfig config = new HCInfectedLODConfig;
        string path = HCInfectedStore.DIRECTORY + "/lod.json";
        string content;
        string error;
        bool migrate = false;
        bool migratedPreference = false;
        reason = "";
        MakeDirectory(HCInfectedStore.ROOT);
        MakeDirectory(HCInfectedStore.DIRECTORY);
        if (!HCV2ThreatStore<HCInfectedLODConfig>.CanOpen(path))
        {
            reason = "lod.json recovery pending; preserving file";
            return null;
        }
        if (FileExist(path))
        {
            if (!HCInfectedStore.ReadBounded(path, content) || !JsonFileLoader<HCInfectedLODConfig>.LoadData(content, config, error))
            {
                reason = "unreadable lod.json; preserving file";
                return null;
            }
            // Only the named compatibility keys may be absent. Schema 1/2
            // additionally permits absent Herds: those older empty templates
            // had no operational herd set. Schema 3 still requires Herds.
            bool legacyHerds = config.SchemaVersion == 1 || config.SchemaVersion == 2;
            bool baselinePresent = true;
            if (!HCJsonFields.Has(content, "SchemaVersion") || !HCJsonFields.Has(content, "EnableLOD") || !HCJsonFields.Has(content, "FullRange") || !HCJsonFields.Has(content, "IdleRange") || !HCJsonFields.Has(content, "MinSpawnDistance") || !HCJsonFields.Has(content, "MaterializeRange") || !HCJsonFields.Has(content, "FoldRange")) { baselinePresent = false; }
            if (!HCJsonFields.Has(content, "VisibilityRange") || !HCJsonFields.Has(content, "ClassifyPerTick") || !HCJsonFields.Has(content, "MaxMaterialized") || !HCJsonFields.Has(content, "MaxPerHerd") || !HCJsonFields.Has(content, "MaxObservers") || !HCJsonFields.Has(content, "RegrowSeconds")) { baselinePresent = false; }
            if (!HCJsonFields.Has(content, "PosedBudget") || !HCJsonFields.Has(content, "PosedFullBudget") || !HCJsonFields.Has(content, "PosedIdleBudget") || !HCJsonFields.Has(content, "MemberTypes")) { baselinePresent = false; }
            if (!legacyHerds && !HCJsonFields.Has(content, "Herds")) { baselinePresent = false; }
            if (!baselinePresent)
            {
                reason = "settings_missing_baseline_fields; preserving lod.json";
                return null;
            }
            HCRestoreMissingDefaults(config, content);
            if (config && config.SchemaVersion == 1)
            {
                config.SchemaVersion = 2;
                config.EnableVirtualHerds = true;
                migratedPreference = true;
            }
            if (config && config.SchemaVersion == 2)
            {
                // Do not convert explicit null/invalid arrays into defaults.
                if (!HCJsonFields.Has(content, "Herds")) { config.Herds = new array<ref HCInfectedLODHerdSeed>(); }
                HCInfectedLODConfig.HCSeedDefaults(config);
                config.SchemaVersion = 3;
                migrate = true;
            }
        }
        else
        {
            HCInfectedLODConfig.HCSeedDefaults(config);
            if (!JsonFileLoader<HCInfectedLODConfig>.SaveFile(path, config, error))
            {
                reason = "cannot create lod.json template";
                return null;
            }
        }
        if (!config || !config.IsValid())
        {
            reason = "invalid lod.json ranges/caps/classes/herds; preserving file";
            return null;
        }
        if (migrate)
        {
            if (!HCV2ThreatStore<HCInfectedLODConfig>.Save(path, config, 65536))
            {
                reason = "cannot migrate lod.json; preserving recovery files";
                return null;
            }
            if (migratedPreference)
            {
                Print("[HC InfectedLOD] settings migrated v1->v2 EnableVirtualHerds=true (owner default-on; set false to opt out)");
            }
            int migratedHerdCount;
            migratedHerdCount = config.Herds.Count();
            Print("[HC InfectedLOD] settings migrated v2->v3 herds=" + migratedHerdCount.ToString() + " runtime=PENDING");
        }
        return config;
    }
}

class HCInfectedLODHerd
{
    string Id;
    float X;
    float Z;
    float Radius;
    int HeadCount;
    int Alive;
    int UpdatedUtc;
}

class HCInfectedLODState
{
    int Version;
    string WorldName;
    int SavedUtc;
    ref array<ref HCInfectedLODHerd> Herds = new array<ref HCInfectedLODHerd>;
}

class HCInfectedLODSaveJob : HCSaveJob
{
    HCInfectedLODStore Owner;
    override bool HCWrite() { return Owner && Owner.HCFlushRoutine(); }
    override string HCName() { return "InfectedLOD"; }
}

class HCInfectedLODStore
{
    static const string PATH = "$profile:HollowCountry/infected-lod.json";
    static const int LIMIT = 16384;
    protected ref HCInfectedLODState m_State;
    protected ref HCInfectedLODSaveJob m_Job;
    protected bool m_Healthy;
    protected int m_LastUtc;

    bool Healthy() { return m_Healthy; }
    HCInfectedLODState State() { return m_State; }

    protected bool Valid(int nowUtc)
    {
        if (!m_State || m_State.Version != 1 || m_State.WorldName != GetGame().GetWorldName()) { return false; }
        if (!m_State.Herds || m_State.Herds.Count() > HCLODPolicy.MAX_HERDS) { return false; }
        if (m_State.SavedUtc < 1 || m_State.SavedUtc > nowUtc) { return false; }
        for (int index = 0; index < m_State.Herds.Count(); index++)
        {
            HCInfectedLODHerd herd = m_State.Herds[index];
            if (!herd || herd.Id.Length() < 1 || herd.Id.Length() > 48) { return false; }
            if (!HCLODPolicy.ValidHerd(herd.X, herd.Z, herd.Radius, herd.HeadCount, herd.Alive)) { return false; }
            if (herd.UpdatedUtc < 1 || herd.UpdatedUtc > m_State.SavedUtc) { return false; }
            for (int earlier = 0; earlier < index; earlier++)
            {
                if (m_State.Herds[earlier].Id == herd.Id) { return false; }
            }
        }
        return true;
    }

    protected void Fail(string reason)
    {
        m_Healthy = false;
        Print("[HC InfectedLOD] virtual herds disabled: " + reason + "; preserve infected-lod.json, .tmp and .bak");
    }

    // Load (or create) the journal, then reconcile it with the configured
    // seeds by id: new seeds start at full head count, removed seeds drop,
    // changed seeds keep their living count clamped to the new head count.
    bool Start(HCInfectedLODConfig config)
    {
        int nowUtc = HCGroupClock.Utc();
        if (nowUtc < 1 || !HCV2ThreatStore<HCInfectedLODState>.CanOpen(PATH)) { Fail("UTC clock or pending .tmp/.bak"); return false; }
        if (FileExist(PATH))
        {
            if (!HCV2ThreatStore<HCInfectedLODState>.Load(PATH, LIMIT, m_State) || !Valid(nowUtc)) { Fail("schema/world/cap mismatch"); return false; }
        }
        else
        {
            m_State = new HCInfectedLODState;
            m_State.Version = 1;
            m_State.WorldName = GetGame().GetWorldName();
            m_State.SavedUtc = nowUtc;
        }
        m_LastUtc = nowUtc;
        string world = GetGame().GetWorldName();
        world.ToLower();
        string seedWorld = config.HerdWorld;
        seedWorld.ToLower();
        bool seedsApply = seedWorld == world;
        bool changed = !FileExist(PATH);
        ref array<ref HCInfectedLODHerd> next = new array<ref HCInfectedLODHerd>;
        for (int seedIndex = 0; seedIndex < config.Herds.Count(); seedIndex++)
        {
            if (!seedsApply) { break; }
            HCInfectedLODHerdSeed seed = config.Herds[seedIndex];
            HCInfectedLODHerd herd = Find(seed.Id);
            if (!herd)
            {
                herd = new HCInfectedLODHerd;
                herd.Id = seed.Id;
                herd.Alive = seed.HeadCount;
                herd.UpdatedUtc = nowUtc;
                changed = true;
            }
            if (herd.X != seed.X || herd.Z != seed.Z || herd.Radius != seed.Radius || herd.HeadCount != seed.HeadCount) { changed = true; }
            herd.X = seed.X;
            herd.Z = seed.Z;
            herd.Radius = seed.Radius;
            herd.HeadCount = seed.HeadCount;
            herd.Alive = Math.Min(herd.Alive, herd.HeadCount);
            next.Insert(herd);
        }
        if (next.Count() != m_State.Herds.Count()) { changed = true; }
        m_State.Herds = next;
        m_Healthy = true;
        m_Job = new HCInfectedLODSaveJob;
        m_Job.Owner = this;
        m_Job.HCDirty = changed;
        HCSaveScheduler.HCRegister(m_Job);
        return true;
    }

    HCInfectedLODHerd Find(string id)
    {
        if (!m_State) { return null; }
        foreach (HCInfectedLODHerd herd : m_State.Herds)
        {
            if (herd.Id == id) { return herd; }
        }
        return null;
    }

    void MarkDirty()
    {
        if (m_Job) { m_Job.HCDirty = true; }
    }

    int NowUtc()
    {
        int nowUtc = HCGroupClock.Utc();
        if (nowUtc < m_LastUtc) { return -1; }
        m_LastUtc = nowUtc;
        return nowUtc;
    }

    bool HCFlushRoutine()
    {
        if (!m_Healthy || !m_State) { return false; }
        int nowUtc = NowUtc();
        if (nowUtc < 1) { Fail("UTC clock went backwards"); return false; }
        m_State.SavedUtc = nowUtc;
        if (!HCV2ThreatStore<HCInfectedLODState>.Save(PATH, m_State, LIMIT)) { Fail("journal write"); return false; }
        return true;
    }

    // Owner flushes before releasing state, independent of registry order.
    void Stop()
    {
        if (m_Job)
        {
            if (m_Healthy) { HCSaveScheduler.HCFlush(m_Job); }
            HCSaveScheduler.HCUnregister(m_Job);
        }
        m_Job = null;
        m_Healthy = false;
    }
}
