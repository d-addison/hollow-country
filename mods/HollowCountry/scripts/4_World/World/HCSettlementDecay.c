// #299: fixed-schema, process-lifetime telemetry shared by these World owners.
// No gameplay state, persistence, roster or budget reads. At most 32 keys per
// owner; saturating totals, resettable windows, one summary per 600 tick seconds.
// Native APIs: EnString.c:396 Split; EnScript.c array Find/Count/Insert;
// EnDebug.c:96 Print. Caller-supplied refusal tokens pass HCReached.Token.
class HCWorldActivityCounters
{
    protected ref array<string> m_Keys = new array<string>;
    protected ref array<int> m_Window = new array<int>;
    protected ref array<int> m_Total = new array<int>;
    protected float m_Seconds;
    protected string m_LastReason = "none";

    void HCWorldActivityCounters(string keys)
    {
        keys.Split(" ", m_Keys);
        for (int index = 0; index < m_Keys.Count(); index++)
        {
            m_Window.Insert(0);
            m_Total.Insert(0);
        }
    }

    void HCHit(string key)
    {
        int index = m_Keys.Find(key);
        if (index < 0) { return; }
        if (m_Window[index] < 2147483647) { m_Window[index] = m_Window[index] + 1; }
        if (m_Total[index] < 2147483647) { m_Total[index] = m_Total[index] + 1; }
    }

    void HCRefuse(string reason, string detail = "")
    {
        HCHit("refused");
        HCHit(reason);
        m_LastReason = reason;
        if (detail != "") { m_LastReason = detail; }
    }

    bool HCDue(float deltaTime)
    {
        if (!(deltaTime > 0) || deltaTime > 3600) { return false; }
        m_Seconds += deltaTime;
        return m_Seconds >= 600;
    }

    void HCLog(string prefix, string gauges)
    {
        string line = prefix + " activity window_s=" + m_Seconds.ToString() + gauges;
        for (int index = 0; index < m_Keys.Count(); index++)
        {
            line += " " + m_Keys[index] + "_w=" + m_Window[index].ToString();
            line += " " + m_Keys[index] + "_total=" + m_Total[index].ToString();
            m_Window[index] = 0;
        }
        Print(line + " last_reason=" + HCReached.Token(m_LastReason) + " runtime=PENDING");
        m_Seconds = 0;
        m_LastReason = "none";
    }
}

// W5-PERF: <=32 fact references/tick, <=1 town/10s after its history
// cursor completes, <=1 visual candidate (small sphere + static box)/tick,
// <=1 create, routine dirty save/60s.
// Native timing/proximity cache evidence: World/HCWorkBudget.c header.
// #118 settlement decay. Native references in scripts-1.30.164289:
// 3_Game/Global/Game.c:612 ConfigIsExisting, :703 CreateObjectEx, :705
// ObjectDelete, :930 GetObjectsAtPosition3D, :945 GetPlayers, :1176 SurfaceY,
// :1180 SurfaceGetType, :1196/1197 water veto, :934 GetWorldName;
// 3_Game/Entities/Object.c:287 GetPosition, :358 ClippingInfo;
// 3_Game/CE/CentralEconomy.c:9,28,30,31 setup/height/lifetime/no-persistence.
// 1_Core/proto/EnScript.c:380,385,394,407 arrays; EnMath.c:225,553,566
// AbsFloat/Min/Max; EnConvert.c:30,210 int.ToString/vector.DistanceSq;
// EnString.c:171,223,240 ToLower/Hash/IndexOf; EnDebug.c:96 Print.
// EnMath.c:17,331,343 DEG2RAD/Sin/Cos for bounded candidate rings.
// Persistence reuses HCV2ThreatStore: EnSystem.c:397,417,425,443,462,525,
// 528,531 and JsonFileLoader.c:69,85. No native rename exists: retained temp
// intent + verified backup/copy, NOT OS-atomic rename. Interrupted load closes.
// No game assets, loot, door edits or native acceptance evidence are included.
class HCSettlementTown
{
    string Id;
    int LastDay = -1;
    int Ransack = -1;
    int Barricades = -1;
    int Remains = -1;
    int Notices = -1;
}

class HCSettlementState
{
    int Version = -1;
    int Epoch;
    int SavedUtc;
    string WorldName;
    ref array<ref HCSettlementTown> Towns = new array<ref HCSettlementTown>;
}

