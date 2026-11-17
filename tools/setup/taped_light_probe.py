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
"""
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import re
import sys

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
MAX_WORST_CASE_MINUTES = 240
DEFAULT_START_DELAY_S = 25
DEFAULT_PER_CLASS_MS = 2000
DEFAULT_POSITION = (7680.0, 7680.0)
WORLD_EXTENT = 15360.0
MAX_CLASSIFICATION_BYTES = 8 * 1024 * 1024
MAX_PLAN_BYTES = 1024 * 1024
LOADER_CHUNK = 40
NAME_RULE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
IDENT_RULE = re.compile(r"^[A-Za-z0-9_]{1,64}$")
PROBED_GROUPS = ("slot_host", "no_slot_host")
GROUP_CODES = {"no_slot_host": 0, "slot_host": 1}
PROBE_ROLES = ("representative", "control")
# Stock files whose launch-plan pin is the verified runtime's scheduled-shutdown delta,
# not the stock bytes. They are recorded with their stock hash, never silently accepted.
PLAN_PIN_DELTAS = frozenset({"db/messages.xml"})

# ---------------------------------------------------------------------------
# Classification input and target selection
# ---------------------------------------------------------------------------


def sha256(data):
    return hashlib.sha256(data).hexdigest()


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
    protected string m_HCTLQuote = "";
    protected string m_HCTLSlash = "";
    protected string m_HCTLStatus = "running";
    protected vector m_HCTLPos;
    protected ref array<string> m_HCTLClasses = new array<string>;
    protected ref array<string> m_HCTLRoots = new array<string>;
    protected ref array<int> m_HCTLGroups = new array<int>;
    protected ref array<string> m_HCTLLights = new array<string>;
    protected ref array<string> m_HCTLSlots = new array<string>;
    protected ref array<Object> m_HCTLLive = new array<Object>;
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
        Print("[HC Taped Light Probe] ARMED; observation only; classes=" + m_HCTLClasses.Count());
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
        return "[" + value[0] + "," + value[1] + "," + value[2] + "]";
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
            }
            releaseIndex = releaseIndex - 1;
        }
        m_HCTLLive.Clear();
    }

    void HCTLStep()
    {
        if (m_HCTLDone)
            return;
        if (m_HCTLCursor == 0)
        {
            m_HCTLBeginMs = GetGame().GetTime();
            Print("[HC Taped Light Probe] BEGIN; observation only; classes=" + m_HCTLClasses.Count());
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
            m_HCTLSlotRows.Insert("{" + HCTLKey("slot") + HCTLStr(slotName) + "," + HCTLKey("id") + slotId + "," + HCTLKey("valid") + HCTLBool(slotValid) + "," + HCTLKey("selection") + HCTLStr(selection) + "," + HCTLKey("selection_known") + HCTLBool(selectionKnown) + "," + HCTLKey("bone") + HCTLStr(bone) + "," + HCTLKey("bone_known") + HCTLBool(boneKnown) + "}");
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
        return HCTLKey("selection_count") + total + "," + HCTLKey("selection_matches") + "[" + matches + "]";
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
        return HCTLKey("beam_start") + HCTLBool(startExists) + "," + HCTLKey("beam_start_pos") + HCTLVector(startPos) + "," + HCTLKey("beam_end") + HCTLBool(endExists) + "," + HCTLKey("beam_end_pos") + HCTLVector(endPos);
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
            result = result + "{" + HCTLKey("slot") + HCTLStr(slotName) + "," + HCTLKey("host_has_slot") + HCTLBool(hostHasSlot) + "," + HCTLKey("selection") + HCTLStr(selection) + ",";
            result = result + HCTLKey("selection_on_model") + HCTLBool(onModel) + "," + HCTLKey("memory_point") + HCTLBool(memoryPoint) + "," + HCTLKey("bone_index") + boneIndex + "," + HCTLKey("bone_object") + HCTLStr(boneType) + "}";
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
            result = result + "{" + HCTLKey("slot") + HCTLStr(m_HCTLSlots.Get(slotIndex)) + "," + HCTLKey("light_fits") + HCTLBool(lightItem.GetInventory().HasInventorySlot(slotId)) + "," + HCTLKey("can_add") + HCTLBool(canAddSlot) + "," + HCTLKey("attach_ok") + HCTLBool(attachOk) + ",";
            result = result + HCTLKey("found_type") + HCTLStr(foundType) + "," + HCTLKey("proxy_after_attach") + HCTLStr(boneType);
            if (beamFacts != "")
                result = result + "," + beamFacts;
            result = result + "}";
            slotIndex = slotIndex + 1;
        }
        return result + "]}";
    }

    string HCTLObserveHost(int index)
    {
        string className = m_HCTLClasses.Get(index);
        string groupName = "no_slot_host";
        if (m_HCTLGroups.Get(index) == 1)
            groupName = "slot_host";
        int beginMs = GetGame().GetTime();
        m_HCTLClassTimedOut = false;
        string row = "{" + HCTLKey("i") + index + "," + HCTLKey("class") + HCTLStr(className) + "," + HCTLKey("root") + HCTLStr(m_HCTLRoots.Get(index)) + "," + HCTLKey("group") + HCTLStr(groupName) + ",";
        EntityAI hostItem = EntityAI.Cast(HCTLSpawn(className));
        if (!hostItem)
            return row + HCTLKey("spawned") + "false," + HCTLKey("timed_out") + "false}";
        row = row + HCTLKey("spawned") + "true," + HCTLKey("type") + HCTLStr(hostItem.GetType()) + ",";
        row = row + HCTLKey("own_slots") + HCTLOwnSlotNames(hostItem, 16) + "," + HCTLKey("attach_slots") + HCTLAttachSlotNames(hostItem, 24) + "," + HCTLSelectionFacts(hostItem) + ",";
        row = row + HCTLKey("slots") + "[" + HCTLHostSlots(hostItem) + "]," + HCTLKey("lights") + "[";
        int lightIndex = 0;
        string lightName = "";
        while (lightIndex < m_HCTLLights.Count())
        {
            if (GetGame().GetTime() - beginMs > m_HCTLPerClassMs)
            {
                m_HCTLClassTimedOut = true;
                break;
            }
            lightName = m_HCTLLights.Get(lightIndex);
            if (lightIndex > 0)
                row = row + ",";
            row = row + HCTLObserveLight(hostItem, lightName);
            lightIndex = lightIndex + 1;
        }
        int elapsedMs = GetGame().GetTime() - beginMs;
        if (m_HCTLClassTimedOut)
            m_HCTLTimeouts = m_HCTLTimeouts + 1;
        row = row + "]," + HCTLKey("timed_out") + HCTLBool(m_HCTLClassTimedOut) + "," + HCTLKey("ms") + elapsedMs + "}";
        HCTLReleaseAll();
        return row;
    }

    void HCTLCensusResidual()
    {
        array<Object> nearObjects = new array<Object>;
        array<CargoBase> nearCargos = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(m_HCTLPos, 8.0, nearObjects, nearCargos);
        int scanLimit = nearObjects.Count();
        if (scanLimit > 512)
            scanLimit = 512;
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
        FPrintln(handle, HCTLKey("begin_ms") + m_HCTLBeginMs + "," + HCTLKey("end_ms") + m_HCTLEndMs + "," + HCTLKey("hard_cap") + m_HCTLHardCap + "," + HCTLKey("per_class_ms") + m_HCTLPerClassMs + ",");
        FPrintln(handle, HCTLKey("classes") + m_HCTLClasses.Count() + "," + HCTLKey("observed") + m_HCTLRows.Count() + "," + HCTLKey("position") + HCTLVector(m_HCTLPos) + ",");
        FPrintln(handle, HCTLKey("counters") + "{" + HCTLKey("spawned") + m_HCTLSpawned + "," + HCTLKey("deleted") + m_HCTLDeleted + "," + HCTLKey("timeouts") + m_HCTLTimeouts + "," + HCTLKey("attach_ok") + m_HCTLAttachOk + "," + HCTLKey("live_after_release") + m_HCTLLive.Count() + "," + HCTLKey("residual_probe_types") + m_HCTLResidualProbe + "," + HCTLKey("residual_other") + m_HCTLResidualOther + "},");
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
        FPrintln(sentinel, "status=" + m_HCTLStatus + " observed=" + m_HCTLRows.Count() + " spawned=" + m_HCTLSpawned + " deleted=" + m_HCTLDeleted);
        CloseFile(sentinel);
        Print("[HC Taped Light Probe] observed=" + m_HCTLRows.Count() + " spawned=" + m_HCTLSpawned + " deleted=" + m_HCTLDeleted + " residual=" + m_HCTLResidualProbe);
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
    chunks = [host_adds[i:i + LOADER_CHUNK] for i in range(0, len(host_adds), LOADER_CHUNK)]
    calls = "        HCTLLoadMeta();\n" + "\n".join(f"        HCTLLoadHosts{n}();" for n in range(len(chunks)))
    loaders = "".join("    void HCTLLoadHosts%d()\n    {\n%s\n    }\n\n" % (n, "\n".join(chunk))
                      for n, chunk in enumerate(chunks))
    text = (HOOK_TEMPLATE.replace("@@LOADER_CALLS@@", calls).replace("@@META_ADDS@@", "\n".join(meta))
            .replace("@@HOST_LOADERS@@", loaders).replace("@@HARD_CAP@@", str(HARD_CAP))
            .replace("@@PER_CLASS_MS@@", str(per_class_ms)).replace("@@START_MS@@", str(start_delay_s * 1000))
            .replace("@@STEP_MS@@", str(STEP_MS))
            .replace("@@WATCHDOG_MS@@", str(watchdog_ms(len(hosts), start_delay_s, per_class_ms)))
            .replace("@@POS_X@@", "%.1f" % x).replace("@@POS_Z@@", "%.1f" % z)
            .replace("@@OBSERVATIONS_KIND@@", OBSERVATIONS_KIND))
    if "@@" in text or not text.isascii():
        raise ValueError("hook must be ASCII with every placeholder resolved")
    return text.encode("ascii")


# ---------------------------------------------------------------------------
# Enforce compile-shape lint (rules observed in native compiles; copied from the CE probe)
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
# (callee, positions of arguments that are `out` parameters and must be declared first)
_OUT_CALLS = (("GetObjectsAtPosition3D", (2, 3)), ("GetSelectionForSlotId", (1,)),
              ("GetBoneNameForSlotId", (1,)), ("GetSelectionList", (0,)))


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
    for header, body, _start in _function_bodies(clean):
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
    plan_bytes = _read_bounded(source_runtime / "launch-plan.json", MAX_PLAN_BYTES)
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
    records = {}
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
    return {"mission": mission, "records": records, "config": config, "battleye": battleye,
            "launch_plan_sha256": sha256(plan_bytes)}


def _instrument(blob, hook):
    """Stock init.c with the factory substituted plus the appended generated hook."""
    if len(blob) > dm.MAX_INIT_BYTES:
        raise ValueError("init.c byte budget exceeded")
    if b"HCDisposableDiagnosticMission" in blob or b"[HC Diagnostic Mission]" in blob:
        raise ValueError("previously instrumented init.c forbidden")
    if len(re.findall(rb"\bclass\s+CustomMission\s*:\s*MissionServer\b", blob)) != 1:
        raise ValueError("expected stock CustomMission inheritance")
    if len(re.findall(rb"\bCreateCustomMission\s*\(", blob)) != 1:
        raise ValueError("expected exactly one stock mission factory")
    result, count = dm._FACTORY.subn(rb"\g<1>HCDisposableDiagnosticMission\g<2>", blob)
    if count != 1:
        raise ValueError("unsupported stock mission factory shape")
    return result + hook


def _prepare_mission(source, destination, hook):
    """Write a fresh isolated mission copy with the hook appended; never launches anything."""
    source, destination = dm._safe_path(source), dm._safe_path(destination)
    if not source.is_dir():
        raise ValueError("source mission directory required")
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("source/destination overlap forbidden")
    if destination.exists() or destination.is_symlink():
        raise ValueError("destination must be fresh; no overwrite")
    files, directories, total = dm._inventory(source)
    initial = next((info for name, info in files if name.as_posix() == "init.c"), None)
    if initial is None or initial.st_size > dm.MAX_INIT_BYTES:
        raise ValueError("bounded stock init.c required")
    init_path = source / "init.c"
    dm._unchanged(init_path, initial)
    with init_path.open("rb") as stream:
        original = stream.read(dm.MAX_INIT_BYTES + 1)
    dm._unchanged(init_path, initial)
    instrumented = _instrument(original, hook)
    dm._safe_path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for relative in directories:
        (destination / relative).mkdir(exist_ok=False)
    manifest = {"schema": 1, "kind": "disposable-taped-light-probe", "runtime_acceptance": "pending",
                "source_root": str(source), "mission_path": str(destination), "source_bytes": total, "files": {},
                "init_change": "stock factory subclass substitution plus authored appended OnInit hook",
                "hook_sha256": sha256(hook),
                "requires": ["server mode", "fresh storage and profiles", "no clients",
                             "inspect observation completeness separately from startup"]}
    for relative, info in files:
        src, dst = source / relative, destination / relative
        dm._unchanged(src, info)
        digest = hashlib.sha256()
        if relative.as_posix() == "init.c":
            digest.update(original)
            with dst.open("xb") as output:
                output.write(instrumented)
            staged_hash, staged_bytes = sha256(instrumented), len(instrumented)
        else:
            remaining = info.st_size
            with src.open("rb") as stream, dst.open("xb") as output:
                while remaining:
                    chunk = stream.read(min(131072, remaining))
                    if not chunk:
                        raise ValueError("source truncated during copy")
                    digest.update(chunk)
                    output.write(chunk)
                    remaining -= len(chunk)
                if stream.read(1):
                    raise ValueError("source grew during copy")
            staged_hash, staged_bytes = digest.hexdigest(), info.st_size
        dm._unchanged(src, info)
        manifest["files"][relative.as_posix()] = {
            "source_sha256": digest.hexdigest(), "staged_sha256": staged_hash,
            "source_bytes": info.st_size, "staged_bytes": staged_bytes}
    with (destination / dm.MARKER_NAME).open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return manifest


def _new_file(path, data):
    with open(path, "xb") as stream:
        stream.write(data)


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
    problems = lint_hook(hook.decode("ascii"), native_types=native)
    if problems:
        raise ValueError("generated hook violates native compile rules: " + "; ".join(problems[:3]))
    source_runtime, destination = dm._safe_path(source_runtime), dm._safe_path(destination)
    if source_runtime == destination or source_runtime in destination.parents or destination in source_runtime.parents:
        raise ValueError("source/destination overlap forbidden")
    if destination.exists() or destination.is_symlink():
        raise ValueError("destination must be fresh; no overwrite")
    parent = Path(WSL_PARENT if _wsl_parent is None else _wsl_parent)
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError(f"probe parent directory {parent} must exist and not be a symlink")
    windows_root = windows_runtime_root(destination, parent)
    worst_minutes = math.ceil(watchdog_ms(len(targets["hosts"]), start_delay_s, per_class_ms) / 60000) + 3
    if wait_minutes is None:
        wait_minutes = max(5, worst_minutes)
    if not 5 <= wait_minutes <= MAX_WORST_CASE_MINUTES or wait_minutes < worst_minutes:
        raise ValueError(f"wait minutes must be 5..{MAX_WORST_CASE_MINUTES} and cover the {worst_minutes} minute worst case")
    source = _verify_source(source_runtime, battleye_sha256)

    mission_dest = destination / "mpmissions" / MISSION_NAME
    manifest = _prepare_mission(source["mission"], mission_dest, hook)
    for name in ("storage", "profiles", "battleye"):
        (destination / name).mkdir(exist_ok=False)
    _new_file(destination / "serverDZ.cfg", source["config"].read_bytes())
    _new_file(destination / "battleye/BEServer_x64.dll", source["battleye"].read_bytes())

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
        entry["origin"] = "instrumented" if name == "init.c" else "stock-copy"
        mission_files.append(entry)

    groups = {group: sum(1 for h in targets["hosts"] if h["group"] == group) for group in PROBED_GROUPS}
    windows_mission = f"{windows_root}\\mpmissions\\{MISSION_NAME}"
    plan = {
        "schema_version": 1, "kind": PLAN_KIND, "status": "staged-only-not-launched", "acceptance": "PENDING",
        "staged_utc": (now or datetime.datetime.now(datetime.timezone.utc)).isoformat(),
        "variant": "probe",
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
        "mission_files": mission_files, "staged_files": staged,
    }
    with open(destination / PLAN_NAME, "x", encoding="utf-8") as stream:
        json.dump(plan, stream, indent=2)
        stream.write("\n")
    return plan


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
