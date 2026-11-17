"""Stage a disposable native Central Economy probe runtime; never launch the engine.

The probe answers one question per placement: which loose items exist inside the
building's bounding box some minutes after a fresh-storage server start. It is an
observation harness. It proves nothing about DayZ behavior until its census has been
produced by a native run and inspected, and it never accepts anything itself.

Stage a fresh runtime (destination must not exist):

    python3 tools/setup/ce_probe.py --destination /mnt/d/HollowCountryLocal/ce-probe-001

The staged mission is a hash-verified copy of the stock mission whose init.c gets
the generated hook appended. Only an optional --treatment-mapgroupproto replaces
mapgroupproto.xml. Storage and profiles start empty so the census sees the initial
spawn. Launch with tools/setup/Start-CEProbeServer.ps1 on Windows.
"""
import argparse
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

try:
    from . import diagnostic_mission as dm  # noqa: F401  (kept importable from this module)
    from . import probe_runtime as rt
except ImportError:  # executed as a script from tools/setup
    import diagnostic_mission as dm  # noqa: F401
    import probe_runtime as rt

# Shared names are re-exported unchanged; the implementations live in probe_runtime.
SERVER_EXE, SERVER_INSTALL = rt.SERVER_EXE, rt.SERVER_INSTALL
SERVER_EXE_SHA256, BATTLEYE_SHA256 = rt.SERVER_EXE_SHA256, rt.BATTLEYE_SHA256
WINDOWS_PARENT, VERIFIED_RUNTIME_NAME = rt.WINDOWS_PARENT, rt.VERIFIED_RUNTIME_NAME
DEFAULT_SOURCE_RUNTIME, MISSION_NAME, PORT = rt.DEFAULT_SOURCE_RUNTIME, rt.MISSION_NAME, rt.PORT
MAX_PLAN_BYTES, NAME_RULE, IDENT_RULE, PLAN_PIN_DELTAS = rt.MAX_PLAN_BYTES, rt.NAME_RULE, rt.IDENT_RULE, rt.PLAN_PIN_DELTAS
ENGINE_TYPE_NAMES, RESERVED_WORDS = rt.ENGINE_TYPE_NAMES, rt.RESERVED_WORDS
SENSITIVE_PART, ALLOWED_MISSION_DIRS, ALLOWED_MISSION_FILE = rt.SENSITIVE_PART, rt.ALLOWED_MISSION_DIRS, rt.ALLOWED_MISSION_FILE
sha256, native_type_names, lint_hook = rt.sha256, rt.native_type_names, rt.lint_hook
_clean, _split_arguments, _parameter_names, _function_bodies = rt._clean, rt._split_arguments, rt._parameter_names, rt._function_bodies
_read_bounded, _hash_file, _safe_plan_path = rt._read_bounded, rt._hash_file, rt._safe_plan_path
_check_mission_entry, _new_file = rt._check_mission_entry, rt._new_file
_MODIFIERS, _DECLARATION, _NOT_TYPES, _FUNCTION = rt._MODIFIERS, rt._DECLARATION, rt._NOT_TYPES, rt._FUNCTION
_STRING, _EXPONENT, _OUT_CALLS = rt._STRING, rt._EXPONENT, rt._OUT_CALLS

WSL_PARENT = Path("/mnt/d/HollowCountryLocal")
PLAN_NAME = "ce-probe-plan.json"
HARD_CAP = 400
DEFAULT_PER_CLASS = 24
MAX_XML_BYTES = 16 * 1024 * 1024
ROLE_RULE = re.compile(r"^[a-z]{1,16}$")
NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")

PROBE_CLASSES = (
    ("Land_Tenement_Small", "apartment"), ("Land_Tenement_Big", "apartment"),
    ("Land_Mil_Barracks1", "barracks"), ("Land_Mil_Barracks2", "barracks"),
    ("Land_Mil_Barracks3", "barracks"), ("Land_Mil_Barracks4", "barracks"),
    ("Land_Mil_Barracks5", "barracks"), ("Land_Mil_Barracks_Round", "barracks"),
    ("Land_Mil_Barracks6", "barracks"), ("Land_Tisy_Barracks", "barracks"),
    ("Land_House_1W01", "control"), ("Land_House_2W01", "control"),
    ("Land_HouseBlock_2F1", "control"),
)

