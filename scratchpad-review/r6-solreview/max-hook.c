

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
    protected string m_HCProbeReachDetail = "";
    protected string m_HCProbePlayerState = "none";
    protected string m_HCProbePlayerEntrances = "";
    protected string m_HCProbePlayerAttempts = "";
    protected string m_HCProbePlayerDetail = "";
    protected string m_HCProbePlayerCodes = "";
    protected string m_HCProbeStrictCodes = "";
    protected string m_HCProbeOpenCodes = "";
    protected string m_HCProbeOpenPlayerCodes = "";
    protected string m_HCProbeOpenState = "none";
    protected string m_HCProbePlayerOpenState = "none";
    protected string m_HCProbeOpenAttempts = "";
    protected string m_HCProbePlayerOpenAttempts = "";
    protected string m_HCProbeDoorText = "";
    protected string m_HCProbeDoorState = "none";
    protected string m_HCProbeFrameText = "";
    protected string m_HCProbeDetailText = "{}";
    protected string m_HCProbeDiagType = "";
    protected string m_HCProbeFreeType = "";
    protected float m_HCProbeGridStep = 1.0;
    protected float m_HCProbeSnapLimit = 0.5;
    protected float m_HCProbeEndTolerance = 0.5;
    protected float m_HCProbeSeedMargin = 1.0;
    protected float m_HCProbeProjectedMargin = 0.5;
    protected float m_HCProbeWaistHeight = 1.0;
    protected float m_HCProbeVerticalAllowance = 0.25;
    protected float m_HCProbeTrivialShift = 0.01;
    protected float m_HCProbeClearRequired = 1.9;
    protected float m_HCProbeFreeClear = 0.0;
    protected float m_HCProbeDiagHSnap = -1.0;
    protected float m_HCProbeDiagVSnap = -1.0;
    protected float m_HCProbeDiagHGap = -1.0;
    protected float m_HCProbeDiagVGap = -1.0;
    protected int m_HCProbeHitLimit = 24;
    protected int m_HCProbeStepLimit = 64;
    protected int m_HCProbeBuildingRayLimit = 150000;
    protected int m_HCProbeRunRayLimit = 2500000;
    protected int m_HCProbePathLimit = 3000;
    protected int m_HCProbeOutputLimit = 6000000;
    protected int m_HCProbeDoorDelayTicks = 30;
    protected int m_HCProbeDoorSettleTicks = 30;
    protected int m_HCProbeOpenFloorChunk = 100;
    protected int m_HCProbeDoorCount = 0;
    protected int m_HCProbeDoorLocked = 0;
    protected int m_HCProbeDoorOpenStart = 0;
    protected int m_HCProbeDoorAjarStart = 0;
    protected int m_HCProbeDoorMovingStart = 0;
    protected int m_HCProbeSettleUsed = 0;
    protected int m_HCProbeOpenSettle = 0;
    protected int m_HCProbeCloseSettle = 0;
    protected int m_HCProbeDoorsObserved = 0;
    protected int m_HCProbeDoorsRestored = 0;
    protected int m_HCProbeDoorDelay = 0;
    protected int m_HCProbeWaitNext = 0;
    protected int m_HCProbeOpenIndex = 0;
    protected int m_HCProbeOpenPaths = 0;
    protected int m_HCProbeOpenPlayerPaths = 0;
    protected int m_HCProbeEnterPaths = 0;
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
    protected int m_HCProbePlayerPaths = 0;
    protected int m_HCProbeDiagWaypoints = 0;
    protected int m_HCProbeDiagRel = 0;
    protected int m_HCProbeFreeRel = 0;
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
    protected float m_HCProbeFrameY = 0.0;
    protected string m_HCProbeHitType = "";
    protected string m_HCProbeReachAttempts = "";
    protected string m_HCProbeDiag = "";
    protected ref array<string> m_HCProbeTypeNames = new array<string>;
    protected ref array<int> m_HCProbeTypeCounts = new array<int>;
    protected ref array<string> m_HCProbeClasses = new array<string>;
    protected ref array<string> m_HCProbeRoles = new array<string>;
    protected ref array<vector> m_HCProbePositions = new array<vector>;
    protected ref array<int> m_HCProbeReachCounts = new array<int>;
    protected ref array<string> m_HCProbeReachSamples = new array<string>;
    protected ref array<int> m_HCProbeOpenedDoors = new array<int>;
    protected ref array<string> m_HCProbeEntered = new array<string>;
    protected ref array<vector> m_HCProbeOpenPos = new array<vector>;
    protected ref array<float> m_HCProbeOpenFree = new array<float>;
    protected ref array<float> m_HCProbeOpenClear = new array<float>;
    protected ref array<int> m_HCProbeOpenCap = new array<int>;
    protected ref array<string> m_HCProbeFrameClasses = new array<string>;
    protected ref array<vector> m_HCProbeFramePos = new array<vector>;
    protected ref array<vector> m_HCProbeColPos = new array<vector>;
    protected ref array<float> m_HCProbeColClear = new array<float>;
    protected ref array<float> m_HCProbeColFree = new array<float>;
    protected ref array<float> m_HCProbeColDir = new array<float>;
    protected ref array<int> m_HCProbeColRel = new array<int>;
    protected ref array<string> m_HCProbeColType = new array<string>;
    protected ref PGFilter m_HCProbeFilter;
    protected ref PGFilter m_HCProbePlayerFilter;
    protected PGFilter m_HCProbeUsedFilter;
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
    protected vector m_HCProbePlayerEntrance;
    protected vector m_HCProbeOpenEntrance;
    protected vector m_HCProbeUsedEntrance;
    protected vector m_HCProbePlayerOpenEntrance;
    protected vector m_HCProbeAttemptEntrance;
    protected vector m_HCProbeDiagSampled;
    protected vector m_HCProbeDiagFinal;

    override void OnInit()
    {
        super.OnInit();
        if (!GetGame() || !GetGame().IsServer() || m_HCProbeStarted)
            return;
        m_HCProbeStarted = true;
        int quoteCode = 34;
        m_HCProbeQuote = quoteCode.AsciiToString();
        HCProbeLoadTargets0();
        HCProbeLoadTargets1();
        HCProbeLoadFrame0();
        HCProbeLoadFrame1();
        Print("[HC Interior Sampler] LOADED; targets=" + HCProbeInt(m_HCProbeClasses.Count()));
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCProbeStart, 75000, false);
    }

    void HCProbeAdd(string className, string role, float x, float y, float z)
    {
        m_HCProbeClasses.Insert(className);
        m_HCProbeRoles.Insert(role);
        m_HCProbePositions.Insert(Vector(x, y, z));
    }

    void HCProbeFrameAdd(string className, float x, float y, float z)
    {
        m_HCProbeFrameClasses.Insert(className);
        m_HCProbeFramePos.Insert(Vector(x, y, z));
    }

    void HCProbeLoadTargets0()
    {
        HCProbeAdd("Land_Tenement_Small", "tenement", 1000.000000, 100.500000, 2000.000000);
        HCProbeAdd("Land_Tenement_Small", "tenement", 1031.500000, 111.500000, 2007.250000);
        HCProbeAdd("Land_Tenement_Small", "tenement", 1105.000000, 103.500000, 2449.500000);
        HCProbeAdd("Land_Tenement_Small", "tenement", 1210.000000, 106.500000, 2195.750000);
        HCProbeAdd("Land_Tenement_Small", "tenement", 1315.000000, 109.500000, 2645.250000);
        HCProbeAdd("Land_Tenement_Small", "tenement", 1388.500000, 101.500000, 2384.250000);
        HCProbeAdd("Land_Tenement_Small", "tenement", 1493.500000, 104.500000, 2130.500000);
        HCProbeAdd("Land_Tenement_Small", "tenement", 1598.500000, 107.500000, 2580.000000);
        HCProbeAdd("Land_Tenement_Small", "tenement", 1703.500000, 110.500000, 2326.250000);
        HCProbeAdd("Land_Tenement_Small", "tenement", 1777.000000, 102.500000, 2065.250000);
        HCProbeAdd("Land_Tenement_Small", "tenement", 1882.000000, 105.500000, 2514.750000);
        HCProbeAdd("Land_Tenement_Small", "tenement", 1987.000000, 108.500000, 2261.000000);
        HCProbeAdd("Land_Tenement_Big", "tenement", 1000.000000, 100.500000, 2000.000000);
        HCProbeAdd("Land_Tenement_Big", "tenement", 1031.500000, 111.500000, 2007.250000);
        HCProbeAdd("Land_Tenement_Big", "tenement", 1105.000000, 103.500000, 2449.500000);
        HCProbeAdd("Land_Tenement_Big", "tenement", 1210.000000, 106.500000, 2195.750000);
        HCProbeAdd("Land_Tenement_Big", "tenement", 1315.000000, 109.500000, 2645.250000);
        HCProbeAdd("Land_Tenement_Big", "tenement", 1388.500000, 101.500000, 2384.250000);
        HCProbeAdd("Land_Tenement_Big", "tenement", 1493.500000, 104.500000, 2130.500000);
        HCProbeAdd("Land_Tenement_Big", "tenement", 1598.500000, 107.500000, 2580.000000);
        HCProbeAdd("Land_Tenement_Big", "tenement", 1703.500000, 110.500000, 2326.250000);
        HCProbeAdd("Land_Tenement_Big", "tenement", 1777.000000, 102.500000, 2065.250000);
        HCProbeAdd("Land_Tenement_Big", "tenement", 1882.000000, 105.500000, 2514.750000);
        HCProbeAdd("Land_Tenement_Big", "tenement", 1987.000000, 108.500000, 2261.000000);
        HCProbeAdd("Land_HouseBlock_2F1", "calibration", 1000.000000, 100.500000, 2000.000000);
        HCProbeAdd("Land_HouseBlock_2F1", "calibration", 1031.500000, 111.500000, 2007.250000);
        HCProbeAdd("Land_HouseBlock_2F1", "calibration", 1105.000000, 103.500000, 2449.500000);
        HCProbeAdd("Land_HouseBlock_2F1", "calibration", 1210.000000, 106.500000, 2195.750000);
        HCProbeAdd("Land_HouseBlock_2F1", "calibration", 1315.000000, 109.500000, 2645.250000);
        HCProbeAdd("Land_HouseBlock_2F1", "calibration", 1388.500000, 101.500000, 2384.250000);
        HCProbeAdd("Land_HouseBlock_2F1", "calibration", 1493.500000, 104.500000, 2130.500000);
        HCProbeAdd("Land_HouseBlock_2F1", "calibration", 1598.500000, 107.500000, 2580.000000);
        HCProbeAdd("Land_HouseBlock_2F1", "calibration", 1703.500000, 110.500000, 2326.250000);
        HCProbeAdd("Land_HouseBlock_2F1", "calibration", 1777.000000, 102.500000, 2065.250000);
        HCProbeAdd("Land_HouseBlock_2F1", "calibration", 1882.000000, 105.500000, 2514.750000);
        HCProbeAdd("Land_HouseBlock_2F1", "calibration", 1987.000000, 108.500000, 2261.000000);
        HCProbeAdd("Land_Mil_Barracks2", "calibration", 1000.000000, 100.500000, 2000.000000);
        HCProbeAdd("Land_Mil_Barracks2", "calibration", 1031.500000, 111.500000, 2007.250000);
        HCProbeAdd("Land_Mil_Barracks2", "calibration", 1105.000000, 103.500000, 2449.500000);
        HCProbeAdd("Land_Mil_Barracks2", "calibration", 1210.000000, 106.500000, 2195.750000);
    }

    void HCProbeLoadTargets1()
    {
        HCProbeAdd("Land_Mil_Barracks2", "calibration", 1315.000000, 109.500000, 2645.250000);
        HCProbeAdd("Land_Mil_Barracks2", "calibration", 1388.500000, 101.500000, 2384.250000);
        HCProbeAdd("Land_Mil_Barracks2", "calibration", 1493.500000, 104.500000, 2130.500000);
        HCProbeAdd("Land_Mil_Barracks2", "calibration", 1598.500000, 107.500000, 2580.000000);
        HCProbeAdd("Land_Mil_Barracks2", "calibration", 1703.500000, 110.500000, 2326.250000);
        HCProbeAdd("Land_Mil_Barracks2", "calibration", 1777.000000, 102.500000, 2065.250000);
        HCProbeAdd("Land_Mil_Barracks2", "calibration", 1882.000000, 105.500000, 2514.750000);
        HCProbeAdd("Land_Mil_Barracks2", "calibration", 1987.000000, 108.500000, 2261.000000);
    }

    void HCProbeLoadFrame0()
    {
        HCProbeFrameAdd("Land_HouseBlock_2F1", 0.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 1.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 2.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 3.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 4.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 5.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 6.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 7.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 8.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 9.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 10.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 11.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 12.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 13.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 14.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 15.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 16.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 17.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 18.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 19.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 20.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 21.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 22.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 23.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 24.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 25.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 26.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 27.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 28.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 29.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 30.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_HouseBlock_2F1", 31.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 0.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 1.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 2.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 3.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 4.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 5.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 6.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 7.000000, 0.000000, 1.000000);
    }

    void HCProbeLoadFrame1()
    {
        HCProbeFrameAdd("Land_Mil_Barracks2", 8.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 9.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 10.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 11.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 12.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 13.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 14.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 15.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 16.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 17.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 18.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 19.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 20.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 21.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 22.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 23.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 24.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 25.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 26.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 27.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 28.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 29.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 30.000000, 0.000000, 1.000000);
        HCProbeFrameAdd("Land_Mil_Barracks2", 31.000000, 0.000000, 1.000000);
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

    bool HCProbeTakePath(int variant)
    {
        if (variant == 3)
        {
            if (m_HCProbeOpenPlayerPaths >= m_HCProbePathLimit)
                return false;
            m_HCProbeOpenPlayerPaths = m_HCProbeOpenPlayerPaths + 1;
            return true;
        }
        if (variant == 2)
        {
            if (m_HCProbeOpenPaths >= m_HCProbePathLimit)
                return false;
            m_HCProbeOpenPaths = m_HCProbeOpenPaths + 1;
            return true;
        }
        if (variant == 1)
        {
            if (m_HCProbePlayerPaths >= m_HCProbePathLimit)
                return false;
            m_HCProbePlayerPaths = m_HCProbePlayerPaths + 1;
            return true;
        }
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
        bool hit = DayZPhysics.RaycastRV(rayFrom, rayTo, contactPos, contactDir, contactComponent, hitObjects, null, null, false, false, ObjIntersectGeom);
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
        m_HCProbeFreeClear = 0.0;
        m_HCProbeFreeRel = 0;
        m_HCProbeFreeType = "";
        for (attempt = 0; attempt < 16; attempt++)
        {
            if (startY >= endY)
                return -1.0;
            result = HCProbeRay(Vector(surfacePos[0], startY, surfacePos[2]), Vector(surfacePos[0], endY, surfacePos[2]));
            if (result < 1)
                return -1.0;
            hitY = m_HCProbeHitPos[1];
            if (attempt == 0)
            {
                m_HCProbeFreeClear = hitY - surfacePos[1];
                m_HCProbeFreeRel = m_HCProbeHitRel;
                m_HCProbeFreeType = m_HCProbeHitType;
            }
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
        head = head + HCProbeKey("filters") + "{" + HCProbeKey("flags") + "{" + HCProbeFlagsText() + "},";
        head = head + HCProbeKey("strict") + HCProbeFilterText(m_HCProbeFilter) + ",";
        head = head + HCProbeKey("player") + HCProbeFilterText(m_HCProbePlayerFilter) + "},";
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
        if (!m_HCProbePlayerFilter)
            return false;
        return true;
    }

    bool HCProbeSampleMesh(vector position, float radius, PGFilter meshFilter)
    {
        vector sampled;
        bool found = GetGame().GetWorld().GetAIWorld().SampleNavmeshPosition(position, radius, meshFilter, sampled);
        if (!found)
            return false;
        m_HCProbeSampled = sampled;
        return true;
    }

    int HCProbePath(vector startPos, vector endPos, vector goalPos, PGFilter meshFilter)
    {
        m_HCProbePathCount = 0;
        m_HCProbePathGap = 0.0;
        TVectorArray waypoints = new TVectorArray;
        bool found = GetGame().GetWorld().GetAIWorld().FindPath(startPos, endPos, meshFilter, waypoints);
        if (!found)
            return 1;
        m_HCProbePathCount = waypoints.Count();
        m_HCProbeDiagWaypoints = waypoints.Count();
        if (waypoints.Count() < 2)
            return 2;
        vector finalPoint = waypoints.Get(waypoints.Count() - 1);
        m_HCProbeDiagFinal = m_HCProbeBuilding.CoordToLocal(finalPoint);
        m_HCProbePathGap = vector.Distance(finalPoint, goalPos);
        float gapX = goalPos[0] - finalPoint[0];
        float gapZ = goalPos[2] - finalPoint[2];
        m_HCProbeDiagHGap = Math.Sqrt(gapX * gapX + gapZ * gapZ);
        m_HCProbeDiagVGap = Math.AbsFloat(goalPos[1] - finalPoint[1]);
        if (m_HCProbeDiagHGap > m_HCProbeEndTolerance)
            return 3;
        if (m_HCProbeDiagVGap > m_HCProbeVerticalAllowance)
            return 3;
        if (m_HCProbeDiagHGap > m_HCProbeTrivialShift)
        {
            float waistY = goalPos[1] + m_HCProbeWaistHeight;
            if (HCProbeBlocked(Vector(finalPoint[0], waistY, finalPoint[2]), Vector(goalPos[0], waistY, goalPos[2])))
            {
                m_HCProbeDiagRel = m_HCProbeHitRel;
                m_HCProbeDiagType = m_HCProbeHitType;
                return 4;
            }
            return 6;
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
            standoff = standoff + 1.0;
        }
        return false;
    }

    string HCProbeVariantState(int variant)
    {
        if (variant == 1)
            return m_HCProbePlayerState;
        if (variant == 2)
            return m_HCProbeOpenState;
        if (variant == 3)
            return m_HCProbePlayerOpenState;
        return m_HCProbeReachState;
    }

    void HCProbeSetState(int variant, string state)
    {
        if (variant == 0)
            m_HCProbeReachState = state;
        if (variant == 1)
            m_HCProbePlayerState = state;
        if (variant == 2)
            m_HCProbeOpenState = state;
        if (variant == 3)
            m_HCProbePlayerOpenState = state;
    }

    void HCProbeUseEntrance(int variant)
    {
        m_HCProbeUsedEntrance = m_HCProbeEntrance;
        if (variant == 1)
            m_HCProbeUsedEntrance = m_HCProbePlayerEntrance;
        if (variant == 2)
            m_HCProbeUsedEntrance = m_HCProbeOpenEntrance;
        if (variant == 3)
            m_HCProbeUsedEntrance = m_HCProbePlayerOpenEntrance;
    }

    void HCProbeSetEntrance(int variant, vector entrance)
    {
        if (variant == 0)
            m_HCProbeEntrance = entrance;
        if (variant == 1)
            m_HCProbePlayerEntrance = entrance;
        if (variant == 2)
            m_HCProbeOpenEntrance = entrance;
        if (variant == 3)
            m_HCProbePlayerOpenEntrance = entrance;
    }

    void HCProbeUseFilter(int variant)
    {
        m_HCProbeUsedFilter = m_HCProbeFilter;
        if (variant == 1 || variant == 3)
            m_HCProbeUsedFilter = m_HCProbePlayerFilter;
    }

    int HCProbeReachAttempt(int variant, vector doorPos, float dirX, float dirZ)
    {
        HCProbeUseFilter(variant);
        PGFilter meshFilter = m_HCProbeUsedFilter;
        HCProbeDiagReset();
        m_HCProbeDetailText = "{}";
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
        if (!HCProbeTakePath(variant))
            return 3;
        if (!HCProbeSampleMesh(m_HCProbeSeedWorld, 1.5, meshFilter))
        {
            HCProbeControlDetail(4, m_HCProbeSeedWorld);
            return 4;
        }
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
        if (!HCProbeSampleMesh(Vector(farWorld[0], farGround, farWorld[2]), 1.5, meshFilter))
            return 7;
        vector farSampled = m_HCProbeSampled;
        m_HCProbeDiagSampled = m_HCProbeBuilding.CoordToLocal(farSampled);
        int stage = HCProbePath(entranceSampled, farSampled, farSampled, meshFilter);
        m_HCProbeAttemptA = m_HCProbePathCount;
        m_HCProbeAttemptB = m_HCProbePathGap;
        if (stage != 5 && stage != 6)
        {
            HCProbeControlDetail(7 + stage, farSampled);
            return 7 + stage;
        }
        m_HCProbeAttemptEntrance = entranceSampled;
        return 12;
    }

    bool HCProbeEnteredCheck(int variant, vector doorPos, float dirX, float dirZ, vector entrance)
    {
        if (m_HCProbeEnterPaths >= 64)
            return false;
        float dirLength = Math.Sqrt(dirX * dirX + dirZ * dirZ);
        if (dirLength < 0.1)
            return false;
        vector insideModel = Vector(doorPos[0] - dirX / dirLength, 0.0, doorPos[2] - dirZ / dirLength);
        if (HCProbeOutsideBox(insideModel, 0.0))
            return false;
        vector insideWorld = m_HCProbeBuilding.CoordToParent(insideModel);
        float ground = GetGame().SurfaceY(insideWorld[0], insideWorld[2]);
        HCProbeUseFilter(variant);
        PGFilter meshFilter = m_HCProbeUsedFilter;
        m_HCProbeEnterPaths = m_HCProbeEnterPaths + 1;
        if (!HCProbeSampleMesh(Vector(insideWorld[0], ground, insideWorld[2]), 1.5, meshFilter))
            return false;
        vector insideSampled = m_HCProbeSampled;
        vector insideLocal = m_HCProbeBuilding.CoordToLocal(insideSampled);
        if (HCProbeOutsideBox(insideLocal, 0.0))
            return false;
        m_HCProbeDiagFinal = Vector(0.0, 0.0, 0.0);
        int stage = HCProbePath(entrance, insideSampled, insideSampled, meshFilter);
        if (stage != 5 && stage != 6)
            return false;
        if (HCProbeOutsideBox(m_HCProbeDiagFinal, 0.0))
            return false;
        return true;
    }

    void HCProbeReachNote(int variant, int door, int stage)
    {
        string entry = "[" + HCProbeInt(door) + "," + HCProbeNum(m_HCProbeStandoff) + "," + HCProbeInt(stage) + ",";
        entry = entry + HCProbeVector(m_HCProbeSeed) + "," + HCProbeVector(m_HCProbeSampledModel) + ",";
        entry = entry + HCProbeNum(m_HCProbeAttemptA) + "," + HCProbeNum(m_HCProbeAttemptB) + "]";
        if (variant >= 2)
        {
            string openAttempts = m_HCProbeOpenAttempts;
            if (variant == 3)
                openAttempts = m_HCProbePlayerOpenAttempts;
            if (openAttempts.Length() > 0)
                openAttempts = openAttempts + ",";
            openAttempts = openAttempts + entry;
            if (variant == 2)
                m_HCProbeOpenAttempts = openAttempts;
            if (variant == 3)
                m_HCProbePlayerOpenAttempts = openAttempts;
            return;
        }
        string attempts = m_HCProbeReachAttempts;
        string detail = m_HCProbeReachDetail;
        if (variant == 1)
        {
            attempts = m_HCProbePlayerAttempts;
            detail = m_HCProbePlayerDetail;
        }
        if (attempts.Length() > 0)
            attempts = attempts + ",";
        if (detail.Length() > 0)
            detail = detail + ",";
        attempts = attempts + entry;
        detail = detail + m_HCProbeDetailText;
        if (variant == 0)
        {
            m_HCProbeReachAttempts = attempts;
            m_HCProbeReachDetail = detail;
        }
        if (variant == 1)
        {
            m_HCProbePlayerAttempts = attempts;
            m_HCProbePlayerDetail = detail;
        }
    }

    void HCProbeReachDoor(int variant, int door, float centreX, float centreZ)
    {
        string state = HCProbeVariantState(variant);
        string enteredState = m_HCProbeEntered.Get(variant);
        if (enteredState == "entered")
            return;
        vector doorPos = m_HCProbeBuilding.CoordToLocal(m_HCProbeBuilding.GetDoorSoundPos(door));
        float dirX = doorPos[0] - centreX;
        float dirZ = doorPos[2] - centreZ;
        int stage = HCProbeReachAttempt(variant, doorPos, dirX, dirZ);
        if (stage == 3 && state != "tested")
            state = "path-budget";
        HCProbeReachNote(variant, door, stage);
        if (stage == 12)
        {
            if (state != "tested")
            {
                HCProbeSetEntrance(variant, m_HCProbeAttemptEntrance);
                if (variant == 0)
                    m_HCProbeReachEntrances = HCProbeVector(m_HCProbeSeed);
                if (variant == 1)
                    m_HCProbePlayerEntrances = HCProbeVector(m_HCProbeSeed);
            }
            state = "tested";
            bool entered = HCProbeEnteredCheck(variant, doorPos, dirX, dirZ, m_HCProbeAttemptEntrance);
            if (entered)
            {
                HCProbeSetEntrance(variant, m_HCProbeAttemptEntrance);
                m_HCProbeEntered.Set(variant, "entered");
            }
            if (!entered)
                m_HCProbeEntered.Set(variant, "not-entered");
        }
        HCProbeSetState(variant, state);
    }

    int HCProbeDoorPhase(int door)
    {
        if (m_HCProbeBuilding.IsDoorClosed(door))
            return 0;
        if (m_HCProbeBuilding.IsDoorOpened(door))
            return 1;
        if (m_HCProbeBuilding.IsDoorOpenedAjar(door))
            return 2;
        return 3;
    }

    bool HCProbeDoorsSettled()
    {
        int wanted = 1;
        if (m_HCProbeWaitNext == 8)
            wanted = 0;
        int index = 0;
        int total = m_HCProbeOpenedDoors.Count();
        for (index = 0; index < total; index++)
        {
            if (HCProbeDoorPhase(m_HCProbeOpenedDoors.Get(index)) != wanted)
                return false;
        }
        return true;
    }

    void HCProbeReachSetup()
    {
        m_HCProbeReachState = "unavailable";
        m_HCProbePlayerState = "unavailable";
        m_HCProbeOpenState = "unavailable";
        m_HCProbePlayerOpenState = "unavailable";
        m_HCProbeReachDoors = "";
        m_HCProbeReachEntrances = "";
        m_HCProbeReachAttempts = "";
        m_HCProbeReachDetail = "";
        m_HCProbePlayerEntrances = "";
        m_HCProbePlayerAttempts = "";
        m_HCProbePlayerDetail = "";
        m_HCProbeDoorState = "mesh-unavailable";
        if (!HCProbeMeshAvailable())
            return;
        int doorCount = m_HCProbeBuilding.GetDoorCount();
        if (doorCount < 1)
        {
            m_HCProbeReachState = "no-door";
            m_HCProbePlayerState = "no-door";
            m_HCProbeOpenState = "no-door";
            m_HCProbePlayerOpenState = "no-door";
            m_HCProbeDoorState = "no-door";
            return;
        }
        if (doorCount > 64)
            doorCount = 64;
        m_HCProbeDoorCount = doorCount;
        m_HCProbeDoorState = "none";
        m_HCProbeReachState = "control-failed";
        m_HCProbePlayerState = "control-failed";
        m_HCProbeOpenState = "control-failed";
        m_HCProbePlayerOpenState = "control-failed";
        float centreX = (m_HCProbeBoxMin[0] + m_HCProbeBoxMax[0]) * 0.5;
        float centreZ = (m_HCProbeBoxMin[2] + m_HCProbeBoxMax[2]) * 0.5;
        string doorText = "";
        string recordText = "";
        int door = 0;
        int lockedFlag = 0;
        int openFlag = 0;
        int phaseCode = 0;
        vector doorPos;
        for (door = 0; door < doorCount; door++)
        {
            doorPos = m_HCProbeBuilding.CoordToLocal(m_HCProbeBuilding.GetDoorSoundPos(door));
            lockedFlag = 0;
            openFlag = 0;
            phaseCode = HCProbeDoorPhase(door);
            if (m_HCProbeBuilding.IsDoorLocked(door))
                lockedFlag = 1;
            if (phaseCode != 0)
                openFlag = 1;
            if (phaseCode == 1)
                m_HCProbeDoorOpenStart = m_HCProbeDoorOpenStart + 1;
            if (phaseCode == 2)
                m_HCProbeDoorAjarStart = m_HCProbeDoorAjarStart + 1;
            if (phaseCode == 3)
                m_HCProbeDoorMovingStart = m_HCProbeDoorMovingStart + 1;
            m_HCProbeDoorLocked = m_HCProbeDoorLocked + lockedFlag;
            if (door > 0)
            {
                doorText = doorText + ",";
                recordText = recordText + ",";
            }
            doorText = doorText + HCProbeVector(doorPos);
            recordText = recordText + "[" + HCProbeNum(doorPos[0]) + "," + HCProbeNum(doorPos[1]) + "," + HCProbeNum(doorPos[2]) + ",";
            recordText = recordText + HCProbeInt(lockedFlag) + "," + HCProbeInt(openFlag) + "," + HCProbeInt(phaseCode) + "]";
            HCProbeReachDoor(0, door, centreX, centreZ);
            HCProbeReachDoor(1, door, centreX, centreZ);
        }
        m_HCProbeReachDoors = doorText;
        m_HCProbeDoorText = recordText;
    }

    void HCProbeDiagReset()
    {
        m_HCProbeDiagSampled = Vector(0.0, 0.0, 0.0);
        m_HCProbeDiagFinal = Vector(0.0, 0.0, 0.0);
        m_HCProbeDiagHSnap = -1.0;
        m_HCProbeDiagVSnap = -1.0;
        m_HCProbeDiagHGap = -1.0;
        m_HCProbeDiagVGap = -1.0;
        m_HCProbeDiagWaypoints = 0;
        m_HCProbeDiagRel = 0;
        m_HCProbeDiagType = "";
    }

    string HCProbeReasonName(int reason)
    {
        if (reason == 0)
            return "sample_failed";
        if (reason == 1)
            return "snap_far";
        if (reason == 2)
            return "snap_blocked";
        if (reason == 3)
            return "path_not_found";
        if (reason == 4)
            return "path_too_short";
        if (reason == 5)
            return "gap_far";
        if (reason == 6)
            return "gap_blocked";
        if (reason == 7)
            return "reached";
        if (reason == 8)
            return "snap_unqualified";
        if (reason == 9)
            return "gap_unqualified";
        if (reason == 10)
            return "clearance_obstructed";
        if (reason == 11)
            return "column_capped";
        return "path_budget";
    }

    void HCProbeDiagSample(int variant, int reason, vector floorPos)
    {
        int slot = variant * 13 + reason;
        int seen = m_HCProbeReachCounts.Get(slot);
        m_HCProbeReachCounts.Set(slot, seen + 1);
        if (seen >= 8)
            return;
        vector floorModel = m_HCProbeBuilding.CoordToLocal(floorPos);
        string text = "[" + HCProbeVector(floorModel) + "," + HCProbeVector(m_HCProbeDiagSampled) + ",";
        text = text + HCProbeNum(m_HCProbeDiagHSnap) + "," + HCProbeNum(m_HCProbeDiagVSnap) + "," + HCProbeInt(m_HCProbeDiagWaypoints) + ",";
        text = text + HCProbeVector(m_HCProbeDiagFinal) + "," + HCProbeNum(m_HCProbeDiagHGap) + "," + HCProbeNum(m_HCProbeDiagVGap) + ",";
        text = text + HCProbeInt(m_HCProbeDiagRel) + "," + HCProbeStr(m_HCProbeDiagType) + "]";
        string held = m_HCProbeReachSamples.Get(slot);
        if (seen > 0)
            held = held + ",";
        m_HCProbeReachSamples.Set(slot, held + text);
    }

    int HCProbeReachResult(int variant, int reason, vector floorPos)
    {
        HCProbeDiagSample(variant, reason, floorPos);
        if (reason == 7)
            return 1;
        if (reason == 12)
            return -1;
        if (reason >= 8)
            return 3;
        if (reason <= 2)
            return 2;
        return 0;
    }

    string HCProbeReachDiagVariant(int variant)
    {
        string text = "{";
        int reason = 0;
        int slot = 0;
        int seen = 0;
        for (reason = 0; reason < 13; reason++)
        {
            slot = variant * 13 + reason;
            seen = m_HCProbeReachCounts.Get(slot);
            if (seen > 0)
            {
                if (text.Length() > 1)
                    text = text + ",";
                text = text + HCProbeKey(HCProbeReasonName(reason)) + "{" + HCProbeKey("count") + HCProbeInt(seen) + ",";
                text = text + HCProbeKey("samples") + "[" + m_HCProbeReachSamples.Get(slot) + "]}";
            }
        }
        return text + "}";
    }

    string HCProbeReachDiagText()
    {
        string text = "{" + HCProbeKey("strict") + HCProbeReachDiagVariant(0) + ",";
        text = text + HCProbeKey("player") + HCProbeReachDiagVariant(1) + ",";
        text = text + HCProbeKey("strict_open") + HCProbeReachDiagVariant(2) + ",";
        text = text + HCProbeKey("player_open") + HCProbeReachDiagVariant(3) + "}";
        return text;
    }

    void HCProbeControlDetail(int stage, vector probeWorld)
    {
        m_HCProbeDetailText = "{}";
        if (stage != 4 && stage != 10)
            return;
        int result = HCProbeRay(Vector(probeWorld[0], probeWorld[1] + 2.0, probeWorld[2]), Vector(probeWorld[0], probeWorld[1] - 2.0, probeWorld[2]));
        float groundY = -1000.0;
        if (result > 0)
        {
            vector groundLocal = m_HCProbeBuilding.CoordToLocal(m_HCProbeHitPos);
            groundY = groundLocal[1];
        }
        string text = "{" + HCProbeKey("seed") + HCProbeVector(m_HCProbeSeed) + "," + HCProbeKey("sample") + HCProbeVector(m_HCProbeDiagSampled) + ",";
        text = text + HCProbeKey("final") + HCProbeVector(m_HCProbeDiagFinal) + "," + HCProbeKey("h_gap") + HCProbeNum(m_HCProbeDiagHGap) + ",";
        text = text + HCProbeKey("v_gap") + HCProbeNum(m_HCProbeDiagVGap) + "," + HCProbeKey("waypoints") + HCProbeInt(m_HCProbeDiagWaypoints) + ",";
        text = text + HCProbeKey("ray") + HCProbeInt(result) + "," + HCProbeKey("rel") + HCProbeInt(m_HCProbeHitRel) + ",";
        text = text + HCProbeKey("type") + HCProbeStr(m_HCProbeHitType) + "," + HCProbeKey("hit_y") + HCProbeNum(groundY) + "}";
        m_HCProbeDetailText = text;
    }

    string HCProbeFlagEntry(string name, int value)
    {
        return HCProbeKey(name) + HCProbeInt(value);
    }

    string HCProbeFlagsText()
    {
        string text = HCProbeFlagEntry("NONE", PGPolyFlags.NONE) + "," + HCProbeFlagEntry("WALK", PGPolyFlags.WALK) + ",";
        text = text + HCProbeFlagEntry("DISABLED", PGPolyFlags.DISABLED) + "," + HCProbeFlagEntry("DOOR", PGPolyFlags.DOOR) + ",";
        text = text + HCProbeFlagEntry("INSIDE", PGPolyFlags.INSIDE) + "," + HCProbeFlagEntry("SWIM", PGPolyFlags.SWIM) + ",";
        text = text + HCProbeFlagEntry("SWIM_SEA", PGPolyFlags.SWIM_SEA) + "," + HCProbeFlagEntry("LADDER", PGPolyFlags.LADDER) + ",";
        text = text + HCProbeFlagEntry("JUMP_OVER", PGPolyFlags.JUMP_OVER) + "," + HCProbeFlagEntry("JUMP_DOWN", PGPolyFlags.JUMP_DOWN) + ",";
        text = text + HCProbeFlagEntry("CLIMB", PGPolyFlags.CLIMB) + "," + HCProbeFlagEntry("CRAWL", PGPolyFlags.CRAWL) + ",";
        text = text + HCProbeFlagEntry("CROUCH", PGPolyFlags.CROUCH) + "," + HCProbeFlagEntry("UNREACHABLE", PGPolyFlags.UNREACHABLE) + ",";
        text = text + HCProbeFlagEntry("ALL", PGPolyFlags.ALL) + "," + HCProbeFlagEntry("JUMP", PGPolyFlags.JUMP) + ",";
        text = text + HCProbeFlagEntry("SPECIAL", PGPolyFlags.SPECIAL);
        return text;
    }

    string HCProbeFilterText(PGFilter meshFilter)
    {
        string text = "{" + HCProbeKey("include") + HCProbeInt(meshFilter.GetIncludeFlags()) + ",";
        text = text + HCProbeKey("exclude") + HCProbeInt(meshFilter.GetExcludeFlags()) + ",";
        text = text + HCProbeKey("exclusive") + HCProbeInt(meshFilter.GetExlusiveFlags()) + "}";
        return text;
    }

    int HCProbeReachHit(int variant, vector floorPos, float freeClear, int capKind)
    {
        string state = HCProbeVariantState(variant);
        HCProbeUseFilter(variant);
        PGFilter meshFilter = m_HCProbeUsedFilter;
        HCProbeUseEntrance(variant);
        vector entrance = m_HCProbeUsedEntrance;
        if (state != "tested")
            return -1;
        HCProbeDiagReset();
        if (capKind > 0)
            return HCProbeReachResult(variant, 11, floorPos);
        if (freeClear < m_HCProbeClearRequired)
        {
            m_HCProbeDiagRel = m_HCProbeFreeRel;
            m_HCProbeDiagType = m_HCProbeFreeType;
            return HCProbeReachResult(variant, 10, floorPos);
        }
        if (!HCProbeTakePath(variant))
            return HCProbeReachResult(variant, 12, floorPos);
        if (!HCProbeSampleMesh(floorPos, 1.5, meshFilter))
            return HCProbeReachResult(variant, 0, floorPos);
        vector candidate = m_HCProbeSampled;
        m_HCProbeDiagSampled = m_HCProbeBuilding.CoordToLocal(candidate);
        float shiftX = candidate[0] - floorPos[0];
        float shiftZ = candidate[2] - floorPos[2];
        m_HCProbeDiagHSnap = Math.Sqrt(shiftX * shiftX + shiftZ * shiftZ);
        m_HCProbeDiagVSnap = Math.AbsFloat(candidate[1] - floorPos[1]);
        if (m_HCProbeDiagHSnap > m_HCProbeSnapLimit)
            return HCProbeReachResult(variant, 1, floorPos);
        if (m_HCProbeDiagVSnap > m_HCProbeVerticalAllowance)
            return HCProbeReachResult(variant, 1, floorPos);
        if (m_HCProbeDiagHSnap > m_HCProbeTrivialShift)
        {
            float waistY = floorPos[1] + m_HCProbeWaistHeight;
            int snapRay = HCProbeRay(Vector(floorPos[0], waistY, floorPos[2]), Vector(candidate[0], waistY, candidate[2]));
            m_HCProbeDiagRel = m_HCProbeHitRel;
            m_HCProbeDiagType = m_HCProbeHitType;
            if (snapRay != 0)
                return HCProbeReachResult(variant, 2, floorPos);
            return HCProbeReachResult(variant, 8, floorPos);
        }
        int stage = HCProbePath(entrance, candidate, floorPos, meshFilter);
        if (stage == 1)
            return HCProbeReachResult(variant, 3, floorPos);
        if (stage == 2)
            return HCProbeReachResult(variant, 4, floorPos);
        if (stage == 3)
            return HCProbeReachResult(variant, 5, floorPos);
        if (stage == 4)
            return HCProbeReachResult(variant, 6, floorPos);
        if (stage == 6)
            return HCProbeReachResult(variant, 9, floorPos);
        return HCProbeReachResult(variant, 7, floorPos);
    }

    void HCProbeRecordFloor(vector floorPos, float clearance, float freeClear, float dirY, int capKind)
    {
        vector modelPos = m_HCProbeBuilding.CoordToLocal(floorPos);
        int code = -1;
        int playerCode = -1;
        if (clearance >= 1.9)
        {
            code = HCProbeReachHit(0, floorPos, freeClear, capKind);
            playerCode = HCProbeReachHit(1, floorPos, freeClear, capKind);
        }
        string text = "[" + HCProbeNum(modelPos[0]) + "," + HCProbeNum(modelPos[1]) + "," + HCProbeNum(modelPos[2]) + ",";
        text = text + HCProbeNum(clearance) + "," + HCProbeNum(dirY) + "," + HCProbeInt(code) + "]";
        string codeText = HCProbeInt(playerCode);
        string strictText = HCProbeInt(code);
        if (m_HCProbeOutputChars + m_HCProbePlayerCodes.Length() + text.Length() > m_HCProbeOutputLimit)
        {
            m_HCProbeOutputCapped = true;
            return;
        }
        if (m_HCProbeHitsEmitted > 0)
        {
            text = "," + text;
            codeText = "," + codeText;
            strictText = "," + strictText;
        }
        m_HCProbeHitsEmitted = m_HCProbeHitsEmitted + 1;
        m_HCProbePlayerCodes = m_HCProbePlayerCodes + codeText;
        m_HCProbeStrictCodes = m_HCProbeStrictCodes + strictText;
        m_HCProbeOpenPos.Insert(floorPos);
        m_HCProbeOpenFree.Insert(freeClear);
        m_HCProbeOpenClear.Insert(clearance);
        m_HCProbeOpenCap.Insert(capKind);
        HCProbeEmit(text);
    }

    void HCProbeColumnFlush(int capKind)
    {
        int total = m_HCProbeColPos.Count();
        int index = 0;
        for (index = 0; index < total; index++)
        {
            m_HCProbeFreeRel = m_HCProbeColRel.Get(index);
            m_HCProbeFreeType = m_HCProbeColType.Get(index);
            HCProbeRecordFloor(m_HCProbeColPos.Get(index), m_HCProbeColClear.Get(index), m_HCProbeColFree.Get(index), m_HCProbeColDir.Get(index), capKind);
        }
        m_HCProbeColPos.Clear();
        m_HCProbeColClear.Clear();
        m_HCProbeColFree.Clear();
        m_HCProbeColDir.Clear();
        m_HCProbeColRel.Clear();
        m_HCProbeColType.Clear();
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
                action = 5;
            if (rel == 1 && drop >= 0.02)
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
                        m_HCProbeColPos.Insert(surfacePos);
                        m_HCProbeColClear.Insert(clearance);
                        m_HCProbeColFree.Insert(m_HCProbeFreeClear);
                        m_HCProbeColDir.Insert(dirY);
                        m_HCProbeColRel.Insert(m_HCProbeFreeRel);
                        m_HCProbeColType.Insert(m_HCProbeFreeType);
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
        HCProbeColumnFlush(capKind);
        if (capKind > 0 || steps >= 12)
            HCProbeDiagColumn(localX, localZ, steps, floors, capKind, trace);
    }

    void HCProbeScanRow()
    {
        if (!m_HCProbeBuilding || m_HCProbeRayCapped || m_HCProbeOutputCapped || m_HCProbeRow >= m_HCProbeRows)
        {
            m_HCProbePhase = 3;
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
            m_HCProbePhase = 3;
    }

    void HCProbeDoorsOpen()
    {
        m_HCProbePhase = 2;
        m_HCProbeOpenCodes = m_HCProbeStrictCodes;
        m_HCProbeOpenPlayerCodes = m_HCProbePlayerCodes;
        m_HCProbeOpenedDoors.Clear();
        string skip = m_HCProbeDoorState;
        if (!m_HCProbeBuilding)
            skip = "no-building";
        if (skip == "none")
        {
            if (m_HCProbeRayCapped || m_HCProbeOutputCapped)
                skip = "skipped-capped";
        }
        int door = 0;
        if (skip == "none")
        {
            for (door = 0; door < m_HCProbeDoorCount; door++)
            {
                if (!m_HCProbeBuilding.IsDoorLocked(door) && HCProbeDoorPhase(door) == 0)
                {
                    m_HCProbeBuilding.OpenDoor(door);
                    m_HCProbeOpenedDoors.Insert(door);
                }
            }
            if (m_HCProbeOpenedDoors.Count() < 1)
                skip = "no-change";
        }
        if (skip != "none")
        {
            m_HCProbeDoorState = skip;
            m_HCProbeEntered.Set(2, m_HCProbeEntered.Get(0));
            m_HCProbeEntered.Set(3, m_HCProbeEntered.Get(1));
            return;
        }
        m_HCProbeDoorState = "opened";
        m_HCProbeDoorDelay = m_HCProbeDoorDelayTicks;
        m_HCProbeSettleUsed = 0;
        m_HCProbeWaitNext = 5;
        m_HCProbePhase = 4;
    }

    void HCProbeWait()
    {
        m_HCProbeDoorDelay = m_HCProbeDoorDelay - 1;
        if (m_HCProbeDoorDelay > 0)
            return;
        if (!HCProbeDoorsSettled() && m_HCProbeSettleUsed < m_HCProbeDoorSettleTicks)
        {
            m_HCProbeSettleUsed = m_HCProbeSettleUsed + 1;
            return;
        }
        if (m_HCProbeWaitNext == 5)
            m_HCProbeOpenSettle = m_HCProbeSettleUsed;
        if (m_HCProbeWaitNext == 8)
            m_HCProbeCloseSettle = m_HCProbeSettleUsed;
        m_HCProbePhase = m_HCProbeWaitNext;
    }

    void HCProbeOpenControl()
    {
        int observed = 0;
        int index = 0;
        int total = m_HCProbeOpenedDoors.Count();
        for (index = 0; index < total; index++)
        {
            if (HCProbeDoorPhase(m_HCProbeOpenedDoors.Get(index)) == 1)
                observed = observed + 1;
        }
        m_HCProbeDoorsObserved = observed;
        if (observed < total)
        {
            m_HCProbeDoorState = "open-stalled";
            m_HCProbeEntered.Set(2, "untested");
            m_HCProbeEntered.Set(3, "untested");
            m_HCProbeOpenCodes = m_HCProbeStrictCodes;
            m_HCProbeOpenPlayerCodes = m_HCProbePlayerCodes;
            m_HCProbePhase = 7;
            return;
        }
        float centreX = (m_HCProbeBoxMin[0] + m_HCProbeBoxMax[0]) * 0.5;
        float centreZ = (m_HCProbeBoxMin[2] + m_HCProbeBoxMax[2]) * 0.5;
        int door = 0;
        for (door = 0; door < m_HCProbeDoorCount; door++)
        {
            HCProbeReachDoor(2, door, centreX, centreZ);
            HCProbeReachDoor(3, door, centreX, centreZ);
        }
        m_HCProbeOpenCodes = "";
        m_HCProbeOpenPlayerCodes = "";
        m_HCProbeOpenIndex = 0;
        m_HCProbePhase = 6;
    }

    void HCProbeOpenFloors()
    {
        int total = m_HCProbeOpenPos.Count();
        int last = m_HCProbeOpenIndex + m_HCProbeOpenFloorChunk;
        if (last > total)
            last = total;
        int index = 0;
        int code = -1;
        int playerCode = -1;
        for (index = m_HCProbeOpenIndex; index < last; index++)
        {
            code = -1;
            playerCode = -1;
            if (m_HCProbeOpenClear.Get(index) >= m_HCProbeClearRequired)
            {
                m_HCProbeFreeRel = 0;
                m_HCProbeFreeType = "";
                code = HCProbeReachHit(2, m_HCProbeOpenPos.Get(index), m_HCProbeOpenFree.Get(index), m_HCProbeOpenCap.Get(index));
                playerCode = HCProbeReachHit(3, m_HCProbeOpenPos.Get(index), m_HCProbeOpenFree.Get(index), m_HCProbeOpenCap.Get(index));
            }
            if (index > 0)
            {
                m_HCProbeOpenCodes = m_HCProbeOpenCodes + ",";
                m_HCProbeOpenPlayerCodes = m_HCProbeOpenPlayerCodes + ",";
            }
            m_HCProbeOpenCodes = m_HCProbeOpenCodes + HCProbeInt(code);
            m_HCProbeOpenPlayerCodes = m_HCProbeOpenPlayerCodes + HCProbeInt(playerCode);
        }
        m_HCProbeOpenIndex = last;
        if (last >= total)
            m_HCProbePhase = 7;
    }

    void HCProbeDoorsClose()
    {
        int index = 0;
        int total = m_HCProbeOpenedDoors.Count();
        for (index = 0; index < total; index++)
            m_HCProbeBuilding.CloseDoor(m_HCProbeOpenedDoors.Get(index));
        m_HCProbeDoorDelay = m_HCProbeDoorDelayTicks;
        m_HCProbeSettleUsed = 0;
        m_HCProbeWaitNext = 8;
        m_HCProbePhase = 4;
    }

    void HCProbeDoorsRestored()
    {
        int restored = 0;
        int index = 0;
        int total = m_HCProbeOpenedDoors.Count();
        for (index = 0; index < total; index++)
        {
            if (HCProbeDoorPhase(m_HCProbeOpenedDoors.Get(index)) == 0)
                restored = restored + 1;
        }
        m_HCProbeDoorsRestored = restored;
        if (m_HCProbeDoorState == "opened")
            m_HCProbeDoorState = "done";
        if (restored < total)
        {
            m_HCProbeDoorState = "not-restored";
            Print("[HC Interior Sampler] WARNING doors not-restored: " + HCProbeInt(total - restored) + " opened door(s) did not report closed");
        }
        m_HCProbePhase = 2;
    }

    string HCProbeDoorRunText()
    {
        string text = "{" + HCProbeKey("count") + HCProbeInt(m_HCProbeDoorCount) + "," + HCProbeKey("locked") + HCProbeInt(m_HCProbeDoorLocked) + ",";
        text = text + HCProbeKey("open_at_start") + HCProbeInt(m_HCProbeDoorOpenStart) + "," + HCProbeKey("opened") + HCProbeInt(m_HCProbeOpenedDoors.Count()) + ",";
        text = text + HCProbeKey("observed_open") + HCProbeInt(m_HCProbeDoorsObserved) + "," + HCProbeKey("restored") + HCProbeInt(m_HCProbeDoorsRestored) + ",";
        text = text + HCProbeKey("delay_ticks") + HCProbeInt(m_HCProbeDoorDelayTicks) + "," + HCProbeKey("state") + HCProbeStr(m_HCProbeDoorState) + ",";
        text = text + HCProbeKey("ajar_at_start") + HCProbeInt(m_HCProbeDoorAjarStart) + "," + HCProbeKey("moving_at_start") + HCProbeInt(m_HCProbeDoorMovingStart) + ",";
        text = text + HCProbeKey("open_settle_ticks") + HCProbeInt(m_HCProbeOpenSettle) + "," + HCProbeKey("close_settle_ticks") + HCProbeInt(m_HCProbeCloseSettle) + ",";
        text = text + HCProbeKey("settle_limit") + HCProbeInt(m_HCProbeDoorSettleTicks) + ",";
        text = text + HCProbeKey("doors") + "[" + m_HCProbeDoorText + "]," + HCProbeKey("attempts") + "[" + m_HCProbeOpenAttempts + "],";
        text = text + HCProbeKey("player_attempts") + "[" + m_HCProbePlayerOpenAttempts + "]}";
        return text;
    }

    string HCProbeEnteredText()
    {
        string text = "{" + HCProbeKey("strict") + "{" + HCProbeKey("closed") + HCProbeStr(m_HCProbeEntered.Get(0)) + ",";
        text = text + HCProbeKey("open") + HCProbeStr(m_HCProbeEntered.Get(2)) + "}," + HCProbeKey("player") + "{";
        text = text + HCProbeKey("closed") + HCProbeStr(m_HCProbeEntered.Get(1)) + "," + HCProbeKey("open") + HCProbeStr(m_HCProbeEntered.Get(3)) + "}}";
        return text;
    }

    int HCProbeFrameProbe(float frameX, float frameY, float frameZ)
    {
        vector fromWorld = m_HCProbeBuilding.CoordToParent(Vector(frameX, frameY + 0.5, frameZ));
        vector toWorld = m_HCProbeBuilding.CoordToParent(Vector(frameX, frameY - 0.5, frameZ));
        m_HCProbeFrameY = -1000.0;
        int result = HCProbeRay(fromWorld, toWorld);
        if (result != 1)
            return 0;
        vector contactLocal = m_HCProbeBuilding.CoordToLocal(m_HCProbeHitPos);
        m_HCProbeFrameY = contactLocal[1];
        return 1;
    }

    string HCProbeFrameCheck(string className)
    {
        string text = "";
        int total = m_HCProbeFrameClasses.Count();
        int index = 0;
        int written = 0;
        int plain = 0;
        int rotated = 0;
        float plainY = 0.0;
        float rotatedY = 0.0;
        vector point;
        for (index = 0; index < total; index++)
        {
            if (m_HCProbeFrameClasses.Get(index) == className)
            {
                point = m_HCProbeFramePos.Get(index);
                plain = HCProbeFrameProbe(point[0], point[1], point[2]);
                plainY = m_HCProbeFrameY;
                rotated = HCProbeFrameProbe(0.0 - point[2], point[1], point[0]);
                rotatedY = m_HCProbeFrameY;
                if (written > 0)
                    text = text + ",";
                text = text + "[" + HCProbeNum(point[0]) + "," + HCProbeNum(point[1]) + "," + HCProbeNum(point[2]) + ",";
                text = text + HCProbeInt(plain) + "," + HCProbeNum(plainY) + "," + HCProbeInt(rotated) + "," + HCProbeNum(rotatedY) + "]";
                written = written + 1;
            }
        }
        return text;
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
        m_HCProbePlayerPaths = 0;
        m_HCProbeHitsEmitted = 0;
        m_HCProbePlayerCodes = "";
        m_HCProbeStrictCodes = "";
        m_HCProbeOpenCodes = "";
        m_HCProbeOpenPlayerCodes = "";
        m_HCProbeOpenAttempts = "";
        m_HCProbePlayerOpenAttempts = "";
        m_HCProbeDoorText = "";
        m_HCProbeFrameText = "";
        m_HCProbeDoorState = "none";
        m_HCProbeOpenState = "none";
        m_HCProbePlayerOpenState = "none";
        m_HCProbeDoorCount = 0;
        m_HCProbeDoorLocked = 0;
        m_HCProbeDoorOpenStart = 0;
        m_HCProbeDoorAjarStart = 0;
        m_HCProbeDoorMovingStart = 0;
        m_HCProbeSettleUsed = 0;
        m_HCProbeOpenSettle = 0;
        m_HCProbeCloseSettle = 0;
        m_HCProbeDoorsObserved = 0;
        m_HCProbeDoorsRestored = 0;
        m_HCProbeOpenIndex = 0;
        m_HCProbeOpenPaths = 0;
        m_HCProbeOpenPlayerPaths = 0;
        m_HCProbeEnterPaths = 0;
        m_HCProbeOpenedDoors.Clear();
        m_HCProbeOpenPos.Clear();
        m_HCProbeOpenFree.Clear();
        m_HCProbeOpenClear.Clear();
        m_HCProbeOpenCap.Clear();
        m_HCProbeEntered.Clear();
        int enteredSlot = 0;
        for (enteredSlot = 0; enteredSlot < 4; enteredSlot++)
            m_HCProbeEntered.Insert("untested");
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
        m_HCProbeReachDetail = "";
        m_HCProbePlayerAttempts = "";
        m_HCProbePlayerDetail = "";
        m_HCProbePlayerEntrances = "";
        m_HCProbeReachCounts.Clear();
        m_HCProbeReachSamples.Clear();
        int slot = 0;
        for (slot = 0; slot < 52; slot++)
        {
            m_HCProbeReachCounts.Insert(0);
            m_HCProbeReachSamples.Insert("");
        }
        m_HCProbeColPos.Clear();
        m_HCProbeColClear.Clear();
        m_HCProbeColFree.Clear();
        m_HCProbeColDir.Clear();
        m_HCProbeColRel.Clear();
        m_HCProbeColType.Clear();
        m_HCProbeRayCapped = false;
        m_HCProbeOutputCapped = false;
        m_HCProbeBoxSource = "none";
        m_HCProbeBoxMin = Vector(0.0, 0.0, 0.0);
        m_HCProbeBoxMax = Vector(0.0, 0.0, 0.0);
        m_HCProbeReachState = "none";
        m_HCProbePlayerState = "none";
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
            m_HCProbeFrameText = HCProbeFrameCheck(expectedType);
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
        if (m_HCProbeFrameText.Length() > 0)
            text = text + HCProbeKey("frame") + "[" + m_HCProbeFrameText + "],";
        text = text + HCProbeKey("reach") + "{" + HCProbeKey("state") + HCProbeStr(m_HCProbeReachState) + ",";
        text = text + HCProbeKey("doors") + "[" + m_HCProbeReachDoors + "]," + HCProbeKey("entrances") + "[" + m_HCProbeReachEntrances + "],";
        text = text + HCProbeKey("attempts") + "[" + m_HCProbeReachAttempts + "],";
        text = text + HCProbeKey("detail") + "[" + m_HCProbeReachDetail + "],";
        text = text + HCProbeKey("player") + "{" + HCProbeKey("state") + HCProbeStr(m_HCProbePlayerState) + ",";
        text = text + HCProbeKey("entrances") + "[" + m_HCProbePlayerEntrances + "]," + HCProbeKey("attempts") + "[" + m_HCProbePlayerAttempts + "],";
        text = text + HCProbeKey("detail") + "[" + m_HCProbePlayerDetail + "]}},";
        text = text + HCProbeKey("hits") + "[";
        HCProbeEmit(text);
    }

    void HCProbeEndBuilding()
    {
        string text = "]," + HCProbeKey("player_codes") + "[" + m_HCProbePlayerCodes + "]," + HCProbeKey("open_codes") + "[" + m_HCProbeOpenCodes + "],";
        text = text + HCProbeKey("open_player_codes") + "[" + m_HCProbeOpenPlayerCodes + "]," + HCProbeKey("door_run") + HCProbeDoorRunText() + ",";
        text = text + HCProbeKey("entered") + HCProbeEnteredText() + "," + HCProbeKey("stats") + "{";
        text = text + HCProbeKey("columns") + HCProbeInt(m_HCProbeStatColumns) + ",";
        text = text + HCProbeKey("rays") + HCProbeInt(m_HCProbeBuildingRays) + "," + HCProbeKey("paths") + HCProbeInt(m_HCProbeBuildingPaths) + ",";
        text = text + HCProbeKey("player_paths") + HCProbeInt(m_HCProbePlayerPaths) + "," + HCProbeKey("open_paths") + HCProbeInt(m_HCProbeOpenPaths) + ",";
        text = text + HCProbeKey("open_player_paths") + HCProbeInt(m_HCProbeOpenPlayerPaths) + ",";
        text = text + HCProbeKey("ray_capped") + HCProbeBool(m_HCProbeRayCapped) + "," + HCProbeKey("output_capped") + HCProbeBool(m_HCProbeOutputCapped) + ",";
        text = text + HCProbeKey("interior_hits") + HCProbeInt(m_HCProbeStatInterior) + "," + HCProbeKey("exterior_hits") + HCProbeInt(m_HCProbeStatExterior) + ",";
        text = text + HCProbeKey("other_hits") + HCProbeInt(m_HCProbeStatOther) + "," + HCProbeKey("step_capped_columns") + HCProbeInt(m_HCProbeStatStepCapped) + ",";
        text = text + HCProbeKey("floor_capped_columns") + HCProbeInt(m_HCProbeStatFloorCapped) + "," + HCProbeKey("rehits") + HCProbeInt(m_HCProbeStatRehits) + ",";
        text = text + HCProbeKey("clearance_capped") + HCProbeInt(m_HCProbeStatClearCapped) + "," + HCProbeKey("hit_relations") + "{" + HCProbeKey("none") + HCProbeInt(m_HCProbeRelNone) + ",";
        text = text + HCProbeKey("building") + HCProbeInt(m_HCProbeRelBuilding) + "," + HCProbeKey("proxy") + HCProbeInt(m_HCProbeRelProxy) + ",";
        text = text + HCProbeKey("other") + HCProbeInt(m_HCProbeRelOther) + "}," + HCProbeKey("other_types") + "[" + HCProbeTypesText() + "]},";
        text = text + HCProbeKey("diag") + "{" + HCProbeKey("columns") + "[" + m_HCProbeDiag + "]},";
        text = text + HCProbeKey("reach_diag") + HCProbeReachDiagText() + "}";
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
        if (phase == 3)
        {
            HCProbeDoorsOpen();
            return;
        }
        if (phase == 4)
        {
            HCProbeWait();
            return;
        }
        if (phase == 5)
        {
            HCProbeOpenControl();
            return;
        }
        if (phase == 6)
        {
            HCProbeOpenFloors();
            return;
        }
        if (phase == 7)
        {
            HCProbeDoorsClose();
            return;
        }
        if (phase == 8)
        {
            HCProbeDoorsRestored();
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
        m_HCProbePlayerFilter = new PGFilter;
        m_HCProbePlayerFilter.SetFlags(PGPolyFlags.WALK | PGPolyFlags.DOOR | PGPolyFlags.INSIDE | PGPolyFlags.JUMP | PGPolyFlags.CLIMB | PGPolyFlags.CROUCH | PGPolyFlags.LADDER, PGPolyFlags.DISABLED | PGPolyFlags.UNREACHABLE | PGPolyFlags.SWIM | PGPolyFlags.SWIM_SEA, PGPolyFlags.NONE);
        m_HCProbePlayerFilter.SetCost(PGAreaType.DOOR_CLOSED, 1000);
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
