// #121 W56: source admission only, runtime=PENDING. Native snapshot
// scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 3_Game/Global/Game.c:1120
// IsServer, :1176 SurfaceY; 3_Game/Entities/Object.c:287 GetPosition, :517
// IsAlive; 1_Core/proto/EnConvert.c:210 DistanceSq; EnScript.c:380 Count,
// :385 Clear, :394 Find, :407 Insert, :470 RemoveOrdered; EnDebug.c:96 Print. Creation/registration remains
// in HCLODMaterialize (native 3_Game/Global/Game.c:703 CreateObjectEx;
// 3_Game/CE/CentralEconomy.c:18,38 ECE_INITAI/ECE_PLACE_ON_SURFACE), geometry in HCObserverTransitionGate/HCInfectedLOD.
// HCWorldMaterializer owns faction/cargo proposals; infected are CE bodies,
// so do not counterfeit faction ledger rows or acquire an AI cargo lease.
// Retain weak body handles including corpses; no refill or deletion on stop.
class HCInfectedVarietySite
{
    string Id;
    string Context;
    string SourceClass;
    vector Position;
}

class HCInfectedVarietyConfig
{
    int SchemaVersion = 1;
    string Runtime;
    int MaxSites = 64;
    int MaxFreshBodies = 3;
    int GroupMembers = 3;
    // Every second fresh body is standing; 0 opts out of this variant.
    int StandingRiserEvery = 2;
    // Audit #121: every Nth fresh body is a custom-graph posed body (0 opts out).
    // Optional in the JSON: HCApplyOptionalDefaults restores the ON default.
    int PosedFreshEvery = 3;
    // Server-wide custom-graph pose slots, including bodies still rising. 0 opts out.
    int MaxPosed = 12;
    bool EnableMigration = true;
    float CorridorRangeMetres = 80;
    float MaxMigrationMetres = 480;
    float MigrationLifetimeSeconds = 60;
    float MigrationScanSeconds = 5;
    float ContextRange = 40;
    float InterestRange = 1000;
    float RequestRange = 1500;
    float MinSpawnDistance = 120;
    float VisibilityRange = 1100;
    int MaxObservers = 8;
    float GroupSpacing = 4;
    float AutomaticIntervalSeconds = 600;
    ref array<ref HCInfectedVarietySite> Sites = new array<ref HCInfectedVarietySite>;

    ref HCC1GroupScaling GroupScaling = new HCC1GroupScaling;
    ref HCC1Variety Variety = new HCC1Variety;
    protected static bool s_HCTuningInvalidLogged;

    void HCNormalizeTunables()
    {
        HCC1Range.s_Invalid = false;
        if (!GroupScaling) { GroupScaling = new HCC1GroupScaling; }
        if (!Variety) { Variety = new HCC1Variety; }
        GroupScaling.Normalize();
        Variety.Normalize();
        if (HCC1Range.s_Invalid && !s_HCTuningInvalidLogged)
        {
            s_HCTuningInvalidLogged = true;
            Print("[HC Variety] tunables=invalid_fields_defaulted first=" + HCC1Range.s_Detail + " runtime=PENDING");
        }
        HCInfectedTuning.SetVariety(this);
    }

    // The authored JSON predates PosedFreshEvery, and JsonFileLoader zero-fills a
    // missing key to 0 (= off). A missing key keeps the owner-default ON cadence;
    // the acceptance disable marker forces the named opt-out.
    // Absent tuning blocks may arrive zero-filled from the native loader; they
    // mean "use the defaults", not invalid operator values.
    void HCApplyTuningDefaults(string content)
    {
        if (!HCJsonFields.Has(content, "GroupScaling")) { GroupScaling = new HCC1GroupScaling; }
        if (!HCJsonFields.Has(content, "Variety")) { Variety = new HCC1Variety; }
    }

    void HCApplyOptionalDefaults(string content, bool posesOptedOut)
    {
        if (!HCJsonFields.Has(content, "PosedFreshEvery")) { PosedFreshEvery = HCInfectedVarietyPolicy.DEFAULT_POSED_FRESH_EVERY; }
        if (!HCJsonFields.Has(content, "MaxPosed")) { MaxPosed = 12; }
        if (posesOptedOut) { PosedFreshEvery = 0; }
        HCApplyTuningDefaults(content);
    }

    bool HCMaxPosedValid()
    {
        return MaxPosed >= 0 && MaxPosed <= 64;
    }

