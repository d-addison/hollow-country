// #226 spec: autumn-only local leaves at a real deciduous canopy; runtime=PENDING.
// Plan/tasks: reuse HC-27 owner and HC-51 snapshot; bounded query, one emitter,
// stop then drain, opt-outs and lifecycle cleanup; native/two-client checks pending.
// Native evidence, installed scripts-1.30.164289 (relative paths):
// 3_Game/gameplay.c:636 GetGame; Global/Game.c:287 GetProfileString,
// :909 GetTickTime, :930 GetObjectsAtPosition3D, :944 GetPlayer,
// :1125 IsDedicatedServer; Entities/Object.c:287 GetPosition, :370
// GetCollisionBox, :467 GetType, :517 IsAlive, :595 IsTree;
// Entities/Man.c:37 IsSoundInsideBuilding;
// 4_World/Entities/ManBase/PlayerBase.c:2848 GetUndergroundPresence,
// :3925 IsUnconscious; 3_Game/PPEManager/PPERequesterBank.c:236 IsRequesterRunning,
// :42 REQ_UNDERGROUND; 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/Particles/ParticleList.c:399 TREE_FALLING_LEAF;
// Particles/Particle.c:158 PlayOnObject, :245 StopParticle (detaches),
// :340 GetParticleCount, :500-536 native deferred deletion;
// 1_Core/proto/EnConvert.c:210 vector.DistanceSq; EnMath3D.c:18 Vector;
// EnString.c:171 ToLower, :286 Contains; EnScript.c:380 Count, :94 Cast;
// EnDebug.c:96 Print (all three under 1_Core/proto).
// Native 4_World/Entities/WoodBase/Trees.c:3-34, :139-159 Betula/Fagus
// naming identifies a conservative deciduous subset. No copied assets.
// Collision-box upper fraction is provisional canopy placement, not asset proof.
class auditleaves_Client
{
    protected ref auditleaves_Config m_Config;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected Particle m_Emitter;
    protected bool m_Enabled;
    protected bool m_Draining;
    protected bool m_FirstStarted;
    protected float m_Elapsed;
    protected float m_NextQuery;
    protected float m_StopAt;
    protected float m_LastNow;
    protected string m_LastState;
    protected string m_LastReason;
    // Native EnScript.c:385 Clear, :846 map, :877 Find, :902 Set.
    // Query arrays are reused but release object references after each query.
    protected ref array<Object> m_Nearby = new array<Object>;
    protected ref array<CargoBase> m_Cargos = new array<CargoBase>;
    protected ref map<string, bool> m_Deciduous = new map<string, bool>;

    HCOperationalStatus HCGetOperationalStatus() { return m_Status; }

    void HCStart()
    {
        m_Config = auditleaves_Config.HCLoad();
        m_Enabled = m_Config.Enabled;
        if (FileExist("$profile:HollowCountry/acceptance/season_leaves.disable")) { m_Enabled = false; }
        // Exact local preference, same native profile pattern as HC-27.
        string saved;
        if (GetGame().GetProfileString("HollowCountrySeasonLeaves", saved) && saved == "0") { m_Enabled = false; }
        Print(HCV2Admission.Line("SeasonLeaves", m_Enabled, "HC-226", false) + " runtime=PENDING");
        HCReport("off", "awaiting_autumn_viewer");
    }

    static bool HCDeciduous(string name)
    {
        name.ToLower();
        return name.Contains("betulapendula") || name.Contains("fagussylvatica");
    }

    protected bool HCCachedDeciduous(string name)
    {
        bool deciduous;
        if (m_Deciduous.Find(name, deciduous)) { return deciduous; }
        deciduous = HCDeciduous(name);
        // Bound retained class names even on maps with many tree variants.
        // Eviction only repeats classification; it cannot change eligibility.
        if (m_Deciduous.Count() >= 256) { m_Deciduous.Clear(); }
        m_Deciduous.Set(name, deciduous);
        return deciduous;
    }

    protected bool HCEligible(bool grade)
    {
        if (!grade || HCSeasonVisualClient.HCGetPhase() != "autumn") { return false; }
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (!viewer || !viewer.IsAlive() || viewer.IsUnconscious()) { return false; }
        if (viewer.IsSoundInsideBuilding() || viewer.GetUndergroundPresence() != EUndergroundPresence.NONE) { return false; }
        if (HCCellarsClient.HCVisualActive() || PPERequesterBank.IsRequesterRunning(PPERequesterBank.REQ_UNDERGROUND)) { return false; }
        return true;
    }

    void HCUpdate(float delta, bool grade)
    {
        if (!m_Config || (!m_Enabled && !m_Emitter)) { return; }
        if (!(delta > 0) || !(delta <= 2000000000)) { return; }
        m_Elapsed = m_Elapsed + delta;
        if (m_Elapsed < m_Config.SampleSeconds) { return; }
        m_Elapsed = 0;
        HCStep(GetGame().GetTickTime(), HCEligible(grade));
    }

