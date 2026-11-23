// wh-sites W2: diag-only site survey probe. INERT unless the server is started with the launch parameter
// -hcSiteSurvey or the empty file $profile:HollowCountry/survey/arm.flag exists at boot. Only then is the
// module registered at all (no [HC Ready] line, no settings key, no [HC Use] counter, no default-on feature);
// Devon's server never arms it. Lead-run in DayZDiag or a test server, once per candidate set.
// Input:  $profile:HollowCountry/survey/probe_input.json  (written by tools/package/site_survey.py write-input)
// Output: $profile:HollowCountry/survey/probe_result.json (via probe_result.json.part, copied whole at the end)
// Formats are documented in the docstring of tools/package/site_survey.py; the importer reads them.
// The result is a raw diag file (never committed); site_survey.py import converts it to the committed survey contract
// of tools/validate/site_rules.py (road_samples, cells, pieces).
// Per tick: HCWorkBudget with units_per_tick units (default 64) in slice_ms (default 4): one unit is one road
// sample, one grid row, one collision-cell row, one piece or one calibration spawn. The JSON parse of the input
// and each native query cannot be preempted; the module is diag-only for that reason.
// Samples: SurfaceGetType (road centre and 2 m either side; grid), SurfaceRoadY, SurfaceY, SurfaceGetNormal,
// SurfaceIsPond/SurfaceIsSea, IsBoxCollidingGeometry (ONLYSTATIC) on 4 m cells; pass two: exact corners and an
// oriented box per piece (sides shrunk by shrink_m); calibration: each listed class spawned at yaw 0 in a row,
// reported, then deleted after hold_seconds (non-persistent: ECE_DYNAMIC_PERSISTENCY like the object spawner).
// Native scripts-1.30.164289: 3_Game/Global/Game.c:691,703 CreateObjectEx, :705 ObjectDelete, :612 ConfigIsExisting,
// :1176 SurfaceY, :1177 SurfaceRoadY, :1180 SurfaceGetType, :1188 SurfaceGetNormal, :1196/1197 SurfaceIsSea/
// SurfaceIsPond, :1366 IsBoxCollidingGeometry (orientation = yaw/pitch/roll degrees like Object.GetOrientation:
// 3_Game/Entities/Object.c:305; the example at Game.c:1357 passes GetOrientation; box edge lengths are whole
// sizes centred on the point), 3_Game/Entities/Object.c:595,601,613 IsTree/IsRock/IsBush, :311 SetOrientation;
// 3_Game/CE/CentralEconomy.c:7-33,57 ECE_* and RF_IGNORE; 3_Game/ObjectSpawner.c:48-56 spawn flags;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnSystem.c:128 GetCLIParam, :397 FileExist,
// :417 OpenFile, :443 CloseFile, :481 FPrintln, :525 MakeDirectory, :528 DeleteFile, :531 CopyFile;
// 1_Core/proto/EnMath.c Math.Sin/Cos/Sqrt/Round/Clamp, DEG2RAD. Runtime acceptance pending: the OBB orientation
// convention and the surface type names are the two unobserved facts; the lead checks them on first run.
class HCSiteSurveyInput
{
    int schema;
    string kind;
    string input_id;
    float grid_m;
    float window_m;
    float cell_m;
    float box_height_m;
    float box_lift_m;
    float shrink_m;
    float hold_seconds;
    float slice_ms;
    int units_per_tick;
    float calibrate_x;
    float calibrate_z;
    float calibrate_spacing_m;
    ref array<float> roads;
    ref array<float> centres;
    ref array<float> pieces;
    ref array<string> piece_ids;
    ref array<string> calibrate;
}

class HCSiteSurveyGate
{
    static const string ARM_FLAG = "$profile:HollowCountry/survey/arm.flag";

    // One cheap check at module registration; false on every normal server.
    static bool HCArmed()
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        string value;
        if (GetCLIParam("hcSiteSurvey", value)) { return true; }
        return FileExist(HCSiteSurveyGate.ARM_FLAG);
    }
}

