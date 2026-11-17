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
import datetime
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import re
import sys
import xml.etree.ElementTree as ET

try:
    from . import diagnostic_mission as dm
except ImportError:  # executed as a script from tools/setup
    import diagnostic_mission as dm

SERVER_EXE = r"D:\SteamLibrary\steamapps\common\DayZServer\DayZServer_x64.exe"
SERVER_INSTALL = r"D:\SteamLibrary\steamapps\common\DayZServer"
SERVER_EXE_SHA256 = "987fbc47bab1dab37f74d7f700aa2e5b6af936a7181a62f5ba9f0090aebba805"
BATTLEYE_SHA256 = "224ab091fd806245ac4f0c3ec896f45f4682ae97ebef599ea546a1bbe37531bc"
WINDOWS_PARENT = r"D:\HollowCountryLocal"
WSL_PARENT = Path("/mnt/d/HollowCountryLocal")
VERIFIED_RUNTIME_NAME = "vanilla-p0-001"
DEFAULT_SOURCE_RUNTIME = "/mnt/d/HollowCountryLocal/vanilla-p0-001"
MISSION_NAME = "dayzOffline.chernarusplus"
PORT = 2302
PLAN_NAME = "ce-probe-plan.json"
HARD_CAP = 400
DEFAULT_PER_CLASS = 24
MAX_XML_BYTES = 16 * 1024 * 1024
MAX_PLAN_BYTES = 1024 * 1024
NAME_RULE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
IDENT_RULE = re.compile(r"^[A-Za-z0-9_]{1,64}$")
ROLE_RULE = re.compile(r"^[a-z]{1,16}$")
NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")
# Stock files whose launch-plan pin is the verified runtime's scheduled-shutdown delta,
# not the stock bytes. They are recorded with their stock hash, never silently accepted.
PLAN_PIN_DELTAS = frozenset({"db/messages.xml"})

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


def sha256(data):
    return hashlib.sha256(data).hexdigest()


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
# Enforce compile-shape lint (rules observed in native compiles 066-072)
# ---------------------------------------------------------------------------

# Engine class names visible to authored mission code (same pins as test_script_identifiers).
ENGINE_TYPE_NAMES = frozenset({
    "Mission", "Game", "World", "Weather", "Object", "Man", "Camera", "Hive", "Widget", "Param", "Class",
    "Managed", "Entity", "Human", "Car", "Transport", "Building", "Effect", "Particle", "Material", "Shape",
    "Timer", "Input", "CGame", "CargoBase", "ItemBase", "EntityAI", "Math", "Print",
})
RESERVED_WORDS = frozenset({
    "local", "ref", "autoptr", "owned", "notnull", "out", "inout", "static", "const", "private", "protected",
    "override", "modded", "sealed", "proto", "native", "external", "volatile", "event", "thread", "typename",
    "class", "enum", "typedef", "new", "delete", "this", "super", "null", "NULL", "true", "false", "void",
    "int", "float", "bool", "string", "vector", "auto", "if", "else", "for", "foreach", "while", "do",
    "switch", "case", "default", "break", "continue", "return", "array", "map", "set",
})
_MODIFIERS = r"(?:(?:ref|autoptr|static|protected|private|const|owned|notnull|out|inout)\s+)*"
_DECLARATION = re.compile(
    r"(?:^[ \t]*|[({;,][ \t]*)" + _MODIFIERS + r"([A-Za-z_]\w*(?:<[^;()=]*?>)?)[ \t]+([A-Za-z_]\w*)[ \t]*(?=[;=,)\[])", re.M)
_NOT_TYPES = frozenset({"return", "new", "class", "typename", "modded", "override", "delete", "else", "case"})
_FUNCTION = re.compile(
    r"^[ \t]{4}((?:(?:override|static|protected|private)[ \t]+)*)[\w<>]+[ \t]+(\w+)[ \t]*\(([^()]*)\)[ \t]*\n[ \t]{4}\{", re.M)
_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')
_EXPONENT = re.compile(r"\b\d+(?:\.\d+)?[eE][+-]?\d+\b")
_OUT_CALLS = (("GetObjectsAtPosition3D", (2, 3)), ("ClippingInfo", (0,)), ("GetCollisionBox", (0,)))


