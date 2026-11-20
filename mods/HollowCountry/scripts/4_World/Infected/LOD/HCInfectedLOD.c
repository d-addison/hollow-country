// #135 shared infected LOD service and virtual herds. Source implementation;
// runtime acceptance pending (runtime=PENDING) and every range/cap provisional
// until measured with 3-6 players.
//
// Tiers (HCLODPolicy, Core/HCLODPolicy.c): full AI near players, idle (posed or
// dormant) at middle range, virtual (data only) far from every player. One
// bounded cursor classifies at most ClassifyPerTick tracked actors per core
// tick against the shared per-frame player roster (HCPerfPlayers) and writes
// HCInfectedActor.LODTier/LODDistance/LODAt. Consumers read that sample
// instead of re-scanning players: variety dormancy (posed budget and the
// near-standing skip) today. Reach and doors are player-centred, not infected
// proximity scans, so they keep their own bounded queries.
//
// Virtual herds (owner default ON; explicit v2 false opts out): a herd keeps its full head count as data in
// $profile:HollowCountry/infected-lod.json. While a player is within
// MaterializeRange of the herd edge, at most MaxPerHerd of its living members
// exist as bodies; each body is created through the admin sitter spawn path
// (Admin/HCAdminDirectors.c HCAdminSitter: CreateObjectEx with ECE_INITAI |
// ECE_PLACE_ON_SURFACE, cast, FindActor/Track, delete on refusal) and only at
// a point beyond MinSpawnDistance from every player, clear of the shared
// observer gate, with every observer within VisibilityRange occluded on both
// view and fire geometry, and on clear ground (HCAdminPlacement.HCClear).
// A body folds back to data only when it is alive, calm, unclaimed, not hit
// for FOLD_HIT_QUIET seconds, beyond FoldRange from every player and unseen
// by the same bounded multi-point test. Death debits the herd; a horde claim
// releases the body to the horde system and debits the herd, so no head
// exists twice.
// Never moves a body: no teleports, no silent movement fixes.
//
// Native scripts-1.30.164289: 3_Game/Global/Game.c:703 CreateObjectEx, :705
// ObjectDelete, :914 GetTickTime, :945 GetPlayers (via HCPerfPlayers), :1176
// SurfaceY; CE/CentralEconomy.c:18 ECE_INITAI, :38 ECE_PLACE_ON_SURFACE;
// 3_Game/Global/DayZPhysics.c:199 RaycastRV, :67-68 ObjIntersectFire/View;
// 3_Game/Entities/DayZInfected.c:13-18 MINDSTATE_*; 4_World/Entities/
// Creatures/Infected/ZombieBase.c:182 GetMindStateSynced, :981 EEHitBy, :1090
// IsCrawling; 3_Game/Entities/Object.c:287 GetPosition, :511 IsKindOf, :517
// IsAlive; 1_Core/proto/EnEntity.c:571 GetParent; 1_Core/proto/EnMath.c:13
// PI2, :38 RandomInt, :126 RandomFloat01, :305 Sqrt, :331 Sin, :343 Cos, :553
// Min, :566 Max; 1_Core/proto/EnConvert.c:196 Distance, :210 DistanceSq.
//
// Per-tick bound: <=24 classified actors x <=64 players DistanceSq; herds on:
// <=24 lease polls, then ONE fold or ONE materialize attempt (alternating),
// three spatial samples x two geometries, capped at MaxObservers(<=8) x
// RAYS_PER_OBSERVER (6) casts total, so a full party can be proven occluded, one HCClear (128 objects, 64 doors), at most one CreateObjectEx;
// regrow <=16 herds per minute; stats once a minute.
// Off: OnTick returns at the first check, no allocations.
class HCLODSightBudget
{
    int Limit;
    int Used;
    void HCReset(int limit) { Limit = limit; Used = 0; }
}

class HCLODLease
{
    ZombieBase Body;
    string HerdId;
    float SpawnedAt;
}

// Alive includes leased bodies. Retain their weak native handles across a
// module stop/start; never delete a visible body or debit a living head just
// because the module stops. A process restart clears native handles; the
// journal already contains the complete living count (native restart pending).
class HCLODStopLeases
{
    protected static ref array<ref HCLODLease> s_Leases;

    static void HCHold(array<ref HCLODLease> leases) { s_Leases = leases; }

    static array<ref HCLODLease> HCTake()
    {
        ref array<ref HCLODLease> leases = s_Leases;
        s_Leases = null;
        if (!leases) { leases = new array<ref HCLODLease>; }
        return leases;
    }
}

