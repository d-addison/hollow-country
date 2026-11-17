"""Stage a disposable native interior floor sampler runtime; never launch the engine.

The sampler answers one question per placement: where are the walkable, roofed floor
surfaces of this exact building, in the building's model space. It is an observation
harness. It proves nothing about DayZ behavior until its census has been produced by a
native run and inspected, and it never accepts anything itself.

Stage a fresh runtime (destination must not exist):

    python3 tools/setup/interior_sampler.py --destination /mnt/d/HollowCountryLocal/interior-sampler-001

The staging, confinement and allowlist functions are the CE probe's (tools/setup/ce_probe.py);
the plan keeps kind "ce-probe" so the unchanged tools/setup/Start-CEProbeServer.ps1 launches it.
Convert the census with tools/audit/interior_points.py.
"""
import argparse
import datetime
import json
import math
from pathlib import Path
import re
import sys

try:
    from . import ce_probe as probe
    from . import diagnostic_mission as dm
except ImportError:  # executed as a script from tools/setup
    import ce_probe as probe
    import diagnostic_mission as dm

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
BUILDING_RAY_RANGE = (100, 2000000)
RUN_RAY_RANGE = (100, 20000000)
PATH_LIMIT_RANGE = (0, 20000)
OUTPUT_LIMIT_RANGE = (4096, 50000000)
DEFAULT_SAMPLE_DELAY_S = 75
DEFAULT_HIT_LIMIT = 24
DEFAULT_BUILDING_RAY_LIMIT = 40000
DEFAULT_RUN_RAY_LIMIT = 400000
DEFAULT_PATH_LIMIT = 3000
DEFAULT_OUTPUT_LIMIT = 6000000
DEFAULT_WAIT_MINUTES = 10