class HCSiteSurveyProbeModule : HCModule
{
    static const string DIR = "$profile:HollowCountry/survey";
    static const string INPUT_PATH = "$profile:HollowCountry/survey/probe_input.json";
    static const string RESULT_PATH = "$profile:HollowCountry/survey/probe_result.json";
    static const string PART_PATH = "$profile:HollowCountry/survey/probe_result.json.part";
    static const int MAX_INPUT_BYTES = 8388608;
    static const int MAX_ROADS = 60000;
    static const int MAX_CENTRES = 4000;
    static const int MAX_PIECES = 4000;
    static const int MAX_CALIBRATE = 64;
    static const int MAX_HITS = 32;
    static const int LEGEND_MAX = 35;
    static const float START_DELAY = 30.0;
    static const float ROAD_OFFSET = 2.0;
    static const int PHASE_WAIT = 0;
    static const int PHASE_ROADS = 1;
    static const int PHASE_CENTRES = 2;
    static const int PHASE_PIECES = 3;
    static const int PHASE_CALIBRATE = 4;
    static const int PHASE_HOLD = 5;
    static const int PHASE_RELEASE = 6;
    static const int PHASE_FINISH = 7;
    static const int PHASE_DONE = 8;

    protected bool m_Running;
    protected bool m_Begun;
    protected bool m_Finished;
    protected string m_Refusal;
    protected string m_Fault;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;
    protected ref HCSiteSurveyInput m_Input;
    protected ref HCWorkBudget m_Budget = new HCWorkBudget;
    protected FileHandle m_File;
    protected int m_Phase;
    protected float m_Elapsed;
    protected float m_HoldLeft;
    protected int m_Cursor;
    protected int m_Sub;
    protected int m_RowCount;
    protected int m_RoadCount;
    protected int m_CentreCount;
    protected int m_PieceCount;
    protected int m_CalibrateCount;
    protected int m_Spawned;
    protected int m_Hits;
    protected int m_PieceHits;
    protected int m_GridN;
    protected int m_CellN;
    protected float m_GridM;
    protected float m_Window;
    protected float m_CellM;
    protected float m_BoxH;
    protected float m_Lift;
    protected float m_Shrink;
    protected float m_SliceMs;
    protected int m_Units;
    protected int m_GridCount;
    protected string m_HText;
    protected string m_SText;
    protected string m_WText;
    protected string m_TText;
    protected string m_AnyHex;
    protected string m_TreeHex;
    protected ref array<string> m_Legend = new array<string>;
    protected ref array<Object> m_Excluded = new array<Object>;
    protected ref array<Object> m_Collided = new array<Object>;
    protected ref array<Object> m_Objects = new array<Object>;