class HCSettlementDecayStore
{
    static bool HCFieldsPresent(string text)
    {
        if (!HCJsonFields.Has(text, "Version")) { return false; }
        if (!HCJsonFields.Every(text, "LastDay", 3)) { return false; }
        if (!HCJsonFields.Every(text, "Ransack", 3) || !HCJsonFields.Every(text, "Barricades", 3)) { return false; }
        return HCJsonFields.Every(text, "Remains", 3) && HCJsonFields.Every(text, "Notices", 3);
    }

    protected ref HCV2ThreatStore<HCSettlementState> m_Writer = new HCV2ThreatStore<HCSettlementState>;
    static const string PATH = "$profile:HollowCountry/settlement-decay.json";
    bool Save(HCSettlementState state)
    {
        if (!m_Writer.FinishSave()) { return false; }
        return HCV2ThreatStore<HCSettlementState>.Save(PATH, state, 16384);
    }
    bool SaveInFlight() { return m_Writer.SaveInFlight(); }
    // Encode: original files intact; write/read tmp: old primary + intent;
    // backup: old primary/backup + intent; promote/read: new primary + old
    // backup + intent; cleanup: new primary/old backup, original load rules.
    int SaveStep(HCSettlementState state) { return m_Writer.SaveStep(PATH, state, 16384); }

}

// This is an additional distance-only gate for authored waypoint/prop changes,
// NOT a resolution of the diagnostic gate's unknown entity lifecycle provider.
// It never marks spectator/optics/CE ownership evidence known. A full kilometre
// veto remains the default for horde callers; decay scenery uses 300 m.
// Camera qualification stays pending.
modded class HCObserverTransitionGate
{
    static bool V2Quiet(vector from, vector toward, float now, float quiet, out float clearSince, float farDistance = 1200, bool horizontal = false)
    {
        if (!Finite(now) || now < 0 || !HCInfectedStore.ValidPosition(from) || !HCInfectedStore.ValidPosition(toward))
        {
            clearSince = -1;
            return false;
        }
        if (!Finite(farDistance) || farDistance < 300 || farDistance > 1200)
        {
            clearSince = -1;
            return false;
        }
        // A horizontal envelope is conservative across terrain elevation and
        // encloses all settlement candidates; other callers retain 3D distance.
        if (horizontal) { from[1] = 0; toward[1] = 0; }
        float distanceSquared = farDistance * farDistance;
        array<Man> players = HCPerfPlayers.HCGet();
        if (players.Count() > 16) { clearSince = -1; return false; }
        foreach (Man observer : players)
        {
            if (!observer) { clearSince = -1; return false; }
            vector position = observer.GetPosition();
            if (!HCInfectedStore.ValidPosition(position)) { clearSince = -1; return false; }
            if (horizontal) { position[1] = 0; }
            if (vector.DistanceSq(position, from) <= distanceSquared || vector.DistanceSq(position, toward) <= distanceSquared)
            {
                clearSince = -1;
                return false;
            }
        }
        if (clearSince < 0 || clearSince > now) { clearSince = now; }
        return now - clearSince >= quiet;
    }
}