def _clean(text):
    """Return text with comments removed and string literal contents blanked."""
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    lines = []
    for line in text.splitlines():
        stripped = _STRING.sub('""', line)
        lines.append(stripped.split("//")[0])
    return "\n".join(lines)


def _split_arguments(text):
    args, depth, current = [], 0, []
    for char in text:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        if char == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    args.append("".join(current).strip())
    return args


def _parameter_names(text):
    names = []
    for parameter in filter(None, (p.strip() for p in text.split(","))):
        parameter = parameter.split("=")[0].strip()
        match = re.search(r"([A-Za-z_]\w*)\s*(?:\[\s*\d*\s*\])?$", parameter)
        if not match or len(parameter.split()) < 2:
            return None
        names.append(match.group(1))
    return tuple(names)


def _function_bodies(clean):
    for match in _FUNCTION.finditer(clean):
        start = match.end() - 1
        depth = 0
        for position in range(start, len(clean)):
            if clean[position] == "{":
                depth += 1
            elif clean[position] == "}":
                depth -= 1
                if depth == 0:
                    yield match, clean[start:position + 1], start
                    break


def native_type_names(cache):
    """Class/enum names declared anywhere in an extracted native script cache."""
    names = set()
    for layer in ("1_Core", "2_GameLib", "3_Game", "4_World", "5_Mission"):
        for source in (Path(cache) / layer).rglob("*.c"):
            text = source.read_text(encoding="utf-8", errors="replace")
            names.update(re.findall(r"^(?:modded\s+|sealed\s+)?(?:class|enum)\s+(\w+)", text, re.M))
    return frozenset(names)


def lint_hook(text, native_types=frozenset(), prototypes=None):
    """Return a list of issues; empty means no observed-rejected shape was found."""
    issues = []
    for number, line in enumerate(text.splitlines(), 1):
        for literal in _STRING.findall(line):
            if "//" in literal or "/*" in literal:
                issues.append(f"line {number}: comment marker inside a string literal")
            if '\\"' in literal.replace('\\\\', ''):
                issues.append(f"line {number}: escaped quote inside a string literal")
    clean = _clean(text)
    for number, line in enumerate(clean.splitlines(), 1):
        if "?" in line:
            issues.append(f"line {number}: ternary operator is not accepted by the native compiler")
        if re.match(r"^\s*(\|\||&&)", line):
            issues.append(f"line {number}: condition continuation with leading operator")
        if _EXPONENT.search(line):
            issues.append(f"line {number}: exponent float literal (use FLT_MAX)")
    forbidden = set(ENGINE_TYPE_NAMES) | set(native_types)
    for match in _DECLARATION.finditer(clean):
        kind, name = match.groups()
        if kind in _NOT_TYPES:
            continue
        line = clean.count("\n", 0, match.start(2)) + 1
        if name in RESERVED_WORDS:
            issues.append(f"line {line}: reserved word '{name}' used as an identifier")
        if name in forbidden:
            issues.append(f"line {line}: identifier '{name}' equals an engine type name")
    for header, body, start in _function_bodies(clean):
        function = header.group(2)
        names = list(_parameter_names(header.group(3)) or ())
        declared = []
        for match in _DECLARATION.finditer(body):
            if match.group(1) in _NOT_TYPES:
                continue
            names.append(match.group(2))
            declared.append((match.start(2), match.group(2)))
        seen = set()
        for name in names:
            if name in seen:
                issues.append(f"{function}: duplicate local '{name}' (Enforce shares one scope per function)")
            seen.add(name)
        for callee, positions in _OUT_CALLS:
            for call in re.finditer(r"\b%s\s*\(" % callee, body):
                end, depth = call.end(), 1
                while end < len(body) and depth:
                    depth += {"(": 1, ")": -1}.get(body[end], 0)
                    end += 1
                args = _split_arguments(body[call.end():end - 1])
                for position in positions:
                    name = args[position] if position < len(args) else ""
                    if not re.match(r"^[A-Za-z_]\w*$", name) or not any(
                            n == name and offset < call.start() for offset, n in declared):
                        issues.append(f"{function}: out argument '{name}' of {callee} must be declared before the call")
    if prototypes:
        for match in re.finditer(r"\boverride\b[^(;{}]*?\b([A-Za-z_]\w*)\s*\(([^()]*)\)", clean):
            name, names = match.group(1), _parameter_names(match.group(2))
            candidates = {p for p in prototypes.get(name, ()) if names is not None and len(p) == len(names)}
            if candidates and names not in candidates:
                issues.append(f"override {name}{names} does not match engine prototype {sorted(candidates)}")
    return issues


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------