class HCInfectedLOD
{
    static const int MAX_TOMBSTONES = 24;
    // Occluded() casts 3 samples x 2 geometries per observer.
    static const int RAYS_PER_OBSERVER = 6;
    protected static ref HCInfectedLODConfig s_Config;

    static void HCSet(HCInfectedLODConfig config) { s_Config = config; }

    static bool Active() { return s_Config != null && s_Config.EnableLOD; }

    // Tiered posed budget; 12/12/12 (the shipped fixed cap) when inactive.
    static int PosedBudget()
    {
        if (!HCInfectedLOD.Active()) { return HCInfectedTuning.Get().LevelOfDetail.PosedFallback; }
        return s_Config.PosedBudget;
    }

    static int PosedFullBudget()
    {
        if (!HCInfectedLOD.Active()) { return HCInfectedTuning.Get().LevelOfDetail.PosedFallback; }
        return s_Config.PosedFullBudget;
    }

    static int PosedIdleBudget()
    {
        if (!HCInfectedLOD.Active()) { return HCInfectedTuning.Get().LevelOfDetail.PosedFallback; }
        return s_Config.PosedIdleBudget;
    }

    // -1 when the roster exceeds MAX_PLAYERS (unknown, never degrades);
    // 100000 when nobody is connected. Dead players still count as observers.
    static float NearestDistance(array<Man> players, vector pos)
    {
        if (!players || players.Count() > HCLODPolicy.MAX_PLAYERS) { return -1; }
        float best = -1;
        for (int index = 0; index < players.Count(); index++)
        {
            Man player = players[index];
            if (!player) { continue; }
            float squared = vector.DistanceSq(pos, player.GetPosition());
            if (best < 0 || squared < best) { best = squared; }
        }
        if (best < 0) { return 100000; }
        return Math.Sqrt(best);
    }

    protected static bool Blocked(bool hit, set<Object> hits, Object body, vector eye, vector aim, vector contact)
    {
        if (!hit) { return false; }
        if (body && hits.Count() > 0 && hits[0] == body) { return false; }
        float toContact = vector.Distance(eye, contact);
        // A contact at the eye is the observer's own gear, not cover.
        if (toContact < 1.5) { return false; }
        return toContact < vector.Distance(eye, aim) - 1.5;
    }

    // Three spatial samples, each checked against view AND fire geometry.
    // Every actual cast spends the shared tick budget; unknown sight is clear.
    protected static bool RayBlocked(Man player, vector eye, vector aim, Object body, int geometry, HCLODSightBudget budget)
    {
        if (!budget || budget.Used >= budget.Limit) { return false; }
        if (vector.Distance(eye, aim) < 4) { return false; }
        budget.Used++;
        vector contact;
        vector normal;
        int component;
        set<Object> hits = new set<Object>;
        bool hit = DayZPhysics.RaycastRV(eye, aim, contact, normal, component, hits, null, player, true, false, geometry);
        return HCInfectedLOD.Blocked(hit, hits, body, eye, aim, contact);
    }

    protected static vector SightAim(vector target, vector eye, int sample)
    {
        if (sample == 0) { return target + "0 1.7 0"; }
        if (sample == 1) { return target + "0 1.1 0"; }
        vector delta = target - eye;
        float length = Math.Sqrt(delta[0] * delta[0] + delta[2] * delta[2]);
        if (length < 1) { return target + "0 1.1 0"; }
        vector side = Vector(delta[2], 0, -delta[0]) * (0.4 / length);
        return target + "0 1.1 0" + side;
    }

    // A partial view at any point vetoes the transition. Vehicle/unknown eye
    // observers also veto it. Native PlayerBase.c:7136-7137 uses the head bone;
    // Object.c:238 GetBonePositionWS, DayZAnimal.c:53 GetBoneIndexByName.
    static bool Occluded(Man player, vector target, Object body, HCLODSightBudget budget)
    {
        if (!player || player.GetParent()) { return false; }
        PlayerBase observer = PlayerBase.Cast(player);
        if (!observer) { return false; }
        int head = observer.GetBoneIndexByName("head");
        if (head < 0) { return false; }
        vector eye = observer.GetBonePositionWS(head);
        int sample = 0;
        while (sample < 3)
        {
            vector aim = HCInfectedLOD.SightAim(target, eye, sample);
            if (!HCInfectedLOD.RayBlocked(player, eye, aim, body, ObjIntersectView, budget)) { return false; }
            if (!HCInfectedLOD.RayBlocked(player, eye, aim, body, ObjIntersectFire, budget)) { return false; }
            sample++;
        }
        return true;
    }

