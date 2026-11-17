"""Stage a disposable native interior floor sampler runtime; never launch the engine.

The sampler answers one question per placement: where are the walkable, roofed floor
surfaces of this exact building, in the building's model space. It is an observation
harness. It proves nothing about DayZ behavior until its census has been produced by a
native run and inspected, and it never accepts anything itself.

Stage a fresh runtime (destination must not exist):

    python3 tools/setup/interior_sampler.py --destination /mnt/d/HollowCountryLocal/interior-sampler-001

Staging, confinement and the allowlist are tools/setup/probe_runtime.py (public API only). The
plan kind is "interior-sampler" (plan file interior-sampler-plan.json, profile directory
HCInteriorSampler, output census.json, sentinel complete.txt). The launcher must carry that row
in its fixed per-kind table, and probe_runtime.LAUNCHER_PROBES must list it, before the plan is
accepted; until then the stager refuses to write the plan. Convert the census with
tools/audit/interior_points.py.

Compile shape (observed natively on 1.30.164289 for another generated hook): a statement with
more than 8 binary '+' is "Formula too complex", and a bare int or float joined to a string is
"Incompatible parameter". The generated hook therefore keeps at most 8 '+' per statement and
converts every number through HCProbeInt/HCProbeNum (which use ToString()); lint_sampler_hook
checks both.
"""
import argparse
import json
import math
from pathlib import Path
import re
import sys

try:
    from . import ce_probe as placements_tool  # public placement parsing/selection only
    from . import probe_runtime as rt
except ImportError:  # executed as a script from tools/setup
    import ce_probe as placements_tool
    import probe_runtime as rt

KIND = "interior-sampler"
PLAN_NAME = "interior-sampler-plan.json"
PROFILE_DIRECTORY = "HCInteriorSampler"
OUTPUT_NAME = "census.json"
SENTINEL_NAME = "complete.txt"
LAUNCHER_ROW = (PLAN_NAME, PROFILE_DIRECTORY, OUTPUT_NAME)
MAX_PLUS_PER_STATEMENT = 8

SAMPLE_CLASSES = (
    ("Land_Tenement_Small", "tenement"), ("Land_Tenement_Big", "tenement"),
    ("Land_HouseBlock_2F1", "calibration"), ("Land_Mil_Barracks2", "calibration"),
)
DEFAULT_PER_CLASS = 4
MAX_PER_CLASS = 16
MAX_TARGETS = 64
GRID_STEP = 1.0
LOADER_CHUNK = 40
INTERSECTS = {"geom": "ObjIntersectGeom", "view": "ObjIntersectView", "fire": "ObjIntersectFire",
              "ifire": "ObjIntersectIFire"}

SAMPLE_DELAY_RANGE = (5, 3600)
HIT_LIMIT_RANGE = (1, 64)
STEP_LIMIT_RANGE = (4, 512)
BUILDING_RAY_RANGE = (100, 2000000)
RUN_RAY_RANGE = (100, 20000000)
PATH_LIMIT_RANGE = (0, 20000)
OUTPUT_LIMIT_RANGE = (4096, 50000000)
DEFAULT_SAMPLE_DELAY_S = 75
DEFAULT_HIT_LIMIT = 24
DEFAULT_STEP_LIMIT = 64
DEFAULT_BUILDING_RAY_LIMIT = 150000
DEFAULT_RUN_RAY_LIMIT = 2500000
DEFAULT_PATH_LIMIT = 3000
DEFAULT_OUTPUT_LIMIT = 6000000
DEFAULT_WAIT_MINUTES = 10

# ---------------------------------------------------------------------------
# Generated Enforce hook
# ---------------------------------------------------------------------------

# Tolerances below are PROVISIONAL: nothing has measured the native navmesh, so they are chosen
# tight (a floor cell is only "reached" when the navmesh sits within half a metre of it with no
# building wall between) and reported in the plan so a native run can be judged against them.
HOOK_HEAD = r"""

// Hollow Country DISPOSABLE interior floor sampler; observation only, no gameplay acceptance.
// Target placements are inlined literal data. Server only; runs once per process.
class HCDisposableDiagnosticMission : CustomMission
{
    protected bool m_HCProbeStarted = false;
    protected bool m_HCProbeWriteFailed = false;
    protected bool m_HCProbeRayCapped = false;
    protected bool m_HCProbeOutputCapped = false;
    protected string m_HCProbeQuote = "";
    protected string m_HCProbePath = "$profile:@@PROFILE_DIR@@/@@OUTPUT_NAME@@";
    protected string m_HCProbeSentinel = "$profile:@@PROFILE_DIR@@/@@SENTINEL_NAME@@";
    protected string m_HCProbePending = "";
    protected string m_HCProbeBoxSource = "none";
    protected string m_HCProbeReachState = "none";
    protected string m_HCProbeReachDoors = "";
    protected string m_HCProbeReachEntrances = "";
    protected float m_HCProbeGridStep = @@GRID_STEP@@;
    protected float m_HCProbeSnapLimit = 0.5;
    protected float m_HCProbeEndTolerance = 0.5;
    protected float m_HCProbeSeedMargin = 1.0;
    protected float m_HCProbeProjectedMargin = 0.5;
    protected float m_HCProbeWaistHeight = 1.0;
    protected int m_HCProbeHitLimit = @@HIT_LIMIT@@;
    protected int m_HCProbeStepLimit = @@STEP_LIMIT@@;
    protected int m_HCProbeBuildingRayLimit = @@BUILDING_RAY_LIMIT@@;
    protected int m_HCProbeRunRayLimit = @@RUN_RAY_LIMIT@@;
    protected int m_HCProbePathLimit = @@PATH_LIMIT@@;
    protected int m_HCProbeOutputLimit = @@OUTPUT_LIMIT@@;
    protected int m_HCProbeBeginMs = 0;
    protected int m_HCProbeFoundCount = 0;
    protected int m_HCProbeCursor = 0;
    protected int m_HCProbePhase = 0;
    protected int m_HCProbeRow = 0;
    protected int m_HCProbeRows = 0;
    protected int m_HCProbeCols = 0;
    protected int m_HCProbeRunRays = 0;
    protected int m_HCProbeBuildingRays = 0;
    protected int m_HCProbeBuildingPaths = 0;
    protected int m_HCProbeHitsEmitted = 0;
    protected int m_HCProbeOutputChars = 0;
    protected int m_HCProbeStatColumns = 0;
    protected int m_HCProbeStatInterior = 0;
    protected int m_HCProbeStatExterior = 0;
    protected int m_HCProbeStatOther = 0;
    protected int m_HCProbeStatStepCapped = 0;
    protected int m_HCProbeStatFloorCapped = 0;
    protected int m_HCProbeStatRehits = 0;
    protected int m_HCProbeStatClearCapped = 0;
    protected int m_HCProbeRelNone = 0;
    protected int m_HCProbeRelBuilding = 0;
    protected int m_HCProbeRelProxy = 0;
    protected int m_HCProbeRelOther = 0;
    protected int m_HCProbeHitCount = 0;
    protected int m_HCProbeHitRel = 0;
    protected int m_HCProbeSkyResult = 0;
    protected int m_HCProbePathCount = 0;
    protected int m_HCProbeDiagColumns = 0;
    protected float m_HCProbePathGap = 0.0;
    protected float m_HCProbeSkyY = 0.0;
    protected float m_HCProbeAttemptA = 0.0;
    protected float m_HCProbeAttemptB = 0.0;
    protected float m_HCProbeStandoff = 0.0;
    protected string m_HCProbeHitType = "";
    protected string m_HCProbeReachAttempts = "";
    protected string m_HCProbeDiag = "";
    protected ref array<string> m_HCProbeTypeNames = new array<string>;
    protected ref array<int> m_HCProbeTypeCounts = new array<int>;
    protected ref array<string> m_HCProbeClasses = new array<string>;
    protected ref array<string> m_HCProbeRoles = new array<string>;
    protected ref array<vector> m_HCProbePositions = new array<vector>;
    protected ref PGFilter m_HCProbeFilter;
    protected Building m_HCProbeBuilding;
    protected vector m_HCProbeBoxMin;
    protected vector m_HCProbeBoxMax;
    protected vector m_HCProbeHitPos;
    protected vector m_HCProbeHitDir;
    protected vector m_HCProbeSampled;
    protected vector m_HCProbeSeed;
    protected vector m_HCProbeEntrance;
    protected vector m_HCProbeSeedWorld;
    protected vector m_HCProbeSampledModel;

    override void OnInit()
    {
        super.OnInit();
        if (!GetGame() || !GetGame().IsServer() || m_HCProbeStarted)
            return;
        m_HCProbeStarted = true;
        int quoteCode = 34;
        m_HCProbeQuote = quoteCode.AsciiToString();
@@LOADER_CALLS@@
        Print("[HC Interior Sampler] LOADED; targets=" + HCProbeInt(m_HCProbeClasses.Count()));
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCProbeStart, @@START_MS@@, false);
    }

    void HCProbeAdd(string className, string role, float x, float y, float z)
    {
        m_HCProbeClasses.Insert(className);
        m_HCProbeRoles.Insert(role);
        m_HCProbePositions.Insert(Vector(x, y, z));
    }

"""

