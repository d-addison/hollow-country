"""Stage a disposable native taped-light geometry probe runtime; never launch the engine.

The probe answers, per candidate host class, what the installed server engine reports about
a flashlight mount: whether the host's own config declares the native light slots, whether the
slot's selection exists on the host model as a selection, memory point or proxy bone, and
whether the native attach calls accept a representative light. It is an observation harness.
It proves nothing about DayZ behavior until a native run has produced observations that
tools/audit/taped_light_report.py can join, and it never accepts anything itself. Beam,
switch, two-client presentation and persistence are not observable here (see the report).

Stage a fresh runtime (destination must not exist; classification is the output of
`python3 -m tools.audit.flashlight_matrix classify`):

    python3 tools/setup/taped_light_probe.py --classification FILE \
        --destination /mnt/d/HollowCountryLocal/taped-light-probe-001

The staged mission is a hash-verified copy of the stock mission whose init.c gets the generated
hook appended. Storage and profiles start empty. There are no clients, no players and no
persistence writes outside the probe's own profile directory.

Limits of the in-script guards: the per-class timeout is checked after every observation (the last
one included) and the watchdog is a queued call, so the watchdog cannot interrupt a synchronous call
that never returns. A hung engine call hangs the probe; the launcher's wait limit is the only outer
bound, and nothing is read from a run that did not write its sentinel.
"""
import argparse
import json
import math
from pathlib import Path
import sys

try:
    from . import diagnostic_mission as dm  # noqa: F401  (kept importable from this module)
    from . import probe_runtime as rt
except ImportError:  # executed as a script from tools/setup
    import diagnostic_mission as dm  # noqa: F401
    import probe_runtime as rt

# Shared names are the one implementation in probe_runtime (same objects, not copies).
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
PLAN_NAME = "taped-light-probe-plan.json"
PLAN_KIND = "taped-light-probe"
OBSERVATIONS_KIND = "taped-light-probe-observations"
PROBE_DIRECTORY = "HCTapedLightProbe"
OUTPUT_RELATIVE = "profiles/" + PROBE_DIRECTORY + "/observations.json"
SENTINEL_RELATIVE = "profiles/" + PROBE_DIRECTORY + "/complete.txt"
CLASSIFICATION_KIND = "flashlight_host_light_classification"
HARD_CAP = 600
MAX_LIGHTS = 8
MAX_SLOTS = 8
STEP_MS = 50
MIN_START_DELAY_S, MAX_START_DELAY_S = 5, 600
MIN_PER_CLASS_MS, MAX_PER_CLASS_MS = 100, 30000
# Start-CEProbeServer.ps1 refuses a plan whose wait is outside 5..120 minutes.
MAX_WORST_CASE_MINUTES = 120
DEFAULT_START_DELAY_S = 25
DEFAULT_PER_CLASS_MS = 2000
DEFAULT_POSITION = (7680.0, 7680.0)
WORLD_EXTENT = 15360.0
MAX_CLASSIFICATION_BYTES = 8 * 1024 * 1024
LOADER_CHUNK = 40
PROBED_GROUPS = ("slot_host", "no_slot_host")
GROUP_CODES = {"no_slot_host": 0, "slot_host": 1}
PROBE_ROLES = ("representative", "control")
# Residual census: objects within 8 m are scanned up to this many; more than this is reported as truncated.
CENSUS_SCAN_LIMIT = 2048
# Native prerequisite (UniversalLight.CanPutAsAttachment, 4_World/Entities/ItemBase/Switchable_Base/
# UniversalLight.c:25-45; slot list :123-132): a parent that owns a handguard slot must hold an attachment
# with hasRailFunctionality. The probe re-observes such a host with the matching rail handguard created
# natively in the slot. Handguard classes are the ones the native weapon scripts create for debug spawns
# (AKM.c:48 and AK101.c:15 AK_RailHndgrd, M4A1.c:16 M4_RISHndgrd, MP5.c:48 MP5_RailHndgrd).
PREREQUISITE_HANDGUARDS = (("weaponHandguardAK", "AK_RailHndgrd"), ("weaponHandguardM4", "M4_RISHndgrd"),
                           ("weaponHandguardMP5", "MP5_RailHndgrd"))
PREREQUISITE_LIGHTS = ("UniversalLight",)

# ---------------------------------------------------------------------------
# Classification input and target selection
# ---------------------------------------------------------------------------


def _ident(value, what):
    if not isinstance(value, str) or not IDENT_RULE.match(value):
        raise ValueError(f"{what} must be a plain identifier of at most 64 characters")
    return value


def select_targets(document):
    """Return the deterministic probe targets from a flashlight_matrix classification."""
    if not isinstance(document, dict) or document.get("kind") != CLASSIFICATION_KIND:
        raise ValueError("a flashlight host/light classification document is required")
    hosts, lights = document.get("hosts"), document.get("lights")
    slots = document.get("native_light_slots")
    if not isinstance(hosts, list) or not isinstance(lights, list) or not isinstance(slots, list):
        raise ValueError("classification needs hosts, lights and native_light_slots lists")
    if not 1 <= len(slots) <= MAX_SLOTS:
        raise ValueError(f"1..{MAX_SLOTS} native light slot names required")
    slot_names = sorted({_ident(name, "slot name") for name in slots})
    chosen, excluded, seen = [], 0, set()
    for entry in hosts:
        if not isinstance(entry, dict):
            raise ValueError("host entries must be objects")
        group = entry.get("group")
        if group == "excluded":
            excluded += 1
            continue
        if group not in PROBED_GROUPS:
            raise ValueError(f"unsupported host group {group!r}")
        name = _ident(entry.get("name"), "host class")
        root = _ident(entry.get("root"), "host root")
        if name.casefold() in seen:
            raise ValueError(f"duplicate host class {name}")
        seen.add(name.casefold())
        chosen.append((0 if group == "slot_host" else 1, name.casefold(), name, root, group))
        if len(chosen) > HARD_CAP:
            raise ValueError(f"host hard cap {HARD_CAP} exceeded")
    if not chosen:
        raise ValueError("no probe-eligible hosts in the classification")
    probe_lights = set()
    for entry in lights:
        if not isinstance(entry, dict):
            raise ValueError("light entries must be objects")
        if entry.get("probe_role") in PROBE_ROLES and entry.get("group") != "excluded":
            probe_lights.add(_ident(entry.get("name"), "light class"))
    if not probe_lights:
        raise ValueError("no probe lights (representative or control) in the classification")
    if len(probe_lights) > MAX_LIGHTS:
        raise ValueError(f"at most {MAX_LIGHTS} probe lights")
    declared = document.get("probe_lights")
    if declared is not None and sorted(declared) != sorted(probe_lights):
        raise ValueError("probe_lights does not match the light entries")
    hosts_out = [{"class": name, "root": root, "group": group, "index": index}
                 for index, (_order, _fold, name, root, group) in enumerate(sorted(chosen))]
    return {"hosts": hosts_out, "lights": sorted(probe_lights), "slots": slot_names, "excluded_not_probed": excluded}


# ---------------------------------------------------------------------------
# Generated Enforce hook
# ---------------------------------------------------------------------------