    bool HCPosedCadenceValid()
    {
        return PosedFreshEvery >= 0 && PosedFreshEvery <= MaxFreshBodies;
    }

    bool HCValid()
    {
        HCNormalizeTunables();
        if (!HCMaxPosedValid()) { return false; }
        if (SchemaVersion != 1 || !Sites || Sites.Count() < 1 || Sites.Count() > MaxSites) { return false; }
        if (MaxSites < 1 || MaxSites > 64 || GroupMembers < 1 || GroupMembers > MaxFreshBodies || MaxFreshBodies > 3) { return false; }
        if (!(CorridorRangeMetres > 0 && CorridorRangeMetres <= 80 && MaxMigrationMetres >= CorridorRangeMetres && MaxMigrationMetres <= 480)) { return false; }
        if (!(MigrationScanSeconds >= 1 && MigrationScanSeconds <= 60)) { return false; }
        if (!(MigrationLifetimeSeconds > 0 && MigrationLifetimeSeconds <= 60)) { return false; }
        if (StandingRiserEvery < 0 || StandingRiserEvery > MaxFreshBodies || !HCPosedCadenceValid()) { return false; }
        if (!(ContextRange >= 1 && ContextRange <= 100 && InterestRange >= 120 && InterestRange <= 1500)) { return false; }
        if (!(MinSpawnDistance >= 120 && VisibilityRange >= 1100 && VisibilityRange <= 1500)) { return false; }
        if (!(RequestRange >= InterestRange && RequestRange <= 3000 && MaxObservers >= 1 && MaxObservers <= 8)) { return false; }
        if (!(GroupSpacing >= 3 && GroupSpacing <= 8 && AutomaticIntervalSeconds >= 60 && AutomaticIntervalSeconds <= 3600)) { return false; }
        array<ref HCInfectedVarietySite> sites = Sites;
        foreach (HCInfectedVarietySite site : sites)
        {
            if (!site || site.Id == "" || site.SourceClass == "" || !HCInfectedStore.ValidPosition(site.Position)) { return false; }
            if (site.Context != "wreck" && site.Context != "church" && site.Context != "gas_station" && site.Context != "roadside" && site.Context != "building") { return false; }
        }
        return true;
    }
}

class HCInfectedVariety
{
    protected static ref HCInfectedVarietyConfig s_Config;
    protected static ref array<ZombieBase> s_Bodies = new array<ZombieBase>;
    protected static ref map<int, bool> s_Used = new map<int, bool>;
    protected static ref map<int, bool> s_Tried = new map<int, bool>;
    protected static bool s_Running;
    protected static bool s_Pending;
    protected static bool s_Admin;
    protected static vector s_Request;
    protected static int s_Selected = -1;
    protected static int s_Made;
    protected static int s_PlayerCursor;
    protected static float s_NextAutomatic;
    protected static string s_Fault;
    protected static string s_LastRefusal;

    static void HCStart(bool preference)
    {
        s_Running = false;
        s_Pending = false;
        s_Config = null;
        s_Fault = "";
        bool enabled = HCOperatorEnabled(preference);
        Print(HCV2Admission.Line("InfectedVarietyPlaces", enabled, "W60-native-fresh-variants", false) + " runtime=PENDING");
        if (!enabled)
        {
            s_Fault = "operator_preference";
            if (preference) { s_Fault = "infected_variety_disabled"; }
            Print("[HC Variety] state=off reason=" + s_Fault + " runtime=PENDING");
            return;
        }
        if (!HCLoadConfig()) { return; }
        s_Running = true;
        Print("[HC Variety] fresh_crawlers=admitted_unverified standing_risers=native_standing_idle places=authored_CE opt_out=acceptance/infected_variety.disable runtime=PENDING");
        int posedEvery;
        if (s_Config) { posedEvery = s_Config.PosedFreshEvery; }
        string posedLine = "[HC Variety] posed_fresh_every=" + posedEvery.ToString() + " class=" + HCInfectedVarietyPolicy.HCPoseClass();
        Print(posedLine + " opt_out=PosedFreshEvery=0|acceptance/infected_poses.disable runtime=PENDING");
        string authored = "[HC Variety] anim_poses=source_authored prone_sleep=" + HCPostureAdmission.HCTierCState("prone_sleep");
        authored = authored + " riser=" + HCPostureAdmission.HCTierCState("riser") + " feed_kneel=" + HCPostureAdmission.HCTierCState("feed_kneel");
        Print(authored + " acceptance=native_two_client_pending runtime=PENDING");
        if (posedEvery > 0 && s_Config.MaxPosed > 0)
        {
            if (!HCPostureAdmission.HCCanEnter("prone_sleep") || !HCPostureAdmission.HCCanEnter("riser") || !HCPostureAdmission.HCCanEnter("feed_kneel"))
            {
                s_Fault = "anim_poses_shared_admission_pending";
                HCRefuse(s_Fault);
            }
        }
    }