def windows_runtime_root(path, wsl_parent=None):
    """Map a direct child of the probe parent to its Windows runtime root, or raise."""
    path = Path(path)
    parent = Path(WSL_PARENT if wsl_parent is None else wsl_parent)
    if path.parent != parent or not NAME_RULE.match(path.name):
        raise ValueError(f"destination must be a new direct child of {parent} with a plain name")
    if path.name.casefold() == VERIFIED_RUNTIME_NAME.casefold():
        raise ValueError("the verified runtime must not be reused")
    root = WINDOWS_PARENT + "\\" + path.name
    parts = PureWindowsPath(root)
    if str(parts.parent) != WINDOWS_PARENT or parts.name != path.name:
        raise ValueError("Windows runtime root must be one named child of " + WINDOWS_PARENT)
    return str(parts)


def _read_bounded(path, limit):
    with open(path, "rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{path} exceeds its byte budget")
    return data


def _hash_file(path):
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _validate_treatment(data):
    _reject_xml_declarations(data)
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise ValueError(f"treatment mapgroupproto is not well-formed: {error}") from error
    if root.tag != "prototype" or next(root.iter("group"), None) is None:
        raise ValueError("treatment mapgroupproto must be a <prototype> with <group> entries")


def _safe_plan_path(value):
    if (not isinstance(value, str) or not value or value.startswith("/") or "\\" in value or ":" in value
            or ".." in value.split("/")):
        raise ValueError("unsafe mission manifest path")
    return value


# Only these stock mission shapes may be copied into the disposable runtime. Anything else,
# listed in the launch plan or not, is refused rather than silently staged.
SENSITIVE_PART = re.compile(
    r"(?i)^(?:keys?|profiles?|storage|players?|saves?|credentials?|secrets?|battleye|logs?|backups?)$"
    r"|\.(?:biprivatekey|bikey|bisign|vars|pem|key|pfx|p12|pub|crt|sqlite|db|sav|log|rpt|adm|mdmp|cfg|bin|dll|exe|ps1|bat|cmd|sh)$"
    r"|(?i:credential|password|secret|token|private)")
ALLOWED_MISSION_DIRS = frozenset({"db", "env"})
ALLOWED_MISSION_FILE = re.compile(r"^(?:(?:db|env)/)?[A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:xml|json|map|c)$")


def _check_mission_entry(relative, *, directory=False):
    """Refuse sensitive or unvalidated mission content regardless of any manifest."""
    name = relative.as_posix()
    for part in relative.parts:
        if SENSITIVE_PART.search(part):
            raise ValueError(f"sensitive or unvalidated mission path refused: {name}")
    if directory:
        if name not in ALLOWED_MISSION_DIRS:
            raise ValueError(f"unvalidated mission directory refused: {name}")
    elif not ALLOWED_MISSION_FILE.match(name):
        raise ValueError(f"unvalidated mission file refused: {name}")