    // Counts players within range and how many of them are occluded. Stops
    // (with observers > maxObservers) instead of casting unbounded rays.
    static void Observers(array<Man> players, vector target, Object body, float range, int maxObservers, out int observers, out int occluded, HCLODSightBudget budget)
    {
        observers = 0;
        occluded = 0;
        if (!players) { return; }
        float rangeSq = range * range;
        int count = Math.Min(players.Count(), HCLODPolicy.MAX_PLAYERS);
        for (int index = 0; index < count; index++)
        {
            Man player = players[index];
            if (!player) { continue; }
            if (vector.DistanceSq(player.GetPosition(), target) > rangeSq) { continue; }
            observers++;
            if (observers > maxObservers) { return; }
            if (HCInfectedLOD.Occluded(player, target, body, budget)) { occluded++; }
        }
    }
}

modded class ZombieBase
{
    // Server tick time of the latest hit; -1 never hit. Read by the fold
    // decision and experiment 1 only.
    protected float m_HCLODHitAt = -1;

    float HCLODHitAt() { return m_HCLODHitAt; }

    override void EEHitBy(TotalDamageResult damageResult, int damageType, EntityAI source, int component, string dmgZone, string ammo, vector modelPos, float speedCoef)
    {
        super.EEHitBy(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);
        if (GetGame().IsServer()) { m_HCLODHitAt = GetGame().GetTickTime(); }
    }
}