HOOK_TEMPLATE = r"""

// Hollow Country DISPOSABLE taped-light geometry probe; observation only, no gameplay acceptance.
// Host, light and slot data are inlined literals. Server only; runs once per process.
// Every spawned object is tracked and deleted; output is one bounded JSON plus a sentinel.
// Limits: the per-class timeout is checked after every observation (including the last) and the
// watchdog fires between steps. The watchdog cannot interrupt a synchronous call that never returns;
// a hung engine call hangs the probe and the launcher's wait limit is the only outer bound.
class HCDisposableDiagnosticMission : CustomMission
{
    protected bool m_HCTLStarted = false;
    protected bool m_HCTLDone = false;
    protected bool m_HCTLClassTimedOut = false;
    protected int m_HCTLCursor = 0;
    protected int m_HCTLHardCap = 0;
    protected int m_HCTLPerClassMs = 0;
    protected int m_HCTLBeginMs = 0;
    protected int m_HCTLEndMs = 0;
    protected int m_HCTLSpawned = 0;
    protected int m_HCTLDeleted = 0;
    protected int m_HCTLTimeouts = 0;
    protected int m_HCTLAttachOk = 0;
    protected int m_HCTLResidualProbe = 0;
    protected int m_HCTLResidualOther = 0;
    protected int m_HCTLCensusTotal = 0;
    protected int m_HCTLCensusScanned = 0;
    protected bool m_HCTLCensusTruncated = false;
    protected int m_HCTLLiveAfterRelease = 0;
    protected string m_HCTLQuote = "";
    protected string m_HCTLSlash = "";
    protected string m_HCTLStatus = "running";
    protected vector m_HCTLPos;
    protected ref array<string> m_HCTLClasses = new array<string>;
    protected ref array<string> m_HCTLRoots = new array<string>;
    protected ref array<int> m_HCTLGroups = new array<int>;
    protected ref array<string> m_HCTLLights = new array<string>;
    protected ref array<string> m_HCTLSlots = new array<string>;
    protected ref array<string> m_HCTLPrereqSlots = new array<string>;
    protected ref array<string> m_HCTLPrereqTypes = new array<string>;
    protected ref array<string> m_HCTLPrereqLights = new array<string>;
    protected ref array<Object> m_HCTLLive = new array<Object>;
    protected ref array<Object> m_HCTLReleased = new array<Object>;
    protected ref array<string> m_HCTLRows = new array<string>;
    protected ref array<string> m_HCTLLightRows = new array<string>;
    protected ref array<string> m_HCTLSlotRows = new array<string>;

    override void OnInit()
    {
        super.OnInit();
        if (!GetGame() || !GetGame().IsServer() || m_HCTLStarted)
            return;
        m_HCTLStarted = true;
        m_HCTLHardCap = @@HARD_CAP@@;
        m_HCTLPerClassMs = @@PER_CLASS_MS@@;
        int quoteCode = 34;
        m_HCTLQuote = quoteCode.AsciiToString();
        int slashCode = 92;
        m_HCTLSlash = slashCode.AsciiToString();
@@LOADER_CALLS@@
        if (m_HCTLClasses.Count() > m_HCTLHardCap)
        {
            Print("[HC Taped Light Probe] FAILED class count exceeds the hard cap");
            return;
        }
        float surfaceY = GetGame().SurfaceY(@@POS_X@@, @@POS_Z@@);
        m_HCTLPos = Vector(@@POS_X@@, surfaceY + 1.0, @@POS_Z@@);
        Print("[HC Taped Light Probe] ARMED; observation only; classes=" + m_HCTLClasses.Count().ToString());
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCTLStep, @@START_MS@@, false);
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCTLWatchdog, @@WATCHDOG_MS@@, false);
    }

    void HCTLAddHost(string className, string rootName, int group)
    {
        m_HCTLClasses.Insert(className);
        m_HCTLRoots.Insert(rootName);
        m_HCTLGroups.Insert(group);
    }

    void HCTLAddLight(string lightName)
    {
        m_HCTLLights.Insert(lightName);
    }

    void HCTLAddSlot(string slotName)
    {
        m_HCTLSlots.Insert(slotName);
    }

    void HCTLAddPrereq(string slotName, string handguardType)
    {
        m_HCTLPrereqSlots.Insert(slotName);
        m_HCTLPrereqTypes.Insert(handguardType);
    }

    void HCTLAddPrereqLight(string lightName)
    {
        m_HCTLPrereqLights.Insert(lightName);
    }

    void HCTLLoadMeta()
    {
@@META_ADDS@@
    }

@@HOST_LOADERS@@
    string HCTLKey(string name)
    {
        return m_HCTLQuote + name + m_HCTLQuote + ":";
    }

    string HCTLStr(string value)
    {
        string text = value;
        if (text.Length() > 96)
            text = text.Substring(0, 96);
        text.Replace(m_HCTLQuote, "'");
        text.Replace(m_HCTLSlash, "/");
        return m_HCTLQuote + text + m_HCTLQuote;
    }

    string HCTLBool(bool value)
    {
        if (value)
            return "true";
        return "false";
    }

    string HCTLVector(vector value)
    {
        return "[" + value[0].ToString() + "," + value[1].ToString() + "," + value[2].ToString() + "]";
    }

    Object HCTLSpawn(string typeName)
    {
        int spawnFlags = ECE_IN_INVENTORY | ECE_NOPERSISTENCY_WORLD | ECE_NOLIFETIME;
        Object created = GetGame().CreateObjectEx(typeName, m_HCTLPos, spawnFlags);
        if (created)
        {
            m_HCTLLive.Insert(created);
            m_HCTLSpawned = m_HCTLSpawned + 1;
        }
        return created;
    }

    void HCTLReleaseAll()
    {
        int releaseIndex = m_HCTLLive.Count() - 1;
        Object releaseItem = null;
        while (releaseIndex >= 0)
        {
            releaseItem = m_HCTLLive.Get(releaseIndex);
            if (releaseItem)
            {
                GetGame().ObjectDelete(releaseItem);
                m_HCTLDeleted = m_HCTLDeleted + 1;
                m_HCTLReleased.Insert(releaseItem);
            }
            releaseIndex = releaseIndex - 1;
        }
        m_HCTLLive.Clear();
    }

    void HCTLMeasureLive()
    {
        int liveIndex = 0;
        Object liveItem = null;
        m_HCTLLiveAfterRelease = m_HCTLLive.Count();
        while (liveIndex < m_HCTLReleased.Count())
        {
            liveItem = m_HCTLReleased.Get(liveIndex);
            if (liveItem)
                m_HCTLLiveAfterRelease = m_HCTLLiveAfterRelease + 1;
            liveIndex = liveIndex + 1;
        }
    }

    void HCTLStep()
    {
        if (m_HCTLDone)
            return;
        if (m_HCTLCursor == 0)
        {
            m_HCTLBeginMs = GetGame().GetTime();
            Print("[HC Taped Light Probe] BEGIN; observation only; classes=" + m_HCTLClasses.Count().ToString());
            HCTLObserveSlots();
            HCTLObserveLights();
        }
        if (m_HCTLCursor < m_HCTLClasses.Count())
        {
            m_HCTLRows.Insert(HCTLObserveHost(m_HCTLCursor));
            m_HCTLCursor = m_HCTLCursor + 1;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCTLStep, @@STEP_MS@@, false);
            return;
        }
        HCTLFinish("complete");
    }

    void HCTLWatchdog()
    {
        if (m_HCTLDone)
            return;
        HCTLFinish("partial");
    }

    void HCTLFinish(string status)
    {
        if (m_HCTLDone)
            return;
        m_HCTLDone = true;
        m_HCTLStatus = status;
        m_HCTLEndMs = GetGame().GetTime();
        HCTLReleaseAll();
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCTLWriteResult, 3000, false);
    }

    void HCTLObserveSlots()
    {
        int slotIndex = 0;
        string slotName = "";
        int slotId = 0;
        bool slotValid = false;
        string selection = "";
        string bone = "";
        bool selectionKnown = false;
        bool boneKnown = false;
        while (slotIndex < m_HCTLSlots.Count())
        {
            slotName = m_HCTLSlots.Get(slotIndex);
            slotIndex = slotIndex + 1;
            slotId = InventorySlots.GetSlotIdFromString(slotName);
            slotValid = InventorySlots.IsSlotIdValid(slotId);
            selection = "";
            bone = "";
            selectionKnown = false;
            boneKnown = false;
            if (slotValid)
            {
                selectionKnown = InventorySlots.GetSelectionForSlotId(slotId, selection);
                boneKnown = InventorySlots.GetBoneNameForSlotId(slotId, bone);
            }
            string slotRowText = "{" + HCTLKey("slot") + HCTLStr(slotName) + "," + HCTLKey("id") + slotId.ToString() + ",";
            slotRowText = slotRowText + HCTLKey("valid") + HCTLBool(slotValid) + "," + HCTLKey("selection") + HCTLStr(selection) + ",";
            slotRowText = slotRowText + HCTLKey("selection_known") + HCTLBool(selectionKnown) + "," + HCTLKey("bone") + HCTLStr(bone) + ",";
            slotRowText = slotRowText + HCTLKey("bone_known") + HCTLBool(boneKnown) + "}";
            m_HCTLSlotRows.Insert(slotRowText);
        }
    }

    bool HCTLRelevantName(string lowered)
    {
        if (lowered.IndexOf("flash") != -1)
            return true;
        if (lowered.IndexOf("light") != -1)
            return true;
        if (lowered.IndexOf("rail") != -1)
            return true;
        if (lowered.IndexOf("beam") != -1)
            return true;
        if (lowered.IndexOf("tape") != -1)
            return true;
        return false;
    }

    string HCTLSelectionFacts(Object subject)
    {
        TStringArray selectionNames = new TStringArray;
        subject.GetSelectionList(selectionNames);
        int total = selectionNames.Count();
        int scanLimit = total;
        if (scanLimit > 512)
            scanLimit = 512;
        int scan = 0;
        string selectionName = "";
        string lowered = "";
        string matches = "";
        int matchCount = 0;
        while (scan < scanLimit)
        {
            selectionName = selectionNames.Get(scan);
            scan = scan + 1;
            lowered = selectionName;
            lowered.ToLower();
            if (matchCount < 16 && HCTLRelevantName(lowered))
            {
                if (matchCount > 0)
                    matches = matches + ",";
                matches = matches + HCTLStr(selectionName);
                matchCount = matchCount + 1;
            }
        }
        return HCTLKey("selection_count") + total.ToString() + "," + HCTLKey("selection_matches") + "[" + matches + "]";
    }

    // Proxy join (probe-003: InventorySlots.GetSelectionForSlotId returned nothing natively, so the model evidence is a
    // proxy selection joined to its CfgNonAIVehicles entry, the pattern 4_World/Systems/Inventory/AttachmentsOutOfReach.c
    // :97-135 reads: inventorySlot at :105, model at :110). Native cache 1.30.164289:
    //   3_Game/Global/Game.c:449 ConfigGetText(path, out value); 3_Game/Global/Game.c:558 ConfigGetTextArray(path,
    //   out values); 3_Game/Global/Game.c:612 ConfigIsExisting(path); 3_Game/constants.c:237 CFG_NONAI_VEHICLES is
    //   "CfgNonAIVehicles"; 5_Mission/GUI/SceneEditorMenu.c:1362 reads inventorySlot as an array and
    //   5_Mission/GUI/SceneEditorMenu.c:1385 falls back to the text form, as does 3_Game/Entities/EntityAI.c:3996;
    //   1_Core/proto/EnString.c:113 Substring, EnString.c:171 ToLower, EnString.c:240 IndexOf and EnString.c:253 LastIndexOf.
    string HCTLProxyBase(string selectionName)
    {
        string text = selectionName.Substring(6, selectionName.Length() - 6);
        int lastSlash = text.LastIndexOf("/");
        if (lastSlash != -1)
            text = text.Substring(lastSlash + 1, text.Length() - lastSlash - 1);
        int lastDot = text.LastIndexOf(".");
        if (lastDot != -1)
            text = text.Substring(0, lastDot);
        return text;
    }

    // View LOD join (fix round 4). GetSelectionList does not establish view-LOD membership, so each proxy model is also
    // looked up in the host's view LOD the way 4_World/Systems/Inventory/AttachmentsOutOfReach.c:112-131 does it:
    // Object.GetLODByName(LOD.NAME_VIEW), LOD.GetSelections, Selection.GetName lower-cased, a substring match on the
    // lower-cased model path without .p3d, then Selection.GetVertexPosition(lod, 0). Native cache 1.30.164289:
    //   3_Game/Entities/Object.c:98 GetLODS(notnull out array<LOD> lods) and 3_Game/Entities/Object.c:106
    //   LOD GetLODByName(string name) (script; null when the model has no such LOD);
    //   3_Game/gameplay.c:179 class Selection with gameplay.c:184 GetName(), gameplay.c:185 GetVertexCount(),
    //   gameplay.c:186 GetLODVertexIndex(int) and gameplay.c:188 GetVertexPosition(LOD lod, int index) (script; it calls
    //   Error() when the LOD vertex index is -1, so a vertex is read only after GetVertexCount() > 0 and
    //   GetLODVertexIndex(0) != -1); gameplay.c:203 class LOD with gameplay.c:207 NAME_VIEW "view", gameplay.c:216
    //   GetSelections(notnull out array<Selection> selections) returning bool and gameplay.c:218 GetVertexPosition(int).
    // The scan reads at most 256 view selections and says so (view_scan_complete); a vertex is emitted as number text.
    // This is source-level evidence only: it does not show that a client renders the attachment.
    string HCTLViewKey(string value)
    {
        string text = value;
        text.Replace(m_HCTLSlash, "/");
        text.ToLower();
        return text;
    }

    string HCTLViewNeedle(string modelPath)
    {
        string needle = HCTLViewKey(modelPath);
        int needleLength = needle.Length();
        if (needleLength > 4 && needle.Substring(needleLength - 4, 4) == ".p3d")
            needle = needle.Substring(0, needleLength - 4);
        return needle;
    }

    string HCTLViewRow(string modelPath, LOD viewLod, array<Selection> viewSelections, array<string> viewNames)
    {
        string needle = "";
        if (modelPath.Length() > 5)
            needle = HCTLViewNeedle(modelPath);
        string matchName = "";
        int matchIndex = 0;
        while (needle != "" && matchIndex < viewNames.Count())
        {
            if (viewNames.Get(matchIndex).IndexOf(needle) != -1)
            {
                matchName = viewNames.Get(matchIndex);
                break;
            }
            matchIndex = matchIndex + 1;
        }
        bool vertexOk = false;
        string vertexText = "";
        if (matchName != "")
        {
            Selection matchSelection = viewSelections.Get(matchIndex);
            if (matchSelection.GetVertexCount() > 0 && matchSelection.GetLODVertexIndex(0) != -1)
            {
                vector vertexPos = matchSelection.GetVertexPosition(viewLod, 0);
                vertexText = HCTLStr(vertexPos[0].ToString()) + "," + HCTLStr(vertexPos[1].ToString()) + "," + HCTLStr(vertexPos[2].ToString());
                vertexOk = true;
            }
        }
        string viewText = HCTLKey("view_selection") + HCTLStr(matchName) + "," + HCTLKey("view_vertex_ok") + HCTLBool(vertexOk) + ",";
        return viewText + HCTLKey("view_vertex") + "[" + vertexText + "]";
    }

    string HCTLProxyRow(string selectionName, LOD viewLod, array<Selection> viewSelections, array<string> viewNames)
    {
        string cfgClass = "Proxy" + HCTLProxyBase(selectionName);
        string cfgPath = "CfgNonAIVehicles " + cfgClass;
        bool cfgExists = GetGame().ConfigIsExisting(cfgPath);
        string modelPath = "";
        string slotText = "";
        TStringArray slotNames = new TStringArray;
        if (cfgExists)
        {
            GetGame().ConfigGetText(cfgPath + " model", modelPath);
            GetGame().ConfigGetTextArray(cfgPath + " inventorySlot", slotNames);
            if (slotNames.Count() == 0)
            {
                GetGame().ConfigGetText(cfgPath + " inventorySlot", slotText);
                if (slotText != "")
                    slotNames.Insert(slotText);
            }
        }
        int slotTotal = slotNames.Count();
        bool slotComplete = true;
        if (slotTotal > 8)
            slotComplete = false;
        string slotList = "";
        int slotIndex = 0;
        while (slotIndex < slotTotal && slotIndex < 8)
        {
            if (slotIndex > 0)
                slotList = slotList + ",";
            slotList = slotList + HCTLStr(slotNames.Get(slotIndex));
            slotIndex = slotIndex + 1;
        }
        string rowText = "{" + HCTLKey("selection") + HCTLStr(selectionName) + "," + HCTLKey("cfg_class") + HCTLStr(cfgClass) + ",";
        rowText = rowText + HCTLKey("cfg_exists") + HCTLBool(cfgExists) + "," + HCTLKey("model") + HCTLStr(modelPath) + ",";
        rowText = rowText + HCTLKey("inventory_slots") + "[" + slotList + "]," + HCTLKey("slot_count") + slotTotal.ToString() + ",";
        rowText = rowText + HCTLKey("slot_scan_complete") + HCTLBool(slotComplete) + ",";
        return rowText + HCTLViewRow(modelPath, viewLod, viewSelections, viewNames) + "}";
    }

    string HCTLProxyFacts(Object subject)
    {
        TStringArray selectionNames = new TStringArray;
        subject.GetSelectionList(selectionNames);
        int total = selectionNames.Count();
        int scanLimit = total;
        if (scanLimit > 512)
            scanLimit = 512;
        bool scanComplete = true;
        if (scanLimit < total)
            scanComplete = false;
        LOD viewLod = subject.GetLODByName(LOD.NAME_VIEW);
        array<Selection> viewSelections = new array<Selection>;
        array<string> viewNames = new array<string>;
        bool viewPresent = false;
        bool viewListed = false;
        if (viewLod)
        {
            viewPresent = true;
            viewListed = viewLod.GetSelections(viewSelections);
        }
        int viewTotal = viewSelections.Count();
        int viewLimit = viewTotal;
        if (viewLimit > 256)
            viewLimit = 256;
        bool viewComplete = false;
        if (viewListed && viewTotal == viewLimit)
            viewComplete = true;
        int viewIndex = 0;
        while (viewIndex < viewLimit)
        {
            viewNames.Insert(HCTLViewKey(viewSelections.Get(viewIndex).GetName()));
            viewIndex = viewIndex + 1;
        }
        TStringArray seen = new TStringArray;
        string rows = "";
        string selectionName = "";
        string lowered = "";
        int scan = 0;
        while (scan < scanLimit)
        {
            selectionName = selectionNames.Get(scan);
            scan = scan + 1;
            lowered = selectionName;
            lowered.ToLower();
            if (lowered.IndexOf("proxy:") == 0 && seen.Find(selectionName) == -1)
            {
                if (seen.Count() < 24)
                {
                    if (seen.Count() > 0)
                        rows = rows + ",";
                    rows = rows + HCTLProxyRow(selectionName, viewLod, viewSelections, viewNames);
                }
                seen.Insert(selectionName);
            }
        }
        int proxyTotal = seen.Count();
        string facts = HCTLKey("proxy_count") + proxyTotal.ToString() + "," + HCTLKey("proxy_scan_complete") + HCTLBool(scanComplete) + ",";
        facts = facts + HCTLKey("view_lod") + HCTLBool(viewPresent) + "," + HCTLKey("view_selection_count") + viewTotal.ToString() + ",";
        facts = facts + HCTLKey("view_scan_complete") + HCTLBool(viewComplete) + ",";
        return facts + HCTLKey("proxies") + "[" + rows + "]";
    }

    string HCTLAttachSlotNames(EntityAI subject, int limit)
    {
        GameInventory subjectInventory = subject.GetInventory();
        string names = "";
        if (!subjectInventory)
            return "[]";
        int total = subjectInventory.GetAttachmentSlotsCount();
        int listed = 0;
        int index = 0;
        while (index < total && listed < limit)
        {
            if (listed > 0)
                names = names + ",";
            names = names + HCTLStr(InventorySlots.GetSlotName(subjectInventory.GetAttachmentSlotId(index)));
            listed = listed + 1;
            index = index + 1;
        }
        return "[" + names + "]";
    }

    string HCTLOwnSlotNames(EntityAI subject, int limit)
    {
        GameInventory subjectInventory = subject.GetInventory();
        string names = "";
        if (!subjectInventory)
            return "[]";
        int total = subjectInventory.GetSlotIdCount();
        int listed = 0;
        int index = 0;
        while (index < total && listed < limit)
        {
            if (listed > 0)
                names = names + ",";
            names = names + HCTLStr(InventorySlots.GetSlotName(subjectInventory.GetSlotId(index)));
            listed = listed + 1;
            index = index + 1;
        }
        return "[" + names + "]";
    }

    string HCTLBeamFacts(Object subject)
    {
        bool startExists = subject.MemoryPointExists("beamStart");
        bool endExists = subject.MemoryPointExists("beamEnd");
        vector startPos = "0 0 0";
        vector endPos = "0 0 0";
        if (startExists)
            startPos = subject.GetMemoryPointPos("beamStart");
        if (endExists)
            endPos = subject.GetMemoryPointPos("beamEnd");
        string beamText = HCTLKey("beam_start") + HCTLBool(startExists) + "," + HCTLKey("beam_start_pos") + HCTLVector(startPos) + ",";
        beamText = beamText + HCTLKey("beam_end") + HCTLBool(endExists) + "," + HCTLKey("beam_end_pos") + HCTLVector(endPos);
        return beamText;
    }

    void HCTLObserveLights()
    {
        int lightIndex = 0;
        string lightName = "";
        EntityAI lightItem = null;
        string row = "";
        int slotIndex = 0;
        string fits = "";
        int slotId = 0;
        while (lightIndex < m_HCTLLights.Count())
        {
            lightName = m_HCTLLights.Get(lightIndex);
            lightIndex = lightIndex + 1;
            lightItem = EntityAI.Cast(HCTLSpawn(lightName));
            row = "{" + HCTLKey("light") + HCTLStr(lightName) + ",";
            if (!lightItem)
            {
                m_HCTLLightRows.Insert(row + HCTLKey("spawned") + "false}");
                continue;
            }
            fits = "";
            slotIndex = 0;
            while (slotIndex < m_HCTLSlots.Count())
            {
                slotId = InventorySlots.GetSlotIdFromString(m_HCTLSlots.Get(slotIndex));
                if (slotIndex > 0)
                    fits = fits + ",";
                fits = fits + "{" + HCTLKey("slot") + HCTLStr(m_HCTLSlots.Get(slotIndex)) + "," + HCTLKey("fits") + HCTLBool(lightItem.GetInventory().HasInventorySlot(slotId)) + "}";
                slotIndex = slotIndex + 1;
            }
            row = row + HCTLKey("spawned") + "true," + HCTLKey("type") + HCTLStr(lightItem.GetType()) + ",";
            row = row + HCTLKey("own_slots") + HCTLOwnSlotNames(lightItem, 16) + "," + HCTLKey("fits_native_slots") + "[" + fits + "],";
            row = row + HCTLKey("attach_slots") + HCTLAttachSlotNames(lightItem, 8) + "," + HCTLBeamFacts(lightItem) + "," + HCTLSelectionFacts(lightItem) + "}";
            m_HCTLLightRows.Insert(row);
            HCTLReleaseAll();
        }
    }

    string HCTLHostSlots(EntityAI hostItem)
    {
        GameInventory hostInventory = hostItem.GetInventory();
        string result = "";
        int slotIndex = 0;
        string slotName = "";
        int slotId = 0;
        bool slotValid = false;
        bool hostHasSlot = false;
        string selection = "";
        bool selectionKnown = false;
        bool onModel = false;
        bool memoryPoint = false;
        int boneIndex = -1;
        Object boneObject = null;
        string boneType = "";
        while (slotIndex < m_HCTLSlots.Count())
        {
            slotName = m_HCTLSlots.Get(slotIndex);
            slotId = InventorySlots.GetSlotIdFromString(slotName);
            slotValid = InventorySlots.IsSlotIdValid(slotId);
            hostHasSlot = false;
            selection = "";
            selectionKnown = false;
            onModel = false;
            memoryPoint = false;
            boneIndex = -1;
            boneObject = null;
            boneType = "";
            if (slotValid && hostInventory)
            {
                hostHasSlot = hostInventory.HasAttachmentSlot(slotId);
                selectionKnown = InventorySlots.GetSelectionForSlotId(slotId, selection);
            }
            if (selectionKnown && selection != "")
            {
                onModel = hostItem.HasSelection(selection);
                memoryPoint = hostItem.MemoryPointExists(selection);
                boneIndex = hostItem.GetBoneIndex(selection);
                if (boneIndex >= 0)
                {
                    boneObject = hostItem.GetBoneObject(boneIndex);
                    if (boneObject)
                        boneType = boneObject.GetType();
                }
            }
            if (slotIndex > 0)
                result = result + ",";
            result = result + "{" + HCTLKey("slot") + HCTLStr(slotName) + "," + HCTLKey("host_has_slot") + HCTLBool(hostHasSlot) + ",";
            result = result + HCTLKey("selection") + HCTLStr(selection) + ",";
            result = result + HCTLKey("selection_on_model") + HCTLBool(onModel) + "," + HCTLKey("memory_point") + HCTLBool(memoryPoint) + ",";
            result = result + HCTLKey("bone_index") + boneIndex.ToString() + "," + HCTLKey("bone_object") + HCTLStr(boneType) + "}";
            slotIndex = slotIndex + 1;
        }
        return result;
    }

    string HCTLObserveLight(EntityAI hostItem, string lightName)
    {
        GameInventory hostInventory = hostItem.GetInventory();
        EntityAI lightItem = EntityAI.Cast(HCTLSpawn(lightName));
        string result = "{" + HCTLKey("light") + HCTLStr(lightName) + ",";
        if (!lightItem || !hostInventory)
            return result + HCTLKey("spawned") + "false}";
        bool canAddAny = hostInventory.CanAddAttachment(lightItem);
        result = result + HCTLKey("spawned") + "true," + HCTLKey("can_add_any") + HCTLBool(canAddAny) + "," + HCTLKey("per_slot") + "[";
        int slotIndex = 0;
        int slotId = 0;
        bool slotValid = false;
        bool canAddSlot = false;
        bool attachOk = false;
        string selection = "";
        bool selectionKnown = false;
        int boneIndex = -1;
        Object boneObject = null;
        string boneType = "";
        EntityAI attached = null;
        EntityAI found = null;
        string foundType = "";
        string beamFacts = "";
        while (slotIndex < m_HCTLSlots.Count())
        {
            slotId = InventorySlots.GetSlotIdFromString(m_HCTLSlots.Get(slotIndex));
            slotValid = InventorySlots.IsSlotIdValid(slotId);
            canAddSlot = false;
            attachOk = false;
            selection = "";
            selectionKnown = false;
            boneIndex = -1;
            boneObject = null;
            boneType = "";
            attached = null;
            found = null;
            foundType = "";
            beamFacts = "";
            if (slotValid)
                canAddSlot = hostInventory.CanAddAttachmentEx(lightItem, slotId);
            if (canAddSlot)
            {
                attached = hostInventory.CreateAttachmentEx(lightName, slotId);
                if (attached)
                {
                    m_HCTLLive.Insert(attached);
                    m_HCTLSpawned = m_HCTLSpawned + 1;
                    m_HCTLAttachOk = m_HCTLAttachOk + 1;
                    attachOk = true;
                    found = hostInventory.FindAttachment(slotId);
                    if (found)
                        foundType = found.GetType();
                    beamFacts = HCTLBeamFacts(attached);
                    selectionKnown = InventorySlots.GetSelectionForSlotId(slotId, selection);
                    if (selectionKnown && selection != "")
                    {
                        boneIndex = hostItem.GetBoneIndex(selection);
                        if (boneIndex >= 0)
                            boneObject = hostItem.GetBoneObject(boneIndex);
                        if (boneObject)
                            boneType = boneObject.GetType();
                    }
                }
            }
            if (slotIndex > 0)
                result = result + ",";
            result = result + "{" + HCTLKey("slot") + HCTLStr(m_HCTLSlots.Get(slotIndex)) + "," + HCTLKey("light_fits") + HCTLBool(lightItem.GetInventory().HasInventorySlot(slotId)) + ",";
            result = result + HCTLKey("can_add") + HCTLBool(canAddSlot) + "," + HCTLKey("attach_ok") + HCTLBool(attachOk) + ",";
            result = result + HCTLKey("found_type") + HCTLStr(foundType) + "," + HCTLKey("proxy_after_attach") + HCTLStr(boneType);
            if (beamFacts != "")
                result = result + "," + beamFacts;
            result = result + "}";
            slotIndex = slotIndex + 1;
        }
        return result + "]}";
    }

    bool HCTLRail(Object subject)
    {
        // Same test as UniversalLight.CanPutAsAttachment applies to the occupant of a handguard slot.
        if (!subject)
            return false;
        if (!subject.ConfigIsExisting("hasRailFunctionality"))
            return false;
        return subject.ConfigGetBool("hasRailFunctionality");
    }

    string HCTLHostPrereq(EntityAI hostItem)
    {
        GameInventory hostInventory = hostItem.GetInventory();
        string result = "";
        int prereqIndex = 0;
        int slotId = 0;
        bool owns = false;
        string occupantType = "";
        bool railFunctional = false;
        EntityAI occupant = null;
        while (prereqIndex < m_HCTLPrereqSlots.Count())
        {
            slotId = InventorySlots.GetSlotIdFromString(m_HCTLPrereqSlots.Get(prereqIndex));
            owns = false;
            occupantType = "";
            railFunctional = false;
            occupant = null;
            if (hostInventory && InventorySlots.IsSlotIdValid(slotId))
            {
                owns = hostInventory.HasAttachmentSlot(slotId);
                if (owns)
                    occupant = hostInventory.FindAttachment(slotId);
            }
            if (occupant)
            {
                occupantType = occupant.GetType();
                railFunctional = HCTLRail(occupant);
            }
            if (prereqIndex > 0)
                result = result + ",";
            result = result + "{" + HCTLKey("slot") + HCTLStr(m_HCTLPrereqSlots.Get(prereqIndex)) + "," + HCTLKey("host_has_slot") + HCTLBool(owns) + ",";
            result = result + HCTLKey("rail_functional") + HCTLBool(railFunctional) + "," + HCTLKey("attached_type") + HCTLStr(occupantType) + "}";
            prereqIndex = prereqIndex + 1;
        }
        return result;
    }

    int HCTLFirstOpenPrereq(EntityAI hostItem)
    {
        // Index of the first prerequisite slot the host owns, or -1 when it owns none or a rail is already attached.
        GameInventory hostInventory = hostItem.GetInventory();
        int firstOpen = -1;
        int prereqIndex = 0;
        int slotId = 0;
        EntityAI occupant = null;
        if (!hostInventory)
            return -1;
        while (prereqIndex < m_HCTLPrereqSlots.Count())
        {
            slotId = InventorySlots.GetSlotIdFromString(m_HCTLPrereqSlots.Get(prereqIndex));
            if (InventorySlots.IsSlotIdValid(slotId) && hostInventory.HasAttachmentSlot(slotId))
            {
                occupant = hostInventory.FindAttachment(slotId);
                if (HCTLRail(occupant))
                    return -1;
                if (firstOpen < 0)
                    firstOpen = prereqIndex;
            }
            prereqIndex = prereqIndex + 1;
        }
        return firstOpen;
    }

    string HCTLHostLightRows(EntityAI hostItem, array<string> lightNames, int beginMs)
    {
        // The class budget is checked after every observation, the last one included.
        string rows = "";
        int lightIndex = 0;
        while (lightIndex < lightNames.Count())
        {
            if (lightIndex > 0)
                rows = rows + ",";
            rows = rows + HCTLObserveLight(hostItem, lightNames.Get(lightIndex));
            lightIndex = lightIndex + 1;
            if (GetGame().GetTime() - beginMs > m_HCTLPerClassMs)
            {
                m_HCTLClassTimedOut = true;
                break;
            }
        }
        return rows;
    }

    string HCTLPrereqVariant(EntityAI baseItem, string className, int beginMs)
    {
        // A fresh copy of the host with the matching rail handguard created natively in its handguard slot.
        string result = "{" + HCTLKey("performed") + "false}";
        if (m_HCTLPrereqLights.Count() == 0 || m_HCTLClassTimedOut)
            return result;
        int prereqIndex = HCTLFirstOpenPrereq(baseItem);
        if (prereqIndex < 0)
            return result;
        string slotName = m_HCTLPrereqSlots.Get(prereqIndex);
        string handguardName = m_HCTLPrereqTypes.Get(prereqIndex);
        int slotId = InventorySlots.GetSlotIdFromString(slotName);
        EntityAI variantHost = EntityAI.Cast(HCTLSpawn(className));
        EntityAI handguard = null;
        EntityAI readBack = null;
        bool attached = false;
        bool occupied = false;
        bool railFunctional = false;
        string foundType = "";
        string lightRows = "";
        if (variantHost && variantHost.GetInventory())
        {
            handguard = variantHost.GetInventory().CreateAttachmentEx(handguardName, slotId);
            // What the slot really holds afterwards, read back natively; the requested label is not evidence.
            readBack = variantHost.GetInventory().FindAttachment(slotId);
            if (readBack)
            {
                occupied = true;
                foundType = readBack.GetType();
                railFunctional = HCTLRail(readBack);
            }
            if (handguard)
            {
                m_HCTLLive.Insert(handguard);
                m_HCTLSpawned = m_HCTLSpawned + 1;
                attached = true;
                lightRows = HCTLHostLightRows(variantHost, m_HCTLPrereqLights, beginMs);
            }
        }
        result = "{" + HCTLKey("performed") + "true," + HCTLKey("slot") + HCTLStr(slotName) + "," + HCTLKey("handguard") + HCTLStr(handguardName) + ",";
        result = result + HCTLKey("handguard_attached") + HCTLBool(attached) + "," + HCTLKey("handguard_found_type") + HCTLStr(foundType) + ",";
        result = result + HCTLKey("handguard_slot_occupied") + HCTLBool(occupied) + "," + HCTLKey("handguard_rail_functional") + HCTLBool(railFunctional) + ",";
        return result + HCTLKey("lights") + "[" + lightRows + "]}";
    }

    string HCTLObserveHost(int index)
    {
        string className = m_HCTLClasses.Get(index);
        string groupName = "no_slot_host";
        if (m_HCTLGroups.Get(index) == 1)
            groupName = "slot_host";
        int beginMs = GetGame().GetTime();
        m_HCTLClassTimedOut = false;
        string row = "{" + HCTLKey("i") + index.ToString() + "," + HCTLKey("class") + HCTLStr(className) + ",";
        row = row + HCTLKey("root") + HCTLStr(m_HCTLRoots.Get(index)) + "," + HCTLKey("group") + HCTLStr(groupName) + ",";
        EntityAI hostItem = EntityAI.Cast(HCTLSpawn(className));
        if (!hostItem)
            return row + HCTLKey("spawned") + "false," + HCTLKey("timed_out") + "false}";
        row = row + HCTLKey("spawned") + "true," + HCTLKey("type") + HCTLStr(hostItem.GetType()) + ",";
        row = row + HCTLKey("own_slots") + HCTLOwnSlotNames(hostItem, 16) + "," + HCTLKey("attach_slots") + HCTLAttachSlotNames(hostItem, 24) + "," + HCTLSelectionFacts(hostItem) + ",";
        row = row + HCTLProxyFacts(hostItem) + ",";
        row = row + HCTLKey("slots") + "[" + HCTLHostSlots(hostItem) + "]," + HCTLKey("prereq") + "[" + HCTLHostPrereq(hostItem) + "],";
        row = row + HCTLKey("lights") + "[" + HCTLHostLightRows(hostItem, m_HCTLLights, beginMs) + "],";
        row = row + HCTLKey("prereq_variant") + HCTLPrereqVariant(hostItem, className, beginMs) + ",";
        int elapsedMs = GetGame().GetTime() - beginMs;
        if (m_HCTLClassTimedOut)
            m_HCTLTimeouts = m_HCTLTimeouts + 1;
        row = row + HCTLKey("timed_out") + HCTLBool(m_HCTLClassTimedOut) + "," + HCTLKey("ms") + elapsedMs.ToString() + "}";
        HCTLReleaseAll();
        return row;
    }

    void HCTLCensusResidual()
    {
        array<Object> nearObjects = new array<Object>;
        array<CargoBase> nearCargos = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(m_HCTLPos, 8.0, nearObjects, nearCargos);
        m_HCTLCensusTotal = nearObjects.Count();
        int scanLimit = m_HCTLCensusTotal;
        if (scanLimit > @@CENSUS_LIMIT@@)
            scanLimit = @@CENSUS_LIMIT@@;
        m_HCTLCensusTruncated = m_HCTLCensusTotal > scanLimit;
        int scan = 0;
        Object nearObject = null;
        string nearType = "";
        m_HCTLResidualProbe = 0;
        m_HCTLResidualOther = 0;
        while (scan < scanLimit)
        {
            nearObject = nearObjects.Get(scan);
            scan = scan + 1;
            if (!nearObject)
                continue;
            nearType = nearObject.GetType();
            if (m_HCTLClasses.Find(nearType) != -1)
                m_HCTLResidualProbe = m_HCTLResidualProbe + 1;
            else if (m_HCTLLights.Find(nearType) != -1)
                m_HCTLResidualProbe = m_HCTLResidualProbe + 1;
            else
                m_HCTLResidualOther = m_HCTLResidualOther + 1;
        }
        m_HCTLCensusScanned = scan;
    }

    void HCTLWriteRows(FileHandle handle, string name, array<string> rows, bool last)
    {
        string tail = ",";
        if (last)
            tail = "";
        FPrintln(handle, HCTLKey(name) + "[");
        int rowIndex = 0;
        while (rowIndex < rows.Count())
        {
            if (rowIndex < rows.Count() - 1)
                FPrintln(handle, rows.Get(rowIndex) + ",");
            else
                FPrintln(handle, rows.Get(rowIndex));
            rowIndex = rowIndex + 1;
        }
        FPrintln(handle, "]" + tail);
    }

    void HCTLWriteResult()
    {
        HCTLMeasureLive();
        HCTLCensusResidual();
        string directory = "$profile:HCTapedLightProbe";
        string outputPath = directory + "/observations.json";
        string sentinelPath = directory + "/complete.txt";
        if (!FileExist(directory) && !MakeDirectory(directory))
        {
            Print("[HC Taped Light Probe] FAILED cannot create output directory");
            return;
        }
        if (FileExist(outputPath) || FileExist(sentinelPath))
        {
            Print("[HC Taped Light Probe] FAILED earlier probe output exists; not overwriting");
            return;
        }
        string world;
        string version;
        GetGame().GetWorldName(world);
        GetGame().GetVersion(version);
        FileHandle handle = OpenFile(outputPath, FileMode.WRITE);
        if (!handle)
        {
            Print("[HC Taped Light Probe] FAILED cannot open observations file");
            return;
        }
        FPrintln(handle, "{");
        FPrintln(handle, HCTLKey("schema") + "1," + HCTLKey("kind") + HCTLStr("@@OBSERVATIONS_KIND@@") + "," + HCTLKey("status") + HCTLStr(m_HCTLStatus) + ",");
        FPrintln(handle, HCTLKey("world") + HCTLStr(world) + "," + HCTLKey("version") + HCTLStr(version) + ",");
        string outLine = HCTLKey("begin_ms") + m_HCTLBeginMs.ToString() + "," + HCTLKey("end_ms") + m_HCTLEndMs.ToString() + ",";
        outLine = outLine + HCTLKey("hard_cap") + m_HCTLHardCap.ToString() + "," + HCTLKey("per_class_ms") + m_HCTLPerClassMs.ToString() + ",";
        FPrintln(handle, outLine);
        outLine = HCTLKey("classes") + m_HCTLClasses.Count().ToString() + "," + HCTLKey("observed") + m_HCTLRows.Count().ToString() + ",";
        outLine = outLine + HCTLKey("position") + HCTLVector(m_HCTLPos) + ",";
        FPrintln(handle, outLine);
        outLine = HCTLKey("counters") + "{" + HCTLKey("spawned") + m_HCTLSpawned.ToString() + "," + HCTLKey("deleted") + m_HCTLDeleted.ToString() + ",";
        outLine = outLine + HCTLKey("timeouts") + m_HCTLTimeouts.ToString() + "," + HCTLKey("attach_ok") + m_HCTLAttachOk.ToString() + ",";
        outLine = outLine + HCTLKey("live_after_release") + m_HCTLLiveAfterRelease.ToString() + ",";
        outLine = outLine + HCTLKey("residual_probe_types") + m_HCTLResidualProbe.ToString() + "," + HCTLKey("residual_other") + m_HCTLResidualOther.ToString() + ",";
        FPrintln(handle, outLine);
        bool censusComplete = !m_HCTLCensusTruncated && m_HCTLCensusScanned == m_HCTLCensusTotal;
        outLine = HCTLKey("census_total") + m_HCTLCensusTotal.ToString() + "," + HCTLKey("census_scanned") + m_HCTLCensusScanned.ToString() + ",";
        outLine = outLine + HCTLKey("census_truncated") + HCTLBool(m_HCTLCensusTruncated) + "," + HCTLKey("census_complete") + HCTLBool(censusComplete) + "},";
        FPrintln(handle, outLine);
        HCTLWriteRows(handle, "slots", m_HCTLSlotRows, false);
        HCTLWriteRows(handle, "lights", m_HCTLLightRows, false);
        HCTLWriteRows(handle, "hosts", m_HCTLRows, true);
        FPrintln(handle, "}");
        CloseFile(handle);
        if (!FileExist(outputPath))
        {
            Print("[HC Taped Light Probe] FAILED observations file missing after write");
            return;
        }
        FileHandle sentinel = OpenFile(sentinelPath, FileMode.WRITE);
        if (!sentinel)
        {
            Print("[HC Taped Light Probe] FAILED cannot open sentinel file");
            return;
        }
        string sentinelText = "status=" + m_HCTLStatus + " observed=" + m_HCTLRows.Count().ToString();
        sentinelText = sentinelText + " spawned=" + m_HCTLSpawned.ToString() + " deleted=" + m_HCTLDeleted.ToString();
        FPrintln(sentinel, sentinelText);
        CloseFile(sentinel);
        string summaryText = "[HC Taped Light Probe] observed=" + m_HCTLRows.Count().ToString() + " spawned=" + m_HCTLSpawned.ToString();
        summaryText = summaryText + " deleted=" + m_HCTLDeleted.ToString() + " residual=" + m_HCTLResidualProbe.ToString();
        Print(summaryText);
        Print("[HC Taped Light Probe] COMPLETE");
    }
}
"""


