

// Hollow Country DISPOSABLE interior floor sampler; observation only, no gameplay acceptance.
// Target placements are inlined literal data. Server only; runs once per process.
class HCDisposableDiagnosticMission : CustomMission
{
    protected bool m_HCProbeStarted = false;
    protected bool m_HCProbeWriteFailed = false;
    protected bool m_HCProbeRayCapped = false;
    protected bool m_HCProbeOutputCapped = false;
    protected string m_HCProbeQuote = "";
    protected string m_HCProbePath = "$profile:HCInteriorSampler/census.json";
    protected string m_HCProbeSentinel = "$profile:HCInteriorSampler/complete.txt";
    protected string m_HCProbePending = "";
    protected string m_HCProbeBoxSource = "none";
    protected string m_HCProbeReachState = "none";
    protected string m_HCProbeReachDoors = "";
    protected string m_HCProbeReachEntrances = "";
    protected float m_HCProbeGridStep = 1.0;
    protected float m_HCProbeSnapLimit = 0.5;
    protected float m_HCProbeEndTolerance = 0.5;
    protected float m_HCProbeSeedMargin = 1.0;
    protected float m_HCProbeProjectedMargin = 0.5;
    protected float m_HCProbeWaistHeight = 1.0;
    protected int m_HCProbeHitLimit = 24;
    protected int m_HCProbeBuildingRayLimit = 40000;
    protected int m_HCProbeRunRayLimit = 400000;
    protected int m_HCProbePathLimit = 3000;
    protected int m_HCProbeOutputLimit = 6000000;
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
    protected vector m_HCProbeSeed;
    protected vector m_HCProbeEntrance;