# No comments and no else inside the methods below: the offline reference transpiler in
# tests/unit/test_interior_sampler.py executes these bodies line by line.
HOOK_TAIL = r"""
    string HCProbeInt(int value)
    {
        return value.ToString();
    }

    string HCProbeNum(float value)
    {
        return value.ToString();
    }

    string HCProbeKey(string name)
    {
        return m_HCProbeQuote + name + m_HCProbeQuote + ":";
    }

    string HCProbeStr(string value)
    {
        string text = value;
        if (text.Length() > 96)
            text = text.Substring(0, 96);
        text.Replace(m_HCProbeQuote, "'");
        return m_HCProbeQuote + text + m_HCProbeQuote;
    }

    string HCProbeBool(bool value)
    {
        if (value)
            return "true";
        return "false";
    }

    string HCProbeVector(vector value)
    {
        return "[" + HCProbeNum(value[0]) + "," + HCProbeNum(value[1]) + "," + HCProbeNum(value[2]) + "]";
    }

    bool HCProbeBoxUsable(vector lo, vector hi)
    {
        int axis = 0;
        for (axis = 0; axis < 3; axis++)
        {
            float extent = hi[axis] - lo[axis];
            if (extent < 0.5)
                return false;
            if (extent > 500.0)
                return false;
        }
        return true;
    }

    int HCProbeCount(float low, float high)
    {
        int count = 0;
        float edge = low + 0.5;
        while (edge < high)
        {
            count = count + 1;
            edge = edge + m_HCProbeGridStep;
        }
        return count;
    }

    bool HCProbeOutsideBox(vector modelPos, float margin)
    {
        if (modelPos[0] < m_HCProbeBoxMin[0] - margin)
            return true;
        if (modelPos[0] > m_HCProbeBoxMax[0] + margin)
            return true;
        if (modelPos[2] < m_HCProbeBoxMin[2] - margin)
            return true;
        if (modelPos[2] > m_HCProbeBoxMax[2] + margin)
            return true;
        return false;
    }

    bool HCProbeTakePath()
    {
        if (m_HCProbeBuildingPaths >= m_HCProbePathLimit)
            return false;
        m_HCProbeBuildingPaths = m_HCProbeBuildingPaths + 1;
        return true;
    }

    void HCProbeClassify(set<Object> found)
    {
        m_HCProbeHitCount = found.Count();
        m_HCProbeHitRel = 0;
        m_HCProbeHitType = "";
        if (m_HCProbeHitCount < 1)
            return;
        m_HCProbeHitType = found.Get(0).GetType();
        m_HCProbeHitRel = 3;
        if (found.Find(m_HCProbeBuilding) != -1)
        {
            m_HCProbeHitRel = 1;
            return;
        }
        int limit = m_HCProbeHitCount;
        if (limit > 4)
            limit = 4;
        int index = 0;
        for (index = 0; index < limit; index++)
        {
            if (found.Get(index).GetParent() == m_HCProbeBuilding)
                m_HCProbeHitRel = 2;
        }
    }

    int HCProbeRay(vector rayFrom, vector rayTo)
    {
        m_HCProbeHitCount = 0;
        m_HCProbeHitRel = 0;
        m_HCProbeHitType = "";
        if (m_HCProbeBuildingRays >= m_HCProbeBuildingRayLimit || m_HCProbeRunRays >= m_HCProbeRunRayLimit)
        {
            m_HCProbeRayCapped = true;
            return -1;
        }
        vector contactPos;
        vector contactDir;
        int contactComponent;
        set<Object> hitObjects = new set<Object>;
        bool hit = DayZPhysics.RaycastRV(rayFrom, rayTo, contactPos, contactDir, contactComponent, hitObjects, null, null, false, false, @@INTERSECT@@);
        m_HCProbeBuildingRays = m_HCProbeBuildingRays + 1;
        m_HCProbeRunRays = m_HCProbeRunRays + 1;
        if (!hit)
            return 0;
        m_HCProbeHitPos = contactPos;
        m_HCProbeHitDir = contactDir;
        HCProbeClassify(hitObjects);
        if (m_HCProbeHitRel == 1)
            return 1;
        return 2;
    }

    float HCProbeClearance(vector surfacePos)
    {
        float startY = surfacePos[1] + 0.05;
        float endY = surfacePos[1] + 6.0;
        float offset = 0.05;
        float hitY = 0.0;
        float gain = 0.0;
        int result = 0;
        int attempt = 0;
        for (attempt = 0; attempt < 16; attempt++)
        {
            if (startY >= endY)
                return -1.0;
            result = HCProbeRay(Vector(surfacePos[0], startY, surfacePos[2]), Vector(surfacePos[0], endY, surfacePos[2]));
            if (result < 1)
                return -1.0;
            hitY = m_HCProbeHitPos[1];
            if (result == 1)
                return hitY - surfacePos[1];
            gain = hitY - startY;
            if (gain < 0.02)
                offset = offset * 2.0;
            if (gain >= 0.02)
                offset = 0.05;
            if (offset > 0.8)
                offset = 0.8;
            startY = hitY + offset;
        }
        m_HCProbeStatClearCapped = m_HCProbeStatClearCapped + 1;
        return -1.0;
    }

    bool HCProbeOpenSky(vector pointPos)
    {
        float endY = pointPos[1] + (m_HCProbeBoxMax[1] - m_HCProbeBoxMin[1]) + 2.0;
        m_HCProbeSkyY = 0.0;
        m_HCProbeSkyResult = HCProbeRay(Vector(pointPos[0], pointPos[1] + 0.05, pointPos[2]), Vector(pointPos[0], endY, pointPos[2]));
        if (m_HCProbeSkyResult == 0)
            return true;
        if (m_HCProbeSkyResult > 0)
        {
            vector skyLocal = m_HCProbeBuilding.CoordToLocal(m_HCProbeHitPos);
            m_HCProbeSkyY = skyLocal[1];
        }
        return false;
    }

    bool HCProbeBlocked(vector fromPos, vector toPos)
    {
        int result = HCProbeRay(fromPos, toPos);
        if (result == 0)
            return false;
        return true;
    }

    void HCProbeHitNote(int rel, string typeName)
    {
        if (rel == 0)
            m_HCProbeRelNone = m_HCProbeRelNone + 1;
        if (rel == 1)
            m_HCProbeRelBuilding = m_HCProbeRelBuilding + 1;
        if (rel == 2)
            m_HCProbeRelProxy = m_HCProbeRelProxy + 1;
        if (rel == 3)
            m_HCProbeRelOther = m_HCProbeRelOther + 1;
        if (rel != 1)
            m_HCProbeStatOther = m_HCProbeStatOther + 1;
        if (rel >= 2)
            HCProbeTypeNote(typeName);
    }

    void HCProbeTypeNote(string typeName)
    {
        int known = -1;
        int index = 0;
        int total = m_HCProbeTypeNames.Count();
        for (index = 0; index < total; index++)
        {
            if (m_HCProbeTypeNames.Get(index) == typeName)
                known = index;
        }
        if (known >= 0)
        {
            m_HCProbeTypeCounts.Set(known, m_HCProbeTypeCounts.Get(known) + 1);
            return;
        }
        if (total < 16)
        {
            m_HCProbeTypeNames.Insert(typeName);
            m_HCProbeTypeCounts.Insert(1);
        }
    }

    string HCProbeTypesText()
    {
        string text = "";
        int index = 0;
        int total = m_HCProbeTypeNames.Count();
        for (index = 0; index < total; index++)
        {
            if (index > 0)
                text = text + ",";
            text = text + "[" + HCProbeStr(m_HCProbeTypeNames.Get(index)) + "," + HCProbeInt(m_HCProbeTypeCounts.Get(index)) + "]";
        }
        return text;
    }

    string HCProbeTraceEntry(int step, int rel, int count, float modelY, float drop, float usedOffset, float dirY, int action, string typeName)
    {
        string entry = "";
        if (step > 1)
            entry = ",";
        entry = entry + "[" + HCProbeInt(step) + "," + HCProbeInt(rel) + "," + HCProbeInt(count) + ",";
        entry = entry + HCProbeNum(modelY) + "," + HCProbeNum(drop) + "," + HCProbeNum(usedOffset) + ",";
        entry = entry + HCProbeNum(dirY) + "," + HCProbeInt(action) + "," + HCProbeStr(typeName) + "]";
        return entry;
    }

    void HCProbeDiagColumn(float localX, float localZ, int steps, int floors, int capKind, string trace)
    {
        if (m_HCProbeDiagColumns >= 3)
            return;
        string capName = "none";
        if (capKind == 1)
            capName = "step";
        if (capKind == 2)
            capName = "floor";
        string text = "";
        if (m_HCProbeDiagColumns > 0)
            text = ",";
        m_HCProbeDiagColumns = m_HCProbeDiagColumns + 1;
        text = text + "{" + HCProbeKey("x") + HCProbeNum(localX) + "," + HCProbeKey("z") + HCProbeNum(localZ) + ",";
        text = text + HCProbeKey("steps") + HCProbeInt(steps) + "," + HCProbeKey("floors") + HCProbeInt(floors) + ",";
        text = text + HCProbeKey("cap") + HCProbeStr(capName) + "," + HCProbeKey("seq") + "[" + trace + "]}";
        m_HCProbeDiag = m_HCProbeDiag + text;
    }

    void HCProbeEmit(string text)
    {
        m_HCProbePending = m_HCProbePending + text;
        m_HCProbeOutputChars = m_HCProbeOutputChars + text.Length();
        if (m_HCProbePending.Length() > 3000)
            HCProbeFlush();
    }

    void HCProbeFlush()
    {
        if (m_HCProbePending.Length() < 1)
            return;
        FileHandle handle = OpenFile(m_HCProbePath, FileMode.APPEND);
        if (!handle)
        {
            m_HCProbeWriteFailed = true;
            Print("[HC Interior Sampler] FAILED cannot append census file");
            return;
        }
        FPrintln(handle, m_HCProbePending);
        CloseFile(handle);
        m_HCProbePending = "";
    }

    void HCProbeHeader(string world, string version)
    {
        m_HCProbeBeginMs = GetGame().GetTime();
        FileHandle handle = OpenFile(m_HCProbePath, FileMode.WRITE);
        if (!handle)
        {
            m_HCProbeWriteFailed = true;
            Print("[HC Interior Sampler] FAILED cannot open census file");
            return;
        }
        string head = "{" + HCProbeKey("schema") + "1," + HCProbeKey("kind") + HCProbeStr("interior-sampler-census") + ",";
        head = head + HCProbeKey("world") + HCProbeStr(world) + "," + HCProbeKey("version") + HCProbeStr(version) + ",";
        head = head + HCProbeKey("placements") + "[";
        FPrintln(handle, head);
        CloseFile(handle);
    }

    bool HCProbeMeshAvailable()
    {
        if (!GetGame().GetWorld())
            return false;
        if (!GetGame().GetWorld().GetAIWorld())
            return false;
        if (!m_HCProbeFilter)
            return false;
        return true;
    }

    bool HCProbeSampleMesh(vector position, float radius)
    {
        vector sampled;
        bool found = GetGame().GetWorld().GetAIWorld().SampleNavmeshPosition(position, radius, m_HCProbeFilter, sampled);
        if (!found)
            return false;
        m_HCProbeSampled = sampled;
        return true;
    }

    int HCProbePath(vector startPos, vector endPos, vector goalPos)
    {
        m_HCProbePathCount = 0;
        m_HCProbePathGap = 0.0;
        TVectorArray waypoints = new TVectorArray;
        bool found = GetGame().GetWorld().GetAIWorld().FindPath(startPos, endPos, m_HCProbeFilter, waypoints);
        if (!found)
            return 1;
        m_HCProbePathCount = waypoints.Count();
        if (waypoints.Count() < 2)
            return 2;
        vector finalPoint = waypoints.Get(waypoints.Count() - 1);
        m_HCProbePathGap = vector.Distance(finalPoint, goalPos);
        if (m_HCProbePathGap > m_HCProbeEndTolerance)
            return 3;
        float gapX = goalPos[0] - finalPoint[0];
        float gapZ = goalPos[2] - finalPoint[2];
        if (gapX * gapX + gapZ * gapZ > 0.000001)
        {
            float waistY = goalPos[1] + m_HCProbeWaistHeight;
            if (HCProbeBlocked(Vector(finalPoint[0], waistY, finalPoint[2]), Vector(goalPos[0], waistY, goalPos[2])))
                return 4;
        }
        return 5;
    }

    bool HCProbeSeedOutside(vector doorPos, float unitX, float unitZ)
    {
        float standoff = 2.0;
        int attempt = 0;
        for (attempt = 0; attempt < 30; attempt++)
        {
            m_HCProbeSeed = Vector(doorPos[0] + unitX * standoff, 0.0, doorPos[2] + unitZ * standoff);
            if (HCProbeOutsideBox(m_HCProbeSeed, m_HCProbeSeedMargin))
            {
                vector seedWorld = m_HCProbeBuilding.CoordToParent(m_HCProbeSeed);
                float ground = GetGame().SurfaceY(seedWorld[0], seedWorld[2]);
                m_HCProbeSeedWorld = Vector(seedWorld[0], ground, seedWorld[2]);
                m_HCProbeSeed = m_HCProbeBuilding.CoordToLocal(m_HCProbeSeedWorld);
                m_HCProbeStandoff = standoff;
                return true;
            }
            standoff = standoff;
        }
        return false;
    }

    int HCProbeReachAttempt(vector doorPos, float dirX, float dirZ)
    {
        m_HCProbeAttemptA = 0.0;
        m_HCProbeAttemptB = 0.0;
        m_HCProbeStandoff = 0.0;
        m_HCProbeSeed = Vector(0.0, 0.0, 0.0);
        m_HCProbeSampledModel = Vector(0.0, 0.0, 0.0);
        float dirLength = Math.Sqrt(dirX * dirX + dirZ * dirZ);
        if (dirLength < 0.1)
            return 1;
        float unitX = dirX / dirLength;
        float unitZ = dirZ / dirLength;
        if (!HCProbeSeedOutside(doorPos, unitX, unitZ))
            return 2;
        if (!HCProbeTakePath())
            return 3;
        if (!HCProbeSampleMesh(m_HCProbeSeedWorld, 1.5))
            return 4;
        vector entranceSampled = m_HCProbeSampled;
        m_HCProbeSampledModel = m_HCProbeBuilding.CoordToLocal(entranceSampled);
        if (!HCProbeOutsideBox(m_HCProbeSampledModel, m_HCProbeProjectedMargin))
        {
            m_HCProbeAttemptB = vector.Distance(entranceSampled, m_HCProbeSeedWorld);
            return 5;
        }
        if (!HCProbeOpenSky(entranceSampled))
        {
            m_HCProbeAttemptA = m_HCProbeSkyResult;
            m_HCProbeAttemptB = m_HCProbeSkyY;
            return 6;
        }
        vector farModel = Vector(m_HCProbeSeed[0] + unitX * 10.0, m_HCProbeSeed[1], m_HCProbeSeed[2] + unitZ * 10.0);
        vector farWorld = m_HCProbeBuilding.CoordToParent(farModel);
        float farGround = GetGame().SurfaceY(farWorld[0], farWorld[2]);
        if (!HCProbeSampleMesh(Vector(farWorld[0], farGround, farWorld[2]), 1.5))
            return 7;
        vector farSampled = m_HCProbeSampled;
        int stage = HCProbePath(entranceSampled, farSampled, farSampled);
        m_HCProbeAttemptA = m_HCProbePathCount;
        m_HCProbeAttemptB = m_HCProbePathGap;
        if (stage != 5)
            return 7 + stage;
        m_HCProbeEntrance = entranceSampled;
        return 12;
    }

    void HCProbeReachNote(int door, int stage)
    {
        string entry = "[" + HCProbeInt(door) + "," + HCProbeNum(m_HCProbeStandoff) + "," + HCProbeInt(stage) + ",";
        entry = entry + HCProbeVector(m_HCProbeSeed) + "," + HCProbeVector(m_HCProbeSampledModel) + ",";
        entry = entry + HCProbeNum(m_HCProbeAttemptA) + "," + HCProbeNum(m_HCProbeAttemptB) + "]";
        if (m_HCProbeReachAttempts.Length() > 0)
            m_HCProbeReachAttempts = m_HCProbeReachAttempts + ",";
        m_HCProbeReachAttempts = m_HCProbeReachAttempts + entry;
    }

    void HCProbeReachSetup()
    {
        m_HCProbeReachState = "unavailable";
        m_HCProbeReachDoors = "";
        m_HCProbeReachEntrances = "";
        m_HCProbeReachAttempts = "";
        if (!HCProbeMeshAvailable())
            return;
        int doorCount = m_HCProbeBuilding.GetDoorCount();
        if (doorCount < 1)
        {
            m_HCProbeReachState = "no-door";
            return;
        }
        if (doorCount > 4)
            doorCount = 4;
        m_HCProbeReachState = "control-failed";
        float centreX = (m_HCProbeBoxMin[0] + m_HCProbeBoxMax[0]) * 0.5;
        float centreZ = (m_HCProbeBoxMin[2] + m_HCProbeBoxMax[2]) * 0.5;
        string doorText = "";
        int door = 0;
        int stage = 0;
        vector doorPos;
        for (door = 0; door < doorCount; door++)
        {
            doorPos = m_HCProbeBuilding.CoordToLocal(m_HCProbeBuilding.GetDoorSoundPos(door));
            if (door > 0)
                doorText = doorText + ",";
            doorText = doorText + HCProbeVector(doorPos);
            if (m_HCProbeReachState != "tested")
            {
                stage = HCProbeReachAttempt(doorPos, doorPos[0] - centreX, doorPos[2] - centreZ);
                if (stage == 3)
                    m_HCProbeReachState = "path-budget";
                HCProbeReachNote(door, stage);
                if (stage == 12)
                {
                    m_HCProbeReachState = "tested";
                    m_HCProbeReachEntrances = HCProbeVector(m_HCProbeSeed);
                }
            }
        }
        m_HCProbeReachDoors = doorText;
    }

    int HCProbeReachHit(vector floorPos)
    {
        if (m_HCProbeReachState != "tested")
            return -1;
        if (!HCProbeTakePath())
            return -1;
        if (!HCProbeSampleMesh(floorPos, 1.5))
            return 2;
        vector candidate = m_HCProbeSampled;
        if (vector.Distance(candidate, floorPos) > m_HCProbeSnapLimit)
            return 2;
        float shiftX = candidate[0] - floorPos[0];
        float shiftZ = candidate[2] - floorPos[2];
        float waistY = floorPos[1] + m_HCProbeWaistHeight;
        if (shiftX * shiftX + shiftZ * shiftZ > 0.000001)
        {
            if (HCProbeBlocked(Vector(floorPos[0], waistY, floorPos[2]), Vector(candidate[0], waistY, candidate[2])))
                return 2;
        }
        if (HCProbePath(m_HCProbeEntrance, candidate, floorPos) == 5)
            return 1;
        return 0;
    }

    void HCProbeRecordFloor(vector floorPos, float clearance, float dirY)
    {
        vector modelPos = m_HCProbeBuilding.CoordToLocal(floorPos);
        int code = -1;
        if (clearance >= 1.9)
            code = HCProbeReachHit(floorPos);
        string text = "[" + HCProbeNum(modelPos[0]) + "," + HCProbeNum(modelPos[1]) + "," + HCProbeNum(modelPos[2]) + ",";
        text = text + HCProbeNum(clearance) + "," + HCProbeNum(dirY) + "," + HCProbeInt(code) + "]";
        if (m_HCProbeOutputChars + text.Length() > m_HCProbeOutputLimit)
        {
            m_HCProbeOutputCapped = true;
            return;
        }
        if (m_HCProbeHitsEmitted > 0)
            text = "," + text;
        m_HCProbeHitsEmitted = m_HCProbeHitsEmitted + 1;
        HCProbeEmit(text);
    }

    void HCProbeScanColumn(float localX, float localZ)
    {
        vector baseWorld = m_HCProbeBuilding.CoordToParent(Vector(localX, m_HCProbeBoxMin[1], localZ));
        float topY = baseWorld[1] + (m_HCProbeBoxMax[1] - m_HCProbeBoxMin[1]) + 0.5;
        float bottomY = baseWorld[1] - 0.5;
        float startY = topY;
        float lastY = topY + 100.0;
        float previousY = 0.0;
        float hitY = 0.0;
        float dirY = 0.0;
        float drop = 0.0;
        float offset = 0.0;
        float usedOffset = 0.0;
        float clearance = 0.0;
        vector surfacePos;
        string trace = "";
        string typeName = "";
        bool tracing = false;
        if (m_HCProbeDiagColumns < 3)
            tracing = true;
        int capKind = 1;
        int steps = 0;
        int floors = 0;
        int action = 0;
        int rel = 0;
        int count = 0;
        int step = 0;
        int result = 0;
        for (step = 0; step < m_HCProbeStepLimit; step++)
        {
            if (startY <= bottomY)
            {
                capKind = 0;
                break;
            }
            result = HCProbeRay(Vector(baseWorld[0], startY, baseWorld[2]), Vector(baseWorld[0], bottomY, baseWorld[2]));
            if (result < 1)
            {
                capKind = 0;
                break;
            }
            steps = steps + 1;
            hitY = m_HCProbeHitPos[1];
            dirY = m_HCProbeHitDir[1];
            rel = m_HCProbeHitRel;
            count = m_HCProbeHitCount;
            typeName = m_HCProbeHitType;
            surfacePos = m_HCProbeHitPos;
            drop = startY - hitY;
            usedOffset = offset;
            offset = 0.05;
            if (drop < 0.02)
            {
                m_HCProbeStatRehits = m_HCProbeStatRehits + 1;
                offset = usedOffset * 2.0;
                if (offset < 0.05)
                    offset = 0.05;
                if (offset > 0.8)
                    offset = 0.8;
            }
            startY = hitY - offset;
            HCProbeHitNote(rel, typeName);
            action = 0;
            if (rel == 1)
            {
                previousY = lastY;
                lastY = hitY;
                action = 2;
                if (previousY - hitY >= 0.25)
                {
                    floors = floors + 1;
                    clearance = HCProbeClearance(surfacePos);
                    action = 3;
                    if (clearance >= 0.0)
                    {
                        action = 4;
                        m_HCProbeStatInterior = m_HCProbeStatInterior + 1;
                        HCProbeRecordFloor(surfacePos, clearance, dirY);
                    }
                    if (action == 3)
                        m_HCProbeStatExterior = m_HCProbeStatExterior + 1;
                }
            }
            if (tracing && steps <= 32)
                trace = trace + HCProbeTraceEntry(steps, rel, count, hitY - baseWorld[1] + m_HCProbeBoxMin[1], drop, usedOffset, dirY, action, typeName);
            if (floors >= m_HCProbeHitLimit)
            {
                capKind = 2;
                break;
            }
        }
        if (capKind == 1 && startY <= bottomY)
            capKind = 0;
        if (capKind == 1)
            m_HCProbeStatStepCapped = m_HCProbeStatStepCapped + 1;
        if (capKind == 2)
            m_HCProbeStatFloorCapped = m_HCProbeStatFloorCapped + 1;
        if (capKind > 0 || steps >= 12)
            HCProbeDiagColumn(localX, localZ, steps, floors, capKind, trace);
    }

    void HCProbeScanRow()
    {
        if (!m_HCProbeBuilding || m_HCProbeRayCapped || m_HCProbeOutputCapped || m_HCProbeRow >= m_HCProbeRows)
        {
            m_HCProbePhase = 2;
            return;
        }
        float localX = m_HCProbeBoxMin[0] + 0.5 + m_HCProbeRow * m_HCProbeGridStep;
        float localZ = 0.0;
        int col = 0;
        for (col = 0; col < m_HCProbeCols; col++)
        {
            localZ = m_HCProbeBoxMin[2] + 0.5 + col * m_HCProbeGridStep;
            HCProbeScanColumn(localX, localZ);
            m_HCProbeStatColumns = m_HCProbeStatColumns + 1;
        }
        m_HCProbeRow = m_HCProbeRow + 1;
        if (m_HCProbeRow >= m_HCProbeRows)
            m_HCProbePhase = 2;
    }

    void HCProbeBeginBuilding()
    {
        string expectedType = m_HCProbeClasses.Get(m_HCProbeCursor);
        vector expectedPos = m_HCProbePositions.Get(m_HCProbeCursor);
        array<Object> candidates = new array<Object>;
        array<CargoBase> candidateCargos = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(expectedPos, 4.0, candidates, candidateCargos);
        m_HCProbeBuilding = null;
        float bestDistance = FLT_MAX;
        int scanLimit = candidates.Count();
        if (scanLimit > 256)
            scanLimit = 256;
        int scan = 0;
        for (scan = 0; scan < scanLimit; scan++)
        {
            Building candidate = Building.Cast(candidates.Get(scan));
            if (!candidate)
                continue;
            if (candidate.GetType() != expectedType)
                continue;
            float candidateDistance = vector.Distance(candidate.GetPosition(), expectedPos);
            if (candidateDistance < bestDistance)
            {
                bestDistance = candidateDistance;
                m_HCProbeBuilding = candidate;
            }
        }
        m_HCProbeBuildingRays = 0;
        m_HCProbeBuildingPaths = 0;
        m_HCProbeHitsEmitted = 0;
        m_HCProbeStatColumns = 0;
        m_HCProbeStatInterior = 0;
        m_HCProbeStatExterior = 0;
        m_HCProbeStatOther = 0;
        m_HCProbeStatStepCapped = 0;
        m_HCProbeStatFloorCapped = 0;
        m_HCProbeStatRehits = 0;
        m_HCProbeStatClearCapped = 0;
        m_HCProbeRelNone = 0;
        m_HCProbeRelBuilding = 0;
        m_HCProbeRelProxy = 0;
        m_HCProbeRelOther = 0;
        m_HCProbeDiagColumns = 0;
        m_HCProbeDiag = "";
        m_HCProbeTypeNames.Clear();
        m_HCProbeTypeCounts.Clear();
        m_HCProbeReachAttempts = "";
        m_HCProbeRayCapped = false;
        m_HCProbeOutputCapped = false;
        m_HCProbeBoxSource = "none";
        m_HCProbeBoxMin = Vector(0.0, 0.0, 0.0);
        m_HCProbeBoxMax = Vector(0.0, 0.0, 0.0);
        m_HCProbeReachState = "none";
        m_HCProbeReachDoors = "";
        m_HCProbeReachEntrances = "";
        m_HCProbeRow = 0;
        m_HCProbeRows = 0;
        m_HCProbeCols = 0;
        m_HCProbePhase = 2;
        bool found = false;
        float distance = -1.0;
        vector actualPos = Vector(0.0, 0.0, 0.0);
        vector orientation = Vector(0.0, 0.0, 0.0);
        vector clip[2];
        if (m_HCProbeBuilding)
        {
            found = true;
            m_HCProbeFoundCount = m_HCProbeFoundCount + 1;
            distance = bestDistance;
            actualPos = m_HCProbeBuilding.GetPosition();
            orientation = m_HCProbeBuilding.GetOrientation();
            m_HCProbeBuilding.ClippingInfo(clip);
            m_HCProbeBoxMin = clip[0];
            m_HCProbeBoxMax = clip[1];
            if (HCProbeBoxUsable(m_HCProbeBoxMin, m_HCProbeBoxMax))
                m_HCProbeBoxSource = "clipping";
        }
        if (m_HCProbeBoxSource == "clipping")
        {
            m_HCProbeRows = HCProbeCount(m_HCProbeBoxMin[0], m_HCProbeBoxMax[0]);
            m_HCProbeCols = HCProbeCount(m_HCProbeBoxMin[2], m_HCProbeBoxMax[2]);
            HCProbeReachSetup();
            m_HCProbePhase = 1;
        }
        string text = "";
        if (m_HCProbeCursor > 0)
            text = ",";
        text = text + "{" + HCProbeKey("i") + HCProbeInt(m_HCProbeCursor) + "," + HCProbeKey("class") + HCProbeStr(expectedType) + ",";
        text = text + HCProbeKey("role") + HCProbeStr(m_HCProbeRoles.Get(m_HCProbeCursor)) + "," + HCProbeKey("found") + HCProbeBool(found) + ",";
        text = text + HCProbeKey("actual") + HCProbeVector(actualPos) + "," + HCProbeKey("distance") + HCProbeNum(distance) + ",";
        text = text + HCProbeKey("orientation") + HCProbeVector(orientation) + "," + HCProbeKey("box_source") + HCProbeStr(m_HCProbeBoxSource) + ",";
        text = text + HCProbeKey("box_min") + HCProbeVector(m_HCProbeBoxMin) + "," + HCProbeKey("box_max") + HCProbeVector(m_HCProbeBoxMax) + ",";
        text = text + HCProbeKey("grid") + "{" + HCProbeKey("step") + HCProbeNum(m_HCProbeGridStep) + "," + HCProbeKey("rows") + HCProbeInt(m_HCProbeRows) + ",";
        text = text + HCProbeKey("cols") + HCProbeInt(m_HCProbeCols) + "},";
        text = text + HCProbeKey("reach") + "{" + HCProbeKey("state") + HCProbeStr(m_HCProbeReachState) + ",";
        text = text + HCProbeKey("doors") + "[" + m_HCProbeReachDoors + "]," + HCProbeKey("entrances") + "[" + m_HCProbeReachEntrances + "],";
        text = text + HCProbeKey("attempts") + "[" + m_HCProbeReachAttempts + "]},";
        text = text + HCProbeKey("hits") + "[";
        HCProbeEmit(text);
    }

    void HCProbeEndBuilding()
    {
        string text = "]," + HCProbeKey("stats") + "{" + HCProbeKey("columns") + HCProbeInt(m_HCProbeStatColumns) + ",";
        text = text + HCProbeKey("rays") + HCProbeInt(m_HCProbeBuildingRays) + "," + HCProbeKey("paths") + HCProbeInt(m_HCProbeBuildingPaths) + ",";
        text = text + HCProbeKey("ray_capped") + HCProbeBool(m_HCProbeRayCapped) + "," + HCProbeKey("output_capped") + HCProbeBool(m_HCProbeOutputCapped) + ",";
        text = text + HCProbeKey("interior_hits") + HCProbeInt(m_HCProbeStatInterior) + "," + HCProbeKey("exterior_hits") + HCProbeInt(m_HCProbeStatExterior) + ",";
        text = text + HCProbeKey("other_hits") + HCProbeInt(m_HCProbeStatOther) + "," + HCProbeKey("step_capped_columns") + HCProbeInt(m_HCProbeStatStepCapped) + ",";
        text = text + HCProbeKey("floor_capped_columns") + HCProbeInt(m_HCProbeStatFloorCapped) + "," + HCProbeKey("rehits") + HCProbeInt(m_HCProbeStatRehits) + ",";
        text = text + HCProbeKey("clearance_capped") + HCProbeInt(m_HCProbeStatClearCapped) + "," + HCProbeKey("hit_relations") + "{" + HCProbeKey("none") + HCProbeInt(m_HCProbeRelNone) + ",";
        text = text + HCProbeKey("building") + HCProbeInt(m_HCProbeRelBuilding) + "," + HCProbeKey("proxy") + HCProbeInt(m_HCProbeRelProxy) + ",";
        text = text + HCProbeKey("other") + HCProbeInt(m_HCProbeRelOther) + "}," + HCProbeKey("other_types") + "[" + HCProbeTypesText() + "]},";
        text = text + HCProbeKey("diag") + "{" + HCProbeKey("columns") + "[" + m_HCProbeDiag + "]}}";
        HCProbeEmit(text);
        m_HCProbeCursor = m_HCProbeCursor + 1;
        m_HCProbePhase = 0;
    }

    void HCProbeFinish()
    {
        string text = "]," + HCProbeKey("summary") + "{" + HCProbeKey("targets") + HCProbeInt(m_HCProbeClasses.Count()) + ",";
        text = text + HCProbeKey("found") + HCProbeInt(m_HCProbeFoundCount) + "," + HCProbeKey("complete") + "true,";
        text = text + HCProbeKey("run_rays") + HCProbeInt(m_HCProbeRunRays) + "," + HCProbeKey("begin_ms") + HCProbeInt(m_HCProbeBeginMs) + ",";
        text = text + HCProbeKey("end_ms") + HCProbeInt(GetGame().GetTime()) + "}}";
        HCProbeEmit(text);
        HCProbeFlush();
        if (m_HCProbeWriteFailed)
        {
            Print("[HC Interior Sampler] FAILED census write error; no sentinel");
            return;
        }
        FileHandle sentinel = OpenFile(m_HCProbeSentinel, FileMode.WRITE);
        if (!sentinel)
        {
            Print("[HC Interior Sampler] FAILED cannot open sentinel file");
            return;
        }
        string summary = "rows=" + HCProbeInt(m_HCProbeClasses.Count()) + " found=" + HCProbeInt(m_HCProbeFoundCount);
        FPrintln(sentinel, summary);
        CloseFile(sentinel);
        Print("[HC Interior Sampler] " + summary);
        Print("[HC Interior Sampler] COMPLETE");
    }

    void HCProbeStep()
    {
        if (m_HCProbeCursor >= m_HCProbeClasses.Count())
        {
            HCProbeFinish();
            return;
        }
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCProbeStep, 100, false);
        int phase = m_HCProbePhase;
        if (phase == 0)
        {
            HCProbeBeginBuilding();
            return;
        }
        if (phase == 1)
        {
            HCProbeScanRow();
            return;
        }
        HCProbeEndBuilding();
    }

    void HCProbeStart()
    {
        string directory = "$profile:@@PROFILE_DIR@@";
        if (!FileExist(directory) && !MakeDirectory(directory))
        {
            Print("[HC Interior Sampler] FAILED cannot create output directory");
            return;
        }
        if (FileExist(m_HCProbePath) || FileExist(m_HCProbeSentinel))
        {
            Print("[HC Interior Sampler] FAILED earlier output exists; not overwriting");
            return;
        }
        m_HCProbeFilter = new PGFilter;
        m_HCProbeFilter.SetFlags(PGPolyFlags.WALK | PGPolyFlags.DOOR | PGPolyFlags.INSIDE, PGPolyFlags.DISABLED | PGPolyFlags.UNREACHABLE | PGPolyFlags.SWIM | PGPolyFlags.SWIM_SEA | PGPolyFlags.LADDER | PGPolyFlags.JUMP | PGPolyFlags.CLIMB | PGPolyFlags.CRAWL | PGPolyFlags.CROUCH, PGPolyFlags.NONE);
        m_HCProbeFilter.SetCost(PGAreaType.DOOR_CLOSED, 1000);
        string world;
        string version;
        GetGame().GetWorldName(world);
        GetGame().GetVersion(version);
        HCProbeHeader(world, version);
        if (!FileExist(m_HCProbePath))
        {
            Print("[HC Interior Sampler] FAILED census header missing after write");
            return;
        }
        Print("[HC Interior Sampler] BEGIN; observation only; targets=" + HCProbeInt(m_HCProbeClasses.Count()));
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCProbeStep, 100, false);
    }
}
"""


