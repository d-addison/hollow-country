// W6 #60 / FR-011 / NFR-003: diagnostic measurement, NEVER qualification.
// Native evidence root: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 3_Game/Global/Game.c:449 ConfigGetText, :923 GetObjectsAtPosition (2D radius),
// :931 GetWorld, :934 GetWorldName, :1120 IsServer, :1176 SurfaceY;
// Global/World.c:82 GetWorldSize; Entities/Object.c:287 GetPosition, :305
// GetOrientation, :370 GetCollisionBox, :467 GetType, :642 IsBuilding,
// :873 ModelToWorld, :874 WorldToModel; gameplay.c:636 GetGame.
// Global/DayZPhysics.c:130-141 ray arguments / :199 RaycastRV signature;
// 1_Core/proto/EnDebug.c:140-150 CollisionFlags.NEARESTCONTACT / :96 Print;
// EnSystem.c:397 FileExist (also used by shared HCV2ThreatStore/HCGroupIO);
// EnMath.c:225 AbsFloat, :553 Min, :566 Max; EnString.c:171 ToLower, :240 IndexOf;
// EnMath3D.c:18 Vector; EnConvert.c:3/30/115/138 ToString;
// EnScript.c:380/385/399/407 array Count/Clear/Get/Insert;
// :743/744/750 set Count/Clear/Get.
// Persistence reuses HCV2ThreatStore<T>: bounded temp/backup/copy/readback;
// no native rename exists. Interrupted writes need operator recovery.
//
// IDLE (no marker): reports ready, no scan, buffers, DTO allocation or IO beyond
// the one marker check at start; OnTick returns at once.
// Marker presence is a boot snapshot: adding/removing it takes effect on restart.
// ON: each core tick handles ONE of: a 128m tile query (<=4096 returned objects,
// overflowing tiles stay pending); <=16 cursor objects (<=64 class comparisons each); <=3
// seed columns (<=21 rays); <=4 validation points (<=12 rays + 2 stair rays);
// or one class summary. At most ONE building is active. 25 seed columns and
// 9 validation points/building; native query cost and budgets remain unmeasured.
// Final JSON serialization is once at completion, bounded at 4 MiB / 8192
// instances / 64 classes. No players, entities, inventory, doors or native
// underground state are changed. No new HCV2Admission: Cellars owns that line;
// this separate marker-only diagnostic does not admit a V2 gameplay feature.
//
// Probe box = one enclosed rectangular candidate BELOW an owner-hit floor near
// terrain height, then nine floor/ceiling and
// center-to-point clearance checks. Class box INTERSECTS successful instance
// boxes; never an unsafe hull across rooms. Confidence = accepted / discovered
// instances (zero on incompatible boxes), NOT a calibrated probability.
// Terrain/columnPos and render/geometry model semantics require native review.
// Stairs come only from explicit operator measurements; no guessed anchors.
class HCCellarSampler : HCModule
{
    static const string MARKER = "$profile:HollowCountry/measure-cellars";
    static const string OUTPUT = "$profile:HollowCountry/cellars-measured.json";
    protected ref HCCellarSamplerData m_Data;
    protected ref HCCellarSamplerSaveJob m_SaveJob;
    protected ref HCV2ThreatStore<HCCellarSamplerData> m_Writer = new HCV2ThreatStore<HCCellarSamplerData>;
    protected ref array<Object> m_Objects;
    protected ref array<CargoBase> m_Cargos;
    protected ref set<Object> m_Hits;
    protected Object m_House;
    protected HCCellarSamplerClass m_Row;
    protected ref HCCellarSamplerInstance m_Instance;
    protected vector m_CollisionMin;
    protected vector m_CollisionMax;
    protected vector m_BoxMin;
    protected vector m_BoxMax;
    protected vector m_Contact;
    protected vector m_Normal;
    protected int m_WorldSize;
    protected int m_TileX;
    protected int m_TileZ;
    protected int m_ObjectCursor;
    protected int m_Seed;
    protected int m_Check = -1;
    protected int m_InstanceCount;
    protected int m_Summary;
    protected bool m_QueryLoaded;
    protected int m_SkippedTiles;
    protected bool m_Summarizing;
    protected bool m_Running;
    protected int m_MeasuredClasses;
    protected ref HCUnitBudget m_Units;
    protected ref HCWorkBudget m_Work;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;