    override string GetName() { return "SiteSurveyProbe"; }

    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Running, m_Refusal, m_Fault, "site_survey_probe_armed");
        return m_Operational;
    }

    override bool IsEnabled(HCSettings settings) { return HCSiteSurveyGate.HCArmed(); }

    override void OnStart(HCSettings settings)
    {
        if (m_Running) { return; }
        if (!HCSiteSurveyGate.HCArmed()) { return; }
        m_Refusal = "";
        m_Fault = "";
        string worldName = GetGame().GetWorldName();
        worldName.ToLower();
        if (worldName != "chernarusplus") { m_Refusal = "world_not_chernarusplus"; return; }
        m_Phase = PHASE_WAIT;
        m_Elapsed = 0;
        m_Running = true;
        Print("[HC SiteSurvey] state=armed wait_s=30 input=probe_input.json runtime=PENDING");
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || !(deltaTime > 0) || m_Phase == PHASE_DONE) { return; }
        m_Elapsed = m_Elapsed + deltaTime;
        if (m_Phase == PHASE_WAIT && m_Elapsed < START_DELAY) { return; }
        if (!m_Begun)
        {
            m_Begun = true;
            if (!HCBegin()) { HCAbort(); return; }
        }
        if (m_Phase == PHASE_HOLD)
        {
            m_HoldLeft = m_HoldLeft - deltaTime;
            if (m_HoldLeft <= 0) { m_Phase = PHASE_RELEASE; }
            return;
        }
        if (m_Phase == PHASE_FINISH)
        {
            if (!m_Finished)
            {
                m_Finished = true;
                HCFinish();
            }
            return;
        }
        m_Budget.HCReset(m_Units, m_SliceMs);
        while (m_Phase != PHASE_DONE && m_Phase != PHASE_HOLD && m_Phase != PHASE_FINISH)
        {
            if (!m_Budget.HCContinue()) { break; }
            HCStep();
        }
    }

    override void OnStop()
    {
        HCDeleteObjects();
        if (m_File)
        {
            CloseFile(m_File);
            m_File = null;
        }
        m_Running = false;
    }

    protected void HCAbort()
    {
        Print("[HC SiteSurvey] state=aborted reason=" + m_Fault + " runtime=PENDING");
        m_Phase = PHASE_DONE;
        OnStop();
    }

    // Zero or missing parameters mean the documented default; out-of-range values are clamped, never skipped.
    protected bool HCBegin()
    {
        string text;
        string error;
        HCSiteSurveyInput data;
        if (!HCGroupIO.HCReadRaw(INPUT_PATH, MAX_INPUT_BYTES, text)) { m_Fault = "input_unreadable"; return false; }
        if (!JsonFileLoader<HCSiteSurveyInput>.LoadData(text, data, error) || !data) { m_Fault = "input_json"; return false; }
        if (data.schema != 1 || data.kind != "hc-site-survey-input") { m_Fault = "input_schema"; return false; }
        if (!data.roads) { data.roads = new array<float>; }
        if (!data.centres) { data.centres = new array<float>; }
        if (!data.pieces) { data.pieces = new array<float>; }
        if (!data.piece_ids) { data.piece_ids = new array<string>; }
        if (!data.calibrate) { data.calibrate = new array<string>; }
        m_RoadCount = data.roads.Count() / 3;
        m_CentreCount = data.centres.Count() / 2;
        m_PieceCount = data.pieces.Count() / 6;
        m_CalibrateCount = data.calibrate.Count();
        if (data.roads.Count() != m_RoadCount * 3 || data.centres.Count() != m_CentreCount * 2) { m_Fault = "input_shape"; return false; }
        if (data.pieces.Count() != m_PieceCount * 6 || data.piece_ids.Count() != m_PieceCount) { m_Fault = "input_shape"; return false; }
        if (m_RoadCount > MAX_ROADS || m_CentreCount > MAX_CENTRES || m_PieceCount > MAX_PIECES || m_CalibrateCount > MAX_CALIBRATE) { m_Fault = "input_too_large"; return false; }
        m_GridM = HCParam(data.grid_m, 8.0, 4.0, 16.0);
        m_Window = HCParam(data.window_m, 80.0, 16.0, 120.0);
        m_CellM = HCParam(data.cell_m, 4.0, 2.0, 8.0);
        m_BoxH = HCParam(data.box_height_m, 2.5, 0.5, 8.0);
        m_Lift = HCParam(data.box_lift_m, 0.4, 0.0, 2.0);
        m_Shrink = HCParam(data.shrink_m, 0.2, 0.0, 1.0);
        m_SliceMs = HCParam(data.slice_ms, 4.0, 1.0, 12.0);
        m_HoldLeft = HCParam(data.hold_seconds, 300.0, 10.0, 3600.0);
        m_Units = data.units_per_tick;
        if (m_Units <= 0) { m_Units = 64; }
        m_Units = Math.Clamp(m_Units, 8, 512);
        m_GridN = (int)(Math.Round(m_Window / m_GridM)) + 1;
        m_CellN = (int)(Math.Round(m_Window / m_CellM));
        m_CellN = Math.Clamp(m_CellN, 1, 60);
        m_Input = data;
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { m_Fault = "profile_dir"; return false; }
        if (!FileExist(DIR) && !MakeDirectory(DIR)) { m_Fault = "survey_dir"; return false; }
        m_File = OpenFile(PART_PATH, FileMode.WRITE);
        if (!m_File) { m_Fault = "result_open"; return false; }
        string header = "{\"schema\":1,\"kind\":\"hc-site-survey-result\",\"input_id\":\"" + data.input_id + "\",\"world\":\"chernarusplus\",";
        header = header + "\"params\":{\"grid_n\":" + m_GridN.ToString() + ",\"cell_n\":" + m_CellN.ToString() + ",\"grid_m\":" + m_GridM.ToString() + ",\"window_m\":" + m_Window.ToString() + ",\"cell_m\":" + m_CellM.ToString();
        header = header + ",\"box_height_m\":" + m_BoxH.ToString() + ",\"box_lift_m\":" + m_Lift.ToString() + ",\"shrink_m\":" + m_Shrink.ToString() + "},";
        FPrintln(m_File, header);
        HCSection("\"roads\":[");
        m_Phase = PHASE_ROADS;
        Print("[HC SiteSurvey] state=started input_id=" + data.input_id + " roads=" + m_RoadCount.ToString() + " centres=" + m_CentreCount.ToString() + " pieces=" + m_PieceCount.ToString() + " calibrate=" + m_CalibrateCount.ToString() + " units_per_tick=" + m_Units.ToString() + " runtime=PENDING");
        return true;
    }

    protected float HCParam(float value, float fallback, float low, float high)
    {
        if (!(value > 0)) { value = fallback; }
        return Math.Clamp(value, low, high);
    }

    protected void HCSection(string opener)
    {
        FPrintln(m_File, opener);
        m_RowCount = 0;
    }

    protected void HCRow(string line)
    {
        if (m_RowCount > 0) { line = "," + line; }
        FPrintln(m_File, line);
        m_RowCount++;
    }

    protected void HCStep()
    {
        if (m_Phase == PHASE_ROADS) { HCStepRoad(); return; }
        if (m_Phase == PHASE_CENTRES) { HCStepCentre(); return; }
        if (m_Phase == PHASE_PIECES) { HCStepPiece(); return; }
        if (m_Phase == PHASE_CALIBRATE) { HCStepCalibrate(); return; }
        if (m_Phase == PHASE_RELEASE) { HCReleaseOne(); return; }
    }

    protected static string HCDigit(int value)
    {
        string digits = "0123456789abcdef";
        int at = Math.Clamp(value, 0, digits.Length() - 1);
        return digits.Substring(at, 1);
    }

    protected int HCDm(float value) { return (int)(Math.Round(value * 10.0)); }

    protected int HCCm(float value) { return (int)(Math.Round(value * 100.0)); }

    // Legend code of the surface name at a point: 0-9a-y index, z when the legend is full.
    protected string HCSurfaceCode(float x, float z)
    {
        string codes = "0123456789abcdefghijklmnopqrstuvwxyz";
        string type;
        GetGame().SurfaceGetType(x, z, type);
        int index = m_Legend.Find(type);
        if (index < 0)
        {
            if (m_Legend.Count() < LEGEND_MAX)
            {
                m_Legend.Insert(type);
                index = m_Legend.Count() - 1;
            }
            else
            {
                index = LEGEND_MAX;
            }
        }
        index = Math.Clamp(index, 0, codes.Length() - 1);
        return codes.Substring(index, 1);
    }

    protected void HCStepRoad()
    {
        if (m_Cursor >= m_RoadCount)
        {
            Print("[HC SiteSurvey] state=roads_done rows=" + m_RoadCount.ToString() + " runtime=PENDING");
            m_Cursor = 0;
            m_Sub = 0;
            FPrintln(m_File, "],");
            HCSection("\"centres\":[");
            m_Phase = PHASE_CENTRES;
            return;
        }
        int at = m_Cursor * 3;
        float x = m_Input.roads[at];
        float z = m_Input.roads[at + 1];
        float rad = m_Input.roads[at + 2] * Math.DEG2RAD;
        float rx = Math.Cos(rad) * ROAD_OFFSET;
        float rz = -Math.Sin(rad) * ROAD_OFFSET;
        string codes = HCSurfaceCode(x, z) + HCSurfaceCode(x - rx, z - rz) + HCSurfaceCode(x + rx, z + rz);
        float roadY = GetGame().SurfaceRoadY(x, z);
        float groundY = GetGame().SurfaceY(x, z);
        HCRow("[" + m_Cursor.ToString() + ",\"" + codes + "\"," + HCDm(roadY).ToString() + "," + HCDm(groundY).ToString() + "]");
        m_Cursor++;
    }

    protected void HCStepCentre()
    {
        if (m_Cursor >= m_CentreCount)
        {
            Print("[HC SiteSurvey] state=centres_done rows=" + m_CentreCount.ToString() + " runtime=PENDING");
            m_Cursor = 0;
            m_Sub = 0;
            FPrintln(m_File, "],");
            HCSection("\"pieces\":[");
            m_Phase = PHASE_PIECES;
            return;
        }
        float x0 = m_Input.centres[m_Cursor * 2];
        float z0 = m_Input.centres[m_Cursor * 2 + 1];
        if (m_Sub == 0)
        {
            m_GridCount = 0;
            m_HText = "";
            m_SText = "";
            m_WText = "";
            m_TText = "";
            m_AnyHex = "";
            m_TreeHex = "";
        }
        if (m_Sub < m_GridN)
        {
            HCGridRow(x0, z0, m_Sub);
            m_Sub++;
            return;
        }
        int cellRow = m_Sub - m_GridN;
        if (cellRow < m_CellN)
        {
            HCCellRow(x0, z0, cellRow);
            m_Sub++;
            return;
        }
        HCRow("{\"i\":" + m_Cursor.ToString() + ",\"h\":\"" + m_HText + "\",\"s\":\"" + m_SText + "\",\"w\":\"" + m_WText + "\",\"t\":\"" + m_TText + "\",\"b\":\"" + m_AnyHex + "\",\"tr\":\"" + m_TreeHex + "\"}");
        m_Cursor++;
        m_Sub = 0;
        if (m_Cursor % 100 == 0) { Print("[HC SiteSurvey] state=centres progress=" + m_Cursor.ToString() + "/" + m_CentreCount.ToString() + " runtime=PENDING"); }
    }

    // One grid row (south to north): height dm, slope percent, water 0/1/2, surface code per point, west to east.
    protected void HCGridRow(float x0, float z0, int row)
    {
        float half = m_Window * 0.5;
        float z = z0 - half + row * m_GridM;
        float x;
        float y;
        float flat;
        int slope;
        string water;
        vector normal;
        for (int col = 0; col < m_GridN; col++)
        {
            x = x0 - half + col * m_GridM;
            y = GetGame().SurfaceY(x, z);
            normal = GetGame().SurfaceGetNormal(x, z);
            slope = 999;
            if (normal[1] > 0.001)
            {
                flat = Math.Sqrt(normal[0] * normal[0] + normal[2] * normal[2]);
                slope = Math.Clamp((int)(Math.Round(flat / normal[1] * 100.0)), 0, 999);
            }
            water = "0";
            if (GetGame().SurfaceIsSea(x, z)) { water = "2"; }
            else if (GetGame().SurfaceIsPond(x, z)) { water = "1"; }
            if (m_GridCount > 0)
            {
                m_HText = m_HText + ",";
                m_SText = m_SText + ",";
            }
            m_HText = m_HText + HCDm(y).ToString();
            m_SText = m_SText + slope.ToString();
            m_WText = m_WText + water;
            m_TText = m_TText + HCSurfaceCode(x, z);
            m_GridCount++;
        }
    }

    // One collision-cell row: any static geometry / trees and bushes only, 4 cells per hex digit, zero padded.
    protected void HCCellRow(float x0, float z0, int row)
    {
        float half = m_Window * 0.5;
        float z = z0 - half + (row + 0.5) * m_CellM;
        float x;
        float y;
        vector centre;
        vector edges = Vector(m_CellM, m_BoxH, m_CellM);
        int trees;
        int buildings;
        int others;
        int anyNib = 0;
        int treeNib = 0;
        int nibCount = 0;
        bool hit;
        for (int col = 0; col < m_CellN; col++)
        {
            x = x0 - half + (col + 0.5) * m_CellM;
            y = GetGame().SurfaceY(x, z);
            centre = Vector(x, y + m_Lift + m_BoxH * 0.5, z);
            hit = HCBox(centre, "0 0 0", edges, trees, buildings, others);
            anyNib = anyNib * 2;
            treeNib = treeNib * 2;
            if (hit)
            {
                anyNib = anyNib + 1;
                m_Hits++;
                if (trees > 0) { treeNib = treeNib + 1; }
            }
            nibCount++;
            if (nibCount == 4)
            {
                m_AnyHex = m_AnyHex + HCDigit(anyNib);
                m_TreeHex = m_TreeHex + HCDigit(treeNib);
                anyNib = 0;
                treeNib = 0;
                nibCount = 0;
            }
        }
        if (nibCount > 0)
        {
            while (nibCount < 4)
            {
                anyNib = anyNib * 2;
                treeNib = treeNib * 2;
                nibCount++;
            }
            m_AnyHex = m_AnyHex + HCDigit(anyNib);
            m_TreeHex = m_TreeHex + HCDigit(treeNib);
        }
    }

    // Static-geometry box test with a bounded category tally (trees/bushes, buildings, everything else).
    protected bool HCBox(vector centre, vector orientation, vector edges, out int trees, out int buildings, out int others)
    {
        trees = 0;
        buildings = 0;
        others = 0;
        m_Collided.Clear();
        bool hit = GetGame().IsBoxCollidingGeometry(centre, orientation, edges, ObjIntersectView, ObjIntersectGeom, m_Excluded, m_Collided, CollisionFlags.ONLYSTATIC);
        int count = Math.Min(m_Collided.Count(), MAX_HITS);
        Object found;
        for (int i = 0; i < count; i++)
        {
            found = m_Collided[i];
            if (!found) { others++; }
            else if (found.IsTree() || found.IsBush()) { trees++; }
            else if (found.IsBuilding()) { buildings++; }
            else { others++; }
        }
        if (hit && count == 0) { others = 1; }
        m_Collided.Clear();
        return hit;
    }

    // Pass two: exact corners (back-left, back-right, front-right, front-left, centre) and one oriented box.
    protected void HCStepPiece()
    {
        if (m_Cursor >= m_PieceCount)
        {
            Print("[HC SiteSurvey] state=pieces_done rows=" + m_PieceCount.ToString() + " hits=" + m_PieceHits.ToString() + " runtime=PENDING");
            m_Cursor = 0;
            FPrintln(m_File, "],");
            HCSection("\"calibration\":[");
            m_Phase = PHASE_CALIBRATE;
            return;
        }
        int at = m_Cursor * 6;
        float px = m_Input.pieces[at];
        float pz = m_Input.pieces[at + 1];
        float yaw = m_Input.pieces[at + 2];
        float hx = m_Input.pieces[at + 3];
        float hz = m_Input.pieces[at + 4];
        float height = m_Input.pieces[at + 5];
        float rad = yaw * Math.DEG2RAD;
        float sn = Math.Sin(rad);
        float cs = Math.Cos(rad);
        float sx;
        float sz;
        float cx;
        float cz;
        float gy;
        float topY = -10000.0;
        int lowCm = 1000000;
        int highCm = -1000000;
        int cm;
        int wet = 0;
        string heights = "";
        for (int k = 0; k < 5; k++)
        {
            sx = 0;
            sz = 0;
            if (k == 0 || k == 3) { sx = -1; }
            if (k == 1 || k == 2) { sx = 1; }
            if (k == 0 || k == 1) { sz = -1; }
            if (k == 2 || k == 3) { sz = 1; }
            cx = px + sx * hx * cs + sz * hz * sn;
            cz = pz - sx * hx * sn + sz * hz * cs;
            gy = GetGame().SurfaceY(cx, cz);
            if (GetGame().SurfaceIsSea(cx, cz) || GetGame().SurfaceIsPond(cx, cz)) { wet = 1; }
            cm = HCCm(gy);
            if (cm < lowCm) { lowCm = cm; }
            if (cm > highCm) { highCm = cm; }
            if (gy > topY) { topY = gy; }
            if (k > 0) { heights = heights + ","; }
            heights = heights + cm.ToString();
        }
        float edgeY = Math.Max(height - m_Lift, 0.2);
        vector edges = Vector(Math.Max(hx * 2.0 - m_Shrink * 2.0, 0.2), edgeY, Math.Max(hz * 2.0 - m_Shrink * 2.0, 0.2));
        vector centre = Vector(px, topY + m_Lift + edgeY * 0.5, pz);
        int trees;
        int buildings;
        int others;
        bool hit = HCBox(centre, Vector(yaw, 0, 0), edges, trees, buildings, others);
        int hitWord = 0;
        if (hit) { hitWord = 1; m_PieceHits++; }
        // Built in short steps: one long concatenation is "Formula too complex" for the 1.30 compiler.
        string pieceId = m_Input.piece_ids[m_Cursor];
        int spread = highCm - lowCm;
        string row = "{\"i\":" + m_Cursor.ToString();
        row = row + ",\"id\":\"" + pieceId + "\"";
        row = row + ",\"y\":[" + heights + "]";
        row = row + ",\"w\":" + wet.ToString();
        row = row + ",\"spread\":" + spread.ToString();
        row = row + ",\"hit\":" + hitWord.ToString();
        row = row + ",\"n\":[" + trees.ToString() + "," + buildings.ToString() + "," + others.ToString() + "]}";
        HCRow(row);
        m_Cursor++;
    }

    // Calibration: one class per unit, yaw 0, along +x from the input origin. The lead reads the front in game.
    protected void HCStepCalibrate()
    {
        if (m_Cursor >= m_CalibrateCount)
        {
            FPrintln(m_File, "],");
            m_Cursor = 0;
            if (m_Objects.Count() > 0)
            {
                Print("[HC SiteSurvey] state=calibration_hold spawned=" + m_Objects.Count().ToString() + " hold_s=" + Math.Round(m_HoldLeft).ToString() + " x=" + Math.Round(m_Input.calibrate_x).ToString() + " z=" + Math.Round(m_Input.calibrate_z).ToString() + " runtime=PENDING");
                m_Phase = PHASE_HOLD;
                return;
            }
            m_Phase = PHASE_FINISH;
            return;
        }
        float spacing = m_Input.calibrate_spacing_m;
        if (!(spacing > 0)) { spacing = 30.0; }
        float x = m_Input.calibrate_x + m_Cursor * spacing;
        float z = m_Input.calibrate_z;
        float y = GetGame().SurfaceY(x, z);
        string name = m_Input.calibrate[m_Cursor];
        int spawned = 0;
        if (GetGame().ConfigIsExisting("CfgVehicles " + name))
        {
            int flags = ECE_SETUP | ECE_CREATEPHYSICS | ECE_NOLIFETIME | ECE_DYNAMIC_PERSISTENCY;
            Object created = GetGame().CreateObjectEx(name, Vector(x, y, z), flags, RF_IGNORE);
            if (created)
            {
                created.SetOrientation("0 0 0");
                m_Objects.Insert(created);
                m_Spawned++;
                spawned = 1;
            }
        }
        HCRow("{\"i\":" + m_Cursor.ToString() + ",\"x\":" + HCDm(x).ToString() + ",\"y\":" + HCDm(y).ToString() + ",\"z\":" + HCDm(z).ToString() + ",\"spawned\":" + spawned.ToString() + "}");
        m_Cursor++;
    }

    // One object per budget unit; the module stop path deletes the rest in HCDeleteObjects.
    protected void HCReleaseOne()
    {
        int last = m_Objects.Count() - 1;
        if (last < 0)
        {
            m_Phase = PHASE_FINISH;
            return;
        }
        Object victim = m_Objects[last];
        m_Objects.Remove(last);
        if (victim) { GetGame().ObjectDelete(victim); }
    }

    protected void HCDeleteObjects()
    {
        Object victim;
        for (int i = 0; i < m_Objects.Count(); i++)
        {
            victim = m_Objects[i];
            if (victim) { GetGame().ObjectDelete(victim); }
        }
        m_Objects.Clear();
    }

    protected void HCFinish()
    {
        string legend = "";
        for (int i = 0; i < m_Legend.Count(); i++)
        {
            if (i > 0) { legend = legend + ","; }
            legend = legend + "\"" + m_Legend[i] + "\"";
        }
        FPrintln(m_File, "\"surface_legend\":[" + legend + "],");
        FPrintln(m_File, "\"stats\":{\"roads\":" + m_RoadCount.ToString() + ",\"centres\":" + m_CentreCount.ToString() + ",\"pieces\":" + m_PieceCount.ToString() + ",\"cell_hits\":" + m_Hits.ToString() + ",\"piece_hits\":" + m_PieceHits.ToString() + ",\"spawned\":" + m_Spawned.ToString() + "},\"done\":true}");
        CloseFile(m_File);
        m_File = null;
        if (!HCGroupIO.HCLooksWholeObject(PART_PATH, HCGroupIO.HC_RAW_READ_CAP) || !CopyFile(PART_PATH, RESULT_PATH))
        {
            m_Fault = "result_publish";
            Print("[HC SiteSurvey] state=failed reason=result_publish keep=probe_result.json.part runtime=PENDING");
            m_Phase = PHASE_DONE;
            return;
        }
        DeleteFile(PART_PATH);
        m_Phase = PHASE_DONE;
        Print("[HC SiteSurvey] state=done result=probe_result.json elapsed_s=" + Math.Round(m_Elapsed).ToString() + " legend=" + m_Legend.Count().ToString() + " cell_hits=" + m_Hits.ToString() + " piece_hits=" + m_PieceHits.ToString() + " spawned=" + m_Spawned.ToString() + " runtime=PENDING");
    }
}

// Registered only when armed, so an unarmed server prints no line and allocates nothing for the probe.
modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        if (HCSiteSurveyGate.HCArmed()) { Register(new HCSiteSurveyProbeModule); }
    }
}