def _bounded(name, value, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")
    return value


def render_hook(targets, sample_delay_s=DEFAULT_SAMPLE_DELAY_S, run_ray_limit=DEFAULT_RUN_RAY_LIMIT,
                building_ray_limit=DEFAULT_BUILDING_RAY_LIMIT, hit_limit=DEFAULT_HIT_LIMIT,
                path_limit=DEFAULT_PATH_LIMIT, output_limit=DEFAULT_OUTPUT_LIMIT, intersect="geom",
                step_limit=DEFAULT_STEP_LIMIT):
    """Return the generated Enforce text (bytes) with every target and limit inlined as literal data."""
    if not targets or len(targets) > MAX_TARGETS:
        raise ValueError(f"1..{MAX_TARGETS} targets required")
    _bounded("sample delay", sample_delay_s, *SAMPLE_DELAY_RANGE)
    _bounded("run ray limit", run_ray_limit, *RUN_RAY_RANGE)
    _bounded("building ray limit", building_ray_limit, *BUILDING_RAY_RANGE)
    _bounded("hit limit", hit_limit, *HIT_LIMIT_RANGE)
    _bounded("step limit", step_limit, *STEP_LIMIT_RANGE)
    _bounded("path limit", path_limit, *PATH_LIMIT_RANGE)
    _bounded("output limit", output_limit, *OUTPUT_LIMIT_RANGE)
    if intersect not in INTERSECTS:
        raise ValueError("intersect must be one of " + ", ".join(sorted(INTERSECTS)))
    adds = []
    for target in targets:
        name, role, pos = target["class"], target["role"], target["pos"]
        if not rt.IDENT_RULE.match(name) or not placements_tool.ROLE_RULE.match(role):
            raise ValueError("target class/role must be plain identifiers")
        if len(pos) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) and abs(v) < 1e6 for v in pos):
            raise ValueError("target position must be three bounded finite numbers")
        adds.append('        HCProbeAdd("%s", "%s", %.6f, %.6f, %.6f);' % (name, role, *pos))
    chunks = [adds[i:i + LOADER_CHUNK] for i in range(0, len(adds), LOADER_CHUNK)]
    calls = "\n".join(f"        HCProbeLoadTargets{n}();" for n in range(len(chunks)))
    loaders = "".join("    void HCProbeLoadTargets%d()\n    {\n%s\n    }\n\n" % (n, "\n".join(chunk))
                      for n, chunk in enumerate(chunks))
    shared = (("@@PROFILE_DIR@@", PROFILE_DIRECTORY), ("@@OUTPUT_NAME@@", OUTPUT_NAME),
              ("@@SENTINEL_NAME@@", SENTINEL_NAME))
    head = HOOK_HEAD
    for placeholder, value in (("@@LOADER_CALLS@@", calls), ("@@START_MS@@", str(sample_delay_s * 1000)),
                               ("@@GRID_STEP@@", repr(GRID_STEP)), ("@@HIT_LIMIT@@", str(hit_limit)), ("@@STEP_LIMIT@@", str(step_limit)),
                               ("@@BUILDING_RAY_LIMIT@@", str(building_ray_limit)),
                               ("@@RUN_RAY_LIMIT@@", str(run_ray_limit)), ("@@PATH_LIMIT@@", str(path_limit)),
                               ("@@OUTPUT_LIMIT@@", str(output_limit))) + shared:
        head = head.replace(placeholder, value)
    tail = HOOK_TAIL.replace("@@INTERSECT@@", INTERSECTS[intersect])
    for placeholder, value in shared:
        tail = tail.replace(placeholder, value)
    text = head + loaders + tail
    if "@@" in text:
        raise ValueError("unresolved placeholder in hook")
    if not text.isascii():
        raise ValueError("hook must be ASCII")
    return text.encode("ascii")