# ---------------------------------------------------------------------------
# Generated Enforce hook
# ---------------------------------------------------------------------------

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
    protected string m_HCProbePath = "$profile:HCCEProbe/census.json";
    protected string m_HCProbeSentinel = "$profile:HCCEProbe/complete.txt";
    protected string m_HCProbePending = "";
    protected string m_HCProbeBoxSource = "none";
    protected string m_HCProbeReachState = "none";
    protected string m_HCProbeReachDoors = "";
    protected string m_HCProbeReachEntrances = "";
    protected float m_HCProbeGridStep = @@GRID_STEP@@;
    protected int m_HCProbeHitLimit = @@HIT_LIMIT@@;
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
    protected int m_HCProbeStatHitCapped = 0;
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
    protected vector m_HCProbeEntrance;

    override void OnInit()
    {
        super.OnInit();
        if (!GetGame() || !GetGame().IsServer() || m_HCProbeStarted)
            return;
        m_HCProbeStarted = true;
        int quoteCode = 34;
        m_HCProbeQuote = quoteCode.AsciiToString();
@@LOADER_CALLS@@
        Print("[HC Interior Sampler] LOADED; targets=" + m_HCProbeClasses.Count());
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
        return "[" + value[0] + "," + value[1] + "," + value[2] + "]";
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

    int HCProbeRay(vector rayFrom, vector rayTo)
    {
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
        if (hitObjects.Find(m_HCProbeBuilding) == -1)
            return 2;
        return 1;
    }

    float HCProbeClearance(vector surfacePos)
    {
        float startY = surfacePos[1] + 0.05;
        float endY = surfacePos[1] + 6.0;
        float hitY = 0.0;
        int result = 0;
        int attempt = 0;
        for (attempt = 0; attempt < 4; attempt++)
        {
            if (startY >= endY)
                return -1.0;
            result = HCProbeRay(Vector(surfacePos[0], startY, surfacePos[2]), Vector(surfacePos[0], endY, surfacePos[2]));
            if (result < 1)
                return -1.0;
            hitY = m_HCProbeHitPos[1];
            if (result == 1)
                return hitY - surfacePos[1];
            startY = hitY + 0.05;
        }
        return -1.0;
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
        FPrintln(handle, "{" + HCProbeKey("schema") + "1," + HCProbeKey("kind") + HCProbeStr("interior-sampler-census") + "," + HCProbeKey("world") + HCProbeStr(world) + "," + HCProbeKey("version") + HCProbeStr(version) + "," + HCProbeKey("placements") + "[");
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

    int HCProbePath(vector startPos, vector endPos)
    {
        TVectorArray waypoints = new TVectorArray;
        bool found = GetGame().GetWorld().GetAIWorld().FindPath(startPos, endPos, m_HCProbeFilter, waypoints);
        if (!found)
            return 0;
        if (waypoints.Count() < 2)
            return 0;
        vector finalPoint = waypoints.Get(waypoints.Count() - 1);
        float gap = vector.Distance(finalPoint, endPos);
        if (gap <= 2.0)
            return 1;
        return 0;
    }

    void HCProbeReachSetup()
    {
        m_HCProbeReachState = "unavailable";
        m_HCProbeReachDoors = "";
        m_HCProbeReachEntrances = "";
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
        vector doorPos;
        vector entrance;
        vector farPoint;
        vector entranceSampled;
        float dirX = 0.0;
        float dirZ = 0.0;
        float dirLength = 0.0;
        float unitX = 0.0;
        float unitZ = 0.0;
        for (door = 0; door < doorCount; door++)
        {
            doorPos = m_HCProbeBuilding.CoordToLocal(m_HCProbeBuilding.GetDoorSoundPos(door));
            if (door > 0)
                doorText = doorText + ",";
            doorText = doorText + HCProbeVector(doorPos);
            if (m_HCProbeReachState == "tested")
                continue;
            dirX = doorPos[0] - centreX;
            dirZ = doorPos[2] - centreZ;
            dirLength = Math.Sqrt(dirX * dirX + dirZ * dirZ);
            if (dirLength < 0.1)
                continue;
            unitX = dirX / dirLength;
            unitZ = dirZ / dirLength;
            entrance = Vector(doorPos[0] + unitX * 2.0, doorPos[1], doorPos[2] + unitZ * 2.0);
            farPoint = Vector(doorPos[0] + unitX * 12.0, doorPos[1], doorPos[2] + unitZ * 12.0);
            if (!HCProbeSampleMesh(m_HCProbeBuilding.CoordToParent(entrance), 1.5))
                continue;
            entranceSampled = m_HCProbeSampled;
            if (!HCProbeSampleMesh(m_HCProbeBuilding.CoordToParent(farPoint), 1.5))
                continue;
            m_HCProbeBuildingPaths = m_HCProbeBuildingPaths + 1;
            if (HCProbePath(entranceSampled, m_HCProbeSampled) < 1)
                continue;
            m_HCProbeEntrance = entranceSampled;
            m_HCProbeReachState = "tested";
            m_HCProbeReachEntrances = HCProbeVector(entrance);
        }
        m_HCProbeReachDoors = doorText;
    }

    int HCProbeReachHit(vector floorPos)
    {
        if (m_HCProbeReachState != "tested")
            return -1;
        if (m_HCProbeBuildingPaths >= m_HCProbePathLimit)
            return -1;
        m_HCProbeBuildingPaths = m_HCProbeBuildingPaths + 1;
        if (!HCProbeSampleMesh(floorPos, 1.5))
            return 2;
        if (false)
            return 2;
        vector candidate = m_HCProbeSampled;
        return HCProbePath(m_HCProbeEntrance, candidate);
    }

    void HCProbeRecordFloor(vector floorPos, float clearance, float dirY)
    {
        vector modelPos = m_HCProbeBuilding.CoordToLocal(floorPos);
        int code = -1;
        if (clearance >= 1.9)
            code = HCProbeReachHit(floorPos);
        string text = "[" + modelPos[0] + "," + modelPos[1] + "," + modelPos[2] + "," + clearance + "," + dirY + "," + code + "]";
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
        float hitY = 0.0;
        float dirY = 0.0;
        float clearance = 0.0;
        vector surfacePos;
        bool ended = false;
        int step = 0;
        int result = 0;
        for (step = 0; step < m_HCProbeHitLimit; step++)
        {
            if (startY <= bottomY)
            {
                ended = true;
                break;
            }
            result = HCProbeRay(Vector(baseWorld[0], startY, baseWorld[2]), Vector(baseWorld[0], bottomY, baseWorld[2]));
            if (result < 1)
            {
                ended = true;
                break;
            }
            hitY = m_HCProbeHitPos[1];
            dirY = m_HCProbeHitDir[1];
            startY = hitY - 0.05;
            if (result == 2)
            {
                m_HCProbeStatOther = m_HCProbeStatOther + 1;
                continue;
            }
            if (lastY - hitY < 0.25)
            {
                lastY = hitY;
                continue;
            }
            lastY = hitY;
            surfacePos = m_HCProbeHitPos;
            clearance = HCProbeClearance(surfacePos);
            if (clearance < 0.0)
            {
                m_HCProbeStatExterior = m_HCProbeStatExterior + 1;
                continue;
            }
            m_HCProbeStatInterior = m_HCProbeStatInterior + 1;
            HCProbeRecordFloor(surfacePos, clearance, dirY);
        }
        if (!ended)
            m_HCProbeStatHitCapped = m_HCProbeStatHitCapped + 1;
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
        m_HCProbeStatHitCapped = 0;
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
        text = text + "{" + HCProbeKey("i") + m_HCProbeCursor + "," + HCProbeKey("class") + HCProbeStr(expectedType) + "," + HCProbeKey("role") + HCProbeStr(m_HCProbeRoles.Get(m_HCProbeCursor)) + ",";
        text = text + HCProbeKey("found") + HCProbeBool(found) + "," + HCProbeKey("actual") + HCProbeVector(actualPos) + "," + HCProbeKey("distance") + distance + "," + HCProbeKey("orientation") + HCProbeVector(orientation) + ",";
        text = text + HCProbeKey("box_source") + HCProbeStr(m_HCProbeBoxSource) + "," + HCProbeKey("box_min") + HCProbeVector(m_HCProbeBoxMin) + "," + HCProbeKey("box_max") + HCProbeVector(m_HCProbeBoxMax) + ",";
        text = text + HCProbeKey("grid") + "{" + HCProbeKey("step") + m_HCProbeGridStep + "," + HCProbeKey("rows") + m_HCProbeRows + "," + HCProbeKey("cols") + m_HCProbeCols + "},";
        text = text + HCProbeKey("reach") + "{" + HCProbeKey("state") + HCProbeStr(m_HCProbeReachState) + "," + HCProbeKey("doors") + "[" + m_HCProbeReachDoors + "]," + HCProbeKey("entrances") + "[" + m_HCProbeReachEntrances + "]},";
        text = text + HCProbeKey("hits") + "[";
        HCProbeEmit(text);
    }

    void HCProbeEndBuilding()
    {
        string text = "]," + HCProbeKey("stats") + "{" + HCProbeKey("columns") + m_HCProbeStatColumns + "," + HCProbeKey("rays") + m_HCProbeBuildingRays + "," + HCProbeKey("paths") + m_HCProbeBuildingPaths + ",";
        text = text + HCProbeKey("ray_capped") + HCProbeBool(m_HCProbeRayCapped) + "," + HCProbeKey("output_capped") + HCProbeBool(m_HCProbeOutputCapped) + ",";
        text = text + HCProbeKey("interior_hits") + m_HCProbeStatInterior + "," + HCProbeKey("exterior_hits") + m_HCProbeStatExterior + "," + HCProbeKey("other_hits") + m_HCProbeStatOther + ",";
        text = text + HCProbeKey("hit_capped_columns") + m_HCProbeStatHitCapped + "}}";
        HCProbeEmit(text);
        m_HCProbeCursor = m_HCProbeCursor + 1;
        m_HCProbePhase = 0;
    }

    void HCProbeFinish()
    {
        string text = "]," + HCProbeKey("summary") + "{" + HCProbeKey("targets") + m_HCProbeClasses.Count() + "," + HCProbeKey("found") + m_HCProbeFoundCount + "," + HCProbeKey("complete") + "true,";
        text = text + HCProbeKey("run_rays") + m_HCProbeRunRays + "," + HCProbeKey("begin_ms") + m_HCProbeBeginMs + "," + HCProbeKey("end_ms") + GetGame().GetTime() + "}}";
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
        FPrintln(sentinel, "rows=" + m_HCProbeClasses.Count() + " found=" + m_HCProbeFoundCount);
        CloseFile(sentinel);
        Print("[HC Interior Sampler] rows=" + m_HCProbeClasses.Count() + " found=" + m_HCProbeFoundCount);
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
        string directory = "$profile:HCCEProbe";
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
        Print("[HC Interior Sampler] BEGIN; observation only; targets=" + m_HCProbeClasses.Count());
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
                path_limit=DEFAULT_PATH_LIMIT, output_limit=DEFAULT_OUTPUT_LIMIT, intersect="geom"):
    """Return the generated Enforce text (bytes) with every target and limit inlined as literal data."""
    if not targets or len(targets) > MAX_TARGETS:
        raise ValueError(f"1..{MAX_TARGETS} targets required")
    _bounded("sample delay", sample_delay_s, *SAMPLE_DELAY_RANGE)
    _bounded("run ray limit", run_ray_limit, *RUN_RAY_RANGE)
    _bounded("building ray limit", building_ray_limit, *BUILDING_RAY_RANGE)
    _bounded("hit limit", hit_limit, *HIT_LIMIT_RANGE)
    _bounded("path limit", path_limit, *PATH_LIMIT_RANGE)
    _bounded("output limit", output_limit, *OUTPUT_LIMIT_RANGE)
    if intersect not in INTERSECTS:
        raise ValueError("intersect must be one of " + ", ".join(sorted(INTERSECTS)))
    adds = []
    for target in targets:
        name, role, pos = target["class"], target["role"], target["pos"]
        if not probe.IDENT_RULE.match(name) or not probe.ROLE_RULE.match(role):
            raise ValueError("target class/role must be plain identifiers")
        if len(pos) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) and abs(v) < 1e6 for v in pos):
            raise ValueError("target position must be three bounded finite numbers")
        adds.append('        HCProbeAdd("%s", "%s", %.6f, %.6f, %.6f);' % (name, role, *pos))
    chunks = [adds[i:i + LOADER_CHUNK] for i in range(0, len(adds), LOADER_CHUNK)]
    calls = "\n".join(f"        HCProbeLoadTargets{n}();" for n in range(len(chunks)))
    loaders = "".join("    void HCProbeLoadTargets%d()\n    {\n%s\n    }\n\n" % (n, "\n".join(chunk))
                      for n, chunk in enumerate(chunks))
    head = HOOK_HEAD
    for placeholder, value in (("@@LOADER_CALLS@@", calls), ("@@START_MS@@", str(sample_delay_s * 1000)),
                               ("@@GRID_STEP@@", repr(GRID_STEP)), ("@@HIT_LIMIT@@", str(hit_limit)),
                               ("@@BUILDING_RAY_LIMIT@@", str(building_ray_limit)),
                               ("@@RUN_RAY_LIMIT@@", str(run_ray_limit)), ("@@PATH_LIMIT@@", str(path_limit)),
                               ("@@OUTPUT_LIMIT@@", str(output_limit))):
        head = head.replace(placeholder, value)
    tail = HOOK_TAIL.replace("@@INTERSECT@@", INTERSECTS[intersect])
    text = head + loaders + tail
    if "@@" in text:
        raise ValueError("unresolved placeholder in hook")
    if not text.isascii():
        raise ValueError("hook must be ASCII")
    return text.encode("ascii")