# ---------------------------------------------------------------------------
# Placement parsing and deterministic sampling
# ---------------------------------------------------------------------------


def _reject_xml_declarations(data):
    if len(data) > MAX_XML_BYTES:
        raise ValueError("XML exceeds byte budget")
    if b"<!doctype" in data.lower() or b"<!entity" in data.lower():
        raise ValueError("DOCTYPE/ENTITY declarations are refused")


def parse_placements(data, wanted=None):
    """Return {group name: [(x, y, z), ...]} from mapgrouppos-shaped XML."""
    _reject_xml_declarations(data)
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise ValueError(f"mapgrouppos XML is not well-formed: {error}") from error
    result = {}
    for group in root.iter("group"):
        name = group.get("name")
        if not name or (wanted is not None and name not in wanted):
            continue
        tokens = (group.get("pos") or "").split()
        if len(tokens) != 3 or not all(NUMBER.match(t) for t in tokens):
            raise ValueError(f"unsupported pos for group {name}")
        position = tuple(float(t) for t in tokens)
        if not all(math.isfinite(v) for v in position):
            raise ValueError(f"non-finite pos for group {name}")
        result.setdefault(name, []).append(position)
    return result


def select_placements(positions, limit=DEFAULT_PER_CLASS):
    """Sort by position, then pick evenly spaced entries (midpoints of equal slices)."""
    ordered = sorted(positions, key=lambda p: (p[0], p[2], p[1]))
    count = len(ordered)
    if limit < 1:
        raise ValueError("limit must be positive")
    if count <= limit:
        return ordered
    return [ordered[(2 * i + 1) * count // (2 * limit)] for i in range(limit)]


def build_targets(placements, classes=PROBE_CLASSES, per_class=DEFAULT_PER_CLASS, hard_cap=HARD_CAP):
    targets = []
    for name, role in classes:
        for position in select_placements(placements.get(name, []), per_class):
            targets.append({"class": name, "role": role, "index": len(targets), "pos": [float(v) for v in position]})
            if len(targets) > hard_cap:
                raise ValueError(f"target hard cap {hard_cap} exceeded")
    return targets


# ---------------------------------------------------------------------------
# Generated Enforce hook
# ---------------------------------------------------------------------------

HOOK_HEAD = r"""

// Hollow Country DISPOSABLE Central Economy probe; observation only, no gameplay acceptance.
// Target placements are inlined literal data. Server only; runs once per process.
class HCDisposableDiagnosticMission : CustomMission
{
    protected bool m_HCProbeStarted = false;
    protected int m_HCProbeCursor = 0;
    protected int m_HCProbeCensusBeginMs = 0;
    protected int m_HCProbeFoundCount = 0;
    protected string m_HCProbeQuote = "";
    protected ref array<string> m_HCProbeClasses = new array<string>;
    protected ref array<string> m_HCProbeRoles = new array<string>;
    protected ref array<vector> m_HCProbePositions = new array<vector>;
    protected ref array<string> m_HCProbeRows = new array<string>;
    protected ref array<string> m_HCProbeExportLog = new array<string>;

    override void OnInit()
    {
        super.OnInit();
        if (!GetGame() || !GetGame().IsServer() || m_HCProbeStarted)
            return;
        m_HCProbeStarted = true;
        int quoteCode = 34;
        m_HCProbeQuote = quoteCode.AsciiToString();
@@LOADER_CALLS@@
        Print("[HC CE Probe] BEGIN; observation only; targets=" + m_HCProbeClasses.Count());
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCProbeRunExports, @@EXPORT_MS@@, false);
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCProbeCensusStep, @@CENSUS_MS@@, false);
    }

    void HCProbeAdd(string className, string role, float x, float y, float z)
    {
        m_HCProbeClasses.Insert(className);
        m_HCProbeRoles.Insert(role);
        m_HCProbePositions.Insert(Vector(x, y, z));
    }

"""

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

    bool HCProbeInsideBox(vector point, vector lo, vector hi)
    {
        int axis = 0;
        for (axis = 0; axis < 3; axis++)
        {
            if (point[axis] < lo[axis] - 0.25)
                return false;
            if (point[axis] > hi[axis] + 0.25)
                return false;
        }
        return true;
    }

    void HCProbeRunExports()
    {
        int beginMs = GetGame().GetTime();
        Print("[HC CE Probe] ExportProxyProto BEGIN");
        GetCEApi().ExportProxyProto();
        Print("[HC CE Probe] ExportProxyProto END");
        int protoMs = GetGame().GetTime();
        Print("[HC CE Probe] ExportProxyData BEGIN center=7680,7680 radius=11000");
        GetCEApi().ExportProxyData(Vector(7680, 0, 7680), 11000);
        Print("[HC CE Probe] ExportProxyData END");
        int dataMs = GetGame().GetTime();
        Print("[HC CE Probe] ExportClusterData BEGIN");
        GetCEApi().ExportClusterData();
        Print("[HC CE Probe] ExportClusterData END");
        int clusterMs = GetGame().GetTime();
        m_HCProbeExportLog.Insert("{" + HCProbeKey("name") + HCProbeStr("ExportProxyProto") + "," + HCProbeKey("begin_ms") + beginMs + "," + HCProbeKey("end_ms") + protoMs + "}");
        m_HCProbeExportLog.Insert("{" + HCProbeKey("name") + HCProbeStr("ExportProxyData") + "," + HCProbeKey("begin_ms") + protoMs + "," + HCProbeKey("end_ms") + dataMs + "}");
        m_HCProbeExportLog.Insert("{" + HCProbeKey("name") + HCProbeStr("ExportClusterData") + "," + HCProbeKey("begin_ms") + dataMs + "," + HCProbeKey("end_ms") + clusterMs + "}");
    }

    void HCProbeCensusStep()
    {
        if (m_HCProbeCursor == 0)
        {
            m_HCProbeCensusBeginMs = GetGame().GetTime();
            Print("[HC CE Probe] census BEGIN");
        }
        int stop = m_HCProbeCursor + 8;
        if (stop > m_HCProbeClasses.Count())
            stop = m_HCProbeClasses.Count();
        while (m_HCProbeCursor < stop)
        {
            m_HCProbeRows.Insert(HCProbeSamplePlacement(m_HCProbeCursor));
            m_HCProbeCursor = m_HCProbeCursor + 1;
        }
        if (m_HCProbeCursor < m_HCProbeClasses.Count())
        {
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCProbeCensusStep, 250, false);
            return;
        }
        HCProbeFinish();
    }

    string HCProbeSamplePlacement(int index)
    {
        string expectedType = m_HCProbeClasses.Get(index);
        vector expectedPos = m_HCProbePositions.Get(index);
        array<Object> candidates = new array<Object>;
        array<CargoBase> candidateCargos = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(expectedPos, 4.0, candidates, candidateCargos);
        Object building = null;
        float bestDistance = FLT_MAX;
        string nearTypes = "";
        int nearCount = 0;
        int scanLimit = candidates.Count();
        if (scanLimit > 512)
            scanLimit = 512;
        int scan = 0;
        for (scan = 0; scan < scanLimit; scan++)
        {
            Object candidate = candidates.Get(scan);
            if (!candidate)
                continue;
            string candidateType = candidate.GetType();
            if (nearCount < 8 && candidateType != "")
            {
                if (nearCount > 0)
                    nearTypes = nearTypes + ",";
                nearTypes = nearTypes + HCProbeStr(candidateType);
                nearCount = nearCount + 1;
            }
            if (candidateType != expectedType)
                continue;
            float candidateDistance = vector.Distance(candidate.GetPosition(), expectedPos);
            if (candidateDistance < bestDistance)
            {
                bestDistance = candidateDistance;
                building = candidate;
            }
        }
        string row = "{" + HCProbeKey("i") + index + "," + HCProbeKey("class") + HCProbeStr(expectedType) + "," + HCProbeKey("role") + HCProbeStr(m_HCProbeRoles.Get(index)) + ",";
        row = row + HCProbeKey("expected") + HCProbeVector(expectedPos) + "," + HCProbeKey("candidates") + candidates.Count() + ",";
        if (!building)
        {
            row = row + HCProbeKey("found") + "false," + HCProbeKey("type") + HCProbeStr("") + "," + HCProbeKey("distance") + "-1,";
            row = row + HCProbeKey("near_types") + "[" + nearTypes + "],";
            row = row + HCProbeKey("box_source") + HCProbeStr("none") + "," + HCProbeKey("sphere_loose") + "0," + HCProbeKey("box_loose") + "0,";
            row = row + HCProbeKey("truncated") + "false," + HCProbeKey("types") + "[]}";
            return row;
        }
        m_HCProbeFoundCount = m_HCProbeFoundCount + 1;
        row = row + HCProbeKey("found") + "true," + HCProbeKey("type") + HCProbeStr(building.GetType()) + "," + HCProbeKey("distance") + bestDistance + ",";
        row = row + HCProbeKey("actual") + HCProbeVector(building.GetPosition()) + ",";
        row = row + HCProbeCountLoot(building) + "}";
        return row;
    }

    string HCProbeCountLoot(Object building)
    {
        vector clip[2];
        float clipRadius = building.ClippingInfo(clip);
        vector collision[2];
        bool hasCollision = building.GetCollisionBox(collision);
        vector boxMin = clip[0];
        vector boxMax = clip[1];
        string boxSource = "clipping";
        if (!HCProbeBoxUsable(boxMin, boxMax) && hasCollision)
        {
            boxMin = collision[0];
            boxMax = collision[1];
            boxSource = "collision";
        }
        if (!HCProbeBoxUsable(boxMin, boxMax))
            boxSource = "none";
        float extentX = Math.Max(Math.AbsFloat(boxMin[0]), Math.AbsFloat(boxMax[0]));
        float extentY = Math.Max(Math.AbsFloat(boxMin[1]), Math.AbsFloat(boxMax[1]));
        float extentZ = Math.Max(Math.AbsFloat(boxMin[2]), Math.AbsFloat(boxMax[2]));
        float queryRadius = Math.Sqrt(extentX * extentX + extentY * extentY + extentZ * extentZ) + 2.0;
        if (boxSource == "none")
            queryRadius = 15.0;
        bool clamped = false;
        if (queryRadius > 80.0)
        {
            queryRadius = 80.0;
            clamped = true;
        }
        array<Object> nearby = new array<Object>;
        array<CargoBase> nearbyCargos = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(building.GetPosition(), queryRadius, nearby, nearbyCargos);
        array<string> typeNames = new array<string>;
        string typeList = "";
        string sampleList = "";
        int sampleCount = 0;
        int boxLoose = 0;
        int sphereLoose = 0;
        bool truncated = false;
        int total = nearby.Count();
        if (total > 2048)
        {
            total = 2048;
            truncated = true;
        }
        int scan = 0;
        for (scan = 0; scan < total; scan++)
        {
            ItemBase item = ItemBase.Cast(nearby.Get(scan));
            if (!item)
                continue;
            if (item.GetHierarchyParent())
                continue;
            sphereLoose = sphereLoose + 1;
            vector modelPos = building.CoordToLocal(item.GetPosition());
            string itemType = item.GetType();
            if (sampleCount < 8)
            {
                if (sampleCount > 0)
                    sampleList = sampleList + ",";
                sampleList = sampleList + HCProbeStr(itemType + "@" + modelPos[0] + "," + modelPos[1] + "," + modelPos[2]);
                sampleCount = sampleCount + 1;
            }
            if (boxSource == "none")
                continue;
            if (!HCProbeInsideBox(modelPos, boxMin, boxMax))
                continue;
            boxLoose = boxLoose + 1;
            if (typeNames.Count() < 16 && typeNames.Find(itemType) == -1)
            {
                if (typeNames.Count() > 0)
                    typeList = typeList + ",";
                typeList = typeList + HCProbeStr(itemType);
                typeNames.Insert(itemType);
            }
        }
        string fragment = HCProbeKey("box_source") + HCProbeStr(boxSource) + "," + HCProbeKey("box_min") + HCProbeVector(boxMin) + "," + HCProbeKey("box_max") + HCProbeVector(boxMax) + ",";
        fragment = fragment + HCProbeKey("clip_radius") + clipRadius + "," + HCProbeKey("collision_box") + HCProbeBool(hasCollision) + ",";
        fragment = fragment + HCProbeKey("query_radius") + queryRadius + "," + HCProbeKey("radius_clamped") + HCProbeBool(clamped) + ",";
        fragment = fragment + HCProbeKey("sphere_loose") + sphereLoose + "," + HCProbeKey("box_loose") + boxLoose + "," + HCProbeKey("truncated") + HCProbeBool(truncated) + ",";
        fragment = fragment + HCProbeKey("types") + "[" + typeList + "]," + HCProbeKey("sphere_samples") + "[" + sampleList + "]";
        return fragment;
    }

    void HCProbeFinish()
    {
        string directory = "$profile:HCCEProbe";
        string censusPath = directory + "/census.json";
        string sentinelPath = directory + "/complete.txt";
        if (!FileExist(directory) && !MakeDirectory(directory))
        {
            Print("[HC CE Probe] FAILED cannot create output directory");
            return;
        }
        if (FileExist(censusPath) || FileExist(sentinelPath))
        {
            Print("[HC CE Probe] FAILED earlier probe output exists; not overwriting");
            return;
        }
        string world;
        string version;
        GetGame().GetWorldName(world);
        GetGame().GetVersion(version);
        string exportJson = "";
        int logIndex = 0;
        for (logIndex = 0; logIndex < m_HCProbeExportLog.Count(); logIndex++)
        {
            if (logIndex > 0)
                exportJson = exportJson + ",";
            exportJson = exportJson + m_HCProbeExportLog.Get(logIndex);
        }
        FileHandle handle = OpenFile(censusPath, FileMode.WRITE);
        if (!handle)
        {
            Print("[HC CE Probe] FAILED cannot open census file");
            return;
        }
        FPrintln(handle, "{");
        FPrintln(handle, HCProbeKey("schema") + "1," + HCProbeKey("kind") + HCProbeStr("ce-probe-census") + ",");
        FPrintln(handle, HCProbeKey("world") + HCProbeStr(world) + "," + HCProbeKey("version") + HCProbeStr(version) + ",");
        FPrintln(handle, HCProbeKey("census_begin_ms") + m_HCProbeCensusBeginMs + "," + HCProbeKey("census_end_ms") + GetGame().GetTime() + ",");
        FPrintln(handle, HCProbeKey("targets") + m_HCProbeClasses.Count() + "," + HCProbeKey("found") + m_HCProbeFoundCount + ",");
        FPrintln(handle, HCProbeKey("exports") + "[" + exportJson + "],");
        FPrintln(handle, HCProbeKey("placements") + "[");
        int rowIndex = 0;
        for (rowIndex = 0; rowIndex < m_HCProbeRows.Count(); rowIndex++)
        {
            if (rowIndex < m_HCProbeRows.Count() - 1)
                FPrintln(handle, m_HCProbeRows.Get(rowIndex) + ",");
            else
                FPrintln(handle, m_HCProbeRows.Get(rowIndex));
        }
        FPrintln(handle, "]");
        FPrintln(handle, "}");
        CloseFile(handle);
        if (!FileExist(censusPath))
        {
            Print("[HC CE Probe] FAILED census file missing after write");
            return;
        }
        FileHandle sentinel = OpenFile(sentinelPath, FileMode.WRITE);
        if (!sentinel)
        {
            Print("[HC CE Probe] FAILED cannot open sentinel file");
            return;
        }
        FPrintln(sentinel, "rows=" + m_HCProbeRows.Count() + " found=" + m_HCProbeFoundCount);
        CloseFile(sentinel);
        Print("[HC CE Probe] rows=" + m_HCProbeRows.Count() + " found=" + m_HCProbeFoundCount);
        Print("[HC CE Probe] COMPLETE");
    }
}
"""

LOADER_CHUNK = 40
MIN_EXPORT_DELAY_S, MAX_EXPORT_DELAY_S = 5, 600
MIN_CENSUS_DELAY_S, MAX_CENSUS_DELAY_S = 30, 3600


def render_hook(targets, export_delay_s=30, census_delay_s=240):
    """Return the generated Enforce text (bytes) with every target inlined as literal data."""
    if not targets or len(targets) > HARD_CAP:
        raise ValueError(f"1..{HARD_CAP} targets required")
    if not MIN_EXPORT_DELAY_S <= export_delay_s <= MAX_EXPORT_DELAY_S:
        raise ValueError("export delay out of range")
    if not MIN_CENSUS_DELAY_S <= census_delay_s <= MAX_CENSUS_DELAY_S:
        raise ValueError("census delay out of range")
    adds = []
    for target in targets:
        name, role, pos = target["class"], target["role"], target["pos"]
        if not IDENT_RULE.match(name) or not ROLE_RULE.match(role):
            raise ValueError("target class/role must be plain identifiers")
        if len(pos) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) and abs(v) < 1e6 for v in pos):
            raise ValueError("target position must be three bounded finite numbers")
        adds.append('        HCProbeAdd("%s", "%s", %.6f, %.6f, %.6f);' % (name, role, *pos))
    chunks = [adds[i:i + LOADER_CHUNK] for i in range(0, len(adds), LOADER_CHUNK)]
    calls = "\n".join(f"        HCProbeLoadTargets{n}();" for n in range(len(chunks)))
    loaders = "".join("    void HCProbeLoadTargets%d()\n    {\n%s\n    }\n\n" % (n, "\n".join(chunk))
                      for n, chunk in enumerate(chunks))
    head = (HOOK_HEAD.replace("@@LOADER_CALLS@@", calls)
            .replace("@@EXPORT_MS@@", str(export_delay_s * 1000))
            .replace("@@CENSUS_MS@@", str(census_delay_s * 1000)))
    text = head + loaders + HOOK_TAIL
    if not text.isascii():
        raise ValueError("hook must be ASCII")
    return text.encode("ascii")




# ---------------------------------------------------------------------------
# Staging (shared lint, name rule, verification and skeleton live in probe_runtime)
# ---------------------------------------------------------------------------


def windows_runtime_root(path, wsl_parent=None):
    """Map a direct child of the probe parent to its Windows runtime root, or raise."""
    return rt.windows_runtime_root(path, WSL_PARENT if wsl_parent is None else wsl_parent)


def _verify_source(source_runtime, battleye_sha256):
    source = rt.verify_source(source_runtime, battleye_sha256, hold=("mapgrouppos.xml",))
    source["mapgrouppos"] = source["held"]["mapgrouppos.xml"]
    return source


def _validate_treatment(data):
    _reject_xml_declarations(data)
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise ValueError(f"treatment mapgroupproto is not well-formed: {error}") from error
    if root.tag != "prototype" or next(root.iter("group"), None) is None:
        raise ValueError("treatment mapgroupproto must be a <prototype> with <group> entries")


def stage(source_runtime, destination, *, treatment_mapgroupproto=None,
          export_delay_s=30, census_delay_s=240, per_class=DEFAULT_PER_CLASS, wait_minutes=25,
          battleye_sha256=BATTLEYE_SHA256, native_scripts=None, now=None, _wsl_parent=None):
    """Stage a fresh probe runtime and write ce-probe-plan.json. Never launches anything.

    ``_wsl_parent`` is an internal test hook; the production parent is always WSL_PARENT
    and the Windows root is always derived from the destination, never supplied.
    """
    if not 5 <= wait_minutes <= 120 or not 1 <= per_class <= 64:
        raise ValueError("wait minutes 5..120 and per-class 1..64 required")
    context = rt.begin(source_runtime, destination, parent=WSL_PARENT if _wsl_parent is None else _wsl_parent,
                       battleye_sha256=battleye_sha256, hold=("mapgrouppos.xml",))
    source = context["source"]
    treatment = None
    if treatment_mapgroupproto is not None:
        treatment = _read_bounded(treatment_mapgroupproto, MAX_XML_BYTES)
        _validate_treatment(treatment)
    names = {name for name, _role in PROBE_CLASSES}
    placements = parse_placements(source["held"]["mapgrouppos.xml"], wanted=names)
    targets = build_targets(placements, per_class=per_class)
    if not targets:
        raise ValueError("no probe placements found in mapgrouppos.xml")
    hook = render_hook(targets, export_delay_s, census_delay_s)
    native = native_type_names(native_scripts) if native_scripts else frozenset()
    problems = lint_hook(hook.decode("ascii"), native_types=native)
    if problems:
        raise ValueError("generated hook violates native compile rules: " + "; ".join(problems[:3]))

    stock_proto_hash = source["records"]["mapgroupproto.xml"]["source_sha256"] if "mapgroupproto.xml" in source["records"] else None
    built = rt.build_runtime(context, hook, purpose="ce-probe",
                             replacements=None if treatment is None else {"mapgroupproto.xml": treatment})
    classes = [{"class": name, "role": role, "available": len(placements.get(name, [])),
                "sampled": sum(1 for t in targets if t["class"] == name)} for name, role in PROBE_CLASSES]
    plan = rt.plan_header("ce-probe", now, after={"variant": "treatment" if treatment is not None else "control"})
    plan.update(rt.plan_runtime_fields(context, built))
    plan.update({
        "treatment": None if treatment is None else {
            "mapgroupproto_sha256": sha256(treatment), "stock_mapgroupproto_sha256": stock_proto_hash},
        "probe": {"export_delay_s": export_delay_s, "census_delay_s": census_delay_s,
                  "per_class_limit": per_class, "hard_cap": HARD_CAP, "target_count": len(targets),
                  "hook_sha256": sha256(hook), "hook_bytes": len(hook), "wait_minutes": wait_minutes,
                  "census_relative_path": "profiles/HCCEProbe/census.json",
                  "sentinel_relative_path": "profiles/HCCEProbe/complete.txt",
                  "export_location": "unobserved; native CEApi comment names storage/export/mapgroupproto.xml"},
        "target_classes": classes, "targets": targets,
        "mission_files": built["mission_files"], "staged_files": built["staged"],
    })
    return rt.write_plan(context["destination"], PLAN_NAME, plan)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--destination", required=True, help="fresh runtime directory (must not exist)")
    parser.add_argument("--source-runtime", default=DEFAULT_SOURCE_RUNTIME)
    parser.add_argument("--treatment-mapgroupproto")
    parser.add_argument("--export-delay-s", type=int, default=30)
    parser.add_argument("--census-delay-s", type=int, default=240)
    parser.add_argument("--per-class", type=int, default=DEFAULT_PER_CLASS)
    parser.add_argument("--wait-minutes", type=int, default=25)
    parser.add_argument("--battleye-sha256", default=BATTLEYE_SHA256)
    parser.add_argument("--native-scripts", help="extracted native script cache used to lint the hook")
    args = parser.parse_args(argv)
    cache = args.native_scripts
    if cache is None:
        default = Path.home() / ".cache/hollow-country/native-scripts/scripts-1.30.164289"
        cache = default if (default / "3_Game").is_dir() else None
    try:
        plan = stage(args.source_runtime, args.destination, treatment_mapgroupproto=args.treatment_mapgroupproto,
                     export_delay_s=args.export_delay_s,
                     census_delay_s=args.census_delay_s, per_class=args.per_class,
                     wait_minutes=args.wait_minutes, battleye_sha256=args.battleye_sha256,
                     native_scripts=cache)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ce_probe: {error}", file=sys.stderr)
        return 1
    print(f"staged {plan['variant']} runtime: {Path(args.destination) / PLAN_NAME}")
    print(f"targets={plan['probe']['target_count']} hook_bytes={plan['probe']['hook_bytes']} "
          f"hook_sha256={plan['probe']['hook_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