# ---------------------------------------------------------------------------
# Lint: probe_runtime's observed compile-shape rules plus the sampler extras
# ---------------------------------------------------------------------------

_LITERAL = re.compile(r'"(?:[^"\\]|\\.)*"')
_PLUS = re.compile(r"(?<!\+)\+(?![+=])")
_FUNCTION_HEAD = re.compile(
    r"\s*(?:(?:override|static|protected|private|proto|native|external)\s+)*[\w<>,]+\s+(\w+)\s*\(([^()]*)\)\s*")
_NOT_FUNCTIONS = frozenset({"if", "for", "while", "switch", "foreach", "else", "return", "new"})
_TYPED_NAME = re.compile(r"\b(int|float|bool|string|vector)\s+(\w+)\s*(?=[;=,)\[])")
_MEMBER_NAME = re.compile(r"\b(?:protected|private)\s+(?:ref\s+)?(int|float|bool|string|vector)\s+(\w+)")
_ANY_DECLARATION = re.compile(r"\b[A-Za-z_]\w*(?:<[^;()=]*?>)?\s+(\w+)\s*(?=[;=])")
_STRING_HELPERS = re.compile(r"^HCProbe(?:Key|Str|Bool|Vector|Int|Num)\(")
_NUMBER_LITERAL = re.compile(r"^-?\d+(?:\.\d+)?$")
_NUMBER_CALL = re.compile(r"(?:\.Count\(\)|\.Length\(\)|\bGetTime\(\)|\.GetDoorCount\(\))$")
_ASSIGNMENT_PREFIX = re.compile(r"^(?:return\b\s*|(?:[\w<>]+\s+)?[\w.\[\]]+\s*=(?!=)\s*)")
_SAMPLER_OUT_CALLS = (("RaycastRV", (2, 3, 4)), ("SampleNavmeshPosition", (3,)), ("FindPath", (3,)))