    static bool HCPosesOptedOut()
    {
        return FileExist("$profile:HollowCountry/acceptance/infected_poses.disable");
    }

    static bool HCOperatorEnabled(bool preference)
    {
        return preference && !FileExist("$profile:HollowCountry/acceptance/infected_variety.disable");
    }

    static bool HCLoadConfig()
    {
        string content = HCWorldStore.Read("$mission:hollow-country/infected/variety-runtime.json");
        string error;
        // Every operational scalar is required: native JSON zero-fill must not
        // silently turn missing ranges/caps into an unbounded permissive gate.
        array<string> keys = {"SchemaVersion", "MaxSites", "MaxFreshBodies", "GroupMembers", "StandingRiserEvery", "EnableMigration", "CorridorRangeMetres", "MaxMigrationMetres", "MigrationLifetimeSeconds", "MigrationScanSeconds", "ContextRange", "InterestRange", "RequestRange", "MinSpawnDistance", "VisibilityRange", "MaxObservers", "GroupSpacing", "AutomaticIntervalSeconds", "Sites"};
        foreach (string key : keys)
        {
            if (!HCJsonFields.Has(content, key)) { s_Fault = "variety_data_missing_field:" + key; HCRefuse(s_Fault); return false; }
        }
        HCInfectedVarietyConfig config;
        bool loaded = JsonFileLoader<HCInfectedVarietyConfig>.LoadData(content, config, error);
        if (loaded && config) { config.HCApplyOptionalDefaults(content, HCPosesOptedOut()); }
        if (loaded && config && !config.HCMaxPosedValid())
        {
            s_Fault = "variety_max_posed_out_of_range";
            HCRefuse(s_Fault);
            return false;
        }
        if (!loaded || !config || !config.HCValid())
        {
            s_Fault = "variety_data_invalid";
            HCRefuse(s_Fault);
            return false;
        }
        // Optional operator tuning profile uses the same owner DTO. Only the
        // two tuning blocks override authored site data; never clone live sites.
        string tuningText;
        string tuningPath = "$profile:HollowCountry/infected-variety.json";
        if (FileExist(tuningPath))
        {
            HCInfectedVarietyConfig tuningConfig;
            if (!HCInfectedStore.ReadBounded(tuningPath, tuningText) || !JsonFileLoader<HCInfectedVarietyConfig>.LoadData(tuningText, tuningConfig, error) || !tuningConfig)
            {
                HCRefuse("variety_tuning_invalid_json_defaults_retained");
            }
            else
            {
                tuningConfig.HCApplyTuningDefaults(tuningText);
                tuningConfig.HCNormalizeTunables();
                config.GroupScaling = tuningConfig.GroupScaling;
                config.Variety = tuningConfig.Variety;
            }
        }
        config.HCNormalizeTunables();
        s_Config = config;
        Print("[HC Variety] max_posed=" + config.MaxPosed.ToString() + " bounds=0..64 opt_out=MaxPosed=0 runtime=PENDING");
        return true;
    }

    // HollowCountryAnims depends on this owner, never the reverse. No IO per request.
    // Inactive/refused owners admit no new holds; cleanup remains unconditional.
    static int HCMaxPosed()
    {
        if (!s_Running || !s_Config) { return 0; }
        return s_Config.MaxPosed;
    }

    static HCInfectedVarietyConfig HCConfig() { return s_Config; }

    static string HCFault() { return s_Fault; }

    static bool HCRefuse(string reason)
    {
        if (reason != s_LastRefusal)
        {
            s_LastRefusal = reason;
            Print("[HC Variety] fresh_dormant=" + reason + " runtime=PENDING");
        }
        return false;
    }

    static string HCContext(vector pos)
    {
        if (!s_Running || !s_Config) { return ""; }
        float nearest = s_Config.ContextRange * s_Config.ContextRange;
        string context;
        array<ref HCInfectedVarietySite> sites = s_Config.Sites;
        foreach (HCInfectedVarietySite site : sites)
        {
            float distance = vector.DistanceSq(pos, site.Position);
            if (distance > nearest) { continue; }
            nearest = distance;
            context = site.Context;
        }
        return context;
    }