modded class HCInfectedModule
{
    protected int m_HCLODCursor;
    // Recyclable history has its own FIFO cap; never consumes live slots.
    // Assigned, unresolved evidence remains with the recovery owner.
    protected ref array<ref HCInfectedActor> m_HCLODTombstones = new array<ref HCInfectedActor>;

    protected void HCLODArchive(int index)
    {
        HCInfectedActor actor = m_Actors[index];
        if (actor.SearchPack) { actor.SearchPack.Release(); actor.SearchPack = null; }
        if (m_HCLODTombstones.Count() >= HCInfectedLOD.MAX_TOMBSTONES) { m_HCLODTombstones.RemoveOrdered(0); }
        m_HCLODTombstones.Insert(actor);
        m_Actors.RemoveOrdered(index);
        m_HCLODCursor = 0;
        m_Cursor = 0;
        m_AdoptionCursor = 0;
        m_RecoveryCursor = 0;
        ResetSweep();
    }

    protected void HCLODPrune()
    {
        int index = 0;
        while (index < m_Actors.Count())
        {
            HCInfectedActor actor = m_Actors[index];
            if ((!actor.InfectedEntity || !actor.InfectedEntity.IsAlive()) && CanRecycleActor(actor)) { HCLODArchive(index); continue; }
            index++;
        }
    }

    void HCLODRetire(ZombieBase body)
    {
        for (int index = m_Actors.Count() - 1; index >= 0; index--)
        {
            HCInfectedActor actor = m_Actors[index];
            if (actor.InfectedEntity == body && CanRecycleActor(actor)) { HCLODArchive(index); return; }
        }
    }

    // The shared LOD cursor: <=work tracked actors per call.
    int HCLODClassify(array<Man> players, float now, int work, float fullRange, float idleRange)
    {
        if (!m_Healthy || m_Actors.Count() == 0) { return 0; }
        int count = m_Actors.Count();
        int spent = 0;
        HCUnitBudget lodWork = HCServer.HCTickWork();
        while (spent < work && spent < count && lodWork.HCTakeFor(HCUnitBudget.HC_WORK_LOD_CLASSIFY, 1))
        {
            if (m_HCLODCursor >= count) { m_HCLODCursor = 0; }
            HCInfectedActor actor = m_Actors[m_HCLODCursor];
            m_HCLODCursor++;
            spent++;
            if (!actor) { continue; }
            ZombieBase entity = actor.InfectedEntity;
            if (!entity || !entity.IsAlive())
            {
                actor.LODTier = -1;
                actor.LODDistance = -1;
                actor.LODAt = -1;
                continue;
            }
            float nearest = HCInfectedLOD.NearestDistance(players, entity.GetPosition());
            actor.LODDistance = nearest;
            actor.LODTier = HCLODPolicy.Tier(nearest, fullRange, idleRange);
            actor.LODAt = now;
        }
        return spent;
    }

    void HCLODCounts(out int full, out int idle, out int far, out int unknown)
    {
        full = 0;
        idle = 0;
        far = 0;
        unknown = 0;
        foreach (HCInfectedActor actor : m_Actors)
        {
            if (!actor.InfectedEntity || !actor.InfectedEntity.IsAlive()) { continue; }
            if (actor.LODTier == HCLODPolicy.TIER_FULL) { full++; }
            if (actor.LODTier == HCLODPolicy.TIER_IDLE) { idle++; }
            if (actor.LODTier == HCLODPolicy.TIER_VIRTUAL) { far++; }
            if (actor.LODTier < 0) { unknown++; }
        }
    }

    int HCLODTracked()
    {
        if (!m_Healthy) { return 0; }
        HCLODPrune();
        return m_Actors.Count();
    }

    // Leases leave four tracked slots for CE infected.
    int HCLODTrackCap()
    {
        if (!m_Healthy || !m_Config) { return 0; }
        return Math.Max(0, Math.Min(m_Config.MaxTracked, m_MemberCap) - 4);
    }

    // Mirrors HCAdminSitter (Admin/HCAdminDirectors.c): same caps, flags,
    // cast and tracking contract; deletes only a body it just created.
    ZombieBase HCLODMaterialize(string type, vector pos)
    {
        if (!m_Healthy || !m_Config || !m_State) { return null; }
        HCLODPrune();
        if (m_Actors.Count() >= Math.Min(m_Config.MaxTracked, m_MemberCap) || m_RegistrationAttempts >= m_WorkCap) { return null; }
        Object body = GetGame().CreateObjectEx(type, pos, ECE_INITAI | ECE_PLACE_ON_SURFACE);
        ZombieBase infected = ZombieBase.Cast(body);
        if (!infected)
        {
            if (body) { GetGame().ObjectDelete(body); }
            return null;
        }
        if (!FindActor(infected) && !Track(infected)) { GetGame().ObjectDelete(body); return null; }
        return infected;
    }

    // A body a horde/search adopted belongs to that system now.
    bool HCLODClaimed(ZombieBase body)
    {
        HCInfectedActor actor = FindActor(body);
        if (!actor) { return false; }
        return actor.GroupId != 0 || actor.SearchPack != null || actor.EverAssigned;
    }

    // Experiment 1 subject: alive, calm, unclaimed, standing, near a player;
    // the admin sitter first. <=24 actors x <=64 players.
    ZombieBase HCLODProbeSubject(array<Man> players, float range)
    {
        if (!m_Healthy) { return null; }
        ZombieBase fallback;
        foreach (HCInfectedActor actor : m_Actors)
        {
            ZombieBase entity = actor.InfectedEntity;
            if (!entity || !entity.IsAlive() || entity.IsCrawling()) { continue; }
            if (actor.GroupId != 0 || actor.SearchPack || actor.EverAssigned) { continue; }
            if (entity.GetMindStateSynced() != DayZInfectedConstants.MINDSTATE_CALM) { continue; }
            float nearest = HCInfectedLOD.NearestDistance(players, entity.GetPosition());
            if (nearest < 0 || nearest > range) { continue; }
            if (entity.IsKindOf("HC_ZmbM_Sitter")) { return entity; }
            if (!fallback) { fallback = entity; }
        }
        return fallback;
    }

    // <=24 tracked actor points on the "infected-lod" layer.
    void HCLODDescribe(HCDebugSnapshot snapshot)
    {
        int points = 0;
        foreach (HCInfectedActor actor : m_Actors)
        {
            if (points >= 24) { break; }
            ZombieBase entity = actor.InfectedEntity;
            if (!entity || !entity.IsAlive()) { continue; }
            points++;
            string tier = "unknown";
            if (actor.LODTier == HCLODPolicy.TIER_FULL) { tier = "full"; }
            if (actor.LODTier == HCLODPolicy.TIER_IDLE) { tier = "idle"; }
            if (actor.LODTier == HCLODPolicy.TIER_VIRTUAL) { tier = "virtual"; }
            snapshot.AddPoint("infected-lod", "actor-" + points.ToString(), entity.GetPosition(), "LOD " + tier, "nearest=" + Math.Round(actor.LODDistance).ToString() + " runtime=PENDING");
        }
    }
}