    override void OnInit()
    {
        super.OnInit();
        if (!GetGame() || !GetGame().IsServer() || m_HCProbeStarted)
            return;
        m_HCProbeStarted = true;
        int quoteCode = 34;
        m_HCProbeQuote = quoteCode.AsciiToString();
        HCProbeLoadTargets0();
        Print("[HC Interior Sampler] LOADED; targets=" + HCProbeInt(m_HCProbeClasses.Count()));
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCProbeStart, 75000, false);
    }

    void HCProbeAdd(string className, string role, float x, float y, float z)
    {
        m_HCProbeClasses.Insert(className);
        m_HCProbeRoles.Insert(role);
        m_HCProbePositions.Insert(Vector(x, y, z));
    }

    void HCProbeLoadTargets0()
    {
        HCProbeAdd("Land_Tenement_Small", "tenement", 1031.500000, 111.500000, 2007.250000);
        HCProbeAdd("Land_Tenement_Small", "tenement", 1315.000000, 109.500000, 2645.250000);
        HCProbeAdd("Land_Tenement_Small", "tenement", 1598.500000, 107.500000, 2580.000000);
        HCProbeAdd("Land_Tenement_Small", "tenement", 1882.000000, 105.500000, 2514.750000);
        HCProbeAdd("Land_Tenement_Big", "tenement", 1031.500000, 111.500000, 2007.250000);
        HCProbeAdd("Land_Tenement_Big", "tenement", 1315.000000, 109.500000, 2645.250000);
        HCProbeAdd("Land_Tenement_Big", "tenement", 1598.500000, 107.500000, 2580.000000);
        HCProbeAdd("Land_Tenement_Big", "tenement", 1882.000000, 105.500000, 2514.750000);
        HCProbeAdd("Land_HouseBlock_2F1", "calibration", 1031.500000, 111.500000, 2007.250000);
        HCProbeAdd("Land_HouseBlock_2F1", "calibration", 1315.000000, 109.500000, 2645.250000);
        HCProbeAdd("Land_HouseBlock_2F1", "calibration", 1598.500000, 107.500000, 2580.000000);
        HCProbeAdd("Land_HouseBlock_2F1", "calibration", 1882.000000, 105.500000, 2514.750000);
        HCProbeAdd("Land_Mil_Barracks2", "calibration", 1031.500000, 111.500000, 2007.250000);
        HCProbeAdd("Land_Mil_Barracks2", "calibration", 1315.000000, 109.500000, 2645.250000);
        HCProbeAdd("Land_Mil_Barracks2", "calibration", 1598.500000, 107.500000, 2580.000000);
        HCProbeAdd("Land_Mil_Barracks2", "calibration", 1882.000000, 105.500000, 2514.750000);
    }


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
        bool hit = DayZPhysics.RaycastRV(rayFrom, rayTo, contactPos, contactDir, contactComponent, hitObjects, null, null, false, false, ObjIntersectGeom);
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

    bool HCProbeOpenSky(vector pointPos)
    {
        float startY = pointPos[1] + 0.05;
        float endY = pointPos[1] + (m_HCProbeBoxMax[1] - m_HCProbeBoxMin[1]) + 2.0;
        int result = 0;
        int attempt = 0;
        for (attempt = 0; attempt < 4; attempt++)
        {
            result = HCProbeRay(Vector(pointPos[0], startY, pointPos[2]), Vector(pointPos[0], endY, pointPos[2]));
            if (result == 0)
                return true;
            if (result != 2)
                return false;
            startY = m_HCProbeHitPos[1] + 0.05;
            if (startY >= endY)
                return true;
        }
        return false;
    }

    bool HCProbeBlocked(vector fromPos, vector toPos)
    {
        int result = HCProbeRay(fromPos, toPos);
        if (result == 0)
            return false;
        if (result == 2)
            return false;
        return true;
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
        TVectorArray waypoints = new TVectorArray;
        bool found = GetGame().GetWorld().GetAIWorld().FindPath(startPos, endPos, m_HCProbeFilter, waypoints);
        if (!found)
            return 0;
        if (waypoints.Count() < 2)
            return 0;
        vector finalPoint = waypoints.Get(waypoints.Count() - 1);
        float gap = vector.Distance(finalPoint, goalPos);
        if (gap <= m_HCProbeEndTolerance)
            return 1;
        return 0;
    }

    bool HCProbeSeedOutside(vector doorPos, float unitX, float unitZ)
    {
        float standoff = 2.0;
        int attempt = 0;
        for (attempt = 0; attempt < 3; attempt++)
        {
            m_HCProbeSeed = Vector(doorPos[0] + unitX * standoff, doorPos[1], doorPos[2] + unitZ * standoff);
            if (HCProbeOutsideBox(m_HCProbeSeed, m_HCProbeSeedMargin))
                return true;
            standoff = standoff + 2.0;
        }
        return false;
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
        vector farPoint;
        vector entranceSampled;
        vector farSampled;
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
            if (!HCProbeSeedOutside(doorPos, unitX, unitZ))
                continue;
            if (!HCProbeTakePath())
            {
                m_HCProbeReachState = "path-budget";
                continue;
            }
            farPoint = Vector(doorPos[0] + unitX * 12.0, doorPos[1], doorPos[2] + unitZ * 12.0);
            if (!HCProbeSampleMesh(m_HCProbeBuilding.CoordToParent(m_HCProbeSeed), 1.5))
                continue;
            entranceSampled = m_HCProbeSampled;
            if (!HCProbeOutsideBox(m_HCProbeBuilding.CoordToLocal(entranceSampled), m_HCProbeProjectedMargin))
                continue;
            if (!HCProbeOpenSky(entranceSampled))
                continue;
            if (!HCProbeSampleMesh(m_HCProbeBuilding.CoordToParent(farPoint), 1.5))
                continue;
            farSampled = m_HCProbeSampled;
            if (HCProbePath(entranceSampled, farSampled, farSampled) < 1)
                continue;
            m_HCProbeEntrance = entranceSampled;
            m_HCProbeReachState = "tested";
            m_HCProbeReachEntrances = HCProbeVector(m_HCProbeSeed);
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
        if (shiftX * shiftX + shiftZ * shiftZ > 0.0025)
        {
            if (HCProbeBlocked(Vector(floorPos[0], waistY, floorPos[2]), Vector(candidate[0], waistY, candidate[2])))
                return 2;
        }
        return HCProbePath(m_HCProbeEntrance, candidate, floorPos);
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
        text = text + "{" + HCProbeKey("i") + HCProbeInt(m_HCProbeCursor) + "," + HCProbeKey("class") + HCProbeStr(expectedType) + ",";
        text = text + HCProbeKey("role") + HCProbeStr(m_HCProbeRoles.Get(m_HCProbeCursor)) + "," + HCProbeKey("found") + HCProbeBool(found) + ",";
        text = text + HCProbeKey("actual") + HCProbeVector(actualPos) + "," + HCProbeKey("distance") + HCProbeNum(distance) + ",";
        text = text + HCProbeKey("orientation") + HCProbeVector(orientation) + "," + HCProbeKey("box_source") + HCProbeStr(m_HCProbeBoxSource) + ",";
        text = text + HCProbeKey("box_min") + HCProbeVector(m_HCProbeBoxMin) + "," + HCProbeKey("box_max") + HCProbeVector(m_HCProbeBoxMax) + ",";
        text = text + HCProbeKey("grid") + "{" + HCProbeKey("step") + HCProbeNum(m_HCProbeGridStep) + "," + HCProbeKey("rows") + HCProbeInt(m_HCProbeRows) + ",";
        text = text + HCProbeKey("cols") + HCProbeInt(m_HCProbeCols) + "},";
        text = text + HCProbeKey("reach") + "{" + HCProbeKey("state") + HCProbeStr(m_HCProbeReachState) + ",";
        text = text + HCProbeKey("doors") + "[" + m_HCProbeReachDoors + "]," + HCProbeKey("entrances") + "[" + m_HCProbeReachEntrances + "]},";
        text = text + HCProbeKey("hits") + "[";
        HCProbeEmit(text);
    }

    void HCProbeEndBuilding()
    {
        string text = "]," + HCProbeKey("stats") + "{" + HCProbeKey("columns") + HCProbeInt(m_HCProbeStatColumns) + ",";
        text = text + HCProbeKey("rays") + HCProbeInt(m_HCProbeBuildingRays) + "," + HCProbeKey("paths") + HCProbeInt(m_HCProbeBuildingPaths) + ",";
        text = text + HCProbeKey("ray_capped") + HCProbeBool(m_HCProbeRayCapped) + "," + HCProbeKey("output_capped") + HCProbeBool(m_HCProbeOutputCapped) + ",";
        text = text + HCProbeKey("interior_hits") + HCProbeInt(m_HCProbeStatInterior) + "," + HCProbeKey("exterior_hits") + HCProbeInt(m_HCProbeStatExterior) + ",";
        text = text + HCProbeKey("other_hits") + HCProbeInt(m_HCProbeStatOther) + "," + HCProbeKey("hit_capped_columns") + HCProbeInt(m_HCProbeStatHitCapped) + "}}";
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
        string directory = "$profile:HCInteriorSampler";
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