    override string GetName() { return "CellarSampler"; }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }

    protected void HCReceipt(string state, string reason)
    {
        m_Status.HCPublish(state, reason);
        int pending = 0;
        if (m_Data && m_Data.Classes) { pending = m_Data.Classes.Count(); }
        string counts = " cellar_measured=" + m_MeasuredClasses.ToString() + " admitted=0 pending=" + pending.ToString();
        string key = " note=";
        if (state != "ready") { key = " refused="; }
        Print("[HC Cellars] HC-31 sampler" + counts + " state=" + state + key + reason + " runtime=PENDING");
    }

    override bool IsEnabled(HCSettings settings)
    {
        // The sampler starts on every server; OnStart snapshots MARKER once.
        // OnTick below is a cheap no-op when that boot snapshot was absent.
        if (!GetGame() || !GetGame().IsServer())
        {
            HCReceipt("off", "not_server");
            return false;
        }
        return true;
    }

    override void OnStart(HCSettings settings)
    {
        if (!FileExist(MARKER))
        {
            HCReceipt("ready", "idle_waiting_for_measure_marker");
            return;
        }
        if (!HCStart()) { HCReceipt("refused", "measurement_input_or_store_invalid"); }
    }

    protected bool HCStart()
    {
        string path = "$mission:hollow-country/cellars/classes.json";
        if (FileExist("$profile:HollowCountry/cellar-classes.json"))
        {
            path = "$profile:HollowCountry/cellar-classes.json";
        }
        if (!HCV2ThreatStore<HCCellarSamplerData>.CanOpen(OUTPUT))
        {
            Print("[HC Cellars] sampler refused: preserve measured JSON, .tmp and .bak; recover store first");
            return false;
        }
        if (!HCGroupJson<HCCellarSamplerData>.Load(path, 32768, m_Data))
        {
            Print("[HC Cellars] sampler refused: missing or invalid authored class list " + path);
            return false;
        }
        string worldName = GetGame().GetWorldName();
        worldName.ToLower();
        if (worldName != "chernarusplus" || m_Data.WorldName != worldName)
        {
            Print("[HC Cellars] sampler refused: ChernarusPlus class list required");
            return false;
        }
        if (m_Data.SchemaVersion != 1 || !m_Data.Classes)
        {
            Print("[HC Cellars] sampler refused: schema/classes invalid");
            return false;
        }
        if (!m_Data.TriggerDefaults) { return false; }
        if (!(m_Data.TriggerDefaults.StairEnvelopePaddingMeters > 0) || m_Data.TriggerDefaults.StairEnvelopePaddingMeters > 64) { return false; }
        if (!(m_Data.TriggerDefaults.BreadcrumbRadiusMeters > 0) || m_Data.TriggerDefaults.BreadcrumbRadiusMeters > 64) { return false; }
        if (m_Data.Classes.Count() < 1 || m_Data.Classes.Count() > 64) { return false; }
        for (int classIndex = 0; classIndex < m_Data.Classes.Count(); classIndex++)
        {
            HCCellarSamplerClass definition = m_Data.Classes[classIndex];
            if (!definition || !definition.Instances) { return false; }
            // Multi-character IndexOf is only trusted on text of at most 1 KB.
            if (definition.BuildingClass.Length() > 1024) { return false; }
            if (definition.BuildingClass.IndexOf("Land_") != 0) { return false; }
            for (int priorIndex = 0; priorIndex < classIndex; priorIndex++)
            {
                if (m_Data.Classes[priorIndex].BuildingClass == definition.BuildingClass) { return false; }
            }
            // Reject result files accidentally used as authored inputs.
            if (definition.Instances.Count() > 0 || definition.SampleCount != 0) { return false; }
            if (definition.StairsMeasured)
            {
                for (int stairAxis = 0; stairAxis < 3; stairAxis++)
                {
                    bool topFinite = definition.StairTop[stairAxis] > -64 && definition.StairTop[stairAxis] < 64;
                    bool bottomFinite = definition.StairBottom[stairAxis] > -64 && definition.StairBottom[stairAxis] < 64;
                    if (!topFinite || !bottomFinite) { return false; }
                }
                if (definition.StairTop[1] - definition.StairBottom[1] < 0.75) { return false; }
            }
        }
        m_WorldSize = GetGame().GetWorld().GetWorldSize();
        if (m_WorldSize < 128 || m_WorldSize > 32768) { return false; }
        m_Data.Complete = false;
        m_Data.HCRestoreDeclaredMethod();
        for (int restoreIndex = 0; restoreIndex < m_Data.Classes.Count(); restoreIndex++) { m_Data.Classes[restoreIndex].HCRestoreDeclaredDefaults(); }
        if (!HCV2ThreatStore<HCCellarSamplerData>.Save(OUTPUT, m_Data, 4194304)) { return false; }
        m_Objects = new array<Object>;
        m_Cargos = new array<CargoBase>;
        m_Hits = new set<Object>;
        m_Units = new HCUnitBudget;
        m_Work = new HCWorkBudget;
        m_Running = true;
        HCReceipt("ready", "measurement_only_native_stair_route_unobserved");
        Print("[HC Cellars] sampler enabled tiles=128m object_budget=16 ray_budget=24 runtime=PENDING");
        return true;
    }

    protected void HCAbort(string reason)
    {
        m_Running = false;
        m_House = null;
        m_Instance = null;
        m_Row = null;
        if (m_Objects) { m_Objects.Clear(); }
        if (m_Cargos) { m_Cargos.Clear(); }
        if (m_Hits) { m_Hits.Clear(); }
        HCReceipt("refused", reason);
        Print("[HC Cellars] sampler aborted: " + reason + "; require complete output without .tmp before generation");
    }

    // Empty results / terrain / foreign objects are never building geometry.
    protected bool HCCastWorld(vector from, vector to)
    {
        m_Hits.Clear();
        int component;
        bool hit = DayZPhysics.RaycastRV(from, to, m_Contact, m_Normal, component, m_Hits, null, null, true, false, ObjIntersectGeom, 0, CollisionFlags.NEARESTCONTACT);
        if (!hit || m_Hits.Count() != 1) { return false; }
        return m_Hits[0] == m_House;
    }

    protected bool HCCastLocal(vector from, vector to)
    {
        return HCCastWorld(m_House.ModelToWorld(from), m_House.ModelToWorld(to));
    }

    protected bool HCClearLocal(vector from, vector to)
    {
        m_Hits.Clear();
        int component;
        bool blocked = DayZPhysics.RaycastRV(m_House.ModelToWorld(from), m_House.ModelToWorld(to), m_Contact, m_Normal, component, m_Hits, null, null, true, false, ObjIntersectGeom, 0, CollisionFlags.NEARESTCONTACT);
        return !blocked;
    }

    protected bool HCVolumeValid(vector low, vector high)
    {
        if (high[0] - low[0] < 1.5 || high[2] - low[2] < 1.5) { return false; }
        return high[1] - low[1] >= 1.6;
    }

    protected bool HCSeedBox(int index)
    {
        int column = index - (index / 5) * 5;
        int rowIndex = index / 5;
        float x = m_CollisionMin[0] + (m_CollisionMax[0] - m_CollisionMin[0]) * (column + 0.5) / 5;
        float z = m_CollisionMin[2] + (m_CollisionMax[2] - m_CollisionMin[2]) * (rowIndex + 0.5) / 5;
        vector columnPos = m_House.ModelToWorld(Vector(x, 0, z));
        float surface = GetGame().SurfaceY(columnPos[0], columnPos[2]);
        // SurfaceY only locates a search band: an owner-hit upward-facing
        // surface supplies the ground-floor columnPos. No inferred floor Y.
        vector from = Vector(columnPos[0], surface + 1.5, columnPos[2]);
        vector to = Vector(columnPos[0], surface - 1, columnPos[2]);
        if (!HCCastWorld(from, to)) { return false; }
        if (m_Normal[1] < 0.85) { return false; }
        float groundFloorY = m_Contact[1];
        from = Vector(columnPos[0], groundFloorY - 0.4, columnPos[2]);
        to = Vector(columnPos[0], groundFloorY - 6, columnPos[2]);
        if (!HCCastWorld(from, to)) { return false; }
        if (m_Normal[1] < 0.85 || groundFloorY - m_Contact[1] < 1.6) { return false; }
        vector floor = m_House.WorldToModel(m_Contact);
        from = m_Contact + "0 0.1 0";
        to = Vector(columnPos[0], groundFloorY + 0.15, columnPos[2]);
        if (!HCCastWorld(from, to)) { return false; }
        if (m_Normal[1] > -0.85) { return false; }
        vector ceiling = m_House.WorldToModel(m_Contact);
        float clearance = ceiling[1] - floor[1];
        if (clearance < 1.9 || clearance > 4.5) { return false; }
        // Include a player's foot origin at the measured floor in the trigger.
        m_BoxMin = Vector(x, floor[1] - 0.1, z);
        m_BoxMax = Vector(x, ceiling[1] - 0.15, z);
        from = Vector(x, floor[1] + 1, z);
        if (!HCCastLocal(from, from + "-24 0 0")) { return false; }
        vector contact = m_House.WorldToModel(m_Contact);
        m_BoxMin[0] = contact[0] + 0.2;
        if (!HCCastLocal(from, from + "24 0 0")) { return false; }
        contact = m_House.WorldToModel(m_Contact);
        m_BoxMax[0] = contact[0] - 0.2;
        if (!HCCastLocal(from, from + "0 0 -24")) { return false; }
        contact = m_House.WorldToModel(m_Contact);
        m_BoxMin[2] = contact[2] + 0.2;
        if (!HCCastLocal(from, from + "0 0 24")) { return false; }
        contact = m_House.WorldToModel(m_Contact);
        m_BoxMax[2] = contact[2] - 0.2;
        return HCVolumeValid(m_BoxMin, m_BoxMax);
    }

    protected bool HCCheckPoint(int index)
    {
        int column = index - (index / 3) * 3;
        int rowIndex = index / 3;
        float x = m_BoxMin[0] + 0.1 + (m_BoxMax[0] - m_BoxMin[0] - 0.2) * column / 2;
        float z = m_BoxMin[2] + 0.1 + (m_BoxMax[2] - m_BoxMin[2] - 0.2) * rowIndex / 2;
        vector from = Vector(x, m_BoxMin[1] + 0.3, z);
        vector to = Vector(x, m_BoxMin[1] - 0.4, z);
        if (!HCCastLocal(from, to)) { return false; }
        vector contact = m_House.WorldToModel(m_Contact);
        if (m_Normal[1] < 0.85 || Math.AbsFloat(contact[1] - (m_BoxMin[1] + 0.1)) > 0.1) { return false; }
        from = Vector(x, m_BoxMax[1] - 0.3, z);
        to = Vector(x, m_BoxMax[1] + 0.4, z);
        if (!HCCastLocal(from, to)) { return false; }
        contact = m_House.WorldToModel(m_Contact);
        if (m_Normal[1] > -0.85 || Math.AbsFloat(contact[1] - (m_BoxMax[1] + 0.15)) > 0.1) { return false; }
        from = (m_BoxMin + m_BoxMax) * 0.5;
        to = Vector(x, from[1], z);
        if (column == 1 && rowIndex == 1) { return true; }
        return HCClearLocal(from, to);
    }

    protected bool HCStairPoint(vector point)
    {
        if (!HCCastLocal(point, point + "0 -1.5 0")) { return false; }
        if (m_Normal[1] < 0.7) { return false; }
        vector floor = m_House.WorldToModel(m_Contact);
        return point[1] - floor[1] >= 0.1;
    }

    protected void HCRecord(bool eligible, string reason)
    {
        // Probe success is geometry evidence only. Check BOTH authored anchors
        // before incrementing acceptance or touching a class box. Never mutate
        // class StairsMeasured because another instance may still fit its anchors.
        m_Instance.GeometryMeasured = eligible;
        if (eligible)
        {
            m_Row.SampleCount = m_Row.SampleCount + 9;
            if (!m_Row.StairsMeasured)
            {
                eligible = false;
                reason = "stair_anchors_unmeasured";
            }
            else
            {
                bool anchors = HCStairPoint(m_Row.StairTop);
                if (anchors) { anchors = HCStairPoint(m_Row.StairBottom); }
                m_Instance.StairAnchorsValid = anchors;
                if (!anchors)
                {
                    eligible = false;
                    reason = "stair_anchor_probe_failed";
                }
                else { reason = "native_stair_route_unobserved"; }
            }
        }
        m_Instance.Eligible = eligible;
        m_Instance.Reason = reason;
        if (eligible)
        {
            if (m_Row.AcceptedInstances == 0)
            {
                m_Row.BoxMin = m_BoxMin;
                m_Row.BoxMax = m_BoxMax;
            }
            else
            {
                for (int axis = 0; axis < 3; axis++)
                {
                    m_Row.BoxMin[axis] = Math.Max(m_Row.BoxMin[axis], m_BoxMin[axis]);
                    m_Row.BoxMax[axis] = Math.Min(m_Row.BoxMax[axis], m_BoxMax[axis]);
                }
                if (!HCVolumeValid(m_Row.BoxMin, m_Row.BoxMax)) { m_Row.Inconsistent = true; }
            }
            m_Row.AcceptedInstances = m_Row.AcceptedInstances + 1;
        }
        m_House = null;
        m_Instance = null;
        m_Row = null;
    }

    protected void HCProbeTick()
    {
        if (m_Check >= 0)
        {
            for (int checkWork = 0; checkWork < 4; checkWork++)
            {
                if (!m_Work.HCContinue() || !m_Units.HCTake(5)) { return; }
                if (!HCCheckPoint(m_Check)) { m_Check = -1; return; }
                m_Check = m_Check + 1;
                if (m_Check == 9) { HCRecord(true, "nine-point rectangular candidate; runtime pending"); return; }
            }
            return;
        }
        for (int seedWork = 0; seedWork < 3; seedWork++)
        {
            if (!m_Work.HCContinue() || !m_Units.HCTake(7)) { return; }
            if (m_Seed >= 25) { HCRecord(false, "no validated below-ground-floor rectangular volume"); return; }
            bool found = HCSeedBox(m_Seed);
            m_Seed = m_Seed + 1;
            if (found) { m_Check = 0; return; }
        }
    }

    protected void HCBeginHouse(Object candidate, HCCellarSamplerClass definition)
    {
        if (m_InstanceCount >= 8192) { HCAbort("8192 instance cap reached"); return; }
        m_InstanceCount = m_InstanceCount + 1;
        m_House = candidate;
        m_Row = definition;
        m_Instance = new HCCellarSamplerInstance;
        m_Instance.Position = candidate.GetPosition();
        vector orientation = candidate.GetOrientation();
        m_Instance.Yaw = orientation[0];
        m_Row.Instances.Insert(m_Instance);
        if (Math.AbsFloat(orientation[1]) > 0.1 || Math.AbsFloat(orientation[2]) > 0.1)
        {
            HCRecord(false, "tilted building: yaw-only generator refused");
            return;
        }
        string model;
        GetGame().ConfigGetText("CfgVehicles " + definition.BuildingClass + " model", model);
        if (model == "" || model != definition.Model) { HCRecord(false, "model/config mismatch"); return; }
        vector bounds[2];
        if (!candidate.GetCollisionBox(bounds)) { HCRecord(false, "no collision bounds"); return; }
        m_CollisionMin = bounds[0];
        m_CollisionMax = bounds[1];
        for (int axis = 0; axis < 3; axis++)
        {
            if (Math.AbsFloat(m_CollisionMin[axis]) > 64 || Math.AbsFloat(m_CollisionMax[axis]) > 64)
            {
                HCRecord(false, "collision bounds outside 64m budget");
                return;
            }
            if (m_CollisionMax[axis] <= m_CollisionMin[axis]) { HCRecord(false, "invalid collision bounds"); return; }
        }
        m_Seed = 0;
        m_Check = -1;
    }

    protected void HCSummaryTick()
    {
        if (m_Summary < m_Data.Classes.Count())
        {
            HCCellarSamplerClass summary = m_Data.Classes[m_Summary];
            m_Summary = m_Summary + 1;
            if (summary.Instances.Count() > 0 && !summary.Inconsistent)
            {
                summary.Confidence = summary.AcceptedInstances / (summary.Instances.Count() * 1.0);
            }
            summary.Disposition = "pending";
            summary.Reason = "native_survey_pending";
            if (summary.SampleCount > 0)
            {
                m_MeasuredClasses = m_MeasuredClasses + 1;
                summary.Reason = "native_stair_route_unobserved";
            }
            if (summary.Inconsistent)
            {
                summary.Disposition = "refused";
                summary.Reason = "inconsistent_measured_boxes";
            }
            Print("[HC Plan] HC-31 task=" + summary.SurveyTask + " class=" + summary.BuildingClass + " state=" + summary.Disposition + " refused=" + summary.Reason + " runtime=PENDING");
            Print("[HC Cellars] measured class=" + summary.BuildingClass + " instances=" + summary.Instances.Count().ToString() + " box=" + summary.BoxMin.ToString() + ":" + summary.BoxMax.ToString());
            if (summary.SampleCount > 0) { HCModuleReadiness.HCUse("CellarSampler", "class_measured"); }
            Print("[HC Cellars] score class=" + summary.BuildingClass + " confidence=" + summary.Confidence.ToString() + " samples=" + summary.SampleCount.ToString() + " stairs=" + summary.StairsMeasured.ToString());
            return;
        }
        m_Data.Complete = true;
        m_Data.SkippedTiles = m_SkippedTiles;
        // Immutable completion image: a crash before commit leaves the boot's
        // Complete=false image, or recovery intent. Never report done early.
        m_SaveJob = new HCCellarSamplerSaveJob;
        m_SaveJob.Owner = this;
        HCSaveScheduler.HCRegister(m_SaveJob);
        m_SaveJob.HCDirty = true;
        m_SaveJob.HCUrgent = true;
        m_SaveJob.HCDue = GetGame().GetTickTime();
        m_Running = false;
        m_Objects.Clear();
        m_Cargos.Clear();
        m_Hits.Clear();
        HCReceipt("ready", "measurement_checkpoint_pending");
    }

    int HCStepCompletion()
    {
        int result = m_Writer.SaveStep(OUTPUT, m_Data, 4194304);
        if (result == HCSaveJob.STEP_FAILED) { HCAbort("JSON save/readback failed; preserve .tmp and .bak"); }
        if (result == HCSaveJob.STEP_DONE)
        {
            HCReceipt("ready", "measurement_complete_native_stair_route_unobserved");
            Print("[HC Cellars] sampler done skipped_tiles=" + m_SkippedTiles.ToString());
        }
        return result;
    }

    override void OnTick(float deltaTime)
    {
        HCSaveScheduler.HCPumpFallback(m_SaveJob);
        if (!m_Running) { return; }
        m_Units.HCReset(24);
        m_Work.HCReset(24);
        HCReached.Mark("cellar_sampler.survey_tick");
        if (m_Summarizing)
        {
            if (m_Work.HCContinue() && m_Units.HCTake(24)) { HCSummaryTick(); }
            return;
        }
        if (m_House) { HCProbeTick(); return; }
        if (!m_QueryLoaded)
        {
            if (!m_Work.HCContinue() || !m_Units.HCTake(24)) { return; }
            m_Objects.Clear();
            m_Cargos.Clear();
            vector center = Vector(m_TileX + 64, 0, m_TileZ + 64);
            GetGame().GetObjectsAtPosition(center, 91, m_Objects, m_Cargos);
            if (m_Objects.Count() > 4096 || m_Cargos.Count() > 4096)
            {
                // Skip only this dense tile; one overflowing query must not discard the whole run.
                Print("[HC Cellars] sampler tile skipped: query result overflow at " + m_TileX.ToString() + "," + m_TileZ.ToString());
                m_SkippedTiles = m_SkippedTiles + 1;
                m_Objects.Clear();
                m_Cargos.Clear();
                m_TileX = m_TileX + 128;
                if (m_TileX >= m_WorldSize) { m_TileX = 0; m_TileZ = m_TileZ + 128; }
                if (m_TileZ >= m_WorldSize) { m_Summarizing = true; }
                return;
            }
            m_ObjectCursor = 0;
            m_QueryLoaded = true;
            return;
        }
        for (int objectWork = 0; objectWork < 16; objectWork++)
        {
            if (!m_Work.HCContinue() || !m_Units.HCTake(1)) { return; }
            if (m_ObjectCursor >= m_Objects.Count())
            {
                m_QueryLoaded = false;
                m_TileX = m_TileX + 128;
                if (m_TileX >= m_WorldSize) { m_TileX = 0; m_TileZ = m_TileZ + 128; }
                if (m_TileZ >= m_WorldSize) { m_Summarizing = true; }
                return;
            }
            Object candidate = m_Objects[m_ObjectCursor];
            m_ObjectCursor = m_ObjectCursor + 1;
            if (!candidate || !candidate.IsBuilding()) { continue; }
            vector position = candidate.GetPosition();
            // Half-open origin ownership avoids duplicates across overlapping queries.
            if (position[0] < m_TileX || position[0] >= m_TileX + 128) { continue; }
            if (position[2] < m_TileZ || position[2] >= m_TileZ + 128) { continue; }
            string typeName = candidate.GetType();
            for (int classIndex = 0; classIndex < m_Data.Classes.Count(); classIndex++)
            {
                HCCellarSamplerClass definition = m_Data.Classes[classIndex];
                if (typeName != definition.BuildingClass) { continue; }
                HCBeginHouse(candidate, definition);
                return;
            }
        }
    }

    override void OnStop()
    {
        if (m_SaveJob)
        {
            HCSaveScheduler.HCFlush(m_SaveJob);
            HCSaveScheduler.HCUnregister(m_SaveJob);
            m_SaveJob.Owner = null;
            m_SaveJob = null;
        }
        if (m_Running) { HCAbort("mission stopped before completion"); }
        m_House = null;
        m_Instance = null;
        m_Row = null;
        m_Data = null;
        m_Objects = null;
        m_Cargos = null;
        m_Hits = null;
        m_Units = null;
        m_Work = null;
        m_WorldSize = 0;
        m_TileX = 0;
        m_TileZ = 0;
        m_ObjectCursor = 0;
        m_Seed = 0;
        m_Check = -1;
        m_InstanceCount = 0;
        m_Summary = 0;
        m_QueryLoaded = false;
        m_SkippedTiles = 0;
        m_Summarizing = false;
        m_MeasuredClasses = 0;
        m_Status.HCPublish("off", "sampler_stopped");
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCCellarSampler);
    }
}

class HCCellarSamplerSaveJob : HCSaveJob
{
    HCCellarSampler Owner;
    override string HCName() { return "CellarSampler"; }
    override int HCStep()
    {
        if (!Owner) { return STEP_FAILED; }
        return Owner.HCStepCompletion();
    }
}