    // Acceptance means one bounded request queued, never a spawn receipt. The
    // normal tick tests nearest candidates one at a time until one is admissible.
    static bool HCAdminFreshDormant(vector pos, out string reason)
    {
        reason = "variety_inactive_or_data_unavailable";
        if (!GetGame().IsServer() || !s_Running || !HCInfectedVarietyModule.VarietyActive()) { return HCRefuse(reason); }
        reason = "variety_invalid_position";
        if (!HCInfectedStore.ValidPosition(pos)) { return HCRefuse(reason); }
        reason = "variety_request_pending";
        if (s_Pending) { return HCRefuse(reason); }
        s_Request = pos;
        s_Admin = true;
        s_Pending = true;
        s_Selected = -1;
        s_Made = 0;
        s_Tried.Clear();
        reason = "variety_fresh_group_queued_runtime_PENDING";
        return true;
    }

    static int HCNearestCandidate()
    {
        int selected = -1;
        float nearest = s_Config.RequestRange * s_Config.RequestRange;
        for (int siteIndex = 0; siteIndex < s_Config.Sites.Count(); siteIndex++)
        {
            if (s_Used.Contains(siteIndex) || s_Tried.Contains(siteIndex)) { continue; }
            float distance = vector.DistanceSq(s_Request, s_Config.Sites[siteIndex].Position);
            if (distance > nearest) { continue; }
            selected = siteIndex;
            nearest = distance;
        }
        return selected;
    }

    static bool HCHidden(vector pos, array<Man> players)
    {
        if (!HCObserverTransitionGate.CanTransition(pos, s_Config.MinSpawnDistance)) { return false; }
        float nearest = HCInfectedLOD.NearestDistance(players, pos);
        if (nearest <= s_Config.MinSpawnDistance) { return false; }
        HCLODSightBudget sight = new HCLODSightBudget;
        sight.HCReset(s_Config.MaxObservers * HCInfectedLOD.RAYS_PER_OBSERVER);
        int observers;
        int occluded;
        HCInfectedLOD.Observers(players, pos, null, s_Config.VisibilityRange, s_Config.MaxObservers, observers, occluded, sight);
        return HCLODPolicy.SpawnHidden(nearest, s_Config.MinSpawnDistance, observers, occluded, s_Config.MaxObservers);
    }

