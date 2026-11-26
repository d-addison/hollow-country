// Row cursor native evidence: 1_Core/proto/EnScript.c:380 Count, :399 Get.
// W5 #121 / #125; source implementation, runtime acceptance PENDING.
// Native evidence, installed scripts-1.30.164289: 3_Game/Global/Game.c:440
// GetDayTime, :945 GetPlayers, :1120 IsServer, :1371 GetWeather;
// 3_Game/Weather.c:189 GetRain, :38 GetActual; 3_Game/dayzplayer.c:633-636
// erect stance masks, :1346 IsPlayerInStance; Entities/Object.c:287 GetPosition,
// :517 IsAlive; 1_Core/proto/EnMath.c:126 RandomFloat01, :427 Floor;
// 4_World/Entities/Creatures/Infected/ZombieBase.c:182 GetMindStateSynced,
// :1090 IsCrawling;
// EnConvert.c:210 DistanceSq, :30 int.ToString, :115 float.ToString;
// EnScript.c:380 Count, :385 Clear; EnDebug.c:96 Print. Geometry uses the
// already inspected HCAlertChain.ClearGeometry (DayZPhysics.c:199 RaycastRV).
// Tick bound: one GetPlayers; at most 32 proximity candidates per sampled
// actor; resumable census/cap passes over <=256 entries (<=32 per tick),
// <=4 posture samples, one retained candidate and <=6 stage steps per tick.
// Selection assigns <=4 roles/refreshes <=4 places; stages scan <=256 entries
// per corpse/place check, do <=1 room query or <=4 dormant wake rays; a single
// shot visits <=32 actors with a cooperative slice, <=3 cues in ONE place, <=6 rays.
// Role/dormant place naming uses <=8*64 existing HCWorld place comparisons.
// Room context reuses HCInfectedRoomCatalog.BuildProductionOrder: existing
// per-tick bind-query cap/radius, <=1 anchor returned, existing room geometry.
// No new persistence, inventory, door state, destinations or synthetic noise.
// Off returns before allocations. Existing v1 admissions/caps remain in force.
// Adopt existing crawlers at tracked corpses or inside catalog room volumes.
// Existing-body path never moves actors or forces injury. W56 fresh groups
// use the separately bounded HCInfectedVariety queue and native crawl request.
// #135: reads the shared infected LOD sample (Infected/LOD/HCInfectedLOD.c)
// instead of re-scanning players when it proves nobody can be within 6 m, and
// takes the posed budget (cap and full/idle sub-budgets) from lod.json; the
// ship default 12/12/12 reproduces the fixed cap exactly. Runtime pending.
// Helper splits describe the SAME worst owner tick as the original fields.
// They overlap posture and must not be added to the owner's total a second time.
// Native: 1_Core/proto/EnSystem.c:106 TickCount; EnString.c:156 Replace;
// EnScript.c:380/399/389 Count/Get/Set; EnConvert.c:30 int.ToString.
class HCVarietyStepTimer : HCStepTimer
{
    protected ref array<int> m_HelperCurrent = {0, 0, 0, 0, 0, 0, 0, 0};
    protected ref array<int> m_HelperWorst = {0, 0, 0, 0, 0, 0, 0, 0};

    void HCVarietyStepTimer(string owner) { m_Owner = owner; }

    void HCHelper(int helper, int started)
    {
        int ticks = TickCount(started);
        if (ticks > 0) { m_HelperCurrent[helper] = m_HelperCurrent[helper] + ticks; }
        if (helper == 3)
        {
            // Splits of this place_fits call only, captured before another
            // catalog consumer can overwrite the last-call measurements.
            m_HelperCurrent[5] = m_HelperCurrent[5] + HCInfectedRoomCatalog.LastBindQueryTicks();
            m_HelperCurrent[6] = m_HelperCurrent[6] + HCInfectedRoomCatalog.LastBindFilterTicks();
            m_HelperCurrent[7] = m_HelperCurrent[7] + HCInfectedRoomCatalog.LastBindAdmissionTicks();
        }
    }

    override void HCEndTick(int totalTicks)
    {
        for (int index = 0; index < 8; index++)
        {
            if (totalTicks > m_WorstTotal) { m_HelperWorst[index] = m_HelperCurrent[index]; }
            m_HelperCurrent[index] = 0;
        }
        super.HCEndTick(totalTicks);
    }

    override string HCLine()
    {
        string line = super.HCLine();
        string helpers = " near_standing=" + m_HelperWorst[0].ToString() + " context=" + m_HelperWorst[1].ToString();
        helpers += " near_corpse=" + m_HelperWorst[2].ToString() + " place_fits=" + m_HelperWorst[3].ToString();
        helpers += " sleep=" + m_HelperWorst[4].ToString();
        helpers += " rooms_query=" + m_HelperWorst[5].ToString() + " rooms_filter=" + m_HelperWorst[6].ToString();
        helpers += " rooms_admit=" + m_HelperWorst[7].ToString();
        line.Replace("; raw TickCount units;", helpers + "; raw TickCount units;");
        return line;
    }