# ---------------------------------------------------------------------------
# Lint: the CE probe's observed compile-shape rules plus the sampler extras
# ---------------------------------------------------------------------------

_SAMPLER_OUT_CALLS = (("RaycastRV", (2, 3, 4)), ("SampleNavmeshPosition", (3,)), ("FindPath", (3,)))


def lint_sampler_hook(text, native_types=frozenset()):
    """Return a list of issues; empty means no observed-rejected shape was found."""
    issues = list(probe.lint_hook(text, native_types=native_types))
    clean = probe._clean(text)
    for number, line in enumerate(clean.splitlines(), 1):
        if re.search(r"\belse\b", line):
            issues.append(f"line {number}: 'else' is not allowed (the reference transpiler models none)")
    for header, body, _start in probe._function_bodies(clean):
        function = header.group(2)
        declared = [(m.start(2), m.group(2)) for m in probe._DECLARATION.finditer(body)
                    if m.group(1) not in probe._NOT_TYPES]
        for callee, positions in _SAMPLER_OUT_CALLS:
            for call in re.finditer(r"\b%s\s*\(" % callee, body):
                end, depth = call.end(), 1
                while end < len(body) and depth:
                    depth += {"(": 1, ")": -1}.get(body[end], 0)
                    end += 1
                args = probe._split_arguments(body[call.end():end - 1])
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
          building_ray_limit=DEFAULT_BUILDING_RAY_LIMIT, run_ray_limit=DEFAULT_RUN_RAY_LIMIT,
          path_limit=DEFAULT_PATH_LIMIT, output_limit=DEFAULT_OUTPUT_LIMIT,
          battleye_sha256=probe.BATTLEYE_SHA256, native_scripts=None, now=None, _wsl_parent=None):
    """Stage a fresh sampler runtime and write ce-probe-plan.json. Never launches anything.

    ``_wsl_parent`` is an internal test hook; the production parent is always probe.WSL_PARENT
    and the Windows root is always derived from the destination, never supplied.
    """
    source_runtime, destination = dm._safe_path(source_runtime), dm._safe_path(destination)
    if source_runtime == destination or source_runtime in destination.parents or destination in source_runtime.parents:
        raise ValueError("source/destination overlap forbidden")
    if destination.exists() or destination.is_symlink():
        raise ValueError("destination must be fresh; no overwrite")
    parent = Path(probe.WSL_PARENT if _wsl_parent is None else _wsl_parent)
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError(f"probe parent directory {parent} must exist and not be a symlink")
    windows_root = probe.windows_runtime_root(destination, parent)
    if not 5 <= wait_minutes <= 120 or not 1 <= per_class <= MAX_PER_CLASS:
        raise ValueError(f"wait minutes 5..120 and per-class 1..{MAX_PER_CLASS} required")
    source = probe._verify_source(source_runtime, battleye_sha256)
    names = {name for name, _role in SAMPLE_CLASSES}
    placements = probe.parse_placements(source["mapgrouppos"], wanted=names)
    missing = [name for name, _role in SAMPLE_CLASSES if not placements.get(name)]
    if missing:
        raise ValueError("stock mapgrouppos has no placements for: " + ", ".join(missing))
    targets = probe.build_targets(placements, classes=SAMPLE_CLASSES, per_class=per_class, hard_cap=MAX_TARGETS)
    limits = {"sample_delay_s": sample_delay_s, "run_ray_limit": run_ray_limit,
              "building_ray_limit": building_ray_limit, "hit_limit": hit_limit, "path_limit": path_limit,
              "output_limit": output_limit, "intersect": intersect}
    hook = render_hook(targets, **limits)
    native = probe.native_type_names(native_scripts) if native_scripts else frozenset()
    problems = lint_sampler_hook(hook.decode("ascii"), native_types=native)
    if problems:
        raise ValueError("generated hook violates native compile rules: " + "; ".join(problems[:3]))

    mission_dest = destination / "mpmissions" / probe.MISSION_NAME
    manifest = dm.prepare_diagnostic_mission(source["mission"], mission_dest, purpose="ce-probe", hook=hook)
    for name in ("storage", "profiles", "battleye"):
        (destination / name).mkdir(exist_ok=False)
    probe._new_file(destination / "serverDZ.cfg", source["config"].read_bytes())
    probe._new_file(destination / "battleye/BEServer_x64.dll", source["battleye"].read_bytes())

    staged = []
    for path in sorted(p for p in destination.rglob("*") if p.is_file()):
        digest, size = probe._hash_file(path)
        staged.append({"path": path.relative_to(destination).as_posix(), "sha256": digest, "bytes": size})
    staged_hash = {entry["path"]: entry["sha256"] for entry in staged}
    mission_files = []
    for name, record in sorted(source["records"].items()):
        entry = dict(record)
        entry["sha256"] = staged_hash[f"mpmissions/{probe.MISSION_NAME}/{name}"]
        if manifest["files"][name]["source_sha256"] != record["source_sha256"]:
            raise ValueError(f"source changed while staging: {name}")
        entry["origin"] = "instrumented" if name == "init.c" else "stock-copy"
        mission_files.append(entry)

    classes = [{"class": name, "role": role, "available": len(placements.get(name, [])),
                "sampled": sum(1 for t in targets if t["class"] == name)} for name, role in SAMPLE_CLASSES]
    windows_mission = f"{windows_root}\\mpmissions\\{probe.MISSION_NAME}"
    port = probe.PORT
    plan = {
        "schema_version": 1, "kind": "ce-probe", "status": "staged-only-not-launched",
        "staged_utc": (now or datetime.datetime.now(datetime.timezone.utc)).isoformat(),
        "variant": "control",
        "server_exe": probe.SERVER_EXE, "server_exe_sha256": probe.SERVER_EXE_SHA256,
        "working_directory": probe.SERVER_INSTALL,
        "port": port, "requested_bind": f"127.0.0.1:{port}",
        "runtime_root": windows_root, "mission": windows_mission,
        "storage": windows_root + "\\storage", "profiles": windows_root + "\\profiles",
        "battleye": windows_root + "\\battleye",
        "arguments": ["-ip=127.0.0.1", f"-port={port}", f"-config={windows_root}\\serverDZ.cfg",
                      f"-mission={windows_mission}", f"-storage={windows_root}\\storage",
                      f"-profiles={windows_root}\\profiles", f"-BEpath={windows_root}\\battleye",
                      "-doLogs", "-adminLog"],
        "source": {"runtime_wsl_path": str(source_runtime), "launch_plan_sha256": source["launch_plan_sha256"],
                   "config_sha256": staged_hash["serverDZ.cfg"], "battleye_sha256": battleye_sha256},
        "treatment": None,
        "probe": {"tool": "interior-sampler", "sample_delay_s": sample_delay_s, "per_class_limit": per_class,
                  "hard_cap": MAX_TARGETS, "target_count": len(targets), "hook_sha256": probe.sha256(hook),
                  "hook_bytes": len(hook), "wait_minutes": wait_minutes,
                  "census_relative_path": "profiles/HCCEProbe/census.json",
                  "sentinel_relative_path": "profiles/HCCEProbe/complete.txt"},
        "sampler": {"grid_step": GRID_STEP, "per_class": per_class, "intersect": intersect,
                    "hit_limit": hit_limit, "building_ray_limit": building_ray_limit,
                    "run_ray_limit": run_ray_limit, "path_limit": path_limit, "output_limit": output_limit},
        "target_classes": classes, "targets": targets,
        "mission_files": mission_files, "staged_files": staged,
    }
    with open(destination / probe.PLAN_NAME, "x", encoding="utf-8") as stream:
        json.dump(plan, stream, indent=2)
        stream.write("\n")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--destination", required=True, help="fresh runtime directory (must not exist)")
    parser.add_argument("--source-runtime", default=probe.DEFAULT_SOURCE_RUNTIME)
    parser.add_argument("--per-class", type=int, default=DEFAULT_PER_CLASS)
    parser.add_argument("--intersect", default="geom", help="raycast geometry: " + ", ".join(sorted(INTERSECTS)))
    parser.add_argument("--wait-minutes", type=int, default=DEFAULT_WAIT_MINUTES)
    parser.add_argument("--sample-delay-s", type=int, default=DEFAULT_SAMPLE_DELAY_S)
    parser.add_argument("--battleye-sha256", default=probe.BATTLEYE_SHA256)
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
    print(f"staged {plan['variant']} runtime: {Path(args.destination) / probe.PLAN_NAME}")
    print(f"targets={plan['probe']['target_count']} hook_bytes={plan['probe']['hook_bytes']} "
          f"hook_sha256={plan['probe']['hook_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