def _blank(text):
    """Text with comments removed and string literal contents blanked (the literals stay as "")."""
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return "\n".join(_LITERAL.sub('""', line).split("//")[0] for line in text.splitlines())


def _functions(clean):
    """(name, parameter text, body text, body start) for every function declared at brace depth 0 or 1.

    Detection follows the braces, not the layout: inline braces, K&R style, tabs and any indentation count."""
    depth, boundary, position = 0, 0, 0
    while position < len(clean):
        char = clean[position]
        if char == "{" and depth <= 1:
            match = _FUNCTION_HEAD.fullmatch(clean[boundary:position])
            if match and match.group(1) not in _NOT_FUNCTIONS:
                inner = 0
                for end in range(position, len(clean)):
                    inner += {"{": 1, "}": -1}.get(clean[end], 0)
                    if inner == 0:
                        yield match.group(1), match.group(2), clean[position:end + 1], position
                        break
                else:
                    return
                position, boundary = end + 1, end + 1
                continue
            depth += 1
            boundary = position + 1
        elif char == "{":
            depth += 1
            boundary = position + 1
        elif char == "}":
            depth -= 1
            boundary = position + 1
        elif char == ";":
            boundary = position + 1
        position += 1


def _split_top(text, separator):
    parts, depth, current = [], 0, []
    for index, char in enumerate(text):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        joins = char == separator and depth == 0
        if separator == "+":
            joins = joins and text[index + 1:index + 2] not in ("+", "=") and text[index - 1:index] != "+"
        if joins:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    parts.append("".join(current).strip())
    return parts