    static void HCStep(float now, float scale)
    {
        if (!s_Running || !HCInfectedVarietyModule.VarietyActive()) { return; }
        HCInfectedModule infected = HCInfectedModule.Instance;
        if (!infected) { return; }
        if (!s_Pending && now < s_NextAutomatic) { return; }
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_INFECTED, 1)) { return; }
        // Includes corpses; only a handle removed by native cleanup frees room.
        for (int bodyIndex = s_Bodies.Count() - 1; bodyIndex >= 0; bodyIndex--)
        {
            if (!s_Bodies[bodyIndex]) { s_Bodies.RemoveOrdered(bodyIndex); }
        }
        if (s_Bodies.Count() >= s_Config.MaxFreshBodies)
        {
            // Automatic retries wait a full interval; an admin request is still refused now.
            if (!s_Pending) { s_NextAutomatic = now + s_Config.AutomaticIntervalSeconds; }
            s_Pending = false;
            HCRefuse("fresh_body_cap_including_corpses");
            return;
        }
        array<Man> players = HCPerfPlayers.HCGet();
        if (!s_Pending)
        {
            s_NextAutomatic = now + s_Config.AutomaticIntervalSeconds;
            if (players.Count() < 1) { return; }
            if (s_PlayerCursor >= players.Count()) { s_PlayerCursor = 0; }
            Man interestPlayer = players[s_PlayerCursor];
            s_PlayerCursor++;
            if (!interestPlayer) { return; }
            s_Request = interestPlayer.GetPosition();
            s_Admin = false;
            s_Pending = true;
            s_Selected = -1;
            s_Made = 0;
            s_Tried.Clear();
        }
        if (!infected.HCVarietyFreshRoom(scale)) { s_Pending = false; HCRefuse("normal_infected_or_posed_cap"); return; }
        if (s_Selected < 0) { s_Selected = HCNearestCandidate(); }
        if (s_Selected < 0) { s_Pending = false; HCRefuse("no_admissible_place"); return; }
        HCInfectedVarietySite site = s_Config.Sites[s_Selected];
        vector pos = site.Position;
        // CE anchors identify context, not clear floor space. Test one outdoor
        // point beside the anchor; never place inside a house or block its door.
        pos[0] = pos[0] + s_Config.ContextRange + s_Made * s_Config.GroupSpacing;
        pos[1] = GetGame().SurfaceY(pos[0], pos[2]);
        float interest = HCInfectedLOD.NearestDistance(players, pos);
        bool interested = s_Admin || (interest >= 0 && interest <= s_Config.InterestRange);
        if (!interested || !HCHidden(pos, players) || !HCAdminPlacement.HCClear(pos))
        {
            s_Tried.Insert(s_Selected, true);
            s_Selected = -1;
            if (s_Made > 0) { s_Pending = false; }
            HCRefuse("place_observed_or_clearance_refused");
            return;
        }
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_INFECTED, 8)) { return; }
        // Audit #121: a posed body is the addon class; the pose layer is requested
        // through the fresh entry below, never by editing a native infected.
        bool poseClass = GetGame().ConfigIsExisting("CfgVehicles " + HCInfectedVarietyPolicy.HCPoseClass());
        int pose = HCInfectedVarietyPolicy.HCPoseFresh(site.Context, s_Made, s_Config.PosedFreshEvery, poseClass);
        string bodyClass = "ZmbM_CitizenASkinny_Brown";
        if (pose > 0) { bodyClass = HCInfectedVarietyPolicy.HCPoseClass(); }
        ZombieBase body = infected.HCLODMaterialize(bodyClass, pos);
        if (!body) { s_Pending = false; HCRefuse("normal_materialize_refused"); return; }
        s_Bodies.Insert(body);
        // Never retry a body or source site: failed native entry leaves a
        // normal tracked living actor, without replacement or deletion.
        if (s_Made == 0) { s_Used.Insert(s_Selected, true); }
        s_Made++;
        bool entered;
        int role = HCInfectedVarietyPolicy.HCContextRole(site.Context, false);
        if (pose > 0)
        {
            entered = body.HCVarietyFreshPosed(now, site.Id, role, pose);
        }
        else if (HCInfectedVarietyPolicy.HCStandingFresh(s_Made - 1, s_Config.StandingRiserEvery))
        {
            entered = body.HCVarietyFreshStanding(now, site.Id, role);
        }
        else { entered = body.HCVarietyFreshCrawler(now, site.Id, role); }
        if (!entered)
        {
            s_Pending = false;
            HCRefuse("fresh_native_entry_refused_body_retained");
            return;
        }
        s_LastRefusal = "";
        Print("[HC Variety] fresh_dormant=created site=" + site.Id + " pose=" + pose.ToString() + " runtime=PENDING");
        if (s_Made >= s_Config.GroupMembers) { s_Pending = false; }
    }

    static void HCStop()
    {
        s_Running = false;
        s_Pending = false;
        s_Config = null;
        // Existing variety owner releases idle. Weak bodies, used sites and
        // corpse capacity survive off/on in this process, preventing refill.
    }
}

modded class HCInfectedModule
{
    bool HCVarietyFreshRoom(float scale)
    {
        if (!m_Healthy || !m_Config || m_Actors.Count() >= Math.Max(0, Math.Min(m_Config.MaxTracked, m_MemberCap) - 4)) { return false; }
        int posedFull = 0;
        int posedIdle = 0;
        int posedTotal = 0;
        array<ref HCInfectedActor> actors = m_Actors;
        foreach (HCInfectedActor actor : actors)
        {
            if (!actor.InfectedEntity || !actor.InfectedEntity.HCVarietyDormant()) { continue; }
            posedTotal++;
            if (actor.LODTier < 0 || actor.LODTier == HCLODPolicy.TIER_FULL) { posedFull++; }
            else { posedIdle++; }
        }
        // Fresh actors start unknown/full, so charge the full tier until LOD
        // classifies them. Shared total cap is checked by the caller as well.
        if (posedTotal >= HCInfectedVarietyPolicy.DormantLimitAt(scale, HCInfectedLOD.PosedBudget())) { return false; }
        return HCInfectedVarietyPolicy.PosedRoom(true, posedFull, posedIdle, HCInfectedLOD.PosedFullBudget(), HCInfectedLOD.PosedIdleBudget());
    }
}