    override void HCCloseWindow()
    {
        super.HCCloseWindow();
        for (int index = 0; index < 8; index++) { m_HelperWorst[index] = 0; }
    }
}

class HCInfectedVarietyModule : HCModule
{
    protected static HCInfectedVarietyModule s_Instance;
    protected bool m_Running;
    protected bool m_Variety;
    protected bool m_Scaling;
    protected bool m_Printed;
    protected ref array<Man> m_Players;
    protected ref HCInfectedVarietyContributor m_Debug;
    protected float m_Clock;
    protected float m_LogAt = 600;
    protected float m_Scale = 1;
    protected bool m_Shot;
    protected vector m_ShotOrigin;
    protected float m_ShotAt;
    protected int m_Woken;
    protected ref HCWorkBudget m_VarietyWork = new HCWorkBudget;
    protected ref HCVarietyStepTimer m_VarietySteps;
    protected int m_WakeRevision;
    protected string m_LastSummary;
    protected float m_SummaryPrintedAt;
    protected float m_CEPrintedAt;
    protected string m_LastCESummary;

    // Shared by the entire modded tick chain, including routes and posture admission.
    void HCMeasureVariety(int stage, string name, int started)
    {
        int ticks = TickCount(started);
        m_VarietySteps.HCAdd(stage, ticks);
        m_VarietySteps.HCItem(name, ticks);
    }

    // #279: first CE summary at 120 s; inspect changes every 300 s.
    // Unchanged summaries heartbeat at most once per 1800 s.
    protected float m_CEVariantsAt = 120;
    protected float m_CEVariantsFrom;