class HCInfectedLODModule : HCModule
{
    protected static HCInfectedLODModule s_Instance;
    protected bool m_Running;
    protected bool m_Herds;
    protected ref HCInfectedLODConfig m_Config;
    protected ref HCInfectedLODStore m_Store;
    protected ref array<ref HCLODLease> m_Leases;
    protected ref HCInfectedLODExperiment m_Experiment;
    protected ref HCInfectedLODContributor m_Debug;
    protected int m_HerdCursor;
    protected int m_LeaseCursor;
    protected bool m_FoldTurn;
    protected float m_StatsAt;
    protected float m_RegrowAt;
    protected int m_Materialized;
    protected int m_Folded;
    protected int m_Released;
    protected int m_Deaths;
    protected int m_Vanished;
    protected int m_RefusedSight;
    protected int m_RefusedPlace;
    protected ref HCLODSightBudget m_Sight;
    protected int m_Rays;
    protected int m_RayPeak;
    protected string m_Refusal;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    static HCInfectedLODModule Get() { return s_Instance; }

    override string GetName() { return "InfectedLOD"; }

    // Wave 16: cached readiness from the live started flag; a faulted herd store is a real degradation.
    override HCOperationalStatus HCGetOperationalStatus()
    {
        string fault = "";
        if (m_Running && m_Store && !m_Store.Healthy()) { fault = "herd_store_unhealthy"; }
        HCModuleReadiness.HCDerive(m_Operational, m_Running, m_Refusal, fault, "lod_config_loaded_tick_running");
        return m_Operational;
    }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableInfected;
    }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings) || m_Running) { return; }
        string reason;
        m_Refusal = "";
        m_Config = HCInfectedLODConfig.Load(reason);
        if (!m_Config)
        {
            Print("[HC InfectedLOD] disabled: " + reason + " runtime=PENDING");
            m_Refusal = "lod_config_unavailable";
            return;
        }
        bool lodPreference = m_Config.EnableLOD;
        bool herdPreference = m_Config.EnableVirtualHerds && lodPreference;
        Print(HCV2Admission.Line("InfectedLOD", lodPreference, "W7-135", HCV2Gates.Qualified("W7-135")));
        Print(HCV2Admission.Line("VirtualHerds", herdPreference, "W7-135", HCV2Gates.Qualified("W7-135")));
        if (!HCV2Admission.Admitted(lodPreference))
        {
            reason = "operator_preference_off";
            Print("[HC InfectedLOD] not started: " + reason + " runtime=PENDING");
            m_Refusal = "operator_preference_off";
            m_Config = null;
            return;
        }
        HCInfectedLOD.HCSet(m_Config);
        m_Leases = new array<ref HCLODLease>;
        m_Sight = new HCLODSightBudget;
        string herdNote = "off";
        if (HCV2Admission.Admitted(herdPreference))
        {
            herdNote = "no-seeds";
            if (m_Config.Herds.Count() > 0)
            {
                herdNote = "member-classes-missing";
                if (m_Config.MemberTypes.Count() > 0 || m_Config.DefaultsExist())
                {
                    m_Store = new HCInfectedLODStore;
                    m_Herds = m_Store.Start(m_Config);
                    herdNote = "store-refused";
                    if (m_Herds) { herdNote = "on"; }
                }
            }
        }
        if (m_Herds) { HCLODResume(); }
        m_Experiment = new HCInfectedLODExperiment;
        bool experiment = m_Experiment.HCArm();
        if (settings.EnableDebugSnapshot)
        {
            m_Debug = new HCInfectedLODContributor;
            HCDebugSnapshot.HCRegister(m_Debug);
        }
        m_StatsAt = GetGame().GetTickTime() + 60;
        m_RegrowAt = GetGame().GetTickTime() + 60;
        m_Running = true;
        s_Instance = this;
        string budget = m_Config.PosedBudget.ToString() + "/" + m_Config.PosedFullBudget.ToString() + "/" + m_Config.PosedIdleBudget.ToString();
        Print("[HC InfectedLOD] started tiers full<=" + m_Config.FullRange.ToString() + " idle<=" + m_Config.IdleRange.ToString() + " materialize<=" + m_Config.MaterializeRange.ToString() + " fold>" + m_Config.FoldRange.ToString() + " sight<=" + m_Config.VisibilityRange.ToString() + " classify=" + m_Config.ClassifyPerTick.ToString() + " herds=" + herdNote + " seeds=" + m_Config.Herds.Count().ToString() + " posed_budget=" + budget + " experiment=" + HCV2Admission.OnOff(experiment) + " runtime=PENDING");
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running) { return; }
        HCInfectedModule infected = HCInfectedModule.Instance;
        if (!infected) { return; }
        float now = GetGame().GetTickTime();
        array<Man> players = HCPerfPlayers.HCGet();
        infected.HCLODClassify(players, now, m_Config.ClassifyPerTick, m_Config.FullRange, m_Config.IdleRange);
        HCReached.Mark("infected_lod.classify");
        if (m_Herds && m_Store.Healthy() && HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_LOD_HERD, 1))
        {
            m_Sight.HCReset(m_Config.MaxObservers * HCInfectedLOD.RAYS_PER_OBSERVER);
            HCLODPollLeases(infected, now);
            if (m_FoldTurn) { HCLODFoldStep(infected, players, now); }
            else { HCLODMaterializeStep(infected, players, now); }
            m_Rays += m_Sight.Used;
            m_RayPeak = Math.Max(m_RayPeak, m_Sight.Used);
            m_FoldTurn = !m_FoldTurn;
            if (now >= m_RegrowAt)
            {
                m_RegrowAt = now + 60;
                HCLODRegrow();
            }
        }
        if (m_Experiment) { m_Experiment.HCStep(infected, players, now); }
        if (now >= m_StatsAt)
        {
            m_StatsAt = now + 60;
            HCLODStats(infected, players);
        }
    }

    protected void HCLODResume()
    {
        m_Leases = HCLODStopLeases.HCTake();
        m_LeaseCursor = 0;
    }

    protected HCInfectedLODHerd Herd(string id)
    {
        if (!m_Store) { return null; }
        return m_Store.Find(id);
    }

    // Debits one living head (death or horde release) with a fresh regrow clock.
    protected void Debit(string herdId)
    {
        HCInfectedLODHerd herd = Herd(herdId);
        if (!herd) { return; }
        herd.Alive = Math.Max(0, herd.Alive - 1);
        int nowUtc = m_Store.NowUtc();
        if (nowUtc > 0) { herd.UpdatedUtc = nowUtc; }
        m_Store.MarkDirty();
    }

    protected void RemoveLease(int index)
    {
        m_Leases.RemoveOrdered(index);
        if (m_LeaseCursor > index) { m_LeaseCursor--; }
    }

    // <=MaxMaterialized(<=24) leases: deaths debit, claims release, bodies the
    // engine removed return to data (they no longer exist anywhere).
    protected void HCLODPollLeases(HCInfectedModule infected, float now)
    {
        for (int index = m_Leases.Count() - 1; index >= 0; index--)
        {
            HCLODLease lease = m_Leases[index];
            if (!lease.Body)
            {
                m_Vanished++;
                RemoveLease(index);
                continue;
            }
            if (!lease.Body.IsAlive())
            {
                m_Deaths++;
                Debit(lease.HerdId);
                RemoveLease(index);
                continue;
            }
            if (infected && infected.HCLODClaimed(lease.Body))
            {
                m_Released++;
                Debit(lease.HerdId);
                RemoveLease(index);
            }
        }
    }

    protected int LeasedFor(string herdId)
    {
        int leased = 0;
        foreach (HCLODLease lease : m_Leases)
        {
            if (lease.HerdId == herdId) { leased++; }
        }
        return leased;
    }

    // The only fold deletion: proven unseen, calm and far by the caller.
    protected void HCLODFold(int index, HCInfectedModule infected)
    {
        HCLODLease lease = m_Leases[index];
        ZombieBase body = lease.Body;
        RemoveLease(index);
        if (body) { infected.HCLODRetire(body); GetGame().ObjectDelete(body); }
        m_Folded++;
    }

    // Fold decision for one lease: cheap checks first, rays only when the
    // cheap decision already says FOLD_NOW.
    protected int HCLODFoldDecision(HCInfectedModule infected, array<Man> players, ZombieBase body, float now)
    {
        if (!body) { return HCLODPolicy.FOLD_KEEP; }
        if (body.IsCrawling()) { return HCLODPolicy.FOLD_KEEP; }
        vector pos = body.GetPosition();
        float nearest = HCInfectedLOD.NearestDistance(players, pos);
        bool calm = body.GetMindStateSynced() == DayZInfectedConstants.MINDSTATE_CALM;
        float sinceHit = -1;
        if (body.HCLODHitAt() >= 0) { sinceHit = now - body.HCLODHitAt(); }
        bool claimed = infected.HCLODClaimed(body);
        int decision = HCLODPolicy.FoldDecision(body.IsAlive(), calm, sinceHit, claimed, nearest, m_Config.FoldRange, 0, 0, m_Config.MaxObservers);
        if (decision != HCLODPolicy.FOLD_NOW) { return decision; }
        if (!HCObserverTransitionGate.CanTransition(pos, m_Config.FoldRange)) { return HCLODPolicy.FOLD_KEEP; }
        int observers;
        int occluded;
        HCInfectedLOD.Observers(players, pos, body, m_Config.VisibilityRange, m_Config.MaxObservers, observers, occluded, m_Sight);
        return HCLODPolicy.FoldDecision(body.IsAlive(), calm, sinceHit, claimed, nearest, m_Config.FoldRange, observers, occluded, m_Config.MaxObservers);
    }

    // ONE lease per call, round robin.
    protected void HCLODFoldStep(HCInfectedModule infected, array<Man> players, float now)
    {
        if (m_Leases.Count() == 0) { return; }
        if (m_LeaseCursor >= m_Leases.Count()) { m_LeaseCursor = 0; }
        int index = m_LeaseCursor;
        m_LeaseCursor++;
        HCLODLease lease = m_Leases[index];
        int decision = HCLODFoldDecision(infected, players, lease.Body, now);
        if (decision == HCLODPolicy.FOLD_NOW) { HCLODFold(index, infected); return; }
        bool far = lease.Body && HCInfectedLOD.NearestDistance(players, lease.Body.GetPosition()) > m_Config.FoldRange;
        if (decision == HCLODPolicy.FOLD_KEEP && far) { m_RefusedSight++; }
    }

    // ONE herd and at most ONE body per call.
    protected void HCLODMaterializeStep(HCInfectedModule infected, array<Man> players, float now)
    {
        HCInfectedLODState state = m_Store.State();
        if (!state || state.Herds.Count() == 0) { return; }
        if (m_HerdCursor >= state.Herds.Count()) { m_HerdCursor = 0; }
        HCInfectedLODHerd herd = state.Herds[m_HerdCursor];
        m_HerdCursor++;
        vector centre = Vector(herd.X, GetGame().SurfaceY(herd.X, herd.Z), herd.Z);
        float nearest = HCInfectedLOD.NearestDistance(players, centre);
        float edge = nearest;
        if (nearest >= 0) { edge = Math.Max(0, nearest - herd.Radius); }
        int leasedHerd = LeasedFor(herd.Id);
        int desired = HCLODPolicy.DesiredMembers(herd.Alive, edge, m_Config.MaterializeRange, m_Config.MaxPerHerd);
        if (!HCLODPolicy.MayMaterialize(desired, leasedHerd, m_Leases.Count(), m_Config.MaxMaterialized, infected.HCLODTracked(), infected.HCLODTrackCap())) { return; }
        float angle = Math.RandomFloat01() * Math.PI2;
        float distance = Math.Sqrt(Math.RandomFloat01()) * herd.Radius;
        float x = herd.X + Math.Cos(angle) * distance;
        float z = herd.Z + Math.Sin(angle) * distance;
        vector pos = Vector(x, GetGame().SurfaceY(x, z), z);
        float pointNearest = HCInfectedLOD.NearestDistance(players, pos);
        if (!HCObserverTransitionGate.CanTransition(pos, m_Config.MinSpawnDistance)) { m_RefusedSight++; return; }
        int observers = 0;
        int occluded = 0;
        if (pointNearest > m_Config.MinSpawnDistance) { HCInfectedLOD.Observers(players, pos, null, m_Config.VisibilityRange, m_Config.MaxObservers, observers, occluded, m_Sight); }
        if (!HCLODPolicy.SpawnHidden(pointNearest, m_Config.MinSpawnDistance, observers, occluded, m_Config.MaxObservers)) { m_RefusedSight++; return; }
        if (!HCAdminPlacement.HCClear(pos)) { m_RefusedPlace++; return; }
        string type = m_Config.MemberType(Math.RandomInt(0, m_Config.MemberTypeCount()));
        ZombieBase body = infected.HCLODMaterialize(type, pos);
        if (!body) { m_RefusedPlace++; return; }
        HCLODLease lease = new HCLODLease;
        lease.Body = body;
        lease.HerdId = herd.Id;
        lease.SpawnedAt = now;
        m_Leases.Insert(lease);
        m_Materialized++;
    }

    // <=16 herds per minute; one head per RegrowSeconds while fully virtual.
    protected void HCLODRegrow()
    {
        HCInfectedLODState state = m_Store.State();
        if (!state) { return; }
        int nowUtc = m_Store.NowUtc();
        if (nowUtc < 1) { return; }
        foreach (HCInfectedLODHerd herd : state.Herds)
        {
            float elapsed = nowUtc - herd.UpdatedUtc;
            if (!HCLODPolicy.MayRegrow(herd.Alive, herd.HeadCount, LeasedFor(herd.Id), elapsed, m_Config.RegrowSeconds)) { continue; }
            herd.Alive++;
            herd.UpdatedUtc = nowUtc;
            m_Store.MarkDirty();
        }
    }

    protected void HCLODStats(HCInfectedModule infected, array<Man> players)
    {
        int full;
        int idle;
        int far;
        int unknown;
        infected.HCLODCounts(full, idle, far, unknown);
        int herds = 0;
        int herdAlive = 0;
        if (m_Herds && m_Store.State())
        {
            herds = m_Store.State().Herds.Count();
            foreach (HCInfectedLODHerd herd : m_Store.State().Herds) { herdAlive += herd.Alive; }
        }
        int playerCount = 0;
        if (players) { playerCount = players.Count(); }
        string line = "[HC InfectedLOD] stats tracked=" + infected.HCLODTracked().ToString() + " full=" + full.ToString() + " idle=" + idle.ToString() + " virtual=" + far.ToString() + " unknown=" + unknown.ToString();
        line = line + " herds=" + herds.ToString() + " herd_alive=" + herdAlive.ToString() + " leased=" + m_Leases.Count().ToString();
        line = line + " materialized_per_min=" + m_Materialized.ToString() + " folded_per_min=" + m_Folded.ToString() + " released_per_min=" + m_Released.ToString() + " deaths_per_min=" + m_Deaths.ToString() + " vanished_per_min=" + m_Vanished.ToString();
        line = line + " refused_sight=" + m_RefusedSight.ToString() + " refused_place=" + m_RefusedPlace.ToString() + " players=" + playerCount.ToString() + " runtime=PENDING";
        line = line + " rays_per_min=" + m_Rays.ToString() + " ray_peak=" + m_RayPeak.ToString() + " ray_budget=" + (m_Config.MaxObservers * HCInfectedLOD.RAYS_PER_OBSERVER).ToString();
        Print("" + line);
        m_Rays = 0;
        m_RayPeak = 0;
        m_Materialized = 0;
        m_Folded = 0;
        m_Released = 0;
        m_Deaths = 0;
        m_Vanished = 0;
        m_RefusedSight = 0;
        m_RefusedPlace = 0;
    }

    // <=16 herd centres and <=24 lease bodies on the "infected-lod" layer.
    void HCLODDescribe(HCDebugSnapshot snapshot)
    {
        if (!m_Running) { return; }
        HCInfectedModule infected = HCInfectedModule.Instance;
        if (infected) { infected.HCLODDescribe(snapshot); }
        if (!m_Herds || !m_Store.State()) { return; }
        foreach (HCInfectedLODHerd herd : m_Store.State().Herds)
        {
            vector centre = Vector(herd.X, 0, herd.Z);
            snapshot.AddPoint("infected-lod", "herd-" + herd.Id, centre, "Herd " + herd.Id, "alive=" + herd.Alive.ToString() + "/" + herd.HeadCount.ToString() + " leased=" + LeasedFor(herd.Id).ToString() + " runtime=PENDING");
        }
        int leaseIndex = 0;
        foreach (HCLODLease lease : m_Leases)
        {
            leaseIndex++;
            if (!lease.Body) { continue; }
            snapshot.AddPoint("infected-lod", "lease-" + leaseIndex.ToString(), lease.Body.GetPosition(), "Herd body", "herd=" + lease.HerdId + " runtime=PENDING");
        }
    }

    // Shutdown has no geometry or deletes. Reconcile terminal leases before
    // flushing; living leases stay in Alive and reserve bodies on module resume.
    override void OnStop()
    {
        if (!m_Running) { return; }
        if (m_Experiment) { m_Experiment.HCRestore(); }
        HCInfectedModule infected = HCInfectedModule.Instance;
        if (m_Herds)
        {
            HCLODPollLeases(infected, GetGame().GetTickTime());
            HCLODStopLeases.HCHold(m_Leases);
        }
        if (m_Store) { m_Store.Stop(); }
        if (m_Debug) { HCDebugSnapshot.HCUnregister(m_Debug); }
        m_Debug = null;
        m_Store = null;
        m_Leases = null;
        m_Sight = null;
        m_Experiment = null;
        m_Herds = false;
        m_Running = false;
        HCInfectedLOD.HCSet(null);
        if (s_Instance == this) { s_Instance = null; }
    }
}

class HCInfectedLODContributor : HCDebugContributor
{
    // <=24 actor + 16 herd + 24 lease points; no sampling or geometry here.
    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        HCInfectedLODModule owner = HCInfectedLODModule.Get();
        if (owner) { owner.HCLODDescribe(snapshot); }
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCInfectedLODModule);
    }
}