def _groups(text):
    depth, start = 0, 0
    for index, char in enumerate(text):
        if char in "([":
            if depth == 0:
                start = index + 1
            depth += 1
        elif char in ")]":
            depth -= 1
            if depth == 0:
                yield text[start:index]


def _operand_kind(operand, types):
    if operand.startswith('""') or _STRING_HELPERS.match(operand) or operand.endswith(".ToString()"):
        return "string"
    if types.get(operand) == "string":
        return "string"
    if _NUMBER_LITERAL.match(operand) or _NUMBER_CALL.search(operand) or types.get(operand) in ("int", "float"):
        return "number"
    indexed = re.fullmatch(r"(\w+)\[[^\]]*\]", operand)
    if indexed and types.get(indexed.group(1)) == "vector":
        return "number"
    return "other"


def _joined_numbers(segment, types):
    """Operands of the concatenations in ``segment`` (every nesting level) that are bare numbers."""
    found = []
    for expression in _split_top(segment, ","):
        expression = _ASSIGNMENT_PREFIX.sub("", expression, count=1)
        operands = _split_top(expression, "+")
        if len(operands) > 1:
            kinds = [(operand, _operand_kind(operand, types)) for operand in operands]
            if any(kind == "string" for _operand, kind in kinds):
                found.extend(operand for operand, kind in kinds if kind == "number")
        for group in _groups(expression):
            found.extend(_joined_numbers(group, types))
    return found