def _verify_source(source_runtime, battleye_sha256):
    mission = source_runtime / "stock-backup/mpmissions" / MISSION_NAME
    if not mission.is_dir():
        raise ValueError("stock-backup mission directory required in the source runtime")
    plan_path = source_runtime / "launch-plan.json"
    plan_bytes = _read_bounded(plan_path, MAX_PLAN_BYTES)
    launch_plan = json.loads(plan_bytes)
    pinned = {}
    for entry in launch_plan.get("mission_files", []):
        path = _safe_plan_path(entry.get("path"))
        _check_mission_entry(Path(path))
        if path in pinned or not re.match(r"^[a-f0-9]{64}$", str(entry.get("sha256"))):
            raise ValueError("duplicate or malformed launch-plan mission entry")
        pinned[path] = entry["sha256"]
    files, directories, _total = dm._inventory(mission)
    for relative in directories:
        _check_mission_entry(relative, directory=True)
    for relative, _info in files:
        _check_mission_entry(relative)
    records, held = {}, {}
    for relative, _info in files:
        name = relative.as_posix()
        digest, size = _hash_file(mission / relative)
        if name not in pinned:
            status = "absent-from-launch-plan-recorded"
        elif pinned[name] == digest:
            status = "match"
        elif name in PLAN_PIN_DELTAS:
            status = "differs-from-launch-plan-recorded"
        else:
            raise ValueError(f"stock mission file differs from launch plan: {name}")
        records[name] = {"path": name, "source_sha256": digest, "bytes": size, "plan_hash_status": status}
        if name in ("mapgrouppos.xml",):
            held[name] = _read_bounded(mission / relative, MAX_XML_BYTES)
    missing = sorted(set(pinned) - set(records))
    if missing:
        raise ValueError(f"launch plan lists files absent from the stock mission: {missing[:3]}")
    config = source_runtime / "serverDZ.cfg"
    config_digest, _ = _hash_file(config)
    if config_digest != launch_plan.get("config_sha256"):
        raise ValueError("serverDZ.cfg does not match the launch plan hash")
    battleye = source_runtime / "battleye/BEServer_x64.dll"
    battleye_digest, _ = _hash_file(battleye)
    if battleye_digest != battleye_sha256:
        raise ValueError("BEServer_x64.dll does not match the pinned hash")
    if "mapgrouppos.xml" not in held:
        raise ValueError("stock mission lacks mapgrouppos.xml")
    return {"mission": mission, "records": records, "mapgrouppos": held["mapgrouppos.xml"], "config": config,
            "battleye": battleye, "launch_plan_sha256": sha256(plan_bytes)}


def _new_file(path, data):
    with open(path, "xb") as stream:
        stream.write(data)