    override string GetName() { return "InfectedVariety"; }
    override bool IsEnabled(HCSettings settings)
    {
        if (!settings || !settings.EnableInfected) { return false; }
        return settings.EnableInfectedVariety || settings.EnableGroupScaling;
    }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings) || m_Running) { return; }
        m_Variety = HCInfectedVariety.HCOperatorEnabled(settings.EnableInfectedVariety);
        HCInfectedVariety.HCStart(settings.EnableInfectedVariety);
        m_Scaling = settings.EnableGroupScaling;
        if (!m_Printed)
        {
            Print(HCV2Admission.Line("InfectedVariety", m_Variety, "W5-121", false));
            m_Printed = true;
        }
        m_VarietySteps = new HCVarietyStepTimer("InfectedVariety");
        m_VarietySteps.HCDefine("observers");
        m_VarietySteps.HCDefine("census");
        m_VarietySteps.HCDefine("caps");
        m_VarietySteps.HCDefine("posture");
        m_VarietySteps.HCDefine("shot");
        m_VarietySteps.HCDefine("fresh");
        m_VarietySteps.HCDefine("routes");
        m_VarietySteps.HCDefine("summary");
        m_Running = true;
        s_Instance = this;
        if (settings.EnableDebugSnapshot)
        {
            m_Debug = new HCInfectedVarietyContributor;
            HCDebugSnapshot.HCRegister(m_Debug);
        }
        Print("[HC Infected] variety source preference=" + HCV2Admission.OnOff(m_Variety) + " scaling=" + HCV2Admission.OnOff(m_Scaling) + "; native crawlers at corpses/catalog rooms and authored CE places; bounded fresh queue; runtime acceptance pending");
        Print("[HC Variety] posture_slice reason=staged_helpers target_ms=2 native_query_bound=PENDING");
        HCPrintCEVariantClasses();
    }

    // Base-class seam: never call a method introduced only on a later modded
    // link. HCModule already declares the operational-status virtual hook.
    static HCOperationalStatus HCObservedStatus()
    {
        if (!s_Instance || !s_Instance.m_Running) { return null; }
        return s_Instance.HCGetOperationalStatus();
    }

    static bool VarietyActive()
    {
        if (!s_Instance || !s_Instance.m_Running || !s_Instance.m_Variety) { return false; }
        return HCInfectedModule.Instance != null;
    }

    static void HCRecordWake()
    {
        if (!VarietyActive()) { return; }
        s_Instance.m_Woken++;
        HCModuleReadiness.HCUse("InfectedVariety", "actor_woken");
        s_Instance.m_WakeRevision++;
    }

    static void HCRecordDamageWake() { HCRecordWake(); }

    static int HCScaledCohort(int requested, int available)
    {
        if (!s_Instance || !s_Instance.m_Running || !s_Instance.m_Scaling) { return requested; }
        return HCInfectedVarietyPolicy.CohortLimit(requested, available, s_Instance.m_Scale);
    }

    // One pending real unsuppressed shot per core tick, no retained shooter,
    // no synthetic noise. Dropped overload never builds an alert queue.
    static void HCRecordShot(vector origin)
    {
        if (!VarietyActive() || s_Instance.m_Shot) { return; }
        if (!HCInfectedStore.ValidPosition(origin)) { return; }
        s_Instance.m_Shot = true;
        s_Instance.m_ShotOrigin = origin;
        s_Instance.m_ShotAt = s_Instance.m_Clock;
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || !(deltaTime > 0) || deltaTime > 300) { return; }
        m_Clock += deltaTime;
        m_VarietyWork.HCReset(64, 4);
        // Consume the first-unit allowance before native work, so later stages
        // cannot each force an extra unit after the shared deadline expires.
        m_VarietyWork.HCContinue();
        int started = TickCount(0);
        m_Players = HCPerfPlayers.HCGet();
        HCReached.Mark("infected_variety.observer_sample");
        HCMeasureVariety(0, "observer_sample", started);
        m_Scale = 1;
        if (m_Scaling) { m_Scale = HCInfectedVarietyPolicy.GroupScale(m_Players.Count()); }
        HCInfectedModule infected = HCInfectedModule.Instance;
        if (infected && m_Variety)
        {
            float nightness = HCInfectedVisionPolicy.Nightness(GetGame().GetDayTime());
            float rain = 0;
            Weather weather = GetGame().GetWeather();
            if (weather) { rain = weather.GetRain().GetActual(); }
            int tickWoken = infected.HCVarietyTick(m_Players, m_Clock, nightness, rain, m_Scale, m_VarietyWork, m_VarietySteps);
            m_Woken += tickWoken;
            m_WakeRevision += tickWoken;
            // HCVarietyTick returns successful wakes only (<=32 cap repairs
            // or <=1 proximity wake). The native callback paths count separately.
            for (int tickWake = 0; tickWake < tickWoken; tickWake++)
            {
                HCModuleReadiness.HCUse("InfectedVariety", "actor_woken");
            }
            if (m_Shot && m_Clock - m_ShotAt <= 2 && m_VarietyWork.HCContinue())
            {
                started = TickCount(0);
                int shotWoken = infected.HCVarietyShot(m_ShotOrigin, nightness, rain, m_VarietyWork);
                m_Woken += shotWoken;
                m_WakeRevision += shotWoken;
                for (int shotWake = 0; shotWake < shotWoken; shotWake++)
                {
                    HCModuleReadiness.HCUse("InfectedVariety", "actor_woken");
                }
                HCMeasureVariety(4, "gunshot", started);
            }
        }
        m_Shot = false;
        if (m_VarietyWork.HCContinue())
        {
            started = TickCount(0);
            HCInfectedVariety.HCStep(m_Clock, m_Scale, m_VarietyWork);
            HCMeasureVariety(5, "fresh_body", started);
        }
        started = TickCount(0);
        if (m_Variety) { HCInfectedVarietyRoutes.HCStep(m_Clock, m_VarietyWork); }
        HCMeasureVariety(6, "migration", started);
        // HCPerfPlayers owns this shared array; never clear it here.
        m_Players = null;
        started = TickCount(0);
        if (m_Clock >= m_LogAt)
        {
            m_LogAt = m_Clock + 600;
            int dormant = 0;
            int runners = 0;
            if (infected) { infected.HCVarietyCounts(dormant, runners); }
            string signature = dormant.ToString() + ":" + m_WakeRevision.ToString() + ":" + m_Woken.ToString() + ":" + runners.ToString() + ":" + m_Scale.ToString();
            if (signature != m_LastSummary || m_Clock - m_SummaryPrintedAt >= 1800)
            {
                Print("[HC Infected] variety dormant=" + dormant.ToString() + " woken=" + m_Woken.ToString() + " runners=" + runners.ToString() + " scale=" + m_Scale.ToString() + " runtime-unverified");
                m_LastSummary = signature;
                m_SummaryPrintedAt = m_Clock;
                m_Woken = 0;
            }
        }
        if (m_Clock >= m_CEVariantsAt)
        {
            m_CEVariantsAt = m_Clock + 300;
            string ceSignature = HCVarietyCounters.HCSignature();
            if (ceSignature != m_LastCESummary || m_Clock - m_CEPrintedAt >= 1800)
            {
                int window = Math.Round(m_Clock - m_CEVariantsFrom);
                Print(HCVarietyCounters.HCSummary(window));
                m_CEVariantsFrom = m_Clock;
                m_CEPrintedAt = m_Clock;
                m_LastCESummary = ceSignature;
            }
        }
        HCMeasureVariety(7, "summaries", started);
    }

    // #279: which CE variant classes the loaded addons define as public (scope 2).
    // One bounded generated units list at startup; mission CE owns populations.
    // Reads go through HCConfigHelper (Game.c:558 ConfigGetTextArray, :539 ConfigGetInt behind presence/type guards).
    protected void HCPrintCEVariantClasses()
    {
        array<string> names = new array<string>;
        HCConfigHelper.GetTextArray("CfgPatches HollowCountryAnims units", names);
        int present = 0;
        string missing = "";
        foreach (string name : names)
        {
            if (HCConfigHelper.GetInt("CfgVehicles " + name + " scope", 0) == 2) { present++; }
            else { missing = missing + " " + name; }
        }
        if (missing == "") { missing = " none"; }
        Print("[HC Variety] ce_variant_classes public=" + present.ToString() + "/" + names.Count().ToString() + " missing=" + missing.Trim() + " max_posed=" + HCInfectedVariety.HCMaxPosed().ToString() + " runtime=PENDING");
    }

    override void OnStop()
    {
        m_Running = false;
        HCInfectedVariety.HCStop();
        HCInfectedModule infected = HCInfectedModule.Instance;
        if (infected) { infected.HCVarietyReleaseAll(); }
        if (m_Debug) { HCDebugSnapshot.HCUnregister(m_Debug); }
        m_Debug = null;
        m_Players = null;
        if (s_Instance == this) { s_Instance = null; }
    }
}