def statement_plus_counts(text):
    """(line, binary '+' count) for every statement, counted on comment-free text with string contents blanked.

    A statement is whatever lies between ';', '{' and '}', so inline braces, any indentation and line breaks
    inside a statement cannot hide an operator. ``++`` and ``+=`` are not binary additions."""
    clean = _blank(text)
    counts = []
    for found in re.finditer(r"[^;{}]+", clean):
        chunk = found.group(0)
        if not chunk.strip():
            continue
        line = clean.count("\n", 0, found.start() + len(chunk) - len(chunk.lstrip())) + 1
        counts.append((line, len(_PLUS.findall(chunk))))
    return counts


def lint_sampler_hook(text, native_types=frozenset()):
    """Return a list of issues; empty means no observed-rejected shape was found.

    Covers probe_runtime's shared rules plus: no else (the reference transpiler models none), at most
    eight binary '+' per statement ("Formula too complex"), no bare number joined to a string
    ("Incompatible parameter"), and every out argument declared before its call. The sampler checks read
    the text per cleaned statement and per brace-delimited function, whatever the layout."""
    issues = list(rt.lint_hook(text, native_types=native_types))
    clean = _blank(text)
    for number, line in enumerate(clean.splitlines(), 1):
        if re.search(r"\belse\b", line):
            issues.append(f"line {number}: 'else' is not allowed (the reference transpiler models none)")
    for line, count in statement_plus_counts(text):
        if count > MAX_PLUS_PER_STATEMENT:
            issues.append(f"line {line}: {count} binary '+' operators in one statement "
                          f"(more than {MAX_PLUS_PER_STATEMENT} is 'Formula too complex' natively)")
    members = {name: kind for kind, name in _MEMBER_NAME.findall(clean)}
    for function, parameters, body, start in _functions(clean):
        types = dict(members)
        types.update({name: kind for kind, name in _TYPED_NAME.findall(parameters + "\n" + body)})
        for found in re.finditer(r"[^;{}]+", body):
            statement = re.sub(r"\s+", " ", found.group(0)).strip()
            for operand in _joined_numbers(statement, types):
                line = clean.count("\n", 0, start + found.start()) + 1
                issues.append(f"{function} (line {line}): number '{operand}' joined to a string without "
                              "ToString(), HCProbeInt or HCProbeNum")
        declared = [(m.start(1), m.group(1)) for m in _ANY_DECLARATION.finditer(body)]
        for callee, positions in _SAMPLER_OUT_CALLS:
            for call in re.finditer(r"\b%s\s*\(" % callee, body):
                end, depth = call.end(), 1
                while end < len(body) and depth:
                    depth += {"(": 1, ")": -1}.get(body[end], 0)
                    end += 1
                args = _split_top(body[call.end():end - 1], ",")
                for position in positions:
                    name = args[position] if position < len(args) else ""
                    if not re.match(r"^[A-Za-z_]\w*$", name) or not any(
                            n == name and offset < call.start() for offset, n in declared):
                        issues.append(f"{function}: out argument '{name}' of {callee} must be declared before the call")
    return issues


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------