def stage(source_runtime, destination, *, treatment_mapgroupproto=None,
          export_delay_s=30, census_delay_s=240, per_class=DEFAULT_PER_CLASS, wait_minutes=25,
          battleye_sha256=BATTLEYE_SHA256, native_scripts=None, now=None, _wsl_parent=None):
    """Stage a fresh probe runtime and write ce-probe-plan.json. Never launches anything.

    ``_wsl_parent`` is an internal test hook; the production parent is always WSL_PARENT
    and the Windows root is always derived from the destination, never supplied.
    """
    source_runtime, destination = dm._safe_path(source_runtime), dm._safe_path(destination)
    if source_runtime == destination or source_runtime in destination.parents or destination in source_runtime.parents:
        raise ValueError("source/destination overlap forbidden")
    if destination.exists() or destination.is_symlink():
        raise ValueError("destination must be fresh; no overwrite")
    parent = Path(WSL_PARENT if _wsl_parent is None else _wsl_parent)
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError(f"probe parent directory {parent} must exist and not be a symlink")
    windows_root = windows_runtime_root(destination, parent)
    if not 5 <= wait_minutes <= 120 or not 1 <= per_class <= 64:
        raise ValueError("wait minutes 5..120 and per-class 1..64 required")
    source = _verify_source(source_runtime, battleye_sha256)
    treatment = None
    if treatment_mapgroupproto is not None:
        treatment = _read_bounded(treatment_mapgroupproto, MAX_XML_BYTES)
        _validate_treatment(treatment)
    names = {name for name, _role in PROBE_CLASSES}
    placements = parse_placements(source["mapgrouppos"], wanted=names)
    targets = build_targets(placements, per_class=per_class)
    if not targets:
        raise ValueError("no probe placements found in mapgrouppos.xml")
    hook = render_hook(targets, export_delay_s, census_delay_s)
    native = native_type_names(native_scripts) if native_scripts else frozenset()
    problems = lint_hook(hook.decode("ascii"), native_types=native)
    if problems:
        raise ValueError("generated hook violates native compile rules: " + "; ".join(problems[:3]))

    mission_dest = destination / "mpmissions" / MISSION_NAME
    manifest = dm.prepare_diagnostic_mission(source["mission"], mission_dest, purpose="ce-probe", hook=hook)
    for name in ("storage", "profiles", "battleye"):
        (destination / name).mkdir(exist_ok=False)
    _new_file(destination / "serverDZ.cfg", source["config"].read_bytes())
    _new_file(destination / "battleye/BEServer_x64.dll", source["battleye"].read_bytes())
    stock_proto_hash = source["records"]["mapgroupproto.xml"]["source_sha256"] if "mapgroupproto.xml" in source["records"] else None
    if treatment is not None:
        proto = mission_dest / "mapgroupproto.xml"
        proto.unlink()
        _new_file(proto, treatment)

    staged = []
    for path in sorted(p for p in destination.rglob("*") if p.is_file()):
        digest, size = _hash_file(path)
        staged.append({"path": path.relative_to(destination).as_posix(), "sha256": digest, "bytes": size})
    staged_hash = {entry["path"]: entry["sha256"] for entry in staged}
    mission_files = []
    for name, record in sorted(source["records"].items()):
        entry = dict(record)
        entry["sha256"] = staged_hash[f"mpmissions/{MISSION_NAME}/{name}"]
        if manifest["files"][name]["source_sha256"] != record["source_sha256"]:
            raise ValueError(f"source changed while staging: {name}")
        entry["origin"] = ("instrumented" if name == "init.c" else
                           "treatment-replacement" if treatment is not None and name == "mapgroupproto.xml" else "stock-copy")
        mission_files.append(entry)

    classes = [{"class": name, "role": role, "available": len(placements.get(name, [])),
                "sampled": sum(1 for t in targets if t["class"] == name)} for name, role in PROBE_CLASSES]
    windows_mission = f"{windows_root}\\mpmissions\\{MISSION_NAME}"
    plan = {
        "schema_version": 1, "kind": "ce-probe", "status": "staged-only-not-launched",
        "staged_utc": (now or datetime.datetime.now(datetime.timezone.utc)).isoformat(),
        "variant": "treatment" if treatment is not None else "control",
        "server_exe": SERVER_EXE, "server_exe_sha256": SERVER_EXE_SHA256, "working_directory": SERVER_INSTALL,
        "port": PORT, "requested_bind": f"127.0.0.1:{PORT}",
        "runtime_root": windows_root, "mission": windows_mission,
        "storage": windows_root + "\\storage", "profiles": windows_root + "\\profiles",
        "battleye": windows_root + "\\battleye",
        "arguments": ["-ip=127.0.0.1", f"-port={PORT}", f"-config={windows_root}\\serverDZ.cfg",
                      f"-mission={windows_mission}", f"-storage={windows_root}\\storage",
                      f"-profiles={windows_root}\\profiles", f"-BEpath={windows_root}\\battleye",
                      "-doLogs", "-adminLog"],
        "source": {"runtime_wsl_path": str(source_runtime), "launch_plan_sha256": source["launch_plan_sha256"],
                   "config_sha256": staged_hash["serverDZ.cfg"], "battleye_sha256": battleye_sha256},
        "treatment": None if treatment is None else {
            "mapgroupproto_sha256": sha256(treatment), "stock_mapgroupproto_sha256": stock_proto_hash},
        "probe": {"export_delay_s": export_delay_s, "census_delay_s": census_delay_s,
                  "per_class_limit": per_class, "hard_cap": HARD_CAP, "target_count": len(targets),
                  "hook_sha256": sha256(hook), "hook_bytes": len(hook), "wait_minutes": wait_minutes,
                  "census_relative_path": "profiles/HCCEProbe/census.json",
                  "sentinel_relative_path": "profiles/HCCEProbe/complete.txt",
                  "export_location": "unobserved; native CEApi comment names storage/export/mapgroupproto.xml"},
        "target_classes": classes, "targets": targets,
        "mission_files": mission_files, "staged_files": staged,
    }
    with open(destination / PLAN_NAME, "x", encoding="utf-8") as stream:
        json.dump(plan, stream, indent=2)
        stream.write("\n")
    return plan


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