class HCInfectedVarietyContributor : HCDebugContributor
{
    // At most 12 dormant + 2 horde points. No sampling or geometry here.
    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        HCInfectedModule infected = HCInfectedModule.Instance;
        if (infected) { infected.HCVarietyDescribe(snapshot); }
    }
}

modded class HCInfectedModule
{
    protected int m_HCVarietyCursor;

    void HCVarietyCounts(out int dormant, out int runners)
    {
        dormant = 0;
        runners = 0;
        foreach (HCInfectedActor counted : m_Actors)
        {
            ZombieBase entity = counted.InfectedEntity;
            if (!entity || !entity.IsAlive()) { continue; }
            if (entity.HCVarietyDormant()) { dormant++; }
            if (entity.HCVarietyRole() == 2) { runners++; }
        }
    }

    protected string HCVarietyPlaceAt(vector pos)
    {
        HCWorldModule world = HCWorldModule.Get();
        string place;
        if (world) { place = world.NearestPlace(pos); }
        if (place != "") { return place; }
        int cellX = Math.Floor(pos[0] / 500);
        int cellZ = Math.Floor(pos[2] / 500);
        return "wild:" + cellX.ToString() + ":" + cellZ.ToString();
    }

    // At most the existing tracked-actor cap; no world query or ray.
    // Native: Object.c:287 GetPosition, :517 IsAlive; EnConvert.c:210 DistanceSq.
    protected bool HCVarietyNearCorpse(ZombieBase candidate)
    {
        vector position = candidate.GetPosition();
        foreach (HCInfectedActor corpse : m_Actors)
        {
            if (!corpse.InfectedEntity || corpse.InfectedEntity.IsAlive()) { continue; }
            if (vector.DistanceSq(position, corpse.InfectedEntity.GetPosition()) <= 100) { return true; }
        }
        return false;
    }

    // Context selection only: an actor is already here. Do not use returned
    // room points as destinations, create entities, or change door/path state.
    // The existing catalog owns template binding and its per-tick query cap;
    // native calls stay in that inspected service (HCInfectedRooms.c:1474-1618).
    // It queries Game.c:930 GetObjectsAtPosition3D once, retains its existing
    // radius/result caps, binds houses and orders room anchors. No raycasts.
    // Object.c:287/305/467 GetPosition/GetOrientation/GetType, :874 WorldToModel,
    // :873 ModelToWorld. This synchronous service cannot promise a 2 ms bound.
    protected bool HCVarietyPlaceFits(ZombieBase candidate)
    {
        TVectorArray roomPoints = new TVectorArray;
        HCInfectedRoomCatalog.BuildProductionOrder(candidate.GetPosition(), 1, roomPoints);
        return roomPoints.Count() > 0;
    }

    protected int HCVarietyInPlace(string place)
    {
        int total = 0;
        foreach (HCInfectedActor resident : m_Actors)
        {
            ZombieBase entity = resident.InfectedEntity;
            if (!entity || !entity.IsAlive() || !entity.HCVarietyDormant()) { continue; }
            if (entity.HCVarietyPlace() == place) { total++; }
        }
        return total;
    }

    // Native: Global/DayZPhysics.c:199 RaycastRV, via HCAlertChain.ClearGeometry
    // (HCAlertChain.c:153-165). Base <=32 players/two rays; HCPoseVariation
    // override can also try one close observer (<=32 more players/two rays).
    protected bool HCVarietyNearStanding(array<Man> players, HCInfectedActor actor, ZombieBase candidate, bool checkGeometry, bool preserveObserver = false)
    {
        // Shared LOD sample: nobody can be within 6 m, so no standing player
        // can be either (same result as the scan below, without it).
        if (actor && HCLODPolicy.SafelyFar(actor.LODDistance, GetGame().GetTickTime() - actor.LODAt, 6)) { return false; }
        int count = Math.Min(32, players.Count());
        // The final no-geometry safety recheck must not advance the future
        // geometry observer rotation a second time for this same candidate.
        int first;
        if (!preserveObserver) { first = candidate.HCVarietyObserverOffset(players.Count()); }
        for (int playerIndex = 0; playerIndex < count; playerIndex++)
        {
            int rosterIndex = (first + playerIndex) % players.Count();
            PlayerBase player = PlayerBase.Cast(players[rosterIndex]);
            if (!player || !player.IsAlive()) { continue; }
            if (vector.DistanceSq(player.GetPosition(), candidate.GetPosition()) > 36) { continue; }
            int erect = DayZPlayerConstants.STANCEMASK_ERECT | DayZPlayerConstants.STANCEMASK_RAISEDERECT;
            if (!player.IsPlayerInStance(erect)) { continue; }
            if (!checkGeometry) { return true; }
            // One geometry candidate per actor/tick. Rotating the first
            // observer prevents an occluded player starving another candidate.
            return m_AlertChain.HCVarietyClear(player.GetPosition(), candidate);
        }
        return false;
    }

    protected int m_HCVarietyPhase;
    protected int m_HCVarietyScan;
    protected int m_HCVarietySize;
    protected int m_HCVarietyLiving;
    protected int m_HCVarietyRunners;
    protected int m_HCVarietyDormant;
    protected int m_HCVarietyFull;
    protected int m_HCVarietyIdle;
    protected int m_HCVarietySamples;
    protected int m_HCVarietyDormantCap = -1;

    int HCVarietyTick(array<Man> players, float now, float nightness, float rain, float scale, HCWorkBudget workBudget, HCVarietyStepTimer steps)
    {
        if (!m_Healthy || !HCInfectedVarietyModule.VarietyActive()) { return 0; }
        int woken = 0;
        // Retain scan cursors across ticks. A census/cap pass processes at most
        // 32 actors in a 4 ms shared slice; posture retains one candidate and
        // executes at most six stage steps per admitted tick.
        // Roster/cap changes restart counts before any new posture admission.
        int dormantCap = HCInfectedVarietyPolicy.DormantLimitAt(scale, HCInfectedLOD.PosedBudget());
        if (m_HCVarietySize != m_Actors.Count() || m_HCVarietyDormantCap != dormantCap)
        {
            m_HCVarietyPhase = 0;
            m_HCVarietyScan = 0;
            m_HCPostureActor = null;
        }
        m_HCVarietySize = m_Actors.Count();
        m_HCVarietyDormantCap = dormantCap;
        int started = TickCount(0);
        if (m_HCVarietyPhase == 0)
        {
            if (m_HCVarietyScan == 0) { m_HCVarietyLiving = 0; }
            int countedWork = 0;
            while (m_HCVarietyScan < m_Actors.Count() && countedWork < 32 && workBudget.HCContinue())
            {
                HCInfectedActor counted = m_Actors[m_HCVarietyScan];
                m_HCVarietyScan++;
                countedWork++;
                if (counted && counted.InfectedEntity && counted.InfectedEntity.IsAlive()) { m_HCVarietyLiving++; }
            }
            int censusTicks = TickCount(started);
            steps.HCAdd(1, censusTicks);
            steps.HCItem("living_census", censusTicks);
            if (m_HCVarietyScan >= m_Actors.Count())
            {
                m_HCVarietyPhase = 1;
                m_HCVarietyScan = 0;
                m_HCVarietyRunners = 0;
                m_HCVarietyDormant = 0;
                m_HCVarietyFull = 0;
                m_HCVarietyIdle = 0;
            }
            return 0;
        }
        int runnerCap = HCInfectedVarietyPolicy.RunnerLimit(m_HCVarietyLiving, nightness);
        if (m_HCVarietyPhase == 1)
        {
            int boundedWork = 0;
            while (m_HCVarietyScan < m_Actors.Count() && boundedWork < 32 && workBudget.HCContinue())
            {
                HCInfectedActor bounded = m_Actors[m_HCVarietyScan];
                m_HCVarietyScan++;
                boundedWork++;
                if (!bounded) { continue; }
                ZombieBase boundedEntity = bounded.InfectedEntity;
                if (!boundedEntity) { continue; }
                if (!boundedEntity.IsAlive()) { boundedEntity.HCVarietyRelease(); continue; }
                if (boundedEntity.HCVarietyRole() == 2)
                {
                    if (m_HCVarietyRunners >= runnerCap)
                    {
                        boundedEntity.HCVarietyAssign(1, boundedEntity.HCVarietyPlace());
                    }
                    else { m_HCVarietyRunners++; }
                }
                if (boundedEntity.HCVarietyDormant())
                {
                    bool overCap = m_HCVarietyDormant >= dormantCap;
                    if (HCInfectedVarietyPolicy.HCShouldWakeDormant(overCap, boundedEntity.GetMindStateSynced() != DayZInfectedConstants.MINDSTATE_CALM))
                    {
                        if (boundedEntity.HCVarietyWake()) { woken++; }
                    }
                    else
                    {
                        m_HCVarietyDormant++;
                        if (bounded.LODTier < 0 || bounded.LODTier == HCLODPolicy.TIER_FULL) { m_HCVarietyFull++; }
                        else { m_HCVarietyIdle++; }
                    }
                }
            }
            int capTicks = TickCount(started);
            steps.HCAdd(2, capTicks);
            steps.HCItem("cap_repair", capTicks);
            if (m_HCVarietyScan >= m_Actors.Count())
            {
                m_HCVarietyPhase = 2;
                m_HCVarietySamples = 0;
            }
            return woken;
        }
        // A separate posture target does not give the rest of this module a
        // fresh slice. Both this 2 ms deadline and the shared 4 ms deadline
        // must admit work; consume the first-unit exception before selection.
        // First guard + four samples + six stages + three inner guards.
        m_HCPostureWork.HCReset(14, 2);
        m_HCPostureWork.HCContinue();
        if (!m_HCPostureActor)
        {
            int work = Math.Min(4, m_Actors.Count());
            for (int sampleIndex = 0; sampleIndex < work && workBudget.HCContinue() && m_HCPostureWork.HCContinue(); sampleIndex++)
            {
                m_HCVarietySamples++;
                if (m_HCVarietyCursor >= m_Actors.Count()) { m_HCVarietyCursor = 0; }
                int selected = m_HCVarietyCursor;
                m_HCVarietyCursor++;
                HCInfectedActor actor = m_Actors[selected];
                if (!actor) { continue; }
                ZombieBase entity = actor.InfectedEntity;
                if (!entity || !entity.IsAlive()) { continue; }
                // Preserve role assignment for standing actors too, before the
                // crawler-only cheap filters. Native evidence is listed above.
                if (entity.HCVarietyRole() < 0)
                {
                    int roleStarted = TickCount(0);
                    string roleContext = HCInfectedVariety.HCContext(entity.GetPosition());
                    steps.HCHelper(1, roleStarted);
                    int role = HCInfectedVarietyPolicy.HCContextRole(roleContext, m_HCVarietyRunners < runnerCap && !entity.IsCrawling());
                    if (role == 2) { m_HCVarietyRunners++; }
                    entity.HCVarietyAssign(role, HCVarietyPlaceAt(entity.GetPosition()));
                }
                if (entity.HCVarietyDormant())
                {
                    int wakeStarted = TickCount(0);
                    bool wake = HCVarietyNearStanding(players, actor, entity, true);
                    steps.HCHelper(0, wakeStarted);
                    if (wake && entity.HCVarietyWake())
                    {
                        woken++;
                        m_HCVarietyDormant--;
                        if (actor.LODTier < 0 || actor.LODTier == HCLODPolicy.TIER_FULL) { m_HCVarietyFull--; }
                        else { m_HCVarietyIdle--; }
                    }
                    // As before, only one geometry/wake candidate per tick.
                    break;
                }
                if (!entity.HCVarietyCanTry(now) || !entity.IsCrawling()) { continue; }
                if (actor.GroupId != 0 || actor.SearchPack || actor.EverAssigned || entity.GetMindStateSynced() != DayZInfectedConstants.MINDSTATE_CALM) { continue; }
                // Refresh the real location BEFORE cap/posed-budget rejection.
                entity.HCVarietyAssign(entity.HCVarietyRole(), HCVarietyPlaceAt(entity.GetPosition()));
                bool nearPlayers = actor.LODTier < 0 || actor.LODTier == HCLODPolicy.TIER_FULL;
                if (m_HCVarietyDormant >= dormantCap || HCVarietyInPlace(entity.HCVarietyPlace()) >= 3) { continue; }
                if (!HCInfectedVarietyPolicy.PosedRoom(nearPlayers, m_HCVarietyFull, m_HCVarietyIdle, HCInfectedLOD.PosedFullBudget(), HCInfectedLOD.PosedIdleBudget())) { continue; }
                if (players.Count() > 32) { continue; }
                m_HCPostureActor = actor;
                m_HCPostureSlot = selected;
                m_HCPosturePosition = actor.InfectedEntity.GetPosition();
                m_HCPostureStage = 2;
                m_HCPostureRetries = 0;
                m_HCPostureCorpse = false;
                break;
            }
        }
        for (int stageStep = 0; stageStep < 6 && m_HCPostureActor; stageStep++)
        {
            if (!workBudget.HCContinue() || !m_HCPostureWork.HCContinue()) { break; }
            int previousStage = m_HCPostureStage;
            woken += HCVarietyPostureStep(players, now, nightness, rain, dormantCap, steps);
            // An inner budget refusal must stop this tick immediately too.
            if (m_HCPostureStage == previousStage) { break; }
        }
        if (m_HCPostureActor)
        {
            m_HCPostureRetries++;
            if (m_HCPostureRetries >= 3) { m_HCPostureActor = null; }
        }
        int postureTicks = TickCount(started);
        steps.HCAdd(3, postureTicks);
        steps.HCItem("posture_candidate", postureTicks);
        if (!m_HCPostureActor && m_HCVarietySamples >= Math.Min(32, m_Actors.Count()))
        {
            m_HCVarietyPhase = 0;
            m_HCVarietyScan = 0;
        }
        return woken;
    }

    protected ref HCWorkBudget m_HCPostureWork = new HCWorkBudget;
    // ref: HCInfectedActor is not Managed, so a raw member is not nulled when HCInfectedModule recycles
    // the slot (m_Actors[slot] = actor frees the old one with Count unchanged). The slot identity
    // check in HCVarietyPostureStep then sees the replacement and drops the candidate.
    protected ref HCInfectedActor m_HCPostureActor;
    protected int m_HCPostureSlot;
    protected int m_HCPostureStage;
    protected int m_HCPostureRetries;
    protected bool m_HCPostureCorpse;
    protected vector m_HCPosturePosition;

    // Role assignment and cheap filters run inline for <=4 samples. One held
    // candidate runs stages 2..6 in <=6 steps, stopping at the first refusal
    // or unchanged stage. Three deferred ticks discard that candidate (including
    // refusals inside stages 2/6); no private-budget starvation pins the cursor.
    // Sleep repeats proximity against LIVE players without geometry, and a
    // corpse-qualified candidate must still have a nearby corpse at commit.
    // Movement >0.5 m, roster/cap changes or unsafe live predicates discard it.
    // The 2 ms goal is cooperative: room binding and each RaycastRV are native
    // synchronous calls; only the next native soak can establish their cost.
    // Native: Game.c:914 GetTickTime; Object.c:287 GetPosition, :517 IsAlive;
    // ZombieBase.c:182 GetMindStateSynced, :1090 IsCrawling; EnMath.c:126 RandomFloat01.
    protected int HCVarietyPostureStep(array<Man> players, float now, float nightness, float rain, int dormantCap, HCVarietyStepTimer steps)
    {
        HCInfectedActor actor = m_HCPostureActor;
        if (!actor) { return 0; }
        // Slot identity first: the candidate is held across ticks, so confirm it is still tracked before reading it.
        if (m_HCPostureSlot >= m_Actors.Count() || m_Actors[m_HCPostureSlot] != actor)
        {
            m_HCPostureActor = null;
            return 0;
        }
        ZombieBase entity = actor.InfectedEntity;
        if (!entity || !entity.IsAlive())
        {
            m_HCPostureActor = null;
            return 0;
        }
        if (vector.DistanceSq(entity.GetPosition(), m_HCPosturePosition) > 0.25)
        {
            m_HCPostureActor = null;
            return 0;
        }
        int helperStarted;
        // Recheck the cheap safety predicates on every admission stage. No
        // other posture candidate is admitted while this one holds the cursor.
        if (!entity.HCVarietyCanTry(now) || !entity.IsCrawling() || entity.HCVarietyDormant()) { m_HCPostureActor = null; return 0; }
        if (actor.GroupId != 0 || actor.SearchPack || actor.EverAssigned || entity.GetMindStateSynced() != DayZInfectedConstants.MINDSTATE_CALM)
        {
            m_HCPostureActor = null;
            return 0;
        }
        bool nearPlayers = actor.LODTier < 0 || actor.LODTier == HCLODPolicy.TIER_FULL;
        if (m_HCVarietyDormant >= dormantCap || !HCInfectedVarietyPolicy.PosedRoom(nearPlayers, m_HCVarietyFull, m_HCVarietyIdle, HCInfectedLOD.PosedFullBudget(), HCInfectedLOD.PosedIdleBudget()))
        {
            m_HCPostureActor = null;
            return 0;
        }
        if (m_HCPostureStage == 2)
        {
            if (HCVarietyInPlace(entity.HCVarietyPlace()) >= 3 || players.Count() > 32) { m_HCPostureActor = null; return 0; }
            if (!m_HCPostureWork.HCContinue()) { return 0; }
            helperStarted = TickCount(0);
            bool standing = HCVarietyNearStanding(players, actor, entity, false);
            steps.HCHelper(0, helperStarted);
            if (standing) { m_HCPostureActor = null; return 0; }
            m_HCPostureStage = 3;
            return 0;
        }
        if (m_HCPostureStage == 3)
        {
            helperStarted = TickCount(0);
            string context = HCInfectedVariety.HCContext(entity.GetPosition());
            steps.HCHelper(1, helperStarted);
            m_HCPostureStage = 4;
            if (context != "") { m_HCPostureStage = 6; }
            return 0;
        }
        if (m_HCPostureStage == 4)
        {
            helperStarted = TickCount(0);
            bool corpse = HCVarietyNearCorpse(entity);
            steps.HCHelper(2, helperStarted);
            m_HCPostureStage = 5;
            if (corpse)
            {
                m_HCPostureCorpse = true;
                m_HCPostureStage = 6;
            }
            return 0;
        }
        if (m_HCPostureStage == 5)
        {
            helperStarted = TickCount(0);
            bool fits = HCVarietyPlaceFits(entity);
            steps.HCHelper(3, helperStarted);
            if (!fits) { m_HCPostureActor = null; return 0; }
            m_HCPostureStage = 6;
            return 0;
        }
        if (m_HCPostureCorpse)
        {
            if (!m_HCPostureWork.HCContinue()) { return 0; }
            helperStarted = TickCount(0);
            bool corpseStillNear = HCVarietyNearCorpse(entity);
            steps.HCHelper(2, helperStarted);
            if (!corpseStillNear) { m_HCPostureActor = null; return 0; }
        }
        // Revalidate the place cap after the room query (fresh bodies and
        // native wake callbacks may have changed occupancy between stages).
        if (HCVarietyInPlace(entity.HCVarietyPlace()) >= 3 || players.Count() > 32) { m_HCPostureActor = null; return 0; }
        if (!m_HCPostureWork.HCContinue()) { return 0; }
        m_HCPostureActor = null;
        helperStarted = TickCount(0);
        bool newlyStanding = HCVarietyNearStanding(players, actor, entity, false, true);
        steps.HCHelper(0, helperStarted);
        if (newlyStanding) { return 0; }
        bool permitted = Math.RandomFloat01() < HCInfectedVarietyActivity.HCDormantChance(entity.HCVarietyPlace(), nightness, rain);
        // Sleep is O(1): DayZInfected.c:107 GetInputController,
        // DayZInfectedInputController.c:9 GetMindState, DayZAnimal.c:193
        // GetAIAgent, AIAgent.c:6 SetKeepInIdle; no spatial query or loop.
        // HCPoseVariation adds Game.c:914 GetTickTime and one scalar draw.
        helperStarted = TickCount(0);
        bool slept = entity.HCVarietySleep(now, permitted);
        steps.HCHelper(4, helperStarted);
        if (slept)
        {
            m_HCVarietyDormant++;
            if (nearPlayers) { m_HCVarietyFull++; }
            else { m_HCVarietyIdle++; }
        }
        return 0;
    }

    protected int m_HCShotCursor;

    int HCVarietyShot(vector origin, float nightness, float rain, HCWorkBudget workBudget)
    {
        if (!m_Healthy || !HCInfectedVarietyModule.VarietyActive()) { return 0; }
        bool wake = Math.RandomFloat01() <= HCInfectedVarietyPolicy.NoiseWakeChance(nightness, rain);
        string place;
        int recipients = 0;
        int checks = 0;
        int woken = 0;
        for (int scanned = 0; scanned < m_Actors.Count() && scanned < m_WorkCap; scanned++)
        {
            if (!workBudget.HCContinue()) { break; }
            m_HCShotCursor = m_HCShotCursor % m_Actors.Count();
            HCInfectedActor actor = m_Actors[m_HCShotCursor];
            m_HCShotCursor++;

            ZombieBase entity = actor.InfectedEntity;
            if (!entity || !entity.IsAlive()) { continue; }
            if (recipients >= 3) { break; }
            if (place != "" && entity.HCVarietyPlace() != place) { continue; }
            if (vector.DistanceSq(origin, entity.GetPosition()) > 6400) { continue; }
            if (checks >= 3) { break; }
            checks++;
            if (!m_AlertChain.HCVarietyClear(origin, entity)) { continue; }
            place = entity.HCVarietyPlace();
            if (wake && entity.HCVarietyDormant() && entity.HCVarietyWake()) { woken++; }
            recipients++;
            // Awake recipients also get the frozen event; wake probability
            // controls posture only. Keep <=80 m, <=3 recipients, <=6 rays.
            actor.Heard = HCHordeStimulus.HCVarietyGunshot(origin, m_Now);
            actor.HeardExternally = true;
        }
        return woken;
    }

    void HCVarietyReleaseAll()
    {
        m_HCVarietyPhase = 0;
        m_HCVarietyScan = 0;
        m_HCPostureActor = null;
        foreach (HCInfectedActor actor : m_Actors)
        {
            if (actor.InfectedEntity) { actor.InfectedEntity.HCVarietyRelease(); }
        }
    }

    override void OnStop()
    {
        HCVarietyReleaseAll();
        super.OnStop();
    }

    override protected void Quarantine(string reason)
    {
        HCVarietyReleaseAll();
        super.Quarantine(reason);
    }

    void HCVarietyDescribe(HCDebugSnapshot snapshot)
    {
        if (snapshot.HCPhase == 0)
        {
            int shown = snapshot.HCShown;
            for (int debugIndex = snapshot.HCRow; debugIndex < m_Actors.Count(); debugIndex++)
            {
                if (!snapshot.HCRowStep()) { return; }
                HCInfectedActor actor = m_Actors[debugIndex];
                ZombieBase entity = actor.InfectedEntity;
                if (!entity || !entity.IsAlive() || !entity.HCVarietyDormant()) { continue; }
                if (shown >= 12) { break; }
                snapshot.AddPoint("infected", "dormant:" + shown.ToString(), entity.GetPosition(), "Dormant crawler", entity.HCVarietyPlace());
                shown++;
                snapshot.HCShown = shown;
            }
            snapshot.HCPhase = 1;
            snapshot.HCRow = 0;
        }
        if (!m_State) { return; }
        int hordeCount = Math.Min(2, m_State.Groups.Count());
        for (int hordeIndex = snapshot.HCRow; hordeIndex < hordeCount; hordeIndex++)
        {
            if (!snapshot.HCRowStep()) { return; }
            HCHordeRecord group = m_State.Groups[hordeIndex];
            if (group.State == 5 || group.State == 6) { continue; }
            snapshot.AddPoint("infected", "horde:" + group.Id.ToString(), group.Anchor, "Horde", "journal living=" + group.Living.ToString());
        }
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCInfectedVarietyModule);
    }
}