    // Pure lifecycle decisions use explicit native-port inputs in offline tests.
    void HCStep(float now, bool eligible)
    {
        HCDrain();
        if (!(now >= m_LastNow) || !(now <= 2000000000))
        {
            HCStopEmitter();
            HCRefuse("clock_discontinuity");
            return;
        }
        m_LastNow = now;
        if (!m_Enabled || !eligible)
        {
            HCStopEmitter();
            m_NextQuery = now + m_Config.QuerySeconds;
            HCReport("off", "preference_or_viewer_or_snapshot");
            return;
        }
        if (m_Emitter && !m_Draining && now >= m_StopAt) { HCStopEmitter(); }
        if (m_Emitter || m_Draining) { return; }
        HCReport("off", "awaiting_query");
        if (now < m_NextQuery) { return; }
        m_NextQuery = now + m_Config.QuerySeconds;
        HCFindAndStart(now);
    }

    protected void HCStopEmitter()
    {
        if (!m_Emitter || m_Draining) { return; }
        m_Emitter.StopParticle();
        m_Draining = true;
        HCReport("off", "emitter_draining");
    }

    protected void HCDrain()
    {
        if (!m_Draining) { return; }
        if (m_Emitter && m_Emitter.GetParticleCount() != 0) { return; }
        m_Emitter = null;
        m_Draining = false;
    }

    protected void HCFindAndStart(float now)
    {
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (!viewer) { return; }
        array<Object> nearby = m_Nearby;
        array<CargoBase> cargos = m_Cargos;
        nearby.Clear();
        cargos.Clear();
        vector origin = viewer.GetPosition();
        // Native query has a spatial bound, no API result-count limit. Script
        // inspects at most MaxObjects and clears both result arrays this call.
        GetGame().GetObjectsAtPosition3D(origin, m_Config.QueryRadius, nearby, cargos);
        m_Units.HCReset(m_Config.MaxObjects);
        m_Work.HCReset(m_Config.MaxObjects);
        int index = 0;
        Object selected;
        float nearest = m_Config.QueryRadius * m_Config.QueryRadius;
        while (index < nearby.Count() && m_Units.HCTake(1) && m_Work.HCContinue())
        {
            Object candidate = nearby[index];
            index = index + 1;
            if (!candidate || !candidate.IsTree() || !HCCachedDeciduous(candidate.GetType())) { continue; }
            float distance = vector.DistanceSq(origin, candidate.GetPosition());
            if (distance < nearest) { selected = candidate; nearest = distance; }
        }
        nearby.Clear();
        cargos.Clear();
        if (!selected) { HCReport("off", "no_nearby_deciduous_tree"); return; }
        vector bounds[2];
        if (!selected.GetCollisionBox(bounds)) { HCRefuse("tree_bounds_unavailable"); return; }
        float height = bounds[1][1] - bounds[0][1];
        if (!(height >= m_Config.MinTreeHeight) || !(height <= m_Config.MaxTreeHeight)) { HCRefuse("tree_bounds_range"); return; }
        vector canopy = Vector(0, bounds[0][1] + height * m_Config.CanopyFraction, 0);
        m_Emitter = Particle.PlayOnObject(ParticleList.TREE_FALLING_LEAF, selected, canopy);
        if (!m_Emitter) { HCRefuse("particle_start_failed"); return; }
        m_StopAt = now + m_Config.LifetimeSeconds;
        HCReport("ready", "emitter_active");
        if (!m_FirstStarted)
        {
            m_FirstStarted = true;
            Print("[HC Leaves] HC_LEAVES_FIRST_EMITTER tree=" + selected.GetType() + " runtime=PENDING");
        }
    }

    protected void HCRefuse(string reason) { HCReport("refused", reason); }

    protected void HCReport(string state, string reason)
    {
        m_Status.HCPublish(state, reason);
        if (state == m_LastState && reason == m_LastReason) { return; }
        m_LastState = state;
        m_LastReason = reason;
        Print("[HC Leaves] state=" + state + " reason=" + reason + " runtime=PENDING");
    }

    int HCHandleCount()
    {
        if (m_Emitter) { return 1; }
        return 0;
    }

    void HCStop()
    {
        m_Enabled = false;
        HCStopEmitter();
        HCReport("off", "mission_stop");
        // Native particle lifecycle drains/deletes; no replacement on this owner.
    }
}

// One owner under existing HC-27 lifecycle. No new timer, RPC or module slot.
// Keep it across GRADE toggles so a draining emitter cannot be replaced early.
modded class HCClientPresentation
{
    protected ref auditleaves_Client m_AuditLeaves;

    override void HCStart()
    {
        super.HCStart();
        if (m_Stopped || m_AuditLeaves) { return; }
        m_AuditLeaves = new auditleaves_Client;
        m_AuditLeaves.HCStart();
    }

    override void HCUpdate(float timeslice, bool allowInput)
    {
        super.HCUpdate(timeslice, allowInput);
        if (!m_AuditLeaves || m_Stopped) { return; }
        bool grade = (m_EffectiveMask & HCClientPresentationSettings.GRADE) != 0;
        m_AuditLeaves.HCUpdate(timeslice, grade);
    }

    override int HCHandleCount()
    {
        int count = super.HCHandleCount();
        if (m_AuditLeaves) { count = count + m_AuditLeaves.HCHandleCount(); }
        return count;
    }

    override void HCStop()
    {
        if (m_AuditLeaves) { m_AuditLeaves.HCStop(); }
        super.HCStop();
        m_AuditLeaves = null;
    }
}