def stage(source_runtime, destination, *, per_class=DEFAULT_PER_CLASS, wait_minutes=DEFAULT_WAIT_MINUTES,
          intersect="geom", sample_delay_s=DEFAULT_SAMPLE_DELAY_S, hit_limit=DEFAULT_HIT_LIMIT,
          step_limit=DEFAULT_STEP_LIMIT,
          building_ray_limit=DEFAULT_BUILDING_RAY_LIMIT, run_ray_limit=DEFAULT_RUN_RAY_LIMIT,
          path_limit=DEFAULT_PATH_LIMIT, output_limit=DEFAULT_OUTPUT_LIMIT,
          battleye_sha256=rt.BATTLEYE_SHA256, native_scripts=None, now=None, _wsl_parent=None):
    """Stage a fresh sampler runtime and write interior-sampler-plan.json. Never launches anything.

    ``_wsl_parent`` is an internal test hook; the production parent is always rt.WSL_PARENT
    and the Windows root is always derived from the destination, never supplied.
    """
    if not 5 <= wait_minutes <= 120 or not 1 <= per_class <= MAX_PER_CLASS:
        raise ValueError(f"wait minutes 5..120 and per-class 1..{MAX_PER_CLASS} required")
    context = rt.begin(source_runtime, destination, parent=rt.WSL_PARENT if _wsl_parent is None else _wsl_parent,
                       battleye_sha256=battleye_sha256, hold=("mapgrouppos.xml",))
    source = context["source"]
    names = {name for name, _role in SAMPLE_CLASSES}
    placements = placements_tool.parse_placements(source["held"]["mapgrouppos.xml"], wanted=names)
    missing = [name for name, _role in SAMPLE_CLASSES if not placements.get(name)]
    if missing:
        raise ValueError("stock mapgrouppos has no placements for: " + ", ".join(missing))
    targets = placements_tool.build_targets(placements, classes=SAMPLE_CLASSES, per_class=per_class,
                                            hard_cap=MAX_TARGETS)
    limits = {"sample_delay_s": sample_delay_s, "run_ray_limit": run_ray_limit,
              "building_ray_limit": building_ray_limit, "hit_limit": hit_limit, "step_limit": step_limit,
              "path_limit": path_limit, "output_limit": output_limit, "intersect": intersect}
    hook = render_hook(targets, **limits)
    native = rt.native_type_names(native_scripts) if native_scripts else frozenset()
    problems = lint_sampler_hook(hook.decode("ascii"), native_types=native)
    if problems:
        raise ValueError("generated hook violates native compile rules: " + "; ".join(problems[:3]))

    # The mission instrumentation purpose is the CE probe's (a generated hook); the plan kind is ours.
    built = rt.build_runtime(context, hook, purpose="ce-probe")
    classes = [{"class": name, "role": role, "available": len(placements.get(name, [])),
                "sampled": sum(1 for t in targets if t["class"] == name)} for name, role in SAMPLE_CLASSES]
    plan = rt.plan_header(KIND, now, after={"variant": "sampler"})
    plan.update(rt.plan_runtime_fields(context, built))
    plan.update({
        "treatment": None,
        "probe": {"tool": KIND, "sample_delay_s": sample_delay_s, "per_class_limit": per_class,
                  "hard_cap": MAX_TARGETS, "target_count": len(targets), "hook_sha256": rt.sha256(hook),
                  "hook_bytes": len(hook), "wait_minutes": wait_minutes,
                  "census_relative_path": f"profiles/{PROFILE_DIRECTORY}/{OUTPUT_NAME}",
                  "sentinel_relative_path": f"profiles/{PROFILE_DIRECTORY}/{SENTINEL_NAME}"},
        "sampler": {"grid_step": GRID_STEP, "per_class": per_class, "intersect": intersect,
                    "hit_limit": hit_limit, "step_limit": step_limit, "building_ray_limit": building_ray_limit,
                    "run_ray_limit": run_ray_limit, "path_limit": path_limit, "output_limit": output_limit,
                    "provisional_tolerances_m": {"snap_limit": 0.5, "path_end": 0.5, "seed_margin": 1.0,
                                                 "projected_margin": 0.5, "waist_height": 1.0}},
        "target_classes": classes, "targets": targets,
        "mission_files": built["mission_files"], "staged_files": built["staged"],
    })
    return rt.write_plan(context["destination"], PLAN_NAME, plan)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--destination", required=True, help="fresh runtime directory (must not exist)")
    parser.add_argument("--source-runtime", default=rt.DEFAULT_SOURCE_RUNTIME)
    parser.add_argument("--per-class", type=int, default=DEFAULT_PER_CLASS)
    parser.add_argument("--intersect", default="geom", help="raycast geometry: " + ", ".join(sorted(INTERSECTS)))
    parser.add_argument("--wait-minutes", type=int, default=DEFAULT_WAIT_MINUTES)
    parser.add_argument("--sample-delay-s", type=int, default=DEFAULT_SAMPLE_DELAY_S)
    parser.add_argument("--battleye-sha256", default=rt.BATTLEYE_SHA256)
    parser.add_argument("--native-scripts", help="extracted native script cache used to lint the hook")
    args = parser.parse_args(argv)
    cache = args.native_scripts
    if cache is None:
        default = Path.home() / ".cache/hollow-country/native-scripts/scripts-1.30.164289"
        cache = default if (default / "3_Game").is_dir() else None
    try:
        plan = stage(args.source_runtime, args.destination, per_class=args.per_class, intersect=args.intersect,
                     wait_minutes=args.wait_minutes, sample_delay_s=args.sample_delay_s,
                     battleye_sha256=args.battleye_sha256, native_scripts=cache)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"interior_sampler: {error}", file=sys.stderr)
        return 1
    print(f"staged {plan['kind']} runtime: {Path(args.destination) / PLAN_NAME}")
    print(f"targets={plan['probe']['target_count']} hook_bytes={plan['probe']['hook_bytes']} "
          f"hook_sha256={plan['probe']['hook_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