class HCSettlementDecay : HCModule
{
    protected ref HCWorldActivityCounters m_Activity = new HCWorldActivityCounters("rows changed props refused fault world_unavailable budget history_pending visual_cap no_visual quiet_300m_60s quiet_wait candidates exhausted position_or_water surface slope occupied_15m building_standoff occupancy_cap class_missing create_failed bounds");
    protected ref HCSettlementState m_State;
    protected ref HCSettlementDecayStore m_Store;
    protected ref HCWorldData m_Catalog;
    protected ref array<Object> m_Props = new array<Object>;
    protected ref array<int> m_PropSlots = new array<int>;
    static const int VISUAL_CANDIDATES = 24;
    // The post-create bounds admit at most 6 x 3 x 6 m. Its horizontal
    // half-diagonal is sqrt(3*3 + 3*3), rounded up, plus 0.75 m clearance.
    static const float VISUAL_FOOTPRINT_RADIUS = 4.25;
    static const float VISUAL_CLEARANCE = 5.0;
    static const float VISUAL_BUILDING_STANDOFF = 8.0;
    // VISUAL_FOOTPRINT_RADIUS 4.25 + VISUAL_CLEARANCE 5.0 + 1.
    static const float VISUAL_QUERY_RADIUS = 10.25;
    // 2 * (VISUAL_FOOTPRINT_RADIUS 4.25 + VISUAL_BUILDING_STANDOFF 8.0).
    static const float VISUAL_BOX_EDGE = 24.5;
    static const float VISUAL_BOX_HEIGHT = 4.0;
    static const int VISUAL_QUERY_CAP = 64;
    protected int m_MaxQueryTicks;
    // 0.35 / 3 (~6.7 degrees) admits gentle ground without conspicuous tilt
    // or burying a <=6 m decorative prop. Probe both signs of both axes.
    static const float VISUAL_SLOPE_RISE = 0.35;
    protected ref array<int> m_VisualAttempts = new array<int>;
    protected ref array<float> m_Clear = new array<float>;
    protected int m_FactNext;
    protected int m_FactSeverity;
    protected int m_TownNow;
    protected bool m_HistoryPending;
    protected bool m_Fault;
    protected int m_CheckpointRevision;
    protected int m_StateRevision;
    protected ref HCSettlementSaveJob m_SaveJob;
    protected ref HCWorkBudget m_WorkBudget = new HCWorkBudget;
    protected int m_Cursor;
    protected int m_PassTowns;
    protected int m_PassChanged;
    protected int m_PassSaved;
    protected float m_Elapsed;
    protected ref array<string> m_RefusalReasons = new array<string>;
    protected bool m_Started;
    protected bool m_Initialized;
    protected bool m_Existing;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "SettlementDecay"; }
    override int StartupPhase() { return HC_PHASE_FEATURE; }
    override void RegisterUses() { HCModuleReadiness.HCRegisterUse("SettlementDecay", "prop_placed"); }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableWorld; }

    // Store allocation is only a start request; both state and catalogue must finish loading.
    override HCOperationalStatus HCGetOperationalStatus()
    {
        if (m_Fault)
        {
            m_Operational.HCPublish("degraded", "persistence_clock_or_schema_fault");
            return m_Operational;
        }
        if (m_Started && !m_Initialized)
        {
            string pending = "settlement_state_loading";
            if (!HCWorldModule.Get()) { pending = "world_unavailable"; }
            m_Operational.HCPublish("requested", pending);
            return m_Operational;
        }
        HCModuleReadiness.HCDerive(m_Operational, m_Started && m_Initialized, "", "", "settlement_state_catalogue_loaded");
        return m_Operational;
    }

    static int RansackAfter(int prior, int day, int severity)
    {
        int age = 0;
        if (day >= 3) { age = 1; }
        if (day >= 7) { age = 2; }
        if (day >= 14) { age = 3; }
        return Math.Min(3, Math.Max(prior, Math.Max(age, severity)));
    }

    protected void Fail()
    {
        m_Activity.HCHit("fault");
        m_Fault = true;
        Print("[HollowCountry] V2 settlement decay disabled: persistence/clock/schema fault; preserve settlement-decay.json, .tmp and .bak");
    }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("SettlementDecay", true, "EXP-S4", HCV2Gates.Qualified("EXP-S4")));
        m_Store = new HCSettlementDecayStore;
        // Native EnSystem.c:397 FileExist; read once at start, validate epoch
        // after World starts. Repeated ticks never reopen the settlement image.
        if (!HCV2ThreatStore<HCSettlementState>.CanOpen(HCSettlementDecayStore.PATH)) { Fail(); return; }
        m_Existing = FileExist(HCSettlementDecayStore.PATH);
        if (m_Existing)
        {
            string image;
            string error;
            if (!HCGroupIO.Read(HCSettlementDecayStore.PATH, 16384, image) || !JsonFileLoader<HCSettlementState>.LoadData(image, m_State, error)) { Fail(); return; }
            if (!HCSettlementDecayStore.HCFieldsPresent(image)) { Fail(); return; }
        }
        m_SaveJob = new HCSettlementSaveJob;
        m_SaveJob.Owner = this;
        HCSaveScheduler.HCRegister(m_SaveJob);
        m_Started = true;
        m_Initialized = false;
    }

    override void OnAllModulesStarted()
    {
        if (!m_Started || m_Fault || m_Initialized) { return; }
        // Resolve World and its epoch after all starts, before the readiness
        // snapshot. Only the fixed authored town catalogue is initialized here;
        // history scans and visual admission remain on the bounded tick.
        HCWorldModule world = HCWorldModule.Get();
        if (!world) { return; }
        int now = HCWorldClock.UTC();
        if (now < world.Epoch() || !Initialize(world, now)) { Fail(); }
    }

    protected bool Valid(HCWorldModule world, int now)
    {
        if (!m_State || m_State.Version != 1 || m_State.Epoch != world.Epoch() || m_State.WorldName != GetGame().GetWorldName()) { return false; }
        if (m_State.SavedUtc < m_State.Epoch || m_State.SavedUtc > now || !m_State.Towns || m_State.Towns.Count() < 1 || m_State.Towns.Count() > m_Catalog.Places.Count()) { return false; }
        for (int townIndex = 0; townIndex < m_State.Towns.Count(); townIndex++)
        {
            HCSettlementTown town = m_State.Towns[townIndex];
            if (!town || town.Id != m_Catalog.Places[townIndex].Id || town.LastDay < -1 || town.LastDay > world.Day()) { return false; }
            if (town.Ransack < 0 || town.Ransack > 3 || town.Barricades < 0 || town.Barricades > 2 || town.Remains < 0 || town.Remains > 1 || town.Notices < 0 || town.Notices > 1) { return false; }
        }
        return true;
    }

    protected bool Initialize(HCWorldModule world, int now)
    {
        m_Catalog = HCWorldData.Fresh(world.Epoch());
        if (m_Existing)
        {
            if (!Valid(world, now)) { return false; }
        }
        else
        {
            m_State = new HCSettlementState;
            m_State.Version = 1;
            m_State.Epoch = world.Epoch();
            m_State.SavedUtc = now;
            m_State.WorldName = GetGame().GetWorldName();
            array<ref HCWorldPlace> initialPlaces = m_Catalog.Places;
            foreach (HCWorldPlace place : initialPlaces)
            {
                HCSettlementTown row = new HCSettlementTown;
                row.Id = place.Id;
                row.Ransack = 0;
                row.Barricades = 0;
                row.Remains = 0;
                row.Notices = 0;
                m_State.Towns.Insert(row);
            }
            HCQueueRoutine();
        }
        // Old stores retain their ordered prefix; only new catalog towns append.
        bool appended = false;
        while (m_State.Towns.Count() < m_Catalog.Places.Count())
        {
            HCSettlementTown appendedTown = new HCSettlementTown;
            appendedTown.Id = m_Catalog.Places[m_State.Towns.Count()].Id;
            appendedTown.Ransack = 0;
            appendedTown.Barricades = 0;
            appendedTown.Remains = 0;
            appendedTown.Notices = 0;
            m_State.Towns.Insert(appendedTown);
            appended = true;
        }
        if (appended) { HCQueueRoutine(); }
        array<ref HCSettlementTown> initializedTowns = m_State.Towns;
        foreach (HCSettlementTown initialized : initializedTowns)
        {
            m_Clear.Insert(-1);
            m_PropSlots.Insert(0);
            m_VisualAttempts.Insert(0);
        }
        m_Initialized = true;
        return true;
    }

    protected void HCQueueRoutine()
    {
        m_StateRevision++;
        m_SaveJob.HCDirty = true;
    }

    bool HCFlushRoutine()
    {
        if (m_Fault || !m_State) { return false; }
        m_SaveJob.HCDirty = true;
        if (!HCSaveScheduler.HCFlush(m_SaveJob)) { Fail(); return false; }
        return true;
    }

    int HCStepRoutine()
    {
        if (m_Fault || !m_State) { return HCSaveJob.STEP_FAILED; }
        if (!m_Store.SaveInFlight()) { m_CheckpointRevision = m_StateRevision; }
        int result = m_Store.SaveStep(m_State);
        if (result == HCSaveJob.STEP_DONE && m_CheckpointRevision != m_StateRevision) { return HCSaveJob.STEP_MORE; }
        if (result == HCSaveJob.STEP_DONE) { m_PassSaved++; }
        if (result == HCSaveJob.STEP_FAILED) { Fail(); }
        return result;
    }

    // A candidate veto consumes one attempt, never the slot until its cap.
    // Reason diagnostics retain boot de-duplication; summaries are <=4/town.
    protected void HCVisualRefused(int index, string reason)
    {
        m_Activity.HCHit(reason);
        if (m_RefusalReasons.Count() < 16 && m_RefusalReasons.Find(reason) < 0)
        {
            m_RefusalReasons.Insert(reason);
            Print("[HollowCountry] V2 settlement visual refused town=" + m_State.Towns[index].Id + " reason=" + reason);
        }
        if (m_VisualAttempts[index] < VISUAL_CANDIDATES) { return; }
        m_Activity.HCRefuse("exhausted", reason);
        string summary = "[HollowCountry] V2 settlement visual exhausted town=" + m_State.Towns[index].Id;
        summary += " slot=" + m_PropSlots[index].ToString() + " candidates=" + m_VisualAttempts[index].ToString();
        Print(summary + " reason=" + reason);
        m_PropSlots[index] = m_PropSlots[index] + 1;
        m_VisualAttempts[index] = 0;
    }

    protected vector HCVisualCandidate(int index, int slot)
    {
        // Hash only the stable town identity; normalize the small remainder to
        // avoid AbsInt overflowing on the minimum signed hash value.
        int heading = m_State.Towns[index].Id.Hash() % 360;
        if (heading < 0) { heading += 360; }
        int attempt = m_VisualAttempts[index];
        float angle = (heading + slot * 97 + attempt * 137) * Math.DEG2RAD;
        // Six rings, four dispersed headings each; the 137-degree stride
        // avoids radial spokes. Try settlement edges before the busy centre.
        // 150, 124, 98, 72, 46, 20 m; all stay inside the 180 m envelope.
        int ring = attempt / 4;
        float radius = 150 - ring * 26;
        vector point = m_Catalog.Places[index].Position;
        point[0] = point[0] + Math.Cos(angle) * radius;
        point[2] = point[2] + Math.Sin(angle) * radius;
        return point;
    }

    protected bool HCVisualSoftSurface(string surface)
    {
        surface.ToLower();
        // Installed DayZ 1.30.164289 addons/surfaces.pbo:config.bin,
        // CfgSurfaces (read with tools.audit.pbo_config): Chernarus terrain
        // soft-ground classes only. Exact allowlist excludes roads, asphalt,
        // concrete, gravel, rock and generic model/interior dirt materials.
        return surface == "cp_dirt" || surface == "cp_grass" || surface == "cp_grass_tall" || surface == "cp_broadleaf_dense1" || surface == "cp_broadleaf_dense2" || surface == "cp_broadleaf_sparse1" || surface == "cp_broadleaf_sparse2" || surface == "cp_conifer_common1" || surface == "cp_conifer_common2" || surface == "cp_conifer_moss1" || surface == "cp_conifer_moss2";
    }

    protected bool HCVisualSurface(vector point)
    {
        // Nine fixed samples span the maximum footprint, not just its centre.
        // Game.c:1180/1183: ground type and a downward trace from above the prop
        // reject hard road/model surfaces over otherwise admissible terrain.
        for (int sample = 0; sample < 9; sample++)
        {
            int column = sample % 3;
            int row = sample / 3;
            float x = point[0] + (column - 1) * 3;
            float z = point[2] + (row - 1) * 3;
            string ground;
            string above;
            GetGame().SurfaceGetType(x, z, ground);
            GetGame().SurfaceGetType3D(x, point[1] + 3, z, above);
            if (!HCVisualSoftSurface(ground) || !HCVisualSoftSurface(above)) { return false; }
        }
        return true;
    }

    protected bool HCVisualClutter(Object obstacle)
    {
        // Object.c:595/613/965/970. EntityAI (items, actors, vehicles) and
        // our own decorative props never receive a terrain clutter exemption.
        if (m_Props.Find(obstacle) >= 0 || obstacle.IsEntityAI()) { return false; }
        return obstacle.IsTree() || obstacle.IsBush() || (obstacle.IsPlainObject() && obstacle.IsScenery());
    }

    protected string HCVisualOccupancy(vector point)
    {
        // At most 24 owned props; refuse before any scenery exemption.
        foreach (Object placed : m_Props)
        {
            if (!placed) { continue; }
            vector placedPosition = placed.GetPosition();
            placedPosition[1] = point[1];
            float placedClearance = VISUAL_FOOTPRINT_RADIUS + VISUAL_CLEARANCE;
            if (vector.DistanceSq(point, placedPosition) <= placedClearance * placedClearance) { return "occupied_15m"; }
        }
        array<Object> nearby = new array<Object>;
        array<CargoBase> cargo = new array<CargoBase>;
        // Game.c:930. Small local broad phase only; no building-origin search
        // and no per-result ClippingInfo. Cap bounds script classification work.
        GetGame().GetObjectsAtPosition3D(point, VISUAL_QUERY_RADIUS, nearby, cargo);
        if (nearby.Count() > VISUAL_QUERY_CAP || cargo.Count() > VISUAL_QUERY_CAP) { return "occupancy_cap"; }
        if (cargo.Count() > 0) { return "occupied_15m"; }
        foreach (Object obstacle : nearby)
        {
            if (!obstacle) { return "occupied_15m"; }
            // Building.Cast includes House and door owners even where a
            // specialized building overrides IsBuilding to false.
            Building building = Building.Cast(obstacle);
            if (building || obstacle.IsBuilding()) { return "building_standoff"; }
            if (HCVisualClutter(obstacle)) { continue; }
            // Legacy counter key retained; now footprint-based, not 15 m.
            // Unknown objects, items, vehicles and all actors remain obstacles.
            return "occupied_15m";
        }
        array<Object> excluded = new array<Object>;
        array<Object> collided = new array<Object>;
        vector boxCentre = point;
        boxCentre[1] = boxCentre[1] + VISUAL_BOX_HEIGHT * 0.5;
        vector boxSize = Vector(VISUAL_BOX_EDGE, VISUAL_BOX_HEIGHT, VISUAL_BOX_EDGE);
        // Game.c:1336-1366: whole edge lengths, centre at half-height so
        // bottom is at ground. Geometry hits catch walls/door owners regardless
        // of building origin; the square conservatively encloses the radial
        // footprint + 8 m standoff. ONLYSTATIC excludes distant actors/items;
        // those are refused by the small sphere above. Both geometry LODs are
        // checked, matching the installed API example, without clipping calls.
        bool hit = GetGame().IsBoxCollidingGeometry(boxCentre, "0 0 0", boxSize, ObjIntersectView, ObjIntersectGeom, excluded, collided, CollisionFlags.ONLYSTATIC);
        if (collided.Count() > VISUAL_QUERY_CAP) { return "occupancy_cap"; }
        if (hit && collided.Count() == 0) { return "occupied_15m"; }
        foreach (Object geometry : collided)
        {
            if (!geometry) { return "occupied_15m"; }
            Building owner = Building.Cast(geometry);
            if (owner || geometry.IsBuilding()) { return "building_standoff"; }
            if (HCVisualClutter(geometry)) { continue; }
            // Non-clutter static geometry (fence, wall, wreck, owned scenery)
            // stays an obstacle. No foreign/orphan prop adoption occurs.
            return "occupied_15m";
        }
        return "";
    }

    protected void Visual(int index, int now)
    {
        if (m_Props.Count() >= 24 || m_PropSlots[index] >= 4) { m_Activity.HCHit("visual_cap"); return; }
        HCSettlementTown town = m_State.Towns[index];
        if (town.Ransack < 1) { m_Activity.HCHit("no_visual"); return; }
        int slot = m_PropSlots[index];
        if (slot == 1 && town.Remains == 0) { m_Activity.HCHit("no_visual"); return; }
        if (slot == 2 && town.Notices == 0) { m_Activity.HCHit("no_visual"); return; }
        if (slot == 3 && town.Barricades == 0) { m_Activity.HCHit("no_visual"); return; }
        vector centre = m_Catalog.Places[index].Position;
        float clearSince = m_Clear[index];
        // All candidates are <=180 m from centre: a 480 m quiet envelope
        // covers their 300 m exclusion for the full 60 s. It can be retained
        // across candidate/slot changes without borrowing another point's wait.
        // UTC day seconds preserve float precision; midnight restarts the wait.
        int dayNow = now - (now / 86400) * 86400;
        bool quiet = HCObserverTransitionGate.V2Quiet(centre, centre, dayNow, 60, clearSince, 480, true);
        m_Clear[index] = clearSince;
        if (!quiet)
        {
            m_Activity.HCHit("quiet_wait");
            m_Activity.HCHit("quiet_300m_60s");
            return;
        }
        // One candidate geometry probe per module tick, <=24 per slot
        // per boot; no orphan or foreign prop is ever adopted.
        vector point = HCVisualCandidate(index, slot);
        m_VisualAttempts[index] = m_VisualAttempts[index] + 1;
        m_Activity.HCHit("candidates");
        point[1] = GetGame().SurfaceY(point[0], point[2]);
        if (!HCWorldLimits.Position(point) || GetGame().SurfaceIsSea(point[0], point[2]) || GetGame().SurfaceIsPond(point[0], point[2])) { HCVisualRefused(index, "position_or_water"); return; }
        if (!HCVisualSurface(point)) { HCVisualRefused(index, "surface"); return; }
        float sx = GetGame().SurfaceY(point[0] + 3, point[2]);
        float sz = GetGame().SurfaceY(point[0], point[2] + 3);
        float nx = GetGame().SurfaceY(point[0] - 3, point[2]);
        float nz = GetGame().SurfaceY(point[0], point[2] - 3);
        if (Math.AbsFloat(sx - point[1]) > VISUAL_SLOPE_RISE || Math.AbsFloat(sz - point[1]) > VISUAL_SLOPE_RISE || Math.AbsFloat(nx - point[1]) > VISUAL_SLOPE_RISE || Math.AbsFloat(nz - point[1]) > VISUAL_SLOPE_RISE) { HCVisualRefused(index, "slope"); return; }
        // EnSystem.c:106 returns raw performance-counter ticks since start.
        // Include both native queries and bounded classification, even refusals.
        int queryStart = TickCount(0);
        string occupied = HCVisualOccupancy(point);
        int queryTicks = TickCount(queryStart);
        m_MaxQueryTicks = Math.Max(m_MaxQueryTicks, queryTicks);
        if (occupied != "") { HCVisualRefused(index, occupied); return; }
        string type = "StaticObj_Garbage_GroundSq_3m_NoLC";
        if (slot == 1) { type = "StaticObj_Furniture_fireplace_grill"; }
        if (slot == 2) { type = "StaticObj_Misc_NoticeBoard1"; }
        if (slot == 3) { type = "StaticObj_Misc_Barricade"; }
        if (!GetGame().ConfigIsExisting("CfgVehicles " + type)) { HCVisualRefused(index, "class_missing"); return; }
        // Decorative static-only classes from the installed vanilla catalog.
        // No ECE_CREATEPHYSICS/UPDATEPATHGRAPH, inventory or CE persistence.
        int flags = ECE_SETUP | ECE_KEEPHEIGHT | ECE_NOLIFETIME | ECE_NOPERSISTENCY_WORLD;
        Object prop = GetGame().CreateObjectEx(type, point, flags);
        if (!prop) { HCVisualRefused(index, "create_failed"); return; }
        vector box[2];
        prop.ClippingInfo(box);
        vector size = box[1] - box[0];
        // Validate the assumed origin-centred footprint too: a small model
        // with offset bounds must not escape the pre-create clearance.
        float extentX = Math.Max(Math.AbsFloat(box[0][0]), Math.AbsFloat(box[1][0]));
        float extentZ = Math.Max(Math.AbsFloat(box[0][2]), Math.AbsFloat(box[1][2]));
        if (extentX > 3 || extentZ > 3)
        {
            GetGame().ObjectDelete(prop);
            HCVisualRefused(index, "bounds");
            return;
        }
        if (!(size[0] > 0 && size[0] <= 6 && size[1] >= 0 && size[1] <= 3 && size[2] > 0 && size[2] <= 6))
        {
            GetGame().ObjectDelete(prop);
            HCVisualRefused(index, "bounds");
            return;
        }
        HCGroundSnap.Snap(prop);
        m_Props.Insert(prop);
        m_PropSlots[index] = m_PropSlots[index] + 1;
        m_VisualAttempts[index] = 0;
        m_Activity.HCHit("props");
        HCModuleReadiness.HCUse("SettlementDecay", "prop_placed");
    }

    override void OnTick(float deltaTime)
    {
        if (m_Activity.HCDue(deltaTime))
        {
            string gauges = " initialized=" + m_Initialized.ToString() + " fault=" + m_Fault.ToString();
            m_Activity.HCLog("[HollowCountry] V2 settlement decay", gauges + " max_query_ticks=" + m_MaxQueryTicks.ToString());
            m_MaxQueryTicks = 0;
        }
        if (m_Fault || !(deltaTime > 0)) { return; }
        m_Elapsed += Math.Min(deltaTime, 60);
        if (!m_HistoryPending && m_Elapsed < 10) { return; }
        HCWorldModule world = HCWorldModule.Get();
        if (!world) { m_Activity.HCHit("world_unavailable"); return; }
        int now = HCWorldClock.UTC();
        if (now < world.Epoch()) { Fail(); return; }
        if (!m_Initialized && !Initialize(world, now)) { Fail(); return; }
        if (m_State.Epoch != world.Epoch() || now < m_State.SavedUtc) { Fail(); return; }
        m_WorkBudget.HCReset(1);
        if (!m_WorkBudget.HCContinue()) { m_Activity.HCHit("budget"); m_WorkBudget.HCDeferred(GetName(), 1); return; }
        int index = m_Cursor;
        HCReached.Mark("settlement_decay.row");
        HCSettlementTown town = m_State.Towns[index];
        if (!m_HistoryPending)
        {
            m_HistoryPending = true;
            m_FactNext = 0;
            m_FactSeverity = 0;
            m_TownNow = now;
        }
        if (now < m_TownNow) { Fail(); return; }
        int sliceSeverity;
        m_FactNext = world.HCScanDamage(town.Id, m_TownNow, m_FactNext, sliceSeverity);
        m_FactSeverity = Math.Max(m_FactSeverity, sliceSeverity);
        if (m_FactNext >= 0) { m_Activity.HCHit("history_pending"); m_WorkBudget.HCDeferred(GetName(), 1); return; }
        m_Activity.HCHit("rows");
        m_HistoryPending = false;
        m_Elapsed = 0;
        m_Cursor = (m_Cursor + 1) % m_State.Towns.Count();
        int changed = 0;
        int before = town.Ransack + town.Barricades + town.Remains + town.Notices;
        town.Ransack = RansackAfter(town.Ransack, HCEscalationClock.Day(), m_FactSeverity);
        if (town.Ransack >= 1) { town.Remains = 1; town.Notices = 1; }
        if (town.Ransack >= 2) { town.Barricades = Math.Max(town.Barricades, 1); }
        if (HCEscalationClock.Pressure("raiders") >= 0.55 && town.Ransack >= 2) { town.Barricades = 2; }
        if (before != town.Ransack + town.Barricades + town.Remains + town.Notices) { changed = 1; m_Activity.HCHit("changed"); }
        if (town.LastDay != world.Day() || changed > 0)
        {
            town.LastDay = world.Day();
            m_State.SavedUtc = now;
            m_StateRevision++;
            m_SaveJob.HCDirty = true;
            if (changed > 0) { Print("[HollowCountry] V2 settlement decay town=" + town.Id + " changed=" + changed.ToString()); }
        }
        m_PassTowns++;
        m_PassChanged += changed;
        if (m_Cursor == 0)
        {
            // Saved counts completed routine checkpoints since the last pass receipt;
            // dirty rows still use the shared scheduler and may finish in the next pass.
            Print("[HollowCountry] V2 settlement decay towns=" + m_PassTowns.ToString() + " changed=" + m_PassChanged.ToString() + " saved=" + m_PassSaved.ToString());
            m_PassTowns = 0;
            m_PassChanged = 0;
            m_PassSaved = 0;
        }
        // No town loop or catch-up: at most one Visual call per module tick.
        Visual(index, now);
    }

    override void OnStop()
    {
        // Native nonpersistent scenery is cleaned with the mission; do not
        // delete visible props during an ordinary observer's session.
        if (m_SaveJob)
        {
            HCSaveScheduler.HCFlush(m_SaveJob);
            HCSaveScheduler.HCUnregister(m_SaveJob);
        }
        m_Started = false;
        m_Initialized = false;
        m_State = null;
    }
}

class HCSettlementSaveJob : HCSaveJob
{
    override string HCName() { return "SettlementDecay"; }
    HCSettlementDecay Owner;
    override int HCStep()
    {
        if (!Owner) { return STEP_FAILED; }
        return Owner.HCStepRoutine();
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCSettlementDecay);
    }
}