def _positive_int(value, low, high, what):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{what} must be an integer {low}..{high}")
    return value


def _validate_position(position):
    try:
        x, z = position
    except (TypeError, ValueError) as error:
        raise ValueError("position must be (x, z)") from error
    for value in (x, z):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
                or not 0.0 < value < WORLD_EXTENT:
            raise ValueError("position must be two finite coordinates inside the world")
    return float(x), float(z)


def watchdog_ms(host_count, start_delay_s, per_class_ms):
    """Worst case: every class consumes its full budget; the watchdog finishes partial after that."""
    return start_delay_s * 1000 + (host_count + 2) * (per_class_ms + STEP_MS) + 60000


def render_hook(targets, start_delay_s=DEFAULT_START_DELAY_S, per_class_ms=DEFAULT_PER_CLASS_MS,
                position=DEFAULT_POSITION):
    """Return the generated Enforce text (bytes) with every host, light and slot inlined as data."""
    hosts, lights, slots = targets.get("hosts"), targets.get("lights"), targets.get("slots")
    if not hosts or len(hosts) > HARD_CAP:
        raise ValueError(f"1..{HARD_CAP} hosts required")
    if not lights or len(lights) > MAX_LIGHTS:
        raise ValueError(f"1..{MAX_LIGHTS} lights required")
    if not slots or len(slots) > MAX_SLOTS:
        raise ValueError(f"1..{MAX_SLOTS} slots required")
    _positive_int(start_delay_s, MIN_START_DELAY_S, MAX_START_DELAY_S, "start delay (s)")
    _positive_int(per_class_ms, MIN_PER_CLASS_MS, MAX_PER_CLASS_MS, "per-class timeout (ms)")
    x, z = _validate_position(position)
    host_adds = []
    for host in hosts:
        name, root, group = _ident(host["class"], "host class"), _ident(host["root"], "host root"), host["group"]
        if group not in GROUP_CODES:
            raise ValueError("host group must be slot_host or no_slot_host")
        host_adds.append('        HCTLAddHost("%s", "%s", %d);' % (name, root, GROUP_CODES[group]))
    meta = ['        HCTLAddLight("%s");' % _ident(name, "light class") for name in lights]
    meta += ['        HCTLAddSlot("%s");' % _ident(name, "slot name") for name in slots]
    meta += ['        HCTLAddPrereq("%s", "%s");' % pair for pair in PREREQUISITE_HANDGUARDS]
    meta += ['        HCTLAddPrereqLight("%s");' % _ident(name, "light class") for name in lights if name in PREREQUISITE_LIGHTS]
    chunks = [host_adds[i:i + LOADER_CHUNK] for i in range(0, len(host_adds), LOADER_CHUNK)]
    calls = "        HCTLLoadMeta();\n" + "\n".join(f"        HCTLLoadHosts{n}();" for n in range(len(chunks)))
    loaders = "".join("    void HCTLLoadHosts%d()\n    {\n%s\n    }\n\n" % (n, "\n".join(chunk))
                      for n, chunk in enumerate(chunks))
    text = (HOOK_TEMPLATE.replace("@@LOADER_CALLS@@", calls).replace("@@META_ADDS@@", "\n".join(meta))
            .replace("@@HOST_LOADERS@@", loaders).replace("@@HARD_CAP@@", str(HARD_CAP))
            .replace("@@CENSUS_LIMIT@@", str(CENSUS_SCAN_LIMIT))
            .replace("@@PER_CLASS_MS@@", str(per_class_ms)).replace("@@START_MS@@", str(start_delay_s * 1000))
            .replace("@@STEP_MS@@", str(STEP_MS))
            .replace("@@WATCHDOG_MS@@", str(watchdog_ms(len(hosts), start_delay_s, per_class_ms)))
            .replace("@@POS_X@@", "%.1f" % x).replace("@@POS_Z@@", "%.1f" % z)
            .replace("@@OBSERVATIONS_KIND@@", OBSERVATIONS_KIND))
    if "@@" in text or not text.isascii():
        raise ValueError("hook must be ASCII with every placeholder resolved")
    return text.encode("ascii")

# ---------------------------------------------------------------------------
# Staging (shared lint, name rule, verification and skeleton live in probe_runtime)
# ---------------------------------------------------------------------------


def windows_runtime_root(path, wsl_parent=None):
    """Map a direct child of the probe parent to its Windows runtime root, or raise."""
    return rt.windows_runtime_root(path, WSL_PARENT if wsl_parent is None else wsl_parent)


def _verify_source(source_runtime, battleye_sha256):
    return rt.verify_source(source_runtime, battleye_sha256)


def stage(source_runtime, destination, classification, *, start_delay_s=DEFAULT_START_DELAY_S,
          per_class_ms=DEFAULT_PER_CLASS_MS, position=DEFAULT_POSITION, wait_minutes=None,
          battleye_sha256=BATTLEYE_SHA256, native_scripts=None, now=None, _wsl_parent=None):
    """Stage a fresh probe runtime and write taped-light-probe-plan.json. Never launches anything.

    ``_wsl_parent`` is an internal test hook; the production parent is always WSL_PARENT
    and the Windows root is always derived from the destination, never supplied.
    """
    targets = select_targets(classification)
    hook = render_hook(targets, start_delay_s, per_class_ms, position)
    native = native_type_names(native_scripts) if native_scripts else frozenset()
    problems = lint_hook(hook.decode("ascii"), native_types=native, explicit_numbers=True)
    if problems:
        raise ValueError("generated hook violates native compile rules: " + "; ".join(problems[:3]))
    worst_minutes = math.ceil(watchdog_ms(len(targets["hosts"]), start_delay_s, per_class_ms) / 60000) + 3
    if wait_minutes is None:
        wait_minutes = max(5, worst_minutes)
    if not 5 <= wait_minutes <= MAX_WORST_CASE_MINUTES or wait_minutes < worst_minutes:
        raise ValueError(f"wait minutes must be 5..{MAX_WORST_CASE_MINUTES} and cover the {worst_minutes} minute worst case")
    context = rt.begin(source_runtime, destination, parent=WSL_PARENT if _wsl_parent is None else _wsl_parent,
                       battleye_sha256=battleye_sha256)
    built = rt.build_runtime(context, hook, purpose="taped-light-probe")

    groups = {group: sum(1 for h in targets["hosts"] if h["group"] == group) for group in PROBED_GROUPS}
    plan = rt.plan_header(PLAN_KIND, now, before={"acceptance": "PENDING"}, after={"variant": "probe"})
    plan.update(rt.plan_runtime_fields(context, built))
    plan.update({
        "probe": {"mode": "server-only-no-clients", "clients": 0, "host_count": len(targets["hosts"]),
                  "groups": groups, "excluded_not_probed": targets["excluded_not_probed"],
                  "lights": targets["lights"], "slots": targets["slots"], "hard_cap": HARD_CAP,
                  "per_class_ms": per_class_ms, "start_delay_s": start_delay_s,
                  "position": [float(v) for v in _validate_position(position)],
                  "watchdog_ms": watchdog_ms(len(targets["hosts"]), start_delay_s, per_class_ms),
                  "wait_minutes": wait_minutes, "hook_sha256": sha256(hook), "hook_bytes": len(hook),
                  "classification_sha256": sha256(json.dumps(classification, sort_keys=True).encode("utf-8")),
                  "output_relative_path": OUTPUT_RELATIVE, "sentinel_relative_path": SENTINEL_RELATIVE,
                  "observations_kind": OBSERVATIONS_KIND},
        "targets": targets["hosts"],
        "mission_files": built["mission_files"], "staged_files": built["staged"],
    })
    return rt.write_plan(context["destination"], PLAN_NAME, plan)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--destination", required=True, help="fresh runtime directory (must not exist)")
    parser.add_argument("--classification", required=True, help="flashlight_matrix classify output (JSON)")
    parser.add_argument("--source-runtime", default=DEFAULT_SOURCE_RUNTIME)
    parser.add_argument("--start-delay-s", type=int, default=DEFAULT_START_DELAY_S)
    parser.add_argument("--per-class-ms", type=int, default=DEFAULT_PER_CLASS_MS)
    parser.add_argument("--position", type=float, nargs=2, metavar=("X", "Z"), default=list(DEFAULT_POSITION))
    parser.add_argument("--wait-minutes", type=int)
    parser.add_argument("--battleye-sha256", default=BATTLEYE_SHA256)
    parser.add_argument("--native-scripts", help="extracted native script cache used to lint the hook")
    args = parser.parse_args(argv)
    cache = args.native_scripts
    if cache is None:
        default = Path.home() / ".cache/hollow-country/native-scripts/scripts-1.30.164289"
        cache = default if (default / "3_Game").is_dir() else None
    try:
        classification = json.loads(_read_bounded(args.classification, MAX_CLASSIFICATION_BYTES))
        plan = stage(args.source_runtime, args.destination, classification, start_delay_s=args.start_delay_s,
                     per_class_ms=args.per_class_ms, position=tuple(args.position), wait_minutes=args.wait_minutes,
                     battleye_sha256=args.battleye_sha256, native_scripts=cache)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"taped_light_probe: {error}", file=sys.stderr)
        return 1
    print(f"staged taped-light probe runtime: {Path(args.destination) / PLAN_NAME}")
    print(f"hosts={plan['probe']['host_count']} lights={len(plan['probe']['lights'])} "
          f"hook_bytes={plan['probe']['hook_bytes']} hook_sha256={plan['probe']['hook_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
